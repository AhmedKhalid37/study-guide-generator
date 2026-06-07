#!/usr/bin/env python3
"""Final offline hardening checks for LMM Phase 2G11.

This is intentionally static/pure except for temporary files used to exercise the
companion preset loader. It does not require Docker, a companion token, or a real
GGUF model.
"""

from __future__ import annotations

import configparser
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import provider_config  # noqa: E402
from pipeline.local_model_companion_client import (  # noqa: E402
    CompanionBridgeConfig,
    _profiles_from_payload,
    _server_status_from_payload,
)
from pipeline.local_model_library_selection import _sanitize_selection  # noqa: E402
from tools.local_model_companion.config import ConfigError, load_config  # noqa: E402


CHECKS = 0
FAILURES: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"PASS {name}")
    else:
        suffix = f" - {detail}" if detail else ""
        print(f"FAIL {name}{suffix}")
        FAILURES.append(name)


def as_jsonable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def assert_no_secret_leaks(name: str, payload: Any) -> None:
    text = as_jsonable(payload)
    forbidden = [
        "replace-with-real-token",
        "tok-secret-final-hardening",
        "Authorization",
        "Bearer ",
        "/tmp/lmm-final-hardening/companion.sock",
        "/mnt/ai/llm-models/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
        "/usr/bin/llama-server",
        "http://127.0.0.1:18080/v1/models",
        "argv=['",
        "\"argv\"",
        "--secret-flag",
        "model_path",
        "executable_path",
    ]
    check(name, not any(item in text for item in forbidden), text[:500])


def test_examples_exist_and_parse() -> None:
    expected = {
        "docs/examples/lmm-companion.config.example.json",
        "docs/examples/lmm-companion.profiles.example.ini",
        "docs/examples/lmm-companion.user.service.example",
        "docs/examples/docker-compose.lmm-companion.override.example.yml",
    }
    present = {str(path.relative_to(ROOT)) for path in (ROOT / "docs/examples").glob("*")}
    check("runtime-service example file set", expected <= present, str(sorted(present)))

    config = json.loads(read("docs/examples/lmm-companion.config.example.json"))
    check("example companion JSON parses as object", isinstance(config, dict))
    check("example config uses placeholder token", config.get("token") == "replace-with-local-token")
    check("example config root is the documented placeholder root", config["approved_roots"][0]["path"] == "/mnt/ai/llm-models")
    check("example config keeps executable in JSON", config.get("llama_server_executable") == "/usr/bin/llama-server")

    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(read("docs/examples/lmm-companion.profiles.example.ini"))
    sections = set(parser.sections())
    check("example INI parses", {"cpu_safe", "gpu_balanced_16gb", "low_memory"} <= sections)
    risky_sections = [
        section
        for section in parser.sections()
        if parser.get(section, "gpu_layers", fallback="").strip() == "999"
    ]
    check("gpu_layers 999 appears only in risky preset", risky_sections == ["full_offload_risky"], str(risky_sections))
    risky_text = "\n".join(dict(parser.items("full_offload_risky", raw=True)).values()).lower()
    check("risky preset explicitly warns about OOM", "risky" in risky_text and "oom" in risky_text)


def test_ini_example_through_loader_and_rejections() -> None:
    with tempfile.TemporaryDirectory(prefix="lmm-phase2g11-") as tmp:
        tmpdir = Path(tmp)
        preset = tmpdir / "profiles.ini"
        preset.write_text(read("docs/examples/lmm-companion.profiles.example.ini"), encoding="utf-8")
        model_root = tmpdir / "models"
        model_root.mkdir()
        config_path = tmpdir / "companion.json"
        config_path.write_text(
            json.dumps(
                {
                    "approved_roots": [{"id": "models", "path": str(model_root), "recursive": True}],
                    "token": "replace-with-local-token",
                    "process_runtime_dir": str(tmpdir / "runtime"),
                    "llama_server_executable": sys.executable,
                    "profile_preset_files": [str(preset)],
                }
            ),
            encoding="utf-8",
        )
        loaded = load_config(config_path)
        profile_ids = {profile.id for profile in loaded.profiles}
        check("example INI imports through companion loader", {"cpu_safe", "gpu_balanced_16gb", "low_memory", "full_offload_risky"} <= profile_ids)
        defaults = {profile.id: profile.default_parameters or {} for profile in loaded.profiles}
        check("imported safe defaults are CPU/balanced/low-memory", defaults["cpu_safe"]["gpu_layers"] == 0 and defaults["gpu_balanced_16gb"]["gpu_layers"] == 20 and defaults["low_memory"]["gpu_layers"] == 0)
        check("imported full offload remains isolated risky preset", defaults["full_offload_risky"]["gpu_layers"] == 999)

        rejected_keys = ["command", "args", "shell", "model_path", "executable", "--ngl"]
        for key in rejected_keys:
            bad_preset = tmpdir / f"bad-{key.replace('-', 'dash')}.ini"
            bad_preset.write_text(f"[bad]\ntype = llama_server\n{key} = unsafe\n", encoding="utf-8")
            bad_config = tmpdir / f"bad-{key.replace('-', 'dash')}.json"
            bad_config.write_text(
                json.dumps(
                    {
                        "approved_roots": [{"id": "models", "path": str(model_root), "recursive": True}],
                        "token": "replace-with-local-token",
                        "llama_server_executable": sys.executable,
                        "profile_preset_files": [str(bad_preset)],
                    }
                ),
                encoding="utf-8",
            )
            try:
                load_config(bad_config)
            except ConfigError:
                rejected = True
            else:
                rejected = False
            check(f"preset rejects free-form key {key}", rejected)


def test_runtime_templates_static_safety() -> None:
    compose = read("docs/examples/docker-compose.lmm-companion.override.example.yml")
    forbidden_compose = [
        "/var/run/docker.sock",
        "privileged:",
        "pid: host",
        "network_mode: host",
        "host-gateway",
        "extra_hosts",
    ]
    check("example Compose avoids unsafe host controls", not any(item in compose for item in forbidden_compose), compose)
    check("example Compose keeps token as env placeholder", "${LMM_COMPANION_TOKEN:?set in local shell or .env.local}" in compose)
    check("example Compose mounts only companion runtime concept", "/run/study-guide-generator/lmm-companion" in compose and "llm-models" not in compose)

    service = read("docs/examples/lmm-companion.user.service.example")
    check("systemd example uses placeholder user paths", "replace-with-user" in service and "/home/ahmed" not in service)
    check("systemd example does not embed token/env secret", "LMM_COMPANION_TOKEN" not in service and "Bearer" not in service)
    check("systemd example does not install or enable itself", "systemctl enable" not in service and "WantedBy=default.target" in service)
    check("systemd example starts only the companion module", " -m tools.local_model_companion.companion " in service)


def test_backend_dto_redaction() -> None:
    config = CompanionBridgeConfig(
        socket_path="/tmp/lmm-final-hardening/companion.sock",
        token="tok-secret-final-hardening",
        timeout_seconds=3,
    )
    status = _server_status_from_payload(
        config,
        {
            "ok": True,
            "state": "running",
            "managed": True,
            "pid": 12345,
            "model_id": "models/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
            "profile_id": "cpu_safe",
            "port": 18080,
            "params": {"gpu_layers": 0},
            "executable_path": "/usr/bin/llama-server",
            "argv": ["/usr/bin/llama-server", "-m", "/mnt/ai/llm-models/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf", "--secret-flag"],
            "url": "http://127.0.0.1:18080/v1/models?token=tok-secret-final-hardening",
            "log_tail": [
                "Authorization: Bearer tok-secret-final-hardening",
                "argv=['/usr/bin/llama-server','--secret-flag'] model /mnt/ai/llm-models/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
            ],
        },
    )
    check("server status DTO keeps safe key set", set(status) == {"ok", "configured", "reachable", "state", "managed", "model_id", "profile_id", "port", "started_at", "error", "log_tail"})
    assert_no_secret_leaks("server status DTO redacts token/socket/path/argv", status)

    profiles = _profiles_from_payload(
        config,
        {
            "ok": True,
            "profiles": [
                {
                    "id": "cpu_safe",
                    "display_name": "CPU safe /usr/bin/llama-server",
                    "description": "Authorization: Bearer tok-secret-final-hardening http://127.0.0.1:18080/v1/models",
                    "type": "llama_server",
                    "test_profile": False,
                    "runnable": True,
                    "runnable_reason": None,
                    "executable_path": "/usr/bin/llama-server",
                    "argv": ["--secret-flag"],
                    "default_parameters": {"gpu_layers": 0},
                    "parameters": {
                        "gpu_layers": {"type": "integer", "min": 0, "max": 999, "default": 0, "label": "GPU layers", "help": "High layers may OOM"},
                        "command": {"type": "enum", "allowed_values": ["bad"], "default": "bad"},
                    },
                    "warnings": ["uses /mnt/ai/llm-models and argv=['--secret-flag']"],
                }
            ],
            "warnings": ["socket /tmp/lmm-final-hardening/companion.sock"],
        },
    )
    check("profile DTO exposes only safe profile fields", set(profiles["profiles"][0]) == {"id", "display_name", "description", "type", "test_profile", "runnable", "runnable_reason", "default_parameters", "parameters", "warnings"})
    check("profile DTO drops unknown command parameter", "command" not in profiles["profiles"][0]["parameters"])
    assert_no_secret_leaks("profile DTO redacts token/socket/path/argv", profiles)


def test_manual_helper_defaults_and_999_scope() -> None:
    command_profiles = provider_config.get_local_model_command_profiles()["profiles"]
    by_id = {profile["id"]: profile for profile in command_profiles}
    check("manual helper default is CPU safe first", command_profiles[0]["id"] == "llama_server_cpu_safe")
    check("manual helper CPU safe uses gpu_layers 0", "-ngl 0" in by_id["llama_server_cpu_safe"]["command"])
    check("manual helper balanced uses partial offload", "-ngl 20" in by_id["llama_server_gpu_balanced"]["command"])
    check("manual helper low memory uses gpu_layers 0", "-ngl 0" in by_id["llama_server_low_memory"]["command"])
    non_risky = [profile for profile in command_profiles if "risky" not in profile["id"]]
    check("gpu_layers 999 is not in non-risky manual helpers", all("999" not in as_jsonable(profile) for profile in non_risky))
    risky = by_id["llama_server_full_offload_risky"]
    risky_text = as_jsonable(risky).lower()
    check("manual helper 999 is explicitly risky", "-ngl 999" in risky["command"] and "risky" in risky_text and ("oom" in risky_text or "out-of-memory" in risky_text))

    focused_files = [
        "pipeline/provider_config.py",
        "docs/CURRENT_TASK.md",
        "docs/NEXT_CHAT_HANDOFF.md",
        "docs/PROJECT_CONTEXT.md",
        "docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md",
        "docs/LOCAL_MODEL_MANAGER_OPERATOR_SETUP.md",
        "docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md",
        "docs/examples/lmm-companion.profiles.example.ini",
    ]
    allowed_context = re.compile(r"(risky|oom|failed safely|not (?:a |the )?default|stress|advanced|full offload|avoid|too aggressive|gpu_layers=999 remains)", re.IGNORECASE)
    bad_contexts: list[str] = []
    for rel in focused_files:
        lines = read(rel).splitlines()
        for index, line in enumerate(lines):
            if "gpu_layers=999" not in line and "gpu_layers = 999" not in line and "-ngl\", \"999\"" not in line and "-ngl 999" not in line:
                continue
            context = " ".join(lines[max(0, index - 8) : min(len(lines), index + 8)])
            if not allowed_context.search(context):
                bad_contexts.append(f"{rel}:{index + 1}: {context}")
    check("gpu_layers 999 mentions are risky or historical", not bad_contexts, "\n".join(bad_contexts[:5]))


def test_static_boundaries() -> None:
    server = read("api/server.py")
    start = server.index('@app.get("/api/local-model/status")')
    end = server.index("# Ask Your Guide")
    local_routes = server[start:end]
    provider_write_terms = [
        "save_provider_settings",
        "patch_provider",
        "ProviderSettingsPatch",
        "clear_provider_key",
        "test_provider_settings",
        "fetch_provider_models",
        "/api/provider-settings",
    ]
    check("local-model routes do not write Provider Settings", not any(term in local_routes for term in provider_write_terms))
    check("local-model routes do not call Ask APIs/helpers", "/api/ask" not in local_routes and "ask_sessions" not in local_routes and "ask_context" not in local_routes)

    lmm_sources = [
        "pipeline/local_model_companion_client.py",
        "pipeline/local_model_library_selection.py",
        "tools/local_model_companion/config.py",
        "tools/local_model_companion/companion.py",
        "tools/local_model_companion/profiles.py",
        "frontend/src/components/LocalModelsPanel.jsx",
        "frontend/src/localModelLibrary.js",
    ]
    check("LMM-focused sources do not import provider settings store", not any("provider_settings_store" in read(rel) for rel in lmm_sources))
    check("LMM frontend does not call Ask endpoints", not any("/api/ask" in read(rel) for rel in lmm_sources if rel.startswith("frontend/")))

    client = read("frontend/src/api/client.js")
    local_client = client[client.index("export function getLocalModelStatus") : client.index("export function getAskJobs")]
    unsafe_frontend_terms = ["http://", "https://", "Authorization", "Bearer", "LMM_COMPANION", "companion.sock", "unix-socket"]
    check("frontend local-model helpers go only through backend API", all('requestJson("/api/local-model/' in block for block in re.findall(r"export function \w+\([^)]*\) \{[\s\S]*?\n\}", local_client)))
    check("frontend local-model helpers do not expose companion connection details", not any(term in local_client for term in unsafe_frontend_terms))
    check("frontend scan sends no host root body", 'requestJson("/api/local-model/library/scan", { method: "POST" })' in local_client)

    panel = read("frontend/src/components/LocalModelsPanel.jsx")
    picker_terms = ["webkitdirectory", 'type="file"', "showDirectoryPicker", "choose folder", "folder picker"]
    check("Local Models has no browser folder picker", not any(term in panel for term in picker_terms))
    check("approved roots remain companion-config copy only", "Configure approved_roots in the companion config" in panel and "scan ? scanLocalModelLibrary : getLocalModelLibrary" in panel)

    compose = read("docker-compose.yml")
    permanent_terms = ["LMM_COMPANION_SOCKET", "LMM_COMPANION_TOKEN", "lmm-companion", "companion.sock"]
    check("production Compose has no permanent LMM companion mount/env", not any(term in compose for term in permanent_terms))

    selected = _sanitize_selection(
        {
            "id": "models:gemma.gguf",
            "display_name": "Gemma",
            "filename": "gemma.gguf",
            "relative_path": "/mnt/ai/llm-models/gemma.gguf",
            "root_id": "models",
            "model_path": "/mnt/ai/llm-models/gemma.gguf",
            "executable": "/usr/bin/llama-server",
            "token": "tok-secret-final-hardening",
            "argv": ["--bad"],
        },
        selected_at="2026-06-07T00:00:00Z",
    )
    check("selected model persistence drops absolute/unsafe fields", selected is not None and "relative_path" not in selected and not {"model_path", "executable", "token", "argv"} & set(selected))


def main() -> int:
    test_examples_exist_and_parse()
    test_ini_example_through_loader_and_rejections()
    test_runtime_templates_static_safety()
    test_backend_dto_redaction()
    test_manual_helper_defaults_and_999_scope()
    test_static_boundaries()

    if FAILURES:
        print(f"\n{len(FAILURES)} of {CHECKS} LMM Phase 2G11 final regression checks failed.")
        for failure in FAILURES:
            print(f" - {failure}")
        return 1
    print(f"\nAll {CHECKS} LMM Phase 2G11 final regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
