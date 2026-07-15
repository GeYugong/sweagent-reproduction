#!/usr/bin/env python3
"""Run the paper-time SWE-bench evaluator with an explicit PyPI drift shim."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Optional

from swebench.harness import context_manager


def install_requirements_compatibility() -> None:
    original = context_manager.get_requirements

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
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    predictions = args.predictions.resolve()
    if not predictions.is_file():
        raise FileNotFoundError(predictions)
    args.results.mkdir(parents=True, exist_ok=True)
    args.testbed.mkdir(parents=True, exist_ok=True)

    configure_conda_downloads()
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

    scorecards_path = predictions.parent / "scorecards.json"
    if not scorecards_path.is_file():
        raise RuntimeError("Evaluator did not produce scorecards.json")
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
