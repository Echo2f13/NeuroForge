"""Retriever for NeuroForge.

Implements multiple retrieval strategies over the vector store and knowledge graph:
- Semantic search: embed query and find top-k similar chunks
- Filtered search: semantic search constrained by metadata filters
- Graph retrieval: concept + prerequisites + related concepts → chunks
- Hybrid retrieval: combine semantic and graph-augmented results
"""

from __future__ import annotations

import json
from typing import Optional

from src.store import KnowledgeGraph, VectorStore


class Retriever:
    """Multi-strategy retriever combining vector search and graph traversal.

    Orchestrates retrieval across ChromaDB (semantic similarity) and
    the knowledge graph (concept relationships) to produce comprehensive,
    context-rich results.

    Args:
        vector_store: Initialized VectorStore with document chunks and concepts.
        knowledge_graph: Initialized KnowledgeGraph with concept relationships.
    """

    def __init__(
        self, vector_store: VectorStore, knowledge_graph: KnowledgeGraph
    ) -> None:
        """Initialize the Retriever.

        Args:
            vector_store: VectorStore instance with collections initialized.
            knowledge_graph: KnowledgeGraph instance with concepts loaded.
        """
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Embed the query and find top-k similar chunks from ChromaDB.

        Uses the document_chunks collection's embedding function to encode
        the query and retrieve the most relevant chunks by cosine similarity.

        Args:
            query: Natural language search query.
            top_k: Number of results to return.

        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        results = self.vector_store.chunks_collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        return self._format_chunk_results(results)

    # ------------------------------------------------------------------
    # Filtered search
    # ------------------------------------------------------------------

    def filtered_search(
        self,
        query: str,
        top_k: int = 5,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> list[dict]:
        """Semantic search with metadata filters on the concepts collection.

        Queries the concepts collection with optional topic and difficulty
        filters, then fetches the source chunks for matching concepts.

        Args:
            query: Natural language search query.
            top_k: Number of concept results to consider.
            topic: Filter by topic (exact match within JSON topics list).
            difficulty: Filter by difficulty level (easy, medium, hard).

        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        where_filter = self._build_where_filter(topic=topic, difficulty=difficulty)

        query_kwargs: dict = {
            "query_texts": [query],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = self.vector_store.concepts_collection.query(**query_kwargs)

        # Extract source chunk IDs from concept metadata
        chunk_ids: list[str] = []
        concept_scores: dict[str, float] = {}

        if results["ids"] and results["ids"][0]:
            for i, meta in enumerate(results["metadatas"][0]):  # type: ignore[index]
                source_chunks_json = meta.get("source_chunks", "[]")
                source_chunks = json.loads(source_chunks_json)
                distance = results["distances"][0][i] if results["distances"] else 0.0  # type: ignore[index]
                for chunk_id in source_chunks:
                    if chunk_id not in concept_scores:
                        chunk_ids.append(chunk_id)
                        concept_scores[chunk_id] = 1.0 - distance

        # Fetch the actual chunks
        return self._fetch_chunks_by_ids(chunk_ids, concept_scores)

    # ------------------------------------------------------------------
    # Graph-based retrieval
    # ------------------------------------------------------------------

    def graph_retrieval(self, concept_id: str) -> list[dict]:
        """Retrieve a concept and its related concepts, then fetch their chunks.

        Traverses the knowledge graph to find the target concept, its
        prerequisites (transitive), and directly related concepts. Then
        fetches the associated document chunks for all discovered concepts.

        Args:
            concept_id: The ID of the concept to start from.

        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        if concept_id not in self.knowledge_graph:
            return []

        # Gather concept IDs: target + prerequisites + related
        concept_ids: list[str] = [concept_id]
        prerequisites = self.knowledge_graph.get_prerequisites(concept_id)
        related = self.knowledge_graph.get_related(concept_id)

        concept_ids.extend(prerequisites)
        concept_ids.extend(related)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_ids: list[str] = []
        for cid in concept_ids:
            if cid not in seen:
                seen.add(cid)
                unique_ids.append(cid)

        # For each concept, get its source chunk IDs from the vector store
        all_chunk_ids: list[str] = []
        for cid in unique_ids:
            concept_data = self.vector_store.get_concept(cid)
            if concept_data and concept_data.get("metadata"):
                source_chunks_json = concept_data["metadata"].get("source_chunks", "[]")
                source_chunks = json.loads(source_chunks_json)
                all_chunk_ids.extend(source_chunks)

        # Deduplicate chunk IDs
        seen_chunks: set[str] = set()
        unique_chunk_ids: list[str] = []
        for chunk_id in all_chunk_ids:
            if chunk_id not in seen_chunks:
                seen_chunks.add(chunk_id)
                unique_chunk_ids.append(chunk_id)

        # Assign scores: target concept chunks score highest, then
        # prerequisites, then related
        chunk_scores: dict[str, float] = {}
        for cid in unique_ids:
            concept_data = self.vector_store.get_concept(cid)
            if concept_data and concept_data.get("metadata"):
                source_chunks_json = concept_data["metadata"].get("source_chunks", "[]")
                source_chunks = json.loads(source_chunks_json)
                if cid == concept_id:
                    score = 1.0
                elif cid in prerequisites:
                    score = 0.7
                else:
                    score = 0.5
                for chunk_id in source_chunks:
                    # Keep the highest score if a chunk appears in multiple concepts
                    if chunk_id not in chunk_scores or score > chunk_scores[chunk_id]:
                        chunk_scores[chunk_id] = score

        return self._fetch_chunks_by_ids(unique_chunk_ids, chunk_scores)

    # ------------------------------------------------------------------
    # Hybrid retrieval
    # ------------------------------------------------------------------

    def hybrid_retrieval(self, query: str, top_k: int = 10) -> list[dict]:
        """Combine semantic search with graph-augmented retrieval.

        Strategy:
        1. Run semantic search to get top candidates.
        2. Identify concepts mentioned in semantic results (via metadata).
        3. Expand via graph: get prerequisites + related for each concept.
        4. Fetch chunks for expanded concepts.
        5. Merge all results, deduplicate by chunk ID, sort by score.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.

        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        # Step 1: Semantic search
        semantic_results = self.semantic_search(query, top_k=top_k)

        # Step 2: Find concepts related to the query via concepts collection
        concept_results = self.vector_store.concepts_collection.query(
            query_texts=[query],
            n_results=min(top_k, 5),
            include=["metadatas", "distances"],
        )

        # Step 3: Expand via graph
        graph_chunks: list[dict] = []
        if concept_results["ids"] and concept_results["ids"][0]:
            for concept_id in concept_results["ids"][0]:
                if concept_id in self.knowledge_graph:
                    graph_results = self.graph_retrieval(concept_id)
                    graph_chunks.extend(graph_results)

        # Step 4: Merge and deduplicate
        merged: dict[str, dict] = {}

        for result in semantic_results:
            rid = result["id"]
            if rid not in merged or result["score"] > merged[rid]["score"]:
                merged[rid] = result

        for result in graph_chunks:
            rid = result["id"]
            # Discount graph scores slightly to prefer direct semantic matches
            adjusted_score = result["score"] * 0.8
            if rid not in merged:
                result_copy = result.copy()
                result_copy["score"] = adjusted_score
                merged[rid] = result_copy
            else:
                # Boost score if found by both methods
                merged[rid]["score"] = min(
                    1.0, merged[rid]["score"] + adjusted_score * 0.2
                )

        # Step 5: Sort by score descending, take top_k
        sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:top_k]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_chunk_results(results: dict) -> list[dict]:
        """Convert raw ChromaDB query results into a standardized format.

        Args:
            results: Raw results dict from ChromaDB collection.query().

        Returns:
            List of formatted result dicts.
        """
        formatted: list[dict] = []

        if not results["ids"] or not results["ids"][0]:
            return formatted

        ids = results["ids"][0]
        documents = results["documents"][0] if results.get("documents") else [None] * len(ids)  # type: ignore[index]
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)  # type: ignore[index]
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)  # type: ignore[index]

        for i, doc_id in enumerate(ids):
            # ChromaDB returns distances; convert to similarity score (1 - distance)
            score = 1.0 - distances[i] if distances[i] is not None else 0.0
            formatted.append(
                {
                    "id": doc_id,
                    "content": documents[i] or "",
                    "score": max(0.0, score),
                    "metadata": metadatas[i] or {},
                }
            )

        return formatted

    def _fetch_chunks_by_ids(
        self, chunk_ids: list[str], scores: dict[str, float]
    ) -> list[dict]:
        """Fetch chunks from the vector store by their IDs.

        Args:
            chunk_ids: List of chunk IDs to fetch.
            scores: Mapping of chunk_id → relevance score.

        Returns:
            List of formatted result dicts.
        """
        results: list[dict] = []

        for chunk_id in chunk_ids:
            chunk_data = self.vector_store.get_chunk(chunk_id)
            if chunk_data:
                results.append(
                    {
                        "id": chunk_data.get("id", chunk_id),
                        "content": chunk_data.get("document", ""),
                        "score": scores.get(chunk_id, 0.0),
                        "metadata": chunk_data.get("metadata", {}),
                    }
                )

        return results

    @staticmethod
    def _build_where_filter(
        topic: Optional[str] = None, difficulty: Optional[str] = None
    ) -> Optional[dict]:
        """Build a ChromaDB where-filter from optional parameters.

        ChromaDB requires metadata filters on scalar fields. Since topics
        is stored as a JSON string, we use $contains for partial matching.

        Args:
            topic: Optional topic to filter by.
            difficulty: Optional difficulty level to filter by.

        Returns:
            A ChromaDB where-filter dict, or None if no filters provided.
        """
        conditions: list[dict] = []

        if difficulty:
            conditions.append({"difficulty": {"$eq": difficulty}})

        if topic:
            # Topics are stored as JSON string, use $contains for matching
            conditions.append({"topics": {"$contains": topic}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
