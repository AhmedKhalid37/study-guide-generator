"""Local figure extraction / cropping for the visual-assets manifest (Slice 40).

This is the **first real extractor-output change** in the visual stack: where
Slice 38 only emitted page-level *signals* (``page_visual_signal`` candidates with
``bbox: null``), this module actually **crops embedded image regions out of a PDF**
with PyMuPDF (``fitz``) and produces real ``extracted_figure`` assets with a real
``bbox`` and a **safe relative image reference** (``assets/<file>.png``).

Scope & guardrails (Slice 40)
-----------------------------
- **Local-only, ``fitz_local`` only.** No Chandra / Mistral / Gemini / VLM, no
  network, no OCR. It uses the same read-only PyMuPDF inspections the extractor
  already performs (``page.get_images`` / ``page.get_image_rects``) plus a single
  ``get_pixmap(clip=...)`` rasterisation per cropped region.
- **Gated / off by default.** :func:`local_figure_extraction_enabled` reads
  ``GUIDEFORGE_LOCAL_FIGURE_EXTRACTION``; when unset/false the caller never invokes
  this module and the manifest stays byte-identical to Slice 38.
- **Advisory only.** It writes nothing into the guide, ``clean.md``, DOCX, exports,
  ``job.json``, validation, or any DTO. The only side effect is PNG files under the
  job's ``assets/`` directory, referenced by the manifest via a relative path.
- **Degrade-not-fail.** It never raises to the caller: a missing PyMuPDF, a corrupt
  PDF, or a single bad image yields fewer (or zero) assets, never a job failure.
- **Explosion prevention.** Tiny/decorative images are skipped, duplicate placements
  of the same region are collapsed, and hard caps bound assets per page and per job
  so a 2,000-page video-frame deck cannot produce an unbounded pile of crops.

The asset dicts returned here are **re-sanitised field-by-field** by
``pipeline.visual_assets_manifest`` before they reach the manifest, so this module
is *not* the security boundary — but it still emits only numeric/relative-path/None
values and never echoes a host path, raw PDF object, or image byte into a field.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable

SOURCE_PROVIDER = "fitz_local"
ASSET_TYPE_EXTRACTED_FIGURE = "extracted_figure"

ENABLE_ENV = "GUIDEFORGE_LOCAL_FIGURE_EXTRACTION"

# --- Explosion-prevention caps (conservative; tuned for course-pack decks) ----
# A region must be at least this many PDF points on each side AND cover at least
# this fraction of the page to count as a figure (skips bullets/logos/rules).
MIN_SIDE_POINTS = 24.0
MIN_AREA_FRACTION = 0.004
# Hard bounds so a pathological deck cannot explode the asset list / disk.
MAX_FIGURES_PER_PAGE = 12
MAX_FIGURES_PER_JOB = 200
# Rasterisation density for crops. 150 DPI is legible without huge files; the crop
# is clipped to the region, so file size scales with the figure, not the page.
CROP_DPI = 150


def local_figure_extraction_enabled() -> bool:
    """Whether the gated local figure-extraction path is turned on.

    Off by default. The caller must check this before invoking
    :func:`extract_local_figures`, so the default job is byte-identical to Slice 38.
    """
    value = os.getenv(ENABLE_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def extract_local_figures(
    pdf_path: Path,
    *,
    assets_dir: Path,
    source_index: int,
    pages: Iterable[int] | None = None,
    remaining_budget: int = MAX_FIGURES_PER_JOB,
) -> list[dict[str, Any]]:
    """Crop embedded image regions from ``pdf_path`` into ``extracted_figure`` assets.

    ``pages`` (1-based page numbers) restricts work to the pages the extraction
    metadata actually produced (so a page selection is honoured); ``None`` means
    all pages. ``remaining_budget`` lets the caller share :data:`MAX_FIGURES_PER_JOB`
    across multiple attachments. Deterministic: same PDF + inputs → same asset ids,
    bboxes, and image filenames.

    Pure-ish and total: never raises. On any failure it returns the assets gathered
    so far (possibly empty) and logs only an exception *type* category.
    """
    try:
        return _extract_inner(
            pdf_path,
            assets_dir=assets_dir,
            source_index=source_index,
            pages=pages,
            remaining_budget=max(0, int(remaining_budget)),
        )
    except Exception as exc:  # never let an advisory extractor break a job
        print(
            f"Local figure extraction skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )
        return []


def _extract_inner(
    pdf_path: Path,
    *,
    assets_dir: Path,
    source_index: int,
    pages: Iterable[int] | None,
    remaining_budget: int,
) -> list[dict[str, Any]]:
    if remaining_budget <= 0:
        return []

    import fitz  # PyMuPDF; ImportError → caller-safe ([] returned by wrapper)

    page_filter: set[int] | None = None
    if pages is not None:
        page_filter = {int(p) for p in pages}

    assets: list[dict[str, Any]] = []
    document = fitz.open(pdf_path)
    try:
        for page_number, page in enumerate(document, start=1):  # 1-based, matches metadata
            if len(assets) >= remaining_budget:
                break
            if page_filter is not None and page_number not in page_filter:
                continue
            try:
                page_assets = _figures_for_page(
                    page,
                    page_number=page_number,
                    assets_dir=assets_dir,
                    source_index=source_index,
                    budget=remaining_budget - len(assets),
                )
            except Exception:
                # One bad page must not lose the rest; record nothing for it.
                page_assets = []
            assets.extend(page_assets)
    finally:
        document.close()

    return assets


def _figures_for_page(
    page: Any,
    *,
    page_number: int,
    assets_dir: Path,
    source_index: int,
    budget: int,
) -> list[dict[str, Any]]:
    if budget <= 0:
        return []

    try:
        rect = page.rect
        page_width = round(float(rect.width), 2)
        page_height = round(float(rect.height), 2)
    except Exception:
        return []
    page_area = page_width * page_height
    if page_area <= 0:
        return []

    try:
        images = page.get_images(full=True)
    except Exception:
        images = []
    if not images:
        return []

    out: list[dict[str, Any]] = []
    seen_regions: set[tuple[int, int, int, int]] = set()  # dedupe identical placements
    figure_index = 0

    for image_pos, image in enumerate(images):
        if len(out) >= budget or len(out) >= MAX_FIGURES_PER_PAGE:
            break
        try:
            xref = int(image[0])
        except (TypeError, ValueError, IndexError):
            continue
        try:
            placements = page.get_image_rects(xref)
        except Exception:
            placements = []
        for placement in placements or []:
            if len(out) >= budget or len(out) >= MAX_FIGURES_PER_PAGE:
                break
            crop = _clamp_rect(placement, page_width, page_height)
            if crop is None:
                continue
            x0, y0, x1, y1 = crop
            width = x1 - x0
            height = y1 - y0
            # Tiny / decorative explosion prevention.
            if width < MIN_SIDE_POINTS or height < MIN_SIDE_POINTS:
                continue
            if (width * height) / page_area < MIN_AREA_FRACTION:
                continue
            # Duplicate-placement explosion prevention (same region twice).
            region_key = (round(x0), round(y0), round(x1), round(y1))
            if region_key in seen_regions:
                continue
            seen_regions.add(region_key)

            figure_index += 1
            asset = _crop_and_record(
                page,
                page_number=page_number,
                source_index=source_index,
                figure_index=figure_index,
                bbox=(x0, y0, x1, y1),
                page_width=page_width,
                page_height=page_height,
                image_pos=image_pos,
                assets_dir=assets_dir,
            )
            if asset is not None:
                out.append(asset)
    return out


def _crop_and_record(
    page: Any,
    *,
    page_number: int,
    source_index: int,
    figure_index: int,
    bbox: tuple[float, float, float, float],
    page_width: float,
    page_height: float,
    image_pos: int,
    assets_dir: Path,
) -> dict[str, Any] | None:
    import fitz

    x0, y0, x1, y1 = bbox
    asset_id = f"s{source_index:02d}_page_{page_number:04d}_figure_{figure_index:02d}"
    filename = f"{asset_id}.png"
    try:
        pixmap = page.get_pixmap(clip=fitz.Rect(x0, y0, x1, y1), dpi=CROP_DPI)
    except Exception:
        return None
    if pixmap.width <= 0 or pixmap.height <= 0:
        return None
    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
        pixmap.save(str(assets_dir / filename))
    except Exception:
        return None

    return {
        "asset_id": asset_id,
        "source_page": page_number,
        "asset_type": ASSET_TYPE_EXTRACTED_FIGURE,
        "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
        "caption": None,
        "source_provider": SOURCE_PROVIDER,
        "recommended_action": "unknown",
        "dedupe_group": None,
        # Relative ref only ("assets/<file>") — never an absolute / host path.
        "image_ref": f"assets/{filename}",
        "scores": {},
        "signals": {
            "page_width": page_width,
            "page_height": page_height,
            "image_index": int(image_pos),
            "crop_width_px": int(pixmap.width),
            "crop_height_px": int(pixmap.height),
        },
        "warnings": [],
    }


def _clamp_rect(
    placement: Any,
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float] | None:
    """Normalise a placement rect into clamped, ordered ``(x0, y0, x1, y1)`` points."""
    try:
        x0 = float(placement.x0)
        y0 = float(placement.y0)
        x1 = float(placement.x1)
        y1 = float(placement.y1)
    except Exception:
        return None
    for value in (x0, y0, x1, y1):
        if value != value or value in (float("inf"), float("-inf")):  # NaN / inf guard
            return None
    # Order corners, then clamp to the page box.
    lo_x, hi_x = min(x0, x1), max(x0, x1)
    lo_y, hi_y = min(y0, y1), max(y0, y1)
    lo_x = max(0.0, min(lo_x, page_width))
    hi_x = max(0.0, min(hi_x, page_width))
    lo_y = max(0.0, min(lo_y, page_height))
    hi_y = max(0.0, min(hi_y, page_height))
    if hi_x <= lo_x or hi_y <= lo_y:
        return None
    return (lo_x, lo_y, hi_x, hi_y)
