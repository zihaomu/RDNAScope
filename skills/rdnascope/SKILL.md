---
name: rdnascope
description: Diagnose RDNA model, kernel and multi-GPU performance with RDNAScope evidence, benchmark contracts, scoped references and candidate gates. Use for recorded native traces or bounded optimization experiments; live GPU work needs an explicitly configured and qualified workload adapter.
---

# RDNAScope evidence and bounded experiments

Read [current implementation](../../docs/implementation.md) before interpreting support, and [configuration](../../docs/configuration.md) for CLI paths. Use the installed `rdnascope`, or the checkout's `.venv/bin/rdnascope`. The [roadmap](../../docs/roadmap.md) describes future capabilities, not current acceptance.

- Start with `doctor`; it checks offline configuration without probing GPUs or downloading tools. Bind optional official Trace Processor and old TLP in a private profile. No fixed local path belongs in shared cases.
- Register explicit sealed inputs with a new run ID and known identity. Leave missing model, request/token, rank, shape and clocks unknown. Registration references files and checks SHA; it does not copy or independently qualify collection. An active SQLite WAL/journal must be resolved by its producer.
- Query one representation at a time. Use `--provider` and, for full/window or otherwise related exports, explicit `--artifact` IDs from `inspect`. Derivation links are declarations; they do not establish export conservation. Native ordering is not a stitched global timeline.
- Inspect `quality` and `provenance` with every result. Cite the query ID, input SHA and event locator. A Perfetto slice locator also requires the recorded Trace Processor build. Inferred PID/rank mappings stay inferred. Native Graph/correlation IDs do not identify generated tokens by themselves.
- Treat duration sums as overlapping observed intervals. Macro HIP spans remain dispatch-local macro evidence. Empty copy records do not exclude traffic; gaps do not prove GPU idle; unknown cross-rank calibration prevents a numeric rank-wait budget. HTTP first-text and reported decode rates do not establish token ITL, correctness or normal-latency gains.
- Use `storage-stats` to separate external evidence, managed payloads and control/unmanaged cache bytes; use service status for Linux RSS/PSS. R2's [lifecycle guide](../../docs/lifecycle.md) covers configured admission/reservations, leases, ABI namespaces and owned workers/services. No threshold/TTL is assumed when unconfigured. GC defaults to preview; execute only the exact reviewed plan within the user's cleanup scope. Never adopt old/unmanaged caches or external source data for deletion.
- Keep full ABI/codegen fingerprints and explicit cold/warm conditions. Use `cache run` for the exclusive writer protocol; a failed namespace is quarantined, not a reusable baseline. CPU fixture reuse does not qualify a real compiler/framework stack. Owned official services require an explicit idle policy or keep request; occupied ports are refused. Keep existing UI/process ownership separate. For existing TLP functionality follow the [explicit bridge](../../docs/migration.md).

Write findings with the observed fact, evidence, limits and smallest discriminating next experiment. Preserve rejected/incomplete evidence. Do not upgrade software validation to RDNA/model qualification. When implementing changes, update the implementation log and run the focused CPU suite; validate a wheel outside the checkout for packaging changes.

For comparisons and optimization, read [workflows](../../docs/workflows.md) and
the actual [support snapshot](../../docs/support.md). Register the metric,
independent boots, warmups/repeats, match dimensions, intentional changes and
target before measurement. Bind an independent output oracle and resource
evidence. Three boots do not establish tail quantiles. A/A drift is inconclusive;
retain it instead of retrying until a candidate appears faster. ABBA is screening.

Use `reference match` before reporting a numeric gap. Unknown shape/layout cannot
yield roofline; observed intervals/collective arrival clues cannot yield a pure
rank-wait or recoverable-wall budget. `semantics register` retains inferred
associations. Exact dependencies and clock calibration need their independent,
scoped evidence. `ui locate` provides source-bound official Perfetto SQL; use the
owned service and VS Code forwarding only when viewing is requested.

Evaluate the candidate type with `experiment evaluate`: kernel/layout,
cache/transfer, thread/config or parallel/topology. Invalid independent controls
and local instability are inconclusive; candidate correctness failures reject.
Keep the candidate isolated. A screening pass or formal validation never changes
the accepted source automatically. Archive the final decision with `kb archive`
and recursively `kb verify` its child/source SHAs.

Live work uses explicit `devices` and `workload run`, within the user's experiment
scope. GPU discovery is only a snapshot; the private trusted adapter must own the
locked lease, interference observer and own-runtime cleanup. Resource-blocked
means no child launch. Never stop another job or reuse a changed ABI namespace.
CPU fixture execution verifies the protocol only. Keep original sources and
historical failed attempts read-only; a prepared action is not a new GPU result.
