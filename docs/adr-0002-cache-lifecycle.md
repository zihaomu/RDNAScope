# ADR 0002: separate cache ownership and conservative deletion

Status: implemented for R2, local validation recorded separately.

Keep R1's external evidence registry unchanged. A separate cache-root index owns
only new query objects, compiler namespaces and job directories. Existing files
are not adopted merely because their names look familiar. An owner marker binds
the root and UID; all cooperating operations use the same flock and lifecycle index.

GC is a two-step protocol: record an immutable preview, then explicitly execute
that exact plan while rechecking the current object and its protections. Record
intent before deleting, and retain tombstones. Unknown, changed or interrupted
states protect bytes instead of pretending they were verified/deleted. Reconcile
repairs metadata only. Quota admission never triggers automatic eviction.

Use declared full fingerprints and exclusive writers for compilation caches; do
not infer ABI compatibility from gfx alone. Quarantine non-success writers. Reserve
expected growth and monitor jobs; this is not an OS hard-quota or cgroup boundary.

Supervise only processes started by this tool. Keep the child group leader
waitable until owned-group cleanup is complete, then reap it and adopted children.
Use upstream HTTP/RPC, UI and idle expiry for Perfetto. The locally validated
last-query idle behavior is explicitly selected and version/tool identity retained.
Do not take over a pre-existing server or invent a second trace serialization.
