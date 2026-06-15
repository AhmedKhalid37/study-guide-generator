#!/usr/bin/env python3
"""Focused test for Slice 99 dual-explanation request plumbing + persistence.

Covers the NEW optional ``dual_explanation_mode`` boolean on ``POST /api/jobs/llm``
across BOTH request-construction paths (JSON body AND multipart/form-data, per the
DECISIONS.md "wire new fields into both paths" rule), that the flag is persisted in
the job manifest, that the generation prompt gains the ``## Dual Explanation Mode``
block only when enabled (byte-equivalent default otherwise), and that invalid /
hostile values never leak a raw string into the manifest or the generation source.

The LLM call and the Chromium renderer are STUBBED (no provider keys, no network,
no browser); the stub also captures the augmented generation source so the prompt
block can be asserted. SKIPS cleanly (exit 0) if FastAPI's TestClient is unavailable.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        print(f"[FAIL] {label}{(' - ' + detail) if detail else ''}")


def _skip(msg: str) -> None:
    print(f"[SKIP] {msg}")
    sys.exit(0)


try:
    from fastapi.testclient import TestClient
except Exception as exc:  # pragma: no cover - depends on environment
    _skip(f"FastAPI TestClient unavailable: {exc}")

import api.server as server
from pipeline.job_manager import Job

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
HOSTILE_CANARY = "boom-canary-string-sk_dualexplanation1234567890"

# Captured augmented source passed to the (stubbed) generator, latest call last.
CAPTURED_SOURCES: list[str] = []


class _DummyConfig:
    provider = "deepseek"
    model = "stub-model"
    base_url = None


def _install_stubs(targets: list) -> None:
    def fake_build_provider_config(*_a, **_k):
        return _DummyConfig()

    def fake_generate(source_text="", *_a, **_k):
        CAPTURED_SOURCES.append(source_text)
        return "## Stub\n\nGenerated offline for the dual-explanation test.\n"

    def fake_render(job, *_a, **_k):
        job.set_status("done")
        return job

    def fake_validate_pm(*_a, **_k):
        return None

    import pipeline.run_llm_job as rlj
    import pipeline.run_markdown_job as rmj
    targets.append((server, "build_provider_config", server.build_provider_config))
    targets.append((server, "_validate_provider_model", server._validate_provider_model))
    targets.append((rlj, "generate_study_guide", rlj.generate_study_guide))
    targets.append((rlj, "run_raw_markdown_pipeline", rlj.run_raw_markdown_pipeline))
    targets.append((server, "generate_study_guide", server.generate_study_guide))
    targets.append((rmj, "run_raw_markdown_pipeline", rmj.run_raw_markdown_pipeline))

    server.build_provider_config = fake_build_provider_config
    server._validate_provider_model = fake_validate_pm
    rlj.generate_study_guide = fake_generate
    rlj.run_raw_markdown_pipeline = fake_render
    server.generate_study_guide = fake_generate
    rmj.run_raw_markdown_pipeline = fake_render


def _restore(targets: list) -> None:
    for obj, name, original in reversed(targets):
        setattr(obj, name, original)


def _base_payload() -> dict:
    return {
        "source_text": "Some source material about thermodynamics.",
        "title": "Dual Explanation Test Guide",
        "provider": "deepseek",
        "model": "stub-model",
        "theme": "claude_clean",
    }


def _manifest(job_id: str) -> dict:
    return Job(job_id).read_manifest()


def _last_source() -> str:
    return CAPTURED_SOURCES[-1] if CAPTURED_SOURCES else ""


def _has_dual_block(text: str) -> bool:
    return (
        "## Dual Explanation Mode" in text
        and "Explain it simply:" in text
        and "Exam answer:" in text
    )


def test_endpoint() -> None:
    targets: list = []
    _install_stubs(targets)
    created_ids: list[str] = []
    try:
        client = TestClient(server.app)

        # ── JSON path, enabled: persisted True + prompt block present. ──
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "dual_explanation_mode": True})
        check("JSON enabled -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("JSON enabled -> manifest True", _manifest(jid).get("dual_explanation_mode") is True)
        check("JSON enabled -> prompt block present", _has_dual_block(_last_source()))
        check("JSON enabled -> no clean.md written by our wiring", not Job(jid).clean_md.exists())

        # ── JSON path, explicit false: persisted False + no prompt block. ──
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "dual_explanation_mode": False})
        check("JSON false -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("JSON false -> manifest False", _manifest(jid).get("dual_explanation_mode") is False)
        check("JSON false -> no prompt block", "## Dual Explanation Mode" not in _last_source())

        # ── JSON path, absent: defaults False + byte-equivalent (no block). ──
        resp = client.post("/api/jobs/llm", json=_base_payload())
        check("JSON absent -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("JSON absent -> manifest defaults False", _manifest(jid).get("dual_explanation_mode") is False)
        absent_source = _last_source()
        check("JSON absent -> no prompt block", "## Dual Explanation Mode" not in absent_source)
        check("JSON absent -> source byte-equivalent to base source_text",
              absent_source == _base_payload()["source_text"])

        # ── Multipart path, enabled (string "true") with an attachment. ──
        files = {"attachments": ("note.txt", b"extra source text", "text/plain")}
        data = {**_base_payload(), "dual_explanation_mode": "true"}
        resp = client.post("/api/jobs/llm", data=data, files=files)
        check("multipart enabled -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("multipart enabled -> manifest True", _manifest(jid).get("dual_explanation_mode") is True)
        check("multipart enabled -> prompt block present", _has_dual_block(_last_source()))

        # ── Multipart path, hostile string: coerced to False, never stored raw. ──
        data = {**_base_payload(), "dual_explanation_mode": HOSTILE_CANARY}
        resp = client.post("/api/jobs/llm", data=data, files={"attachments": ("n.txt", b"x", "text/plain")})
        check("multipart hostile -> 200 (degrade)", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        stored = _manifest(jid).get("dual_explanation_mode")
        check("multipart hostile -> coerced False", stored is False)
        check("multipart hostile -> no raw string in manifest",
              HOSTILE_CANARY not in json.dumps(_manifest(jid), sort_keys=True))
        check("multipart hostile -> no prompt block", "## Dual Explanation Mode" not in _last_source())

        # ── JSON path, invalid (non-bool) value: rejected, not persisted, no raw
        #    string echoed. The endpoint maps the pydantic validation error to a
        #    generic 400 ("Invalid LLM job request."); a 422 would be equally valid.
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "dual_explanation_mode": HOSTILE_CANARY})
        check("JSON invalid -> rejected (400/422) not persisted", resp.status_code in (400, 422))
        body = resp.text
        check("JSON invalid -> raw hostile string not echoed", HOSTILE_CANARY not in body)
        check("JSON invalid -> no keylike/path/url leak in error",
              not KEYLIKE.search(body) and not PATHLIKE.search(body) and not URLLIKE.search(body))

        # ── Existing visual-pilot opt-in unaffected (independent boolean). ──
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "dual_explanation_mode": True})
        check("co-exist -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        m = _manifest(jid)
        check("co-exist -> dual True", m.get("dual_explanation_mode") is True)
        check("co-exist -> visual pilot default False", m.get("visual_markdown_image_pilot") is False)
    finally:
        _restore(targets)
        for jid in created_ids:
            if jid:
                shutil.rmtree(Job(jid).dir, ignore_errors=True)


def main() -> int:
    test_endpoint()
    print(f"\nDual explanation request tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
