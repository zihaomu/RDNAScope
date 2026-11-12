"""Bounded wrapper around official ROCm collection and export commands."""
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import time

from .contracts import ID, artifact, digest, load_config, load_json, validate, write_new
from .storage import sqlite_readonly


def _bytes(root):
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Producer created a symlink in the run directory")
        if path.is_file():
            total += path.stat().st_size
    return total


def _run(argv, cwd, stdout, stderr, timeout, max_bytes, root, env=None):
    start = time.monotonic()
    with stdout.open("x") as out, stderr.open("x") as err:
        process = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err,
                                   env=env, start_new_session=True)
        reason = None
        try:
            while process.poll() is None:
                if time.monotonic() - start > timeout:
                    reason = "timeout"
                    break
                if _bytes(root) > max_bytes:
                    reason = "output_budget"
                    break
                time.sleep(.05)
        except BaseException:
            reason = "interrupted"
            raise
        finally:
            if reason and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)
        code = process.wait()
    if not reason and _bytes(root) > max_bytes:
        reason = "output_budget_after_exit"
    return {"exit_code": code, "reason": reason, "elapsed_seconds": round(time.monotonic() - start, 6)}


def _phase(status="not_requested", argv=None, exit_code=None, timed_out=False, tool_sha256=None, elapsed_seconds=None):
    return {"status": status, "argv": argv or [], "exit_code": exit_code,
            "timed_out": timed_out, "tool_sha256": tool_sha256,
            "elapsed_seconds": elapsed_seconds}


def record(config_path, output, command):
    config = load_config(config_path)
    if not command or command[0] == "--" or not all(isinstance(x, str) and x for x in command):
        raise ValueError("Pass a nonempty application argv after --")
    root = Path(output).expanduser().absolute()
    if not ID.fullmatch(root.name):
        raise ValueError("Output directory name must be a valid run ID")
    root.mkdir(parents=True, exist_ok=False)
    cap = config["capture"]
    tools = config["tools"]
    manifest = {"schema_version": 1, "run_id": root.name, "mode": "diagnostic",
                "context_id": config["context"]["id"], "capture": _phase(), "export": _phase(),
                "artifacts": [], "ranks": [], "clock": {"domain": "unknown", "calibration": "unknown"},
                "coverage": {"writer_completed": None, "record_loss": None, "declared_windows": []},
                "limits": ["Output budget is polled, not a filesystem hard quota",
                           "Process exit does not independently prove loss-free collection or model correctness"]}
    capture_stdout = root / "capture.stdout.log"
    capture_stderr = root / "capture.stderr.log"
    export_stdout = root / "export.stdout.log"
    export_stderr = root / "export.stderr.log"
    try:
        supplied_annotations = config["context"].get("annotations")
        if supplied_annotations:
            document = load_json(supplied_annotations)
            validate("annotations", document)
            if document["run_id"] != root.name:
                raise ValueError("Configured annotations use another run ID")
            shutil.copyfile(supplied_annotations, root / "annotations.json")
        profiler = tools.get("rocprofv3")
        if not profiler or not Path(profiler).is_file() or not os.access(profiler, os.X_OK):
            manifest["capture"] = _phase("unsupported")
            manifest["limits"].append("Configured rocprofv3 is unavailable")
            return _finish(root, manifest, capture_stdout, capture_stderr, export_stdout, export_stderr)
        native_dir = root / "native"
        flags = ["--hip-trace", "--marker-trace"]
        if cap["profile"] == "native_roi":
            flags.append("--kernel-trace")
        argv = [profiler, *flags, "--output-format", "rocpd", "--output-directory", str(native_dir), "--", *command]
        manifest["capture"] = _phase("incomplete", argv, tool_sha256=digest(profiler))
        env = dict(os.environ, RDNASCOPE_RUN_DIR=str(root), RDNASCOPE_CONTEXT_ID=manifest["context_id"])
        outcome = _run(argv, Path.cwd(), capture_stdout, capture_stderr, cap["timeout_seconds"], cap["max_output_bytes"], root, env)
        manifest["capture"].update(exit_code=outcome["exit_code"], timed_out=outcome["reason"] == "timeout",
                                   elapsed_seconds=outcome["elapsed_seconds"])
        if outcome["reason"] or outcome["exit_code"]:
            manifest["capture"]["status"] = "failed"
            manifest["limits"].append("Capture failed: " + str(outcome["reason"] or outcome["exit_code"]))
        dbs = sorted(native_dir.rglob("*.db")) if native_dir.exists() else []
        for db in dbs:
            if db.is_symlink() or any(Path(str(db) + suffix).exists() and Path(str(db) + suffix).stat().st_size
                                      for suffix in ("-wal", "-journal")):
                manifest["capture"]["status"] = "failed"
                manifest["limits"].append("Unsealed native database")
                continue
            try:
                with sqlite_readonly(db) as connection:
                    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite quick_check failed")
                manifest["artifacts"].append(artifact(root, db, "rocpd", "native", None))
            except (sqlite3.Error, ValueError) as exc:
                manifest["capture"]["status"] = "failed"
                manifest["limits"].append("Native DB invalid: " + str(exc))
        if not dbs:
            manifest["capture"]["status"] = "failed"
            manifest["limits"].append("No rocpd DB produced")
        elif manifest["capture"]["status"] != "failed":
            manifest["capture"]["status"] = "complete"
        converter = tools.get("rocpd_command")
        if manifest["capture"]["status"] == "complete" and converter:
            export_dir = root / "export"
            export_dir.mkdir()
            export_argv = [*converter, "convert", "-i", *map(str, dbs), "--output-format", "pftrace",
                           "--group-by-queue", "-d", str(export_dir), "-o", "trace"]
            executable = Path(converter[0])
            if not executable.is_file() or not os.access(executable, os.X_OK):
                manifest["export"] = _phase("unsupported", export_argv)
            else:
                manifest["export"] = _phase("incomplete", export_argv, tool_sha256=digest(executable))
                outcome = _run(export_argv, Path.cwd(), export_stdout, export_stderr,
                               cap["timeout_seconds"], cap["max_output_bytes"], root)
                manifest["export"].update(exit_code=outcome["exit_code"], timed_out=outcome["reason"] == "timeout",
                                          elapsed_seconds=outcome["elapsed_seconds"])
                traces = sorted(export_dir.glob("*.pftrace"))
                for trace in traces:
                    manifest["artifacts"].append(artifact(root, trace, "pftrace", "official_export",
                                                          manifest["artifacts"][0]["sha256"] if len(dbs) == 1 else None))
                if not outcome["reason"] and outcome["exit_code"] == 0 and len(traces) == 1:
                    manifest["export"]["status"] = "complete"
                else:
                    manifest["export"]["status"] = "failed"
                    manifest["limits"].append("Official export failed or produced unexpected trace count")
        elif manifest["capture"]["status"] == "complete":
            manifest["export"] = _phase("unsupported")
            manifest["limits"].append("No official rocpd converter configured")
        return _finish(root, manifest, capture_stdout, capture_stderr, export_stdout, export_stderr)
    except BaseException as exc:
        manifest["capture"]["status"] = "failed" if manifest["capture"]["status"] == "incomplete" else manifest["capture"]["status"]
        manifest["limits"].append("Record interrupted/error: " + type(exc).__name__ + ": " + str(exc))
        _finish(root, manifest, capture_stdout, capture_stderr, export_stdout, export_stderr)
        raise


def _finish(root, manifest, capture_stdout, capture_stderr, export_stdout, export_stderr):
    for path in (capture_stdout, capture_stderr, export_stdout, export_stderr):
        if path.exists() and path.is_file() and not path.is_symlink():
            manifest["artifacts"].append(artifact(root, path, "log", "tool_log", None))
    annotations = root / "annotations.json"
    if annotations.is_file():
        manifest["artifacts"].append(artifact(root, annotations, "annotation", "caller_metadata", None))
    ranks = root / "rank-map.json"
    if ranks.is_file():
        try:
            data = load_json(ranks)
            if not isinstance(data, list) or any(not isinstance(item, dict) or set(item) != {"rank", "pid", "device", "proof"} for item in data):
                raise ValueError("Invalid consumer rank-map.json")
            if any(type(item["rank"]) is not int or item["rank"] < 0 or
                   item["pid"] is not None and (type(item["pid"]) is not int or item["pid"] < 0) or
                   item["device"] is not None and not isinstance(item["device"], str) or
                   item["proof"] not in ("exact", "inferred", "unmapped") for item in data):
                raise ValueError("Invalid rank proof or identity")
            if len({x["rank"] for x in data}) != len(data):
                raise ValueError("Duplicate ranks")
            manifest["ranks"] = data
        except (ValueError, OSError, TypeError) as exc:
            manifest["limits"].append("Rank map unavailable: " + str(exc))
        manifest["artifacts"].append(artifact(root, ranks, "log", "caller_metadata", None))
    declared = root / "scope-windows.json"
    if declared.is_file():
        try:
            data = load_json(declared)
            if not isinstance(data, list):
                raise ValueError("Expected a window array")
            test = dict(manifest)
            test["status"] = "incomplete"
            test["coverage"] = dict(manifest["coverage"], declared_windows=data)
            validate("run-manifest", test)
            manifest["coverage"]["declared_windows"] = data
        except (ValueError, OSError, TypeError) as exc:
            manifest["limits"].append("Declared windows unavailable: " + str(exc))
        manifest["artifacts"].append(artifact(root, declared, "log", "caller_metadata", None))
    known = {item["path"] for item in manifest["artifacts"]}
    native = root / "native"
    if native.exists():
        for path in native.rglob("*"):
            if path.is_file() and not path.is_symlink() and str(path.relative_to(root)) not in known:
                manifest["artifacts"].append(artifact(root, path, "log", "partial_native", None))
    known = {item["path"] for item in manifest["artifacts"]}
    for path in root.iterdir():
        if path.is_file() and not path.is_symlink() and path.name != "run-manifest.json" and path.name not in known:
            manifest["artifacts"].append(artifact(root, path, "log", "caller_output", None))
    manifest["status"] = ("complete" if manifest["capture"]["status"] == manifest["export"]["status"] == "complete"
                          else "unsupported" if manifest["capture"]["status"] == "unsupported"
                          else "failed" if "failed" in (manifest["capture"]["status"], manifest["export"]["status"])
                          else "incomplete")
    validate("run-manifest", manifest)
    write_new(root / "run-manifest.json", manifest)
    return manifest
