"""Tests for LMM Phase 2G2 companion Unix-socket process-control API.

    python test_scripts/test_local_model_companion_process_api.py
"""

from __future__ import annotations

import inspect
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.local_model_companion import companion, process_manager, profiles  # noqa: E402
from tools.local_model_companion.config import load_config  # noqa: E402
from tools.local_model_companion.model_library import ScanLimits  # noqa: E402

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


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
for index in range(80):
    print(
        f"fake-log-{index} model={args.model} Authorization: Bearer tok-api-secret "
        f"http://127.0.0.1:{args.port}/v1 /tmp/lmm-secret.sock --model",
        flush=True,
    )
print(
    f"fake-start port={args.port} ctx={args.ctx_size} gpu={args.gpu_layers} threads={args.threads}",
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


def _read_http(sock_path: Path, method: str, path: str, token: str | None, body: dict[str, object] | None = None):
    payload = b""
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: companion",
    ]
    if token is not None:
        headers.append(f"Authorization: Bearer {token}")
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers.append("Content-Type: application/json")
        headers.append(f"Content-Length: {len(payload)}")
    request = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + payload

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(3)
    client.connect(str(sock_path))
    client.sendall(request)
    chunks: list[bytes] = []
    while True:
        try:
            chunk = client.recv(65536)
        except socket.timeout:
            break
        if not chunk:
            break
        chunks.append(chunk)
    client.close()
    raw = b"".join(chunks)
    header, response_body = raw.split(b"\r\n\r\n", 1)
    status_line = header.splitlines()[0].decode("ascii")
    status_code = int(status_line.split()[1])
    return status_code, json.loads(response_body.decode("utf-8"))


class _NonClosingBytesIO(BytesIO):
    def close(self) -> None:
        pass


class _FakeConnection:
    def __init__(self, request: bytes):
        self.reader = BytesIO(request)
        self.writer = _NonClosingBytesIO()

    def makefile(self, mode: str, buffering: int | None = None):  # noqa: ARG002
        if "r" in mode:
            return self.reader
        return self.writer

    def sendall(self, data: bytes) -> None:
        self.writer.write(data)


class _MemoryServer:
    def __init__(self, state: companion.CompanionState):
        self.state = state
        self.server_version = "memory"
        self.sys_version = ""


def _handle_memory(state: companion.CompanionState, method: str, path: str, token: str | None, body: dict[str, object] | None = None):
    payload = b""
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: companion",
    ]
    if token is not None:
        headers.append(f"Authorization: Bearer {token}")
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers.append("Content-Type: application/json")
        headers.append(f"Content-Length: {len(payload)}")
    request = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + payload
    connection = _FakeConnection(request)
    companion.CompanionRequestHandler(connection, ("local", 0), _MemoryServer(state))
    raw = connection.writer.getvalue()
    header, response_body = raw.split(b"\r\n\r\n", 1)
    status_line = header.splitlines()[0].decode("ascii")
    status_code = int(status_line.split()[1])
    return status_code, json.loads(response_body.decode("utf-8"))


class _Client:
    def __init__(self, state: companion.CompanionState, sock_path: Path | None):
        self.state = state
        self.sock_path = sock_path

    def request(self, method: str, path: str, token: str | None, body: dict[str, object] | None = None):
        if self.sock_path is not None:
            return _read_http(self.sock_path, method, path, token, body)
        return _handle_memory(self.state, method, path, token, body)


def _free_bound_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    return sock, port


def _wait_for_state(client: _Client, token: str, state: str, timeout: float = 3.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        _, last = client.request("GET", "/server/status", token)
        if last.get("state") == state:
            return last
        time.sleep(0.05)
    return last


def _safe_start_payload(model_id: str, port: int) -> dict[str, object]:
    return {
        "model_id": model_id,
        "profile_id": "fake_test",
        "parameters": {
            "port": port,
            "ctx_size": 4096,
            "gpu_layers": 0,
            "threads": 2,
        },
    }


def _assert_no_leaks(name: str, payload: Any, forbidden: tuple[str, ...]) -> None:
    blob = _blob(payload)
    check(name, all(item not in blob for item in forbidden), detail=blob)


def run() -> int:
    server = None
    thread = None
    try:
        with tempfile.TemporaryDirectory(prefix="lmm_api_") as td:
            tmp = Path(td)
            root = tmp / "models"
            root.mkdir()
            model = root / "gemma-Q4_K_M.gguf"
            model.write_bytes(b"gguf")
            exe = tmp / "fake_server.py"
            _write_fake_executable(exe)
            runtime = tmp / "runtime"
            sock_path = tmp / "companion.sock"
            token = "test-token"
            config_path = tmp / "companion.json"
            config_path.write_text(
                json.dumps(
                    {
                        "approved_roots": [{"id": "default", "path": str(root), "recursive": True}],
                        "token": token,
                        "process_runtime_dir": str(runtime),
                        "profiles": {"fake_test": {"executable": str(exe)}},
                    }
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            state = companion.CompanionState(cfg, ScanLimits(max_files_inspected=100, max_models_returned=100))
            if state.process_manager is not None:
                state.process_manager._port_available = lambda port: True

            try:
                server = companion.UnixHTTPServer(str(sock_path), companion.CompanionRequestHandler, state)
            except PermissionError as exc:
                check(
                    "socket: Unix server implemented; in-memory handler fallback used after sandbox bind denial",
                    issubclass(companion.UnixHTTPServer, companion.socketserver.UnixStreamServer)
                    and issubclass(companion.CompanionRequestHandler, companion.BaseHTTPRequestHandler),
                    detail=str(exc),
                )
                client = _Client(state, None)
            else:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                client = _Client(state, sock_path)

            # Unauthorized requests are rejected before routing.
            unauthorized = [
                client.request("GET", "/server/status", None),
                client.request("POST", "/server/start", None, {}),
                client.request("POST", "/server/stop", None, {}),
                client.request("POST", "/server/restart", None, {}),
            ]
            check(
                "auth: unauthorized rejected for all /server endpoints",
                all(status == 401 and body["error"]["code"] == "unauthorized" for status, body in unauthorized),
                detail=str(unauthorized),
            )

            status_code, initial = client.request("GET", "/server/status", token)
            check(
                "status: initially stopped",
                status_code == 200
                and initial["ok"] is True
                and initial["state"] == "stopped"
                and initial["managed"] is False
                and initial["error"] is None
                and initial["log_tail"] == [],
                detail=str(initial),
            )

            _, scan_body = client.request("POST", "/models/scan", token, {})
            model_id = str(scan_body["models"][0]["id"])
            check("scan: existing scan endpoint still works", len(scan_body["models"]) == 1 and model_id.startswith("gguf_"), detail=str(scan_body))

            port1 = 18181
            _, start = client.request("POST", "/server/start", token, _safe_start_payload(model_id, port1))
            check(
                "start: fake executable starts",
                start["state"] == "running"
                and start["managed"] is True
                and start["model_id"] == model_id
                and start["profile_id"] == "fake_test"
                and start["port"] == port1
                and start["error"] is None,
                detail=str(start),
            )

            running = _wait_for_state(client, token, "running")
            check("status: shows running", running["state"] == "running" and running["model_id"] == model_id, detail=str(running))

            _, already = client.request("POST", "/server/start", token, _safe_start_payload(model_id, 18182))
            check(
                "start: while running returns already_running",
                already["state"] == "already_running" and already["error"]["category"] == "already_running",
                detail=str(already),
            )

            forbidden = (
                token,
                str(sock_path),
                str(model),
                str(root),
                str(tmp),
                "tok-api-secret",
                "Authorization",
                "http://127.0.0.1",
                "/tmp/lmm-secret.sock",
                "--model",
                "argv",
            )
            time.sleep(0.2)
            _, logged_status = client.request("GET", "/server/status", token)
            _assert_no_leaks(
                "redaction: responses expose no token/socket/absolute path/raw argv/auth/full URL",
                {"start": start, "status": logged_status, "already": already},
                forbidden,
            )
            check(
                "logs: tail is bounded and redacted",
                isinstance(logged_status["log_tail"], list)
                and len(logged_status["log_tail"]) <= companion.MAX_HTTP_LOG_LINES
                and "fake-log-0" not in _blob(logged_status["log_tail"]),
                detail=str(logged_status["log_tail"][:2]),
            )

            _, stop = client.request("POST", "/server/stop", token, {"grace_seconds": 2})
            check("stop: stops tracked fake process", stop["state"] == "stopped" and stop["error"] is None, detail=str(stop))
            stopped = _wait_for_state(client, token, "stopped")
            check("status: stopped after stop", stopped["state"] == "stopped", detail=str(stopped))

            _, stop_again = client.request("POST", "/server/stop", token, {"grace_seconds": 1})
            check(
                "stop: when stopped returns not_running",
                stop_again["state"] == "not_running" and stop_again["error"]["category"] == "not_running",
                detail=str(stop_again),
            )

            _, restart = client.request("POST", "/server/restart", token, _safe_start_payload(model_id, 18183))
            check(
                "restart: explicit payload restarts fake executable",
                restart["state"] == "running" and restart["port"] == 18183 and restart["error"] is None,
                detail=str(restart),
            )

            _, unknown_model = client.request("POST", "/server/start", token, _safe_start_payload("gguf_missing", 18184))
            check(
                "start: unknown model id rejected",
                unknown_model["state"] == "already_running" or unknown_model["error"]["category"] in {"already_running", "unknown_model"},
                detail=str(unknown_model),
            )
            client.request("POST", "/server/stop", token, {"grace_seconds": 2})

            _, unknown_model_stopped = client.request("POST", "/server/start", token, _safe_start_payload("gguf_missing", 18185))
            check(
                "start: unknown model id rejected when stopped",
                unknown_model_stopped["state"] == "stopped" and unknown_model_stopped["error"]["category"] == "unknown_model",
                detail=str(unknown_model_stopped),
            )

            bad_profile_payload = _safe_start_payload(model_id, 18186)
            bad_profile_payload["profile_id"] = "gpu_default"
            _, unknown_profile = client.request("POST", "/server/start", token, bad_profile_payload)
            check(
                "start: unknown profile rejected",
                unknown_profile["state"] == "stopped" and unknown_profile["error"]["category"] == "unknown_profile",
                detail=str(unknown_profile),
            )

            bad_params = _safe_start_payload(model_id, 18187)
            bad_params["parameters"] = {"port": 80, "ctx_size": "4096", "gpu_layers": 0, "threads": 2}
            _, invalid_params = client.request("POST", "/server/start", token, bad_params)
            check(
                "start: invalid typed parameters rejected",
                invalid_params["state"] == "stopped" and invalid_params["error"]["category"] == "invalid_parameters",
                detail=str(invalid_params),
            )

            conflict_port = 18189
            old_port_available = state.process_manager._port_available
            state.process_manager._port_available = lambda port: False
            try:
                _, conflict = client.request("POST", "/server/start", token, _safe_start_payload(model_id, conflict_port))
            finally:
                state.process_manager._port_available = old_port_available
            check(
                "start: port conflict rejected",
                conflict["state"] == "stopped" and conflict["error"]["category"] == "port_in_use",
                detail=str(conflict),
            )

            malicious = _safe_start_payload(model_id, 18188)
            malicious.update(
                {
                    "model_path": str(model),
                    "executable": str(exe),
                    "args": ["--model", str(model)],
                    "command": f"{exe} --model {model}",
                }
            )
            status_bad, bad_request = client.request("POST", "/server/start", token, malicious)
            check(
                "start: model path/executable/free-form args are rejected at HTTP boundary",
                status_bad == 400 and bad_request["error"]["code"] == "bad_request",
                detail=str(bad_request),
            )

            # Corrupt state returns a safe status, not a traceback or leaked path.
            state.process_manager.state_path.write_text("{not json", encoding="utf-8")
            _, corrupt_status = client.request("GET", "/server/status", token)
            check(
                "status: corrupt state file returns safe status",
                corrupt_status["ok"] is True and corrupt_status["error"]["category"] == "stale_process",
                detail=str(corrupt_status),
            )

            _assert_no_leaks("redaction: corrupt status still has no leaks", corrupt_status, forbidden)

            # Hard-scope source checks.
            repo = Path(__file__).resolve().parents[1]
            api_source = (repo / "api" / "server.py").read_text(encoding="utf-8")
            client_source = (repo / "frontend" / "src" / "api" / "client.js").read_text(encoding="utf-8")
            panel_source = (repo / "frontend" / "src" / "components" / "LocalModelsPanel.jsx").read_text(encoding="utf-8")
            compose_source = (repo / "docker-compose.yml").read_text(encoding="utf-8")
            companion_source = inspect.getsource(companion)
            pm_source = inspect.getsource(process_manager)
            profile_source = inspect.getsource(profiles)
            check(
                "scope: backend bridge routes are present outside companion HTTP handler",
                all(route in api_source for route in (
                    "/api/local-model/server/status",
                    "/api/local-model/server/start",
                    "/api/local-model/server/stop",
                    "/api/local-model/server/restart",
                ))
                and "/api/local-model/server/" not in companion_source,
            )
            check(
                "scope: no frontend start/stop UI/routes added",
                "/api/local-model/server/" not in client_source
                and not any(label in panel_source for label in ("Start server", "Stop server", "Restart server")),
            )
            check(
                "scope: no Docker privilege/socket/host PID changes",
                "privileged: true" not in compose_source
                and "pid: host" not in compose_source
                and "/var/run/docker.sock" not in compose_source
                and "network_mode: host" not in compose_source,
            )
            check(
                "scope: no real llama-server launch profile",
                "llama-server" not in companion_source
                and "llama-server" not in profile_source
                and "llama-server" in pm_source
                and "fake_test" in profile_source,
            )
            check(
                "scope: no shell=True/free-form args in HTTP handler",
                "subprocess.Popen(" not in companion_source
                and "shell=True" not in companion_source,
            )

    finally:
        if server is not None:
            try:
                if getattr(server, "state", None) and server.state.process_manager is not None:
                    server.state.process_manager.stop_managed_server(grace_seconds=1)
            except Exception:
                pass
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
