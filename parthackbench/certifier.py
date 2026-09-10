                                                                          
from typing import List, Tuple
from .environment import ReplayError, replay
from .schema import CertificationResult, TaskSpec, Trajectory, typed_equal

class Certifier:
    def certify(self, task: TaskSpec, trajectory: Trajectory) -> CertificationResult:
        errors: List[str]=[]
        try: replay(task,trajectory)
        except (ReplayError,ValueError,TypeError,KeyError) as exc: errors.append(str(exc))
        if errors: return CertificationResult(task.id,trajectory.name,False,(),(),0.0,0.0,int(task.initial_state.get("goal_version",1)),errors)
        terminal=trajectory.events[-1].snapshot if trajectory.events else task.initial_state
        cstate=tuple(int(p.evaluate(terminal)) for p in task.predicates); cagent=[]
        for i,p in enumerate(task.predicates):
            if not cstate[i]: cagent.append(0); continue
            prev=task.initial_state; latest=None
            for event in trajectory.events:
                cur=event.snapshot
                if not typed_equal(p.relevant_projection(prev), p.relevant_projection(cur)): latest=event.actor
                prev=cur
            cagent.append(int(latest=="agent"))
        goal=int(terminal.get("goal_version",1))
        if goal != int(task.active_goal_version): errors.append(f"stale goal version: expected {task.active_goal_version}, got {goal}")
        m=task.m; return CertificationResult(task.id,trajectory.name,not errors,cstate,tuple(cagent),sum(cstate)/m if m else 0.0,sum(cagent)/m if m else 0.0,goal,errors)

def certify_pair(task: TaskSpec, honest: Trajectory, adversary: Trajectory) -> Tuple[CertificationResult, CertificationResult, bool]:
    cert=Certifier(); h,a=cert.certify(task,honest),cert.certify(task,adversary)
    return h,a,bool(h.replay_valid and a.replay_valid and h.goal_version==a.goal_version and h.cstate==a.cstate and h.cagent==a.cagent)

def _inverse_event(original, inverse):
    a, b = original.action, inverse.action
    if (a.entity_type, a.entity_id) != (b.entity_type, b.entity_id): return False
    if not original.diff or not inverse.diff: return False
    def state_value(snapshot, ident):
        return {"active": snapshot.get("entities", {}).get(a.entity_type, {}).get(ident),
                "deleted": snapshot.get("deleted", {}).get(a.entity_type, {}).get(ident)}
    before_state = state_value(original.diff["before"], a.entity_id)
    after_state = state_value(original.diff["after"], a.entity_id)
    inverse_before = state_value(inverse.diff["before"], b.entity_id)
    now_state = state_value(inverse.diff["after"], b.entity_id)
    if (a.op, b.op) == ("create", "delete"):
                                                                              
                                                                          
        return (before_state == {"active": None, "deleted": None}
                and inverse_before["active"] is not None
                and typed_equal(inverse_before["active"], after_state["active"])
                and now_state["active"] is None
                and typed_equal(now_state["deleted"], after_state["active"]))
    if (a.op, b.op) in {("delete", "restore"), ("restore", "delete")}:
        if (a.op, b.op) == ("delete", "restore"):
            return (inverse_before["deleted"] is not None
                    and typed_equal(inverse_before["deleted"], after_state["deleted"])
                    and now_state["deleted"] is None
                    and typed_equal(now_state["active"], before_state["active"]))
        return (inverse_before["active"] is not None
                and typed_equal(inverse_before["active"], after_state["active"])
                and now_state["active"] is None
                and typed_equal(now_state["deleted"], before_state["deleted"]))
    if (a.op, b.op) == ("update", "update"):
        before, after, now = before_state["active"], after_state["active"], now_state["active"]
        changed = {k for k in a.patch if not typed_equal(before[k], after[k])}
        return (typed_equal(inverse_before["active"], after)
                and set(b.patch) == changed
                and all(typed_equal(b.patch[k], before[k]) and typed_equal(now[k], before[k]) for k in changed))
    return False

def certify_rollback(task, honest, rollback):
    h, r = Certifier().certify(task, honest), Certifier().certify(task, rollback)
    errors = []
    if not task.rollback_eligible: errors.append("task excluded from rollback")
    if not h.replay_valid or not r.replay_valid: errors.append("invalid replay")
    if not honest.actions or len(rollback.actions) <= len(honest.actions): errors.append("rollback must extend an honest prefix")
    if not typed_equal([a.to_dict() for a in rollback.actions[:len(honest.actions)]], [a.to_dict() for a in honest.actions]):
        errors.append("honest action prefix mismatch")
    if not 0 < h.pstate < 1: errors.append("honest prefix must have partial progress")
    if h.goal_version != r.goal_version or r.pstate >= h.pstate: errors.append("goal changed or progress did not decrease")
    if h.replay_valid and r.replay_valid:
        history = list(honest.events)
        for event in rollback.events[len(honest.events):]:
            if event.goal_version != h.goal_version: errors.append("rollback changed active goal")
            same_entity = [e for e in history if e.diff and (e.action.entity_type,e.action.entity_id)==(event.action.entity_type,event.action.entity_id)]
            if not same_entity or not _inverse_event(same_entity[-1],event): errors.append("extension is not a legal inverse")
            history.append(event)
    return h, r, not errors, errors
