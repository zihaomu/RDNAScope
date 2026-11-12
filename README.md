# RDNAScope

RDNAScope is a thin RDNA observation tool. A consuming project supplies its
command, runtime, resource allocation and optional scope marks. RDNAScope
captures bounded official ROCm traces, reads sealed native evidence, creates a
small scope/rank summary and opens the unmodified official Perfetto UI.

The project owns its correctness oracle, trace-off benchmark, candidate changes
and optimization decisions. RDNAScope contains no application adapter catalog.

The current local source is **0.3.0a1 thin alpha**. Synthetic R9700
eager/Graph and dual-rank capture passed in one locked ROCm environment;
monitoring overhead and model performance remain unqualified. See the
[support matrix](docs/thin-support.md) for the exact scope and the
[master plan](docs/rdnascope_thin_tool_master_plan_20261112.md) for the
completed implementation record.

## Install and use

Python 3.12 or newer:

```bash
python -m pip install .
rdnascope --version
rdnascope --config .rdnascope.toml doctor
rdnascope --config .rdnascope.toml record --output ./traces/run-001 -- ./run_workload.sh
rdnascope --config .rdnascope.toml query ./traces/run-001 --view coverage
rdnascope --config .rdnascope.toml report ./traces/run-001
rdnascope --config .rdnascope.toml view ./traces/run-001 --port 9002 --idle-seconds 300
```

Copy the [portable profile](profiles/machine.example.toml) into the consuming
project and bind its official tool paths. `record` is the only command above
that starts the application. Queries and reports are offline. Raw rocpd DB and
PFTrace stay in the consumer-selected run directory, with SHA and failure
records; RDNAScope does not create a substitute trace format.

Read the [user guide](docs/thin-user-guide.md) for contracts, Graph/rank limits,
official UI forwarding and source retention. The [migration guide](docs/thin-migration.md)
explains the incompatibility with the older wide alpha. Apache-2.0 licensed.
