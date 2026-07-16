#!/usr/bin/env python3
"""Run the paper-time SWE-bench evaluator with an explicit PyPI drift shim."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from swebench.harness import context_manager


def install_requirements_compatibility() -> None:
    original = context_manager.get_requirements
    original_exec = context_manager.ExecWrapper.__call__

    def get_requirements_compat(instance: dict, save_path: Optional[str] = None):
        result = original(instance, save_path)
        if save_path is not None:
            candidate = Path(result)
        else:
            candidate = None
        if candidate is not None and candidate.is_file():
            content = candidate.read_text(encoding="utf-8")
            candidate.write_text(
                content.replace("types-pkg_resources", "types-setuptools"),
                encoding="utf-8",
            )
            return result
        if isinstance(result, str):
            return result.replace("types-pkg_resources", "types-setuptools")
        return result

    context_manager.get_requirements = get_requirements_compat

    def exec_compat(self, cmd, raise_error=True, **kwargs):
        if isinstance(cmd, list):
            cmd = [part for part in cmd if part != ""]
        return original_exec(self, cmd, raise_error=raise_error, **kwargs)

    context_manager.ExecWrapper.__call__ = exec_compat


def configure_conda_downloads() -> None:
    defaults = {
        "CONDA_REMOTE_CONNECT_TIMEOUT_SECS": "60",
        "CONDA_REMOTE_READ_TIMEOUT_SECS": "180",
        "CONDA_REMOTE_MAX_RETRIES": "10",
        "CONDA_DEFAULT_THREADS": "1",
        "CONDA_SOLVER": "classic",
    }
    for name, value in defaults.items():
        os.environ.setdefault(name, value)


def configure_pip_constraints(predictions: Path, staging_dir: Path) -> Optional[Path]:
    """Constrain packages whose post-paper releases break frozen repositories."""
    instance_ids = set()
    with predictions.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                instance_ids.add(record.get("instance_id", ""))
    constraints = []
    if any(instance_id.startswith("pvlib__pvlib-python-") for instance_id in instance_ids):
        constraints.append("numpy<2")
    if not constraints:
        os.environ.pop("PIP_CONSTRAINT", None)
        return None
    constraint_path = staging_dir / "pip-constraints.txt"
    constraint_path.write_text("\n".join(constraints) + "\n", encoding="utf-8")
    os.environ["PIP_CONSTRAINT"] = str(constraint_path.resolve())
    return constraint_path


def install_test_runner_compatibility(predictions: Path) -> None:
    instance_ids = set()
    with predictions.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                instance_ids.add(record.get("instance_id", ""))
    if not any(instance_id.startswith("pydicom__pydicom-") for instance_id in instance_ids):
        return
    for install_config in context_manager.MAP_VERSION_TO_INSTALL["pydicom/pydicom"].values():
        pip_packages = install_config.get("pip_packages", "").split()
        if not any(package.startswith("pytest") for package in pip_packages):
            pip_packages.append("pytest==7.4.4")
        install_config["pip_packages"] = " ".join(pip_packages)


def load_paper_evaluator(repo_root: Path):
    evaluator_path = repo_root / "code" / "SWE-agent" / "evaluation" / "evaluation.py"
    spec = importlib.util.spec_from_file_location("paper_evaluation", evaluator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load evaluator: {evaluator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--testbed", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--model-alias")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    original_predictions = args.predictions.resolve()
    if not original_predictions.is_file():
        raise FileNotFoundError(original_predictions)
    args.results.mkdir(parents=True, exist_ok=True)
    args.testbed.mkdir(parents=True, exist_ok=True)

    alias = args.model_alias or (
        "eval_" + hashlib.sha256(original_predictions.parent.name.encode()).hexdigest()[:8]
    )
    if re.fullmatch(r"[A-Za-z0-9_.-]+", alias) is None:
        raise ValueError("model alias contains unsupported characters")
    staging_dir = args.testbed.resolve().parent / "eval_inputs" / alias
    staging_dir.mkdir(parents=True, exist_ok=True)
    predictions = staging_dir / "all_preds.jsonl"
    shutil.copy2(original_predictions, predictions)
    for trajectory in original_predictions.parent.glob("*.traj"):
        shutil.copy2(trajectory, staging_dir / trajectory.name)
    for stale_name in ("scorecards.json", "results.json"):
        stale_path = staging_dir / stale_name
        if stale_path.exists():
            stale_path.unlink()

    configure_conda_downloads()
    configure_pip_constraints(predictions, staging_dir)
    install_test_runner_compatibility(predictions)
    install_requirements_compatibility()
    evaluator = load_paper_evaluator(repo_root)
    evaluator.main(
        predictions_path=str(predictions),
        log_dir=str(args.results.resolve()),
        swe_bench_tasks=args.dataset,
        testbed=str(args.testbed.resolve()),
        skip_existing=False,
        timeout=args.timeout,
        verbose=True,
        conda_link=None,
        log_suffix="",
        num_processes=1,
    )

    scorecards_path = staging_dir / "scorecards.json"
    if not scorecards_path.is_file():
        raise RuntimeError("Evaluator did not produce scorecards.json")
    shutil.copy2(scorecards_path, original_predictions.parent / "scorecards.json")
    results_path = staging_dir / "results.json"
    if results_path.is_file():
        shutil.copy2(results_path, original_predictions.parent / "results.json")
    scorecards = json.loads(scorecards_path.read_text(encoding="utf-8"))
    infrastructure_failures = {
        "build_failure",
        "install_failure",
    }
    if any(infrastructure_failures.intersection(card.get("statuses", [])) for card in scorecards):
        raise RuntimeError("Evaluator reported an infrastructure failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
