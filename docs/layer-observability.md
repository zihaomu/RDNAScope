# Layer-level observability design

Status: design, not an implemented or GPU-qualified collector. The user narrowed
daily monitoring to layer-level evidence that helps choose the next optimization
target while keeping official benchmark scores free of new layer probes.

The later [thin-tool decision](adr-0004-thin-tool-boundary.md) fixes ownership:
application layer hooks and benchmark protocols belong to the consuming project.
RDNAScope receives generic scope/rank observations and produces the shared
summary. This design does not authorize an internal catalog of model adapters.

The first delivery should provide one deterministic JSON summary and a compact
layer table for both an agent and a human. Group by workload, request, phase,
position and rank. Include layer type, timing kind, samples, missing coverage,
variability, observation quality and the next discriminating experiment. Keep
native trace details in the existing official Perfetto workflow.

## Measurement modes

- Benchmark mode leaves new layer instrumentation disabled. Existing output,
  identity and resource safeguards remain. This does not claim zero overhead for
  the existing benchmark harness.
- A separate bounded diagnostic run produces layer samples under matched input,
  source, runtime, Graph, warmup and cache conditions. It has its own run ID and
  links to the benchmark's experiment/workload identity. Its intervals are not
  an exact decomposition of another run's HTTP latency.
- A future progress view may show existing request/phase progress and the latest
  matched layer snapshot. Label snapshot age and sampling scope; do not present
  an old sample as continuously measured GPU-layer completion.

## Graph and timing constraints

Whole-model Graph replay bypasses Python layer calls. Capture-time host ranges
do not establish per-replay layer timings, and CPU submission duration is not
GPU execution duration. Verify a native node-to-layer mapping or a diagnostic
Graph event-boundary implementation before reporting decode-layer intervals.

Do not split a production Graph into one Graph per layer. Additional event nodes
belong to the diagnostic mode and require output, stream, replay and perturbation
checks. Reading samples less frequently does not remove event nodes already
captured into every replay. See the
[PyTorch Event contract](https://docs.pytorch.org/docs/2.14/generated/torch.cuda.Event.html).

Preallocate bounded storage; no per-layer synchronization, JSON serialization or
disk writes. Define event generation/completion/readout/reuse explicitly so a
later replay cannot overwrite the sample being attributed to an earlier one.
Missing/not-ready/overflow states remain visible. If safe readout is unavailable,
reduce diagnostic scope and leave decode-layer timing unknown.

## Prioritization and acceptance

Start with layer boundaries, not a complete attention/MoE/copy/kernel breakdown.
An unusually long layer justifies one targeted follow-up. A rank-duration
difference does not prove pure rank waiting; overlapping layer intervals are not
summed into HTTP wall time or promised recoverable latency. CPU/offload and
unobserved work remain explicitly outside the measured interval.

Validate the record/summary CPU contract, then bounded eager/Graph GPU fixtures,
then a matched model window. Before enabling concurrent monitoring in scored
benchmarks, preregister and measure its overhead. An incremental overhead target
of at most1% is a design goal, not a qualification claim; unresolved baseline
variation produces inconclusive and keeps new probes disabled for scoring.
Preserve independent source-isolated candidate and trace-off model acceptance.
