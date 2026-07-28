"""Tests for the VectorStore module.

Uses ChromaDB EphemeralClient to avoid filesystem side-effects during testing.
"""

from __future__ import annotations

import json

import chromadb
import pytest

from models import Chunk, ChunkMetadata, Concept, Difficulty
from src.store.vector_store import VectorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ephemeral_client():
    """Create a fresh ephemeral ChromaDB client for each test."""
    client = chromadb.EphemeralClient()
    yield client
    # Clean up all collections after each test
    for col in client.list_collections():
        client.delete_collection(col.name)


@pytest.fixture
def store(ephemeral_client):
    """VectorStore backed by ephemeral client."""
    vs = VectorStore(client=ephemeral_client)
    vs.init_collections()
    return vs


@pytest.fixture
def sample_chunks():
    """A list of sample Chunk objects for testing."""
    return [
        Chunk(
            id="chunk_001",
            content="Machine learning is a subset of artificial intelligence.",
            document_id="doc_abc",
            chunk_index=0,
            metadata=ChunkMetadata(
                section_heading="Introduction",
                page_number=1,
                token_count=10,
                start_char=0,
                end_char=55,
            ),
        ),
        Chunk(
            id="chunk_002",
            content="Neural networks are inspired by biological neurons.",
            document_id="doc_abc",
            chunk_index=1,
            metadata=ChunkMetadata(
                section_heading="Neural Networks",
                page_number=2,
                token_count=9,
                start_char=56,
                end_char=107,
            ),
        ),
        Chunk(
            id="chunk_003",
            content="Gradient descent optimizes the loss function iteratively.",
            document_id="doc_abc",
            chunk_index=2,
            metadata=ChunkMetadata(
                section_heading="Optimization",
                page_number=3,
                token_count=8,
                start_char=108,
                end_char=165,
            ),
        ),
    ]


@pytest.fixture
def sample_concepts():
    """A list of sample Concept objects for testing."""
    return [
        Concept(
            id="concept_ml",
            name="Machine Learning",
            definition="A field of AI that enables systems to learn from data.",
            topics=["AI", "Data Science"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=[],
            keywords=["ML", "learning", "data"],
            source_chunk_ids=["chunk_001"],
        ),
        Concept(
            id="concept_nn",
            name="Neural Networks",
            definition="Computing systems inspired by biological neural networks.",
            topics=["Deep Learning", "AI"],
            difficulty=Difficulty.HARD,
            prerequisites=["concept_ml"],
            keywords=["neurons", "layers", "deep learning"],
            source_chunk_ids=["chunk_002"],
        ),
    ]


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestVectorStoreInit:
    """Tests for VectorStore initialization."""

    def test_creates_collections(self, ephemeral_client):
        store = VectorStore(client=ephemeral_client)
        store.init_collections()
        collections = ephemeral_client.list_collections()
        names = [c.name for c in collections]
        assert "document_chunks" in names
        assert "concepts" in names

    def test_lazy_init_on_property_access(self, ephemeral_client):
        store = VectorStore(client=ephemeral_client)
        # Accessing the property should trigger init
        _ = store.chunks_collection
        collections = ephemeral_client.list_collections()
        names = [c.name for c in collections]
        assert "document_chunks" in names

    def test_default_persist_directory(self):
        store = VectorStore.__new__(VectorStore)
        # Just check the attribute isn't set yet without initializing
        assert not hasattr(store, "persist_directory")


# ---------------------------------------------------------------------------
# Tests: Chunk Operations
# ---------------------------------------------------------------------------


class TestChunkOperations:
    """Tests for adding and retrieving chunks."""

    def test_add_chunks(self, store, sample_chunks):
        store.add_chunks(sample_chunks)
        assert store.chunks_collection.count() == 3

    def test_add_empty_list(self, store):
        store.add_chunks([])
        assert store.chunks_collection.count() == 0

    def test_get_chunk_by_id(self, store, sample_chunks):
        store.add_chunks(sample_chunks)
        result = store.get_chunk("chunk_001")
        assert result["id"] == "chunk_001"
        assert "Machine learning" in result["document"]
        assert result["metadata"]["document_id"] == "doc_abc"
        assert result["metadata"]["section_heading"] == "Introduction"
        assert result["metadata"]["page_number"] == 1

    def test_get_nonexistent_chunk(self, store):
        result = store.get_chunk("nonexistent_id")
        assert result == {}

    def test_upsert_overwrites_existing(self, store, sample_chunks):
        store.add_chunks(sample_chunks)
        updated_chunk = Chunk(
            id="chunk_001",
            content="Updated content for chunk one.",
            document_id="doc_abc",
            chunk_index=0,
            metadata=ChunkMetadata(
                section_heading="Updated Section",
                page_number=1,
                token_count=6,
                start_char=0,
                end_char=30,
            ),
        )
        store.add_chunks([updated_chunk])
        result = store.get_chunk("chunk_001")
        assert "Updated content" in result["document"]
        assert result["metadata"]["section_heading"] == "Updated Section"
        # Total count shouldn't increase
        assert store.chunks_collection.count() == 3

    def test_chunk_metadata_fields(self, store, sample_chunks):
        store.add_chunks(sample_chunks)
        result = store.get_chunk("chunk_002")
        meta = result["metadata"]
        assert meta["document_id"] == "doc_abc"
        assert meta["chunk_index"] == 1
        assert meta["section_heading"] == "Neural Networks"
        assert meta["page_number"] == 2
        assert meta["token_count"] == 9
        assert meta["start_char"] == 56
        assert meta["end_char"] == 107


# ---------------------------------------------------------------------------
# Tests: Concept Operations
# ---------------------------------------------------------------------------


class TestConceptOperations:
    """Tests for adding and retrieving concepts."""

    def test_add_concepts(self, store, sample_concepts):
        store.add_concepts(sample_concepts)
        assert store.concepts_collection.count() == 2

    def test_add_empty_concepts(self, store):
        store.add_concepts([])
        assert store.concepts_collection.count() == 0

    def test_get_concept_by_id(self, store, sample_concepts):
        store.add_concepts(sample_concepts)
        result = store.get_concept("concept_ml")
        assert result["id"] == "concept_ml"
        assert "systems to learn from data" in result["document"]
        meta = result["metadata"]
        assert meta["name"] == "Machine Learning"
        assert meta["difficulty"] == "medium"
        assert json.loads(meta["topics"]) == ["AI", "Data Science"]
        assert json.loads(meta["keywords"]) == ["ML", "learning", "data"]
        assert json.loads(meta["source_chunks"]) == ["chunk_001"]

    def test_get_nonexistent_concept(self, store):
        result = store.get_concept("nonexistent_id")
        assert result == {}

    def test_concept_metadata_serialization(self, store, sample_concepts):
        store.add_concepts(sample_concepts)
        result = store.get_concept("concept_nn")
        meta = result["metadata"]
        assert json.loads(meta["prerequisites"]) == ["concept_ml"]
        assert json.loads(meta["topics"]) == ["Deep Learning", "AI"]


# ---------------------------------------------------------------------------
# Tests: Batch Operations
# ---------------------------------------------------------------------------


class TestBatchOperations:
    """Tests for batch insertion methods."""

    def test_batch_add_chunks(self, store):
        chunks = [
            Chunk(
                id=f"batch_chunk_{i:03d}",
                content=f"Content for batch chunk number {i}.",
                document_id="doc_batch",
                chunk_index=i,
                metadata=ChunkMetadata(
                    token_count=7,
                    start_char=i * 40,
                    end_char=(i + 1) * 40,
                ),
            )
            for i in range(250)
        ]
        store.batch_add_chunks(chunks, batch_size=100)
        assert store.chunks_collection.count() == 250

    def test_batch_add_concepts(self, store):
        concepts = [
            Concept(
                id=f"batch_concept_{i:03d}",
                name=f"Concept {i}",
                definition=f"Definition for concept number {i}.",
                topics=["batch_topic"],
                difficulty=Difficulty.EASY,
            )
            for i in range(150)
        ]
        store.batch_add_concepts(concepts, batch_size=50)
        assert store.concepts_collection.count() == 150

    def test_batch_with_size_larger_than_list(self, store, sample_chunks):
        store.batch_add_chunks(sample_chunks, batch_size=1000)
        assert store.chunks_collection.count() == 3


# ---------------------------------------------------------------------------
# Tests: Collection Management
# ---------------------------------------------------------------------------


class TestCollectionManagement:
    """Tests for collection management operations."""

    def test_delete_collection(self, store, sample_chunks):
        store.add_chunks(sample_chunks)
        store.delete_collection("document_chunks")
        collections = store._client.list_collections()
        names = [c.name for c in collections]
        assert "document_chunks" not in names

    def test_get_stats(self, store, sample_chunks, sample_concepts):
        store.add_chunks(sample_chunks)
        store.add_concepts(sample_concepts)
        stats = store.get_stats()
        assert stats["chunk_count"] == 3
        assert stats["concept_count"] == 2

    def test_get_stats_empty(self, store):
        stats = store.get_stats()
        assert stats["chunk_count"] == 0
        assert stats["concept_count"] == 0
