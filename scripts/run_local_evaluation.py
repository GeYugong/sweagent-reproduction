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
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SWE_BENCH_SOURCE = PROJECT_ROOT / "code" / "SWE-bench"
sys.path.insert(0, str(SWE_BENCH_SOURCE))

from swebench.harness import context_manager


def install_requirements_compatibility() -> None:
    original = context_manager.get_requirements
    original_exec = context_manager.ExecWrapper.__call__
    original_task_init = context_manager.TaskEnvContextManager.__init__

    def normalize_requirements(content: str, instance: dict) -> str:
        lines = [
            line
            for line in content.splitlines()
            if not re.match(r"^\s*types-pkg_resources(?:\s|[<>=!~]|$)", line)
        ]
        content = "\n".join(lines) + "\n"
        if instance.get("repo") == "pyvista/pyvista":
            lines = [line for line in content.splitlines() if line.strip() != "vtk"]
            lines.append("vtk<9.3")
            content = "\n".join(lines) + "\n"
        return content

    def get_requirements_compat(instance: dict, save_path: Optional[str] = None):
        result = original(instance, save_path)
        if save_path is not None:
            candidate = Path(result)
        else:
            candidate = None
        if candidate is not None and candidate.is_file():
            content = candidate.read_text(encoding="utf-8")
            candidate.write_text(normalize_requirements(content, instance), encoding="utf-8")
            return result
        if isinstance(result, str):
            return normalize_requirements(result, instance)
        return result

    context_manager.get_requirements = get_requirements_compat

    def exec_compat(self, cmd, raise_error=True, **kwargs):
        if isinstance(cmd, list):
            cmd = [part for part in cmd if part != ""]
        elif isinstance(cmd, str):
            cmd = re.sub(
                r"\. (?P<root>\S+)/bin/activate (?P<env>\S+) &&",
                (
                    r". \g<root>/etc/profile.d/conda.sh && "
                    r"conda activate \g<env> &&"
                ),
                cmd,
            )
        return original_exec(self, cmd, raise_error=raise_error, **kwargs)

    context_manager.ExecWrapper.__call__ = exec_compat

    def task_init_compat(self, *args, **kwargs):
        original_task_init(self, *args, **kwargs)
        self.cmd_activate = (
            f". {self.conda_path}/etc/profile.d/conda.sh && "
            f"conda activate {self.venv} && echo 'activate successful'"
        )
        if os.environ.get("PIP_CONSTRAINT"):
            self.exec.subprocess_args["env"]["PIP_CONSTRAINT"] = os.environ[
                "PIP_CONSTRAINT"
            ]

    context_manager.TaskEnvContextManager.__init__ = task_init_compat


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
    if any(instance_id.startswith("pyvista__pyvista-") for instance_id in instance_ids):
        constraints.append("vtk<9.3")
    if any(instance_id.startswith("astropy__astropy-") for instance_id in instance_ids):
        constraints.append("setuptools==68.0.0")
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
    if any(
        instance_id.startswith("pydicom__pydicom-") for instance_id in instance_ids
    ):
        for install_config in context_manager.MAP_VERSION_TO_INSTALL[
            "pydicom/pydicom"
        ].values():
            configured = install_config.get("pip_packages", [])
            pip_packages = (
                configured.split() if isinstance(configured, str) else list(configured)
            )
            python_version = str(install_config.get("python", ""))
            pytest_version = "6.2.5" if python_version.startswith("3.6") else "7.4.4"
            if not any(package.startswith("pytest") for package in pip_packages):
                pip_packages.append(f"pytest=={pytest_version}")
            install_config["pip_packages"] = pip_packages

    if any(
        instance_id.startswith("pydata__xarray-") for instance_id in instance_ids
    ):
        for install_config in context_manager.MAP_VERSION_TO_INSTALL[
            "pydata/xarray"
        ].values():
            configured = install_config.get("pip_packages", [])
            pip_packages = (
                configured.split() if isinstance(configured, str) else list(configured)
            )
            replacements = {
                "numpy": "numpy==1.23.0",
                "pytest": "pytest==7.4.0",
                "setuptools": "setuptools==68.0.0",
            }
            for package_name, pinned in replacements.items():
                pip_packages = [
                    package
                    for package in pip_packages
                    if not package.lower().startswith(package_name)
                ]
                pip_packages.append(pinned)
            install_config["pip_packages"] = pip_packages


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

    repo_root = PROJECT_ROOT
    imported_context = Path(context_manager.__file__).resolve()
    if SWE_BENCH_SOURCE.resolve() not in imported_context.parents:
        raise RuntimeError(
            f"Expected frozen SWE-bench source, imported {imported_context}"
        )
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
