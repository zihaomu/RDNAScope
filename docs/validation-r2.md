# R2 local validation — 2026-11-11

Scope: owned cache/query/namespace/worker/service lifecycle on this Linux host.
This is not new GPU collection, framework compilation qualification, an updated
P4/P5 result, a model A/B or a performance gain.

| Check | Actual evidence |
|---|---|
| CPU suite | 43 tests passed, including the original 22 R1 tests |
| Original prototype | 40 regressions passed; 43 original source/script/test hashes preserved |
| GC | Isolated synthetic deletion only; preview/pin/lease/handoff/inode/content/owner/plan guards and tombstones tested |
| Budget | Admission before provider, concurrent reservations, disk floor, fast-exit growth, log/RSS limits tested |
| Namespace | Compatible fixture reused; wrong ABI, active writer and non-success state rejected |
| Process cleanup | Timeout, explicit stop, Ctrl-C, same-group descendants and scratch cleanup tested |
| Real queries | 8 historical inputs referenced; 8936 kernels agree on 8 fields; no copied raw trace |
| Official RPC | Two last-query idle exits and explicit keep/stop passed; zero services/leases left active |
| Packaging | Wheel/sdist, source-independent CWD, 5 schemas, worker and synthetic explicit GC checked with retained command logs |
| GitHub CI/publication | Prepared only; not run or pushed remotely |

CPU negative cases include a log replaced with an external symlink: the external
file remained unchanged, unsafe accounting blocked new admission and evidence was
protected. GC never adopted old caches or followed external paths. Pending jobs
protect namespace references across lease handoff; dead PID/start identity and
abandoned job reconciliation do not imply successful process cleanup.

## Actual official service behavior

The first HTTP attempt used `--idle-timeout 1s` with the upstream default start
policy. It did not expire during the 8-second observation; the owned supervisor
deadline stopped/reaped it. The failed record, command, stderr and frozen review
script remain available. No existing UI was stopped.

After explicitly selecting `--idle-start last-query`, the same registered official
window trace loaded through the upstream HTTP server twice. Requested idle was 1s;
whole-job wall time was approximately 2.14/2.19s including load/readiness and upstream
scheduling. Both exited with code 0. A third explicit `--keep` service was stopped
through its own supervisor. Initial source SHA stayed identical; all three final
children/supervisors exited and leases returned to zero. The first failed service
also ended; no new service was left running.

The ~3.08 MB PFTrace produced sampled child RSS of 41.7–42.9 MB and PSS of
32.8–34.0 MB. These are process samples, not a trace-size multiplier for another
workload, a global RAM-recovery measurement or a long-lived worker plateau test.
Services are isolated per load; no persistent parser pool was introduced. The
versioned official UI URL/VS Code RPC port was returned, while browser rendering
was not tested in R2.

Upstream identity: Perfetto v59.1-1e9c61e98, SHA256
`2434129a3af4dc9e2034a476f7b76447b490975213e301769310d3bd0d5d6458`.
Other versions/idle modes/platforms remain unqualified.

## Historical query preservation and storage scope

Raw rocpd and full official PFTrace again matched all 8936 kernel records on name,
start, duration, PID, Graph/node, queue and stream. Rank0/1 each had 4468 kernels;
duration sum was 96,430,756 ns. The same final query reused its result, with managed
payload count/bytes/hash unchanged and no active lease afterwards. This compares
payloads, not transient filesystem free-space counters or index access timestamps.
Provider-scoped correlation remains different/unmapped across representations.
Semantic/full-model/clock/normal-performance quality remains unknown.

Real input state saw no GC execution or trace copy. Destructive tests used only
temporary synthetic inputs; independent wheel validation also tested a pinned
query surviving explicit GC while unreferenced fixture objects became tombstones.

## Packaging, logs and practical limits

R2 is version 0.1.0a2 under Apache-2.0. The fresh wheel environment contains
jsonschema and its dependencies, with no Torch/Triton/ROCm/TraceLens/browser/pytest.
The synthetic example, five schemas, namespace writer, pin/preview/execute cycle
and original TLP doctor bridge are checked from an unrelated temporary CWD with
PYTHONPATH removed. Sdist includes the synthetic namespace fixture used by tests;
neither archive includes private configs, trace/model data, environments or caches.

Local evidence lives under `artifacts/r2-20261111-01/`: CPU stdout/stderr,
`query-review.json`, `official-final/official-service-review.json`, the failed idle
attempt, `wheel-review.json`, full wheel commands, package inventories/hashes and
review scripts. Original regression/source checks are in the prototype's separate
stage directory. These private artifacts are not distributed fixtures.

Host quota/TTL values remain unconfigured until selected by the owner. No automatic
GC policy was enabled. Admission and sampled monitoring are not filesystem/cgroup
hard limits; audit metadata can grow and unknown/unsafe objects remain protected.
Old collector/exporter/compiler/worktree caches are not migrated, and true compiler
cache hits/ABI validity need backend qualification. Foreground process-group rules
do not contain arbitrary daemonization or make SIGKILL cleanup guarantees.
R3–R6 and remote CI/publication remain separate work.
