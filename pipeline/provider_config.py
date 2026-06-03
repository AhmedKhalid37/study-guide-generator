from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline import provider_settings_store
from pipeline.llm_client import (
    LLMConfig,
    LLMProviderError,
    MissingLLMConfigError,
    generate_chat_completion,
    load_env_file,
)


DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
LOCAL_LLM_BASE_URL = "http://host.docker.internal:8080/v1"
DEEPSEEK_MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
]
QWEN_MODELS = [
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-plus",
    "qwen3-max",
    "qwen3.6-max-preview",
    "qwen-plus",
    "qwen-max",
]


@dataclass(frozen=True)
class ProviderRegistryEntry:
    id: str
    display_name: str
    configured: bool
    available_models: list[str]
    default_model: str | None
    base_url_configured: bool
    base_url: str | None = None
    discovery_error: str | None = None
    supports_thinking: bool = False
    kind: str = "cloud"


PROVIDER_ALIASES = {
    "deepseek": "deepseek",
    "DeepSeek": "deepseek",
    "qwen": "qwen",
    "Qwen": "qwen",
    "local": "local",
    "Local": "local",
    "Local llama.cpp": "local",
    "Local OpenAI-compatible": "local",
    "llama.cpp": "local",
}


# ---------------------------------------------------------------------------
# Effective-value resolvers (settings store → env → built-in default)
#
# These are the single chain used by both the registry entries and
# build_provider_config, so resolution stays consistent. With no settings files
# present the store returns None for every field and each chain falls straight
# through to the existing os.getenv(...) / constant — byte-identical to before
# the store existed (see docs/PROVIDER_SETTINGS_DESIGN.md §15).
# ---------------------------------------------------------------------------

def _store_field(provider_id: str | None, field: str) -> Any:
    if not provider_id:
        return None
    try:
        return provider_settings_store.get_field(provider_id, field)
    except Exception:
        return None


def _store_secret(provider_id: str | None) -> str | None:
    if not provider_id:
        return None
    try:
        return provider_settings_store.get_secret(provider_id)
    except Exception:
        return None


def _env_api_key(provider_id: str) -> str | None:
    if provider_id == "deepseek":
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
    if provider_id == "qwen":
        return os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    if provider_id == "local":
        return os.getenv("LOCAL_LLM_API_KEY") or os.getenv("LLM_API_KEY") or "local"
    return None


def _effective_api_key(provider_id: str) -> str | None:
    return _store_secret(provider_id) or _env_api_key(provider_id)


def _env_base_url(provider_id: str) -> str | None:
    if provider_id == "deepseek":
        return os.getenv("DEEPSEEK_BASE_URL") or os.getenv("LLM_BASE_URL") or DEEPSEEK_BASE_URL
    if provider_id == "qwen":
        return os.getenv("DASHSCOPE_BASE_URL") or os.getenv("QWEN_BASE_URL") or QWEN_BASE_URL
    if provider_id == "local":
        return os.getenv("LOCAL_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    return None


def _effective_base_url(provider_id: str) -> str | None:
    return _store_field(provider_id, "base_url") or _env_base_url(provider_id)


def _env_default_model(provider_id: str) -> str | None:
    if provider_id == "deepseek":
        return (
            os.getenv("DEEPSEEK_MODEL")
            or os.getenv("LLM_MODEL")
            or os.getenv("DEEPSEEK_MODEL_FLASH")
            or DEEPSEEK_MODELS[0]
        )
    if provider_id == "qwen":
        return os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL") or QWEN_MODELS[0]
    if provider_id == "local":
        return os.getenv("LOCAL_LLM_MODEL") or os.getenv("LLM_MODEL")
    return None


def _effective_default_model(provider_id: str) -> str | None:
    return _store_field(provider_id, "default_model") or _env_default_model(provider_id)


def _merge_custom_models(models: list[str], provider_id: str) -> list[str]:
    """Registry list ∪ user-added custom ids (registry-first, deduped)."""
    merged = list(models)
    for model in _store_field(provider_id, "custom_models") or []:
        if model not in merged:
            merged.append(model)
    return merged


def get_provider_registry(*, discover_local: bool = True) -> list[dict[str, Any]]:
    load_env_file()
    return [
        _entry_to_public_dict(_deepseek_entry()),
        _entry_to_public_dict(_qwen_entry()),
        _entry_to_public_dict(_local_entry(discover=discover_local)),
    ]


def resolve_provider_id(provider: str) -> str | None:
    return PROVIDER_ALIASES.get(provider) or PROVIDER_ALIASES.get(provider.strip())


def get_provider_entry(provider: str, *, discover_local: bool = True) -> ProviderRegistryEntry | None:
    load_env_file()
    provider_id = resolve_provider_id(provider)
    if provider_id == "deepseek":
        return _deepseek_entry()
    if provider_id == "qwen":
        return _qwen_entry()
    if provider_id == "local":
        return _local_entry(discover=discover_local)
    return None


def validate_provider_model(provider: str, model: str) -> tuple[bool, str | None]:
    entry = get_provider_entry(provider)
    if entry is None:
        return False, "Unsupported provider."
    if not entry.configured:
        return False, f"{entry.display_name} is not configured on the server."

    selected_model = _selected_model(model, None, fallback=entry.default_model or "")
    if not selected_model:
        return False, f"{entry.display_name} has no default model configured."

    if entry.available_models and selected_model not in entry.available_models:
        return False, f"Unsupported model for {entry.display_name}."
    return True, None


def build_provider_config(
    provider: str,
    model_choice: str,
    custom_model: str | None = None,
    *,
    qwen_thinking_enabled: bool = True,
    temperature_override: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
) -> LLMConfig:
    load_env_file()
    provider_id = resolve_provider_id(provider)

    # Sampling precedence (§4b): an explicit caller value (a generator preset pin,
    # tier 1) wins; otherwise the per-provider settings-store default fills in;
    # otherwise the env/provider default. A preset is NEVER a tier on the
    # provider/model ladder — it only fills sampling here.
    store_temperature = _store_field(provider_id, "temperature")
    temperature = (
        temperature_override
        if temperature_override is not None
        else store_temperature
        if store_temperature is not None
        else _llm_temperature_from_env()
    )
    if top_p is None:
        top_p = _store_field(provider_id, "top_p")
    if max_tokens is None:
        max_tokens = _store_field(provider_id, "max_tokens")

    if provider_id == "deepseek":
        api_key = _effective_api_key("deepseek")
        if not api_key:
            raise MissingLLMConfigError("Missing DEEPSEEK_API_KEY.")
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=_effective_default_model("deepseek") or DEEPSEEK_MODELS[0],
        )
        return LLMConfig(
            base_url=_effective_base_url("deepseek") or DEEPSEEK_BASE_URL,
            api_key=api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            provider="deepseek",
        )

    if provider_id == "qwen":
        api_key = _effective_api_key("qwen")
        if not api_key:
            raise MissingLLMConfigError("Missing DASHSCOPE_API_KEY or QWEN_API_KEY.")
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=_effective_default_model("qwen") or QWEN_MODELS[0],
        )
        return LLMConfig(
            base_url=_effective_base_url("qwen") or QWEN_BASE_URL,
            api_key=api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            provider="qwen",
            extra_body={"enable_thinking": qwen_thinking_enabled},
        )

    if provider_id == "local":
        base_url = _effective_base_url("local")
        if not base_url:
            raise MissingLLMConfigError("Missing LOCAL_LLM_BASE_URL.")
        api_key = _effective_api_key("local") or "local"
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=_effective_default_model("local") or "",
        )
        if not model:
            raise MissingLLMConfigError("Missing LOCAL_LLM_MODEL.")
        return LLMConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            provider="local",
        )

    raise MissingLLMConfigError(f"Unsupported LLM provider: {provider}")


def _selected_model(model_choice: str, custom_model: str | None, *, fallback: str) -> str:
    if model_choice == "Use environment default":
        return fallback
    if model_choice == "Custom model ID":
        model = (custom_model or "").strip()
        if not model:
            return fallback
        return model
    return model_choice


def _llm_temperature_from_env() -> float:
    temperature_raw = os.getenv("LLM_TEMPERATURE", "0.2")
    try:
        return float(temperature_raw)
    except ValueError as exc:
        raise MissingLLMConfigError(
            f"LLM_TEMPERATURE must be a number, got: {temperature_raw}"
        ) from exc


def _deepseek_entry() -> ProviderRegistryEntry:
    api_key = _effective_api_key("deepseek")
    default_model = _effective_default_model("deepseek")
    base_url = _effective_base_url("deepseek")
    return ProviderRegistryEntry(
        id="deepseek",
        display_name="DeepSeek",
        configured=bool(api_key),
        available_models=_models_with_default(
            _merge_custom_models(DEEPSEEK_MODELS, "deepseek"), default_model
        ),
        default_model=default_model,
        base_url_configured=bool(base_url),
        base_url=None,
    )


def _qwen_entry() -> ProviderRegistryEntry:
    api_key = _effective_api_key("qwen")
    default_model = _effective_default_model("qwen")
    base_url = _effective_base_url("qwen")
    return ProviderRegistryEntry(
        id="qwen",
        display_name="Qwen",
        configured=bool(api_key),
        available_models=_models_with_default(
            _merge_custom_models(QWEN_MODELS, "qwen"), default_model
        ),
        default_model=default_model,
        base_url_configured=bool(base_url),
        base_url=None,
        supports_thinking=True,
    )


def _local_entry(*, discover: bool) -> ProviderRegistryEntry:
    base_url = _effective_base_url("local")
    default_model = _effective_default_model("local")
    models: list[str] = []
    discovery_error: str | None = None

    if base_url and discover:
        models, discovery_error = _discover_openai_models(
            base_url,
            api_key=_effective_api_key("local") or "local",
        )
    models = _merge_custom_models(models, "local")
    if not default_model and models:
        default_model = models[0]
    if default_model and default_model not in models:
        models = [default_model, *models]

    configured = bool(base_url and default_model)
    if base_url and not default_model and not discovery_error:
        discovery_error = "LOCAL_LLM_MODEL is required when using a local provider."

    return ProviderRegistryEntry(
        id="local",
        display_name="Local llama.cpp",
        configured=configured,
        available_models=models,
        default_model=default_model,
        base_url_configured=bool(base_url),
        base_url=base_url,
        discovery_error=discovery_error,
        kind="local",
    )


def _discover_openai_models(base_url: str, *, api_key: str, timeout: float = 1.5) -> tuple[list[str], str | None]:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.hostname == "host.docker.internal" and not Path("/.dockerenv").exists():
        return [], "host.docker.internal is only reachable from Docker; start the app in Docker or use localhost for local development."

    models_url = f"{base_url.rstrip('/')}/models"
    request = urllib.request.Request(models_url, headers={"Accept": "application/json"})
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return [], str(exc)

    raw_models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(raw_models, list):
        return [], "Model discovery response did not include a data list."

    model_ids = [
        str(item.get("id"))
        for item in raw_models
        if isinstance(item, dict) and item.get("id")
    ]
    return sorted(set(model_ids)), None


def _models_with_default(models: list[str], default_model: str | None) -> list[str]:
    if default_model and default_model not in models:
        return [default_model, *models]
    return models


def _entry_to_public_dict(entry: ProviderRegistryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "display_name": entry.display_name,
        "configured": entry.configured,
        "available_models": entry.available_models,
        "default_model": entry.default_model,
        "base_url_configured": entry.base_url_configured,
        "base_url": entry.base_url,
        "discovery_error": entry.discovery_error,
        "supports_thinking": entry.supports_thinking,
        "kind": entry.kind,
    }


# ---------------------------------------------------------------------------
# Provider-settings public view + write orchestration (Slice 1)
#
# The redaction boundary: _settings_to_public_dict has NO key field by
# construction. The only secret read here is to derive a last-4 hint + the
# key_source flag — nothing longer than 4 chars ever leaves this function.
# ---------------------------------------------------------------------------

def _entry_for_id(provider_id: str, *, discover_local: bool) -> ProviderRegistryEntry | None:
    if provider_id == "deepseek":
        return _deepseek_entry()
    if provider_id == "qwen":
        return _qwen_entry()
    if provider_id == "local":
        return _local_entry(discover=discover_local)
    return None


def _base_url_host(base_url: str | None) -> str | None:
    """Host only — never query/userinfo (a base URL may embed credentials)."""
    if not base_url:
        return None
    try:
        return urllib.parse.urlparse(base_url).hostname
    except ValueError:
        return None


def _key_source_and_hint(provider_id: str) -> tuple[str, str | None]:
    stored = _store_secret(provider_id)
    if stored:
        return "store", provider_settings_store.key_hint(stored)
    env_key = _env_api_key(provider_id)
    # "local" defaults its env key to the literal "local" — not a real secret, so
    # it does not count as a configured key source for display.
    if env_key and not (provider_id == "local" and env_key == "local"):
        return "env", provider_settings_store.key_hint(env_key)
    return "none", None


def _settings_to_public_dict(provider_id: str, *, discover_local: bool) -> dict[str, Any]:
    entry = _entry_for_id(provider_id, discover_local=discover_local)
    if entry is None:
        raise MissingLLMConfigError(f"Unsupported LLM provider: {provider_id}")
    key_source, hint = _key_source_and_hint(provider_id)
    store_temp = _store_field(provider_id, "temperature")
    return {
        "id": entry.id,
        "display_name": entry.display_name,
        "kind": entry.kind,
        "configured": entry.configured,
        "key_source": key_source,
        "key_hint": hint,
        "base_url_host": _base_url_host(_effective_base_url(provider_id)),
        "base_url_configured": entry.base_url_configured,
        "available_models": entry.available_models,
        "custom_models": list(_store_field(provider_id, "custom_models") or []),
        "default_model": entry.default_model,
        "temperature": store_temp if store_temp is not None else _llm_temperature_from_env(),
        "top_p": _store_field(provider_id, "top_p"),
        "max_tokens": _store_field(provider_id, "max_tokens"),
        "thinking_default": _store_field(provider_id, "thinking_default"),
        "supports_thinking": entry.supports_thinking,
        "timeout_seconds": _store_field(provider_id, "timeout_seconds"),
        "retry_count": _store_field(provider_id, "retry_count"),
        "discovery_error": entry.discovery_error,
        "last_test": provider_settings_store.get_last_test(provider_id),
    }


def get_provider_settings_view(*, discover_local: bool = False) -> dict[str, Any]:
    """The safe, redacted view of every provider's effective settings + status.

    Used by ``GET /api/provider-settings``. Never contains a raw key.
    """
    load_env_file()
    return {
        "default_provider": provider_settings_store.get_default_provider(),
        "providers": [
            _settings_to_public_dict(pid, discover_local=discover_local)
            for pid in provider_settings_store.KNOWN_PROVIDER_IDS
        ],
    }


def get_single_provider_view(provider_id: str, *, discover_local: bool = False) -> dict[str, Any]:
    load_env_file()
    return _settings_to_public_dict(provider_id, discover_local=discover_local)


def update_provider_settings(provider_id: str, patch: Any) -> dict[str, Any]:
    provider_settings_store.update_provider(provider_id, patch)
    return get_single_provider_view(provider_id)


def clear_provider_key(provider_id: str) -> dict[str, Any]:
    provider_settings_store.clear_key(provider_id)
    return get_single_provider_view(provider_id)


def set_default_provider(provider_id: Any) -> dict[str, Any]:
    provider_settings_store.set_default_provider(provider_id)
    return get_provider_settings_view()


# Short, fail-fast probe timeout for the test button — independent of any
# generation timeout. No retries; a test should fail fast, not hammer upstream.
PROVIDER_TEST_TIMEOUT = 10.0


def _redact_secret(message: str, *secrets: str | None) -> str:
    safe = str(message)
    for secret in secrets:
        if secret and len(secret) >= 4:
            safe = safe.replace(secret, "***")
    return safe


def test_provider(provider_id: str) -> dict[str, Any]:
    """Minimal connectivity/auth probe. Creates no job and no artifacts; returns
    only a safe, classified result and persists a summary-only ``last_test``."""
    from datetime import datetime, timezone

    load_env_file()
    entry = _entry_for_id(provider_id, discover_local=False)
    if entry is None:
        raise MissingLLMConfigError(f"Unsupported LLM provider: {provider_id}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not entry.configured:
        result = {
            "ok": False,
            "category": "provider_auth",
            "message": f"{entry.display_name} is not configured on the server.",
            "latency_ms": None,
            "model": entry.default_model,
            "at": now,
        }
        provider_settings_store.record_test_result(provider_id, result)
        return result

    try:
        config = build_provider_config(
            provider_id,
            "Use environment default",
            qwen_thinking_enabled=True,
            temperature_override=0.0,
            max_tokens=1,
        )
    except MissingLLMConfigError as exc:
        result = {
            "ok": False,
            "category": "provider_auth",
            "message": _redact_secret(str(exc)),
            "latency_ms": None,
            "model": entry.default_model,
            "at": now,
        }
        provider_settings_store.record_test_result(provider_id, result)
        return result

    import time

    start = time.monotonic()
    ok = False
    category = "ok"
    message = "Provider responded successfully."
    try:
        generate_chat_completion(
            [{"role": "user", "content": "ping"}],
            config,
            timeout=PROVIDER_TEST_TIMEOUT,
        )
        ok = True
    except LLMProviderError as exc:
        category = exc.category
        message = _redact_secret(str(exc), config.api_key)
    except Exception as exc:  # noqa: BLE001 — classified + redacted below
        from pipeline.errors import classify_exception

        category, message = classify_exception(exc, base_url=config.base_url)
        message = _redact_secret(message, config.api_key)

    latency_ms = int((time.monotonic() - start) * 1000)
    result = {
        "ok": ok,
        "category": category,
        "message": message,
        "latency_ms": latency_ms,
        "model": config.model,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    provider_settings_store.record_test_result(provider_id, result)
    return result
