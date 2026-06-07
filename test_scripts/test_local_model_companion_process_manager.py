"""Tests for LMM Phase 2G1 companion process-manager internals.

    python test_scripts/test_local_model_companion_process_manager.py
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.local_model_companion import companion, process_manager, profiles  # noqa: E402
from tools.local_model_companion.config import ApprovedRoot, CompanionConfig  # noqa: E402
from tools.local_model_companion.model_library import scan_models  # noqa: E402
from tools.local_model_companion.process_manager import ManagedServerProcessManager  # noqa: E402
from tools.local_model_companion.profiles import fake_test_profile  # noqa: E402

results: list[tuple[str, bool]] = []
_NEXT_PORT = 18080


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _free_port() -> int:
    global _NEXT_PORT
    _NEXT_PORT += 1
    return _NEXT_PORT


def _pid_dead(pid: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.05)
    return False


def _write_fake_executable(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import argparse
import signal
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--ctx-size", type=int, required=True)
parser.add_argument("--gpu-layers", type=int, required=True)
parser.add_argument("--threads", type=int, required=True)
args = parser.parse_args()
running = True

def stop(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, stop)
print(
    f"fake-start model={args.model} port={args.port} "
    f"Authorization: Bearer tok-fake-secret http://127.0.0.1:{args.port}/v1 /tmp/companion.sock",
    flush=True,
)
while running:
    time.sleep(0.05)
print("fake-stop", flush=True)
sys.exit(0)
""",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _cfg(root: Path) -> CompanionConfig:
    return CompanionConfig((ApprovedRoot("default", root.resolve(strict=False), True),), configured=True)


def _manager(base: Path, cfg: CompanionConfig, exe: Path) -> ManagedServerProcessManager:
    manager = ManagedServerProcessManager(cfg, base / "runtime", [fake_test_profile(exe)])
    manager._port_available = lambda port: True
    return manager


def _model_id(cfg: CompanionConfig) -> str:
    return str(scan_models(cfg)["models"][0]["id"])


def _recorded_pid(manager: ManagedServerProcessManager) -> int:
    return int(json.loads(manager.state_path.read_text(encoding="utf-8"))["pid"])


def _write_fake_state(
    manager: ManagedServerProcessManager,
    *,
    pid: int,
    model_id: str,
    exe: Path,
) -> None:
    manager._write_state(
        {
            "version": process_manager.STATE_VERSION,
            "pid": pid,
            "model_id": model_id,
            "root_id": "default",
            "profile_id": "fake_test",
            "port": _free_port(),
            "params": {"port": _free_port(), "ctx_size": 4096},
            "started_at": "2026-06-06T00:00:00Z",
            "executable_path": str(exe.resolve(strict=True)),
            "process_start_ticks": None,
            "status": "running",
            "last_error": None,
        }
    )


def run() -> int:
    managed_pids: list[int] = []
    foreign_process: subprocess.Popen[bytes] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="lmm_pm_") as td:
            tmp = Path(td)
            root = tmp / "models"
            root.mkdir()
            model = root / "gemma-Q4_K_M.gguf"
            model.write_bytes(b"gguf")
            exe = tmp / "fake_server.py"
            _write_fake_executable(exe)
            cfg = _cfg(root)
            model_id = _model_id(cfg)

            mgr = _manager(tmp / "case_start", cfg, exe)
            port = _free_port()
            start = mgr.start_managed_server(model_id, "fake_test", {"port": port, "ctx_size": 4096})
            pid = _recorded_pid(mgr)
            managed_pids.append(pid)
            check(
                "start: fake executable starts successfully",
                start["state"] == "running"
                and start["model_id"] == model_id
                and start["profile_id"] == "fake_test"
                and start["port"] == port
                and start["managed"] is True,
                detail=str(start),
            )

            status = mgr.get_managed_server_status()
            check(
                "status: tracked fake process shows running",
                status["state"] == "running" and status["model_id"] == model_id and status["error"] is None,
                detail=str(status),
            )

            already = mgr.start_managed_server(model_id, "fake_test", {"port": _free_port(), "ctx_size": 4096})
            check(
                "start: while running returns already_running",
                already["state"] == "already_running" and already["error"]["category"] == "already_running",
                detail=str(already),
            )

            stop = mgr.stop_managed_server(grace_seconds=2)
            check(
                "stop: tracked fake process stops",
                stop["state"] == "stopped" and stop["error"] is None and _pid_dead(pid),
                detail=str(stop),
            )

            stop_again = mgr.stop_managed_server()
            check(
                "stop: not running returns not_running",
                stop_again["state"] == "not_running" and stop_again["error"]["category"] == "not_running",
                detail=str(stop_again),
            )

            unknown_model = _manager(tmp / "case_unknown_model", cfg, exe).start_managed_server(
                "gguf_unknown", "fake_test", {"port": _free_port(), "ctx_size": 4096}
            )
            check(
                "start: rejects unknown model id",
                unknown_model["state"] == "stopped" and unknown_model["error"]["category"] == "unknown_model",
                detail=str(unknown_model),
            )

            outside_record = {"id": "gguf_outside", "root_id": "default", "relative_path": "../outside.gguf"}
            outside_res = _manager(tmp / "case_outside", cfg, exe).start_managed_server(
                "gguf_outside",
                "fake_test",
                {"port": _free_port(), "ctx_size": 4096},
                library_records=[outside_record],
            )
            check(
                "start: rejects model outside approved root",
                outside_res["state"] == "stopped" and outside_res["error"]["category"] == "model_outside_approved_root",
                detail=str(outside_res),
            )

            unknown_profile = _manager(tmp / "case_profile", cfg, exe).start_managed_server(
                model_id, "gpu_default", {"port": _free_port(), "ctx_size": 4096}
            )
            invalid_params = _manager(tmp / "case_params", cfg, exe).start_managed_server(
                model_id, "fake_test", {"port": 80, "ctx_size": "4096"}
            )
            check(
                "start: rejects unknown profile",
                unknown_profile["state"] == "stopped" and unknown_profile["error"]["category"] == "invalid_profile",
                detail=str(unknown_profile),
            )
            check(
                "start: rejects invalid typed params",
                invalid_params["state"] == "stopped" and invalid_params["error"]["category"] == "invalid_parameter",
                detail=str(invalid_params),
            )

            conflict_mgr = _manager(tmp / "case_port", cfg, exe)
            conflict_mgr._port_available = lambda port: False
            conflict = conflict_mgr.start_managed_server(
                model_id, "fake_test", {"port": _free_port(), "ctx_size": 4096}
            )
            check(
                "start: rejects port conflict",
                conflict["state"] == "stopped" and conflict["error"]["category"] == "port_in_use",
                detail=str(conflict),
            )

            stale_mgr = _manager(tmp / "case_stale", cfg, exe)
            _write_fake_state(stale_mgr, pid=99999999, model_id=model_id, exe=exe)
            stale_status = stale_mgr.get_managed_server_status()
            check(
                "status: stale/dead PID becomes safe stale state",
                stale_status["state"] == "stopped" and stale_status["error"]["category"] == "stale_pid",
                detail=str(stale_status),
            )

            foreign_process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            foreign_mgr = _manager(tmp / "case_foreign", cfg, exe)
            _write_fake_state(foreign_mgr, pid=foreign_process.pid, model_id=model_id, exe=exe)
            foreign_stop = foreign_mgr.stop_managed_server(grace_seconds=0.1)
            check(
                "stop: foreign PID is not killed",
                foreign_stop["state"] == "unknown"
                and foreign_stop["error"]["category"] == "identity_uncertain"
                and foreign_process.poll() is None,
                detail=str(foreign_stop),
            )

            redact_mgr = _manager(tmp / "case_redact", cfg, exe)
            redact_port = _free_port()
            redact_start = redact_mgr.start_managed_server(model_id, "fake_test", {"port": redact_port, "ctx_size": 4096})
            redact_pid = _recorded_pid(redact_mgr)
            managed_pids.append(redact_pid)
            time.sleep(0.2)
            redact_status = redact_mgr.get_managed_server_status()
            safe_blob = _blob({"start": redact_start, "status": redact_status})
            state_blob = redact_mgr.state_path.read_text(encoding="utf-8")
            forbidden_safe = (
                str(root),
                str(model),
                str(tmp),
                "tok-fake-secret",
                "Authorization",
                "/tmp/companion.sock",
                f"http://127.0.0.1:{redact_port}/v1",
                "argv_redacted",
                "--model",
            )
            check(
                "safe DTO: no absolute model path, token, socket, Authorization, full URL, or raw argv",
                all(item not in safe_blob for item in forbidden_safe),
                detail=safe_blob,
            )
            check(
                "state file: contains no token",
                "tok-fake-secret" not in state_blob and "Authorization" not in state_blob,
                detail=state_blob,
            )
            redact_mgr.stop_managed_server(grace_seconds=2)

            manager_source = inspect.getsource(process_manager)
            profile_source = inspect.getsource(profiles)
            check(
                "source: process manager uses Popen without shell execution",
                "subprocess.Popen(" in manager_source
                and "shell=False" in manager_source
                and "shell=True" not in manager_source
                and "os.system(" not in manager_source,
            )
            fake_profile = fake_test_profile(exe)
            check(
                "profiles: no free-form args and typed bounded fake params only",
                set(fake_profile.parameter_map()) == {"port", "ctx_size", "gpu_layers", "threads"}
                and "{model_path}" in fake_profile.argv_template
                and "args" not in profile_source.lower(),
            )

            api_source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(encoding="utf-8")
            companion_source = inspect.getsource(companion)
            check(
                "routes: no FastAPI start/stop/restart routes",
                all(route not in api_source for route in (
                    "/api/local-model/server/start",
                    "/api/local-model/server/stop",
                    "/api/local-model/server/restart",
                )),
            )
            check(
                "routes: companion HTTP process endpoints delegate to process manager",
                all(route in companion_source for route in ("/server/start", "/server/stop", "/server/restart"))
                and "subprocess.Popen(" not in companion_source
                and "shell=True" not in companion_source,
            )
    finally:
        for pid in managed_pids:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
        if foreign_process is not None and foreign_process.poll() is None:
            foreign_process.terminate()
            try:
                foreign_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                foreign_process.kill()
                foreign_process.wait(timeout=2)

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
