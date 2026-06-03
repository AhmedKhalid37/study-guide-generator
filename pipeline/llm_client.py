from __future__ import annotations

import os
import time
from dataclasses import dataclass


def load_env_file() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


class MissingLLMConfigError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    """A classified LLM API failure with a user-facing message."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.2
    top_p: float | None = None
    max_tokens: int | None = None
    provider: str = "openai_compatible"
    extra_body: dict | None = None
    # Runtime knobs resolved from provider settings (Slice 3). Both default to the
    # "unset" values so the from_env()/CLI path and any caller that does not set
    # them stay byte-identical: no app-level timeout (the OpenAI client uses its own
    # default) and no retries (a single attempt, exactly as before).
    timeout: float | None = None
    retry_count: int = 0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        load_env_file()
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


# Exception type-name fragments for transient provider/transport failures that a
# retry can plausibly fix (matched by name to avoid importing the provider SDK).
# Deterministic failures — auth (401), model-not-found (404), bad request (400) —
# are deliberately NOT here: retrying them just repeats the same failure.
_RETRYABLE_TYPE_NAMES = (
    "APITimeoutError",
    "APIConnectionError",
    "InternalServerError",
    "ConnectionError",
    "ConnectionResetError",
    "ConnectionRefusedError",
    "TimeoutError",
)

# Linear backoff between retries (seconds). Kept as a module constant so a test can
# monkeypatch ``time.sleep`` to avoid real waits.
_RETRY_BACKOFF_SECONDS = 0.5


def _is_retryable_exception(exc: Exception) -> bool:
    """True only for transient API/transport failures a retry could fix.

    Non-retryable by design: any 4xx (auth, model-not-found, bad request) and any
    error not positively classified as transient. Validation / missing-config /
    unsupported provider never reach here — the config is already built and the
    HTTP call has begun by this point, so a retry only ever re-issues the same
    in-flight model call (no new job, no new artifacts)."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    name = type(exc).__name__
    return any(fragment in name for fragment in _RETRYABLE_TYPE_NAMES)


def generate_chat_completion(
    messages: list[dict],
    config: LLMConfig,
    *,
    timeout: float | None = None,
    retries: int | None = None,
    allow_empty_content: bool = False,
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI Python package is required for LLM jobs. "
            "Install dependencies with: python -m pip install -r requirements.txt"
        ) from exc

    # Timeout precedence: an explicit caller value (e.g. the provider test probe's
    # short fail-fast timeout) wins; otherwise the provider-settings value carried
    # on the config; otherwise None ⇒ the OpenAI client's own default (byte-identical
    # to before provider settings existed).
    effective_timeout = timeout if timeout is not None else config.timeout
    # Retry precedence: an explicit caller value (the test probe forces 0) wins;
    # otherwise the provider-settings retry_count on the config; otherwise 0.
    effective_retries = retries if retries is not None else config.retry_count
    if not isinstance(effective_retries, int) or effective_retries < 0:
        effective_retries = 0

    client_kwargs: dict = {"base_url": config.base_url, "api_key": config.api_key}
    if effective_timeout is not None:
        client_kwargs["timeout"] = effective_timeout
    client = OpenAI(**client_kwargs)
    params = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
    }
    # Only sent when a preset (or future caller) supplies them, so existing calls
    # remain byte-identical to before these fields existed.
    if config.top_p is not None:
        params["top_p"] = config.top_p
    if config.max_tokens is not None:
        params["max_tokens"] = config.max_tokens
    if config.extra_body is not None:
        params["extra_body"] = config.extra_body

    # One attempt by default (retry_count 0 ⇒ identical to the pre-retry behavior);
    # additional attempts only for transient failures, up to retry_count.
    attempts = effective_retries + 1
    response = None
    for attempt in range(attempts):
        try:
            response = client.chat.completions.create(**params)
            break
        except Exception as exc:
            is_last = attempt + 1 >= attempts
            if not is_last and _is_retryable_exception(exc):
                if _RETRY_BACKOFF_SECONDS:
                    time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            from pipeline.errors import classify_exception
            category, user_message = classify_exception(exc, base_url=config.base_url)
            raise LLMProviderError(category, user_message) from exc
    # A response with no choices at all is always a failure: there is nothing the
    # provider returned, even for the connectivity probe.
    if not getattr(response, "choices", None):
        raise RuntimeError("LLM returned an empty response.")
    content = response.choices[0].message.content
    if not content:
        # The provider-settings "Test connection" probe only verifies
        # auth/connectivity/model reachability; reasoning/thinking models (e.g.
        # Qwen with thinking, DeepSeek V4 Pro) can return a valid choice with empty
        # content under max_tokens=1. For that path a returned choice counts as
        # success. Real generation stays strict (default) so bad/empty model
        # outputs are never silently accepted.
        if allow_empty_content:
            return content or ""
        raise RuntimeError("LLM returned an empty response.")
    return content
