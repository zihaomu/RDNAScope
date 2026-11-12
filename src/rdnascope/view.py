"""Own only the official local Trace Processor RPC process."""
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
from urllib.request import urlopen

from .contracts import digest, verify_run, output_path, write_new


def _identity(pid):
    stat = Path(f"/proc/{pid}/stat").read_text()
    return {"pid": pid, "start_ticks": stat.rsplit(") ", 1)[1].split()[19],
            "uid": Path(f"/proc/{pid}").stat().st_uid,
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def _same(identity):
    try:
        return _identity(identity["pid"]) == identity and identity["uid"] == os.getuid()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return False


def _kill(process):
    if process.poll() is None:
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


def start(run, trace_processor, port, idle_seconds=300, keep=False):
    root, manifest = verify_run(run)
    traces = [item for item in manifest["artifacts"] if item["format"] == "pftrace"]
    if len(traces) != 1:
        raise ValueError("View requires exactly one official PFTrace input")
    if type(port) is not int or not 1024 <= port <= 65535 or not keep and (type(idle_seconds) is not int or idle_seconds <= 0):
        raise ValueError("Invalid localhost port or idle timeout")
    binary = Path(trace_processor).resolve(strict=True)
    if not os.access(binary, os.X_OK):
        raise ValueError("Trace Processor is not executable")
    version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=10, check=True).stdout
    match = re.search(r"Perfetto (v[0-9][A-Za-z0-9._-]*)", version)
    if not match:
        raise ValueError("Unknown official UI build")
    help_text = subprocess.run([str(binary), "server", "http", "--help"], capture_output=True, text=True, timeout=10, check=True).stdout
    if "--idle-timeout" not in help_text or "--idle-start" not in help_text:
        raise ValueError("Official server lacks qualified idle controls")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    trace = output_path(root, traces[0]["path"])
    ui_dir = root / "ui" / (str(int(time.time() * 1000)) + "-" + str(port))
    ui_dir.mkdir(parents=True, exist_ok=False)
    argv = [str(binary), "server", "http", "--ip-address", "127.0.0.1", "--port", str(port)]
    if not keep:
        argv += ["--idle-start", "last-query"]
    argv += ["--idle-timeout", "never" if keep else str(idle_seconds) + "s", str(trace)]
    base = "https://ui.perfetto.dev/" + match[1] + "/"
    url = base + ("#!/?rpc_port=" + str(port) if port != 9001 else "")
    state = {"status": "starting", "run_id": manifest["run_id"], "trace": traces[0],
             "tool_sha256": digest(binary), "tool_version": version.strip(), "argv": argv,
             "port": port, "bind_address": "127.0.0.1", "official_ui": url,
             "flags_url": base + "#!/flags/cspAllowAnyWebsocketPort" if port != 9001 else None,
             "forwarding": "Forward the RPC port in VS Code and open official_ui locally; verify RPC sidebar port",
             "idle_seconds": None if keep else idle_seconds, "keep": keep,
             "browser_rendered": "not_tested"}
    with (ui_dir / "stdout.log").open("x") as out, (ui_dir / "stderr.log").open("x") as err:
        process = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
    state["process"] = _identity(process.pid)
    deadline = time.monotonic() + 15
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError("Official server exited before readiness")
            try:
                with urlopen(f"http://127.0.0.1:{port}/status", timeout=.25) as response:
                    if response.status == 200:
                        state["status"] = "ready"
                        break
            except OSError:
                pass
            time.sleep(.05)
        else:
            raise TimeoutError("Official RPC startup exceeded 15 seconds")
    except BaseException as exc:
        _kill(process)
        state["status"] = "failed"
        state["error"] = str(exc)
        write_new(ui_dir / "service.json", state)
        raise
    write_new(ui_dir / "service.json", state)
    state["state_path"] = str(ui_dir / "service.json")
    return state


def status(state_path, stop=False):
    path = Path(state_path).resolve(strict=True)
    state = json.loads(path.read_text())
    identity = state.get("process")
    alive = isinstance(identity, dict) and _same(identity)
    if stop and alive:
        command = Path(f"/proc/{identity['pid']}/cmdline").read_bytes().split(b"\0")
        expected = [x.encode() for x in state["argv"]]
        if command[:len(expected)] != expected:
            raise ValueError("Owned service argv changed; refusing stop")
        os.killpg(identity["pid"], signal.SIGTERM)
    return {"state_path": str(path), "recorded_status": state["status"],
            "owned_process_alive": alive, "stop_requested": bool(stop and alive),
            "official_ui": state["official_ui"]}
