# Release integrity

This document describes consistency checks for the public PartHackBench release. The checks operate only on released artifacts and do not use an external target document as an execution oracle.

## Structural invariants

The release contains 6 development and 18 held-out tasks. Family totals are 8 Persistent multi-step, 6 Entity CRUD, 4 Fixed-goal interaction, and 6 GoalPatch tasks. Held-out honest progress spans the seven configured levels, and 14 held-out tasks are eligible for strict fixed-goal rollback evaluation.

## Frozen empirical records

`artifacts/empirical_shared_ledger.json` stores separate released task-level shared-reference delta series for Historical, CAPE-Max, DeepSeek, and IDJ. `artifacts/empirical_results.json` stores the corresponding frozen aggregate records. These files are empirical artifacts and are not regenerated from protocol fixtures.

`python scripts/verify_release_integrity.py` independently re-aggregates the released task-level ledger and verifies that the resulting means, strict-success counts, denominators, and selected cross-record invariants agree with the released aggregate record.

## Fixture boundary

Development protocol witnesses are deterministic mechanics fixtures that satisfy the benchmark pair-certification rule. They exercise replay and certification behavior, are excluded from empirical aggregation, and cannot be constructed for held-out tasks through the public fixture API. Attack search always requires an explicit candidate generator.

## Public/private boundary

Exported public records omit certification vectors, eligibility verdicts, canaries, and designated private evaluator material. Local certification remains available for software verification, while mechanics-fixture outputs remain separate from frozen empirical observations.

## Scope

Release-integrity checks validate internal consistency of the distributed artifacts. They do not rerun unavailable external model calls and do not claim end-to-end replay of model executions that are outside the public bundle.
