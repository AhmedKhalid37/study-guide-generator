"""Deterministic guide-quality contract **lint** (Slice 102).

A companion to ``guide_quality_prompt_contract``: after a guide is generated, scan
the final ``clean.md`` for *safe COUNTS ONLY* to report whether the output appears
to honour the quality contract — reasoning leaks, required structure, exam-alert
flags, reference tables, and (shallow, deferred) worked-example / arithmetic /
consistency signals.

**Flag-only, never auto-reject.** This v1 only summarises; it never rewrites,
regenerates, rejects, or fails the job. The motivating spec allows reject+regenerate
*or* flag; flag-only is the safe choice for a first cut.

No-leak contract (critical)
---------------------------
The report stores **only**: a closed status token, ints, bools, a fixed closed
``kind`` per check, fixed instruction strings, and closed warning tokens. It NEVER
stores or echoes: a matched/leaked phrase, source text, a heading's text, a table's
contents, a formula, an example, a number from the guide, a filename, path, source
title, caption, OCR text, image/asset ref, image byte, base64 / data URI, provider
payload, token, URL, argv, socket path, model path, or a raw exception string. The
banned-phrase signatures live in code as generic English words; the report records
how MANY were seen, never which text matched.

Purity & safety
---------------
stdlib-only. Pure / total: it reads the passed Markdown string, computes counts, and
returns a sanitized dict. It calls no LLM/provider/model/cloud, inspects no
PDF/image, OCRs nothing, reconstructs no table, renders/exports nothing, and never
raises — any malformed input or unexpected error degrades to a safe report.
"""
from __future__ import annotations

import re
from typing import Any

REPORT_VERSION = 1
REPORT_KIND = "guide_quality_contract_lint"

# --- Closed warning vocabulary -----------------------------------------------
EMPTY_MARKDOWN = "empty_markdown"
REASONING_LEAK_PRESENT = "reasoning_leak_present"
REQUIRED_SECTIONS_MISSING = "required_sections_missing"
EXAM_ALERTS_ABSENT = "exam_alerts_absent"
REFERENCE_TABLES_ABSENT = "reference_tables_absent"
MAX_ITEMS_APPLIED = "max_items_applied"

WARNING_ORDER = [
    EMPTY_MARKDOWN,
    REASONING_LEAK_PRESENT,
    REQUIRED_SECTIONS_MISSING,
    EXAM_ALERTS_ABSENT,
    REFERENCE_TABLES_ABSENT,
    MAX_ITEMS_APPLIED,
]

# --- Reasoning-leak signatures (generic English; not source content) ---------
# Matched case-insensitively as substrings. Each hit increments a COUNT only; the
# matched text is never stored. "?" is deliberately NOT scanned here: legitimate
# mock-exam / self-test questions use it, so a question-mark heuristic would be
# noisy. Phrase signatures are robust and deterministic.
_LEAK_SIGNATURES: tuple[str, ...] = (
    "actually,",
    "actually ",
    "it seems",
    "i think",
    "let's infer",
    "lets infer",
    "is confusing",
    "a bit confusing",
    "is unclear",
    "i'm not sure",
    "im not sure",
    "presumably",
    "the slide is",
)

# --- Required-section aliases (comprehensive guides) -------------------------
# Each required section is matched if ANY of its alias substrings appears in a
# Markdown heading line (case-insensitive). Aliases are intentionally permissive so
# a style phrasing the heading slightly differently still counts.
_REQUIRED_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("how_to_use", ("how to use",)),
    ("big_picture", ("big picture", "the big picture")),
    ("notation", ("notation", "terms you must know", "key terms", "glossary")),
    ("formula_sheet", ("formula sheet", "formulas at a glance")),
    ("definitions_cheat", ("definitions cheat", "definition cheat", "definitions reference")),
    ("common_mistakes", ("common mistakes", "mistakes that lose", "marks you lose")),
    ("consolidation", ("consolidation", "pipeline", "putting it together", "end-to-end", "end to end")),
    ("mock_exam", ("mock exam", "practice exam", "practice questions", "exam questions")),
    ("cram_sheet", ("cram sheet", "last-minute", "last minute", "quick recap")),
    ("self_test", ("self-test", "self test", "can i", "checklist")),
)

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S", re.MULTILINE)
# A Markdown table separator row: a line of only |, -, :, and spaces with at least
# one dash group, e.g. "| --- | :--: |". Counts as one table.
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$", re.MULTILINE)
_EXAM_ALERT_RE = re.compile(r"exam alert|⚠️", re.IGNORECASE)
# Shallow "steps shown" signal: a line with two or more '=' separating numbers
# (e.g. substitution then result). Informational only — never proves correctness.
_MULTI_STEP_RE = re.compile(r"\d.*=.*=.*\d")
_EXAMPLE_RE = re.compile(r"\bexamples?\b|worked example", re.IGNORECASE)


# =============================================================================
# Public API
# =============================================================================


def build_guide_quality_contract_lint_report(
    clean_markdown: str | None,
    *,
    comprehensive: bool = False,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: generated Markdown -> sanitized contract-lint report.

    Returns a dict with ``version``, ``kind``, ``status``
    (``completed``/``skipped``/``partial``), ``summary`` (safe counts), ``checks``
    (closed-kind per-check summaries), and ``warnings`` (closed tokens). ``max_items``
    optionally caps how many checks are emitted (defensive). Flag-only — it never
    rejects/regenerates and never fails a job. Pure and total: never raises; a
    missing/empty/non-string ``clean_markdown`` degrades to a safe ``skipped`` report.
    """
    try:
        return _build(clean_markdown, bool(comprehensive), max_items)
    except Exception:
        return _skipped(bool(comprehensive), reason_warning=None)


# =============================================================================
# Builder
# =============================================================================


def _build(clean_markdown: Any, comprehensive: bool, max_items: Any) -> dict[str, Any]:
    if not isinstance(clean_markdown, str) or not clean_markdown.strip():
        return _skipped(comprehensive, reason_warning=EMPTY_MARKDOWN)

    text = clean_markdown
    lowered = text.lower()
    warnings: set[str] = set()

    # 1. Reasoning leak — count banned signatures (never store the matched text).
    leak_count = sum(lowered.count(sig) for sig in _LEAK_SIGNATURES)

    # 2. Required structure — heading alias matching (comprehensive only).
    heading_lines = [line for line in text.splitlines() if _HEADING_RE.match(line)]
    headings_lc = [line.lower() for line in heading_lines]
    required_total = len(_REQUIRED_SECTIONS) if comprehensive else 0
    present = 0
    if comprehensive:
        for _key, aliases in _REQUIRED_SECTIONS:
            if any(any(alias in h for alias in aliases) for h in headings_lc):
                present += 1

    # 3. Exam alerts — count callout LINES (so "⚠️ EXAM ALERT" on one line is one,
    # not two, since the regex would otherwise match both markers).
    exam_alert_count = sum(1 for line in text.splitlines() if _EXAM_ALERT_RE.search(line))

    # 4. Reference tables.
    table_count = len(_TABLE_SEPARATOR_RE.findall(text))

    # 5/6/7. Shallow informational signals (deep verification deferred).
    example_count = len(_EXAMPLE_RE.findall(text))
    multi_step_count = len(_MULTI_STEP_RE.findall(text))

    checks: list[dict[str, Any]] = []

    checks.append(
        _check(
            "reasoning_leak",
            status="warning" if leak_count > 0 else "passed",
            observed=leak_count,
            expected=0,
            instruction=(
                "Counts hedging/uncertainty signatures in explanatory prose. The "
                "guide should read as settled fact; any hit is flagged (the matched "
                "text is never stored)."
            ),
        )
    )
    if leak_count > 0:
        warnings.add(REASONING_LEAK_PRESENT)

    if comprehensive:
        struct_status = "warning" if present < required_total else "passed"
        checks.append(
            _check(
                "required_structure",
                status=struct_status,
                observed=present,
                expected=required_total,
                instruction=(
                    "Checks the mandatory comprehensive-guide sections by heading "
                    "alias. Missing sections are flagged; headings' text is never "
                    "stored."
                ),
            )
        )
        if present < required_total:
            warnings.add(REQUIRED_SECTIONS_MISSING)

        alert_status = "warning" if exam_alert_count == 0 else "passed"
        if exam_alert_count == 0:
            warnings.add(EXAM_ALERTS_ABSENT)
        table_status = "warning" if table_count == 0 else "passed"
        if table_count == 0:
            warnings.add(REFERENCE_TABLES_ABSENT)
    else:
        checks.append(
            _check(
                "required_structure",
                status="not_applicable",
                observed=0,
                expected=0,
                instruction=(
                    "Full structural contract applies only to comprehensive/long "
                    "guides; not evaluated for this request."
                ),
            )
        )
        alert_status = "passed" if exam_alert_count > 0 else "not_applicable"
        table_status = "passed" if table_count > 0 else "not_applicable"

    checks.append(
        _check(
            "exam_alerts",
            status=alert_status,
            observed=exam_alert_count,
            expected=1 if comprehensive else 0,
            instruction="Counts exam-alert flags marking high-yield, easily-missed points.",
        )
    )
    checks.append(
        _check(
            "reference_tables",
            status=table_status,
            observed=table_count,
            expected=1 if comprehensive else 0,
            instruction="Counts Markdown tables (reference data should live in labelled tables).",
        )
    )
    checks.append(
        _check(
            "worked_examples",
            status="unknown",
            observed=example_count,
            expected=0,
            instruction=(
                "Counts example mentions only; deep completeness (all parallel "
                "outputs computed to a final decision) is deferred."
            ),
        )
    )
    checks.append(
        _check(
            "arithmetic_steps",
            status="unknown",
            observed=multi_step_count,
            expected=0,
            instruction=(
                "Counts multi-step arithmetic lines as a proxy for shown working; "
                "rigorous arithmetic verification is left to the existing math "
                "verifier and is deferred here."
            ),
        )
    )
    checks.append(
        _check(
            "consistency",
            status="not_applicable",
            observed=0,
            expected=0,
            instruction=(
                "Deep numeric self-consistency (a label appearing with two values) "
                "is deferred; it is not evaluated here, and no value is ever stored."
            ),
        )
    )

    # Defensive cap on emitted checks (never a product limit).
    status = "completed"
    if isinstance(max_items, int) and not isinstance(max_items, bool) and 0 <= max_items < len(checks):
        checks = checks[:max_items]
        warnings.add(MAX_ITEMS_APPLIED)
        status = "partial"

    # Assign stable, positional ids now that the final check set is fixed.
    for index, check in enumerate(checks, start=1):
        check["check_id"] = f"guide_quality_contract_check_{index:04d}"

    warning_status_count = sum(1 for c in checks if c.get("status") == "warning")

    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": status,
        "summary": {
            "comprehensive": comprehensive,
            "reasoning_leak_count": leak_count,
            "required_section_count": required_total,
            "required_section_present_count": present,
            "exam_alert_count": exam_alert_count,
            "table_count": table_count,
            "warning_count": warning_status_count,
        },
        "checks": checks,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


# =============================================================================
# Assembly
# =============================================================================


_CHECK_KINDS = frozenset(
    {
        "reasoning_leak",
        "required_structure",
        "exam_alerts",
        "reference_tables",
        "worked_examples",
        "arithmetic_steps",
        "consistency",
    }
)
_CHECK_STATUSES = frozenset({"passed", "warning", "not_applicable", "unknown"})

# Per-check ``check_id`` is assigned positionally in ``_build`` once the final check
# set is fixed (after any max_items truncation), so the sequence is deterministic.
def _check(kind: str, *, status: str, observed: int, expected: int, instruction: str) -> dict[str, Any]:
    safe_kind = kind if kind in _CHECK_KINDS else "consistency"
    safe_status = status if status in _CHECK_STATUSES else "unknown"
    return {
        "check_id": None,  # assigned positionally in _build
        "kind": safe_kind,
        "status": safe_status,
        "observed_count": int(observed) if isinstance(observed, int) and not isinstance(observed, bool) else 0,
        "expected_count": int(expected) if isinstance(expected, int) and not isinstance(expected, bool) else 0,
        "instruction": str(instruction),
        "warnings": [],
    }


def _skipped(comprehensive: bool, *, reason_warning: str | None) -> dict[str, Any]:
    warnings = [reason_warning] if reason_warning in WARNING_ORDER else []
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": "skipped",
        "summary": {
            "comprehensive": bool(comprehensive),
            "reasoning_leak_count": 0,
            "required_section_count": 0,
            "required_section_present_count": 0,
            "exam_alert_count": 0,
            "table_count": 0,
            "warning_count": 0,
        },
        "checks": [],
        "warnings": warnings,
    }
