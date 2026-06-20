"""Cheap **animation-frame redundancy detector** + ``frame_dedup_mode`` resolver
(Slice 176M).

The OCR work (Slices 176F–176L) surfaced a narrow pathology: a small minority of
sources — roughly 1–2%, especially **StatQuest-style video-export slide decks** —
emit one PDF page per animation build-step, so the deck is dominated by runs of
near-identical frames. The eventual fix (a phash-collapse → terminal-frame →
coverage-coupled → VLM-classify-survivors selection pipeline) is **expensive** and
must stay a *gated conditional branch*, never a core path, because ~98% of decks
have no such redundancy.

This module is the **cheap gate** for that future branch — and **only** the gate:

What this module IS:
  * a cheap, OCR-free, model-free, network-free **detector** that measures
    consecutive-page visual redundancy from low-resolution perceptual hashes
    (difference-hash / dHash) and emits **closed metrics only**;
  * a tiny deterministic **resolver** for the three-state user setting
    ``frame_dedup_mode = auto | force_on | force_off`` (default ``auto``) that
    decides whether the expensive frame-selection branch *should* run.

What this module is **NOT** (do not grow it into any of these here):
  * the frame-selection pipeline itself (phash-collapse / terminal-frame /
    coverage-coupled / VLM-classify-survivors) — **not built in this slice**;
  * OCR generation/wiring, OCR-context full-guide generation, guide regeneration,
    a Layer-2 judge, repair, provider/model generation, cloud OCR, a frontend-wide
    redesign, or a broad document-analysis framework. ``judge_ready=false``;
    ``repair_ready=false``.

Hard constraints (mirrors the house posture in
:mod:`pipeline.slide_raster_ocr_ingestion`):
  * **Measurement only.** The detector never runs the expensive selection pipeline
    and never mutates normal generation. When the resolved flag is ``off`` the
    normal ~98% path is untouched (this module simply isn't consulted by it).
  * **Cheap + local.** Low-resolution in-memory hashing via PyMuPDF (``fitz``); no
    image files are written, so raster frames never reach the repo. No VLM/model
    calls. No cloud services.
  * **Leak-free.** Every persisted field is a closed-vocabulary token, count, or
    bool — no paths, filenames, hashes-as-values, byte counts, snippets, or free
    text. ``raw_images_committed`` / ``thumbnails_committed`` /
    ``source_pdf_committed`` are hardwired ``False``. Never raises to the caller.
  * **Conservative.** False positives (normal/repetitive-template decks wrongly
    flagged) are real and harmful, so ``auto`` only resolves ``on`` for a clear
    ``high`` signal; ``medium`` / ``low`` / ``unknown`` resolve ``off``. The
    operator can override either way via ``force_on`` / ``force_off``.
"""

from __future__ import annotations

import os
from typing import Any

ARTIFACT_NAME = "slide_redundancy_detection"

# --- closed vocabularies -----------------------------------------------------
# Consumers must treat any value not in these sets as the listed safe default.

_STATUS = {"completed", "degraded", "blocked", "skipped"}
_BUCKET = {"low", "medium", "high", "very_high", "unknown"}
_REDUNDANCY = {"low", "medium", "high", "unknown"}
_CONFIDENCE = {"low", "medium", "high"}
_FRAME_DEDUP_MODE = {"auto", "force_on", "force_off"}
_RESOLVED = {"on", "off"}
_RESOLUTION_REASON = {
    "detector_high",
    "detector_low",
    "detector_unknown_default_off",
    "user_force_on",
    "user_force_off",
}
_WARNINGS = {
    "fitz_unavailable",
    "render_failed",
    "no_pages_available",
    "too_few_pages_for_detection",
    "hashing_failed",
    "detector_low_confidence",
}

# --- hashing + similarity constants ------------------------------------------
# dHash (difference hash) at 9x8 grayscale → 64 bits. dHash compares horizontal
# gradients, so it stays sensitive to body-content changes even when two slides
# share a template header/footer — this is the main guard against false-positives
# on repetitive-template (but content-distinct) lecture decks.
_HASH_BITS = 64
_HASH_W = 9  # 9 columns → 8 horizontal comparisons per row
_HASH_H = 8  # 8 rows

# A consecutive pair counts as a near-duplicate (animation build-step) only above a
# deliberately high similarity, so template-similar-but-distinct slides do not count.
_HIGH_SIM_THRESHOLD = 0.92
# Single-linkage clustering along the page sequence starts a new visual cluster when
# the adjacent similarity drops below this (i.e. a genuinely different slide).
_CLUSTER_BREAK_SIMILARITY = 0.88
_MIN_PAGES_FOR_DETECTION = 3


# --- pure similarity / hashing helpers ---------------------------------------

def hamming_distance(a: Any, b: Any) -> int:
    """Bit-count difference between two 64-bit hash ints. Pure; never raises."""
    try:
        xor = int(a) ^ int(b)
    except (TypeError, ValueError):
        return _HASH_BITS
    try:
        return xor.bit_count()  # Python 3.10+
    except AttributeError:  # pragma: no cover - fallback for very old runtimes
        return bin(xor).count("1")


def similarity_from_hashes(a: Any, b: Any) -> float:
    """Normalized [0, 1] similarity of two hashes (1.0 == identical). Pure."""
    return max(0.0, 1.0 - (hamming_distance(a, b) / float(_HASH_BITS)))


def difference_hash_from_gray_rows(rows: Any) -> int:
    """Compute a 64-bit dHash from an 8x9 grayscale matrix (rows of 9 values).

    ``rows`` is an ``_HASH_H``-by-``_HASH_W`` nested sequence of numbers. The hash
    bit is 1 where a pixel is brighter than its right neighbour. Pure; returns 0 on
    malformed input rather than raising.
    """
    try:
        bits = 0
        position = 0
        seq = list(rows)
        for r in range(_HASH_H):
            row = list(seq[r])
            for c in range(_HASH_W - 1):
                if float(row[c]) > float(row[c + 1]):
                    bits |= 1 << position
                position += 1
        return bits
    except (TypeError, ValueError, IndexError):
        return 0


# --- pure adjacent-redundancy metrics ----------------------------------------

def compute_adjacent_metrics(hashes: Any) -> dict[str, Any]:
    """Closed-but-numeric adjacent-redundancy metrics from a page-hash sequence.

    Returns raw floats/ints (for the *summary builder* and *decision* to bucket /
    threshold) — these are aggregate statistics, never per-page content. Pure and
    total; an empty / single-element sequence yields zero pairs.
    """
    seq = [h for h in hashes if isinstance(h, int)] if isinstance(hashes, list) else []
    page_count = len(seq)
    if page_count < 2:
        return {
            "page_count": page_count,
            "adjacent_pairs": 0,
            "mean_adjacent_similarity": 0.0,
            "high_similarity_pair_ratio": 0.0,
            "distinct_visual_cluster_count": page_count,
            "cluster_to_page_ratio": 1.0 if page_count else 0.0,
        }

    sims: list[float] = []
    high_pairs = 0
    clusters = 1
    for i in range(1, page_count):
        sim = similarity_from_hashes(seq[i - 1], seq[i])
        sims.append(sim)
        if sim >= _HIGH_SIM_THRESHOLD:
            high_pairs += 1
        if sim < _CLUSTER_BREAK_SIMILARITY:
            clusters += 1

    pairs = len(sims)
    mean_sim = sum(sims) / pairs if pairs else 0.0
    return {
        "page_count": page_count,
        "adjacent_pairs": pairs,
        "mean_adjacent_similarity": mean_sim,
        "high_similarity_pair_ratio": high_pairs / pairs if pairs else 0.0,
        "distinct_visual_cluster_count": clusters,
        "cluster_to_page_ratio": clusters / page_count,
    }


# --- pure decision + bucketing -----------------------------------------------

def derive_slide_redundancy(metrics: Any) -> tuple[str, str]:
    """Closed ``(slide_redundancy, detector_confidence)`` from adjacent metrics.

    Conservative by construction (false positives are harmful):
      * ``high`` only when a clear share of consecutive pairs are near-duplicates
        AND visual clusters collapse many pages (low cluster-to-page ratio);
      * ``low`` when consecutive pages are mostly distinct and clusters ≈ pages;
      * ``medium`` in between; ``unknown`` when there are too few pages to judge.
    Pure and total.
    """
    m = metrics if isinstance(metrics, dict) else {}
    page_count = _as_int(m.get("page_count"))
    pairs = _as_int(m.get("adjacent_pairs"))
    if page_count < _MIN_PAGES_FOR_DETECTION or pairs <= 0:
        return "unknown", "low"

    high_ratio = _as_float(m.get("high_similarity_pair_ratio"))
    cluster_ratio = _as_float(m.get("cluster_to_page_ratio"))
    mean_sim = _as_float(m.get("mean_adjacent_similarity"))

    # HIGH: animation-export decks have runs of near-identical frames → a real
    # fraction of near-duplicate adjacent pairs AND clusters that collapse pages.
    is_high = high_ratio >= 0.30 and cluster_ratio <= 0.60
    # LOW: normal/varied (incl. repetitive-template-but-distinct) decks — pages are
    # mostly distinct and clusters roughly track pages.
    is_low = high_ratio < 0.15 and cluster_ratio >= 0.80

    if is_high:
        redundancy = "high"
    elif is_low:
        redundancy = "low"
    else:
        redundancy = "medium"

    # Confidence: stronger with more pages and more decisive signals.
    confidence = _confidence(page_count, high_ratio, cluster_ratio, mean_sim, redundancy)
    return redundancy, confidence


def _confidence(
    page_count: int, high_ratio: float, cluster_ratio: float, mean_sim: float, redundancy: str
) -> str:
    if page_count < 6:
        return "low"
    if redundancy == "high" and high_ratio >= 0.45 and cluster_ratio <= 0.45:
        return "high"
    if redundancy == "low" and high_ratio <= 0.05 and cluster_ratio >= 0.92:
        return "high"
    if redundancy == "medium":
        return "low"
    return "medium"


def bucket_similarity(value: Any) -> str:
    """Bucket a [0,1] similarity (mean adjacent / high-similarity ratio) into a token."""
    v = _as_float(value)
    if v <= 0.0:
        return "low"
    if v >= 0.85:
        return "very_high"
    if v >= 0.55:
        return "high"
    if v >= 0.25:
        return "medium"
    return "low"


def bucket_cluster_to_page_ratio(value: Any) -> str:
    """Bucket cluster-to-page ratio. Near 1.0 (clusters ≈ pages) → very_high (varied)."""
    v = _as_float(value)
    if v <= 0.0:
        return "unknown"
    if v >= 0.85:
        return "very_high"
    if v >= 0.60:
        return "high"
    if v >= 0.35:
        return "medium"
    return "low"


def bucket_count(value: Any, *, low: int, medium: int, high: int) -> str:
    """Bucket a non-negative count into low|medium|high|very_high by ascending cutoffs."""
    n = _as_int(value)
    if n <= 0:
        return "unknown"
    if n <= low:
        return "low"
    if n <= medium:
        return "medium"
    if n <= high:
        return "high"
    return "very_high"


# --- closed summary builder ---------------------------------------------------

def build_closed_redundancy_summary(
    *,
    status: str,
    source_label: str,
    metrics: Any = None,
    slide_redundancy: str | None = None,
    detector_confidence: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the committed-safe closed detector summary from adjacent metrics.

    Raw frames / thumbnails / source PDFs are structurally excluded (the
    ``*_committed`` flags are hardwired ``False`` and no path / image / size argument
    is accepted). Counts are coarse; everything else is a closed token. Never raises.
    """
    m = metrics if isinstance(metrics, dict) else {}
    if slide_redundancy is None or detector_confidence is None:
        derived_redundancy, derived_conf = derive_slide_redundancy(m)
        slide_redundancy = slide_redundancy or derived_redundancy
        detector_confidence = detector_confidence or derived_conf

    page_count = _as_int(m.get("page_count"))
    pairs = _as_int(m.get("adjacent_pairs"))
    warn = _safe_warnings(warnings)
    coerced_conf = _coerce(detector_confidence, _CONFIDENCE, "low")
    if coerced_conf == "low" and "detector_low_confidence" not in warn:
        warn = [*warn, "detector_low_confidence"]

    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _coerce(status, _STATUS, "blocked"),
        "source_label": _safe_label(source_label),
        "page_count_bucket": bucket_count(page_count, low=12, medium=40, high=120),
        "pages_sampled_count": page_count,
        "adjacent_pairs_sampled_count": pairs,
        "mean_adjacent_similarity_bucket": bucket_similarity(m.get("mean_adjacent_similarity")),
        "high_similarity_pair_ratio_bucket": bucket_similarity(m.get("high_similarity_pair_ratio")),
        "distinct_visual_cluster_count_bucket": bucket_count(
            m.get("distinct_visual_cluster_count"), low=5, medium=20, high=60
        ),
        "cluster_to_page_ratio_bucket": bucket_cluster_to_page_ratio(m.get("cluster_to_page_ratio")),
        "slide_redundancy": _coerce(slide_redundancy, _REDUNDANCY, "unknown"),
        "detector_confidence": coerced_conf,
        "raw_images_committed": False,
        "thumbnails_committed": False,
        "source_pdf_committed": False,
        "warnings": warn,
    }


# --- the three-state setting + resolver ---------------------------------------

def resolve_frame_dedup(detector_slide_redundancy: Any, frame_dedup_mode: Any) -> dict[str, str]:
    """Resolve whether the expensive frame-selection branch should run.

    ``frame_dedup_mode``: ``auto`` (trust detector) | ``force_on`` | ``force_off``;
    default ``auto``. Conservative: in ``auto`` only a clear ``high`` detector signal
    resolves ``on``; ``low`` / ``medium`` / ``unknown`` resolve ``off``. ``force_on``
    / ``force_off`` override the detector either way. Pure and total — emits closed
    tokens only and never engages the (unbuilt) selection pipeline.
    """
    redundancy = _coerce(detector_slide_redundancy, _REDUNDANCY, "unknown")
    mode = _coerce(frame_dedup_mode, _FRAME_DEDUP_MODE, "auto")

    if mode == "force_on":
        resolved, reason = "on", "user_force_on"
    elif mode == "force_off":
        resolved, reason = "off", "user_force_off"
    elif redundancy == "high":
        resolved, reason = "on", "detector_high"
    elif redundancy in {"low", "medium"}:
        # medium stays OFF — false positives are real; only a clear high engages.
        resolved, reason = "off", "detector_low"
    else:  # unknown
        resolved, reason = "off", "detector_unknown_default_off"

    return {
        "detector_slide_redundancy": redundancy,
        "frame_dedup_mode": mode,
        "resolved_frame_dedup": resolved,
        "resolution_reason": reason,
    }


# --- cheap local PDF hashing (in-memory; no image files written) -------------

def compute_page_hashes_from_pdf(
    pdf_path: str | os.PathLike[str],
    *,
    max_pages: int = 400,
) -> tuple[list[int], list[str]]:
    """Render low-res grayscale page thumbnails **in memory** and dHash each page.

    Local, read-only, OCR-free, model-free. Renders each page to a tiny grayscale
    pixmap via PyMuPDF and computes a 64-bit dHash — **no image files are written**,
    so raster frames never reach the repo. Returns ``(hashes, warnings)``; degrades to
    ``([], [warning])`` on any failure. Never raises.
    """
    warnings: list[str] = []
    try:
        import fitz  # guarded
    except Exception:
        return [], ["fitz_unavailable"]
    hashes: list[int] = []
    try:
        with fitz.open(pdf_path) as document:
            count = min(int(document.page_count), int(max_pages))
            if count <= 0:
                return [], ["no_pages_available"]
            for index in range(count):
                try:
                    rows = _render_gray_rows(fitz, document[index])
                    hashes.append(difference_hash_from_gray_rows(rows))
                except Exception:
                    warnings.append("hashing_failed")
    except Exception:
        return [], ["render_failed"]
    if not hashes:
        warnings.append("render_failed")
    return hashes, _safe_warnings(warnings)


def _render_gray_rows(fitz: Any, page: Any) -> list[list[float]]:
    """Render one page to an _HASH_H x _HASH_W grayscale matrix (small + cheap)."""
    # csGRAY pixmap at the exact hash grid keeps this O(pages) and tiny.
    matrix = fitz.Matrix(_HASH_W / max(1.0, page.rect.width), _HASH_H / max(1.0, page.rect.height))
    pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
    # Clamp to expected grid; pad/truncate defensively.
    w, h = pixmap.width, pixmap.height
    samples = pixmap.samples
    rows: list[list[float]] = []
    for r in range(_HASH_H):
        row: list[float] = []
        for c in range(_HASH_W):
            if r < h and c < w:
                row.append(float(samples[r * w + c]))
            else:
                row.append(0.0)
        rows.append(row)
    return rows


# --- inert config + detector runner ------------------------------------------

class FrameRedundancyConfig:
    """Config for the cheap detector. No I/O in the constructor.

    Either provide ``pdf_path`` (the detector renders + hashes locally) or
    ``page_hashes`` (precomputed 64-bit dHashes from already-rendered thumbnails, used
    by tests / validation harnesses). ``frame_dedup_mode`` carries the operator's
    three-state setting through to the resolver.
    """

    def __init__(
        self,
        *,
        source_label: str = "unknown",
        pdf_path: str | None = None,
        page_hashes: list[int] | None = None,
        frame_dedup_mode: str = "auto",
        max_pages: int = 400,
    ) -> None:
        self.source_label = source_label
        self.pdf_path = pdf_path
        self.page_hashes = list(page_hashes) if page_hashes else None
        self.frame_dedup_mode = frame_dedup_mode
        self.max_pages = int(max_pages)


def run_slide_redundancy_detection(config: FrameRedundancyConfig) -> dict[str, Any]:
    """Cheap detector → ``{"detection": <closed summary>, "resolution": <resolver>}``.

    Measurement only: computes the redundancy summary and resolves
    ``frame_dedup_mode`` against it. It never runs the expensive frame-selection
    pipeline (which is not built) and never mutates normal generation. Never raises.
    """
    warnings: list[str] = []
    hashes = config.page_hashes
    if hashes is None and config.pdf_path:
        hashes, warnings = compute_page_hashes_from_pdf(config.pdf_path, max_pages=config.max_pages)
    hashes = [h for h in (hashes or []) if isinstance(h, int)]

    if not hashes:
        summary = build_closed_redundancy_summary(
            status="blocked",
            source_label=config.source_label,
            metrics={"page_count": 0, "adjacent_pairs": 0},
            slide_redundancy="unknown",
            detector_confidence="low",
            warnings=[*warnings] or ["no_pages_available"],
        )
        resolution = resolve_frame_dedup("unknown", config.frame_dedup_mode)
        return {"detection": summary, "resolution": resolution}

    if len(hashes) < _MIN_PAGES_FOR_DETECTION:
        warnings.append("too_few_pages_for_detection")

    metrics = compute_adjacent_metrics(hashes)
    redundancy, confidence = derive_slide_redundancy(metrics)
    status = "completed" if len(hashes) >= _MIN_PAGES_FOR_DETECTION else "degraded"
    summary = build_closed_redundancy_summary(
        status=status,
        source_label=config.source_label,
        metrics=metrics,
        slide_redundancy=redundancy,
        detector_confidence=confidence,
        warnings=warnings,
    )
    resolution = resolve_frame_dedup(redundancy, config.frame_dedup_mode)
    return {"detection": summary, "resolution": resolution}


# --- closed-vocabulary sanitisers --------------------------------------------

def _coerce(value: Any, allowed: set[str], default: str) -> str:
    return value if value in allowed else default


def _safe_label(value: Any) -> str:
    import re

    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    seen: list[str] = []
    for w in warnings:
        if w in _WARNINGS and w not in seen:
            seen.append(w)
    return seen
