"""NeuroForge — Relationship Extraction & Graph Validation.

Provides comprehensive relationship extraction between concepts using LLM,
graph construction with NetworkX, cycle detection/removal for prerequisite
edges, and simple visualization.

Features:
- LLM-powered relationship extraction (prerequisite, related, part_of)
- Batch processing of concept groups to respect context limits
- NetworkX directed graph construction
- Cycle detection restricted to prerequisite edges only
- Automatic cycle removal (weakest edge heuristic)
- Matplotlib-based graph visualization
"""

from __future__ import annotations

import logging
from typing import Optional

import networkx as nx
from pydantic import BaseModel, Field

from models import Concept, ConceptRelationship
from src.llm import LLMClient, LLMProvider

logger = logging.getLogger("neuroforge.extraction.relationships")

# ---------------------------------------------------------------------------
# Internal response models for LLM structured output
# ---------------------------------------------------------------------------


class RelationshipItem(BaseModel):
    """A single relationship extracted by the LLM."""

    source: str = Field(..., description="Source concept name")
    target: str = Field(..., description="Target concept name")
    relationship_type: str = Field(
        ..., description="Type: prerequisite, related, or part_of"
    )


class RelationshipListResponse(BaseModel):
    """LLM response model for relationship extraction."""

    relationships: list[RelationshipItem] = Field(
        ..., description="List of concept relationships"
    )


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

RELATIONSHIP_EXTRACTION_PROMPT = """You are a knowledge engineering expert. Given the following concepts and their definitions, identify relationships between them.

CONCEPTS:
{concept_details}

For each pair where a clear relationship exists, classify it as one of:
- "prerequisite": the source concept must be understood BEFORE the target concept
- "related": concepts are thematically connected but neither is a prerequisite of the other
- "part_of": the source concept is a component or subtopic of the target concept

Rules:
- Only include relationships where there is a clear, defensible connection.
- Do not force relationships — if two concepts are unrelated, skip them.
- A concept cannot be a prerequisite of itself.
- Be precise: prerequisite means strict ordering of understanding.

Return a JSON object with a single key "relationships" containing a list of objects.
Each object has: "source" (concept name), "target" (concept name), "relationship_type".

Example output:
{{"relationships": [{{"source": "Linear Algebra", "target": "Neural Networks", "relationship_type": "prerequisite"}}, {{"source": "Backpropagation", "target": "Neural Networks", "relationship_type": "part_of"}}]}}
"""

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_GROUP_SIZE = 15  # Max concepts per LLM call


# ---------------------------------------------------------------------------
# RelationshipExtractor
# ---------------------------------------------------------------------------


class RelationshipExtractor:
    """Extracts and validates relationships between concepts.

    Uses an LLM to identify prerequisite, related, and part_of relationships,
    builds a directed graph, detects cycles in prerequisite edges, and
    provides visualization.

    Args:
        llm_client: An LLMClient instance for LLM calls.
        group_size: Max number of concepts per LLM call (default 15).
        provider: Preferred LLM provider (optional).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        group_size: int = DEFAULT_GROUP_SIZE,
        provider: Optional[LLMProvider] = None,
    ):
        self.llm_client = llm_client
        self.group_size = group_size
        self.provider = provider

    def extract_relationships(
        self, concepts: list[Concept]
    ) -> list[ConceptRelationship]:
        """Use LLM to identify relationships between concepts.

        Processes concepts in groups to stay within context limits.
        Deduplicates extracted relationships.

        Args:
            concepts: List of concepts to find relationships between.

        Returns:
            List of ConceptRelationship instances.
        """
        if len(concepts) < 2:
            return []

        # Build name→id mapping
        concept_id_map: dict[str, str] = {
            c.name.lower().strip(): c.id for c in concepts
        }

        all_relationships: list[ConceptRelationship] = []

        for group in self._group_concepts(concepts):
            rels = self._extract_group_relationships(group, concept_id_map)
            all_relationships.extend(rels)

        # Deduplicate
        return self._deduplicate_relationships(all_relationships)

    def build_relationship_graph(
        self,
        concepts: list[Concept],
        relationships: list[ConceptRelationship],
    ) -> nx.DiGraph:
        """Build a NetworkX directed graph from concepts and relationships.

        Nodes are concept IDs with name/difficulty attributes.
        Edges have a relationship_type attribute.

        Args:
            concepts: List of concepts (graph nodes).
            relationships: List of relationships (graph edges).

        Returns:
            A NetworkX DiGraph.
        """
        graph = nx.DiGraph()

        # Add nodes
        for concept in concepts:
            graph.add_node(
                concept.id,
                name=concept.name,
                difficulty=concept.difficulty.value,
            )

        # Add edges
        for rel in relationships:
            if graph.has_node(rel.source_concept) and graph.has_node(
                rel.target_concept
            ):
                graph.add_edge(
                    rel.source_concept,
                    rel.target_concept,
                    relationship_type=rel.relationship_type,
                )

        return graph

    def validate_no_cycles(
        self, graph: nx.DiGraph
    ) -> tuple[bool, list[list[str]]]:
        """Detect circular prerequisites in the graph.

        Only checks edges with relationship_type == "prerequisite".
        Related and part_of edges are allowed to have cycles.

        Args:
            graph: A NetworkX DiGraph.

        Returns:
            Tuple of (is_valid, cycles) where is_valid is True if no
            prerequisite cycles exist, and cycles is the list of cycles found.
        """
        # Build subgraph of only prerequisite edges
        prereq_edges = [
            (u, v)
            for u, v, data in graph.edges(data=True)
            if data.get("relationship_type") == "prerequisite"
        ]
        prereq_graph = nx.DiGraph()
        prereq_graph.add_nodes_from(graph.nodes())
        prereq_graph.add_edges_from(prereq_edges)

        # Find all simple cycles
        cycles = list(nx.simple_cycles(prereq_graph))

        is_valid = len(cycles) == 0
        return is_valid, cycles

    def remove_cycles(
        self,
        relationships: list[ConceptRelationship],
        concepts: list[Concept],
    ) -> list[ConceptRelationship]:
        """Remove prerequisite edges that create circular dependencies.

        Strategy: iteratively find cycles and remove one edge per cycle
        (the last edge in the cycle) until no cycles remain.

        Only prerequisite edges are considered for removal. Related and
        part_of edges are preserved regardless.

        Args:
            relationships: List of relationships to clean.
            concepts: List of concepts for graph building.

        Returns:
            Filtered list of relationships with cycles removed.
        """
        # Separate prerequisite from other relationships
        prereq_rels = [
            r for r in relationships if r.relationship_type == "prerequisite"
        ]
        other_rels = [
            r for r in relationships if r.relationship_type != "prerequisite"
        ]

        # Build prerequisite-only graph
        prereq_graph = nx.DiGraph()
        for concept in concepts:
            prereq_graph.add_node(concept.id)
        for rel in prereq_rels:
            prereq_graph.add_edge(rel.source_concept, rel.target_concept)

        # Iteratively remove edges to break cycles
        removed_edges: set[tuple[str, str]] = set()
        while True:
            try:
                cycle = nx.find_cycle(prereq_graph)
                # Remove the last edge in the cycle
                edge_to_remove = cycle[-1][:2]  # (u, v)
                prereq_graph.remove_edge(*edge_to_remove)
                removed_edges.add(edge_to_remove)
                logger.info(
                    f"Removed prerequisite edge {edge_to_remove} to break cycle"
                )
            except nx.NetworkXNoCycle:
                break

        # Filter out removed prerequisite relationships
        filtered_prereqs = [
            r
            for r in prereq_rels
            if (r.source_concept, r.target_concept) not in removed_edges
        ]

        return filtered_prereqs + other_rels

    def visualize_graph(
        self, graph: nx.DiGraph, output_path: Optional[str] = None
    ) -> None:
        """Visualize the relationship graph using matplotlib.

        Edges are colored by relationship type:
        - prerequisite: red
        - related: blue
        - part_of: green

        Args:
            graph: A NetworkX DiGraph to visualize.
            output_path: If provided, save the figure to this path.
                        Otherwise, display it interactively.
        """
        import matplotlib.pyplot as plt

        if graph.number_of_nodes() == 0:
            logger.warning("Empty graph — nothing to visualize.")
            return

        fig, ax = plt.subplots(1, 1, figsize=(12, 8))

        # Layout
        pos = nx.spring_layout(graph, seed=42, k=2.0)

        # Draw nodes with labels
        labels = {
            node: data.get("name", node)
            for node, data in graph.nodes(data=True)
        }
        nx.draw_networkx_nodes(
            graph, pos, ax=ax, node_color="lightblue",
            node_size=800, alpha=0.9
        )
        nx.draw_networkx_labels(graph, pos, labels=labels, ax=ax, font_size=8)

        # Color edges by type
        edge_colors = {
            "prerequisite": "red",
            "related": "blue",
            "part_of": "green",
        }

        for rel_type, color in edge_colors.items():
            edges = [
                (u, v)
                for u, v, data in graph.edges(data=True)
                if data.get("relationship_type") == rel_type
            ]
            if edges:
                nx.draw_networkx_edges(
                    graph, pos, edgelist=edges, ax=ax,
                    edge_color=color, arrows=True,
                    arrowsize=15, alpha=0.7,
                    connectionstyle="arc3,rad=0.1",
                )

        # Build legend manually
        import matplotlib.patches as mpatches

        legend_patches = [
            mpatches.Patch(color=color, label=rel_type)
            for rel_type, color in edge_colors.items()
            if any(
                data.get("relationship_type") == rel_type
                for _, _, data in graph.edges(data=True)
            )
        ]
        if legend_patches:
            ax.legend(handles=legend_patches, loc="upper left")
        ax.set_title("Concept Relationship Graph")
        plt.tight_layout()

        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches="tight")
            logger.info(f"Graph saved to {output_path}")
        else:
            plt.show()

        plt.close(fig)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _group_concepts(
        self, concepts: list[Concept]
    ) -> list[list[Concept]]:
        """Split concepts into groups of self.group_size."""
        groups = []
        for i in range(0, len(concepts), self.group_size):
            groups.append(concepts[i : i + self.group_size])
        return groups

    def _extract_group_relationships(
        self,
        concepts: list[Concept],
        concept_id_map: dict[str, str],
    ) -> list[ConceptRelationship]:
        """Extract relationships for a single group of concepts via LLM."""
        # Build concept details string
        concept_details = "\n".join(
            f"- {c.name}: {c.definition}" for c in concepts
        )

        prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(
            concept_details=concept_details
        )

        try:
            result, _usage = self.llm_client.generate_json(
                prompt=prompt,
                response_model=RelationshipListResponse,
                provider=self.provider,
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as e:
            logger.warning(f"Relationship extraction failed for group: {e}")
            return []

        relationships: list[ConceptRelationship] = []
        valid_types = {"prerequisite", "related", "part_of"}

        for item in result.relationships:
            source_id = concept_id_map.get(item.source.lower().strip())
            target_id = concept_id_map.get(item.target.lower().strip())

            if (
                source_id
                and target_id
                and source_id != target_id
                and item.relationship_type in valid_types
            ):
                relationships.append(
                    ConceptRelationship(
                        source_concept=source_id,
                        target_concept=target_id,
                        relationship_type=item.relationship_type,
                    )
                )

        return relationships

    def _deduplicate_relationships(
        self, relationships: list[ConceptRelationship]
    ) -> list[ConceptRelationship]:
        """Remove duplicate relationships (same source, target, type)."""
        seen: set[tuple[str, str, str]] = set()
        unique: list[ConceptRelationship] = []

        for rel in relationships:
            key = (
                rel.source_concept,
                rel.target_concept,
                rel.relationship_type,
            )
            if key not in seen:
                seen.add(key)
                unique.append(rel)

        return unique
