"""Pure, deterministic **visual insertion planner core** (Slice 52, roadmap V3+).

The visual stack (``docs/VISION_ROADMAP.md`` §8) goes: advisory manifest (V1,
``pipeline.visual_assets_manifest``) → candidate *scoring* (V3 core,
``pipeline.visual_asset_scoring`` + the Slice 47 ``visual_asset_scoring.json``
artifact) → a *replacement* plan (V3 core, ``pipeline.visual_replacement_planner``
+ the Slice 49 ``visual_replacement_plan.json`` artifact) → an eventual guide
embedding (V4+). This module is the next *pure planning core* on that path: given
an already-sanitized ``visual_replacement_plan.json``-shaped replacement plan (and,
optionally, a **safe-only** source-page anchor inventory), it returns a **separate
advisory insertion-position plan** — a per-asset ``insertion_mode`` / ``placement``
/ ``anchor_status`` with closed-vocabulary ``reasons`` — *without ever* mutating the
replacement plan or anchors, persisting an artifact, embedding visuals, changing
extraction/guides/rendering, or wiring into production.

What this slice does and does NOT do
------------------------------------
- It **plans** an advisory *insertion position* (``insertion_mode`` +
  ``placement`` + ``anchor_status``) for each already-planned replacement item and
  returns a brand-new ``visual_insertion_plan`` report dict. The pure planning core
  never mutates the replacement plan, the anchor inventory, or any item/anchor
  dict, never embeds visuals, never calls any provider/model/llama-server/network,
  and never opens or inspects any image file.
- It does **NOT** persist a job artifact (no ``visual_insertion_plan.json`` writer
  in this slice), is **not** wired into ``pipeline/run_llm_job.py`` / extraction /
  rendering / prompts / exports / the API / any UI, and is **not** added to any
  generic artifact list, export bundle, or artifact UI row.
- The ``insertion_mode`` it assigns is **advisory only** — it is a *candidate
  position*, never a binding include/insert decision. The real guide embedding is a
  later, separately-designed slice. Generated guides are unaffected.

Anchors are presence-only and safe-only
---------------------------------------
A source-page *anchor* is a safe, slug-safe reference id for a source page (e.g.
``source_page_0001``) — never a coordinate, never raw layout, never raw text. The
optional ``source_page_anchors`` inventory may be a list of
``{"source_page": 1, "anchor_id": "source_page_0001"}`` entries, a dict keyed by
source page, or absent. Every anchor id is sanitized to a slug before it can leave
this module; an invalid/empty anchor id is dropped (never emitted), so a lookup
simply misses and the item degrades to ``anchor_status:"missing"``. No anchor field
other than the sanitized id is ever read into the output.

Chandra independence
--------------------
This is a provider-agnostic visual-stack slice, **not** Chandra integration. A
``chandra_local`` item (or one carrying the ``chandra_blocked`` marker) is never
mapped to a direct ``figure_reference`` / ``table_reference`` /
``text_summary_reference`` insertion mode: it degrades to ``review_only`` /
``review_appendix`` and carries the closed reason ``chandra_blocked`` because Slice
45 recorded the Chandra live harness as ``status:not_run``
(``operator_input_not_supplied``) — Chandra *extraction* integration remains blocked
until a live harness pass is recorded.

Purity & safety
---------------
:func:`plan_visual_insertion_item`, :func:`plan_visual_insertions` and
:func:`build_visual_insertion_plan` are pure, *total* functions of already-sanitized
input. The module imports **nothing** from PyMuPDF (``fitz``), Tesseract, llama.cpp,
a Chandra runtime/provider, Mistral/Gemini/cloud SDKs, the Local Model Manager,
renderers, the API server, the job manager, or any extraction/run-job module — only
Python stdlib (``re``, ``typing``). The pure core **never raises** on malformed
input; it degrades to a safe ``completed`` report with closed-vocabulary warnings.

Every emitted field is a fixed token from a closed vocabulary, an int, ``None``, an
empty list, or a deterministic slug-safe ``asset_id`` / ``anchor_id``. Input fields
are coerced field-by-field and **never echoed** — only a sanitized asset id, a
coerced source page, a sanitized anchor id, and closed-vocab
provider/type/action/mode/placement/anchor-status tokens leave this module. No raw
caption, raw source/OCR text, provider/model payload, image byte, data URI, base64
blob, path, URL, header, token, socket path, model/``mmproj`` path, executable path,
or raw argv can survive into the plan even if a hostile record smuggles one in.
"""
from __future__ import annotations

import re
from typing import Any

REPORT_VERSION = 1
REPORT_KIND = "visual_insertion_plan"
REPORT_SOURCE = "visual_replacement_plan.json"

# --- Closed vocabularies (this module owns what it is allowed to emit) --------

# Advisory insertion mode. Never a binding insert/embed decision.
INSERTION_MODE_FIGURE_REFERENCE = "figure_reference"
INSERTION_MODE_TABLE_REFERENCE = "table_reference"
INSERTION_MODE_TEXT_SUMMARY_REFERENCE = "text_summary_reference"
INSERTION_MODE_REVIEW_ONLY = "review_only"
INSERTION_MODE_UNKNOWN = "unknown"
INSERTION_MODES = {
    INSERTION_MODE_FIGURE_REFERENCE,
    INSERTION_MODE_TABLE_REFERENCE,
    INSERTION_MODE_TEXT_SUMMARY_REFERENCE,
    INSERTION_MODE_REVIEW_ONLY,
    INSERTION_MODE_UNKNOWN,
}

# Reference modes need a resolved source-page anchor to place; the others do not.
_REFERENCE_MODES = {
    INSERTION_MODE_FIGURE_REFERENCE,
    INSERTION_MODE_TABLE_REFERENCE,
    INSERTION_MODE_TEXT_SUMMARY_REFERENCE,
}

# Advisory placement. Only ever a source-page reference, a review appendix, or
# unknown — never derived from private/raw text or a real layout coordinate.
PLACEMENT_SOURCE_PAGE_REFERENCE = "source_page_reference"
PLACEMENT_REVIEW_APPENDIX = "review_appendix"
PLACEMENT_UNKNOWN = "unknown"
PLACEMENTS = {
    PLACEMENT_SOURCE_PAGE_REFERENCE,
    PLACEMENT_REVIEW_APPENDIX,
    PLACEMENT_UNKNOWN,
}

# Anchor resolution status.
ANCHOR_STATUS_MATCHED = "matched"
ANCHOR_STATUS_MISSING = "missing"
ANCHOR_STATUS_NOT_REQUIRED = "not_required"
ANCHOR_STATUS_UNKNOWN = "unknown"
ANCHOR_STATUSES = {
    ANCHOR_STATUS_MATCHED,
    ANCHOR_STATUS_MISSING,
    ANCHOR_STATUS_NOT_REQUIRED,
    ANCHOR_STATUS_UNKNOWN,
}

# Advisory candidate actions (mirror the replacement planner's; owned locally so
# they cannot be widened upstream). Anything else → "unknown".
ACTION_INCLUDE_AS_FIGURE = "candidate_include_as_figure"
ACTION_CONVERT_TO_TABLE = "candidate_convert_to_table"
ACTION_SUMMARIZE_AS_TEXT = "candidate_summarize_as_text"
ACTION_REVIEW_ONLY = "review_only"
ACTION_UNKNOWN = "unknown"
CANDIDATE_ACTIONS = {
    ACTION_INCLUDE_AS_FIGURE,
    ACTION_CONVERT_TO_TABLE,
    ACTION_SUMMARIZE_AS_TEXT,
    ACTION_REVIEW_ONLY,
    ACTION_UNKNOWN,
}

# Closed source-provider vocabulary (mirrors the upstream cores). Anything else →
# "unknown".
SOURCE_PROVIDER_FITZ_LOCAL = "fitz_local"
SOURCE_PROVIDER_CHANDRA_LOCAL = "chandra_local"
SOURCE_PROVIDER_MISTRAL_OCR = "mistral_ocr"
SOURCE_PROVIDER_UNKNOWN = "unknown"
SOURCE_PROVIDERS = {
    SOURCE_PROVIDER_FITZ_LOCAL,
    SOURCE_PROVIDER_CHANDRA_LOCAL,
    SOURCE_PROVIDER_MISTRAL_OCR,
    SOURCE_PROVIDER_UNKNOWN,
}

# Closed asset-type vocabulary (union of the upstream cores' emitted types, plus
# reserved buckets). Anything else → "unknown".
ASSET_TYPE_UNKNOWN = "unknown"
ASSET_TYPES = {
    "page_visual_signal",
    "extracted_figure",
    "table",
    "table_region",
    "equation_block",
    "diagram",
    "figure",
    "image_region",
    "cropped_region",
    "unknown_region",
    ASSET_TYPE_UNKNOWN,
}

# Closed reason tokens. Only these may appear in an item's ``reasons`` list.
REASONS = {
    "candidate_include_as_figure",
    "candidate_convert_to_table",
    "candidate_summarize_as_text",
    "review_only",
    "anchor_matched",
    "anchor_missing",
    "source_page_reference",
    "review_appendix",
    "chandra_blocked",
    "low_information_signal",
    "unknown_candidate_action",
    "input_sanitized",
}

# Closed warning tokens. Only these may appear in an item's / report's warnings.
WARNINGS = {
    "replacement_plan_malformed",
    "replacement_item_malformed",
    "asset_id_missing",
    "asset_id_invalid",
    "source_page_invalid",
    "source_provider_unrecognized",
    "asset_type_unrecognized",
    "candidate_action_unrecognized",
    "anchor_id_invalid",
    "anchor_lookup_missing",
    "input_unrecognized",
}

# candidate_action → (insertion_mode, its closed action reason). Used only for
# non-Chandra items; Chandra items are forced to review_only upstream of this.
_ACTION_TO_MODE: dict[str, tuple[str, str]] = {
    ACTION_INCLUDE_AS_FIGURE: (INSERTION_MODE_FIGURE_REFERENCE, "candidate_include_as_figure"),
    ACTION_CONVERT_TO_TABLE: (INSERTION_MODE_TABLE_REFERENCE, "candidate_convert_to_table"),
    ACTION_SUMMARIZE_AS_TEXT: (INSERTION_MODE_TEXT_SUMMARY_REFERENCE, "candidate_summarize_as_text"),
    ACTION_REVIEW_ONLY: (INSERTION_MODE_REVIEW_ONLY, "review_only"),
    ACTION_UNKNOWN: (INSERTION_MODE_UNKNOWN, "unknown_candidate_action"),
}

# Deterministic emit order for reasons / warnings.
_REASON_ORDER = [
    "candidate_include_as_figure",
    "candidate_convert_to_table",
    "candidate_summarize_as_text",
    "review_only",
    "anchor_matched",
    "anchor_missing",
    "source_page_reference",
    "review_appendix",
    "low_information_signal",
    "chandra_blocked",
    "unknown_candidate_action",
    "input_sanitized",
]
_WARNING_ORDER = [
    "replacement_plan_malformed",
    "replacement_item_malformed",
    "input_unrecognized",
    "asset_id_missing",
    "asset_id_invalid",
    "source_page_invalid",
    "asset_type_unrecognized",
    "source_provider_unrecognized",
    "candidate_action_unrecognized",
    "anchor_id_invalid",
    "anchor_lookup_missing",
]

_SLUG_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]")
_MAX_ASSET_ID_LEN = 64
_MAX_ANCHOR_ID_LEN = 64


# --- Public API --------------------------------------------------------------


def plan_visual_insertion_item(item: Any, *, anchors_by_page: Any = None) -> dict[str, Any]:
    """Plan one ``visual_replacement_plan``-shaped item → a safe insertion dict.

    Pure and total: never mutates ``item`` or ``anchors_by_page``, never raises.
    ``anchors_by_page`` is an optional safe-only source-page anchor inventory (a
    list of ``{"source_page", "anchor_id"}`` entries, a dict keyed by source page,
    or ``None``); only a sanitized anchor id is ever read from it.
    """
    anchors = _normalize_anchors(anchors_by_page)[0]
    return _plan_one(item, index=1, anchors=anchors)


def plan_visual_insertions(items: Any, *, anchors_by_page: Any = None) -> list[dict[str, Any]]:
    """Plan a list of replacement-plan items → a list of insertion dicts.

    Non-list input degrades to ``[]``. ``anchors_by_page`` (optional, same shapes as
    :func:`plan_visual_insertion_item`) is sanitized once. Inputs are never mutated;
    no raw anchor field is echoed.
    """
    if not isinstance(items, list):
        return []
    anchors = _normalize_anchors(anchors_by_page)[0]
    out: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        out.append(_plan_one(item, index=index, anchors=anchors))
    return out


def build_visual_insertion_plan(
    replacement_plan: Any,
    *,
    source_page_anchors: Any = None,
) -> dict[str, Any]:
    """Build a ``visual_insertion_plan`` report from a replacement-plan dict.

    ``replacement_plan`` is the ``visual_replacement_plan.json``-shaped dict produced
    by the Slice 48/49 replacement planner. Returns a fresh advisory insertion plan
    report. Pure and total: the input replacement plan and ``source_page_anchors``
    (and their items/entries) are never mutated, no file is written, and any
    malformed input degrades to a valid ``completed`` report with a closed-vocab
    ``replacement_plan_malformed`` warning. ``source_page_anchors`` is optional and
    safe-only; only sanitized anchor ids are read from it.
    """
    warnings: list[str] = []
    items: Any = None
    if isinstance(replacement_plan, dict):
        items = replacement_plan.get("items")
        if not isinstance(items, list):
            warnings.append("replacement_plan_malformed")
            items = None
    else:
        warnings.append("replacement_plan_malformed")

    anchors, anchor_warnings = _normalize_anchors(source_page_anchors)
    warnings.extend(anchor_warnings)

    insertions = plan_visual_insertions(items, anchors_by_page=anchors)
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": "completed",
        "source": REPORT_SOURCE,
        "insertions": insertions,
        "summary": _summarize(insertions),
        "warnings": _ordered_unique(warnings, _WARNING_ORDER, WARNINGS),
    }


# --- Core planning (per-item) ------------------------------------------------


def _plan_one(item: Any, *, index: int, anchors: dict[int, str] | None) -> dict[str, Any]:
    if not isinstance(item, dict):
        # A non-dict item carries nothing plannable; return a safe shell.
        return _build_item(
            asset_id=_fallback_id(index),
            source_page=None,
            source_provider=SOURCE_PROVIDER_UNKNOWN,
            asset_type=ASSET_TYPE_UNKNOWN,
            candidate_action=ACTION_UNKNOWN,
            insertion_mode=INSERTION_MODE_UNKNOWN,
            placement=PLACEMENT_UNKNOWN,
            anchor_id=None,
            anchor_status=ANCHOR_STATUS_UNKNOWN,
            reasons=["unknown_candidate_action", "input_sanitized"],
            warnings=["replacement_item_malformed"],
        )

    warnings: list[str] = []
    reasons: list[str] = []

    asset_id, _ = _coerce_asset_id(item.get("asset_id"), index)
    if not isinstance(item.get("asset_id"), str):
        warnings.append("asset_id_missing")
    elif asset_id == _fallback_id(index) or asset_id != item.get("asset_id"):
        warnings.append("asset_id_invalid")

    source_page = _coerce_source_page(item.get("source_page"), warnings)
    source_provider = _safe_provider(item.get("source_provider"), warnings)
    asset_type = _safe_asset_type(item.get("asset_type"), warnings)
    candidate_action = _safe_action(item.get("candidate_action"), warnings)

    # An asset_type page signal is low-information regardless of action.
    if asset_type == "page_visual_signal":
        reasons.append("low_information_signal")

    chandra = _is_chandra(item, source_provider)

    if chandra:
        # Chandra items stay advisory + blocked (Slice 45 not_run): never a direct
        # figure/table/text insertion mode until a live harness pass is recorded.
        insertion_mode = INSERTION_MODE_REVIEW_ONLY
        placement = PLACEMENT_REVIEW_APPENDIX
        anchor_id: str | None = None
        anchor_status = ANCHOR_STATUS_NOT_REQUIRED
        reasons.extend(["review_only", "review_appendix", "chandra_blocked"])
    else:
        insertion_mode, action_reason = _ACTION_TO_MODE.get(
            candidate_action, (INSERTION_MODE_UNKNOWN, "unknown_candidate_action")
        )
        reasons.append(action_reason)
        if insertion_mode in _REFERENCE_MODES:
            anchor_id, anchor_status, placement = _resolve_anchor(source_page, anchors, reasons, warnings)
        elif insertion_mode == INSERTION_MODE_REVIEW_ONLY:
            anchor_id = None
            anchor_status = ANCHOR_STATUS_NOT_REQUIRED
            placement = PLACEMENT_REVIEW_APPENDIX
            reasons.append("review_appendix")
        else:  # unknown
            anchor_id = None
            anchor_status = ANCHOR_STATUS_UNKNOWN
            placement = PLACEMENT_UNKNOWN

    if warnings:
        reasons.append("input_sanitized")

    return _build_item(
        asset_id=asset_id,
        source_page=source_page,
        source_provider=source_provider,
        asset_type=asset_type,
        candidate_action=candidate_action,
        insertion_mode=insertion_mode,
        placement=placement,
        anchor_id=anchor_id,
        anchor_status=anchor_status,
        reasons=reasons,
        warnings=warnings,
    )


def _resolve_anchor(
    source_page: int | None,
    anchors: dict[int, str] | None,
    reasons: list[str],
    warnings: list[str],
) -> tuple[str | None, str, str]:
    """Resolve a source-page anchor for a reference-mode item.

    Returns ``(anchor_id, anchor_status, placement)``. A hit yields a matched anchor
    + a real source-page-reference placement; any miss (no inventory, unknown page,
    or dropped/invalid anchor id) degrades safely to a missing anchor and an unknown
    placement — the item stays advisory and must not be placed without an anchor.
    """
    anchor_id = None
    if source_page is not None and anchors:
        anchor_id = anchors.get(source_page)
    if anchor_id is not None:
        reasons.extend(["anchor_matched", "source_page_reference"])
        return anchor_id, ANCHOR_STATUS_MATCHED, PLACEMENT_SOURCE_PAGE_REFERENCE
    reasons.append("anchor_missing")
    warnings.append("anchor_lookup_missing")
    return None, ANCHOR_STATUS_MISSING, PLACEMENT_UNKNOWN


def _is_chandra(item: dict[str, Any], source_provider: str) -> bool:
    """True for a Chandra item: chandra_local provider OR a chandra_blocked marker."""
    if source_provider == SOURCE_PROVIDER_CHANDRA_LOCAL:
        return True
    item_reasons = item.get("reasons")
    return isinstance(item_reasons, list) and "chandra_blocked" in item_reasons


def _build_item(
    *,
    asset_id: str,
    source_page: int | None,
    source_provider: str,
    asset_type: str,
    candidate_action: str,
    insertion_mode: str,
    placement: str,
    anchor_id: str | None,
    anchor_status: str,
    reasons: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "source_page": source_page,
        "source_provider": source_provider,
        "asset_type": asset_type,
        "candidate_action": candidate_action,
        "insertion_mode": insertion_mode,
        "placement": placement,
        "anchor_id": anchor_id,
        "anchor_status": anchor_status,
        "reasons": _ordered_unique(reasons, _REASON_ORDER, REASONS),
        "warnings": _ordered_unique(warnings, _WARNING_ORDER, WARNINGS),
    }


# --- Summary -----------------------------------------------------------------


def _summarize(insertions: list[dict[str, Any]]) -> dict[str, Any]:
    mode_counts = {
        INSERTION_MODE_FIGURE_REFERENCE: 0,
        INSERTION_MODE_TABLE_REFERENCE: 0,
        INSERTION_MODE_TEXT_SUMMARY_REFERENCE: 0,
        INSERTION_MODE_REVIEW_ONLY: 0,
        INSERTION_MODE_UNKNOWN: 0,
    }
    anchor_matched = 0
    anchor_missing = 0
    for item in insertions:
        mode = item.get("insertion_mode")
        if mode in mode_counts:
            mode_counts[mode] += 1
        status = item.get("anchor_status")
        if status == ANCHOR_STATUS_MATCHED:
            anchor_matched += 1
        elif status == ANCHOR_STATUS_MISSING:
            anchor_missing += 1
    return {
        "insertion_count": len(insertions),
        "figure_reference_count": mode_counts[INSERTION_MODE_FIGURE_REFERENCE],
        "table_reference_count": mode_counts[INSERTION_MODE_TABLE_REFERENCE],
        "text_summary_reference_count": mode_counts[INSERTION_MODE_TEXT_SUMMARY_REFERENCE],
        "review_only_count": mode_counts[INSERTION_MODE_REVIEW_ONLY],
        "unknown_count": mode_counts[INSERTION_MODE_UNKNOWN],
        "anchor_matched_count": anchor_matched,
        "anchor_missing_count": anchor_missing,
    }


# --- Source-page anchor inventory (presence-only, safe-only) ------------------


def _normalize_anchors(raw: Any) -> tuple[dict[int, str] | None, list[str]]:
    """Build a ``{positive_int_page: safe_anchor_id}`` map from a safe-only inventory.

    Accepts a list of ``{"source_page", "anchor_id"}`` entries, a dict keyed by
    source page (value may be a slug-safe anchor id string or a dict carrying
    ``anchor_id``), an already-normalized ``{int: str}`` map (idempotent), or
    ``None``. Returns ``(anchors_or_None, warnings)``. Anchor ids are sanitized to a
    slug; an invalid/empty id is dropped (never emitted) and recorded as a closed
    ``anchor_id_invalid`` warning. A wholly unrecognized inventory type yields
    ``(None, ["input_unrecognized"])``. The input is never mutated.
    """
    if raw is None:
        return None, []
    warnings: list[str] = []
    out: dict[int, str] = {}
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                warnings.append("input_unrecognized")
                continue
            _add_anchor(entry.get("source_page"), entry.get("anchor_id"), out, warnings)
    elif isinstance(raw, dict):
        for key, value in raw.items():
            anchor_value = value
            if isinstance(value, dict):
                anchor_value = value.get("anchor_id")
            _add_anchor(key, anchor_value, out, warnings)
    else:
        return None, ["input_unrecognized"]
    return (out or None), _ordered_unique(warnings, _WARNING_ORDER, WARNINGS)


def _add_anchor(page_value: Any, anchor_value: Any, out: dict[int, str], warnings: list[str]) -> None:
    page = _coerce_positive_int(page_value)
    if page is None:
        warnings.append("input_unrecognized")
        return
    safe_anchor = _coerce_anchor_id(anchor_value)
    if safe_anchor is None:
        warnings.append("anchor_id_invalid")
        return
    out.setdefault(page, safe_anchor)


# --- Field coercion (never echo raw, untrusted input) ------------------------


def _fallback_id(index: Any) -> str:
    try:
        safe_index = int(index)
    except (TypeError, ValueError):
        safe_index = 1
    if safe_index < 1:
        safe_index = 1
    return f"asset_{safe_index:04d}"


def _coerce_asset_id(value: Any, index: Any) -> tuple[str, bool]:
    """Return ``(safe_id, was_problematic)`` — slug-safe, deterministic fallback."""
    if not isinstance(value, str):
        return _fallback_id(index), True
    slug = _SLUG_SANITIZE_RE.sub("", value)[:_MAX_ASSET_ID_LEN]
    if not slug:
        return _fallback_id(index), True
    return slug, slug != value


def _coerce_anchor_id(value: Any) -> str | None:
    """Return a slug-safe anchor id, or ``None`` if missing/empty after sanitizing."""
    if not isinstance(value, str):
        return None
    slug = _SLUG_SANITIZE_RE.sub("", value)[:_MAX_ANCHOR_ID_LEN]
    return slug or None


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def _coerce_source_page(value: Any, warnings: list[str]) -> int | None:
    """Coerce a source page to a positive int; warn when a present value is invalid."""
    page = _coerce_positive_int(value)
    if page is None and value is not None:
        warnings.append("source_page_invalid")
    return page


def _safe_provider(value: Any, warnings: list[str]) -> str:
    if value is None:
        return SOURCE_PROVIDER_UNKNOWN
    if value in SOURCE_PROVIDERS:
        return value
    warnings.append("source_provider_unrecognized")
    return SOURCE_PROVIDER_UNKNOWN


def _safe_asset_type(value: Any, warnings: list[str]) -> str:
    if value in ASSET_TYPES:
        return value
    if value is not None:
        warnings.append("asset_type_unrecognized")
    return ASSET_TYPE_UNKNOWN


def _safe_action(value: Any, warnings: list[str]) -> str:
    if value in CANDIDATE_ACTIONS:
        return value
    if value is not None:
        warnings.append("candidate_action_unrecognized")
    return ACTION_UNKNOWN


# --- Small deterministic utilities -------------------------------------------


def _ordered_unique(tokens: list[str], order: list[str], allowed: set[str]) -> list[str]:
    """Return ``tokens`` filtered to ``allowed`` and emitted in a fixed order."""
    present = {t for t in tokens if t in allowed}
    return [t for t in order if t in present]
