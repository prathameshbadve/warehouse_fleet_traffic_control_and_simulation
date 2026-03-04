# Assignment Problem Definition (MVP)

## Purpose
This document defines the **optimization problem** solved by the assignment module at each dispatch decision epoch. The solver produces a set of task–robot pairs that minimize the **frozen MVP assignment cost model** defined in `control/mdp/cost_model.md`.

**Scope (MVP):**
- Assignment only (no explicit routing optimization).
- No reassignment (only unassigned, released tasks are eligible).
- Only currently idle robots are eligible.
- Single-task assignment per robot per decision epoch.

---

## 1. Sets and Indices

At decision time $t = \tau_k$:

- Candidate tasks:
  $$
  I(t) = \{ i : \text{task } i \text{ is released, pending, and unassigned at time } t \}
  $$
  Contracted eligibility rules are defined in `control/mdp/state_schema.md`.

- Candidate robots:
  $$
  R(t) = \{ r : \text{robot } r \text{ is idle and dispatchable at time } t \}
  $$
  Contracted eligibility rules are defined in `control/mdp/state_schema.md`.

- Admissible task–robot pairs:
  $$
  \mathcal{P}(t) \subseteq I(t) \times R(t)
  $$
  In MVP, all combinations are admissible unless explicitly ruled out by hard feasibility filters (e.g., battery infeasible). If any hard feasibility filters are used, they must be deterministic and documented in this file (Section 6).

---

## 2. Decision Variables

Binary assignment variables:
$$
x_{ir} =
\begin{cases}
1 & \text{if task } i \text{ is assigned to robot } r \\
0 & \text{otherwise}
\end{cases}
\quad \forall (i,r) \in \mathcal{P}(t)
$$

---

## 3. Objective Function

Minimize total assignment cost:
$$
\min_{x} \sum_{(i,r)\in \mathcal{P}(t)} C_{ir}(t)\; x_{ir}
$$

Where $C_{ir}(t)$ is the **frozen pairwise cost** computed per `control/mdp/cost_model.md`.

### 3.1 Cost model reference (MVP)
The cost matrix $C_{ir}(t)$ must be computed using:
- Predicted completion time $\widehat{C}_{ir}(t)$
- Soft tardiness penalty beyond $D_i$
- Hard deadline proxy penalty beyond $H_i$
- Idle-time proxy (travel-to-pickup)
- Congestion and churn terms are set to 0 for MVP

See `control/mdp/cost_model.md` for the exact formula and parameter contract.

---

## 4. Constraints

### 4.1 Task assignment uniqueness
Each task is assigned to at most one robot:
$$
\sum_{r \in R(t) : (i,r)\in \mathcal{P}(t)} x_{ir} \le 1
\quad \forall i \in I(t)
$$

### 4.2 Robot assignment uniqueness
Each robot is assigned to at most one task per dispatch call:
$$
\sum_{i \in I(t) : (i,r)\in \mathcal{P}(t)} x_{ir} \le 1
\quad \forall r \in R(t)
$$

### 4.3 Variable domain
$$
x_{ir} \in \{0,1\} \quad \forall (i,r) \in \mathcal{P}(t)
$$

---

## 5. Output Mapping to Action Schema

The optimizer returns a set of pairs:
$$
M(t) = \{(i,r) \in \mathcal{P}(t) : x_{ir}=1\}
$$

This is translated into `DispatchAction.assignments` as a list of:
- `(task_id=i, robot_id=r)` for all $(i,r)\in M(t)$

The action must satisfy the hard contract in `control/mdp/action_schema.md`:
- no duplicate tasks or robots
- only candidate tasks/robots
- no reassignment (MVP)

---

## 6. Feasibility Filters (Optional, but Must Be Explicit)

MVP defaults to **no hard feasibility filters** beyond candidate set rules.

If you introduce feasibility filters in MVP (allowed, but discouraged unless necessary), they must be:
- deterministic given state + oracles
- applied before optimization to form $\mathcal{P}(t)$
- logged (count of filtered pairs)

Examples (ONLY if needed):
- Battery feasibility: require predicted energy to complete task $\le$ available SOC margin
- Forbidden zones: robot cannot enter certain areas

If used, define the filter as:
$$
(i,r) \in \mathcal{P}(t) \iff \text{Eligible}(i,r,t)=1
$$

and specify the exact rule and parameters here.

---

## 7. Solver Class (Implementation-Agnostic)

The optimization problem is a **minimum-cost bipartite matching with optional unbalanced sides**.

Two equivalent solution styles are acceptable:

### 7.1 Hungarian / Assignment solver (square matrix style)
- If $|I(t)| \ne |R(t)|$, add dummy tasks or dummy robots with cost 0 (or a configurable “no-op” cost).
- Selects a complete matching in the padded problem; discard dummy matches.

### 7.2 Min-cost flow formulation (recommended for flexibility)
- Source → robots edges capacity 1
- Robots → tasks edges cost $C_{ir}(t)$, capacity 1
- Tasks → sink edges capacity 1
- Send up to $\min(|I|,|R|)$ units of flow
- Produces a (possibly partial) matching directly

**MVP expectation:** either approach is fine; solver choice must be transparent and deterministic.

---

## 8. Determinism and Tie-Breaking (Hard Requirement)

For reproducible comparisons across policies:
- The solver must be deterministic given the same cost matrix.
- If there are ties in cost, apply a deterministic tie-break rule, e.g.:
  1) smaller task_id lexical
  2) then smaller robot_id lexical

This is important when benchmarking with Common Random Numbers (CRN).

---

## 9. Edge Cases (Required Behavior)

### 9.1 No candidates
- If $I(t)=\emptyset$ or $R(t)=\emptyset$: return empty assignment list.

### 9.2 More tasks than robots
- Assign up to $|R(t)|$ tasks (best according to objective).

### 9.3 More robots than tasks
- Assign all tasks (each to at most one robot), leaving extra robots idle.

### 9.4 Infeasible pairs due to filters
- If feasibility filters remove all pairs, return empty assignment list.

---

## 10. Complexity Targets (MVP Guidance)
Let $n=\max(|I(t)|,|R(t)|)$.

- Hungarian: $O(n^3)$
- Min-cost flow: depends on implementation; typically fast enough for MVP scales

For typical MVP scales (tens to low hundreds), both are acceptable.

---

## 11. Versioning
- `assignment_problem_version: "mvp_v1"`
- Must remain consistent with:
  - `control/mdp/state_schema.md` (candidate sets)
  - `control/mdp/action_schema.md` (action constraints)
  - `control/mdp/cost_model.md` (pairwise cost)

Any breaking change requires a new version tag.