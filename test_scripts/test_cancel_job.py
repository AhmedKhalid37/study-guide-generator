#!/usr/bin/env python3
"""Focused test for cooperative server-side job cancellation.

Covers the cancel slice end-to-end WITHOUT needing an LLM provider or the
Chromium renderer:

  1. Cancel-marker lifecycle on a Job (request / observe / clear) and that
     ``raise_if_cancelled`` raises :class:`JobCancelled`.
  2. The shared markdown pipeline (``run_raw_markdown_pipeline``) short-circuits
     at its first safe checkpoint when a cancel was requested — it raises
     ``JobCancelled`` and writes NEITHER ``clean.md`` NOR ``final.pdf`` (so the
     uninterruptible Chromium render is never reached and nothing is corrupted).
  3. A paste entry point (``run_pasted_text_job``) catches the cancel and ends
     the job in the non-failure terminal status ``cancelled`` (via a marker
     pre-seeded by monkeypatching ``Job.create``), with its input preserved.
  4. The ``POST /api/jobs/{id}/cancel`` endpoint via FastAPI TestClient:
     running job -> marker written + ``cancelled: true``; already-``done`` job ->
     no-op (no marker, artifacts untouched); unknown id -> 404.

No external APIs. The endpoint portion SKIPS cleanly if FastAPI/TestClient is
unavailable. Run inside the Docker image for full coverage.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Make the repo root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.job_manager import Job, JobCancelled  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, ok: bool) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def _new_job(root: Path, job_id: str, **meta) -> Job:
    """Construct a Job rooted at a temp dir with a minimal manifest on disk."""
    job = Job(job_id, root=root)
    job.input_dir.mkdir(parents=True, exist_ok=True)
    job.logs_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"id": job_id, "status": "created"}
    manifest.update(meta)
    job._write_manifest(manifest)
    return job


def test_marker_lifecycle(tmp: Path) -> None:
    job = _new_job(tmp, "lifecycle")
    check("marker absent initially", not job.cancel_requested())
    job.request_cancel()
    check("marker present after request_cancel", job.cancel_requested())
    check("marker file exists on disk", job.cancel_marker.exists())

    raised = False
    try:
        job.raise_if_cancelled()
    except JobCancelled as exc:
        raised = exc.job.id == job.id
    check("raise_if_cancelled raises JobCancelled", raised)

    job.clear_cancel_request()
    check("marker cleared after clear_cancel_request", not job.cancel_requested())
    # No-op once cleared.
    cleared_noop = True
    try:
        job.raise_if_cancelled()
    except JobCancelled:
        cleared_noop = False
    check("raise_if_cancelled is a no-op after clear", cleared_noop)


def test_pipeline_short_circuits(tmp: Path) -> None:
    from pipeline.run_markdown_job import run_raw_markdown_pipeline

    job = _new_job(tmp, "shortcircuit", path_mode="have_markdown")
    job.raw_md.write_text("# Title\n\nSome body text.\n", encoding="utf-8")
    job.request_cancel()

    raised = False
    try:
        run_raw_markdown_pipeline(job, theme="claude_clean", strict_math=True)
    except JobCancelled:
        raised = True
    check("run_raw_markdown_pipeline raises JobCancelled when cancel requested", raised)
    # Crucially: it bailed BEFORE sanitize/render, so no artifacts were written.
    check("clean.md NOT created on cancel (no partial write)", not job.clean_md.exists())
    check("final.pdf NOT created on cancel (render skipped)", not job.final_pdf.exists())


def test_paste_entry_point_marks_cancelled(tmp: Path) -> None:
    """run_pasted_text_job should catch the cancel and end status 'cancelled'."""
    import pipeline.run_markdown_job as rmj

    original_create = Job.create

    def create_with_marker(meta=None):
        # Build the job under our temp root, then pre-seed a cancel request so the
        # first pipeline checkpoint trips immediately (no LLM/Chromium involved).
        job_id = "paste-cancel"
        job = _new_job(tmp, job_id, **(meta or {}))
        job.request_cancel()
        return job

    Job.create = staticmethod(create_with_marker)
    try:
        job = rmj.run_pasted_text_job("# Pasted\n\nbody\n", theme="claude_clean", strict_math=True)
    finally:
        Job.create = original_create

    manifest = job.read_manifest()
    check("paste job ends in status 'cancelled'", manifest.get("status") == "cancelled")
    check("paste job is not a failure (error stays falsy)", not manifest.get("error"))
    check("cancel marker cleared after observe", not job.cancel_requested())
    check("pasted input preserved after cancel", job.raw_md.exists())
    check("no final.pdf produced for cancelled paste job", not job.final_pdf.exists())


def test_endpoint() -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception as exc:  # pragma: no cover - env without fastapi/httpx
        print(f"[SKIP] endpoint test — TestClient unavailable: {exc}")
        return

    try:
        from api.server import app
        from pipeline.job_manager import JOBS_DIR
    except Exception as exc:  # pragma: no cover
        print(f"[SKIP] endpoint test — could not import app: {exc}")
        return

    client = TestClient(app)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)

    running_id = "zzcancel-running-test"
    done_id = "zzcancel-done-test"
    created: list[Path] = []

    def make(job_id: str, status: str) -> Job:
        job = Job(job_id)  # rooted at the real JOBS_DIR so _get_job resolves it
        job.input_dir.mkdir(parents=True, exist_ok=True)
        job._write_manifest({"id": job_id, "status": status})
        created.append(job.dir)
        return job

    try:
        running = make(running_id, "generating")
        done = make(done_id, "done")

        r1 = client.post(f"/api/jobs/{running_id}/cancel")
        body1 = r1.json()
        check("endpoint: running job -> 200", r1.status_code == 200)
        check("endpoint: running job -> cancelled true", body1.get("cancelled") is True)
        check("endpoint: running job -> marker written", running.cancel_requested())

        r2 = client.post(f"/api/jobs/{done_id}/cancel")
        body2 = r2.json()
        check("endpoint: done job -> 200", r2.status_code == 200)
        check("endpoint: done job -> cancelled false", body2.get("cancelled") is False)
        check("endpoint: done job -> status echoed 'done'", body2.get("status") == "done")
        check("endpoint: done job -> NO marker written", not done.cancel_requested())

        r3 = client.post("/api/jobs/zzcancel-nonexistent-xyz/cancel")
        check("endpoint: unknown id -> 404", r3.status_code == 404)
    finally:
        for path in created:
            shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_marker_lifecycle(tmp)
        test_pipeline_short_circuits(tmp)
        test_paste_entry_point_marks_cancelled(tmp)
    test_endpoint()

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
