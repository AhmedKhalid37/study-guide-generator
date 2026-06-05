#!/usr/bin/env python3
"""Focused test for Ask Your Guide — Slice 2 backend context inventory.

Covers the two read-only endpoints WITHOUT any LLM provider, model call,
chunking, or Chromium render:

  GET /api/ask/jobs
    1. an eligible job (has a generated clean.md) appears;
    2. a guide-less / failed / incomplete job (no clean.md) does NOT appear.

  GET /api/ask/jobs/{job_id}/context
    3. returns guide/source counts, page-anchor count, and attachment
       names/modes/extracted_chars/warnings/page selections when present;
    4. an unknown job returns 404.

  Security / redaction (5)
    The responses never include raw guide text, raw extracted text, raw API
    keys, ``api_key``, ``Authorization``, ``sk-``, a full base URL with scheme,
    or secret-store content — even when those strings are present in the source
    artifacts/manifest on disk.

  Read-only (6)
    The original job artifacts (clean.md / extracted.txt / job.json) are
    byte-identical after calling both endpoints.

The pure ``ask_inventory`` reader is also unit-tested directly. The endpoint
portion SKIPS cleanly if FastAPI/TestClient is unavailable. Run inside the
Docker image for full coverage.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

# Make the repo root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import ask_inventory  # noqa: E402
from pipeline.job_manager import Job  # noqa: E402

PASS = 0
FAIL = 0

# A fake key planted in the source/manifest to prove it never escapes.
SECRET_KEY = "sk-live-THIS_MUST_NEVER_LEAK_0123456789abcdef"
GUIDE_BODY_MARKER = "ZZZ_GUIDE_BODY_SECRET_PROSE_MARKER"
SOURCE_BODY_MARKER = "ZZZ_SOURCE_BODY_SECRET_PROSE_MARKER"

CLEAN_MD = (
    "# Study Guide\n\n"
    "## Backpropagation\n\n"
    f"{GUIDE_BODY_MARKER} the chain rule propagates gradients.\n\n"
    "## Summary\n\n"
    "Key points only.\n"
)
# 3 ATX headings above (# Study Guide, ## Backpropagation, ## Summary).
EXPECTED_HEADINGS = 3

EXTRACTED_TXT = (
    "## Page 1\n\n"
    f"{SOURCE_BODY_MARKER} lecture slide one.\n\n"
    "## Page 2\n\n"
    "lecture slide two.\n\n"
    "## Page 3\n\n"
    "lecture slide three.\n"
)
EXPECTED_PAGE_ANCHORS = 3


def check(name: str, ok: bool) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def _digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pure_reader(tmp: Path) -> None:
    """ask_inventory reads counts read-only and returns no body."""
    job = Job("reader", root=tmp)
    job.dir.mkdir(parents=True, exist_ok=True)

    check("no guide -> not eligible", not ask_inventory.has_generated_guide(job))
    g0 = ask_inventory.guide_inventory(job)
    check("absent guide summary present=False", g0["clean_md_present"] is False)
    check("absent guide summary char_count=0", g0["char_count"] == 0)
    s0 = ask_inventory.source_inventory(job)
    check("absent source summary present=False", s0["extracted_txt_present"] is False)

    job.clean_md.write_text(CLEAN_MD, encoding="utf-8")
    job.extracted_txt.write_text(EXTRACTED_TXT, encoding="utf-8")

    check("guide present -> eligible", ask_inventory.has_generated_guide(job))
    g1 = ask_inventory.guide_inventory(job)
    check("guide char_count matches", g1["char_count"] == len(CLEAN_MD))
    check("guide heading_count counted", g1["heading_count"] == EXPECTED_HEADINGS)
    check(
        "guide summary carries no body",
        GUIDE_BODY_MARKER not in repr(g1),
    )

    s1 = ask_inventory.source_inventory(job)
    check("source char_count matches", s1["char_count"] == len(EXTRACTED_TXT))
    check("source page_anchor_count counted", s1["page_anchor_count"] == EXPECTED_PAGE_ANCHORS)
    check(
        "source summary carries no body",
        SOURCE_BODY_MARKER not in repr(s1),
    )


def test_endpoints() -> None:
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

    # Ids deliberately avoid an "sk-" / "task-" style substring so the redaction
    # scan (5) can flag a literal "sk-" key prefix without false-positiving on the
    # job id itself.
    eligible_id = "zzguidetest-eligible"
    guideless_id = "zzguidetest-guideless"
    created: list[Path] = []
    digests: dict[str, str | None] = {}

    def make(job_id: str, *, with_guide: bool, status: str) -> Job:
        job = Job(job_id)  # rooted at the real JOBS_DIR so _get_job resolves it
        job.input_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "id": job_id,
            "status": status,
            "title": f"Guide {job_id}",
            "created_at": "2026-06-05T10:00:00",
            "updated_at": "2026-06-05T10:05:00",
            "prompt_name": "basic_study_guide",
            "generator_preset": "claude_review",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "total_extracted_chars": 1234,
            # Planted secrets/paths that must never surface in any response.
            "api_key": SECRET_KEY,
            "Authorization": f"Bearer {SECRET_KEY}",
            "base_url": "https://api.deepseek.com/v1",
            "input_path": "/home/secret/jobs/input/lecture.pdf",
            "attachments": [
                {
                    "filename": "lecture.pdf",
                    "mode": "pdf_mixed",
                    "status": "extracted",
                    "extracted_chars": 18799,
                    "truncated": True,
                    "warnings": ["page 4 OCR was low confidence"],
                    "api_key": SECRET_KEY,
                }
            ],
            "page_selections": {"lecture.pdf": [[1, 3]]},
        }
        job._write_manifest(manifest)
        if with_guide:
            job.clean_md.write_text(CLEAN_MD, encoding="utf-8")
            job.extracted_txt.write_text(EXTRACTED_TXT, encoding="utf-8")
        created.append(job.dir)
        return job

    try:
        eligible = make(eligible_id, with_guide=True, status="done")
        make(guideless_id, with_guide=False, status="failed")

        # Snapshot original artifact digests for the read-only proof (6).
        digests["clean"] = _digest(eligible.clean_md)
        digests["extracted"] = _digest(eligible.extracted_txt)
        digests["manifest"] = _digest(eligible.manifest)

        # ── GET /api/ask/jobs ───────────────────────────────────────────────
        r = client.get("/api/ask/jobs?limit=200")
        check("list: 200", r.status_code == 200)
        listing = r.json().get("jobs", [])
        ids = {row.get("id") for row in listing}
        check("list: eligible job appears (1)", eligible_id in ids)
        check("list: guide-less job absent (2)", guideless_id not in ids)

        row = next((x for x in listing if x.get("id") == eligible_id), {})
        check("list: row has title", row.get("title") == f"Guide {eligible_id}")
        check("list: row has status done", row.get("status") == "done")
        check("list: row has style", row.get("style") == "basic_study_guide")
        check("list: row has provider/model", row.get("provider") == "deepseek" and row.get("model") == "deepseek-chat")
        check("list: row marks guide_available", row.get("guide_available") is True)
        check("list: row marks source_available", row.get("source_available") is True)

        # Scope the redaction scan to OUR job's row only — the listing also returns
        # unrelated real jobs whose titles may legitimately contain "sk-"/"task-".
        import json as _json

        list_blob = _json.dumps(row, ensure_ascii=False)

        # ── GET /api/ask/jobs/{id}/context ──────────────────────────────────
        rc = client.get(f"/api/ask/jobs/{eligible_id}/context")
        check("context: 200", rc.status_code == 200)
        ctx = rc.json()
        check("context: guide present", ctx["guide"]["clean_md_present"] is True)
        check("context: guide char_count", ctx["guide"]["char_count"] == len(CLEAN_MD))
        check("context: guide heading_count", ctx["guide"]["heading_count"] == EXPECTED_HEADINGS)
        check("context: source present", ctx["source"]["extracted_txt_present"] is True)
        check("context: source char_count", ctx["source"]["char_count"] == len(EXTRACTED_TXT))
        check("context: page_anchor_count (3)", ctx["source"]["page_anchor_count"] == EXPECTED_PAGE_ANCHORS)

        atts = ctx.get("attachments", [])
        check("context: one attachment", len(atts) == 1)
        att = atts[0] if atts else {}
        check("context: attachment filename", att.get("filename") == "lecture.pdf")
        check("context: attachment mode", att.get("mode") == "pdf_mixed")
        check("context: attachment extracted_chars", att.get("extracted_chars") == 18799)
        check("context: attachment warnings", att.get("warnings") == ["page 4 OCR was low confidence"])
        check("context: page_selections present", ctx.get("page_selections") == {"lecture.pdf": [[1, 3]]})
        check("context: readiness ready=True", ctx["readiness"]["ready"] is True)
        check("context: readiness status ready", ctx["readiness"]["status"] == "ready")

        context_blob = rc.text

        # Context of a guide-less (but existing) job: 200, not_ready, no 404.
        rg = client.get(f"/api/ask/jobs/{guideless_id}/context")
        check("context: guide-less existing job -> 200", rg.status_code == 200)
        if rg.status_code == 200:
            gctx = rg.json()
            check("context: guide-less not_ready", gctx["readiness"]["ready"] is False)
            check("context: guide-less has reason", len(gctx["readiness"]["reasons"]) >= 1)

        # ── unknown job -> 404 (4) ──────────────────────────────────────────
        r404 = client.get("/api/ask/jobs/zzask-nonexistent-xyz/context")
        check("context: unknown id -> 404 (4)", r404.status_code == 404)

        # ── redaction / no-body proof (5) ───────────────────────────────────
        combined = list_blob + context_blob
        leaks = {
            "sk- key": "sk-" in combined,
            "raw api_key value": SECRET_KEY in combined,
            "api_key field": "api_key" in combined,
            "Authorization field": "Authorization" in combined,
            "full base URL scheme": "https://" in combined,
            "raw guide body": GUIDE_BODY_MARKER in combined,
            "raw source body": SOURCE_BODY_MARKER in combined,
            "filesystem input_path": "/home/secret" in combined,
        }
        for label, leaked in leaks.items():
            check(f"redaction: no {label} (5)", not leaked)

        # ── read-only proof (6) ─────────────────────────────────────────────
        check("readonly: clean.md unchanged (6)", _digest(eligible.clean_md) == digests["clean"])
        check("readonly: extracted.txt unchanged (6)", _digest(eligible.extracted_txt) == digests["extracted"])
        check("readonly: job.json unchanged (6)", _digest(eligible.manifest) == digests["manifest"])
    finally:
        for path in created:
            shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        test_pure_reader(Path(td))
    test_endpoints()

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
