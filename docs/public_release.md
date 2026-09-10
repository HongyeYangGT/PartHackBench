# Public release contents

The public `records/` tree contains public task specifications, honest replay audit records, honest evaluator payloads/projections, and released evaluator records. Private certification vectors and eligibility verdicts are excluded.

Exact frozen adversarial and rollback trace files are not asserted when the corresponding frozen raw traces are outside the public bundle. Released aggregate and task-level empirical values remain available under `artifacts/` and `records/evaluator_records/`.

Per-task attack-matching outcomes are intentionally absent from public task specifications. The shared-reference matched set is represented only in frozen empirical records. Development protocol witnesses are computed only for mechanics checks and are not stored inside empirical evaluator records.
