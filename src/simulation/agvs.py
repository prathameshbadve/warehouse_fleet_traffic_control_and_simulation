"""
AGV Simulation object and processes
"""

from __future__ import annotations
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Type

import numpy as np
import simpy

from src.warehouse.config import AGVConfig
from src.warehouse.graph import WarehouseGraph, NodeType
from src.simulation.tasks import Task, TaskStatus


class MovementStrategy(ABC):
    """Base class for movement strategies"""

    def __init__(self, env: simpy.Environment):
        self.env = env

    def move(self, agv: AGV, travel_time: float, battery_drain: float):
        """
        SimPy Generator process:

        Arguments:
            - agv: AGV
            - travel_time: float - Time required to travel
            - battery_drain: float - Battery level / energy consumed
        """


class TeleportStrategy(MovementStrategy):
    """
    Teleport movement strategy

    AGVs teleport directly to the next node in the path.
    """

    def move(self, agv: AGV, travel_time: float, battery_drain: float):
        """
        SimPy Generator Process for Teleport Strategy
        """

        # Simulate travel time
        yield self.env.timeout(travel_time)
        # Drain battery
        yield agv.state.battery_soc.get(battery_drain)


class AGVStatus(str, Enum):
    """Valid AGV Status"""

    IDLE = "idle"
    MOVING = "moving"
    WAITING = "waiting"
    RETRIEVING = "retrieving"
    PICKING = "picking"
    STORING = "storing"
    CHARGING = "charging"


@dataclass
class AGVState:
    """Object representing the AGV state"""

    # Position attributes
    current_position: str  # Node ID
    battery_soc: simpy.Container
    next_position: str | None = None
    last_position: str | None = None

    # Status attributes
    status: AGVStatus = AGVStatus.IDLE

    # Task attributes
    current_task: Task | None = None
    current_path: List[str] = field(default_factory=list)


@dataclass
class AGVMetrics:
    """Object representing AGV Metrics"""

    # Task related attributes
    tasks_completed: int = 0

    # Important time attributes
    idle_time_s: float = 0.0
    busy_time_s: float = 0.0
    waiting_time_s: float = 0.0
    moving_time_s: float = 0.0
    charging_time_s: float = 0.0

    # Distance attributes
    distance_travelled_m: float = 0.0

    # Energy attributes
    energy_consumed: float = 0.0

    # Charging attributes
    num_charging_visits: int = 0

    # State log
    status_log: List[Tuple[float, AGVStatus]] = field(default_factory=list)

    def log_status(self, time: float, status: AGVStatus):
        """Log the status of the AGV at the given time"""

        self.status_log.append((time, status))


class AGV:
    """
    Object representing an AGV in the simulation.
    """

    def __init__(
        self,
        env: simpy.Environment,  # Simpy environment tells the AGV the time of events
        rng: np.random.Generator,
        warehouse: WarehouseGraph,  # Warehouse environment in which the AGV will operate
        config: AGVConfig,
        agv_id: str,
        start_position: str,
        movement_strategy: Type[MovementStrategy] | None,
        pick_station_resources: Dict[str, simpy.Resource] | None = None,
        parking_station_resources: Dict[str, simpy.Resource] | None = None,
        charging_station_resources: Dict[str, simpy.Resource] | None = None,
    ):
        self.env = env
        self.rng = rng
        self.warehouse = warehouse
        self.config = config
        if movement_strategy is None:
            self.movement_strategy = TeleportStrategy(env)
        else:
            self.movement_strategy = movement_strategy

        # Simulation resources
        self.pick_station_resources = pick_station_resources
        self.parking_station_resources = parking_station_resources
        self.charging_station_resources = charging_station_resources

        # AGV Attributes
        self.id = agv_id
        self.state = AGVState(
            current_position=start_position,
            battery_soc=simpy.Container(
                env,
                capacity=100.0,
                init=config.init_battery_capacity,
            ),
        )
        self.metrics = AGVMetrics()

        # Attributes used to calculate important time stats
        self.last_idle_start_time: float | None = env.now
        self.last_busy_start_time: float | None = None
        self.last_wait_start_time: float | None = None
        self.last_moving_start_time: float | None = None
        self.last_charging_start_time: float | None = None

        # Task assignment event
        self.request_task_assignment = env.event()

    def _set_status(
        self,
        new_status: AGVStatus,
    ):
        """Update AGV Status and log"""

        self.state.status = new_status
        self.metrics.log_status(self.env.now, new_status)

    def _needs_charging(self) -> bool:
        """Checks if the AGV requires charging"""

        return self.state.battery_soc.level < self.config.battery_threshold

    def _drain_battery_after_storage_retrieval(self):
        """Drains the battery of the AGV required to store/retrieve a pod"""

        yield self.state.battery_soc.get(
            self.config.battery_drain_per_storage_retrieval
        )
        self.metrics.energy_consumed += self.config.battery_drain_per_storage_retrieval

    def compute_edge_travel_dist_time_and_energy(
        self, from_node: str, to_node: str, with_pod: bool
    ) -> float:
        """Computes the travel time between nodes based on the movement strategy"""

        edge_length = self.warehouse.edge_length(from_node, to_node)
        travel_time = edge_length / self.config.speed_mps
        drain = (
            edge_length * self.config.battery_drain_with_pod_per_meter
            if with_pod
            else edge_length * self.config.battery_drain_without_pod_per_meter
        )
        return edge_length, travel_time, drain

    def assign_task(
        self,
        task: Task,
    ):
        """Assigns a new task to an idle AGV"""

        # Assign the task
        self.state.current_task = task

        # Add AGV cross ref to task
        task.assigned_agv = self.id

        # Update the time of assignment and task status
        task.assigned_time = self.env.now
        task.status = TaskStatus.ASSIGNED

        # Wake the AGV if it's waiting
        if not self.request_task_assignment.triggered:
            self.request_task_assignment.succeed()

    def _follow_path(
        self,
        path: List[str],
        with_pod: bool,
    ):
        """
        SimPy Generator process that yields travel events
        from node to node in the path
        """

        # Update the AGV status to MOVING
        self._set_status(AGVStatus.MOVING)

        for next_destination in path:
            # Check if the next destination is distinct from the current position
            # Case: Next destination is same, so no action required
            if next_destination == self.state.current_position:
                continue

            # Case: Next destination is distinct
            self.state.next_position = next_destination

            # Compute the travel time and energy required
            travel_dist_m, travel_time, battery_drain = (
                self.compute_edge_travel_dist_time_and_energy(
                    self.state.current_position,
                    self.state.next_position,
                    with_pod,
                )
            )

            # Update the AGV time attributes
            self.last_moving_start_time = self.env.now

            # Perform the movement
            yield from self.movement_strategy.move(
                self, agv=self, travel_time=travel_time, battery_drain=battery_drain
            )

            # Update relevant AGV attributes
            # We are not directly adding the travel time as within the move() function
            # there could be waiting delays.
            travel_time_stop = self.env.now
            travel_time = travel_time_stop - self.last_moving_start_time
            self.last_moving_start_time = None

            # Metrics
            self.metrics.moving_time_s += travel_time
            self.metrics.distance_travelled_m += travel_dist_m
            self.metrics.energy_consumed += battery_drain

            # Position state attributes
            self.state.last_position = self.state.current_position
            self.state.current_position = next_destination
            self.state.next_position = None

    def _retrieve_pod(self):
        """Retrieve Pod from Storage Cell"""

        # Update AGV Status to RETRIEVING
        self._set_status(AGVStatus.RETRIEVING)

        # Sample retrieval time
        mean_time = self.config.mean_pod_storage_retrieval_time_s
        retrieval_time = self.rng.normal(mean_time, mean_time * 0.1)

        yield self.env.timeout(retrieval_time)
        yield from self._drain_battery_after_storage_retrieval()

    def _store_pod(self):
        """Store Pod in Storage Cell"""

        # Update AGV Status to RETRIEVING
        self._set_status(AGVStatus.STORING)

        # Sample retrieval time
        mean_time = self.config.mean_pod_storage_retrieval_time_s
        storage_time = self.rng.normal(mean_time, mean_time * 0.1)

        yield self.env.timeout(storage_time)
        yield from self._drain_battery_after_storage_retrieval()

    def _request_pick_station_resource(self, pick_station: str):
        """
        SimPy generator process
        """

        pick_station_resource = self.pick_station_resources.get(pick_station, None)
        if pick_station_resource is None:
            raise KeyError(f"Missing pick station resource for station {pick_station}")

        with pick_station_resource.request() as req:
            yield req

    def _request_charging_station_resource(self, charging_station: str):
        """
        SimPy generator process
        """

        charging_station_resource = self.charging_station_resources.get(
            charging_station, None
        )
        if charging_station_resource is None:
            raise KeyError(
                f"Missing charging station resource for station {charging_station}"
            )

        with charging_station_resource.request() as req:
            yield req

    def _charge_agv(self, charging_station: str, charging_time: float = None):
        """SimPy generator process for charging"""

        # AGV starts waiting to obtain charger resource
        self.last_wait_start_time = self.env.now
        self._set_status(AGVStatus.WAITING)

        # Request charging station resource
        yield from self._request_charging_station_resource(charging_station)

        # Finish waiting and begin charging
        waiting_time = self.env.now - self.last_wait_start_time
        self.metrics.waiting_time_s += waiting_time

        # Update AGV status
        self._set_status(AGVStatus.CHARGING)
        self.last_charging_start_time = self.env.now

        # Compute charging time
        time_to_full = (100.0 - self.state.battery_soc.level) / (
            self.config.battery_charge_rate
        )
        if charging_time is None:
            charge_time = time_to_full
        else:
            charge_time = min(time_to_full, charging_time)
        yield self.env.timeout(charge_time)

        # Charging is complete, update metrics and attributes
        self.state.battery_soc.put(charge_time * self.config.battery_charge_rate)
        self.metrics.charging_time_s += self.env.now - self.last_charging_start_time
        self.metrics.num_charging_visits += 1
        self.last_charging_start_time = None

    def _pick_items(self, task: Task):
        """Request to access resource at pick station and perform picking"""

        # AGV starts waiting for pick station resource
        self.last_wait_start_time = self.env.now
        self._set_status(AGVStatus.WAITING)

        # Request a resource at the picking station
        yield from self._request_pick_station_resource(task.picking_location)

        # Finish waiting after the resource is obtained
        waiting_time = self.env.now - self.last_wait_start_time
        self.metrics.waiting_time_s += waiting_time

        # Update AGV Status
        self._set_status(AGVStatus.PICKING)

        # Sample picking time
        picking_time = self.rng.gamma(
            self.config.picking_time_shape,
            self.config.picking_time_scale,
        )
        yield self.env.timeout(picking_time)

    def run(self):
        """
        Main AGV simulation loop
        """

        # Ensure that the initial status is IDLE and logged
        self._set_status(AGVStatus.IDLE)

        while True:
            ##################
            # AGV IDLE STATE #
            ##################

            # Request task assignment if current_task is None and AGV is IDLE
            if self.state.current_task is None and self.state.status == AGVStatus.IDLE:
                yield self.request_task_assignment
                # Reset event for next cycle
                self.request_task_assignment = self.env.event()

            # Check if the assigned task is None
            task = self.state.current_task
            if task is None:
                continue  # AGV continues to wait for task assignment

            # Case: When the assigned task is not None
            ############################
            # AGV HAS AN ASSIGNED TASK #
            ############################

            # Update AGV idle time
            # compute idle time since last idle start
            if self.last_idle_start_time is not None:
                idle_time = self.env.now - self.last_idle_start_time
                self.metrics.idle_time_s += idle_time
            self.last_idle_start_time = None

            # Start measuring the busy time
            self.last_busy_start_time = self.env.now

            # Update task status
            task.status = TaskStatus.IN_PROGRESS

            ####
            # Task Part 1: Move from current position to Storage Cell
            task_part_1_path = self.warehouse.shortest_path(
                self.state.current_position, task.pod_location
            )
            # Tell the AGV to follow the path
            # Follow Path function updates the time attributes and metrics
            #   after each segment on the path is convered
            yield from self._follow_path(task_part_1_path, with_pod=False)

            ####
            # Task Part 2: Perform Pod Retrieval at Storage Cell
            # Tell the AGV to retrieve pod
            start_retrieval_time = self.env.now
            yield from self._retrieve_pod()

            task.metrics.retrieval_time_s = self.env.now - start_retrieval_time

            ####
            # Task Part 3: Move from Storage Cell to assigned Pick Station
            task_part_3_path = self.warehouse.shortest_path(
                task.pod_location, task.picking_location
            )
            # Tell the AGV to follow the path
            yield from self._follow_path(task_part_3_path, with_pod=True)

            ####
            # Task Part 4: Get access to picking station and
            # perform Picking at the pickstation
            start_picking_time = self.env.now
            yield from self._pick_items(task)

            task.metrics.picking_time_s = self.env.now - start_picking_time

            ####
            # Task Part 5: Move from Pick Station back to Storage Cell
            task_part_5_path = self.warehouse.shortest_path(
                task.picking_location, task.pod_location
            )
            yield from self._follow_path(task_part_5_path, with_pod=True)

            ####
            # Task Part 6: Perform Pod Storage at Storage Cell
            # Tell AGV to store pod
            start_storing_time = self.env.now
            yield from self._store_pod()

            task.metrics.storage_time_s += self.env.now - start_storing_time

            # The task is complete so
            # Update task state
            task.status = TaskStatus.COMPLETE
            task.complete_time = self.env.now
            task.metrics.cycle_time_s = task.complete_time - task.release_time

            # Update AGV state and metrics
            self.metrics.tasks_completed += 1
            busy_time = task.complete_time - self.last_busy_start_time
            self.metrics.busy_time_s += busy_time
            self.state.current_task = None

            # As soon as the pod is stored back, check if the AGV needs charging
            if self._needs_charging():
                #########################
                # AGV REQUIRES CHARGING #
                #########################
                # Find the nearest charging station
                nearest_charging_station, _ = self.warehouse.nearest_node_of_type(
                    self.state.current_position, NodeType.CHARGING
                )
                path_to_charger = self.warehouse.shortest_path(
                    self.state.current_position, nearest_charging_station
                )
                # Tell AGV to follow the above path
                yield from self._follow_path(path_to_charger, with_pod=False)

                # AGV has reached the charger
                yield from self._charge_agv(nearest_charging_station)

            #################################
            # AGV DOES NOT REQUIRE CHARGING #
            #################################

            ####
            # Task Part 7: Storage cell to Parking Station
            # To do: Add capacity to parking stations and
            # send AGV to nearest parking station with available capacity
            parking_station, _ = self.warehouse.nearest_node_of_type(
                self.state.current_position, NodeType.PARKING
            )
            task_part_7_path = self.warehouse.shortest_path(
                self.state.current_position, parking_station
            )
            yield from self._follow_path(task_part_7_path, with_pod=False)

            # Set status to IDLE
            self._set_status(AGVStatus.IDLE)
