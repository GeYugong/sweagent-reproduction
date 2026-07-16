#!/usr/bin/env python3
"""Recover aggregate SWE-agent results embedded in the arXiv source package.

This script is deliberately separate from artifact recomputation.  The arXiv
package contains final table values and vector figures, but it does not contain
the underlying dev-37 manifest, six pass@k prediction sets, ablation runs, or
per-instance failure labels.  The generated files therefore reproduce the
published aggregates and record that limitation instead of presenting them as
freshly recomputed raw-run results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PAPER_SOURCE_MEMBER = {
    "aci": "tables/results_main.tex",
    "hyperparameters": "appx_tables/hyperparam_sweep.tex",
    "pass_at_k": "appx_tables/pass_at_k.tex",
    "failure_description": "appx/analyses/failure_modes.tex",
    "failure_categories": "appx_tables/failure_mode_categories.tex",
    "failure_figure": "figures/failure_modes_pie.pdf",
}

FIXED_PDF_TIME = datetime(2024, 5, 27, 0, 0, 0, tzinfo=timezone.utc)

ACI_EXPECTED = (
    ("editor", "edit_without_linting", "edit action", 15.0, 3.0, False),
    ("editor", "default_with_linting", "edit action with linting", 18.0, 0.0, True),
    ("editor", "no_edit", "No edit", 10.3, 7.7, False),
    ("search", "default_summarized", "Summarized", 18.0, 0.0, True),
    ("search", "iterative", "Iterative", 12.0, 6.0, False),
    ("search", "no_search", "No search", 15.7, 2.3, False),
    ("file_viewer", "window_30", "30 lines", 14.3, 3.7, False),
    ("file_viewer", "default_window_100", "100 lines", 18.0, 0.0, True),
    ("file_viewer", "full_file", "Full file", 12.7, 5.3, False),
    ("context", "default_last_5", "Last 5 observations", 18.0, 0.0, True),
    ("context", "full_history", "Full history", 15.0, 3.0, False),
    ("context", "no_demonstration", "Without demonstration", 16.3, 1.7, False),
)

ACI_ASSERTIONS = (
    r"\texttt{edit} action & 15.0  \decrease{3.0}",
    r"w/ linting \twemoji{cowboy_hat_face} & 18.0",
    r"No \texttt{edit} & 10.3 \decrease{7.7}",
    r"Summarized \twemoji{cowboy_hat_face} & 18.0",
    r"Iterative & 12.0 \decrease{6.0}",
    r"No search & 15.7 \decrease{2.3}",
    r"30 lines & 14.3 \decrease{3.7}",
    r"100 lines \twemoji{cowboy_hat_face}  & 18.0",
    r"Full file & 12.7 \decrease{5.3}",
    r"Last 5 Obs. \twemoji{cowboy_hat_face}  & 18.0",
    r"Full history & 15.0 \decrease{3.0}",
    r"w/o demo. & 16.3 \decrease{1.7}",
)

FAILURE_MODES = (
    ("Incorrect Implementation", "Incorrect Implementation", 39.9),
    ("Overly Specific Implementation", "Overly Specific Implementation", 12.1),
    ("Failed Edit Recovery", "Failed to Recover from Edit", 23.4),
    ("Failed to Find Edit Location", "Failed to Find Edit Location", 12.9),
    ("Failed to Find Relevant File", "Failed to Find Relevant File", 2.0),
    ("Gave Up Prematurely", "Gave Up Prematurely", 2.4),
    ("Failed to Reproduce", "Can’t Reproduce", 4.8),
    ("Ran Out of Budget", "Ran Out of Time", 2.4),
    ("Other", "Other", 0.0),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_source_members(source: Path) -> dict[str, bytes]:
    with tarfile.open(source, "r:gz") as archive:
        members: dict[str, bytes] = {}
        for key, member_name in PAPER_SOURCE_MEMBER.items():
            handle = archive.extractfile(member_name)
            if handle is None:
                raise FileNotFoundError(f"Missing arXiv source member: {member_name}")
            members[key] = handle.read()
    return members


def parse_hyperparameters(tex: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in tex.splitlines():
        clean = line.replace(r"{\bf", "").replace("}", "").replace("~", "")
        if not clean.strip().startswith(("GPT-4 Turbo", "Claude 3 Opus")):
            continue
        cells = [cell.strip() for cell in clean.split("&")]
        if len(cells) != 5:
            continue
        score_match = re.search(r"[0-9]+(?:\.[0-9]+)?", cells[4])
        if score_match is None:
            raise ValueError(f"Cannot parse hyperparameter score: {line}")
        rows.append(
            {
                "model": cells[0],
                "temperature": float(cells[1]),
                "window_lines": int(cells[2]),
                "history": cells[3].replace("Obs.", "observations"),
                "mean_resolved_percent": float(score_match.group()),
                "samples_per_configuration": 5,
                "dev_subset_instances": 37,
                "raw_runs_available": False,
            }
        )
    if len(rows) != 16:
        raise AssertionError(f"Expected 16 hyperparameter rows, found {len(rows)}")
    return rows


def parse_pass_at_k(tex: str) -> list[dict[str, Any]]:
    active_lines = [line.strip() for line in tex.splitlines() if not line.lstrip().startswith("%")]
    resolve_line = next(line for line in active_lines if line.startswith(r"Resolve \%"))
    pass_line = next(line for line in active_lines if line.startswith(r"Pass$@$k"))
    resolve_values = [float(value) for value in re.findall(r"\d+\.\d+", resolve_line)]
    pass_values = [float(value) for value in re.findall(r"\d+\.\d+", pass_line)]
    if len(resolve_values) != 8:
        raise AssertionError(f"Expected six runs, a mean, and a standard deviation: {resolve_values}")
    if len(pass_values) != 6:
        raise AssertionError(f"Expected six pass@k values: {pass_values}")

    run_values = resolve_values[:6]
    published_mean = resolve_values[6]
    published_std = resolve_values[7]
    calculated_mean = sum(run_values) / len(run_values)
    if round(calculated_mean, 2) != published_mean:
        raise AssertionError((calculated_mean, published_mean))

    rows: list[dict[str, Any]] = []
    for index, (run_percent, pass_percent) in enumerate(zip(run_values, pass_values), start=1):
        implied_resolved = round(run_percent * 300 / 100)
        if round(implied_resolved * 100 / 300, 2) != run_percent:
            raise AssertionError(f"Run {index} percentage does not imply an integer count")
        rows.append(
            {
                "k": index,
                "run_resolved_count": implied_resolved,
                "run_resolved_percent": run_percent,
                "pass_at_k_percent": pass_percent,
                "published_run_mean_percent": published_mean,
                "published_run_std_percent": published_std,
                "raw_predictions_available": False,
            }
        )
    return rows


def parse_aci(tex: str) -> list[dict[str, Any]]:
    for expected in ACI_ASSERTIONS:
        if expected not in tex:
            raise AssertionError(f"Missing ACI table assertion: {expected}")
    return [
        {
            "component": component,
            "variant": variant,
            "paper_label": label,
            "resolved_percent": resolved,
            "absolute_drop_points": drop,
            "is_paper_default": is_default,
            "raw_run_available": False,
        }
        for component, variant, label, resolved, drop, is_default in ACI_EXPECTED
    ]


def extract_pdf_text(pdf: bytes, executable: str) -> str:
    proc = subprocess.run(
        [executable, "-layout", "-", "-"],
        input=pdf,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"pdftotext failed: {message}")
    return proc.stdout.decode("utf-8", errors="replace")


def parse_failure_modes(
    pdf: bytes,
    description: str,
    category_table: str,
    pdftotext: str,
) -> list[dict[str, Any]]:
    if r"($n=248$)" not in description and r"($n=\num{248})" not in description:
        if "($n=248$)" not in description and "($n=$\\num{248})" not in description:
            raise AssertionError("Failure-analysis denominator 248 not found")
    if "one of \\num{9}" not in description and "possible failure categories" not in description:
        raise AssertionError("Failure-category description missing")

    pdf_text = extract_pdf_text(pdf, pdftotext)
    observed_percentages = [float(value) for value in re.findall(r"\b\d+\.\d\b", pdf_text)]
    expected_nonzero = sorted(percent for _, _, percent in FAILURE_MODES if percent > 0)
    if sorted(observed_percentages) != expected_nonzero:
        raise AssertionError((observed_percentages, expected_nonzero))

    rows: list[dict[str, Any]] = []
    for canonical, figure_label, percent in FAILURE_MODES:
        if canonical not in category_table:
            raise AssertionError(f"Category absent from appendix table: {canonical}")
        count = round(percent * 248 / 100)
        if percent and round(count * 100 / 248, 1) != percent:
            raise AssertionError((canonical, count, percent))
        rows.append(
            {
                "category": canonical,
                "figure_label": figure_label,
                "count": count,
                "percent": percent,
                "shown_in_figure": percent > 0,
                "raw_instance_labels_available": False,
            }
        )
    if sum(row["count"] for row in rows) != 248:
        raise AssertionError("Recovered failure-mode counts do not sum to 248")
    return rows


def write_csv(path: Path, rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def configure_plotting() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )
    return plt


def pdf_metadata(title: str) -> dict[str, Any]:
    return {
        "Title": title,
        "Author": "SWE-agent reproduction study",
        "Subject": "Aggregate values recovered from arXiv 2405.15793v3 source",
        "Keywords": "SWE-agent, reproduction, source aggregate",
        "CreationDate": FIXED_PDF_TIME,
        "ModDate": FIXED_PDF_TIME,
    }


def plot_pass_at_k(path: Path, rows: list[dict[str, Any]]) -> None:
    plt = configure_plotting()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(4.0, 2.8))
    x = [row["k"] for row in rows]
    y = [row["pass_at_k_percent"] for row in rows]
    axis.plot(x, y, color="#3159a7", marker="o", linewidth=2.0, markersize=4.5)
    axis.set_xlabel("k")
    axis.set_ylabel("% Resolved")
    axis.set_xticks(x)
    axis.set_ylim(15, 35)
    axis.grid(axis="y", color="#d9d9d9", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(path, format="pdf", metadata=pdf_metadata("SWE-agent pass@k source aggregate"))
    plt.close(fig)


def plot_failure_modes(path: Path, rows: list[dict[str, Any]]) -> None:
    plt = configure_plotting()
    path.parent.mkdir(parents=True, exist_ok=True)
    plotted = [row for row in rows if row["shown_in_figure"]]
    colors = ("#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974", "#64B5CD", "#8C8C8C", "#DD8452")
    fig, axis = plt.subplots(figsize=(8.4, 4.8))
    wedges, _, _ = axis.pie(
        [row["count"] for row in plotted],
        colors=colors,
        startangle=85,
        counterclock=False,
        autopct=lambda value: f"{value:.1f}",
        pctdistance=0.72,
        wedgeprops={"linewidth": 0.7, "edgecolor": "white"},
    )
    axis.legend(
        wedges,
        [row["figure_label"] for row in plotted],
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=8,
    )
    axis.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path, format="pdf", metadata=pdf_metadata("SWE-agent failure modes source aggregate"))
    plt.close(fig)


def file_record(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": sha256(data),
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=project_root / "paper" / "2405.15793_source.tar.gz")
    parser.add_argument(
        "--pdftotext",
        default="pdftotext",
        help="pdftotext executable; pass an absolute path when it is not on PATH",
    )
    parser.add_argument("--skip-figures", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    members = read_source_members(source)
    text = {key: value.decode("utf-8") for key, value in members.items() if not key.endswith("figure")}

    aci_rows = parse_aci(text["aci"])
    hyperparameter_rows = parse_hyperparameters(text["hyperparameters"])
    pass_rows = parse_pass_at_k(text["pass_at_k"])
    failure_rows = parse_failure_modes(
        members["failure_figure"],
        text["failure_description"],
        text["failure_categories"],
        args.pdftotext,
    )

    outputs = {
        "aci": project_root / "data" / "derived" / "paper_aci_ablation_results.csv",
        "hyperparameters": project_root / "data" / "derived" / "paper_hyperparameter_sweep.csv",
        "pass_at_k": project_root / "data" / "derived" / "paper_pass_at_k.csv",
        "failure_modes": project_root / "data" / "derived" / "paper_failure_mode_counts.csv",
        "pass_at_k_pdf": project_root / "output" / "pdf" / "pass_at_k_source_aggregate.pdf",
        "failure_modes_pdf": project_root / "output" / "pdf" / "failure_modes_source_aggregate.pdf",
    }

    write_csv(outputs["aci"], aci_rows, tuple(aci_rows[0].keys()))
    write_csv(outputs["hyperparameters"], hyperparameter_rows, tuple(hyperparameter_rows[0].keys()))
    write_csv(outputs["pass_at_k"], pass_rows, tuple(pass_rows[0].keys()))
    write_csv(outputs["failure_modes"], failure_rows, tuple(failure_rows[0].keys()))
    if not args.skip_figures:
        plot_pass_at_k(outputs["pass_at_k_pdf"], pass_rows)
        plot_failure_modes(outputs["failure_modes_pdf"], failure_rows)

    output_records = [file_record(path, project_root) for key, path in outputs.items() if path.exists()]
    manifest = {
        "schema_version": 1,
        "as_of": "2026-07-16",
        "evidence_type": "paper_source_aggregate",
        "paper": {
            "arxiv_id": "2405.15793",
            "version": "v3",
            "source": file_record(source, project_root),
            "members": {
                key: {
                    "path": PAPER_SOURCE_MEMBER[key],
                    "bytes": len(value),
                    "sha256": sha256(value),
                }
                for key, value in members.items()
            },
        },
        "recovered": {
            "aci_table_rows": len(aci_rows),
            "aci_nondefault_ablations": sum(not row["is_paper_default"] for row in aci_rows),
            "hyperparameter_configurations": len(hyperparameter_rows),
            "pass_at_k_points": len(pass_rows),
            "failure_category_schema_size": len(failure_rows),
            "failure_nonzero_categories": sum(row["shown_in_figure"] for row in failure_rows),
            "failure_instances": sum(row["count"] for row in failure_rows),
        },
        "limitations": [
            "ACI ablation trajectories, predictions, and evaluation logs are not present in the paper package.",
            "The random 37-instance dev subset and all hyperparameter-sweep raw runs are not present.",
            "The six pass@k prediction sets and per-instance resolution matrix are not present.",
            "The 248 model-generated failure labels, 15 validation IDs, and hand labels are not present.",
            "The zero-count Other failure category is inferred because the appendix defines nine categories while the vector figure shows eight nonzero slices summing to 248.",
        ],
        "outputs": output_records,
    }
    manifest_path = project_root / "data" / "manifests" / "paper_source_aggregate_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(manifest["recovered"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
