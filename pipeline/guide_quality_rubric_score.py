"""Deterministic guide-quality rubric score v1 (Slice 105).

This module turns the already-sanitized guide-quality artifacts into a compact,
advisory scorecard. It is intentionally conservative: deterministic counts can be
scored, but semantic axes remain unknown/unsupported instead of pretending that a
shallow signal proves quality.

No-leak contract:
    * consumes only already-sanitized dicts passed by the caller;
    * copies no strings from inputs except closed status/check tokens used only for
      decisions;
    * emits only closed ids, statuses, reasons, confidence values, integer counts,
      booleans, None, and closed warnings;
    * never includes raw warnings, instructions, check text, matched phrases,
      guide/source/formula/table text, captions, refs, filenames, paths, URLs,
      provider payloads, argv, tokens, data URIs, base64, image bytes, or raw
      exception messages.

Pure stdlib-only and total: malformed input degrades to unknown axes and closed
warnings. The artifact is advisory-only; ``blocking`` is always False.
"""
from __future__ import annotations

from typing import Any

VERSION = 1
KIND = "guide_quality_rubric_score"

STATUS_COMPLETED = "completed"
STATUS_PARTIAL = "partial"
STATUS_SKIPPED = "skipped"
_TOP_STATUSES = frozenset({STATUS_COMPLETED, STATUS_PARTIAL, STATUS_SKIPPED})

AXIS_PASSED = "passed"
AXIS_WARNING = "warning"
AXIS_UNKNOWN = "unknown"
AXIS_NOT_APPLICABLE = "not_applicable"
_AXIS_STATUSES = frozenset({AXIS_PASSED, AXIS_WARNING, AXIS_UNKNOWN, AXIS_NOT_APPLICABLE})

CONF_DETERMINISTIC = "deterministic"
CONF_ADVISORY = "advisory"
CONF_UNSUPPORTED = "unsupported"
_CONFIDENCE_VALUES = frozenset({CONF_DETERMINISTIC, CONF_ADVISORY, CONF_UNSUPPORTED})

WARN_QA_GATE_MISSING = "qa_gate_missing"
WARN_CONTRACT_LINT_MISSING = "contract_lint_missing"
WARN_GUIDE_QUALITY_REPORT_V2_MISSING = "guide_quality_report_v2_missing"
WARN_SOURCE_COVERAGE_REPORT_MISSING = "source_coverage_report_missing"
WARN_MATH_VERIFICATION_MISSING = "math_verification_missing"
WARN_VISUAL_TABLE_ARTIFACTS_MISSING = "visual_table_artifacts_missing"
WARN_SEMANTIC_UNSUPPORTED = "semantic_axis_not_deterministically_measured"
WARN_MAX_ITEMS_REACHED = "max_items_reached"
WARN_MALFORMED_INPUT_DEGRADED = "malformed_input_degraded"

WARNING_ORDER = [
    WARN_QA_GATE_MISSING,
    WARN_CONTRACT_LINT_MISSING,
    WARN_GUIDE_QUALITY_REPORT_V2_MISSING,
    WARN_SOURCE_COVERAGE_REPORT_MISSING,
    WARN_MATH_VERIFICATION_MISSING,
    WARN_VISUAL_TABLE_ARTIFACTS_MISSING,
    WARN_SEMANTIC_UNSUPPORTED,
    WARN_MAX_ITEMS_REACHED,
    WARN_MALFORMED_INPUT_DEGRADED,
]

AXIS_SPECS = (
    ("rubric_axis_0001", "reasoning_hygiene"),
    ("rubric_axis_0002", "required_structure"),
    ("rubric_axis_0003", "exam_focus"),
    ("rubric_axis_0004", "reference_tables"),
    ("rubric_axis_0005", "math_verification"),
    ("rubric_axis_0006", "source_coverage"),
    ("rubric_axis_0007", "coverage_signal_alignment"),
    ("rubric_axis_0008", "visual_table_honesty"),
    ("rubric_axis_0009", "beginner_scaffolding"),
    ("rubric_axis_0010", "worked_example_completeness"),
)
_AXIS_KINDS = frozenset(kind for _axis_id, kind in AXIS_SPECS)

_CHECK_STATUSES = frozenset({"passed", "warning", "unknown", "not_applicable"})
_SKIPPED = "skipped"
_INCOMPLETE_COVERAGE_STATUSES = frozenset({"partial", "unreadable"})
_REPORT_VISUAL_TABLE_WARNINGS = frozenset(
    {
        "visual_signal_missing",
        "table_signal_missing",
        "visual_plan_malformed",
        "table_manifest_malformed",
        "table_policy_malformed",
    }
)
_VISUAL_TABLE_COUNT_KEYS = (
    "missing_count",
    "missing_visual_count",
    "missing_table_count",
    "unreadable_count",
    "unreadable_visual_count",
    "unreadable_table_count",
    "unsafe_count",
    "unsafe_visual_count",
    "unsafe_table_count",
    "deferred_count",
    "deferred_visual_count",
    "deferred_table_count",
    "skipped_count",
    "rejected_count",
)
_MAX_ITEMS_CEILING = len(AXIS_SPECS)
_REASONS = frozenset(
    {
        "reasoning_signal_missing",
        "reasoning_leak_count_zero",
        "reasoning_leak_warning_signal",
        "reasoning_leak_severe_signal",
        "required_structure_not_comprehensive",
        "required_structure_signal_missing",
        "required_structure_complete",
        "required_structure_partial",
        "required_structure_absent",
        "exam_focus_signal_missing",
        "exam_alert_count_positive",
        "exam_alert_signal_weak",
        "exam_focus_not_applicable",
        "reference_table_count_positive",
        "reference_table_signal_weak",
        "reference_tables_signal_missing",
        "reference_tables_not_applicable",
        "math_signal_missing",
        "math_checked_zero_mismatch",
        "math_no_checked_claims",
        "math_mismatch_present",
        "source_coverage_signal_missing",
        "source_coverage_clean",
        "source_coverage_warning_signal",
        "coverage_report_signal_missing",
        "coverage_report_no_warnings",
        "coverage_report_warnings_present",
        "visual_table_signal_missing",
        "visual_table_no_warnings",
        "visual_table_warning_signal",
        "semantic_axis_not_deterministically_measured",
    }
)


def build_guide_quality_rubric_score(
    *,
    qa_gate: dict | None = None,
    contract_lint: dict | None = None,
    guide_quality_report_v2: dict | None = None,
    source_coverage_report: dict | None = None,
    math_verification: dict | None = None,
    validation: dict | None = None,
    visual_inclusion_plan: dict | None = None,
    table_candidates_manifest: dict | None = None,
    table_reconstruction_policy: dict | None = None,
    comprehensive: bool | None = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Build a sanitized advisory rubric score from existing artifacts.

    ``validation`` is accepted for wiring symmetry but is not used for scoring in
    v1; math scoring reads only ``math_verification`` summary counts. The function
    is total and never raises.
    """
    try:
        return _build(
            qa_gate=qa_gate,
            contract_lint=contract_lint,
            guide_quality_report_v2=guide_quality_report_v2,
            source_coverage_report=source_coverage_report,
            math_verification=math_verification,
            validation=validation,
            visual_inclusion_plan=visual_inclusion_plan,
            table_candidates_manifest=table_candidates_manifest,
            table_reconstruction_policy=table_reconstruction_policy,
            comprehensive=comprehensive,
            max_items=max_items,
        )
    except Exception:
        return _finalize(STATUS_SKIPPED, [], {WARN_MALFORMED_INPUT_DEGRADED})


def _build(
    *,
    qa_gate: Any,
    contract_lint: Any,
    guide_quality_report_v2: Any,
    source_coverage_report: Any,
    math_verification: Any,
    validation: Any,
    visual_inclusion_plan: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    comprehensive: Any,
    max_items: Any,
) -> dict[str, Any]:
    del validation  # v1 intentionally does not score from render validation.

    warnings: set[str] = set()
    comp = _comprehensive_signal(comprehensive, qa_gate, contract_lint, warnings)

    axes = [
        _reasoning_hygiene_axis(contract_lint, qa_gate, warnings),
        _required_structure_axis(contract_lint, qa_gate, comp, warnings),
        _exam_focus_axis(contract_lint, comp, warnings),
        _reference_tables_axis(
            contract_lint,
            table_candidates_manifest,
            table_reconstruction_policy,
            comp,
            warnings,
        ),
        _math_verification_axis(math_verification, warnings),
        _source_coverage_axis(source_coverage_report, qa_gate, warnings),
        _coverage_signal_alignment_axis(guide_quality_report_v2, warnings),
        _visual_table_honesty_axis(
            guide_quality_report_v2,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            warnings,
        ),
        _semantic_axis("rubric_axis_0009", "beginner_scaffolding", warnings),
        _semantic_axis("rubric_axis_0010", "worked_example_completeness", warnings),
    ]

    status = STATUS_COMPLETED
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        cap = max(0, min(max_items, _MAX_ITEMS_CEILING))
        if cap < len(axes):
            axes = axes[:cap]
            warnings.add(WARN_MAX_ITEMS_REACHED)
            status = STATUS_PARTIAL

    if status != STATUS_PARTIAL and _known_axis_count(axes) == 0:
        status = STATUS_SKIPPED

    return _finalize(status, axes, warnings)


def _reasoning_hygiene_axis(
    contract_lint: Any, qa_gate: Any, warnings: set[str]
) -> dict[str, Any]:
    summary = _usable_summary(contract_lint, warnings)
    qa_check = _find_check(qa_gate, "reasoning_leak", warnings)

    if summary is None and qa_check is None:
        warnings.add(WARN_CONTRACT_LINT_MISSING)
        warnings.add(WARN_QA_GATE_MISSING)
        return _axis(
            "rubric_axis_0001",
            "reasoning_hygiene",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="reasoning_signal_missing",
            signals={"warning_count": 0},
        )

    leak_count = _safe_count(summary.get("reasoning_leak_count"), default=None) if summary else None
    if leak_count is None and qa_check is not None:
        leak_count = _safe_count(qa_check.get("observed_count"), default=None)

    qa_status = _check_status(qa_check)
    if leak_count == 0 or qa_status == "passed":
        return _axis(
            "rubric_axis_0001",
            "reasoning_hygiene",
            status=AXIS_PASSED,
            score=2,
            confidence=CONF_DETERMINISTIC,
            reason="reasoning_leak_count_zero",
            signals={"warning_count": 0},
        )
    if leak_count is not None and leak_count > 1:
        return _axis(
            "rubric_axis_0001",
            "reasoning_hygiene",
            status=AXIS_WARNING,
            score=0,
            confidence=CONF_DETERMINISTIC,
            reason="reasoning_leak_severe_signal",
            signals={"warning_count": leak_count},
        )
    return _axis(
        "rubric_axis_0001",
        "reasoning_hygiene",
        status=AXIS_WARNING,
        score=1,
        confidence=CONF_ADVISORY,
        reason="reasoning_leak_warning_signal",
        signals={"warning_count": _safe_count(leak_count)},
    )


def _required_structure_axis(
    contract_lint: Any, qa_gate: Any, comprehensive: bool | None, warnings: set[str]
) -> dict[str, Any]:
    if comprehensive is False:
        return _axis(
            "rubric_axis_0002",
            "required_structure",
            status=AXIS_NOT_APPLICABLE,
            score=None,
            confidence=CONF_ADVISORY,
            reason="required_structure_not_comprehensive",
            signals={"required_count": 0, "present_count": 0},
        )

    summary = _usable_summary(contract_lint, warnings)
    qa_check = _find_check(qa_gate, "required_structure", warnings)
    if summary is None and qa_check is None:
        warnings.add(WARN_CONTRACT_LINT_MISSING)
        warnings.add(WARN_QA_GATE_MISSING)
        return _axis(
            "rubric_axis_0002",
            "required_structure",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="required_structure_signal_missing",
            signals={"required_count": 0, "present_count": 0},
        )

    required_count = _safe_count(summary.get("required_section_count"), default=None) if summary else None
    present_count = _safe_count(summary.get("required_section_present_count"), default=None) if summary else None
    if required_count is None and qa_check is not None:
        required_count = _safe_count(qa_check.get("expected_count"), default=None)
        present_count = _safe_count(qa_check.get("observed_count"), default=None)

    if required_count is None or required_count <= 0:
        return _axis(
            "rubric_axis_0002",
            "required_structure",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="required_structure_signal_missing",
            signals={"required_count": 0, "present_count": _safe_count(present_count)},
        )

    present = _safe_count(present_count)
    if present >= required_count:
        status, score, reason = AXIS_PASSED, 2, "required_structure_complete"
    elif present > 0:
        status, score, reason = AXIS_WARNING, 1, "required_structure_partial"
    else:
        status, score, reason = AXIS_WARNING, 0, "required_structure_absent"
    return _axis(
        "rubric_axis_0002",
        "required_structure",
        status=status,
        score=score,
        confidence=CONF_DETERMINISTIC,
        reason=reason,
        signals={"required_count": required_count, "present_count": present},
    )


def _exam_focus_axis(
    contract_lint: Any, comprehensive: bool | None, warnings: set[str]
) -> dict[str, Any]:
    summary = _usable_summary(contract_lint, warnings)
    if summary is None:
        warnings.add(WARN_CONTRACT_LINT_MISSING)
        return _axis(
            "rubric_axis_0003",
            "exam_focus",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="exam_focus_signal_missing",
            signals={"exam_alert_count": 0},
        )

    alert_count = _safe_count(summary.get("exam_alert_count"))
    if alert_count > 0:
        return _axis(
            "rubric_axis_0003",
            "exam_focus",
            status=AXIS_PASSED,
            score=2,
            confidence=CONF_DETERMINISTIC,
            reason="exam_alert_count_positive",
            signals={"exam_alert_count": alert_count},
        )
    if comprehensive is False:
        return _axis(
            "rubric_axis_0003",
            "exam_focus",
            status=AXIS_NOT_APPLICABLE,
            score=None,
            confidence=CONF_ADVISORY,
            reason="exam_focus_not_applicable",
            signals={"exam_alert_count": 0},
        )
    return _axis(
        "rubric_axis_0003",
        "exam_focus",
        status=AXIS_WARNING,
        score=1,
        confidence=CONF_ADVISORY,
        reason="exam_alert_signal_weak",
        signals={"exam_alert_count": 0},
    )


def _reference_tables_axis(
    contract_lint: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    comprehensive: bool | None,
    warnings: set[str],
) -> dict[str, Any]:
    summary = _usable_summary(contract_lint, warnings)
    table_count = _safe_count(summary.get("table_count"), default=None) if summary else None
    table_signal_count = _table_signal_count(table_candidates_manifest, table_reconstruction_policy, warnings)

    if table_count is not None and table_count > 0:
        return _axis(
            "rubric_axis_0004",
            "reference_tables",
            status=AXIS_PASSED,
            score=2,
            confidence=CONF_DETERMINISTIC,
            reason="reference_table_count_positive",
            signals={"table_count": table_count, "table_signal_count": table_signal_count},
        )
    if table_signal_count > 0:
        return _axis(
            "rubric_axis_0004",
            "reference_tables",
            status=AXIS_WARNING,
            score=1,
            confidence=CONF_ADVISORY,
            reason="reference_table_signal_weak",
            signals={"table_count": _safe_count(table_count), "table_signal_count": table_signal_count},
        )
    if summary is None:
        warnings.add(WARN_CONTRACT_LINT_MISSING)
        return _axis(
            "rubric_axis_0004",
            "reference_tables",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="reference_tables_signal_missing",
            signals={"table_count": 0, "table_signal_count": 0},
        )
    if comprehensive is False:
        return _axis(
            "rubric_axis_0004",
            "reference_tables",
            status=AXIS_NOT_APPLICABLE,
            score=None,
            confidence=CONF_ADVISORY,
            reason="reference_tables_not_applicable",
            signals={"table_count": 0, "table_signal_count": 0},
        )
    return _axis(
        "rubric_axis_0004",
        "reference_tables",
        status=AXIS_WARNING,
        score=1,
        confidence=CONF_ADVISORY,
        reason="reference_table_signal_weak",
        signals={"table_count": 0, "table_signal_count": 0},
    )


def _math_verification_axis(math_verification: Any, warnings: set[str]) -> dict[str, Any]:
    summary = _math_summary(math_verification, warnings)
    if summary is None:
        warnings.add(WARN_MATH_VERIFICATION_MISSING)
        return _axis(
            "rubric_axis_0005",
            "math_verification",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="math_signal_missing",
            signals={"checked_count": 0, "mismatch_count": 0},
        )

    checked = _safe_count(summary.get("total"), default=None)
    if checked is None:
        checked = _safe_count(summary.get("checked_count"), default=None)
    if checked is None:
        checked = _safe_count(summary.get("checked"), default=None)
    mismatch = _safe_count(summary.get("mismatch"), default=None)
    if mismatch is None:
        mismatch = _safe_count(summary.get("mismatch_count"), default=None)

    if checked is None or mismatch is None:
        warnings.add(WARN_MALFORMED_INPUT_DEGRADED)
        return _axis(
            "rubric_axis_0005",
            "math_verification",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="math_signal_missing",
            signals={"checked_count": 0, "mismatch_count": 0},
        )
    if mismatch > 0:
        return _axis(
            "rubric_axis_0005",
            "math_verification",
            status=AXIS_WARNING,
            score=0,
            confidence=CONF_DETERMINISTIC,
            reason="math_mismatch_present",
            signals={"checked_count": checked, "mismatch_count": mismatch},
        )
    if checked <= 0:
        return _axis(
            "rubric_axis_0005",
            "math_verification",
            status=AXIS_NOT_APPLICABLE,
            score=1,
            confidence=CONF_ADVISORY,
            reason="math_no_checked_claims",
            signals={"checked_count": 0, "mismatch_count": 0},
        )
    return _axis(
        "rubric_axis_0005",
        "math_verification",
        status=AXIS_PASSED,
        score=2,
        confidence=CONF_DETERMINISTIC,
        reason="math_checked_zero_mismatch",
        signals={"checked_count": checked, "mismatch_count": 0},
    )


def _source_coverage_axis(
    source_coverage_report: Any, qa_gate: Any, warnings: set[str]
) -> dict[str, Any]:
    if _is_usable_artifact(source_coverage_report, warnings):
        summary = source_coverage_report.get("summary")
        summary = summary if isinstance(summary, dict) else {}
        top_status = _token(source_coverage_report.get("status"))
        unreadable_pages = _safe_count(summary.get("empty_or_unreadable_pages"))
        unreadable_sources = _safe_count(summary.get("unreadable_source_count"))
        source_gap_count = _safe_count(summary.get("source_gap_count")) + _safe_count(
            summary.get("missing_source_count")
        )
        has_gap = (
            top_status in _INCOMPLETE_COVERAGE_STATUSES
            or unreadable_pages > 0
            or unreadable_sources > 0
            or source_gap_count > 0
        )
        return _axis(
            "rubric_axis_0006",
            "source_coverage",
            status=AXIS_WARNING if has_gap else AXIS_PASSED,
            score=1 if has_gap else 2,
            confidence=CONF_DETERMINISTIC,
            reason="source_coverage_warning_signal" if has_gap else "source_coverage_clean",
            signals={
                "unreadable_page_count": unreadable_pages,
                "unreadable_source_count": unreadable_sources,
                "source_gap_count": source_gap_count,
            },
        )

    qa_check = _find_check(qa_gate, "source_coverage", warnings)
    qa_status = _check_status(qa_check)
    if qa_status == "passed":
        return _axis(
            "rubric_axis_0006",
            "source_coverage",
            status=AXIS_PASSED,
            score=2,
            confidence=CONF_ADVISORY,
            reason="source_coverage_clean",
            signals={"unreadable_page_count": 0, "unreadable_source_count": 0, "source_gap_count": 0},
        )
    if qa_status == "warning":
        return _axis(
            "rubric_axis_0006",
            "source_coverage",
            status=AXIS_WARNING,
            score=1,
            confidence=CONF_ADVISORY,
            reason="source_coverage_warning_signal",
            signals={"unreadable_page_count": 0, "unreadable_source_count": 0, "source_gap_count": 0},
        )

    warnings.add(WARN_SOURCE_COVERAGE_REPORT_MISSING)
    return _axis(
        "rubric_axis_0006",
        "source_coverage",
        status=AXIS_UNKNOWN,
        score=None,
        confidence=CONF_UNSUPPORTED,
        reason="source_coverage_signal_missing",
        signals={"unreadable_page_count": 0, "unreadable_source_count": 0, "source_gap_count": 0},
    )


def _coverage_signal_alignment_axis(
    guide_quality_report_v2: Any, warnings: set[str]
) -> dict[str, Any]:
    summary = _usable_summary(guide_quality_report_v2, warnings)
    if summary is None:
        warnings.add(WARN_GUIDE_QUALITY_REPORT_V2_MISSING)
        return _axis(
            "rubric_axis_0007",
            "coverage_signal_alignment",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="coverage_report_signal_missing",
            signals={"warning_count": 0},
        )
    warning_count = _safe_count(summary.get("warning_count"))
    return _axis(
        "rubric_axis_0007",
        "coverage_signal_alignment",
        status=AXIS_WARNING if warning_count > 0 else AXIS_PASSED,
        score=1 if warning_count > 0 else 2,
        confidence=CONF_DETERMINISTIC,
        reason="coverage_report_warnings_present" if warning_count > 0 else "coverage_report_no_warnings",
        signals={"warning_count": warning_count},
    )


def _visual_table_honesty_axis(
    guide_quality_report_v2: Any,
    visual_inclusion_plan: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    warnings: set[str],
) -> dict[str, Any]:
    artifact_present = any(
        _is_usable_artifact(item, warnings)
        for item in (visual_inclusion_plan, table_candidates_manifest, table_reconstruction_policy)
    )
    report_present = _is_usable_artifact(guide_quality_report_v2, warnings)
    if not artifact_present:
        warnings.add(WARN_VISUAL_TABLE_ARTIFACTS_MISSING)
        return _axis(
            "rubric_axis_0008",
            "visual_table_honesty",
            status=AXIS_UNKNOWN,
            score=None,
            confidence=CONF_UNSUPPORTED,
            reason="visual_table_signal_missing",
            signals={"warning_count": 0, "planned_visual_count": 0, "table_signal_count": 0},
        )

    planned_visual_count = _artifact_count(visual_inclusion_plan, "planned_count", "items", warnings)
    table_signal_count = _table_signal_count(table_candidates_manifest, table_reconstruction_policy, warnings)
    report_warning_count = _report_visual_table_warning_count(guide_quality_report_v2)
    artifact_warning_count = (
        _closed_summary_count(visual_inclusion_plan, _VISUAL_TABLE_COUNT_KEYS)
        + _closed_summary_count(table_candidates_manifest, _VISUAL_TABLE_COUNT_KEYS)
        + _closed_summary_count(table_reconstruction_policy, _VISUAL_TABLE_COUNT_KEYS)
    )
    warning_count = report_warning_count + artifact_warning_count
    if not report_present:
        warning_count += 1

    return _axis(
        "rubric_axis_0008",
        "visual_table_honesty",
        status=AXIS_WARNING if warning_count > 0 else AXIS_PASSED,
        score=1 if warning_count > 0 else 2,
        confidence=CONF_ADVISORY,
        reason="visual_table_warning_signal" if warning_count > 0 else "visual_table_no_warnings",
        signals={
            "warning_count": warning_count,
            "planned_visual_count": planned_visual_count,
            "table_signal_count": table_signal_count,
        },
    )


def _semantic_axis(axis_id: str, kind: str, warnings: set[str]) -> dict[str, Any]:
    warnings.add(WARN_SEMANTIC_UNSUPPORTED)
    return _axis(
        axis_id,
        kind,
        status=AXIS_UNKNOWN,
        score=None,
        confidence=CONF_UNSUPPORTED,
        reason="semantic_axis_not_deterministically_measured",
        signals={},
    )


def _axis(
    axis_id: str,
    kind: str,
    *,
    status: str,
    score: int | None,
    confidence: str,
    reason: str,
    signals: dict[str, Any],
) -> dict[str, Any]:
    safe_score: int | None
    if score in (0, 1, 2):
        safe_score = score
    else:
        safe_score = None
    return {
        "axis_id": axis_id if any(axis_id == spec_id for spec_id, _kind in AXIS_SPECS) else "rubric_axis_0001",
        "kind": kind if kind in _AXIS_KINDS else "reasoning_hygiene",
        "status": status if status in _AXIS_STATUSES else AXIS_UNKNOWN,
        "score": safe_score,
        "max_score": 2 if safe_score is not None else None,
        "confidence": confidence if confidence in _CONFIDENCE_VALUES else CONF_UNSUPPORTED,
        "reason": reason if reason in _REASONS else "semantic_axis_not_deterministically_measured",
        "signals": _safe_signals(signals),
    }


def _finalize(status: str, axes: list[dict[str, Any]], warnings: set[str]) -> dict[str, Any]:
    score_total = sum(axis["score"] for axis in axes if isinstance(axis.get("score"), int))
    score_possible = sum(axis["max_score"] for axis in axes if isinstance(axis.get("max_score"), int))
    known_axis_count = _known_axis_count(axes)
    unknown_axis_count = sum(1 for axis in axes if axis.get("status") == AXIS_UNKNOWN)
    warning_axis_count = sum(1 for axis in axes if axis.get("status") == AXIS_WARNING)
    safe_status = status if status in _TOP_STATUSES else STATUS_SKIPPED
    return {
        "version": VERSION,
        "kind": KIND,
        "status": safe_status,
        "blocking": False,
        "summary": {
            "score_total": score_total,
            "score_possible": score_possible,
            "known_axis_count": known_axis_count,
            "unknown_axis_count": unknown_axis_count,
            "warning_axis_count": warning_axis_count,
            "rubric_axis_count": len(axes),
        },
        "axes": axes,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _known_axis_count(axes: list[dict[str, Any]]) -> int:
    return sum(1 for axis in axes if isinstance(axis.get("score"), int))


def _safe_signals(signals: Any) -> dict[str, Any]:
    if not isinstance(signals, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in signals.items():
        if not isinstance(key, str) or not _safe_signal_key(key):
            continue
        if isinstance(value, bool):
            safe[key] = bool(value)
        else:
            safe[key] = _safe_count(value)
    return safe


def _safe_signal_key(key: str) -> bool:
    if not key or len(key) > 48:
        return False
    return all(ch.islower() or ch.isdigit() or ch == "_" for ch in key)


def _comprehensive_signal(
    explicit: Any, qa_gate: Any, contract_lint: Any, warnings: set[str]
) -> bool | None:
    if isinstance(explicit, bool):
        return explicit
    for artifact in (contract_lint, qa_gate):
        summary = _usable_summary(artifact, warnings)
        if summary is not None and isinstance(summary.get("comprehensive"), bool):
            return bool(summary.get("comprehensive"))
    return None


def _usable_summary(artifact: Any, warnings: set[str]) -> dict[str, Any] | None:
    if not _is_usable_artifact(artifact, warnings):
        return None
    summary = artifact.get("summary")
    if not isinstance(summary, dict):
        warnings.add(WARN_MALFORMED_INPUT_DEGRADED)
        return None
    return summary


def _math_summary(math_verification: Any, warnings: set[str]) -> dict[str, Any] | None:
    if not _is_usable_artifact(math_verification, warnings):
        return None
    report = math_verification.get("report")
    if not isinstance(report, dict):
        warnings.add(WARN_MALFORMED_INPUT_DEGRADED)
        return None
    summary = report.get("summary")
    if not isinstance(summary, dict):
        warnings.add(WARN_MALFORMED_INPUT_DEGRADED)
        return None
    return summary


def _is_usable_artifact(artifact: Any, warnings: set[str]) -> bool:
    if artifact is None:
        return False
    if not isinstance(artifact, dict):
        warnings.add(WARN_MALFORMED_INPUT_DEGRADED)
        return False
    if _token(artifact.get("status")) == _SKIPPED:
        return False
    return True


def _find_check(artifact: Any, kind: str, warnings: set[str]) -> dict[str, Any] | None:
    if not _is_usable_artifact(artifact, warnings):
        return None
    checks = artifact.get("checks")
    if not isinstance(checks, list):
        return None
    for item in checks:
        if not isinstance(item, dict):
            warnings.add(WARN_MALFORMED_INPUT_DEGRADED)
            continue
        if _token(item.get("kind")) == kind:
            return item
    return None


def _check_status(check: Any) -> str:
    if not isinstance(check, dict):
        return ""
    token = _token(check.get("status"))
    return token if token in _CHECK_STATUSES else ""


def _table_signal_count(
    table_candidates_manifest: Any, table_reconstruction_policy: Any, warnings: set[str]
) -> int:
    return _artifact_count(
        table_candidates_manifest, "table_like_candidate_count", "candidates", warnings
    ) + _artifact_count(table_reconstruction_policy, "policy_item_count", "items", warnings)


def _artifact_count(
    artifact: Any, summary_key: str, list_key: str, warnings: set[str]
) -> int:
    if artifact is None:
        return 0
    if not isinstance(artifact, dict):
        warnings.add(WARN_MALFORMED_INPUT_DEGRADED)
        return 0
    if _token(artifact.get("status")) == _SKIPPED:
        return 0
    summary = artifact.get("summary")
    if isinstance(summary, dict):
        count = _safe_count(summary.get(summary_key), default=None)
        if count is not None:
            return count
    items = artifact.get(list_key)
    if isinstance(items, list):
        return len(items)
    return 0


def _report_visual_table_warning_count(report: Any) -> int:
    if not isinstance(report, dict):
        return 0
    raw_warnings = report.get("warnings")
    if not isinstance(raw_warnings, list):
        return 0
    count = 0
    for value in raw_warnings:
        token = _token(value)
        if token in _REPORT_VISUAL_TABLE_WARNINGS:
            count += 1
    return count


def _closed_summary_count(artifact: Any, keys: tuple[str, ...]) -> int:
    if not isinstance(artifact, dict):
        return 0
    summary = artifact.get("summary")
    if not isinstance(summary, dict):
        return 0
    return sum(_safe_count(summary.get(key)) for key in keys)


def _safe_count(value: Any, default: int | None = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    if value < 0:
        return default
    return value


def _token(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""
