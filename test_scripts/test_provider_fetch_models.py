"""Backend tests for the read-only provider fetch-models path (Slice 4).

Proves that `fetch_provider_models`:
  * returns ok:true with a sorted/de-duplicated id list on a successful /models fetch,
  * uses the OpenAI-compatible `/models` discovery for the local provider,
  * returns a safe, redacted, non-leaking error for unconfigured providers,
  * returns a redacted error (no raw key) on an HTTP/auth failure,
  * never leaks a stored raw key into the fetch response, /api/provider-settings,
    or /api/options,
  * does NOT write to provider_settings.json or secrets.json (read-only, no
    auto-persist of custom_models), and
  * leaves provider/model precedence + preset `model_hint` advisory-only behavior
    untouched.

Store/unit level — no running server. `_discover_openai_models` uses urllib (not the
openai SDK), so we monkeypatch `urllib.request.urlopen` with a scripted fake to drive
the real discovery code path. The two settings JSON files are redirected to a temp dir
and provider env is controlled so resolution is deterministic.

    python test_scripts/test_provider_fetch_models.py
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

FAKE_KEY = "sk-fetch-DEADBEEF000011112222secretZZ"

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


# ── Scripted fake urlopen ─────────────────────────────────────────────────────
# Records the requested URL (so we can assert /models was hit) and either returns a
# JSON body or raises a urllib error, mirroring how the real discovery sees them.

class _FakeUrlopen:
    requested_urls: list = []
    behavior = ("json", {"data": []})

    def __call__(self, request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        _FakeUrlopen.requested_urls.append(url)
        kind, payload = _FakeUrlopen.behavior
        if kind == "raise":
            raise payload
        # urlopen is consumed as a context manager; BytesIO already supports that
        # protocol (__enter__/__exit__) and a .read() returning the JSON body.
        return io.BytesIO(json.dumps(payload).encode("utf-8"))


def _reset_urlopen(behavior):
    _FakeUrlopen.requested_urls = []
    _FakeUrlopen.behavior = behavior


def run():
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="ps_fetch_"))
    _point_store_at(tmp)
    provider_config.load_env_file = lambda: None
    _clear_provider_env()
    os.environ["DEEPSEEK_API_KEY"] = "sk-env-only-AAAA"
    os.environ["DASHSCOPE_API_KEY"] = "sk-qwen-env-BBBB"

    fake = _FakeUrlopen()
    urllib.request.urlopen = fake

    # ── 1. Known provider: mocked /models → ok:true, sorted + de-duped ids ─────
    _reset_urlopen(("json", {"data": [
        {"id": "deepseek-chat"},
        {"id": "deepseek-reasoner"},
        {"id": "deepseek-chat"},   # duplicate
        {"id": "deepseek-v4-pro"},
    ]}))
    res = provider_config.fetch_provider_models("deepseek")
    expected = ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro"]
    check(
        "known provider: ok:true with sorted, de-duplicated model ids",
        res["ok"] is True
        and res["models"] == expected
        and res["error"] is None
        and res["provider"] == "deepseek"
        and res["source"] == "provider"
        and res["base_url_host"] == "api.deepseek.com",
        detail=str(res),
    )
    check(
        "known provider: discovery hit the /models endpoint",
        _FakeUrlopen.requested_urls
        and _FakeUrlopen.requested_urls[-1].endswith("/v1/models"),
        detail=str(_FakeUrlopen.requested_urls),
    )

    # ── 2. Local provider uses the same OpenAI-compatible /models discovery ────
    os.environ["LOCAL_LLM_BASE_URL"] = "http://127.0.0.1:8080/v1"
    os.environ["LOCAL_LLM_MODEL"] = "gemma-4-it"
    _reset_urlopen(("json", {"data": [{"id": "gemma-4-it"}, {"id": "llama-3"}]}))
    res = provider_config.fetch_provider_models("local")
    check(
        "local provider: ok:true via /models discovery path",
        res["ok"] is True
        and res["models"] == ["gemma-4-it", "llama-3"]
        and res["base_url_host"] == "127.0.0.1"
        and _FakeUrlopen.requested_urls[-1] == "http://127.0.0.1:8080/v1/models",
        detail=str(res),
    )

    # ── 3. Unconfigured provider → safe, non-leaking error ─────────────────────
    os.environ.pop("LOCAL_LLM_BASE_URL", None)  # local has no base URL now
    res = provider_config.fetch_provider_models("local")
    check(
        "unconfigured local: ok:false with a safe 'no base URL' error",
        res["ok"] is False
        and res["models"] == []
        and res["error"]
        and res["error"]["category"] == "provider_config"
        and "base url" in res["error"]["message"].lower(),
        detail=str(res),
    )

    # ── 4. HTTP/auth failure → redacted classified error, no key leak ──────────
    # Configure deepseek with a stored key so we can prove it never appears in the
    # error message even when the upstream rejects the request.
    provider_config.update_provider_settings("deepseek", {"api_key": FAKE_KEY})
    http_401 = urllib.error.HTTPError(
        url="https://api.deepseek.com/v1/models",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=io.BytesIO(b"{}"),
    )
    _reset_urlopen(("raise", http_401))
    res = provider_config.fetch_provider_models("deepseek")
    check(
        "auth failure: ok:false, classified provider_auth, no raw key in message",
        res["ok"] is False
        and res["error"]
        and res["error"]["category"] == "provider_auth"
        and FAKE_KEY not in json.dumps(res),
        detail=str(res),
    )
    # A network failure classifies + redacts too.
    _reset_urlopen(("raise", urllib.error.URLError("Connection refused")))
    res_net = provider_config.fetch_provider_models("deepseek")
    check(
        "network failure: ok:false, classified provider_network, no key leak",
        res_net["ok"] is False
        and res_net["error"]["category"] == "provider_network"
        and FAKE_KEY not in json.dumps(res_net),
        detail=str(res_net),
    )

    # ── 5. Stored raw key absent from fetch response, /api/provider-settings,
    #       and /api/options ────────────────────────────────────────────────────
    _reset_urlopen(("json", {"data": [{"id": "deepseek-chat"}]}))
    fetch_ok = provider_config.fetch_provider_models("deepseek")
    settings_view = provider_config.get_provider_settings_view()
    options = provider_config.get_provider_registry(discover_local=False)
    check(
        "leak-scan: raw key absent from a SUCCESSFUL fetch-models response",
        fetch_ok["ok"] is True and FAKE_KEY not in json.dumps(fetch_ok),
    )
    check(
        "leak-scan: raw key absent from /api/provider-settings view",
        FAKE_KEY not in json.dumps(settings_view),
    )
    check(
        "leak-scan: raw key absent from /api/options registry",
        FAKE_KEY not in json.dumps(options),
    )
    # Sanity: the key IS resolvable server-side (so the fetch could authenticate).
    check(
        "leak-scan: stored key is still resolvable server-side (resolver intact)",
        provider_config._effective_api_key("deepseek") == FAKE_KEY,
    )

    # ── 6. Fetch does NOT write settings/secrets or auto-persist custom_models ──
    def _snapshot(path: Path) -> bytes:
        return path.read_bytes() if path.exists() else b""

    settings_before = _snapshot(provider_settings_store.SETTINGS_JSON)
    secrets_before = _snapshot(provider_settings_store.SECRETS_JSON)
    _reset_urlopen(("json", {"data": [{"id": "brand-new-model-id"}]}))
    provider_config.fetch_provider_models("deepseek")
    settings_after = _snapshot(provider_settings_store.SETTINGS_JSON)
    secrets_after = _snapshot(provider_settings_store.SECRETS_JSON)
    check(
        "no-persist: provider_settings.json unchanged by fetch",
        settings_before == settings_after,
    )
    check(
        "no-persist: secrets.json unchanged by fetch",
        secrets_before == secrets_after,
    )
    check(
        "no-persist: fetched id NOT added to custom_models",
        "brand-new-model-id"
        not in provider_settings_store.get_custom_models("deepseek"),
    )

    # ── 7. Provider/model precedence unchanged ─────────────────────────────────
    # Store a default model; a per-job request model must still win over it, and the
    # store default must win over the env default.
    provider_config.update_provider_settings("deepseek", {"default_model": "deepseek-reasoner"})
    cfg_req = provider_config.build_provider_config("deepseek", "deepseek-chat")
    cfg_default = provider_config.build_provider_config("deepseek", "Use environment default")
    check(
        "precedence: per-job request model wins over the stored default",
        cfg_req.model == "deepseek-chat",
        detail=cfg_req.model,
    )
    check(
        "precedence: stored default model wins over the env default",
        cfg_default.model == "deepseek-reasoner",
        detail=cfg_default.model,
    )

    # ── 8. Generator preset model_hint stays advisory (never repins) ───────────
    # Preset-style pins (sampling/thinking) must not change the user's provider/model.
    os.environ["DASHSCOPE_API_KEY"] = "sk-qwen-env-BBBB"
    provider_config.update_provider_settings("qwen", {"default_model": "qwen-plus"})
    qcfg = provider_config.build_provider_config(
        "qwen",
        "qwen3.7-max",               # explicit user selection
        qwen_thinking_enabled=True,  # preset thinking pin
        temperature_override=0.4,    # preset sampling pin
    )
    check(
        "preset: provider/model stay the user's selection despite preset pins",
        qcfg.provider == "qwen"
        and qcfg.model == "qwen3.7-max"
        and abs(qcfg.temperature - 0.4) < 1e-9,
        detail=f"{qcfg.provider}/{qcfg.model}",
    )

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
