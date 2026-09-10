# PartHackBench

**PartHackBench** is a controlled benchmark for stress-testing partial-credit evaluators in stateful tool-agent tasks. It asks a simple question: **can an agent change the score it receives by changing the path it takes, while ending with the same certified task progress?**

## Why PartHackBench?

![PartHackBench](assets/1.png)

Imagine asking an AI assistant to prepare a weekend trip for you.

You give it four simple jobs: book the hotel, buy the train ticket, reserve a restaurant, and arrange a ride from the station.

The first assistant books the hotel and the train ticket, then stops. Two jobs are finished. If you check your trip right now, it is **half ready**.

The second assistant takes a stranger route. It completes all four jobs. For a moment, your trip is perfectly arranged: hotel booked, ticket purchased, restaurant reserved, ride scheduled. Then it cancels the restaurant and the ride.

Now check both trips again.

They are identical. Both have a hotel and a train ticket. Neither has a restaurant reservation or a ride.

So how much credit should the two assistants receive?

Intuitively, the same amount.

But imagine a scoring system that remembers the best moment each assistant ever reached. The first assistant never went beyond 50%, so it receives **0.5**. The second assistant briefly reached 100%, so the evaluator still gives it **1.0**, even though half of that work has disappeared.

That simple mismatch is the problem behind **PartHackBench**.

A higher score alone proves very little. Perhaps the second assistant genuinely accomplished more. To test an evaluator fairly, PartHackBench first removes that possibility by constructing trajectory pairs whose **final task progress is certified to be the same**.

In the trip example, the benchmark checks each requirement separately: hotel, ticket, restaurant, and ride. It also checks whether the surviving accomplishments are credited to the same actor. Only when the two trajectories reach the same terminal world state and match component by component can they form an **equal-progress pair**.

Once that condition is satisfied, the benchmark asks:

> **If two agents end with the same certified progress, does the evaluator still give them different scores?**

The score difference is

```math
\Delta_{\text{hack}} = f(A)-f(H),
```

where `H` is the honest trajectory and `A` is the adversarial trajectory. A positive `\Delta_{\text{hack}}` means the evaluator awarded extra credit even though benchmark-defined final progress stayed fixed.

![PartHackBench](assets/2.png)

The trip story also gives an intuitive meaning to the main objects used throughout the benchmark. A **goal predicate** is one persistent requirement, such as “the hotel is booked.” A **trajectory** is the full sequence of actions taken by the agent. The **current state** describes what is actually true at the end of the task. A **historical evaluator** can retain credit for achievements that occurred earlier in the trajectory, while a **current-state evaluator** scores what still holds at evaluation time. A **rollback** occurs when completed work is later undone, such as cancelling the restaurant reservation.

This leads to the second stress test. Suppose an assistant currently satisfies two requirements and then cancels one of them. Its certified progress has decreased, so a partial-credit evaluator should reduce its score as well. PartHackBench calls this a **strict rollback test**. Equal-progress tests check whether scores remain invariant when certified progress remains fixed; rollback tests check whether scores decrease when certified progress decreases.

PartHackBench implements both tests in **PB-CSTE v1.0**, a deterministic and replayable tool-use environment. Tasks operate on explicit persistent goals through allowlisted state-changing actions. Every successful operation produces a state change, provenance record, and replayable snapshot. Certification is applied before evaluator scores are compared, so score differences are measured only after the benchmark has controlled for final task progress.

## How PartHackBench works

PB-CSTE contains **6 development tasks and 18 held-out tasks** across four task families: Persistent multi-step, Entity CRUD, Fixed-goal interaction, and GoalPatch. Fourteen fixed-goal cases additionally support strict rollback evaluation.

For an equal-progress test, an honest trajectory `H` and a candidate adversarial trajectory `A` are replayed from the same frozen initial state. The certifier evaluates the terminal goal predicates component by component and verifies attribution for surviving accomplishments. GoalPatch cases additionally require the active goal version to match. A pair becomes eligible when the active goal version, predicate vector, and attribution vector agree component by component. Task-external fields outside the benchmark progress construct do not affect pair eligibility. The evaluator is then scored on both trajectories, and `\Delta_{\text{hack}}` measures any remaining credit difference.

For rollback evaluation, the benchmark starts from a certified trajectory and applies a legal reversal that reduces current task progress while preserving the relevant fixed goal definition. A rollback-aware evaluator should satisfy `f(R) < f(H)`. Historical evaluators can fail this test when earlier achievements continue to contribute credit after they have been undone.

The benchmark therefore separates three layers that are easy to conflate in agent evaluation: **what actions occurred**, **what task state survives at the end**, and **what score the evaluator assigns**. PB-CSTE provides the executable state and provenance layer; certification determines which trajectory comparisons are valid; evaluator-specific scoring then reveals whether the scoring rule is sensitive to path history after certified progress has been controlled.

The frozen reference experiment produced **15 matched held-out equal-progress pairs** for the Historical target. That matched set is stored in the empirical ledger as an observed experimental outcome and is not encoded in the held-out task definitions.

## Release principle

Frozen empirical records are distributed as immutable release artifacts. The repository does not reconstruct missing frozen attack or rollback traces from task templates and then treat those reconstructions as empirical observations. Development fixtures remain available for protocol, serializer, evaluator, and difficulty checks; development mechanics witnesses are excluded from empirical aggregation.

This keeps deterministic benchmark mechanics separate from external model-run outputs, which may vary across independent reruns.

## Included

- PB-CSTE task/environment code and deterministic protocol mechanics;
- 6 development + 18 held-out task specifications across the four task families;
- public serializer and schema-free IDJ projection;
- certifier and deterministic evaluator implementations;
- prompt templates for attacker, DeepSeek judge, IDJ checklist construction, and IDJ scoring;
- frozen shared-reference task-level ledger;
- frozen shared-reference, target-specific, rollback, and integrity aggregates;
- target-specific ranked deltas;
- public honest evaluator payload/projection records, replay audit records, and structural task audits;
- CI tests for release integrity, task structure, public/private record hygiene, and empirical-ledger arithmetic.

## Frozen headline results

The frozen Historical/Predicate-Max shared set contains 15 matched tasks. Historical mean Δhack rounds to **.252**, conditional ASR is **10/15**, and end-to-end yield is **10/18**. Shared-reference DeepSeek mean inflation is **.022** with ASR **1/15**; IDJ is **.017** with ASR **1/15**. Current-state controls have zero shared-set inflation. Rollback detection is 0/14 for historical evaluators, 10/14 for DeepSeek, 12/14 for IDJ, and 14/14 for CSPS / Lightweight CAPE.

These values are aggregated from the released empirical records wherever the corresponding lower-level inputs are public. They are not hard-coded into the evaluator implementations or integrity tests.

## Quick start

```bash
python scripts/verify_package.py
python scripts/verify_release_integrity.py
python -m unittest discover -s tests -v
python -m parthackbench.cli aggregate-results --json
python -m parthackbench.cli manifest --split heldout
python -m parthackbench.cli replay-honest --task PH-H01 --json
```

For a mechanics-only development witness:

```bash
python -m parthackbench.cli protocol-fixture --task PH-D04 --kind adversary --json
```

Development protocol fixtures are provided to exercise replay and certification mechanics offline. They cannot be constructed for held-out tasks through the public fixture API, are never used as a default attack generator, and are excluded from empirical measurements.

## Data layout

| Path | Purpose |
|---|---|
| `artifacts/empirical_shared_ledger.json` | Frozen task-level shared-reference deltas for Historical, CAPE-Max, DeepSeek, and IDJ |
| `artifacts/empirical_results.json` | Frozen aggregate empirical results |
| `artifacts/candidate_accounting_k3.json` | Frozen K=3 aggregate candidate accounting |
| `records/evaluator_records/` | Released shared and target-specific evaluator records |
| `records/tasks/` | Public task specifications |
| `records/public_payloads/honest/` | Serialized honest public evaluator inputs |
| `records/idj_projections/honest/` | Schema-free honest projections |
| `prompts/` | Frozen prompt templates supplied with the release |
| `paper/PartHackBench_preprint_reference.pdf` | Reference paper included with the repository |

## Public/private boundary

The public release excludes private certification vectors, eligibility verdicts, canaries, and private identifiers from exported records. Expected values, hidden tests, trusted state, private identifiers, certification vectors, and eligibility verdicts remain outside public evaluator inputs.

The source package contains development-only witness construction in `parthackbench/fixtures.py` so the mechanics can be exercised offline. Held-out witness construction is rejected by the public API. Development witnesses are mechanics-only fixtures and are excluded from frozen empirical observations.

## Frozen model configuration

The historical-target attacker used `deepseek-v4-pro` in thinking mode, temperature 0, strict JSON, a 12,000-token cap, a 600-second timeout, and one bounded retry. The DeepSeek judge used structured partial scoring at temperature 0 with strict JSON, a 4,096-token cap, a 600-second timeout, and one bounded retry. IDJ checklist construction used Gemini 2.5 Pro; IDJ scoring used the schema-free projection, three calls per trajectory, and the median as primary.

Provider-side model revision identifiers and the frozen per-task IDJ checklist hashes are not present in the supplied release source, so the repository leaves them unspecified.

## What the public release reproduces

`aggregate-results` recomputes shared-reference and target-specific summary fields from the released lower-level records wherever those inputs are public. `verify_release_integrity.py` independently checks the same arithmetic and cross-record invariants. Aggregate fields whose lower-level inputs are outside the public bundle are preserved as empirical records.

The public package therefore supports deterministic replay of the released benchmark mechanics and re-aggregation of released empirical records. Raw model traces that remain outside the public bundle are outside its replay scope.

## Independent reruns

A new model execution should use a new run identifier and be reported separately from the frozen reference run. Semantic model scores may vary across independent executions. Rerun outputs should not overwrite `artifacts/empirical_shared_ledger.json` or `artifacts/empirical_results.json`.

See `docs/RELEASE_INTEGRITY.md`, `docs/data_provenance.md`, and `docs/reproducibility.md` for details.
