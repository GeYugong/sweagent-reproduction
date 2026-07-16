#!/usr/bin/env python3
"""Validate the frozen full-paper reproduction contract without running experiments."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "conf" / "full_paper_matrix.yaml"
INVENTORY_PATH = ROOT / "conf" / "paper_output_inventory.yaml"
STUDY_PATH = ROOT / "conf" / "study.yaml"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


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

    full_reproduction = study.get("full_reproduction", {})
    if full_reproduction.get("matrix") != "conf/full_paper_matrix.yaml":
        errors.append("study matrix pointer is not frozen")
    if full_reproduction.get("paper_output_inventory") != "conf/paper_output_inventory.yaml":
        errors.append("study output inventory pointer is not frozen")
    if full_reproduction.get("minimum_unique_agent_episodes") != 13_140:
        errors.append("study minimum episode count must be 13140")
    if set(full_reproduction.get("evidence_types", [])) != expected_evidence_types:
        errors.append("study evidence types do not match the matrix")
    if full_reproduction.get("explicit_total_budget_authorized") is not False:
        errors.append("budget authorization must remain false until explicitly approved")

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
        "errors": errors,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
