#!/usr/bin/env python3
"""Focused tests for Ask Your Guide — backend local chat API.

No live local model is required: local status, provider config, and generation are
stubbed. The tests cover session storage, local-only enforcement, bounded lexical
retrieval, prompt rules, redaction, history persistence, and original artifact
immutability.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import ask_context, ask_sessions  # noqa: E402
from pipeline.job_manager import Job  # noqa: E402

PASS = 0
FAIL = 0

SECRET_KEY = "sk-live-THIS_MUST_NEVER_LEAK_0123456789abcdef"
SECRET_URL = "https://api.deepseek.com/v1"
GUIDE_MARKER = "ZZZ_GUIDE_FULL_BODY_MARKER"
SOURCE_MARKER = "ZZZ_SOURCE_FULL_BODY_MARKER"

CLEAN_MD = (
    "# Study Guide\n\n"
    "## Alpha Topic\n\n"
    f"{GUIDE_MARKER} Alpha enzymes regulate glycolysis and feedback loops. "
    f"Do not leak {SECRET_KEY} or {SECRET_URL}.\n\n"
    "## Beta Topic\n\n"
    "Beta material discusses unrelated cell walls and transport.\n"
)
EXTRACTED_TXT = (
    "## Page 4\n\n"
    f"{SOURCE_MARKER} The source says alpha regulation is inhibited by citrate.\n\n"
    "## Page 12\n\n"
    "Unrelated transport notes only.\n"
)


def check(name: str, ok: bool) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def _digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _blob(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _clean(value: str) -> bool:
    return (
        SECRET_KEY not in value
        and "sk-" not in value
        and "Authorization" not in value
        and SECRET_URL not in value
        and "https://" not in value
        and "/home/" not in value
    )


def make_job(job_id: str, *, with_guide: bool = True) -> Job:
    job = Job(job_id)
    job.input_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": job_id,
        "status": "done" if with_guide else "failed",
        "title": f"Guide {job_id}",
        "created_at": "2026-06-05T10:00:00",
        "updated_at": "2026-06-05T10:05:00",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "api_key": SECRET_KEY,
        "Authorization": f"Bearer {SECRET_KEY}",
        "base_url": SECRET_URL,
        "input_path": "/home/secret/jobs/input/lecture.pdf",
    }
    job._write_manifest(manifest)
    if with_guide:
        job.clean_md.write_text(CLEAN_MD, encoding="utf-8")
        job.extracted_txt.write_text(EXTRACTED_TXT, encoding="utf-8")
    return job


def test_pure_retrieval_and_prompt(tmp: Path) -> None:
    job = Job("pure-chat", root=tmp)
    job.dir.mkdir(parents=True, exist_ok=True)
    job.clean_md.write_text(CLEAN_MD, encoding="utf-8")
    job.extracted_txt.write_text(EXTRACTED_TXT, encoding="utf-8")
    ask_context.prepare_context(job)
    index = ask_context.load_index(job)

    chunks = ask_sessions.retrieve_chunks(index, "alpha glycolysis citrate regulation", max_chunks=2, token_budget=900)
    check("pure: retrieved bounded top 2", 1 <= len(chunks) <= 2)
    labels = {c.get("label") for c in chunks}
    check("pure: relevant alpha/Source page selected", "Alpha Topic" in labels or "Page 4" in labels)
    check("pure: unrelated beta not dominant", "Beta Topic" not in list(labels)[:1])

    messages, citations, meta = ask_sessions.assemble_prompt(
        question="Explain alpha regulation.",
        retrieved_chunks=chunks,
        recent_history=[{"role": "user", "content": "Earlier alpha question."}],
    )
    prompt_blob = _blob(messages)
    check("pure: hard rule not covered present", "not covered in the guide/source" in prompt_blob)
    check("pure: hard rule no invented citations present", "Do not invent" in prompt_blob)
    check("pure: citation labels included", bool(citations) and all(c in prompt_blob for c in citations))
    check("pure: metadata has no chunk text", all("text" not in row for row in meta))
    cache_blob = ask_context._index_path(job).read_text(encoding="utf-8")
    check("pure: cache redacts planted key/url", _clean(cache_blob))


def test_endpoints() -> None:
    try:
        from fastapi.testclient import TestClient
    except Exception as exc:
        print(f"[SKIP] endpoint test — TestClient unavailable: {exc}")
        return
    try:
        from api.server import app
        from pipeline.job_manager import JOBS_DIR
    except Exception as exc:
        print(f"[SKIP] endpoint test — could not import app: {exc}")
        return

    client = TestClient(app)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    eligible_id = "zzaskchat-eligible"
    guideless_id = "zzaskchat-guideless"
    created: list[Path] = []
    captured: dict[str, object] = {"calls": []}

    original_status = ask_sessions.get_local_model_status
    original_config = ask_sessions.build_provider_config
    original_generate = ask_sessions.generate_chat_completion

    def cleanup() -> None:
        ask_sessions.get_local_model_status = original_status
        ask_sessions.build_provider_config = original_config
        ask_sessions.generate_chat_completion = original_generate
        for path in created:
            shutil.rmtree(path, ignore_errors=True)

    try:
        eligible = make_job(eligible_id, with_guide=True)
        guideless = make_job(guideless_id, with_guide=False)
        created.extend([eligible.dir, guideless.dir])

        before = {
            "clean": _digest(eligible.clean_md),
            "extracted": _digest(eligible.extracted_txt),
            "manifest": _digest(eligible.manifest),
        }

        # 1. create eligible session.
        r = client.post(
            f"/api/ask/jobs/{eligible_id}/sessions",
            json={"title": f"Alpha chat {SECRET_KEY} {SECRET_URL}"},
        )
        check("ep: create session 200", r.status_code == 200)
        body = r.json()
        session = body.get("session", {})
        session_id = session.get("session_id")
        check("ep: session id shape", isinstance(session_id, str) and session_id.startswith("ask_"))
        check("ep: create stores local provider only", session.get("settings", {}).get("provider") == "local")
        check("ep: create response clean", _clean(r.text))

        # 2. unknown job -> 404.
        ru = client.post("/api/ask/jobs/zzaskchat-missing/sessions", json={})
        check("ep: unknown job 404", ru.status_code == 404)

        # 3. guide-less job safe not-ready.
        rg = client.post(f"/api/ask/jobs/{guideless_id}/sessions", json={})
        check("ep: guide-less create not ready", rg.status_code == 409 and "not_ready" in rg.text)

        # 4. load session safe metadata/history.
        rl = client.get(f"/api/ask/sessions/{session_id}")
        check("ep: load session 200", rl.status_code == 200)
        check("ep: load history initially empty", rl.json().get("history") == [])
        check("ep: load response clean", _clean(rl.text))

        # 5. reject empty/oversized.
        re = client.post(f"/api/ask/sessions/{session_id}/message", json={"message": "   "})
        check("ep: empty message 400", re.status_code == 400)
        ro = client.post(f"/api/ask/sessions/{session_id}/message", json={"message": "x" * 5000})
        check("ep: oversized message 400", ro.status_code == 400)

        # 6. offline refuses without model/config call.
        config_calls = {"count": 0}

        def offline_status() -> dict:
            return {
                "provider": "local",
                "configured": False,
                "reachable": False,
                "selected_model": None,
                "default_model": None,
                "model_count": 0,
                "base_url_host": "host.docker.internal",
                "error": {"category": "local_offline", "message": "offline"},
            }

        def fail_config(*args, **kwargs):
            config_calls["count"] += 1
            raise AssertionError("model config should not be built while offline")

        ask_sessions.get_local_model_status = offline_status
        ask_sessions.build_provider_config = fail_config
        rm_off = client.post(f"/api/ask/sessions/{session_id}/message", json={"message": "Explain alpha."})
        check("ep: offline returns structured response", rm_off.status_code == 200 and rm_off.json().get("status") == "local_offline")
        check("ep: offline made no provider call", config_calls["count"] == 0)

        # Online stubs: local only, no cloud fallback.
        def online_status() -> dict:
            return {
                "provider": "local",
                "configured": True,
                "reachable": True,
                "selected_model": "local-test-model",
                "default_model": "local-test-model",
                "model_count": 1,
                "base_url_host": "host.docker.internal",
                "error": None,
            }

        class DummyConfig:
            provider = "local"
            model = "local-test-model"

        def local_config(provider, model_choice, **kwargs):
            captured["calls"].append({"provider": provider, "model": model_choice, "kwargs": kwargs})
            if provider != "local":
                raise AssertionError("cloud provider fallback attempted")
            if model_choice in {"deepseek-chat", "qwen-plus"}:
                raise AssertionError("hosted model fallback attempted")
            return DummyConfig()

        def fake_generate(messages, config):
            captured["messages"] = messages
            captured["config_provider"] = getattr(config, "provider", None)
            return "From your guide/source: Alpha regulation is inhibited by citrate. (Source Page 4)"

        ask_sessions.get_local_model_status = online_status
        ask_sessions.build_provider_config = local_config
        ask_sessions.generate_chat_completion = fake_generate

        msg = f"Explain alpha regulation. {SECRET_KEY} Authorization: Bearer abcdefghi {SECRET_URL}"
        rm = client.post(f"/api/ask/sessions/{session_id}/message", json={"message": msg})
        check("ep: message answered", rm.status_code == 200 and rm.json().get("status") == "answered")
        data = rm.json()
        check("ep: answer returned", "Alpha regulation" in data.get("answer", ""))
        check("ep: citations returned", "Source Page 4" in data.get("citations", []) or "Guide Alpha Topic" in data.get("citations", []))
        check("ep: retrieved chunks bounded", 1 <= len(data.get("retrieved_chunks", [])) <= ask_sessions.MAX_RETRIEVED_CHUNKS)
        check("ep: no retrieved chunk text in response", all("text" not in row for row in data.get("retrieved_chunks", [])))
        check("ep: no raw prompt in response", "Available citation labels" not in rm.text and "Retrieved guide/source chunks" not in rm.text)
        check("ep: response clean", _clean(rm.text))

        prompt_blob = _blob(captured.get("messages"))
        check("ep: prompt includes citation-labelled chunks", "[Source Page 4]" in prompt_blob or "[Guide Alpha Topic]" in prompt_blob)
        check("ep: prompt includes hard answer rules", "Cite only the citation labels" in prompt_blob and "Do not invent" in prompt_blob)
        check("ep: prompt got redacted question", SECRET_KEY not in prompt_blob and SECRET_URL not in prompt_blob)
        check("ep: local provider only", captured.get("config_provider") == "local")
        call = captured["calls"][0] if captured["calls"] else {}
        check("ep: build_provider_config provider local", call.get("provider") == "local")
        check("ep: no DeepSeek/Qwen fallback", "deepseek" not in _blob(captured["calls"]).lower() and "qwen" not in _blob(captured["calls"]).lower())

        # 9. history persisted as JSONL and metadata updated.
        session_dir = eligible.dir / "ask" / "sessions" / session_id
        history_path = session_dir / "history.jsonl"
        meta_path = session_dir / "session.json"
        lines = history_path.read_text(encoding="utf-8").splitlines()
        check("ep: history jsonl two records", len(lines) == 2 and all(json.loads(line) for line in lines))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        check("ep: session metadata updated", meta.get("updated_at") != meta.get("created_at"))

        file_blob = history_path.read_text(encoding="utf-8") + meta_path.read_text(encoding="utf-8")
        check("ep: session/history files clean", _clean(file_blob))

        cache_path = eligible.dir / "ask" / "cache" / "context_index.json"
        check("ep: cache exists", cache_path.exists())
        check("ep: cache clean", _clean(cache_path.read_text(encoding="utf-8")))

        after = {
            "clean": _digest(eligible.clean_md),
            "extracted": _digest(eligible.extracted_txt),
            "manifest": _digest(eligible.manifest),
        }
        check("ep: original artifacts unchanged", before == after)
    finally:
        cleanup()


def main() -> int:
    tmp = Path("/tmp/ask-local-chat-tests")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        test_pure_retrieval_and_prompt(tmp)
        test_endpoints()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nPassed: {PASS}  Failed: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
