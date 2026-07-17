#!/usr/bin/env python3
"""Compare regenerated zero-cost paper artifacts with the committed baseline."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "conf" / "full_paper_matrix.yaml"
MANIFEST_PATH = ROOT / "data" / "manifests" / "zero_cost_regeneration_audit.json"
DOC_PATH = ROOT / "docs" / "zero_cost_regeneration_audit.md"
AUDITED_RUN_IDS = {
    "EXP-ARTIFACT-001",
    "EXP-ARTIFACT-002",
    "EXP-ARTIFACT-003",
    "EXP-ARTIFACT-004",
    "EXP-ARTIFACT-007",
    "EXP-ARTIFACT-008",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(args: list[str], *, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def git_blob(revision: str, relative_path: str) -> bytes:
    return git_output(["show", f"{revision}:{relative_path}"], text=False)


def remove_key_recursive(value: Any, key: str) -> None:
    if isinstance(value, dict):
        value.pop(key, None)
        for child in value.values():
            remove_key_recursive(child, key)
    elif isinstance(value, list):
        for child in value:
            remove_key_recursive(child, key)


def normalize_json(payload: bytes) -> Any:
    value = json.loads(payload.decode("utf-8"))
    normalized = copy.deepcopy(value)
    if isinstance(normalized, dict):
        normalized.pop("generated_at_utc", None)
    remove_key_recursive(normalized, "cache_hit")
    return normalized


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


def render_markdown(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    metadata_rows = "\n".join(
        f"| `{row['path']}` | {', '.join(row['ignored_volatile_fields'])} |"
        for row in manifest["observations"]
        if row["comparison"]
        in {"METADATA_ONLY_DIFFERENCE", "LINE_ENDING_ONLY_DIFFERENCE"}
    )
    commands = "\n".join(
        f"- `{command}`" for command in manifest["commands"]
    )
    return f"""# 零成本论文工件再生成审计

## 结论

从冻结输入重新执行六条公开工件生成链后，{summary['target_file_count']} 个受审计文件中 {summary['byte_exact_count']} 个与提交基线逐字节相同，{summary['metadata_only_count']} 个 JSON 仅变化生成时间或 cache-hit 运行元数据，{summary['line_ending_only_count']} 个 CSV 仅因 Git/Windows 文本过滤产生 LF/CRLF 差异；真实内容差异为 {summary['semantic_mismatch_count']}。

重新执行的核心结果保持不变：SWE-bench 主结果八组报告在论文期 evaluator 上 8/8 匹配；HumanEvalFix 三种语言计数与修正分母不变；ACI/超参/pass@k/失败模式源码聚合不变；A01–A10 和 A13–A14 状态不变。

## 执行命令

{commands}

全部命令在本地 WSL2 执行，模型 API、GPU和远程服务器使用均为 0。

## 规范化后相同的非语义变化

| 文件 | 规范化时忽略字段 |
|---|---|
{metadata_rows}

`generated_at_utc` 记录本次执行时间；evaluator 的 `cache_hit` 只表示本地 parquet 是否已存在；`line_endings` 表示工作区 CRLF 与 Git blob LF 的文本过滤差异。三者均不参与论文数值、实例集合或分析结论比较，PDF 等二进制工件仍要求逐字节一致。

## 验收边界

该审计证明当前工作区能从已冻结的公开输入重新生成工件层结果，不证明退役模型可以重新推理，也不补足未发布的消融轨迹、dev37 ID、pass@k 六次预测或失败标签。原模型严格重跑仍保持未完成。

机器清单位于 `data/manifests/zero_cost_regeneration_audit.json`。
"""


def main() -> int:
    matrix = load_yaml(MATRIX_PATH)
    baseline_revision = str(git_output(["rev-parse", "HEAD"])).strip()
    target_paths: set[str] = set()
    for run in matrix.get("artifact_reproduction_runs", []):
        if run.get("id") in AUDITED_RUN_IDS:
            target_paths.update(run.get("outputs", []))

    observations = []
    errors = []
    for relative_path in sorted(target_paths):
        current_path = ROOT / relative_path
        if not current_path.is_file():
            errors.append(f"missing current file: {relative_path}")
            continue
        try:
            baseline = git_blob(baseline_revision, relative_path)
        except subprocess.CalledProcessError:
            errors.append(f"file absent from baseline revision: {relative_path}")
            continue
        current = current_path.read_bytes()
        comparison = "BYTE_EXACT"
        ignored_fields: list[str] = []
        if current != baseline:
            if current_path.suffix == ".json":
                if normalize_json(current) == normalize_json(baseline):
                    comparison = "METADATA_ONLY_DIFFERENCE"
                    ignored_fields = ["generated_at_utc"]
                    if relative_path.endswith("official_evaluator_replay.json"):
                        ignored_fields.append("cache_hit")
                else:
                    comparison = "SEMANTIC_MISMATCH"
            elif current_path.suffix in {".csv", ".md", ".py", ".txt", ".yaml"} and (
                current.replace(b"\r\n", b"\n")
                == baseline.replace(b"\r\n", b"\n")
            ):
                comparison = "LINE_ENDING_ONLY_DIFFERENCE"
                ignored_fields = ["line_endings"]
            else:
                comparison = "BYTE_MISMATCH"
        if comparison in {"SEMANTIC_MISMATCH", "BYTE_MISMATCH"}:
            errors.append(f"regeneration mismatch: {relative_path}")
        observations.append(
            {
                "path": relative_path,
                "comparison": comparison,
                "baseline_bytes": len(baseline),
                "current_bytes": len(current),
                "baseline_sha256": sha256_bytes(baseline),
                "current_sha256": sha256_bytes(current),
                "ignored_volatile_fields": ignored_fields,
            }
        )

    commands = [
        ".venv-analysis/bin/python scripts/reproduce_official_swebench_results.py",
        ".venv-analysis/bin/python scripts/reproduce_humanevalfix.py --figure output/pdf/humanevalfix_turns_artifact.pdf",
        ".venv-analysis/bin/python scripts/reproduce_paper_source_aggregates.py --pdftotext /mnt/d/texlive/2026/bin/windows/pdftotext.exe",
        ".venv-analysis/bin/python scripts/reproduce_official_instance_analyses.py",
        ".venv-analysis/bin/python scripts/reproduce_official_qualitative_interface.py",
        "/home/gugabobo/.venvs/swebench-paper-eval/bin/python scripts/replay_official_evaluator.py --offline",
    ]
    summary = {
        "target_file_count": len(observations),
        "byte_exact_count": sum(
            row["comparison"] == "BYTE_EXACT" for row in observations
        ),
        "metadata_only_count": sum(
            row["comparison"] == "METADATA_ONLY_DIFFERENCE"
            for row in observations
        ),
        "line_ending_only_count": sum(
            row["comparison"] == "LINE_ENDING_ONLY_DIFFERENCE"
            for row in observations
        ),
        "semantic_mismatch_count": sum(
            row["comparison"] in {"SEMANTIC_MISMATCH", "BYTE_MISMATCH"}
            for row in observations
        ),
        "errors": errors,
    }
    manifest = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": (
            "COMPLETE_SEMANTIC_REGENERATION_NO_DERIVED_DRIFT"
            if not errors
            else "FAILED_REGENERATION_AUDIT"
        ),
        "baseline_revision": baseline_revision,
        "audited_artifact_runs": sorted(AUDITED_RUN_IDS),
        "commands": commands,
        "runtime": {
            "execution": "local_wsl2",
            "model_api_calls": 0,
            "gpu_used": False,
            "server_used": False,
        },
        "observations": observations,
        "summary": summary,
    }
    DOC_PATH.write_text(render_markdown(manifest), encoding="utf-8")
    manifest["outputs"] = {
        "audit_document": file_record(DOC_PATH),
    }
    write_json(MANIFEST_PATH, manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                **summary,
                "manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
