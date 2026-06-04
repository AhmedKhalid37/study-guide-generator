"""Backend tests for the detection-only Local Model Manager status (LMM Slice 2).

Proves that `get_local_model_status`:
  * reachable local server → ok:true, reachable:true, sorted/de-duped model list,
    model_count, latency, configured:true;
  * offline / network failure → ok:true, reachable:false, normalized `local_offline`
    category, safe redacted message, latency_ms:null;
  * unconfigured (no base URL) → ok:true, reachable:false, base_url_configured:false,
    no crash;
  * invalid / malformed base URL → ok:true, safe response, host redacted, no crash;
  * the response exposes `base_url_host` (host only) — never a full URL, userinfo,
    or query;
  * a sentinel local API key never appears anywhere in the response;
  * NO writes — provider_settings.json / secrets.json unchanged, no jobs/artifacts;
  * existing /api/options + provider-settings views still omit any raw key.

Store/unit level — no running server. `_discover_openai_models` uses urllib (not the
openai SDK), so we monkeypatch `urllib.request.urlopen` with a scripted fake to drive
the real discovery code path. The settings JSON files are redirected to a temp dir and
provider env is controlled so resolution is deterministic. `/.dockerenv` existence is
faked via Path.exists so host.docker.internal probing is exercised without Docker.

    python test_scripts/test_local_model_status.py
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import provider_config, provider_settings_store  # noqa: E402

FAKE_LOCAL_KEY = "sk-local-DEADBEEF000011112222secretZZ"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _point_store_at(tmp: Path):
    provider_settings_store.CONFIG_DIR = tmp
    provider_settings_store.SETTINGS_JSON = tmp / "provider_settings.json"
    provider_settings_store.SECRETS_JSON = tmp / "secrets.json"


def _clear_provider_env():
    for var in (
        "DEEPSEEK_API_KEY", "LLM_API_KEY", "DEEPSEEK_MODEL", "LLM_MODEL",
        "DEEPSEEK_MODEL_FLASH", "DEEPSEEK_BASE_URL", "LLM_BASE_URL",
        "DASHSCOPE_API_KEY", "QWEN_API_KEY", "QWEN_MODEL", "DASHSCOPE_BASE_URL",
        "QWEN_BASE_URL", "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL",
        "LOCAL_LLM_API_KEY", "LLM_TEMPERATURE",
    ):
        os.environ.pop(var, None)


# ── Scripted fake urlopen (mirrors the real discovery's view) ─────────────────
class _FakeUrlopen:
    requested_urls: list = []
    behavior = ("json", {"data": []})

    def __call__(self, request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        _FakeUrlopen.requested_urls.append(url)
        kind, payload = _FakeUrlopen.behavior
        if kind == "raise":
            raise payload
        return io.BytesIO(json.dumps(payload).encode("utf-8"))


def _reset_urlopen(behavior):
    _FakeUrlopen.requested_urls = []
    _FakeUrlopen.behavior = behavior


def run():
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="lmm_status_"))
    _point_store_at(tmp)
    provider_config.load_env_file = lambda: None
    _clear_provider_env()

    # Pretend we are inside Docker so the host.docker.internal guard does not
    # short-circuit (we drive reachability via the fake urlopen instead).
    real_exists = Path.exists
    Path.exists = lambda self: True if str(self) == "/.dockerenv" else real_exists(self)

    fake = _FakeUrlopen()
    urllib.request.urlopen = fake

    # ── 1. Reachable local server → ok:true, reachable:true, sorted/de-duped ───
    os.environ["LOCAL_LLM_BASE_URL"] = "http://host.docker.internal:8080/v1"
    os.environ["LOCAL_LLM_MODEL"] = "gemma-4-it"
    _reset_urlopen(("json", {"data": [
        {"id": "llama-3"},
        {"id": "gemma-4-it"},
        {"id": "llama-3"},  # duplicate
    ]}))
    res = provider_config.get_local_model_status()
    check(
        "reachable: ok:true, reachable:true, configured:true",
        res["ok"] is True and res["reachable"] is True and res["configured"] is True,
        detail=str(res),
    )
    check(
        "reachable: sorted + de-duped models, model_count matches",
        res["models"] == ["gemma-4-it", "llama-3"]
        and res["model_count"] == 2
        and res["selected_model"] == "gemma-4-it"
        and res["error"] is None,
        detail=str(res),
    )
    check(
        "reachable: probe hit the /v1/models endpoint",
        _FakeUrlopen.requested_urls
        and _FakeUrlopen.requested_urls[-1].endswith("/v1/models"),
        detail=str(_FakeUrlopen.requested_urls),
    )
    check(
        "reachable: latency_ms is an int (round-trip measured)",
        isinstance(res["latency_ms"], int),
        detail=str(res["latency_ms"]),
    )

    # ── 2. Offline / network failure → ok:true, reachable:false, local_offline ─
    _reset_urlopen(("raise", urllib.error.URLError("Connection refused")))
    res_off = provider_config.get_local_model_status()
    check(
        "offline: ok:true but reachable:false (request succeeded, server down)",
        res_off["ok"] is True and res_off["reachable"] is False,
        detail=str(res_off),
    )
    check(
        "offline: normalized to local_offline with a safe message, latency null",
        res_off["error"]
        and res_off["error"]["category"] == "local_offline"
        and res_off["models"] == []
        and res_off["model_count"] == 0
        and res_off["latency_ms"] is None,
        detail=str(res_off),
    )

    # ── 3. Unconfigured (no base URL) → safe, no crash ─────────────────────────
    os.environ.pop("LOCAL_LLM_BASE_URL", None)
    res_unc = provider_config.get_local_model_status()
    check(
        "unconfigured: ok:true, base_url_configured:false, not reachable, no crash",
        res_unc["ok"] is True
        and res_unc["base_url_configured"] is False
        and res_unc["base_url_host"] is None
        and res_unc["reachable"] is False
        and res_unc["configured"] is False
        and res_unc["error"]["category"] == "provider_config",
        detail=str(res_unc),
    )

    # ── 4. Invalid / malformed base URL → safe, no crash, redacted ─────────────
    os.environ["LOCAL_LLM_BASE_URL"] = "http://user:secretpw@bad host:99999/v1"
    _reset_urlopen(("raise", urllib.error.URLError("name or service not known")))
    res_bad = provider_config.get_local_model_status()
    blob_bad = json.dumps(res_bad)
    check(
        "invalid base URL: ok:true, no crash, no userinfo password leaked",
        res_bad["ok"] is True
        and res_bad["reachable"] is False
        and "secretpw" not in blob_bad,
        detail=str(res_bad),
    )

    # ── 5. base_url_host only — never full URL / userinfo / query ──────────────
    os.environ["LOCAL_LLM_BASE_URL"] = "http://user:topsecret@host.docker.internal:8080/v1?token=abc"
    os.environ["LOCAL_LLM_MODEL"] = "gemma-4-it"
    _reset_urlopen(("json", {"data": [{"id": "gemma-4-it"}]}))
    res_url = provider_config.get_local_model_status()
    blob_url = json.dumps(res_url)
    check(
        "host-only: base_url_host is the bare host (no scheme/port/path)",
        res_url["base_url_host"] == "host.docker.internal",
        detail=str(res_url["base_url_host"]),
    )
    check(
        "host-only: no full URL, userinfo, or query string in the response",
        "topsecret" not in blob_url
        and "?token=" not in blob_url
        and "host.docker.internal:8080" not in blob_url
        and "/v1" not in blob_url,
        detail=blob_url,
    )

    # ── 6. Sentinel local API key never appears in the response ────────────────
    provider_config.update_provider_settings("local", {"api_key": FAKE_LOCAL_KEY})
    _reset_urlopen(("json", {"data": [{"id": "gemma-4-it"}]}))
    res_key = provider_config.get_local_model_status()
    check(
        "no-key-leak: stored local key absent from the status response",
        FAKE_LOCAL_KEY not in json.dumps(res_key),
        detail="(redacted)",
    )
    # Sanity: the key IS resolvable server-side (so a probe could authenticate).
    check(
        "no-key-leak: stored local key still resolvable server-side (resolver intact)",
        provider_config._effective_api_key("local") == FAKE_LOCAL_KEY,
    )
    # And it must not leak via the other public views either.
    check(
        "no-key-leak: absent from /api/provider-settings + /api/options",
        FAKE_LOCAL_KEY not in json.dumps(provider_config.get_provider_settings_view())
        and FAKE_LOCAL_KEY not in json.dumps(
            provider_config.get_provider_registry(discover_local=False)
        ),
    )

    # ── 7. No writes — settings/secrets files unchanged by status probes ───────
    def _snapshot(path: Path) -> bytes:
        return path.read_bytes() if path.exists() else b""

    settings_before = _snapshot(provider_settings_store.SETTINGS_JSON)
    secrets_before = _snapshot(provider_settings_store.SECRETS_JSON)
    _reset_urlopen(("json", {"data": [{"id": "brand-new-id"}]}))
    provider_config.get_local_model_status()
    provider_config.get_local_model_status()
    check(
        "no-write: provider_settings.json unchanged by status probes",
        settings_before == _snapshot(provider_settings_store.SETTINGS_JSON),
    )
    check(
        "no-write: secrets.json unchanged by status probes",
        secrets_before == _snapshot(provider_settings_store.SECRETS_JSON),
    )
    check(
        "no-write: discovered id NOT auto-persisted into custom_models",
        "brand-new-id" not in provider_settings_store.get_custom_models("local"),
    )

    # ── 8. Action descriptors are safe (deferred start helper disabled) ────────
    actions = {a["id"]: a for a in res_key["actions"]}
    check(
        "actions: open_provider_settings enabled, copy_start_command disabled",
        actions.get("open_provider_settings", {}).get("enabled") is True
        and actions.get("copy_start_command", {}).get("enabled") is False,
        detail=str(res_key["actions"]),
    )

    Path.exists = real_exists  # restore

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
