"""Configuration loader for the scanning-only host companion prototype."""

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
class CompanionConfig:
    approved_roots: tuple[ApprovedRoot, ...]
    token: str | None = None
    configured: bool = False


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ConfigError("approved root recursive must be a boolean")


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

    return CompanionConfig(
        approved_roots=tuple(roots),
        token=env_token or config_token,
        configured=True,
    )
