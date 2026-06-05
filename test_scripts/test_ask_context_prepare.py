#!/usr/bin/env python3
"""Focused test for Ask Your Guide — Slice 3 backend context preparation.

Covers the chunking + lexical index + cache and the
``POST /api/ask/jobs/{job_id}/prepare`` endpoint WITHOUT any LLM provider,
model call, local-model call, or Chromium render:

  1. Preparing an eligible job builds a cache + returns ready with chunk counts.
  2. Guide chunk labels preserve the nearest markdown heading.
  3. Source chunks preserve ``## Page N`` anchors + page numbers.
  4. A second prepare without content changes is a cache HIT (no artifact/cache
     rewrite).
  5. Changing clean.md OR extracted.txt changes the content hash + rebuilds.
  6. Unknown job -> 404.
  7. Guide-less job is handled safely (200, ready:false, no crash).
  8. Cache corruption is handled by rebuilding, not crashing.
  9. No original artifact mutation: sha256 of clean.md / extracted.txt /
     job.json unchanged after prepare.
 10. Prepare response excludes raw guide/source body text, ``api_key``,
     ``Authorization``, ``sk-``, a full base URL (``https://``), and host paths.
 11. The cache/index file excludes raw secrets + unrelated manifest fields.
 12. No new dependency (pure stdlib import of the module).

The pure ``ask_context`` helpers are unit-tested directly; the endpoint portion
SKIPS cleanly if FastAPI/TestClient is unavailable. Run inside the Docker image
for full coverage.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

# Make the repo root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import ask_context  # noqa: E402
from pipeline.job_manager import Job  # noqa: E402

PASS = 0
FAIL = 0

SECRET_KEY = "sk-live-THIS_MUST_NEVER_LEAK_0123456789abcdef"
GUIDE_BODY_MARKER = "ZZZ_GUIDE_BODY_SECRET_PROSE_MARKER"
SOURCE_BODY_MARKER = "ZZZ_SOURCE_BODY_SECRET_PROSE_MARKER"

CLEAN_MD = (
    "# Study Guide\n\n"
    "Overview paragraph.\n\n"
    "## Backpropagation\n\n"
    f"{GUIDE_BODY_MARKER} the chain rule propagates gradients backward.\n\n"
    "## Summary\n\n"
    "Key points only.\n"
)
# Headings: "Study Guide", "Backpropagation", "Summary".
EXPECTED_GUIDE_LABELS = {"Study Guide", "Backpropagation", "Summary"}

EXTRACTED_TXT = (
    "## Page 1\n\n"
    f"{SOURCE_BODY_MARKER} lecture slide one introduces gradients.\n\n"
    "## Page 2\n\n"
    "lecture slide two covers the chain rule.\n\n"
    "## Page 3\n\n"
    "lecture slide three has a worked example.\n"
)
EXPECTED_PAGES = {1, 2, 3}


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


def test_pure_helpers(tmp: Path) -> None:
    """ask_context chunks deterministically, preserves labels, caches safely."""
    job = Job("prep-reader", root=tmp)
    job.dir.mkdir(parents=True, exist_ok=True)

    # Guide-less job -> not ready, no crash, nothing written.
    r0 = ask_context.prepare_context(job)
    check("pure: guide-less -> ready False", r0["ready"] is False)
    check("pure: guide-less wrote no cache", not ask_context._index_path(job).exists())

    job.clean_md.write_text(CLEAN_MD, encoding="utf-8")
    job.extracted_txt.write_text(EXTRACTED_TXT, encoding="utf-8")

    r1 = ask_context.prepare_context(job)
    check("pure: first prepare ready", r1["ready"] is True)
    check("pure: first prepare status built", r1["cache_status"] == "built")
    check("pure: guide chunks > 0", r1["guide_chunk_count"] >= 3)
    check("pure: source chunks > 0", r1["source_chunk_count"] >= 3)
    check(
        "pure: total == guide + source",
        r1["total_chunk_count"] == r1["guide_chunk_count"] + r1["source_chunk_count"],
    )

    index = ask_context.load_index(job)
    chunks = index["chunks"]

    # (2) guide labels preserve nearest heading.
    guide_labels = {c["label"] for c in chunks if c["source_type"] == "guide"}
    check("pure: guide labels are headings", EXPECTED_GUIDE_LABELS <= guide_labels)
    bp = next(
        c for c in chunks
        if c["source_type"] == "guide" and GUIDE_BODY_MARKER in c["text"]
    )
    check("pure: backprop chunk labelled by heading", bp["label"] == "Backpropagation")

    # (3) source chunks preserve page anchors + numbers.
    source_pages = {c["page"] for c in chunks if c["source_type"] == "source"}
    check("pure: source pages preserved", EXPECTED_PAGES <= source_pages)
    source_labels = {c["label"] for c in chunks if c["source_type"] == "source"}
    check("pure: source labels are 'Page N'", {"Page 1", "Page 2", "Page 3"} <= source_labels)

    # lexical index present + sane.
    check("pure: doc_freq present", isinstance(index["doc_freq"], dict) and index["doc_freq"])
    check(
        "pure: chunk terms are freq maps",
        all(isinstance(c["terms"], dict) for c in chunks),
    )
    check(
        "pure: approx_tokens ~ chars/4",
        all(c["approx_tokens"] == (c["char_count"] + 3) // 4 for c in chunks),
    )

    # (4) second prepare with no change -> cache HIT, cache bytes unchanged.
    cache_path = ask_context._index_path(job)
    before = _digest(cache_path)
    r2 = ask_context.prepare_context(job)
    check("pure: second prepare is hit", r2["cache_status"] == "hit")
    check("pure: hash stable across hit", r2["content_hash"] == r1["content_hash"])
    check("pure: cache file unchanged on hit", _digest(cache_path) == before)

    # (5) change guide -> hash changes + rebuild.
    job.clean_md.write_text(CLEAN_MD + "\n## Extra\n\nmore content here.\n", encoding="utf-8")
    r3 = ask_context.prepare_context(job)
    check("pure: guide change rebuilds", r3["cache_status"] == "rebuilt")
    check("pure: guide change new hash", r3["content_hash"] != r1["content_hash"])

    # (5b) change source -> hash changes + rebuild.
    h_before_src = r3["content_hash"]
    job.extracted_txt.write_text(EXTRACTED_TXT + "\n## Page 4\n\nslide four.\n", encoding="utf-8")
    r4 = ask_context.prepare_context(job)
    check("pure: source change rebuilds", r4["cache_status"] == "rebuilt")
    check("pure: source change new hash", r4["content_hash"] != h_before_src)

    # (8) corrupt cache -> rebuild, not crash.
    cache_path.write_text("{ this is not valid json", encoding="utf-8")
    r5 = ask_context.prepare_context(job)
    check("pure: corrupt cache rebuilds", r5["cache_status"] == "rebuilt")
    check("pure: corrupt cache recovered ready", r5["ready"] is True)

    # (11) cache file has no secret / unrelated manifest fields.
    cache_blob = cache_path.read_text(encoding="utf-8")
    check("pure: cache has no sk- key", "sk-" not in cache_blob)
    check("pure: cache has no api_key field", "api_key" not in cache_blob)
    cache_obj = json.loads(cache_blob)
    allowed = {
        "kind", "version", "job_id", "content_hash", "built_at",
        "guide_present", "source_present", "guide_chunk_count",
        "source_chunk_count", "total_chunk_count", "doc_freq",
        "citation_summary", "chunks",
    }
    check("pure: cache top-level keys whitelisted", set(cache_obj.keys()) <= allowed)

    # (11b) content hash is content-derived (recompute matches).
    recomputed = ask_context.compute_content_hash(
        job.clean_md.read_text(encoding="utf-8"),
        job.extracted_txt.read_text(encoding="utf-8"),
    )
    check("pure: content_hash reproducible", recomputed == r5["content_hash"])

    # cache stays inside the job dir.
    check(
        "pure: cache under job/ask/cache",
        cache_path.resolve().is_relative_to(job.dir.resolve())
        and cache_path.parent.name == "cache",
    )


def test_endpoint() -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception as exc:  # pragma: no cover
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

    eligible_id = "zzprep-eligible"
    guideless_id = "zzprep-guideless"
    created: list[Path] = []
    digests: dict[str, str | None] = {}

    def make(job_id: str, *, with_guide: bool, status: str) -> Job:
        job = Job(job_id)
        job.input_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "id": job_id,
            "status": status,
            "title": f"Guide {job_id}",
            "created_at": "2026-06-05T10:00:00",
            "provider": "deepseek",
            "model": "deepseek-chat",
            # Planted secrets/paths that must never surface.
            "api_key": SECRET_KEY,
            "Authorization": f"Bearer {SECRET_KEY}",
            "base_url": "https://api.deepseek.com/v1",
            "input_path": "/home/secret/jobs/input/lecture.pdf",
            "attachments": [{"filename": "lecture.pdf", "api_key": SECRET_KEY}],
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

        digests["clean"] = _digest(eligible.clean_md)
        digests["extracted"] = _digest(eligible.extracted_txt)
        digests["manifest"] = _digest(eligible.manifest)

        # (1) eligible -> 200 ready + built, with chunk counts.
        r = client.post(f"/api/ask/jobs/{eligible_id}/prepare")
        check("ep: eligible 200", r.status_code == 200)
        body = r.json()
        check("ep: ready True", body.get("ready") is True)
        check("ep: cache_status built", body.get("cache_status") == "built")
        check("ep: job_id echoed", body.get("job_id") == eligible_id)
        check("ep: guide chunk count >=3", body.get("guide_chunk_count", 0) >= 3)
        check("ep: source chunk count >=3", body.get("source_chunk_count", 0) >= 3)
        check(
            "ep: total == guide+source",
            body.get("total_chunk_count")
            == body.get("guide_chunk_count", 0) + body.get("source_chunk_count", 0),
        )
        # (2/3) citation summary carries headings + pages.
        summary = body.get("citation_summary", {})
        check(
            "ep: citation guide headings",
            EXPECTED_GUIDE_LABELS <= set(summary.get("guide", {}).get("headings_sample", [])),
        )
        check(
            "ep: citation source pages",
            EXPECTED_PAGES <= set(summary.get("source", {}).get("page_numbers_sample", [])),
        )
        check("ep: cache_relpath job-relative", body.get("cache_relpath") == ask_context.CACHE_RELPATH)
        first_hash = body.get("content_hash")

        # (4) second prepare -> hit, no artifact rewrite.
        r2 = client.post(f"/api/ask/jobs/{eligible_id}/prepare")
        check("ep: second prepare 200", r2.status_code == 200)
        check("ep: second prepare hit", r2.json().get("cache_status") == "hit")
        check("ep: hash stable", r2.json().get("content_hash") == first_hash)

        # (5) content change -> rebuild + new hash.
        eligible.clean_md.write_text(CLEAN_MD + "\n## More\n\nextra body.\n", encoding="utf-8")
        r3 = client.post(f"/api/ask/jobs/{eligible_id}/prepare")
        check("ep: change -> rebuilt", r3.json().get("cache_status") == "rebuilt")
        check("ep: change -> new hash", r3.json().get("content_hash") != first_hash)
        # restore original guide so the immutability digest below matches.
        eligible.clean_md.write_text(CLEAN_MD, encoding="utf-8")
        client.post(f"/api/ask/jobs/{eligible_id}/prepare")

        # (6) unknown job -> 404.
        r404 = client.post("/api/ask/jobs/zzprep-nonexistent/prepare")
        check("ep: unknown -> 404", r404.status_code == 404)

        # (7) guide-less existing job -> 200 not-ready, no crash.
        rg = client.post(f"/api/ask/jobs/{guideless_id}/prepare")
        check("ep: guide-less 200", rg.status_code == 200)
        check("ep: guide-less ready False", rg.json().get("ready") is False)

        # (10) redaction / no-body proof on the prepare response.
        blob = r.text + r3.text
        leaks = {
            "sk- key": "sk-" in blob,
            "raw api_key value": SECRET_KEY in blob,
            "api_key field": "api_key" in blob,
            "Authorization field": "Authorization" in blob,
            "full base URL scheme": "https://" in blob,
            "raw guide body": GUIDE_BODY_MARKER in blob,
            "raw source body": SOURCE_BODY_MARKER in blob,
            "filesystem input_path": "/home/secret" in blob,
            "chunk text field": '"text"' in blob,
        }
        for label, leaked in leaks.items():
            check(f"ep: response has no {label} (10)", not leaked)

        # (9) immutability of original artifacts.
        check("ep: clean.md unchanged (9)", _digest(eligible.clean_md) == digests["clean"])
        check("ep: extracted.txt unchanged (9)", _digest(eligible.extracted_txt) == digests["extracted"])
        check("ep: job.json unchanged (9)", _digest(eligible.manifest) == digests["manifest"])
    finally:
        for path in created:
            shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        test_pure_helpers(Path(td))
    test_endpoint()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
