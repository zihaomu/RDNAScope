# Evidence and optimization workflows

The CLI works without an agent service. Every command emits JSON; inspect its
`status`, `issues`, `limits` and `basis`. Command completion alone is not a scientific
pass. Immutable record IDs cannot be reused, including unsuccessful attempts.

## Offline diagnosis

Follow the README example to register, query, analyze and verify a synthetic run.
`analyze RUN --output PREFIX` writes model, kernel and multi-GPU findings and a case
whose ID is PREFIX. `records list finding` lists findings. Native inputs remain
external references, with SHA checked on each read. `kb search WORDS` searches
case titles/observations; `kb verify ID` recursively checks records and sources.

Use `--provider` and `--artifact` to choose one registered representation. Full
and window exports are alternatives; they are not additive observations. Without
explicit semantics the report is descriptive, with missing request/token/shape
and dependency qualifications preserved.

`semantics register map.json --id MAP` accepts a versioned semantic sidecar.
Inferred associations remain inferred. Exact entries/dependencies and complete
scope require independent evidence assertions. Clock calibration also needs a
qualified `cross_rank_clock` capability for the same runtime, world and inputs;
setting a clock flag cannot qualify it. Use `schema semantic-map` for the contract.
Then run `analyze RUN --map MAP --output NEW_PREFIX`.

## Measurement before optimization

The included CPU fixture exercises independent boots, output checks, bounded jobs,
evidence pinning and comparison. These thresholds are example protocol choices.
They do not describe any GPU's noise or performance target.

```bash
rdnascope --data-dir /tmp/rdnascope-bench bench contract examples/cpu-benchmark-contract.json --id cpu-protocol
rdnascope --data-dir /tmp/rdnascope-bench workload fixture --contract cpu-protocol --prefix cpu-aa --phase aa
rdnascope --data-dir /tmp/rdnascope-bench workload fixture --contract cpu-protocol --prefix cpu-ab --phase compare
rdnascope --data-dir /tmp/rdnascope-bench records list measurement
```

The second command starts three independent CPU processes; the third starts six
in the preregistered A/B order. Samples, failures and logs are retained. Timing
drift may produce `inconclusive`; do not retry until a favorable result appears.
These commands do not modify a model or adopt the candidate.

For real results, register a benchmark contract and use `bench ingest SPEC --id ID`.
The spec binds `contract_id`, adapter (`freetoken-http` or `metric-json`), boot, arm,
context, input evidence and resource evidence. FreeToken additionally uses an
independent frozen `oracle_ref`. Evidence consists of `source_id`, relative path,
SHA and optional typed JSON-pointer assertion. Obtain the fields with `schema
benchmark-contract` and `schema measurement`; bind sources in a private profile.

`bench aa M0 M1 M2` compares independent boot medians, with required warmups/cases,
output/resource checks and exact matching context. Repeated tokens or relabeled
copies of one input do not become independent boots. `bench compare --baseline
A0 --baseline A1 --baseline A2 --candidate B0 --candidate B1 --candidate B2`
requires the contract's balanced sequence and permits only declared intentional
changes. Formal comparisons require at least three pairs with both orders. ABBA
is screening only and still needs a separate qualified baseline A/A in experiment
evaluation. The reported pair gain range is observed, not a population confidence
interval; three boots do not establish production P95.

HTTP wall, first-text and reported server decode rate have separate metric names.
Without token timing there is no ITL; first-text is not renamed TTFT. Failed or
missing requests remain failures. Output parity reported by the producer alone
does not substitute for an independent text/token reference.

## References and findings

`reference register FILE --id REF [--evidence REFS.json]` distinguishes specification
bounds, measured same-condition baselines and reachable calibrations. Use
`reference match REF CONTEXT.json` before `analyze --reference REF`.

Measured references require qualified, matching measurements. Reachable kernel or
communication references additionally require the corresponding device/runtime
timing capability. Unknown shape/layout/topology or an unqualified reference
produces an applicability explanation, not a numerical efficiency. There is no
qualified real kernel/communication calibration bundled with this release.

For model references, pass matching `--measurement ID` options to `analyze`; their
input corpus must be exactly the registered HTTP inputs and their evidence basis
must agree. Matched wall differences remain descriptive observations. Kernel
duration sums and rank entry skew are never promised recoverable model latency.

## Candidate decision

`experiment evaluate SPEC.json --id EXPERIMENT` records one hypothesis, baseline
and candidate source digests, type, typed gate assertions and measurement IDs.
Use `schema experiment` for result fields. Input keys are `basis`, `hypothesis`,
`candidate_type`, `baseline`, `candidate`, `gate_evidence`, `aa_measurements`,
`baseline_measurements` and `candidate_measurements` (see
[experiment implementation](../src/rdnascope/experiments.py) for producer details).

Kernel/layout, cache/transfer, thread/config and parallel/topology changes require
different correctness gates. Kernel fixtures do not block unrelated thread
experiments. Invalid independent controls and unstable measurement are
`inconclusive`; true candidate correctness failure is `rejected`. A screening pass
is a hypothesis; only qualified formal comparisons and all applicable gates can
be `validated`. All decisions have `adopted: false`; source adoption is separate.

Archive related records with `kb archive CASE.json --id CASE`; include each child's
kind, ID and `record_sha256`. Verify the resulting case before using it as a
regression reference. Preserve failed attempts rather than editing old records.

## GPU execution and capture

`devices --physical-gpus N M` explicitly reads SMI/KFD/PCI/processes/reservations.
It provides a snapshot, not a reservation. `doctor` never performs this probe.
`workload run PLAN.json` needs an explicitly bound, SHA-checked private adapter.
GPU actions additionally require selected physical devices, fixed argument
templates and `locked-owner-observer-v1`: the trusted adapter acquires/rechecks
the shared lease, observes interference and cleans only its owned runtime.
An occupied/excluded card or insufficient configured RAM returns resource_blocked
before a child is started. No foreign process is stopped.

The optional FreeToken compatibility helper is included under `bridges/`; its
bindings supply the original helpers, runtime lock, foundation launcher and model
paths. It prepares fresh isolated candidates or invokes bounded native ROI, A/A,
configuration screening and candidate actions. The application retains its exact
Torch/Triton/native pairing. Collection uses rocprofv3/rocpd and upstream PFTrace
conversion. The original application and evidence stay read-only. This bridge
requires its original external helper installation; it is not a standalone
FreeToken distribution or a newly qualified GPU backend.

Plans declare time and disk reservations and may bind a full cache fingerprint
and namespace. New raw outputs use `data_dir/evidence/RUN`, outside lifecycle GC;
they have a per-run monitored budget and are retained on failure. Managed logs,
scratch and compilation namespaces retain the R2 lease/admission protocol. Raw
evidence and cache must share a filesystem for this accounting. This is monitored
admission, not an OS hard quota; separate evidence retention remains an explicit
owner policy.

After sealing producer files, use `capture audit RUN --contract AUDIT.json
--pftrace CONTENT_ID --output NEW_FILE`. The audit checks SQLite integrity, rank
coverage and native/export interval conservation. Optional Graph windows specify
their expected counts. Writer completion and loss status require separately
verified typed assertions. Missing evidence stays unknown. Successful export is
not full-model coverage, normal-performance or cross-rank-clock qualification.

Register a scoped capability using `capabilities register FILE --id ID` and resolve
against an exact context with `capabilities resolve CONTEXT.json`. Changed device,
runtime, tool build, mode, world or workload invalidates the match. The
[support snapshot](support.md) lists the actual current qualification.

## Official UI

```bash
rdnascope --config /path/to/machine.local.toml ui locate FINDING --pftrace CONTENT_ID --port 9001
rdnascope --config /path/to/machine.local.toml service start --run RUN --artifact CONTENT_ID --port 9001 --idle-seconds 300
```

Use a free port. The service response includes the official versioned Perfetto UI
URL and local RPC port. Forward that port with VS Code Remote, open the returned
official UI URL locally and connect to the forwarded RPC. Paste `official_ui_sql`
from `ui locate` into the UI Query tab. A native lookup must have one unique
name/time/duration/PID match; PFTrace slice IDs also bind the exact parser build.
Existing services are not adopted or stopped. See [lifecycle](lifecycle.md) for
service status, explicit keep and stop. Browser rendering was not revalidated in
the R3–R6 pass; unique source-to-slice SQL lookup was.
