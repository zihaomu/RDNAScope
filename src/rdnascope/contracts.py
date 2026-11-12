"""Small, portable contracts for explicit consumer-owned runs."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import tomllib

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
STATES = {"complete", "incomplete", "failed", "unsupported", "not_requested"}
FORMATS = {"rocpd", "pftrace", "chrome", "log", "annotation"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def load_json(path, max_bytes=8 * 1024 * 1024):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError("JSON input exceeds byte budget")
    def bad_constant(value):
        raise ValueError("Non-finite JSON number: " + value)
    return json.loads(path.read_text(), parse_constant=bad_constant)


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value) + "\n"
    with path.open("x") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def replace_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=".rdnascope-", delete=False) as stream:
            name = stream.name
            stream.write(canonical(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def schema(name):
    if name not in {"run-manifest", "annotations", "summary"}:
        raise ValueError("Unknown thin contract")
    from importlib.resources import files
    return json.loads(files("rdnascope").joinpath("schemas", "thin-v1", name + ".json").read_text())


def _check(spec, value, path="/"):
    """Validate the deliberately small JSON Schema subset shipped in thin-v1."""
    known = {"$schema", "title", "type", "const", "enum", "required", "properties",
             "additionalProperties", "items", "minimum", "minLength", "pattern", "anyOf"}
    unknown = set(spec) - known
    if unknown:
        raise ValueError("Unsupported contract keyword: " + ",".join(sorted(unknown)))
    if "anyOf" in spec:
        for option in spec["anyOf"]:
            try:
                _check(option, value, path)
                break
            except ValueError:
                pass
        else:
            raise ValueError(path + " does not satisfy any allowed type")
    types = spec.get("type")
    types = [types] if isinstance(types, str) else types
    if types:
        valid = {"object": lambda x: isinstance(x, dict),
                 "array": lambda x: isinstance(x, list),
                 "string": lambda x: isinstance(x, str),
                 "integer": lambda x: type(x) is int,
                 "number": lambda x: type(x) in (int, float) and math.isfinite(x),
                 "boolean": lambda x: type(x) is bool,
                 "null": lambda x: x is None}
        if any(kind not in valid for kind in types):
            raise ValueError("Unsupported contract type")
        if not any(valid[kind](value) for kind in types):
            raise ValueError(path + " has wrong type")
    if "const" in spec and (type(value) is not type(spec["const"]) or value != spec["const"]):
        raise ValueError(path + " differs from required constant")
    if "enum" in spec and not any(type(value) is type(item) and value == item for item in spec["enum"]):
        raise ValueError(path + " is outside allowed enum")
    if isinstance(value, dict):
        missing = set(spec.get("required", ())) - set(value)
        if missing:
            raise ValueError(path + " missing " + ",".join(sorted(missing)))
        properties = spec.get("properties", {})
        if spec.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError(path + " has unknown fields: " + ",".join(sorted(set(value) - set(properties))))
        for key, item in value.items():
            if key in properties:
                _check(properties[key], item, path.rstrip("/") + "/" + key)
    if isinstance(value, list) and "items" in spec:
        for index, item in enumerate(value):
            _check(spec["items"], item, path.rstrip("/") + "/" + str(index))
    if "minimum" in spec and type(value) in (int, float) and value < spec["minimum"]:
        raise ValueError(path + " is below minimum")
    if "minLength" in spec and isinstance(value, str) and len(value) < spec["minLength"]:
        raise ValueError(path + " is too short")
    if "pattern" in spec and isinstance(value, str) and not re.fullmatch(spec["pattern"], value):
        raise ValueError(path + " does not match pattern")


def validate(name, value):
    _check(schema(name), value)
    canonical(value)
    if name == "run-manifest":
        ranks = value["ranks"]
        if len({item["rank"] for item in ranks}) != len(ranks):
            raise ValueError("Duplicate rank metadata")
        pids = [item["pid"] for item in ranks if item["pid"] is not None]
        if len(set(pids)) != len(pids):
            raise ValueError("Duplicate PID metadata")
        paths = [item["path"] for item in value["artifacts"]]
        if len(set(paths)) != len(paths):
            raise ValueError("Duplicate artifact path")
        if value["status"] == "complete" and (value["capture"]["status"], value["export"]["status"]) != ("complete", "complete"):
            raise ValueError("Complete run needs complete capture and export")
        for window in value["coverage"]["declared_windows"]:
            if window["begin_ns"] >= window["end_ns"]:
                raise ValueError("Declared window bounds are unordered")
    elif name == "annotations":
        for scope in value["scopes"]:
            if scope["gpu_interval_verified"] and scope["time_basis"] in ("gpu_stream", "native_kernel") and not scope["locator"]:
                raise ValueError("Claimed verified GPU interval needs a source locator")
    return value


def load_config(path):
    source = Path(path).expanduser().resolve(strict=True)
    with source.open("rb") as stream:
        value = tomllib.load(stream)
    if set(value) != {"schema_version", "tools", "capture", "context"} or value["schema_version"] != 1:
        raise ValueError("Config requires only schema_version=1, tools, capture and context")
    tools = value["tools"]
    if not isinstance(tools, dict) or set(tools) - {"rocprofv3", "rocpd_command", "trace_processor"}:
        raise ValueError("Unknown tools field")
    for key in ("rocprofv3", "trace_processor"):
        if key in tools:
            if not isinstance(tools[key], str) or not tools[key]:
                raise ValueError("Invalid tool path")
            tools[key] = str((source.parent / tools[key]).resolve())
    if "rocpd_command" in tools:
        if not isinstance(tools["rocpd_command"], list) or not tools["rocpd_command"] or not all(isinstance(x, str) and x for x in tools["rocpd_command"]):
            raise ValueError("rocpd_command must be a nonempty argv array")
        tools["rocpd_command"][0] = str((source.parent / tools["rocpd_command"][0]).resolve())
    capture = value["capture"]
    if not isinstance(capture, dict) or set(capture) != {"backend", "profile", "timeout_seconds", "max_output_bytes"}:
        raise ValueError("Capture fields must be explicit and minimal")
    if capture["backend"] != "rocm_native" or capture["profile"] not in ("scope", "native_roi"):
        raise ValueError("Unsupported capture backend/profile")
    for key in ("timeout_seconds", "max_output_bytes"):
        if type(capture[key]) is not int or capture[key] <= 0:
            raise ValueError(key + " must be positive")
    context = value["context"]
    if not isinstance(context, dict) or set(context) - {"id", "annotations"} or not isinstance(context.get("id"), str) or not ID.fullmatch(context["id"]):
        raise ValueError("Invalid context")
    if "annotations" in context:
        if not isinstance(context["annotations"], str) or not context["annotations"]:
            raise ValueError("Invalid annotations path")
        context["annotations"] = str((source.parent / context["annotations"]).resolve())
    return value


def run_dir(path):
    source = Path(path).expanduser()
    if source.is_symlink():
        raise ValueError("Run must be an existing real directory")
    path = source.resolve(strict=True)
    if not path.is_dir():
        raise ValueError("Run must be an existing real directory")
    return path


def output_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("Artifact path must be relative to run")
    source = root / path
    if source.is_symlink():
        raise ValueError("Artifact must not be a symlink")
    resolved = source.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Artifact escapes run or is not a regular file")
    return resolved


def verify_run(path):
    root = run_dir(path)
    manifest = validate("run-manifest", load_json(root / "run-manifest.json"))
    if manifest["run_id"] != root.name:
        raise ValueError("Run ID differs from directory name")
    for item in manifest["artifacts"]:
        source = output_path(root, item["path"])
        if source.stat().st_size != item["bytes"] or digest(source) != item["sha256"]:
            raise ValueError("Source artifact changed: " + item["path"])
        if item["format"] == "rocpd":
            for suffix in ("-wal", "-journal"):
                side = Path(str(source) + suffix)
                if side.exists() and side.stat().st_size:
                    raise ValueError("Active SQLite WAL/journal: " + str(side))
    return root, manifest


def artifact(root, path, format, role, derived_from=None):
    path = Path(path).resolve(strict=True)
    root = Path(root).resolve(strict=True)
    if not path.is_relative_to(root) or format not in FORMATS:
        raise ValueError("Unsupported artifact or path")
    return {"path": str(path.relative_to(root)), "format": format, "role": role,
            "sha256": digest(path), "bytes": path.stat().st_size,
            "derived_from": derived_from}
