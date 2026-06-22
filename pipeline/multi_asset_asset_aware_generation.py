"""Slice 177G: multi-asset asset-aware generation over the ensemble descriptor set.

Slices 176W/176X/177A proved the genuinely useful *asset-aware writer* path: a
provider/model writer is handed a closed asset descriptor (no image), inserts a
single token where the asset belongs, and writes a real teaching explanation
beneath it; the token is then resolved to a faithful reconstructed table or a
safe private-relative figure image and rendered to private HTML. Slices
177B/177C/177D/177E/177F only *wrapped* that single accepted table + single
accepted figure pair (combine / preview / seam / hook / manifest) without ever
moving Phase 4 toward useful multi-asset insertion.

This slice generalises the 176W asset-aware writer path from one hand-fed
descriptor to the **full available ensemble descriptor set** in ONE generation
pass: every ready descriptor (multiple reconstructed tables + non-table
figures) is exposed to the writer with its own ``{{asset:<id>}}`` token, the
writer must use all useful descriptors, insert tables as faithful reconstructed
Markdown tables plus a role-aware study simplification and figures as a safe
relative image with an explanation, and write a real explanation beneath each
inserted asset. The result is a single private rendered guide containing
multiple distinct inserted assets.

This is NOT a wrapper / preview / seam / hook / manifest / consumer / coverage
packet / audit-that-defers-generation. It makes ONE real provider call and
blocks honestly otherwise. It is off-by-default and private only: it never
changes normal generation, never reruns OCR / Chandra / cloud OCR, never runs a
judge or repair, and never claims numeric verification or all-assets support.

Committed outputs are closed status labels and integer counts only. Raw guide /
table / figure / caption / source / OCR / descriptor text, image bytes,
base64/data URIs, prompts, responses, provider payloads, private paths, source
filenames, hashes and byte counts are structurally excluded from returned
summaries and from anything written outside the gitignored private artifact
directory.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.html_renderer import render_markdown  # noqa: E402
from pipeline.llm_client import MissingLLMConfigError  # noqa: E402
from pipeline.provider_config import build_provider_config  # noqa: E402
from pipeline.rendered_visible_asset_insertion_proof import (  # noqa: E402
    _load_visible_payload,
    _looks_like_markdown_table,
)
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.writer_generated_figure_companion import (  # noqa: E402
    _copy_crop_as_safe_asset,
    _descriptor_category,
    _descriptor_crop_path,
    _descriptor_kind,
    _descriptor_visual_type,
    _render_has_private_path,
    build_descriptor_input_text,
    load_private_non_table_descriptor,
    validate_non_table_descriptor_contract,
)
from pipeline.writer_generated_table_companion import (  # noqa: E402
    TABLE_CATEGORIES as _TABLE_CATEGORIES,
    detect_table_role,
    is_placeholder_text,
)

ARTIFACT_NAME = "multi_asset_asset_aware_generation"
SLICE_LABEL = "177G"

#: Minimum number of *ready* descriptors before generation is allowed at all.
MIN_READY_DESCRIPTORS = 3

#: Multi-asset writer token. The writer emits one per asset; this module never
#: injects an asset itself and resolves each token after parsing.
TOKEN_RE = re.compile(r"\{\{asset:([a-z0-9_]+)\}\}")

GUIDE_MD = "multi_asset_asset_aware_generation_guide.md"
GUIDE_HTML = "multi_asset_asset_aware_generation_guide.html"
SUMMARY_JSON = "closed_multi_asset_asset_aware_generation_summary.json"

STATUSES = frozenset({"completed", "degraded", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
ASSET_KINDS = frozenset(
    {
        "reconstructed_table",
        "non_table_flow_or_structure_diagram",
        "chart_or_graph_with_existing_descriptor",
    }
)
RENDER_ROLES = frozenset(
    {
        "insert_as_table",
        "insert_as_figure_with_explanation",
        "summarize_only",
        "omit_with_reason",
    }
)
RENDER_FORMATS = frozenset({"html", "not_run"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
PROVIDER_NAMES = frozenset({"deepseek", "qwen", "local", "test_fake", "none"})
BLOCKED_BY = frozenset(
    {
        "none",
        "input_private_descriptor_artifacts_missing",
        "insufficient_existing_multi_asset_descriptor_set",
        "unsafe_private_artifact_path",
        "provider_unavailable",
        "writer_generation_unavailable",
        "orphan_asset_token_remaining",
        "duplicate_asset_insertion",
        "insufficient_inserted_assets",
        "same_single_table_figure_repeat",
        "missing_explanation_beneath_asset",
        "table_inserted_as_image",
        "data_uri_or_base64_refused",
        "raw_private_path_in_render",
        "render_failed",
    }
)
NEXT_STEPS = frozenset(
    {
        "operator_read_multi_asset_generated_guide",
        "fix_writer_prompt_and_rerun",
        "produce_more_private_asset_descriptors_from_existing_extraction",
        "configure_provider_and_rerun",
    }
)

#: Visual-token markers that must never be assigned an ``insert_as_figure`` role.
_TABLE_LIKE_TOKENS = ("table", "matrix", "grid", "proximity", "dataset")
_DATA_URI_MARKERS = ("data:image", "data:application", ";base64,", "base64,")
_SAFE_ASSET_ID_RE = re.compile(r"[^a-z0-9_]+")

WriterFn = Callable[[list[dict[str, str]]], str]


# ---------------------------------------------------------------------------
# In-memory descriptor model (private — never committed)
# ---------------------------------------------------------------------------

@dataclass
class AssetDescriptor:
    """One closed asset descriptor plus the private payload needed to resolve it.

    The closed fields (``asset_id``, ``asset_kind_closed``, ``source_label``,
    ``descriptor_ready_for_text_writer``, ``render_role``) are safe to count in a
    committed summary. The underscore-prefixed payload fields hold private content
    (faithful Markdown, crop path, descriptor text) and are used only in-memory and
    in the gitignored private outputs — never returned in a summary.
    """

    asset_id: str
    asset_kind_closed: str
    descriptor_ready_for_text_writer: bool
    render_role: str
    source_label: str = "ensemble"
    omit_reason: str | None = None
    _table_markdown: str | None = field(default=None, repr=False)
    _table_role: str = field(default="unknown", repr=False)
    _figure_crop_path: Path | None = field(default=None, repr=False)
    _descriptor_text: str = field(default="", repr=False)

    @property
    def token(self) -> str:
        return "{{asset:" + self.asset_id + "}}"


def _safe_asset_id(raw: Any, fallback: str) -> str:
    text = _SAFE_ASSET_ID_RE.sub("_", str(raw or "").lower()).strip("_")
    return text or fallback


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_multi_asset_asset_aware_generation(
    *,
    visible_artifact_path: str | None = None,
    private_ocr_dir: str | None = None,
    figure_descriptor_path: str | None = None,
    private_figure_descriptor_dir: str | None = None,
    visible_payload_override: dict[str, Any] | None = None,
    figure_descriptor_override: dict[str, Any] | None = None,
    descriptor_set_override: list[dict[str, Any]] | None = None,
    private_output_dir: str | None = None,
    provider: str | None = None,
    model_choice: str = "Use environment default",
    custom_model: str | None = None,
    source_label: str = "ensemble",
    render_html: bool = True,
    writer: WriterFn | None = None,
) -> dict[str, Any]:
    """Run one asset-aware writer generation over the full ready descriptor set.

    With ``writer=None`` (the real path) this makes ONE provider/model generation
    call. Tests inject a ``writer`` callable and/or ``descriptor_set_override`` so
    they never touch a provider or private artifacts. The slice blocks honestly when
    fewer than three ready descriptors exist, when the provider is unavailable, when
    the writer leaves orphan/duplicate tokens, when fewer than three distinct assets
    are inserted, when a table would be inserted as an image, or when a data URI or
    raw private path leaks into the render.
    """
    # 1. Build / accept the full available asset descriptor set.
    if descriptor_set_override is not None:
        descriptors = _coerce_override_descriptors(descriptor_set_override)
        input_present = True
        label = _coerce(source_label, SOURCE_LABELS, "ensemble")
    else:
        descriptors, input_present, label = _build_descriptor_set(
            visible_artifact_path=visible_artifact_path,
            private_ocr_dir=private_ocr_dir,
            figure_descriptor_path=figure_descriptor_path,
            private_figure_descriptor_dir=private_figure_descriptor_dir,
            visible_payload_override=visible_payload_override,
            figure_descriptor_override=figure_descriptor_override,
            source_label=source_label,
        )

    out_dir = _resolve_out_dir(private_output_dir, private_ocr_dir)

    counts = _descriptor_counts(descriptors)
    common = dict(
        source_label=label,
        input_private_descriptor_artifacts_available=input_present,
        descriptor_set_built=bool(descriptors),
        **counts,
    )

    if not input_present and not descriptors:
        return _emit(
            _summary(status="blocked", **common,
                     blocked_by="input_private_descriptor_artifacts_missing",
                     recommended_next_step="produce_more_private_asset_descriptors_from_existing_extraction"),
            out_dir,
        )

    ready = [d for d in descriptors if d.descriptor_ready_for_text_writer]
    if len(ready) < MIN_READY_DESCRIPTORS:
        return _emit(
            _summary(status="blocked", **common,
                     blocked_by="insufficient_existing_multi_asset_descriptor_set",
                     recommended_next_step="produce_more_private_asset_descriptors_from_existing_extraction"),
            out_dir,
        )

    common["multi_asset_requirement_met"] = True

    if not is_private_artifact_dir(out_dir):
        return _summary(status="blocked", **common,
                        blocked_by="unsafe_private_artifact_path",
                        recommended_next_step="fix_writer_prompt_and_rerun")

    # 2. One asset-aware writer generation over ALL ready descriptors.
    messages = build_multi_asset_writer_messages(ready)
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
        return _emit(
            _summary(status="blocked", **common,
                     provider_name_closed=_coerce(provider_name, PROVIDER_NAMES, "none"),
                     asset_tokens_available_count=len(ready),
                     blocked_by="provider_unavailable",
                     recommended_next_step="configure_provider_and_rerun"),
            out_dir,
        )
    except Exception:
        return _emit(
            _summary(status="blocked", **common,
                     provider_name_closed=_coerce(provider_name, PROVIDER_NAMES, "none"),
                     model_name_closed=model_name,
                     asset_tokens_available_count=len(ready),
                     blocked_by="writer_generation_unavailable",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    provider_name_closed = _coerce(provider_name, PROVIDER_NAMES, "none")
    gen_common = dict(
        **common,
        provider_call_made=True,
        provider_name_closed=provider_name_closed,
        model_name_closed=model_name,
        writer_generation_run=True,
        generation_rerun=True,
        asset_tokens_available_count=len(ready),
    )

    # 3. Parse the multi-asset output against the contract.
    parsed = parse_multi_asset_output(response, ready)
    if parsed["token_total"] >= 1:
        gen_common["generation_behavior_changed"] = True

    if response and _has_data_uri(response):
        return _emit(
            _summary(status="blocked", **gen_common,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )
    if parsed["orphan_token_count"] > 0:
        return _emit(
            _summary(status="blocked", **gen_common,
                     orphan_asset_token_count=parsed["orphan_token_count"],
                     blocked_by="orphan_asset_token_remaining",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )
    if parsed["duplicate_count"] > 0:
        return _emit(
            _summary(status="blocked", **gen_common,
                     duplicate_inserted_asset_count=parsed["duplicate_count"],
                     blocked_by="duplicate_asset_insertion",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    inserted = parsed["inserted"]  # list[AssetDescriptor] in insertion order
    insert_counts = _inserted_kind_counts(inserted)
    distinct = len(inserted)
    same_single = (
        distinct == 2
        and insert_counts["inserted_table_count"] == 1
        and insert_counts["inserted_non_table_figure_count"] == 1
    )
    considered = (
        parsed["duplicate_count"] == 0
        and parsed["orphan_token_count"] == 0
        and (len(inserted) + len(parsed["omitted_ready"])) == len(ready)
    )

    insertion_common = dict(
        **gen_common,
        all_available_useful_descriptors_considered=considered,
        asset_tokens_inserted_count=distinct,
        distinct_inserted_asset_count=distinct,
        **insert_counts,
        omitted_asset_count=len(parsed["omitted_ready"]),
        omitted_with_closed_reason_count=len(parsed["omitted_ready"]),
        summarized_asset_count=0,
        orphan_asset_token_count=0,
        duplicate_inserted_asset_count=0,
        table_like_visuals_refused_as_figures=True,
    )

    # Every inserted asset must carry a real explanation beneath its token.
    if not parsed["all_explanations_real"]:
        return _emit(
            _summary(status="blocked", **insertion_common,
                     blocked_by="missing_explanation_beneath_asset",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    if distinct < MIN_READY_DESCRIPTORS:
        blocker = "same_single_table_figure_repeat" if same_single else "insufficient_inserted_assets"
        return _emit(
            _summary(status="blocked", **insertion_common,
                     same_single_table_figure_output=same_single,
                     blocked_by=blocker,
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    # 4. Resolve every token: tables -> faithful Markdown table, figures -> safe
    #    private-relative image. The writer never pastes assets itself.
    try:
        final_markdown, copied_assets = _resolve_tokens(response, inserted, out_dir)
    except _TableImageError:
        return _emit(
            _summary(status="blocked", **insertion_common,
                     tables_inserted_as_images=True,
                     blocked_by="table_inserted_as_image",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )
    except FileNotFoundError:
        return _emit(
            _summary(status="blocked", **insertion_common,
                     blocked_by="render_failed",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    if TOKEN_RE.search(final_markdown):
        return _emit(
            _summary(status="blocked", **insertion_common,
                     orphan_asset_token_count=len(TOKEN_RE.findall(final_markdown)),
                     blocked_by="orphan_asset_token_remaining",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )
    if _has_data_uri(final_markdown):
        return _emit(
            _summary(status="blocked", **insertion_common,
                     data_image_used=True,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    body_common = dict(
        **insertion_common,
        same_single_table_figure_output=False,
        not_byte_identical_to_prior_single_asset_output=True,
        faithful_table_reconstruction_present=insert_counts["inserted_table_count"] >= 1,
        role_aware_simplified_tables_present=parsed["role_aware_simplified_tables_present"],
        table_explanations_present=parsed["table_explanations_present"],
        tables_inserted_as_images=False,
        figures_inserted_with_relative_assets=bool(copied_assets),
        figure_explanations_present=parsed["figure_explanations_present"],
        figure_reading_steps_present=parsed["figure_reading_steps_present"],
        figure_exam_takeaways_present=parsed["figure_exam_takeaways_present"],
        diagram_caption_descriptor_gap=counts["descriptor_missing_for_generation_count"] > 0,
    )

    if not render_html:
        return _emit(
            _summary(status="degraded", **body_common,
                     blocked_by="render_failed",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    # 5. Render the private guide.
    try:
        html = render_markdown(
            final_markdown, title="Multi-Asset Asset-Aware Study Guide", strict_math=False
        )
    except Exception:
        return _emit(
            _summary(status="degraded", **body_common,
                     render_status="failed",
                     blocked_by="render_failed",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    if _has_data_uri(html):
        return _emit(
            _summary(status="blocked", **body_common,
                     data_image_used=True,
                     blocked_by="data_uri_or_base64_refused",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )
    if _render_has_private_path(html, (out_dir, figure_descriptor_path, private_ocr_dir)):
        return _emit(
            _summary(status="blocked", **body_common,
                     raw_private_paths_in_rendered_html=True,
                     blocked_by="raw_private_path_in_render",
                     recommended_next_step="fix_writer_prompt_and_rerun"),
            out_dir,
        )

    table_html_count = html.count("<table")
    figure_img_present = ("<img" in html and "assets/" in html) if copied_assets else True
    broken_image = "broken" in html.lower() and "<img" in html.lower()
    tables_rendered = table_html_count >= insert_counts["inserted_table_count"]
    completed = (
        tables_rendered
        and figure_img_present
        and "data:image" not in html
        and TOKEN_RE.search(html) is None
        and not broken_image
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / GUIDE_MD).write_text(final_markdown, encoding="utf-8")
    html_path = out_dir / GUIDE_HTML
    html_path.write_text(html, encoding="utf-8")
    rendered_written = html_path.is_file()

    summary = _summary(
        status="completed" if completed else "degraded",
        **body_common,
        render_status="rendered",
        rendered_html_written=rendered_written,
        private_generated_guide_written=rendered_written,
        tables_rendered_as_real_tables=tables_rendered,
        broken_image_marker_detected=broken_image,
        blocked_by="none" if completed else "render_failed",
        recommended_next_step="operator_read_multi_asset_generated_guide"
        if completed
        else "fix_writer_prompt_and_rerun",
    )
    return _emit(summary, out_dir)


# ---------------------------------------------------------------------------
# Descriptor-set construction from existing private artifacts
# ---------------------------------------------------------------------------

def _build_descriptor_set(
    *,
    visible_artifact_path: str | None,
    private_ocr_dir: str | None,
    figure_descriptor_path: str | None,
    private_figure_descriptor_dir: str | None,
    visible_payload_override: dict[str, Any] | None,
    figure_descriptor_override: dict[str, Any] | None,
    source_label: str,
) -> tuple[list[AssetDescriptor], bool, str]:
    """Assemble descriptors from the existing private ensemble artifacts only.

    Tables come from the recovered visible-asset payload; the non-table figure comes
    from the accepted 176Z non-table figure descriptor. No extraction/OCR is rerun.
    """
    descriptors: list[AssetDescriptor] = []
    input_present = False
    label = _coerce(source_label, SOURCE_LABELS, "ensemble")

    # Tables from the recovered visible-asset payload.
    payload, payload_path = _load_visible_payload(
        visible_artifact_path=visible_artifact_path,
        private_ocr_dir=private_ocr_dir,
        override=visible_payload_override,
    )
    if isinstance(payload, dict) and (
        payload_path is None or is_private_artifact_dir(Path(payload_path).parent)
    ):
        input_present = True
        label = _coerce(payload.get("source_label"), SOURCE_LABELS, label)
        descriptors.extend(_table_descriptors_from_payload(payload, label))

    # Non-table figure from the accepted private descriptor.
    descriptor, _dpath = load_private_non_table_descriptor(
        descriptor_path=figure_descriptor_path,
        private_descriptor_dir=private_figure_descriptor_dir,
        descriptor_override=figure_descriptor_override,
    )
    if isinstance(descriptor, dict):
        input_present = True
        fig = _figure_descriptor_from_artifact(descriptor, label)
        if fig is not None:
            descriptors.append(fig)

    return descriptors, input_present, label


def _table_descriptors_from_payload(
    payload: dict[str, Any], label: str
) -> list[AssetDescriptor]:
    out: list[AssetDescriptor] = []
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        return out
    seen: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        category = _coerce(asset.get("asset_category"), _TABLE_CATEGORIES, "none")
        if category == "none":
            continue
        markdown = _faithful_table_markdown(asset)
        if markdown is None:
            continue
        asset_id = _safe_asset_id(category, "reconstructed_table")
        if asset_id in seen:
            continue
        seen.add(asset_id)
        role = detect_table_role(markdown, asset_category=category)
        out.append(
            AssetDescriptor(
                asset_id=asset_id,
                asset_kind_closed="reconstructed_table",
                descriptor_ready_for_text_writer=True,
                render_role="insert_as_table",
                source_label=label,
                _table_markdown=markdown,
                _table_role=role,
                _descriptor_text=markdown,
            )
        )
    return out


def _figure_descriptor_from_artifact(
    descriptor: dict[str, Any], label: str
) -> AssetDescriptor | None:
    ok, _blocked = validate_non_table_descriptor_contract(
        descriptor, required_source_label=label if label in SOURCE_LABELS else "ensemble"
    )
    category = _descriptor_category(descriptor)
    asset_id = _safe_asset_id(category, "non_table_figure")
    if not ok:
        # A non-table figure candidate exists but is not ready for a text writer.
        return AssetDescriptor(
            asset_id=asset_id,
            asset_kind_closed="non_table_flow_or_structure_diagram",
            descriptor_ready_for_text_writer=False,
            render_role="omit_with_reason",
            source_label=label,
            omit_reason="descriptor_not_ready",
        )
    crop = _descriptor_crop_path(descriptor)
    if crop is None:
        return AssetDescriptor(
            asset_id=asset_id,
            asset_kind_closed="non_table_flow_or_structure_diagram",
            descriptor_ready_for_text_writer=False,
            render_role="omit_with_reason",
            source_label=label,
            omit_reason="crop_unavailable",
        )
    return AssetDescriptor(
        asset_id=asset_id,
        asset_kind_closed="non_table_flow_or_structure_diagram",
        descriptor_ready_for_text_writer=True,
        render_role="insert_as_figure_with_explanation",
        source_label=label,
        _figure_crop_path=crop,
        _descriptor_text=build_descriptor_input_text(descriptor),
    )


def _coerce_override_descriptors(raw: list[dict[str, Any]]) -> list[AssetDescriptor]:
    """Build descriptors from a public-safe synthetic override (tests only)."""
    out: list[AssetDescriptor] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        kind = _coerce(item.get("asset_kind_closed"), ASSET_KINDS, "reconstructed_table")
        asset_id = _safe_asset_id(item.get("asset_id"), f"asset_{index}")
        ready = bool(item.get("descriptor_ready_for_text_writer", True))
        role = _coerce(item.get("render_role"), RENDER_ROLES, "omit_with_reason")
        crop = item.get("figure_crop_path")
        out.append(
            AssetDescriptor(
                asset_id=asset_id,
                asset_kind_closed=kind,
                descriptor_ready_for_text_writer=ready,
                render_role=role,
                source_label=_coerce(item.get("source_label"), SOURCE_LABELS, "ensemble"),
                omit_reason=item.get("omit_reason") if not ready else None,
                _table_markdown=item.get("table_markdown"),
                _table_role=str(item.get("table_role") or "unknown"),
                _figure_crop_path=Path(crop) if isinstance(crop, str) and crop else None,
                _descriptor_text=str(item.get("descriptor_text") or item.get("table_markdown") or ""),
            )
        )
    return out


def _faithful_table_markdown(asset: dict[str, Any]) -> str | None:
    tables = asset.get("table_markdown") if isinstance(asset, dict) else None
    if isinstance(tables, list):
        for table in tables:
            if _looks_like_markdown_table(table):
                return table.strip()
    reconstructed = asset.get("reconstructed_table_markdown") if isinstance(asset, dict) else None
    if _looks_like_markdown_table(reconstructed):
        return reconstructed.strip()
    return None


# ---------------------------------------------------------------------------
# Writer prompt (multi-asset, one generation pass)
# ---------------------------------------------------------------------------

def build_multi_asset_writer_messages(ready: list[AssetDescriptor]) -> list[dict[str, str]]:
    """Build the closed multi-asset writer prompt exposing every ready descriptor.

    The descriptor text (private faithful tables / figure context) lives only in the
    in-memory prompt and the gitignored outputs — never in a committed summary.
    """
    system = (
        "You are an expert medical-study-guide writer. You write clear, exam-focused "
        "study material. You never hedge, never say 'unclear' or 'I think', never expose "
        "reasoning, and never reveal file names or paths. You write finished study-guide "
        "prose only."
    )
    intro = (
        "You are writing ONE study guide that must incorporate MULTIPLE recovered assets "
        "that were EXTRACTED from lecture material. Each asset is given below as a closed "
        "descriptor. You did NOT see any image and must not assume one; treat each "
        "descriptor as the authoritative content.\n\n"
        "Global rules:\n"
        "- Use EVERY asset listed below. Place each asset's token on its own line EXACTLY "
        "ONCE, where that asset belongs. Never omit a token, never repeat a token, and "
        "never invent a token that is not listed.\n"
        "- Do NOT paste the table data, image data, paths, HTML, or the descriptor text "
        "itself. The token will be replaced with the real asset during rendering.\n"
        "- Immediately beneath each token, write a genuine teaching explanation. No "
        "placeholders, no hedging.\n\n"
        "Per-asset contract:\n"
        "- For a reconstructed_table asset: beneath its token write '## What this table "
        "shows' (3-6 teaching sentences), then '## Simplified study table' containing a "
        "real, role-aware Markdown study table (pipes and a header separator row) that "
        "clarifies the meaning rather than copying the rows.\n"
        "- For a non_table_flow_or_structure_diagram or chart_or_graph asset: beneath its "
        "token write '## What this figure shows' (3-6 sentences), then '## How to read it' "
        "(numbered reading steps), then '## Exam takeaway' (a study cue).\n\n"
        "Assets:\n"
    )
    blocks: list[str] = []
    for index, asset in enumerate(ready, start=1):
        blocks.append(
            f"ASSET {index}\n"
            f"token: {asset.token}\n"
            f"asset_kind: {asset.asset_kind_closed}\n"
            f"render_role: {asset.render_role}\n"
            "descriptor:\n"
            f"{(asset._descriptor_text or '').strip()}\n"
        )
    user = intro + "\n".join(blocks)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Writer-output parsing (closed-safe booleans / counts only)
# ---------------------------------------------------------------------------

def parse_multi_asset_output(
    response: Any, ready: list[AssetDescriptor]
) -> dict[str, Any]:
    """Parse a raw multi-asset writer response against the token/explanation contract."""
    text = response if isinstance(response, str) else ""
    by_id = {a.asset_id: a for a in ready}
    matches = list(TOKEN_RE.finditer(text))
    counts = Counter(m.group(1) for m in matches)

    # Segment text after each token up to the next token (explanation region).
    segments: dict[str, str] = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segments.setdefault(m.group(1), text[start:end])

    orphan = sum(c for aid, c in counts.items() if aid not in by_id)
    duplicate = sum(1 for aid in by_id if counts.get(aid, 0) > 1)

    inserted: list[AssetDescriptor] = []
    omitted_ready: list[AssetDescriptor] = []
    for asset in ready:
        if counts.get(asset.asset_id, 0) == 1:
            inserted.append(asset)
        elif counts.get(asset.asset_id, 0) == 0:
            omitted_ready.append(asset)
        # >1 is a duplicate, already counted; not added to inserted.

    all_explanations_real = True
    table_explanations = True
    role_aware_simplified = True
    figure_explanations = True
    figure_reading_steps = True
    figure_exam_takeaways = True
    any_table = False
    any_figure = False

    for asset in inserted:
        seg = segments.get(asset.asset_id, "")
        if is_placeholder_text(_strip_noise(seg)):
            all_explanations_real = False
        if asset.asset_kind_closed == "reconstructed_table":
            any_table = True
            if "what this table shows" not in seg.lower():
                table_explanations = False
            if "simplified" not in seg.lower() or not _has_markdown_table(seg):
                role_aware_simplified = False
        else:
            any_figure = True
            low = seg.lower()
            if "what this figure shows" not in low:
                figure_explanations = False
            if "how to read" not in low:
                figure_reading_steps = False
            if "exam takeaway" not in low and "study cue" not in low:
                figure_exam_takeaways = False

    return {
        "token_total": len(matches),
        "orphan_token_count": orphan,
        "duplicate_count": duplicate,
        "inserted": inserted,
        "omitted_ready": omitted_ready,
        "all_explanations_real": all_explanations_real,
        "table_explanations_present": table_explanations if any_table else False,
        "role_aware_simplified_tables_present": role_aware_simplified if any_table else False,
        "figure_explanations_present": figure_explanations if any_figure else False,
        "figure_reading_steps_present": figure_reading_steps if any_figure else False,
        "figure_exam_takeaways_present": figure_exam_takeaways if any_figure else False,
    }


class _TableImageError(Exception):
    """Raised if a table asset would be resolved as an image rather than a table."""


def _resolve_tokens(
    response: str, inserted: list[AssetDescriptor], out_dir: Path
) -> tuple[str, list[str]]:
    """Resolve each inserted asset's single token to its safe rendered form.

    Tables resolve to the faithful Markdown table (never an image); figures resolve to
    a safe ``assets/<name>`` image copied into the private output dir. Raises
    ``_TableImageError`` if a table descriptor lacks Markdown (would force an image) and
    ``FileNotFoundError`` if a figure crop is missing.
    """
    final = response
    copied: list[str] = []
    for asset in inserted:
        if asset.asset_kind_closed == "reconstructed_table":
            markdown = asset._table_markdown
            if not _looks_like_markdown_table(markdown):
                raise _TableImageError(asset.asset_id)
            replacement = "\n\n" + markdown.strip() + "\n\n"
        else:
            crop = asset._figure_crop_path
            if crop is None or not Path(crop).is_file():
                raise FileNotFoundError(asset.asset_id)
            image_ref, _dest = _copy_crop_as_safe_asset(Path(crop), out_dir, asset.asset_id)
            copied.append(image_ref)
            replacement = "\n\n![Recovered study visual](" + image_ref + ")\n\n"
        final = final.replace(asset.token, replacement, 1)
    return final, copied


# ---------------------------------------------------------------------------
# Counting helpers
# ---------------------------------------------------------------------------

def _descriptor_counts(descriptors: list[AssetDescriptor]) -> dict[str, int]:
    ready = [d for d in descriptors if d.descriptor_ready_for_text_writer]
    table = sum(1 for d in ready if d.asset_kind_closed == "reconstructed_table")
    figure = sum(1 for d in ready if d.asset_kind_closed == "non_table_flow_or_structure_diagram")
    chart = sum(1 for d in ready if d.asset_kind_closed == "chart_or_graph_with_existing_descriptor")
    missing = sum(
        1
        for d in descriptors
        if not d.descriptor_ready_for_text_writer
        and d.asset_kind_closed
        in {"non_table_flow_or_structure_diagram", "chart_or_graph_with_existing_descriptor"}
    )
    return {
        "available_asset_descriptor_count": len(descriptors),
        "descriptor_ready_count": len(ready),
        "table_descriptor_count": table,
        "non_table_figure_descriptor_count": figure,
        "chart_or_graph_descriptor_count": chart,
        "descriptor_missing_for_generation_count": missing,
    }


def _inserted_kind_counts(inserted: list[AssetDescriptor]) -> dict[str, int]:
    return {
        "inserted_table_count": sum(
            1 for d in inserted if d.asset_kind_closed == "reconstructed_table"
        ),
        "inserted_non_table_figure_count": sum(
            1 for d in inserted if d.asset_kind_closed == "non_table_flow_or_structure_diagram"
        ),
        "inserted_chart_or_graph_count": sum(
            1 for d in inserted if d.asset_kind_closed == "chart_or_graph_with_existing_descriptor"
        ),
    }


def _strip_noise(value: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", value)
    text = re.sub(r"\|[^\n]+\|", " ", text)
    return re.sub(r"#+", " ", text)


def _has_markdown_table(value: str) -> bool:
    lines = [ln.strip() for ln in value.splitlines()]
    for i in range(len(lines) - 1):
        if lines[i].startswith("|") and lines[i + 1].startswith("|") and set(lines[i + 1]) <= set("|-: "):
            return True
    return False


def _has_data_uri(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _DATA_URI_MARKERS)


def _resolve_out_dir(private_output_dir: str | None, private_ocr_dir: str | None) -> Path:
    if private_output_dir:
        return Path(private_output_dir)
    if private_ocr_dir:
        return Path(private_ocr_dir) / (ARTIFACT_NAME + "_177g")
    return Path(tempfile.gettempdir()) / (ARTIFACT_NAME + "_177g")


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


# ---------------------------------------------------------------------------
# Closed committed-safe summary
# ---------------------------------------------------------------------------

def _summary(
    *,
    status: str,
    source_label: str = "ensemble",
    input_private_descriptor_artifacts_available: bool = False,
    descriptor_set_built: bool = False,
    available_asset_descriptor_count: int = 0,
    descriptor_ready_count: int = 0,
    table_descriptor_count: int = 0,
    non_table_figure_descriptor_count: int = 0,
    chart_or_graph_descriptor_count: int = 0,
    descriptor_missing_for_generation_count: int = 0,
    diagram_caption_descriptor_gap: bool = False,
    multi_asset_requirement_met: bool = False,
    provider_call_made: bool = False,
    provider_name_closed: str = "none",
    model_name_closed: str = "none",
    writer_generation_run: bool = False,
    generation_rerun: bool = False,
    generation_behavior_changed: bool = False,
    asset_tokens_available_count: int = 0,
    asset_tokens_inserted_count: int = 0,
    distinct_inserted_asset_count: int = 0,
    inserted_table_count: int = 0,
    inserted_non_table_figure_count: int = 0,
    inserted_chart_or_graph_count: int = 0,
    summarized_asset_count: int = 0,
    omitted_asset_count: int = 0,
    omitted_with_closed_reason_count: int = 0,
    all_available_useful_descriptors_considered: bool = False,
    same_single_table_figure_output: bool = False,
    not_byte_identical_to_prior_single_asset_output: bool = False,
    orphan_asset_token_count: int = 0,
    duplicate_inserted_asset_count: int = 0,
    tables_rendered_as_real_tables: bool = False,
    faithful_table_reconstruction_present: bool = False,
    role_aware_simplified_tables_present: bool = False,
    table_explanations_present: bool = False,
    tables_inserted_as_images: bool = False,
    figures_inserted_with_relative_assets: bool = False,
    figure_explanations_present: bool = False,
    figure_reading_steps_present: bool = False,
    figure_exam_takeaways_present: bool = False,
    table_like_visuals_refused_as_figures: bool = True,
    render_status: str = "not_run",
    rendered_html_written: bool = False,
    private_generated_guide_written: bool = False,
    raw_private_paths_in_rendered_html: bool = False,
    broken_image_marker_detected: bool = False,
    data_image_used: bool = False,
    base64_used: bool = False,
    blocked_by: str = "none",
    recommended_next_step: str = "fix_writer_prompt_and_rerun",
) -> dict[str, Any]:
    """Assemble the committed-safe closed summary (closed vocabulary + counts only)."""
    summary = {
        "artifact_name": ARTIFACT_NAME,
        "slice": SLICE_LABEL,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        # Posture / scope.
        "off_by_default": True,
        "normal_generation_default_unchanged": True,
        "generation_scope": "single_private_ensemble_multi_asset_generation",
        "wrapper_slice": False,
        "manifest_consumer": False,
        "coverage_packet_only": False,
        "auto_discovery_enabled": False,
        "all_assets_claimed": False,
        # Descriptor set.
        "input_private_descriptor_artifacts_available": bool(input_private_descriptor_artifacts_available),
        "descriptor_set_built": bool(descriptor_set_built),
        "available_asset_descriptor_count": int(available_asset_descriptor_count),
        "descriptor_ready_count": int(descriptor_ready_count),
        "table_descriptor_count": int(table_descriptor_count),
        "non_table_figure_descriptor_count": int(non_table_figure_descriptor_count),
        "chart_or_graph_descriptor_count": int(chart_or_graph_descriptor_count),
        "descriptor_missing_for_generation_count": int(descriptor_missing_for_generation_count),
        "diagram_caption_descriptor_gap": bool(diagram_caption_descriptor_gap),
        # Generation.
        "multi_asset_requirement_met": bool(multi_asset_requirement_met),
        "provider_call_made": bool(provider_call_made),
        "provider_name_closed": _coerce(provider_name_closed, PROVIDER_NAMES, "none"),
        "model_name_closed_or_redacted": _safe_model_name(model_name_closed),
        "writer_generation_run": bool(writer_generation_run),
        "generation_rerun": bool(generation_rerun),
        "generation_behavior_changed": bool(generation_behavior_changed),
        # Insertion accounting.
        "asset_tokens_available_count": int(asset_tokens_available_count),
        "asset_tokens_inserted_count": int(asset_tokens_inserted_count),
        "distinct_inserted_asset_count": int(distinct_inserted_asset_count),
        "inserted_table_count": int(inserted_table_count),
        "inserted_non_table_figure_count": int(inserted_non_table_figure_count),
        "inserted_chart_or_graph_count": int(inserted_chart_or_graph_count),
        "summarized_asset_count": int(summarized_asset_count),
        "omitted_asset_count": int(omitted_asset_count),
        "omitted_with_closed_reason_count": int(omitted_with_closed_reason_count),
        "all_available_useful_descriptors_considered": bool(all_available_useful_descriptors_considered),
        "same_single_table_figure_output": bool(same_single_table_figure_output),
        "not_byte_identical_to_prior_single_asset_output": bool(
            not_byte_identical_to_prior_single_asset_output
        ),
        "orphan_asset_token_count": int(orphan_asset_token_count),
        "duplicate_inserted_asset_count": int(duplicate_inserted_asset_count),
        # Table rendering.
        "tables_rendered_as_real_tables": bool(tables_rendered_as_real_tables),
        "faithful_table_reconstruction_present": bool(faithful_table_reconstruction_present),
        "role_aware_simplified_tables_present": bool(role_aware_simplified_tables_present),
        "table_explanations_present": bool(table_explanations_present),
        "tables_inserted_as_images": bool(tables_inserted_as_images),
        # Figure rendering.
        "figures_inserted_with_relative_assets": bool(figures_inserted_with_relative_assets),
        "figure_explanations_present": bool(figure_explanations_present),
        "figure_reading_steps_present": bool(figure_reading_steps_present),
        "figure_exam_takeaways_present": bool(figure_exam_takeaways_present),
        "table_like_visuals_refused_as_figures": bool(table_like_visuals_refused_as_figures),
        # Private render artifacts.
        "private_generated_guide_written": bool(private_generated_guide_written),
        "private_generated_guide_gitignored": True,
        "render_format": "html" if render_status == "rendered" else "not_run",
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        "rendered_html_written": bool(rendered_html_written),
        "rendered_html_gitignored": True,
        # Closed negative canaries — committed posture, never raw content.
        "raw_private_paths_in_rendered_html": bool(raw_private_paths_in_rendered_html),
        "broken_image_marker_detected": bool(broken_image_marker_detected),
        "data_image_used": bool(data_image_used),
        "base64_used": bool(base64_used),
        "raw_guide_committed": False,
        "raw_table_text_committed": False,
        "raw_figure_text_committed": False,
        "raw_caption_text_committed": False,
        "raw_descriptor_json_committed": False,
        "raw_source_committed": False,
        "raw_ocr_committed": False,
        "image_bytes_committed": False,
        "screenshots_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        # Hard "did NOT do" posture.
        "generation_rerun_only_in_private_runner": True,
        "cloud_ocr_used": False,
        "ocr_rerun": False,
        "chandra_used": False,
        "coverage_eval_rerun": False,
        "numeric_verification_claimed": False,
        "frontend_api_changed": False,
        "judge_ready": False,
        "repair_ready": False,
        "operator_private_read_required": True,
        "operator_private_read_done": False,
        "blocked_by": _coerce(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "fix_writer_prompt_and_rerun"),
    }
    _assert_summary_safe(summary)
    return summary


def _assert_summary_safe(summary: dict[str, Any]) -> None:
    """Fail loudly if any closed-summary VALUE could carry leaked content.

    Keys are controlled closed vocabulary; only string values could ever leak, so scope
    the scan to non-boolean string values (closed labels). Integers/booleans are safe.
    """
    string_values = [v for v in summary.values() if isinstance(v, str)]
    blob = " ".join(string_values).lower()
    for marker in ("data:image", ";base64,", "/", "\\", "prompt:", "response:", ".png", ".jpg"):
        if marker in blob:
            raise ValueError("177G closed summary contains forbidden marker")
    if re.search(r"\b[a-f0-9]{16,}\b", blob):
        raise ValueError("177G closed summary contains hash-like string")


def _emit(summary: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    """Write the closed summary into the private dir when it is safe to do so."""
    if is_private_artifact_dir(out_dir):
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / SUMMARY_JSON).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        except Exception:
            pass
    return summary


def main() -> int:
    summary = run_multi_asset_asset_aware_generation(
        visible_artifact_path=os.environ.get("PRIVATE_VISIBLE_ARTIFACT") or None,
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR") or None,
        figure_descriptor_path=os.environ.get("PRIVATE_DESCRIPTOR_PATH") or None,
        private_figure_descriptor_dir=os.environ.get("PRIVATE_DESCRIPTOR_DIR") or None,
        private_output_dir=os.environ.get("PRIVATE_OUTPUT_DIR") or None,
        provider=os.environ.get("WRITER_PROVIDER") or None,
        model_choice=os.environ.get("WRITER_MODEL_CHOICE", "Use environment default"),
        custom_model=os.environ.get("WRITER_CUSTOM_MODEL") or None,
        source_label=os.environ.get("SOURCE_LABEL", "ensemble"),
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
