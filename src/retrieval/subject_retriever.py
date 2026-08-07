"""Subject-Scoped Retriever for NeuroForge.

Implements retrieval strategies scoped to a specific subject, using
the subject's isolated vector store collections and knowledge graph.
"""

from __future__ import annotations

import json
from typing import Optional

from src.store import KnowledgeGraph
from src.store.subject_vector_store import SubjectScopedVectorStore


class SubjectRetriever:
    """Retriever scoped to a specific subject.
    
    Provides the same retrieval strategies as the base Retriever but
    operates on a specific subject's isolated collections.
    
    Args:
        vector_store: SubjectScopedVectorStore instance.
        knowledge_graph: KnowledgeGraph for the subject.
        subject_id: Subject identifier for scoped operations.
    """

    def __init__(
        self,
        vector_store: SubjectScopedVectorStore,
        knowledge_graph: KnowledgeGraph,
        subject_id: str,
    ) -> None:
        """Initialize the subject-scoped retriever.
        
        Args:
            vector_store: Subject-scoped vector store.
            knowledge_graph: Knowledge graph for the subject.
            subject_id: Subject identifier.
        """
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph
        self.subject_id = subject_id

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Embed the query and find top-k similar chunks.
        
        Args:
            query: Natural language search query.
            top_k: Number of results to return.
            
        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        return self.vector_store.search_chunks(
            self.subject_id, 
            query, 
            top_k=top_k,
        )

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
        """Semantic search with metadata filters on concepts.
        
        Args:
            query: Natural language search query.
            top_k: Number of results.
            topic: Filter by topic.
            difficulty: Filter by difficulty level.
            
        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        # Build filter
        where_filter = self._build_where_filter(topic=topic, difficulty=difficulty)
        
        # Search concepts with filter
        results = self.vector_store.search_concepts(
            self.subject_id,
            query,
            top_k=top_k,
            where=where_filter,
        )
        
        # Extract source chunk IDs from concept metadata
        chunk_ids: list[str] = []
        chunk_scores: dict[str, float] = {}
        
        for result in results:
            meta = result.get("metadata", {})
            source_chunks_json = meta.get("source_chunks", "[]")
            try:
                source_chunks = json.loads(source_chunks_json)
            except json.JSONDecodeError:
                source_chunks = []
            
            score = result.get("score", 0.0)
            for chunk_id in source_chunks:
                if chunk_id not in chunk_scores:
                    chunk_ids.append(chunk_id)
                    chunk_scores[chunk_id] = score
        
        # Fetch the actual chunks
        return self._fetch_chunks_by_ids(chunk_ids, chunk_scores)

    # ------------------------------------------------------------------
    # Graph-based retrieval
    # ------------------------------------------------------------------

    def graph_retrieval(self, concept_id: str) -> list[dict]:
        """Retrieve concept + related concepts, then fetch their chunks.
        
        Args:
            concept_id: The concept to start from.
            
        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        if concept_id not in self.knowledge_graph:
            return []
        
        # Gather concept IDs
        concept_ids: list[str] = [concept_id]
        concept_ids.extend(self.knowledge_graph.get_prerequisites(concept_id))
        concept_ids.extend(self.knowledge_graph.get_related(concept_id))
        
        # Deduplicate
        seen: set[str] = set()
        unique_ids: list[str] = []
        for cid in concept_ids:
            if cid not in seen:
                seen.add(cid)
                unique_ids.append(cid)
        
        # Fetch chunks for each concept
        all_chunk_ids: list[str] = []
        chunk_scores: dict[str, float] = {}
        
        for cid in unique_ids:
            concept_data = self.vector_store.get_concept(self.subject_id, cid)
            if concept_data and concept_data.get("metadata"):
                source_chunks_json = concept_data["metadata"].get("source_chunks", "[]")
                try:
                    source_chunks = json.loads(source_chunks_json)
                except json.JSONDecodeError:
                    source_chunks = []
                
                # Score based on relationship
                if cid == concept_id:
                    score = 1.0
                elif cid in self.knowledge_graph.get_prerequisites(concept_id):
                    score = 0.7
                else:
                    score = 0.5
                
                for chunk_id in source_chunks:
                    if chunk_id not in chunk_scores or score > chunk_scores[chunk_id]:
                        if chunk_id not in chunk_scores:
                            all_chunk_ids.append(chunk_id)
                        chunk_scores[chunk_id] = score
        
        return self._fetch_chunks_by_ids(all_chunk_ids, chunk_scores)

    # ------------------------------------------------------------------
    # Hybrid retrieval
    # ------------------------------------------------------------------

    def hybrid_retrieval(self, query: str, top_k: int = 10) -> list[dict]:
        """Combine semantic search with graph-augmented retrieval.
        
        Args:
            query: Natural language search query.
            top_k: Maximum results to return.
            
        Returns:
            List of dicts with keys: id, content, score, metadata.
        """
        # Step 1: Semantic search on chunks
        semantic_results = self.semantic_search(query, top_k=top_k)
        
        # Step 2: Find related concepts
        concept_results = self.vector_store.search_concepts(
            self.subject_id,
            query,
            top_k=min(top_k, 5),
        )
        
        # Step 3: Expand via graph
        graph_chunks: list[dict] = []
        for result in concept_results:
            concept_id = result.get("id")
            if concept_id and concept_id in self.knowledge_graph:
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
            adjusted_score = result["score"] * 0.8
            if rid not in merged:
                result_copy = result.copy()
                result_copy["score"] = adjusted_score
                merged[rid] = result_copy
            else:
                merged[rid]["score"] = min(1.0, merged[rid]["score"] + adjusted_score * 0.2)
        
        # Step 5: Sort and limit
        sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:top_k]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_chunks_by_ids(
        self, 
        chunk_ids: list[str], 
        scores: dict[str, float],
    ) -> list[dict]:
        """Fetch chunks from vector store by ID.
        
        Args:
            chunk_ids: List of chunk IDs to fetch.
            scores: Mapping of chunk_id → score.
            
        Returns:
            List of formatted result dicts.
        """
        results: list[dict] = []
        
        for chunk_id in chunk_ids:
            chunk_data = self.vector_store.get_chunk(self.subject_id, chunk_id)
            if chunk_data:
                results.append({
                    "id": chunk_data.get("id", chunk_id),
                    "content": chunk_data.get("document", ""),
                    "score": scores.get(chunk_id, 0.0),
                    "metadata": chunk_data.get("metadata", {}),
                })
        
        return results

    @staticmethod
    def _build_where_filter(
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> Optional[dict]:
        """Build ChromaDB where-filter.
        
        Args:
            topic: Optional topic filter.
            difficulty: Optional difficulty filter.
            
        Returns:
            ChromaDB where-filter dict or None.
        """
        conditions: list[dict] = []
        
        if difficulty:
            conditions.append({"difficulty": {"$eq": difficulty}})
        if topic:
            conditions.append({"topics": {"$contains": topic}})
        
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
