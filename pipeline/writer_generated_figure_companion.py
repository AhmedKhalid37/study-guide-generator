"""Slice 176Y: writer-generated figure/diagram companion.

This is the figure/diagram counterpart to the writer-generated table companion:
one existing private visible-asset descriptor is selected, a writer receives only
the descriptor/context, and the writer must place a single visual token plus a
student-facing explanation beneath it. The token is then resolved to either a
safe private image reference or a recreated structured study visual, and the
result is rendered to private HTML for operator inspection.

Committed outputs are closed labels only. Raw descriptor text, reconstructed
grid content, images, source captions, prompts, responses, provider payloads,
private paths, hashes, and byte counts are structurally excluded from summaries.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.html_renderer import render_markdown  # noqa: E402
from pipeline.llm_client import MissingLLMConfigError  # noqa: E402
from pipeline.provider_config import build_provider_config  # noqa: E402
from pipeline.rendered_visible_asset_insertion_proof import _load_visible_payload  # noqa: E402
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.visible_table_figure_pilot import SOURCE_LABEL_DEFAULT  # noqa: E402

ARTIFACT_NAME = "writer_generated_figure_companion"
SLICE_LABEL = "176Y"
WRITER_TOKEN = "{{figure:study_visual}}"

STATUSES = frozenset({"completed", "degraded", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
ASSET_CATEGORIES = frozenset(
    {
        "decision_tree_diagram",
        "split_diagram",
        "flowchart",
        "graph_chart_plot",
        "architecture_diagram",
        "labeled_conceptual_diagram",
        "figure_image_crop",
        "figure",
        "diagram",
        "none",
    }
)
ASSET_KINDS = frozenset(
    {"figure_or_diagram", "graph_or_chart", "flowchart", "decision_tree_diagram", "unknown"}
)
VISUAL_MODES = frozenset({"image_asset", "recreated_non_table_diagram", "blocked"})
RENDER_FORMATS = frozenset({"html", "not_run"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
VISIBILITY_STATUSES = frozenset({"operator_pending", "visible", "not_checked", "failed"})
PROVIDER_NAMES = frozenset({"deepseek", "qwen", "local", "test_fake", "none"})
EXPLANATION_SOURCES = frozenset({"writer_generated_from_descriptor", "unavailable", "invalid"})
BLOCKED_BY = frozenset(
    {
        "none",
        "no_existing_figure_descriptor",
        "no_existing_non_table_figure_descriptor",
        "provider_unavailable",
        "writer_generation_unavailable",
        "writer_token_missing",
        "writer_token_duplicate",
        "render_failed",
        "placeholder_content_detected",
        "unsafe_private_artifact_path",
        "unsafe_asset_reference",
        "raw_image_data_refused",
    }
)
NEXT_STEPS = frozenset(
    {
        "operator_read_private_rendered_guide",
        "fix_writer_prompt_and_rerun",
        "produce_private_figure_descriptor_from_existing_extraction",
        "produce_private_non_table_figure_descriptor_from_existing_extraction",
    }
)

WriterFn = Callable[[list[dict[str, str]]], str]

_CATEGORY_PRIORITY = (
    "decision_tree_diagram",
    "split_diagram",
    "flowchart",
    "graph_chart_plot",
    "architecture_diagram",
    "labeled_conceptual_diagram",
    "figure_image_crop",
    "figure",
    "diagram",
)
_CATEGORY_ALIASES = {
    "decision_tree_or_split_diagram": "decision_tree_diagram",
    "graph": "graph_chart_plot",
    "chart": "graph_chart_plot",
    "plot": "graph_chart_plot",
    "graph_or_chart": "graph_chart_plot",
}
_EXCLUDED_VISUAL_TOKENS = (
    "table",
    "matrix",
    "grid",
    "proximity_matrix",
    "dataset table",
    "table-like visual",
    "structured table",
    "structured grid",
    "patient_dataset_table",
    "table_json",
    "table_markdown",
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
_SAFE_IMAGE_REF_RE = re.compile(r"^assets/[A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|webp)$", re.I)
_PLACEHOLDER_MARKERS = (
    "placeholder",
    "todo",
    "tbd",
    "lorem ipsum",
    "fill in",
    "your text here",
    "example explanation",
    "sample text",
    "to be written",
    "i think",
    "not sure",
    "unclear",
    "cannot determine",
    "can't determine",
    "as an ai",
    "source is unclear",
    "maybe",
    "probably",
)


def build_writer_messages(*, descriptor_text: str, visual_mode: str) -> list[dict[str, str]]:
    """Build the descriptor-only writer prompt for one figure/diagram companion."""
    system = (
        "You are an expert study-guide writer. You write finished, exam-focused "
        "student-facing explanations. Never hedge, never reveal uncertainty, never "
        "mention files or paths, and never expose reasoning or metadata."
    )
    user = (
        "Write ONE narrow study-guide section for an existing recovered visual asset. "
        "You are given only a safe extracted descriptor/context. You did not inspect "
        "the source image. Use only the descriptor; do not invent unsupported labels, "
        "numbers, relationships, or source details.\n\n"
        f"Visual insertion mode: {visual_mode}.\n\n"
        "Output Markdown that follows this contract exactly:\n"
        "1. Start with a heading for the selected figure/diagram companion.\n"
        f"2. Place the token {WRITER_TOKEN} on its own line exactly once where the "
        "visual should appear. Do not paste image data, paths, HTML, or the descriptor.\n"
        "3. Immediately beneath the token, write '## What this figure shows' followed "
        "by 3-6 teaching sentences explaining what the visual shows, how to read it, "
        "why it matters for exams, and one supported common confusion or key takeaway.\n"
        "4. Add '## How to read it' with concise study reading steps.\n"
        "5. Add '## Practice seed' with a short blank-label or self-test prompt using "
        "only supported labels/concepts from the descriptor.\n"
        "6. Do not include raw paths, provider metadata, prompt text, or private-source "
        "metadata. Do not say the source is unclear.\n\n"
        "Safe extracted visual descriptor/context:\n\n"
        f"{descriptor_text.strip()}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_writer_generated_figure_companion(
    *,
    visible_artifact_path: str | None = None,
    private_ocr_dir: str | None = None,
    private_companion_dir: str | None = None,
    visible_payload_override: dict[str, Any] | None = None,
    provider: str | None = None,
    model_choice: str = "Use environment default",
    custom_model: str | None = None,
    source_label: str = SOURCE_LABEL_DEFAULT,
    render_html: bool = True,
    writer: WriterFn | None = None,
) -> dict[str, Any]:
    """Run one descriptor-driven writer companion over an existing figure asset."""
    payload, payload_path = _load_visible_payload(
        visible_artifact_path=visible_artifact_path,
        private_ocr_dir=private_ocr_dir,
        override=visible_payload_override,
    )
    parent = Path(payload_path).parent if payload_path else Path.cwd()
    out_dir = Path(private_companion_dir) if private_companion_dir else parent / ARTIFACT_NAME
    if not isinstance(payload, dict):
        summary = _summary(
            status="blocked",
            source_label=source_label,
            blocked_by="no_existing_non_table_figure_descriptor",
            recommended_next_step="produce_private_non_table_figure_descriptor_from_existing_extraction",
        )
        _write_closed_summary_if_safe(summary, out_dir)
        return summary
    if payload_path is not None and not is_private_artifact_dir(Path(payload_path).parent):
        return _summary(
            status="blocked",
            source_label=_source_label_from_payload(payload, source_label),
            blocked_by="unsafe_private_artifact_path",
            recommended_next_step="produce_private_figure_descriptor_from_existing_extraction",
        )

    label = _source_label_from_payload(payload, source_label)
    asset = select_figure_asset_payload(payload)
    if asset is None:
        summary = _summary(
            status="blocked",
            source_label=label,
            blocked_by="no_existing_non_table_figure_descriptor",
            recommended_next_step="produce_private_non_table_figure_descriptor_from_existing_extraction",
            table_like_visual_companion_status="completed_but_not_counted_for_figure_gate"
            if _has_table_like_candidate(payload)
            else "not_applicable",
        )
        _write_closed_summary_if_safe(summary, out_dir)
        return summary

    category = _asset_category(asset)
    kind = _asset_kind(asset, category)
    visual_flags = _visual_shape_flags(asset)
    if _contains_raw_image_data(asset):
        return _summary(
            status="blocked",
            source_label=label,
            selected_asset_category=category,
            selected_asset_kind=kind,
            **visual_flags,
            writer_input_descriptor_present=True,
            blocked_by="raw_image_data_refused",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )

    visual_mode = "blocked"
    visual_markdown = ""
    image_ref = _safe_image_ref(asset)
    if image_ref:
        visual_mode = "image_asset"
        visual_markdown = f"![Recreated study visual]({image_ref})"
    elif _has_non_table_diagram_structure(asset):
        visual_mode = "recreated_non_table_diagram"
        visual_markdown = build_recreated_non_table_diagram_markdown(asset)
    elif _has_unsafe_image_ref(asset):
        return _summary(
            status="blocked",
            source_label=label,
            selected_asset_category=category,
            selected_asset_kind=kind,
            **visual_flags,
            writer_input_descriptor_present=True,
            blocked_by="unsafe_asset_reference",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )
    else:
        summary = _summary(
            status="blocked",
            source_label=label,
            selected_asset_category=category,
            selected_asset_kind=kind,
            **visual_flags,
            blocked_by="no_existing_non_table_figure_descriptor",
            recommended_next_step="produce_private_non_table_figure_descriptor_from_existing_extraction",
        )
        _write_closed_summary_if_safe(summary, out_dir)
        return summary

    if not is_private_artifact_dir(out_dir):
        return _summary(
            status="blocked",
            source_label=label,
            selected_asset_category=category,
            selected_asset_kind=kind,
            **visual_flags,
            writer_input_descriptor_present=True,
            visual_insertion_mode=visual_mode,
            blocked_by="unsafe_private_artifact_path",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )

    descriptor_text = build_descriptor_text(asset)
    messages = build_writer_messages(descriptor_text=descriptor_text, visual_mode=visual_mode)

    provider_name = "none"
    model_name = "none"
    try:
        if writer is None:
            resolved_provider = provider or _resolve_default_provider()
            config = build_provider_config(resolved_provider, model_choice, custom_model)
            provider_name = config.provider
            model_name = config.model
            from pipeline.llm_client import generate_chat_completion

            response = generate_chat_completion(messages, config)
        else:
            provider_name = "test_fake"
            model_name = "test_fake"
            response = writer(messages)
    except MissingLLMConfigError:
        return _summary(
            status="blocked",
            source_label=label,
            selected_asset_category=category,
            selected_asset_kind=kind,
            **visual_flags,
            visual_insertion_mode=visual_mode,
            writer_input_descriptor_present=True,
            provider_name_closed=_coerce(provider_name, PROVIDER_NAMES, "none"),
            blocked_by="provider_unavailable",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )
    except Exception:
        return _summary(
            status="blocked",
            source_label=label,
            selected_asset_category=category,
            selected_asset_kind=kind,
            **visual_flags,
            visual_insertion_mode=visual_mode,
            writer_input_descriptor_present=True,
            provider_name_closed=_coerce(provider_name, PROVIDER_NAMES, "none"),
            model_name_closed=model_name,
            blocked_by="writer_generation_unavailable",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )

    parsed = parse_writer_output(response)
    common = dict(
        source_label=label,
        selected_asset_category=category,
        selected_asset_kind=kind,
        **visual_flags,
        visual_insertion_mode=visual_mode,
        writer_input_descriptor_present=True,
        provider_call_made=True,
        provider_name_closed=_coerce(provider_name, PROVIDER_NAMES, "none"),
        model_name_closed=model_name,
        generation_rerun=True,
    )
    if parsed["token_count"] == 0:
        return _summary(
            status="blocked",
            **common,
            blocked_by="writer_token_missing",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )
    if parsed["token_count"] > 1:
        return _summary(
            status="blocked",
            **common,
            generation_behavior_changed=True,
            blocked_by="writer_token_duplicate",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )

    common["generation_behavior_changed"] = True
    if not parsed["explanation_real"]:
        return _summary(
            status="blocked",
            **common,
            explanation_beneath_asset_present=parsed["explanation_present"],
            explanation_source="writer_generated_from_descriptor"
            if parsed["explanation_present"]
            else "unavailable",
            explanation_non_placeholder=False,
            study_reading_steps_present=parsed["study_reading_steps_present"],
            blank_label_practice_seed_present=parsed["blank_label_practice_seed_present"],
            blocked_by="placeholder_content_detected",
            recommended_next_step="fix_writer_prompt_and_rerun",
        )

    final_markdown = response.replace(WRITER_TOKEN, "\n\n" + visual_markdown.strip() + "\n\n", 1)
    render_format = "not_run"
    render_status = "not_run"
    rendered_written = False
    visual_visibility = "not_checked"
    explanation_visibility = "not_checked"
    status = "degraded"
    blocker = "render_failed"
    next_step = "fix_writer_prompt_and_rerun"

    if render_html:
        try:
            html = render_markdown(final_markdown, title="Writer Figure Companion Guide", strict_math=False)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "writer_generated_figure_companion_guide.md").write_text(
                final_markdown, encoding="utf-8"
            )
            html_path = out_dir / "writer_generated_figure_companion_guide.html"
            html_path.write_text(html, encoding="utf-8")
            rendered_written = html_path.is_file()
            render_format = "html"
            render_status = "rendered"
            token_absent = WRITER_TOKEN not in html
            explanation_rendered = "What this figure shows" in html
            if visual_mode == "image_asset":
                visual_rendered = "<img" in html and "data:image" not in html and "assets/" in html
            else:
                visual_rendered = "Recreated non-table study diagram" in html and "<table" not in html
            if token_absent and visual_rendered and explanation_rendered:
                status = "completed"
                blocker = "none"
                next_step = "operator_read_private_rendered_guide"
                visual_visibility = "operator_pending"
                explanation_visibility = "operator_pending"
            else:
                visual_visibility = "failed"
                explanation_visibility = "operator_pending" if explanation_rendered else "failed"
        except Exception:
            render_status = "failed"

    summary = _summary(
        status=status,
        **common,
        visual_inserted=status == "completed",
        visual_render_status="operator_pending" if status == "completed" else "failed",
        explanation_beneath_asset_present=True,
        explanation_source="writer_generated_from_descriptor",
        explanation_non_placeholder=True,
        study_reading_steps_present=parsed["study_reading_steps_present"],
        blank_label_practice_seed_present=parsed["blank_label_practice_seed_present"],
        render_format=render_format,
        render_status=render_status,
        private_rendered_guide_written=rendered_written,
        private_rendered_guide_gitignored=is_private_artifact_dir(out_dir),
        visual_visibility_status=visual_visibility,
        explanation_visibility_status=explanation_visibility,
        blocked_by=blocker,
        recommended_next_step=next_step,
    )
    if render_status == "rendered":
        _write_closed_summary_if_safe(summary, out_dir)
    return summary


def select_figure_asset_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        return None
    by_category: dict[str, dict[str, Any]] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if _is_table_like_asset(asset):
            continue
        category = _asset_category(asset)
        kind = _asset_kind(asset, category)
        if not (_safe_image_ref(asset) or _has_unsafe_image_ref(asset) or _has_non_table_diagram_structure(asset)):
            continue
        if category in _CATEGORY_PRIORITY or kind in {"figure_or_diagram", "graph_or_chart", "flowchart", "decision_tree_diagram"}:
            by_category.setdefault(category, asset)
    for category in _CATEGORY_PRIORITY:
        if category in by_category:
            return by_category[category]
    return next(iter(by_category.values()), None)


def build_descriptor_text(asset: dict[str, Any]) -> str:
    """Build the private descriptor text sent to the writer."""
    category = _asset_category(asset)
    kind = _asset_kind(asset, category)
    lines = [
        f"asset_category: {category}",
        f"asset_kind: {kind}",
        "asset_role: study_visual",
        f"display_role: {asset.get('display_role') or 'explanation_support'}",
    ]
    structure = _non_table_diagram_structure(asset)
    if structure:
        lines.append("non_table_visual_structure:")
        for key, value in structure.items():
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=True)}")
    descriptor = asset.get("descriptor_text")
    if isinstance(descriptor, str) and descriptor.strip():
        lines.append("descriptor_context:")
        lines.append(descriptor.strip())
    return "\n".join(lines)


def build_recreated_non_table_diagram_markdown(asset: dict[str, Any]) -> str:
    structure = _non_table_diagram_structure(asset)
    parts = ["**Recreated non-table study diagram from recovered descriptor**"]
    nodes = structure.get("nodes") or structure.get("diagram_nodes") or structure.get("concept_labels") or []
    edges = structure.get("edges") or structure.get("diagram_edges") or []
    steps = structure.get("flow_steps") or structure.get("flowchart_steps") or []
    series = structure.get("chart_series") or structure.get("plot_series") or structure.get("graph_points") or []
    if isinstance(nodes, list) and nodes:
        parts.append("Nodes: " + " -> ".join(_closed_label(item) for item in nodes[:8]))
    if isinstance(edges, list) and edges:
        rendered_edges = []
        for edge in edges[:8]:
            if isinstance(edge, dict):
                left = _closed_label(edge.get("from") or edge.get("source") or edge.get("start"))
                right = _closed_label(edge.get("to") or edge.get("target") or edge.get("end"))
                label = _closed_label(edge.get("label"))
                rendered_edges.append(f"{left} -> {right}" + (f" ({label})" if label else ""))
            elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
                rendered_edges.append(f"{_closed_label(edge[0])} -> {_closed_label(edge[1])}")
        if rendered_edges:
            parts.append("Connections:\n" + "\n".join(f"- {item}" for item in rendered_edges))
    if isinstance(steps, list) and steps:
        parts.append("Flow:\n" + "\n".join(f"{index}. {_closed_label(step)}" for index, step in enumerate(steps[:8], 1)))
    if isinstance(series, list) and series:
        parts.append("Graph/chart series present: " + str(min(len(series), 8)))
    return "\n\n".join(parts)


def parse_writer_output(response: Any) -> dict[str, Any]:
    text = response if isinstance(response, str) else ""
    count = text.count(WRITER_TOKEN)
    after = text.split(WRITER_TOKEN, 1)[1] if count >= 1 else text
    explanation_present = bool(_strip_markdown_noise(after).strip())
    return {
        "token_count": count,
        "explanation_present": explanation_present,
        "explanation_real": explanation_present and not is_placeholder_text(after),
        "study_reading_steps_present": _has_reading_steps(after),
        "blank_label_practice_seed_present": _has_practice_seed(after),
    }


def is_placeholder_text(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return True
    text = value.lower()
    if any(marker in text for marker in _PLACEHOLDER_MARKERS):
        return True
    words = re.findall(r"[A-Za-z0-9]+", value)
    return len(words) < 25


def _summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    selected_asset_category: str = "none",
    selected_asset_kind: str = "unknown",
    selected_asset_role: str = "study_visual",
    asset_descriptor_source: str = "private_visible_asset_inventory",
    writer_input_descriptor_present: bool = False,
    provider_call_made: bool = False,
    provider_name_closed: str = "none",
    model_name_closed: str = "none",
    generation_rerun: bool = False,
    generation_behavior_changed: bool = False,
    visual_inserted: bool = False,
    visual_insertion_mode: str = "blocked",
    visual_is_table_like: bool = False,
    visual_is_matrix: bool = False,
    visual_is_grid: bool = False,
    visual_inserted_as_raw_private_path: bool = False,
    visual_render_status: str = "not_checked",
    explanation_beneath_asset_present: bool = False,
    explanation_source: str = "unavailable",
    explanation_non_placeholder: bool = False,
    study_reading_steps_present: bool = False,
    blank_label_practice_seed_present: bool = False,
    render_format: str = "not_run",
    render_status: str = "not_run",
    private_rendered_guide_written: bool = False,
    private_rendered_guide_gitignored: bool = False,
    private_run_closed_summary_written: bool = False,
    visual_visibility_status: str = "not_checked",
    explanation_visibility_status: str = "not_checked",
    figure_diagram_companion_status: str = "not_produced",
    table_like_visual_companion_status: str = "not_applicable",
    blocked_by: str = "none",
    recommended_next_step: str = "fix_writer_prompt_and_rerun",
) -> dict[str, Any]:
    completed = status == "completed"
    return {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        "selected_asset_category": _coerce(selected_asset_category, ASSET_CATEGORIES, "none"),
        "selected_asset_kind": _coerce(selected_asset_kind, ASSET_KINDS, "unknown"),
        "selected_asset_role": selected_asset_role if selected_asset_role == "study_visual" else "study_visual",
        "asset_descriptor_source": asset_descriptor_source,
        "writer_input_descriptor_present": bool(writer_input_descriptor_present),
        "writer_saw_image": False,
        "provider_call_made": bool(provider_call_made),
        "provider_name_closed": _coerce(provider_name_closed, PROVIDER_NAMES, "none"),
        "model_name_closed_or_redacted": _safe_model_name(model_name_closed),
        "generation_rerun": bool(generation_rerun),
        "generation_behavior_changed": bool(generation_behavior_changed),
        "visual_inserted": bool(visual_inserted),
        "visual_insertion_mode": _coerce(visual_insertion_mode, VISUAL_MODES, "blocked"),
        "visual_is_table_like": bool(visual_is_table_like),
        "visual_is_matrix": bool(visual_is_matrix),
        "visual_is_grid": bool(visual_is_grid),
        "visual_inserted_as_raw_private_path": bool(visual_inserted_as_raw_private_path),
        "visual_render_status": _coerce(visual_render_status, VISIBILITY_STATUSES, "not_checked"),
        "explanation_beneath_asset_present": bool(explanation_beneath_asset_present),
        "explanation_source": _coerce(explanation_source, EXPLANATION_SOURCES, "unavailable"),
        "explanation_non_placeholder": bool(explanation_non_placeholder),
        "study_reading_steps_present": bool(study_reading_steps_present),
        "blank_label_practice_seed_present": bool(blank_label_practice_seed_present),
        "render_format": _coerce(render_format, RENDER_FORMATS, "not_run"),
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        "private_rendered_guide_written": bool(private_rendered_guide_written),
        "private_rendered_guide_gitignored": bool(private_rendered_guide_gitignored),
        "private_run_closed_summary_written": bool(private_run_closed_summary_written),
        "visual_visibility_status": _coerce(visual_visibility_status, VISIBILITY_STATUSES, "not_checked"),
        "explanation_visibility_status": _coerce(
            explanation_visibility_status, VISIBILITY_STATUSES, "not_checked"
        ),
        "figure_diagram_companion_status": (
            "produced" if completed else _closed_companion_status(figure_diagram_companion_status)
        ),
        "table_like_visual_companion_status": _closed_table_like_status(table_like_visual_companion_status),
        "operator_private_read_required": completed,
        "operator_private_read_done": False,
        "raw_figure_text_committed": False,
        "raw_caption_text_committed": False,
        "raw_descriptor_json_committed": False,
        "raw_guide_committed": False,
        "raw_source_committed": False,
        "raw_ocr_committed": False,
        "image_bytes_committed": False,
        "screenshots_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        "cloud_ocr_used": False,
        "ocr_rerun": False,
        "coverage_eval_rerun": False,
        "numeric_verification_claimed": False,
        "frontend_api_changed": False,
        "judge_ready": False,
        "repair_ready": False,
        "postprocessor_explanation_injected": False,
        "blocked_by": _coerce(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "fix_writer_prompt_and_rerun"),
    }


def _write_closed_summary_if_safe(summary: dict[str, Any], out_dir: Path) -> None:
    if not is_private_artifact_dir(out_dir):
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    summary["private_run_closed_summary_written"] = True
    (out_dir / "closed_writer_generated_figure_companion_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def _is_table_like_asset(asset: dict[str, Any]) -> bool:
    if isinstance(asset.get("table_json"), list) and asset.get("table_json"):
        return True
    if isinstance(asset.get("table_markdown"), list) and asset.get("table_markdown"):
        return True
    if isinstance(asset.get("table_markdown"), str) and asset.get("table_markdown").strip():
        return True
    text = _asset_closed_text(asset)
    return any(token in text for token in _EXCLUDED_VISUAL_TOKENS)


def _visual_shape_flags(asset: dict[str, Any]) -> dict[str, bool]:
    text = _asset_closed_text(asset)
    has_grid_payload = isinstance(asset.get("table_json"), list) and bool(asset.get("table_json"))
    return {
        "visual_is_table_like": _is_table_like_asset(asset),
        "visual_is_matrix": "matrix" in text or "proximity_matrix" in text,
        "visual_is_grid": has_grid_payload or "grid" in text or "structured grid" in text,
    }


def _has_table_like_candidate(payload: dict[str, Any]) -> bool:
    assets = payload.get("assets") if isinstance(payload, dict) else None
    return isinstance(assets, list) and any(isinstance(asset, dict) and _is_table_like_asset(asset) for asset in assets)


def _asset_closed_text(asset: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "asset_category",
        "asset_kind",
        "asset_type",
        "visual_type",
        "display_role",
        "placement_hint",
        "normalized_context",
    ):
        value = asset.get(key)
        if isinstance(value, str):
            values.append(value)
    return " ".join(values).strip().lower().replace("-", "_")


def _non_table_diagram_structure(asset: dict[str, Any]) -> dict[str, Any]:
    structure: dict[str, Any] = {}
    for key in _NON_TABLE_STRUCTURE_KEYS:
        value = asset.get(key)
        if isinstance(value, list) and value:
            structure[key] = value
    return structure


def _has_non_table_diagram_structure(asset: dict[str, Any]) -> bool:
    return bool(_non_table_diagram_structure(asset)) and not _is_table_like_asset(asset)


def _closed_label(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("label", "name", "id", "text"):
            if key in value:
                return _closed_label(value[key])
        return "node"
    text = str(value).strip()
    text = re.sub(r"[\r\n|<>]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:80]


def _closed_companion_status(value: str) -> str:
    return value if value in {"produced", "not_produced"} else "not_produced"


def _closed_table_like_status(value: str) -> str:
    allowed = {"not_applicable", "completed_but_not_counted_for_figure_gate"}
    return value if value in allowed else "not_applicable"


def _safe_image_ref(asset: dict[str, Any]) -> str | None:
    for key in ("image_asset_ref", "asset_ref", "safe_image_ref"):
        value = asset.get(key)
        if isinstance(value, str) and _SAFE_IMAGE_REF_RE.match(value) and ".." not in value:
            return value
    return None


def _has_unsafe_image_ref(asset: dict[str, Any]) -> bool:
    for key in ("image_asset_ref", "asset_ref", "safe_image_ref"):
        value = asset.get(key)
        if isinstance(value, str) and value and _safe_image_ref(asset) is None:
            return True
    return False


def _contains_raw_image_data(asset: dict[str, Any]) -> bool:
    for key in ("image_data", "image_base64", "base64", "data_uri"):
        value = asset.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return any(
        isinstance(value, str) and value.strip().lower().startswith("data:image")
        for value in asset.values()
    )


def _has_structured_visual(asset: dict[str, Any]) -> bool:
    return bool(_asset_grids(asset)) or any(
        isinstance(value, str) and value.strip() for value in asset.get("table_markdown", [])
    )


def _strip_markdown_noise(value: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", value)
    text = re.sub(r"\|[^\n]+\|", " ", text)
    return re.sub(r"#+", " ", text)


def _has_reading_steps(value: str) -> bool:
    text = value.lower()
    return "how to read" in text or "reading steps" in text or bool(re.search(r"\n\s*(?:1\.|-)\s+", value))


def _has_practice_seed(value: str) -> bool:
    text = value.lower()
    return "practice seed" in text or "blank-label" in text or "self-test" in text or "label" in text


def _asset_category(asset: dict[str, Any]) -> str:
    raw = asset.get("asset_category") if isinstance(asset, dict) else None
    if isinstance(raw, str):
        raw = raw.strip().lower().replace("-", "_")
        raw = _CATEGORY_ALIASES.get(raw, raw)
    kind = asset.get("asset_kind") or asset.get("asset_type") or asset.get("visual_type")
    if raw == "none" and isinstance(kind, str):
        lowered = kind.strip().lower().replace("-", "_")
        if lowered in {"flowchart", "graph_or_chart", "chart", "plot", "diagram", "figure"}:
            raw = _CATEGORY_ALIASES.get(lowered, lowered)
    return _coerce(raw, ASSET_CATEGORIES, "none")


def _asset_kind(asset: dict[str, Any], category: str) -> str:
    raw = asset.get("asset_kind") or asset.get("asset_type") or asset.get("visual_type")
    if isinstance(raw, str):
        lowered = raw.strip().lower().replace("-", "_")
        aliases = {
            "figure": "figure_or_diagram",
            "diagram": "figure_or_diagram",
            "figure_or_diagram": "figure_or_diagram",
            "graph": "graph_or_chart",
            "chart": "graph_or_chart",
            "plot": "graph_or_chart",
            "graph_or_chart": "graph_or_chart",
            "flowchart": "flowchart",
            "decision_tree": "decision_tree_diagram",
            "decision_tree_diagram": "decision_tree_diagram",
        }
        coerced = aliases.get(lowered, lowered)
        if coerced in ASSET_KINDS:
            return coerced
    if category == "decision_tree_diagram":
        return "decision_tree_diagram"
    if category == "flowchart":
        return "flowchart"
    if category == "graph_chart_plot":
        return "graph_or_chart"
    if category in {"split_diagram", "architecture_diagram", "labeled_conceptual_diagram", "figure_image_crop", "figure", "diagram"}:
        return "figure_or_diagram"
    return "unknown"


def _source_label_from_payload(payload: dict[str, Any], fallback: str) -> str:
    raw = payload.get("source_label") if isinstance(payload, dict) else fallback
    return _coerce(raw, SOURCE_LABELS, "unknown")


def _resolve_default_provider() -> str:
    try:
        from pipeline import provider_settings_store

        default = provider_settings_store.get_default_provider()
        if default:
            return default
    except Exception:
        pass
    return os.environ.get("WRITER_PROVIDER", "deepseek")


def _safe_model_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "none"
    name = value.strip()
    if "/" in name or "\\" in name or len(name) > 64:
        return "redacted"
    return name


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_writer_generated_figure_companion(
        visible_artifact_path=os.environ.get("PRIVATE_VISIBLE_ARTIFACT"),
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR"),
        private_companion_dir=os.environ.get("PRIVATE_COMPANION_DIR"),
        provider=os.environ.get("WRITER_PROVIDER") or None,
        model_choice=os.environ.get("WRITER_MODEL_CHOICE", "Use environment default"),
        custom_model=os.environ.get("WRITER_CUSTOM_MODEL") or None,
        source_label=os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT),
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
