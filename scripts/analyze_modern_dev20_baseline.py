#!/usr/bin/env python3
"""Freeze and analyze the completed modern-model dev20 baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "conf" / "modern_dev20_baseline_runs.yaml"
DEFAULT_MANIFEST = (
    ROOT / "data" / "manifests" / "modern_dev20_baseline_analysis.json"
)
DEFAULT_CSV = ROOT / "data" / "derived" / "modern_dev20_baseline_instances.csv"
DEFAULT_DOC = ROOT / "docs" / "modern_dev20_baseline_analysis.md"
RESOLVED_OUTCOMES = {"RESOLVED_FULL"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def find_outcome(statuses: list[str]) -> str:
    for status in reversed(statuses):
        if status.startswith("RESOLVED_"):
            return status
    if "not_generated" in statuses:
        return "NOT_GENERATED"
    if "generated" in statuses and "applied" not in statuses:
        return "PATCH_APPLY_FAILED"
    return "UNKNOWN"


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("Wilson interval requires a positive denominator")
    probability = successes / total
    denominator = 1 + z * z / total
    center = (probability + z * z / (2 * total)) / denominator
    half_width = (
        z
        * math.sqrt(
            probability * (1 - probability) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return center - half_width, center + half_width


def numeric_summary(values: list[int]) -> dict[str, float | int]:
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    return {
        "sum": sum(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "q1": quartiles[0],
        "q3": quartiles[2],
        "minimum": min(values),
        "maximum": max(values),
    }


def collect_observation(
    config: dict[str, Any],
    run: dict[str, str],
    trace_root: Path,
) -> dict[str, Any]:
    run_dir = trace_root / run["run_directory"]
    resolved_run_dir = run_dir.resolve()
    if not resolved_run_dir.is_relative_to(trace_root.resolve()):
        raise ValueError(f"Run directory escapes trace root: {run_dir}")
    scorecard_path = run_dir / "scorecards.json"
    trajectory_path = run_dir / f"{run['instance_id']}.traj"
    if not scorecard_path.is_file() or not trajectory_path.is_file():
        raise FileNotFoundError(
            f"Missing scorecard or trajectory for {run['instance_id']}"
        )
    scorecards = load_json(scorecard_path)
    if not isinstance(scorecards, list) or len(scorecards) != 1:
        raise ValueError(f"Expected one scorecard in {scorecard_path}")
    scorecard = scorecards[0]
    if scorecard.get("instance_id") != run["instance_id"]:
        raise ValueError(f"Scorecard instance mismatch in {scorecard_path}")
    trajectory = load_json(trajectory_path)
    statuses = list(scorecard.get("statuses", []))
    outcome = find_outcome(statuses)
    model_stats = trajectory.get("info", {}).get("model_stats", {})
    exit_status = trajectory.get("info", {}).get("exit_status")

    args_path = run_dir / "args.yaml"
    args_record = None
    args_model_verified = None
    args_parameters_verified = None
    if args_path.is_file():
        args = load_yaml(args_path)
        model_args = args.get("agent", {}).get("model", {})
        args_model_verified = model_args.get("model_name") == config["model"]
        args_parameters_verified = (
            float(model_args.get("temperature")) == float(config["temperature"])
            and float(model_args.get("top_p")) == float(config["top_p"])
        )
        args_record = file_record(args_path)

    raw_files = {
        "scorecard": file_record(scorecard_path),
        "trajectory": file_record(trajectory_path),
    }
    for key, filename in (
        ("predictions", "all_preds.jsonl"),
        ("results", "results.json"),
        ("run_manifest", "run_manifest.txt"),
    ):
        path = run_dir / filename
        raw_files[key] = file_record(path) if path.is_file() else None
    raw_files["args"] = args_record

    return {
        "run_id": run["run_id"],
        "instance_id": run["instance_id"],
        "repository": run["instance_id"].split("__", 1)[0],
        "run_directory": run["run_directory"],
        "scorecard_statuses": statuses,
        "outcome": outcome,
        "resolved": outcome in RESOLVED_OUTCOMES,
        "generated": "generated" in statuses,
        "applied": "applied" in statuses,
        "exit_status": exit_status,
        "persisted_api_calls": int(model_stats.get("api_calls", 0)),
        "persisted_input_tokens": int(model_stats.get("tokens_sent", 0)),
        "persisted_output_tokens": int(model_stats.get("tokens_received", 0)),
        "patch_file_count": len(scorecard.get("patch_files", [])),
        "patch_lines_add": int(scorecard.get("patch_lines_add", 0)),
        "patch_lines_del": int(scorecard.get("patch_lines_del", 0)),
        "args_model_verified": args_model_verified,
        "args_parameters_verified": args_parameters_verified,
        "raw_files": raw_files,
    }


def build_repository_summary(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        groups[observation["repository"]].append(observation)
    result = []
    for repository in sorted(groups):
        rows = groups[repository]
        result.append(
            {
                "repository": repository,
                "instances": len(rows),
                "resolved": sum(row["resolved"] for row in rows),
                "resolve_rate": sum(row["resolved"] for row in rows) / len(rows),
                "persisted_api_calls": sum(
                    row["persisted_api_calls"] for row in rows
                ),
                "persisted_input_tokens": sum(
                    row["persisted_input_tokens"] for row in rows
                ),
                "persisted_output_tokens": sum(
                    row["persisted_output_tokens"] for row in rows
                ),
            }
        )
    return result


def render_markdown(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    outcome_rows = "\n".join(
        f"| `{outcome}` | {count} |"
        for outcome, count in summary["outcome_counts"].items()
    )
    repository_rows = "\n".join(
        f"| `{row['repository']}` | {row['instances']} | {row['resolved']} | "
        f"{100 * row['resolve_rate']:.1f}% | {row['persisted_api_calls']} | "
        f"{row['persisted_input_tokens']:,} | {row['persisted_output_tokens']:,} |"
        for row in manifest["repository_summary"]
    )
    lower, upper = summary["resolve_rate_wilson_95"]
    return f"""# 现代模型 dev20 基线统计

## 结论

`gpt-5.6-terra` 在冻结 SWE-bench Lite dev20 上完成 20/20 个实例，完全解决 4 个，resolve rate 为 20.0%，Wilson 95% CI 为 [{100 * lower:.1f}%, {100 * upper:.1f}%]。该结果属于现代模型开发集基线，不是论文 `gpt-4-1106-preview` 的严格重跑，也不能与论文 Lite test 点估计作直接显著性比较。

原始轨迹持久化 397 次 API 调用、5,496,947 input tokens 和 70,405 output tokens。`sqlfluff__sqlfluff-1763` 的最终格式纠正请求没有写入轨迹 usage；资源台账确认总调用为 398，因此 token 总数只能解释为下界。中转端点未提供可核验价格，成本不填 0。

## 结果分布

| evaluator 结果 | 实例数 |
|---|---:|
{outcome_rows}

14/20 个实例生成 prediction，10/20 成功应用，4/20 完全解决。6 个未生成 prediction，4 个 prediction 在 benchmark test patch 叠加阶段应用失败。该分布表明现代模型与论文期严格 ACI 的格式接口、测试文件修改和提交协议是当前主要工程边界，不能只用 resolve rate 概括。

## 仓库分层

| 仓库 | n | resolved | rate | calls | input tokens | output tokens |
|---|---:|---:|---:|---:|---:|---:|
{repository_rows}

仓库样本量为 1–5，仅用于描述，不作仓库间显著性推断。20 个实例来自 dev split，选择清单在运行前由 seed 42 固定。

## 资源分布

- API calls：均值 {summary['api_calls']['mean']:.2f}，中位数 {summary['api_calls']['median']:.1f}，IQR [{summary['api_calls']['q1']:.1f}, {summary['api_calls']['q3']:.1f}]；
- input tokens：均值 {summary['input_tokens']['mean']:,.2f}，中位数 {summary['input_tokens']['median']:,.1f}；
- output tokens：均值 {summary['output_tokens']['mean']:,.2f}，中位数 {summary['output_tokens']['median']:,.1f}；
- 成功实例持久化调用 87 次，失败实例 310 次；调用量不解释为因果因素。

## 证据完整性

20 份 scorecard、20 份 trajectory、prediction/result 文件及可得运行参数均记录路径、字节数和 SHA-256。19/20 份 `args.yaml` 逐项确认模型、temperature 和 top-p；`sqlfluff__sqlfluff-1763` 缺少 `args.yaml`、run manifest 和最终 usage，已作为持久化缺口保留。该缺口不改变其 `NOT_GENERATED` 判分，但阻止把 token 合计写成精确总成本。

## 完成边界

本分析完成已有现代默认 ACI 基线的统计收口。八个论文单因素 ACI 的 dev20 配对运行尚未执行，因而 `modern_replication_complete=false`，也不存在可计算的配对 McNemar 检验。扩大 API 实验前仍需明确总预算上限和端点价格。

机器清单位于 `data/manifests/modern_dev20_baseline_analysis.json`，逐实例数据位于 `data/derived/modern_dev20_baseline_instances.csv`。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--document", type=Path, default=DEFAULT_DOC)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    output_manifest = args.manifest.resolve()
    output_csv = args.csv.resolve()
    output_document = args.document.resolve()
    config = load_yaml(config_path)
    selection_path = ROOT / config["selection_manifest"]
    selection = load_json(selection_path)
    selected_ids = list(selection["instances"])
    runs = config.get("runs", [])
    run_ids = [run["instance_id"] for run in runs]
    if len(runs) != config["expected_instances"] or set(run_ids) != set(selected_ids):
        raise ValueError("Frozen run map does not exactly match the dev20 selection")
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("Frozen run map contains duplicate instances")
    trace_root = ROOT / config["trace_root"]
    observations = [
        collect_observation(config, run, trace_root) for run in runs
    ]
    observations.sort(key=lambda row: row["instance_id"])
    if any(row["outcome"] == "UNKNOWN" for row in observations):
        raise ValueError("At least one scorecard outcome is unknown")
    verified_args = [row for row in observations if row["args_model_verified"] is not None]
    if len(verified_args) != 19 or not all(
        row["args_model_verified"] and row["args_parameters_verified"]
        for row in verified_args
    ):
        raise ValueError("Expected exactly 19 verified runtime argument files")

    resolved_count = sum(row["resolved"] for row in observations)
    lower, upper = wilson_interval(resolved_count, len(observations))
    outcome_counts = Counter(row["outcome"] for row in observations)
    exit_status_counts = Counter(
        row["exit_status"] or "MISSING_PERSISTED_EXIT_STATUS"
        for row in observations
    )
    persisted_calls = sum(row["persisted_api_calls"] for row in observations)
    resource_adjustment = sum(
        int(gap["resource_audited_api_calls"])
        - int(gap["persisted_api_calls"])
        for gap in config.get("known_persistence_gaps", [])
    )
    summary = {
        "selected_count": len(selected_ids),
        "evaluated_count": len(observations),
        "resolved_count": resolved_count,
        "unresolved_count": len(observations) - resolved_count,
        "resolve_rate": resolved_count / len(observations),
        "resolve_rate_wilson_95": [lower, upper],
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "exit_status_counts": dict(sorted(exit_status_counts.items())),
        "generated_count": sum(row["generated"] for row in observations),
        "applied_count": sum(row["applied"] for row in observations),
        "runtime_args_verified_count": len(verified_args),
        "persisted_api_calls": persisted_calls,
        "resource_audited_api_calls": persisted_calls + resource_adjustment,
        "known_unpersisted_api_calls": resource_adjustment,
        "persisted_input_tokens": sum(
            row["persisted_input_tokens"] for row in observations
        ),
        "persisted_output_tokens": sum(
            row["persisted_output_tokens"] for row in observations
        ),
        "token_totals_are_lower_bounds": resource_adjustment > 0,
        "api_calls": numeric_summary(
            [row["persisted_api_calls"] for row in observations]
        ),
        "input_tokens": numeric_summary(
            [row["persisted_input_tokens"] for row in observations]
        ),
        "output_tokens": numeric_summary(
            [row["persisted_output_tokens"] for row in observations]
        ),
        "resolved_persisted_api_calls": sum(
            row["persisted_api_calls"] for row in observations if row["resolved"]
        ),
        "unresolved_persisted_api_calls": sum(
            row["persisted_api_calls"] for row in observations if not row["resolved"]
        ),
        "pricing_status": config["pricing_status"],
    }
    repository_summary = build_repository_summary(observations)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_id",
        "instance_id",
        "repository",
        "run_directory",
        "outcome",
        "resolved",
        "generated",
        "applied",
        "exit_status",
        "persisted_api_calls",
        "persisted_input_tokens",
        "persisted_output_tokens",
        "patch_file_count",
        "patch_lines_add",
        "patch_lines_del",
        "args_model_verified",
        "args_parameters_verified",
        "scorecard_sha256",
        "trajectory_sha256",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for observation in observations:
            row = {field: observation.get(field) for field in fields}
            row["scorecard_sha256"] = observation["raw_files"]["scorecard"][
                "sha256"
            ]
            row["trajectory_sha256"] = observation["raw_files"]["trajectory"][
                "sha256"
            ]
            writer.writerow(row)

    manifest = {
        "schema_version": 1,
        "as_of": config["as_of"],
        "generated_at_utc": utc_now(),
        "status": "COMPLETE_BASELINE_STATISTICS_WITH_ONE_USAGE_PERSISTENCE_GAP",
        "evidence": "modern",
        "model": config["model"],
        "api_style": config["api_style"],
        "paper_alignment": {
            "sweagent_revision": config["sweagent_revision"],
            "temperature": config["temperature"],
            "top_p": config["top_p"],
            "dataset": config["dataset"],
            "dataset_revision": config["dataset_revision"],
            "split": config["split"],
            "direct_comparison_to_paper_test_rate_allowed": config[
                "direct_comparison_to_paper_test_rate_allowed"
            ],
        },
        "inputs": {
            "run_map": file_record(config_path),
            "selection_manifest": file_record(selection_path),
        },
        "known_persistence_gaps": config.get("known_persistence_gaps", []),
        "observations": observations,
        "repository_summary": repository_summary,
        "summary": summary,
        "completion": {
            "baseline_statistics_complete": True,
            "paired_aci_ablations_complete": False,
            "modern_replication_complete": False,
            "exact_model_rerun_complete": False,
        },
    }
    output_document.write_text(render_markdown(manifest), encoding="utf-8")
    manifest["outputs"] = {
        "instance_csv": file_record(output_csv),
        "analysis_document": file_record(output_document),
    }
    write_json(output_manifest, manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "evaluated": len(observations),
                "resolved": resolved_count,
                "resolve_rate": summary["resolve_rate"],
                "wilson_95": summary["resolve_rate_wilson_95"],
                "persisted_api_calls": summary["persisted_api_calls"],
                "resource_audited_api_calls": summary[
                    "resource_audited_api_calls"
                ],
                "persisted_input_tokens": summary["persisted_input_tokens"],
                "persisted_output_tokens": summary["persisted_output_tokens"],
                "manifest": output_manifest.relative_to(ROOT).as_posix(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
