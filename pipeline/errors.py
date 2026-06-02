from __future__ import annotations

VALID_CATEGORIES = frozenset({
    "extraction",
    "ocr",
    "math",
    "pdf",
    "docx",
    "provider_auth",
    "provider_model",
    "provider_ratelimit",
    "local_offline",
    "unknown",
})


def classify_exception(exc: Exception, *, base_url: str | None = None) -> tuple[str, str]:
    """Map an exception to (error_category, user_facing_message).

    Inspects type-name strings to avoid hard imports of provider SDKs.
    Returns the first matching category; falls back to "unknown".
    """
    exc_name = type(exc).__name__
    raw_message = str(exc)
    status_code = getattr(exc, "status_code", None)

    # Already-classified pipeline error (e.g. LLMProviderError)
    if hasattr(exc, "category") and exc.category in VALID_CATEGORIES:
        return exc.category, raw_message

    # Missing / bad LLM config
    if exc_name == "MissingLLMConfigError":
        return "provider_auth", raw_message

    # OpenAI-compatible SDK errors keyed on HTTP status code or type name
    if status_code == 401 or "AuthenticationError" in exc_name:
        return "provider_auth", (
            "API authentication failed — the API key may be invalid or expired."
        )
    if status_code == 404 or "NotFoundError" in exc_name:
        return "provider_model", (
            "The model was not found — check that the model name is correct."
        )
    if status_code == 429 or "RateLimitError" in exc_name:
        return "provider_ratelimit", (
            "Rate limit exceeded — too many requests to the API provider. "
            "Wait a moment and try again."
        )

    # Connection failures → local server offline
    if "APIConnectionError" in exc_name or "ConnectionRefusedError" in exc_name:
        url_hint = f" at {base_url}" if base_url else ""
        return "local_offline", (
            f"Local model server{url_hint} is offline — "
            "start llama-server or choose a hosted provider."
        )

    # Extraction / OCR
    if "ExtractionError" in exc_name:
        return "extraction", raw_message
    if any(kw in raw_message.lower() for kw in ("tesseract", "pytesseract", "ocr")):
        return "ocr", raw_message

    # Math
    if "math" in exc_name.lower() or "katex" in raw_message.lower():
        return "math", raw_message

    # Render errors (matched by name convention)
    if "pdf" in exc_name.lower() and "render" in exc_name.lower():
        return "pdf", raw_message
    if "docx" in exc_name.lower() and "render" in exc_name.lower():
        return "docx", raw_message

    return "unknown", raw_message
