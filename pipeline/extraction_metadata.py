from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pipeline.job_manager import Job
from pipeline.ocr_routing import (
    ACTIONS as _ROUTE_ACTIONS,
    CONFIDENCES as _ROUTE_CONFIDENCES,
    LOCAL_OCR_PROVIDER_ID as _ROUTE_LOCAL_PROVIDER,
    REASONS as _ROUTE_REASONS,
    WARNINGS as _ROUTE_WARNINGS,
)

ARTIFACT_NAME = "extraction_metadata.json"


def pdf_source_metadata(
    *,
    filename: str,
    content_type: str,
    extraction_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build a source-level artifact entry from PDF extraction metadata."""
    if not isinstance(extraction_metadata, dict):
        return None
    if extraction_metadata.get("kind") != "pdf_extraction":
        return None
    pages = extraction_metadata.get("pages")
    if not isinstance(pages, list):
        return None
    return {
        "filename": Path(filename).name,
        "content_type": content_type,
        "page_count": int(extraction_metadata.get("page_count") or 0),
        "pages": [_safe_page(page) for page in pages if isinstance(page, dict)],
        "warnings": _safe_warnings(extraction_metadata.get("warnings", [])),
    }


def write_extraction_metadata(job: Job, sources: list[dict[str, Any]]) -> None:
    """Persist per-job extraction metadata, degrading safely on failure.

    This helper is advisory-only. It never raises to the caller and never mutates
    job status or validation artifacts. Unexpected errors produce a small skipped
    artifact when possible; logs include only the exception type name.
    """
    if not sources:
        return

    artifact_path = job.extraction_metadata_json
    try:
        payload = {
            "version": 2,
            "kind": "extraction_metadata",
            "status": "completed",
            "sources": sources,
        }
        job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
    except Exception as exc:  # never let metadata break a job
        _write_skipped(job, "metadata_unavailable", "Extraction metadata could not be collected.")
        print(
            f"Extraction metadata skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )


def write_skipped_extraction_metadata(
    job: Job,
    *,
    reason: str = "metadata_unavailable",
    safe_message: str = "Extraction metadata could not be collected.",
) -> None:
    """Best-effort public wrapper for callers that need an explicit skipped file."""
    _write_skipped(job, reason, safe_message)


def _write_skipped(job: Job, reason: str, safe_message: str) -> None:
    try:
        payload = {
            "version": 2,
            "kind": "extraction_metadata",
            "status": "skipped",
            "reason": reason,
            "safe_message": safe_message,
        }
        job.save_text(job.extraction_metadata_json, json.dumps(payload, indent=2) + "\n")
    except Exception:
        pass


def _safe_page(page: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "page": int(page.get("page") or 0),
        "method": _safe_method(page.get("method")),
        "text_chars": max(0, int(page.get("text_chars") or 0)),
        "word_count": max(0, int(page.get("word_count") or 0)),
        "has_page_anchor": bool(page.get("has_page_anchor")),
        "warnings": _safe_warnings(page.get("warnings", [])),
    }
    # Additive, advisory-only visual/object signals (Slice 30). Numeric/boolean
    # only; each value is carried through unknown-safe (None / null) when the
    # extractor could not measure it. Only emitted when the extractor supplied the
    # key, so a version-1 page record (no visual signals) stays byte-identical.
    if "image_object_count" in page:
        record["image_object_count"] = _safe_count(page.get("image_object_count"))
    if "drawing_object_count" in page:
        record["drawing_object_count"] = _safe_count(page.get("drawing_object_count"))
    if "has_images" in page:
        record["has_images"] = _safe_bool_or_none(page.get("has_images"))
    if "has_drawings" in page:
        record["has_drawings"] = _safe_bool_or_none(page.get("has_drawings"))
    if "page_width" in page:
        record["page_width"] = _safe_dimension(page.get("page_width"))
    if "page_height" in page:
        record["page_height"] = _safe_dimension(page.get("page_height"))
    if "visual_warnings" in page:
        record["visual_warnings"] = _safe_warnings(page.get("visual_warnings", []))
    # Advisory, deterministic page classification (Slice 31). Computed from the
    # already-sanitized fields above only — never from any upstream-supplied
    # `classification` key, so a smuggled value cannot survive. Additive and
    # unknown-safe: it never gates a job, reroutes OCR, or changes extracted text.
    classification = _classify_pdf_page(record)
    record["classification"] = _safe_classification(classification.get("classification"))
    record["classification_reasons"] = _safe_reasons(classification.get("classification_reasons"))
    record["ocr_recommended"] = bool(classification.get("ocr_recommended"))
    # Advisory OCR routing decision (Slice 34). Computed live in
    # `pipeline.extract` where local-OCR availability is authoritatively known,
    # then carried through here with closed-vocabulary sanitisation — the same
    # carry-and-coerce posture `_safe_method` / `_safe_warnings` apply to the
    # other upstream-computed fields. A smuggled value coerces to a fixed safe
    # token, so no path, secret, image data, or free text can survive. Emitted
    # only when the extractor supplied it, so a route-less (legacy or non-PDF)
    # page record stays byte-identical.
    if "ocr_route_action" in page:
        record["ocr_route_action"] = _safe_route_action(page.get("ocr_route_action"))
        record["ocr_route_provider"] = _safe_route_provider(page.get("ocr_route_provider"))
        record["ocr_route_reason"] = _safe_route_reason(page.get("ocr_route_reason"))
        record["ocr_route_confidence"] = _safe_route_confidence(page.get("ocr_route_confidence"))
        record["ocr_route_warnings"] = _safe_route_warnings(page.get("ocr_route_warnings"))
    return record


# --- Advisory OCR routing decision (Slice 34) ------------------------------
#
# These sanitisers mirror `pipeline.ocr_routing._decision`: every persisted route
# token is either a member of the imported closed vocabulary or a fixed safe
# default. They never echo an input value, so a hostile upstream record cannot
# smuggle a path / secret / image blob / free text into the artifact.


def classify_pdf_page_record(record: dict[str, Any]) -> dict[str, Any]:
    """Public wrapper around the advisory page classifier.

    Used by :mod:`pipeline.extract` to obtain a page's advisory ``classification``
    as the input to the OCR routing policy, so live extraction and the persisted
    artifact share one classifier (single source of truth). Pure and never raises.
    """
    return _classify_pdf_page(record)


def _safe_route_action(value: Any) -> str:
    return value if value in _ROUTE_ACTIONS else "unknown"


def _safe_route_provider(value: Any) -> str | None:
    return value if value == _ROUTE_LOCAL_PROVIDER else None


def _safe_route_reason(value: Any) -> str:
    return value if value in _ROUTE_REASONS else "routing_unavailable"


def _safe_route_confidence(value: Any) -> str:
    return value if value in _ROUTE_CONFIDENCES else "low"


def _safe_route_warnings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [w for w in value if w in _ROUTE_WARNINGS]


# --- Advisory page classification (Slice 31) -------------------------------
#
# Closed vocabulary; consumers must treat any value not in this set (or a missing
# field) as "unknown", never as an error. Mirrors `_safe_method`'s posture.
_CLASSIFICATIONS = {
    "embedded_text",
    "ocr_fallback",
    "likely_scanned",
    "blank_or_low_text",
    "mixed",
    "unknown",
    "error",
}

# Stable reason tokens. Whitelisted so the artifact can only ever carry these
# fixed strings — never free text, paths, or smuggled values.
_CLASSIFICATION_REASONS = {
    "method_ocr",
    "meaningful_embedded_text",
    "low_text",
    "near_zero_text",
    "images_present",
    "drawings_present",
    "no_visual_objects",
    "visual_signals_unavailable",
    "insufficient_signals",
    "error_warning",
    "classification_unavailable",
}

# Conservative thresholds. The "meaningful" gate mirrors
# extract._is_meaningful_page_text (>=40 chars OR >=5 word tokens) so the advisory
# classification agrees with the extractor's own per-page text/OCR decision. The
# near-zero gate is intentionally stricter than that to separate a genuinely
# empty page from a sparse one.
_MEANINGFUL_TEXT_CHARS = 40
_MEANINGFUL_TEXT_WORDS = 5
_NEAR_ZERO_TEXT_CHARS = 10
_NEAR_ZERO_TEXT_WORDS = 3

# Per-page warning tokens that make content classification unsafe. None are
# emitted by the extractor today — its warnings (ocr_unavailable,
# no_text_extracted, ocr_empty_fallback_embedded_text) are normal fallbacks, not
# errors — so this stays inert until a future slice records an explicit per-page
# extraction error.
_ERROR_WARNINGS = {"page_extraction_error", "ocr_error", "extraction_error"}


def _classify_pdf_page(record: dict[str, Any]) -> dict[str, Any]:
    """Advisory, deterministic page classification from sanitized metadata only.

    Never raises and never affects extraction, OCR routing, prompts, or
    generation. On any unexpected input it degrades to ``classification:
    "unknown"`` with reason ``classification_unavailable``. Reads only the
    already-sanitized numeric / method / visual fields on ``record`` (no raw
    text, paths, or upstream classification keys), so the result is reproducible
    and leak-free.
    """
    try:
        return _classify_pdf_page_inner(record)
    except Exception:
        return {
            "classification": "unknown",
            "classification_reasons": ["classification_unavailable"],
            "ocr_recommended": False,
        }


def _classify_pdf_page_inner(record: dict[str, Any]) -> dict[str, Any]:
    method = record.get("method")
    text_chars = int(record.get("text_chars") or 0)
    word_count = int(record.get("word_count") or 0)
    warnings = record.get("warnings") or []

    image_count = record.get("image_object_count")
    drawing_count = record.get("drawing_object_count")
    has_images = record.get("has_images")
    has_drawings = record.get("has_drawings")

    images_present = (isinstance(image_count, int) and image_count > 0) or has_images is True
    drawings_present = (isinstance(drawing_count, int) and drawing_count > 0) or has_drawings is True
    image_measured = isinstance(image_count, int) or isinstance(has_images, bool)
    drawing_measured = isinstance(drawing_count, int) or isinstance(has_drawings, bool)
    visual_measured = image_measured and drawing_measured
    visual_present = images_present or drawings_present

    has_meaningful_text = (
        text_chars >= _MEANINGFUL_TEXT_CHARS or word_count >= _MEANINGFUL_TEXT_WORDS
    )
    near_zero_text = (
        text_chars < _NEAR_ZERO_TEXT_CHARS and word_count < _NEAR_ZERO_TEXT_WORDS
    )

    # 1. An explicit per-page extraction error makes content classification
    #    unsafe; bail to `error` before reading text/visual signals.
    if any(w in _ERROR_WARNINGS for w in warnings):
        return {
            "classification": "error",
            "classification_reasons": ["error_warning"],
            "ocr_recommended": False,
        }

    text_reason = (
        "meaningful_embedded_text"
        if has_meaningful_text
        else "near_zero_text"
        if near_zero_text
        else "low_text"
    )
    if images_present:
        visual_reason = "images_present"
    elif drawings_present:
        visual_reason = "drawings_present"
    elif visual_measured:
        visual_reason = "no_visual_objects"
    else:
        visual_reason = "visual_signals_unavailable"

    # 2. OCR already ran and produced this page's text.
    if method == "ocr":
        return {
            "classification": "ocr_fallback",
            "classification_reasons": ["method_ocr", visual_reason],
            "ocr_recommended": False,
        }

    # 3. Embedded-text page (rich, or a sparse OCR-empty/unavailable fallback).
    if method == "embedded_text":
        if has_meaningful_text:
            if images_present:
                return {
                    "classification": "mixed",
                    "classification_reasons": [text_reason, "images_present"],
                    "ocr_recommended": False,
                }
            return {
                "classification": "embedded_text",
                "classification_reasons": [text_reason, visual_reason],
                "ocr_recommended": False,
            }
        return _classify_low_text(text_reason, visual_present, visual_measured, visual_reason)

    # 4. No text was extracted for this page.
    if method == "none":
        return _classify_low_text(text_reason, visual_present, visual_measured, visual_reason)

    # 5. Unrecognised / unknown method → not enough to classify.
    return {
        "classification": "unknown",
        "classification_reasons": ["insufficient_signals", visual_reason],
        "ocr_recommended": False,
    }


def _classify_low_text(
    text_reason: str,
    visual_present: bool,
    visual_measured: bool,
    visual_reason: str,
) -> dict[str, Any]:
    """Classify a low/near-empty-text page using the (sanitized) visual signal."""
    if visual_present:
        # Image / vector content but little or no text → looks like a scan or an
        # image-only slide; OCR would plausibly help.
        return {
            "classification": "likely_scanned",
            "classification_reasons": [text_reason, visual_reason],
            "ocr_recommended": True,
        }
    if visual_measured:
        # We positively measured no images and no drawings → genuinely blank.
        return {
            "classification": "blank_or_low_text",
            "classification_reasons": [text_reason, "no_visual_objects"],
            "ocr_recommended": False,
        }
    # Visual signals missing → cannot tell a scan from a blank page.
    return {
        "classification": "unknown",
        "classification_reasons": [text_reason, "visual_signals_unavailable"],
        "ocr_recommended": False,
    }


def _safe_classification(value: Any) -> str:
    """Coerce a classification to the closed vocabulary; `unknown` on anything else."""
    if value in _CLASSIFICATIONS:
        return value  # type: ignore[return-value]
    return "unknown"


def _safe_reasons(reasons: Any) -> list[str]:
    """Whitelist reason tokens so only fixed, leak-free strings can be persisted."""
    if not isinstance(reasons, list):
        return ["classification_unavailable"]
    out = [r for r in reasons if isinstance(r, str) and r in _CLASSIFICATION_REASONS]
    return out or ["classification_unavailable"]


def _safe_count(value: Any) -> int | None:
    """Non-negative integer count, or None when the signal was not measured."""
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
    """Finite, non-negative page dimension, or None when unknown."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf guard
        return None
    return round(max(0.0, number), 2)


def _safe_method(method: Any) -> str:
    value = str(method or "unknown")
    if value in {"embedded_text", "ocr", "none", "unknown"}:
        return value
    return "unknown"


def _safe_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    return [str(warning)[:300] for warning in warnings if warning]
