"""Live Docker validation for the LMM Phase 2C companion socket mount.

This is a manual smoke harness, not part of normal release smoke:

    python test_scripts/validate_lmm_companion_socket_mount.py

It starts the stdlib host companion on a temporary Unix socket, recreates the
Docker app service with a temporary Compose override that mounts only that temp
runtime directory, and verifies the read-only backend bridge endpoints through
http://127.0.0.1:8000.
"""

from __future__ import annotations

import json
import os
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
COMPANION_CONTAINER_DIR = "/tmp/lmm_socket_mount_validation"
APP_HEALTH_TIMEOUT_SECONDS = 90.0
COMPANION_HEALTH_TIMEOUT_SECONDS = 10.0


class ValidationError(RuntimeError):
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


def _sanitize_output(text: str, token: str, socket_path: Path) -> str:
    sanitized = text.replace(token, "[redacted-token]")
    sanitized = sanitized.replace(str(socket_path), "[redacted-socket]")
    return sanitized[-4000:]


def _run(
    args: list[str],
    *,
    token: str,
    socket_path: Path,
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
        stdout = _sanitize_output(completed.stdout, token, socket_path)
        stderr = _sanitize_output(completed.stderr, token, socket_path)
        raise ValidationError(
            f"command failed ({completed.returncode}): {' '.join(args[:4])}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return completed


def _docker_available(token: str, socket_path: Path) -> None:
    completed = _run(["docker", "version"], token=token, socket_path=socket_path, timeout=20, allow_failure=True)
    if completed.returncode != 0:
        stderr = _sanitize_output(completed.stderr, token, socket_path)
        stdout = _sanitize_output(completed.stdout, token, socket_path)
        raise ValidationError(
            "Docker is unavailable. Start Docker, ensure this user can access the Docker daemon, "
            f"then rerun the harness.\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    compose = _run(
        ["docker", "compose", "version"],
        token=token,
        socket_path=socket_path,
        timeout=20,
        allow_failure=True,
    )
    if compose.returncode != 0:
        raise ValidationError("docker compose is unavailable. Install the Docker Compose plugin and rerun.")


def _compose_service_exists(token: str, socket_path: Path) -> None:
    completed = _run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--services"],
        token=token,
        socket_path=socket_path,
        timeout=30,
        allow_failure=True,
    )
    if completed.returncode != 0:
        raise ValidationError("Unable to read Compose services. Expected docker-compose.yml service: app.")
    services = {line.strip() for line in completed.stdout.splitlines() if line.strip()}
    check("compose service app exists", SERVICE_NAME in services, detail=f"services={sorted(services)}")


def _compose_service_running(token: str, socket_path: Path) -> bool:
    completed = _run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "--services", "--status", "running"],
        token=token,
        socket_path=socket_path,
        timeout=30,
        allow_failure=True,
    )
    if completed.returncode != 0:
        return False
    return SERVICE_NAME in {line.strip() for line in completed.stdout.splitlines()}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_compose_override(path: Path, runtime_dir: Path, token: str) -> None:
    volume_source = str(runtime_dir).replace("\\", "\\\\").replace('"', '\\"')
    path.write_text(
        "\n".join(
            [
                "services:",
                f"  {SERVICE_NAME}:",
                "    environment:",
                f"      LMM_COMPANION_SOCKET: {COMPANION_CONTAINER_DIR}/companion.sock",
                f"      LMM_COMPANION_TOKEN: {token}",
                "      LMM_COMPANION_TIMEOUT_SECONDS: '3'",
                "    volumes:",
                f'      - "{volume_source}:{COMPANION_CONTAINER_DIR}:rw"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _http_json_unix(socket_path: Path, method: str, path: str, token: str, timeout: float = 2.0) -> dict[str, Any]:
    request = (
        f"{method} {path} HTTP/1.1\r\n"
        "Host: local-model-companion\r\n"
        f"Authorization: Bearer {token}\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    ).encode("utf-8")
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
                f"stdout:\n{_sanitize_output(stdout, token, socket_path)}\n"
                f"stderr:\n{_sanitize_output(stderr, token, socket_path)}"
            )
        if socket_path.exists():
            try:
                payload = _http_json_unix(socket_path, "GET", "/health", token)
                return payload
            except (OSError, json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
        time.sleep(0.1)
    raise ValidationError(f"host companion health did not become ready: {last_error or 'socket missing'}")


def _http_json(method: str, path: str, *, timeout: float = 5.0) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"{BACKEND_BASE_URL}{path}",
        data=b"" if method.upper() == "POST" else None,
        method=method.upper(),
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            body = json.loads(raw.decode("utf-8")) if raw else None
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except json.JSONDecodeError:
            body = raw.decode("utf-8", errors="replace")
        return exc.code, body
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


def _is_safe_relative(value: str) -> bool:
    if not value or "\x00" in value:
        return False
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or PureWindowsPath(value).is_absolute():
        return False
    parts = PurePosixPath(normalized).parts
    return bool(parts) and all(part not in ("", ".", "..") for part in parts)


def _assert_no_leaks(payloads: list[Any], token: str, socket_path: Path, runtime_dir: Path, model_root: Path) -> None:
    blob = _json_blob(payloads)
    forbidden = {
        "token": token,
        "host_socket": str(socket_path),
        "container_socket": f"{COMPANION_CONTAINER_DIR}/companion.sock",
        "runtime_dir": str(runtime_dir),
        "model_root": str(model_root),
    }
    leaked = [name for name, value in forbidden.items() if value and value in blob]
    check("redaction: no token/socket/raw temp host path in backend responses", not leaked, detail=", ".join(leaked))


def _validate_backend_endpoints(token: str, socket_path: Path, runtime_dir: Path, model_root: Path) -> None:
    status_code, status_body = _http_json("GET", "/api/local-model/companion/status")
    check("GET companion/status returns 200", status_code == 200, detail=str(status_body))
    check(
        "companion status is configured and reachable with scan capability",
        isinstance(status_body, dict)
        and status_body.get("configured") is True
        and status_body.get("reachable") is True
        and "scan" in status_body.get("capabilities", []),
        detail=str(status_body),
    )

    pre_code, pre_body = _http_json("GET", "/api/local-model/library")
    check("GET library before scan returns 200", pre_code == 200, detail=str(pre_body))
    check(
        "pre-scan library is safe and empty",
        isinstance(pre_body, dict)
        and pre_body.get("configured") is True
        and pre_body.get("reachable") is True
        and pre_body.get("models") == []
        and pre_body.get("model_count") == 0,
        detail=str(pre_body),
    )

    scan_code, scan_body = _http_json("POST", "/api/local-model/library/scan")
    check("POST library/scan returns 200", scan_code == 200, detail=str(scan_body))
    models = scan_body.get("models") if isinstance(scan_body, dict) else None
    filenames = {model.get("filename") for model in models or [] if isinstance(model, dict)}
    check(
        "scan returns fake GGUF models and excludes non-GGUF file",
        isinstance(models, list)
        and {"gemma-validation-Q4_K_M.gguf", "qwen-validation-Q8_0.GGUF"}.issubset(filenames)
        and "notes.txt" not in _json_blob(scan_body),
        detail=str(sorted(filenames)),
    )

    post_code, post_body = _http_json("GET", "/api/local-model/library")
    check("GET library after scan returns 200", post_code == 200, detail=str(post_body))
    check(
        "post-scan cached library returns scanned models",
        isinstance(post_body, dict) and post_body.get("model_count") == len(models or []) and post_body.get("model_count", 0) >= 2,
        detail=f"model_count={post_body.get('model_count') if isinstance(post_body, dict) else None}",
    )

    for model in models or []:
        relative_path = model.get("relative_path") if isinstance(model, dict) else None
        check(
            f"relative_path is root-relative only for {model.get('filename') if isinstance(model, dict) else '<bad>'}",
            isinstance(relative_path, str) and _is_safe_relative(relative_path),
            detail=str(relative_path),
        )

    _assert_no_leaks([status_body, pre_body, scan_body, post_body], token, socket_path, runtime_dir, model_root)

    for endpoint in (
        "/api/local-model/server/start",
        "/api/local-model/server/stop",
        "/api/local-model/server/restart",
    ):
        process_code, process_body = _http_json("POST", endpoint)
        check(
            f"process-control endpoint unavailable: {endpoint}",
            process_code in (404, 405),
            detail=f"status={process_code} body={process_body}",
        )


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


def run() -> int:
    token = f"tok-lmm-phase2c-{secrets.token_hex(16)}"
    temp_dir = Path(tempfile.mkdtemp(prefix="lmm_socket_mount_validation_", dir="/tmp"))
    runtime_dir = temp_dir / "runtime"
    model_root = temp_dir / "approved_models"
    config_path = temp_dir / "companion_config.json"
    override_path = temp_dir / "compose.override.yml"
    socket_path = runtime_dir / "companion.sock"
    companion_process: subprocess.Popen[str] | None = None
    compose_started = False
    was_running = False

    try:
        runtime_dir.mkdir(mode=0o755)
        model_root.mkdir(mode=0o700)
        nested = model_root / "nested"
        nested.mkdir()
        (model_root / "gemma-validation-Q4_K_M.gguf").write_bytes(b"gguf validation fixture")
        (nested / "qwen-validation-Q8_0.GGUF").write_bytes(b"gguf validation fixture")
        (model_root / "notes.txt").write_text("not a model", encoding="utf-8")
        _write_json(
            config_path,
            {
                "approved_roots": [{"id": "validation", "path": str(model_root), "recursive": True}],
                "token": token,
            },
        )
        os.chmod(config_path, 0o600)
        _write_compose_override(override_path, runtime_dir, token)

        info(f"temporary validation root: {temp_dir}")
        _docker_available(token, socket_path)
        _compose_service_exists(token, socket_path)
        was_running = _compose_service_running(token, socket_path)
        info(f"compose service '{SERVICE_NAME}' was {'running' if was_running else 'not running'} before validation")

        companion_process = _start_companion(config_path, socket_path)
        companion_health = _wait_for_companion(socket_path, token, companion_process)
        check(
            "host companion health over Unix socket",
            companion_health.get("ok") is True and "scan" in companion_health.get("capabilities", []),
            detail=str({k: companion_health.get(k) for k in ("ok", "version", "platform", "capabilities")}),
        )

        # The prototype companion creates a 0600 host-user socket. The current
        # Docker image drops to appuser uid 10001, so this temporary validation
        # socket is relaxed while token auth remains required.
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
            timeout=300,
        )
        compose_started = True
        _wait_for_app_health()
        _validate_backend_endpoints(token, socket_path, runtime_dir, model_root)

    finally:
        if compose_started:
            try:
                if was_running:
                    info("restoring app service with committed Compose file only")
                    _run(
                        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build", SERVICE_NAME],
                        token=token,
                        socket_path=socket_path,
                        timeout=300,
                        allow_failure=True,
                    )
                else:
                    info("stopping validation app service because it was not running before validation")
                    _run(
                        ["docker", "compose", "-f", str(COMPOSE_FILE), "-f", str(override_path), "down"],
                        token=token,
                        socket_path=socket_path,
                        timeout=120,
                        allow_failure=True,
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] compose cleanup failed: {exc}")

        if companion_process is not None and companion_process.poll() is None:
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
    print("Live Docker/socket mount validation passed.")
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
