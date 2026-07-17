#!/usr/bin/env python3
"""Materialize the frozen R1 batch manifests for bounded modern replication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "conf" / "bounded_modern_reproduction.yaml"
DEV23_PATH = ROOT / "data" / "manifests" / "swebench_lite_dev23_full.json"
DEV20_PATH = ROOT / "data" / "manifests" / "swebench_lite_dev20_seed42.json"
VARIANTS_PATH = ROOT / "conf" / "modern_aci" / "variants.yaml"
OUTPUT_DIR = ROOT / "data" / "manifests" / "bounded_r1"
PLAN_OUTPUT = ROOT / "data" / "manifests" / "bounded_modern_r1_plan.json"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def json_payload(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_or_check(path: Path, payload: bytes, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_bytes() != payload:
            raise ValueError(f"Generated bounded R1 output is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def batch_manifest(
    plan: dict[str, Any], dev23: dict[str, Any], instance_ids: list[str], label: str
) -> dict[str, Any]:
    experiment = plan["experiment"]
    return {
        "dataset": experiment["dataset"],
        "dataset_revision": experiment["dataset_revision"],
        "split": experiment["split"],
        "source_instance_count": dev23["source_instance_count"],
        "selection": {
            "algorithm": "frozen bounded-modern R1 batch subset",
            "seed": 42,
            "selected_count": len(instance_ids),
            "label": label,
        },
        "instances": instance_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    plan = load_yaml(PLAN_PATH)
    dev23 = load_json(DEV23_PATH)
    dev20 = load_json(DEV20_PATH)
    variants = load_yaml(VARIANTS_PATH)
    experiment = plan["experiment"]
    if plan.get("status") != "RELATIVE_BUDGET_AUTHORIZED_PRICE_UNVERIFIED":
        raise ValueError("Bounded plan is not authorized for R1 materialization")
    dev23_ids = list(dev23["instances"])
    existing_default_ids = list(dev20["instances"])
    missing_default_ids = [item for item in dev23_ids if item not in existing_default_ids]
    if len(dev23_ids) != 23 or len(existing_default_ids) != 20 or len(missing_default_ids) != 3:
        raise ValueError("Expected dev23 with exactly three default-ACI holdouts")

    variant_map = {item["id"]: item for item in variants["variants"]}
    expected_variant_ids = list(experiment["configuration_ids"])[1:]
    if sorted(variant_map) != sorted(expected_variant_ids):
        raise ValueError("Bounded plan variants do not match modern ACI definitions")

    specs: list[dict[str, Any]] = []
    default_manifest_path = OUTPUT_DIR / "default_aci_missing3.json"
    default_payload = json_payload(
        batch_manifest(plan, dev23, missing_default_ids, "default_aci_r1_missing3")
    )
    write_or_check(default_manifest_path, default_payload, args.check)
    default_config_path = ROOT / "code" / "SWE-agent" / "config" / "default.yaml"
    specs.append(
        {
            "configuration_id": "default_aci",
            "batch_id": "bounded_r1_default_aci",
            "instance_manifest": {
                "path": default_manifest_path.relative_to(ROOT).as_posix(),
                "bytes": len(default_payload),
                "sha256": sha256_bytes(default_payload),
            },
            "instance_count": len(missing_default_ids),
            "config_source": None,
            "config": file_record(default_config_path),
            "config_asset_dir": None,
        }
    )
    for variant_id in expected_variant_ids:
        variant = variant_map[variant_id]
        manifest_path = OUTPUT_DIR / f"{variant_id}_dev23.json"
        payload = json_payload(batch_manifest(plan, dev23, dev23_ids, f"{variant_id}_r1"))
        write_or_check(manifest_path, payload, args.check)
        config_path = ROOT / variant["config"]
        specs.append(
            {
                "configuration_id": variant_id,
                "batch_id": f"bounded_r1_{variant_id}",
                "instance_manifest": {
                    "path": manifest_path.relative_to(ROOT).as_posix(),
                    "bytes": len(payload),
                    "sha256": sha256_bytes(payload),
                },
                "instance_count": len(dev23_ids),
                "config_source": variant["config"],
                "config": file_record(config_path),
                "config_asset_dir": "conf/modern_aci/commands",
            }
        )

    planned_cells = []
    for instance_id in existing_default_ids:
        planned_cells.append(
            {
                "configuration_id": "default_aci",
                "repetition": 1,
                "instance_id": instance_id,
                "status": "CREDITED_EXISTING_BASELINE",
            }
        )
    for spec in specs:
        manifest = load_json(ROOT / spec["instance_manifest"]["path"])
        for instance_id in manifest["instances"]:
            planned_cells.append(
                {
                    "configuration_id": spec["configuration_id"],
                    "repetition": 1,
                    "instance_id": instance_id,
                    "batch_id": spec["batch_id"],
                    "status": "PLANNED_NOT_EXECUTED",
                }
            )
    if len(planned_cells) != 207 or sum(
        row["status"] == "PLANNED_NOT_EXECUTED" for row in planned_cells
    ) != 187:
        raise ValueError("R1 must contain 20 credited and 187 new cells")

    output = {
        "schema_version": 1,
        "as_of": plan["as_of"],
        "status": "READY_FOR_R1_EXECUTION",
        "stage": "R1",
        "inputs": {
            "bounded_plan": file_record(PLAN_PATH),
            "dev23_manifest": file_record(DEV23_PATH),
            "dev20_baseline_manifest": file_record(DEV20_PATH),
            "variant_definitions": file_record(VARIANTS_PATH),
        },
        "execution": {
            "model": experiment["model"],
            "max_api_calls_per_episode": experiment["max_api_calls_per_episode"],
            "new_episode_count": 187,
            "credited_episode_count": 20,
            "total_r1_cells": 207,
            "hard_max_api_calls": 4675,
            "relative_budget_checkpoint_C0": 9.35,
            "model_api_calls_executed": 0,
        },
        "batches": specs,
        "cells": planned_cells,
        "completion": {
            "r1_complete": False,
            "bounded_modern_reproduction_complete": False,
        },
    }
    write_or_check(PLAN_OUTPUT, json_payload(output), args.check)
    print(
        json.dumps(
            {
                "status": output["status"],
                "batches": len(specs),
                "new_cells": output["execution"]["new_episode_count"],
                "credited_cells": output["execution"]["credited_episode_count"],
                "model_api_calls": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
