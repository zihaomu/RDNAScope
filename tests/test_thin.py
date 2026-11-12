"""Thin tool contracts: source integrity, time basis, capture failure and ownership."""
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import sys

import pytest

from rdnascope.capture import record
from rdnascope.contracts import artifact, load_config, validate, write_new
from rdnascope.readers import query
from rdnascope.reports import write_report
from rdnascope.view import start as view_start


PHASE = {"status": "not_requested", "argv": [], "exit_code": None,
         "timed_out": False, "tool_sha256": None}


def make_run(tmp_path, source, format="chrome", ranks=None, annotations=None, status="incomplete"):
    root = tmp_path / "run-1"
    root.mkdir()
    shutil.copy2(source, root / source.name)
    items = [artifact(root, root / source.name, format, "input")]
    if annotations is not None:
        write_new(root / "annotations.json", {"schema_version": 1, "run_id": root.name,
                  "scopes": annotations, "source": "caller"})
        items.append(artifact(root, root / "annotations.json", "annotation", "caller_metadata"))
    manifest = {"schema_version": 1, "run_id": root.name, "mode": "diagnostic", "context_id": "fixture",
        "capture": PHASE, "export": PHASE, "artifacts": items,
        "ranks": ranks or [], "clock": {"domain": "unknown", "calibration": "unknown"},
        "coverage": {"writer_completed": None, "record_loss": None, "declared_windows": []},
        "limits": [], "status": status}
    validate("run-manifest", manifest)
    write_new(root / "run-manifest.json", manifest)
    return root


def test_direct_chrome_reader_cache_and_source_tamper(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"traceEvents": [
        {"ph": "X", "ts": 5, "dur": 2, "pid": 41, "cat": "kernel", "name": "k"}]}))
    run = make_run(tmp_path, source, ranks=[{"rank": 0, "pid": 41, "device": "fixture",
                                                   "proof": "inferred"}])
    first = query(run, "events")
    again = query(run, "events")
    assert first["rows"][0]["duration_ns"] == "2000"
    assert first["rows"][0]["association"] == "inferred"
    assert first["cache_hit"] is False and again["cache_hit"] is True
    assert len(list((run / ".rdnascope-cache").glob("*.json"))) == 1
    (run / "input.json").write_text('{"traceEvents": []}')
    with pytest.raises(ValueError, match="Source artifact changed"):
        query(run, "events")


def test_scope_report_preserves_unknown_gpu_time_and_rank_clock(tmp_path):
    source = tmp_path / "input.json"
    source.write_text('{"traceEvents": []}')
    basic = {"kind": "layer", "rank": 0, "clock_domain": "rank0", "start_ns": 100,
             "association": "inferred", "gpu_interval_verified": False, "locator": None}
    scopes = [dict(basic, name="layer0", time_basis="cpu_submission", duration_ns=200),
              dict(basic, name="layer0", time_basis="cpu_submission", start_ns=400, duration_ns=400),
              dict(basic, name="layer1", time_basis="gpu_stream", duration_ns=900)]
    run = make_run(tmp_path, source, annotations=scopes,
        ranks=[{"rank": 0, "pid": 41, "device": "fixture", "proof": "inferred"}])
    result = write_report(run)
    assert result["coverage"]["cross_rank_clock"] == "unknown"
    layer = next(item for item in result["groups"] if item["scope"] == "layer0")
    assert layer["median_ns"] == 300 and layer["samples"] == 2
    gpu = next(item for item in result["groups"] if item["scope"] == "layer1")
    assert gpu["time_basis"] == "gpu_unknown" and gpu["median_ns"] is None
    assert write_report(run) == result
    assert "Median ns" in (run / "summary.md").read_text()
    (run / "annotations.json").write_text("{}")
    with pytest.raises(ValueError, match="Source artifact changed"):
        write_report(run)


def test_rocpd_integer_intervals_and_active_wal_refused(tmp_path):
    db = tmp_path / "sample.db"
    with sqlite3.connect(db) as connection:
        connection.executescript("""
          CREATE TABLE rocpd_kernel_dispatch_0(id INTEGER,pid INTEGER,kernel_id INTEGER,
              start INTEGER,end INTEGER,queue_id INTEGER,stream_id INTEGER,
              graph_exec_id INTEGER,graph_node_id INTEGER,agent_id INTEGER,dispatch_id INTEGER,
              event_id INTEGER,tid INTEGER);
          CREATE TABLE rocpd_info_process_0(id INTEGER,pid INTEGER);
          CREATE TABLE rocpd_info_kernel_symbol_0(id INTEGER,display_name TEXT,kernel_name TEXT);
          CREATE TABLE rocpd_event_0(id INTEGER,correlation_id INTEGER);
          INSERT INTO rocpd_info_process_0 VALUES(1,41);
          INSERT INTO rocpd_info_kernel_symbol_0 VALUES(1,'add','add');
          INSERT INTO rocpd_event_0 VALUES(1,7);
          INSERT INTO rocpd_kernel_dispatch_0 VALUES(1,1,1,100,125,2,3,4,5,6,7,1,8);
        """)
    run = make_run(tmp_path, db, "rocpd", ranks=[{"rank": 0, "pid": 41,
                                            "device": "fixture", "proof": "exact"}])
    row = query(run, "kernels")["rows"][0]
    assert row["duration_ns"] == "25" and row["rank"] == 0 and row["association"] == "inferred"
    assert row["rank_metadata_proof"] == "exact"
    assert row["event_id"].endswith("rocpd_kernel_dispatch_0/id=1")
    (run / "sample.db-wal").write_bytes(b"active")
    with pytest.raises(ValueError, match="WAL"):
        query(run, "kernels")


def _config(tmp_path, profiler, converter, limit=1048576, timeout=3):
    path = tmp_path / "config.toml"
    path.write_text(f'''schema_version = 1
[tools]
rocprofv3 = "{profiler}"
rocpd_command = ["{sys.executable}", "{converter}"]
[capture]
backend = "rocm_native"
profile = "native_roi"
timeout_seconds = {timeout}
max_output_bytes = {limit}
[context]
id = "fixture"
''')
    return path


def test_capture_bounds_failed_producer_and_preserves_logs(tmp_path):
    profiler = tmp_path / "profiler"
    profiler.write_text("#!" + sys.executable + "\nimport time\ntime.sleep(3)\n")
    profiler.chmod(0o700)
    converter = tmp_path / "convert.py"
    converter.write_text("pass\n")
    config = _config(tmp_path, profiler, converter, timeout=1)
    manifest = record(config, tmp_path / "timeout-run", [sys.executable, "-c", "pass"])
    assert manifest["status"] == "failed" and manifest["capture"]["timed_out"]
    assert (tmp_path / "timeout-run/run-manifest.json").exists()
    assert (tmp_path / "timeout-run/capture.stderr.log").exists()
    with pytest.raises(FileExistsError):
        record(config, tmp_path / "timeout-run", ["true"])


def test_capture_fake_official_protocol_keeps_native_and_caller_metadata(tmp_path):
    profiler = tmp_path / "profiler"
    profiler.write_text("#!" + sys.executable + "\n" + '''import json,os,sqlite3,sys
from pathlib import Path
args=sys.argv[1:];root=Path(args[args.index('--output-directory')+1]);root.mkdir()
with sqlite3.connect(root/'capture.db') as db:
 db.execute('CREATE TABLE rocpd_kernel_dispatch_0(id INTEGER,pid INTEGER,kernel_id INTEGER,start INTEGER,end INTEGER)')
 db.execute('CREATE TABLE rocpd_info_process_0(id INTEGER,pid INTEGER)')
 db.execute('CREATE TABLE rocpd_info_kernel_symbol_0(id INTEGER,display_name TEXT,kernel_name TEXT)')
 db.execute('INSERT INTO rocpd_info_process_0 VALUES(1,41)')
 db.execute("INSERT INTO rocpd_info_kernel_symbol_0 VALUES(1,'fixture','fixture')")
 db.execute('INSERT INTO rocpd_kernel_dispatch_0 VALUES(1,1,1,100,125)')
out=Path(os.environ['RDNASCOPE_RUN_DIR'])
(out/'rank-map.json').write_text(json.dumps([{'rank':0,'pid':41,'device':'fixture','proof':'inferred'}]))
(out/'numeric.json').write_text(json.dumps({'passed':True}))
''')
    profiler.chmod(0o700)
    converter = tmp_path / "converter.py"
    converter.write_text('''import sys
from pathlib import Path
args=sys.argv[1:];folder=Path(args[args.index('-d')+1]);(folder/'trace_results.pftrace').write_bytes(b'fake-fixture-only')
''')
    config = _config(tmp_path, profiler, converter)
    run = tmp_path / "good-run"
    manifest = record(config, run, [sys.executable, "-c", "pass"])
    assert manifest["status"] == "complete"
    assert manifest["capture"]["argv"][1:4] == ["--hip-trace", "--marker-trace", "--kernel-trace"]
    assert manifest["export"]["status"] == "complete"
    assert manifest["capture"]["elapsed_seconds"] is not None
    assert any(x["path"] == "numeric.json" and x["role"] == "caller_output" for x in manifest["artifacts"])
    formats = [item["format"] for item in manifest["artifacts"]]
    assert formats.count("rocpd") == 1 and formats.count("pftrace") == 1
    assert query(run, "kernels", "rocpd")["rows"][0]["duration_ns"] == "25"
    assert query(run, "coverage", "rocpd")["rows"][0]["writer_completed"] is None


def test_config_unknown_field_and_view_occupied_port(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('schema_version=1\n[tools]\ntrace_processor="/tmp/tool"\n[capture]\nbackend="rocm_native"\nprofile="scope"\ntimeout_seconds=1\nmax_output_bytes=10\n[context]\nid="x"\nextra="bad"\n')
    with pytest.raises(ValueError, match="Invalid context"):
        load_config(config)
    trace = tmp_path / "fake.pftrace"
    trace.write_bytes(b"fixture")
    run = make_run(tmp_path, trace, "pftrace")
    fake_tool = tmp_path / "trace_processor"
    fake_tool.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "Perfetto v59.1-fixture"; else echo "--idle-timeout --idle-start"; fi\n')
    fake_tool.chmod(0o700)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        with pytest.raises(OSError):
            view_start(run, fake_tool, busy.getsockname()[1], 1)
