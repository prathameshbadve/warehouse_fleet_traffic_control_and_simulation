"""
Contains functions to initialize the simpy resources required for the simulation.
"""

from typing import Dict, List

import simpy


def initialize_pick_station_resources(
    env: simpy.Environment,
    pick_stations: List[str],
    capacity: int,
) -> Dict[str, simpy.Resource]:
    """Creates pick station simpy resources"""

    pick_station_resources = {}

    for ps in pick_stations:
        resource = simpy.Resource(env, capacity=capacity)
        pick_station_resources[ps] = resource

    return pick_station_resources


def initialize_charging_station_resources(
    env: simpy.Environment,
    charging_stations: List[str],
    capacity: int,
) -> Dict[str, simpy.Resource]:
    """Creates charging station simpy resources"""

    charging_station_resources = {}

    for cs in charging_stations:
        resource = simpy.Resource(env, capacity=capacity)
        charging_station_resources[cs] = resource

    return charging_station_resources


# def initialize_parking_station_resources(
#     env: simpy.Environment,
#     parking_stations: List[str],
# ) -> Dict[str, simpy.Resource]:
#     """Creates parking station simpy resources"""

#     parking_station_resources = {}

#     for pk in parking_stations:
#         resource = simpy.Resource(env, capacity=20)
#         parking_station_resources[pk] = resource

#     return parking_station_resources
