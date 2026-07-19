#!/usr/bin/env python3
"""Materialize deterministic R2--R4 manifests for bounded modern replication."""

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
VARIANTS_PATH = ROOT / "conf" / "modern_aci" / "variants.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def payload(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    value = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(value), "sha256": sha256(value)}


def write_or_check(path: Path, value: bytes, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_bytes() != value:
            raise ValueError(f"Generated bounded stage output is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=("R2", "R3", "R4"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stage = args.stage.lower()
    plan = load_yaml(PLAN_PATH)
    dev23 = load_json(DEV23_PATH)
    variants = load_yaml(VARIANTS_PATH)
    experiment = plan["experiment"]
    if plan.get("status") != "RELATIVE_BUDGET_AUTHORIZED_PRICE_UNVERIFIED":
        raise ValueError("Bounded plan is not authorized for stage materialization")
    instance_ids = list(dev23["instances"])
    if len(instance_ids) != 23:
        raise ValueError("Expected exactly 23 frozen dev instances")
    variant_map = {item["id"]: item for item in variants["variants"]}
    configuration_ids = list(experiment["configuration_ids"])
    if sorted(variant_map) != sorted(configuration_ids[1:]):
        raise ValueError("Bounded plan variants do not match modern ACI definitions")

    output_dir = ROOT / "data" / "manifests" / f"bounded_{stage}"
    specs: list[dict[str, Any]] = []
    for configuration_id in configuration_ids:
        manifest_path = output_dir / f"{configuration_id}_dev23.json"
        manifest = {
            "dataset": experiment["dataset"],
            "dataset_revision": experiment["dataset_revision"],
            "split": experiment["split"],
            "source_instance_count": dev23["source_instance_count"],
            "selection": {
                "algorithm": f"frozen bounded-modern {stage.upper()} full dev23 batch",
                "seed": 42,
                "selected_count": len(instance_ids),
                "label": f"{configuration_id}_{stage}",
            },
            "instances": instance_ids,
        }
        manifest_payload = payload(manifest)
        write_or_check(manifest_path, manifest_payload, args.check)
        if configuration_id == "default_aci":
            config_source: str | None = None
            config_path = ROOT / "code" / "SWE-agent" / "config" / "default.yaml"
            asset_dir: str | None = None
        else:
            variant = variant_map[configuration_id]
            config_source = variant["config"]
            config_path = ROOT / config_source
            asset_dir = "conf/modern_aci/commands"
        specs.append(
            {
                "configuration_id": configuration_id,
                "batch_id": f"bounded_{stage}_{configuration_id}",
                "instance_manifest": {
                    "path": manifest_path.relative_to(ROOT).as_posix(),
                    "bytes": len(manifest_payload),
                    "sha256": sha256(manifest_payload),
                },
                "instance_count": len(instance_ids),
                "config_source": config_source,
                "config": file_record(config_path),
                "config_asset_dir": asset_dir,
            }
        )
    output = {
        "schema_version": 1,
        "as_of": plan["as_of"],
        "status": f"READY_FOR_{args.stage.upper()}_EXECUTION",
        "stage": args.stage.upper(),
        "inputs": {
            "bounded_plan": file_record(PLAN_PATH),
            "dev23_manifest": file_record(DEV23_PATH),
            "variant_definitions": file_record(VARIANTS_PATH),
        },
        "execution": {
            "model": experiment["model"],
            "max_api_calls_per_episode": experiment["max_api_calls_per_episode"],
            "new_episode_count": 207,
            "hard_max_api_calls": 5175,
        },
        "batches": specs,
        "cells": [
            {
                "configuration_id": configuration_id,
                "repetition": int(args.stage[-1]),
                "instance_id": instance_id,
                "batch_id": f"bounded_{stage}_{configuration_id}",
                "status": "PLANNED_NOT_EXECUTED",
            }
            for configuration_id in configuration_ids
            for instance_id in instance_ids
        ],
        "completion": {f"{stage}_complete": False, "bounded_modern_reproduction_complete": False},
    }
    if len(output["cells"]) != 207:
        raise ValueError("Each post-R1 stage must contain exactly 207 cells")
    plan_path = ROOT / "data" / "manifests" / f"bounded_modern_{stage}_plan.json"
    write_or_check(plan_path, payload(output), args.check)
    print(json.dumps({"status": output["status"], "batches": len(specs), "new_cells": 207}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
