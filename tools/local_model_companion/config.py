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
    executable: Path
    host: str | None = None
    default_parameters: dict[str, int] | None = None
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


def _as_int_defaults(value: Any, *, profile_id: str) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"profile {profile_id} default_parameters must be an object")
    allowed = {"port", "ctx_size", "gpu_layers", "threads"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"profile {profile_id} has unknown default parameter: {unknown[0]}")
    defaults: dict[str, int] = {}
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ConfigError(f"profile {profile_id} default parameter {key} must be an integer")
        defaults[key] = raw
    return defaults


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
        executable = profile_data.get("executable")
        if not isinstance(executable, str) or not executable.strip():
            raise ConfigError(f"profile {profile_id} executable must be a non-empty string")
        raw_host = profile_data.get("host")
        if raw_host is not None and (not isinstance(raw_host, str) or not raw_host.strip()):
            raise ConfigError(f"profile {profile_id} host must be a non-empty string when provided")
        process_profiles.append(
            ProcessProfileConfig(
                id=profile_id.strip(),
                executable=Path(executable).expanduser().resolve(strict=False),
                host=raw_host.strip() if isinstance(raw_host, str) else None,
                default_parameters=_as_int_defaults(profile_data.get("default_parameters"), profile_id=profile_id),
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
