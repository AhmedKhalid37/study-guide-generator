#!/usr/bin/env python3
"""Slice 149 — Measured Guide Quality Baseline harness.

Two modes, one entrypoint:

1. **Synthetic self-test (default, no flags).** Exercises the pure baseline
   aggregator (`pipeline/guide_quality_baseline.py`) end-to-end using
   **synthetic artifact JSON written to a temp dir only**. It proves the harness
   aggregates existing wired artifacts into a closed baseline record with all
   required metric families — with ``reasoning_leak_status`` as a first-class
   headline metric — and that a trend diff works on closed statuses. No real
   local fixture/job is required.

2. **Local operator run (``--artifact-dir`` given).** Reads the existing
   exact-name wired artifact JSONs from a caller-provided **local, gitignored**
   job artifact directory and emits a **closed aggregate summary only**. It
   reruns no checks, reads no PDFs/guides/``clean.md``/source/OCR text, and calls
   no provider/model/cloud/local LLM. The artifact directory path is **never**
   printed; no raw artifact JSON, source/guide text, snippets, formulas,
   filenames, or paths are ever printed — only closed status tokens and closed
   warning labels. It exits nonzero only on a harness error (e.g. an unreadable
   golden spec or a missing ``--artifact-dir``), never because a metric is
   honestly ``not_available`` / ``needs_future_metric`` / ``fail``.

This is a measurement harness, **not** judge execution and **not** production
artifact writing. Temp paths and local job paths are never printed.

Run (synthetic):  python test_scripts/validate_guide_quality_baseline_harness.py
Run (local):
  python test_scripts/validate_guide_quality_baseline_harness.py \
    --golden-spec test_scripts/fixtures/guide_quality_baseline/nn_iris_local_golden_spec.json \
    --artifact-dir <local_gitignored_job_artifact_dir> \
    --run-label app_run_1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.guide_quality_baseline import (  # noqa: E402
    build_guide_quality_baseline_record,
    collect_guide_quality_baseline_artifacts,
    collect_guide_quality_baseline_guide_text_metrics,
    compare_guide_quality_baseline_records,
    normalize_guide_quality_baseline_golden_spec,
    serialize_guide_quality_baseline_record,
)

VALIDATION_ID = "guide_quality_baseline_harness"
LOCAL_VALIDATION_ID = "guide_quality_baseline_local_operator_run"

FIXTURE = (
    REPO / "test_scripts" / "fixtures" / "guide_quality_baseline" / "nn_iris_local_golden_spec.json"
)

# Metric families surfaced flat in the local-mode summary (stable order).
_METRIC_FAMILIES = (
    "reasoning_leak_status",
    "numeric_math_status",
    "guide_quality_qa_gate_status",
    "source_coverage_status",
    "structure_contract_status",
    "reference_relative_completeness_status",
    "figure_handling_status",
    "artifact_existence_status",
)

# Closed guide-text coverage counts surfaced in local mode when --guide-text given.
_GUIDE_TEXT_COUNT_KEYS = (
    "required_reference_check_count",
    "matched_reference_check_count",
    "missing_reference_check_count",
    "expected_figure_check_count",
    "matched_figure_check_count",
    "missing_figure_check_count",
    "section_check_count",
    "matched_section_check_count",
    "missing_section_check_count",
)

# Synthetic canaries that must never survive into the serialized closed record.
CANARIES = (
    "/home/operator/private_deck.pdf",
    "Bearer sk-secret-token",
    "softmax of the iris hidden layer equals 0.97",
)

# A run label is a short closed token only — never a path or content.
_RUN_LABEL_OK = re.compile(r"^[A-Za-z0-9_\-.]{1,48}$")


def _safe_run_label(value: object) -> str:
    if isinstance(value, str) and _RUN_LABEL_OK.match(value) and ".." not in value:
        return value
    return "local"


def _write(directory: Path, name: str, payload: dict) -> None:
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def _clean_artifacts(directory: Path) -> None:
    """A healthy synthetic job dir: required + optional artifacts, all clean."""
    _write(
        directory,
        "guide_quality_contract_lint.json",
        {
            "version": 1,
            "kind": "guide_quality_report",
            "status": "completed",
            "summary": {
                "reasoning_leak_count": 0,
                "required_section_count": 4,
                "required_section_present_count": 4,
                "warning_count": 0,
                # Canary in an unread field — must not propagate.
                "source_name": CANARIES[0],
            },
        },
    )
    _write(
        directory,
        "guide_quality_qa_gate.json",
        {
            "version": 1,
            "kind": "guide_quality_gate",
            "status": "passed",
            "summary": {"check_count": 6, "passed_count": 6, "warning_count": 0, "unknown_count": 0},
        },
    )
    _write(
        directory,
        "math_verification.json",
        {
            "version": 1,
            "source_name": CANARIES[0],
            "summary": {"total": 5, "ok": 5, "mismatch": 0, "unparseable": 0},
            "claims": [{"text": CANARIES[2]}],
        },
    )
    _write(
        directory,
        "source_coverage_report.json",
        {
            "version": 1,
            "kind": "source_coverage_report",
            "status": "complete",
            "summary": {"source_count": 1, "complete_source_count": 1, "visual_candidate_pages": 2},
        },
    )


def run_local_baseline(
    golden_spec_path: object,
    artifact_dir: object,
    run_label: object,
    guide_text_path: object = None,
) -> dict:
    """Read a local artifact dir and return a closed-summary-only dict.

    Never includes the artifact directory path or any raw artifact body. On a
    harness error (unreadable spec / missing dir) returns a dict whose
    ``baseline_harness_status`` is ``error`` (caller maps that to a nonzero exit).
    Honest measurement outcomes (including ``failed``/``partial``/``skipped``
    baseline status) return ``baseline_harness_status`` ``ok``.

    When ``guide_text_path`` is given, the local gitignored guide text is read
    only to compute **closed coverage counts/statuses** — the path, the text, any
    snippet, and any matched alias are never printed or returned.
    """
    label = _safe_run_label(run_label)

    try:
        spec_data = json.loads(Path(str(golden_spec_path)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "validation_id": LOCAL_VALIDATION_ID,
            "run_label": label,
            "baseline_harness_status": "error",
            "local_operator_baseline_run": "closed_summary_only",
            "error": "golden_spec_unreadable",
        }

    if not (isinstance(artifact_dir, (str, os.PathLike)) and os.path.isdir(artifact_dir)):
        return {
            "validation_id": LOCAL_VALIDATION_ID,
            "run_label": label,
            "baseline_harness_status": "error",
            "local_operator_baseline_run": "closed_summary_only",
            "error": "artifact_dir_not_found",
        }

    # Optional local guide text → closed coverage metrics only (text never kept).
    guide_text_metrics = None
    guide_text_available = False
    if guide_text_path is not None:
        try:
            guide_text = Path(str(guide_text_path)).read_text(encoding="utf-8")
        except (OSError, ValueError):
            return {
                "validation_id": LOCAL_VALIDATION_ID,
                "run_label": label,
                "baseline_harness_status": "error",
                "local_operator_baseline_run": "closed_summary_only",
                "error": "guide_text_unreadable",
            }
        guide_text_metrics = collect_guide_quality_baseline_guide_text_metrics(guide_text, spec_data)
        guide_text_available = bool(guide_text_metrics.get("guide_text_available"))
        # Drop the local text reference immediately; only closed counts survive.
        del guide_text

    # The collector returns closed scalars only and never echoes the dir path.
    artifacts = collect_guide_quality_baseline_artifacts(artifact_dir)
    record = build_guide_quality_baseline_record(
        spec_data,
        artifacts,
        run_metadata={"local_operator_run": "closed_summary_only"},
        guide_text_metrics=guide_text_metrics,
    )
    metrics = record.get("metrics", {})

    def _status(name: str) -> str:
        entry = metrics.get(name)
        if isinstance(entry, dict):
            value = entry.get("status")
            if isinstance(value, str):
                return value
        return "not_available"

    summary: dict[str, object] = {
        "validation_id": LOCAL_VALIDATION_ID,
        "run_label": label,
        "baseline_harness_status": "ok",
        "local_operator_baseline_run": "closed_summary_only",
        "baseline_status": record.get("status", "skipped"),
        "local_guide_text_available": guide_text_available,
    }
    for family in _METRIC_FAMILIES:
        summary[family] = _status(family)
    coverage = record.get("guide_text_coverage", {})
    if guide_text_available and isinstance(coverage, dict):
        for key in _GUIDE_TEXT_COUNT_KEYS:
            value = coverage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                summary[key] = value
    summary["warnings"] = list(record.get("warnings", []))

    # Defensive last line of defense: no local path may ever appear in output.
    rendered = json.dumps(summary, sort_keys=True)
    leak_paths = [str(artifact_dir)]
    if guide_text_path is not None:
        leak_paths.append(str(guide_text_path))
    if any(p and p in rendered for p in leak_paths):
        return {
            "validation_id": LOCAL_VALIDATION_ID,
            "run_label": label,
            "baseline_harness_status": "error",
            "local_operator_baseline_run": "closed_summary_only",
            "error": "path_leak_guard_tripped",
        }
    return summary


def _run_local_mode(args: argparse.Namespace) -> int:
    summary = run_local_baseline(
        args.golden_spec, args.artifact_dir, args.run_label, args.guide_text
    )
    print(json.dumps(summary, sort_keys=True))
    return 1 if summary.get("baseline_harness_status") == "error" else 0


def _run_synthetic_selftest() -> int:
    failures: list[str] = []

    spec_data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    spec = normalize_guide_quality_baseline_golden_spec(spec_data)
    golden_spec_status = "ok" if spec.get("valid") else "fail"
    if not spec.get("valid"):
        failures.append("golden_spec_invalid")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        _clean_artifacts(tmp_dir)

        artifacts = collect_guide_quality_baseline_artifacts(tmp_dir)
        # Collector must never echo the directory path.
        if str(tmp_dir) in json.dumps(artifacts):
            failures.append("collector_leaked_path")

        record = build_guide_quality_baseline_record(spec_data, artifacts)
        serialized = serialize_guide_quality_baseline_record(record)

        baseline_harness_status = "ok" if record.get("status") in {"ok", "warning", "partial"} else "fail"
        if record.get("status") not in {"ok", "warning", "partial"}:
            failures.append(f"unexpected_overall_status:{record.get('status')}")

        metrics = record.get("metrics", {})
        reasoning = metrics.get("reasoning_leak_status", {})
        reasoning_leak_metric_status = "ok" if reasoning.get("status") == "pass" else "fail"
        if reasoning.get("status") != "pass":
            failures.append("reasoning_leak_not_pass")
        if reasoning.get("source") != "guide_quality_contract_lint":
            failures.append("reasoning_leak_wrong_source")

        numeric = metrics.get("numeric_math_status", {})
        numeric_math_metric_status = "ok" if numeric.get("status") == "pass" else "fail"
        if numeric.get("status") != "pass":
            failures.append("numeric_math_not_pass")

        # Every required metric family must be present.
        for family in _METRIC_FAMILIES:
            if family not in metrics:
                failures.append(f"missing_metric_family:{family}")

        artifact_reuse_status = "ok"
        inputs = record.get("artifact_inputs", {})
        for name in ("math_verification", "guide_quality_contract_lint", "guide_quality_qa_gate"):
            if inputs.get(name) != "present":
                artifact_reuse_status = "fail"
                failures.append(f"required_artifact_not_present:{name}")

        # No canary may survive into the serialized closed record.
        for canary in CANARIES:
            if canary in serialized:
                failures.append("canary_survived")

        # Trend diff: no previous, then improved vs a regressed prior.
        no_prev = compare_guide_quality_baseline_records(record, None)
        if no_prev.get("status") != "no_previous":
            failures.append("trend_no_previous_failed")

        prior = build_guide_quality_baseline_record(spec_data, artifacts)
        prior["metrics"]["reasoning_leak_status"] = {"status": "fail", "source": "guide_quality_contract_lint"}
        improved = compare_guide_quality_baseline_records(record, prior)
        if improved.get("status") != "improved":
            failures.append("trend_improved_failed")

    summary = {
        "validation_id": VALIDATION_ID,
        "baseline_harness_status": baseline_harness_status,
        "artifact_reuse_status": artifact_reuse_status,
        "reasoning_leak_metric_status": reasoning_leak_metric_status,
        "numeric_math_metric_status": numeric_math_metric_status,
        "golden_spec_status": golden_spec_status,
        "local_operator_baseline_run": "not_run",
        "next_step": "style_preset_audit_using_baseline",
        "failure_count": len(failures),
    }
    print(json.dumps(summary, sort_keys=True))
    if failures:
        print(json.dumps({"failures": sorted(set(failures))}, sort_keys=True))
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measured guide-quality baseline harness.")
    parser.add_argument(
        "--golden-spec",
        default=str(FIXTURE),
        help="Path to the committed closed golden spec (default: nn_iris fixture).",
    )
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="Local gitignored job artifact directory. When given, runs local mode.",
    )
    parser.add_argument(
        "--run-label",
        default="local",
        help="Closed run label echoed in local-mode output (e.g. app_run_1).",
    )
    parser.add_argument(
        "--guide-text",
        default=None,
        help=(
            "Optional local gitignored generated-guide text file. Read only to "
            "compute closed coverage counts/statuses; path/text never printed."
        ),
    )
    args = parser.parse_args(argv)

    if args.artifact_dir is not None:
        return _run_local_mode(args)
    return _run_synthetic_selftest()


if __name__ == "__main__":
    raise SystemExit(main())
