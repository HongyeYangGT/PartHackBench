\
\
\
\
\
\
   
from __future__ import annotations
import copy
from .certifier import Certifier
from .environment import replay
from .schema import Action, Trajectory
from .tasks import honest_trajectory


def _flatten(macros):
    return [copy.deepcopy(action) for macro in macros for action in macro]


def _inverse_from_event(event):
    action = event.action
    if action.op == "create":
        return Action("delete", action.entity_type, action.entity_id)
    if action.op == "delete":
        return Action("restore", action.entity_type, action.entity_id)
    if action.op == "restore":
        return Action("delete", action.entity_type, action.entity_id)
    if action.op == "update":
        before = event.diff["before"]["entities"][action.entity_type][action.entity_id]
        after = event.diff["after"]["entities"][action.entity_type][action.entity_id]
        changed = [key for key in action.patch if before.get(key) != after.get(key)]
        return Action("update", action.entity_type, action.entity_id,
                      patch={key: before[key] for key in changed})
    raise ValueError("goal revision is not inverted inside a fixed-goal fixture")


def construct_protocol_witness(task, witness_count=None):
    if task.split != "development":
        raise ValueError("protocol witnesses are available only for development tasks")
    honest = honest_trajectory(task)
    replay(task, honest)
    remaining = task.m - task.honest_count
    n = remaining if witness_count is None else int(witness_count)
    if n < 1 or n > remaining:
        raise ValueError("witness_count must select at least one remaining milestone")
    extra = _flatten(task.milestone_actions[task.honest_count:task.honest_count + n])
    peak = Trajectory(task.id, "protocol-peak", list(honest.actions) + extra,
                      provenance="protocol-fixture")
    replay(task, peak)
    extension_events = peak.events[len(honest.events):]
    inverses = [_inverse_from_event(event) for event in reversed(extension_events)
                if event.actor == "agent"]
    candidate = Trajectory(task.id, "protocol-witness",
                           list(honest.actions) + extra + inverses,
                           provenance="protocol-fixture")
    replay(task, candidate)
    return candidate


def construct_rollback_fixture(task):
                                                                             
    if not task.rollback_eligible:
        raise ValueError("GoalPatch tasks are excluded from strict rollback fixtures")
    honest = honest_trajectory(task)
    replay(task, honest)
    base = Certifier().certify(task, honest)
    for event in reversed(honest.events):
        if event.actor != "agent" or event.action.op == "revise_goal" or not event.diff:
            continue
        try:
            inverse = _inverse_from_event(event)
        except Exception:
            continue
        candidate = Trajectory(task.id, "rollback-fixture",
                               list(honest.actions) + [inverse],
                               provenance="protocol-fixture",
                               metadata={"kind": "rollback-fixture"})
        cert = Certifier().certify(task, candidate)
        if cert.replay_valid and cert.goal_version == base.goal_version and cert.pstate < base.pstate:
            return candidate
    raise ValueError(f"no strict rollback fixture found for {task.id}")
