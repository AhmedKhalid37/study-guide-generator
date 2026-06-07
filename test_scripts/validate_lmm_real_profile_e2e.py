"""Live Docker E2E validation for a configured real LMM profile.

This manual harness validates the real configured-profile path:

  companion -> Docker backend bridge -> Local Models backend endpoints

Required env:
  LMM_REAL_LLAMA_SERVER_BIN
  LMM_REAL_MODEL_ROOT
  LMM_REAL_MODEL_ID or LMM_REAL_MODEL_PATTERN
  LMM_REAL_PORT
  LMM_REAL_CTX_SIZE
  LMM_REAL_GPU_LAYERS
  LMM_REAL_THREADS

Optional env:
  LMM_REAL_PARALLEL
  LMM_REAL_CACHE_TYPE_K
  LMM_REAL_CACHE_TYPE_V
  LMM_REAL_FLASH_ATTENTION
  LMM_REAL_MMAP
  LMM_REAL_READINESS_TIMEOUT
  LMM_REAL_BACKEND_TIMEOUT

Missing required env skips with exit 0. A full PASS requires the backend start
path to reach running readiness and the managed server to stop cleanly. A CUDA
OOM/model-too-large response is reported as a safe failure and exits 0.
"""

from __future__ import annotations

import base64
import fnmatch
import json
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
SERVICE_NAME = "app"
BACKEND_BASE_URL = "http://127.0.0.1:8000"
COMPANION_CONTAINER_DIR = "/tmp/lmm_real_profile_e2e"
PROFILE_ID = "cpu_safe_real_e2e"
APP_HEALTH_TIMEOUT_SECONDS = 120.0
COMPANION_HEALTH_TIMEOUT_SECONDS = 10.0

UNSAFE_CONFIG_KEYS = {
    "args",
    "argv",
    "command",
    "free_flags",
    "flags",
    "model_path",
    "provider_settings",
    "shell",
}


class ValidationError(RuntimeError):
    pass


class SafeFailure(RuntimeError):
    pass


results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise ValidationError(name)


def info(message: str) -> None:
    print(f"[INFO] {message}")


def _json_blob(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True)


def _sanitize_output(text: str, *, token: str, socket_path: Path, model_root: Path | None = None) -> str:
    sanitized = text.replace(token, "[redacted-token]")
    sanitized = sanitized.replace(str(socket_path), "[redacted-socket]")
    if model_root is not None:
        sanitized = sanitized.replace(str(model_root), "[redacted-model-root]")
    sanitized = re.sub(r"Authorization:\s*Bearer\s+[^\s\"']+", "[redacted-auth]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"https?://[^\s\"']+", "[redacted-url]", sanitized, flags=re.IGNORECASE)
    return sanitized[-4000:]


def _run(
    args: list[str],
    *,
    token: str,
    socket_path: Path,
    model_root: Path | None = None,
    timeout: float = 120.0,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ValidationError(f"required command not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValidationError(f"command timed out: {' '.join(args[:3])}") from exc

    if completed.returncode != 0 and not allow_failure:
        stdout = _sanitize_output(completed.stdout, token=token, socket_path=socket_path, model_root=model_root)
        stderr = _sanitize_output(completed.stderr, token=token, socket_path=socket_path, model_root=model_root)
        raise ValidationError(
            f"command failed ({completed.returncode}): {' '.join(args[:4])}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return completed


def _required_env_missing() -> list[str]:
    required = [
        "LMM_REAL_LLAMA_SERVER_BIN",
        "LMM_REAL_MODEL_ROOT",
        "LMM_REAL_PORT",
        "LMM_REAL_CTX_SIZE",
        "LMM_REAL_GPU_LAYERS",
        "LMM_REAL_THREADS",
    ]
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if not (os.environ.get("LMM_REAL_MODEL_ID", "").strip() or os.environ.get("LMM_REAL_MODEL_PATTERN", "").strip()):
        missing.append("LMM_REAL_MODEL_ID or LMM_REAL_MODEL_PATTERN")
    return missing


def _env_int(name: str, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValidationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _optional_env_int(name: str, minimum: int, maximum: int) -> int | None:
    if not os.environ.get(name, "").strip():
        return None
    return _env_int(name, minimum, maximum)


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValidationError(f"{name} must be a number") from exc
    if value < minimum or value > maximum:
        raise ValidationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _optional_env_bool(name: str) -> bool | None:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return None
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValidationError(f"{name} must be true or false")


def _optional_cache_type(name: str) -> str | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", raw):
        raise ValidationError(f"{name} must be an allowed cache type token")
    return raw


def _operator_parameters() -> dict[str, Any]:
    params: dict[str, Any] = {
        "port": _env_int("LMM_REAL_PORT", 1024, 65535),
        "ctx_size": _env_int("LMM_REAL_CTX_SIZE", 512, 131072),
        "gpu_layers": _env_int("LMM_REAL_GPU_LAYERS", 0, 999),
        "threads": _env_int("LMM_REAL_THREADS", 1, 256),
    }
    optional_ints = {
        "parallel": _optional_env_int("LMM_REAL_PARALLEL", 1, 32),
    }
    optional_enums = {
        "cache_type_k": _optional_cache_type("LMM_REAL_CACHE_TYPE_K"),
        "cache_type_v": _optional_cache_type("LMM_REAL_CACHE_TYPE_V"),
    }
    optional_bools = {
        "flash_attention": _optional_env_bool("LMM_REAL_FLASH_ATTENTION"),
        "mmap": _optional_env_bool("LMM_REAL_MMAP"),
    }
    for group in (optional_ints, optional_enums, optional_bools):
        for key, value in group.items():
            if value is not None:
                params[key] = value
    return params


def _build_companion_config(
    *,
    model_root: Path,
    token: str,
    runtime_dir: Path,
    llama_bin: Path,
    parameters: dict[str, Any],
    readiness_timeout: float,
) -> dict[str, Any]:
    return {
        "approved_roots": [{"id": "models", "path": str(model_root), "recursive": True}],
        "token": token,
        "process_runtime_dir": str(runtime_dir / "process"),
        "profiles": {
            PROFILE_ID: {
                "type": "llama_server",
                "display_name": "CPU safe real E2E",
                "description": "Operator-provided real validation profile.",
                "executable": str(llama_bin),
                "host": "0.0.0.0",
                "default_parameters": dict(parameters),
                "warnings": ["CPU mode is slower but safer."],
                "readiness_timeout_seconds": readiness_timeout,
            }
        },
    }


def _assert_config_has_no_unsafe_fields(config: dict[str, Any]) -> None:
    def walk(value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if key in UNSAFE_CONFIG_KEYS:
                    found.append(key)
                found.extend(walk(item))
        elif isinstance(value, list):
            for item in value:
                found.extend(walk(item))
        return found

    unsafe = sorted(set(walk(config)))
    if unsafe:
        raise ValidationError(f"generated companion config contains unsafe fields: {', '.join(unsafe)}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(path, 0o600)


def _write_compose_override(path: Path, runtime_dir: Path, token: str, timeout_seconds: float) -> None:
    volume_source = str(runtime_dir).replace("\\", "\\\\").replace('"', '\\"')
    path.write_text(
        "\n".join(
            [
                "services:",
                f"  {SERVICE_NAME}:",
                "    environment:",
                f"      LMM_COMPANION_SOCKET: {COMPANION_CONTAINER_DIR}/companion.sock",
                f"      LMM_COMPANION_TOKEN: {token}",
                f"      LMM_COMPANION_TIMEOUT_SECONDS: '{timeout_seconds:g}'",
                "    volumes:",
                f'      - "{volume_source}:{COMPANION_CONTAINER_DIR}:rw"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _selection_store_snapshot() -> tuple[bool, bytes]:
    path = REPO_ROOT / "config" / "local_model_library_selection.json"
    try:
        return path.exists(), path.read_bytes() if path.exists() else b""
    except OSError:
        return False, b""


def _restore_selection_store(
    override_path: Path,
    *,
    existed: bool,
    snapshot: bytes,
    token: str,
    socket_path: Path,
    model_root: Path,
) -> None:
    encoded = base64.b64encode(snapshot).decode("ascii")
    script = (
        "import base64, pathlib, sys;"
        "p=pathlib.Path('/app/config/local_model_library_selection.json');"
        "p.parent.mkdir(parents=True, exist_ok=True);"
        "p.write_bytes(base64.b64decode(sys.argv[1])) if sys.argv[2]=='1' else p.unlink(missing_ok=True)"
    )
    _run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "-f",
            str(override_path),
            "exec",
            "-T",
            SERVICE_NAME,
            "python",
            "-c",
            script,
            encoded,
            "1" if existed else "0",
        ],
        token=token,
        socket_path=socket_path,
        model_root=model_root,
        timeout=30,
        allow_failure=True,
    )


def _http_json_unix(
    socket_path: Path,
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    body_bytes = json.dumps(body or {}, separators=(",", ":"), sort_keys=True).encode("utf-8") if body is not None else b""
    request = (
        f"{method} {path} HTTP/1.1\r\n"
        "Host: local-model-companion\r\n"
        f"Authorization: Bearer {token}\r\n"
        "Accept: application/json\r\n"
        "Content-Type: application/json\r\n"
        "Connection: close\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "\r\n"
    ).encode("utf-8") + body_bytes
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    chunks: list[bytes] = []
    try:
        client.connect(str(socket_path))
        client.sendall(request)
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        client.close()
    raw = b"".join(chunks)
    header, sep, body = raw.partition(b"\r\n\r\n")
    if not sep:
        raise ValidationError("companion returned malformed HTTP")
    status_line = header.splitlines()[0].decode("iso-8859-1", errors="replace")
    parts = status_line.split()
    if len(parts) < 2 or not parts[1].isdigit() or int(parts[1]) != 200:
        raise ValidationError(f"companion health failed: {status_line}")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("companion returned non-object JSON")
    return payload


def _wait_for_companion(socket_path: Path, token: str, process: subprocess.Popen[str]) -> dict[str, Any]:
    deadline = time.monotonic() + COMPANION_HEALTH_TIMEOUT_SECONDS
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise ValidationError(
                "host companion exited before becoming ready\n"
                f"stdout:\n{_sanitize_output(stdout, token=token, socket_path=socket_path)}\n"
                f"stderr:\n{_sanitize_output(stderr, token=token, socket_path=socket_path)}"
            )
        if socket_path.exists():
            try:
                return _http_json_unix(socket_path, "GET", "/health", token)
            except (OSError, json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
        time.sleep(0.1)
    raise ValidationError(f"host companion health did not become ready: {last_error or 'socket missing'}")


def _http_json(method: str, path: str, *, body: dict[str, Any] | None = None, timeout: float = 10.0) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif method.upper() == "POST":
        data = b""
    request = urllib.request.Request(
        f"{BACKEND_BASE_URL}{path}",
        data=data,
        method=method.upper(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            response_body = json.loads(raw.decode("utf-8")) if raw else None
            return response.status, response_body
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            response_body = json.loads(raw.decode("utf-8")) if raw else None
        except json.JSONDecodeError:
            response_body = raw.decode("utf-8", errors="replace")
        return exc.code, response_body
    except (urllib.error.URLError, OSError) as exc:
        raise ValidationError(f"backend at {BACKEND_BASE_URL} is unavailable: {exc}") from exc


def _wait_for_app_health() -> None:
    deadline = time.monotonic() + APP_HEALTH_TIMEOUT_SECONDS
    last_error = ""
    while time.monotonic() < deadline:
        try:
            status, payload = _http_json("GET", "/api/health", timeout=3)
            if status == 200 and isinstance(payload, dict) and payload.get("ok") is True:
                check("backend health ready on port 8000", True, detail=str(payload))
                return
            last_error = f"status={status} body={payload}"
        except ValidationError as exc:
            last_error = str(exc)
        time.sleep(1)
    raise ValidationError(f"app health never became ready on port 8000: {last_error}")


def _docker_available(token: str, socket_path: Path, model_root: Path) -> None:
    completed = _run(
        ["docker", "version"],
        token=token,
        socket_path=socket_path,
        model_root=model_root,
        timeout=20,
        allow_failure=True,
    )
    if completed.returncode != 0:
        stdout = _sanitize_output(completed.stdout, token=token, socket_path=socket_path, model_root=model_root)
        stderr = _sanitize_output(completed.stderr, token=token, socket_path=socket_path, model_root=model_root)
        raise ValidationError(f"Docker is unavailable.\nstdout:\n{stdout}\nstderr:\n{stderr}")

    compose = _run(
        ["docker", "compose", "version"],
        token=token,
        socket_path=socket_path,
        model_root=model_root,
        timeout=20,
        allow_failure=True,
    )
    if compose.returncode != 0:
        raise ValidationError("docker compose is unavailable")


def _compose_service_running(token: str, socket_path: Path, model_root: Path) -> bool:
    completed = _run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "--services", "--status", "running"],
        token=token,
        socket_path=socket_path,
        model_root=model_root,
        timeout=30,
        allow_failure=True,
    )
    if completed.returncode != 0:
        return False
    return SERVICE_NAME in {line.strip() for line in completed.stdout.splitlines()}


def _start_companion(config_path: Path, socket_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
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
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _is_safe_relative(value: str) -> bool:
    if not value or "\x00" in value:
        return False
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or PureWindowsPath(value).is_absolute():
        return False
    parts = PurePosixPath(normalized).parts
    return bool(parts) and all(part not in ("", ".", "..") for part in parts)


def _select_model(models: list[dict[str, Any]]) -> dict[str, Any]:
    requested_id = os.environ.get("LMM_REAL_MODEL_ID", "").strip()
    if requested_id:
        for item in models:
            if item.get("id") == requested_id:
                return item
        raise ValidationError("LMM_REAL_MODEL_ID was not found in scanned approved root")

    pattern = os.environ.get("LMM_REAL_MODEL_PATTERN", "").strip()
    if not pattern:
        raise ValidationError("missing LMM_REAL_MODEL_ID or LMM_REAL_MODEL_PATTERN")
    for item in models:
        candidates = [
            item.get("filename"),
            item.get("relative_path"),
            item.get("display_name"),
            item.get("id"),
        ]
        if any(isinstance(value, str) and fnmatch.fnmatch(value, pattern) for value in candidates):
            return item
    raise ValidationError("model pattern did not match any scanned GGUF model")


def _safe_failure_category(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    category = error.get("category")
    return category if isinstance(category, str) else None


def _assert_safe_payloads(payloads: list[Any], *, token: str, socket_path: Path, runtime_dir: Path, model_root: Path, llama_bin: Path) -> None:
    blob = _json_blob(payloads)
    forbidden = {
        "token": token,
        "host_socket": str(socket_path),
        "container_socket": f"{COMPANION_CONTAINER_DIR}/companion.sock",
        "runtime_dir": str(runtime_dir),
        "model_root": str(model_root),
        "llama_bin": str(llama_bin),
        "authorization": "Authorization",
        "raw_argv": "argv",
        "raw_model_flag": "--model",
    }
    leaked = [name for name, value in forbidden.items() if value and value in blob]
    url_leak = re.search(r"https?://[^\s\"']+", blob, re.IGNORECASE)
    if url_leak:
        leaked.append("full_url")
    check("redaction: no token/socket/absolute path/auth/url/raw argv leaks", not leaked, detail=", ".join(leaked))


def _assert_relative_model_paths(models: Any) -> None:
    if not isinstance(models, list) or not models:
        raise ValidationError("scan returned no models")
    for model in models:
        if not isinstance(model, dict):
            raise ValidationError("scan returned a non-object model")
        relative_path = model.get("relative_path")
        check(
            f"model path is root-relative only for {model.get('filename') or model.get('id')}",
            isinstance(relative_path, str) and _is_safe_relative(relative_path),
            detail=str(relative_path),
        )


def _port_released(port: int, timeout: float = 8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                pass
        except OSError:
            return True
        time.sleep(0.1)
    return False


def _wait_for_running_or_safe_failure(timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        status, payload = _http_json("GET", "/api/local-model/server/status", timeout=10)
        if status != 200 or not isinstance(payload, dict):
            raise ValidationError(f"server/status failed while polling: status={status} body={payload}")
        last = payload
        if payload.get("state") == "running":
            return payload
        if _safe_failure_category(payload) == "model_may_be_too_large":
            raise SafeFailure("server reported model_may_be_too_large during readiness")
        if payload.get("state") in {"error", "crashed"}:
            raise ValidationError(f"server failed before readiness: {payload}")
        time.sleep(1)
    raise ValidationError(f"server did not reach running before timeout: {last}")


def _validate_backend_flow(
    *,
    model_root: Path,
    runtime_dir: Path,
    socket_path: Path,
    token: str,
    llama_bin: Path,
    parameters: dict[str, Any],
    readiness_timeout: float,
) -> None:
    payloads: list[Any] = []

    status_code, status_body = _http_json("GET", "/api/local-model/companion/status")
    payloads.append(status_body)
    check(
        "GET companion/status reaches configured companion",
        status_code == 200
        and isinstance(status_body, dict)
        and status_body.get("configured") is True
        and status_body.get("reachable") is True
        and "server_profiles" in status_body.get("capabilities", []),
        detail=str(status_body),
    )

    scan_code, scan_body = _http_json("POST", "/api/local-model/library/scan", timeout=30)
    payloads.append(scan_body)
    check("POST library/scan returns models", scan_code == 200 and isinstance(scan_body, dict), detail=str(scan_body))
    models = scan_body.get("models") if isinstance(scan_body, dict) else None
    _assert_relative_model_paths(models)
    selected_model = _select_model([item for item in models if isinstance(item, dict)])
    model_id = selected_model.get("id")
    check("selected real GGUF model id is available", isinstance(model_id, str) and bool(model_id), detail=str(selected_model))

    profiles_code, profiles_body = _http_json("GET", "/api/local-model/server/profiles")
    payloads.append(profiles_body)
    profiles = profiles_body.get("profiles") if isinstance(profiles_body, dict) else None
    check(
        "GET server/profiles exposes configured real profile safely",
        profiles_code == 200
        and isinstance(profiles, list)
        and any(item.get("id") == PROFILE_ID and item.get("runnable") is True for item in profiles if isinstance(item, dict)),
        detail=str(profiles_body),
    )

    selection_code, selection_body = _http_json(
        "POST",
        "/api/local-model/library/selection",
        body={"model_id": model_id, "model": selected_model},
    )
    payloads.append(selection_body)
    check(
        "POST library/selection saves selected real model metadata",
        selection_code == 200
        and isinstance(selection_body, dict)
        and isinstance(selection_body.get("selected"), dict)
        and selection_body["selected"].get("id") == model_id,
        detail=str(selection_body),
    )

    start_payload = {"model_id": model_id, "profile_id": PROFILE_ID, "parameters": dict(parameters)}
    start_code, start_body = _http_json("POST", "/api/local-model/server/start", body=start_payload, timeout=readiness_timeout + 20)
    payloads.append(start_body)
    if _safe_failure_category(start_body) == "model_may_be_too_large":
        _assert_safe_payloads(payloads, token=token, socket_path=socket_path, runtime_dir=runtime_dir, model_root=model_root, llama_bin=llama_bin)
        raise SafeFailure("server/start reported model_may_be_too_large")
    check(
        "POST server/start reaches running or already_running",
        start_code == 200
        and isinstance(start_body, dict)
        and start_body.get("state") in {"running", "already_running"}
        and start_body.get("managed") is True,
        detail=str(start_body),
    )

    running_body = _wait_for_running_or_safe_failure(readiness_timeout + 10)
    payloads.append(running_body)
    check(
        "GET server/status reports running",
        running_body.get("state") == "running" and running_body.get("managed") is True and running_body.get("port") == parameters["port"],
        detail=str(running_body),
    )

    info("skipping /api/local-model/status: no Provider Settings writes are allowed, so the local provider URL is not repointed")

    stop_code, stop_body = _http_json("POST", "/api/local-model/server/stop", body={"grace_seconds": 10}, timeout=30)
    payloads.append(stop_body)
    check(
        "POST server/stop returns stopped",
        stop_code == 200
        and isinstance(stop_body, dict)
        and stop_body.get("state") in {"stopped", "not_running", "stale_pid"},
        detail=str(stop_body),
    )

    stopped_code, stopped_body = _http_json("GET", "/api/local-model/server/status")
    payloads.append(stopped_body)
    check(
        "GET server/status reports stopped after stop",
        stopped_code == 200
        and isinstance(stopped_body, dict)
        and stopped_body.get("state") in {"stopped", "not_running"},
        detail=str(stopped_body),
    )
    check("managed llama-server port released", _port_released(int(parameters["port"])), detail=f"port={parameters['port']}")
    _assert_safe_payloads(payloads, token=token, socket_path=socket_path, runtime_dir=runtime_dir, model_root=model_root, llama_bin=llama_bin)


def run() -> int:
    missing = _required_env_missing()
    if missing:
        print("SKIP real configured-profile E2E validation: missing explicit env " + ", ".join(missing))
        return 0

    llama_bin = Path(os.environ["LMM_REAL_LLAMA_SERVER_BIN"]).expanduser().resolve(strict=True)
    model_root = Path(os.environ["LMM_REAL_MODEL_ROOT"]).expanduser().resolve(strict=True)
    if not llama_bin.is_file() or not os.access(llama_bin, os.X_OK):
        raise ValidationError("LMM_REAL_LLAMA_SERVER_BIN must be an executable file")
    if not model_root.is_dir():
        raise ValidationError("LMM_REAL_MODEL_ROOT must be a directory")

    parameters = _operator_parameters()
    readiness_timeout = _env_float("LMM_REAL_READINESS_TIMEOUT", 90.0, 1.0, 120.0)
    backend_timeout = _env_float("LMM_REAL_BACKEND_TIMEOUT", 15.0, 1.0, 30.0)

    token = f"tok-lmm-phase2g8-{secrets.token_hex(16)}"
    temp_dir = Path(tempfile.mkdtemp(prefix="lmm_real_profile_e2e_", dir="/tmp"))
    runtime_dir = temp_dir / "runtime"
    config_path = temp_dir / "companion_config.json"
    override_path = temp_dir / "compose.override.yml"
    socket_path = runtime_dir / "companion.sock"
    companion_process: subprocess.Popen[str] | None = None
    compose_started = False
    was_running = False
    selection_existed, selection_snapshot = _selection_store_snapshot()

    try:
        runtime_dir.mkdir(mode=0o755)
        config = _build_companion_config(
            model_root=model_root,
            token=token,
            runtime_dir=runtime_dir,
            llama_bin=llama_bin,
            parameters=parameters,
            readiness_timeout=readiness_timeout,
        )
        _assert_config_has_no_unsafe_fields(config)
        _write_json(config_path, config)
        _write_compose_override(override_path, runtime_dir, token, backend_timeout)

        info("temporary validation root created")
        _docker_available(token, socket_path, model_root)
        was_running = _compose_service_running(token, socket_path, model_root)
        info(f"compose service '{SERVICE_NAME}' was {'running' if was_running else 'not running'} before validation")

        companion_process = _start_companion(config_path, socket_path)
        companion_health = _wait_for_companion(socket_path, token, companion_process)
        check(
            "host companion health over Unix socket",
            companion_health.get("ok") is True and "server_profiles" in companion_health.get("capabilities", []),
            detail=str({k: companion_health.get(k) for k in ("ok", "version", "platform", "capabilities")}),
        )
        socket_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)

        _run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "-f",
                str(override_path),
                "up",
                "-d",
                "--build",
                SERVICE_NAME,
            ],
            token=token,
            socket_path=socket_path,
            model_root=model_root,
            timeout=300,
        )
        compose_started = True
        _wait_for_app_health()
        _validate_backend_flow(
            model_root=model_root,
            runtime_dir=runtime_dir,
            socket_path=socket_path,
            token=token,
            llama_bin=llama_bin,
            parameters=parameters,
            readiness_timeout=readiness_timeout,
        )

    except SafeFailure as exc:
        print(f"SAFE_FAIL real configured-profile E2E validation: {exc}")
        return 0
    finally:
        if compose_started:
            try:
                _restore_selection_store(
                    override_path,
                    existed=selection_existed,
                    snapshot=selection_snapshot,
                    token=token,
                    socket_path=socket_path,
                    model_root=model_root,
                )
                if was_running:
                    info("restoring app service with committed Compose file only")
                    _run(
                        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build", SERVICE_NAME],
                        token=token,
                        socket_path=socket_path,
                        model_root=model_root,
                        timeout=300,
                        allow_failure=True,
                    )
                else:
                    info("stopping validation app service because it was not running before validation")
                    _run(
                        ["docker", "compose", "-f", str(COMPOSE_FILE), "-f", str(override_path), "down"],
                        token=token,
                        socket_path=socket_path,
                        model_root=model_root,
                        timeout=120,
                        allow_failure=True,
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] compose cleanup failed: {exc}")

        if companion_process is not None:
            try:
                _http_json_unix(socket_path, "POST", "/server/stop", token, {"grace_seconds": 5}, timeout=5)
            except Exception:
                pass
            if companion_process.poll() is None:
                companion_process.terminate()
                try:
                    companion_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    companion_process.kill()
                    companion_process.wait(timeout=5)
        shutil.rmtree(temp_dir, ignore_errors=True)

    failed = [name for name, ok, _detail in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print(
        "PASS real configured-profile E2E validation: "
        f"port={parameters['port']} ctx_size={parameters['ctx_size']} "
        f"gpu_layers={parameters['gpu_layers']} threads={parameters['threads']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except ValidationError as exc:
        print(f"[ERROR] {exc}")
        failed = [name for name, ok, _detail in results if not ok]
        if failed:
            print("FAILED:", ", ".join(failed))
        raise SystemExit(1)
