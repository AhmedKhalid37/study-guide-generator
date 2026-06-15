"""Sanitized **guide quality report v2** builder (Slice 96).

Full Material Coverage capstone follow-up. Slices 82–95 layered a set of already-
sanitized coverage signals onto every generation (material page selections, source
coverage, the full non-table visual inclusion plan, table candidate/policy context,
missing-material guidance, and the Slice 95 coverage-aware generation guidance).
Slice 96 adds the matching *measurement*: after a guide is generated, a deterministic
report that honestly summarises whether the generated ``clean.md`` appears to reflect
those signals.

Product goal (did the guide use the material it was told to use?)
-----------------------------------------------------------------
``After a guide is generated, write a sanitized guide_quality_report_v2.json that
summarises source/page/visual/table/missing-material usage signals from the
generated clean.md and the already-sanitized coverage artifacts.``

This is **not** a semantic evaluator and does not prove correctness. It is an honest,
deterministic *signal* report: it counts safe page-grounded signals, safe Markdown
image refs of the fixed shape ``assets/<slug>.png``, and a small closed set of static
app-authored guidance phrases, and compares those counts against the aggregate counts
already present in the sanitized coverage artifacts. Where an expected signal is not
observed it raises a closed warning rather than asserting a failure.

Scope (Slice 96 = report/artifact only)
---------------------------------------
Pure derivation only. It does NOT call an LLM, change prompts, change extraction/OCR,
inspect PDFs/images, read image bytes, reconstruct a table, extract table text, add UI,
change render/export, change figure-insertion semantics, change material page selection,
change visual-manifest filtering, or call any provider / model / VLM / Chandra / Mistral
/ Gemini / cloud. It scans only the already-generated ``clean.md`` string and the
already-sanitized artifact/context dicts, and returns a sanitized report dict.

Purity & safety
---------------
stdlib-only (imports nothing from ``pipeline`` and no provider/model/OCR/renderer/
FastAPI/frontend module). ``clean.md`` MAY be scanned, but **no excerpt is ever
persisted**: the markdown is read for *counts only*. The report emits **only** closed
tokens, ints, ``None``, bools, fixed instruction strings built from those, and a safe
generated ``check_id`` of the fixed shape ``guide_quality_check_NNNN``. No filename,
path, source title, caption, document / OCR / table text, raw image ref, raw asset ref,
asset id, image byte, base64 / data URI, provider payload, token, URL, argv, socket
path, model path, or raw exception string can survive into it. Never raises; any
malformed input degrades to a safe ``skipped`` / ``partial`` report.
"""
from __future__ import annotations

import re
from typing import Any

REPORT_VERSION = 2
REPORT_KIND = "guide_quality_report"

# --- Closed check kinds (this module owns what it emits) ---------------------
KIND_SOURCE_PAGES = "source_pages"
KIND_VISUALS = "visuals"
KIND_TABLES = "tables"
KIND_MISSING_MATERIAL = "missing_material"
KIND_COVERAGE = "coverage"

# Deterministic emission order of the closed checks.
_CHECK_ORDER = (
    KIND_SOURCE_PAGES,
    KIND_VISUALS,
    KIND_TABLES,
    KIND_MISSING_MATERIAL,
    KIND_COVERAGE,
)

# --- Closed check-status vocabulary ------------------------------------------
STATUS_PASSED = "passed"
STATUS_WARNING = "warning"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_UNKNOWN = "unknown"

# --- Closed warning vocabulary (this module owns what it emits) --------------
GUIDE_MISSING = "guide_missing"
SOURCE_COVERAGE_MALFORMED = "source_coverage_malformed"
VISUAL_PLAN_MALFORMED = "visual_plan_malformed"
TABLE_MANIFEST_MALFORMED = "table_manifest_malformed"
TABLE_POLICY_MALFORMED = "table_policy_malformed"
MISSING_MATERIAL_MALFORMED = "missing_material_malformed"
COVERAGE_CONTEXT_MALFORMED = "coverage_context_malformed"
SOURCE_PAGE_SIGNAL_MISSING = "source_page_signal_missing"
VISUAL_SIGNAL_MISSING = "visual_signal_missing"
TABLE_SIGNAL_MISSING = "table_signal_missing"
MISSING_MATERIAL_SIGNAL_MISSING = "missing_material_signal_missing"
COVERAGE_SIGNAL_MISSING = "coverage_signal_missing"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic emitted warning ordering (closed tokens only, never raw text).
WARNING_ORDER = [
    GUIDE_MISSING,
    SOURCE_COVERAGE_MALFORMED,
    VISUAL_PLAN_MALFORMED,
    TABLE_MANIFEST_MALFORMED,
    TABLE_POLICY_MALFORMED,
    MISSING_MATERIAL_MALFORMED,
    COVERAGE_CONTEXT_MALFORMED,
    SOURCE_PAGE_SIGNAL_MISSING,
    VISUAL_SIGNAL_MISSING,
    TABLE_SIGNAL_MISSING,
    MISSING_MATERIAL_SIGNAL_MISSING,
    COVERAGE_SIGNAL_MISSING,
    MAX_ITEMS_APPLIED,
]

# Safe generated check-id shape.
CHECK_ID_PREFIX = "guide_quality_check_"

# Defensive ceiling — guards a pathological ``max_items``, NOT a product cap. The
# real check count is bounded by ``len(_CHECK_ORDER)``.
_CHECK_HARD_CEILING = 500

# Bound the scan so a pathological clean.md cannot blow up regex work. Counts on the
# truncated head are still an honest signal; truncation never changes safety.
_MAX_SCAN_CHARS = 5_000_000

# --- Safe scan patterns (counted only; no captured text is ever persisted) ---
# Page-grounded signal: a "page <N>" style reference. We keep only the integer page
# numbers (for the unique count); we never keep the surrounding text.
_PAGE_SIGNAL_RE = re.compile(r"\bpage\s+(\d{1,4})\b", re.IGNORECASE)

# Markdown image ref ``![alt](ref)`` — the ref is validated by ``_is_safe_asset_ref``
# below; anything not of the fixed safe ``assets/<slug>.png`` shape is ignored.
_IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)\s*\)")

# A safe app-generated asset ref is exactly ``assets/<slug>.png`` with a conservative
# slug charset, no directory traversal, no nested path, no scheme, no backslash.
_SAFE_ASSET_REF_RE = re.compile(r"^assets/[A-Za-z0-9][A-Za-z0-9._-]*\.png$")

# Closed set of static, app-authored guidance phrases. These are headings/labels the
# app itself injects (never source content), so counting their presence in the guide
# is a safe usage signal. The values are matched case-insensitively as plain phrases.
_PHRASE_SOURCE_VISUAL = "source visual, page"
_PHRASE_TABLE_GUIDANCE = "table reconstruction guidance"
_PHRASE_MISSING_GUIDANCE = "missing visual and table guidance"
_PHRASE_COVERAGE_GUIDANCE = "coverage-aware generation guidance"

# Closed per-check instruction (never echoes raw input / source content).
_CHECK_INSTRUCTION = {
    KIND_SOURCE_PAGES: (
        "Counts safe page-grounded signals observed in the generated guide and "
        "compares them against the source coverage report; a low count where pages "
        "were covered is reported as a warning, not a failure."
    ),
    KIND_VISUALS: (
        "Counts safe app-generated figure image refs of the fixed assets/<slug>.png "
        "shape and compares them against the planned non-table visual count; missing "
        "refs are reported as a warning only when full visual insertion was expected."
    ),
    KIND_TABLES: (
        "Counts safe app-authored table-guidance phrases and compares them against "
        "the table candidate / reconstruction policy counts; absent guidance where "
        "tables were detected is reported as a warning."
    ),
    KIND_MISSING_MATERIAL: (
        "Counts safe app-authored missing-material guidance phrases and compares them "
        "against the missing-material context item count; absent notes where material "
        "could not be inserted or reconstructed is reported as a warning."
    ),
    KIND_COVERAGE: (
        "Counts safe app-authored coverage-aware guidance phrases and compares them "
        "against the coverage-aware signal count; absent guidance where coverage "
        "signals were active is reported as a warning."
    ),
}

# Per-check closed warning emitted when an expected signal is not observed.
_CHECK_WARNING = {
    KIND_SOURCE_PAGES: SOURCE_PAGE_SIGNAL_MISSING,
    KIND_VISUALS: VISUAL_SIGNAL_MISSING,
    KIND_TABLES: TABLE_SIGNAL_MISSING,
    KIND_MISSING_MATERIAL: MISSING_MATERIAL_SIGNAL_MISSING,
    KIND_COVERAGE: COVERAGE_SIGNAL_MISSING,
}


# =============================================================================
# Public API
# =============================================================================


def build_guide_quality_report_v2(
    clean_markdown: str | None,
    *,
    source_coverage_report: dict | None = None,
    visual_inclusion_plan: dict | None = None,
    table_candidates_manifest: dict | None = None,
    table_reconstruction_policy: dict | None = None,
    missing_material_context: dict | None = None,
    coverage_aware_context: dict | None = None,
    full_visual_insertion_enabled: bool = False,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: generated guide + sanitized coverage artifacts -> quality report.

    Scans ``clean_markdown`` for *counts only* (safe page-grounded signals, safe
    ``assets/<slug>.png`` image refs, a closed set of static app-authored guidance
    phrases) and compares those counts against the aggregate counts already present
    in the sanitized coverage artifacts. Produces one closed *check* per coverage
    dimension (source pages, visuals, tables, missing material, coverage) plus a
    sanitized summary and a closed warning list.

    ``full_visual_insertion_enabled`` only relaxes/strengthens the visuals check (a
    planned visual with no observed image ref is a warning only when full insertion
    was expected). ``max_items`` is an optional **defensive ceiling**, NOT a product
    cap. Returns a report dict with ``version``, ``kind``, ``status``
    (``completed``/``partial``/``skipped``), ``summary``, ``checks``, ``warnings``.
    Pure and total: never raises, calls no LLM/provider, inspects no PDF/image, OCRs
    nothing, reconstructs no table, and never persists a markdown excerpt. On a
    missing/unreadable guide it degrades to a safe ``skipped`` report.
    """
    try:
        return _build(
            clean_markdown,
            source_coverage_report,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            missing_material_context,
            coverage_aware_context,
            bool(full_visual_insertion_enabled),
            max_items,
        )
    except Exception:
        return _skipped_report({GUIDE_MISSING}, _blank_summary())


# =============================================================================
# Builder
# =============================================================================


def _build(
    clean_markdown: Any,
    source_coverage_report: Any,
    visual_inclusion_plan: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    missing_material_context: Any,
    coverage_aware_context: Any,
    full_visual_insertion_enabled: bool,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()

    if not isinstance(clean_markdown, str) or not clean_markdown.strip():
        return _skipped_report({GUIDE_MISSING}, _blank_summary())

    text = clean_markdown[:_MAX_SCAN_CHARS]

    # --- Scan the generated guide for COUNTS ONLY (no excerpt is ever kept) ----
    page_total, page_unique = _scan_page_signals(text)
    safe_image_ref_count = _scan_safe_image_refs(text)
    source_visual_phrase = _count_phrase(text, _PHRASE_SOURCE_VISUAL)
    table_phrase = _count_phrase(text, _PHRASE_TABLE_GUIDANCE)
    missing_phrase = _count_phrase(text, _PHRASE_MISSING_GUIDANCE)
    coverage_phrase = _count_phrase(text, _PHRASE_COVERAGE_GUIDANCE)

    # --- Read the sanitized coverage artifacts for DECISIONS ONLY -------------
    covered_pages, unreadable_pages = _coverage_counts(source_coverage_report, warnings)
    planned_visual_count = _plan_count(visual_inclusion_plan, warnings)
    table_candidate_count = _table_candidate_count(table_candidates_manifest, warnings)
    table_policy_item_count = _table_policy_count(table_reconstruction_policy, warnings)
    missing_material_item_count = _context_count(
        missing_material_context, MISSING_MATERIAL_MALFORMED, warnings
    )
    coverage_signal_count = _context_count(
        coverage_aware_context, COVERAGE_CONTEXT_MALFORMED, warnings
    )

    # --- Build one closed check per coverage dimension ------------------------
    specs = [
        _source_pages_check(page_total, covered_pages),
        _visuals_check(
            safe_image_ref_count,
            source_visual_phrase,
            planned_visual_count,
            full_visual_insertion_enabled,
        ),
        _tables_check(table_phrase, table_candidate_count, table_policy_item_count),
        _missing_material_check(missing_phrase, missing_material_item_count),
        _coverage_check(coverage_phrase, coverage_signal_count, unreadable_pages),
    ]
    ordered = {kind: spec for kind, spec in specs}

    status_token = "completed"
    ceiling = _CHECK_HARD_CEILING
    if isinstance(max_items, int) and not isinstance(max_items, bool) and max_items >= 0:
        ceiling = min(ceiling, max_items)
    selected = [kind for kind in _CHECK_ORDER]
    if len(selected) > ceiling:
        selected = selected[:ceiling]
        warnings.add(MAX_ITEMS_APPLIED)
        status_token = "partial"

    checks: list[dict[str, Any]] = []
    for index, kind in enumerate(selected, start=1):
        observed, expected, status = ordered[kind]
        check_warnings: list[str] = []
        if status == STATUS_WARNING:
            token = _CHECK_WARNING[kind]
            warnings.add(token)
            check_warnings.append(token)
        checks.append(
            {
                "check_id": f"{CHECK_ID_PREFIX}{index:04d}",
                "kind": kind,
                "status": status,
                "observed_count": observed,
                "expected_count": expected,
                "instruction": _CHECK_INSTRUCTION[kind],
                "warnings": check_warnings,
            }
        )

    summary = {
        "guide_present": True,
        "source_page_signal_count": page_total,
        "unique_source_page_signal_count": page_unique,
        "safe_image_ref_count": safe_image_ref_count,
        "planned_visual_count": planned_visual_count,
        "table_candidate_count": table_candidate_count,
        "table_policy_item_count": table_policy_item_count,
        "missing_material_item_count": missing_material_item_count,
        "coverage_signal_count": coverage_signal_count,
        "warning_count": len(warnings),
    }
    return _finalize(status_token, summary, checks, warnings)


# =============================================================================
# Per-dimension checks (closed; counts in, closed status out)
# =============================================================================


def _source_pages_check(
    page_total: int, covered_pages: int
) -> tuple[str, tuple[int, int, str]]:
    expected = covered_pages
    if covered_pages <= 0:
        status = STATUS_NOT_APPLICABLE
    elif page_total > 0:
        status = STATUS_PASSED
    else:
        status = STATUS_WARNING
    return KIND_SOURCE_PAGES, (page_total, expected, status)


def _visuals_check(
    safe_image_ref_count: int,
    source_visual_phrase: int,
    planned_visual_count: int,
    full_visual_insertion_enabled: bool,
) -> tuple[str, tuple[int, int, str]]:
    observed = safe_image_ref_count + source_visual_phrase
    expected = planned_visual_count
    if planned_visual_count <= 0:
        status = STATUS_NOT_APPLICABLE
    elif observed > 0:
        status = STATUS_PASSED
    elif full_visual_insertion_enabled:
        status = STATUS_WARNING
    else:
        # Visuals were planned but full insertion was not enabled, so an absent ref
        # is expected behaviour rather than a quality gap.
        status = STATUS_UNKNOWN
    return KIND_VISUALS, (observed, expected, status)


def _tables_check(
    table_phrase: int, table_candidate_count: int, table_policy_item_count: int
) -> tuple[str, tuple[int, int, str]]:
    expected = max(table_candidate_count, table_policy_item_count)
    if expected <= 0:
        status = STATUS_NOT_APPLICABLE
    elif table_phrase > 0:
        status = STATUS_PASSED
    else:
        status = STATUS_WARNING
    return KIND_TABLES, (table_phrase, expected, status)


def _missing_material_check(
    missing_phrase: int, missing_material_item_count: int
) -> tuple[str, tuple[int, int, str]]:
    expected = missing_material_item_count
    if missing_material_item_count <= 0:
        status = STATUS_NOT_APPLICABLE
    elif missing_phrase > 0:
        status = STATUS_PASSED
    else:
        status = STATUS_WARNING
    return KIND_MISSING_MATERIAL, (missing_phrase, expected, status)


def _coverage_check(
    coverage_phrase: int, coverage_signal_count: int, unreadable_pages: int
) -> tuple[str, tuple[int, int, str]]:
    expected = coverage_signal_count
    if coverage_signal_count <= 0:
        status = STATUS_NOT_APPLICABLE
    elif coverage_phrase > 0:
        status = STATUS_PASSED
    else:
        status = STATUS_WARNING
    return KIND_COVERAGE, (coverage_phrase, expected, status)


# =============================================================================
# Markdown scanning (counts only; never persists an excerpt)
# =============================================================================


def _scan_page_signals(text: str) -> tuple[int, int]:
    """Return (total page-signal count, unique page-number count). Counts only."""
    pages: list[int] = []
    seen: set[int] = set()
    for match in _PAGE_SIGNAL_RE.finditer(text):
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        pages.append(value)
        seen.add(value)
    return len(pages), len(seen)


def _scan_safe_image_refs(text: str) -> int:
    """Count Markdown image refs of the fixed safe ``assets/<slug>.png`` shape only."""
    count = 0
    for match in _IMAGE_REF_RE.finditer(text):
        ref = match.group(1)
        if _is_safe_asset_ref(ref):
            count += 1
    return count


def _is_safe_asset_ref(ref: Any) -> bool:
    """True only for an app-generated ``assets/<slug>.png`` ref with no scheme,
    no nested path, no traversal, no backslash, no whitespace."""
    if not isinstance(ref, str):
        return False
    candidate = ref.strip()
    if not candidate or candidate != ref.strip():
        return False
    if "\\" in candidate or ".." in candidate or "//" in candidate:
        return False
    if ":" in candidate:  # rejects http:, https:, data:, file:, drive letters
        return False
    if candidate.startswith("/") or candidate.startswith("./"):
        return False
    return bool(_SAFE_ASSET_REF_RE.match(candidate))


def _count_phrase(text: str, phrase: str) -> int:
    """Count case-insensitive occurrences of a static app-authored phrase."""
    if not phrase:
        return 0
    return text.lower().count(phrase)


# =============================================================================
# Artifact reading (read for decisions; never echo raw input)
# =============================================================================


def _coverage_counts(report: Any, warnings: set[str]) -> tuple[int, int]:
    """Return (covered_page_count, unreadable_page_count) from the coverage report."""
    if report is None:
        return 0, 0
    if not isinstance(report, dict):
        warnings.add(SOURCE_COVERAGE_MALFORMED)
        return 0, 0
    if _token(report.get("status")) == "skipped":
        return 0, 0
    summary = report.get("summary")
    if not isinstance(summary, dict):
        warnings.add(SOURCE_COVERAGE_MALFORMED)
        return 0, 0
    return (
        _safe_count(summary.get("covered_pages")),
        _safe_count(summary.get("empty_or_unreadable_pages")),
    )


def _plan_count(plan: Any, warnings: set[str]) -> int:
    return _artifact_count(
        plan,
        summary_key="planned_count",
        list_key="items",
        malformed=VISUAL_PLAN_MALFORMED,
        warnings=warnings,
    )


def _table_candidate_count(manifest: Any, warnings: set[str]) -> int:
    return _artifact_count(
        manifest,
        summary_key="table_like_candidate_count",
        list_key="candidates",
        malformed=TABLE_MANIFEST_MALFORMED,
        warnings=warnings,
    )


def _table_policy_count(policy: Any, warnings: set[str]) -> int:
    return _artifact_count(
        policy,
        summary_key="policy_item_count",
        list_key="items",
        malformed=TABLE_POLICY_MALFORMED,
        warnings=warnings,
    )


def _context_count(context: Any, malformed: str, warnings: set[str]) -> int:
    return _artifact_count(
        context,
        summary_key="prompt_item_count",
        list_key="items",
        malformed=malformed,
        warnings=warnings,
    )


def _artifact_count(
    artifact: Any,
    *,
    summary_key: str,
    list_key: str,
    malformed: str,
    warnings: set[str],
) -> int:
    """Count items in a sanitized artifact: summary count first, list len fallback."""
    if artifact is None:
        return 0
    if not isinstance(artifact, dict):
        warnings.add(malformed)
        return 0
    if _token(artifact.get("status")) == "skipped":
        return 0
    summary = artifact.get("summary")
    if isinstance(summary, dict):
        count = _safe_count(summary.get(summary_key), default=None)
        if count is not None:
            return count
    listed = artifact.get(list_key)
    if isinstance(listed, list):
        return len(listed)
    return 0


# =============================================================================
# Field coercion
# =============================================================================


def _safe_count(value: Any, *, default: int | None = 0) -> int | None:
    # A safe count is a non-negative int (never a float/str/bool).
    if not isinstance(value, int) or isinstance(value, bool):
        return default
    return value if value >= 0 else default


def _token(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


# =============================================================================
# Assembly
# =============================================================================


def _blank_summary() -> dict[str, Any]:
    return {
        "guide_present": False,
        "source_page_signal_count": 0,
        "unique_source_page_signal_count": 0,
        "safe_image_ref_count": 0,
        "planned_visual_count": 0,
        "table_candidate_count": 0,
        "table_policy_item_count": 0,
        "missing_material_item_count": 0,
        "coverage_signal_count": 0,
        "warning_count": 0,
    }


def _finalize(
    status: str,
    summary: dict[str, Any],
    checks: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    summary = dict(summary)
    summary["warning_count"] = len(warnings)
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": status,
        "summary": summary,
        "checks": checks,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_report(warnings: set[str], summary: dict[str, Any]) -> dict[str, Any]:
    return _finalize("skipped", summary, [], warnings)
