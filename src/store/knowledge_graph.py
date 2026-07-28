"""Knowledge Graph for NeuroForge.

Provides a NetworkX-based directed graph for representing concept
relationships, enabling prerequisite queries, topic filtering,
and graph serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import networkx as nx
from networkx.readwrite import json_graph

from models import Concept, ConceptRelationship, Difficulty


class KnowledgeGraph:
    """Directed knowledge graph backed by NetworkX.

    Nodes represent concepts with attributes (name, definition, difficulty,
    topics, keywords). Edges represent relationships between concepts
    (prerequisite, related, part_of).

    Supports transitive prerequisite queries, topic-based subgraph extraction,
    and JSON serialization for persistence.
    """

    def __init__(self) -> None:
        """Initialize an empty directed graph."""
        self.graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_concepts(self, concepts: list[Concept]) -> None:
        """Add concept nodes with attributes to the graph.

        Args:
            concepts: List of Concept models to add as nodes.
        """
        for concept in concepts:
            self.graph.add_node(
                concept.id,
                name=concept.name,
                definition=concept.definition,
                difficulty=concept.difficulty.value,
                topics=concept.topics,
                keywords=concept.keywords,
            )

    def add_relationships(self, relationships: list[ConceptRelationship]) -> None:
        """Add relationship edges to the graph.

        Args:
            relationships: List of ConceptRelationship models to add as edges.
        """
        for rel in relationships:
            self.graph.add_edge(
                rel.source_concept,
                rel.target_concept,
                relationship_type=rel.relationship_type,
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_prerequisites(self, concept_id: str) -> list[str]:
        """Get all prerequisite concepts (transitive) for a given concept.

        Follows 'prerequisite' edges transitively using BFS to find all
        concepts that must be learned before the given concept.

        Args:
            concept_id: The concept to find prerequisites for.

        Returns:
            List of concept IDs that are (transitive) prerequisites.
        """
        if concept_id not in self.graph:
            return []

        prerequisites: list[str] = []
        visited: set[str] = set()
        queue: list[str] = [concept_id]

        while queue:
            current = queue.pop(0)
            for predecessor in self.graph.predecessors(current):
                edge_data = self.graph.edges[predecessor, current]
                if edge_data.get("relationship_type") == "prerequisite":
                    if predecessor not in visited:
                        visited.add(predecessor)
                        prerequisites.append(predecessor)
                        queue.append(predecessor)

        return prerequisites

    def get_related(self, concept_id: str) -> list[str]:
        """Get directly related concepts (neighbors connected by any edge).

        Returns all concepts that share a direct edge (in or out) with
        the given concept.

        Args:
            concept_id: The concept to find relations for.

        Returns:
            List of directly related concept IDs.
        """
        if concept_id not in self.graph:
            return []

        related: set[str] = set()
        # Successors (outgoing edges)
        for successor in self.graph.successors(concept_id):
            related.add(successor)
        # Predecessors (incoming edges)
        for predecessor in self.graph.predecessors(concept_id):
            related.add(predecessor)

        return list(related)

    def get_dependents(self, concept_id: str) -> list[str]:
        """Get concepts that require this concept as a prerequisite.

        Finds all concepts that have a 'prerequisite' edge pointing
        from this concept (i.e., this concept is their prerequisite).

        Args:
            concept_id: The concept to find dependents for.

        Returns:
            List of concept IDs that depend on this concept.
        """
        if concept_id not in self.graph:
            return []

        dependents: list[str] = []
        for successor in self.graph.successors(concept_id):
            edge_data = self.graph.edges[concept_id, successor]
            if edge_data.get("relationship_type") == "prerequisite":
                dependents.append(successor)

        return dependents

    def get_topic_subgraph(self, topic: str) -> nx.DiGraph:
        """Extract a subgraph containing only nodes belonging to a topic.

        Args:
            topic: The topic to filter by.

        Returns:
            A new DiGraph containing only nodes with the given topic
            and all edges between them.
        """
        matching_nodes = [
            node
            for node, data in self.graph.nodes(data=True)
            if topic in data.get("topics", [])
        ]
        return self.graph.subgraph(matching_nodes).copy()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Serialize the graph to a JSON file.

        Uses NetworkX's node-link format for full fidelity.

        Args:
            path: File path to write the JSON output.
        """
        data = json_graph.node_link_data(self.graph)
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: str) -> None:
        """Deserialize a graph from a JSON file.

        Replaces the current graph with the loaded one.

        Args:
            path: File path to read the JSON from.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        filepath = Path(path)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.graph = json_graph.node_link_graph(data, directed=True)

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def visualize(self, output_path: Optional[str] = None) -> None:
        """Visualize the knowledge graph using matplotlib.

        Nodes are colored by difficulty level. If output_path is provided,
        saves the figure to disk; otherwise displays it interactively.

        Args:
            output_path: Optional path to save the visualization image.
        """
        import matplotlib.pyplot as plt

        if self.graph.number_of_nodes() == 0:
            return

        # Color nodes by difficulty
        color_map = {"easy": "#4CAF50", "medium": "#FFC107", "hard": "#F44336"}
        node_colors = [
            color_map.get(self.graph.nodes[n].get("difficulty", "medium"), "#9E9E9E")
            for n in self.graph.nodes()
        ]

        # Labels are concept names (fall back to IDs)
        labels = {
            n: self.graph.nodes[n].get("name", n) for n in self.graph.nodes()
        }

        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        pos = nx.spring_layout(self.graph, seed=42)

        nx.draw_networkx(
            self.graph,
            pos=pos,
            ax=ax,
            labels=labels,
            node_color=node_colors,
            node_size=800,
            font_size=8,
            arrows=True,
            arrowsize=15,
            edge_color="#666666",
            width=1.5,
        )

        # Add edge labels for relationship type
        edge_labels = nx.get_edge_attributes(self.graph, "relationship_type")
        nx.draw_networkx_edge_labels(
            self.graph, pos=pos, edge_labels=edge_labels, font_size=6, ax=ax
        )

        ax.set_title("NeuroForge Knowledge Graph", fontsize=14)
        plt.tight_layout()

        if output_path:
            filepath = Path(output_path)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
        else:
            plt.show()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of nodes in the graph."""
        return self.graph.number_of_nodes()

    def __contains__(self, concept_id: str) -> bool:
        """Check if a concept exists in the graph."""
        return concept_id in self.graph
