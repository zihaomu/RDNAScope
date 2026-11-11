# R0/R1 local validation — 2026-11-11

This report covers the first portable offline loop. It is not a new model run,
GPU qualification, full-model coverage report or performance-gain claim.

| Check | Actual result |
|---|---|
| New CPU contracts and providers | 22 passed |
| Original prototype regression | 40 passed |
| Original source/scripts/tests | 43 hashes unchanged |
| Build | Wheel and sdist built; Apache-2.0 metadata/license present |
| Clean wheel install | Separate venv, temporary CWD, no PYTHONPATH; 4 schemas load |
| Installed offline example | 2 synthetic kernels; repeated query reuses one result file |
| Runtime footprint | jsonschema and its dependencies; no Torch/Triton/ROCm/TraceLens/browser/test packages |
| Legacy bridge | Original doctor JSON identical; argument/exit-code and recursion checks covered |
| Repository skill | Structure validator passed |
| GitHub CPU CI | Prepared for Python 3.12/3.13; not run remotely |

The CPU suite exercises identity/schema rejection, content mismatch, missing rank
metadata/unknown clocks, nanosecond precision, multiple DB inputs and pagination,
active WAL/negative intervals, atomic concurrent registration, declared lineage
cycles/overlap, source/cache changes, subprocess byte/time bounds, numeric overflow,
unsupported semantic views and legacy macro clock preservation.

## Historical native evidence review

The existing official03 capture was registered by reference: five DBs, full official
PFTrace, official window PFTrace and HTTP JSON. Input hashes were verified before
and after queries. No source evidence was rewritten or copied.

| Observed category | Raw DB / full PFTrace count | Sum of intervals (ns) |
|---|---:|---:|
| Kernel dispatch | 8936 | 96,430,756 |
| HIP API | 2018 | 135,066,502 |
| Graph execution | 4 | 32,349,408 |
| HIP event | 72 | 1,817,790,414 |
| Marker | 21 | 67,903,487 |

Every kernel agreed on name, start, duration, PID, Graph/node, queue and stream.
There were 4468 kernels per declared rank. The official window retained all kernels
and only 16 markers, consistent with its existing bounds. HTTP provider returned
12 stored observations; their reported parity was not treated as a fresh oracle audit.

The expanded metadata audit initially failed on correlation values. Raw DB
`rocpd_event.correlation_id` and PFTrace `debug.corr_id` differ for this capture.
Both are preserved with `correlation_scope`; the cause and cross-provider mapping
are not qualified. The failed attempt and small difference report remain in the
local validation directory. Duration/name matching does not prove every field's
equivalence. Missing request/token mappings, complete Graph coverage, calibrated
rank clocks and normal performance remain unknown.

Parsing used explicitly configured official Perfetto v59.1-1e9c61e98, binary SHA256
`2434129a3af4dc9e2034a476f7b76447b490975213e301769310d3bd0d5d6458`.
RDNAScope adds small query envelopes; it does not serialize a second native trace.

At review, 241,113,110 unique external input bytes were referenced, the registry
occupied 36,864 bytes, and 12 query cache files occupied 32,767 bytes. Several query
implementation revisions were tested; their keys remain distinct. Repeating the
same final query changed neither cache count nor bytes. No GC or deletion occurred.
Dependency wheels, Python environments, producer/compiler caches, exports and
process RSS are outside these registry statistics. R2 must address those budgets.

## Reproduction and evidence

For public synthetic inputs, install `.[test]`, run `python -m pytest -q`, and use the
[README commands](../README.md). Build with `python -m build`; install the wheel in
a fresh venv, change to a temporary directory and run `doctor`, all four `schema`
commands, and `register/query/storage-stats` against an absolute example path.

Local original inputs require explicit private bindings; they are not distributed.
The local `artifacts/r0r1-final-20261111-01/` includes `review_real_inputs.py`,
`review_wheel.py`, query JSON/provenance, complete command logs, package file lists,
wheel/sdist hashes and the initial failed metadata audit. The original workspace
keeps regression logs and the source-preservation review in its separate stage log.

The checkout has not been committed or pushed. Only local Python 3.12 was exercised.
No GPU, model, profiler, exporter, driver setting or existing UI service was started
or modified in this stage.
