"""
Simulation Metrics Collector Object
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

import numpy as np
import simpy

from src.warehouse.config import WarehouseConfig
from src.simulation.agvs import AGV, AGVStatus
from src.simulation.tasks import TaskGenerator, TaskStatus


@dataclass
class Snapshot:
    """A point-in-time snapshot of system state."""

    time_s: float  # Time of snapshot in seconds
    tasks_completed: int  # Count of tasks completed till this time
    tasks_pending: int  # Count of tasks pending at this time
    tasks_failed: int  # Count of tasks failed at this time
    throughput_per_hour: float  # Number of tasks completed per hour by this time
    avg_cycle_time_s: float  # Average cycle time of completed tasks till this time
    agv_utilization_pct: float  # Average utilization of AGVs at this time (0-100%)
    n_agvs_idle: int  # Number of idle AGVs at this time
    n_agvs_working: int  # Number of AGVs currently working (moving, retrieving, storing, picking) at this time
    n_agvs_charging: int  # Number of AGVs currently charging at this time
    n_agvs_waiting: (
        int  # Number of AGVs currently waiting (e.g., at a station) at this time
    )
    station_queue_lengths: dict[str, int]  # station_id → queue length


@dataclass
class SimulationMetrics:
    """Contains all top level simulation metrics"""

    # Time-series
    snapshots: list[Snapshot] = field(default_factory=list)

    total_simulation_time_s: float = 0.0
    tasks_generated: int = 0
    tasks_completed: int = 0

    avg_throughput_per_hour: float = 0.0
    avg_cycle_time_s: float = 0.0
    median_cycle_time_s: float = 0.0
    p95_cycle_time_s: float = 0.0
    avg_agv_utilization_pct: float = 0.0
    avg_station_utilization_pct: float = 0.0
    total_distance_travelled_m: float = 0.0

    # Per-AGV summaries
    agv_summaries: dict[str, dict] = field(default_factory=dict)


class MetricsCollector:
    """
    SimPy process that periodically snapshots the system state and computes final KPIs.
    """

    def __init__(
        self,
        env: simpy.Environment,
        agvs: List[AGV],
        task_generator: TaskGenerator,
        warehouse_config: WarehouseConfig,
        interval_s: float = 60.0,
    ):
        self.env = env
        self.agvs = agvs
        self.task_generator = task_generator
        self.warehouse_config = warehouse_config
        self.interval_s = interval_s
        self.metrics = SimulationMetrics()

        self._snapshots: List[Snapshot] = []

    def run(self):
        """
        SimPy generator: takes snapshot at regular intervals until the simulation ends.
        """

        while True:
            yield self.env.timeout(self.interval_s)
            snapshot = self._take_snapshot()
            self.metrics.snapshots.append(snapshot)

    def _take_snapshot(self) -> Snapshot:
        """
        Capture current system state and return a Snapshot object.
        """

        now = self.env.now

        # Count completed tasks
        completed_tasks = [
            t for t in self.task_generator.tasks if t.status == TaskStatus.COMPLETE
        ]
        pending_tasks = [
            t
            for t in self.task_generator.tasks
            if t.status not in [TaskStatus.COMPLETE, TaskStatus.FAILED]
        ]
        failed_tasks = [
            t for t in self.task_generator.tasks if t.status == TaskStatus.FAILED
        ]

        n_completed = len(completed_tasks)
        n_pending = len(pending_tasks)
        n_failed = len(failed_tasks)

        # Throughput: tasks completed so far / elapsed hours
        elapsed_hours = now / 3600.0
        throughput = n_completed / elapsed_hours if elapsed_hours > 0 else 0.0

        # Average cycle time of completed tasks
        cycle_times = [
            (t.complete_time - t.release_time)
            for t in completed_tasks
            if t.complete_time is not None
        ]
        avg_cycle = float(np.mean(cycle_times)) if cycle_times else 0.0

        # AGV states
        idle_states = {AGVStatus.IDLE}
        working_states = {
            AGVStatus.MOVING,
            AGVStatus.RETRIEVING,
            AGVStatus.PICKING,
            AGVStatus.STORING,
        }
        charging_states = {AGVStatus.CHARGING}
        waiting_states = {AGVStatus.WAITING}

        n_idle = sum(1 for a in self.agvs if a.state.status in idle_states)
        n_working = sum(1 for a in self.agvs if a.state.status in working_states)
        n_charging = sum(1 for a in self.agvs if a.state.status in charging_states)
        n_waiting = sum(1 for a in self.agvs if a.state.status in waiting_states)

        # AGV utilization: % of AGVs not idle and not charging
        n_active = len(self.agvs) - n_idle - n_charging
        utilization = (n_active / len(self.agvs) * 100) if self.agvs else 0.0

        # Station queue lengths
        station_queues = {}
        # To do: Implement simpy resources at picking, charging and wariting stations.
        # for station_id, resource in self.pick_stations.items():
        #     station_queues[station_id] = len(resource.queue) + len(resource.users)

        return Snapshot(
            time_s=now,
            tasks_completed=n_completed,
            tasks_pending=n_pending,
            tasks_failed=n_failed,
            throughput_per_hour=throughput,
            avg_cycle_time_s=avg_cycle,
            agv_utilization_pct=utilization,
            n_agvs_idle=n_idle,
            n_agvs_working=n_working,
            n_agvs_charging=n_charging,
            n_agvs_waiting=n_waiting,
            station_queue_lengths=station_queues,
        )

    def compute_final_metrics(self):
        """
        Compute summary statistics after the simulation completes.

        Returns:
            SimulationMetrics with both time-series snapshots and summary stats.
        """

        # Order-level stats
        all_tasks = self.task_generator.tasks
        completed = [t for t in all_tasks if t.status == TaskStatus.COMPLETE]
        cycle_times = [
            t.metrics.cycle_time_s
            for t in completed
            if t.metrics.cycle_time_s is not None
        ]

        self.metrics.tasks_generated = len(all_tasks)
        self.metrics.tasks_completed = len(completed)
        self.metrics.total_simulation_time_s = self.env.now

        elapsed_hours = self.env.now / 3600.0
        self.metrics.avg_throughput_per_hour = (
            len(completed) / elapsed_hours if elapsed_hours > 0 else 0.0
        )

        if cycle_times:
            self.metrics.avg_cycle_time_s = float(np.mean(cycle_times))
            self.metrics.median_cycle_time_s = float(np.median(cycle_times))
            self.metrics.p95_cycle_time_s = float(np.percentile(cycle_times, 95))

        # AGV-level stats
        total_dist = 0.0
        utilizations = []
        for agv in self.agvs:
            total_active = agv.metrics.busy_time_s
            total_time = self.env.now
            util = (total_active / total_time * 100) if total_time > 0 else 0.0
            utilizations.append(util)
            total_dist += agv.metrics.distance_travelled_m

            self.metrics.agv_summaries[agv.id] = {
                "tasks_completed": agv.metrics.tasks_completed,
                "distance_m": total_dist,
                "idle_time_s": agv.metrics.idle_time_s,
                "charging_time_s": agv.metrics.charging_time_s,
                "wait_time_s": agv.metrics.waiting_time_s,
                "utilization_pct": util,
                "final_battery_pct": agv.state.battery_soc.level,
            }

        self.metrics.total_distance_travelled_m = total_dist
        self.metrics.avg_agv_utilization_pct = (
            float(np.mean(utilizations)) if utilizations else 0.0
        )

        return self.metrics
