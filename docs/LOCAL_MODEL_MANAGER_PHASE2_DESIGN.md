# LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md - Host companion and approved GGUF library

> **Status: Phase 2A DESIGN ONLY.** No code, endpoints, UI, Docker changes, model
> scanning, or process spawning are implemented by this slice. Phase 1 remains
> complete and validated: detection-only status, Local Models panel, and manual
> command helper. This document designs the next architecture boundary for a
> future Local Model Manager that can scan user-approved GGUF folders and manage a
> host `llama-server` through a small host-side companion.

---

## 1. Problem Statement

Phase 1 is intentionally detection-only. It tells the user whether the configured
local OpenAI-compatible server is reachable, lists models exposed by that running
server, and provides a copyable manual `llama-server` command template. That is no
longer enough for the desired future workflow:

- The user wants to approve a local model directory and see GGUF models inside the
  app.
- The user wants to select a model from that discovered local library.
- The user wants Start / Stop / Restart buttons instead of manually running a
  command.

Those requirements need host filesystem access and host process control. The
Docker backend must not directly browse the host filesystem, directly start or
stop host processes, mount the Docker socket, run privileged, use the host PID
namespace, or scan the whole PC. Direct Docker-to-host spawning remains rejected.

The safe boundary is a small explicit host companion running outside Docker under
the user's host account. The Docker backend talks to it over a narrow local API;
the companion owns host filesystem and process access.

## 2. Architecture Overview

Future flow:

```text
React UI
  -> Docker FastAPI backend
  -> mounted Unix-domain-socket host companion API
  -> approved model directory scan
  -> llama-server process start/stop on host
```

Boundaries:

- React UI never talks directly to the companion.
- Docker FastAPI backend is the only bridge between frontend and companion.
- Host companion runs under the user's host account, outside Docker.
- For the current Linux Docker deployment, the primary companion transport is a
  Unix domain socket mounted into the backend container.
- A `127.0.0.1`-only companion control API is valid only for native/desktop
  packaging, host-network Docker, or a host-gateway TCP alternative that receives
  explicit operator sign-off.
- Host companion control never binds to public `0.0.0.0`.
- Host companion requires an auth token on every non-public request.
- The companion token is stored server-side only and is never exposed to the
  frontend.
- The frontend never receives the companion token or socket path.
- The companion only starts/stops processes it started and tracks.
- The companion provides host filesystem/process access; the Docker backend does
  not attempt to emulate that access.

The companion may start `llama-server` with `--host 0.0.0.0` so the Docker backend
can reach the model server through the existing local-provider base URL. That is
separate from the companion's own control API, which must never be exposed
publicly.

### Transport / Connectivity

Linux Docker cannot assume that a host service bound only to host `127.0.0.1` is
reachable from a container. Container `127.0.0.1` is the container itself, and
`host.docker.internal`/host-gateway access may not reach a host loopback-only
listener. Phase 2B should therefore assume Unix socket transport unless the
operator explicitly chooses a TCP alternative.

Primary Linux Docker design:

- The host companion listens on a Unix domain socket file, for example under a
  user-owned runtime directory such as `$XDG_RUNTIME_DIR/main-app-lmm/companion.sock`
  or another operator-configured user-owned directory.
- Docker Compose later mounts only that socket file, or the containing runtime
  directory, into the backend container.
- The backend calls the companion through that mounted socket.
- Socket file permissions restrict access to the host user and the container user
  or group selected for the deployment.
- Token authentication remains as defense-in-depth unless a later accepted design
  deliberately drops it after reviewing socket ownership and permissions.
- The React frontend never receives the token, socket path, mounted path, or raw
  companion connection details.
- This preserves the "not exposed on the network" property better than TCP.

Documented alternatives:

1. **Host-gateway TCP companion.** The companion binds to a host/Docker-reachable
   interface or Docker bridge gateway, not public `0.0.0.0`. Firewall rules must
   restrict access to Docker bridge subnets. Token auth is required. This is
   practical but weaker than a Unix socket and needs explicit operator sign-off.
2. **Host networking.** The backend container uses host networking so
   `127.0.0.1` reaches the host listener. This is not the default because it
   changes Docker deployment and security assumptions.
3. **Pure host desktop/native packaging.** A later package may run backend and
   companion under the same host user, avoiding Docker bridge issues. In that
   packaging, a `127.0.0.1`-only control API can be valid.

## 3. Approved Model Directory Design

The model library is opt-in and root-scoped:

- User may configure one or more approved model roots.
- The companion scans only those approved roots.
- Scan is explicit, triggered by the user, not silent background scanning.
- Optional recursive scanning may be allowed only under an approved root.
- Only `.gguf` files are model candidates.
- No whole-PC scan.
- No home-directory scan by default.
- No arbitrary path search from Docker.
- No frontend-provided absolute path is used as a shell/process argument.

Path safety rules:

- Approved roots are canonicalized when configured.
- Candidate files are canonicalized before use.
- Traversal outside approved roots is rejected.
- `..` traversal is rejected.
- Symlink policy must be explicit. Recommended v1 policy: resolve symlinks and
  require the resolved path to remain inside an approved root. A stricter v1 may
  reject symlinks entirely; either policy is acceptable only if documented and
  tested.
- The frontend should not receive unnecessary absolute host paths. It should see
  display metadata and an opaque model id or root-relative path.

## 4. Model Metadata Schema

Companion model records should be safe to return through the backend after
redaction:

```jsonc
{
  "id": "opaque_companion_model_id",
  "display_name": "gemma-4-26B-A4B-it-UD-Q4_K_M",
  "filename": "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
  "relative_path": "gemma/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
  "size_bytes": 17179869184,
  "modified_at": "2026-06-06T10:20:30Z",
  "family_hint": "gemma",
  "quant_hint": "Q4_K_M",
  "selected": false,
  "server_compatible": true
}
```

Rules:

- `id` is the stable value used by start requests.
- Backend may store only the opaque companion model id instead of a host path.
- `relative_path` is optional; if exposed, it must be root-relative and safe.
- Absolute host paths should be kept out of frontend responses unless a later
  explicit troubleshooting design allows a redacted display form.
- `family_hint` and `quant_hint` are best-effort filename hints, not trusted
  compatibility guarantees.
- `server_compatible` means "compatible with the companion's configured
  launcher/profile rules," not model quality validation.

## 5. Companion API Design

The companion API is narrow, local-only, token-authenticated, and command-
whitelisted. For Linux Docker it is served over the mounted Unix socket described
in §2. A TCP listener is allowed only for native/host-network packaging or the
explicitly signed-off host-gateway TCP alternative; it must never be public.

### `GET /health`

- Auth: required.
- Request body: none.
- Response:

```jsonc
{ "ok": true, "version": "0.1.0", "platform": "linux", "capabilities": ["scan"] }
```

- Redaction: no paths, token, environment, command line, or secrets.
- Failure modes: unavailable companion, version mismatch, unauthorized.

### `GET /models`

- Auth: required.
- Request body: none.
- Response:

```jsonc
{ "ok": true, "models": [], "last_scan_at": null, "roots_configured": 1 }
```

- Redaction: no unnecessary absolute host paths.
- Failure modes: unauthorized, no approved roots, scan cache unavailable,
  malformed state.

### `POST /models/scan`

- Auth: required.
- Request body:

```jsonc
{ "recursive": true, "root_ids": ["default"] }
```

- Response:

```jsonc
{
  "ok": true,
  "models": [],
  "scanned_roots": 1,
  "rejected_count": 0,
  "warnings": []
}
```

- Redaction: warnings must be bounded and path-redacted or root-relative.
- Failure modes: no approved roots, root missing, permission denied, symlink
  escape rejected, traversal rejected, scan timeout, too many files.

### `GET /server/status`

- Auth: required.
- Request body: none.
- Response:

```jsonc
{
  "ok": true,
  "state": "stopped",
  "pid": null,
  "model_id": null,
  "profile_id": null,
  "port": 8080,
  "started_at": null,
  "health": { "reachable": false, "latency_ms": null },
  "last_error": null,
  "log_tail": []
}
```

- Redaction: bounded sanitized log tail only; no full command with absolute paths
  unless path-redacted.
- Failure modes: stale PID, crashed process, port conflict, unauthorized.

### `POST /server/start`

- Auth: required.
- Request body:

```jsonc
{
  "model_id": "opaque_companion_model_id",
  "profile_id": "gpu_default",
  "parameters": {
    "ctx_size": 8192,
    "gpu_layers": 999,
    "port": 8080,
    "threads": 8
  }
}
```

- The request accepts a selected model id, not a path and not a command.
- The request accepts a whitelisted profile id.
- Optional parameters are typed and bounded only.
- No free-form args in v1.
- Response:

```jsonc
{ "ok": true, "state": "starting", "pid": 12345, "model_id": "opaque_companion_model_id", "port": 8080 }
```

- Failure modes: already running, unknown model id, model outside approved root,
  unknown profile, invalid parameter, port in use, executable missing, start
  timeout, server health check failed, unauthorized.

### `POST /server/stop`

- Auth: required.
- Request body:

```jsonc
{ "grace_seconds": 10 }
```

- Response:

```jsonc
{ "ok": true, "state": "stopped" }
```

- Failure modes: not running, stale PID, tracked process already exited, process
  did not stop after grace timeout, unauthorized.
- The companion must not kill unrelated processes.

### `POST /server/restart`

- Auth: required.
- Request body: same as start, or `{ "reuse_last": true }` only if last launch
  metadata is available and safe.
- Response: same shape as start/status.
- Failure modes: stop failure, start failure, missing last launch metadata,
  unauthorized.

## 6. Command/Profile Model

The companion launches `llama-server` only through whitelisted profiles:

- `gpu_default`: default GPU/offload profile for the current Linux host.
- `cpu`: CPU-only profile.
- `low_memory`: optional later profile with smaller context/batch values.

Profile rules:

- Fixed executable path is configured in the companion, not supplied by the
  frontend.
- Executable path is canonicalized and checked for existence and execute
  permission.
- Fixed flags come from the profile.
- User-adjustable values are typed and bounded: context size, GPU layers, port,
  maybe threads.
- No free-form args in v1.
- No shell string execution.
- Use `subprocess` with an argv array, never `shell=True`.
- Companion records PID, model id, profile id, port, start time, argv metadata
  with redacted paths, and log file location for processes it starts.

## 7. Process Lifecycle

Start:

- If the companion has a running tracked process, `start` returns an
  `already_running` error unless a restart endpoint is used.
- Before spawning, validate model id, profile id, typed parameters, executable,
  and port availability.
- After spawning, poll the OpenAI-compatible health/models endpoint until ready or
  timeout.
- If readiness fails, stop the child it just started and return a bounded error.

Stop:

- Stop only the tracked process started by the companion.
- Send graceful termination first, then force-kill only that tracked process after
  timeout.
- If no tracked process exists, return `not_running`.
- If the PID is stale or belongs to another command, clear state and do not kill it.

Restart:

- Restart is stop-then-start.
- It either requires an explicit start request or uses previously recorded launch
  metadata only when that metadata remains valid.

Crash and stale PID handling:

- Status checks whether the tracked PID is alive and still matches the expected
  process metadata.
- Dead tracked PID becomes `crashed` or `stopped` with last exit metadata.
- Recycled/foreign PID is treated as stale and is not killed.
- No auto-restart loop in v1.

Port conflict:

- Detect before start where possible.
- If another process is already bound to the port, fail with `port_in_use`.
- If the child reports address-in-use after spawn, surface that as `port_in_use`
  and clean up the tracked child.

Logs:

- Capture stdout/stderr to a companion-owned host log file.
- Expose only a bounded sanitized tail.
- Redact tokens, raw API keys, full URLs with credentials, and absolute model paths
  where possible.
- Do not expose unbounded logs or streaming logs in v1.

Manual external `llama-server`:

- If the user manually started another `llama-server`, the companion may report
  port conflict or backend health may show reachable.
- The companion must not adopt or kill that unrelated process in v1.
- Stop only affects the tracked process the companion started.

## 8. Backend Bridge Design

Future Docker backend endpoints:

```text
GET  /api/local-model/companion/status
GET  /api/local-model/library
POST /api/local-model/library/scan
POST /api/local-model/server/start
POST /api/local-model/server/stop
POST /api/local-model/server/restart
```

Backend rules:

- Backend reads companion connection config/token from server-side config only.
- For Linux Docker, the expected companion connection config is the mounted Unix
  socket path inside the backend container plus the server-side token.
- Frontend never receives the companion token, socket path, or raw connection
  config.
- Backend is the only caller of the companion API.
- Backend redacts host paths before returning data to the UI.
- Backend normalizes companion errors into existing categories where possible:
  `local_offline`, `provider_config`, `provider_network`, `provider_model`, and
  a narrow companion-specific category only if needed.
- Provider Settings remains the config writer for local base URL/default model
  unless a later accepted design deliberately changes that.
- Local Models page becomes the operational view: companion status, library,
  selection, start/stop controls, and fallback helper. It is not a second provider
  settings writer.

## 9. UI Design

Future Local Models page shows:

- current server status;
- companion status;
- approved model folder status;
- explicit scan button;
- discovered GGUF model list;
- selected model;
- Start / Stop / Restart buttons;
- command helper fallback;
- bounded errors and troubleshooting.

Behavior:

- User selects a model from the discovered list.
- Start starts the selected model through the backend and companion.
- Stop stops only the tracked companion-started server.
- Restart is explicit and uses the same constraints as start.
- If the companion is absent, show the Phase 1 manual command helper and keep
  process controls unavailable.
- No silent scanning and no scary whole-PC scanning. The UI should say which
  approved folder roots are configured and when the last explicit scan ran.

## 10. Security Model

Mandatory controls:

- Linux Docker control transport is Unix socket first.
- `127.0.0.1`-only companion control is valid only for native/desktop packaging,
  host-network Docker, or a signed-off TCP alternative; it is not assumed
  reachable from the current Docker backend.
- Companion control never binds publicly to `0.0.0.0`.
- Token auth on companion API.
- Token stored server-side only.
- No frontend token or socket-path exposure.
- No arbitrary shell.
- No free-form command args in v1.
- No full-PC scan.
- No home scan by default.
- No arbitrary path traversal.
- No arbitrary path search from Docker.
- No raw API keys in responses or logs.
- No unbounded logs.
- No world-readable secrets.
- No killing unrelated host processes.
- No Docker socket.
- No privileged container.
- No host PID namespace.
- No `--privileged`.
- Direct Docker host process spawn is permanently rejected.

The companion is an untrusted-input boundary even on localhost. It must whitelist
parse every request, bound every value, canonicalize every path, and emit only
safe response fields.

## 11. Cross-Platform Notes

- Linux first, because the current operator is on Linux/CachyOS.
- GPU and driver details stay host-side.
- Windows and macOS support need separate design later.
- Windows path handling, executable discovery, process termination, and service
  behavior differ and should not be improvised inside the Linux-first slice.
- Companion packaging, signing, installer UX, auto-start, and update flow are
  deferred.

## 12. Slice Plan After Phase 2A

- **Phase 2B:** companion prototype design/code for approved-folder scanning only,
  using the chosen transport contract; no start/stop.
- **Phase 2C:** backend bridge read-only companion status and model library.
- **Phase 2D:** Local Models UI model library picker.
- **Phase 2E:** start/stop selected model through companion.
- **Phase 2F:** validation/security pass.
- **Later:** packaging/signing and cross-platform installers.

Each slice must preserve the boundary: Docker backend talks to the companion; the
companion owns host filesystem/process access; frontend never receives the token.

## 13. Explicit Non-Goals for Phase 2A

- No code.
- No companion implementation.
- No backend endpoints.
- No frontend UI.
- No Docker changes.
- No process spawn.
- No model scanning implementation.
- No provider settings behavior change.
- No Ask behavior change.
- No extra uploads.
- No new dependency.
