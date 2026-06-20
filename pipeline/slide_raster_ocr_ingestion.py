"""Local slide-raster OCR **ingestion artifact seam** (Slice 176H).

Slices 176F/176G proved the two real decks are near-empty-text, full-page raster
slide images; that **Tesseract** recovers bulk prose / loose tables but **fails**
dense structured grids; and that **local structured OCR** (Chandra OCR 2 served as
GGUF via local ``llama.cpp``/``llama-server`` — the Slice-41 path, local-only, no
cloud/API) recovers dense tables and math, while the **Gini masked-recompute proof
remains outstanding** (the representative Gini slide was a per-split *answer*
summary, not the raw class-count grid). 176G's recorded next step was
``build_local_slide_ocr_ingestion_pipeline``; this module is its **first minimal,
off-by-default increment**.

What this seam IS:
  * pure/testable helpers that classify a PDF text layer, detect full-page raster
    slides, render selected pages locally, run **configured local** OCR engines,
    write raw OCR into a **private, gitignored / temp** artifact directory, and emit
    a **committed-safe closed summary** for downstream coverage / figure / numeric
    consumers.

What this seam is **NOT** (do not grow it into any of these here):
  * guide-generation wiring, frontend/API integration, full ingestion rollout,
    numeric-recompute wiring, a Layer-2 judge, repair, cloud OCR, provider/model
    generation, or a broad new framework. ``judge_ready=false``;
    ``repair_ready=false``.

Hard constraints (mirrors the house posture in
:mod:`pipeline.extraction_metadata` / :mod:`pipeline.quality_safety_recompute_verifier`):
  * **Local only. No cloud OCR. Ever.** ``cloud_ocr_used`` is a hardwired ``False``.
  * **Off by default.** The runner is inert unless a config explicitly enables it;
    otherwise it returns ``status="skipped"``.
  * **Raw OCR / table / rendered-image bytes never enter the committed summary** —
    they go only to a private artifact directory, and only when that directory is
    confirmed private (gitignored / temp). If no private directory is available the
    seam **degrades to a closed ``blocked`` status rather than writing into the
    repo.**
  * Every persisted field is a closed-vocabulary token, count, or bool — no paths,
    filenames, hashes, byte counts, secrets, model files/caches, snippets, or free
    text. Never raises to the caller.
  * This seam may **not** claim numeric recovery: ``numeric_recompute_readiness``
    stays ``not_attempted`` (a later masked-recompute consumer owns that).
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

ARTIFACT_NAME = "slide_raster_ocr_ingestion_summary"

# --- closed vocabularies -----------------------------------------------------
# Consumers must treat any value not in these sets as the listed safe default,
# never as an error. Nothing outside these sets can ever be persisted.

_STATUS = {"completed", "degraded", "blocked", "skipped"}
_TEXT_LAYER_STATUS = {"near_empty", "partial", "usable", "unknown"}
_CONTENT_FORM = {
    "full_page_raster_slide_images",
    "mixed_text_and_images",
    "text_layer",
    "unknown",
}
_TESSERACT_STATUS = {"ran", "available", "not_available", "failed", "skipped"}
_STRUCTURED_STATUS = {"ran_local", "available", "not_available", "failed_local", "skipped"}
# Closed local-engine labels. GGUF/local-VLM routes must NOT be labelled hf/cli
# unless the pip `chandra-ocr` hf/cli package actually ran (176G recorded that the
# package is not installed; the GGUF/llama-server route is `chandra_gguf_local`).
_STRUCTURED_ENGINE = {
    "chandra_gguf_local",
    "local_structured_ocr_vlm",
    "chandra_hf_local",
    "chandra_cli_local",
    "none",
    "unknown",
}
_QUALITY = {"clean", "partial", "failed", "not_run"}
_DOWNSTREAM_READINESS = {
    "ready_for_visible_table_pilot",
    "ready_for_bulk_content_ingestion_pilot",
    "needs_engine_setup",
    "blocked",
}
_NUMERIC_READINESS = {
    "not_attempted",
    "needs_input_cell_parser",
    "blocked",
    "ready_for_masked_recompute",
}
# Closed warning tokens the seam may emit (no free text / paths / exception text).
_WARNINGS = {
    "off_by_default_skipped",
    "no_private_artifact_dir",
    "private_dir_not_gitignored",
    "fitz_unavailable",
    "render_failed",
    "no_pages_selected",
    "tesseract_unavailable",
    "tesseract_failed",
    "structured_ocr_not_configured",
    "structured_ocr_unavailable",
    "structured_ocr_failed_local",
    "artifact_write_refused",
    "artifact_write_failed",
    "numeric_recompute_deferred",
}

# Path segments treated as private/gitignored roots for raw artifacts. These match
# the repo's gitignored runtime areas (`local_operator_baselines/`, `jobs/`) plus a
# dedicated private OCR area; anything under the system temp dir is also private.
_PRIVATE_SEGMENTS = {"local_operator_baselines", "jobs", ".private_ocr", ".trash"}

# Conservative text-layer thresholds, aligned with extract._is_meaningful_page_text
# (>=40 chars OR >=5 word tokens marks a real text page) so this seam agrees with
# the extractor's own per-page text/OCR decision.
_MEANINGFUL_TEXT_CHARS = 40
_MEANINGFUL_TEXT_WORDS = 5
_NEAR_EMPTY_TEXT_CHARS = 10
_NEAR_EMPTY_TEXT_WORDS = 3


# --- text-layer + content-form classification (pure, leak-free) --------------

def classify_pdf_text_layer(page_texts: list[str]) -> str:
    """Closed text-layer status from per-page extracted text *lengths only*.

    Reads the structural shape of the text layer (how many pages carry meaningful
    text), never the text itself, and returns a closed token. ``near_empty`` is the
    176F/176G finding for the real decks (full-page raster slides). Never raises.
    """
    try:
        pages = [t if isinstance(t, str) else "" for t in (page_texts or [])]
        if not pages:
            return "unknown"
        meaningful = sum(1 for t in pages if _is_meaningful(t))
        near_empty = sum(1 for t in pages if _is_near_empty(t))
        ratio_meaningful = meaningful / len(pages)
        ratio_near_empty = near_empty / len(pages)
        if ratio_meaningful >= 0.6:
            return "usable"
        if ratio_near_empty >= 0.6:
            return "near_empty"
        return "partial"
    except Exception:
        return "unknown"


def detect_full_page_image_blocks(page_signals: list[dict[str, Any]]) -> str:
    """Closed effective-content-form from per-page visual/text signals.

    ``page_signals`` items carry the same numeric/bool keys
    :func:`pipeline.extract._pdf_visual_signals` emits (``image_object_count`` /
    ``has_images`` / ``text_chars`` / ``word_count``) — no bytes, no text. Returns a
    closed token describing the deck's dominant content form. Never raises.
    """
    try:
        signals = [s for s in (page_signals or []) if isinstance(s, dict)]
        if not signals:
            return "unknown"
        image_pages = 0
        text_pages = 0
        for s in signals:
            has_image = _signal_has_image(s)
            has_text = _is_meaningful_counts(
                int(s.get("text_chars") or 0), int(s.get("word_count") or 0)
            )
            if has_image and not has_text:
                image_pages += 1
            elif has_text and not has_image:
                text_pages += 1
            elif has_image and has_text:
                # counts as mixed on this page; tracked via neither bucket below
                pass
        total = len(signals)
        if image_pages / total >= 0.6:
            return "full_page_raster_slide_images"
        if text_pages / total >= 0.6:
            return "text_layer"
        return "mixed_text_and_images"
    except Exception:
        return "unknown"


def _signal_has_image(s: dict[str, Any]) -> bool:
    count = s.get("image_object_count")
    if isinstance(count, int) and count > 0:
        return True
    return s.get("has_images") is True


def _is_meaningful(text: str) -> bool:
    stripped = (text or "").strip()
    if len(stripped) >= _MEANINGFUL_TEXT_CHARS:
        return True
    return len(re.findall(r"\w+", stripped)) >= _MEANINGFUL_TEXT_WORDS


def _is_meaningful_counts(text_chars: int, word_count: int) -> bool:
    return text_chars >= _MEANINGFUL_TEXT_CHARS or word_count >= _MEANINGFUL_TEXT_WORDS


def _is_near_empty(text: str) -> bool:
    stripped = (text or "").strip()
    return (
        len(stripped) < _NEAR_EMPTY_TEXT_CHARS
        and len(re.findall(r"\w+", stripped)) < _NEAR_EMPTY_TEXT_WORDS
    )


# --- private-artifact directory policy (pure, leak-free) ---------------------

def is_private_artifact_dir(path: str | os.PathLike[str] | None) -> bool:
    """Whether raw OCR may be written under ``path`` (i.e. it is gitignored / temp).

    True only when the directory is under the system temp dir, or one of its path
    segments is a known-gitignored runtime root (`local_operator_baselines/`,
    `jobs/`, `.private_ocr/`, `.trash/`). Anything else — including a tracked repo
    folder — is refused, so raw OCR can never land in a committed location. Pure and
    never raises.
    """
    if not path:
        return False
    try:
        resolved = Path(path).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        try:
            resolved.relative_to(temp_root)
            return True
        except ValueError:
            pass
        return any(part in _PRIVATE_SEGMENTS for part in resolved.parts)
    except Exception:
        return False


def render_selected_pages_to_temp_images(
    pdf_path: str | os.PathLike[str],
    page_indices: list[int],
    out_dir: str | os.PathLike[str],
    *,
    dpi: int = 200,
) -> tuple[int, list[str]]:
    """Render selected 0-based pages to PNGs under a **private** ``out_dir``.

    Local, read-only, OCR-free rasterisation via PyMuPDF (``fitz``). Refuses unless
    ``out_dir`` is a private artifact directory (the rendered images are raster
    slide content and must never enter the repo). Returns ``(rendered_count,
    image_paths)``; ``image_paths`` are local-only and must not be committed or put
    in the closed summary. Degrades to ``(0, [])`` on any failure — never raises.
    """
    if not is_private_artifact_dir(out_dir) or not page_indices:
        return 0, []
    try:
        import fitz  # guarded: caller degrades when PyMuPDF is unavailable
    except Exception:
        return 0, []
    rendered: list[str] = []
    try:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        with fitz.open(pdf_path) as document:
            count = int(document.page_count)
            zoom = max(1.0, float(dpi) / 72.0)
            matrix = fitz.Matrix(zoom, zoom)
            for index in sorted({i for i in page_indices if 0 <= i < count}):
                pixmap = document[index].get_pixmap(matrix=matrix)
                target = out / f"page_{index:04d}.png"
                pixmap.save(str(target))
                rendered.append(str(target))
    except Exception:
        return len(rendered), rendered
    return len(rendered), rendered


# --- local OCR engine probes (local only; never cloud) -----------------------

def run_tesseract_if_available(image_paths: list[str]) -> tuple[str, float | None]:
    """Run local Tesseract over rendered images, if it is installed.

    Returns ``(status, mean_confidence_or_None)`` with a closed status token. Raw OCR
    text is **never** returned here (it would be a leak vector); only the mean
    confidence (a number) flows out, and the runner buckets that into a closed
    quality token. Local subprocess only; degrades to ``not_available`` / ``failed``
    rather than raising.
    """
    if not image_paths:
        return "skipped", None
    try:
        import shutil

        if not shutil.which("tesseract"):
            return "not_available", None
    except Exception:
        return "not_available", None
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        # binary present but python bindings missing — installed but not runnable here
        return "available", None
    try:
        confidences: list[float] = []
        for image_path in image_paths:
            data = pytesseract.image_to_data(
                Image.open(image_path), output_type=pytesseract.Output.DICT
            )
            page_conf = [float(c) for c in data.get("conf", []) if _is_real_conf(c)]
            if page_conf:
                confidences.append(sum(page_conf) / len(page_conf))
        if not confidences:
            return "failed", None
        return "ran", round(sum(confidences) / len(confidences), 2)
    except Exception:
        return "failed", None


def _is_real_conf(value: Any) -> bool:
    try:
        return float(value) >= 0.0
    except (TypeError, ValueError):
        return False


def run_local_structured_ocr_if_configured(
    image_paths: list[str],
    *,
    configured: bool,
    engine: str,
    endpoint_reachable: bool,
) -> tuple[str, str]:
    """Local structured OCR (e.g. Chandra GGUF via local llama-server), if configured.

    This seam never contacts a network OCR service; ``configured`` /
    ``endpoint_reachable`` describe a **local** structured-OCR route the operator set
    up (the 176G GGUF/llama-server path). Returns ``(status, engine_label)`` with
    closed tokens. The engine label is sanitised to the closed set and is **not**
    coerced to hf/cli for a GGUF/VLM route. No raw structured output is returned here.
    """
    safe_engine = engine if engine in _STRUCTURED_ENGINE else "unknown"
    if not configured:
        return "not_available", "none"
    if not endpoint_reachable:
        return "available", safe_engine
    if not image_paths:
        return "skipped", safe_engine
    # The real local call is performed by a gitignored transient harness (as in
    # 176G), not by this committed seam; when wired, it sets `ran_local` /
    # `failed_local`. The committed seam reports `available` so it never fabricates a
    # ran-local result it did not produce.
    return "available", safe_engine


# --- private artifact write (raw OCR stays out of the repo) -------------------

def write_private_ocr_artifact(
    out_dir: str | os.PathLike[str],
    raw_payload: str,
    *,
    name: str = "raw_ocr.txt",
) -> tuple[bool, bool]:
    """Write raw OCR/structured output to a **private** directory only.

    Returns ``(written, dir_is_private)``. Refuses (``False, False``) unless
    ``out_dir`` is confirmed private (gitignored / temp), so raw OCR can never be
    written into a committed location. Never raises. The committed summary records
    only the booleans this returns — never the payload, the path, or its size.
    """
    private = is_private_artifact_dir(out_dir)
    if not private:
        return False, False
    try:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(raw_payload if isinstance(raw_payload, str) else "", encoding="utf-8")
        return True, True
    except Exception:
        return False, True


# --- closed quality bucketing -------------------------------------------------

def bulk_text_quality_from_confidence(mean_conf: float | None) -> str:
    """Closed quality bucket from OCR mean confidence (same bands as the 176F gate)."""
    if mean_conf is None:
        return "not_run"
    try:
        value = float(mean_conf)
    except (TypeError, ValueError):
        return "not_run"
    if value >= 70:
        return "clean"
    if value >= 40:
        return "partial"
    return "failed"


# --- closed summary builder ---------------------------------------------------

def build_closed_slide_ocr_summary(
    *,
    status: str,
    source_label: str,
    pages_considered_count: int,
    pages_rendered_count: int,
    text_layer_status: str,
    effective_content_form: str,
    tesseract_status: str,
    structured_ocr_status: str,
    structured_ocr_engine: str,
    private_artifact_written: bool,
    private_artifact_gitignored: bool,
    bulk_text_quality: str = "not_run",
    loose_table_quality: str = "not_run",
    dense_grid_quality: str = "not_run",
    figure_caption_quality: str = "not_run",
    downstream_readiness: str = "blocked",
    numeric_recompute_readiness: str = "not_attempted",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the committed-safe closed summary. All fields coerced to closed sets.

    Raw OCR / table text, rendered images, model files, and model caches are
    structurally excluded (the ``*_committed`` flags are hardwired ``False`` and no
    text/path/size argument is accepted). ``cloud_ocr_used`` is hardwired ``False``.
    ``numeric_recompute_readiness`` cannot be ``ready_for_masked_recompute`` from this
    seam — that is reserved for a later masked-recompute consumer.
    """
    numeric = _coerce(numeric_recompute_readiness, _NUMERIC_READINESS, "not_attempted")
    if numeric == "ready_for_masked_recompute":
        # This seam never proves numeric readiness; refuse the optimistic token.
        numeric = "needs_input_cell_parser"
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _coerce(status, _STATUS, "blocked"),
        "source_label": _safe_label(source_label),
        "pages_considered_count": _safe_count(pages_considered_count),
        "pages_rendered_count": _safe_count(pages_rendered_count),
        "text_layer_status": _coerce(text_layer_status, _TEXT_LAYER_STATUS, "unknown"),
        "effective_content_form": _coerce(effective_content_form, _CONTENT_FORM, "unknown"),
        "tesseract_status": _coerce(tesseract_status, _TESSERACT_STATUS, "skipped"),
        "structured_ocr_status": _coerce(structured_ocr_status, _STRUCTURED_STATUS, "skipped"),
        "structured_ocr_engine": _coerce(structured_ocr_engine, _STRUCTURED_ENGINE, "none"),
        "cloud_ocr_used": False,
        "private_artifact_written": bool(private_artifact_written),
        "private_artifact_gitignored": bool(private_artifact_gitignored),
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "rendered_images_committed": False,
        "model_files_committed": False,
        "model_cache_committed": False,
        "bulk_text_quality": _coerce(bulk_text_quality, _QUALITY, "not_run"),
        "loose_table_quality": _coerce(loose_table_quality, _QUALITY, "not_run"),
        "dense_grid_quality": _coerce(dense_grid_quality, _QUALITY, "not_run"),
        "figure_caption_quality": _coerce(figure_caption_quality, _QUALITY, "not_run"),
        "downstream_readiness": _coerce(downstream_readiness, _DOWNSTREAM_READINESS, "blocked"),
        "numeric_recompute_readiness": numeric,
        "warnings": _safe_warnings(warnings),
    }


def _decide_downstream_readiness(
    *,
    blocked: bool,
    structured_ocr_status: str,
    dense_grid_quality: str,
    tesseract_status: str,
    bulk_text_quality: str,
) -> str:
    if blocked:
        return "blocked"
    if structured_ocr_status == "ran_local" and dense_grid_quality in {"clean", "partial"}:
        return "ready_for_visible_table_pilot"
    if tesseract_status == "ran" and bulk_text_quality in {"clean", "partial"}:
        return "ready_for_bulk_content_ingestion_pilot"
    if structured_ocr_status in {"not_available", "skipped"} and tesseract_status in {
        "not_available",
        "available",
        "skipped",
    }:
        return "needs_engine_setup"
    return "blocked"


# --- off-by-default runner ----------------------------------------------------

class SlideOcrIngestionConfig:
    """Inert-by-default config for the ingestion seam. No I/O in the constructor."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        source_label: str = "unknown",
        pdf_path: str | None = None,
        page_indices: list[int] | None = None,
        private_artifact_dir: str | None = None,
        tesseract_enabled: bool = True,
        structured_ocr_configured: bool = False,
        structured_ocr_engine: str = "none",
        structured_ocr_endpoint_reachable: bool = False,
    ) -> None:
        self.enabled = bool(enabled)
        self.source_label = source_label
        self.pdf_path = pdf_path
        self.page_indices = list(page_indices or [])
        self.private_artifact_dir = private_artifact_dir
        self.tesseract_enabled = bool(tesseract_enabled)
        self.structured_ocr_configured = bool(structured_ocr_configured)
        self.structured_ocr_engine = structured_ocr_engine
        self.structured_ocr_endpoint_reachable = bool(structured_ocr_endpoint_reachable)


def run_slide_raster_ocr_ingestion(
    config: SlideOcrIngestionConfig,
    *,
    page_texts: list[str] | None = None,
    page_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Off-by-default local ingestion runner → committed-safe closed summary.

    Inert unless ``config.enabled`` (returns ``status="skipped"``). When enabled it
    classifies the text layer / content form, renders selected pages and runs local
    OCR engines **only** into a private artifact directory, and returns the closed
    summary. If no private directory is available it returns ``status="blocked"``
    rather than writing into the repo. Never raises; never claims numeric recovery.
    """
    warnings: list[str] = []
    text_layer = classify_pdf_text_layer(page_texts or [])
    content_form = detect_full_page_image_blocks(page_signals or [])

    if not config.enabled:
        warnings.append("off_by_default_skipped")
        return build_closed_slide_ocr_summary(
            status="skipped",
            source_label=config.source_label,
            pages_considered_count=len(config.page_indices),
            pages_rendered_count=0,
            text_layer_status=text_layer,
            effective_content_form=content_form,
            tesseract_status="skipped",
            structured_ocr_status="skipped",
            structured_ocr_engine="none",
            private_artifact_written=False,
            private_artifact_gitignored=False,
            downstream_readiness="blocked",
            warnings=warnings,
        )

    # Refuse to write raw artifacts anywhere non-private → blocked, no repo writes.
    private_dir = config.private_artifact_dir
    if not is_private_artifact_dir(private_dir):
        warnings.append("no_private_artifact_dir" if not private_dir else "private_dir_not_gitignored")
        return build_closed_slide_ocr_summary(
            status="blocked",
            source_label=config.source_label,
            pages_considered_count=len(config.page_indices),
            pages_rendered_count=0,
            text_layer_status=text_layer,
            effective_content_form=content_form,
            tesseract_status="skipped",
            structured_ocr_status="skipped",
            structured_ocr_engine="none",
            private_artifact_written=False,
            private_artifact_gitignored=False,
            downstream_readiness="blocked",
            numeric_recompute_readiness="blocked",
            warnings=warnings,
        )

    rendered_count = 0
    image_paths: list[str] = []
    if config.pdf_path and config.page_indices:
        rendered_count, image_paths = render_selected_pages_to_temp_images(
            config.pdf_path, config.page_indices, private_dir
        )
        if rendered_count == 0:
            warnings.append("render_failed")
    else:
        warnings.append("no_pages_selected")

    tesseract_status = "skipped"
    bulk_quality = "not_run"
    loose_quality = "not_run"
    if config.tesseract_enabled:
        tesseract_status, mean_conf = run_tesseract_if_available(image_paths)
        bulk_quality = bulk_text_quality_from_confidence(mean_conf)
        loose_quality = bulk_quality  # loose tables track bulk text for Tesseract
        if tesseract_status == "not_available":
            warnings.append("tesseract_unavailable")
        elif tesseract_status == "failed":
            warnings.append("tesseract_failed")

    structured_status, structured_engine = run_local_structured_ocr_if_configured(
        image_paths,
        configured=config.structured_ocr_configured,
        engine=config.structured_ocr_engine,
        endpoint_reachable=config.structured_ocr_endpoint_reachable,
    )
    if not config.structured_ocr_configured:
        warnings.append("structured_ocr_not_configured")
    elif structured_status == "available":
        warnings.append("structured_ocr_unavailable")
    elif structured_status == "failed_local":
        warnings.append("structured_ocr_failed_local")

    # Raw OCR bytes never enter the summary; the private write is recorded as bools
    # only. The committed seam itself writes no raw payload (the real run uses a
    # gitignored transient harness), so the artifact-write flags reflect rendering.
    artifact_written = rendered_count > 0
    artifact_gitignored = is_private_artifact_dir(private_dir)

    # numeric recompute is always deferred from this seam.
    warnings.append("numeric_recompute_deferred")

    blocked = rendered_count == 0
    status = "completed" if not blocked else "degraded"
    downstream = _decide_downstream_readiness(
        blocked=blocked,
        structured_ocr_status=structured_status,
        dense_grid_quality="not_run",
        tesseract_status=tesseract_status,
        bulk_text_quality=bulk_quality,
    )

    return build_closed_slide_ocr_summary(
        status=status,
        source_label=config.source_label,
        pages_considered_count=len(config.page_indices),
        pages_rendered_count=rendered_count,
        text_layer_status=text_layer,
        effective_content_form=content_form,
        tesseract_status=tesseract_status,
        structured_ocr_status=structured_status,
        structured_ocr_engine=structured_engine,
        private_artifact_written=artifact_written,
        private_artifact_gitignored=artifact_gitignored,
        bulk_text_quality=bulk_quality,
        loose_table_quality=loose_quality,
        dense_grid_quality="not_run",
        figure_caption_quality="not_run",
        downstream_readiness=downstream,
        numeric_recompute_readiness="needs_input_cell_parser",
        warnings=warnings,
    )


# --- closed-vocabulary sanitisers --------------------------------------------

def _coerce(value: Any, allowed: set[str], default: str) -> str:
    return value if value in allowed else default


def _safe_label(value: Any) -> str:
    """A short closed-ish source label: alnum/underscore, bounded — never a path."""
    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    seen: list[str] = []
    for w in warnings:
        if w in _WARNINGS and w not in seen:
            seen.append(w)
    return seen
