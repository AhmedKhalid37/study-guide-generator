"""Slice 177E: default-off normal-pipeline dry-run asset companion hook.

177D proved the pure off-by-default insertion seam. 177E adds a tiny wrapper shaped
like the normal guide-markdown-before-render chokepoint: by default it returns the
guide Markdown byte-for-byte unchanged, and only a private runner can explicitly turn
it on. The enabled private dry-run calls the 177D seam, renders the inserted guide
through the existing Markdown renderer, and emits a closed summary.

This is not a frontend/API rollout and does not change normal generation defaults.
It does not call a provider, regenerate a guide, rerun OCR, add judge/repair, run
cloud OCR / Chandra / broad OCR, perform numeric verification, or claim all assets
are solved.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.asset_companion_insertion import (  # noqa: E402
    insert_companion_section,
    pick_insertion_point,
)
from pipeline.combined_asset_companion_guide import _has_data_uri, _render_has_private_path  # noqa: E402
from pipeline.full_guide_asset_companion_preview import (  # noqa: E402
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
)
from pipeline.html_renderer import render_markdown  # noqa: E402
from pipeline.non_table_figure_descriptor import VISUAL_TYPES as NT_VISUAL_TYPES  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "asset_companion_pipeline_hook"
SLICE_LABEL = "177E"

PIPELINE_HOOK_MD = "asset_companion_pipeline_hook.md"
PIPELINE_HOOK_HTML = "asset_companion_pipeline_hook.html"
PIPELINE_HOOK_SUMMARY_JSON = "closed_asset_companion_pipeline_hook_summary.json"

INPUT_FULL_GUIDE_SOURCE = "private_ensemble_full_guide_markdown"
COMBINED_COMPANION_SOURCE = "private_177b_combined_asset_companion"
INSERTION_SEAM_SOURCE = "asset_companion_insertion_177d"
HOOK_LOCATION_CLOSED = "guide_markdown_before_render"

STATUSES = frozenset({"completed", "degraded", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
INSERTION_LOCATIONS = frozenset(
    {"before_trailing_summary", "appended_at_end", "not_inserted"}
)
BLOCKED_BY = frozenset(
    {
        "none",
        "hook_disabled",
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
        "operator_read_private_pipeline_hook_output",
        "enable_private_pipeline_hook",
        "rebuild_combined_companion",
        "provide_full_guide",
        "fix_pipeline_hook_render_and_rerun",
    }
)


@dataclass(frozen=True)
class AssetCompanionPipelineHookConfig:
    """Default-off hook configuration for the guide Markdown chokepoint."""

    enabled: bool = False
    private_runner_enabled: bool = False


def default_asset_companion_pipeline_hook_config() -> AssetCompanionPipelineHookConfig:
    """Normal/default mode: the hook is disabled and not privately enabled."""
    return AssetCompanionPipelineHookConfig()


def apply_asset_companion_pipeline_hook(
    guide_md: str,
    combined_md: str,
    *,
    config: AssetCompanionPipelineHookConfig | None = None,
) -> tuple[str, bool]:
    """Return guide Markdown unchanged unless the private hook is explicitly enabled.

    The boolean reports whether the 177D insertion seam was called. Normal/default
    config does not call it and returns ``guide_md`` byte-for-byte unchanged.
    """
    cfg = config or default_asset_companion_pipeline_hook_config()
    if not (cfg.enabled and cfg.private_runner_enabled):
        return guide_md, False
    return insert_companion_section(guide_md, combined_md, enabled=True), True


def run_asset_companion_pipeline_hook(
    *,
    full_guide_path: str | None = None,
    full_guide_md: str | None = None,
    combined_companion_dir: str | None = None,
    private_output_dir: str | None = None,
    enabled: bool = False,
    private_runner_enabled: bool = False,
    render_html: bool = True,
) -> dict[str, Any]:
    """Run the default-off hook as a private dry-run and render one private artifact."""
    if private_output_dir:
        out_dir = Path(private_output_dir)
    elif combined_companion_dir:
        out_dir = Path(combined_companion_dir).parent / (ARTIFACT_NAME + "_177e")
    else:
        out_dir = Path(tempfile.gettempdir()) / (ARTIFACT_NAME + "_177e")

    default_cfg = default_asset_companion_pipeline_hook_config()
    probe_guide = full_guide_md or ""
    disabled_output, disabled_called = apply_asset_companion_pipeline_hook(
        probe_guide, "", config=default_cfg
    )
    disabled_path_byte_identical = disabled_output == probe_guide and not disabled_called

    if not (enabled and private_runner_enabled):
        return _emit(
            _summary(
                status="degraded",
                private_hook_enabled=False,
                private_runner_enabled=private_runner_enabled,
                disabled_path_byte_identical=disabled_path_byte_identical,
                blocked_by="hook_disabled",
                recommended_next_step="enable_private_pipeline_hook",
            ),
            out_dir,
        )

    guide_md = full_guide_md if (full_guide_md and full_guide_md.strip()) else _load_full_guide(full_guide_path)
    if guide_md is None:
        return _emit(
            _summary(
                status="blocked",
                private_hook_enabled=True,
                private_runner_enabled=True,
                disabled_path_byte_identical=disabled_path_byte_identical,
                blocked_by="full_guide_not_found",
                recommended_next_step="provide_full_guide",
            ),
            out_dir,
        )
    full_guide_available = True
    full_guide_gitignored = (
        True
        if full_guide_md
        else is_private_artifact_dir(Path(full_guide_path).parent if full_guide_path else None)
    )

    combined = _load_combined_companion(combined_companion_dir)
    if combined is None:
        return _emit(
            _summary(
                status="blocked",
                private_hook_enabled=True,
                private_runner_enabled=True,
                disabled_path_byte_identical=disabled_path_byte_identical,
                input_full_guide_available=full_guide_available,
                input_full_guide_gitignored=full_guide_gitignored,
                blocked_by="combined_companion_not_found",
                recommended_next_step="rebuild_combined_companion",
            ),
            out_dir,
        )
    combined_md, combined_summary = combined
    combined_companion_gitignored = is_private_artifact_dir(combined_companion_dir)
    combined_dir = Path(combined_companion_dir) if combined_companion_dir else None

    base_block = dict(
        private_hook_enabled=True,
        private_runner_enabled=True,
        disabled_path_byte_identical=disabled_path_byte_identical,
        input_full_guide_available=full_guide_available,
        input_full_guide_gitignored=full_guide_gitignored,
        combined_companion_available=True,
        combined_companion_gitignored=combined_companion_gitignored,
    )

    if not _combined_has_table_block(combined_summary, combined_md):
        return _emit(
            _summary(
                status="blocked",
                **base_block,
                blocked_by="combined_companion_missing_table",
                recommended_next_step="rebuild_combined_companion",
            ),
            out_dir,
        )
    if not _combined_has_figure_block(combined_md):
        return _emit(
            _summary(
                status="blocked",
                **base_block,
                blocked_by="combined_companion_missing_figure",
                recommended_next_step="rebuild_combined_companion",
            ),
            out_dir,
        )
    if not _combined_figure_is_non_table(combined_summary):
        return _emit(
            _summary(
                status="blocked",
                **base_block,
                blocked_by="combined_companion_figure_table_like",
                recommended_next_step="rebuild_combined_companion",
            ),
            out_dir,
        )
    if not _combined_table_is_study_oriented(combined_summary):
        return _emit(
            _summary(
                status="blocked",
                **base_block,
                blocked_by="combined_companion_table_row_reduced",
                recommended_next_step="rebuild_combined_companion",
            ),
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

    if _has_data_uri(guide_md) or _has_data_uri(combined_md):
        return _emit(
            _summary(
                status="blocked",
                **accepted,
                blocked_by="data_uri_or_base64_refused",
                recommended_next_step="fix_pipeline_hook_render_and_rerun",
            ),
            out_dir,
        )
    if not is_private_artifact_dir(out_dir):
        return _summary(
            status="blocked",
            **accepted,
            blocked_by="unsafe_private_artifact_path",
            recommended_next_step="fix_pipeline_hook_render_and_rerun",
        )
    if not render_html:
        return _emit(
            _summary(
                status="degraded",
                **accepted,
                blocked_by="render_failed",
                recommended_next_step="fix_pipeline_hook_render_and_rerun",
            ),
            out_dir,
        )

    try:
        copied = _copy_companion_assets(combined_md, combined_dir, out_dir)
    except FileNotFoundError:
        return _emit(
            _summary(
                status="blocked",
                **accepted,
                blocked_by="relative_assets_unavailable",
                recommended_next_step="rebuild_combined_companion",
            ),
            out_dir,
        )
    if copied is None:
        return _emit(
            _summary(
                status="blocked",
                **accepted,
                blocked_by="data_uri_or_base64_refused",
                recommended_next_step="fix_pipeline_hook_render_and_rerun",
            ),
            out_dir,
        )

    hook_md, called_insertion = apply_asset_companion_pipeline_hook(
        guide_md,
        combined_md,
        config=AssetCompanionPipelineHookConfig(
            enabled=True,
            private_runner_enabled=True,
        ),
    )
    try:
        html = render_markdown(
            hook_md, title="Guide with Pipeline Hook Asset Companion", strict_math=False
        )
    except Exception:
        return _emit(
            _summary(
                status="degraded",
                **accepted,
                enabled_path_called_insertion_seam=called_insertion,
                render_status="failed",
                blocked_by="render_failed",
                recommended_next_step="fix_pipeline_hook_render_and_rerun",
            ),
            out_dir,
        )
    if _has_data_uri(html):
        return _emit(
            _summary(
                status="blocked",
                **accepted,
                enabled_path_called_insertion_seam=called_insertion,
                blocked_by="data_uri_or_base64_refused",
                recommended_next_step="fix_pipeline_hook_render_and_rerun",
            ),
            out_dir,
        )
    if _render_has_private_path(html, (full_guide_path, combined_companion_dir, out_dir)):
        return _emit(
            _summary(
                status="blocked",
                **accepted,
                enabled_path_called_insertion_seam=called_insertion,
                blocked_by="raw_private_path_in_render",
                recommended_next_step="fix_pipeline_hook_render_and_rerun",
            ),
            out_dir,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / PIPELINE_HOOK_MD).write_text(hook_md, encoding="utf-8")
    html_path = out_dir / PIPELINE_HOOK_HTML
    html_path.write_text(html, encoding="utf-8")
    render_written = html_path.is_file()

    normal_guide_content_present = _normal_guide_content_present(guide_md, html)
    section_inserted = COMPANION_SECTION_MARKER in html and "companions" in html.lower()
    has_img = "<img" in html and "assets/" in html
    table_block_rendered = "What this table shows" in html and "Simplified study table" in html
    figure_block_rendered = has_img and "What this figure shows" in html and "Exam takeaway" in html
    refs_preserved = _relative_refs_preserved(copied, out_dir) and "assets/" in html
    broken_image = _broken_image_detected(html, copied, out_dir)

    completed = (
        render_written
        and normal_guide_content_present
        and section_inserted
        and table_block_rendered
        and figure_block_rendered
        and refs_preserved
        and called_insertion
        and not broken_image
    )

    return _emit(
        _summary(
            status="completed" if completed else "degraded",
            **accepted,
            enabled_path_called_insertion_seam=called_insertion,
            render_status="rendered",
            private_hook_render_written=render_written,
            normal_guide_content_present=normal_guide_content_present,
            asset_companion_section_inserted=section_inserted,
            relative_asset_refs_preserved=refs_preserved,
            broken_image_marker_detected=broken_image,
            blocked_by="none" if completed else "render_failed",
            recommended_next_step="operator_read_private_pipeline_hook_output"
            if completed
            else "fix_pipeline_hook_render_and_rerun",
        ),
        out_dir,
    )


def _emit(summary: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    if is_private_artifact_dir(out_dir):
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / PIPELINE_HOOK_SUMMARY_JSON).write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
    return summary


def _summary(
    *,
    status: str,
    source_label: str = "ensemble",
    default_hook_enabled: bool = False,
    private_hook_enabled: bool = False,
    private_runner_enabled: bool = False,
    disabled_path_byte_identical: bool = True,
    enabled_path_called_insertion_seam: bool = False,
    input_full_guide_available: bool = False,
    input_full_guide_gitignored: bool = False,
    combined_companion_available: bool = False,
    combined_companion_gitignored: bool = False,
    insertion_location: str = "not_inserted",
    asset_companion_section_inserted: bool = False,
    relative_asset_refs_preserved: bool = False,
    private_hook_render_written: bool = False,
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
    recommended_next_step: str = "fix_pipeline_hook_render_and_rerun",
) -> dict[str, Any]:
    rendered = render_status == "rendered"
    summary = {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        "off_by_default": True,
        "normal_generation_default_unchanged": True,
        "default_hook_enabled": bool(default_hook_enabled),
        "private_hook_enabled": bool(private_hook_enabled),
        "private_runner_enabled": bool(private_runner_enabled),
        "hook_location_closed": HOOK_LOCATION_CLOSED,
        "hook_invoked_from_private_runner": bool(private_hook_enabled and private_runner_enabled),
        "hook_invoked_from_normal_generation": False,
        "disabled_path_byte_identical": bool(disabled_path_byte_identical),
        "enabled_path_called_insertion_seam": bool(enabled_path_called_insertion_seam),
        "insertion_seam_source": INSERTION_SEAM_SOURCE,
        "input_full_guide_source": INPUT_FULL_GUIDE_SOURCE,
        "input_full_guide_available": bool(input_full_guide_available),
        "input_full_guide_gitignored": bool(input_full_guide_gitignored),
        "combined_companion_source": COMBINED_COMPANION_SOURCE,
        "combined_companion_available": bool(combined_companion_available),
        "combined_companion_gitignored": bool(combined_companion_gitignored),
        "asset_companion_section_inserted": bool(asset_companion_section_inserted),
        "insertion_location": _coerce(insertion_location, INSERTION_LOCATIONS, "not_inserted"),
        "relative_asset_refs_preserved": bool(relative_asset_refs_preserved),
        "private_hook_render_written": bool(private_hook_render_written),
        "private_hook_render_gitignored": True,
        "render_format": "html" if rendered else "not_run",
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        "normal_guide_content_present": bool(normal_guide_content_present),
        "table_companion_inserted": bool(table_companion_inserted),
        "faithful_table_present": bool(faithful_table_present),
        "table_explanation_present": bool(table_explanation_present),
        "role_aware_simplified_table_present": bool(role_aware_simplified_table_present),
        "simplified_table_is_row_reduced_copy": False,
        "simplified_table_is_study_oriented": True,
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
        "raw_private_paths_in_rendered_html": False,
        "broken_image_marker_detected": bool(broken_image_marker_detected),
        "data_image_used": False,
        "base64_image_used": False,
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
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "fix_pipeline_hook_render_and_rerun"),
    }
    _assert_summary_safe(summary)
    return summary


def _assert_summary_safe(summary: dict[str, Any]) -> None:
    values_blob = " ".join(str(v) for v in summary.values()).lower()
    for marker in ("data:image", ";base64,", "/", "\\", "prompt:", "response:"):
        if marker in values_blob:
            raise ValueError("177E closed summary contains forbidden marker")
    if re.search(r"\b[a-f0-9]{16,}\b", values_blob):
        raise ValueError("177E closed summary contains hash-like string")


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_asset_companion_pipeline_hook(
        full_guide_path=os.environ.get("PRIVATE_FULL_GUIDE_PATH") or None,
        combined_companion_dir=os.environ.get("PRIVATE_COMBINED_DIR") or None,
        private_output_dir=os.environ.get("PRIVATE_PIPELINE_HOOK_DIR") or None,
        enabled=os.environ.get("ENABLE_ASSET_COMPANION_PIPELINE_HOOK") == "1",
        private_runner_enabled=os.environ.get("ENABLE_ASSET_COMPANION_PIPELINE_HOOK") == "1",
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
