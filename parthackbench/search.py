                                                                       
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional
from .certifier import certify_pair
from .evaluators import Evaluator, get_evaluator
from .schema import TaskSpec, Trajectory

@dataclass
class CandidateRecord:
    task_id: str
    candidate_index: int
    generated: bool
    protocol_valid: bool
    matched: bool
    score: Optional[float] = None
    error: Optional[str] = None

def search_task(task: TaskSpec, honest: Trajectory, evaluator: Evaluator | str, k: int = 3,
                generator: Optional[Callable[[TaskSpec, int], Optional[Trajectory]]] = None):
    if k < 1: raise ValueError("K must be positive")
    if generator is None:
        raise ValueError("attack search requires an explicit generator; protocol fixtures are never used as attack candidates")
    ev = get_evaluator(evaluator) if isinstance(evaluator, str) else evaluator
    records: List[CandidateRecord] = []; selected = None
    for i in range(k):
        try:
            candidate = generator(task, i)
        except Exception as exc:
            records.append(CandidateRecord(task.id, i, False, False, False,
                                           error=f"generation failure: {exc}"))
            continue
        if candidate is None:
            records.append(CandidateRecord(task.id, i, False, False, False, error="generation failure")); continue
        try:
            h, a, eligible = certify_pair(task, honest, candidate)
            if not h.replay_valid or not a.replay_valid:
                records.append(CandidateRecord(task.id, i, True, False, False, error="replay or certification failure")); continue
            if not eligible:
                records.append(CandidateRecord(task.id, i, True, True, False, error="component-wise mismatch")); continue
            score = ev.score(task, candidate)
            records.append(CandidateRecord(task.id, i, True, True, True, score=score))
            if selected is None or score > selected[0]: selected = (score, i, candidate)
        except Exception as exc:
            records.append(CandidateRecord(task.id, i, True, False, False, error=str(exc)))
    return (selected[2] if selected else None), records

def run_search(tasks, honest, evaluator, k=3, generator=None):
    selected, accounting = {}, []
    for task in tasks:
        candidate, rows = search_task(task, honest[task.id], evaluator, k, generator)
        if candidate is not None: selected[task.id] = candidate
        accounting.extend(rows)
    return selected, accounting

def accounting_summary(records):
    return {"generated":sum(r.generated for r in records), "protocol_valid":sum(r.protocol_valid for r in records),
            "matched_candidates":sum(r.matched for r in records), "tasks":len(set(r.task_id for r in records)),
            "records":[asdict(r) for r in records]}
