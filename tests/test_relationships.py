"""Tests for NeuroForge Relationship Extraction.

Tests cover:
- RelationshipExtractor.extract_relationships (mocked LLM)
- RelationshipExtractor.build_relationship_graph
- RelationshipExtractor.validate_no_cycles
- RelationshipExtractor.remove_cycles
- Edge cases: empty inputs, self-loops, deduplication
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from models import Concept, ConceptRelationship, Difficulty
from src.extraction.relationships import (
    RelationshipExtractor,
    RelationshipItem,
    RelationshipListResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_concept(id: str, name: str, definition: str = "A concept.") -> Concept:
    """Helper to create a Concept with minimal fields."""
    return Concept(
        id=id,
        name=name,
        definition=definition,
        topics=["General"],
        difficulty=Difficulty.MEDIUM,
    )


@pytest.fixture
def sample_concepts() -> list[Concept]:
    """A set of concepts for testing."""
    return [
        make_concept("c1", "Linear Algebra", "Study of linear equations and matrices."),
        make_concept("c2", "Calculus", "Study of continuous change."),
        make_concept("c3", "Neural Networks", "Computing systems inspired by biology."),
        make_concept("c4", "Deep Learning", "Neural networks with many hidden layers."),
        make_concept("c5", "Backpropagation", "Algorithm to compute gradients in NNs."),
    ]


@pytest.fixture
def sample_relationships() -> list[ConceptRelationship]:
    """A set of relationships for testing graph operations."""
    return [
        ConceptRelationship(
            source_concept="c1", target_concept="c3", relationship_type="prerequisite"
        ),
        ConceptRelationship(
            source_concept="c2", target_concept="c3", relationship_type="prerequisite"
        ),
        ConceptRelationship(
            source_concept="c3", target_concept="c4", relationship_type="prerequisite"
        ),
        ConceptRelationship(
            source_concept="c5", target_concept="c3", relationship_type="part_of"
        ),
        ConceptRelationship(
            source_concept="c3", target_concept="c4", relationship_type="related"
        ),
    ]


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """A mock LLMClient that returns canned relationship data."""
    client = MagicMock()
    client.generate_json.return_value = (
        RelationshipListResponse(
            relationships=[
                RelationshipItem(
                    source="Linear Algebra",
                    target="Neural Networks",
                    relationship_type="prerequisite",
                ),
                RelationshipItem(
                    source="Calculus",
                    target="Neural Networks",
                    relationship_type="prerequisite",
                ),
                RelationshipItem(
                    source="Backpropagation",
                    target="Neural Networks",
                    relationship_type="part_of",
                ),
            ]
        ),
        {"provider": "mock", "total_tokens": 100},
    )
    return client


# ---------------------------------------------------------------------------
# Tests: extract_relationships
# ---------------------------------------------------------------------------


class TestExtractRelationships:
    """Tests for the extract_relationships method."""

    def test_basic_extraction(
        self, mock_llm_client: MagicMock, sample_concepts: list[Concept]
    ):
        """LLM output is correctly mapped to ConceptRelationship list."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        rels = extractor.extract_relationships(sample_concepts)

        assert len(rels) == 3
        # Check that concept names were mapped to IDs
        assert rels[0].source_concept == "c1"
        assert rels[0].target_concept == "c3"
        assert rels[0].relationship_type == "prerequisite"

    def test_empty_concepts(self, mock_llm_client: MagicMock):
        """Should return empty list for fewer than 2 concepts."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)

        assert extractor.extract_relationships([]) == []
        assert extractor.extract_relationships([make_concept("c1", "Solo")]) == []

    def test_deduplication(self, mock_llm_client: MagicMock):
        """Duplicate relationships should be removed."""
        mock_llm_client.generate_json.return_value = (
            RelationshipListResponse(
                relationships=[
                    RelationshipItem(
                        source="Linear Algebra",
                        target="Neural Networks",
                        relationship_type="prerequisite",
                    ),
                    RelationshipItem(
                        source="Linear Algebra",
                        target="Neural Networks",
                        relationship_type="prerequisite",
                    ),
                ]
            ),
            {"provider": "mock", "total_tokens": 50},
        )

        concepts = [
            make_concept("c1", "Linear Algebra"),
            make_concept("c3", "Neural Networks"),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        rels = extractor.extract_relationships(concepts)

        assert len(rels) == 1

    def test_invalid_concept_names_ignored(self, mock_llm_client: MagicMock):
        """Relationships with unknown concept names are skipped."""
        mock_llm_client.generate_json.return_value = (
            RelationshipListResponse(
                relationships=[
                    RelationshipItem(
                        source="Unknown Concept",
                        target="Neural Networks",
                        relationship_type="prerequisite",
                    ),
                ]
            ),
            {"provider": "mock", "total_tokens": 50},
        )

        concepts = [
            make_concept("c1", "Linear Algebra"),
            make_concept("c3", "Neural Networks"),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        rels = extractor.extract_relationships(concepts)

        assert len(rels) == 0

    def test_self_loops_ignored(self, mock_llm_client: MagicMock):
        """A concept referencing itself should be filtered out."""
        mock_llm_client.generate_json.return_value = (
            RelationshipListResponse(
                relationships=[
                    RelationshipItem(
                        source="Neural Networks",
                        target="Neural Networks",
                        relationship_type="prerequisite",
                    ),
                ]
            ),
            {"provider": "mock", "total_tokens": 50},
        )

        concepts = [
            make_concept("c1", "Linear Algebra"),
            make_concept("c3", "Neural Networks"),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        rels = extractor.extract_relationships(concepts)

        assert len(rels) == 0

    def test_llm_failure_returns_empty(self, mock_llm_client: MagicMock):
        """If LLM call fails, an empty list is returned."""
        mock_llm_client.generate_json.side_effect = Exception("API Error")

        concepts = [
            make_concept("c1", "Linear Algebra"),
            make_concept("c3", "Neural Networks"),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        rels = extractor.extract_relationships(concepts)

        assert rels == []


# ---------------------------------------------------------------------------
# Tests: build_relationship_graph
# ---------------------------------------------------------------------------


class TestBuildRelationshipGraph:
    """Tests for the build_relationship_graph method."""

    def test_basic_graph(
        self,
        mock_llm_client: MagicMock,
        sample_concepts: list[Concept],
        sample_relationships: list[ConceptRelationship],
    ):
        """Graph has correct nodes and edges.

        Note: DiGraph only allows one edge per (u,v) pair, so the duplicate
        c3→c4 edge (prerequisite + related) results in 4 edges, not 5.
        The last-added type ('related') overwrites the first ('prerequisite').
        """
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(
            sample_concepts, sample_relationships
        )

        assert graph.number_of_nodes() == 5
        # DiGraph: one edge per (u,v) pair — c3→c4 appears twice, second overwrites
        assert graph.number_of_edges() == 4
        assert graph.has_edge("c1", "c3")
        assert graph.edges["c1", "c3"]["relationship_type"] == "prerequisite"

    def test_empty_inputs(self, mock_llm_client: MagicMock):
        """Empty concepts/relationships produce empty graph."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph([], [])

        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0

    def test_node_attributes(
        self,
        mock_llm_client: MagicMock,
        sample_concepts: list[Concept],
    ):
        """Nodes have name and difficulty attributes."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(sample_concepts, [])

        assert graph.nodes["c1"]["name"] == "Linear Algebra"
        assert graph.nodes["c1"]["difficulty"] == "medium"

    def test_edges_with_unknown_nodes_skipped(
        self, mock_llm_client: MagicMock, sample_concepts: list[Concept]
    ):
        """Relationships referencing non-existent concept IDs are skipped."""
        rels = [
            ConceptRelationship(
                source_concept="c1",
                target_concept="unknown_id",
                relationship_type="prerequisite",
            )
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(sample_concepts, rels)

        assert graph.number_of_edges() == 0


# ---------------------------------------------------------------------------
# Tests: validate_no_cycles
# ---------------------------------------------------------------------------


class TestValidateNoCycles:
    """Tests for the validate_no_cycles method."""

    def test_no_cycles(
        self,
        mock_llm_client: MagicMock,
        sample_concepts: list[Concept],
        sample_relationships: list[ConceptRelationship],
    ):
        """A valid graph with no prerequisite cycles passes."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(
            sample_concepts, sample_relationships
        )

        is_valid, cycles = extractor.validate_no_cycles(graph)
        assert is_valid is True
        assert cycles == []

    def test_prerequisite_cycle_detected(self, mock_llm_client: MagicMock):
        """A cycle in prerequisite edges is detected."""
        concepts = [
            make_concept("a", "A"),
            make_concept("b", "B"),
            make_concept("c", "C"),
        ]
        rels = [
            ConceptRelationship(
                source_concept="a", target_concept="b", relationship_type="prerequisite"
            ),
            ConceptRelationship(
                source_concept="b", target_concept="c", relationship_type="prerequisite"
            ),
            ConceptRelationship(
                source_concept="c", target_concept="a", relationship_type="prerequisite"
            ),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(concepts, rels)

        is_valid, cycles = extractor.validate_no_cycles(graph)
        assert is_valid is False
        assert len(cycles) >= 1

    def test_related_cycles_allowed(self, mock_llm_client: MagicMock):
        """Cycles in 'related' edges should NOT be flagged."""
        concepts = [
            make_concept("a", "A"),
            make_concept("b", "B"),
        ]
        rels = [
            ConceptRelationship(
                source_concept="a", target_concept="b", relationship_type="related"
            ),
            ConceptRelationship(
                source_concept="b", target_concept="a", relationship_type="related"
            ),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(concepts, rels)

        is_valid, cycles = extractor.validate_no_cycles(graph)
        assert is_valid is True
        assert cycles == []

    def test_part_of_cycles_allowed(self, mock_llm_client: MagicMock):
        """Cycles in 'part_of' edges should NOT be flagged."""
        concepts = [
            make_concept("a", "A"),
            make_concept("b", "B"),
        ]
        rels = [
            ConceptRelationship(
                source_concept="a", target_concept="b", relationship_type="part_of"
            ),
            ConceptRelationship(
                source_concept="b", target_concept="a", relationship_type="part_of"
            ),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(concepts, rels)

        is_valid, cycles = extractor.validate_no_cycles(graph)
        assert is_valid is True
        assert cycles == []


# ---------------------------------------------------------------------------
# Tests: remove_cycles
# ---------------------------------------------------------------------------


class TestRemoveCycles:
    """Tests for the remove_cycles method."""

    def test_removes_prerequisite_cycle(self, mock_llm_client: MagicMock):
        """Cycles in prerequisite edges are broken by removing an edge."""
        concepts = [
            make_concept("a", "A"),
            make_concept("b", "B"),
            make_concept("c", "C"),
        ]
        rels = [
            ConceptRelationship(
                source_concept="a", target_concept="b", relationship_type="prerequisite"
            ),
            ConceptRelationship(
                source_concept="b", target_concept="c", relationship_type="prerequisite"
            ),
            ConceptRelationship(
                source_concept="c", target_concept="a", relationship_type="prerequisite"
            ),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        cleaned = extractor.remove_cycles(rels, concepts)

        # At least one prerequisite edge should be removed
        prereq_count = sum(
            1 for r in cleaned if r.relationship_type == "prerequisite"
        )
        assert prereq_count < 3

        # Validate no cycles remain
        graph = extractor.build_relationship_graph(concepts, cleaned)
        is_valid, _ = extractor.validate_no_cycles(graph)
        assert is_valid is True

    def test_preserves_non_prerequisite_edges(self, mock_llm_client: MagicMock):
        """Related and part_of edges are never removed."""
        concepts = [
            make_concept("a", "A"),
            make_concept("b", "B"),
        ]
        rels = [
            ConceptRelationship(
                source_concept="a", target_concept="b", relationship_type="related"
            ),
            ConceptRelationship(
                source_concept="b", target_concept="a", relationship_type="related"
            ),
            ConceptRelationship(
                source_concept="a", target_concept="b", relationship_type="prerequisite"
            ),
            ConceptRelationship(
                source_concept="b", target_concept="a", relationship_type="prerequisite"
            ),
        ]
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        cleaned = extractor.remove_cycles(rels, concepts)

        related_count = sum(
            1 for r in cleaned if r.relationship_type == "related"
        )
        # Both related edges preserved
        assert related_count == 2

    def test_no_cycles_unchanged(
        self,
        mock_llm_client: MagicMock,
        sample_concepts: list[Concept],
        sample_relationships: list[ConceptRelationship],
    ):
        """If no cycles exist, relationships are returned unchanged."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        cleaned = extractor.remove_cycles(sample_relationships, sample_concepts)

        assert len(cleaned) == len(sample_relationships)


# ---------------------------------------------------------------------------
# Tests: visualize_graph
# ---------------------------------------------------------------------------


class TestVisualizeGraph:
    """Tests for graph visualization."""

    def test_visualize_empty_graph(self, mock_llm_client: MagicMock):
        """Empty graph should not raise."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = nx.DiGraph()
        # Should not raise
        extractor.visualize_graph(graph)

    def test_visualize_saves_file(
        self,
        mock_llm_client: MagicMock,
        sample_concepts: list[Concept],
        sample_relationships: list[ConceptRelationship],
        tmp_path,
    ):
        """Visualization saves to file when output_path is specified."""
        extractor = RelationshipExtractor(llm_client=mock_llm_client)
        graph = extractor.build_relationship_graph(
            sample_concepts, sample_relationships
        )
        output_file = str(tmp_path / "test_graph.png")
        extractor.visualize_graph(graph, output_path=output_file)

        import os

        assert os.path.exists(output_file)
