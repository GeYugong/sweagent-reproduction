#!/usr/bin/env python3
"""Reproduce HumanEvalFix pass rates and resolved-turn data from official artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OFFICIAL_REVISION = "bbd565c9035f873ba5ee2c1bd1d65c5ee2d85d1a"
PASS_MARKER = ">>>>> All Tests Passed"


@dataclass(frozen=True)
class LanguageRun:
    language: str
    run: str
    expected_passes: int
    expected_eval_logs: int
    expected_all_logs: int


RUNS = (
    LanguageRun("python", "gpt4-turbo__swe-bench-HumanEvalFix-python__default__t-0.00__p-0.95__c-4.00__install-1", 143, 162, 163),
    LanguageRun("js", "gpt4-turbo__swe-bench-HumanEvalFix-js__default__t-0.00__p-0.95__c-4.00__install-0", 148, 164, 165),
    LanguageRun("java", "gpt4-turbo__swe-bench-HumanEvalFix-java__default__t-0.00__p-0.95__c-4.00__install-0", 145, 164, 165),
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
    return proc.stdout.decode("utf-8", errors="strict") if text else proc.stdout


def git_blob(repo: Path, revision: str, path: str) -> bytes:
    return git(repo, "show", f"{revision}:{path}")  # type: ignore[return-value]


def git_blobs(repo: Path, blob_shas: list[str]) -> dict[str, bytes]:
    """Read many blobs through one ``git cat-file --batch`` process."""
    unique_shas = list(dict.fromkeys(blob_shas))
    proc = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        input=("\n".join(unique_shas) + "\n").encode("ascii"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git cat-file --batch failed: {message}")
    payload = proc.stdout
    cursor = 0
    blobs: dict[str, bytes] = {}
    for expected_sha in unique_shas:
        header_end = payload.index(b"\n", cursor)
        header = payload[cursor:header_end].decode("ascii")
        cursor = header_end + 1
        object_sha, object_type, size_text = header.split()
        if object_sha != expected_sha or object_type != "blob":
            raise RuntimeError(f"unexpected cat-file header: {header}")
        size = int(size_text)
        blobs[expected_sha] = payload[cursor : cursor + size]
        cursor += size
        if payload[cursor : cursor + 1] != b"\n":
            raise RuntimeError(f"missing batch separator after {expected_sha}")
        cursor += 1
    return blobs


def tree_blobs(repo: Path, revision: str, prefix: str, suffix: str) -> list[tuple[str, str]]:
    raw = str(git(repo, "ls-tree", "-r", revision, "--", prefix, text=True))
    rows: list[tuple[str, str]] = []
    pattern = re.compile(r"^\d+ blob ([0-9a-f]+)\t(.+)$")
    for line in raw.splitlines():
        match = pattern.match(line)
        if match and match.group(2).endswith(suffix):
            rows.append((match.group(2), match.group(1)))
    return rows


def normalize_instance_id(value: str) -> str:
    return value.removeprefix("swe-bench__")


def file_instance_id(path: str) -> str:
    return normalize_instance_id(Path(path).name.split(".", 1)[0])


def config_value(args_yaml: str, field: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(field)}:\s*(.+?)\s*$", args_yaml, flags=re.MULTILINE)
    return match.group(1) if match else None


def summarize_language(repo: Path, revision: str, spec: LanguageRun) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    log_prefix = f"logs/{spec.run}"
    traj_prefix = f"trajs/{spec.run}"
    all_logs = tree_blobs(repo, revision, log_prefix, ".log")
    logs = [(path, blob_sha) for path, blob_sha in all_logs if path.endswith(".eval.log")]
    testbed_logs = [(path, blob_sha) for path, blob_sha in all_logs if not path.endswith(".eval.log")]
    trajectories = tree_blobs(repo, revision, traj_prefix, ".traj")
    if (
        len(logs) != spec.expected_eval_logs
        or len(all_logs) != spec.expected_all_logs
        or len(trajectories) != 164
    ):
        raise AssertionError(
            f"{spec.language}: expected {spec.expected_eval_logs} eval logs, "
            f"{spec.expected_all_logs} total logs, and 164 trajectories; found "
            f"{len(logs)}, {len(all_logs)}, and {len(trajectories)}"
        )

    blob_data = git_blobs(repo, [blob_sha for _, blob_sha in all_logs + trajectories])
    log_rows: dict[str, dict[str, Any]] = {}
    for path, blob_sha in logs:
        content = blob_data[blob_sha].decode("utf-8", errors="replace")
        instance_id = file_instance_id(path)
        log_rows[instance_id] = {
            "resolved": PASS_MARKER in content,
            "log_path": path,
            "log_blob_sha": blob_sha,
        }

    traj_rows: dict[str, dict[str, Any]] = {}
    for path, blob_sha in trajectories:
        payload = json.loads(blob_data[blob_sha])
        instance_id = file_instance_id(path)
        traj_rows[instance_id] = {
            "turns": len(payload["trajectory"]),
            "trajectory_path": path,
            "trajectory_blob_sha": blob_sha,
        }

    missing_eval_logs = sorted(set(traj_rows) - set(log_rows))
    unexpected_eval_logs = sorted(set(log_rows) - set(traj_rows))
    if unexpected_eval_logs:
        raise AssertionError(f"{spec.language}: evaluation logs without trajectories={unexpected_eval_logs}")

    instance_rows: list[dict[str, Any]] = []
    resolved_turns: list[int] = []
    for instance_id in sorted(traj_rows):
        eval_log_present = instance_id in log_rows
        resolved = bool(log_rows.get(instance_id, {}).get("resolved", False))
        turns = int(traj_rows[instance_id]["turns"])
        if resolved:
            resolved_turns.append(turns)
        instance_rows.append(
            {
                "language": spec.language,
                "instance_id": instance_id,
                "eval_log_present": eval_log_present,
                "resolved": resolved,
                "turns": turns,
                "resolved_turns": turns if resolved else "",
                "log_blob_sha": log_rows.get(instance_id, {}).get("log_blob_sha", ""),
                "trajectory_blob_sha": traj_rows[instance_id]["trajectory_blob_sha"],
            }
        )

    passes = sum(row["resolved"] for row in instance_rows)
    if passes != spec.expected_passes:
        raise AssertionError(f"{spec.language}: expected {spec.expected_passes} passes, found {passes}")

    args_path = f"{traj_prefix}/args.yaml"
    predictions_path = f"{traj_prefix}/all_preds.jsonl"
    args_blob = git_blob(repo, revision, args_path)
    predictions_blob = git_blob(repo, revision, predictions_path)
    args_text = args_blob.decode("utf-8", errors="strict")
    notebook_denominator = len(all_logs)
    corrected_denominator = len(instance_rows)
    summary = {
        "language": spec.language,
        "run": spec.run,
        "passes": passes,
        "paper_notebook_reproduction": {
            "denominator_all_log_files": notebook_denominator,
            "failures_by_notebook_definition": notebook_denominator - passes,
            "percent": passes * 100.0 / notebook_denominator,
            "rounded_1": round(passes * 100.0 / notebook_denominator, 1),
            "glob": "*.log",
            "includes_testbed_log_as_failure": len(testbed_logs) > 0,
        },
        "benchmark_corrected": {
            "denominator_instances": corrected_denominator,
            "unresolved_instances": corrected_denominator - passes,
            "percent": passes * 100.0 / corrected_denominator,
            "rounded_1": round(passes * 100.0 / corrected_denominator, 1),
            "policy": "Use the declared 164 tasks; instances with missing evaluation logs remain unresolved/unevaluated.",
        },
        "resolved_turns": {
            "count": len(resolved_turns),
            "min": min(resolved_turns),
            "max": max(resolved_turns),
            "mean": statistics.fmean(resolved_turns),
            "median": statistics.median(resolved_turns),
        },
        "configuration": {
            "model_alias": config_value(args_text, "model_name"),
            "temperature": config_value(args_text, "temperature"),
            "top_p": config_value(args_text, "top_p"),
            "per_instance_cost_limit": config_value(args_text, "per_instance_cost_limit"),
            "install_variant": spec.run.rsplit("__", 1)[-1],
            "args_path": args_path,
            "args_sha256": hashlib.sha256(args_blob).hexdigest(),
        },
        "predictions": {
            "path": predictions_path,
            "sha256": hashlib.sha256(predictions_blob).hexdigest(),
            "nonempty_lines": sum(bool(line.strip()) for line in predictions_blob.decode("utf-8").splitlines()),
        },
        "evaluation_log_count": len(logs),
        "testbed_log_count": len(testbed_logs),
        "all_log_file_count": len(all_logs),
        "missing_evaluation_log_instance_ids": missing_eval_logs,
        "trajectory_count": len(trajectories),
    }
    return summary, instance_rows


def write_instance_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "language",
        "instance_id",
        "eval_log_present",
        "resolved",
        "turns",
        "resolved_turns",
        "log_blob_sha",
        "trajectory_blob_sha",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "language",
        "passes",
        "paper_notebook_denominator",
        "paper_notebook_percent",
        "paper_notebook_rounded_1",
        "corrected_denominator",
        "corrected_percent",
        "corrected_rounded_1",
        "evaluation_logs",
        "testbed_logs",
        "missing_evaluation_logs",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "language": row["language"],
                    "passes": row["passes"],
                    "paper_notebook_denominator": row["paper_notebook_reproduction"]["denominator_all_log_files"],
                    "paper_notebook_percent": f'{row["paper_notebook_reproduction"]["percent"]:.8f}',
                    "paper_notebook_rounded_1": f'{row["paper_notebook_reproduction"]["rounded_1"]:.1f}',
                    "corrected_denominator": row["benchmark_corrected"]["denominator_instances"],
                    "corrected_percent": f'{row["benchmark_corrected"]["percent"]:.8f}',
                    "corrected_rounded_1": f'{row["benchmark_corrected"]["rounded_1"]:.1f}',
                    "evaluation_logs": row["evaluation_log_count"],
                    "testbed_logs": row["testbed_log_count"],
                    "missing_evaluation_logs": ";".join(row["missing_evaluation_log_instance_ids"]),
                }
            )


def write_histogram_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    edges = list(range(0, 40, 2))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("language", "bin_left", "bin_right", "count"))
        writer.writeheader()
        for language in ("js", "java", "python"):
            turns = [int(row["turns"]) for row in rows if row["language"] == language and row["resolved"]]
            for left, right in zip(edges[:-1], edges[1:]):
                count = sum(left <= value < right for value in turns)
                if right == edges[-1]:
                    count = sum(left <= value <= right for value in turns)
                writer.writerow({"language": language, "bin_left": left, "bin_right": right, "count": count})


def make_figure(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("--figure requires matplotlib and numpy") from exc

    order = ("js", "java", "python")
    colors = ("#a30025", "#ff661f", "#479300")
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for axis, language, color in zip(axes, order, colors):
        turns = [int(row["turns"]) for row in rows if row["language"] == language and row["resolved"]]
        axis.hist(turns, bins=np.arange(0, 40, 2), color=color, edgecolor="black")
        axis.set_title(f"HumanEvalFix-{language}", fontsize=24)
        axis.set_xlabel("Turn", fontsize=21)
        axis.set_ylabel("Frequency", fontsize=21)
        axis.tick_params(axis="x", labelsize=15)
        axis.tick_params(axis="y", labelsize=15)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fixed_timestamp = datetime(2024, 7, 11, 15, 23, 43, tzinfo=timezone.utc)
    fig.savefig(
        path,
        bbox_inches="tight",
        facecolor="white",
        transparent=False,
        metadata={
            "Creator": "SWE-agent artifact reproduction",
            "CreationDate": fixed_timestamp,
            "ModDate": fixed_timestamp,
        },
    )
    plt.close(fig)
    figure_blob = path.read_bytes()
    return {
        "bytes": len(figure_blob),
        "sha256": hashlib.sha256(figure_blob).hexdigest(),
        "matplotlib_version": plt.matplotlib.__version__,
        "numpy_version": np.__version__,
        "bins": "numpy.arange(0, 40, 2)",
        "language_order": list(order),
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=project_root / "code" / "humanevalfix-results")
    parser.add_argument("--revision", default=OFFICIAL_REVISION)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=project_root / "data" / "manifests" / "official_humanevalfix_artifacts.json",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=project_root / "data" / "derived" / "humanevalfix_instance_results.csv",
    )
    parser.add_argument(
        "--output-summary-csv",
        type=Path,
        default=project_root / "data" / "derived" / "humanevalfix_summary.csv",
    )
    parser.add_argument(
        "--output-histogram-csv",
        type=Path,
        default=project_root / "data" / "derived" / "humanevalfix_histogram_bins.csv",
    )
    parser.add_argument("--figure", type=Path, default=None)
    args = parser.parse_args()

    repo = args.repo.resolve()
    try:
        repo_display = repo.relative_to(project_root).as_posix()
    except ValueError:
        repo_display = str(repo)
    revision = str(git(repo, "rev-parse", args.revision, text=True)).strip()
    summaries: list[dict[str, Any]] = []
    instance_rows: list[dict[str, Any]] = []
    for spec in RUNS:
        summary, rows = summarize_language(repo, revision, spec)
        summaries.append(summary)
        instance_rows.extend(rows)

    figure_metadata = None
    if args.figure is not None:
        figure_metadata = make_figure(args.figure, instance_rows)
        try:
            figure_path = args.figure.resolve().relative_to(project_root).as_posix()
        except ValueError:
            figure_path = str(args.figure.resolve())
        figure_metadata["path"] = figure_path

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "repository": "https://github.com/SWE-agent/humanevalfix-results",
            "local_path": repo_display,
            "revision": revision,
            "notebook": "view_results.ipynb",
            "pass_marker": PASS_MARKER,
        },
        "language_resolution": {
            "paper_main_table": ["python", "js", "java"],
            "paper_appendix_typo": "go",
            "official_run_directories": [summary["language"] for summary in summaries],
            "conclusion": "The executed third language was Java; the appendix reference to Go is inconsistent with the released artifacts.",
        },
        "metric_audit": {
            "notebook_behavior": "The released notebook globs every *.log file, so one testbed environment log per language is counted as a failed task.",
            "python_release_gap": "The Git release contains 162 Python evaluation logs for 164 trajectories; the missing instance IDs are recorded per run.",
            "reporting_policy": "Report the paper/notebook metric and the fixed 164-instance metric side by side.",
        },
        "figure": figure_metadata,
        "runs": summaries,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_instance_csv(args.output_csv, instance_rows)
    write_summary_csv(args.output_summary_csv, summaries)
    write_histogram_csv(args.output_histogram_csv, instance_rows)

    for summary in summaries:
        print(
            f'{summary["language"]}: paper={summary["passes"]}/'
            f'{summary["paper_notebook_reproduction"]["denominator_all_log_files"]} '
            f'({summary["paper_notebook_reproduction"]["percent"]:.5f}%), '
            f'corrected={summary["passes"]}/'
            f'{summary["benchmark_corrected"]["denominator_instances"]} '
            f'({summary["benchmark_corrected"]["percent"]:.5f}%), '
            f'resolved_turns={summary["resolved_turns"]["count"]}'
        )
    print(f"manifest={args.output_json}")
    print(f"csv={args.output_csv}")
    print(f"summary_csv={args.output_summary_csv}")
    print(f"histogram_csv={args.output_histogram_csv}")
    if args.figure is not None:
        print(f"figure={args.figure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
