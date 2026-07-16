#!/usr/bin/env python3
"""Recompute the paper's main SWE-bench rows from official Git artifacts.

The SWE-bench experiments repository reset its public main-branch history in
October 2024.  The pre-reset commit used here is still available from the
official GitHub repository and contains predictions, evaluation logs,
trajectories, and generated ``results.json`` files.  This script reads blobs
directly from that commit, so the large historical tree does not need to be
checked out on Windows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OFFICIAL_REVISION = "a5d52722965c791c0c04d18135f906b44f716d39"


@dataclass(frozen=True)
class RunSpec:
    split: str
    run: str
    system: str
    model: str
    denominator: int
    paper_main_percent: float
    paper_main_implied_count: int
    paper_exit_count: int | None
    official_artifact_count: int

    @property
    def path(self) -> str:
        return f"evaluation/{self.split}/{self.run}"


RUNS = (
    RunSpec("lite", "20240402_sweagent_gpt4", "SWE-agent", "gpt-4-1106-preview", 300, 18.00, 54, 54, 54),
    RunSpec("lite", "20240402_sweagent_claude3opus", "SWE-agent", "claude-3-opus-20240229", 300, 13.00, 39, 35, 35),
    RunSpec("lite", "20240402_rag_gpt4", "RAG", "gpt-4-1106-preview", 300, 2.67, 8, None, 8),
    RunSpec("lite", "20240402_rag_claude3opus", "RAG", "claude-3-opus-20240229", 300, 4.33, 13, None, 13),
    RunSpec("test", "20240402_sweagent_gpt4", "SWE-agent", "gpt-4-1106-preview", 2294, 12.47, 286, 286, 286),
    RunSpec("test", "20240402_sweagent_claude3opus", "SWE-agent", "claude-3-opus-20240229", 2294, 10.46, 240, 241, 241),
    RunSpec("test", "20240402_rag_gpt4", "RAG", "gpt-4-1106-preview", 2294, 1.31, 30, None, 30),
    RunSpec("test", "20240402_rag_claude3opus", "RAG", "claude-3-opus-20240229", 2294, 3.79, 87, None, 87),
)


def git(repo: Path, *args: str, text: bool = False) -> bytes | str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {message}")
    if text:
        return proc.stdout.decode("utf-8", errors="strict")
    return proc.stdout


def git_blob(repo: Path, revision: str, path: str) -> bytes:
    return git(repo, "show", f"{revision}:{path}")  # type: ignore[return-value]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(repo: Path, revision: str, prefix: str) -> dict[str, Any]:
    raw = git(repo, "ls-tree", "-r", "-l", revision, "--", prefix, text=True)
    pattern = re.compile(r"^\d+ blob ([0-9a-f]+)\s+(\d+)\t(.+)$")
    rows: list[tuple[str, int, str]] = []
    for line in str(raw).splitlines():
        match = pattern.match(line)
        if match:
            rows.append((match.group(3), int(match.group(2)), match.group(1)))
    return {
        "file_count": len(rows),
        "total_bytes": sum(size for _, size, _ in rows),
        "log_count": sum("/logs/" in path for path, _, _ in rows),
        "trajectory_count": sum("/trajs/" in path for path, _, _ in rows),
        "prediction_file_count": sum(path.endswith("/all_preds.jsonl") for path, _, _ in rows),
        "results_file_count": sum(path.endswith("/results/results.json") for path, _, _ in rows),
    }


def parse_predictions(data: bytes) -> dict[str, Any]:
    instance_ids: list[str] = []
    line_count = 0
    null_or_empty = 0
    malformed = 0
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        line_count += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        instance_id = row.get("instance_id")
        if isinstance(instance_id, str):
            instance_ids.append(instance_id)
        patch = row.get("model_patch")
        if patch is None or (isinstance(patch, str) and not patch.strip()):
            null_or_empty += 1
    return {
        "line_count": line_count,
        "unique_instance_count": len(set(instance_ids)),
        "duplicate_instance_count": len(instance_ids) - len(set(instance_ids)),
        "null_or_empty_patch_count": null_or_empty,
        "malformed_line_count": malformed,
    }


def summarize_run(repo: Path, revision: str, spec: RunSpec) -> dict[str, Any]:
    results_path = f"{spec.path}/results/results.json"
    predictions_path = f"{spec.path}/all_preds.jsonl"
    results_blob = git_blob(repo, revision, results_path)
    predictions_blob = git_blob(repo, revision, predictions_path)
    results = json.loads(results_blob)
    resolved = results.get("resolved", [])
    resolved_count = len(resolved)
    resolved_unique_count = len(set(resolved))
    if resolved_count != spec.official_artifact_count:
        raise AssertionError(
            f"{spec.path}: expected {spec.official_artifact_count} official resolved entries, "
            f"found {resolved_count}"
        )
    artifact_percent = resolved_count * 100.0 / spec.denominator
    category_counts = {
        key: {
            "entries": len(value),
            "unique_instances": len(set(value)),
        }
        for key, value in results.items()
        if isinstance(value, list)
    }
    return {
        "split": spec.split,
        "run": spec.run,
        "path": spec.path,
        "system": spec.system,
        "model": spec.model,
        "denominator": spec.denominator,
        "official_artifact": {
            "resolved_entries": resolved_count,
            "resolved_unique_instances": resolved_unique_count,
            "percent": artifact_percent,
            "percent_rounded_2": round(artifact_percent, 2),
        },
        "paper_main_table": {
            "percent": spec.paper_main_percent,
            "implied_count": spec.paper_main_implied_count,
            "count_delta_from_artifact": resolved_count - spec.paper_main_implied_count,
            "matches_artifact_after_2dp_rounding": round(artifact_percent, 2) == spec.paper_main_percent,
        },
        "paper_exit_condition_table": {
            "resolved_count": spec.paper_exit_count,
            "matches_artifact": spec.paper_exit_count == resolved_count if spec.paper_exit_count is not None else None,
        },
        "results_categories": category_counts,
        "predictions": {
            **parse_predictions(predictions_blob),
            "path": predictions_path,
            "bytes": len(predictions_blob),
            "sha256": sha256(predictions_blob),
        },
        "results_file": {
            "path": results_path,
            "bytes": len(results_blob),
            "sha256": sha256(results_blob),
        },
        "tree_inventory": inventory(repo, revision, spec.path),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "split",
        "run",
        "system",
        "model",
        "denominator",
        "artifact_resolved",
        "artifact_percent",
        "paper_main_implied_count",
        "paper_main_percent",
        "count_delta",
        "paper_main_match",
        "paper_exit_count",
        "paper_exit_match",
        "prediction_instances",
        "logs",
        "trajectories",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "split": row["split"],
                    "run": row["run"],
                    "system": row["system"],
                    "model": row["model"],
                    "denominator": row["denominator"],
                    "artifact_resolved": row["official_artifact"]["resolved_entries"],
                    "artifact_percent": f'{row["official_artifact"]["percent"]:.8f}',
                    "paper_main_implied_count": row["paper_main_table"]["implied_count"],
                    "paper_main_percent": f'{row["paper_main_table"]["percent"]:.2f}',
                    "count_delta": row["paper_main_table"]["count_delta_from_artifact"],
                    "paper_main_match": row["paper_main_table"]["matches_artifact_after_2dp_rounding"],
                    "paper_exit_count": row["paper_exit_condition_table"]["resolved_count"],
                    "paper_exit_match": row["paper_exit_condition_table"]["matches_artifact"],
                    "prediction_instances": row["predictions"]["unique_instance_count"],
                    "logs": row["tree_inventory"]["log_count"],
                    "trajectories": row["tree_inventory"]["trajectory_count"],
                }
            )


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=project_root / "code" / "SWE-bench-experiments")
    parser.add_argument("--revision", default=OFFICIAL_REVISION)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=project_root / "data" / "manifests" / "official_swebench_artifacts.json",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=project_root / "data" / "derived" / "official_swebench_main_results.csv",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    try:
        repo_display = repo.relative_to(project_root).as_posix()
    except ValueError:
        repo_display = str(repo)
    revision = str(git(repo, "rev-parse", args.revision, text=True)).strip()
    commit_meta = str(git(repo, "show", "-s", "--format=%aI%x00%cI%x00%s", revision, text=True)).strip().split("\x00")
    rows = [summarize_run(repo, revision, spec) for spec in RUNS]
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "repository": "https://github.com/SWE-bench/experiments",
            "local_path": repo_display,
            "revision": revision,
            "author_date": commit_meta[0],
            "commit_date": commit_meta[1],
            "subject": commit_meta[2],
            "access_method": "git blobs from pre-reset official history",
        },
        "interpretation": {
            "paper_main_table_mismatches": [
                "Claude 3 Opus Lite: paper main table says 13.00% (39/300 implied), official artifacts and paper exit table contain 35/300.",
                "Claude 3 Opus Full: paper main table says 10.46% (240/2294 implied), official artifacts and paper exit table contain 241/2294.",
            ],
            "mismatch_policy": "Preserve both published table values and artifact-recomputed values; do not overwrite either.",
        },
        "runs": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(args.output_csv, rows)

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(("split", "run", "artifact", "paper", "delta", "match"))
    for row in rows:
        writer.writerow(
            (
                row["split"],
                row["run"],
                f'{row["official_artifact"]["resolved_entries"]}/{row["denominator"]}',
                f'{row["paper_main_table"]["implied_count"]}/{row["denominator"]}',
                row["paper_main_table"]["count_delta_from_artifact"],
                row["paper_main_table"]["matches_artifact_after_2dp_rounding"],
            )
        )
    print(stream.getvalue().strip())
    print(f"manifest={args.output_json}")
    print(f"csv={args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
