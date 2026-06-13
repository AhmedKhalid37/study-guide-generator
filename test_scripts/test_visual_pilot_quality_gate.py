#!/usr/bin/env python3
"""Slice 60 — focused tests for the visual pilot quality gate + PDF image visibility.

Manual operator review of the single-figure pilot found two real problems that the
earlier trace-artifact direction would not have fixed:

  * **Selection quality** — with several safe ``extracted_figure`` crops available, the
    pilot could pick a low-value chapter-title / title-page crop simply because it came
    first, instead of a content-bearing figure/table/diagram.
  * **PDF "ok" was too weak** — a non-empty rendered PDF was reported as ``pdf_render_ok``
    even when the image was a broken/missing marker (only alt text), not a visible
    embedded image.

This test exercises the conservative deterministic quality gate added to
``pipeline.visual_markdown_insertion`` (rank safe candidates by already-available
metadata only; prefer content figures; drop decorative title/header/footer/logo/banner
crops; degrade-never-fail and never over-reject on sparse metadata) and the strengthened
PDF image-visibility check (embedded image object, not just a non-empty file).

Data discipline (no-leak): every PNG is a tiny runtime-built byte literal under a temp
dir — never committed, never base64/data-URI in an assertion. The gate reads only
sanitized manifest metadata (source page, bbox, page/crop dimensions); no private text,
OCR text, caption, image bytes, host path, token, or provider payload is read or emitted.
A final sweep scans every returned diagnostic string.

Run:

    python test_scripts/test_visual_pilot_quality_gate.py
    GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1 python test_scripts/test_visual_pilot_quality_gate.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# test_scripts is not a package; add it to the path so the operator harness's
# reusable PDF-embed helper can be imported without duplicating it here.
sys.path.insert(0, os.path.dirname(__file__))

from pipeline import visual_markdown_insertion as vmi  # noqa: E402

PASS = 0
FAIL = 0
SKIP = 0

# Forbidden value shapes — none may appear in any returned diagnostic.
KEYLIKE = re.compile(r"(sk-|sk_|pk-|rk_)[A-Za-z0-9_\-]{12,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/root/|/tmp/|/opt/|C:\\|\\\\)")
URLLIKE = re.compile(r"https?://|file://|ftp://")
AUTHLIKE = re.compile(r"Authorization|Bearer\s+\S", re.IGNORECASE)
SOCKETLIKE = re.compile(r"\.sock\b")
DATAURI = re.compile(r"data:[^;]+;base64,", re.IGNORECASE)
GGUFLIKE = re.compile(r"\.gguf\b|mmproj|llama-server", re.IGNORECASE)
_LEAK_PATTERNS = (
    ("key", KEYLIKE), ("path", PATHLIKE), ("url", URLLIKE), ("auth", AUTHLIKE),
    ("socket", SOCKETLIKE), ("datauri", DATAURI), ("gguf", GGUFLIKE),
)
_OUTPUTS: list[str] = []

# Page geometry used across the geometry cases (A4-ish, in PDF points).
PW, PH = 612.0, 792.0

# A minimal valid 1x1 PNG; only present so the on-disk file gate finds a real file.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _figure_png(width: int = 96, height: int = 96) -> bytes:
    """A figure-sized grayscale PNG built at runtime (stdlib only; never committed).

    Large enough that the strengthened PDF visibility check counts it as a real image
    rather than the tiny broken-image placeholder icon. Bytes are never asserted on.
    """
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    idat = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")

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
        "signals": {
            "page_width": pw, "page_height": ph,
            "crop_width_px": cw, "crop_height_px": ch,
        },
        "warnings": [],
    }


# Named geometry presets used by several cases.
def content_figure(asset_id="content_fig", page=5) -> dict:
    return _figure(asset_id, page=page, bbox=[100, 200, 500, 600], pw=PW, ph=PH, cw=800, ch=800)


def title_full(asset_id="title_full") -> dict:
    return _figure(asset_id, page=1, bbox=[0, 0, 612, 792], pw=PW, ph=PH, cw=1200, ch=1500)


def header_banner(asset_id="header_banner") -> dict:
    return _figure(asset_id, page=3, bbox=[20, 10, 590, 60], pw=PW, ph=PH, cw=1100, ch=90)


def footer_banner(asset_id="footer_banner") -> dict:
    return _figure(asset_id, page=3, bbox=[20, 740, 590, 785], pw=PW, ph=PH, cw=1100, ch=80)


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
              write_png_for=None) -> FakeJob:
    """Build a FakeJob; write a real PNG for each asset's safe ref so the file gate passes.

    ``write_png_for`` may restrict which asset ids get a real PNG (default: all that have
    a safe ``assets/<slug>.png`` ref). Unsafe refs are never written.
    """
    job = FakeJob(dir=tmp, opt_in=opt_in)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        aid = asset.get("asset_id")
        if write_png_for is not None and aid not in write_png_for:
            continue
        ref = asset.get("image_ref")
        if isinstance(ref, str) and re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", ref):
            (job.dir / ref).write_bytes(_PNG_1x1)
    job.visual_assets_manifest_json.write_text(
        json.dumps(_manifest(assets)) + "\n", encoding="utf-8")
    if plan_ids is not None:
        job.visual_replacement_plan_json.write_text(
            json.dumps(_plan(plan_ids)) + "\n", encoding="utf-8")
    return job


def _select(job: FakeJob):
    """Flag-independent selection (drives the gate without env/PNG gymnastics)."""
    cand = vmi.select_visual_markdown_candidate(job)
    if cand is not None:
        record(json.dumps(cand, default=str))
    return cand


def _with_env(value, fn):
    old = os.environ.get(vmi.ENABLE_ENV)
    if value is None:
        os.environ.pop(vmi.ENABLE_ENV, None)
    else:
        os.environ[vmi.ENABLE_ENV] = value
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop(vmi.ENABLE_ENV, None)
        else:
            os.environ[vmi.ENABLE_ENV] = old


# --- 0. pure scorer / rank unit checks ------------------------------------------------
def test_scorer_units() -> None:
    s = vmi.score_visual_markdown_candidate_for_pilot
    check("scorer.content_not_decorative", s(content_figure())["decorative"] is False)
    check("scorer.title_full_decorative", s(title_full())["decorative"] is True)
    check("scorer.header_decorative", s(header_banner())["decorative"] is True)
    check("scorer.footer_decorative", s(footer_banner())["decorative"] is True)
    check("scorer.tiny_decorative", s(tiny_logo())["decorative"] is True)
    check("scorer.content_beats_title",
          s(content_figure())["score"] > s(title_full())["score"])

    # Metadata-sparse must NOT be over-rejected (the synthetic fixture shape).
    sparse = _figure("sparse", page=3, bbox=[0.0, 0.0, 10.0, 10.0])
    qs = s(sparse)
    check("scorer.sparse_not_decorative", qs["decorative"] is False, str(qs))
    check("scorer.sparse_reason", "quality_metadata_sparse" in qs["reasons"], str(qs))

    # A wide content table in the MIDDLE of the page is penalized but not hard-dropped.
    mid_wide = _figure("mid_wide", page=4, bbox=[20, 350, 590, 410], pw=PW, ph=PH, cw=1100, ch=120)
    check("scorer.mid_banner_not_decorative",
          s(mid_wide)["decorative"] is False, str(s(mid_wide)))

    # All closed-vocab reasons.
    for asset in (content_figure(), title_full(), header_banner(), tiny_logo()):
        q = s(asset)
        check("scorer.reasons_closed_vocab",
              all(r in vmi.QUALITY_REASONS for r in q["reasons"]), str(q["reasons"]))

    # rank: title+content -> content (index 1); only junk -> None.
    check("rank.title_then_content",
          vmi.rank_visual_markdown_candidates([title_full(), content_figure()]) == 1)
    check("rank.only_junk_none",
          vmi.rank_visual_markdown_candidates([title_full(), tiny_logo(), header_banner()]) is None)
    check("rank.empty_none", vmi.rank_visual_markdown_candidates([]) is None)
    check("rank.invalid_none", vmi.rank_visual_markdown_candidates("nope") is None)
    # Two equal content figures -> priority order preserved (index 0).
    check("rank.tie_prefers_priority",
          vmi.rank_visual_markdown_candidates([content_figure("a", page=5),
                                               content_figure("b", page=7)]) == 0)
    check("is_decorative.helper", vmi.is_decorative_visual_candidate(tiny_logo()) is True
          and vmi.is_decorative_visual_candidate(content_figure()) is False)


# --- 1–4. better content figure wins over decorative crops ----------------------------
def _case_content_wins(name: str, junk: dict) -> None:
    with tempfile.TemporaryDirectory() as d:
        good = content_figure("good_content", page=6)
        assets = [junk, good]  # junk first in manifest/priority order
        job = _make_job(Path(d), assets)
        cand = _select(job)
        check(f"{name}.selected_content",
              cand is not None and cand["asset_id"] == "good_content", str(cand))


def test_content_beats_decorative() -> None:
    _case_content_wins("title_vs_content", title_full())       # (1)
    _case_content_wins("banner_vs_content", header_banner())   # (2)
    _case_content_wins("tiny_vs_content", tiny_logo())         # (3)
    _case_content_wins("footer_vs_content", footer_banner())   # (4)


# --- 5 & 6. a single content figure still inserts -------------------------------------
def test_single_content_inserts() -> None:
    # (5) later-page content figure, no plan -> selected.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("only_fig", page=6)])
        cand = _select(job)
        check("single.later_page_selected",
              cand is not None and cand["asset_id"] == "only_fig", str(cand))
        check("single.quality_reasons_present",
              cand is not None and isinstance(cand.get("quality_reasons"), list))

    # (6) one content-sized candidate with a plan entry -> still inserts.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("planned_fig", page=4)],
                        plan_ids=["planned_fig"])
        cand = _select(job)
        check("single.planned_content_inserts",
              cand is not None and cand["asset_id"] == "planned_fig", str(cand))


# --- 7. only decorative/junk -> degrade safely (no insertion) -------------------------
def test_only_junk_omits() -> None:
    with tempfile.TemporaryDirectory() as d:
        assets = [title_full("t"), tiny_logo("l"), header_banner("h")]
        job = _make_job(Path(d), assets)
        cand = _select(job)
        check("junk.select_none", cand is None, str(cand))

        # Through the real entry point (flag + opt-in on): byte-identical, low-quality.
        out, info = _with_env("1", lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out)
        record(json.dumps(info, default=str))
        check("junk.byte_identical", out == BASE_MD, repr(out[:60]))
        check("junk.no_image", "![" not in out)
        check("junk.reason_low_quality",
              info.get("reason") == vmi.SKIP_CANDIDATE_LOW_QUALITY, str(info))


# --- 8. unsafe asset refs never enter selection ---------------------------------------
def test_unsafe_refs_excluded() -> None:
    # A good content figure alongside one with an unsafe ref -> good selected.
    with tempfile.TemporaryDirectory() as d:
        bad = content_figure("bad_ref", page=4)
        bad["image_ref"] = "../../../etc/passwd.png"
        good = content_figure("safe_fig", page=5)
        job = _make_job(Path(d), [bad, good])
        cand = _select(job)
        check("unsafe.good_selected",
              cand is not None and cand["asset_id"] == "safe_fig", str(cand))

    # Only-unsafe -> nothing selected (unsafe, not a quality-gate decision).
    with tempfile.TemporaryDirectory() as d:
        bad = content_figure("only_bad", page=4)
        bad["image_ref"] = "/etc/passwd.png"
        job = _make_job(Path(d), [bad])
        cand = _select(job)
        check("unsafe.only_bad_none", cand is None, str(cand))


# --- 9. chandra / mistral / page_visual_signal never selected -------------------------
def test_blocked_providers_excluded() -> None:
    with tempfile.TemporaryDirectory() as d:
        chandra = content_figure("chandra_fig", page=4)
        chandra["source_provider"] = "chandra_local"
        mistral = content_figure("mistral_fig", page=4)
        mistral["source_provider"] = "mistral_ocr"
        signal = content_figure("signal_fig", page=4)
        signal["asset_type"] = "page_visual_signal"
        good = content_figure("fitz_fig", page=5)
        job = _make_job(Path(d), [chandra, mistral, signal, good])
        cand = _select(job)
        check("blocked.fitz_selected",
              cand is not None and cand["asset_id"] == "fitz_fig", str(cand))

    # chandra_blocked marker on an otherwise-fitz asset is still excluded.
    with tempfile.TemporaryDirectory() as d:
        blocked = content_figure("blocked_fig", page=4)
        blocked["reasons"] = ["chandra_blocked"]
        job = _make_job(Path(d), [blocked])
        cand = _select(job)
        check("blocked.chandra_blocked_none", cand is None, str(cand))


# --- 10 & 11 & 12. one-figure rule, default-off, gate truth-table ---------------------
def test_pilot_invariants() -> None:
    # (10) Several good candidates through the real pilot -> exactly one image.
    with tempfile.TemporaryDirectory() as d:
        assets = [content_figure("c1", page=4), content_figure("c2", page=5),
                  content_figure("c3", page=6)]
        job = _make_job(Path(d), assets)
        out, info = _with_env("1", lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        record(out)
        check("invariant.exactly_one_image", out.count("![") == 1, str(out.count("![")))
        check("invariant.status_inserted", info.get("status") == vmi.STATUS_INSERTED, str(info))

    # (11) Default-off (env unset) -> byte-identical, even with great candidates present.
    with tempfile.TemporaryDirectory() as d:
        job = _make_job(Path(d), [content_figure("c1", page=5)])
        out, info = _with_env(None, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
        check("invariant.default_off_byte_identical", out == BASE_MD, repr(out[:60]))
        check("invariant.default_off_reason", info.get("reason") == vmi.SKIP_DISABLED, str(info))

    # (12) Two-key gate unchanged: only (env on, opt-in on) may insert.
    for name, env, opt_in, may_insert in (
        ("off_off", None, False, False),
        ("off_on", None, True, False),
        ("on_off", "1", False, False),
        ("on_on", "1", True, True),
    ):
        with tempfile.TemporaryDirectory() as d:
            job = _make_job(Path(d), [content_figure("c1", page=5)], opt_in=opt_in)
            out, info = _with_env(env, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))
            if may_insert:
                check(f"gate.{name}.inserted",
                      info.get("status") == vmi.STATUS_INSERTED and "![" in out, str(info))
            else:
                check(f"gate.{name}.byte_identical", out == BASE_MD and "![" not in out, str(info))


# --- 13. the gate mutates nothing -----------------------------------------------------
def test_no_mutation() -> None:
    with tempfile.TemporaryDirectory() as d:
        assets = [title_full("t"), content_figure("good", page=5)]
        job = _make_job(Path(d), assets, plan_ids=["good"])
        man_before = job.visual_assets_manifest_json.read_text(encoding="utf-8")
        plan_before = job.visual_replacement_plan_json.read_text(encoding="utf-8")
        png_before = (job.dir / "assets" / "good.png").read_bytes()
        in_memory_assets = json.loads(man_before)["assets"]
        snapshot = json.dumps(in_memory_assets, sort_keys=True)

        # Score + rank + select must not touch inputs or artifacts.
        for a in in_memory_assets:
            vmi.score_visual_markdown_candidate_for_pilot(a)
        vmi.rank_visual_markdown_candidates(in_memory_assets)
        out, _info = _with_env("1", lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))

        check("nomut.assets_in_memory_unchanged",
              json.dumps(in_memory_assets, sort_keys=True) == snapshot)
        check("nomut.manifest_on_disk_unchanged",
              job.visual_assets_manifest_json.read_text(encoding="utf-8") == man_before)
        check("nomut.plan_on_disk_unchanged",
              job.visual_replacement_plan_json.read_text(encoding="utf-8") == plan_before)
        check("nomut.source_png_unchanged",
              (job.dir / "assets" / "good.png").read_bytes() == png_before)
        # The pilot returns NEW text; it never writes clean.md itself.
        check("nomut.no_clean_md_written", not (job.dir / "clean.md").exists())
        check("nomut.produced_has_image", "![" in out)


# --- 15. PDF image visibility (embedded image object, not just a non-empty file) ------
def test_pdf_image_visibility() -> None:
    try:
        from pipeline.pdf_renderer import render_pdf, _find_chromium
    except Exception as exc:
        skip("pdfvis.render", f"renderer import unavailable ({type(exc).__name__})")
        return
    if _find_chromium() is None:
        skip("pdfvis.render", "no Chromium on host")
        return
    try:
        from validate_visual_pilot_operator_sample import _pdf_embeds_image
    except Exception as exc:
        skip("pdfvis.helper", f"harness import unavailable ({type(exc).__name__})")
        return
    try:
        import fitz  # noqa: F401
    except Exception as exc:
        skip("pdfvis.fitz", f"PyMuPDF unavailable ({type(exc).__name__})")
        return

    slug = "s00_page_0003_figure_01"
    good_md = (
        "# Guide\n\nText.\n\n## Visual Reference\n\n"
        f"![Extracted figure from source page 3](assets/{slug}.png)\n"
    )
    missing_md = (
        "# Guide\n\nText.\n\n## Visual Reference\n\n"
        "![Extracted figure from source page 3](assets/does_not_exist.png)\n"
    )
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)
        (work / "assets").mkdir(parents=True, exist_ok=True)
        (work / "assets" / f"{slug}.png").write_bytes(_figure_png())

        # Positive: a resolvable relative ref embeds a real image object.
        (work / "clean.md").write_text(good_md, encoding="utf-8")
        out_pdf = work / "good.pdf"
        try:
            render_pdf(work / "clean.md", out_pdf)
        except Exception as exc:
            check("pdfvis.render_no_raise", False, type(exc).__name__)
            return
        check("pdfvis.pdf_nonempty", out_pdf.is_file() and out_pdf.stat().st_size > 0)
        check("pdfvis.embeds_image_true", _pdf_embeds_image(out_pdf) is True)

        # Negative: a broken/missing ref renders only a tiny broken-image placeholder
        # icon (~14x16) — the visibility check must NOT count that as a visible figure.
        (work / "clean.md").write_text(missing_md, encoding="utf-8")
        out_pdf2 = work / "missing.pdf"
        try:
            render_pdf(work / "clean.md", out_pdf2)
        except Exception as exc:
            skip("pdfvis.missing_render", type(exc).__name__)
        else:
            # The file still renders (non-empty) but must report NOT visible — exactly
            # the weakness this check closes (non-empty PDF != visible image).
            check("pdfvis.missing_pdf_nonempty",
                  out_pdf2.is_file() and out_pdf2.stat().st_size > 0)
            check("pdfvis.embeds_image_false_when_missing",
                  _pdf_embeds_image(out_pdf2) is False)


# --- 14. no-leak sweep over everything the gate returned ------------------------------
def test_no_leak_sweep() -> None:
    leaks: list[str] = []
    for blob in _OUTPUTS:
        found = _sweep_one(blob)
        if found is not None:
            leaks.append(found)
    check("sweep.no_leaks", not leaks, ",".join(sorted(set(leaks))))
    check("sweep.had_outputs", len(_OUTPUTS) > 0, str(len(_OUTPUTS)))


def main() -> int:
    test_scorer_units()
    test_content_beats_decorative()
    test_single_content_inserts()
    test_only_junk_omits()
    test_unsafe_refs_excluded()
    test_blocked_providers_excluded()
    test_pilot_invariants()
    test_no_mutation()
    test_pdf_image_visibility()
    test_no_leak_sweep()
    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
