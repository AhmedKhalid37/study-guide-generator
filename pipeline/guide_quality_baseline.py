"""Slice 149 — Measured Guide Quality Baseline aggregator/diff harness.

A pure, deterministic, stdlib-only aggregator that scores a *real, locally
generated* study guide by **reusing existing wired artifacts** rather than
rebuilding a parallel Quality Safety / guide-quality stack. It reads the
existing exact-name artifact JSON files from a caller-provided local job
artifact directory, extracts **closed scalar statuses / counts only**, compares
them against a committed *golden spec* (closed facts/labels/expectations, never
copied source text), and emits a closed aggregate baseline record plus an
optional trend diff against a previous closed record.

Strict boundaries (do not weaken):

- **Reuse, do not rebuild.** This module never reimplements math verification,
  guide-quality contract lint, the QA gate, source coverage, or the rubric. It
  only reads the closed summaries those producers already emit.
- **No content ever leaves.** It never reads PDFs / DOCX / images / generated
  guides / ``clean.md`` / source / OCR / table / caption text. From each
  artifact it copies only whitelisted scalar fields (ints, bools, and a small
  set of known status tokens) — never raw artifact bodies, ``claims`` text,
  ``source_name`` filenames, ``checks`` instructions, paths, or free strings.
- **No path leakage.** The collector accepts a directory but never returns,
  prints, or embeds that path (or any filename beyond the exact safe artifact
  names) in its output.
- **No external calls.** stdlib only; no FastAPI / frontend / provider / model /
  cloud / local-LLM / render / OCR / job-runtime imports.
- **Advisory + non-blocking.** This is a measurement baseline, not a gate.

Public surface:
  - ``normalize_guide_quality_baseline_golden_spec(data) -> dict``
  - ``collect_guide_quality_baseline_artifacts(artifact_dir, *, artifact_names=None) -> dict``
  - ``build_guide_quality_baseline_record(golden_spec, artifacts, *, run_metadata=None) -> dict``
  - ``compare_guide_quality_baseline_records(current_record, previous_record=None) -> dict``
  - ``serialize_guide_quality_baseline_record(record) -> str``
"""
from __future__ import annotations

import json
import os
from typing import Any

# =============================================================================
# Constants / closed vocabularies
# =============================================================================

RECORD_VERSION = 1
RECORD_KIND = "guide_quality_measured_baseline_record"
GOLDEN_SPEC_KIND = "guide_quality_baseline_golden_spec"

# Exact artifact names this baseline is allowed to read. Nothing else is opened.
MATH_VERIFICATION = "math_verification.json"
CONTRACT_LINT = "guide_quality_contract_lint.json"
QA_GATE = "guide_quality_qa_gate.json"
REPORT_V2 = "guide_quality_report_v2.json"
SOURCE_COVERAGE = "source_coverage_report.json"
RUBRIC_SCORE = "guide_quality_rubric_score.json"

# Stable logical keys used in the collector / record (never expose paths).
_LOGICAL_NAMES: dict[str, str] = {
    "math_verification": MATH_VERIFICATION,
    "guide_quality_contract_lint": CONTRACT_LINT,
    "guide_quality_qa_gate": QA_GATE,
    "guide_quality_report_v2": REPORT_V2,
    "source_coverage_report": SOURCE_COVERAGE,
    "guide_quality_rubric_score": RUBRIC_SCORE,
}

# Core artifacts required for a non-degraded baseline.
_REQUIRED_ARTIFACTS = ("math_verification", "guide_quality_contract_lint", "guide_quality_qa_gate")
_OPTIONAL_ARTIFACTS = ("guide_quality_report_v2", "source_coverage_report", "guide_quality_rubric_score")

# Closed status vocabularies.
PRESENCE_PRESENT = "present"
PRESENCE_MISSING = "missing"
PRESENCE_MALFORMED = "malformed"
_PRESENCE_TOKENS = frozenset({PRESENCE_PRESENT, PRESENCE_MISSING, PRESENCE_MALFORMED})

# Overall baseline status.
OVERALL_OK = "ok"
OVERALL_WARNING = "warning"
OVERALL_PARTIAL = "partial"
OVERALL_FAILED = "failed"
OVERALL_SKIPPED = "skipped"

# Metric status.
METRIC_PASS = "pass"
METRIC_WARNING = "warning"
METRIC_FAIL = "fail"
METRIC_NOT_AVAILABLE = "not_available"
METRIC_NEEDS_FUTURE = "needs_future_metric"
METRIC_NOT_OBSERVED = "not_observed"
METRIC_SKIPPED = "skipped"
_METRIC_TOKENS = frozenset(
    {
        METRIC_PASS,
        METRIC_WARNING,
        METRIC_FAIL,
        METRIC_NOT_AVAILABLE,
        METRIC_NEEDS_FUTURE,
        METRIC_NOT_OBSERVED,
        METRIC_SKIPPED,
    }
)

# Trend status.
TREND_IMPROVED = "improved"
TREND_UNCHANGED = "unchanged"
TREND_REGRESSED = "regressed"
TREND_NO_PREVIOUS = "no_previous"

# Local operator run vocabulary (never carries content).
RUN_NOT_RUN = "not_run"
RUN_CLOSED_SUMMARY_ONLY = "closed_summary_only"

# Required metric families (order is stable for deterministic output).
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

# Ranking for trend comparison: higher is better.
_METRIC_RANK: dict[str, int] = {
    METRIC_FAIL: 0,
    METRIC_WARNING: 1,
    METRIC_SKIPPED: 2,
    METRIC_NOT_OBSERVED: 2,
    METRIC_NOT_AVAILABLE: 2,
    METRIC_NEEDS_FUTURE: 2,
    METRIC_PASS: 3,
}

# Whitelisted scalar summary keys per artifact (ints/bools only; never strings).
_CONTRACT_LINT_INT_KEYS = (
    "reasoning_leak_count",
    "required_section_count",
    "required_section_present_count",
    "exam_alert_count",
    "table_count",
    "warning_count",
)
_QA_GATE_INT_KEYS = ("check_count", "passed_count", "warning_count", "unknown_count")
_MATH_INT_KEYS = ("total", "ok", "mismatch", "unparseable")
_REPORT_V2_INT_KEYS = ("coverage_signal_count", "visual_signal_count", "warning_count")
_SOURCE_COVERAGE_INT_KEYS = (
    "source_count",
    "complete_source_count",
    "partial_source_count",
    "skipped_source_count",
    "unreadable_source_count",
    "visual_candidate_pages",
)

# A small closed set of top-level artifact status tokens we are willing to echo.
_SAFE_STATUS_TOKENS = frozenset(
    {
        "ok",
        "completed",
        "complete",
        "passed",
        "warning",
        "partial",
        "skipped",
        "unreadable",
        "unknown",
        "failed",
        "mismatch",
    }
)

# Golden-spec scalar/label fields that are safe to retain (closed labels only).
_GOLDEN_LIST_FIELDS = (
    "required_concepts",
    "key_facts",
    "known_numbers",
    "must_not_claim",
    "expected_sections",
)


# =============================================================================
# Safe coercion helpers
# =============================================================================


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _safe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _safe_status_token(value: Any) -> str | None:
    """Return a top-level status token only if it is in the safe closed set."""
    if isinstance(value, str) and value in _SAFE_STATUS_TOKENS:
        return value
    return None


def _looks_path_like(value: str) -> bool:
    """Reject obviously path-like / private strings in committed golden labels."""
    if "/" in value or "\\" in value:
        return True
    if value.startswith("~") or value.startswith("."):
        return True
    lowered = value.lower()
    for marker in (".pdf", ".docx", ".zip", ".png", ".jpg", ".jpeg", ".md", "data:", "://"):
        if marker in lowered:
            return True
    return False


def _safe_label(value: Any) -> str | None:
    """A closed label is a short non-path-like token-style string."""
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token or len(token) > 80:
        return None
    if _looks_path_like(token):
        return None
    return token


# =============================================================================
# Golden spec normalization
# =============================================================================


def normalize_guide_quality_baseline_golden_spec(data: Any) -> dict[str, Any]:
    """Normalize a golden spec to closed labels only.

    Unsafe / path-like / content-bearing strings are stripped (not preserved).
    Always returns a well-formed dict; ``valid`` reflects whether the input was
    a usable golden spec of the expected kind.
    """
    warnings: list[str] = []
    if not isinstance(data, dict):
        return _empty_golden_spec(["golden_spec_not_a_mapping"], valid=False)

    kind = data.get("kind")
    valid = kind == GOLDEN_SPEC_KIND
    if not valid:
        warnings.append("golden_spec_unexpected_kind")

    fixture_id = _safe_label(data.get("fixture_id")) or "unknown_fixture"
    fixture_mode = _safe_label(data.get("fixture_mode")) or "local_gitignored_source"
    provenance = _safe_label(data.get("provenance_status")) or "operator_local_only"

    spec: dict[str, Any] = {
        "version": _safe_int(data.get("version")) or RECORD_VERSION,
        "kind": GOLDEN_SPEC_KIND,
        "fixture_id": fixture_id,
        "fixture_mode": fixture_mode,
        "source_material_committed": bool(data.get("source_material_committed", False)),
        "generated_guide_committed": bool(data.get("generated_guide_committed", False)),
        "provenance_status": provenance,
        "valid": valid,
    }

    for field in _GOLDEN_LIST_FIELDS:
        raw = data.get(field)
        clean: list[str] = []
        if isinstance(raw, list):
            for item in raw:
                label = _safe_label(item)
                if label is not None and label not in clean:
                    clean.append(label)
            if len(clean) != len(raw):
                warnings.append(f"{field}_entries_dropped")
        elif raw is not None:
            warnings.append(f"{field}_not_a_list")
        spec[field] = clean

    figures: list[dict[str, str]] = []
    raw_figures = data.get("expected_figures_or_diagrams")
    if isinstance(raw_figures, list):
        for item in raw_figures:
            if not isinstance(item, dict):
                warnings.append("expected_figure_entry_dropped")
                continue
            fig_id = _safe_label(item.get("id"))
            fig_status = _safe_label(item.get("expected_status")) or "expected_or_explained_missing"
            if fig_id is None:
                warnings.append("expected_figure_entry_dropped")
                continue
            figures.append({"id": fig_id, "expected_status": fig_status})
    elif raw_figures is not None:
        warnings.append("expected_figures_not_a_list")
    spec["expected_figures_or_diagrams"] = figures

    # Carry through only closed warning labels supplied by the spec author.
    spec_warnings: list[str] = []
    raw_warnings = data.get("warnings")
    if isinstance(raw_warnings, list):
        for item in raw_warnings:
            label = _safe_label(item)
            if label is not None and label not in spec_warnings:
                spec_warnings.append(label)
    spec["spec_warnings"] = spec_warnings

    # Drop duplicate normalization warnings deterministically.
    spec["normalization_warnings"] = sorted(set(warnings))
    return spec


def _empty_golden_spec(warnings: list[str], *, valid: bool) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "version": RECORD_VERSION,
        "kind": GOLDEN_SPEC_KIND,
        "fixture_id": "unknown_fixture",
        "fixture_mode": "local_gitignored_source",
        "source_material_committed": False,
        "generated_guide_committed": False,
        "provenance_status": "operator_local_only",
        "valid": valid,
    }
    for field in _GOLDEN_LIST_FIELDS:
        spec[field] = []
    spec["expected_figures_or_diagrams"] = []
    spec["spec_warnings"] = []
    spec["normalization_warnings"] = sorted(set(warnings))
    return spec


# =============================================================================
# Artifact collection (closed scalar extraction only)
# =============================================================================


def collect_guide_quality_baseline_artifacts(
    artifact_dir: Any, *, artifact_names: Any = None
) -> dict[str, Any]:
    """Read exact-name artifacts from a local job dir; extract closed scalars only.

    Returns a mapping ``logical_name -> {presence, status, counts}`` where:
      - ``presence`` is one of present/missing/malformed
      - ``status`` is a safe top-level status token or ``None``
      - ``counts`` holds only whitelisted integer/bool scalars

    The artifact directory path is **never** returned, printed, or embedded.
    Missing artifacts and malformed JSON are tolerated.
    """
    selected = _select_logical_names(artifact_names)
    result: dict[str, Any] = {}

    dir_ok = isinstance(artifact_dir, (str, os.PathLike)) and os.path.isdir(artifact_dir)

    for logical in selected:
        filename = _LOGICAL_NAMES[logical]
        if not dir_ok:
            result[logical] = _artifact_entry(PRESENCE_MISSING)
            continue
        path = os.path.join(str(artifact_dir), filename)
        if not os.path.isfile(path):
            result[logical] = _artifact_entry(PRESENCE_MISSING)
            continue
        data = _read_json_defensively(path)
        if data is None or not isinstance(data, dict):
            result[logical] = _artifact_entry(PRESENCE_MALFORMED)
            continue
        result[logical] = _extract_artifact_scalars(logical, data)

    return result


def _select_logical_names(artifact_names: Any) -> list[str]:
    if artifact_names is None:
        return list(_LOGICAL_NAMES.keys())
    selected: list[str] = []
    for name in artifact_names:
        # Accept either the logical key or the exact filename.
        if name in _LOGICAL_NAMES:
            if name not in selected:
                selected.append(name)
            continue
        for logical, filename in _LOGICAL_NAMES.items():
            if name == filename and logical not in selected:
                selected.append(logical)
                break
    return selected


def _read_json_defensively(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _artifact_entry(presence: str, *, status: str | None = None, counts: dict | None = None) -> dict[str, Any]:
    safe_presence = presence if presence in _PRESENCE_TOKENS else PRESENCE_MISSING
    return {
        "presence": safe_presence,
        "status": status,
        "counts": dict(counts or {}),
    }


def _extract_artifact_scalars(logical: str, data: dict[str, Any]) -> dict[str, Any]:
    """Copy only whitelisted scalar fields out of an artifact body."""
    status = _safe_status_token(data.get("status"))
    summary = data.get("summary")
    summary = summary if isinstance(summary, dict) else {}

    int_keys: tuple[str, ...] = ()
    if logical == "guide_quality_contract_lint":
        int_keys = _CONTRACT_LINT_INT_KEYS
    elif logical == "guide_quality_qa_gate":
        int_keys = _QA_GATE_INT_KEYS
    elif logical == "math_verification":
        int_keys = _MATH_INT_KEYS
    elif logical == "guide_quality_report_v2":
        int_keys = _REPORT_V2_INT_KEYS
    elif logical == "source_coverage_report":
        int_keys = _SOURCE_COVERAGE_INT_KEYS

    counts: dict[str, int] = {}
    for key in int_keys:
        value = _safe_int(summary.get(key))
        if value is not None:
            counts[key] = value

    return _artifact_entry(PRESENCE_PRESENT, status=status, counts=counts)


# =============================================================================
# Metric derivation
# =============================================================================


def _metric(status: str, source: str) -> dict[str, str]:
    safe_status = status if status in _METRIC_TOKENS else METRIC_NOT_AVAILABLE
    return {"status": safe_status, "source": source}


def _present(entry: dict[str, Any] | None) -> bool:
    return bool(entry) and entry.get("presence") == PRESENCE_PRESENT


def _derive_reasoning_leak(artifacts: dict[str, Any]) -> dict[str, str]:
    """Headline, first-class metric. Prefer contract lint, then QA gate."""
    lint = artifacts.get("guide_quality_contract_lint")
    if _present(lint):
        leak = lint["counts"].get("reasoning_leak_count")
        if leak is not None:
            return _metric(METRIC_FAIL if leak > 0 else METRIC_PASS, "guide_quality_contract_lint")
    gate = artifacts.get("guide_quality_qa_gate")
    if _present(gate):
        # QA gate's reasoning_leak check is folded into warning_count; if the
        # gate ran with zero warnings it is a clean signal, otherwise warn.
        warnings = gate["counts"].get("warning_count")
        status = gate.get("status")
        if warnings is not None:
            if warnings == 0 and status in {"passed", "ok"}:
                return _metric(METRIC_PASS, "guide_quality_qa_gate")
            return _metric(METRIC_WARNING, "guide_quality_qa_gate")
    return _metric(METRIC_NOT_AVAILABLE, "not_available")


def _derive_numeric_math(artifacts: dict[str, Any], golden_spec: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    extra_warnings: list[str] = []
    math = artifacts.get("math_verification")
    if not _present(math):
        return _metric(METRIC_NOT_AVAILABLE, "not_available"), extra_warnings
    counts = math["counts"]
    total = counts.get("total")
    mismatch = counts.get("mismatch")
    unparseable = counts.get("unparseable")
    # Spec-relative numeric scoring needs scored known_numbers; defer otherwise.
    if not golden_spec.get("known_numbers"):
        extra_warnings.append("numeric_spec_relative_scoring_needs_future_metric")
    if total is None:
        return _metric(METRIC_NOT_AVAILABLE, "math_verification"), extra_warnings
    if total == 0:
        return _metric(METRIC_NOT_OBSERVED, "math_verification"), extra_warnings
    if mismatch and mismatch > 0:
        return _metric(METRIC_FAIL, "math_verification"), extra_warnings
    if unparseable and unparseable > 0:
        return _metric(METRIC_WARNING, "math_verification"), extra_warnings
    return _metric(METRIC_PASS, "math_verification"), extra_warnings


def _derive_qa_gate(artifacts: dict[str, Any]) -> dict[str, str]:
    gate = artifacts.get("guide_quality_qa_gate")
    if not _present(gate):
        return _metric(METRIC_NOT_AVAILABLE, "not_available")
    status = gate.get("status")
    if status in {"passed", "ok"}:
        return _metric(METRIC_PASS, "guide_quality_qa_gate")
    if status in {"warning", "partial"}:
        return _metric(METRIC_WARNING, "guide_quality_qa_gate")
    if status == "skipped":
        return _metric(METRIC_NOT_OBSERVED, "guide_quality_qa_gate")
    return _metric(METRIC_NOT_OBSERVED, "guide_quality_qa_gate")


def _derive_source_coverage(artifacts: dict[str, Any]) -> dict[str, str]:
    cov = artifacts.get("source_coverage_report")
    if not _present(cov):
        return _metric(METRIC_NOT_AVAILABLE, "not_available")
    status = cov.get("status")
    # The producer's top-level report status token is "completed"
    # (pipeline/source_coverage_report.py::_top_level_status); per-source status
    # uses "complete". Accept both (plus "ok") so a fully-covered source maps to
    # pass instead of silently falling through to not_observed.
    if status in {"completed", "complete", "ok"}:
        return _metric(METRIC_PASS, "source_coverage_report")
    if status == "partial":
        return _metric(METRIC_WARNING, "source_coverage_report")
    if status == "unreadable":
        return _metric(METRIC_FAIL, "source_coverage_report")
    if status == "skipped":
        return _metric(METRIC_NOT_OBSERVED, "source_coverage_report")
    return _metric(METRIC_NOT_OBSERVED, "source_coverage_report")


def _derive_structure_contract(artifacts: dict[str, Any]) -> dict[str, str]:
    lint = artifacts.get("guide_quality_contract_lint")
    if _present(lint):
        required = lint["counts"].get("required_section_count")
        present = lint["counts"].get("required_section_present_count")
        if required is not None and present is not None:
            if present >= required:
                return _metric(METRIC_PASS, "guide_quality_contract_lint")
            return _metric(METRIC_WARNING, "guide_quality_contract_lint")
    report = artifacts.get("guide_quality_report_v2")
    if _present(report):
        warnings = report["counts"].get("warning_count")
        if warnings is not None:
            return _metric(METRIC_PASS if warnings == 0 else METRIC_WARNING, "guide_quality_report_v2")
    return _metric(METRIC_NOT_AVAILABLE, "not_available")


def _derive_reference_relative_completeness(golden_spec: dict[str, Any]) -> dict[str, str]:
    # The existing wired artifacts do not expose concept/section labels that can
    # be safely matched against golden labels without parsing guide text, so
    # this thin metric is deferred rather than faked.
    if golden_spec.get("required_concepts") or golden_spec.get("expected_sections"):
        return _metric(METRIC_NEEDS_FUTURE, "golden_spec")
    return _metric(METRIC_NOT_AVAILABLE, "golden_spec")


def _derive_figure_handling(golden_spec: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, str]:
    expects_figures = bool(golden_spec.get("expected_figures_or_diagrams"))
    cov = artifacts.get("source_coverage_report")
    # Source coverage exposes a closed visual-candidate-page counter, but it
    # cannot be matched to specific expected figure ids without inspecting the
    # guide / images, so figure-id-level handling is deferred.
    if expects_figures:
        if _present(cov) and cov["counts"].get("visual_candidate_pages") is not None:
            return _metric(METRIC_NEEDS_FUTURE, "source_coverage_report")
        return _metric(METRIC_NEEDS_FUTURE, "golden_spec")
    return _metric(METRIC_NOT_AVAILABLE, "golden_spec")


def _derive_artifact_existence(artifacts: dict[str, Any]) -> dict[str, str]:
    required_present = 0
    required_bad = 0
    for name in _REQUIRED_ARTIFACTS:
        entry = artifacts.get(name)
        if _present(entry):
            required_present += 1
        else:
            required_bad += 1
    if required_present == len(_REQUIRED_ARTIFACTS):
        return _metric(METRIC_PASS, "artifact_collector")
    if required_present == 0:
        return _metric(METRIC_FAIL, "artifact_collector")
    return _metric(METRIC_WARNING, "artifact_collector")


# =============================================================================
# Record assembly
# =============================================================================


def build_guide_quality_baseline_record(
    golden_spec: Any, artifacts: Any, *, run_metadata: Any = None
) -> dict[str, Any]:
    """Build a closed aggregate baseline record from a golden spec + artifacts.

    Never embeds raw artifact bodies, paths, filenames, or content — only closed
    statuses, counts, and percentages derived from whitelisted scalars.
    """
    spec = normalize_guide_quality_baseline_golden_spec(golden_spec)
    arts = artifacts if isinstance(artifacts, dict) else {}

    warnings: list[str] = []
    metrics: dict[str, dict[str, str]] = {}

    metrics["reasoning_leak_status"] = _derive_reasoning_leak(arts)
    numeric_metric, numeric_warnings = _derive_numeric_math(arts, spec)
    metrics["numeric_math_status"] = numeric_metric
    warnings.extend(numeric_warnings)
    metrics["guide_quality_qa_gate_status"] = _derive_qa_gate(arts)
    metrics["source_coverage_status"] = _derive_source_coverage(arts)
    metrics["structure_contract_status"] = _derive_structure_contract(arts)
    metrics["reference_relative_completeness_status"] = _derive_reference_relative_completeness(spec)
    metrics["figure_handling_status"] = _derive_figure_handling(spec, arts)
    metrics["artifact_existence_status"] = _derive_artifact_existence(arts)

    artifact_inputs = _artifact_inputs_view(arts)
    summary = _summary_counts(metrics, arts)
    status = _roll_up_overall_status(spec, metrics, arts)

    if not spec.get("valid"):
        warnings.append("golden_spec_invalid")
    warnings.extend(spec.get("normalization_warnings", []))

    local_run = _resolve_local_run(run_metadata)

    record: dict[str, Any] = {
        "version": RECORD_VERSION,
        "kind": RECORD_KIND,
        "fixture_id": spec.get("fixture_id", "unknown_fixture"),
        "fixture_mode": spec.get("fixture_mode", "local_gitignored_source"),
        "source_material_committed": bool(spec.get("source_material_committed", False)),
        "generated_guide_committed": bool(spec.get("generated_guide_committed", False)),
        "status": status,
        "local_operator_run": local_run,
        "artifact_inputs": artifact_inputs,
        "metrics": {name: metrics[name] for name in _METRIC_FAMILIES},
        "summary": summary,
        "trend": {
            "status": TREND_NO_PREVIOUS,
            "improved_metric_count": 0,
            "regressed_metric_count": 0,
        },
        "warnings": sorted(set(warnings)),
    }
    return record


def _artifact_inputs_view(artifacts: dict[str, Any]) -> dict[str, str]:
    view: dict[str, str] = {}
    for logical in _LOGICAL_NAMES:
        entry = artifacts.get(logical)
        if not isinstance(entry, dict):
            view[logical] = PRESENCE_MISSING
            continue
        presence = entry.get("presence")
        view[logical] = presence if presence in _PRESENCE_TOKENS else PRESENCE_MISSING
    return view


def _summary_counts(metrics: dict[str, dict[str, str]], artifacts: dict[str, Any]) -> dict[str, int]:
    pass_count = warning_count = fail_count = 0
    not_available_count = needs_future_count = 0
    for name in _METRIC_FAMILIES:
        status = metrics[name]["status"]
        if status == METRIC_PASS:
            pass_count += 1
        elif status == METRIC_WARNING:
            warning_count += 1
        elif status == METRIC_FAIL:
            fail_count += 1
        elif status == METRIC_NOT_AVAILABLE:
            not_available_count += 1
        elif status == METRIC_NEEDS_FUTURE:
            needs_future_count += 1

    req_present = sum(1 for n in _REQUIRED_ARTIFACTS if _present(artifacts.get(n)))
    opt_present = sum(1 for n in _OPTIONAL_ARTIFACTS if _present(artifacts.get(n)))
    return {
        "pass_count": pass_count,
        "warning_count": warning_count,
        "fail_count": fail_count,
        "not_available_count": not_available_count,
        "needs_future_metric_count": needs_future_count,
        "required_artifact_present_count": req_present,
        "required_artifact_missing_count": len(_REQUIRED_ARTIFACTS) - req_present,
        "optional_artifact_present_count": opt_present,
        "optional_artifact_missing_count": len(_OPTIONAL_ARTIFACTS) - opt_present,
    }


def _roll_up_overall_status(
    golden_spec: dict[str, Any], metrics: dict[str, dict[str, str]], artifacts: dict[str, Any]
) -> str:
    if not golden_spec.get("valid"):
        return OVERALL_SKIPPED
    req_present = sum(1 for n in _REQUIRED_ARTIFACTS if _present(artifacts.get(n)))
    if req_present == 0:
        return OVERALL_SKIPPED
    statuses = [metrics[name]["status"] for name in _METRIC_FAMILIES]
    if METRIC_FAIL in statuses:
        return OVERALL_FAILED
    if req_present < len(_REQUIRED_ARTIFACTS):
        return OVERALL_PARTIAL
    if METRIC_WARNING in statuses:
        return OVERALL_WARNING
    return OVERALL_OK


def _resolve_local_run(run_metadata: Any) -> str:
    if isinstance(run_metadata, dict):
        token = run_metadata.get("local_operator_run")
        if token == RUN_CLOSED_SUMMARY_ONLY:
            return RUN_CLOSED_SUMMARY_ONLY
    return RUN_NOT_RUN


# =============================================================================
# Trend comparison
# =============================================================================


def compare_guide_quality_baseline_records(
    current_record: Any, previous_record: Any = None
) -> dict[str, Any]:
    """Compute a closed trend diff between two baseline records (statuses only)."""
    current_metrics = _metrics_of(current_record)
    if previous_record is None:
        return {
            "status": TREND_NO_PREVIOUS,
            "improved_metric_count": 0,
            "regressed_metric_count": 0,
            "unchanged_metric_count": len(current_metrics),
        }
    previous_metrics = _metrics_of(previous_record)

    improved = regressed = unchanged = 0
    for name in _METRIC_FAMILIES:
        cur = _METRIC_RANK.get(current_metrics.get(name, METRIC_NOT_AVAILABLE), 2)
        prev = _METRIC_RANK.get(previous_metrics.get(name, METRIC_NOT_AVAILABLE), 2)
        if cur > prev:
            improved += 1
        elif cur < prev:
            regressed += 1
        else:
            unchanged += 1

    if regressed > 0:
        status = TREND_REGRESSED
    elif improved > 0:
        status = TREND_IMPROVED
    else:
        status = TREND_UNCHANGED

    return {
        "status": status,
        "improved_metric_count": improved,
        "regressed_metric_count": regressed,
        "unchanged_metric_count": unchanged,
    }


def _metrics_of(record: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(record, dict):
        return out
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        return out
    for name, entry in metrics.items():
        if isinstance(entry, dict):
            status = entry.get("status")
            if isinstance(status, str):
                out[name] = status
    return out


# =============================================================================
# Serialization
# =============================================================================


def serialize_guide_quality_baseline_record(record: Any) -> str:
    """Deterministic JSON serialization (sorted keys, stable separators)."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
