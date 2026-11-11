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
