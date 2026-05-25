from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from pipeline import style_store
from pipeline.job_manager import JOBS_DIR, Job
from pipeline.llm_client import MissingLLMConfigError, generate_chat_completion
from pipeline.provider_config import (
    build_provider_config,
    get_provider_registry,
    resolve_provider_id,
    validate_provider_model,
)
from pipeline.run_llm_job import AttachmentSource, LLMJobError, run_llm_job
from pipeline.run_markdown_job import MarkdownJobError, run_markdown_job, run_pasted_text_job


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
    "validation.json": ("validation_json", "application/json"),
    "render.log": ("render_log", "text/plain; charset=utf-8"),
}
MAX_LLM_ATTACHMENTS = 5
MAX_LLM_ATTACHMENT_BYTES = 15 * 1024 * 1024


class PasteJobRequest(BaseModel):
    text: str
    theme: str = "claude_clean"
    strict_math: bool = True


class LLMJobRequest(BaseModel):
    source_text: str
    title: str = "Generated Study Guide"
    mode: str = "exam"
    prompt_name: str = "basic_study_guide"
    provider: str
    model: str
    theme: str = "claude_clean"
    strict_math: bool = True
    qwen_thinking: bool = True


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


@app.get("/api/jobs")
def list_jobs(limit: int = 20) -> dict[str, Any]:
    jobs = []
    if JOBS_DIR.exists():
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
                }
            )

    jobs.sort(
        key=lambda item: str(item.get("created_at") or item.get("id") or ""),
        reverse=True,
    )
    return {"jobs": jobs[: max(limit, 0)]}


@app.post("/api/jobs/paste")
def create_paste_job(request: PasteJobRequest) -> dict[str, Any]:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty.")
    _validate_theme(request.theme)

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
    return job_response(job)


@app.post("/api/jobs/upload-markdown")
def create_upload_markdown_job(
    file: UploadFile = File(...),
    theme: str = Form("claude_clean"),
    strict_math: bool = Form(True),
) -> dict[str, Any]:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".md", ".markdown"}:
        raise HTTPException(status_code=400, detail="file must be .md or .markdown.")
    _validate_theme(theme)

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

    try:
        config = build_provider_config(
            llm_request.provider,
            llm_request.model,
            qwen_thinking_enabled=llm_request.qwen_thinking,
        )
        job = run_llm_job(
            source_text,
            title=title,
            mode=llm_request.mode,
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
    return job_response(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    manifest = _safe_manifest(job.read_manifest())
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
    path, media_type = _artifact_path(job, artifact_name)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": _content_disposition(disposition, artifact_name)},
    )


def job_response(job: Job) -> dict[str, Any]:
    manifest = job.read_manifest()
    availability = _artifact_availability(job)
    artifact_urls = _artifact_urls(job, availability)
    return {
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
    }


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
    ]:
        safe.pop(key, None)
    safe["attachments"] = _safe_attachment_metadata(manifest.get("attachments", []))
    safe["extraction_warnings"] = _safe_warnings(manifest.get("extraction_warnings", []))
    safe["total_extracted_chars"] = int(manifest.get("total_extracted_chars") or 0)
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
            "mode": _form_text(form, "mode") or "exam",
            "prompt_name": _form_text(form, "prompt_name") or _form_text(form, "style") or "basic_study_guide",
            "provider": _form_text(form, "provider") or "",
            "model": _form_text(form, "model") or "",
            "theme": _form_text(form, "theme") or "claude_clean",
            "strict_math": _form_bool(form, "strict_math", True),
            "qwen_thinking": _form_bool(form, "qwen_thinking", True),
        }
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
        "validation_json": _validation_json_path(job).exists(),
        "render_log": job.render_log.exists(),
    }


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
