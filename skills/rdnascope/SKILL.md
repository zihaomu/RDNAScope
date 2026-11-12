---
name: rdnascope
description: Read a bounded RDNA diagnostic run, summarize scope/rank evidence, and open its official Perfetto trace.
---

# RDNAScope thin observation

Read the [thin user guide](../../docs/thin-user-guide.md) and current
[support matrix](../../docs/thin-support.md). The consuming project supplies
application launch, scope marks, output oracle, trace-off baseline and any
optimization decisions. Never add a project adapter to RDNAScope.

1. Run `rdnascope --config PROFILE doctor` to check configured paths. This is
   an offline identity check, not GPU qualification.
2. Use `record --output NEW_RUN -- COMMAND...` only for an explicitly requested
   diagnostic with a bounded profile. Record the application and official tool
   stdout/stderr and inspect `run-manifest.json` before interpreting rows.
3. Use `query RUN --view coverage`, then `query RUN --view events` or `kernels`
   with one selected provider. Cite the source SHA and native locator. DB and
   PFTrace derived from the same capture are alternative representations, not
   independent counts.
4. Use `report RUN` for the common `summary.json` and `summary.md`. A CPU
   submission scope is not a GPU layer interval. Missing/unknown coverage and
   rank clocks remain unknown. Native category sums can overlap.
5. If a PFTrace is present, use `view RUN --port PORT --idle-seconds N` to start
   an owned official Trace Processor. Forward PORT in VS Code and open the
   exact official URL. For nondefault ports, enable the official local WebSocket
   port flag shown in the response. Inspect/stop only the recorded owned state.

Propose one smallest discriminating next measurement from the observed location.
Do not claim model speedup, pure rank waiting, kernel root cause or zero trace
overhead from this diagnostic alone. Preserve failed runs and raw official files.
