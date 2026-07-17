#!/usr/bin/env python3
"""Validate the frozen full-paper reproduction contract without running experiments."""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "conf" / "full_paper_matrix.yaml"
INVENTORY_PATH = ROOT / "conf" / "paper_output_inventory.yaml"
STUDY_PATH = ROOT / "conf" / "study.yaml"
COVERAGE_PATH = ROOT / "data" / "manifests" / "full_reproduction_coverage.json"
MODERN_ANALYSIS_PATH = (
    ROOT / "data" / "manifests" / "modern_dev20_baseline_analysis.json"
)
REGENERATION_AUDIT_PATH = (
    ROOT / "data" / "manifests" / "zero_cost_regeneration_audit.json"
)
MODERN_ACI_STATIC_PATH = (
    ROOT / "data" / "manifests" / "modern_aci_variant_validation.json"
)
MODERN_ACI_RUNTIME_PATH = (
    ROOT / "data" / "manifests" / "modern_aci_runtime_validation.json"
)
MODERN_ACI_PAIRING_PATH = (
    ROOT / "data" / "manifests" / "modern_aci_dev20_pairing.json"
)
BOUNDED_MODERN_CONFIG_PATH = ROOT / "conf" / "bounded_modern_reproduction.yaml"
BOUNDED_DEV23_PATH = ROOT / "data" / "manifests" / "swebench_lite_dev23_full.json"
DEV20_SELECTION_PATH = ROOT / "data" / "manifests" / "swebench_lite_dev20_seed42.json"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def is_blocking(status: str) -> bool:
    return status.startswith(("BLOCKED", "IN_PROGRESS", "NOT_STARTED", "PARTIALLY"))


def main() -> int:
    matrix = load_yaml(MATRIX_PATH)
    inventory = load_yaml(INVENTORY_PATH)
    study = load_yaml(STUDY_PATH)
    errors: list[str] = []

    if matrix.get("schema_version") != 2:
        errors.append("full_paper_matrix schema_version must be 2")
    if inventory.get("schema_version") != 1:
        errors.append("paper_output_inventory schema_version must be 1")
    expected_evidence_types = {"source", "artifact", "exact", "modern", "exploratory"}
    if set(matrix.get("evidence_types", {})) != expected_evidence_types:
        errors.append("matrix evidence types must be source/artifact/exact/modern/exploratory")

    experiments = matrix.get("experiments", [])
    experiment_ids = [entry.get("id") for entry in experiments]
    expected_ids = [f"E{index:02d}" for index in range(1, 19)]
    if experiment_ids != expected_ids:
        errors.append(f"experiment IDs must be ordered E01-E18, got {experiment_ids}")
    if len(experiment_ids) != len(set(experiment_ids)):
        errors.append("experiment IDs are not unique")

    gross_episodes = sum(int(entry.get("episodes", 0)) for entry in experiments)
    accounting = matrix.get("episode_accounting", {})
    if gross_episodes != 13_440:
        errors.append(f"gross experiment episode total must be 13440, got {gross_episodes}")
    if accounting.get("maximum_without_proven_reuse") != gross_episodes:
        errors.append("maximum_without_proven_reuse does not match experiment sum")
    if accounting.get("minimum_unique_agent_episodes") != gross_episodes - 300:
        errors.append("minimum unique episodes must reuse exactly one 300-instance E03 run")
    if accounting.get("failure_label_requests") != 248:
        errors.append("E18 failure-label request count must be 248")

    gates = matrix.get("gates", [])
    gate_ids = [entry.get("id") for entry in gates]
    gate_map = {entry.get("id"): entry for entry in gates}
    if len(gate_ids) != len(set(gate_ids)):
        errors.append("gate IDs are not unique")
    required_gate_ids = {
        "G_MODEL_GPT4_TURBO",
        "G_MODEL_CLAUDE_3_OPUS",
        "G_MODEL_FAILURE_LABELER",
        "G_OFFICIAL_ARTIFACTS",
        "G_EXACT_ABLATION_CONFIGS",
        "G_EXACT_RUNTIME_PROMPTS",
        "G_DEV37_MANIFEST",
        "G_HUMANEVAL_LANGUAGE",
        "G_API_PRICING_AND_BUDGET",
        "G_EXPERIMENT_BUDGET_AUTHORIZATION",
        "G_FORMAL_DISK",
        "G_SERVER_RUNTIME",
        "G_EVALUATOR_REPLAY",
    }
    missing_gates = sorted(required_gate_ids - set(gate_ids))
    if missing_gates:
        errors.append(f"missing required gates: {missing_gates}")

    global_exact_requires = matrix.get("global_exact_requires", [])
    for gate_id in global_exact_requires:
        if gate_id not in gate_map:
            errors.append(f"global exact requirement references unknown gate {gate_id}")

    analysis_ids = {
        entry.get("id") for entry in matrix.get("analysis_artifacts", [])
    }
    for experiment in experiments:
        for gate_id in experiment.get("requires", []):
            if gate_id not in gate_map:
                errors.append(f"{experiment.get('id')} references unknown gate {gate_id}")
        for artifact_id in experiment.get("artifacts", []):
            if artifact_id not in analysis_ids:
                errors.append(
                    f"{experiment.get('id')} references unknown analysis artifact {artifact_id}"
                )
        if experiment.get("evidence") == "exact" and str(
            experiment.get("status", "")
        ).startswith("COMPLETE"):
            all_requires = list(experiment.get("requires", [])) + list(
                global_exact_requires
            )
            blocked = [
                gate_id
                for gate_id in all_requires
                if is_blocking(str(gate_map[gate_id].get("status", "")))
            ]
            if blocked:
                errors.append(
                    f"{experiment.get('id')} is complete while gates remain blocking: {blocked}"
                )

    outputs = inventory.get("outputs", [])
    terminal_output_statuses = set(inventory.get("status_semantics", {}))
    output_ids = [entry.get("id") for entry in outputs]
    labels = [entry.get("paper_label") for entry in outputs]
    if len(outputs) != 54:
        errors.append(f"paper output inventory must contain 54 entries, got {len(outputs)}")
    if len(output_ids) != len(set(output_ids)):
        errors.append("paper output inventory IDs are not unique")
    if len(labels) != len(set(labels)):
        errors.append("paper output labels are not unique")
    expected_output_ids = [f"O{index:02d}" for index in range(1, 55)]
    if output_ids != expected_output_ids:
        errors.append("paper output inventory IDs must be ordered O01-O54")

    source_archive = ROOT / inventory.get("source_archive", "")
    if not source_archive.is_file():
        errors.append(f"paper source archive is missing: {source_archive}")
        source_members: set[str] = set()
    else:
        with tarfile.open(source_archive, "r:gz") as archive:
            source_members = {member.name for member in archive.getmembers()}

    inventory_gate_ids: set[str] = set()
    inventory_matrix_artifacts: set[str] = set()
    for output in outputs:
        output_id = output.get("id")
        if output.get("status") not in terminal_output_statuses:
            errors.append(
                f"{output_id} has a non-terminal or unknown status: {output.get('status')}"
            )
        if not output.get("acceptance"):
            errors.append(f"{output_id} has no acceptance criterion")
        for source_member in output.get("source_members", []):
            if source_member not in source_members:
                errors.append(f"{output_id} source member is absent: {source_member}")
        for artifact_path in output.get("generated_artifacts", []):
            if not (ROOT / artifact_path).is_file():
                errors.append(f"{output_id} generated artifact is absent: {artifact_path}")
        for gate_id in output.get("requires", []):
            inventory_gate_ids.add(gate_id)
            if gate_id not in gate_map:
                errors.append(f"{output_id} references unknown gate {gate_id}")
        for artifact_id in output.get("matrix_artifacts", []):
            inventory_matrix_artifacts.add(artifact_id)
            if artifact_id not in analysis_ids:
                errors.append(f"{output_id} references unknown matrix artifact {artifact_id}")

    uncovered_analysis = sorted(analysis_ids - inventory_matrix_artifacts)
    if uncovered_analysis:
        errors.append(f"analysis artifacts absent from paper inventory: {uncovered_analysis}")

    completion = matrix.get("completion_contract", {})
    strict_expected = bool(completion.get("public_artifact_reproduction_complete")) and bool(
        completion.get("exact_model_rerun_complete")
    )
    if bool(completion.get("strict_full_paper_reproduction_complete")) != strict_expected:
        errors.append("strict completion flag violates the declared AND rule")
    if completion.get("output_inventory") != "conf/paper_output_inventory.yaml":
        errors.append("matrix output inventory pointer is not frozen")
    if completion.get("reproduction_report") != "docs/reproduction_report.md":
        errors.append("matrix reproduction report pointer is not frozen")
    if not (ROOT / "docs" / "reproduction_report.md").is_file():
        errors.append("reproduction report is missing")

    public_complete = bool(completion.get("public_artifact_reproduction_complete"))
    coverage = load_json(COVERAGE_PATH) if COVERAGE_PATH.is_file() else {}
    if public_complete:
        if coverage.get("status") != "COMPLETE_PUBLIC_ARTIFACT_REPRODUCTION":
            errors.append("public completion is declared without a complete coverage audit")
        coverage_completion = coverage.get("completion", {})
        if coverage_completion.get(
            "computed_public_artifact_reproduction_complete"
        ) is not True:
            errors.append("coverage audit does not compute public completion")
        if coverage_completion.get(
            "declared_public_artifact_reproduction_complete"
        ) is not True:
            errors.append("coverage audit was not generated from the public-complete contract")
        coverage_summary = coverage.get("summary", {})
        if coverage_summary.get("paper_output_count") != 54:
            errors.append("coverage audit does not contain all 54 paper outputs")
        if coverage_summary.get("public_terminal_output_count") != 54:
            errors.append("coverage audit has non-terminal paper outputs")
        if len(coverage.get("observations", [])) != 54 or not all(
            entry.get("public_terminal") is True
            for entry in coverage.get("observations", [])
        ):
            errors.append("coverage observations are incomplete or non-terminal")
        if coverage_summary.get("missing_official_artifacts_terminal") is not True:
            errors.append("missing official artifacts do not have terminal evidence")
        if coverage_summary.get("evaluator_repository_coverage_complete") is not True:
            errors.append("coverage audit lacks repository evaluator coverage")
        expected_input_paths = {
            "matrix": MATRIX_PATH,
            "inventory": INVENTORY_PATH,
            "protocol_recovery": ROOT
            / "data"
            / "manifests"
            / "paper_protocol_recovery.json",
            "gold_repository_replay": ROOT
            / "data"
            / "manifests"
            / "official_gold_repository_replay.json",
        }
        for key, path in expected_input_paths.items():
            observed_hash = coverage.get("inputs", {}).get(key, {}).get("sha256")
            if not path.is_file() or observed_hash != sha256_file(path):
                errors.append(f"coverage input hash is stale or missing: {key}")
        for key in ("coverage_csv", "completion_audit"):
            record = coverage.get("outputs", {}).get(key, {})
            path = ROOT / str(record.get("path", ""))
            if not path.is_file() or record.get("sha256") != sha256_file(path):
                errors.append(f"coverage output hash is stale or missing: {key}")
        generated_records = coverage.get("generated_artifacts", [])
        if len(generated_records) != 35:
            errors.append("coverage audit must pin 35 unique generated artifacts")
        for record in generated_records:
            path = ROOT / str(record.get("path", ""))
            if not path.is_file() or record.get("sha256") != sha256_file(path):
                errors.append(
                    f"coverage generated artifact hash is stale: {record.get('path')}"
                )
        source_records = coverage.get("source_members", [])
        if len(source_records) != 56:
            errors.append("coverage audit must pin 56 unique source members")
        if source_archive.is_file():
            with tarfile.open(source_archive, "r:gz") as archive:
                archive_members = {
                    member.name: member for member in archive.getmembers()
                }
                for record in source_records:
                    member = archive_members.get(str(record.get("path", "")))
                    extracted = archive.extractfile(member) if member else None
                    payload = extracted.read() if extracted else None
                    if payload is None or record.get("sha256") != sha256_bytes(payload):
                        errors.append(
                            f"coverage source member hash is stale: {record.get('path')}"
                        )
        for field in (
            "exact_model_rerun_complete",
            "modern_replication_complete",
            "strict_full_paper_reproduction_complete",
        ):
            if coverage_completion.get(field) is not completion.get(field):
                errors.append(f"coverage and matrix completion flags differ: {field}")

    full_reproduction = study.get("full_reproduction", {})
    if full_reproduction.get("matrix") != "conf/full_paper_matrix.yaml":
        errors.append("study matrix pointer is not frozen")
    if full_reproduction.get("report") != "docs/reproduction_report.md":
        errors.append("study reproduction report pointer is not frozen")
    if full_reproduction.get("paper_output_inventory") != "conf/paper_output_inventory.yaml":
        errors.append("study output inventory pointer is not frozen")
    if full_reproduction.get("coverage_manifest") != (
        "data/manifests/full_reproduction_coverage.json"
    ):
        errors.append("study coverage manifest pointer is not frozen")
    if full_reproduction.get("minimum_unique_agent_episodes") != 13_140:
        errors.append("study minimum episode count must be 13140")
    if set(full_reproduction.get("evidence_types", [])) != expected_evidence_types:
        errors.append("study evidence types do not match the matrix")
    if full_reproduction.get("explicit_total_budget_authorized") is not False:
        errors.append("budget authorization must remain false until explicitly approved")
    for field in (
        "public_artifact_reproduction_complete",
        "exact_model_rerun_complete",
        "modern_replication_complete",
        "strict_full_paper_reproduction_complete",
    ):
        if full_reproduction.get(field) is not completion.get(field):
            errors.append(f"study and matrix completion flags differ: {field}")

    modern_runs = {
        entry.get("id"): entry for entry in matrix.get("existing_non_exact_runs", [])
    }
    modern_baseline = modern_runs.get("EXP-DEV20", {})
    modern_analysis = (
        load_json(MODERN_ANALYSIS_PATH) if MODERN_ANALYSIS_PATH.is_file() else {}
    )
    if str(modern_baseline.get("status", "")).startswith("COMPLETE_"):
        if modern_analysis.get("status") != (
            "COMPLETE_BASELINE_STATISTICS_WITH_ONE_USAGE_PERSISTENCE_GAP"
        ):
            errors.append("modern dev20 baseline lacks a complete analysis manifest")
        modern_summary = modern_analysis.get("summary", {})
        expected_modern_values = {
            "instances": modern_summary.get("evaluated_count"),
            "resolved": modern_summary.get("resolved_count"),
            "persisted_api_calls": modern_summary.get("persisted_api_calls"),
            "resource_audited_api_calls": modern_summary.get(
                "resource_audited_api_calls"
            ),
            "persisted_input_tokens": modern_summary.get(
                "persisted_input_tokens"
            ),
            "persisted_output_tokens": modern_summary.get(
                "persisted_output_tokens"
            ),
            "runtime_args_verified": modern_summary.get(
                "runtime_args_verified_count"
            ),
        }
        for field, expected in expected_modern_values.items():
            if modern_baseline.get(field) != expected:
                errors.append(f"matrix modern baseline field is stale: {field}")
        if modern_summary.get("evaluated_count") != 20:
            errors.append("modern dev20 analysis must contain 20 instances")
        if modern_summary.get("resolved_count") != 4:
            errors.append("modern dev20 analysis resolved count must be 4")
        if modern_analysis.get("completion", {}).get(
            "modern_replication_complete"
        ) is not False:
            errors.append("dev20 baseline cannot complete the modern replication")
        for key in ("run_map", "selection_manifest"):
            record = modern_analysis.get("inputs", {}).get(key, {})
            path = ROOT / str(record.get("path", ""))
            if not path.is_file() or record.get("sha256") != sha256_file(path):
                errors.append(f"modern analysis input hash is stale or missing: {key}")
        for key in ("instance_csv", "analysis_document"):
            record = modern_analysis.get("outputs", {}).get(key, {})
            path = ROOT / str(record.get("path", ""))
            if not path.is_file() or record.get("sha256") != sha256_file(path):
                errors.append(f"modern analysis output hash is stale or missing: {key}")

    modern_aci = modern_runs.get("EXP-MODERN-ACI-PREP", {})
    if not modern_aci:
        errors.append("modern ACI preparation entry is missing from the matrix")
    else:
        static_validation = (
            load_json(MODERN_ACI_STATIC_PATH) if MODERN_ACI_STATIC_PATH.is_file() else {}
        )
        runtime_validation = (
            load_json(MODERN_ACI_RUNTIME_PATH)
            if MODERN_ACI_RUNTIME_PATH.is_file()
            else {}
        )
        pairing = (
            load_json(MODERN_ACI_PAIRING_PATH) if MODERN_ACI_PAIRING_PATH.is_file() else {}
        )
        if static_validation.get("status") != "COMPLETE_STATIC_SINGLE_FACTOR_VALIDATION":
            errors.append("modern ACI static validation is missing or incomplete")
        static_summary = static_validation.get("summary", {})
        if static_summary.get("variant_count") != 8 or static_summary.get(
            "single_factor_valid_count"
        ) != 8:
            errors.append("modern ACI static validation must contain eight valid variants")
        if static_summary.get("model_api_calls") != 0:
            errors.append("modern ACI static preparation must not call a model API")
        for variant in static_validation.get("variants", []):
            record = variant.get("config", {})
            path = ROOT / str(record.get("path", ""))
            if not path.is_file() or record.get("sha256") != sha256_file(path):
                errors.append(
                    f"modern ACI generated config hash is stale: {variant.get('id')}"
                )
            if variant.get("single_factor_valid") is not True:
                errors.append(f"modern ACI variant is not single-factor valid: {variant.get('id')}")
        if runtime_validation.get("status") != (
            "COMPLETE_RUNTIME_PARSER_AND_BEHAVIOR_VALIDATION"
        ):
            errors.append("modern ACI runtime validation is missing or incomplete")
        runtime_summary = runtime_validation.get("summary", {})
        if (
            runtime_summary.get("variant_count") != 8
            or runtime_summary.get("parsed_variant_count") != 8
            or runtime_summary.get("behavior_test_count") != 4
            or runtime_summary.get("passed_behavior_test_count") != 4
            or runtime_summary.get("errors") != []
        ):
            errors.append("modern ACI runtime validation counters are incomplete")
        if runtime_validation.get("runtime", {}).get("model_api_calls") != 0:
            errors.append("modern ACI runtime validation must not call a model API")
        runtime_static_record = runtime_validation.get("inputs", {}).get(
            "static_validation", {}
        )
        if (
            not MODERN_ACI_STATIC_PATH.is_file()
            or runtime_static_record.get("sha256") != sha256_file(MODERN_ACI_STATIC_PATH)
        ):
            errors.append("modern ACI runtime validation is stale against static validation")
        if pairing.get("status") != "READY_BLOCKED_PRICE_AND_BUDGET":
            errors.append("modern ACI pairing manifest is not budget-blocked and ready")
        execution = pairing.get("execution", {})
        expected_pairing_fields = {
            "variant_count": 8,
            "instances_per_variant": 20,
            "planned_new_episodes": 160,
            "hard_max_api_calls": 4000,
            "model_api_calls_executed_for_preparation": 0,
        }
        for field, expected in expected_pairing_fields.items():
            if execution.get(field) != expected:
                errors.append(f"modern ACI pairing field is stale: {field}")
            if modern_aci.get(field) not in (None, expected):
                errors.append(f"matrix modern ACI field is stale: {field}")
        if len(pairing.get("planned_runs", [])) != 160:
            errors.append("modern ACI pairing must contain 160 planned runs")
        planned_ids = [row.get("planned_run_id") for row in pairing.get("planned_runs", [])]
        if len(planned_ids) != len(set(planned_ids)):
            errors.append("modern ACI planned run IDs are not unique")
        if not all(
            row.get("status") == "PLANNED_NOT_EXECUTED"
            for row in pairing.get("planned_runs", [])
        ):
            errors.append("modern ACI pairing includes an unexpected execution status")
        readiness = pairing.get("readiness", {})
        if (
            readiness.get("static_single_factor_validation_complete") is not True
            or readiness.get("runtime_parser_and_behavior_validation_complete")
            is not True
            or readiness.get("pricing_verified") is not False
            or readiness.get("paid_execution_allowed") is not False
        ):
            errors.append("modern ACI pairing readiness flags are invalid")
        if pairing.get("completion", {}).get("modern_replication_complete") is not False:
            errors.append("modern ACI preparation cannot complete modern replication")
        if modern_aci.get("completed_new_episodes") != 0:
            errors.append("matrix modern ACI preparation must record zero completed episodes")
        if modern_aci.get("paired_aci_ablations_complete") is not False:
            errors.append("matrix modern ACI preparation cannot mark paired ablations complete")
        expected_study_paths = {
            "aci_variant_definitions": "conf/modern_aci/variants.yaml",
            "aci_static_validation": "data/manifests/modern_aci_variant_validation.json",
            "aci_runtime_validation": "data/manifests/modern_aci_runtime_validation.json",
            "aci_pairing_manifest": "data/manifests/modern_aci_dev20_pairing.json",
            "aci_reconstruction_document": "docs/modern_aci_reconstruction.md",
        }
        modern_study = study.get("modern_replication", {})
        for field, expected in expected_study_paths.items():
            if modern_study.get(field) != expected:
                errors.append(f"study modern ACI pointer is stale: {field}")
        for path in (
            ROOT / "conf" / "modern_aci" / "variants.yaml",
            MODERN_ACI_STATIC_PATH,
            MODERN_ACI_RUNTIME_PATH,
            MODERN_ACI_PAIRING_PATH,
            ROOT / "docs" / "modern_aci_reconstruction.md",
        ):
            if not path.is_file():
                errors.append(f"modern ACI required file is missing: {path}")

    bounded_run = modern_runs.get("EXP-BOUNDED-MODERN-ACI", {})
    bounded = (
        load_yaml(BOUNDED_MODERN_CONFIG_PATH)
        if BOUNDED_MODERN_CONFIG_PATH.is_file()
        else {}
    )
    dev23 = load_json(BOUNDED_DEV23_PATH) if BOUNDED_DEV23_PATH.is_file() else {}
    dev20 = load_json(DEV20_SELECTION_PATH) if DEV20_SELECTION_PATH.is_file() else {}
    if not bounded_run:
        errors.append("bounded modern reproduction entry is missing from the matrix")
    if bounded.get("schema_version") != 1:
        errors.append("bounded modern reproduction config must use schema_version 1")
    if bounded.get("status") != "PREREGISTERED_WAITING_FOR_PRICE_CALIBRATION":
        errors.append("bounded modern reproduction status is not preregistered")
    if bounded.get("completion_marker") != "BOUNDED_MODERN_REPRODUCTION_COMPLETE":
        errors.append("bounded modern completion marker is not frozen")
    bounded_experiment = bounded.get("experiment", {})
    bounded_expected = {
        "instances": 23,
        "configurations": 9,
        "repetitions_per_configuration_instance": 4,
        "total_episode_cells": 828,
        "existing_episode_cells_credited": 20,
        "new_episode_cells": 808,
        "new_hard_max_api_calls": 20200,
    }
    for field, expected in bounded_expected.items():
        if bounded_experiment.get(field) != expected:
            errors.append(f"bounded modern experiment field is stale: {field}")
    if bounded_experiment.get("total_episode_cells") != (
        bounded_experiment.get("instances", 0)
        * bounded_experiment.get("configurations", 0)
        * bounded_experiment.get("repetitions_per_configuration_instance", 0)
    ):
        errors.append("bounded modern total episode arithmetic is invalid")
    if bounded_experiment.get("new_episode_cells") != (
        bounded_experiment.get("total_episode_cells", 0)
        - bounded_experiment.get("existing_episode_cells_credited", 0)
    ):
        errors.append("bounded modern new episode arithmetic is invalid")
    budget = bounded.get("budget", {})
    if not (
        budget.get("planned_remaining_cost_multiple_of_C0") == 40.4
        and budget.get("normal_remaining_budget_multiple_of_C0") == 50.0
        and budget.get("absolute_hard_stop_multiple_of_C0") == 80.0
        and budget.get("reference_billed_usd_known") is False
        and budget.get("unknown_price_is_zero") is False
    ):
        errors.append("bounded modern budget or price gate is not frozen")
    if not (
        budget.get("planned_remaining_cost_multiple_of_C0", 999)
        < budget.get("normal_remaining_budget_multiple_of_C0", 0)
        < budget.get("absolute_hard_stop_multiple_of_C0", 0)
    ):
        errors.append("bounded modern budget ordering is invalid")
    stages = bounded.get("stages", [])
    if [stage.get("id") for stage in stages] != ["R1", "R2", "R3", "R4"]:
        errors.append("bounded modern stages must be ordered R1-R4")
    if [stage.get("cumulative_new_episodes") for stage in stages] != [
        187,
        394,
        601,
        808,
    ]:
        errors.append("bounded modern cumulative episode checkpoints are invalid")
    if bounded.get("completion_contract", {}).get("completion_flag_initial") is not False:
        errors.append("bounded modern completion flag must remain false before execution")
    dev23_instances = dev23.get("instances", [])
    expected_dev23 = sorted(
        list(dev20.get("instances", [])) + list(dev20.get("holdout_instances", []))
    )
    if (
        len(dev23_instances) != 23
        or len(dev23_instances) != len(set(dev23_instances))
        or dev23_instances != expected_dev23
    ):
        errors.append("bounded dev23 manifest does not equal selected plus holdout dev IDs")
    bounded_study = study.get("modern_replication", {})
    bounded_study_expected = {
        "bounded_completion_plan": "docs/bounded_reproduction_completion_plan.md",
        "bounded_completion_config": "conf/bounded_modern_reproduction.yaml",
        "bounded_dev23_manifest": "data/manifests/swebench_lite_dev23_full.json",
        "bounded_completion_marker": "BOUNDED_MODERN_REPRODUCTION_COMPLETE",
        "bounded_total_episode_cells": 828,
        "bounded_existing_episode_cells": 20,
        "bounded_new_episode_cells": 808,
        "bounded_planned_cost_multiple_of_current": 40.4,
        "bounded_normal_budget_multiple_of_current": 50.0,
        "bounded_absolute_hard_stop_multiple_of_current": 80.0,
    }
    for field, expected in bounded_study_expected.items():
        if bounded_study.get(field) != expected:
            errors.append(f"study bounded modern field is stale: {field}")
    for path in (
        BOUNDED_MODERN_CONFIG_PATH,
        BOUNDED_DEV23_PATH,
        ROOT / "docs" / "bounded_reproduction_completion_plan.md",
    ):
        if not path.is_file():
            errors.append(f"bounded modern required file is missing: {path}")

    artifact_runs = {
        entry.get("id"): entry for entry in matrix.get("artifact_reproduction_runs", [])
    }
    regeneration_run = artifact_runs.get("EXP-ARTIFACT-011", {})
    regeneration_audit = (
        load_json(REGENERATION_AUDIT_PATH)
        if REGENERATION_AUDIT_PATH.is_file()
        else {}
    )
    if regeneration_run:
        if regeneration_audit.get("status") != (
            "COMPLETE_SEMANTIC_REGENERATION_NO_DERIVED_DRIFT"
        ):
            errors.append("zero-cost regeneration audit is missing or incomplete")
        regeneration_summary = regeneration_audit.get("summary", {})
        regeneration_fields = {
            "target_files": "target_file_count",
            "byte_exact_files": "byte_exact_count",
            "metadata_only_files": "metadata_only_count",
            "line_ending_only_files": "line_ending_only_count",
            "semantic_mismatches": "semantic_mismatch_count",
        }
        for matrix_field, summary_field in regeneration_fields.items():
            if regeneration_run.get(matrix_field) != regeneration_summary.get(
                summary_field
            ):
                errors.append(
                    f"matrix regeneration audit field is stale: {matrix_field}"
                )
        if regeneration_summary.get("errors") != []:
            errors.append("zero-cost regeneration audit retains errors")
        document = regeneration_audit.get("outputs", {}).get(
            "audit_document", {}
        )
        document_path = ROOT / str(document.get("path", ""))
        if (
            not document_path.is_file()
            or document.get("sha256") != sha256_file(document_path)
        ):
            errors.append("zero-cost regeneration audit document hash is stale")

    resource = matrix.get("resource_measurements", {})
    if resource.get("formal_scale_up_allowed") is not False:
        errors.append("formal scale-up cannot be allowed below the disk threshold")
    if float(resource.get("free_gb", 0)) >= float(resource.get("formal_threshold_gb", 0)):
        errors.append("resource gate says blocked but recorded free disk meets the threshold")

    report = {
        "valid": not errors,
        "experiment_count": len(experiments),
        "gross_agent_episodes": gross_episodes,
        "minimum_unique_agent_episodes": accounting.get(
            "minimum_unique_agent_episodes"
        ),
        "failure_label_requests": accounting.get("failure_label_requests"),
        "gate_count": len(gates),
        "paper_output_count": len(outputs),
        "inventory_gate_references": sorted(inventory_gate_ids),
        "strict_full_paper_reproduction_complete": completion.get(
            "strict_full_paper_reproduction_complete"
        ),
        "public_artifact_reproduction_complete": completion.get(
            "public_artifact_reproduction_complete"
        ),
        "exact_model_rerun_complete": completion.get("exact_model_rerun_complete"),
        "errors": errors,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
