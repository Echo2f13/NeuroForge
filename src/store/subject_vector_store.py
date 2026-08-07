"""Subject-Scoped Vector Store for NeuroForge.

Manages per-subject ChromaDB collections for document chunks and concepts,
providing isolated vector storage for each study subject.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from models import Chunk, ChunkMetadata, Concept

logger = logging.getLogger("neuroforge.store")


def get_collection_names(subject_id: str) -> tuple[str, str]:
    """Get ChromaDB collection names for a subject.
    
    Args:
        subject_id: Subject identifier.
        
    Returns:
        Tuple of (chunks_collection_name, concepts_collection_name).
    """
    # Replace hyphens with underscores for valid collection names
    safe_id = subject_id.replace("-", "_")
    return (
        f"subject_{safe_id}_chunks",
        f"subject_{safe_id}_concepts",
    )


class SubjectScopedVectorStore:
    """Vector store with per-subject collection isolation.
    
    Each subject gets its own pair of collections (chunks and concepts),
    providing complete isolation of learning materials between subjects.
    
    Args:
        persist_directory: Path to ChromaDB persistence directory.
        client: Optional pre-configured ChromaDB client (for testing).
    """

    def __init__(
        self,
        persist_directory: str = "./data/chroma_db",
        client: Optional[chromadb.ClientAPI] = None,
    ) -> None:
        """Initialize the subject-scoped vector store.
        
        Args:
            persist_directory: Directory for ChromaDB persistence.
            client: Optional pre-built client (e.g., EphemeralClient for tests).
        """
        self.persist_directory = persist_directory
        
        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(path=persist_directory)
        
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Cache of collections per subject: {subject_id: (chunks_coll, concepts_coll)}
        self._collections: dict[str, tuple[chromadb.Collection, chromadb.Collection]] = {}

    # -------------------------------------------------------------------------
    # Collection Management
    # -------------------------------------------------------------------------

    def get_collections(
        self, 
        subject_id: str,
    ) -> tuple[chromadb.Collection, chromadb.Collection]:
        """Get or create collections for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Tuple of (chunks_collection, concepts_collection).
        """
        if subject_id not in self._collections:
            chunks_name, concepts_name = get_collection_names(subject_id)
            
            chunks_coll = self._client.get_or_create_collection(
                name=chunks_name,
                embedding_function=self._embedding_fn,
            )
            concepts_coll = self._client.get_or_create_collection(
                name=concepts_name,
                embedding_function=self._embedding_fn,
            )
            
            self._collections[subject_id] = (chunks_coll, concepts_coll)
            logger.debug(f"Initialized collections for subject: {subject_id}")
        
        return self._collections[subject_id]

    def get_chunks_collection(self, subject_id: str) -> chromadb.Collection:
        """Get the chunks collection for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            The chunks collection.
        """
        chunks_coll, _ = self.get_collections(subject_id)
        return chunks_coll

    def get_concepts_collection(self, subject_id: str) -> chromadb.Collection:
        """Get the concepts collection for a subject.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            The concepts collection.
        """
        _, concepts_coll = self.get_collections(subject_id)
        return concepts_coll

    def delete_subject_collections(self, subject_id: str) -> None:
        """Delete all collections for a subject.
        
        Args:
            subject_id: Subject identifier.
        """
        chunks_name, concepts_name = get_collection_names(subject_id)
        
        try:
            self._client.delete_collection(name=chunks_name)
            logger.info(f"Deleted chunks collection: {chunks_name}")
        except Exception as e:
            logger.warning(f"Failed to delete chunks collection {chunks_name}: {e}")
        
        try:
            self._client.delete_collection(name=concepts_name)
            logger.info(f"Deleted concepts collection: {concepts_name}")
        except Exception as e:
            logger.warning(f"Failed to delete concepts collection {concepts_name}: {e}")
        
        # Clear from cache
        self._collections.pop(subject_id, None)

    def list_all_collections(self) -> list[str]:
        """List all collection names in the database.
        
        Returns:
            List of collection names.
        """
        collections = self._client.list_collections()
        return [c.name for c in collections]

    # -------------------------------------------------------------------------
    # Chunk Operations
    # -------------------------------------------------------------------------

    def add_chunks(self, subject_id: str, chunks: list[Chunk]) -> None:
        """Add chunks to a subject's collection.
        
        Args:
            subject_id: Subject identifier.
            chunks: List of Chunk models to store.
        """
        if not chunks:
            return
        
        collection = self.get_chunks_collection(subject_id)
        
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [self._chunk_metadata(chunk, subject_id) for chunk in chunks]
        
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug(f"Added {len(chunks)} chunks to subject {subject_id}")

    def batch_add_chunks(
        self, 
        subject_id: str, 
        chunks: list[Chunk], 
        batch_size: int = 100,
    ) -> None:
        """Add chunks in batches for large document sets.
        
        Args:
            subject_id: Subject identifier.
            chunks: List of Chunk models to store.
            batch_size: Number of chunks per batch.
        """
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            self.add_chunks(subject_id, batch)

    def get_chunk(self, subject_id: str, chunk_id: str) -> dict:
        """Retrieve a single chunk by ID.
        
        Args:
            subject_id: Subject identifier.
            chunk_id: Chunk identifier.
            
        Returns:
            Dictionary with id, document, and metadata fields.
            Empty dict if not found.
        """
        collection = self.get_chunks_collection(subject_id)
        result = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
        
        if not result["ids"]:
            return {}
        
        return {
            "id": result["ids"][0],
            "document": result["documents"][0],
            "metadata": result["metadatas"][0],
        }

    def search_chunks(
        self, 
        subject_id: str, 
        query: str, 
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """Search for chunks by semantic similarity.
        
        Args:
            subject_id: Subject identifier.
            query: Search query text.
            top_k: Number of results to return.
            where: Optional metadata filter.
            
        Returns:
            List of dicts with id, content, score, metadata.
        """
        collection = self.get_chunks_collection(subject_id)
        
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        output = []
        for i, chunk_id in enumerate(results["ids"][0]):
            output.append({
                "id": chunk_id,
                "content": results["documents"][0][i],
                "score": 1 - results["distances"][0][i],  # Convert distance to similarity
                "metadata": results["metadatas"][0][i],
            })
        
        return output

    def delete_chunks(self, subject_id: str, chunk_ids: list[str]) -> None:
        """Delete chunks by ID.
        
        Args:
            subject_id: Subject identifier.
            chunk_ids: List of chunk IDs to delete.
        """
        if not chunk_ids:
            return
        
        collection = self.get_chunks_collection(subject_id)
        collection.delete(ids=chunk_ids)
        logger.debug(f"Deleted {len(chunk_ids)} chunks from subject {subject_id}")

    def delete_document_chunks(self, subject_id: str, document_id: str) -> int:
        """Delete all chunks for a document.
        
        Args:
            subject_id: Subject identifier.
            document_id: Document identifier.
            
        Returns:
            Number of chunks deleted.
        """
        collection = self.get_chunks_collection(subject_id)
        
        # Find chunks for this document
        results = collection.get(
            where={"document_id": document_id},
            include=[],
        )
        
        if results["ids"]:
            collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0

    # -------------------------------------------------------------------------
    # Concept Operations
    # -------------------------------------------------------------------------

    def add_concepts(self, subject_id: str, concepts: list[Concept]) -> None:
        """Add concepts to a subject's collection.
        
        Args:
            subject_id: Subject identifier.
            concepts: List of Concept models to store.
        """
        if not concepts:
            return
        
        collection = self.get_concepts_collection(subject_id)
        
        ids = [concept.id for concept in concepts]
        documents = [concept.definition for concept in concepts]
        metadatas = [self._concept_metadata(concept, subject_id) for concept in concepts]
        
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug(f"Added {len(concepts)} concepts to subject {subject_id}")

    def batch_add_concepts(
        self, 
        subject_id: str, 
        concepts: list[Concept], 
        batch_size: int = 100,
    ) -> None:
        """Add concepts in batches.
        
        Args:
            subject_id: Subject identifier.
            concepts: List of Concept models to store.
            batch_size: Number of concepts per batch.
        """
        for i in range(0, len(concepts), batch_size):
            batch = concepts[i:i + batch_size]
            self.add_concepts(subject_id, batch)

    def get_concept(self, subject_id: str, concept_id: str) -> dict:
        """Retrieve a single concept by ID.
        
        Args:
            subject_id: Subject identifier.
            concept_id: Concept identifier.
            
        Returns:
            Dictionary with id, document, and metadata fields.
            Empty dict if not found.
        """
        collection = self.get_concepts_collection(subject_id)
        result = collection.get(ids=[concept_id], include=["documents", "metadatas"])
        
        if not result["ids"]:
            return {}
        
        return {
            "id": result["ids"][0],
            "document": result["documents"][0],
            "metadata": result["metadatas"][0],
        }

    def search_concepts(
        self, 
        subject_id: str, 
        query: str, 
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """Search for concepts by semantic similarity.
        
        Args:
            subject_id: Subject identifier.
            query: Search query text.
            top_k: Number of results to return.
            where: Optional metadata filter.
            
        Returns:
            List of dicts with id, definition, score, metadata.
        """
        collection = self.get_concepts_collection(subject_id)
        
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        output = []
        for i, concept_id in enumerate(results["ids"][0]):
            output.append({
                "id": concept_id,
                "definition": results["documents"][0][i],
                "score": 1 - results["distances"][0][i],
                "metadata": results["metadatas"][0][i],
            })
        
        return output

    def delete_concepts(self, subject_id: str, concept_ids: list[str]) -> None:
        """Delete concepts by ID.
        
        Args:
            subject_id: Subject identifier.
            concept_ids: List of concept IDs to delete.
        """
        if not concept_ids:
            return
        
        collection = self.get_concepts_collection(subject_id)
        collection.delete(ids=concept_ids)
        logger.debug(f"Deleted {len(concept_ids)} concepts from subject {subject_id}")

    # -------------------------------------------------------------------------
    # Cross-Subject Search
    # -------------------------------------------------------------------------

    def search_all_subjects(
        self, 
        subject_ids: list[str],
        query: str, 
        top_k: int = 5,
        search_type: str = "chunks",
    ) -> list[dict]:
        """Search across multiple subjects.
        
        Args:
            subject_ids: List of subject identifiers to search.
            query: Search query text.
            top_k: Number of results per subject.
            search_type: "chunks" or "concepts".
            
        Returns:
            List of dicts with id, content/definition, score, metadata, subject_id.
            Sorted by score descending.
        """
        all_results = []
        
        for subject_id in subject_ids:
            if search_type == "chunks":
                results = self.search_chunks(subject_id, query, top_k)
                for r in results:
                    r["subject_id"] = subject_id
                    all_results.append(r)
            else:
                results = self.search_concepts(subject_id, query, top_k)
                for r in results:
                    r["subject_id"] = subject_id
                    all_results.append(r)
        
        # Sort by score and limit
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results[:top_k]

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stats(self, subject_id: str) -> dict:
        """Get statistics for a subject's collections.
        
        Args:
            subject_id: Subject identifier.
            
        Returns:
            Dictionary with chunk_count and concept_count.
        """
        chunks_coll, concepts_coll = self.get_collections(subject_id)
        return {
            "chunk_count": chunks_coll.count(),
            "concept_count": concepts_coll.count(),
        }

    def get_global_stats(self, subject_ids: list[str]) -> dict:
        """Get aggregated statistics across multiple subjects.
        
        Args:
            subject_ids: List of subject identifiers.
            
        Returns:
            Dictionary with total chunk_count and concept_count.
        """
        total_chunks = 0
        total_concepts = 0
        
        for subject_id in subject_ids:
            stats = self.get_stats(subject_id)
            total_chunks += stats["chunk_count"]
            total_concepts += stats["concept_count"]
        
        return {
            "chunk_count": total_chunks,
            "concept_count": total_concepts,
        }

    # -------------------------------------------------------------------------
    # Metadata Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _chunk_metadata(chunk: Chunk, subject_id: str) -> dict:
        """Build metadata dict for a chunk.
        
        ChromaDB metadata values must be str, int, float, or bool.
        """
        meta = chunk.metadata
        return {
            "subject_id": subject_id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "section_heading": meta.section_heading or "",
            "page_number": meta.page_number or 0,
            "token_count": meta.token_count,
            "start_char": meta.start_char,
            "end_char": meta.end_char,
        }

    @staticmethod
    def _concept_metadata(concept: Concept, subject_id: str) -> dict:
        """Build metadata dict for a concept.
        
        Lists are JSON-serialized since ChromaDB requires scalar values.
        """
        return {
            "subject_id": subject_id,
            "name": concept.name,
            "topics": json.dumps(concept.topics),
            "difficulty": concept.difficulty.value,
            "prerequisites": json.dumps(concept.prerequisites),
            "keywords": json.dumps(concept.keywords),
            "source_chunks": json.dumps(concept.source_chunk_ids),
        }
