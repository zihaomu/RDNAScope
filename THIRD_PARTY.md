# Third-party boundaries

RDNAScope source is licensed under Apache-2.0. Dependency and optional tool licenses remain their own:

- pytest: optional development dependency, MIT; not vendored.
- Perfetto Trace Processor/UI: external optional upstream tools; their upstream licenses and notices apply. No binary, frontend assets or source are bundled.
- ROCm rocprofiler/rocpd: producer/exporter environment, not bundled or installed by this CPU core.

The repository examples are synthetic RDNAScope fixtures. Private trace files, model weights, compiled native libraries, browser/tool downloads and prototype experiment data are not distribution contents. Future redistribution of an upstream component requires its own notice and packaging review.
