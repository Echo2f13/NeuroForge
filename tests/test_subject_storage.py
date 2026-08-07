"""Tests for Subject-Scoped Storage Operations.

Verifies that data is properly isolated between subjects in the
SubjectScopedVectorStore, including:
- Chunks go to correct subject collection
- Concepts go to correct subject collection
- Queries only return subject's data
- Cross-subject search returns all subjects' data
- Subject deletion cleans up collections
"""

from __future__ import annotations

import chromadb
import pytest

from models import Chunk, ChunkMetadata, Concept, Difficulty
from src.store.subject_vector_store import (
    SubjectScopedVectorStore,
    get_collection_names,
)


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
def vector_store(ephemeral_client):
    """SubjectScopedVectorStore backed by ephemeral client."""
    return SubjectScopedVectorStore(client=ephemeral_client)


@pytest.fixture
def math_chunks():
    """Sample chunks for mathematics subject."""
    return [
        Chunk(
            id="math-chunk-1",
            content="Calculus is the mathematical study of continuous change.",
            document_id="math-doc-1",
            chunk_index=0,
            metadata=ChunkMetadata(
                section_heading="Introduction to Calculus",
                page_number=1,
                token_count=9,
                start_char=0,
                end_char=55,
            ),
        ),
        Chunk(
            id="math-chunk-2",
            content="The derivative measures the rate of change of a function.",
            document_id="math-doc-1",
            chunk_index=1,
            metadata=ChunkMetadata(
                section_heading="Derivatives",
                page_number=2,
                token_count=11,
                start_char=56,
                end_char=113,
            ),
        ),
        Chunk(
            id="math-chunk-3",
            content="Integration is the reverse process of differentiation.",
            document_id="math-doc-1",
            chunk_index=2,
            metadata=ChunkMetadata(
                section_heading="Integration",
                page_number=3,
                token_count=8,
                start_char=114,
                end_char=168,
            ),
        ),
    ]


@pytest.fixture
def physics_chunks():
    """Sample chunks for physics subject."""
    return [
        Chunk(
            id="physics-chunk-1",
            content="Newton's laws describe the motion of objects and forces.",
            document_id="physics-doc-1",
            chunk_index=0,
            metadata=ChunkMetadata(
                section_heading="Classical Mechanics",
                page_number=1,
                token_count=10,
                start_char=0,
                end_char=55,
            ),
        ),
        Chunk(
            id="physics-chunk-2",
            content="The theory of relativity changed our understanding of space and time.",
            document_id="physics-doc-1",
            chunk_index=1,
            metadata=ChunkMetadata(
                section_heading="Relativity",
                page_number=5,
                token_count=12,
                start_char=56,
                end_char=125,
            ),
        ),
    ]


@pytest.fixture
def math_concepts():
    """Sample concepts for mathematics subject."""
    return [
        Concept(
            id="math-concept-1",
            name="Calculus",
            definition="The mathematical study of continuous change and motion.",
            topics=["Mathematics", "Analysis"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=[],
            keywords=["derivative", "integral", "limit"],
            source_chunk_ids=["math-chunk-1"],
        ),
        Concept(
            id="math-concept-2",
            name="Derivative",
            definition="A measure of how a function changes as its input changes.",
            topics=["Calculus", "Analysis"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=["math-concept-1"],
            keywords=["rate", "change", "slope"],
            source_chunk_ids=["math-chunk-2"],
        ),
    ]


@pytest.fixture
def physics_concepts():
    """Sample concepts for physics subject."""
    return [
        Concept(
            id="physics-concept-1",
            name="Newton's Laws",
            definition="Three physical laws describing motion and forces.",
            topics=["Physics", "Mechanics"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=[],
            keywords=["force", "motion", "inertia"],
            source_chunk_ids=["physics-chunk-1"],
        ),
        Concept(
            id="physics-concept-2",
            name="Relativity",
            definition="Einstein's theory of space, time, and gravitation.",
            topics=["Physics", "Modern Physics"],
            difficulty=Difficulty.HARD,
            prerequisites=["physics-concept-1"],
            keywords=["spacetime", "gravity", "Einstein"],
            source_chunk_ids=["physics-chunk-2"],
        ),
    ]


# ---------------------------------------------------------------------------
# Tests: Collection Naming
# ---------------------------------------------------------------------------


class TestCollectionNaming:
    """Tests for collection naming conventions."""

    def test_get_collection_names_simple(self):
        """Test collection names for simple subject ID."""
        chunks_name, concepts_name = get_collection_names("math")
        assert chunks_name == "subject_math_chunks"
        assert concepts_name == "subject_math_concepts"

    def test_get_collection_names_with_hyphens(self):
        """Test collection names handle hyphens correctly."""
        # ChromaDB collection names don't allow hyphens
        chunks_name, concepts_name = get_collection_names("data-science")
        assert chunks_name == "subject_data_science_chunks"
        assert concepts_name == "subject_data_science_concepts"
        assert "-" not in chunks_name
        assert "-" not in concepts_name

    def test_get_collection_names_uuid_style(self):
        """Test collection names for UUID-style subject IDs."""
        chunks_name, concepts_name = get_collection_names("abc-123-def")
        assert chunks_name == "subject_abc_123_def_chunks"
        assert concepts_name == "subject_abc_123_def_concepts"


# ---------------------------------------------------------------------------
# Tests: Chunk Isolation Between Subjects
# ---------------------------------------------------------------------------


class TestChunkIsolation:
    """Tests that chunks are properly isolated between subjects."""

    def test_chunks_stored_in_correct_collection(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test chunks are stored in subject-specific collections."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        # Check collection counts
        math_stats = vector_store.get_stats("math")
        physics_stats = vector_store.get_stats("physics")

        assert math_stats["chunk_count"] == 3
        assert physics_stats["chunk_count"] == 2

    def test_chunk_retrieval_by_subject(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test retrieving chunks returns only that subject's chunks."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        # Get math chunk should succeed
        result = vector_store.get_chunk("math", "math-chunk-1")
        assert result["id"] == "math-chunk-1"
        assert "Calculus" in result["document"]

        # Get physics chunk should succeed
        result = vector_store.get_chunk("physics", "physics-chunk-1")
        assert result["id"] == "physics-chunk-1"
        assert "Newton" in result["document"]

    def test_chunk_not_accessible_from_wrong_subject(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test chunks aren't accessible from wrong subject."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        # Math chunk should NOT be found in physics collection
        result = vector_store.get_chunk("physics", "math-chunk-1")
        assert result == {}

        # Physics chunk should NOT be found in math collection
        result = vector_store.get_chunk("math", "physics-chunk-1")
        assert result == {}

    def test_chunk_metadata_includes_subject_id(
        self, vector_store, math_chunks
    ):
        """Test chunk metadata correctly includes subject_id."""
        vector_store.add_chunks("math", math_chunks)

        result = vector_store.get_chunk("math", "math-chunk-1")
        assert result["metadata"]["subject_id"] == "math"
        assert result["metadata"]["document_id"] == "math-doc-1"

    def test_empty_chunk_list_handled(self, vector_store):
        """Test adding empty chunk list doesn't raise errors."""
        vector_store.add_chunks("empty-subject", [])
        # Should create collection but with zero items
        stats = vector_store.get_stats("empty-subject")
        assert stats["chunk_count"] == 0


# ---------------------------------------------------------------------------
# Tests: Concept Isolation Between Subjects
# ---------------------------------------------------------------------------


class TestConceptIsolation:
    """Tests that concepts are properly isolated between subjects."""

    def test_concepts_stored_in_correct_collection(
        self, vector_store, math_concepts, physics_concepts
    ):
        """Test concepts are stored in subject-specific collections."""
        vector_store.add_concepts("math", math_concepts)
        vector_store.add_concepts("physics", physics_concepts)

        math_stats = vector_store.get_stats("math")
        physics_stats = vector_store.get_stats("physics")

        assert math_stats["concept_count"] == 2
        assert physics_stats["concept_count"] == 2

    def test_concept_retrieval_by_subject(
        self, vector_store, math_concepts, physics_concepts
    ):
        """Test retrieving concepts returns only that subject's concepts."""
        vector_store.add_concepts("math", math_concepts)
        vector_store.add_concepts("physics", physics_concepts)

        # Get math concept should succeed
        result = vector_store.get_concept("math", "math-concept-1")
        assert result["id"] == "math-concept-1"
        assert "continuous change" in result["document"]

        # Get physics concept should succeed
        result = vector_store.get_concept("physics", "physics-concept-1")
        assert result["id"] == "physics-concept-1"
        assert "motion" in result["document"]

    def test_concept_not_accessible_from_wrong_subject(
        self, vector_store, math_concepts, physics_concepts
    ):
        """Test concepts aren't accessible from wrong subject."""
        vector_store.add_concepts("math", math_concepts)
        vector_store.add_concepts("physics", physics_concepts)

        # Math concept should NOT be found in physics collection
        result = vector_store.get_concept("physics", "math-concept-1")
        assert result == {}

        # Physics concept should NOT be found in math collection
        result = vector_store.get_concept("math", "physics-concept-1")
        assert result == {}

    def test_concept_metadata_includes_subject_id(
        self, vector_store, math_concepts
    ):
        """Test concept metadata correctly includes subject_id."""
        vector_store.add_concepts("math", math_concepts)

        result = vector_store.get_concept("math", "math-concept-1")
        assert result["metadata"]["subject_id"] == "math"
        assert result["metadata"]["name"] == "Calculus"


# ---------------------------------------------------------------------------
# Tests: Search Returns Only Subject's Data
# ---------------------------------------------------------------------------


class TestSubjectScopedSearch:
    """Tests that search operations respect subject boundaries."""

    def test_search_chunks_returns_only_subject_data(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test chunk search returns only results from queried subject."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        # Search for "change" - should only get math results
        results = vector_store.search_chunks("math", "rate of change")
        
        assert len(results) > 0
        for result in results:
            assert result["metadata"]["subject_id"] == "math"
            # Should not contain physics content
            assert "Newton" not in result["content"]
            assert "relativity" not in result["content"].lower()

    def test_search_concepts_returns_only_subject_data(
        self, vector_store, math_concepts, physics_concepts
    ):
        """Test concept search returns only results from queried subject."""
        vector_store.add_concepts("math", math_concepts)
        vector_store.add_concepts("physics", physics_concepts)

        # Search for "physics-related" term in math collection
        results = vector_store.search_concepts("math", "mathematical analysis")
        
        assert len(results) > 0
        for result in results:
            assert result["metadata"]["subject_id"] == "math"

    def test_search_empty_subject_returns_empty(self, vector_store, math_chunks):
        """Test searching empty subject returns no results."""
        vector_store.add_chunks("math", math_chunks)

        # Search in subject with no data
        results = vector_store.search_chunks("empty-subject", "calculus")
        assert results == []

    def test_search_with_metadata_filter(
        self, vector_store, math_chunks
    ):
        """Test search with metadata filter works correctly."""
        vector_store.add_chunks("math", math_chunks)

        # Search with document_id filter
        results = vector_store.search_chunks(
            "math",
            "mathematical study",
            where={"document_id": "math-doc-1"},
        )
        
        assert len(results) > 0
        for result in results:
            assert result["metadata"]["document_id"] == "math-doc-1"

    def test_search_respects_top_k(self, vector_store, math_chunks):
        """Test search respects top_k limit."""
        vector_store.add_chunks("math", math_chunks)

        results = vector_store.search_chunks("math", "mathematics", top_k=2)
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Tests: Cross-Subject Search
# ---------------------------------------------------------------------------


class TestCrossSubjectSearch:
    """Tests for searching across multiple subjects."""

    def test_search_all_subjects_chunks(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test cross-subject chunk search returns results from all subjects."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        results = vector_store.search_all_subjects(
            subject_ids=["math", "physics"],
            query="fundamental concepts",
            top_k=10,
            search_type="chunks",
        )

        # Should have results from both subjects
        subject_ids_in_results = {r["subject_id"] for r in results}
        assert "math" in subject_ids_in_results or "physics" in subject_ids_in_results

    def test_search_all_subjects_concepts(
        self, vector_store, math_concepts, physics_concepts
    ):
        """Test cross-subject concept search returns results from all subjects."""
        vector_store.add_concepts("math", math_concepts)
        vector_store.add_concepts("physics", physics_concepts)

        results = vector_store.search_all_subjects(
            subject_ids=["math", "physics"],
            query="scientific theory",
            top_k=10,
            search_type="concepts",
        )

        # Results should include subject_id field
        for result in results:
            assert "subject_id" in result
            assert result["subject_id"] in ["math", "physics"]

    def test_search_all_subjects_sorted_by_score(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test cross-subject search results are sorted by score."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        results = vector_store.search_all_subjects(
            subject_ids=["math", "physics"],
            query="study of motion and change",
            top_k=10,
            search_type="chunks",
        )

        # Check scores are in descending order
        scores = [r.get("score", 0) for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_all_subjects_respects_top_k(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test cross-subject search respects top_k limit."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        results = vector_store.search_all_subjects(
            subject_ids=["math", "physics"],
            query="scientific study",
            top_k=3,
            search_type="chunks",
        )

        assert len(results) <= 3

    def test_search_all_subjects_with_empty_subject(
        self, vector_store, math_chunks
    ):
        """Test cross-subject search handles empty subjects gracefully."""
        vector_store.add_chunks("math", math_chunks)
        # Don't add anything to physics

        results = vector_store.search_all_subjects(
            subject_ids=["math", "physics"],
            query="mathematics",
            top_k=5,
            search_type="chunks",
        )

        # Should still return math results
        assert len(results) > 0
        for result in results:
            assert result["subject_id"] == "math"


# ---------------------------------------------------------------------------
# Tests: Subject Deletion Cleanup
# ---------------------------------------------------------------------------


class TestSubjectDeletionCleanup:
    """Tests that subject deletion properly cleans up collections."""

    def test_delete_subject_removes_collections(
        self, vector_store, math_chunks, math_concepts
    ):
        """Test deleting a subject removes its collections."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_concepts("math", math_concepts)

        # Verify collections exist
        collections_before = vector_store.list_all_collections()
        assert "subject_math_chunks" in collections_before
        assert "subject_math_concepts" in collections_before

        # Delete subject collections
        vector_store.delete_subject_collections("math")

        # Verify collections are removed
        collections_after = vector_store.list_all_collections()
        assert "subject_math_chunks" not in collections_after
        assert "subject_math_concepts" not in collections_after

    def test_delete_subject_preserves_other_subjects(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test deleting one subject doesn't affect others."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        # Delete math subject
        vector_store.delete_subject_collections("math")

        # Physics should still be intact
        physics_stats = vector_store.get_stats("physics")
        assert physics_stats["chunk_count"] == 2

        # Physics chunk should still be retrievable
        result = vector_store.get_chunk("physics", "physics-chunk-1")
        assert result["id"] == "physics-chunk-1"

    def test_delete_nonexistent_subject_no_error(self, vector_store):
        """Test deleting non-existent subject doesn't raise errors."""
        # Should not raise any exceptions
        vector_store.delete_subject_collections("nonexistent-subject")

    def test_delete_subject_clears_cache(
        self, vector_store, math_chunks
    ):
        """Test deleting subject clears internal collection cache."""
        vector_store.add_chunks("math", math_chunks)

        # Access collections to populate cache
        _ = vector_store.get_collections("math")
        assert "math" in vector_store._collections

        # Delete subject
        vector_store.delete_subject_collections("math")

        # Cache should be cleared
        assert "math" not in vector_store._collections


# ---------------------------------------------------------------------------
# Tests: Collection Management
# ---------------------------------------------------------------------------


class TestCollectionManagement:
    """Tests for collection management operations."""

    def test_get_collections_creates_if_not_exist(self, vector_store):
        """Test get_collections creates collections if they don't exist."""
        chunks_coll, concepts_coll = vector_store.get_collections("new-subject")

        assert chunks_coll is not None
        assert concepts_coll is not None
        
        collections = vector_store.list_all_collections()
        assert "subject_new_subject_chunks" in collections
        assert "subject_new_subject_concepts" in collections

    def test_get_collections_caches_results(self, vector_store):
        """Test collections are cached after first access."""
        # First access
        coll1_chunks, coll1_concepts = vector_store.get_collections("test-subject")
        
        # Second access should return same objects
        coll2_chunks, coll2_concepts = vector_store.get_collections("test-subject")
        
        assert coll1_chunks is coll2_chunks
        assert coll1_concepts is coll2_concepts

    def test_list_all_collections(
        self, vector_store, math_chunks, physics_chunks
    ):
        """Test listing all collections in the database."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)

        collections = vector_store.list_all_collections()
        
        assert "subject_math_chunks" in collections
        assert "subject_math_concepts" in collections
        assert "subject_physics_chunks" in collections
        assert "subject_physics_concepts" in collections


# ---------------------------------------------------------------------------
# Tests: Statistics
# ---------------------------------------------------------------------------


class TestStatistics:
    """Tests for statistics operations."""

    def test_get_stats_single_subject(
        self, vector_store, math_chunks, math_concepts
    ):
        """Test getting stats for a single subject."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_concepts("math", math_concepts)

        stats = vector_store.get_stats("math")
        
        assert stats["chunk_count"] == 3
        assert stats["concept_count"] == 2

    def test_get_stats_empty_subject(self, vector_store):
        """Test getting stats for empty subject."""
        # Access collections to create them
        _ = vector_store.get_collections("empty-subject")
        
        stats = vector_store.get_stats("empty-subject")
        
        assert stats["chunk_count"] == 0
        assert stats["concept_count"] == 0

    def test_get_global_stats(
        self, vector_store, math_chunks, math_concepts, physics_chunks, physics_concepts
    ):
        """Test getting global stats across multiple subjects."""
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_concepts("math", math_concepts)
        vector_store.add_chunks("physics", physics_chunks)
        vector_store.add_concepts("physics", physics_concepts)

        stats = vector_store.get_global_stats(["math", "physics"])
        
        assert stats["chunk_count"] == 5  # 3 + 2
        assert stats["concept_count"] == 4  # 2 + 2


# ---------------------------------------------------------------------------
# Tests: Batch Operations
# ---------------------------------------------------------------------------


class TestBatchOperations:
    """Tests for batch insertion methods."""

    def test_batch_add_chunks(self, vector_store):
        """Test batch adding chunks works correctly."""
        chunks = [
            Chunk(
                id=f"batch-chunk-{i}",
                content=f"Batch chunk content number {i} for testing.",
                document_id="batch-doc",
                chunk_index=i,
                metadata=ChunkMetadata(
                    token_count=8,
                    start_char=i * 50,
                    end_char=(i + 1) * 50,
                ),
            )
            for i in range(250)
        ]

        vector_store.batch_add_chunks("batch-subject", chunks, batch_size=100)
        
        stats = vector_store.get_stats("batch-subject")
        assert stats["chunk_count"] == 250

    def test_batch_add_concepts(self, vector_store):
        """Test batch adding concepts works correctly."""
        concepts = [
            Concept(
                id=f"batch-concept-{i}",
                name=f"Concept {i}",
                definition=f"Definition for batch concept number {i}.",
                topics=["Batch Testing"],
                difficulty=Difficulty.EASY,
            )
            for i in range(150)
        ]

        vector_store.batch_add_concepts("batch-subject", concepts, batch_size=50)
        
        stats = vector_store.get_stats("batch-subject")
        assert stats["concept_count"] == 150


# ---------------------------------------------------------------------------
# Tests: Document-Level Operations
# ---------------------------------------------------------------------------


class TestDocumentOperations:
    """Tests for document-level operations."""

    def test_delete_document_chunks(self, vector_store, math_chunks):
        """Test deleting all chunks for a specific document."""
        vector_store.add_chunks("math", math_chunks)
        
        # All chunks have same document_id
        count = vector_store.delete_document_chunks("math", "math-doc-1")
        
        assert count == 3
        
        # Verify chunks are deleted
        stats = vector_store.get_stats("math")
        assert stats["chunk_count"] == 0

    def test_delete_document_chunks_preserves_other_docs(self, vector_store):
        """Test deleting document chunks doesn't affect other documents."""
        chunks_doc1 = [
            Chunk(
                id="doc1-chunk-1",
                content="Content from document 1.",
                document_id="doc-1",
                chunk_index=0,
                metadata=ChunkMetadata(token_count=5, start_char=0, end_char=25),
            ),
        ]
        chunks_doc2 = [
            Chunk(
                id="doc2-chunk-1",
                content="Content from document 2.",
                document_id="doc-2",
                chunk_index=0,
                metadata=ChunkMetadata(token_count=5, start_char=0, end_char=25),
            ),
        ]

        vector_store.add_chunks("multi-doc", chunks_doc1)
        vector_store.add_chunks("multi-doc", chunks_doc2)
        
        # Delete only doc-1 chunks
        vector_store.delete_document_chunks("multi-doc", "doc-1")
        
        # doc-2 chunk should still exist
        result = vector_store.get_chunk("multi-doc", "doc2-chunk-1")
        assert result["id"] == "doc2-chunk-1"

    def test_delete_nonexistent_document_returns_zero(self, vector_store, math_chunks):
        """Test deleting non-existent document returns zero count."""
        vector_store.add_chunks("math", math_chunks)
        
        count = vector_store.delete_document_chunks("math", "nonexistent-doc")
        assert count == 0


# ---------------------------------------------------------------------------
# Tests: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_special_characters_in_subject_id(self, vector_store):
        """Test subject IDs with special characters are handled."""
        # Subject with hyphens (common in UUIDs)
        chunks = [
            Chunk(
                id="special-chunk-1",
                content="Testing special characters.",
                document_id="special-doc",
                chunk_index=0,
                metadata=ChunkMetadata(token_count=3, start_char=0, end_char=27),
            ),
        ]
        
        vector_store.add_chunks("subject-with-hyphens", chunks)
        
        result = vector_store.get_chunk("subject-with-hyphens", "special-chunk-1")
        assert result["id"] == "special-chunk-1"

    def test_upsert_updates_existing_chunk(self, vector_store, math_chunks):
        """Test upserting chunk with same ID updates content."""
        vector_store.add_chunks("math", math_chunks)
        
        updated_chunk = Chunk(
            id="math-chunk-1",
            content="Updated calculus content.",
            document_id="math-doc-1",
            chunk_index=0,
            metadata=ChunkMetadata(token_count=3, start_char=0, end_char=25),
        )
        
        vector_store.add_chunks("math", [updated_chunk])
        
        result = vector_store.get_chunk("math", "math-chunk-1")
        assert "Updated" in result["document"]
        
        # Count should remain the same
        stats = vector_store.get_stats("math")
        assert stats["chunk_count"] == 3

    def test_concurrent_subject_access(self, vector_store, math_chunks, physics_chunks):
        """Test accessing multiple subjects doesn't cause interference."""
        # Add data to multiple subjects
        vector_store.add_chunks("math", math_chunks)
        vector_store.add_chunks("physics", physics_chunks)
        
        # Access collections for both subjects
        math_coll = vector_store.get_chunks_collection("math")
        physics_coll = vector_store.get_chunks_collection("physics")
        
        # Collections should be different objects
        assert math_coll.name != physics_coll.name
        
        # Data should be isolated
        assert math_coll.count() == 3
        assert physics_coll.count() == 2
