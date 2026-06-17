"""Quality Safety canonical fixture matcher v1 (Slice 112).

Pure deterministic fallback matcher for the Quality Safety Unit. Recompute from
structured computation inputs remains the primary truth path; this module only
allows a narrow exact canonical fixture match when recompute is unavailable or
unsupported.

The module is intentionally unwired and offline:
  * stdlib only, plus the Slice 110 fact-sheet normalizer;
  * no FastAPI / frontend / provider / model / cloud / OCR / render / job runtime
    imports;
  * reads no source documents, no ``clean.md``, writes no artifacts, calls no
    providers/models;
  * never raises on malformed input and returns JSON-serializable dicts only;
  * never echoes raw paths, URLs, provider payloads, snippets, OCR/table/caption
    text, raw computation inputs, or raw exception text.
"""
from __future__ import annotations

import math
import re
from typing import Any

from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet

VERSION = 1
FIXTURE_KIND = "quality_safety_canonical_fixture"
REPORT_KIND = "quality_safety_canonical_match_report"

SOURCE_QUALITIES = frozenset(
    {"clean", "ambiguous_animation_frames", "scanned", "mixed", "synthetic", "unknown"}
)
FACT_TYPES = frozenset({"numeric", "categorical", "string"})
PROVENANCE = "canonical_fixture"

REPORT_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})
CHECK_IDS = frozenset(
    {
        "canonical_fixture_match",
        "canonical_fixture_mismatch",
        "canonical_fixture_missing",
        "canonical_fixture_skipped_by_recompute_verified",
        "canonical_fixture_skipped_by_recompute_failed",
        "canonical_fixture_not_applicable",
    }
)
CHECK_STATUSES = frozenset({"passed", "warning", "failed", "not_applicable", "unknown"})

FIXTURE_WARNING_ORDER = (
    "malformed_canonical_fixture_degraded",
    "invalid_canonical_fact_dropped",
    "invalid_canonical_value",
    "invalid_canonical_tolerance",
    "invalid_canonical_match_key",
    "invalid_lecture_id",
    "invalid_source_quality",
    "unsafe_string_sanitized",
    "max_items_reached",
)

REPORT_WARNING_ORDER = (
    "fact_sheet_missing",
    "canonical_fixture_missing",
    "malformed_fact_sheet_degraded",
    "malformed_canonical_fixture_degraded",
    "canonical_lecture_id_mismatch",
    "canonical_fact_missing",
    "canonical_value_mismatch",
    "canonical_not_eligible",
    "skipped_by_recompute_verified",
    "skipped_by_recompute_failed",
    "max_items_reached",
)

_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_SAFE_MATCH_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,120}$")
_UNSAFE_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|/var/|\\\\|[A-Za-z]:\\|\.\./|/\.\.|"
    r"authorization|bearer|api[_-]?key|token|secret|data:|base64|provider payload|"
    r"ocr|caption|table text|uploaded[_ -]?quality|quality[_ -]?spec|evidence quote|"
    r"source text|raw text|guide snippet|source snippet|private|\.pdf|\.docx|\.zip|"
    r"\.png|\.jpg|\.jpeg|\.webp|\.socket|\.sock)",
    re.IGNORECASE,
)
_BASE64ISH_RE = re.compile(r"^[A-Za-z0-9+/]{80,}={0,2}$")

_DEFAULT_MAX_ITEMS = 200
_ALIAS_LIMIT = 16
_MAX_TOLERANCE = 1.0
_DEFAULT_TOLERANCE = 1e-6


def normalize_quality_safety_canonical_fixture(data: Any, *, max_items: int | None = None) -> dict[str, Any]:
    """Normalize a canonical fixture; never raise on malformed input."""
    try:
        return _normalize_fixture(data, max_items=max_items)
    except Exception:
        return _fixture(
            lecture_id="synthetic_fixture",
            source_quality="unknown",
            facts=[],
            warnings={"malformed_canonical_fixture_degraded"},
        )


def build_quality_safety_canonical_match_report(
    fact_sheet: Any,
    canonical_fixture: Any,
    *,
    recompute_report: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Build a canonical fallback match report; never raise."""
    result = _match(
        fact_sheet,
        canonical_fixture,
        recompute_report=recompute_report,
        max_items=max_items,
    )
    return result["report"]


def match_quality_safety_canonical_facts(
    fact_sheet: Any,
    canonical_fixture: Any,
    *,
    recompute_report: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Return a normalized fact sheet copy plus the canonical fallback report."""
    return _match(
        fact_sheet,
        canonical_fixture,
        recompute_report=recompute_report,
        max_items=max_items,
    )


def _normalize_fixture(data: Any, *, max_items: Any) -> dict[str, Any]:
    warnings: set[str] = set()
    if not isinstance(data, dict):
        warnings.add("malformed_canonical_fixture_degraded")
        return _fixture(
            lecture_id="synthetic_fixture",
            source_quality="unknown",
            facts=[],
            warnings=warnings,
        )

    lecture_id = _safe_id(data.get("lecture_id"), "synthetic_fixture", warnings, "invalid_lecture_id")
    source_quality = _safe_source_quality(data.get("source_quality"), warnings)
    cap = _resolve_max_items(max_items)

    raw_facts = data.get("facts")
    if raw_facts is None and isinstance(data.get("ground_truth_numerics"), list):
        raw_facts = data.get("ground_truth_numerics")
    if raw_facts is None:
        raw_facts = []
    if not isinstance(raw_facts, list):
        warnings.add("malformed_canonical_fixture_degraded")
        raw_facts = []

    if len(raw_facts) > cap:
        warnings.add("max_items_reached")

    facts: list[dict[str, Any]] = []
    for index, raw_fact in enumerate(raw_facts[:cap], start=1):
        fact = _normalize_canonical_fact(raw_fact, lecture_id=lecture_id, index=index, warnings=warnings)
        if fact is not None:
            facts.append(fact)

    return _fixture(
        lecture_id=lecture_id,
        source_quality=source_quality,
        facts=facts,
        warnings=warnings,
    )


def _normalize_canonical_fact(
    data: Any,
    *,
    lecture_id: str,
    index: int,
    warnings: set[str],
) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        warnings.add("invalid_canonical_fact_dropped")
        return None

    fact_id = _safe_id(data.get("id"), f"synthetic.fact.{index:04d}", warnings, "invalid_canonical_fact_dropped")
    label = _safe_token(data.get("label"), "synthetic_label", warnings, "invalid_canonical_fact_dropped")
    fact_type = _safe_fact_type(data.get("type"), warnings)

    value: Any
    if fact_type == "numeric":
        value = _finite_number(data.get("value"))
        if value is None:
            warnings.add("invalid_canonical_value")
            warnings.add("invalid_canonical_fact_dropped")
            return None
    else:
        value = _safe_token(data.get("value"), "synthetic_value", warnings, "unsafe_string_sanitized")

    tolerance = _finite_number(data.get("tol"))
    if tolerance is None:
        tolerance = _finite_number(data.get("tolerance"))
    if fact_type == "numeric":
        if tolerance is None:
            tolerance = _DEFAULT_TOLERANCE
        if not (0.0 <= float(tolerance) <= _MAX_TOLERANCE):
            warnings.add("invalid_canonical_tolerance")
            warnings.add("invalid_canonical_fact_dropped")
            return None
    else:
        tolerance = None

    default_match_key = _match_key(lecture_id, label)
    match_key_raw = data.get("match_key")
    if match_key_raw is None:
        match_key = default_match_key
    else:
        match_key = _safe_match_key(match_key_raw, default_match_key, warnings)

    aliases = _safe_aliases(data.get("allowed_aliases"), warnings)

    return {
        "id": fact_id,
        "label": label,
        "value": value,
        "tol": tolerance if fact_type == "numeric" else None,
        "type": fact_type,
        "match_key": match_key,
        "allowed_aliases": aliases,
        "provenance": PROVENANCE,
    }


def _fixture(
    *,
    lecture_id: str,
    source_quality: str,
    facts: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": FIXTURE_KIND,
        "lecture_id": lecture_id,
        "source_quality": source_quality,
        "facts": facts,
        "warnings": _ordered(warnings, FIXTURE_WARNING_ORDER),
    }


def _match(
    fact_sheet: Any,
    canonical_fixture: Any,
    *,
    recompute_report: Any,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()
    checks: list[dict[str, Any]] = []
    blocking_failures: list[dict[str, Any]] = []

    if fact_sheet is None:
        warnings.add("fact_sheet_missing")
        return _result(
            normalize_quality_safety_fact_sheet(None),
            _report("skipped", checks, blocking_failures, warnings, fact_count=0, canonical_count=0),
        )

    if canonical_fixture is None:
        warnings.add("canonical_fixture_missing")
        sheet = normalize_quality_safety_fact_sheet(fact_sheet)
        if "malformed_fact_sheet_degraded" in sheet.get("warnings", []):
            warnings.add("malformed_fact_sheet_degraded")
        return _result(
            sheet,
            _report(
                "skipped",
                checks,
                blocking_failures,
                warnings,
                fact_count=_count_facts(sheet),
                canonical_count=0,
            ),
        )

    sheet = normalize_quality_safety_fact_sheet(fact_sheet)
    if "malformed_fact_sheet_degraded" in sheet.get("warnings", []):
        warnings.add("malformed_fact_sheet_degraded")

    fixture = normalize_quality_safety_canonical_fixture(canonical_fixture, max_items=max_items)
    fixture_warnings = set(fixture.get("warnings", []))
    if "malformed_canonical_fixture_degraded" in fixture_warnings:
        warnings.add("malformed_canonical_fixture_degraded")
    if "max_items_reached" in fixture_warnings:
        warnings.add("max_items_reached")

    fact_count = _count_facts(sheet)
    canonical_count = len(fixture.get("facts", [])) if isinstance(fixture.get("facts"), list) else 0

    if sheet.get("lecture_id") != fixture.get("lecture_id"):
        warnings.add("canonical_lecture_id_mismatch")
        return _result(
            sheet,
            _report("skipped", checks, blocking_failures, warnings, fact_count=fact_count, canonical_count=canonical_count),
        )

    recompute_status = _recompute_status_map(recompute_report)
    fixture_index = _canonical_index(fixture)
    cap = _resolve_max_items(max_items)
    processed = 0
    truncated = False

    for fact in _iter_facts(sheet):
        if processed >= cap:
            truncated = True
            break
        processed += 1
        fact_id = _safe_fact_id(fact.get("id"))
        status = recompute_status.get(fact_id)
        if status is None:
            status = _status_from_fact(fact)

        if status == "verified":
            check = _check(
                fact_id=fact_id,
                check_id="canonical_fixture_skipped_by_recompute_verified",
                status="not_applicable",
                warnings=["skipped_by_recompute_verified"],
            )
            checks.append(check)
            warnings.add("skipped_by_recompute_verified")
            continue
        if status == "failed":
            check = _check(
                fact_id=fact_id,
                check_id="canonical_fixture_skipped_by_recompute_failed",
                status="not_applicable",
                warnings=["skipped_by_recompute_failed"],
            )
            checks.append(check)
            warnings.add("skipped_by_recompute_failed")
            continue

        if fact.get("type") != "numeric":
            check = _check(
                fact_id=fact_id,
                check_id="canonical_fixture_not_applicable",
                status="not_applicable",
                supplied_value=None,
                warnings=["canonical_not_eligible"],
            )
            checks.append(check)
            warnings.add("canonical_not_eligible")
            continue

        supplied = _finite_number(fact.get("value"))
        if supplied is None:
            check = _check(
                fact_id=fact_id,
                check_id="canonical_fixture_not_applicable",
                status="not_applicable",
                supplied_value=None,
                warnings=["canonical_not_eligible"],
            )
            checks.append(check)
            warnings.add("canonical_not_eligible")
            continue

        canonical = _find_canonical_fact(fact, sheet.get("lecture_id"), fixture_index)
        if canonical is None:
            check = _check(
                fact_id=fact_id,
                check_id="canonical_fixture_missing",
                status="warning",
                supplied_value=supplied,
                warnings=["canonical_fact_missing"],
            )
            checks.append(check)
            warnings.add("canonical_fact_missing")
            continue

        if canonical.get("type") != "numeric":
            check = _check(
                fact_id=fact_id,
                canonical_id=_safe_fact_id(canonical.get("id")),
                label=_safe_label(fact.get("label")),
                match_key=_safe_optional_match_key(canonical.get("match_key")),
                check_id="canonical_fixture_not_applicable",
                status="not_applicable",
                supplied_value=supplied,
                warnings=["canonical_not_eligible"],
            )
            checks.append(check)
            warnings.add("canonical_not_eligible")
            continue

        canonical_value = _finite_number(canonical.get("value"))
        tolerance = _finite_number(canonical.get("tol"))
        if canonical_value is None or tolerance is None:
            check = _check(
                fact_id=fact_id,
                canonical_id=_safe_fact_id(canonical.get("id")),
                check_id="canonical_fixture_not_applicable",
                status="not_applicable",
                supplied_value=supplied,
                warnings=["canonical_not_eligible"],
            )
            checks.append(check)
            warnings.add("canonical_not_eligible")
            continue

        if abs(float(supplied) - float(canonical_value)) <= float(tolerance):
            check = _check(
                fact_id=fact_id,
                canonical_id=_safe_fact_id(canonical.get("id")),
                label=_safe_label(fact.get("label")),
                match_key=_safe_optional_match_key(canonical.get("match_key")),
                check_id="canonical_fixture_match",
                status="passed",
                supplied_value=supplied,
                canonical_value=canonical_value,
                tolerance=tolerance,
                warnings=[],
            )
            checks.append(check)
            fact["verification_status"] = "verified"
            fact["provenance"] = PROVENANCE
            fact["confidence"] = "high"
            continue

        check = _check(
            fact_id=fact_id,
            canonical_id=_safe_fact_id(canonical.get("id")),
            label=_safe_label(fact.get("label")),
            match_key=_safe_optional_match_key(canonical.get("match_key")),
            check_id="canonical_fixture_mismatch",
            status="failed",
            supplied_value=supplied,
            canonical_value=canonical_value,
            tolerance=tolerance,
            warnings=["canonical_value_mismatch"],
        )
        checks.append(check)
        blocking_failures.append(_blocking_failure(check))
        warnings.add("canonical_value_mismatch")

    if truncated:
        warnings.add("max_items_reached")

    return _result(
        sheet,
        _report(
            _report_status(checks, blocking_failures, warnings),
            checks,
            blocking_failures,
            warnings,
            fact_count=fact_count,
            canonical_count=canonical_count,
        ),
    )


def _result(sheet: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    return {"fact_sheet": sheet, "report": report}


def _report(
    status: str,
    checks: list[dict[str, Any]],
    blocking_failures: list[dict[str, Any]],
    warnings: set[str],
    *,
    fact_count: int,
    canonical_count: int,
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": REPORT_KIND,
        "status": status if status in REPORT_STATUSES else "warning",
        "blocking": True,
        "summary": _summary(checks, blocking_failures, warnings, fact_count, canonical_count),
        "checks": checks,
        "blocking_failures": blocking_failures,
        "warnings": _ordered(warnings, REPORT_WARNING_ORDER),
    }


def _summary(
    checks: list[dict[str, Any]],
    blocking_failures: list[dict[str, Any]],
    warnings: set[str],
    fact_count: int,
    canonical_count: int,
) -> dict[str, int]:
    eligible = 0
    matched = 0
    mismatch = 0
    unmatched = 0
    skipped = 0
    for check in checks:
        check_id = check.get("check_id")
        status = check.get("status")
        if check_id in {
            "canonical_fixture_skipped_by_recompute_verified",
            "canonical_fixture_skipped_by_recompute_failed",
        }:
            skipped += 1
            continue
        if check_id == "canonical_fixture_not_applicable":
            continue
        eligible += 1
        if status == "passed":
            matched += 1
        elif status == "failed":
            mismatch += 1
        elif check_id == "canonical_fixture_missing":
            unmatched += 1
    return {
        "fact_count": max(0, int(fact_count)),
        "canonical_fact_count": max(0, int(canonical_count)),
        "eligible_fact_count": max(0, eligible),
        "matched_fact_count": max(0, matched),
        "mismatch_count": max(0, mismatch),
        "unmatched_fact_count": max(0, unmatched),
        "skipped_by_recompute_count": max(0, skipped),
        "warning_count": max(0, len(_ordered(warnings, REPORT_WARNING_ORDER))),
        "blocking_failure_count": max(0, len(blocking_failures)),
    }


def _report_status(
    checks: list[dict[str, Any]],
    blocking_failures: list[dict[str, Any]],
    warnings: set[str],
) -> str:
    if blocking_failures:
        return "failed"
    if "max_items_reached" in warnings:
        return "partial"
    if not checks:
        return "skipped"
    eligible = [
        check
        for check in checks
        if check.get("check_id")
        not in {
            "canonical_fixture_not_applicable",
            "canonical_fixture_skipped_by_recompute_verified",
            "canonical_fixture_skipped_by_recompute_failed",
        }
    ]
    if warnings:
        return "warning"
    if eligible and all(check.get("status") == "passed" for check in eligible):
        return "passed"
    return "skipped"


def _check(
    *,
    fact_id: str,
    check_id: str,
    status: str,
    canonical_id: str | None = None,
    label: str | None = None,
    match_key: str | None = None,
    supplied_value: Any = None,
    canonical_value: Any = None,
    tolerance: Any = None,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "canonical_id": canonical_id,
        "label": label,
        "match_key": match_key,
        "check_id": check_id if check_id in CHECK_IDS else "canonical_fixture_not_applicable",
        "status": status if status in CHECK_STATUSES else "unknown",
        "supplied_value": _number_or_none(supplied_value),
        "canonical_value": _number_or_none(canonical_value),
        "tolerance": _number_or_none(tolerance),
        "warnings": _ordered(warnings, REPORT_WARNING_ORDER),
    }


def _blocking_failure(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "fact_id": check.get("fact_id"),
        "canonical_id": check.get("canonical_id"),
        "check_id": "canonical_fixture_mismatch",
        "status": "failed",
        "supplied_value": check.get("supplied_value"),
        "canonical_value": check.get("canonical_value"),
        "tolerance": check.get("tolerance"),
    }


def _canonical_index(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    facts = fixture.get("facts")
    if not isinstance(facts, list):
        return index
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        keys = [
            _safe_fact_id(fact.get("id")),
            _safe_label(fact.get("label")),
            _safe_optional_match_key(fact.get("match_key")),
        ]
        aliases = fact.get("allowed_aliases")
        if isinstance(aliases, list):
            keys.extend(_safe_label(alias) for alias in aliases)
        for key in keys:
            if key and key not in index:
                index[key] = fact
    return index


def _find_canonical_fact(
    fact: dict[str, Any],
    lecture_id: Any,
    index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    label = _safe_label(fact.get("label"))
    keys = [
        _safe_fact_id(fact.get("id")),
        label,
        _match_key(_safe_fact_id(lecture_id), label) if label else None,
        _safe_optional_match_key(fact.get("match_key")),
    ]
    for key in keys:
        if key and key in index:
            return index[key]
    return None


def _recompute_status_map(report: Any) -> dict[str, str]:
    if not isinstance(report, dict):
        return {}
    checks = report.get("checks")
    if not isinstance(checks, list):
        return {}
    status_by_fact: dict[str, str] = {}
    for check in checks:
        if not isinstance(check, dict):
            continue
        fact_id = _safe_fact_id(check.get("fact_id"))
        if fact_id == "fact_unknown":
            continue
        status = check.get("status")
        if status == "passed":
            status_by_fact[fact_id] = "verified"
        elif status == "failed":
            status_by_fact[fact_id] = "failed"
        elif status in {"warning", "unknown", "not_applicable"} and fact_id not in status_by_fact:
            status_by_fact[fact_id] = "eligible"
    return status_by_fact


def _status_from_fact(fact: dict[str, Any]) -> str:
    status = fact.get("verification_status")
    provenance = fact.get("provenance")
    if status == "failed":
        return "failed"
    if status == "verified" and provenance != PROVENANCE:
        return "verified"
    return "eligible"


def _iter_facts(sheet: dict[str, Any]):
    concepts = sheet.get("concepts")
    if not isinstance(concepts, list):
        return
    for concept in concepts:
        if not isinstance(concept, dict):
            continue
        facts = concept.get("facts")
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if isinstance(fact, dict):
                yield fact


def _count_facts(sheet: dict[str, Any]) -> int:
    return sum(1 for _ in _iter_facts(sheet))


def _safe_source_quality(value: Any, warnings: set[str]) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add("invalid_source_quality")
        return "unknown"
    candidate = value.strip().lower()
    if candidate not in SOURCE_QUALITIES:
        warnings.add("invalid_source_quality")
        return "unknown"
    return candidate


def _safe_fact_type(value: Any, warnings: set[str]) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add("invalid_canonical_fact_dropped")
        return "numeric"
    candidate = value.strip().lower()
    if candidate not in FACT_TYPES:
        warnings.add("invalid_canonical_fact_dropped")
        return "numeric"
    return candidate


def _safe_id(value: Any, default: str, warnings: set[str], warning_token: str) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add(warning_token)
        return default
    candidate = _normalize_id(value)
    if not candidate or _unsafe(candidate) or not _SAFE_ID_RE.fullmatch(candidate):
        warnings.add(warning_token)
        return default
    return candidate


def _safe_fact_id(value: Any) -> str:
    if not isinstance(value, str):
        return "fact_unknown"
    candidate = _normalize_id(value)
    if not candidate or _unsafe(candidate) or not _SAFE_ID_RE.fullmatch(candidate):
        return "fact_unknown"
    return candidate


def _safe_token(value: Any, default: str, warnings: set[str], warning_token: str) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add(warning_token)
        return default
    candidate = value.strip()
    if not candidate or _unsafe(candidate):
        warnings.add(warning_token)
        return default
    candidate = re.sub(r"[^A-Za-z0-9_.:-]+", "_", candidate).strip("_.:-")
    if not candidate or not _SAFE_TOKEN_RE.fullmatch(candidate):
        warnings.add(warning_token)
        return default
    return candidate[:80]


def _safe_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or _unsafe(candidate):
        return None
    candidate = re.sub(r"[^A-Za-z0-9_.:-]+", "_", candidate).strip("_.:-")
    if not candidate or not _SAFE_TOKEN_RE.fullmatch(candidate):
        return None
    return candidate[:80]


def _safe_match_key(value: Any, default: str, warnings: set[str]) -> str:
    if not isinstance(value, str):
        warnings.add("invalid_canonical_match_key")
        return default
    candidate = value.strip()
    if not candidate or _unsafe(candidate):
        warnings.add("invalid_canonical_match_key")
        return default
    candidate = re.sub(r"[^A-Za-z0-9_.:-]+", "_", candidate).strip("_.:-")
    if not candidate or not _SAFE_MATCH_KEY_RE.fullmatch(candidate):
        warnings.add("invalid_canonical_match_key")
        return default
    return candidate[:120]


def _safe_optional_match_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or _unsafe(candidate):
        return None
    candidate = re.sub(r"[^A-Za-z0-9_.:-]+", "_", candidate).strip("_.:-")
    if not candidate or not _SAFE_MATCH_KEY_RE.fullmatch(candidate):
        return None
    return candidate[:120]


def _safe_aliases(value: Any, warnings: set[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.add("unsafe_string_sanitized")
        return []
    aliases: list[str] = []
    for raw in value[:_ALIAS_LIMIT]:
        alias = _safe_label(raw)
        if alias is None:
            warnings.add("unsafe_string_sanitized")
            continue
        if alias not in aliases:
            aliases.append(alias)
    if len(value) > _ALIAS_LIMIT:
        warnings.add("max_items_reached")
    return aliases


def _match_key(lecture_id: str | None, label: str | None) -> str | None:
    if not lecture_id or not label:
        return None
    return f"{lecture_id}::{label}"[:120]


def _normalize_id(value: str) -> str:
    normalized = re.sub(r"\s+", "_", value.strip().lower())
    normalized = re.sub(r"[^a-z0-9._-]+", "_", normalized)
    normalized = normalized.strip("._-")
    normalized = re.sub(r"[._-]{2,}", "_", normalized)
    return normalized[:80]


def _unsafe(value: str) -> bool:
    if not isinstance(value, str):
        return True
    stripped = value.strip()
    if not stripped:
        return True
    return bool(_UNSAFE_RE.search(stripped) or _BASE64ISH_RE.fullmatch(stripped))


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return value


def _number_or_none(value: Any) -> int | float | None:
    number = _finite_number(value)
    return number if number is not None else None


def _resolve_max_items(max_items: Any) -> int:
    if isinstance(max_items, bool):
        return _DEFAULT_MAX_ITEMS
    if isinstance(max_items, int):
        return max(0, max_items)
    return _DEFAULT_MAX_ITEMS


def _ordered(warnings: Any, order: tuple[str, ...]) -> list[str]:
    seen = set(warnings) if isinstance(warnings, (set, list, tuple)) else set()
    return [token for token in order if token in seen]
