# Implementation log

Current checkpoint: **0.2.0a1 software alpha**. This is not full live R3–R6
acceptance. Original entries below are historical checkpoints.

| Milestone | Current status | Remaining acceptance |
|---|---|---|
| R0/R1 | Portable offline core locally validated | Remote CI/publication recorded by release |
| R2 | Managed-core lifecycle locally validated | Actual framework cache qualification per adapter |
| R3 | Scoped matrix/audits/guarded adapter implemented; historical QUEUE rechecked | Fresh eager/Graph/dual-rank collection, output/loss/perturbation and another pair |
| R4 | Contracts/A/A/comparison/reference gates tested; historical A/A inconclusive | Fresh qualified TP2 controls and real reachable kernel/communication references |
| R5 | Three-domain evidence reports, inferred map and official slice location validated | Repeatable model slow-point/reference chain; exact clocks/dependencies remain unqualified |
| R6 | Typed decisions, isolated preparation, actual second CPU adapter, skill and manual GPU CI | Fresh candidate correctness/model comparison and second GPU pair; no source adopted |

See [R3–R6 validation](validation-r3r6.md), [support](support.md) and
[release notes](release-0.2.0a1.md). GPU/model tests are resource-blocked.

## R0/R1 scope

This first implementation creates the portable offline package, Apache-2.0 license,
four versioned contracts, registry/declared derivations, bounded read-only providers,
small result-cache reuse, legacy CLI bridge, synthetic fixtures and CPU CI.

No new GPU collection, model requests, model speedup, calibrated rank timing or
formal adoption is claimed. R2 quota/GC/compiler-cache management, R3 hardware
qualification and later performance/diagnostic milestones remain separate.

## Completed local scope — 2026-11-11

- Cloned the empty target repository into a separate checkout; preserved the prototype.
- Isolated package environment; runtime dependencies exclude Torch/ROCm/browser/models.
- Added contracts, read-only providers and registry without copying source evidence.
- Added the repository's offline skill and CPU workflow; the workflow is prepared for
  Python 3.12/3.13. Remote CI has not run; local validation used Python 3.12.
- New CPU suite: **22 passed**. Original prototype suite: **40 passed**. Original
  source/scripts/tests: **43/43 SHA unchanged**.
- Built wheel and sdist; installed the wheel in a second independent environment,
  executed schemas/register/query/stats from a temporary CWD without PYTHONPATH,
  and checked dependency consistency. No model/GPU/browser packages were installed.
- The installed `tlp` bridge returned exactly the original `doctor` JSON. Separate
  negative tests verified literal argument forwarding, CWD behavior and exit code.
- Read-only queries on the historical official03 capture agreed across raw rocpd
  and official PFTrace: **8936 kernels, 96,430,756 ns duration sum**, ranks 0/1 each
  4468. Name/start/duration/PID/Graph/node/queue/stream matched for every kernel.
- Preserved the first failed metadata audit: raw `rocpd_event.correlation_id` and
  exported `debug.corr_id` differ. Both values now carry explicit source scopes;
  no cross-provider correlation equivalence is claimed.
- Registered 241,113,110 bytes of unique external evidence without copying it.
  Registry: 36,864 bytes. Query cache at final review: 12 small results/32,767 bytes
  across implementation revisions; repeating an identical query added no file/byte.
  This is an evidence-reference test, not a complete cache/RSS/compilation audit.

See [validation details](validation-r0r1.md). Full command stdout/stderr, input SHA,
query envelopes, negative-audit details, package inventories and reproducible local
review scripts are retained privately under `artifacts/r0r1-final-20261111-01/`.
They are not published trace fixtures. The original project plan also records each
implementation step and links those local artifacts.

R0/R1's first offline loop was locally validated at this checkpoint. Later milestone
status follows below; historical P4/P5/performance statuses are not upgraded.

## R2 implementation — 2026-11-11

Status: the implemented R2 managed-core scope is locally validated (0.1.0a2).

- Separate owned cache index with reservations, PID/start/boot/UID leases, references,
  explicit recorded GC plans, rechecks, tombstones and metadata-only reconciliation.
- New query objects use that lifecycle; old untracked cache files remain protected.
  Root accounting includes control/unmanaged bytes; configured thresholds block new
  admission without silently evicting evidence. No host thresholds/TTL are guessed.
- Full declared ABI/codegen fingerprint, explicit cold sessions, exclusive namespace
  writers, and conservative quarantine/protection of non-success evidence.
- Bounded foreground command jobs with logs, scratch cleanup, timeout/RSS/disk/log
  checks, Ctrl-C/stop handling and owned process-group/descendant cleanup.
- Official HTTP/UI service startup/status/stop with upstream idle expiry. Preserved
  the failed default-owner-aware idle attempt; explicit `last-query` passed two real
  tests, and explicit keep/stop passed another. Initial input SHA remained unchanged.
- CLI/guide/ADR/skill updated. Final CPU/package/regression/evidence review is
  recorded in [R2 validation](validation-r2.md).

Final checks: **43 new-core tests, 40 original regressions**, isolated wheel with
5 schemas/worker/synthetic GC, source-independent CWD and legacy bridge passed.
The real historical input review retained 8936 matching kernel records; the final
official service trials left no active child/supervisor/lease. Full logs and scripts
remain under private `artifacts/r2-20261111-01/`; no real cache GC was executed.

This scope does not migrate old collectors/exporters/worktrees or qualify actual
framework compilation, GPU collection, model performance or cross-rank clocks.
R3–R6 and GitHub publication/remote CI remain pending.

## R3–R6 implementation — 2026-11-11

- Added eight immutable v1 evidence contracts (13 total schemas), exact SHA/typed
  assertions, local source bindings, recursive case verification and automatic
  pinning of managed measurement evidence. Unknown facts retain their own basis.
- Added explicit device/RAM admission, exact-context capability resolution and
  sealed native/export/rank/Graph audits. Synthetic truncated/missing/bad-window
  inputs and historical STREAM errors refuse qualification. Missing completion,
  loss, clocks and full-model coverage remain unknown.
- Added independent-boot contracts/A/A, preregistered matched formal or screening
  comparisons, separate HTTP metrics, frozen output oracles and scoped references.
  Positive tests verify model baseline gaps; unknown shape and mismatches do not
  produce roofline or gain estimates. Drift remains inconclusive.
- Added shared model/kernel/multi-GPU findings, evidence-qualified semantic maps
  and dependency scopes. Historical replay links 1176 HC events in four inferred
  groups and 14 findings. No complete model path, rank-wait or recoverable-wall
  estimate follows from those groups. Official UI lookup uniquely locates a real
  source finding using the pinned official parser; no native format is rewritten.
- Added mechanism-specific experiment gates, preserved failed/incorrect first
  attempts and corrected local-instability classification to inconclusive. Fresh
  source-isolated candidate preparation changed only the intended model source
  file. The accepted FreeToken baseline is unchanged.
- Added actual bounded CPU workload boots as a second adapter. Its first A/A
  passed, but the executed comparison failed arm stability; no candidate was
  adopted. FreeToken compatibility GPU actions are prepared in private profiles
  with exact locked runtime/helper identities, shared cache fingerprint and owned
  evidence outputs; fresh execution remains blocked by foreign occupancy.
- Updated CLI, skill, workflow/config/architecture/ADR/support/release documents.
  Added manual self-hosted GPU CI requiring a trusted runner, exact profile/plan
  SHA, selected physical cards, budgets and guarded execution. No GPU workflow
  was dispatched on this occupied host.

Local verification: **66 new-core tests, 40 original regressions**, all **56**
prototype files in the opening SHA snapshot unchanged, all **809** FreeToken
baseline manifest entries unchanged, and exactly one intended delta among the
isolated candidate's 809 entries. New adapter bindings match their current bytes.
The combined historical/synthetic case recursively verifies source/child SHAs.

The wheel was installed in a new environment outside the checkout without
PYTHONPATH. Thirteen schemas, register/query/cache reuse, three-domain analysis,
case search/verification, actual three-boot CPU producer and evidence protection
from GC all passed. The installed `tlp` doctor JSON matches the original. No
Torch/Triton/TraceLens/browser/pytest was installed. This host lacks ensurepip;
the successful environment used `venv --without-pip` plus the existing installer,
without changing the OS. Skill validation used the original tooling environment
because the lean core intentionally has no PyYAML dependency.

Full private command logs/manifests/results remain under
`artifacts/r3r6-20261111-01/`; they are not published fixtures. New raw evidence
is protected separately from managed GC and has monitored per-run budgets, not
automatic archival deletion or filesystem hard quotas. All selected cards were
still occupied at closeout; no new GPU/model work, foreign stop or source adoption
occurred. Live R3–R6 acceptance stays open with the explicit resource prerequisite.

## Initial repository publication and CPU CI

The reviewed 73 public files were committed and normally pushed to `main` in the
previously empty target repository. Commit
[`588a8e1`](https://github.com/zihaomu/RDNAScope/commit/588a8e1e3681c2dc2bbfc76cefe956a0618c2bf3)
contains the implementation. [CPU CI run 43002759303](https://github.com/zihaomu/RDNAScope/actions/runs/43002759303)
completed successfully for both Python 3.12 and 3.13, including tests, wheel build
and analysis outside the checkout. The manual GPU workflow was not dispatched.

The [0.2.0a1 release notes](release-0.2.0a1.md) describe the software alpha and open
hardware gates. Distribution artifacts and a sanitized validation summary belong
to the [GitHub prerelease](https://github.com/zihaomu/RDNAScope/releases/tag/v0.2.0a1).
Private inputs/logs/profiles/caches remain outside Git and release assets.

## Remaining GPU acceptance resumed — 2026-11-11

The user resumed GPU acceptance and requested automatic selection of idle cards.
This is a new attempt with fresh run IDs, identity/source/native checks,
preregistered decode/wall A/A contracts and a bounded foreground resource scan.
The opening snapshot had no eligible idle card. Existing exclusion/reservation
rules remain in force. Actual hardware results will be recorded separately from
the published alpha checkpoint above.

Preflight found that rebinding the legacy native controller's output ROOT also
redirected its official Trace Processor path. The bridge now executes a frozen
controller copy with that independently SHA-bound tool reference preserved. A
CPU regression exercises the complete native bootstrap without a GPU; **67 tests
passed**. Original prototype/application sources remain unchanged, and the
published 0.2.0a1 artifacts retain their original hashes. This local fix is not
new collection qualification.

## Live acceptance — 2026-11-11, local changes after the alpha release

Automatic bounded discovery obtained an exclusive single R9700, then a TP2
pair, respecting current reservations and both device exclusions. Original
application/native inputs stayed read-only. These results belong to the local
working tree; published 0.2.0a1 assets were not replaced.

- Single-device eager/Graph HIP-event and rocprofv3 probes passed 20 independent
  CPU-formula output checks. Official QUEUE windows conserve 36/38 native
  kernels; all five declared Graph windows contain the expected two nodes.
  This qualifies observed FP32 dispatch/export only. Loss, full model coverage,
  cross-rank clocks and normal performance remain unknown.
- The original supervisor correctly failed a root-owned official export.
  An exact-owner/mount Docker writer binding now applies the host UID/GID, with
  requested/applied argv recorded. Foundation and unrelated commands pass
  through. Official offline recovery preserved the original DB hashes and
  failure record. The bridge also preserves the independently bound official
  Trace Processor path and copies the frozen AA overlay patch.
- Live Triton compilation exposed an atomic temporary-directory rename race
  in capacity monitoring. Only vanished descendants of active writer roots are
  tolerated by nondigest monitoring. Root, owner, link, final seal, hash and GC
  checks remain strict; monitoring is not a filesystem hard quota.
- Trace-off FreeToken TP2 boot AA1 completed 12 requests, AA2 completed 10;
  all 22 completed outputs matched the frozen oracle. AA2 long8000 repeat2
  exceeded the 120-second HTTP budget. Both ranks' 60-second watchdogs stalled
  at prefill MoE AllGather sequence4167, last completed4166/enqueued4170.
  Enqueue callsites do not establish live CPU activity or pure transport wait.
  AA3 and model candidate A/B were not run. The cohort is inconclusive; partial
  producer arrays now explicitly fail the preregistered completeness contract.
- A second real GPU workload adapter completed three independent FP32 scalar
  Graph boots, 18 numerical checks and a separate 192-kernel native capture
  with exact export conservation. Amortized HIP-span boot medians were
  2560/3451/2747 ns/op: 32.44% spread versus a 5% limit. Its device/shape/runtime
  reference is conditional, not a qualified numeric gap or roofline.
- An isolated local candidate attempt stopped on foreign GPU use before its
  fixture. One fresh bounded resource-only wait found no available pair. The
  next closeout snapshot found a new exclusive pair. A fresh local attempt on
  that pair passed80 actual candidate layout/output checks across eager/dynamic
  Graph paths. All48 local samples were retained, but baseline drift13.71% and
  12.89% exceeded the preregistered2% limit. Local performance remains
  inconclusive, no model cohort ran and the candidate was not adopted. This is
  a two-device controlled fixture, not distributed TP2/RCCL qualification.
  No foreign process was stopped.
- A new localhost official Perfetto RPC serves the fresh single-GPU Graph
  qualification window on port9002. The previous model service is untouched.
  A software-rendered browser verified native9002, CPU HIP API and GPU queue
  tracks. The first trial connected to the old9001 because the upstream UI
  requires a nonstandard-port flag; its failed result is preserved. Service
  output and the workflow guide now explain the official flag and exact sidebar
  check. The user's VS Code forwarding remains independently unverified.

**72 local core tests and 40 original regressions passed.** Private immutable
cases, failed attempts, source manifests, native DBs, official windows and exact
commands are retained under `artifacts/r3r6-gpu-20261111-112403/`. They are not
public fixtures. Full dual-rank native coverage/perturbation, complete stable TP2
controls, candidate local/model comparison and a second TP2 pair remain open.
The local candidate's controlled numerical gate passed; stable local performance
and actual model/RCCL qualification remain separate open gates.
The next diagnostic ROI must target prefill MoE; the historical decode8/9 ROI
does not explain the new timeout. No model performance gain or source adoption
was validated.

## Layer-level scope refinement — 2026-11-12

The user prefers layer-level visibility with a small cost and evidence for the
next optimization target. The new [design](layer-observability.md) keeps added
layer instrumentation disabled in scored benchmarks and uses separate, matched,
bounded diagnostics for a shared agent/human layer summary. Whole-model Graph
replay, event readout/reuse and perturbation require explicit qualification;
infrequent readout alone does not reduce captured event-node execution.

This step updates the design only. No collector/model/GPU change or new timing
qualification occurred, and the earlier incomplete/inconclusive gates remain.

## Thin tool scope decision — 2026-11-12

The user explicitly accepts reducing scope to make RDNAScope a reusable RDNA
observation tool. The accepted [ADR 0004](adr-0004-thin-tool-boundary.md) keeps
capture, generic metadata/query/summary and official viewing. Consuming projects
own their integration, benchmark/oracle/candidate rules and optimization skills;
integration is not merely moved to an internal plugins directory.

The inventory found application coupling in the packaged legacy bridge,
benchmark parser, measurement adapter enum, HTTP result interpretation and their
tests. Existing benchmark/experiment/reference/knowledge and compiler-cache
orchestration also exceed the proposed daily product surface. Generic readers,
quality/provenance checks and necessary owned-process/output handling can be
reused. Raw outputs will belong to an explicit consumer directory.

This step records scope, inventory and migration order only. README, architecture,
roadmap and layer-design notices distinguish that target from current code.
No source was extracted/deleted, API removed, old evidence rewritten, GPU started
or new runtime qualification claimed. Referenced source and old releases must be
preserved before paths are retired.

## Complete thin-tool execution plan — 2026-11-12

The [master plan](rdnascope_thin_tool_master_plan_20261112.md) consolidates the
accepted scope into one implementation baseline: product/consumer ownership,
bounded official capture and viewing, proposed configuration/CLI, minimal
run/annotation/summary contracts, layer/Graph limits, overhead and lifecycle,
source migration/rollback, T0–T3 tasks, verification and release criteria.
README and roadmap now point to it. New interfaces remain explicitly proposed;
this document step did not implement extraction, start GPU work or change
current qualification.

## Thin-tool T1 migration in progress — 2026-11-12

T1.1 compared all 76 T0 snapshot entries with the live checkout: 71 identical,
five documentation/entry files changed after the master plan, no file missing.
The five current copies were frozen outside this repository before extraction.
T1.2 placed the exact legacy application bridge in a consumer-owned sidecar
outside both Git repositories, together with a local config template, HTTP result
parser, consumer skill and CPU isolation checks. Four sidecar tests passed. The
accepted model tree and historical evidence remain untouched.

T1.3 mapped 37 stage files referencing the bridge and preserved the old source
SHA in the external T0 snapshot. An independently installed 0.2.0a1 wheel
verified the historical final case before source removal. Post-removal verification
and T1.4/T1.5 are still pending. The private audit is recorded in the original
project's `artifacts/thin-tool-migration-20261112-01/`; no new GPU acceptance is
inferred from this CPU/source work.

## Thin T1/T2 implementation checkpoint — 2026-11-12

The old bridge and broad platform modules, 13 old schemas, application-bound
examples and prior tests were mapped by SHA into the external T0 source archive
before removal. The independent old wheel recursively verified the same
historical final case after the bridge removal and again after full source
removal, with identical results. Former source paths are unavailable here;
the archive and old wheel are the rollback/read path.

The new `0.3.0a1` candidate has only explicit configuration, bounded official
record/export, read-only rocpd/PFTrace/Chrome queries, deterministic scope/rank
reports and owned official UI control. The default command surface has no
benchmark/candidate/knowledge/compiler namespace or `tlp` bridge. Six focused
CPU tests passed; four consumer-side bridge/parser tests passed. A real
historical **synthetic** official Graph PFTrace produced 38 native kernel rows
in the previous qualification; the new reader returned native locators and a
small report, then started official Trace Processor on port 9003 and stopped
only its recorded process. This is an offline recheck, not new GPU collection.

The first wheel/sdist audit found no application bridge/benchmark paths; one
source-outside-checkout install and `pip check` passed before final contract
edits. The final wheel must be rebuilt/retested after T3 CPU review. Current
hardware resource discovery was read-only; physical 0/4/6 had no foreign KFD
process or active reservation at the snapshot, but a snapshot is not a lease.
Two other eligible cards had active foreign work/reservations, and physical 7
had foreign VRAM use. No device has been allocated for this migration yet.
Private actual logs and mappings are in the original workspace's
`artifacts/thin-tool-migration-20261112-01/` and new repo's ignored
`artifacts/thin-migration-20261112-01/`. T3 GPU, external consumer, cost and
final release remain open.

## Thin T3 hardware and external-use checkpoint — 2026-11-12

An initial locked physical-SMI4 run failed before collection because the
container lacked `jsonschema`; its logs and cleanup are retained. The thin
runtime validator was replaced with a packaged standard-library schema-subset
check, removing that dependency. Six local CPU tests passed after this fix.

Fresh locked R9700/ROCm10.1 captures then passed bounded synthetic checks:
single eager FP32 had five numeric samples and 16/16 kernel conservation;
dynamic Graph had five numeric samples, five ordered launch windows and 19/19
conservation. The first two dual-card choices were refused because foreign
processes occupied one selected card. A later physical-SMI5/6 two-rank
all-reduce run passed three numeric samples per rank, SQLite integrity on all
three producer DBs and 66/66 native/official merged-export kernel
conservation. Own containers and leases were released; no foreign task was
stopped. The merged file does not calibrate rank clocks, and writer completion
and independent record loss remain unknown.

An external consumer in the original project used its own config, command and
annotations without adding application code here. Seven CPU submission scopes
generated the same JSON/Markdown diagnostic summary and a next measurement;
official UI on port9003 was ready and its owned process stopped. A second
historical scalar Graph PFTrace produced 192 kernel rows via the same reader,
with its original SHA and historical status retained. The trace-off/profile/
trace-off seven-sample cost series drifted substantially; monitoring cost is
inconclusive and no one-percent claim is made. The consumer profile wrote a
167493632-byte DB and 21099130-byte PFTrace under a polled 1GiB budget;
capture/export took 3.744/6.407 seconds. Full evidence and step-by-step links
are in the original project's plan steps111–113 and its
`artifacts/thin-tool-migration-20261112-01/` directory. The FreeToken accepted
model worktree and evidence were not modified.

The [new support matrix](thin-support.md) now scopes this alpha to the actual
device/runtime/fixture. Final source-outside wheel, package audit and local
commit remain separate release gates.

## Thin local alpha closeout — 2026-11-12

The final CPU suite passed six tests, and the external consumer sidecar's
current isolated test file passed three. The final `0.3.0a1` wheel/sdist were
built after the runtime and documentation edits. In a fresh environment whose
working directory is outside this checkout, the installed wheel passed import,
version, doctor, schema, official PFTrace query, report, UI start/owned stop
and `pip check`. Every packaged Python/schema byte matched current source;
the wheel contained ten thin Python modules and three thin-v1 schemas, with no
application bridge or legacy schema. The sdist contained the generic release
note and thin docs. Local private audit JSON is under
`artifacts/thin-migration-20261112-01/final-wheel-audit.json`.

The [0.3.0a1 release note](release-0.3.0a1.md) and
[support matrix](thin-support.md) state the narrow R9700 fixture qualification,
unknown layer/rank clocks/loss and inconclusive monitoring cost. The original
project's plan steps111–114 link failures and raw validation artifacts. The
old public alpha assets and model baseline were not changed. This is a local
alpha package and reviewable source change; remote CI/public release are not
claimed by these local checks.

## Thin alpha CI migration follow-up — 2026-11-12

Draft PR 1 on `thin/0.3.0a1` exposed a stale outside-checkout wheel step in
`.github/workflows/cpu.yml`: it still passed removed `--data-dir` and imported
old `rdnascope.core`, `analysis`, `records` and registry APIs. The first 3.13
job failed at CLI argument parsing; its remote log remains on GitHub Actions
run `43144549796`. This is a CI protocol failure, not a GPU qualification.

The workflow now installs the wheel outside checkout, runs current `doctor`
and `schema`, builds a sealed generic Chrome fixture with thin-v1 contracts,
then checks native-unit query, diagnostic report, installed import path and no
implicit Torch import. The exact outside-checkout script passed locally
against the final alpha wheel (`0.3.0a1 1 1`), and the six focused CPU tests
passed again. Remote 3.12/3.13 checks must be observed before declaring CI
green; failed initial jobs remain visible.

The pushed CI migration commit `8d0d541` passed both Python 3.12 and 3.13
jobs in Actions runs `43144784053` and `43144790548`, including wheel install
outside checkout. A further workflow review found the old manual GPU workflow
still imported removed wide-alpha resource/workload modules. Its exact bytes
match the external T0 snapshot and are mapped in the original project's
`legacy-gpu-workflow-map.json`; the broken workflow was removed. Hardware
resource admission and fixture execution remain external to the thin package.
No remote GPU run or user model qualification is claimed.

The workflow-boundary commit `76c41f7` passed both Python versions in push
Actions run `43144955484` and PR Actions run `43144960378`. Draft PR 1 remains
unmerged; no public 0.3.0a1 tag or release has been created. The retained
initial CI failure and the final passing runs are separate evidence.
