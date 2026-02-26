"""
Task Generator Object
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List

import numpy as np
import simpy

from src.warehouse.config import TaskConfig
from src.warehouse.graph import WarehouseGraph, NodeType


class TaskPriority(str, Enum):
    """Valid Task Priorities"""

    STANDARD = "standard"
    EXPRESS = "express"


class TaskStatus(str, Enum):
    """Valid Task Status"""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class TaskMetrics:
    """Object containing all Task Metrics"""

    cycle_time_s: float = 0.0
    wait_time_s: float = 0.0
    retrieval_time_s: float = 0.0
    picking_time_s: float = 0.0
    storage_time_s: float = 0.0
    delay_s: float = 0.0


@dataclass
class Task:
    """Represents one task in the simulation"""

    id: str
    pod_location: str
    picking_location: str
    priority: TaskPriority
    status: TaskStatus = TaskStatus.PENDING
    assigned_agv: str | None = None
    release_time: float | None = None
    assigned_time: float | None = None
    complete_time: float | None = None
    metrics: TaskMetrics = field(default_factory=TaskMetrics)


class TaskGenerator:
    """
    Generator object that samples inter-arrival times
    and creates tasks to be performed in the simulation.
    """

    def __init__(
        self,
        env: simpy.Environment,
        rng: np.random.Generator,
        warehouse: WarehouseGraph,
        config: TaskConfig,
    ):
        self.env = env
        self.rng = rng
        self.warehouse = warehouse
        self.config = config

        self.tasks: List[Task] = []
        self.pending_tasks: List[Task] = []
        self.failed_tasks: List[Task] = []

        self._task_counter: int = 0
        self._storage_nodes: List[str] = []
        self._pick_station_nodes: List[str] = []

    def _get_storage_nodes(self):
        """Gets the list of storage nodes from the warehouse graph"""

        if len(self._storage_nodes) == 0:
            self._storage_nodes = self.warehouse.nodes_by_type(NodeType.STORAGE)

        return self._storage_nodes

    def _get_pick_station_nodes(self):
        """Gets the list of pick stations from the warehouse graph"""

        if len(self._pick_station_nodes) == 0:
            self._pick_station_nodes = self.warehouse.nodes_by_type(
                NodeType.PICK_STATION
            )

        return self._pick_station_nodes

    def _create_task(self, creation_time: float) -> Task:
        """Creates a task object"""

        # Increment the task counter
        self._task_counter += 1

        # Set task id
        task_id = f"TSK_{self._task_counter:05d}"

        # Randomly assign express status to the task
        is_express = self.rng.random() < self.config.express_fraction
        priority = TaskPriority.EXPRESS if is_express else TaskPriority.STANDARD

        # Randomly pick a storage cell for pod retrieval
        storage_nodes = self._get_storage_nodes()
        pod_location = self.rng.choice(
            storage_nodes
        )  # To do: Add logic to ensure the storage node has a pod available for retrieval.
        # For now, we assume all storage nodes are always available.

        # Randomly pick a pick station
        pick_station_nodes = self._get_pick_station_nodes()
        picking_location = self.rng.choice(pick_station_nodes)

        # Create the task object
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

    def run(self):
        """Simpy generator process: samples inter-arrival times, creates task"""

        while True:
            task_arrival_rate_per_min = self.config.task_arrival_base_rate_per_min
            inter_arrival_mean_s = 60 / task_arrival_rate_per_min
            inter_arrival_time = self.rng.exponential(inter_arrival_mean_s)
            yield self.env.timeout(inter_arrival_time)

            self._create_task(self.env.now)

    def get_and_clear_pending(self) -> List[Task]:
        """Returns the pending tasks and clears the buffer"""

        pending_tasks = list(self.pending_tasks)
        self.pending_tasks.clear()

        return pending_tasks
