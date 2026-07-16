#!/usr/bin/env python3
"""Summarize completed SWE-bench dev20 evaluations from local artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RESOLVED_STATUSES = {"RESOLVED_FULL"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_trajectory(run_dir: Path, instance_id: str) -> Path | None:
    preferred = run_dir / f"{instance_id}.traj"
    if preferred.is_file():
        return preferred
    candidates = sorted(run_dir.glob("*.traj"))
    return candidates[0] if len(candidates) == 1 else None


def collect_runs(trace_root: Path, selected: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for scorecard_path in sorted(trace_root.glob("*/scorecards.json")):
        run_dir = scorecard_path.parent
        scorecards = load_json(scorecard_path)
        if not isinstance(scorecards, list):
            raise ValueError(f"Expected a list in {scorecard_path}")
        for scorecard in scorecards:
            instance_id = scorecard.get("instance_id")
            if instance_id not in selected:
                continue
            if instance_id in seen:
                raise ValueError(
                    f"Duplicate evaluated instance {instance_id}: {scorecard_path}"
                )
            seen.add(instance_id)
            statuses = list(scorecard.get("statuses", []))
            outcome = next(
                (status for status in reversed(statuses) if status.startswith("RESOLVED_")),
                "UNKNOWN",
            )
            if outcome == "UNKNOWN":
                if "not_generated" in statuses:
                    outcome = "NOT_GENERATED"
                elif "generated" in statuses and "applied" not in statuses:
                    outcome = "PATCH_APPLY_FAILED"
            trajectory_path = find_trajectory(run_dir, instance_id)
            model_stats: dict[str, Any] = {}
            if trajectory_path is not None:
                trajectory = load_json(trajectory_path)
                model_stats = trajectory.get("info", {}).get("model_stats", {})
            records.append(
                {
                    "instance_id": instance_id,
                    "run_directory": run_dir.name,
                    "outcome": outcome,
                    "resolved": outcome in RESOLVED_STATUSES,
                    "api_calls": int(model_stats.get("api_calls", 0)),
                    "input_tokens": int(model_stats.get("tokens_sent", 0)),
                    "output_tokens": int(model_stats.get("tokens_received", 0)),
                    "patch_files": scorecard.get("patch_files", []),
                    "patch_lines_add": int(scorecard.get("patch_lines_add", 0)),
                    "patch_lines_del": int(scorecard.get("patch_lines_del", 0)),
                }
            )
    return sorted(records, key=lambda item: item["instance_id"])


def build_summary(manifest: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    selected = list(manifest["instances"])
    evaluated_ids = {record["instance_id"] for record in records}
    resolved = sum(record["resolved"] for record in records)
    evaluated = len(records)
    return {
        "dataset": manifest["dataset"],
        "dataset_revision": manifest["dataset_revision"],
        "split": manifest["split"],
        "selection_seed": manifest["selection"]["seed"],
        "selected_count": len(selected),
        "evaluated_count": evaluated,
        "remaining_count": len(selected) - evaluated,
        "resolved_count": resolved,
        "unresolved_count": evaluated - resolved,
        "resolve_rate": resolved / evaluated if evaluated else None,
        "api_calls": sum(record["api_calls"] for record in records),
        "input_tokens": sum(record["input_tokens"] for record in records),
        "output_tokens": sum(record["output_tokens"] for record in records),
        "remaining_instances": [item for item in selected if item not in evaluated_ids],
        "runs": records,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    rate = summary["resolve_rate"]
    rate_text = "n/a" if rate is None else f"{100 * rate:.1f}%"
    lines = [
        "# SWE-bench Lite dev20 自动汇总",
        "",
        f"- 数据集 revision：`{summary['dataset_revision']}`",
        f"- 已评测：{summary['evaluated_count']}/{summary['selected_count']}",
        f"- resolved：{summary['resolved_count']}",
        f"- 当前 resolve rate：{rate_text}",
        f"- API 调用：{summary['api_calls']}",
        f"- 输入 token：{summary['input_tokens']:,}",
        f"- 输出 token：{summary['output_tokens']:,}",
        "",
        "| instance | result | calls | input tokens | output tokens |",
        "|---|---|---:|---:|---:|",
    ]
    for record in summary["runs"]:
        lines.append(
            f"| `{record['instance_id']}` | {record['outcome']} | "
            f"{record['api_calls']} | {record['input_tokens']:,} | "
            f"{record['output_tokens']:,} |"
        )
    lines.extend(["", "## 待评测实例", ""])
    lines.extend(f"- `{item}`" for item in summary["remaining_instances"])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_json(args.manifest)
    selected = set(manifest["instances"])
    records = collect_runs(args.trace_root, selected)
    summary = build_summary(manifest, records)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
