"""Runtime tests for provider settings wiring (Slice 3).

Proves that the stored ``timeout_seconds`` / ``retry_count`` / ``thinking_default``
reach the live model call, that retries fire only for transient failures, and that
no raw key leaks through the public views or redacted errors.

These are store/unit level — no running server. The ``openai`` SDK is not installed
outside Docker, so a tiny fake ``openai`` module is injected into ``sys.modules``;
``generate_chat_completion`` imports ``OpenAI`` lazily, so the fake is picked up. The
two settings JSON files are redirected to a temp dir and ``os.environ`` is controlled
so the env fallback is deterministic.

    python test_scripts/test_provider_runtime_settings.py
"""
import json
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Fake openai SDK (injected before pipeline imports it lazily) ──────────────
# A configurable stand-in: it records the client init kwargs (so we can assert the
# timeout reached the client), counts create() calls (so we can assert retries),
# and replays a scripted list of behaviors per create() call.


class FakeAPIError(Exception):
    """Generic provider error carrying an optional HTTP status code, matching how
    the real SDK exposes ``status_code`` (used by the retryable classifier)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class APIConnectionError(Exception):
    """Name-matched transient transport error (no status_code), like the real SDK's."""


class _FakeClient:
    last_init_kwargs: dict | None = None
    behaviors: list = []  # ("raise", exc) | ("return", content)
    call_count: int = 0

    def __init__(self, **kwargs):
        _FakeClient.last_init_kwargs = kwargs
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create)
        )

    def _create(self, **params):
        idx = _FakeClient.call_count
        _FakeClient.call_count += 1
        kind, payload = _FakeClient.behaviors[min(idx, len(_FakeClient.behaviors) - 1)]
        if kind == "raise":
            raise payload
        message = types.SimpleNamespace(content=payload)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def _reset_client(behaviors):
    _FakeClient.last_init_kwargs = None
    _FakeClient.behaviors = behaviors
    _FakeClient.call_count = 0


_fake_openai = types.ModuleType("openai")
_fake_openai.OpenAI = _FakeClient
sys.modules["openai"] = _fake_openai

from pipeline import llm_client, provider_config, provider_settings_store  # noqa: E402

# No real backoff sleeps in retry tests.
llm_client._RETRY_BACKOFF_SECONDS = 0

FAKE_KEY = "sk-runtime-DEADBEEF000011112222secret"

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


def run():
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="ps_runtime_"))
    _point_store_at(tmp)
    provider_config.load_env_file = lambda: None
    _clear_provider_env()
    os.environ["DEEPSEEK_API_KEY"] = "sk-env-only-AAAA"
    os.environ["DASHSCOPE_API_KEY"] = "sk-qwen-env-BBBB"

    # ── 1. No settings ⇒ config + runtime byte-identical (no timeout, no retries) ─
    cfg = provider_config.build_provider_config("deepseek", "deepseek-v4-pro")
    check(
        "no-store: config carries no timeout and zero retries",
        cfg.timeout is None and cfg.retry_count == 0,
        detail=f"timeout={cfg.timeout} retry_count={cfg.retry_count}",
    )
    _reset_client([("return", "hello")])
    out = llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    check(
        "no-store: client built WITHOUT a timeout kwarg, single attempt",
        out == "hello"
        and "timeout" not in (_FakeClient.last_init_kwargs or {})
        and _FakeClient.call_count == 1,
        detail=str(_FakeClient.last_init_kwargs),
    )
    qcfg = provider_config.build_provider_config("qwen", "qwen3.7-max")
    check(
        "no-store: qwen thinking defaults to True (unchanged)",
        qcfg.extra_body == {"enable_thinking": True},
        detail=str(qcfg.extra_body),
    )

    # ── 2. Stored timeout_seconds reaches the live client ─────────────────────
    provider_config.update_provider_settings("deepseek", {"timeout_seconds": 42})
    cfg = provider_config.build_provider_config("deepseek", "deepseek-v4-pro")
    check("timeout: build_provider_config carries stored timeout", cfg.timeout == 42.0)
    _reset_client([("return", "ok")])
    llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    check(
        "timeout: OpenAI client constructed with the stored timeout",
        (_FakeClient.last_init_kwargs or {}).get("timeout") == 42.0,
        detail=str(_FakeClient.last_init_kwargs),
    )
    # An explicit caller timeout (e.g. the test probe) still wins over the config.
    _reset_client([("return", "ok")])
    llm_client.generate_chat_completion(
        [{"role": "user", "content": "x"}], cfg, timeout=5.0
    )
    check(
        "timeout: explicit caller timeout wins over the stored value",
        (_FakeClient.last_init_kwargs or {}).get("timeout") == 5.0,
    )

    # ── 3. Stored retry_count drives retries on transient failures ────────────
    provider_config.update_provider_settings("deepseek", {"retry_count": 2})
    cfg = provider_config.build_provider_config("deepseek", "deepseek-v4-pro")
    check("retry: build_provider_config carries stored retry_count", cfg.retry_count == 2)
    # Two transient 503s then success ⇒ exactly 3 create() calls, returns content.
    _reset_client([
        ("raise", FakeAPIError("upstream 503", status_code=503)),
        ("raise", FakeAPIError("upstream 503", status_code=503)),
        ("return", "recovered"),
    ])
    out = llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    check(
        "retry: retries a transient 5xx up to retry_count then succeeds",
        out == "recovered" and _FakeClient.call_count == 3,
        detail=f"calls={_FakeClient.call_count}",
    )
    # A name-matched connection error is also retryable.
    _reset_client([
        ("raise", APIConnectionError("conn reset")),
        ("return", "ok-after-conn"),
    ])
    out = llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    check(
        "retry: a transient connection error is retried",
        out == "ok-after-conn" and _FakeClient.call_count == 2,
    )
    # Exhausting all retries raises a classified LLMProviderError (no infinite loop).
    _reset_client([("raise", FakeAPIError("still 500", status_code=500))])
    raised = False
    try:
        llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    except llm_client.LLMProviderError:
        raised = True
    check(
        "retry: exhausting retries raises after retry_count+1 attempts",
        raised and _FakeClient.call_count == 3,
        detail=f"calls={_FakeClient.call_count}",
    )

    # ── 4. retry_count never retries non-retryable failures ───────────────────
    # (a) 401 auth — deterministic, must fail on the first attempt.
    _reset_client([("raise", FakeAPIError("bad key", status_code=401))])
    try:
        llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    except llm_client.LLMProviderError:
        pass
    check("no-retry: 401 auth error is not retried", _FakeClient.call_count == 1)
    # (b) 400 bad request — deterministic, not retried.
    _reset_client([("raise", FakeAPIError("bad payload", status_code=400))])
    try:
        llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    except llm_client.LLMProviderError:
        pass
    check("no-retry: 400 bad request is not retried", _FakeClient.call_count == 1)
    # (c) 404 model-not-found — deterministic, not retried.
    _reset_client([("raise", FakeAPIError("no model", status_code=404))])
    try:
        llm_client.generate_chat_completion([{"role": "user", "content": "x"}], cfg)
    except llm_client.LLMProviderError:
        pass
    check("no-retry: 404 model error is not retried", _FakeClient.call_count == 1)
    # (d) Missing config never even reaches a model call (no key ⇒ raises pre-call).
    os.environ.pop("DASHSCOPE_API_KEY", None)
    os.environ.pop("QWEN_API_KEY", None)
    _reset_client([("return", "should-not-run")])
    try:
        provider_config.build_provider_config("qwen", "qwen3.7-max")
        missing_raised = False
    except provider_config.MissingLLMConfigError:
        missing_raised = True
    check(
        "no-retry: missing config raises before any model call (0 create calls)",
        missing_raised and _FakeClient.call_count == 0,
    )
    os.environ["DASHSCOPE_API_KEY"] = "sk-qwen-env-BBBB"

    # ── 5. thinking_default fills only when no explicit thinking is set ───────
    provider_config.update_provider_settings("qwen", {"thinking_default": False})
    # No explicit value ⇒ store default (False) fills.
    qcfg = provider_config.build_provider_config("qwen", "qwen3.7-max")
    check(
        "thinking: store thinking_default fills when request did not set thinking",
        qcfg.extra_body == {"enable_thinking": False},
        detail=str(qcfg.extra_body),
    )
    # Explicit request value wins over the store default.
    qcfg = provider_config.build_provider_config(
        "qwen", "qwen3.7-max", qwen_thinking_enabled=True
    )
    check(
        "thinking: explicit request thinking=True beats store default False",
        qcfg.extra_body == {"enable_thinking": True},
    )

    # ── 6. Preset thinking beats provider thinking_default ────────────────────
    # The preset path passes the preset's pinned thinking as an explicit value.
    preset_thinking = True  # e.g. claude_cram["thinking"]
    qcfg = provider_config.build_provider_config(
        "qwen", "qwen3.7-max", qwen_thinking_enabled=preset_thinking
    )
    check(
        "thinking: preset thinking value overrides provider thinking_default",
        qcfg.extra_body == {"enable_thinking": True},
    )

    # ── 7. Generator preset never changes provider/model ──────────────────────
    provider_config.update_provider_settings(
        "qwen", {"default_model": "qwen-plus", "thinking_default": False}
    )
    qcfg = provider_config.build_provider_config(
        "qwen",
        "qwen3.7-max",            # explicit user selection
        qwen_thinking_enabled=True,  # preset thinking pin
        temperature_override=0.4,    # preset sampling pin
        top_p=0.8,
    )
    check(
        "preset: provider/model stay the user's selection despite preset pins",
        qcfg.provider == "qwen"
        and qcfg.model == "qwen3.7-max"
        and abs(qcfg.temperature - 0.4) < 1e-9,
        detail=f"{qcfg.provider}/{qcfg.model}",
    )

    # ── 8. No raw key leaks through views, configs-as-serialized, or errors ───
    provider_config.update_provider_settings("deepseek", {"api_key": FAKE_KEY})
    options = provider_config.get_provider_registry(discover_local=False)
    settings_view = provider_config.get_provider_settings_view()
    check(
        "leak-scan: raw key absent from /api/options registry JSON",
        FAKE_KEY not in json.dumps(options),
    )
    check(
        "leak-scan: raw key absent from /api/provider-settings view JSON",
        FAKE_KEY not in json.dumps(settings_view),
    )
    # The key lives on the (server-side) LLMConfig but is never serialized to any
    # response; confirm it is NOT present in the public DTOs above, and that a probe
    # error message is scrubbed of the key even if upstream echoes it.
    cfg_with_key = provider_config.build_provider_config("deepseek", "deepseek-v4-pro")
    check(
        "leak-scan: stored key is on the server-side config (resolver works)",
        cfg_with_key.api_key == FAKE_KEY,
    )
    redacted = provider_config._redact_secret(
        f"Upstream said: Authorization Bearer {FAKE_KEY} rejected", FAKE_KEY
    )
    check(
        "leak-scan: error redaction strips the raw key from a message",
        FAKE_KEY not in redacted and "***" in redacted,
    )

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
