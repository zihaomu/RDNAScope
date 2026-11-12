"""Thin explicit capture, read, report and official-view CLI."""
import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .contracts import digest, load_config, schema
from .capture import record
from .readers import query
from .reports import write_report
from .view import start as view_start, status as view_status


def parser():
    p = argparse.ArgumentParser(description="RDNAScope: bounded RDNA observation")
    p.add_argument("--version", action="version", version="rdnascope " + __version__)
    p.add_argument("--config", type=Path)
    commands = p.add_subparsers(dest="action", required=True)
    commands.add_parser("doctor")
    q = commands.add_parser("schema")
    q.add_argument("name", choices=("run-manifest", "annotations", "summary"))
    q = commands.add_parser("record")
    q.add_argument("--output", type=Path, required=True)
    q.add_argument("command", nargs=argparse.REMAINDER)
    q = commands.add_parser("query")
    q.add_argument("run", type=Path)
    q.add_argument("--view", choices=("summary", "events", "kernels", "coverage", "provenance"), default="summary")
    q.add_argument("--provider", choices=("auto", "rocpd", "pftrace", "chrome"), default="auto")
    q.add_argument("--limit", type=int, default=100)
    q.add_argument("--offset", type=int, default=0)
    q.add_argument("--no-cache", action="store_true")
    q = commands.add_parser("report")
    q.add_argument("run", type=Path)
    q.add_argument("--provider", choices=("auto", "rocpd", "pftrace", "chrome"), default="auto")
    q = commands.add_parser("view")
    q.add_argument("run", type=Path)
    q.add_argument("--port", type=int, default=9001)
    mode = q.add_mutually_exclusive_group()
    mode.add_argument("--idle-seconds", type=int, default=300)
    mode.add_argument("--keep", action="store_true")
    q = commands.add_parser("view-status")
    q.add_argument("state", type=Path)
    q = commands.add_parser("view-stop")
    q.add_argument("state", type=Path)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config) if args.config else None
        tools = config["tools"] if config else {}
        if args.action == "doctor":
            result = {"version": __version__, "scope": "offline_config_check_no_gpu_probe",
                      "capture_backend": config["capture"]["backend"] if config else None,
                      "tools": {name: {"path": path, "exists": Path(path).is_file(),
                                      "sha256": digest(path) if Path(path).is_file() else None}
                                for name, path in tools.items() if name != "rocpd_command"},
                      "rocpd_command": {"argv": tools["rocpd_command"],
                                        "executable_exists": Path(tools["rocpd_command"][0]).is_file(),
                                        "executable_sha256": digest(tools["rocpd_command"][0]) if Path(tools["rocpd_command"][0]).is_file() else None}
                      if "rocpd_command" in tools else None,
                      "gpu_qualification": "unknown"}
        elif args.action == "schema":
            result = schema(args.name)
        elif args.action == "record":
            if not config:
                raise ValueError("record requires --config")
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            result = record(args.config, args.output, command)
        elif args.action == "query":
            result = query(args.run, args.view, args.provider, args.limit, args.offset,
                           tools.get("trace_processor"), not args.no_cache)
        elif args.action == "report":
            result = write_report(args.run, args.provider, tools.get("trace_processor"))
        elif args.action == "view":
            if not tools.get("trace_processor"):
                raise ValueError("view requires configured official Trace Processor")
            result = view_start(args.run, tools["trace_processor"], args.port,
                                args.idle_seconds, args.keep)
        elif args.action == "view-status":
            result = view_status(args.state)
        else:
            result = view_status(args.state, stop=True)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0 if result.get("status") not in ("failed", "incomplete", "unsupported") else 2
    except KeyboardInterrupt:
        print(json.dumps({"status": "canceled", "message": "Owned command interrupted; inspect run logs"}), file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
