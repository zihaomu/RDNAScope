# ADR 0004: a thin RDNA observation tool

Date: 2026-11-12. Status: accepted scope decision; implementation migration pending.

Execution baseline: [thin-tool master plan](rdnascope_thin_tool_master_plan_20261112.md).

## Decision

RDNAScope is a reusable tool that consuming projects configure and invoke to
capture RDNA execution evidence, query it, produce small summaries and view
details in official Perfetto. Narrowing coverage is preferable to growing a
project-specific optimization platform.

The consuming project owns its integration. RDNAScope contains no maintained
catalog of application adapters, model hooks, prompt/oracle formats, benchmark
launchers, candidate patches or optimization acceptance rules. Renaming those
files into an internal plugins/examples directory would not satisfy the boundary.

## Small core

Keep these responsibilities:

1. Explicit, bounded capture using verified ROCm tools and official native
   export. Record backend identity, completion, missing data and limitations.
2. A small generic run manifest and optional scope/rank metadata. Scope names
   and application identifiers are supplied by the caller; missing associations
   remain unknown. Native evidence stays in its official format.
3. Read-only queries and compact scope/rank summaries with source locations and
   timing semantics. Agents and humans consume the same facts.
4. Official Perfetto launch/location plus only the process, output-budget and
   derived-cache management needed by these operations.

Hardware/backend qualification, format integrity and safe cleanup of owned
capture/UI processes remain necessary. Thinness does not justify invented layer
timings, undeclared timestamp shifts or unsafe cleanup.

## Consumer-owned content

The caller supplies its launch command/environment, GPU allocation and scheduler
integration, ranges/hooks, phase/iteration/layer names, and optional metrics.
Application correctness, no-trace benchmarks, A/A and A/B, compiler caches,
worktrees, regression cases and optimization skills belong to that project.
RDNAScope may emit evidence for those decisions; it does not own the workflow.

Project configuration and hook scripts live in the consumer checkout. Raw runs
and reports go to an explicit consumer-owned output directory, not the
RDNAScope source tree or a default central corpus of application experiments.
Generic tool binaries and bounded reproducible query caches may use a separate
tool cache. Existing evidence is not moved or deleted by this decision.

The configuration boundary describes commands, tool paths, budgets and metadata.
It must not require a Python module for that application inside RDNAScope. Data
contracts must not enumerate particular applications or parse their private HTTP
or model fields. Optional application metrics are opaque values with declared
units and scope; their business meaning and correctness remain caller-owned.

## Layer visibility and overhead

The desired first useful summary is at scope/layer and rank granularity. A
project may mark its layers; the core must also work when no layer metadata is
available. Whole-model Graph replay needs verified replay-time associations;
capture-time Python ranges do not prove per-replay layer duration.

Default scoring adds no layer instrumentation. A separate bounded diagnostic
may collect it. Concurrent low-overhead observation requires measured overhead
and coverage; no universal zero-cost or one-percent claim is made. The narrower
scope may initially support only selected modes that are actually verified.

## Migration and acceptance

The current alpha is broader. Extract application bridges, business result
parsers and their tests first; then retire the built-in benchmark/candidate/
knowledge workflow and compilation-cache orchestration from the default product
surface. Reuse generic readers, evidence checks and owned-service primitives
where they directly support capture/query/report/view. This decision does not
declare a new capture CLI implemented or remove existing APIs in place.

Preserve the old version and all referenced sources before retiring paths.
Record explicit external source bindings for historical evidence; never rewrite
old hashes, silently delete old runs or claim unavailable bytes still verify.
Application-specific migration work occurs in a separate consumer workspace,
without changing an accepted model baseline.

Acceptance requires:

- A build/install outside the checkout that needs no application repository.
- Capture/read/report/view exercised with generic fixtures; unsupported device,
  Graph, clock and semantic features remain explicit.
- A consuming project configured entirely from its own checkout, without
  adding a file, import, application-name branch or private path to this repo.
- No application-specific integration in source, packaged schemas, shipped
  examples or runtime entry points. Hardware evidence is a separate scope.
- Bounded outputs, retained failure evidence, owned-only process cleanup and
  score/diagnostic distinction verified for the reduced surface.

The earlier roadmap and optimization APIs remain a historical implementation
record, not mandatory scope for the thin tool. A general observation skill may
remain; application optimization skills stay with the consumer.
