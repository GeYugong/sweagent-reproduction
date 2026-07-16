#!/usr/bin/env python3
"""Replay paper-era SWE-bench result aggregation from official artifacts.

The official experiment repository contains predictions, evaluation logs, and
``results.json`` files, but its results depend on two historical inputs that are
easy to miss:

* the unreleased SWE-bench source tree used on 2024-04-16; and
* the 2024-04-15 Hugging Face dataset revisions containing the test references.

This script materializes only the exact logs requested by each prediction file,
runs the pinned historical ``get_model_report`` implementation, and compares
every category list (including order and duplicates) with the official JSON.
It also replays against a pinned 2025 dataset snapshot to quantify reference
drift without changing the paper-aligned result.

Run from WSL with the isolated evaluator environment, for example::

    /home/gugabobo/.venvs/swebench-paper-eval/bin/python \
        scripts/replay_official_evaluator.py
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable


EXPERIMENTS_REVISION = "a5d52722965c791c0c04d18135f906b44f716d39"
EVALUATOR_REVISION = "cfb20092bbbee9683176177b2f59b85f522e7f27"
CATEGORY_ORDER = (
    "no_generation",
    "generated",
    "with_logs",
    "install_fail",
    "reset_failed",
    "no_apply",
    "applied",
    "test_errored",
    "test_timeout",
    "resolved",
)


@dataclass(frozen=True)
class RunSpec:
    split: str
    run: str

    @property
    def prefix(self) -> str:
        return f"evaluation/{self.split}/{self.run}"


@dataclass(frozen=True)
class DatasetRevision:
    revision: str
    commit_date: str
    sha256: str
    size: int


@dataclass(frozen=True)
class DatasetSpec:
    split: str
    repository: str
    paper: DatasetRevision
    post_paper: DatasetRevision

    def url(self, revision: DatasetRevision) -> str:
        return (
            f"https://huggingface.co/datasets/{self.repository}/resolve/"
            f"{revision.revision}/data/test-00000-of-00001.parquet"
        )


RUNS = (
    RunSpec("lite", "20240402_sweagent_gpt4"),
    RunSpec("lite", "20240402_sweagent_claude3opus"),
    RunSpec("lite", "20240402_rag_gpt4"),
    RunSpec("lite", "20240402_rag_claude3opus"),
    RunSpec("test", "20240402_sweagent_gpt4"),
    RunSpec("test", "20240402_sweagent_claude3opus"),
    RunSpec("test", "20240402_rag_gpt4"),
    RunSpec("test", "20240402_rag_claude3opus"),
)

DATASETS = {
    "lite": DatasetSpec(
        split="lite",
        repository="princeton-nlp/SWE-bench_Lite",
        paper=DatasetRevision(
            revision="81ad348adcaf3368691f4db2907f8fc97a8f7526",
            commit_date="2024-04-15T22:17:00Z",
            sha256="2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1",
            size=1_176_783,
        ),
        post_paper=DatasetRevision(
            revision="6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2",
            commit_date="2025-03-03T05:29:31Z",
            sha256="7a21f37b8bc179c7db5beeb14e88ac538ba283455c776e6b2535bbfb6e3551b4",
            size=1_119_540,
        ),
    ),
    "test": DatasetSpec(
        split="test",
        repository="princeton-nlp/SWE-bench",
        paper=DatasetRevision(
            revision="283547aced6224d4adbe55c678b4c9c43fe7d501",
            commit_date="2024-04-15T22:18:03Z",
            sha256="831728617f006e70c9de546e15cbdb49ce27b6fe8a8e4c4cd8035e8da3de3020",
            size=12_102_802,
        ),
        post_paper=DatasetRevision(
            revision="e48e2bd1e9fecd5bbd641e9414ac59da9f2e69f6",
            commit_date="2025-03-03T05:28:08Z",
            sha256="db4f70ef735b3162c74801ddcdf8d7bae8d704193788c6d844f898c20b571cbb",
            size=12_097_227,
        ),
    ),
}


def git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {message}")
    if text:
        return proc.stdout.decode("utf-8", errors="strict")
    return proc.stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_within(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise RuntimeError(f"Refusing unsafe temporary path: {resolved_path}")


def reset_temp_dir(path: Path, temp_root: Path) -> None:
    ensure_within(path, temp_root)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


class GitBatchReader:
    """Read many blobs without checking out the large historical tree."""

    def __init__(self, repo: Path):
        self.proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=repo,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError("Unable to open git cat-file pipes")
        self.stdin: BinaryIO = self.proc.stdin
        self.stdout: BinaryIO = self.proc.stdout

    def get(self, object_name: str) -> bytes | None:
        self.stdin.write(object_name.encode("utf-8") + b"\n")
        self.stdin.flush()
        header = self.stdout.readline()
        if not header:
            raise RuntimeError(f"git cat-file ended while reading {object_name}")
        decoded = header.decode("utf-8", errors="replace").rstrip("\n")
        if decoded.endswith(" missing"):
            return None
        parts = decoded.split()
        if len(parts) != 3 or parts[1] != "blob":
            raise RuntimeError(f"Unexpected cat-file response for {object_name}: {decoded}")
        size = int(parts[2])
        data = self.stdout.read(size)
        terminator = self.stdout.read(1)
        if len(data) != size or terminator != b"\n":
            raise RuntimeError(f"Truncated git blob for {object_name}")
        return data

    def close(self) -> None:
        if not self.stdin.closed:
            self.stdin.close()
        self.proc.wait(timeout=30)
        if self.proc.returncode:
            stderr = b""
            if self.proc.stderr is not None:
                stderr = self.proc.stderr.read()
            raise RuntimeError(stderr.decode("utf-8", errors="replace"))

    def __enter__(self) -> "GitBatchReader":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def download_verified(
    url: str,
    destination: Path,
    revision: DatasetRevision,
    offline: bool,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    cache_hit = destination.exists()
    if cache_hit:
        actual_size = destination.stat().st_size
        actual_hash = sha256_file(destination)
        if actual_size == revision.size and actual_hash == revision.sha256:
            return {
                "path": destination.as_posix(),
                "cache_hit": True,
                "bytes": actual_size,
                "sha256": actual_hash,
            }
        destination.unlink()
    if offline:
        raise RuntimeError(f"Pinned dataset is absent from the offline cache: {destination}")

    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        partial.unlink()
    request = urllib.request.Request(url, headers={"User-Agent": "swe-agent-paper-replay/1"})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1024 * 1024)
    actual_size = partial.stat().st_size
    actual_hash = sha256_file(partial)
    if actual_size != revision.size or actual_hash != revision.sha256:
        partial.unlink()
        raise RuntimeError(
            f"Dataset verification failed for {url}: size={actual_size}, sha256={actual_hash}"
        )
    partial.replace(destination)
    return {
        "path": destination.as_posix(),
        "cache_hit": False,
        "bytes": actual_size,
        "sha256": actual_hash,
    }


def normalize_test_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"Unexpected test reference value: {type(value).__name__}")
    return value


def parquet_to_refs(parquet_path: Path, refs_path: Path) -> dict[str, dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required in the evaluator environment") from exc

    table = pq.read_table(
        parquet_path,
        columns=["instance_id", "FAIL_TO_PASS", "PASS_TO_PASS"],
    )
    refs: dict[str, dict[str, Any]] = {}
    refs_path.parent.mkdir(parents=True, exist_ok=True)
    with refs_path.open("w", encoding="utf-8", newline="\n") as handle:
        for raw in table.to_pylist():
            row = {
                "instance_id": raw["instance_id"],
                "FAIL_TO_PASS": normalize_test_list(raw["FAIL_TO_PASS"]),
                "PASS_TO_PASS": normalize_test_list(raw["PASS_TO_PASS"]),
            }
            refs[row["instance_id"]] = row
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    if len(refs) != table.num_rows:
        raise RuntimeError(f"Duplicate dataset IDs in {parquet_path}")
    return refs


def prepare_dataset_revisions(
    cache_root: Path,
    offline: bool,
) -> tuple[dict[str, dict[str, Path]], dict[str, Any], dict[str, dict[str, dict[str, Any]]]]:
    refs_paths: dict[str, dict[str, Path]] = {}
    manifest: dict[str, Any] = {}
    loaded_refs: dict[str, dict[str, dict[str, Any]]] = {}
    for split, spec in DATASETS.items():
        refs_paths[split] = {}
        loaded_refs[split] = {}
        revision_rows: dict[str, Any] = {}
        for label, revision in (("paper", spec.paper), ("post_paper", spec.post_paper)):
            stem = f"{split}_{label}_{revision.revision[:8]}"
            parquet_path = cache_root / f"{stem}.parquet"
            refs_path = cache_root / f"{stem}_refs.jsonl"
            download = download_verified(spec.url(revision), parquet_path, revision, offline)
            refs = parquet_to_refs(parquet_path, refs_path)
            refs_paths[split][label] = refs_path
            loaded_refs[split][label] = refs
            revision_rows[label] = {
                "repository": f"https://huggingface.co/datasets/{spec.repository}",
                "revision": revision.revision,
                "commit_date": revision.commit_date,
                "download_url": spec.url(revision),
                "parquet_bytes": revision.size,
                "parquet_sha256": revision.sha256,
                "row_count": len(refs),
                "cache": download,
                "refs_jsonl_sha256": sha256_file(refs_path),
            }

        paper_refs = loaded_refs[split]["paper"]
        post_refs = loaded_refs[split]["post_paper"]
        changed: list[dict[str, Any]] = []
        for instance_id in sorted(set(paper_refs) | set(post_refs)):
            before = paper_refs.get(instance_id)
            after = post_refs.get(instance_id)
            fields = []
            if before is None or after is None:
                fields.append("membership")
            else:
                for field in ("FAIL_TO_PASS", "PASS_TO_PASS"):
                    if before[field] != after[field]:
                        fields.append(field)
            if fields:
                changed.append({"instance_id": instance_id, "fields": fields})
        manifest[split] = {
            **revision_rows,
            "paper_to_post_paper_reference_diff": {
                "changed_instance_count": len(changed),
                "changed_instances": changed,
            },
        }
    return refs_paths, manifest, loaded_refs


def load_jsonl(data: bytes) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Malformed prediction line {line_number}") from exc
        row["_line_number"] = line_number
        rows.append(row)
    return rows


def patch_state(patch: Any) -> str:
    if patch is None:
        return "null"
    if not isinstance(patch, str):
        return "invalid"
    if not patch.strip():
        return "empty_string"
    return "nonempty"


def prediction_audit(
    predictions: list[dict[str, Any]],
    dataset_ids: Iterable[str],
) -> dict[str, Any]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    state_counts: Counter[str] = Counter()
    ordered_ids: list[str] = []
    for row in predictions:
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str):
            raise RuntimeError(f"Prediction line {row['_line_number']} has no instance_id")
        state = patch_state(row.get("model_patch"))
        state_counts[state] += 1
        ordered_ids.append(instance_id)
        patch = row.get("model_patch")
        attempt = {
            "line_number": row["_line_number"],
            "patch_state": state,
            "patch_sha256": sha256_bytes(patch.encode("utf-8")) if isinstance(patch, str) else None,
        }
        by_id[instance_id].append(attempt)

    duplicate_details = {
        instance_id: attempts
        for instance_id, attempts in sorted(by_id.items())
        if len(attempts) > 1
    }
    dataset_set = set(dataset_ids)
    prediction_set = set(ordered_ids)
    return {
        "line_count": len(predictions),
        "unique_instance_count": len(prediction_set),
        "duplicate_line_count": len(predictions) - len(prediction_set),
        "duplicated_unique_instance_count": len(duplicate_details),
        "patch_state_counts": dict(sorted(state_counts.items())),
        "duplicated_instances": duplicate_details,
        "dataset_instances_without_prediction": sorted(dataset_set - prediction_set),
        "predictions_outside_dataset": sorted(prediction_set - dataset_set),
    }


def materialize_run(
    reader: GitBatchReader,
    spec: RunSpec,
    run_dir: Path,
    temp_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    reset_temp_dir(run_dir, temp_root)
    predictions_object = f"{EXPERIMENTS_REVISION}:{spec.prefix}/all_preds.jsonl"
    results_object = f"{EXPERIMENTS_REVISION}:{spec.prefix}/results/results.json"
    predictions_data = reader.get(predictions_object)
    results_data = reader.get(results_object)
    if predictions_data is None or results_data is None:
        raise RuntimeError(f"Missing official run blobs for {spec.prefix}")
    predictions_path = run_dir / "all_preds.jsonl"
    predictions_path.write_bytes(predictions_data)
    official = json.loads(results_data)
    predictions = load_jsonl(predictions_data)

    log_dir = run_dir / "logs"
    log_dir.mkdir()
    requested_ids = sorted(
        {
            row["instance_id"]
            for row in predictions
            if patch_state(row.get("model_patch")) == "nonempty"
        }
    )
    materialized_count = 0
    materialized_bytes = 0
    missing_logs: list[str] = []
    for instance_id in requested_ids:
        name = f"{instance_id}.{spec.run}.eval.log"
        object_name = f"{EXPERIMENTS_REVISION}:{spec.prefix}/logs/{name}"
        data = reader.get(object_name)
        if data is None:
            missing_logs.append(instance_id)
            continue
        (log_dir / name).write_bytes(data)
        materialized_count += 1
        materialized_bytes += len(data)
    materialization = {
        "prediction_bytes": len(predictions_data),
        "prediction_sha256": sha256_bytes(predictions_data),
        "official_results_bytes": len(results_data),
        "official_results_sha256": sha256_bytes(results_data),
        "requested_unique_log_count": len(requested_ids),
        "materialized_unique_log_count": materialized_count,
        "materialized_log_bytes": materialized_bytes,
        "missing_log_instance_ids": missing_logs,
    }
    return predictions, official, materialization


def category_comparison(
    replayed: dict[str, list[str]],
    official: dict[str, list[str]],
) -> tuple[dict[str, Any], bool]:
    keys = list(dict.fromkeys([*CATEGORY_ORDER, *official.keys(), *replayed.keys()]))
    comparison: dict[str, Any] = {}
    exact = replayed == official
    for key in keys:
        replayed_list = replayed.get(key, [])
        official_list = official.get(key, [])
        replayed_counter = Counter(replayed_list)
        official_counter = Counter(official_list)
        comparison[key] = {
            "official_entries": len(official_list),
            "official_unique_instances": len(set(official_list)),
            "replayed_entries": len(replayed_list),
            "replayed_unique_instances": len(set(replayed_list)),
            "list_equal": replayed_list == official_list,
            "replayed_only_with_multiplicity": sorted((replayed_counter - official_counter).elements()),
            "official_only_with_multiplicity": sorted((official_counter - replayed_counter).elements()),
        }
    return comparison, exact


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiments-repo",
        type=Path,
        default=project_root / "code" / "SWE-bench-experiments",
    )
    parser.add_argument(
        "--evaluator-repo",
        type=Path,
        default=project_root / "code" / "SWE-bench",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=project_root / "data" / "cache" / "paper_evaluator",
    )
    parser.add_argument(
        "--temp-root",
        type=Path,
        default=project_root / "tmp" / "official-evaluator-replay",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "data" / "manifests" / "official_evaluator_replay.json",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-post-paper", action="store_true")
    parser.add_argument("--keep-materialized", action="store_true")
    args = parser.parse_args()

    experiments_repo = args.experiments_repo.resolve()
    evaluator_repo = args.evaluator_repo.resolve()
    cache_root = args.cache_root.resolve()
    temp_root = args.temp_root.resolve()
    temp_root.mkdir(parents=True, exist_ok=True)

    experiments_commit = str(git(experiments_repo, "rev-parse", EXPERIMENTS_REVISION)).strip()
    evaluator_commit = str(git(evaluator_repo, "rev-parse", "HEAD")).strip()
    if experiments_commit != EXPERIMENTS_REVISION:
        raise RuntimeError(f"Unexpected experiments revision: {experiments_commit}")
    if evaluator_commit != EVALUATOR_REVISION:
        raise RuntimeError(
            f"Evaluator submodule must be at {EVALUATOR_REVISION}, found {evaluator_commit}"
        )

    refs_paths, dataset_manifest, loaded_refs = prepare_dataset_revisions(
        cache_root,
        args.offline,
    )

    sys.path.insert(0, str(evaluator_repo))
    import swebench  # type: ignore[import-not-found]
    from swebench import get_model_report  # type: ignore[import-not-found]

    source_text = inspect.getsource(get_model_report)
    if "len(p[\"model_patch\"].strip()) == 0" not in source_text or "if any([" not in source_text:
        raise RuntimeError("Pinned get_model_report semantics do not match the audited source")

    run_rows: list[dict[str, Any]] = []
    with GitBatchReader(experiments_repo) as reader:
        for index, spec in enumerate(RUNS, start=1):
            print(f"[{index}/{len(RUNS)}] materialize {spec.split}/{spec.run}", flush=True)
            run_dir = temp_root / spec.split / spec.run
            predictions, official, materialization = materialize_run(
                reader,
                spec,
                run_dir,
                temp_root,
            )
            paper_refs = loaded_refs[spec.split]["paper"]
            audit = prediction_audit(predictions, paper_refs)

            print(f"[{index}/{len(RUNS)}] replay paper references", flush=True)
            paper_report = get_model_report(
                spec.run,
                str(run_dir / "all_preds.jsonl"),
                str(refs_paths[spec.split]["paper"]),
                str(run_dir / "logs"),
            )
            paper_comparison, paper_exact = category_comparison(paper_report, official)

            post_comparison = None
            post_exact = None
            if not args.skip_post_paper:
                print(f"[{index}/{len(RUNS)}] replay post-paper references", flush=True)
                post_report = get_model_report(
                    spec.run,
                    str(run_dir / "all_preds.jsonl"),
                    str(refs_paths[spec.split]["post_paper"]),
                    str(run_dir / "logs"),
                )
                post_comparison, post_exact = category_comparison(post_report, official)

            run_rows.append(
                {
                    "split": spec.split,
                    "run": spec.run,
                    "source_prefix": spec.prefix,
                    "materialization": materialization,
                    "predictions": audit,
                    "official_category_counts": {
                        key: {
                            "entries": len(value),
                            "unique_instances": len(set(value)),
                        }
                        for key, value in official.items()
                    },
                    "paper_reference_replay": {
                        "exact_full_report_match": paper_exact,
                        "categories": paper_comparison,
                    },
                    "post_paper_reference_replay": None
                    if args.skip_post_paper
                    else {
                        "exact_full_report_match": post_exact,
                        "categories": post_comparison,
                    },
                }
            )
            if not args.keep_materialized:
                ensure_within(run_dir, temp_root)
                shutil.rmtree(run_dir)

    paper_exact_count = sum(
        row["paper_reference_replay"]["exact_full_report_match"] for row in run_rows
    )
    post_exact_count = None
    if not args.skip_post_paper:
        post_exact_count = sum(
            row["post_paper_reference_replay"]["exact_full_report_match"] for row in run_rows
        )

    evaluator_meta = str(
        git(evaluator_repo, "show", "-s", "--format=%aI%x00%cI%x00%s", EVALUATOR_REVISION)
    ).strip().split("\x00")
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "official_experiments": {
            "repository": "https://github.com/SWE-bench/experiments",
            "revision": experiments_commit,
            "access_method": "git cat-file --batch; exact prediction, result, and requested log blobs only",
        },
        "historical_evaluator": {
            "repository": "https://github.com/SWE-bench/SWE-bench",
            "revision": evaluator_commit,
            "author_date": evaluator_meta[0],
            "commit_date": evaluator_meta[1],
            "subject": evaluator_meta[2],
            "reported_package_version": getattr(swebench, "__version__", "unknown"),
            "get_model_report_source_sha256": sha256_bytes(source_text.encode("utf-8")),
        },
        "historical_semantics": {
            "prediction_iteration": "JSONL lines are processed in order without deduplication.",
            "empty_patch": "Both null and whitespace-only strings enter no_generation.",
            "log_lookup": "Each non-empty line reads <instance_id>.<run>.eval.log; duplicate lines reuse the same log.",
            "no_apply": "Either pred_try or pred_minimal_try apply-failure marker is sufficient.",
            "resolved": "Only RESOLVED_FULL enters resolved.",
        },
        "datasets": dataset_manifest,
        "runs": run_rows,
        "summary": {
            "run_count": len(run_rows),
            "paper_reference_exact_match_count": paper_exact_count,
            "all_paper_reference_reports_exact": paper_exact_count == len(run_rows),
            "post_paper_reference_exact_match_count": post_exact_count,
            "all_post_paper_reference_reports_exact": None
            if post_exact_count is None
            else post_exact_count == len(run_rows),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"paper_exact={paper_exact_count}/{len(run_rows)} "
        f"post_paper_exact={post_exact_count}/{len(run_rows) if post_exact_count is not None else 'n/a'}",
        flush=True,
    )
    print(f"manifest={args.output}", flush=True)
    return 0 if paper_exact_count == len(run_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
