# RDNAScope 0.3.0a1 local alpha

This alpha reduces RDNAScope to explicit bounded official ROCm capture/export,
read-only native queries, a small scope/rank summary and an official Perfetto
Trace Processor entry. The [user guide](thin-user-guide.md) describes the CLI;
the [support matrix](thin-support.md) states the actual qualification.

## Migration

The `0.2.0a1` benchmark/experiment/knowledge/cache platform, FreeToken bridge,
application result parsing and `tlp` command are absent from this distribution.
There is no automatic conversion of old records. Use the old independently
installable wheel and preserved source snapshot for historical cases; the
[migration guide](thin-migration.md) gives the ownership split. Consumer
projects own launch, model marks, oracles, scored benchmarks and optimization.

## Validation scope

Local CPU fixtures cover strict contracts, source SHA/cache, native integer
times, incomplete/timeout cases, official exporter protocol and owned UI
lifecycle. An external consumer drove `record` from its own config and emitted
seven CPU submission scopes. A separate historical scalar Graph PFTrace was
read without tool source changes.

On this machine's R9700/gfx1201 with the locked ROCm 10.1.0 image and matching
official producer/converter, a synthetic FP32 eager fixture conserved 16/16
native/export kernels; dynamic Graph conserved 19/19; a two-rank all-reduce
fixture conserved 66/66 across three raw DBs and one merged official export.
All numeric fixture outputs passed. The exact source/tool hashes, original DBs,
PFTrace and negative resource/launch attempts remain in local validation
artifacts outside this Git distribution.

Capture success does not independently prove loss-free collection. CPU scopes
do not establish GPU layer time. Rank/PID/device mapping is inferred and the
cross-rank clock is uncalibrated. The three-group diagnostic cost sample was
too noisy to resolve a one-percent change. These results do not qualify a
FreeToken model, normal TP2 latency, other RDNA/ROCm pairings or a performance
gain. Formal scored runs should disable added tracing and keep their own run ID.

## Distribution

The package has no runtime Python dependencies. It requires an explicit
matching ROCm producer/converter and, for PFTrace queries/UI, an explicit
official Trace Processor. The wheel ships only the thin Python modules and
three thin-v1 schemas. The sdist includes this note, generic documentation,
one Chrome fixture, a generic profile and the tool skill. No model weights,
trace data, machine profile or application integration is shipped.
