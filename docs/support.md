# Support snapshot — 0.2.0a1

Status is evidence-scoped. A package version never qualifies all RDNA devices.
No new GPU/model process was started during this implementation pass: selected
devices were occupied by other jobs and admission refused them.

| Area | Observed validation | Boundary |
|---|---|---|
| Offline core | Linux, local Python 3.12; remote Python 3.12/3.13 CPU tests, build and installed-wheel analysis passed | CPU software qualification only; [actual CI](https://github.com/zihaomu/RDNAScope/actions/runs/43002759303) |
| Native readers | Historical R9700/gfx1201, locked ROCm 10.1 / HIP 7.16, official rocpd/PFTrace QUEUE path | Historical reanalysis; not a new collection qualification |
| Native conservation | 8936 kernels, 96,430,756 ns sum; names/start/duration/PID/Graph/node/queue/stream match | Two decode Graph replays per rank; not complete model coverage |
| Rejected inputs | Historical STREAM mismatch, synthetic truncated DB/missing rank/bad Graph window | Negative evidence remains archived |
| Semantics | 1176 historical HC events, four inferred request/decode/rank groups | Hook decode index is not a global token ID; exact association remains unqualified |
| Official UI | Unique source finding to official PFTrace slice; parser build pinned | SQL locator verified; no new browser render trial |
| FreeToken measurements | Frozen 3-boot A/A reanalysis preserves 49.82% / 28.61% / 7.67% spreads | Inconclusive under its historical contract; no new TP2 throughput gain |
| Candidate source | Fresh isolated RowGather source/patch/manifests prepared | Fresh GPU correctness/local timing/model A/B not run; no adoption |
| Workload generalization | `freetoken-http` reader and actual `metric-json` CPU fixture launches | Second GPU device-pair validation pending |
| Compilation cache | Managed fingerprint/lease/reuse/quarantine protocol tested with CPU fixtures | Fresh Torch/Triton cache behavior not qualified |
| Cross-rank clocks/wait | No new calibration | Unknown; arrival clues are not pure communication wait |
| Reachable kernel/communication reference | Registration/matching gates tested synthetically | No real calibrated reference in this release |
| PMC, bandwidth counters, PC sampling, other RDNA SKUs | Not tested | No support inferred from R9700 or Instinct |

Capabilities use `not_tested`, `qualified`, `conditional`, `failed` or `unsupported`
per feature and exact device/runtime/backend/tool/mode/world/device-set/workload
context. Historical data, live tests, synthetic fixtures and declarations have
different `basis` values. Missing writer/loss/coverage evidence is not a pass.

The remaining live acceptance work is: minimum eager/Graph fixtures and timing
references; fresh dual-rank native ROI plus outputs/coverage/perturbation; stable
trace-off TP2 controls and a justified candidate comparison; another available
device pair. These need exclusive allocation and fresh runtime checks. A blocked
resource check does not qualify those items. An unstable real A/A should end with
an instability report, not repeated attempts until a speedup appears.
