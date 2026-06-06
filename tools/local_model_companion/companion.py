"""Unix-socket and CLI entry point for the Phase 2B companion prototype."""

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


class CompanionState:
    def __init__(self, config: CompanionConfig, limits: ScanLimits | None = None):
        self.config = config
        self.limits = limits or ScanLimits()
        self.models: list[dict[str, object]] = []
        self.last_scan_at: str | None = None
        self.last_warnings: list[dict[str, object]] = []

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
        self._write_json(404, {"ok": False, "error": {"code": "not_found", "message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        if self.path == "/models/scan":
            self._write_json(200, self.server.state.scan())
            return
        self._write_json(404, {"ok": False, "error": {"code": "not_found", "message": "not found"}})


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
