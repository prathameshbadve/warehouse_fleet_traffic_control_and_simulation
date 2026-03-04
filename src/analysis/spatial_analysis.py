"""
Spatial Analysis Module for Warehouse Simulation
Tracks edge/node usage, identifies congestion hotspots, and generates heat maps
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from src.warehouse.graph import WarehouseGraph, NodeType


@dataclass
class EdgeUsageStats:
    """Statistics for a single edge."""

    from_node: str
    to_node: str
    traversal_count: int = 0
    total_time_spent_s: float = 0.0
    avg_speed_mps: float = 0.0
    congestion_score: float = 0.0  # 0-100, higher = more congested


@dataclass
class NodeUsageStats:
    """Statistics for a single node."""

    node_id: str
    visit_count: int = 0
    total_dwell_time_s: float = 0.0
    avg_dwell_time_s: float = 0.0
    max_queue_length: int = 0
    congestion_score: float = 0.0


@dataclass
class CongestionHotspot:
    """Represents a congestion hotspot in the warehouse."""

    location_id: str  # Node or edge ID
    location_type: str  # 'node' or 'edge'
    congestion_score: float
    reason: str  # Description of why it's congested
    recommendation: str  # What to do about it


class SpatialAnalyzer:
    """
    Tracks and analyzes spatial usage patterns in the warehouse.
    Identifies bottlenecks and generates heat maps.
    """

    def __init__(self, warehouse: WarehouseGraph):
        self.warehouse = warehouse

        # Track edge usage
        self.edge_usage: Dict[Tuple[str, str], EdgeUsageStats] = {}

        # Track node usage
        self.node_usage: Dict[str, NodeUsageStats] = {}

        # Initialize all edges and nodes
        self._initialize_tracking()

    def _initialize_tracking(self):
        """Initialize tracking for all edges and nodes."""
        # Initialize all edges
        for from_node, to_node in self.warehouse.graph.edges():
            edge_key = (from_node, to_node)
            self.edge_usage[edge_key] = EdgeUsageStats(
                from_node=from_node, to_node=to_node
            )

        # Initialize all nodes
        for node_id in self.warehouse.graph.nodes():
            self.node_usage[node_id] = NodeUsageStats(node_id=node_id)

    def record_edge_traversal(
        self, from_node: str, to_node: str, time_spent_s: float, distance_m: float
    ):
        """Record that an AGV traversed an edge."""
        edge_key = (from_node, to_node)

        if edge_key not in self.edge_usage:
            self.edge_usage[edge_key] = EdgeUsageStats(
                from_node=from_node, to_node=to_node
            )

        stats = self.edge_usage[edge_key]
        stats.traversal_count += 1
        stats.total_time_spent_s += time_spent_s

        # Calculate average speed
        if distance_m > 0 and time_spent_s > 0:
            speed = distance_m / time_spent_s
            # Running average
            n = stats.traversal_count
            stats.avg_speed_mps = (stats.avg_speed_mps * (n - 1) + speed) / n

    def record_node_visit(self, node_id: str, dwell_time_s: float):
        """Record that an AGV visited a node."""
        if node_id not in self.node_usage:
            self.node_usage[node_id] = NodeUsageStats(node_id=node_id)

        stats = self.node_usage[node_id]
        stats.visit_count += 1
        stats.total_dwell_time_s += dwell_time_s
        stats.avg_dwell_time_s = stats.total_dwell_time_s / stats.visit_count

    def calculate_congestion_scores(self):
        """Calculate congestion scores for all edges and nodes."""
        # Edge congestion: based on traversal count and slow speeds
        if self.edge_usage:
            max_traversals = max(e.traversal_count for e in self.edge_usage.values())

            for edge_stats in self.edge_usage.values():
                if max_traversals > 0:
                    # High traversals = high congestion
                    utilization_score = (
                        edge_stats.traversal_count / max_traversals
                    ) * 100

                    # Low speeds suggest congestion (if we have speed data)
                    # This is a simplification - in reality would need baseline speed
                    edge_stats.congestion_score = utilization_score

        # Node congestion: based on dwell time
        if self.node_usage:
            max_dwell = max(
                (n.total_dwell_time_s for n in self.node_usage.values()), default=0
            )

            for node_stats in self.node_usage.values():
                if max_dwell > 0:
                    node_stats.congestion_score = (
                        node_stats.total_dwell_time_s / max_dwell
                    ) * 100

    def identify_hotspots(self, top_n: int = 10) -> List[CongestionHotspot]:
        """
        Identify the top N congestion hotspots in the warehouse.

        Args:
            top_n: Number of hotspots to return

        Returns:
            List of CongestionHotspot objects, sorted by severity
        """
        self.calculate_congestion_scores()

        hotspots = []

        # Find congested edges
        for edge_key, stats in self.edge_usage.items():
            if stats.congestion_score > 50:  # Threshold for "congested"
                from_node, to_node = edge_key

                # Determine reason and recommendation
                reason = f"High traffic ({stats.traversal_count} traversals)"
                recommendation = "Consider adding parallel path or widening corridor"

                hotspots.append(
                    CongestionHotspot(
                        location_id=f"{from_node} → {to_node}",
                        location_type="edge",
                        congestion_score=stats.congestion_score,
                        reason=reason,
                        recommendation=recommendation,
                    )
                )

        # Find congested nodes
        for node_id, stats in self.node_usage.items():
            if stats.congestion_score > 50:
                node_type = self.warehouse.get_node(node_id).get("node_type")

                reason = (
                    f"Long dwell time ({stats.avg_dwell_time_s:.1f}s avg, "
                    f"{stats.visit_count} visits)"
                )

                # Recommendations based on node type
                if node_type == NodeType.PICK_STATION:
                    recommendation = "Increase pick station capacity or add stations"
                elif node_type == NodeType.CHARGING:
                    recommendation = "Add more charging stations or increase capacity"
                elif node_type == NodeType.INTERSECTION:
                    recommendation = "Review routing logic or add alternative paths"
                else:
                    recommendation = "Review operational procedures at this location"

                hotspots.append(
                    CongestionHotspot(
                        location_id=node_id,
                        location_type="node",
                        congestion_score=stats.congestion_score,
                        reason=reason,
                        recommendation=recommendation,
                    )
                )

        # Sort by congestion score and return top N
        hotspots.sort(key=lambda x: x.congestion_score, reverse=True)
        return hotspots[:top_n]

    def generate_traffic_heatmap(
        self,
        output_path: str,
        metric: str = "traversals",
        figsize: Tuple[int, int] = (14, 10),
    ):
        """
        Generate a heat map visualization of traffic patterns.

        Args:
            output_path: Where to save the plot
            metric: 'traversals' or 'dwell_time'
            figsize: Figure size in inches
        """
        _, ax = plt.subplots(figsize=figsize)

        # Get node positions
        node_positions = {}
        for node_id in self.warehouse.graph.nodes():
            node_data = self.warehouse.get_node(node_id)
            node_positions[node_id] = (node_data["x"], node_data["y"])

        # Draw edges with thickness based on usage
        if metric == "traversals":
            max_value = max(
                (e.traversal_count for e in self.edge_usage.values()), default=1
            )

            for edge_key, stats in self.edge_usage.items():
                from_node, to_node = edge_key

                if from_node in node_positions and to_node in node_positions:
                    x1, y1 = node_positions[from_node]
                    x2, y2 = node_positions[to_node]

                    # Line width proportional to usage
                    width = max(0.5, (stats.traversal_count / max_value) * 5)

                    # Color intensity based on congestion
                    intensity = stats.congestion_score / 100
                    color = plt.get_cmap("hot")(intensity)

                    ax.plot(
                        [x1, x2],
                        [y1, y2],
                        color=color,
                        linewidth=width,
                        alpha=0.6,
                        zorder=1,
                    )

        # Draw nodes with size based on usage
        for node_id, stats in self.node_usage.items():
            if node_id in node_positions:
                x, y = node_positions[node_id]
                node_data = self.warehouse.get_node(node_id)
                node_type = node_data.get("node_type")

                # Size based on visits
                size = (
                    20
                    + (
                        stats.visit_count
                        / max(n.visit_count for n in self.node_usage.values())
                    )
                    * 200
                )

                # Color based on type
                if node_type == NodeType.STORAGE:
                    color = "lightblue"
                elif node_type == NodeType.PICK_STATION:
                    color = "lightgreen"
                elif node_type == NodeType.CHARGING:
                    color = "yellow"
                elif node_type == NodeType.PARKING:
                    color = "lightgray"
                else:  # INTERSECTION
                    color = "white"

                # Outline intensity based on congestion
                edge_color = plt.get_cmap("hot")(stats.congestion_score / 100)

                ax.scatter(
                    x,
                    y,
                    s=size,
                    c=[color],
                    edgecolors=edge_color,
                    linewidths=2,
                    zorder=2,
                    alpha=0.7,
                )

        ax.set_xlabel("X Position (m)", fontsize=12)
        ax.set_ylabel("Y Position (m)", fontsize=12)
        ax.set_title(
            f"Warehouse Traffic Heat Map ({metric})", fontsize=14, fontweight="bold"
        )
        ax.grid(True, alpha=0.3)
        ax.set_aspect("equal")

        # Add colorbar
        sm = plt.cm.ScalarMappable(
            cmap=plt.get_cmap("hot"), norm=plt.Normalize(vmin=0, vmax=100)
        )
        sm.set_array([])
        _ = plt.colorbar(sm, ax=ax, label="Congestion Score")

        # Add legend
        legend_elements = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Storage",
                markerfacecolor="lightblue",
                markersize=10,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Pick Station",
                markerfacecolor="lightgreen",
                markersize=10,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Charging",
                markerfacecolor="yellow",
                markersize=10,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Parking",
                markerfacecolor="lightgray",
                markersize=10,
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                label="Intersection",
                markerfacecolor="white",
                markersize=10,
                markeredgecolor="black",
            ),
        ]
        ax.legend(
            handles=legend_elements,
            loc="upper right",
            title="Node Types",
            framealpha=0.9,
        )

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"Traffic heat map saved to {output_path}")

    def generate_summary_report(self) -> Dict:
        """Generate a summary dictionary of spatial analysis results."""
        self.calculate_congestion_scores()

        # Most used edges
        top_edges = sorted(
            self.edge_usage.values(), key=lambda e: e.traversal_count, reverse=True
        )[:5]

        # Most visited nodes
        top_nodes = sorted(
            self.node_usage.values(), key=lambda n: n.visit_count, reverse=True
        )[:5]

        # Hotspots
        hotspots = self.identify_hotspots(top_n=5)

        return {
            "total_edges_tracked": len(self.edge_usage),
            "total_nodes_tracked": len(self.node_usage),
            "total_edge_traversals": sum(
                e.traversal_count for e in self.edge_usage.values()
            ),
            "total_node_visits": sum(n.visit_count for n in self.node_usage.values()),
            "top_edges": [
                {
                    "from": e.from_node,
                    "to": e.to_node,
                    "traversals": e.traversal_count,
                    "avg_speed_mps": e.avg_speed_mps,
                    "congestion_score": e.congestion_score,
                }
                for e in top_edges
            ],
            "top_nodes": [
                {
                    "node_id": n.node_id,
                    "visits": n.visit_count,
                    "avg_dwell_time_s": n.avg_dwell_time_s,
                    "congestion_score": n.congestion_score,
                }
                for n in top_nodes
            ],
            "hotspots": [
                {
                    "location": h.location_id,
                    "type": h.location_type,
                    "score": h.congestion_score,
                    "reason": h.reason,
                    "recommendation": h.recommendation,
                }
                for h in hotspots
            ],
        }
