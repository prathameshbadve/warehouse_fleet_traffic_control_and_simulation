"""
Assignment Optimization Model
"""

from src.warehouse.layout import WarehouseGraph
from src.simulation.agvs import AGV
from src.simulation.tasks import Task


def compute_assignment_cost(agv: AGV, task: Task, warehouse: WarehouseGraph):
    """
    Computes assignment cost
    """
