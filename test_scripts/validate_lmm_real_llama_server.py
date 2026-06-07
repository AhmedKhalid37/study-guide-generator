"""Live Linux validation for LMM Phase 2G5 real llama-server lifecycle.

Required env:
  LMM_REAL_LLAMA_SERVER_BIN
  LMM_REAL_MODEL_ROOT
  LMM_REAL_MODEL_ID or LMM_REAL_MODEL_PATTERN or LMM_REAL_MODEL_FILENAME

Optional env:
  LMM_REAL_PORT
  LMM_REAL_CTX_SIZE
  LMM_REAL_GPU_LAYERS
  LMM_REAL_THREADS
  LMM_REAL_READINESS_TIMEOUT

Missing required env skips with exit 0. Invalid explicit env or a failed live
launch fails with exit 1.
"""

from __future__ import annotations

import fnmatch
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = "llama_cpp_gpu_default"
TOKEN = "local-test-token"


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def _http_json_unix(socket_path: Path, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    body_bytes = json.dumps(body or {}, separators=(",", ":"), sort_keys=True).encode("utf-8") if body is not None else b""
    request = (
        f"{method} {path} HTTP/1.1\r\n"
        "Host: local-model-companion\r\n"
        f"Authorization: Bearer {TOKEN}\r\n"
        "Accept: application/json\r\n"
        "Content-Type: application/json\r\n"
        "Connection: close\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "\r\n"
    ).encode("utf-8") + body_bytes

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5)
    try:
        client.connect(str(socket_path))
        client.sendall(request)
        chunks: list[bytes] = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        client.close()

    raw = b"".join(chunks)
    header, sep, response_body = raw.partition(b"\r\n\r\n")
    if not sep:
        raise RuntimeError("companion returned malformed HTTP")
    status_line = header.splitlines()[0].decode("ascii", errors="replace")
    parts = status_line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        raise RuntimeError("companion returned malformed status")
    status = int(parts[1])
    payload = json.loads(response_body.decode("utf-8"))
    if status < 200 or status >= 300:
        raise RuntimeError(f"companion HTTP {status}: {payload}")
    if not isinstance(payload, dict):
        raise RuntimeError("companion returned non-object JSON")
    return payload


def _wait_for_companion(socket_path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = _http_json_unix(socket_path, "GET", "/health")
            if payload.get("ok") is True:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"companion did not become ready: {last_error}")


def _select_model(models: list[dict[str, Any]]) -> str:
    requested_id = os.environ.get("LMM_REAL_MODEL_ID")
    if requested_id and requested_id.strip():
        for item in models:
            if item.get("id") == requested_id.strip():
                return requested_id.strip()
        raise RuntimeError("LMM_REAL_MODEL_ID was not found in scanned approved root")

    pattern = os.environ.get("LMM_REAL_MODEL_PATTERN") or os.environ.get("LMM_REAL_MODEL_FILENAME")
    if not pattern or not pattern.strip():
        raise RuntimeError("missing LMM_REAL_MODEL_ID or LMM_REAL_MODEL_PATTERN/LMM_REAL_MODEL_FILENAME")
    wanted = pattern.strip()
    for item in models:
        candidates = [
            item.get("filename"),
            item.get("relative_path"),
            item.get("display_name"),
            item.get("id"),
        ]
        if any(isinstance(value, str) and fnmatch.fnmatch(value, wanted) for value in candidates):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id:
                return model_id
    raise RuntimeError("model pattern did not match any scanned GGUF model")


def _wait_http_models(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                request = b"GET /v1/models HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
                client.sendall(request)
                raw = client.recv(4096)
            if b" 200 " in raw.split(b"\r\n", 1)[0]:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"llama-server /v1/models did not become ready: {last_error}")


def _port_released(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                pass
        except OSError:
            return True
        time.sleep(0.1)
    return False


def _assert_no_leaks(payloads: list[dict[str, Any]], forbidden: tuple[str, ...]) -> None:
    blob = json.dumps(payloads, sort_keys=True)
    leaked = [item for item in forbidden if item and item in blob]
    if leaked:
        raise RuntimeError(f"safe response leak detected: {', '.join(leaked)}")


def _required_env_missing() -> list[str]:
    missing = []
    for name in ("LMM_REAL_LLAMA_SERVER_BIN", "LMM_REAL_MODEL_ROOT"):
        if not os.environ.get(name, "").strip():
            missing.append(name)
    if not (
        os.environ.get("LMM_REAL_MODEL_ID", "").strip()
        or os.environ.get("LMM_REAL_MODEL_PATTERN", "").strip()
        or os.environ.get("LMM_REAL_MODEL_FILENAME", "").strip()
    ):
        missing.append("LMM_REAL_MODEL_ID or LMM_REAL_MODEL_PATTERN/LMM_REAL_MODEL_FILENAME")
    return missing


def run() -> int:
    missing = _required_env_missing()
    if missing:
        print("SKIP real llama-server validation: missing explicit env " + ", ".join(missing))
        return 0

    llama_bin = Path(os.environ["LMM_REAL_LLAMA_SERVER_BIN"]).expanduser().resolve(strict=True)
    model_root = Path(os.environ["LMM_REAL_MODEL_ROOT"]).expanduser().resolve(strict=True)
    if not llama_bin.is_file() or not os.access(llama_bin, os.X_OK):
        raise RuntimeError("LMM_REAL_LLAMA_SERVER_BIN must be an executable file")
    if not model_root.is_dir():
        raise RuntimeError("LMM_REAL_MODEL_ROOT must be a directory")

    port = _env_int("LMM_REAL_PORT", 18080, 1024, 65535)
    ctx_size = _env_int("LMM_REAL_CTX_SIZE", 8192, 512, 131072)
    gpu_layers = _env_int("LMM_REAL_GPU_LAYERS", 999, 0, 999)
    threads = _env_int("LMM_REAL_THREADS", 8, 1, 256)
    readiness_timeout = _env_float("LMM_REAL_READINESS_TIMEOUT", 60.0, 1.0, 120.0)

    proc: subprocess.Popen[str] | None = None
    payloads: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="lmm_real_llama_") as td:
        tmp = Path(td)
        socket_path = tmp / "companion.sock"
        runtime_dir = tmp / "runtime"
        config_path = tmp / "companion.json"
        config_path.write_text(
            json.dumps(
                {
                    "approved_roots": [{"id": "models", "path": str(model_root), "recursive": True}],
                    "token": TOKEN,
                    "process_runtime_dir": str(runtime_dir),
                    "profiles": {
                        PROFILE_ID: {
                            "executable": str(llama_bin),
                            "host": "0.0.0.0",
                            "default_parameters": {
                                "port": port,
                                "ctx_size": ctx_size,
                                "gpu_layers": gpu_layers,
                                "threads": threads,
                            },
                            "readiness_timeout_seconds": readiness_timeout,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        try:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tools.local_model_companion.companion",
                    "--config",
                    str(config_path),
                    "serve",
                    "--socket",
                    str(socket_path),
                ],
                cwd=str(REPO_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            _wait_for_companion(socket_path)
            scan = _http_json_unix(socket_path, "POST", "/models/scan", {})
            payloads.append(scan)
            models = scan.get("models")
            if not isinstance(models, list) or not models:
                raise RuntimeError("scan found no GGUF models in explicit approved root")
            model_id = _select_model([item for item in models if isinstance(item, dict)])

            start = _http_json_unix(
                socket_path,
                "POST",
                "/server/start",
                {
                    "model_id": model_id,
                    "profile_id": PROFILE_ID,
                    "parameters": {
                        "port": port,
                        "ctx_size": ctx_size,
                        "gpu_layers": gpu_layers,
                        "threads": threads,
                    },
                },
            )
            payloads.append(start)
            if start.get("state") != "running" or start.get("error") is not None:
                raise RuntimeError(f"real llama-server did not reach running state: {start}")

            _wait_http_models(port, timeout=10.0)
            status = _http_json_unix(socket_path, "GET", "/server/status")
            payloads.append(status)
            if status.get("state") != "running":
                raise RuntimeError(f"status did not report running: {status}")

            stop = _http_json_unix(socket_path, "POST", "/server/stop", {"grace_seconds": 10})
            payloads.append(stop)
            if stop.get("state") != "stopped" or stop.get("error") is not None:
                raise RuntimeError(f"stop did not report stopped: {stop}")
            if not _port_released(port):
                raise RuntimeError("llama-server port was not released after stop")

            _assert_no_leaks(
                payloads,
                (
                    str(llama_bin),
                    str(model_root),
                    str(socket_path),
                    str(config_path),
                    TOKEN,
                    "Authorization",
                    "argv",
                    "--host",
                    "--threads",
                ),
            )
            print("PASS real llama-server validation: launched, reached /v1/models, stopped cleanly")
            return 0
        finally:
            if proc is not None:
                try:
                    _http_json_unix(socket_path, "POST", "/server/stop", {"grace_seconds": 5})
                except Exception:
                    pass
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL real llama-server validation: {exc}")
        raise SystemExit(1)
