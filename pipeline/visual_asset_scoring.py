"""Pure, deterministic **visual asset scoring core** (Slice 46, roadmap V3).

The visual stack (``docs/VISION_ROADMAP.md`` §8) calls for a *candidate scoring*
step between the advisory manifest (V1, ``pipeline.visual_assets_manifest``) and any
guide-inclusion decision (V4+). This module is the **scoring core** for that step:
given already-sanitized, manifest-shaped asset candidates (from the local ``fitz``
extractor today, or the disabled ``chandra_local`` normalizer's asset shape), it
produces a **separate advisory scoring report** — a per-asset ``priority`` /
``include_score`` with closed-vocabulary ``reasons`` — *without ever* mutating the
manifest, changing extraction/guides/rendering, or wiring into production.

What this slice does and does NOT do
------------------------------------
- It **scores** existing ``visual_assets_manifest.json``-shaped assets and returns a
  brand-new ``visual_asset_scoring`` report dict. The scoring core never mutates the
  input manifest or any asset dict, never embeds visuals, never calls any
  provider/model/llama-server/network, and never opens or inspects any image file.
- Slice 47 adds a thin, advisory **artifact writer**
  (:func:`write_visual_asset_scoring_report` /
  :func:`write_skipped_visual_asset_scoring_report`) that persists the report as the
  exact-name sibling artifact ``visual_asset_scoring.json``, DERIVED from the
  already-written manifest. The writer is degrade-not-fail (never raises into job
  generation), does **not** mutate ``visual_assets_manifest.json``, does **not**
  change guide output / prompts / rendering / extraction / OCR routing, and is
  reached only by its exact filename (not added to generic artifact lists, export
  bundles, or UI rows).
- It deliberately keeps ``recommended_action: "unknown"`` for **every** score. The
  actual ``include_as_figure | convert_to_table | summarize_as_text | omit``
  decision (the V3 "text-replacement test") and any artifact-writing are later,
  separately-designed slices. This core only assigns *priority* and a numeric
  *include_score* — "how likely is this worth a closer look".

Purity & safety
---------------
:func:`score_visual_assets_manifest` and its helpers are pure, *total* functions of
already-sanitized input. The module imports **nothing** from PyMuPDF (``fitz``),
Tesseract, llama.cpp, a Chandra runtime/provider, Mistral/Gemini/cloud SDKs, the
Local Model Manager, renderers, the API server, the job manager, or any extraction
module — only Python stdlib (``re``, ``typing``). It **never raises** on malformed
input; it degrades to a safe ``completed`` report with closed-vocabulary warnings.

Every emitted field is a fixed token from a closed vocabulary, an int/float,
``None``, an empty list, or a deterministic slug-safe ``asset_id``. Input fields are
coerced field-by-field and **never echoed** — only the asset id, a coerced source
page, a closed-vocab provider/type, numeric scores, and closed-vocab
reason/warning tokens leave this module. Captions are used *only* as a boolean
"has caption" scoring signal and are **never** emitted. No raw path, URL, header,
token, data URI, base64 blob, image byte, raw caption/OCR text, socket path, model
path, ``mmproj`` path, executable path, or raw argv can survive into the report
even if a hostile asset record smuggles one in.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

REPORT_VERSION = 1
REPORT_KIND = "visual_asset_scoring"
REPORT_SOURCE = "visual_assets_manifest.json"

# Slice 47: exact-name advisory artifact derived from visual_assets_manifest.json.
ARTIFACT_NAME = "visual_asset_scoring.json"

# Closed skip-reason vocabulary for the persisted artifact (Slice 47). Only these
# tokens may appear as a skipped report's ``reason``; raw exceptions, paths, or
# manifest payloads are never used.
SKIP_REASON_MANIFEST_UNAVAILABLE = "visual_manifest_unavailable"
SKIP_REASON_SCORING_UNAVAILABLE = "visual_scoring_unavailable"
SKIP_REASON_WRITE_FAILED = "write_failed"
SKIP_REASONS = {
    SKIP_REASON_MANIFEST_UNAVAILABLE,
    SKIP_REASON_SCORING_UNAVAILABLE,
    SKIP_REASON_WRITE_FAILED,
}

# --- Closed vocabularies (this module owns what it is allowed to emit) --------

# Priority buckets. ``unknown`` is for assets whose type could not be recognized.
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
PRIORITY_UNKNOWN = "unknown"
PRIORITIES = {PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW, PRIORITY_UNKNOWN}

# This core never decides include/omit; every score stays "unknown".
RECOMMENDED_ACTION_UNKNOWN = "unknown"

# Closed source-provider vocabulary (mirrors the manifest/normalizer providers,
# owned locally so it cannot be widened upstream). Anything else → "unknown".
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

# Closed reason tokens. Only these may appear in a score's ``reasons`` list.
REASONS = {
    "asset_type_table",
    "asset_type_diagram",
    "asset_type_equation",
    "asset_type_extracted_figure",
    "has_bbox",
    "has_caption",
    "large_region",
    "page_has_images",
    "page_has_drawings",
    "provider_fitz_local",
    "provider_chandra_local",
    "provider_mistral_ocr",
    "low_information_signal",
    "unknown_asset_type",
    "input_sanitized",
}

# Closed warning tokens. Only these may appear in a score's / report's warnings.
WARNINGS = {
    "asset_id_missing",
    "asset_id_invalid",
    "source_page_invalid",
    "asset_type_unrecognized",
    "source_provider_unrecognized",
    "bbox_invalid",
    "signals_invalid",
    "manifest_malformed",
    "input_unrecognized",
}

# --- Scoring constants (deterministic heuristics; conservative on purpose) -----
#
# Base "worth a closer look" weight per asset type. Tables are a near-free win;
# equations/diagrams/figures are mid; a bare ``page_visual_signal`` is just a hint.
_TYPE_BASE_SCORE: dict[str, float] = {
    "table": 0.70,
    "table_region": 0.70,
    "equation_block": 0.60,
    "diagram": 0.60,
    "extracted_figure": 0.50,
    "figure": 0.50,
    "image_region": 0.35,
    "cropped_region": 0.35,
    "page_visual_signal": 0.20,
    "unknown_region": 0.0,
    ASSET_TYPE_UNKNOWN: 0.0,
}

# Type → its closed reason token (types without a specific token are omitted here).
_TYPE_REASON: dict[str, str] = {
    "table": "asset_type_table",
    "table_region": "asset_type_table",
    "equation_block": "asset_type_equation",
    "diagram": "asset_type_diagram",
    "extracted_figure": "asset_type_extracted_figure",
}

_PROVIDER_REASON: dict[str, str] = {
    SOURCE_PROVIDER_FITZ_LOCAL: "provider_fitz_local",
    SOURCE_PROVIDER_CHANDRA_LOCAL: "provider_chandra_local",
    SOURCE_PROVIDER_MISTRAL_OCR: "provider_mistral_ocr",
}

# Types that are inherently "unknown" priority regardless of score.
_UNKNOWN_PRIORITY_TYPES = {"unknown_region", ASSET_TYPE_UNKNOWN}

_BONUS_BBOX = 0.10
_BONUS_CAPTION = 0.10
_BONUS_LARGE = 0.15
_BONUS_PAGE_IMAGES = 0.10
_BONUS_PAGE_DRAWINGS = 0.10

_HIGH_THRESHOLD = 0.65
_MEDIUM_THRESHOLD = 0.40
_LARGE_REGION_RATIO = 0.20

# Deterministic emit order for reasons (subset of REASONS that may be produced).
_REASON_ORDER = [
    "asset_type_table",
    "asset_type_diagram",
    "asset_type_equation",
    "asset_type_extracted_figure",
    "unknown_asset_type",
    "provider_fitz_local",
    "provider_chandra_local",
    "provider_mistral_ocr",
    "has_bbox",
    "has_caption",
    "large_region",
    "page_has_images",
    "page_has_drawings",
    "low_information_signal",
    "input_sanitized",
]
# Deterministic emit order for warnings.
_WARNING_ORDER = [
    "input_unrecognized",
    "asset_id_missing",
    "asset_id_invalid",
    "source_page_invalid",
    "asset_type_unrecognized",
    "source_provider_unrecognized",
    "bbox_invalid",
    "signals_invalid",
]

_ASSET_ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]")
_MAX_ASSET_ID_LEN = 64


# --- Public API --------------------------------------------------------------


def score_visual_asset_candidate(asset: Any, *, page_context: Any = None) -> dict[str, Any]:
    """Score one manifest-shaped asset candidate → a safe score dict.

    Pure and total: never mutates ``asset``, never raises. ``page_context`` (an
    optional dict carrying ``page_width`` / ``page_height``) is used only as a
    fallback source of page dimensions for the ``large_region`` signal when the
    asset's own ``signals`` lack them; it is never echoed.
    """
    return _score_one(asset, index=1, page_context=page_context)


def score_visual_asset_candidates(
    assets: Any,
    *,
    page_context_by_page: Any = None,
) -> list[dict[str, Any]]:
    """Score a list of manifest-shaped asset candidates → a list of score dicts.

    Non-list input degrades to ``[]``. Each asset is scored independently and
    deterministically; ``page_context_by_page`` (optional ``{page_number: context}``)
    supplies fallback page dimensions per source page. Inputs are never mutated.
    """
    if not isinstance(assets, list):
        return []
    ctx_by_page = page_context_by_page if isinstance(page_context_by_page, dict) else {}
    scores: list[dict[str, Any]] = []
    for index, asset in enumerate(assets, start=1):
        page = _peek_source_page(asset)
        page_context = ctx_by_page.get(page) if page is not None else None
        scores.append(_score_one(asset, index=index, page_context=page_context))
    return scores


def score_visual_assets_manifest(
    manifest: Any,
    *,
    page_context_by_page: Any = None,
) -> dict[str, Any]:
    """Score a whole ``visual_assets_manifest.json``-shaped dict → a report dict.

    Returns a fresh ``visual_asset_scoring`` advisory report. Pure and total: the
    input manifest and its assets are never mutated, no file is written, and any
    malformed input degrades to a valid ``completed`` report with a closed-vocab
    ``manifest_malformed`` warning.
    """
    warnings: list[str] = []
    assets: Any = None
    if isinstance(manifest, dict):
        assets = manifest.get("assets")
        if not isinstance(assets, list):
            warnings.append("manifest_malformed")
            assets = None
    else:
        warnings.append("manifest_malformed")

    scores = score_visual_asset_candidates(assets, page_context_by_page=page_context_by_page)
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": "completed",
        "source": REPORT_SOURCE,
        "scores": scores,
        "summary": _summarize(scores),
        "warnings": warnings,
    }


# --- Artifact writer (Slice 47 — advisory, degrade-not-fail) -----------------
#
# These are the ONLY job-aware functions in this module. They persist the scoring
# report as the exact-name sibling artifact ``visual_asset_scoring.json``, derived
# from the already-written manifest. Mirrors the
# ``visual_assets_manifest.write_*``/``extraction_metadata`` degrade-to-skipped
# posture: never raise to the caller, never mutate the source manifest, never gate
# or fail generation, never touch job status / validation / clean.md.


def write_visual_asset_scoring_report(job: Any, manifest: Any) -> dict[str, Any]:
    """Persist ``visual_asset_scoring.json`` derived from a manifest dict.

    ``manifest`` is the already-written ``visual_assets_manifest.json``-shaped dict
    (the persisted, sanitized boundary output). The source manifest is **never**
    mutated. When the manifest is unavailable or not a ``completed`` manifest with a
    list of assets, a safe *skipped* report is written instead. Any write failure
    degrades to a ``write_failed`` skipped report. Returns the report dict that was
    written (advisory; the return value is informational only).
    """
    try:
        if not _is_scorable_manifest(manifest):
            return write_skipped_visual_asset_scoring_report(
                job,
                reason=SKIP_REASON_MANIFEST_UNAVAILABLE,
                safe_message="Visual assets manifest was unavailable for scoring.",
            )
        report = score_visual_assets_manifest(manifest)
        job.save_text(
            job.visual_asset_scoring_json,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
    except Exception as exc:  # never let an advisory artifact break a job
        print(
            f"Visual asset scoring skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )
        return write_skipped_visual_asset_scoring_report(
            job,
            reason=SKIP_REASON_WRITE_FAILED,
            safe_message="Visual asset scoring report could not be written.",
        )


def write_skipped_visual_asset_scoring_report(
    job: Any,
    *,
    reason: str = SKIP_REASON_SCORING_UNAVAILABLE,
    safe_message: str = "Visual asset scoring report could not be produced.",
) -> dict[str, Any]:
    """Best-effort writer for an explicit *skipped* scoring artifact.

    Uses only closed-vocabulary ``reason`` tokens and a short, safe message; never
    echoes raw exceptions, paths, or manifest payloads. Never raises.
    """
    payload = _skipped_report(reason, safe_message)
    try:
        job.save_text(
            job.visual_asset_scoring_json,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )
    except Exception:
        pass
    return payload


def _is_scorable_manifest(manifest: Any) -> bool:
    """True only for a ``completed`` manifest dict carrying a list of assets."""
    return (
        isinstance(manifest, dict)
        and manifest.get("status") == "completed"
        and isinstance(manifest.get("assets"), list)
    )


def _skipped_report(reason: Any, safe_message: Any) -> dict[str, Any]:
    safe_reason = reason if reason in SKIP_REASONS else SKIP_REASON_SCORING_UNAVAILABLE
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": "skipped",
        "source": REPORT_SOURCE,
        "reason": safe_reason,
        "safe_message": str(safe_message)[:300],
        "scores": [],
        "summary": _summarize([]),
        "warnings": [],
    }


# --- Core scoring (per-asset) ------------------------------------------------


def _score_one(asset: Any, *, index: int, page_context: Any) -> dict[str, Any]:
    warnings: list[str] = []
    reasons: list[str] = []

    if not isinstance(asset, dict):
        # A non-dict candidate carries no scorable signal; return a safe shell.
        return _build_score(
            asset_id=_fallback_id(index),
            source_page=None,
            source_provider=SOURCE_PROVIDER_UNKNOWN,
            asset_type=ASSET_TYPE_UNKNOWN,
            priority=PRIORITY_UNKNOWN,
            include_score=0.0,
            reasons=["unknown_asset_type"],
            warnings=["input_unrecognized"],
        )

    asset_id = _safe_asset_id(asset.get("asset_id"), index, warnings)
    source_page = _safe_source_page(asset, warnings)
    source_provider = _safe_provider(asset.get("source_provider"), warnings)
    asset_type = _safe_asset_type(asset.get("asset_type"), warnings)
    signals = _safe_signals(asset.get("signals"), warnings)

    bbox = _safe_bbox(asset.get("bbox"))
    if asset.get("bbox") is not None and bbox is None:
        warnings.append("bbox_invalid")

    # --- type base ---
    score = _TYPE_BASE_SCORE.get(asset_type, 0.0)
    type_reason = _TYPE_REASON.get(asset_type)
    if type_reason is not None:
        reasons.append(type_reason)
    if asset_type in _UNKNOWN_PRIORITY_TYPES:
        reasons.append("unknown_asset_type")

    # --- provider context (informational) ---
    provider_reason = _PROVIDER_REASON.get(source_provider)
    if provider_reason is not None:
        reasons.append(provider_reason)

    # --- bbox / caption signals ---
    if bbox is not None:
        reasons.append("has_bbox")
        score += _BONUS_BBOX
    if _has_caption(asset.get("caption")):
        reasons.append("has_caption")
        score += _BONUS_CAPTION

    # --- large region (needs a valid bbox AND page dimensions) ---
    if bbox is not None and _is_large_region(bbox, signals, page_context):
        reasons.append("large_region")
        score += _BONUS_LARGE

    # --- page-level visual signals ---
    images_present, drawings_present = _page_signal_presence(signals)
    if images_present:
        reasons.append("page_has_images")
        score += _BONUS_PAGE_IMAGES
    if drawings_present:
        reasons.append("page_has_drawings")
        score += _BONUS_PAGE_DRAWINGS

    # A page-level signal with no stronger evidence stays low-information.
    if asset_type == "page_visual_signal" and not images_present and not drawings_present:
        reasons.append("low_information_signal")

    # --- priority + sanitization note ---
    if asset_type in _UNKNOWN_PRIORITY_TYPES:
        score = 0.0
        priority = PRIORITY_UNKNOWN
    else:
        score = _clamp(score)
        priority = _priority_for(score)

    if warnings:
        reasons.append("input_sanitized")

    return _build_score(
        asset_id=asset_id,
        source_page=source_page,
        source_provider=source_provider,
        asset_type=asset_type,
        priority=priority,
        include_score=round(score, 3),
        reasons=reasons,
        warnings=warnings,
    )


def _build_score(
    *,
    asset_id: str,
    source_page: int | None,
    source_provider: str,
    asset_type: str,
    priority: str,
    include_score: float,
    reasons: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "source_page": source_page,
        "source_provider": source_provider,
        "asset_type": asset_type,
        "recommended_action": RECOMMENDED_ACTION_UNKNOWN,
        "priority": priority,
        "include_score": include_score,
        "reasons": _ordered_unique(reasons, _REASON_ORDER, REASONS),
        "warnings": _ordered_unique(warnings, _WARNING_ORDER, WARNINGS),
    }


# --- Summary -----------------------------------------------------------------


def _summarize(scores: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {PRIORITY_HIGH: 0, PRIORITY_MEDIUM: 0, PRIORITY_LOW: 0, PRIORITY_UNKNOWN: 0}
    for score in scores:
        priority = score.get("priority")
        if priority in counts:
            counts[priority] += 1
    return {
        "asset_count": len(scores),
        "high_priority_count": counts[PRIORITY_HIGH],
        "medium_priority_count": counts[PRIORITY_MEDIUM],
        "low_priority_count": counts[PRIORITY_LOW],
        "unknown_priority_count": counts[PRIORITY_UNKNOWN],
    }


# --- Field coercion (never echo raw, untrusted input) ------------------------


def _fallback_id(index: int) -> str:
    try:
        safe_index = int(index)
    except (TypeError, ValueError):
        safe_index = 1
    if safe_index < 1:
        safe_index = 1
    return f"asset_{safe_index:04d}"


def _safe_asset_id(value: Any, index: int, warnings: list[str]) -> str:
    if not isinstance(value, str):
        warnings.append("asset_id_missing")
        return _fallback_id(index)
    slug = _ASSET_ID_SANITIZE_RE.sub("", value)[:_MAX_ASSET_ID_LEN]
    if not slug:
        warnings.append("asset_id_invalid")
        return _fallback_id(index)
    if slug != value:
        # Present but carried characters outside the slug-safe set.
        warnings.append("asset_id_invalid")
    return slug


def _peek_source_page(asset: Any) -> int | None:
    """Best-effort page lookup for context selection (no warnings emitted)."""
    if not isinstance(asset, dict):
        return None
    return _coerce_positive_int(asset.get("source_page"))


def _safe_source_page(asset: dict[str, Any], warnings: list[str]) -> int | None:
    if "source_page" not in asset:
        return None
    page = _coerce_positive_int(asset.get("source_page"))
    if page is None:
        warnings.append("source_page_invalid")
    return page


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


def _safe_asset_type(value: Any, warnings: list[str]) -> str:
    if value in ASSET_TYPES:
        return value
    if value is not None:
        warnings.append("asset_type_unrecognized")
    return ASSET_TYPE_UNKNOWN


def _safe_signals(value: Any, warnings: list[str]) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    warnings.append("signals_invalid")
    return {}


def _has_caption(value: Any) -> bool:
    # Caption is used ONLY as a boolean scoring signal; it is never emitted.
    return isinstance(value, str) and bool(value.strip())


def _page_signal_presence(signals: dict[str, Any]) -> tuple[bool, bool]:
    image_count = _safe_count(signals.get("image_object_count"))
    drawing_count = _safe_count(signals.get("drawing_object_count"))
    has_images = signals.get("has_images") is True
    has_drawings = signals.get("has_drawings") is True
    images_present = has_images or (image_count is not None and image_count > 0)
    drawings_present = has_drawings or (drawing_count is not None and drawing_count > 0)
    return images_present, drawings_present


def _is_large_region(bbox: list[float], signals: dict[str, Any], page_context: Any) -> bool:
    width = _safe_dimension(signals.get("page_width"))
    height = _safe_dimension(signals.get("page_height"))
    if (width is None or height is None) and isinstance(page_context, dict):
        if width is None:
            width = _safe_dimension(page_context.get("page_width"))
        if height is None:
            height = _safe_dimension(page_context.get("page_height"))
    if not width or not height:
        return False
    x0, y0, x1, y1 = bbox
    area = (x1 - x0) * (y1 - y0)
    page_area = width * height
    if page_area <= 0:
        return False
    return (area / page_area) >= _LARGE_REGION_RATIO


def _safe_count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _safe_dimension(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf guard
        return None
    return number if number > 0 else None


def _safe_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    coords: list[float] = []
    for item in value:
        if isinstance(item, bool):
            return None
        try:
            number = float(item)
        except (TypeError, ValueError):
            return None
        if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
            return None
        coords.append(round(max(0.0, number), 2))
    x0, y0, x1, y1 = coords
    if x1 <= x0 or y1 <= y0:  # must be a well-ordered, positive-area box
        return None
    return [x0, y0, x1, y1]


# --- Small deterministic utilities -------------------------------------------


def _clamp(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _priority_for(score: float) -> str:
    if score >= _HIGH_THRESHOLD:
        return PRIORITY_HIGH
    if score >= _MEDIUM_THRESHOLD:
        return PRIORITY_MEDIUM
    return PRIORITY_LOW


def _ordered_unique(tokens: list[str], order: list[str], allowed: set[str]) -> list[str]:
    """Return ``tokens`` filtered to ``allowed`` and emitted in a fixed order."""
    present = {t for t in tokens if t in allowed}
    return [t for t in order if t in present]
