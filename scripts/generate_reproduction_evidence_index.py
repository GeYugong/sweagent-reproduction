#!/usr/bin/env python3
"""Generate a hash index for the committed SWE-agent reproduction evidence."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "manifests" / "reproduction_evidence_index.json"
MATRIX_PATH = ROOT / "conf" / "full_paper_matrix.yaml"
KEY_EVIDENCE_PATHS = [
    "paper/2405.15793_SWE-agent.pdf",
    "paper/2405.15793_source.tar.gz",
    "conf/full_paper_matrix.yaml",
    "conf/paper_output_inventory.yaml",
    "data/manifests/full_reproduction_coverage.json",
    "data/manifests/zero_cost_regeneration_audit.json",
    "data/manifests/official_evaluator_replay.json",
    "data/manifests/official_gold_repository_replay.json",
    "data/manifests/modern_dev20_baseline_analysis.json",
    "docs/reproduction_report.md",
    "logs/experiment_log.md",
    "logs/experiment_registry.csv",
]
SECRET_PATTERNS = [
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(
        rb"(?:OPENAI_API_KEY|ANTHROPIC_AUTH_TOKEN)\s*[=:]\s*['\"]"
        rb"[A-Za-z0-9_-]{20,}"
    ),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_git(args: list[str], *, cwd: Path = ROOT, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def category_for(path: str, mode: str) -> str:
    if mode == "160000":
        return "submodule"
    prefix = path.split("/", 1)[0]
    return {
        "paper": "paper",
        "conf": "configuration",
        "data": "data",
        "docs": "documentation",
        "logs": "experiment_log",
        "scripts": "script",
        "patches": "patch",
        "output": "rendered_artifact",
    }.get(prefix, "repository_root")


def parse_index() -> list[dict[str, str]]:
    payload = run_git(["ls-files", "--stage", "-z"], text=False)
    entries = []
    for raw_entry in payload.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        if stage != "0":
            raise ValueError(f"Unexpected non-zero index stage for {raw_path!r}")
        entries.append(
            {
                "mode": mode,
                "git_object_id": object_id,
                "path": raw_path.decode("utf-8"),
            }
        )
    return entries


def file_contains_secret(path: Path) -> bool:
    payload = path.read_bytes()
    if b"\0" in payload[:8192]:
        return False
    return any(pattern.search(payload) is not None for pattern in SECRET_PATTERNS)


def main() -> int:
    matrix = load_yaml(MATRIX_PATH)
    completion = matrix.get("completion_contract", {})
    repository_head = str(run_git(["rev-parse", "HEAD"])).strip()
    tracked_status = str(
        run_git(["status", "--porcelain", "--untracked-files=no"])
    ).strip()
    index_entries = parse_index()
    file_records = []
    submodule_records = []
    secret_hit_paths = []

    for entry in index_entries:
        relative_path = entry["path"]
        path = ROOT / relative_path
        category = category_for(relative_path, entry["mode"])
        if entry["mode"] == "160000":
            local_head = str(run_git(["rev-parse", "HEAD"], cwd=path)).strip()
            local_status = str(
                run_git(
                    ["status", "--porcelain", "--untracked-files=no"], cwd=path
                )
            ).strip()
            submodule_records.append(
                {
                    **entry,
                    "category": category,
                    "local_head": local_head,
                    "head_matches_gitlink": local_head == entry["git_object_id"],
                    "tracked_worktree_clean": local_status == "",
                }
            )
            continue
        if not path.is_file():
            raise FileNotFoundError(f"Tracked file is absent: {relative_path}")
        record = {
            **entry,
            "category": category,
            "bytes": path.stat().st_size,
            "working_tree_sha256": sha256_file(path),
        }
        file_records.append(record)
        if file_contains_secret(path):
            secret_hit_paths.append(relative_path)

    key_evidence = []
    record_by_path = {record["path"]: record for record in file_records}
    for relative_path in KEY_EVIDENCE_PATHS:
        if relative_path not in record_by_path:
            raise FileNotFoundError(f"Key evidence is not tracked: {relative_path}")
        key_evidence.append(record_by_path[relative_path])

    history_output = str(
        run_git(["log", "-20", "--format=%H%x09%s"])
    ).splitlines()
    commit_history = [
        {"commit": line.split("\t", 1)[0], "subject": line.split("\t", 1)[1]}
        for line in history_output
    ]
    disk = shutil.disk_usage(ROOT)
    category_counts = Counter(record["category"] for record in file_records)
    category_counts.update(record["category"] for record in submodule_records)
    submodules_valid = all(
        record["head_matches_gitlink"] and record["tracked_worktree_clean"]
        for record in submodule_records
    )
    completion_valid = (
        completion.get("public_artifact_reproduction_complete") is True
        and completion.get("exact_model_rerun_complete") is False
        and completion.get("modern_replication_complete") is False
        and completion.get("strict_full_paper_reproduction_complete") is False
    )
    status = (
        "COMPLETE_COMMITTED_EVIDENCE_INDEX"
        if tracked_status == ""
        and not secret_hit_paths
        and submodules_valid
        and completion_valid
        else "FAILED_EVIDENCE_INDEX_VALIDATION"
    )
    manifest = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": status,
        "scope": "Committed SWE-agent reproduction evidence",
        "repository": {
            "indexed_revision": repository_head,
            "tracked_worktree_clean_before_index_write": tracked_status == "",
            "tracked_status_before_index_write": tracked_status.splitlines(),
            "self_excluded_from_index": True,
            "self_exclusion_reason": (
                "The index did not exist in the indexed revision and is committed in the subsequent evidence-freeze commit."
            ),
        },
        "completion": {
            "public_artifact_reproduction_complete": completion.get(
                "public_artifact_reproduction_complete"
            ),
            "exact_model_rerun_complete": completion.get(
                "exact_model_rerun_complete"
            ),
            "modern_replication_complete": completion.get(
                "modern_replication_complete"
            ),
            "strict_full_paper_reproduction_complete": completion.get(
                "strict_full_paper_reproduction_complete"
            ),
            "flags_valid": completion_valid,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pid": os.getpid(),
            "model_api_calls": 0,
            "gpu_used": False,
            "server_used": False,
            "disk_total_bytes": disk.total,
            "disk_free_bytes": disk.free,
        },
        "summary": {
            "tracked_file_count": len(file_records),
            "submodule_count": len(submodule_records),
            "category_counts": dict(sorted(category_counts.items())),
            "secret_hit_file_count": len(secret_hit_paths),
            "submodules_valid": submodules_valid,
            "key_evidence_count": len(key_evidence),
        },
        "secret_scan": {
            "patterns": [
                "OpenAI-style sk token with at least 20 payload characters",
                "literal OPENAI_API_KEY or ANTHROPIC_AUTH_TOKEN assignment",
            ],
            "hit_files": secret_hit_paths,
        },
        "submodules": submodule_records,
        "key_evidence": key_evidence,
        "files": sorted(file_records, key=lambda record: record["path"]),
        "recent_commits": commit_history,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": status,
                "indexed_revision": repository_head,
                "tracked_files": len(file_records),
                "submodules": len(submodule_records),
                "secret_hits": len(secret_hit_paths),
                "tracked_clean": tracked_status == "",
                "output": OUTPUT_PATH.relative_to(ROOT).as_posix(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if status == "COMPLETE_COMMITTED_EVIDENCE_INDEX" else 1


if __name__ == "__main__":
    raise SystemExit(main())
