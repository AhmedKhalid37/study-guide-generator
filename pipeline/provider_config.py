from __future__ import annotations

import os

from pipeline.llm_client import LLMConfig, MissingLLMConfigError, load_env_file


DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
]
QWEN_MODELS = [
    "qwen3.7-max",
    "qwen3.6-plus",
    "qwen3-max",
    "qwen3.6-max-preview",
    "qwen-plus",
    "qwen-max",
]


def build_provider_config(
    provider: str,
    model_choice: str,
    custom_model: str | None = None,
    *,
    qwen_thinking_enabled: bool = True,
) -> LLMConfig:
    load_env_file()
    temperature = _llm_temperature_from_env()

    if provider == "DeepSeek":
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
            provider="deepseek",
        )

    if provider == "Qwen":
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
            provider="qwen",
            extra_body={"enable_thinking": qwen_thinking_enabled},
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
