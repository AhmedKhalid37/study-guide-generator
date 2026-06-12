#!/usr/bin/env python3
"""Focused tests for Slice 56: the visual-pilot PNG ride-along in export bundles.

Run with:

    python test_scripts/test_visual_pilot_export_asset.py

No external APIs and no PyMuPDF/Tesseract/Mistral/Gemini/Chandra dependency.

Slice 56 makes exported Markdown/HTML portable: when a job's ``clean.md`` references
the Slice 54 visual pilot's safe job-local image (``![caption](assets/<slug>.png)``),
that *single* referenced PNG rides along in the export bundle. It does NOT export the
whole ``assets/`` directory, does NOT export unreferenced / extra cropped images,
includes at most one PNG (the pilot's one-figure rule), never counts the PNG toward
the requested-artifact gate, and never leaks image bytes or absolute paths into the
bundle index / logs.

The suite has two parts:

  * Part A — PURE helper checks (always run): ``extract_visual_pilot_asset_refs`` and
    ``find_exportable_visual_pilot_asset`` safety/containment, no FastAPI needed.
  * Part B — BUNDLE checks: drive ``api.server.export_bundle`` directly against
    temp-dir Jobs (``_get_job`` monkeypatched). SKIPPED automatically when FastAPI is
    not importable in host Python (run in Docker for full coverage).
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.visual_markdown_insertion import (  # noqa: E402
    extract_visual_pilot_asset_refs,
    find_exportable_visual_pilot_asset,
)

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\)")
URLLIKE = re.compile(r"https?://")
DATAURI = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,", re.IGNORECASE)

# A recognisable ASCII marker embedded in the fake PNG bytes. It must appear in the
# zipped image entry (proving the ride-along works) but NEVER in the bundle index.
PNG_BODY_SENTINEL = "png_image_body_sentinel"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + PNG_BODY_SENTINEL.encode("ascii") + b" fake png"


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


def _scan_for_leak(text: str) -> str | None:
    if KEYLIKE.search(text):
        return "credential-like value"
    if PATHLIKE.search(text):
        return "filesystem-path-like value"
    if URLLIKE.search(text):
        return "url-like value"
    if DATAURI.search(text):
        return "data-uri/base64-like value"
    return None


def _fake_job(job_dir: Path) -> SimpleNamespace:
    """A minimal duck-typed job for the pure helpers (only ``dir`` + ``clean_md``)."""
    return SimpleNamespace(dir=job_dir, clean_md=job_dir / "clean.md")


# ---------------------------------------------------------------------------
# Part A — pure helper checks (no FastAPI)
# ---------------------------------------------------------------------------


def part_a() -> None:
    # extract_visual_pilot_asset_refs: keeps only safe refs, de-dupes, order-preserving
    md = (
        "# Guide\n\n"
        "![Figure from page 3](assets/fig_p003_01.png)\n\n"
        "![dup](assets/fig_p003_01.png)\n\n"
        "![second](assets/fig_p004_02.png)\n"
    )
    refs = extract_visual_pilot_asset_refs(md)
    check("extract keeps distinct safe refs in order",
          refs == ["assets/fig_p003_01.png", "assets/fig_p004_02.png"], str(refs))

    # Unsafe / non-pilot markdown image refs are all rejected by the validator.
    unsafe_md = "\n\n".join(
        [
            "![abs](/etc/passwd.png)",
            "![dotdot](assets/../secret.png)",
            "![backslash](assets\\fig.png)",
            "![url](https://example.com/a.png)",
            "![datauri](data:image/png;base64,AAAA.png)",
            "![nonpng](assets/fig.jpg)",
            "![nested](assets/sub/fig.png)",
            "![dash-slug](assets/fig-1.png)",  # '-' not in [A-Za-z0-9_]
        ]
    )
    check("extract rejects every unsafe/non-pilot ref",
          extract_visual_pilot_asset_refs(unsafe_md) == [], str(extract_visual_pilot_asset_refs(unsafe_md)))

    check("extract handles non-string input", extract_visual_pilot_asset_refs(None) == [])
    check("extract handles empty string", extract_visual_pilot_asset_refs("") == [])

    # find_exportable_visual_pilot_asset: returns the ref only when the file exists.
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job1"
        (job_dir / "assets").mkdir(parents=True)
        (job_dir / "assets" / "fig_p003_01.png").write_bytes(PNG_BYTES)
        (job_dir / "clean.md").write_text(md, encoding="utf-8")
        job = _fake_job(job_dir)
        check("find returns the first referenced+present ref",
              find_exportable_visual_pilot_asset(job) == "assets/fig_p003_01.png",
              str(find_exportable_visual_pilot_asset(job)))

    # Referenced but MISSING file -> None (skipped calmly).
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job2"
        job_dir.mkdir(parents=True)
        (job_dir / "clean.md").write_text(
            "![x](assets/missing.png)\n", encoding="utf-8"
        )
        check("find returns None when referenced file is missing",
              find_exportable_visual_pilot_asset(_fake_job(job_dir)) is None)

    # No clean.md at all -> None.
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job3"
        job_dir.mkdir(parents=True)
        check("find returns None when there is no clean.md",
              find_exportable_visual_pilot_asset(_fake_job(job_dir)) is None)

    # clean.md present but references nothing safe -> None.
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job4"
        (job_dir / "assets").mkdir(parents=True)
        (job_dir / "assets" / "fig_p001_01.png").write_bytes(PNG_BYTES)  # exists but unreferenced
        (job_dir / "clean.md").write_text("# No images here\n", encoding="utf-8")
        check("find returns None when clean.md references no safe asset",
              find_exportable_visual_pilot_asset(_fake_job(job_dir)) is None)

    # Symlink escape: ref looks safe but resolves outside the job dir -> rejected.
    with tempfile.TemporaryDirectory() as tmp:
        outside = Path(tmp) / "outside.png"
        outside.write_bytes(PNG_BYTES)
        job_dir = Path(tmp) / "job5"
        (job_dir / "assets").mkdir(parents=True)
        link = job_dir / "assets" / "escape.png"
        try:
            link.symlink_to(outside)
            symlink_ok = True
        except (OSError, NotImplementedError):
            symlink_ok = False
        if symlink_ok:
            (job_dir / "clean.md").write_text(
                "![x](assets/escape.png)\n", encoding="utf-8"
            )
            check("find rejects a symlink that escapes the job dir",
                  find_exportable_visual_pilot_asset(_fake_job(job_dir)) is None)
        else:
            print("[SKIP] symlink escape (symlinks unavailable)")


# ---------------------------------------------------------------------------
# Part B — bundle checks (needs FastAPI)
# ---------------------------------------------------------------------------


def part_b() -> int:
    try:
        from fastapi import HTTPException

        from api import server  # noqa: WPS433
    except Exception as exc:  # FastAPI / deps not importable in host python
        print(f"[SKIP] api.server bundle section ({type(exc).__name__})")
        return 0

    from pipeline.job_manager import Job

    def _make_job(
        root: Path,
        job_id: str,
        *,
        with_pdf: bool = True,
        clean_md: str | None = None,
        assets: dict[str, bytes] | None = None,
    ) -> Job:
        job = Job(id=job_id, root=root)
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        job._write_manifest({"id": job.id, "status": "completed", "title": job.id})
        if with_pdf:
            job.final_pdf.write_bytes(b"%PDF-1.4 fake pdf bytes")
        if assets:
            job.assets_dir.mkdir(parents=True, exist_ok=True)
            for name, data in assets.items():
                (job.assets_dir / name).write_bytes(data)
        if clean_md is not None:
            job.save_text(job.clean_md, clean_md)
        return job

    def _bundle(jobs_by_id, job_ids, artifacts):
        original = server._get_job

        def fake_get_job(raw_id):
            jid = str(raw_id)
            if jid in jobs_by_id:
                return jobs_by_id[jid]
            raise HTTPException(status_code=404, detail="Job not found.")

        server._get_job = fake_get_job
        try:
            resp = server.export_bundle(
                server.BundleRequest(job_ids=job_ids, artifacts=artifacts)
            )
        finally:
            server._get_job = original
        return resp

    def _zip(resp):
        return zipfile.ZipFile(io.BytesIO(resp.body))

    def _names(resp) -> list[str]:
        with _zip(resp) as zf:
            return zf.namelist()

    REFERENCED = "fig_p003_01.png"
    EXTRA = "fig_p007_09.png"
    CLEAN_WITH_REF = (
        "# Guide\n\nSome text.\n\n"
        f"![Figure from page 3](assets/{REFERENCED})\n\nMore text.\n"
    )

    # --- referenced PNG rides along, exactly once, under base_dir/assets/ ----
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(
            root, "job-ref",
            clean_md=CLEAN_WITH_REF,
            assets={REFERENCED: PNG_BYTES, EXTRA: PNG_BYTES},
        )
        resp = _bundle({"job-ref": job}, ["job-ref"], ["pdf", "markdown"])
        names = _names(resp)
        png_entries = [n for n in names if n.lower().endswith(".png")]
        check("bundle includes exactly one png", len(png_entries) == 1, str(png_entries))
        check("the included png is the referenced asset",
              any(n.endswith(f"/assets/{REFERENCED}") for n in names), str(names))
        check("bundle does NOT include the unreferenced extra png",
              not any(n.endswith(f"/assets/{EXTRA}") for n in names), str(names))
        check("png zip entry is a relative path (no leading slash, no '..', no backslash)",
              all(not p.startswith("/") and ".." not in p and "\\" not in p for p in png_entries),
              str(png_entries))
        check("png zip entry sits under the job base dir",
              all(p.count("/") >= 2 and "/assets/" in p for p in png_entries), str(png_entries))
        # The actual image bytes ride along in the entry...
        with _zip(resp) as zf:
            png_data = zf.read(png_entries[0])
            manifest_text = zf.read("manifest.json").decode("utf-8")
        check("png entry carries the real image bytes", png_data == PNG_BYTES)
        # ...but the bundle index must not echo image bytes or absolute paths.
        check("manifest does NOT echo image body bytes",
              PNG_BODY_SENTINEL not in manifest_text)
        leak = _scan_for_leak(manifest_text)
        check("manifest has no path/url/credential/base64 leak", leak is None, leak or "")
        manifest = json.loads(manifest_text)
        entry = manifest["jobs"][0]
        check("manifest records the safe relative ref only",
              entry.get("visual_pilot_asset") == f"assets/{REFERENCED}",
              str(entry.get("visual_pilot_asset")))
        # The ride-along must NOT inflate the requested-artifact count.
        check("files_included counts requested artifacts only (pdf+markdown=2)",
              manifest.get("files_included") == 2, str(manifest.get("files_included")))

    # --- referenced PNG missing on disk: skipped calmly, export still succeeds
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-miss", clean_md=CLEAN_WITH_REF, assets=None)
        resp = _bundle({"job-miss": job}, ["job-miss"], ["pdf"])
        names = _names(resp)
        check("missing referenced png is skipped, no png bundled",
              not any(n.lower().endswith(".png") for n in names), str(names))
        check("export still includes the requested pdf",
              any(n.endswith("/final.pdf") for n in names), str(names))
        with _zip(resp) as zf:
            entry = json.loads(zf.read("manifest.json").decode("utf-8"))["jobs"][0]
        check("manifest records null pilot asset when file missing",
              entry.get("visual_pilot_asset") is None, str(entry.get("visual_pilot_asset")))

    # --- no safe reference: behaves exactly as before, no png ----------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(
            root, "job-noref",
            clean_md="# Guide\n\nNo figures.\n",
            assets={EXTRA: PNG_BYTES},  # present but unreferenced
        )
        resp = _bundle({"job-noref": job}, ["job-noref"], ["pdf"])
        names = _names(resp)
        check("unreferenced assets are never bundled",
              not any(n.lower().endswith(".png") for n in names), str(names))
        check("no /assets/ dir entries when nothing is referenced",
              not any("/assets/" in n for n in names), str(names))

    # --- unsafe refs in clean.md are all rejected at the bundle level --------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        unsafe_clean = "\n\n".join(
            [
                "![abs](/etc/passwd.png)",
                "![dotdot](assets/../secret.png)",
                "![url](https://example.com/a.png)",
                "![datauri](data:image/png;base64,AAAA.png)",
                "![nonpng](assets/real.jpg)",
                "![nested](assets/sub/real.png)",
            ]
        )
        job = _make_job(
            root, "job-unsafe",
            clean_md=unsafe_clean,
            assets={"secret.png": PNG_BYTES, "real.jpg": PNG_BYTES},
        )
        resp = _bundle({"job-unsafe": job}, ["job-unsafe"], ["pdf"])
        names = _names(resp)
        check("no unsafe-referenced file is ever bundled",
              not any(n.lower().endswith((".png", ".jpg")) for n in names), str(names))

    # --- ride-along PNG does NOT by itself satisfy the requested gate --------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Referenced PNG exists, but the requested artifact (pdf) does NOT.
        job = _make_job(
            root, "job-gate",
            with_pdf=False,
            clean_md=CLEAN_WITH_REF,
            assets={REFERENCED: PNG_BYTES},
        )
        raised = False
        try:
            _bundle({"job-gate": job}, ["job-gate"], ["pdf"])
        except HTTPException as exc:
            raised = exc.status_code == 404
        check("pilot-png-only job still 404s for absent requested pdf", raised)

    # --- export does not mutate the source asset -----------------------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(
            root, "job-immut",
            clean_md=CLEAN_WITH_REF,
            assets={REFERENCED: PNG_BYTES},
        )
        before = (job.assets_dir / REFERENCED).read_bytes()
        _bundle({"job-immut": job}, ["job-immut"], ["pdf"])
        check("export leaves the source PNG byte-identical",
              (job.assets_dir / REFERENCED).read_bytes() == before)
        # clean.md untouched too.
        check("export does not write clean.md",
              job.clean_md.read_text(encoding="utf-8") == CLEAN_WITH_REF)

    return 0


def main() -> int:
    part_a()
    part_b()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
