"""Backend tests for the Local Model command-helper profiles (LMM Slice 4).

Proves that `get_local_model_command_profiles`:
  * returns ok:true with a default `profile` + a `profiles` list, each carrying a
    label, a display `command` string, and an `argv` list;
  * the command uses the PLACEHOLDER model path (/path/to/model.gguf) — never a real
    host path — and includes --host 0.0.0.0 and --port 8080 (Docker reachability);
  * carries safety warnings (edit the path, run on host, app never runs it);
  * NEVER contains a raw API key, even with a stored/env local key set;
  * NEVER contains userinfo / a full secret base URL (host-only at most);
  * performs NO writes (provider_settings.json / secrets.json unchanged, no jobs);
  * spawns NO process — by source inspection (no subprocess/os.system/Popen) AND by
    a hard monkeypatch that fails the test if subprocess.Popen is ever called;
  * the existing detection-only status response is unchanged by this slice.

Store/unit level — no running server, no network (the command helper does no I/O
beyond reading the resolved base URL host). Settings JSON files are redirected to a
temp dir and provider env is controlled so resolution is deterministic.

    python test_scripts/test_local_model_command_profile.py
"""
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import provider_config, provider_settings_store  # noqa: E402

FAKE_LOCAL_KEY = "sk-local-DEADBEEF000011112222secretZZ"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _point_store_at(tmp: Path):
    provider_settings_store.CONFIG_DIR = tmp
    provider_settings_store.SETTINGS_JSON = tmp / "provider_settings.json"
    provider_settings_store.SECRETS_JSON = tmp / "secrets.json"


def _clear_provider_env():
    for var in (
        "DEEPSEEK_API_KEY", "LLM_API_KEY", "DEEPSEEK_MODEL", "LLM_MODEL",
        "DEEPSEEK_MODEL_FLASH", "DEEPSEEK_BASE_URL", "LLM_BASE_URL",
        "DASHSCOPE_API_KEY", "QWEN_API_KEY", "QWEN_MODEL", "DASHSCOPE_BASE_URL",
        "QWEN_BASE_URL", "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL",
        "LOCAL_LLM_API_KEY", "LLM_TEMPERATURE",
    ):
        os.environ.pop(var, None)


def run():
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="lmm_cmd_"))
    _point_store_at(tmp)
    provider_config.load_env_file = lambda: None
    _clear_provider_env()

    # Hard guarantee: if anything in this slice ever tries to spawn a process, fail.
    def _boom(*a, **k):  # noqa: ANN001
        raise AssertionError("command helper must never spawn a process")

    real_popen = subprocess.Popen
    subprocess.Popen = _boom

    # ── 1. Shape: ok + default profile + profiles list ─────────────────────────
    res = provider_config.get_local_model_command_profiles()
    check(
        "shape: ok:true, provider:local, has profile + non-empty profiles list",
        res["ok"] is True
        and res["provider"] == "local"
        and isinstance(res["profile"], dict)
        and isinstance(res["profiles"], list)
        and len(res["profiles"]) >= 1,
        detail=str(list(res.keys())),
    )

    prof = res["profile"]
    check(
        "default profile: has id, label, command (str), argv (list)",
        isinstance(prof.get("id"), str) and prof["id"]
        and isinstance(prof.get("label"), str) and prof["label"]
        and isinstance(prof.get("command"), str) and prof["command"]
        and isinstance(prof.get("argv"), list) and prof["argv"],
        detail=str(prof),
    )

    # ── 2. Placeholder model path, host/port present, no real path ─────────────
    check(
        "command: uses placeholder model path /path/to/model.gguf",
        "/path/to/model.gguf" in prof["command"]
        and prof.get("placeholders", {}).get("model_path") == "/path/to/model.gguf",
        detail=prof["command"],
    )
    check(
        "command: includes --host 0.0.0.0 and --port 8080 (Docker reachability)",
        "--host 0.0.0.0" in prof["command"] and "--port 8080" in prof["command"],
        detail=prof["command"],
    )
    check(
        "command: starts with the llama-server binary",
        prof["argv"][0] == "llama-server" and prof["command"].startswith("llama-server "),
        detail=prof["command"],
    )

    # ── 3. Warnings present and safe-by-intent ─────────────────────────────────
    warnings_blob = " ".join(prof.get("warnings", [])).lower()
    check(
        "warnings: edit-path + run-on-host + app-never-runs guidance present",
        len(prof.get("warnings", [])) >= 2
        and "model path" in warnings_blob
        and "host machine" in warnings_blob
        and "never runs" in warnings_blob,
        detail=str(prof.get("warnings")),
    )

    # ── 4/5. No raw key + no userinfo/full URL even with secrets configured ─────
    # Use a DISTINCTIVE host so we can tell a leak of the user's configured URL from
    # the static docker example note (which legitimately mentions host.docker.internal).
    os.environ["LOCAL_LLM_BASE_URL"] = "http://user:topsecret@10.11.12.13:9999/v1?token=abc"
    provider_config.update_provider_settings("local", {"api_key": FAKE_LOCAL_KEY})
    res_secret = provider_config.get_local_model_command_profiles()
    blob = json.dumps(res_secret)
    check(
        "no-key-leak: stored local key absent from command-profile response",
        FAKE_LOCAL_KEY not in blob,
        detail="(redacted)",
    )
    check(
        "no-url-leak: no userinfo password, no query token, no user host:port",
        "topsecret" not in blob
        and "?token=" not in blob
        and "10.11.12.13:9999" not in blob,
        detail="(blob withheld)",
    )
    check(
        "host-only: base_url_host is the bare user host (no port/path/userinfo)",
        res_secret.get("base_url_host") == "10.11.12.13",
        detail=str(res_secret.get("base_url_host")),
    )

    # ── 6. No writes — settings/secrets unchanged by reading profiles ──────────
    def _snapshot(path: Path) -> bytes:
        return path.read_bytes() if path.exists() else b""

    settings_before = _snapshot(provider_settings_store.SETTINGS_JSON)
    secrets_before = _snapshot(provider_settings_store.SECRETS_JSON)
    provider_config.get_local_model_command_profiles()
    provider_config.get_local_model_command_profiles()
    check(
        "no-write: provider_settings.json unchanged by reading profiles",
        settings_before == _snapshot(provider_settings_store.SETTINGS_JSON),
    )
    check(
        "no-write: secrets.json unchanged by reading profiles",
        secrets_before == _snapshot(provider_settings_store.SECRETS_JSON),
    )

    # ── 7. No process spawn — source inspection (defensive, static) ────────────
    src = "\n".join(
        inspect.getsource(fn)
        for fn in (
            provider_config.get_local_model_command_profiles,
            provider_config._render_command_profile,
        )
    )
    # Check for actual CALL patterns (a trailing "." / "(") so prose in docstrings
    # that merely mentions "subprocess" doesn't trip the assertion.
    check(
        "no-spawn: command-helper source makes no subprocess/os.system/Popen call",
        "subprocess." not in src
        and "Popen(" not in src
        and "os.system(" not in src
        and "os.exec" not in src
        and "shell=True" not in src,
    )

    # ── 8. Existing detection-only status response is unchanged ────────────────
    os.environ.pop("LOCAL_LLM_BASE_URL", None)
    status = provider_config.get_local_model_status()
    check(
        "status-untouched: detection status still returns the Slice-2 shape",
        status["ok"] is True
        and "reachable" in status
        and "actions" in status,
        detail=str(list(status.keys())),
    )

    subprocess.Popen = real_popen  # restore

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
