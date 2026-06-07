"""Safe internal launch profile definitions for companion-managed processes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProfileError(ValueError):
    """Raised when a profile definition or parameter payload is invalid."""


@dataclass(frozen=True)
class TypedParameter:
    name: str
    kind: str
    default: int | None
    minimum: int | None = None
    maximum: int | None = None
    required: bool = True

    def validate(self, value: Any) -> int | None:
        if value is None:
            if self.required:
                raise ProfileError(f"{self.name} is required")
            return None
        if self.kind != "int":
            raise ProfileError(f"{self.name} has unsupported parameter type")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ProfileError(f"{self.name} must be an integer")
        if self.minimum is not None and value < self.minimum:
            raise ProfileError(f"{self.name} is below minimum {self.minimum}")
        if self.maximum is not None and value > self.maximum:
            raise ProfileError(f"{self.name} is above maximum {self.maximum}")
        return value


@dataclass(frozen=True)
class LaunchProfile:
    profile_id: str
    executable_path: Path
    argv_template: tuple[str, ...]
    parameters: tuple[TypedParameter, ...]
    description: str = ""
    runnable: bool = True
    host: str | None = None
    requires_readiness: bool = False
    readiness_timeout_seconds: float = 30.0
    readiness_interval_seconds: float = 0.25

    def parameter_map(self) -> dict[str, TypedParameter]:
        return {item.name: item for item in self.parameters}

    def validate_parameters(self, supplied: dict[str, Any] | None) -> dict[str, int | None]:
        supplied = dict(supplied or {})
        specs = self.parameter_map()
        unknown = sorted(set(supplied) - set(specs))
        if unknown:
            raise ProfileError(f"unknown parameter: {unknown[0]}")

        validated: dict[str, int | None] = {}
        for name, spec in specs.items():
            value = supplied[name] if name in supplied else spec.default
            validated[name] = spec.validate(value)
        return validated


def fake_test_profile(executable_path: str | Path) -> LaunchProfile:
    """Build the only runnable profile used by Phase 2G1 tests.

    The executable path is supplied by the test/companion config side, never by a
    frontend/backend request. Real server profiles are intentionally not
    registered here in Phase 2G2.
    """

    return LaunchProfile(
        profile_id="fake_test",
        executable_path=Path(executable_path),
        argv_template=(
            "{executable}",
            "--model",
            "{model_path}",
            "--port",
            "{port}",
            "--ctx-size",
            "{ctx_size}",
            "--gpu-layers",
            "{gpu_layers}",
            "--threads",
            "{threads}",
        ),
        parameters=(
            TypedParameter("port", "int", 18080, 1024, 65535),
            TypedParameter("ctx_size", "int", 2048, 512, 131072),
            TypedParameter("gpu_layers", "int", 0, 0, 999),
            TypedParameter("threads", "int", 2, 1, 256),
        ),
        description="Phase 2G1 fake executable test profile only.",
        runnable=True,
    )


REAL_LLAMA_SERVER_PROFILE_IDS = frozenset({"llama_cpp_gpu_default", "llama_server_gpu_default"})
SAFE_LLAMA_HOSTS = frozenset({"127.0.0.1", "0.0.0.0", "localhost"})


def real_llama_server_profile(
    profile_id: str,
    executable_path: str | Path,
    *,
    host: str = "127.0.0.1",
    default_parameters: dict[str, int] | None = None,
    readiness_timeout_seconds: float = 30.0,
) -> LaunchProfile:
    """Build an explicit Linux llama-server profile from companion config only."""

    if profile_id not in REAL_LLAMA_SERVER_PROFILE_IDS:
        raise ProfileError("unknown real llama-server profile id")
    safe_host = host.strip() if isinstance(host, str) else ""
    if safe_host not in SAFE_LLAMA_HOSTS:
        raise ProfileError("profile host is not allowed")

    defaults = dict(default_parameters or {})
    specs = (
        TypedParameter("port", "int", defaults.get("port", 8080), 1024, 65535),
        TypedParameter("ctx_size", "int", defaults.get("ctx_size", 8192), 512, 131072),
        TypedParameter("gpu_layers", "int", defaults.get("gpu_layers", 999), 0, 999),
        TypedParameter("threads", "int", defaults.get("threads", 8), 1, 256),
    )
    for spec in specs:
        spec.validate(spec.default)
    return LaunchProfile(
        profile_id=profile_id,
        executable_path=Path(executable_path),
        argv_template=(
            "{executable}",
            "-m",
            "{model_path}",
            "--host",
            "{host}",
            "--port",
            "{port}",
            "-c",
            "{ctx_size}",
            "-ngl",
            "{gpu_layers}",
            "--threads",
            "{threads}",
        ),
        parameters=specs,
        description="Explicit Linux llama.cpp llama-server profile.",
        runnable=True,
        host=safe_host,
        requires_readiness=True,
        readiness_timeout_seconds=max(1.0, min(float(readiness_timeout_seconds), 120.0)),
        readiness_interval_seconds=0.25,
    )
