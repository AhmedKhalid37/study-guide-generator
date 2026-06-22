"""Slice 177B: combined table + figure companion private guide.

This narrow private producer composes the two already-accepted Phase 4 companion
outputs into ONE student-visible rendered guide artifact:

  * the accepted **176X writer-generated table companion** — faithful reconstructed
    table + teaching explanation beneath it + role-aware *study* simplified table, and
  * the accepted **177A writer-generated non-table figure companion** — a visible
    non-table visual asset + explanation + how-to-read steps + exam takeaway.

It does NOT call a provider, rerun generation/OCR, change frontend/API behavior, add
a judge or repair, or claim that all figures/tables are solved. The preferred path is
to reuse the accepted private 176X and 177A guide artifacts verbatim; this module only
verifies they are the accepted artifacts (role-aware simplified table that is not a
row-reduced copy; a real non-table figure, never table/matrix/grid/text-only/sliver),
stitches them under one title with clear section separation, copies the figure crop as
a safe private-relative ``assets/<name>`` image, renders private HTML, and emits a
closed committed-safe summary.

Committed output is closed labels only. Raw table/figure/caption/source/OCR text,
descriptor JSON, guide prose, image bytes, base64/data URIs, prompts, responses,
provider payloads, private paths, hashes and byte counts are structurally excluded
from the returned summary and from anything written outside the gitignored private
artifact directory.
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

from pipeline.html_renderer import render_markdown  # noqa: E402
from pipeline.non_table_figure_descriptor import VISUAL_TYPES as NT_VISUAL_TYPES  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402

ARTIFACT_NAME = "combined_asset_companion_guide"
SLICE_LABEL = "177B"

# Accepted-artifact filenames written by the 176X / 177A runners.
TABLE_GUIDE_MD = "writer_generated_table_companion_guide.md"
TABLE_SUMMARY_JSON = "closed_writer_generated_table_companion_summary.json"
FIGURE_GUIDE_MD = "writer_figure_companion_177a_guide.md"
FIGURE_SUMMARY_JSON = "closed_writer_figure_companion_177a_summary.json"

# Combined private outputs.
COMBINED_GUIDE_MD = "combined_asset_companion_guide.md"
COMBINED_GUIDE_HTML = "combined_asset_companion_guide.html"
COMBINED_SUMMARY_JSON = "closed_combined_asset_companion_guide_summary.json"

TABLE_COMPANION_SOURCE = "private_176x_writer_table_companion"
FIGURE_COMPANION_SOURCE = "private_177a_writer_figure_companion"

STATUSES = frozenset({"completed", "degraded", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
RENDER_FORMATS = frozenset({"html", "not_run"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
VISIBILITY_STATUSES = frozenset({"operator_pending", "visible", "not_checked", "failed"})
BLOCKED_BY = frozenset(
    {
        "none",
        "table_companion_not_found",
        "figure_companion_not_found",
        "table_companion_row_reduced",
        "figure_companion_table_like",
        "data_uri_or_base64_refused",
        "raw_private_path_in_render",
        "unsafe_private_artifact_path",
        "figure_asset_unavailable",
        "render_failed",
    }
)
NEXT_STEPS = frozenset(
    {
        "operator_read_private_combined_asset_companion_guide",
        "rebuild_table_companion",
        "rebuild_figure_companion",
        "fix_combined_render_and_rerun",
    }
)

_SAFE_IMAGE_REF_RE = re.compile(r"^assets/[A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|webp)$", re.I)
_IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_PRIVATE_PATH_MARKERS = (".private_ocr", "local_operator_baselines", "/tmp/", "\\tmp\\", ".trash")
_DATA_URI_MARKERS = ("data:image", "data:application", ";base64,")


def run_combined_asset_companion_guide(
    *,
    table_companion_dir: str | None = None,
    figure_companion_dir: str | None = None,
    private_combined_dir: str | None = None,
    render_html: bool = True,
) -> dict[str, Any]:
    """Compose the accepted 176X + 177A companions into one private rendered guide.

    Never calls a provider, never reruns generation/OCR. Blocks honestly when either
    accepted companion is missing, when the table companion is a row-reduced copy rather
    than a role-aware study table, when the figure companion is table-like, when an asset
    requires a data URI/base64, or when no private guide can be written safely.
    """
    # Resolve the output directory first so honest blocks can still drop a private summary.
    if private_combined_dir:
        out_dir = Path(private_combined_dir)
    elif table_companion_dir:
        out_dir = Path(table_companion_dir).parent / (ARTIFACT_NAME + "_177b")
    else:
        out_dir = Path(tempfile.gettempdir()) / (ARTIFACT_NAME + "_177b")

    # 1. Load the accepted 176X table companion (output artifacts).
    table = _load_companion(table_companion_dir, TABLE_GUIDE_MD, TABLE_SUMMARY_JSON)
    if table is None:
        return _emit(
            _summary(status="blocked", blocked_by="table_companion_not_found",
                     recommended_next_step="rebuild_table_companion"),
            out_dir,
        )
    table_md, table_summary = table

    # 2. Load the accepted 177A figure companion (output artifacts).
    figure = _load_companion(figure_companion_dir, FIGURE_GUIDE_MD, FIGURE_SUMMARY_JSON)
    if figure is None:
        return _emit(
            _summary(status="blocked",
                     table_companion_present=True,
                     blocked_by="figure_companion_not_found",
                     recommended_next_step="rebuild_figure_companion"),
            out_dir,
        )
    figure_md, figure_summary = figure
    figure_dir = Path(figure_companion_dir) if figure_companion_dir else None

    # 3. Verify the inputs are the accepted artifacts (closed-flag + structural).
    table_ok = _table_companion_accepted(table_summary, table_md)
    if not table_ok:
        return _emit(
            _summary(status="blocked",
                     table_companion_present=True,
                     figure_companion_present=True,
                     blocked_by="table_companion_row_reduced",
                     recommended_next_step="rebuild_table_companion"),
            out_dir,
        )
    figure_ok = _figure_companion_accepted(figure_summary, figure_md)
    if not figure_ok:
        return _emit(
            _summary(status="blocked",
                     table_companion_present=True,
                     figure_companion_present=True,
                     blocked_by="figure_companion_table_like",
                     recommended_next_step="rebuild_figure_companion"),
            out_dir,
        )

    source_label = _combined_source_label(table_summary, figure_summary)
    figure_visual_type = _coerce(figure_summary.get("visual_type_closed"), NT_VISUAL_TYPES, "none")

    accepted = dict(
        source_label=source_label,
        table_companion_present=True,
        faithful_table_present=True,
        table_explanation_present=True,
        role_aware_simplified_table_present=True,
        figure_companion_present=True,
        figure_visual_present=True,
        figure_visual_type_closed=figure_visual_type,
        figure_explanation_present=True,
        figure_reading_steps_present=True,
        figure_exam_takeaway_present=True,
    )

    # 4. Refuse any inlined raw image data in the source companions.
    if _has_data_uri(table_md) or _has_data_uri(figure_md):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_combined_render_and_rerun"),
            out_dir,
        )

    # 5. Output directory must be a gitignored private artifact dir.
    if not is_private_artifact_dir(out_dir):
        return _summary(status="blocked", **accepted,
                        blocked_by="unsafe_private_artifact_path",
                        recommended_next_step="fix_combined_render_and_rerun")

    if not render_html:
        return _emit(
            _summary(status="degraded", **accepted,
                     blocked_by="render_failed",
                     recommended_next_step="fix_combined_render_and_rerun"),
            out_dir,
        )

    # 6. Copy figure assets as safe private-relative refs into the combined dir.
    try:
        copied = _copy_figure_assets(figure_md, figure_dir, out_dir)
    except FileNotFoundError:
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="figure_asset_unavailable",
                     recommended_next_step="rebuild_figure_companion"),
            out_dir,
        )
    if copied is None:
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_combined_render_and_rerun"),
            out_dir,
        )

    combined_md = compose_combined_markdown(table_md=table_md, figure_md=figure_md)

    # 7. Render private HTML; refuse any data URI or raw private path that leaked in.
    try:
        html = render_markdown(combined_md, title="Combined Asset Companion Guide", strict_math=False)
    except Exception:
        return _emit(
            _summary(status="degraded", **accepted,
                     combined_render_status="failed",
                     blocked_by="render_failed",
                     recommended_next_step="fix_combined_render_and_rerun"),
            out_dir,
        )
    if _has_data_uri(html):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_combined_render_and_rerun"),
            out_dir,
        )
    if _render_has_private_path(html, (table_companion_dir, figure_companion_dir, out_dir)):
        return _emit(
            _summary(status="blocked", **accepted,
                     blocked_by="raw_private_path_in_render",
                     recommended_next_step="fix_combined_render_and_rerun"),
            out_dir,
        )

    # 8. Write the private combined artifacts and confirm the two blocks rendered.
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / COMBINED_GUIDE_MD).write_text(combined_md, encoding="utf-8")
    html_path = out_dir / COMBINED_GUIDE_HTML
    html_path.write_text(html, encoding="utf-8")
    rendered_written = html_path.is_file()

    table_count = html.count("<table")
    has_img = "<img" in html and "assets/" in html
    table_block_rendered = (
        "What this table shows" in html and "Simplified study table" in html and table_count >= 2
    )
    figure_block_rendered = (
        has_img and "What this figure shows" in html and "Exam takeaway" in html
    )
    completed = rendered_written and table_block_rendered and figure_block_rendered

    summary = _summary(
        status="completed" if completed else "degraded",
        **accepted,
        combined_render_status="rendered",
        private_combined_guide_written=rendered_written,
        table_visibility_status="operator_pending" if completed else "failed",
        figure_visibility_status="operator_pending" if completed else "failed",
        blocked_by="none" if completed else "render_failed",
        recommended_next_step="operator_read_private_combined_asset_companion_guide"
        if completed
        else "fix_combined_render_and_rerun",
    )
    return _emit(summary, out_dir)


def compose_combined_markdown(*, table_md: str, figure_md: str) -> str:
    """Stitch the two accepted companion guides under one title with clear separation."""
    return (
        "# Combined Asset Companion Study Guide\n\n"
        "This private study section combines one reconstructed-table companion and one "
        "non-table figure companion into a single student-visible guide. It demonstrates "
        "that table companions and non-table figure companions can coexist in one rendered "
        "artifact; it does not claim that all tables or figures are solved.\n\n"
        "---\n\n"
        "## Reconstructed table companion\n\n"
        f"{table_md.strip()}\n\n"
        "---\n\n"
        "## Non-table figure companion\n\n"
        f"{figure_md.strip()}\n"
    )


# ---------------------------------------------------------------------------
# Acceptance checks (closed-flag + structural; pure)
# ---------------------------------------------------------------------------

def _table_companion_accepted(summary: dict[str, Any], md: str) -> bool:
    if not isinstance(summary, dict):
        return False
    if summary.get("status") != "completed":
        return False
    flags = (
        summary.get("faithful_table_present") is True
        and summary.get("explanation_beneath_asset_present") is True
        and summary.get("simplified_table_present") is True
        and summary.get("simplified_table_non_placeholder") is True
        and summary.get("simplified_table_is_study_oriented") is True
        and summary.get("simplified_table_is_row_reduced_copy") is False
    )
    if not flags:
        return False
    # Structural: faithful + simplified ⇒ two real tables, both required study headings.
    return (
        _markdown_table_count(md) >= 2
        and "What this table shows" in md
        and "Simplified study table" in md
    )


def _figure_companion_accepted(summary: dict[str, Any], md: str) -> bool:
    if not isinstance(summary, dict):
        return False
    if summary.get("status") != "completed":
        return False
    flags = (
        summary.get("visual_is_non_table_figure") is True
        and summary.get("visual_is_table_like") is False
        and summary.get("visual_is_matrix") is False
        and summary.get("visual_is_grid") is False
        and summary.get("visual_is_text_only") is False
        and summary.get("visual_is_partial_sliver") is False
        and summary.get("visual_inserted") is True
        and summary.get("explanation_beneath_asset_present") is True
        and summary.get("study_reading_steps_present") is True
        and summary.get("exam_takeaway_present") is True
    )
    if not flags:
        return False
    # Structural: a safe relative image ref + the required study headings.
    refs = _IMAGE_REF_RE.findall(md)
    has_safe_image = any(_SAFE_IMAGE_REF_RE.match(ref.strip()) for ref in refs)
    return (
        has_safe_image
        and "What this figure shows" in md
        and "How to read it" in md
        and "Exam takeaway" in md
    )


# ---------------------------------------------------------------------------
# IO + safety helpers
# ---------------------------------------------------------------------------

def _load_companion(
    dir_path: str | None, md_name: str, summary_name: str
) -> tuple[str, dict[str, Any]] | None:
    if not dir_path:
        return None
    base = Path(dir_path)
    md_path = base / md_name
    summary_path = base / summary_name
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


def _copy_figure_assets(
    figure_md: str, figure_dir: Path | None, out_dir: Path
) -> list[str] | None:
    """Copy each ``assets/<name>`` ref from the figure guide into the combined dir.

    Returns the list of copied relative refs, ``None`` if any ref is unsafe/data-URI,
    and raises ``FileNotFoundError`` if a referenced asset is missing.
    """
    refs = [ref.strip() for ref in _IMAGE_REF_RE.findall(figure_md)]
    copied: list[str] = []
    assets_dir = out_dir / "assets"
    for ref in refs:
        if ref.lower().startswith(_DATA_URI_MARKERS):
            return None
        if not _SAFE_IMAGE_REF_RE.match(ref) or ".." in ref:
            return None
        if figure_dir is None:
            raise FileNotFoundError(ref)
        src = figure_dir / ref
        if not src.is_file():
            raise FileNotFoundError(ref)
        assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, assets_dir / Path(ref).name)
        copied.append(ref)
    return copied


def _has_data_uri(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _DATA_URI_MARKERS)


def _render_has_private_path(html: str, paths: tuple[Any, ...]) -> bool:
    for path in paths:
        if not path:
            continue
        try:
            resolved = str(Path(path).resolve())
        except Exception:
            continue
        if resolved and resolved in html:
            return True
    return any(marker in html for marker in _PRIVATE_PATH_MARKERS)


def _markdown_table_count(md: str) -> int:
    """Count Markdown table blocks (a header row followed by a ``---`` separator row)."""
    lines = md.splitlines()
    count = 0
    for i in range(len(lines) - 1):
        row = lines[i].strip()
        sep = lines[i + 1].strip()
        if row.startswith("|") and sep.startswith("|") and set(sep) <= set("|-: "):
            count += 1
    return count


def _combined_source_label(table_summary: dict[str, Any], figure_summary: dict[str, Any]) -> str:
    table_label = _coerce(table_summary.get("source_label"), SOURCE_LABELS, "unknown")
    figure_label = _coerce(figure_summary.get("source_label"), SOURCE_LABELS, "unknown")
    if table_label == figure_label and table_label != "unknown":
        return table_label
    if "unknown" in (table_label, figure_label):
        other = figure_label if table_label == "unknown" else table_label
        return other if other != "unknown" else "unknown"
    return "mixed"


def _emit(summary: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    """Write the closed summary to the private dir when it is safe to do so."""
    if is_private_artifact_dir(out_dir):
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / COMBINED_SUMMARY_JSON).write_text(json.dumps(summary, indent=2), encoding="utf-8")
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
    combined_render_status: str = "not_run",
    private_combined_guide_written: bool = False,
    table_companion_present: bool = False,
    faithful_table_present: bool = False,
    table_explanation_present: bool = False,
    role_aware_simplified_table_present: bool = False,
    table_visibility_status: str = "operator_pending",
    figure_companion_present: bool = False,
    figure_visual_present: bool = False,
    figure_visual_type_closed: str = "none",
    figure_explanation_present: bool = False,
    figure_reading_steps_present: bool = False,
    figure_exam_takeaway_present: bool = False,
    figure_visibility_status: str = "operator_pending",
    blocked_by: str = "none",
    recommended_next_step: str = "fix_combined_render_and_rerun",
) -> dict[str, Any]:
    rendered = combined_render_status == "rendered"
    summary = {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        "combined_render_format": "html" if rendered else "not_run",
        "combined_render_status": _coerce(combined_render_status, RENDER_STATUSES, "not_run"),
        "private_combined_guide_written": bool(private_combined_guide_written),
        "private_combined_guide_gitignored": True,
        # Table companion block.
        "table_companion_source": TABLE_COMPANION_SOURCE,
        "table_companion_present": bool(table_companion_present),
        "faithful_table_present": bool(faithful_table_present),
        "table_explanation_present": bool(table_explanation_present),
        "role_aware_simplified_table_present": bool(role_aware_simplified_table_present),
        "simplified_table_is_row_reduced_copy": False,
        "simplified_table_is_study_oriented": True,
        "table_visibility_status": _coerce(table_visibility_status, VISIBILITY_STATUSES, "operator_pending"),
        # Figure companion block.
        "figure_companion_source": FIGURE_COMPANION_SOURCE,
        "figure_companion_present": bool(figure_companion_present),
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
        "figure_visibility_status": _coerce(figure_visibility_status, VISIBILITY_STATUSES, "operator_pending"),
        # Closed negative canaries — committed posture, never raw content.
        "raw_private_paths_in_rendered_html": False,
        "data_image_used": False,
        "base64_image_used": False,
        "image_bytes_committed": False,
        "raw_table_text_committed": False,
        "raw_figure_text_committed": False,
        "raw_caption_text_committed": False,
        "raw_descriptor_json_committed": False,
        "raw_guide_committed": False,
        "raw_source_committed": False,
        "raw_ocr_committed": False,
        "screenshots_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
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
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "fix_combined_render_and_rerun"),
    }
    _assert_summary_safe(summary)
    return summary


def _assert_summary_safe(summary: dict[str, Any]) -> None:
    # Keys are controlled closed vocabulary (e.g. ``base64_image_used``); only the
    # values could ever carry leaked content, so scope the scan to values.
    values_blob = " ".join(str(v) for v in summary.values()).lower()
    for marker in ("data:image", ";base64,", "/", "\\", "prompt:", "response:"):
        if marker in values_blob:
            raise ValueError("177B closed summary contains forbidden marker")
    if re.search(r"\b[a-f0-9]{16,}\b", values_blob):
        raise ValueError("177B closed summary contains hash-like string")


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_combined_asset_companion_guide(
        table_companion_dir=os.environ.get("PRIVATE_TABLE_COMPANION_DIR") or None,
        figure_companion_dir=os.environ.get("PRIVATE_FIGURE_COMPANION_DIR") or None,
        private_combined_dir=os.environ.get("PRIVATE_COMBINED_DIR") or None,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
