#!/usr/bin/env python3
"""Focused test for Full Material Coverage page/slide selection persistence (Slice 79).

Covers `_normalize_material_page_selection` + the request/manifest plumbing for the
NEW optional `material_page_selection` field on `POST /api/jobs/llm` (BOTH the JSON
body and the multipart/form-data path, per the DECISIONS.md "wire new fields into
both paths" rule), and that retry preserves the stored normalized model.

This field is DISTINCT from the load-bearing, filename-keyed `page_selections` PDF
page-range field; this test also asserts that existing `page_selections` behaviour
(normalization, 400 on bad shapes, manifest persistence) is unchanged.

The LLM call and the Chromium renderer are STUBBED (no provider keys, no network,
no browser), so this runs offline/deterministically. Extraction is intentionally
NOT exercised — Slice 79 persists the model but applies it to nothing.

SKIPS cleanly (exit 0) if FastAPI's TestClient is unavailable.
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
    from fastapi.testclient import TestClient
except Exception as exc:  # pragma: no cover - depends on environment
    _skip(f"FastAPI TestClient unavailable: {exc}")

import api.server as server
from pipeline.job_manager import Job

# Leak-detection regexes + synthetic canaries fed into the field to prove none are
# ever copied into the persisted manifest or the API response.
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|C:\\|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_materialselectioncanary1234567890",
    "/home/example/private-source.pdf",
]


def _no_leak(label: str, obj) -> None:
    blob = json.dumps(obj, sort_keys=True)
    check(f"{label}: no keylike", not KEYLIKE.search(blob))
    check(f"{label}: no pathlike", not PATHLIKE.search(blob))
    check(f"{label}: no urllike", not URLLIKE.search(blob))
    check(f"{label}: no data/base64", not DATA_OR_BASE64.search(blob))
    check(f"{label}: no argv/socket", not ARGV_OR_SOCKET.search(blob))
    for canary in FORBIDDEN_CANARIES:
        check(f"{label}: no canary {canary!r}", canary not in blob)


# ── 1. _normalize_material_page_selection (degrade-never-fail) ───────────────

def test_normalize_helper() -> None:
    norm = server._normalize_material_page_selection
    absent = norm(None)
    check("None -> mode all", absent["mode"] == "all")
    check("None -> no warnings", absent["warnings"] == [])
    check("None -> shape", set(absent) == {"version", "mode", "include_pages", "exclude_pages", "warnings"})

    valid = norm({"mode": "include", "include_pages": [3, 1, 2, 2]})
    check("valid include normalized/sorted/deduped", valid["include_pages"] == [1, 2, 3])
    check("valid include mode", valid["mode"] == "include")

    # Malformed *content* degrades safely with closed warnings (never raises/400).
    bad_list = norm({"mode": "include", "include_pages": "1,2,3"})
    check("malformed pages -> empty", bad_list["include_pages"] == [])
    check("malformed pages -> selection_malformed", "selection_malformed" in bad_list["warnings"])

    unknown = norm({"mode": "bogus"})
    check("unknown mode -> all", unknown["mode"] == "all")
    check("unknown mode -> mode_unknown", "mode_unknown" in unknown["warnings"])

    invalid_pages = norm({"mode": "include", "include_pages": [1, 0, -2, "x", 2]})
    check("invalid pages dropped", invalid_pages["include_pages"] == [1, 2])
    check("invalid pages -> page_invalid", "page_invalid" in invalid_pages["warnings"])

    # Hostile canary content must never survive into the normalized output.
    hostile = norm(
        {
            "mode": "/home/example/private-source.pdf",
            "include_pages": ["assets/secret.png", "raw OCR dump", 1],
            "exclude_pages": ["table cell text", 2],
            "note": "sk_materialselectioncanary1234567890",
        }
    )
    _no_leak("helper hostile", hostile)


# ── 2. endpoint plumbing (LLM + renderer stubbed) ────────────────────────────

class _DummyConfig:
    provider = "deepseek"
    model = "stub-model"
    base_url = None


def _install_stubs(targets: list) -> None:
    def fake_build_provider_config(*_a, **_k):
        return _DummyConfig()

    def fake_generate(*_a, **_k):
        return "## Stub\n\nGenerated offline for the material-selection test.\n"

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
        "title": "Material PS Test Guide",
        "provider": "deepseek",
        "model": "stub-model",
        "theme": "claude_clean",
    }


def _manifest(job_id: str) -> dict:
    return Job(job_id).read_manifest()


def test_endpoint() -> None:
    targets: list = []
    _install_stubs(targets)
    created_ids: list[str] = []
    try:
        client = TestClient(server.app)

        # ── JSON path: new field accepted, normalized, persisted, echoed. ──
        sel = {"mode": "include", "include_pages": [3, 1, 2], "exclude_pages": [2]}
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "material_page_selection": sel})
        check("JSON path -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        stored = _manifest(jid).get("material_page_selection")
        check("JSON path -> manifest persisted normalized model",
              stored == {"version": 1, "mode": "include", "include_pages": [1, 2, 3],
                         "exclude_pages": [2], "warnings": ["exclude_overlaps_include"]})
        echo = resp.json().get("material_page_selection")
        check("JSON path -> response echoes mode", echo and echo.get("mode") == "include")
        check("JSON path -> response echoes include", echo.get("include_pages") == [1, 2, 3])
        # The existing page_selections field still defaults to {} and is unaffected.
        check("JSON path -> page_selections still {}", resp.json().get("page_selections") == {})
        # No clean.md was written (render stubbed) — our change adds no clean.md write.
        check("JSON path -> no clean.md written by our wiring", not Job(jid).clean_md.exists())

        # ── Multipart path: new field rides as a JSON string. ──
        files = {"attachments": ("note.txt", b"extra source text", "text/plain")}
        data = {**_base_payload(), "material_page_selection": '{"mode": "exclude", "exclude_pages": [5, 4]}'}
        resp = client.post("/api/jobs/llm", data=data, files=files)
        check("multipart path -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        stored = _manifest(jid).get("material_page_selection")
        check("multipart path -> manifest persisted normalized model",
              stored == {"version": 1, "mode": "exclude", "include_pages": [],
                         "exclude_pages": [4, 5], "warnings": []})

        # ── Absent field: default normalized "all", no warnings; behaviour intact. ──
        resp = client.post("/api/jobs/llm", json=_base_payload())
        check("absent -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        stored = _manifest(jid).get("material_page_selection")
        check("absent -> manifest default all",
              stored == {"version": 1, "mode": "all", "include_pages": [],
                         "exclude_pages": [], "warnings": []})
        check("absent -> page_selections still {}", _manifest(jid).get("page_selections") == {})

        # ── Malformed content degrades safely (200, closed warnings) — NOT a 400. ──
        bad = {**_base_payload(), "material_page_selection": {"mode": "bogus", "include_pages": "1,2"}}
        resp = client.post("/api/jobs/llm", json=bad)
        check("malformed content -> 200 (degrade, not 400)", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        stored = _manifest(jid).get("material_page_selection")
        check("malformed content -> mode all", stored["mode"] == "all")
        check("malformed content -> mode_unknown warning", "mode_unknown" in stored["warnings"])
        check("malformed content -> selection_malformed warning", "selection_malformed" in stored["warnings"])

        # ── Multipart with invalid JSON string -> degrades to default all. ──
        data = {**_base_payload(), "material_page_selection": "{not valid json"}
        resp = client.post("/api/jobs/llm", data=data, files={"attachments": ("n.txt", b"x", "text/plain")})
        check("multipart bad-json -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("multipart bad-json -> default all",
              _manifest(jid).get("material_page_selection")["mode"] == "all")

        # ── Existing page_selections behaviour preserved: valid + invalid. ──
        resp = client.post("/api/jobs/llm", json={**_base_payload(),
                                                  "page_selections": {"deck.pdf": [[35, 42], [1, 20]]}})
        check("page_selections valid -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("page_selections still normalized/persisted",
              _manifest(jid).get("page_selections") == {"deck.pdf": [[1, 20], [35, 42]]})
        resp = client.post("/api/jobs/llm", json={**_base_payload(),
                                                  "page_selections": {"deck.pdf": [[10, 5]]}})
        check("page_selections invalid still -> 400", resp.status_code == 400)

        # ── No-leak: hostile canary content never persists or echoes. ──
        hostile = {
            "mode": "/home/example/private-source.pdf",
            "include_pages": ["assets/secret.png", "raw OCR dump", 1],
            "exclude_pages": ["table cell text", 2],
            "note": "sk_materialselectioncanary1234567890",
        }
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "material_page_selection": hostile})
        check("hostile -> 200 (degrade)", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        _no_leak("hostile manifest", _manifest(jid).get("material_page_selection"))
        _no_leak("hostile response", resp.json().get("material_page_selection"))

        # ── Retry preserves the stored normalized model. ──
        sel = {"mode": "include", "include_pages": [2, 9]}
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "material_page_selection": sel})
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        Job(jid).set_status("failed", "forced for retry test")
        resp = client.post(f"/api/jobs/{jid}/retry")
        check("retry -> 200", resp.status_code == 200)
        check("retry preserves material selection in manifest",
              _manifest(jid).get("material_page_selection") ==
              {"version": 1, "mode": "include", "include_pages": [2, 9],
               "exclude_pages": [], "warnings": []})
        check("retry response echoes material selection",
              resp.json().get("material_page_selection", {}).get("include_pages") == [2, 9])
    finally:
        _restore(targets)
        for jid in created_ids:
            if jid:
                shutil.rmtree(Job(jid).dir, ignore_errors=True)


# ── 3. per-attachment material_page_selections helper (Slice 80) ─────────────

def test_per_attachment_helper() -> None:
    norm = server._normalize_material_page_selections

    absent = norm(None)
    check("per-attach None -> empty envelope",
          absent == {"version": 1, "attachments": {}, "warnings": []})

    non_dict = norm(["not", "a", "dict"])
    check("per-attach non-dict -> empty + selections_malformed",
          non_dict == {"version": 1, "attachments": {}, "warnings": ["selections_malformed"]})

    flat = norm({
        "attachment_1": {"mode": "exclude", "exclude_pages": [4, 3]},
        "attachment_0": {"mode": "include", "include_pages": [2, 1]},
    })
    check("per-attach keys sorted by index",
          list(flat["attachments"].keys()) == ["attachment_0", "attachment_1"])
    check("per-attach entry normalized",
          flat["attachments"]["attachment_1"] ==
          {"version": 1, "mode": "exclude", "include_pages": [], "exclude_pages": [3, 4], "warnings": []})
    check("per-attach no top-level warnings", flat["warnings"] == [])

    # Envelope input round-trips (retry re-normalization path).
    round_trip = norm(flat)
    check("per-attach envelope round-trips", round_trip == flat)

    # Unsafe / filename / path keys are dropped with a closed warning, and the
    # offending key never appears in the output.
    unsafe = norm({
        "attachment_0": {"mode": "all"},
        "private-source.pdf": {"mode": "exclude", "exclude_pages": [1]},
        "/home/example/x": {"mode": "include", "include_pages": [1]},
        "title text": {"mode": "all"},
    })
    check("per-attach safe key kept", list(unsafe["attachments"].keys()) == ["attachment_0"])
    check("per-attach unsafe keys -> attachment_key_invalid",
          unsafe["warnings"] == ["attachment_key_invalid"])
    _no_leak("per-attach unsafe keys", unsafe)

    # Malformed entry value under a valid key degrades via the pure model.
    malformed_entry = norm({"attachment_0": "1,2,3", "attachment_1": {"mode": "bogus"}})
    check("per-attach malformed value -> selection_malformed",
          "selection_malformed" in malformed_entry["attachments"]["attachment_0"]["warnings"])
    check("per-attach unknown mode -> mode_unknown",
          "mode_unknown" in malformed_entry["attachments"]["attachment_1"]["warnings"])

    # Zero-padded / duplicate-index keys canonicalize.
    padded = norm({"attachment_00": {"mode": "all"}, "attachment_2": {"mode": "all"}})
    check("per-attach zero-pad canonicalized",
          list(padded["attachments"].keys()) == ["attachment_0", "attachment_2"])

    # Hostile canary values never survive normalization.
    hostile = norm({
        "attachment_0": {
            "mode": "/home/example/private-source.pdf",
            "include_pages": ["assets/secret.png", "raw OCR dump", 1],
            "exclude_pages": ["table cell text", 2],
            "note": "sk_materialselectioncanary1234567890",
        },
    })
    _no_leak("per-attach hostile entry", hostile)


# ── 4. per-attachment endpoint plumbing (Slice 80) ───────────────────────────

def test_per_attachment_endpoint() -> None:
    targets: list = []
    _install_stubs(targets)
    created_ids: list[str] = []
    try:
        client = TestClient(server.app)

        # JSON path: per-attachment selections normalized + persisted as envelope.
        sels = {"attachment_0": {"mode": "include", "include_pages": [3, 1, 2]},
                "attachment_1": {"mode": "exclude", "exclude_pages": [5]}}
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "material_page_selections": sels})
        check("per-attach JSON -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        stored = _manifest(jid).get("material_page_selections")
        check("per-attach JSON -> manifest envelope",
              stored == {"version": 1, "warnings": [], "attachments": {
                  "attachment_0": {"version": 1, "mode": "include", "include_pages": [1, 2, 3],
                                   "exclude_pages": [], "warnings": []},
                  "attachment_1": {"version": 1, "mode": "exclude", "include_pages": [],
                                   "exclude_pages": [5], "warnings": []}}})
        echo = resp.json().get("material_page_selections")
        check("per-attach JSON -> response echoes envelope", echo == stored)
        # Slice 79 top-level still defaults; page_selections untouched.
        check("per-attach JSON -> top-level material default all",
              resp.json().get("material_page_selection", {}).get("mode") == "all")
        check("per-attach JSON -> page_selections still {}", resp.json().get("page_selections") == {})
        check("per-attach JSON -> no clean.md written", not Job(jid).clean_md.exists())

        # Multipart path: per-attachment rides as a JSON string.
        files = {"attachments": ("note.txt", b"extra source text", "text/plain")}
        data = {**_base_payload(),
                "material_page_selections": '{"attachment_0": {"mode": "exclude", "exclude_pages": [2]}}'}
        resp = client.post("/api/jobs/llm", data=data, files=files)
        check("per-attach multipart -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("per-attach multipart -> manifest persisted",
              _manifest(jid)["material_page_selections"]["attachments"]["attachment_0"]["exclude_pages"] == [2])

        # Both top-level and per-attachment supplied -> both persisted.
        resp = client.post("/api/jobs/llm", json={**_base_payload(),
                                                  "material_page_selection": {"mode": "include", "include_pages": [1]},
                                                  "material_page_selections": {"attachment_0": {"mode": "exclude", "exclude_pages": [9]}}})
        check("both fields -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("both fields -> top-level persisted",
              _manifest(jid)["material_page_selection"]["include_pages"] == [1])
        check("both fields -> per-attachment persisted",
              _manifest(jid)["material_page_selections"]["attachments"]["attachment_0"]["exclude_pages"] == [9])

        # Absent per-attachment -> empty envelope; Slice 79 behaviour preserved.
        resp = client.post("/api/jobs/llm", json=_base_payload())
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("absent per-attach -> empty envelope",
              _manifest(jid).get("material_page_selections") == {"version": 1, "attachments": {}, "warnings": []})
        check("absent per-attach -> top-level still default all",
              _manifest(jid)["material_page_selection"]["mode"] == "all")
        check("absent per-attach -> page_selections still {}", _manifest(jid).get("page_selections") == {})

        # Unsafe / filename keys ignored (NOT persisted), closed warning recorded.
        resp = client.post("/api/jobs/llm", json={**_base_payload(),
                                                  "material_page_selections": {
                                                      "private-source.pdf": {"mode": "exclude", "exclude_pages": [1]},
                                                      "attachment_0": {"mode": "all"}}})
        check("unsafe keys -> 200 (degrade)", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        stored = _manifest(jid).get("material_page_selections")
        check("unsafe keys -> only safe key persisted", list(stored["attachments"].keys()) == ["attachment_0"])
        check("unsafe keys -> attachment_key_invalid warning", stored["warnings"] == ["attachment_key_invalid"])
        _no_leak("unsafe-key manifest", stored)

        # Multipart bad JSON -> degrades to empty envelope.
        data = {**_base_payload(), "material_page_selections": "{not valid json"}
        resp = client.post("/api/jobs/llm", data=data, files={"attachments": ("n.txt", b"x", "text/plain")})
        check("per-attach multipart bad-json -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("per-attach multipart bad-json -> empty envelope",
              _manifest(jid)["material_page_selections"]["attachments"] == {})

        # Existing page_selections behaviour preserved (valid + invalid 400).
        resp = client.post("/api/jobs/llm", json={**_base_payload(),
                                                  "page_selections": {"deck.pdf": [[1, 20]]},
                                                  "material_page_selections": {"attachment_0": {"mode": "all"}}})
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        check("page_selections still persisted alongside per-attach",
              _manifest(jid).get("page_selections") == {"deck.pdf": [[1, 20]]})
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "page_selections": {"deck.pdf": [[10, 5]]}})
        check("page_selections invalid still -> 400", resp.status_code == 400)

        # Hostile canary content never persists or echoes.
        hostile = {"private-source.pdf": {"mode": "exclude", "exclude_pages": [1]},
                   "attachment_0": {"mode": "/home/example/private-source.pdf",
                                    "include_pages": ["assets/secret.png", "raw OCR dump", 1],
                                    "note": "sk_materialselectioncanary1234567890"}}
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "material_page_selections": hostile})
        check("per-attach hostile -> 200", resp.status_code == 200)
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        _no_leak("per-attach hostile manifest", _manifest(jid).get("material_page_selections"))
        _no_leak("per-attach hostile response", resp.json().get("material_page_selections"))

        # Retry preserves the per-attachment envelope.
        sels = {"attachment_0": {"mode": "include", "include_pages": [2, 9]}}
        resp = client.post("/api/jobs/llm", json={**_base_payload(), "material_page_selections": sels})
        jid = resp.json().get("job_id")
        created_ids.append(jid)
        Job(jid).set_status("failed", "forced for retry test")
        resp = client.post(f"/api/jobs/{jid}/retry")
        check("per-attach retry -> 200", resp.status_code == 200)
        check("per-attach retry preserves envelope",
              _manifest(jid)["material_page_selections"]["attachments"]["attachment_0"]["include_pages"] == [2, 9])
    finally:
        _restore(targets)
        for jid in created_ids:
            if jid:
                shutil.rmtree(Job(jid).dir, ignore_errors=True)


if __name__ == "__main__":
    test_normalize_helper()
    test_endpoint()
    test_per_attachment_helper()
    test_per_attachment_endpoint()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
