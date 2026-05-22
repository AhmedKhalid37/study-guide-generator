from __future__ import annotations

import os
from dataclasses import dataclass


class MissingLLMConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        missing = [
            name
            for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
            if not os.getenv(name)
        ]
        if missing:
            joined = ", ".join(missing)
            raise MissingLLMConfigError(
                f"Missing LLM environment variable(s): {joined}. "
                "Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL before running LLM jobs."
            )

        temperature_raw = os.getenv("LLM_TEMPERATURE", "0.2")
        try:
            temperature = float(temperature_raw)
        except ValueError as exc:
            raise MissingLLMConfigError(
                f"LLM_TEMPERATURE must be a number, got: {temperature_raw}"
            ) from exc

        return cls(
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            model=os.environ["LLM_MODEL"],
            temperature=temperature,
        )


def generate_chat_completion(messages: list[dict], config: LLMConfig) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI Python package is required for LLM jobs. "
            "Install dependencies with: python -m pip install -r requirements.txt"
        ) from exc

    client = OpenAI(base_url=config.base_url, api_key=config.api_key)
    response = client.chat.completions.create(
        model=config.model,
        messages=messages,
        temperature=config.temperature,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned an empty response.")
    return content
