# Migration from the wide 0.2.0a1 alpha

`0.3.0a1` is a deliberately narrower, incompatible API. `rdnascope` now exposes
`doctor`, `schema`, `record`, `query`, `report` and official `view` commands.
The old registry/records, benchmark/candidate/reference/knowledge, compile
namespace, workload adapters, managed worker/GC and `tlp` bridge commands are
not included in the new distribution. This is not an automatic migration of
old run data or claims.

Keep the independently installable old `0.2.0a1` wheel to read old records.
The historical source snapshot and post-release local fixes are archived
outside the new checkout with exact SHA mapping. Any source path removed from
this checkout is explicitly unavailable at that former location; use the
matching archived bytes and old environment for historical auditing. Old
immutable records and raw DB/PFTrace files are not rewritten or deleted.

Application bridges, result parsers and optimization skills belong to the
consumer workspace. The new run directory contains a small manifest alongside
official native files. To inspect an old trace through the thin reader, first
prepare a **new** explicit run directory and manifest referring to preserved
official bytes; do not mutate old records or claim that a new run was captured.
