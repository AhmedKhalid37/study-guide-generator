#!/usr/bin/env python3
"""Focused test for the PDF page-selection request plumbing (Slice 3).

Covers `_normalize_page_selections` + the request/manifest plumbing for the
optional `page_selections` field on `POST /api/jobs/llm` (BOTH the JSON body and
the multipart/form-data path, per the DECISIONS.md "wire new fields into both
paths" rule), and that retry preserves the stored selection.

The LLM call and the Chromium renderer are STUBBED (no provider keys, no network,
no browser), so this runs offline/deterministically. It only asserts that page
selections are validated, normalized, persisted to the manifest, echoed by
`job_response`, and round-tripped through retry — extraction is intentionally NOT
exercised (Slice 3 does not filter pages).

SKIPS cleanly (exit 0) if FastAPI's TestClient is unavailable.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0
FAIL = 0


def check(label: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}")


def _skip(msg: str) -> None:
    print(f"[SKIP] {msg}")
    sys.exit(0)


try:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
except Exception as exc:  # pragma: no cover - depends on environment
    _skip(f"FastAPI TestClient unavailable: {exc}")

import api.server as server
from pipeline.job_manager import Job


# ── 1. _normalize_page_selections (pure validation/normalization) ────────────

def test_normalize() -> None:
    norm = server._normalize_page_selections
    check("empty/None -> {}", norm(None) == {} and norm({}) == {})
    check(
        "valid ranges kept (sorted)",
        norm({"a.pdf": [[35, 42], [1, 20]]}) == {"a.pdf": [[1, 20], [35, 42]]},
    )
    check(
        "overlapping/adjacent merged",
        norm({"a.pdf": [[1, 5], [4, 8], [9, 10], [20, 25]]}) == {"a.pdf": [[1, 10], [20, 25]]},
    )
    check("empty range list -> file dropped", norm({"a.pdf": []}) == {})

    def rejects(value) -> bool:
        try:
            norm(value)
            return False
        except HTTPException as exc:
            return exc.status_code == 400

    check("non-dict top level -> 400", rejects([[1, 2]]))
    check("non-list ranges -> 400", rejects({"a.pdf": "1-20"}))
    check("triple instead of pair -> 400", rejects({"a.pdf": [[1, 2, 3]]}))
    check("non-int page -> 400", rejects({"a.pdf": [[1, "x"]]}))
    check("bool page -> 400", rejects({"a.pdf": [[True, 2]]}))
    check("start < 1 -> 400", rejects({"a.pdf": [[0, 5]]}))
    check("end < start -> 400", rejects({"a.pdf": [[10, 5]]}))


# ── 2. endpoint plumbing (LLM + renderer stubbed) ────────────────────────────

class _DummyConfig:
    provider = "deepseek"
    model = "stub-model"
    base_url = None


def _install_stubs(monkeypatch_targets: list) -> None:
    """Replace the network/browser-bound functions with deterministic stubs and
    record originals for restore."""
    def fake_build_provider_config(*_args, **_kwargs):
        return _DummyConfig()

    def fake_generate(*_args, **_kwargs):
        return "## Stub\n\nGenerated offline for the page-selection test.\n"

    def fake_render(job, *_args, **_kwargs):
        # Skip Chromium; mark the job done so job_response is happy.
        job.set_status("done")
        return job

    def fake_validate_pm(*_args, **_kwargs):
        return None

    monkeypatch_targets.append((server, "build_provider_config", server.build_provider_config))
    monkeypatch_targets.append((server, "_validate_provider_model", server._validate_provider_model))
    import pipeline.run_llm_job as rlj
    import pipeline.run_markdown_job as rmj
    monkeypatch_targets.append((rlj, "generate_study_guide", rlj.generate_study_guide))
    monkeypatch_targets.append((rlj, "run_raw_markdown_pipeline", rlj.run_raw_markdown_pipeline))
    monkeypatch_targets.append((server, "generate_study_guide", server.generate_study_guide))
    monkeypatch_targets.append((rmj, "run_raw_markdown_pipeline", rmj.run_raw_markdown_pipeline))

    server.build_provider_config = fake_build_provider_config
    server._validate_provider_model = fake_validate_pm
    rlj.generate_study_guide = fake_generate
    rlj.run_raw_markdown_pipeline = fake_render
    server.generate_study_guide = fake_generate
    rmj.run_raw_markdown_pipeline = fake_render


def _restore(monkeypatch_targets: list) -> None:
    for obj, name, original in reversed(monkeypatch_targets):
        setattr(obj, name, original)


def _base_payload() -> dict:
    return {
        "source_text": "Some source material about thermodynamics.",
        "title": "PS Test Guide",
        "provider": "deepseek",
        "model": "stub-model",
        "theme": "claude_clean",
    }


def _manifest_selection(job_id: str) -> dict:
    return Job(job_id).read_manifest().get("page_selections")


def test_endpoint() -> None:
    targets: list = []
    _install_stubs(targets)
    created_ids: list[str] = []
    try:
        client = TestClient(server.app)

        # JSON path with valid selections -> persists (normalized) to manifest.
        payload = {**_base_payload(), "page_selections": {"deck.pdf": [[35, 42], [1, 20]]}}
        resp = client.post("/api/jobs/llm", json=payload)
        check("JSON path -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("JSON path -> response echoes selection", resp.json().get("page_selections") == {"deck.pdf": [[1, 20], [35, 42]]})
        check("JSON path -> manifest persisted selection", _manifest_selection(jid) == {"deck.pdf": [[1, 20], [35, 42]]})

        # Multipart path with valid selections (JSON string) -> persists.
        files = {"attachments": ("note.txt", b"extra source text", "text/plain")}
        data = {**_base_payload(), "page_selections": '{"deck.pdf": [[1, 10]]}'}
        resp = client.post("/api/jobs/llm", data=data, files=files)
        check("multipart path -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("multipart path -> manifest persisted selection", _manifest_selection(jid) == {"deck.pdf": [[1, 10]]})

        # Default path (no page_selections) -> empty, behaviour unchanged.
        resp = client.post("/api/jobs/llm", json=_base_payload())
        check("default path -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("default path -> response selection {}", resp.json().get("page_selections") == {})
        check("default path -> manifest selection {}", _manifest_selection(jid) == {})

        # Invalid shape (JSON path) -> safe 400, no job created.
        bad = {**_base_payload(), "page_selections": {"deck.pdf": [[10, 5]]}}
        resp = client.post("/api/jobs/llm", json=bad)
        check("invalid selection -> 400", resp.status_code == 400)

        # Invalid top-level type via Pydantic (list, not object) -> 400.
        bad2 = {**_base_payload(), "page_selections": [[1, 2]]}
        resp = client.post("/api/jobs/llm", json=bad2)
        check("invalid selection type -> 400", resp.status_code == 400)

        # Retry preserves the stored selection from the manifest.
        retry_payload = {**_base_payload(), "page_selections": {"deck.pdf": [[2, 9]]}}
        resp = client.post("/api/jobs/llm", json=retry_payload)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        job = Job(jid)
        job.set_status("failed", "forced for retry test")
        resp = client.post(f"/api/jobs/{jid}/retry")
        check("retry -> 200", resp.status_code == 200)
        check("retry preserves selection in manifest", _manifest_selection(jid) == {"deck.pdf": [[2, 9]]})
        check("retry response echoes selection", resp.json().get("page_selections") == {"deck.pdf": [[2, 9]]})
    finally:
        _restore(targets)
        # Best-effort cleanup of the throwaway jobs we created.
        import shutil
        for jid in created_ids:
            if jid:
                shutil.rmtree(Job(jid).dir, ignore_errors=True)


if __name__ == "__main__":
    test_normalize()
    test_endpoint()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
