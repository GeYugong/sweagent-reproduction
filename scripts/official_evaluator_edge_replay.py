#!/usr/bin/env python3
"""Prepare and verify empty/duplicate plus gold/no-apply evaluator branches."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from official_container_replay import (
    DATASET_REVISION,
    DATASET_SHA256,
    EXPERIMENTS_REVISION,
    docker_version,
    ensure_output_path,
    git_blob,
    load_predictions,
    normalize_tests,
    sha256_bytes,
    sha256_file,
)


PROFILES = {
    "empty_duplicate": {
        "alias": "paper_replay_empty_duplicate",
        "description": "One official empty-string line plus two duplicate null lines; no testbed.",
    },
    "gold_no_apply": {
        "alias": "paper_replay_gold_no_apply",
        "description": "One gold patch plus one official RAG no-apply patch in pytest 4.4.",
    },
}


def read_tasks(parquet_path: Path) -> dict[str, dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required") from exc
    if sha256_file(parquet_path) != DATASET_SHA256:
        raise RuntimeError(f"Paper Lite Parquet hash mismatch: {parquet_path}")
    tasks = {}
    for raw in pq.read_table(parquet_path).to_pylist():
        row = dict(raw)
        row["FAIL_TO_PASS"] = normalize_tests(row["FAIL_TO_PASS"])
        row["PASS_TO_PASS"] = normalize_tests(row["PASS_TO_PASS"])
        tasks[row["instance_id"]] = row
    return tasks


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def prepare_empty_duplicate(
    experiments_repo: Path,
    tasks: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    run = "20240402_sweagent_gpt4"
    source = load_predictions(
        git_blob(experiments_repo, f"evaluation/lite/{run}/all_preds.jsonl")
    )
    selected = [
        row
        for row in source
        if row["instance_id"] in {"django__django-13964", "psf__requests-863"}
    ]
    expected_ids = [
        "django__django-13964",
        "psf__requests-863",
        "psf__requests-863",
    ]
    if [row["instance_id"] for row in selected] != expected_ids:
        raise RuntimeError("Unexpected duplicate prediction ordering")
    states = [
        "null"
        if row.get("model_patch") is None
        else "empty_string"
        if not row["model_patch"].strip()
        else "nonempty"
        for row in selected
    ]
    if states != ["empty_string", "null", "null"]:
        raise RuntimeError(f"Unexpected empty prediction states: {states}")
    selected_tasks = [tasks["django__django-13964"], tasks["psf__requests-863"]]
    details = [
        {
            "line_index": index,
            "instance_id": row["instance_id"],
            "source": f"{run}/all_preds.jsonl",
            "patch_state": state,
            "expected_scorecard_statuses": ["not_generated"],
        }
        for index, (row, state) in enumerate(zip(selected, states), start=1)
    ]
    return selected, selected_tasks, details


def prepare_gold_no_apply(
    experiments_repo: Path,
    tasks: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    gold_id = "pytest-dev__pytest-5227"
    no_apply_id = "pytest-dev__pytest-5221"
    gold_task = tasks[gold_id]
    no_apply_task = tasks[no_apply_id]
    if any(
        task["repo"] != "pytest-dev/pytest" or str(task["version"]) != "4.4"
        for task in (gold_task, no_apply_task)
    ):
        raise RuntimeError("Expected both edge tasks in pytest 4.4")

    rag_run = "20240402_rag_gpt4"
    rag_matches = [
        row
        for row in load_predictions(
            git_blob(experiments_repo, f"evaluation/lite/{rag_run}/all_preds.jsonl")
        )
        if row["instance_id"] == no_apply_id
    ]
    if len(rag_matches) != 1 or not rag_matches[0].get("model_patch"):
        raise RuntimeError("Missing official RAG no-apply prediction")
    rag_results = json.loads(
        git_blob(experiments_repo, f"evaluation/lite/{rag_run}/results/results.json")
    )
    if no_apply_id not in rag_results["no_apply"]:
        raise RuntimeError("Selected RAG prediction is not in official no_apply")

    predictions = [
        {
            "instance_id": gold_id,
            "model_name_or_path": "gold_patch",
            "model_patch": gold_task["patch"],
        },
        rag_matches[0],
    ]
    details = [
        {
            "line_index": 1,
            "instance_id": gold_id,
            "source": f"SWE-bench_Lite@{DATASET_REVISION}:patch",
            "patch_state": "gold",
            "patch_sha256": sha256_bytes(gold_task["patch"].encode("utf-8")),
            "expected_resolution": "RESOLVED_FULL",
            "expected_scorecard_statuses": ["generated", "applied", "RESOLVED_FULL"],
        },
        {
            "line_index": 2,
            "instance_id": no_apply_id,
            "source": f"{rag_run}/all_preds.jsonl",
            "patch_state": "official_rag_no_apply",
            "patch_sha256": sha256_bytes(rag_matches[0]["model_patch"].encode("utf-8")),
            "official_categories": [
                key for key, values in rag_results.items() if no_apply_id in values
            ],
            "expected_scorecard_statuses": ["generated"],
        },
    ]
    return predictions, [gold_task, no_apply_task], details


def prepare(
    profile: str,
    project_root: Path,
    experiments_repo: Path,
    parquet_path: Path,
    output_dir: Path,
) -> int:
    ensure_output_path(output_dir, project_root)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    tasks = read_tasks(parquet_path)
    if profile == "empty_duplicate":
        predictions, selected_tasks, details = prepare_empty_duplicate(experiments_repo, tasks)
    else:
        predictions, selected_tasks, details = prepare_gold_no_apply(experiments_repo, tasks)

    predictions_path = output_dir / "all_preds.jsonl"
    tasks_path = output_dir / "tasks.jsonl"
    write_jsonl(predictions_path, predictions)
    write_jsonl(tasks_path, selected_tasks)
    manifest = {
        "schema_version": 1,
        "profile": profile,
        "status": "PREPARED",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "description": PROFILES[profile]["description"],
        "official_experiments_revision": EXPERIMENTS_REVISION,
        "dataset_revision": DATASET_REVISION,
        "dataset_sha256": DATASET_SHA256,
        "model_alias": PROFILES[profile]["alias"],
        "predictions_sha256": sha256_file(predictions_path),
        "tasks_sha256": sha256_file(tasks_path),
        "prediction_lines": details,
    }
    (output_dir / "input_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"profile={profile}")
    print(f"predictions={predictions_path}")
    print(f"tasks={tasks_path}")
    print(f"model_alias={PROFILES[profile]['alias']}")
    return 0


def collect_empty_duplicate(
    scorecards: list[dict[str, Any]],
    input_manifest: dict[str, Any],
    observed_log_dir: Path,
) -> tuple[list[dict[str, Any]], bool]:
    expected = input_manifest["prediction_lines"]
    rows = []
    for source, scorecard in zip(expected, scorecards):
        exact = (
            scorecard.get("instance_id") == source["instance_id"]
            and scorecard.get("statuses") == source["expected_scorecard_statuses"]
        )
        rows.append(
            {
                **source,
                "observed_instance_id": scorecard.get("instance_id"),
                "observed_scorecard_statuses": scorecard.get("statuses"),
                "exact_outcome_match": exact,
            }
        )
    unexpected_logs = sorted(path.name for path in observed_log_dir.glob("*.eval.log"))
    all_exact = len(scorecards) == len(expected) and all(
        row["exact_outcome_match"] for row in rows
    ) and not unexpected_logs
    if unexpected_logs:
        rows.append({"unexpected_eval_logs": unexpected_logs, "exact_outcome_match": False})
    return rows, all_exact


def expected_full_report(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "FAIL_TO_PASS": {"success": ref["FAIL_TO_PASS"], "failure": []},
        "PASS_TO_PASS": {"success": ref["PASS_TO_PASS"], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": []},
        "PASS_TO_FAIL": {"success": [], "failure": []},
    }


def collect_gold_no_apply(
    scorecards: list[dict[str, Any]],
    input_manifest: dict[str, Any],
    output_dir: Path,
    observed_log_dir: Path,
) -> tuple[list[dict[str, Any]], bool]:
    from swebench import get_eval_refs, get_eval_report, get_logs_eval, get_resolution_status

    refs = get_eval_refs(str(output_dir / "tasks.jsonl"))
    scorecards_by_id = {card["instance_id"]: card for card in scorecards}
    rows = []
    alias = input_manifest["model_alias"]
    for source in input_manifest["prediction_lines"]:
        instance_id = source["instance_id"]
        scorecard = scorecards_by_id[instance_id]
        log_path = observed_log_dir / f"{instance_id}.{alias}.eval.log"
        if not log_path.is_file():
            raise RuntimeError(f"Missing observed evaluator log: {log_path}")
        status_map, found = get_logs_eval(str(log_path))
        if source["patch_state"] == "gold":
            report = get_eval_report(status_map, refs[instance_id])
            resolution = get_resolution_status(report)
            exact = (
                found
                and report == expected_full_report(refs[instance_id])
                and resolution == "RESOLVED_FULL"
                and scorecard.get("statuses") == source["expected_scorecard_statuses"]
            )
            rows.append(
                {
                    **source,
                    "observed_patch_applied": found,
                    "observed_resolution": resolution,
                    "all_reference_tests_passed": report == expected_full_report(refs[instance_id]),
                    "observed_scorecard_statuses": scorecard.get("statuses"),
                    "observed_log_sha256": sha256_file(log_path),
                    "exact_outcome_match": exact,
                }
            )
        else:
            content = log_path.read_text(encoding="utf-8", errors="replace")
            apply_failure_markers = [
                marker
                for marker in (
                    ">>>>> Patch Apply Failed; (pred_try)",
                    ">>>>> Patch Apply Failed; (pred_minimal_try)",
                )
                if marker in content
            ]
            exact = (
                not found
                and bool(apply_failure_markers)
                and scorecard.get("statuses") == source["expected_scorecard_statuses"]
            )
            rows.append(
                {
                    **source,
                    "observed_patch_applied": found,
                    "observed_apply_failure_markers": apply_failure_markers,
                    "observed_scorecard_statuses": scorecard.get("statuses"),
                    "observed_log_sha256": sha256_file(log_path),
                    "exact_outcome_match": exact,
                }
            )
    return rows, all(row["exact_outcome_match"] for row in rows)


def collect(
    profile: str,
    output_dir: Path,
    results_dir: Path,
    manifest_path: Path,
) -> int:
    input_manifest = json.loads((output_dir / "input_manifest.json").read_text(encoding="utf-8"))
    if input_manifest["profile"] != profile:
        raise RuntimeError("Profile mismatch in input manifest")
    scorecards = json.loads((output_dir / "scorecards.json").read_text(encoding="utf-8"))
    observed_log_dir = results_dir / input_manifest["model_alias"]
    if profile == "empty_duplicate":
        rows, all_exact = collect_empty_duplicate(scorecards, input_manifest, observed_log_dir)
    else:
        rows, all_exact = collect_gold_no_apply(
            scorecards,
            input_manifest,
            output_dir,
            observed_log_dir,
        )
    manifest = {
        **input_manifest,
        "status": "COMPLETE_EXACT" if all_exact else "COMPLETE_MISMATCH",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "docker": docker_version(),
        },
        "results_directory": results_dir.as_posix(),
        "observations": rows,
        "summary": {
            "expected_line_count": len(input_manifest["prediction_lines"]),
            "exact_outcome_match_count": sum(
                row.get("exact_outcome_match", False) for row in rows
            ),
            "all_exact": all_exact,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"profile={profile} exact={manifest['summary']['exact_outcome_match_count']}/"
        f"{manifest['summary']['expected_line_count']}"
    )
    print(f"manifest={manifest_path}")
    return 0 if all_exact else 1


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "collect"))
    parser.add_argument("profile", choices=tuple(PROFILES))
    parser.add_argument(
        "--experiments-repo",
        type=Path,
        default=project_root / "code" / "SWE-bench-experiments",
    )
    parser.add_argument(
        "--parquet",
        type=Path,
        default=project_root
        / "data"
        / "cache"
        / "paper_evaluator"
        / "lite_paper_81ad348a.parquet",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    profile = args.profile
    output_dir = (
        args.output_dir
        or project_root / "outputs" / "evaluation" / "official_container_replay" / profile
    ).resolve()
    results_dir = (
        args.results_dir
        or project_root / "outputs" / "evaluation" / "official_container_replay" / "results"
    ).resolve()
    manifest_path = (
        args.manifest
        or project_root / "data" / "manifests" / f"official_{profile}_replay.json"
    ).resolve()
    if args.mode == "prepare":
        return prepare(
            profile,
            project_root,
            args.experiments_repo.resolve(),
            args.parquet.resolve(),
            output_dir,
        )
    return collect(profile, output_dir, results_dir, manifest_path)


if __name__ == "__main__":
    raise SystemExit(main())
