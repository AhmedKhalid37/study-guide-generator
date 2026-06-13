#!/usr/bin/env python3
"""Slice 68 — focused tests for the sanitized visual-pilot selection trace.

Slice 67 reran the real post-Slice-66 cap-2 operator sample and it STILL selected two
useful-but-reconstructable tables only; no irreplaceable diagram/figure was chosen.
Before any further blind heuristic tuning, Slice 68 adds a bounded, sanitized
candidate-audit artifact (``visual_markdown_selection_trace.json``) so future real runs
can explain *why* diagrams were not selected. The trace is DIAGNOSTIC ONLY — it never
changes ranking, the cap, the default, the two-key gate, the UI, render/export behavior,
or extraction/OCR routing, and it adds no model/provider/cloud call.

This suite exercises:

  * the trace is written only when BOTH gates are on AND selection was attempted,
    and NOT written when the master switch is off or the job did not opt in,
  * the trace records the effective cap (1 by default, 2 under the env), the selected
    count, the inserted count, and the selected visual types,
  * tables-only vs diagram-selected outcomes are distinguished with safe closed tokens,
  * safe / unsafe candidate counts and closed rejection-reason counts are recorded,
  * Chandra / Mistral / page_visual_signal candidates are counted/rejected (never raw),
  * the trace is fully sanitized + bounded (no path / filename / document / OCR text /
    image bytes / base64 / data URI / provider payload / token / argv / model path),
  * trace-creation failure never fails generation, default-off output is byte-identical,
    the cap default/hard-cap are unchanged, and export does not pick up the trace file.

Data discipline (no-leak): every PNG is a tiny runtime-built fixture under a temp dir —
never committed, never base64/data-URI in an assertion. No private text, OCR text,
caption text, host path, token, provider payload, raw argv, or full URL is read or
emitted. A final sweep scans every serialized trace string.

Run:

    python test_scripts/test_visual_pilot_selection_trace_sanitized.py
    GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2 python test_scripts/test_visual_pilot_selection_trace_sanitized.py
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
    from PIL import Image, ImageDraw  # optional; pixel-type cases skip without it
    _HAVE_PIL = True
except Exception:  # pragma: no cover - environment dependent
    _HAVE_PIL = False

PASS = 0
FAIL = 0
SKIP = 0

# Forbidden value shapes — none may appear in any serialized trace output.
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

# A unique source-document-like filename that MUST never appear anywhere in the trace.
SECRET_SOURCE_NAME = "Operator_Private_Source_Document_2026.pdf"
SECRET_CAPTION = "raw private caption text that must never leak"

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


def _sweep(trace: dict) -> str | None:
    text = json.dumps(trace, sort_keys=True)
    for label, pat in _LEAK_PATTERNS:
        if pat.search(text):
            return label
    if SECRET_SOURCE_NAME in text or SECRET_CAPTION in text:
        return "secret_text"
    return None


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
    """Draw a tiny PNG of a given visual KIND with Pillow (caller guards _HAVE_PIL)."""
    img = Image.new("L", size, 255)
    d = ImageDraw.Draw(img)
    w, h = size
    cols = [(12, 40), (56, 84), (100, 128)]
    if kind == "light_table":
        for ry in (16, 40, 64, 88, 112):
            for (x0, x1) in cols:
                d.rectangle([x0, ry, x1, ry + 9], fill=120)
        for ly in (10, 34, 58, 82, 106, 130):
            d.line([(0, ly), (w, ly)], fill=0, width=1)
    elif kind == "diagram":
        d.ellipse([10, 10, 52, 52], outline=0, width=3)
        d.rectangle([70, 18, 104, 58], outline=0, width=3)
        d.line([52, 30, 70, 36], fill=0, width=3)
        d.line([20, 62, 92, 104], fill=0, width=3)
        d.ellipse([60, 74, 100, 112], outline=0, width=3)
        d.line([30, 50, 36, 96], fill=0, width=3)
        d.rectangle([12, 86, 34, 110], fill=0)
    else:  # solid / fallback
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
            atype="extracted_figure", reasons=None) -> dict:
    asset = {
        "asset_id": asset_id,
        "source_page": page,
        "asset_type": atype,
        "bbox": bbox,
        # A raw private caption is intentionally placed in the manifest to prove the
        # trace never carries it through.
        "caption": SECRET_CAPTION,
        "source_provider": provider,
        "image_ref": image_ref if image_ref is not None else f"assets/{asset_id}.png",
        "scores": {},
        "signals": {"page_width": pw, "page_height": ph,
                    "crop_width_px": cw, "crop_height_px": ch},
        "warnings": [],
    }
    if reasons is not None:
        asset["reasons"] = reasons
    asset["_kind"] = kind  # out-of-band fixture hint (stripped before persisting)
    return asset


def content_table(asset_id="tbl", page=5) -> dict:
    return _figure(asset_id, page=page, kind="light_table",
                   bbox=[100, 200, 500, 600], pw=PW, ph=PH, cw=800, ch=800)


def content_diagram(asset_id="dia", page=6) -> dict:
    return _figure(asset_id, page=page, kind="diagram",
                   bbox=[100, 200, 500, 600], pw=PW, ph=PH, cw=800, ch=800)


def _manifest(assets: list[dict]) -> dict:
    clean_assets = []
    for a in assets:
        c = {k: v for k, v in a.items() if k != "_kind"}
        clean_assets.append(c)
    return {
        "version": 1, "kind": "visual_assets_manifest", "status": "completed",
        # A source-doc-like filename in the manifest source field to prove it never leaks.
        "source": SECRET_SOURCE_NAME, "assets": clean_assets,
        "summary": {"asset_count": len(clean_assets)}, "warnings": [],
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


def _make_job(tmp: Path, assets: list[dict], *, plan_ids=None, opt_in=True) -> FakeJob:
    job = FakeJob(dir=tmp, opt_in=opt_in)
    job.assets_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        ref = asset.get("image_ref")
        kind = asset.get("_kind", "solid")
        if isinstance(ref, str) and re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", ref):
            target = job.dir / ref
            if _HAVE_PIL and kind in ("light_table", "diagram"):
                _draw_png(kind, target)
            else:
                target.write_bytes(_solid_png())
    job.visual_assets_manifest_json.write_text(
        json.dumps(_manifest(assets)) + "\n", encoding="utf-8")
    if plan_ids is not None:
        job.visual_replacement_plan_json.write_text(
            json.dumps(_plan(plan_ids)) + "\n", encoding="utf-8")
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


def _trace_path(job: FakeJob) -> Path:
    return job.dir / vmi.SELECTION_TRACE_FILENAME


def _read_trace(job: FakeJob) -> dict | None:
    p = _trace_path(job)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _run_pilot(job: FakeJob, *, enabled: bool, cap: str | None = None):
    env = {vmi.ENABLE_ENV: "1" if enabled else None, vmi.MAX_IMAGES_ENV: cap}
    return _with_env(env, lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD))


# --- Tests -------------------------------------------------------------------


def test_not_written_when_flag_off(tmp: Path) -> None:
    job = _make_job(tmp, [content_table()])
    text, info = _run_pilot(job, enabled=False)
    check("1. flag off → no trace file", not _trace_path(job).is_file())
    check("1. flag off → output byte-identical", text == BASE_MD)
    check("1. flag off → skipped/disabled", info.get("reason") == vmi.SKIP_DISABLED)


def test_not_written_when_opt_out(tmp: Path) -> None:
    job = _make_job(tmp, [content_table()], opt_in=False)
    text, info = _run_pilot(job, enabled=True)
    check("2. opt-out → no trace file", not _trace_path(job).is_file())
    check("2. opt-out → output byte-identical", text == BASE_MD)
    check("2. opt-out → skipped/opt-out", info.get("reason") == vmi.SKIP_JOB_OPT_OUT)


def test_written_when_enabled(tmp: Path) -> None:
    job = _make_job(tmp, [content_table()], plan_ids=["tbl"])
    _text, info = _run_pilot(job, enabled=True)
    trace = _read_trace(job)
    check("3. enabled+opted+selected → trace written", trace is not None)
    check("3. trace status inserted", trace and trace.get("status") == vmi.STATUS_INSERTED)
    check("3. schema_version present", trace and trace.get("schema_version") == 1)
    check("3. insertion succeeded", info.get("status") == vmi.STATUS_INSERTED)


def test_effective_cap_default_one(tmp: Path) -> None:
    job = _make_job(tmp, [content_table("a"), content_table("b")])
    _run_pilot(job, enabled=True, cap=None)
    trace = _read_trace(job)
    check("4. default effective_max_images == 1",
          trace and trace.get("effective_max_images") == 1, str(trace))
    check("4. inserted_visual_count == 1", trace and trace.get("inserted_visual_count") == 1)
    check("4. selected_count == 1",
          trace and trace["candidate_summary"]["selected_count"] == 1)


def test_effective_cap_two(tmp: Path) -> None:
    job = _make_job(tmp, [content_table("a", page=5), content_table("b", page=6)])
    _run_pilot(job, enabled=True, cap="2")
    trace = _read_trace(job)
    check("5. cap=2 → effective_max_images == 2",
          trace and trace.get("effective_max_images") == 2, str(trace))
    check("5. cap=2 → inserted_visual_count == 2",
          trace and trace.get("inserted_visual_count") == 2)
    check("6. cap=2 → selected_count == 2 + inserted recorded",
          trace and trace["candidate_summary"]["selected_count"] == 2
          and len(trace["selected_candidates"]) == 2)


def test_selected_visual_types_recorded(tmp: Path) -> None:
    if not _HAVE_PIL:
        skip("7/8. visual-type recording", "Pillow unavailable")
        return
    job = _make_job(tmp, [content_table("a", page=5), content_table("b", page=6)])
    _run_pilot(job, enabled=True, cap="2")
    trace = _read_trace(job)
    types = {c["visual_type"] for c in trace["selected_candidates"]}
    check("7. selected types recorded as closed tokens",
          types and types.issubset(vmi.VISUAL_TYPES), str(types))
    check("8. tables-only distinguished (no diagram selected)",
          types == {vmi.VISUAL_TYPE_TABLE}, str(types))
    check("8. type_counts has reconstructable_table",
          trace["candidate_summary"]["type_counts"].get(vmi.VISUAL_TYPE_TABLE, 0) >= 1)


def test_diagram_selected_distinguished(tmp: Path) -> None:
    if not _HAVE_PIL:
        skip("8. diagram-selected distinguished", "Pillow unavailable")
        return
    job = _make_job(tmp, [content_table("tbl", page=5), content_diagram("dia", page=6)])
    _run_pilot(job, enabled=True, cap="2")
    trace = _read_trace(job)
    first = trace["selected_candidates"][0]
    check("8. diagram ranked first (visual_type)",
          first["visual_type"] == vmi.VISUAL_TYPE_DIAGRAM, str(first))
    check("8. diagram-first selection_reason token",
          first["selection_reason"] == vmi.TRACE_SELECTED_DIAGRAM_FIRST, str(first))
    types = {c["visual_type"] for c in trace["selected_candidates"]}
    check("8. diagram present in selected types", vmi.VISUAL_TYPE_DIAGRAM in types)


def test_safe_unsafe_counts(tmp: Path) -> None:
    job = _make_job(tmp, [content_table("a", page=5), content_table("b", page=6)])
    _run_pilot(job, enabled=True, cap="2")
    trace = _read_trace(job)
    cs = trace["candidate_summary"]
    check("9. safe_candidate_count == 2", cs["safe_candidate_count"] == 2, str(cs))
    check("9. unsafe_candidate_count == 0", cs["unsafe_candidate_count"] == 0, str(cs))
    check("9. total_manifest_assets == 2", cs["total_manifest_assets"] == 2, str(cs))
    check("9. safe + unsafe == total",
          cs["safe_candidate_count"] + cs["unsafe_candidate_count"]
          == cs["total_manifest_assets"])


def test_unsafe_refs_counted_not_raw(tmp: Path) -> None:
    # An unsafe ref (absolute-looking) must be counted/rejected but never written raw.
    bad = _figure("bad", page=4, kind="solid", bbox=[100, 200, 500, 600],
                  pw=PW, ph=PH, cw=800, ch=800,
                  image_ref="/etc/passwd")
    good = content_table("good", page=5)
    job = _make_job(tmp, [bad, good], plan_ids=["good"])
    _run_pilot(job, enabled=True, cap="2")
    trace = _read_trace(job)
    cs = trace["candidate_summary"]
    check("12. unsafe ref counted", cs["unsafe_candidate_count"] >= 1, str(cs))
    check("12. unsafe ref → rejected_unsafe_ref token",
          cs["rejection_reason_counts"].get(vmi.TRACE_REJECTED_UNSAFE_REF, 0) >= 1, str(cs))
    check("12. unsafe ref NOT written raw", "/etc/passwd" not in json.dumps(trace))
    check("12. good candidate still safe", cs["safe_candidate_count"] >= 1)


def test_foreign_providers_rejected(tmp: Path) -> None:
    chandra = _figure("ch", page=2, provider="chandra", bbox=[100, 200, 500, 600],
                      pw=PW, ph=PH, cw=800, ch=800)
    mistral = _figure("mi", page=2, provider="mistral", bbox=[100, 200, 500, 600],
                      pw=PW, ph=PH, cw=800, ch=800)
    page_sig = _figure("ps", page=2, atype="page_visual_signal", bbox=[100, 200, 500, 600],
                       pw=PW, ph=PH, cw=800, ch=800)
    blocked = _figure("bl", page=2, bbox=[100, 200, 500, 600], pw=PW, ph=PH,
                      cw=800, ch=800, reasons=["chandra_blocked"])
    good = content_table("good", page=5)
    job = _make_job(tmp, [chandra, mistral, page_sig, blocked, good], plan_ids=["good"])
    _run_pilot(job, enabled=True, cap="2")
    trace = _read_trace(job)
    cs = trace["candidate_summary"]
    rc = cs["rejection_reason_counts"]
    check("13. foreign providers rejected (>=2 wrong_provider)",
          rc.get(vmi.TRACE_REJECTED_WRONG_PROVIDER, 0) >= 2, str(rc))
    check("13. page_visual_signal rejected (wrong_asset_type)",
          rc.get(vmi.TRACE_REJECTED_WRONG_ASSET_TYPE, 0) >= 1, str(rc))
    check("13. only the one fitz_local figure is safe", cs["safe_candidate_count"] == 1, str(cs))
    check("13. foreign provider tokens not raw",
          "chandra" not in json.dumps(trace) and "mistral" not in json.dumps(trace))


def test_no_leak_sweep(tmp: Path) -> None:
    job = _make_job(tmp, [content_table("a", page=5), content_diagram("b", page=6)],
                    plan_ids=["a", "b"])
    _run_pilot(job, enabled=True, cap="2")
    trace = _read_trace(job)
    leak = _sweep(trace)
    check("10/11. trace has no path/filename/text/bytes/base64/datauri/token", leak is None,
          f"leak={leak}")
    # Every asset_ref present is a safe assets/<slug>.png shape only.
    refs = [c["asset_ref"] for c in trace["selected_candidates"]]
    ok_refs = all(r is None or re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", r) for r in refs)
    check("10. asset_refs are safe job-local shape only", ok_refs, str(refs))
    check("11. raw caption text absent", vmi.SELECTION_TRACE_FILENAME and
          SECRET_CAPTION not in json.dumps(trace))


def test_trace_failure_never_fails_generation(tmp: Path) -> None:
    job = _make_job(tmp, [content_table("a", page=5)], plan_ids=["a"])
    orig = vmi.build_visual_markdown_selection_trace

    def _boom(*a, **k):
        raise RuntimeError("synthetic trace failure")

    vmi.build_visual_markdown_selection_trace = _boom  # type: ignore[assignment]
    try:
        text, info = _run_pilot(job, enabled=True)
    finally:
        vmi.build_visual_markdown_selection_trace = orig  # type: ignore[assignment]
    check("14. generation still succeeds when trace build raises",
          info.get("status") == vmi.STATUS_INSERTED)
    check("14. figure still inserted despite trace failure", "![" in text)
    check("14. no trace file left on failure", not _trace_path(job).is_file())


def test_default_off_byte_identical(tmp: Path) -> None:
    job = _make_job(tmp, [content_table("a", page=5)])
    # No env at all → master switch off → byte-identical, no artifact.
    text, info = _with_env(
        {vmi.ENABLE_ENV: None, vmi.MAX_IMAGES_ENV: None},
        lambda: vmi.apply_visual_markdown_pilot(job, BASE_MD),
    )
    check("15. default-off output byte-identical", text == BASE_MD)
    check("15. default-off writes no trace", not _trace_path(job).is_file())


def test_two_key_gate_unchanged(tmp: Path) -> None:
    # Master ON but job opt-out → still skipped, no trace (per-job half of the gate).
    job = _make_job(tmp, [content_table("a", page=5)], opt_in=False)
    text, info = _run_pilot(job, enabled=True, cap="2")
    check("16. two-key gate: opt-out still blocks insertion", text == BASE_MD)
    check("16. two-key gate: opt-out writes no trace", not _trace_path(job).is_file())


def test_cap_constants_unchanged() -> None:
    check("17. default cap reader == 1",
          _with_env({vmi.MAX_IMAGES_ENV: None}, vmi.visual_markdown_pilot_max_images) == 1)
    check("17. hard cap == 2", vmi._HARD_MAX_IMAGES == 2)
    check("17. env over hard cap clamps to default 1",
          _with_env({vmi.MAX_IMAGES_ENV: "5"}, vmi.visual_markdown_pilot_max_images) == 1)
    check("17. valid env 2 honored",
          _with_env({vmi.MAX_IMAGES_ENV: "2"}, vmi.visual_markdown_pilot_max_images) == 2)


def test_export_does_not_pick_up_trace(tmp: Path) -> None:
    job = _make_job(tmp, [content_table("a", page=5)], plan_ids=["a"])
    _run_pilot(job, enabled=True)
    check("3. (sanity) trace exists for export check", _trace_path(job).is_file())
    exportable = list(vmi.find_exportable_visual_pilot_assets(job))
    has_trace = any(vmi.SELECTION_TRACE_FILENAME in str(r) for r in exportable)
    has_png_only = all(re.fullmatch(r"assets/[A-Za-z0-9_]+\.png", str(r)) for r in exportable)
    check("18. export ride-along excludes the trace file", not has_trace, str(exportable))
    check("18. export ride-along stays PNG-only", has_png_only, str(exportable))


def test_apply_does_not_write_clean_md(tmp: Path) -> None:
    # The pilot returns text; clean.md is written only by the run_markdown_job
    # save_clean_md chokepoint, never by the pilot/trace path.
    job = _make_job(tmp, [content_table("a", page=5)], plan_ids=["a"])
    _run_pilot(job, enabled=True)
    check("19. pilot/trace path does not write clean.md", not job.clean_md.exists())


def test_skip_low_quality_still_traces(tmp: Path) -> None:
    # A decorative-only manifest → nothing inserted, but selection WAS attempted, so a
    # trace is still written explaining the skip.
    deco = _figure("logo", page=1, kind="solid", bbox=[280, 380, 300, 400],
                   pw=PW, ph=PH, cw=40, ch=40)  # tiny crop → decorative
    job = _make_job(tmp, [deco])
    _text, info = _run_pilot(job, enabled=True)
    trace = _read_trace(job)
    check("3b. skip(low-quality) still writes a trace", trace is not None)
    check("3b. skip trace status == skipped", trace and trace.get("status") == "skipped")
    check("3b. skip trace reason is a closed skip token",
          trace and (trace.get("reason") in vmi.SKIP_REASONS or trace.get("reason") is None))
    check("3b. skip trace inserted_visual_count == 0",
          trace and trace.get("inserted_visual_count") == 0)


def main() -> int:
    cases = [
        test_not_written_when_flag_off,
        test_not_written_when_opt_out,
        test_written_when_enabled,
        test_effective_cap_default_one,
        test_effective_cap_two,
        test_selected_visual_types_recorded,
        test_diagram_selected_distinguished,
        test_safe_unsafe_counts,
        test_unsafe_refs_counted_not_raw,
        test_foreign_providers_rejected,
        test_no_leak_sweep,
        test_trace_failure_never_fails_generation,
        test_default_off_byte_identical,
        test_two_key_gate_unchanged,
        test_export_does_not_pick_up_trace,
        test_apply_does_not_write_clean_md,
        test_skip_low_quality_still_traces,
    ]
    for case in cases:
        with tempfile.TemporaryDirectory() as d:
            case(Path(d))
    test_cap_constants_unchanged()

    print(f"\n{PASS} passed, {FAIL} failed, {SKIP} skipped")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
