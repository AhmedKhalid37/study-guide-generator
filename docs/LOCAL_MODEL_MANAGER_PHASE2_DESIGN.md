# LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md - Host companion and approved GGUF library

> **Status: Phase 2C read-only backend bridge implemented; socket-mount
> validation harness added.** Phase 2A established the host-companion boundary.
> Phase 2B adds a Linux-first, stdlib-only host companion prototype under
> `tools/local_model_companion/` for approved-folder GGUF scanning and a
> Unix-domain-socket API contract. Phase 2C adds a backend-only, read-only bridge
> from FastAPI to that companion for status, cached library, and explicit
> companion scan. The validation-only harness
> `test_scripts/validate_lmm_companion_socket_mount.py` passed live validation and
> proves the Docker app container can reach the host companion through a mounted
> Unix socket using a temporary Compose override. There is still no frontend UI,
> production Docker Compose mount, Provider Settings write, Ask change, dependency
> addition, model execution, or `llama-server` start/stop/restart behavior.

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

Phase 2C socket-mount validation:

- `test_scripts/validate_lmm_companion_socket_mount.py` is a manual live harness,
  not normal release smoke.
- It creates a temporary `/tmp` workspace with a fake approved model root,
  fake `.gguf` files, a non-GGUF file, explicit companion config, and a host
  companion Unix socket.
- It generates a temporary Compose override that mounts only the temporary
  runtime directory into the backend container and sets server-side
  `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and
  `LMM_COMPANION_TIMEOUT_SECONDS`.
- It verifies the deployed backend endpoints
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`, and
  `POST /api/local-model/library/scan` through `http://127.0.0.1:8000`.
- It checks fake GGUF discovery, non-GGUF exclusion, root-relative paths, response
  redaction of token/socket/raw temp host paths, and absence of local-model
  start/stop/restart endpoints.
- Live validation passed 17/17: the backend reported configured/reachable
  companion status with `scan`, returned safe empty cached library state before
  scan, returned two fake GGUF models after scan, excluded the non-GGUF file,
  returned root-relative paths only, leaked no token/socket/temp absolute host
  path, and left start/stop/restart probes unavailable.
- It makes no permanent Docker Compose change and does not introduce UI,
  Provider Settings writes, Ask changes, host-gateway TCP, Docker socket,
  privileged container mode, host PID namespace, `llama-server` launch, or model
  process control.

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

**Phase 2B implementation status:** implemented in
`tools/local_model_companion/companion.py` over a Unix domain socket using Python
stdlib HTTP handling. Requires `Authorization: Bearer <token>`; token may come from
`LMM_COMPANION_TOKEN` or the explicit local companion config and is never returned.

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

**Phase 2B implementation status:** implemented as a cached read. It returns the
last in-memory scan result only and does not scan until `POST /models/scan` is
called.

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

**Phase 2B implementation status:** implemented for configured approved roots only.
It returns safe model records with opaque ids derived from root id plus normalized
root-relative path. It does not expose absolute host paths in model records.

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

Phase 2C implemented only the first three read-only/library endpoints. The
start/stop/restart endpoints above remain future Phase 2E design targets and are
not registered in FastAPI by Phase 2C.

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

- **Phase 2B:** DONE. Companion prototype for approved-folder scanning only, using
  the Unix-domain-socket transport contract; no start/stop.
- **Phase 2C:** DONE. Backend bridge read-only companion status, cached model
  library, and explicit companion scan; no UI, no Docker Compose mount, no
  start/stop.
- **Phase 2D:** DONE. Local Models UI model library picker; frontend-only
  selection, no Provider Settings write, no Ask change, no process control.
- **Phase 2E:** either selected-model handoff to Provider Settings / command
  helper while still avoiding process control, or an explicit start/stop design
  review if the operator chooses to move toward process lifecycle management.
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

## 14. Phase 2B Scanning Prototype

Files:

- `tools/local_model_companion/config.py`
- `tools/local_model_companion/model_library.py`
- `tools/local_model_companion/companion.py`
- `test_scripts/test_local_model_companion_scan.py`

Config shape:

```json
{
  "approved_roots": [
    {
      "id": "default",
      "path": "/home/user/models",
      "recursive": true
    }
  ],
  "token": "optional-local-companion-token"
}
```

The config path must be explicit through `--config` or `LMM_COMPANION_CONFIG`.
There is no default home scan, no implicit `~/models`, and no silent approved-root
creation. Missing config returns a safe no-roots state. `LMM_COMPANION_TOKEN`
overrides the optional config token for the socket server.

CLI:

```bash
python -m tools.local_model_companion.companion --config /path/to/config.json scan
python -m tools.local_model_companion.companion --config /path/to/config.json serve --socket /path/to/companion.sock
```

Implemented scan safety:

- Scans only configured approved roots.
- Canonicalizes approved roots and candidate paths.
- Accepts `.gguf` case-insensitively.
- Resolves file symlinks and requires the resolved target to remain inside the
  approved root.
- Rejects symlink escapes and traversal candidates with bounded warnings.
- Skips symlinked directories to avoid recursive symlink loops.
- Supports recursive or top-level-only scans per root.
- Bounds files inspected, models returned, elapsed time, and warning count.
- Converts missing roots, broken symlinks, permission/path errors, and scan limits
  into bounded warnings instead of crashes.
- Returns safe model metadata only: opaque stable id, display name, filename,
  root-relative path, root id, size, modified timestamp, family/quant hints, and
  `server_compatible: true` for discovered GGUF candidates.

Implemented Unix socket API:

- `GET /health`
- `GET /models`
- `POST /models/scan`

No process-control API is implemented in Phase 2B. There is no `/server/start`,
`/server/stop`, or `/server/restart`, no `llama-server` launch, no shell execution,
and no subprocess usage in the companion package.

## 15. Phase 2C Backend Companion Bridge

Files:

- `pipeline/local_model_companion_client.py`
- `api/server.py`
- `test_scripts/test_local_model_companion_bridge.py`

Backend endpoints:

```text
GET  /api/local-model/companion/status
GET  /api/local-model/library
POST /api/local-model/library/scan
```

Configuration is server-side only:

- `LMM_COMPANION_SOCKET`
- `LMM_COMPANION_TOKEN`
- `LMM_COMPANION_TIMEOUT_SECONDS` (optional)

Missing socket or token means the bridge is unconfigured. The raw token and raw
socket path are never returned to the frontend. Responses expose only
`socket_configured: true/false` and, when configured, `socket_label: "configured"`.

Implemented client behavior:

- Uses stdlib `socket.AF_UNIX`; no new dependency.
- Sends `Authorization: Bearer <token>` to the companion.
- Calls companion `GET /health`, `GET /models`, and `POST /models/scan`.
- Bounds request timeout and response body size.
- Parses JSON and rejects malformed or unexpected shapes safely.
- Treats unconfigured/offline/auth/timeout/error states as safe DTOs, not raw API
  crashes.

Normalized error categories:

- `companion_config`
- `companion_offline`
- `companion_auth`
- `companion_timeout`
- `companion_error`

Model-library safety:

- `GET /api/local-model/library` reads the companion cached model list only; it
  does not trigger a scan.
- `POST /api/local-model/library/scan` triggers scanning inside the companion only.
  The Docker backend still never scans host folders directly.
- Model records are whitelisted to: `id`, `display_name`, `filename`,
  `relative_path`, `root_id`, `size_bytes`, `modified_at`, `family_hint`,
  `quant_hint`, and `server_compatible`.
- Unexpected companion fields are dropped.
- Absolute `relative_path` values are not returned.
- Absolute paths, URLs, auth-like text, and token-like text are redacted from
  returned strings and bounded warnings.
- Warnings are bounded and include truncation metadata when the companion sends too
  many entries.

Non-goals preserved in Phase 2C:

- No frontend UI.
- No Docker Compose mount or deployment change.
- No Provider Settings write and no local-provider base URL behavior change.
- No Ask change.
- No host-gateway TCP implementation.
- No direct Docker host filesystem scan.
- No model launch.
- No process-control route.
- No `/api/local-model/server/start`, `/api/local-model/server/stop`, or
  `/api/local-model/server/restart`.
- No shell execution and no subprocess usage in the bridge code.

Focused validation:

- `python test_scripts/test_local_model_companion_bridge.py` passed 14/14 checks in
  host Python. FastAPI route introspection was skipped there because FastAPI was not
  installed, matching the existing backend script style; source-level route checks
  still verify no start/stop/restart API was added.

## 16. Phase 2D Frontend Model-Library Picker

Files:

- `frontend/src/api/client.js`
- `frontend/src/localModelLibrary.js`
- `frontend/src/components/LocalModelsPanel.jsx`
- `frontend/scripts/verify-local-model-library.mjs`
- `frontend/package.json`

Frontend API helpers:

```text
getLocalModelCompanionStatus() -> GET  /api/local-model/companion/status
getLocalModelLibrary()         -> GET  /api/local-model/library
scanLocalModelLibrary()        -> POST /api/local-model/library/scan
```

Implemented UI behavior:

- Adds a compact **Model Library** section inside the existing Local Models panel.
- Fetches companion status and cached library data on open.
- Shows safe states for companion unconfigured, offline/unreachable, auth failed,
  reachable, endpoint unavailable, no approved roots, no cached/discovered models,
  and scan warnings.
- The scan button is an explicit **Scan approved folder(s)** action that delegates
  to the existing Phase 2C backend scan endpoint.
- Renders discovered GGUF models using only safe fields:
  `display_name`, `filename`, `relative_path`, `root_id`, formatted `size_bytes`,
  formatted `modified_at`, `family_hint`, `quant_hint`, and
  `server_compatible`.
- Allows visual-only selection in React state. Selection is not persisted and is
  not consumed by Ask or Provider Settings in this slice.
- Keeps the existing Phase 1 manual command helper visible/usable when companion
  discovery is unavailable.

Non-goals preserved in Phase 2D:

- No backend endpoint addition.
- No Docker Compose change.
- No Provider Settings write and no local-provider base URL/default-model behavior
  change.
- No Ask change.
- No browser localStorage/sessionStorage.
- No token, raw socket path, Authorization header, or absolute host path exposure.
- No `dangerouslySetInnerHTML`.
- No dependency addition.
- No `llama-server` launch.
- No process-control UI or route.
- No `/api/local-model/server/start`, `/api/local-model/server/stop`, or
  `/api/local-model/server/restart`.

Focused validation:

- `npm --prefix frontend run test:local-model-library` covers API helper
  paths/methods, companion state normalization, model whitelist normalization,
  safe rendering source checks, scan flow, frontend-only selection, no Provider
  Settings writes, no browser storage, no raw HTML rendering, no token/socket/auth
  strings in the new UI slice, and no process-control routes/labels in the new
  section.
- Existing frontend checks (`test:local-model-status`,
  `test:local-model-command`) and backend local-model suites remain green.

Next recommended slice is Phase 2E selected-model handoff to Provider Settings /
command helper, still with no process control. If the operator explicitly wants to
move toward process lifecycle management, do a Phase 2E start/stop design review
before implementation.
