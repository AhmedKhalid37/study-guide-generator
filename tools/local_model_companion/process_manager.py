"""Private process-control internals for the local model companion.

Phase 2G1 exposes no HTTP route and launches no real llama-server profile. The
only runnable profile is supplied by tests/config as a safe fake executable.
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CompanionConfig
from .model_library import ScanLimits, scan_models
from .profiles import LaunchProfile, ProfileError

STATE_VERSION = 1
STATE_FILENAME = "managed_server_state.json"
LOG_FILENAME = "managed_server.log"
MAX_LOG_BYTES = 64 * 1024
MAX_LOG_TAIL_BYTES = 4096


@dataclass(frozen=True)
class ResolvedModel:
    model_id: str
    root_id: str
    path: Path
    relative_path: str


class ProcessManagerError(ValueError):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category
        self.message = message


class ManagedServerProcessManager:
    def __init__(
        self,
        config: CompanionConfig,
        runtime_dir: str | os.PathLike[str],
        profiles: list[LaunchProfile] | tuple[LaunchProfile, ...],
        *,
        scan_limits: ScanLimits | None = None,
    ):
        self.config = config
        self.runtime_dir = Path(runtime_dir)
        self.profiles = {profile.profile_id: profile for profile in profiles}
        self.scan_limits = scan_limits or ScanLimits()
        self.state_path = self.runtime_dir / STATE_FILENAME
        self.log_path = self.runtime_dir / LOG_FILENAME

    def start_managed_server(
        self,
        model_id: str,
        profile_id: str,
        parameters: dict[str, Any] | None = None,
        *,
        library_records: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        self._ensure_runtime_dir()
        existing = self._load_state()
        if existing is not None:
            identity = self._check_identity(existing)
            if identity == "running":
                return self._safe_status(existing, public_state="already_running", error_category="already_running")
            if identity in ("identity_uncertain", "foreign"):
                self._write_state({**existing, "status": "unknown", "last_error": "tracked PID identity is uncertain"})
                return self._safe_status(existing, public_state="unknown", error_category="identity_uncertain")
            self._clear_state()

        try:
            profile = self._profile(profile_id)
            params = profile.validate_parameters(parameters)
            port = params.get("port")
            if not isinstance(port, int):
                raise ProcessManagerError("invalid_parameter", "profile requires an integer port")
            if not self._port_available(port):
                raise ProcessManagerError("port_in_use", "requested port is already in use")
            executable = self._validate_executable(profile)
            model = self._resolve_model(model_id, library_records)
            argv = self._build_argv(profile, executable, model.path, params)
        except ProfileError as exc:
            return self._stopped_error("invalid_parameter", str(exc))
        except ProcessManagerError as exc:
            return self._stopped_error(exc.category, exc.message)

        log_handle = self._open_log_for_append()
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                close_fds=True,
                shell=False,
            )
        except OSError as exc:
            log_handle.close()
            return self._stopped_error("launch_failed", f"unable to launch executable: {exc.__class__.__name__}")

        started_at = _now_iso()
        time.sleep(0.05)
        if process.poll() is not None:
            process.wait(timeout=0)
            log_handle.close()
            return self._stopped_error("launch_failed", "managed process exited immediately")

        state = {
            "version": STATE_VERSION,
            "pid": process.pid,
            "model_id": model.model_id,
            "root_id": model.root_id,
            "profile_id": profile.profile_id,
            "port": port,
            "params": params,
            "started_at": started_at,
            "executable_path": str(executable),
            "executable_fingerprint": self._file_fingerprint(executable),
            "process_start_ticks": self._proc_start_ticks(process.pid),
            "private_model_path": str(model.path),
            "argv_redacted": self._redacted_argv(argv, model.path),
            "status": "running",
            "last_error": None,
            "log_path": str(self.log_path),
        }
        self._write_state(state)
        log_handle.close()
        return self._safe_status(state)

    def stop_managed_server(self, *, grace_seconds: float = 5.0) -> dict[str, object]:
        self._ensure_runtime_dir()
        state = self._load_state()
        if state is None:
            return self._status_payload("not_running", error_category="not_running")

        identity = self._check_identity(state)
        if identity == "dead":
            self._clear_state()
            return self._status_payload("stale_pid", error_category="stale_pid")
        if identity != "running":
            next_state = {**state, "status": "unknown", "last_error": "tracked PID identity is uncertain"}
            self._write_state(next_state)
            return self._safe_status(next_state, public_state="unknown", error_category="identity_uncertain")

        pid = _int_or_none(state.get("pid"))
        if pid is None:
            self._clear_state()
            return self._status_payload("not_running", error_category="not_running")

        timeout = max(0.1, min(float(grace_seconds), 30.0))
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._clear_state()
            return self._status_payload("stale_pid", error_category="stale_pid")
        except OSError as exc:
            return self._safe_status(state, public_state="unknown", error_category="stop_failed", error_message=exc.__class__.__name__)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._check_identity(state) == "dead":
                self._reap_if_child(pid)
                self._clear_state()
                return self._status_payload("stopped")
            time.sleep(0.05)

        if self._check_identity(state) != "running":
            next_state = {**state, "status": "unknown", "last_error": "tracked PID identity changed before force kill"}
            self._write_state(next_state)
            return self._safe_status(next_state, public_state="unknown", error_category="identity_uncertain")
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            self._clear_state()
            return self._status_payload("stopped")
        except OSError as exc:
            return self._safe_status(state, public_state="unknown", error_category="stop_failed", error_message=exc.__class__.__name__)

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if self._check_identity(state) == "dead":
                self._reap_if_child(pid)
                self._clear_state()
                return self._status_payload("stopped")
            time.sleep(0.05)
        return self._safe_status(state, public_state="unknown", error_category="stop_timeout")

    def get_managed_server_status(self) -> dict[str, object]:
        self._ensure_runtime_dir()
        state = self._load_state()
        if state is None:
            return self._status_payload("stopped")
        identity = self._check_identity(state)
        if identity == "running":
            return self._safe_status(state, public_state="running")
        if identity == "dead":
            next_state = {**state, "status": "stopped", "last_error": "tracked process is no longer running"}
            self._write_state(next_state)
            return self._safe_status(next_state, public_state="stopped", error_category="stale_pid")
        next_state = {**state, "status": "unknown", "last_error": "tracked PID identity is uncertain"}
        self._write_state(next_state)
        return self._safe_status(next_state, public_state="unknown", error_category="identity_uncertain")

    def _profile(self, profile_id: str) -> LaunchProfile:
        profile = self.profiles.get(profile_id)
        if profile is None or not profile.runnable:
            raise ProcessManagerError("invalid_profile", "unknown or disabled launch profile")
        return profile

    def _resolve_model(
        self,
        model_id: str,
        library_records: list[dict[str, object]] | None,
    ) -> ResolvedModel:
        records = library_records
        if records is None:
            scan = scan_models(self.config, self.scan_limits)
            records = list(scan.get("models", [])) if isinstance(scan.get("models"), list) else []
        record = next((item for item in records if item.get("id") == model_id), None)
        if record is None:
            raise ProcessManagerError("unknown_model", "model id is not in the approved companion library")

        root_id = record.get("root_id")
        relative_path = record.get("relative_path")
        if not isinstance(root_id, str) or not isinstance(relative_path, str):
            raise ProcessManagerError("model_outside_approved_root", "model record is missing safe root metadata")
        root = next((item for item in self.config.approved_roots if item.id == root_id), None)
        if root is None:
            raise ProcessManagerError("model_outside_approved_root", "model root is not approved")
        if _unsafe_relative_path(relative_path):
            raise ProcessManagerError("model_outside_approved_root", "model path is not root-relative")

        root_path = root.path.resolve(strict=False)
        try:
            model_path = (root_path / relative_path).resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise ProcessManagerError("model_outside_approved_root", "model file could not be resolved") from exc
        if not _is_within(model_path, root_path) or not model_path.is_file():
            raise ProcessManagerError("model_outside_approved_root", "model file is outside the approved root")
        return ResolvedModel(model_id=model_id, root_id=root_id, path=model_path, relative_path=relative_path)

    def _validate_executable(self, profile: LaunchProfile) -> Path:
        try:
            executable = profile.executable_path.expanduser().resolve(strict=True)
        except FileNotFoundError as exc:
            raise ProcessManagerError("executable_missing", "profile executable does not exist") from exc
        except OSError as exc:
            raise ProcessManagerError("executable_not_allowed", "profile executable could not be resolved") from exc
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ProcessManagerError("executable_not_allowed", "profile executable is not executable")
        return executable

    def _build_argv(
        self,
        profile: LaunchProfile,
        executable: Path,
        model_path: Path,
        params: dict[str, int | None],
    ) -> list[str]:
        values = {
            "executable": str(executable),
            "model_path": str(model_path),
            **{name: "" if value is None else str(value) for name, value in params.items()},
        }
        argv: list[str] = []
        for token in profile.argv_template:
            placeholders = re.findall(r"{([a-zA-Z0-9_]+)}", token)
            if any(name not in values for name in placeholders):
                raise ProcessManagerError("invalid_profile", "profile template references an unknown value")
            rendered = token
            for name in placeholders:
                rendered = rendered.replace("{" + name + "}", values[name])
            if rendered == "":
                raise ProcessManagerError("invalid_parameter", "profile rendered an empty argv token")
            argv.append(rendered)
        if not argv or argv[0] != str(executable):
            raise ProcessManagerError("invalid_profile", "profile argv must start with the configured executable")
        return argv

    def _check_identity(self, state: dict[str, Any]) -> str:
        pid = _int_or_none(state.get("pid"))
        if pid is None or pid <= 0:
            return "dead"
        proc = Path("/proc") / str(pid)
        if not proc.exists():
            return "dead"
        if self._proc_state(pid) == "Z":
            return "dead"
        expected_exe = state.get("executable_path")
        if not isinstance(expected_exe, str) or not expected_exe:
            return "identity_uncertain"
        current_ticks = self._proc_start_ticks(pid)
        expected_ticks = _int_or_none(state.get("process_start_ticks"))
        if current_ticks is not None and expected_ticks is not None and current_ticks != expected_ticks:
            return "foreign"

        expected_path = Path(expected_exe)
        cmdline = self._proc_cmdline(pid)
        exe_matches = False
        try:
            exe_matches = (proc / "exe").resolve(strict=True) == expected_path
        except OSError:
            exe_matches = False
        cmdline_matches = str(expected_path) in cmdline[:3]
        if not exe_matches and not cmdline_matches:
            return "foreign"
        return "running"

    def _proc_cmdline(self, pid: int) -> list[str]:
        try:
            raw = (Path("/proc") / str(pid) / "cmdline").read_bytes()
        except OSError:
            return []
        return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]

    def _proc_start_ticks(self, pid: int) -> int | None:
        try:
            text = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        try:
            after_comm = text.rsplit(") ", 1)[1]
            fields = after_comm.split()
            return int(fields[19])
        except (IndexError, ValueError):
            return None

    def _proc_state(self, pid: int) -> str | None:
        try:
            text = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        try:
            return text.rsplit(") ", 1)[1].split()[0]
        except IndexError:
            return None

    def _reap_if_child(self, pid: int) -> None:
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        except OSError:
            return

    def _file_fingerprint(self, path: Path) -> dict[str, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return {
            "dev": stat.st_dev,
            "ino": stat.st_ino,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }

    def _port_available(self, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError:
            return False
        with sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    def _load_state(self) -> dict[str, Any] | None:
        try:
            raw = self.state_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"status": "unknown", "last_error": "process state file is corrupt"}
        if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
            return {"status": "unknown", "last_error": "process state file has an unsupported schema"}
        return data

    def _write_state(self, state: dict[str, Any]) -> None:
        self._ensure_runtime_dir()
        tmp_path = self.state_path.with_suffix(".tmp")
        payload = json.dumps(state, indent=2, sort_keys=True)
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
        os.replace(tmp_path, self.state_path)
        try:
            os.chmod(self.state_path, 0o600)
        except OSError:
            pass

    def _clear_state(self) -> None:
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return

    def _ensure_runtime_dir(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.runtime_dir, 0o700)
        except OSError:
            pass

    def _open_log_for_append(self):
        self._ensure_runtime_dir()
        if self.log_path.exists() and self.log_path.stat().st_size > MAX_LOG_BYTES:
            self.log_path.write_text("", encoding="utf-8")
        fd = os.open(self.log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        return os.fdopen(fd, "ab", buffering=0)

    def _safe_status(
        self,
        state_data: dict[str, Any],
        *,
        public_state: str | None = None,
        error_category: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, object]:
        return self._status_payload(
            public_state or str(state_data.get("status") or "unknown"),
            model_id=_safe_str(state_data.get("model_id")),
            root_id=_safe_str(state_data.get("root_id")),
            profile_id=_safe_str(state_data.get("profile_id")),
            port=_int_or_none(state_data.get("port")),
            params=state_data.get("params") if isinstance(state_data.get("params"), dict) else None,
            started_at=_safe_str(state_data.get("started_at")),
            error_category=error_category,
            error_message=error_message or _safe_str(state_data.get("last_error")),
            log_tail=self._safe_log_tail(),
        )

    def _status_payload(
        self,
        state: str,
        *,
        model_id: str | None = None,
        root_id: str | None = None,
        profile_id: str | None = None,
        port: int | None = None,
        params: dict[str, object] | None = None,
        started_at: str | None = None,
        error_category: str | None = None,
        error_message: str | None = None,
        log_tail: str | None = None,
    ) -> dict[str, object]:
        error = None
        if error_category:
            error = {"category": error_category, "message": _sanitize_text(error_message or error_category)}
        return {
            "ok": True,
            "state": state,
            "managed": state in {"running", "already_running"},
            "model_id": model_id,
            "root_id": root_id,
            "profile_id": profile_id,
            "port": port,
            "params": dict(params or {}),
            "started_at": started_at,
            "error": error,
            "log_tail": log_tail,
        }

    def _stopped_error(self, category: str, message: str) -> dict[str, object]:
        return self._status_payload("stopped", error_category=category, error_message=message)

    def _safe_log_tail(self) -> str | None:
        try:
            with self.log_path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - MAX_LOG_TAIL_BYTES))
                data = handle.read(MAX_LOG_TAIL_BYTES)
        except OSError:
            return None
        text = data.decode("utf-8", errors="replace")
        if size > MAX_LOG_TAIL_BYTES and "\n" in text:
            text = text.split("\n", 1)[1]
        return _sanitize_text(text)[-MAX_LOG_TAIL_BYTES:]

    def _redacted_argv(self, argv: list[str], model_path: Path) -> list[str]:
        redacted: list[str] = []
        model_text = str(model_path)
        for token in argv:
            if token == model_text:
                redacted.append("<model_path>")
            else:
                redacted.append(_sanitize_text(token))
        return redacted


def start_managed_server(
    manager: ManagedServerProcessManager,
    model_id: str,
    profile_id: str,
    parameters: dict[str, Any] | None = None,
    *,
    library_records: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return manager.start_managed_server(model_id, profile_id, parameters, library_records=library_records)


def stop_managed_server(manager: ManagedServerProcessManager, *, grace_seconds: float = 5.0) -> dict[str, object]:
    return manager.stop_managed_server(grace_seconds=grace_seconds)


def get_managed_server_status(manager: ManagedServerProcessManager) -> dict[str, object]:
    return manager.get_managed_server_status()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _safe_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _unsafe_relative_path(value: str) -> bool:
    path = Path(value)
    return path.is_absolute() or any(part in ("", ".", "..") for part in path.parts)


def _sanitize_text(text: str) -> str:
    safe = str(text)
    safe = re.sub(r"Authorization:\s*Bearer\s+\S+", "<authorization>", safe, flags=re.IGNORECASE)
    safe = re.sub(r"https?://[^\s\"']+", "<url>", safe)
    safe = re.sub(r"/(?:tmp|home|mnt|var|Users)/[^\s\"']+", "<path>", safe)
    safe = re.sub(r"tok-[A-Za-z0-9_.-]+", "<token>", safe)
    safe = re.sub(r"sk-[A-Za-z0-9_.-]+", "<token>", safe)
    safe = re.sub(r"(?<!\S)--[A-Za-z0-9][A-Za-z0-9_-]*", "<arg>", safe)
    return safe
