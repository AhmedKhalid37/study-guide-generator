# Local Model Manager Operator Setup

Linux is the supported setup path for the current host companion. Windows,
macOS, Ollama, simple-local-model packaging, host-gateway TCP, Docker socket
control, privileged containers, and host PID namespace are deferred.

This guide covers configuring the host companion, approved model roots, safe
real `llama-server` profiles, optional `.ini` preset import, and the Docker
Unix-socket bridge. The app does not suggest hardware settings yet; profile
defaults are operator-owned and whitelist-validated.

For repeatable companion startup, systemd user-service examples, token rotation
notes, and temporary Docker override templates, see
`docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md`.

The web app does not implement a true browser folder picker for host GGUF
folders. Approved folders currently come from the host companion config
(`approved_roots`). Configure that file, restart the companion, then use Scan in
Local Models.

## 1. Find llama-server

If `llama-server` is on `PATH`:

```bash
command -v llama-server
```

If a server is already running and you need the exact executable:

```bash
readlink -f /proc/<pid>/exe
```

Use the resolved executable path in companion JSON. Do not put executable paths
in `.ini` preset files.

## 2. Choose Approved Model Roots

Pick one or more directories that contain GGUF files. Keep the root narrow, for
example a dedicated model directory rather than a whole home directory.

Rules enforced by the companion:

- only explicitly configured roots are scanned;
- only `.gguf` candidates are returned;
- symlinks must resolve inside an approved root;
- frontend/backend requests use model ids, not absolute host model paths;
- no whole-PC scan and no implicit `~/models` scan.

## 3. Example Companion Config

Example JSON:

```json
{
  "approved_roots": [
    { "id": "models", "path": "/mnt/ai/llm-models", "recursive": true }
  ],
  "token": "REPLACE_WITH_LONG_RANDOM_TOKEN",
  "process_runtime_dir": "/run/user/1000/main-app-lmm",
  "profiles": {
    "cpu_safe": {
      "type": "llama_server",
      "display_name": "CPU safe",
      "description": "Slow but reliable CPU launch.",
      "executable": "/usr/bin/llama-server",
      "host": "0.0.0.0",
      "default_parameters": {
        "port": 18080,
        "ctx_size": 4096,
        "gpu_layers": 0,
        "threads": 8,
        "parallel": 1,
        "flash_attention": false,
        "mmap": true
      },
      "warnings": ["CPU mode is slower but safer."]
    },
    "gpu_low_memory": {
      "type": "llama_server",
      "display_name": "GPU low memory",
      "description": "Small partial offload profile.",
      "executable": "/usr/bin/llama-server",
      "host": "0.0.0.0",
      "default_parameters": {
        "port": 18081,
        "ctx_size": 2048,
        "gpu_layers": 8,
        "threads": 8,
        "parallel": 1,
        "flash_attention": true,
        "mmap": true
      }
    },
    "gpu_balanced": {
      "type": "llama_server",
      "display_name": "GPU balanced",
      "description": "Partial offload profile for larger models.",
      "executable": "/usr/bin/llama-server",
      "host": "0.0.0.0",
      "default_parameters": {
        "port": 18082,
        "ctx_size": 4096,
        "gpu_layers": 20,
        "threads": 8,
        "parallel": 1,
        "cache_type_k": "q8_0",
        "flash_attention": true,
        "mmap": true
      },
      "parameter_schema": {
        "cache_type_k": { "allowed_values": ["f16", "q8_0"] },
        "flash_attention": {},
        "mmap": {}
      }
    }
  }
}
```

Notes:

- The token is server-side only. Do not commit it.
- The executable stays in companion JSON.
- `gpu_layers=999` is not a safe general default. Phase 2G5 proved it can fail
  safely as `model_may_be_too_large` / CUDA OOM on a large model.
- These defaults are examples, not app-generated recommendations.
- The Local Models setup screen may show a compact edit-me template with
  `/mnt/ai/llm-models` and `/tmp/lmm-companion-runtime` placeholders. Replace
  them with your own host paths; the UI does not write this config.

Start the companion from the repo root:

```bash
python -m tools.local_model_companion.companion --config /path/to/companion.json serve --socket /run/user/1000/main-app-lmm/companion.sock
```

## 4. Docker Unix Socket Bridge

Unix socket transport is the implemented Linux Docker path. The companion
listens on a host-owned socket file; the Docker backend receives a mounted view
of that socket or runtime directory and authenticates with the token.

Temporary override concept:

```yaml
services:
  app:
    volumes:
      - /run/user/1000/main-app-lmm:/run/user/1000/main-app-lmm
    environment:
      LMM_COMPANION_SOCKET: /run/user/1000/main-app-lmm/companion.sock
      LMM_COMPANION_TOKEN: REPLACE_WITH_LONG_RANDOM_TOKEN
      LMM_COMPANION_TIMEOUT_SECONDS: "3"
```

Do not paste a full Compose file from this example. Do not commit tokens,
operator-specific paths, temporary overrides, or generated config files.

Environment variables used by the Docker backend bridge:

- `LMM_COMPANION_SOCKET`
- `LMM_COMPANION_TOKEN`
- `LMM_COMPANION_TIMEOUT_SECONDS`

The frontend never receives these values.

## 5. Optional INI Presets

`.ini` preset import is implemented for profile defaults only. The preset file
path is supplied by companion JSON, never by the frontend:

```json
{
  "approved_roots": [
    { "id": "models", "path": "/mnt/ai/llm-models", "recursive": true }
  ],
  "token": "REPLACE_WITH_LONG_RANDOM_TOKEN",
  "process_runtime_dir": "/run/user/1000/main-app-lmm",
  "llama_server_executable": "/usr/bin/llama-server",
  "profile_preset_files": ["/path/to/lmm-profiles.ini"]
}
```

Example `.ini`:

```ini
[cpu_safe]
display_name = CPU safe
description = Slow but reliable CPU launch.
type = llama_server
port = 18080
ctx_size = 4096
gpu_layers = 0
threads = 8
parallel = 1
flash_attention = false
mmap = true

[gpu_balanced_16gb]
display_name = GPU balanced 16GB
description = Partial offload profile for large models.
type = llama_server
port = 18081
ctx_size = 4096
gpu_layers = 20
threads = 8
parallel = 1
flash_attention = true
mmap = true
```

Accepted preset keys:

- display fields: `display_name`, `description`, `type`;
- integer defaults: `port`, `ctx_size`, `gpu_layers`, `threads`, `parallel`;
- enum defaults: `cache_type_k`, `cache_type_v`;
- boolean defaults: `flash_attention`, `mmap`.

Rejected by design:

- unknown keys;
- `command`, `args`, `shell`, `model_path`, `executable`, free-form flags;
- invalid int/bool/enum values;
- values containing environment expansion or shell fragments;
- absolute model paths or executable paths in the preset file.

Imported profiles use the same safe metadata and typed parameter schema as JSON
profiles. They do not write Provider Settings and do not affect Ask.

## 6. Real Validation Harness

Direct companion lifecycle harness:

```bash
python test_scripts/validate_lmm_real_llama_server.py
```

Required env:

- `LMM_REAL_LLAMA_SERVER_BIN`
- `LMM_REAL_MODEL_ROOT`
- one of `LMM_REAL_MODEL_ID`, `LMM_REAL_MODEL_PATTERN`, or
  `LMM_REAL_MODEL_FILENAME`

Optional env:

- `LMM_REAL_PORT`
- `LMM_REAL_CTX_SIZE`
- `LMM_REAL_GPU_LAYERS`
- `LMM_REAL_THREADS`
- `LMM_REAL_READINESS_TIMEOUT`

CPU proof example:

```bash
LMM_REAL_LLAMA_SERVER_BIN=/usr/bin/llama-server \
LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models \
LMM_REAL_MODEL_PATTERN=gemma-4-26B-A4B-it-UD-Q4_K_M.gguf \
LMM_REAL_PORT=18080 \
LMM_REAL_CTX_SIZE=4096 \
LMM_REAL_GPU_LAYERS=0 \
LMM_REAL_THREADS=8 \
python test_scripts/validate_lmm_real_llama_server.py
```

Phase 2G5 CPU validation passed: the harness launched real `llama-server`,
reached `/v1/models`, stopped cleanly, and verified cleanup. A full offload
stress run with `gpu_layers=999` on a large model failed safely as
`model_may_be_too_large` / CUDA OOM; that is expected to happen on some
hardware/model combinations and is not a passed high-offload validation.

Configured-profile E2E harness:

```bash
python test_scripts/validate_lmm_real_profile_e2e.py
```

Required env:

- `LMM_REAL_LLAMA_SERVER_BIN`
- `LMM_REAL_MODEL_ROOT`
- one of `LMM_REAL_MODEL_ID` or `LMM_REAL_MODEL_PATTERN`
- `LMM_REAL_PORT`
- `LMM_REAL_CTX_SIZE`
- `LMM_REAL_GPU_LAYERS`
- `LMM_REAL_THREADS`

Optional env:

- `LMM_REAL_PARALLEL`
- `LMM_REAL_CACHE_TYPE_K`
- `LMM_REAL_CACHE_TYPE_V`
- `LMM_REAL_FLASH_ATTENTION`
- `LMM_REAL_MMAP`
- `LMM_REAL_READINESS_TIMEOUT`
- `LMM_REAL_BACKEND_TIMEOUT`

CPU-safe E2E proof example:

```bash
LMM_REAL_LLAMA_SERVER_BIN=/usr/bin/llama-server \
LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models \
LMM_REAL_MODEL_PATTERN=gemma-4-26B-A4B-it-UD-Q4_K_M.gguf \
LMM_REAL_PORT=18080 \
LMM_REAL_CTX_SIZE=4096 \
LMM_REAL_GPU_LAYERS=0 \
LMM_REAL_THREADS=8 \
python test_scripts/validate_lmm_real_profile_e2e.py
```

Phase 2G8 configured-profile E2E validation passed with those values. The
harness proved the actual companion -> Docker backend -> Local Models backend
flow: scan, safe profile metadata, selected model handoff, managed start,
readiness via `/v1/models`, managed stop, and port release. It uses only a
temporary Compose override and restores Docker with committed Compose only. It
does not write Provider Settings and skips `/api/local-model/status` rather than
repointing the local provider. It also verifies no token, socket path, absolute
model root or executable path, Authorization header, full URL, or raw argv leaks
through backend responses, and that returned model paths are root-relative only.

## 7. Local Models Setup UX

When the companion is unconfigured, the Local Models page explains:

- approved GGUF folders are configured in the host companion config;
- the web app cannot safely browse the whole PC or pick host folders directly;
- configure `approved_roots`, restart the companion, then click Scan;
- manual server mode still works without the companion.

The manual command helper defaults are safe examples:

```bash
llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 4096 -ngl 0 --threads 8
llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 4096 -ngl 20 --threads 8
llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 2048 -ngl 0 --threads 8
```

Full offload `-ngl 999` may appear only as an advanced risky option and is not
the default. If the page shows one saved selected model while the companion is
unconfigured, that model may be a saved selection from a previous validation or
session, not the current scanned library. Configure the companion and scan to
show all GGUF models.

## 8. Troubleshooting

`companion_config` / unconfigured:
Set `LMM_COMPANION_SOCKET` and `LMM_COMPANION_TOKEN` for the Docker backend, and
start the host companion with matching token/config.

Auth failed:
The backend token and companion token do not match. Rotate both values together.
Do not expose the token in frontend code or committed files.

Socket missing/offline:
Confirm the companion is running and the socket path exists on the host and in
the mounted container path. Check socket permissions for the backend container
user/group.

Model root empty:
Confirm the approved root path is correct, contains `.gguf` files, and recursive
scan is enabled if models live under subdirectories.

Port in use:
Choose another profile port or stop the process already listening on that port.
A manually started server can occupy the port before the companion starts.

Manually started server already using port:
The companion will not adopt or stop manual processes. Stop it manually or use a
different port.

Model may be too large / CUDA OOM:
Lower `gpu_layers`, context size, or parallel slots; choose a smaller/less
memory-hungry model; or use the CPU safe profile. The app does not generate a
hardware recommendation yet.

Readiness timeout:
The process spawned but `/v1/models` did not become ready before the timeout.
Review the companion log tail, increase `readiness_timeout_seconds` in JSON if
the model loads slowly, or use safer defaults.

Executable missing / permission denied:
Re-check `command -v llama-server`, `readlink -f /proc/<pid>/exe`, and execute
permissions. The executable path belongs in companion JSON, not preset files.

## 9. Scope

Current scope:

- Linux-first host companion setup.
- Unix socket companion control.
- Approved GGUF roots.
- JSON profiles and optional safe `.ini` profile-default import.
- Whitelist-based typed defaults and typed UI controls.

Deferred:

- app-suggested settings or AI-generated recommendations;
- Provider Settings writes from LMM;
- Ask behavior changes;
- permanent Docker Compose changes;
- model downloads;
- browser folder picker / host approve-root flow;
- host-gateway TCP;
- Docker socket, privileged container, or host PID namespace;
- Windows/macOS implementation;
- Ollama/simple-local-model path.
