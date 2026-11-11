# Configuration and offline usage

Path precedence is CLI > `RDNASCOPE_DATA_DIR`/`RDNASCOPE_CACHE_DIR` > TOML > XDG defaults. Select TOML using `--config FILE` or `RDNASCOPE_CONFIG`. TOML-relative paths are resolved against its directory, not CWD. Explicit data roots default to a cache beneath that root unless another cache root is selected. `doctor` does not create those directories.

See `profiles/machine.example.toml`. Copy private settings to a Git-ignored `*.local.toml`. A configured official Trace Processor is required only for PFTrace queries. No producer environment, model, binary download or driver change is performed by this package.

```bash
rdnascope identity --run trial --output identity.json
# Edit only known workload facts; leave missing clocks/identities unknown.
rdnascope --config /path/to/machine.local.toml register --run trial --identity identity.json /path/to/rank0.db /path/to/rank1.db
rdnascope --config /path/to/machine.local.toml query trial --view kernels --limit 20
```

Register multiple formats and declared derivation links with `register --manifest capture.json`:

```json
{
  "schema_version": 1,
  "identity": {"...": "full identity object produced by the identity command"},
  "inputs": [
    {"label":"raw0","path":"rank0.db","format":"rocpd"},
    {"label":"display","path":"trace.pftrace","format":"pftrace","derived_from":["raw0"]}
  ]
}
```

This is an illustrative descriptor: replace the identity placeholder with the actual full object. Input paths are relative to the descriptor. Cycles and unknown parents are refused. Derivation edges are **declarations**, not a semantic export-conservation audit. Source bytes remain outside the registry.

`inspect RUN` verifies immutable identities/files. Re-registration with the same run ID is refused. A source changing after registration refuses queries, including cache hits. SQLite inputs with active WAL/journals are refused; this tool does not checkpoint or modify a producer database.

`query RUN --view summary|events|kernels|metrics|phases|collectives|coverage|provenance` returns schema-v1 JSON. Use `--limit`, `--offset`, `--provider` and `--no-cache` explicitly. Rows follow native source ordering; pagination is not global timeline stitching.

For related full/window exports, select a content ID listed by `inspect RUN`:

```bash
rdnascope --config /path/to/machine.local.toml query trial --provider pftrace --view kernels --artifact sha256:ACTUAL_CONTENT_SHA
```

Repeated `--artifact` options select several independent sources. Related representations sharing declared ancestry are refused to avoid double counting. This check cannot detect undeclared overlap.

Derived cache keys bind input SHA, semantic identity, provider/binary build, implementation, view and page. Run/experiment labels do not multiply equivalent payloads. R1's `storage-stats` separated external evidence, registry and query cache; that initial release had no deletion command.

R2 adds the optional `[storage]` policy, managed namespace/job accounting, explicit
GC and official service process RSS/PSS. See [lifecycle](lifecycle.md). Existing R1
query files stay untracked/protected; new query objects receive lifecycle records.

## Evidence records and workload bindings

`[sources]` maps portable source IDs to local directories. Paths are resolved
relative to the TOML file. Record evidence contains only a source ID, a relative
path, SHA and optional typed JSON assertion. Symlink escapes and `..` traversal
are refused. The reserved `rdnascope-cache` and `rdnascope-evidence` bindings must
match this profile's cache and `data_dir/evidence` roots.

`[machine]` supplies the explicit SMI executable, optional KFD/proc roots,
reservation directory, physical/unfiltered exclusions and optional
`min_available_ram_bytes`. These facts are local policy. A device snapshot is
read-only and does not reserve cards. Missing configured RAM observations block
admission. No default device exclusions, fixed model, RAM threshold or shared
reservation path are embedded in the generic core.

`[adapters.NAME]` binds a trusted executable with `executable_sha256` and optional
`identity_files` (path/SHA). Identity files are verified and frozen into each job
before launch; exact argument references use those frozen bytes. Venv executable
paths remain intact. GPU adapters require `gpu=true`, fixed `actions` templates
and the implemented `locked-owner-observer-v1` protocol. Core discovery is only
the preflight; the adapter must acquire/recheck the actual runtime lease and
continuous interference guard. Templates may expand `{run_id}`,
`{physical_gpus}`, `{timeout_seconds}` and an owned `{output_dir}`. Arbitrary GPU
argv are not accepted. This is a trusted local integration interface, not a
sandbox for untrusted adapters.

A workload plan supplies a fresh run ID, adapter/action, selected physical cards,
time/disk budgets and optional ABI namespace/fingerprint. GPU outputs default to
protected per-run evidence outside GC. That evidence and the cache must reside
on the same filesystem for current admission accounting. Monitoring can stop an
owned over-budget job but cannot enforce a filesystem hard quota. Full examples,
benchmark semantics and UI instructions are in [workflows](workflows.md).
