"""Deterministic guide-quality **QA gate** v1 (Slice 103).

Slice 102 added the central guide-quality prompt contract and a flag-only
``guide_quality_contract_lint`` artifact. Slice 103 adds a higher-level
*advisory* QA gate that combines the already-sanitized quality signals — the
contract lint, the guide quality report v2, the source-coverage report, and the
existing numeric math-verification report — into one closed summary of whether a
generated guide appears to pass basic quality checks.

**Flag-only / advisory in v1.** The gate NEVER rejects, regenerates, blocks
render/export, or changes job status. ``blocking`` is always ``False``. Auto
reject+regenerate is intentionally deferred until the advisory gate is validated.

How math is handled
-------------------
The existing math verifier (``pipeline/math_verifier.py``) already runs and
writes ``math_verification.json``; this gate only **summarises** its existing
status/counts. It does NOT rerun verification, parse formulas from guide text, or
call any LLM. If no math artifact is present, the math check degrades to
``unknown``/``not_applicable`` with a closed warning.

No-leak contract (critical)
---------------------------
The gate consumes only already-sanitized input dicts and copies **no string**
out of them. It reads a fixed set of known **integer count** fields (coerced via
``_safe_int``) and a small set of **closed status tokens**; every ``instruction``
string in the output is a fixed in-module constant. Therefore it can never echo a
guide excerpt, phrase, heading, formula, number-as-value, table content, caption,
OCR text, filename, path, source title, image/asset ref, image byte, base64 /
data URI, provider payload, token, URL, argv, socket path, model path, or a raw
exception string — even if a hostile canary is injected into an input artifact.

Purity & safety
---------------
stdlib-only. Pure / total: it reads the passed dicts, computes counts, and returns
a sanitized dict. It imports nothing from ``pipeline`` and no provider / model /
OCR / renderer / FastAPI / frontend module, inspects no PDF/image, OCRs nothing,
reconstructs no table, renders/exports nothing, and never raises — any malformed
input or unexpected error degrades to a safe report.
"""
from __future__ import annotations

from typing import Any

GATE_VERSION = 1
GATE_KIND = "guide_quality_qa_gate"

# --- Closed warning vocabulary (this module owns what it emits) --------------
CONTRACT_LINT_MISSING = "contract_lint_missing"
QUALITY_REPORT_V2_MISSING = "quality_report_v2_missing"
SOURCE_COVERAGE_MISSING = "source_coverage_missing"
MATH_VERIFICATION_ARTIFACT_MISSING = "math_verification_artifact_missing"
REASONING_LEAK_PRESENT = "reasoning_leak_present"
REQUIRED_SECTIONS_MISSING = "required_sections_missing"
MATH_VERIFICATION_MISMATCH_PRESENT = "math_verification_mismatch_present"
SOURCE_COVERAGE_INCOMPLETE = "source_coverage_incomplete"
QUALITY_REPORT_WARNINGS_PRESENT = "quality_report_warnings_present"
ALL_SIGNALS_UNKNOWN = "all_signals_unknown"
MAX_ITEMS_APPLIED = "max_items_applied"

WARNING_ORDER = [
    CONTRACT_LINT_MISSING,
    QUALITY_REPORT_V2_MISSING,
    SOURCE_COVERAGE_MISSING,
    MATH_VERIFICATION_ARTIFACT_MISSING,
    REASONING_LEAK_PRESENT,
    REQUIRED_SECTIONS_MISSING,
    MATH_VERIFICATION_MISMATCH_PRESENT,
    SOURCE_COVERAGE_INCOMPLETE,
    QUALITY_REPORT_WARNINGS_PRESENT,
    ALL_SIGNALS_UNKNOWN,
    MAX_ITEMS_APPLIED,
]

# --- Closed token sets -------------------------------------------------------
_CHECK_KINDS = frozenset(
    {
        "reasoning_leak",
        "required_structure",
        "math_verification",
        "source_coverage",
        "quality_report_v2",
    }
)
_CHECK_STATUSES = frozenset({"passed", "warning", "unknown", "not_applicable"})
_GATE_STATUSES = frozenset({"passed", "warning", "skipped", "partial"})

# A "skipped" sibling artifact carries no usable signal.
_SKIPPED_TOKEN = "skipped"

# Source-coverage top-level statuses that indicate the source was not fully read.
_INCOMPLETE_COVERAGE_STATUSES = frozenset({"partial", "unreadable"})

# Defensive ceiling so a degenerate caller cannot ask for an unbounded report.
_MAX_ITEMS_CEILING = 64


# =============================================================================
# Public API
# =============================================================================


def build_guide_quality_qa_gate(
    *,
    guide_quality_contract_lint: dict | None = None,
    guide_quality_report_v2: dict | None = None,
    source_coverage_report: dict | None = None,
    math_verification: dict | None = None,
    math_validation: dict | None = None,
    comprehensive: bool = False,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: sanitized quality artifacts -> advisory QA-gate report.

    Returns a dict with ``version``, ``kind``, ``status``
    (``passed``/``warning``/``skipped``/``partial``), ``summary`` (closed counts +
    ``blocking`` which is always ``False``), ``checks`` (closed-kind per-check
    summaries), and ``warnings`` (closed tokens only). ``max_items`` optionally caps
    how many checks are emitted (defensive). Flag-only — it never rejects,
    regenerates, blocks render/export, or fails a job. Pure and total: never raises;
    any malformed input degrades to a safe ``skipped`` gate.
    """
    try:
        return _build(
            guide_quality_contract_lint,
            guide_quality_report_v2,
            source_coverage_report,
            math_verification,
            math_validation,
            bool(comprehensive),
            max_items,
        )
    except Exception:
        return _skipped(bool(comprehensive))


# =============================================================================
# Builder
# =============================================================================


def _build(
    contract_lint: Any,
    quality_report_v2: Any,
    source_coverage: Any,
    math_verification: Any,
    math_validation: Any,
    comprehensive: bool,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()
    checks: list[dict[str, Any]] = []

    checks.append(_reasoning_leak_check(contract_lint, warnings))
    checks.append(_required_structure_check(contract_lint, comprehensive, warnings))
    checks.append(_math_verification_check(math_verification, math_validation, warnings))
    checks.append(_source_coverage_check(source_coverage, warnings))
    checks.append(_quality_report_v2_check(quality_report_v2, warnings))

    # Defensive cap on emitted checks (never a product limit).
    truncated = False
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        cap = max(0, min(max_items, _MAX_ITEMS_CEILING))
        if cap < len(checks):
            checks = checks[:cap]
            truncated = True
            warnings.add(MAX_ITEMS_APPLIED)

    # Assign stable, positional ids now that the final check set is fixed.
    for index, check in enumerate(checks, start=1):
        check["check_id"] = f"guide_quality_gate_check_{index:04d}"

    passed_count = sum(1 for c in checks if c["status"] == "passed")
    warning_count = sum(1 for c in checks if c["status"] == "warning")
    # "unknown" and "not_applicable" both mean "no positive signal" for the rollup.
    unknown_count = sum(
        1 for c in checks if c["status"] in {"unknown", "not_applicable"}
    )

    status = _roll_up_status(
        check_count=len(checks),
        passed_count=passed_count,
        warning_count=warning_count,
        truncated=truncated,
    )
    if status == "skipped" and checks:
        warnings.add(ALL_SIGNALS_UNKNOWN)

    return {
        "version": GATE_VERSION,
        "kind": GATE_KIND,
        "status": status,
        "summary": {
            "comprehensive": bool(comprehensive),
            "check_count": len(checks),
            "passed_count": passed_count,
            "warning_count": warning_count,
            "unknown_count": unknown_count,
            "blocking": False,
        },
        "checks": checks,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _roll_up_status(
    *, check_count: int, passed_count: int, warning_count: int, truncated: bool
) -> str:
    if check_count == 0:
        return "skipped"
    if warning_count > 0:
        return "warning"
    if passed_count == 0:
        # Only unknown / not_applicable checks — no usable signal.
        return "skipped"
    if truncated:
        return "partial"
    return "passed"


# =============================================================================
# Individual checks (each reads only known integer fields + closed tokens)
# =============================================================================


def _reasoning_leak_check(contract_lint: Any, warnings: set[str]) -> dict[str, Any]:
    summary = _usable_summary(contract_lint)
    if summary is None:
        warnings.add(CONTRACT_LINT_MISSING)
        return _check(
            "reasoning_leak",
            status="unknown",
            observed=0,
            expected=0,
            instruction=_INSTR_REASONING_LEAK_UNKNOWN,
        )
    leak_count = _safe_int(summary.get("reasoning_leak_count")) or 0
    if leak_count > 0:
        warnings.add(REASONING_LEAK_PRESENT)
    return _check(
        "reasoning_leak",
        status="warning" if leak_count > 0 else "passed",
        observed=leak_count,
        expected=0,
        instruction=_INSTR_REASONING_LEAK,
    )


def _required_structure_check(
    contract_lint: Any, comprehensive: bool, warnings: set[str]
) -> dict[str, Any]:
    if not comprehensive:
        return _check(
            "required_structure",
            status="not_applicable",
            observed=0,
            expected=0,
            instruction=_INSTR_REQUIRED_STRUCTURE_NA,
        )
    summary = _usable_summary(contract_lint)
    if summary is None:
        warnings.add(CONTRACT_LINT_MISSING)
        return _check(
            "required_structure",
            status="unknown",
            observed=0,
            expected=0,
            instruction=_INSTR_REQUIRED_STRUCTURE_UNKNOWN,
        )
    present = _safe_int(summary.get("required_section_present_count")) or 0
    expected = _safe_int(summary.get("required_section_count")) or 0
    if expected > 0 and present < expected:
        warnings.add(REQUIRED_SECTIONS_MISSING)
        status = "warning"
    elif expected <= 0:
        # Comprehensive requested but the lint recorded no required-section total
        # (e.g. it ran non-comprehensive); treat as no usable signal.
        status = "unknown"
    else:
        status = "passed"
    return _check(
        "required_structure",
        status=status,
        observed=present,
        expected=expected,
        instruction=_INSTR_REQUIRED_STRUCTURE,
    )


def _math_verification_check(
    math_verification: Any, math_validation: Any, warnings: set[str]
) -> dict[str, Any]:
    summary = _math_summary(math_verification)
    if summary is None:
        # No numeric verification artifact. Fall back to a presence-only signal
        # from the KaTeX render validation if it clearly indicates a problem;
        # otherwise unknown. Never copies any string out of either artifact.
        warnings.add(MATH_VERIFICATION_ARTIFACT_MISSING)
        if _math_validation_has_problem(math_validation):
            warnings.add(MATH_VERIFICATION_MISMATCH_PRESENT)
            return _check(
                "math_verification",
                status="warning",
                observed=0,
                expected=0,
                instruction=_INSTR_MATH_FALLBACK_WARNING,
            )
        return _check(
            "math_verification",
            status="unknown",
            observed=0,
            expected=0,
            instruction=_INSTR_MATH_UNKNOWN,
        )
    total = _safe_int(summary.get("total")) or 0
    mismatch = _safe_int(summary.get("mismatch")) or 0
    if mismatch > 0:
        warnings.add(MATH_VERIFICATION_MISMATCH_PRESENT)
        status = "warning"
    elif total <= 0:
        status = "not_applicable"
    else:
        status = "passed"
    return _check(
        "math_verification",
        status=status,
        observed=mismatch,
        expected=0,
        instruction=_INSTR_MATH,
    )


def _source_coverage_check(source_coverage: Any, warnings: set[str]) -> dict[str, Any]:
    if not _is_usable_artifact(source_coverage):
        warnings.add(SOURCE_COVERAGE_MISSING)
        return _check(
            "source_coverage",
            status="unknown",
            observed=0,
            expected=0,
            instruction=_INSTR_SOURCE_COVERAGE_UNKNOWN,
        )
    summary = source_coverage.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    top_status = _token(source_coverage.get("status"))
    unreadable_pages = _safe_int(summary.get("empty_or_unreadable_pages")) or 0
    unreadable_sources = _safe_int(summary.get("unreadable_source_count")) or 0
    incomplete = (
        top_status in _INCOMPLETE_COVERAGE_STATUSES
        or unreadable_pages > 0
        or unreadable_sources > 0
    )
    if incomplete:
        warnings.add(SOURCE_COVERAGE_INCOMPLETE)
    return _check(
        "source_coverage",
        status="warning" if incomplete else "passed",
        observed=unreadable_pages,
        expected=0,
        instruction=_INSTR_SOURCE_COVERAGE,
    )


def _quality_report_v2_check(quality_report_v2: Any, warnings: set[str]) -> dict[str, Any]:
    summary = _usable_summary(quality_report_v2)
    if summary is None:
        warnings.add(QUALITY_REPORT_V2_MISSING)
        return _check(
            "quality_report_v2",
            status="unknown",
            observed=0,
            expected=0,
            instruction=_INSTR_QUALITY_V2_UNKNOWN,
        )
    report_warnings = _safe_int(summary.get("warning_count")) or 0
    if report_warnings > 0:
        warnings.add(QUALITY_REPORT_WARNINGS_PRESENT)
    return _check(
        "quality_report_v2",
        status="warning" if report_warnings > 0 else "passed",
        observed=report_warnings,
        expected=0,
        instruction=_INSTR_QUALITY_V2,
    )


# =============================================================================
# Input readers (never copy a string out of an input artifact)
# =============================================================================


def _is_usable_artifact(artifact: Any) -> bool:
    """True when ``artifact`` is a dict that did not degrade to ``skipped``."""
    if not isinstance(artifact, dict):
        return False
    if _token(artifact.get("status")) == _SKIPPED_TOKEN:
        return False
    return True


def _usable_summary(artifact: Any) -> dict | None:
    """Return the ``summary`` dict of a usable sibling artifact, else ``None``."""
    if not _is_usable_artifact(artifact):
        return None
    summary = artifact.get("summary")
    return summary if isinstance(summary, dict) else None


def _math_summary(math_verification: Any) -> dict | None:
    """Return the inner ``report.summary`` of a usable math-verification artifact.

    ``math_verification.json`` wraps the verifier report under a ``report`` key with
    a top-level ``status``. A missing/skipped/malformed artifact returns ``None``.
    """
    if not _is_usable_artifact(math_verification):
        return None
    report = math_verification.get("report")
    if not isinstance(report, dict):
        return None
    summary = report.get("summary")
    return summary if isinstance(summary, dict) else None


def _math_validation_has_problem(math_validation: Any) -> bool:
    """Presence-only fallback: does the KaTeX validation clearly flag a problem?

    Reads only a small set of well-known boolean/int fields; never copies a string.
    Conservative — returns ``True`` only on an explicit failure signal.
    """
    if not isinstance(math_validation, dict):
        return False
    for ok_key in ("ok", "valid"):
        value = math_validation.get(ok_key)
        if value is False:
            return True
    summary = math_validation.get("summary")
    summary = summary if isinstance(summary, dict) else math_validation
    for err_key in ("error_count", "invalid_count", "errors", "mismatch"):
        count = _safe_int(summary.get(err_key)) if isinstance(summary, dict) else None
        if count is not None and count > 0:
            return True
    return False


# =============================================================================
# Assembly
# =============================================================================


def _check(
    kind: str, *, status: str, observed: int, expected: int, instruction: str
) -> dict[str, Any]:
    safe_kind = kind if kind in _CHECK_KINDS else "quality_report_v2"
    safe_status = status if status in _CHECK_STATUSES else "unknown"
    return {
        "check_id": None,  # assigned positionally in _build
        "kind": safe_kind,
        "status": safe_status,
        "observed_count": observed if isinstance(observed, int) and not isinstance(observed, bool) else 0,
        "expected_count": expected if isinstance(expected, int) and not isinstance(expected, bool) else 0,
        "instruction": str(instruction),
        "warnings": [],
    }


def _safe_int(value: Any) -> int | None:
    """Return ``value`` as an int only when it already is a non-bool int, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _token(value: Any) -> str:
    """Lower-cased stripped string for a scalar token; '' for anything else."""
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def _skipped(comprehensive: bool) -> dict[str, Any]:
    return {
        "version": GATE_VERSION,
        "kind": GATE_KIND,
        "status": "skipped",
        "summary": {
            "comprehensive": bool(comprehensive),
            "check_count": 0,
            "passed_count": 0,
            "warning_count": 0,
            "unknown_count": 0,
            "blocking": False,
        },
        "checks": [],
        "warnings": [],
    }


# --- Fixed instruction strings (constants; never derived from input) ---------
_INSTR_REASONING_LEAK = (
    "Summarises the contract lint's reasoning-leak signature count. The guide "
    "should read as settled fact; any hit is flagged. No matched text is stored."
)
_INSTR_REASONING_LEAK_UNKNOWN = (
    "Reasoning-leak signal unavailable: the guide-quality contract lint artifact "
    "was missing or skipped."
)
_INSTR_REQUIRED_STRUCTURE = (
    "Summarises the contract lint's required-section presence for comprehensive "
    "guides; missing mandatory sections are flagged. No heading text is stored."
)
_INSTR_REQUIRED_STRUCTURE_NA = (
    "Required-structure check applies only to comprehensive/long guides; not "
    "evaluated for this request."
)
_INSTR_REQUIRED_STRUCTURE_UNKNOWN = (
    "Required-structure signal unavailable: the guide-quality contract lint "
    "artifact was missing or skipped."
)
_INSTR_MATH = (
    "Summarises the existing numeric math-verification report's mismatch count; a "
    "non-zero mismatch is flagged. Verification is not rerun and no formula or "
    "value is stored."
)
_INSTR_MATH_UNKNOWN = (
    "Math-verification signal unavailable: the math_verification artifact was "
    "missing or skipped. Verification is not rerun here."
)
_INSTR_MATH_FALLBACK_WARNING = (
    "Numeric math-verification artifact missing; the KaTeX render validation "
    "indicates a math problem. No formula, value, or raw error is stored."
)
_INSTR_SOURCE_COVERAGE = (
    "Summarises the source-coverage report: empty/unreadable pages or a "
    "partial/unreadable source are flagged. No source text is stored."
)
_INSTR_SOURCE_COVERAGE_UNKNOWN = (
    "Source-coverage signal unavailable: the source_coverage_report artifact was "
    "missing or skipped."
)
_INSTR_QUALITY_V2 = (
    "Summarises the guide quality report v2 warning count; a non-zero count is "
    "flagged. No excerpt or value is stored."
)
_INSTR_QUALITY_V2_UNKNOWN = (
    "Guide quality report v2 signal unavailable: the artifact was missing or "
    "skipped."
)
