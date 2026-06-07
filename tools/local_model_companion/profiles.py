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
