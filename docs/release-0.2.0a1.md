# 0.2.0a1 — evidence and experiment alpha

This initial trial release adds a standalone offline core, native read-only
queries, lifecycle-managed caches/jobs/services, scoped capabilities, benchmark
contracts, references, three-domain findings, semantic sidecars, candidate gates
and immutable cases. Apache-2.0; Python 3.12+; core dependency is jsonschema.

Thirteen v1 schemas ship in the wheel. Existing v1 identities/query contracts and
the explicit legacy `tlp` bridge remain readable. Native files retain upstream
formats. There is no automatic migration of old caches, GPU probe on import,
framework installation, code adoption or LLM-service dependency.

Local validation: 66 CPU tests and historical R9700 QUEUE interval conservation;
see [validation](validation-r3r6.md), [implementation](implementation.md) and the
release's sanitized validation summary for installation/regression details.
Remote CI results are recorded separately from local tests. Manual GPU CI is
prepared but requires an operator-configured self-hosted runner and reviewed plan.

GPU resources were occupied, so fresh native/Graph qualification, TP2 controls,
candidate numerical/performance tests and another GPU pair remain pending. The
historical TP2 A/A is inconclusive; no new model speedup is claimed. Exact full
model critical paths, calibrated rank waiting and real reachable kernel/communication
references remain unqualified. The second runnable adapter is a synthetic CPU
fixture. Compatibility FreeToken GPU actions are not newly qualified.

This is an alpha CLI/API. New schema fields need a version/migration decision;
immutable historical records must not be edited to fit a newer implementation.
Raw evidence retention remains explicit owner policy and is separate from managed
cache GC. File/process budgets are monitored, not filesystem hard quotas.
