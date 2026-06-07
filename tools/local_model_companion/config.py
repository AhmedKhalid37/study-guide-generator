"""Configuration loader for the host companion prototype."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_ENV_VAR = "LMM_COMPANION_CONFIG"
TOKEN_ENV_VAR = "LMM_COMPANION_TOKEN"


class ConfigError(ValueError):
    """Raised only for invalid explicit companion config."""


@dataclass(frozen=True)
class ApprovedRoot:
    id: str
    path: Path
    recursive: bool = True


@dataclass(frozen=True)
class ProcessProfileConfig:
    id: str
    profile_type: str
    executable: Path
    display_name: str | None = None
    description: str | None = None
    host: str | None = None
    default_parameters: dict[str, Any] | None = None
    parameter_schema: dict[str, dict[str, Any]] | None = None
    warnings: tuple[str, ...] = ()
    readiness_timeout_seconds: float | None = None


@dataclass(frozen=True)
class CompanionConfig:
    approved_roots: tuple[ApprovedRoot, ...]
    token: str | None = None
    configured: bool = False
    process_runtime_dir: Path | None = None
    profiles: tuple[ProcessProfileConfig, ...] = ()


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ConfigError("approved root recursive must be a boolean")


def _as_optional_float(value: Any, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{field} must be a number when provided")
    parsed = float(value)
    if parsed <= 0 or parsed > 120:
        raise ConfigError(f"{field} must be between 0 and 120")
    return parsed


SAFE_PROFILE_PARAMETER_NAMES = {
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


def _as_safe_defaults(value: Any, *, profile_id: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"profile {profile_id} default_parameters must be an object")
    unknown = sorted(set(value) - SAFE_PROFILE_PARAMETER_NAMES)
    if unknown:
        raise ConfigError(f"profile {profile_id} has unknown default parameter: {unknown[0]}")
    defaults: dict[str, Any] = {}
    for key, raw in value.items():
        if key in {"port", "ctx_size", "gpu_layers", "threads", "parallel"}:
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise ConfigError(f"profile {profile_id} default parameter {key} must be an integer")
        elif key in {"flash_attention", "mmap"}:
            if not isinstance(raw, bool):
                raise ConfigError(f"profile {profile_id} default parameter {key} must be a boolean")
        elif key in {"cache_type_k", "cache_type_v"} and not isinstance(raw, str):
            raise ConfigError(f"profile {profile_id} default parameter {key} must be a string")
        defaults[key] = raw
    return defaults


def _as_parameter_schema(value: Any, *, profile_id: str) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"profile {profile_id} parameter_schema must be an object")
    unknown = sorted(set(value) - SAFE_PROFILE_PARAMETER_NAMES)
    if unknown:
        raise ConfigError(f"profile {profile_id} has unknown schema parameter: {unknown[0]}")
    schema: dict[str, dict[str, Any]] = {}
    for key, raw in value.items():
        if not isinstance(raw, dict):
            raise ConfigError(f"profile {profile_id} schema for {key} must be an object")
        allowed = {"min", "max", "allowed_values", "label", "help", "required"}
        extra = sorted(set(raw) - allowed)
        if extra:
            raise ConfigError(f"profile {profile_id} schema for {key} has unknown field: {extra[0]}")
        safe: dict[str, Any] = {}
        for bound in ("min", "max"):
            if bound in raw:
                if isinstance(raw[bound], bool) or not isinstance(raw[bound], int):
                    raise ConfigError(f"profile {profile_id} schema {key}.{bound} must be an integer")
                safe[bound] = raw[bound]
        if "allowed_values" in raw:
            values = raw["allowed_values"]
            if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item.strip() for item in values):
                raise ConfigError(f"profile {profile_id} schema {key}.allowed_values must be a non-empty string list")
            safe["allowed_values"] = [item.strip() for item in values]
        for text_key in ("label", "help"):
            if text_key in raw:
                if not isinstance(raw[text_key], str):
                    raise ConfigError(f"profile {profile_id} schema {key}.{text_key} must be a string")
                safe[text_key] = raw[text_key].strip()[:240 if text_key == "label" else 1000]
        if "required" in raw:
            if not isinstance(raw["required"], bool):
                raise ConfigError(f"profile {profile_id} schema {key}.required must be a boolean")
            safe["required"] = raw["required"]
        schema[key] = safe
    return schema


def _as_profile_warnings(value: Any, *, profile_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError(f"profile {profile_id} warnings must be a list when provided")
    warnings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(f"profile {profile_id} warnings must contain strings only")
        cleaned = item.strip()
        if cleaned:
            warnings.append(cleaned[:500])
    return tuple(warnings[:8])


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigError(f"unable to read companion config: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid companion config JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ConfigError("companion config must be a JSON object")
    return data


def load_config(config_path: str | os.PathLike[str] | None = None) -> CompanionConfig:
    """Load explicit companion config.

    A missing path means "no approved roots configured". A path may also be
    supplied by `LMM_COMPANION_CONFIG`; there is intentionally no default path.
    """

    effective_path = config_path or os.environ.get(CONFIG_ENV_VAR)
    env_token = os.environ.get(TOKEN_ENV_VAR)
    if not effective_path:
        return CompanionConfig(approved_roots=(), token=env_token, configured=False)

    path = Path(effective_path)
    data = _load_json(path)
    if not data:
        return CompanionConfig(approved_roots=(), token=env_token, configured=False)

    raw_roots = data.get("approved_roots", [])
    if raw_roots is None:
        raw_roots = []
    if not isinstance(raw_roots, list):
        raise ConfigError("approved_roots must be a list")

    roots: list[ApprovedRoot] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_roots):
        if not isinstance(item, dict):
            raise ConfigError("approved_roots entries must be objects")
        root_id = item.get("id")
        root_path = item.get("path")
        if not isinstance(root_id, str) or not root_id.strip():
            raise ConfigError(f"approved root at index {index} has invalid id")
        if root_id in seen_ids:
            raise ConfigError(f"duplicate approved root id: {root_id}")
        if not isinstance(root_path, str) or not root_path.strip():
            raise ConfigError(f"approved root {root_id} has invalid path")
        roots.append(
            ApprovedRoot(
                id=root_id.strip(),
                path=Path(root_path).expanduser().resolve(strict=False),
                recursive=_as_bool(item.get("recursive"), default=True),
            )
        )
        seen_ids.add(root_id)

    config_token = data.get("token")
    if config_token is not None and not isinstance(config_token, str):
        raise ConfigError("token must be a string when provided")

    raw_runtime_dir = data.get("process_runtime_dir")
    if raw_runtime_dir is not None and (not isinstance(raw_runtime_dir, str) or not raw_runtime_dir.strip()):
        raise ConfigError("process_runtime_dir must be a non-empty string when provided")

    raw_profiles = data.get("profiles", {})
    if raw_profiles is None:
        raw_profiles = {}
    if not isinstance(raw_profiles, dict):
        raise ConfigError("profiles must be an object when provided")

    process_profiles: list[ProcessProfileConfig] = []
    for profile_id, profile_data in raw_profiles.items():
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ConfigError("profile ids must be non-empty strings")
        if not isinstance(profile_data, dict):
            raise ConfigError(f"profile {profile_id} must be an object")
        raw_type = profile_data.get("type", "fake_test" if profile_id == "fake_test" else "llama_server")
        if raw_type != "llama_server" and not (profile_id == "fake_test" and raw_type == "fake_test"):
            raise ConfigError(f"profile {profile_id} type is not supported")
        executable = profile_data.get("executable")
        if not isinstance(executable, str) or not executable.strip():
            raise ConfigError(f"profile {profile_id} executable must be a non-empty string")
        raw_display_name = profile_data.get("display_name")
        if raw_display_name is not None and not isinstance(raw_display_name, str):
            raise ConfigError(f"profile {profile_id} display_name must be a string when provided")
        raw_description = profile_data.get("description")
        if raw_description is not None and not isinstance(raw_description, str):
            raise ConfigError(f"profile {profile_id} description must be a string when provided")
        raw_host = profile_data.get("host")
        if raw_host is not None and (not isinstance(raw_host, str) or not raw_host.strip()):
            raise ConfigError(f"profile {profile_id} host must be a non-empty string when provided")
        process_profiles.append(
            ProcessProfileConfig(
                id=profile_id.strip(),
                profile_type=raw_type,
                executable=Path(executable).expanduser().resolve(strict=False),
                display_name=raw_display_name.strip()[:120] if isinstance(raw_display_name, str) and raw_display_name.strip() else None,
                description=raw_description.strip()[:1000] if isinstance(raw_description, str) and raw_description.strip() else None,
                host=raw_host.strip() if isinstance(raw_host, str) else None,
                default_parameters=_as_safe_defaults(profile_data.get("default_parameters"), profile_id=profile_id),
                parameter_schema=_as_parameter_schema(profile_data.get("parameter_schema"), profile_id=profile_id),
                warnings=_as_profile_warnings(profile_data.get("warnings"), profile_id=profile_id),
                readiness_timeout_seconds=_as_optional_float(
                    profile_data.get("readiness_timeout_seconds"),
                    field=f"profile {profile_id} readiness_timeout_seconds",
                ),
            )
        )

    runtime_dir = None
    if raw_runtime_dir:
        runtime_dir = Path(raw_runtime_dir).expanduser().resolve(strict=False)
    elif process_profiles:
        runtime_dir = (path.resolve(strict=False).parent / ".lmm-companion-runtime").resolve(strict=False)

    return CompanionConfig(
        approved_roots=tuple(roots),
        token=env_token or config_token,
        configured=True,
        process_runtime_dir=runtime_dir,
        profiles=tuple(process_profiles),
    )
