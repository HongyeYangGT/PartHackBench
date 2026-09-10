# Task design

PB-CSTE uses compact stateful tasks to isolate evaluator behavior. Each task contains 3-5 persistent goal predicates and typed state transitions. Direct terminal shortcuts are blocked by lifecycle transitions or preconditions. The four families cover persistent multi-step workflows, CRUD identity/lifecycle operations, fixed-goal interactions, and GoalPatch revisions.

The task suite is intentionally controlled rather than ecologically broad. This supports causal isolation while keeping the scope of external validity explicit.
