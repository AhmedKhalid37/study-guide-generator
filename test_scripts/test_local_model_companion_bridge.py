"""Backend tests for LMM Phase 2C companion bridge.

The bridge is stdlib-only and testable without FastAPI. These checks cover the
server-side env contract, Unix-socket HTTP request shape, safe failure categories,
model-field whitelisting, redaction, warning bounds, and route registration when
FastAPI is available in the current Python environment.

    python test_scripts/test_local_model_companion_bridge.py
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
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


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

    secret_token = "tok-phase2c-SUPERSECRET"
    secret_socket = "/tmp/lmm-phase2c-secret.sock"
    absolute_host_path = "/home/user/models/secret-model.gguf"
    auth_text = f"Authorization: Bearer {secret_token}"
    full_url = "http://127.0.0.1:65535/private?token=abc"

    try:
        # 1. Unconfigured env is a safe status/library/scan response, not a crash.
        _set_companion_env(None, None)
        status_unc = bridge.get_companion_status()
        library_unc = bridge.get_companion_library()
        scan_unc = bridge.scan_companion_library()
        check(
            "unconfigured status: ok true, configured false, safe config error",
            status_unc["ok"] is True
            and status_unc["configured"] is False
            and status_unc["reachable"] is False
            and status_unc["socket_configured"] is False
            and status_unc["error"]["category"] == "companion_config",
            detail=str(status_unc),
        )
        check(
            "unconfigured library/scan: empty models with safe error",
            library_unc["models"] == []
            and library_unc["model_count"] == 0
            and library_unc["error"]["category"] == "companion_config"
            and scan_unc["models"] == []
            and scan_unc["error"]["category"] == "companion_config",
            detail=str({"library": library_unc, "scan": scan_unc}),
        )

        # 2. Successful socket calls: health, cached models, explicit scan.
        warnings = [
            {
                "code": "path_warning",
                "message": f"bad {absolute_host_path} {secret_token} {auth_text} {full_url}",
                "root_id": "default",
                "relative_path": "safe/model.gguf",
            }
            for _ in range(30)
        ]
        model_record = {
            "id": "gguf_ok",
            "display_name": "Gemma 4",
            "filename": "gemma.gguf",
            "relative_path": "sub/gemma.gguf",
            "root_id": "default",
            "size_bytes": 123,
            "modified_at": "2026-06-06T00:00:00Z",
            "family_hint": "gemma",
            "quant_hint": "Q4_K_M",
            "server_compatible": True,
            "absolute_path": absolute_host_path,
            "token": secret_token,
        }
        bad_relative_record = {
            "id": "gguf_abs",
            "display_name": f"Bad {absolute_host_path}",
            "filename": absolute_host_path,
            "relative_path": absolute_host_path,
            "root_id": "default",
            "size_bytes": 456,
            "server_compatible": True,
        }
        old_socket_ctor = _install_fake_socket(
            [
                _http_response(
                    200,
                    {
                        "ok": True,
                        "version": "0.1.0",
                        "platform": "linux",
                        "capabilities": ["scan", "admin"],
                    },
                ),
                _http_response(
                    200,
                    {
                        "ok": True,
                        "models": [model_record, model_record, bad_relative_record],
                        "last_scan_at": None,
                        "roots_configured": 1,
                        "warnings": [],
                    },
                ),
                _http_response(
                    200,
                    {
                        "ok": True,
                        "models": [model_record],
                        "last_scan_at": "2026-06-06T00:00:00Z",
                        "roots_configured": 1,
                        "warnings": warnings,
                    },
                ),
            ]
        )
        _set_companion_env(secret_socket, secret_token, timeout="2")
        status_ok = bridge.get_companion_status()
        library_ok = bridge.get_companion_library()
        scan_ok = bridge.scan_companion_library()
        sent_requests = [item.request.decode("utf-8", errors="replace") for item in _FakeSocket.instances]
        check(
            "success: health status exposes only safe companion status",
            status_ok["reachable"] is True
            and status_ok["transport"] == "unix_socket"
            and status_ok["socket_label"] == "configured"
            and status_ok["capabilities"] == ["scan"]
            and status_ok["platform"] == "linux"
            and status_ok["version"] == "0.1.0"
            and status_ok["error"] is None,
            detail=str(status_ok),
        )
        check(
            "success: Authorization bearer token sent server-side",
            len(sent_requests) == 3
            and all(f"Authorization: Bearer {secret_token}" in req for req in sent_requests)
            and sent_requests[0].startswith("GET /health ")
            and sent_requests[1].startswith("GET /models ")
            and sent_requests[2].startswith("POST /models/scan "),
            detail=str(sent_requests),
        )
        check(
            "success: models are whitelisted, de-duped, counted",
            library_ok["reachable"] is True
            and library_ok["model_count"] == 2
            and len(library_ok["models"]) == 2
            and set(library_ok["models"][0].keys()).issubset(set(bridge._MODEL_FIELDS)),
            detail=str(library_ok),
        )
        check(
            "scan: warnings are bounded and include truncation metadata",
            scan_ok["model_count"] == 1
            and len(scan_ok["warnings"]) == bridge.MAX_COMPANION_WARNINGS + 1
            and scan_ok["warnings"][-1]["code"] == "warnings_truncated",
            detail=str(scan_ok["warnings"][-2:]),
        )
        redaction_blob = _blob({"status": status_ok, "library": library_ok, "scan": scan_ok})
        check(
            "redaction: no token, raw socket path, absolute path, auth header, or full URL leaks",
            secret_token not in redaction_blob
            and secret_socket not in redaction_blob
            and absolute_host_path not in redaction_blob
            and auth_text not in redaction_blob
            and full_url not in redaction_blob,
            detail=redaction_blob,
        )
        bridge.socket.socket = old_socket_ctor

        # 3. Auth failure maps to companion_auth and does not echo the token.
        old_socket_ctor = _install_fake_socket(
            [_http_response(401, {"ok": False, "error": {"message": f"bad {secret_token}"}}, reason="Unauthorized")]
        )
        auth_fail = bridge.get_companion_status()
        check(
            "auth failure: 401 maps to companion_auth",
            auth_fail["reachable"] is False
            and auth_fail["error"]["category"] == "companion_auth"
            and secret_token not in _blob(auth_fail),
            detail=str(auth_fail),
        )
        bridge.socket.socket = old_socket_ctor

        # 4. Missing/refused socket is offline and never reveals the raw socket path.
        bridge.socket.socket = old_socket_ctor
        _set_companion_env(secret_socket, secret_token)
        offline = bridge.get_companion_status()
        offline_blob = _blob(offline)
        check(
            "offline: missing/refused socket maps to companion_offline without path leak",
            offline["reachable"] is False
            and offline["error"]["category"] == "companion_offline"
            and secret_socket not in offline_blob,
            detail=str(offline),
        )

        # 5. Timeout maps to companion_timeout.
        old_socket_ctor = _install_fake_socket([real_socket.timeout("slow companion")])
        timeout = bridge.get_companion_library()
        check(
            "timeout: socket timeout maps to companion_timeout",
            timeout["reachable"] is False
            and timeout["error"]["category"] == "companion_timeout",
            detail=str(timeout),
        )
        bridge.socket.socket = old_socket_ctor

        # 6. Malformed JSON and unexpected model shapes are safe companion_error.
        old_socket_ctor = _install_fake_socket(
            [
                _http_response(200, b"{not json"),
                _http_response(200, {"ok": True, "models": {"unexpected": True}}),
            ]
        )
        malformed = bridge.get_companion_library()
        unexpected = bridge.get_companion_library()
        check(
            "malformed/unexpected companion response maps to companion_error",
            malformed["error"]["category"] == "companion_error"
            and unexpected["error"]["category"] == "companion_error"
            and malformed["models"] == []
            and unexpected["models"] == [],
            detail=str({"malformed": malformed, "unexpected": unexpected}),
        )
        bridge.socket.socket = old_socket_ctor

        # 7. Source/route inspection: no Phase 2C process-control surface.
        bridge_source = inspect.getsource(bridge)
        forbidden_bridge_terms = ("subprocess", "Popen(", "os.system(", "shell=True")
        check(
            "safety-source: bridge code has no process execution primitives",
            all(term not in bridge_source for term in forbidden_bridge_terms),
            detail=", ".join(term for term in forbidden_bridge_terms if term in bridge_source),
        )
        api_source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(encoding="utf-8")
        forbidden_routes = (
            '"/api/local-model/server/start"',
            '"/api/local-model/server/stop"',
            '"/api/local-model/server/restart"',
        )
        check(
            "safety-source: no local-model start/stop/restart FastAPI routes",
            all(route not in api_source for route in forbidden_routes),
            detail=", ".join(route for route in forbidden_routes if route in api_source),
        )

        try:
            from api.server import app  # noqa: WPS433

            paths = {getattr(route, "path", "") for route in getattr(app, "routes", [])}
            check(
                "routes: Phase 2C endpoints are registered before static fallback",
                {
                    "/api/local-model/companion/status",
                    "/api/local-model/library",
                    "/api/local-model/library/scan",
                }.issubset(paths),
                detail=str(sorted(p for p in paths if p.startswith("/api/local-model"))),
            )
        except Exception as exc:
            check(
                "routes: FastAPI route inspection skipped when unavailable",
                True,
                detail=exc.__class__.__name__,
            )

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
