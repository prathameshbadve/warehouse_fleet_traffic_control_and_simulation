"""
Script to read warehouse config and create a warehouse layout diagram
"""

from src.warehouse.config import load_config
from src.warehouse.layout import GridLayoutGenerator
from src.warehouse.visualization import plot_warehouse


def main():
    """Main runner function"""

    warehouse_config = load_config(
        "/Users/pbadve/Documents/My Projects/Portfolio_Projects/warehouse_fleet_traffic_control_and_simulation/config/default_warehouse_config.yaml"
    )
    layout_gen = GridLayoutGenerator(warehouse_config)

    warehouse_layout = layout_gen.generate()

    warehouse_diagram = plot_warehouse(warehouse_layout)

    warehouse_diagram.savefig("data/diagrams/warehouse_layout.png")


if __name__ == "__main__":
    main()
