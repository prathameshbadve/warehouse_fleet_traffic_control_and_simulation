"""
Simulation Metrics Collector Object
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict

import numpy as np
import simpy

from src.warehouse.config import WarehouseConfig
from src.simulation.agvs import AGV, AGVStatus
from src.simulation.tasks import Task, TaskGenerator, TaskStatus, TaskPriority


@dataclass
class Snapshot:
    """A point-in-time snapshot of system state."""

    # Timestamp
    time_s: float

    # Task level
    tasks_completed: int
    tasks_pending: int
    tasks_failed: int
    throughput_per_hour: float

    # Cycle time metrics
    avg_cycle_time_s: float
    median_cycle_time_s: float
    p95_cycle_time_s: float

    # SLA Metrics
    sla_compliance_rate_overall: float
    sla_compliance_rate_standard: float
    sla_compliance_rate_express: float
    avg_lateness_s: float

    # AGV level
    agv_utilization_pct: float
    n_agvs_idle: int
    n_agvs_working: int
    n_agvs_charging: int
    n_agvs_waiting: int
    avg_battery_level: float

    # Station level
    pick_station_utilization: float
    charging_station_utilization: float
    avg_pick_station_queue_length: float
    avg_charging_station_queue_length: float
    max_pick_station_queue_length: int
    max_charging_station_queue_length: int

    # Wait time metrics
    avg_wait_time_pick_s: float
    avg_wait_time_charging_s: float

    # Detailed station data
    station_queue_lengths: Dict[str, int] = field(default_factory=dict)
    station_utilizations: Dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationMetrics:
    """Contains all top level simulation metrics"""

    # Time-series snapshots
    snapshots: list[Snapshot] = field(default_factory=list)

    # Basic metrics
    total_simulation_time_s: float = 0.0
    tasks_generated: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0

    # Throughput metrics
    avg_throughput_per_hour: float = 0.0

    # Cycle time metrics
    avg_cycle_time_s: float = 0.0
    median_cycle_time_s: float = 0.0
    p50_cycle_time_s: float = 0.0
    p75_cycle_time_s: float = 0.0
    p90_cycle_time_s: float = 0.0
    p95_cycle_time_s: float = 0.0
    p99_cycle_time_s: float = 0.0
    std_cycle_time_s: float = 0.0

    # SLA metrics
    sla_compliance_rate_overall: float = 0.0
    sla_compliance_rate_standard: float = 0.0
    sla_compliance_rate_express: float = 0.0
    avg_lateness_s: float = 0.0
    max_lateness_s: float = 0.0
    pct_tasks_late: float = 0.0

    # AGV utilization
    avg_agv_utilization_pct: float = 0.0
    min_agv_utilization_pct: float = 0.0
    max_agv_utilization_pct: float = 0.0
    std_agv_utilization_pct: float = 0.0

    # Station metrics
    avg_pick_station_utilization: float = 0.0
    avg_charging_station_utilization: float = 0.0
    avg_pick_queue_length: float = 0.0
    avg_charging_queue_length: float = 0.0
    max_pick_queue_length: int = 0
    max_charging_queue_length: int = 0

    # Wait time metrics
    avg_wait_time_pick_s: float = 0.0
    avg_wait_time_charging_s: float = 0.0
    p95_wait_time_pick_s: float = 0.0
    p95_wait_time_charging_s: float = 0.0

    # Distance and energy
    total_distance_travelled_m: float = 0.0
    avg_distance_per_task_m: float = 0.0
    total_energy_consumed: float = 0.0
    avg_energy_per_task: float = 0.0

    # Cycle time breakdown (average across all tasks)
    avg_travel_to_storage_time_s: float = 0.0
    avg_retrieval_time_s: float = 0.0
    avg_travel_to_pick_time_s: float = 0.0
    avg_picking_time_s: float = 0.0
    avg_travel_return_time_s: float = 0.0
    avg_storage_time_s: float = 0.0
    avg_travel_to_parking_time_s: float = 0.0

    # Per-AGV summaries
    agv_summaries: Dict[str, Dict] = field(default_factory=dict)

    # Raw data for plotting
    all_cycle_times: List[float] = field(default_factory=list)
    all_lateness_values: List[float] = field(default_factory=list)
    all_wait_times_pick: List[float] = field(default_factory=list)
    all_wait_times_charging: List[float] = field(default_factory=list)

    # To be deleted later
    total_delay_s: float = 0.0
    avg_task_delay_s: float = 0.0
    num_sla_violations: int = 0


class MetricsCollector:
    """
    SimPy process that periodically snapshots the system state
    and computes final KPIs for OR analysis
    """

    def __init__(
        self,
        env: simpy.Environment,
        agvs: List[AGV],
        task_generator: TaskGenerator,
        warehouse_config: WarehouseConfig,
        pick_station_resources: Dict[str, simpy.Resource],
        charging_station_resources: Dict[str, simpy.Resource],
        interval_s: float = 60.0,
    ):
        self.env = env
        self.agvs = agvs
        self.task_generator = task_generator
        self.warehouse_config = warehouse_config
        self.pick_station_resources = pick_station_resources
        self.charging_station_resources = charging_station_resources
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

    def _compute_sla_metrics(self, tasks: List[Task]) -> Dict:
        """Compute SLA compliance metrics for completed tasks."""

        if not tasks or len(tasks) == 0:
            return {
                "overall": 0.0,
                "standard": 0.0,
                "express": 0.0,
                "avg_lateness": 0.0,
                "late_tasks": [],
                "late_times": [],
            }

        # Separate the standard and express priority tasks
        standard_tasks = [t for t in tasks if t.priority == TaskPriority.STANDARD]
        express_tasks = [t for t in tasks if t.priority == TaskPriority.EXPRESS]

        # Get the SLA deadlines from the config file
        standard_sla = self.warehouse_config.tasks.standard_sla_deadline_s
        express_sla = self.warehouse_config.tasks.express_sla_deadline_s

        # Calculate compliance
        standard_met = sum(
            1 for t in standard_tasks if t.metrics.cycle_time_s <= standard_sla
        )
        express_met = sum(
            1 for t in express_tasks if t.metrics.cycle_time_s <= express_sla
        )

        # Calculate the compliance percentages
        standard_compliance = (
            (standard_met / len(standard_tasks) * 100) if standard_tasks else 100.0
        )
        express_compliance = (
            (express_met / len(express_tasks) * 100) if express_tasks else 100.0
        )

        # Calculate lateness
        late_tasks = []
        late_times = []
        for t in tasks:
            sla = express_sla if t.priority == TaskPriority.EXPRESS else standard_sla
            lateness = max(0, t.metrics.cycle_time_s - sla)
            if lateness > 0:
                late_tasks.append(t)
                late_times.append(lateness)

        avg_lateness = np.mean(late_times) if late_times else 0.0
        overall_compliance = (
            ((standard_met + express_met) / len(tasks) * 100) if tasks else 100.0
        )

        return {
            "overall": overall_compliance,
            "standard": standard_compliance,
            "express": express_compliance,
            "avg_lateness": avg_lateness,
            "late_tasks": late_tasks,
            "late_times": late_times,
        }

    def _compute_station_metrics(self) -> Dict:
        """Compute station utilization and queue metrics."""

        pick_queues = []
        pick_utilizations = []
        station_queues = {}
        station_utils = {}

        for station_id, resource in self.pick_station_resources.items():
            queue_len = len(resource.queue)
            in_use = len(resource.users)
            capacity = resource.capacity

            pick_queues.append(queue_len)
            utilization = (in_use / capacity * 100) if capacity > 0 else 0.0
            pick_utilizations.append(utilization)

            station_queues[station_id] = queue_len
            station_utils[station_id] = utilization

        charging_queues = []
        charging_utilizations = []

        for station_id, resource in self.charging_station_resources.items():
            queue_len = len(resource.queue)
            in_use = len(resource.users)
            capacity = resource.capacity

            charging_queues.append(queue_len)
            utilization = (in_use / capacity * 100) if capacity > 0 else 0.0
            charging_utilizations.append(utilization)

            station_queues[station_id] = queue_len
            station_utils[station_id] = utilization

        return {
            "pick_util": np.mean(pick_utilizations) if pick_utilizations else 0.0,
            "charging_util": np.mean(charging_utilizations)
            if charging_utilizations
            else 0.0,
            "avg_pick_queue": np.mean(pick_queues) if pick_queues else 0.0,
            "avg_charging_queue": np.mean(charging_queues) if charging_queues else 0.0,
            "max_pick_queue": int(max(pick_queues)) if pick_queues else 0,
            "max_charging_queue": int(max(charging_queues)) if charging_queues else 0,
            "station_queues": station_queues,
            "station_utils": station_utils,
        }

    def _take_snapshot(self) -> Snapshot:
        """
        Capture current system state and return a Snapshot object.
        """

        now = self.env.now

        # Task status counts
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

        # Throughput
        elapsed_hours = now / 3600.0
        throughput = n_completed / elapsed_hours if elapsed_hours > 0 else 0.0

        # Cycle time metrics
        cycle_times = [
            t.metrics.cycle_time_s
            for t in completed_tasks
            if t.metrics.cycle_time_s > 0
        ]
        avg_cycle = float(np.mean(cycle_times)) if cycle_times else 0.0
        median_cycle = float(np.median(cycle_times)) if cycle_times else 0.0
        p95_cycle = float(np.percentile(cycle_times, 95)) if cycle_times else 0.0

        # SLA metrics
        sla_metrics = self._compute_sla_metrics(completed_tasks)

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
        utilization = (n_working / len(self.agvs) * 100) if self.agvs else 0.0

        # Average battery level
        avg_battery = (
            np.mean([a.state.battery_soc.level for a in self.agvs])
            if self.agvs
            else 0.0
        )

        # Station metrics
        station_metrics = self._compute_station_metrics()

        # Wait time metrics (from completed tasks)
        wait_times_pick = [
            t.metrics.wait_time_s for t in completed_tasks if t.metrics.wait_time_s > 0
        ]
        avg_wait_pick = float(np.mean(wait_times_pick)) if wait_times_pick else 0.0

        # Note: We're not tracking charging wait times per task yet
        # This would require additional instrumentation in AGV.run()
        avg_wait_charging = 0.0

        return Snapshot(
            time_s=now,
            tasks_completed=n_completed,
            tasks_pending=n_pending,
            tasks_failed=n_failed,
            throughput_per_hour=throughput,
            avg_cycle_time_s=avg_cycle,
            median_cycle_time_s=median_cycle,
            p95_cycle_time_s=p95_cycle,
            sla_compliance_rate_overall=sla_metrics["overall"],
            sla_compliance_rate_standard=sla_metrics["standard"],
            sla_compliance_rate_express=sla_metrics["express"],
            avg_lateness_s=sla_metrics["avg_lateness"],
            agv_utilization_pct=utilization,
            n_agvs_idle=n_idle,
            n_agvs_working=n_working,
            n_agvs_charging=n_charging,
            n_agvs_waiting=n_waiting,
            avg_battery_level=avg_battery,
            pick_station_utilization=station_metrics["pick_util"],
            charging_station_utilization=station_metrics["charging_util"],
            avg_pick_station_queue_length=station_metrics["avg_pick_queue"],
            avg_charging_station_queue_length=station_metrics["avg_charging_queue"],
            max_pick_station_queue_length=station_metrics["max_pick_queue"],
            max_charging_station_queue_length=station_metrics["max_charging_queue"],
            avg_wait_time_pick_s=avg_wait_pick,
            avg_wait_time_charging_s=avg_wait_charging,
            station_queue_lengths=station_metrics["station_queues"],
            station_utilizations=station_metrics["station_utils"],
        )

    def compute_final_metrics(self):
        """
        Compute summary statistics after the simulation completes.

        Returns:
            SimulationMetrics with both time-series snapshots and summary stats.
        """

        all_tasks = self.task_generator.tasks
        completed = [t for t in all_tasks if t.status == TaskStatus.COMPLETE]
        failed = [t for t in all_tasks if t.status == TaskStatus.FAILED]

        cycle_times = [
            t.metrics.cycle_time_s for t in completed if t.metrics.cycle_time_s > 0
        ]

        self.metrics.tasks_generated = len(all_tasks)
        self.metrics.tasks_completed = len(completed)
        self.metrics.tasks_failed = len(failed)
        self.metrics.total_simulation_time_s = self.env.now

        # Throughput
        elapsed_hours = self.env.now / 3600.0
        self.metrics.avg_throughput_per_hour = (
            len(completed) / elapsed_hours if elapsed_hours > 0 else 0.0
        )

        # Cycle time statistics
        if cycle_times:
            self.metrics.avg_cycle_time_s = float(np.mean(cycle_times))
            self.metrics.median_cycle_time_s = float(np.median(cycle_times))
            self.metrics.std_cycle_time_s = float(np.std(cycle_times))
            self.metrics.p50_cycle_time_s = float(np.percentile(cycle_times, 50))
            self.metrics.p75_cycle_time_s = float(np.percentile(cycle_times, 75))
            self.metrics.p90_cycle_time_s = float(np.percentile(cycle_times, 90))
            self.metrics.p95_cycle_time_s = float(np.percentile(cycle_times, 95))
            self.metrics.p99_cycle_time_s = float(np.percentile(cycle_times, 99))
            self.metrics.all_cycle_times = cycle_times

        # SLA metrics
        sla_metrics = self._compute_sla_metrics(completed)
        self.metrics.sla_compliance_rate_overall = sla_metrics["overall"]
        self.metrics.sla_compliance_rate_standard = sla_metrics["standard"]
        self.metrics.sla_compliance_rate_express = sla_metrics["express"]
        self.metrics.avg_lateness_s = sla_metrics["avg_lateness"]
        self.metrics.all_lateness_values = sla_metrics["late_times"]

        if sla_metrics["late_tasks"]:
            self.metrics.max_lateness_s = max(sla_metrics["late_times"])
            self.metrics.pct_tasks_late = (
                len(sla_metrics["late_tasks"]) / len(completed) * 100
            )

        # Wait time statistics
        wait_times_pick = [
            t.metrics.wait_time_s for t in completed if t.metrics.wait_time_s > 0
        ]
        if wait_times_pick:
            self.metrics.avg_wait_time_pick_s = float(np.mean(wait_times_pick))
            self.metrics.p95_wait_time_pick_s = float(
                np.percentile(wait_times_pick, 95)
            )
            self.metrics.all_wait_times_pick = wait_times_pick

        # Station metrics (average across all snapshots)
        if self.metrics.snapshots:
            self.metrics.avg_pick_station_utilization = np.mean(
                [s.pick_station_utilization for s in self.metrics.snapshots]
            )
            self.metrics.avg_charging_station_utilization = np.mean(
                [s.charging_station_utilization for s in self.metrics.snapshots]
            )
            self.metrics.avg_pick_queue_length = np.mean(
                [s.avg_pick_station_queue_length for s in self.metrics.snapshots]
            )
            self.metrics.avg_charging_queue_length = np.mean(
                [s.avg_charging_station_queue_length for s in self.metrics.snapshots]
            )
            self.metrics.max_pick_queue_length = max(
                [s.max_pick_station_queue_length for s in self.metrics.snapshots]
            )
            self.metrics.max_charging_queue_length = max(
                [s.max_charging_station_queue_length for s in self.metrics.snapshots]
            )

        # Cycle time breakdown
        retrieval_times = [
            t.metrics.retrieval_time_s
            for t in completed
            if t.metrics.retrieval_time_s > 0
        ]
        picking_times = [
            t.metrics.picking_time_s for t in completed if t.metrics.picking_time_s > 0
        ]
        storage_times = [
            t.metrics.storage_time_s for t in completed if t.metrics.storage_time_s > 0
        ]

        if retrieval_times:
            self.metrics.avg_retrieval_time_s = float(np.mean(retrieval_times))
        if picking_times:
            self.metrics.avg_picking_time_s = float(np.mean(picking_times))
        if storage_times:
            self.metrics.avg_storage_time_s = float(np.mean(storage_times))

        # AGV-level statistics
        total_dist = 0.0
        total_energy = 0.0
        utilizations = []

        for agv in self.agvs:
            total_active = agv.metrics.busy_time_s
            total_time = self.env.now
            util = (total_active / total_time * 100) if total_time > 0 else 0.0
            utilizations.append(util)
            total_dist += agv.metrics.distance_travelled_m
            total_energy += agv.metrics.energy_consumed

            self.metrics.agv_summaries[agv.id] = {
                "tasks_completed": agv.metrics.tasks_completed,
                "distance_m": agv.metrics.distance_travelled_m,
                "energy_consumed": agv.metrics.energy_consumed,
                "idle_time_s": agv.metrics.idle_time_s,
                "busy_time_s": agv.metrics.busy_time_s,
                "charging_time_s": agv.metrics.charging_time_s,
                "wait_time_s": agv.metrics.waiting_time_s,
                "utilization_pct": util,
                "final_battery_pct": agv.state.battery_soc.level,
                "num_charging_visits": agv.metrics.num_charging_visits,
            }

        self.metrics.total_distance_travelled_m = total_dist
        self.metrics.total_energy_consumed = total_energy

        if completed:
            self.metrics.avg_distance_per_task_m = total_dist / len(completed)
            self.metrics.avg_energy_per_task = total_energy / len(completed)

        if utilizations:
            self.metrics.avg_agv_utilization_pct = float(np.mean(utilizations))
            self.metrics.min_agv_utilization_pct = float(min(utilizations))
            self.metrics.max_agv_utilization_pct = float(max(utilizations))
            self.metrics.std_agv_utilization_pct = float(np.std(utilizations))

        return self.metrics
