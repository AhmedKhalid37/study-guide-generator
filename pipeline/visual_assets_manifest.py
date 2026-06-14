"""Provider-agnostic **visual assets manifest** schema/boundary (Slice 38).

This is the *normalization boundary* that Slice 36's visual/cost roadmap called
for: a single, safe artifact shape that every present and future visual provider
(``fitz_local`` today; ``chandra_local`` / ``mistral_ocr`` / ``vlm_*`` later) maps
into. It is **advisory only** and changes nothing about extraction, OCR routing,
prompts, guide text, or rendering.

What this slice does and does NOT do
------------------------------------
- It **builds the manifest schema** and populates it *only* from page-level visual
  signals already collected for ``extraction_metadata.json`` (Slice 30/31/34):
  page number, page dimensions, image/drawing object counts, ``has_images`` /
  ``has_drawings``, advisory ``classification`` and (when present) the local OCR
  ``ocr_route_action``.
- It does **not** open or inspect any PDF beyond what extraction metadata already
  measured, **not** crop/rasterize/segment images, **not** write any image files
  or raw image bytes, **not** embed visuals into guides, **not** score candidates,
  **not** dedupe, and **not** call any provider or network.

Because nothing is cropped in this slice, each manifest asset is a *page-level
visual candidate* (``asset_type: "page_visual_signal"``) — it represents "this
page carries a visual signal worth a closer look later", **not** a real extracted
figure. Actual local figure extraction / cropping / candidate scoring / Chandra
verification / Mistral skeleton are later slices.

Purity & safety
---------------
:func:`build_visual_assets_manifest` is a pure function of already-sanitized
extraction-metadata source records. It imports **nothing** from PyMuPDF (``fitz``),
Tesseract, Mistral, Gemini, Chandra, or any VLM/provider SDK — only stdlib typing
and the pure, stdlib-only ``pipeline.page_selection_model`` (Slice 82's material
page-filter decision; no provider/network/fitz import comes with it).
Every emitted field is a fixed token from a closed vocabulary, an int/float,
``None``, an empty dict, or a deterministic ``asset_id``. Inputs are coerced
field-by-field and never echoed, so no raw path, absolute host path, image byte,
raw PDF object, provider payload, OCR error, key/token/header, URL, socket path, or
argv can survive into the manifest even if a hostile record smuggles one in.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

from pipeline.page_selection_model import (
    VISUAL_FILTER_NO_MATCHING_PAGES,
    VISUAL_FILTER_TOKENS,
    page_is_in_material_selection,
)

ARTIFACT_NAME = "visual_assets_manifest.json"
MANIFEST_VERSION = 1

# --- Closed vocabularies (this module owns what it is allowed to emit) -------
#
# These are intentionally self-contained: the manifest coerces every value to one
# of its own fixed tokens (or a safe default), so it can never be widened or
# poisoned by an upstream change or a smuggled record. Future-reserved values are
# documented but MUST NOT be emitted by this slice.

# Only the local PyMuPDF page-signal provider exists today. Future-safe (reserved,
# not emitted here): "chandra_local", "mistral_ocr", and "vlm_*".
SOURCE_PROVIDER_FITZ_LOCAL = "fitz_local"
SOURCE_PROVIDERS = {SOURCE_PROVIDER_FITZ_LOCAL}

# Conservative asset types. ``page_visual_signal`` is the page-level signal from
# Slice 38; ``extracted_figure`` is a real cropped region from Slice 40's local
# fitz extractor. Still reserved-for-later (NOT emitted yet): "cropped_region",
# "table_region", "decorative".
ASSET_TYPE_PAGE_VISUAL_SIGNAL = "page_visual_signal"
ASSET_TYPE_EXTRACTED_FIGURE = "extracted_figure"
ASSET_TYPES = {ASSET_TYPE_PAGE_VISUAL_SIGNAL, ASSET_TYPE_EXTRACTED_FIGURE}

# An ``extracted_figure`` image reference is ALWAYS a fixed-shape relative path
# ("assets/<slug>.png"). Anything that does not match exactly is dropped to None,
# so no absolute / host / traversal path can survive into the manifest.
_IMAGE_REF_RE = re.compile(r"^assets/[A-Za-z0-9_]+\.png$")
# Slug characters allowed in a re-derived ``asset_id`` (defence in depth: even if
# the extractor is changed, the manifest only ever persists this character set).
_ASSET_ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_]")
_MAX_ASSET_ID_LEN = 64

# Default advisory action only. Reserved-for-later candidate-scoring values (NOT
# emitted this slice): "include_as_figure", "convert_to_table",
# "summarize_as_text", "omit".
RECOMMENDED_ACTION_UNKNOWN = "unknown"
RECOMMENDED_ACTIONS = {RECOMMENDED_ACTION_UNKNOWN}

# Closed page-classification vocabulary mirrored from
# pipeline.extraction_metadata (Slice 31). Owned locally so the manifest cannot be
# poisoned or widened by an upstream change; anything else coerces to "unknown".
_CLASSIFICATIONS = {
    "embedded_text",
    "ocr_fallback",
    "likely_scanned",
    "blank_or_low_text",
    "mixed",
    "unknown",
    "error",
}

# Closed OCR-route action vocabulary mirrored from pipeline.ocr_routing (Slice 34).
# Carried through only for context; anything else coerces to "unknown".
_OCR_ROUTE_ACTIONS = {
    "use_embedded_text",
    "use_local_ocr",
    "cloud_ocr_candidate",
    "skip_ocr",
    "unknown",
}

# Fixed manifest-level warning tokens (safe, closed). The base two are reserved
# (not emitted today). Slice 82 adds the material page-filter tokens, emitted when
# an active material selection drops visual candidates from excluded pages.
WARNINGS = {"source_unavailable", "no_visual_signals", *VISUAL_FILTER_TOKENS}


def build_visual_assets_manifest(
    sources: Any,
    extracted_assets: Any = None,
    *,
    page_filters: Any = None,
) -> dict[str, Any]:
    """Pure builder: sanitized extraction-metadata ``sources`` → manifest dict.

    ``sources`` is the same list of per-source records persisted in
    ``extraction_metadata.json`` (each a dict with a ``pages`` list of already
    sanitized page records). One *page-level visual candidate*
    (``page_visual_signal``) is emitted per page that carries a positive image or
    drawing signal — a page with BOTH images and drawings yields exactly one
    candidate (the signals dict records both).

    ``extracted_assets`` (Slice 40, optional) is the list of *real cropped figures*
    produced by :mod:`pipeline.visual_asset_extractor`. Each is **re-sanitised
    field-by-field here** (asset id slug, ``extracted_figure`` type, finite/ordered
    ``bbox``, fixed-shape relative ``image_ref``, numeric signals) before it joins
    the manifest, so the manifest — not the fitz extractor — remains the security
    boundary and cannot be poisoned. When ``None``/empty the output is
    byte-identical to Slice 38.

    ``page_filters`` (Slice 82, optional) applies the Full Material Coverage page
    selection to the page-level visual candidates. It is a list aligned by index
    with ``sources``; each entry is either ``None`` (no active material filter for
    that source — existing behaviour) or a collection of positive 1-based page ints
    (the *effective* post-material allowed set Slice 81 already computed for that
    attachment, which is itself a subset of any ``page_selections`` universe). A
    page candidate whose ``source_page`` is not in its source's allowed set is
    dropped before it becomes a manifest record; closed filter tokens record that a
    drop happened. ``None`` / absent ⇒ output is byte-identical to before Slice 82.

    Pure and total: never raises, never inspects a PDF, never crops, never calls a
    provider, never opens an image file. On any unexpected input it degrades to an
    empty-but-valid manifest.
    """
    try:
        return _build_inner(sources, extracted_assets, page_filters)
    except Exception:
        return _empty_manifest()


def _build_inner(
    sources: Any, extracted_assets: Any, page_filters: Any = None
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    pages_with_signals = 0
    filter_warnings: set[str] = set()
    filtered_count = 0

    if isinstance(sources, list):
        for source_index, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            pages = source.get("pages")
            if not isinstance(pages, list):
                continue
            allowed = _resolve_page_filter(page_filters, source_index)
            source_candidates = 0
            source_kept = 0
            for page in pages:
                if not isinstance(page, dict):
                    continue
                asset = _page_candidate(page)
                if asset is None:
                    continue
                source_candidates += 1
                # Slice 82: drop candidates from material-excluded pages. With no
                # active filter (`allowed is None`) every candidate is kept.
                decision = page_is_in_material_selection(asset["source_page"], allowed)
                if not decision["kept"]:
                    filtered_count += 1
                    if decision["status"]:
                        filter_warnings.add(decision["status"])
                    continue
                source_kept += 1
                pages_with_signals += 1
                assets.append(asset)
            # An active filter that removed every candidate from a source records a
            # closed "no matching pages" token (not a failure).
            if allowed is not None and source_candidates > 0 and source_kept == 0:
                filter_warnings.add(VISUAL_FILTER_NO_MATCHING_PAGES)

    extracted_count = 0
    if isinstance(extracted_assets, list):
        for raw in extracted_assets:
            asset = _safe_extracted_asset(raw)
            if asset is not None:
                extracted_count += 1
                assets.append(asset)

    providers = sorted({asset["source_provider"] for asset in assets}) if assets else []
    warnings = [token for token in VISUAL_FILTER_TOKENS if token in filter_warnings]
    return {
        "version": MANIFEST_VERSION,
        "kind": "visual_assets_manifest",
        "status": "completed",
        "source": "extraction_metadata.json",
        "assets": assets,
        "summary": {
            "asset_count": len(assets),
            "pages_with_visual_signals": pages_with_signals,
            "extracted_figure_count": extracted_count,
            "source_providers": providers,
            "pages_filtered_by_material_selection": filtered_count,
        },
        "warnings": warnings,
    }


def _resolve_page_filter(page_filters: Any, source_index: int) -> set[int] | None:
    """Return the effective allowed page set for one source, or None (no filter).

    ``page_filters`` is the optional list aligned with ``sources``. A missing /
    out-of-range / ``None`` entry ⇒ ``None`` (no active material filter for that
    source). A collection entry ⇒ a set of positive 1-based ints (possibly empty,
    meaning the material selection left no pages, so every candidate is dropped).
    """
    if not isinstance(page_filters, (list, tuple)):
        return None
    if source_index < 0 or source_index >= len(page_filters):
        return None
    entry = page_filters[source_index]
    if entry is None:
        return None
    if not isinstance(entry, (list, tuple, set, frozenset)):
        return None
    allowed: set[int] = set()
    for value in entry:
        try:
            page = int(value)
        except (TypeError, ValueError):
            continue
        if page > 0:
            allowed.add(page)
    return allowed


def _page_candidate(page: dict[str, Any]) -> dict[str, Any] | None:
    """Build one page-level visual candidate, or None when the page has no signal.

    Reads only sanitized numeric/boolean signals (mirroring the Slice 31
    classifier's notion of "visual present") and never echoes raw input strings.
    """
    image_count = _safe_count(page.get("image_object_count"))
    drawing_count = _safe_count(page.get("drawing_object_count"))
    has_images = _safe_bool_or_none(page.get("has_images"))
    has_drawings = _safe_bool_or_none(page.get("has_drawings"))

    images_present = (image_count is not None and image_count > 0) or has_images is True
    drawings_present = (drawing_count is not None and drawing_count > 0) or has_drawings is True
    if not (images_present or drawings_present):
        return None

    source_page = _safe_page_number(page.get("page"))
    return {
        "asset_id": f"page_{source_page:04d}_visual_01",
        "source_page": source_page,
        "asset_type": ASSET_TYPE_PAGE_VISUAL_SIGNAL,
        # No cropping/segmentation happens in this slice, so there is no real
        # bounding box. Reserved for a later local-extraction slice.
        "bbox": None,
        "caption": None,
        "source_provider": SOURCE_PROVIDER_FITZ_LOCAL,
        # No candidate scoring in this slice.
        "recommended_action": RECOMMENDED_ACTION_UNKNOWN,
        "dedupe_group": None,
        "scores": {},
        "signals": {
            "image_object_count": image_count,
            "drawing_object_count": drawing_count,
            "has_images": has_images,
            "has_drawings": has_drawings,
            "page_width": _safe_dimension(page.get("page_width")),
            "page_height": _safe_dimension(page.get("page_height")),
            "classification": _safe_classification(page.get("classification")),
            "ocr_route_action": _safe_ocr_route_action(page.get("ocr_route_action")),
        },
        "warnings": [],
    }


def write_visual_assets_manifest(
    job: Any,
    sources: Any,
    extracted_assets: Any = None,
    *,
    page_filters: Any = None,
) -> None:
    """Persist the manifest from sanitized extraction-metadata ``sources``.

    ``extracted_assets`` (Slice 40, optional) are real cropped-figure records from
    :mod:`pipeline.visual_asset_extractor`; they are re-sanitised by
    :func:`build_visual_assets_manifest`. When ``None``/empty the persisted file is
    byte-identical to Slice 38.

    Advisory-only and fully wrapped: never raises to the caller, never mutates job
    status / validation, never blocks or fails generation. Mirrors
    ``extraction_metadata.write_extraction_metadata``'s degrade-to-skipped posture.

    Persistence convention (smallest approach, documented in DECISIONS): the
    manifest is derived from ``extraction_metadata.json`` and is written exactly
    when those PDF sources exist. Non-PDF jobs / jobs with no extraction-metadata
    sources OMIT the artifact entirely (the caller simply does not invoke this).
    A page set with zero visual signals still writes a valid ``completed`` manifest
    with an empty ``assets`` list (we looked and found no candidates).
    """
    try:
        manifest = build_visual_assets_manifest(
            sources, extracted_assets, page_filters=page_filters
        )
        job.save_text(
            job.visual_assets_manifest_json,
            json.dumps(manifest, indent=2) + "\n",
        )
    except Exception as exc:  # never let an advisory artifact break a job
        _write_skipped(job, "manifest_unavailable", "Visual assets manifest could not be built.")
        print(
            f"Visual assets manifest skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )


def write_skipped_visual_assets_manifest(
    job: Any,
    *,
    reason: str = "manifest_unavailable",
    safe_message: str = "Visual assets manifest could not be built.",
) -> None:
    """Best-effort public wrapper for callers that need an explicit skipped file."""
    _write_skipped(job, reason, safe_message)


def _write_skipped(job: Any, reason: str, safe_message: str) -> None:
    try:
        payload = {
            "version": MANIFEST_VERSION,
            "kind": "visual_assets_manifest",
            "status": "skipped",
            "source": "extraction_metadata.json",
            "reason": _safe_skip_reason(reason),
            "safe_message": str(safe_message)[:300],
        }
        job.save_text(
            job.visual_assets_manifest_json,
            json.dumps(payload, indent=2) + "\n",
        )
    except Exception:
        pass


def _empty_manifest() -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "kind": "visual_assets_manifest",
        "status": "completed",
        "source": "extraction_metadata.json",
        "assets": [],
        "summary": {
            "asset_count": 0,
            "pages_with_visual_signals": 0,
            "extracted_figure_count": 0,
            "source_providers": [],
            "pages_filtered_by_material_selection": 0,
        },
        "warnings": [],
    }


# --- Field-by-field coercion (never echo raw input) --------------------------


def _safe_count(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _safe_bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _safe_dimension(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf guard
        return None
    return round(max(0.0, number), 2)


def _safe_page_number(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_classification(value: Any) -> str:
    return value if value in _CLASSIFICATIONS else "unknown"


def _safe_ocr_route_action(value: Any) -> str:
    return value if value in _OCR_ROUTE_ACTIONS else "unknown"


def _safe_skip_reason(value: Any) -> str:
    safe = {"manifest_unavailable", "source_unavailable"}
    return value if value in safe else "manifest_unavailable"


# --- Extracted-figure coercion (Slice 40 — re-sanitise the fitz extractor) ----
#
# The local figure extractor produces asset dicts, but this manifest is the real
# security boundary: every field below is rebuilt from a closed vocab / coerced
# numeric / strict-shape relative ref, so even a changed or hostile extractor
# cannot smuggle an absolute path, raw image byte, URL, or free text into the
# persisted artifact. A record that cannot be made safe is dropped (returns None).


def _safe_extracted_asset(asset: Any) -> dict[str, Any] | None:
    if not isinstance(asset, dict):
        return None
    asset_id = _safe_asset_id(asset.get("asset_id"))
    image_ref = _safe_image_ref(asset.get("image_ref"))
    if asset_id is None or image_ref is None:
        # An extracted figure without a stable id or a valid relative image is
        # meaningless and is dropped rather than persisted in a broken state.
        return None
    source_page = _safe_page_number(asset.get("source_page"))
    bbox = _safe_bbox(asset.get("bbox"))
    signals = asset.get("signals") if isinstance(asset.get("signals"), dict) else {}
    return {
        "asset_id": asset_id,
        "source_page": source_page,
        "asset_type": ASSET_TYPE_EXTRACTED_FIGURE,
        "bbox": bbox,
        "caption": None,
        "source_provider": SOURCE_PROVIDER_FITZ_LOCAL,
        "recommended_action": RECOMMENDED_ACTION_UNKNOWN,
        "dedupe_group": None,
        "image_ref": image_ref,
        "scores": {},
        "signals": {
            "page_width": _safe_dimension(signals.get("page_width")),
            "page_height": _safe_dimension(signals.get("page_height")),
            "image_index": _safe_count(signals.get("image_index")),
            "crop_width_px": _safe_count(signals.get("crop_width_px")),
            "crop_height_px": _safe_count(signals.get("crop_height_px")),
        },
        "warnings": [],
    }


def _safe_asset_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    slug = _ASSET_ID_SANITIZE_RE.sub("", value)[:_MAX_ASSET_ID_LEN]
    return slug or None


def _safe_image_ref(value: Any) -> str | None:
    if isinstance(value, str) and _IMAGE_REF_RE.match(value):
        return value
    return None


def _safe_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    coords: list[float] = []
    for item in value:
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
