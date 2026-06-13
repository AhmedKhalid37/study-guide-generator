#!/usr/bin/env python3
"""Slice 66 — focused tests for lightly-ruled / text-heavy table detection.

Slice 65's real operator validation showed the Slice 64 visual-type classifier only caught a
*strong* full horizontal+vertical rule grid as a table; the real sample's lightly ruled /
text-heavy tables stayed ``unknown`` (their faint rules and antialiased text never reached the
strict near-black ink threshold), so every candidate stayed in one type tier and diagram-first
ranking never engaged — two useful but reconstructable tables were selected. Slice 66 improves
the deterministic classifier with a softer-ink text-band rhythm + column-gutter structure so a
table with weak/no drawn rules is recognized as ``reconstructable_table``, while a genuine
diagram (no regular row/column rhythm) stays ``diagram_or_figure``.

This suite exercises:

  * strong-grid, lightly-ruled, and text-band (weak/no vertical rule) tables all classify as
    ``reconstructable_table``; a diagram-like crop classifies as ``diagram_or_figure``,
  * diagram beats a lightly ruled table at cap 1; at cap 2 one diagram + one light table selects
    both with the diagram first; two diagrams + a light table selects the two diagrams; only
    light tables are still selected when no diagram exists,
  * decorative / low-information crops are still rejected, unknown type preserves the prior
    quality-only selection, analysis failure degrades to ``unknown`` and never fails the job,
  * unsafe refs / Chandra / Mistral / page_visual_signal are never analyzed or selected,
  * determinism (no OCR / model / cloud), the two-key gate, default-off byte-identical output,
    default cap 1, hard cap 2, and unchanged export ride-along are all preserved,
  * a full no-leak sweep over markdown, info dicts, and serialized diagnostics.

Data discipline (no-leak): every PNG is a tiny runtime-built image under a temp dir — never
committed, never base64/data-URI in an assertion. The classifier reads only bounded
non-sensitive pixel summaries; it never OCRs, calls a model/provider/network, serializes or
logs image bytes, or records a path or source text. A final sweep scans every returned
diagnostic / serialized string.

Pixel-type cases SKIP automatically when Pillow is unavailable (the classifier then degrades
to ``unknown``, which this suite also asserts). Run:

    python test_scripts/test_visual_pilot_light_table_detection.py
    GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2 python test_scripts/test_visual_pilot_light_table_detection.py
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


def _draw_png(kind: str, path: Path, size=(140, 140)) -> None:
    """Draw a tiny PNG of a given visual KIND with Pillow (caller guards _HAVE_PIL).

    The table kinds use *gray* (mid-tone) text blocks and, for the light table, *thin*
    full-width rules — deliberately weaker than the strong-grid case — so they exercise the
    Slice 66 softer-ink band/gutter detection rather than the strong horizontal+vertical grid.
    """
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    w, h = size
    cols = [(12, 40), (56, 84), (100, 128)]   # three column blocks, white gutters between
    if kind == "strong_table":
        # Strong full grid (near-black rules both ways) — the Slice 64 grid path.
        for x in range(0, w + 1, 20):
            d.line([(x, 0), (x, h)], fill=0, width=2)
        for y in range(0, h + 1, 20):
            d.line([(0, y), (w, y)], fill=0, width=2)
    elif kind == "light_table":
        # Lightly ruled: gray text in columns + a few THIN full-width horizontal rules,
        # NO vertical rules (the classic lightly-ruled table the strong grid misses).
        for ry in (16, 40, 64, 88, 112):
            for (x0, x1) in cols:
                d.rectangle([x0, ry, x1, ry + 9], fill=120)
        for ly in (10, 34, 58, 82, 106, 130):
            d.line([(0, ly), (w, ly)], fill=0, width=1)
    elif kind == "text_band_table":
        # Text-heavy table with NO drawn rules at all: regular gray text rows in columns,
        # separated by white gutters (rows + columns from whitespace rhythm only).
        for ry in (14, 38, 62, 86, 110):
            for (x0, x1) in cols:
                d.rectangle([x0, ry, x1, ry + 10], fill=120)
    elif kind == "diagram":
        d.ellipse([10, 10, 52, 52], outline=0, width=3)
        d.rectangle([70, 18, 104, 58], outline=0, width=3)
        d.line([52, 30, 70, 36], fill=0, width=3)        # connector
        d.line([20, 62, 92, 104], fill=0, width=3)       # diagonal
        d.ellipse([60, 74, 100, 112], outline=0, width=3)
        d.line([30, 50, 36, 96], fill=0, width=3)
        d.rectangle([12, 86, 34, 110], fill=0)           # solid block (lowers blank)
    elif kind == "decorative":
        d.rectangle([4, 4, 12, 12], fill=0)              # tiny corner mark only
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
    """Build a FakeJob; write a PNG of each asset's KIND so the file gate + classifier work.

    ``corrupt_for`` (a set of asset ids) writes invalid PNG bytes instead, to exercise the
    analysis-failure degrade path. Unsafe refs are never written.
    """
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
        drawn = {"strong_table", "light_table", "text_band_table", "diagram", "decorative"}
        if kind in drawn and _HAVE_PIL:
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


# --- 1, 2, 3, 4, 9. classifier units: light tables -> table; diagram -> diagram ----------
def test_classifier_units() -> None:
    if not _HAVE_PIL:
        skip("classify.units", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        cases = (
            ("strong_table", vmi.VISUAL_TYPE_TABLE),       # (1) strong grid still a table
            ("light_table", vmi.VISUAL_TYPE_TABLE),        # (2) lightly ruled -> table
            ("text_band_table", vmi.VISUAL_TYPE_TABLE),    # (3) text bands, no v-rules -> table
            ("diagram", vmi.VISUAL_TYPE_DIAGRAM),          # (4) diagram-like -> diagram
            ("decorative", vmi.VISUAL_TYPE_DECORATIVE),    # (9) decorative low-info -> rejected
        )
        for kind, expected in cases:
            _draw_png(kind, td / "assets" / f"{kind}.png")
            got = cls(job, {"asset_ref": f"assets/{kind}.png"})
            check(f"classify.{kind}", got == expected, f"{got}")
            check(f"classify.{kind}_closed_vocab", got in vmi.VISUAL_TYPES, str(got))
        # Solid mid-gray (no edges, not blank) and too-small crops -> unknown (unchanged).
        (td / "assets" / "solid.png").write_bytes(_solid_png())
        check("classify.solid_unknown",
              cls(job, {"asset_ref": "assets/solid.png"}) == vmi.VISUAL_TYPE_UNKNOWN)
        (td / "assets" / "tiny.png").write_bytes(_solid_png(10, 10))
        check("classify.tiny_unknown",
              cls(job, {"asset_ref": "assets/tiny.png"}) == vmi.VISUAL_TYPE_UNKNOWN)
        record(json.dumps({"types": [cls(job, {"asset_ref": f"assets/{k}.png"})
                                     for k, _ in cases]}))


# --- pure feature helpers (no image needed) ----------------------------------------------
def test_feature_helpers() -> None:
    # Regular evenly-spaced runs -> regular; irregular -> not.
    regular = [(10, 14), (30, 34), (50, 54), (70, 74)]
    irregular = [(10, 14), (12, 40), (90, 95)]
    check("helper.regular_runs", vmi._runs_regular(regular) == 1.0)
    check("helper.irregular_runs", vmi._runs_regular(irregular) == 0.0)
    check("helper.too_few_runs", vmi._runs_regular([(10, 14), (30, 34)]) == 0.0)
    # Column blocks: gutter-separated content runs.
    col = [0.0, 0.0, 0.4, 0.4, 0.0, 0.0, 0.5, 0.5, 0.0, 0.6, 0.6, 0.0]
    check("helper.three_blocks", vmi._count_col_blocks(col, vmi._LT_COL_GUTTER_MAX) == 3)
    check("helper.one_block",
          vmi._count_col_blocks([0.3, 0.3, 0.3, 0.3], vmi._LT_COL_GUTTER_MAX) == 1)
    check("helper.no_blocks", vmi._count_col_blocks([0.0, 0.0, 0.0], vmi._LT_COL_GUTTER_MAX) == 0)
    # Profile runs: ambiguous values keep an open run open but never start one.
    runs = vmi._profile_runs([0.0, 0.2, 0.2, 0.0, 0.2, 0.0], 0.05, 0.01)
    check("helper.profile_runs", runs == [(1, 3), (4, 5)], str(runs))


# --- 5. diagram beats a lightly ruled table at cap 1 -------------------------------------
def test_diagram_beats_light_table_cap1() -> None:
    if not _HAVE_PIL:
        skip("cap1.diagram_beats_light_table", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        # Light table first in priority order, but the diagram must still win on visual type.
        job = _make_job(Path(d), [content_figure("ltbl", page=4, kind="light_table"),
                                  content_figure("dia", page=6, kind="diagram")])
        cands = sel(job)  # default cap 1
        check("cap1.diagram_selected", _ids(cands) == ["dia"],
              str(_ids(cands)) + " " + str(_types(cands)))
        check("cap1.type_is_diagram",
              _types(cands) == [vmi.VISUAL_TYPE_DIAGRAM], str(_types(cands)))


# --- 6. cap 2: one diagram + one light table -> both, diagram first ----------------------
def test_diagram_then_light_table_cap2() -> None:
    if not _HAVE_PIL:
        skip("cap2.diagram_then_light_table", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("ltbl", page=4, kind="light_table"),
                                  content_figure("dia", page=8, kind="diagram")])
        cands = sel(job, max_images=2)
        check("cap2.both_selected", set(_ids(cands)) == {"ltbl", "dia"}, str(_ids(cands)))
        check("cap2.diagram_first", _ids(cands)[0] == "dia", str(_ids(cands)))
        check("cap2.light_table_allowed_second",
              _ids(cands)[1] == "ltbl" and _types(cands)[1] == vmi.VISUAL_TYPE_TABLE,
              str(_types(cands)))


# --- 7. cap 2: two diagrams + a light table -> the two diagrams --------------------------
def test_two_diagrams_beat_light_table_cap2() -> None:
    if not _HAVE_PIL:
        skip("cap2.two_diagrams", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("ltbl", page=3, kind="light_table"),
                                  content_figure("d1", page=5, kind="diagram"),
                                  content_figure("d2", page=7, kind="diagram")])
        cands = sel(job, max_images=2)
        check("cap2.two_diagrams_selected", set(_ids(cands)) == {"d1", "d2"}, str(_ids(cands)))
        check("cap2.no_table_when_diagrams", "ltbl" not in _ids(cands), str(_ids(cands)))
        check("cap2.both_diagram_type",
              _types(cands) == [vmi.VISUAL_TYPE_DIAGRAM, vmi.VISUAL_TYPE_DIAGRAM],
              str(_types(cands)))


# --- 8. only light tables -> still selected ----------------------------------------------
def test_only_light_tables_still_selected() -> None:
    if not _HAVE_PIL:
        skip("tables.only_light_selected", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("t1", page=4, kind="light_table"),
                                  content_figure("t2", page=6, kind="text_band_table")])
        c1 = sel(job)  # cap 1
        check("tables.cap1_selects_table",
              len(c1) == 1 and _types(c1) == [vmi.VISUAL_TYPE_TABLE], str(_types(c1)))
        c2 = sel(job, max_images=2)  # cap 2
        check("tables.cap2_selects_two_tables",
              set(_ids(c2)) == {"t1", "t2"}
              and _types(c2) == [vmi.VISUAL_TYPE_TABLE, vmi.VISUAL_TYPE_TABLE],
              str(_ids(c2)) + " " + str(_types(c2)))


# --- 9. decorative is not preferred just to avoid a table --------------------------------
def test_decorative_not_preferred_over_table() -> None:
    if not _HAVE_PIL:
        skip("decor.not_over_table", "Pillow unavailable")
        return
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("decor", page=4, kind="decorative"),
                                  content_figure("ltbl", page=6, kind="light_table")])
        c1 = sel(job)
        check("decor.light_table_beats_decorative",
              _ids(c1) == ["ltbl"] and _types(c1) == [vmi.VISUAL_TYPE_TABLE], str(_types(c1)))
    # When the only accepted candidate is pixel-decorative, it is still inserted (the
    # metadata gate already cleared it; we never over-reject to "solve" CV).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("lone", page=5, kind="decorative")])
        check("decor.lone_still_selected", _ids(sel(job)) == ["lone"], str(_ids(sel(job))))


# --- 10 & 16. unknown type preserves prior quality-only behavior -------------------------
def test_unknown_preserves_prior_behavior() -> None:
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5, kind="solid"),
                                  content_figure("c2", page=8, kind="solid")])
        c1 = sel(job)
        check("unknown.default_one", _ids(c1) == ["c1"], str(_ids(c1)))
        check("unknown.type_unknown", _types(c1) == [vmi.VISUAL_TYPE_UNKNOWN], str(_types(c1)))
        c2 = sel(job, max_images=2)
        check("unknown.cap2_two_distinct_pages",
              set(_ids(c2)) == {"c1", "c2"} and c2[0]["asset_id"] == "c1", str(_ids(c2)))


# --- 11. analysis failure degrades to unknown and never fails the job --------------------
def test_analysis_failure_degrades() -> None:
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("corrupt", page=5, kind="solid")],
                        corrupt_for={"corrupt"})
        got = cls(job, {"asset_ref": "assets/corrupt.png"})
        check("fail.corrupt_unknown", got == vmi.VISUAL_TYPE_UNKNOWN, str(got))
        out, info = _with_env({vmi.ENABLE_ENV: "1"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out); record(json.dumps(info, default=str))
        check("fail.pilot_still_inserts",
              info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
        check("fail.info_type_unknown_or_none",
              info.get("visual_type") in (vmi.VISUAL_TYPE_UNKNOWN, None),
              str(info.get("visual_type")))


# --- 12. unsafe refs are never analyzed --------------------------------------------------
def test_unsafe_refs_never_analyzed() -> None:
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        job = FakeJob(dir=Path(d))
        for ref in ("/etc/passwd.png", "assets/../secret.png", "assets\\fig.png",
                    "https://example.com/a.png", "data:image/png;base64,AAAA.png",
                    "assets/fig.jpg", "assets/sub/fig.png", None, 123):
            got = cls(job, {"asset_ref": ref})
            check(f"unsafe.classify_unknown[{ref!r}]", got == vmi.VISUAL_TYPE_UNKNOWN, str(got))
    if _HAVE_PIL:
        with tempfile.TemporaryDirectory() as d:
            bad = content_figure("bad", page=4, kind="light_table", image_ref="/etc/passwd.png")
            good = content_figure("safe", page=6, kind="light_table")
            job = _make_job(Path(d), [bad, good])
            check("unsafe.only_safe_selected", _ids(sel(job, max_images=2)) == ["safe"],
                  str(_ids(sel(job, max_images=2))))


# --- 13. chandra / mistral / page_visual_signal are never analyzed or selected -----------
def test_blocked_providers_excluded() -> None:
    sel = vmi.select_visual_markdown_candidates
    with tempfile.TemporaryDirectory() as d:
        chandra = content_figure("chandra", page=4, kind="light_table")
        chandra["source_provider"] = "chandra_local"
        mistral = content_figure("mistral", page=4, kind="light_table")
        mistral["source_provider"] = "mistral_ocr"
        signal = content_figure("signal", page=4, kind="light_table")
        signal["asset_type"] = "page_visual_signal"
        blocked = content_figure("blocked", page=4, kind="light_table")
        blocked["reasons"] = ["chandra_blocked"]
        good = content_figure("fitz", page=5, kind="solid")
        job = _make_job(Path(d), [chandra, mistral, signal, blocked, good])
        check("blocked.only_fitz_selected", _ids(sel(job, max_images=2)) == ["fitz"],
              str(_ids(sel(job, max_images=2))))


# --- 14 & 15. determinism (no model/cloud), closed-vocab info, and no leaks --------------
def test_determinism_and_diagnostics() -> None:
    if not _HAVE_PIL:
        skip("info.diagnostics", "Pillow unavailable")
        return
    cls = vmi.classify_visual_markdown_candidate_type_for_pilot
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        (td / "assets").mkdir()
        job = FakeJob(dir=td)
        _draw_png("light_table", td / "assets" / "lt.png")
        # Deterministic across repeated calls (pure pixel arithmetic; no model/network).
        results = {cls(job, {"asset_ref": "assets/lt.png"}) for _ in range(5)}
        check("determinism.stable", results == {vmi.VISUAL_TYPE_TABLE}, str(results))
        # Returned features are bounded numeric summaries only — no text / bytes / path.
        feats = vmi._visual_type_features(job, "assets/lt.png")
        check("features.all_numeric",
              isinstance(feats, dict) and all(isinstance(v, float) for v in feats.values()),
              str(feats))
        record(json.dumps(feats, default=str))

    # The success info carries only a safe closed-vocab visual_type token (cap 2).
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("ltbl", page=4, kind="light_table"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out); record(json.dumps(info, default=str))
        check("info.visual_type_closed_vocab",
              info.get("visual_type") in vmi.VISUAL_TYPES, str(info.get("visual_type")))
        check("info.first_is_diagram", info.get("visual_type") == vmi.VISUAL_TYPE_DIAGRAM, str(info))
        assets = info.get("inserted_assets") or []
        check("info.diagram_before_table",
              [a.get("visual_type") for a in assets]
              == [vmi.VISUAL_TYPE_DIAGRAM, vmi.VISUAL_TYPE_TABLE],
              str([a.get("visual_type") for a in assets]))


# --- 17, 18, 19. gate / default-off / cap invariants (unchanged) -------------------------
def test_gate_and_cap_invariants() -> None:
    sel = vmi.select_visual_markdown_candidates
    kind = "light_table" if _HAVE_PIL else "solid"

    # (18) default cap remains exactly 1 even with two great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind),
                                  content_figure("b", page=8, kind=kind)])
        check("cap.default_one", len(sel(job)) == 1, str(len(sel(job))))

    # (19) cap is hard-bounded at 2 — an over-large request never widens it.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind),
                                  content_figure("b", page=7, kind=kind),
                                  content_figure("c", page=9, kind=kind)])
        check("cap.hard_max_2", len(sel(job, max_images=99)) == 2, str(len(sel(job, max_images=99))))
        check("cap.env_hard_max_2",
              _with_env({vmi.MAX_IMAGES_ENV: "99"}, vmi.visual_markdown_pilot_max_images) == 1)

    # (16) default-OFF (env unset) -> byte-identical, even with great candidates.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("a", page=5, kind=kind)])
        out, info = _with_env({vmi.ENABLE_ENV: None},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("gate.default_off_byte_identical", out == BASE_MD, repr(out[:60]))
        check("gate.default_off_reason", info.get("reason") == vmi.SKIP_DISABLED, str(info))

    # (17) two-key gate unchanged: only (env on, opt-in on) inserts, even at cap 2.
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
                check(f"gate.{name}.inserted",
                      info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
            else:
                check(f"gate.{name}.byte_identical", out == BASE_MD and "![" not in out, str(info))


# --- 20. export ride-along behavior is unchanged -----------------------------------------
def test_export_ride_along_unchanged() -> None:
    if not _HAVE_PIL:
        skip("export.ride_along", "Pillow unavailable")
        return
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("ltbl", page=4, kind="light_table"),
                                  content_figure("dia", page=8, kind="diagram")])
        out, info = _with_env({vmi.ENABLE_ENV: "1", vmi.MAX_IMAGES_ENV: "2"},
                              lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        job.clean_md.write_text(out, encoding="utf-8")
        refs = vmi.find_exportable_visual_pilot_assets(job)
        record(out); record(json.dumps({"refs": refs}, default=str))
        # Refs are safe job-local ``assets/<slug>.png`` only, capped at the hard max of 2.
        check("export.refs_safe",
              all(vmi.validate_visual_asset_ref(r) == r for r in refs) and len(refs) <= 2,
              str(refs))
        check("export.refs_match_inserted",
              set(refs) == {"assets/ltbl.png", "assets/dia.png"}, str(refs))


# --- final. no-leak sweep over everything recorded ---------------------------------------
def test_no_leak_sweep() -> None:
    leaks = []
    for blob in _OUTPUTS:
        found = _sweep_one(blob)
        if found is not None:
            leaks.append(found)
    check("sweep.no_leaks", not leaks, ",".join(sorted(set(leaks))))
    check("sweep.had_outputs", len(_OUTPUTS) > 0, str(len(_OUTPUTS)))


def main() -> int:
    test_classifier_units()
    test_feature_helpers()
    test_diagram_beats_light_table_cap1()
    test_diagram_then_light_table_cap2()
    test_two_diagrams_beat_light_table_cap2()
    test_only_light_tables_still_selected()
    test_decorative_not_preferred_over_table()
    test_unknown_preserves_prior_behavior()
    test_analysis_failure_degrades()
    test_unsafe_refs_never_analyzed()
    test_blocked_providers_excluded()
    test_determinism_and_diagnostics()
    test_gate_and_cap_invariants()
    test_export_ride_along_unchanged()
    test_no_leak_sweep()
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
