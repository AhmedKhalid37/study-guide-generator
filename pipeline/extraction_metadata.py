from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pipeline.job_manager import Job

ARTIFACT_NAME = "extraction_metadata.json"


def pdf_source_metadata(
    *,
    filename: str,
    content_type: str,
    extraction_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build a source-level artifact entry from PDF extraction metadata."""
    if not isinstance(extraction_metadata, dict):
        return None
    if extraction_metadata.get("kind") != "pdf_extraction":
        return None
    pages = extraction_metadata.get("pages")
    if not isinstance(pages, list):
        return None
    return {
        "filename": Path(filename).name,
        "content_type": content_type,
        "page_count": int(extraction_metadata.get("page_count") or 0),
        "pages": [_safe_page(page) for page in pages if isinstance(page, dict)],
        "warnings": _safe_warnings(extraction_metadata.get("warnings", [])),
    }


def write_extraction_metadata(job: Job, sources: list[dict[str, Any]]) -> None:
    """Persist per-job extraction metadata, degrading safely on failure.

    This helper is advisory-only. It never raises to the caller and never mutates
    job status or validation artifacts. Unexpected errors produce a small skipped
    artifact when possible; logs include only the exception type name.
    """
    if not sources:
        return

    artifact_path = job.extraction_metadata_json
    try:
        payload = {
            "version": 1,
            "kind": "extraction_metadata",
            "status": "completed",
            "sources": sources,
        }
        job.save_text(artifact_path, json.dumps(payload, indent=2) + "\n")
    except Exception as exc:  # never let metadata break a job
        _write_skipped(job, "metadata_unavailable", "Extraction metadata could not be collected.")
        print(
            f"Extraction metadata skipped ({type(exc).__name__}); job continues.",
            file=sys.stderr,
        )


def write_skipped_extraction_metadata(
    job: Job,
    *,
    reason: str = "metadata_unavailable",
    safe_message: str = "Extraction metadata could not be collected.",
) -> None:
    """Best-effort public wrapper for callers that need an explicit skipped file."""
    _write_skipped(job, reason, safe_message)


def _write_skipped(job: Job, reason: str, safe_message: str) -> None:
    try:
        payload = {
            "version": 1,
            "kind": "extraction_metadata",
            "status": "skipped",
            "reason": reason,
            "safe_message": safe_message,
        }
        job.save_text(job.extraction_metadata_json, json.dumps(payload, indent=2) + "\n")
    except Exception:
        pass


def _safe_page(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": int(page.get("page") or 0),
        "method": _safe_method(page.get("method")),
        "text_chars": max(0, int(page.get("text_chars") or 0)),
        "word_count": max(0, int(page.get("word_count") or 0)),
        "has_page_anchor": bool(page.get("has_page_anchor")),
        "warnings": _safe_warnings(page.get("warnings", [])),
    }


def _safe_method(method: Any) -> str:
    value = str(method or "unknown")
    if value in {"embedded_text", "ocr", "none", "unknown"}:
        return value
    return "unknown"


def _safe_warnings(warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    return [str(warning)[:300] for warning in warnings if warning]
