# R2 managed cache and process lifecycle

RDNAScope 0.1.0a2 manages **new query results, explicit compiler namespaces and owned
worker/service logs**. It does not take ownership of old TLP caches, model weights,
FreeToken worktrees, external DB/PFTrace inputs or the prototype's existing UI.
The R1 evidence registry keeps its original schema. Lifecycle metadata uses a
separate versioned SQLite index inside `CACHE/.rdnascope/`.

## Policy and accounting

Add owner-selected thresholds to a private TOML profile:

```toml
[storage]
# max_bytes = ...          # total logical file bytes under the cache root
# min_free_bytes = ...     # minimum free bytes on its filesystem
# ttl_seconds = ...        # eligibility age, not an automatic deletion timer
query_reserve_bytes = 8388608
```

Omitted thresholds are unconfigured. No host-wide quota or TTL is guessed, and
automatic GC is disabled. `doctor` reports policy without creating directories.
`cache preflight --reserve-bytes N` creates/opens lifecycle bookkeeping and checks
current files, live reservations and filesystem free space. It returns exit 2 when
blocked. This does not reserve space against unrelated programs on the filesystem.

```bash
rdnascope --config machine.local.toml cache preflight --reserve-bytes 8388608
rdnascope --config machine.local.toml storage-stats
rdnascope --config machine.local.toml cache list
```

Query misses reserve the configured estimate before provider execution and recheck
actual output size before atomic publication. Choose an estimate suitable for the
page size. Cache hits may still be read when a capacity limit is exceeded. `--no-cache`
does not create lifecycle state. Query payload byte/time bounds remain independent.

Statistics separate external references, query/namespace/job payloads, control
metadata, unmanaged cache files and file allocation. Unmanaged files and audit
metadata count against the cache budget but are not GC candidates. Source evidence,
other environment/download caches, worktrees and process memory are separate.
Logical bytes and allocated file blocks do not equal a filesystem's full quota usage.

This is application-level admission control with periodic worker monitoring, not a
filesystem hard quota. A writer can overshoot between checks; final checks catch
fast-exit writers too. Audit/cleanup metadata may grow after admission is blocked.
Other programs can consume disk after preflight. GPU collectors/exporters are not
yet migrated to this budget API; that requires their later adapter qualification.

## References, leases and explicit GC

```bash
rdnascope --config machine.local.toml cache pin query:CONTENT_KEY --reference case:my-case
rdnascope --config machine.local.toml cache gc --older-than-seconds 86400 --output gc-plan.json
# Review candidates, protected reasons and estimated logical bytes first.
rdnascope --config machine.local.toml cache gc --execute --plan gc-plan.json
rdnascope --config machine.local.toml cache unpin query:CONTENT_KEY --reference case:my-case
```

IDs come from `cache list`; a query object uses `query:QUERY_ID`. The age above is
an example, not an installed default. `--reclaim-bytes N` selects oldest eligible
objects until the requested logical byte target. Preview writes no payload deletion.
Its optional output must be a new file outside the managed cache.

Execution requires the unchanged locally recorded plan. The store lock serializes
publication, pinning, lease admission and GC. Execution rechecks current references,
access times, object state, content hash and inode. A new access or pin after preview
causes a skip. Active leases and pending/unreconciled job references protect objects.
Leases bind PID, Linux boot ID, process start ticks and UID; PID reuse is not liveness.

Unmanaged paths, symlinks, hardlinks and foreign/special files are protected. GC
never traverses outside the owned root. Changed/unsafe objects fail closed, and
unsafe root accounting blocks new allocation rather than understating usage.
Deletion records intent before unlinking and keeps the original SHA/tombstone.
Missing bytes are reported as unavailable. `cache reconcile` can complete metadata
for an already-absent deletion, drop dead leases and mark/pin abandoned jobs; it
does not delete files or signal a recovered PID. A partially removed directory
remains protected for explicit investigation.

## Compilation namespace and bounded commands

```bash
rdnascope --config machine.local.toml cache namespace fingerprint.json
rdnascope --config machine.local.toml cache run \
  --namespace namespace:ACTUAL_KEY --fingerprint fingerprint.json \
  --reserve-bytes 104857600 --timeout-seconds 60 -- python my_fixture.py
```

The fingerprint schema binds gfx, Python ABI, exact framework/compiler/SDK identity,
native/source/codegen SHA and flags. See the explicitly synthetic
[example](../examples/cache-fingerprint.json). `schema cache-fingerprint` exports
the fifth packaged schema; the four evidence contracts remain v1.

Equivalent fingerprints reuse a namespace. `--cold-session SESSION` makes an explicit
separate condition; repeating that session can reuse it within a matched experiment.
The caller must establish the actual environment identity; declarations do not verify
an installed Torch/Triton/ROCm stack. CPU fixtures test mechanics only.

Use `cache run` to hold an exclusive writer lease. The backend variable is
`TRITON_CACHE_DIR`, `TORCHINDUCTOR_CACHE_DIR`, or the custom fixture variable
`RDNASCOPE_COMPILE_CACHE`. Framework/version-specific behavior is not qualified by
these filesystem tests. Direct writers that bypass the lease protocol are unsupported;
content changes outside the protocol refuse reuse. No existing compiler cache is
copied or cleared, and no framework is installed by namespace creation.

Commands run in their caller CWD with a per-job scratch directory as TMPDIR. Logs,
argv, environment overrides/fingerprint, process identity, exit reason and hashes are
retained. Child timeout, periodic disk/log checks and optional RSS limit stop owned
process groups. Scratch cleanup and final-size checks run on success, failure,
stop and Ctrl-C. Log overflow retains a bounded prefix and reports truncation; trace
events are not filtered. Failed/canceled writers quarantine their namespace, and
non-success evidence is pinned. Investigate before explicitly unpinning/GC; a
quarantined namespace cannot be reused until removed and recreated.

The supervisor keeps the group leader unreaped while signalling its own group,
uses Linux parent-death protection and adopts/reaps same-group descendants. Commands
must remain foreground processes in that group. Escaping sessions/daemonization and
kernel-uninterruptible tasks are not a supported containment boundary. SIGKILL of a
supervisor is a crash, not proof of descendant cleanup; reconciliation records
abandonment conservatively. GPU job isolation needs its own resource-qualified runner.

## Official UI service

```bash
rdnascope --config machine.local.toml service start --run RUN \
  --artifact sha256:PFTRACE_SHA --port 9002 --idle-seconds 300
rdnascope --config machine.local.toml service list
rdnascope --config machine.local.toml service status job:ACTUAL_KEY
rdnascope --config machine.local.toml service stop job:ACTUAL_KEY
```

Select an explicitly registered PFTrace. Forward the returned RPC port in VS Code
and open the returned versioned official UI URL locally. The upstream process owns
HTTP, CORS, protobufs and rendering; no new frontend/proxy/serializer is added.
An occupied port is refused without stopping/adopting its server.

Choose either `--idle-seconds N` or explicit `--keep`. Idle uses upstream
`--idle-start last-query`; default owner-aware idle did not expire in the local
qualification attempt, so it is not used. Upstream scheduling may delay expiry;
the requested idle duration is not an exact wall-clock deadline. `--max-seconds N`
adds a supervisor deadline; `--max-rss-bytes N` adds sampled child-RSS control.
Services and commands reserve 2 MiB of job growth with a 1 MiB combined log limit;
compiler payload growth has the caller's additional reservation.

Status lists the latest 100 jobs/services, their initial input/tool/command, owner
identity and current child/supervisor RSS/PSS from Linux `/proc`. A browser can load
another trace; the initial input binding is not a continuously audited UI model
identity. A successful readiness check is not a rendered-browser or trace-quality
qualification. Existing external services never enter this lifecycle automatically.

Managed lifecycle and worker checks currently require Linux `/proc` and flock.
Contracts and uncached offline queries are the fallback elsewhere; other platforms
have not been qualified. [Validation](validation-r2.md) records the actual scope.
