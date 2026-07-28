"""Tests for the Retriever module."""

from __future__ import annotations

import json

import chromadb
import pytest

from models import Chunk, ChunkMetadata, Concept, ConceptRelationship, Difficulty
from src.retrieval import Retriever
from src.store import KnowledgeGraph, VectorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ephemeral_vector_store():
    """VectorStore backed by an ephemeral ChromaDB client (no disk persistence)."""
    client = chromadb.Client()
    store = VectorStore(client=client)
    store.init_collections()
    return store


@pytest.fixture
def knowledge_graph():
    """Empty KnowledgeGraph instance."""
    return KnowledgeGraph()


@pytest.fixture
def sample_chunks():
    """A set of sample chunks for testing."""
    return [
        Chunk(
            id="chunk_001",
            content="Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            document_id="doc_01",
            chunk_index=0,
            metadata=ChunkMetadata(
                section_heading="Introduction",
                page_number=1,
                token_count=18,
                start_char=0,
                end_char=95,
            ),
        ),
        Chunk(
            id="chunk_002",
            content="Neural networks are computing systems inspired by biological neural networks in the brain.",
            document_id="doc_01",
            chunk_index=1,
            metadata=ChunkMetadata(
                section_heading="Neural Networks",
                page_number=2,
                token_count=15,
                start_char=96,
                end_char=185,
            ),
        ),
        Chunk(
            id="chunk_003",
            content="Gradient descent is an optimization algorithm used to minimize the loss function in machine learning models.",
            document_id="doc_01",
            chunk_index=2,
            metadata=ChunkMetadata(
                section_heading="Optimization",
                page_number=3,
                token_count=18,
                start_char=186,
                end_char=292,
            ),
        ),
        Chunk(
            id="chunk_004",
            content="Backpropagation computes the gradient of the loss function with respect to each weight in the network.",
            document_id="doc_01",
            chunk_index=3,
            metadata=ChunkMetadata(
                section_heading="Backpropagation",
                page_number=4,
                token_count=17,
                start_char=293,
                end_char=393,
            ),
        ),
        Chunk(
            id="chunk_005",
            content="Supervised learning uses labeled data to train models that predict outcomes for unseen inputs.",
            document_id="doc_01",
            chunk_index=4,
            metadata=ChunkMetadata(
                section_heading="Learning Types",
                page_number=5,
                token_count=15,
                start_char=394,
                end_char=487,
            ),
        ),
    ]


@pytest.fixture
def sample_concepts():
    """A set of sample concepts for testing."""
    return [
        Concept(
            id="concept_ml",
            name="Machine Learning",
            definition="A subset of AI that enables systems to learn from data.",
            topics=["artificial_intelligence", "data_science"],
            difficulty=Difficulty.EASY,
            prerequisites=[],
            keywords=["ML", "learning", "AI"],
            source_chunk_ids=["chunk_001"],
        ),
        Concept(
            id="concept_nn",
            name="Neural Networks",
            definition="Computing systems inspired by biological neural networks.",
            topics=["deep_learning", "artificial_intelligence"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=["concept_ml"],
            keywords=["neurons", "layers", "deep learning"],
            source_chunk_ids=["chunk_002"],
        ),
        Concept(
            id="concept_gd",
            name="Gradient Descent",
            definition="An optimization algorithm to minimize the loss function.",
            topics=["optimization", "machine_learning"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=["concept_ml"],
            keywords=["gradient", "optimization", "loss"],
            source_chunk_ids=["chunk_003"],
        ),
        Concept(
            id="concept_bp",
            name="Backpropagation",
            definition="Computes gradient of loss with respect to network weights.",
            topics=["deep_learning", "optimization"],
            difficulty=Difficulty.HARD,
            prerequisites=["concept_nn", "concept_gd"],
            keywords=["backprop", "chain rule", "gradients"],
            source_chunk_ids=["chunk_004"],
        ),
    ]


@pytest.fixture
def sample_relationships():
    """Relationships between sample concepts."""
    return [
        ConceptRelationship(
            source_concept="concept_ml",
            target_concept="concept_nn",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="concept_ml",
            target_concept="concept_gd",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="concept_nn",
            target_concept="concept_bp",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="concept_gd",
            target_concept="concept_bp",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="concept_nn",
            target_concept="concept_gd",
            relationship_type="related",
        ),
    ]


@pytest.fixture
def populated_retriever(
    ephemeral_vector_store,
    knowledge_graph,
    sample_chunks,
    sample_concepts,
    sample_relationships,
):
    """Retriever with populated vector store and knowledge graph."""
    # Populate vector store
    ephemeral_vector_store.add_chunks(sample_chunks)
    ephemeral_vector_store.add_concepts(sample_concepts)

    # Populate knowledge graph
    knowledge_graph.add_concepts(sample_concepts)
    knowledge_graph.add_relationships(sample_relationships)

    return Retriever(
        vector_store=ephemeral_vector_store,
        knowledge_graph=knowledge_graph,
    )


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestRetrieverInit:
    """Tests for Retriever initialization."""

    def test_init_stores_references(self, ephemeral_vector_store, knowledge_graph):
        retriever = Retriever(
            vector_store=ephemeral_vector_store,
            knowledge_graph=knowledge_graph,
        )
        assert retriever.vector_store is ephemeral_vector_store
        assert retriever.knowledge_graph is knowledge_graph


# ---------------------------------------------------------------------------
# Tests: Semantic Search
# ---------------------------------------------------------------------------


class TestSemanticSearch:
    """Tests for semantic_search method."""

    def test_returns_list_of_dicts(self, populated_retriever):
        results = populated_retriever.semantic_search("machine learning")
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_result_has_required_keys(self, populated_retriever):
        results = populated_retriever.semantic_search("neural networks")
        assert len(results) > 0
        for result in results:
            assert "id" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result

    def test_respects_top_k(self, populated_retriever):
        results = populated_retriever.semantic_search("learning", top_k=2)
        assert len(results) <= 2

    def test_scores_are_non_negative(self, populated_retriever):
        results = populated_retriever.semantic_search("optimization algorithm")
        for result in results:
            assert result["score"] >= 0.0

    def test_relevant_results_ranked_higher(self, populated_retriever):
        results = populated_retriever.semantic_search("gradient descent optimization")
        assert len(results) > 0
        # The top result should be about gradient descent or optimization
        top_content = results[0]["content"].lower()
        assert "gradient" in top_content or "optimization" in top_content


# ---------------------------------------------------------------------------
# Tests: Filtered Search
# ---------------------------------------------------------------------------


class TestFilteredSearch:
    """Tests for filtered_search method."""

    def test_filter_by_difficulty(self, populated_retriever):
        results = populated_retriever.filtered_search(
            "learning concepts", difficulty="easy"
        )
        # Should find chunks linked to easy concepts
        assert isinstance(results, list)

    def test_filter_by_topic(self, populated_retriever):
        results = populated_retriever.filtered_search(
            "deep learning", topic="deep_learning"
        )
        assert isinstance(results, list)

    def test_no_filters_returns_results(self, populated_retriever):
        results = populated_retriever.filtered_search("machine learning")
        assert isinstance(results, list)
        assert len(results) > 0

    def test_result_has_required_keys(self, populated_retriever):
        results = populated_retriever.filtered_search(
            "neural networks", difficulty="medium"
        )
        for result in results:
            assert "id" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result


# ---------------------------------------------------------------------------
# Tests: Graph Retrieval
# ---------------------------------------------------------------------------


class TestGraphRetrieval:
    """Tests for graph_retrieval method."""

    def test_returns_chunks_for_existing_concept(self, populated_retriever):
        results = populated_retriever.graph_retrieval("concept_bp")
        assert isinstance(results, list)
        assert len(results) > 0

    def test_includes_prerequisite_chunks(self, populated_retriever):
        # Backpropagation requires neural networks and gradient descent
        results = populated_retriever.graph_retrieval("concept_bp")
        chunk_ids = [r["id"] for r in results]
        # Should include chunks from concept_bp itself plus prerequisites
        assert "chunk_004" in chunk_ids  # backpropagation chunk
        # Should include at least one prerequisite chunk
        prereq_chunks = {"chunk_002", "chunk_003"}  # nn, gd
        assert len(prereq_chunks & set(chunk_ids)) > 0

    def test_nonexistent_concept_returns_empty(self, populated_retriever):
        results = populated_retriever.graph_retrieval("nonexistent_concept")
        assert results == []

    def test_concept_with_no_prerequisites(self, populated_retriever):
        # Machine learning has no prerequisites
        results = populated_retriever.graph_retrieval("concept_ml")
        assert isinstance(results, list)
        assert len(results) > 0
        chunk_ids = [r["id"] for r in results]
        assert "chunk_001" in chunk_ids

    def test_result_has_required_keys(self, populated_retriever):
        results = populated_retriever.graph_retrieval("concept_nn")
        for result in results:
            assert "id" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result

    def test_scores_reflect_relationship_distance(self, populated_retriever):
        results = populated_retriever.graph_retrieval("concept_bp")
        scores_by_id = {r["id"]: r["score"] for r in results}
        # The target concept's chunk should score highest
        if "chunk_004" in scores_by_id:
            assert scores_by_id["chunk_004"] == 1.0


# ---------------------------------------------------------------------------
# Tests: Hybrid Retrieval
# ---------------------------------------------------------------------------


class TestHybridRetrieval:
    """Tests for hybrid_retrieval method."""

    def test_returns_results(self, populated_retriever):
        results = populated_retriever.hybrid_retrieval("neural networks and backpropagation")
        assert isinstance(results, list)
        assert len(results) > 0

    def test_respects_top_k(self, populated_retriever):
        results = populated_retriever.hybrid_retrieval("machine learning", top_k=3)
        assert len(results) <= 3

    def test_results_are_deduplicated(self, populated_retriever):
        results = populated_retriever.hybrid_retrieval("gradient descent")
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids))

    def test_results_sorted_by_score_descending(self, populated_retriever):
        results = populated_retriever.hybrid_retrieval("optimization algorithms")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_result_has_required_keys(self, populated_retriever):
        results = populated_retriever.hybrid_retrieval("learning from data")
        for result in results:
            assert "id" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result
