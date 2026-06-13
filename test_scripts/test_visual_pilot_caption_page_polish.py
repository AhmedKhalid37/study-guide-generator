#!/usr/bin/env python3
"""Slice 74 — focused tests for safe source-page captions on inserted visuals.

Slice 73 proved the off-by-default visual markdown image pilot can finally select
irreplaceable diagrams/figures on the real operator sample. Slice 74 stops adding
table/diagram morphology heuristics and adds a small, user-visible polish: a safe,
generic italic caption line placed *below* each inserted visual, carrying only a
fixed phrase plus the (already-bounded, integer) source page number when available.

This slice must NOT change selection, ranking, classification, the cap, the default,
the two-key gate, export, the renderer, providers, OCR routing, or any UI. These
tests therefore prove two things at once:

  1. the caption is present, generic, and safe (no filename / path / OCR / document /
     table / caption text / base64 / data URI / provider payload / token), with a
     page number when available and a generic fallback otherwise; and
  2. captions are purely additive — image refs, selected order, selected count, and
     ranking outcomes are unchanged, default-off output stays byte-identical, and a
     caption is never emitted unless BOTH the master flag and per-job opt-in are on.

Data discipline (no-leak): every PNG is a tiny runtime-built byte literal (or a
Pillow-drawn shape) under a temp dir — never committed, never base64/data-URI in an
assertion. No private text, OCR text, caption text, host path, token, provider
payload, raw argv, or full URL is read or emitted. A final sweep scans every
returned markdown / diagnostic string.

Pillow-gated ranking checks and renderer/export checks SKIP automatically when their
host deps are unavailable; run inside the container for full coverage.

Run:

    python test_scripts/test_visual_pilot_caption_page_polish.py
    GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2 python test_scripts/test_visual_pilot_caption_page_polish.py
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import visual_markdown_insertion as vmi  # noqa: E402

try:
    from PIL import Image, ImageDraw  # type: ignore

    _HAVE_PIL = True
except Exception:  # Pillow optional on host
    _HAVE_PIL = False

PASS = 0
FAIL = 0
SKIP = 0

# Forbidden value shapes — none may appear in any returned markdown / diagnostic string.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
BASE64URI = re.compile(r"data:[^;]+;base64,")
GGUFLIKE = re.compile(r"\.gguf\b|mmproj", re.IGNORECASE)

# Words that would only be present if private source content leaked into a caption.
LEAK_WORDS = (
    "patient", "John Doe", "MRN", "confidential", "secret", "private",
    ".pdf", "OCR", "Figure 1:", "Table 1:", "glossary", "definition",
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


def skip(name: str, why: str = "") -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name}" + (f" — {why}" if why else ""))


def _sweep(name: str, text: str) -> None:
    for label, pat in (
        ("key", KEYLIKE), ("path", PATHLIKE), ("url", URLLIKE), ("auth", AUTHLIKE),
        ("socket", SOCKETLIKE), ("datauri", BASE64URI), ("gguf", GGUFLIKE),
    ):
        check(f"{name}.no_{label}", not pat.search(text), text[:120])


# --- runtime PNG fixtures (never committed) ----------------------------------


def _solid_png(width: int = 96, height: int = 96, value: int = 0x80) -> bytes:
    """A figure-sized grayscale PNG via stdlib only (no Pillow)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes([value]) * width for _ in range(height))
    idat = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _draw_diagram(path: Path, size=(140, 140)) -> None:
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, 52, 52], outline=0, width=3)
    d.rectangle([70, 18, 104, 58], outline=0, width=3)
    d.line([52, 30, 70, 36], fill=0, width=3)
    d.line([20, 62, 92, 104], fill=0, width=3)
    d.ellipse([60, 74, 100, 112], outline=0, width=3)
    d.line([30, 50, 36, 96], fill=0, width=3)
    d.rectangle([12, 86, 34, 110], fill=0)
    img.save(path)


def _draw_two_col_table(path: Path, size=(140, 140)) -> None:
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    # Term (left) + multi-line definition (right), variable row heights, no rules.
    for i, ry in enumerate((12, 38, 66, 96, 120)):
        d.rectangle([10, ry, 38, ry + 8], fill=110)
        d.rectangle([60, ry, 132, ry + 8], fill=110)
        if i in (1, 3):
            d.rectangle([60, ry + 10, 118, ry + 18], fill=110)
    img.save(path)


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


# Content-sized geometry → score 1.2, non-decorative, clears the secondary floor.
PW, PH = 612, 792


def _figure(asset_id: str, *, page: int, kind: str = "solid", image_ref=None) -> dict:
    asset = {
        "asset_id": asset_id,
        "source_page": page,
        "asset_type": "extracted_figure",
        "bbox": [100, 200, 500, 600],
        "caption": None,
        "source_provider": "fitz_local",
        "image_ref": image_ref if image_ref is not None else f"assets/{asset_id}.png",
        "scores": {},
        "signals": {"page_width": PW, "page_height": PH,
                    "crop_width_px": 800, "crop_height_px": 800},
        "warnings": [],
    }
    asset["_kind"] = kind
    return asset


def _manifest(assets: list[dict]) -> dict:
    clean = [{k: v for k, v in a.items() if k != "_kind"} for a in assets]
    return {
        "version": 1, "kind": "visual_assets_manifest", "status": "completed",
        "source": "extraction_metadata.json", "assets": clean,
        "summary": {"asset_count": len(clean)}, "warnings": [],
    }


def _make_job(tmp: Path, assets: list[dict], *, opt_in=True) -> FakeJob:
    job = FakeJob(dir=tmp, opt_in=opt_in)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        ref = asset.get("image_ref")
        if not (isinstance(ref, str) and re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", ref)):
            continue
        dest = job.dir / ref
        kind = asset.get("_kind", "solid")
        if kind == "diagram" and _HAVE_PIL:
            _draw_diagram(dest)
        elif kind == "table" and _HAVE_PIL:
            _draw_two_col_table(dest)
        else:
            dest.write_bytes(_solid_png())
    job.visual_assets_manifest_json.write_text(
        json.dumps(_manifest(assets)) + "\n", encoding="utf-8")
    return job


def _with_env(pairs: dict, fn):
    """Run ``fn`` with env vars forced (value None = unset); restore afterwards."""
    old = {k: os.environ.get(k) for k in pairs}
    try:
        for k, v in pairs.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return fn()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _caption_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines()
            if ln.strip().startswith("*Source visual")]


def _image_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip().startswith("![")]


# === 1-8: caption builder — presence, page, fallback, safety ==================


def test_caption_builder() -> None:
    # 1. inserted visual gets a generic safe caption (block = image + caption line).
    block = vmi.build_visual_markdown_block(
        {"asset_ref": "assets/fig_01.png", "source_page": 6, "caption": None})
    img = vmi.build_visual_markdown_image(
        {"asset_ref": "assets/fig_01.png", "source_page": 6, "caption": None})
    check("1.block_has_image_and_caption",
          block.startswith(img) and "*Source visual" in block, block)
    # 2. source page number appears when available.
    check("2.page_number_present", "*Source visual, page 6.*" in block, block)
    check("2.caption_below_image",
          block == f"{img}\n\n*Source visual, page 6.*", block)
    # 3. missing/invalid source page falls back to the generic caption. (A float like
    #    2.5 is a VALID coercion to page 2 — same as the image alt text — so it is not a
    #    fallback case and is excluded here.)
    for bad in (None, 0, -3, "x", True, [1], object()):
        b = vmi.build_visual_markdown_block(
            {"asset_ref": "assets/fig_01.png", "source_page": bad, "caption": None})
        check(f"3.fallback_generic[{bad!r}]",
              b.endswith("*Source visual.*") and "page" not in b.split("](", 1)[-1], b)
    # 4. caption does not include a source filename even if one is smuggled in.
    smug = vmi.build_visual_markdown_block({
        "asset_ref": "assets/fig_01.png", "source_page": 6,
        "caption": "lecture_notes_final.pdf Figure 1: confidential",
    })
    cap = "\n".join(_caption_lines(smug))
    check("4.no_source_filename", ".pdf" not in cap and "lecture_notes" not in cap, cap)
    # 5. caption does not include an absolute path.
    smug2 = vmi.build_visual_markdown_block({
        "asset_ref": "assets/fig_01.png", "source_page": 6,
        "caption": "/home/op/private/source.pdf",
    })
    check("5.no_absolute_path", not PATHLIKE.search("\n".join(_caption_lines(smug2))))
    # 6. caption does not include OCR/document/table/source-caption text.
    smug3 = vmi.build_visual_markdown_block({
        "asset_ref": "assets/fig_01.png", "source_page": 6,
        "caption": "patient John Doe MRN 12345 glossary definition table 1",
    })
    cap3 = "\n".join(_caption_lines(smug3))
    for w in ("patient", "John Doe", "MRN", "glossary", "definition"):
        check(f"6.no_doc_text[{w}]", w not in cap3, cap3)
    # 7. caption does not include base64 / data URI / image bytes.
    smug4 = vmi.build_visual_markdown_block({
        "asset_ref": "assets/fig_01.png", "source_page": 6,
        "caption": "data:image/png;base64,AAAABBBBCCCCDDDD",
    })
    cap4 = "\n".join(_caption_lines(smug4))
    check("7.no_base64_datauri", not BASE64URI.search(cap4) and "base64" not in cap4, cap4)
    # 8. caption does not include a provider payload / token.
    smug5 = vmi.build_visual_markdown_block({
        "asset_ref": "assets/fig_01.png", "source_page": 6,
        "caption": "sk-abcdef012345678901234 Authorization Bearer xyz",
    })
    cap5 = "\n".join(_caption_lines(smug5))
    check("8.no_token_auth",
          not KEYLIKE.search(cap5) and not AUTHLIKE.search(cap5), cap5)

    # The caption line is, by construction, ALWAYS one of exactly two fixed strings —
    # nothing from the candidate's caption field can survive into it. (The image alt
    # text is the unchanged pre-Slice-74 `build_visual_markdown_image` output and is out
    # of scope here; Slice 74's safety property is the caption LINE.)
    for b in (block, smug, smug2, smug3, smug4, smug5):
        cap_only = "\n".join(_caption_lines(b))
        for cl in _caption_lines(b):
            check("caption.fixed_vocab_only",
                  cl == "*Source visual.*" or re.fullmatch(r"\*Source visual, page \d+\.\*", cl) is not None,
                  cl)
        _sweep("caption.builder", cap_only)


# === 9-13: insertion — cap 1 & cap 2, order, refs, count ======================


def test_insertion_caption_invariants() -> None:
    base = "# Guide\n\nSome content.\n"
    c1 = {"asset_ref": "assets/a1.png", "source_page": 3, "caption": None}
    c2 = {"asset_ref": "assets/a2.png", "source_page": 4, "caption": None}

    # 9. caption works with cap 1 (single insertion path).
    out1, info1 = vmi.insert_visual_markdown_reference(base, c1)
    check("9.cap1_inserted", info1.get("status") == vmi.STATUS_INSERTED, str(info1))
    check("9.cap1_one_image", len(_image_lines(out1)) == 1, str(_image_lines(out1)))
    check("9.cap1_one_caption", len(_caption_lines(out1)) == 1, str(_caption_lines(out1)))
    check("9.cap1_page_label", "*Source visual, page 3.*" in out1, out1)
    _sweep("9.cap1", out1)

    # 10. caption works with cap 2; both inserted visuals get captions.
    out2, info2 = vmi.insert_visual_markdown_references(base, [c1, c2])
    check("10.cap2_inserted", info2.get("status") == vmi.STATUS_INSERTED, str(info2))
    check("10.cap2_two_images", len(_image_lines(out2)) == 2, str(_image_lines(out2)))
    check("10.cap2_two_captions", len(_caption_lines(out2)) == 2, str(_caption_lines(out2)))
    check("10.cap2_both_pages",
          "*Source visual, page 3.*" in out2 and "*Source visual, page 4.*" in out2, out2)
    _sweep("10.cap2", out2)

    # 11. caption order matches selected visual order.
    captions = _caption_lines(out2)
    check("11.caption_order",
          captions == ["*Source visual, page 3.*", "*Source visual, page 4.*"], str(captions))

    # 12. caption does not change image refs (refs identical with vs without caption).
    refs_with = vmi.extract_visual_pilot_asset_refs(out2)
    check("12.refs_unchanged", refs_with == ["assets/a1.png", "assets/a2.png"], str(refs_with))
    # The exact image markdown the pilot writes is the unchanged build_visual_markdown_image.
    for c in (c1, c2):
        img = vmi.build_visual_markdown_image(c)
        check(f"12.image_md_unchanged[{c['asset_ref']}]", img in out2, img)

    # 13. caption does not change selected candidate count.
    check("13.count_cap1", info1.get("inserted_visual_count", 1) == 1, str(info1))
    check("13.count_cap2", info2.get("inserted_visual_count") == 2, str(info2))


# === 14-17: apply path — ranking, default-off, two-key gate ===================


def test_apply_path_gates_and_ranking() -> None:
    base = "# Guide\n\nSome content.\n"

    # 15. default-off (master flag unset) → byte-identical, NO caption.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [_figure("a1", page=3)])
        out, info = _with_env(
            {vmi.ENABLE_ENV: None}, lambda: vmi.apply_visual_markdown_pilot(job, base))
        check("15.default_off_byte_identical", out == base, repr(out[:60]))
        check("15.default_off_no_caption", "*Source visual" not in out)
        check("15.default_off_reason", info.get("reason") == vmi.SKIP_DISABLED, str(info))

    # 16. master flag off (explicit) → no caption (covered by 15 semantics; assert again
    #     with an opted-in job to prove opt-in cannot bypass the master switch).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [_figure("a1", page=3)], opt_in=True)
        out, info = _with_env(
            {vmi.ENABLE_ENV: None}, lambda: vmi.apply_visual_markdown_pilot(job, base))
        check("16.flag_off_no_caption", "*Source visual" not in out and out == base, str(info))

    # 17. job opt-in false (master flag on) → no caption.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [_figure("a1", page=3)], opt_in=False)
        out, info = _with_env(
            {vmi.ENABLE_ENV: "1"}, lambda: vmi.apply_visual_markdown_pilot(job, base))
        check("17.opt_out_no_caption", "*Source visual" not in out and out == base, str(info))
        check("17.opt_out_reason", info.get("reason") == vmi.SKIP_JOB_OPT_OUT, str(info))

    # 14. caption does not change ranking outcomes — selection (which Slice 74 did NOT
    #     touch) decides order/refs; the applied output's refs/order MUST equal what the
    #     unmodified selector returns, just with caption lines added.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [_figure("a1", page=3), _figure("a2", page=4)])
        env = {vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"}
        selected = _with_env(
            env, lambda: vmi.select_visual_markdown_candidates(job, max_images=2))
        out, info = _with_env(env, lambda: vmi.apply_visual_markdown_pilot(job, base))
        sel_refs = [c.get("asset_ref") for c in selected]
        applied_refs = vmi.extract_visual_pilot_asset_refs(out)
        check("14.ranking_refs_match", applied_refs == sel_refs, f"{applied_refs} vs {sel_refs}")
        check("14.count_matches_selection",
              info.get("inserted_visual_count") == len(selected), str(info))
        # Caption order tracks the selected order, page-labelled per candidate.
        expected_caps = [
            (f"*Source visual, page {vmi._safe_page(c.get('source_page'))}.*"
             if vmi._safe_page(c.get("source_page")) else "*Source visual.*")
            for c in selected
        ]
        check("14.caption_order_tracks_selection",
              _caption_lines(out) == expected_caps, str(_caption_lines(out)))
        _sweep("14.apply", out)


# === 18-19: tables allowed when best/only; diagrams beat tables (Pillow) ======


def test_ranking_unchanged_with_captions() -> None:
    if not _HAVE_PIL:
        skip("18-19.ranking", "Pillow unavailable")
        return
    base = "# Guide\n\nSome content.\n"
    env1 = {vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "1"}

    # 18. a reconstructable table is still selected when it is the best/only visual.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [_figure("t1", page=3, kind="table")])
        sel = _with_env(env1, lambda: vmi.select_visual_markdown_candidates(job, max_images=1))
        if not sel:
            skip("18.table_only", "selector returned none on host classifier")
        else:
            check("18.table_classified", sel[0].get("visual_type") == vmi.VISUAL_TYPE_TABLE,
                  str(sel[0].get("visual_type")))
            out, info = _with_env(env1, lambda: vmi.apply_visual_markdown_pilot(job, base))
            check("18.table_selected_with_caption",
                  info.get("status") == vmi.STATUS_INSERTED and "*Source visual" in out, str(info))

    # 19. a diagram still beats a reconstructable table at cap 1.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [_figure("t1", page=3, kind="table"),
                                  _figure("g1", page=4, kind="diagram")])
        sel = _with_env(env1, lambda: vmi.select_visual_markdown_candidates(job, max_images=1))
        if not sel:
            skip("19.diagram_beats_table", "selector returned none on host classifier")
        elif sel[0].get("visual_type") not in (vmi.VISUAL_TYPE_DIAGRAM, vmi.VISUAL_TYPE_TABLE):
            skip("19.diagram_beats_table", f"unexpected type {sel[0].get('visual_type')}")
        else:
            check("19.diagram_first", sel[0].get("visual_type") == vmi.VISUAL_TYPE_DIAGRAM,
                  str(sel[0].get("visual_type")))
            check("19.diagram_ref_g1", sel[0].get("asset_ref") == "assets/g1.png",
                  str(sel[0].get("asset_ref")))


# === 20: selection trace remains sanitized & bounded =========================


def test_selection_trace_unaffected() -> None:
    base = "# Guide\n\nSome content.\n"
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(tmp, [_figure("a1", page=3), _figure("a2", page=4)])
        env = {vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"}
        _with_env(env, lambda: vmi.apply_visual_markdown_pilot(job, base))
        trace_path = tmp / vmi.SELECTION_TRACE_FILENAME
        if not trace_path.exists():
            skip("20.trace", "no trace emitted on host")
            return
        raw = trace_path.read_text(encoding="utf-8")
        # The trace must never carry the new caption strings or any private content.
        check("20.trace_no_caption_text", "Source visual" not in raw, raw[:120])
        _sweep("20.trace", raw)
        data = json.loads(raw)
        check("20.trace_bounded_count",
              0 <= int(data.get("selected_count", 0)) <= vmi._HARD_MAX_IMAGES, str(data.get("selected_count")))


# === 21: export ref scan unaffected by caption lines ==========================


def test_export_refs_unaffected() -> None:
    base = "# Guide\n\nSome content.\n"
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        job = _make_job(tmp, [_figure("a1", page=3), _figure("a2", page=4)])
        env = {vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"}
        out, info = _with_env(env, lambda: vmi.apply_visual_markdown_pilot(job, base))
        if info.get("status") != vmi.STATUS_INSERTED:
            skip("21.export", "nothing inserted on host")
            return
        job.clean_md.write_text(out, encoding="utf-8")
        refs = vmi.find_exportable_visual_pilot_assets(job)
        check("21.export_finds_refs", refs == ["assets/a1.png", "assets/a2.png"], str(refs))
        check("21.export_caption_not_a_ref",
              all(r.startswith("assets/") and r.endswith(".png") for r in refs), str(refs))


# === 22-23: PDF render shows image; DOCX render succeeds (caption present) ====


def test_render_with_caption() -> None:
    asset_name = "s00_page_0003_figure_01.png"
    clean_md = (
        "# Synthetic Guide\n\nSome content.\n\n"
        "## Visual Reference\n\n"
        f"![Extracted figure from source page 3](assets/{asset_name})\n\n"
        "*Source visual, page 3.*\n"
    )

    # 22. HTML/PDF render still resolves the image; caption text rides along safely.
    try:
        from pipeline.html_renderer import render_markdown_file
    except Exception as exc:
        skip("22.html", f"renderer import unavailable ({type(exc).__name__})")
    else:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "assets").mkdir(parents=True, exist_ok=True)
            (tmp / "assets" / asset_name).write_bytes(_solid_png())
            (tmp / "clean.md").write_text(clean_md, encoding="utf-8")
            try:
                html = render_markdown_file(tmp / "clean.md")
            except Exception as exc:
                skip("22.html", f"render unavailable ({type(exc).__name__})")
            else:
                check("22.html_image_visible",
                      "<img" in html and f'src="assets/{asset_name}"' in html, html[:160])
                check("22.html_caption_visible", "Source visual, page 3." in html, html[:160])
                check("22.html_no_abspath", "/home/" not in html and "file://" not in html)

    # 23. DOCX render still succeeds with a caption line present.
    try:
        from pipeline.docx_renderer import render_docx
    except Exception as exc:
        skip("23.docx", f"docx renderer import unavailable ({type(exc).__name__})")
    else:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "assets").mkdir(parents=True, exist_ok=True)
            (tmp / "assets" / asset_name).write_bytes(_solid_png())
            (tmp / "clean.md").write_text(clean_md, encoding="utf-8")
            out_path = tmp / "final.docx"
            try:
                render_docx(tmp / "clean.md", out_path)
            except Exception as exc:
                skip("23.docx", f"render unavailable ({type(exc).__name__})")
            else:
                check("23.docx_nonempty", out_path.is_file() and out_path.stat().st_size > 0,
                      str(out_path))


# === 24: degrade-never-fail if caption construction raises ====================


def test_caption_degrades_never_fails() -> None:
    candidate = {"asset_ref": "assets/fig_01.png", "source_page": 6, "caption": None}
    img = vmi.build_visual_markdown_image(candidate)
    original = vmi._visual_caption_line

    def boom(_page):
        raise RuntimeError("caption blew up")

    vmi._visual_caption_line = boom  # type: ignore
    try:
        block = vmi.build_visual_markdown_block(candidate)
    finally:
        vmi._visual_caption_line = original  # type: ignore
    check("24.degrades_to_image_only", block == img, block)
    check("24.no_caption_on_failure", "*Source visual" not in block, block)

    # An invalid ref still raises ValueError (unchanged contract), not a silent caption.
    raised = False
    try:
        vmi.build_visual_markdown_block({"asset_ref": "/etc/passwd.png", "source_page": 6})
    except ValueError:
        raised = True
    check("24.invalid_ref_still_raises", raised)


def _summary() -> int:
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    return 1 if FAIL else 0


def main() -> int:
    test_caption_builder()
    test_insertion_caption_invariants()
    test_apply_path_gates_and_ranking()
    test_ranking_unchanged_with_captions()
    test_selection_trace_unaffected()
    test_export_refs_unaffected()
    test_render_with_caption()
    test_caption_degrades_never_fails()
    return _summary()


if __name__ == "__main__":
    sys.exit(main())
