from __future__ import annotations

import errno
import json
import os
import re
import socket
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from pipeline.llm_client import load_env_file


COMPANION_SOCKET_ENV = "LMM_COMPANION_SOCKET"
COMPANION_TOKEN_ENV = "LMM_COMPANION_TOKEN"
COMPANION_TIMEOUT_ENV = "LMM_COMPANION_TIMEOUT_SECONDS"
DEFAULT_COMPANION_TIMEOUT_SECONDS = 3.0
MAX_COMPANION_BODY_BYTES = 2 * 1024 * 1024
MAX_COMPANION_WARNINGS = 25

_MODEL_FIELDS = (
    "id",
    "display_name",
    "filename",
    "relative_path",
    "root_id",
    "size_bytes",
    "modified_at",
    "family_hint",
    "quant_hint",
    "server_compatible",
)
_SAFE_ERROR_MESSAGES = {
    "companion_config": "Local model companion is not configured.",
    "companion_offline": "Local model companion is not reachable.",
    "companion_auth": "Local model companion authentication failed.",
    "companion_timeout": "Local model companion request timed out.",
    "companion_error": "Local model companion returned an invalid response.",
}


@dataclass(frozen=True)
class CompanionBridgeConfig:
    socket_path: str | None
    token: str | None
    timeout_seconds: float

    @property
    def configured(self) -> bool:
        return bool(self.socket_path and self.token)


class CompanionClientError(RuntimeError):
    def __init__(self, category: str, message: str | None = None, status_code: int | None = None):
        super().__init__(message or _SAFE_ERROR_MESSAGES.get(category, _SAFE_ERROR_MESSAGES["companion_error"]))
        self.category = category
        self.status_code = status_code


def _safe_error(category: str) -> dict[str, str]:
    return {
        "category": category,
        "message": _SAFE_ERROR_MESSAGES.get(category, _SAFE_ERROR_MESSAGES["companion_error"]),
    }


def _timeout_from_env(value: str | None) -> float:
    if value is None or not value.strip():
        return DEFAULT_COMPANION_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return DEFAULT_COMPANION_TIMEOUT_SECONDS
    if parsed <= 0:
        return DEFAULT_COMPANION_TIMEOUT_SECONDS
    return min(parsed, 30.0)


def get_companion_bridge_config() -> CompanionBridgeConfig:
    load_env_file()
    socket_path = os.environ.get(COMPANION_SOCKET_ENV)
    token = os.environ.get(COMPANION_TOKEN_ENV)
    return CompanionBridgeConfig(
        socket_path=socket_path.strip() if socket_path and socket_path.strip() else None,
        token=token.strip() if token and token.strip() else None,
        timeout_seconds=_timeout_from_env(os.environ.get(COMPANION_TIMEOUT_ENV)),
    )


def _base_status(config: CompanionBridgeConfig) -> dict[str, Any]:
    return {
        "ok": True,
        "configured": config.configured,
        "reachable": False,
        "transport": "unix_socket",
        "socket_configured": bool(config.socket_path),
        "socket_label": "configured" if config.socket_path else None,
        "capabilities": [],
        "platform": None,
        "version": None,
        "error": None,
    }


def _empty_library(config: CompanionBridgeConfig, category: str | None) -> dict[str, Any]:
    return {
        "ok": True,
        "configured": config.configured,
        "reachable": False,
        "models": [],
        "model_count": 0,
        "last_scan_at": None,
        "roots_configured": 0,
        "warnings": [],
        "error": _safe_error(category) if category else None,
    }


def _is_safe_relative(value: str) -> bool:
    if not value or "\x00" in value:
        return False
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or PureWindowsPath(value).is_absolute():
        return False
    parts = PurePosixPath(normalized).parts
    return bool(parts) and all(part not in ("", ".", "..") for part in parts)


def _safe_str(value: Any, max_len: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.replace("\x00", "").strip()
    if not cleaned:
        return None
    return cleaned[:max_len]


def _safe_model_text(value: Any, max_len: int = 240) -> str | None:
    safe_value = _safe_str(value, max_len=max_len * 4)
    if safe_value is None:
        return None
    redacted = _redact_text(safe_value, max_len=max_len)
    return redacted or None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def _safe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _sanitize_model(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    model: dict[str, Any] = {}
    for field in _MODEL_FIELDS:
        value = item.get(field)
        if field == "relative_path":
            safe_value = _safe_str(value, max_len=500)
            if safe_value and _is_safe_relative(safe_value):
                model[field] = safe_value.replace("\\", "/")
            continue
        if field == "size_bytes":
            safe_size = _safe_int(value)
            if safe_size is not None:
                model[field] = safe_size
            continue
        if field == "server_compatible":
            safe_compatible = _safe_bool(value)
            if safe_compatible is not None:
                model[field] = safe_compatible
            continue
        safe_text = _safe_model_text(value, max_len=500 if field == "id" else 240)
        if safe_text is not None:
            model[field] = safe_text
    model_id = model.get("id")
    if not isinstance(model_id, str) or not model_id:
        return None
    return model


_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_AUTH_RE = re.compile(r"authorization\s*:\s*bearer\s+[^\s\"']+", re.IGNORECASE)
_TOKEN_RE = re.compile(r"\b(?:sk|tok|token)[-_][A-Za-z0-9._-]{8,}\b")
_POSIX_PATH_RE = re.compile(r"(?<![\w.-])/(?:[\w .@+-]+/)+[\w .@+-]+")
_WIN_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\?)+")


def _redact_text(value: str, max_len: int = 240) -> str:
    redacted = _AUTH_RE.sub("[redacted-auth]", value)
    redacted = _URL_RE.sub("[redacted-url]", redacted)
    redacted = _TOKEN_RE.sub("[redacted-token]", redacted)
    redacted = _POSIX_PATH_RE.sub("[redacted-path]", redacted)
    redacted = _WIN_PATH_RE.sub("[redacted-path]", redacted)
    return redacted.replace("\x00", "").strip()[:max_len]


def _sanitize_warning(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    warning: dict[str, Any] = {}
    code = _safe_str(item.get("code"), max_len=80)
    if code:
        warning["code"] = re.sub(r"[^a-zA-Z0-9_.-]", "_", code)[:80]
    message = _safe_str(item.get("message"), max_len=1000)
    if message:
        warning["message"] = _redact_text(message)
    root_id = _safe_str(item.get("root_id"), max_len=120)
    if root_id:
        warning["root_id"] = root_id
    relative_path = _safe_str(item.get("relative_path"), max_len=500)
    if relative_path and _is_safe_relative(relative_path):
        warning["relative_path"] = relative_path.replace("\\", "/")
    count = _safe_int(item.get("count"))
    if count is not None:
        warning["count"] = count
    return warning or None


def _sanitize_warnings(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    warnings: list[dict[str, Any]] = []
    for item in items[:MAX_COMPANION_WARNINGS]:
        warning = _sanitize_warning(item)
        if warning:
            warnings.append(warning)
    if len(items) > MAX_COMPANION_WARNINGS:
        warnings.append(
            {
                "code": "warnings_truncated",
                "message": "additional companion warnings were suppressed",
                "count": len(items) - MAX_COMPANION_WARNINGS,
            }
        )
    return warnings


def _sanitize_models(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        model = _sanitize_model(item)
        if not model:
            continue
        model_id = model["id"]
        if model_id in seen:
            continue
        seen.add(model_id)
        models.append(model)
    return models


def _http_json_unix(config: CompanionBridgeConfig, method: str, path: str) -> dict[str, Any]:
    if not config.socket_path or not config.token:
        raise CompanionClientError("companion_config")

    request = (
        f"{method} {path} HTTP/1.1\r\n"
        "Host: local-model-companion\r\n"
        f"Authorization: Bearer {config.token}\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    ).encode("utf-8")

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(config.timeout_seconds)
    chunks: list[bytes] = []
    try:
        sock.connect(config.socket_path)
        sock.sendall(request)
        total = 0
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_COMPANION_BODY_BYTES:
                raise CompanionClientError("companion_error")
    except socket.timeout as exc:
        raise CompanionClientError("companion_timeout") from exc
    except FileNotFoundError as exc:
        raise CompanionClientError("companion_offline") from exc
    except ConnectionRefusedError as exc:
        raise CompanionClientError("companion_offline") from exc
    except OSError as exc:
        if exc.errno in {
            errno.ENOENT,
            errno.ECONNREFUSED,
            errno.ECONNRESET,
            errno.ENOTSOCK,
            errno.EACCES,
            errno.EPERM,
        }:
            raise CompanionClientError("companion_offline") from exc
        raise CompanionClientError("companion_error") from exc
    finally:
        sock.close()

    raw = b"".join(chunks)
    header, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        raise CompanionClientError("companion_error")
    status_line = header.splitlines()[0].decode("iso-8859-1", errors="replace")
    parts = status_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        raise CompanionClientError("companion_error")
    status_code = int(parts[1])
    if status_code in (401, 403):
        raise CompanionClientError("companion_auth", status_code=status_code)
    if status_code < 200 or status_code >= 300:
        raise CompanionClientError("companion_error", status_code=status_code)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CompanionClientError("companion_error") from exc
    if not isinstance(payload, dict):
        raise CompanionClientError("companion_error")
    return payload


def get_companion_status() -> dict[str, Any]:
    config = get_companion_bridge_config()
    status = _base_status(config)
    if not config.configured:
        status["configured"] = False
        status["reachable"] = False
        status["error"] = _safe_error("companion_config")
        return status
    try:
        payload = _http_json_unix(config, "GET", "/health")
    except CompanionClientError as exc:
        status["error"] = _safe_error(exc.category)
        return status

    if payload.get("ok") is not True:
        status["error"] = _safe_error("companion_error")
        return status

    capabilities = payload.get("capabilities")
    safe_capabilities = [
        value for value in capabilities if isinstance(value, str) and value == "scan"
    ] if isinstance(capabilities, list) else []
    status.update(
        {
            "configured": True,
            "reachable": True,
            "capabilities": safe_capabilities,
            "platform": _safe_str(payload.get("platform"), max_len=80),
            "version": _safe_str(payload.get("version"), max_len=80),
            "error": None,
        }
    )
    return status


def _library_from_payload(config: CompanionBridgeConfig, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("ok") is not True:
        return _empty_library(config, "companion_error")
    if not isinstance(payload.get("models"), list):
        return _empty_library(config, "companion_error")
    models = _sanitize_models(payload.get("models"))
    roots_configured = _safe_int(payload.get("roots_configured"))
    return {
        "ok": True,
        "configured": True,
        "reachable": True,
        "models": models,
        "model_count": len(models),
        "last_scan_at": _safe_str(payload.get("last_scan_at"), max_len=80),
        "roots_configured": roots_configured if roots_configured is not None else 0,
        "warnings": _sanitize_warnings(payload.get("warnings")),
        "error": None,
    }


def get_companion_library() -> dict[str, Any]:
    config = get_companion_bridge_config()
    if not config.configured:
        return _empty_library(config, "companion_config")
    try:
        payload = _http_json_unix(config, "GET", "/models")
    except CompanionClientError as exc:
        return _empty_library(config, exc.category)
    return _library_from_payload(config, payload)


def scan_companion_library() -> dict[str, Any]:
    config = get_companion_bridge_config()
    if not config.configured:
        return _empty_library(config, "companion_config")
    try:
        payload = _http_json_unix(config, "POST", "/models/scan")
    except CompanionClientError as exc:
        return _empty_library(config, exc.category)
    return _library_from_payload(config, payload)
