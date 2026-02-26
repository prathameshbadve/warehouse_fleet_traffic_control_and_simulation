"""
Warehouse Graph object containing the nodes of all storage location,
picking stations, charging stations and parking.
"""

from __future__ import annotations
from enum import Enum

import numpy as np
import networkx as nx


class NodeType(Enum):
    """Types of locations in the warehouse."""

    INTERSECTION = "intersection"  # Highway junction
    STORAGE = "storage"  # Pod storage location (side branch off aisle)
    PICK_STATION = "pick_station"  # Human picker processes items
    CHARGING = "charging"  # AGV charging dock
    PARKING = "parking"  # Safe waiting / buffer location


class EdgeType(Enum):
    """Types of traversable paths."""

    AISLE = "aisle"  # Narrow storage aisle (typically one-way, capacity 1)
    HIGHWAY = "highway"  # Wide cross-aisle / main corridor (two-way, capacity 2+)
    STATION_ACCESS = "station_access"  # Short edge connecting highway to station
    UTURN = "uturn"  # Cross-link between paired aisles


class WarehouseGraph:
    """
    Directed graph representing a warehouse floor.

    Wraps a NetworkX DiGraph with typed nodes and edges, providing
    domain-specific queries (e.g., "give me all storage nodes near
    a pick station") while keeping the raw graph accessible for
    pathfinding algorithms.

    Attributes:
        graph: The underlying NetworkX DiGraph.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    ###################
    # NODE MANAGEMENT #
    ###################

    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        x: float,
        y: float,
        **attrs,
    ):
        """
        Add a node with spatial coordinates and type.

        Args:
            node_id: Unique identifier (e.g., "S_3_12" for storage aisle 3, bay 12).
            node_type: What kind of location this is.
            x: X coordinate in meters (east-west).
            y: Y coordinate in meters (north-south).
            **attrs: Additional attributes (e.g., pod_id for storage nodes).
        """

        if node_id in self.graph:
            raise ValueError(f"Node ID {node_id} already exists in the graph.")

        self.graph.add_node(
            node_id,
            node_type=node_type,
            x=x,
            y=y,
            **attrs,
        )

    def get_node(self, node_id: str) -> dict:
        """Get all attributes of a node."""

        return self.graph.nodes[node_id]

    def nodes_by_type(self, node_type: NodeType) -> list[str]:
        """Return all node IDs of a given type."""

        return [
            n for n, d in self.graph.nodes(data=True) if d.get("node_type") == node_type
        ]

    ###################
    # EDGE MANAGEMENT #
    ###################

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        edge_type: EdgeType,
        capacity: int = 1,
        **attrs,
    ):
        """
        Compute the length and add a directed edge between two nodes.

        Args:
            from_node: Source node ID.
            to_node: Target node ID.
            edge_type: Type of path.
            distance: Physical distance in meters.
            capacity: Max concurrent AGVs on this edge.
            **attrs: Additional attributes.
        """

        edge_length = self._compute_edge_length(from_node, to_node)

        self.graph.add_edge(
            from_node,
            to_node,
            edge_type=edge_type,
            capacity=capacity,
            length=edge_length,
            **attrs,
        )

    def add_bidirectional_edges(
        self,
        node_a: str,
        node_b: str,
        edge_type: EdgeType,
        capacity: int = 1,
        **attrs,
    ) -> None:
        """Add edges in both directions (for highways and wide corridors)."""

        self.add_edge(node_a, node_b, edge_type, capacity, **attrs)
        self.add_edge(node_b, node_a, edge_type, capacity, **attrs)

    ####################
    # HELPER FUNCTIONS #
    ####################

    def _compute_edge_length(
        self,
        from_node: str,
        to_node: str,
    ):
        """
        Helper function to compute distance between nodes.
        Used to set the length of edge while adding edge to graph.
        """

        node_1 = self.get_node(from_node)
        node_2 = self.get_node(to_node)

        x1 = node_1["x"]
        y1 = node_1["y"]

        x2 = node_2["x"]
        y2 = node_2["y"]

        return np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    ###################
    # QUERY FUNCTIONS #
    ###################

    @property
    def n_nodes(self) -> int:
        """Returns the number of nodes in the graph"""

        return self.graph.number_of_nodes()

    @property
    def n_edges(self) -> int:
        """Returns the number of edges in the graph"""

        return self.graph.number_of_edges()

    def neighbors(self, node_id: str) -> list[str]:
        """Return successor nodes (nodes reachable from this node)."""

        return list(self.graph.successors(node_id))

    def edge_length(self, from_node: str, to_node: str) -> float:
        """Get length of a specific edge. Raises KeyError if edge doesn't exist."""

        return self.graph.edges[from_node, to_node]["length"]

    def edge_capacity(self, from_node: str, to_node: str) -> int:
        """Get capacity of a specific edge."""

        return self.graph.edges[from_node, to_node]["capacity"]

    def shortest_path_distance(self, from_node: str, to_node: str) -> float:
        """
        Compute shortest path distance ignoring capacity/conflicts.

        Uses cached all-pairs shortest paths if available, otherwise
        computes single-source Dijkstra.

        Returns:
            Distance in meters. Raises nx.NetworkXNoPath if unreachable.
        """

        return nx.shortest_path_length(self.graph, from_node, to_node, weight="length")

    def shortest_path(self, from_node: str, to_node: str) -> list[str]:
        """Compute shortest path (list of node IDs) ignoring conflicts."""

        return nx.shortest_path(self.graph, from_node, to_node, weight="length")

    def nearest_node_of_type(
        self, from_node: str, target_type: NodeType
    ) -> tuple[str, float]:
        """
        Find the nearest node of a given type from a source node.

        Returns:
            Tuple of (node_id, distance).

        Raises:
            ValueError: If no nodes of the target type exist.
        """

        candidates = self.nodes_by_type(target_type)
        if not candidates:
            raise ValueError(f"No nodes of type {target_type} in the graph")

        best_node = None
        best_dist = float("inf")
        for candidate in candidates:
            try:
                dist = self.shortest_path_distance(from_node, candidate)
                if dist < best_dist:
                    best_dist = dist
                    best_node = candidate
            except nx.NetworkXNoPath:
                continue

        if best_node is None:
            raise ValueError(
                f"No reachable nodes of type {target_type} from {from_node}"
            )
        return best_node, best_dist

    def validate(self) -> list[str]:
        """
        Run basic sanity checks on the graph.

        Returns:
            List of warning/error messages (empty = all good).
        """

        issues = []

        # Check connectivity
        if not nx.is_weakly_connected(self.graph):
            components = list(nx.weakly_connected_components(self.graph))
            issues.append(
                f"Graph is not connected: {len(components)} components "
                f"(sizes: {[len(c) for c in components]})"
            )

        # Check required node types exist
        for required in [NodeType.STORAGE, NodeType.PICK_STATION, NodeType.CHARGING]:
            if not self.nodes_by_type(required):
                issues.append(f"No nodes of type {required.name}")

        # Check pick stations are reachable from at least one storage node
        pick_stations = self.nodes_by_type(NodeType.PICK_STATION)
        storage_nodes = self.nodes_by_type(NodeType.STORAGE)
        if pick_stations and storage_nodes:
            test_storage = storage_nodes[0]
            reachable = False
            for ps in pick_stations:
                if nx.has_path(self.graph, test_storage, ps):
                    reachable = True
                    break
            if not reachable:
                issues.append(
                    f"No pick station reachable from storage node {test_storage}"
                )

        return issues
