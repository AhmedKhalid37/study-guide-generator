"""Focused tests for the stored ``default_provider`` precedence fix.

Bug (validation Finding #2): the stored provider-settings ``default_provider`` was
inert — with no per-request provider, ``_pick_generate_provider(None)`` always
picked the FIRST configured provider (DeepSeek), ignoring a stored default of, say,
Qwen.

Expected precedence ladder (see DECISIONS.md):

    explicit per-request provider  >  stored default_provider  >  first-configured

These tests exercise the REAL ``api.server._pick_generate_provider`` plus the
``provider_config`` resolver. FastAPI / pydantic / starlette are not installed
outside Docker, so tiny fakes are injected into ``sys.modules`` BEFORE importing
``api.server`` (it only needs them to define routes/models at import time). The two
settings JSON files are redirected to a temp dir and ``os.environ`` is controlled so
provider configuration is deterministic and the developer's real keys are untouched.

    python test_scripts/test_default_provider_precedence.py
"""
import json
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Fake web deps (injected before api.server imports them) ───────────────────
_fastapi = types.ModuleType("fastapi")


class HTTPException(Exception):
    def __init__(self, status_code: int = 400, detail: object = "") -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FastAPI:
    def __init__(self, *a, **k):
        pass

    def add_middleware(self, *a, **k):
        pass

    def _noop_dec(self, *a, **k):
        def wrap(fn):
            return fn

        return wrap

    get = post = put = delete = patch = _noop_dec

    def mount(self, *a, **k):
        pass


def _placeholder(*a, **k):
    return None


_fastapi.FastAPI = FastAPI
_fastapi.HTTPException = HTTPException
_fastapi.File = _placeholder
_fastapi.Form = _placeholder
_fastapi.Request = object
_fastapi.UploadFile = object
_fastapi.__path__ = []  # make it a package so submodule imports resolve

_mw = types.ModuleType("fastapi.middleware")
_cors = types.ModuleType("fastapi.middleware.cors")
_cors.CORSMiddleware = type("CORSMiddleware", (), {})
_mw.cors = _cors
_fastapi.middleware = _mw

_resp = types.ModuleType("fastapi.responses")
_resp.FileResponse = type("FileResponse", (), {})
_resp.Response = type("Response", (), {})

_sf = types.ModuleType("fastapi.staticfiles")
_sf.StaticFiles = type("StaticFiles", (), {"__init__": lambda self, *a, **k: None})

_pyd = types.ModuleType("pydantic")


class _BaseModel:
    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


_pyd.BaseModel = _BaseModel
_pyd.ValidationError = type("ValidationError", (Exception,), {})

_star = types.ModuleType("starlette")
_conc = types.ModuleType("starlette.concurrency")


async def _run_in_threadpool(fn, *a, **k):
    return fn(*a, **k)


_conc.run_in_threadpool = _run_in_threadpool
_star.concurrency = _conc

for name, mod in {
    "fastapi": _fastapi,
    "fastapi.middleware": _mw,
    "fastapi.middleware.cors": _cors,
    "fastapi.responses": _resp,
    "fastapi.staticfiles": _sf,
    "pydantic": _pyd,
    "starlette": _star,
    "starlette.concurrency": _conc,
}.items():
    sys.modules.setdefault(name, mod)

from pipeline import provider_config, provider_settings_store  # noqa: E402

import importlib  # noqa: E402

server = importlib.import_module("api.server")  # noqa: E402

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _point_store_at(tmp: Path) -> None:
    provider_settings_store.CONFIG_DIR = tmp
    provider_settings_store.SETTINGS_JSON = tmp / "provider_settings.json"
    provider_settings_store.SECRETS_JSON = tmp / "secrets.json"


def _clear_provider_env() -> None:
    for var in (
        "DEEPSEEK_API_KEY", "LLM_API_KEY", "DEEPSEEK_MODEL", "LLM_MODEL",
        "DEEPSEEK_MODEL_FLASH", "DEEPSEEK_BASE_URL", "LLM_BASE_URL",
        "DASHSCOPE_API_KEY", "QWEN_API_KEY", "QWEN_MODEL", "DASHSCOPE_BASE_URL",
        "QWEN_BASE_URL", "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL",
        "LOCAL_LLM_API_KEY", "LLM_TEMPERATURE",
    ):
        os.environ.pop(var, None)


def run() -> int:
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="dpp_test_"))
    _point_store_at(tmp)
    # Neutralize the .env loader so resolution depends ONLY on the env vars this
    # test sets (otherwise the real .env keys would repopulate the process env).
    provider_config.load_env_file = lambda: None
    _clear_provider_env()

    # Baseline config: BOTH DeepSeek and Qwen configured via env. The registry order
    # is [deepseek, qwen, local], so the historical "first configured" is DeepSeek.
    os.environ["DEEPSEEK_API_KEY"] = "sk-deepseek-env-AAAA"
    os.environ["DASHSCOPE_API_KEY"] = "sk-qwen-env-BBBB"

    # ── 1. No request provider + stored default=qwen ⇒ picks qwen, not first ──
    provider_settings_store.set_default_provider("qwen")
    pid, fallback = server._pick_generate_provider(None)
    check(
        "no-request provider + stored default qwen ⇒ picks qwen (not first-configured deepseek)",
        pid == "qwen",
        detail=f"picked {pid!r}",
    )
    # The returned fallback model is qwen's effective default_model (env → built-in).
    check(
        "stored-default pick returns that provider's effective default_model",
        fallback == provider_config._effective_default_model("qwen"),
        detail=f"fallback={fallback!r}",
    )

    # ── 2. Explicit per-request provider wins over the stored default ─────────
    pid2, _ = server._pick_generate_provider("deepseek")
    check(
        "explicit request provider deepseek wins over stored default qwen",
        pid2 == "deepseek",
        detail=f"picked {pid2!r}",
    )

    # ── 3a. Stored default present but UNCONFIGURED ⇒ first-configured fallback ─
    # Point the default at qwen, then remove qwen's key so it is no longer configured.
    os.environ.pop("DASHSCOPE_API_KEY", None)
    os.environ.pop("QWEN_API_KEY", None)
    pid3, _ = server._pick_generate_provider(None)
    check(
        "stored default qwen unconfigured ⇒ falls back to first-configured deepseek",
        pid3 == "deepseek",
        detail=f"picked {pid3!r}",
    )
    os.environ["DASHSCOPE_API_KEY"] = "sk-qwen-env-BBBB"  # restore

    # ── 3b. Stored default unknown (hand-edited file) ⇒ first-configured fallback ─
    # set_default_provider rejects unknown ids, so simulate a corrupt file directly.
    provider_settings_store.SETTINGS_JSON.write_text(
        json.dumps({"version": 1, "default_provider": "bogus", "providers": {}}),
        encoding="utf-8",
    )
    check(
        "unknown stored default coerced to None by the defensive loader",
        provider_settings_store.get_default_provider() is None,
    )
    pid3b, _ = server._pick_generate_provider(None)
    check(
        "unknown stored default ⇒ falls back to first-configured deepseek",
        pid3b == "deepseek",
        detail=f"picked {pid3b!r}",
    )

    # ── 3c. No stored default at all ⇒ unchanged first-configured behavior ────
    provider_settings_store.set_default_provider(None)
    pid3c, _ = server._pick_generate_provider(None)
    check(
        "no stored default ⇒ first-configured deepseek (historical behavior)",
        pid3c == "deepseek",
        detail=f"picked {pid3c!r}",
    )

    # ── 4. Stored default_model of the selected default provider is used ──────
    provider_settings_store.set_default_provider("qwen")
    provider_config.update_provider_settings("qwen", {"default_model": "qwen3.7-plus"})
    pid4, fallback4 = server._pick_generate_provider(None)
    check(
        "selected default provider's stored default_model is the returned fallback",
        pid4 == "qwen" and fallback4 == "qwen3.7-plus",
        detail=f"pid={pid4!r} fallback={fallback4!r}",
    )
    # And it flows through the caller's model resolution (request model absent):
    model_choice = ("" or "").strip() or fallback4 or "Use environment default"
    cfg4 = provider_config.build_provider_config(pid4, model_choice)
    check(
        "no request model ⇒ build uses the stored default_model",
        cfg4.provider == "qwen" and cfg4.model == "qwen3.7-plus",
        detail=f"model={cfg4.model!r}",
    )

    # ── 5. A per-request model wins over the stored default_model ─────────────
    request_model = "qwen-max"
    model_choice5 = (request_model or "").strip() or fallback4 or "Use environment default"
    cfg5 = provider_config.build_provider_config(pid4, model_choice5)
    check(
        "per-request model wins over stored default_model",
        cfg5.model == "qwen-max",
        detail=f"model={cfg5.model!r}",
    )

    # ── 6. Generator preset stays advisory — never repins provider/model ──────
    # The Cram preset is tuned for qwen; running it on deepseek only sets a sampling
    # override + a soft warning. build_provider_config keeps the user's selection.
    preset = server.generator_presets.get_generator_preset("claude_cram")
    check("preset fixture loaded (claude_cram → qwen)", preset is not None and preset["provider"] == "qwen")
    cfg6 = provider_config.build_provider_config(
        "deepseek",            # user-selected provider (mismatch vs preset's qwen)
        "deepseek-chat",       # user-selected model
        temperature_override=preset["temperature"],
        top_p=preset["top_p"],
        max_tokens=preset["max_tokens"],
    )
    check(
        "preset sampling applies but provider/model stay the user's selection",
        cfg6.provider == "deepseek" and cfg6.model == "deepseek-chat",
        detail=f"provider={cfg6.provider!r} model={cfg6.model!r}",
    )

    # ── 7. Leak scan: no raw key / no api_key field in the public views ───────
    options_registry = provider_config.get_provider_registry(discover_local=False)
    settings_view = provider_config.get_provider_settings_view()
    blob = json.dumps(options_registry) + json.dumps(settings_view)
    check(
        "leak-scan: no raw env keys in /api/options registry or /api/provider-settings view",
        "sk-deepseek-env-AAAA" not in blob and "sk-qwen-env-BBBB" not in blob,
    )
    check(
        "leak-scan: no 'api_key' / 'key' field in provider-settings view providers",
        all("api_key" not in p and "key" not in p for p in settings_view["providers"]),
    )

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
