"""Pure, deterministic **visual replacement planner core** (Slice 48, roadmap V3).

The visual stack (``docs/VISION_ROADMAP.md`` §8) goes: advisory manifest (V1,
``pipeline.visual_assets_manifest``) → candidate *scoring* (V3 core,
``pipeline.visual_asset_scoring`` + the Slice 47 ``visual_asset_scoring.json``
artifact) → an eventual guide-inclusion decision (V4+). This module is the next
*pure planning core* on that path: given an already-sanitized
``visual_asset_scoring.json``-shaped scoring report (and, optionally, a
``visual_assets_manifest.json``-shaped manifest for a presence-only cross-check),
it returns a **separate advisory replacement plan** — a per-asset
``candidate_action`` / ``placement`` / ``priority`` with closed-vocabulary
``reasons`` — *without ever* mutating the scoring report or manifest, persisting an
artifact, embedding visuals, changing extraction/guides/rendering, or wiring into
production.

What this slice does and does NOT do
------------------------------------
- It **plans** ``candidate_*`` actions for already-scored, manifest/scoring-shaped
  assets and returns a brand-new ``visual_replacement_plan`` report dict. The pure
  planning core never mutates the scoring report, the manifest, or any item/asset
  dict, never embeds visuals, never calls any provider/model/llama-server/network,
  and never opens or inspects any image file.
- Slice 49 adds a thin, advisory **artifact writer**
  (:func:`write_visual_replacement_plan_report` /
  :func:`write_skipped_visual_replacement_plan_report`) that persists the report as
  the exact-name sibling artifact ``visual_replacement_plan.json``, DERIVED from the
  already-written ``visual_asset_scoring.json`` report (with an optional
  presence-only manifest cross-check). The writer is degrade-not-fail (never raises
  into job generation), does **not** mutate ``visual_asset_scoring.json`` or
  ``visual_assets_manifest.json``, does **not** change guide output / prompts /
  rendering / extraction / OCR routing, makes **no** production include/omit
  decision, and is reached only by its exact filename (not added to generic
  artifact lists, export bundles, or UI rows).
- The ``candidate_action`` it assigns is **advisory only** — it is a *candidate*
  (``candidate_include_as_figure`` / ``candidate_convert_to_table`` /
  ``candidate_summarize_as_text`` / ``review_only`` / ``unknown``), never a binding
  include/omit decision. The real "text-replacement test" and any guide embedding
  are later, separately-designed slices. Generated guides are unaffected.

Chandra independence
--------------------
This is a provider-agnostic visual-stack slice, **not** Chandra integration. A
``chandra_local`` item may be *planned* only as advisory, and every such item
carries the closed reason ``chandra_blocked`` because Slice 45 recorded the Chandra
live harness as ``status:not_run`` (``operator_input_not_supplied``) — Chandra
*extraction* integration remains blocked until a live harness pass is recorded.

Purity & safety
---------------
:func:`plan_visual_replacement_candidate`, :func:`plan_visual_replacement_candidates`
and :func:`build_visual_replacement_plan` are pure, *total* functions of already-
sanitized input. The module imports **nothing** from PyMuPDF (``fitz``), Tesseract,
llama.cpp, a Chandra runtime/provider, Mistral/Gemini/cloud SDKs, the Local Model
Manager, renderers, the API server, the job manager, or any extraction/run-job
module — only Python stdlib (``json``, ``re``, ``sys``, ``typing``); the Slice 49
artifact writers take a duck-typed ``job`` and call only its ``save_text`` /
``visual_replacement_plan_json`` members. The pure core **never raises** on
malformed input; it degrades to a safe ``completed`` report with closed-vocabulary
warnings, and the writers degrade to a safe ``skipped`` report rather than failing
a job.

Every emitted field is a fixed token from a closed vocabulary, an int, ``None``, an
empty list, or a deterministic slug-safe ``asset_id``. Input fields are coerced
field-by-field and **never echoed** — only a sanitized asset id, a coerced source
page, and closed-vocab provider/type/priority/action/placement tokens leave this
module. No raw caption, raw source/OCR text, provider/model payload, image byte,
data URI, base64 blob, path, URL, header, token, socket path, model/``mmproj``
path, executable path, or raw argv can survive into the plan even if a hostile
record smuggles one in. A manifest cross-reference contributes **presence only**
(a ``has_manifest_match`` / ``missing_manifest_match`` reason); no manifest field
is read into the output.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

REPORT_VERSION = 1
REPORT_KIND = "visual_replacement_plan"
REPORT_SOURCE = "visual_asset_scoring.json"

# Slice 49: exact-name advisory artifact derived from visual_asset_scoring.json
# (with an optional presence-only cross-check against visual_assets_manifest.json).
ARTIFACT_NAME = "visual_replacement_plan.json"

# Closed skip-reason vocabulary for the persisted artifact (Slice 49). Only these
# tokens may appear as a skipped report's ``reason``; raw exceptions, paths,
# scoring payloads, or manifest payloads are never used.
SKIP_REASON_SCORING_UNAVAILABLE = "visual_scoring_unavailable"
SKIP_REASON_MANIFEST_UNAVAILABLE = "visual_manifest_unavailable"
SKIP_REASON_PLANNING_UNAVAILABLE = "visual_replacement_planning_unavailable"
SKIP_REASON_WRITE_FAILED = "write_failed"
SKIP_REASONS = {
    SKIP_REASON_SCORING_UNAVAILABLE,
    SKIP_REASON_MANIFEST_UNAVAILABLE,
    SKIP_REASON_PLANNING_UNAVAILABLE,
    SKIP_REASON_WRITE_FAILED,
}

# --- Closed vocabularies (this module owns what it is allowed to emit) --------

# Advisory candidate actions. Never a binding include/omit decision.
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

# Advisory placement. Only ever a page reference or unknown — never derived from
# private/raw text or a real layout coordinate.
PLACEMENT_SOURCE_PAGE_REFERENCE = "source_page_reference"
PLACEMENT_UNKNOWN = "unknown"
PLACEMENTS = {PLACEMENT_SOURCE_PAGE_REFERENCE, PLACEMENT_UNKNOWN}

# Priority buckets (mirror the scoring core's; owned locally so they cannot be
# widened upstream). Anything else → "unknown".
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
PRIORITY_UNKNOWN = "unknown"
PRIORITIES = {PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW, PRIORITY_UNKNOWN}

# Closed source-provider vocabulary (mirrors the scoring core / manifest). Anything
# else → "unknown".
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

# Closed asset-type vocabulary (union of the manifest's and the Chandra
# normalizer's emitted types, plus reserved buckets). Anything else → "unknown".
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
    "score_high",
    "score_medium",
    "score_low",
    "asset_type_diagram",
    "asset_type_figure",
    "asset_type_table",
    "asset_type_equation",
    "asset_type_page_signal",
    "has_manifest_match",
    "missing_manifest_match",
    "review_required",
    "chandra_blocked",
    "low_information_signal",
    "unknown_asset_type",
    "input_sanitized",
}

# Closed warning tokens. Only these may appear in an item's / report's warnings.
WARNINGS = {
    "scoring_report_malformed",
    "score_item_malformed",
    "asset_lookup_missing",
    "asset_id_missing",
    "asset_id_invalid",
    "asset_type_unrecognized",
    "source_provider_unrecognized",
    "priority_unrecognized",
    "candidate_action_unresolved",
    "input_unrecognized",
}

# --- Planning constants (deterministic; conservative on purpose) --------------

# Asset-type families that drive a candidate action at high/medium priority.
_FIGURE_TYPES = {"diagram", "figure", "image_region", "cropped_region", "extracted_figure"}
_TABLE_TYPES = {"table", "table_region"}
_EQUATION_TYPES = {"equation_block"}
# "Unknown visual block" tokens that are *legitimately* unknown (not coerced from an
# unrecognized type): summarizing as text is safer than embedding an unknown crop.
_UNKNOWN_VISUAL_TYPES = {"unknown_region", ASSET_TYPE_UNKNOWN}

# Asset-type → its closed reason token.
_TYPE_REASON: dict[str, str] = {
    "diagram": "asset_type_diagram",
    "figure": "asset_type_figure",
    "extracted_figure": "asset_type_figure",
    "image_region": "asset_type_figure",
    "cropped_region": "asset_type_figure",
    "table": "asset_type_table",
    "table_region": "asset_type_table",
    "equation_block": "asset_type_equation",
    "page_visual_signal": "asset_type_page_signal",
}

# Priority → its closed reason token.
_PRIORITY_REASON: dict[str, str] = {
    PRIORITY_HIGH: "score_high",
    PRIORITY_MEDIUM: "score_medium",
    PRIORITY_LOW: "score_low",
}

# Deterministic emit order for reasons / warnings (subsets that may be produced).
_REASON_ORDER = [
    "score_high",
    "score_medium",
    "score_low",
    "asset_type_table",
    "asset_type_diagram",
    "asset_type_figure",
    "asset_type_equation",
    "asset_type_page_signal",
    "unknown_asset_type",
    "low_information_signal",
    "chandra_blocked",
    "has_manifest_match",
    "missing_manifest_match",
    "review_required",
    "input_sanitized",
]
_WARNING_ORDER = [
    "scoring_report_malformed",
    "score_item_malformed",
    "input_unrecognized",
    "asset_id_missing",
    "asset_id_invalid",
    "asset_type_unrecognized",
    "source_provider_unrecognized",
    "priority_unrecognized",
    "asset_lookup_missing",
    "candidate_action_unresolved",
]

_ASSET_ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]")
_MAX_ASSET_ID_LEN = 64


# --- Public API --------------------------------------------------------------


def plan_visual_replacement_candidate(score: Any, *, asset: Any = None) -> dict[str, Any]:
    """Plan one ``visual_asset_scoring``-shaped score item → a safe plan item dict.

    Pure and total: never mutates ``score`` or ``asset``, never raises. ``asset`` is
    an optional manifest-shaped asset dict used **for presence only** (it adds a
    ``has_manifest_match`` reason); no manifest field is read into the output.
    """
    return _plan_one(score, index=1, asset=asset, lookup_attempted=asset is not None)


def plan_visual_replacement_candidates(
    scores: Any,
    *,
    assets_by_id: Any = None,
) -> list[dict[str, Any]]:
    """Plan a list of score items → a list of plan item dicts.

    Non-list input degrades to ``[]``. ``assets_by_id`` (optional
    ``{safe_asset_id: asset}`` map) enables a presence-only manifest cross-check:
    when supplied, a missing match adds ``missing_manifest_match`` /
    ``asset_lookup_missing`` and a hit adds ``has_manifest_match``. Inputs are never
    mutated; no manifest field is echoed.
    """
    if not isinstance(scores, list):
        return []
    lookup = assets_by_id if isinstance(assets_by_id, dict) else None
    attempted = lookup is not None
    items: list[dict[str, Any]] = []
    for index, score in enumerate(scores, start=1):
        asset = None
        if lookup is not None and isinstance(score, dict):
            safe_id, _ = _coerce_asset_id(score.get("asset_id"), index)
            asset = lookup.get(safe_id)
        items.append(_plan_one(score, index=index, asset=asset, lookup_attempted=attempted))
    return items


def build_visual_replacement_plan(
    scoring_report: Any,
    *,
    manifest: Any = None,
) -> dict[str, Any]:
    """Build a ``visual_replacement_plan`` report from a scoring report dict.

    Returns a fresh advisory plan report. Pure and total: the input scoring report
    and manifest (and their items/assets) are never mutated, no file is written, and
    any malformed input degrades to a valid ``completed`` report with a closed-vocab
    ``scoring_report_malformed`` warning. ``manifest`` (optional,
    ``visual_assets_manifest.json``-shaped) is used only for a presence-only
    cross-check; no manifest field is read into the output.
    """
    warnings: list[str] = []
    scores: Any = None
    if isinstance(scoring_report, dict):
        scores = scoring_report.get("scores")
        if not isinstance(scores, list):
            warnings.append("scoring_report_malformed")
            scores = None
    else:
        warnings.append("scoring_report_malformed")

    assets_by_id = _build_assets_by_id(manifest)
    items = plan_visual_replacement_candidates(scores, assets_by_id=assets_by_id)
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": "completed",
        "source": REPORT_SOURCE,
        "items": items,
        "summary": _summarize(items),
        "warnings": _ordered_unique(warnings, _WARNING_ORDER, WARNINGS),
    }


# --- Artifact writer (Slice 49 — advisory, degrade-not-fail) -----------------
#
# These are the ONLY job-aware functions in this module. They persist the
# replacement plan as the exact-name sibling artifact
# ``visual_replacement_plan.json``, DERIVED from the already-written
# ``visual_asset_scoring.json`` report (with an optional presence-only manifest
# cross-check). Mirrors the Slice 47 scoring-writer / ``extraction_metadata``
# degrade-to-skipped posture: never raise to the caller, never mutate the source
# scoring report or manifest, never gate or fail generation, never touch job
# status / validation / clean.md, and never embed visuals.


def write_visual_replacement_plan_report(
    job: Any,
    scoring_report: Any,
    *,
    manifest: Any = None,
) -> dict[str, Any]:
    """Persist ``visual_replacement_plan.json`` derived from a scoring report dict.

    ``scoring_report`` is the ``visual_asset_scoring.json``-shaped dict produced by
    the Slice 47 scoring writer (the persisted, sanitized boundary output). The
    source scoring report and ``manifest`` are **never** mutated. ``manifest``
    (optional, ``visual_assets_manifest.json``-shaped) is used only for a
    presence-only asset-id cross-check; no manifest field is read into the output.

    When the scoring report is unavailable or not a ``completed`` report with a list
    of scores, a safe *skipped* plan is written instead. Any write failure degrades
    to a ``write_failed`` skipped plan. Returns the report dict that was written
    (advisory; the return value is informational only).
    """
    try:
        if not _is_plannable_scoring_report(scoring_report):
            return write_skipped_visual_replacement_plan_report(
                job,
                reason=SKIP_REASON_SCORING_UNAVAILABLE,
                safe_message="Visual asset scoring report was unavailable for planning.",
            )
        report = build_visual_replacement_plan(scoring_report, manifest=manifest)
        job.save_text(
            job.visual_replacement_plan_json,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
    except Exception as exc:  # never let an advisory artifact break a job
        print(
            f"Visual replacement planning skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )
        return write_skipped_visual_replacement_plan_report(
            job,
            reason=SKIP_REASON_WRITE_FAILED,
            safe_message="Visual replacement plan could not be written.",
        )


def write_skipped_visual_replacement_plan_report(
    job: Any,
    *,
    reason: str = SKIP_REASON_PLANNING_UNAVAILABLE,
    safe_message: str = "Visual replacement plan could not be produced.",
) -> dict[str, Any]:
    """Best-effort writer for an explicit *skipped* replacement-plan artifact.

    Uses only closed-vocabulary ``reason`` tokens and a short, safe message; never
    echoes raw exceptions, paths, scoring payloads, or manifest payloads. Never
    raises.
    """
    payload = _skipped_report(reason, safe_message)
    try:
        job.save_text(
            job.visual_replacement_plan_json,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )
    except Exception:
        pass
    return payload


def _is_plannable_scoring_report(scoring_report: Any) -> bool:
    """True only for a ``completed`` scoring report dict carrying a list of scores."""
    return (
        isinstance(scoring_report, dict)
        and scoring_report.get("status") == "completed"
        and isinstance(scoring_report.get("scores"), list)
    )


def _skipped_report(reason: Any, safe_message: Any) -> dict[str, Any]:
    safe_reason = reason if reason in SKIP_REASONS else SKIP_REASON_PLANNING_UNAVAILABLE
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": "skipped",
        "source": REPORT_SOURCE,
        "reason": safe_reason,
        "safe_message": str(safe_message)[:300],
        "items": [],
        "summary": _summarize([]),
        "warnings": [],
    }


# --- Core planning (per-item) ------------------------------------------------


def _plan_one(score: Any, *, index: int, asset: Any, lookup_attempted: bool) -> dict[str, Any]:
    warnings: list[str] = []
    reasons: list[str] = []

    if not isinstance(score, dict):
        # A non-dict score item carries nothing plannable; return a safe shell.
        return _build_item(
            asset_id=_fallback_id(index),
            source_page=None,
            source_provider=SOURCE_PROVIDER_UNKNOWN,
            asset_type=ASSET_TYPE_UNKNOWN,
            priority=PRIORITY_UNKNOWN,
            candidate_action=ACTION_UNKNOWN,
            placement=PLACEMENT_UNKNOWN,
            reasons=["input_sanitized"],
            warnings=["score_item_malformed"],
        )

    asset_id, _ = _coerce_asset_id(score.get("asset_id"), index)
    if not isinstance(score.get("asset_id"), str):
        warnings.append("asset_id_missing")
    elif asset_id == _fallback_id(index) or asset_id != score.get("asset_id"):
        warnings.append("asset_id_invalid")

    source_page = _coerce_positive_int(score.get("source_page"))
    source_provider = _safe_provider(score.get("source_provider"), warnings)
    asset_type, type_unrecognized = _safe_asset_type(score.get("asset_type"), warnings)
    priority = _safe_priority(score.get("priority"), warnings)

    # --- priority reason ---
    priority_reason = _PRIORITY_REASON.get(priority)
    if priority_reason is not None:
        reasons.append(priority_reason)

    # --- asset-type reason ---
    type_reason = _TYPE_REASON.get(asset_type)
    if type_reason is not None:
        reasons.append(type_reason)
    if asset_type in _UNKNOWN_VISUAL_TYPES:
        reasons.append("unknown_asset_type")
    if asset_type == "page_visual_signal":
        reasons.append("low_information_signal")

    # --- candidate action (advisory only) ---
    candidate_action = _decide_action(priority, asset_type, type_unrecognized, warnings)
    if candidate_action == ACTION_REVIEW_ONLY:
        reasons.append("review_required")

    # --- provider note: Chandra stays advisory + blocked (Slice 45 not_run) ---
    if source_provider == SOURCE_PROVIDER_CHANDRA_LOCAL:
        reasons.append("chandra_blocked")

    # --- presence-only manifest cross-check ---
    if asset is not None and isinstance(asset, dict):
        reasons.append("has_manifest_match")
    elif lookup_attempted:
        reasons.append("missing_manifest_match")
        warnings.append("asset_lookup_missing")

    # --- placement: a page reference only for an actionable candidate ---
    placement = _placement_for(candidate_action, source_page)

    if warnings:
        reasons.append("input_sanitized")

    return _build_item(
        asset_id=asset_id,
        source_page=source_page,
        source_provider=source_provider,
        asset_type=asset_type,
        priority=priority,
        candidate_action=candidate_action,
        placement=placement,
        reasons=reasons,
        warnings=warnings,
    )


def _decide_action(
    priority: str,
    asset_type: str,
    type_unrecognized: bool,
    warnings: list[str],
) -> str:
    """Deterministic, conservative candidate action. Advisory only."""
    if priority == PRIORITY_UNKNOWN:
        return ACTION_UNKNOWN
    if priority == PRIORITY_LOW:
        return ACTION_REVIEW_ONLY
    # priority is high or medium below.
    if asset_type in _FIGURE_TYPES:
        return ACTION_INCLUDE_AS_FIGURE
    if asset_type in _TABLE_TYPES:
        return ACTION_CONVERT_TO_TABLE
    if asset_type in _EQUATION_TYPES:
        return ACTION_SUMMARIZE_AS_TEXT
    if asset_type == "page_visual_signal":
        # A bare page-level signal is not a real asset to embed; review it.
        return ACTION_REVIEW_ONLY
    if asset_type in _UNKNOWN_VISUAL_TYPES and not type_unrecognized:
        # Legitimately-unknown visual block: summarizing is safer than embedding.
        return ACTION_SUMMARIZE_AS_TEXT
    # Recognized-but-unmapped, or an unrecognized/coerced type at actionable
    # priority: do not guess an embedding — fall back to review.
    warnings.append("candidate_action_unresolved")
    return ACTION_REVIEW_ONLY


def _placement_for(candidate_action: str, source_page: int | None) -> str:
    actionable = candidate_action in {
        ACTION_INCLUDE_AS_FIGURE,
        ACTION_CONVERT_TO_TABLE,
        ACTION_SUMMARIZE_AS_TEXT,
    }
    if actionable and source_page is not None:
        return PLACEMENT_SOURCE_PAGE_REFERENCE
    return PLACEMENT_UNKNOWN


def _build_item(
    *,
    asset_id: str,
    source_page: int | None,
    source_provider: str,
    asset_type: str,
    priority: str,
    candidate_action: str,
    placement: str,
    reasons: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "source_page": source_page,
        "source_provider": source_provider,
        "asset_type": asset_type,
        "priority": priority,
        "candidate_action": candidate_action,
        "placement": placement,
        "reasons": _ordered_unique(reasons, _REASON_ORDER, REASONS),
        "warnings": _ordered_unique(warnings, _WARNING_ORDER, WARNINGS),
    }


# --- Summary -----------------------------------------------------------------


def _summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        ACTION_INCLUDE_AS_FIGURE: 0,
        ACTION_CONVERT_TO_TABLE: 0,
        ACTION_SUMMARIZE_AS_TEXT: 0,
        ACTION_REVIEW_ONLY: 0,
        ACTION_UNKNOWN: 0,
    }
    for item in items:
        action = item.get("candidate_action")
        if action in counts:
            counts[action] += 1
    return {
        "item_count": len(items),
        "candidate_include_as_figure_count": counts[ACTION_INCLUDE_AS_FIGURE],
        "candidate_convert_to_table_count": counts[ACTION_CONVERT_TO_TABLE],
        "candidate_summarize_as_text_count": counts[ACTION_SUMMARIZE_AS_TEXT],
        "review_only_count": counts[ACTION_REVIEW_ONLY],
        "unknown_count": counts[ACTION_UNKNOWN],
    }


# --- Manifest cross-reference (presence only) --------------------------------


def _build_assets_by_id(manifest: Any) -> dict[str, Any] | None:
    """Build a ``{safe_asset_id: asset}`` lookup from a manifest dict.

    Returns ``None`` when no usable manifest is supplied. Keys are sanitized to the
    same slug-safe space the planner coerces score ids into, so a presence check can
    match. The asset dicts are kept only to answer "is there a match?" — no field is
    ever read into plan output.
    """
    if not isinstance(manifest, dict):
        return None
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        return None
    lookup: dict[str, Any] = {}
    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            continue
        safe_id, _ = _coerce_asset_id(asset.get("asset_id"), index)
        lookup.setdefault(safe_id, asset)
    return lookup


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
    slug = _ASSET_ID_SANITIZE_RE.sub("", value)[:_MAX_ASSET_ID_LEN]
    if not slug:
        return _fallback_id(index), True
    return slug, slug != value


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def _safe_provider(value: Any, warnings: list[str]) -> str:
    if value is None:
        return SOURCE_PROVIDER_UNKNOWN
    if value in SOURCE_PROVIDERS:
        return value
    warnings.append("source_provider_unrecognized")
    return SOURCE_PROVIDER_UNKNOWN


def _safe_asset_type(value: Any, warnings: list[str]) -> tuple[str, bool]:
    """Return ``(safe_type, was_unrecognized)``.

    ``was_unrecognized`` is ``True`` only when a non-``None`` value was present but
    outside the closed vocabulary (so it was coerced to ``unknown``); a missing type
    coerces to ``unknown`` silently, like the scoring core.
    """
    if value in ASSET_TYPES:
        return value, False
    if value is not None:
        warnings.append("asset_type_unrecognized")
        return ASSET_TYPE_UNKNOWN, True
    return ASSET_TYPE_UNKNOWN, False


def _safe_priority(value: Any, warnings: list[str]) -> str:
    if value in PRIORITIES:
        return value
    if value is not None:
        warnings.append("priority_unrecognized")
    return PRIORITY_UNKNOWN


# --- Small deterministic utilities -------------------------------------------


def _ordered_unique(tokens: list[str], order: list[str], allowed: set[str]) -> list[str]:
    """Return ``tokens`` filtered to ``allowed`` and emitted in a fixed order."""
    present = {t for t in tokens if t in allowed}
    return [t for t in order if t in present]
