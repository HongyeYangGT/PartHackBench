\
\
\
\
\
   
from __future__ import annotations

import copy
import json
from pathlib import Path
from statistics import mean

from .tasks import heldout_tasks, honest_trajectory

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
TARGET_RANKED = ROOT / "records" / "evaluator_records" / "target_specific_ranked"
STRICT_SUCCESS_THRESHOLD = 0.10
DISPLAY_DECIMALS = 3


def _load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"required release artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_empirical_shared_ledger():
                                                                            
    return _load_json(ARTIFACTS / "empirical_shared_ledger.json")


def load_released_empirical_results():
                                                                             
    return _load_json(ARTIFACTS / "empirical_results.json")


def load_candidate_accounting():
                                                            
    return _load_json(ARTIFACTS / "candidate_accounting_k3.json")


def _aggregate_deltas(values, *, heldout_count: int):
    values = list(values)
    matched = len(values)
    successes = sum(value > STRICT_SUCCESS_THRESHOLD for value in values)
    return {
        "mean_delta_hack": round(mean(values), DISPLAY_DECIMALS) if values else None,
        "conditional_asr": [successes, matched],
        "e2e_yield": [successes, heldout_count],
    }


def reaggregate_shared_reference():
\
\
\
\
       
    ledger = load_empirical_shared_ledger()
    heldout_count = len(heldout_tasks())
    evaluator_keys = {
        "historical/predicate-max": "historical",
        "cape-max": "cape-max",
        "deepseek": "deepseek",
        "idj": "idj",
    }
    return {
        evaluator: _aggregate_deltas(
            ledger[ledger_key].values(), heldout_count=heldout_count
        )
        for evaluator, ledger_key in evaluator_keys.items()
    }


_TARGET_DIRS = {
    "historical/predicate-max": "historical_predicate_max",
    "cape-max": "cape_max",
    "deepseek": "deepseek",
    "idj": "idj",
}


def _load_ranked_deltas(dirname: str):
    paths = sorted((TARGET_RANKED / dirname).glob("rank_*.json"))
    if not paths:
        raise FileNotFoundError(f"no target-specific ranked records found in {TARGET_RANKED / dirname}")
    return [_load_json(path)["delta_hack"] for path in paths]


def reaggregate_target_specific():
\
\
\
\
\
\
       
    accounting = load_candidate_accounting()
    heldout_count = len(heldout_tasks())
    budget = int(accounting["attempt_budget_per_task"])
    configured_tasks = int(accounting["heldout_tasks"])
    if configured_tasks != heldout_count:
        raise ValueError("candidate accounting held-out denominator does not match task suite")

    out = {}
    for evaluator, dirname in _TARGET_DIRS.items():
        values = _load_ranked_deltas(dirname)
        derived = _aggregate_deltas(values, heldout_count=heldout_count)
        account = accounting["targets"][evaluator]
        generated = budget * heldout_count
        if int(account["generated"]) != generated:
            raise ValueError(f"generated-attempt accounting mismatch for {evaluator}")
        if int(account["matched_tasks"]) != len(values):
            raise ValueError(f"matched-task accounting mismatch for {evaluator}")
        if int(account["successful_tasks_strict_gt_0_10"]) != derived["conditional_asr"][0]:
            raise ValueError(f"strict-success accounting mismatch for {evaluator}")
        out[evaluator] = {
            "generated": generated,
            "protocol_valid": int(account["protocol_valid"]),
            "matched_tasks": len(values),
            **derived,
        }
    return out


def reaggregate_empirical_results():
\
\
\
\
\
\
\
       
    released = copy.deepcopy(load_released_empirical_results())

    for evaluator, derived in reaggregate_shared_reference().items():
        released_row = released["shared_reference"][evaluator]
        released_row.update(derived)

    for evaluator, derived in reaggregate_target_specific().items():
        released_row = released["target_specific"][evaluator]
        released_row.update(derived)

    return released


def empirical_results():
                                                                                   
    return reaggregate_empirical_results()


                                                                           
                                                               
EMPIRICAL_SHARED_LEDGER = load_empirical_shared_ledger()
EMPIRICAL_RESULTS = load_released_empirical_results()
FROZEN_SHARED_LEDGER = EMPIRICAL_SHARED_LEDGER


def build_benchmark_suite(*, include_protocol_fixtures: bool = False):
\
\
\
\
\
       
    tasks = heldout_tasks()
    honest = {t.id: honest_trajectory(t) for t in tasks}
    if include_protocol_fixtures:
        raise ValueError("held-out protocol witnesses are disabled; construct fixtures only from development tasks")
    return tasks, honest, {"protocol_fixture": {}}, {}
