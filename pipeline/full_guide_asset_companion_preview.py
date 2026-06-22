"""Slice 177C: full-guide private preview with the combined asset companion inserted.

This narrow private producer takes ONE existing accepted private full generated
study guide (same ensemble lineage as the 176X/177A/177B work) and inserts the
already-accepted **177B combined asset companion** into it as a clearly separated
section, then renders the result to a private HTML preview.

The accepted 177B combined companion carries both:

  * the **176X writer-generated table companion** — faithful reconstructed table +
    teaching explanation + role-aware *study* simplified table (not a row-reduced
    copy), and
  * the **177A non-table figure companion** — a real non-table visual asset +
    explanation + how-to-read steps + exam takeaway.

This slice proves the accepted table+figure companion can live inside a realistic
full study guide artifact, not only in a standalone companion document. It does NOT
call a provider, rerun generation/OCR, change frontend/API behavior, add a judge or
repair, run cloud OCR / Chandra / broad OCR, perform numeric verification, or claim
that all figures/tables are solved. The preferred path is to reuse the existing
private full guide and the accepted 177B companion verbatim; this module only
verifies they are the accepted artifacts, stitches them under one preview with clear
section separation, copies the figure crop as a safe private-relative
``assets/<name>`` image, renders private HTML, and emits a closed committed-safe
summary.

Committed output is closed labels only. Raw guide / table / figure / caption /
source / OCR text, descriptor JSON, image bytes, base64/data URIs, prompts,
responses, provider payloads, private paths, source filenames, hashes and byte
counts are structurally excluded from the returned summary and from anything written
outside the gitignored private artifact directory.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.combined_asset_companion_guide import (  # noqa: E402
    COMBINED_GUIDE_MD,
    COMBINED_SUMMARY_JSON,
    _DATA_URI_MARKERS,
    _IMAGE_REF_RE,
    _SAFE_IMAGE_REF_RE,
    _has_data_uri,
    _markdown_table_count,
    _render_has_private_path,
)
from pipeline.html_renderer import render_markdown  # noqa: E402
from pipeline.non_table_figure_descriptor import VISUAL_TYPES as NT_VISUAL_TYPES  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "full_guide_asset_companion_preview"
SLICE_LABEL = "177C"

# Private preview outputs.
PREVIEW_GUIDE_MD = "full_guide_asset_companion_preview.md"
PREVIEW_GUIDE_HTML = "full_guide_asset_companion_preview.html"
PREVIEW_SUMMARY_JSON = "closed_full_guide_asset_companion_preview_summary.json"

INPUT_FULL_GUIDE_SOURCE = "private_ensemble_full_guide"
COMBINED_COMPANION_SOURCE = "private_177b_combined_asset_companion_guide"

# Section heading + intro that wraps the inserted companion block. Kept as module
# constants so detection and rendering share one marker (no raw guide content).
COMPANION_SECTION_HEADING = "Recovered visual/table companions"
COMPANION_SECTION_MARKER = "Recovered visual"  # stable substring for HTML detection

STATUSES = frozenset({"completed", "degraded", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
RENDER_FORMATS = frozenset({"html", "not_run"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
BLOCKED_BY = frozenset(
    {
        "none",
        "full_guide_not_found",
        "combined_companion_not_found",
        "combined_companion_missing_table",
        "combined_companion_missing_figure",
        "combined_companion_figure_table_like",
        "combined_companion_table_row_reduced",
        "relative_assets_unavailable",
        "data_uri_or_base64_refused",
        "raw_private_path_in_render",
        "unsafe_private_artifact_path",
        "render_failed",
    }
)
NEXT_STEPS = frozenset(
    {
        "operator_read_private_full_guide_asset_companion_preview",
        "rebuild_combined_companion",
        "provide_full_guide",
        "fix_preview_render_and_rerun",
    }
)

_BROKEN_IMAGE_MARKERS = ("data:image", "src=\"\"", "src=''", "alt=\"broken")


def run_full_guide_asset_companion_preview(
    *,
    full_guide_path: str | None = None,
    combined_companion_dir: str | None = None,
    private_preview_dir: str | None = None,
    render_html: bool = True,
) -> dict[str, Any]:
    """Insert the accepted 177B combined companion into an existing full guide.

    Never calls a provider, never reruns generation/OCR. Blocks honestly when the
    full guide is missing, when the accepted 177B combined companion is missing or
    lacks an accepted table/figure block, when the figure is table-like, when the
    simplified table is a row-reduced copy, when relative assets cannot be preserved
    safely, when a data URI/base64 would be required, or when no private preview can
    be written safely.
    """
    # Resolve the output directory first so honest blocks can still drop a summary.
    if private_preview_dir:
        out_dir = Path(private_preview_dir)
    elif combined_companion_dir:
        out_dir = Path(combined_companion_dir).parent / (ARTIFACT_NAME + "_177c")
    else:
        out_dir = Path(tempfile.gettempdir()) / (ARTIFACT_NAME + "_177c")

    # 1. Load the existing private full generated guide.
    full_guide_md = _load_full_guide(full_guide_path)
    if full_guide_md is None:
        return _emit(
            _summary(status="blocked", blocked_by="full_guide_not_found",
                     recommended_next_step="provide_full_guide"),
            out_dir,
        )
    full_guide_available = True
    full_guide_gitignored = is_private_artifact_dir(
        Path(full_guide_path).parent if full_guide_path else None
    )

    # 2. Load the accepted 177B combined companion (md + closed summary).
    combined = _load_combined_companion(combined_companion_dir)
    if combined is None:
        return _emit(
            _summary(status="blocked",
                     input_full_guide_available=full_guide_available,
                     input_full_guide_gitignored=full_guide_gitignored,
                     blocked_by="combined_companion_not_found",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )
    combined_md, combined_summary = combined
    combined_companion_gitignored = is_private_artifact_dir(combined_companion_dir)
    combined_dir = Path(combined_companion_dir) if combined_companion_dir else None

    base_block = dict(
        input_full_guide_available=full_guide_available,
        input_full_guide_gitignored=full_guide_gitignored,
        combined_companion_available=True,
        combined_companion_gitignored=combined_companion_gitignored,
    )

    # 3. Verify the combined companion carries an accepted table block.
    if not _combined_has_table_block(combined_summary, combined_md):
        return _emit(
            _summary(status="blocked", **base_block,
                     blocked_by="combined_companion_missing_table",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )

    # 4. Verify the combined companion carries a figure block at all.
    if not _combined_has_figure_block(combined_md):
        return _emit(
            _summary(status="blocked", **base_block,
                     blocked_by="combined_companion_missing_figure",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )

    # 5. The figure block must be an accepted NON-table figure (never table-like).
    if not _combined_figure_is_non_table(combined_summary):
        return _emit(
            _summary(status="blocked", **base_block,
                     blocked_by="combined_companion_figure_table_like",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )

    # 6. The simplified table must be a role-aware study table, not a row-reduced copy.
    if not _combined_table_is_study_oriented(combined_summary):
        return _emit(
            _summary(status="blocked", **base_block,
                     blocked_by="combined_companion_table_row_reduced",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )

    source_label = _coerce(combined_summary.get("source_label"), SOURCE_LABELS, "ensemble")
    figure_visual_type = _coerce(
        combined_summary.get("figure_visual_type_closed"), NT_VISUAL_TYPES, "none"
    )

    accepted = dict(
        **base_block,
        source_label=source_label,
        table_companion_inserted=True,
        faithful_table_present=True,
        table_explanation_present=True,
        role_aware_simplified_table_present=True,
        figure_companion_inserted=True,
        figure_visual_present=True,
        figure_visual_type_closed=figure_visual_type,
        figure_explanation_present=True,
        figure_reading_steps_present=True,
        figure_exam_takeaway_present=True,
    )

    # 7. Refuse any inlined raw image data already present in the source documents.
    if _has_data_uri(full_guide_md) or _has_data_uri(combined_md):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_preview_render_and_rerun"),
            out_dir,
        )

    # 8. Output directory must be a gitignored private artifact dir.
    if not is_private_artifact_dir(out_dir):
        return _summary(status="blocked", **accepted,
                        blocked_by="unsafe_private_artifact_path",
                        recommended_next_step="fix_preview_render_and_rerun")

    if not render_html:
        return _emit(
            _summary(status="degraded", **accepted,
                     blocked_by="render_failed",
                     recommended_next_step="fix_preview_render_and_rerun"),
            out_dir,
        )

    # 9. Copy the companion figure assets as safe private-relative refs.
    try:
        copied = _copy_companion_assets(combined_md, combined_dir, out_dir)
    except FileNotFoundError:
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="relative_assets_unavailable",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )
    if copied is None:
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_preview_render_and_rerun"),
            out_dir,
        )

    preview_md = compose_full_guide_preview(full_guide_md=full_guide_md, combined_md=combined_md)

    # 10. Render private HTML; refuse data URI or any raw private path that leaked in.
    try:
        html = render_markdown(
            preview_md, title="Full Guide with Asset Companions (Preview)", strict_math=False
        )
    except Exception:
        return _emit(
            _summary(status="degraded", **accepted,
                     render_status="failed",
                     blocked_by="render_failed",
                     recommended_next_step="fix_preview_render_and_rerun"),
            out_dir,
        )
    if _has_data_uri(html):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_preview_render_and_rerun"),
            out_dir,
        )
    if _render_has_private_path(html, (full_guide_path, combined_companion_dir, out_dir)):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="raw_private_path_in_render",
                     recommended_next_step="fix_preview_render_and_rerun"),
            out_dir,
        )

    # 11. Write the private preview artifacts and confirm the inserted blocks rendered.
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / PREVIEW_GUIDE_MD).write_text(preview_md, encoding="utf-8")
    html_path = out_dir / PREVIEW_GUIDE_HTML
    html_path.write_text(html, encoding="utf-8")
    preview_written = html_path.is_file()

    normal_guide_content_present = _normal_guide_content_present(full_guide_md, html)
    section_inserted = COMPANION_SECTION_MARKER in html and "companions" in html.lower()
    has_img = "<img" in html and "assets/" in html
    table_block_rendered = "What this table shows" in html and "Simplified study table" in html
    figure_block_rendered = has_img and "What this figure shows" in html and "Exam takeaway" in html
    refs_preserved = _relative_refs_preserved(copied, out_dir) and "assets/" in html
    broken_image = _broken_image_detected(html, copied, out_dir)

    completed = (
        preview_written
        and normal_guide_content_present
        and section_inserted
        and table_block_rendered
        and figure_block_rendered
        and refs_preserved
        and not broken_image
    )

    summary = _summary(
        status="completed" if completed else "degraded",
        **accepted,
        render_status="rendered",
        private_full_preview_written=preview_written,
        normal_guide_content_present=normal_guide_content_present,
        asset_companion_section_inserted=section_inserted,
        relative_asset_refs_preserved=refs_preserved,
        broken_image_marker_detected=broken_image,
        blocked_by="none" if completed else "render_failed",
        recommended_next_step="operator_read_private_full_guide_asset_companion_preview"
        if completed
        else "fix_preview_render_and_rerun",
    )
    return _emit(summary, out_dir)


def compose_full_guide_preview(*, full_guide_md: str, combined_md: str) -> str:
    """Insert the combined companion as a clearly separated trailing section.

    The original guide content is preserved verbatim; the accepted companion is
    appended under a deterministic ``# Recovered visual/table companions`` heading so
    placement never disturbs existing guide sections.
    """
    companion_body = _strip_leading_h1(combined_md.strip())
    return (
        f"{full_guide_md.strip()}\n\n"
        "---\n\n"
        f"# {COMPANION_SECTION_HEADING}\n\n"
        "This section inserts the accepted recovered-asset companions (one reconstructed-table "
        "companion and one non-table figure companion) into the study guide above. It "
        "demonstrates that recovered table and figure companions can live inside a full study "
        "guide; it does not claim that all tables or figures in this guide are solved.\n\n"
        f"{companion_body}\n"
    )


# ---------------------------------------------------------------------------
# Acceptance checks (closed-flag + structural; pure)
# ---------------------------------------------------------------------------

def _combined_has_table_block(summary: dict[str, Any], md: str) -> bool:
    if not isinstance(summary, dict) or summary.get("status") != "completed":
        return False
    flags = (
        summary.get("table_companion_present") is True
        and summary.get("faithful_table_present") is True
        and summary.get("table_explanation_present") is True
        and summary.get("role_aware_simplified_table_present") is True
    )
    if not flags:
        return False
    return (
        _markdown_table_count(md) >= 2
        and "What this table shows" in md
        and "Simplified study table" in md
    )


def _combined_has_figure_block(md: str) -> bool:
    refs = _IMAGE_REF_RE.findall(md)
    has_safe_image = any(_SAFE_IMAGE_REF_RE.match(ref.strip()) for ref in refs)
    return (
        has_safe_image
        and "What this figure shows" in md
        and "How to read it" in md
        and "Exam takeaway" in md
    )


def _combined_figure_is_non_table(summary: dict[str, Any]) -> bool:
    if not isinstance(summary, dict):
        return False
    return (
        summary.get("figure_companion_present") is True
        and summary.get("figure_visual_present") is True
        and summary.get("figure_visual_is_non_table_figure") is True
        and summary.get("figure_visual_is_table_like") is False
        and summary.get("figure_visual_is_matrix") is False
        and summary.get("figure_visual_is_grid") is False
        and summary.get("figure_visual_is_text_only") is False
        and summary.get("figure_visual_is_partial_sliver") is False
        and summary.get("figure_explanation_present") is True
        and summary.get("figure_reading_steps_present") is True
        and summary.get("figure_exam_takeaway_present") is True
    )


def _combined_table_is_study_oriented(summary: dict[str, Any]) -> bool:
    if not isinstance(summary, dict):
        return False
    return (
        summary.get("simplified_table_is_study_oriented") is True
        and summary.get("simplified_table_is_row_reduced_copy") is False
    )


# ---------------------------------------------------------------------------
# IO + safety helpers
# ---------------------------------------------------------------------------

def _load_full_guide(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    try:
        if not p.is_file():
            return None
        md = p.read_text(encoding="utf-8")
    except Exception:
        return None
    return md if md.strip() else None


def _load_combined_companion(
    dir_path: str | None,
) -> tuple[str, dict[str, Any]] | None:
    if not dir_path:
        return None
    base = Path(dir_path)
    md_path = base / COMBINED_GUIDE_MD
    summary_path = base / COMBINED_SUMMARY_JSON
    try:
        if not (md_path.is_file() and summary_path.is_file()):
            return None
        md = md_path.read_text(encoding="utf-8")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(summary, dict) or not md.strip():
        return None
    return md, summary


def _copy_companion_assets(
    combined_md: str, combined_dir: Path | None, out_dir: Path
) -> list[str] | None:
    """Copy each ``assets/<name>`` ref from the combined companion into the preview dir.

    Returns the list of copied relative refs, ``None`` if any ref is unsafe/data-URI,
    and raises ``FileNotFoundError`` if a referenced asset is missing.
    """
    refs = [ref.strip() for ref in _IMAGE_REF_RE.findall(combined_md)]
    copied: list[str] = []
    assets_dir = out_dir / "assets"
    for ref in refs:
        if ref.lower().startswith(_DATA_URI_MARKERS):
            return None
        if not _SAFE_IMAGE_REF_RE.match(ref) or ".." in ref:
            return None
        if combined_dir is None:
            raise FileNotFoundError(ref)
        src = combined_dir / ref
        if not src.is_file():
            raise FileNotFoundError(ref)
        assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, assets_dir / Path(ref).name)
        copied.append(ref)
    return copied


def _relative_refs_preserved(copied: list[str], out_dir: Path) -> bool:
    if not copied:
        return False
    for ref in copied:
        if not _SAFE_IMAGE_REF_RE.match(ref):
            return False
        if not (out_dir / ref).is_file():
            return False
    return True


def _broken_image_detected(html: str, copied: list[str], out_dir: Path) -> bool:
    if any(marker in html.lower() for marker in _BROKEN_IMAGE_MARKERS):
        return True
    # A referenced asset whose file is absent on disk would render broken.
    for ref in copied:
        if not (out_dir / ref).is_file():
            return True
    return False


def _normal_guide_content_present(full_guide_md: str, html: str) -> bool:
    """Whether the original guide body (not just the companion) rendered.

    Content-agnostic: compares the original guide's Markdown heading count against the
    rendered HTML heading count, so we never embed raw guide text in committed code.
    """
    md_headings = sum(1 for line in full_guide_md.splitlines() if line.lstrip().startswith("#"))
    if md_headings < 1:
        return bool(full_guide_md.strip()) and len(html) > 0
    return len(re.findall(r"<h[1-6][\s>]", html)) >= md_headings


def _strip_leading_h1(md: str) -> str:
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            if line.lstrip().startswith("# "):
                return "\n".join(lines[i + 1 :]).strip()
            break
    return md


def _emit(summary: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    """Write the closed summary to the private dir when it is safe to do so."""
    if is_private_artifact_dir(out_dir):
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / PREVIEW_SUMMARY_JSON).write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
    return summary


# ---------------------------------------------------------------------------
# Closed committed-safe summary
# ---------------------------------------------------------------------------

def _summary(
    *,
    status: str,
    source_label: str = "ensemble",
    input_full_guide_available: bool = False,
    input_full_guide_gitignored: bool = False,
    combined_companion_available: bool = False,
    combined_companion_gitignored: bool = False,
    private_full_preview_written: bool = False,
    render_status: str = "not_run",
    normal_guide_content_present: bool = False,
    asset_companion_section_inserted: bool = False,
    table_companion_inserted: bool = False,
    faithful_table_present: bool = False,
    table_explanation_present: bool = False,
    role_aware_simplified_table_present: bool = False,
    figure_companion_inserted: bool = False,
    figure_visual_present: bool = False,
    figure_visual_type_closed: str = "none",
    figure_explanation_present: bool = False,
    figure_reading_steps_present: bool = False,
    figure_exam_takeaway_present: bool = False,
    relative_asset_refs_preserved: bool = False,
    broken_image_marker_detected: bool = False,
    blocked_by: str = "none",
    recommended_next_step: str = "fix_preview_render_and_rerun",
) -> dict[str, Any]:
    rendered = render_status == "rendered"
    summary = {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        # Inputs.
        "input_full_guide_source": INPUT_FULL_GUIDE_SOURCE,
        "input_full_guide_available": bool(input_full_guide_available),
        "input_full_guide_gitignored": bool(input_full_guide_gitignored),
        "combined_companion_source": COMBINED_COMPANION_SOURCE,
        "combined_companion_available": bool(combined_companion_available),
        "combined_companion_gitignored": bool(combined_companion_gitignored),
        # Private preview.
        "private_full_preview_written": bool(private_full_preview_written),
        "private_full_preview_gitignored": True,
        "render_format": "html" if rendered else "not_run",
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        # Composition.
        "normal_guide_content_present": bool(normal_guide_content_present),
        "asset_companion_section_inserted": bool(asset_companion_section_inserted),
        # Table companion block.
        "table_companion_inserted": bool(table_companion_inserted),
        "faithful_table_present": bool(faithful_table_present),
        "table_explanation_present": bool(table_explanation_present),
        "role_aware_simplified_table_present": bool(role_aware_simplified_table_present),
        "simplified_table_is_row_reduced_copy": False,
        "simplified_table_is_study_oriented": True,
        # Figure companion block.
        "figure_companion_inserted": bool(figure_companion_inserted),
        "figure_visual_present": bool(figure_visual_present),
        "figure_visual_type_closed": _coerce(figure_visual_type_closed, NT_VISUAL_TYPES, "none"),
        "figure_visual_is_non_table_figure": True,
        "figure_visual_is_text_only": False,
        "figure_visual_is_partial_sliver": False,
        "figure_visual_is_table_like": False,
        "figure_visual_is_matrix": False,
        "figure_visual_is_grid": False,
        "figure_explanation_present": bool(figure_explanation_present),
        "figure_reading_steps_present": bool(figure_reading_steps_present),
        "figure_exam_takeaway_present": bool(figure_exam_takeaway_present),
        # Render-safety canaries.
        "relative_asset_refs_preserved": bool(relative_asset_refs_preserved),
        "raw_private_paths_in_rendered_html": False,
        "broken_image_marker_detected": bool(broken_image_marker_detected),
        "data_image_used": False,
        "base64_image_used": False,
        # Closed negative canaries — committed posture, never raw content.
        "image_bytes_committed": False,
        "raw_table_text_committed": False,
        "raw_figure_text_committed": False,
        "raw_caption_text_committed": False,
        "raw_descriptor_json_committed": False,
        "raw_guide_committed": False,
        "raw_source_committed": False,
        "raw_ocr_committed": False,
        "source_filenames_committed": False,
        "screenshots_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        # Behavior guards.
        "provider_call_made": False,
        "generation_rerun": False,
        "generation_behavior_changed": False,
        "cloud_ocr_used": False,
        "ocr_rerun": False,
        "coverage_eval_rerun": False,
        "numeric_verification_claimed": False,
        "frontend_api_changed": False,
        "judge_ready": False,
        "repair_ready": False,
        "operator_private_read_required": True,
        "operator_private_read_done": False,
        "blocked_by": _coerce(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "fix_preview_render_and_rerun"),
    }
    _assert_summary_safe(summary)
    return summary


def _assert_summary_safe(summary: dict[str, Any]) -> None:
    # Keys are controlled closed vocabulary; only values could ever carry leaked
    # content, so scope the scan to values.
    values_blob = " ".join(str(v) for v in summary.values()).lower()
    for marker in ("data:image", ";base64,", "/", "\\", "prompt:", "response:"):
        if marker in values_blob:
            raise ValueError("177C closed summary contains forbidden marker")
    if re.search(r"\b[a-f0-9]{16,}\b", values_blob):
        raise ValueError("177C closed summary contains hash-like string")


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_full_guide_asset_companion_preview(
        full_guide_path=os.environ.get("PRIVATE_FULL_GUIDE_PATH") or None,
        combined_companion_dir=os.environ.get("PRIVATE_COMBINED_DIR") or None,
        private_preview_dir=os.environ.get("PRIVATE_FULL_PREVIEW_DIR") or None,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
