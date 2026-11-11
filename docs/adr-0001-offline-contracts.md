# ADR 0001: offline contracts and migration boundary

Status: accepted for the R0/R1 implementation.

The diagnostic core registers sealed, externally owned evidence by SHA and exposes
versioned small query envelopes. It does not invent clock calibration, operator
mapping or qualification from successful parsing. Native producer formats remain
unchanged. A configured upstream Trace Processor handles PFTrace.

Keep user data/config outside package resources. Bundle schemas with importlib
resources so wheels work outside a source checkout. Store registry metadata in a
transactional SQLite database, and derived payloads in atomic content-keyed files.
Input hashes are checked before and after execution and on cache hits.

The prototype remains available through an explicit forwarding bridge. Do not copy
its hardcoded model/device/SDK policies into a generic package or reinterpret its
CLI. Later milestones can replace one adapter at a time, retaining old evidence.

Declared provenance links describe lineage without asserting semantic equivalence.
Normal-model performance, clock calibration and complete replay coverage need
their own evidence gates. Unknown results remain unknown.
