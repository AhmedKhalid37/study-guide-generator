"""Quality Safety verifier-coupled leak scanner v1 (Slice 113).

Pure deterministic scanner for leak and uncertainty signals in candidate guide
Markdown. The scanner is intentionally unwired and offline: it reads only
caller-supplied text/reports, writes no artifacts, reads no source documents or
``clean.md``, calls no providers/models, and never returns raw matched text.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet

VERSION = 1
REPORT_KIND = "quality_safety_leak_report"
CONTEXT_KIND = "quality_safety_verification_context"

REPORT_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})
LEAK_KINDS = frozenset(
    {
        "reasoning_leak",
        "uncertainty_leak",
        "unresolved_answer",
        "placeholder_leak",
        "numeric_uncertainty",
        "structural_uncertainty",
    }
)
SEVERITIES = frozenset({"blocking", "warning", "info"})
VERIFICATION_STATUSES = frozenset(
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

WARNING_ORDER = (
    "candidate_markdown_missing",
    "malformed_candidate_degraded",
    "malformed_fact_sheet_degraded",
    "malformed_recompute_report_degraded",
    "malformed_canonical_report_degraded",
    "verification_context_missing",
    "unsafe_fact_token_dropped",
    "max_items_reached",
)

SUMMARY_KEYS = (
    "line_count",
    "leak_count",
    "blocking_leak_count",
    "warning_leak_count",
    "info_leak_count",
    "verified_recompute_leak_count",
    "failed_recompute_leak_count",
    "verified_canonical_leak_count",
    "failed_canonical_leak_count",
    "unverified_leak_count",
    "unknown_context_leak_count",
    "warning_count",
)

_DEFAULT_MAX_ITEMS = 200
_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_UNSAFE_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|/var/|\\\\|[A-Za-z]:\\|\.\./|/\.\.|"
    r"authorization|bearer|api[_-]?key|token|secret|data:|base64|provider payload|"
    r"ocr|caption|table text|uploaded[_ -]?quality|quality[_ -]?spec|evidence quote|"
    r"source text|raw text|guide snippet|source snippet|private|\.pdf|\.docx|\.zip|"
    r"\.png|\.jpg|\.jpeg|\.webp|\.socket|\.sock)",
    re.IGNORECASE,
)
_BASE64ISH_RE = re.compile(r"^[A-Za-z0-9+/]{80,}={0,2}$")
_LEAK_LEFT = r"(?<![A-Za-z0-9_])"
_LEAK_RIGHT = r"(?![A-Za-z0-9_])"

_FIXED_RULES: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "reasoning_leak",
        "wait_or_actually",
        "blocking",
        re.compile(_LEAK_LEFT + r"(?:wait|actually)" + _LEAK_RIGHT, re.IGNORECASE),
    ),
    (
        "uncertainty_leak",
        "unclear_or_trust",
        "contextual",
        re.compile(
            _LEAK_LEFT + r"(?:unclear|we(?:'|’)ll\s+trust|we\s+will\s+trust)" + _LEAK_RIGHT,
            re.IGNORECASE,
        ),
    ),
    (
        "uncertainty_leak",
        "speculative_inference",
        "contextual",
        re.compile(_LEAK_LEFT + r"(?:it\s+seems|let(?:'|’)s\s+infer)" + _LEAK_RIGHT, re.IGNORECASE),
    ),
    (
        "uncertainty_leak",
        "personal_uncertainty",
        "contextual",
        re.compile(
            _LEAK_LEFT
            + r"(?:i\s+think|presumably|probably|maybe|guess|not\s+sure|cannot\s+tell|hard\s+to\s+tell)"
            + _LEAK_RIGHT,
            re.IGNORECASE,
        ),
    ),
    (
        "uncertainty_leak",
        "unsafe_assumption",
        "contextual",
        re.compile(
            _LEAK_LEFT + r"(?:we\s+assume|assume\s+this\s+is|appears\s+to\s+be|likely\s+means)" + _LEAK_RIGHT,
            re.IGNORECASE,
        ),
    ),
)
_TODO_RE = re.compile(r"\b(?:TODO|TBD|FIXME)\b", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"\[(?:insert|fill|unknown)\b[^\]]{0,80}\]", re.IGNORECASE)
_EQUALS_QUESTION_RE = re.compile(r"(?:=|≈)\s*\?")
_ANSWER_MARKER_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:answer|final answer|solution)\s*:\s*$", re.IGNORECASE)
_QUESTION_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    r"(?:question\s*\d*|practice\s+question|mock\s+question|self[- ]?test|quiz|check[- ]?yourself)\b",
    re.IGNORECASE,
)
_SOURCE_REF_RE = re.compile(r"\b(?:source|page|slide|p\.|pp\.)\s*[:#]?\s*\d{1,4}\b", re.IGNORECASE)


def scan_quality_safety_leaks(
    candidate_markdown: Any,
    *,
    fact_sheet: Any = None,
    recompute_report: Any = None,
    canonical_report: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Scan candidate Markdown for leak signals; never raise."""
    return build_quality_safety_leak_report(
        candidate_markdown,
        fact_sheet=fact_sheet,
        recompute_report=recompute_report,
        canonical_report=canonical_report,
        max_items=max_items,
    )


def build_quality_safety_leak_report(
    candidate_markdown: Any,
    *,
    fact_sheet: Any = None,
    recompute_report: Any = None,
    canonical_report: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Build a safe JSON-serializable leak report; never raise."""
    try:
        return _build_report(
            candidate_markdown,
            fact_sheet=fact_sheet,
            recompute_report=recompute_report,
            canonical_report=canonical_report,
            max_items=max_items,
        )
    except Exception:
        warnings = {"malformed_candidate_degraded"}
        return _report("partial", [], warnings, line_count=0)


def extract_quality_safety_verification_context(
    fact_sheet: Any = None,
    recompute_report: Any = None,
    canonical_report: Any = None,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Return safe fact-id verification context; never include raw labels/text."""
    try:
        context, warnings = _verification_context(
            fact_sheet,
            recompute_report,
            canonical_report,
            max_items=max_items,
        )
        facts = [
            {"fact_id": fact_id, "verification_status": data["verification_status"]}
            for fact_id, data in sorted(context.items())
        ]
        return {
            "version": VERSION,
            "kind": CONTEXT_KIND,
            "facts": facts,
            "warnings": _ordered(warnings),
        }
    except Exception:
        return {
            "version": VERSION,
            "kind": CONTEXT_KIND,
            "facts": [],
            "warnings": ["malformed_fact_sheet_degraded"],
        }


def _build_report(
    candidate_markdown: Any,
    *,
    fact_sheet: Any,
    recompute_report: Any,
    canonical_report: Any,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()
    if candidate_markdown is None:
        warnings.add("candidate_markdown_missing")
        return _report("skipped", [], warnings, line_count=0)
    if not isinstance(candidate_markdown, str):
        warnings.add("malformed_candidate_degraded")
        return _report("skipped", [], warnings, line_count=0)

    context, context_warnings = _verification_context(
        fact_sheet,
        recompute_report,
        canonical_report,
        max_items=max_items,
    )
    warnings.update(context_warnings)

    lines = candidate_markdown.splitlines()
    cap = _resolve_max_items(max_items)
    leaks: list[dict[str, Any]] = []
    reached = False

    for line_index, line in enumerate(lines):
        if len(leaks) >= cap:
            reached = True
            break
        line_leaks = _scan_line(line, line_index, lines, context)
        for leak in line_leaks:
            if len(leaks) >= cap:
                reached = True
                break
            leaks.append(leak)

    if reached:
        warnings.add("max_items_reached")
    return _report(_status(leaks, warnings), leaks, warnings, line_count=len(lines))


def _scan_line(
    line: str,
    line_index: int,
    lines: list[str],
    context: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    attached_ids, status = _attach_context(line, context)

    for leak_kind, rule_id, severity_policy, pattern in _FIXED_RULES:
        if pattern.search(line):
            severity = _severity(leak_kind, severity_policy, status)
            leaks.append(_leak(leak_kind, rule_id, line_index, severity, status, attached_ids))

    if _EQUALS_QUESTION_RE.search(line):
        rule_id = "approx_question_mark" if "≈" in line else "numeric_equals_question_mark"
        leaks.append(_leak("numeric_uncertainty", rule_id, line_index, "blocking", status, attached_ids))

    if _TODO_RE.search(line):
        leaks.append(_leak("placeholder_leak", "todo_marker", line_index, "blocking", status, attached_ids))

    if _PLACEHOLDER_RE.search(line):
        leaks.append(_leak("placeholder_leak", "placeholder_bracket", line_index, "blocking", status, attached_ids))

    if _ANSWER_MARKER_RE.fullmatch(line) and not _has_substantive_answer(lines, line_index):
        leaks.append(_leak("unresolved_answer", "empty_answer_marker", line_index, "blocking", status, attached_ids))

    if _structural_question(line, lines, line_index):
        severity = "blocking" if _formula_or_numeric_context(line) else "warning"
        leaks.append(_leak("structural_uncertainty", "formula_question_mark", line_index, severity, status, attached_ids))

    return leaks


def _verification_context(
    fact_sheet: Any,
    recompute_report: Any,
    canonical_report: Any,
    *,
    max_items: Any,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    warnings: set[str] = set()
    context: dict[str, dict[str, Any]] = {}
    if fact_sheet is None:
        warnings.add("verification_context_missing")
    else:
        sheet = normalize_quality_safety_fact_sheet(fact_sheet, max_items=max_items)
        if "malformed_fact_sheet_degraded" in sheet.get("warnings", []):
            warnings.add("malformed_fact_sheet_degraded")
        if "unsafe_string_sanitized" in sheet.get("warnings", []):
            warnings.add("unsafe_fact_token_dropped")
        for fact in _iter_facts(sheet):
            fact_id = _safe_fact_id(fact.get("id"))
            if fact_id is None:
                warnings.add("unsafe_fact_token_dropped")
                continue
            labels = []
            label = _safe_label_token(fact.get("label"))
            if label is None:
                warnings.add("unsafe_fact_token_dropped")
            else:
                labels.append(label)
            fact_warnings = fact.get("warnings")
            if isinstance(fact_warnings, list) and any(
                token in fact_warnings
                for token in ("unsafe_string_sanitized", "invalid_fact_id", "invalid_source_ref")
            ):
                warnings.add("unsafe_fact_token_dropped")
            context[fact_id] = {
                "verification_status": "unknown",
                "tokens": tuple([fact_id] + labels),
            }

    if recompute_report is None and canonical_report is None:
        if fact_sheet is not None:
            warnings.add("verification_context_missing")
        return context, warnings

    recompute_statuses = _report_statuses(recompute_report, source="recompute", warnings=warnings)
    canonical_statuses = _report_statuses(canonical_report, source="canonical", warnings=warnings)
    for fact_id, status in canonical_statuses.items():
        context.setdefault(fact_id, {"verification_status": "unknown", "tokens": (fact_id,)})
        context[fact_id]["verification_status"] = status
    for fact_id, status in recompute_statuses.items():
        context.setdefault(fact_id, {"verification_status": "unknown", "tokens": (fact_id,)})
        current = context[fact_id].get("verification_status")
        if status in {"verified_recompute", "failed_recompute"} or current == "unknown":
            context[fact_id]["verification_status"] = status
    return context, warnings


def _report_statuses(report: Any, *, source: str, warnings: set[str]) -> dict[str, str]:
    if report is None:
        return {}
    if not isinstance(report, dict):
        warnings.add(
            "malformed_recompute_report_degraded"
            if source == "recompute"
            else "malformed_canonical_report_degraded"
        )
        return {}
    checks = report.get("checks")
    if not isinstance(checks, list):
        warnings.add(
            "malformed_recompute_report_degraded"
            if source == "recompute"
            else "malformed_canonical_report_degraded"
        )
        return {}
    statuses: dict[str, str] = {}
    for check in checks:
        if not isinstance(check, dict):
            continue
        fact_id = _safe_fact_id(check.get("fact_id"))
        if fact_id is None:
            warnings.add("unsafe_fact_token_dropped")
            continue
        if source == "recompute":
            status = _recompute_status(check)
        else:
            status = _canonical_status(check)
        if status != "unknown":
            statuses[fact_id] = status
    return statuses


def _recompute_status(check: dict[str, Any]) -> str:
    status = check.get("status")
    check_id = check.get("check_id")
    if status == "passed":
        return "verified_recompute"
    if status == "failed":
        return "failed_recompute"
    if check_id == "non_numeric_fact_not_applicable" or status == "not_applicable":
        return "not_applicable"
    if status in {"warning", "unknown"}:
        return "unverified"
    return "unknown"


def _canonical_status(check: dict[str, Any]) -> str:
    status = check.get("status")
    check_id = check.get("check_id")
    if check_id == "canonical_fixture_match" and status == "passed":
        return "verified_canonical"
    if check_id == "canonical_fixture_mismatch" and status == "failed":
        return "failed_canonical"
    if check_id == "canonical_fixture_not_applicable" or status == "not_applicable":
        return "not_applicable"
    if status in {"warning", "unknown"}:
        return "unverified"
    return "unknown"


def _attach_context(line: str, context: dict[str, dict[str, Any]]) -> tuple[list[str], str]:
    fact_ids: list[str] = []
    statuses: list[str] = []
    for fact_id, data in sorted(context.items()):
        tokens = data.get("tokens")
        if not isinstance(tokens, tuple):
            continue
        for token in tokens:
            if isinstance(token, str) and _contains_token(line, token):
                fact_ids.append(fact_id)
                status = data.get("verification_status")
                statuses.append(status if status in VERIFICATION_STATUSES else "unknown")
                break
    if not fact_ids:
        return [], "unknown"
    return fact_ids[:8], _dominant_status(statuses)


def _dominant_status(statuses: list[str]) -> str:
    for status in (
        "failed_recompute",
        "verified_recompute",
        "failed_canonical",
        "verified_canonical",
        "unverified",
        "not_applicable",
        "unknown",
    ):
        if status in statuses:
            return status
    return "unknown"


def _severity(leak_kind: str, policy: str, verification_status: str) -> str:
    if policy in SEVERITIES:
        return policy
    if leak_kind == "uncertainty_leak":
        if verification_status in {
            "verified_recompute",
            "failed_recompute",
            "verified_canonical",
            "failed_canonical",
            "unverified",
        }:
            return "blocking"
        return "warning"
    return "warning"


def _leak(
    leak_kind: str,
    rule_id: str,
    line_index: int,
    severity: str,
    verification_status: str,
    fact_ids: list[str],
) -> dict[str, Any]:
    return {
        "leak_kind": leak_kind if leak_kind in LEAK_KINDS else "structural_uncertainty",
        "rule_id": rule_id,
        "line_index": max(0, int(line_index)),
        "severity": severity if severity in SEVERITIES else "warning",
        "verification_status": (
            verification_status if verification_status in VERIFICATION_STATUSES else "unknown"
        ),
        "fact_ids": [fact_id for fact_id in fact_ids if _safe_fact_id(fact_id) is not None],
        "warnings": [],
    }


def _report(status: str, leaks: list[dict[str, Any]], warnings: set[str], *, line_count: int) -> dict[str, Any]:
    ordered_warnings = _ordered(warnings)
    return {
        "version": VERSION,
        "kind": REPORT_KIND,
        "status": status if status in REPORT_STATUSES else "warning",
        "blocking": any(leak.get("severity") == "blocking" for leak in leaks),
        "summary": _summary(leaks, ordered_warnings, line_count),
        "leaks": leaks,
        "blocking_failures": [_blocking_failure(leak) for leak in leaks if leak.get("severity") == "blocking"],
        "warnings": ordered_warnings,
    }


def _summary(leaks: list[dict[str, Any]], warnings: list[str], line_count: int) -> dict[str, int]:
    counts = {key: 0 for key in SUMMARY_KEYS}
    counts["line_count"] = max(0, int(line_count))
    counts["leak_count"] = max(0, len(leaks))
    counts["warning_count"] = max(0, len(warnings))
    for leak in leaks:
        severity = leak.get("severity")
        status = leak.get("verification_status")
        if severity == "blocking":
            counts["blocking_leak_count"] += 1
        elif severity == "warning":
            counts["warning_leak_count"] += 1
        elif severity == "info":
            counts["info_leak_count"] += 1
        if status == "verified_recompute":
            counts["verified_recompute_leak_count"] += 1
        elif status == "failed_recompute":
            counts["failed_recompute_leak_count"] += 1
        elif status == "verified_canonical":
            counts["verified_canonical_leak_count"] += 1
        elif status == "failed_canonical":
            counts["failed_canonical_leak_count"] += 1
        elif status == "unverified":
            counts["unverified_leak_count"] += 1
        else:
            counts["unknown_context_leak_count"] += 1
    return counts


def _blocking_failure(leak: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": "quality_safety_leak_scan",
        "leak_kind": leak.get("leak_kind") if leak.get("leak_kind") in LEAK_KINDS else "structural_uncertainty",
        "rule_id": leak.get("rule_id") if isinstance(leak.get("rule_id"), str) else "unknown_rule",
        "verification_status": (
            leak.get("verification_status") if leak.get("verification_status") in VERIFICATION_STATUSES else "unknown"
        ),
        "fact_ids": leak.get("fact_ids") if isinstance(leak.get("fact_ids"), list) else [],
        "severity": "blocking",
    }


def _status(leaks: list[dict[str, Any]], warnings: set[str]) -> str:
    if any(leak.get("severity") == "blocking" for leak in leaks):
        return "failed"
    if "max_items_reached" in warnings:
        return "partial"
    if any(leak.get("severity") == "warning" for leak in leaks):
        return "warning"
    return "passed"


def _structural_question(line: str, lines: list[str], line_index: int) -> bool:
    if "?" not in line or _EQUALS_QUESTION_RE.search(line):
        return False
    stripped = line.strip()
    if not stripped:
        return False
    if _QUESTION_HEADING_RE.match(stripped):
        return False
    if _SOURCE_REF_RE.search(stripped):
        return False
    heading_text = re.sub(r"^\s*#{1,6}\s*", "", stripped).strip()
    if heading_text.lower() == "why?" and _next_committed(lines, line_index):
        return False
    if heading_text.rstrip(":").lower() == "assumption":
        return False
    return _formula_or_numeric_context(stripped)


def _formula_or_numeric_context(line: str) -> bool:
    return bool(re.search(r"\d", line) or re.search(r"[=≈+\-*/^]", line))


def _next_committed(lines: list[str], line_index: int) -> bool:
    for next_line in lines[line_index + 1 : line_index + 4]:
        stripped = next_line.strip()
        if not stripped:
            continue
        if _TODO_RE.search(stripped) or _PLACEHOLDER_RE.search(stripped) or _EQUALS_QUESTION_RE.search(stripped):
            return False
        return True
    return False


def _has_substantive_answer(lines: list[str], line_index: int) -> bool:
    for next_line in lines[line_index + 1 : line_index + 4]:
        stripped = next_line.strip()
        if not stripped:
            return False
        if _ANSWER_MARKER_RE.fullmatch(stripped):
            return False
        if _TODO_RE.search(stripped) or _PLACEHOLDER_RE.search(stripped) or _EQUALS_QUESTION_RE.search(stripped):
            return False
        return True
    return False


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


def _safe_fact_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = _normalize_id(value)
    if not candidate or _unsafe(candidate) or not _SAFE_ID_RE.fullmatch(candidate):
        return None
    return candidate


def _safe_label_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or _unsafe(candidate):
        return None
    candidate = re.sub(r"[^A-Za-z0-9_.:-]+", "_", candidate).strip("_.:-")
    if not candidate or not _SAFE_TOKEN_RE.fullmatch(candidate):
        return None
    return candidate[:80]


def _contains_token(line: str, token: str) -> bool:
    if not token:
        return False
    return bool(re.search(r"(?<![A-Za-z0-9_.:-])" + re.escape(token) + r"(?![A-Za-z0-9_.:-])", line))


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


def _resolve_max_items(max_items: Any) -> int:
    if isinstance(max_items, bool):
        return _DEFAULT_MAX_ITEMS
    if isinstance(max_items, int):
        return max(0, max_items)
    return _DEFAULT_MAX_ITEMS


def _ordered(warnings: Any) -> list[str]:
    seen = set(warnings) if isinstance(warnings, (set, list, tuple)) else set()
    return [token for token in WARNING_ORDER if token in seen]
