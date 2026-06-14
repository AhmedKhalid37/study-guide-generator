#!/usr/bin/env python3
"""Focused tests for the ``source_coverage_report.json`` artifact writer.

Run with:

    python test_scripts/test_source_coverage_artifact.py

Synthetic dictionaries and temp job directories only. No PDFs, images,
providers, renderers, OCR engines, or model calls are required.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\\.gguf|llama-server)")
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_sourcecoverageartifact1234567890",
    "synthetic boom with private details",
]

from pipeline.job_manager import Job  # noqa: E402
from pipeline.run_llm_job import AttachmentSource, _attach_sources  # noqa: E402
import pipeline.run_llm_job as run_llm_job  # noqa: E402
from pipeline.source_coverage_artifact import (  # noqa: E402
    SOURCE_COVERAGE_REPORT_FILENAME,
    write_skipped_source_coverage_report,
    write_source_coverage_report,
)


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


def _make_job(root: str, job_id: str = "job-source-coverage") -> Job:
    job = Job(id=job_id, root=Path(root))
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "created"})
    return job


def _metadata() -> dict[str, Any]:
    return {
        "version": 2,
        "kind": "extraction_metadata",
        "status": "completed",
        "sources": [
            {
                "filename": "private-source.pdf",
                "title": "Quarterly Private Plan",
                "path": "/home/example/private-source.pdf",
                "content_type": "application/pdf",
                "page_count": 3,
                "pages": [
                    _page(1, "embedded_text", 80, 12, anchor=True),
                    _page(2, "ocr", 50, 7),
                    _page(3, "none", 0, 0),
                ],
            }
        ],
    }


def _page(page: int, method: str, chars: int, words: int, *, anchor: bool = False) -> dict[str, Any]:
    return {
        "page": page,
        "method": method,
        "text_chars": chars,
        "word_count": words,
        "has_page_anchor": anchor,
        "text": "raw document paragraph",
        "ocr_text": "raw OCR dump",
        "caption": "source caption text",
        "table_text": "table cell text",
        "api_key": "sk_sourcecoverageartifact1234567890",
        "url": "https://example.invalid/private-source.pdf",
        "argv": "--model /home/example/model.gguf --mmproj /home/example/mmproj.gguf",
        "socket": "/tmp/private.sock",
        "image_ref": "assets/secret.png",
        "bytes": "data:image/png;base64,AAAA",
    }


def _scan_for_leak(node: Any, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            lower = str(key).lower()
            if lower in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            if lower in {"filename", "path", "title", "text", "ocr_text", "caption", "table_text", "image_ref"}:
                return f"{path}.{key} (forbidden field)"
            found = _scan_for_leak(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_leak(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        for canary in FORBIDDEN_CANARIES:
            if canary in node:
                return f"{path} (canary leaked: {canary})"
        if KEYLIKE.search(node):
            return f"{path} (credential-like value)"
        if PATHLIKE.search(node):
            return f"{path} (path-like value)"
        if URLLIKE.search(node):
            return f"{path} (URL-like value)"
        if DATA_OR_BASE64.search(node):
            return f"{path} (data/base64-like value)"
        if ARGV_OR_SOCKET.search(node):
            return f"{path} (argv/socket/model-like value)"
    return None


def _read_report(job: Job) -> dict[str, Any]:
    return json.loads(job.source_coverage_report_json.read_text(encoding="utf-8"))


def test_writes_completed_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_source_coverage_report(job, _metadata())
        path = job.source_coverage_report_json
        check("artifact name constant", SOURCE_COVERAGE_REPORT_FILENAME == "source_coverage_report.json")
        check("artifact file written", path.exists() and path.is_file())
        check("artifact filename exact", path.name == SOURCE_COVERAGE_REPORT_FILENAME)
        check("artifact under job dir", path.resolve().is_relative_to(job.dir.resolve()))
        check("returned status completed-or-partial", report.get("status") in {"completed", "partial"})
        on_disk = _read_report(job)
        check("on-disk equals returned report", on_disk == report)
        check("summary source count", on_disk["summary"]["source_count"] == 1, str(on_disk))
        check("summary page count", on_disk["summary"]["total_pages"] == 3, str(on_disk))
        check("no leak in completed artifact", _scan_for_leak(on_disk) is None, _scan_for_leak(on_disk) or "")


def test_skipped_extraction_metadata_writes_safe_skipped_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_source_coverage_report(
            job,
            {
                "version": 2,
                "kind": "extraction_metadata",
                "status": "skipped",
                "reason": "metadata_unavailable",
                "safe_message": "Extraction metadata could not be collected.",
            },
        )
        on_disk = _read_report(job)
        check("skipped status", on_disk.get("status") == "skipped", str(on_disk))
        check("skipped warning token", on_disk.get("warnings") == ["metadata_skipped"], str(on_disk))
        check("skipped no sources", on_disk.get("sources") == [], str(on_disk))
        check("skipped returned equals disk", report == on_disk)
        check("skipped no leak", _scan_for_leak(on_disk) is None, _scan_for_leak(on_disk) or "")


def test_malformed_metadata_degrades_safely() -> None:
    for label, bad in {"none": None, "string": "bad", "wrong_kind": {"kind": "other"}}.items():
        with tempfile.TemporaryDirectory() as tmp:
            job = _make_job(tmp, f"job-malformed-{label}")
            report = write_source_coverage_report(job, bad)
            check(f"malformed {label} status skipped", report.get("status") == "skipped", str(report))
            check(f"malformed {label} sources empty", report.get("sources") == [], str(report))
            check(f"malformed {label} persisted", _read_report(job) == report)


def test_visual_manifest_counts_and_malformed_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-visual-counts")
        report = write_source_coverage_report(
            job,
            _metadata(),
            visual_manifest={
                "version": 1,
                "kind": "visual_assets_manifest",
                "status": "completed",
                "assets": [
                    {"source_page": 1, "asset_id": "assets/secret.png"},
                    {"source_page": 1},
                    {"source_page": 2, "caption": "source caption text"},
                    {"source_page": 99},
                    "bad",
                ],
            },
        )
        check("visual unique positive source pages", report["summary"]["visual_candidate_pages"] == 2, str(report))
        check("visual out-of-range warning", "visual_page_out_of_range" in report["warnings"], str(report))
        check("visual malformed warning", "visual_manifest_malformed" in report["warnings"], str(report))
        check("visual no leak", _scan_for_leak(report) is None, _scan_for_leak(report) or "")

    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-visual-malformed")
        report = write_source_coverage_report(job, _metadata(), visual_manifest={"assets": {}})
        check("malformed visual does not fail", report.get("status") in {"completed", "partial"}, str(report))
        check("malformed visual warning emitted", "visual_manifest_malformed" in report["warnings"], str(report))


class _FailingJob(Job):
    def save_text(self, path, text):  # type: ignore[override]
        raise OSError("synthetic boom with private details sk-sourcecoverageartifact123456")


def test_write_failure_returns_safe_skipped_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _FailingJob(id="job-fail", root=Path(tmp))
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        report = write_source_coverage_report(job, _metadata())
        text = json.dumps(report, sort_keys=True)
        check("write failure status skipped", report.get("status") == "skipped", str(report))
        check("write failure warning closed", report.get("warnings") == ["metadata_skipped"], str(report))
        check("write failure raw message absent", "synthetic boom" not in text and "private details" not in text, text)
        check("write failure no artifact", not job.source_coverage_report_json.exists())


def test_explicit_skipped_writer_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        report = write_skipped_source_coverage_report(job)
        check("explicit skipped status", report.get("status") == "skipped", str(report))
        check("explicit skipped warning", report.get("warnings") == ["metadata_skipped"], str(report))
        check("explicit skipped persisted", _read_report(job) == report)
        report2 = write_skipped_source_coverage_report(
            job,
            reason="raw unsafe reason /home/example",
            safe_message="x",
        )
        check("unknown skipped reason not emitted", "raw unsafe reason" not in json.dumps(report2), str(report2))


def test_exact_name_route_and_no_generic_or_export_exposure() -> None:
    try:
        from api import server  # noqa: WPS433
    except Exception as exc:
        print(f"[SKIP] api.server endpoint section ({type(exc).__name__})")
        return

    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        path, media = server._artifact_path(job, "source_coverage_report.json")
        check("exact-name path resolves", path == job.source_coverage_report_json)
        check("exact-name media type json", media == "application/json")
        check("not in ARTIFACTS", "source_coverage_report.json" not in server.ARTIFACTS)
        check("not in EXPORT_ARTIFACTS", "source_coverage_report.json" not in server.EXPORT_ARTIFACTS)
        check("not in EXPORT aliases", "source_coverage_report.json" not in server.EXPORT_ARTIFACT_ALIASES)
        check("not in visual advisory export ride-alongs",
              "source_coverage_report.json" not in server.VISUAL_ADVISORY_EXPORT_ARTIFACTS)
        availability = server._artifact_availability(job)
        urls = server._artifact_urls(job, availability)
        check("not in _artifact_urls", "source_coverage_report.json" not in urls, str(urls))
        details = {d.get("name") for d in server._artifact_details(job, availability)}
        check("not in _artifact_details", "source_coverage_report.json" not in details, str(details))


@dataclass
class _FakeExtractionResult:
    text: str
    mode: str
    warnings: list[str]
    metadata: dict[str, Any]


def test_attach_sources_wires_writer_after_metadata_available() -> None:
    original_extract_file = run_llm_job.extract_file
    original_pdf_source_metadata = run_llm_job.pdf_source_metadata
    calls: list[dict[str, Any]] = []
    original_writer = run_llm_job.write_source_coverage_report

    def fake_extract_file(path: Path, *, pages=None):  # noqa: ANN001
        return _FakeExtractionResult(
            text="Synthetic extracted attachment text.",
            mode="pdf_text",
            warnings=[],
            metadata={"kind": "pdf_extraction", "page_count": 1, "pages": []},
        )

    def fake_pdf_source_metadata(**kwargs):  # noqa: ANN003
        return {
            "filename": "synthetic.pdf",
            "content_type": "application/pdf",
            "page_count": 1,
            "pages": [_page(1, "embedded_text", 80, 12, anchor=True)],
            "warnings": [],
        }

    def spy_writer(job: Job, extraction_metadata: Any, *, visual_manifest: Any = None):
        calls.append({"metadata": extraction_metadata, "visual_manifest": visual_manifest})
        return original_writer(job, extraction_metadata, visual_manifest=visual_manifest)

    with tempfile.TemporaryDirectory() as tmp:
        source_pdf = Path(tmp) / "upload.pdf"
        source_pdf.write_bytes(b"%PDF synthetic placeholder")
        job = _make_job(tmp, "job-wiring")
        run_llm_job.extract_file = fake_extract_file
        run_llm_job.pdf_source_metadata = fake_pdf_source_metadata
        run_llm_job.write_source_coverage_report = spy_writer
        try:
            augmented, report = _attach_sources(job, "Base source.", [AttachmentSource(path=source_pdf, filename="upload.pdf")])
        finally:
            run_llm_job.extract_file = original_extract_file
            run_llm_job.pdf_source_metadata = original_pdf_source_metadata
            run_llm_job.write_source_coverage_report = original_writer

        check("wiring writer called once", len(calls) == 1, str(calls))
        check("wiring after metadata artifact", job.extraction_metadata_json.exists())
        check("wiring visual manifest loaded", isinstance(calls[0].get("visual_manifest"), dict), str(calls))
        check("wiring source coverage artifact exists", job.source_coverage_report_json.exists())
        check("wiring text still attached", "## Attached Sources" in augmented and report["files"][0]["status"] == "extracted")


def test_attach_sources_writer_failure_does_not_fail_generation_path() -> None:
    original_extract_file = run_llm_job.extract_file
    original_pdf_source_metadata = run_llm_job.pdf_source_metadata
    original_writer = run_llm_job.write_source_coverage_report

    def fake_extract_file(path: Path, *, pages=None):  # noqa: ANN001
        return _FakeExtractionResult(
            text="Synthetic extracted attachment text.",
            mode="pdf_text",
            warnings=[],
            metadata={"kind": "pdf_extraction", "page_count": 1, "pages": []},
        )

    def fake_pdf_source_metadata(**kwargs):  # noqa: ANN003
        return {
            "filename": "synthetic.pdf",
            "content_type": "application/pdf",
            "page_count": 1,
            "pages": [_page(1, "embedded_text", 80, 12, anchor=True)],
            "warnings": [],
        }

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("synthetic boom with private details sk-sourcecoverageartifact123456")

    with tempfile.TemporaryDirectory() as tmp:
        source_pdf = Path(tmp) / "upload.pdf"
        source_pdf.write_bytes(b"%PDF synthetic placeholder")
        job = _make_job(tmp, "job-wiring-fail")
        run_llm_job.extract_file = fake_extract_file
        run_llm_job.pdf_source_metadata = fake_pdf_source_metadata
        run_llm_job.write_source_coverage_report = boom
        try:
            augmented, report = _attach_sources(job, "Base source.", [AttachmentSource(path=source_pdf, filename="upload.pdf")])
        finally:
            run_llm_job.extract_file = original_extract_file
            run_llm_job.pdf_source_metadata = original_pdf_source_metadata
            run_llm_job.write_source_coverage_report = original_writer

        check("writer failure job path still returns text", "## Attached Sources" in augmented)
        check("writer failure extraction still succeeded", report["files"][0]["status"] == "extracted", str(report))
        check("writer failure job not failed", job.read_manifest().get("status") == "created", str(job.read_manifest()))


def main() -> int:
    test_writes_completed_report()
    test_skipped_extraction_metadata_writes_safe_skipped_report()
    test_malformed_metadata_degrades_safely()
    test_visual_manifest_counts_and_malformed_warning()
    test_write_failure_returns_safe_skipped_report()
    test_explicit_skipped_writer_defaults()
    test_exact_name_route_and_no_generic_or_export_exposure()
    test_attach_sources_wires_writer_after_metadata_available()
    test_attach_sources_writer_failure_does_not_fail_generation_path()
    print(f"\nSource coverage artifact tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
