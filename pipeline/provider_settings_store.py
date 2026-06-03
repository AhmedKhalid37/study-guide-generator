"""Server-side provider settings store (Slice 1 — backend foundation).

Persists in-app provider configuration in two local JSON files under a
gitignored runtime dir, mirroring the existing JSON stores (``style_store`` /
``library_store`` / ``shortcut_store``): atomic temp-file + ``os.replace``
writes, whitelist parsing of untrusted input, and a defensive load that degrades
to defaults rather than crashing.

```
config/provider_settings.json   NON-SECRET: base URLs, default models, custom
                                model ids, sampling + runtime defaults, the
                                default provider, and a last-test summary.
config/secrets.json             SECRET: raw API keys ONLY, file mode 0600.
```

Security boundary (see ``docs/PROVIDER_SETTINGS_DESIGN.md`` §2):

* Raw API keys live **only** in ``secrets.json``. They are never written into
  ``provider_settings.json``, never serialized into any response DTO, never
  logged, and never placed in a job manifest or export.
* :func:`get_secret` exposes a raw key to the **server** (the resolver in
  ``provider_config`` and the test probe) — it is never called to build a public
  response. Public views expose only ``configured``, a last-4 ``key_hint``, and a
  ``key_source`` flag.
* Writes are whitelist-parsed: a fresh field set is built from only the known
  keys, so unknown/dangerous fields in the incoming JSON are never copied across.
* If either file is missing or unreadable, the store degrades to "no settings"
  (fail-safe). With no files present, every read returns ``None``/empty, so
  provider resolution is byte-identical to the pre-store ``.env`` behavior (§15).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"
SETTINGS_JSON = CONFIG_DIR / "provider_settings.json"
SECRETS_JSON = CONFIG_DIR / "secrets.json"

# The canonical provider ids. Kept local (not imported from provider_config) so
# this storage layer has no dependency on the resolver that consumes it — that
# would be a circular import, since provider_config imports this module.
KNOWN_PROVIDER_IDS = ("deepseek", "qwen", "local")

# Non-secret per-provider fields a PATCH may set. ``api_key`` is handled
# separately (write-only, secrets file). Anything outside this set is discarded.
SETTINGS_FIELDS = (
    "base_url",
    "default_model",
    "custom_models",
    "temperature",
    "top_p",
    "max_tokens",
    "thinking_default",
    "timeout_seconds",
    "retry_count",
)

# (python type, lower bound, upper bound) for the bounded numeric fields.
NUMERIC_BOUNDS: dict[str, tuple[type, float, float]] = {
    "temperature": (float, 0.0, 2.0),
    "top_p": (float, 0.0, 1.0),
    "max_tokens": (int, 1, 1_000_000),
    "timeout_seconds": (int, 1, 600),
    "retry_count": (int, 0, 10),
}

MAX_BASE_URL_CHARS = 500
MAX_MODEL_ID_CHARS = 200
MAX_CUSTOM_MODELS = 50
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9 ._:\-/]+$")
LAST_TEST_CATEGORY_CHARS = 60


class ProviderSettingsError(RuntimeError):
    """Raised for invalid provider-settings input. Messages are safe to surface
    to the client (HTTP 400); they never contain a secret value."""


# ---------------------------------------------------------------------------
# Defensive load (fail-safe: missing/corrupt ⇒ empty defaults, never raises)
# ---------------------------------------------------------------------------

def _read_settings() -> dict[str, Any]:
    default = {"version": 1, "default_provider": None, "providers": {}}
    if not SETTINGS_JSON.exists():
        return default
    try:
        data = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(data, dict):
        return default
    providers = data.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    default_provider = data.get("default_provider")
    if default_provider not in KNOWN_PROVIDER_IDS:
        default_provider = None
    return {"version": 1, "default_provider": default_provider, "providers": providers}


def _read_secrets() -> dict[str, Any]:
    default = {"version": 1, "keys": {}}
    if not SECRETS_JSON.exists():
        return default
    try:
        data = json.loads(SECRETS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(data, dict) or not isinstance(data.get("keys"), dict):
        return default
    return {"version": 1, "keys": data["keys"]}


def _provider_block(provider_id: str) -> dict[str, Any]:
    block = _read_settings()["providers"].get(provider_id)
    return block if isinstance(block, dict) else {}


# ---------------------------------------------------------------------------
# Public reads (server-side; the secret reads here never feed a response DTO)
# ---------------------------------------------------------------------------

def get_field(provider_id: str, field: str) -> Any:
    """Return a stored non-secret field value, or ``None`` if unset/absent.

    Values were validated on write; this is a plain read used by the resolver.
    """
    if field not in SETTINGS_FIELDS:
        return None
    value = _provider_block(provider_id).get(field)
    if field == "custom_models":
        return [m for m in value if isinstance(m, str)] if isinstance(value, list) else []
    return value


def get_custom_models(provider_id: str) -> list[str]:
    return list(get_field(provider_id, "custom_models") or [])


def get_default_provider() -> str | None:
    return _read_settings()["default_provider"]


def get_last_test(provider_id: str) -> dict[str, Any] | None:
    value = _provider_block(provider_id).get("last_test")
    return value if isinstance(value, dict) else None


def get_secret(provider_id: str) -> str | None:
    """Return the raw stored API key for the server's own use (resolver / test).

    **Never call this to build a response.** It is the single intentional read of
    a raw secret; callers must keep the value server-side.
    """
    value = _read_secrets()["keys"].get(provider_id)
    return value if isinstance(value, str) and value else None


def has_stored_key(provider_id: str) -> bool:
    return get_secret(provider_id) is not None


def key_hint(raw_key: str | None) -> str | None:
    """A safe, non-secret last-4 hint (or ``None``). Requires length > 4 so the
    hint is always a proper subset — a short placeholder key (e.g. ``"none"``) is
    never echoed back whole. 4 chars is below any useful reconstruction threshold;
    nothing longer is ever exposed."""
    if not raw_key or len(raw_key) <= 4:
        return None
    return raw_key[-4:]


# ---------------------------------------------------------------------------
# Whitelist parsing — the write boundary
# ---------------------------------------------------------------------------

def _clean_optional_str(value: Any, *, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _clean_base_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_BASE_URL_CHARS:
        raise ProviderSettingsError("base_url is too long.")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ProviderSettingsError("base_url must be a valid http(s) URL.")
    return text


def _clean_model_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_MODEL_ID_CHARS or not MODEL_ID_PATTERN.match(text):
        raise ProviderSettingsError("model id contains unsupported characters.")
    return text


def _clean_custom_models(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProviderSettingsError("custom_models must be a list.")
    out: list[str] = []
    for item in value:
        cleaned = _clean_model_id(item)
        if cleaned and cleaned not in out:
            out.append(cleaned)
    if len(out) > MAX_CUSTOM_MODELS:
        raise ProviderSettingsError(f"custom_models exceeds the limit of {MAX_CUSTOM_MODELS}.")
    return out


def _clean_number(field: str, value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderSettingsError(f"{field} must be a number.")
    typ, low, high = NUMERIC_BOUNDS[field]
    if typ is int and isinstance(value, float) and not value.is_integer():
        raise ProviderSettingsError(f"{field} must be a whole number.")
    num = typ(value)
    if num < low or num > high:
        raise ProviderSettingsError(f"{field} must be between {low} and {high}.")
    return num


def _normalize_settings_fields(patch: dict[str, Any]) -> dict[str, Any]:
    """Build a fresh dict of ONLY the known fields present in ``patch``.

    A field present with ``null`` is normalized to ``None`` (clears the override
    so resolution falls back to ``.env``/defaults). A field absent from ``patch``
    is not returned, so the caller leaves it unchanged. Unknown keys are never
    read, so they cannot ride along.
    """
    clean: dict[str, Any] = {}
    for field in SETTINGS_FIELDS:
        if field not in patch:
            continue
        value = patch[field]
        if field == "base_url":
            clean[field] = _clean_base_url(value)
        elif field == "default_model":
            clean[field] = _clean_model_id(value)
        elif field == "custom_models":
            clean[field] = _clean_custom_models(value)
        elif field == "thinking_default":
            if value is not None and not isinstance(value, bool):
                raise ProviderSettingsError("thinking_default must be true, false, or null.")
            clean[field] = value
        elif field in NUMERIC_BOUNDS:
            clean[field] = _clean_number(field, value)
    return clean


# ---------------------------------------------------------------------------
# Atomic writers (settings 0644; secrets 0600)
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, data: dict[str, Any], *, mode: int) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=CONFIG_DIR, prefix=f".{path.stem}-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _set_secret(provider_id: str, raw_key: str) -> None:
    secrets = _read_secrets()
    keys = dict(secrets["keys"])
    keys[provider_id] = raw_key
    _atomic_write(SECRETS_JSON, {"version": 1, "keys": keys}, mode=0o600)


# ---------------------------------------------------------------------------
# Public writes
# ---------------------------------------------------------------------------

def update_provider(provider_id: str, patch: Any) -> None:
    """Apply a partial update to one provider.

    Non-secret fields go to ``provider_settings.json``; ``api_key`` (write-only)
    goes only to ``secrets.json``:
      * ``api_key`` non-empty string  → store the new key.
      * ``api_key`` absent or ``""``  → key unchanged (blank is never a clear).
    Use :func:`clear_key` to remove a key.
    """
    if provider_id not in KNOWN_PROVIDER_IDS:
        raise ProviderSettingsError(f"Unknown provider: {provider_id}")
    patch = patch if isinstance(patch, dict) else {}

    clean = _normalize_settings_fields(patch)
    if clean:
        settings = _read_settings()
        providers = dict(settings["providers"])
        block = dict(providers.get(provider_id) if isinstance(providers.get(provider_id), dict) else {})
        block.update(clean)
        providers[provider_id] = block
        _atomic_write(
            SETTINGS_JSON,
            {"version": 1, "default_provider": settings["default_provider"], "providers": providers},
            mode=0o644,
        )

    if "api_key" in patch:
        raw = patch.get("api_key")
        if isinstance(raw, str) and raw.strip():
            _set_secret(provider_id, raw.strip())
        # Blank / non-string ⇒ no-op (key unchanged). Never clears here.


def clear_key(provider_id: str) -> None:
    if provider_id not in KNOWN_PROVIDER_IDS:
        raise ProviderSettingsError(f"Unknown provider: {provider_id}")
    secrets = _read_secrets()
    if provider_id not in secrets["keys"]:
        return
    keys = {k: v for k, v in secrets["keys"].items() if k != provider_id}
    _atomic_write(SECRETS_JSON, {"version": 1, "keys": keys}, mode=0o600)


def set_default_provider(provider_id: Any) -> None:
    """Set (or clear, with ``None``/empty) the default provider."""
    if provider_id in (None, ""):
        target = None
    elif provider_id in KNOWN_PROVIDER_IDS:
        target = provider_id
    else:
        raise ProviderSettingsError(f"Unknown provider: {provider_id}")
    settings = _read_settings()
    _atomic_write(
        SETTINGS_JSON,
        {"version": 1, "default_provider": target, "providers": settings["providers"]},
        mode=0o644,
    )


def record_test_result(provider_id: str, result: dict[str, Any]) -> None:
    """Persist a SUMMARY-ONLY last-test record (never request/response bodies)."""
    if provider_id not in KNOWN_PROVIDER_IDS:
        return
    summary = {
        "ok": bool(result.get("ok")),
        "at": str(result.get("at") or ""),
        "latency_ms": result.get("latency_ms") if isinstance(result.get("latency_ms"), int) else None,
        "category": str(result.get("category") or "")[:LAST_TEST_CATEGORY_CHARS],
    }
    settings = _read_settings()
    providers = dict(settings["providers"])
    block = dict(providers.get(provider_id) if isinstance(providers.get(provider_id), dict) else {})
    block["last_test"] = summary
    providers[provider_id] = block
    _atomic_write(
        SETTINGS_JSON,
        {"version": 1, "default_provider": settings["default_provider"], "providers": providers},
        mode=0o644,
    )
