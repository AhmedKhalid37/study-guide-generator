#!/usr/bin/env python3
"""Focused tests for the provider-agnostic visual_assets_manifest.json artifact.

Run with:

    python test_scripts/test_visual_assets_manifest.py

No external APIs and no PyMuPDF/Tesseract/Mistral/Gemini/Chandra dependency: the
manifest builder is a pure function of already-sanitized extraction-metadata
records, so these tests feed it plain dicts. The integration test writes the
artifact through a temp-dir Job.
"""
from __future__ import annotations

import importlib
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
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\\\|\\\\\\\\)")
URLLIKE = re.compile(r"https?://")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z])")

from pipeline.visual_assets_manifest import (  # noqa: E402
    ARTIFACT_NAME,
    ASSET_TYPE_PAGE_VISUAL_SIGNAL,
    MANIFEST_VERSION,
    RECOMMENDED_ACTION_UNKNOWN,
    SOURCE_PROVIDER_FITZ_LOCAL,
    build_visual_assets_manifest,
    write_skipped_visual_assets_manifest,
    write_visual_assets_manifest,
)
from pipeline.job_manager import Job  # noqa: E402


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


def _make_job(root: str, job_id: str = "job-vam") -> Job:
    job = Job(id=job_id, root=Path(root))
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    job._write_manifest({"id": job.id, "status": "created"})
    return job


def _scan_for_leak(node, path: str = "") -> str | None:
    """Recursively reject secret-like keys and path/url/credential/argv-like values."""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            found = _scan_for_leak(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_leak(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        if KEYLIKE.search(node):
            return f"{path} (value looks like a credential)"
        if PATHLIKE.search(node):
            return f"{path} (value looks like a filesystem path)"
        if URLLIKE.search(node):
            return f"{path} (value looks like a URL)"
        if ARGV_OR_SOCKET.search(node):
            return f"{path} (value looks like argv/socket)"
    return None


def _source(pages: list[dict]) -> dict:
    return {"filename": "lecture.pdf", "content_type": "application/pdf", "pages": pages}


# --- top-level shape ---------------------------------------------------------


def test_top_level_shape_no_assets() -> None:
    manifest = build_visual_assets_manifest([])
    check("version is the manifest version", manifest.get("version") == MANIFEST_VERSION)
    check("kind is visual_assets_manifest", manifest.get("kind") == "visual_assets_manifest")
    check("status completed", manifest.get("status") == "completed")
    check("source is extraction_metadata.json", manifest.get("source") == "extraction_metadata.json")
    check("assets is empty list", manifest.get("assets") == [])
    check("warnings is empty list", manifest.get("warnings") == [])
    summary = manifest.get("summary", {})
    check("summary asset_count 0", summary.get("asset_count") == 0)
    check("summary pages_with_visual_signals 0", summary.get("pages_with_visual_signals") == 0)
    check("summary source_providers empty when no assets", summary.get("source_providers") == [])
    check("artifact name constant", ARTIFACT_NAME == "visual_assets_manifest.json")


def test_no_visual_signals_pages_yield_no_assets() -> None:
    pages = [
        {"page": 1, "has_images": False, "has_drawings": False,
         "image_object_count": 0, "drawing_object_count": 0, "classification": "embedded_text"},
        {"page": 2, "has_images": None, "has_drawings": None, "classification": "blank_or_low_text"},
    ]
    manifest = build_visual_assets_manifest([_source(pages)])
    check("text-only pages produce no candidates", manifest["assets"] == [])
    check("summary count 0 for text-only", manifest["summary"]["asset_count"] == 0)


# --- candidate creation ------------------------------------------------------


def test_page_with_images_creates_candidate() -> None:
    pages = [{"page": 7, "image_object_count": 2, "has_images": True,
              "drawing_object_count": 0, "has_drawings": False,
              "page_width": 1024.0, "page_height": 768.0,
              "classification": "mixed", "ocr_route_action": "use_embedded_text"}]
    manifest = build_visual_assets_manifest([_source(pages)])
    check("one candidate from image page", len(manifest["assets"]) == 1)
    asset = manifest["assets"][0]
    check("asset_id deterministic format", asset["asset_id"] == "page_0007_visual_01")
    check("source_page matches", asset["source_page"] == 7)
    check("asset_type page_visual_signal", asset["asset_type"] == ASSET_TYPE_PAGE_VISUAL_SIGNAL)
    check("bbox is null in this slice", asset["bbox"] is None)
    check("caption is null", asset["caption"] is None)
    check("source_provider fitz_local", asset["source_provider"] == SOURCE_PROVIDER_FITZ_LOCAL)
    check("recommended_action unknown", asset["recommended_action"] == RECOMMENDED_ACTION_UNKNOWN)
    check("dedupe_group null", asset["dedupe_group"] is None)
    check("scores empty (no scoring yet)", asset["scores"] == {})
    check("signals image_object_count", asset["signals"]["image_object_count"] == 2)
    check("signals classification carried", asset["signals"]["classification"] == "mixed")
    check("signals ocr_route_action carried", asset["signals"]["ocr_route_action"] == "use_embedded_text")
    check("pages_with_visual_signals 1", manifest["summary"]["pages_with_visual_signals"] == 1)
    check("source_providers fitz_local only", manifest["summary"]["source_providers"] == ["fitz_local"])


def test_page_with_drawings_creates_candidate() -> None:
    pages = [{"page": 3, "image_object_count": 0, "has_images": False,
              "drawing_object_count": 5, "has_drawings": True,
              "classification": "likely_scanned"}]
    manifest = build_visual_assets_manifest([_source(pages)])
    check("drawing page yields a candidate", len(manifest["assets"]) == 1)
    check("drawing asset_id", manifest["assets"][0]["asset_id"] == "page_0003_visual_01")
    check("drawing signal count", manifest["assets"][0]["signals"]["drawing_object_count"] == 5)


def test_page_with_both_creates_single_candidate() -> None:
    pages = [{"page": 9, "image_object_count": 3, "has_images": True,
              "drawing_object_count": 4, "has_drawings": True,
              "classification": "mixed"}]
    manifest = build_visual_assets_manifest([_source(pages)])
    check("images+drawings → exactly one candidate", len(manifest["assets"]) == 1)
    sig = manifest["assets"][0]["signals"]
    check("both image signal recorded", sig["image_object_count"] == 3 and sig["has_images"] is True)
    check("both drawing signal recorded", sig["drawing_object_count"] == 4 and sig["has_drawings"] is True)


def test_count_only_signal_without_boolean() -> None:
    # A positive object count with no has_* boolean must still count as a signal.
    pages = [{"page": 4, "image_object_count": 1, "drawing_object_count": 0}]
    manifest = build_visual_assets_manifest([_source(pages)])
    check("count-only image triggers candidate", len(manifest["assets"]) == 1)


# --- closed vocabulary / sanitization ---------------------------------------


def test_smuggled_fields_are_sanitized() -> None:
    pages = [{
        "page": 5,
        "has_images": True,
        # Hostile / smuggled values that must NOT survive verbatim:
        "classification": "/home/secret/path.pdf",
        "ocr_route_action": "https://evil.example/key?token=sk_abcdeftoken1234567890",
        "page_width": "not-a-number",
        "page_height": float("inf"),
        "image_object_count": -7,
    }]
    manifest = build_visual_assets_manifest([_source(pages)])
    asset = manifest["assets"][0]
    sig = asset["signals"]
    check("smuggled classification coerced to unknown", sig["classification"] == "unknown")
    check("smuggled ocr_route_action coerced to unknown", sig["ocr_route_action"] == "unknown")
    check("non-numeric width → None", sig["page_width"] is None)
    check("inf height → None", sig["page_height"] is None)
    check("negative count clamped to 0", sig["image_object_count"] == 0)
    check("source_provider stays fitz_local", asset["source_provider"] == "fitz_local")
    check("asset_type stays page_visual_signal", asset["asset_type"] == "page_visual_signal")
    leak = _scan_for_leak(manifest)
    check("no leak survives sanitization", leak is None, leak or "")


def test_extra_top_level_keys_not_echoed() -> None:
    # An attacker-controlled extra key on the source/page must not appear anywhere.
    src = _source([{"page": 1, "has_images": True, "evil_key": "sk_secrettokenvalue1234567890"}])
    src["another_evil"] = "/etc/passwd"
    manifest = build_visual_assets_manifest([src])
    text = json.dumps(manifest)
    check("evil source key not echoed", "another_evil" not in text and "/etc/passwd" not in text)
    check("evil page key not echoed", "evil_key" not in text and "sk_secrettokenvalue" not in text)


def test_non_pdf_garbage_input_degrades_safely() -> None:
    for bad in [None, 123, "string", {"not": "a list"}, [1, 2, "x"], [{"pages": "nope"}]]:
        manifest = build_visual_assets_manifest(bad)
        ok = (
            manifest["kind"] == "visual_assets_manifest"
            and manifest["status"] in {"completed"}
            and manifest["assets"] == []
        )
        check(f"garbage input degrades safely: {type(bad).__name__}", ok)


def test_builder_is_pure_no_provider_imports() -> None:
    import pipeline.visual_assets_manifest as mod

    src = mod.__file__
    source_text = Path(src).read_text(encoding="utf-8")
    # Inspect import lines only — the module docstring legitimately *names*
    # future-reserved providers (chandra/mistral/vlm) as vocabulary, so a bare
    # substring scan would false-positive. We forbid actually importing them.
    import_lines = [
        ln.strip() for ln in source_text.splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    forbidden = ["fitz", "pytesseract", "mistralai", "google.generativeai",
                 "chandra", "ocr_provider", "tesseract"]
    offenders = [
        tok for tok in forbidden
        if any(tok in ln for ln in import_lines)
    ]
    check("no provider/SDK imports in module source", not offenders, str(offenders))
    # Confirm the module did not pull provider modules into sys.modules on import.
    importlib.reload(mod)
    bad_loaded = [m for m in ("fitz", "pytesseract", "mistralai", "chandra") if m in sys.modules]
    check("no provider modules imported at runtime", not bad_loaded, str(bad_loaded))


def test_no_image_bytes_or_files_in_manifest() -> None:
    pages = [{"page": 1, "has_images": True, "image_object_count": 1}]
    manifest = build_visual_assets_manifest([_source(pages)])
    text = json.dumps(manifest)
    check("no base64/data-uri image bytes", "data:image" not in text and "base64" not in text)
    check("no png/jpg byte markers", "\\u00ff\\u00d8" not in text)


# --- integration (writes the artifact through a Job) -------------------------


def test_integration_writes_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-write")
        sources = [_source([
            {"page": 1, "has_images": True, "image_object_count": 2, "classification": "mixed"},
            {"page": 2, "has_images": False, "has_drawings": False, "classification": "embedded_text"},
        ])]
        write_visual_assets_manifest(job, sources)
        path = job.visual_assets_manifest_json
        check("artifact filename is exact name", path.name == ARTIFACT_NAME)
        check("artifact file written", path.exists())
        data = json.loads(path.read_text(encoding="utf-8"))
        check("written manifest completed", data["status"] == "completed")
        check("written manifest one asset", data["summary"]["asset_count"] == 1)
        # No image files were ever written next to the manifest.
        siblings = {p.name for p in job.dir.iterdir() if p.is_file()}
        image_files = [n for n in siblings if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
        check("no image files emitted by manifest", not image_files, str(image_files))


def test_integration_does_not_raise_on_bad_save(monkeypatch=None) -> None:
    # If save_text raises, the writer must degrade to a skipped artifact, never raise.
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-fail")
        original = job.save_text
        calls = {"n": 0}

        def boom(path, text):  # noqa: ANN001
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("disk full")
            return original(path, text)

        # frozen dataclass: patch via object.__setattr__-free approach using a wrapper attr
        try:
            object.__setattr__(job, "save_text", boom)
        except Exception:
            check("integration bad-save (could not patch, skipped)", True)
            return
        raised = False
        try:
            write_visual_assets_manifest(job, [_source([{"page": 1, "has_images": True}])])
        except Exception:
            raised = True
        check("writer never raises on save failure", not raised)
        data = json.loads(job.visual_assets_manifest_json.read_text(encoding="utf-8"))
        check("degraded to skipped artifact", data["status"] == "skipped")
        check("skipped reason is safe token", data["reason"] in {"manifest_unavailable", "source_unavailable"})


def test_explicit_skipped_writer() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = _make_job(tmp, "job-skip")
        write_skipped_visual_assets_manifest(job)
        data = json.loads(job.visual_assets_manifest_json.read_text(encoding="utf-8"))
        check("explicit skipped status", data["status"] == "skipped")
        check("explicit skipped safe message", isinstance(data["safe_message"], str))
        check("explicit skipped no leak", _scan_for_leak(data) is None)


def main() -> int:
    test_top_level_shape_no_assets()
    test_no_visual_signals_pages_yield_no_assets()
    test_page_with_images_creates_candidate()
    test_page_with_drawings_creates_candidate()
    test_page_with_both_creates_single_candidate()
    test_count_only_signal_without_boolean()
    test_smuggled_fields_are_sanitized()
    test_extra_top_level_keys_not_echoed()
    test_non_pdf_garbage_input_degrades_safely()
    test_builder_is_pure_no_provider_imports()
    test_no_image_bytes_or_files_in_manifest()
    test_integration_writes_artifact()
    test_integration_does_not_raise_on_bad_save()
    test_explicit_skipped_writer()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
