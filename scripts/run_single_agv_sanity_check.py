"""
Single-AGV sanity-check runner for charging and waiting behavior.

Examples:
    python scripts/run_single_agv_sanity_check.py
    python scripts/run_single_agv_sanity_check.py --num-tasks 6 --inter-arrival-seconds 20
    python scripts/run_single_agv_sanity_check.py --inter-arrival-sequence "10,40,10,60"
    python scripts/run_single_agv_sanity_check.py --initial-battery 25 --battery-threshold 30
    python scripts/run_single_agv_sanity_check.py --block-charging-station-hold-seconds 300
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
from typing import List

import numpy as np
import simpy


# Get the project root (where pyproject.toml is located)
cwd = Path.cwd()
project_root = cwd
for parent in [cwd] + list(cwd.parents):
    if (parent / "pyproject.toml").exists():
        project_root = parent
        break

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# pylint: disable=wrong-import-position
from src.simulation.agvs import AGV, AGVStatus, TeleportStrategy
from src.simulation.metrics import MetricsCollector
from src.simulation.stations import (
    initialize_charging_station_resources,
    initialize_pick_station_resources,
)
from src.simulation.tasks import Task, TaskGenerator, TaskPriority, TaskStatus
from src.warehouse.config import WarehouseConfig, load_config
from src.warehouse.graph import NodeType, WarehouseGraph
from src.warehouse.layout import GridLayoutGenerator
# pylint: enable=wrong-import-position


class ControlledTaskGenerator(TaskGenerator):
    """
    Finite task generator with user-controlled inter-arrival process.

    If an explicit sequence is provided, it is interpreted as inter-arrival
    times *between* consecutive tasks and therefore must have length N-1.
    """

    def __init__(
        self,
        env: simpy.Environment,
        rng: np.random.Generator,
        warehouse: WarehouseGraph,
        config,
        n_tasks: int,
        inter_arrival_mode: str,
        inter_arrival_s: float,
        inter_arrival_sequence: List[float] | None = None,
        start_delay_s: float = 0.0,
        fixed_storage_node: str | None = None,
        fixed_pick_node: str | None = None,
    ):
        super().__init__(env=env, rng=rng, warehouse=warehouse, config=config)
        self.n_tasks = n_tasks
        self.inter_arrival_mode = inter_arrival_mode
        self.inter_arrival_s = inter_arrival_s
        self.inter_arrival_sequence = inter_arrival_sequence
        self.start_delay_s = start_delay_s
        self.fixed_storage_node = fixed_storage_node
        self.fixed_pick_node = fixed_pick_node
        self.finished_generating = False

        if self.n_tasks < 0:
            raise ValueError("n_tasks must be >= 0")
        if self.inter_arrival_mode not in {"fixed", "exponential"}:
            raise ValueError("inter_arrival_mode must be one of: fixed, exponential")
        if self.inter_arrival_s < 0:
            raise ValueError("inter_arrival_s must be >= 0")
        if self.start_delay_s < 0:
            raise ValueError("start_delay_s must be >= 0")
        if self.inter_arrival_sequence is not None:
            required = max(self.n_tasks - 1, 0)
            if len(self.inter_arrival_sequence) != required:
                raise ValueError(
                    "inter_arrival_sequence length must equal num_tasks - 1 "
                    f"(expected {required}, got {len(self.inter_arrival_sequence)})"
                )
            if any(x < 0 for x in self.inter_arrival_sequence):
                raise ValueError("inter_arrival_sequence values must be >= 0")

    def _create_task(self, creation_time: float) -> Task:
        """
        Create a task, optionally pinning storage/pick nodes for repeatable traces.
        """
        self._task_counter += 1
        task_id = f"TSK_{self._task_counter:05d}"

        is_express = self.rng.random() < self.config.express_fraction
        priority = TaskPriority.EXPRESS if is_express else TaskPriority.STANDARD

        storage_nodes = self._get_storage_nodes()
        if self.fixed_storage_node is not None:
            if self.fixed_storage_node not in storage_nodes:
                raise ValueError(
                    f"fixed_storage_node={self.fixed_storage_node} is not a storage node"
                )
            pod_location = self.fixed_storage_node
        else:
            pod_location = self.rng.choice(storage_nodes)

        pick_station_nodes = self._get_pick_station_nodes()
        if self.fixed_pick_node is not None:
            if self.fixed_pick_node not in pick_station_nodes:
                raise ValueError(
                    f"fixed_pick_node={self.fixed_pick_node} is not a pick station node"
                )
            picking_location = self.fixed_pick_node
        else:
            picking_location = self.rng.choice(pick_station_nodes)

        task = Task(
            id=task_id,
            pod_location=pod_location,
            picking_location=picking_location,
            priority=priority,
            release_time=creation_time,
        )
        self.tasks.append(task)
        self.pending_tasks.append(task)
        return task

    def _sample_gap(self, idx: int) -> float:
        """Sample/lookup inter-arrival gap before task idx (idx > 0)."""
        if self.inter_arrival_sequence is not None:
            return self.inter_arrival_sequence[idx - 1]
        if self.inter_arrival_mode == "fixed":
            return self.inter_arrival_s
        return self.rng.exponential(self.inter_arrival_s)

    def run(self):
        """Generate exactly n_tasks and then stop."""
        if self.start_delay_s > 0:
            yield self.env.timeout(self.start_delay_s)

        for idx in range(self.n_tasks):
            if idx > 0:
                yield self.env.timeout(self._sample_gap(idx))
            self._create_task(self.env.now)

        self.finished_generating = True


def _dispatcher_process(
    env: simpy.Environment,
    agv: AGV,
    task_gen: ControlledTaskGenerator,
    dispatch_interval_s: float,
):
    """Assign pending tasks to the single AGV whenever it is idle."""
    while True:
        pending_tasks = task_gen.get_and_clear_pending()
        if pending_tasks:
            agv_is_idle = (
                agv.state.status == AGVStatus.IDLE and agv.state.current_task is None
            )
            if agv_is_idle:
                chosen_task = pending_tasks.pop(0)
                agv.assign_task(chosen_task)

            if pending_tasks:
                task_gen.pending_tasks.extend(pending_tasks)

        done = (
            task_gen.finished_generating
            and not task_gen.pending_tasks
            and agv.state.current_task is None
            and agv.state.status == AGVStatus.IDLE
        )
        if done:
            return

        yield env.timeout(dispatch_interval_s)


def _completion_monitor(
    env: simpy.Environment,
    agv: AGV,
    task_gen: ControlledTaskGenerator,
    poll_interval_s: float = 0.5,
):
    """Terminate when generation is finished and all tasks are complete/failed."""
    terminal_statuses = {TaskStatus.COMPLETE, TaskStatus.FAILED}
    while True:
        all_terminal = all(t.status in terminal_statuses for t in task_gen.tasks)
        done = (
            task_gen.finished_generating
            and all_terminal
            and not task_gen.pending_tasks
            and agv.state.current_task is None
            and agv.state.status == AGVStatus.IDLE
        )
        if done:
            return
        yield env.timeout(poll_interval_s)


def _block_resource(
    env: simpy.Environment,
    resource: simpy.Resource,
    resource_id: str,
    hold_seconds: float,
    start_seconds: float,
):
    """Optionally occupy a station resource to force AGV waiting behavior."""
    if hold_seconds <= 0:
        return
    if start_seconds > 0:
        yield env.timeout(start_seconds)
    with resource.request() as req:
        yield req
        print(
            f"[{env.now:8.2f}s] Blocking resource {resource_id} for {hold_seconds:.1f}s"
        )
        yield env.timeout(hold_seconds)
    print(f"[{env.now:8.2f}s] Released blocker on resource {resource_id}")


def _parse_inter_arrival_sequence(raw: str | None) -> List[float] | None:
    """Parse comma-separated float list into a sequence."""
    if raw is None or raw.strip() == "":
        return None
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def _build_overridden_config(base: WarehouseConfig, args: argparse.Namespace):
    """Apply CLI overrides to AGV/station/simulation config values."""
    agv = replace(
        base.agv,
        init_battery_capacity=args.initial_battery,
        battery_threshold=args.battery_threshold,
        battery_charge_rate=args.battery_charge_rate,
        battery_drain_without_pod_per_meter=args.battery_drain_without_pod_per_meter,
        battery_drain_with_pod_per_meter=args.battery_drain_with_pod_per_meter,
        battery_drain_per_storage_retrieval=args.battery_drain_per_storage_retrieval,
    )
    tasks = replace(base.tasks, express_fraction=args.express_fraction)
    stations = replace(
        base.stations,
        pick_station_capacity=args.pick_station_capacity,
        charging_station_capacity=args.charging_station_capacity,
    )
    simulation = replace(
        base.simulation,
        dispatch_interval_s=args.dispatch_interval_seconds,
        metrics_interval_s=args.metrics_interval_seconds,
        random_seed=args.seed,
    )
    return WarehouseConfig(
        layout=base.layout,
        agv=agv,
        tasks=tasks,
        stations=stations,
        simulation=simulation,
    )


def _format_or_na(value: float | None) -> str:
    return "NA" if value is None else f"{value:.2f}"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Single AGV sanity-check simulation with controlled task arrivals."
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/default_warehouse_config.yaml",
        help="Path to warehouse config YAML.",
    )
    parser.add_argument("--seed", type=int, default=73, help="Random seed.")

    parser.add_argument(
        "--num-tasks",
        type=int,
        default=8,
        help="Exact number of tasks to generate.",
    )
    parser.add_argument(
        "--start-delay-seconds",
        type=float,
        default=0.0,
        help="Delay before generating the first task.",
    )
    parser.add_argument(
        "--inter-arrival-mode",
        choices=["fixed", "exponential"],
        default="fixed",
        help="Inter-arrival process used when sequence is not provided.",
    )
    parser.add_argument(
        "--inter-arrival-seconds",
        type=float,
        default=30.0,
        help="Fixed gap or exponential mean for gaps between tasks.",
    )
    parser.add_argument(
        "--inter-arrival-sequence",
        type=str,
        default=None,
        help='Comma-separated gaps between tasks, e.g. "10,25,10". Must be N-1 values.',
    )

    parser.add_argument(
        "--dispatch-interval-seconds",
        type=float,
        default=1.0,
        help="Dispatcher polling interval in seconds.",
    )
    parser.add_argument(
        "--metrics-interval-seconds",
        type=float,
        default=10.0,
        help="Metrics snapshot interval in seconds.",
    )
    parser.add_argument(
        "--max-sim-seconds",
        type=float,
        default=7200.0,
        help="Safety timeout for the simulation run.",
    )

    parser.add_argument(
        "--initial-battery",
        type=float,
        default=35.0,
        help="Initial battery SOC (%) for the AGV.",
    )
    parser.add_argument(
        "--battery-threshold",
        type=float,
        default=30.0,
        help="Battery threshold (%) below which AGV triggers charging.",
    )
    parser.add_argument(
        "--battery-charge-rate",
        type=float,
        default=0.6,
        help="Charge rate in %% per second.",
    )
    parser.add_argument(
        "--battery-drain-without-pod-per-meter",
        type=float,
        default=0.12,
        help="Battery drain per meter while moving without pod.",
    )
    parser.add_argument(
        "--battery-drain-with-pod-per-meter",
        type=float,
        default=0.16,
        help="Battery drain per meter while moving with pod.",
    )
    parser.add_argument(
        "--battery-drain-per-storage-retrieval",
        type=float,
        default=0.8,
        help="Battery drain per storage retrieval/storage operation.",
    )
    parser.add_argument(
        "--express-fraction",
        type=float,
        default=0.0,
        help="Express task fraction (0 to 1).",
    )

    parser.add_argument(
        "--pick-station-capacity",
        type=int,
        default=1,
        help="Capacity of each pick station resource.",
    )
    parser.add_argument(
        "--charging-station-capacity",
        type=int,
        default=1,
        help="Capacity of each charging station resource.",
    )

    parser.add_argument(
        "--agv-start-node",
        type=str,
        default=None,
        help="Optional AGV starting node (defaults to first parking node).",
    )
    parser.add_argument(
        "--fixed-storage-node",
        type=str,
        default=None,
        help="Optional fixed storage node for all tasks.",
    )
    parser.add_argument(
        "--fixed-pick-node",
        type=str,
        default=None,
        help="Optional fixed pick station node for all tasks.",
    )

    parser.add_argument(
        "--block-pick-station-id",
        type=str,
        default=None,
        help="Pick station id to block temporarily.",
    )
    parser.add_argument(
        "--block-pick-station-start-seconds",
        type=float,
        default=0.0,
        help="Start time for temporary pick-station block.",
    )
    parser.add_argument(
        "--block-pick-station-hold-seconds",
        type=float,
        default=0.0,
        help="How long to hold the pick-station block.",
    )
    parser.add_argument(
        "--block-all-pick-stations",
        action="store_true",
        help="Block all pick stations instead of a single station id.",
    )
    parser.add_argument(
        "--block-charging-station-id",
        type=str,
        default=None,
        help="Charging station id to block temporarily.",
    )
    parser.add_argument(
        "--block-charging-station-start-seconds",
        type=float,
        default=0.0,
        help="Start time for temporary charging-station block.",
    )
    parser.add_argument(
        "--block-charging-station-hold-seconds",
        type=float,
        default=0.0,
        help="How long to hold the charging-station block.",
    )
    parser.add_argument(
        "--block-all-charging-stations",
        action="store_true",
        help="Block all charging stations instead of a single station id.",
    )

    args = parser.parse_args()

    inter_arrival_sequence = _parse_inter_arrival_sequence(args.inter_arrival_sequence)

    config_path = Path(args.config)
    if config_path.exists():
        base_config = load_config(config_path)
        print(f"Loaded config from {config_path}")
    else:
        print(f"Config {config_path} not found. Using default WarehouseConfig.")
        base_config = WarehouseConfig()

    config = _build_overridden_config(base_config, args)

    env = simpy.Environment()
    rng = np.random.default_rng(config.simulation.random_seed)

    warehouse = GridLayoutGenerator(config).generate()
    validation_issues = warehouse.validate()
    if validation_issues:
        print("Warehouse validation issues:")
        for issue in validation_issues:
            print(f"  - {issue}")

    pick_stations = warehouse.nodes_by_type(NodeType.PICK_STATION)
    charging_stations = warehouse.nodes_by_type(NodeType.CHARGING)
    parking_nodes = warehouse.nodes_by_type(NodeType.PARKING)

    pick_station_resources = initialize_pick_station_resources(
        env, pick_stations, config.stations.pick_station_capacity
    )
    charging_station_resources = initialize_charging_station_resources(
        env, charging_stations, config.stations.charging_station_capacity
    )

    agv_start = args.agv_start_node or parking_nodes[0]
    if agv_start not in warehouse.graph.nodes:
        raise ValueError(f"agv-start-node {agv_start} is not a valid warehouse node")

    agv = AGV(
        agv_id="AGV_SANITY_001",
        start_position=agv_start,
        env=env,
        config=config.agv,
        warehouse=warehouse,
        rng=rng,
        movement_strategy=TeleportStrategy,
        pick_station_resources=pick_station_resources,
        charging_station_resources=charging_station_resources,
    )
    env.process(agv.run())

    task_gen = ControlledTaskGenerator(
        env=env,
        rng=rng,
        warehouse=warehouse,
        config=config.tasks,
        n_tasks=args.num_tasks,
        inter_arrival_mode=args.inter_arrival_mode,
        inter_arrival_s=args.inter_arrival_seconds,
        inter_arrival_sequence=inter_arrival_sequence,
        start_delay_s=args.start_delay_seconds,
        fixed_storage_node=args.fixed_storage_node,
        fixed_pick_node=args.fixed_pick_node,
    )
    env.process(task_gen.run())
    env.process(
        _dispatcher_process(
            env=env,
            agv=agv,
            task_gen=task_gen,
            dispatch_interval_s=config.simulation.dispatch_interval_s,
        )
    )

    collector = MetricsCollector(
        env=env,
        agvs=[agv],
        task_generator=task_gen,
        warehouse_config=config,
        interval_s=config.simulation.metrics_interval_s,
    )
    env.process(collector.run())

    if args.block_pick_station_hold_seconds > 0:
        if args.block_all_pick_stations:
            for station_id, resource in pick_station_resources.items():
                env.process(
                    _block_resource(
                        env=env,
                        resource=resource,
                        resource_id=station_id,
                        hold_seconds=args.block_pick_station_hold_seconds,
                        start_seconds=args.block_pick_station_start_seconds,
                    )
                )
        else:
            blocked_pick = args.block_pick_station_id or pick_stations[0]
            if blocked_pick not in pick_station_resources:
                raise ValueError(f"Invalid block-pick-station-id: {blocked_pick}")
            env.process(
                _block_resource(
                    env=env,
                    resource=pick_station_resources[blocked_pick],
                    resource_id=blocked_pick,
                    hold_seconds=args.block_pick_station_hold_seconds,
                    start_seconds=args.block_pick_station_start_seconds,
                )
            )

    if args.block_charging_station_hold_seconds > 0:
        if args.block_all_charging_stations:
            for station_id, resource in charging_station_resources.items():
                env.process(
                    _block_resource(
                        env=env,
                        resource=resource,
                        resource_id=station_id,
                        hold_seconds=args.block_charging_station_hold_seconds,
                        start_seconds=args.block_charging_station_start_seconds,
                    )
                )
        else:
            blocked_charging = args.block_charging_station_id or charging_stations[0]
            if blocked_charging not in charging_station_resources:
                raise ValueError(
                    f"Invalid block-charging-station-id: {blocked_charging}"
                )
            env.process(
                _block_resource(
                    env=env,
                    resource=charging_station_resources[blocked_charging],
                    resource_id=blocked_charging,
                    hold_seconds=args.block_charging_station_hold_seconds,
                    start_seconds=args.block_charging_station_start_seconds,
                )
            )

    completion_event = env.process(_completion_monitor(env=env, agv=agv, task_gen=task_gen))
    timeout_event = env.timeout(args.max_sim_seconds)
    env.run(until=(completion_event | timeout_event))

    timed_out = not completion_event.triggered
    final_metrics = collector.compute_final_metrics()
    agv_summary = final_metrics.agv_summaries.get(agv.id, {})

    print("\n================= SANITY CHECK SUMMARY =================")
    if timed_out:
        print(
            f"Simulation hit timeout at t={env.now:.2f}s "
            f"(max-sim-seconds={args.max_sim_seconds:.2f})."
        )
    else:
        print(f"Simulation completed all tasks at t={env.now:.2f}s.")

    print(f"Tasks requested:  {args.num_tasks}")
    print(f"Tasks generated:  {final_metrics.tasks_generated}")
    print(f"Tasks completed:  {final_metrics.tasks_completed}")
    print(f"Tasks pending:    {len(task_gen.pending_tasks)}")
    print(f"AGV waits (s):    {agv.metrics.waiting_time_s:.2f}")
    print(f"AGV charging (s): {agv.metrics.charging_time_s:.2f}")
    print(f"Charging visits:  {agv.metrics.num_charging_visits}")
    print(f"Final battery %:  {agv_summary.get('final_battery_pct', agv.state.battery_soc.level):.2f}")

    print("\nPer-task timings (seconds):")
    print(
        "task_id      release   assigned  completed  queue_wait  exec_time  cycle_time  status"
    )
    for task in task_gen.tasks:
        release_t = task.release_time
        assigned_t = task.assigned_time
        complete_t = task.complete_time
        queue_wait = (
            assigned_t - release_t
            if assigned_t is not None and release_t is not None
            else None
        )
        exec_time = (
            complete_t - assigned_t
            if complete_t is not None and assigned_t is not None
            else None
        )
        cycle_time = (
            complete_t - release_t
            if complete_t is not None and release_t is not None
            else None
        )
        print(
            f"{task.id:<12} {_format_or_na(release_t):>8} "
            f"{_format_or_na(assigned_t):>9} {_format_or_na(complete_t):>9} "
            f"{_format_or_na(queue_wait):>10} {_format_or_na(exec_time):>10} "
            f"{_format_or_na(cycle_time):>11}  {task.status.value}"
        )

    print("\nAGV status transition log:")
    print("time_s     status")
    for ts, status in agv.metrics.status_log:
        print(f"{ts:8.2f}   {status.value}")


if __name__ == "__main__":
    main()
