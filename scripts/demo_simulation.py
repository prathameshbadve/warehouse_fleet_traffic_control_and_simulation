"""
Demo Script: Enhanced Warehouse Simulation with Phase 1 Metrics

This script demonstrates:
1. Running a single simulation with comprehensive metrics
2. Running multiple scenarios for comparison
3. Generating professional-grade visualizations

Usage:
    python demo_enhanced_simulation.py --single
    python demo_enhanced_simulation.py --compare
    python demo_enhanced_simulation.py --full
"""

import argparse
from pathlib import Path
import sys

# Add paths
cwd = Path.cwd()
parent_dir = cwd.parent
for parent in [cwd] + list(cwd.parents):
    if (parent / "pyproject.toml").exists():
        parent_dir = parent

# Add to Python path if not already there
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# pylint: disable=wrong-import-position
from src.warehouse.config import WarehouseConfig, load_config  # noqa: E402
from src.simulation.agvs import TeleportStrategy  # noqa: E402
from src.simulation.engine import SimulationEngine  # noqa: E402
from src.warehouse.config import TaskConfig  # noqa: E402


def run_single_simulation():
    """
    Run a single simulation with default configuration.
    Demonstrates basic usage of the enhanced engine.
    """
    print("\n" + "=" * 80)
    print("DEMO: SINGLE SIMULATION RUN")
    print("=" * 80 + "\n")

    # Load configuration
    config_path = parent_dir / "config" / "default_warehouse_config.yaml"
    if config_path.exists():
        config = load_config(config_path)
        print(f"✓ Loaded configuration from: {config_path}")
    else:
        config = WarehouseConfig()
        print("✓ Using default configuration")

    # Create and run simulation
    engine = SimulationEngine(
        warehouse_config=config,
        n_agvs=10,
        movement_strategy=TeleportStrategy,
        output_dir="data/output/results/demo",
        run_name="demo_single_run",
    )

    metrics = engine.run(gen_vis=True)
    engine.save_metrics_summary()

    print("\n" + "=" * 80)
    print("✓ SINGLE SIMULATION COMPLETE")
    print(f"✓ Results saved to: {engine.run_output_dir}")
    print("=" * 80 + "\n")

    return metrics


def run_fleet_size_comparison():
    """
    Run multiple simulations comparing different fleet sizes.
    Demonstrates multi-scenario analysis capabilities.
    """
    print("\n" + "=" * 80)
    print("DEMO: FLEET SIZE COMPARISON")
    print("=" * 80 + "\n")

    # Load base configuration
    config_path = parent_dir / "config" / "default_warehouse_config.yaml"
    if config_path.exists():
        config = load_config(config_path)
    else:
        config = WarehouseConfig()

    # Fleet sizes to compare
    fleet_sizes = [5, 10, 12, 15, 20]
    results = {}

    print(f"Running {len(fleet_sizes)} scenarios with fleet sizes: {fleet_sizes}\n")

    for n_agvs in fleet_sizes:
        print(f"\n{'=' * 80}")
        print(f"SCENARIO: {n_agvs} AGVs")
        print(f"{'=' * 80}\n")

        engine = SimulationEngine(
            warehouse_config=config,
            n_agvs=n_agvs,
            movement_strategy=TeleportStrategy,
            output_dir="data/output/results/demo/comparison",
            run_name=f"fleet_{n_agvs}agvs",
        )

        metrics = engine.run(gen_vis=True)
        engine.save_metrics_summary()

        results[n_agvs] = {"metrics": metrics, "output_dir": engine.run_output_dir}

    # Print comparison summary
    print("\n" + "=" * 80)
    print("FLEET SIZE COMPARISON SUMMARY")
    print("=" * 80 + "\n")

    print(
        f"{'Fleet Size':<12} {'Throughput':<15} {'Avg Cycle':<15} {'SLA Comp.':<15} {'AGV Util.':<15}"
    )
    print("-" * 80)

    for n_agvs in fleet_sizes:
        m = results[n_agvs]["metrics"]
        print(
            f"{n_agvs:<12} "
            f"{m.avg_throughput_per_hour:<15.2f} "
            f"{m.avg_cycle_time_s:<15.2f} "
            f"{m.sla_compliance_rate_overall:<15.2f} "
            f"{m.avg_agv_utilization_pct:<15.2f}"
        )

    print("\n" + "=" * 80)
    print("✓ FLEET SIZE COMPARISON COMPLETE")
    print("✓ Individual results saved to: results/comparison/")
    print("=" * 80 + "\n")

    return results


def run_workload_comparison():
    """
    Run multiple simulations comparing different workload intensities.
    """
    print("\n" + "=" * 80)
    print("DEMO: WORKLOAD INTENSITY COMPARISON")
    print("=" * 80 + "\n")

    # Load base configuration
    config_path = parent_dir / "config" / "default_warehouse_config.yaml"
    if config_path.exists():
        base_config = load_config(config_path)
    else:
        base_config = WarehouseConfig()

    # Workload scenarios: low, medium, high task arrival rates
    workload_scenarios = [("low", 6.0), ("medium", 8.0), ("high", 10.0)]
    results = {}

    print(f"Running {len(workload_scenarios)} workload scenarios\n")

    for scenario_name, task_rate in workload_scenarios:
        print(f"\n{'=' * 80}")
        print(f"SCENARIO: {scenario_name.upper()} workload ({task_rate} tasks/min)")
        print(f"{'=' * 80}\n")

        # Create modified config with different task rate
        config = WarehouseConfig(
            layout=base_config.layout,
            agv=base_config.agv,
            tasks=TaskConfig(
                task_arrival_base_rate_per_min=task_rate,
                express_fraction=base_config.tasks.express_fraction,
                standard_sla_deadline_s=base_config.tasks.standard_sla_deadline_s,
                express_sla_deadline_s=base_config.tasks.express_sla_deadline_s,
            ),
            stations=base_config.stations,
            simulation=base_config.simulation,
        )

        engine = SimulationEngine(
            warehouse_config=config,
            n_agvs=13,
            movement_strategy=TeleportStrategy,
            output_dir="data/output/results/demo/workload_comparison",
            run_name=f"workload_{scenario_name}",
        )

        metrics = engine.run(gen_vis=True)
        engine.save_metrics_summary()

        results[scenario_name] = {
            "task_rate": task_rate,
            "metrics": metrics,
            "output_dir": engine.run_output_dir,
        }

    # Print comparison summary
    print("\n" + "=" * 80)
    print("WORKLOAD COMPARISON SUMMARY")
    print("=" * 80 + "\n")

    print(
        f"{'Workload':<12} {'Rate':<12} {'Throughput':<15} {'Avg Cycle':<15} {'SLA Comp.':<15} {'AGV Util.':<15}"
    )
    print("-" * 90)

    for scenario_name, task_rate in workload_scenarios:
        m = results[scenario_name]["metrics"]
        print(
            f"{scenario_name:<12} "
            f"{task_rate:<12.1f} "
            f"{m.avg_throughput_per_hour:<15.2f} "
            f"{m.avg_cycle_time_s:<15.2f} "
            f"{m.sla_compliance_rate_overall:<15.2f} "
            f"{m.avg_agv_utilization_pct:<15.2f}"
        )

    print("\n" + "=" * 80)
    print("✓ WORKLOAD COMPARISON COMPLETE")
    print("✓ Individual results saved to: results/workload_comparison/")
    print("=" * 80 + "\n")

    return results


def main():
    """Main entry point with command-line argument handling."""
    parser = argparse.ArgumentParser(
        description="Demo: Enhanced Warehouse Simulation with Phase 1 Metrics"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["single", "fleet", "workload", "full"],
        default="single",
        help="Simulation mode: single run, fleet comparison, workload comparison, or full demo",
    )

    args = parser.parse_args()

    if args.mode == "single":
        run_single_simulation()

    elif args.mode == "fleet":
        run_fleet_size_comparison()

    elif args.mode == "workload":
        run_workload_comparison()

    elif args.mode == "full":
        print("\n" + "=" * 80)
        print("RUNNING FULL DEMO: ALL SCENARIOS")
        print("=" * 80 + "\n")

        print("Part 1: Single simulation demonstration")
        run_single_simulation()

        print("\n" + "=" * 80 + "\n")
        print("Part 2: Fleet size comparison")
        run_fleet_size_comparison()

        print("\n" + "=" * 80 + "\n")
        print("Part 3: Workload intensity comparison")
        run_workload_comparison()

        print("\n" + "=" * 80)
        print("✓ FULL DEMO COMPLETE")
        print("✓ All results saved to: results/")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    # For direct execution without args
    parent_dir = (
        Path(__file__).parent.parent
        if hasattr(Path(__file__), "parent")
        else Path.cwd()
    )
    main()
