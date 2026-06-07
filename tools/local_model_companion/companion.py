"""Unix-socket and CLI entry point for the local model companion prototype."""

from __future__ import annotations

import argparse
import json
import os
import platform
import socketserver
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from .config import ConfigError, CompanionConfig, load_config
from .model_library import COMPANION_SCAN_VERSION, ScanLimits, scan_models
from .process_manager import (
    ManagedServerProcessManager,
    get_managed_server_status,
    start_managed_server,
    stop_managed_server,
)
from .profiles import LaunchProfile, fake_test_profile

MAX_JSON_BODY_BYTES = 64 * 1024
MAX_HTTP_LOG_LINES = 50

START_FIELDS = {"model_id", "profile_id", "parameters"}
STOP_FIELDS = {"grace_seconds"}
RESTART_FIELDS = {"reuse_last", "model_id", "profile_id", "parameters"}

ERROR_CATEGORY_MAP = {
    "invalid_profile": "unknown_profile",
    "invalid_parameter": "invalid_parameters",
    "launch_failed": "process_start_failed",
    "executable_missing": "process_start_failed",
    "executable_not_allowed": "process_start_failed",
    "stale_pid": "stale_process",
    "identity_uncertain": "stale_process",
    "stop_failed": "process_stop_failed",
    "stop_timeout": "process_stop_failed",
    "model_outside_approved_root": "unknown_model",
}


class CompanionState:
    def __init__(self, config: CompanionConfig, limits: ScanLimits | None = None):
        self.config = config
        self.limits = limits or ScanLimits()
        self.models: list[dict[str, object]] = []
        self.last_scan_at: str | None = None
        self.last_warnings: list[dict[str, object]] = []
        self.process_manager = self._build_process_manager()
        self.last_launch: dict[str, object] | None = None

    def scan(self) -> dict[str, object]:
        result = scan_models(self.config, self.limits)
        self.models = list(result["models"])
        self.last_warnings = list(result.get("warnings", []))
        self.last_scan_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        result["last_scan_at"] = self.last_scan_at
        return result

    def cached_models(self) -> dict[str, object]:
        return {
            "ok": True,
            "version": COMPANION_SCAN_VERSION,
            "models": self.models,
            "last_scan_at": self.last_scan_at,
            "roots_configured": len(self.config.approved_roots),
            "warnings": self.last_warnings,
        }

    def server_status(self) -> dict[str, object]:
        if self.process_manager is None:
            return _public_server_status(
                _status_payload(
                    "stopped",
                    error_category="process_error",
                    error_message="process manager is not configured",
                )
            )
        return _public_server_status(get_managed_server_status(self.process_manager))

    def start_server(self, payload: dict[str, object]) -> dict[str, object]:
        if self.process_manager is None:
            return _public_server_status(
                _status_payload(
                    "stopped",
                    error_category="process_error",
                    error_message="process manager is not configured",
                )
            )
        start_payload = _validate_start_payload(payload, self.process_manager)
        if start_payload.get("error"):
            return _public_server_status(start_payload)
        result = start_managed_server(
            self.process_manager,
            str(start_payload["model_id"]),
            str(start_payload["profile_id"]),
            start_payload["parameters"] if isinstance(start_payload.get("parameters"), dict) else {},
            library_records=self.models or None,
        )
        if result.get("state") == "running" and result.get("error") is None:
            self.last_launch = {
                "model_id": start_payload["model_id"],
                "profile_id": start_payload["profile_id"],
                "parameters": dict(start_payload["parameters"]) if isinstance(start_payload.get("parameters"), dict) else {},
            }
        return _public_server_status(result)

    def stop_server(self, payload: dict[str, object]) -> dict[str, object]:
        if self.process_manager is None:
            return _public_server_status(_status_payload("not_running", error_category="not_running"))
        grace_seconds = payload.get("grace_seconds", 5)
        if isinstance(grace_seconds, bool) or not isinstance(grace_seconds, (int, float)) or grace_seconds < 0 or grace_seconds > 30:
            return _public_server_status(
                _status_payload("stopped", error_category="invalid_parameters", error_message="grace_seconds must be between 0 and 30")
            )
        return _public_server_status(stop_managed_server(self.process_manager, grace_seconds=float(grace_seconds)))

    def restart_server(self, payload: dict[str, object]) -> dict[str, object]:
        if self.process_manager is None:
            return _public_server_status(
                _status_payload("stopped", error_category="process_error", error_message="process manager is not configured")
            )

        explicit = "model_id" in payload or "profile_id" in payload or "parameters" in payload
        if explicit:
            start_payload = _validate_start_payload(
                {key: payload[key] for key in START_FIELDS if key in payload},
                self.process_manager,
            )
        elif payload.get("reuse_last") is True and self.last_launch is not None:
            start_payload = dict(self.last_launch)
        elif payload.get("reuse_last") is True:
            start_payload = _status_payload(
                "stopped",
                error_category="invalid_parameters",
                error_message="reuse_last requires previous launch metadata",
            )
        else:
            start_payload = _status_payload(
                "stopped",
                error_category="invalid_parameters",
                error_message="restart requires explicit start payload or reuse_last",
            )

        if start_payload.get("error"):
            return _public_server_status(start_payload)

        stop_result = stop_managed_server(self.process_manager, grace_seconds=5.0)
        if not _restart_may_start_after_stop(stop_result):
            return _public_server_status(stop_result)

        result = start_managed_server(
            self.process_manager,
            str(start_payload["model_id"]),
            str(start_payload["profile_id"]),
            start_payload["parameters"] if isinstance(start_payload.get("parameters"), dict) else {},
            library_records=self.models or None,
        )
        if result.get("state") == "running" and result.get("error") is None:
            self.last_launch = {
                "model_id": start_payload["model_id"],
                "profile_id": start_payload["profile_id"],
                "parameters": dict(start_payload["parameters"]) if isinstance(start_payload.get("parameters"), dict) else {},
            }
        return _public_server_status(result)

    def _build_process_manager(self) -> ManagedServerProcessManager | None:
        if self.config.process_runtime_dir is None:
            return None
        profiles = _launch_profiles_from_config(self.config)
        return ManagedServerProcessManager(self.config, self.config.process_runtime_dir, profiles, scan_limits=self.limits)


class UnixHTTPServer(socketserver.UnixStreamServer):
    allow_reuse_address = False

    def __init__(self, socket_path: str, handler_cls: type[BaseHTTPRequestHandler], state: CompanionState):
        self.state = state
        super().__init__(socket_path, handler_cls)


class CompanionRequestHandler(BaseHTTPRequestHandler):
    server: UnixHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _write_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        token = self.server.state.config.token
        if not token:
            return False
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {token}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._write_json(401, {"ok": False, "error": {"code": "unauthorized", "message": "unauthorized"}})
        return False

    def _read_json_body(self) -> tuple[dict[str, object] | None, dict[str, object] | None]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            return None, {"ok": False, "error": {"code": "bad_request", "message": "invalid Content-Length"}}
        if length < 0 or length > MAX_JSON_BODY_BYTES:
            return None, {"ok": False, "error": {"code": "bad_request", "message": "request body is too large"}}
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, {"ok": False, "error": {"code": "bad_request", "message": "request body must be JSON"}}
        if not isinstance(payload, dict):
            return None, {"ok": False, "error": {"code": "bad_request", "message": "request body must be a JSON object"}}
        return payload, None

    def do_GET(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        if self.path == "/health":
            self._write_json(
                200,
                {
                    "ok": True,
                    "version": COMPANION_SCAN_VERSION,
                    "platform": platform.system().lower(),
                    "capabilities": ["scan"],
                },
            )
            return
        if self.path == "/models":
            self._write_json(200, self.server.state.cached_models())
            return
        if self.path == "/server/status":
            self._write_json(200, self.server.state.server_status())
            return
        self._write_json(404, {"ok": False, "error": {"code": "not_found", "message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        if self.path == "/models/scan":
            self._write_json(200, self.server.state.scan())
            return
        if self.path in {"/server/start", "/server/stop", "/server/restart"}:
            payload, error = self._read_json_body()
            if error is not None:
                self._write_json(400, error)
                return
            assert payload is not None
            if self.path == "/server/start":
                unknown = sorted(set(payload) - START_FIELDS)
                if unknown:
                    self._write_json(400, _bad_request(f"unknown field: {unknown[0]}"))
                    return
                self._write_json(200, self.server.state.start_server(payload))
                return
            if self.path == "/server/stop":
                unknown = sorted(set(payload) - STOP_FIELDS)
                if unknown:
                    self._write_json(400, _bad_request(f"unknown field: {unknown[0]}"))
                    return
                self._write_json(200, self.server.state.stop_server(payload))
                return
            unknown = sorted(set(payload) - RESTART_FIELDS)
            if unknown:
                self._write_json(400, _bad_request(f"unknown field: {unknown[0]}"))
                return
            self._write_json(200, self.server.state.restart_server(payload))
            return
        self._write_json(404, {"ok": False, "error": {"code": "not_found", "message": "not found"}})


def _launch_profiles_from_config(config: CompanionConfig) -> list[LaunchProfile]:
    profiles: list[LaunchProfile] = []
    for item in config.profiles:
        if item.id == "fake_test":
            profiles.append(fake_test_profile(item.executable))
    return profiles


def _validate_start_payload(payload: dict[str, object], manager: ManagedServerProcessManager) -> dict[str, object]:
    model_id = payload.get("model_id")
    profile_id = payload.get("profile_id")
    parameters = payload.get("parameters", {})
    if not isinstance(model_id, str) or not model_id.strip():
        return _status_payload("stopped", error_category="unknown_model", error_message="model_id is required")
    if not isinstance(profile_id, str) or not profile_id.strip():
        return _status_payload("stopped", error_category="unknown_profile", error_message="profile_id is required")
    if profile_id not in manager.profiles:
        return _status_payload("stopped", error_category="unknown_profile", error_message="unknown launch profile")
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        return _status_payload("stopped", error_category="invalid_parameters", error_message="parameters must be an object")
    return {"model_id": model_id.strip(), "profile_id": profile_id.strip(), "parameters": dict(parameters)}


def _restart_may_start_after_stop(payload: dict[str, object]) -> bool:
    if payload.get("state") in {"stopped", "not_running"} and payload.get("error") is None:
        return True
    error = payload.get("error")
    if isinstance(error, dict) and error.get("category") in {"not_running", "stale_pid"}:
        return True
    return False


def _status_payload(
    state: str,
    *,
    error_category: str | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    error = None
    if error_category:
        error = {"category": error_category, "message": error_message or error_category}
    return {
        "ok": True,
        "state": state,
        "managed": state in {"running", "already_running"},
        "model_id": None,
        "profile_id": None,
        "port": None,
        "started_at": None,
        "error": error,
        "log_tail": [],
    }


def _public_server_status(payload: dict[str, object]) -> dict[str, object]:
    error = payload.get("error")
    safe_error = None
    if isinstance(error, dict):
        raw_category = error.get("category")
        category = ERROR_CATEGORY_MAP.get(raw_category, raw_category) if isinstance(raw_category, str) else "process_error"
        if category not in {
            "not_running",
            "already_running",
            "unknown_model",
            "unknown_profile",
            "invalid_parameters",
            "port_in_use",
            "process_start_failed",
            "process_stop_failed",
            "stale_process",
            "process_error",
            "unauthorized",
            "bad_request",
        }:
            category = "process_error"
        message = error.get("message") if isinstance(error.get("message"), str) else category
        safe_error = {"category": category, "message": _safe_message(message)}

    return {
        "ok": True,
        "state": _safe_state(payload.get("state")),
        "managed": bool(payload.get("managed")),
        "model_id": payload.get("model_id") if isinstance(payload.get("model_id"), str) else None,
        "profile_id": payload.get("profile_id") if isinstance(payload.get("profile_id"), str) else None,
        "port": payload.get("port") if isinstance(payload.get("port"), int) and not isinstance(payload.get("port"), bool) else None,
        "started_at": payload.get("started_at") if isinstance(payload.get("started_at"), str) else None,
        "error": safe_error,
        "log_tail": _log_tail_lines(payload.get("log_tail")),
    }


def _safe_state(value: object) -> str:
    if isinstance(value, str) and value in {"stopped", "running", "already_running", "not_running", "unknown"}:
        return value
    return "unknown"


def _log_tail_lines(value: object) -> list[str]:
    if isinstance(value, str):
        return [_safe_message(line) for line in value.splitlines()[-MAX_HTTP_LOG_LINES:]]
    if isinstance(value, list):
        lines = [item for item in value if isinstance(item, str)]
        return [_safe_message(line) for line in lines[-MAX_HTTP_LOG_LINES:]]
    return []


def _safe_message(value: str) -> str:
    text = value.replace("\r", " ").replace("\n", " ")
    if len(text) > 500:
        text = text[:500]
    return text


def _bad_request(message: str) -> dict[str, object]:
    return {"ok": False, "error": {"code": "bad_request", "message": message}}


def run_server(socket_path: str, config: CompanionConfig, limits: ScanLimits | None = None) -> None:
    sock = Path(socket_path)
    sock.parent.mkdir(parents=True, exist_ok=True)
    if sock.exists():
        sock.unlink()
    state = CompanionState(config, limits)
    with UnixHTTPServer(str(sock), CompanionRequestHandler, state) as server:
        os.chmod(sock, 0o600)
        server.serve_forever()


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Model Manager host companion prototype")
    parser.add_argument("--config", help="explicit companion JSON config path")
    parser.add_argument("--max-files", type=int, default=ScanLimits.max_files_inspected)
    parser.add_argument("--max-models", type=int, default=ScanLimits.max_models_returned)
    parser.add_argument("--max-warnings", type=int, default=ScanLimits.max_warnings)
    parser.add_argument("--timeout-seconds", type=float, default=ScanLimits.timeout_seconds)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="scan approved roots and print safe JSON")
    serve = sub.add_parser("serve", help="serve the companion API on a Unix domain socket")
    serve.add_argument("--socket", required=True, help="Unix domain socket path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    limits = ScanLimits(
        max_files_inspected=args.max_files,
        max_models_returned=args.max_models,
        max_warnings=args.max_warnings,
        timeout_seconds=args.timeout_seconds,
    )
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        _print_json({"ok": False, "error": {"code": "invalid_config", "message": str(exc)}})
        return 2

    if args.command == "scan":
        _print_json(scan_models(config, limits))
        return 0
    if args.command == "serve":
        if not config.token:
            _print_json({"ok": False, "error": {"code": "missing_token", "message": "companion token is required"}})
            return 2
        run_server(args.socket, config, limits)
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
