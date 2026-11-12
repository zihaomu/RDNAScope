# Thin product support matrix

Status as of 2026-11-12. The full local validation log is kept in the Git
checkout's `docs/implementation.md` and the original project's plan. A working
command or CPU test does not qualify a GPU mode.

| Capability | Current scope | Status |
|---|---|---|
| Install and offline configuration | Python 3.12+; no application package | Six tool CPU tests, three consumer isolation tests and final outside-checkout wheel/`pip check` passed |
| Generic Chrome X reader | Explicit file and unit, SHA-verified | Local CPU fixture passed |
| rocpd reader | Sealed single DB, integer native intervals | Synthetic SQLite and single GPU actual DB passed; three dual-rank DBs each pass SQLite integrity and aggregate via official PFTrace |
| PFTrace reader and official UI | Matching Trace Processor v59.1; one official file | Actual single/dual export query passed; official service ready/owned stop passed on new run; local VS Code opening remains user-side |
| Bounded `rocprofv3` wrapper | Explicit `rocm_native` native ROI | CPU timeout plus actual single/dual fixture capture/export passed; output cap is polled |
| Scope/rank summary | Caller annotations and native fallback | External consumer seven CPU submission scopes passed; caller GPU interval proof remains external |
| Single R9700 eager | Physical SMI4, gfx1201, locked ROCm 10.1 image, FP32 1024 elements | Five numeric samples; 16/16 native/export kernels conserved |
| R9700 Graph | Same device/runtime, dynamic values 3/5/7/9/11 | Five numeric samples; 19/19 native/export kernels; five Graph launch windows each with two kernels; no general layer mapping |
| R9700 dual rank | Physical SMI5/6, two-process synthetic all_reduce | Three numeric samples/rank; 33/33 native kernels/rank and 66/66 merged official export; PID/device inferred, cross-rank clock unknown |
| External reuse | Consumer-owned config/marks and historical second scalar Graph workload | New consumer CLI capture/report/UI passed; second PFTrace offline read returned 192 kernels, no new GPU claim |
| Runtime perturbation | Trace-off / trace-on / trace-off 7-sample small fixture | Diagnostic/inconclusive: large noise/order drift; no ≤1% claim |

The live captures used R9700/gfx1201, the locked ROCm 10.1.0 image, the SDK
`rocprofv3` rocpd producer and matching official `rocpd convert`; actual
producer/converter SHA is sealed in each run manifest. No other RDNA device,
ROCm pairing, FreeToken model, normal TP2 latency, calibrated multi-rank wait,
independent writer completion/loss or verified GPU layer interval is qualified.
All new runs remain diagnostic. Prior wide-alpha GPU fixtures and model attempts
retain their original scope and failures.
