#!/usr/bin/env python3
"""Prepare and verify a minimal paper-era container evaluator replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENTS_REVISION = "a5d52722965c791c0c04d18135f906b44f716d39"
DATASET_REVISION = "81ad348adcaf3368691f4db2907f8fc97a8f7526"
DATASET_SHA256 = "2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1"
OFFICIAL_RUN = "20240402_sweagent_gpt4"
MODEL_ALIAS = "paper_replay_pytest44_gpt4"
INSTANCE_IDS = (
    "pytest-dev__pytest-5227",  # official RESOLVED_FULL
    "pytest-dev__pytest-5221",  # official RESOLVED_NO after successful apply
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob(repo: Path, path: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{EXPERIMENTS_REVISION}:{path}"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))
    return proc.stdout


def normalize_tests(value: Any) -> list[str]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("Invalid SWE-bench test reference")
    return value


def ensure_output_path(path: Path, project_root: Path) -> None:
    allowed = (project_root / "outputs" / "evaluation").resolve()
    resolved = path.resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise RuntimeError(f"Unsafe output path: {resolved}")


def load_predictions(data: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


def docker_version() -> str | None:
    proc = subprocess.run(
        ["docker", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def prepare(
    project_root: Path,
    experiments_repo: Path,
    parquet_path: Path,
    output_dir: Path,
) -> int:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required to prepare the paper dataset subset") from exc

    ensure_output_path(output_dir, project_root)
    if sha256_file(parquet_path) != DATASET_SHA256:
        raise RuntimeError(f"Paper Lite Parquet hash mismatch: {parquet_path}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    all_prediction_data = git_blob(
        experiments_repo,
        f"evaluation/lite/{OFFICIAL_RUN}/all_preds.jsonl",
    )
    predictions_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in load_predictions(all_prediction_data):
        predictions_by_id.setdefault(row["instance_id"], []).append(row)
    selected_predictions = []
    for instance_id in INSTANCE_IDS:
        matches = predictions_by_id.get(instance_id, [])
        if len(matches) != 1 or not matches[0].get("model_patch"):
            raise RuntimeError(f"Expected one non-empty official prediction for {instance_id}")
        selected_predictions.append(matches[0])

    task_rows = pq.read_table(parquet_path).to_pylist()
    tasks_by_id = {row["instance_id"]: row for row in task_rows}
    selected_tasks = []
    for instance_id in INSTANCE_IDS:
        task = dict(tasks_by_id[instance_id])
        task["FAIL_TO_PASS"] = normalize_tests(task["FAIL_TO_PASS"])
        task["PASS_TO_PASS"] = normalize_tests(task["PASS_TO_PASS"])
        if task["repo"] != "pytest-dev/pytest" or str(task["version"]) != "4.4":
            raise RuntimeError(f"Unexpected task grouping for {instance_id}")
        selected_tasks.append(task)

    predictions_path = output_dir / "all_preds.jsonl"
    tasks_path = output_dir / "tasks.jsonl"
    with predictions_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected_predictions:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with tasks_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected_tasks:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    official_results = json.loads(
        git_blob(
            experiments_repo,
            f"evaluation/lite/{OFFICIAL_RUN}/results/results.json",
        )
    )
    official_log_dir = output_dir / "official_logs"
    official_log_dir.mkdir()
    instance_rows = []
    for prediction, task in zip(selected_predictions, selected_tasks):
        instance_id = prediction["instance_id"]
        log_name = f"{instance_id}.{OFFICIAL_RUN}.eval.log"
        log_data = git_blob(
            experiments_repo,
            f"evaluation/lite/{OFFICIAL_RUN}/logs/{log_name}",
        )
        (official_log_dir / log_name).write_bytes(log_data)
        instance_rows.append(
            {
                "instance_id": instance_id,
                "repo": task["repo"],
                "version": str(task["version"]),
                "base_commit": task["base_commit"],
                "fail_to_pass_count": len(task["FAIL_TO_PASS"]),
                "pass_to_pass_count": len(task["PASS_TO_PASS"]),
                "prediction_patch_sha256": sha256_bytes(
                    prediction["model_patch"].encode("utf-8")
                ),
                "prediction_patch_bytes": len(prediction["model_patch"].encode("utf-8")),
                "official_log_sha256": sha256_bytes(log_data),
                "official_categories": [
                    category
                    for category, values in official_results.items()
                    if instance_id in values
                ],
            }
        )

    manifest = {
        "schema_version": 1,
        "status": "PREPARED",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_policy": (
            "Two official GPT-4 Lite predictions from the same pytest 4.4 environment: "
            "one RESOLVED_FULL and one applied RESOLVED_NO."
        ),
        "official_experiments_revision": EXPERIMENTS_REVISION,
        "official_run": OFFICIAL_RUN,
        "dataset": {
            "repository": "princeton-nlp/SWE-bench_Lite",
            "revision": DATASET_REVISION,
            "parquet_sha256": DATASET_SHA256,
        },
        "model_alias": MODEL_ALIAS,
        "predictions": {
            "path": predictions_path.as_posix(),
            "sha256": sha256_file(predictions_path),
        },
        "tasks": {
            "path": tasks_path.as_posix(),
            "sha256": sha256_file(tasks_path),
        },
        "instances": instance_rows,
    }
    (output_dir / "input_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"predictions={predictions_path}")
    print(f"tasks={tasks_path}")
    print(f"model_alias={MODEL_ALIAS}")
    return 0


def collect(
    project_root: Path,
    output_dir: Path,
    results_dir: Path,
    manifest_path: Path,
) -> int:
    from swebench import get_eval_refs, get_eval_report, get_logs_eval, get_resolution_status

    input_manifest = json.loads((output_dir / "input_manifest.json").read_text(encoding="utf-8"))
    scorecards = json.loads((output_dir / "scorecards.json").read_text(encoding="utf-8"))
    scorecards_by_id = {card["instance_id"]: card for card in scorecards}
    refs = get_eval_refs(str(output_dir / "tasks.jsonl"))
    observed_log_dir = results_dir / MODEL_ALIAS
    rows = []
    for source in input_manifest["instances"]:
        instance_id = source["instance_id"]
        official_log = output_dir / "official_logs" / f"{instance_id}.{OFFICIAL_RUN}.eval.log"
        observed_log = observed_log_dir / f"{instance_id}.{MODEL_ALIAS}.eval.log"
        if not observed_log.is_file():
            raise RuntimeError(f"Missing observed evaluator log: {observed_log}")
        official_status_map, official_found = get_logs_eval(str(official_log))
        observed_status_map, observed_found = get_logs_eval(str(observed_log))
        official_report = get_eval_report(official_status_map, refs[instance_id])
        observed_report = get_eval_report(observed_status_map, refs[instance_id])
        official_resolution = get_resolution_status(official_report)
        observed_resolution = get_resolution_status(observed_report)
        scorecard = scorecards_by_id[instance_id]
        expected_statuses = ["generated", "applied", official_resolution]
        exact = (
            official_found
            and observed_found
            and official_report == observed_report
            and observed_resolution == official_resolution
            and scorecard.get("statuses") == expected_statuses
        )
        rows.append(
            {
                **source,
                "official_resolution": official_resolution,
                "observed_resolution": observed_resolution,
                "official_patch_applied": official_found,
                "observed_patch_applied": observed_found,
                "test_report_exact_match": official_report == observed_report,
                "scorecard_statuses": scorecard.get("statuses"),
                "expected_scorecard_statuses": expected_statuses,
                "observed_log_sha256": sha256_file(observed_log),
                "exact_outcome_match": exact,
            }
        )

    all_exact = all(row["exact_outcome_match"] for row in rows)
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
        "instances": rows,
        "summary": {
            "instance_count": len(rows),
            "exact_outcome_match_count": sum(row["exact_outcome_match"] for row in rows),
            "all_exact": all_exact,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"exact={manifest['summary']['exact_outcome_match_count']}/{len(rows)}")
    print(f"manifest={manifest_path}")
    return 0 if all_exact else 1


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "collect"))
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
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root
        / "outputs"
        / "evaluation"
        / "official_container_replay"
        / "pytest44_sweagent_gpt4",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=project_root
        / "outputs"
        / "evaluation"
        / "official_container_replay"
        / "results",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=project_root
        / "data"
        / "manifests"
        / "official_container_replay.json",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if args.mode == "prepare":
        return prepare(
            project_root,
            args.experiments_repo.resolve(),
            args.parquet.resolve(),
            output_dir,
        )
    return collect(
        project_root,
        output_dir,
        args.results_dir.resolve(),
        args.manifest.resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
