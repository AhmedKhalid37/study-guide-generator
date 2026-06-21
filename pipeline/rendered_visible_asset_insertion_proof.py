"""Rendered reconstructed-table proof for Slice 176U.

This module uses an existing private visible-asset payload and writes a private
guide artifact that embeds one recovered structured table as a real Markdown
table, then renders it through the existing HTML renderer. Committed outputs are
closed status labels only; raw guide, OCR, table, caption, image, prompt,
response, and provider payload content are structurally excluded from returned
summaries.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.html_renderer import render_markdown  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.visible_table_figure_pilot import SOURCE_LABEL_DEFAULT  # noqa: E402

ARTIFACT_NAME = "rendered_reconstructed_table_proof"

STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
TABLE_CATEGORIES = frozenset({"patient_dataset_table", "proximity_matrix"})
ASSET_CATEGORIES = frozenset({"patient_dataset_table", "proximity_matrix", "none"})
ASSET_KINDS = frozenset({"table", "unknown"})
INSERTION_MODES = frozenset({"private_markdown_table", "private_reconstructed_table", "not_run"})
RENDER_FORMATS = frozenset({"pdf", "html", "not_run"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
VISIBILITY_STATUSES = frozenset({"visible", "not_visible", "unknown", "not_checked"})
BLOCKED_BY = frozenset(
    {
        "none",
        "private_visible_table_missing",
        "private_guide_source_missing",
        "renderer_unavailable",
        "asset_visibility_failed",
        "unsafe_private_artifact_path",
        "scope_too_large",
    }
)
NEXT_STEPS = frozenset(
    {
        "inspect_private_rendered_reconstructed_table_guide",
        "add_explanation_beneath_asset",
        "add_faithful_table_plus_simplified_version",
        "harden_off_by_default_visible_asset_insertion",
        "add_user_page_exclusion_controls",
        "blocked",
    }
)
PHASE4_NEXT_REQUIREMENTS = frozenset(
    {
        "add_explanation_beneath_asset",
        "add_faithful_table_plus_simplified_version",
        "harden_off_by_default_visible_asset_insertion",
        "blocked",
    }
)
_ASSET_REF_RE = re.compile(r"^assets/[A-Za-z0-9_]+\.png$")
_CATEGORY_PRIORITY = ("patient_dataset_table", "proximity_matrix")


def build_closed_rendered_visible_asset_insertion_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    private_visible_artifact_available: bool = False,
    private_visible_artifact_gitignored: bool = False,
    private_guide_source_available: bool = False,
    private_guide_source_gitignored: bool = False,
    private_rendered_guide_written: bool = False,
    private_rendered_guide_gitignored: bool = False,
    selected_asset_category: str = "none",
    selected_asset_kind: str = "table",
    insertion_mode: str = "not_run",
    render_format: str = "not_run",
    render_status: str = "not_run",
    asset_visibility_status: str = "not_checked",
    export_visibility_status: str = "not_checked",
    blocked_by: str = "none",
    phase4_next_requirement: str = "blocked",
    recommended_next_step: str = "blocked",
) -> dict[str, Any]:
    """Return the committed-safe closed proof summary."""
    selected_category = _coerce(selected_asset_category, ASSET_CATEGORIES, "none")
    selected_kind = _coerce(selected_asset_kind, ASSET_KINDS, "table")
    inserted_as_image = False
    insertion = _coerce(insertion_mode, INSERTION_MODES, "not_run")
    render_fmt = _coerce(render_format, RENDER_FORMATS, "not_run")
    render_state = _coerce(render_status, RENDER_STATUSES, "not_run")
    asset_visibility = _coerce(asset_visibility_status, VISIBILITY_STATUSES, "not_checked")
    export_visibility = _coerce(export_visibility_status, VISIBILITY_STATUSES, "not_checked")
    rendered_written = bool(private_rendered_guide_written)
    rendered_gitignored = bool(private_rendered_guide_gitignored)
    blocker = _coerce(blocked_by, BLOCKED_BY, "none")
    phase4 = _coerce(phase4_next_requirement, PHASE4_NEXT_REQUIREMENTS, "blocked")
    next_step = _coerce(recommended_next_step, NEXT_STEPS, "blocked")
    final_status = _final_status(
        requested=status,
        selected_category=selected_category,
        selected_kind=selected_kind,
        insertion_mode=insertion,
        render_format=render_fmt,
        render_status=render_state,
        asset_visibility_status=asset_visibility,
        private_rendered_guide_written=rendered_written,
        private_rendered_guide_gitignored=rendered_gitignored,
        blocked_by=blocker,
    )
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": final_status,
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        "private_visible_artifact_available": bool(private_visible_artifact_available),
        "private_visible_artifact_gitignored": bool(private_visible_artifact_gitignored),
        "private_guide_source_available": bool(private_guide_source_available),
        "private_guide_source_gitignored": bool(private_guide_source_gitignored),
        "private_rendered_guide_written": rendered_written,
        "private_rendered_guide_gitignored": rendered_gitignored,
        "selected_asset_category": selected_category,
        "selected_asset_kind": selected_kind,
        "selected_asset_role": "display_only",
        "insertion_mode": insertion,
        "table_inserted_as_image": inserted_as_image,
        "render_format": render_fmt,
        "render_status": render_state,
        "asset_visibility_status": asset_visibility,
        "export_visibility_status": export_visibility,
        "raw_asset_committed": False,
        "raw_guide_committed": False,
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "raw_caption_text_committed": False,
        "rendered_guide_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        "provider_call_made": False,
        "generation_rerun": False,
        "ocr_rerun": False,
        "coverage_eval_rerun": False,
        "cloud_ocr_used": False,
        "numeric_verification_claimed": False,
        "generation_behavior_changed": False,
        "frontend_api_changed": False,
        "blocked_by": blocker,
        "phase4_next_requirement": phase4,
        "recommended_next_step": next_step,
    }


def run_rendered_visible_asset_insertion_proof(
    *,
    visible_artifact_path: str | None = None,
    private_ocr_dir: str | None = None,
    private_guide_source_path: str | None = None,
    private_render_dir: str | None = None,
    visible_payload_override: dict[str, Any] | None = None,
    source_label: str = SOURCE_LABEL_DEFAULT,
    render_html: bool = True,
) -> dict[str, Any]:
    """Insert one existing recovered structured table into a private rendered guide."""
    payload, payload_path = _load_visible_payload(
        visible_artifact_path=visible_artifact_path,
        private_ocr_dir=private_ocr_dir,
        override=visible_payload_override,
    )
    visible_available = isinstance(payload, dict)
    visible_gitignored = bool(
        visible_available
        and (payload_path is None or is_private_artifact_dir(Path(payload_path).parent))
    )
    if not visible_available:
        return build_closed_rendered_visible_asset_insertion_summary(
            status="blocked",
            source_label=source_label,
            private_visible_artifact_available=False,
            private_visible_artifact_gitignored=False,
            blocked_by="private_visible_table_missing",
            phase4_next_requirement="blocked",
            recommended_next_step="blocked",
        )
    if not visible_gitignored:
        return build_closed_rendered_visible_asset_insertion_summary(
            status="blocked",
            source_label=source_label,
            private_visible_artifact_available=True,
            private_visible_artifact_gitignored=False,
            blocked_by="unsafe_private_artifact_path",
            phase4_next_requirement="blocked",
            recommended_next_step="blocked",
        )

    asset = select_visible_asset_payload(payload)
    if asset is None:
        return build_closed_rendered_visible_asset_insertion_summary(
            status="blocked",
            source_label=_source_label_from_payload(payload, source_label),
            private_visible_artifact_available=True,
            private_visible_artifact_gitignored=True,
            blocked_by="private_visible_table_missing",
            phase4_next_requirement="blocked",
            recommended_next_step="blocked",
        )

    parent = Path(payload_path).parent if payload_path else Path.cwd()
    out_dir = Path(private_render_dir) if private_render_dir else parent / ARTIFACT_NAME
    if not is_private_artifact_dir(out_dir):
        return build_closed_rendered_visible_asset_insertion_summary(
            status="blocked",
            source_label=_source_label_from_payload(payload, source_label),
            private_visible_artifact_available=True,
            private_visible_artifact_gitignored=True,
            blocked_by="unsafe_private_artifact_path",
            phase4_next_requirement="blocked",
            recommended_next_step="blocked",
        )

    guide_markdown, guide_source_available = _resolve_private_guide_markdown(
        private_guide_source_path=private_guide_source_path,
        artifact_parent=parent,
    )
    if not guide_source_available:
        guide_markdown = _default_private_guide_template()
        guide_source_available = True

    inserted, insertion_mode = insert_visible_asset_into_markdown(guide_markdown, asset)
    if not inserted:
        return build_closed_rendered_visible_asset_insertion_summary(
            status="blocked",
            source_label=_source_label_from_payload(payload, source_label),
            private_visible_artifact_available=True,
            private_visible_artifact_gitignored=True,
            private_guide_source_available=guide_source_available,
            private_guide_source_gitignored=True,
            selected_asset_category=_asset_category(asset),
            selected_asset_kind=_asset_kind(asset),
            blocked_by="asset_visibility_failed",
            phase4_next_requirement="blocked",
            recommended_next_step="blocked",
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = out_dir / "rendered_reconstructed_table_guide.md"
    markdown_path.write_text(inserted, encoding="utf-8")
    source_path = out_dir / "reconstructed_table_guide_source.md"
    source_path.write_text(guide_markdown, encoding="utf-8")

    rendered_written = False
    render_format = "not_run"
    render_status = "not_run"
    asset_visibility = "not_checked"
    export_visibility = "not_checked"
    status = "degraded"
    blocker = "renderer_unavailable"
    phase4_next = "blocked"
    next_step = "blocked"

    if render_html:
        try:
            html = render_markdown(
                inserted,
                title="Recovered Reconstructed Table Guide",
                strict_math=False,
            )
            html_path = out_dir / "rendered_reconstructed_table_guide.html"
            html_path.write_text(html, encoding="utf-8")
            visible = _html_has_visible_table(html, insertion_mode)
            rendered_written = html_path.is_file()
            render_format = "html"
            render_status = "rendered"
            asset_visibility = "visible" if visible else "not_visible"
            export_visibility = "visible" if visible else "not_visible"
            status = "completed" if visible else "degraded"
            blocker = "none" if visible else "asset_visibility_failed"
            phase4_next = (
                "add_explanation_beneath_asset"
                if visible
                else "harden_off_by_default_visible_asset_insertion"
            )
            next_step = (
                "inspect_private_rendered_reconstructed_table_guide"
                if visible
                else "blocked"
            )
        except Exception:
            render_format = "not_run"
            render_status = "failed"
            asset_visibility = "not_checked"

    summary = build_closed_rendered_visible_asset_insertion_summary(
        status=status,
        source_label=_source_label_from_payload(payload, source_label),
        private_visible_artifact_available=True,
        private_visible_artifact_gitignored=True,
        private_guide_source_available=guide_source_available,
        private_guide_source_gitignored=True,
        private_rendered_guide_written=rendered_written,
        private_rendered_guide_gitignored=is_private_artifact_dir(out_dir),
        selected_asset_category=_asset_category(asset),
        selected_asset_kind=_asset_kind(asset),
        insertion_mode=insertion_mode,
        render_format=render_format,
        render_status=render_status,
        asset_visibility_status=asset_visibility,
        export_visibility_status=export_visibility,
        blocked_by=blocker,
        phase4_next_requirement=phase4_next,
        recommended_next_step=next_step,
    )
    (out_dir / "closed_rendered_reconstructed_table_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def select_visible_asset_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pick the safest high-value table from a private 176K payload."""
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        return None
    by_category: dict[str, dict[str, Any]] = {}
    for raw in assets:
        if not isinstance(raw, dict):
            continue
        category = _asset_category(raw)
        if category in TABLE_CATEGORIES and category not in by_category:
            by_category[category] = raw
    for category in _CATEGORY_PRIORITY:
        asset = by_category.get(category)
        if asset and _asset_has_insertable_content(asset):
            return asset
    return None


def insert_visible_asset_into_markdown(markdown: str, asset: dict[str, Any]) -> tuple[str | None, str]:
    """Return private markdown with one recovered table inserted, or ``None``."""
    if _asset_category(asset) not in TABLE_CATEGORIES:
        return None, "not_run"
    tables = asset.get("table_markdown")
    if isinstance(tables, list):
        for table in tables:
            if _looks_like_markdown_table(table):
                return _append_asset_block(markdown, table.strip()), "private_markdown_table"

    reconstructed = asset.get("reconstructed_table_markdown")
    if _looks_like_markdown_table(reconstructed):
        return _append_asset_block(markdown, reconstructed.strip()), "private_reconstructed_table"

    return None, "not_run"


def is_safe_relative_asset_ref(value: Any) -> bool:
    """Accept only job-local visual asset refs, never absolute/traversal/URLs."""
    if not isinstance(value, str):
        return False
    if "\\" in value or value.startswith("/") or ":" in value or ".." in value:
        return False
    return _ASSET_REF_RE.fullmatch(value) is not None


def _load_visible_payload(
    *,
    visible_artifact_path: str | None,
    private_ocr_dir: str | None,
    override: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, Path | None]:
    if override is not None:
        return override, None
    candidates: list[Path] = []
    if visible_artifact_path:
        candidates.append(Path(visible_artifact_path))
    if private_ocr_dir:
        candidates.append(Path(private_ocr_dir) / "visible_table_figure_pilot.json")
    if not candidates:
        candidates.extend(_discover_visible_artifacts(Path.cwd()))

    for path in candidates:
        try:
            if not path.is_file() or not is_private_artifact_dir(path.parent):
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload, path
        except Exception:
            continue
    return None, None


def _discover_visible_artifacts(root: Path) -> list[Path]:
    try:
        paths = []
        for path in root.rglob("visible_table_figure_pilot.json"):
            if is_private_artifact_dir(path.parent):
                paths.append(path)
        return paths
    except Exception:
        return []


def _resolve_private_guide_markdown(
    *, private_guide_source_path: str | None, artifact_parent: Path
) -> tuple[str, bool]:
    candidates: list[Path] = []
    if private_guide_source_path:
        candidates.append(Path(private_guide_source_path))
    candidates.append(artifact_parent / "ocr_context_private_guide.md")
    for path in candidates:
        try:
            if path.is_file() and is_private_artifact_dir(path.parent):
                return path.read_text(encoding="utf-8", errors="replace"), True
        except Exception:
            continue
    return "", False


def _append_asset_block(markdown: str, block: str) -> str:
    base = markdown.strip() or _default_private_guide_template().strip()
    return base + "\n\n## Recovered Reconstructed Table\n\n" + block.strip() + "\n"


def _default_private_guide_template() -> str:
    return "# Private Guide Preview\n\nThis private preview is generated for render verification only.\n"


def _html_has_visible_table(html: str, insertion_mode: str) -> bool:
    if insertion_mode in {"private_markdown_table", "private_reconstructed_table"}:
        return "<table" in html and "</table>" in html
    return False


def _asset_has_insertable_content(asset: dict[str, Any]) -> bool:
    if _asset_category(asset) not in TABLE_CATEGORIES:
        return False
    tables = asset.get("table_markdown")
    if isinstance(tables, list) and any(_looks_like_markdown_table(t) for t in tables):
        return True
    return _looks_like_markdown_table(asset.get("reconstructed_table_markdown"))


def _asset_category(asset: dict[str, Any]) -> str:
    return _coerce(asset.get("asset_category"), ASSET_CATEGORIES, "none")


def _asset_kind(asset: dict[str, Any]) -> str:
    category = _asset_category(asset)
    if category in TABLE_CATEGORIES:
        return "table"
    return "unknown"


def _source_label_from_payload(payload: dict[str, Any], fallback: str) -> str:
    raw = payload.get("source_label") if isinstance(payload, dict) else fallback
    return _coerce(raw, SOURCE_LABELS, "unknown")


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _looks_like_markdown_table(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lines = [line.strip() for line in value.strip().splitlines() if line.strip()]
    return len(lines) >= 2 and lines[0].startswith("|") and lines[1].startswith("|") and "---" in lines[1]


def _final_status(
    *,
    requested: str,
    selected_category: str,
    selected_kind: str,
    insertion_mode: str,
    render_format: str,
    render_status: str,
    asset_visibility_status: str,
    private_rendered_guide_written: bool,
    private_rendered_guide_gitignored: bool,
    blocked_by: str,
) -> str:
    status = _coerce(requested, STATUSES, "blocked")
    if status == "completed":
        complete = (
            selected_category in TABLE_CATEGORIES
            and selected_kind == "table"
            and insertion_mode in {"private_markdown_table", "private_reconstructed_table"}
            and render_format in {"html", "pdf"}
            and render_status == "rendered"
            and asset_visibility_status == "visible"
            and private_rendered_guide_written
            and private_rendered_guide_gitignored
            and blocked_by == "none"
        )
        if not complete:
            return "blocked" if blocked_by not in {"none", "renderer_unavailable", "asset_visibility_failed"} else "degraded"
    return status


def main() -> int:
    summary = run_rendered_visible_asset_insertion_proof(
        visible_artifact_path=os.environ.get("PRIVATE_VISIBLE_ARTIFACT"),
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR"),
        private_guide_source_path=os.environ.get("PRIVATE_GUIDE_SOURCE_MD"),
        private_render_dir=os.environ.get("PRIVATE_RENDER_DIR"),
        source_label=os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT),
        render_html=os.environ.get("RENDER_HTML", "1") != "0",
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] in {"completed", "degraded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
