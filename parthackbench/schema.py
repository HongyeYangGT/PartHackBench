                                                                          
import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

State = Dict[str, Any]

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)

def typed_equal(a, b):
    return canonical(a) == canonical(b)

@dataclass(frozen=True)
class PredicateSpec:
    id: str
    description: str
    condition: Dict[str, Any]
    def evaluate(self, state: State) -> bool:
        c, k = self.condition, self.condition.get("kind")
        e = state.get("entities", {})
        if k == "field_equals":
            obj = e.get(c["entity_type"], {}).get(c["entity_id"])
            return obj is not None and c["field"] in obj and typed_equal(obj[c["field"]], c["value"])
        if k == "exists": return c["entity_id"] in e.get(c["entity_type"], {})
        if k == "deleted": return c["entity_id"] in state.get("deleted", {}).get(c["entity_type"], {})
        if k == "count_at_least": return len(e.get(c["entity_type"], {})) >= int(c["count"])
        if k == "goal_version": return int(state.get("goal_version", 1)) == int(c["version"])
        raise ValueError(f"unknown predicate kind: {k!r}")
    def relevant_projection(self, state: State) -> Any:
        c, k = self.condition, self.condition.get("kind")
        if k == "field_equals":
            obj = state.get("entities", {}).get(c["entity_type"], {}).get(c["entity_id"])
            return [obj is not None, obj is not None and c["field"] in obj,
                    None if obj is None else obj.get(c["field"])]
        if k == "exists": return c["entity_id"] in state.get("entities", {}).get(c["entity_type"], {})
        if k == "deleted": return c["entity_id"] in state.get("deleted", {}).get(c["entity_type"], {})
        if k == "count_at_least": return len(state.get("entities", {}).get(c["entity_type"], {}))
        if k == "goal_version": return int(state.get("goal_version", 1))
        raise ValueError(f"unknown predicate kind: {k!r}")

@dataclass(frozen=True)
class Action:
    op: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    attrs: Dict[str, Any] = field(default_factory=dict)
    patch: Dict[str, Any] = field(default_factory=dict)
    version: Optional[int] = None
    actor: str = "agent"
    metadata: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self, public: bool = False) -> Dict[str, Any]:
        d = {"op":self.op,"entity_type":self.entity_type,"entity_id":self.entity_id,
             "attrs":self.attrs,"patch":self.patch,"version":self.version,"actor":self.actor}
        if not public and self.metadata: d["metadata"] = self.metadata
        return d
    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict): raise ValueError("action must be an object")
        allowed={"op","entity_type","entity_id","attrs","patch","version","actor","metadata"}
        if set(d)-allowed: raise ValueError(f"unknown action fields: {sorted(set(d)-allowed)}")
        if "op" not in d or not isinstance(d["op"], str): raise ValueError("action op is required")
        return cls(**copy.deepcopy({k:d[k] for k in allowed if k in d}))

@dataclass
class Event:
    index: int
    action: Action
    actor: str
    diff: Dict[str, Any]
    snapshot: State
    goal_version: int
    timestamp: int

@dataclass
class TaskSpec:
    id: str
    split: str
    family: str
    instruction: str
    predicates: List[PredicateSpec]
    initial_state: State
    active_goal_version: int = 1
    tags: Tuple[str, ...] = ()
    rollback_eligible: bool = True
    provenance: str = "frozen-benchmark"
    entity_schema: Dict[str, Dict[str, str]] = field(default_factory=dict)
    public_ids: Dict[str, str] = field(default_factory=dict)
    public_predicates: List[Dict[str, Any]] = field(default_factory=list)
    goal_versions: Dict[int, List[PredicateSpec]] = field(default_factory=dict)
    interventions: List[Dict[str, Any]] = field(default_factory=list)
    honest_count: int = 0
    completion_actions: List[Action] = field(default_factory=list)
    milestone_actions: List[List[Action]] = field(default_factory=list)
    transition_rules: Dict[str, Any] = field(default_factory=dict)
    @property
    def m(self): return len(self.predicates)
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict): raise ValueError("task must be an object")
        d = copy.deepcopy(data)
        required = {"id", "split", "family", "instruction", "predicates", "initial_state"}
        missing = required - set(d)
        if missing: raise ValueError(f"missing task fields: {sorted(missing)}")
        if set(d) - set(cls.__dataclass_fields__): raise ValueError("unknown task fields")
        if not all(isinstance(d[key], str) and d[key] for key in ("id", "split", "family", "instruction")):
            raise ValueError("task identity and instruction fields must be non-empty strings")
        if d["split"] not in {"development", "heldout"}: raise ValueError("invalid task split")
        if not isinstance(d["initial_state"], dict): raise ValueError("initial_state must be an object")
        if not isinstance(d["predicates"], list): raise ValueError("predicates must be a list")
        d["predicates"] = [PredicateSpec(**p) for p in d["predicates"]]
        d["goal_versions"] = {int(k): [PredicateSpec(**p) for p in v] for k, v in d.get("goal_versions", {}).items()}
        d["completion_actions"] = [Action.from_dict(a) for a in d.get("completion_actions", [])]
        d["milestone_actions"] = [[Action.from_dict(a) for a in macro] for macro in d.get("milestone_actions", [])]
        d["tags"] = tuple(d.get("tags", []))
        task = cls(**d)
        if not 3 <= task.m <= 5: raise ValueError("tasks require 3 to 5 predicates")
        if len(set(p.id for p in task.predicates)) != task.m: raise ValueError("duplicate predicate IDs")
        if not task.public_ids or len(set(task.public_ids.values())) != len(task.public_ids):
            raise ValueError("public entity aliases must be bijective")
        if any(not isinstance(private, str) or not isinstance(alias, str)
               for private, alias in task.public_ids.items()):
            raise ValueError("public entity aliases must be strings")
        if len(task.public_predicates) != task.m: raise ValueError("public goal mapping must be one-to-one")
        if any(not isinstance(p, dict) or not isinstance(p.get("rule"), dict)
               for p in task.public_predicates):
            raise ValueError("public predicates require rule objects")
        if not isinstance(task.honest_count, int) or not 0 <= task.honest_count <= task.m:
            raise ValueError("honest_count must be within predicate count")
        if task.milestone_actions and len(task.milestone_actions) != task.m:
            raise ValueError("milestone_actions must align one-to-one with predicates")
        if not isinstance(task.transition_rules, dict):
            raise ValueError("transition_rules must be an object")
        return task

@dataclass
class Trajectory:
    task_id: str
    name: str
    actions: List[Action]
    events: List[Event] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "user-provided"
    def to_dict(self, public: bool = False):
        return {"task_id":self.task_id,"name":self.name,"actions":[a.to_dict(public) for a in self.actions],"provenance":self.provenance}
    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict) or set(d) - {"task_id", "name", "actions", "provenance"}:
            raise ValueError("unknown trajectory fields")
        if not isinstance(d.get("actions"), list) or len(d["actions"]) > 512:
            raise ValueError("trajectory requires at most 512 actions")
        return cls(d["task_id"], d.get("name", "candidate"), [Action.from_dict(a) for a in d["actions"]],
                   provenance=d.get("provenance", "user-provided"))

@dataclass
class CertificationResult:
    task_id: str
    trajectory_name: str
    replay_valid: bool
    cstate: Tuple[int, ...]
    cagent: Tuple[int, ...]
    pstate: float
    pagent: float
    goal_version: int
    errors: List[str] = field(default_factory=list)
    def as_dict(self):
        return {"task_id":self.task_id,"trajectory":self.trajectory_name,"replay_valid":self.replay_valid,
                "cstate":list(self.cstate),"cagent":list(self.cagent),"pstate":self.pstate,"pagent":self.pagent,
                "goal_version":self.goal_version,"errors":self.errors}
