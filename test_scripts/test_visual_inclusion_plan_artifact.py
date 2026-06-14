#!/usr/bin/env python3
"""Focused tests for the ``visual_inclusion_plan.json`` artifact writer (Slice 84).

Run with:

    python test_scripts/test_visual_inclusion_plan_artifact.py

Synthetic dictionaries and temp job directories only. No PDFs, images, providers,
renderers, OCR engines, or model calls are required. The artifact wraps the pure
Slice 83 planner (``pipeline.visual_inclusion_planner.build_visual_inclusion_plan``)
and only adds safe exact-name persistence.
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
FORBIDDEN_KEY_NAMES = {
    "filename", "path", "title", "text", "ocr_text", "caption", "table_text",
    "image_ref", "asset_ref", "asset_id", "url", "argv", "socket", "bytes",
}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_visualinclusionplan1234567890",
    "synthetic boom with private details",
]

from pipeline.job_manager import Job  # noqa: E402
from pipeline.run_llm_job import AttachmentSource, _attach_sources  # noqa: E402
import pipeline.run_llm_job as run_llm_job  # noqa: E402
from pipeline.visual_inclusion_plan_artifact import (  # noqa: E402
    VISUAL_INCLUSION_PLAN_FILENAME,
    write_visual_inclusion_plan,
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


def _make_job(root: str, job_id: str = "job-visual-inclusion-plan") -> Job:
    job = Job(id=job_id, root=Path(root))
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "created"})
    return job


def _leaky_fields() -> dict[str, Any]:
    """Hostile fields a manifest record might carry; the planner must NOT echo them."""
    return {
        "filename": "private-source.pdf",
        "title": "Quarterly Private Plan",
        "path": "/home/example/private-source.pdf",
        "text": "raw document paragraph",
        "ocr_text": "raw OCR dump",
        "caption": "source caption text",
        "table_text": "table cell text",
        "image_ref": "assets/secret.png",
        "asset_ref": "assets/secret.png",
        "url": "https://example.invalid/private-source.pdf",
        "argv": "--model /home/example/model.gguf --mmproj /home/example/mmproj.gguf",
        "socket": "/tmp/private.sock",
        "bytes": "data:image/png;base64,AAAA",
        "api_key": "sk_visualinclusionplan1234567890",
    }


def _figure(source_index: int, source_page: int, *, asset_id: str | None = None) -> dict[str, Any]:
    rec = dict(_leaky_fields())
    rec.update(
        {
            "asset_type": "extracted_figure",
            "source_index": source_index,
            "source_page": source_page,
        }
    )
    if asset_id is not None:
        rec["asset_id"] = asset_id
    return rec


def _table(source_index: int, source_page: int) -> dict[str, Any]:
    rec = dict(_leaky_fields())
    rec.update(
        {
            "asset_type": "extracted_figure",
            "visual_kind": "table",
            "source_index": source_index,
            "source_page": source_page,
        }
    )
    return rec


def _manifest(assets: list[Any], status: str = "completed") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": status,
        "assets": assets,
    }


def _scan_for_leak(node: Any, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            lower = str(key).lower()
            if lower in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            if lower in FORBIDDEN_KEY_NAMES:
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


def _read_plan(job: Job) -> dict[str, Any]:
    return json.loads(job.visual_inclusion_plan_json.read_text(encoding="utf-8"))


def test_writes_plan_from_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        manifest = _manifest([
            _figure(0, 1, asset_id="a1"),
            _figure(0, 2, asset_id="a2"),
            _figure(1, 1, asset_id="a3"),
        ])
        plan = write_visual_inclusion_plan(job, manifest)
        path = job.visual_inclusion_plan_json
        check("artifact name constant", VISUAL_INCLUSION_PLAN_FILENAME == "visual_inclusion_plan.json")
        check("artifact file written", path.exists() and path.is_file())
        check("artifact filename exact", path.name == VISUAL_INCLUSION_PLAN_FILENAME)
        check("artifact under job dir", path.resolve().is_relative_to(job.dir.resolve()))
        check("plan kind", plan.get("kind") == "visual_inclusion_plan", str(plan))
        check("plan status completed", plan.get("status") == "completed", str(plan))
        on_disk = _read_plan(job)
        check("on-disk equals returned plan", on_disk == plan)
        check("plans all 3 eligible (not top-1/2)", on_disk["summary"]["planned_count"] == 3, str(on_disk))
        check("non_table_planned_count 3", on_disk["summary"]["non_table_planned_count"] == 3, str(on_disk))
        check("no leak in plan artifact", _scan_for_leak(on_disk) is None, _scan_for_leak(on_disk) or "")


def test_default_plans_all_useful_non_table() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-all")
        # 5 useful figures + 1 table → planner must plan all 5, not a top-1/2 cap.
        assets = [_figure(0, p, asset_id=f"f{p}") for p in range(1, 6)]
        assets.append(_table(0, 6))
        plan = write_visual_inclusion_plan(job, _manifest(assets))
        check("default plans all 5 useful", plan["summary"]["planned_count"] == 5, str(plan["summary"]))
        check("default status completed (no cap)", plan["status"] == "completed", str(plan))
        check("default no max_items_applied", "max_items_applied" not in plan["warnings"], str(plan))


def test_table_like_records_skipped_and_counted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-table")
        plan = write_visual_inclusion_plan(
            job,
            _manifest([_figure(0, 1, asset_id="f1"), _table(0, 2), _table(0, 3)]),
        )
        check("table-like skipped", plan["summary"]["planned_count"] == 1, str(plan["summary"]))
        check("table-like counted", plan["summary"]["table_like_skipped_count"] == 2, str(plan["summary"]))
        check("table warning token", "visual_type_table_skipped" in plan["warnings"], str(plan))


def test_decorative_tiny_blank_unsafe_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-junk")
        decorative = dict(_leaky_fields())
        decorative.update({"asset_type": "extracted_figure", "visual_kind": "logo",
                           "source_index": 0, "source_page": 1})
        tiny = dict(_leaky_fields())
        tiny.update({"asset_type": "extracted_figure", "source_index": 0, "source_page": 2,
                     "signals": {"crop_width_px": 10, "crop_height_px": 10}})
        blank = dict(_leaky_fields())
        blank.update({"asset_type": "page_visual_signal", "source_index": 0, "source_page": 3,
                      "signals": {"classification": "blank_or_low_text"}})
        unsafe = dict(_leaky_fields())
        unsafe.update({"asset_type": "extracted_figure", "source_index": 0, "source_page": 4,
                       "unsafe": True})
        good = _figure(0, 5, asset_id="g1")
        plan = write_visual_inclusion_plan(job, _manifest([decorative, tiny, blank, unsafe, good]))
        check("only the safe useful figure planned", plan["summary"]["planned_count"] == 1, str(plan["summary"]))
        check("decorative warning", "visual_record_decorative" in plan["warnings"], str(plan))
        check("tiny warning", "visual_record_tiny" in plan["warnings"], str(plan))
        check("low-info warning", "visual_record_low_information" in plan["warnings"], str(plan))
        check("unsafe warning", "visual_record_unsafe" in plan["warnings"], str(plan))


def test_missing_manifest_writes_safe_skipped_plan() -> None:
    for label, manifest in {
        "none": None,
        "skipped": _manifest([], status="skipped"),
    }.items():
        with tempfile.TemporaryDirectory() as tmp:
            job = _make_job(tmp, f"job-missing-{label}")
            plan = write_visual_inclusion_plan(job, manifest)
            check(f"{label}: status skipped", plan.get("status") == "skipped", str(plan))
            check(f"{label}: zero planned", plan["summary"]["planned_count"] == 0, str(plan))
            check(f"{label}: persisted", _read_plan(job) == plan)
            check(f"{label}: no leak", _scan_for_leak(plan) is None, _scan_for_leak(plan) or "")


def test_malformed_manifest_degrades_safely() -> None:
    for label, bad in {"string": "bad", "list": [1, 2, 3], "int": 5,
                       "wrong_assets": {"assets": {}}}.items():
        with tempfile.TemporaryDirectory() as tmp:
            job = _make_job(tmp, f"job-malformed-{label}")
            plan = write_visual_inclusion_plan(job, bad)
            check(f"malformed {label} status skipped", plan.get("status") == "skipped", str(plan))
            check(f"malformed {label} no items", plan.get("items") == [], str(plan))
            check(f"malformed {label} persisted", _read_plan(job) == plan)
            check(f"malformed {label} no leak", _scan_for_leak(plan) is None, "")


def test_safe_candidate_id_mapping() -> None:
    # Slice 90 adds a safe generated ``candidate_id`` to every item so the
    # full-insertion path can map a planned item back to its sanitized manifest
    # record WITHOUT the plan ever carrying a filename/path/slug/ref. This pins that
    # the id is a fixed-shape sequential ordinal and that nothing else widened the
    # item schema or leaked a ref.
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-schema")
        plan = write_visual_inclusion_plan(job, _manifest([_figure(0, 1, asset_id="a1")]))
        item = plan["items"][0]
        allowed = {"plan_index", "candidate_id", "source_index", "source_page",
                   "visual_kind", "inclusion_role", "reason", "warnings"}
        check("item keys whitelisted", set(item.keys()) <= allowed, str(item.keys()))
        check("candidate_id present", "candidate_id" in item, str(item.keys()))
        cid = item.get("candidate_id")
        check("candidate_id is safe generated ordinal",
              isinstance(cid, str) and cid.startswith("visual_candidate_"), str(cid))
        check("candidate_id carries no ref/path/slug", _scan_for_leak(item) is None,
              _scan_for_leak(item) or "")
        check("source_page is an int", isinstance(item["source_page"], int), str(item))


class _FailingJob(Job):
    def save_text(self, path, text):  # type: ignore[override]
        raise OSError("synthetic boom with private details sk_visualinclusionplan1234567890")


def test_write_failure_degrades_never_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _FailingJob(id="job-fail", root=Path(tmp))
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        plan = write_visual_inclusion_plan(job, _manifest([_figure(0, 1, asset_id="a1")]))
        text = json.dumps(plan, sort_keys=True)
        check("write failure returns a plan", isinstance(plan, dict) and plan.get("kind") == "visual_inclusion_plan")
        check("write failure raw message absent", "synthetic boom" not in text and "private details" not in text)
        check("write failure no artifact file", not job.visual_inclusion_plan_json.exists())


def test_deterministic_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job_a = _make_job(tmp, "job-det-a")
        job_b = _make_job(tmp, "job-det-b")
        manifest = _manifest([_figure(0, 2, asset_id="a"), _figure(0, 1, asset_id="b"),
                              _table(0, 3), _figure(1, 1, asset_id="c")])
        write_visual_inclusion_plan(job_a, manifest)
        write_visual_inclusion_plan(job_b, manifest)
        check("deterministic serialization", _read_plan(job_a) == _read_plan(job_b))


def test_exact_name_route_and_no_generic_or_export_exposure() -> None:
    try:
        from api import server  # noqa: WPS433
    except Exception as exc:
        print(f"[SKIP] api.server endpoint section ({type(exc).__name__})")
        return

    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp)
        path, media = server._artifact_path(job, "visual_inclusion_plan.json")
        check("exact-name path resolves", path == job.visual_inclusion_plan_json)
        check("exact-name media type json", media == "application/json")
        check("not in ARTIFACTS", "visual_inclusion_plan.json" not in server.ARTIFACTS)
        check("not in EXPORT_ARTIFACTS", "visual_inclusion_plan.json" not in server.EXPORT_ARTIFACTS)
        check("not in EXPORT aliases", "visual_inclusion_plan.json" not in server.EXPORT_ARTIFACT_ALIASES)
        check("not in visual advisory export ride-alongs",
              "visual_inclusion_plan.json" not in server.VISUAL_ADVISORY_EXPORT_ARTIFACTS)
        availability = server._artifact_availability(job)
        urls = server._artifact_urls(job, availability)
        check("not in _artifact_urls", "visual_inclusion_plan.json" not in urls, str(urls))
        details = {d.get("name") for d in server._artifact_details(job, availability)}
        check("not in _artifact_details", "visual_inclusion_plan.json" not in details, str(details))


@dataclass
class _FakeExtractionResult:
    text: str
    mode: str
    warnings: list[str]
    metadata: dict[str, Any]


def test_attach_sources_wires_writer_after_manifest_available() -> None:
    original_extract_file = run_llm_job.extract_file
    original_pdf_source_metadata = run_llm_job.pdf_source_metadata
    original_writer = run_llm_job.write_visual_inclusion_plan
    calls: list[dict[str, Any]] = []

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
            "pages": [{"page": 1, "method": "embedded_text", "text_chars": 80,
                       "word_count": 12, "has_page_anchor": True}],
            "warnings": [],
        }

    def spy_writer(job: Job, visual_manifest: Any = None):
        calls.append({"visual_manifest": visual_manifest})
        return original_writer(job, visual_manifest=visual_manifest)

    with tempfile.TemporaryDirectory() as tmp:
        source_pdf = Path(tmp) / "upload.pdf"
        source_pdf.write_bytes(b"%PDF synthetic placeholder")
        job = _make_job(tmp, "job-wiring")
        run_llm_job.extract_file = fake_extract_file
        run_llm_job.pdf_source_metadata = fake_pdf_source_metadata
        run_llm_job.write_visual_inclusion_plan = spy_writer
        try:
            augmented, report = _attach_sources(
                job, "Base source.", [AttachmentSource(path=source_pdf, filename="upload.pdf")]
            )
        finally:
            run_llm_job.extract_file = original_extract_file
            run_llm_job.pdf_source_metadata = original_pdf_source_metadata
            run_llm_job.write_visual_inclusion_plan = original_writer

        check("wiring writer called once", len(calls) == 1, str(calls))
        check("wiring after manifest", job.visual_assets_manifest_json.exists())
        check("wiring plan artifact exists", job.visual_inclusion_plan_json.exists())
        check("wiring text still attached",
              "## Attached Sources" in augmented and report["files"][0]["status"] == "extracted")
        on_disk = _read_plan(job)
        check("wiring plan kind", on_disk.get("kind") == "visual_inclusion_plan", str(on_disk))
        check("wiring plan no leak", _scan_for_leak(on_disk) is None, _scan_for_leak(on_disk) or "")


def test_attach_sources_writer_failure_does_not_fail_generation_path() -> None:
    original_extract_file = run_llm_job.extract_file
    original_pdf_source_metadata = run_llm_job.pdf_source_metadata
    original_writer = run_llm_job.write_visual_inclusion_plan

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
            "pages": [{"page": 1, "method": "embedded_text", "text_chars": 80,
                       "word_count": 12, "has_page_anchor": True}],
            "warnings": [],
        }

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("synthetic boom with private details sk_visualinclusionplan1234567890")

    with tempfile.TemporaryDirectory() as tmp:
        source_pdf = Path(tmp) / "upload.pdf"
        source_pdf.write_bytes(b"%PDF synthetic placeholder")
        job = _make_job(tmp, "job-wiring-fail")
        run_llm_job.extract_file = fake_extract_file
        run_llm_job.pdf_source_metadata = fake_pdf_source_metadata
        run_llm_job.write_visual_inclusion_plan = boom
        try:
            augmented, report = _attach_sources(
                job, "Base source.", [AttachmentSource(path=source_pdf, filename="upload.pdf")]
            )
        finally:
            run_llm_job.extract_file = original_extract_file
            run_llm_job.pdf_source_metadata = original_pdf_source_metadata
            run_llm_job.write_visual_inclusion_plan = original_writer

        check("writer failure job path still returns text", "## Attached Sources" in augmented)
        check("writer failure extraction still succeeded",
              report["files"][0]["status"] == "extracted", str(report))
        check("writer failure job not failed",
              job.read_manifest().get("status") == "created", str(job.read_manifest()))


def test_no_clean_md_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-clean")
        clean_before = job.clean_md.exists()
        write_visual_inclusion_plan(job, _manifest([_figure(0, 1, asset_id="a1")]))
        check("no clean.md written by plan artifact", job.clean_md.exists() == clean_before)


def main() -> int:
    test_writes_plan_from_manifest()
    test_default_plans_all_useful_non_table()
    test_table_like_records_skipped_and_counted()
    test_decorative_tiny_blank_unsafe_skipped()
    test_missing_manifest_writes_safe_skipped_plan()
    test_malformed_manifest_degrades_safely()
    test_safe_candidate_id_mapping()
    test_write_failure_degrades_never_fails()
    test_deterministic_output()
    test_exact_name_route_and_no_generic_or_export_exposure()
    test_attach_sources_wires_writer_after_manifest_available()
    test_attach_sources_writer_failure_does_not_fail_generation_path()
    test_no_clean_md_write()
    print(f"\nVisual inclusion plan artifact tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
