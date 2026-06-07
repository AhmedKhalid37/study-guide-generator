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
MAX_COMPANION_LOG_LINES = 50
MAX_COMPANION_LOG_LINE_CHARS = 500
MAX_START_BODY_BYTES = 16 * 1024
MAX_PROFILES = 50

_START_FIELDS = {"model_id", "profile_id", "parameters"}
_STOP_FIELDS = {"grace_seconds"}
_RESTART_FIELDS = {"reuse_last", "model_id", "profile_id", "parameters"}
_SAFE_START_PARAMETER_NAMES = {
    "port",
    "ctx_size",
    "gpu_layers",
    "threads",
    "parallel",
    "cache_type_k",
    "cache_type_v",
    "flash_attention",
    "mmap",
}
_START_PARAMETER_BOUNDS = {
    "port": (1024, 65535),
    "ctx_size": (512, 131072),
    "gpu_layers": (0, 999),
    "threads": (1, 256),
    "parallel": (1, 32),
}
_START_PARAMETER_ENUMS = {"cache_type_k", "cache_type_v"}
_START_PARAMETER_BOOLEANS = {"flash_attention", "mmap"}
_SERVER_STATES = {"stopped", "starting", "running", "already_running", "not_running", "error", "crashed", "unknown"}
_PROCESS_ERROR_CATEGORIES = {
    "bad_request",
    "not_running",
    "already_running",
    "unknown_model",
    "unknown_profile",
    "invalid_parameters",
    "executable_missing",
    "permission_denied",
    "executable_not_allowed",
    "port_in_use",
    "model_load_failed",
    "model_may_be_too_large",
    "readiness_timeout",
    "process_start_failed",
    "process_crashed",
    "process_stop_failed",
    "stale_process",
    "process_error",
}
_BRIDGE_ERROR_CATEGORIES = {
    "companion_config",
    "companion_offline",
    "companion_auth",
    "companion_timeout",
    "companion_error",
}
_ERROR_CATEGORY_ALIASES = {
    "unauthorized": "companion_auth",
    "invalid_profile": "unknown_profile",
    "invalid_parameter": "invalid_parameters",
    "launch_failed": "process_start_failed",
    "executable_not_allowed": "process_start_failed",
    "stale_pid": "stale_process",
    "identity_uncertain": "stale_process",
    "stop_failed": "process_stop_failed",
    "stop_timeout": "process_stop_failed",
    "model_outside_approved_root": "unknown_model",
}

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
    "bad_request": "Local model server request is invalid.",
    "not_running": "Local model server is not running.",
    "already_running": "Local model server is already running.",
    "unknown_model": "Local model is not available in the companion library.",
    "unknown_profile": "Local model launch profile is not available.",
    "invalid_parameters": "Local model server parameters are invalid.",
    "executable_missing": "Configured local model server executable was not found.",
    "permission_denied": "Configured local model server executable is not runnable.",
    "executable_not_allowed": "Configured local model server executable is not usable.",
    "port_in_use": "Requested local model server port is already in use.",
    "model_load_failed": "Local model server could not load the selected model.",
    "model_may_be_too_large": "Selected local model may be too large for available memory.",
    "readiness_timeout": "Local model server did not become ready in time.",
    "process_start_failed": "Local model server failed to start.",
    "process_crashed": "Local model server process exited unexpectedly.",
    "process_stop_failed": "Local model server failed to stop.",
    "stale_process": "Local model server process state is stale.",
    "process_error": "Local model server process state is unavailable.",
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


class _UnixSocketTransport:
    name = "unix_socket"

    def open(self, config: CompanionBridgeConfig) -> socket.socket:
        if not config.socket_path:
            raise CompanionClientError("companion_config")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(config.timeout_seconds)
        return sock


def _transport_for_config(config: CompanionBridgeConfig) -> _UnixSocketTransport:
    # Linux Unix sockets are the only implemented companion transport in Phase 2G5.
    return _UnixSocketTransport()


def _safe_error(category: str) -> dict[str, str]:
    category = _normalize_error_category(category)
    return {
        "category": category,
        "message": _SAFE_ERROR_MESSAGES.get(category, _SAFE_ERROR_MESSAGES["companion_error"]),
    }


def _safe_process_error(category: Any, message: Any = None) -> dict[str, str]:
    category = _normalize_error_category(category)
    if category not in _BRIDGE_ERROR_CATEGORIES and category not in _PROCESS_ERROR_CATEGORIES:
        category = "process_error"
    safe_message = _redact_text(message, max_len=MAX_COMPANION_LOG_LINE_CHARS) if isinstance(message, str) else None
    return {
        "category": category,
        "message": safe_message or _SAFE_ERROR_MESSAGES.get(category, _SAFE_ERROR_MESSAGES["process_error"]),
    }


def _normalize_error_category(category: Any) -> str:
    if not isinstance(category, str):
        return "companion_error"
    safe_category = re.sub(r"[^a-zA-Z0-9_.-]", "_", category.strip())[:80]
    return _ERROR_CATEGORY_ALIASES.get(safe_category, safe_category) if safe_category else "companion_error"


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


def _empty_server_status(config: CompanionBridgeConfig, category: str | None) -> dict[str, Any]:
    return {
        "ok": True,
        "configured": config.configured,
        "reachable": False,
        "state": "unknown",
        "managed": False,
        "model_id": None,
        "profile_id": None,
        "port": None,
        "started_at": None,
        "error": _safe_error(category) if category else None,
        "log_tail": [],
    }


def _empty_profiles(config: CompanionBridgeConfig, category: str | None) -> dict[str, Any]:
    return {
        "ok": True,
        "configured": config.configured,
        "reachable": False,
        "profiles": [],
        "warnings": [],
        "error": _safe_error(category) if category else None,
    }


def _bad_server_request(message: str) -> dict[str, Any]:
    config = get_companion_bridge_config()
    return {
        **_empty_server_status(config, None),
        "error": _safe_process_error("bad_request", message),
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


def _safe_identifier(value: Any, *, max_len: int) -> str | None:
    text = _safe_str(value, max_len=max_len * 2)
    if text is None or "/" in text or "\\" in text or "\x00" in text:
        return None
    redacted = _redact_text(text, max_len=max_len)
    if not redacted or "[redacted-" in redacted:
        return None
    return redacted


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
_ARGV_RE = re.compile(r"\bargv\b\s*[:=]\s*\[[^\]]*\]", re.IGNORECASE)
_ARG_FLAG_RE = re.compile(r"(?<![\w-])--[A-Za-z0-9][A-Za-z0-9_-]*")


def _redact_text(value: str, max_len: int = 240) -> str:
    redacted = _AUTH_RE.sub("[redacted-auth]", value)
    redacted = _URL_RE.sub("[redacted-url]", redacted)
    redacted = _ARGV_RE.sub("[redacted-argv]", redacted)
    redacted = _ARG_FLAG_RE.sub("[redacted-arg]", redacted)
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


def _http_json_unix(
    config: CompanionBridgeConfig,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not config.socket_path or not config.token:
        raise CompanionClientError("companion_config")

    body_bytes = b""
    if body is not None:
        try:
            body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise CompanionClientError("bad_request") from exc
        if len(body_bytes) > MAX_START_BODY_BYTES:
            raise CompanionClientError("bad_request")

    request = (
        f"{method} {path} HTTP/1.1\r\n"
        "Host: local-model-companion\r\n"
        f"Authorization: Bearer {config.token}\r\n"
        "Accept: application/json\r\n"
        "Content-Type: application/json\r\n"
        "Connection: close\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "\r\n"
    ).encode("utf-8") + body_bytes

    transport = _transport_for_config(config)
    sock = transport.open(config)
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
    if status_code == 400:
        raise CompanionClientError("bad_request", status_code=status_code)
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
        value for value in capabilities if isinstance(value, str) and value in {"scan", "server_profiles"}
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


def _sanitize_parameter_schema(raw: Any, defaults: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    param_type = raw.get("type")
    if param_type not in {"integer", "boolean", "enum"}:
        return None
    item: dict[str, Any] = {"type": param_type}
    label = _safe_str(raw.get("label"), max_len=120)
    if label:
        item["label"] = _redact_text(label, max_len=120)
    help_text = _safe_str(raw.get("help"), max_len=500)
    if help_text:
        item["help"] = _redact_text(help_text, max_len=500)
    if isinstance(raw.get("required"), bool):
        item["required"] = raw["required"]

    if param_type == "integer":
        minimum = raw.get("min")
        maximum = raw.get("max")
        default = raw.get("default")
        if (
            isinstance(minimum, int)
            and not isinstance(minimum, bool)
            and isinstance(maximum, int)
            and not isinstance(maximum, bool)
            and minimum <= maximum
            and isinstance(default, int)
            and not isinstance(default, bool)
            and minimum <= default <= maximum
        ):
            item.update({"min": minimum, "max": maximum, "default": default})
        else:
            return None
    elif param_type == "boolean":
        default = raw.get("default")
        if not isinstance(default, bool):
            return None
        item["default"] = default
    else:
        allowed = raw.get("allowed_values")
        default = raw.get("default")
        if not isinstance(allowed, list) or not isinstance(default, str):
            return None
        safe_allowed = [
            value
            for value in allowed
            if isinstance(value, str) and value and re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", value)
        ][:32]
        if default not in safe_allowed:
            return None
        item["allowed_values"] = safe_allowed
        item["default"] = default
    defaults["_last"] = item["default"]
    return item


def _profiles_from_payload(config: CompanionBridgeConfig, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("ok") is not True:
        return _empty_profiles(config, "companion_error")
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list):
        return _empty_profiles(config, "companion_error")
    profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_profiles[:MAX_PROFILES]:
        if not isinstance(raw, dict):
            continue
        profile_id = _safe_identifier(raw.get("id"), max_len=80)
        if not profile_id or profile_id in seen:
            continue
        parameters_raw = raw.get("parameters")
        if not isinstance(parameters_raw, dict):
            continue
        default_parameters: dict[str, Any] = {}
        parameters: dict[str, Any] = {}
        for name, param_raw in parameters_raw.items():
            if name not in _SAFE_START_PARAMETER_NAMES:
                continue
            marker: dict[str, Any] = {}
            schema = _sanitize_parameter_schema(param_raw, marker)
            if schema is None:
                continue
            parameters[name] = schema
            default_parameters[name] = marker["_last"]
        profile: dict[str, Any] = {
            "id": profile_id,
            "display_name": _redact_text(_safe_str(raw.get("display_name"), max_len=120) or profile_id, max_len=120),
            "description": _redact_text(_safe_str(raw.get("description"), max_len=500) or "", max_len=500),
            "type": "llama_server" if raw.get("type") == "llama_server" else "fake_test" if raw.get("type") == "fake_test" else "unknown",
            "test_profile": raw.get("test_profile") is True,
            "runnable": raw.get("runnable") is True,
            "runnable_reason": _normalize_error_category(raw.get("runnable_reason")) if raw.get("runnable_reason") else None,
            "default_parameters": default_parameters,
            "parameters": parameters,
            "warnings": [
                _redact_text(item, max_len=500)
                for item in raw.get("warnings", [])
                if isinstance(item, str) and _redact_text(item, max_len=500)
            ][:8],
        }
        profiles.append(profile)
        seen.add(profile_id)
    return {
        "ok": True,
        "configured": True,
        "reachable": True,
        "profiles": profiles,
        "warnings": _sanitize_warnings([{"message": item} for item in payload.get("warnings", []) if isinstance(item, str)]),
        "error": None,
    }


def get_companion_server_profiles() -> dict[str, Any]:
    config = get_companion_bridge_config()
    if not config.configured:
        return _empty_profiles(config, "companion_config")
    try:
        payload = _http_json_unix(config, "GET", "/profiles")
    except CompanionClientError as exc:
        return _empty_profiles(config, exc.category)
    return _profiles_from_payload(config, payload)


def _validate_start_payload(payload: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "request body must be a JSON object"
    unknown = sorted(set(payload) - _START_FIELDS)
    if unknown:
        return None, f"unknown field: {unknown[0]}"

    model_id = _safe_identifier(payload.get("model_id"), max_len=240)
    if model_id is None:
        return None, "model_id is required"
    profile_id = _safe_identifier(payload.get("profile_id"), max_len=80)
    if profile_id is None:
        return None, "profile_id is required"

    raw_parameters = payload.get("parameters", {})
    if raw_parameters is None:
        raw_parameters = {}
    if not isinstance(raw_parameters, dict):
        return None, "parameters must be an object"
    unknown_parameters = sorted(set(raw_parameters) - _SAFE_START_PARAMETER_NAMES)
    if unknown_parameters:
        return None, f"unknown parameter: {unknown_parameters[0]}"

    parameters: dict[str, Any] = {}
    for name, (minimum, maximum) in _START_PARAMETER_BOUNDS.items():
        if name not in raw_parameters:
            continue
        value = raw_parameters[name]
        if isinstance(value, bool) or not isinstance(value, int):
            return None, f"{name} must be an integer"
        if value < minimum or value > maximum:
            return None, f"{name} is outside the allowed range"
        parameters[name] = value
    for name in _START_PARAMETER_BOOLEANS:
        if name not in raw_parameters:
            continue
        value = raw_parameters[name]
        if not isinstance(value, bool):
            return None, f"{name} must be a boolean"
        parameters[name] = value
    for name in _START_PARAMETER_ENUMS:
        if name not in raw_parameters:
            continue
        value = raw_parameters[name]
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", value):
            return None, f"{name} must be an allowed string"
        parameters[name] = value
    return {"model_id": model_id, "profile_id": profile_id, "parameters": parameters}, None


def _validate_stop_payload(payload: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "request body must be a JSON object"
    unknown = sorted(set(payload) - _STOP_FIELDS)
    if unknown:
        return None, f"unknown field: {unknown[0]}"
    value = payload.get("grace_seconds", 5)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, "grace_seconds must be a number"
    if value < 0 or value > 30:
        return None, "grace_seconds must be between 0 and 30"
    return {"grace_seconds": value}, None


def _validate_restart_payload(payload: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "request body must be a JSON object"
    unknown = sorted(set(payload) - _RESTART_FIELDS)
    if unknown:
        return None, f"unknown field: {unknown[0]}"
    has_explicit = any(field in payload for field in _START_FIELDS)
    reuse_last = payload.get("reuse_last")
    if reuse_last is not None and not isinstance(reuse_last, bool):
        return None, "reuse_last must be a boolean"
    if has_explicit and reuse_last:
        return None, "restart accepts either explicit start payload or reuse_last"
    if reuse_last is True:
        return {"reuse_last": True}, None
    if has_explicit:
        return _validate_start_payload({key: payload[key] for key in _START_FIELDS if key in payload})
    return None, "restart requires explicit start payload or reuse_last"


def _server_status_from_payload(config: CompanionBridgeConfig, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("ok") is not True:
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        return {
            **_empty_server_status(config, None),
            "configured": True,
            "reachable": True,
            "error": _safe_process_error(
                error.get("category") or error.get("code") or "companion_error",
                error.get("message"),
            ),
        }

    state = payload.get("state")
    safe_state = state if isinstance(state, str) and state in _SERVER_STATES else "unknown"
    error = payload.get("error")
    safe_error = None
    if isinstance(error, dict):
        safe_error = _safe_process_error(
            error.get("category") or error.get("code") or "process_error",
            error.get("message"),
        )

    log_tail: list[str] = []
    raw_tail = payload.get("log_tail")
    if isinstance(raw_tail, str):
        log_tail = [
            _redact_text(line, max_len=MAX_COMPANION_LOG_LINE_CHARS)
            for line in raw_tail.splitlines()[-MAX_COMPANION_LOG_LINES:]
        ]
    elif isinstance(raw_tail, list):
        log_tail = [
            _redact_text(line, max_len=MAX_COMPANION_LOG_LINE_CHARS)
            for line in raw_tail
            if isinstance(line, str)
        ][-MAX_COMPANION_LOG_LINES:]

    port = payload.get("port")
    safe_port = port if isinstance(port, int) and not isinstance(port, bool) and 0 < port <= 65535 else None
    return {
        "ok": True,
        "configured": True,
        "reachable": True,
        "state": safe_state,
        "managed": bool(payload.get("managed")),
        "model_id": _safe_model_text(payload.get("model_id"), max_len=240),
        "profile_id": _safe_identifier(payload.get("profile_id"), max_len=80),
        "port": safe_port,
        "started_at": _safe_model_text(payload.get("started_at"), max_len=80),
        "error": safe_error,
        "log_tail": [line for line in log_tail if line],
    }


def _call_server_endpoint(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    config = get_companion_bridge_config()
    if not config.configured:
        return _empty_server_status(config, "companion_config")
    try:
        payload = _http_json_unix(config, method, path, body)
    except CompanionClientError as exc:
        return _empty_server_status(config, exc.category)
    return _server_status_from_payload(config, payload)


def get_companion_server_status() -> dict[str, Any]:
    return _call_server_endpoint("GET", "/server/status")


def start_companion_server(payload: Any) -> dict[str, Any]:
    safe_payload, error = _validate_start_payload(payload)
    if error is not None:
        return _bad_server_request(error)
    assert safe_payload is not None
    return _call_server_endpoint("POST", "/server/start", safe_payload)


def stop_companion_server(payload: Any) -> dict[str, Any]:
    safe_payload, error = _validate_stop_payload(payload)
    if error is not None:
        return _bad_server_request(error)
    assert safe_payload is not None
    return _call_server_endpoint("POST", "/server/stop", safe_payload)


def restart_companion_server(payload: Any) -> dict[str, Any]:
    safe_payload, error = _validate_restart_payload(payload)
    if error is not None:
        return _bad_server_request(error)
    assert safe_payload is not None
    return _call_server_endpoint("POST", "/server/restart", safe_payload)
