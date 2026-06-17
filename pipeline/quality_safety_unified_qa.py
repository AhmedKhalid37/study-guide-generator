"""Quality Safety unified deterministic QA report v1 (Slice 114).

This module aggregates the offline deterministic Quality Safety reports from
Slices 108-113 into one safe in-memory report. It deliberately does not compute
judge scores, write artifacts, read source documents, call providers, repair
content, or tune prompts.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.quality_safety_canonical_matcher import build_quality_safety_canonical_match_report
from pipeline.quality_safety_eval_harness import (
    load_quality_safety_fixture_spec,
    run_quality_safety_layer1_checks,
)
from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet
from pipeline.quality_safety_leak_scanner import build_quality_safety_leak_report
from pipeline.quality_safety_recompute_verifier import (
    build_quality_safety_recompute_report,
    verify_quality_safety_fact_sheet,
)

VERSION = 1
KIND = "quality_safety_unified_qa"

REPORT_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})
COMPONENT_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial", "unknown"})
COMPONENTS = ("layer1", "recompute", "canonical", "leak")

WARNING_ORDER = (
    "malformed_input_degraded",
    "component_missing",
    "component_malformed",
    "layer1_warning",
    "numeric_unverified",
    "canonical_unmatched",
    "leak_warning",
    "coverage_warning",
    "mock_question_warning",
    "unknown_verification_context",
    "max_items_reached",
)

SAFE_WARNING_TOKENS = frozenset(WARNING_ORDER)
SAFE_VERIFICATION_STATUSES = frozenset(
    {
        "verified_recompute",
        "failed_recompute",
        "verified_canonical",
        "failed_canonical",
        "unverified",
        "not_applicable",
        "unknown",
    }
)

LAYER1_CHECK_IDS = frozenset(
    {
        "leaked_reasoning",
        "numeric_correctness",
        "worked_answer_completeness",
        "coverage",
        "mock_question_count",
    }
)
RECOMPUTE_CHECK_IDS = frozenset(
    {
        "weighted_gini",
        "total_error",
        "amount_of_say",
        "softmax",
        "cross_entropy",
        "forward_pass",
        "numeric_fact_not_recomputable",
        "non_numeric_fact_not_applicable",
    }
)
CANONICAL_CHECK_IDS = frozenset(
    {
        "canonical_fixture_match",
        "canonical_fixture_mismatch",
        "canonical_fixture_missing",
        "canonical_fixture_skipped_by_recompute_verified",
        "canonical_fixture_skipped_by_recompute_failed",
        "canonical_fixture_not_applicable",
    }
)
LEAK_CHECK_IDS = frozenset({"quality_safety_leak_scan"})
SAFE_CHECK_IDS = LAYER1_CHECK_IDS | RECOMPUTE_CHECK_IDS | CANONICAL_CHECK_IDS | LEAK_CHECK_IDS | {"unknown_check"}

_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_UNSAFE_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|/var/|\\\\|[A-Za-z]:\\|\.\./|/\.\.|"
    r"authorization|bearer|api[_-]?key|token|secret|data:|base64|provider payload|"
    r"ocr|caption|table text|uploaded[_ -]?quality|quality[_ -]?spec|evidence quote|"
    r"source text|raw text|guide snippet|source snippet|private|\.pdf|\.docx|\.zip|"
    r"\.png|\.jpg|\.jpeg|\.webp|\.socket|\.sock)",
    re.IGNORECASE,
)
_BASE64ISH_RE = re.compile(r"^[A-Za-z0-9+/]{80,}={0,2}$")

_SUMMARY_KEYS = (
    "blocking_failure_count",
    "warning_count",
    "layer1_blocking_failure_count",
    "numeric_blocking_failure_count",
    "leak_blocking_failure_count",
    "coverage_warning_count",
    "mock_question_warning_count",
    "verified_recompute_count",
    "verified_canonical_count",
    "failed_recompute_count",
    "failed_canonical_count",
    "unverified_fact_count",
    "unknown_context_leak_count",
    "deterministic_axis_count",
)


def build_quality_safety_unified_qa_report(
    *,
    candidate_markdown: Any = None,
    fixture_spec: Any = None,
    fact_sheet: Any = None,
    layer1_report: Any = None,
    recompute_report: Any = None,
    canonical_report: Any = None,
    leak_report: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Build a deterministic unified report; never raise."""
    try:
        fixture = load_quality_safety_fixture_spec(fixture_spec) if fixture_spec is not None else None
        sheet = normalize_quality_safety_fact_sheet(fact_sheet, max_items=max_items) if fact_sheet is not None else None
        if layer1_report is None and isinstance(candidate_markdown, str) and fixture is not None:
            layer1_report = run_quality_safety_layer1_checks(candidate_markdown, fixture, max_items=max_items)
        if recompute_report is None and sheet is not None:
            recompute_report = build_quality_safety_recompute_report(sheet, max_items=max_items)
        if leak_report is None and isinstance(candidate_markdown, str):
            leak_report = build_quality_safety_leak_report(
                candidate_markdown,
                fact_sheet=sheet,
                recompute_report=recompute_report,
                canonical_report=canonical_report,
                max_items=max_items,
            )
        return aggregate_quality_safety_reports(
            fixture_spec=fixture,
            layer1_report=layer1_report,
            recompute_report=recompute_report,
            canonical_report=canonical_report,
            leak_report=leak_report,
            max_items=max_items,
        )
    except Exception:
        return _empty_report(
            status="partial",
            warnings={"malformed_input_degraded", "component_malformed"},
        )


def aggregate_quality_safety_reports(
    *,
    fixture_spec: Any = None,
    layer1_report: Any = None,
    recompute_report: Any = None,
    canonical_report: Any = None,
    leak_report: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Aggregate caller-supplied child reports into the unified QA report."""
    try:
        return _aggregate(
            fixture_spec=fixture_spec,
            layer1_report=layer1_report,
            recompute_report=recompute_report,
            canonical_report=canonical_report,
            leak_report=leak_report,
            max_items=max_items,
        )
    except Exception:
        return _empty_report(
            status="partial",
            warnings={"malformed_input_degraded", "component_malformed"},
        )


def build_quality_safety_deterministic_axes(unified_report: Any) -> dict[str, int | None]:
    """Return only deterministic 0-5 axes for later judge injection."""
    if not isinstance(unified_report, dict):
        return _axes(None, None, None, None)
    summary = _safe_summary(unified_report.get("summary"))
    statuses = unified_report.get("component_statuses")
    statuses = statuses if isinstance(statuses, dict) else {}
    component_summaries = unified_report.get("component_summaries")
    component_summaries = component_summaries if isinstance(component_summaries, dict) else {}

    accuracy = _accuracy_axis(summary, statuses)
    coverage = _coverage_axis(component_summaries.get("layer1"))
    solved = _solved_problem_axis(unified_report, component_summaries.get("layer1"))
    clarity = _clarity_axis(unified_report, statuses)
    return _axes(accuracy, coverage, solved, clarity)


def run_quality_safety_unified_floor(
    *,
    candidate_markdown: Any,
    fixture_spec: Any = None,
    fact_sheet: Any = None,
    canonical_fixture: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Run the pure offline deterministic floor; never write artifacts."""
    try:
        fixture = load_quality_safety_fixture_spec(fixture_spec)
        layer1 = run_quality_safety_layer1_checks(candidate_markdown, fixture, max_items=max_items)
        sheet = normalize_quality_safety_fact_sheet(fact_sheet, max_items=max_items)
        verified = verify_quality_safety_fact_sheet(sheet, max_items=max_items)
        verified_sheet = verified.get("fact_sheet") if isinstance(verified, dict) else sheet
        recompute = verified.get("report") if isinstance(verified, dict) else None
        canonical = None
        if canonical_fixture is not None:
            canonical = build_quality_safety_canonical_match_report(
                verified_sheet,
                canonical_fixture,
                recompute_report=recompute,
                max_items=max_items,
            )
        leak = build_quality_safety_leak_report(
            candidate_markdown,
            fact_sheet=verified_sheet,
            recompute_report=recompute,
            canonical_report=canonical,
            max_items=max_items,
        )
        return aggregate_quality_safety_reports(
            fixture_spec=fixture,
            layer1_report=layer1,
            recompute_report=recompute,
            canonical_report=canonical,
            leak_report=leak,
            max_items=max_items,
        )
    except Exception:
        return _empty_report(
            status="partial",
            warnings={"malformed_input_degraded", "component_malformed"},
        )


def _aggregate(
    *,
    fixture_spec: Any,
    layer1_report: Any,
    recompute_report: Any,
    canonical_report: Any,
    leak_report: Any,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()
    component_statuses = {
        "layer1": _component_status(layer1_report, expected_kind="quality_safety_eval_layer1", warnings=warnings),
        "recompute": _component_status(recompute_report, expected_kind="quality_safety_recompute_report", warnings=warnings),
        "canonical": _canonical_component_status(canonical_report),
        "leak": _component_status(leak_report, expected_kind="quality_safety_leak_report", warnings=warnings),
    }
    if canonical_report is not None and component_statuses["canonical"] == "unknown":
        warnings.add("component_malformed")

    if layer1_report is None:
        warnings.add("component_missing")
    if recompute_report is None:
        warnings.add("component_missing")
    if leak_report is None:
        warnings.add("component_missing")
    if fixture_spec is not None:
        fixture = load_quality_safety_fixture_spec(fixture_spec)
        if fixture.get("warnings"):
            warnings.add("malformed_input_degraded")

    warnings.update(_mapped_component_warnings("layer1", layer1_report))
    warnings.update(_mapped_component_warnings("recompute", recompute_report))
    warnings.update(_mapped_component_warnings("canonical", canonical_report))
    warnings.update(_mapped_component_warnings("leak", leak_report))

    blocking_failures = []
    blocking_failures.extend(_layer1_blocking_failures(layer1_report))
    blocking_failures.extend(_numeric_blocking_failures("recompute", recompute_report))
    blocking_failures.extend(_numeric_blocking_failures("canonical", canonical_report))
    blocking_failures.extend(_leak_blocking_failures(leak_report))
    blocking_failures = _stable_failures(blocking_failures)

    cap = _resolve_max_items(max_items)
    truncated = False
    if len(blocking_failures) > cap:
        blocking_failures = blocking_failures[:cap]
        truncated = True
    ordered_warnings = _ordered_warnings(warnings)
    if len(ordered_warnings) > cap:
        ordered_warnings = ordered_warnings[:cap]
        truncated = True
    if truncated and "max_items_reached" not in ordered_warnings:
        ordered_warnings = _ordered_warnings(set(ordered_warnings) | {"max_items_reached"})

    component_summaries = _component_summaries(
        layer1_report=layer1_report,
        recompute_report=recompute_report,
        canonical_report=canonical_report,
        leak_report=leak_report,
    )
    summary = _build_summary(
        layer1_report=layer1_report,
        recompute_report=recompute_report,
        canonical_report=canonical_report,
        leak_report=leak_report,
        blocking_failures=blocking_failures,
        warnings=ordered_warnings,
    )
    provisional = {
        "summary": summary,
        "component_statuses": component_statuses,
        "component_summaries": component_summaries,
        "blocking_failures": blocking_failures,
        "warnings": ordered_warnings,
    }
    axes = build_quality_safety_deterministic_axes(provisional)
    summary["deterministic_axis_count"] = sum(1 for value in axes.values() if value is not None)

    status = _overall_status(
        blocking_failures=blocking_failures,
        warnings=ordered_warnings,
        component_statuses=component_statuses,
        truncated=truncated,
    )
    shippable = not blocking_failures and status in {"passed", "warning"}
    safety_floor_green = _safety_floor_green(
        shippable=shippable,
        warnings=ordered_warnings,
        summary=summary,
        component_statuses=component_statuses,
    )
    return {
        "version": VERSION,
        "kind": KIND,
        "status": status,
        "shippable": shippable,
        "safety_floor_green": safety_floor_green,
        "blocking": bool(blocking_failures),
        "summary": summary,
        "deterministic_axes_0_5": axes,
        "component_statuses": component_statuses,
        "component_summaries": component_summaries,
        "blocking_failures": blocking_failures,
        "warnings": ordered_warnings,
    }


def _empty_report(*, status: str, warnings: set[str]) -> dict[str, Any]:
    ordered = _ordered_warnings(warnings)
    summary = {key: 0 for key in _SUMMARY_KEYS}
    axes = _axes(None, None, None, None)
    return {
        "version": VERSION,
        "kind": KIND,
        "status": status if status in REPORT_STATUSES else "partial",
        "shippable": False,
        "safety_floor_green": False,
        "blocking": False,
        "summary": summary,
        "deterministic_axes_0_5": axes,
        "component_statuses": {component: "unknown" for component in COMPONENTS},
        "component_summaries": {},
        "blocking_failures": [],
        "warnings": ordered,
    }


def _component_status(report: Any, *, expected_kind: str, warnings: set[str]) -> str:
    if report is None:
        return "unknown"
    if not isinstance(report, dict) or report.get("kind") != expected_kind:
        warnings.add("component_malformed")
        return "unknown"
    status = report.get("status")
    return status if status in COMPONENT_STATUSES else "unknown"


def _canonical_component_status(report: Any) -> str:
    if report is None:
        return "skipped"
    if not isinstance(report, dict) or report.get("kind") != "quality_safety_canonical_match_report":
        return "unknown"
    status = report.get("status")
    return status if status in COMPONENT_STATUSES else "unknown"


def _component_summaries(
    *,
    layer1_report: Any,
    recompute_report: Any,
    canonical_report: Any,
    leak_report: Any,
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for component, report in (
        ("layer1", layer1_report),
        ("recompute", recompute_report),
        ("canonical", canonical_report),
        ("leak", leak_report),
    ):
        if not isinstance(report, dict):
            continue
        summary = _safe_summary(report.get("summary"))
        item = {
            "status": _safe_component_status(report.get("status")),
            "summary": summary,
            "warnings": _ordered_warnings(_mapped_component_warnings(component, report)),
        }
        if component == "layer1":
            checks_by_id = _layer1_checks_by_id(report)
            if checks_by_id:
                item["checks_by_id"] = checks_by_id
        summaries[component] = item
    return summaries


def _build_summary(
    *,
    layer1_report: Any,
    recompute_report: Any,
    canonical_report: Any,
    leak_report: Any,
    blocking_failures: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, int]:
    summary = {key: 0 for key in _SUMMARY_KEYS}
    summary["blocking_failure_count"] = len(blocking_failures)
    summary["warning_count"] = len(warnings)
    summary["layer1_blocking_failure_count"] = len(_layer1_blocking_failures(layer1_report))
    summary["numeric_blocking_failure_count"] = len(_numeric_blocking_failures("recompute", recompute_report)) + len(
        _numeric_blocking_failures("canonical", canonical_report)
    )
    if _layer1_has_failed_numeric(layer1_report):
        summary["numeric_blocking_failure_count"] += 1
    summary["leak_blocking_failure_count"] = len(_leak_blocking_failures(leak_report))
    if _has_warning(layer1_report, {"coverage_below_target", "expected_topic_missing"}):
        summary["coverage_warning_count"] = 1
    if _has_warning(layer1_report, {"mock_question_count_below_minimum"}):
        summary["mock_question_warning_count"] = 1
    recompute_summary = _safe_summary(recompute_report.get("summary") if isinstance(recompute_report, dict) else None)
    canonical_summary = _safe_summary(canonical_report.get("summary") if isinstance(canonical_report, dict) else None)
    leak_summary = _safe_summary(leak_report.get("summary") if isinstance(leak_report, dict) else None)
    summary["verified_recompute_count"] = _int(recompute_summary.get("verified_fact_count"))
    summary["verified_canonical_count"] = _int(canonical_summary.get("matched_fact_count"))
    summary["failed_recompute_count"] = _int(recompute_summary.get("failed_fact_count"))
    summary["failed_canonical_count"] = _int(canonical_summary.get("mismatch_count"))
    summary["unverified_fact_count"] = _int(recompute_summary.get("unverified_fact_count")) + _int(
        canonical_summary.get("unmatched_fact_count")
    )
    summary["unknown_context_leak_count"] = _int(leak_summary.get("unknown_context_leak_count"))
    return summary


def _layer1_blocking_failures(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    failures: list[dict[str, Any]] = []
    seen: set[str] = set()
    raw_failures = report.get("blocking_failures")
    if isinstance(raw_failures, list):
        for item in raw_failures:
            check_id = _safe_check_id(item, LAYER1_CHECK_IDS)
            if check_id not in seen:
                failures.append(_failure(component="layer1", check_id=check_id))
                seen.add(check_id)
    checks = report.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict):
                continue
            check_id = _safe_check_id(check.get("id"), LAYER1_CHECK_IDS)
            if check.get("status") == "failed" and check.get("blocking") is True and check_id not in seen:
                failures.append(_failure(component="layer1", check_id=check_id))
                seen.add(check_id)
    return failures


def _numeric_blocking_failures(component: str, report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    allowed = RECOMPUTE_CHECK_IDS if component == "recompute" else CANONICAL_CHECK_IDS
    verification = "failed_recompute" if component == "recompute" else "failed_canonical"
    failures: list[dict[str, Any]] = []
    raw_failures = report.get("blocking_failures")
    if isinstance(raw_failures, list):
        for item in raw_failures:
            if not isinstance(item, dict):
                continue
            failures.append(
                _failure(
                    component=component,
                    check_id=_safe_check_id(item.get("check_id"), allowed),
                    fact_ids=[item.get("fact_id")],
                    verification_status=verification,
                )
            )
    checks = report.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict) or check.get("status") != "failed":
                continue
            candidate = _failure(
                component=component,
                check_id=_safe_check_id(check.get("check_id"), allowed),
                fact_ids=[check.get("fact_id")],
                verification_status=verification,
            )
            if candidate not in failures:
                failures.append(candidate)
    return failures


def _leak_blocking_failures(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    failures: list[dict[str, Any]] = []
    raw_failures = report.get("blocking_failures")
    if isinstance(raw_failures, list):
        for item in raw_failures:
            if not isinstance(item, dict):
                continue
            failures.append(
                _failure(
                    component="leak",
                    check_id="quality_safety_leak_scan",
                    fact_ids=item.get("fact_ids"),
                    verification_status=_safe_verification_status(item.get("verification_status")),
                    warnings=item.get("warnings"),
                )
            )
    leaks = report.get("leaks")
    if isinstance(leaks, list):
        for leak in leaks:
            if not isinstance(leak, dict) or leak.get("severity") != "blocking":
                continue
            candidate = _failure(
                component="leak",
                check_id="quality_safety_leak_scan",
                fact_ids=leak.get("fact_ids"),
                verification_status=_safe_verification_status(leak.get("verification_status")),
                warnings=leak.get("warnings"),
            )
            if candidate not in failures:
                failures.append(candidate)
    return failures


def _failure(
    *,
    component: str,
    check_id: str,
    fact_ids: Any = None,
    verification_status: str = "unknown",
    warnings: Any = None,
) -> dict[str, Any]:
    return {
        "component": component if component in COMPONENTS else "layer1",
        "check_id": check_id if check_id in SAFE_CHECK_IDS else "unknown_check",
        "status": "failed",
        "severity": "blocking",
        "fact_ids": _safe_fact_ids(fact_ids),
        "verification_status": _safe_verification_status(verification_status),
        "warnings": _ordered_warnings(_map_warning_tokens(warnings)),
    }


def _mapped_component_warnings(component: str, report: Any) -> set[str]:
    mapped: set[str] = set()
    if report is None:
        return mapped
    if not isinstance(report, dict):
        return {"component_malformed"}
    warnings = report.get("warnings")
    if not isinstance(warnings, list):
        return mapped
    for token in warnings:
        if not isinstance(token, str):
            continue
        if token == "max_items_reached":
            mapped.add("max_items_reached")
        elif "malformed" in token:
            mapped.add("component_malformed")
        elif token in {"fixture_missing", "fact_sheet_missing", "candidate_markdown_missing"}:
            mapped.add("malformed_input_degraded")
        elif component == "layer1":
            mapped.add("layer1_warning")
            if token in {"coverage_below_target", "expected_topic_missing"}:
                mapped.add("coverage_warning")
            if token == "mock_question_count_below_minimum":
                mapped.add("mock_question_warning")
        elif component == "recompute":
            if token in {
                "computation_missing",
                "unsupported_computation_method",
                "malformed_computation_inputs",
                "invalid_numeric_value",
                "recomputed_mismatch",
            }:
                mapped.add("numeric_unverified")
        elif component == "canonical":
            if token in {"canonical_fact_missing", "canonical_value_mismatch", "canonical_not_eligible"}:
                mapped.add("canonical_unmatched")
        elif component == "leak":
            if token == "verification_context_missing":
                mapped.add("unknown_verification_context")
            else:
                mapped.add("leak_warning")
    return mapped


def _map_warning_tokens(warnings: Any) -> set[str]:
    if not isinstance(warnings, (list, tuple, set)):
        return set()
    return {token for token in warnings if token in SAFE_WARNING_TOKENS}


def _overall_status(
    *,
    blocking_failures: list[dict[str, Any]],
    warnings: list[str],
    component_statuses: dict[str, str],
    truncated: bool,
) -> str:
    if blocking_failures:
        return "failed"
    if truncated or "max_items_reached" in warnings or any(status == "partial" for status in component_statuses.values()):
        return "partial"
    if all(status in {"unknown", "skipped"} for status in component_statuses.values()):
        return "skipped"
    if warnings or any(status == "warning" for status in component_statuses.values()):
        return "warning"
    return "passed"


def _safety_floor_green(
    *,
    shippable: bool,
    warnings: list[str],
    summary: dict[str, int],
    component_statuses: dict[str, str],
) -> bool:
    if not shippable:
        return False
    if any(token in warnings for token in ("malformed_input_degraded", "component_malformed", "component_missing")):
        return False
    if component_statuses.get("leak") not in {"passed", "skipped"}:
        return False
    if summary.get("numeric_blocking_failure_count", 0) or summary.get("layer1_blocking_failure_count", 0):
        return False
    if summary.get("failed_recompute_count", 0) or summary.get("failed_canonical_count", 0):
        return False
    return True


def _accuracy_axis(summary: dict[str, int], statuses: dict[str, Any]) -> int | None:
    if summary.get("numeric_blocking_failure_count", 0) or summary.get("failed_recompute_count", 0) or summary.get("failed_canonical_count", 0):
        return 0
    verified = summary.get("verified_recompute_count", 0) + summary.get("verified_canonical_count", 0)
    if verified > 0:
        return 5
    if summary.get("unverified_fact_count", 0) > 0:
        return 4
    if statuses.get("recompute") == "unknown" and statuses.get("canonical") in {"unknown", "skipped"}:
        return 2
    return 2


def _coverage_axis(layer1_component_summary: Any) -> int | None:
    if not isinstance(layer1_component_summary, dict):
        return None
    summary = _safe_summary(layer1_component_summary.get("summary"))
    expected = _int(summary.get("expected_topic_count"))
    observed = _int(summary.get("observed_topic_count"))
    if expected <= 0:
        return None
    ratio = observed / expected
    if ratio >= 0.95:
        return 5
    if ratio >= 0.85:
        return 4
    if ratio >= 0.70:
        return 3
    if ratio >= 0.50:
        return 2
    return 0


def _solved_problem_axis(unified_report: dict[str, Any], layer1_component_summary: Any) -> int | None:
    if _has_blocking(unified_report, component="layer1", check_id="worked_answer_completeness"):
        return 0
    if _has_blocking(unified_report, component="leak", check_id="quality_safety_leak_scan"):
        return 0
    if not isinstance(layer1_component_summary, dict):
        return 3
    checks = _component_checks(unified_report, "layer1")
    worked = checks.get("worked_answer_completeness")
    if worked == "passed":
        return 5
    return 3


def _clarity_axis(unified_report: dict[str, Any], statuses: dict[str, Any]) -> int | None:
    leak_status = statuses.get("leak")
    if leak_status == "unknown":
        return None
    if _has_blocking(unified_report, component="leak"):
        return 0
    if leak_status == "warning":
        return 3
    if leak_status == "passed":
        return 5
    if leak_status == "skipped":
        return None
    return 3


def _component_checks(unified_report: dict[str, Any], component: str) -> dict[str, str]:
    # The unified report does not persist child checks. This helper supports
    # tests that pass an internal sanitized summary with a checks_by_id field.
    summaries = unified_report.get("component_summaries")
    if not isinstance(summaries, dict):
        return {}
    data = summaries.get(component)
    if not isinstance(data, dict):
        return {}
    checks = data.get("checks_by_id")
    return checks if isinstance(checks, dict) else {}


def _has_blocking(unified_report: dict[str, Any], *, component: str, check_id: str | None = None) -> bool:
    failures = unified_report.get("blocking_failures")
    if not isinstance(failures, list):
        return False
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        if failure.get("component") != component:
            continue
        if check_id is None or failure.get("check_id") == check_id:
            return True
    return False


def _axes(
    accuracy: int | None,
    coverage: int | None,
    solved_problem: int | None,
    clarity: int | None,
) -> dict[str, int | None]:
    return {
        "accuracy": _axis_value(accuracy),
        "coverage": _axis_value(coverage),
        "solved_problem": _axis_value(solved_problem),
        "clarity": _axis_value(clarity),
    }


def _axis_value(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if 0 <= value <= 5:
        return value
    return None


def _stable_failures(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {component: index for index, component in enumerate(COMPONENTS)}
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for failure in sorted(
        failures,
        key=lambda item: (
            order.get(str(item.get("component")), 99),
            str(item.get("check_id")),
            ",".join(item.get("fact_ids") or []),
            str(item.get("verification_status")),
        ),
    ):
        key = (
            failure.get("component"),
            failure.get("check_id"),
            tuple(failure.get("fact_ids") or []),
            failure.get("verification_status"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(failure)
    return unique


def _safe_summary(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int(number) for key, number in value.items() if isinstance(key, str)}


def _safe_component_status(status: Any) -> str:
    return status if status in COMPONENT_STATUSES else "unknown"


def _safe_check_id(value: Any, allowed: frozenset[str]) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return "unknown_check"


def _safe_fact_ids(value: Any) -> list[str]:
    raw = value if isinstance(value, list) else [value]
    fact_ids: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        candidate = item.strip().lower()
        if _UNSAFE_RE.search(candidate) or _BASE64ISH_RE.fullmatch(candidate):
            continue
        candidate = re.sub(r"[^a-z0-9._-]+", "_", candidate).strip("._-")[:80]
        if candidate and _SAFE_ID_RE.fullmatch(candidate) and candidate not in fact_ids:
            fact_ids.append(candidate)
    return fact_ids[:8]


def _safe_verification_status(value: Any) -> str:
    return value if value in SAFE_VERIFICATION_STATUSES else "unknown"


def _ordered_warnings(warnings: Any) -> list[str]:
    seen = set(warnings) if isinstance(warnings, (set, list, tuple)) else set()
    return [token for token in WARNING_ORDER if token in seen]


def _has_warning(report: Any, tokens: set[str]) -> bool:
    if not isinstance(report, dict) or not isinstance(report.get("warnings"), list):
        return False
    return any(token in tokens for token in report["warnings"])


def _layer1_has_failed_numeric(report: Any) -> bool:
    if not isinstance(report, dict) or not isinstance(report.get("checks"), list):
        return False
    for check in report["checks"]:
        if isinstance(check, dict) and check.get("id") == "numeric_correctness" and check.get("status") == "failed":
            return True
    return False


def _layer1_checks_by_id(report: Any) -> dict[str, str]:
    if not isinstance(report, dict) or not isinstance(report.get("checks"), list):
        return {}
    checks: dict[str, str] = {}
    for check in report["checks"]:
        if not isinstance(check, dict):
            continue
        check_id = check.get("id")
        status = check.get("status")
        if check_id in LAYER1_CHECK_IDS and status in {"passed", "warning", "failed", "not_applicable", "unknown"}:
            checks[check_id] = status
    return checks


def _resolve_max_items(max_items: Any) -> int:
    if isinstance(max_items, bool):
        return 1000
    if isinstance(max_items, int):
        return max(0, max_items)
    return 1000


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    return 0
