"""
Main Simulation Engine
"""

from __future__ import annotations
from typing import Type, List, Dict

import numpy as np
import simpy

from src.warehouse.config import WarehouseConfig
from src.warehouse.graph import WarehouseGraph, NodeType
from src.warehouse.layout import GridLayoutGenerator
from src.simulation.agvs import MovementStrategy, AGV, AGVStatus
from src.simulation.tasks import TaskGenerator
from src.simulation.metrics import SimulationMetrics, MetricsCollector
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
    ):
        self.warehouse_config = warehouse_config
        self.n_agvs = n_agvs
        self.movement_strat = movement_strategy

        # Initialize simulation objects
        self.warehouse: WarehouseGraph | None = None
        self.agvs: List[AGV] = []
        self.metrics: SimulationMetrics | None = None

        # Simpy resources for the stations (initialized in run())
        self.pick_station_resources: Dict[str, simpy.Resource] = {}
        self.charging_station_resources: Dict[str, simpy.Resource] = {}
        self.parking_station_resources: Dict[str, simpy.Resource] = {}

    def run(self):
        """Run one replication of the simulation"""

        print("-------------------------------")
        print("Configuring simulation with the following parameters:")
        print(f"    Number of AGVs: {self.n_agvs}")
        print(f"    Number of pick stations: {self.warehouse_config.layout.n_highways}")
        print(
            f"    Number of charging stations: {self.warehouse_config.layout.n_highways}"
        )
        print(
            f"    Number of parking stations: {self.warehouse_config.layout.n_highways}"
        )
        print(
            f"    Simulation duration: {self.warehouse_config.simulation.duration_s / 3600:.1f} hours"  # pylint: disable=line-too-long
        )

        env = simpy.Environment()
        rng = np.random.default_rng(self.warehouse_config.simulation.random_seed)

        # Build the warehouse
        print("-------------------------------")
        print("Generating warehouse layout...")
        grid_layout_gen = GridLayoutGenerator(self.warehouse_config)
        self.warehouse = grid_layout_gen.generate()
        warehouse_validation_issues = self.warehouse.validate()
        if len(warehouse_validation_issues) > 0:
            print("Warehouse layout validation issues found:")
        else:
            print("Warehouse layout generated and validated successfully...")

        # Initialize simulation resources
        print("-------------------------------")
        print("Initializing required SimPy resources...")

        # Stations
        pick_stations = self.warehouse.nodes_by_type(NodeType.PICK_STATION)
        charging_stations = self.warehouse.nodes_by_type(NodeType.CHARGING)
        parking_stations = self.warehouse.nodes_by_type(NodeType.PARKING)

        # Create the simpy resources for the stations
        self.pick_station_resources: Dict[str, simpy.Resource] = (
            initialize_pick_station_resources(
                env, pick_stations, self.warehouse_config.stations.pick_station_capacity
            )
        )
        self.charging_station_resources: Dict[str, simpy.Resource] = (
            initialize_charging_station_resources(
                env,
                charging_stations,
                self.warehouse_config.stations.charging_station_capacity,
            )
        )
        # self.parking_station_resources: Dict[str, simpy.Resource] = (
        #     initialize_parking_station_resources(env, parking_stations)
        # )

        print("All required SimPy resources initialized successfully...")

        # Create the AGV fleet
        print("-------------------------------")
        print("Generating the AGV fleet...")
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

        print(f"Total {self.n_agvs} generated.")

        # Task generator
        print("-------------------------------")
        print("Starting the task generator process...")
        task_gen = TaskGenerator(
            env=env,
            rng=rng,
            warehouse=self.warehouse,
            config=self.warehouse_config.tasks,
        )
        env.process(task_gen.run())

        # Task dispatcher
        print("-------------------------------")
        print("Ensuring that the task assignment process is active...")
        env.process(self._dispatcher_process(env, task_gen))

        # Metrics Collector
        collector = MetricsCollector(
            env=env,
            agvs=self.agvs,
            task_generator=task_gen,
            warehouse_config=self.warehouse_config,
        )
        env.process(collector.run())

        # Run the simulation
        print("-------------------------------")
        print("Simulation Start...")
        env.run(until=self.warehouse_config.simulation.duration_s)

        self.metrics = collector.compute_final_metrics()
        print("\nSimulation complete:")
        print(f"  Tasks generated: {self.metrics.tasks_generated}")
        print(f"  Tasks completed: {self.metrics.tasks_completed}")
        print(
            f"  Avg throughput:   {self.metrics.avg_throughput_per_hour:.0f} orders/hour"
        )
        print(f"  Avg cycle time:   {self.metrics.avg_cycle_time_s:.1f}s")
        print(f"  P95 cycle time:   {self.metrics.p95_cycle_time_s:.1f}s")
        print(f"  AGV utilization:  {self.metrics.avg_agv_utilization_pct:.1f}%")
        print(f"  Station util:     {self.metrics.avg_station_utilization_pct:.1f}%")

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
