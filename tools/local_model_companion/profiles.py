"""Safe internal launch profile definitions for companion-managed processes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re


class ProfileError(ValueError):
    """Raised when a profile definition or parameter payload is invalid."""


@dataclass(frozen=True)
class TypedParameter:
    name: str
    kind: str
    default: int | bool | str | None
    minimum: int | None = None
    maximum: int | None = None
    allowed_values: tuple[str, ...] = ()
    label: str = ""
    help_text: str = ""
    required: bool = True

    def validate(self, value: Any) -> int | bool | str | None:
        if value is None:
            if self.required:
                raise ProfileError(f"{self.name} is required")
            return None
        if self.kind in {"int", "integer"}:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ProfileError(f"{self.name} must be an integer")
            if self.minimum is not None and value < self.minimum:
                raise ProfileError(f"{self.name} is below minimum {self.minimum}")
            if self.maximum is not None and value > self.maximum:
                raise ProfileError(f"{self.name} is above maximum {self.maximum}")
            return value
        if self.kind in {"bool", "boolean"}:
            if not isinstance(value, bool):
                raise ProfileError(f"{self.name} must be a boolean")
            return value
        if self.kind == "enum":
            if not isinstance(value, str):
                raise ProfileError(f"{self.name} must be a string")
            if value not in self.allowed_values:
                raise ProfileError(f"{self.name} is not an allowed value")
            return value
        raise ProfileError(f"{self.name} has unsupported parameter type")

    def metadata(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "integer" if self.kind == "int" else "boolean" if self.kind == "bool" else self.kind,
            "default": self.default,
            "label": self.label or self.name.replace("_", " ").title(),
            "help": self.help_text,
            "required": self.required,
        }
        if self.minimum is not None:
            payload["min"] = self.minimum
        if self.maximum is not None:
            payload["max"] = self.maximum
        if self.allowed_values:
            payload["allowed_values"] = list(self.allowed_values)
        return payload


@dataclass(frozen=True)
class ParameterArgvMapping:
    name: str
    flag: str
    mode: str = "value"

    def render(self, value: int | bool | str | None) -> tuple[str, ...]:
        if value is None:
            return ()
        if self.mode == "value":
            return (self.flag, str(value))
        if self.mode == "flag_when_true":
            return (self.flag,) if value is True else ()
        if self.mode == "flag_when_false":
            return (self.flag,) if value is False else ()
        raise ProfileError("profile has unsupported argv mapping")


@dataclass(frozen=True)
class LaunchProfile:
    profile_id: str
    executable_path: Path
    argv_template: tuple[str, ...]
    parameters: tuple[TypedParameter, ...]
    argv_mappings: tuple[ParameterArgvMapping, ...] = ()
    display_name: str = ""
    description: str = ""
    profile_type: str = "llama_server"
    test_profile: bool = False
    runnable: bool = True
    runnable_reason: str | None = None
    warnings: tuple[str, ...] = ()
    host: str | None = None
    requires_readiness: bool = False
    readiness_timeout_seconds: float = 30.0
    readiness_interval_seconds: float = 0.25

    def parameter_map(self) -> dict[str, TypedParameter]:
        return {item.name: item for item in self.parameters}

    def validate_parameters(self, supplied: dict[str, Any] | None) -> dict[str, int | bool | str | None]:
        supplied = dict(supplied or {})
        specs = self.parameter_map()
        unknown = sorted(set(supplied) - set(specs))
        if unknown:
            raise ProfileError(f"unknown parameter: {unknown[0]}")

        validated: dict[str, int | bool | str | None] = {}
        for name, spec in specs.items():
            value = supplied[name] if name in supplied else spec.default
            validated[name] = spec.validate(value)
        return validated

    def safe_metadata(self) -> dict[str, object]:
        return {
            "id": self.profile_id,
            "display_name": self.display_name or self.profile_id,
            "description": self.description,
            "type": self.profile_type,
            "test_profile": self.test_profile,
            "runnable": self.runnable,
            "runnable_reason": self.runnable_reason,
            "default_parameters": {item.name: item.default for item in self.parameters},
            "parameters": {item.name: item.metadata() for item in self.parameters},
            "warnings": list(self.warnings),
        }


SAFE_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
REAL_LLAMA_SERVER_PROFILE_IDS = frozenset({"llama_cpp_gpu_default", "llama_server_gpu_default"})
SAFE_LLAMA_HOSTS = frozenset({"127.0.0.1", "0.0.0.0", "localhost"})
SAFE_CACHE_TYPES = ("f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1")

LLAMA_SERVER_PARAMETER_SPECS: dict[str, TypedParameter] = {
    "port": TypedParameter(
        "port",
        "integer",
        18080,
        1024,
        65535,
        label="Port",
        help_text="Local port used by the companion-managed server.",
    ),
    "ctx_size": TypedParameter(
        "ctx_size",
        "integer",
        4096,
        512,
        131072,
        label="Context window",
        help_text="Larger context windows use more memory.",
    ),
    "gpu_layers": TypedParameter(
        "gpu_layers",
        "integer",
        0,
        0,
        999,
        label="GPU layers",
        help_text="Very high GPU layer counts can fail with out-of-memory errors on large models.",
    ),
    "threads": TypedParameter(
        "threads",
        "integer",
        8,
        1,
        256,
        label="Threads",
        help_text="CPU worker threads for llama-server.",
    ),
    "parallel": TypedParameter(
        "parallel",
        "integer",
        1,
        1,
        32,
        label="Parallel slots",
        help_text="Concurrent request slots for the managed server.",
    ),
    "cache_type_k": TypedParameter(
        "cache_type_k",
        "enum",
        "f16",
        allowed_values=SAFE_CACHE_TYPES,
        label="K cache type",
        help_text="KV cache K tensor type from the configured allow-list.",
    ),
    "cache_type_v": TypedParameter(
        "cache_type_v",
        "enum",
        "f16",
        allowed_values=SAFE_CACHE_TYPES,
        label="V cache type",
        help_text="KV cache V tensor type from the configured allow-list.",
    ),
    "flash_attention": TypedParameter(
        "flash_attention",
        "boolean",
        False,
        label="Flash attention",
        help_text="Enable llama-server flash attention when the configured build supports it.",
    ),
    "mmap": TypedParameter(
        "mmap",
        "boolean",
        True,
        label="Memory map",
        help_text="Disable only when the configured profile needs --no-mmap.",
    ),
}

LLAMA_SERVER_ARGV_MAPPINGS: tuple[ParameterArgvMapping, ...] = (
    ParameterArgvMapping("port", "--port"),
    ParameterArgvMapping("ctx_size", "-c"),
    ParameterArgvMapping("gpu_layers", "-ngl"),
    ParameterArgvMapping("threads", "--threads"),
    ParameterArgvMapping("parallel", "--parallel"),
    ParameterArgvMapping("cache_type_k", "--cache-type-k"),
    ParameterArgvMapping("cache_type_v", "--cache-type-v"),
    ParameterArgvMapping("flash_attention", "--flash-attn", "flag_when_true"),
    ParameterArgvMapping("mmap", "--no-mmap", "flag_when_false"),
)


def _copy_parameter_spec(name: str, default: Any, overrides: dict[str, Any] | None = None) -> TypedParameter:
    source = LLAMA_SERVER_PARAMETER_SPECS[name]
    override = dict(overrides or {})
    allowed = override.get("allowed_values", source.allowed_values)
    if not isinstance(allowed, tuple):
        allowed = tuple(item for item in allowed if isinstance(item, str)) if isinstance(allowed, list) else source.allowed_values
    spec = TypedParameter(
        name=source.name,
        kind=source.kind,
        default=default,
        minimum=override.get("min", source.minimum),
        maximum=override.get("max", source.maximum),
        allowed_values=allowed,
        label=str(override.get("label") or source.label),
        help_text=str(override.get("help") or source.help_text),
        required=bool(override.get("required", source.required)),
    )
    spec.validate(spec.default)
    return spec


def llama_server_parameters(
    defaults: dict[str, Any] | None,
    parameter_schema: dict[str, Any] | None = None,
) -> tuple[TypedParameter, ...]:
    defaults = dict(defaults or {})
    schema = dict(parameter_schema or {})
    base_names = ["port", "ctx_size", "gpu_layers", "threads"]
    names = list(base_names)
    for name in defaults:
        if name not in names:
            names.append(name)
    for name in schema:
        if name not in names:
            names.append(name)
    unknown = [name for name in names if name not in LLAMA_SERVER_PARAMETER_SPECS]
    if unknown:
        raise ProfileError(f"unknown parameter: {unknown[0]}")

    specs: list[TypedParameter] = []
    for name in names:
        source = LLAMA_SERVER_PARAMETER_SPECS[name]
        default = defaults[name] if name in defaults else source.default
        raw_schema = schema.get(name)
        if raw_schema is not None and not isinstance(raw_schema, dict):
            raise ProfileError(f"{name} schema must be an object")
        specs.append(_copy_parameter_spec(name, default, raw_schema))
    return tuple(specs)


def llama_server_argv_mappings(parameters: tuple[TypedParameter, ...]) -> tuple[ParameterArgvMapping, ...]:
    names = {item.name for item in parameters}
    return tuple(item for item in LLAMA_SERVER_ARGV_MAPPINGS if item.name in names)


def profile_runnable_state(executable_path: str | Path) -> tuple[bool, str | None]:
    path = Path(executable_path)
    try:
        resolved = path.expanduser().resolve(strict=True)
    except FileNotFoundError:
        return False, "executable_missing"
    except OSError:
        return False, "executable_not_allowed"
    if not resolved.is_file():
        return False, "executable_missing"
    try:
        import os

        if not os.access(resolved, os.X_OK):
            return False, "permission_denied"
    except OSError:
        return False, "permission_denied"
    return True, None


def fake_test_profile(executable_path: str | Path) -> LaunchProfile:
    """Build the only runnable profile used by Phase 2G1 tests.

    The executable path is supplied by the test/companion config side, never by a
    frontend/backend request. Real server profiles are intentionally not
    registered here in Phase 2G2.
    """

    runnable, reason = profile_runnable_state(executable_path)
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
            TypedParameter("port", "integer", 18080, 1024, 65535, label="Port"),
            TypedParameter("ctx_size", "integer", 2048, 512, 131072, label="Context window"),
            TypedParameter("gpu_layers", "integer", 0, 0, 999, label="GPU layers"),
            TypedParameter("threads", "integer", 2, 1, 256, label="Threads"),
        ),
        display_name="Fake test",
        description="Phase 2G1 fake executable test profile only.",
        profile_type="fake_test",
        test_profile=True,
        runnable=runnable,
        runnable_reason=reason,
        warnings=("Validation profile only; it does not launch a real model server.",),
    )


def real_llama_server_profile(
    profile_id: str,
    executable_path: str | Path,
    *,
    display_name: str | None = None,
    description: str | None = None,
    host: str = "127.0.0.1",
    default_parameters: dict[str, Any] | None = None,
    parameter_schema: dict[str, Any] | None = None,
    warnings: tuple[str, ...] | list[str] | None = None,
    readiness_timeout_seconds: float = 30.0,
) -> LaunchProfile:
    """Build an explicit Linux llama-server profile from companion config only."""

    if not isinstance(profile_id, str) or not SAFE_PROFILE_ID_RE.match(profile_id):
        raise ProfileError("invalid real llama-server profile id")
    safe_host = host.strip() if isinstance(host, str) else ""
    if safe_host not in SAFE_LLAMA_HOSTS:
        raise ProfileError("profile host is not allowed")

    specs = llama_server_parameters(default_parameters, parameter_schema)
    runnable, reason = profile_runnable_state(executable_path)
    safe_warnings = tuple(item for item in (warnings or ()) if isinstance(item, str) and item.strip())
    if not safe_warnings:
        safe_warnings = (
            "Large models may fail with very high GPU layers.",
            "CPU mode is slower but safer.",
        )
    return LaunchProfile(
        profile_id=profile_id,
        executable_path=Path(executable_path),
        argv_template=(
            "{executable}",
            "-m",
            "{model_path}",
            "--host",
            "{host}",
        ),
        parameters=specs,
        argv_mappings=llama_server_argv_mappings(specs),
        display_name=display_name or profile_id,
        description=description or "Explicit Linux llama.cpp llama-server profile.",
        profile_type="llama_server",
        test_profile=False,
        runnable=runnable,
        runnable_reason=reason,
        warnings=safe_warnings,
        host=safe_host,
        requires_readiness=True,
        readiness_timeout_seconds=max(1.0, min(float(readiness_timeout_seconds), 120.0)),
        readiness_interval_seconds=0.25,
    )


def cpu_safe_llama_server_profile(profile_id: str, executable_path: str | Path) -> LaunchProfile:
    return real_llama_server_profile(
        profile_id,
        executable_path,
        display_name="CPU safe",
        description="Slow but reliable CPU launch.",
        default_parameters={"port": 18080, "ctx_size": 4096, "gpu_layers": 0, "threads": 8, "parallel": 1},
        warnings=("CPU mode is slower but safer.",),
    )
