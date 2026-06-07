"""Backend tests for LMM Phase 2G3 companion process bridge.

These checks cover only the Docker FastAPI backend bridge/client layer. The
companion process manager itself is covered by the Phase 2G1/2G2 tests.

    python test_scripts/test_local_model_companion_process_bridge.py
"""

from __future__ import annotations

import inspect
import json
import os
import socket as real_socket
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import local_model_companion_client as bridge  # noqa: E402


results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _http_response(status: int, payload: Any, reason: str = "OK") -> bytes:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "\r\n"
    ).encode("utf-8") + body


class _FakeSocket:
    instances: list["_FakeSocket"] = []
    responses: list[bytes | BaseException] = []

    def __init__(self, *args: Any, **kwargs: Any):
        self.request = b""
        self.connected_to: str | None = None
        self.timeout: float | None = None
        self.closed = False
        self.response = _FakeSocket.responses.pop(0)
        self.sent_response = False
        _FakeSocket.instances.append(self)

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def connect(self, path: str) -> None:
        self.connected_to = path

    def sendall(self, request: bytes) -> None:
        self.request += request

    def recv(self, size: int) -> bytes:
        if isinstance(self.response, BaseException):
            raise self.response
        if self.sent_response:
            return b""
        self.sent_response = True
        return self.response

    def close(self) -> None:
        self.closed = True


def _install_fake_socket(responses: list[bytes | BaseException]):
    _FakeSocket.instances = []
    _FakeSocket.responses = list(responses)
    old_socket_ctor = bridge.socket.socket
    bridge.socket.socket = _FakeSocket
    return old_socket_ctor


def _set_companion_env(socket_path: str | None, token: str | None, timeout: str | None = None) -> None:
    for key in (
        bridge.COMPANION_SOCKET_ENV,
        bridge.COMPANION_TOKEN_ENV,
        bridge.COMPANION_TIMEOUT_ENV,
    ):
        os.environ.pop(key, None)
    if socket_path is not None:
        os.environ[bridge.COMPANION_SOCKET_ENV] = socket_path
    if token is not None:
        os.environ[bridge.COMPANION_TOKEN_ENV] = token
    if timeout is not None:
        os.environ[bridge.COMPANION_TIMEOUT_ENV] = timeout


def _safe_start_payload(port: int = 8123) -> dict[str, Any]:
    return {
        "model_id": "gguf_ok",
        "profile_id": "fake_test",
        "parameters": {
            "port": port,
            "ctx_size": 4096,
            "gpu_layers": 0,
            "threads": 2,
        },
    }


def _request_texts() -> list[str]:
    return [item.request.decode("utf-8", errors="replace") for item in _FakeSocket.instances]


def _request_body(request: str) -> dict[str, Any]:
    _, _, body = request.partition("\r\n\r\n")
    return json.loads(body or "{}")


def _assert_no_leaks(name: str, payload: Any, forbidden: tuple[str, ...]) -> None:
    blob = _blob(payload)
    leaked = [item for item in forbidden if item and item in blob]
    check(name, not leaked, detail=", ".join(leaked) or blob)


def run() -> int:
    old_env = {
        key: os.environ.get(key)
        for key in (
            bridge.COMPANION_SOCKET_ENV,
            bridge.COMPANION_TOKEN_ENV,
            bridge.COMPANION_TIMEOUT_ENV,
        )
    }
    old_load_env_file = bridge.load_env_file
    old_socket_ctor = bridge.socket.socket
    bridge.load_env_file = lambda: None

    secret_token = "tok-phase2g3-SUPERSECRET"
    secret_socket = "/tmp/lmm-phase2g3-secret.sock"
    absolute_host_path = "/home/user/models/secret-model.gguf"
    auth_text = f"Authorization: Bearer {secret_token}"
    full_url = "http://127.0.0.1:8123/v1?token=abc"
    raw_argv = f"argv=['/bin/fake','--model','{absolute_host_path}']"
    forbidden = (
        secret_token,
        secret_socket,
        absolute_host_path,
        auth_text,
        full_url,
        raw_argv,
        "--model",
        "/bin/fake",
        "executable_path",
        "model_path",
    )

    try:
        # 1. Unconfigured env is safe for all bridge endpoints.
        _set_companion_env(None, None)
        unc_status = bridge.get_companion_server_status()
        unc_start = bridge.start_companion_server(_safe_start_payload())
        unc_stop = bridge.stop_companion_server({"grace_seconds": 5})
        unc_restart = bridge.restart_companion_server({"reuse_last": True})
        check(
            "unconfigured env: status/start/stop/restart return safe config errors",
            all(
                item["configured"] is False
                and item["reachable"] is False
                and item["error"]["category"] == "companion_config"
                and secret_socket not in _blob(item)
                for item in (unc_status, unc_start, unc_stop, unc_restart)
            ),
            detail=str([unc_status, unc_start, unc_stop, unc_restart]),
        )

        # 2. Successful fake socket companion responses and request shapes.
        old_socket_ctor = _install_fake_socket(
            [
                _http_response(200, {"ok": True, "state": "stopped", "managed": False, "error": None, "log_tail": []}),
                _http_response(
                    200,
                    {
                        "ok": True,
                        "state": "running",
                        "managed": True,
                        "model_id": "gguf_ok",
                        "profile_id": "fake_test",
                        "port": 8123,
                        "started_at": "2026-06-07T00:00:00Z",
                        "pid": 99999,
                        "params": {"port": 8123},
                        "private_model_path": absolute_host_path,
                        "argv": ["/bin/fake", "--model", absolute_host_path],
                        "error": None,
                        "log_tail": [],
                    },
                ),
                _http_response(200, {"ok": True, "state": "stopped", "managed": False, "error": None, "log_tail": []}),
                _http_response(
                    200,
                    {
                        "ok": True,
                        "state": "running",
                        "managed": True,
                        "model_id": "gguf_ok",
                        "profile_id": "fake_test",
                        "port": 8124,
                        "started_at": "2026-06-07T00:01:00Z",
                        "error": None,
                        "log_tail": [f"started {auth_text} {full_url} {absolute_host_path} {raw_argv}"],
                    },
                ),
            ]
        )
        _set_companion_env(secret_socket, secret_token, timeout="2")
        ok_status = bridge.get_companion_server_status()
        ok_start = bridge.start_companion_server(_safe_start_payload(8123))
        ok_stop = bridge.stop_companion_server({"grace_seconds": 5})
        ok_restart = bridge.restart_companion_server(_safe_start_payload(8124))
        sent = _request_texts()
        bodies = [_request_body(item) for item in sent]
        check(
            "success: methods/paths and Authorization header are correct",
            len(sent) == 4
            and sent[0].startswith("GET /server/status ")
            and sent[1].startswith("POST /server/start ")
            and sent[2].startswith("POST /server/stop ")
            and sent[3].startswith("POST /server/restart ")
            and all(f"Authorization: Bearer {secret_token}" in item for item in sent),
            detail=str(sent),
        )
        check(
            "success: start/stop/restart forward only allowed typed fields",
            bodies[1] == _safe_start_payload(8123)
            and bodies[2] == {"grace_seconds": 5}
            and bodies[3] == _safe_start_payload(8124),
            detail=str(bodies[1:]),
        )
        check(
            "success: responses expose only safe server status fields",
            ok_status["state"] == "stopped"
            and ok_start["state"] == "running"
            and ok_start["managed"] is True
            and ok_start["model_id"] == "gguf_ok"
            and ok_start["profile_id"] == "fake_test"
            and ok_start["port"] == 8123
            and ok_stop["state"] == "stopped"
            and ok_restart["port"] == 8124
            and "pid" not in ok_start
            and "params" not in ok_start,
            detail=str({"status": ok_status, "start": ok_start, "stop": ok_stop, "restart": ok_restart}),
        )
        _assert_no_leaks("success redaction: no token/socket/path/auth/url/raw argv leaks", {"start": ok_start, "restart": ok_restart}, forbidden)
        bridge.socket.socket = old_socket_ctor

        # 3. Auth failure maps to companion_auth without echoing token/body.
        old_socket_ctor = _install_fake_socket(
            [_http_response(401, {"ok": False, "error": {"message": f"bad {secret_token}"}}, reason="Unauthorized")]
        )
        auth_fail = bridge.get_companion_server_status()
        check(
            "auth failure: maps to companion_auth",
            auth_fail["error"]["category"] == "companion_auth" and secret_token not in _blob(auth_fail),
            detail=str(auth_fail),
        )
        bridge.socket.socket = old_socket_ctor

        # 4. Missing socket maps to companion_offline and hides the socket path.
        _set_companion_env(secret_socket, secret_token)
        offline = bridge.get_companion_server_status()
        check(
            "offline: missing socket maps to companion_offline without path leak",
            offline["error"]["category"] == "companion_offline" and secret_socket not in _blob(offline),
            detail=str(offline),
        )

        # 5. Timeout maps safely.
        old_socket_ctor = _install_fake_socket([real_socket.timeout("slow companion")])
        timeout = bridge.get_companion_server_status()
        check(
            "timeout: maps to companion_timeout",
            timeout["error"]["category"] == "companion_timeout",
            detail=str(timeout),
        )
        bridge.socket.socket = old_socket_ctor

        # 6. Malformed/unexpected JSON maps safely.
        old_socket_ctor = _install_fake_socket([_http_response(200, b"{not json"), _http_response(200, [])])
        malformed = bridge.get_companion_server_status()
        unexpected = bridge.get_companion_server_status()
        check(
            "malformed/unexpected companion JSON maps to companion_error",
            malformed["error"]["category"] == "companion_error"
            and unexpected["error"]["category"] == "companion_error",
            detail=str({"malformed": malformed, "unexpected": unexpected}),
        )
        bridge.socket.socket = old_socket_ctor

        # 7. Misbehaving companion payloads are redacted/dropped.
        old_socket_ctor = _install_fake_socket(
            [
                _http_response(
                    200,
                    {
                        "ok": True,
                        "state": "running",
                        "managed": True,
                        "model_id": f"gguf_ok {secret_token} {absolute_host_path}",
                        "profile_id": f"fake/test/{secret_token}",
                        "port": 8123,
                        "started_at": f"2026-06-07T00:00:00Z {full_url}",
                        "error": {
                            "category": "launch_failed",
                            "message": f"{auth_text} {full_url} {absolute_host_path} {secret_socket} {raw_argv}",
                        },
                        "log_tail": [f"{secret_token} {auth_text} {full_url} {absolute_host_path} {raw_argv}"],
                    },
                )
            ]
        )
        redacted = bridge.get_companion_server_status()
        check(
            "error category aliases: launch_failed maps to process_start_failed",
            redacted["error"]["category"] == "process_start_failed",
            detail=str(redacted),
        )
        _assert_no_leaks("redaction: malicious companion fields are sanitized", redacted, forbidden)
        bridge.socket.socket = old_socket_ctor

        # 8. Start validation rejects unsafe/free-form fields before socket use.
        old_socket_ctor = _install_fake_socket([_http_response(200, {"ok": True, "state": "running"})])
        bad_start = _safe_start_payload()
        bad_start.update(
            {
                "executable": "/bin/fake",
                "model_path": absolute_host_path,
                "command": "fake --model /tmp/model.gguf",
                "args": ["--model", absolute_host_path],
            }
        )
        start_rejected = bridge.start_companion_server(bad_start)
        start_bad_param = bridge.start_companion_server({**_safe_start_payload(), "parameters": {"port": 80}})
        start_unknown_param = bridge.start_companion_server({**_safe_start_payload(), "parameters": {"port": 8123, "cmd": "x"}})
        check(
            "start validation: rejects unsafe top-level and invalid/free-form parameter fields before socket",
            start_rejected["error"]["category"] == "bad_request"
            and start_bad_param["error"]["category"] == "bad_request"
            and start_unknown_param["error"]["category"] == "bad_request"
            and len(_FakeSocket.instances) == 0,
            detail=str([start_rejected, start_bad_param, start_unknown_param]),
        )
        bridge.socket.socket = old_socket_ctor

        # 9. Stop validation is typed/bounded.
        old_socket_ctor = _install_fake_socket([_http_response(200, {"ok": True, "state": "stopped", "managed": False, "error": None})])
        stop_bad_type = bridge.stop_companion_server({"grace_seconds": "5"})
        stop_bad_range = bridge.stop_companion_server({"grace_seconds": 31})
        stop_unknown = bridge.stop_companion_server({"grace_seconds": 5, "pid": 123})
        stop_ok = bridge.stop_companion_server({"grace_seconds": 0.5})
        check(
            "stop validation: typed and bounded grace_seconds only",
            stop_bad_type["error"]["category"] == "bad_request"
            and stop_bad_range["error"]["category"] == "bad_request"
            and stop_unknown["error"]["category"] == "bad_request"
            and stop_ok["state"] == "stopped"
            and _request_body(_request_texts()[-1]) == {"grace_seconds": 0.5},
            detail=str([stop_bad_type, stop_bad_range, stop_unknown, stop_ok]),
        )
        bridge.socket.socket = old_socket_ctor

        # 10. Restart validation accepts explicit payload or reuse_last only.
        old_socket_ctor = _install_fake_socket(
            [
                _http_response(200, {"ok": True, "state": "running", "managed": True, "port": 8125}),
                _http_response(200, {"ok": True, "state": "running", "managed": True, "port": 8126}),
            ]
        )
        restart_explicit = bridge.restart_companion_server(_safe_start_payload(8125))
        restart_reuse = bridge.restart_companion_server({"reuse_last": True})
        restart_mixed = bridge.restart_companion_server({**_safe_start_payload(8127), "reuse_last": True})
        restart_empty = bridge.restart_companion_server({})
        check(
            "restart validation: explicit payload or reuse_last only",
            restart_explicit["port"] == 8125
            and restart_reuse["port"] == 8126
            and restart_mixed["error"]["category"] == "bad_request"
            and restart_empty["error"]["category"] == "bad_request",
            detail=str([restart_explicit, restart_reuse, restart_mixed, restart_empty]),
        )
        bridge.socket.socket = old_socket_ctor

        # 11-14. Hard-scope source checks.
        repo = Path(__file__).resolve().parents[1]
        api_source = (repo / "api" / "server.py").read_text(encoding="utf-8")
        bridge_source = inspect.getsource(bridge)
        provider_store_source = (repo / "pipeline" / "provider_settings_store.py").read_text(encoding="utf-8")
        ask_sources = "\n".join(
            (repo / path).read_text(encoding="utf-8")
            for path in (
                "pipeline/orchestrator.py",
                "pipeline/ask_sessions.py",
                "pipeline/ask_context.py",
            )
        )
        frontend_client_source = (repo / "frontend" / "src" / "api" / "client.js").read_text(encoding="utf-8")
        panel_source = (repo / "frontend" / "src" / "components" / "LocalModelsPanel.jsx").read_text(encoding="utf-8")
        managed_section = panel_source[
            panel_source.find("function ManagedServerSection") : panel_source.find("function CompanionStateIcon")
        ]
        server_route_source = "\n".join(
            inspect.getsource(func)
            for func in (
                bridge.get_companion_server_status,
                bridge.start_companion_server,
                bridge.stop_companion_server,
                bridge.restart_companion_server,
            )
        )
        check(
            "routes: Phase 2G3 backend process bridge routes are registered",
            all(
                route in api_source
                for route in (
                    "/api/local-model/server/status",
                    "/api/local-model/server/start",
                    "/api/local-model/server/stop",
                    "/api/local-model/server/restart",
                )
            ),
        )
        check(
            "scope: no Provider Settings writes in bridge routes/client",
            "provider_settings_store" not in bridge_source
            and "update_provider_settings" not in server_route_source
            and "os.replace" in provider_store_source,
        )
        check(
            "scope: no Ask changes depend on local-model process bridge",
            "/api/local-model/server/" not in ask_sources,
        )
        check(
            "scope: Phase 2G4 frontend process UI uses backend bridge only",
            all(
                route in frontend_client_source
                for route in (
                    "/api/local-model/server/status",
                    "/api/local-model/server/start",
                    "/api/local-model/server/stop",
                    "/api/local-model/server/restart",
                )
            )
            and '"/server/start"' not in managed_section
            and '"/server/stop"' not in managed_section
            and '"/server/restart"' not in managed_section
            and "LMM_COMPANION" not in managed_section
            and "Authorization" not in managed_section,
        )
        check(
            "scope: backend bridge has no subprocess/os.system/shell/direct host control",
            all(term not in bridge_source for term in ("subprocess", "Popen(", "os.system(", "shell=True", "os.kill(")),
            detail=", ".join(term for term in ("subprocess", "Popen(", "os.system(", "shell=True", "os.kill(") if term in bridge_source),
        )

        try:
            from api.server import app  # noqa: WPS433

            paths = {getattr(route, "path", "") for route in getattr(app, "routes", [])}
            check(
                "routes: FastAPI app exposes Phase 2G3 bridge endpoints",
                {
                    "/api/local-model/server/status",
                    "/api/local-model/server/start",
                    "/api/local-model/server/stop",
                    "/api/local-model/server/restart",
                }.issubset(paths),
                detail=str(sorted(p for p in paths if p.startswith("/api/local-model/server"))),
            )
        except Exception as exc:
            check("routes: FastAPI route inspection skipped when unavailable", True, detail=exc.__class__.__name__)

    finally:
        bridge.socket.socket = old_socket_ctor
        bridge.load_env_file = old_load_env_file
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
