from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from pipeline.job_manager import JOBS_DIR, Job


app = FastAPI(title="Study Guide Generator API")

THEMES = ["claude_clean"]
INPUT_MODES = ["upload_markdown", "paste_text", "generate_llm"]
STYLE_PRESETS = [
    "basic_study_guide",
    "baby_steps",
    "exam_cram",
    "mcq_training",
    "final_solution",
    "claude_study_guide",
]
DEEPSEEK_MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
]
QWEN_MODELS = [
    "qwen3.7-max",
    "qwen3.6-plus",
    "qwen3-max",
    "qwen3.6-max-preview",
    "qwen-plus",
    "qwen-max",
]

ARTIFACTS = {
    "clean.md": ("clean_md", "text/markdown"),
    "final.html": ("final_html", "text/html"),
    "final.pdf": ("final_pdf", "application/pdf"),
    "validation.json": ("validation_json", "application/json"),
    "render.log": ("render_log", "text/plain"),
}


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/options")
def options() -> dict[str, Any]:
    return {
        "themes": THEMES,
        "input_modes": INPUT_MODES,
        "styles": STYLE_PRESETS,
        "providers": ["DeepSeek", "Qwen"],
        "models": {
            "DeepSeek": DEEPSEEK_MODELS,
            "Qwen": QWEN_MODELS,
        },
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


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    manifest = job.read_manifest()
    return {
        "job": manifest,
        "artifact_availability": _artifact_availability(job),
    }


@app.get("/api/jobs/{job_id}/artifacts/{artifact_name}")
def get_artifact(job_id: str, artifact_name: str) -> FileResponse:
    job = _get_job(job_id)
    path, media_type = _artifact_path(job, artifact_name)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(path, media_type=media_type, filename=artifact_name)


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
