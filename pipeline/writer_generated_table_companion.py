"""Slice 176W: writer-generated table companion (first Phase 4 generation slice).

Slice 176U proved the mechanical rendered reconstructed-table path; Slice 176V added
explanation + simplified-table *slots* beside the faithful table but blocked honestly
because it required operator-provided / deterministic content and never called a
provider (``generation_behavior_changed=false``). This module is the first Phase 4
slice where **generation behavior actually changes**: a real provider/model WRITER is
given a closed table descriptor (the existing private recovered table) and must

  * insert the ``{{table:patient_dataset}}`` token exactly once where the faithful
    table belongs (the writer inserts the token, never postprocessor/template code),
  * write a genuine, non-placeholder explanation beneath that token, and
  * emit a simplified, clearer, study-friendly Markdown table generated *from the
    descriptor* (never a deterministic placeholder).

The single token is then resolved through the existing render path: it is replaced by
the faithful recovered Markdown table (a real table, never an image) and the whole
companion is rendered to private HTML for the operator to read.

Architecture: figure/table understanding is an EXTRACTION concern. The writer receives
extracted table content as a closed descriptor — it does NOT see an image and does not
need vision. ``writer_saw_image=false`` by construction.

Committed outputs are closed status labels only. Raw guide / table / explanation /
simplified-table / caption / source / OCR text, prompts, responses, provider payloads,
private paths, hashes and byte counts are structurally excluded from returned summaries
and from anything written outside the gitignored private artifact directory.

What this module is **NOT** (do not grow it into any of these here): an OCR rerun, a
``candidate_1`` run, a coverage eval, a new validator/ingest/schema/bridge as primary
output, a frontend/API rollout, a Layer-2 judge, repair, or cloud OCR.
``judge_ready=false``; ``repair_ready=false``. It never claims explanation/simplified
*quality* — that requires private operator inspection — and it never injects the token
or any prose itself.
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
from pipeline.rendered_visible_asset_insertion_proof import (  # noqa: E402
    _load_visible_payload,
    _looks_like_markdown_table,
    select_visible_asset_payload,
)
from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.visible_table_figure_pilot import SOURCE_LABEL_DEFAULT  # noqa: E402

ARTIFACT_NAME = "writer_generated_table_companion"

#: The single writer token. The writer must emit this exactly once; this module never
#: injects it. Resolution replaces it with the faithful recovered Markdown table.
WRITER_TOKEN = "{{table:patient_dataset}}"

STATUSES = frozenset({"completed", "degraded", "blocked"})
SOURCE_LABELS = frozenset({"ensemble", "candidate_1", "mixed", "unknown"})
TABLE_CATEGORIES = frozenset({"patient_dataset_table", "proximity_matrix"})
ASSET_CATEGORIES = frozenset({"patient_dataset_table", "proximity_matrix", "none"})
TOKEN_COUNTS = frozenset({"0", "1", "many"})
EXPLANATION_SOURCES = frozenset({"writer_generated_from_descriptor", "unavailable", "invalid"})
SIMPLIFIED_SOURCES = frozenset(
    {"writer_generated_from_descriptor", "deterministic_fallback", "unavailable"}
)
RENDER_FORMATS = frozenset({"html", "not_run"})
RENDER_STATUSES = frozenset({"rendered", "failed", "not_run"})
VISIBILITY_STATUSES = frozenset({"operator_pending", "visible", "not_checked", "failed"})
PROVIDER_NAMES = frozenset({"deepseek", "qwen", "local", "test_fake", "none"})
BLOCKED_BY = frozenset(
    {
        "none",
        "provider_unavailable",
        "writer_generation_unavailable",
        "writer_token_missing",
        "writer_token_duplicate",
        "writer_token_invalid",
        "render_failed",
        "private_artifact_missing",
        "placeholder_content_detected",
        "unsafe_private_artifact_path",
    }
)
NEXT_STEPS = frozenset(
    {
        "operator_read_private_rendered_guide",
        "fix_writer_prompt_and_rerun",
        "fallback_to_descriptor_captioning_for_figures",
    }
)

_PLACEHOLDER_MARKERS = (
    "placeholder",
    "todo",
    "tbd",
    "lorem ipsum",
    "xxxx",
    "fill in",
    "your text here",
    "example explanation",
    "sample text",
    "to be written",
    "i think",
    "unclear",
    "not sure",
)

#: Writer is a callable that takes a list of chat messages and returns the raw model
#: text. Tests inject a fake; the real path builds one from the provider boundary.
WriterFn = Callable[[list[dict[str, str]]], str]


def build_writer_messages(*, faithful_markdown: str) -> list[dict[str, str]]:
    """Build the closed writer prompt. Carries the extracted table as a descriptor.

    The faithful Markdown table is real private content; it lives only in-memory and in
    the gitignored private outputs — never in a committed summary. The prompt tells the
    writer it received an *extracted descriptor* (no image) and pins the exact contract
    this module parses: one ``{{table:patient_dataset}}`` token, an explanation beneath
    it, then a simplified Markdown table.
    """
    system = (
        "You are an expert medical-study-guide writer. You write clear, exam-focused "
        "study material. You never hedge, never say 'unclear' or 'I think', and never "
        "expose your reasoning. You write finished study-guide prose only."
    )
    user = (
        "You are writing ONE section of a study guide about a patient-dataset table that "
        "was EXTRACTED from lecture material. You are given the faithful extracted table "
        "below as a closed descriptor. You did NOT see an image and must not assume one; "
        "treat the extracted table as the authoritative content.\n\n"
        "Produce Markdown that follows this contract EXACTLY:\n"
        f"1. Place the token {WRITER_TOKEN} on its own line, EXACTLY ONCE, at the point "
        "where the faithful table should appear. Do NOT paste the table itself — the "
        "token will be replaced by the faithful table during rendering.\n"
        "2. Immediately beneath the token, write a section headed "
        "'## What this table shows' with a genuine teaching explanation (3-6 sentences) "
        "of what the table teaches a student: the variables, what they mean, and the "
        "study takeaway. No hedging, no placeholders.\n"
        "3. Then write a section headed '## Simplified study table' containing a clearer, "
        "study-friendly Markdown table: fewer columns or rows, or reorganized, while "
        "preserving the key terms and meaning. It MUST be a real Markdown table (pipes "
        "and a header separator row), never a placeholder and never an image.\n"
        "4. Do not reveal any file names or paths.\n\n"
        "Faithful extracted table (descriptor):\n\n"
        f"{faithful_markdown.strip()}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def parse_writer_output(response: str, *, faithful_markdown: str) -> dict[str, Any]:
    """Parse a raw writer response against the token/explanation/simplified contract.

    Returns closed-safe booleans/labels only (no raw text). ``token_count`` is the raw
    count; the rest describe whether the explanation beneath the token and the simplified
    table are present and non-placeholder. The simplified table is only counted as
    writer-generated when it is a real Markdown table that is NOT a normalized copy of
    the faithful table.
    """
    text = response if isinstance(response, str) else ""
    count = text.count(WRITER_TOKEN)
    token_count_label = "0" if count == 0 else "1" if count == 1 else "many"
    result = {
        "token_count": count,
        "token_count_label": token_count_label,
        "explanation_present": False,
        "explanation_real": False,
        "simplified_present": False,
        "simplified_real": False,
        "simplified_markdown": "",
    }
    if count != 1:
        return result

    _before, after = text.split(WRITER_TOKEN, 1)
    after_lines = after.splitlines()
    tables = _extract_markdown_tables(after)
    if tables:
        table_start, simplified_md = tables[0]
        explanation_lines = after_lines[:table_start]
        result["simplified_markdown"] = simplified_md
        result["simplified_present"] = True
        result["simplified_real"] = _simplified_is_writer_generated(
            simplified_md, faithful_markdown
        )
    else:
        explanation_lines = after_lines

    explanation_text = _strip_heading_markers("\n".join(explanation_lines)).strip()
    result["explanation_present"] = bool(explanation_text)
    result["explanation_real"] = bool(explanation_text) and not is_placeholder_text(
        explanation_text
    )
    return result


def run_writer_generated_table_companion(
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
    """Run the writer-generated table companion against the private recovered table.

    With ``writer=None`` (the real path) this makes ONE real provider/model generation
    call through the app's provider boundary. Tests inject a ``writer`` callable so they
    never touch a provider. The slice blocks honestly when the provider is unavailable,
    when the writer does not insert exactly one token, or when the explanation/simplified
    content is missing or placeholder.
    """
    # 1. Load the existing private recovered table artifact.
    payload, payload_path = _load_visible_payload(
        visible_artifact_path=visible_artifact_path,
        private_ocr_dir=private_ocr_dir,
        override=visible_payload_override,
    )
    if not isinstance(payload, dict):
        return _summary(status="blocked", source_label=source_label,
                        blocked_by="private_artifact_missing",
                        recommended_next_step="fix_writer_prompt_and_rerun")
    if payload_path is not None and not is_private_artifact_dir(Path(payload_path).parent):
        return _summary(status="blocked", source_label=source_label,
                        blocked_by="unsafe_private_artifact_path",
                        recommended_next_step="fix_writer_prompt_and_rerun")

    label = _source_label_from_payload(payload, source_label)
    asset = select_visible_asset_payload(payload)
    if asset is None:
        return _summary(status="blocked", source_label=label,
                        blocked_by="private_artifact_missing",
                        recommended_next_step="fix_writer_prompt_and_rerun")
    category = _asset_category(asset)
    faithful_markdown = _faithful_table_markdown(asset)
    if faithful_markdown is None:
        return _summary(status="blocked", source_label=label,
                        selected_asset_category=category,
                        blocked_by="private_artifact_missing",
                        recommended_next_step="fix_writer_prompt_and_rerun")

    parent = Path(payload_path).parent if payload_path else Path.cwd()
    out_dir = Path(private_companion_dir) if private_companion_dir else parent / ARTIFACT_NAME
    if not is_private_artifact_dir(out_dir):
        return _summary(status="blocked", source_label=label,
                        selected_asset_category=category,
                        writer_input_descriptor_present=True,
                        faithful_table_present=True,
                        blocked_by="unsafe_private_artifact_path",
                        recommended_next_step="fix_writer_prompt_and_rerun")

    # 2. Build the closed descriptor prompt for the writer.
    messages = build_writer_messages(faithful_markdown=faithful_markdown)

    # 3. Make the real (or injected) writer call. Honest blocking on unavailability.
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
        return _summary(status="blocked", source_label=label,
                        selected_asset_category=category,
                        writer_input_descriptor_present=True,
                        faithful_table_present=True,
                        provider_name_closed=_coerce(provider_name, PROVIDER_NAMES, "none"),
                        blocked_by="provider_unavailable",
                        recommended_next_step="fix_writer_prompt_and_rerun")
    except Exception:
        return _summary(status="blocked", source_label=label,
                        selected_asset_category=category,
                        writer_input_descriptor_present=True,
                        faithful_table_present=True,
                        provider_name_closed=_coerce(provider_name, PROVIDER_NAMES, "none"),
                        model_name_closed=model_name,
                        blocked_by="writer_generation_unavailable",
                        recommended_next_step="fix_writer_prompt_and_rerun")

    provider_name_closed = _coerce(provider_name, PROVIDER_NAMES, "none")

    # 4. Parse the writer output against the contract.
    parsed = parse_writer_output(response, faithful_markdown=faithful_markdown)
    common = dict(
        source_label=label,
        selected_asset_category=category,
        writer_input_descriptor_present=True,
        faithful_table_present=True,
        provider_call_made=True,
        provider_name_closed=provider_name_closed,
        model_name_closed=model_name,
        generation_rerun=True,
    )

    if parsed["token_count"] == 0:
        return _summary(status="blocked", **common,
                        blocked_by="writer_token_missing",
                        recommended_next_step="fix_writer_prompt_and_rerun")
    if parsed["token_count"] > 1:
        return _summary(status="blocked", **common,
                        writer_token_present=True, writer_token_count="many",
                        writer_token_inserted_by_writer=True,
                        generation_behavior_changed=True,
                        blocked_by="writer_token_duplicate",
                        recommended_next_step="fix_writer_prompt_and_rerun")

    # token_count == 1 — the writer changed generation behavior.
    common.update(
        writer_token_present=True,
        writer_token_count="1",
        writer_token_inserted_by_writer=True,
        generation_behavior_changed=True,
    )
    if not parsed["explanation_real"]:
        return _summary(status="blocked", **common,
                        explanation_beneath_asset_present=parsed["explanation_present"],
                        explanation_source="writer_generated_from_descriptor"
                        if parsed["explanation_present"] else "unavailable",
                        explanation_non_placeholder=False,
                        simplified_table_present=parsed["simplified_present"],
                        simplified_table_source="writer_generated_from_descriptor"
                        if parsed["simplified_present"] else "unavailable",
                        simplified_table_non_placeholder=parsed["simplified_real"],
                        blocked_by="placeholder_content_detected",
                        recommended_next_step="fix_writer_prompt_and_rerun")
    if not parsed["simplified_real"]:
        return _summary(status="blocked", **common,
                        explanation_beneath_asset_present=True,
                        explanation_source="writer_generated_from_descriptor",
                        explanation_non_placeholder=True,
                        simplified_table_present=parsed["simplified_present"],
                        simplified_table_source="writer_generated_from_descriptor"
                        if parsed["simplified_present"] else "unavailable",
                        simplified_table_non_placeholder=False,
                        blocked_by="placeholder_content_detected",
                        recommended_next_step="fix_writer_prompt_and_rerun")

    # 5. Resolve the single token to the faithful table and render private HTML.
    final_markdown = response.replace(
        WRITER_TOKEN, "\n\n" + faithful_markdown.strip() + "\n\n", 1
    )
    render_format = "not_run"
    render_status = "not_run"
    rendered_written = False
    faithful_visibility = "not_checked"
    explanation_visibility = "not_checked"
    simplified_visibility = "not_checked"
    status = "degraded"
    blocker = "render_failed"
    next_step = "fix_writer_prompt_and_rerun"

    if render_html:
        try:
            html = render_markdown(
                final_markdown, title="Writer Table Companion Guide", strict_math=False
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "writer_generated_table_companion_guide.md").write_text(
                final_markdown, encoding="utf-8"
            )
            html_path = out_dir / "writer_generated_table_companion_guide.html"
            html_path.write_text(html, encoding="utf-8")
            rendered_written = html_path.is_file()
            render_format = "html"
            render_status = "rendered"
            table_count = html.count("<table")
            token_absent = WRITER_TOKEN not in html
            no_image = "<img" not in html and "data:image" not in html
            explanation_rendered = "What this table shows" in html
            # faithful (resolved) + simplified ⇒ two real tables, no leftover token,
            # no image substitution.
            full = table_count >= 2 and token_absent and no_image and explanation_rendered
            if full:
                status = "completed"
                blocker = "none"
                next_step = "operator_read_private_rendered_guide"
                faithful_visibility = "operator_pending"
                explanation_visibility = "operator_pending"
                simplified_visibility = "operator_pending"
            else:
                status = "degraded"
                blocker = "writer_token_invalid" if not token_absent else "render_failed"
                next_step = "fix_writer_prompt_and_rerun"
                faithful_visibility = "failed"
                explanation_visibility = "operator_pending" if explanation_rendered else "failed"
                simplified_visibility = "failed"
        except Exception:
            render_format = "not_run"
            render_status = "failed"
            blocker = "render_failed"

    summary = _summary(
        status=status,
        **common,
        explanation_beneath_asset_present=True,
        explanation_source="writer_generated_from_descriptor",
        explanation_non_placeholder=True,
        simplified_table_present=True,
        simplified_table_source="writer_generated_from_descriptor",
        simplified_table_non_placeholder=True,
        render_format=render_format,
        render_status=render_status,
        private_rendered_guide_written=rendered_written,
        private_rendered_guide_gitignored=is_private_artifact_dir(out_dir),
        faithful_table_visibility_status=faithful_visibility,
        explanation_visibility_status=explanation_visibility,
        simplified_table_visibility_status=simplified_visibility,
        blocked_by=blocker,
        recommended_next_step=next_step,
    )
    if render_status == "rendered":
        (out_dir / "closed_writer_generated_table_companion_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
    return summary


def _summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    selected_asset_category: str = "patient_dataset_table",
    writer_input_descriptor_present: bool = False,
    provider_call_made: bool = False,
    provider_name_closed: str = "none",
    model_name_closed: str = "none",
    generation_rerun: bool = False,
    generation_behavior_changed: bool = False,
    writer_token_present: bool = False,
    writer_token_count: str = "0",
    writer_token_inserted_by_writer: bool = False,
    faithful_table_present: bool = False,
    explanation_beneath_asset_present: bool = False,
    explanation_source: str = "unavailable",
    explanation_non_placeholder: bool = False,
    simplified_table_present: bool = False,
    simplified_table_source: str = "unavailable",
    simplified_table_non_placeholder: bool = False,
    render_format: str = "not_run",
    render_status: str = "not_run",
    private_rendered_guide_written: bool = False,
    private_rendered_guide_gitignored: bool = False,
    faithful_table_visibility_status: str = "not_checked",
    explanation_visibility_status: str = "not_checked",
    simplified_table_visibility_status: str = "not_checked",
    blocked_by: str = "none",
    recommended_next_step: str = "fix_writer_prompt_and_rerun",
) -> dict[str, Any]:
    """Assemble the committed-safe closed summary (closed vocabulary only, no raw text)."""
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _coerce(source_label, SOURCE_LABELS, "unknown"),
        "selected_asset_category": _coerce(selected_asset_category, ASSET_CATEGORIES, "none"),
        "selected_asset_kind": "table",
        "asset_descriptor_source": "private_recovered_table_artifact",
        "writer_input_descriptor_present": bool(writer_input_descriptor_present),
        "writer_saw_image": False,
        "provider_call_made": bool(provider_call_made),
        "provider_name_closed": _coerce(provider_name_closed, PROVIDER_NAMES, "none"),
        "model_name_closed_or_redacted": _safe_model_name(model_name_closed),
        "generation_rerun": bool(generation_rerun),
        "generation_behavior_changed": bool(generation_behavior_changed),
        "writer_token_present": bool(writer_token_present),
        "writer_token_count": _coerce(writer_token_count, TOKEN_COUNTS, "0"),
        "writer_token_inserted_by_writer": bool(writer_token_inserted_by_writer),
        "postprocessor_token_injected": False,
        "faithful_table_present": bool(faithful_table_present),
        "faithful_table_source": "private_recovered_table",
        "table_inserted_as_image": False,
        "explanation_beneath_asset_present": bool(explanation_beneath_asset_present),
        "explanation_source": _coerce(explanation_source, EXPLANATION_SOURCES, "unavailable"),
        "explanation_non_placeholder": bool(explanation_non_placeholder),
        "simplified_table_present": bool(simplified_table_present),
        "simplified_table_source": _coerce(simplified_table_source, SIMPLIFIED_SOURCES, "unavailable"),
        "simplified_table_non_placeholder": bool(simplified_table_non_placeholder),
        "render_format": _coerce(render_format, RENDER_FORMATS, "not_run"),
        "render_status": _coerce(render_status, RENDER_STATUSES, "not_run"),
        "private_rendered_guide_written": bool(private_rendered_guide_written),
        "private_rendered_guide_gitignored": bool(private_rendered_guide_gitignored),
        "faithful_table_visibility_status": _coerce(
            faithful_table_visibility_status, VISIBILITY_STATUSES, "not_checked"
        ),
        "explanation_visibility_status": _coerce(
            explanation_visibility_status, VISIBILITY_STATUSES, "not_checked"
        ),
        "simplified_table_visibility_status": _coerce(
            simplified_table_visibility_status, VISIBILITY_STATUSES, "not_checked"
        ),
        "operator_private_read_required": True,
        "operator_private_read_done": False,
        # Closed negative canaries — committed posture, never raw content.
        "raw_table_text_committed": False,
        "raw_explanation_committed": False,
        "raw_simplified_table_committed": False,
        "raw_source_committed": False,
        "raw_ocr_committed": False,
        "raw_guide_committed": False,
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
        "blocked_by": _coerce(blocked_by, BLOCKED_BY, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "fix_writer_prompt_and_rerun"),
    }


# ---------------------------------------------------------------------------
# Helpers (pure)
# ---------------------------------------------------------------------------

def _faithful_table_markdown(asset: dict[str, Any]) -> str | None:
    if _asset_category(asset) not in TABLE_CATEGORIES:
        return None
    tables = asset.get("table_markdown") if isinstance(asset, dict) else None
    if isinstance(tables, list):
        for table in tables:
            if _looks_like_markdown_table(table):
                return table.strip()
    reconstructed = asset.get("reconstructed_table_markdown") if isinstance(asset, dict) else None
    if _looks_like_markdown_table(reconstructed):
        return reconstructed.strip()
    return None


def _extract_markdown_tables(text: str) -> list[tuple[int, str]]:
    """Return ``(start_line_index, table_markdown)`` for each Markdown table block."""
    lines = text.splitlines()
    blocks: list[tuple[int, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].strip().startswith("|"):
            start = i
            group: list[str] = []
            while i < n and lines[i].strip().startswith("|"):
                group.append(lines[i])
                i += 1
            block = "\n".join(group).strip()
            if _looks_like_markdown_table(block):
                blocks.append((start, block))
        else:
            i += 1
    return blocks


def _simplified_is_writer_generated(simplified_md: str, faithful_markdown: str) -> bool:
    """True only for a real, non-placeholder table that is not a copy of the faithful one."""
    if not _looks_like_markdown_table(simplified_md):
        return False
    low = simplified_md.lower()
    if any(marker in low for marker in _PLACEHOLDER_MARKERS):
        return False
    grid = _parse_markdown_table(simplified_md)
    if len(grid) < 2:
        return False
    cell_chars = sum(len(c.strip()) for row in grid for c in row)
    if cell_chars < 4:
        return False
    return _normalize_table(simplified_md) != _normalize_table(faithful_markdown)


def is_placeholder_text(text: Any) -> bool:
    """Heuristic: True when ``text`` looks like placeholder/boilerplate, not real prose."""
    if not isinstance(text, str):
        return True
    stripped = text.strip()
    if len(stripped) < 24:
        return True
    low = stripped.lower()
    if any(marker in low for marker in _PLACEHOLDER_MARKERS):
        return True
    letters = sum(1 for c in stripped if c.isalpha())
    if letters < 20:
        return True
    words = [w for w in re.split(r"\s+", stripped) if w]
    return len(words) < 6


def _strip_heading_markers(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        out.append(stripped.lstrip("#").strip() if stripped.startswith("#") else line)
    return "\n".join(out)


def _parse_markdown_table(markdown: Any) -> list[list[str]]:
    if not isinstance(markdown, str):
        return []
    rows: list[list[str]] = []
    for index, line in enumerate([ln.strip() for ln in markdown.strip().splitlines() if ln.strip()]):
        if not line.startswith("|"):
            continue
        if index == 1 and "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def _normalize_table(markdown: str) -> str:
    grid = _parse_markdown_table(markdown)
    return "\n".join(" ".join(c.strip().lower() for c in row) for row in grid).strip()


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
    """Model ids are public, but cap length and strip anything path/secret-shaped."""
    if not isinstance(value, str) or not value.strip():
        return "none"
    name = value.strip()
    if "/" in name or "\\" in name or len(name) > 64:
        return "redacted"
    return name


def _asset_category(asset: dict[str, Any]) -> str:
    return _coerce(asset.get("asset_category") if isinstance(asset, dict) else None, ASSET_CATEGORIES, "none")


def _source_label_from_payload(payload: dict[str, Any], fallback: str) -> str:
    raw = payload.get("source_label") if isinstance(payload, dict) else fallback
    return _coerce(raw, SOURCE_LABELS, "unknown")


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_writer_generated_table_companion(
        visible_artifact_path=os.environ.get("PRIVATE_VISIBLE_ARTIFACT"),
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR"),
        private_companion_dir=os.environ.get("PRIVATE_COMPANION_DIR"),
        provider=os.environ.get("WRITER_PROVIDER") or None,
        model_choice=os.environ.get("WRITER_MODEL_CHOICE", "Use environment default"),
        custom_model=os.environ.get("WRITER_CUSTOM_MODEL") or None,
        source_label=os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT),
        render_html=os.environ.get("RENDER_HTML", "1") != "0",
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] in {"completed", "degraded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
