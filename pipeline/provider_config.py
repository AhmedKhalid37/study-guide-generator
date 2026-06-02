from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.llm_client import LLMConfig, MissingLLMConfigError, load_env_file


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
    # A generator preset can pin its own sampling params; otherwise fall back to the
    # process-global env temperature and leave top_p/max_tokens unset (provider default).
    temperature = (
        temperature_override
        if temperature_override is not None
        else _llm_temperature_from_env()
    )
    provider_id = resolve_provider_id(provider)

    if provider_id == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise MissingLLMConfigError("Missing DEEPSEEK_API_KEY.")
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=os.getenv("DEEPSEEK_MODEL")
            or os.getenv("LLM_MODEL")
            or os.getenv("DEEPSEEK_MODEL_FLASH")
            or DEEPSEEK_MODELS[0],
        )
        return LLMConfig(
            base_url=os.getenv("DEEPSEEK_BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or DEEPSEEK_BASE_URL,
            api_key=api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            provider="deepseek",
        )

    if provider_id == "qwen":
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key:
            raise MissingLLMConfigError("Missing DASHSCOPE_API_KEY or QWEN_API_KEY.")
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL") or QWEN_MODELS[0],
        )
        return LLMConfig(
            base_url=os.getenv("DASHSCOPE_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or QWEN_BASE_URL,
            api_key=api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            provider="qwen",
            extra_body={"enable_thinking": qwen_thinking_enabled},
        )

    if provider_id == "local":
        base_url = os.getenv("LOCAL_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
        if not base_url:
            raise MissingLLMConfigError("Missing LOCAL_LLM_BASE_URL.")
        api_key = os.getenv("LOCAL_LLM_API_KEY") or os.getenv("LLM_API_KEY") or "local"
        model = _selected_model(
            model_choice,
            custom_model,
            fallback=os.getenv("LOCAL_LLM_MODEL") or os.getenv("LLM_MODEL") or "",
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
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
    default_model = (
        os.getenv("DEEPSEEK_MODEL")
        or os.getenv("LLM_MODEL")
        or os.getenv("DEEPSEEK_MODEL_FLASH")
        or DEEPSEEK_MODELS[0]
    )
    base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("LLM_BASE_URL") or DEEPSEEK_BASE_URL
    return ProviderRegistryEntry(
        id="deepseek",
        display_name="DeepSeek",
        configured=bool(api_key),
        available_models=_models_with_default(DEEPSEEK_MODELS, default_model),
        default_model=default_model,
        base_url_configured=bool(base_url),
        base_url=None,
    )


def _qwen_entry() -> ProviderRegistryEntry:
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    default_model = os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL") or QWEN_MODELS[0]
    base_url = os.getenv("DASHSCOPE_BASE_URL") or os.getenv("QWEN_BASE_URL") or QWEN_BASE_URL
    return ProviderRegistryEntry(
        id="qwen",
        display_name="Qwen",
        configured=bool(api_key),
        available_models=_models_with_default(QWEN_MODELS, default_model),
        default_model=default_model,
        base_url_configured=bool(base_url),
        base_url=None,
        supports_thinking=True,
    )


def _local_entry(*, discover: bool) -> ProviderRegistryEntry:
    base_url = os.getenv("LOCAL_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
    default_model = os.getenv("LOCAL_LLM_MODEL") or os.getenv("LLM_MODEL")
    models: list[str] = []
    discovery_error: str | None = None

    if base_url and discover:
        models, discovery_error = _discover_openai_models(
            base_url,
            api_key=os.getenv("LOCAL_LLM_API_KEY") or os.getenv("LLM_API_KEY") or "local",
        )
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
