#!/usr/bin/env python3
"""Materialize and validate the preregistered modern ACI configurations."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = ROOT / "conf" / "modern_aci" / "variants.yaml"
CUSTOM_COMMAND_ROOT = ROOT / "conf" / "modern_aci" / "commands"
VALIDATION_PATH = ROOT / "data" / "manifests" / "modern_aci_variant_validation.json"
RUNTIME_VALIDATION_PATH = (
    ROOT / "data" / "manifests" / "modern_aci_runtime_validation.json"
)
PAIRING_PATH = ROOT / "data" / "manifests" / "modern_aci_dev20_pairing.json"
BASELINE_RUN_MAP_PATH = ROOT / "conf" / "modern_dev20_baseline_runs.yaml"
BASELINE_ANALYSIS_PATH = (
    ROOT / "data" / "manifests" / "modern_dev20_baseline_analysis.json"
)
FUNCTION_PATTERN = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{", re.MULTILINE
)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def bytes_record(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def yaml_bytes(value: dict[str, Any], variant_id: str) -> bytes:
    body = yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        width=100_000,
    )
    header = (
        "# GENERATED FILE: scripts/materialize_modern_aci_variants.py\n"
        f"# Modern reconstructed ACI variant: {variant_id}\n"
        "# This configuration is not an exact unpublished paper-run config.\n"
    )
    return (header + body).encode("utf-8")


def write_or_check(path: Path, payload: bytes, check: bool) -> None:
    if check:
        if not path.is_file():
            raise FileNotFoundError(f"Generated output is missing: {path}")
        if path.read_bytes() != payload:
            raise ValueError(f"Generated output is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def recursive_diff(left: Any, right: Any, path: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                differences.append(child)
            else:
                differences.extend(recursive_diff(left[key], right[key], child))
        return differences
    if left != right:
        return [path or "<root>"]
    return []


def normalize_trailing_whitespace(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: normalize_trailing_whitespace(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [normalize_trailing_whitespace(child) for child in value]
    if isinstance(value, str):
        return "\n".join(line.rstrip() for line in value.split("\n"))
    return value


def apply_transformation(
    base: dict[str, Any], transformation: dict[str, Any]
) -> dict[str, Any]:
    result = copy.deepcopy(base)
    operation = transformation.get("operation")
    if operation == "replace_command_file":
        old = transformation["old"]
        new = transformation["new"]
        command_files = result["command_files"]
        if command_files.count(old) != 1 or new in command_files:
            raise ValueError(f"Cannot replace command file {old!r} with {new!r}")
        command_files[command_files.index(old)] = new
    elif operation == "remove_command_file":
        value = transformation["value"]
        command_files = result["command_files"]
        if command_files.count(value) != 1:
            raise ValueError(f"Cannot remove command file exactly once: {value!r}")
        command_files.remove(value)
    elif operation == "append_command_file":
        value = transformation["value"]
        command_files = result["command_files"]
        if value in command_files:
            raise ValueError(f"Command file is already present: {value!r}")
        command_files.append(value)
    elif operation == "set_env":
        result["env_variables"][transformation["key"]] = transformation["value"]
    elif operation == "set_top_level":
        result[transformation["key"]] = transformation["value"]
    elif operation == "clear_top_level_list":
        key = transformation["key"]
        if not isinstance(result.get(key), list) or not result[key]:
            raise ValueError(f"Cannot clear absent or empty list: {key}")
        result[key] = []
    else:
        raise ValueError(f"Unsupported transformation operation: {operation!r}")
    return result


def resolve_command_file(relative_path: str) -> Path:
    if not relative_path.startswith("config/commands/"):
        raise ValueError(f"Unexpected command path: {relative_path}")
    basename = Path(relative_path).name
    custom = CUSTOM_COMMAND_ROOT / basename
    if basename.startswith(("modern_", "_modern_")):
        candidate = custom
    else:
        candidate = ROOT / "code" / "SWE-agent" / relative_path
    if not candidate.is_file():
        raise FileNotFoundError(f"Command file is missing: {candidate}")
    return candidate


def public_commands(config: dict[str, Any]) -> tuple[list[str], list[str]]:
    public: list[str] = []
    helpers: list[str] = []
    for command_path in config["command_files"]:
        path = resolve_command_file(command_path)
        if path.suffix != ".sh":
            continue
        for name in FUNCTION_PATTERN.findall(path.read_text(encoding="utf-8")):
            if name.startswith("_"):
                helpers.append(name)
            else:
                public.append(name)
    return public, helpers


def current_runtime_validation(
    static_validation_sha256: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not RUNTIME_VALIDATION_PATH.is_file():
        return None, None
    runtime = load_json(RUNTIME_VALIDATION_PATH)
    valid = (
        runtime.get("status") == "COMPLETE_RUNTIME_PARSER_AND_BEHAVIOR_VALIDATION"
        and runtime.get("inputs", {})
        .get("static_validation", {})
        .get("sha256")
        == static_validation_sha256
        and runtime.get("summary", {}).get("variant_count") == 8
        and runtime.get("summary", {}).get("errors") == []
        and runtime.get("runtime", {}).get("model_api_calls") == 0
    )
    return runtime if valid else None, file_record(RUNTIME_VALIDATION_PATH)


def build_pairing_manifest(
    definitions: dict[str, Any],
    variant_records: list[dict[str, Any]],
    static_validation_record: dict[str, Any],
    runtime_validation: dict[str, Any] | None,
    runtime_record: dict[str, Any] | None,
) -> dict[str, Any]:
    base = definitions["base"]
    selection_path = ROOT / base["selection_manifest"]
    selection = load_json(selection_path)
    instances = selection["instances"]
    if len(instances) != 20 or len(instances) != len(set(instances)):
        raise ValueError("The paired modern manifest requires 20 unique instances")

    baseline_runs = load_yaml(BASELINE_RUN_MAP_PATH)
    baseline_analysis = load_json(BASELINE_ANALYSIS_PATH)
    run_by_instance = {
        row["instance_id"]: row for row in baseline_runs.get("runs", [])
    }
    observation_by_instance = {
        row["instance_id"]: row
        for row in baseline_analysis.get("observations", [])
    }
    if set(run_by_instance) != set(instances):
        raise ValueError("Baseline run map does not match the frozen dev20 selection")
    if set(observation_by_instance) != set(instances):
        raise ValueError("Baseline analysis does not match the frozen dev20 selection")

    variants_by_id = {row["id"]: row for row in variant_records}
    planned_runs: list[dict[str, Any]] = []
    for variant in definitions["variants"]:
        variant_id = variant["id"]
        config_record = variants_by_id[variant_id]["config"]
        for instance_id in instances:
            baseline_run = run_by_instance[instance_id]
            baseline_observation = observation_by_instance[instance_id]
            safe_instance = instance_id.replace("__", "_")
            planned_runs.append(
                {
                    "variant_id": variant_id,
                    "instance_id": instance_id,
                    "planned_run_id": f"modern_aci_{variant_id}_{safe_instance}",
                    "config_sha256": config_record["sha256"],
                    "paired_baseline_run_id": baseline_run["run_id"],
                    "paired_baseline_run_directory": baseline_run["run_directory"],
                    "paired_baseline_outcome": baseline_observation["outcome"],
                    "paired_baseline_resolved": baseline_observation["resolved"],
                    "status": "PLANNED_NOT_EXECUTED",
                }
            )

    summary = baseline_analysis["summary"]
    variant_count = len(definitions["variants"])
    episode_count = len(planned_runs)
    if variant_count != 8 or episode_count != 160:
        raise ValueError("Expected eight variants and 160 paired episodes")
    scale = episode_count / summary["evaluated_count"]
    runtime_complete = runtime_validation is not None
    status = (
        "READY_BLOCKED_PRICE_AND_BUDGET"
        if runtime_complete
        else "PREPARED_PENDING_RUNTIME_VALIDATION"
    )
    inputs: dict[str, Any] = {
        "variant_definitions": file_record(DEFINITION_PATH),
        "static_validation": static_validation_record,
        "selection_manifest": file_record(selection_path),
        "baseline_run_map": file_record(BASELINE_RUN_MAP_PATH),
        "baseline_analysis": file_record(BASELINE_ANALYSIS_PATH),
    }
    if runtime_complete and runtime_record is not None:
        inputs["runtime_validation"] = runtime_record
    return {
        "schema_version": 1,
        "as_of": definitions["as_of"],
        "evidence": "modern_reconstructed",
        "status": status,
        "paper_alignment": {
            "sweagent_revision": base["sweagent_revision"],
            "dataset": base["dataset"],
            "dataset_revision": base["dataset_revision"],
            "split": base["split"],
            "temperature": base["temperature"],
            "top_p": base["top_p"],
            "max_api_calls_per_instance": base["max_api_calls_per_instance"],
            "exact_paper_run_configs_available": False,
            "direct_comparison_to_paper_test_rate_allowed": False,
        },
        "execution": {
            "model": base["model"],
            "variant_count": variant_count,
            "instances_per_variant": len(instances),
            "planned_new_episodes": episode_count,
            "hard_max_api_calls": episode_count
            * base["max_api_calls_per_instance"],
            "model_api_calls_executed_for_preparation": 0,
            "gpu_required": False,
            "server_required": False,
            "pricing_status": "UNKNOWN",
            "explicit_total_budget_authorized": False,
        },
        "baseline_projection_lower_bounds": {
            "basis_episodes": summary["evaluated_count"],
            "known_usage_persistence_gap": True,
            "projected_persisted_api_calls": round(
                summary["persisted_api_calls"] * scale
            ),
            "projected_resource_audited_api_calls": round(
                summary["resource_audited_api_calls"] * scale
            ),
            "projected_input_tokens": round(
                summary["persisted_input_tokens"] * scale
            ),
            "projected_output_tokens": round(
                summary["persisted_output_tokens"] * scale
            ),
            "dollar_cost": None,
        },
        "analysis_preregistration": {
            "primary_outcome": "RESOLVED_FULL",
            "denominator_rule": "All selected instances, including empty predictions and format or call-limit exits",
            "paired_test": "two-sided exact McNemar per variant versus the frozen baseline",
            "multiple_testing": "Holm family-wise correction across eight primary comparisons",
            "effect_interval": "paired resolution-rate difference with 10000 paired bootstrap resamples",
            "bootstrap_seed": 42,
            "retry_policy": "no automatic retry",
        },
        "inputs": inputs,
        "variants": variant_records,
        "planned_runs": planned_runs,
        "readiness": {
            "static_single_factor_validation_complete": True,
            "runtime_parser_and_behavior_validation_complete": runtime_complete,
            "paired_manifest_complete": True,
            "pricing_verified": False,
            "explicit_total_budget_authorized": False,
            "paid_execution_allowed": False,
        },
        "completion": {
            "preparation_complete": runtime_complete,
            "paired_runs_complete": False,
            "paired_analysis_complete": False,
            "modern_replication_complete": False,
            "exact_model_rerun_complete": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that every generated file is current without changing files.",
    )
    args = parser.parse_args()

    definitions = load_yaml(DEFINITION_PATH)
    if definitions.get("schema_version") != 1:
        raise ValueError("Modern ACI definitions must use schema_version 1")
    base_path = ROOT / definitions["base"]["config"]
    if sha256_file(base_path) != definitions["base"]["sha256"]:
        raise ValueError("Frozen base configuration hash has changed")
    base_config = load_yaml(base_path)

    variant_ids: list[str] = []
    variant_records: list[dict[str, Any]] = []
    for variant in definitions.get("variants", []):
        variant_id = variant["id"]
        if variant_id in variant_ids:
            raise ValueError(f"Duplicate variant id: {variant_id}")
        variant_ids.append(variant_id)
        generated = apply_transformation(base_config, variant["transformation"])
        diff_paths = recursive_diff(base_config, generated)
        if diff_paths != variant["expected_diff_paths"]:
            raise ValueError(
                f"{variant_id} changes {diff_paths}, expected {variant['expected_diff_paths']}"
            )

        observed_public, helper_functions = public_commands(generated)
        if observed_public != variant["expected_public_commands"]:
            raise ValueError(
                f"{variant_id} exposes {observed_public}, expected "
                f"{variant['expected_public_commands']}"
            )
        if len(observed_public) != len(set(observed_public)):
            raise ValueError(f"{variant_id} has duplicate public command functions")

        reference_record = None
        reference_raw_diff_paths: list[str] = []
        if variant.get("public_reference_config"):
            reference_path = ROOT / variant["public_reference_config"]
            if sha256_file(reference_path) != variant["public_reference_sha256"]:
                raise ValueError(f"{variant_id} public reference hash has changed")
            reference_config = load_yaml(reference_path)
            reference_raw_diff_paths = recursive_diff(generated, reference_config)
            if (
                variant.get("public_reference_match_mode")
                != "trailing_whitespace_normalized"
            ):
                raise ValueError(f"{variant_id} has an unsupported reference match mode")
            if normalize_trailing_whitespace(reference_config) != (
                normalize_trailing_whitespace(generated)
            ):
                raise ValueError(
                    f"{variant_id} does not match its normalized public reference"
                )
            reference_record = file_record(reference_path)

        asset_records = []
        for relative_asset in variant.get("assets", []):
            asset_path = ROOT / relative_asset
            if not asset_path.is_file():
                raise FileNotFoundError(f"Missing modern ACI asset: {asset_path}")
            asset_records.append(file_record(asset_path))

        config_path = ROOT / variant["config"]
        payload = yaml_bytes(generated, variant_id)
        write_or_check(config_path, payload, args.check)
        record: dict[str, Any] = {
            "id": variant_id,
            "paper_component": variant["paper_component"],
            "paper_label": variant["paper_label"],
            "paper_resolved_percent": variant["paper_resolved_percent"],
            "paper_absolute_drop_points": variant[
                "paper_absolute_drop_points"
            ],
            "reconstruction_class": variant["reconstruction_class"],
            "exact_paper_run_config_available": variant[
                "exact_paper_run_config_available"
            ],
            "transformation": variant["transformation"],
            "observed_diff_paths": diff_paths,
            "single_factor_valid": True,
            "expected_public_commands": variant["expected_public_commands"],
            "observed_public_commands": observed_public,
            "helper_functions": helper_functions,
            "config": bytes_record(config_path, payload),
            "assets": asset_records,
        }
        if reference_record is not None:
            record["public_reference_config"] = reference_record
            record["public_reference_match_mode"] = variant[
                "public_reference_match_mode"
            ]
            record["public_reference_raw_diff_paths"] = reference_raw_diff_paths
            record["public_reference_normalized_match"] = True
        variant_records.append(record)

    if variant_ids != [
        "edit_without_linting",
        "no_edit",
        "iterative_search",
        "no_search",
        "window_30",
        "full_file",
        "full_history",
        "no_demonstration",
    ]:
        raise ValueError("Modern ACI variants are missing or out of preregistered order")

    validation = {
        "schema_version": 1,
        "as_of": definitions["as_of"],
        "evidence": "modern_reconstructed",
        "status": "COMPLETE_STATIC_SINGLE_FACTOR_VALIDATION",
        "inputs": {
            "variant_definitions": file_record(DEFINITION_PATH),
            "base_config": file_record(base_path),
        },
        "summary": {
            "variant_count": len(variant_records),
            "single_factor_valid_count": sum(
                row["single_factor_valid"] for row in variant_records
            ),
            "behavioral_reconstruction_count": sum(
                row["reconstruction_class"] == "behavioral_reconstruction"
                for row in variant_records
            ),
            "exact_paper_run_config_count": sum(
                row["exact_paper_run_config_available"]
                for row in variant_records
            ),
            "model_api_calls": 0,
        },
        "variants": variant_records,
        "completion": {
            "static_single_factor_validation_complete": True,
            "runtime_parser_validation_complete": False,
            "paired_runs_complete": False,
            "modern_replication_complete": False,
            "exact_model_rerun_complete": False,
        },
    }
    validation_payload = json_bytes(validation)
    write_or_check(VALIDATION_PATH, validation_payload, args.check)
    validation_record = bytes_record(VALIDATION_PATH, validation_payload)

    runtime_validation, runtime_record = current_runtime_validation(
        validation_record["sha256"]
    )
    pairing = build_pairing_manifest(
        definitions,
        variant_records,
        validation_record,
        runtime_validation,
        runtime_record,
    )
    pairing_payload = json_bytes(pairing)
    write_or_check(PAIRING_PATH, pairing_payload, args.check)

    print(
        json.dumps(
            {
                "mode": "check" if args.check else "write",
                "static_status": validation["status"],
                "pairing_status": pairing["status"],
                "variants": len(variant_records),
                "single_factor_valid": validation["summary"][
                    "single_factor_valid_count"
                ],
                "planned_runs": len(pairing["planned_runs"]),
                "runtime_validation_current": runtime_validation is not None,
                "model_api_calls": 0,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
