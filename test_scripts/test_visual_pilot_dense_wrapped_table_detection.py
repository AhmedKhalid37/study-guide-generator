#!/usr/bin/env python3
"""Slice 72 — focused tests for dense ruled / wrapped-cell two-column table detection.

Slice 71's real operator validation showed Slice 70 measurably improved table-vs-diagram
classification (the trace's type buckets split: 9 diagram + 2 table where Slice 69 read 11 + 0),
yet the two *selected* visuals were STILL reconstructable two-column definition tables. The
residual mechanism: those tables are densely ruled with WRAPPED multi-line description cells, so
each column's antialiased wrapped lines merge into too FEW separated horizontal text bands for
Slice 70's ``two_col_split`` per-column band guard (≥ 3 bands) to fire — leaving them to fall
through to ``diagram_or_figure`` and lead the diagram tier.

Slice 72 adds one more bounded, deterministic, pixel-only signal — ``dense_wrapped_two_col`` —
that does NOT rely on band count. It pairs the two-column structure with two guards a diagram
cannot fake: a *persistent* clean vertical gutter (a diagram's connectors/diagonals break it)
and per-column *text richness* (avg ink-runs per inked row — several words per row, not a
continuous shape outline). So a dense wrapped definition table whose merged bands defeat the
Slice 70 guard still classifies as ``reconstructable_table`` while a labeled diagram stays
``diagram_or_figure`` and diagrams/figures still beat reconstructable tables in ranking.

This suite exercises (numbers track the slice brief):

  1-4   dense two-column, wrapped-cell two-column, ruled wrapped, and lightly-ruled wrapped
        tables all classify as ``reconstructable_table`` (case 1 proves the NEW path: it fires
        when Slice 70's ``two_col_split`` does not);
  5-6   the existing two-column glossary table and a strong-grid table still classify as table;
  7-9   irregular labeled diagram, flowchart/block diagram, and a labeled diagram with text-like
        dark bands all stay ``diagram_or_figure`` (text presence alone never flips a diagram);
  10-13 diagram beats a dense wrapped table at cap 1; at cap 2 one diagram + one dense table
        selects both with the diagram first; two diagrams + a dense table selects the two
        diagrams; only dense wrapped tables are still selected when no diagram exists;
  14-15 decorative / low-information crops are still rejected; unknown type preserves prior
        quality-only selection;
  16-18 analysis failure degrades to ``unknown`` and never fails the job; unsafe refs are never
        analyzed; Chandra / Mistral / page_visual_signal are never analyzed or selected;
  19-20 determinism (no OCR / model / cloud) and a full no-leak sweep over markdown, info dicts,
        returned features, and the serialized selection trace;
  21-26 default-off byte-identical output, the two-key gate, default cap 1, hard cap 2, unchanged
        export ride-along, and the sanitized + bounded selection trace are all preserved.

Data discipline (no-leak): every PNG is a tiny runtime-built image under a temp dir — never
committed, never base64/data-URI in an assertion. The classifier reads only bounded
non-sensitive pixel summaries; it never OCRs, calls a model/provider/network, serializes or
logs image bytes, or records a path or source text. A final sweep scans every returned
diagnostic / serialized string.

Pixel-type cases SKIP automatically when Pillow is unavailable (the classifier then degrades to
``unknown``, which this suite also asserts). Run:

    python test_scripts/test_visual_pilot_dense_wrapped_table_detection.py
    GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2 python test_scripts/test_visual_pilot_dense_wrapped_table_detection.py
"""
from __future__ import annotations

import json
import os
import random
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


def _words(d, x0: int, x1: int, y0: int, y1: int, *, pitch: int = 4, fill: int = 70,
           seed: int = 0) -> None:
    """Fill a cell with short, word-like horizontal ink segments (DENSE wrapped text).

    Several short runs per row (multiple "words") and many stacked rows — the texture a real
    text column has and a continuous diagram shape does not. ``pitch`` is the vertical spacing
    between text lines; ``pitch=1`` packs every row so the bands MERGE (the real wrapped-table
    failure shape that defeats Slice 70's per-column band guard).
    """
    rnd = random.Random((x0 * 131 + y0 * 17 + seed))
    y = y0
    while y < y1:
        x = x0
        while x < x1 - 4:
            wlen = min(rnd.randint(4, 12), x1 - x)
            d.line([(x, y), (x + wlen, y)], fill=fill, width=1)
            x += wlen + rnd.randint(2, 4)
        y += pitch


# Visual kinds drawn with Pillow. The dense/wrapped table kinds render real word-textured columns
# separated by a clean vertical gutter; the diagram kinds use continuous shapes + cross-gutter
# connectors so the dense-wrapped guard must keep them diagrams.
_DRAWN_KINDS = {
    "dense_wrapped", "dense_wrapped_merged", "wrapped_cell", "ruled_wrapped",
    "lightly_ruled_wrapped", "glossary_two_column", "strong_grid",
    "labeled_diagram", "flowchart", "diagram", "decorative",
}


def _draw_png(kind: str, path: Path, size=(160, 160)) -> None:
    """Draw a tiny PNG of a given visual KIND with Pillow (caller guards _HAVE_PIL)."""
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    w, h = size
    if kind == "dense_wrapped":
        # Two dense word-text columns + a clean central gutter (rows separated -> many bands).
        _words(d, 8, 46, 8, 152, pitch=4)
        _words(d, 66, 152, 8, 152, pitch=4, seed=3)
    elif kind == "dense_wrapped_merged":
        # Same two columns but pitch=1 packs every row so per-column bands MERGE to ~1 — the
        # exact wrapped failure shape: Slice 70's two_col_split cannot fire, Slice 72's must.
        _words(d, 8, 46, 8, 152, pitch=1)
        _words(d, 66, 152, 8, 152, pitch=1, seed=3)
    elif kind == "wrapped_cell":
        # Variable-height wrapped cells (entries) with blank gaps between them, both columns.
        for (y0, y1) in ((8, 40), (48, 96), (104, 152)):
            _words(d, 8, 46, y0, y1, pitch=3)
            _words(d, 66, 152, y0, y1, pitch=3, seed=7)
    elif kind == "ruled_wrapped":
        # Dense wrapped columns + full-width dark horizontal rules between rows.
        _words(d, 8, 46, 8, 152, pitch=3, seed=5)
        _words(d, 66, 152, 8, 152, pitch=3, seed=9)
        for ry in range(8, 153, 28):
            d.line([(6, ry), (154, ry)], fill=0, width=1)
    elif kind == "lightly_ruled_wrapped":
        # Dense wrapped columns + FAINT rules (above the dark threshold) — relies on text texture.
        _words(d, 8, 46, 8, 152, pitch=3, seed=2)
        _words(d, 66, 152, 8, 152, pitch=3, seed=4)
        for ry in range(8, 153, 28):
            d.line([(6, ry), (154, ry)], fill=170, width=1)
    elif kind == "glossary_two_column":
        # Slice 70 fixture: term (left) + multi-line definition (right), VARIABLE row heights,
        # NO drawn rules — still a table (via the established two_col_split path).
        for i, ry in enumerate((12, 38, 66, 96, 120, 140)):
            d.rectangle([10, ry, 38, ry + 8], fill=110)
            d.rectangle([60, ry, 150, ry + 8], fill=110)
            if i in (1, 3):
                d.rectangle([60, ry + 10, 130, ry + 18], fill=110)
    elif kind == "strong_grid":
        # Strong full near-black grid (both ways) — the Slice 64 grid path; must stay a table.
        for x in range(0, w + 1, 20):
            d.line([(x, 0), (x, h)], fill=0, width=2)
        for y in range(0, h + 1, 20):
            d.line([(0, y), (w, y)], fill=0, width=2)
    elif kind == "diagram":
        # Irregular shapes + connectors (no two clean text columns) — stays a diagram. Drawn to
        # span the whole canvas so the blank ratio stays well below the low-information threshold.
        d.ellipse([12, 12, 64, 64], outline=0, width=3)
        d.rectangle([88, 18, 140, 70], outline=0, width=3)
        d.line([64, 38, 88, 44], fill=0, width=3)              # connector across the middle
        d.line([24, 76, 120, 128], fill=0, width=3)            # long diagonal
        d.ellipse([74, 92, 138, 144], outline=0, width=3)
        d.line([38, 64, 44, 124], fill=0, width=3)
        d.rectangle([14, 104, 46, 144], fill=0)                # solid block
        d.line([100, 70, 110, 92], fill=0, width=3)
    elif kind == "labeled_diagram":
        # An irregular diagram WITH text labels: dark text-like bands exist, but connectors smear
        # ink across the middle and the columns are continuous shapes (not text-rich stacks) — so
        # the dense-wrapped guard must keep it a diagram (it must not become a table for "has text").
        d.ellipse([12, 14, 60, 62], outline=0, width=3)
        d.line([60, 38, 104, 38], fill=0, width=3)             # connector crossing the gutter
        d.rectangle([104, 16, 150, 64], outline=0, width=3)
        d.text((22, 34), "start", fill=0)
        d.text((112, 34), "end", fill=0)
        d.line([34, 62, 88, 132], fill=0, width=3)             # long diagonal
        d.ellipse([78, 96, 142, 144], outline=0, width=3)
        d.text((92, 116), "node", fill=0)
        d.rectangle([14, 112, 40, 146], fill=0)
    elif kind == "flowchart":
        # Vertically stacked blocks with connectors and labels — a single-column diagram.
        for y in (8, 64, 120):
            d.rectangle([54, y, 118, y + 38], outline=0, width=3)
            d.text((70, y + 14), "step", fill=0)
        d.line([86, 46, 86, 64], fill=0, width=3)
        d.line([86, 102, 86, 120], fill=0, width=3)
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


# --- 1-4. dense / wrapped / ruled / lightly-ruled wrapped tables -> reconstructable_table ---
def test_dense_wrapped_tables_classify_as_table() -> None:
    if not _HAVE_PIL:
        skip("dense_wrapped.classify", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        cases = (
            ("dense_wrapped", "1"),          # (1) dense two-column wrapped text
            ("wrapped_cell", "2"),           # (2) variable-height wrapped cells
            ("ruled_wrapped", "3"),          # (3) ruled wrapped table (dark rules)
            ("lightly_ruled_wrapped", "4"),  # (4) lightly ruled wrapped table (faint rules)
        )
        for kind, num in cases:
            _draw_png(kind, td / "assets" / f"{kind}.png")
            got = cls(job, {"asset_ref": f"assets/{kind}.png"})
            check(f"{num}.table.{kind}", got == vmi.VISUAL_TYPE_TABLE, str(got))
            check(f"{num}.table.{kind}_closed_vocab", got in vmi.VISUAL_TYPES, str(got))
        record(json.dumps({"table_types": [cls(job, {"asset_ref": f"assets/{k}.png"})
                                           for k, _ in cases]}))


# --- 1 (proof). the NEW dense-wrapped path fires when Slice 70's band guard cannot -----------
def test_new_path_fires_when_band_guard_cannot() -> None:
    if not _HAVE_PIL:
        skip("new_path.merged_bands", "Pillow unavailable")
        return
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        _draw_png("dense_wrapped_merged", td / "assets" / "m.png")
        feats = vmi._visual_type_features(job, "assets/m.png")
        record(json.dumps(feats, default=str))
        # Merged bands: Slice 70's two_col_split CANNOT fire (per-column bands < 3) ...
        check("1p.two_col_split_off",
              isinstance(feats, dict) and feats.get("two_col_split") == 0.0, str(feats))
        # ... but the Slice 72 dense-wrapped signal DOES, so it still classifies as a table.
        check("1p.dense_wrapped_on",
              isinstance(feats, dict) and feats.get("dense_wrapped_two_col") == 1.0, str(feats))
        check("1p.classified_table",
              vmi._classify_visual_type_from_features(feats) == vmi.VISUAL_TYPE_TABLE, str(feats))
        check("1p.feature_closed_range",
              feats.get("dense_wrapped_two_col") in (0.0, 1.0), str(feats))


# --- 5-6. existing glossary table + strong grid still classify as table ----------------------
def test_existing_tables_still_table() -> None:
    if not _HAVE_PIL:
        skip("existing_tables.classify", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        for kind, num in (("glossary_two_column", "5"), ("strong_grid", "6")):
            _draw_png(kind, td / "assets" / f"{kind}.png")
            got = cls(job, {"asset_ref": f"assets/{kind}.png"})
            check(f"{num}.table.{kind}", got == vmi.VISUAL_TYPE_TABLE, str(got))


# --- 7-9. diagrams (incl. labeled) stay diagram; "has text" never flips a diagram ------------
def test_diagrams_stay_diagram() -> None:
    if not _HAVE_PIL:
        skip("diagrams.classify", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        for kind, num in (("diagram", "7"), ("flowchart", "8"), ("labeled_diagram", "9")):
            _draw_png(kind, td / "assets" / f"{kind}.png")
            got = cls(job, {"asset_ref": f"assets/{kind}.png"})
            check(f"{num}.not_table.{kind}", got != vmi.VISUAL_TYPE_TABLE, str(got))
            feats = vmi._visual_type_features(job, f"assets/{kind}.png")
            check(f"{num}.dense_wrapped_off.{kind}",
                  isinstance(feats, dict) and feats.get("dense_wrapped_two_col") == 0.0,
                  str(feats))
            record(json.dumps(feats, default=str))
        # (9) the labeled diagram (text-like dark bands) is specifically NOT a table.
        check("9.labeled_diagram_is_diagram",
              cls(job, {"asset_ref": "assets/labeled_diagram.png"}) == vmi.VISUAL_TYPE_DIAGRAM,
              "labeled_diagram")


# --- dense-wrapped helper units (pure; no image) ---------------------------------------------
def test_dense_wrapped_helper_units() -> None:
    # Two text-rich columns with a clean persistent gutter: the signal fires.
    w, h = 48, 40
    col_text = ([0.0]                                   # left margin
                + [0.4] * 14                            # left column (cols 1..14)
                + [0.0] * 8                             # gutter (cols 15..22)
                + [0.4] * 18                            # right column (cols 23..40)
                + [0.0] * 7)                            # right margin -> total 48
    assert len(col_text) == w, len(col_text)
    pixels = [255] * (w * h)
    for r in range(h):                                  # every row text-rich: several runs/col
        base = r * w
        for c in (2, 5, 8, 11, 24, 28, 32, 36):         # multiple short "words" per row
            pixels[base + c] = 80
    fires = vmi._dense_wrapped_two_column(pixels, w, h, col_text)
    check("helper.dense_wrapped_fires", fires == 1.0, str(fires))
    # Two SOLID column blobs (one run per row each) -> text richness fails -> does not fire.
    solid = [255] * (w * h)
    for r in range(h):
        base = r * w
        for c in list(range(1, 15)) + list(range(23, 41)):
            solid[base + c] = 80
    check("helper.solid_blobs_no_fire",
          vmi._dense_wrapped_two_column(solid, w, h, col_text) == 0.0)
    # A gutter broken on most rows (connectors crossing) -> persistent-gutter guard fails.
    crossed = [v for v in pixels]
    for r in range(h):
        for c in range(15, 23):
            crossed[r * w + c] = 80                      # ink fills the gutter every row
    # recompute col_text so the gutter now reads as content (a single wide column).
    ctt = []
    for c in range(w):
        ink = sum(1 for r in range(h) if crossed[r * w + c] <= vmi._LT_INK)
        ctt.append(ink / h)
    check("helper.broken_gutter_no_fire",
          vmi._dense_wrapped_two_column(crossed, w, h, ctt) == 0.0)
    # Richness helper: text row scores > 1; a solid run scores ~1.
    rich = vmi._column_text_richness(pixels, w, h, 1, 15)
    check("helper.richness_text_high", rich >= vmi._DW_MIN_COL_RICHNESS, str(rich))
    check("helper.richness_solid_low",
          vmi._column_text_richness(solid, w, h, 1, 15) <= 1.5,
          str(vmi._column_text_richness(solid, w, h, 1, 15)))
    # Gutter consistency: clean gutter ~1.0, fully-inked band ~0.0.
    check("helper.gutter_clear",
          vmi._gutter_consistency(pixels, w, h, 15, 23) >= 0.9,
          str(vmi._gutter_consistency(pixels, w, h, 15, 23)))


# --- 10. diagram beats a dense wrapped table at cap 1 ----------------------------------------
def test_diagram_beats_dense_wrapped_cap1() -> None:
    if not _HAVE_PIL:
        skip("cap1.diagram_beats_dense", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        # Dense wrapped table first in priority order, but the diagram must still win on type.
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="dense_wrapped"),
                                  content_figure("dia", page=6, kind="diagram")])
        cands = sel(job)  # default cap 1
        check("10.diagram_selected", _ids(cands) == ["dia"],
              str(_ids(cands)) + " " + str(_types(cands)))
        check("10.type_is_diagram",
              _types(cands) == [vmi.VISUAL_TYPE_DIAGRAM], str(_types(cands)))


# --- 11. cap 2: one diagram + one dense wrapped table -> both, diagram first ------------------
def test_diagram_then_dense_wrapped_cap2() -> None:
    if not _HAVE_PIL:
        skip("cap2.diagram_then_dense", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="dense_wrapped"),
                                  content_figure("dia", page=8, kind="diagram")])
        cands = sel(job, max_images=2)
        check("11.both_selected", set(_ids(cands)) == {"tbl", "dia"}, str(_ids(cands)))
        check("11.diagram_first", _ids(cands)[0] == "dia", str(_ids(cands)))
        check("11.table_allowed_second",
              _ids(cands)[1] == "tbl" and _types(cands)[1] == vmi.VISUAL_TYPE_TABLE,
              str(_types(cands)))


# --- 12. cap 2: two diagrams + a dense wrapped table -> the two diagrams ----------------------
def test_two_diagrams_beat_dense_wrapped_cap2() -> None:
    if not _HAVE_PIL:
        skip("cap2.two_diagrams", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=3, kind="dense_wrapped"),
                                  content_figure("d1", page=5, kind="diagram"),
                                  content_figure("d2", page=7, kind="labeled_diagram")])
        cands = sel(job, max_images=2)
        check("12.two_diagrams_selected", set(_ids(cands)) == {"d1", "d2"}, str(_ids(cands)))
        check("12.no_table_when_diagrams", "tbl" not in _ids(cands), str(_ids(cands)))
        check("12.both_diagram_type",
              _types(cands) == [vmi.VISUAL_TYPE_DIAGRAM, vmi.VISUAL_TYPE_DIAGRAM],
              str(_types(cands)))


# --- 13. only dense wrapped tables -> still selected -----------------------------------------
def test_only_dense_wrapped_still_selected() -> None:
    if not _HAVE_PIL:
        skip("dense.only_selected", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("t1", page=4, kind="dense_wrapped"),
                                  content_figure("t2", page=6, kind="wrapped_cell")])
        c1 = sel(job)  # cap 1
        check("13.cap1_selects_table",
              len(c1) == 1 and _types(c1) == [vmi.VISUAL_TYPE_TABLE], str(_types(c1)))
        c2 = sel(job, max_images=2)  # cap 2
        check("13.cap2_selects_two_tables",
              set(_ids(c2)) == {"t1", "t2"}
              and _types(c2) == [vmi.VISUAL_TYPE_TABLE, vmi.VISUAL_TYPE_TABLE],
              str(_ids(c2)) + " " + str(_types(c2)))


# --- 14. decorative / low-information crop still rejected from preference --------------------
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
        check("14.decorative_classified",
              cls(job, {"asset_ref": "assets/dec.png"}) == vmi.VISUAL_TYPE_DECORATIVE)
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("dec", page=4, kind="decorative"),
                                  content_figure("tbl", page=6, kind="dense_wrapped")])
        c1 = sel(job)
        check("14.table_beats_decorative",
              _ids(c1) == ["tbl"] and _types(c1) == [vmi.VISUAL_TYPE_TABLE], str(_types(c1)))


# --- 15. unknown type preserves prior quality-only behavior ---------------------------------
def test_unknown_preserves_prior_behavior() -> None:
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5, kind="solid"),
                                  content_figure("c2", page=8, kind="solid")])
        c1 = sel(job)
        check("15.default_one", _ids(c1) == ["c1"], str(_ids(c1)))
        check("15.type_unknown", _types(c1) == [vmi.VISUAL_TYPE_UNKNOWN], str(_types(c1)))
        c2 = sel(job, max_images=2)
        check("15.cap2_two_distinct_pages",
              set(_ids(c2)) == {"c1", "c2"} and c2[0]["asset_id"] == "c1", str(_ids(c2)))


# --- 16. analysis failure degrades to unknown and never fails the job -----------------------
def test_analysis_failure_degrades() -> None:
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("corrupt", page=5, kind="solid")],
                        corrupt_for={"corrupt"})
        got = cls(job, {"asset_ref": "assets/corrupt.png"})
        check("16.corrupt_unknown", got == vmi.VISUAL_TYPE_UNKNOWN, str(got))
        out, info = _with_env({vmi.ENABLE_ENV: "1"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out); record(json.dumps(info, default=str))
        check("16.pilot_still_inserts",
              info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
        check("16.info_type_unknown_or_none",
              info.get("visual_type") in (vmi.VISUAL_TYPE_UNKNOWN, None),
              str(info.get("visual_type")))


# --- 17. unsafe refs are never analyzed -----------------------------------------------------
def test_unsafe_refs_never_analyzed() -> None:
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = FakeJob(dir=Path(d))
        for ref in ("/etc/passwd.png", "assets/../secret.png", "assets\\fig.png",
                    "https://example.com/a.png", "data:image/png;base64,AAAA.png",
                    "assets/fig.jpg", "assets/sub/fig.png", None, 123):
            got = cls(job, {"asset_ref": ref})
            check(f"17.unsafe_unknown[{ref!r}]", got == vmi.VISUAL_TYPE_UNKNOWN, str(got))
    if _HAVE_PIL:
        with tempfile.TemporaryDirectory() as d:
            bad = content_figure("bad", page=4, kind="dense_wrapped",
                                 image_ref="/etc/passwd.png")
            good = content_figure("safe", page=6, kind="dense_wrapped")
            job = _make_job(Path(d), [bad, good])
            check("17.only_safe_selected", _ids(sel(job, max_images=2)) == ["safe"],
                  str(_ids(sel(job, max_images=2))))


# --- 18. chandra / mistral / page_visual_signal are never analyzed or selected --------------
def test_blocked_providers_excluded() -> None:
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        chandra = content_figure("chandra", page=4, kind="dense_wrapped")
        chandra["source_provider"] = "chandra_local"
        mistral = content_figure("mistral", page=4, kind="dense_wrapped")
        mistral["source_provider"] = "mistral_ocr"
        signal = content_figure("signal", page=4, kind="dense_wrapped")
        signal["asset_type"] = "page_visual_signal"
        good = content_figure("fitz", page=5, kind="solid")
        job = _make_job(Path(d), [chandra, mistral, signal, good])
        check("18.only_fitz_selected", _ids(sel(job, max_images=2)) == ["fitz"],
              str(_ids(sel(job, max_images=2))))


# --- 19 & 20. determinism (no model/cloud), closed-vocab features, and no leaks -------------
def test_determinism_and_diagnostics() -> None:
    if not _HAVE_PIL:
        skip("info.diagnostics", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        _draw_png("dense_wrapped_merged", td / "assets" / "g.png")
        # Deterministic across repeated calls (pure pixel arithmetic; no model/network).
        results = {cls(job, {"asset_ref": "assets/g.png"}) for _ in range(5)}
        check("19.determinism_stable", results == {vmi.VISUAL_TYPE_TABLE}, str(results))
        # Returned features are bounded numeric summaries only — no text / bytes / path.
        feats = vmi._visual_type_features(job, "assets/g.png")
        check("20.features_all_numeric",
              isinstance(feats, dict) and all(isinstance(v, float) for v in feats.values()),
              str(feats))
        check("20.dense_wrapped_feature_present",
              "dense_wrapped_two_col" in feats and feats["dense_wrapped_two_col"] in (0.0, 1.0),
              str(feats))
        record(json.dumps(feats, default=str))

    # The success info carries only a safe closed-vocab visual_type token (cap 2).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="dense_wrapped"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out); record(json.dumps(info, default=str))
        check("20.info_visual_type_closed_vocab",
              info.get("visual_type") in vmi.VISUAL_TYPES, str(info.get("visual_type")))
        check("20.info_first_is_diagram",
              info.get("visual_type") == vmi.VISUAL_TYPE_DIAGRAM, str(info))


# --- 21, 22, 23, 24. gate / default-off / cap invariants (unchanged) ------------------------
def test_gate_and_cap_invariants() -> None:
    sel = vmi.select_visual_markdown_candidates
    kind = "dense_wrapped" if _HAVE_PIL else "solid"

    # (23) default cap remains exactly 1 even with two great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind),
                                  content_figure("b", page=8, kind=kind)])
        check("23.cap_default_one", len(sel(job)) == 1, str(len(sel(job))))

    # (24) cap is hard-bounded at 2 — an over-large request never widens it.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind),
                                  content_figure("b", page=7, kind=kind),
                                  content_figure("c", page=9, kind=kind)])
        check("24.cap_hard_max_2", len(sel(job, max_images=99)) == 2,
              str(len(sel(job, max_images=99))))
        check("24.cap_env_hard_max_2",
              _with_env({vmi.MAX_IMAGES_ENV: "99"}, vmi.visual_markdown_pilot_max_images) == 1)

    # (21) default-OFF (env unset) -> byte-identical, even with great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind)])
        out, info = _with_env({vmi.ENABLE_ENV: None},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("21.default_off_byte_identical", out == BASE_MD, repr(out[:60]))
        check("21.default_off_reason", info.get("reason") == vmi.SKIP_DISABLED, str(info))

    # (22) two-key gate unchanged: only (env on, opt-in on) inserts, even at cap 2.
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
                check(f"22.gate_{name}_inserted",
                      info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
            else:
                check(f"22.gate_{name}_byte_identical",
                      out == BASE_MD and "![" not in out, str(info))


# --- 25. export ride-along behavior is unchanged --------------------------------------------
def test_export_ride_along_unchanged() -> None:
    if not _HAVE_PIL:
        skip("export.ride_along", "Pillow unavailable")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="dense_wrapped"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        job.clean_md.write_text(out, encoding="utf-8")
        refs = vmi.find_exportable_visual_pilot_assets(job)
        record(out); record(json.dumps({"refs": refs}, default=str))
        # Refs are safe job-local ``assets/<slug>.png`` only, capped at the hard max of 2.
        check("25.refs_safe",
              all(vmi.validate_visual_asset_ref(r) == r for r in refs) and len(refs) <= 2,
              str(refs))
        check("25.refs_match_inserted",
              set(refs) == {"assets/tbl.png", "assets/dia.png"}, str(refs))


# --- 26. the sanitized selection trace reflects the improved classification, stays bounded ---
def test_selection_trace_reflects_classification() -> None:
    if not _HAVE_PIL:
        skip("trace.reflects_classification", "Pillow unavailable")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("tbl", page=4, kind="dense_wrapped"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        trace_path = job.dir / vmi.SELECTION_TRACE_FILENAME
        check("26.trace_written", trace_path.is_file(), str(trace_path))
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        record(json.dumps(trace, default=str))
        summary = trace.get("candidate_summary", {})
        type_counts = summary.get("type_counts", {})
        # Improved classification: the dense wrapped table is now typed as a table, so the buckets
        # split (a diagram AND a reconstructable table are seen) — the Slice 71 failure mode.
        check("26.type_counts_split",
              type_counts.get(vmi.VISUAL_TYPE_DIAGRAM, 0) >= 1
              and type_counts.get(vmi.VISUAL_TYPE_TABLE, 0) >= 1, str(type_counts))
        selected = trace.get("selected_candidates", [])
        sel_types = [c.get("visual_type") for c in selected]
        check("26.diagram_selected_first",
              sel_types[:1] == [vmi.VISUAL_TYPE_DIAGRAM], str(sel_types))
        check("26.table_present_second",
              vmi.VISUAL_TYPE_TABLE in sel_types, str(sel_types))
        check("26.diagram_first_reason",
              any(c.get("selection_reason") == vmi.TRACE_SELECTED_DIAGRAM_FIRST
                  for c in selected), str([c.get("selection_reason") for c in selected]))
        # The trace stays bounded + closed-vocab: classification tokens only, no path/text.
        for c in selected:
            check("26.classification_token_closed",
                  c.get("classification") in vmi._VT_TO_CLASSIFIED.values(),
                  str(c.get("classification")))


# --- final. no-leak sweep over everything recorded ------------------------------------------
def test_no_leak_sweep() -> None:
    leaks = []
    for blob in _OUTPUTS:
        found = _sweep_one(blob)
        if found is not None:
            leaks.append(found)
    check("sweep.no_leaks", not leaks, ",".join(sorted(set(leaks))))
    check("sweep.had_outputs", len(_OUTPUTS) > 0, str(len(_OUTPUTS)))


def main() -> int:
    test_dense_wrapped_tables_classify_as_table()
    test_new_path_fires_when_band_guard_cannot()
    test_existing_tables_still_table()
    test_diagrams_stay_diagram()
    test_dense_wrapped_helper_units()
    test_diagram_beats_dense_wrapped_cap1()
    test_diagram_then_dense_wrapped_cap2()
    test_two_diagrams_beat_dense_wrapped_cap2()
    test_only_dense_wrapped_still_selected()
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
