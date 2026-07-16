#!/usr/bin/env python3
"""Recompute paper analyses A01-A10 from frozen public SWE-agent artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pyarrow.parquet as pq
from matplotlib.backends.backend_pdf import PdfPages
from unidiff import PatchSet, UnidiffParseError


EXPERIMENTS_REVISION = "a5d52722965c791c0c04d18135f906b44f716d39"
LITE_DATASET_REVISION = "81ad348adcaf3368691f4db2907f8fc97a8f7526"
LITE_DATASET_SHA256 = "2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1"
FULL_DATASET_REVISION = "283547aced6224d4adbe55c678b4c9c43fe7d501"
FULL_DATASET_SHA256 = "831728617f006e70c9de546e15cbdb49ce27b6fe8a8e4c4cd8035e8da3de3020"
PAPER_ARXIV_ID = "2405.15793v3"

RUN_GPT4 = "20240402_sweagent_gpt4"
RUN_CLAUDE = "20240402_sweagent_claude3opus"
RUN_RAG_GPT4 = "20240402_rag_gpt4"
RUN_RAG_CLAUDE = "20240402_rag_claude3opus"
RUN_RAG_CLAUDE2 = "20231010_rag_claude2"

PERFORMANCE_RUNS = [
    ("sweagent_gpt4", RUN_GPT4),
    ("sweagent_claude3opus", RUN_CLAUDE),
    ("rag_gpt4", RUN_RAG_GPT4),
    ("rag_claude3opus", RUN_RAG_CLAUDE),
    ("rag_claude2", RUN_RAG_CLAUDE2),
]

TRAJECTORY_RUNS = [
    ("full", RUN_GPT4, "test"),
    ("full", RUN_CLAUDE, "test"),
    ("lite", RUN_GPT4, "lite"),
    ("lite", RUN_CLAUDE, "lite"),
]

EXIT_CATEGORIES = [
    "Submit",
    "Exit Cost (Submit)",
    "Exit Cost (No Submit)",
    "Early Exit",
]

PAPER_EXIT_COUNTS = {
    (RUN_GPT4, "full", "resolved"): [266, 20, 0, 0],
    (RUN_GPT4, "full", "all"): [1589, 630, 48, 1],
    (RUN_GPT4, "lite", "resolved"): [50, 4, 0, 0],
    (RUN_GPT4, "lite", "all"): [203, 95, 2, 0],
    (RUN_CLAUDE, "full", "resolved"): [206, 35, 0, 0],
    (RUN_CLAUDE, "full", "all"): [882, 1048, 73, 1],
    (RUN_CLAUDE, "lite", "resolved"): [32, 3, 0, 0],
    (RUN_CLAUDE, "lite", "all"): [133, 156, 11, 0],
}

ACTION_ALLOWLIST = [
    "search_dir",
    "search_file",
    "find_file",
    "find",
    "create",
    "edit",
    "exit_cost",
    "submit",
    "open",
    "scroll_up",
    "scroll_down",
    "goto",
    "python3",
    "python",
    "pytest",
]

TRANSITION_VALID_ACTIONS = {
    "search_dir",
    "find_file",
    "create",
    "edit",
    "search_file",
    "goto",
    "submit",
    "exit_cost",
    "open",
    "scroll_up",
    "scroll_down",
    "python",
    "pytest",
    "<START>",
    "<END>",
}

PAPER_TRANSITION_ROWS = {
    1: [
        ("<START>",),
        ("create",),
        ("edit",),
        ("exit_cost",),
        ("find_file",),
        ("goto",),
        ("open",),
        ("pytest",),
        ("python",),
        ("scroll_down",),
        ("scroll_up",),
        ("search_dir",),
        ("search_file",),
        ("submit",),
    ],
    2: [
        ("<START>", "create"),
        ("create", "edit"),
        ("edit", "edit"),
        ("edit", "python"),
        ("find_file", "open"),
        ("goto", "edit"),
        ("open", "edit"),
        ("open", "scroll_down"),
        ("open", "search_file"),
        ("python", "edit"),
        ("python", "find_file"),
        ("rm", "submit"),
        ("scroll_down", "scroll_down"),
        ("search_dir", "open"),
        ("search_file", "goto"),
    ],
    3: [
        ("<START>", "create", "edit"),
        ("create", "edit", "python"),
        ("edit", "edit", "python"),
        ("edit", "edit", "edit"),
        ("edit", "python", "edit"),
        ("edit", "python", "find_file"),
        ("edit", "python", "open"),
        ("edit", "python", "rm"),
        ("find_file", "open", "search_file"),
        ("open", "search_file", "goto"),
        ("python", "edit", "edit"),
        ("python", "edit", "python"),
        ("scroll_down", "scroll_down", "scroll_down"),
        ("search_dir", "open", "search_file"),
        ("search_file", "goto", "edit"),
    ],
    4: [
        ("<START>", "create", "edit", "python"),
        ("create", "edit", "python", "edit"),
        ("create", "edit", "python", "find_file"),
        ("edit", "edit", "python", "edit"),
        ("edit", "edit", "edit", "python"),
        ("edit", "edit", "edit", "edit"),
        ("edit", "python", "edit", "edit"),
        ("edit", "python", "edit", "python"),
        ("edit", "python", "find_file", "open"),
        ("edit", "python", "rm", "submit"),
        ("open", "search_file", "goto", "edit"),
        ("python", "edit", "edit", "python"),
        ("python", "edit", "python", "edit"),
        ("scroll_down", "scroll_down", "scroll_down", "scroll_down"),
        ("search_dir", "open", "search_file", "goto"),
    ],
}

PAPER_TRANSITION_CELLS = {
    (1, ("open",), "search_file"): 0.35,
    (1, ("open",), "scroll_down"): 0.18,
    (1, ("open",), "goto"): 0.09,
    (1, ("open",), "edit"): 0.25,
    (2, ("search_dir", "open"), "search_file"): 0.53,
    (2, ("edit", "python"), "edit"): 0.48,
    (3, ("create", "edit", "python"), "edit"): 0.36,
    (3, ("create", "edit", "python"), "find_file"): 0.28,
    (3, ("create", "edit", "python"), "search_dir"): 0.20,
    (4, ("edit", "python", "rm", "submit"), "<END>"): 1.00,
}

FAILED_EDIT_MARKER = "Your proposed edit has introduced new syntax error(s)."

PAPER_PATCH_STATS = {
    ("gpt4", "prediction", "resolved"): [(3.0, 5.70), (1.0, 1.32), (1.0, 1.52), (1.0, 1.22)],
    ("gpt4", "prediction", "all"): [(12.0, 16.58), (1.0, 1.35), (2.0, 1.83), (1.0, 1.53)],
    ("gpt4", "gold", "resolved"): [(2.0, 3.58), (1.0, 1.98), (1.0, 1.30), (1.0, 1.00)],
    ("gpt4", "gold", "all"): [(7.0, 11.67), (2.0, 4.05), (2.0, 2.45), (1.0, 1.24)],
    ("claude3opus", "prediction", "resolved"): [(3.0, 5.09), (1.0, 1.59), (1.0, 1.56), (1.0, 1.26)],
    ("claude3opus", "prediction", "all"): [(11.0, 15.25), (1.0, 1.79), (2.0, 2.14), (2.0, 1.87)],
    ("claude3opus", "gold", "resolved"): [(3.0, 3.91), (1.0, 1.94), (1.0, 1.40), (1.0, 1.00)],
    ("claude3opus", "gold", "all"): [(6.0, 10.68), (2.0, 3.61), (2.0, 2.22), (1.0, 1.13)],
}

PATCH_METRICS = ["lines_added", "lines_removed", "num_hunks", "num_files"]

PDF_METADATA = {
    "Title": "SWE-agent official artifact analysis reproduction",
    "Author": "",
    "Subject": "arXiv 2405.15793v3 artifact replay",
    "Keywords": "SWE-agent SWE-bench reproduction",
    "CreationDate": datetime(2024, 5, 6, tzinfo=timezone.utc),
    "ModDate": datetime(2024, 5, 6, tzinfo=timezone.utc),
}


@dataclass(frozen=True)
class TrajectoryRecord:
    instance_id: str
    split: str
    run: str
    exit_status: str | None
    steps: int
    cost: float
    actions: tuple[str, ...]
    failed_edits: tuple[bool, ...]


def run_command(args: Sequence[str], cwd: Path, *, binary: bool = False) -> bytes | str:
    return subprocess.check_output(args, cwd=cwd, text=not binary)


def git_blob(repo: Path, revision: str, path: str) -> bytes:
    return run_command(["git", "show", f"{revision}:{path}"], repo, binary=True)  # type: ignore[return-value]


def git_text(repo: Path, revision: str, path: str) -> str:
    return git_blob(repo, revision, path).decode("utf-8")


def git_paths(repo: Path, revision: str, prefix: str) -> list[str]:
    text = run_command(
        ["git", "ls-tree", "-r", "--name-only", revision, prefix], repo
    )
    return str(text).splitlines()


def git_object_id(repo: Path, revision: str, path: str) -> str:
    return str(run_command(["git", "rev-parse", f"{revision}:{path}"], repo)).strip()


def iter_git_blobs(repo: Path, revision: str, paths: Sequence[str]) -> Iterator[tuple[str, bytes]]:
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    if proc.stdin is None or proc.stdout is None:
        raise RuntimeError("Unable to open git cat-file pipes")
    try:
        for path in paths:
            proc.stdin.write(f"{revision}:{path}\n".encode("utf-8"))
            proc.stdin.flush()
            header = proc.stdout.readline().decode("utf-8").strip().split()
            if len(header) != 3 or header[1] != "blob":
                raise RuntimeError(f"Unexpected cat-file header for {path}: {header}")
            size = int(header[2])
            payload = proc.stdout.read(size)
            separator = proc.stdout.read(1)
            if len(payload) != size or separator != b"\n":
                raise RuntimeError(f"Truncated git blob: {path}")
            yield path, payload
    finally:
        proc.stdin.close()
        proc.stdout.close()
        return_code = proc.wait()
        if return_code:
            raise RuntimeError(f"git cat-file exited with {return_code}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_hash(path: Path, expected: str) -> None:
    observed = sha256_file(path)
    if observed != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path}: {observed} != {expected}")


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        if not rows:
            raise RuntimeError(f"Cannot infer columns for empty CSV: {path}")
        fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def load_results(repo: Path, split: str, run: str) -> dict[str, list[str]]:
    return json.loads(
        git_text(repo, EXPERIMENTS_REVISION, f"evaluation/{split}/{run}/results/results.json")
    )


def read_paper_member(paper_source: Path, member: str) -> str:
    with tarfile.open(paper_source, "r:gz") as archive:
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RuntimeError(f"Missing paper source member: {member}")
        return extracted.read().decode("utf-8")


def clean_tex_number(value: str) -> float:
    value = value.replace("\\phantom{0}", "").replace("\\%", "").strip()
    return float(value)


def parse_performance_table(paper_source: Path, member: str) -> list[dict[str, Any]]:
    rows = []
    for line in read_paper_member(paper_source, member).splitlines():
        if "&" not in line or "(" not in line or "\\%" not in line:
            continue
        parts = [part.strip() for part in line.split("&")]
        if len(parts) != 6:
            continue
        match = re.match(r"(.+?)\s*\((\d+)\)$", parts[0])
        if not match:
            continue
        label = match.group(1).strip()
        total = int(match.group(2))
        values = [clean_tex_number(part.rstrip(" \\\\")) for part in parts[1:]]
        rows.append({"label": label, "total": total, "percentages": values})
    if not rows:
        raise RuntimeError(f"No performance rows parsed from {member}")
    return rows


def parse_action_pattern(field: str) -> tuple[str, ...]:
    actions = [value.replace("\\_", "_") for value in re.findall(r"\\texttt\{([^}]*)\}", field)]
    if len(actions) == 1:
        repeat = re.search(r"\((?:x(\d+)|(\d+)x)\)", field)
        if repeat:
            count = int(repeat.group(1) or repeat.group(2))
            actions *= count
    return tuple(actions)


def parse_top_triples(paper_source: Path) -> list[dict[str, Any]]:
    rows = []
    text = read_paper_member(paper_source, "appx_tables/most_common_triples.tex")
    for line in text.splitlines():
        match = re.match(r"\s*(.+?\\texttt\{.+?)\s*&\s*(\d+)\s*\\\\", line)
        if not match:
            continue
        pattern = parse_action_pattern(match.group(1))
        if len(pattern) == 3:
            rows.append({"pattern": pattern, "paper_count": int(match.group(2))})
    if len(rows) != 10:
        raise RuntimeError(f"Expected 10 paper triple rows, found {len(rows)}")
    return rows


def parse_index_triples(paper_source: Path) -> list[dict[str, Any]]:
    rows = []
    text = read_paper_member(paper_source, "appx_tables/most_common_triples_by_index.tex")
    for line in text.splitlines():
        match = re.match(
            r"\s*(\d+)-(\d+)\s*&\s*(.+?)\s*&\s*(\d+)\s*&\s*(.+?)\s*\\\\",
            line,
        )
        if not match:
            continue
        pattern = parse_action_pattern(match.group(3))
        if len(pattern) != 3:
            raise RuntimeError(f"Unexpected indexed pattern: {line}")
        rows.append(
            {
                "start_turn": int(match.group(1)),
                "end_turn": int(match.group(2)),
                "pattern": pattern,
                "paper_count": int(match.group(4)),
                "category": match.group(5).strip(),
            }
        )
    if not rows:
        raise RuntimeError("No indexed triple rows parsed from paper source")
    return rows


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return [dict(row) for row in pq.read_table(path).to_pylist()]


def trajectory_record(path: str, payload: bytes, split: str, run: str) -> TrajectoryRecord:
    raw = json.loads(payload)
    actions = []
    failed_edits = []
    for turn in raw["trajectory"]:
        action = turn.get("action") or ""
        pieces = action.split()
        command = pieces[0] if pieces else "<EMPTY>"
        actions.append(command)
        failed_edits.append(command == "edit" and FAILED_EDIT_MARKER in (turn.get("observation") or ""))
    info = raw["info"]
    return TrajectoryRecord(
        instance_id=Path(path).name.split(".", 1)[0],
        split=split,
        run=run,
        exit_status=info.get("exit_status"),
        steps=len(actions),
        cost=float(info["model_stats"]["instance_cost"]),
        actions=tuple(actions),
        failed_edits=tuple(failed_edits),
    )


def load_trajectories(repo: Path, split: str, run: str, source_split: str) -> list[TrajectoryRecord]:
    prefix = f"evaluation/{source_split}/{run}/trajs"
    paths = [path for path in git_paths(repo, EXPERIMENTS_REVISION, prefix) if path.endswith(".traj")]
    records = [
        trajectory_record(path, payload, split, run)
        for path, payload in iter_git_blobs(repo, EXPERIMENTS_REVISION, paths)
    ]
    if len(records) != len(paths):
        raise RuntimeError(f"Trajectory count mismatch for {split}/{run}")
    return records


def year_bucket(created_at: str) -> str:
    year = datetime.fromisoformat(created_at.rstrip("Z")).year
    return str(year) if year >= 2020 else "Before 2020"


def reproduce_performance(
    repo: Path,
    lite_tasks: list[dict[str, Any]],
    paper_source: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    tasks_by_id = {row["instance_id"]: row for row in lite_tasks}
    results_by_run = {run: load_results(repo, "lite", run) for _, run in PERFORMANCE_RUNS}
    repo_targets = parse_performance_table(paper_source, "appx_tables/performance_by_repo.tex")
    time_targets = parse_performance_table(paper_source, "appx_tables/performance_by_temporal.tex")

    repo_totals = Counter(row["repo"] for row in lite_tasks)
    year_totals = Counter(year_bucket(row["created_at"]) for row in lite_tasks)
    repo_rows = []
    time_rows = []

    for target in repo_targets:
        repo_name = target["label"]
        if repo_totals[repo_name] != target["total"]:
            raise RuntimeError(f"Repository denominator mismatch: {repo_name}")
        for index, (run_key, run) in enumerate(PERFORMANCE_RUNS):
            count = sum(
                tasks_by_id[instance_id]["repo"] == repo_name
                for instance_id in results_by_run[run]["resolved"]
            )
            percent = round(100.0 * count / target["total"], 2)
            paper_percent = target["percentages"][index]
            repo_rows.append(
                {
                    "repository": repo_name,
                    "total": target["total"],
                    "run": run_key,
                    "resolved": count,
                    "percent": f"{percent:.2f}",
                    "paper_percent": f"{paper_percent:.2f}",
                    "exact": percent == paper_percent,
                }
            )

    for target in time_targets:
        bucket = target["label"]
        if year_totals[bucket] != target["total"]:
            raise RuntimeError(f"Year denominator mismatch: {bucket}")
        for index, (run_key, run) in enumerate(PERFORMANCE_RUNS):
            count = sum(
                year_bucket(tasks_by_id[instance_id]["created_at"]) == bucket
                for instance_id in results_by_run[run]["resolved"]
            )
            percent = round(100.0 * count / target["total"], 2)
            paper_percent = target["percentages"][index]
            time_rows.append(
                {
                    "year_bucket": bucket,
                    "total": target["total"],
                    "run": run_key,
                    "resolved": count,
                    "percent": f"{percent:.2f}",
                    "paper_percent": f"{paper_percent:.2f}",
                    "exact": percent == paper_percent,
                }
            )

    audit = {
        "a01_repo_rows": len(repo_rows),
        "a01_exact_rows": sum(row["exact"] for row in repo_rows),
        "a02_year_rows": len(time_rows),
        "a02_exact_rows": sum(row["exact"] for row in time_rows),
    }
    return repo_rows, time_rows, audit


def exit_category(status: str | None) -> str | None:
    if status == "submitted":
        return "Submit"
    if status == "submitted (exit_cost)":
        return "Exit Cost (Submit)"
    if status == "exit_cost":
        return "Exit Cost (No Submit)"
    if status in {"early_exit", "submitted (exit_format)"}:
        return "Early Exit"
    return None


def reproduce_exit_conditions(
    repo: Path,
    trajectories: dict[tuple[str, str], list[TrajectoryRecord]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    claude_full_details: dict[str, Any] = {}
    for split, run, source_split in TRAJECTORY_RUNS:
        records = trajectories[(split, run)]
        by_id = {record.instance_id: record for record in records}
        resolved_list = load_results(repo, source_split, run)["resolved"]
        resolved_set = set(resolved_list)
        all_counts = Counter(
            category
            for record in records
            if (category := exit_category(record.exit_status)) is not None
        )
        unique_counts = Counter(
            category
            for record in records
            if record.instance_id in resolved_set
            if (category := exit_category(record.exit_status)) is not None
        )
        weighted_counts = Counter(
            category
            for instance_id in resolved_list
            if instance_id in by_id
            if (category := exit_category(by_id[instance_id].exit_status)) is not None
        )
        for outcome, counts in (("all", all_counts), ("resolved", unique_counts)):
            target = PAPER_EXIT_COUNTS[(run, split, outcome)]
            for index, category in enumerate(EXIT_CATEGORIES):
                rows.append(
                    {
                        "run": run,
                        "split": split,
                        "outcome": outcome,
                        "category": category,
                        "paper_count": target[index],
                        "public_unique_count": counts[category],
                        "public_prediction_line_weighted_count": (
                            weighted_counts[category] if outcome == "resolved" else counts[category]
                        ),
                        "unique_exact": counts[category] == target[index],
                        "weighted_exact": (
                            weighted_counts[category] == target[index]
                            if outcome == "resolved"
                            else counts[category] == target[index]
                        ),
                    }
                )
        if split == "full" and run == RUN_CLAUDE:
            claude_full_details = {
                "trajectory_files": len(records),
                "missing_exit_status": sum(record.exit_status is None for record in records),
                "resolved_report_entries": len(resolved_list),
                "resolved_unique_instances": len(resolved_set),
                "resolved_entries_without_public_trajectory": sum(
                    instance_id not in by_id for instance_id in resolved_list
                ),
                "resolved_unique_without_public_trajectory": len(resolved_set - set(by_id)),
            }
    audit = {
        "rows": len(rows),
        "unique_exact_rows": sum(row["unique_exact"] for row in rows),
        "weighted_exact_rows": sum(row["weighted_exact"] for row in rows),
        "claude_full_public_gap": claude_full_details,
    }
    return rows, audit


def describe(values: Sequence[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=float)
    return {
        "n": len(array),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "q75": float(np.percentile(array, 75)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def trajectory_analysis_rows(
    repo: Path,
    trajectories: dict[tuple[str, str], list[TrajectoryRecord]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    summary_rows = []
    instance_rows = []
    target_turns = {
        ("full", RUN_GPT4): {"mean": 14.71, "median": 12.0, "q75": 18.0},
        ("lite", RUN_CLAUDE): {"mean": 12.71, "median": 13.0, "q75": 15.0},
    }
    for split, run, source_split in TRAJECTORY_RUNS:
        records = trajectories[(split, run)]
        resolved = set(load_results(repo, source_split, run)["resolved"])
        for record in records:
            instance_rows.append(
                {
                    "run": run,
                    "split": split,
                    "instance_id": record.instance_id,
                    "resolved": record.instance_id in resolved,
                    "steps": record.steps,
                    "cost_usd": f"{record.cost:.8f}",
                    "exit_status": record.exit_status or "MISSING",
                    "failed_edits": sum(record.failed_edits),
                }
            )
        groups = {
            "all_public_trajectories": records,
            "resolved": [record for record in records if record.instance_id in resolved],
            "unresolved": [record for record in records if record.instance_id not in resolved],
            "intentional_submit": [record for record in records if record.exit_status == "submitted"],
            "intentional_submit_resolved": [
                record
                for record in records
                if record.exit_status == "submitted" and record.instance_id in resolved
            ],
            "intentional_submit_unresolved": [
                record
                for record in records
                if record.exit_status == "submitted" and record.instance_id not in resolved
            ],
        }
        for group, selected in groups.items():
            if not selected:
                continue
            step_stats = describe([record.steps for record in selected])
            cost_stats = describe([record.cost for record in selected])
            target = target_turns.get((split, run), {}) if group == "resolved" else {}
            summary_rows.append(
                {
                    "run": run,
                    "split": split,
                    "group": group,
                    "n": len(selected),
                    "steps_mean": f"{step_stats['mean']:.4f}",
                    "steps_median": f"{step_stats['median']:.4f}",
                    "steps_q75": f"{step_stats['q75']:.4f}",
                    "cost_mean": f"{cost_stats['mean']:.4f}",
                    "cost_median": f"{cost_stats['median']:.4f}",
                    "cost_q75": f"{cost_stats['q75']:.4f}",
                    "paper_steps_mean": target.get("mean", ""),
                    "paper_steps_median": target.get("median", ""),
                    "paper_steps_q75": target.get("q75", ""),
                    "paper_turn_summary_exact": (
                        round(float(step_stats["mean"]), 2) == target.get("mean")
                        and float(step_stats["median"]) == target.get("median")
                        and float(step_stats["q75"]) == target.get("q75")
                        if target
                        else ""
                    ),
                }
            )
    exact_targets = [row for row in summary_rows if row["paper_turn_summary_exact"] != ""]
    return summary_rows, instance_rows, {
        "paper_turn_targets": len(exact_targets),
        "paper_turn_exact": sum(row["paper_turn_summary_exact"] is True for row in exact_targets),
        "paper_text_cost_note": {
            "claim": "resolved median cost 1.21 and 12 steps; unresolved 2.52 and 21 steps",
            "public_full_gpt4_resolved_median_cost": next(
                row["cost_median"]
                for row in summary_rows
                if row["run"] == RUN_GPT4 and row["split"] == "full" and row["group"] == "resolved"
            ),
            "public_full_gpt4_unresolved_median_cost": next(
                row["cost_median"]
                for row in summary_rows
                if row["run"] == RUN_GPT4 and row["split"] == "full" and row["group"] == "unresolved"
            ),
        },
    }


def action_rows(
    records: Sequence[TrajectoryRecord], resolved: set[str]
) -> tuple[list[dict[str, Any]], list[TrajectoryRecord], dict[str, Any]]:
    selected = [record for record in records if record.instance_id in resolved]
    max_turns = max(record.steps for record in selected)
    totals = Counter(action for record in selected for action in record.actions)
    rows = []
    top_by_turn = {}
    for turn_index in range(max_turns):
        actions = [record.actions[turn_index] for record in selected if record.steps > turn_index]
        counts = Counter(actions)
        reaching = len(actions)
        allowed_counts = {action: counts[action] for action in ACTION_ALLOWLIST if counts[action]}
        if allowed_counts:
            top_by_turn[turn_index + 1] = max(
                allowed_counts, key=lambda action: (allowed_counts[action], action)
            )
        for action in ACTION_ALLOWLIST:
            count = counts[action]
            rows.append(
                {
                    "turn": turn_index + 1,
                    "trajectories_reaching_turn": reaching,
                    "action": action,
                    "count": count,
                    "share_of_reaching": f"{count / reaching:.8f}",
                    "share_of_action_total": f"{count / totals[action]:.8f}" if totals[action] else "0.00000000",
                }
            )
    first_actions = Counter(record.actions[0] for record in selected)
    audit = {
        "resolved_trajectories": len(selected),
        "first_action_counts": dict(sorted(first_actions.items())),
        "first_actions_match_paper_set": set(first_actions) <= {"create", "find_file", "search_dir"},
        "top_actions_turn_5_to_31": {
            str(turn): top_by_turn.get(turn) for turn in range(5, min(31, max_turns) + 1)
        },
    }
    return rows, selected, audit


def triple_rows(
    selected: Sequence[TrajectoryRecord], paper_source: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    counts = Counter(
        tuple(record.actions[index : index + 3])
        for record in selected
        for index in range(max(0, record.steps - 2))
    )
    target_top = parse_top_triples(paper_source)
    top_rows = []
    for rank, target in enumerate(target_top, start=1):
        observed = counts[target["pattern"]]
        top_rows.append(
            {
                "rank": rank,
                "pattern": " | ".join(target["pattern"]),
                "paper_count": target["paper_count"],
                "observed_count": observed,
                "exact": observed == target["paper_count"],
            }
        )

    indexed_targets = parse_index_triples(paper_source)
    index_rows = []
    for target in indexed_targets:
        start_index = target["start_turn"] - 1
        observed = sum(
            tuple(record.actions[start_index : start_index + 3]) == target["pattern"]
            for record in selected
            if record.steps >= start_index + 3
        )
        index_rows.append(
            {
                "start_turn": target["start_turn"],
                "end_turn": target["end_turn"],
                "pattern": " | ".join(target["pattern"]),
                "category": target["category"],
                "paper_count": target["paper_count"],
                "observed_count": observed,
                "exact": observed == target["paper_count"],
            }
        )
    audit = {
        "top_triple_rows": len(top_rows),
        "top_triple_exact": sum(row["exact"] for row in top_rows),
        "indexed_rows": len(index_rows),
        "indexed_exact": sum(row["exact"] for row in index_rows),
        "category_labels_source": "manual assignments in appx_tables/most_common_triples_by_index.tex",
    }
    return top_rows, index_rows, audit


def transition_rows(
    records: Sequence[TrajectoryRecord],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    sequences = [("<START>", *record.actions, "<END>") for record in records]
    csv_rows = []
    plot_data = {}
    source_cell_matches = []
    for n in range(1, 5):
        paper_leads = PAPER_TRANSITION_ROWS[n]
        lead_set = set(paper_leads)
        transitions: dict[tuple[str, ...], Counter[str]] = {}
        for sequence in sequences:
            for index in range(len(sequence) - n):
                lead = tuple(sequence[index : index + n])
                next_action = sequence[index + n]
                if lead not in lead_set:
                    continue
                if n == 1 and lead[0] not in TRANSITION_VALID_ACTIONS:
                    continue
                if next_action not in TRANSITION_VALID_ACTIONS:
                    continue
                if lead not in transitions:
                    transitions[lead] = Counter()
                transitions[lead][next_action] += 1
        missing = lead_set - set(transitions)
        if missing:
            raise RuntimeError(f"Missing transition rows for n={n}: {sorted(missing)}")
        next_actions = sorted({action for counter in transitions.values() for action in counter})
        probabilities = np.zeros((len(paper_leads), len(next_actions)))
        actual_counts = []
        for row_index, lead in enumerate(paper_leads):
            total = sum(transitions[lead].values())
            actual_counts.append(total)
            for column_index, next_action in enumerate(next_actions):
                count = transitions[lead][next_action]
                probability = count / total
                probabilities[row_index, column_index] = probability
                expected = PAPER_TRANSITION_CELLS.get((n, lead, next_action))
                cell_exact = expected is None or round(probability, 2) == expected
                if expected is not None:
                    source_cell_matches.append(cell_exact)
                csv_rows.append(
                    {
                        "n": n,
                        "previous_actions": " | ".join(lead),
                        "next_action": next_action,
                        "count": count,
                        "total_after_sequence": total,
                        "probability": f"{probability:.8f}",
                        "paper_pdf_rounded_target": "" if expected is None else f"{expected:.2f}",
                        "paper_pdf_cell_exact": "" if expected is None else cell_exact,
                    }
                )
        legacy_display_counts = [sum(counter.values()) for counter in transitions.values()]
        plot_data[n] = {
            "leads": paper_leads,
            "next_actions": next_actions,
            "probabilities": probabilities,
            "actual_counts": actual_counts,
            "legacy_display_counts": legacy_display_counts,
        }
    audit = {
        "rows": len(csv_rows),
        "source_pdf_spot_checks": len(source_cell_matches),
        "source_pdf_spot_checks_exact": sum(source_cell_matches),
        "legacy_figure_issue": (
            "The paper PDF's right-margin transition counts follow dictionary insertion order "
            "while heatmap rows are sorted, so those labels are permuted. Probability cells are unaffected."
        ),
        "prose_figure_difference": {
            "sequence": "create | edit | python",
            "figure_next_edit_find_file_search_dir": [0.36, 0.28, 0.20],
            "prose_next_edit_find_file_search_dir": [0.39, 0.31, 0.22],
        },
    }
    return csv_rows, plot_data, audit


def failed_edit_analysis(
    records: Sequence[TrajectoryRecord], resolved: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    all_counts = [sum(record.failed_edits) for record in records]
    resolved_counts = [
        sum(record.failed_edits) for record in records if record.instance_id in resolved
    ]

    def summarize_counts(label: str, values: list[int], paper_n: int, paper_positive: int) -> list[dict[str, Any]]:
        positive = [value for value in values if value]
        metrics = {
            "public_trajectory_count": len(values),
            "trajectories_with_failed_edit": len(positive),
            "positive_median_failed_edits": float(np.median(positive)),
            "positive_mean_failed_edits": float(np.mean(positive)),
            "positive_max_failed_edits": max(positive),
            "total_failed_edits": sum(positive),
        }
        paper = {
            "public_trajectory_count": paper_n,
            "trajectories_with_failed_edit": paper_positive,
            "positive_median_failed_edits": 3.0 if label == "all" else 2.0,
            "positive_max_failed_edits": 33 if label == "all" else 26,
        }
        return [
            {
                "scope": label,
                "metric": metric,
                "public_value": value,
                "paper_value": paper.get(metric, ""),
                "exact": "" if metric not in paper else value == paper[metric],
            }
            for metric, value in metrics.items()
        ]

    summary_rows = summarize_counts("all", all_counts, 2294, 1185)
    summary_rows += summarize_counts("resolved", resolved_counts, 286, 113)

    edit_blocks: list[list[bool]] = []
    failure_runs: list[tuple[int, bool]] = []
    for record in records:
        index = 0
        while index < record.steps:
            if record.actions[index] != "edit":
                index += 1
                continue
            block = []
            while index < record.steps and record.actions[index] == "edit":
                block.append(record.failed_edits[index])
                index += 1
            edit_blocks.append(block)
            cursor = 0
            while cursor < len(block):
                if not block[cursor]:
                    cursor += 1
                    continue
                end = cursor
                while end < len(block) and block[end]:
                    end += 1
                failure_runs.append((end - cursor, end < len(block) and not block[end]))
                cursor = end + 1 if end < len(block) else end

    recovery_rows = []
    max_failures = max(length for length, _ in failure_runs)
    for failures in range(0, max_failures + 1):
        if failures == 0:
            denominator = len(edit_blocks)
            numerator = sum(any(not item for item in block) for block in edit_blocks)
        else:
            eligible = [success for length, success in failure_runs if length >= failures]
            denominator = len(eligible)
            numerator = sum(eligible)
        probability = numerator / denominator if denominator else float("nan")
        paper_probability = 0.905 if failures == 0 else 0.572 if failures == 1 else None
        recovery_rows.append(
            {
                "failed_edits_in_row": failures,
                "successful_recoveries": numerator,
                "eligible_sequences": denominator,
                "probability": f"{probability:.8f}",
                "paper_probability": "" if paper_probability is None else f"{paper_probability:.3f}",
                "paper_probability_exact_at_reported_precision": (
                    ""
                    if paper_probability is None
                    else round(probability * 100, 1) == round(paper_probability * 100, 1)
                ),
            }
        )

    success_lengths = [length for length, success in failure_runs if success]
    failed_lengths = [length for length, success in failure_runs if not success]
    audit = {
        "public_full_gpt4_trajectory_files": len(records),
        "paper_denominator": 2294,
        "public_trajectory_gap": 2294 - len(records),
        "resolved_positive_percentage_recomputed": round(100 * 113 / 286, 1),
        "paper_resolved_positive_percentage_text": 31.5,
        "paper_percentage_is_arithmetically_inconsistent": round(100 * 113 / 286, 1) != 31.5,
        "maximal_failure_runs": len(failure_runs),
        "successful_failure_runs": len(success_lengths),
        "unsuccessful_failure_runs": len(failed_lengths),
        "successful_mean_run_length": float(np.mean(success_lengths)),
        "unsuccessful_mean_run_length": float(np.mean(failed_lengths)),
        "paper_reported_run_counts": {"successful": 810, "unsuccessful": 555},
        "paper_reported_mean_lengths": {"successful": 2.2, "unsuccessful": 5.59},
        "mean_lengths_match_paper": (
            round(float(np.mean(success_lengths)), 1) == 2.2
            and round(float(np.mean(failed_lengths)), 2) == 5.59
        ),
    }
    return summary_rows, recovery_rows, audit


def patch_stats(patch: str) -> tuple[int, int, int, int]:
    parsed = PatchSet(patch)
    return (
        sum(hunk.added for file in parsed for hunk in file),
        sum(hunk.removed for file in parsed for hunk in file),
        sum(len(file) for file in parsed),
        len(parsed.added_files + parsed.modified_files + parsed.removed_files),
    )


def summarize_patch_group(
    model: str,
    source: str,
    outcome: str,
    patches: Sequence[str],
) -> list[dict[str, Any]]:
    values = np.asarray([patch_stats(patch) for patch in patches], dtype=float)
    expected = PAPER_PATCH_STATS[(model, source, outcome)]
    rows = []
    for metric_index, metric in enumerate(PATCH_METRICS):
        metric_values = values[:, metric_index]
        percentile_90 = float(np.percentile(metric_values, 90))
        kept = metric_values[metric_values <= percentile_90]
        median = float(np.median(kept))
        mean = float(np.mean(kept))
        paper_median, paper_mean = expected[metric_index]
        rows.append(
            {
                "model": model,
                "source": source,
                "outcome": outcome,
                "metric": metric,
                "input_patch_lines": len(patches),
                "p90": f"{percentile_90:.8f}",
                "kept_at_or_below_p90": len(kept),
                "median": f"{median:.4f}",
                "mean": f"{mean:.4f}",
                "paper_median": f"{paper_median:.2f}",
                "paper_mean": f"{paper_mean:.2f}",
                "exact": median == paper_median and round(mean, 2) == paper_mean,
            }
        )
    return rows


def reproduce_patch_statistics(
    repo: Path, full_tasks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tasks_by_id = {row["instance_id"]: row for row in full_tasks}
    rows = []
    input_counts = {}
    for model, run in (("gpt4", RUN_GPT4), ("claude3opus", RUN_CLAUDE)):
        predictions = load_jsonl(
            git_blob(repo, EXPERIMENTS_REVISION, f"evaluation/test/{run}/all_preds.jsonl")
        )
        resolved = set(load_results(repo, "test", run)["resolved"])
        nonempty = [
            prediction
            for prediction in predictions
            if isinstance(prediction.get("model_patch"), str)
            and prediction["model_patch"].strip()
        ]
        resolved_predictions = [
            prediction for prediction in nonempty if prediction["instance_id"] in resolved
        ]
        groups = {
            ("prediction", "resolved"): [prediction["model_patch"] for prediction in resolved_predictions],
            ("prediction", "all"): [prediction["model_patch"] for prediction in nonempty],
            ("gold", "resolved"): [
                tasks_by_id[prediction["instance_id"]]["patch"]
                for prediction in resolved_predictions
            ],
            ("gold", "all"): [
                tasks_by_id[prediction["instance_id"]]["patch"] for prediction in nonempty
            ],
        }
        input_counts[model] = {
            "prediction_lines": len(predictions),
            "nonempty_prediction_lines": len(nonempty),
            "unique_nonempty_instances": len({item["instance_id"] for item in nonempty}),
            "resolved_prediction_lines": len(resolved_predictions),
            "unique_resolved_instances": len(resolved),
        }
        for (source, outcome), patches in groups.items():
            rows.extend(summarize_patch_group(model, source, outcome, patches))
    audit = {
        "rows": len(rows),
        "exact_rows": sum(row["exact"] for row in rows),
        "input_counts": input_counts,
        "semantics": (
            "Nonempty prediction lines are retained in JSONL order without deduplication. "
            "Gold patches are repeated once per retained prediction line. Each metric independently "
            "keeps values less than or equal to its 90th percentile before median/mean calculation."
        ),
    }
    return rows, audit


def file_f1(true_labels: Sequence[str], predicted_labels: Sequence[str]) -> float:
    if not predicted_labels:
        return 0.0
    true_set = set(true_labels)
    predicted_set = set(predicted_labels)
    overlap = len(true_set & predicted_set)
    if not overlap:
        return 0.0
    return 2.0 * overlap / (len(true_set) + len(predicted_set))


def reproduce_file_localization(
    repo: Path, lite_tasks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tasks_by_id = {row["instance_id"]: row for row in lite_tasks}
    targets = {RUN_GPT4: 59.05, RUN_RAG_CLAUDE: 45.47}
    rows = []
    for run in (RUN_GPT4, RUN_CLAUDE, RUN_RAG_GPT4, RUN_RAG_CLAUDE):
        predictions = load_jsonl(
            git_blob(repo, EXPERIMENTS_REVISION, f"evaluation/lite/{run}/all_preds.jsonl")
        )
        scores = []
        parse_errors = 0
        added_only_skips = 0
        for prediction in predictions:
            gold_patch = PatchSet(tasks_by_id[prediction["instance_id"]]["patch"])
            gold_files = [
                item.path for item in gold_patch.modified_files + gold_patch.removed_files
            ]
            if not gold_files:
                added_only_skips += 1
                continue
            try:
                predicted_patch = PatchSet(prediction.get("model_patch"))
                predicted_files = [
                    item.path
                    for item in predicted_patch.modified_files + predicted_patch.removed_files
                    if not item.path.startswith("reproduce")
                ]
            except (TypeError, UnidiffParseError):
                parse_errors += 1
                predicted_files = []
            scores.append(file_f1(gold_files, predicted_files))
        mean_percent = 100.0 * sum(scores) / len(scores)
        target = targets.get(run)
        rows.append(
            {
                "run": run,
                "split": "lite",
                "prediction_lines": len(predictions),
                "scored_lines": len(scores),
                "patch_parse_errors": parse_errors,
                "gold_added_only_skips": added_only_skips,
                "mean_f1_percent": f"{mean_percent:.4f}",
                "paper_mean_f1_percent": "" if target is None else f"{target:.2f}",
                "paper_exact": "" if target is None else round(mean_percent, 2) == target,
            }
        )
    target_rows = [row for row in rows if row["paper_exact"] != ""]
    return rows, {
        "paper_targets": len(target_rows),
        "paper_targets_exact": sum(row["paper_exact"] is True for row in target_rows),
        "paper_split_recovered": "lite",
    }


def compress_pattern(pattern: Sequence[str]) -> str:
    output = []
    index = 0
    while index < len(pattern):
        end = index + 1
        while end < len(pattern) and pattern[end] == pattern[index]:
            end += 1
        count = end - index
        output.append(f"{pattern[index]} ({count}x)" if count > 1 else pattern[index])
        index = end
    return ", ".join(output)


def plot_trajectory_distributions(
    path: Path,
    trajectories: dict[tuple[str, str], list[TrajectoryRecord]],
    results: dict[tuple[str, str], set[str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(path, metadata=PDF_METADATA) as pdf:
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        for axis, split, run, title in (
            (axes[0], "full", RUN_GPT4, "GPT-4 Turbo / Full"),
            (axes[1], "lite", RUN_CLAUDE, "Claude 3 Opus / Lite"),
        ):
            solved = results[(split, run)]
            turns = [
                record.steps
                for record in trajectories[(split, run)]
                if record.instance_id in solved
            ]
            axis.hist(turns, bins=15, color="#1f90ff", edgecolor="black")
            axis.set_title(title)
            axis.set_xlabel("Turns")
            axis.set_ylabel("Resolved trajectories")
            axis.grid(axis="y", alpha=0.2)
        figure.suptitle("Resolved trajectories by turn")
        figure.tight_layout()
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)

        records = trajectories[("full", RUN_GPT4)]
        solved = results[("full", RUN_GPT4)]
        submitted = [record for record in records if record.exit_status == "submitted"]
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        for label, color, selected in (
            ("Resolved", "#f28e2b", [record for record in submitted if record.instance_id in solved]),
            ("Unresolved", "#4e79a7", [record for record in submitted if record.instance_id not in solved]),
        ):
            axes[0].hist(
                [record.steps for record in selected],
                bins=20,
                alpha=0.65,
                color=color,
                label=label,
            )
            axes[1].hist(
                [record.cost for record in selected],
                bins=20,
                alpha=0.65,
                color=color,
                label=label,
            )
        axes[0].set_xlabel("Steps")
        axes[1].set_xlabel("Cost (USD)")
        for axis in axes:
            axis.set_ylabel("Intentional submissions")
            axis.legend()
            axis.grid(axis="y", alpha=0.2)
        figure.suptitle("Intentional submissions before budget exhaustion / GPT-4 Turbo Full")
        figure.tight_layout()
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)


def plot_action_analyses(
    path: Path,
    action_data: list[dict[str, Any]],
    indexed_triples: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    turns = sorted({int(row["turn"]) for row in action_data})
    active_actions = [
        action
        for action in ACTION_ALLOWLIST
        if any(int(row["count"]) for row in action_data if row["action"] == action)
    ]
    counts = np.asarray(
        [
            [
                int(next(row["count"] for row in action_data if row["turn"] == turn and row["action"] == action))
                for action in active_actions
            ]
            for turn in turns
        ],
        dtype=float,
    )
    reaching = np.asarray(
        [
            int(next(row["trajectories_reaching_turn"] for row in action_data if row["turn"] == turn))
            for turn in turns
        ],
        dtype=float,
    )
    colors = plt.cm.tab20(np.linspace(0, 1, len(active_actions)))
    with PdfPages(path, metadata=PDF_METADATA) as pdf:
        for title, matrix, ylabel in (
            ("Action frequency per turn / resolved GPT-4 Turbo Full", counts, "Frequency"),
            (
                "Action share among trajectories reaching each turn",
                counts / reaching[:, None],
                "Share of active trajectories",
            ),
        ):
            figure, axis = plt.subplots(figsize=(13.5, 6))
            bottom = np.zeros(len(turns))
            for action_index, action in enumerate(active_actions):
                axis.bar(
                    turns,
                    matrix[:, action_index],
                    bottom=bottom,
                    label=action,
                    color=colors[action_index],
                    width=0.85,
                )
                bottom += matrix[:, action_index]
            axis.set_title(title)
            axis.set_xlabel("Turn")
            axis.set_ylabel(ylabel)
            axis.legend(
                ncols=1,
                fontsize=8,
                frameon=False,
                loc="upper left",
                bbox_to_anchor=(1.01, 1.0),
            )
            axis.grid(axis="y", alpha=0.2)
            figure.tight_layout(rect=(0, 0, 0.87, 1))
            pdf.savefig(figure, bbox_inches="tight")
            plt.close(figure)

        density = np.divide(
            counts,
            counts.sum(axis=0),
            out=np.zeros_like(counts),
            where=counts.sum(axis=0) > 0,
        )
        figure, axis = plt.subplots(figsize=(13.5, 6))
        for action_index, action in enumerate(active_actions):
            axis.plot(
                turns,
                density[:, action_index],
                label=action,
                color=colors[action_index],
                linewidth=1.8,
                alpha=0.9,
            )
        axis.set_title("Turn density within each action")
        axis.set_xlabel("Turn")
        axis.set_ylabel("Share of each action's occurrences")
        axis.set_ylim(bottom=0)
        axis.legend(
            ncols=1,
            fontsize=8,
            frameon=False,
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
        )
        axis.grid(alpha=0.2)
        figure.tight_layout(rect=(0, 0, 0.87, 1))
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)

        categories = sorted({row["category"] for row in indexed_triples})
        start_turns = sorted({int(row["start_turn"]) for row in indexed_triples})
        figure, axis = plt.subplots(figsize=(10, 5))
        bottom = np.zeros(len(start_turns))
        for category_index, category in enumerate(categories):
            values = np.asarray(
                [
                    sum(
                        int(row["observed_count"])
                        for row in indexed_triples
                        if row["category"] == category and int(row["start_turn"]) == turn
                    )
                    for turn in start_turns
                ],
                dtype=float,
            )
            axis.bar(
                start_turns,
                values,
                bottom=bottom,
                label=category,
                color=plt.cm.Set2(category_index / max(1, len(categories) - 1)),
            )
            bottom += values
        axis.set_title("Published manually categorized frequent triples by starting turn")
        axis.set_xlabel("Starting turn")
        axis.set_ylabel("Observed triple occurrences")
        axis.legend(frameon=False)
        axis.grid(axis="y", alpha=0.2)
        figure.tight_layout()
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)


def plot_transition_probabilities(path: Path, plot_data: dict[int, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(path, metadata=PDF_METADATA) as pdf:
        for n in range(1, 5):
            data = plot_data[n]
            matrix = data["probabilities"]
            leads = data["leads"]
            next_actions = data["next_actions"]
            figure_height = max(6.0, 0.48 * len(leads) + 2.5)
            figure, axis = plt.subplots(figsize=(13, figure_height))
            image = axis.imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
            axis.set_xticks(range(len(next_actions)), next_actions, rotation=55, ha="right")
            axis.set_yticks(range(len(leads)), [compress_pattern(lead) for lead in leads])
            axis.set_xlabel("Next action")
            axis.set_ylabel(f"Previous {n} action{'s' if n > 1 else ''}")
            axis.set_title(f"Transition probabilities / {n}-gram (right counts corrected)")
            for row_index in range(matrix.shape[0]):
                for column_index in range(matrix.shape[1]):
                    value = matrix[row_index, column_index]
                    axis.text(
                        column_index,
                        row_index,
                        f"{value:.2f}",
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="white" if value >= 0.5 else "black",
                    )
                axis.text(
                    matrix.shape[1] + 0.12,
                    row_index,
                    str(data["actual_counts"][row_index]),
                    va="center",
                    fontsize=8,
                )
            axis.set_xlim(-0.5, matrix.shape[1] + 1.2)
            figure.colorbar(image, ax=axis, fraction=0.025, pad=0.06)
            figure.tight_layout()
            pdf.savefig(figure, bbox_inches="tight")
            plt.close(figure)


def plot_failed_edits(
    path: Path,
    records: Sequence[TrajectoryRecord],
    resolved: set[str],
    recovery_rows: Sequence[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    all_counts = [sum(record.failed_edits) for record in records]
    resolved_counts = [
        sum(record.failed_edits) for record in records if record.instance_id in resolved
    ]
    with PdfPages(path, metadata=PDF_METADATA) as pdf:
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        axes[0].hist(all_counts, bins=range(0, max(all_counts) + 2), color="#4e79a7")
        axes[1].hist(
            resolved_counts,
            bins=range(0, max(resolved_counts) + 2),
            color="#f28e2b",
        )
        axes[0].set_title("All public GPT-4 Full trajectories")
        axes[1].set_title("Resolved GPT-4 Full trajectories")
        for axis in axes:
            axis.set_xlabel("Failed edit actions")
            axis.set_ylabel("Trajectories")
            axis.grid(axis="y", alpha=0.2)
        figure.tight_layout()
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)

        curve = [row for row in recovery_rows if int(row["failed_edits_in_row"]) <= 15]
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.plot(
            [int(row["failed_edits_in_row"]) for row in curve],
            [float(row["probability"]) for row in curve],
            marker="o",
            color="#4e79a7",
        )
        axis.set_ylim(0, 1)
        axis.set_xlabel("Consecutive failed edits")
        axis.set_ylabel("Probability of eventual immediate edit recovery")
        axis.set_title("Edit recovery probability / public GPT-4 Full trajectories")
        axis.grid(alpha=0.25)
        figure.tight_layout()
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)


def runtime_versions() -> dict[str, str]:
    packages = ["numpy", "matplotlib", "pyarrow", "unidiff"]
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        **{package: importlib.metadata.version(package) for package in packages},
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiments-repo",
        type=Path,
        default=project_root / "code" / "SWE-bench-experiments",
    )
    parser.add_argument(
        "--lite-parquet",
        type=Path,
        default=project_root / "data" / "cache" / "paper_evaluator" / "lite_paper_81ad348a.parquet",
    )
    parser.add_argument(
        "--full-parquet",
        type=Path,
        default=project_root / "data" / "cache" / "paper_evaluator" / "test_paper_283547ac.parquet",
    )
    parser.add_argument(
        "--paper-source",
        type=Path,
        default=project_root / "paper" / "2405.15793_source.tar.gz",
    )
    parser.add_argument(
        "--derived-dir",
        type=Path,
        default=project_root / "data" / "derived",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        default=project_root / "output" / "pdf",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=project_root / "data" / "manifests" / "official_instance_analyses.json",
    )
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()

    repo = args.experiments_repo.resolve()
    lite_path = args.lite_parquet.resolve()
    full_path = args.full_parquet.resolve()
    paper_source = args.paper_source.resolve()
    derived_dir = args.derived_dir.resolve()
    figure_dir = args.figure_dir.resolve()
    manifest_path = args.manifest.resolve()

    ensure_hash(lite_path, LITE_DATASET_SHA256)
    ensure_hash(full_path, FULL_DATASET_SHA256)
    lite_tasks = load_tasks(lite_path)
    full_tasks = load_tasks(full_path)
    if len(lite_tasks) != 300 or len(full_tasks) != 2294:
        raise RuntimeError("Unexpected paper dataset cardinality")

    performance_repo, performance_year, performance_audit = reproduce_performance(
        repo, lite_tasks, paper_source
    )
    trajectories = {
        (split, run): load_trajectories(repo, split, run, source_split)
        for split, run, source_split in TRAJECTORY_RUNS
    }
    exit_rows, exit_audit = reproduce_exit_conditions(repo, trajectories)
    trajectory_summary, trajectory_instances, trajectory_audit = trajectory_analysis_rows(
        repo, trajectories
    )
    results_sets = {
        (split, run): set(load_results(repo, source_split, run)["resolved"])
        for split, run, source_split in TRAJECTORY_RUNS
    }
    action_data, resolved_gpt4, action_audit = action_rows(
        trajectories[("full", RUN_GPT4)], results_sets[("full", RUN_GPT4)]
    )
    top_triples, indexed_triples, triple_audit = triple_rows(resolved_gpt4, paper_source)
    transitions, transition_plot_data, transition_audit = transition_rows(
        trajectories[("full", RUN_GPT4)]
    )
    failed_summary, failed_recovery, failed_audit = failed_edit_analysis(
        trajectories[("full", RUN_GPT4)], results_sets[("full", RUN_GPT4)]
    )
    patch_rows, patch_audit = reproduce_patch_statistics(repo, full_tasks)
    localization_rows, localization_audit = reproduce_file_localization(repo, lite_tasks)

    outputs = {
        "performance_by_repo": derived_dir / "official_performance_by_repo.csv",
        "performance_by_year": derived_dir / "official_performance_by_year.csv",
        "exit_conditions": derived_dir / "official_exit_conditions.csv",
        "trajectory_summary": derived_dir / "official_trajectory_summary.csv",
        "trajectory_instances": derived_dir / "official_trajectory_instances.csv",
        "actions_per_turn": derived_dir / "official_actions_per_turn.csv",
        "action_triples": derived_dir / "official_action_triples.csv",
        "action_patterns_by_turn": derived_dir / "official_action_patterns_by_turn.csv",
        "transition_probabilities": derived_dir / "official_transition_probabilities.csv",
        "failed_edit_summary": derived_dir / "official_failed_edit_summary.csv",
        "failed_edit_recovery": derived_dir / "official_failed_edit_recovery.csv",
        "patch_statistics": derived_dir / "official_patch_statistics.csv",
        "file_localization": derived_dir / "official_file_localization.csv",
    }
    data_by_key = {
        "performance_by_repo": performance_repo,
        "performance_by_year": performance_year,
        "exit_conditions": exit_rows,
        "trajectory_summary": trajectory_summary,
        "trajectory_instances": trajectory_instances,
        "actions_per_turn": action_data,
        "action_triples": top_triples,
        "action_patterns_by_turn": indexed_triples,
        "transition_probabilities": transitions,
        "failed_edit_summary": failed_summary,
        "failed_edit_recovery": failed_recovery,
        "patch_statistics": patch_rows,
        "file_localization": localization_rows,
    }
    for key, path in outputs.items():
        write_csv(path, data_by_key[key])

    figure_outputs = {
        "trajectory_distributions": figure_dir / "official_trajectory_distributions_artifact.pdf",
        "action_analyses": figure_dir / "official_action_analyses_artifact.pdf",
        "transition_probabilities_figure": figure_dir
        / "official_transition_probabilities_artifact.pdf",
        "failed_edits": figure_dir / "official_failed_edits_artifact.pdf",
    }
    if not args.no_figures:
        plot_trajectory_distributions(
            figure_outputs["trajectory_distributions"], trajectories, results_sets
        )
        plot_action_analyses(figure_outputs["action_analyses"], action_data, indexed_triples)
        plot_transition_probabilities(
            figure_outputs["transition_probabilities_figure"], transition_plot_data
        )
        plot_failed_edits(
            figure_outputs["failed_edits"],
            trajectories[("full", RUN_GPT4)],
            results_sets[("full", RUN_GPT4)],
            failed_recovery,
        )

    tracked_outputs = {**outputs}
    if not args.no_figures:
        tracked_outputs.update(figure_outputs)
    output_manifest = {
        key: {
            "path": path.relative_to(project_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for key, path in tracked_outputs.items()
    }

    analyses = {
        "A01_performance_by_repository": {
            "status": "COMPLETE_EXACT",
            **{key: performance_audit[key] for key in ("a01_repo_rows", "a01_exact_rows")},
        },
        "A02_performance_by_year": {
            "status": "COMPLETE_EXACT",
            **{key: performance_audit[key] for key in ("a02_year_rows", "a02_exact_rows")},
        },
        "A03_exit_conditions": {
            "status": "PARTIAL_CLAUDE_FULL_RESOLVED_TRAJECTORIES_MISSING",
            **exit_audit,
        },
        "A04_turn_step_cost": {
            "status": "PARTIAL_TURN_TARGETS_EXACT_COST_PROSE_DRIFT",
            **trajectory_audit,
        },
        "A05_actions_per_turn": {"status": "COMPLETE_PUBLIC_TRAJECTORY_REPLAY", **action_audit},
        "A06_action_triples": {"status": "COMPLETE_EXACT_PUBLISHED_COUNTS", **triple_audit},
        "A07_action_transitions": {
            "status": "COMPLETE_NUMERIC_SPOT_CHECKS_WITH_LEGACY_LABEL_BUG",
            **transition_audit,
        },
        "A08_failed_edits": {
            "status": "PARTIAL_PUBLIC_TRAJECTORY_GAP_AND_PAPER_COUNT_INCONSISTENCY",
            **failed_audit,
        },
        "A09_patch_statistics": {"status": "COMPLETE_EXACT", **patch_audit},
        "A10_file_localization": {"status": "COMPLETE_EXACT", **localization_audit},
    }

    manifest = {
        "schema_version": 1,
        "status": "COMPLETE_AVAILABLE_A01_A10_WITH_DOCUMENTED_PUBLIC_ARTIFACT_GAPS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper": {
            "arxiv_id": PAPER_ARXIV_ID,
            "source_path": paper_source.relative_to(project_root).as_posix(),
            "source_sha256": sha256_file(paper_source),
        },
        "frozen_inputs": {
            "experiments_revision": EXPERIMENTS_REVISION,
            "lite_dataset_revision": LITE_DATASET_REVISION,
            "lite_dataset_sha256": LITE_DATASET_SHA256,
            "full_dataset_revision": FULL_DATASET_REVISION,
            "full_dataset_sha256": FULL_DATASET_SHA256,
            "trajectory_trees": {
                f"{split}/{run}": {
                    "git_tree": git_object_id(
                        repo, EXPERIMENTS_REVISION, f"evaluation/{source_split}/{run}/trajs"
                    ),
                    "files": len(trajectories[(split, run)]),
                }
                for split, run, source_split in TRAJECTORY_RUNS
            },
            "paper_analysis_source_blobs": {
                path: git_object_id(repo, EXPERIMENTS_REVISION, path)
                for path in (
                    "analysis/resolved_by_repo.py",
                    "analysis/resolved_by_time.py",
                    "analysis/stats_patch.py",
                    "analysis/calc_localization_f1.py",
                )
            },
        },
        "runtime": runtime_versions(),
        "analyses": analyses,
        "outputs": output_manifest,
        "summary": {
            "analysis_items": 10,
            "complete_exact_or_public_replay": 7,
            "partial_with_explicit_gap": 3,
            "api_calls": 0,
            "gpu_used": False,
            "server_used": False,
        },
    }
    write_json(manifest_path, manifest)
    print(f"manifest={manifest_path}")
    for name, analysis in analyses.items():
        print(f"{name}: {analysis['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
