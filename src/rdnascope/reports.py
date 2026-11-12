"""Small deterministic human/agent summary from the same verified run."""
from collections import defaultdict
from pathlib import Path
from statistics import median

from .contracts import digest, load_json, output_path, validate, verify_run, write_new, canonical
from .readers import query


def _annotations(root, manifest):
    items = [item for item in manifest["artifacts"] if item["format"] == "annotation"]
    if not items:
        if (root / "annotations.json").exists():
            raise ValueError("Unregistered annotations.json must not affect a run")
        return []
    if len(items) != 1:
        raise ValueError("Exactly one annotation input is supported")
    document = validate("annotations", load_json(output_path(root, items[0]["path"])))
    if document["run_id"] != manifest["run_id"]:
        raise ValueError("Annotation run ID mismatch")
    return document["scopes"]


def build(run, provider="auto", trace_processor=None, max_groups=64):
    root, manifest = verify_run(run)
    scopes = _annotations(root, manifest)
    rank_ids = {item["rank"] for item in manifest["ranks"]}
    windows = manifest["coverage"]["declared_windows"]
    grouped = defaultdict(list)
    limitations = ["Scope interval sums are not model wall time or a critical path",
                   "No cross-rank arrival or pure wait is inferred without clock calibration",
                   "Diagnostic collection does not qualify trace-off model performance"]
    for scope in scopes:
        if scope["rank"] is not None and scope["rank"] not in rank_ids:
            raise ValueError("Annotation rank lacks declared mapping")
        if scope["time_basis"] in ("gpu_stream", "native_kernel") and not scope["gpu_interval_verified"]:
            limitations.append("Unverified GPU intervals remain unknown in layer timing")
            basis = "gpu_unknown"
        else:
            basis = scope["time_basis"]
        key = (scope["name"], scope["kind"], scope["rank"], basis, scope["clock_domain"])
        grouped[key].append(scope)
    results = []
    for key, rows in sorted(grouped.items(), key=lambda item: tuple(str(x) for x in item[0])):
        name, kind, rank, basis, clock = key
        values = [x["duration_ns"] for x in rows] if basis != "gpu_unknown" else []
        matching = [w for w in windows if w.get("rank") == rank and w.get("clock_domain") == clock]
        contained = [x for x in rows if any(x["start_ns"] >= w.get("begin_ns", 0) and
                     x["start_ns"] + x["duration_ns"] <= w.get("end_ns", -1) for w in matching)]
        coverage = "unknown" if not matching else "complete" if len(contained) == len(rows) else "partial"
        med = median(values) if values else None
        spread = (max(values) - min(values)) / med if values and med else None
        results.append({"scope": name, "kind": kind, "rank": rank, "time_basis": basis,
                        "clock_domain": clock, "samples": len(rows), "median_ns": med,
                        "max_ns": max(values) if values else None, "relative_range": spread,
                        "coverage": coverage, "locators": [x["locator"] for x in rows if x["locator"]][:8],
                        "association": "caller_declared"})
    if len(results) > max_groups:
        raise ValueError("Summary group budget exceeded; select a smaller diagnostic")
    if not results and any(item["format"] in ("rocpd", "pftrace", "chrome") for item in manifest["artifacts"]):
        native = query(run, "summary", provider, limit=64, trace_processor=trace_processor, cache=True)
        results = [{"scope": item["category"], "kind": "native_category", "rank": None,
                    "time_basis": "native_interval_sum", "clock_domain": manifest["clock"]["domain"],
                    "samples": item["count"], "median_ns": None, "max_ns": None,
                    "relative_range": None, "coverage": "unknown", "locators": [],
                    "association": "unmapped", "duration_sum_ns": item["duration_ns"]}
                   for item in native["rows"]]
        limitations.append("No consumer layer annotation; native category sums are descriptive only")
    if results:
        candidate = max(results, key=lambda item: item["median_ns"] if item["median_ns"] is not None else -1)
        next_step = ("Inspect scope " + candidate["scope"] + " on rank " + str(candidate["rank"]) +
                     " with a bounded native ROI and matched trace-off control; verify its time basis")
    else:
        next_step = "Add a consumer-owned scope annotation for a bounded diagnostic window"
    if manifest["status"] != "complete":
        limitations.append("Capture/export is not complete; retained data is diagnostic only")
    status = "failed" if manifest["status"] == "failed" else "inconclusive" if manifest["status"] != "complete" else "diagnostic"
    result = validate("summary", {"schema_version": 1, "run_id": manifest["run_id"], "status": status,
        "source_sha256": digest(root / "run-manifest.json"), "groups": results,
        "coverage": {"writer_completed": manifest["coverage"]["writer_completed"],
                     "record_loss": manifest["coverage"]["record_loss"],
                     "declared_windows": len(windows), "rank_mapping": manifest["ranks"],
                     "cross_rank_clock": manifest["clock"]["calibration"]},
        "next_measurement": next_step, "limits": sorted(set(limitations + manifest["limits"]))})
    return result


def markdown(result):
    lines = ["# RDNAScope diagnostic summary", "", "Run: `" + result["run_id"] + "`  ",
             "Status: **" + result["status"] + "**", "",
             "| Scope | Rank | Basis | Samples | Median ns | Max ns | Coverage |", "|---|---:|---|---:|---:|---:|---|"]
    for item in result["groups"]:
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in (
            item["scope"], item["rank"], item["time_basis"], item["samples"],
            item["median_ns"], item["max_ns"], item["coverage"])) + " |")
    lines += ["", "Next measurement: " + (result["next_measurement"] or "none"), "",
              "Source manifest SHA-256: `" + result["source_sha256"] + "`", "", "Limits:"]
    lines += ["- " + value for value in result["limits"]]
    return "\n".join(lines) + "\n"


def write_report(run, provider="auto", trace_processor=None):
    root, _ = verify_run(run)
    result = build(run, provider, trace_processor)
    output = root / "summary.json"
    text_path = root / "summary.md"
    desired = canonical(result) + "\n"
    desired_text = markdown(result)
    if output.exists() and (not output.is_file() or output.read_text() != desired):
        raise ValueError("Existing summary differs; preserve run and choose a new run ID")
    if text_path.exists() and (not text_path.is_file() or text_path.read_text() != desired_text):
        raise ValueError("Existing summary text differs; preserve run and choose a new run ID")
    if not output.exists():
        write_new(output, result)
    if not text_path.exists():
        with text_path.open("x") as stream:
            stream.write(desired_text)
    return result
