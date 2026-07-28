"""Tests for the KnowledgeGraph module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import networkx as nx
import pytest

from models import Concept, ConceptRelationship, Difficulty
from src.store.knowledge_graph import KnowledgeGraph


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def sample_concepts() -> list[Concept]:
    """Create a set of sample concepts for testing."""
    return [
        Concept(
            id="algebra",
            name="Algebra",
            definition="Branch of mathematics dealing with symbols.",
            topics=["mathematics"],
            difficulty=Difficulty.EASY,
            keywords=["equations", "variables"],
        ),
        Concept(
            id="calculus",
            name="Calculus",
            definition="Study of continuous change.",
            topics=["mathematics"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=["algebra"],
            keywords=["derivatives", "integrals"],
        ),
        Concept(
            id="linear_algebra",
            name="Linear Algebra",
            definition="Study of linear equations and transformations.",
            topics=["mathematics", "computer_science"],
            difficulty=Difficulty.MEDIUM,
            prerequisites=["algebra"],
            keywords=["matrices", "vectors"],
        ),
        Concept(
            id="machine_learning",
            name="Machine Learning",
            definition="Algorithms that improve through experience.",
            topics=["computer_science", "ai"],
            difficulty=Difficulty.HARD,
            prerequisites=["calculus", "linear_algebra"],
            keywords=["neural networks", "training"],
        ),
        Concept(
            id="deep_learning",
            name="Deep Learning",
            definition="Neural networks with many layers.",
            topics=["ai"],
            difficulty=Difficulty.HARD,
            prerequisites=["machine_learning"],
            keywords=["CNN", "RNN"],
        ),
    ]


@pytest.fixture
def sample_relationships() -> list[ConceptRelationship]:
    """Create sample relationships between concepts."""
    return [
        ConceptRelationship(
            source_concept="algebra",
            target_concept="calculus",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="algebra",
            target_concept="linear_algebra",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="calculus",
            target_concept="machine_learning",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="linear_algebra",
            target_concept="machine_learning",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="machine_learning",
            target_concept="deep_learning",
            relationship_type="prerequisite",
        ),
        ConceptRelationship(
            source_concept="calculus",
            target_concept="linear_algebra",
            relationship_type="related",
        ),
    ]


@pytest.fixture
def populated_graph(
    sample_concepts: list[Concept],
    sample_relationships: list[ConceptRelationship],
) -> KnowledgeGraph:
    """Build a populated knowledge graph."""
    kg = KnowledgeGraph()
    kg.add_concepts(sample_concepts)
    kg.add_relationships(sample_relationships)
    return kg


# ------------------------------------------------------------------
# Test initialization
# ------------------------------------------------------------------


class TestInit:
    """Tests for graph initialization."""

    def test_empty_graph(self) -> None:
        kg = KnowledgeGraph()
        assert len(kg) == 0
        assert isinstance(kg.graph, nx.DiGraph)

    def test_contains_false_for_empty(self) -> None:
        kg = KnowledgeGraph()
        assert "anything" not in kg


# ------------------------------------------------------------------
# Test adding concepts
# ------------------------------------------------------------------


class TestAddConcepts:
    """Tests for add_concepts method."""

    def test_add_single_concept(self) -> None:
        kg = KnowledgeGraph()
        concept = Concept(
            id="test",
            name="Test",
            definition="A test concept.",
            topics=["testing"],
            difficulty=Difficulty.EASY,
        )
        kg.add_concepts([concept])
        assert len(kg) == 1
        assert "test" in kg

    def test_node_attributes(self, sample_concepts: list[Concept]) -> None:
        kg = KnowledgeGraph()
        kg.add_concepts(sample_concepts)
        attrs = kg.graph.nodes["algebra"]
        assert attrs["name"] == "Algebra"
        assert attrs["definition"] == "Branch of mathematics dealing with symbols."
        assert attrs["difficulty"] == "easy"
        assert "mathematics" in attrs["topics"]
        assert "equations" in attrs["keywords"]

    def test_add_empty_list(self) -> None:
        kg = KnowledgeGraph()
        kg.add_concepts([])
        assert len(kg) == 0

    def test_add_multiple_concepts(self, sample_concepts: list[Concept]) -> None:
        kg = KnowledgeGraph()
        kg.add_concepts(sample_concepts)
        assert len(kg) == 5


# ------------------------------------------------------------------
# Test adding relationships
# ------------------------------------------------------------------


class TestAddRelationships:
    """Tests for add_relationships method."""

    def test_edges_created(self, populated_graph: KnowledgeGraph) -> None:
        assert populated_graph.graph.has_edge("algebra", "calculus")
        assert populated_graph.graph.has_edge("algebra", "linear_algebra")

    def test_edge_attributes(self, populated_graph: KnowledgeGraph) -> None:
        edge = populated_graph.graph.edges["algebra", "calculus"]
        assert edge["relationship_type"] == "prerequisite"

    def test_related_edge(self, populated_graph: KnowledgeGraph) -> None:
        edge = populated_graph.graph.edges["calculus", "linear_algebra"]
        assert edge["relationship_type"] == "related"

    def test_add_empty_relationships(self) -> None:
        kg = KnowledgeGraph()
        kg.add_relationships([])
        assert kg.graph.number_of_edges() == 0


# ------------------------------------------------------------------
# Test queries
# ------------------------------------------------------------------


class TestGetPrerequisites:
    """Tests for get_prerequisites method."""

    def test_direct_prerequisite(self, populated_graph: KnowledgeGraph) -> None:
        prereqs = populated_graph.get_prerequisites("calculus")
        assert "algebra" in prereqs

    def test_transitive_prerequisites(self, populated_graph: KnowledgeGraph) -> None:
        prereqs = populated_graph.get_prerequisites("machine_learning")
        assert "calculus" in prereqs
        assert "linear_algebra" in prereqs
        assert "algebra" in prereqs

    def test_deep_transitive(self, populated_graph: KnowledgeGraph) -> None:
        prereqs = populated_graph.get_prerequisites("deep_learning")
        assert "machine_learning" in prereqs
        assert "algebra" in prereqs

    def test_no_prerequisites(self, populated_graph: KnowledgeGraph) -> None:
        prereqs = populated_graph.get_prerequisites("algebra")
        assert prereqs == []

    def test_nonexistent_concept(self, populated_graph: KnowledgeGraph) -> None:
        prereqs = populated_graph.get_prerequisites("nonexistent")
        assert prereqs == []


class TestGetRelated:
    """Tests for get_related method."""

    def test_related_includes_successors(self, populated_graph: KnowledgeGraph) -> None:
        related = populated_graph.get_related("algebra")
        assert "calculus" in related
        assert "linear_algebra" in related

    def test_related_includes_predecessors(self, populated_graph: KnowledgeGraph) -> None:
        related = populated_graph.get_related("calculus")
        assert "algebra" in related

    def test_nonexistent_concept(self, populated_graph: KnowledgeGraph) -> None:
        related = populated_graph.get_related("nonexistent")
        assert related == []


class TestGetDependents:
    """Tests for get_dependents method."""

    def test_direct_dependents(self, populated_graph: KnowledgeGraph) -> None:
        dependents = populated_graph.get_dependents("algebra")
        assert "calculus" in dependents
        assert "linear_algebra" in dependents

    def test_no_dependents(self, populated_graph: KnowledgeGraph) -> None:
        dependents = populated_graph.get_dependents("deep_learning")
        assert dependents == []

    def test_nonexistent_concept(self, populated_graph: KnowledgeGraph) -> None:
        dependents = populated_graph.get_dependents("nonexistent")
        assert dependents == []

    def test_does_not_include_related(self, populated_graph: KnowledgeGraph) -> None:
        # calculus -> linear_algebra is "related", not "prerequisite"
        dependents = populated_graph.get_dependents("calculus")
        assert "linear_algebra" not in dependents
        assert "machine_learning" in dependents


# ------------------------------------------------------------------
# Test topic subgraph
# ------------------------------------------------------------------


class TestGetTopicSubgraph:
    """Tests for get_topic_subgraph method."""

    def test_mathematics_subgraph(self, populated_graph: KnowledgeGraph) -> None:
        sub = populated_graph.get_topic_subgraph("mathematics")
        assert "algebra" in sub.nodes
        assert "calculus" in sub.nodes
        assert "linear_algebra" in sub.nodes
        assert "machine_learning" not in sub.nodes
        assert "deep_learning" not in sub.nodes

    def test_ai_subgraph(self, populated_graph: KnowledgeGraph) -> None:
        sub = populated_graph.get_topic_subgraph("ai")
        assert "machine_learning" in sub.nodes
        assert "deep_learning" in sub.nodes
        assert "algebra" not in sub.nodes

    def test_nonexistent_topic(self, populated_graph: KnowledgeGraph) -> None:
        sub = populated_graph.get_topic_subgraph("nonexistent_topic")
        assert sub.number_of_nodes() == 0

    def test_subgraph_preserves_edges(self, populated_graph: KnowledgeGraph) -> None:
        sub = populated_graph.get_topic_subgraph("mathematics")
        assert sub.has_edge("algebra", "calculus")
        assert sub.has_edge("algebra", "linear_algebra")


# ------------------------------------------------------------------
# Test serialization
# ------------------------------------------------------------------


class TestSerialization:
    """Tests for save/load methods."""

    def test_save_and_load(self, populated_graph: KnowledgeGraph) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "graph.json")
            populated_graph.save(path)

            # Verify file exists and is valid JSON
            with open(path, "r") as f:
                data = json.load(f)
            assert "nodes" in data
            # NetworkX uses "links" or "edges" depending on version
            assert "links" in data or "edges" in data

            # Load into new graph
            new_kg = KnowledgeGraph()
            new_kg.load(path)
            assert len(new_kg) == len(populated_graph)
            assert new_kg.graph.number_of_edges() == populated_graph.graph.number_of_edges()

    def test_loaded_graph_preserves_attributes(self, populated_graph: KnowledgeGraph) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "graph.json")
            populated_graph.save(path)

            new_kg = KnowledgeGraph()
            new_kg.load(path)

            attrs = new_kg.graph.nodes["algebra"]
            assert attrs["name"] == "Algebra"
            assert attrs["difficulty"] == "easy"

    def test_loaded_graph_preserves_edges(self, populated_graph: KnowledgeGraph) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "graph.json")
            populated_graph.save(path)

            new_kg = KnowledgeGraph()
            new_kg.load(path)

            assert new_kg.graph.has_edge("algebra", "calculus")
            edge = new_kg.graph.edges["algebra", "calculus"]
            assert edge["relationship_type"] == "prerequisite"

    def test_load_nonexistent_file(self) -> None:
        kg = KnowledgeGraph()
        with pytest.raises(FileNotFoundError):
            kg.load("/nonexistent/path/graph.json")

    def test_save_creates_directories(self) -> None:
        kg = KnowledgeGraph()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "nested" / "dir" / "graph.json")
            kg.save(path)
            assert Path(path).exists()


# ------------------------------------------------------------------
# Test visualization (smoke test)
# ------------------------------------------------------------------


class TestVisualize:
    """Tests for visualize method."""

    def test_visualize_saves_file(self, populated_graph: KnowledgeGraph) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "graph.png")
            populated_graph.visualize(output_path=output)
            assert Path(output).exists()

    def test_visualize_empty_graph(self) -> None:
        kg = KnowledgeGraph()
        # Should not raise on empty graph
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "empty.png")
            kg.visualize(output_path=output)
            # Empty graph produces no file
            assert not Path(output).exists()


# ------------------------------------------------------------------
# Test graph integrity
# ------------------------------------------------------------------


class TestGraphIntegrity:
    """Tests for overall graph integrity."""

    def test_node_count(self, populated_graph: KnowledgeGraph) -> None:
        assert populated_graph.graph.number_of_nodes() == 5

    def test_edge_count(self, populated_graph: KnowledgeGraph) -> None:
        # 5 prerequisite + 1 related = 6 edges
        assert populated_graph.graph.number_of_edges() == 6

    def test_is_directed(self, populated_graph: KnowledgeGraph) -> None:
        assert populated_graph.graph.is_directed()

    def test_prerequisites_form_dag(self, populated_graph: KnowledgeGraph) -> None:
        """Prerequisite edges should form a DAG (no cycles)."""
        prereq_edges = [
            (u, v)
            for u, v, d in populated_graph.graph.edges(data=True)
            if d.get("relationship_type") == "prerequisite"
        ]
        prereq_graph = nx.DiGraph(prereq_edges)
        assert nx.is_directed_acyclic_graph(prereq_graph)
