#!/usr/bin/env python3
"""Slice 62 — focused tests for the capped multi-figure visual pilot.

Slice 62 cautiously extends the off-by-default visual markdown image pilot from
"at most one figure" to "up to a small server-configured cap" (hard upper bound 2),
while keeping default behavior byte-identical to the single-figure pilot. This suite
exercises:

  * the env cap reader (default/invalid/0/negative/huge -> 1; valid 2 -> 2),
  * capped multi-candidate SELECTION (Slice 60 quality gate reused; secondary floor;
    duplicate id/ref de-dup; page diversity; only-decorative -> none),
  * capped multi INSERTION (anchored placement + a single trailing
    ``## Visual References`` section; generic page-only captions),
  * the unchanged two-key gate + default-off byte-identical output,
  * render compatibility for >1 image (PDF embeds all; DOCX degrades-never-fails),
  * the export ride-along of ALL and ONLY referenced pilot PNGs up to the cap,
  * a full no-leak sweep over markdown, info dicts, bundle index, and logs.

Data discipline (no-leak): every PNG is a tiny runtime-built byte literal under a temp
dir — never committed, never base64/data-URI in an assertion. No private text, OCR text,
caption text, host path, token, provider payload, raw argv, or full URL is read or
emitted. The gate reads only sanitized manifest metadata (source page, bbox, page/crop
dimensions). A final sweep scans every returned diagnostic / serialized string.

Parts B (render) and C (export) SKIP automatically when their host deps (Chromium /
python-docx / PyMuPDF / FastAPI) are unavailable; run inside the container for full
coverage.

Run:

    python test_scripts/test_visual_pilot_multifigure.py
    GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2 python test_scripts/test_visual_pilot_multifigure.py
"""
from __future__ import annotations

import io
import json
import os
import re
import struct
import sys
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import visual_markdown_insertion as vmi  # noqa: E402

PASS = 0
FAIL = 0
SKIP = 0

# Forbidden value shapes — none may appear in any returned diagnostic / serialized output.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
DATAURI = re.compile(r"data:[^;]+;base64,", re.IGNORECASE)
GGUFLIKE = re.compile(r"\.gguf\b|mmproj|llama-server", re.IGNORECASE)
ARGVLIKE = re.compile(r"--\w+\s+\S")
_LEAK_PATTERNS = (
    ("key", KEYLIKE), ("path", PATHLIKE), ("url", URLLIKE), ("auth", AUTHLIKE),
    ("socket", SOCKETLIKE), ("datauri", DATAURI), ("gguf", GGUFLIKE), ("argv", ARGVLIKE),
)
_OUTPUTS: list[str] = []

# A recognisable ASCII marker baked into the synthetic PNG body. It must ride along in a
# zipped image entry (export works) but must NEVER appear in a bundle index / markdown.
PNG_BODY_SENTINEL = "png_image_body_sentinel"

# Page geometry used across the geometry cases (A4-ish, in PDF points).
PW, PH = 612.0, 792.0

BASE_MD = "# Guide\n\nSome content.\n"


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


def skip(name: str, detail: str = "") -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name}" + (f" — {detail}" if detail else ""))


def record(text) -> str:
    if isinstance(text, str):
        _OUTPUTS.append(text)
    return text


def _sweep_one(text) -> str | None:
    if not isinstance(text, str):
        return None
    for label, pat in _LEAK_PATTERNS:
        if pat.search(text):
            return label
    return None


def _build_png(width: int = 96, height: int = 96, *, sentinel: bool = False) -> bytes:
    """A figure-sized grayscale PNG built at runtime (stdlib only; never committed).

    Large enough that the strengthened PDF visibility check counts it as a real image.
    With ``sentinel`` the recognisable body marker is appended after IEND so the export
    ride-along has something to detect without embedding any path/secret.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    idat = zlib.compress(raw, 9)
    body = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    return body + (PNG_BODY_SENTINEL.encode("ascii") if sentinel else b"")


@dataclass(frozen=True)
class FakeJob:
    dir: Path
    opt_in: bool = True

    @property
    def visual_assets_manifest_json(self) -> Path:
        return self.dir / "visual_assets_manifest.json"

    @property
    def visual_replacement_plan_json(self) -> Path:
        return self.dir / "visual_replacement_plan.json"

    @property
    def assets_dir(self) -> Path:
        return self.dir / "assets"

    @property
    def clean_md(self) -> Path:
        return self.dir / "clean.md"

    @property
    def visual_markdown_image_pilot(self) -> bool:
        return self.opt_in


def _figure(asset_id: str, *, page: int, bbox=None, pw=None, ph=None,
            cw=None, ch=None, image_ref=None, provider="fitz_local",
            atype="extracted_figure") -> dict:
    return {
        "asset_id": asset_id,
        "source_page": page,
        "asset_type": atype,
        "bbox": bbox,
        "caption": None,
        "source_provider": provider,
        "image_ref": image_ref if image_ref is not None else f"assets/{asset_id}.png",
        "scores": {},
        "signals": {"page_width": pw, "page_height": ph,
                    "crop_width_px": cw, "crop_height_px": ch},
        "warnings": [],
    }


def content_figure(asset_id="content_fig", page=5, image_ref=None) -> dict:
    """A content-sized figure -> score 1.2, non-decorative (clears the secondary floor)."""
    return _figure(asset_id, page=page, bbox=[100, 200, 500, 600], pw=PW, ph=PH,
                   cw=800, ch=800, image_ref=image_ref)


def low_quality_figure(asset_id="low_fig", page=7) -> dict:
    """A small-area figure -> score ~0.7, non-decorative but BELOW the secondary floor."""
    return _figure(asset_id, page=page, bbox=[100, 200, 140, 240], pw=PW, ph=PH,
                   cw=200, ch=200)


def title_full(asset_id="title_full") -> dict:
    return _figure(asset_id, page=1, bbox=[0, 0, 612, 792], pw=PW, ph=PH, cw=1200, ch=1500)


def header_banner(asset_id="header_banner") -> dict:
    return _figure(asset_id, page=3, bbox=[20, 10, 590, 60], pw=PW, ph=PH, cw=1100, ch=90)


def tiny_logo(asset_id="tiny_logo") -> dict:
    return _figure(asset_id, page=2, bbox=[280, 380, 325, 425], pw=PW, ph=PH, cw=40, ch=40)


def _manifest(assets: list[dict]) -> dict:
    return {
        "version": 1, "kind": "visual_assets_manifest", "status": "completed",
        "source": "extraction_metadata.json", "assets": assets,
        "summary": {"asset_count": len(assets)}, "warnings": [],
    }


def _plan(asset_ids: list[str]) -> dict:
    return {
        "version": 1, "kind": "visual_replacement_plan", "status": "completed",
        "source": "visual_asset_scoring.json",
        "items": [{
            "asset_id": aid, "source_page": 3, "source_provider": "fitz_local",
            "asset_type": "extracted_figure", "priority": "high",
            "candidate_action": "candidate_include_as_figure",
            "placement": "source_page_reference",
            "reasons": ["score_high"], "warnings": [],
        } for aid in asset_ids],
        "summary": {}, "warnings": [],
    }


def _make_job(tmp: Path, assets: list[dict], *, plan_ids=None, opt_in=True,
              png_for=None, sentinel=False) -> FakeJob:
    """Build a FakeJob; write a real PNG for each asset's safe ref so the file gate passes."""
    job = FakeJob(dir=tmp, opt_in=opt_in)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        aid = asset.get("asset_id")
        if png_for is not None and aid not in png_for:
            continue
        ref = asset.get("image_ref")
        if isinstance(ref, str) and re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", ref):
            (job.dir / ref).write_bytes(_build_png(sentinel=sentinel))
    job.visual_assets_manifest_json.write_text(
        json.dumps(_manifest(assets)) + "\n", encoding="utf-8")
    if plan_ids is not None:
        job.visual_replacement_plan_json.write_text(
            json.dumps(_plan(plan_ids)) + "\n", encoding="utf-8")
    return job


def _with_env(pairs: dict, fn):
    """Run ``fn`` with the given env vars set (None value = unset), restoring after."""
    saved = {k: os.environ.get(k) for k in pairs}
    for k, v in pairs.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _ids(cands) -> list:
    return [c.get("asset_id") for c in cands]


# ---------------------------------------------------------------------------
# Case 1 — env cap reader
# ---------------------------------------------------------------------------
def test_env_cap() -> None:
    def cap(val):
        return _with_env({vmi.MAX_IMAGES_ENV: val}, vmi.visual_markdown_pilot_max_images)

    check("cap.absent_is_1", cap(None) == 1)
    check("cap.empty_is_1", cap("") == 1)
    check("cap.whitespace_is_1", cap("   ") == 1)
    check("cap.invalid_is_1", cap("abc") == 1)
    check("cap.float_is_1", cap("1.5") == 1)
    check("cap.zero_is_1", cap("0") == 1)
    check("cap.negative_is_1", cap("-1") == 1)
    check("cap.one_is_1", cap("1") == 1)
    check("cap.two_is_2", cap("2") == 2)
    check("cap.three_degrades_to_1", cap("3") == 1)
    check("cap.huge_degrades_to_1", cap("999999999") == 1)
    check("cap.padded_two_is_2", cap("  2  ") == 2)
    check("cap.return_type_int", isinstance(cap(None), int) and isinstance(cap("2"), int))


# ---------------------------------------------------------------------------
# Cases 2-8 — capped multi-candidate SELECTION (pure; quality gate reused)
# ---------------------------------------------------------------------------
def test_selection() -> None:
    sel = vmi.select_visual_markdown_candidates

    # (2) default cap stays exactly one figure max, even with two great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)])
        cands = sel(job)  # default max_images = 1
        check("default.one_max", len(cands) == 1 and _ids(cands) == ["c1"], str(_ids(cands)))

    # (3) cap 2 + two high-quality on different pages -> two candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)])
        cands = sel(job, max_images=2)
        check("cap2.two_high_quality", len(cands) == 2 and set(_ids(cands)) == {"c1", "c2"},
              str(_ids(cands)))
        check("cap2.strongest_first", cands[0]["asset_id"] == "c1", str(_ids(cands)))

    # (4) cap 2 + only one high-quality candidate -> one.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("only", page=5)])
        cands = sel(job, max_images=2)
        check("cap2.one_candidate", len(cands) == 1 and _ids(cands) == ["only"], str(_ids(cands)))

    # (5) cap 2 + a low-quality (non-decorative, below floor) second -> only one.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("good", page=5), low_quality_figure("low", page=8)])
        cands = sel(job, max_images=2)
        check("cap2.low_quality_second_dropped",
              len(cands) == 1 and _ids(cands) == ["good"], str(_ids(cands)))

    # (6) all decorative -> none selected.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [title_full("t"), tiny_logo("l"), header_banner("h")])
        cands = sel(job, max_images=2)
        check("cap2.all_decorative_none", cands == [], str(_ids(cands)))

    # (7a) duplicate asset ids are de-duped (manifest collapses to the first).
    with tempfile.TemporaryDirectory() as d:
        dup = content_figure("dup", page=5)
        dup2 = content_figure("dup", page=8)  # same id, different page
        job = _make_job(Path(d), [dup, dup2])
        cands = sel(job, max_images=2)
        check("cap2.dup_ids_collapsed", len(cands) == 1, str(_ids(cands)))

    # (7b) duplicate asset refs (distinct ids) are de-duped at selection.
    with tempfile.TemporaryDirectory() as d:
        a = content_figure("ref_a", page=5, image_ref="assets/shared.png")
        b = content_figure("ref_b", page=8, image_ref="assets/shared.png")
        job = _make_job(Path(d), [a, b], png_for={"ref_a"})  # the shared file exists once
        cands = sel(job, max_images=2)
        check("cap2.dup_refs_deduped", len(cands) == 1, str([c.get("asset_ref") for c in cands]))

    # (8) prefer different pages: two on page 5, one on page 8 -> pick page5 + page8.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("p5a", page=5),
                                  content_figure("p5b", page=5),
                                  content_figure("p8", page=8)])
        cands = sel(job, max_images=2)
        pages = sorted(c["source_page"] for c in cands)
        check("cap2.prefers_distinct_pages", pages == [5, 8], str(_ids(cands)) + " " + str(pages))
        check("cap2.distinct_drops_same_page", "p5b" not in _ids(cands), str(_ids(cands)))

    # (8b) only same-page good candidates -> two from the same page is allowed (no
    # better alternative exists).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("s1", page=5), content_figure("s2", page=5)])
        cands = sel(job, max_images=2)
        check("cap2.same_page_allowed_when_no_alt", len(cands) == 2, str(_ids(cands)))


# ---------------------------------------------------------------------------
# Cases 9-10 — hard safety gates hold under multi-selection
# ---------------------------------------------------------------------------
def test_safety_gates() -> None:
    sel = vmi.select_visual_markdown_candidates

    # (9) unsafe refs never enter selection; a safe content figure still wins.
    unsafe_refs = [
        ("abs", "/etc/passwd.png"),
        ("dotdot", "assets/../secret.png"),
        ("backslash", "assets\\fig.png"),
        ("url", "https://example.com/a.png"),
        ("datauri", "data:image/png;base64,AAAA.png"),
        ("nonpng", "assets/fig.jpg"),
        ("nested", "assets/sub/fig.png"),
    ]
    for label, ref in unsafe_refs:
        with tempfile.TemporaryDirectory() as d:
            bad = content_figure(f"bad_{label}", page=4, image_ref=ref)
            good = content_figure("safe_fig", page=5)
            job = _make_job(Path(d), [bad, good])
            cands = sel(job, max_images=2)
            check(f"safe.unsafe_{label}_excluded",
                  _ids(cands) == ["safe_fig"], f"{ref} -> {_ids(cands)}")

    # (10) chandra / mistral / page_visual_signal are never selected even with cap 2.
    with tempfile.TemporaryDirectory() as d:
        chandra = content_figure("chandra_fig", page=4)
        chandra["source_provider"] = "chandra_local"
        mistral = content_figure("mistral_fig", page=4)
        mistral["source_provider"] = "mistral_ocr"
        signal = content_figure("signal_fig", page=4)
        signal["asset_type"] = "page_visual_signal"
        blocked = content_figure("blocked_fig", page=4)
        blocked["reasons"] = ["chandra_blocked"]
        good1 = content_figure("fitz1", page=5)
        good2 = content_figure("fitz2", page=6)
        job = _make_job(Path(d), [chandra, mistral, signal, blocked, good1, good2])
        cands = sel(job, max_images=2)
        check("blocked.only_fitz_selected", set(_ids(cands)) == {"fitz1", "fitz2"}, str(_ids(cands)))


# ---------------------------------------------------------------------------
# Cases 2,11,12,13,14 — INSERTION through the real entry point (env-gated)
# ---------------------------------------------------------------------------
def test_insertion() -> None:
    ON = {vmi.ENABLE_ENV: "1"}
    CAP2 = {vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"}

    # (3-render) cap 2 + two distinct-page content figures -> exactly two images, under
    # a single plural "## Visual References" section, generic page-only captions.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)])
        out, info = _with_env(CAP2, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out); record(json.dumps(info, default=str))
        check("ins.cap2_two_images", out.count("![") == 2, str(out.count("![")))
        check("ins.cap2_count_field", info.get("inserted_visual_count") == 2, str(info))
        check("ins.cap2_plural_section", "## Visual References" in out, out)
        check("ins.cap2_single_section", out.count("## Visual Reference") == 1, out)
        # (11) captions are generic page-only captions, no raw text.
        check("ins.caption_page5", "![Extracted figure from source page 5]" in out, out)
        check("ins.caption_page8", "![Extracted figure from source page 8]" in out, out)
        _leak = _sweep_one(out)
        check("ins.no_leak_markdown", _leak is None, _leak or "")

    # (2) default cap (no MAX env) -> exactly one image even with two great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)])
        out, info = _with_env(ON, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("ins.default_one_image", out.count("![") == 1, str(out.count("![")))
        check("ins.default_count_1", info.get("inserted_visual_count") == 1, str(info))
        check("ins.default_singular_heading",
              "## Visual Reference" in out and "## Visual References" not in out, out)

    # cap 2 but only one high-quality -> one image (singular section, byte-shape as legacy).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("only", page=5), low_quality_figure("low", page=8)])
        out, info = _with_env(CAP2, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("ins.cap2_one_high_quality", out.count("![") == 1, str(out.count("![")))
        check("ins.cap2_one_count", info.get("inserted_visual_count") == 1, str(info))

    # cap 2 with two anchored pages -> each image placed at its own anchor, no section.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)])
        anchored = ("# Guide\n\n<!-- visual-anchor: source_page_0005 -->\n\nMid.\n\n"
                    "<!-- visual-anchor: source_page_0008 -->\n\nEnd.\n")
        out, info = _with_env(CAP2, lambda: vmi.apply_visual_markdown_pilot(job, anchored))
        record(out)
        check("ins.anchored_two_images", out.count("![") == 2, str(out.count("![")))
        check("ins.anchored_no_section", "## Visual Reference" not in out, out)
        check("ins.anchored_order",
              out.index("source_page_0005") < out.index("(assets/c1.png)")
              < out.index("source_page_0008") < out.index("(assets/c2.png)"), out)

    # (6) all decorative -> byte-identical + closed low-quality reason.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [title_full("t"), tiny_logo("l")])
        out, info = _with_env(CAP2, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("ins.all_decorative_byte_identical", out == BASE_MD, repr(out[:60]))
        check("ins.all_decorative_reason",
              info.get("reason") == vmi.SKIP_CANDIDATE_LOW_QUALITY, str(info))

    # (12) default-OFF (env unset) -> byte-identical, even at cap 2 with great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)])
        out, info = _with_env({vmi.ENABLE_ENV: None, vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("ins.default_off_byte_identical", out == BASE_MD, repr(out[:60]))
        check("ins.default_off_reason", info.get("reason") == vmi.SKIP_DISABLED, str(info))

    # (13) two-key gate unchanged: only (env on, opt-in on) inserts, even at cap 2.
    for name, env, opt_in, may in (
        ("off_off", None, False, False),
        ("off_on", None, True, False),
        ("on_off", "1", False, False),
        ("on_on", "1", True, True),
    ):
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)],
                            opt_in=opt_in)
            out, info = _with_env({vmi.ENABLE_ENV: env, vmi.MAX_IMAGES_ENV: "2"},
                                  lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
            if may:
                check(f"gate.{name}.inserted",
                      info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
            else:
                check(f"gate.{name}.byte_identical", out == BASE_MD and "![" not in out, str(info))

    # (14) the pilot returns NEW text; it never writes clean.md itself (the only writer
    # remains JobManager.save_clean_md, exercised by the e2e/operator harnesses).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5), content_figure("c2", page=8)])
        out, _info = _with_env(CAP2, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("ins.no_clean_md_written", not job.clean_md.exists())
        check("ins.returned_two_images", out.count("![") == 2, str(out.count("![")))


# ---------------------------------------------------------------------------
# Case 19 — no mutation of manifest / plan / source PNGs
# ---------------------------------------------------------------------------
def test_no_mutation() -> None:
    CAP2 = {vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"}
    with tempfile.TemporaryDirectory() as d:
        assets = [content_figure("c1", page=5), content_figure("c2", page=8)]
        job = _make_job(Path(d), assets, plan_ids=["c1", "c2"])
        man_before = job.visual_assets_manifest_json.read_text(encoding="utf-8")
        plan_before = job.visual_replacement_plan_json.read_text(encoding="utf-8")
        png_before = (job.dir / "assets" / "c1.png").read_bytes()
        in_mem = json.loads(man_before)["assets"]
        snap = json.dumps(in_mem, sort_keys=True)

        vmi.select_visual_markdown_candidates(job, max_images=2,
                                              manifest=json.loads(man_before),
                                              replacement_plan=json.loads(plan_before))
        _with_env(CAP2, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))

        check("nomut.in_memory_assets_unchanged", json.dumps(in_mem, sort_keys=True) == snap)
        check("nomut.manifest_on_disk_unchanged",
              job.visual_assets_manifest_json.read_text(encoding="utf-8") == man_before)
        check("nomut.plan_on_disk_unchanged",
              job.visual_replacement_plan_json.read_text(encoding="utf-8") == plan_before)
        check("nomut.source_png_unchanged",
              (job.dir / "assets" / "c1.png").read_bytes() == png_before)


# ---------------------------------------------------------------------------
# Part B — render compatibility for >1 image (cases 15-16; host-skippable)
# ---------------------------------------------------------------------------
TWO_IMAGE_MD = (
    "# Guide\n\nText.\n\n## Visual References\n\n"
    "![Extracted figure from source page 5](assets/m1.png)\n\n"
    "![Extracted figure from source page 8](assets/m2.png)\n"
)


def _make_render_dir(tmp: Path) -> Path:
    (tmp / "assets").mkdir(parents=True, exist_ok=True)
    (tmp / "assets" / "m1.png").write_bytes(_build_png())
    (tmp / "assets" / "m2.png").write_bytes(_build_png())
    (tmp / "clean.md").write_text(TWO_IMAGE_MD, encoding="utf-8")
    return tmp


def test_render_pdf() -> None:
    try:
        from pipeline.pdf_renderer import render_pdf, _find_chromium
    except Exception as exc:
        skip("render.pdf", f"renderer import unavailable ({type(exc).__name__})")
        return
    if _find_chromium() is None:
        skip("render.pdf", "no Chromium on host")
        return
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        skip("render.pdf_fitz", f"PyMuPDF unavailable ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as d:
        work = _make_render_dir(Path(d))
        out_pdf = work / "final.pdf"
        try:
            render_pdf(work / "clean.md", out_pdf)
        except Exception as exc:
            check("render.pdf_no_raise", False, type(exc).__name__)
            return
        check("render.pdf_nonempty", out_pdf.is_file() and out_pdf.stat().st_size > 0)
        count = 0
        try:
            with fitz.open(str(out_pdf)) as doc:
                for page in doc:
                    for image in page.get_images(full=True):
                        if int(image[2]) >= 32 and int(image[3]) >= 32:
                            count += 1
        except Exception as exc:
            skip("render.pdf_image_count", f"inspect unavailable ({type(exc).__name__})")
            return
        check("render.pdf_embeds_both_images", count >= 2, f"embedded={count}")


def test_render_docx() -> None:
    try:
        import docx  # noqa: F401
        from pipeline.docx_renderer import render_docx
    except Exception as exc:
        skip("render.docx", f"python-docx unavailable ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as d:
        work = _make_render_dir(Path(d))
        out = work / "final.docx"
        try:
            render_docx(work / "clean.md", out, title="Guide")
        except Exception as exc:
            check("render.docx_no_raise", False, type(exc).__name__)
            return
        check("render.docx_nonempty", out.is_file() and out.stat().st_size > 0)
        # Two embedded PNGs make the zip non-trivially larger than an image-less doc.
        check("render.docx_embedded_two", out.stat().st_size > 8000, str(out.stat().st_size))


# ---------------------------------------------------------------------------
# Part C — export ride-along of ALL and ONLY referenced PNGs up to the cap
# (cases 17-18; FastAPI-skippable)
# ---------------------------------------------------------------------------
def test_export() -> None:
    try:
        from fastapi import HTTPException
        from api import server  # noqa: WPS433
    except Exception as exc:
        skip("export.bundle", f"FastAPI unavailable ({type(exc).__name__})")
        return

    from pipeline.job_manager import Job

    REF1, REF2, EXTRA = "m1.png", "m2.png", "unref_extra.png"
    CLEAN_TWO = (
        "# Guide\n\nText.\n\n## Visual References\n\n"
        f"![Extracted figure from source page 5](assets/{REF1})\n\n"
        f"![Extracted figure from source page 8](assets/{REF2})\n"
    )

    def _make_job(root: Path, job_id: str, *, with_pdf: bool, clean_md: str,
                  assets: dict) -> Job:
        job = Job(id=job_id, root=root)
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        job._write_manifest({"id": job.id, "status": "completed", "title": job.id,
                             "visual_markdown_image_pilot": True})
        if with_pdf:
            job.final_pdf.write_bytes(b"%PDF-1.4 synthetic pdf bytes")
        job.assets_dir.mkdir(parents=True, exist_ok=True)
        for name, data in assets.items():
            (job.assets_dir / name).write_bytes(data)
        job.save_text(job.clean_md, clean_md)
        return job

    def _bundle(jobs_by_id, job_ids, artifacts):
        original = server._get_job

        def fake(raw_id):
            jid = str(raw_id)
            if jid in jobs_by_id:
                return jobs_by_id[jid]
            raise HTTPException(status_code=404, detail="Job not found.")

        server._get_job = fake
        try:
            return server.export_bundle(server.BundleRequest(job_ids=job_ids, artifacts=artifacts))
        finally:
            server._get_job = original

    png = _build_png(sentinel=True)

    # (17) both referenced PNGs ride along; the unreferenced extra does NOT.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        job = _make_job(root, "job-two", with_pdf=True, clean_md=CLEAN_TWO,
                        assets={REF1: png, REF2: png, EXTRA: png})
        resp = _bundle({"job-two": job}, ["job-two"], ["pdf", "markdown"])
        with zipfile.ZipFile(io.BytesIO(resp.body)) as zf:
            names = zf.namelist()
            manifest_text = record(zf.read("manifest.json").decode("utf-8"))
        png_entries = [n for n in names if n.lower().endswith(".png")]
        check("export.two_pngs_ride_along", len(png_entries) == 2, str(png_entries))
        check("export.both_referenced_present",
              any(n.endswith(f"/assets/{REF1}") for n in names)
              and any(n.endswith(f"/assets/{REF2}") for n in names), str(names))
        check("export.unreferenced_excluded",
              not any(n.endswith(f"/assets/{EXTRA}") for n in names), str(names))
        check("export.relative_under_assets",
              all("/assets/" in p and not p.startswith("/") and ".." not in p
                  and "\\" not in p for p in png_entries), str(png_entries))
        manifest = json.loads(manifest_text)
        entry = manifest["jobs"][0]
        check("export.manifest_lists_both",
              entry.get("visual_pilot_assets") == [f"assets/{REF1}", f"assets/{REF2}"],
              str(entry.get("visual_pilot_assets")))
        check("export.manifest_backward_compat_first",
              entry.get("visual_pilot_asset") == f"assets/{REF1}",
              str(entry.get("visual_pilot_asset")))
        check("export.manifest_no_image_bytes", PNG_BODY_SENTINEL not in manifest_text)
        leak = _sweep_one(manifest_text)
        check("export.manifest_no_leak", leak is None, leak or "")
        # (18) the ride-along PNGs do NOT inflate the requested-artifact count.
        check("export.files_included_requested_only",
              manifest.get("files_included") == 2, str(manifest.get("files_included")))

    # (18b) a pilot-PNG-only job with the requested artifact absent still 404s.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        job = _make_job(root, "job-gate", with_pdf=False, clean_md=CLEAN_TWO,
                        assets={REF1: png, REF2: png})
        raised = False
        try:
            _bundle({"job-gate": job}, ["job-gate"], ["pdf"])
        except HTTPException as exc:
            raised = exc.status_code == 404
        check("export.png_alone_does_not_satisfy_gate", raised)

    # export leaves the source PNGs byte-identical.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        job = _make_job(root, "job-immut", with_pdf=True, clean_md=CLEAN_TWO,
                        assets={REF1: png, REF2: png})
        before = (job.assets_dir / REF1).read_bytes()
        _bundle({"job-immut": job}, ["job-immut"], ["pdf"])
        check("export.source_png_byte_identical",
              (job.assets_dir / REF1).read_bytes() == before)


# ---------------------------------------------------------------------------
# Case 20 — no-leak sweep over everything recorded
# ---------------------------------------------------------------------------
def test_no_leak_sweep() -> None:
    leaks = []
    for blob in _OUTPUTS:
        found = _sweep_one(blob)
        if found is not None:
            leaks.append(found)
    check("sweep.no_leaks", not leaks, ",".join(sorted(set(leaks))))
    check("sweep.had_outputs", len(_OUTPUTS) > 0, str(len(_OUTPUTS)))


def main() -> int:
    test_env_cap()
    test_selection()
    test_safety_gates()
    test_insertion()
    test_no_mutation()
    test_render_pdf()
    test_render_docx()
    test_export()
    test_no_leak_sweep()
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
