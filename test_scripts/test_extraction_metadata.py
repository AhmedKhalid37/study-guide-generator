#!/usr/bin/env python3
"""Focused tests for the per-job extraction_metadata.json artifact.

Run with:

    python test_scripts/test_extraction_metadata.py

No external APIs. Requires PyMuPDF (fitz) for the synthetic PDF fixture and
SKIPS cleanly if unavailable.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)


try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from pipeline.extract import extract_file  # noqa: E402
from pipeline.extraction_metadata import (  # noqa: E402
    pdf_source_metadata,
    write_extraction_metadata,
    write_skipped_extraction_metadata,
)
from pipeline.job_manager import Job  # noqa: E402
from pipeline.run_llm_job import AttachmentSource, _attach_sources  # noqa: E402
import pipeline.run_llm_job as run_llm_job  # noqa: E402


TEXT_PAGES = [
    "Page one contains enough embedded selectable text for extraction metadata.",
    "Page two contains enough embedded selectable text for extraction metadata.",
]


def _build_text_pdf(path: Path) -> None:
    if fitz is None:
        raise RuntimeError("PyMuPDF unavailable")
    doc = fitz.open()
    for body in TEXT_PAGES:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), body, fontsize=14)
    doc.save(str(path))
    doc.close()


def _make_job(root: str, job_id: str = "job-test") -> Job:
    job = Job(id=job_id, root=Path(root))
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "created"})
    return job


def _read_artifact(job: Job) -> dict:
    return json.loads(job.extraction_metadata_json.read_text(encoding="utf-8"))


def _scan_for_secret(node, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            found = _scan_for_secret(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_secret(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str) and KEYLIKE.search(node):
        return f"{path} (value looks like a credential)"
    return None


def test_helper_writes_completed_metadata_without_pdf_dependency() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-helper")
        source = pdf_source_metadata(
            filename="lecture.pdf",
            content_type="application/pdf",
            extraction_metadata={
                "kind": "pdf_extraction",
                "page_count": 1,
                "pages": [
                    {
                        "page": 1,
                        "method": "embedded_text",
                        "text_chars": 55,
                        "word_count": 8,
                        "has_page_anchor": True,
                        "warnings": [],
                    }
                ],
                "warnings": [],
            },
        )
        check("helper/source-built", source is not None, str(source))
        write_extraction_metadata(job, [source] if source else [])
        check("helper/artifact-exists", job.extraction_metadata_json.exists())
        artifact = _read_artifact(job)
        check("helper/status", artifact.get("status") == "completed", str(artifact))
        check("helper/source-count", len(artifact.get("sources") or []) == 1, str(artifact))
        check("helper/no-secret-leak", _scan_for_secret(artifact) is None, str(artifact))


def test_helper_writes_skipped_metadata_without_pdf_dependency() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-helper-skipped")
        write_skipped_extraction_metadata(job)
        check("helper-skipped/artifact-exists", job.extraction_metadata_json.exists())
        artifact = _read_artifact(job)
        check("helper-skipped/status", artifact.get("status") == "skipped", str(artifact))
        check("helper-skipped/reason", artifact.get("reason") == "metadata_unavailable", str(artifact))
        check("helper-skipped/no-secret-leak", _scan_for_secret(artifact) is None, str(artifact))


def test_pdf_attachment_writes_completed_metadata() -> None:
    if fitz is None:
        print("[SKIP] completed PDF attachment metadata - PyMuPDF (fitz) unavailable")
        return
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "lecture.pdf"
        _build_text_pdf(pdf)
        direct = extract_file(pdf)
        job = _make_job(tmp)

        augmented, report = _attach_sources(
            job,
            "Base source.",
            [AttachmentSource(path=pdf, filename="lecture.pdf")],
        )

        check("completed/artifact-exists", job.extraction_metadata_json.exists())
        artifact = _read_artifact(job)
        check("completed/version", artifact.get("version") == 2, str(artifact.get("version")))
        check("completed/kind", artifact.get("kind") == "extraction_metadata", str(artifact.get("kind")))
        check("completed/status", artifact.get("status") == "completed", str(artifact.get("status")))
        sources = artifact.get("sources") or []
        check("completed/source-count", len(sources) == 1, str(sources))
        source = sources[0] if sources else {}
        check("completed/source-filename", source.get("filename") == "lecture.pdf", str(source))
        check("completed/content-type", source.get("content_type") == "application/pdf", str(source))
        check("completed/page-count", source.get("page_count") == 2, str(source))
        pages = source.get("pages") or []
        check("completed/page-records", len(pages) == 2, str(pages))
        check("completed/page-1-method", pages and pages[0].get("method") == "embedded_text", str(pages[:1]))
        check("completed/page-1-anchor", pages and pages[0].get("has_page_anchor") is True, str(pages[:1]))
        check("completed/page-1-chars", pages and pages[0].get("text_chars") == len(TEXT_PAGES[0]), str(pages[:1]))
        check("completed/page-1-words", pages and pages[0].get("word_count", 0) >= 8, str(pages[:1]))
        check("completed/source-warnings", source.get("warnings") == [], str(source.get("warnings")))
        # Slice 30: additive visual/object signals are present for real PDF pages.
        page1 = pages[0] if pages else {}
        check("completed/visual-image-count", page1.get("image_object_count") == 0, str(page1))
        check("completed/visual-drawing-count-present", "drawing_object_count" in page1, str(page1))
        check("completed/visual-has-images", page1.get("has_images") is False, str(page1))
        check("completed/visual-has-drawings", "has_drawings" in page1, str(page1))
        check(
            "completed/visual-page-width",
            isinstance(page1.get("page_width"), (int, float)) and page1.get("page_width") > 0,
            str(page1),
        )
        check(
            "completed/visual-page-height",
            isinstance(page1.get("page_height"), (int, float)) and page1.get("page_height") > 0,
            str(page1),
        )
        # Healthy pages carry no degrade warnings for visual collection.
        check("completed/visual-no-warnings", "visual_warnings" not in page1, str(page1))
        check("completed/no-secret-leak", _scan_for_secret(artifact) is None, str(artifact)[:200])

        # Extraction text behavior is unchanged: _attach_sources includes exactly
        # the extractor output under the attachment section.
        check("text/direct-output-preserved", direct.text.strip() in augmented)
        check("text/report-status", report["files"][0]["status"] == "extracted", str(report["files"]))
        check("text/report-mode", report["files"][0]["mode"] == "pdf_text", str(report["files"]))
        check("validation/untouched", not job.validation_json.exists())
        check("math-verification/untouched", not job.math_verification_json.exists())


def test_metadata_failure_degrades_to_skipped() -> None:
    if fitz is None:
        print("[SKIP] metadata failure during PDF attachment extraction - PyMuPDF (fitz) unavailable")
        return
    original = run_llm_job.pdf_source_metadata

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("synthetic metadata failure with secret sk-abcdef0123456789xyz")

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "lecture.pdf"
        _build_text_pdf(pdf)
        job = _make_job(tmp, "job-skipped")
        run_llm_job.pdf_source_metadata = _boom
        try:
            augmented, report = _attach_sources(
                job,
                "Base source.",
                [AttachmentSource(path=pdf, filename="lecture.pdf")],
            )
        finally:
            run_llm_job.pdf_source_metadata = original

        check("skipped/artifact-exists", job.extraction_metadata_json.exists())
        artifact = _read_artifact(job)
        check("skipped/status", artifact.get("status") == "skipped", str(artifact))
        check("skipped/reason", artifact.get("reason") == "metadata_unavailable", str(artifact))
        check("skipped/safe-message", bool(artifact.get("safe_message")), str(artifact))
        raw = job.extraction_metadata_json.read_text(encoding="utf-8")
        check("skipped/no-traceback", "Traceback" not in raw and "RuntimeError" not in raw, raw)
        check("skipped/no-exc-message", "synthetic metadata failure" not in raw, raw)
        check("skipped/no-secret-leak", _scan_for_secret(artifact) is None, str(artifact))
        check("skipped/job-not-failed", job.read_manifest().get("status") == "created")
        check("skipped/text-still-attached", "## Attached Sources" in augmented)
        check("skipped/extraction-still-succeeded", report["files"][0]["status"] == "extracted", str(report["files"]))


def test_artifact_route_safe() -> None:
    try:
        import api.server as server  # noqa: PLC0415
    except Exception as exc:
        print(f"[SKIP] route/import - FastAPI unavailable ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        job.extraction_metadata_json.write_text(
            json.dumps({"version": 1, "kind": "extraction_metadata", "status": "completed", "sources": []}),
            encoding="utf-8",
        )
        path, media = server._artifact_path(job, "extraction_metadata.json")
        check("route/path", path == job.extraction_metadata_json, str(path))
        check("route/media-json", media == "application/json", media)
        check("route/not-in-ARTIFACTS", "extraction_metadata.json" not in server.ARTIFACTS)
        avail = server._artifact_availability(job)
        urls = server._artifact_urls(job, avail)
        check("route/not-in-urls", "extraction_metadata.json" not in urls, str(urls))
        details_names = {d["name"] for d in server._artifact_details(job, avail)}
        check("route/not-in-details", "extraction_metadata.json" not in details_names, str(details_names))


if __name__ == "__main__":
    test_helper_writes_completed_metadata_without_pdf_dependency()
    test_helper_writes_skipped_metadata_without_pdf_dependency()
    test_pdf_attachment_writes_completed_metadata()
    test_metadata_failure_degrades_to_skipped()
    test_artifact_route_safe()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"Extraction metadata tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
