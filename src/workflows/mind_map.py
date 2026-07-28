"""Mind Map Generation Workflow for NeuroForge.

Extracts concept hierarchy from the knowledge graph and generates
a MindMap model with nodes and edges. This workflow is graph-driven
(not LLM-driven) — it traverses the existing knowledge graph structure
and formats it as a tree for visualization.

Features:
- Topic-level filtering (only nodes related to the topic)
- Depth control (limit tree depth via BFS)
- Node-edge JSON structure via Pydantic MindMap model
- Optional matplotlib visualization (simple tree layout)
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Optional

from models.output import MindMap, MindMapNode
from src.store.knowledge_graph import KnowledgeGraph

logger = logging.getLogger("neuroforge.workflows.mind_map")


class MindMapWorkflow:
    """Mind map generation workflow: extract → filter → build → visualize.

    Traverses the knowledge graph to extract a concept hierarchy for a
    given topic and builds a MindMap (Pydantic model) with typed nodes
    and labeled edges.

    Args:
        knowledge_graph: Initialized KnowledgeGraph instance with concepts loaded.
    """

    def __init__(self, knowledge_graph: KnowledgeGraph) -> None:
        self.knowledge_graph = knowledge_graph

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, topic: str, max_depth: int = 3) -> MindMap:
        """Generate a mind map for a topic from the knowledge graph.

        Pipeline stages:
        1. Filter — extract subgraph for the given topic.
        2. Build — BFS traversal to create node tree with depth control.
        3. Edges — generate labeled edges between connected nodes.

        Args:
            topic: The topic to generate a mind map for.
            max_depth: Maximum depth of the tree (default 3).
                       Must be >= 1.

        Returns:
            A validated MindMap with nodes and edges.
        """
        if max_depth < 1:
            max_depth = 1

        logger.info(f"Generating mind map for topic='{topic}', max_depth={max_depth}")

        # Stage 1: Filter — get topic subgraph
        subgraph = self._filter_subgraph(topic)

        if subgraph.number_of_nodes() == 0:
            logger.warning(f"No nodes found for topic '{topic}'. Returning empty map.")
            return MindMap(nodes=[], edges=[])

        # Stage 2: Build — create nodes via BFS with depth control
        nodes = self._build_nodes(topic, subgraph, max_depth)

        # Stage 3: Edges — generate edges between connected nodes
        edges = self._build_edges(nodes, subgraph)

        mind_map = MindMap(nodes=nodes, edges=edges)
        logger.info(
            f"Mind map generated: {len(nodes)} nodes, {len(edges)} edges"
        )
        return mind_map

    def visualize(
        self, mind_map: MindMap, output_path: Optional[str] = None
    ) -> None:
        """Visualize a mind map using matplotlib.

        Draws the mind map as a tree layout with colored nodes by type.
        If output_path is provided, saves to file; otherwise displays
        interactively.

        Args:
            mind_map: The MindMap to visualize.
            output_path: Optional path to save the image.
        """
        import matplotlib.pyplot as plt
        import networkx as nx
        from pathlib import Path

        if not mind_map.nodes:
            logger.warning("Empty mind map — nothing to visualize.")
            return

        # Build a NetworkX graph for layout
        G = nx.DiGraph()
        for node in mind_map.nodes:
            G.add_node(node.id, label=node.label, type=node.type)
        for edge in mind_map.edges:
            G.add_edge(
                edge["source"], edge["target"], label=edge.get("label", "")
            )

        # Color by node type
        color_map = {
            "topic": "#2196F3",       # Blue
            "subtopic": "#4CAF50",    # Green
            "concept": "#FFC107",     # Amber
            "example": "#9C27B0",     # Purple
        }
        node_colors = [
            color_map.get(G.nodes[n].get("type", "concept"), "#9E9E9E")
            for n in G.nodes()
        ]

        labels = {n: G.nodes[n].get("label", n) for n in G.nodes()}

        fig, ax = plt.subplots(1, 1, figsize=(14, 10))

        # Use hierarchical layout if possible, fall back to spring
        try:
            pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
        except Exception:
            pos = nx.spring_layout(G, seed=42, k=2.0)

        nx.draw_networkx(
            G,
            pos=pos,
            ax=ax,
            labels=labels,
            node_color=node_colors,
            node_size=1200,
            font_size=8,
            arrows=True,
            arrowsize=15,
            edge_color="#666666",
            width=1.5,
        )

        # Edge labels
        edge_labels = nx.get_edge_attributes(G, "label")
        nx.draw_networkx_edge_labels(
            G, pos=pos, edge_labels=edge_labels, font_size=6, ax=ax
        )

        ax.set_title(f"Mind Map", fontsize=14)
        plt.tight_layout()

        if output_path:
            filepath = Path(output_path)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
        else:
            plt.show()

    # ------------------------------------------------------------------
    # Pipeline Stages
    # ------------------------------------------------------------------

    def _filter_subgraph(self, topic: str) -> "nx.DiGraph":
        """Stage 1: Extract the subgraph for a given topic.

        Uses KnowledgeGraph.get_topic_subgraph for exact topic match.
        Falls back to a name/keyword-based search if no topic match.
        """
        import networkx as nx

        # Try exact topic match first
        subgraph = self.knowledge_graph.get_topic_subgraph(topic)

        if subgraph.number_of_nodes() > 0:
            return subgraph

        # Fallback: search by node name or keywords containing the topic
        topic_lower = topic.lower()
        matching_nodes = []
        for node, data in self.knowledge_graph.graph.nodes(data=True):
            name = data.get("name", "").lower()
            keywords = [kw.lower() for kw in data.get("keywords", [])]
            topics = [t.lower() for t in data.get("topics", [])]
            if (
                topic_lower in name
                or topic_lower in keywords
                or topic_lower in topics
                or any(topic_lower in t for t in topics)
                or any(topic_lower in kw for kw in keywords)
            ):
                matching_nodes.append(node)

        if not matching_nodes:
            return nx.DiGraph()

        return self.knowledge_graph.graph.subgraph(matching_nodes).copy()

    def _build_nodes(
        self, topic: str, subgraph: "nx.DiGraph", max_depth: int
    ) -> list[MindMapNode]:
        """Stage 2: Build MindMapNode tree via BFS with depth control.

        Creates a root node for the topic, then adds child nodes
        discovered via BFS traversal of the subgraph.

        Node typing:
        - depth 0: topic (root)
        - depth 1: subtopic
        - depth 2+: concept
        """
        nodes: list[MindMapNode] = []
        visited: set[str] = set()

        # Create root node for the topic
        root_id = f"root-{topic.lower().replace(' ', '-')}"
        root_node = MindMapNode(
            id=root_id,
            label=topic,
            type="topic",
            parent_id=None,
        )
        nodes.append(root_node)

        # Find the best root candidates in the subgraph
        # Prefer nodes with most outgoing edges (likely parent concepts)
        graph_nodes = list(subgraph.nodes())
        if not graph_nodes:
            return nodes

        # Sort by out-degree descending to find root-like nodes
        sorted_nodes = sorted(
            graph_nodes,
            key=lambda n: subgraph.out_degree(n),
            reverse=True,
        )

        # BFS from sorted starting points
        # queue entries: (node_id, parent_mind_map_id, current_depth)
        queue: deque[tuple[str, str, int]] = deque()

        for start_node in sorted_nodes:
            if start_node not in visited:
                queue.append((start_node, root_id, 1))

        while queue:
            node_id, parent_id, depth = queue.popleft()

            if node_id in visited:
                continue
            if depth > max_depth:
                continue

            visited.add(node_id)

            # Get node attributes
            node_data = subgraph.nodes.get(node_id, {})
            label = node_data.get("name", node_id)

            # Determine node type based on depth
            if depth == 1:
                node_type = "subtopic"
            else:
                node_type = "concept"

            mind_map_node = MindMapNode(
                id=node_id,
                label=label,
                type=node_type,
                parent_id=parent_id,
            )
            nodes.append(mind_map_node)

            # Enqueue successors (children in the graph)
            for successor in subgraph.successors(node_id):
                if successor not in visited:
                    queue.append((successor, node_id, depth + 1))

            # Also enqueue predecessors not yet visited
            # (to handle reverse edges in the subgraph)
            for predecessor in subgraph.predecessors(node_id):
                if predecessor not in visited:
                    queue.append((predecessor, node_id, depth + 1))

        return nodes

    def _build_edges(
        self, nodes: list[MindMapNode], subgraph: "nx.DiGraph"
    ) -> list[dict]:
        """Stage 3: Generate edges between connected nodes.

        Creates edges from:
        1. Parent-child relationships in the node tree
        2. Graph edges between nodes in the subgraph
        """
        edges: list[dict] = []
        node_ids = {n.id for n in nodes}

        # Add parent-child edges from the tree structure
        for node in nodes:
            if node.parent_id and node.parent_id in node_ids:
                edges.append(
                    {
                        "source": node.parent_id,
                        "target": node.id,
                        "label": "contains",
                    }
                )

        # Add graph relationship edges (between non-root nodes)
        seen_edges: set[tuple[str, str]] = {
            (e["source"], e["target"]) for e in edges
        }

        for u, v, data in subgraph.edges(data=True):
            if u in node_ids and v in node_ids:
                if (u, v) not in seen_edges:
                    rel_type = data.get("relationship_type", "related")
                    edges.append(
                        {
                            "source": u,
                            "target": v,
                            "label": rel_type,
                        }
                    )
                    seen_edges.add((u, v))

        return edges
