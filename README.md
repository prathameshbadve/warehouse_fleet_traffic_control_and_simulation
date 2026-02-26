# Warehouse Fleet Traffic Control and Simulation

This project models an automated warehouse with AGV (Automated Guided Vehicle) traffic, task dispatching, charging behavior, and station-level contention using a discrete-event simulation (SimPy).

## Project Goal

Build a simulation framework that can evaluate warehouse fleet performance under different operational policies, fleet sizes, and workload patterns before deploying changes in production.

The objective is to answer questions like:
- How many AGVs are needed for a target throughput?
- When does charging become a bottleneck?
- How do dispatch cadence and station capacities affect cycle time and utilization?

## Business Problem

In high-volume fulfillment centers, poor AGV coordination creates measurable cost and service risk:
- Late orders due to long queueing and cycle times
- Underutilized or overutilized fleet assets
- Charging congestion that silently reduces throughput
- Difficulty validating policy changes safely on live operations

A simulation-first workflow reduces experimentation risk by letting teams test fleet, charging, and task-arrival scenarios offline.

## Methodology

The simulator combines four components:
- Warehouse network model: A graph-based layout of highways, aisles, storage cells, pick stations, parking, and charging nodes.
- Stochastic task generation: Tasks are released over time with configurable arrival rates and priority mix.
- AGV process model: Each AGV follows a state machine (`idle`, `moving`, `waiting`, `picking`, `charging`, etc.) with battery drain/charge dynamics.
- Dispatch and resource constraints: Pending tasks are periodically assigned to idle AGVs; pick and charging stations are modeled as finite-capacity SimPy resources.

Metrics are collected continuously and summarized at run end, including:
- Tasks generated/completed
- Throughput and cycle-time distribution (avg/median/p95)
- AGV utilization, waiting time, charging time, and final SOC
- Station-level queue pressure indicators

## Insights

This framework is designed to surface operational insights such as:
- Throughput collapse points when task arrival exceeds effective service capacity
- Charging-policy tradeoffs (higher safety thresholds reduce outage risk but increase charging downtime)
- Station bottlenecks (pick vs charging) as primary drivers of queueing and SLA risk
- Fleet sizing thresholds where additional AGVs stop improving throughput due to shared resource contention

From the single-AGV sanity-check script, blocking all charging stations in a short test created clear waiting buildup (about 150s AGV waiting time), confirming waiting and charging logic are functioning and observable.

## Run

Main simulation:

```bash
python scripts/run_simulation.py --config config/default_warehouse_config.yaml --n-agvs 20 --hours 4
```

Single-AGV sanity check:

```bash
python scripts/run_single_agv_sanity_check.py --num-tasks 8 --inter-arrival-seconds 30
```
