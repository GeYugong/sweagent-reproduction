#!/usr/bin/env python3
"""Audit paper qualitative cases and recover the prompt/ACI runtime artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

import pyarrow.parquet as pq
import yaml


PAPER_ARXIV_ID = "2405.15793v3"
PAPER_SHA256 = "3d2bafc2fd9e104fd204f7d4582260817c48b15133f7c1cf668dd081c2fbc1ab"
EXPERIMENTS_REVISION = "a5d52722965c791c0c04d18135f906b44f716d39"
SWEAGENT_INITIAL_REVISION = "5b143857cb7af8b22fd421a103429f76f5259f08"
SWEAGENT_LAST5_REVISION = "08e66863ac8ccf3cf8b740c243e74af15119f7b8"
SWEAGENT_PAPER_SNAPSHOT = "658eb2842e8a8b00069b301338bc342b70538f7a"
LITE_DATASET_REVISION = "81ad348adcaf3368691f4db2907f8fc97a8f7526"
LITE_DATASET_SHA256 = "2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1"
FULL_DATASET_REVISION = "283547aced6224d4adbe55c678b4c9c43fe7d501"
FULL_DATASET_SHA256 = "831728617f006e70c9de546e15cbdb49ce27b6fe8a8e4c4cd8035e8da3de3020"

RUN = "20240402_sweagent_gpt4"
RUN_ROOTS = {
    "full": f"evaluation/test/{RUN}/trajs",
    "lite": f"evaluation/lite/{RUN}/trajs",
}
RUN_BASE_LITE = f"evaluation/lite/{RUN}"

SYSTEM_REQUIRED_SHA256 = "bcf072797e41fd3f9111b36416fdd32269c98a830fe850324e68560883641e7d"
SYSTEM_OPTIONAL_SHA256 = "a4d3de50b84779d8b77c453db17183352e5c9b29280d12050504542dd9771db4"
DEMONSTRATION_SHA256 = "55f076f087bbe380ae06c6f8b624cceb56e7afa1c8589bbdfc91de0949e8e529"

QUALITATIVE_CASES = (
    ("psf__requests-2317", "successful", "resolved"),
    ("pylint-dev__pylint-5859", "successful", "resolved"),
    ("sympy__sympy-21614", "unsuccessful", "applied_unresolved"),
    ("django__django-14411", "unsuccessful", "applied_unresolved"),
)

EXPECTED_FINAL_OBSERVATION_EXACT = {
    "psf__requests-2317": False,
    "pylint-dev__pylint-5859": True,
    "sympy__sympy-21614": False,
    "django__django-14411": True,
}

EXPECTED_MODEL_PATCH_IN_PAPER = {
    "psf__requests-2317": True,
    "pylint-dev__pylint-5859": True,
    "sympy__sympy-21614": False,
    "django__django-14411": True,
}

PAPER_COMMAND_SIGNATURES = {
    "open": "open <path> [<line_number>]",
    "goto": "goto <line_number>",
    "scroll_down": "scroll_down",
    "scroll_up": "scroll_up",
    "search_file": "search_file <search_term> [<file>]",
    "search_dir": "search_dir <search_term> [<dir>]",
    "find_file": "find_file <file_name> [<dir>]",
    "edit": "edit <n>:<m> <replacement_text> end_of_edit",
    "create": "create <filename>",
    "submit": "submit",
}

COMMAND_NOTES = {
    "open": "RUNTIME_ARGUMENT_LABEL_SPLIT_REQUIRED_2002_OPTIONAL_566",
    "goto": "MATCH",
    "scroll_down": "PAPER_DIRECTION_TEXT_REVERSES_IMPLEMENTATION",
    "scroll_up": "RUNTIME_SIGNATURE_IS_SCROLL_DOWN_AND_PAPER_DIRECTION_TEXT_REVERSES_IMPLEMENTATION",
    "search_file": "RUNTIME_ARGUMENT_LABEL_SPLIT_AND_PAPER_50_LIMIT_DIFFERS_FROM_CODE_100",
    "search_dir": "RUNTIME_ARGUMENT_LABEL_SPLIT_AND_PAPER_50_LIMIT_DIFFERS_FROM_CODE_100",
    "find_file": "RUNTIME_ARGUMENT_LABEL_SPLIT_AND_PAPER_50_LIMIT_ABSENT_FROM_CODE",
    "edit": "IMPLEMENTED_PAPER_USES_ABBREVIATED_ARGUMENT_NAMES",
    "create": "MATCH",
    "submit": "MATCH",
}

COMMAND_IMPLEMENTATION = {
    "open": "opens a file and optionally centers the viewer around a line",
    "goto": "centers the current file around a requested line",
    "scroll_down": "CURRENT_LINE += WINDOW - OVERLAP",
    "scroll_up": "CURRENT_LINE -= WINDOW - OVERLAP",
    "search_file": "rejects queries matching more than 100 lines",
    "search_dir": "rejects queries matching files in more than 100 files",
    "find_file": "returns all matching paths without an explicit result cap",
    "edit": "rejects selected flake8 syntax/name errors and restores the original file",
    "create": "creates and opens a new file",
    "submit": "stages repository changes and emits model.patch",
}

PAPER_INTERFACE_MEMBERS = (
    "appx/01_interface.tex",
    "appx/03_prompts.tex",
    "appx/04_qualitative_analysis.tex",
    "appx_tables/commands.tex",
    "figures/prompts/system.tex",
    "figures/prompts/instance.tex",
    "figures/prompts/next_step.tex",
    "figures/prompts/error.tex",
    "figures/prompts/linting.tex",
    "figures/prompts/collapsed_obs.tex",
    "figures/prompts/demonstration.tex",
    "figures/interface/command_skeleton.tex",
    "figures/interface/file_viewer.tex",
    "figures/interface/search.tex",
    "figures/aci-ui.pdf",
    "figures/appx/prompt_flow.pdf",
    "figures/appx/swe-agent-components.pdf",
    "figures/file_editor_example.pdf",
    "figures/file_viewer_example.pdf",
    "figures/edit_comparison.pdf",
    "figures/search_comparison.pdf",
)

EXECUTION_COMMANDS = {
    "python",
    "python3",
    "pytest",
    "pylint",
    "tox",
    "make",
    "npm",
    "node",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def git_bytes(repo: Path, revision: str, path: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{revision}:{path}"]
    )


def git_object_id(repo: Path, revision: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"{revision}:{path}"], text=True
    ).strip()


def git_paths(repo: Path, revision: str, root: str) -> list[str]:
    payload = subprocess.check_output(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only", revision, "--", root]
    )
    return [item.decode() for item in payload.rstrip(b"\0").split(b"\0") if item]


def iter_git_blobs(
    repo: Path, revision: str, root: str
) -> Iterator[tuple[str, str, bytes]]:
    paths = git_paths(repo, revision, root)
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    if process.stdin is None or process.stdout is None:
        raise RuntimeError("Unable to open git cat-file pipes")
    try:
        for path in paths:
            process.stdin.write(f"{revision}:{path}\n".encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().strip().split()
            if len(header) != 3 or header[1] != "blob":
                raise RuntimeError(f"Unexpected git cat-file header for {path}: {header}")
            object_id, _, size_text = header
            payload = process.stdout.read(int(size_text))
            if process.stdout.read(1) != b"\n":
                raise RuntimeError(f"Missing git cat-file separator for {path}")
            yield path, object_id, payload
    finally:
        process.stdin.close()
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"git cat-file failed with exit code {return_code}")


def load_tasks(path: Path) -> dict[str, dict[str, Any]]:
    return {row["instance_id"]: row for row in pq.read_table(path).to_pylist()}


def load_json_blob(repo: Path, revision: str, path: str) -> Any:
    return json.loads(git_bytes(repo, revision, path))


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"Cannot write an empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_exact_text(path: Path, content: str) -> None:
    if "\r" in content:
        raise RuntimeError(f"Unexpected carriage return in prompt artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode())


def output_record(path: Path, project_root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(project_root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def parse_command_metadata(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    items: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() != "# @yaml":
            index += 1
            continue
        index += 1
        block: list[str] = []
        while index < len(lines) and lines[index].startswith("#"):
            line = lines[index][1:]
            block.append(line[1:] if line.startswith(" ") else line)
            index += 1
        while index < len(lines):
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\(\) \{$", lines[index])
            if match:
                break
            index += 1
        if index >= len(lines):
            continue
        metadata = yaml.safe_load("\n".join(block))
        if metadata:
            metadata["name"] = match.group(1)
            items.append(metadata)
    return items


def load_config_and_commands(
    repo: Path, revision: str, config_path: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    config = yaml.safe_load(git_bytes(repo, revision, config_path))
    commands: list[dict[str, Any]] = []
    command_sources: dict[str, str] = {}
    for path in config["command_files"]:
        text = git_bytes(repo, revision, path).decode()
        for command in parse_command_metadata(text):
            commands.append(command)
            command_sources[command["name"]] = path
    return config, commands, command_sources


def detailed_command_docs(commands: Sequence[dict[str, Any]]) -> str:
    docs = ""
    for command in commands:
        docs += f"{command['name']}:\n"
        if command.get("docstring") is not None:
            docs += f"  docstring: {command['docstring']}\n"
        if command.get("signature") is not None:
            docs += f"  signature: {command['signature']}\n"
        if command.get("arguments") is not None:
            docs += "  arguments:\n"
            for name, settings in command["arguments"].items():
                required = "required" if settings["required"] else "optional"
                docs += (
                    f"    - {name} ({settings['type']}) [{required}]: "
                    f"{settings['description']}\n"
                )
        docs += "\n"
    return docs


def render_system_prompt(config: dict[str, Any], commands: Sequence[dict[str, Any]]) -> str:
    docs = detailed_command_docs(commands)
    return config["system_template"].format(
        command_docs=docs, **config["env_variables"]
    )


def changed_line_count(left: str, right: str) -> int:
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    if len(left_lines) != len(right_lines):
        raise RuntimeError("Prompt variants unexpectedly have different line counts")
    return sum(a != b for a, b in zip(left_lines, right_lines))


def prompt_runtime_audit(
    experiments_repo: Path,
    sweagent_repo: Path,
    lite_tasks: dict[str, dict[str, Any]],
    full_tasks: dict[str, dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, str],
    dict[str, dict[str, Any]],
    dict[str, str],
]:
    initial_config, initial_commands, initial_sources = load_config_and_commands(
        sweagent_repo, SWEAGENT_INITIAL_REVISION, "config/default.yaml"
    )
    optional_system = render_system_prompt(initial_config, initial_commands)
    if optional_system.count("[optional]") != 4:
        raise RuntimeError("Expected exactly four optional argument labels")
    required_system = optional_system.replace("[optional]", "[required]")
    expected_systems = {
        SYSTEM_REQUIRED_SHA256: ("required", required_system),
        SYSTEM_OPTIONAL_SHA256: ("optional", optional_system),
    }
    for expected_sha, (_, content) in expected_systems.items():
        if sha256_bytes(content.encode()) != expected_sha:
            raise RuntimeError("Recovered system prompt hash mismatch")

    snapshot_config, snapshot_commands, _ = load_config_and_commands(
        sweagent_repo,
        SWEAGENT_PAPER_SNAPSHOT,
        "config/configs/default_sys-env_window100-detailed_cmd_format-last_5_history-1_demos.yaml",
    )
    snapshot_system = render_system_prompt(snapshot_config, snapshot_commands)

    variant_counts: Counter[tuple[str, str, str]] = Counter()
    split_counts: Counter[tuple[str, str]] = Counter()
    demo_hashes: Counter[str] = Counter()
    demo_contents: dict[str, str] = {}
    instance_exact = 0
    trajectory_count = 0
    trajectory_tree_ids: dict[str, str] = {}

    for split, root in RUN_ROOTS.items():
        tasks = full_tasks if split == "full" else lite_tasks
        trajectory_tree_ids[split] = git_object_id(
            experiments_repo, EXPERIMENTS_REVISION, root
        )
        for path, _, payload in iter_git_blobs(
            experiments_repo, EXPERIMENTS_REVISION, root
        ):
            trajectory_count += 1
            record = json.loads(payload)
            if len(record.get("history", [])) < 3:
                raise RuntimeError(f"Missing prompt history in {path}")
            system = record["history"][0]["content"]
            system_sha = sha256_bytes(system.encode())
            if system_sha not in expected_systems:
                raise RuntimeError(f"Unknown system prompt variant in {path}: {system_sha}")
            variant, expected_system = expected_systems[system_sha]
            if system != expected_system:
                raise RuntimeError(f"System prompt content mismatch in {path}")

            demo = record["history"][1]
            if demo.get("role") != "user" or not demo.get("is_demo"):
                raise RuntimeError(f"Unexpected demonstration history entry in {path}")
            demo_sha = sha256_bytes(demo["content"].encode())
            demo_hashes[demo_sha] += 1
            demo_contents[demo_sha] = demo["content"]

            instance_id = path.rsplit("/", 1)[-1].removesuffix(".traj")
            if instance_id not in tasks:
                raise RuntimeError(f"Missing frozen task for {instance_id}")
            instance_message = next(
                entry["content"]
                for entry in record["history"]
                if entry.get("role") == "user" and not entry.get("is_demo")
            )
            state_match = re.search(
                r"\n\(Open file: (?P<open>.+)\)\n"
                r"\(Current directory: (?P<cwd>.+)\)\nbash-\$$",
                instance_message,
            )
            if not state_match:
                raise RuntimeError(f"Cannot recover instance prompt state for {instance_id}")
            expected_instance = initial_config["instance_template"].format(
                issue=tasks[instance_id]["problem_statement"],
                open_file=state_match.group("open"),
                working_dir=state_match.group("cwd"),
            )
            if expected_instance != instance_message:
                raise RuntimeError(f"Initial instance template mismatch for {instance_id}")
            instance_exact += 1

            repository = instance_id.split("__", 1)[0]
            variant_counts[(split, repository, variant)] += 1
            split_counts[(split, variant)] += 1

    if trajectory_count != 2568 or instance_exact != 2568:
        raise RuntimeError("Unexpected GPT-4 public trajectory prompt coverage")
    if demo_hashes != Counter({DEMONSTRATION_SHA256: 2568}):
        raise RuntimeError(f"Unexpected demonstration variants: {demo_hashes}")
    expected_split_counts = Counter(
        {
            ("full", "required"): 1753,
            ("full", "optional"): 515,
            ("lite", "required"): 249,
            ("lite", "optional"): 51,
        }
    )
    if split_counts != expected_split_counts:
        raise RuntimeError(f"Unexpected system prompt distribution: {split_counts}")

    rows = []
    for (split, repository, variant), count in sorted(variant_counts.items()):
        system_sha = (
            SYSTEM_REQUIRED_SHA256 if variant == "required" else SYSTEM_OPTIONAL_SHA256
        )
        rows.append(
            {
                "split": split,
                "repository": repository,
                "variant": variant,
                "system_prompt_sha256": system_sha,
                "trajectories": count,
            }
        )

    prompts = {
        "system_required": required_system,
        "system_optional": optional_system,
        "demonstration": demo_contents[DEMONSTRATION_SHA256],
        "instance_template": initial_config["instance_template"],
    }
    summary = {
        "public_gpt4_trajectories": trajectory_count,
        "instance_template_exact": instance_exact,
        "system_variants": {
            "required": {
                "sha256": SYSTEM_REQUIRED_SHA256,
                "full": split_counts[("full", "required")],
                "lite": split_counts[("lite", "required")],
                "total": split_counts[("full", "required")]
                + split_counts[("lite", "required")],
            },
            "optional": {
                "sha256": SYSTEM_OPTIONAL_SHA256,
                "full": split_counts[("full", "optional")],
                "lite": split_counts[("lite", "optional")],
                "total": split_counts[("full", "optional")]
                + split_counts[("lite", "optional")],
            },
        },
        "demonstration": {
            "sha256": DEMONSTRATION_SHA256,
            "exact_count": demo_hashes[DEMONSTRATION_SHA256],
        },
        "paper_snapshot_system_changed_lines": {
            "versus_runtime_optional": changed_line_count(snapshot_system, optional_system),
            "versus_runtime_required": changed_line_count(snapshot_system, required_system),
        },
        "trajectory_trees": trajectory_tree_ids,
    }
    runtime_docs = {
        "required": parse_runtime_command_docs(required_system),
        "optional": parse_runtime_command_docs(optional_system),
    }
    return rows, summary, prompts, runtime_docs, initial_sources


def parse_runtime_command_docs(system_prompt: str) -> dict[str, dict[str, Any]]:
    body = system_prompt.split("COMMANDS:\n", 1)[1].split("\nPlease note", 1)[0]
    starts = list(re.finditer(r"(?m)^([a-z_]+):\n", body))
    result: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        block = body[match.end() : end]
        doc_match = re.search(r"(?m)^  docstring: (.*)$", block)
        signature_match = re.search(
            r"(?ms)^  signature: (.*?)(?=^  arguments:|\n\n|\Z)", block
        )
        if not doc_match or not signature_match:
            raise RuntimeError(f"Cannot parse runtime docs for {match.group(1)}")
        arguments = re.findall(
            r"(?m)^    - ([a-z_]+) \(([^)]+)\) \[(required|optional)\]: (.*)$",
            block,
        )
        result[match.group(1)] = {
            "docstring": doc_match.group(1),
            "signature": signature_match.group(1).strip().replace("\n", " "),
            "arguments": {
                name: {"type": kind, "mode": mode, "description": description}
                for name, kind, mode, description in arguments
            },
        }
    return result


def extract_box_blocks(tex: str, environment: str) -> list[str]:
    boxes = re.findall(
        rf"\\begin\{{{re.escape(environment)}\}}.*?\](.*?)"
        rf"\\end\{{{re.escape(environment)}\}}",
        tex,
        re.DOTALL,
    )
    output = []
    for box in boxes:
        blocks = re.findall(
            r"\\begin\{(?:Code)?Verbatim\}(?:\[[^]]*\])?"
            r"(.*?)\\end\{(?:Code)?Verbatim\}",
            box,
            re.DOTALL,
        )
        if not blocks:
            raise RuntimeError(f"Missing verbatim block in {environment}")
        output.append(blocks[-1].strip())
    return output


def action_name(action: str) -> str:
    first_line = action.strip().splitlines()[0]
    return first_line.split()[0] if first_line.split() else ""


def qualitative_audit(
    experiments_repo: Path,
    lite_tasks: dict[str, dict[str, Any]],
    paper_members: dict[str, bytes],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    results = load_json_blob(
        experiments_repo, EXPERIMENTS_REVISION, f"{RUN_BASE_LITE}/results/results.json"
    )
    predictions = [
        json.loads(line)
        for line in git_bytes(
            experiments_repo, EXPERIMENTS_REVISION, f"{RUN_BASE_LITE}/all_preds.jsonl"
        ).splitlines()
    ]
    qualitative_source = paper_members["appx/04_qualitative_analysis.tex"].decode()
    source_case_ids = re.findall(r"\\input\{trajectories/([^}]+)\}", qualitative_source)
    expected_ids = [item[0] for item in QUALITATIVE_CASES]
    if source_case_ids != expected_ids:
        raise RuntimeError(f"Unexpected qualitative case order: {source_case_ids}")

    case_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    total_actions = 0
    exact_actions = 0
    exact_gold = 0
    exact_results = 0

    for instance_id, paper_class, expected_result in QUALITATIVE_CASES:
        trajectory_path = f"{RUN_BASE_LITE}/trajs/{instance_id}.traj"
        trajectory_payload = git_bytes(
            experiments_repo, EXPERIMENTS_REVISION, trajectory_path
        )
        trajectory = json.loads(trajectory_payload)
        tex_path = f"trajectories/{instance_id}.tex"
        tex_payload = paper_members[tex_path]
        tex = tex_payload.decode()
        paper_actions = extract_box_blocks(tex, "agentbox")
        official_actions = [step["action"].strip() for step in trajectory["trajectory"]]
        if len(paper_actions) != len(official_actions):
            raise RuntimeError(f"Action count mismatch for {instance_id}")

        action_matches = [paper == official for paper, official in zip(paper_actions, official_actions)]
        if not all(action_matches):
            raise RuntimeError(f"Paper action sequence mismatch for {instance_id}")
        total_actions += len(official_actions)
        exact_actions += sum(action_matches)
        for turn, (action, exact) in enumerate(zip(official_actions, action_matches), 1):
            action_rows.append(
                {
                    "instance_id": instance_id,
                    "turn": turn,
                    "action_name": action_name(action),
                    "action": action,
                    "action_sha256": sha256_bytes(action.encode()),
                    "paper_action_exact": exact,
                }
            )

        is_resolved = instance_id in results["resolved"]
        is_applied = instance_id in results["applied"]
        public_result = "resolved" if is_resolved else "applied_unresolved" if is_applied else "other"
        result_exact = public_result == expected_result
        if not result_exact:
            raise RuntimeError(f"Unexpected result for {instance_id}: {public_result}")
        exact_results += 1

        prediction_rows = [row for row in predictions if row["instance_id"] == instance_id]
        if len(prediction_rows) != 1:
            raise RuntimeError(f"Unexpected prediction rows for {instance_id}")
        submission = trajectory["info"].get("submission") or ""
        prediction_patch = prediction_rows[0].get("model_patch") or ""
        if prediction_patch.strip() != submission.strip():
            raise RuntimeError(f"Prediction/trajectory patch mismatch for {instance_id}")

        gold_patch = lite_tasks[instance_id]["patch"].strip()
        gold_blocks = extract_box_blocks(tex, "goldpatchbox")
        if len(gold_blocks) != 1:
            raise RuntimeError(f"Unexpected gold patch boxes for {instance_id}")
        gold_exact = gold_blocks[0] == gold_patch
        if not gold_exact:
            raise RuntimeError(f"Paper gold patch mismatch for {instance_id}")
        exact_gold += 1

        model_patch_in_paper = submission.strip() in tex
        if model_patch_in_paper != EXPECTED_MODEL_PATCH_IN_PAPER[instance_id]:
            raise RuntimeError(f"Unexpected model patch presentation for {instance_id}")
        final_observations = extract_box_blocks(tex, "observationbox")
        paper_final_observation_exact = (
            final_observations[-1] == trajectory["trajectory"][-1]["observation"].strip()
        )
        if (
            paper_final_observation_exact
            != EXPECTED_FINAL_OBSERVATION_EXACT[instance_id]
        ):
            raise RuntimeError(f"Unexpected final observation presentation for {instance_id}")

        actions = [action_name(action) for action in official_actions]
        failed_edits = sum(
            step.get("action", "").lstrip().startswith("edit ")
            and "Your proposed edit has introduced new syntax error(s)"
            in (step.get("observation") or "")
            for step in trajectory["trajectory"]
        )
        stats = trajectory["info"]["model_stats"]
        log_path = f"{RUN_BASE_LITE}/logs/{instance_id}.{RUN}.eval.log"
        log_payload = git_bytes(experiments_repo, EXPERIMENTS_REVISION, log_path)
        case_rows.append(
            {
                "instance_id": instance_id,
                "paper_class": paper_class,
                "public_result": public_result,
                "result_exact": result_exact,
                "exit_status": trajectory["info"]["exit_status"],
                "turns": len(official_actions),
                "api_calls": stats["api_calls"],
                "instance_cost": f"{stats['instance_cost']:.5f}",
                "edit_attempts": actions.count("edit"),
                "failed_edit_attempts": failed_edits,
                "execution_actions": sum(name in EXECUTION_COMMANDS for name in actions),
                "final_action": actions[-1],
                "paper_actions_exact": sum(action_matches),
                "model_patch_in_paper": model_patch_in_paper,
                "paper_final_observation_exact": paper_final_observation_exact,
                "gold_patch_exact": gold_exact,
                "model_patch_sha256": sha256_bytes(submission.strip().encode()),
                "gold_patch_sha256": sha256_bytes(gold_patch.encode()),
                "trajectory_blob": git_object_id(
                    experiments_repo, EXPERIMENTS_REVISION, trajectory_path
                ),
                "trajectory_sha256": sha256_bytes(trajectory_payload),
                "evaluation_log_blob": git_object_id(
                    experiments_repo, EXPERIMENTS_REVISION, log_path
                ),
                "evaluation_log_sha256": sha256_bytes(log_payload),
                "paper_tex_sha256": sha256_bytes(tex_payload),
            }
        )

    if (total_actions, exact_actions, exact_gold, exact_results) != (72, 72, 4, 4):
        raise RuntimeError("Qualitative aggregate audit mismatch")
    summary = {
        "cases": 4,
        "successful": 2,
        "unsuccessful": 2,
        "result_labels_exact": exact_results,
        "paper_actions": total_actions,
        "paper_actions_exact": exact_actions,
        "gold_patches_exact": exact_gold,
        "model_patches_shown_verbatim": sum(
            row["model_patch_in_paper"] for row in case_rows
        ),
        "final_observations_exact": sum(
            row["paper_final_observation_exact"] for row in case_rows
        ),
        "sympy_runtime_exit": "submitted (exit_cost)",
        "sympy_paper_exit_observation": "Exited",
        "sympy_autosubmitted_patch_omitted_from_paper": True,
    }
    return case_rows, action_rows, summary


def command_audit(
    sweagent_repo: Path,
    initial_sources: dict[str, str],
    runtime_docs: dict[str, dict[str, dict[str, Any]]],
    paper_commands: str,
) -> list[dict[str, Any]]:
    initial_config, initial_commands, _ = load_config_and_commands(
        sweagent_repo, SWEAGENT_INITIAL_REVISION, "config/default.yaml"
    )
    del initial_config
    initial_by_name = {item["name"]: item for item in initial_commands}
    if set(initial_by_name) != set(PAPER_COMMAND_SIGNATURES):
        raise RuntimeError("Initial command set does not match paper command set")

    rows = []
    for name, paper_signature in PAPER_COMMAND_SIGNATURES.items():
        paper_name = name.replace("_", "\\_")
        if f"\\textbf{{{paper_name}}}" not in paper_commands:
            raise RuntimeError(f"Paper command table missing {name}")
        source_path = initial_sources[name]
        initial = initial_by_name[name]
        required = runtime_docs["required"][name]
        optional = runtime_docs["optional"][name]
        required_modes = ";".join(
            f"{arg}:{settings['mode']}" for arg, settings in required["arguments"].items()
        )
        optional_modes = ";".join(
            f"{arg}:{settings['mode']}" for arg, settings in optional["arguments"].items()
        )
        rows.append(
            {
                "command": name,
                "paper_signature": paper_signature,
                "runtime_signature": required["signature"],
                "initial_code_signature": initial["signature"].replace("\n", " "),
                "required_variant_arguments": required_modes,
                "optional_variant_arguments": optional_modes,
                "implementation_source": source_path,
                "implementation_blob": git_object_id(
                    sweagent_repo, SWEAGENT_INITIAL_REVISION, source_path
                ),
                "implementation_semantics": COMMAND_IMPLEMENTATION[name],
                "audit_status": COMMAND_NOTES[name],
            }
        )
    return rows


def runtime_versions() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pyarrow": importlib.metadata.version("pyarrow"),
        "PyYAML": importlib.metadata.version("PyYAML"),
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
        "--sweagent-repo", type=Path, default=project_root / "code" / "SWE-agent"
    )
    parser.add_argument(
        "--lite-parquet",
        type=Path,
        default=project_root
        / "data"
        / "cache"
        / "paper_evaluator"
        / "lite_paper_81ad348a.parquet",
    )
    parser.add_argument(
        "--full-parquet",
        type=Path,
        default=project_root
        / "data"
        / "cache"
        / "paper_evaluator"
        / "test_paper_283547ac.parquet",
    )
    parser.add_argument(
        "--paper-source",
        type=Path,
        default=project_root / "paper" / "2405.15793_source.tar.gz",
    )
    parser.add_argument(
        "--derived-dir", type=Path, default=project_root / "data" / "derived"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=project_root
        / "data"
        / "manifests"
        / "official_qualitative_interface.json",
    )
    args = parser.parse_args()

    experiments_repo = args.experiments_repo.resolve()
    sweagent_repo = args.sweagent_repo.resolve()
    lite_path = args.lite_parquet.resolve()
    full_path = args.full_parquet.resolve()
    paper_source = args.paper_source.resolve()
    derived_dir = args.derived_dir.resolve()
    manifest_path = args.manifest.resolve()

    ensure_hash(lite_path, LITE_DATASET_SHA256)
    ensure_hash(full_path, FULL_DATASET_SHA256)
    ensure_hash(paper_source, PAPER_SHA256)
    lite_tasks = load_tasks(lite_path)
    full_tasks = load_tasks(full_path)
    if len(lite_tasks) != 300 or len(full_tasks) != 2294:
        raise RuntimeError("Unexpected frozen dataset cardinality")

    requested_members = set(PAPER_INTERFACE_MEMBERS)
    requested_members.update(
        f"trajectories/{instance_id}.tex" for instance_id, _, _ in QUALITATIVE_CASES
    )
    paper_members: dict[str, bytes] = {}
    with tarfile.open(paper_source, "r:gz") as archive:
        for name in sorted(requested_members):
            handle = archive.extractfile(name)
            if handle is None:
                raise RuntimeError(f"Missing paper source member: {name}")
            paper_members[name] = handle.read()

    prompt_rows, prompt_summary, prompts, runtime_docs, initial_sources = (
        prompt_runtime_audit(
            experiments_repo, sweagent_repo, lite_tasks, full_tasks
        )
    )
    case_rows, action_rows, qualitative_summary = qualitative_audit(
        experiments_repo, lite_tasks, paper_members
    )
    command_rows = command_audit(
        sweagent_repo,
        initial_sources,
        runtime_docs,
        paper_members["appx_tables/commands.tex"].decode(),
    )

    outputs = {
        "qualitative_cases": derived_dir / "official_qualitative_cases.csv",
        "qualitative_actions": derived_dir / "official_qualitative_actions.csv",
        "prompt_runtime_variants": derived_dir / "official_prompt_runtime_variants.csv",
        "command_interface_audit": derived_dir / "official_command_interface_audit.csv",
        "system_prompt_required": derived_dir / "official_prompt_system_required.txt",
        "system_prompt_optional": derived_dir / "official_prompt_system_optional.txt",
        "demonstration_prompt": derived_dir / "official_prompt_demonstration.txt",
        "instance_template": derived_dir / "official_prompt_instance_template.txt",
    }
    write_csv(outputs["qualitative_cases"], case_rows)
    write_csv(outputs["qualitative_actions"], action_rows)
    write_csv(outputs["prompt_runtime_variants"], prompt_rows)
    write_csv(outputs["command_interface_audit"], command_rows)
    write_exact_text(outputs["system_prompt_required"], prompts["system_required"])
    write_exact_text(outputs["system_prompt_optional"], prompts["system_optional"])
    write_exact_text(outputs["demonstration_prompt"], prompts["demonstration"])
    write_exact_text(outputs["instance_template"], prompts["instance_template"])

    paper_asset_manifest = {
        name: {"bytes": len(paper_members[name]), "sha256": sha256_bytes(paper_members[name])}
        for name in PAPER_INTERFACE_MEMBERS
    }
    manifest = {
        "schema_version": 1,
        "status": "COMPLETE_A13_A14_ARTIFACT_AUDIT_WITH_RUNTIME_PROMPT_VARIANTS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper": {
            "arxiv_id": PAPER_ARXIV_ID,
            "source_path": paper_source.relative_to(project_root).as_posix(),
            "source_sha256": PAPER_SHA256,
        },
        "frozen_inputs": {
            "experiments_revision": EXPERIMENTS_REVISION,
            "sweagent_initial_revision": SWEAGENT_INITIAL_REVISION,
            "sweagent_last5_revision": SWEAGENT_LAST5_REVISION,
            "sweagent_paper_snapshot": SWEAGENT_PAPER_SNAPSHOT,
            "lite_dataset_revision": LITE_DATASET_REVISION,
            "lite_dataset_sha256": LITE_DATASET_SHA256,
            "full_dataset_revision": FULL_DATASET_REVISION,
            "full_dataset_sha256": FULL_DATASET_SHA256,
            "initial_config_blob": git_object_id(
                sweagent_repo, SWEAGENT_INITIAL_REVISION, "config/default.yaml"
            ),
            "last5_config_blob": git_object_id(
                sweagent_repo,
                SWEAGENT_LAST5_REVISION,
                "config/configs/default_sys-env_window100-detailed_cmd_format-last_5_history-1_demos.yaml",
            ),
        },
        "runtime": runtime_versions(),
        "A13_qualitative_cases": {
            "status": "COMPLETE_EXACT_ACTIONS_RESULTS_AND_GOLD_WITH_PRESENTATION_DIFFERENCES",
            **qualitative_summary,
        },
        "A14_prompts_commands_interface": {
            "status": "COMPLETE_RUNTIME_ASSETS_RECOVERED_WITH_DOCUMENTED_PAPER_CODE_DRIFT",
            **prompt_summary,
            "commands_mapped": len(command_rows),
            "paper_interface_assets": paper_asset_manifest,
            "documented_differences": [
                "The nominal GPT-4 run contains two system-prompt variants that differ only in four optional-argument labels.",
                "All 2,568 public GPT-4 instance messages exactly match the initial SWE-agent config, not the paper-time snapshot.",
                "The runtime scroll_up documentation exposes the signature scroll_down and describes movement in the wrong direction.",
                "The paper command table reverses the scroll direction descriptions relative to implementation semantics.",
                "The paper prose states a 50-result search cap; search_file rejects more than 100 matched lines, search_dir rejects more than 100 matched files, and find_file has no explicit cap.",
                "Paper prompt figures are edited presentation artifacts rather than byte-exact runtime prompts.",
            ],
        },
        "outputs": {
            key: output_record(path, project_root) for key, path in outputs.items()
        },
        "summary": {
            "api_calls": 0,
            "gpu_used": False,
            "server_used": False,
        },
    }
    write_json(manifest_path, manifest)
    print(f"manifest={manifest_path}")
    print(
        "A13: cases=4 actions=72/72 gold=4/4 results=4/4; "
        "A14: prompts=2568 system_variants=2 commands=10/10"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
