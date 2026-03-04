# Warehouse Fleet Traffic Control and Simulation


## Background

Modern autonomous fleets (warehouse robots, delivery vehicles, compute jobs) operate in congested, stochastic environments with:
- Dynamic Task Arrival
- Battery / energy constraints
- Shared infrastructure bottlenecks
- Delayed and noisy state information

## Problem Statement

This project aims to analyze the operations in a warehouse fulfillment center. It models an automated warehouse with AGV (Automated Guided Vehicle) traffic, task dispatching, charging behavior, and station-level contention using discrete-event simulation. Different task assignment and routing policies are compared to find the best fit for the warehouse operations.

## Goal

Build a simulation framework that can evaluate warehouse fleet performance under different operational policies, fleet sizes, and workload patterns before deploying changes in production.

The objective is to answer questions like:
- How many AGVs are needed for achieving 95% SLA compliance?
- When does charging become a bottleneck?
- How do dispatch cadence and station capacities affect cycle time and utilization?
- What is the best task disaptching strategy (greedy, static optimization, rolling-horizon)?

## Business Problem

In high-volume fulfillment centers, poor AGV coordination creates measurable cost and service risk:
- Late orders due to long queueing and cycle times
- Underutilized or overutilized fleet assets
- Charging congestion that silently reduces throughput
- Space congestion due to high traffic in aisles leading to gridlocks
- Difficulty validating policy changes safely on live operations

A simulation-first workflow reduces experimentation risk by letting teams test fleet, charging, and task-arrival scenarios offline.

## Methodology

The simulator combines four components:
- <b>Warehouse network model:</b> A graph-based layout of highways, aisles, storage cells, pick stations, parking, and charging nodes.
- <b>Stochastic task generation:</b> Tasks are released over time with configurable arrival rates and priority mix.
- <b>AGV process model:</b> Each AGV follows a state machine (`idle`, `moving`, `waiting`, `retrieving`, `picking`, `storing`, `charging`, etc.) with battery drain/charge dynamics.
- <b>Dispatch and resource constraints:</b> Pending tasks are periodically assigned to idle AGVs; pick and charging stations are modeled as finite-capacity SimPy resources.

Metrics are collected continuously and summarized at run end, including:
- Tasks generated/completed
- Throughput and cycle-time distribution (avg/median/p95)
- AGV utilization, waiting time, charging time, and final SOC
- Station-level queue pressure indicators

## Run

Main simulation:

```bash
# 1. Install required packages
pip install -r requirements.txt

# 2. Run simulation with default config
python scripts/run_simulation.py --config config/default_warehouse_config.yaml --n-agvs 20 --hours 4
```

The simulation results are stored in "data/output/results/"
<!-- Single-AGV sanity check:

```bash
python scripts/run_single_agv_sanity_check.py --num-tasks 8 --inter-arrival-seconds 30
``` -->

## Insights

This framework is designed to surface operational insights such as:
- Throughput collapse points when task arrival exceeds effective service capacity
- Charging-policy tradeoffs (higher safety thresholds reduce outage risk but increase charging downtime)
- Station bottlenecks (pick vs charging) as primary drivers of queueing and SLA risk
- Fleet sizing thresholds where additional AGVs stop improving throughput due to shared resource contention

From the single-AGV sanity-check script, blocking all charging stations in a short test created clear waiting buildup (about 150s AGV waiting time), confirming waiting and charging logic are functioning and observable.