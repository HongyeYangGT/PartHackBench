# Reproducibility

Reproducibility is split into deterministic benchmark mechanics, released-record re-aggregation, and independent model reruns. The public package does not claim end-to-end replay of unreleased raw model traces.

For the frozen release record, `python scripts/verify_release_integrity.py` re-aggregates the shared ledger and checks internal consistency with the released aggregate artifacts.

For software mechanics, the test suite replays honest trajectories, validates terminal progress, checks task difficulty constraints, and exercises development witness mechanics and rollback behavior. Development witness traces are excluded from empirical aggregation, held-out witness construction is disabled, and the attack-search API requires an explicit candidate generator.

For new model reruns, copy `runs/independent_rerun_template/run_manifest.template.json`, assign a new `run_id`, preserve the task/evaluator configuration, and store new outputs outside the frozen artifact files. Semantic model outputs may vary across reruns.
