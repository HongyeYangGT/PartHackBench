# Data provenance

The release has two clearly separated record roles.

**Frozen empirical records** are measurements preserved from the frozen empirical run. They include the task-level shared-reference ledger and release-level aggregate results. These values are immutable within this release.

**Protocol/task records** encode PB-CSTE mechanics, public task specifications, replay audit records, serialization behavior, and local test fixtures. They support software verification and task-structure inspection. Local adversarial or rollback mechanics fixtures do not substitute for unavailable frozen empirical traces.

No post-hoc random noise is injected into the frozen empirical ledger. No missing model outputs, per-attempt outcomes, checklist hashes, provider revisions, or frozen traces are invented.

The public task specification does not contain per-task attack-matching outcomes. Matched-task membership is an empirical result and appears only in frozen experimental records. Mechanics-only development witnesses are independent of matched-task membership and are excluded from empirical metrics.
