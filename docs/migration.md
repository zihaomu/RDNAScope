# Prototype migration boundary

The original TraceLens/Perfetto workspace stays in place. Its FreeToken sources, original traces, case hashes, compiled caches, accepted model baseline and requested UI services are not moved or rewritten. The RDNAScope checkout contains selected new source and small synthetic examples only.

The old analysis CLI continues to work in its original environment. RDNAScope's `tlp` executable is an **explicit bridge**:

```toml
[legacy]
executable = "/actual/path/to/the/original/.venv/bin/tlp"
```

```bash
tlp --config /path/to/machine.local.toml <original command and arguments>
```

The bridge forwards arguments, CWD, stdout/stderr and exit status; it never treats old `import` as new `register`. Without an explicit executable it explains configuration rather than guessing a workspace. Recursive delegation is refused.

Normalized legacy datasets may also be registered directly by directory. The new reader verifies the registered manifest/events and the old normalized SHA, preserves macro/evidence categories and dispatch-local clocks. This does **not** retroactively verify all old external source bindings or upgrade old performance/clock qualification. Direct raw macro collection and model optimization remain in the original tool pending later adapters.

This checkout does not copy old model/artifact directories into Git. Locally configured original `.pftrace`/`.db`/HTTP inputs can be inspected without copying them. Published fixtures must be selected explicitly; only the repository's synthetic examples are currently included.
