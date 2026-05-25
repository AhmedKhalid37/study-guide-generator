from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from pipeline.job_manager import JOBS_DIR, Job
from pipeline.llm_client import MissingLLMConfigError
from pipeline.provider_config import build_provider_config, get_provider_registry, validate_provider_model
from pipeline.run_llm_job import LLMJobError, run_llm_job
from pipeline.run_markdown_job import MarkdownJobError, run_markdown_job, run_pasted_text_job


app = FastAPI(title="Study Guide Generator API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

THEMES = ["claude_clean"]
INPUT_MODES = ["upload_markdown", "paste_text", "generate_llm"]
STYLE_PRESETS = [
    "basic_study_guide",
    "baby_steps",
    "exam_cram",
    "mcq_training",
    "final_solution",
    "claude_study_guide",
    "master_longform",
]
ARTIFACTS = {
    "clean.md": ("clean_md", "text/markdown; charset=utf-8"),
    "final.html": ("final_html", "text/html; charset=utf-8"),
    "final.pdf": ("final_pdf", "application/pdf"),
    "validation.json": ("validation_json", "application/json"),
    "render.log": ("render_log", "text/plain; charset=utf-8"),
}


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


@app.get("/api/jobs")
def list_jobs(limit: int = 20) -> dict[str, Any]:
    jobs = []
    if JOBS_DIR.exists():
        for manifest_path in JOBS_DIR.glob("*/job.json"):
            manifest = _read_json(manifest_path)
            if manifest is None:
                continue
            job_id = str(manifest.get("id") or manifest_path.parent.name)
            jobs.append(
                {
                    **manifest,
                    "id": job_id,
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
def create_llm_job(request: LLMJobRequest) -> dict[str, Any]:
    source_text = request.source_text.strip()
    title = request.title.strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="source_text must not be empty.")
    if not title:
        raise HTTPException(status_code=400, detail="title must not be empty.")
    _validate_theme(request.theme)
    _validate_prompt_name(request.prompt_name)
    _validate_provider_model(request.provider, request.model)

    try:
        config = build_provider_config(
            request.provider,
            request.model,
            qwen_thinking_enabled=request.qwen_thinking,
        )
        job = run_llm_job(
            source_text,
            title=title,
            mode=request.mode,
            prompt_name=request.prompt_name,
            theme=request.theme,
            strict_math=request.strict_math,
            config=config,
        )
    except MissingLLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMJobError as exc:
        raise _job_error(exc, job=getattr(exc, "job", None)) from exc
    except Exception as exc:
        raise _job_error(exc) from exc
    return job_response(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    manifest = job.read_manifest()
    return {
        "job": manifest,
        "artifact_availability": _artifact_availability(job),
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
    artifact_urls = {
        artifact_name: f"/api/jobs/{job.id}/artifacts/{artifact_name}"
        for artifact_name, (key, _media_type) in ARTIFACTS.items()
        if availability.get(key)
    }
    return {
        "job_id": job.id,
        "status": manifest.get("status"),
        "title": manifest.get("title"),
        "provider": manifest.get("provider"),
        "model": manifest.get("model"),
        "created_at": manifest.get("created_at"),
        "artifact_availability": availability,
        "artifact_urls": artifact_urls,
    }


def _validate_theme(theme: str) -> None:
    if theme not in THEMES:
        raise HTTPException(status_code=400, detail="Unsupported theme.")


def _validate_prompt_name(prompt_name: str) -> None:
    if prompt_name not in STYLE_PRESETS:
        raise HTTPException(status_code=400, detail="Unsupported prompt_name.")


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
