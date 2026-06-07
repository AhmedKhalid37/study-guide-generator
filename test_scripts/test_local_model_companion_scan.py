"""Tests for LMM Phase 2B host companion approved-folder GGUF scanning.

    python test_scripts/test_local_model_companion_scan.py
"""

import inspect
import json
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.local_model_companion import companion, config, model_library  # noqa: E402
from tools.local_model_companion.config import ApprovedRoot, CompanionConfig  # noqa: E402
from tools.local_model_companion.model_library import ScanLimits, scan_models  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _write_config(path: Path, roots, token=None):
    data = {"approved_roots": roots}
    if token is not None:
        data["token"] = token
    path.write_text(json.dumps(data), encoding="utf-8")


def _scan(root: Path, recursive=True, limits=None):
    cfg = CompanionConfig((ApprovedRoot("default", root.resolve(strict=False), recursive),), configured=True)
    return scan_models(cfg, limits or ScanLimits())


def _blob(payload):
    return json.dumps(payload, sort_keys=True)


def _read_http(sock_path: Path, request: bytes):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(2)
    client.connect(str(sock_path))
    client.sendall(request)
    chunks = []
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
    header, body = raw.split(b"\r\n\r\n", 1)
    status_line = header.splitlines()[0].decode("ascii")
    return status_line, json.loads(body.decode("utf-8"))


def run():
    with tempfile.TemporaryDirectory(prefix="lmm_companion_") as td:
        tmp = Path(td)

        # 1. No explicit config means no roots and no scan.
        old_env = os.environ.pop(config.CONFIG_ENV_VAR, None)
        old_token = os.environ.pop(config.TOKEN_ENV_VAR, None)
        cfg_none = config.load_config(None)
        res_none = scan_models(cfg_none)
        check(
            "no-config: no approved roots configured and no models",
            res_none["models"] == [] and res_none["scanned_roots"] == 0 and res_none["roots_configured"] == 0,
            detail=str(res_none),
        )
        check(
            "no-config: warning is safe and bounded",
            res_none["warnings"] and res_none["warnings"][0]["code"] == "no_approved_roots",
            detail=str(res_none["warnings"]),
        )

        # 2. Non-existent root warns without exposing the absolute host path.
        missing = tmp / "missing"
        res_missing = _scan(missing)
        check(
            "missing-root: warning returned, no crash",
            res_missing["models"] == [] and any(w["code"] == "root_missing" for w in res_missing["warnings"]),
            detail=str(res_missing),
        )
        check(
            "missing-root: response does not include absolute missing path",
            str(missing) not in _blob(res_missing),
            detail=_blob(res_missing),
        )

        # 3. Simple GGUF record shape and safe metadata.
        root = tmp / "models"
        root.mkdir()
        model = root / "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
        model.write_bytes(b"gguf")
        (root / "notes.txt").write_text("ignore", encoding="utf-8")
        res_simple = _scan(root)
        models = res_simple["models"]
        check(
            "simple-root: one .gguf model returned",
            len(models) == 1 and models[0]["filename"] == model.name,
            detail=str(models),
        )
        rec = models[0]
        check(
            "simple-root: non-GGUF ignored",
            "notes.txt" not in _blob(res_simple),
            detail=_blob(res_simple),
        )
        check(
            "metadata: root-relative path and no absolute host path",
            rec["relative_path"] == model.name and str(root) not in _blob(rec),
            detail=str(rec),
        )
        check(
            "metadata: family and quant hints parsed",
            rec["family_hint"] == "gemma" and rec["quant_hint"] == "Q4_K_M",
            detail=str(rec),
        )
        check(
            "metadata: stable opaque id across scans",
            rec["id"] == _scan(root)["models"][0]["id"] and rec["id"].startswith("gguf_"),
            detail=rec["id"],
        )

        # 4. Recursive scan only under approved root.
        nested = root / "gemma"
        nested.mkdir()
        nested_model = nested / "llama-3-Q8_0.GGUF"
        nested_model.write_bytes(b"gguf")
        res_recursive = _scan(root, recursive=True)
        rels_recursive = {m["relative_path"] for m in res_recursive["models"]}
        res_flat = _scan(root, recursive=False)
        rels_flat = {m["relative_path"] for m in res_flat["models"]}
        check(
            "recursive: nested .GGUF is found case-insensitively",
            "gemma/llama-3-Q8_0.GGUF" in rels_recursive,
            detail=str(rels_recursive),
        )
        check(
            "non-recursive: nested file is not scanned",
            "gemma/llama-3-Q8_0.GGUF" not in rels_flat,
            detail=str(rels_flat),
        )

        # 5. Symlink file inside approved root accepted; symlink escape rejected.
        symlink_root = tmp / "symlink_root"
        symlink_root.mkdir()
        inner_dir = symlink_root / "inner"
        inner_dir.mkdir()
        inner_target = inner_dir / "phi-3-Q5_K_M.gguf"
        inner_target.write_bytes(b"gguf")
        (symlink_root / "alias.gguf").symlink_to(inner_target)
        outside = tmp / "outside-Q4_0.gguf"
        outside.write_bytes(b"gguf")
        (symlink_root / "escape.gguf").symlink_to(outside)
        res_symlink = _scan(symlink_root)
        rels_symlink = {m["relative_path"] for m in res_symlink["models"]}
        check(
            "symlink-inside: resolved file inside approved root is accepted",
            "inner/phi-3-Q5_K_M.gguf" in rels_symlink,
            detail=str(res_symlink),
        )
        check(
            "symlink-escape: target outside approved root is rejected",
            any(w["code"] == "symlink_escape_rejected" for w in res_symlink["warnings"])
            and str(outside) not in _blob(res_symlink),
            detail=str(res_symlink["warnings"]),
        )

        # 6. Broken symlink warning is bounded/safe.
        broken_root = tmp / "broken_root"
        broken_root.mkdir()
        (broken_root / "broken.gguf").symlink_to(broken_root / "missing.gguf")
        res_broken = _scan(broken_root)
        check(
            "broken-symlink: warning returned, no crash",
            any(w["code"] == "broken_symlink" for w in res_broken["warnings"]),
            detail=str(res_broken["warnings"]),
        )

        # 7. Explicit traversal candidate outside root is rejected by the scanner guard.
        warnings = model_library.WarningCollector(5)
        record, rejected = model_library._record_for_candidate(  # private guard tested intentionally
            ApprovedRoot("default", root.resolve(strict=False), True),
            root.resolve(strict=False),
            outside,
            warnings,
        )
        check(
            "traversal-guard: direct candidate outside approved root rejected",
            record is None and rejected is True and warnings.items[0]["code"] == "traversal_rejected",
            detail=str(warnings.items),
        )

        # 8. Max models and bounded warnings behavior.
        limit_root = tmp / "limit_root"
        limit_root.mkdir()
        for index in range(4):
            (limit_root / f"qwen-{index}-Q4_K_M.gguf").write_bytes(b"gguf")
        res_limited = _scan(
            limit_root,
            limits=ScanLimits(max_files_inspected=100, max_models_returned=2, max_warnings=3, timeout_seconds=10),
        )
        check(
            "limits: max models returned is enforced",
            len(res_limited["models"]) == 2 and any(w["code"] == "max_models_returned" for w in res_limited["warnings"]),
            detail=str(res_limited),
        )
        noisy_root = tmp / "noisy_root"
        noisy_root.mkdir()
        for index in range(5):
            (noisy_root / f"broken-{index}.gguf").symlink_to(noisy_root / f"missing-{index}.gguf")
        res_noisy = _scan(
            noisy_root,
            limits=ScanLimits(max_files_inspected=100, max_models_returned=100, max_warnings=2, timeout_seconds=10),
        )
        check(
            "warnings: warning list is bounded",
            len(res_noisy["warnings"]) <= 2,
            detail=str(res_noisy["warnings"]),
        )

        # 9. Config file shape and token source.
        cfg_path = tmp / "companion.json"
        _write_config(
            cfg_path,
            [{"id": "default", "path": str(root), "recursive": True}],
            token="secret-token",
        )
        cfg = config.load_config(cfg_path)
        check(
            "config: explicit approved_roots shape loads",
            cfg.configured is True
            and len(cfg.approved_roots) == 1
            and cfg.approved_roots[0].id == "default"
            and cfg.approved_roots[0].recursive is True
            and cfg.token == "secret-token",
        )

        # 10. Unix socket API requires auth and exposes health/models/scan.
        sock_path = tmp / "companion.sock"
        state = companion.CompanionState(cfg, ScanLimits(max_files_inspected=100, max_models_returned=100))
        body_scan = {"models": []}
        try:
            server = companion.UnixHTTPServer(str(sock_path), companion.CompanionRequestHandler, state)
        except PermissionError as exc:
            check(
                "socket: Unix socket server implemented, runtime bind skipped by sandbox",
                issubclass(companion.UnixHTTPServer, companion.socketserver.UnixStreamServer)
                and hasattr(companion.CompanionRequestHandler, "do_GET")
                and hasattr(companion.CompanionRequestHandler, "do_POST"),
                detail=str(exc),
            )
            body_scan = state.scan()
        else:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                status_unauth, body_unauth = _read_http(
                    sock_path,
                    b"GET /health HTTP/1.1\r\nHost: companion\r\n\r\n",
                )
                status_health, body_health = _read_http(
                    sock_path,
                    b"GET /health HTTP/1.1\r\nHost: companion\r\nAuthorization: Bearer secret-token\r\n\r\n",
                )
                status_models, body_models = _read_http(
                    sock_path,
                    b"GET /models HTTP/1.1\r\nHost: companion\r\nAuthorization: Bearer secret-token\r\n\r\n",
                )
                status_scan, body_scan = _read_http(
                    sock_path,
                    b"POST /models/scan HTTP/1.1\r\nHost: companion\r\nAuthorization: Bearer secret-token\r\nContent-Length: 0\r\n\r\n",
                )
                check(
                    "socket: unauthorized request rejected",
                    status_unauth.startswith("HTTP/1.0 401") and body_unauth["error"]["code"] == "unauthorized",
                    detail=str(body_unauth),
                )
                check(
                    "socket: health endpoint returns scan capability",
                    status_health.startswith("HTTP/1.0 200") and body_health["capabilities"] == ["scan"],
                    detail=str(body_health),
                )
                check(
                    "socket: GET /models is cached and does not scan before POST",
                    status_models.startswith("HTTP/1.0 200") and body_models["models"] == [] and body_models["last_scan_at"] is None,
                    detail=str(body_models),
                )
                check(
                    "socket: POST /models/scan scans approved roots",
                    status_scan.startswith("HTTP/1.0 200") and len(body_scan["models"]) >= 1 and body_scan["last_scan_at"],
                    detail=str(body_scan),
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        # 11. Source inspection: no shell execution or direct spawn in companion HTTP/config/scan code.
        companion_sources = "\n".join(
            inspect.getsource(module) for module in (companion, config, model_library)
        )
        forbidden = (
            "Popen(",
            "os.system(",
            "shell=True",
            "llama-server",
        )
        check(
            "safety-source: no direct subprocess/shell/real llama-server in companion HTTP/config/scan code",
            all(term not in companion_sources for term in forbidden),
            detail=", ".join(term for term in forbidden if term in companion_sources),
        )

        # 12. Final absolute-path leak check for model records.
        combined_records = res_simple["models"] + res_recursive["models"] + res_symlink["models"] + body_scan["models"]
        records_blob = _blob(combined_records)
        check(
            "records: absolute host paths are absent from model records",
            str(tmp) not in records_blob and str(root) not in records_blob and str(symlink_root) not in records_blob,
            detail=records_blob,
        )

        if old_env is not None:
            os.environ[config.CONFIG_ENV_VAR] = old_env
        if old_token is not None:
            os.environ[config.TOKEN_ENV_VAR] = old_token

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
