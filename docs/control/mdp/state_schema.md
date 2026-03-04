# MDP State Schema (MVP Freeze)

### Purpose
This document defines the frozen MVP state contract passed from the discrete-event simulation (DES) to the decision layer (policy/optimizer) at each decision epoch $\tau_k$. This schema is the single source of truth for all assignment policies and the assignment optimizer.

The schema is designed for assignment-only MVP. Routing optimization and explicit congestion features are out of scope for this freeze.

## 1. Decision State Object: DispatchState
At decision time 
$t = \tau_k$, the policy receives:

### 1.1 Global fields
- time_s: float - Current simulation time in seconds.
- decision_id: str - Unique identifier for this decision epoch (for logging/replay).
- graph_id: str - Identifier for the active warehouse graph configuration (for reproducibility).

## 2. Robot Snapshot: RobotSnapshot
A list/dict over robots indexed by robot_id.

### 2.1 Required fields
- robot_id: str
- node_id: str - Current node in the warehouse graph $V$. \
<b>MVP constraint:</b> if robot is traversing an edge, DES must project it to a node representation consistent with downstream execution (e.g., “next node” or “current node”). The policy does not reason about partial edge progress in MVP.

- status: str $\in$ {idle, busy, charging, blocked} - Current robot mode.
- soc: float in [0,1] - Battery state-of-charge.
- current_task_id: Optional[str] - Null if none.
- earliest_available_time_s: float - Predicted earliest time the robot can begin a newly assigned task (dispatchable time). MVP rule: for idle robots, equals time_s.

### 2.2 Optional fields (allowed, not required for MVP)
- last_completed_task_id: Optional[str]
- home_node_id: Optional[str] - Default waiting/staging node.
- metadata: dict - Arbitrary extra info for debugging/logging; policies must not depend on it for correctness.

## 3. Task Snapshot: TaskSnapshot
A list/dict over tasks indexed by task_id.

### 3.1 Required fields
- task_id: str
- pickup_node_id: str
- drop_node_id: str
- release_time_s: float - Task becomes available at this time.
- due_time_s: float - Soft SLA deadline (tardiness penalized beyond this).
- hard_deadline_s: float - Hard SLA deadline (violation penalty beyond this).
- priority_weight: float
- Weight $w_i$ applied to tardiness.
- status: str ∈ {pending, assigned, in_progress, completed, cancelled} \
<b>MVP constraint:</b> The assignment decision considers only tasks that are currently feasible candidates (see Candidate Set rules below).

- assigned_robot_id: Optional[str] - Null if not assigned.
- num_reassignments: int - Count of prior reassignments (for future churn penalties; MVP may ignore).

### 3.2 Derived fields (not included; must be derived by policy if needed)
- Slack: $D_i - \hat{C}_{ir}(t)$
- Urgency classes, etc.

## 4. Candidate Sets (Frozen Rules)
The policy must build candidate sets $I$ (tasks) and $R$ (robots) from the snapshot using the following MVP rules.

### 4.1 Candidate Tasks $I$
Include a task $i$ iff:
- status == pending
- release_time_s <= time_s
- assigned_robot_id is None \
<b>MVP note:</b> reassignment is out of scope; assigned tasks are excluded.

### 4.2 Candidate Robots $R$
Include a robot $r$ iff:
- status == idle
- earliest_available_time_s == time_s
- current_task_id is None \
<b>MVP note:</b> assigning to “soon available” robots is out of scope.

## 5. Travel/Service Time Oracles (Interface Expectations)
The state schema does not carry routing details, but the assignment optimizer requires deterministic estimators:
- $\hat{T}$(u_node_id, v_node_id, t) \
Estimated travel time in seconds from node $u$ to $v$ at time $t$. \
<b>MVP requirement:</b> time-independent estimate using mean edge weights is sufficient.

- S_pick_hat(task_id) \
Estimated pickup service time (seconds). MVP may be constant.

- S_drop_hat(task_id) \
Estimated drop service time (seconds). MVP may be constant.

These are provided by the environment/control integration layer (not embedded in the state object).

## 6. Backward Compatibility Policy
Any addition of new fields must:
- be optional by default
- not change semantics of existing required fields
- not break candidate set rules unless explicitly versioned

## 7. Versioning
state_schema_version: "mvp_v1" (implicit by file location; may be added explicitly in the object for safety)