"""Unit checks for the Phase 2G8 real configured-profile E2E harness.

These tests do not require Docker, llama-server, or real models. The live path is
covered by:

    python test_scripts/validate_lmm_real_profile_e2e.py
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import validate_lmm_real_profile_e2e as harness


results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def run() -> int:
    old_env = {
        key: os.environ.get(key)
        for key in (
            "LMM_REAL_LLAMA_SERVER_BIN",
            "LMM_REAL_MODEL_ROOT",
            "LMM_REAL_MODEL_ID",
            "LMM_REAL_MODEL_PATTERN",
            "LMM_REAL_PORT",
            "LMM_REAL_CTX_SIZE",
            "LMM_REAL_GPU_LAYERS",
            "LMM_REAL_THREADS",
        )
    }
    try:
        for key in old_env:
            os.environ.pop(key, None)
        missing = harness._required_env_missing()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            skip_code = harness.run()
        skip_output = buffer.getvalue()
        check(
            "skip: missing explicit env exits 0 before Docker work",
            skip_code == 0
            and "SKIP real configured-profile E2E validation" in skip_output
            and "LMM_REAL_LLAMA_SERVER_BIN" in missing
            and "LMM_REAL_PORT" in missing,
            detail=skip_output.strip(),
        )

        with tempfile.TemporaryDirectory(prefix="lmm_e2e_harness_test_") as td:
            tmp = Path(td)
            model_root = tmp / "models"
            runtime_dir = tmp / "runtime"
            llama_bin = tmp / "llama-server"
            override_path = tmp / "compose.override.yml"
            socket_path = runtime_dir / "companion.sock"
            model_root.mkdir()
            runtime_dir.mkdir()
            llama_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            llama_bin.chmod(0o700)
            token = "tok-phase2g8-SUPERSECRET"
            params = {
                "port": 18080,
                "ctx_size": 4096,
                "gpu_layers": 0,
                "threads": 8,
                "parallel": 1,
                "cache_type_k": "f16",
                "flash_attention": False,
                "mmap": True,
            }

            config = harness._build_companion_config(
                model_root=model_root,
                token=token,
                runtime_dir=runtime_dir,
                llama_bin=llama_bin,
                parameters=params,
                readiness_timeout=90.0,
            )
            harness._assert_config_has_no_unsafe_fields(config)
            config_blob = _blob(config)
            check(
                "config: generated companion config has no unsafe launch fields",
                all(key not in config_blob for key in ("argv", "args", "command", "free_flags", "model_path", "shell"))
                and config["profiles"][harness.PROFILE_ID]["default_parameters"]["gpu_layers"] == 0
                and config["profiles"][harness.PROFILE_ID]["executable"] == str(llama_bin),
                detail="safe keys only",
            )

            harness._write_compose_override(override_path, runtime_dir, token, 15.0)
            override_text = override_path.read_text(encoding="utf-8")
            sanitized = harness._sanitize_output(
                override_text
                + f"\nAuthorization: Bearer {token}"
                + f"\nhttp://127.0.0.1:18080/v1?token={token}"
                + f"\n{socket_path}\n{model_root}",
                token=token,
                socket_path=socket_path,
                model_root=model_root,
            )
            check(
                "redaction: temp Compose override token is redacted before logging",
                token not in sanitized
                and str(socket_path) not in sanitized
                and str(model_root) not in sanitized
                and "Authorization: Bearer" not in sanitized
                and "http://127.0.0.1" not in sanitized,
                detail="sanitized output redacted",
            )

            safe_payloads = [
                {
                    "ok": True,
                    "models": [
                        {
                            "id": "gguf_ok",
                            "filename": "model.gguf",
                            "relative_path": "family/model.gguf",
                            "root_id": "models",
                        }
                    ],
                },
                {"ok": True, "state": "running", "managed": True, "port": 18080, "log_tail": ["[redacted-path]"]},
            ]
            harness._assert_safe_payloads(
                safe_payloads,
                token=token,
                socket_path=socket_path,
                runtime_dir=runtime_dir,
                model_root=model_root,
                llama_bin=llama_bin,
            )
            leak_detected = False
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    harness._assert_safe_payloads(
                        [{"log_tail": [f"argv=['{llama_bin}', '--model', '{model_root / 'model.gguf'}'] {token}"]}],
                        token=token,
                        socket_path=socket_path,
                        runtime_dir=runtime_dir,
                        model_root=model_root,
                        llama_bin=llama_bin,
                    )
            except harness.ValidationError:
                leak_detected = True
            harness.results.clear()
            check("redaction: helper detects token/path/raw argv leaks", leak_detected)

        repo = Path(__file__).resolve().parents[1]
        source = (repo / "test_scripts" / "validate_lmm_real_profile_e2e.py").read_text(encoding="utf-8")
        docker_compose = (repo / "docker-compose.yml").read_text(encoding="utf-8")
        check(
            "scope: no committed Docker Compose writes",
            "COMPOSE_FILE.write" not in source
            and "docker-compose.yml" in source
            and "lmm_real_profile_e2e" not in docker_compose,
        )
        check(
            "scope: no Provider Settings writes",
            "provider_settings_store" not in source
            and "update_provider_settings" not in source
            and "/api/provider-settings" not in source,
        )
        check(
            "scope: no Ask changes",
            "/api/ask" not in source and "ask_sessions" not in source and "ask_context" not in source,
        )

    finally:
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
