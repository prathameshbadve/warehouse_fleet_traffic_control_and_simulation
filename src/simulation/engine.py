"""
Main Simulation Engine
"""
# pylint: disable=line-too-long

from __future__ import annotations
from datetime import datetime
from typing import Type, List, Dict
from pathlib import Path

import numpy as np
import simpy

from src.warehouse.config import WarehouseConfig
from src.warehouse.graph import WarehouseGraph, NodeType
from src.warehouse.layout import GridLayoutGenerator
from src.simulation.agvs import MovementStrategy, AGV, AGVStatus
from src.simulation.tasks import TaskGenerator
from src.simulation.metrics import SimulationMetrics, MetricsCollector
from src.simulation.visualization import generate_visualizations
from src.simulation.stations import (
    initialize_charging_station_resources,
    initialize_pick_station_resources,
    # initialize_parking_station_resources,
)


class SimulationEngine:
    """
    Top level simulation engine.

    Requires:
        - warehouse configuration
        - number of agvs
        - simulation AGV movement strategy
    """

    def __init__(
        self,
        warehouse_config: WarehouseConfig,
        n_agvs: int,
        movement_strategy: Type[MovementStrategy] | None,
        output_dir: str = "data/output/results",
        run_name: str | None = None,
    ):
        self.warehouse_config = warehouse_config
        self.n_agvs = n_agvs
        self.movement_strat = movement_strategy

        # Output configuration
        self.output_dir = Path(output_dir)
        self.run_name = run_name or self._generate_run_name()
        self.run_output_dir = self.output_dir / self.run_name
        self.run_output_dir.mkdir(exist_ok=True, parents=True)

        # Initialize simulation objects
        self.warehouse: WarehouseGraph | None = None
        self.agvs: List[AGV] = []
        self.metrics: SimulationMetrics | None = None

        # Simpy resources for the stations (initialized in run())
        self.pick_station_resources: Dict[str, simpy.Resource] = {}
        self.charging_station_resources: Dict[str, simpy.Resource] = {}
        self.parking_station_resources: Dict[str, simpy.Resource] = {}

    def _generate_run_name(self) -> str:
        """Generates a unique run name based on configuration"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"run_{self.n_agvs}agvs_{timestamp}"

    def run(self, gen_vis: bool = True):
        """
        Run one replication of the simulation

        Args:
            generate_visualizations: If True, automatically generate all plots

        Returns:
            SimulationMetrics object with comprehensive results

        """

        print("\n" + "=" * 70)
        print("WAREHOUSE SIMULATION ENGINE")
        print("=" * 70)
        print(f"Run Name: {self.run_name}")
        print(f"Output Directory: {self.run_output_dir}")
        print("=" * 70)

        print("\n[Configuration]")
        print(f"  • Fleet Size: {self.n_agvs} AGVs")
        print(f"  • Pick Stations: {self.warehouse_config.layout.n_highways}")
        print(f"  • Charging Stations: {self.warehouse_config.layout.n_highways}")
        print("  • Parking Stations: 4 corners")
        print(
            f"  • Task Arrival Rate: {self.warehouse_config.tasks.task_arrival_base_rate_per_min:.1f} tasks/min"
        )
        print(
            f"  • Simulation Duration: {self.warehouse_config.simulation.duration_s / 3600:.1f} hours"
        )
        print(
            f"  • Standard SLA: {self.warehouse_config.tasks.standard_sla_deadline_s:.0f}s"
        )
        print(
            f"  • Express SLA: {self.warehouse_config.tasks.express_sla_deadline_s:.0f}s"
        )

        env = simpy.Environment()
        rng = np.random.default_rng(self.warehouse_config.simulation.random_seed)

        # Build the warehouse
        print("\n[WAREHOUSE GENERATION]")
        grid_layout_gen = GridLayoutGenerator(self.warehouse_config)
        self.warehouse = grid_layout_gen.generate()
        warehouse_validation_issues = self.warehouse.validate()

        if len(warehouse_validation_issues) > 0:
            print(
                f"  ⚠ Warning: {len(warehouse_validation_issues)} validation issues found"
            )
            for issue in warehouse_validation_issues:
                print(f"    - {issue}")
        else:
            print("  ✓ Warehouse layout validated successfully")

        print(f"  • Total Nodes: {self.warehouse.n_nodes}")
        print(f"  • Total Edges: {self.warehouse.n_edges}")
        print(
            f"  • Storage Cells: {len(self.warehouse.nodes_by_type(NodeType.STORAGE))}"
        )

        # Initialize simulation resources
        print("\n[STATION RESOURCES]")

        # Stations
        pick_stations = self.warehouse.nodes_by_type(NodeType.PICK_STATION)
        charging_stations = self.warehouse.nodes_by_type(NodeType.CHARGING)
        parking_stations = self.warehouse.nodes_by_type(NodeType.PARKING)

        # Create the simpy resources for the stations
        self.pick_station_resources = initialize_pick_station_resources(
            env, pick_stations, self.warehouse_config.stations.pick_station_capacity
        )
        self.charging_station_resources = initialize_charging_station_resources(
            env,
            charging_stations,
            self.warehouse_config.stations.charging_station_capacity,
        )
        # self.parking_station_resources: Dict[str, simpy.Resource] = (
        #     initialize_parking_station_resources(env, parking_stations)
        # )

        print(
            f"  ✓ {len(pick_stations)} pick stations initialized (capacity: {self.warehouse_config.stations.pick_station_capacity} each)"
        )
        print(
            f"  ✓ {len(charging_stations)} charging stations initialized (capacity: {self.warehouse_config.stations.charging_station_capacity} each)"
        )
        print(f"  ✓ {len(parking_stations)} parking stations available")

        # Create the AGV fleet
        print("\n[AGV FLEET CREATION]")
        for i in range(self.n_agvs):
            # AGV ID
            agv_id = f"AGV_{i:03d}"
            starting_location = rng.choice(parking_stations)

            agv = AGV(
                agv_id=agv_id,
                start_position=starting_location,
                env=env,
                config=self.warehouse_config.agv,
                warehouse=self.warehouse,
                rng=rng,
                movement_strategy=self.movement_strat,
                pick_station_resources=self.pick_station_resources,
                charging_station_resources=self.charging_station_resources,
                # parking_station_resources=self.parking_station_resources,
            )

            self.agvs.append(agv)
            env.process(agv.run())

        print(f"  ✓ {self.n_agvs} AGVs deployed across parking stations")

        # Task generator
        print("\n[TASK GENERATION]")
        task_gen = TaskGenerator(
            env=env,
            rng=rng,
            warehouse=self.warehouse,
            config=self.warehouse_config.tasks,
        )
        env.process(task_gen.run())
        print(
            f"  ✓ Task generator activated (rate: {self.warehouse_config.tasks.task_arrival_base_rate_per_min:.1f} tasks/min)"
        )

        # Task dispatcher
        print("\n[TASK DISPATCHER]")
        env.process(self._dispatcher_process(env, task_gen))
        print(
            f"  ✓ Dispatcher active (interval: {self.warehouse_config.simulation.dispatch_interval_s}s)"
        )

        # Metrics Collector
        print("\n[METRICS COLLECTION]")
        collector = MetricsCollector(
            env=env,
            agvs=self.agvs,
            task_generator=task_gen,
            warehouse_config=self.warehouse_config,
            pick_station_resources=self.pick_station_resources,
            charging_station_resources=self.charging_station_resources,
            interval_s=self.warehouse_config.simulation.metrics_interval_s,
        )
        env.process(collector.run())
        print(
            f"  ✓ Enhanced metrics collector active (interval: {self.warehouse_config.simulation.metrics_interval_s}s)"
        )

        # Run simulation
        print("\n" + "=" * 70)
        print("SIMULATION RUNNING...")
        print("=" * 70)

        env.run(until=self.warehouse_config.simulation.duration_s)

        # Compute final metrics
        print("\n[COMPUTING FINAL METRICS]")
        self.metrics = collector.compute_final_metrics()

        # Print summary
        print("\n" + "=" * 70)
        print("SIMULATION COMPLETE - RESULTS SUMMARY")
        print("=" * 70)

        print("\n[TASK PERFORMANCE]")
        print(f"  • Tasks Generated:    {self.metrics.tasks_generated}")
        print(f"  • Tasks Completed:    {self.metrics.tasks_completed}")
        print(f"  • Tasks Failed:       {self.metrics.tasks_failed}")
        print(
            f"  • Throughput:         {self.metrics.avg_throughput_per_hour:.2f} tasks/hour"
        )

        print("\n[CYCLE TIME STATISTICS]")
        print(f"  • Mean:               {self.metrics.avg_cycle_time_s:.2f}s")
        print(f"  • Median (P50):       {self.metrics.median_cycle_time_s:.2f}s")
        print(f"  • P95:                {self.metrics.p95_cycle_time_s:.2f}s")
        print(f"  • P99:                {self.metrics.p99_cycle_time_s:.2f}s")
        print(f"  • Std Deviation:      {self.metrics.std_cycle_time_s:.2f}s")

        print("\n[SLA COMPLIANCE]")
        print(
            f"  • Overall:            {self.metrics.sla_compliance_rate_overall:.2f}%"
        )
        print(
            f"  • Standard Tasks:     {self.metrics.sla_compliance_rate_standard:.2f}%"
        )
        print(
            f"  • Express Tasks:      {self.metrics.sla_compliance_rate_express:.2f}%"
        )
        print(f"  • Avg Lateness:       {self.metrics.avg_lateness_s:.2f}s")
        print(f"  • Max Lateness:       {self.metrics.max_lateness_s:.2f}s")
        print(f"  • % Tasks Late:       {self.metrics.pct_tasks_late:.2f}%")

        print("\n[AGV FLEET PERFORMANCE]")
        print(f"  • Avg Utilization:    {self.metrics.avg_agv_utilization_pct:.2f}%")
        print(f"  • Min Utilization:    {self.metrics.min_agv_utilization_pct:.2f}%")
        print(f"  • Max Utilization:    {self.metrics.max_agv_utilization_pct:.2f}%")
        print(f"  • Total Distance:     {self.metrics.total_distance_travelled_m:.2f}m")
        print(f"  • Avg Distance/Task:  {self.metrics.avg_distance_per_task_m:.2f}m")
        print(f"  • Total Energy:       {self.metrics.total_energy_consumed:.2f}")

        print("\n[STATION PERFORMANCE]")
        print(
            f"  • Pick Station Util:  {self.metrics.avg_pick_station_utilization:.2f}%"
        )
        print(
            f"  • Charging Util:      {self.metrics.avg_charging_station_utilization:.2f}%"
        )
        print(f"  • Avg Pick Queue:     {self.metrics.avg_pick_queue_length:.2f}")
        print(f"  • Avg Charging Queue: {self.metrics.avg_charging_queue_length:.2f}")
        print(f"  • Max Pick Queue:     {self.metrics.max_pick_queue_length}")
        print(f"  • Max Charging Queue: {self.metrics.max_charging_queue_length}")

        # Generate visualizations
        if gen_vis:
            print("\n" + "=" * 70)
            print("GENERATING VISUALIZATIONS")
            print("=" * 70)

            generate_visualizations(self.metrics, str(self.run_output_dir))

        print("\n" + "=" * 70)
        print(f"✓ ALL RESULTS SAVED TO: {self.run_output_dir}")
        print("=" * 70 + "\n")

        return self.metrics

    def _dispatcher_process(
        self,
        env: simpy.Environment,
        task_gen: TaskGenerator,
    ):
        """Periodically assign pending tasks to idle AGVs."""

        dispatch_interval_s = self.warehouse_config.simulation.dispatch_interval_s

        while True:
            # Get pending tasks
            pending_tasks = task_gen.get_and_clear_pending()

            if pending_tasks:
                idle_agvs = [
                    agv
                    for agv in self.agvs
                    if agv.state.status == AGVStatus.IDLE
                    and agv.state.current_task is None
                ]
                if idle_agvs:
                    while len(pending_tasks) > 0 and len(idle_agvs) > 0:
                        chosen_task = pending_tasks.pop(0)
                        chosen_agv = idle_agvs.pop(0)
                        chosen_agv.assign_task(chosen_task)

                # Update the pending tasks in the task generator (if any are left unassigned)
                if len(pending_tasks) > 0:
                    task_gen.pending_tasks.extend(pending_tasks)

            yield env.timeout(dispatch_interval_s)

    def save_metrics_summary(self, filename: str = "metrics_summary.txt"):
        """Save a text summary of metrics to file"""

        if self.metrics is None:
            print("Warning: No metrics available to save")
            return

        output_path = self.run_output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("WAREHOUSE SIMULATION - METRICS SUMMARY\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Run Name: {self.run_name}\n")
            f.write(f"Fleet Size: {self.n_agvs} AGVs\n")
            f.write(
                f"Simulation Duration: {self.metrics.total_simulation_time_s / 3600:.2f} hours\n\n"
            )

            f.write("[TASK PERFORMANCE]\n")
            f.write(f"  Tasks Generated:    {self.metrics.tasks_generated}\n")
            f.write(f"  Tasks Completed:    {self.metrics.tasks_completed}\n")
            f.write(f"  Tasks Failed:       {self.metrics.tasks_failed}\n")
            f.write(
                f"  Throughput:         {self.metrics.avg_throughput_per_hour:.2f} tasks/hour\n\n"
            )

            f.write("[CYCLE TIME STATISTICS]\n")
            f.write(f"  Mean:               {self.metrics.avg_cycle_time_s:.2f}s\n")
            f.write(f"  Median (P50):       {self.metrics.median_cycle_time_s:.2f}s\n")
            f.write(f"  P75:                {self.metrics.p75_cycle_time_s:.2f}s\n")
            f.write(f"  P90:                {self.metrics.p90_cycle_time_s:.2f}s\n")
            f.write(f"  P95:                {self.metrics.p95_cycle_time_s:.2f}s\n")
            f.write(f"  P99:                {self.metrics.p99_cycle_time_s:.2f}s\n")
            f.write(f"  Std Deviation:      {self.metrics.std_cycle_time_s:.2f}s\n\n")

            f.write("[SLA COMPLIANCE]\n")
            f.write(
                f"  Overall:            {self.metrics.sla_compliance_rate_overall:.2f}%\n"
            )
            f.write(
                f"  Standard Tasks:     {self.metrics.sla_compliance_rate_standard:.2f}%\n"
            )
            f.write(
                f"  Express Tasks:      {self.metrics.sla_compliance_rate_express:.2f}%\n"
            )
            f.write(f"  Avg Lateness:       {self.metrics.avg_lateness_s:.2f}s\n")
            f.write(f"  Max Lateness:       {self.metrics.max_lateness_s:.2f}s\n")
            f.write(f"  % Tasks Late:       {self.metrics.pct_tasks_late:.2f}%\n\n")

            f.write("[AGV FLEET PERFORMANCE]\n")
            f.write(
                f"  Avg Utilization:    {self.metrics.avg_agv_utilization_pct:.2f}%\n"
            )
            f.write(
                f"  Min Utilization:    {self.metrics.min_agv_utilization_pct:.2f}%\n"
            )
            f.write(
                f"  Max Utilization:    {self.metrics.max_agv_utilization_pct:.2f}%\n"
            )
            f.write(
                f"  Std Utilization:    {self.metrics.std_agv_utilization_pct:.2f}%\n"
            )
            f.write(
                f"  Total Distance:     {self.metrics.total_distance_travelled_m:.2f}m\n"
            )
            f.write(
                f"  Avg Distance/Task:  {self.metrics.avg_distance_per_task_m:.2f}m\n"
            )
            f.write(f"  Total Energy:       {self.metrics.total_energy_consumed:.2f}\n")
            f.write(f"  Avg Energy/Task:    {self.metrics.avg_energy_per_task:.2f}\n\n")

            f.write("[STATION PERFORMANCE]\n")
            f.write(
                f"  Pick Station Util:  {self.metrics.avg_pick_station_utilization:.2f}%\n"
            )
            f.write(
                f"  Charging Util:      {self.metrics.avg_charging_station_utilization:.2f}%\n"
            )
            f.write(f"  Avg Pick Queue:     {self.metrics.avg_pick_queue_length:.2f}\n")
            f.write(
                f"  Avg Charging Queue: {self.metrics.avg_charging_queue_length:.2f}\n"
            )
            f.write(f"  Max Pick Queue:     {self.metrics.max_pick_queue_length}\n")
            f.write(f"  Max Charging Queue: {self.metrics.max_charging_queue_length}\n")
            f.write(f"  Avg Wait (Pick):    {self.metrics.avg_wait_time_pick_s:.2f}s\n")
            f.write(
                f"  P95 Wait (Pick):    {self.metrics.p95_wait_time_pick_s:.2f}s\n\n"
            )

        print(f"✓ Metrics summary saved to: {output_path}")
