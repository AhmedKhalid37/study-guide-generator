#!/usr/bin/env python3
"""Focused tests for Slice 51: visual advisory JSON artifacts in export bundles.

Run with:

    python test_scripts/test_visual_advisory_export_bundle.py

No external APIs and no PyMuPDF/Tesseract/Mistral/Gemini/Chandra dependency. The
whole suite drives ``api.server.export_bundle`` directly against temp-dir Jobs
(``_get_job`` is monkeypatched to map ids -> temp Jobs), so it never touches the
real jobs directory.

Slice 51 bundles the three advisory visual diagnostic JSON artifacts ALONGSIDE the
requested exports WHEN PRESENT:

    visual_assets_manifest.json   (Slice 40)
    visual_asset_scoring.json     (Slice 47)
    visual_replacement_plan.json  (Slice 49)

It includes JSON diagnostics only (never cropped images / image bytes), adds no
generic artifact UI rows, makes no production include/omit decision, never mutates
the source artifacts, and never gates the bundle (absent advisory files are skipped
calmly). The whole suite is SKIPPED automatically when FastAPI is not importable in
host Python (run in Docker for full coverage).
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\\\|\\\\\\\\)")
URLLIKE = re.compile(r"https?://")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z])")
DATAURI = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,", re.IGNORECASE)

# A sentinel placed inside the advisory artifact *bodies*. The bundle index
# (manifest.json) must list filenames/presence only and must NEVER echo this.
RAW_SENTINEL = "raw_unsafe_body_sentinel"


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
    if ARGV_OR_SOCKET.search(text):
        return "argv/socket-like value"
    if DATAURI.search(text):
        return "data-uri/base64-like value"
    return None


def main() -> int:
    try:
        from fastapi import HTTPException

        from api import server  # noqa: WPS433
    except Exception as exc:  # FastAPI / deps not importable in host python
        print(f"[SKIP] api.server bundle section ({type(exc).__name__})")
        print("\n0 passed, 0 failed")
        return 0

    from pipeline.job_manager import Job

    ADVISORY = (
        "visual_assets_manifest.json",
        "visual_asset_scoring.json",
        "visual_replacement_plan.json",
    )

    def _make_job(root: Path, job_id: str, *, with_pdf=True, advisory=()) -> Job:
        job = Job(id=job_id, root=root)
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job.logs_dir.mkdir(parents=True, exist_ok=True)
        job._write_manifest({"id": job.id, "status": "completed", "title": job.id})
        if with_pdf:
            job.final_pdf.write_bytes(b"%PDF-1.4 fake pdf bytes")
        # A stray cropped image must NEVER be bundled by this slice.
        assets = job.dir / "assets"
        assets.mkdir(exist_ok=True)
        (assets / "fig_p001_01.png").write_bytes(b"\x89PNG\r\n\x1a\n fake png")
        path_by_name = {
            "visual_assets_manifest.json": job.visual_assets_manifest_json,
            "visual_asset_scoring.json": job.visual_asset_scoring_json,
            "visual_replacement_plan.json": job.visual_replacement_plan_json,
        }
        for name in advisory:
            body = {
                "version": 1,
                "kind": name[: -len(".json")],
                "status": "completed",
                "summary": {"note": RAW_SENTINEL},
                "items": [],
            }
            job.save_text(path_by_name[name], json.dumps(body, indent=2) + "\n")
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

    def _names(resp) -> list[str]:
        with zipfile.ZipFile(io.BytesIO(resp.body)) as zf:
            return zf.namelist()

    # --- all three advisory present -----------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-all", advisory=ADVISORY)
        resp = _bundle({"job-all": job}, ["job-all"], ["pdf"])
        names = _names(resp)
        for name in ADVISORY:
            check(f"all-present bundle includes {name}",
                  any(n.endswith("/" + name) for n in names), str(names))
        check("all-present bundle still includes requested pdf",
              any(n.endswith("/final.pdf") for n in names), str(names))

    # --- partial advisory set ------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-part",
                        advisory=("visual_assets_manifest.json",
                                  "visual_asset_scoring.json"))
        resp = _bundle({"job-part": job}, ["job-part"], ["pdf"])
        names = _names(resp)
        check("partial bundle includes manifest",
              any(n.endswith("/visual_assets_manifest.json") for n in names))
        check("partial bundle includes scoring",
              any(n.endswith("/visual_asset_scoring.json") for n in names))
        check("partial bundle omits absent plan calmly",
              not any(n.endswith("/visual_replacement_plan.json") for n in names))

    # --- none present: behaves exactly as before -----------------------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-none", advisory=())
        resp = _bundle({"job-none": job}, ["job-none"], ["pdf"])
        names = _names(resp)
        check("no-advisory bundle has no advisory files",
              not any(any(n.endswith("/" + a) for a in ADVISORY) for n in names))
        check("no-advisory bundle still includes pdf",
              any(n.endswith("/final.pdf") for n in names))

    # --- never bundles cropped images / PNG / image bytes --------------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-png", advisory=ADVISORY)
        resp = _bundle({"job-png": job}, ["job-png"], ["pdf"])
        names = _names(resp)
        check("bundle contains no .png image files",
              not any(n.lower().endswith(".png") for n in names), str(names))
        check("bundle contains no assets/ dir entries",
              not any("/assets/" in n for n in names), str(names))

    # --- bundle index: safe metadata only, no raw artifact body --------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-idx", advisory=ADVISORY)
        resp = _bundle({"job-idx": job}, ["job-idx"], ["pdf"])
        with zipfile.ZipFile(io.BytesIO(resp.body)) as zf:
            manifest_text = zf.read("manifest.json").decode("utf-8")
        manifest = json.loads(manifest_text)
        entry = manifest["jobs"][0]
        check("index records visual_advisory_included filenames",
              set(entry.get("visual_advisory_included", [])) == set(ADVISORY),
              str(entry.get("visual_advisory_included")))
        check("index does NOT echo raw artifact body content",
              RAW_SENTINEL not in manifest_text)
        leak = _scan_for_leak(manifest_text)
        check("index has no path/url/credential/base64 leak", leak is None, leak or "")

    # --- advisory artifacts do not satisfy the requested-artifact gate -------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Job exists with advisory files but NO pdf; a pdf bundle must still 404.
        job = _make_job(root, "job-gate", with_pdf=False, advisory=ADVISORY)
        raised = False
        try:
            _bundle({"job-gate": job}, ["job-gate"], ["pdf"])
        except HTTPException as exc:
            raised = exc.status_code == 404
        check("advisory-only job still 404s for absent requested pdf", raised)

    # --- export does not mutate the advisory artifacts -----------------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-immut", advisory=ADVISORY)
        before = {
            name: (job.dir / name).read_bytes() for name in ADVISORY
        }
        _bundle({"job-immut": job}, ["job-immut"], ["pdf"])
        for name in ADVISORY:
            check(f"export leaves {name} byte-identical",
                  (job.dir / name).read_bytes() == before[name])

    # --- generic UI exposure unchanged + exact-name routes intact ------------
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        job = _make_job(root, "job-rows", advisory=ADVISORY)
        for name in ADVISORY:
            check(f"{name} not in ARTIFACTS", name not in server.ARTIFACTS)
            check(f"{name} not in EXPORT_ARTIFACTS", name not in server.EXPORT_ARTIFACTS)
            check(f"{name} not an export alias",
                  name not in server.EXPORT_ARTIFACT_ALIASES)
            path, media = server._artifact_path(job, name)
            check(f"{name} exact-name route resolves",
                  path == (job.dir / name) and media == "application/json")
        availability = server._artifact_availability(job)
        urls = server._artifact_urls(job, availability)
        details = {d.get("name") for d in server._artifact_details(job, availability)}
        for name in ADVISORY:
            check(f"{name} not in _artifact_urls", name not in urls)
            check(f"{name} not in _artifact_details", name not in details)
        check("VISUAL_ADVISORY_EXPORT_ARTIFACTS holds exactly the three names",
              tuple(server.VISUAL_ADVISORY_EXPORT_ARTIFACTS) == ADVISORY)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
