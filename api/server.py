from __future__ import annotations

import io
import json
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from pipeline import (
    ask_context,
    ask_inventory,
    generator_presets,
    library_store,
    presets as preset_store,
    shortcut_store,
    style_store,
)
from pipeline.job_manager import (
    JOBS_DIR,
    Job,
    JobManagerError,
    empty_trash,
    is_trashed,
    list_trashed,
    purge_trashed_job,
    restore_job,
    trash_job,
)
from pipeline.llm_client import LLMProviderError, MissingLLMConfigError, generate_chat_completion
from pipeline.markdown_sections import (
    check_outline_compliance,
    parse_sections,
    splice_section,
)
from pipeline.orchestrator import (
    DIFFICULTY_VALUES,
    OUTPUT_DEPTH_VALUES,
    generate_study_guide,
)
from pipeline import provider_settings_store
from pipeline.provider_config import (
    build_provider_config,
    clear_provider_key,
    fetch_provider_models,
    get_local_model_command_profiles,
    get_local_model_status,
    get_provider_registry,
    get_provider_settings_view,
    resolve_provider_id,
    set_default_provider,
    stored_default_provider_entry,
    test_provider,
    update_provider_settings,
    validate_provider_model,
)
from pipeline.provider_settings_store import ProviderSettingsError
from pipeline.run_llm_job import AttachmentSource, LLMJobError, run_llm_job
from pipeline.run_markdown_job import (
    MarkdownJobError,
    rerender_job,
    run_markdown_job,
    run_pasted_text_job,
)


app = FastAPI(title="Study Guide Generator API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

THEMES = ["claude_clean"]
INPUT_MODES = ["upload_markdown", "paste_text", "generate_llm"]
STYLE_PRESETS = list(style_store.BUILTIN_STYLE_IDS)
ARTIFACTS = {
    "clean.md": ("clean_md", "text/markdown; charset=utf-8"),
    "final.html": ("final_html", "text/html; charset=utf-8"),
    "final.pdf": ("final_pdf", "application/pdf"),
    "final.docx": (
        "final_docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "validation.json": ("validation_json", "application/json"),
    "render.log": ("render_log", "text/plain; charset=utf-8"),
}
MAX_LLM_ATTACHMENTS = 5
MAX_LLM_ATTACHMENT_BYTES = 15 * 1024 * 1024

# Large-PDF preflight thresholds (read-only inspection — see
# docs/LARGE_PDF_PREFLIGHT_DESIGN.md). All env-tunable, read once at import,
# following the os.getenv precedent in pipeline/run_llm_job.py. These are ADVISORY
# warn thresholds only; they do NOT change the hard upload ceiling
# (MAX_LLM_ATTACHMENT_BYTES) that preflight reuses as its size guard.
PREFLIGHT_SAMPLE_PAGES = int(os.getenv("PREFLIGHT_SAMPLE_PAGES", "20"))
PREFLIGHT_WARN_PAGES = int(os.getenv("PREFLIGHT_WARN_PAGES", "80"))
PREFLIGHT_WARN_SIZE_MB = float(os.getenv("PREFLIGHT_WARN_SIZE_MB", "25"))
PREFLIGHT_OCR_PAGE_LIMIT = int(os.getenv("PREFLIGHT_OCR_PAGE_LIMIT", "60"))
PREFLIGHT_DEFAULT_FIRST_N = int(os.getenv("PREFLIGHT_DEFAULT_FIRST_N", "20"))
PREFLIGHT_IMAGE_HEAVY_RATIO = float(os.getenv("PREFLIGHT_IMAGE_HEAVY_RATIO", "0.85"))
PREFLIGHT_TEXT_RATIO = float(os.getenv("PREFLIGHT_TEXT_RATIO", "0.15"))

# Export bundle selectors -> (artifact filename, availability key). Only these
# artifacts may ever be bundled; raw source, attachments, and .env are never
# exposed. render.log is included only when explicitly selected.
EXPORT_ARTIFACTS: dict[str, tuple[str, str]] = {
    "pdf": ("final.pdf", "final_pdf"),
    "docx": ("final.docx", "final_docx"),
    "markdown": ("clean.md", "clean_md"),
    "html": ("final.html", "final_html"),
    "validation": ("validation.json", "validation_json"),
    "render_log": ("render.log", "render_log"),
}
EXPORT_ARTIFACT_ALIASES = {
    "pdf": "pdf",
    "docx": "docx",
    "final.docx": "docx",
    "word": "docx",
    "md": "markdown",
    "markdown": "markdown",
    "clean.md": "markdown",
    "html": "html",
    "final.html": "html",
    "validation": "validation",
    "validation.json": "validation",
    "log": "render_log",
    "render_log": "render_log",
    "render.log": "render_log",
}
MAX_BUNDLE_JOBS = 100

# The visible "mode" control was removed from the Builder (Styles now define guide
# type). Templates still contain a {mode} placeholder, so we keep accepting mode
# for request compatibility and default it to this stable value.
DEFAULT_MODE = "study_guide"

MAX_OUTLINE_SECTIONS = 50
MAX_OUTLINE_TITLE_CHARS = 200
MAX_OUTLINE_INSTRUCTION_CHARS = 600

# Large-PDF page-selection plumbing (Slice 3, see docs/LARGE_PDF_PREFLIGHT_DESIGN.md
# §5). These bound the optional per-file page-range map so it can never become an
# unbounded input. NOTE: this slice only *plumbs and persists* the selection —
# extraction still ignores it (no page filtering yet).
MAX_PAGE_SELECTION_FILES = 20
MAX_PAGE_RANGES_PER_FILE = 50


class PasteJobRequest(BaseModel):
    text: str
    theme: str = "claude_clean"
    strict_math: bool = True
    folder_id: str | None = None


class OutlineSection(BaseModel):
    title: str = ""
    instructions: str = ""


class OutlineData(BaseModel):
    enabled: bool = False
    sections: list[OutlineSection] = []


class LLMJobRequest(BaseModel):
    source_text: str
    title: str = "Generated Study Guide"
    mode: str = DEFAULT_MODE
    prompt_name: str = "basic_study_guide"
    generator_preset: str | None = None
    provider: str
    model: str
    theme: str = "claude_clean"
    strict_math: bool = True
    # None ⇒ "not explicitly set": the provider-settings thinking_default fills it
    # (qwen only), falling back to True. An explicit true/false from the request
    # still wins. With no store this resolves to True ⇒ unchanged behavior.
    qwen_thinking: bool | None = None
    folder_id: str | None = None
    outline: OutlineData | None = None
    # Optional output-section toggles (dict-of-bool, e.g. {"glossary": true}).
    # Unknown keys are ignored downstream by the orchestrator whitelist; an unset
    # or empty map adds no new prompt fragments (default behaviour unchanged).
    include_sections: dict[str, bool] = {}
    # Optional global generation-directive axes (C2). These MODIFY overall
    # behaviour (how deep / how it is pitched) rather than ADD sections. Each is an
    # optional scalar enum validated at the handler; unset adds no prompt fragments.
    # Voice/tone is intentionally NOT an axis here — it stays owned by Styles.
    output_depth: str | None = None
    difficulty: str | None = None
    # Optional per-file PDF page selection (Slice 3). Shape: filename -> list of
    # [start, end] ranges, 1-based inclusive (e.g. {"deck.pdf": [[1, 20], [35, 42]]}).
    # Absent/empty == "all pages" == current behaviour. Validated + normalized by
    # _normalize_page_selections at the handler (kept loose here so we control the
    # error, mirroring how include_sections is handled on the multipart path).
    # PERSISTED ONLY this slice — _extract_pdf still ignores it (no page filtering).
    page_selections: dict[str, Any] = {}


class OutlineGenerateRequest(BaseModel):
    source_text: str = ""
    title: str = ""
    provider: str | None = None
    model: str | None = None


class StyleCreateRequest(BaseModel):
    name: str
    description: str = ""
    content: str
    base_style: str | None = None
    tags: list[str] = []


class StyleUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    tags: list[str] | None = None


class StyleGenerateRequest(BaseModel):
    description: str
    base_style: str | None = None
    provider: str | None = None
    model: str | None = None


class FolderCreateRequest(BaseModel):
    name: str
    color: str | None = None


class FolderUpdateRequest(BaseModel):
    name: str | None = None
    color: str | None = None
    sort_order: int | None = None


class MoveJobRequest(BaseModel):
    folder_id: str | None = None


class FavoriteRequest(BaseModel):
    value: bool


class BatchMoveRequest(BaseModel):
    job_ids: list[str]
    folder_id: str | None = None


class BulkJobsRequest(BaseModel):
    """Body for /api/jobs/bulk/{delete,restore}: a list of job ids."""

    ids: list[str] = []


class BulkMoveRequest(BaseModel):
    """Body for /api/jobs/bulk/move. Folder field matches the existing single/
    batch move contract (``folder_id``), not ``folder``."""

    ids: list[str] = []
    folder_id: str | None = None


class BundleRequest(BaseModel):
    job_ids: list[str]
    artifacts: list[str] = ["pdf"]


class RerenderRequest(BaseModel):
    theme: str | None = None


class EditCleanMdRequest(BaseModel):
    text: str


class SectionRegenerateRequest(BaseModel):
    action: str
    instruction: str = ""
    provider: str | None = None
    model: str | None = None
    qwen_thinking: bool = True


class QuizRequest(BaseModel):
    question_types: list[str] = ["mcq", "flashcards"]
    count: int = 25
    difficulty: str = "medium"
    focus: str = "all"
    section_indices: list[int] | None = None
    provider: str | None = None
    model: str | None = None
    qwen_thinking: bool = True


VALID_QUESTION_TYPES = {"mcq", "true_false", "fill_blank", "short_answer", "flashcards"}
VALID_QUIZ_COUNTS = {10, 25, 50, 100}
VALID_DIFFICULTIES = {"easy", "medium", "exam"}
VALID_FOCUS = {"definitions", "formulas", "examples", "all"}
VALID_EXPORT_FORMATS = {"csv", "anki_tsv", "quizlet"}


SECTION_REGEN_ACTIONS: dict[str, str] = {
    "simplify": "Simplify this section using plainer language and fewer details, keeping all key facts.",
    "expand": "Expand this section with more detail, examples, and thorough explanations.",
    "add_mcqs": "Add 5–8 multiple-choice questions (with answers) at the end of this section.",
    "summarize": "Replace the section body with a concise bullet-point summary, keeping the heading.",
    "exam_notes": "Rewrite this section as tight bullet-point exam notes, keeping the heading.",
    "expand_formulas": "Expand each formula with a worked example and a step-by-step derivation.",
}


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/options")
def options() -> dict[str, Any]:
    provider_details = get_provider_registry()
    return {
        "themes": THEMES,
        "input_modes": INPUT_MODES,
        "styles": STYLE_PRESETS,
        "generator_presets": generator_presets.list_generator_presets(),
        "providers": [provider["display_name"] for provider in provider_details],
        "models": {
            provider["display_name"]: provider["available_models"]
            for provider in provider_details
        },
        "provider_details": provider_details,
        "providers_v2": provider_details,
    }


# ── Provider settings (Slice 1 — backend store + safe endpoints) ─────────────
# Raw API keys are write-only and never returned. All responses go through the
# single redacting serializer in provider_config (no key field by construction).

def _resolve_known_provider(provider: str) -> str:
    provider_id = resolve_provider_id(provider)
    if provider_id not in provider_settings_store.KNOWN_PROVIDER_IDS:
        raise HTTPException(status_code=400, detail="Unsupported provider.")
    return provider_id


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object.")
    return data


@app.get("/api/provider-settings")
def get_provider_settings() -> dict[str, Any]:
    return get_provider_settings_view()


@app.patch("/api/provider-settings")
async def patch_provider_defaults(request: Request) -> dict[str, Any]:
    body = await _json_body(request)
    if "default_provider" in body:
        try:
            return set_default_provider(body.get("default_provider"))
        except ProviderSettingsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_provider_settings_view()


@app.patch("/api/provider-settings/{provider}")
async def patch_provider_settings(provider: str, request: Request) -> dict[str, Any]:
    provider_id = _resolve_known_provider(provider)
    body = await _json_body(request)
    try:
        return update_provider_settings(provider_id, body)
    except ProviderSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/provider-settings/{provider}/clear-key")
def clear_provider_settings_key(provider: str) -> dict[str, Any]:
    provider_id = _resolve_known_provider(provider)
    try:
        return clear_provider_key(provider_id)
    except ProviderSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/provider-settings/{provider}/test")
async def test_provider_settings(provider: str) -> dict[str, Any]:
    provider_id = _resolve_known_provider(provider)
    return await run_in_threadpool(test_provider, provider_id)


@app.post("/api/provider-settings/{provider}/fetch-models")
async def fetch_provider_settings_models(provider: str) -> dict[str, Any]:
    # Read-only model discovery (Slice 4): hits the provider's /models endpoint and
    # returns the ids only. Never persists, never returns a raw key; unknown
    # provider → 400 via _resolve_known_provider.
    provider_id = _resolve_known_provider(provider)
    return await run_in_threadpool(fetch_provider_models, provider_id)


@app.get("/api/local-model/status")
async def local_model_status() -> dict[str, Any]:
    # Local Model Manager — detection-only status (LMM Slice 2). Read-only: probes
    # the configured local server's /models with a fail-fast timeout and returns a
    # safe DTO (no raw key, host-only URL, offline normalized to local_offline). It
    # spawns nothing, browses no files, and writes no config — provider settings
    # remain the single config writer. `ok` reflects only that this request
    # succeeded; the server's live state is in `reachable`/`error`.
    return await run_in_threadpool(get_local_model_status)


@app.post("/api/local-model/check")
async def local_model_check() -> dict[str, Any]:
    # Refresh action — same read-only probe as GET /status (the status endpoint
    # already does the live network round-trip). Kept as a thin POST alias so the
    # frontend "Refresh" verb is explicit; it adds no new behavior or writer.
    return await run_in_threadpool(get_local_model_status)


@app.get("/api/local-model/command-profile")
async def local_model_command_profile() -> dict[str, Any]:
    # Local Model Manager — command-helper profiles (LMM Slice 4). Returns static,
    # read-only `llama-server` start-command templates the OPERATOR copies and runs
    # MANUALLY on the host. This is a display helper only: the app NEVER executes it
    # (no subprocess / spawn anywhere). The command is built from a fixed flag
    # whitelist with a model PLACEHOLDER — no request input, no host filesystem read,
    # no GGUF scan, no raw key, no full URL. Read-only: writes nothing.
    return await run_in_threadpool(get_local_model_command_profiles)


@app.get("/api/styles")
def list_styles() -> dict[str, Any]:
    return style_store.list_styles()


@app.get("/api/styles/{style_id}")
def get_style(style_id: str) -> dict[str, Any]:
    try:
        return style_store.get_style(style_id)
    except style_store.StyleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except style_store.StyleStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/styles")
def create_style(request: StyleCreateRequest) -> dict[str, Any]:
    try:
        return style_store.create_custom_style(
            name=request.name,
            description=request.description,
            content=request.content,
            base_style=request.base_style,
            tags=request.tags,
        )
    except style_store.StyleStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/styles/{style_id}")
def update_style(style_id: str, request: StyleUpdateRequest) -> dict[str, Any]:
    try:
        return style_store.update_custom_style(
            style_id,
            name=request.name,
            description=request.description,
            content=request.content,
            tags=request.tags,
        )
    except style_store.StyleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except style_store.StyleStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/styles/{style_id}")
def delete_style(style_id: str) -> dict[str, bool]:
    try:
        style_store.delete_custom_style(style_id)
    except style_store.StyleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except style_store.StyleStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/styles/generate")
def generate_style(request: StyleGenerateRequest) -> dict[str, Any]:
    description = request.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="description must not be empty.")

    provider_id, fallback_model = _pick_generate_provider(request.provider)
    model_choice = (request.model or "").strip() or fallback_model or "Use environment default"

    base_content: str | None = None
    if request.base_style:
        try:
            base_content = style_store.resolve_prompt_text(request.base_style)
        except style_store.StyleNotFoundError:
            base_content = None

    try:
        config = build_provider_config(provider_id, model_choice, qwen_thinking_enabled=True)
        messages = _build_style_generation_messages(description, base_content)
        raw = generate_chat_completion(messages, config)
    except MissingLLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Style generation failed: {exc}") from exc

    draft = _parse_style_draft(raw, description)
    draft["provider"] = provider_id
    draft["model"] = config.model
    draft["base_style"] = request.base_style if request.base_style in style_store.BUILTIN_STYLES else None
    return draft


def _pick_generate_provider(provider: str | None) -> tuple[str, str]:
    registry = get_provider_registry(discover_local=False)
    if provider:
        provider_id = resolve_provider_id(provider)
        entry = next((item for item in registry if item["id"] == provider_id), None)
        if entry is None:
            raise HTTPException(status_code=400, detail="Unsupported provider.")
        if not entry["configured"]:
            raise HTTPException(
                status_code=400,
                detail=f"{entry['display_name']} is not configured on the server.",
            )
        return entry["id"], entry.get("default_model") or ""

    # No per-request provider: honor the stored provider-settings default_provider
    # when it resolves to a known, configured provider. This is a DEFAULT only — it
    # sits BELOW an explicit per-request provider (handled above) and ABOVE the
    # first-configured fallback (below). An unset/unknown/unconfigured stored default
    # returns None and falls straight through to the historical first-configured
    # behavior. The model returned is that provider's effective default_model
    # (store → env → built-in), which the caller still overrides with any per-request
    # model.
    default_entry = stored_default_provider_entry(registry)
    if default_entry is not None:
        return default_entry["id"], default_entry.get("default_model") or ""

    entry = next((item for item in registry if item["configured"]), None)
    if entry is None:
        raise HTTPException(
            status_code=400,
            detail="No LLM provider is configured on the server. Add a provider API key to enable style generation.",
        )
    return entry["id"], entry.get("default_model") or ""


def _build_style_generation_messages(description: str, base_content: str | None) -> list[dict]:
    system = (
        "You are an expert prompt engineer. You design reusable instruction TEMPLATES. "
        "Another AI model will later fill the template with a specific source document and "
        "produce a Markdown study guide. You never write the study guide yourself; you only "
        "write the instruction template."
    )
    parts = [
        "Write a study-guide generation prompt template for the following requested style:",
        "",
        description,
        "",
    ]
    if base_content:
        parts += [
            "Use this existing template as a structural reference (adapt it, do not copy verbatim):",
            "",
            "```",
            base_content.strip(),
            "```",
            "",
        ]
    parts += [
        "Rules for the template you write:",
        "- It MUST contain these literal placeholders, each exactly once: {title}, {mode}, and {source}.",
        "- {source} must appear near the end, where the source document will be injected.",
        "- Instruct the assistant to output valid Markdown only and to start with `# {title}`.",
        "- Instruct the assistant to use dollar-delimited LaTeX: $...$ for inline math and $$...$$ for display math.",
        "- Do not include any real document content — only instructions and section scaffolding.",
        "",
        "Respond with a single JSON object and nothing else, using exactly these keys:",
        '- "name": a short human title for the style (<= 60 characters)',
        '- "description": one sentence describing the style',
        '- "prompt": the full template text as a single string',
    ]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]


def _parse_style_draft(raw: str, description: str) -> dict[str, Any]:
    text = (raw or "").strip()
    candidates: list[str] = []
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])
    candidates.append(text)

    parsed: dict[str, Any] | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            parsed = data
            break

    if parsed and isinstance(parsed.get("prompt"), str) and parsed["prompt"].strip():
        name = str(parsed.get("name") or "").strip() or _fallback_style_name(description)
        draft_description = str(parsed.get("description") or "").strip()
        content = parsed["prompt"].strip()
    else:
        name = _fallback_style_name(description)
        draft_description = ""
        content = text

    return {
        "name": name[:120],
        "description": draft_description[:600],
        "content": content,
        "missing_placeholders": style_store.missing_placeholders(content),
    }


def _fallback_style_name(description: str) -> str:
    words = description.strip().split()
    name = " ".join(words[:6]).strip(" .,:;")
    return (name or "Custom Style").title()[:60]


@app.get("/api/presets")
def list_presets() -> dict[str, Any]:
    return {"presets": preset_store.list_presets()}


@app.post("/api/presets/{preset_id}/apply")
def apply_preset(preset_id: str) -> dict[str, Any]:
    applied = preset_store.apply_preset(preset_id)
    if applied is None:
        raise HTTPException(status_code=404, detail="Unknown preset.")
    return applied


@app.post("/api/outline/generate")
def generate_outline(request: OutlineGenerateRequest) -> dict[str, Any]:
    topic = (request.source_text or request.title or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Provide a topic or source text to outline.")

    provider_id, fallback_model = _pick_generate_provider(request.provider)
    model_choice = (request.model or "").strip() or fallback_model or "Use environment default"

    try:
        config = build_provider_config(provider_id, model_choice, qwen_thinking_enabled=True)
        messages = _build_outline_messages(topic[:8000], request.title.strip())
        raw = generate_chat_completion(messages, config)
    except MissingLLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Outline generation failed: {exc}") from exc

    sections = _parse_outline_draft(raw)
    if not sections:
        raise HTTPException(status_code=502, detail="The model did not return a usable outline. Try again.")
    return {"sections": sections, "provider": provider_id, "model": config.model}


def _build_outline_messages(topic: str, title: str) -> list[dict]:
    system = (
        "You design study-guide OUTLINES. You output only a JSON array of section "
        "objects — you never write the guide content itself."
    )
    parts = [
        "Create a concise outline for a study guide.",
        f"Guide title: {title}" if title else "",
        "",
        "Topic / source material:",
        topic,
        "",
        "Rules:",
        "- Return 6 to 9 sections covering the topic in a sensible teaching order.",
        '- Each section is a JSON object with "title" (<= 8 words) and "instructions" '
        "(one short sentence on what that section should cover).",
        "- Do NOT write the actual guide content. Titles + one-line instructions only.",
        "",
        'Respond with a single JSON array and nothing else, e.g. '
        '[{"title": "Big Picture", "instructions": "Explain the core idea simply."}]',
    ]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(part for part in parts if part is not None)},
    ]


def _parse_outline_draft(raw: str) -> list[dict[str, str]]:
    text = (raw or "").strip()
    candidates: list[str] = []
    fenced = re.search(r"```(?:json)?\s*([\[{].*[\]}])\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))
    open_sq, close_sq = text.find("["), text.rfind("]")
    if open_sq != -1 and close_sq != -1 and close_sq > open_sq:
        candidates.append(text[open_sq : close_sq + 1])
    open_br, close_br = text.find("{"), text.rfind("}")
    if open_br != -1 and close_br != -1 and close_br > open_br:
        candidates.append(text[open_br : close_br + 1])
    candidates.append(text)

    items: list[Any] | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            items = parsed
            break
        if isinstance(parsed, dict) and isinstance(parsed.get("sections"), list):
            items = parsed["sections"]
            break

    sections: list[dict[str, str]] = []
    for item in (items or [])[:MAX_OUTLINE_SECTIONS]:
        if isinstance(item, str):
            title, instructions = item, ""
        elif isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or "")
            instructions = str(
                item.get("instructions") or item.get("instruction") or item.get("description") or ""
            )
        else:
            continue
        title = " ".join(title.split())[:MAX_OUTLINE_TITLE_CHARS]
        if not title:
            continue
        sections.append({"title": title, "instructions": instructions.strip()[:MAX_OUTLINE_INSTRUCTION_CHARS]})
    return sections


@app.get("/api/jobs")
def list_jobs(limit: int = 20) -> dict[str, Any]:
    jobs = []
    if JOBS_DIR.exists():
        folders_by_id = {folder["id"]: folder for folder in library_store.list_folders()}
        for manifest_path in JOBS_DIR.glob("*/job.json"):
            manifest = _read_json(manifest_path)
            if manifest is None:
                continue
            job_id = str(manifest.get("id") or manifest_path.parent.name)
            safe_manifest = _safe_manifest(manifest)
            jobs.append(
                {
                    **safe_manifest,
                    "id": job_id,
                    "attachment_summary": _attachment_summary(safe_manifest),
                    "artifact_availability": _artifact_availability(Job(job_id)),
                    **_folder_meta(job_id, folders_by_id),
                }
            )

    # Newest first, then float favorites to the top. The second sort is stable, so
    # newest-first order is preserved within the favorite and non-favorite groups.
    jobs.sort(
        key=lambda item: str(item.get("created_at") or item.get("id") or ""),
        reverse=True,
    )
    jobs.sort(key=lambda item: not bool(item.get("favorite")))
    return {"jobs": jobs[: max(limit, 0)]}


# ──────────────────────────────────────────────────────────────────────────────
# Ask Your Guide — context inventory (Ask Slice 2, read-only).
#
# Registered here (well before the SPA mount and the parametric /api/jobs/{job_id}
# catch-all — different prefix, so no capture conflict). These endpoints expose a
# SAFE, read-only inventory of generated guides so a future Ask Your Guide
# workspace can pick a guide and see what context is available. They read job
# artifacts (clean.md / extracted.txt / manifest) ONLY, never write, never call a
# model, and reuse the existing manifest/attachment redaction helpers — so no raw
# key, full base URL, filesystem path, or artifact body is ever exposed. They do
# NOT chunk, index, retrieve, create jobs, or touch save_clean_md.
# ──────────────────────────────────────────────────────────────────────────────


def _ask_job_summary(manifest: dict[str, Any], job: Job) -> dict[str, Any]:
    """Curated, redacted summary row for the Ask guide picker.

    Builds on the same ``_safe_manifest`` redaction the job listing uses, then
    emits only an explicit whitelist of display-safe fields (no raw key, no full
    URL, no filesystem path can ride along because nothing is passed through
    verbatim)."""
    safe = _safe_manifest(manifest)
    job_id = str(manifest.get("id") or job.id)
    return {
        "id": job_id,
        "title": safe.get("title"),
        "status": safe.get("status"),
        "created_at": safe.get("created_at"),
        "updated_at": safe.get("updated_at"),
        "style": safe.get("prompt_name"),
        "generator_preset": safe.get("generator_preset"),
        "provider": safe.get("provider"),
        "model": safe.get("model"),
        "favorite": bool(safe.get("favorite")),
        "attachment_summary": _attachment_summary(manifest),
        "guide_available": True,
        "source_available": job.extracted_txt.exists(),
    }


@app.get("/api/ask/jobs")
def list_ask_jobs(limit: int = 50) -> dict[str, Any]:
    """List ONLY Ask-eligible jobs: those with a generated guide (clean.md).

    Reuses the existing job manifest listing; a guide-less / failed / incomplete
    job (no clean.md) is filtered out rather than returned as ineligible."""
    jobs: list[dict[str, Any]] = []
    if JOBS_DIR.exists():
        for manifest_path in JOBS_DIR.glob("*/job.json"):
            manifest = _read_json(manifest_path)
            if manifest is None:
                continue
            job_id = str(manifest.get("id") or manifest_path.parent.name)
            job = Job(job_id)
            if not ask_inventory.has_generated_guide(job):
                continue
            jobs.append(_ask_job_summary(manifest, job))

    # Newest first, then float favorites to the top (mirrors /api/jobs ordering).
    jobs.sort(
        key=lambda item: str(item.get("created_at") or item.get("id") or ""),
        reverse=True,
    )
    jobs.sort(key=lambda item: not bool(item.get("favorite")))
    return {"jobs": jobs[: max(limit, 0)]}


@app.get("/api/ask/jobs/{job_id}/context")
def get_ask_job_context(job_id: str) -> dict[str, Any]:
    """Read-only readiness + source inventory for ONE job (404 if unknown).

    Summarizes the generated guide, extracted source, and attachment metadata,
    plus a readiness object for future Ask prep. Returns counts/booleans only —
    never the guide/source body, never a key/URL/path."""
    job = _get_job(job_id)
    manifest = job.read_manifest()
    safe = _safe_manifest(manifest)

    guide = ask_inventory.guide_inventory(job)
    source = ask_inventory.source_inventory(job)

    reasons: list[str] = []
    if not guide["clean_md_present"]:
        reasons.append("No generated guide (clean.md) is available for this job yet.")
    ready = bool(guide["clean_md_present"])

    return {
        "id": job.id,
        "title": safe.get("title"),
        "status": safe.get("status"),
        "style": safe.get("prompt_name"),
        "generator_preset": safe.get("generator_preset"),
        "provider": safe.get("provider"),
        "model": safe.get("model"),
        "guide": guide,
        "source": source,
        "attachments": _safe_attachment_metadata(manifest.get("attachments", [])),
        "attachment_summary": _attachment_summary(manifest),
        "page_selections": _safe_page_selections(manifest.get("page_selections")),
        "readiness": {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "reasons": reasons,
        },
    }


@app.post("/api/ask/jobs/{job_id}/prepare")
def prepare_ask_job_context(job_id: str) -> dict[str, Any]:
    """Build/refresh the Ask chunk index for ONE job (404 if unknown).

    Idempotent: an unchanged guide+source returns a cache ``hit`` without
    rewriting anything; a content change rebuilds. A guide-less but existing
    job returns 200 ``ready:false`` (mirroring the Slice 2 context endpoint),
    never a 404. Builds/reads ONLY ``clean.md`` + ``extracted.txt`` and writes
    only the job-local Ask cache — it never calls a model, reads a key, or
    mutates the original artifacts/manifest.

    The response is an explicit whitelist of counts + a citation summary; it
    never returns guide/source body text, chunk text, keys, URLs, or host
    paths (only a job-relative cache path)."""
    job = _get_job(job_id)
    result = ask_context.prepare_context(job)

    if not result.get("ready"):
        return {
            "job_id": job.id,
            "ready": False,
            "cache_status": result.get("cache_status", "skipped"),
            "reason": result.get("reason"),
        }

    return {
        "job_id": job.id,
        "ready": True,
        "cache_status": result["cache_status"],
        "content_hash": result["content_hash"],
        "guide_chunk_count": result["guide_chunk_count"],
        "source_chunk_count": result["source_chunk_count"],
        "total_chunk_count": result["total_chunk_count"],
        "citation_summary": result["citation_summary"],
        "cache_relpath": result["cache_relpath"],
    }


@app.get("/api/library")
def get_library(
    q: str | None = None,
    folder_id: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    style: str | None = None,
    has_attachments: bool | None = None,
    has_warnings: bool | None = None,
    sort: str = "newest",
) -> dict[str, Any]:
    jobs = _all_library_jobs()
    folders = _library_folders_with_counts(jobs)
    filtered = _filter_library_jobs(
        jobs,
        q=q,
        folder_id=folder_id,
        status=status,
        provider=provider,
        style=style,
        has_attachments=has_attachments,
        has_warnings=has_warnings,
    )
    filtered = _sort_library_jobs(filtered, sort)
    return {"folders": folders, "jobs": filtered, "sort": sort}


@app.get("/api/library/folders")
def list_library_folders() -> dict[str, Any]:
    return {"folders": _library_folders_with_counts(_all_library_jobs())}


@app.post("/api/library/folders")
def create_library_folder(request: FolderCreateRequest) -> dict[str, Any]:
    try:
        return library_store.create_folder(name=request.name, color=request.color)
    except library_store.LibraryStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/library/folders/{folder_id}")
def update_library_folder(folder_id: str, request: FolderUpdateRequest) -> dict[str, Any]:
    try:
        return library_store.update_folder(
            folder_id,
            name=request.name,
            color=request.color,
            sort_order=request.sort_order,
        )
    except library_store.FolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except library_store.LibraryStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/library/folders/{folder_id}")
def delete_library_folder(folder_id: str) -> dict[str, Any]:
    try:
        reassigned = library_store.delete_folder(folder_id)
    except library_store.FolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except library_store.LibraryStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "reassigned": reassigned}


@app.post("/api/library/jobs/move")
def batch_move_library_jobs(request: BatchMoveRequest) -> dict[str, Any]:
    valid_ids: list[str] = []
    for jid in request.job_ids:
        try:
            valid_ids.append(_get_job(jid).id)
        except HTTPException:
            continue
    try:
        moved = library_store.move_jobs(valid_ids, request.folder_id)
    except library_store.FolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except library_store.LibraryStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "moved": moved}


@app.post("/api/library/jobs/{job_id}/move")
def move_library_job(job_id: str, request: MoveJobRequest) -> dict[str, Any]:
    job = _get_job(job_id)
    try:
        folder = library_store.move_job(job.id, request.folder_id)
    except library_store.FolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except library_store.LibraryStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "job_id": job.id, "folder_id": folder}


# ── Shortcuts (Home launcher registry) ───────────────────────────────────────

def _guard_shortcut_id(shortcut_id: str) -> str:
    """Reject path-traversal-ish ids before they reach the store (like jobs)."""
    if "/" in shortcut_id or "\\" in shortcut_id or shortcut_id in {"", ".", ".."}:
        raise HTTPException(status_code=404, detail="Shortcut not found.")
    return shortcut_id


def _shortcut_error(exc: Exception) -> HTTPException:
    if isinstance(exc, shortcut_store.ShortcutNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, shortcut_store.ShortcutStoreError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail="Invalid shortcut request.")


@app.get("/api/shortcuts")
def list_shortcuts_route() -> dict[str, Any]:
    return {"shortcuts": shortcut_store.list_shortcuts()}


@app.get("/api/shortcuts/export")
def export_shortcuts_route() -> dict[str, Any]:
    return shortcut_store.export_all()


@app.post("/api/shortcuts")
def create_shortcut_route(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return shortcut_store.create_shortcut(body)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.post("/api/shortcuts/reorder")
def reorder_shortcuts_route(body: dict[str, Any]) -> dict[str, Any]:
    items = body.get("items") if isinstance(body, dict) else None
    try:
        return {"shortcuts": shortcut_store.reorder_shortcuts(items)}
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.post("/api/shortcuts/defaults/reset")
def reset_shortcuts_route() -> dict[str, Any]:
    return {"shortcuts": shortcut_store.reset_defaults()}


@app.post("/api/shortcuts/import/preview")
async def preview_import_shortcuts_route(request: Request) -> dict[str, Any]:
    data, overwrite = await _read_shortcut_import(request)
    try:
        return shortcut_store.preview_import(data, overwrite=overwrite)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.post("/api/shortcuts/import")
async def import_shortcuts_route(request: Request) -> dict[str, Any]:
    data, overwrite = await _read_shortcut_import(request)
    try:
        return shortcut_store.import_shortcuts(data, overwrite=overwrite)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


async def _read_shortcut_import(request: Request) -> tuple[Any, bool]:
    """Parse an import body that may be a single shortcut, a list, or an envelope.

    An optional top-level ``overwrite`` flag on an envelope controls conflict
    handling; absent it, conflicting ids get a fresh id (never overwrite).
    """
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON.") from exc
    overwrite = bool(isinstance(payload, dict) and payload.get("overwrite"))
    return payload, overwrite


@app.get("/api/shortcuts/{shortcut_id}")
def get_shortcut_route(shortcut_id: str) -> dict[str, Any]:
    _guard_shortcut_id(shortcut_id)
    try:
        return shortcut_store.get_shortcut(shortcut_id)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.put("/api/shortcuts/{shortcut_id}")
def update_shortcut_route(shortcut_id: str, body: dict[str, Any]) -> dict[str, Any]:
    _guard_shortcut_id(shortcut_id)
    try:
        return shortcut_store.update_shortcut(shortcut_id, body)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.delete("/api/shortcuts/{shortcut_id}")
def delete_shortcut_route(shortcut_id: str) -> dict[str, bool]:
    _guard_shortcut_id(shortcut_id)
    try:
        shortcut_store.delete_shortcut(shortcut_id)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc
    return {"ok": True}


@app.get("/api/shortcuts/{shortcut_id}/export")
def export_shortcut_route(shortcut_id: str) -> dict[str, Any]:
    _guard_shortcut_id(shortcut_id)
    try:
        return shortcut_store.export_shortcut(shortcut_id)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.get("/api/shortcuts/{shortcut_id}/inspect")
def inspect_shortcut_route(shortcut_id: str) -> dict[str, Any]:
    # Read-only shortcut inspector (Slice 1): legacy valid/reason + the richer
    # validity object + live, redacted repair candidates. No mutation, no repair
    # apply. Unknown id -> 404 via _shortcut_error.
    _guard_shortcut_id(shortcut_id)
    try:
        return shortcut_store.inspect_shortcut(shortcut_id)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.post("/api/shortcuts/{shortcut_id}/repair/preview")
def repair_preview_shortcut_route(shortcut_id: str, body: dict[str, Any]) -> dict[str, Any]:
    # Repair preview (Slice 3A) — READ-ONLY. Returns the proposed shortcut +
    # diff + resulting validity without writing shortcuts.json. Unknown id ->
    # 404; bad/invalid repair request -> 400 (both via _shortcut_error).
    _guard_shortcut_id(shortcut_id)
    try:
        return shortcut_store.preview_repair(shortcut_id, body)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.post("/api/shortcuts/{shortcut_id}/repair/apply")
def repair_apply_shortcut_route(shortcut_id: str, body: dict[str, Any]) -> dict[str, Any]:
    # Repair apply (Slice 3A) — the ONLY write. in_place updates via the existing
    # update_shortcut; clone creates a new shortcut via create_shortcut (original
    # untouched). Reuses the store's whitelist + atomic write. No raw keys.
    _guard_shortcut_id(shortcut_id)
    try:
        return shortcut_store.apply_repair(shortcut_id, body)
    except shortcut_store.ShortcutStoreError as exc:
        raise _shortcut_error(exc) from exc


@app.get("/api/exports")
def get_exports(
    q: str | None = None,
    folder_id: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    style: str | None = None,
    artifact: str | None = None,
    has_attachments: bool | None = None,
    has_warnings: bool | None = None,
    sort: str = "newest",
) -> dict[str, Any]:
    jobs = _all_export_jobs()
    folders = _library_folders_with_counts(jobs)
    filtered = _filter_library_jobs(
        jobs,
        q=q,
        folder_id=folder_id,
        status=status,
        provider=provider,
        style=style,
        has_attachments=has_attachments,
        has_warnings=has_warnings,
    )
    if artifact:
        selector = EXPORT_ARTIFACT_ALIASES.get(artifact.strip().lower())
        avail_key = EXPORT_ARTIFACTS[selector][1] if selector else None
        if avail_key:
            filtered = [job for job in filtered if (job.get("artifact_availability") or {}).get(avail_key)]
    filtered = _sort_library_jobs(filtered, sort)
    return {
        "folders": folders,
        "jobs": filtered,
        "sort": sort,
        "artifact_types": list(EXPORT_ARTIFACTS.keys()),
    }


@app.post("/api/exports/bundle")
def export_bundle(request: BundleRequest) -> Response:
    if not request.job_ids:
        raise HTTPException(status_code=400, detail="Select at least one guide to export.")
    if len(request.job_ids) > MAX_BUNDLE_JOBS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_BUNDLE_JOBS} guides per bundle.")
    selectors = _normalize_export_selectors(request.artifacts)

    buffer = io.BytesIO()
    manifest_jobs: list[dict[str, Any]] = []
    total_included = 0
    used_dirs: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for raw_id in request.job_ids:
            try:
                job = _get_job(raw_id)
            except HTTPException:
                manifest_jobs.append(
                    {"job_id": str(raw_id), "found": False, "included": [], "skipped": list(selectors)}
                )
                continue
            meta = job.read_manifest()
            raw_title = meta.get("title")
            title = str(raw_title or job.id)
            # Untitled (paste/upload) jobs fall back to "guide-<id>" rather than
            # doubling the id when the slug would just be the job id.
            base_dir = _unique_bundle_dir(_safe_slug(raw_title or ""), job.id, used_dirs)
            included: list[str] = []
            skipped: list[str] = []
            for selector in selectors:
                artifact_name, _avail_key = EXPORT_ARTIFACTS[selector]
                if selector == "docx":
                    # Best-effort lazy generation; a failure just marks it skipped.
                    try:
                        _ensure_docx(job)
                    except Exception:
                        pass
                path, _media = _artifact_path(job, artifact_name)
                if path.exists() and path.is_file():
                    archive.write(path, f"{base_dir}/{artifact_name}")
                    included.append(selector)
                    total_included += 1
                else:
                    skipped.append(selector)
            manifest_jobs.append(
                {"job_id": job.id, "title": title, "found": True, "included": included, "skipped": skipped}
            )

        if total_included == 0:
            raise HTTPException(
                status_code=404,
                detail="None of the requested artifacts are available for the selected guides.",
            )

        bundle_manifest = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "artifacts_requested": selectors,
            "guides_requested": len(request.job_ids),
            "files_included": total_included,
            "jobs": manifest_jobs,
        }
        archive.writestr("manifest.json", json.dumps(bundle_manifest, indent=2, ensure_ascii=False))

    buffer.seek(0)
    filename = f"study-guides-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _all_export_jobs() -> list[dict[str, Any]]:
    """Library jobs enriched with artifact URLs + flat folder metadata.

    Same safe shape as the library list, plus per-job ``artifact_urls`` so the
    Exports Center can link/download artifacts directly. No filesystem paths.
    """
    jobs: list[dict[str, Any]] = []
    if JOBS_DIR.exists():
        folders_by_id = {folder["id"]: folder for folder in library_store.list_folders()}
        for manifest_path in JOBS_DIR.glob("*/job.json"):
            manifest = _read_json(manifest_path)
            if manifest is None:
                continue
            job_id = str(manifest.get("id") or manifest_path.parent.name)
            job_obj = Job(job_id)
            safe = _safe_manifest(manifest)
            availability = _artifact_availability(job_obj)
            folder_id = library_store.folder_id_for(job_id)
            folder = folders_by_id.get(folder_id)
            jobs.append(
                {
                    **safe,
                    "id": job_id,
                    "attachment_summary": _attachment_summary(safe),
                    "artifact_availability": availability,
                    "artifact_urls": _artifact_urls(job_obj, availability),
                    "folder_id": folder_id,
                    "folder_name": folder.get("name") if folder else None,
                    "folder_color": folder.get("color") if folder else None,
                }
            )
    return jobs


def _normalize_export_selectors(artifacts: list[str]) -> list[str]:
    if not artifacts:
        raise HTTPException(status_code=400, detail="Select at least one artifact type.")
    selectors: list[str] = []
    for raw in artifacts:
        key = EXPORT_ARTIFACT_ALIASES.get(str(raw).strip().lower())
        if key is None:
            raise HTTPException(status_code=400, detail=f"Unsupported artifact type: {raw}")
        if key not in selectors:
            selectors.append(key)
    return selectors


def _safe_slug(text: str, *, fallback: str = "guide", limit: int = 60) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", str(text or ""))
    cleaned = re.sub(r"\s+", "_", cleaned.strip()).strip("._-")
    return cleaned[:limit] or fallback


def _unique_bundle_dir(slug: str, job_id: str, used: set[str]) -> str:
    base = f"{slug}-{job_id}"
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def _clean_outline_sections(outline: OutlineData | None) -> list[tuple[str, str]]:
    """Return [(title, instructions)] for an enabled outline, sanitized + capped.

    Titles/instructions are the user's own plain text; they are injected as prompt
    text only (never executed) and trimmed to bound prompt size.
    """
    if outline is None or not outline.enabled:
        return []
    cleaned: list[tuple[str, str]] = []
    for section in outline.sections[:MAX_OUTLINE_SECTIONS]:
        title = " ".join(str(section.title or "").split())[:MAX_OUTLINE_TITLE_CHARS]
        if not title:
            continue
        instructions = str(section.instructions or "").strip()[:MAX_OUTLINE_INSTRUCTION_CHARS]
        cleaned.append((title, instructions))
    return cleaned


def _apply_outline_directive(source_text: str, outline: OutlineData | None) -> str:
    """Prepend a clear "Required Outline" directive to the source for LLM jobs.

    No-op when the outline is absent/disabled/empty, so non-outline generation is
    byte-for-byte unchanged.
    """
    sections = _clean_outline_sections(outline)
    if not sections:
        return source_text
    lines = [
        "## Required Outline",
        "",
        "Follow this section structure in the exact order given. Every numbered "
        "section below MUST appear as a heading in the study guide, in this order. "
        "Do not skip, merge, or reorder required sections. You may add brief "
        "connective text, but do not omit any required section.",
        "",
    ]
    for index, (title, instructions) in enumerate(sections, start=1):
        lines.append(f"{index}. {title}")
        if instructions:
            lines.append(f"   - {instructions}")
    lines += ["", "---", "", "## Source Material", "", source_text]
    return "\n".join(lines)


def _outline_meta(outline: OutlineData | None) -> dict[str, Any]:
    sections = _clean_outline_sections(outline)
    if not sections:
        return {}
    return {
        "outline_enabled": True,
        "outline_section_count": len(sections),
        "outline_titles": [title for title, _ in sections],
    }


def _store_outline_meta(job: Job, outline: OutlineData | None) -> None:
    meta = _outline_meta(outline)
    if meta:
        job.update(**meta)


def _outline_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    """Safe outline summary for API responses (never huge; titles capped)."""
    titles = manifest.get("outline_titles")
    safe_titles = (
        [str(title)[:MAX_OUTLINE_TITLE_CHARS] for title in titles[:MAX_OUTLINE_SECTIONS]]
        if isinstance(titles, list)
        else []
    )
    return {
        "outline_enabled": bool(manifest.get("outline_enabled")),
        "outline_section_count": int(manifest.get("outline_section_count") or len(safe_titles)),
        "outline_titles": safe_titles,
    }


def _all_library_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    if JOBS_DIR.exists():
        for manifest_path in JOBS_DIR.glob("*/job.json"):
            manifest = _read_json(manifest_path)
            if manifest is None:
                continue
            job_id = str(manifest.get("id") or manifest_path.parent.name)
            safe = _safe_manifest(manifest)
            jobs.append(
                {
                    **safe,
                    "id": job_id,
                    "attachment_summary": _attachment_summary(safe),
                    "artifact_availability": _artifact_availability(Job(job_id)),
                    "folder_id": library_store.folder_id_for(job_id),
                }
            )
    return jobs


def _library_folders_with_counts(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for job in jobs:
        fid = job.get("folder_id") or library_store.VIRTUAL_UNFILED
        counts[fid] = counts.get(fid, 0) + 1

    folders: list[dict[str, Any]] = [
        {"id": library_store.VIRTUAL_ALL, "name": "All Guides", "color": None, "system": True, "count": len(jobs)},
        {
            "id": library_store.VIRTUAL_UNFILED,
            "name": "Unfiled",
            "color": None,
            "system": True,
            "count": counts.get(library_store.VIRTUAL_UNFILED, 0),
        },
    ]
    for folder in library_store.list_folders():
        folders.append({**folder, "count": counts.get(folder["id"], 0)})
    return folders


def _job_has_warnings(job: dict[str, Any]) -> bool:
    summary = job.get("attachment_summary") or {}
    return bool(summary.get("has_warnings")) or bool(job.get("error"))


def _filter_library_jobs(
    jobs: list[dict[str, Any]],
    *,
    q: str | None,
    folder_id: str | None,
    status: str | None,
    provider: str | None,
    style: str | None,
    has_attachments: bool | None,
    has_warnings: bool | None,
) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()

    def keep(job: dict[str, Any]) -> bool:
        if folder_id and folder_id != library_store.VIRTUAL_ALL:
            if job.get("folder_id") != folder_id:
                return False
        if needle:
            haystack = " ".join(
                str(job.get(field) or "")
                for field in ("title", "id", "provider", "model", "prompt_name")
            ).lower()
            if needle not in haystack:
                return False
        if status and str(job.get("status") or "") != status:
            return False
        if provider and str(job.get("provider") or "").lower() != provider.lower():
            return False
        if style and str(job.get("prompt_name") or "") != style:
            return False
        if has_attachments is not None:
            count = int((job.get("attachment_summary") or {}).get("count") or 0)
            if has_attachments != (count > 0):
                return False
        if has_warnings is not None and has_warnings != _job_has_warnings(job):
            return False
        return True

    return [job for job in jobs if keep(job)]


def _sort_library_jobs(jobs: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    def created_key(job: dict[str, Any]) -> str:
        return str(job.get("created_at") or job.get("id") or "")

    if sort == "oldest":
        ordered = sorted(jobs, key=created_key)
    elif sort == "title":
        ordered = sorted(jobs, key=lambda job: str(job.get("title") or "").lower())
    elif sort == "status":
        ordered = sorted(jobs, key=lambda job: str(job.get("status") or ""))
    else:
        ordered = sorted(jobs, key=created_key, reverse=True)
    # Favorites float to the top regardless of the chosen sort; the stable sort
    # keeps the chosen ordering within the favorite and non-favorite groups.
    ordered.sort(key=lambda job: not bool(job.get("favorite")))
    return ordered


@app.post("/api/jobs/paste")
def create_paste_job(request: PasteJobRequest) -> dict[str, Any]:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty.")
    _validate_theme(request.theme)
    folder_target = _resolve_folder_target(request.folder_id)

    try:
        job = run_pasted_text_job(
            text,
            theme=request.theme,
            strict_math=request.strict_math,
        )
    except MarkdownJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc) from exc
    _apply_folder_assignment(job.id, folder_target)
    return job_response(job)


@app.post("/api/jobs/upload-markdown")
def create_upload_markdown_job(
    file: UploadFile = File(...),
    theme: str = Form("claude_clean"),
    strict_math: bool = Form(True),
    folder_id: str | None = Form(None),
) -> dict[str, Any]:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".md", ".markdown"}:
        raise HTTPException(status_code=400, detail="file must be .md or .markdown.")
    _validate_theme(theme)
    folder_target = _resolve_folder_target(folder_id)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="api-upload-") as tmp:
            temp_path = Path(tmp.name)
            while chunk := file.file.read(1024 * 1024):
                tmp.write(chunk)
        job = run_markdown_job(temp_path, theme=theme, strict_math=strict_math)
    except MarkdownJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        file.file.close()
    _apply_folder_assignment(job.id, folder_target)
    return job_response(job)


@app.post("/api/preflight/pdf")
async def preflight_pdf_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    """Read-only preflight of a single uploaded PDF (see
    docs/LARGE_PDF_PREFLIGHT_DESIGN.md, Slice 1).

    Inspects the PDF *before* any job is created: page count + a cheap sampled
    text-vs-scanned estimate (no OCR), returning a verdict + warnings + allowed
    actions. Creates no job, writes nothing persistent (the temp file is removed
    in ``finally``), runs no OCR, and changes no limits. Accepts PDFs only.
    """
    filename = Path(file.filename or "document.pdf").name
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Preflight only inspects PDF files.")

    temp_path: Path | None = None
    size = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="preflight-") as tmp:
            temp_path = Path(tmp.name)
            # Reuse the existing streaming size guard so preflight can't smuggle a
            # file larger than the upload ceiling. This does NOT change the limit.
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_LLM_ATTACHMENT_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{filename} exceeds the {MAX_LLM_ATTACHMENT_BYTES // (1024 * 1024)} MB upload limit.",
                    )
                tmp.write(chunk)
        report = await run_in_threadpool(
            _build_pdf_preflight_report, temp_path, filename=filename, file_size_bytes=size
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        await file.close()
    return report


@app.post("/api/jobs/llm")
async def create_llm_job(request: Request) -> dict[str, Any]:
    llm_request, attachments = await _parse_llm_request(request)
    source_text = llm_request.source_text.strip()
    title = llm_request.title.strip()
    if not source_text and attachments:
        source_text = "Use the attached source files to generate the study guide."
    if not source_text:
        raise HTTPException(status_code=400, detail="source_text must not be empty.")
    if not title:
        raise HTTPException(status_code=400, detail="title must not be empty.")
    _validate_theme(llm_request.theme)
    _validate_prompt_name(llm_request.prompt_name)
    _validate_provider_model(llm_request.provider, llm_request.model)
    _validate_generation_axes(llm_request.output_depth, llm_request.difficulty)
    # Normalize the optional PDF page selection up front (raises 400 on bad shapes).
    # Persisted on the job for future rerender/retry; extraction ignores it (Slice 3).
    page_selections = _normalize_page_selections(llm_request.page_selections)
    folder_target = _resolve_folder_target(llm_request.folder_id)
    # Prepend a "Required Outline" directive into the source so it works with any
    # style (the {source} slot is the one injection point every template shares).
    source_text = _apply_outline_directive(source_text, llm_request.outline)

    # A generator preset (when set) supplies the system prompt + sampling params and
    # takes precedence over the style; the style/prompt_name is then unused.
    preset = None
    preset_warning: str | None = None
    if llm_request.generator_preset:
        _validate_generator_preset(llm_request.generator_preset)
        preset = generator_presets.get_generator_preset(llm_request.generator_preset)
        if resolve_provider_id(llm_request.provider) != preset["provider"]:
            preset_warning = (
                f"{preset['name']} is tuned for {preset['model_hint']}; you're running "
                f"it on a different provider. It will still work, but the model-specific "
                f"tuning may not fully apply."
            )

    try:
        if preset is not None:
            config = build_provider_config(
                llm_request.provider,
                llm_request.model,
                qwen_thinking_enabled=preset["thinking"],
                temperature_override=preset["temperature"],
                top_p=preset["top_p"],
                max_tokens=preset["max_tokens"],
            )
        else:
            config = build_provider_config(
                llm_request.provider,
                llm_request.model,
                qwen_thinking_enabled=llm_request.qwen_thinking,
            )
        # run_llm_job is blocking (LLM call + subprocess rendering); offload it
        # to a worker thread so it doesn't stall the asyncio event loop.
        job = await run_in_threadpool(
            run_llm_job,
            source_text,
            title=title,
            mode=(llm_request.mode or DEFAULT_MODE),
            prompt_name=llm_request.prompt_name,
            generator_preset=llm_request.generator_preset,
            include_sections=llm_request.include_sections,
            output_depth=llm_request.output_depth,
            difficulty=llm_request.difficulty,
            theme=llm_request.theme,
            strict_math=llm_request.strict_math,
            config=config,
            attachments=attachments,
            page_selections=page_selections,
        )
    except MissingLLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc) from exc
    finally:
        for attachment in attachments:
            attachment.path.unlink(missing_ok=True)
    _apply_folder_assignment(job.id, folder_target)
    _store_outline_meta(job, llm_request.outline)
    response = job_response(job)
    if preset_warning:
        response["generator_preset_warning"] = preset_warning
    return response


# ── Bulk job actions (Library multi-select backend) ──────────────────────────
# These reuse the SAME single-item internals (trash_job / restore_job /
# library_store.move_job) so there is exactly one trash path, one path guard,
# and one folder-persistence model. Every endpoint returns partial-success
# results and never aborts the whole batch because one id is bad.
#
# IMPORTANT ordering: these literal /api/jobs/bulk/* routes MUST be registered
# BEFORE the parametric /api/jobs/{job_id}/restore (and friends) below, or
# "/api/jobs/bulk/restore" would be captured with job_id="bulk". They are also,
# of course, before the catch-all /api/jobs/{job_id}.


def _dedupe_ids(ids: list[str]) -> list[str]:
    """Strip/dedupe job ids, preserving first-seen order. Blank ids are dropped
    (they carry no addressable target)."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in ids or []:
        jid = str(raw or "").strip()
        if not jid or jid in seen:
            continue
        seen.add(jid)
        out.append(jid)
    return out


def _bulk_summary(results: list[dict[str, str]]) -> dict[str, Any]:
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = sum(1 for r in results if r["status"] == "error")
    return {"results": results, "ok_count": ok, "fail_count": fail}


@app.post("/api/jobs/bulk/delete")
def bulk_delete_jobs(request: BulkJobsRequest) -> dict[str, Any]:
    """Bulk SOFT-delete. Each id is routed through the exact same guarded
    single-job path (``trash_job`` -> ``jobs/.trash/<id>/``). Never hard-deletes,
    never bypasses ``_guarded_trash_target``. Already-trashed ids are reported
    ``skipped``; unknown/invalid ids are reported ``error``; the batch always
    continues."""
    results: list[dict[str, str]] = []
    for jid in _dedupe_ids(request.ids):
        try:
            job = _get_job(jid)  # validates id (slash/dot reject) + active job
        except HTTPException:
            if is_trashed(jid):  # guard-safe: ValueError -> False
                results.append({"id": jid, "status": "skipped", "detail": "already trashed"})
            else:
                results.append({"id": jid, "status": "error", "detail": "not found"})
            continue
        try:
            trash_job(job.id)
            results.append({"id": job.id, "status": "ok"})
        except FileNotFoundError:
            results.append({"id": job.id, "status": "error", "detail": "not found"})
        except (JobManagerError, ValueError) as exc:
            results.append({"id": job.id, "status": "error", "detail": str(exc)})
    return _bulk_summary(results)


@app.post("/api/jobs/bulk/restore")
def bulk_restore_jobs(request: BulkJobsRequest) -> dict[str, Any]:
    """Bulk restore. Each id is routed through the same single-job ``restore_job``
    (``jobs/.trash/<id>/`` -> ``jobs/<id>/``). Ids that are already active (not in
    trash) are reported ``skipped``; unknown/invalid ids are ``error``."""
    results: list[dict[str, str]] = []
    for jid in _dedupe_ids(request.ids):
        if not is_trashed(jid):  # guard-safe for traversal ids
            try:
                _get_job(jid)  # is it an active job already?
                results.append({"id": jid, "status": "skipped", "detail": "not trashed"})
            except HTTPException:
                results.append({"id": jid, "status": "error", "detail": "not found"})
            continue
        try:
            restore_job(jid)
            results.append({"id": jid, "status": "ok"})
        except FileNotFoundError:
            results.append({"id": jid, "status": "error", "detail": "not found"})
        except (JobManagerError, ValueError) as exc:
            results.append({"id": jid, "status": "error", "detail": str(exc)})
    return _bulk_summary(results)


@app.post("/api/jobs/bulk/move")
def bulk_move_jobs(request: BulkMoveRequest) -> dict[str, Any]:
    """Bulk move-to-folder. Reuses the existing single-job
    ``library_store.move_job`` (no new folder model). The destination folder is
    a batch-level param: an unknown folder 404s the whole request (matching the
    single-item contract). Per-id results are partial-success."""
    # Validate the destination folder once, up front (mirrors single-item 404).
    try:
        library_store.normalize_target(request.folder_id)
    except library_store.FolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except library_store.LibraryStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results: list[dict[str, str]] = []
    for jid in _dedupe_ids(request.ids):
        try:
            job = _get_job(jid)
        except HTTPException:
            results.append({"id": jid, "status": "error", "detail": "not found"})
            continue
        try:
            library_store.move_job(job.id, request.folder_id)
            results.append({"id": job.id, "status": "ok"})
        except library_store.LibraryStoreError as exc:
            results.append({"id": job.id, "status": "error", "detail": str(exc)})
    return _bulk_summary(results)


@app.post("/api/jobs/bulk/purge")
def bulk_purge_jobs(request: BulkJobsRequest) -> dict[str, Any]:
    """Bulk PERMANENT delete. Each id is routed through the exact same guarded
    single-job ``purge_trashed_job`` (operates strictly inside ``jobs/.trash/``);
    no new removal path is introduced. Ids that are not CURRENTLY in the trash are
    reported ``error`` — there is no one-click permanent delete of an active job —
    and the batch always continues. Like the single purge, this is irreversible."""
    results: list[dict[str, str]] = []
    for jid in _dedupe_ids(request.ids):
        if not is_trashed(jid):  # guard-safe for traversal ids -> False
            results.append({"id": jid, "status": "error", "detail": "not in trash"})
            continue
        try:
            purge_trashed_job(jid)
            library_store.move_job(jid, None)  # drop any stale folder assignment
            results.append({"id": jid, "status": "ok"})
        except FileNotFoundError:
            results.append({"id": jid, "status": "error", "detail": "not found"})
        except (JobManagerError, ValueError) as exc:
            results.append({"id": jid, "status": "error", "detail": str(exc)})
    return _bulk_summary(results)


# ── Trash (soft delete) + permanent delete ──────────────────────────────────
# NOTE: these /api/jobs/trash* routes are registered BEFORE the catch-all
# /api/jobs/{job_id} so "trash" is never mistaken for a job id.


@app.get("/api/jobs/trash")
def list_trash() -> dict[str, Any]:
    """List jobs currently in the trash (newest-trashed first)."""
    items: list[dict[str, Any]] = []
    for entry in list_trashed():
        safe = _safe_manifest(entry.get("manifest") or {})
        items.append(
            {
                **safe,
                "id": entry["id"],
                "trashed_at": entry.get("trashed_at"),
                "attachment_summary": _attachment_summary(safe),
            }
        )
    items.sort(key=lambda item: str(item.get("trashed_at") or ""), reverse=True)
    return {"jobs": items}


@app.post("/api/jobs/{job_id}/trash")
def trash_job_route(job_id: str) -> dict[str, Any]:
    """Soft-delete: move an ACTIVE job into the trash (restorable)."""
    job = _get_job(job_id)  # validates id + confirms it's an active job
    try:
        marker = trash_job(job.id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    except (JobManagerError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "job_id": job.id, "trashed_at": marker.get("trashed_at")}


@app.post("/api/jobs/{job_id}/restore")
def restore_job_route(job_id: str) -> dict[str, Any]:
    """Restore a trashed job back to the active library."""
    _require_trashed_job(job_id)
    try:
        restore_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Trashed job not found.") from exc
    except (JobManagerError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "job_id": job_id}


@app.delete("/api/jobs/trash")
def empty_trash_route() -> dict[str, Any]:
    """PERMANENTLY delete every job currently in the trash."""
    removed = empty_trash()
    for jid in removed:
        library_store.move_job(jid, None)  # drop any stale folder assignment
    return {"ok": True, "purged": len(removed), "job_ids": removed}


@app.delete("/api/jobs/trash/{job_id}")
def purge_trashed_route(job_id: str) -> dict[str, Any]:
    """PERMANENTLY delete ONE job that is already in the trash. 404 if the id is
    not currently trashed — there is no one-click permanent delete of an active
    job."""
    _require_trashed_job(job_id)
    try:
        purge_trashed_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Trashed job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    library_store.move_job(job_id, None)  # drop any stale folder assignment
    return {"ok": True, "job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    manifest = _safe_manifest(job.read_manifest())
    manifest.update(_folder_meta(job.id))
    availability = _artifact_availability(job)
    return {
        "job": manifest,
        "attachment_summary": _attachment_summary(manifest),
        "artifact_availability": availability,
        "artifact_urls": _artifact_urls(job, availability),
        "artifacts": _artifact_details(job, availability),
        "validation_summary": _validation_summary(job),
        "render_log_summary": _render_log_summary(job),
    }


@app.get("/api/jobs/{job_id}/progress")
def get_job_progress(job_id: str) -> dict[str, Any]:
    """Coarse, pollable progress for a job's generation.

    ``status`` is the terminal-state source of truth (failed /
    completed_with_warnings / done); ``stage``/``progress`` is the finer-grained
    position within a running job. When a job reaches a terminal status the UI
    should stop polling — even if ``stage`` never reached "complete" (e.g. a job
    that failed mid-render keeps its last stage but reports status "failed").
    No filesystem paths are exposed.
    """
    job = _get_job(job_id)
    manifest = job.read_manifest()
    return {
        "status": manifest.get("status"),
        "stage": manifest.get("stage"),
        "stage_label": manifest.get("stage_label"),
        "progress": manifest.get("progress"),
        "updated_at": manifest.get("updated_at"),
    }


# Statuses a job can never be cancelled out of — it has already finished. The
# cancel endpoint refuses to touch these so completed artifacts are never mutated.
_TERMINAL_JOB_STATUSES = frozenset(
    {"done", "completed_with_warnings", "failed", "cancelled"}
)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    """Request cooperative cancellation of a running generation.

    Writes a sidecar cancel marker (``jobs/<id>/cancel.requested``); the running
    job thread observes it at its next safe stage boundary and ends in status
    ``cancelled`` with partial input/artifacts preserved. This NEVER kills a
    process and never interrupts an in-flight LLM call or Chromium render — a
    cancel requested mid-call takes effect at the next checkpoint. Already
    terminal jobs (done / completed_with_warnings / failed / cancelled) are a
    safe no-op: their artifacts are never touched and no marker is written.
    """
    job = _get_job(job_id)
    status = str(job.read_manifest().get("status") or "")
    if status in _TERMINAL_JOB_STATUSES:
        return {"id": job.id, "cancelled": False, "status": status}
    # Do not set status here — the running thread owns the manifest and would
    # overwrite it. The marker is the only cross-request signal.
    job.request_cancel()
    return {"id": job.id, "cancelled": True, "status": "cancelling"}


@app.post("/api/jobs/{job_id}/favorite")
def set_job_favorite(job_id: str, request: FavoriteRequest) -> dict[str, Any]:
    job = _get_job(job_id)
    job.set_favorite(request.value)
    return {"ok": True, "job_id": job.id, "favorite": request.value}


@app.get("/api/jobs/{job_id}/artifacts/{artifact_name}")
def get_artifact(
    job_id: str,
    artifact_name: str,
    disposition: str = "attachment",
) -> FileResponse:
    job = _get_job(job_id)
    if artifact_name == "final.docx":
        try:
            if _ensure_docx(job) is None:
                raise HTTPException(status_code=404, detail="Artifact not found.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"DOCX generation failed: {exc}") from exc
    path, media_type = _artifact_path(job, artifact_name)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": _content_disposition(disposition, artifact_name)},
    )


@app.get("/api/jobs/{job_id}/error")
def get_job_error(job_id: str) -> dict[str, Any]:
    """Return the error category, user-facing message, and a tail of the relevant log."""
    job = _get_job(job_id)
    manifest = job.read_manifest()
    status = manifest.get("status", "")
    if "failed" not in status:
        raise HTTPException(status_code=404, detail="This job has not failed.")
    category = manifest.get("error_category") or "unknown"
    message = manifest.get("error") or "An unknown error occurred."
    log_tail: list[str] = []
    if job.render_log.exists():
        text = job.render_log.read_text(encoding="utf-8", errors="replace")
        lines = [line for line in text.splitlines() if line.strip()]
        log_tail = [_safe_log_line(line) for line in lines[-20:]]
    return {
        "job_id": job_id,
        "status": status,
        "error_category": category,
        "message": message,
        "log_tail": log_tail,
        "log_available": job.render_log.exists(),
        "validation_available": _validation_json_path(job).exists(),
    }


@app.post("/api/jobs/{job_id}/retry")
def retry_failed_job(job_id: str) -> dict[str, Any]:
    """Re-run a failed job using its already-saved input — no re-upload needed."""
    job = _get_job(job_id)
    manifest = job.read_manifest()
    status = manifest.get("status", "")
    if "failed" not in status:
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried.")

    path_mode = manifest.get("path_mode", "")
    theme = str(manifest.get("theme") or "claude_clean")
    strict_math = bool(manifest.get("strict_math", True))

    if path_mode == "have_markdown":
        if not job.raw_md.exists():
            raise HTTPException(status_code=400, detail="raw.md is missing; cannot retry this job.")
        job.set_status("created", None)
        try:
            from pipeline.run_markdown_job import run_raw_markdown_pipeline
            run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
        except MarkdownJobError as exc:
            raise _job_error(exc, job=getattr(exc, "job", None)) from exc
        except Exception as exc:
            raise _job_error(exc, job=job) from exc
        return job_response(job)

    if path_mode == "generate":
        source_path = job.input_dir / "source.txt"
        if not source_path.exists():
            raise HTTPException(
                status_code=400,
                detail="input/source.txt is missing; cannot retry this job.",
            )
        provider = str(manifest.get("provider") or "")
        model_name = str(manifest.get("model") or "Use environment default")
        title = str(manifest.get("title") or "Generated Study Guide")
        mode = str(manifest.get("mode") or DEFAULT_MODE)
        prompt_name = str(manifest.get("prompt_name") or "basic_study_guide")
        qwen_thinking = bool(manifest.get("qwen_thinking", True))
        manifest_sections = manifest.get("include_sections")
        include_sections = manifest_sections if isinstance(manifest_sections, dict) else {}
        # Reproduce the generation-directive axes the job was created with. Stored
        # values were validated on the way in; the orchestrator ignores unknowns.
        manifest_depth = manifest.get("output_depth")
        output_depth = manifest_depth if isinstance(manifest_depth, str) else None
        manifest_difficulty = manifest.get("difficulty")
        difficulty = manifest_difficulty if isinstance(manifest_difficulty, str) else None
        # Preserve the PDF page selection across a retry (Slice 3). Re-normalize the
        # stored value and write it back so the manifest stays canonical even if it
        # predates this field. Extraction still ignores it — this only keeps the
        # request reproducible for the future page-filtering slice.
        page_selections = _normalize_page_selections(manifest.get("page_selections"))
        job.update(page_selections=page_selections)
        # Reproduce the generator preset the job was created with, so a retry rebuilds
        # through the same preset system prompt + tuned sampling params (not the default
        # prompt path). If the stored preset id no longer exists (e.g. removed since the
        # job ran), degrade gracefully to the default path rather than failing the retry.
        manifest_preset = manifest.get("generator_preset")
        generator_preset = manifest_preset if isinstance(manifest_preset, str) and manifest_preset else None
        preset = None
        if generator_preset is not None:
            if generator_presets.generator_preset_exists(generator_preset):
                preset = generator_presets.get_generator_preset(generator_preset)
            else:
                generator_preset = None

        try:
            if preset is not None:
                # Mirror the /api/jobs/llm preset path: the preset pins its own sampling
                # params (the user's saved provider/model still wins — model_hint stays
                # advisory, never a hard pin).
                config = build_provider_config(
                    provider,
                    model_name,
                    qwen_thinking_enabled=preset["thinking"],
                    temperature_override=preset["temperature"],
                    top_p=preset["top_p"],
                    max_tokens=preset["max_tokens"],
                )
            else:
                config = build_provider_config(provider, model_name, qwen_thinking_enabled=qwen_thinking)
        except MissingLLMConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        job.set_status("created", None)

        try:
            job.set_status("generating")
            raw_markdown = generate_study_guide(
                source_text,
                title=title,
                mode=mode,
                prompt_name=prompt_name,
                generator_preset=generator_preset,
                include_sections=include_sections,
                output_depth=output_depth,
                difficulty=difficulty,
                config=config,
            )
            job.save_text(job.raw_md, raw_markdown)
            job.update(raw_md=str(job.raw_md))
            from pipeline.run_markdown_job import run_raw_markdown_pipeline
            run_raw_markdown_pipeline(job, theme=theme, strict_math=strict_math)
        except LLMProviderError as exc:
            job.set_status("failed", str(exc), error_category=exc.category)
            raise HTTPException(status_code=502, detail={"message": str(exc), "job": job_response(job)}) from exc
        except MarkdownJobError as exc:
            raise _job_error(exc, job=getattr(exc, "job", None)) from exc
        except Exception as exc:
            raise _job_error(exc, job=job) from exc
        return job_response(job)

    raise HTTPException(
        status_code=400,
        detail=f"Cannot retry a job with path_mode '{path_mode}'.",
    )


@app.post("/api/jobs/{job_id}/rerender")
def rerender_existing_job(job_id: str, request: RerenderRequest | None = None) -> dict[str, Any]:
    job = _get_job(job_id)
    theme = request.theme if request else None
    if theme is not None:
        _validate_theme(theme)
    if not job.clean_md.exists():
        raise HTTPException(status_code=400, detail="This guide has no clean.md to re-render.")
    try:
        rerender_job(job, theme=theme)
    except MarkdownJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc) from exc
    # Keep an already-generated DOCX in sync (best-effort; never fails rerender).
    if job.final_docx.exists():
        try:
            _ensure_docx(job, regenerate=True)
        except Exception:
            pass
    return job_response(job)


@app.get("/api/jobs/{job_id}/versions")
def list_job_versions(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    manifest = job.read_manifest()
    return {"versions": manifest.get("versions", [])}


@app.get("/api/jobs/{job_id}/clean_md")
def get_clean_md(job_id: str) -> Response:
    job = _get_job(job_id)
    if not job.clean_md.exists():
        raise HTTPException(status_code=404, detail="clean.md not found.")
    return Response(
        content=job.clean_md.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


@app.put("/api/jobs/{job_id}/clean_md")
def put_clean_md(job_id: str, body: EditCleanMdRequest) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job.clean_md.exists():
        raise HTTPException(status_code=404, detail="No clean.md for this job.")
    job.save_clean_md(body.text, "edited")
    try:
        rerender_job(job)
    except MarkdownJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc, job=job) from exc
    if job.final_docx.exists():
        try:
            _ensure_docx(job, regenerate=True)
        except Exception:
            pass
    manifest = job.read_manifest()
    return {
        "artifact_availability": _artifact_availability(job),
        "versions": manifest.get("versions", []),
    }


@app.get("/api/jobs/{job_id}/versions/{version}/clean_md")
def get_version_clean_md(job_id: str, version: int) -> Response:
    job = _get_job(job_id)
    v_path = job.versions_dir / str(version) / "clean.md"
    if not _is_job_path(job, v_path) or not v_path.exists():
        raise HTTPException(status_code=404, detail=f"Version {version} not found.")
    return Response(
        content=v_path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )


@app.post("/api/jobs/{job_id}/revert/{version}")
def revert_job_version(job_id: str, version: int) -> dict[str, Any]:
    job = _get_job(job_id)
    v_path = job.versions_dir / str(version) / "clean.md"
    if not _is_job_path(job, v_path) or not v_path.exists():
        raise HTTPException(status_code=404, detail=f"Version {version} not found.")
    old_text = v_path.read_text(encoding="utf-8")
    job.save_clean_md(old_text, "reverted")
    try:
        rerender_job(job)
    except MarkdownJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc, job=job) from exc
    if job.final_docx.exists():
        try:
            _ensure_docx(job, regenerate=True)
        except Exception:
            pass
    manifest = job.read_manifest()
    return {
        "artifact_availability": _artifact_availability(job),
        "versions": manifest.get("versions", []),
    }


@app.get("/api/jobs/{job_id}/sections")
def list_job_sections(job_id: str) -> dict[str, Any]:
    """Return all heading sections parsed from clean.md (preamble excluded)."""
    job = _get_job(job_id)
    if not job.clean_md.exists():
        raise HTTPException(status_code=404, detail="No clean.md for this job.")
    text = job.clean_md.read_text(encoding="utf-8")
    sections = parse_sections(text)
    return {
        "sections": [
            {
                "index": s.index,
                "heading_text": s.heading_text,
                "heading_level": s.heading_level,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "preview": s.raw_markdown[:200],
            }
            for s in sections
            if s.heading_level > 0
        ]
    }


@app.get("/api/jobs/{job_id}/outline_compliance")
def get_outline_compliance(job_id: str) -> dict[str, Any]:
    """Compare the job's required outline sections against headings in clean.md."""
    job = _get_job(job_id)
    manifest = job.read_manifest()

    if not manifest.get("outline_enabled"):
        return {"has_outline": False, "sections": []}

    outline_titles: list[str] = manifest.get("outline_titles") or []
    if not outline_titles:
        return {"has_outline": False, "sections": []}

    if not job.clean_md.exists():
        raise HTTPException(status_code=404, detail="No clean.md for this job.")

    text = job.clean_md.read_text(encoding="utf-8")
    doc_sections = parse_sections(text)
    results = check_outline_compliance(outline_titles, doc_sections)
    return {"has_outline": True, "sections": results}


@app.post("/api/jobs/{job_id}/sections/{section_index}/regenerate")
def regenerate_job_section(
    job_id: str,
    section_index: int,
    request: SectionRegenerateRequest,
) -> dict[str, Any]:
    """Regenerate a single section of clean.md with the LLM, then re-render.

    Writes through save_clean_md (auto-snapshots for version history).
    Splices by token-derived line position, not string matching.
    """
    job = _get_job(job_id)
    manifest = job.read_manifest()

    # Validate action
    valid_actions = set(SECTION_REGEN_ACTIONS.keys()) | {"custom"}
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {', '.join(sorted(valid_actions))}",
        )
    if request.action == "custom" and not request.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is required for action=custom.")

    if not job.clean_md.exists():
        raise HTTPException(status_code=404, detail="No clean.md for this job.")

    text = job.clean_md.read_text(encoding="utf-8")
    sections = parse_sections(text)

    target = next((s for s in sections if s.index == section_index), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Section {section_index} not found.")
    if target.heading_level == 0:
        raise HTTPException(status_code=400, detail="Cannot regenerate the preamble section.")

    # Resolve provider / model — fall back to what the job was originally generated with.
    provider_str = (request.provider or manifest.get("provider") or "").strip()
    model_str = (request.model or manifest.get("model") or "").strip()
    if not provider_str:
        raise HTTPException(
            status_code=400,
            detail=(
                "provider is required (pass it in the request or generate "
                "the guide with an LLM so the provider is stored in the job)."
            ),
        )

    try:
        config = build_provider_config(
            provider_str,
            model_str or "Use environment default",
            qwen_thinking_enabled=request.qwen_thinking,
        )
    except MissingLLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Build the LLM prompt (section only — not the whole guide).
    title = manifest.get("title") or "Study Guide"
    action_desc = (
        request.instruction.strip()
        if request.action == "custom" and request.instruction.strip()
        else SECTION_REGEN_ACTIONS.get(request.action, request.instruction.strip())
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert study guide editor. "
                "You rewrite individual sections of a study guide. "
                "Output ONLY the rewritten section as valid Markdown. "
                "Use dollar-delimited LaTeX for math ($...$ inline, $$...$$ display). "
                "Begin your response with the section heading line."
            ),
        },
        {
            "role": "user",
            "content": "\n".join([
                f"Guide title: {title}",
                "",
                f"Task: {action_desc}",
                "",
                "Section to rewrite:",
                "",
                target.raw_markdown.rstrip(),
            ]),
        },
    ]

    try:
        new_section_md = generate_chat_completion(messages, config)
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Section regeneration failed: {exc}") from exc

    new_section_md = new_section_md.strip()
    # Guard: if the LLM omitted the heading, prepend the original one.
    if not new_section_md.startswith("#"):
        heading_line = target.raw_markdown.split("\n", 1)[0]
        new_section_md = heading_line + "\n" + new_section_md

    # Splice by line position (not string match) and write through the chokepoint.
    new_text = splice_section(text, target, new_section_md + "\n")
    job.save_clean_md(new_text, "edited")

    try:
        rerender_job(job)
    except MarkdownJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc, job=job) from exc

    if job.final_docx.exists():
        try:
            _ensure_docx(job, regenerate=True)
        except Exception:
            pass

    updated = job.read_manifest()
    return {
        "ok": True,
        "section_index": section_index,
        "artifact_availability": _artifact_availability(job),
        "versions": updated.get("versions", []),
    }


@app.post("/api/jobs/{job_id}/quiz")
def generate_quiz(job_id: str, request: QuizRequest) -> dict[str, Any]:
    """Generate a quiz from a job's clean.md and persist it under jobs/<id>/quizzes/<n>.json."""
    job = _get_job(job_id)
    if not job.clean_md.exists():
        raise HTTPException(status_code=404, detail="No clean.md for this job.")

    # Validate inputs
    bad_types = [t for t in request.question_types if t not in VALID_QUESTION_TYPES]
    if bad_types:
        raise HTTPException(status_code=400, detail=f"Invalid question_types: {bad_types}. Allowed: {sorted(VALID_QUESTION_TYPES)}")
    if not request.question_types:
        raise HTTPException(status_code=400, detail="question_types must not be empty.")
    if request.count not in VALID_QUIZ_COUNTS:
        raise HTTPException(status_code=400, detail=f"count must be one of {sorted(VALID_QUIZ_COUNTS)}.")
    if request.difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(status_code=400, detail=f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}.")
    if request.focus not in VALID_FOCUS:
        raise HTTPException(status_code=400, detail=f"focus must be one of {sorted(VALID_FOCUS)}.")

    # Resolve provider/model: prefer request > job manifest > any configured provider
    manifest = job.read_manifest()
    provider_str = (request.provider or manifest.get("provider") or "").strip()
    model_str = (request.model or manifest.get("model") or "").strip()
    if not provider_str:
        provider_id, fallback_model = _pick_generate_provider(None)
        provider_str = provider_id
        if not model_str:
            model_str = fallback_model or "Use environment default"

    try:
        config = build_provider_config(
            provider_str,
            model_str or "Use environment default",
            qwen_thinking_enabled=request.qwen_thinking,
        )
    except MissingLLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Build content from selected sections
    text = job.clean_md.read_text(encoding="utf-8")
    sections = parse_sections(text)
    title = manifest.get("title") or "Study Guide"

    if request.section_indices is not None:
        idx_set = set(request.section_indices)
        selected = [s for s in sections if s.index in idx_set and s.heading_level > 0]
        if not selected:
            raise HTTPException(status_code=400, detail="No valid sections found for the given section_indices.")
        content_parts = [s.raw_markdown for s in selected]
    else:
        content_parts = [s.raw_markdown for s in sections if s.heading_level > 0]
        if not content_parts:
            # Preamble-only guide — use full text
            content_parts = [text]

    content = "\n\n".join(content_parts)

    # Truncate if very long (keep ~120 KB of guide text for the prompt)
    MAX_CONTENT_CHARS = 120_000
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[Guide truncated — additional content not shown]"

    messages = _build_quiz_messages(
        title=title,
        content=content,
        question_types=request.question_types,
        count=request.count,
        difficulty=request.difficulty,
        focus=request.focus,
    )

    try:
        raw = generate_chat_completion(messages, config)
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quiz generation failed: {exc}") from exc

    items = _parse_quiz_response(raw)

    # Persist
    quiz_dir = job.quizzes_dir
    quiz_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(
        int(p.stem) for p in quiz_dir.glob("*.json") if p.stem.isdigit()
    )
    n = (existing[-1] + 1) if existing else 1
    quiz_data: dict[str, Any] = {
        "n": n,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {
            "question_types": request.question_types,
            "count": request.count,
            "difficulty": request.difficulty,
            "focus": request.focus,
            "section_indices": request.section_indices,
            "provider": config.provider,
            "model": config.model,
        },
        "item_count": len(items),
        "items": items,
    }
    (quiz_dir / f"{n}.json").write_text(
        json.dumps(quiz_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return quiz_data


@app.get("/api/jobs/{job_id}/quizzes")
def list_quizzes(job_id: str) -> dict[str, Any]:
    """List previously generated quizzes for a job."""
    job = _get_job(job_id)
    quizzes: list[dict[str, Any]] = []
    if job.quizzes_dir.exists():
        for path in sorted(job.quizzes_dir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
            data = _read_json(path)
            if data is None:
                continue
            quizzes.append({
                "n": data.get("n"),
                "created_at": data.get("created_at"),
                "item_count": data.get("item_count") or len(data.get("items") or []),
                "config": data.get("config"),
            })
    return {"quizzes": quizzes}


@app.get("/api/jobs/{job_id}/quizzes/{quiz_n}")
def get_quiz(job_id: str, quiz_n: int) -> dict[str, Any]:
    """Return a specific quiz (items included)."""
    job = _get_job(job_id)
    path = job.quizzes_dir / f"{quiz_n}.json"
    if not _is_job_path(job, path) or not path.exists():
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_n} not found.")
    data = _read_json(path)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_n} could not be read.")
    return data


@app.get("/api/jobs/{job_id}/quizzes/{quiz_n}/export")
def export_quiz(job_id: str, quiz_n: int, format: str = "csv") -> Response:
    """Export a quiz as csv, anki_tsv, or quizlet format."""
    if format not in VALID_EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {sorted(VALID_EXPORT_FORMATS)}.")
    job = _get_job(job_id)
    path = job.quizzes_dir / f"{quiz_n}.json"
    if not _is_job_path(job, path) or not path.exists():
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_n} not found.")
    data = _read_json(path)
    if data is None:
        raise HTTPException(status_code=500, detail="Quiz file could not be read.")
    items = data.get("items") or []

    content, media_type, ext = _render_quiz_export(items, format)
    filename = f"quiz-{job_id}-{quiz_n}.{ext}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_quiz_messages(
    *,
    title: str,
    content: str,
    question_types: list[str],
    count: int,
    difficulty: str,
    focus: str,
) -> list[dict]:
    focus_desc = {
        "definitions": "key terms, definitions, and vocabulary",
        "formulas": "formulas, equations, and mathematical relationships",
        "examples": "specific examples, case studies, and applications",
        "all": "all concepts in the material",
    }.get(focus, "all concepts in the material")

    type_instructions: list[str] = []
    for qt in question_types:
        if qt == "mcq":
            type_instructions.append('- "mcq": include "options" (array of exactly 4 strings, each prefixed A./B./C./D.); "answer" is the letter only (A, B, C, or D)')
        elif qt == "true_false":
            type_instructions.append('- "true_false": no "options" field; "answer" is "True" or "False"')
        elif qt == "fill_blank":
            type_instructions.append('- "fill_blank": question contains a blank (_____); "answer" is the missing word(s)')
        elif qt == "short_answer":
            type_instructions.append('- "short_answer": open-ended question; "answer" is a concise model answer (1–3 sentences)')
        elif qt == "flashcards":
            type_instructions.append('- "flashcards": "question" is the term/prompt; "answer" is the definition or explanation')

    types_joined = ", ".join(f'"{t}"' for t in question_types)
    system = (
        "You are an expert quiz generator. You produce structured quiz questions from study material. "
        "You output ONLY valid JSON — no prose, no markdown fences, no explanation before or after."
    )
    user_parts = [
        f"Generate exactly {count} quiz questions for the study guide titled: {title}",
        "",
        f"Distribute questions across these types: {types_joined}",
        f"Difficulty: {difficulty}",
        f"Focus on: {focus_desc}",
        "",
        "RETURN A JSON ARRAY AND NOTHING ELSE. Each element must have:",
        '  "type": one of the types listed above',
        '  "question": question text',
        '  "answer": see per-type rules below',
        '  "topic": the section heading this question comes from (exact text)',
        f'  "difficulty": "{difficulty}"',
        "",
        "Per-type rules:",
        *type_instructions,
        "",
        "Do not include any text outside the JSON array. Do not wrap in markdown fences.",
        "",
        "=== STUDY GUIDE CONTENT ===",
        "",
        content,
    ]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def _parse_quiz_response(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    # Strip accidental markdown fences
    fenced = re.search(r"```(?:json)?\s*(\[.*\])\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Find outermost array
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Quiz parse error: the model returned invalid JSON. ({exc})",
        ) from exc

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=502,
            detail="Quiz parse error: expected a JSON array from the model.",
        )

    items: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        qtype = str(item.get("type") or "").strip()
        if qtype not in VALID_QUESTION_TYPES:
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question or not answer:
            continue
        clean: dict[str, Any] = {
            "type": qtype,
            "question": question,
            "answer": answer,
            "topic": str(item.get("topic") or "").strip(),
            "difficulty": str(item.get("difficulty") or "").strip(),
        }
        if qtype == "mcq" and isinstance(item.get("options"), list):
            clean["options"] = [str(o) for o in item["options"]]
        items.append(clean)
    return items


def _render_quiz_export(items: list[dict[str, Any]], format: str) -> tuple[bytes, str, str]:
    """Return (content_bytes, media_type, file_extension)."""
    def front(item: dict) -> str:
        return item.get("question", "")

    def back(item: dict) -> str:
        ans = item.get("answer", "")
        if item.get("type") == "mcq" and item.get("options"):
            # Include the full option text for the answer letter
            letter = ans.upper()
            opts: list[str] = item["options"]
            match = next((o for o in opts if o.upper().startswith(f"{letter}.")), ans)
            return match
        return ans

    def topic(item: dict) -> str:
        return item.get("topic", "")

    def diff(item: dict) -> str:
        return item.get("difficulty", "")

    if format == "csv":
        import csv
        import io as _io
        buf = _io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["Front", "Back", "Topic", "Difficulty"])
        for item in items:
            writer.writerow([front(item), back(item), topic(item), diff(item)])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "csv"

    if format == "anki_tsv":
        rows = [f"{front(item)}\t{back(item)}\t{topic(item)}\t{diff(item)}" for item in items]
        return "\n".join(rows).encode("utf-8"), "text/tab-separated-values; charset=utf-8", "tsv"

    if format == "quizlet":
        # Quizlet import: term<TAB>definition<NEWLINE>
        rows = [f"{front(item)}\t{back(item)}" for item in items]
        return "\n".join(rows).encode("utf-8"), "text/plain; charset=utf-8", "txt"

    raise ValueError(f"Unknown format: {format}")


def job_response(job: Job) -> dict[str, Any]:
    manifest = job.read_manifest()
    availability = _artifact_availability(job)
    artifact_urls = _artifact_urls(job, availability)
    response: dict[str, Any] = {
        "job_id": job.id,
        "status": manifest.get("status"),
        "title": manifest.get("title"),
        "provider": manifest.get("provider"),
        "model": manifest.get("model"),
        "created_at": manifest.get("created_at"),
        "attachments": _safe_attachment_metadata(manifest.get("attachments", [])),
        "extraction_warnings": _safe_warnings(manifest.get("extraction_warnings", [])),
        "total_extracted_chars": manifest.get("total_extracted_chars", 0),
        "attachment_summary": _attachment_summary(manifest),
        "artifact_availability": availability,
        "artifact_urls": artifact_urls,
        "math_failures": _safe_math_failures(manifest.get("math_failures", [])),
        "math_warnings": manifest.get("math_warnings"),
        # Echo the stored PDF page selection (Slice 3). Already normalized + bounded
        # on write; default {} (= all pages). Lets the UI/tests confirm persistence.
        "page_selections": _safe_page_selections(manifest.get("page_selections")),
        **_outline_summary(manifest),
    }
    if manifest.get("error"):
        response["error"] = manifest["error"]
        response["error_category"] = manifest.get("error_category") or "unknown"
    return response


def _artifact_urls(job: Job, availability: dict[str, bool]) -> dict[str, str]:
    return {
        artifact_name: f"/api/jobs/{job.id}/artifacts/{artifact_name}"
        for artifact_name, (key, _media_type) in ARTIFACTS.items()
        if availability.get(key)
    }


def _validate_theme(theme: str) -> None:
    if theme not in THEMES:
        raise HTTPException(status_code=400, detail="Unsupported theme.")


def _validate_prompt_name(prompt_name: str) -> None:
    if not style_store.style_exists(prompt_name):
        raise HTTPException(status_code=400, detail="Unsupported prompt_name.")


def _validate_generation_axes(output_depth: str | None, difficulty: str | None) -> None:
    """Reject unknown axis enum values up front (repo convention: scalar inputs are
    validated at the boundary, like provider/model/theme). Unset (None/"") is fine
    and contributes no prompt fragment."""
    if output_depth and output_depth not in OUTPUT_DEPTH_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported output_depth. Expected one of: {', '.join(OUTPUT_DEPTH_VALUES)}.",
        )
    if difficulty and difficulty not in DIFFICULTY_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported difficulty. Expected one of: {', '.join(DIFFICULTY_VALUES)}.",
        )


def _validate_generator_preset(preset_id: str) -> None:
    """Reject unknown presets and presets whose body no longer resolves from the md."""
    if not generator_presets.generator_preset_exists(preset_id):
        raise HTTPException(status_code=400, detail="Unsupported generator_preset.")
    try:
        generator_presets.resolve_system_prompt(preset_id)
    except generator_presets.GeneratorPresetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_folder_target(folder_id: str | None) -> str | None:
    """Validate an optional Library folder target before a job runs.

    Returns the concrete folder id to assign, or ``None`` to leave the job
    unfiled (``None``/``""``/``"unfiled"``). Raises a clear HTTP error for an
    unknown folder or the virtual "all" target.
    """
    try:
        return library_store.normalize_target(folder_id)
    except library_store.FolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except library_store.LibraryStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _apply_folder_assignment(job_id: str, folder_target: str | None) -> None:
    """Assign a freshly created job to a pre-validated folder (best effort).

    ``folder_target`` must already have passed :func:`_resolve_folder_target`.
    If the folder vanished between validation and assignment, the job is left
    unfiled rather than failing an already-generated job.
    """
    if folder_target is None:
        return
    try:
        library_store.move_job(job_id, folder_target)
    except library_store.LibraryStoreError:
        pass


_EMPTY_FOLDER_META = {"folder_id": None, "folder_name": None, "folder_color": None}


def _folder_meta(job_id: str, folders_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Safe, flat folder metadata for a job: id/name/color (all None if unfiled).

    Only exposes registry fields (id/name/color) — never any filesystem path.
    ``folders_by_id`` is an optional precomputed ``list_folders`` map to avoid a
    per-job folder read when listing many jobs.
    """
    folder_id = library_store.folder_id_for(job_id)
    if folder_id == library_store.VIRTUAL_UNFILED:
        return dict(_EMPTY_FOLDER_META)
    folder = (folders_by_id or {}).get(folder_id) or library_store.get_folder(folder_id)
    if not folder:
        return dict(_EMPTY_FOLDER_META)
    return {
        "folder_id": folder["id"],
        "folder_name": folder.get("name"),
        "folder_color": folder.get("color"),
    }


def _safe_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    safe = dict(manifest)
    for key in [
        "input_path",
        "source_path",
        "raw_md",
        "clean_md",
        "final_html",
        "final_pdf",
        "validation_json",
        "error_log_path",  # filesystem path — never expose; use artifact endpoint instead
    ]:
        safe.pop(key, None)
    safe["attachments"] = _safe_attachment_metadata(manifest.get("attachments", []))
    safe["extraction_warnings"] = _safe_warnings(manifest.get("extraction_warnings", []))
    safe["math_failures"] = _safe_math_failures(manifest.get("math_failures", []))
    safe["total_extracted_chars"] = int(manifest.get("total_extracted_chars") or 0)
    safe["favorite"] = bool(manifest.get("favorite", False))
    safe.update(_outline_summary(manifest))
    return safe


def _safe_attachment_metadata(attachments: Any) -> list[dict[str, Any]]:
    if not isinstance(attachments, list):
        return []

    safe: list[dict[str, Any]] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        filename = str(attachment.get("filename") or attachment.get("original_filename") or "attachment")
        safe.append(
            {
                "filename": filename,
                "extension": Path(filename).suffix.lower(),
                "mode": attachment.get("mode"),
                "status": attachment.get("status") or "unknown",
                "extracted_chars": int(attachment.get("extracted_chars") or 0),
                "truncated": bool(attachment.get("truncated")),
                "warnings": _safe_warnings(attachment.get("warnings", [])),
            }
        )
    return safe


def _safe_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    return [str(warning)[:500] for warning in warnings if warning]


def _safe_math_failures(failures: Any) -> list[dict[str, Any]]:
    """Sanitize the recorded list of math expressions that failed validation.

    These let the UI show "N math expressions couldn't render — fix them in the
    Markdown editor". Only the expression, mode, and KaTeX message are exposed
    (no filesystem paths), each length-capped.
    """
    if not isinstance(failures, list):
        return []
    safe: list[dict[str, Any]] = []
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        safe.append(
            {
                "expr": str(failure.get("expr") or "")[:500],
                "display_mode": bool(failure.get("display_mode")),
                "message": str(failure.get("message") or "")[:500],
            }
        )
    return safe


def _attachment_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    attachments = _safe_attachment_metadata(manifest.get("attachments", []))
    warnings = _safe_warnings(manifest.get("extraction_warnings", []))
    if not warnings:
        warnings = [
            warning
            for attachment in attachments
            for warning in attachment.get("warnings", [])
        ]
    return {
        "count": len(attachments),
        "warning_count": len(warnings),
        "total_extracted_chars": int(manifest.get("total_extracted_chars") or 0),
        "has_warnings": bool(warnings),
    }


def _artifact_details(job: Job, availability: dict[str, bool]) -> list[dict[str, Any]]:
    urls = _artifact_urls(job, availability)
    details: list[dict[str, Any]] = []
    for artifact_name, (key, media_type) in ARTIFACTS.items():
        available = bool(availability.get(key))
        details.append(
            {
                "name": artifact_name,
                "key": key,
                "label": _artifact_label(artifact_name),
                "available": available,
                "media_type": media_type,
                "url": urls.get(artifact_name),
            }
        )
    return details


def _artifact_label(artifact_name: str) -> str:
    return {
        "final.pdf": "PDF",
        "final.docx": "DOCX",
        "clean.md": "Markdown",
        "final.html": "HTML",
        "validation.json": "Validation JSON",
        "render.log": "Render log",
    }.get(artifact_name, artifact_name)


def _validation_summary(job: Job) -> dict[str, Any]:
    path = _validation_json_path(job)
    if not path.exists() or not path.is_file():
        manifest = job.read_manifest()
        math_validation = manifest.get("math_validation")
        if isinstance(math_validation, dict):
            return {
                "available": False,
                "ok": bool(math_validation.get("ok")),
                "error_count": int(math_validation.get("errors") or 0),
                "display_blocks": int(math_validation.get("display_blocks") or 0),
                "inline_formulas": int(math_validation.get("inline_formulas") or 0),
            }
        return {"available": False, "ok": None, "error_count": 0}

    data = _read_json(path) or {}
    errors = data.get("errors")
    error_count = len(errors) if isinstance(errors, list) else int(errors or 0)
    return {
        "available": True,
        "ok": bool(data.get("ok")),
        "error_count": error_count,
        "display_blocks": int(data.get("displayBlocks") or data.get("display_blocks") or 0),
        "inline_formulas": int(data.get("inlineFormulas") or data.get("inline_formulas") or 0),
    }


def _render_log_summary(job: Job) -> dict[str, Any]:
    if not job.render_log.exists() or not job.render_log.is_file():
        return {"available": False, "line_count": 0, "last_lines": []}

    text = job.render_log.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    return {
        "available": True,
        "line_count": len(lines),
        "last_lines": [_safe_log_line(line) for line in lines[-5:]],
    }


def _safe_log_line(line: str) -> str:
    return str(line).replace(str(JOBS_DIR), "jobs")


async def _parse_llm_request(request: Request) -> tuple[LLMJobRequest, list[AttachmentSource]]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        data = {
            "source_text": _form_text(form, "source_text") or _form_text(form, "prompt") or _form_text(form, "topic") or "",
            "title": _form_text(form, "title") or "Generated Study Guide",
            "mode": _form_text(form, "mode") or DEFAULT_MODE,
            "prompt_name": _form_text(form, "prompt_name") or _form_text(form, "style") or "basic_study_guide",
            "generator_preset": _form_text(form, "generator_preset") or None,
            "provider": _form_text(form, "provider") or "",
            "model": _form_text(form, "model") or "",
            "theme": _form_text(form, "theme") or "claude_clean",
            "strict_math": _form_bool(form, "strict_math", True),
            # Absent ⇒ None so the provider-settings thinking_default can fill it on
            # the multipart path too (parity with the JSON LLMJobRequest default).
            "qwen_thinking": _form_bool(form, "qwen_thinking", None),
            "folder_id": _form_text(form, "folder_id"),
            # C2 generation axes ride along as plain form text (unset → None so the
            # default request stays axis-free). Validated downstream like the JSON path.
            "output_depth": _form_text(form, "output_depth") or None,
            "difficulty": _form_text(form, "difficulty") or None,
        }
        outline_raw = _form_text(form, "outline")
        if outline_raw:
            try:
                data["outline"] = json.loads(outline_raw)
            except json.JSONDecodeError:
                data["outline"] = None
        # C1 output sections arrive as a JSON string in multipart (the attachments
        # path); without this they were silently dropped when a guide had uploads.
        # Mirror the outline handling: bad JSON / non-dict falls back to the default.
        sections_raw = _form_text(form, "include_sections")
        if sections_raw:
            try:
                parsed_sections = json.loads(sections_raw)
            except json.JSONDecodeError:
                parsed_sections = None
            if isinstance(parsed_sections, dict):
                data["include_sections"] = parsed_sections
        # PDF page selections (Slice 3) ride as a JSON string in multipart, exactly
        # like include_sections above (this is the path the Builder uses once it has
        # attachments). Bad JSON / non-dict falls back to {} (= all pages); the
        # contents are validated later by _normalize_page_selections.
        page_selections_raw = _form_text(form, "page_selections")
        if page_selections_raw:
            try:
                parsed_selections = json.loads(page_selections_raw)
            except json.JSONDecodeError:
                parsed_selections = None
            if isinstance(parsed_selections, dict):
                data["page_selections"] = parsed_selections
        uploads = [
            value
            for key, value in form.multi_items()
            if key in {"attachments", "files", "file"} and hasattr(value, "filename") and hasattr(value, "read")
        ]
        attachments = await _save_llm_attachments(uploads)
        try:
            return LLMJobRequest(**data), attachments
        except ValidationError as exc:
            for attachment in attachments:
                attachment.path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Invalid LLM job request.") from exc

    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON request.") from exc
    try:
        return LLMJobRequest(**payload), []
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="Invalid LLM job request.") from exc


def _form_text(form: Any, key: str) -> str | None:
    value = form.get(key)
    if isinstance(value, str):
        return value
    return None


def _form_bool(form: Any, key: str, default: bool | None) -> bool | None:
    value = form.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


async def _save_llm_attachments(uploads: list[UploadFile]) -> list[AttachmentSource]:
    if len(uploads) > MAX_LLM_ATTACHMENTS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_LLM_ATTACHMENTS} attachments are allowed.")

    attachments: list[AttachmentSource] = []
    for upload in uploads:
        filename = Path(upload.filename or "attachment").name
        suffix = Path(filename).suffix.lower()
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="llm-attachment-") as tmp:
                temp_path = Path(tmp.name)
                size = 0
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_LLM_ATTACHMENT_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail=f"{filename} exceeds the {MAX_LLM_ATTACHMENT_BYTES // (1024 * 1024)} MB attachment limit.",
                        )
                    tmp.write(chunk)
            attachments.append(AttachmentSource(path=temp_path, filename=filename))
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()
    return attachments


def _preflight_limits() -> dict[str, Any]:
    """Effective threshold values echoed back so UI copy can reference them."""
    return {
        "max_upload_mb": MAX_LLM_ATTACHMENT_BYTES // (1024 * 1024),
        "sample_pages": PREFLIGHT_SAMPLE_PAGES,
        "warn_pages": PREFLIGHT_WARN_PAGES,
        "warn_size_mb": PREFLIGHT_WARN_SIZE_MB,
        "ocr_page_limit": PREFLIGHT_OCR_PAGE_LIMIT,
        "default_first_n": PREFLIGHT_DEFAULT_FIRST_N,
        "image_heavy_ratio": PREFLIGHT_IMAGE_HEAVY_RATIO,
        "text_ratio": PREFLIGHT_TEXT_RATIO,
    }


def _preflight_base(filename: str, file_size_bytes: int) -> dict[str, Any]:
    return {
        "ok": True,
        "filename": filename,
        "content_type": "application/pdf",
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
        "limits": _preflight_limits(),
    }


def _preflight_terminal(
    base: dict[str, Any],
    *,
    verdict: str,
    scanned_flag: str,
    recommended_mode: str,
    warnings: list[str],
    allowed_actions: list[str],
    ocr_available: bool = False,
) -> dict[str, Any]:
    """Assemble a non-inspected report (blocked / degraded-to-ok) with the same
    top-level shape as a successful inspection so the contract stays uniform."""
    return {
        **base,
        "page_count": None,
        "sampled_pages": 0,
        "text_pages_estimate": 0,
        "ocr_pages_estimate": 0,
        "image_ratio_est": None,
        "is_estimate": True,
        "scanned_flag": scanned_flag,
        "recommended_mode": recommended_mode,
        "ocr_available": ocr_available,
        "verdict": verdict,
        "warnings": warnings,
        "allowed_actions": allowed_actions,
    }


def _build_pdf_preflight_report(
    path: Path, *, filename: str, file_size_bytes: int
) -> dict[str, Any]:
    """Turn the cheap :func:`pipeline.extract.preflight_pdf` inspection into the
    API report (verdict + warnings + allowed actions + echoed limits).

    Preflight must NEVER block a PDF that would otherwise process: encrypted /
    corrupt files return ``verdict: "blocked"`` (the request still succeeded —
    ``ok: true``), and any other inspection failure (incl. PyMuPDF being
    unavailable on the host) degrades to ``verdict: "ok"`` with a soft note.
    """
    from pipeline.extract import ExtractionError, PdfEncryptedError, preflight_pdf

    base = _preflight_base(filename, file_size_bytes)

    try:
        result = preflight_pdf(
            path,
            sample_pages=PREFLIGHT_SAMPLE_PAGES,
            image_heavy_ratio=PREFLIGHT_IMAGE_HEAVY_RATIO,
            text_ratio=PREFLIGHT_TEXT_RATIO,
        )
    except PdfEncryptedError:
        return _preflight_terminal(
            base,
            verdict="blocked",
            scanned_flag="unknown",
            recommended_mode="full",
            warnings=[
                "This PDF is encrypted or password-protected and can't be read. "
                "Remove it or upload an unlocked copy."
            ],
            allowed_actions=["remove_file"],
        )
    except ImportError:
        # PyMuPDF unavailable (e.g. host venv) — never block a processable file.
        return _preflight_terminal(
            base,
            verdict="ok",
            scanned_flag="unknown",
            recommended_mode="full",
            warnings=["Couldn't inspect this PDF (PDF tools unavailable); it will be processed normally."],
            allowed_actions=["continue", "remove_file"],
        )
    except ExtractionError:
        return _preflight_terminal(
            base,
            verdict="blocked",
            scanned_flag="unknown",
            recommended_mode="full",
            warnings=["This file couldn't be opened — it may be corrupt or not a real PDF."],
            allowed_actions=["remove_file"],
        )
    except Exception:
        # Any other unexpected inspection failure degrades to a safe pass.
        return _preflight_terminal(
            base,
            verdict="ok",
            scanned_flag="unknown",
            recommended_mode="full",
            warnings=["Couldn't fully inspect this PDF; it will be processed normally."],
            allowed_actions=["continue", "remove_file"],
        )

    page_count = result.page_count
    file_size_mb = base["file_size_mb"]
    text_pages = round(result.text_ratio * page_count)
    ocr_pages = max(0, page_count - text_pages)

    warnings: list[str] = []
    verdict = "ok"

    large_by_pages = page_count > PREFLIGHT_WARN_PAGES
    large_by_size = file_size_mb > PREFLIGHT_WARN_SIZE_MB
    is_large = large_by_pages or large_by_size

    if page_count == 0:
        verdict = "warn"
        warnings.append("This PDF appears to have no readable pages.")

    if result.scanned_flag == "image_heavy":
        verdict = "warn"
        warnings.append(
            f"This PDF appears image-based (~{round(result.image_ratio * 100)}% of sampled pages "
            "have no text layer); OCR may take a long time."
        )
    elif result.scanned_flag == "mixed" and is_large:
        verdict = "warn"
        warnings.append(
            "This PDF is a mix of text and scanned pages; scanned pages will be OCR'd, which can be slow."
        )

    if large_by_pages:
        verdict = "warn"
        warnings.append(
            f"This PDF has {page_count} pages (over the {PREFLIGHT_WARN_PAGES}-page guidance); "
            "generation may be slow and the extracted text may be truncated to the configured limit."
        )
    if large_by_size:
        verdict = "warn"
        warnings.append(
            f"This PDF is {file_size_mb} MB (over the {PREFLIGHT_WARN_SIZE_MB:g} MB guidance); "
            "processing may be slow."
        )

    if ocr_pages > PREFLIGHT_OCR_PAGE_LIMIT:
        verdict = "warn"
        warnings.append(
            f"OCR would run on an estimated {ocr_pages} pages and may take a long time."
        )

    if result.scanned_flag in {"image_heavy", "mixed"} and not result.ocr_available:
        verdict = "warn"
        warnings.append(
            "OCR is unavailable in this environment, so scanned pages would yield little or no text."
        )

    if verdict == "ok":
        recommended_mode = "full"
        allowed_actions = ["continue"]
    else:
        recommended_mode = "first_n" if (result.scanned_flag == "image_heavy" or is_large) else "page_range"
        allowed_actions = ["continue"]
        if page_count > 0:
            allowed_actions += ["process_first_n", "choose_page_range"]
        allowed_actions.append("remove_file")

    return {
        **base,
        "page_count": page_count,
        "sampled_pages": result.sampled_pages,
        "text_pages_estimate": text_pages,
        "ocr_pages_estimate": ocr_pages,
        "image_ratio_est": result.image_ratio,
        "is_estimate": True,
        "scanned_flag": result.scanned_flag,
        "recommended_mode": recommended_mode,
        "ocr_available": result.ocr_available,
        "verdict": verdict,
        "warnings": warnings,
        "allowed_actions": allowed_actions,
    }


def _normalize_page_selections(raw: Any) -> dict[str, list[list[int]]]:
    """Validate + normalize the optional per-file PDF page-selection map.

    Shape: ``{filename: [[start, end], ...]}`` with 1-based inclusive ranges.
    Absent / ``None`` / empty ⇒ ``{}`` (= "all pages" = current behaviour). Each
    range must be a ``[start, end]`` pair of positive ints with ``start <= end``;
    ranges per file are sorted and overlapping/adjacent ones merged so the stored
    spec is canonical. Files / ranges are bounded (``MAX_PAGE_SELECTION_FILES`` /
    ``MAX_PAGE_RANGES_PER_FILE``). Invalid shapes raise a 400.

    Slice 3 NOTE: this is stored on the job and round-tripped through retry, but
    extraction does NOT consume it yet — no page filtering happens.
    """
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=400, detail="page_selections must be an object keyed by filename."
        )
    normalized: dict[str, list[list[int]]] = {}
    for filename, ranges in list(raw.items())[:MAX_PAGE_SELECTION_FILES]:
        if not isinstance(filename, str) or not filename.strip():
            raise HTTPException(
                status_code=400, detail="page_selections keys must be non-empty filenames."
            )
        if not isinstance(ranges, (list, tuple)):
            raise HTTPException(
                status_code=400,
                detail=f"page_selections['{filename}'] must be a list of [start, end] ranges.",
            )
        cleaned: list[list[int]] = []
        for pair in list(ranges)[:MAX_PAGE_RANGES_PER_FILE]:
            # bool is a subclass of int — reject it explicitly so True/False can't
            # masquerade as a page number.
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
                or isinstance(pair[0], bool)
                or isinstance(pair[1], bool)
                or not isinstance(pair[0], int)
                or not isinstance(pair[1], int)
            ):
                raise HTTPException(
                    status_code=400, detail="page ranges must be [start, end] integer pairs."
                )
            start, end = int(pair[0]), int(pair[1])
            if start < 1 or end < start:
                raise HTTPException(
                    status_code=400,
                    detail="page ranges must use positive 1-based pages with start <= end.",
                )
            cleaned.append([start, end])
        if not cleaned:
            # An explicit empty list means "no selection for this file" → omit it
            # so the stored map only carries real selections.
            continue
        cleaned.sort()
        merged: list[list[int]] = []
        for start, end in cleaned:
            if merged and start <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        normalized[filename] = merged
    return normalized


def _safe_page_selections(raw: Any) -> dict[str, list[list[int]]]:
    """Defensive read of a stored page-selection map for API responses. Never
    raises (unlike :func:`_normalize_page_selections`); a malformed manifest value
    degrades to ``{}``."""
    if not isinstance(raw, dict):
        return {}
    safe: dict[str, list[list[int]]] = {}
    for filename, ranges in raw.items():
        if not isinstance(filename, str) or not isinstance(ranges, list):
            continue
        pairs: list[list[int]] = []
        for pair in ranges:
            if (
                isinstance(pair, (list, tuple))
                and len(pair) == 2
                and all(isinstance(n, int) and not isinstance(n, bool) for n in pair)
            ):
                pairs.append([int(pair[0]), int(pair[1])])
        if pairs:
            safe[filename] = pairs
    return safe


def _validate_provider_model(provider: str, model: str) -> None:
    valid, message = validate_provider_model(provider, model)
    if valid:
        return
    raise HTTPException(status_code=400, detail=message or "Unsupported provider or model.")


def _job_error(exc: Exception, job: Job | None = None) -> HTTPException:
    detail: dict[str, Any] = {"message": _safe_log_line(str(exc))}
    if job is not None:
        detail["job"] = job_response(job)
    return HTTPException(status_code=500, detail=detail)


def _get_job(job_id: str) -> Job:
    if "/" in job_id or "\\" in job_id or job_id in {"", ".", ".."}:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = Job(job_id)
    try:
        job_dir = job.dir.resolve()
        jobs_dir = JOBS_DIR.resolve()
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc

    if not job_dir.is_relative_to(jobs_dir) or not job.manifest.exists():
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _require_trashed_job(job_id: str) -> str:
    """Validate an id (same slash/dot rejection as :func:`_get_job`) and confirm
    it is CURRENTLY in the trash. 404 otherwise — you cannot permanently delete
    or restore something that hasn't been trashed first.
    """
    if "/" in job_id or "\\" in job_id or job_id in {"", ".", ".."}:
        raise HTTPException(status_code=404, detail="Trashed job not found.")
    if not is_trashed(job_id):
        raise HTTPException(status_code=404, detail="Trashed job not found.")
    return job_id


def _artifact_availability(job: Job) -> dict[str, bool]:
    return {
        "clean_md": job.clean_md.exists(),
        "final_html": job.final_html.exists(),
        "final_pdf": job.final_pdf.exists(),
        # DOCX is generated lazily from clean.md, so it is "available" (i.e.
        # downloadable) whenever a clean.md exists, even if the file isn't on
        # disk yet — the first request/bundle generates it.
        "final_docx": job.final_docx.exists() or job.clean_md.exists(),
        "validation_json": _validation_json_path(job).exists(),
        "render_log": job.render_log.exists(),
    }


def _ensure_docx(job: Job, *, regenerate: bool = False) -> Path | None:
    """Lazily generate final.docx from clean.md. Returns the path, or None if
    there is no clean.md to convert. Raises on a genuine conversion failure.
    """
    if not job.clean_md.exists():
        return None
    if job.final_docx.exists() and not regenerate:
        return job.final_docx
    from pipeline.docx_renderer import render_docx

    manifest = job.read_manifest()
    render_docx(
        job.clean_md,
        job.final_docx,
        title=manifest.get("title"),
        generated_date=manifest.get("created_at"),
    )
    return job.final_docx


def _artifact_path(job: Job, artifact_name: str) -> tuple[Path, str]:
    artifact = ARTIFACTS.get(artifact_name)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    key, media_type = artifact
    if key == "validation_json":
        return _validation_json_path(job), media_type
    return getattr(job, key), media_type


def _content_disposition(disposition: str, filename: str) -> str:
    disposition = disposition.lower().strip()
    if disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=400, detail="Unsupported artifact disposition.")

    safe_filename = filename.replace("\\", "").replace('"', "")
    return f'{disposition}; filename="{safe_filename}"'


def _validation_json_path(job: Job) -> Path:
    manifest = job.read_manifest()
    manifest_path = manifest.get("validation_json")
    candidates = [
        Path(manifest_path) if manifest_path else None,
        job.logs_dir / "validation.json",
        job.validation_json,
    ]
    for path in candidates:
        if path is not None and _is_job_path(job, path) and path.exists():
            return path
    return job.logs_dir / "validation.json"


def _is_job_path(job: Job, path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(job.dir.resolve())
    except OSError:
        return False


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# Serve the built React frontend same-origin in Docker/production. This mount is
# registered after every explicit /api route above, so API routes take precedence.
_FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
