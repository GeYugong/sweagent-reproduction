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
