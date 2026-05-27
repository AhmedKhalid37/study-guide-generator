from __future__ import annotations

import io
import json
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

from pipeline import library_store, style_store
from pipeline.job_manager import JOBS_DIR, Job
from pipeline.llm_client import LLMProviderError, MissingLLMConfigError, generate_chat_completion
from pipeline.markdown_sections import (
    check_outline_compliance,
    parse_sections,
    splice_section,
)
from pipeline.orchestrator import generate_study_guide
from pipeline.provider_config import (
    build_provider_config,
    get_provider_registry,
    resolve_provider_id,
    validate_provider_model,
)
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
    provider: str
    model: str
    theme: str = "claude_clean"
    strict_math: bool = True
    qwen_thinking: bool = True
    folder_id: str | None = None
    outline: OutlineData | None = None


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


class BatchMoveRequest(BaseModel):
    job_ids: list[str]
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
        "providers": [provider["display_name"] for provider in provider_details],
        "models": {
            provider["display_name"]: provider["available_models"]
            for provider in provider_details
        },
        "provider_details": provider_details,
        "providers_v2": provider_details,
    }


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

    jobs.sort(
        key=lambda item: str(item.get("created_at") or item.get("id") or ""),
        reverse=True,
    )
    return {"jobs": jobs[: max(limit, 0)]}


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
        return sorted(jobs, key=created_key)
    if sort == "title":
        return sorted(jobs, key=lambda job: str(job.get("title") or "").lower())
    if sort == "status":
        return sorted(jobs, key=lambda job: str(job.get("status") or ""))
    return sorted(jobs, key=created_key, reverse=True)


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
    folder_target = _resolve_folder_target(llm_request.folder_id)
    # Prepend a "Required Outline" directive into the source so it works with any
    # style (the {source} slot is the one injection point every template shares).
    source_text = _apply_outline_directive(source_text, llm_request.outline)

    try:
        config = build_provider_config(
            llm_request.provider,
            llm_request.model,
            qwen_thinking_enabled=llm_request.qwen_thinking,
        )
        job = run_llm_job(
            source_text,
            title=title,
            mode=(llm_request.mode or DEFAULT_MODE),
            prompt_name=llm_request.prompt_name,
            theme=llm_request.theme,
            strict_math=llm_request.strict_math,
            config=config,
            attachments=attachments,
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
    return job_response(job)


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

        try:
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
    safe["total_extracted_chars"] = int(manifest.get("total_extracted_chars") or 0)
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
            "provider": _form_text(form, "provider") or "",
            "model": _form_text(form, "model") or "",
            "theme": _form_text(form, "theme") or "claude_clean",
            "strict_math": _form_bool(form, "strict_math", True),
            "qwen_thinking": _form_bool(form, "qwen_thinking", True),
            "folder_id": _form_text(form, "folder_id"),
        }
        outline_raw = _form_text(form, "outline")
        if outline_raw:
            try:
                data["outline"] = json.loads(outline_raw)
            except json.JSONDecodeError:
                data["outline"] = None
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


def _form_bool(form: Any, key: str, default: bool) -> bool:
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


def _validate_provider_model(provider: str, model: str) -> None:
    valid, message = validate_provider_model(provider, model)
    if valid:
        return
    raise HTTPException(status_code=400, detail=message or "Unsupported provider or model.")


def _job_error(exc: Exception, job: Job | None = None) -> HTTPException:
    detail: dict[str, Any] = {"message": str(exc)}
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

    render_docx(job.clean_md, job.final_docx)
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
