"""
# pylint: disable=line-too-long
Warehouse layout generators — Highway-Aisle Design

Builds a WarehouseGraph from a WarehouseConfig. Models an Amazon/Kiva-style
warehouse with two-way aisles, storage racks on both sides.

Layout geometry (top-down, not to scale):

    [CS0]         [CS1]         [CS2]         [CS3]
    |             |             |             |
    H═════════════H═════════════H═════════════H  ← Top highway (Connects storage grid to charging stations)
|       |             |             |             |
|       |             |             |             |
-[S]-[S]-[S]--[S]--[S]-[S]--[S]--[S]-[S]--[S]--[S]-  ← Horizontal Aisle (Access to storage cells on both sides)
|       |             |             |             |
|       |             |             |             |
    H═════════════H═════════════H═════════════H  ← Bottom highway (Connects storage grid to picking stations)
    |             |             |             |
    [PS0]         [PS1]         [PS2]         [PS3]

Nomenclature:
    - NodeType:
        - INTERSECTION: Highway-aisle intersection points (AGVs can turn here)
                        I_H{i}_A{j} for intersection at highway i and aisle j
        - STORAGE: Storage cell locations along the aisles
                   S_A{i}_S{j}_C{k} for storage cell k in aisle i, segment j and numbered from the left highway to the right
        - PICK_STATION: Picking stations at the south end
                        PS_{i} for pick station i numbered from left to right
        - CHARGING: Charging stations at the north end
                    CS_{i} for charging station i numbered from left to right
        - PARKING: Parking/waiting spots at the four corners of the storage grid
                   PK0: Top-left, PK1: Top-right, PK2: Bottom-right, PK3: Bottom-left

    - EdgeType:
        - HIGHWAY: Edges along the vertical highways (higher speed, higher capacity)
        - AISLE: Edges along the horizontal aisles (lower speed, lower capacity)
        - STATION_ACCESS: Edges connecting pick/charging stations and parking spots to the main highway grid

# pylint: enable=line-too-long
"""

from __future__ import annotations

from src.warehouse.config import WarehouseConfig
from src.warehouse.graph import WarehouseGraph, NodeType, EdgeType


class GridLayoutGenerator:
    """
    Generates a warehouse graph with parallel edges.

    For all adjacent nodes u, v:
    - Edge going from u to v
    - Edge going from v to u

    We are modeling parallel paths along each edge
    """

    def __init__(self, config: WarehouseConfig) -> None:
        self.layout_config = config.layout
        self.config = config

        # Top level parameters
        self.n_highways = self.layout_config.n_highways
        self.n_aisles = self.layout_config.n_aisles
        self.dist_between_storage_cells = (
            self.layout_config.dist_between_storage_cells_m
        )
        self.n_storage_cells_per_segment = (
            self.layout_config.n_storage_cells_per_segment
        )
        self.n_pick_stations = self.n_highways
        self.n_charging_stations = self.n_highways
        # self.n_parking_spots = self.station_config.n_parking_spots

        # Derived parameters
        self.distance_between_highways = (
            self.n_storage_cells_per_segment + 1
        ) * self.dist_between_storage_cells
        self.distance_between_aisles = 2 * self.dist_between_storage_cells
        self.num_intersection_nodes = self.n_aisles
        self.num_aisle_segments = self.n_highways - 1
        self.warehouse_width = self.num_aisle_segments * self.distance_between_highways
        self.warehouse_depth = (self.n_aisles - 1) * self.distance_between_aisles

        self.distance_between_picking_stations = self.warehouse_width / (
            self.n_pick_stations + 1
        )

    def generate(self) -> WarehouseGraph:
        """Build and return the complete warehouse graph."""
        graph = WarehouseGraph()

        self._add_highways(graph)
        self._add_aisles(graph)
        self._connect_aisles_to_highways(graph)
        self._add_picking_stations(graph)
        self._add_parking_areas(graph)
        self._add_charging_stations(graph)

        return graph

    # ── Geometry helpers ─────────────────────────────────────────

    def _add_highways(self, graph: WarehouseGraph):
        """Add the highway nodes and edges"""

        # Add Highway Nodes
        for i in range(self.n_highways):
            for j in range(self.num_intersection_nodes):
                node_id = f"I_H{i}_A{j}"
                graph.add_node(
                    node_id,
                    node_type=NodeType.INTERSECTION,
                    x=i * self.distance_between_highways,
                    y=j * self.distance_between_aisles,
                )

        # Add Highway Edges
        # Vertical Edges Only
        for i in range(self.n_highways):
            for j in range(self.n_aisles - 1):
                from_node_id = f"I_H{i}_A{j}"
                to_node_id = f"I_H{i}_A{j + 1}"
                graph.add_bidirectional_edges(
                    from_node_id,
                    to_node_id,
                    edge_type=EdgeType.HIGHWAY,
                    capacity=3,
                )

    def _add_aisles(self, graph: WarehouseGraph):
        """Add all aisle points and edges"""

        # Add Highway Nodes
        for i in range(self.n_aisles):
            for j in range(self.num_aisle_segments):
                for k in range(self.n_storage_cells_per_segment):
                    node_id = f"S_A{i}_S{j}_C{k}"
                    graph.add_node(
                        node_id,
                        node_type=NodeType.STORAGE,
                        x=(j * self.distance_between_highways)
                        + ((k + 1) * self.dist_between_storage_cells),
                        y=i * self.distance_between_aisles,
                    )

        # Add Highway Edges
        # Horizontal Edges only
        for i in range(self.n_aisles):
            for j in range(self.num_aisle_segments):
                for k in range(self.n_storage_cells_per_segment - 1):
                    from_node_id = f"S_A{i}_S{j}_C{k}"
                    to_node_id = f"S_A{i}_S{j}_C{k + 1}"
                    graph.add_bidirectional_edges(
                        from_node_id,
                        to_node_id,
                        edge_type=EdgeType.AISLE,
                        capacity=2,
                    )

    def _connect_aisles_to_highways(self, graph: WarehouseGraph):
        """Connects the highway intersection points to the neighboring aisle points"""

        # Main loop
        for i in range(self.n_aisles):
            for j in range(self.num_aisle_segments):
                # Connection 1
                from_node_id = f"I_H{j}_A{i}"
                to_node_id = f"S_A{i}_S{j}_C0"
                graph.add_bidirectional_edges(
                    from_node_id,
                    to_node_id,
                    edge_type=EdgeType.AISLE,
                    capacity=2,
                )

                # Connection 2
                from_node_id = f"I_H{j + 1}_A{i}"
                to_node_id = f"S_A{i}_S{j}_C4"
                graph.add_bidirectional_edges(
                    from_node_id,
                    to_node_id,
                    edge_type=EdgeType.AISLE,
                    capacity=2,
                )

    def _add_picking_stations(self, graph: WarehouseGraph):
        """Add picking stations"""

        # Add Picking Station Nodes & Buffer Highway Nodes
        for i in range(self.n_pick_stations):
            node_id = f"PS_{i}"
            graph.add_node(
                node_id,
                node_type=NodeType.PICK_STATION,
                x=(i + 1) * self.distance_between_picking_stations,
                y=-2 * self.distance_between_aisles,
            )

            buffer_node_id = f"I_BL{i}"
            graph.add_node(
                buffer_node_id,
                node_type=NodeType.INTERSECTION,
                x=(i + 1) * self.distance_between_picking_stations,
                y=-1 * self.distance_between_aisles,
            )

            # Add edges connecting pick stations to buffer highways intersections
            graph.add_bidirectional_edges(
                node_id,
                buffer_node_id,
                edge_type=EdgeType.STATION_ACCESS,
                capacity=2,
            )

        # Add buffer highway edges
        for i in range(self.n_pick_stations - 1):
            from_node_id = f"I_BL{i}"
            to_node_id = f"I_BL{i + 1}"
            graph.add_bidirectional_edges(
                from_node_id,
                to_node_id,
                edge_type=EdgeType.HIGHWAY,
                capacity=5,
            )

        # Connect buffer highway to vertical highways
        for i in range(self.n_pick_stations):
            from_node_id = f"I_BL{i}"
            to_node_id = f"I_H{i}_A0"
            graph.add_bidirectional_edges(
                from_node_id,
                to_node_id,
                edge_type=EdgeType.HIGHWAY,
                capacity=5,
            )

    def _add_parking_areas(self, graph: WarehouseGraph):
        """Add waiting areas"""

        node_id = "PK0"
        graph.add_node(
            node_id,
            node_type=NodeType.PARKING,
            x=0.0,
            y=-1 * self.distance_between_aisles,
        )
        graph.add_bidirectional_edges(
            node_id,
            "I_H0_A0",
            edge_type=EdgeType.STATION_ACCESS,
            capacity=2,
        )

        node_id = "PK1"
        graph.add_node(
            node_id,
            node_type=NodeType.PARKING,
            x=self.warehouse_width,
            y=-1 * self.distance_between_aisles,
        )
        graph.add_bidirectional_edges(
            node_id,
            f"I_H{self.n_highways - 1}_A0",
            edge_type=EdgeType.STATION_ACCESS,
            capacity=2,
        )

        node_id = "PK2"
        graph.add_node(
            node_id,
            node_type=NodeType.PARKING,
            x=self.warehouse_width,
            y=self.warehouse_depth + self.distance_between_aisles,
        )
        to_node = f"I_H{self.n_highways - 1}_A{self.n_aisles - 1}"
        graph.add_bidirectional_edges(
            node_id,
            to_node,
            edge_type=EdgeType.STATION_ACCESS,
            capacity=2,
        )

        node_id = "PK3"
        graph.add_node(
            node_id,
            node_type=NodeType.PARKING,
            x=0.0,
            y=self.warehouse_depth + self.distance_between_aisles,
        )
        to_node = f"I_H0_A{self.n_aisles - 1}"
        graph.add_bidirectional_edges(
            node_id,
            to_node,
            edge_type=EdgeType.STATION_ACCESS,
            capacity=2,
        )

    def _add_charging_stations(self, graph: WarehouseGraph):
        """Add AGV charging stations"""

        # Add Picking Station Nodes & Buffer Highway Nodes
        for i in range(self.n_charging_stations):
            node_id = f"CS_{i}"
            graph.add_node(
                node_id,
                node_type=NodeType.CHARGING,
                x=(i + 1) * self.distance_between_picking_stations,
                y=self.warehouse_depth + 2 * self.distance_between_aisles,
            )

            buffer_node_id = f"I_BU{i}"
            graph.add_node(
                buffer_node_id,
                node_type=NodeType.INTERSECTION,
                x=(i + 1) * self.distance_between_picking_stations,
                y=self.warehouse_depth + self.distance_between_aisles,
            )

            # Add edges connecting pick stations to buffer highways intersections
            graph.add_bidirectional_edges(
                node_id,
                buffer_node_id,
                edge_type=EdgeType.STATION_ACCESS,
                capacity=2,
            )

        # Add buffer highway edges
        for i in range(self.n_charging_stations - 1):
            from_node_id = f"I_BU{i}"
            to_node_id = f"I_BU{i + 1}"
            graph.add_bidirectional_edges(
                from_node_id,
                to_node_id,
                edge_type=EdgeType.HIGHWAY,
                capacity=5,
            )

        # Connect buffer highway to vertical highways
        for i in range(self.n_charging_stations):
            from_node_id = f"I_BU{i}"
            to_node_id = f"I_H{i}_A{self.n_aisles - 1}"
            graph.add_bidirectional_edges(
                from_node_id,
                to_node_id,
                edge_type=EdgeType.HIGHWAY,
                capacity=5,
            )
