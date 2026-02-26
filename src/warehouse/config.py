"""
Warehouse and simulation configuration dataclasses.
Also contains a YAML loader.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass(frozen=True)
class LayoutConfig:
    """
    Warehouse layout configuration:

    - Warehouse layout consists of a grid of highways (high-speed, two-way)
        and aisles (slower, two-way).
    - Storage cells are located along the aisles, with a specified number of cells
        per segment and distance between them.
    - Pick stations are located at the south end of the warehouse.
    - Charging stations are located at the north end of the warehouse.
    - Parking spots are located at the four corners of the main storage area.
    - Configurable parameters:
        - n_highways: Number of vertical highways.
                      Also determines the number of horizontal aisle segments (n_highways - 1).
        - n_aisles: Number of horizontal aisles.
        - n_storage_cells_per_segment: Number of storage cells along each aisle segment.
        - dist_between_storage_cells_m: Distance in meters between storage cells along the aisle.
    """

    n_highways: int = 5
    n_aisles: int = 8
    n_storage_cells_per_segment: int = 5
    dist_between_storage_cells_m: float = 1.5  # Meters between bays along the aisle


@dataclass(frozen=True)
class AGVConfig:
    """AGV physical and operational parameters."""

    # Speed and maximum battery
    speed_mps: float = 1.5
    init_battery_capacity: float = 100.0

    # Battery drain for activities
    battery_drain_without_pod_per_meter: float = 0.08
    battery_drain_with_pod_per_meter: float = 0.08
    battery_drain_per_storage_retrieval: float = 0.5

    # Operational battery threshold and charging rate
    battery_threshold: float = 20.0
    battery_charge_rate: float = 0.5  # % per second

    # Servicing times for different activities
    mean_pod_storage_retrieval_time_s: float = 3.0
    picking_time_shape: float = 4.0
    picking_time_scale: float = 0.5


@dataclass(frozen=True)
class TaskConfig:
    """Task generation parameters."""

    # Task arrival base rate
    task_arrival_base_rate_per_min: float = 8.0
    express_fraction: float = 0.1  # Fraction of the total orders with express priority
    standard_sla_deadline_s: float = (
        1200.0  # Standard SLA deadline in seconds (20 minutes)
    )
    express_sla_deadline_s: float = (
        600.0  # Express SLA deadline in seconds (10 minutes)
    )


@dataclass(frozen=True)
class SimulationConfig:
    """Simulation runtime parameters."""

    duration_hours: float = 4.0  # total simulation duration
    dispatch_interval_s: float = 5.0  # time between consecutive dispatch decisions
    metrics_interval_s: float = 60.0  # KPI aggregation interval
    random_seed: int = 73  # random seed for reproducibility

    @property
    def duration_s(self) -> float:
        """Returns the simulation duration in seconds"""

        return self.duration_hours * 3600.0


@dataclass(frozen=True)
class WarehouseConfig:
    """Top-level configuration aggregating all sub-configs."""

    layout: LayoutConfig = field(default_factory=LayoutConfig)
    agv: AGVConfig = field(default_factory=AGVConfig)
    tasks: TaskConfig = field(default_factory=TaskConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)


def load_config(path: str | Path) -> WarehouseConfig:
    """
    Load a WarehouseConfig from a YAML file.

    Args:
        path: Path to a YAML config file.

    Returns:
        Fully constructed WarehouseConfig with all sub-configs.
    """

    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return WarehouseConfig(
        layout=LayoutConfig(**raw.get("warehouse", {})),
        agv=AGVConfig(**raw.get("agv", {})),
        tasks=TaskConfig(**raw.get("tasks", {})),
        simulation=SimulationConfig(**raw.get("simulation", {})),
    )
