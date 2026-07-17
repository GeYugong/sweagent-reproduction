#!/usr/bin/env python3
"""Record conservative C0-relative usage for bounded modern replication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "conf" / "bounded_modern_reproduction.yaml"
TRACE_ROOT = ROOT / "outputs" / "traces"
OUTPUT_PATH = ROOT / "data" / "manifests" / "bounded_modern_budget_ledger.json"
BASELINE = {"resource_calls": 398, "input_tokens": 5_496_947, "output_tokens": 70_405}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="R1")
    args = parser.parse_args()
    plan = load_yaml(PLAN_PATH)
    trajectories = sorted(TRACE_ROOT.glob(f"bounded_{args.stage.lower()}_*/*.traj"))
    totals = {"persisted_calls": 0, "input_tokens": 0, "output_tokens": 0}
    observations = []
    for trajectory_path in trajectories:
        with trajectory_path.open(encoding="utf-8") as handle:
            trajectory = json.load(handle)
        stats = trajectory.get("info", {}).get("model_stats", {})
        row = {
            "path": trajectory_path.relative_to(ROOT).as_posix(),
            "api_calls": int(stats.get("api_calls", 0)),
            "input_tokens": int(stats.get("tokens_sent", 0)),
            "output_tokens": int(stats.get("tokens_received", 0)),
        }
        totals["persisted_calls"] += row["api_calls"]
        totals["input_tokens"] += row["input_tokens"]
        totals["output_tokens"] += row["output_tokens"]
        observations.append(row)
    multiples = {
        "calls": totals["persisted_calls"] / BASELINE["resource_calls"],
        "input_tokens": totals["input_tokens"] / BASELINE["input_tokens"],
        "output_tokens": totals["output_tokens"] / BASELINE["output_tokens"],
    }
    conservative_multiple = max(multiples.values(), default=0.0)
    budget = plan["budget"]
    if conservative_multiple >= budget["absolute_hard_stop_multiple_of_C0"]:
        status = "HARD_STOP_80_C0"
    elif conservative_multiple >= budget["normal_remaining_budget_multiple_of_C0"]:
        status = "PAUSE_AT_50_C0"
    else:
        status = "WITHIN_RELATIVE_BUDGET"
    ledger = {
        "schema_version": 1,
        "as_of": plan["as_of"],
        "stage": args.stage,
        "status": status,
        "inputs": {"bounded_plan": file_record(PLAN_PATH)},
        "observations": observations,
        "totals": totals,
        "baseline_C0_usage": BASELINE,
        "relative_usage_multiples": multiples,
        "conservative_usage_multiple_C0": conservative_multiple,
        "pricing_status": "DOLLAR_PRICE_UNVERIFIED",
        "model_api_calls_in_ledger": totals["persisted_calls"],
    }
    OUTPUT_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "trajectory_count": len(observations), "conservative_C0": conservative_multiple}, indent=2, ensure_ascii=False))
    return 0 if status == "WITHIN_RELATIVE_BUDGET" else 1


if __name__ == "__main__":
    raise SystemExit(main())
