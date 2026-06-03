"""Unit tests for the provider-settings backend (Slice 1).

Store-level tests — no running server (FastAPI isn't installed outside Docker).
The two JSON files are redirected to a temp dir so the real ``config/`` is never
touched, and ``os.environ`` is controlled so the env fallback is deterministic.

Covers (per the slice's verification list):
  * no settings files ⇒ resolution is byte-identical to the env/default path
  * PATCH stores non-secret fields in provider_settings.json only
  * PATCH api_key writes to secrets.json (0600) and NEVER to the public config
  * the public views + /api/options registry never contain a raw key
  * blank api_key is a no-op; clear-key removes the key (configured flips off
    when no env fallback exists)
  * invalid provider / out-of-range field raise a safe ProviderSettingsError
  * a generator-preset sampling override never changes the selected provider/model
    (model_hint stays advisory; request selection is authoritative)

    python test_scripts/test_provider_settings_store.py
"""
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import provider_config, provider_settings_store  # noqa: E402
from pipeline.provider_settings_store import ProviderSettingsError  # noqa: E402

FAKE_KEY = "sk-test-DEADBEEFraw0000zzzz1234"
FAKE_KEY_HINT = "1234"

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
    tmp = Path(tempfile.mkdtemp(prefix="ps_test_"))
    _point_store_at(tmp)
    # Neutralize the .env loader so resolution depends ONLY on the env vars this
    # test sets — otherwise the developer's real .env keys would repopulate the
    # process env and make the env-fallback assertions non-deterministic.
    provider_config.load_env_file = lambda: None
    _clear_provider_env()

    # ── 1. No store + env key ⇒ byte-identical env/default resolution ─────────
    os.environ["DEEPSEEK_API_KEY"] = "sk-env-only-AAAA"
    entry = provider_config.get_provider_entry("deepseek", discover_local=False)
    check("no-store: env key ⇒ configured", entry is not None and entry.configured)
    check(
        "no-store: base_url falls through to built-in default",
        provider_config._effective_base_url("deepseek") == provider_config.DEEPSEEK_BASE_URL,
    )
    cfg = provider_config.build_provider_config("deepseek", "deepseek-v4-pro")
    check(
        "no-store: build_provider_config uses env key + selected model + default base_url",
        cfg.api_key == "sk-env-only-AAAA"
        and cfg.model == "deepseek-v4-pro"
        and cfg.base_url == provider_config.DEEPSEEK_BASE_URL
        and abs(cfg.temperature - 0.2) < 1e-9,
    )
    check(
        "no-store: settings.json/secrets.json not created by reads",
        not provider_settings_store.SETTINGS_JSON.exists()
        and not provider_settings_store.SECRETS_JSON.exists(),
    )

    # ── 2. PATCH non-secret fields + api_key (write-only) ─────────────────────
    view = provider_config.update_provider_settings(
        "deepseek",
        {
            "base_url": "https://proxy.example.com/v1",
            "default_model": "deepseek-v4-pro",
            "custom_models": ["my-finetune-1", "my-finetune-1"],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 256,
            "api_key": FAKE_KEY,
            # Unknown / dangerous keys must be dropped by whitelist parsing.
            "evil": "rm -rf",
            "secrets": {"x": "y"},
        },
    )
    settings_on_disk = json.loads(provider_settings_store.SETTINGS_JSON.read_text())
    block = settings_on_disk["providers"]["deepseek"]
    check(
        "patch: non-secret fields persisted to provider_settings.json",
        block.get("base_url") == "https://proxy.example.com/v1"
        and block.get("default_model") == "deepseek-v4-pro"
        and block.get("temperature") == 0.7
        and block.get("top_p") == 0.9
        and block.get("max_tokens") == 256,
    )
    check(
        "patch: custom_models deduped",
        block.get("custom_models") == ["my-finetune-1"],
        detail=str(block.get("custom_models")),
    )
    check(
        "patch: unknown/dangerous keys never persisted",
        "evil" not in block and "secrets" not in block and "api_key" not in block,
    )

    # secrets.json holds the raw key (and ONLY there), file mode 0600.
    secrets_on_disk = json.loads(provider_settings_store.SECRETS_JSON.read_text())
    check(
        "patch: raw key written to secrets.json only",
        secrets_on_disk.get("keys", {}).get("deepseek") == FAKE_KEY,
    )
    mode = stat.S_IMODE(os.stat(provider_settings_store.SECRETS_JSON).st_mode)
    check("patch: secrets.json mode is 0600", mode == 0o600, detail=oct(mode))
    check(
        "patch: provider_settings.json text contains no raw key",
        FAKE_KEY not in provider_settings_store.SETTINGS_JSON.read_text(),
    )

    # ── 3. Public view never returns a raw key; exposes safe status only ──────
    check(
        "view: configured + key_source=store + last-4 hint, no raw key field",
        view["configured"] is True
        and view["key_source"] == "store"
        and view["key_hint"] == FAKE_KEY_HINT
        and "api_key" not in view
        and "key" not in view,
    )
    check(
        "view: base_url exposed as host only",
        view["base_url_host"] == "proxy.example.com",
    )
    check(
        "view: custom model folded into available_models",
        "my-finetune-1" in view["available_models"],
    )
    full_view = provider_config.get_provider_settings_view()
    check(
        "leak-scan: raw key absent from full provider-settings view JSON",
        FAKE_KEY not in json.dumps(full_view),
    )

    # ── 4. Resolver now prefers the stored key + stored sampling default ──────
    cfg2 = provider_config.build_provider_config("deepseek", "deepseek-v4-pro")
    check(
        "resolve: stored key + base_url + temperature win over env",
        cfg2.api_key == FAKE_KEY
        and cfg2.base_url == "https://proxy.example.com/v1"
        and abs(cfg2.temperature - 0.7) < 1e-9
        and abs((cfg2.top_p or 0) - 0.9) < 1e-9
        and cfg2.max_tokens == 256,
    )

    # ── 5. /api/options registry never leaks the raw key ──────────────────────
    registry = provider_config.get_provider_registry(discover_local=False)
    check(
        "leak-scan: raw key absent from /api/options registry JSON",
        FAKE_KEY not in json.dumps(registry),
    )

    # ── 6. Blank api_key is a no-op; clear-key removes it ─────────────────────
    provider_config.update_provider_settings("deepseek", {"api_key": "", "temperature": 0.3})
    check(
        "patch: blank api_key leaves the key unchanged",
        provider_settings_store.get_secret("deepseek") == FAKE_KEY,
    )
    # Remove the env fallback so clearing the stored key flips configured off.
    os.environ.pop("DEEPSEEK_API_KEY", None)
    cleared = provider_config.clear_provider_key("deepseek")
    check(
        "clear-key: removes key ⇒ configured false, key_source none",
        cleared["configured"] is False
        and cleared["key_source"] == "none"
        and cleared["key_hint"] is None
        and provider_settings_store.get_secret("deepseek") is None,
    )

    # ── 7. Invalid input raises a safe ProviderSettingsError ──────────────────
    def _raises(fn):
        try:
            fn()
            return False
        except ProviderSettingsError:
            return True

    check("validate: unknown provider rejected", _raises(lambda: provider_settings_store.update_provider("nope", {})))
    check("validate: temperature out of range rejected", _raises(lambda: provider_settings_store.update_provider("deepseek", {"temperature": 5.0})))
    check("validate: negative retry_count rejected", _raises(lambda: provider_settings_store.update_provider("deepseek", {"retry_count": -1})))
    check("validate: bad base_url rejected", _raises(lambda: provider_settings_store.update_provider("deepseek", {"base_url": "not-a-url"})))
    check("validate: non-list custom_models rejected", _raises(lambda: provider_settings_store.update_provider("deepseek", {"custom_models": "x"})))
    check("validate: invalid custom model id rejected", _raises(lambda: provider_settings_store.update_provider("deepseek", {"custom_models": ["bad id?!"]})))

    # ── 8. Generator-preset sampling override never changes provider/model ────
    # Set a store default_model; an explicit selection must still win (request is
    # authoritative — model_hint/presets never repin provider/model).
    provider_config.update_provider_settings("deepseek", {"default_model": "deepseek-v4-flash", "api_key": FAKE_KEY})
    cfg3 = provider_config.build_provider_config(
        "deepseek",
        "deepseek-chat",          # explicit user selection
        qwen_thinking_enabled=True,
        temperature_override=0.15,  # a preset sampling pin
        top_p=0.5,
        max_tokens=99,
    )
    check(
        "preset: sampling override applies but provider/model stay the user's selection",
        cfg3.provider == "deepseek"
        and cfg3.model == "deepseek-chat"
        and abs(cfg3.temperature - 0.15) < 1e-9
        and abs((cfg3.top_p or 0) - 0.5) < 1e-9
        and cfg3.max_tokens == 99,
    )

    # ── 9. test_provider is side-effect free for an unconfigured provider ─────
    os.environ.pop("DASHSCOPE_API_KEY", None)
    os.environ.pop("QWEN_API_KEY", None)
    test_result = provider_config.test_provider("qwen")
    check(
        "test: unconfigured provider returns redacted not-ok without network",
        test_result["ok"] is False
        and FAKE_KEY not in json.dumps(test_result)
        and test_result["latency_ms"] is None,
    )

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
