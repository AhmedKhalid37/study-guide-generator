#!/usr/bin/env python3
"""Focused tests for the minimal visual markdown image pilot (Slice 54).

Run with the flag OFF (default):

    python test_scripts/test_visual_markdown_insertion.py

Run a few flag-ON cases too:

    GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1 python test_scripts/test_visual_markdown_insertion.py

The pilot helper is a near-pure function of an already-sanitized clean.md plus the
job's already-produced (sanitized) visual advisory artifacts. These tests feed it
tiny *handcrafted synthetic* manifests / plans and a temp job dir holding a tiny
real PNG written by the test (a 1x1 PNG byte literal) — no model dumps, private
documents, screenshots from the app, OCR text, image bytes from a provider, or
local host paths are used. The PNG bytes never appear in any assertion or output.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

# Leak detectors — none of these may appear anywhere in the inserted markdown.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
BASE64URI = re.compile(r"data:[^;]+;base64,")
GGUFLIKE = re.compile(r"\.gguf\b|mmproj", re.IGNORECASE)

from pipeline import visual_markdown_insertion as vmi  # noqa: E402

# A minimal valid 1x1 PNG (transparent). Used only so the on-disk file gate has a
# real PNG to find; the bytes are never asserted on or emitted into any artifact.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


@dataclass(frozen=True)
class FakeJob:
    """Duck-typed stand-in exposing only what the pilot reads."""

    dir: Path

    @property
    def visual_assets_manifest_json(self) -> Path:
        return self.dir / "visual_assets_manifest.json"

    @property
    def visual_replacement_plan_json(self) -> Path:
        return self.dir / "visual_replacement_plan.json"

    @property
    def assets_dir(self) -> Path:
        return self.dir / "assets"


def _figure_asset(asset_id: str, *, image_ref: str, page: int = 3, caption=None) -> dict:
    return {
        "asset_id": asset_id,
        "source_page": page,
        "asset_type": "extracted_figure",
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "caption": caption,
        "source_provider": "fitz_local",
        "image_ref": image_ref,
        "scores": {},
        "signals": {},
        "warnings": [],
    }


def _manifest(assets: list[dict]) -> dict:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": "completed",
        "source": "extraction_metadata.json",
        "assets": assets,
        "summary": {"asset_count": len(assets)},
        "warnings": [],
    }


def _plan(items: list[dict]) -> dict:
    return {
        "version": 1,
        "kind": "visual_replacement_plan",
        "status": "completed",
        "source": "visual_asset_scoring.json",
        "items": items,
        "summary": {},
        "warnings": [],
    }


def _plan_item(asset_id: str, *, action="candidate_include_as_figure",
               provider="fitz_local", atype="extracted_figure", reasons=None) -> dict:
    return {
        "asset_id": asset_id,
        "source_page": 3,
        "source_provider": provider,
        "asset_type": atype,
        "priority": "high",
        "candidate_action": action,
        "placement": "source_page_reference",
        "reasons": reasons or ["score_high", "asset_type_figure"],
        "warnings": [],
    }


def _make_job(tmp: Path, *, assets: list[dict] | None = None, plan_items=None,
              png_names: list[str] | None = None) -> FakeJob:
    job = FakeJob(dir=tmp)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for name in (png_names or []):
        (job.assets_dir / name).write_bytes(_PNG_1x1)
    if assets is not None:
        job.visual_assets_manifest_json.write_text(
            json.dumps(_manifest(assets)) + "\n", encoding="utf-8"
        )
    if plan_items is not None:
        job.visual_replacement_plan_json.write_text(
            json.dumps(_plan(plan_items)) + "\n", encoding="utf-8"
        )
    return job


def _leak_scan(name: str, text: str) -> None:
    for label, pat in (
        ("key", KEYLIKE), ("path", PATHLIKE), ("url", URLLIKE), ("auth", AUTHLIKE),
        ("socket", SOCKETLIKE), ("datauri", BASE64URI), ("gguf", GGUFLIKE),
    ):
        check(f"{name}.no_{label}", not pat.search(text), text[:120])


BASE_MD = "# Guide\n\nSome content.\n"


def run() -> None:
    # ---- flag gate -----------------------------------------------------------
    flag_on = vmi.is_visual_markdown_pilot_enabled()

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("s00_page_0003_figure_01", image_ref="assets/s00_page_0003_figure_01.png")],
            plan_items=[_plan_item("s00_page_0003_figure_01")],
            png_names=["s00_page_0003_figure_01.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        if not flag_on:
            check("flagoff.byte_identical", out == BASE_MD, repr(out[:80]))
            check("flagoff.reason_disabled", info.get("reason") == vmi.SKIP_DISABLED, str(info))
            check("flagoff.no_image", "![" not in out)
        else:
            check("flagon.inserted", info.get("status") == vmi.STATUS_INSERTED, str(info))
            check("flagon.has_image", "![" in out and "assets/s00_page_0003_figure_01.png" in out)

    # ---- validate_visual_asset_ref (pure, flag-independent) ------------------
    v = vmi.validate_visual_asset_ref
    check("ref.accepts_safe", v("assets/fig_01.png") == "assets/fig_01.png")
    check("ref.reject_absolute", v("/etc/passwd.png") is None)
    check("ref.reject_absolute_assets", v("/assets/fig.png") is None)
    check("ref.reject_dotdot", v("assets/../secret.png") is None)
    check("ref.reject_backslash", v("assets\\fig.png") is None)
    check("ref.reject_url", v("https://x/y.png") is None)
    check("ref.reject_datauri", v("data:image/png;base64,AAAA") is None)
    check("ref.reject_nonpng", v("assets/fig.jpg") is None)
    check("ref.reject_subdir", v("assets/sub/fig.png") is None)
    check("ref.reject_nonstr", v(None) is None and v(123) is None)
    check("ref.reject_empty", v("") is None)

    # ---- caption sanitization / length limit --------------------------------
    img = vmi.build_visual_markdown_image(
        {"asset_ref": "assets/fig_01.png", "source_page": 3, "caption": None}
    )
    check("caption.generic_default", img == "![Extracted figure from source page 3](assets/fig_01.png)", img)
    long_raw = "x" * 500 + "]](evil)(http://bad)"
    img2 = vmi.build_visual_markdown_image(
        {"asset_ref": "assets/fig_01.png", "source_page": 2, "caption": long_raw}
    )
    cap = img2[img2.index("[") + 1: img2.index("]")]
    check("caption.length_limited", len(cap) <= 80, str(len(cap)))
    check("caption.no_markup_chars", "]" not in cap and "[" not in cap, cap)
    check("caption.stripped_unsafe", "http" not in img2 and "evil" not in img2.split("](")[0])
    _leak_scan("caption", img2)

    # ---- the rest require the flag ON to exercise selection/insertion --------
    if not flag_on:
        # Prove flag-off does not insert even when artifacts + png exist.
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            job = _make_job(
                tmp,
                assets=[_figure_asset("a1", image_ref="assets/a1.png")],
                plan_items=[_plan_item("a1")],
                png_names=["a1.png"],
            )
            out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
            check("flagoff.artifacts_present_still_noop", out == BASE_MD)
        _summary()
        return

    # ===== flag-ON behaviour =====
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png")],
            plan_items=[_plan_item("a1")],
            png_names=["a1.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.single_image", out.count("![") == 1, str(out.count("![")))
        check("on.image_ref_shape", "(assets/a1.png)" in out)
        check("on.visual_reference_section", "## Visual Reference" in out)
        _leak_scan("on.output", out)

    # Multiple candidates → still only one image.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[
                _figure_asset("a1", image_ref="assets/a1.png"),
                _figure_asset("a2", image_ref="assets/a2.png"),
            ],
            plan_items=[_plan_item("a1"), _plan_item("a2")],
            png_names=["a1.png", "a2.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.only_one_of_many", out.count("![") == 1, str(out.count("![")))

    # Plan→manifest fallback: no plan file, first safe manifest figure used.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png")],
            plan_items=None,
            png_names=["a1.png"],
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.manifest_fallback", info.get("status") == vmi.STATUS_INSERTED and "assets/a1.png" in out, str(info))

    # Asset file missing on disk → degrade to original.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png")],
            plan_items=[_plan_item("a1")],
            png_names=[],  # no PNG written
        )
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.missing_file_degrades", out == BASE_MD and info.get("status") == "skipped", str(info))

    # Reject Chandra-local candidate.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        chandra = _figure_asset("c1", image_ref="assets/c1.png")
        chandra["source_provider"] = "chandra_local"
        job = _make_job(tmp, assets=[chandra], plan_items=None, png_names=["c1.png"])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_chandra", out == BASE_MD, str(info))

    # Reject chandra_blocked marker even on a fitz asset.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        blocked = _figure_asset("c2", image_ref="assets/c2.png")
        blocked["reasons"] = ["chandra_blocked"]
        job = _make_job(tmp, assets=[blocked], plan_items=None, png_names=["c2.png"])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_chandra_blocked", out == BASE_MD, str(info))

    # Reject page_visual_signal (not an extracted_figure).
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        sig = _figure_asset("p1", image_ref="assets/p1.png")
        sig["asset_type"] = "page_visual_signal"
        sig.pop("image_ref", None)
        job = _make_job(tmp, assets=[sig], plan_items=None, png_names=["p1.png"])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_page_signal", out == BASE_MD, str(info))

    # Reject unsafe image_ref on an otherwise-eligible figure.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        bad = _figure_asset("b1", image_ref="../../../etc/passwd.png")
        job = _make_job(tmp, assets=[bad], plan_items=None, png_names=[])
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.reject_bad_ref", out == BASE_MD, str(info))

    # Malformed manifest → degrade safely.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = FakeJob(dir=tmp)
        job.assets_dir.mkdir(parents=True, exist_ok=True)
        job.visual_assets_manifest_json.write_text("{not json", encoding="utf-8")
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.malformed_manifest_degrades", out == BASE_MD, str(info))

    # No artifacts at all (e.g. paste job) → degrade safely.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = FakeJob(dir=tmp)
        out, info = vmi.apply_visual_markdown_pilot(job, BASE_MD)
        check("on.no_artifacts_degrades", out == BASE_MD and info.get("reason") == vmi.SKIP_CANDIDATE_UNAVAILABLE, str(info))

    # Source-page anchor placement (deterministic marker present).
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(
            tmp,
            assets=[_figure_asset("a1", image_ref="assets/a1.png", page=3)],
            plan_items=[_plan_item("a1")],
            png_names=["a1.png"],
        )
        md_with_anchor = "# Guide\n\n<!-- visual-anchor: source_page_0003 -->\n\nMore.\n"
        out, info = vmi.apply_visual_markdown_pilot(job, md_with_anchor)
        check("on.anchor_placement", info.get("placement") == vmi.PLACEMENT_SOURCE_PAGE_ANCHOR, str(info))
        check("on.anchor_no_extra_section", "## Visual Reference" not in out)
        # image must appear after the anchor marker
        check("on.anchor_after_marker", out.index("<!-- visual-anchor") < out.index("!["))

    # No mutation of source manifest / plan dicts.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        assets = [_figure_asset("a1", image_ref="assets/a1.png")]
        items = [_plan_item("a1")]
        man_before = json.dumps(_manifest(assets), sort_keys=True)
        plan_before = json.dumps(_plan(items), sort_keys=True)
        job = _make_job(tmp, assets=assets, plan_items=items, png_names=["a1.png"])
        manifest_obj = json.loads(job.visual_assets_manifest_json.read_text())
        plan_obj = json.loads(job.visual_replacement_plan_json.read_text())
        before_m = json.dumps(manifest_obj, sort_keys=True)
        before_p = json.dumps(plan_obj, sort_keys=True)
        vmi.select_visual_markdown_candidate(job, manifest=manifest_obj, replacement_plan=plan_obj)
        check("on.no_mutation_manifest", json.dumps(manifest_obj, sort_keys=True) == before_m)
        check("on.no_mutation_plan", json.dumps(plan_obj, sort_keys=True) == before_p)
        # artifacts on disk unchanged too
        check("on.disk_manifest_unchanged",
              json.dumps(json.loads(job.visual_assets_manifest_json.read_text()), sort_keys=True) == man_before)
        check("on.disk_plan_unchanged",
              json.dumps(json.loads(job.visual_replacement_plan_json.read_text()), sort_keys=True) == plan_before)

    _summary()


def _summary() -> None:
    print(f"\n{PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    run()
