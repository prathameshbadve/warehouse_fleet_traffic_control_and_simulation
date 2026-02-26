"""
Quick-run script for the AGV fleet simulator.
---------------------------------------------
Usage:
    python run_simulation.py
    python run_simulation.py --n-agvs 80 --hours 2
    python run_simulation.py --config config/default_warehouse.yaml
"""

import argparse
from pathlib import Path

from src.warehouse.config import WarehouseConfig, SimulationConfig, load_config
from src.simulation.engine import SimulationEngine
from src.simulation.agvs import TeleportStrategy


def main():
    """Main"""

    parser = argparse.ArgumentParser(description="Run AGV fleet simulation")

    parser.add_argument(
        "--config",
        type=str,
        default="config/default_warehouse.yaml",
        help="Path to warehouse config YAML",
    )
    parser.add_argument(
        "--n-agvs", type=int, default=50, help="Number of AGVs to deploy"
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=4.0,
        help="Simulation duration in hours (overrides config)",
    )
    parser.add_argument(
        "--seed", type=int, default=73, help="Random seed (overrides config)"
    )
    args = parser.parse_args()

    print(args)

    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        config = load_config(config_path)
        print(f"Loaded config from {config_path}")
    else:
        print(f"Config {config_path} not found, using defaults")
        config = WarehouseConfig()

    # Apply CLI overrides
    if args.hours is not None or args.seed is not None:
        sim_kwargs = {
            "duration_hours": args.hours or config.simulation.duration_hours,
            "dispatch_interval_s": config.simulation.dispatch_interval_s,
            "metrics_interval_s": config.simulation.metrics_interval_s,
            "random_seed": args.seed
            if args.seed is not None
            else config.simulation.random_seed,
        }
        config = WarehouseConfig(
            layout=config.layout,
            agv=config.agv,
            tasks=config.tasks,
            simulation=SimulationConfig(**sim_kwargs),
        )

    # Run
    engine = SimulationEngine(
        config,
        n_agvs=args.n_agvs,
        movement_strategy=TeleportStrategy,
        # assignment_strategy=args.strategy,
    )
    engine.run()


if __name__ == "__main__":
    main()
