"""Read sealed official inputs from an explicit run directory."""
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from . import __version__, providers
from .contracts import canonical, digest, load_json, output_path, verify_run, write_new
from .storage import sqlite_readonly


VIEWS = {"summary", "events", "kernels", "coverage", "provenance"}


def _identity(manifest):
    return {"ranks": [{"rank": item["rank"], "process_id": item["pid"]} for item in manifest["ranks"]],
            "clock": manifest["clock"], "semantics": {"time_unit": "us", "native_rank": None}}


def _select(manifest, provider):
    counts = {name: sum(item["format"] == name for item in manifest["artifacts"])
              for name in ("rocpd", "pftrace", "chrome")}
    if provider == "auto":
        provider = next((name for name in ("rocpd", "pftrace", "chrome") if counts[name] == 1), None)
    if provider not in counts or counts[provider] == 0:
        raise ValueError("Selected native provider is unavailable")
    chosen = [item for item in manifest["artifacts"] if item["format"] == provider]
    if len(chosen) != 1:
        raise ValueError("Select one native input; multiple rank DBs require an explicit merged export or future qualified reader")
    return provider, chosen


def query(run, view="summary", provider="auto", limit=100, offset=0, trace_processor=None, cache=True):
    if view not in VIEWS or type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or offset < 0:
        raise ValueError("Invalid view or page")
    root, manifest = verify_run(run)
    try:
        selected_provider, chosen = _select(manifest, provider)
    except ValueError:
        if view not in ("coverage", "provenance"):
            raise
        selected_provider, chosen = "none", []
    tool = str(Path(trace_processor).resolve()) if trace_processor else None
    settings = SimpleNamespace(trace_processor=tool, timeout_seconds=60, max_json_bytes=8 * 1024 * 1024)
    info = ({"name": selected_provider, "contract_version": 1}
            if view in ("coverage", "provenance") else providers.provider_info(selected_provider, settings))
    implementation = {"version": __version__, "reader_sha256": digest(Path(providers.__file__)),
                      "contract_sha256": digest(Path(__file__).with_name("contracts.py"))}
    key = __import__("hashlib").sha256(canonical({"inputs": [(x["sha256"], x["format"]) for x in chosen],
        "ranks": manifest["ranks"], "clock": manifest["clock"], "view": view,
        "provider": info, "implementation": implementation, "limit": limit, "offset": offset}).encode()).hexdigest()
    cache_dir = root / ".rdnascope-cache"
    cache_file = cache_dir / (key + ".json")
    if cache and cache_file.exists():
        if cache_file.is_symlink():
            raise ValueError("Query cache must not be a symlink")
        saved = load_json(cache_file, 8 * 1024 * 1024)
        if saved.get("key") != key or saved.get("payload_sha256") != __import__("hashlib").sha256(canonical(saved.get("payload")).encode()).hexdigest():
            raise ValueError("Query cache integrity failed")
        return dict(saved["payload"], cache_hit=True)
    item = chosen[0] if chosen else None
    source = output_path(root, item["path"]) if item else None
    a = {"artifact_id": "sha256:" + item["sha256"], "format": item["format"], "uri": source.as_uri()} if item else None
    identity = _identity(manifest)
    if view == "coverage":
        rows = [{"writer_completed": manifest["coverage"]["writer_completed"],
                 "record_loss": manifest["coverage"]["record_loss"],
                 "declared_windows": manifest["coverage"]["declared_windows"],
                 "rank_mapping": manifest["ranks"], "cross_rank_clock": manifest["clock"]["calibration"]}]
    elif view == "provenance":
        rows = [{"path": x["path"], "format": x["format"], "sha256": x["sha256"],
                 "bytes": x["bytes"], "tool": info, "implementation": implementation}
                for x in (chosen or manifest["artifacts"])]
    elif selected_provider == "rocpd":
        with sqlite_readonly(source) as connection:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("rocpd SQLite integrity check failed")
        rows = providers.rocpd([a], identity, view, settings, limit, offset)
    elif selected_provider == "pftrace":
        rows = providers.perfetto([a], identity, view, settings, limit, offset)
    else:
        rows = providers.json_query([a], identity, "chrome", view, settings, limit, offset)
    rank_proof = {item["rank"]: item["proof"] for item in manifest["ranks"]}
    for row in rows:
        if "rank" in row:
            row["rank_metadata_proof"] = rank_proof.get(row["rank"], "unmapped")
            row["association"] = "inferred" if row["rank"] in rank_proof and rank_proof[row["rank"]] != "unmapped" else "unmapped"
    payload = {"schema_version": 1, "run_id": manifest["run_id"], "view": view,
               "provider": info, "rows": rows[:limit], "page": {"limit": limit, "offset": offset, "has_more": len(rows) > limit},
               "source": {"path": item["path"], "sha256": item["sha256"]} if item else None,
               "limits": ["Observed intervals are not a reconstructed critical path",
                          "Unknown rank clock calibration prevents exact cross-rank wait inference"]}
    if cache:
        encoded = canonical(payload).encode()
        if len(encoded) < 128 * 1024 and (not cache_dir.exists() or len(list(cache_dir.glob("*.json"))) < 64):
            cache_dir.mkdir(exist_ok=True)
            saved = {"key": key, "payload_sha256": __import__("hashlib").sha256(encoded).hexdigest(), "payload": payload}
            try:
                write_new(cache_file, saved)
            except FileExistsError:
                pass
    return dict(payload, cache_hit=False)
