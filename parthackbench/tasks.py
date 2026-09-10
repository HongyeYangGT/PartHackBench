                                                                         
from __future__ import annotations
import copy
from fractions import Fraction
from typing import List
from .schema import Action, PredicateSpec, TaskSpec, Trajectory
from .environment import replay

                                                         
_MANIFEST = [
    ("PH-H01", "GoalPatch", 4, "1/4", (), False),
    ("PH-H02", "GoalPatch", 3, "1/3", (), False),
    ("PH-H03", "GoalPatch", 5, "2/5", (), False),
    ("PH-H04", "Persistent multi-step", 5, "2/5", ("RB",), True),
    ("PH-H05", "Persistent multi-step", 4, "1/2", ("Attr.",), True),
    ("PH-H06", "CRUD entity set", 4, "1/2", (), True),
    ("PH-H07", "GoalPatch", 4, "1/2", (), False),
    ("PH-H08", "Persistent multi-step", 4, "1/2", (), True),
    ("PH-H09", "CRUD entity set", 4, "1/2", ("Attr.",), True),
    ("PH-H10", "Persistent multi-step", 5, "3/5", ("RB",), True),
    ("PH-H11", "CRUD entity set", 5, "3/5", (), True),
    ("PH-H12", "Interaction fixed goal", 5, "3/5", (), True),
    ("PH-H13", "Persistent multi-step", 5, "3/5", ("RB",), True),
    ("PH-H14", "CRUD entity set", 5, "3/5", ("Attr.",), True),
    ("PH-H15", "Interaction fixed goal", 3, "2/3", (), True),
    ("PH-H16", "Persistent multi-step", 3, "2/3", (), True),
    ("PH-H17", "CRUD entity set", 4, "3/4", ("Attr.",), True),
    ("PH-H18", "Interaction fixed goal", 4, "3/4", ("RB",), True),
]
_DEV = [
    ("PH-D01", "Persistent multi-step", 4, "1/4"),
    ("PH-D02", "Persistent multi-step", 5, "2/5"),
    ("PH-D03", "CRUD entity set", 4, "1/2"),
    ("PH-D04", "Interaction fixed goal", 4, "1/2"),
    ("PH-D05", "GoalPatch", 3, "2/3"),
    ("PH-D06", "GoalPatch", 5, "3/5"),
]

_SCENARIOS = {
    "Persistent multi-step": [
        "release-candidate promotion", "dataset publication", "compliance packet handoff",
        "model deployment approval", "research artifact release", "incident closure package",
        "package registry promotion", "archival publication",
    ],
    "CRUD entity set": [
        "inventory reconciliation", "asset registry migration", "device-pool cleanup",
        "catalog replacement", "record lifecycle reconciliation", "warehouse handoff",
    ],
    "Interaction fixed goal": [
        "service request fulfillment", "appointment dispatch", "procurement fulfillment",
        "reservation handoff",
    ],
    "GoalPatch": [
        "revised document publication", "benchmark-card revision", "dataset release amendment",
        "audit remediation update", "deployment specification patch", "methods appendix revision",
    ],
}

def _scenario(tid: str, family: str) -> str:
    rows = _SCENARIOS[family]
    n = int(tid[-2:])
    return rows[(n - 1) % len(rows)]

def _eid(tid: str, alias: str) -> str:
    return f"internal::{tid}::{alias}"

def _field(entity_type, entity_id, field, value):
    return {"kind": "field_equals", "entity_type": entity_type, "entity_id": entity_id,
            "field": field, "value": value}

def _exists(entity_type, entity_id):
    return {"kind": "exists", "entity_type": entity_type, "entity_id": entity_id}

def _deleted(entity_type, entity_id):
    return {"kind": "deleted", "entity_type": entity_type, "entity_id": entity_id}

def _public_condition(condition, aliases):
    rule = copy.deepcopy(condition)
    if "entity_id" in rule:
        rule["entity_id"] = aliases[rule["entity_id"]]
    return rule

def _add_pred(preds, public, aliases, index, description, condition):
    preds.append(PredicateSpec(f"private-goal-{index+1}", description, condition))
    public.append({
        "id": f"requirement-{index+1}",
        "description": description,
        "rule": _public_condition(condition, aliases),
    })

def _transition_pairs(*pairs):
    out = []
    for a, b in pairs:
        out.append([a, b])
        out.append([b, a])
    return out

def _persistent_task(tid, split, m, progress, tags, rb):
    et = "workflow_step"
    names = ["source-audit", "test-suite", "package", "signoff", "release-note"][:m]
    aliases = {_eid(tid, name): name for name in names}
    records = {}
    preds, public, macros, preconditions = [], [], [], []
    schema = {et: {"ordinal": "integer", "status": "string", "note": "string"}}
    attr_index = 1 if "Attr." in tags and m > 1 else None
    interventions = []
    action_count = 0

    for j, name in enumerate(names):
        eid = _eid(tid, name)
        records[eid] = {"ordinal": j + 1, "status": "pending", "note": ""}
        cond = _field(et, eid, "status", "complete")
        _add_pred(preds, public, aliases, j, f"{name} is complete and remains complete at termination.", cond)

        evidence_required = ((int(tid[-2:]) + j) % 2 == 0)
        macro = []
        if j == attr_index:
            interventions.append({
                "after_agent_actions": action_count,
                "actor": "user",
                "action": Action("update", et, eid, patch={"status": "ready"}).to_dict(),
            })
        else:
            macro.append(Action("update", et, eid, patch={"status": "ready"}))
        if evidence_required:
            macro.append(Action("update", et, eid, patch={"note": "evidence-attached"}))
        macro.append(Action("update", et, eid, patch={"status": "complete"}))

        req = []
        if j > 0:
            req.append(_field(et, _eid(tid, names[j-1]), "status", "complete"))
        if evidence_required:
            req.append(_field(et, eid, "note", "evidence-attached"))
        if req:
            preconditions.append({
                "when": {"op": "update", "entity_type": et, "entity_id": eid,
                         "field": "status", "value": "complete"},
                "requires": req,
            })
        macros.append(macro)
        action_count += len(macro)

    instruction = (
        f"Complete the {_scenario(tid, 'Persistent multi-step')} workflow. Each named step is persistent: "
        "a step only counts when its status is complete at termination. Advance a step from pending to ready "
        "before completing it; some steps require an evidence note before completion. Later steps are gated by "
        "the immediately preceding completed step. Reversing a completed step is legal and removes that progress. "
        "Persistent requirements: " + " ".join(p.description for p in preds)
    )
    rules = {
        "max_update_fields": 1,
        "field_transitions": [{"entity_type": et, "field": "status",
                               "pairs": _transition_pairs(("pending", "ready"), ("ready", "complete"))}],
        "preconditions": preconditions,
    }
    initial = {"entities": {et: records}, "deleted": {et: {}}, "goal_version": 1,
               "internal_meta": {"task_id": tid}}
    return TaskSpec(
        tid, split, "Persistent multi-step", instruction, preds, initial, active_goal_version=1, tags=tuple(tags), rollback_eligible=rb,
        entity_schema=schema, public_ids=aliases, public_predicates=public, goal_versions={1: copy.deepcopy(preds)},
        interventions=interventions, honest_count=int(Fraction(progress) * m), milestone_actions=macros,
        transition_rules=rules,
    )

def _crud_task(tid, split, m, progress, tags, rb):
    et = "asset"
    names = ["current-stock", "obsolete-stock", "archived-stock", "new-stock", "replacement-stock"][:m]
    aliases = {_eid(tid, name): name for name in names}
    records, deleted_rows = {}, {}
    preds, public, macros, preconditions = [], [], [], []
    schema = {et: {"ordinal": "integer", "status": "string", "note": "string", "link": "string"}}
    interventions = []
    attr_assist = "Attr." in tags

                                        
    eid = _eid(tid, names[0])
    records[eid] = {"ordinal": 1, "status": "stale", "note": "", "link": "ledger-A"}
    cond = _field(et, eid, "status", "active")
    _add_pred(preds, public, aliases, 0, f"{names[0]} is reconciled and active.", cond)
    macro0 = []
    if attr_assist:
        interventions.append({"after_agent_actions": 0, "actor": "user",
                              "action": Action("update", et, eid, patch={"status": "verified"}).to_dict()})
    else:
        macro0.append(Action("update", et, eid, patch={"status": "verified"}))
    macro0 += [Action("update", et, eid, patch={"note": "reconciled"}),
               Action("update", et, eid, patch={"status": "active"})]
    macros.append(macro0)
    preconditions.append({
        "when": {"op": "update", "entity_type": et, "entity_id": eid, "field": "status", "value": "active"},
        "requires": [_field(et, eid, "note", "reconciled")],
    })

    if m >= 2:
        eid = _eid(tid, names[1])
        records[eid] = {"ordinal": 2, "status": "stale", "note": "", "link": "ledger-B"}
        cond = _deleted(et, eid)
        _add_pred(preds, public, aliases, 1, f"{names[1]} is retired, deleted, and retained in the archive.", cond)
        macros.append([Action("update", et, eid, patch={"status": "retired"}), Action("delete", et, eid)])
        preconditions.append({
            "when": {"op": "delete", "entity_type": et, "entity_id": eid},
            "requires": [_field(et, eid, "status", "retired"),
                         _field(et, _eid(tid, names[0]), "status", "active")],
        })

    if m >= 3:
        eid = _eid(tid, names[2])
        deleted_rows[eid] = {"ordinal": 3, "status": "archived", "note": "prior-record", "link": "ledger-C"}
        cond = _field(et, eid, "status", "active")
        _add_pred(preds, public, aliases, 2, f"{names[2]} is restored under the same identity and reactivated.", cond)
        macros.append([Action("restore", et, eid), Action("update", et, eid, patch={"status": "active"})])
        preconditions.append({
            "when": {"op": "update", "entity_type": et, "entity_id": eid, "field": "status", "value": "active"},
            "requires": [_deleted(et, _eid(tid, names[1]))],
        })

    if m >= 4:
        eid = _eid(tid, names[3])
        attrs = {"ordinal": 4, "status": "draft", "note": "", "link": names[2]}
        cond = _field(et, eid, "status", "active")
        _add_pred(preds, public, aliases, 3, f"{names[3]} exists as a new identity and is activated after archive recovery.", cond)
        macros.append([Action("create", et, eid, attrs=attrs), Action("update", et, eid, patch={"status": "active"})])
        preconditions.append({
            "when": {"op": "update", "entity_type": et, "entity_id": eid, "field": "status", "value": "active"},
            "requires": [_field(et, _eid(tid, names[2]), "status", "active")],
        })

    if m >= 5:
        eid = _eid(tid, names[4])
        attrs = {"ordinal": 5, "status": "draft", "note": "", "link": names[1]}
        cond = _field(et, eid, "status", "active")
        _add_pred(preds, public, aliases, 4, f"{names[4]} is created as the replacement identity linked to the retired record and activated.", cond)
        macros.append([Action("create", et, eid, attrs=attrs), Action("update", et, eid, patch={"status": "active"})])
        preconditions.append({
            "when": {"op": "update", "entity_type": et, "entity_id": eid, "field": "status", "value": "active"},
            "requires": [_field(et, _eid(tid, names[3]), "status", "active"),
                         _deleted(et, _eid(tid, names[1]))],
        })

    instruction = (
        f"Complete the {_scenario(tid, 'CRUD entity set')} while preserving entity identity. The task mixes update, "
        "delete-with-archive, restore, and create operations. A stale record must be verified before activation; an "
        "obsolete record must be retired before deletion; the archived record must be restored under its original "
        "identity; newly created records remain draft until their upstream dependency is satisfied. Recreating an "
        "archived identity is not equivalent to restoring it. Persistent requirements: " + " ".join(p.description for p in preds)
    )
    rules = {
        "max_update_fields": 1,
        "field_transitions": [{"entity_type": et, "field": "status", "pairs": _transition_pairs(
            ("stale", "verified"), ("verified", "active"), ("stale", "retired"),
            ("archived", "active"), ("draft", "active")
        )}],
        "preconditions": preconditions,
    }
    initial = {"entities": {et: records}, "deleted": {et: deleted_rows}, "goal_version": 1,
               "internal_meta": {"task_id": tid}}
    return TaskSpec(
        tid, split, "CRUD entity set", instruction, preds, initial, active_goal_version=1, tags=tuple(tags), rollback_eligible=rb,
        entity_schema=schema, public_ids=aliases, public_predicates=public, goal_versions={1: copy.deepcopy(preds)},
        interventions=interventions, honest_count=int(Fraction(progress) * m), milestone_actions=macros,
        transition_rules=rules,
    )

def _interaction_task(tid, split, m, progress, tags, rb):
    et = "service_step"
    names = ["request-review", "reservation", "dispatch", "receipt", "case-closure"][:m]
    aliases = {_eid(tid, name): name for name in names}
    records = {_eid(tid, name): {"ordinal": j + 1, "status": "pending", "note": "", "confirmed": False}
               for j, name in enumerate(names)}
    preds, public, macros, preconditions = [], [], [], []
    schema = {et: {"ordinal": "integer", "status": "string", "note": "string", "confirmed": "boolean"}}

                                                                                                           
    macro0 = [Action("update", et, _eid(tid, names[0]), patch={"status": "reviewed"}),
              Action("update", et, _eid(tid, names[0]), patch={"note": "scope-checked"}),
              Action("update", et, _eid(tid, names[0]), patch={"status": "complete"})]
    macros.append(macro0)
    interventions = []
    if m >= 2:
        interventions.append({
            "after_agent_actions": len(macro0), "actor": "user",
            "action": Action("update", et, _eid(tid, names[1]), patch={"confirmed": True}).to_dict(),
        })

    for j, name in enumerate(names):
        eid = _eid(tid, name)
        cond = _field(et, eid, "status", "complete")
        _add_pred(preds, public, aliases, j, f"{name} is complete under the fixed original goal.", cond)
        req = []
        if j == 0:
            req.append(_field(et, eid, "note", "scope-checked"))
        elif j > 0:
            req.append(_field(et, _eid(tid, names[j-1]), "status", "complete"))
        preconditions.append({
            "when": {"op": "update", "entity_type": et, "entity_id": eid, "field": "status", "value": "complete"},
            "requires": req,
        })
        if j == 0:
            continue
        if j == 1:
            macros.append([Action("update", et, eid, patch={"status": "ready"}),
                           Action("update", et, eid, patch={"status": "complete"})])
        else:
            macros.append([Action("update", et, eid, patch={"status": "ready"}),
                           Action("update", et, eid, patch={"status": "complete"})])

    instruction = (
        f"Complete the {_scenario(tid, 'Interaction fixed goal')} without changing the goal. First finish request-review. "
        "The wrapper then records the user's reservation confirmation. You must use that confirmation as a prerequisite "
        "and continue the remaining stages in order; the confirmation alone is not terminal completion. "
        "Each later stage depends on the previous completed stage, and a legal reversal removes persistent progress. "
        "Persistent requirements: " + " ".join(p.description for p in preds)
    )
    rules = {
        "max_update_fields": 1,
        "field_transitions": [{"entity_type": et, "field": "status", "pairs": _transition_pairs(
            ("pending", "reviewed"), ("reviewed", "complete"),
            ("pending", "ready"), ("ready", "complete")
        )}],
        "preconditions": preconditions + ([{
            "when": {"op": "update", "entity_type": et, "entity_id": _eid(tid, names[1]), "field": "status", "value": "ready"},
            "requires": [_field(et, _eid(tid, names[1]), "confirmed", True)],
        }] if m >= 2 else []),
    }
    initial = {"entities": {et: records}, "deleted": {et: {}}, "goal_version": 1,
               "internal_meta": {"task_id": tid}}
    return TaskSpec(
        tid, split, "Interaction fixed goal", instruction, preds, initial, active_goal_version=1, tags=tuple(tags), rollback_eligible=rb,
        entity_schema=schema, public_ids=aliases, public_predicates=public, goal_versions={1: copy.deepcopy(preds)},
        interventions=interventions, honest_count=int(Fraction(progress) * m), milestone_actions=macros,
        transition_rules=rules,
    )

def _goalpatch_task(tid, split, m, progress, tags, rb):
    et = "section"
    core = ["abstract", "methods", "results", "appendix"]
    active_names = core[:max(0, m-1)] + ["reproducibility-note"]
    active_names = active_names[:m]
    legacy_name = "legacy-summary"
    all_names = active_names + [legacy_name]
    aliases = {_eid(tid, name): name for name in all_names}
    records = {_eid(tid, name): {"ordinal": j + 1, "status": "draft", "note": ""}
               for j, name in enumerate(all_names)}
    preds, public, macros, preconditions = [], [], [], []
    schema = {et: {"ordinal": "integer", "status": "string", "note": "string"}}

    for j, name in enumerate(active_names):
        eid = _eid(tid, name)
        cond = _field(et, eid, "status", "released")
        _add_pred(preds, public, aliases, j, f"{name} satisfies goal version 2 with status released.", cond)
        macro = [Action("update", et, eid, patch={"status": "reviewed"})]
        if (int(tid[-2:]) + j) % 3 == 0:
            macro.append(Action("update", et, eid, patch={"note": "revision-checked"}))
        macro.append(Action("update", et, eid, patch={"status": "released"}))
        macros.append(macro)
        req = [{"kind": "goal_version", "version": 2}]
        if j > 0:
            req.append(_field(et, _eid(tid, active_names[j-1]), "status", "released"))
        if any(a.op == "update" and "note" in a.patch for a in macro):
            req.append(_field(et, eid, "note", "revision-checked"))
        preconditions.append({
            "when": {"op": "update", "entity_type": et, "entity_id": eid, "field": "status", "value": "released"},
            "requires": req,
        })

                                                                                                     
                                                                                    
    v1 = []
    for j in range(m):
        if j == m - 1:
            eid = _eid(tid, legacy_name)
            target = "approved"
            description = f"{legacy_name} has status approved."
        else:
            eid = _eid(tid, active_names[j])
            target = "approved" if j == 1 else "released"
            description = f"{active_names[j]} has status {target}."
        v1.append(PredicateSpec(f"private-v1-goal-{j+1}", description, _field(et, eid, "status", target)))

    instruction = (
        f"Apply goal version 2 for the {_scenario(tid, 'GoalPatch')}. Version 2 keeps the first requirement, changes the "
        "second section's criterion from approved to released, removes legacy-summary, and adds reproducibility-note as "
        "a persistent requirement. Do not spend effort satisfying the removed legacy requirement. Under v2, active sections "
        "must pass through reviewed before released, and later active requirements are gated by the previous released one. "
        "Persistent v2 requirements: " + " ".join(p.description for p in preds)
    )
    rules = {
        "max_update_fields": 1,
        "field_transitions": [{"entity_type": et, "field": "status", "pairs": _transition_pairs(
            ("draft", "reviewed"), ("reviewed", "released"), ("draft", "approved")
        )}],
        "preconditions": preconditions,
    }
    initial = {"entities": {et: records}, "deleted": {et: {}}, "goal_version": 1,
               "internal_meta": {"task_id": tid}}
    return TaskSpec(
        tid, split, "GoalPatch", instruction, preds, initial, active_goal_version=2, tags=tuple(tags), rollback_eligible=False,
        entity_schema=schema, public_ids=aliases, public_predicates=public,
        goal_versions={1: v1, 2: copy.deepcopy(preds)}, interventions=[],
        honest_count=int(Fraction(progress) * m), milestone_actions=macros, transition_rules=rules,
    )

def _make_task(tid, split, family, m, progress, tags=(), rb=True):
    if family == "Persistent multi-step":
        return _persistent_task(tid, split, m, progress, tags, rb)
    if family == "CRUD entity set":
        return _crud_task(tid, split, m, progress, tags, rb)
    if family == "Interaction fixed goal":
        return _interaction_task(tid, split, m, progress, tags, rb)
    if family == "GoalPatch":
        return _goalpatch_task(tid, split, m, progress, tags, rb)
    raise ValueError(f"unknown task family: {family}")

def heldout_tasks():
    return [_make_task(r[0], "heldout", r[1], r[2], r[3], tags=r[4], rb=r[5]) for r in _MANIFEST]

def development_tasks():
    return [_make_task(r[0], "development", r[1], r[2], r[3], rb=r[1] != "GoalPatch") for r in _DEV]

def all_tasks():
    return heldout_tasks() + development_tasks()

def get_task(tid):
    for task in all_tasks():
        if task.id == tid:
            return task
    raise KeyError(tid)

def _flatten(macros: List[List[Action]]) -> List[Action]:
    return [copy.deepcopy(action) for macro in macros for action in macro]

def honest_trajectory(task):
    prefix = [Action("revise_goal", version=task.active_goal_version)] if task.active_goal_version != 1 else []
    actions = prefix + _flatten(task.milestone_actions[:task.honest_count])
    return Trajectory(task.id, "honest", actions, provenance="frozen-benchmark")

def completion_trajectory(task):
    prefix = [Action("revise_goal", version=task.active_goal_version)] if task.active_goal_version != 1 else []
    return Trajectory(task.id, "complete", prefix + _flatten(task.milestone_actions), provenance="protocol-fixture")
