#!/usr/bin/env python3
"""Slice 70 — focused tests for table-vs-diagram visual-classification precision.

Slice 69's real operator selection trace localized the remaining visual-pilot failure: all
safe candidates were classified ``diagram_or_figure`` while the two *selected* visuals were,
by manual inspection, clean two-column definition/glossary TABLES — so diagram-first ranking
had no signal and reconstructable tables won. The mechanism is a *classification* gap: a
glossary/definition table has VARIABLE-height rows (multi-line definitions wrap), so its
horizontal text bands are not evenly spaced; Slice 66's text-grid path requires a *regular*
row rhythm and therefore misses it, and with no drawn rules the lightly-ruled path misses it
too — leaving it to fall through to ``diagram_or_figure``.

Slice 70 adds one more bounded, deterministic, pixel-only signal — a ``two_col_split`` — that
fires only when the crop has exactly two substantial text columns separated by a real gutter
AND each column independently contains several separated horizontal text bands. The
per-column row-band requirement is the guard that keeps a labeled DIAGRAM a diagram (text
presence alone is never enough). Row-spacing regularity is intentionally NOT required, which
is what lets variable-height glossary/definition rows qualify.

This suite exercises (numbers track the slice brief):

  1-4   two-column glossary/definition, lightly ruled two-column, text-band-with-central-gutter,
        and strong-grid tables all classify as ``reconstructable_table``;
  5-7   irregular labeled diagram, flowchart/block diagram, and a diagram whose labels create
        text-like dark bands all stay ``diagram_or_figure`` (never table merely for "has text");
  8-11  diagram beats a two-column table at cap 1; at cap 2 one diagram + one table selects
        both with the diagram first; two diagrams + a table selects the two diagrams; only
        tables are still selected when no diagram exists;
  12-13 decorative / low-information crops are still rejected; unknown type preserves prior
        quality-only selection;
  14-16 analysis failure degrades to ``unknown`` and never fails the job; unsafe refs are
        never analyzed; Chandra / Mistral / page_visual_signal are never analyzed or selected;
  17-18 determinism (no OCR / model / cloud) and a full no-leak sweep over markdown, info
        dicts, returned features, and the serialized selection trace;
  19-23 default-off byte-identical output, the two-key gate, default cap 1, hard cap 2, and
        unchanged export ride-along are all preserved;
  24    the sanitized selection trace reflects the improved classification and stays bounded.

Data discipline (no-leak): every PNG is a tiny runtime-built image under a temp dir — never
committed, never base64/data-URI in an assertion. The classifier reads only bounded
non-sensitive pixel summaries; it never OCRs, calls a model/provider/network, serializes or
logs image bytes, or records a path or source text. A final sweep scans every returned
diagnostic / serialized string.

Pixel-type cases SKIP automatically when Pillow is unavailable (the classifier then degrades
to ``unknown``, which this suite also asserts). Run:

    python test_scripts/test_visual_pilot_table_diagram_precision.py
    GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2 python test_scripts/test_visual_pilot_table_diagram_precision.py
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
GGUFLIKE = re.compile(r"\.gguf\b|mmproj|\.bin\b|llama-server", re.IGNORECASE)
ARGVLIKE = re.compile(r"--\w+\s+\S")
_LEAK_PATTERNS = (
    ("key", KEYLIKE), ("path", PATHLIKE), ("url", URLLIKE), ("auth", AUTHLIKE),
    ("socket", SOCKETLIKE), ("datauri", DATAURI), ("gguf", GGUFLIKE), ("argv", ARGVLIKE),
)
_OUTPUTS: list[str] = []

# Page geometry used across the metadata cases (A4-ish, in PDF points).
PW, PH = 612.0, 792.0
BASE_MD = "# Guide\n\nSome content.\n"

try:
    from PIL import Image, ImageDraw  # optional; pixel-type cases skip without it
    _HAVE_PIL = True
except Exception:  # pragma: no cover - env-dependent
    _HAVE_PIL = False


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} :: {detail}")


def skip(name: str, why: str) -> None:
    global SKIP
    SKIP += 1
    print(f"[SKIP] {name} — {why}")


def record(blob: str) -> None:
    if isinstance(blob, str):
        _OUTPUTS.append(blob)


def _sweep_one(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    for label, pat in _LEAK_PATTERNS:
        if pat.search(text):
            return label
    return None


# --- PNG fixtures (runtime-built; never committed) ----------------------------------


def _solid_png(width: int = 96, height: int = 96, value: int = 0x80) -> bytes:
    """A solid grayscale PNG via stdlib only (no Pillow). Classifies as ``unknown``."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes([value]) * width for _ in range(height))
    idat = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# Visual kinds drawn with Pillow. The table kinds deliberately use *gray* (mid-tone) text
# blocks so they exercise the softer-ink band/gutter projections rather than only the strong
# near-black grid. The two-column glossary uses *irregular* row heights (wrapped definitions)
# — exactly the layout Slice 66 missed and Slice 70 must now catch.
_DRAWN_KINDS = {
    "glossary_two_column", "ruled_two_column", "text_band_central_gutter", "strong_grid",
    "labeled_diagram", "flowchart", "diagram", "decorative",
}


def _draw_png(kind: str, path: Path, size=(140, 140)) -> None:
    """Draw a tiny PNG of a given visual KIND with Pillow (caller guards _HAVE_PIL)."""
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    w, h = size
    if kind == "glossary_two_column":
        # Term (left) + multi-line definition (right), VARIABLE row heights, NO drawn rules:
        # the exact glossary/definition layout that Slice 66's regular-rhythm path missed.
        for i, ry in enumerate((12, 38, 66, 96, 120)):
            d.rectangle([10, ry, 38, ry + 8], fill=110)        # short term (left column)
            d.rectangle([60, ry, 132, ry + 8], fill=110)       # definition line 1 (right column)
            if i in (1, 3):                                     # wrapped 2nd line ⇒ irregular rows
                d.rectangle([60, ry + 10, 118, ry + 18], fill=110)
    elif kind == "ruled_two_column":
        # Two text columns + a single THIN central vertical divider (no full grid).
        for ry in (16, 44, 72, 100, 126):
            d.rectangle([10, ry, 40, ry + 8], fill=120)
            d.rectangle([64, ry, 132, ry + 8], fill=120)
        d.line([(52, 0), (52, h)], fill=0, width=1)
    elif kind == "text_band_central_gutter":
        # Two text columns separated by a wide whitespace gutter, no rules at all.
        for ry in (12, 34, 56, 78, 100, 122):
            d.rectangle([8, ry, 42, ry + 8], fill=120)
            d.rectangle([60, ry, 134, ry + 8], fill=120)
    elif kind == "strong_grid":
        # Strong full near-black grid (both ways) — the Slice 64 grid path; must stay a table.
        for x in range(0, w + 1, 20):
            d.line([(x, 0), (x, h)], fill=0, width=2)
        for y in range(0, h + 1, 20):
            d.line([(0, y), (w, y)], fill=0, width=2)
    elif kind == "diagram":
        # Irregular shapes + connectors (no two clean text columns) — stays a diagram.
        d.ellipse([10, 10, 52, 52], outline=0, width=3)
        d.rectangle([70, 18, 104, 58], outline=0, width=3)
        d.line([52, 30, 70, 36], fill=0, width=3)              # connector across the middle
        d.line([20, 62, 92, 104], fill=0, width=3)             # diagonal
        d.ellipse([60, 74, 100, 112], outline=0, width=3)
        d.line([30, 50, 36, 96], fill=0, width=3)
        d.rectangle([12, 86, 34, 110], fill=0)                 # solid block (lowers blank ratio)
    elif kind == "labeled_diagram":
        # An irregular diagram WITH text labels: dark text-like bands exist, but connectors
        # smear ink across the middle and the columns are not stacks of text rows — so the
        # two-column guard must keep it a diagram (it must not become a table for "has text").
        d.ellipse([10, 12, 50, 52], outline=0, width=3)
        d.line([50, 32, 86, 32], fill=0, width=3)              # connector crossing the gutter
        d.rectangle([86, 14, 126, 54], outline=0, width=3)
        d.text((18, 28), "start", fill=0)
        d.text((92, 28), "end", fill=0)
        d.line([28, 52, 70, 108], fill=0, width=3)             # long diagonal
        d.ellipse([64, 80, 108, 118], outline=0, width=3)
        d.text((72, 94), "node", fill=0)
        d.rectangle([12, 96, 32, 120], fill=0)
    elif kind == "flowchart":
        # Vertically stacked blocks with connectors and labels — a single-column diagram.
        for y in (8, 58, 108):
            d.rectangle([46, y, 98, y + 34], outline=0, width=3)
            d.text((58, y + 12), "step", fill=0)
        d.line([72, 42, 72, 58], fill=0, width=3)
        d.line([72, 92, 72, 108], fill=0, width=3)
    elif kind == "decorative":
        d.rectangle([4, 4, 12, 12], fill=0)                    # tiny corner mark only
    else:  # "solid" / fallback
        d.rectangle([0, 0, w, h], fill=0x80)
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


def _figure(asset_id: str, *, page: int, kind: str = "solid", bbox=None, pw=None, ph=None,
            cw=None, ch=None, image_ref=None, provider="fitz_local",
            atype="extracted_figure") -> dict:
    """A manifest figure; ``kind`` selects the drawn PNG (carried out-of-band for fixtures)."""
    asset = {
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
    asset["_kind"] = kind  # test-only hint; stripped before writing the manifest
    return asset


def content_figure(asset_id="content_fig", page=5, *, kind="solid", image_ref=None) -> dict:
    """Content-sized metadata (score 1.2, non-decorative, clears the secondary floor)."""
    return _figure(asset_id, page=page, kind=kind, bbox=[100, 200, 500, 600],
                   pw=PW, ph=PH, cw=800, ch=800, image_ref=image_ref)


def _manifest(assets: list[dict]) -> dict:
    clean = []
    for a in assets:
        a2 = {k: v for k, v in a.items() if k != "_kind"}
        clean.append(a2)
    return {
        "version": 1, "kind": "visual_assets_manifest", "status": "completed",
        "source": "extraction_metadata.json", "assets": clean,
        "summary": {"asset_count": len(clean)}, "warnings": [],
    }


def _make_job(tmp: Path, assets: list[dict], *, opt_in=True, corrupt_for=None) -> FakeJob:
    """Build a FakeJob; write a PNG of each asset's KIND so the file gate + classifier work."""
    job = FakeJob(dir=tmp, opt_in=opt_in)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        aid = asset.get("asset_id")
        ref = asset.get("image_ref")
        if not (isinstance(ref, str) and re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", ref)):
            continue
        dest = job.dir / ref
        if corrupt_for and aid in corrupt_for:
            dest.write_bytes(b"\x89PNG\r\n\x1a\n not a real png body")
            continue
        kind = asset.get("_kind", "solid")
        if kind in _DRAWN_KINDS and _HAVE_PIL:
            _draw_png(kind, dest)
        else:
            dest.write_bytes(_solid_png())
    job.visual_assets_manifest_json.write_text(
        json.dumps(_manifest(assets)) + "\n", encoding="utf-8")
    return job


def _with_env(pairs: dict, fn):
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


def _types(cands) -> list:
    return [c.get("visual_type") for c in cands]


# --- 1-4. tables: two-column / glossary / definition / ruled / text-band / grid -> table ---
def test_tables_classify_as_reconstructable_table() -> None:
    if not _HAVE_PIL:
        skip("tables.classify", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        cases = (
            ("glossary_two_column", "1"),       # (1) two-column glossary/definition, irregular rows
            ("ruled_two_column", "2"),          # (2) lightly ruled two-column (thin divider)
            ("text_band_central_gutter", "3"),  # (3) text bands + central gutter, no rules
            ("strong_grid", "4"),               # (4) strong full grid still a table
        )
        for kind, num in cases:
            _draw_png(kind, td / "assets" / f"{kind}.png")
            got = cls(job, {"asset_ref": f"assets/{kind}.png"})
            check(f"{num}.table.{kind}", got == vmi.VISUAL_TYPE_TABLE, str(got))
            check(f"{num}.table.{kind}_closed_vocab", got in vmi.VISUAL_TYPES, str(got))
        record(json.dumps({"table_types": [cls(job, {"asset_ref": f"assets/{k}.png"})
                                           for k, _ in cases]}))


# --- 5-7. diagrams (incl. labeled) stay diagram; "has text" never flips a diagram ----------
def test_diagrams_stay_diagram() -> None:
    if not _HAVE_PIL:
        skip("diagrams.classify", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        cases = (
            ("diagram", "5"),          # (5) irregular labeled diagram (shapes + connectors)
            ("flowchart", "6"),        # (6) flowchart / block diagram (single column)
            ("labeled_diagram", "7"),  # (7) diagram whose labels make text-like dark bands
        )
        for kind, num in cases:
            _draw_png(kind, td / "assets" / f"{kind}.png")
            got = cls(job, {"asset_ref": f"assets/{kind}.png"})
            check(f"{num}.diagram.{kind}", got == vmi.VISUAL_TYPE_DIAGRAM, str(got))
        # (7) explicit: the labeled diagram's two_col_split signal does NOT fire.
        feats = vmi._visual_type_features(job, "assets/labeled_diagram.png")
        check("7.labeled_diagram_two_col_split_off",
              isinstance(feats, dict) and feats.get("two_col_split") == 0.0, str(feats))
        record(json.dumps({"diagram_types": [cls(job, {"asset_ref": f"assets/{k}.png"})
                                             for k, _ in cases]}))
        record(json.dumps(feats, default=str))


# --- two-column split helper unit (pure; no image) -----------------------------------------
def test_two_column_split_helper() -> None:
    # A clean two-column layout: left block, wide gutter, right block, with >=3 row bands each.
    w = 40
    col_text = ([0.0, 0.0]                    # left margin
                + [0.3, 0.3, 0.3, 0.3, 0.3]   # left column (cols 2..6)
                + [0.0] * 6                    # gutter
                + [0.4] * 18                   # right column
                + [0.0] * 9)                   # right margin -> total 40
    assert len(col_text) == w, len(col_text)
    # Each row band needs ink in both columns: 4 stacked text rows separated by blanks.
    h = 24
    pixels = [255] * (w * h)
    for ry in (2, 8, 14, 20):                  # four separated bands
        for rr in (ry, ry + 1):
            base = rr * w
            for c in list(range(2, 7)) + list(range(14, 32)):
                pixels[base + c] = 90          # ink in both columns
    strength = vmi._two_column_split(pixels, w, h, col_text)
    check("helper.two_col_split_fires", strength == 1.0, str(strength))
    # One wide content block (no gutter) -> not two columns.
    one = vmi._two_column_split([90] * (w * h), w, h, [0.5] * w)
    check("helper.two_col_split_single_block", one == 0.0, str(one))
    # Two columns but only one row band each -> fails the per-column row guard.
    thin = [255] * (w * h)
    base = 5 * w
    for c in list(range(2, 7)) + list(range(14, 32)):
        thin[base + c] = 90
    check("helper.two_col_split_needs_rows",
          vmi._two_column_split(thin, w, h, col_text) == 0.0)
    # Content-span helper: returns measurable spans.
    spans = vmi._content_column_spans(col_text, vmi._LT_COL_GUTTER_MAX)
    check("helper.content_spans_two", len(spans) == 2, str(spans))


# --- 8. diagram beats a two-column table at cap 1 ------------------------------------------
def test_diagram_beats_two_column_cap1() -> None:
    if not _HAVE_PIL:
        skip("cap1.diagram_beats_two_column", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        # Two-column table first in priority order, but the diagram must still win on type.
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="glossary_two_column"),
                                  content_figure("dia", page=6, kind="diagram")])
        cands = sel(job)  # default cap 1
        check("8.diagram_selected", _ids(cands) == ["dia"],
              str(_ids(cands)) + " " + str(_types(cands)))
        check("8.type_is_diagram",
              _types(cands) == [vmi.VISUAL_TYPE_DIAGRAM], str(_types(cands)))


# --- 9. cap 2: one diagram + one two-column table -> both, diagram first --------------------
def test_diagram_then_two_column_cap2() -> None:
    if not _HAVE_PIL:
        skip("cap2.diagram_then_two_column", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="glossary_two_column"),
                                  content_figure("dia", page=8, kind="diagram")])
        cands = sel(job, max_images=2)
        check("9.both_selected", set(_ids(cands)) == {"tbl", "dia"}, str(_ids(cands)))
        check("9.diagram_first", _ids(cands)[0] == "dia", str(_ids(cands)))
        check("9.table_allowed_second",
              _ids(cands)[1] == "tbl" and _types(cands)[1] == vmi.VISUAL_TYPE_TABLE,
              str(_types(cands)))


# --- 10. cap 2: two diagrams + a two-column table -> the two diagrams -----------------------
def test_two_diagrams_beat_two_column_cap2() -> None:
    if not _HAVE_PIL:
        skip("cap2.two_diagrams", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=3, kind="glossary_two_column"),
                                  content_figure("d1", page=5, kind="diagram"),
                                  content_figure("d2", page=7, kind="labeled_diagram")])
        cands = sel(job, max_images=2)
        check("10.two_diagrams_selected", set(_ids(cands)) == {"d1", "d2"}, str(_ids(cands)))
        check("10.no_table_when_diagrams", "tbl" not in _ids(cands), str(_ids(cands)))
        check("10.both_diagram_type",
              _types(cands) == [vmi.VISUAL_TYPE_DIAGRAM, vmi.VISUAL_TYPE_DIAGRAM],
              str(_types(cands)))


# --- 11. only two-column tables -> still selected ------------------------------------------
def test_only_tables_still_selected() -> None:
    if not _HAVE_PIL:
        skip("tables.only_selected", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("t1", page=4, kind="glossary_two_column"),
                                  content_figure("t2", page=6, kind="text_band_central_gutter")])
        c1 = sel(job)  # cap 1
        check("11.cap1_selects_table",
              len(c1) == 1 and _types(c1) == [vmi.VISUAL_TYPE_TABLE], str(_types(c1)))
        c2 = sel(job, max_images=2)  # cap 2
        check("11.cap2_selects_two_tables",
              set(_ids(c2)) == {"t1", "t2"}
              and _types(c2) == [vmi.VISUAL_TYPE_TABLE, vmi.VISUAL_TYPE_TABLE],
              str(_ids(c2)) + " " + str(_types(c2)))


# --- 12. decorative / low-information crop still rejected from preference -------------------
def test_decorative_still_rejected() -> None:
    if not _HAVE_PIL:
        skip("decor.rejected", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        _draw_png("decorative", td / "assets" / "dec.png")
        check("12.decorative_classified",
              cls(job, {"asset_ref": "assets/dec.png"}) == vmi.VISUAL_TYPE_DECORATIVE)
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("dec", page=4, kind="decorative"),
                                  content_figure("tbl", page=6, kind="glossary_two_column")])
        c1 = sel(job)
        check("12.table_beats_decorative",
              _ids(c1) == ["tbl"] and _types(c1) == [vmi.VISUAL_TYPE_TABLE], str(_types(c1)))


# --- 13. unknown type preserves prior quality-only behavior --------------------------------
def test_unknown_preserves_prior_behavior() -> None:
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5, kind="solid"),
                                  content_figure("c2", page=8, kind="solid")])
        c1 = sel(job)
        check("13.default_one", _ids(c1) == ["c1"], str(_ids(c1)))
        check("13.type_unknown", _types(c1) == [vmi.VISUAL_TYPE_UNKNOWN], str(_types(c1)))
        c2 = sel(job, max_images=2)
        check("13.cap2_two_distinct_pages",
              set(_ids(c2)) == {"c1", "c2"} and c2[0]["asset_id"] == "c1", str(_ids(c2)))


# --- 14. analysis failure degrades to unknown and never fails the job ----------------------
def test_analysis_failure_degrades() -> None:
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("corrupt", page=5, kind="solid")],
                        corrupt_for={"corrupt"})
        got = cls(job, {"asset_ref": "assets/corrupt.png"})
        check("14.corrupt_unknown", got == vmi.VISUAL_TYPE_UNKNOWN, str(got))
        out, info = _with_env({vmi.ENABLE_ENV: "1"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out); record(json.dumps(info, default=str))
        check("14.pilot_still_inserts",
              info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
        check("14.info_type_unknown_or_none",
              info.get("visual_type") in (vmi.VISUAL_TYPE_UNKNOWN, None),
              str(info.get("visual_type")))


# --- 15. unsafe refs are never analyzed ----------------------------------------------------
def test_unsafe_refs_never_analyzed() -> None:
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = FakeJob(dir=Path(d))
        for ref in ("/etc/passwd.png", "assets/../secret.png", "assets\\fig.png",
                    "https://example.com/a.png", "data:image/png;base64,AAAA.png",
                    "assets/fig.jpg", "assets/sub/fig.png", None, 123):
            got = cls(job, {"asset_ref": ref})
            check(f"15.unsafe_unknown[{ref!r}]", got == vmi.VISUAL_TYPE_UNKNOWN, str(got))
    if _HAVE_PIL:
        with tempfile.TemporaryDirectory() as d:
            bad = content_figure("bad", page=4, kind="glossary_two_column",
                                 image_ref="/etc/passwd.png")
            good = content_figure("safe", page=6, kind="glossary_two_column")
            job = _make_job(Path(d), [bad, good])
            check("15.only_safe_selected", _ids(sel(job, max_images=2)) == ["safe"],
                  str(_ids(sel(job, max_images=2))))


# --- 16. chandra / mistral / page_visual_signal are never analyzed or selected -------------
def test_blocked_providers_excluded() -> None:
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        chandra = content_figure("chandra", page=4, kind="glossary_two_column")
        chandra["source_provider"] = "chandra_local"
        mistral = content_figure("mistral", page=4, kind="glossary_two_column")
        mistral["source_provider"] = "mistral_ocr"
        signal = content_figure("signal", page=4, kind="glossary_two_column")
        signal["asset_type"] = "page_visual_signal"
        good = content_figure("fitz", page=5, kind="solid")
        job = _make_job(Path(d), [chandra, mistral, signal, good])
        check("16.only_fitz_selected", _ids(sel(job, max_images=2)) == ["fitz"],
              str(_ids(sel(job, max_images=2))))


# --- 17 & 18. determinism (no model/cloud), closed-vocab features, and no leaks ------------
def test_determinism_and_diagnostics() -> None:
    if not _HAVE_PIL:
        skip("info.diagnostics", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        _draw_png("glossary_two_column", td / "assets" / "g.png")
        # Deterministic across repeated calls (pure pixel arithmetic; no model/network).
        results = {cls(job, {"asset_ref": "assets/g.png"}) for _ in range(5)}
        check("17.determinism_stable", results == {vmi.VISUAL_TYPE_TABLE}, str(results))
        # Returned features are bounded numeric summaries only — no text / bytes / path.
        feats = vmi._visual_type_features(job, "assets/g.png")
        check("18.features_all_numeric",
              isinstance(feats, dict) and all(isinstance(v, float) for v in feats.values()),
              str(feats))
        check("18.two_col_split_feature_present",
              "two_col_split" in feats and feats["two_col_split"] in (0.0, 1.0), str(feats))
        record(json.dumps(feats, default=str))

    # The success info carries only a safe closed-vocab visual_type token (cap 2).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="glossary_two_column"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out); record(json.dumps(info, default=str))
        check("18.info_visual_type_closed_vocab",
              info.get("visual_type") in vmi.VISUAL_TYPES, str(info.get("visual_type")))
        check("18.info_first_is_diagram",
              info.get("visual_type") == vmi.VISUAL_TYPE_DIAGRAM, str(info))


# --- 19, 20, 21, 22. gate / default-off / cap invariants (unchanged) -----------------------
def test_gate_and_cap_invariants() -> None:
    sel = vmi.select_visual_markdown_candidates
    kind = "glossary_two_column" if _HAVE_PIL else "solid"

    # (21) default cap remains exactly 1 even with two great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind),
                                  content_figure("b", page=8, kind=kind)])
        check("21.cap_default_one", len(sel(job)) == 1, str(len(sel(job))))

    # (22) cap is hard-bounded at 2 — an over-large request never widens it.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind),
                                  content_figure("b", page=7, kind=kind),
                                  content_figure("c", page=9, kind=kind)])
        check("22.cap_hard_max_2", len(sel(job, max_images=99)) == 2,
              str(len(sel(job, max_images=99))))
        check("22.cap_env_hard_max_2",
              _with_env({vmi.MAX_IMAGES_ENV: "99"}, vmi.visual_markdown_pilot_max_images) == 1)

    # (19) default-OFF (env unset) -> byte-identical, even with great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind)])
        out, info = _with_env({vmi.ENABLE_ENV: None},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("19.default_off_byte_identical", out == BASE_MD, repr(out[:60]))
        check("19.default_off_reason", info.get("reason") == vmi.SKIP_DISABLED, str(info))

    # (20) two-key gate unchanged: only (env on, opt-in on) inserts, even at cap 2.
    for name, env, opt_in, may in (
        ("off_off", None, False, False),
        ("off_on", None, True, False),
        ("on_off", "1", False, False),
        ("on_on", "1", True, True),
    ):
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(Path(d), [content_figure("a", page=5, kind=kind),
                                      content_figure("b", page=8, kind=kind)], opt_in=opt_in)
            out, info = _with_env({vmi.ENABLE_ENV: env, vmi.MAX_IMAGES_ENV: "2"},
                                  lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
            record(out); record(json.dumps(info, default=str))
            if may:
                check(f"20.gate_{name}_inserted",
                      info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
            else:
                check(f"20.gate_{name}_byte_identical",
                      out == BASE_MD and "![" not in out, str(info))


# --- 23. export ride-along behavior is unchanged -------------------------------------------
def test_export_ride_along_unchanged() -> None:
    if not _HAVE_PIL:
        skip("export.ride_along", "Pillow unavailable")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="glossary_two_column"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        job.clean_md.write_text(out, encoding="utf-8")
        refs = vmi.find_exportable_visual_pilot_assets(job)
        record(out); record(json.dumps({"refs": refs}, default=str))
        # Refs are safe job-local ``assets/<slug>.png`` only, capped at the hard max of 2.
        check("23.refs_safe",
              all(vmi.validate_visual_asset_ref(r) == r for r in refs) and len(refs) <= 2,
              str(refs))
        check("23.refs_match_inserted",
              set(refs) == {"assets/tbl.png", "assets/dia.png"}, str(refs))


# --- 24. the sanitized selection trace reflects the improved classification ----------------
def test_selection_trace_reflects_classification() -> None:
    if not _HAVE_PIL:
        skip("trace.reflects_classification", "Pillow unavailable")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="glossary_two_column"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        trace_path = job.dir / vmi.SELECTION_TRACE_FILENAME
        check("24.trace_written", trace_path.is_file(), str(trace_path))
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        record(json.dumps(trace, default=str))
        summary = trace.get("candidate_summary", {})
        type_counts = summary.get("type_counts", {})
        # Improved classification: both a diagram AND a reconstructable table are now seen —
        # the type buckets are no longer collapsed into one (the Slice 69 failure mode).
        check("24.type_counts_split",
              type_counts.get(vmi.VISUAL_TYPE_DIAGRAM, 0) >= 1
              and type_counts.get(vmi.VISUAL_TYPE_TABLE, 0) >= 1, str(type_counts))
        # The diagram is selected first via diagram-first ranking; the table rides second.
        selected = trace.get("selected_candidates", [])
        sel_types = [c.get("visual_type") for c in selected]
        check("24.diagram_selected_first",
              sel_types[:1] == [vmi.VISUAL_TYPE_DIAGRAM], str(sel_types))
        check("24.table_present_second",
              vmi.VISUAL_TYPE_TABLE in sel_types, str(sel_types))
        check("24.diagram_first_reason",
              any(c.get("selection_reason") == vmi.TRACE_SELECTED_DIAGRAM_FIRST
                  for c in selected), str([c.get("selection_reason") for c in selected]))
        # The trace stays bounded + closed-vocab: classification tokens only, no path/text.
        for c in selected:
            check("24.classification_token_closed",
                  c.get("classification") in vmi._VT_TO_CLASSIFIED.values(),
                  str(c.get("classification")))


# --- final. no-leak sweep over everything recorded -----------------------------------------
def test_no_leak_sweep() -> None:
    leaks = []
    for blob in _OUTPUTS:
        found = _sweep_one(blob)
        if found is not None:
            leaks.append(found)
    check("sweep.no_leaks", not leaks, ",".join(sorted(set(leaks))))
    check("sweep.had_outputs", len(_OUTPUTS) > 0, str(len(_OUTPUTS)))


def main() -> int:
    test_tables_classify_as_reconstructable_table()
    test_diagrams_stay_diagram()
    test_two_column_split_helper()
    test_diagram_beats_two_column_cap1()
    test_diagram_then_two_column_cap2()
    test_two_diagrams_beat_two_column_cap2()
    test_only_tables_still_selected()
    test_decorative_still_rejected()
    test_unknown_preserves_prior_behavior()
    test_analysis_failure_degrades()
    test_unsafe_refs_never_analyzed()
    test_blocked_providers_excluded()
    test_determinism_and_diagnostics()
    test_gate_and_cap_invariants()
    test_export_ride_along_unchanged()
    test_selection_trace_reflects_classification()
    test_no_leak_sweep()
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
