                                                                                
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parthackbench.frozen_run import (
    load_candidate_accounting,
    load_empirical_shared_ledger,
    load_released_empirical_results,
    reaggregate_shared_reference,
    reaggregate_target_specific,
)
from parthackbench.tasks import heldout_tasks


def main():
    ledger = load_empirical_shared_ledger()
    released = load_released_empirical_results()
    heldout_ids = {task.id for task in heldout_tasks()}

    required_shared = {"historical", "cape-max", "deepseek", "idj"}
    assert set(ledger) == required_shared
    keysets = [set(rows) for rows in ledger.values()]
    assert keysets and all(keys == keysets[0] for keys in keysets[1:])
    assert keysets[0].issubset(heldout_ids)

    derived_shared = reaggregate_shared_reference()
    for evaluator, derived in derived_shared.items():
        row = released["shared_reference"][evaluator]
        for field in ("mean_delta_hack", "conditional_asr", "e2e_yield"):
            assert derived[field] == row[field], (evaluator, field, derived[field], row[field])

    derived_target = reaggregate_target_specific()
    for evaluator, derived in derived_target.items():
        row = released["target_specific"][evaluator]
        for field in ("generated", "protocol_valid", "matched_tasks", "mean_delta_hack", "conditional_asr", "e2e_yield"):
            assert derived[field] == row[field], (evaluator, field, derived[field], row[field])

    accounting = load_candidate_accounting()
    assert accounting["heldout_tasks"] == len(heldout_ids)
    expected_attempts = accounting["attempt_budget_per_task"] * len(heldout_ids)
    for row in accounting["targets"].values():
        assert row["generated"] == expected_attempts
        assert row["successful_tasks_strict_gt_0_10"] <= row["matched_tasks"] <= row["protocol_valid"] <= row["generated"]

    rollback_total = sum(task.rollback_eligible for task in heldout_tasks())
    for row in released["rollback"].values():
        detected = row["detected"]
        assert detected[1] == rollback_total
        assert 0 <= detected[0] <= detected[1]
        assert row["retained_false_credit"] >= 0

    print(json.dumps({
        "status": "ok",
        "reaggregated_shared_reference": derived_shared,
        "reaggregated_target_specific": derived_target,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
