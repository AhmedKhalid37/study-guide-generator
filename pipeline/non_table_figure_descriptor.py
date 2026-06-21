"""Slice 176Z: produce a private non-table figure descriptor.

This producer fills the gap left by 176Y: it creates one private descriptor for
an actual non-table visual so a later writer-companion slice can use a real
figure/diagram input. Committed output is a closed summary only. Raw source text,
captions, OCR text, paths, crops, descriptor JSON, prompts, responses, provider
payloads, hashes, and byte counts are structurally excluded from that summary.

The public API is intentionally small:
  * select_non_table_candidate is pure and public-safe.
  * build_closed_summary emits only closed labels / bools.
  * run_non_table_figure_descriptor is the private runner. It may read private
    artifacts/source PDFs and write a crop plus descriptor only under a private
    artifact directory.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.visible_table_figure_pilot import SOURCE_LABEL_DEFAULT  # noqa: E402

ARTIFACT_NAME = "non_table_figure_descriptor"
SLICE_LABEL = "176Z"
DESCRIPTOR_FILENAME = "non_table_figure_descriptor.json"
SUMMARY_FILENAME = "closed_non_table_figure_descriptor_summary.json"

STATUSES = frozenset({"completed", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
CANDIDATE_SOURCES = frozenset(
    {
        "private_visible_artifact",
        "private_manifest",
        "private_source_deck",
        "synthetic_fixture",
        "none",
    }
)
SCAN_MODES = frozenset(
    {
        "visible_payload",
        "manifest_structural_scan",
        "pdf_local_geometry_crop",
        "synthetic_fixture",
        "no_candidate",
    }
)
ASSET_CATEGORIES = frozenset(
    {
        "figure",
        "diagram",
        "ensemble_structure_diagram",
        "decision_tree_diagram",
        "flowchart",
        "graph",
        "chart",
        "plot",
        "conceptual_diagram",
        "none",
    }
)
ASSET_KINDS = frozenset(
    {
        "figure",
        "diagram",
        "decision_tree_diagram",
        "flowchart",
        "graph",
        "chart",
        "plot",
        "conceptual_diagram",
        "unknown",
    }
)
VISUAL_TYPES = frozenset(
    {
        "figure",
        "diagram",
        "decision_tree_diagram",
        "flow_or_structure_diagram",
        "flowchart",
        "graph",
        "chart",
        "plot",
        "conceptual_diagram",
        "none",
    }
)
READINESS = frozenset({"ready_for_writer_companion", "blocked"})
BLOCKED_BY = frozenset(
    {
        "none",
        "private_artifact_missing",
        "unsafe_private_artifact_path",
        "no_non_table_figure_found_in_existing_extraction",
        "no_acceptable_non_table_figure_crop_after_operator_review",
        "descriptor_write_failed",
        "closed_summary_leak_detected",
    }
)
NEXT_STEPS = frozenset(
    {
        "run_writer_generated_figure_companion_on_non_table_descriptor",
        "need_better_visual_extraction_or_operator_supplied_non_table_figure",
        "improve_non_table_visual_crop_selection",
    }
)

_CATEGORY_ALIASES = {
    "graph_chart_plot": "chart",
    "graph_or_chart": "chart",
    "figure_or_diagram": "diagram",
    "split_diagram": "decision_tree_diagram",
    "decision_tree_or_split_diagram": "decision_tree_diagram",
    "architecture_diagram": "conceptual_diagram",
    "labeled_conceptual_diagram": "conceptual_diagram",
    "figure_image_crop": "figure",
    "ensemble_flow_diagram": "ensemble_structure_diagram",
    "ensemble_structure": "ensemble_structure_diagram",
}
_KIND_ALIASES = {
    "graph_or_chart": "chart",
    "graph_chart_plot": "chart",
    "figure_or_diagram": "diagram",
    "split_diagram": "decision_tree_diagram",
    "decision_tree": "decision_tree_diagram",
}
_TABLE_LIKE_TOKENS = (
    "table",
    "matrix",
    "grid",
    "proximity",
    "dataset",
    "dataframe",
    "rows",
    "columns",
    "cells",
    "cell",
    "structured_grid",
    "structured table",
    "scanned table",
)
_NON_TABLE_STRUCTURE_KEYS = (
    "diagram_nodes",
    "diagram_edges",
    "nodes",
    "edges",
    "flow_steps",
    "flowchart_steps",
    "chart_series",
    "plot_series",
    "graph_points",
    "concept_labels",
)
_TEXT_ONLY_REJECT_TOKENS = (
    "activation function",
    "relu",
    "question",
    "solution",
    "exercise",
)
_ENSEMBLE_STRUCTURE_TOKENS = (
    "training data",
    "data1",
    "data2",
    "data m",
    "learner1",
    "learner2",
    "learner m",
    "model combiner",
    "final model",
)
_RAW_SUMMARY_MARKERS = (
    "data:image",
    "base64",
    "prompt",
    "response",
    "provider_payload",
    "descriptor_json",
    "ocr text",
    "caption text",
)
OPERATOR_REJECTED_PREVIOUS_CROP_REASON = "text_only_or_wrong_source"
OPERATOR_TARGET_VISUAL_TYPE = "ensemble_structure_diagram"
_DEFAULT_PRIVATE_ROOTS: tuple[str, ...] = ()
_MAX_PDFS_TO_SCAN = 8
_MAX_PAGES_PER_PDF = 80


def run_non_table_figure_descriptor(
    *,
    private_ocr_dir: str | None = None,
    private_descriptor_dir: str | None = None,
    private_visible_artifact: str | None = None,
    private_source_deck: str | None = None,
    source_label: str = SOURCE_LABEL_DEFAULT,
    inventory_roots: list[str] | None = None,
) -> dict[str, Any]:
    """Create one private non-table descriptor and print/return a closed summary."""
    base_private = Path(private_ocr_dir) if private_ocr_dir else None
    out_dir = (
        Path(private_descriptor_dir)
        if private_descriptor_dir
        else (base_private / ARTIFACT_NAME if base_private else Path(tempfile.gettempdir()) / ARTIFACT_NAME)
    )

    if private_ocr_dir and not is_private_artifact_dir(private_ocr_dir):
        summary = build_closed_summary(
            status="blocked",
            source_label=source_label,
            blocked_by="unsafe_private_artifact_path",
        )
        _write_summary_if_private(summary, out_dir)
        return summary
    if not is_private_artifact_dir(out_dir):
        return build_closed_summary(
            status="blocked",
            source_label=source_label,
            blocked_by="unsafe_private_artifact_path",
        )

    candidates: list[dict[str, Any]] = []
    candidates.extend(_candidates_from_visible_payload(private_visible_artifact, base_private))
    candidates.extend(_candidates_from_manifest(base_private))
    candidates.extend(
        _candidates_from_private_pdfs(
            out_dir=out_dir,
            private_source_deck=private_source_deck,
            inventory_roots=inventory_roots,
            source_label=source_label,
        )
    )

    selected = select_non_table_candidate(candidates)
    if selected is None:
        summary = build_closed_summary(
            status="blocked",
            source_label=source_label,
            blocked_by="no_acceptable_non_table_figure_crop_after_operator_review",
        )
        _write_summary_if_private(summary, out_dir)
        return summary

    descriptor = _private_descriptor_from_candidate(selected, source_label=source_label)
    descriptor_path = out_dir / DESCRIPTOR_FILENAME
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        descriptor_path.write_text(json.dumps(descriptor, indent=2, ensure_ascii=False), encoding="utf-8")
        descriptor_written = descriptor_path.is_file()
    except Exception:
        descriptor_written = False

    if not descriptor_written:
        summary = build_closed_summary(
            status="blocked",
            source_label=source_label,
            candidate_source=_candidate_source(selected),
            candidate_scan_mode=_scan_mode(selected),
            selected_asset_category=_asset_category(selected),
            selected_asset_kind=_asset_kind(selected),
            visual_type_closed=_visual_type(selected),
            visual_is_text_only=_quality_flag(selected, "visual_is_text_only"),
            visual_is_partial_sliver=_quality_flag(selected, "visual_is_partial_sliver"),
            visual_source_matches_label=_quality_flag(selected, "visual_source_matches_label", default=True),
            blocked_by="descriptor_write_failed",
        )
        _write_summary_if_private(summary, out_dir)
        return summary

    visual_available = _private_visual_available(selected)
    visual_quality = _visual_quality_flags(selected)
    completed = (
        descriptor_written
        and visual_available
        and is_private_artifact_dir(out_dir)
        and not visual_quality["visual_is_text_only"]
        and not visual_quality["visual_is_partial_sliver"]
        and visual_quality["visual_source_matches_label"]
    )
    summary = build_closed_summary(
        status="completed" if completed else "blocked",
        source_label=source_label,
        candidate_source=_candidate_source(selected),
        candidate_scan_mode=_scan_mode(selected),
        selected_asset_category=_asset_category(selected),
        selected_asset_kind=_asset_kind(selected),
        visual_type_closed=_visual_type(selected),
        descriptor_written=descriptor_written,
        descriptor_gitignored=is_private_artifact_dir(out_dir),
        private_visual_asset_available=visual_available,
        private_visual_asset_gitignored=visual_available and is_private_artifact_dir(out_dir),
        visual_is_text_only=visual_quality["visual_is_text_only"],
        visual_is_partial_sliver=visual_quality["visual_is_partial_sliver"],
        visual_source_matches_label=visual_quality["visual_source_matches_label"],
        visual_is_non_table_figure=completed,
        blocked_by="none" if completed else "no_acceptable_non_table_figure_crop_after_operator_review",
    )
    _write_summary_if_private(summary, out_dir)
    return summary


def select_non_table_candidate(candidates: Any) -> dict[str, Any] | None:
    """Return the first conservative non-table visual candidate by priority."""
    if not isinstance(candidates, list):
        return None
    scored: list[tuple[int, dict[str, Any]]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if not is_eligible_non_table_candidate(candidate):
            continue
        scored.append((_candidate_score(candidate), candidate))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def is_eligible_non_table_candidate(candidate: dict[str, Any]) -> bool:
    if _visual_shape_flags(candidate)["visual_is_table_like"]:
        return False
    quality_flags = _visual_quality_flags(candidate)
    if (
        quality_flags["visual_is_text_only"]
        or quality_flags["visual_is_partial_sliver"]
        or not quality_flags["visual_source_matches_label"]
    ):
        return False
    category = _asset_category(candidate)
    kind = _asset_kind(candidate)
    if category not in ASSET_CATEGORIES or category == "none":
        return False
    if kind not in ASSET_KINDS or kind == "unknown":
        return False
    if _has_dominant_non_text_visual_structure(candidate):
        return True
    return False


def build_closed_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    candidate_source: str = "none",
    candidate_scan_mode: str = "no_candidate",
    selected_asset_category: str = "none",
    selected_asset_kind: str = "unknown",
    selected_asset_role: str = "study_visual",
    descriptor_written: bool = False,
    descriptor_gitignored: bool = False,
    private_visual_asset_available: bool = False,
    private_visual_asset_gitignored: bool = False,
    visual_is_text_only: bool = False,
    visual_is_partial_sliver: bool = False,
    visual_source_matches_label: bool = True,
    visual_is_non_table_figure: bool = False,
    visual_type_closed: str = "none",
    blocked_by: str = "none",
) -> dict[str, Any]:
    """Closed-label summary safe for committing or pasting."""
    coerced_status = _coerce(status, STATUSES, "blocked")
    completed = coerced_status == "completed"
    if completed:
        readiness = "ready_for_writer_companion"
        next_step = "run_writer_generated_figure_companion_on_non_table_descriptor"
        blocker = "none"
    else:
        readiness = "blocked"
        if blocked_by == "no_acceptable_non_table_figure_crop_after_operator_review":
            next_step = "improve_non_table_visual_crop_selection"
        else:
            next_step = "need_better_visual_extraction_or_operator_supplied_non_table_figure"
        blocker = _coerce(blocked_by, BLOCKED_BY, "no_non_table_figure_found_in_existing_extraction")
    summary = {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "status": coerced_status,
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        "candidate_source": _coerce(candidate_source, CANDIDATE_SOURCES, "none"),
        "candidate_scan_mode": _coerce(candidate_scan_mode, SCAN_MODES, "no_candidate"),
        "selected_asset_category": _coerce(selected_asset_category, ASSET_CATEGORIES, "none"),
        "selected_asset_kind": _coerce(selected_asset_kind, ASSET_KINDS, "unknown"),
        "selected_asset_role": selected_asset_role if selected_asset_role == "study_visual" else "study_visual",
        "operator_rejected_previous_crop_reason": OPERATOR_REJECTED_PREVIOUS_CROP_REASON,
        "operator_target_visual_type": OPERATOR_TARGET_VISUAL_TYPE,
        "descriptor_written": bool(descriptor_written) if completed else False,
        "descriptor_gitignored": bool(descriptor_gitignored) if completed else False,
        "private_visual_asset_available": bool(private_visual_asset_available) if completed else False,
        "private_visual_asset_gitignored": bool(private_visual_asset_gitignored) if completed else False,
        "visual_is_table_like": False,
        "visual_is_matrix": False,
        "visual_is_grid": False,
        "visual_is_text_only": bool(visual_is_text_only) if completed else False,
        "visual_is_partial_sliver": bool(visual_is_partial_sliver) if completed else False,
        "visual_source_matches_label": bool(visual_source_matches_label) if completed else False,
        "visual_is_non_table_figure": bool(visual_is_non_table_figure) if completed else False,
        "visual_type_closed": _coerce(visual_type_closed, VISUAL_TYPES, "none"),
        "visual_descriptor_readiness": _coerce(readiness, READINESS, "blocked"),
        "figure_companion_input_ready": completed,
        "provider_call_made": False,
        "generation_rerun": False,
        "generation_behavior_changed": False,
        "ocr_rerun": False,
        "cloud_ocr_used": False,
        "chandra_used": False,
        "frontend_api_changed": False,
        "numeric_verification_claimed": False,
        "judge_ready": False,
        "repair_ready": False,
        "blocked_by": blocker,
        "recommended_next_step": _coerce(next_step, NEXT_STEPS, next_step),
    }
    _assert_closed_summary_safe(summary)
    return summary


def _candidates_from_visible_payload(path: str | None, private_dir: Path | None) -> list[dict[str, Any]]:
    paths: list[Path] = []
    if path:
        paths.append(Path(path))
    if private_dir:
        paths.append(private_dir / "visible_table_figure_pilot.json")
    out: list[dict[str, Any]] = []
    for payload_path in paths:
        if not payload_path.is_file() or not is_private_artifact_dir(payload_path.parent):
            continue
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload_label = payload.get("source_label") if isinstance(payload, dict) else None
        assets = payload.get("assets") if isinstance(payload, dict) else None
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            candidate = dict(asset)
            candidate.setdefault("candidate_source", "private_visible_artifact")
            candidate.setdefault("candidate_scan_mode", "visible_payload")
            candidate.setdefault("source_label", payload_label)
            candidate.setdefault("visual_source_matches_label", _source_matches_label(payload_label, payload_label))
            out.append(candidate)
    return out


def _candidates_from_manifest(private_dir: Path | None) -> list[dict[str, Any]]:
    if private_dir is None:
        return []
    manifest_path = private_dir / "extracted_content_manifest.json"
    if not manifest_path.is_file() or not is_private_artifact_dir(manifest_path.parent):
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    out: list[dict[str, Any]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        raw_category = entry.get("slide_category")
        category = _category_from_manifest(raw_category)
        if category == "none":
            continue
        signals = entry.get("signals") if isinstance(entry.get("signals"), dict) else {}
        out.append(
            {
                "candidate_source": "private_manifest",
                "candidate_scan_mode": "manifest_structural_scan",
                "asset_category": category,
                "asset_kind": category,
                "display_role": "study_visual",
                "has_table": bool(signals.get("has_table")),
                "table_count": _safe_int(signals.get("table_count")),
                "max_table_rows": _safe_int(signals.get("max_table_rows")),
                "max_table_cols": _safe_int(signals.get("max_table_cols")),
                "figure_or_diagram_count": _safe_int(signals.get("figure_or_diagram_count")),
                "_private_context_text": _private_manifest_context(entry),
            }
        )
    return out


def _candidates_from_private_pdfs(
    *,
    out_dir: Path,
    private_source_deck: str | None,
    inventory_roots: list[str] | None,
    source_label: str,
) -> list[dict[str, Any]]:
    pdfs = _discover_private_pdfs(private_source_deck, inventory_roots, source_label)
    out: list[dict[str, Any]] = []
    for pdf_path in pdfs[:_MAX_PDFS_TO_SCAN]:
        try:
            import fitz  # type: ignore
        except Exception:
            return out
        try:
            doc = fitz.open(pdf_path)
        except Exception:
            continue
        for page_index in range(min(len(doc), _MAX_PAGES_PER_PDF)):
            try:
                page = doc[page_index]
                candidate = _candidate_from_pdf_page(
                    page,
                    page_index=page_index,
                    pdf_path=pdf_path,
                    out_dir=out_dir,
                    source_label=source_label,
                )
            except Exception:
                candidate = None
            if candidate is not None:
                out.append(candidate)
        try:
            doc.close()
        except Exception:
            pass
    return out


def _candidate_from_pdf_page(
    page: Any, *, page_index: int, pdf_path: Path, out_dir: Path, source_label: str
) -> dict[str, Any] | None:
    if page.rect.width <= page.rect.height:
        return None
    drawings = page.get_drawings()
    metrics = _drawing_metrics(drawings, page.rect)
    if metrics["curve_count"] < 4 and metrics["rect_count"] < 3 and metrics["diagonal_line_count"] < 2:
        return None
    if metrics["grid_like"]:
        return None
    text = page.get_text("text") or ""
    closed_text = text.lower()
    if _looks_table_like_text(closed_text) and metrics["curve_count"] < 4:
        return None
    if _looks_text_only_page(closed_text):
        return None
    if not (0.04 <= metrics["area_ratio"] <= 0.85):
        return None

    clip = _expanded_rect(metrics["union_rect"], page.rect)
    text_metrics = _pdf_crop_text_metrics(page, clip)
    if _is_text_dominated_crop(metrics, text_metrics):
        return None
    partial_sliver = _is_partial_visual_sliver(metrics, page.rect, clip)
    source_matches = _source_matches_label(str(pdf_path), source_label)
    if not source_matches:
        return None
    crop_name = f"non_table_figure_page_{page_index + 1:04d}.png"
    crop_path = out_dir / "visual_assets" / crop_name
    try:
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        pix = page.get_pixmap(clip=clip, dpi=180)
        pix.save(crop_path)
    except Exception:
        return None

    is_ensemble_structure = _is_ensemble_structure_text(closed_text)
    asset_category = "ensemble_structure_diagram" if is_ensemble_structure else "conceptual_diagram"
    visual_type = "flow_or_structure_diagram" if is_ensemble_structure else "conceptual_diagram"
    return {
        "candidate_source": "private_source_deck",
        "candidate_scan_mode": "pdf_local_geometry_crop",
        "source_label": source_label,
        "asset_category": asset_category,
        "asset_kind": "conceptual_diagram",
        "display_role": "study_visual",
        "visual_type": visual_type,
        "visual_is_text_only": False,
        "visual_is_partial_sliver": partial_sliver,
        "visual_source_matches_label": source_matches,
        "visual_structure_score": _visual_structure_score(metrics),
        "_private_source_path": str(pdf_path),
        "_private_visual_crop_path": str(crop_path),
        "_private_page_index": page_index,
        "_private_bbox": [float(clip.x0), float(clip.y0), float(clip.x1), float(clip.y1)],
        "_private_context_text": text.strip(),
    }


def _pdf_crop_text_metrics(page: Any, clip: Any) -> dict[str, Any]:
    char_count = 0
    text_area = 0.0
    clip_area = max(1.0, float(clip.width) * float(clip.height))
    try:
        blocks = page.get_text("blocks", clip=clip)
    except Exception:
        blocks = []
    for block in blocks:
        if len(block) < 5 or not isinstance(block[4], str):
            continue
        text = block[4].strip()
        if not text:
            continue
        char_count += len(text)
        width = max(0.0, float(block[2]) - float(block[0]))
        height = max(0.0, float(block[3]) - float(block[1]))
        text_area += width * height
    return {
        "char_count": char_count,
        "text_area_ratio": min(1.0, text_area / clip_area),
    }


def _is_text_dominated_crop(metrics: dict[str, Any], text_metrics: dict[str, Any]) -> bool:
    visual_score = _visual_structure_score(metrics)
    text_area_ratio = float(text_metrics.get("text_area_ratio") or 0.0)
    char_count = _safe_int(text_metrics.get("char_count"))
    if visual_score < 8:
        return True
    return text_area_ratio > 0.72 and char_count > 500 and visual_score < 20


def _is_partial_visual_sliver(metrics: dict[str, Any], page_rect: Any, clip: Any) -> bool:
    page_width = max(1.0, float(page_rect.width))
    page_height = max(1.0, float(page_rect.height))
    width_ratio = max(0.0, float(clip.width) / page_width)
    height_ratio = max(0.0, float(clip.height) / page_height)
    area_ratio = max(0.0, float(metrics.get("area_ratio") or 0.0))
    if width_ratio < 0.18 or height_ratio < 0.18:
        return True
    return area_ratio < 0.035 and _visual_structure_score(metrics) < 16


def _visual_structure_score(metrics: dict[str, Any]) -> int:
    return (
        _safe_int(metrics.get("curve_count")) * 2
        + _safe_int(metrics.get("rect_count")) * 2
        + _safe_int(metrics.get("diagonal_line_count"))
        + _safe_int(metrics.get("horizontal_line_count"))
        + _safe_int(metrics.get("vertical_line_count"))
    )


def _drawing_metrics(drawings: Any, page_rect: Any) -> dict[str, Any]:
    rects = []
    curve_count = 0
    rect_count = 0
    horizontal = 0
    vertical = 0
    diagonal = 0
    for drawing in drawings if isinstance(drawings, list) else []:
        rect = drawing.get("rect")
        if rect is not None:
            try:
                if rect.width > 2 and rect.height > 2 and not _is_background_rect(rect, page_rect):
                    rects.append(rect)
            except Exception:
                pass
        for item in drawing.get("items", []):
            op = item[0] if item else ""
            if op == "c":
                curve_count += 1
            elif op == "re":
                rect_count += 1
            elif op == "l" and len(item) >= 3:
                p0, p1 = item[1], item[2]
                dx = abs(float(p1.x) - float(p0.x))
                dy = abs(float(p1.y) - float(p0.y))
                if dx < 1 and dy > 4:
                    vertical += 1
                elif dy < 1 and dx > 4:
                    horizontal += 1
                elif dx > 4 and dy > 4:
                    diagonal += 1
    if rects:
        union = rects[0]
        for rect in rects[1:]:
            union |= rect
    else:
        union = page_rect
    area_ratio = max(0.0, min(1.0, (union.width * union.height) / (page_rect.width * page_rect.height)))
    grid_like = curve_count == 0 and diagonal == 0 and horizontal >= 4 and vertical <= 2
    return {
        "curve_count": curve_count,
        "rect_count": rect_count,
        "horizontal_line_count": horizontal,
        "vertical_line_count": vertical,
        "diagonal_line_count": diagonal,
        "grid_like": grid_like,
        "area_ratio": area_ratio,
        "union_rect": union,
    }


def _is_background_rect(rect: Any, page_rect: Any) -> bool:
    return (
        abs(float(rect.x0) - float(page_rect.x0)) < 2
        and abs(float(rect.y0) - float(page_rect.y0)) < 2
        and abs(float(rect.x1) - float(page_rect.x1)) < 2
        and abs(float(rect.y1) - float(page_rect.y1)) < 2
    )


def _expanded_rect(rect: Any, page_rect: Any) -> Any:
    margin_x = max(12.0, page_rect.width * 0.015)
    top_margin = 1.0
    bottom_margin = max(6.0, page_rect.height * 0.01)
    return rect.__class__(
        max(page_rect.x0, rect.x0 - margin_x),
        max(page_rect.y0, rect.y0 - top_margin),
        min(page_rect.x1, rect.x1 + margin_x),
        min(page_rect.y1, rect.y1 + bottom_margin),
    )


def _discover_private_pdfs(
    private_source_deck: str | None, inventory_roots: list[str] | None, source_label: str
) -> list[Path]:
    paths: list[Path] = []
    if private_source_deck:
        candidate = Path(private_source_deck)
        if candidate.is_file() and candidate.suffix.lower() == ".pdf" and is_private_artifact_dir(candidate.parent):
            paths.append(candidate)
    roots = [Path(root) for root in (list(_DEFAULT_PRIVATE_ROOTS) if inventory_roots is None else inventory_roots)]
    for root in roots:
        if not root.exists() or not is_private_artifact_dir(root):
            continue
        for path in root.rglob("*.pdf"):
            if path.is_file() and is_private_artifact_dir(path.parent):
                paths.append(path)
    deduped: list[Path] = []
    seen: set[str] = set()
    label = (source_label or "").lower()
    for path in paths:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    deduped.sort(key=lambda p: (0 if label and label in p.name.lower() else 1, len(p.parts), p.name.lower()))
    return deduped


def _private_descriptor_from_candidate(candidate: dict[str, Any], *, source_label: str) -> dict[str, Any]:
    return {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        "candidate_source": _candidate_source(candidate),
        "candidate_scan_mode": _scan_mode(candidate),
        "selected_asset_category": _asset_category(candidate),
        "selected_asset_kind": _asset_kind(candidate),
        "selected_asset_role": "study_visual",
        "visual_type_hypothesis": _visual_type(candidate),
        "private_visual_crop_path": candidate.get("_private_visual_crop_path"),
        "private_source_path": candidate.get("_private_source_path"),
        "page_local_visual_location": {
            "page_index": candidate.get("_private_page_index"),
            "bbox": candidate.get("_private_bbox"),
        },
        "private_context_text": candidate.get("_private_context_text"),
        "private_structure": _non_table_structure(candidate),
        "safe_insertion_mode": "private_image_asset",
        "visual_is_table_like": False,
        "visual_is_matrix": False,
        "visual_is_grid": False,
    }


def _private_manifest_context(entry: dict[str, Any]) -> str:
    parts: list[str] = []
    html = entry.get("raw_layout_html")
    if isinstance(html, str):
        parts.append(_strip_tags(html))
    normalized = entry.get("normalized")
    if isinstance(normalized, dict):
        for value in normalized.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(item) for item in value if isinstance(item, str))
    return "\n".join(part for part in parts if part).strip()


def _write_summary_if_private(summary: dict[str, Any], out_dir: Path) -> None:
    if not is_private_artifact_dir(out_dir):
        return
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / SUMMARY_FILENAME).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        pass


def _assert_closed_summary_safe(summary: dict[str, Any]) -> None:
    blob = json.dumps(summary, sort_keys=True)
    lowered = blob.lower()
    if any(marker in lowered for marker in _RAW_SUMMARY_MARKERS):
        raise ValueError("closed summary contains forbidden raw marker")
    for value in _walk_values(summary):
        if isinstance(value, str):
            if "/" in value or "\\" in value:
                raise ValueError("closed summary contains path-like string")
            if re.search(r"\b[a-f0-9]{16,}\b", value.lower()):
                raise ValueError("closed summary contains hash-like string")


def _walk_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        out: list[Any] = []
        for item in value.values():
            out.extend(_walk_values(item))
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_walk_values(item))
        return out
    return [value]


def _candidate_score(candidate: dict[str, Any]) -> int:
    category = _asset_category(candidate)
    priority = {
        "decision_tree_diagram": 90,
        "ensemble_structure_diagram": 88,
        "flowchart": 80,
        "conceptual_diagram": 75,
        "chart": 70,
        "plot": 70,
        "graph": 70,
        "diagram": 60,
        "figure": 50,
    }.get(category, 0)
    if _private_visual_available(candidate):
        priority += 10
    if _has_non_table_structure(candidate):
        priority += 5
    return priority


def _asset_category(candidate: dict[str, Any]) -> str:
    raw = candidate.get("asset_category") or candidate.get("visual_type") or candidate.get("asset_type")
    token = _normalize_token(raw)
    token = _CATEGORY_ALIASES.get(token, token)
    return _coerce(token, ASSET_CATEGORIES, "none")


def _asset_kind(candidate: dict[str, Any]) -> str:
    raw = candidate.get("asset_kind") or candidate.get("asset_type") or candidate.get("visual_type")
    token = _normalize_token(raw)
    token = _KIND_ALIASES.get(token, token)
    if token == "unknown":
        token = _asset_category(candidate)
    return _coerce(token, ASSET_KINDS, "unknown")


def _visual_type(candidate: dict[str, Any]) -> str:
    token = _normalize_token(candidate.get("visual_type")) or _asset_category(candidate)
    token = _CATEGORY_ALIASES.get(token, token)
    return _coerce(token, VISUAL_TYPES, "none")


def _candidate_source(candidate: dict[str, Any]) -> str:
    return _coerce(candidate.get("candidate_source"), CANDIDATE_SOURCES, "none")


def _scan_mode(candidate: dict[str, Any]) -> str:
    return _coerce(candidate.get("candidate_scan_mode"), SCAN_MODES, "no_candidate")


def _category_from_manifest(value: Any) -> str:
    token = _normalize_token(value)
    if token.startswith("ensemble_"):
        token = token.removeprefix("ensemble_")
    return _coerce(_CATEGORY_ALIASES.get(token, token), ASSET_CATEGORIES, "none")


def _visual_shape_flags(candidate: dict[str, Any]) -> dict[str, bool]:
    text = _closed_candidate_text(candidate)
    table_payload = bool(candidate.get("table_json") or candidate.get("table_markdown"))
    table_signal = bool(candidate.get("has_table") or candidate.get("table_count"))
    rows = _safe_int(candidate.get("max_table_rows") or candidate.get("rows"))
    cols = _safe_int(candidate.get("max_table_cols") or candidate.get("cols"))
    matrix = "matrix" in text or "proximity" in text
    grid = "grid" in text or (rows >= 2 and cols >= 2)
    table_like = table_payload or table_signal or matrix or grid or any(token in text for token in _TABLE_LIKE_TOKENS)
    return {
        "visual_is_table_like": table_like,
        "visual_is_matrix": matrix,
        "visual_is_grid": grid,
    }


def _closed_candidate_text(candidate: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "asset_category",
        "asset_kind",
        "asset_type",
        "visual_type",
        "display_role",
        "placement_hint",
        "candidate_source",
        "candidate_scan_mode",
    ):
        value = candidate.get(key)
        if isinstance(value, str):
            values.append(value)
    return " ".join(values).lower().replace("-", "_")


def _looks_table_like_text(text: str) -> bool:
    return any(token in text for token in ("table", "matrix", "dataset", "row", "column", "cell"))


def _looks_text_only_page(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    if not normalized:
        return False
    return any(token in normalized for token in _TEXT_ONLY_REJECT_TOKENS)


def _is_ensemble_structure_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    return all(token in normalized for token in _ENSEMBLE_STRUCTURE_TOKENS)


def _source_matches_label(value: Any, source_label: Any) -> bool:
    label = _normalize_token(source_label)
    if not label or label == "unknown":
        return False
    haystack = _normalize_token(value)
    return label in haystack


def _has_non_table_structure(candidate: dict[str, Any]) -> bool:
    return bool(_non_table_structure(candidate))


def _has_dominant_non_text_visual_structure(candidate: dict[str, Any]) -> bool:
    if _has_non_table_structure(candidate):
        return True
    if _safe_int(candidate.get("visual_structure_score")) >= 8 and _private_visual_available(candidate):
        return True
    return False


def _non_table_structure(candidate: dict[str, Any]) -> dict[str, Any]:
    structure: dict[str, Any] = {}
    for key in _NON_TABLE_STRUCTURE_KEYS:
        value = candidate.get(key)
        if isinstance(value, list) and value:
            structure[key] = value
    return structure


def _private_visual_available(candidate: dict[str, Any]) -> bool:
    path = candidate.get("_private_visual_crop_path") or candidate.get("private_visual_crop_path")
    return isinstance(path, str) and bool(path) and Path(path).is_file() and is_private_artifact_dir(Path(path).parent)


def _visual_quality_flags(candidate: dict[str, Any]) -> dict[str, bool]:
    flags = {
        "visual_is_text_only": _quality_flag(candidate, "visual_is_text_only"),
        "visual_is_partial_sliver": _quality_flag(candidate, "visual_is_partial_sliver"),
        "visual_source_matches_label": _quality_flag(candidate, "visual_source_matches_label", default=True),
    }
    if not _has_dominant_non_text_visual_structure(candidate):
        flags["visual_is_text_only"] = True
    return flags


def _quality_flag(candidate: dict[str, Any], key: str, *, default: bool = False) -> bool:
    value = candidate.get(key)
    if isinstance(value, bool):
        return value
    return default


def _normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    roots = os.environ.get("PRIVATE_INVENTORY_ROOTS")
    summary = run_non_table_figure_descriptor(
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR"),
        private_descriptor_dir=os.environ.get("PRIVATE_DESCRIPTOR_DIR"),
        private_visible_artifact=os.environ.get("PRIVATE_VISIBLE_ARTIFACT"),
        private_source_deck=os.environ.get("PRIVATE_SOURCE_DECK"),
        source_label=os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT),
        inventory_roots=[item for item in roots.split(os.pathsep) if item] if roots else None,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
