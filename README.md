# RDNAScope

Evidence-backed performance diagnostics for AMD RDNA model, kernel and multi-GPU workloads.

**0.2.0a1 is an alpha for evidence-based diagnosis and bounded optimization experiments.** It provides read-only native queries, scoped capabilities, benchmark contracts, model/kernel/multi-GPU findings, candidate gates and managed storage/processes. Default analysis stays offline. Fresh FreeToken GPU validation and a second GPU pair are pending resource availability; no new model speedup or general RDNA support is claimed.

```bash
python -m pip install .
rdnascope --data-dir /tmp/rdnascope-demo doctor
rdnascope --data-dir /tmp/rdnascope-demo register --run demo --identity examples/offline-identity.json examples/chrome.json
rdnascope --data-dir /tmp/rdnascope-demo query demo --view summary
rdnascope --data-dir /tmp/rdnascope-demo query demo --view kernels --limit 10
rdnascope --data-dir /tmp/rdnascope-demo analyze demo --output demo-analysis
rdnascope --data-dir /tmp/rdnascope-demo kb verify demo-analysis
rdnascope --data-dir /tmp/rdnascope-demo storage-stats
```

Run the same query again to reuse its content-keyed result. Registration stores file references and SHA, without copying input bytes. The example is synthetic, contains no model data, and establishes no GPU qualification. Use absolute input paths when working outside the checkout.

- Providers: rocpd SQLite, PFTrace through an explicitly configured official Trace Processor, HTTP performance JSON, Chrome traces, and existing normalized TLP datasets.
- Query views: summary, events, kernels, metrics, phases, collectives, coverage and provenance. A view unsupported by a provider returns explicit unknown capability; empty rows are not proof that work is absent.
- Thirteen versioned schemas ship in the wheel, including immutable capabilities, measurements, references, semantic maps, findings and cases. Evidence uses local source bindings and content SHA.
- Input SHA is checked even on cache hits. Unknown clocks and semantic mappings remain unknown/inferred.
- R2 adds configured capacity/free-space checks, reservations, leases, pin/reference protection, previewed explicit GC, ABI namespaces, bounded foreground workers and official Perfetto service lifecycle. Old/unmanaged caches and external evidence are excluded from GC. [Usage and limits](docs/lifecycle.md).
- A/A uses independent process boots. Comparisons bind the output oracle, resource checks, exact conditions and declared changes. Drift returns `inconclusive`; screening never adopts source code. HTTP first-text is distinct from TTFT and token ITL.
- Three-domain reports retain unknown shape, missing semantic positions and unqualified rank clocks. `ui locate` maps a finding to an official Perfetto query; there is no new trace serializer or frontend.
- Two result adapters are available: FreeToken HTTP evidence and a runnable synthetic CPU fixture. GPU compatibility actions require a private, SHA-bound runtime/ownership adapter. They are prepared, but not newly GPU-qualified in this alpha.
- The `tlp` entry point is an opt-in bridge to the untouched prototype, **not a reinterpretation of old arguments**. See [migration](docs/migration.md).

[中文说明](README.zh-CN.md) · [Workflow guide](docs/workflows.md) · [Support matrix](docs/support.md) · [Architecture](docs/architecture.md) · [Configuration](docs/configuration.md) · [Validation](docs/validation-r3r6.md) · [Roadmap](docs/roadmap.md)

Agent workflow: [repository skill](skills/rdnascope/SKILL.md). Development checks: `python -m pip install -e '.[test]'` then `python -m pytest -q`. CI also builds and installs the wheel outside the checkout.

Core installation needs Python 3.12+ and jsonschema. It does not install Torch, ROCm, model weights, browser binaries or TraceLens. Managed lifecycle currently requires Linux `/proc` and flock; uncached offline queries remain independent. No hardware qualification or normal-performance acceptance follows from software tests or explicit command execution.

Licensed under Apache-2.0. See [LICENSE](LICENSE) and [third-party boundaries](THIRD_PARTY.md).
