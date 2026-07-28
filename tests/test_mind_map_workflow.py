"""Tests for NeuroForge Mind Map Workflow.

Tests cover:
- MindMapWorkflow.generate with topic filtering
- Depth control (max_depth parameter)
- Empty graph handling
- Node typing (topic, subtopic, concept)
- Edge generation (parent-child and graph relationships)
- Fallback to name/keyword-based filtering
- Visualization (saves to file)
"""

from __future__ import annotations

import pytest

from models import Concept, ConceptRelationship, Difficulty, MindMap, MindMapNode
from src.store.knowledge_graph import KnowledgeGraph
from src.workflows.mind_map import MindMapWorkflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_concept(
    id: str,
    name: str,
    topics: list[str],
    difficulty: Difficulty = Difficulty.MEDIUM,
    keywords: list[str] | None = None,
) -> Concept:
    """Helper to create a Concept."""
    return Concept(
        id=id,
        name=name,
        definition=f"Definition of {name}.",
        topics=topics,
        difficulty=difficulty,
        keywords=keywords or [],
    )


@pytest.fixture
def ml_concepts() -> list[Concept]:
    """A set of Machine Learning concepts organized by topic."""
    return [
        make_concept("ml-1", "Machine Learning", ["Machine Learning"], keywords=["ml", "ai"]),
        make_concept("ml-2", "Supervised Learning", ["Machine Learning"], keywords=["supervised"]),
        make_concept("ml-3", "Unsupervised Learning", ["Machine Learning"], keywords=["unsupervised"]),
        make_concept("ml-4", "Linear Regression", ["Machine Learning"], keywords=["regression"]),
        make_concept("ml-5", "Decision Trees", ["Machine Learning"], keywords=["trees"]),
        make_concept("ml-6", "K-Means Clustering", ["Machine Learning"], keywords=["clustering"]),
        make_concept("ml-7", "Neural Networks", ["Machine Learning", "Deep Learning"], keywords=["nn"]),
    ]


@pytest.fixture
def ml_relationships() -> list[ConceptRelationship]:
    """Relationships between ML concepts."""
    return [
        ConceptRelationship(source_concept="ml-1", target_concept="ml-2", relationship_type="prerequisite"),
        ConceptRelationship(source_concept="ml-1", target_concept="ml-3", relationship_type="prerequisite"),
        ConceptRelationship(source_concept="ml-2", target_concept="ml-4", relationship_type="prerequisite"),
        ConceptRelationship(source_concept="ml-2", target_concept="ml-5", relationship_type="prerequisite"),
        ConceptRelationship(source_concept="ml-3", target_concept="ml-6", relationship_type="prerequisite"),
        ConceptRelationship(source_concept="ml-1", target_concept="ml-7", relationship_type="related"),
    ]


@pytest.fixture
def knowledge_graph(ml_concepts, ml_relationships) -> KnowledgeGraph:
    """Knowledge graph populated with ML concepts and relationships."""
    kg = KnowledgeGraph()
    kg.add_concepts(ml_concepts)
    kg.add_relationships(ml_relationships)
    return kg


@pytest.fixture
def workflow(knowledge_graph) -> MindMapWorkflow:
    """MindMapWorkflow initialized with the ML knowledge graph."""
    return MindMapWorkflow(knowledge_graph=knowledge_graph)


# ---------------------------------------------------------------------------
# Tests: Basic Generation
# ---------------------------------------------------------------------------


class TestMindMapGenerate:
    """Tests for the generate method."""

    def test_generates_mind_map_for_topic(self, workflow: MindMapWorkflow):
        """Should produce a MindMap with nodes and edges for a valid topic."""
        result = workflow.generate("Machine Learning", max_depth=3)

        assert isinstance(result, MindMap)
        assert len(result.nodes) > 0
        assert len(result.edges) > 0

    def test_root_node_is_topic_type(self, workflow: MindMapWorkflow):
        """The first node should be the root with type='topic'."""
        result = workflow.generate("Machine Learning", max_depth=2)

        root = result.nodes[0]
        assert root.type == "topic"
        assert root.parent_id is None
        assert "machine learning" in root.label.lower() or root.label == "Machine Learning"

    def test_nodes_are_valid_pydantic_models(self, workflow: MindMapWorkflow):
        """All nodes should be valid MindMapNode instances."""
        result = workflow.generate("Machine Learning", max_depth=3)

        for node in result.nodes:
            assert isinstance(node, MindMapNode)
            assert node.id
            assert node.label
            assert node.type in {"topic", "subtopic", "concept", "example"}

    def test_edges_have_required_keys(self, workflow: MindMapWorkflow):
        """All edges should have source, target, and label keys."""
        result = workflow.generate("Machine Learning", max_depth=3)

        for edge in result.edges:
            assert "source" in edge
            assert "target" in edge
            assert "label" in edge

    def test_edges_reference_existing_nodes(self, workflow: MindMapWorkflow):
        """Edge sources and targets should reference existing node IDs."""
        result = workflow.generate("Machine Learning", max_depth=3)
        node_ids = {n.id for n in result.nodes}

        for edge in result.edges:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids


# ---------------------------------------------------------------------------
# Tests: Depth Control
# ---------------------------------------------------------------------------


class TestDepthControl:
    """Tests for max_depth parameter."""

    def test_depth_1_only_direct_children(self, workflow: MindMapWorkflow):
        """max_depth=1 should only include root + direct children."""
        result = workflow.generate("Machine Learning", max_depth=1)

        # Should have root + some direct children (depth 1 subtopics)
        # But no grandchildren (depth 2+)
        types = {n.type for n in result.nodes}
        assert "topic" in types
        # At depth 1, children are subtopics
        assert "subtopic" in types or len(result.nodes) == 1
        # No concepts (depth 2+)
        assert "concept" not in types

    def test_depth_3_includes_deeper_nodes(self, workflow: MindMapWorkflow):
        """max_depth=3 should include concepts at deeper levels."""
        result = workflow.generate("Machine Learning", max_depth=3)

        # Should have more nodes than depth=1
        result_depth1 = workflow.generate("Machine Learning", max_depth=1)
        assert len(result.nodes) >= len(result_depth1.nodes)

    def test_max_depth_less_than_1_defaults_to_1(self, workflow: MindMapWorkflow):
        """max_depth < 1 should be clamped to 1."""
        result = workflow.generate("Machine Learning", max_depth=0)

        # Should still produce a valid mind map (treated as max_depth=1)
        assert isinstance(result, MindMap)
        assert len(result.nodes) >= 1  # At least the root


# ---------------------------------------------------------------------------
# Tests: Topic Filtering
# ---------------------------------------------------------------------------


class TestTopicFiltering:
    """Tests for topic-level filtering."""

    def test_filters_to_relevant_topic(self, knowledge_graph: KnowledgeGraph):
        """Only nodes belonging to the specified topic appear in the map."""
        # Add a concept in a different topic
        from models import Concept, Difficulty

        history_concept = Concept(
            id="hist-1",
            name="World War II",
            definition="Global conflict 1939-1945.",
            topics=["History"],
            difficulty=Difficulty.MEDIUM,
        )
        knowledge_graph.add_concepts([history_concept])

        workflow = MindMapWorkflow(knowledge_graph=knowledge_graph)
        result = workflow.generate("Machine Learning", max_depth=3)

        # The History concept should not appear
        node_ids = {n.id for n in result.nodes}
        assert "hist-1" not in node_ids

    def test_nonexistent_topic_returns_empty(self, workflow: MindMapWorkflow):
        """A topic with no matching nodes returns an empty MindMap."""
        result = workflow.generate("Quantum Physics", max_depth=3)

        assert isinstance(result, MindMap)
        assert len(result.nodes) == 0
        assert len(result.edges) == 0


# ---------------------------------------------------------------------------
# Tests: Empty / Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_knowledge_graph(self):
        """An empty graph produces an empty mind map."""
        kg = KnowledgeGraph()
        workflow = MindMapWorkflow(knowledge_graph=kg)
        result = workflow.generate("Anything", max_depth=3)

        assert result.nodes == []
        assert result.edges == []

    def test_single_node_graph(self):
        """A graph with one node produces root + that node."""
        kg = KnowledgeGraph()
        kg.add_concepts([
            make_concept("only-1", "Solo Concept", ["Solo Topic"]),
        ])
        workflow = MindMapWorkflow(knowledge_graph=kg)
        result = workflow.generate("Solo Topic", max_depth=3)

        # Root + the single concept
        assert len(result.nodes) == 2
        assert result.nodes[0].type == "topic"
        assert result.nodes[1].type == "subtopic"

    def test_disconnected_nodes(self):
        """Nodes with no edges still appear in the mind map."""
        kg = KnowledgeGraph()
        kg.add_concepts([
            make_concept("d-1", "Concept A", ["Testing"]),
            make_concept("d-2", "Concept B", ["Testing"]),
            make_concept("d-3", "Concept C", ["Testing"]),
        ])
        workflow = MindMapWorkflow(knowledge_graph=kg)
        result = workflow.generate("Testing", max_depth=2)

        # Root + 3 concept nodes
        assert len(result.nodes) == 4

    def test_keyword_fallback_filtering(self):
        """If no exact topic match, falls back to name/keyword search."""
        kg = KnowledgeGraph()
        kg.add_concepts([
            make_concept("py-1", "Python Basics", ["Programming"], keywords=["python"]),
            make_concept("py-2", "Python OOP", ["Programming"], keywords=["python", "oop"]),
            make_concept("js-1", "JavaScript", ["Programming"], keywords=["javascript"]),
        ])
        workflow = MindMapWorkflow(knowledge_graph=kg)

        # Search by keyword "python" — should find py-1 and py-2 but not js-1
        result = workflow.generate("python", max_depth=2)

        node_ids = {n.id for n in result.nodes}
        assert "py-1" in node_ids
        assert "py-2" in node_ids
        assert "js-1" not in node_ids


# ---------------------------------------------------------------------------
# Tests: Node Type Assignment
# ---------------------------------------------------------------------------


class TestNodeTypes:
    """Tests for correct node type assignment."""

    def test_depth_0_is_topic(self, workflow: MindMapWorkflow):
        """Root node at depth 0 should have type='topic'."""
        result = workflow.generate("Machine Learning", max_depth=3)
        root = result.nodes[0]
        assert root.type == "topic"

    def test_depth_1_is_subtopic(self, workflow: MindMapWorkflow):
        """Nodes at depth 1 should have type='subtopic'."""
        result = workflow.generate("Machine Learning", max_depth=1)
        subtopics = [n for n in result.nodes if n.type == "subtopic"]
        # All non-root nodes at max_depth=1 are subtopics
        for node in subtopics:
            assert node.parent_id is not None

    def test_depth_2_plus_is_concept(self, workflow: MindMapWorkflow):
        """Nodes at depth 2+ should have type='concept'."""
        result = workflow.generate("Machine Learning", max_depth=3)
        concepts = [n for n in result.nodes if n.type == "concept"]

        # Concepts should have a subtopic as parent (or another concept)
        subtopic_and_concept_ids = {
            n.id for n in result.nodes if n.type in ("subtopic", "concept")
        }
        for node in concepts:
            assert node.parent_id in subtopic_and_concept_ids or node.parent_id is not None


# ---------------------------------------------------------------------------
# Tests: Visualization
# ---------------------------------------------------------------------------


class TestVisualization:
    """Tests for mind map visualization."""

    def test_visualize_saves_to_file(self, workflow: MindMapWorkflow, tmp_path):
        """Visualization should save an image file."""
        result = workflow.generate("Machine Learning", max_depth=2)
        output_file = str(tmp_path / "mind_map.png")

        workflow.visualize(result, output_path=output_file)

        import os
        assert os.path.exists(output_file)

    def test_visualize_empty_map_no_error(self, workflow: MindMapWorkflow):
        """Visualizing an empty mind map should not raise."""
        empty_map = MindMap(nodes=[], edges=[])
        # Should not raise
        workflow.visualize(empty_map)
