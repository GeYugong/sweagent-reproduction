#!/usr/bin/env python3
"""Prepare, run, and collect one paper-era gold evaluation per repository."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


DATASET_REVISION = "81ad348adcaf3368691f4db2907f8fc97a8f7526"
DATASET_SHA256 = "2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1"
EXPERIMENTS_REVISION = "a5d52722965c791c0c04d18135f906b44f716d39"
OFFICIAL_RUN = "20240402_sweagent_gpt4"
SWE_AGENT_REVISION = "658eb2842e8a8b00069b301338bc342b70538f7a"
SWE_BENCH_REVISION = "cfb20092bbbee9683176177b2f59b85f522e7f27"
REUSED_PYTEST_MANIFEST = "data/manifests/official_gold_no_apply_replay.json"
REQUESTS_SEMANTIC_MANIFEST = (
    "data/manifests/requests_offhost_redirect_validation.json"
)

REPOSITORY_COMPATIBILITY = {
    "astropy/astropy": ["setuptools==68.0.0"],
    "matplotlib/matplotlib": [
        "ghostscript 10.02.1~dfsg1-0ubuntu7.8",
        "texlive-latex-base 2023.20240207-1",
        "texlive-latex-extra 2023.20240207-1",
        "dvipng 1.15-1.1",
    ],
    "psf/requests": [
        "public off-host redirect dependency replaced by local cross-host semantic validation"
    ],
    "pydata/xarray": [
        "libmamba dependency solver",
        "numpy==1.23.0",
        "pytest==7.4.0",
        "setuptools==68.0.0",
    ],
    "pylint-dev/pylint": [
        "removed unavailable development-only types-pkg_resources==0.1.3"
    ],
    "sphinx-doc/sphinx": ["setuptools==69.5.1"],
}

OFFICIAL_COMPATIBILITY_EVIDENCE = [
    "validation/lite_20240627/pydata__xarray-4248/report.json",
    "validation/lite_20240627/pydata__xarray-4248/test_output.txt",
    "validation/lite_20240627/pylint-dev__pylint-5859/report.json",
    "validation/lite_20240627/pylint-dev__pylint-5859/test_output.txt",
    "validation/lite_20240627/sphinx-doc__sphinx-8713/report.json",
    "validation/lite_20240627/sphinx-doc__sphinx-8713/test_output.txt",
]

EXPECTED_SELECTION = {
    "astropy/astropy": "astropy__astropy-14995",
    "django/django": "django__django-13447",
    "matplotlib/matplotlib": "matplotlib__matplotlib-23964",
    "mwaskom/seaborn": "mwaskom__seaborn-3010",
    "pallets/flask": "pallets__flask-4992",
    "psf/requests": "psf__requests-2317",
    "pydata/xarray": "pydata__xarray-4248",
    "pylint-dev/pylint": "pylint-dev__pylint-5859",
    "pytest-dev/pytest": "pytest-dev__pytest-5227",
    "scikit-learn/scikit-learn": "scikit-learn__scikit-learn-13584",
    "sphinx-doc/sphinx": "sphinx-doc__sphinx-8713",
    "sympy/sympy": "sympy__sympy-24152",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob(repo: Path, revision: str, path: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace"))
    return process.stdout


def git_object_id(repo: Path, revision: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{revision}:{path}"], cwd=repo, text=True
    ).strip()


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()


def normalize_tests(value: Any) -> list[str]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("Invalid SWE-bench test reference")
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def ensure_output_path(path: Path, project_root: Path) -> None:
    allowed = (project_root / "outputs" / "evaluation").resolve()
    resolved = path.resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise RuntimeError(f"Unsafe output path: {resolved}")


def repository_key(repository: str) -> str:
    return repository.replace("/", "__")


def model_alias(repository: str) -> str:
    value = "paper_replay_gold_" + repository.replace("/", "_")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", value) is None:
        raise ValueError(f"Invalid model alias for {repository}")
    return value


def load_paper_tasks(parquet_path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for prepare") from exc
    if sha256_file(parquet_path) != DATASET_SHA256:
        raise RuntimeError(f"Paper Lite Parquet hash mismatch: {parquet_path}")
    rows = []
    for raw in pq.read_table(parquet_path).to_pylist():
        row = dict(raw)
        row["FAIL_TO_PASS"] = normalize_tests(row["FAIL_TO_PASS"])
        row["PASS_TO_PASS"] = normalize_tests(row["PASS_TO_PASS"])
        rows.append(row)
    return rows


def select_instances(
    tasks: list[dict[str, Any]], resolved: set[str]
) -> list[tuple[dict[str, Any], str]]:
    repositories = sorted({task["repo"] for task in tasks})
    if repositories != sorted(EXPECTED_SELECTION):
        raise RuntimeError(f"Unexpected paper Lite repository set: {repositories}")
    selected = []
    for repository in repositories:
        candidates = [task for task in tasks if task["repo"] == repository]
        resolved_candidates = [
            task for task in candidates if task["instance_id"] in resolved
        ]
        pool = resolved_candidates or candidates
        policy = (
            "minimum_reference_tests_among_official_gpt4_resolved"
            if resolved_candidates
            else "minimum_reference_tests_no_official_gpt4_resolved_available"
        )
        task = min(
            pool,
            key=lambda item: (
                len(item["FAIL_TO_PASS"]) + len(item["PASS_TO_PASS"]),
                len(item["patch"].encode("utf-8")),
                item["instance_id"],
            ),
        )
        if task["instance_id"] != EXPECTED_SELECTION[repository]:
            raise RuntimeError(
                f"Selection drift for {repository}: {task['instance_id']}"
            )
        selected.append((task, policy))
    return selected


def prepare(
    project_root: Path,
    experiments_repo: Path,
    parquet_path: Path,
    output_dir: Path,
    selection_manifest_path: Path,
) -> int:
    ensure_output_path(output_dir, project_root)
    if git_head(project_root / "code" / "SWE-agent") != SWE_AGENT_REVISION:
        raise RuntimeError("SWE-agent checkout revision mismatch")
    if git_head(project_root / "code" / "SWE-bench") != SWE_BENCH_REVISION:
        raise RuntimeError("SWE-bench checkout revision mismatch")

    tasks = load_paper_tasks(parquet_path)
    official_results = json.loads(
        git_blob(
            experiments_repo,
            EXPERIMENTS_REVISION,
            f"evaluation/lite/{OFFICIAL_RUN}/results/results.json",
        )
    )
    resolved = set(official_results["resolved"])
    selected = select_instances(tasks, resolved)
    records = []
    for task, policy in selected:
        repository = task["repo"]
        key = repository_key(repository)
        input_dir = output_dir / "inputs" / key
        input_dir.mkdir(parents=True, exist_ok=True)
        predictions_path = input_dir / "all_preds.jsonl"
        tasks_path = input_dir / "tasks.jsonl"
        prediction = {
            "instance_id": task["instance_id"],
            "model_name_or_path": "gold_patch",
            "model_patch": task["patch"],
        }
        write_jsonl(predictions_path, [prediction])
        write_jsonl(tasks_path, [task])

        official_categories = [
            category
            for category, values in official_results.items()
            if task["instance_id"] in values
        ]
        official_log_record = None
        if task["instance_id"] in resolved:
            log_name = f"{task['instance_id']}.{OFFICIAL_RUN}.eval.log"
            log_source = f"evaluation/lite/{OFFICIAL_RUN}/logs/{log_name}"
            log_payload = git_blob(experiments_repo, EXPERIMENTS_REVISION, log_source)
            official_log_path = input_dir / "official_resolved.eval.log"
            official_log_path.write_bytes(log_payload)
            official_log_record = {
                "source": log_source,
                "git_blob": git_object_id(
                    experiments_repo, EXPERIMENTS_REVISION, log_source
                ),
                "sha256": sha256_bytes(log_payload),
            }

        record = {
            "repository": repository,
            "repository_key": key,
            "instance_id": task["instance_id"],
            "version": str(task["version"]),
            "base_commit": task["base_commit"],
            "selection_policy": policy,
            "official_categories": official_categories,
            "official_resolved_log": official_log_record,
            "fail_to_pass_count": len(task["FAIL_TO_PASS"]),
            "pass_to_pass_count": len(task["PASS_TO_PASS"]),
            "gold_patch_bytes": len(task["patch"].encode("utf-8")),
            "gold_patch_sha256": sha256_bytes(task["patch"].encode("utf-8")),
            "test_patch_sha256": sha256_bytes(task["test_patch"].encode("utf-8")),
            "model_alias": model_alias(repository),
            "input_directory": str(Path("inputs") / key),
            "predictions_sha256": sha256_file(predictions_path),
            "tasks_sha256": sha256_file(tasks_path),
            "execution": (
                "reuse_EXP-ARTIFACT-006_gold"
                if repository == "pytest-dev/pytest"
                else "pending_local_paper_evaluator"
            ),
        }
        write_json(input_dir / "input_manifest.json", record)
        records.append(record)

    master = {
        "schema_version": 1,
        "status": "PREPARED_12_REPOSITORIES_11_PENDING_1_REUSED",
        "prepared_at_utc": utc_now(),
        "selection_policy": (
            "For each paper Lite repository, choose the instance with the fewest "
            "F2P+P2P references among official GPT-4 resolved instances. If the run "
            "has no resolved instance for that repository, choose the minimum over "
            "all Lite instances. Break ties by gold-patch bytes then instance ID."
        ),
        "paper_repositories": sorted(EXPECTED_SELECTION),
        "dataset": {
            "repository": "princeton-nlp/SWE-bench_Lite",
            "revision": DATASET_REVISION,
            "sha256": DATASET_SHA256,
            "rows": len(tasks),
        },
        "official_experiments_revision": EXPERIMENTS_REVISION,
        "official_run": OFFICIAL_RUN,
        "swe_agent_revision": SWE_AGENT_REVISION,
        "swe_bench_revision": SWE_BENCH_REVISION,
        "transport_policy": "process-scoped Git HTTP/1.1; no global Git mutation",
        "model_api_calls": 0,
        "instances": records,
    }
    write_json(output_dir / "input_manifest.json", master)
    write_json(selection_manifest_path, master)
    print(f"prepared={len(records)} repositories")
    print(f"pending={sum(row['execution'].startswith('pending') for row in records)}")
    print(f"manifest={output_dir / 'input_manifest.json'}")
    print(f"selection_manifest={selection_manifest_path}")
    return 0


def expected_scorecard_present(
    path: Path, instance_id: str, input_dir: Path, source_path: Path
) -> bool:
    if not path.is_file():
        return False
    cards = json.loads(path.read_text(encoding="utf-8"))
    attempt = latest_attempt(input_dir)
    return bool(
        len(cards) == 1
        and cards[0].get("instance_id") == instance_id
        and cards[0].get("statuses") == ["generated", "applied", "RESOLVED_FULL"]
        and attempt is not None
        and attempt.get("protocol_valid") is True
        and attempt.get("swebench_import_source") == str(source_path)
    )


def run_selected(
    project_root: Path,
    output_dir: Path,
    testbed: Path,
    timeout: int,
    repositories: list[str],
    force: bool,
    conda_solver: str | None,
) -> int:
    ensure_output_path(output_dir, project_root)
    master_path = output_dir / "input_manifest.json"
    if not master_path.is_file():
        raise FileNotFoundError("Run prepare before run")
    master = json.loads(master_path.read_text(encoding="utf-8"))
    requested = set(repositories)
    known = {row["repository"] for row in master["instances"]}
    if requested - known:
        raise ValueError(f"Unknown repositories: {sorted(requested - known)}")

    env = os.environ.copy()
    scrubbed = []
    for name in list(env):
        if re.search(r"(OPENAI|ANTHROPIC|CLAUDE).*(KEY|TOKEN|URL)", name):
            scrubbed.append(name)
            env.pop(name, None)
    env.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.version",
            "GIT_CONFIG_VALUE_0": "HTTP/1.1",
            "PYTHONPATH": str(project_root / "code" / "SWE-bench"),
        }
    )
    if conda_solver:
        env["CONDA_SOLVER"] = conda_solver

    source_path = project_root / "code" / "SWE-bench"
    preflight = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "import ghapi, pandas, requests; "
                "from swebench.harness import context_manager; "
                f"expected=Path({str(source_path)!r}).resolve(); "
                "actual=Path(context_manager.__file__).resolve(); "
                "assert expected in actual.parents, (expected, actual); "
                "print(actual)"
            ),
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if preflight.returncode != 0:
        raise RuntimeError(
            "Outer evaluator runtime preflight failed before creating an attempt:\n"
            + preflight.stdout
            + preflight.stderr
        )
    print(
        f"outer_runtime={sys.executable} swebench_source={preflight.stdout.strip()} "
        f"conda_solver={conda_solver or 'default'}",
        flush=True,
    )

    failures = []
    for row in master["instances"]:
        repository = row["repository"]
        if repository == "pytest-dev/pytest":
            continue
        if requested and repository not in requested:
            continue
        input_dir = output_dir / row["input_directory"]
        scorecards_path = input_dir / "scorecards.json"
        if not force and expected_scorecard_present(
            scorecards_path, row["instance_id"], input_dir, source_path
        ):
            print(f"[{repository}] skip=existing_RESOLVED_FULL", flush=True)
            continue

        attempts_dir = input_dir / "attempts"
        for incomplete in sorted(attempts_dir.glob("attempt_*")):
            incomplete_manifest = incomplete / "attempt.json"
            if incomplete_manifest.exists():
                continue
            runner_log = incomplete / "runner.log"
            recovered = {
                "schema_version": 1,
                "repository": repository,
                "instance_id": row["instance_id"],
                "attempt": int(incomplete.name.rsplit("_", 1)[-1]),
                "status": "INTERRUPTED_OUTER_RUNNER_NO_RETURN_CODE",
                "detected_at_utc": utc_now(),
                "return_code": None,
                "scorecard_statuses": None,
                "success": False,
                "protocol_valid": False,
                "model_api_calls": 0,
                "runner_log_sha256": (
                    sha256_file(runner_log) if runner_log.is_file() else None
                ),
            }
            write_json(incomplete_manifest, recovered)
        attempt_number = len(list(attempts_dir.glob("attempt_*"))) + 1
        attempt_dir = attempts_dir / f"attempt_{attempt_number:03d}"
        attempt_dir.mkdir(parents=True)
        log_path = attempt_dir / "runner.log"
        results_dir = output_dir / "results"
        command = [
            sys.executable,
            str(project_root / "scripts" / "run_local_evaluation.py"),
            str(input_dir / "all_preds.jsonl"),
            "--dataset",
            str(input_dir / "tasks.jsonl"),
            "--results",
            str(results_dir),
            "--testbed",
            str(testbed),
            "--timeout",
            str(timeout),
            "--model-alias",
            row["model_alias"],
        ]
        started = utc_now()
        start_clock = time.monotonic()
        print(
            f"[{repository}] attempt={attempt_number} instance={row['instance_id']} start",
            flush=True,
        )
        with log_path.open("w", encoding="utf-8", newline="\n") as log_handle:
            process = subprocess.Popen(
                command,
                cwd=project_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                log_handle.write(line)
                log_handle.flush()
                if any(
                    marker in line
                    for marker in (
                        "Setting up testbed",
                        "Creating environment",
                        "Cloned ",
                        "Finished evaluation",
                        "Evaluation failed",
                        "Wrote per-instance scorecards",
                    )
                ):
                    print(f"[{repository}] {line.rstrip()}", flush=True)
            return_code = process.wait()
        duration = time.monotonic() - start_clock

        artifacts = {}
        candidates = {
            "scorecards": scorecards_path,
            "results": input_dir / "results.json",
            "evaluation_log": (
                results_dir
                / row["model_alias"]
                / f"{row['instance_id']}.{row['model_alias']}.eval.log"
            ),
        }
        for name, source in candidates.items():
            if source.is_file():
                destination = attempt_dir / source.name
                shutil.copy2(source, destination)
                artifacts[name] = {
                    "path": str(destination.relative_to(output_dir)),
                    "sha256": sha256_file(destination),
                }
        statuses = None
        if scorecards_path.is_file():
            cards = json.loads(scorecards_path.read_text(encoding="utf-8"))
            if len(cards) == 1:
                statuses = cards[0].get("statuses")
        success = return_code == 0 and statuses == [
            "generated",
            "applied",
            "RESOLVED_FULL",
        ]
        attempt = {
            "schema_version": 1,
            "repository": repository,
            "instance_id": row["instance_id"],
            "attempt": attempt_number,
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "duration_seconds": round(duration, 3),
            "return_code": return_code,
            "scorecard_statuses": statuses,
            "success": success,
            "protocol_valid": True,
            "swebench_revision": SWE_BENCH_REVISION,
            "timeout_seconds": timeout,
            "outer_python": sys.executable,
            "conda_solver": conda_solver or "default",
            "git_transport": "HTTP/1.1 process scope",
            "swebench_import_source": str(source_path),
            "compatibility": [
                "source checkout forced through PYTHONPATH",
                "conda activation uses etc/profile.d/conda.sh",
                "instance-scoped package constraints from run_local_evaluation.py",
            ]
            + ([f"conda solver set to {conda_solver}"] if conda_solver else []),
            "credential_variables_scrubbed": sorted(scrubbed),
            "model_api_calls": 0,
            "artifacts": artifacts,
            "runner_log_sha256": sha256_file(log_path),
        }
        write_json(attempt_dir / "attempt.json", attempt)
        print(
            f"[{repository}] return={return_code} statuses={statuses} "
            f"duration={duration:.1f}s",
            flush=True,
        )
        if not success:
            failures.append(repository)

    print(f"run_failures={len(failures)}", flush=True)
    if failures:
        print("failed_repositories=" + ",".join(failures), flush=True)
    return 1 if failures else 0


def expected_full_report(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "FAIL_TO_PASS": {"success": reference["FAIL_TO_PASS"], "failure": []},
        "PASS_TO_PASS": {"success": reference["PASS_TO_PASS"], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": []},
        "PASS_TO_FAIL": {"success": [], "failure": []},
    }


def latest_attempt(input_dir: Path) -> dict[str, Any] | None:
    attempts = attempt_history(input_dir)
    if not attempts:
        return None
    return attempts[-1]


def attempt_history(input_dir: Path) -> list[dict[str, Any]]:
    paths = sorted((input_dir / "attempts").glob("attempt_*/attempt.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def collect(
    project_root: Path,
    output_dir: Path,
    manifest_path: Path,
) -> int:
    source_path = str(project_root / "code" / "SWE-bench")
    if source_path not in sys.path:
        sys.path.insert(0, source_path)
    from swebench import get_eval_refs, get_eval_report, get_logs_eval, get_resolution_status
    from swebench.harness.constants import APPLY_PATCH_PASS
    from swebench.metrics.log_parsers import MAP_REPO_TO_PARSER

    def parse_eval_log(path: Path, repository: str) -> tuple[dict[str, Any], bool]:
        content = path.read_text(encoding="utf-8")
        required_markers = [
            f"{APPLY_PATCH_PASS} (test)",
            f"{APPLY_PATCH_PASS} (pred)",
        ]
        if any(marker not in content for marker in required_markers):
            return {}, False
        content = content.split(f"{APPLY_PATCH_PASS} (pred)")[-1]
        return MAP_REPO_TO_PARSER[repository](content), True

    ensure_output_path(output_dir, project_root)
    master_path = output_dir / "input_manifest.json"
    master = json.loads(master_path.read_text(encoding="utf-8"))
    reused = json.loads(
        (project_root / REUSED_PYTEST_MANIFEST).read_text(encoding="utf-8")
    )
    reused_gold = next(
        row
        for row in reused["observations"]
        if row.get("instance_id") == "pytest-dev__pytest-5227"
        and row.get("patch_state") == "gold"
    )
    requests_semantic_path = project_root / REQUESTS_SEMANTIC_MANIFEST
    requests_semantic = json.loads(
        requests_semantic_path.read_text(encoding="utf-8")
    )
    experiments_repo = project_root / "code" / "SWE-bench-experiments"
    experiments_revision = git_head(experiments_repo)
    official_compatibility_files = []
    for relative_path in OFFICIAL_COMPATIBILITY_EVIDENCE:
        evidence_path = experiments_repo / relative_path
        working_sha256 = sha256_file(evidence_path)
        revision_sha256 = sha256_bytes(
            git_blob(experiments_repo, experiments_revision, relative_path)
        )
        official_compatibility_files.append(
            {
                "path": relative_path,
                "bytes": evidence_path.stat().st_size,
                "sha256": working_sha256,
                "git_object_id": git_object_id(
                    experiments_repo, experiments_revision, relative_path
                ),
                "matches_repository_revision": working_sha256
                == revision_sha256,
            }
        )
    if not all(
        item["matches_repository_revision"]
        for item in official_compatibility_files
    ):
        raise RuntimeError(
            "Official compatibility evidence differs from the pinned repository revision"
        )

    observations = []
    for source in master["instances"]:
        repository = source["repository"]
        if repository == "pytest-dev/pytest":
            exact = (
                reused["status"] == "COMPLETE_EXACT"
                and reused_gold["patch_sha256"] == source["gold_patch_sha256"]
                and reused_gold["observed_scorecard_statuses"]
                == ["generated", "applied", "RESOLVED_FULL"]
                and reused_gold["all_reference_tests_passed"]
                and reused_gold["exact_outcome_match"]
            )
            observations.append(
                {
                    **source,
                    "evidence": "reused_EXP-ARTIFACT-006_gold",
                    "observed_scorecard_statuses": reused_gold[
                        "observed_scorecard_statuses"
                    ],
                    "observed_resolution": reused_gold["observed_resolution"],
                    "all_reference_tests_passed": reused_gold[
                        "all_reference_tests_passed"
                    ],
                    "observed_log_sha256": reused_gold["observed_log_sha256"],
                    "exact_outcome_match": exact,
                    "full_reference_outcome_match": exact,
                    "semantic_outcome_match": False,
                    "validated_outcome_match": exact,
                    "validation_class": (
                        "full_reference_outcome" if exact else "failed"
                    ),
                    "reference_success_count": (
                        source["fail_to_pass_count"]
                        + source["pass_to_pass_count"]
                        if exact
                        else 0
                    ),
                    "reference_failure_count": 0 if exact else (
                        source["fail_to_pass_count"]
                        + source["pass_to_pass_count"]
                    ),
                    "environment_compatibility": REPOSITORY_COMPATIBILITY.get(
                        repository, []
                    ),
                }
            )
            continue

        input_dir = output_dir / source["input_directory"]
        tasks_path = input_dir / "tasks.jsonl"
        scorecards_path = input_dir / "scorecards.json"
        observed_log = (
            output_dir
            / "results"
            / source["model_alias"]
            / f"{source['instance_id']}.{source['model_alias']}.eval.log"
        )
        observation = {
            **source,
            "evidence": "fresh_gold_evaluator_replay",
            "latest_attempt": latest_attempt(input_dir),
            "attempt_history": attempt_history(input_dir),
            "environment_compatibility": REPOSITORY_COMPATIBILITY.get(
                repository, []
            ),
        }
        if not scorecards_path.is_file() or not observed_log.is_file():
            observation.update(
                {
                    "observed_scorecard_statuses": None,
                    "observed_resolution": None,
                    "all_reference_tests_passed": False,
                    "exact_outcome_match": False,
                    "full_reference_outcome_match": False,
                    "semantic_outcome_match": False,
                    "validated_outcome_match": False,
                    "validation_class": "missing_output",
                }
            )
            observations.append(observation)
            continue

        cards = json.loads(scorecards_path.read_text(encoding="utf-8"))
        refs = get_eval_refs(str(tasks_path))
        reference = refs[source["instance_id"]]
        status_map, patch_applied = get_logs_eval(str(observed_log))
        report = get_eval_report(status_map, reference)
        resolution = get_resolution_status(report)
        expected = expected_full_report(reference)
        card = cards[0] if len(cards) == 1 else {}
        official_report_exact = None
        if source["official_resolved_log"] is not None:
            official_log = input_dir / "official_resolved.eval.log"
            official_map, official_applied = parse_eval_log(
                official_log, repository
            )
            official_report = get_eval_report(official_map, reference)
            official_report_exact = official_applied and official_report == report
        attempt = latest_attempt(input_dir)
        exact = (
            len(cards) == 1
            and card.get("instance_id") == source["instance_id"]
            and card.get("statuses") == ["generated", "applied", "RESOLVED_FULL"]
            and patch_applied
            and resolution == "RESOLVED_FULL"
            and report == expected
            and (official_report_exact is not False)
            and attempt is not None
            and attempt.get("protocol_valid") is True
            and attempt.get("swebench_revision") == SWE_BENCH_REVISION
        )
        requests_semantic_match = (
            repository == "psf/requests"
            and source["instance_id"] == requests_semantic.get("instance_id")
            and source["base_commit"]
            == requests_semantic.get("source_base_commit")
            and source["gold_patch_sha256"]
            == requests_semantic.get("gold_patch_sha256")
            and source["test_patch_sha256"]
            == requests_semantic.get("test_patch_sha256")
            and patch_applied
            and report["FAIL_TO_PASS"]["failure"] == []
            and len(report["FAIL_TO_PASS"]["success"])
            == source["fail_to_pass_count"]
            and report["PASS_TO_PASS"]["failure"]
            == [
                "test_requests.py::RequestsTestCase::"
                "test_auth_is_stripped_on_redirect_off_host"
            ]
            and len(report["PASS_TO_PASS"]["success"])
            == source["pass_to_pass_count"] - 1
            and requests_semantic.get("status_code") == 200
            and requests_semantic.get("history_length") == 1
            and requests_semantic.get("initial_authorization_present") is True
            and requests_semantic.get("final_authorization_absent_client") is True
            and requests_semantic.get("final_authorization_absent_server") is True
        )
        validated = exact or requests_semantic_match
        observation.update(
            {
                "observed_scorecard_statuses": card.get("statuses"),
                "observed_patch_applied": patch_applied,
                "observed_resolution": resolution,
                "all_reference_tests_passed": report == expected,
                "official_resolved_report_exact": official_report_exact,
                "observed_log_sha256": sha256_file(observed_log),
                "exact_outcome_match": exact,
                "full_reference_outcome_match": exact,
                "semantic_outcome_match": requests_semantic_match,
                "validated_outcome_match": validated,
                "validation_class": (
                    "full_reference_outcome"
                    if exact
                    else (
                        "external_network_semantic"
                        if requests_semantic_match
                        else "failed"
                    )
                ),
                "reference_success_count": len(
                    report["FAIL_TO_PASS"]["success"]
                )
                + len(report["PASS_TO_PASS"]["success"]),
                "reference_failure_count": len(
                    report["FAIL_TO_PASS"]["failure"]
                )
                + len(report["PASS_TO_PASS"]["failure"]),
            }
        )
        observations.append(observation)

    exact_count = sum(row["exact_outcome_match"] for row in observations)
    semantic_count = sum(row["semantic_outcome_match"] for row in observations)
    validated_count = sum(row["validated_outcome_match"] for row in observations)
    all_exact = exact_count == len(observations) == len(EXPECTED_SELECTION)
    all_validated = validated_count == len(observations) == len(EXPECTED_SELECTION)
    csv_path = project_root / "data" / "derived" / "official_gold_repository_replay.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "repository",
        "instance_id",
        "version",
        "selection_policy",
        "fail_to_pass_count",
        "pass_to_pass_count",
        "gold_patch_sha256",
        "evidence",
        "observed_resolution",
        "all_reference_tests_passed",
        "official_resolved_report_exact",
        "exact_outcome_match",
        "semantic_outcome_match",
        "validated_outcome_match",
        "validation_class",
        "reference_success_count",
        "reference_failure_count",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in observations:
            writer.writerow({field: row.get(field) for field in fields})

    manifest = {
        **master,
        "status": (
            "COMPLETE_12_OF_12_GOLD_REPOSITORY_ENVIRONMENTS"
            if all_exact
            else (
                "COMPLETE_11_FULL_REFERENCE_1_EXTERNAL_NETWORK_SEMANTIC"
                if all_validated and exact_count == 11 and semantic_count == 1
                else (
                    f"PARTIAL_{validated_count}_OF_12_"
                    "GOLD_REPOSITORY_ENVIRONMENTS"
                )
            )
        ),
        "collected_at_utc": utc_now(),
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "model_api_calls": 0,
            "gpu_used": False,
            "server_used": False,
        },
        "input_manifest_sha256": sha256_file(master_path),
        "requests_semantic_manifest": {
            "path": REQUESTS_SEMANTIC_MANIFEST,
            "sha256": sha256_file(requests_semantic_path),
        },
        "official_compatibility_evidence": {
            "repository": "SWE-bench/experiments",
            "revision": experiments_revision,
            "files": official_compatibility_files,
        },
        "observations": observations,
        "outputs": {
            "summary_csv": {
                "path": str(csv_path.relative_to(project_root)).replace("\\", "/"),
                "bytes": csv_path.stat().st_size,
                "sha256": sha256_file(csv_path),
            }
        },
        "summary": {
            "repository_count": len(observations),
            "fresh_repository_count": sum(
                row["evidence"] == "fresh_gold_evaluator_replay"
                for row in observations
            ),
            "reused_repository_count": sum(
                row["evidence"] == "reused_EXP-ARTIFACT-006_gold"
                for row in observations
            ),
            "fresh_attempt_count": sum(
                len(row.get("attempt_history", [])) for row in observations
            ),
            "unsuccessful_fresh_attempt_count": sum(
                not attempt.get("success", False)
                for row in observations
                for attempt in row.get("attempt_history", [])
            ),
            "protocol_valid_successful_fresh_attempt_count": sum(
                attempt.get("success") is True
                and attempt.get("protocol_valid") is True
                for row in observations
                for attempt in row.get("attempt_history", [])
            ),
            "exact_outcome_match_count": exact_count,
            "semantic_outcome_match_count": semantic_count,
            "validated_outcome_match_count": validated_count,
            "all_exact": all_exact,
            "all_validated": all_validated,
        },
    }
    write_json(manifest_path, manifest)
    print(f"exact={exact_count}/{len(observations)}")
    print(f"semantic={semantic_count}/{len(observations)}")
    print(f"validated={validated_count}/{len(observations)}")
    print(f"manifest={manifest_path}")
    return 0 if all_validated else 1


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "collect"))
    parser.add_argument(
        "--experiments-repo",
        type=Path,
        default=project_root / "code" / "SWE-bench-experiments",
    )
    parser.add_argument(
        "--parquet",
        type=Path,
        default=(
            project_root
            / "data"
            / "cache"
            / "paper_evaluator"
            / "lite_paper_81ad348a.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            project_root
            / "outputs"
            / "evaluation"
            / "official_gold_repository_replay"
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=(
            project_root
            / "data"
            / "manifests"
            / "official_gold_repository_replay.json"
        ),
    )
    parser.add_argument(
        "--selection-manifest",
        type=Path,
        default=(
            project_root
            / "data"
            / "manifests"
            / "official_gold_repository_selection.json"
        ),
    )
    parser.add_argument("--testbed", type=Path, default=Path("/home/gugabobo/sb"))
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--repository", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--conda-solver", choices=("classic", "libmamba"))
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if args.mode == "prepare":
        return prepare(
            project_root,
            args.experiments_repo.resolve(),
            args.parquet.resolve(),
            output_dir,
            args.selection_manifest.resolve(),
        )
    if args.mode == "run":
        return run_selected(
            project_root,
            output_dir,
            args.testbed.resolve(),
            args.timeout,
            args.repository,
            args.force,
            args.conda_solver,
        )
    return collect(project_root, output_dir, args.manifest.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
