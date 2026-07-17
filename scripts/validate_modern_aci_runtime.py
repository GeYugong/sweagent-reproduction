#!/usr/bin/env python3
"""Validate generated modern ACI configs with the frozen SWE-agent parser."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sweagent.agent.agents import AgentConfig


ROOT = Path(__file__).resolve().parents[1]
STATIC_VALIDATION_PATH = (
    ROOT / "data" / "manifests" / "modern_aci_variant_validation.json"
)
DEFAULT_OUTPUT = ROOT / "data" / "manifests" / "modern_aci_runtime_validation.json"
CUSTOM_COMMAND_ROOT = ROOT / "conf" / "modern_aci" / "commands"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def run_behavior_test(name: str, script: str) -> dict[str, Any]:
    result = subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "name": name,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "output": result.stdout.strip(),
    }


def behavior_tests(runtime_root: Path) -> list[dict[str, Any]]:
    defaults = runtime_root / "config" / "commands" / "defaults.sh"
    iterative = runtime_root / "config" / "commands" / "modern_iterative_search.sh"
    edit = runtime_root / "config" / "commands" / "modern_edit_without_linting.sh"
    full_file = runtime_root / "config" / "commands" / "_modern_full_file_view.sh"
    with tempfile.TemporaryDirectory(prefix="modern-aci-") as directory:
        sample = Path(directory) / "sample.txt"
        sample.write_text(
            "one\nneedle alpha\nthree\nfour\nfive\nneedle beta\nseven\n",
            encoding="utf-8",
        )
        common = f"""
set -euo pipefail
export CURRENT_FILE={sample!s}
export CURRENT_LINE=1
export WINDOW=4
export OVERLAP=1
SEARCH_RESULTS=()
SEARCH_FILES=()
SEARCH_INDEX=0
_constrain_line() {{ :; }}
_print() {{ printf 'VIEW:%s:%s:%s\\n' "$CURRENT_FILE" "$CURRENT_LINE" "$WINDOW"; }}
"""
        iterative_test = common + f"""
source {iterative!s}
search_file needle "$CURRENT_FILE" > {directory!s}/iterative.out
grep -q 'Search result 1/2' {directory!s}/iterative.out
next >> {directory!s}/iterative.out
grep -q 'Search result 2/2' {directory!s}/iterative.out
prev >> {directory!s}/iterative.out
test "$SEARCH_INDEX" -eq 0
echo ITERATIVE_OK
"""
        edit_test = common + f"""
source {edit!s}
printf 'changed\\n' | edit 2:2 > {directory!s}/edit.out
test "$(sed -n '2p' "$CURRENT_FILE")" = changed
echo EDIT_WITHOUT_LINT_OK
"""
        full_file_test = f"""
set -euo pipefail
export CURRENT_FILE={sample!s}
source {full_file!s}
_print > {directory!s}/full.out
grep -q '7:seven' {directory!s}/full.out
grep -q 'full-file view' {directory!s}/full.out
echo FULL_FILE_OK
"""
        syntax_test = "set -euo pipefail\n" + "\n".join(
            f"bash -n {path!s}"
            for path in sorted(CUSTOM_COMMAND_ROOT.glob("*.sh"))
        ) + "\necho BASH_SYNTAX_OK\n"
        return [
            run_behavior_test("bash_syntax", syntax_test),
            run_behavior_test("iterative_search_navigation", iterative_test),
            run_behavior_test("edit_without_linting_application", edit_test),
            run_behavior_test("full_file_rendering", full_file_test),
        ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    if not (runtime_root / "sweagent").is_dir():
        raise FileNotFoundError(f"Frozen SWE-agent runtime is missing: {runtime_root}")

    static = load_json(STATIC_VALIDATION_PATH)
    errors: list[str] = []
    observations: list[dict[str, Any]] = []
    previous_cwd = Path.cwd()
    try:
        os.chdir(runtime_root)
        for variant in static.get("variants", []):
            variant_id = variant["id"]
            config_path = runtime_root / "config" / "modern_aci" / f"{variant_id}.yaml"
            if not config_path.is_file():
                errors.append(f"missing runtime config: {variant_id}")
                continue
            if sha256_file(config_path) != variant["config"]["sha256"]:
                errors.append(f"runtime config hash mismatch: {variant_id}")
                continue
            try:
                config = AgentConfig.load_yaml(config_path)
                public_commands = [command.name for command in config._commands]
                expected_commands = variant["expected_public_commands"]
                if public_commands != expected_commands:
                    errors.append(
                        f"runtime command mismatch for {variant_id}: {public_commands}"
                    )
                observations.append(
                    {
                        "id": variant_id,
                        "config_sha256": sha256_file(config_path),
                        "public_commands": public_commands,
                        "public_command_count": len(public_commands),
                        "history_processor": type(config.history_processor).__name__,
                        "demonstration_count": len(config.demonstrations),
                        "window": config.env_variables.get("WINDOW"),
                        "parsed": public_commands == expected_commands,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - manifest records parser failures
                errors.append(f"runtime parse failed for {variant_id}: {exc}")
    finally:
        os.chdir(previous_cwd)

    tests = behavior_tests(runtime_root)
    errors.extend(
        f"behavior test failed: {test['name']}"
        for test in tests
        if not test["passed"]
    )
    patch_path = ROOT / "patches" / "sweagent_local_api.patch"
    manifest = {
        "schema_version": 1,
        "as_of": "2026-07-17",
        "evidence": "modern_reconstructed",
        "status": (
            "COMPLETE_RUNTIME_PARSER_AND_BEHAVIOR_VALIDATION"
            if not errors
            else "FAILED_RUNTIME_PARSER_OR_BEHAVIOR_VALIDATION"
        ),
        "inputs": {
            "static_validation": file_record(STATIC_VALIDATION_PATH),
            "runtime_patch": file_record(patch_path),
            "command_assets": [
                file_record(path)
                for path in sorted(CUSTOM_COMMAND_ROOT.glob("*.sh"))
            ],
        },
        "runtime": {
            "execution": "local_wsl2",
            "runtime_root": str(runtime_root),
            "python": platform.python_version(),
            "model_api_calls": 0,
            "gpu_used": False,
            "server_used": False,
        },
        "observations": observations,
        "behavior_tests": tests,
        "summary": {
            "variant_count": len(observations),
            "parsed_variant_count": sum(row["parsed"] for row in observations),
            "behavior_test_count": len(tests),
            "passed_behavior_test_count": sum(test["passed"] for test in tests),
            "errors": errors,
        },
        "completion": {
            "runtime_parser_and_behavior_validation_complete": not errors,
            "paired_runs_complete": False,
            "modern_replication_complete": False,
            "exact_model_rerun_complete": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                **manifest["summary"],
                "model_api_calls": 0,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
