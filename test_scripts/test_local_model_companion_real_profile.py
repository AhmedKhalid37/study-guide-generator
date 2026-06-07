"""Tests for LMM Phase 2G5 explicit real llama-server profile hardening.

This sandbox can block TCP binds, so readiness success is exercised by
monkeypatching the manager's HTTP readiness probe. The live validation harness
exercises the real /v1/models network path when llama-server is available.

    python test_scripts/test_local_model_companion_real_profile.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.local_model_companion import companion  # noqa: E402
from tools.local_model_companion.config import ApprovedRoot, CompanionConfig, load_config  # noqa: E402
from tools.local_model_companion.model_library import scan_models  # noqa: E402
from tools.local_model_companion.process_manager import ManagedServerProcessManager  # noqa: E402
from tools.local_model_companion.profiles import real_llama_server_profile  # noqa: E402

results: list[tuple[str, bool]] = []
_NEXT_PORT = 19100


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _free_port() -> int:
    global _NEXT_PORT
    _NEXT_PORT += 1
    return _NEXT_PORT


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o700)


def _write_sleeping_server(path: Path) -> None:
    _write_executable(
        path,
        """#!/usr/bin/env python3
import argparse
import signal
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("-m", required=True)
parser.add_argument("--host", required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("-c", type=int, required=True)
parser.add_argument("-ngl", type=int, required=True)
parser.add_argument("--threads", type=int, required=True)
args = parser.parse_args()
print(
    f"ready fake model={args.m} Authorization: Bearer tok-real-profile-secret "
    f"http://user:pass@127.0.0.1:{args.port}/v1/models --threads /tmp/private.sock",
    flush=True,
)
running = True
signal.signal(signal.SIGTERM, lambda signum, frame: globals().__setitem__("running", False))
while running:
    time.sleep(0.05)
sys.exit(0)
""",
    )


def _write_failing_server(path: Path, message: str) -> None:
    _write_executable(
        path,
        f"""#!/usr/bin/env python3
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("-m", required=True)
parser.add_argument("--host", required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("-c", type=int, required=True)
parser.add_argument("-ngl", type=int, required=True)
parser.add_argument("--threads", type=int, required=True)
parser.parse_args()
print({message!r}, flush=True)
sys.exit(1)
""",
    )


def _cfg(root: Path) -> CompanionConfig:
    return CompanionConfig((ApprovedRoot("models", root.resolve(strict=False), True),), configured=True)


def _model_id(cfg: CompanionConfig) -> str:
    return str(scan_models(cfg)["models"][0]["id"])


def _profile(exe: Path, *, timeout: float = 1.5):
    return real_llama_server_profile(
        "llama_cpp_gpu_default",
        exe,
        host="0.0.0.0",
        default_parameters={"port": 8080, "ctx_size": 8192, "gpu_layers": 999, "threads": 8},
        readiness_timeout_seconds=timeout,
    )


def _manager(base: Path, cfg: CompanionConfig, exe: Path, *, timeout: float = 1.5) -> ManagedServerProcessManager:
    manager = ManagedServerProcessManager(cfg, base / "runtime", [_profile(exe, timeout=timeout)])
    manager._port_available = lambda port: True
    return manager


def _start_payload(port: int) -> dict[str, int]:
    return {"port": port, "ctx_size": 4096, "gpu_layers": 1, "threads": 2}


def _pid_dead(pid: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        state = Path("/proc") / str(pid) / "stat"
        try:
            if state.read_text(encoding="utf-8", errors="replace").rsplit(") ", 1)[1].split()[0] == "Z":
                return True
        except OSError:
            return True
        time.sleep(0.05)
    return False


def run() -> int:
    with tempfile.TemporaryDirectory(prefix="lmm_real_profile_") as td:
        tmp = Path(td)
        root = tmp / "models"
        root.mkdir()
        model = root / "gemma-Q4_K_M.gguf"
        model.write_bytes(b"gguf")
        cfg = _cfg(root)
        model_id = _model_id(cfg)

        ready_exe = tmp / "ready_llama_server.py"
        _write_sleeping_server(ready_exe)
        profile = _profile(ready_exe)
        argv = _manager(tmp / "argv", cfg, ready_exe)._build_argv(
            profile,
            ready_exe.resolve(strict=True),
            model.resolve(strict=True),
            profile.validate_parameters({"port": 18111, "ctx_size": 4096, "gpu_layers": 1, "threads": 2}),
        )
        check(
            "argv: real profile is centralized array with configured executable/model/host/typed params",
            argv == [
                str(ready_exe.resolve(strict=True)),
                "-m",
                str(model.resolve(strict=True)),
                "--host",
                "0.0.0.0",
                "--port",
                "18111",
                "-c",
                "4096",
                "-ngl",
                "1",
                "--threads",
                "2",
            ],
            detail=str(argv),
        )

        config_path = tmp / "companion.json"
        config_path.write_text(
            json.dumps(
                {
                    "approved_roots": [{"id": "models", "path": str(root), "recursive": True}],
                    "token": "local-test-token",
                    "process_runtime_dir": str(tmp / "runtime-from-config"),
                    "profiles": {
                        "llama_cpp_gpu_default": {
                            "executable": str(ready_exe),
                            "host": "0.0.0.0",
                            "default_parameters": {
                                "port": 18112,
                                "ctx_size": 8192,
                                "gpu_layers": 999,
                                "threads": 8,
                            },
                            "readiness_timeout_seconds": 2,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        loaded = load_config(config_path)
        state = companion.CompanionState(loaded)
        configured_profile = state.process_manager.profiles.get("llama_cpp_gpu_default") if state.process_manager else None
        check(
            "config: explicit real profile parses without default executable",
            configured_profile is not None
            and configured_profile.executable_path == ready_exe.resolve(strict=False)
            and configured_profile.requires_readiness is True
            and configured_profile.host == "0.0.0.0",
            detail=str(configured_profile),
        )

        injected = _manager(tmp / "inject", cfg, ready_exe).start_managed_server(
            model_id,
            "llama_cpp_gpu_default",
            {"port": _free_port(), "ctx_size": 4096, "gpu_layers": 1, "threads": 2, "args": "--bad"},
        )
        check(
            "params: request cannot inject args/executable/model path",
            injected["state"] == "error" and injected["error"]["category"] == "invalid_parameter",
            detail=str(injected),
        )

        missing = _manager(tmp / "missing", cfg, tmp / "missing_llama_server").start_managed_server(
            model_id,
            "llama_cpp_gpu_default",
            _start_payload(_free_port()),
        )
        check(
            "executable: missing executable is safe error",
            missing["state"] == "error" and missing["error"]["category"] == "executable_missing",
            detail=str(missing),
        )

        not_exec = tmp / "not_executable"
        not_exec.write_text("#!/bin/sh\n", encoding="utf-8")
        denied = _manager(tmp / "denied", cfg, not_exec).start_managed_server(
            model_id,
            "llama_cpp_gpu_default",
            _start_payload(_free_port()),
        )
        check(
            "executable: non-executable path is permission_denied",
            denied["state"] == "error" and denied["error"]["category"] == "permission_denied",
            detail=str(denied),
        )

        ready_mgr = _manager(tmp / "ready", cfg, ready_exe)
        ready_mgr._readiness_succeeded = lambda port: True
        ready_port = _free_port()
        ready = ready_mgr.start_managed_server(model_id, "llama_cpp_gpu_default", _start_payload(ready_port))
        ready_state = json.loads(ready_mgr.state_path.read_text(encoding="utf-8"))
        ready_pid = int(ready_state["pid"])
        check(
            "readiness: success promotes starting to running",
            ready["state"] == "running" and ready["managed"] is True and ready["port"] == ready_port and ready["error"] is None,
            detail=str(ready),
        )
        ready_stop = ready_mgr.stop_managed_server(grace_seconds=2)
        check(
            "stop: real-profile process group stops tracked child",
            ready_stop["state"] == "stopped" and _pid_dead(ready_pid),
            detail=str(ready_stop),
        )

        delayed_mgr = _manager(tmp / "delayed", cfg, ready_exe, timeout=3.0)
        readiness_at = time.monotonic() + 0.4
        delayed_mgr._readiness_succeeded = lambda port: time.monotonic() >= readiness_at
        delayed_port = _free_port()
        delayed_result: dict[str, object] = {}

        def _start_delayed() -> None:
            delayed_result.update(
                delayed_mgr.start_managed_server(model_id, "llama_cpp_gpu_default", _start_payload(delayed_port))
            )

        thread = threading.Thread(target=_start_delayed)
        thread.start()
        observed_starting = False
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and thread.is_alive():
            if delayed_mgr.state_path.exists():
                state_data = json.loads(delayed_mgr.state_path.read_text(encoding="utf-8"))
                if state_data.get("status") == "starting":
                    observed_starting = True
                    break
            time.sleep(0.02)
        thread.join(timeout=5)
        check(
            "state: starting is recorded before readiness and running after readiness",
            observed_starting and delayed_result.get("state") == "running",
            detail=str(delayed_result),
        )
        delayed_mgr.stop_managed_server(grace_seconds=2)

        timeout_mgr = _manager(tmp / "timeout", cfg, ready_exe, timeout=0.4)
        timeout_mgr._readiness_succeeded = lambda port: False
        timeout_port = _free_port()
        timeout_result = timeout_mgr.start_managed_server(model_id, "llama_cpp_gpu_default", _start_payload(timeout_port))
        timeout_state = json.loads(timeout_mgr.state_path.read_text(encoding="utf-8"))
        timeout_pid = int(timeout_state["pid"])
        status_after_timeout = timeout_mgr.get_managed_server_status()
        check(
            "readiness: timeout records stable error and does not restart",
            timeout_result["state"] == "error"
            and timeout_result["error"]["category"] == "readiness_timeout"
            and status_after_timeout["state"] == "error"
            and _pid_dead(timeout_pid),
            detail=str({"start": timeout_result, "status": status_after_timeout}),
        )

        oom_exe = tmp / "oom_llama_server.py"
        _write_failing_server(oom_exe, "CUDA out of memory while loading model")
        oom = _manager(tmp / "oom", cfg, oom_exe).start_managed_server(
            model_id,
            "llama_cpp_gpu_default",
            _start_payload(_free_port()),
        )
        check(
            "logs: OOM-like failure maps to model_may_be_too_large",
            oom["state"] == "crashed" and oom["error"]["category"] == "model_may_be_too_large",
            detail=str(oom),
        )

        load_exe = tmp / "load_fail_llama_server.py"
        _write_failing_server(load_exe, "failed to load model: invalid gguf")
        load_fail = _manager(tmp / "load_fail", cfg, load_exe).start_managed_server(
            model_id,
            "llama_cpp_gpu_default",
            _start_payload(_free_port()),
        )
        check(
            "logs: bad GGUF/load failure maps to model_load_failed",
            load_fail["state"] == "crashed" and load_fail["error"]["category"] == "model_load_failed",
            detail=str(load_fail),
        )

        conflict_mgr = _manager(tmp / "port", cfg, ready_exe)
        conflict_mgr._port_available = lambda port: False
        conflict = conflict_mgr.start_managed_server(
            model_id,
            "llama_cpp_gpu_default",
            _start_payload(_free_port()),
        )
        check(
            "port: port in use rejected before launch",
            conflict["state"] == "error" and conflict["error"]["category"] == "port_in_use",
            detail=str(conflict),
        )

        safe_blob = _blob(
            {
                "ready": ready,
                "timeout": timeout_result,
                "oom": oom,
                "load": load_fail,
                "status": status_after_timeout,
            }
        )
        forbidden = (
            str(tmp),
            str(root),
            str(model),
            "tok-real-profile-secret",
            "Authorization",
            "user:pass",
            "/tmp/private.sock",
            "--threads",
            "argv",
        )
        check(
            "safe DTO: no token/socket/absolute path/raw argv leaks",
            all(item not in safe_blob for item in forbidden),
            detail=safe_blob,
        )

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
