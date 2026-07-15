#!/usr/bin/env python3
"""Verify that the checked-out SWE-agent snapshot matches the study protocol."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

EXPECTED_COMMIT = "658eb2842e8a8b00069b301338bc342b70538f7a"
EXPECTED_COMMAND_FILES = [
    "config/commands/defaults.sh",
    "config/commands/search.sh",
    "config/commands/edit_linting.sh",
    "config/commands/_split_string.py",
]


def git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def require_pattern(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, flags=re.MULTILINE) is None:
        raise AssertionError(f"Missing expected {label}: {pattern}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    upstream = root / "code" / "SWE-agent"
    config_path = upstream / "config" / "default.yaml"

    config_text = config_path.read_text(encoding="utf-8")
    commit = git_head(upstream)

    checks = {
        "upstream_commit": commit == EXPECTED_COMMIT,
        "window_100": re.search(r"^\s+WINDOW:\s+100\s*$", config_text, re.MULTILINE) is not None,
        "history_last5": re.search(r"^history_processor:\s+Last5Observations\s*$", config_text, re.MULTILINE)
        is not None,
        "commands_exact": all(f"- {path}" in config_text for path in EXPECTED_COMMAND_FILES),
        "single_demo": config_text.count("- trajectories/demonstrations/") == 1,
        "thought_action_parser": re.search(r"^parse_function:\s+ThoughtActionParser\s*$", config_text, re.MULTILINE)
        is not None,
        "detailed_command_parser": re.search(r"^parse_command:\s+ParseCommandDetailed\s*$", config_text, re.MULTILINE)
        is not None,
    }

    run_text = (upstream / "run.py").read_text(encoding="utf-8")
    models_text = (upstream / "sweagent" / "agent" / "models.py").read_text(encoding="utf-8")
    require_pattern(run_text, r"model_name=\"gpt4\"", "model shortcut")
    require_pattern(run_text, r"per_instance_cost_limit=3\.0", "instance cost limit")
    require_pattern(run_text, r"temperature=0\.0", "temperature")
    require_pattern(run_text, r"top_p=0\.95", "top-p")
    require_pattern(models_text, r'"gpt4":\s*"gpt-4-1106-preview"', "API model mapping")

    checks.update(
        {
            "model_gpt4_turbo": True,
            "temperature_0": True,
            "top_p_095": True,
            "cost_limit_3": True,
        }
    )

    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "expected_commit": EXPECTED_COMMIT,
        "observed_commit": commit,
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
