"""
Multi-Scenario Comparison Module
Creates side-by-side visualizations for comparing multiple simulation runs
"""

import sys
from typing import Dict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import numpy as np

# Add paths
cwd = Path.cwd()
parent_dir = cwd.parent
for parent in [cwd] + list(cwd.parents):
    if (parent / "pyproject.toml").exists():
        parent_dir = parent

# Add to Python path if not already there
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from src.simulation.metrics import SimulationMetrics  # noqa: E402, pylint: disable=wrong-import-position


class ScenarioComparison:
    """
    Compare multiple simulation scenarios and generate comparison visualizations.

    Useful for analyzing:
    - Fleet size optimization
    - Workload sensitivity
    - Configuration trade-offs
    """

    def __init__(self, output_dir: str = "data/output/results/comparison"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        self.scenarios: Dict[str, SimulationMetrics] = {}
        self.scenario_metadata: Dict[str, Dict] = {}

        # Styling
        plt.style.use("seaborn-v0_8-darkgrid")
        self.colors = ["#2E86AB", "#A23B72", "#F18F01", "#06A77D", "#C73E1D"]

    def add_scenario(
        self, name: str, metrics: SimulationMetrics, metadata: Dict = None
    ):
        """
        Add a scenario to the comparison.

        Args:
            name: Scenario name (e.g., "20_AGVs", "High_Load")
            metrics: SimulationMetrics object from the run
            metadata: Optional dict with scenario parameters
                      (e.g., {'n_agvs': 20, 'task_rate': 8.0})
        """
        self.scenarios[name] = metrics
        self.scenario_metadata[name] = metadata or {}
        print(f"✓ Added scenario: {name}")

    def generate_comparison_report(self):
        """Generate all comparison visualizations."""
        if len(self.scenarios) < 2:
            print("Warning: Need at least 2 scenarios to compare")
            return

        print("\n" + "=" * 60)
        print("GENERATING SCENARIO COMPARISON VISUALIZATIONS")
        print("=" * 60)

        print(f"\nComparing {len(self.scenarios)} scenarios:")
        for name in self.scenarios:
            print(f"  • {name}")

        print("\n[1/5] Creating KPI comparison dashboard...")
        self.create_kpi_comparison()

        print("[2/5] Creating performance metrics comparison...")
        self.create_performance_comparison()

        print("[3/5] Creating SLA compliance comparison...")
        self.create_sla_comparison()

        print("[4/5] Creating resource utilization comparison...")
        self.create_utilization_comparison()

        print("[5/5] Creating detailed comparison table...")
        self.create_comparison_table()

        print("\n" + "=" * 60)
        print(f"✓ All comparison visualizations saved to: {self.output_dir}")
        print("=" * 60 + "\n")

    def create_kpi_comparison(self):
        """Create a dashboard comparing key KPIs across scenarios."""
        fig = plt.figure(figsize=(16, 10))
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)

        fig.suptitle("KPI Comparison Across Scenarios", fontsize=18, fontweight="bold")

        scenario_names = list(self.scenarios.keys())
        x_pos = np.arange(len(scenario_names))
        bar_width = 0.7

        # 1. Throughput comparison
        ax1 = fig.add_subplot(gs[0, 0])
        throughputs = [
            self.scenarios[s].avg_throughput_per_hour for s in scenario_names
        ]
        bars = ax1.bar(
            x_pos,
            throughputs,
            bar_width,
            color=self.colors[0],
            alpha=0.7,
            edgecolor="black",
        )
        ax1.set_ylabel("Tasks per Hour", fontsize=11, fontweight="bold")
        ax1.set_title("System Throughput", fontsize=12, fontweight="bold")
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax1.grid(True, alpha=0.3, axis="y")

        # Add value labels
        for b in bars:
            height = b.get_height()
            ax1.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        # 2. Cycle time comparison
        ax2 = fig.add_subplot(gs[0, 1])
        cycle_times_mean = [self.scenarios[s].avg_cycle_time_s for s in scenario_names]
        cycle_times_p95 = [self.scenarios[s].p95_cycle_time_s for s in scenario_names]

        x_pos2 = np.arange(len(scenario_names))
        width = 0.35

        # pylint: disable=unused-variable
        bars1 = ax2.bar(  # noqa: F841
            x_pos2 - width / 2,
            cycle_times_mean,
            width,
            label="Mean",
            color=self.colors[1],
            alpha=0.7,
            edgecolor="black",
        )
        bars2 = ax2.bar(  # noqa: F841
            x_pos2 + width / 2,
            cycle_times_p95,
            width,
            label="P95",
            color=self.colors[2],
            alpha=0.7,
            edgecolor="black",
        )

        ax2.set_ylabel("Seconds", fontsize=11, fontweight="bold")
        ax2.set_title("Cycle Time (Mean vs P95)", fontsize=12, fontweight="bold")
        ax2.set_xticks(x_pos2)
        ax2.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis="y")

        # 3. SLA compliance comparison
        ax3 = fig.add_subplot(gs[1, 0])
        sla_rates = [
            self.scenarios[s].sla_compliance_rate_overall for s in scenario_names
        ]
        bars = ax3.bar(
            x_pos,
            sla_rates,
            bar_width,
            color=self.colors[3],
            alpha=0.7,
            edgecolor="black",
        )
        ax3.axhline(
            90,
            color="red",
            linestyle="--",
            linewidth=2,
            alpha=0.7,
            label="Target (90%)",
        )
        ax3.set_ylabel("Compliance Rate (%)", fontsize=11, fontweight="bold")
        ax3.set_title("SLA Compliance", fontsize=12, fontweight="bold")
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax3.set_ylim(0, 105)
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis="y")

        # Add value labels with color coding
        for b in bars:
            height = b.get_height()
            color = "green" if height >= 90 else "red"
            ax3.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color=color,
            )

        # 4. AGV utilization comparison
        ax4 = fig.add_subplot(gs[1, 1])
        avg_utils = [self.scenarios[s].avg_agv_utilization_pct for s in scenario_names]
        bars = ax4.bar(
            x_pos,
            avg_utils,
            bar_width,
            color=self.colors[4],
            alpha=0.7,
            edgecolor="black",
        )
        ax4.axhline(
            70,
            color="orange",
            linestyle="--",
            linewidth=1.5,
            alpha=0.7,
            label="Target (70%)",
        )
        ax4.axhline(
            85,
            color="red",
            linestyle="--",
            linewidth=1.5,
            alpha=0.7,
            label="High (85%)",
        )
        ax4.set_ylabel("Utilization (%)", fontsize=11, fontweight="bold")
        ax4.set_title("AGV Fleet Utilization", fontsize=12, fontweight="bold")
        ax4.set_xticks(x_pos)
        ax4.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax4.set_ylim(0, 100)
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis="y")

        # Add value labels
        for b in bars:
            height = b.get_height()
            ax4.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        plt.savefig(
            self.output_dir / "comparison_01_kpi_dashboard.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

    def create_performance_comparison(self):
        """Compare detailed performance metrics across scenarios."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("Performance Metrics Comparison", fontsize=16, fontweight="bold")

        scenario_names = list(self.scenarios.keys())
        x_pos = np.arange(len(scenario_names))

        # 1. Cycle time percentiles
        ax = axes[0, 0]
        p50_vals = [self.scenarios[s].p50_cycle_time_s for s in scenario_names]
        p75_vals = [self.scenarios[s].p75_cycle_time_s for s in scenario_names]
        p90_vals = [self.scenarios[s].p90_cycle_time_s for s in scenario_names]
        p95_vals = [self.scenarios[s].p95_cycle_time_s for s in scenario_names]

        width = 0.2
        ax.bar(
            x_pos - 1.5 * width,
            p50_vals,
            width,
            label="P50",
            color=self.colors[0],
            alpha=0.7,
        )
        ax.bar(
            x_pos - 0.5 * width,
            p75_vals,
            width,
            label="P75",
            color=self.colors[1],
            alpha=0.7,
        )
        ax.bar(
            x_pos + 0.5 * width,
            p90_vals,
            width,
            label="P90",
            color=self.colors[2],
            alpha=0.7,
        )
        ax.bar(
            x_pos + 1.5 * width,
            p95_vals,
            width,
            label="P95",
            color=self.colors[3],
            alpha=0.7,
        )

        ax.set_ylabel("Cycle Time (seconds)", fontsize=10)
        ax.set_title("Cycle Time Percentiles", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 2. Tasks completed
        ax = axes[0, 1]
        tasks_completed = [self.scenarios[s].tasks_completed for s in scenario_names]
        tasks_generated = [self.scenarios[s].tasks_generated for s in scenario_names]

        # pylint: disable=unused-variable
        width = 0.35
        bars1 = ax.bar(  # noqa: F841
            x_pos - width / 2,
            tasks_generated,
            width,
            label="Generated",
            color=self.colors[0],
            alpha=0.5,
            edgecolor="black",
        )
        bars2 = ax.bar(  # noqa: F841
            x_pos + width / 2,
            tasks_completed,
            width,
            label="Completed",
            color=self.colors[3],
            alpha=0.7,
            edgecolor="black",
        )

        ax.set_ylabel("Number of Tasks", fontsize=10)
        ax.set_title("Tasks Generated vs Completed", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 3. Distance and energy metrics
        ax = axes[1, 0]
        distances = [self.scenarios[s].avg_distance_per_task_m for s in scenario_names]
        bars = ax.bar(
            x_pos, distances, 0.7, color=self.colors[2], alpha=0.7, edgecolor="black"
        )
        ax.set_ylabel("Distance per Task (meters)", fontsize=10)
        ax.set_title("Average Distance per Task", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.grid(True, alpha=0.3, axis="y")

        # Add value labels
        for b in bars:
            height = b.get_height()
            ax.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}m",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        # 4. Task breakdown (if available)
        ax = axes[1, 1]
        ax.axis("off")

        # Create a summary table
        summary_data = [["Metric"] + scenario_names]

        metrics_to_show = [
            ("Throughput", "avg_throughput_per_hour", "{:.2f}"),
            ("Avg Cycle Time", "avg_cycle_time_s", "{:.1f}s"),
            ("SLA Compliance", "sla_compliance_rate_overall", "{:.1f}%"),
            ("AGV Utilization", "avg_agv_utilization_pct", "{:.1f}%"),
            ("Total Distance", "total_distance_travelled_m", "{:.0f}m"),
        ]

        for label, attr, fmt in metrics_to_show:
            row = [label]
            for s in scenario_names:
                val = getattr(self.scenarios[s], attr)
                row.append(fmt.format(val))
            summary_data.append(row)

        table = ax.table(
            cellText=summary_data, cellLoc="center", loc="center", bbox=[0, 0.1, 1, 0.8]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        # Style header
        for i in range(len(scenario_names) + 1):
            cell = table[(0, i)]
            cell.set_facecolor(self.colors[0])
            cell.set_text_props(weight="bold", color="white")

        # Alternate row colors
        for i in range(1, len(summary_data)):
            for j in range(len(scenario_names) + 1):
                cell = table[(i, j)]
                if i % 2 == 0:
                    cell.set_facecolor("#f0f0f0")

        ax.set_title(
            "Performance Summary Table", fontsize=11, fontweight="bold", pad=20
        )

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "comparison_02_performance_metrics.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

    def create_sla_comparison(self):
        """Compare SLA compliance across scenarios."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("SLA Compliance Comparison", fontsize=16, fontweight="bold")

        scenario_names = list(self.scenarios.keys())
        x_pos = np.arange(len(scenario_names))

        # 1. SLA compliance by priority
        ax = axes[0, 0]
        overall = [
            self.scenarios[s].sla_compliance_rate_overall for s in scenario_names
        ]
        standard = [
            self.scenarios[s].sla_compliance_rate_standard for s in scenario_names
        ]
        express = [
            self.scenarios[s].sla_compliance_rate_express for s in scenario_names
        ]

        width = 0.25
        ax.bar(
            x_pos - width,
            overall,
            width,
            label="Overall",
            color=self.colors[0],
            alpha=0.7,
        )
        ax.bar(
            x_pos, standard, width, label="Standard", color=self.colors[3], alpha=0.7
        )
        ax.bar(
            x_pos + width,
            express,
            width,
            label="Express",
            color=self.colors[4],
            alpha=0.7,
        )
        ax.axhline(90, color="red", linestyle="--", linewidth=1.5, alpha=0.5)

        ax.set_ylabel("Compliance Rate (%)", fontsize=10)
        ax.set_title("SLA Compliance by Priority", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.set_ylim(0, 105)
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 2. Percentage of late tasks
        ax = axes[0, 1]
        late_pcts = [self.scenarios[s].pct_tasks_late for s in scenario_names]
        bars = ax.bar(
            x_pos, late_pcts, 0.7, color=self.colors[4], alpha=0.7, edgecolor="black"
        )
        ax.set_ylabel("% of Tasks", fontsize=10)
        ax.set_title("Percentage of Late Tasks", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.grid(True, alpha=0.3, axis="y")

        for b in bars:
            height = b.get_height()
            ax.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        # 3. Average lateness
        ax = axes[1, 0]
        lateness = [self.scenarios[s].avg_lateness_s for s in scenario_names]
        bars = ax.bar(
            x_pos, lateness, 0.7, color=self.colors[2], alpha=0.7, edgecolor="black"
        )
        ax.set_ylabel("Seconds", fontsize=10)
        ax.set_title(
            "Average Lateness (Late Tasks Only)", fontsize=11, fontweight="bold"
        )
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.grid(True, alpha=0.3, axis="y")

        for b in bars:
            height = b.get_height()
            if height > 0:
                ax.text(
                    b.get_x() + b.get_width() / 2.0,
                    height,
                    f"{height:.1f}s",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        # 4. SLA summary table
        ax = axes[1, 1]
        ax.axis("off")

        table_data = [["Metric"] + scenario_names]
        sla_metrics = [
            ("Overall Compliance", "sla_compliance_rate_overall", "{:.2f}%"),
            ("Standard Compliance", "sla_compliance_rate_standard", "{:.2f}%"),
            ("Express Compliance", "sla_compliance_rate_express", "{:.2f}%"),
            ("% Tasks Late", "pct_tasks_late", "{:.2f}%"),
            ("Avg Lateness", "avg_lateness_s", "{:.1f}s"),
            ("Max Lateness", "max_lateness_s", "{:.1f}s"),
        ]

        for label, attr, fmt in sla_metrics:
            row = [label]
            for s in scenario_names:
                val = getattr(self.scenarios[s], attr)
                row.append(fmt.format(val))
            table_data.append(row)

        table = ax.table(
            cellText=table_data, cellLoc="center", loc="center", bbox=[0, 0.1, 1, 0.8]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)

        # Style
        for i in range(len(scenario_names) + 1):
            cell = table[(0, i)]
            cell.set_facecolor(self.colors[0])
            cell.set_text_props(weight="bold", color="white")

        for i in range(1, len(table_data)):
            for j in range(len(scenario_names) + 1):
                cell = table[(i, j)]
                if i % 2 == 0:
                    cell.set_facecolor("#f0f0f0")

        ax.set_title("SLA Metrics Summary", fontsize=11, fontweight="bold", pad=20)

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "comparison_03_sla_compliance.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

    def create_utilization_comparison(self):
        """Compare resource utilization across scenarios."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("Resource Utilization Comparison", fontsize=16, fontweight="bold")

        scenario_names = list(self.scenarios.keys())
        x_pos = np.arange(len(scenario_names))

        # 1. AGV utilization statistics
        ax = axes[0, 0]
        avg_utils = [self.scenarios[s].avg_agv_utilization_pct for s in scenario_names]
        min_utils = [self.scenarios[s].min_agv_utilization_pct for s in scenario_names]
        max_utils = [self.scenarios[s].max_agv_utilization_pct for s in scenario_names]

        ax.plot(
            x_pos,
            avg_utils,
            marker="o",
            linewidth=2,
            markersize=8,
            label="Average",
            color=self.colors[0],
        )
        ax.fill_between(
            x_pos,
            min_utils,
            max_utils,
            alpha=0.3,
            color=self.colors[0],
            label="Min-Max Range",
        )
        ax.axhline(70, color="orange", linestyle="--", linewidth=1.5, alpha=0.5)

        ax.set_ylabel("Utilization (%)", fontsize=10)
        ax.set_title("AGV Utilization (Avg, Min, Max)", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)

        # 2. Station utilization comparison
        ax = axes[0, 1]
        pick_utils = [
            self.scenarios[s].avg_pick_station_utilization for s in scenario_names
        ]
        charging_utils = [
            self.scenarios[s].avg_charging_station_utilization for s in scenario_names
        ]

        width = 0.35
        ax.bar(
            x_pos - width / 2,
            pick_utils,
            width,
            label="Pick Stations",
            color=self.colors[1],
            alpha=0.7,
            edgecolor="black",
        )
        ax.bar(
            x_pos + width / 2,
            charging_utils,
            width,
            label="Charging Stations",
            color=self.colors[2],
            alpha=0.7,
            edgecolor="black",
        )
        ax.axhline(
            80,
            color="red",
            linestyle="--",
            linewidth=1.5,
            alpha=0.5,
            label="High Util (80%)",
        )

        ax.set_ylabel("Utilization (%)", fontsize=10)
        ax.set_title("Station Utilization", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")
        ax.set_ylim(0, 110)

        # 3. Queue lengths
        ax = axes[1, 0]
        pick_queues = [self.scenarios[s].avg_pick_queue_length for s in scenario_names]
        charging_queues = [
            self.scenarios[s].avg_charging_queue_length for s in scenario_names
        ]

        width = 0.35
        ax.bar(
            x_pos - width / 2,
            pick_queues,
            width,
            label="Pick Stations",
            color=self.colors[1],
            alpha=0.7,
            edgecolor="black",
        )
        ax.bar(
            x_pos + width / 2,
            charging_queues,
            width,
            label="Charging Stations",
            color=self.colors[2],
            alpha=0.7,
            edgecolor="black",
        )

        ax.set_ylabel("Avg Queue Length", fontsize=10)
        ax.set_title("Average Queue Lengths", fontsize=11, fontweight="bold")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 4. Wait times
        ax = axes[1, 1]
        wait_times = [self.scenarios[s].avg_wait_time_pick_s for s in scenario_names]
        bars = ax.bar(
            x_pos, wait_times, 0.7, color=self.colors[3], alpha=0.7, edgecolor="black"
        )
        ax.set_ylabel("Seconds", fontsize=10)
        ax.set_title(
            "Average Wait Time at Pick Stations", fontsize=11, fontweight="bold"
        )
        ax.set_xticks(x_pos)
        ax.set_xticklabels(scenario_names, rotation=45, ha="right")
        ax.grid(True, alpha=0.3, axis="y")

        for b in bars:
            height = b.get_height()
            if height > 0:
                ax.text(
                    b.get_x() + b.get_width() / 2.0,
                    height,
                    f"{height:.1f}s",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "comparison_04_utilization.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()

    def create_comparison_table(self):
        """Create a comprehensive comparison table."""
        fig = plt.figure(figsize=(16, 10))
        ax = fig.add_subplot(111)
        ax.axis("off")

        fig.suptitle(
            "Comprehensive Scenario Comparison Table",
            fontsize=16,
            fontweight="bold",
            y=0.98,
        )

        scenario_names = list(self.scenarios.keys())

        # Build comprehensive table
        table_data = [["Metric"] + scenario_names]

        metrics_groups = [
            (
                "TASK PERFORMANCE",
                [
                    ("Tasks Completed", "tasks_completed", "{:.0f}"),
                    ("Throughput (tasks/hr)", "avg_throughput_per_hour", "{:.2f}"),
                ],
            ),
            (
                "CYCLE TIME",
                [
                    ("Mean (s)", "avg_cycle_time_s", "{:.2f}"),
                    ("Median (s)", "median_cycle_time_s", "{:.2f}"),
                    ("P95 (s)", "p95_cycle_time_s", "{:.2f}"),
                    ("Std Dev (s)", "std_cycle_time_s", "{:.2f}"),
                ],
            ),
            (
                "SLA COMPLIANCE",
                [
                    ("Overall (%)", "sla_compliance_rate_overall", "{:.2f}"),
                    ("Standard (%)", "sla_compliance_rate_standard", "{:.2f}"),
                    ("Express (%)", "sla_compliance_rate_express", "{:.2f}"),
                    ("% Late", "pct_tasks_late", "{:.2f}"),
                ],
            ),
            (
                "AGV UTILIZATION",
                [
                    ("Mean (%)", "avg_agv_utilization_pct", "{:.2f}"),
                    ("Min (%)", "min_agv_utilization_pct", "{:.2f}"),
                    ("Max (%)", "max_agv_utilization_pct", "{:.2f}"),
                ],
            ),
            (
                "STATION METRICS",
                [
                    ("Pick Util (%)", "avg_pick_station_utilization", "{:.2f}"),
                    ("Charging Util (%)", "avg_charging_station_utilization", "{:.2f}"),
                    ("Avg Pick Queue", "avg_pick_queue_length", "{:.2f}"),
                ],
            ),
            (
                "DISTANCE & ENERGY",
                [
                    ("Total Distance (m)", "total_distance_travelled_m", "{:.0f}"),
                    ("Dist/Task (m)", "avg_distance_per_task_m", "{:.2f}"),
                    ("Total Energy", "total_energy_consumed", "{:.0f}"),
                ],
            ),
        ]

        for group_name, metrics in metrics_groups:
            # Add group header
            table_data.append([group_name] + [""] * len(scenario_names))

            # Add metrics in group
            for label, attr, fmt in metrics:
                row = [f"  {label}"]
                for s in scenario_names:
                    val = getattr(self.scenarios[s], attr)
                    row.append(fmt.format(val))
                table_data.append(row)

        # Create table
        table = ax.table(
            cellText=table_data, cellLoc="center", loc="center", bbox=[0, 0, 1, 1]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.8)

        # Style header row
        for i in range(len(scenario_names) + 1):
            cell = table[(0, i)]
            cell.set_facecolor(self.colors[0])
            cell.set_text_props(weight="bold", color="white", fontsize=9)

        # Style group headers and alternate rows
        row_idx = 1
        for group_name, metrics in metrics_groups:
            # Group header
            for j in range(len(scenario_names) + 1):
                cell = table[(row_idx, j)]
                cell.set_facecolor("#cccccc")
                cell.set_text_props(weight="bold", fontsize=8)
            row_idx += 1

            # Metrics in group
            for _ in metrics:
                for j in range(len(scenario_names) + 1):
                    cell = table[(row_idx, j)]
                    if row_idx % 2 == 0:
                        cell.set_facecolor("#f5f5f5")
                row_idx += 1

        plt.savefig(
            self.output_dir / "comparison_05_full_table.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close()


def compare_scenarios(
    scenarios_dict: Dict[str, SimulationMetrics],
    output_dir: str = "data/output/results/comparison",
):
    """
    Convenience function to compare multiple scenarios.

    Args:
        scenarios_dict: Dict mapping scenario names to SimulationMetrics
        output_dir: Output directory for comparison plots

    Returns:
        ScenarioComparison object
    """
    comparison = ScenarioComparison(output_dir)

    for name, metrics in scenarios_dict.items():
        comparison.add_scenario(name, metrics)

    comparison.generate_comparison_report()

    return comparison
