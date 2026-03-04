# Assignment Cost Model (MVP Freeze)

## Purpose

This document defines the frozen pairwise assignment cost $C_{it}(t)$ used by the assignment problem optimizer. The optimizer selects a matching that minimizes the sum of these costs across all assigned pairs.

This model is aligned with the overall project objective:

$$
\alpha \cdot \text{tardiness} + \beta \cdot \text{robot idle} + \gamma \cdot \text{congestion} + \delta \cdot \text{reassignment / churn}
$$

## 1. Candidate Pair Definition
- $i \in I$: Candidate tasks
- $r \in R$: Candidate AGVs

## 2. Required Estimators
- $\hat{T}(u, v)$: estimated travel time from node $u$ to node $v$
- $\hat{S}_{i}^{pick}$: estimated picking service time
- $\hat{S}_{i}^{drop}$: estimated dropoff time

