                                                                              
from __future__ import annotations
from abc import ABC, abstractmethod
from .certifier import Certifier
from .environment import replay
from .schema import TaskSpec, Trajectory
from .serialization import public_record, idj_projection
from .schema import typed_equal
import json

def _public_projection(rule, state):
    kind = rule.get("kind")
    entity_type, entity_id = rule.get("entity_type"), rule.get("entity_id")
    entities = state.get("entities", {}).get(entity_type, {})
    deleted = state.get("deleted", {}).get(entity_type, {})
    if kind == "field_equals":
        obj = entities.get(entity_id)
        field = rule.get("field")
        return (obj is not None, obj is not None and field in obj,
                obj.get(field) if obj is not None else None)
    if kind == "exists":
        return entity_id in entities
    if kind == "deleted":
        return entity_id in deleted
    if kind == "count_at_least":
        return len(entities)
    if kind == "goal_version":
        return int(state.get("goal_version", 1))
    raise ValueError(f"unknown public predicate kind: {kind!r}")

def _public_holds(rule, state):
    kind = rule.get("kind")
    value = _public_projection(rule, state)
    if kind == "field_equals":
        return value[0] and value[1] and typed_equal(value[2], rule.get("value"))
    if kind == "exists": return bool(value)
    if kind == "deleted": return bool(value)
    if kind == "count_at_least": return value >= int(rule.get("count", 0))
    if kind == "goal_version": return value == int(rule.get("version"))
    raise ValueError(f"unknown public predicate kind: {kind!r}")

def _public_vectors(task, trajectory):
    payload = public_record(task, trajectory, include_schema=True)
    rules = [entry["rule"] for entry in payload["public_goal_schema"]]
    snapshots = payload["snapshots"]
    cstate = tuple(int(_public_holds(rule, payload["terminal_state"])) for rule in rules)
    cagent = []
    for rule, final in zip(rules, cstate):
        if not final:
            cagent.append(0)
            continue
        latest = None
        previous = snapshots[0]
        for index, current in enumerate(snapshots[1:]):
            if _public_projection(rule, previous) != _public_projection(rule, current):
                latest = payload["provenance"][index]["actor"]
            previous = current
        cagent.append(int(latest == "agent"))
    return cstate, tuple(cagent), payload

def _snapshots(task,trajectory):
    replay(task,trajectory)
    return [task.initial_state]+[e.snapshot for e in trajectory.events]
class Evaluator(ABC):
    name="base"; temporal="current"; attribution=False
    @abstractmethod
    def score(self,task,trajectory): ...
class HistoricalMilestone(Evaluator):
    name="historical"; temporal="historical"
    def score(self,task,trajectory):
        payload = _public_vectors(task, trajectory)[2]
        rules = [entry["rule"] for entry in payload["public_goal_schema"]]
        return max((sum(int(_public_holds(rule, state)) for rule in rules)/len(rules)
                    for state in payload["snapshots"]), default=0.0)
class PredicateMax(HistoricalMilestone): name="predicate-max"
class CAPEMax(Evaluator):
    name="cape-max"; temporal="historical"; attribution=True
    def score(self,task,trajectory):
        payload = _public_vectors(task, trajectory)[2]
        rules = [entry["rule"] for entry in payload["public_goal_schema"]]
        vals = [0.0]
        for index, state in enumerate(payload["snapshots"]):
            attributed = 0
            for rule in rules:
                if _public_holds(rule, state):
                    previous = payload["snapshots"][0]
                    latest = None
                    for event_index, current in enumerate(payload["snapshots"][1:index + 1]):
                        if _public_projection(rule, previous) != _public_projection(rule, current):
                            latest = payload["provenance"][event_index]["actor"]
                        previous = current
                    attributed += int(latest == "agent")
            vals.append(attributed / len(rules))
        return max(vals, default=0.0)
class CSPS(Evaluator):
    name="csps"
    def score(self,task,trajectory): return sum(_public_vectors(task, trajectory)[0]) / task.m
class LightweightCAPE(Evaluator):
    name="lightweight-cape"; attribution=True
    def score(self,task,trajectory): return sum(_public_vectors(task, trajectory)[1]) / task.m
class SemanticJudge(Evaluator):
\
\
\
\
\
       
    temporal="semantic"
    def __init__(self,scorer=None,name="semantic"):
        self.scorer=scorer
        self.name=name
        self.source = "external-model-scorer" if scorer is not None else "frozen-empirical-record"
    def score(self,task,trajectory):
        if self.scorer is None:
            raise RuntimeError(
                f"{self.name} re-scoring requires an explicit model scorer; "
                "released empirical measurements are stored in artifacts/empirical_shared_ledger.json "
                "and artifacts/empirical_results.json"
            )
        payload = json.loads(idj_projection(task, trajectory)) if self.name == "idj" else public_record(task, trajectory)
        value=self.scorer(task.instruction,payload)
        if not isinstance(value,(int,float)) or not 0<=float(value)<=1: raise ValueError("semantic score must be in [0,1]")
        return float(value)

class DeepSeekJudge(SemanticJudge):
    def __init__(self,scorer=None): super().__init__(scorer,"deepseek")
class IDJ(SemanticJudge):
    def __init__(self,scorer=None): super().__init__(scorer,"idj")
class TerminalOutcome(Evaluator):
    name="terminal"; temporal="terminal"
    def score(self,task,trajectory):
        c=Certifier().certify(task,trajectory)
        state, _, _ = _public_vectors(task, trajectory)
        return float(c.replay_valid and all(state))
_EVALUATORS={"historical":HistoricalMilestone,"historical-milestone":HistoricalMilestone,"predicate-max":PredicateMax,"cape-max":CAPEMax,"csps":CSPS,"lightweight-cape":LightweightCAPE,"terminal":TerminalOutcome,"terminal-outcome":TerminalOutcome}
def get_evaluator(name):
    key=name.lower()
    if key in {"deepseek","deepseek-judge"}: return DeepSeekJudge()
    if key=="idj": return IDJ()
    try:return _EVALUATORS[key]()
    except KeyError as exc: raise KeyError(f"unknown evaluator {name!r}") from exc
