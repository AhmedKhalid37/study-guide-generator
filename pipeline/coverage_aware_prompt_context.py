"""Coverage-aware **generation prompt-context** builder (Slice 95).

Full Material Coverage capstone. Slices 82–94 layered a set of already-sanitized
coverage signals onto every generation:

* which material pages/slides are included vs. excluded (page-selection envelopes);
* what source coverage exists (Slice 84 ``source_coverage_report``);
* which useful non-table visuals are planned (Slice 84 ``visual_inclusion_plan``);
* which table-like candidates exist + their reconstruction policy (Slices 92/85);
* the Slice 93 table reconstruction prompt context;
* the Slice 94 missing diagram/table explainer context.

Slice 95 adds the single, summarising layer on top: one short, sanitized
**coverage-aware generation guidance** block that tells the guide generator to use
the selected material *completely and honestly* — focus on included pages, never
rely on excluded ones, connect explanations to inserted figures, reconstruct tables
only from available source text, and add honest notes (not guesses) when something
is unavailable.

Product goal (use the selected material completely and honestly)
---------------------------------------------------------------
``Guide generation should be aware of material coverage — included/excluded pages,
source coverage gaps, planned/inserted visual context, table policy, and
missing-material guidance — without exposing raw source details or hallucinating
unavailable content.``

This is a *summary* of the coverage rules and which closed signals are active. It
deliberately does NOT repeat every Slice 93/94 item; those blocks carry the
per-item detail.

Scope (Slice 95 = prompt-context only)
--------------------------------------
Pure derivation only. It does NOT change extraction/OCR, inspect PDFs/images, read
image bytes, reconstruct a table, extract table text, render, export, change figure
insertion semantics, change material page selection, change visual-manifest
filtering, add UI, or call a provider / model / VLM / Chandra / Mistral / Gemini /
cloud. It reads ONLY the already-sanitized job-request selection envelopes and
artifact/context dicts and returns a sanitized context dict whose ``prompt_block``
is safe to append to the existing generation prompt.

Purity & safety
---------------
stdlib-only (imports nothing from ``pipeline`` and no provider/model/OCR/renderer/
FastAPI/frontend module). The context emits **only** closed tokens, ints, ``None``,
bools, fixed instruction strings built from those, and a safe generated ``item_id``
of the fixed shape ``coverage_context_NNNN``. No filename, path, source title,
caption, document / OCR / table text, image ref, asset ref / asset id, image byte,
base64 / data URI, provider payload, token, URL, argv, socket path, model path, or
raw exception string can survive into it: input fields are read for *decisions only*
and never echoed. Never raises; any malformed input degrades to a safe ``skipped`` /
empty context.
"""
from __future__ import annotations

from typing import Any

CONTEXT_VERSION = 1
CONTEXT_KIND = "coverage_aware_prompt_context"

# --- Closed coverage-signal / item kinds -------------------------------------
KIND_INCLUDED_PAGE = "included_page"
KIND_SOURCE_GAP = "source_gap"
KIND_VISUAL_PLAN = "visual_plan"
KIND_TABLE_POLICY = "table_policy"
KIND_MISSING_MATERIAL = "missing_material"

# Deterministic emission order of the closed signal items.
_SIGNAL_ORDER = (
    KIND_INCLUDED_PAGE,
    KIND_SOURCE_GAP,
    KIND_VISUAL_PLAN,
    KIND_TABLE_POLICY,
    KIND_MISSING_MATERIAL,
)

# --- Closed warning vocabulary (this module owns what it emits) --------------
ALL_INPUTS_MISSING = "all_inputs_missing"
JOB_REQUEST_MALFORMED = "job_request_malformed"
SOURCE_COVERAGE_MALFORMED = "source_coverage_malformed"
VISUAL_PLAN_MALFORMED = "visual_plan_malformed"
TABLE_MANIFEST_MALFORMED = "table_manifest_malformed"
TABLE_POLICY_MALFORMED = "table_policy_malformed"
TABLE_PROMPT_CONTEXT_MALFORMED = "table_prompt_context_malformed"
MISSING_MATERIAL_MALFORMED = "missing_material_malformed"
MAX_ITEMS_APPLIED = "max_items_applied"

# Deterministic emitted warning ordering (closed tokens only, never raw text).
WARNING_ORDER = [
    ALL_INPUTS_MISSING,
    JOB_REQUEST_MALFORMED,
    SOURCE_COVERAGE_MALFORMED,
    VISUAL_PLAN_MALFORMED,
    TABLE_MANIFEST_MALFORMED,
    TABLE_POLICY_MALFORMED,
    TABLE_PROMPT_CONTEXT_MALFORMED,
    MISSING_MATERIAL_MALFORMED,
    MAX_ITEMS_APPLIED,
]

# Safe generated item-id shape.
ITEM_ID_PREFIX = "coverage_context_"

# Defensive ceiling — guards a pathological ``max_items``, NOT a product cap. The
# real signal count is bounded by ``len(_SIGNAL_ORDER)``.
_PROMPT_ITEM_HARD_CEILING = 500

# Static, leak-free guidance lines prepended to every non-empty prompt block.
_GUIDANCE_LINES = (
    "Coverage-aware generation guidance:",
    "- Use only the included source material and the available source text.",
    "- Do not rely on pages or slides that were excluded by material coverage "
    "controls.",
    "- Preserve page-grounded terms, labels, headers, units, and numeric values "
    "when present in the provided source text.",
    "- Connect explanations to inserted figures when figures are present.",
    "- Do not invent diagram labels, figure captions, table rows, table cells, or "
    "numeric values.",
    "- If a page or table-like item is unreadable or unavailable, add a short "
    "honest note instead of guessing.",
)

# Closed one-line signal bullet per active coverage signal (never source content).
_SIGNAL_BULLET = {
    KIND_INCLUDED_PAGE: "Material page exclusions are active.",
    KIND_SOURCE_GAP: "Source coverage includes unreadable pages.",
    KIND_VISUAL_PLAN: "Non-table visuals were planned for included pages.",
    KIND_TABLE_POLICY: "Table-like candidates were detected and have "
    "reconstruction guidance.",
    KIND_MISSING_MATERIAL: "Missing visual/table guidance is active.",
}

# Closed per-item instruction per active coverage signal (never source content).
_SIGNAL_INSTRUCTION = {
    KIND_INCLUDED_PAGE: (
        "Material page selections are active; focus only on the included pages and "
        "do not rely on pages or slides that were excluded."
    ),
    KIND_SOURCE_GAP: (
        "Some source pages were unreadable or uncovered; mention coverage gaps only "
        "generically and page-based, and do not fill them with invented content."
    ),
    KIND_VISUAL_PLAN: (
        "Non-table visuals were planned for included pages; connect explanations to "
        "inserted figures and do not invent diagram labels or captions."
    ),
    KIND_TABLE_POLICY: (
        "Table-like candidates were detected; reconstruct or simplify a table only "
        "when its contents are present in the provided source text, and never invent "
        "rows, cells, labels, or values."
    ),
    KIND_MISSING_MATERIAL: (
        "Some detected visual or table material could not be inserted or "
        "reconstructed; add short honest missing-material notes instead of guessing."
    ),
}


# =============================================================================
# Public API
# =============================================================================


def build_coverage_aware_prompt_context(
    *,
    job_request: dict | None = None,
    source_coverage_report: dict | None = None,
    visual_inclusion_plan: dict | None = None,
    table_candidates_manifest: dict | None = None,
    table_reconstruction_policy: dict | None = None,
    table_prompt_context: dict | None = None,
    missing_material_context: dict | None = None,
    full_visual_insertion_enabled: bool = False,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Pure builder: sanitized coverage signals -> coverage-aware prompt context.

    Reads only the already-sanitized job-request page-selection envelopes and the
    Slice 84/92/93/94 artifact/context dicts. Produces a short, summarising
    guidance block plus one closed *signal item* per active coverage signal
    (included-page exclusions, source-coverage gaps, planned visuals, table policy,
    missing-material guidance). It never repeats the per-item Slice 93/94 detail.

    ``full_visual_insertion_enabled`` is accepted for symmetry with the other
    coverage builders; the guidance is identical either way (it never claims a
    figure was inserted or failed). ``max_items`` is an optional **defensive
    ceiling**, NOT a product cap. Returns a context dict with ``version``, ``kind``,
    ``status`` (``completed``/``partial``/``skipped``), ``summary``, ``prompt_block``,
    ``items``, ``warnings``. Pure and total: never raises, inspects no PDF/image,
    OCRs nothing, reconstructs no table, and calls no provider. On any unexpected
    input it degrades to a safe ``skipped`` context with an empty ``prompt_block``.
    """
    try:
        return _build(
            job_request,
            source_coverage_report,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            table_prompt_context,
            missing_material_context,
            max_items,
        )
    except Exception:
        return _skipped_context({ALL_INPUTS_MISSING}, _blank_summary())


# =============================================================================
# Builder
# =============================================================================


def _build(
    job_request: Any,
    source_coverage_report: Any,
    visual_inclusion_plan: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    table_prompt_context: Any,
    missing_material_context: Any,
    max_items: Any,
) -> dict[str, Any]:
    warnings: set[str] = set()

    if all(
        value is None
        for value in (
            job_request,
            source_coverage_report,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
            table_prompt_context,
            missing_material_context,
        )
    ):
        return _skipped_context({ALL_INPUTS_MISSING}, _blank_summary())

    # --- Read every input for DECISIONS ONLY (never echo a raw field) ---------
    has_selections = _has_material_selections(job_request, warnings)
    source_count, covered_pages, unreadable_pages = _coverage_counts(
        source_coverage_report, warnings
    )
    planned_visual_count = _plan_count(visual_inclusion_plan, warnings)
    table_candidate_count = _table_candidate_count(table_candidates_manifest, warnings)
    table_policy_item_count = _table_policy_count(
        table_reconstruction_policy, table_prompt_context, warnings
    )
    missing_material_item_count = _missing_material_count(
        missing_material_context, warnings
    )

    summary = {
        "has_material_page_selections": has_selections,
        "source_count": source_count,
        "covered_page_count": covered_pages,
        "unreadable_page_count": unreadable_pages,
        "planned_visual_count": planned_visual_count,
        "table_candidate_count": table_candidate_count,
        "table_policy_item_count": table_policy_item_count,
        "missing_material_item_count": missing_material_item_count,
        "prompt_item_count": 0,
    }

    # --- Decide which closed coverage signals are active ----------------------
    active: dict[str, bool] = {
        KIND_INCLUDED_PAGE: has_selections,
        KIND_SOURCE_GAP: unreadable_pages > 0,
        KIND_VISUAL_PLAN: planned_visual_count > 0,
        KIND_TABLE_POLICY: table_candidate_count > 0 or table_policy_item_count > 0,
        KIND_MISSING_MATERIAL: missing_material_item_count > 0,
    }
    signals = [kind for kind in _SIGNAL_ORDER if active.get(kind)]

    status_token = "completed"
    ceiling = _PROMPT_ITEM_HARD_CEILING
    if isinstance(max_items, int) and not isinstance(max_items, bool) and max_items >= 0:
        ceiling = min(ceiling, max_items)
    if len(signals) > ceiling:
        signals = signals[:ceiling]
        warnings.add(MAX_ITEMS_APPLIED)
        status_token = "partial"

    if not signals:
        # Nothing useful and safe to say (all coverage signals inactive).
        return _skipped_context(warnings, summary)

    items: list[dict[str, Any]] = []
    for index, kind in enumerate(signals, start=1):
        items.append(
            {
                "item_id": f"{ITEM_ID_PREFIX}{index:04d}",
                # Coverage signals are aggregate, not page-anchored, so there is no
                # single verifiable source page; any future page must be a positive int.
                "source_page": None,
                "kind": kind,
                "instruction": _SIGNAL_INSTRUCTION[kind],
                "warnings": [],
            }
        )

    summary["prompt_item_count"] = len(items)
    prompt_block = _prompt_block(signals)
    return _finalize(status_token, summary, items, prompt_block, warnings)


# =============================================================================
# Input extraction (read for decisions; never echo raw input)
# =============================================================================


def _has_material_selections(job_request: Any, warnings: set[str]) -> bool:
    """True when a global or per-attachment page selection actually limits pages."""
    if job_request is None:
        return False
    if not isinstance(job_request, dict):
        warnings.add(JOB_REQUEST_MALFORMED)
        return False
    if _selection_active(job_request.get("material_page_selection")):
        return True
    per = job_request.get("material_page_selections")
    if isinstance(per, dict):
        # The envelope may nest per-attachment selections under "attachments".
        candidates = per.get("attachments") if isinstance(per.get("attachments"), dict) else per
        if isinstance(candidates, dict):
            for selection in candidates.values():
                if _selection_active(selection):
                    return True
    return False


def _selection_active(selection: Any) -> bool:
    if not isinstance(selection, dict):
        return False
    for key in ("include_pages", "exclude_pages"):
        pages = selection.get(key)
        if isinstance(pages, list) and any(_is_positive_int(page) for page in pages):
            return True
    return _token(selection.get("mode")) in ("include", "exclude")


def _coverage_counts(report: Any, warnings: set[str]) -> tuple[int, int, int]:
    """Return (source_count, covered_page_count, unreadable_page_count)."""
    if report is None:
        return 0, 0, 0
    if not isinstance(report, dict):
        warnings.add(SOURCE_COVERAGE_MALFORMED)
        return 0, 0, 0
    if _token(report.get("status")) == "skipped":
        return 0, 0, 0
    summary = report.get("summary")
    if not isinstance(summary, dict):
        warnings.add(SOURCE_COVERAGE_MALFORMED)
        return 0, 0, 0
    return (
        _safe_count(summary.get("source_count")),
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


def _table_policy_count(policy: Any, prompt_context: Any, warnings: set[str]) -> int:
    count = _artifact_count(
        policy,
        summary_key="policy_item_count",
        list_key="items",
        malformed=TABLE_POLICY_MALFORMED,
        warnings=warnings,
    )
    # The Slice 93 prompt context is optional; only use it to RAISE the count so an
    # absent/skipped policy still reflects actionable table guidance.
    ctx_count = _artifact_count(
        prompt_context,
        summary_key="prompt_item_count",
        list_key="items",
        malformed=TABLE_PROMPT_CONTEXT_MALFORMED,
        warnings=warnings,
    )
    return max(count, ctx_count)


def _missing_material_count(context: Any, warnings: set[str]) -> int:
    return _artifact_count(
        context,
        summary_key="prompt_item_count",
        list_key="items",
        malformed=MISSING_MATERIAL_MALFORMED,
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
# Prompt-block text (closed; never echoes raw input)
# =============================================================================


def _prompt_block(signals: list[str]) -> str:
    lines = list(_GUIDANCE_LINES)
    lines.append("Coverage signals:")
    for kind in signals:
        lines.append(f"- {_SIGNAL_BULLET[kind]}")
    return "\n".join(lines)


# =============================================================================
# Field coercion
# =============================================================================


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


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
        "has_material_page_selections": False,
        "source_count": 0,
        "covered_page_count": 0,
        "unreadable_page_count": 0,
        "planned_visual_count": 0,
        "table_candidate_count": 0,
        "table_policy_item_count": 0,
        "missing_material_item_count": 0,
        "prompt_item_count": 0,
    }


def _finalize(
    status: str,
    summary: dict[str, Any],
    items: list[dict[str, Any]],
    prompt_block: str,
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": CONTEXT_VERSION,
        "kind": CONTEXT_KIND,
        "status": status,
        "summary": summary,
        "prompt_block": prompt_block,
        "items": items,
        "warnings": [token for token in WARNING_ORDER if token in warnings],
    }


def _skipped_context(warnings: set[str], summary: dict[str, Any]) -> dict[str, Any]:
    safe_summary = dict(summary)
    safe_summary["prompt_item_count"] = 0
    return _finalize("skipped", safe_summary, [], "", warnings)
