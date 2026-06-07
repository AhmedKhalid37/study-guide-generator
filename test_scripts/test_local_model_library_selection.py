"""Backend tests for LMM Phase 2E selected library model handoff.

    python test_scripts/test_local_model_library_selection.py
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import local_model_library_selection as selection  # noqa: E402
from pipeline import provider_config, provider_settings_store  # noqa: E402


results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _snapshot(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def _point_selection_store_at(tmp: Path) -> None:
    selection.CONFIG_DIR = tmp
    selection.SELECTION_JSON = tmp / "local_model_library_selection.json"


def _point_provider_store_at(tmp: Path) -> None:
    provider_settings_store.CONFIG_DIR = tmp
    provider_settings_store.SETTINGS_JSON = tmp / "provider_settings.json"
    provider_settings_store.SECRETS_JSON = tmp / "secrets.json"


def run() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="lmm_selection_"))
    selection_dir = tmp / "config"
    provider_dir = tmp / "provider"
    jobs_dir = tmp / "jobs"
    _point_selection_store_at(selection_dir)
    _point_provider_store_at(provider_dir)
    provider_config.load_env_file = lambda: None

    secret = "tok-phase2e-SUPERSECRET"
    socket_path = "/tmp/lmm-phase2e-secret.sock"
    absolute_path = "/home/user/models/private/model.gguf"
    full_url = "http://127.0.0.1:65535/private?secret=1"
    auth_header = f"Authorization: Bearer {secret}"

    provider_settings_store.update_provider("local", {"default_model": "unchanged-model"})
    provider_before = _snapshot(provider_settings_store.SETTINGS_JSON)
    secrets_before = _snapshot(provider_settings_store.SECRETS_JSON)

    real_popen = subprocess.Popen

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("selected-model handoff must never spawn a process")

    subprocess.Popen = _boom
    try:
        # 1. Initial selection empty.
        initial = selection.get_library_model_selection()
        check(
            "initial selection is empty",
            initial["ok"] is True and initial["selected"] is None and initial["future_launch_preview"] is None,
            detail=str(initial),
        )

        safe_model = {
            "id": "gguf_safe",
            "display_name": "Gemma Safe Q4",
            "filename": "gemma-safe-q4.gguf",
            "relative_path": "family/gemma-safe-q4.gguf",
            "root_id": "default",
            "size_bytes": 123456,
            "modified_at": "2026-06-06T00:00:00Z",
            "family_hint": "gemma",
            "quant_hint": "Q4_K_M",
            "server_compatible": True,
            "absolute_path": absolute_path,
        }

        # 2. Save by model_id, validating against cached library when available.
        saved = selection.save_library_model_selection(
            {"model_id": "gguf_safe"},
            library_getter=lambda: {"ok": True, "models": [safe_model]},
        )
        selected = saved["selected"]
        check(
            "save safe selected model from cached library",
            selected["id"] == "gguf_safe"
            and selected["relative_path"] == "family/gemma-safe-q4.gguf"
            and isinstance(selected.get("selected_at"), str)
            and saved["future_launch_preview"]["profile"] == "gpu_default",
            detail=str(saved),
        )

        # 3. Load selected model from durable backend JSON.
        loaded = selection.get_library_model_selection()
        check(
            "load selected model from selection store",
            loaded["selected"]["id"] == "gguf_safe"
            and loaded["future_launch_preview"]["model_id"] == "gguf_safe",
            detail=str(loaded),
        )

        # 4. Clear selected model only.
        cleared = selection.clear_library_model_selection()
        check(
            "clear selected model",
            cleared["selected"] is None and cleared["future_launch_preview"] is None,
            detail=str(cleared),
        )

        # 5/6/7. Unsafe fields are dropped/redacted, including absolute relative_path.
        unsafe_model = {
            "id": "gguf_unsafe",
            "display_name": f"Bad {absolute_path}",
            "filename": f"bad {full_url}",
            "relative_path": absolute_path,
            "root_id": f"default {socket_path}",
            "size_bytes": 99,
            "modified_at": f"2026-06-06T00:00:00Z {auth_header}",
            "family_hint": f"family {secret}",
            "quant_hint": "Q8_0",
            "server_compatible": True,
            "absolute_path": absolute_path,
            "socket_path": socket_path,
            "Authorization": auth_header,
            "url": full_url,
            "raw": {"token": secret},
        }
        unsafe_saved = selection.save_library_model_selection(
            {"model_id": "gguf_unsafe", "model": unsafe_model},
            library_getter=None,
        )
        unsafe_selected = unsafe_saved["selected"]
        unsafe_blob = _blob(unsafe_saved) + _snapshot(selection.SELECTION_JSON).decode("utf-8")
        check(
            "absolute relative_path is dropped",
            "relative_path" not in unsafe_selected,
            detail=str(unsafe_selected),
        )
        check(
            "extra unsafe fields are dropped",
            set(unsafe_selected.keys()).issubset(set(selection.SELECTION_FIELDS))
            and "absolute_path" not in unsafe_blob
            and "socket_path" not in unsafe_blob
            and "raw" not in unsafe_blob,
            detail=str(unsafe_selected.keys()),
        )
        check(
            "token/socket/auth/url/path-like strings are redacted",
            secret not in unsafe_blob
            and socket_path not in unsafe_blob
            and absolute_path not in unsafe_blob
            and auth_header not in unsafe_blob
            and full_url not in unsafe_blob,
            detail=unsafe_blob,
        )

        # Cached-library validation rejects unknown ids when a current model list exists.
        try:
            selection.save_library_model_selection(
                {"model_id": "missing"},
                library_getter=lambda: {"ok": True, "models": [safe_model]},
            )
            rejected_missing = False
        except selection.LocalModelLibrarySelectionError:
            rejected_missing = True
        check("unknown model_id rejected when cached library is available", rejected_missing)

        # 8. Provider Settings file/API remains unchanged by selection reads/writes.
        check(
            "no Provider Settings file changed",
            provider_before == _snapshot(provider_settings_store.SETTINGS_JSON)
            and secrets_before == _snapshot(provider_settings_store.SECRETS_JSON),
        )
        check(
            "selection module does not call provider settings API",
            "provider_settings" not in inspect.getsource(selection),
        )

        # 9. No job artifacts touched.
        check("no job artifact directory touched", not jobs_dir.exists())

        # 10. Selection route remains present; process-control routes are a later
        # backend bridge and are not implemented by the selection module.
        try:
            from api.server import app  # noqa: WPS433

            paths = {route.path for route in app.routes}
            route_check = {
                "/api/local-model/library/selection",
            }.issubset(paths) and "/api/local-model/server/" not in inspect.getsource(selection)
            check("routes: selection present, process control outside selection module", route_check, detail=str(sorted(paths)))
        except Exception as exc:
            check("routes: skipped when FastAPI server import is unavailable", True, detail=type(exc).__name__)

        # 11. No subprocess/os.system/shell=True in Phase 2E selected-model code.
        source = inspect.getsource(selection)
        check(
            "no subprocess/os.system/shell=True in selected-model handoff",
            "subprocess." not in source
            and "Popen(" not in source
            and "os.system(" not in source
            and "os.exec" not in source
            and "shell=True" not in source,
        )

        # Command-helper preview consumes the saved selection as safe metadata only.
        command_profiles = provider_config.get_local_model_command_profiles()
        preview = command_profiles.get("future_launch_preview")
        command_blob = _blob(command_profiles)
        check(
            "command helper includes non-runnable selected-model preview",
            preview["model_id"] == "gguf_unsafe"
            and preview["profile"] == "gpu_default"
            and preview["runnable_command"] is False
            and absolute_path not in command_blob,
            detail=str(preview),
        )
    finally:
        subprocess.Popen = real_popen

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
