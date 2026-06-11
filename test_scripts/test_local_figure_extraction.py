#!/usr/bin/env python3
"""Focused tests for Slice 40 local figure extraction into the visual manifest.

Run with:

    python test_scripts/test_local_figure_extraction.py

Two layers:
  * **Pure (always runs):** the manifest's re-sanitisation of ``extracted_figure``
    records — bbox validity, deterministic id slugging, safe relative image refs,
    leak prevention, and byte-compatible behaviour when no figures are supplied.
    Plus the gating helper. No PyMuPDF needed (we feed plain dicts).
  * **fitz-backed (skips if PyMuPDF is missing):** the real extractor against a
    synthetic in-memory PDF — actual crop files, bbox-within-page, tiny/duplicate
    explosion prevention, and per-page/per-job caps. Full coverage runs in Docker
    where ``fitz`` is installed; the host run skips this layer cleanly.
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
SKIP = 0

# Leak detectors (mirror test_visual_assets_manifest.py).
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\\\|\.\./)")
URLLIKE = re.compile(r"https?://")

from pipeline.visual_assets_manifest import (  # noqa: E402
    ASSET_TYPE_EXTRACTED_FIGURE,
    ASSET_TYPE_PAGE_VISUAL_SIGNAL,
    SOURCE_PROVIDER_FITZ_LOCAL,
    build_visual_assets_manifest,
    write_visual_assets_manifest,
)
from pipeline.visual_asset_extractor import (  # noqa: E402
    MAX_FIGURES_PER_PAGE,
    MIN_SIDE_POINTS,
    ENABLE_ENV,
    extract_local_figures,
    local_figure_extraction_enabled,
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


def skip(name: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name} - {why}")


def _valid_figure(**over):
    base = {
        "asset_id": "s00_page_0001_figure_01",
        "source_page": 1,
        "asset_type": "extracted_figure",
        "bbox": [10.0, 20.0, 110.0, 220.0],
        "image_ref": "assets/s00_page_0001_figure_01.png",
        "signals": {
            "page_width": 612.0,
            "page_height": 792.0,
            "image_index": 0,
            "crop_width_px": 200,
            "crop_height_px": 400,
        },
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------- #
# Layer 1 — pure manifest re-sanitisation / merge (no fitz)                    #
# --------------------------------------------------------------------------- #

def test_merge_and_summary() -> None:
    sources = [{"pages": [{"page": 1, "image_object_count": 1, "has_images": True}]}]
    manifest = build_visual_assets_manifest(sources, [_valid_figure()])
    types = [a["asset_type"] for a in manifest["assets"]]
    check("page candidate still present", ASSET_TYPE_PAGE_VISUAL_SIGNAL in types)
    check("extracted_figure merged in", ASSET_TYPE_EXTRACTED_FIGURE in types)
    check("asset_count counts both", manifest["summary"]["asset_count"] == 2)
    check("extracted_figure_count is 1", manifest["summary"]["extracted_figure_count"] == 1)
    check(
        "source_providers fitz_local",
        manifest["summary"]["source_providers"] == [SOURCE_PROVIDER_FITZ_LOCAL],
    )
    fig = next(a for a in manifest["assets"] if a["asset_type"] == ASSET_TYPE_EXTRACTED_FIGURE)
    check("bbox preserved/ordered", fig["bbox"] == [10.0, 20.0, 110.0, 220.0])
    check("image_ref preserved", fig["image_ref"] == "assets/s00_page_0001_figure_01.png")
    check("figure caption null", fig["caption"] is None)
    check("figure scores empty", fig["scores"] == {})


def test_none_is_backward_compatible() -> None:
    sources = [{"pages": [{"page": 1, "image_object_count": 1, "has_images": True}]}]
    none_manifest = build_visual_assets_manifest(sources, None)
    empty_manifest = build_visual_assets_manifest(sources, [])
    check("None == [] extracted", none_manifest == empty_manifest)
    check("no extracted assets", none_manifest["summary"]["extracted_figure_count"] == 0)
    check(
        "only page candidates remain",
        all(a["asset_type"] == ASSET_TYPE_PAGE_VISUAL_SIGNAL for a in none_manifest["assets"]),
    )


def test_bad_image_ref_dropped() -> None:
    bad_refs = [
        "/home/user/secret.png",          # absolute host path
        "assets/../../etc/passwd.png",    # traversal
        "../assets/x.png",                # traversal
        "https://evil.test/x.png",        # url
        "assets/x.jpg",                   # wrong extension
        "assets/x.png ",                  # trailing space
        "asset/x.png",                    # wrong prefix
        None,
        12345,
    ]
    for ref in bad_refs:
        manifest = build_visual_assets_manifest([], [_valid_figure(image_ref=ref)])
        check(f"dropped figure with bad ref {ref!r}", manifest["summary"]["extracted_figure_count"] == 0)


def test_bad_bbox_coerced_to_none() -> None:
    for bad in [[1, 2, 3], [0, 0, 0, 0], [10, 10, 5, 20], ["a", 1, 2, 3],
                [float("nan"), 0, 1, 1], "10,20,30,40", None]:
        manifest = build_visual_assets_manifest([], [_valid_figure(bbox=bad)])
        figs = [a for a in manifest["assets"] if a["asset_type"] == ASSET_TYPE_EXTRACTED_FIGURE]
        # The asset is still kept (id + ref valid) but bbox degrades to None.
        check(f"bbox {bad!r} -> None, asset kept", len(figs) == 1 and figs[0]["bbox"] is None)


def test_asset_id_slugged() -> None:
    manifest = build_visual_assets_manifest(
        [], [_valid_figure(asset_id="../etc/passwd; rm -rf /")]
    )
    figs = [a for a in manifest["assets"] if a["asset_type"] == ASSET_TYPE_EXTRACTED_FIGURE]
    check("asset_id slugged to safe chars", len(figs) == 1 and re.fullmatch(r"[A-Za-z0-9_]+", figs[0]["asset_id"]) is not None)
    manifest2 = build_visual_assets_manifest([], [_valid_figure(asset_id="!!!")])
    check("empty slug drops asset", manifest2["summary"]["extracted_figure_count"] == 0)


def test_no_leak_from_smuggled_fields() -> None:
    hostile = _valid_figure(
        api_key="sk-livesecretsecretsecret1234567890",
        path="/home/attacker/private.pdf",
        url="https://exfil.example/leak",
        signals={
            "page_width": 612.0,
            "image_index": 0,
            "secret": "sk-anothersecretsecretsecret999999",
            "host_path": "/etc/shadow",
        },
    )
    manifest = build_visual_assets_manifest([], [hostile])
    blob = json.dumps(manifest)
    check("no smuggled api_key key", '"api_key"' not in blob)
    check("no smuggled path key", '"path"' not in blob and '"host_path"' not in blob)
    check("no key-like secret leaks", KEYLIKE.search(blob) is None)
    check("no host path leaks", PATHLIKE.search(blob) is None)
    check("no url leaks", URLLIKE.search(blob) is None)
    fig = next(a for a in manifest["assets"] if a["asset_type"] == ASSET_TYPE_EXTRACTED_FIGURE)
    check(
        "signals whitelisted",
        set(fig["signals"]) == {"page_width", "page_height", "image_index", "crop_width_px", "crop_height_px"},
    )


def test_write_merges_and_no_image_bytes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job = Job(id="job-fig", root=Path(tmp))
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        job._write_manifest({"id": job.id, "status": "created"})
        write_visual_assets_manifest(
            job,
            [{"pages": [{"page": 2, "image_object_count": 1, "has_images": True}]}],
            [_valid_figure(source_page=2)],
        )
        text = job.visual_assets_manifest_json.read_text()
        data = json.loads(text)
        check("written manifest completed", data["status"] == "completed")
        check("written has extracted figure", data["summary"]["extracted_figure_count"] == 1)
        check("no base64/data-uri in manifest", "data:image" not in text and "base64" not in text)
        check("no PNG byte marker in manifest", "\x89PNG" not in text)


def test_gating_helper() -> None:
    saved = os.environ.pop(ENABLE_ENV, None)
    try:
        check("disabled by default", local_figure_extraction_enabled() is False)
        for truthy in ("1", "true", "YES", "On"):
            os.environ[ENABLE_ENV] = truthy
            check(f"enabled for {truthy!r}", local_figure_extraction_enabled() is True)
        for falsy in ("0", "false", "no", "", "off"):
            os.environ[ENABLE_ENV] = falsy
            check(f"disabled for {falsy!r}", local_figure_extraction_enabled() is False)
    finally:
        os.environ.pop(ENABLE_ENV, None)
        if saved is not None:
            os.environ[ENABLE_ENV] = saved


# --------------------------------------------------------------------------- #
# Layer 2 — real fitz extractor (skips if PyMuPDF missing)                     #
# --------------------------------------------------------------------------- #

def _png_bytes(width: int, height: int, color=(200, 30, 30)):
    """Tiny self-contained PNG without Pillow (raw zlib-compressed RGB)."""
    import struct
    import zlib

    raw = bytearray()
    row = bytes(color) * width
    for _ in range(height):
        raw += b"\x00" + row

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


def test_real_extractor() -> None:
    try:
        import fitz  # noqa: F401
    except Exception:
        skip("real fitz extractor", "PyMuPDF not installed (runs in Docker)")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        pdf_path = tmpdir / "synthetic.pdf"
        assets_dir = tmpdir / "assets"

        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        big = _png_bytes(120, 160)
        tiny = _png_bytes(8, 8)
        # One clearly-large figure (well above MIN_SIDE_POINTS).
        page.insert_image(fitz.Rect(50, 50, 300, 400), stream=big)
        # A duplicate placement of the SAME region (must collapse to one).
        page.insert_image(fitz.Rect(50, 50, 300, 400), stream=big)
        # A tiny decorative image (must be skipped).
        page.insert_image(fitz.Rect(5, 5, 5 + MIN_SIDE_POINTS / 2, 5 + MIN_SIDE_POINTS / 2), stream=tiny)
        doc.save(str(pdf_path))
        doc.close()

        assets = extract_local_figures(
            pdf_path, assets_dir=assets_dir, source_index=0, pages=None
        )
        check("at least one figure extracted", len(assets) >= 1)
        check("tiny + duplicate collapsed to one", len(assets) == 1, f"got {len(assets)}")
        if assets:
            fig = assets[0]
            check("type is extracted_figure", fig["asset_type"] == ASSET_TYPE_EXTRACTED_FIGURE)
            check("image_ref is relative assets/*.png", re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", fig["image_ref"]) is not None)
            check("crop file exists", (assets_dir / Path(fig["image_ref"]).name).exists())
            x0, y0, x1, y1 = fig["bbox"]
            check("bbox within page", 0 <= x0 < x1 <= 612 and 0 <= y0 < y1 <= 792)
            check("bbox above min size", (x1 - x0) >= MIN_SIDE_POINTS and (y1 - y0) >= MIN_SIDE_POINTS)

        # Determinism: same PDF, fresh dir → identical ids/bboxes.
        assets2 = extract_local_figures(
            pdf_path, assets_dir=tmpdir / "assets2", source_index=0, pages=None
        )
        check(
            "deterministic ids + bboxes",
            [(a["asset_id"], a["bbox"]) for a in assets] == [(a["asset_id"], a["bbox"]) for a in assets2],
        )


def test_per_page_cap() -> None:
    try:
        import fitz  # noqa: F401
    except Exception:
        skip("per-page cap", "PyMuPDF not installed (runs in Docker)")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        pdf_path = tmpdir / "many.pdf"
        doc = fitz.open()
        page = doc.new_page(width=2000, height=2000)
        img = _png_bytes(60, 60)
        # Lay out many large, non-overlapping figures (more than the per-page cap).
        placed = 0
        for r in range(6):
            for c in range(6):
                if placed >= MAX_FIGURES_PER_PAGE + 8:
                    break
                x = 20 + c * 320
                y = 20 + r * 320
                page.insert_image(fitz.Rect(x, y, x + 280, y + 280), stream=img)
                placed += 1
        doc.save(str(pdf_path))
        doc.close()

        assets = extract_local_figures(
            pdf_path, assets_dir=tmpdir / "assets", source_index=0, pages=None
        )
        check("per-page cap enforced", len(assets) <= MAX_FIGURES_PER_PAGE, f"got {len(assets)}")


def main() -> int:
    test_merge_and_summary()
    test_none_is_backward_compatible()
    test_bad_image_ref_dropped()
    test_bad_bbox_coerced_to_none()
    test_asset_id_slugged()
    test_no_leak_from_smuggled_fields()
    test_write_merges_and_no_image_bytes()
    test_gating_helper()
    test_real_extractor()
    test_per_page_cap()
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
