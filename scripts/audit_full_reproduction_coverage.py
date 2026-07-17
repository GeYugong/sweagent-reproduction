#!/usr/bin/env python3
"""Audit public-paper output coverage without running model inference."""

from __future__ import annotations

import csv
import hashlib
import json
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "conf" / "full_paper_matrix.yaml"
INVENTORY_PATH = ROOT / "conf" / "paper_output_inventory.yaml"
PROTOCOL_PATH = ROOT / "data" / "manifests" / "paper_protocol_recovery.json"
GOLD_REPLAY_PATH = (
    ROOT / "data" / "manifests" / "official_gold_repository_replay.json"
)
CSV_PATH = ROOT / "data" / "derived" / "paper_output_coverage.csv"
DOC_PATH = ROOT / "docs" / "public_artifact_completion_audit.md"
MANIFEST_PATH = ROOT / "data" / "manifests" / "full_reproduction_coverage.json"

PROTOCOL_TERMINAL_STATUSES = {
    "RECOVERED",
    "RECOVERED_CONFIG_ONLY",
    "RECOVERED_PARAMETER_IMPLEMENTATION_ONLY",
    "INFERABLE_NOT_RELEASED",
    "BLOCKED_MISSING_OFFICIAL_IMPLEMENTATION",
}
RESULT_ASSET_TERMINAL_STATUSES = {
    "PAPER_AGGREGATE_RECOVERED_RAW_RUNS_MISSING",
    "PAPER_AGGREGATE_RECOVERED_RAW_RUNS_AND_DEV37_MISSING",
    "PAPER_AGGREGATE_RECOVERED_RAW_PREDICTIONS_MISSING",
    "PAPER_AGGREGATE_RECOVERED_RAW_LABELS_MISSING",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_markdown(
    as_of: str,
    status_counts: Counter[str],
    output_count: int,
    exact_count: int,
    documented_gap_count: int,
    source_verified_count: int,
    audited_count: int,
    blocking_gates: list[dict[str, str]],
) -> str:
    status_rows = "\n".join(
        f"| `{status}` | {count} |" for status, count in sorted(status_counts.items())
    )
    gate_rows = "\n".join(
        f"| `{gate['id']}` | `{gate['status']}` |"
        for gate in blocking_gates
    )
    return f"""# 公开工件复现完成审计

审计日期：{as_of}

## 结论

公开工件复现层已完成，覆盖论文输出清单 {output_count}/{output_count}。这一结论表示所有公开可得的论文源码成员、作者发布的预测/轨迹/评测工件及可确定性派生文件均已核验；未公开的逐实例原始运行、标签或精确实现已经完成负检索并进入明确终态。

该结论不等于整篇论文严格复现完成。论文指定的退役模型、部分精确消融配置、dev37 实例清单、失败标签、批量预算、磁盘和容器资源仍未满足；现代模型实验也不能替代原模型严格重跑。

## 输出覆盖

- 论文输出清单：{output_count}/{output_count} 处于可审计终态；
- 作者工件精确复算：{exact_count} 项；
- 作者工件复算且量化公开缺口：{documented_gap_count} 项；
- 论文源码资产验证：{source_verified_count} 项；
- prompt、命令或界面审计：{audited_count} 项；
- 12 个论文期仓库 gold 环境：11 个 full-reference outcome，1 个 Requests 外网语义替代验证，仓库级 12/12。

| 输出状态 | 数量 |
|---|---:|
{status_rows}

逐输出证据、source member 数量、派生文件状态和 gate 状态位于 `data/derived/paper_output_coverage.csv`。唯一 source member 与派生文件的字节数、SHA-256，以及输入清单哈希位于 `data/manifests/full_reproduction_coverage.json`。

## 缺失私有工件的终态

协议恢复清单中的 11 个组件和 4 组结果资产均已进入终态。未发布内容包括 Shell-only 和部分 ACI 实现、八项消融原始运行、dev37 ID、五次采样轨迹、六次 pass@k 预测、248 个失败标签及 15 个验证样本。论文聚合值可以从源码重建，但不会被表述为逐实例原始工件复算。

## 严格重跑阻塞门槛

| 门槛 | 状态 |
|---|---|
{gate_rows}

严格完成判定保持为：`public_artifact_reproduction_complete AND exact_model_rerun_complete`。当前公开工件项为真，原模型重跑项为假，因此 `strict_full_paper_reproduction_complete=false`。

## 可复核命令

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /mnt/d/0code/Research/05/.venv-analysis/bin/python `
  scripts/audit_full_reproduction_coverage.py

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /mnt/d/0code/Research/05/.venv-analysis/bin/python `
  scripts/validate_full_reproduction_plan.py
```
"""


def main() -> int:
    matrix = load_yaml(MATRIX_PATH)
    inventory = load_yaml(INVENTORY_PATH)
    protocol = load_json(PROTOCOL_PATH)
    gold_replay = load_json(GOLD_REPLAY_PATH)

    gates = {gate["id"]: gate for gate in matrix.get("gates", [])}
    terminal_output_statuses = set(inventory.get("status_semantics", {}))
    source_archive = ROOT / inventory["source_archive"]
    source_records: dict[str, dict[str, Any]] = {}
    generated_records: dict[str, dict[str, Any]] = {}
    observations: list[dict[str, Any]] = []

    with tarfile.open(source_archive, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        for output in inventory.get("outputs", []):
            for member_name in output.get("source_members", []):
                if member_name in source_records or member_name not in members:
                    continue
                member = members[member_name]
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                payload = extracted.read()
                source_records[member_name] = {
                    "path": member_name,
                    "bytes": len(payload),
                    "sha256": sha256_bytes(payload),
                }

    for output in inventory.get("outputs", []):
        source_members = output.get("source_members", [])
        generated_artifacts = output.get("generated_artifacts", [])
        requirements = output.get("requires", [])
        missing_source = [
            member for member in source_members if member not in source_records
        ]
        missing_generated = [
            path for path in generated_artifacts if not (ROOT / path).is_file()
        ]
        for relative_path in generated_artifacts:
            path = ROOT / relative_path
            if path.is_file() and relative_path not in generated_records:
                generated_records[relative_path] = file_record(path)
        blocking_requirements = [
            gate_id
            for gate_id in requirements
            if str(gates.get(gate_id, {}).get("status", "UNKNOWN")).startswith(
                ("BLOCKED", "PARTIALLY")
            )
        ]
        status_terminal = output.get("status") in terminal_output_statuses
        public_terminal = (
            status_terminal and not missing_source and not missing_generated
        )
        observations.append(
            {
                "id": output.get("id"),
                "kind": output.get("kind"),
                "paper_label": output.get("paper_label"),
                "status": output.get("status"),
                "evidence_lanes": output.get("evidence_lanes", []),
                "source_member_count": len(source_members),
                "all_source_members_present": not missing_source,
                "missing_source_members": missing_source,
                "generated_artifact_count": len(generated_artifacts),
                "all_generated_artifacts_present": not missing_generated,
                "missing_generated_artifacts": missing_generated,
                "requires": requirements,
                "requirement_statuses": {
                    gate_id: gates.get(gate_id, {}).get("status", "UNKNOWN")
                    for gate_id in requirements
                },
                "blocking_requirements": blocking_requirements,
                "status_terminal": status_terminal,
                "public_terminal": public_terminal,
            }
        )

    protocol_components = protocol.get("protocol_components", [])
    result_assets = protocol.get("result_assets", [])
    protocol_terminal = all(
        entry.get("status") in PROTOCOL_TERMINAL_STATUSES
        for entry in protocol_components
    ) and all(
        entry.get("status") in RESULT_ASSET_TERMINAL_STATUSES
        for entry in result_assets
    )
    paper_source_matches_protocol = (
        sha256_file(source_archive) == protocol.get("paper", {}).get("source_sha256")
    )
    gold_summary = gold_replay.get("summary", {})
    evaluator_terminal = (
        gold_summary.get("all_validated") is True
        and gold_summary.get("validated_outcome_match_count") == 12
        and gold_summary.get("exact_outcome_match_count") == 11
        and gold_summary.get("semantic_outcome_match_count") == 1
        and str(gates.get("G_EVALUATOR_REPLAY", {}).get("status", "")).startswith(
            "COMPLETE_"
        )
    )
    output_count = len(observations)
    outputs_terminal = output_count == 54 and all(
        observation["public_terminal"] for observation in observations
    )
    negative_findings_terminal = len(protocol.get("negative_findings", [])) >= 7
    public_complete = all(
        (
            outputs_terminal,
            protocol_terminal,
            negative_findings_terminal,
            paper_source_matches_protocol,
            evaluator_terminal,
        )
    )

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    csv_fields = [
        "id",
        "kind",
        "paper_label",
        "status",
        "evidence_lanes",
        "source_member_count",
        "all_source_members_present",
        "generated_artifact_count",
        "all_generated_artifacts_present",
        "requires",
        "blocking_requirements",
        "status_terminal",
        "public_terminal",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, lineterminator="\n")
        writer.writeheader()
        for observation in observations:
            row = {field: observation.get(field) for field in csv_fields}
            for field in ("evidence_lanes", "requires", "blocking_requirements"):
                row[field] = ";".join(row[field])
            writer.writerow(row)

    status_counts = Counter(
        str(observation["status"]) for observation in observations
    )
    blocking_gates = [
        {"id": gate_id, "status": str(gate.get("status"))}
        for gate_id, gate in gates.items()
        if str(gate.get("status", "")).startswith(("BLOCKED", "PARTIALLY"))
    ]
    DOC_PATH.write_text(
        build_markdown(
            as_of=str(matrix.get("as_of")),
            status_counts=status_counts,
            output_count=output_count,
            exact_count=status_counts["ARTIFACT_RECOMPUTED_EXACT"],
            documented_gap_count=(
                status_counts["ARTIFACT_RECOMPUTED_WITH_DOCUMENTED_GAP"]
                + status_counts["SOURCE_AGGREGATE_REBUILT_RAW_INPUT_BLOCKED"]
            ),
            source_verified_count=status_counts["SOURCE_ASSET_VERIFIED"],
            audited_count=status_counts["ARTIFACT_AUDITED"],
            blocking_gates=blocking_gates,
        ),
        encoding="utf-8",
    )

    completion = matrix.get("completion_contract", {})
    manifest = {
        "schema_version": 1,
        "as_of": matrix.get("as_of"),
        "generated_at_utc": utc_now(),
        "scope": "SWE-agent paper public-artifact completion audit",
        "status": (
            "COMPLETE_PUBLIC_ARTIFACT_REPRODUCTION"
            if public_complete
            else "INCOMPLETE_PUBLIC_ARTIFACT_REPRODUCTION"
        ),
        "inputs": {
            "matrix": file_record(MATRIX_PATH),
            "inventory": file_record(INVENTORY_PATH),
            "protocol_recovery": file_record(PROTOCOL_PATH),
            "gold_repository_replay": file_record(GOLD_REPLAY_PATH),
            "paper_source": file_record(source_archive),
        },
        "source_members": [source_records[key] for key in sorted(source_records)],
        "generated_artifacts": [
            generated_records[key] for key in sorted(generated_records)
        ],
        "observations": observations,
        "protocol_recovery": {
            "component_count": len(protocol_components),
            "result_asset_count": len(result_assets),
            "negative_finding_count": len(protocol.get("negative_findings", [])),
            "all_missing_official_artifacts_terminal": protocol_terminal
            and negative_findings_terminal,
        },
        "evaluator_replay": {
            "repository_count": 12,
            "full_reference_count": gold_summary.get(
                "exact_outcome_match_count"
            ),
            "external_network_semantic_count": gold_summary.get(
                "semantic_outcome_match_count"
            ),
            "validated_count": gold_summary.get("validated_outcome_match_count"),
            "complete": evaluator_terminal,
        },
        "summary": {
            "paper_output_count": output_count,
            "public_terminal_output_count": sum(
                observation["public_terminal"] for observation in observations
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "unique_source_member_count": len(source_records),
            "unique_generated_artifact_count": len(generated_records),
            "paper_source_matches_protocol_sha256": paper_source_matches_protocol,
            "outputs_terminal": outputs_terminal,
            "missing_official_artifacts_terminal": protocol_terminal
            and negative_findings_terminal,
            "evaluator_repository_coverage_complete": evaluator_terminal,
        },
        "completion": {
            "computed_public_artifact_reproduction_complete": public_complete,
            "declared_public_artifact_reproduction_complete": completion.get(
                "public_artifact_reproduction_complete"
            ),
            "exact_model_rerun_complete": completion.get(
                "exact_model_rerun_complete"
            ),
            "modern_replication_complete": completion.get(
                "modern_replication_complete"
            ),
            "strict_full_paper_reproduction_complete": completion.get(
                "strict_full_paper_reproduction_complete"
            ),
        },
        "outputs": {
            "coverage_csv": file_record(CSV_PATH),
            "completion_audit": file_record(DOC_PATH),
        },
    }
    write_json(MANIFEST_PATH, manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "paper_outputs": f"{sum(row['public_terminal'] for row in observations)}/{output_count}",
                "source_members": len(source_records),
                "generated_artifacts": len(generated_records),
                "protocol_terminal": protocol_terminal,
                "evaluator_terminal": evaluator_terminal,
                "declared_public_complete": completion.get(
                    "public_artifact_reproduction_complete"
                ),
                "computed_public_complete": public_complete,
                "manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if public_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
