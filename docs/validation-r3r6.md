# R3–R6 validation — 2026-11-11, alpha 0.2.0a1

R3–R6's software interfaces are implemented. Live GPU acceptance is incomplete.
All selected GPU snapshots showed foreign occupancy and the workload launcher
returned `resource_blocked` before starting a child. No new GPU/model run, foreign
process stop, accepted-source change or real-cache GC was performed.

## Software and historical evidence

- **66 CPU tests passed** on local Python 3.12, including the prior 43 lifecycle
  tests. Coverage includes typed evidence/SHA/traversal, independent-boot drift,
  duplicate input detection, output failure, changed conditions, reference scope,
  candidate-specific gates, clock restrictions, scoped dependency bounds,
  model-reference gaps, resource refusal, RAM admission, frozen helper inputs,
  owned raw-output budgets and actual CPU adapter processes.
- The historical official QUEUE export still conserves **8936 kernel intervals,
  96,430,756 ns summed duration**, with matching name/start/duration/PID/Graph/node/
  queue/stream. This is an observed overlapping duration sum, not model wall time.
  The default STREAM export remains rejected. Missing rank and deliberately wrong
  expected Graph windows are rejected; the latter is a fault-injection test.
- Truncated SQLite is rejected by integrity checks. Missing loss/clock/full-model
  coverage evidence remains unknown. No unknown capability was upgraded from a
  successful reader test.
- Frozen FreeToken output references were rechecked while replaying historical
  three-boot measurements. The three case spreads remain **49.82%, 28.61%, 7.67%**,
  and their A/A result is `inconclusive`. No new model request was made.
- Four inferred request/decode/rank groups link **1176 HC events** using the
  previously audited sequence. Decode indices 8/9 are hook coordinates, not
  global output-token IDs. The 14 linked findings retain incomplete semantics,
  unqualified clocks and null numerical/recoverable-wall gaps.
- One real kernel finding was uniquely located in the official window PFTrace
  with read-only name/time/duration/PID SQL and a pinned official Trace Processor
  build. Source and export correlation IDs retain separate meanings. No frontend,
  native serializer, browser-render trial or new trace export was added.

## Experiments and corrections

A fresh isolated RowGather candidate was prepared with source/native manifests,
patch and plan. Its owned evidence occupies approximately **56.1 MB logical /
57.9 MB allocated**, including the isolated source/native copy; this is not the
size of a new trace. Fresh candidate GPU correctness and timing remain not run.

Historical candidate replay first exposed a decision bug: local timing instability
was classified as rejection. The engine now returns `inconclusive`. The first
immutable attempt and corrected superseding record are both retained. Historical
fixture success is not relabeled as fresh candidate GPU validation.

The second adapter ran a real CPU fixture in three independent boots, then six
balanced comparison boots. Initial A/A passed; the comparison's arm stability
was unqualified, so the candidate remained `inconclusive`, `adopted: false`.
This verifies retained process/log/output/measurement/decision evidence without
claiming a CPU gain or RDNA performance qualification. Deterministic synthetic
tests separately exercise passing and rejected comparisons and reference matches.

Four private plans are prepared for native dual-rank ROI, trace-off TP2 A/A,
bounded thread screening and the isolated kernel candidate. Their device/runtime/
source/helper/fingerprint bindings are explicit. Every current launch attempt
refused occupied devices before GPU execution. The compatibility bridge's new
GPU paths, framework cache use and numerical/performance gates remain unvalidated.

## Packaging, publication and retained evidence

The implementation log records final original-project regression, source SHA,
wheel/sdist, isolated installation, link/privacy and publication checks once run.
CPU CI includes Python 3.12/3.13 and installed-wheel analysis. GPU CI is manual,
requires a separately configured trusted runner/profile and exact reviewed plan
SHA, and was not dispatched against the occupied host.

Full local inputs and logs are intentionally private. Maintainer evidence handles
under `artifacts/r3r6-20261111-01/` include `pytest-final.stdout.log`,
`pipeline-review.json`, `native-queue-audit.json`, `native-stream-audit.json`,
`freetoken-aa-review.json`, `advanced-review.json`,
`historical-candidate-corrected.json`, `candidate-prepare-review.json`,
`official-ui-location.json` and the resource-refusal records. They are not links
to public fixtures. Source tests and synthetic examples are public; actual model
prompts, traces, machine bindings, environments and complete runtime logs are not.

The [support matrix](support.md) and [workflow guide](workflows.md) separate
implemented APIs from outstanding hardware and performance acceptance. This alpha
does not close the entire R3–R6 live-validation plan.
