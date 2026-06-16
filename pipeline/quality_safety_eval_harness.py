"""Offline quality-safety eval harness skeleton (Slice 108).

Pure, deterministic, synthetic-only measurement helpers for the Quality Safety
Unit phase. This module does not call providers, judges, APIs, renderers, OCR,
or generation. It reads caller-supplied fixture dictionaries and candidate
Markdown strings, then returns JSON-serializable reports containing only closed
statuses/warnings, counts, numeric values, and sanitized synthetic fixture ids.

It intentionally does not persist JSONL records. A future slice can wire these
pure records to an output path after the schema is validated.
"""
from __future__ import annotations

import math
import re
from typing import Any

VERSION = 1
FIXTURE_KIND = "quality_safety_fixture"
LAYER1_KIND = "quality_safety_eval_layer1"
REGRESSION_KIND = "quality_safety_regression_record"

REPORT_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})
CHECK_IDS = (
    "leaked_reasoning",
    "numeric_correctness",
    "worked_answer_completeness",
    "coverage",
    "mock_question_count",
)
CHECK_STATUSES = frozenset({"passed", "warning", "failed", "not_applicable", "unknown"})

FIXTURE_WARNING_ORDER = (
    "malformed_fixture_degraded",
    "invalid_expected_topic_dropped",
    "invalid_numeric_target_dropped",
    "invalid_min_mock_questions_defaulted",
    "invalid_tier_target_defaulted",
    "max_items_reached",
)

REPORT_WARNING_ORDER = (
    "fixture_missing",
    "candidate_markdown_missing",
    "malformed_fixture_degraded",
    "malformed_input_degraded",
    "max_items_reached",
    "numeric_target_missing",
    "expected_topic_missing",
    "mock_question_count_below_minimum",
    "worked_answer_incomplete_signal",
    "leaked_reasoning_signal",
    "numeric_mismatch_signal",
    "coverage_below_target",
)

SOURCE_QUALITIES = frozenset(
    {"clean", "ambiguous_animation_frames", "scanned", "mixed", "synthetic", "unknown"}
)
TIER_KEYS = ("premium", "local")
BLOCKING_CHECK_IDS = frozenset(
    {"leaked_reasoning", "numeric_correctness", "worked_answer_completeness"}
)

_SAFE_ID_RE = re.compile(r"[^a-z0-9 _.-]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![A-Za-z0-9_])"
)
_SECRETISH_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|\\\\|[A-Za-z]:\\|authorization|bearer|"
    r"api[_-]?key|data:|base64|provider payload|ocr|caption|table text|"
    r"\.pdf|\.docx|\.zip|\.png|\.jpg|\.jpeg|\.webp)",
    re.IGNORECASE,
)
_LEAK_SIGNATURES = (
    "wait",
    "actually",
    "unclear",
    "we'll trust",
    "we will trust",
    "it seems",
    "let's infer",
    "i think",
    "presumably",
)
_LEAK_PATTERNS = tuple(
    re.compile(r"\b" + re.escape(token).replace(r"\ ", r"\s+") + r"\b", re.IGNORECASE)
    for token in _LEAK_SIGNATURES
)
_STRUCTURAL_UNCERTAINTY_RE = re.compile(r"(=\s*\?|≈\s*\?|≃\s*\?)")
_WORKED_MARKER_RE = re.compile(r"\b(worked\s+answer|worked\s+solution|solution|answer)\b", re.IGNORECASE)
_UNRESOLVED_RE = re.compile(
    r"(=\s*\?|≈\s*\?|≃\s*\?|answer\s+missing|solution\s+missing|unresolved|incomplete\s+answer)",
    re.IGNORECASE,
)
_MOCK_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:(?:mock|practice)\s+question\b|q\d+\b(?:[\s:.)-]|$))",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")


def load_quality_safety_fixture_spec(data: Any) -> dict[str, Any]:
    """Return a normalized synthetic fixture spec; never raise on bad input."""
    warnings: set[str] = set()
    if not isinstance(data, dict):
        warnings.add("malformed_fixture_degraded")
        data = {}

    lecture_id = _safe_fixture_id(data.get("lecture_id"), default="synthetic_eval_fixture")
    title = _safe_fixture_id(data.get("title"), default="Synthetic Eval Fixture")
    source_quality = data.get("source_quality")
    if not isinstance(source_quality, str):
        source_quality = "synthetic"
    source_quality = source_quality.strip().lower()
    if source_quality not in SOURCE_QUALITIES:
        source_quality = "synthetic"

    expected_topics = _load_expected_topics(data.get("expected_topics"), warnings)
    numerics = _load_numeric_targets(data.get("ground_truth_numerics"), warnings)
    min_mock_questions = _load_min_mock_questions(data.get("min_mock_questions"), warnings)
    tier_targets = _load_tier_targets(data.get("tier_targets"), warnings)

    return {
        "version": VERSION,
        "kind": FIXTURE_KIND,
        "lecture_id": lecture_id,
        "title": title,
        "source_quality": source_quality,
        "expected_topics": expected_topics,
        "ground_truth_numerics": numerics,
        "min_mock_questions": min_mock_questions,
        "tier_targets": tier_targets,
        "warnings": _ordered(warnings, FIXTURE_WARNING_ORDER),
    }


def run_quality_safety_layer1_checks(
    candidate_markdown: Any,
    fixture_spec: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Run deterministic Layer-1 checks over Markdown and a synthetic fixture."""
    report_warnings: set[str] = set()
    if not isinstance(candidate_markdown, str):
        report_warnings.add("candidate_markdown_missing")
        candidate_markdown = ""

    if not isinstance(fixture_spec, dict) or fixture_spec.get("kind") != FIXTURE_KIND:
        report_warnings.add("fixture_missing")
        fixture = load_quality_safety_fixture_spec(fixture_spec)
    else:
        fixture = load_quality_safety_fixture_spec(fixture_spec)
    if fixture.get("warnings"):
        report_warnings.add("malformed_fixture_degraded")

    checks = [
        _check_leaked_reasoning(candidate_markdown, report_warnings),
        _check_numeric_correctness(candidate_markdown, fixture, report_warnings),
        _check_worked_answer_completeness(candidate_markdown, report_warnings),
        _check_coverage(candidate_markdown, fixture, report_warnings),
        _check_mock_question_count(candidate_markdown, fixture, report_warnings),
    ]

    truncated = False
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        cap = max(0, min(max_items, len(checks)))
        if cap < len(checks):
            checks = checks[:cap]
            truncated = True
            report_warnings.add("max_items_reached")

    blocking_failures = [
        check["id"]
        for check in checks
        if check["id"] in BLOCKING_CHECK_IDS and check["status"] == "failed"
    ]
    summary = _layer1_summary(checks, fixture, blocking_failures, report_warnings)
    status = _layer1_status(
        checks=checks,
        blocking_failures=blocking_failures,
        warning_count=len(report_warnings),
        truncated=truncated,
    )
    return {
        "version": VERSION,
        "kind": LAYER1_KIND,
        "status": status,
        "shippable": status == "passed" and not blocking_failures,
        "summary": summary,
        "checks": checks,
        "blocking_failures": blocking_failures,
        "warnings": _ordered(report_warnings, REPORT_WARNING_ORDER),
    }


def run_quality_safety_eval(
    candidate_markdown: Any,
    fixture_spec: Any,
    *,
    run_metadata: dict[str, Any] | None = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Convenience wrapper returning a report and safe regression record."""
    fixture = load_quality_safety_fixture_spec(fixture_spec)
    report = run_quality_safety_layer1_checks(
        candidate_markdown, fixture, max_items=max_items
    )
    metadata = run_metadata if isinstance(run_metadata, dict) else {}
    record = build_quality_safety_regression_record(
        run_id=metadata.get("run_id", "synthetic_run"),
        git_sha=metadata.get("git_sha"),
        model=metadata.get("model"),
        preset=metadata.get("preset"),
        lecture_id=metadata.get("lecture_id", fixture.get("lecture_id")),
        tier=metadata.get("tier"),
        layer1_report=report,
        overall_10=metadata.get("overall_10"),
        previous_record=metadata.get("previous_record"),
    )
    return {"layer1": report, "record": record}


def build_quality_safety_regression_record(
    *,
    run_id: Any,
    git_sha: Any = None,
    model: Any = None,
    preset: Any = None,
    lecture_id: Any = None,
    tier: Any = None,
    layer1_report: dict[str, Any] | None = None,
    overall_10: Any = None,
    previous_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, JSON-serializable future JSONL record."""
    layer1 = layer1_report if isinstance(layer1_report, dict) else None
    score = _safe_score(overall_10)
    shippable = bool(layer1.get("shippable")) if layer1 else False
    warnings = _safe_string_list(layer1.get("warnings")) if layer1 else []
    blocking_failures = _safe_blocking_failures(layer1.get("blocking_failures")) if layer1 else []
    delta_vs_prev = _delta_vs_previous(score, previous_record)
    regressed = _is_regressed(
        current_shippable=shippable,
        current_score=score,
        current_layer1=layer1,
        previous_record=previous_record,
    )

    return {
        "version": VERSION,
        "kind": REGRESSION_KIND,
        "run_id": _safe_meta(run_id, "synthetic_run"),
        "git_sha": _safe_meta(git_sha, "unknown"),
        "model": _safe_meta(model, "unknown"),
        "preset": _safe_meta(preset, "unknown"),
        "lecture_id": _safe_meta(lecture_id, "synthetic_eval_fixture"),
        "tier": _safe_meta(tier, "unknown"),
        "overall_10": score,
        "shippable": shippable,
        "axes": {},
        "layer1": layer1 if layer1 is not None else None,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "delta_vs_prev": delta_vs_prev,
        "regressed": regressed,
    }


def _load_expected_topics(value: Any, warnings: set[str]) -> list[str]:
    topics: list[str] = []
    if value is None:
        return topics
    if not isinstance(value, list):
        warnings.add("invalid_expected_topic_dropped")
        return topics
    seen: set[str] = set()
    for item in value:
        topic = _safe_fixture_id(item, default="")
        if not topic:
            warnings.add("invalid_expected_topic_dropped")
            continue
        key = _normalize(topic)
        if key in seen:
            continue
        seen.add(key)
        topics.append(topic)
    return topics


def _load_numeric_targets(value: Any, warnings: set[str]) -> list[dict[str, float | str]]:
    targets: list[dict[str, float | str]] = []
    if value is None:
        return targets
    if not isinstance(value, list):
        warnings.add("invalid_numeric_target_dropped")
        return targets
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            warnings.add("invalid_numeric_target_dropped")
            continue
        label = _safe_fixture_id(item.get("label"), default="")
        expected = _finite_float(item.get("value"))
        tol = _finite_float(item.get("tol"))
        if not label or expected is None or tol is None or tol < 0:
            warnings.add("invalid_numeric_target_dropped")
            continue
        key = _normalize(label)
        if key in seen:
            continue
        seen.add(key)
        targets.append({"label": label, "value": float(expected), "tol": float(tol)})
    return targets


def _load_min_mock_questions(value: Any, warnings: set[str]) -> int:
    if isinstance(value, bool):
        warnings.add("invalid_min_mock_questions_defaulted")
        return 0
    if isinstance(value, int):
        return max(0, value)
    if value is None:
        return 0
    warnings.add("invalid_min_mock_questions_defaulted")
    return 0


def _load_tier_targets(value: Any, warnings: set[str]) -> dict[str, float]:
    targets: dict[str, float] = {}
    if value is None:
        return targets
    if not isinstance(value, dict):
        warnings.add("invalid_tier_target_defaulted")
        return targets
    for key in TIER_KEYS:
        score = _finite_float(value.get(key))
        if score is None:
            if key in value:
                warnings.add("invalid_tier_target_defaulted")
            continue
        targets[key] = max(0.0, min(10.0, float(score)))
    return targets


def _check_leaked_reasoning(candidate: str, warnings: set[str]) -> dict[str, Any]:
    signature_count = 0
    for pattern in _LEAK_PATTERNS:
        signature_count += len(pattern.findall(candidate))
    structural_count = 0
    for line in candidate.splitlines():
        if _is_mock_question_line(line):
            continue
        if _STRUCTURAL_UNCERTAINTY_RE.search(line) or "?" in line:
            structural_count += 1
    signal_count = signature_count + structural_count
    status = "failed" if signal_count else "passed"
    if signal_count:
        warnings.add("leaked_reasoning_signal")
    return {
        "id": "leaked_reasoning",
        "status": status,
        "blocking": status == "failed",
        "signature_count": signature_count,
        "structural_uncertainty_count": structural_count,
        "signal_count": signal_count,
    }


def _check_numeric_correctness(
    candidate: str, fixture: dict[str, Any], warnings: set[str]
) -> dict[str, Any]:
    targets = fixture.get("ground_truth_numerics")
    if not isinstance(targets, list) or not targets:
        return {
            "id": "numeric_correctness",
            "status": "not_applicable",
            "blocking": False,
            "target_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "missing_count": 0,
            "targets": [],
        }

    details: list[dict[str, Any]] = []
    pass_count = fail_count = missing_count = 0
    normalized_lines = [(_normalize(line), line) for line in candidate.splitlines()]
    for item in targets:
        label = str(item.get("label", ""))
        expected = float(item.get("value", 0.0))
        tol = float(item.get("tol", 0.0))
        label_norm = _normalize(label)
        values: list[float] = []
        for line_norm, line in normalized_lines:
            if label_norm and label_norm in line_norm:
                values.extend(_extract_numbers(line))
        unique_values = _dedupe_floats(values)
        if not unique_values:
            missing_count += 1
            status = "unknown"
            warnings.add("numeric_target_missing")
        elif any(abs(value - expected) <= tol for value in unique_values):
            pass_count += 1
            status = "passed"
        else:
            fail_count += 1
            status = "failed"
            warnings.add("numeric_mismatch_signal")
        details.append(
            {
                "label": label,
                "status": status,
                "expected_value": expected,
                "tolerance": tol,
                "found_values": unique_values,
            }
        )

    if fail_count:
        status = "failed"
    elif missing_count:
        status = "unknown"
    else:
        status = "passed"
    return {
        "id": "numeric_correctness",
        "status": status,
        "blocking": status == "failed",
        "target_count": len(targets),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "missing_count": missing_count,
        "targets": details,
    }


def _check_worked_answer_completeness(candidate: str, warnings: set[str]) -> dict[str, Any]:
    in_worked_section = False
    marker_count = 0
    unresolved_count = 0
    for line in candidate.splitlines():
        stripped = line.strip()
        if _HEADING_RE.match(stripped):
            in_worked_section = bool(_WORKED_MARKER_RE.search(stripped))
        marker = bool(_WORKED_MARKER_RE.search(stripped))
        if marker:
            marker_count += 1
        if marker or in_worked_section:
            if _UNRESOLVED_RE.search(stripped) or stripped.endswith("?"):
                unresolved_count += 1
    status = "failed" if unresolved_count else "passed"
    if unresolved_count:
        warnings.add("worked_answer_incomplete_signal")
    return {
        "id": "worked_answer_completeness",
        "status": status,
        "blocking": status == "failed",
        "worked_marker_count": marker_count,
        "unresolved_signal_count": unresolved_count,
    }


def _check_coverage(candidate: str, fixture: dict[str, Any], warnings: set[str]) -> dict[str, Any]:
    topics = fixture.get("expected_topics")
    if not isinstance(topics, list) or not topics:
        return {
            "id": "coverage",
            "status": "not_applicable",
            "blocking": False,
            "expected_count": 0,
            "observed_count": 0,
            "missing_count": 0,
            "coverage_ratio": None,
            "missing_topics": [],
        }
    haystack = _normalize(candidate)
    missing: list[str] = []
    for topic in topics:
        needle = _normalize(topic)
        if not needle or needle not in haystack:
            missing.append(topic)
    observed = len(topics) - len(missing)
    ratio = observed / len(topics) if topics else 1.0
    if missing:
        warnings.add("expected_topic_missing")
    if ratio < 0.9:
        warnings.add("coverage_below_target")
    return {
        "id": "coverage",
        "status": "warning" if ratio < 0.9 else "passed",
        "blocking": False,
        "expected_count": len(topics),
        "observed_count": observed,
        "missing_count": len(missing),
        "coverage_ratio": round(ratio, 4),
        "missing_topics": missing,
    }


def _check_mock_question_count(
    candidate: str, fixture: dict[str, Any], warnings: set[str]
) -> dict[str, Any]:
    minimum = fixture.get("min_mock_questions")
    minimum = minimum if isinstance(minimum, int) and not isinstance(minimum, bool) else 0
    count = sum(1 for line in candidate.splitlines() if _is_mock_question_line(line))
    status = "passed" if count >= minimum else "warning"
    if status == "warning":
        warnings.add("mock_question_count_below_minimum")
    return {
        "id": "mock_question_count",
        "status": status,
        "blocking": False,
        "mock_question_count": count,
        "minimum_required": minimum,
    }


def _layer1_summary(
    checks: list[dict[str, Any]],
    fixture: dict[str, Any],
    blocking_failures: list[str],
    warnings: set[str],
) -> dict[str, Any]:
    by_id = {check["id"]: check for check in checks}
    coverage = by_id.get("coverage", {})
    numeric = by_id.get("numeric_correctness", {})
    mock = by_id.get("mock_question_count", {})
    return {
        "blocking_failure_count": len(blocking_failures),
        "advisory_warning_count": len(warnings),
        "check_count": len(checks),
        "expected_topic_count": int(coverage.get("expected_count") or len(fixture.get("expected_topics") or [])),
        "observed_topic_count": int(coverage.get("observed_count") or 0),
        "numeric_target_count": int(numeric.get("target_count") or len(fixture.get("ground_truth_numerics") or [])),
        "numeric_pass_count": int(numeric.get("pass_count") or 0),
        "numeric_fail_count": int(numeric.get("fail_count") or 0),
        "mock_question_count": int(mock.get("mock_question_count") or 0),
    }


def _layer1_status(
    *,
    checks: list[dict[str, Any]],
    blocking_failures: list[str],
    warning_count: int,
    truncated: bool,
) -> str:
    if not checks:
        return "skipped"
    if blocking_failures:
        return "failed"
    if truncated:
        return "partial"
    if warning_count:
        return "warning"
    return "passed"


def _is_regressed(
    *,
    current_shippable: bool,
    current_score: float | None,
    current_layer1: dict[str, Any] | None,
    previous_record: dict[str, Any] | None,
) -> bool:
    if not isinstance(previous_record, dict):
        return False
    if previous_record.get("shippable") is True and not current_shippable:
        return True
    previous_score = _safe_score(previous_record.get("overall_10"))
    if previous_score is not None and current_score is not None:
        if previous_score - current_score > 0.3:
            return True
    previous_checks = _checks_by_id(_previous_layer1(previous_record))
    current_checks = _checks_by_id(current_layer1)
    for check_id in BLOCKING_CHECK_IDS:
        previous = previous_checks.get(check_id)
        current = current_checks.get(check_id)
        if previous and current and previous.get("status") == "passed" and current.get("status") == "failed":
            return True
    return False


def _delta_vs_previous(
    current_score: float | None, previous_record: dict[str, Any] | None
) -> dict[str, float] | None:
    if not isinstance(previous_record, dict):
        return None
    previous_score = _safe_score(previous_record.get("overall_10"))
    if previous_score is None or current_score is None:
        return None
    return {"overall_10_delta": round(current_score - previous_score, 4)}


def _previous_layer1(previous_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(previous_record, dict):
        return None
    layer1 = previous_record.get("layer1")
    return layer1 if isinstance(layer1, dict) else None


def _checks_by_id(layer1: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(layer1, dict):
        return {}
    checks = layer1.get("checks")
    if not isinstance(checks, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in checks:
        if isinstance(item, dict) and item.get("id") in CHECK_IDS:
            out[str(item["id"])] = item
    return out


def _safe_blocking_failures(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item in CHECK_IDS]


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed = set(REPORT_WARNING_ORDER)
    return [str(item) for item in value if item in allowed]


def _safe_score(value: Any) -> float | None:
    score = _finite_float(value)
    if score is None:
        return None
    return max(0.0, min(10.0, round(float(score), 4)))


def _safe_meta(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    stripped = value.strip()
    if not stripped or len(stripped) > 80 or _SECRETISH_RE.search(stripped):
        return default
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", stripped):
        return default
    return stripped


def _safe_fixture_id(value: Any, *, default: str) -> str:
    if not isinstance(value, str):
        return default
    stripped = " ".join(value.strip().split())
    if not stripped or len(stripped) > 100 or _SECRETISH_RE.search(stripped):
        return default
    cleaned = _SAFE_ID_RE.sub("", stripped.lower()).strip(" ._-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or default


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return _NON_ALNUM_RE.sub(" ", value.lower()).strip()


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _extract_numbers(line: str) -> list[float]:
    numbers: list[float] = []
    for match in _NUMBER_RE.finditer(line):
        try:
            value = float(match.group(0))
        except ValueError:
            continue
        if math.isfinite(value):
            numbers.append(value)
    return numbers


def _dedupe_floats(values: list[float]) -> list[float]:
    out: list[float] = []
    seen: set[float] = set()
    for value in values:
        rounded = round(value, 12)
        if rounded in seen:
            continue
        seen.add(rounded)
        out.append(float(value))
    return out


def _is_mock_question_line(line: str) -> bool:
    return bool(_MOCK_LINE_RE.search(line))


def _ordered(values: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in values]
