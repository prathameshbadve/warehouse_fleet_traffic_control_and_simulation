"""# pylint: disable=too-many-lines
Visualization module for AGV warehouse simulation
Generates plots for analysis
"""

from __future__ import annotations
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

from src.simulation.metrics import SimulationMetrics


class SimulationVisualizer:
    """
    Creates comprehensive visualizations for warehouse simulation results.
    """

    def __init__(
        self,
        metrics: SimulationMetrics,
        output_dir: str = "data/output/results",
    ):
        self.metrics = metrics
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Set professional style
        plt.style.use("seaborn-v0_8-darkgrid")
        self.colors = {
            "primary": "#2E86AB",
            "secondary": "#A23B72",
            "success": "#06A77D",
            "warning": "#F18F01",
            "danger": "#C73E1D",
            "idle": "#95C8D8",
            "working": "#2E86AB",
            "charging": "#F18F01",
            "waiting": "#A23B72",
        }

    def generate_all_plots(self):
        """Generate all visualizations"""

        print("\n" + "=" * 60)
        print("GENERATING SIMULATION RESULTS VISUALIZATIONS")
        print("=" * 60)

        # 1. Executive dashboard (single page overview)
        print("\n[1/7] Creating executive dashboard...")
        self.create_executive_dashboard()

        # 2. Time-series plots
        print("[2/7] Creating time-series analysis...")
        self.create_timeseries_plots()

        # 3. Cycle time distribution
        print("[3/7] Creating cycle time distribution analysis...")
        self.create_cycle_time_analysis()

        # 4. SLA compliance analysis
        print("[4/7] Creating SLA compliance analysis...")
        self.create_sla_analysis()

        # 5. Station utilization and queues
        print("[5/7] Creating station utilization analysis...")
        self.create_station_analysis()

        # 6. AGV performance summary
        print("[6/7] Creating AGV performance summary...")
        self.create_agv_summary_table()

        # 7. AGV fleet analysis
        print("[7/7] Creating AGV fleet distribution plots...")
        self.create_agv_fleet_analysis()

        print("\n" + "=" * 60)
        print(f"✓ All visualizations saved to: {self.output_dir}")
        print("=" * 60 + "\n")

    def create_executive_dashboard(self):
        """
        Creat a single-page executive dashboard with key metrics.
        """

        fig = plt.figure(figsize=(16, 10))
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

        # Title
        fig.suptitle(
            "AGV Warehouse Simulation - Executive Dashboard",
            fontsize=18,
            fontweight="bold",
            y=0.98,
        )

        # Subtitle with simulation parameters
        sim_hours = self.metrics.total_simulation_time_s / 3600
        n_agvs = len(self.metrics.agv_summaries)
        subtitle = (
            f"Simulation Duration: {sim_hours:.1f} hours | "
            f"Fleet Size: {n_agvs} AGVs | "
            f"Tasks Completed: {self.metrics.tasks_completed}"
        )
        fig.text(0.5, 0.95, subtitle, ha="center", fontsize=11, style="italic")

        # === ROW 1: KEY METRICS CARDS ===
        metrics_data = [
            {
                "title": "Throughput",
                "value": f"{self.metrics.avg_throughput_per_hour:.1f}",
                "unit": "tasks/hour",
                "color": self.colors["success"],
            },
            {
                "title": "Avg Cycle Time",
                "value": f"{self.metrics.avg_cycle_time_s:.1f}",
                "unit": "seconds",
                "color": self.colors["primary"],
            },
            {
                "title": "SLA Compliance",
                "value": f"{self.metrics.sla_compliance_rate_overall:.1f}",
                "unit": "%",
                "color": self.colors["success"]
                if self.metrics.sla_compliance_rate_overall >= 90
                else self.colors["warning"],
            },
        ]

        for idx, metric in enumerate(metrics_data):
            ax = fig.add_subplot(gs[0, idx])
            ax.axis("off")

            # Draw card background
            card = Rectangle(
                (0.05, 0.15),
                0.9,
                0.7,
                facecolor=metric["color"],
                alpha=0.1,
                edgecolor=metric["color"],
                linewidth=2,
            )
            ax.add_patch(card)

            # Add text
            ax.text(
                0.5,
                0.7,
                metric["title"],
                ha="center",
                va="top",
                fontsize=12,
                fontweight="bold",
            )
            ax.text(
                0.5,
                0.5,
                metric["value"],
                ha="center",
                va="center",
                fontsize=28,
                fontweight="bold",
                color=metric["color"],
            )
            ax.text(
                0.5,
                0.3,
                metric["unit"],
                ha="center",
                va="top",
                fontsize=10,
                style="italic",
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)

        # === ROW 2: TIME SERIES ===

        # Throughput over time
        ax1 = fig.add_subplot(gs[1, :2])
        times = [s.time_s / 3600 for s in self.metrics.snapshots]
        throughputs = [s.throughput_per_hour for s in self.metrics.snapshots]
        ax1.plot(times, throughputs, linewidth=2, color=self.colors["primary"])
        ax1.fill_between(times, throughputs, alpha=0.3, color=self.colors["primary"])
        ax1.set_xlabel("Time (hours)", fontsize=10)
        ax1.set_ylabel("Throughput (tasks/hour)", fontsize=10)
        ax1.set_title("Throughput Over Time", fontsize=12, fontweight="bold")
        ax1.grid(True, alpha=0.3)

        # AGV states stacked area
        ax2 = fig.add_subplot(gs[1, 2])
        n_idle = [s.n_agvs_idle for s in self.metrics.snapshots]
        n_working = [s.n_agvs_working for s in self.metrics.snapshots]
        n_charging = [s.n_agvs_charging for s in self.metrics.snapshots]
        n_waiting = [s.n_agvs_waiting for s in self.metrics.snapshots]

        ax2.stackplot(
            times,
            n_working,
            n_charging,
            n_waiting,
            n_idle,
            labels=["Working", "Charging", "Waiting", "Idle"],
            colors=[
                self.colors["working"],
                self.colors["charging"],
                self.colors["waiting"],
                self.colors["idle"],
            ],
            alpha=0.8,
        )
        ax2.set_xlabel("Time (hours)", fontsize=10)
        ax2.set_ylabel("Number of AGVs", fontsize=10)
        ax2.set_title("AGV Fleet Status", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, alpha=0.3)

        # === ROW 3: DISTRIBUTIONS ===

        # Cycle time distribution
        ax3 = fig.add_subplot(gs[2, 0])
        if self.metrics.all_cycle_times:
            ax3.hist(
                self.metrics.all_cycle_times,
                bins=30,
                color=self.colors["primary"],
                alpha=0.7,
                edgecolor="black",
            )
            ax3.axvline(
                self.metrics.median_cycle_time_s,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Median: {self.metrics.median_cycle_time_s:.1f}s",
            )
            ax3.axvline(
                self.metrics.p95_cycle_time_s,
                color="orange",
                linestyle="--",
                linewidth=2,
                label=f"P95: {self.metrics.p95_cycle_time_s:.1f}s",
            )
            ax3.legend(fontsize=8)
        ax3.set_xlabel("Cycle Time (seconds)", fontsize=10)
        ax3.set_ylabel("Frequency", fontsize=10)
        ax3.set_title("Cycle Time Distribution", fontsize=12, fontweight="bold")
        ax3.grid(True, alpha=0.3, axis="y")

        # Station utilization comparison
        ax4 = fig.add_subplot(gs[2, 1])
        station_types = ["Pick\nStations", "Charging\nStations"]
        utilizations = [
            self.metrics.avg_pick_station_utilization,
            self.metrics.avg_charging_station_utilization,
        ]
        bars = ax4.bar(
            station_types,
            utilizations,
            color=[self.colors["primary"], self.colors["warning"]],
            alpha=0.7,
            edgecolor="black",
            linewidth=1.5,
        )
        ax4.axhline(100, color="red", linestyle="--", linewidth=1, alpha=0.5)
        ax4.set_ylabel("Utilization (%)", fontsize=10)
        ax4.set_title("Station Utilization", fontsize=12, fontweight="bold")
        ax4.set_ylim(0, 110)
        ax4.grid(True, alpha=0.3, axis="y")

        # Add value labels on bars
        for b in bars:
            height = b.get_height()
            ax4.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10,
            )

        # AGV utilization distribution
        ax5 = fig.add_subplot(gs[2, 2])
        if self.metrics.agv_summaries:
            utils = [v["utilization_pct"] for v in self.metrics.agv_summaries.values()]
            ax5.hist(
                utils,
                bins=20,
                color=self.colors["secondary"],
                alpha=0.7,
                edgecolor="black",
            )
            ax5.axvline(
                np.mean(utils),
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Mean: {np.mean(utils):.1f}%",
            )
            ax5.legend(fontsize=8)
        ax5.set_xlabel("Utilization (%)", fontsize=10)
        ax5.set_ylabel("Number of AGVs", fontsize=10)
        ax5.set_title("AGV Utilization Distribution", fontsize=12, fontweight="bold")
        ax5.grid(True, alpha=0.3, axis="y")

        plt.savefig(
            self.output_dir / "01_executive_dashboard.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

    def create_timeseries_plots(self):
        """Create detailed time-series analysis plots."""
        fig, axes = plt.subplots(3, 2, figsize=(16, 12))
        fig.suptitle("Time-Series Analysis", fontsize=16, fontweight="bold")

        times = [s.time_s / 3600 for s in self.metrics.snapshots]

        # 1. Throughput
        ax = axes[0, 0]
        throughputs = [s.throughput_per_hour for s in self.metrics.snapshots]
        ax.plot(
            times,
            throughputs,
            linewidth=2,
            color=self.colors["primary"],
            marker="o",
            markersize=3,
        )
        ax.set_ylabel("Tasks/Hour", fontsize=11)
        ax.set_title("System Throughput", fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.3)

        # 2. Tasks in system
        ax = axes[0, 1]
        completed = [s.tasks_completed for s in self.metrics.snapshots]
        pending = [s.tasks_pending for s in self.metrics.snapshots]
        ax.plot(
            times,
            completed,
            label="Completed",
            linewidth=2,
            color=self.colors["success"],
        )
        ax.plot(
            times, pending, label="Pending", linewidth=2, color=self.colors["warning"]
        )
        ax.set_ylabel("Number of Tasks", fontsize=11)
        ax.set_title("Tasks Status Over Time", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 3. Cycle time rolling average
        ax = axes[1, 0]
        cycle_times = [s.avg_cycle_time_s for s in self.metrics.snapshots]
        ax.plot(times, cycle_times, linewidth=2, color=self.colors["primary"])
        ax.fill_between(times, cycle_times, alpha=0.3, color=self.colors["primary"])
        ax.set_ylabel("Seconds", fontsize=11)
        ax.set_title("Average Cycle Time", fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.3)

        # 4. SLA compliance
        ax = axes[1, 1]
        sla_overall = [s.sla_compliance_rate_overall for s in self.metrics.snapshots]
        sla_standard = [s.sla_compliance_rate_standard for s in self.metrics.snapshots]
        sla_express = [s.sla_compliance_rate_express for s in self.metrics.snapshots]
        ax.plot(
            times,
            sla_overall,
            label="Overall",
            linewidth=2,
            color=self.colors["primary"],
        )
        ax.plot(
            times,
            sla_standard,
            label="Standard",
            linewidth=2,
            color=self.colors["success"],
            linestyle="--",
        )
        ax.plot(
            times,
            sla_express,
            label="Express",
            linewidth=2,
            color=self.colors["danger"],
            linestyle="--",
        )
        ax.axhline(
            90, color="red", linestyle=":", linewidth=1, alpha=0.5, label="Target (90%)"
        )
        ax.set_ylabel("Compliance Rate (%)", fontsize=11)
        ax.set_title("SLA Compliance Rate", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 105)

        # 5. Station queue lengths
        ax = axes[2, 0]
        pick_queues = [s.avg_pick_station_queue_length for s in self.metrics.snapshots]
        charging_queues = [
            s.avg_charging_station_queue_length for s in self.metrics.snapshots
        ]
        ax.plot(
            times,
            pick_queues,
            label="Pick Stations",
            linewidth=2,
            color=self.colors["primary"],
        )
        ax.plot(
            times,
            charging_queues,
            label="Charging Stations",
            linewidth=2,
            color=self.colors["warning"],
        )
        ax.set_ylabel("Avg Queue Length", fontsize=11)
        ax.set_xlabel("Time (hours)", fontsize=11)
        ax.set_title("Station Queue Lengths", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 6. Average battery level
        ax = axes[2, 1]
        battery_levels = [s.avg_battery_level for s in self.metrics.snapshots]
        ax.plot(times, battery_levels, linewidth=2, color=self.colors["success"])
        ax.fill_between(times, battery_levels, alpha=0.3, color=self.colors["success"])
        ax.axhline(
            20, color="red", linestyle="--", linewidth=1, label="Threshold (20%)"
        )
        ax.set_ylabel("Battery Level (%)", fontsize=11)
        ax.set_xlabel("Time (hours)", fontsize=11)
        ax.set_title("Fleet Average Battery Level", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "02_timeseries_analysis.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

    def create_cycle_time_analysis(self):
        """Create comprehensive cycle time distribution analysis."""
        fig = plt.figure(figsize=(16, 10))
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)

        fig.suptitle("Cycle Time Distribution Analysis", fontsize=16, fontweight="bold")

        cycle_times = self.metrics.all_cycle_times
        if not cycle_times:
            return

        # 1. Histogram with percentiles
        ax1 = fig.add_subplot(gs[0, 0])
        n, bins, patches = ax1.hist(  # pylint: disable=unused-variable
            cycle_times,
            bins=40,
            color=self.colors["primary"],
            alpha=0.7,
            edgecolor="black",
            linewidth=0.5,
        )

        # Add percentile lines
        percentiles = [50, 75, 90, 95, 99]
        colors_p = ["green", "blue", "orange", "red", "darkred"]
        for p, color in zip(percentiles, colors_p):
            val = np.percentile(cycle_times, p)
            ax1.axvline(
                val, color=color, linestyle="--", linewidth=2, label=f"P{p}: {val:.1f}s"
            )

        ax1.set_xlabel("Cycle Time (seconds)", fontsize=11)
        ax1.set_ylabel("Frequency", fontsize=11)
        ax1.set_title("Cycle Time Histogram", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper right", fontsize=9)
        ax1.grid(True, alpha=0.3, axis="y")

        # 2. CDF plot
        ax2 = fig.add_subplot(gs[0, 1])
        sorted_times = np.sort(cycle_times)
        cdf = np.arange(1, len(sorted_times) + 1) / len(sorted_times) * 100
        ax2.plot(sorted_times, cdf, linewidth=2, color=self.colors["primary"])

        # Mark key percentiles
        for p, color in zip(percentiles, colors_p):
            val = np.percentile(cycle_times, p)
            ax2.plot(val, p, "o", markersize=10, color=color, label=f"P{p}: {val:.1f}s")
            ax2.hlines(
                p, sorted_times[0], val, colors=color, linestyles="--", alpha=0.5
            )
            ax2.vlines(val, 0, p, colors=color, linestyles="--", alpha=0.5)

        ax2.set_xlabel("Cycle Time (seconds)", fontsize=11)
        ax2.set_ylabel("Cumulative Probability (%)", fontsize=11)
        ax2.set_title(
            "Cumulative Distribution Function", fontsize=12, fontweight="bold"
        )
        ax2.legend(loc="lower right", fontsize=9)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 105)

        # 3. Box plot with statistics
        ax3 = fig.add_subplot(gs[1, 0])
        bp = ax3.boxplot(
            cycle_times,
            vert=True,
            patch_artist=True,
            widths=0.5,
            showmeans=True,
            meanprops=dict(marker="D", markerfacecolor="red", markersize=8),
        )

        for patch in bp["boxes"]:
            patch.set_facecolor(self.colors["primary"])
            patch.set_alpha(0.5)

        # Add statistics text
        stats_text = (
            f"Mean: {self.metrics.avg_cycle_time_s:.1f}s\n"
            f"Median: {self.metrics.median_cycle_time_s:.1f}s\n"
            f"Std Dev: {self.metrics.std_cycle_time_s:.1f}s\n"
            f"Min: {min(cycle_times):.1f}s\n"
            f"Max: {max(cycle_times):.1f}s"
        )
        ax3.text(
            1.3,
            np.median(cycle_times),
            stats_text,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            fontsize=10,
            verticalalignment="center",
        )

        ax3.set_ylabel("Cycle Time (seconds)", fontsize=11)
        ax3.set_title("Box Plot with Statistics", fontsize=12, fontweight="bold")
        ax3.grid(True, alpha=0.3, axis="y")
        ax3.set_xticklabels(["All Tasks"])

        # 4. Summary statistics table
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.axis("off")

        stats_data = [
            ["Metric", "Value"],
            ["Mean", f"{self.metrics.avg_cycle_time_s:.2f} s"],
            ["Median (P50)", f"{self.metrics.median_cycle_time_s:.2f} s"],
            ["Std Deviation", f"{self.metrics.std_cycle_time_s:.2f} s"],
            ["P75", f"{self.metrics.p75_cycle_time_s:.2f} s"],
            ["P90", f"{self.metrics.p90_cycle_time_s:.2f} s"],
            ["P95", f"{self.metrics.p95_cycle_time_s:.2f} s"],
            ["P99", f"{self.metrics.p99_cycle_time_s:.2f} s"],
            ["Min", f"{min(cycle_times):.2f} s"],
            ["Max", f"{max(cycle_times):.2f} s"],
            ["Total Tasks", f"{len(cycle_times)}"],
        ]

        table = ax4.table(
            cellText=stats_data,
            cellLoc="left",
            colWidths=[0.6, 0.4],
            loc="center",
            bbox=[0.1, 0.1, 0.8, 0.8],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 2)

        # Style header row
        for i in range(2):
            cell = table[(0, i)]
            cell.set_facecolor(self.colors["primary"])
            cell.set_text_props(weight="bold", color="white")

        # Alternate row colors
        for i in range(1, len(stats_data)):
            for j in range(2):
                cell = table[(i, j)]
                if i % 2 == 0:
                    cell.set_facecolor("#f0f0f0")

        ax4.set_title(
            "Cycle Time Statistics Summary", fontsize=12, fontweight="bold", pad=20
        )

        plt.savefig(
            self.output_dir / "03_cycle_time_analysis.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

    def create_sla_analysis(self):
        """Create SLA compliance and lateness analysis."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("SLA Compliance Analysis", fontsize=16, fontweight="bold")

        # 1. SLA compliance rates bar chart
        ax = axes[0, 0]
        categories = ["Overall", "Standard\nTasks", "Express\nTasks"]
        rates = [
            self.metrics.sla_compliance_rate_overall,
            self.metrics.sla_compliance_rate_standard,
            self.metrics.sla_compliance_rate_express,
        ]
        colors = [self.colors["primary"], self.colors["success"], self.colors["danger"]]
        bars = ax.bar(
            categories, rates, color=colors, alpha=0.7, edgecolor="black", linewidth=1.5
        )
        ax.axhline(
            90,
            color="red",
            linestyle="--",
            linewidth=2,
            label="Target (90%)",
            alpha=0.7,
        )
        ax.axhline(
            95,
            color="green",
            linestyle="--",
            linewidth=2,
            label="Stretch Goal (95%)",
            alpha=0.7,
        )
        ax.set_ylabel("Compliance Rate (%)", fontsize=11)
        ax.set_title("SLA Compliance Rates", fontsize=12, fontweight="bold")
        ax.set_ylim(0, 105)
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # Add value labels
        for b in bars:
            height = b.get_height()
            ax.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )

        # 2. SLA compliance over time
        ax = axes[0, 1]
        times = [s.time_s / 3600 for s in self.metrics.snapshots]
        sla_overall = [s.sla_compliance_rate_overall for s in self.metrics.snapshots]
        sla_standard = [s.sla_compliance_rate_standard for s in self.metrics.snapshots]
        sla_express = [s.sla_compliance_rate_express for s in self.metrics.snapshots]

        ax.plot(
            times,
            sla_overall,
            label="Overall",
            linewidth=2.5,
            color=self.colors["primary"],
        )
        ax.plot(
            times,
            sla_standard,
            label="Standard",
            linewidth=2,
            color=self.colors["success"],
            linestyle="--",
            alpha=0.8,
        )
        ax.plot(
            times,
            sla_express,
            label="Express",
            linewidth=2,
            color=self.colors["danger"],
            linestyle="--",
            alpha=0.8,
        )
        ax.axhline(90, color="red", linestyle=":", linewidth=1.5, alpha=0.5)
        ax.set_xlabel("Time (hours)", fontsize=11)
        ax.set_ylabel("Compliance Rate (%)", fontsize=11)
        ax.set_title("SLA Compliance Over Time", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 105)

        # 3. Lateness distribution
        ax = axes[1, 0]
        if self.metrics.all_lateness_values:
            ax.hist(
                self.metrics.all_lateness_values,
                bins=30,
                color=self.colors["danger"],
                alpha=0.7,
                edgecolor="black",
            )
            ax.axvline(
                self.metrics.avg_lateness_s,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Mean: {self.metrics.avg_lateness_s:.1f}s",
            )
            ax.legend()
        else:
            ax.text(
                0.5,
                0.5,
                "No Late Tasks!",
                ha="center",
                va="center",
                fontsize=16,
                fontweight="bold",
                color=self.colors["success"],
            )
        ax.set_xlabel("Lateness (seconds)", fontsize=11)
        ax.set_ylabel("Frequency", fontsize=11)
        ax.set_title("Distribution of Late Tasks", fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="y")

        # 4. SLA summary metrics
        ax = axes[1, 1]
        ax.axis("off")

        # Calculate additional metrics
        n_tasks = self.metrics.tasks_completed
        n_late = int(self.metrics.pct_tasks_late * n_tasks / 100)
        n_on_time = n_tasks - n_late

        summary_data = [
            ["Metric", "Value"],
            ["Total Tasks Completed", f"{n_tasks}"],
            [
                "Tasks On-Time",
                f"{n_on_time} ({100 - self.metrics.pct_tasks_late:.1f}%)",
            ],
            ["Tasks Late", f"{n_late} ({self.metrics.pct_tasks_late:.1f}%)"],
            ["", ""],
            ["Overall Compliance", f"{self.metrics.sla_compliance_rate_overall:.2f}%"],
            [
                "Standard Compliance",
                f"{self.metrics.sla_compliance_rate_standard:.2f}%",
            ],
            ["Express Compliance", f"{self.metrics.sla_compliance_rate_express:.2f}%"],
            ["", ""],
            ["Avg Lateness (late tasks)", f"{self.metrics.avg_lateness_s:.2f}s"],
            ["Max Lateness", f"{self.metrics.max_lateness_s:.2f}s"],
        ]

        table = ax.table(
            cellText=summary_data,
            cellLoc="left",
            colWidths=[0.65, 0.35],
            loc="center",
            bbox=[0.05, 0.1, 0.9, 0.8],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2.2)

        # Style header
        for i in range(2):
            cell = table[(0, i)]
            cell.set_facecolor(self.colors["primary"])
            cell.set_text_props(weight="bold", color="white")

        # Alternate row colors and highlight section breaks
        for i in range(1, len(summary_data)):
            for j in range(2):
                cell = table[(i, j)]
                if summary_data[i][0] == "":
                    cell.set_facecolor("#cccccc")
                elif i % 2 == 0:
                    cell.set_facecolor("#f0f0f0")

        ax.set_title("SLA Performance Summary", fontsize=12, fontweight="bold", pad=20)

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "04_sla_analysis.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

    def create_station_analysis(self):
        """Create station utilization and queue analysis."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(
            "Station Utilization & Queue Analysis", fontsize=16, fontweight="bold"
        )

        times = [s.time_s / 3600 for s in self.metrics.snapshots]

        # 1. Station utilization over time
        ax = axes[0, 0]
        pick_utils = [s.pick_station_utilization for s in self.metrics.snapshots]
        charging_utils = [
            s.charging_station_utilization for s in self.metrics.snapshots
        ]

        ax.plot(
            times,
            pick_utils,
            label="Pick Stations",
            linewidth=2,
            color=self.colors["primary"],
        )
        ax.plot(
            times,
            charging_utils,
            label="Charging Stations",
            linewidth=2,
            color=self.colors["warning"],
        )
        ax.axhline(
            80,
            color="orange",
            linestyle="--",
            linewidth=1.5,
            alpha=0.5,
            label="High Utilization (80%)",
        )
        ax.axhline(
            100, color="red", linestyle="--", linewidth=1.5, alpha=0.5, label="Capacity"
        )
        ax.set_xlabel("Time (hours)", fontsize=11)
        ax.set_ylabel("Utilization (%)", fontsize=11)
        ax.set_title("Station Utilization Over Time", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 110)

        # 2. Queue lengths over time
        ax = axes[0, 1]
        pick_queues = [s.avg_pick_station_queue_length for s in self.metrics.snapshots]
        charging_queues = [
            s.avg_charging_station_queue_length for s in self.metrics.snapshots
        ]

        ax.plot(
            times,
            pick_queues,
            label="Pick Stations",
            linewidth=2,
            color=self.colors["primary"],
            marker="o",
            markersize=3,
        )
        ax.plot(
            times,
            charging_queues,
            label="Charging Stations",
            linewidth=2,
            color=self.colors["warning"],
            marker="s",
            markersize=3,
        )
        ax.set_xlabel("Time (hours)", fontsize=11)
        ax.set_ylabel("Avg Queue Length", fontsize=11)
        ax.set_title("Station Queue Lengths Over Time", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 3. Average utilization comparison
        ax = axes[1, 0]
        station_types = ["Pick\nStations", "Charging\nStations"]
        avg_utils = [
            self.metrics.avg_pick_station_utilization,
            self.metrics.avg_charging_station_utilization,
        ]
        colors = [self.colors["primary"], self.colors["warning"]]

        bars = ax.bar(
            station_types,
            avg_utils,
            color=colors,
            alpha=0.7,
            edgecolor="black",
            linewidth=1.5,
        )
        ax.axhline(
            80,
            color="orange",
            linestyle="--",
            linewidth=1.5,
            label="Target (80%)",
            alpha=0.7,
        )
        ax.set_ylabel("Avg Utilization (%)", fontsize=11)
        ax.set_title("Average Station Utilization", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")
        ax.set_ylim(0, 110)

        # Add value labels
        for b in bars:
            height = b.get_height()
            ax.text(
                b.get_x() + b.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=11,
                fontweight="bold",
            )

        # 4. Queue statistics summary
        ax = axes[1, 1]
        ax.axis("off")

        queue_data = [
            ["Metric", "Pick", "Charging"],
            [
                "Avg Queue Length",
                f"{self.metrics.avg_pick_queue_length:.2f}",
                f"{self.metrics.avg_charging_queue_length:.2f}",
            ],
            [
                "Max Queue Length",
                f"{self.metrics.max_pick_queue_length}",
                f"{self.metrics.max_charging_queue_length}",
            ],
            [
                "Avg Utilization",
                f"{self.metrics.avg_pick_station_utilization:.1f}%",
                f"{self.metrics.avg_charging_station_utilization:.1f}%",
            ],
            [
                "Avg Wait Time",
                f"{self.metrics.avg_wait_time_pick_s:.1f}s",
                f"{self.metrics.avg_wait_time_charging_s:.1f}s",
            ],
        ]

        table = ax.table(
            cellText=queue_data,
            cellLoc="center",
            colWidths=[0.5, 0.25, 0.25],
            loc="center",
            bbox=[0.05, 0.2, 0.9, 0.6],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2.5)

        # Style header
        for i in range(3):
            cell = table[(0, i)]
            cell.set_facecolor(self.colors["primary"])
            cell.set_text_props(weight="bold", color="white")

        # Alternate row colors
        for i in range(1, len(queue_data)):
            for j in range(3):
                cell = table[(i, j)]
                if i % 2 == 0:
                    cell.set_facecolor("#f0f0f0")

        ax.set_title(
            "Station Performance Summary", fontsize=12, fontweight="bold", pad=20
        )

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "05_station_analysis.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

    def create_agv_summary_table(self):
        """Create a comprehensive per-AGV performance summary table."""
        if not self.metrics.agv_summaries:
            return

        # Create DataFrame for easier manipulation
        df = pd.DataFrame(self.metrics.agv_summaries).T
        df = df.sort_values("utilization_pct", ascending=False)

        # Create figure with subplots for table and summary stats
        fig = plt.figure(figsize=(16, 12))
        gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.3)

        fig.suptitle("Per-AGV Performance Summary", fontsize=16, fontweight="bold")

        # Main table
        ax1 = fig.add_subplot(gs[0])
        ax1.axis("off")

        # Prepare table data
        table_data = [
            [
                "AGV ID",
                "Tasks",
                "Distance (m)",
                "Energy",
                "Utilization",
                "Idle (s)",
                "Busy (s)",
                "Charging (s)",
                "Wait (s)",
                "# Charges",
                "Final Battery",
            ]
        ]

        for agv_id, row in df.iterrows():
            table_data.append(
                [
                    agv_id,
                    f"{row['tasks_completed']}",
                    f"{row['distance_m']:.1f}",
                    f"{row['energy_consumed']:.1f}",
                    f"{row['utilization_pct']:.1f}%",
                    f"{row['idle_time_s']:.0f}",
                    f"{row['busy_time_s']:.0f}",
                    f"{row['charging_time_s']:.0f}",
                    f"{row['wait_time_s']:.0f}",
                    f"{row['num_charging_visits']}",
                    f"{row['final_battery_pct']:.1f}%",
                ]
            )

        # Create table
        table = ax1.table(
            cellText=table_data, cellLoc="center", loc="center", bbox=[0, 0, 1, 1]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.5)

        # Style header row
        for i in range(len(table_data[0])):
            cell = table[(0, i)]
            cell.set_facecolor(self.colors["primary"])
            cell.set_text_props(weight="bold", color="white", fontsize=9)

        # Color code utilization column
        util_col_idx = 4
        for i in range(1, len(table_data)):
            util_val = df.iloc[i - 1]["utilization_pct"]
            cell = table[(i, util_col_idx)]
            if util_val >= 80:
                cell.set_facecolor("#90EE90")  # Light green
            elif util_val >= 60:
                cell.set_facecolor("#FFFFE0")  # Light yellow
            else:
                cell.set_facecolor("#FFB6C1")  # Light red

            # Alternate row colors for readability
            if i % 2 == 0:
                for j in range(len(table_data[0])):
                    if j != util_col_idx:
                        table[(i, j)].set_facecolor("#f5f5f5")

        # Summary statistics
        ax2 = fig.add_subplot(gs[1])
        ax2.axis("off")

        summary_text = f"""
        FLEET SUMMARY STATISTICS
        
        Total AGVs: {len(df)}
        
        Utilization:    Mean: {self.metrics.avg_agv_utilization_pct:.1f}%  |  Min: {self.metrics.min_agv_utilization_pct:.1f}%  |  Max: {self.metrics.max_agv_utilization_pct:.1f}%  |  Std: {self.metrics.std_agv_utilization_pct:.1f}%
        
        Tasks/AGV:      Mean: {df["tasks_completed"].mean():.1f}  |  Min: {df["tasks_completed"].min():.0f}  |  Max: {df["tasks_completed"].max():.0f}  |  Std: {df["tasks_completed"].std():.1f}
        
        Distance/AGV:   Mean: {df["distance_m"].mean():.1f}m  |  Min: {df["distance_m"].min():.1f}m  |  Max: {df["distance_m"].max():.1f}m
        
        Energy/AGV:     Mean: {df["energy_consumed"].mean():.1f}  |  Total Fleet: {df["energy_consumed"].sum():.1f}
        
        Charging/AGV:   Mean Visits: {df["num_charging_visits"].mean():.1f}  |  Mean Time: {df["charging_time_s"].mean():.0f}s  |  Total Fleet Time: {df["charging_time_s"].sum():.0f}s
        """

        ax2.text(
            0.05,
            0.5,
            summary_text,
            fontsize=11,
            verticalalignment="center",
            family="monospace",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
        )

        plt.savefig(
            self.output_dir / "06_agv_summary_table.png", dpi=300, bbox_inches="tight"
        )
        plt.close()

    def create_agv_fleet_analysis(self):
        """Create AGV fleet distribution and comparison plots."""
        if not self.metrics.agv_summaries:
            return

        df = pd.DataFrame(self.metrics.agv_summaries).T

        fig, axes = plt.subplots(2, 3, figsize=(16, 10))
        fig.suptitle("AGV Fleet Distribution Analysis", fontsize=16, fontweight="bold")

        # 1. Utilization distribution
        ax = axes[0, 0]
        ax.hist(
            df["utilization_pct"],
            bins=20,
            color=self.colors["primary"],
            alpha=0.7,
            edgecolor="black",
        )
        ax.axvline(
            df["utilization_pct"].mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {df['utilization_pct'].mean():.1f}%",
        )
        ax.set_xlabel("Utilization (%)", fontsize=10)
        ax.set_ylabel("Number of AGVs", fontsize=10)
        ax.set_title("AGV Utilization Distribution", fontsize=11, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 2. Tasks completed distribution
        ax = axes[0, 1]
        ax.hist(
            df["tasks_completed"],
            bins=20,
            color=self.colors["success"],
            alpha=0.7,
            edgecolor="black",
        )
        ax.axvline(
            df["tasks_completed"].mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {df['tasks_completed'].mean():.1f}",
        )
        ax.set_xlabel("Tasks Completed", fontsize=10)
        ax.set_ylabel("Number of AGVs", fontsize=10)
        ax.set_title("Tasks per AGV Distribution", fontsize=11, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 3. Distance traveled distribution
        ax = axes[0, 2]
        ax.hist(
            df["distance_m"],
            bins=20,
            color=self.colors["secondary"],
            alpha=0.7,
            edgecolor="black",
        )
        ax.axvline(
            df["distance_m"].mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {df['distance_m'].mean():.1f}m",
        )
        ax.set_xlabel("Distance (m)", fontsize=10)
        ax.set_ylabel("Number of AGVs", fontsize=10)
        ax.set_title("Distance per AGV Distribution", fontsize=11, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 4. Energy consumed distribution
        ax = axes[1, 0]
        ax.hist(
            df["energy_consumed"],
            bins=20,
            color=self.colors["warning"],
            alpha=0.7,
            edgecolor="black",
        )
        ax.axvline(
            df["energy_consumed"].mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {df['energy_consumed'].mean():.1f}",
        )
        ax.set_xlabel("Energy Consumed", fontsize=10)
        ax.set_ylabel("Number of AGVs", fontsize=10)
        ax.set_title("Energy per AGV Distribution", fontsize=11, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 5. Charging visits distribution
        ax = axes[1, 1]
        ax.hist(
            df["num_charging_visits"],
            bins=15,
            color=self.colors["charging"],
            alpha=0.7,
            edgecolor="black",
        )
        ax.axvline(
            df["num_charging_visits"].mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {df['num_charging_visits'].mean():.1f}",
        )
        ax.set_xlabel("Number of Charging Visits", fontsize=10)
        ax.set_ylabel("Number of AGVs", fontsize=10)
        ax.set_title("Charging Visits per AGV", fontsize=11, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        # 6. Final battery level distribution
        ax = axes[1, 2]
        ax.hist(
            df["final_battery_pct"],
            bins=20,
            color=self.colors["success"],
            alpha=0.7,
            edgecolor="black",
        )
        ax.axvline(
            df["final_battery_pct"].mean(),
            color="red",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {df['final_battery_pct'].mean():.1f}%",
        )
        ax.axvline(
            20,
            color="orange",
            linestyle=":",
            linewidth=2,
            label="Threshold (20%)",
            alpha=0.7,
        )
        ax.set_xlabel("Final Battery Level (%)", fontsize=10)
        ax.set_ylabel("Number of AGVs", fontsize=10)
        ax.set_title("Final Battery Distribution", fontsize=11, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "07_agv_fleet_analysis.png", dpi=300, bbox_inches="tight"
        )
        plt.close()


def generate_visualizations(metrics: SimulationMetrics, output_dir: str = "results"):
    """
    Convenience function to generate all visualizations.

    Args:
        metrics: SimulationMetrics object from completed simulation
        output_dir: Directory to save plots (default: "data/output/results")
    """

    visualizer = SimulationVisualizer(metrics, output_dir)
    visualizer.generate_all_plots()
    return visualizer
