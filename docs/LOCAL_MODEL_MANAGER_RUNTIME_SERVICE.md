# Local Model Manager Runtime Service

This guide documents Linux-first operator packaging for running the host Local
Model Manager companion repeatably and connecting the Docker backend to it. It is
docs/templates only: no app installer, no production Compose change, and no
system service installed by the app.

Windows and macOS companion packaging remain deferred. Auto-control is optional;
manual `llama-server` mode still works without the companion.

## 1. Scope

Implemented deployment path:

- Linux host companion running outside Docker under the operator's user account.
- Unix-domain socket transport mounted into the Docker backend container.
- Server-side bearer token shared only between the companion and Docker backend.
- Operator-owned approved GGUF roots, for example `/mnt/ai/llm-models`.
- JSON companion config and optional safe `.ini` profile-default presets.

Out of scope:

- Windows/macOS service packaging.
- Permanent Docker Compose changes committed to the repo.
- App-installed system service or autostart code.
- Provider Settings writes, Ask changes, frontend UI changes, or production
  backend behavior changes.
- Host-gateway TCP, host networking, Docker socket, privileged containers, or
  host PID namespace.
- Model downloads, hardware recommendations, arbitrary flags, or free-form shell.

## 2. Files And Directories

Recommended operator-owned paths:

```text
Config:
  ~/.config/study-guide-generator/lmm-companion.json

Profile presets:
  ~/.config/study-guide-generator/lmm-companion.profiles.ini

Runtime/socket:
  ${XDG_RUNTIME_DIR}/study-guide-generator/lmm-companion.sock

Runtime/socket fallback when XDG_RUNTIME_DIR is unavailable:
  /tmp/study-guide-generator-$USER/lmm-companion.sock

Process runtime state:
  ${XDG_RUNTIME_DIR}/study-guide-generator/lmm-process
  fallback: /tmp/study-guide-generator-$USER/lmm-process

Logs:
  ~/.local/state/study-guide-generator/lmm-companion/

Model roots:
  /mnt/ai/llm-models
```

The socket path must be mounted into the Docker backend container, preferably by
mounting only the containing runtime directory. The Docker backend reads
`LMM_COMPANION_SOCKET` as the container-side socket path.

The token is server-side only. Put it in the companion config and Docker/backend
environment. Do not put it in frontend code, public docs, committed Compose
files, or command output you plan to share.

Model roots are read by the host companion. The Docker backend should not mount
or scan model roots; it calls the companion and receives safe model ids and
root-relative metadata.

## 3. Token Handling

Generate a local token on the host:

```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Alternative:

```bash
openssl rand -base64 32
```

Rules:

- Never commit the token.
- Store the real token only in the local companion config and local Docker
  backend environment such as `.env.local`.
- Keep committed examples as placeholders such as `replace-with-local-token`.
- Do not paste `docker compose config` output when it includes expanded secrets.

## 4. Companion Config

Use a local file such as
`~/.config/study-guide-generator/lmm-companion.json`. A safe template is also in
`docs/examples/lmm-companion.config.example.json`.

Preset-file based example:

```json
{
  "approved_roots": [
    { "id": "models", "path": "/mnt/ai/llm-models", "recursive": true }
  ],
  "token": "replace-with-local-token",
  "process_runtime_dir": "/tmp/study-guide-generator-replace-with-user/lmm-process",
  "llama_server_executable": "/usr/bin/llama-server",
  "profile_preset_files": [
    "~/.config/study-guide-generator/lmm-companion.profiles.ini"
  ]
}
```

Inline-profile option, if you do not use `profile_preset_files`:

```json
{
  "approved_roots": [
    { "id": "models", "path": "/mnt/ai/llm-models", "recursive": true }
  ],
  "token": "replace-with-local-token",
  "process_runtime_dir": "/tmp/study-guide-generator-replace-with-user/lmm-process",
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
      "warnings": ["CPU mode is slower but safer for large GGUF models."]
    },
    "gpu_balanced_16gb": {
      "type": "llama_server",
      "display_name": "GPU balanced 16GB",
      "description": "Partial GPU offload for larger models.",
      "executable": "/usr/bin/llama-server",
      "host": "0.0.0.0",
      "default_parameters": {
        "port": 18081,
        "ctx_size": 4096,
        "gpu_layers": 20,
        "threads": 8,
        "parallel": 1,
        "flash_attention": true,
        "mmap": true
      },
      "warnings": ["Reduce gpu_layers if startup reports CUDA OOM."]
    },
    "low_memory": {
      "type": "llama_server",
      "display_name": "Low memory",
      "description": "Lower context and no GPU offload.",
      "executable": "/usr/bin/llama-server",
      "host": "0.0.0.0",
      "default_parameters": {
        "port": 18082,
        "ctx_size": 2048,
        "gpu_layers": 0,
        "threads": 8,
        "parallel": 1,
        "flash_attention": false,
        "mmap": true
      }
    }
  }
}
```

Notes:

- Replace `/mnt/ai/llm-models`, `/usr/bin/llama-server`, and
  `replace-with-local-token` for your host.
- JSON config paths are expanded for `~`, but not for shell variables such as
  `$USER`; replace placeholder path segments explicitly.
- `gpu_layers=999` is intentionally not a default. It can be useful only as an
  advanced full-offload experiment and can fail with CUDA OOM on large models.
- Use either imported preset ids or inline profile ids. Do not define the same
  profile id in both places.
- If you use `profile_preset_files`, keep the executable path in JSON through
  `llama_server_executable`; preset files should not carry executable paths.
- The app does not write this config and does not suggest hardware settings.

## 5. Profile Preset INI

Optional `.ini` profile presets are profile defaults only. A safe template is in
`docs/examples/lmm-companion.profiles.example.ini`.

Example:

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
description = Partial GPU offload for larger models.
type = llama_server
port = 18081
ctx_size = 4096
gpu_layers = 20
threads = 8
parallel = 1
flash_attention = true
mmap = true

[low_memory]
display_name = Low memory
description = Lower context and no GPU offload.
type = llama_server
port = 18082
ctx_size = 2048
gpu_layers = 0
threads = 8
parallel = 1
flash_attention = false
mmap = true

[full_offload_risky]
display_name = Full offload risky
description = Advanced experiment only. Can OOM on large models.
type = llama_server
port = 18083
ctx_size = 4096
gpu_layers = 999
threads = 8
parallel = 1
flash_attention = true
mmap = true
```

Preset import rules:

- `.ini` imports only whitelisted typed defaults.
- No shell commands, arbitrary flags, environment expansion, or free-form args.
- No model paths.
- No executable paths in preset files; use companion JSON
  `llama_server_executable` for imported presets.
- Unknown keys, invalid types, duplicate ids, and unsafe command/path-like values
  are rejected.
- `full_offload_risky` is optional and not a default.

## 6. Run The Companion Manually

From the repo root:

```bash
if [ -n "${XDG_RUNTIME_DIR:-}" ]; then
  export LMM_COMPANION_RUNTIME_DIR="$XDG_RUNTIME_DIR/study-guide-generator"
else
  export LMM_COMPANION_RUNTIME_DIR="/tmp/study-guide-generator-$USER"
fi

mkdir -p "$LMM_COMPANION_RUNTIME_DIR"
export LMM_COMPANION_SOCKET="$LMM_COMPANION_RUNTIME_DIR/lmm-companion.sock"

python -m tools.local_model_companion.companion \
  --config ~/.config/study-guide-generator/lmm-companion.json \
  serve \
  --socket "$LMM_COMPANION_SOCKET"
```

Basic health does not require launching a model. If your `curl` supports Unix
sockets:

```bash
curl --unix-socket "$LMM_COMPANION_SOCKET" \
  -H "Authorization: Bearer $LMM_COMPANION_TOKEN" \
  http://localhost/health
```

Python health check:

```bash
python - <<'PY'
import http.client
import json
import os

class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__("localhost")
        self.socket_path = socket_path
    def connect(self):
        import socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)

socket_path = os.environ["LMM_COMPANION_SOCKET"]
token = os.environ["LMM_COMPANION_TOKEN"]
conn = UnixHTTPConnection(socket_path)
conn.request("GET", "/health", headers={"Authorization": f"Bearer {token}"})
print(conn.getresponse().read().decode("utf-8"))
PY
```

Useful checks:

- `GET /health` verifies auth and process availability.
- `GET /profiles` verifies configured profiles without launching a model.
- `POST /models/scan` verifies approved-root scanning.

Example scan with `curl`:

```bash
curl --unix-socket "$LMM_COMPANION_SOCKET" \
  -H "Authorization: Bearer $LMM_COMPANION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"recursive": true}' \
  http://localhost/models/scan
```

## 7. Docker Compose Temporary Override

Use a local override file only, for example
`docker-compose.lmm-companion.override.yml` copied from
`docs/examples/docker-compose.lmm-companion.override.example.yml`. Do not commit a
real override with tokens or operator-specific paths.

The override should:

- Mount only the runtime/socket directory, not the whole home directory.
- Set `LMM_COMPANION_SOCKET` to the container-side socket path.
- Set `LMM_COMPANION_TOKEN` from local environment or `.env.local`.
- Avoid Docker socket mounts, privileged mode, host PID namespace, and host
  networking.
- Avoid host-gateway TCP.

Minimal override shape:

```yaml
services:
  app:
    volumes:
      - ${LMM_COMPANION_RUNTIME_DIR:-/tmp/study-guide-generator-${USER}}:/run/study-guide-generator/lmm-companion:rw
    environment:
      LMM_COMPANION_SOCKET: /run/study-guide-generator/lmm-companion/lmm-companion.sock
      LMM_COMPANION_TOKEN: ${LMM_COMPANION_TOKEN:?set in local shell or .env.local}
      LMM_COMPANION_TIMEOUT_SECONDS: "3"
```

Start Docker with the local override only when you need companion integration:

```bash
docker compose -f docker-compose.yml -f docker-compose.lmm-companion.override.yml up
```

Do not paste full `docker compose config` output if it expands
`LMM_COMPANION_TOKEN`.

## 8. systemd User Service Example

Copy `docs/examples/lmm-companion.user.service.example` to:

```text
~/.config/systemd/user/study-guide-lmm-companion.service
```

Adjust `WorkingDirectory`, config path, and socket path for your checkout and
user id. The service runs as the user, not root, and uses no privileged
permissions.

Example commands:

```bash
systemctl --user daemon-reload
systemctl --user enable --now study-guide-lmm-companion.service
systemctl --user status study-guide-lmm-companion.service
journalctl --user -u study-guide-lmm-companion.service -f
```

Stop or disable:

```bash
systemctl --user stop study-guide-lmm-companion.service
systemctl --user disable study-guide-lmm-companion.service
```

The template uses `Restart=on-failure` with a delay. Avoid aggressive restart
loops while tuning real model profiles, because repeated launches can keep
failing on port conflicts or CUDA OOM.

## 9. End-To-End Validation

Live validation is optional and requires real host paths. No Docker run is
required for this docs slice, but operators can validate a configured runtime
with:

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

Required env:

- `LMM_REAL_LLAMA_SERVER_BIN`
- `LMM_REAL_MODEL_ROOT`
- `LMM_REAL_MODEL_PATTERN` or `LMM_REAL_MODEL_ID`
- `LMM_REAL_PORT`
- `LMM_REAL_CTX_SIZE`
- `LMM_REAL_GPU_LAYERS`
- `LMM_REAL_THREADS`

Known-good CPU-safe proof from Phase 2G8:

- `/usr/bin/llama-server`
- `/mnt/ai/llm-models`
- `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`
- `port=18080`
- `ctx_size=4096`
- `gpu_layers=0`
- `threads=8`

That run reached `/v1/models`, reported running through the backend/companion
path, stopped cleanly, and released the port.

Full GPU/full offload `gpu_layers=999` failed safely with CUDA OOM on the 26B
model in earlier validation. Treat that as a hardware/model sizing issue, not an
app failure. Use CPU safe or partial GPU offload first.

## 10. Troubleshooting

Companion unconfigured:
Set backend `LMM_COMPANION_SOCKET` and `LMM_COMPANION_TOKEN`, then start the
host companion with matching config/token.

Socket missing:
Confirm the companion is running, the host socket exists, the containing runtime
directory is mounted into Docker, and the container-side
`LMM_COMPANION_SOCKET` points at the mounted socket.

Auth failed:
The backend token and companion token do not match. Rotate both values together
and keep the real token out of committed files and frontend code.

Models not showing:
Confirm `approved_roots` points at a directory containing `.gguf` files. Enable
recursive scan if needed. The companion scans approved roots only.

Saved selected model stale:
A saved model can come from a previous validation/session. Rescan with the
configured companion and reselect if the model is no longer present.

No profiles configured:
Add JSON `profiles` or configure `profile_preset_files` plus
`llama_server_executable`, then restart the companion.

Profile executable missing:
Verify `/usr/bin/llama-server` or your configured executable with
`command -v llama-server` and filesystem execute permissions. Executables belong
in JSON, not preset `.ini` files.

Port in use:
Choose another profile port or stop the process currently listening. The
companion does not adopt or stop manually started servers.

Model too large / CUDA OOM:
Lower `gpu_layers`, `ctx_size`, or `parallel`, use CPU safe mode, or use a
smaller model.

Readiness timeout:
The process started but `/v1/models` did not become ready in time. Inspect the
companion log tail, increase readiness timeout in config if appropriate, or use
safer profile defaults.

Manually started server not controlled by companion:
Stop it manually or use a different port. Companion stop/restart affects only
the tracked companion-managed process.

Docker backend cannot reach socket:
Check the override mount, container-side socket path, service name, and socket
directory permissions. Do not switch to host-gateway TCP without a separate
approved design.

Runtime/socket permissions:
Use a user-owned runtime directory with restrictive permissions. If the
container user cannot access the socket, adjust the mounted directory ownership
or group deliberately; do not mount the whole home directory as a workaround.

## 11. Security Checklist

- No whole-PC scan.
- Approved roots only.
- No token in frontend.
- No raw socket path in frontend.
- No absolute host model path in backend/UI responses.
- No Docker socket.
- No privileged container.
- No host PID namespace.
- No host networking or host-gateway TCP unless separately approved.
- No arbitrary flags, free-form shell, command strings, or frontend-supplied
  executable/model paths.
- No Provider Settings writes from LMM controls.
- Ask remains unchanged.
- Manual servers remain manual; companion stop controls only tracked
  companion-managed processes.
