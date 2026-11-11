# ADR 0003 — Immutable evidence, scoped qualification and comparisons

Accepted for alpha 0.2.0a1. R0/R1's four schemas and R2's fingerprint retain version
1. Eight additional v1 schemas cover capability, benchmark-contract, measurement,
reference, semantic-map, finding, experiment and case. Existing records are not
rewritten when new evidence becomes available.

Records use exclusive creation and a canonical envelope SHA. References bind a
source ID, source-relative path and byte SHA, optionally a typed JSON-pointer
assertion. Private source bindings stay outside portable records. Recursive case
verification checks child SHAs and all referenced bytes. Managed query/job/cache
evidence receives a record reference so lifecycle GC cannot silently invalidate it.
Raw per-run output is separate protected evidence; no automatic retention is
inferred for it.

Qualification is feature-specific and exact-context-specific. Synthetic CPU data
cannot establish GPU qualification. Historical and live evidence have distinct
bases. Capture/export conservation, output correctness, complete coverage, clock
calibration and normal performance are independent gates. Unknown is retained.

Benchmark contracts fix metric, units, independent boots, cases, warmups/repeats,
matching dimensions, intentional changes, balanced sequence and acceptance target
before measurement. A/A uses boot medians and reports observed spread. A/B reports
paired ratios and their observed range; it does not infer population confidence
or tail quantiles from a handful of boots. ABBA remains screening. Every failure
and skipped stage remains visible. Measurement instability is inconclusive.

References distinguish published specification bounds, measured same-condition
baselines and reachable calibration. Measured references require qualified scoped
evidence. No name-based shape/FLOP inference, unqualified roofline, kernel-sum wall
budget or uncalibrated rank-wait subtraction is permitted.

Semantic sidecars retain exact/inferred/unmapped status. Exact associations and
dependencies need independent assertions; calibrated clocks need a matching
capability. Native IDs are not rewritten. Model/kernel/multi-GPU findings share
the same provenance and report alternatives/next experiments. An exact complete
non-overlapping dependency scope may yield a scoped lower bound, not a complete
model critical path or recoverable wall claim.

Candidate gates follow the mechanism: kernel/layout, cache/transfer,
thread/config and parallel/topology. A malformed independent control is
inconclusive, not evidence that the candidate's mathematics failed. Formal
validation, screening and source adoption remain separate. Evaluation never
adopts source automatically. This separation lets future adapters extend the
runner without inheriting FreeToken's RowGather-specific protocol.
