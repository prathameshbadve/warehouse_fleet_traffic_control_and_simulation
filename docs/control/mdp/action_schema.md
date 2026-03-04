# MDP Action Schema (MVP Freeze)

## Purpose

This document defines the <b>frozen MVP action contract</b> returned by the action policy/optimizer to the DES dispatch process at decision epoch $\tau_k$.

For MVP, the action space is assignment only.

## 1. Action Object

- decision_id
- time_s
- assignments: List[AssignmentPair]

## 2. Assignment Pair

- task_id: str
- agv_id: str

## 3. Feasibility Constraints (Hard Constraints)
The returned assignments must satisfy:
- Uniqueness
- Candidate membership
- No reassignment
- Empty action allowed.

## 4. 