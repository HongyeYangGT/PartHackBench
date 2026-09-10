                                                                                                   
from __future__ import annotations
import copy, hashlib, json
from typing import Iterable
from .schema import Action, Event, TaskSpec, Trajectory, PredicateSpec, typed_equal, canonical

class ReplayError(Exception):
    pass

def _diff(before, after):
    return {} if typed_equal(before, after) else {"before": copy.deepcopy(before), "after": copy.deepcopy(after)}

def _condition_holds(state, condition):
                                                                                      
    return PredicateSpec("__precondition__", "", copy.deepcopy(condition)).evaluate(state)

def _matches_when(action, when):
    if when.get("op") is not None and action.op != when["op"]:
        return False
    if when.get("entity_type") is not None and action.entity_type != when["entity_type"]:
        return False
    if when.get("entity_id") is not None and action.entity_id != when["entity_id"]:
        return False
    field = when.get("field")
    if field is not None:
        if action.op != "update" or field not in action.patch:
            return False
        if "value" in when and not typed_equal(action.patch[field], when["value"]):
            return False
    return True

class DeterministicEnvironment:
    ALLOWED = {"create", "update", "delete", "restore", "revise_goal"}
    ACTORS = {"agent", "user", "system"}

    def __init__(self, task):
        self.task = copy.deepcopy(task)
        self.state = copy.deepcopy(task.initial_state)
        self._events = []
        self._clock = 0
        self.catalog = set(task.public_ids)

    @property
    def events(self):
        return copy.deepcopy(self._events)

    def snapshot(self):
        return copy.deepcopy(self.state)

    def _validate_base(self, a):
        if a.op not in self.ALLOWED:
            raise ReplayError(f"operation {a.op!r} is not allowlisted")
        if a.actor != "agent":
            raise ReplayError("actor is wrapper-assigned; action cannot impersonate another actor")
        if a.metadata:
            raise ReplayError("action metadata is not part of the tool schema")
        if not isinstance(a.attrs, dict) or not isinstance(a.patch, dict):
            raise ReplayError("attrs and patch must be objects")
        if a.op != "create" and a.attrs:
            raise ReplayError("attrs only allowed on create")
        if a.op != "update" and a.patch:
            raise ReplayError("patch only allowed on update")
        if a.op != "revise_goal" and a.version is not None:
            raise ReplayError("version only allowed on revise_goal")
        if a.op == "revise_goal":
            if a.entity_type is not None or a.entity_id is not None or type(a.version) is not int:
                raise ReplayError("invalid revise_goal")
            if a.version not in self.task.goal_versions:
                raise ReplayError("goal revision was not predeclared")
            if int(a.version) <= int(self.state.get("goal_version", 1)):
                raise ReplayError("goal version must increase")
            return
        if a.entity_type not in self.task.entity_schema or not isinstance(a.entity_id, str):
            raise ReplayError("invalid typed entity")
        if a.entity_id not in self.catalog:
            raise ReplayError("entity is not in task catalog")
        data = a.attrs if a.op == "create" else a.patch
        fields = self.task.entity_schema[a.entity_type]
        if set(data) - set(fields):
            raise ReplayError("field is not in the public tool schema")
        types = {"string": str, "integer": int, "boolean": bool, "number": float}
        for key, value in data.items():
            if type(value) is not types[fields[key]]:
                raise ReplayError(f"wrong type for {key}")
        if a.op == "create" and set(data) != set(fields):
            raise ReplayError("create requires all typed fields")
        if a.op == "update" and not data:
            raise ReplayError("empty update")

    def _validate_task_rules(self, a):
        rules = self.task.transition_rules or {}
        max_fields = rules.get("max_update_fields")
        if a.op == "update" and max_fields is not None and len(a.patch) > int(max_fields):
            raise ReplayError(f"update may change at most {int(max_fields)} field(s)")

        if a.op == "update":
            active = self.state.get("entities", {}).get(a.entity_type, {})
            current = active.get(a.entity_id)
            if current is not None:
                for rule in rules.get("field_transitions", []):
                    if rule.get("entity_type") != a.entity_type:
                        continue
                    field = rule.get("field")
                    if field not in a.patch:
                        continue
                    old, new = current.get(field), a.patch[field]
                    allowed = [(pair[0], pair[1]) for pair in rule.get("pairs", [])]
                    if not any(typed_equal(old, x) and typed_equal(new, y) for x, y in allowed):
                        raise ReplayError(f"illegal transition for {field}: {old!r} -> {new!r}")

        for rule in rules.get("preconditions", []):
            if _matches_when(a, rule.get("when", {})):
                missing = [c for c in rule.get("requires", []) if not _condition_holds(self.state, c)]
                if missing:
                    raise ReplayError("task precondition not satisfied")

    def _validate(self, a):
        self._validate_base(a)
        self._validate_task_rules(a)

    def apply(self, a, *, actor="agent"):
        if actor not in self.ACTORS:
            raise ReplayError("unknown wrapper actor")
        self._validate(a)
        before = self.snapshot()
        candidate = self.snapshot()
        if a.op == "revise_goal":
            candidate["goal_version"] = int(a.version)
        else:
            active = candidate.setdefault("entities", {}).setdefault(a.entity_type, {})
            deleted = candidate.setdefault("deleted", {}).setdefault(a.entity_type, {})
            eid = a.entity_id
            if a.op == "create":
                if eid in active or eid in deleted:
                    raise ReplayError(f"entity already exists: {eid}")
                active[eid] = copy.deepcopy(a.attrs)
            elif a.op == "update":
                if eid not in active:
                    raise ReplayError(f"cannot update missing entity: {eid}")
                if set(a.patch) - set(active[eid]):
                    raise ReplayError("update cannot add undeclared fields")
                active[eid] = {**active[eid], **copy.deepcopy(a.patch)}
            elif a.op == "delete":
                if eid not in active:
                    raise ReplayError(f"cannot delete missing entity: {eid}")
                deleted[eid] = copy.deepcopy(active.pop(eid))
            elif a.op == "restore":
                if eid not in deleted:
                    raise ReplayError(f"cannot restore non-deleted entity: {eid}")
                active[eid] = copy.deepcopy(deleted.pop(eid))
        self.state = candidate
        self._clock += 1
        event = Event(
            len(self._events), copy.deepcopy(a), actor, _diff(before, candidate),
            self.snapshot(), int(candidate.get("goal_version", 1)), self._clock,
        )
        self._events.append(event)
        return copy.deepcopy(event)

    def replay(self, actions: Iterable[Action]):
        actions = list(actions)
        if len(actions) > 512:
            raise ReplayError("trajectory action limit exceeded")

        def intervene(count):
            for event in self.task.interventions:
                if event["after_agent_actions"] == count:
                    source = Action.from_dict(event["action"])
                    self.apply(
                        Action(source.op, source.entity_type, source.entity_id,
                               source.attrs, source.patch, source.version),
                        actor=event["actor"],
                    )

        intervene(0)
        for count, a in enumerate(actions, 1):
            self.apply(a)
            intervene(count)
        return Trajectory(self.task.id, "replay", actions, list(self.events), provenance=self.task.provenance)

def replay(task, trajectory):
    trajectory.events = []
    if trajectory.task_id != task.id:
        raise ReplayError("task identity mismatch")
    env = DeterministicEnvironment(task)
    result = env.replay(trajectory.actions)
    trajectory.events = result.events
    return trajectory

def environment_revision(task):
                                                                              
    record = {
        "initial_state": task.initial_state,
        "entity_schema": task.entity_schema,
        "transition_rules": task.transition_rules,
        "goal_versions": {
            str(k): [p.__dict__ for p in v] for k, v in sorted(task.goal_versions.items())
        },
        "interventions": task.interventions,
    }
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
