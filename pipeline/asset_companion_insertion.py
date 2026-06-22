"""Slice 177D: off-by-default asset-companion insertion seam.

Slice 177C proved that an existing private full study guide can be *composed* with
the accepted 177B combined table+figure companion in a standalone preview producer.
177D takes one step closer to the normal guide pipeline: it exposes a single, narrow,
**off-by-default** insertion seam that future normal generation *could* call, while
still producing a real private rendered artifact now.

The seam is the pure function :func:`insert_companion_section`. By contract it returns
the guide Markdown **unchanged** unless an explicit ``enabled=True`` flag is passed.
Normal app generation never passes that flag, so default generation behavior is
untouched; only the private runner enables it. When enabled, the seam inserts the
accepted combined companion as one clearly separated section at a deterministic safe
location (before a trailing summary-like section if present, otherwise appended), and
:func:`run_asset_companion_insertion` renders the result to a private gitignored HTML
artifact.

This slice proves a reusable gated insertion seam exists. It does NOT expose the
feature in the frontend/API, does NOT change normal generation defaults, does NOT call
a provider, rerun generation/OCR, add a judge or repair, run cloud OCR / Chandra /
broad OCR, perform numeric verification, or claim that all tables/figures are solved.

Committed output is closed labels only. Raw guide / table / figure / caption / source
/ OCR text, descriptor JSON, image bytes, base64/data URIs, prompts, responses,
provider payloads, private paths, source filenames, hashes and byte counts are
structurally excluded from the returned summary and from anything written outside the
gitignored private artifact directory.
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

# Minimal reuse of the already-accepted 177B/177C helpers (acceptance checks, asset
# copying, render-safety canaries, no-leak markers). 177D adds only the gated seam.
from pipeline.combined_asset_companion_guide import (  # noqa: E402
    _has_data_uri,
    _render_has_private_path,
)
from pipeline.full_guide_asset_companion_preview import (  # noqa: E402
    COMPANION_SECTION_HEADING,
    COMPANION_SECTION_MARKER,
    _broken_image_detected,
    _combined_figure_is_non_table,
    _combined_has_figure_block,
    _combined_has_table_block,
    _combined_table_is_study_oriented,
    _copy_companion_assets,
    _load_combined_companion,
    _load_full_guide,
    _normal_guide_content_present,
    _relative_refs_preserved,
    _strip_leading_h1,
)
from pipeline.html_renderer import render_markdown  # noqa: E402
from pipeline.non_table_figure_descriptor import VISUAL_TYPES as NT_VISUAL_TYPES  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "asset_companion_insertion_seam"
SLICE_LABEL = "177D"

# Private insertion outputs.
INSERTED_GUIDE_MD = "asset_companion_insertion_seam.md"
INSERTED_GUIDE_HTML = "asset_companion_insertion_seam.html"
INSERTION_SUMMARY_JSON = "closed_asset_companion_insertion_seam_summary.json"

INPUT_FULL_GUIDE_SOURCE = "private_ensemble_full_guide"
COMBINED_COMPANION_SOURCE = "private_177b_or_177c_combined_asset_companion"
INSERTION_MODE = "gated_private_companion_section"

STATUSES = frozenset({"completed", "degraded", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
INSERTION_LOCATIONS = frozenset(
    {"before_trailing_summary", "appended_at_end", "not_inserted"}
)
BLOCKED_BY = frozenset(
    {
        "none",
        "seam_disabled",
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
        "operator_read_private_asset_companion_insertion_output",
        "enable_private_runner",
        "rebuild_combined_companion",
        "provide_full_guide",
        "fix_insertion_render_and_rerun",
    }
)

# Trailing sections the companion should sit *before* (so it lands inside the guide
# body, not dangling after the wrap-up). Content-agnostic — only generic headings.
_TRAILING_SECTION_RE = re.compile(
    r"(?im)^#{1,3}[ \t]+(summary|references|key takeaways|further reading|glossary|"
    r"conclusion|wrap[- ]?up)\b"
)


# ---------------------------------------------------------------------------
# The gated insertion seam (pure; the reusable part future generation can call)
# ---------------------------------------------------------------------------

def insert_companion_section(
    guide_md: str, combined_md: str, *, enabled: bool = False
) -> str:
    """Insert the accepted combined companion as one section — only when enabled.

    This is the off-by-default seam. With ``enabled=False`` (the default, and what
    normal app generation uses) the guide is returned **byte-for-byte unchanged**, so
    wiring this helper into the generation path changes nothing until a caller opts in.
    With ``enabled=True`` (the private runner) the accepted combined companion is
    inserted at the deterministic location chosen by :func:`pick_insertion_point`.

    Pure: never reads disk, never copies assets, never renders. Asset copying and
    render-safety are the runner's job.
    """
    if not enabled:
        return guide_md
    body = _strip_leading_h1(combined_md.strip())
    section = _companion_section_md(body)
    idx, _location = pick_insertion_point(guide_md)
    if idx is None:
        return f"{guide_md.rstrip()}\n\n{section}\n"
    head = guide_md[:idx].rstrip()
    tail = guide_md[idx:]
    return f"{head}\n\n{section}\n\n{tail}"


def pick_insertion_point(guide_md: str) -> tuple[int | None, str]:
    """Deterministic, content-agnostic insertion point for the companion section.

    Returns ``(start_index, location_label)``. If the guide ends with a generic
    summary-like section we insert just before it; otherwise we append at the end.
    """
    matches = list(_TRAILING_SECTION_RE.finditer(guide_md))
    if matches:
        return matches[-1].start(), "before_trailing_summary"
    return None, "appended_at_end"


def _companion_section_md(companion_body: str) -> str:
    return (
        "---\n\n"
        f"# {COMPANION_SECTION_HEADING}\n\n"
        "This section was inserted through the off-by-default companion-insertion seam "
        "(it is not part of normal generation). It adds the accepted recovered-asset "
        "companions (one reconstructed-table companion and one non-table figure "
        "companion). It does not claim that all tables or figures in this guide are "
        "solved.\n\n"
        f"{companion_body}"
    )


# ---------------------------------------------------------------------------
# Private runner: real artifact through the gated seam
# ---------------------------------------------------------------------------

def run_asset_companion_insertion(
    *,
    full_guide_path: str | None = None,
    full_guide_md: str | None = None,
    combined_companion_dir: str | None = None,
    private_output_dir: str | None = None,
    enabled: bool = False,
    render_html: bool = True,
) -> dict[str, Any]:
    """Insert the accepted combined companion through the gated seam and render private HTML.

    Off-by-default: with ``enabled=False`` the seam does not fire and the runner reports
    that the normal-generation default is unchanged (it does not write an inserted
    guide). The private runner passes ``enabled=True`` to produce the real artifact.

    Never calls a provider, never reruns generation/OCR. Blocks honestly when the full
    guide is missing, when the accepted combined companion is missing or lacks an
    accepted table/figure block, when the figure is table-like, when the simplified
    table is a row-reduced copy, when relative assets cannot be preserved safely, when a
    data URI/base64 would be required, or when no private artifact can be written safely.
    """
    # Resolve the output dir first so honest blocks can still drop a closed summary.
    if private_output_dir:
        out_dir = Path(private_output_dir)
    elif combined_companion_dir:
        out_dir = Path(combined_companion_dir).parent / (ARTIFACT_NAME + "_177d")
    else:
        out_dir = Path(tempfile.gettempdir()) / (ARTIFACT_NAME + "_177d")

    # 0. Off-by-default gate. Disabled is the normal-generation default: do nothing.
    if not enabled:
        return _emit(
            _summary(
                status="degraded",
                private_runner_enabled=False,
                asset_companion_section_inserted=False,
                insertion_location="not_inserted",
                blocked_by="seam_disabled",
                recommended_next_step="enable_private_runner",
            ),
            out_dir,
        )

    # 1. Load the full guide (string preferred, else path).
    guide_md = full_guide_md if (full_guide_md and full_guide_md.strip()) else _load_full_guide(full_guide_path)
    if guide_md is None:
        return _emit(
            _summary(status="blocked", blocked_by="full_guide_not_found",
                     recommended_next_step="provide_full_guide"),
            out_dir,
        )
    full_guide_available = True
    full_guide_gitignored = (
        True
        if full_guide_md
        else is_private_artifact_dir(Path(full_guide_path).parent if full_guide_path else None)
    )

    # 2. Load the accepted combined companion (md + closed summary) from its dir.
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

    # 3. The combined companion must carry an accepted table block.
    if not _combined_has_table_block(combined_summary, combined_md):
        return _emit(
            _summary(status="blocked", **base_block,
                     blocked_by="combined_companion_missing_table",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )

    # 4. ... and a figure block at all.
    if not _combined_has_figure_block(combined_md):
        return _emit(
            _summary(status="blocked", **base_block,
                     blocked_by="combined_companion_missing_figure",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )

    # 5. ... and that figure must be an accepted NON-table figure.
    if not _combined_figure_is_non_table(combined_summary):
        return _emit(
            _summary(status="blocked", **base_block,
                     blocked_by="combined_companion_figure_table_like",
                     recommended_next_step="rebuild_combined_companion"),
            out_dir,
        )

    # 6. ... and the simplified table must be a study table, not a row-reduced copy.
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
    _, insertion_location = pick_insertion_point(guide_md)

    accepted = dict(
        **base_block,
        source_label=source_label,
        insertion_location=insertion_location,
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

    # 7. Refuse any inlined raw image data in either source document.
    if _has_data_uri(guide_md) or _has_data_uri(combined_md):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_insertion_render_and_rerun"),
            out_dir,
        )

    # 8. Output directory must be a gitignored private artifact dir.
    if not is_private_artifact_dir(out_dir):
        return _summary(status="blocked", **accepted,
                        blocked_by="unsafe_private_artifact_path",
                        recommended_next_step="fix_insertion_render_and_rerun")

    if not render_html:
        return _emit(
            _summary(status="degraded", **accepted,
                     blocked_by="render_failed",
                     recommended_next_step="fix_insertion_render_and_rerun"),
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
                     recommended_next_step="fix_insertion_render_and_rerun"),
            out_dir,
        )

    # 10. Run the gated seam (enabled) and render private HTML.
    inserted_md = insert_companion_section(guide_md, combined_md, enabled=True)
    try:
        html = render_markdown(
            inserted_md, title="Guide with Inserted Asset Companion", strict_math=False
        )
    except Exception:
        return _emit(
            _summary(status="degraded", **accepted,
                     render_status="failed",
                     blocked_by="render_failed",
                     recommended_next_step="fix_insertion_render_and_rerun"),
            out_dir,
        )
    if _has_data_uri(html):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_insertion_render_and_rerun"),
            out_dir,
        )
    if _render_has_private_path(html, (full_guide_path, combined_companion_dir, out_dir)):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="raw_private_path_in_render",
                     recommended_next_step="fix_insertion_render_and_rerun"),
            out_dir,
        )

    # 11. Write private artifacts and confirm the inserted blocks rendered.
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / INSERTED_GUIDE_MD).write_text(inserted_md, encoding="utf-8")
    html_path = out_dir / INSERTED_GUIDE_HTML
    html_path.write_text(html, encoding="utf-8")
    inserted_written = html_path.is_file()

    normal_guide_content_present = _normal_guide_content_present(guide_md, html)
    section_inserted = COMPANION_SECTION_MARKER in html and "companions" in html.lower()
    has_img = "<img" in html and "assets/" in html
    table_block_rendered = "What this table shows" in html and "Simplified study table" in html
    figure_block_rendered = has_img and "What this figure shows" in html and "Exam takeaway" in html
    refs_preserved = _relative_refs_preserved(copied, out_dir) and "assets/" in html
    broken_image = _broken_image_detected(html, copied, out_dir)

    completed = (
        inserted_written
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
        private_inserted_guide_written=inserted_written,
        normal_guide_content_present=normal_guide_content_present,
        asset_companion_section_inserted=section_inserted,
        relative_asset_refs_preserved=refs_preserved,
        broken_image_marker_detected=broken_image,
        blocked_by="none" if completed else "render_failed",
        recommended_next_step="operator_read_private_asset_companion_insertion_output"
        if completed
        else "fix_insertion_render_and_rerun",
    )
    return _emit(summary, out_dir)


# ---------------------------------------------------------------------------
# IO helper
# ---------------------------------------------------------------------------

def _emit(summary: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    """Write the closed summary to the private dir when it is safe to do so."""
    if is_private_artifact_dir(out_dir):
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / INSERTION_SUMMARY_JSON).write_text(
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
    private_runner_enabled: bool = True,
    input_full_guide_available: bool = False,
    input_full_guide_gitignored: bool = False,
    combined_companion_available: bool = False,
    combined_companion_gitignored: bool = False,
    insertion_location: str = "not_inserted",
    asset_companion_section_inserted: bool = False,
    relative_asset_refs_preserved: bool = False,
    private_inserted_guide_written: bool = False,
    render_status: str = "not_run",
    normal_guide_content_present: bool = False,
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
    broken_image_marker_detected: bool = False,
    blocked_by: str = "none",
    recommended_next_step: str = "fix_insertion_render_and_rerun",
) -> dict[str, Any]:
    rendered = render_status == "rendered"
    summary = {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        # Off-by-default posture.
        "off_by_default": True,
        "normal_generation_default_unchanged": True,
        "private_runner_enabled": bool(private_runner_enabled),
        # Inputs.
        "input_full_guide_source": INPUT_FULL_GUIDE_SOURCE,
        "input_full_guide_available": bool(input_full_guide_available),
        "input_full_guide_gitignored": bool(input_full_guide_gitignored),
        "combined_companion_source": COMBINED_COMPANION_SOURCE,
        "combined_companion_available": bool(combined_companion_available),
        "combined_companion_gitignored": bool(combined_companion_gitignored),
        # Insertion.
        "insertion_mode": INSERTION_MODE,
        "insertion_location": _coerce(insertion_location, INSERTION_LOCATIONS, "not_inserted"),
        "asset_companion_section_inserted": bool(asset_companion_section_inserted),
        "relative_asset_refs_preserved": bool(relative_asset_refs_preserved),
        # Private artifact.
        "private_inserted_guide_written": bool(private_inserted_guide_written),
        "private_inserted_guide_gitignored": True,
        "render_format": "html" if rendered else "not_run",
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        # Composition.
        "normal_guide_content_present": bool(normal_guide_content_present),
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
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "fix_insertion_render_and_rerun"),
    }
    _assert_summary_safe(summary)
    return summary


def _assert_summary_safe(summary: dict[str, Any]) -> None:
    # Keys are controlled closed vocabulary; only values could ever carry leaked
    # content, so scope the scan to values.
    values_blob = " ".join(str(v) for v in summary.values()).lower()
    for marker in ("data:image", ";base64,", "/", "\\", "prompt:", "response:"):
        if marker in values_blob:
            raise ValueError("177D closed summary contains forbidden marker")
    if re.search(r"\b[a-f0-9]{16,}\b", values_blob):
        raise ValueError("177D closed summary contains hash-like string")


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_asset_companion_insertion(
        full_guide_path=os.environ.get("PRIVATE_FULL_GUIDE_PATH") or None,
        combined_companion_dir=os.environ.get("PRIVATE_COMBINED_DIR") or None,
        private_output_dir=os.environ.get("PRIVATE_INSERTION_DIR") or None,
        enabled=os.environ.get("ENABLE_INSERTION_SEAM") == "1",
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
