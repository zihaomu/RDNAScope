# Thin RDNAScope user guide

The [master plan](rdnascope_thin_tool_master_plan_20261112.md) defines the product
boundary. The current `0.3.0a1` checkout offers `doctor`, `record`, `query`,
`report`, `view`, `view-status` and `view-stop`. The consumer owns its launch,
resource guard, marks, oracle, benchmark and optimization skill.

## Configure and record

Copy [the portable profile](../profiles/machine.example.toml) into your project
and bind exact paths. Relative tool paths resolve from the profile directory.
`rocpd_command` is argv, so a project may use a wrapper that supplies the
matching SDK environment. The tool does not silently download or choose a ROCm
runtime. `doctor` checks paths only; it does not start a GPU probe.

```bash
rdnascope --config .rdnascope.toml doctor
rdnascope --config .rdnascope.toml record --output ./traces/run-001 -- ./run_workload.sh
```

`record` invokes the official `rocprofv3` with HIP/marker tracking. The
`native_roi` profile also requests kernel dispatches. It writes the original
rocpd DB, then calls the configured official `rocpd convert` with
`--group-by-queue` to create PFTrace. It never shifts native timestamps or
serializes a substitute trace. One new run directory is required each time;
timeout/output budget failures keep logs and partial native files. The output
budget is polled and is not a filesystem hard quota.

The launched command receives `RDNASCOPE_RUN_DIR` and `RDNASCOPE_CONTEXT_ID`.
It may write `annotations.json` and `rank-map.json` into that run directory.
Alternatively `[context].annotations` may name an existing annotation JSON
whose `run_id` matches the new directory name. The tool hashes these files;
project fields remain project-owned. `rank-map.json` is an array of
`{rank,pid,device,proof}`. A caller's `exact` label is retained as metadata,
while queried native PID/rank association remains **inferred** until separately
qualified. Unmapped PID stays unmapped.

## Query and summarize

```bash
rdnascope --config .rdnascope.toml query ./traces/run-001 --view coverage
rdnascope --config .rdnascope.toml query ./traces/run-001 --provider rocpd --view events
rdnascope --config .rdnascope.toml report ./traces/run-001
```

`query` verifies every manifest artifact SHA before serving fresh or cached
data. It reads one rocpd DB, one PFTrace, or one generic Chrome trace at a
time. For multiple rank DBs, use the official merged PFTrace; the first alpha
does not infer a cross-rank clock from that merge. Related DB/PFTrace inputs
are alternative representations, so do not sum their counts. The cache is
under the explicit run directory, limited to 64 small query pages; raw inputs
are never copied there.

`report` produces `summary.json` and `summary.md` from one deterministic result.
It groups consumer scopes by name/kind/rank/time basis/clock domain, with
sample count, median, maximum and declared-window coverage. Nesting/overlap
does not become wall time. Unverified GPU intervals have unknown duration.
Caller-declared verified GPU intervals still need the consumer's actual proof;
the tool does not certify their stream dependencies. With no scopes, the report
shows native category counts and overlapping duration sums as a fallback.
Missing native input yields a failure/inconclusive report with logs retained.
Unknown rank clock calibration prevents numeric pure-wait estimates.

## Official UI

```bash
rdnascope --config .rdnascope.toml view ./traces/run-001 --port 9002 --idle-seconds 300
rdnascope view-status ./traces/run-001/ui/ID/service.json
rdnascope view-stop ./traces/run-001/ui/ID/service.json
```

Only the official Trace Processor runs locally; open the returned matching
`ui.perfetto.dev` URL in your browser after forwarding the RPC port through VS
Code. On nondefault ports, enable the **official** `Relax Content Security
Policy for 127.0.0.1:*` flag linked in the result, reopen the URL, and check
that the sidebar reports the chosen port. `view-stop` checks recorded PID,
start time, boot ID, UID and argv before signaling an owned process. Occupied
ports are refused. The UI is a view of the same official PFTrace, not an
independent timing qualification.

## Contracts and limits

Use `rdnascope schema run-manifest`, `schema annotations` and `schema summary`
for the packaged thin-v1 JSON contracts. `run-manifest.json` separates capture
and export states, retains original argv/exit/status, source SHA, rank
declarations, clock status and missing producer evidence. `complete` means
the wrapper and export exited successfully and sealed files passed basic
checks; it does not mean output correctness, no record loss or normal model
performance. CPU HIP/marker spans are host submission observations. Whole-model
Graph replay does not execute Python layer hooks on each replay; GPU layer time
requires separately verified native mapping or a proven consumer interval.

Formal scoring should keep added probes off and use an independent run identity.
The suggested one-percent monitoring overhead is a future target, not a current
qualification.
