"""
Base task assignment strategy for assignment decision
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
from dataclasses import dataclass

import numpy as np

from src.simulation.agvs import AGV
from src.simulation.tasks import Task
from src.warehouse.graph import WarehouseGraph


@dataclass
class AssignmentDecision:
    """Represents a single task-to-AGV assignment decision."""

    task: Task
    agv: AGV
    expected_completion_time: float = None
    priority_score: float = None


class AssignmentPolicy(ABC):
    """
    Base class for task assignment policies
    """

    def __init__(self, warehouse: WarehouseGraph):
        self.warehouse = warehouse

    @abstractmethod
    def assign(
        self, pending_tasks: List[Task], idle_agvs: List[AGV], current_time: float
    ):
        """
        Assign pending tasks to idle AGVs.

        Args:
            pending_tasks: List of tasks awaiting assignment
            idle_agvs: List of available AGVs
            current_time: Current simulation time

        Returns:
            List of assignment decisions (task, agv) pairs
        """

        pass
