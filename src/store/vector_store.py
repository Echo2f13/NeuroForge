"""Vector Store for NeuroForge.

Manages persistent ChromaDB collections for document chunks and concepts,
using sentence-transformers (all-MiniLM-L6-v2) for embeddings.
"""

from __future__ import annotations

import json
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from models import Chunk, ChunkMetadata, Concept


class VectorStore:
    """Persistent vector store backed by ChromaDB.

    Manages two collections:
    - document_chunks: stores text chunks with structural metadata
    - concepts: stores extracted knowledge concepts

    Both collections use the all-MiniLM-L6-v2 sentence-transformer model
    for embedding generation.

    Args:
        persist_directory: Path to the ChromaDB persistence directory.
        client: Optional pre-configured ChromaDB client (useful for testing).
    """

    def __init__(
        self,
        persist_directory: str = "./chroma_db/",
        client: Optional[chromadb.ClientAPI] = None,
    ) -> None:
        """Initialize VectorStore with a persistent ChromaDB client.

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

        self._chunks_collection: Optional[chromadb.Collection] = None
        self._concepts_collection: Optional[chromadb.Collection] = None

    def init_collections(self) -> None:
        """Create or retrieve the document_chunks and concepts collections."""
        self._chunks_collection = self._client.get_or_create_collection(
            name="document_chunks",
            embedding_function=self._embedding_fn,
        )
        self._concepts_collection = self._client.get_or_create_collection(
            name="concepts",
            embedding_function=self._embedding_fn,
        )

    @property
    def chunks_collection(self) -> chromadb.Collection:
        """Access the document_chunks collection (initializes if needed)."""
        if self._chunks_collection is None:
            self.init_collections()
        return self._chunks_collection  # type: ignore[return-value]

    @property
    def concepts_collection(self) -> chromadb.Collection:
        """Access the concepts collection (initializes if needed)."""
        if self._concepts_collection is None:
            self.init_collections()
        return self._concepts_collection  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Chunk operations
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Insert chunks into the document_chunks collection.

        Args:
            chunks: List of Chunk models to store.
        """
        if not chunks:
            return

        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [self._chunk_metadata(chunk) for chunk in chunks]

        self.chunks_collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def batch_add_chunks(self, chunks: list[Chunk], batch_size: int = 100) -> None:
        """Insert chunks in batches for large document sets.

        Args:
            chunks: List of Chunk models to store.
            batch_size: Number of chunks per batch.
        """
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            self.add_chunks(batch)

    def get_chunk(self, chunk_id: str) -> dict:
        """Retrieve a single chunk by ID.

        Args:
            chunk_id: The unique chunk identifier.

        Returns:
            Dictionary with id, document, and metadata fields.
        """
        result = self.chunks_collection.get(ids=[chunk_id], include=["documents", "metadatas"])
        if not result["ids"]:
            return {}
        return {
            "id": result["ids"][0],
            "document": result["documents"][0],  # type: ignore[index]
            "metadata": result["metadatas"][0],  # type: ignore[index]
        }

    # ------------------------------------------------------------------
    # Concept operations
    # ------------------------------------------------------------------

    def add_concepts(self, concepts: list[Concept]) -> None:
        """Insert concepts into the concepts collection.

        Args:
            concepts: List of Concept models to store.
        """
        if not concepts:
            return

        ids = [concept.id for concept in concepts]
        documents = [concept.definition for concept in concepts]
        metadatas = [self._concept_metadata(concept) for concept in concepts]

        self.concepts_collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def batch_add_concepts(self, concepts: list[Concept], batch_size: int = 100) -> None:
        """Insert concepts in batches for large sets.

        Args:
            concepts: List of Concept models to store.
            batch_size: Number of concepts per batch.
        """
        for i in range(0, len(concepts), batch_size):
            batch = concepts[i : i + batch_size]
            self.add_concepts(batch)

    def get_concept(self, concept_id: str) -> dict:
        """Retrieve a single concept by ID.

        Args:
            concept_id: The unique concept identifier.

        Returns:
            Dictionary with id, document, and metadata fields.
        """
        result = self.concepts_collection.get(
            ids=[concept_id], include=["documents", "metadatas"]
        )
        if not result["ids"]:
            return {}
        return {
            "id": result["ids"][0],
            "document": result["documents"][0],  # type: ignore[index]
            "metadata": result["metadatas"][0],  # type: ignore[index]
        }

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def delete_collection(self, name: str) -> None:
        """Delete a collection by name.

        Args:
            name: Name of the collection to delete.
        """
        self._client.delete_collection(name=name)
        if name == "document_chunks":
            self._chunks_collection = None
        elif name == "concepts":
            self._concepts_collection = None

    def get_stats(self) -> dict:
        """Return collection sizes.

        Returns:
            Dictionary with chunk_count and concept_count.
        """
        return {
            "chunk_count": self.chunks_collection.count(),
            "concept_count": self.concepts_collection.count(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk_metadata(chunk: Chunk) -> dict:
        """Build a flat metadata dict for a chunk (ChromaDB-compatible).

        ChromaDB metadata values must be str, int, float, or bool.
        """
        meta = chunk.metadata
        return {
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "section_heading": meta.section_heading or "",
            "page_number": meta.page_number or 0,
            "token_count": meta.token_count,
            "start_char": meta.start_char,
            "end_char": meta.end_char,
        }

    @staticmethod
    def _concept_metadata(concept: Concept) -> dict:
        """Build a flat metadata dict for a concept (ChromaDB-compatible).

        Lists are JSON-serialized since ChromaDB requires scalar metadata values.
        """
        return {
            "name": concept.name,
            "topics": json.dumps(concept.topics),
            "difficulty": concept.difficulty.value,
            "prerequisites": json.dumps(concept.prerequisites),
            "keywords": json.dumps(concept.keywords),
            "source_chunks": json.dumps(concept.source_chunk_ids),
        }
