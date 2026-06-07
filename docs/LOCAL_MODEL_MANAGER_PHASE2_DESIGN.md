# LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md - Host companion and approved GGUF library

> **Status: Phase 2G5 real Linux llama-server validation/hardening complete.** Phase 2A
> established the host-companion boundary.
> Phase 2B adds a Linux-first, stdlib-only host companion prototype under
> `tools/local_model_companion/` for approved-folder GGUF scanning and a
> Unix-domain-socket API contract. Phase 2C adds a backend-only, read-only bridge
> from FastAPI to that companion for status, cached library, and explicit
> companion scan. The validation-only harness
> `test_scripts/validate_lmm_companion_socket_mount.py` passed live validation and
> proves the Docker app container can reach the host companion through a mounted
> Unix socket using a temporary Compose override. Phase 2D adds the frontend
> model-library picker. Phase 2E persists the selected discovered GGUF model as
> app-side safe metadata only and feeds a non-runnable future-launch preview.
> Phase 2F is docs-only and defines the safe contract for future Phase 2G
> companion-managed `llama-server` start/stop/restart. Phase 2G1 adds
> companion-private process-management internals under
> `tools/local_model_companion/` and validates them only with a fake/safe test
> executable. Phase 2G2 exposes those internals on the companion's own
> Unix-socket HTTP API. Phase 2G3 exposes those companion process endpoints
> through safe FastAPI backend bridge routes only. Phase 2G4 adds frontend UI
> controls that call only those backend bridge routes with a saved selected model
> id plus fixed typed `fake_test` defaults. Phase 2G5 adds explicit-config real
> Linux `llama-server` profiles, readiness polling against `/v1/models`, bounded
> log/error classification, process-group stop hardening, and a live validation
> harness.
> There is still no production Docker Compose mount, Provider Settings write, Ask
> change, dependency addition, local provider base-URL/model behavior change,
> direct companion frontend call, host-gateway TCP, Docker socket, privileged
> container, host PID namespace, automatic restart loop, model download manager,
> multi-server pool, or Windows/macOS process control.

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

Phase 2C implemented the first three read-only/library endpoints. Phase 2E adds
selection metadata endpoints under `/library/selection`. Phase 2G3 implements the
server status/start/stop/restart backend bridge routes above. Phase 2G4 adds UI
controls that call only those backend bridge routes. They delegate only to the
companion Unix socket; the Docker backend does not directly inspect, start, stop,
signal, or adopt host processes.

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
- **Phase 2E:** DONE. Selected discovered GGUF model persists as app-side safe
  metadata and feeds a non-runnable future-launch preview; no Provider Settings
  write, no Ask change, no process control.
- **Phase 2F:** DONE. Start/stop design review for future companion-managed
  `llama-server` process control; docs only, no routes or implementation.
- **Phase 2G1:** DONE. Companion process-control internals with a fake/safe test
  executable only; no companion HTTP start/stop API, backend bridge, or UI.
- **Phase 2G2:** DONE. Companion HTTP server endpoints for process status/start/
  stop/restart using the internal manager; still no backend bridge or UI.
- **Phase 2G3:** DONE. Backend bridge for server status/start/stop/restart; no
  UI, Docker change, Provider Settings write, Ask change, or real
  `llama-server` validation.
- **Phase 2G4:** DONE. Local Models UI start/stop/restart controls, still
  fake/safe validation only; no backend routes, Docker changes, Provider
  Settings writes, Ask changes, or real `llama-server` validation.
- **Phase 2G5:** DONE. Explicit-config real Linux `llama-server` profiles,
  readiness polling, lifecycle hardening, safe error classification, and live
  validation harness.
- **Phase 2G6:** operator-run live validation follow-up and optional real-profile
  UI design, if requested.
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

## 17. Phase 2E Selected Library Model Handoff

Files:

- `pipeline/local_model_library_selection.py`
- `api/server.py`
- `pipeline/provider_config.py`
- `test_scripts/test_local_model_library_selection.py`
- `frontend/src/api/client.js`
- `frontend/src/localModelLibrary.js`
- `frontend/src/components/LocalModelsPanel.jsx`
- `frontend/scripts/verify-local-model-library.mjs`

Backend endpoints:

```text
GET    /api/local-model/library/selection
POST   /api/local-model/library/selection
DELETE /api/local-model/library/selection
```

Storage:

- Durable app-side JSON file: `config/local_model_library_selection.json`.
- Schema: `{ "version": 1, "selected": null | safe_selected_model }`.
- Writes use atomic temp-file plus `os.replace`.
- This is not a job artifact, export, history file, cache, Provider Settings file,
  or browser storage.

Stored selected-model fields:

- `id`
- `display_name`
- `filename`
- `relative_path` (root-relative only; absolute values dropped)
- `root_id`
- `size_bytes`
- `modified_at`
- `family_hint`
- `quant_hint`
- `server_compatible`
- `selected_at`

Implemented behavior:

- `GET /selection` returns the current safe selected model or `selected: null`,
  plus a non-runnable `future_launch_preview`.
- `POST /selection` accepts `model_id` plus an optional safe model snapshot. When
  the cached companion library has models, the backend validates the id against
  that cached list and stores the sanitized library record. If no cached list is
  available, it stores only the sanitized snapshot.
- `DELETE /selection` clears only this app-side selection file.
- `GET /api/local-model/command-profile` includes `selected_library_model` and a
  non-runnable `future_launch_preview` with model id, filename, root-relative
  path, root id, `gpu_default` profile placeholder, and companion-model-id
  resolver.
- The Local Models panel fetches saved selection on load, lets the user click a
  model, persists only after **Remember selected model**, shows the saved **Chosen
  library model**, marks it stale when absent from the current library, and offers
  **Clear selection**.
- The preview deliberately does not generate a runnable command with a host
  absolute model path. Future companion launch will resolve the selected model id.
- Existing Phase 1 manual command helper remains available.

Non-goals preserved in Phase 2E:

- No Provider Settings write.
- No Ask change.
- No local provider base URL/default model/runtime behavior change.
- No Docker Compose change.
- No host-gateway TCP, Docker socket, privileged container, or host PID namespace.
- No `llama-server` launch.
- No subprocess, shell execution, or process control.
- No start/stop/restart route or UI control.
- No browser localStorage/sessionStorage.
- No raw companion token, socket path, Authorization header, full URL, or absolute
  host model path exposure.

Focused validation:

- `python test_scripts/test_local_model_library_selection.py` passed 14/14,
  covering empty/save/load/clear, absolute `relative_path` drop, unsafe field
  dropping, token/socket/auth/full-URL/path-like redaction, no Provider Settings
  change, no job artifact touch, no start/stop/restart endpoints, no
  subprocess/shell source, and command-helper preview metadata.
- `npm --prefix frontend run test:local-model-library` covers selection
  GET/POST/DELETE helpers, selected UI state, persisted display, stale display,
  clear flow, no Provider Settings calls, no browser storage, no raw HTML, no
  process-control routes/labels, and no companion connection secret strings in
  the new UI slice.

## 18. Phase 2F Start/Stop Design Review

Phase 2F is a docs-only safety review before any `llama-server` process-control
implementation. It defines the required contract for Phase 2G and does not add
companion code, backend routes, frontend controls, Docker changes, subprocess
launching, Provider Settings writes, Ask changes, dependencies, or any
start/stop/restart behavior.

### Threat Model

Future process control must defend against:

- arbitrary command execution through free-form flags, shell strings, executable
  paths, profile names, model ids, or filenames;
- killing unrelated host processes, including manually started `llama-server`
  instances;
- path traversal, symlink escape, or a model path resolving outside an approved
  root;
- malicious model filenames, root ids, profile ids, or typed parameter inputs;
- port conflicts with manually started servers or unrelated processes;
- stale PID files and PID reuse after the tracked process exits;
- log leakage of tokens, Authorization headers, full URLs with credentials,
  absolute model paths, environment variables, or command lines;
- token/socket leakage from companion to backend to frontend;
- frontend accidentally receiving raw host paths;
- the companion control API being exposed to the network;
- the Docker backend becoming a general host process manager;
- user confusion between selected model metadata and the currently running
  companion-managed model.

### Process-Control Boundary

The boundary remains unchanged:

- Docker FastAPI never directly starts, stops, restarts, signals, or inspects host
  processes.
- Only the host companion may spawn `llama-server`.
- The companion may stop only a process it started and still tracks as its own.
- No Docker socket, privileged container, host PID namespace, or direct
  Docker-to-host spawn is allowed.
- Companion control is Unix-socket-first for the Linux Docker deployment.
- Companion token/auth remains required for all non-public companion requests.
- The frontend never receives the companion token, socket path, Authorization
  header, raw companion URL, or raw absolute host model path.

The model API and the companion control API are separate. `llama-server` may bind
`--host 0.0.0.0` so the Docker backend can reach the OpenAI-compatible model API,
but the companion control API must never bind publicly. If future security work
wants a tighter model API binding, that needs its own design and validation.

### Companion Server API Contract

All endpoints require `Authorization: Bearer <token>`, return JSON, use bounded
request/response sizes, and redact tokens, socket paths, raw absolute host paths,
Authorization headers, credentialed URLs, and unbounded logs.

Allowed states:

- `stopped`: no tracked companion-started server is active.
- `starting`: companion spawned a tracked child and is waiting for health.
- `running`: tracked child identity is verified and health succeeded recently.
- `stopping`: companion is terminating only its tracked child.
- `crashed`: tracked child exited unexpectedly or failed health after start.
- `unknown`: companion cannot prove process identity or state safely.
- `error`: companion hit a bounded operational/configuration error.

`GET /server/status`

- Request body: none.
- Response shape:

```jsonc
{
  "ok": true,
  "state": "stopped",
  "managed": false,
  "model_id": null,
  "root_id": null,
  "profile_id": null,
  "port": null,
  "params": {},
  "started_at": null,
  "last_health_check": null,
  "last_error": null,
  "log_tail": null
}
```

- `pid` is omitted in normal frontend/backend responses. If a troubleshooting
  response later includes a process hint, it must be bounded and not enough to
  invite manual killing from the UI.
- `log_tail` is `null` unless explicitly requested by a later bounded
  troubleshooting flag; v1 should not stream logs.
- Error categories: `unauthorized`, `state_unavailable`, `stale_pid`,
  `identity_uncertain`, `companion_config`, `companion_error`.
- State transitions: refresh may move `starting` to `running` or `crashed`,
  `running` to `crashed` or `unknown`, `stopping` to `stopped` or `unknown`.

`POST /server/start`

- Request body accepts only:

```jsonc
{
  "model_id": "opaque_companion_model_id",
  "profile_id": "gpu_default",
  "parameters": {
    "port": 8080,
    "ctx_size": 8192,
    "gpu_layers": 999,
    "threads": null,
    "batch_size": null
  }
}
```

- `model_id` must resolve inside the companion's approved-root model library.
- `profile_id` must be one of the companion's whitelisted profiles.
- Parameters are typed and bounded. Unknown parameters are rejected.
- No shell command, no free-form args, no arbitrary executable path, no model path,
  and no environment block is accepted from the frontend or backend.
- Response shape:

```jsonc
{
  "ok": true,
  "state": "starting",
  "managed": true,
  "model_id": "opaque_companion_model_id",
  "root_id": "default",
  "profile_id": "gpu_default",
  "port": 8080,
  "params": {
    "ctx_size": 8192,
    "gpu_layers": 999,
    "threads": null,
    "batch_size": null
  },
  "started_at": "2026-06-06T12:00:00Z",
  "last_error": null
}
```

- Error categories: `unauthorized`, `already_running`, `unknown_model`,
  `model_outside_approved_root`, `invalid_profile`, `invalid_parameter`,
  `port_in_use`, `executable_missing`, `executable_not_allowed`,
  `launch_failed`, `start_timeout`, `health_check_failed`, `companion_config`,
  `companion_error`.
- State transitions: `stopped`/`crashed`/safe `unknown` -> `starting` ->
  `running` on health success, or `crashed`/`error` on launch or health failure.
  `running` -> `already_running` unless restart is used.

`POST /server/stop`

- Request body:

```jsonc
{ "grace_seconds": 10 }
```

- `grace_seconds` is optional and bounded. The companion may clamp it to a safe
  range.
- Stop only targets the tracked PID started by this companion.
- If the PID is stale, reused, foreign, or identity cannot be proven, do not kill;
  clear stale state or mark `unknown` safely.
- Response shape:

```jsonc
{
  "ok": true,
  "state": "stopped",
  "managed": false,
  "last_error": null
}
```

- Error categories: `unauthorized`, `not_running`, `stale_pid`,
  `identity_uncertain`, `stop_timeout`, `companion_error`.
- State transitions: `running`/`starting` -> `stopping` -> `stopped`; uncertain
  identity -> `unknown` without signaling.

`POST /server/restart`

- Request body requires either an explicit validated start payload:

```jsonc
{
  "model_id": "opaque_companion_model_id",
  "profile_id": "gpu_default",
  "parameters": { "port": 8080, "ctx_size": 8192, "gpu_layers": 999 }
}
```

  or:

```jsonc
{ "reuse_last": true }
```

- `reuse_last` works only when the last launch metadata still validates against
  the current approved model library, profile whitelist, executable config, and
  parameter bounds.
- Restart is stop then start. If stop cannot prove identity, restart must not
  kill and must not continue to start unless the resulting state is safe and the
  explicit request says to start after a non-running/cleared state.
- Response shape: same safe fields as start/status.
- Error categories: all stop/start categories plus `missing_last_launch`,
  `last_launch_invalid`, `restart_stop_failed`, `restart_start_failed`.

### Whitelisted Launch Profiles

Profiles convert selected model metadata plus typed bounded parameters into an
argv array. They never accept free-form flags.

Shared rules:

- The executable path is configured in companion config, never supplied by UI or
  backend.
- The executable path is canonicalized and checked for existence, execute
  permission, and expected file identity where possible.
- The model id is resolved by the companion against the approved-root model
  library. The model path never comes from frontend/backend.
- Launch uses an argv array only and never `shell=True`.
- Numeric parameters are bounded and rejected or clamped only by explicit profile
  rules.
- Profile defaults are companion-owned and may be displayed to the UI only as safe
  metadata.

Initial profiles:

| Profile | Purpose | Defaults | Bounds |
| --- | --- | --- | --- |
| `gpu_default` | Normal GPU/offload launch | `port: 8080`, `ctx_size: 8192`, `gpu_layers: 999`, `threads: null`, `batch_size: null` | `port: 1024-65535`, `ctx_size: 512-131072`, `gpu_layers: 0-999`, `threads: 1-256`, `batch_size: 1-4096` |
| `cpu` | CPU-only launch | `port: 8080`, `ctx_size: 4096`, `gpu_layers: 0`, `threads: null`, `batch_size: null` | same port/thread/batch bounds; `ctx_size: 512-65536`; `gpu_layers: 0` only |
| `low_memory` | Later constrained profile | `port: 8080`, `ctx_size: 2048`, `gpu_layers: 0`, `threads: null`, `batch_size: 128` | may be added later after validation; absent profiles are rejected |

Example argv shape:

```text
/path/to/llama-server
  -m <resolved-approved-model-path>
  --host 0.0.0.0
  --port <port>
  -c <ctx_size>
  -ngl <gpu_layers>
```

The private argv contains the resolved model path only inside the companion. API
responses expose model id, root id, filename/display metadata, and redacted argv
metadata only.

### Process State Storage

The companion stores process state in a companion-owned runtime/config directory
with restricted permissions. The state file contains:

- tracked PID;
- process start time;
- executable fingerprint and/or canonical resolved executable path;
- argv metadata with model path redacted for API use;
- private resolved model path only if needed for identity verification;
- model id and root id;
- profile id;
- port;
- selected typed params;
- `started_at`;
- `last_health_check`;
- `last_error`;
- log path;
- status.

Rules:

- No raw companion token, Authorization header, provider API key, or socket secret
  is stored in process state.
- API responses omit unnecessary absolute model paths. Absolute paths may remain
  in companion-private state only when needed to verify process identity.
- State updates should be atomic to avoid corrupt stale PID files.
- Stale PID detection must guard against PID reuse before any signal is sent.

### Process Identity and Stale PID Checks

Before reporting a tracked process as running or stopping it, the companion must
verify identity:

- PID exists.
- Command or executable matches the expected canonical `llama-server` path where
  the platform supports it.
- Process start time matches the recorded start time where available.
- The expected port responds to the expected model-server health probe.
- If any required identity check is uncertain, the companion does not kill.

Linux is first. Use `/proc/<pid>` for executable, command line, and process start
metadata when available. Windows/macOS process identity and termination semantics
are deferred to later designs.

Stale or reused PID handling:

- stale dead PID -> clear/mark stopped with bounded last error;
- PID reused by a foreign process -> `unknown` or `stale_pid`, no signal;
- identity uncertain -> `unknown`, no signal;
- manually started `llama-server` -> never adopted and never killed in v1.

### Port Handling

- `port` is numeric, bounded, and profile-allowed. Default v1 allowed range is
  `1024-65535`; privileged ports are rejected unless a later design explicitly
  allows them.
- Start preflights port availability on the host before spawn.
- If another process already listens on the requested port, return
  `port_in_use`; do not adopt it.
- If a manually started `llama-server` is already on `8080`, companion start
  fails with `port_in_use`. The Phase 1/Ask local-provider status may still show a
  reachable manual server; the Local Models UI must distinguish that from a
  companion-managed server.
- If the child later reports address-in-use, surface `port_in_use`, stop/clean up
  only the child just spawned, and leave no misleading running state.

### Logs

- Companion captures stdout/stderr to a bounded companion-owned log file with
  non-world-readable permissions.
- Log retention is bounded by size and/or rotation count.
- No unbounded streaming log endpoint in first implementation.
- Logs are not returned unless an explicit future troubleshooting field requests
  a bounded tail.
- Returned log tails must redact tokens, Authorization headers, raw API keys,
  full URLs with credentials, socket paths, and absolute model paths where
  possible.

### Health Checks

- After start, the companion polls from the host:
  `http://127.0.0.1:<port>/v1/models` or a documented equivalent health endpoint.
- Health success moves state to `running`.
- Timeout moves state to `crashed` or `error`; if the companion just started the
  child, it stops only that child after identity verification.
- The backend still uses the configured local-provider base URL for actual app
  generation and Ask. Companion status is operational state, not the Provider
  Settings source of truth unless a later confirmed flow changes that.

### Backend Bridge Contract for Phase 2G

```text
GET  /api/local-model/server/status
POST /api/local-model/server/start
POST /api/local-model/server/stop
POST /api/local-model/server/restart
```

Phase 2G3 implements these backend routes. They use the same Phase 2C bridge
configuration: server-side `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and
optional `LMM_COMPANION_TIMEOUT_SECONDS`.

Backend rules:

- Reads companion token/socket config server-side only.
- Uses a stdlib Unix-socket HTTP client with bounded timeout/body size.
- Sends `Authorization: Bearer <token>` only server-side.
- Forwards only typed payloads matching the companion contract:
  `model_id`, `profile_id`, `parameters.port`, `parameters.ctx_size`,
  `parameters.gpu_layers`, `parameters.threads`, `grace_seconds`, or
  `reuse_last`.
- Rejects unknown top-level fields and unknown parameter fields with safe
  `bad_request` DTOs before opening the companion socket.
- Redacts and whitelists companion responses before returning them to the
  frontend.
- Returns safe normalized errors:
  `companion_config`, `companion_offline`, `companion_auth`,
  `companion_timeout`, `companion_error`, `bad_request`, `not_running`,
  `already_running`, `unknown_model`, `unknown_profile`, `invalid_parameters`,
  `port_in_use`, `process_start_failed`, `process_stop_failed`,
  `stale_process`, and `process_error`.
- Never accepts free-form command args, shell strings, executable paths, raw model
  paths, environment blocks, or arbitrary flags.
- Never exposes the companion token, socket path, Authorization header, raw host
  paths, raw argv, pid, executable path, private model path, full URLs,
  tracebacks, low-level socket details, or raw companion connection details.
- Does not write Provider Settings unless a later explicit confirmed slice adds
  that behavior.
- Does not change Ask.
- Does not change the local provider base URL/model or write any provider config.
- Does not call subprocess, shell, Docker, or host process APIs.

### UI Contract for Phase 2G

Implemented Phase 2G4 Local Models UI controls:

- Start selected model.
- Stop managed server.
- Restart managed server.
- Show `running`, `stopped`, `starting`, `stopping`, `crashed`, `unknown`, and
  error states.
- Explain port conflicts, including the case where a manual server is already
  running separately from the companion-managed server.
- Explain companion missing/offline/auth-failed states.
- Keep the manual command fallback.
- Explicitly warn that Stop affects only the companion-managed server.
- Disable Start when no selected model exists.
- Disable controls when the companion is unavailable.
- Build start/restart payloads from the saved selected library model and fixed
  typed defaults only: `model_id`, `profile_id: "fake_test"`, and
  `parameters.port`, `parameters.ctx_size`, `parameters.gpu_layers`,
  `parameters.threads`.
- Label `fake_test` as validation/test profile only.
- No free-form flags UI in v1.
- No raw host path, token, socket path, or Authorization display.
- No Provider Settings write unless a later explicit confirmed slice adds it.

### Required Test Plan for Phase 2G

Future implementation must include tests for:

- companion start success with a fake executable or safe test process;
- start rejects unknown model id;
- start rejects a model outside an approved root;
- start rejects invalid profile;
- start rejects invalid parameters;
- start rejects port in use;
- start while running returns `already_running`;
- stop stops a tracked process;
- stop does not kill a foreign PID;
- stale PID is not killed;
- restart validates previous metadata before `reuse_last`;
- logs are bounded and redacted;
- auth is required;
- backend redacts token/socket/paths;
- UI contains no raw path/token/socket display;
- no shell/subprocess free-form args are accepted;
- no Provider Settings write;
- no Ask change;
- no Docker privileged mode, host PID namespace, or Docker socket.

### Explicit Non-Goals for Phase 2F

- No implementation.
- No process-control code.
- No backend routes.
- No frontend UI.
- No Docker changes.
- No `llama-server` launch.
- No Provider Settings write.
- No Ask change.
- No hosted/cloud Ask.
- No model download manager.
- No multi-server pool.
- No Windows/macOS process implementation.

## 19. Phase 2G1 Companion Process Internals

Phase 2G1 implements only companion-private lifecycle primitives. The app cannot
start or stop models from the backend or frontend yet.

Added internals:

- `tools/local_model_companion/profiles.py` defines typed, bounded launch
  profiles and the explicit `fake_test` profile constructor used by tests.
- `tools/local_model_companion/process_manager.py` defines
  `ManagedServerProcessManager`, `start_managed_server`,
  `stop_managed_server`, and `get_managed_server_status`.
- The manager resolves selected model ids against approved-root GGUF library
  records, re-canonicalizes the root-relative model path, and rejects unknown
  models or paths outside the approved root.
- The manager validates executable paths from companion/test config, checks that
  the file exists and is executable, builds argv arrays only, and launches with
  `subprocess.Popen(..., shell=False)`.
- Process state is stored in a companion-owned runtime directory as
  `managed_server_state.json` via atomic replace. Active state includes version,
  pid, model id, root id, profile id, port, typed params, `started_at`,
  executable path/fingerprint metadata, Linux process start ticks, private model
  path, redacted argv metadata, status, last error, and log path. It stores no
  token.
- Linux `/proc` checks verify PID existence, zombie/dead state, process start
  ticks when available, and command/executable identity before status reports or
  stop signals. Foreign or uncertain PIDs are not killed.
- Logs are written to `managed_server.log` with non-world-readable permissions
  where practical. Safe DTOs expose only a bounded, redacted tail.

Phase 2G1 validation uses only a temporary fake Python executable created by the
test. It stays alive, prints predictable output including redaction bait, handles
termination, and is cleaned up by the test harness. No real `llama-server` is
launched.

Explicit non-goals preserved in Phase 2G1:

- No FastAPI backend start/stop/restart routes.
- No frontend UI.
- No Docker Compose changes.
- No Provider Settings writes.
- No Ask changes.
- No backend bridge start/stop.
- No companion HTTP `/server/start`, `/server/stop`, or `/server/restart`
  endpoints.
- No real `llama-server` launch.
- No shell execution or free-form command args.
- No host-gateway TCP, Docker socket, privileged container, or host PID
  namespace.

## 20. Phase 2G2 Companion HTTP Process API

Phase 2G2 exposes the Phase 2G1 process manager through the host companion's own
Unix-socket HTTP API only. The Docker FastAPI backend and React frontend still do
not have start/stop/restart routes or controls.

Added companion-local endpoints:

- `GET /server/status`
- `POST /server/start`
- `POST /server/stop`
- `POST /server/restart`

All four endpoints use the existing companion bearer token auth and the existing
Unix-domain-socket `BaseHTTPRequestHandler` server. The handlers parse bounded
JSON request bodies, reject unknown top-level fields with `bad_request`, and
delegate lifecycle operations to `ManagedServerProcessManager`. The HTTP handler
code does not call `subprocess.Popen`.

Request shapes:

```json
{
  "model_id": "opaque-model-id",
  "profile_id": "fake_test",
  "parameters": {
    "port": 8123,
    "ctx_size": 4096,
    "gpu_layers": 0,
    "threads": 2
  }
}
```

```json
{
  "grace_seconds": 5
}
```

```json
{
  "reuse_last": true
}
```

`restart` prefers the explicit start payload. `reuse_last` is allowed only when
prior launch metadata exists in the companion process and can still be validated.

Safe response DTOs expose only:

- `ok`
- `state`
- `managed`
- `model_id`
- `profile_id`
- `port`
- `started_at`
- `error`
- bounded/redacted `log_tail`

Responses must not expose the companion token, socket path, absolute model path,
executable path, raw argv, full command line, Authorization header text, or full
URLs. Corrupt process state files return safe status/error DTOs instead of
tracebacks.

Companion config now supports optional process manager configuration:

```json
{
  "approved_roots": [],
  "token": "test-token",
  "process_runtime_dir": "/tmp/lmm-companion-runtime",
  "profiles": {
    "fake_test": {
      "executable": "/tmp/fake_server.py"
    }
  }
}
```

There is still no default real executable and no default real `llama-server`
profile. If profiles are configured without an explicit runtime dir, the runtime
dir is safely derived beside the explicit config file.

Phase 2G2 validation uses only a fake executable profile and fake `.gguf` files
under temp approved roots. The focused process API test starts the real companion
handler path where possible; in this sandbox Unix socket and TCP socket creation
are denied, so it falls back to in-memory handler dispatch and monkeypatches only
the test process manager's port probe. Production code still uses the Unix socket
server and real port availability check.

Explicit non-goals preserved in Phase 2G2:

- No FastAPI backend server status/start/stop/restart routes.
- No frontend start/stop/restart UI.
- No Docker Compose changes.
- No Provider Settings writes.
- No Ask changes.
- No backend bridge start/stop.
- No real `llama-server` validation or launch profile.
- No host-gateway TCP, Docker socket, privileged container, or host PID namespace.
- No shell execution or free-form command args.

## 21. Phase 2G3 Backend Process Bridge

Phase 2G3 implements only the Docker FastAPI backend bridge to the companion's
existing process endpoints. It adds no frontend UI and no Docker/Provider
Settings/Ask/runtime configuration changes.

Backend routes:

- `GET /api/local-model/server/status`
- `POST /api/local-model/server/start`
- `POST /api/local-model/server/stop`
- `POST /api/local-model/server/restart`

The bridge extends `pipeline/local_model_companion_client.py` instead of adding a
second transport. It uses the Phase 2C server-side companion configuration:
`LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and optional
`LMM_COMPANION_TIMEOUT_SECONDS`. All calls use the stdlib Unix-socket HTTP
client, include the bearer token only server-side, enforce bounded timeout/body
size, and normalize socket/auth/timeout/malformed-response failures to safe
categories.

Request validation is backend-side and typed:

- Start accepts only `model_id`, `profile_id`, and `parameters`.
- Start parameters accept only `port`, `ctx_size`, `gpu_layers`, and `threads`
  with bounded integer values matching the fake test profile.
- Stop accepts only `grace_seconds`, bounded from 0 to 30.
- Restart accepts either the explicit start payload or `{ "reuse_last": true }`.
- Unknown top-level fields, unknown parameter fields, executable paths, model
  paths, command strings, args arrays, shell flags, environment blocks, and other
  free-form values are rejected before any companion socket request is sent.

Response validation is also backend-side. The frontend receives only:

- `ok`
- `configured`
- `reachable`
- `state`
- `managed`
- `model_id`
- `profile_id`
- `port`
- `started_at`
- `error`
- `log_tail`

The bridge drops or redacts companion `pid`, params, executable/private model
paths, raw argv, raw socket paths, bearer tokens, Authorization headers, full
URLs, tracebacks, low-level socket details, and absolute host paths. Companion
process categories are mapped into the allowed frontend-safe set:
`not_running`, `already_running`, `unknown_model`, `unknown_profile`,
`invalid_parameters`, `port_in_use`, `process_start_failed`,
`process_stop_failed`, `stale_process`, and `process_error`; bridge failures use
`companion_config`, `companion_offline`, `companion_auth`, `companion_timeout`,
`companion_error`, or `bad_request`.

Explicit non-goals preserved in Phase 2G3:

- No frontend start/stop/restart UI.
- No Docker Compose changes or permanent companion socket mount.
- No Provider Settings writes.
- No Ask changes.
- No local provider base URL/model change.
- No real `llama-server` validation.
- No direct Docker host process control.
- No direct Docker host filesystem scanning.
- No host-gateway TCP, Docker socket, privileged container, or host PID namespace.
- No subprocess, shell execution, Docker commands, or host process APIs in the
  backend bridge.
- No free-form command args.
- No raw companion token/socket path/absolute host path/Authorization/full
  URL/raw argv exposure.

New validation:

- `test_scripts/test_local_model_companion_process_bridge.py` covers
  unconfigured/offline/auth/timeout/malformed companion states, successful fake
  Unix-socket requests, Authorization header presence server-side, safe
  start/stop/restart payload forwarding, redaction, validation rejection before
  socket forwarding, route registration, no Provider Settings writes, no Ask
  changes, no frontend start/stop UI/routes, and no backend subprocess/shell/
  direct host control.
- Existing Phase 2C, 2E, and 2G2 tests were updated so their historical
  no-backend-route assertions now recognize the Phase 2G3 bridge while preserving
  their original safety boundaries.

## 22. Phase 2G4 Local Models Managed-Server UI

Phase 2G4 implements only the frontend/client controls for the Phase 2G3 backend
bridge. It adds no backend routes and no host/runtime/Docker behavior.

Frontend API helpers:

- `getLocalModelServerStatus()` calls `GET /api/local-model/server/status`.
- `startLocalModelServer(payload)` calls `POST /api/local-model/server/start`.
- `stopLocalModelServer(payload)` calls `POST /api/local-model/server/stop`.
- `restartLocalModelServer(payload)` calls
  `POST /api/local-model/server/restart`.

The Local Models panel now includes a **Managed Server** section. On load it
fetches managed server status alongside existing companion/library/selection
state. It keeps the selected-model preview and manual command helper fallback
visible. It renders companion unconfigured/offline/auth failed states, no saved
selected model, stopped/running/already-running/not-running/unknown-style server
states, and safe error categories including port conflict, invalid params,
unknown model/profile, companion offline, and auth failure.

Start and restart use an explicit safe payload built from the saved selected
library model id plus fixed typed defaults only:

```json
{
  "model_id": "saved-selected-library-model-id",
  "profile_id": "fake_test",
  "parameters": {
    "port": 18080,
    "ctx_size": 2048,
    "gpu_layers": 0,
    "threads": 2
  }
}
```

Stop sends only:

```json
{ "grace_seconds": 5 }
```

The UI labels `fake_test` as a validation/test profile only. It does not expose
editable process flags, executable paths, model paths, commands, raw argv,
arbitrary JSON, tokens, socket paths, Authorization headers, or raw absolute
paths. Stop/restart are enabled only when status indicates a companion-managed
running server. The section copy states that it controls only the companion-
managed test/server process, manual servers are not stopped by the button, and
Provider Settings are not changed.

Explicit non-goals preserved in Phase 2G4:

- No backend route additions.
- No direct companion calls from the frontend.
- No Docker Compose changes.
- No Provider Settings writes.
- No Ask changes.
- No local provider base URL/model behavior change.
- No real `llama-server` validation.
- No host-gateway TCP, Docker socket, privileged container, or host PID
  namespace.
- No browser localStorage/sessionStorage.
- No free-form command args UI or arbitrary JSON editor.
- No `dangerouslySetInnerHTML`.
- No token/socket/raw absolute path/raw argv exposure in UI.

Validation added/updated:

- `frontend/scripts/verify-local-model-library.mjs` now asserts the new API
  helper paths/methods, allowed-only start payload fields, disallowed unsafe
  payload fields, disabled start without saved selected model, manual command
  helper fallback, companion-managed-only stop copy, no Provider Settings/Ask
  calls, no browser storage, no raw HTML rendering, no token/socket/
  Authorization strings in UI source/fixtures, no raw absolute path rendering,
  and managed status/error normalization.

## 23. Phase 2G5 Real Linux llama-server Validation And Hardening

Phase 2G5 implements Linux-first real-runtime support behind explicit companion
config while preserving the Phase 2G safety boundary. Real launch is opt-in only:
there is no default runnable real profile and no frontend/backend request can
supply an executable path, model path, host, shell command, or free-form args.

Configured real profiles:

- `llama_cpp_gpu_default`
- `llama_server_gpu_default`

Example explicit companion config:

```json
{
  "approved_roots": [
    { "id": "models", "path": "/home/user/models", "recursive": true }
  ],
  "token": "local-test-token",
  "process_runtime_dir": "/tmp/lmm-companion-runtime",
  "profiles": {
    "llama_cpp_gpu_default": {
      "executable": "/home/user/llama.cpp/build/bin/llama-server",
      "host": "0.0.0.0",
      "default_parameters": {
        "port": 8080,
        "ctx_size": 8192,
        "gpu_layers": 999,
        "threads": 8
      }
    }
  }
}
```

Real profile argv is centralized in `tools/local_model_companion/profiles.py`:

```text
<configured-llama-server>
  -m <resolved-approved-model-path>
  --host <configured-safe-host>
  --port <port>
  -c <ctx_size>
  -ngl <gpu_layers>
  --threads <threads>
```

Lifecycle semantics:

- `starting` means the child process was spawned and persisted, but readiness has
  not succeeded.
- `running` means host-side readiness polling succeeded against
  `http://127.0.0.1:<port>/v1/models`.
- `error` means validation, launch, or readiness failed safely.
- `crashed` means the tracked process exited unexpectedly or before readiness.
- Launch failures record stable state and do not auto-restart; the user/operator
  must explicitly start again.

Process safety:

- Real/fake launches use `subprocess.Popen(..., shell=False,
  start_new_session=True)`.
- Stop targets only the tracked process group after PID identity checks.
- Linux `/proc` checks include PID existence, zombie state, executable/cmdline
  match, process start ticks, and process group id where recorded.
- Foreign/reused/uncertain PIDs are not killed.
- If the companion dies while a child survives, persisted state lets a restarted
  companion verify identity before status/stop. Without verifiable state, it does
  not adopt or kill foreign processes.

Error/log handling:

- stdout/stderr are captured to a companion-owned bounded log file.
- API log tails are bounded and redacted.
- Safe categories include `executable_missing`, `permission_denied`,
  `port_in_use`, `model_load_failed`, `model_may_be_too_large`,
  `readiness_timeout`, `process_start_failed`, and `process_crashed`.
- API/backend/frontend DTOs must not expose tokens, Authorization headers,
  socket paths, full URLs with credentials, absolute host model paths, raw argv,
  executable paths, or unbounded logs.

Backend/frontend behavior:

- Backend `/api/local-model/server/*` routes pass through only whitelisted states
  and categories.
- The frontend displays new states/error copy but still uses the Phase 2G4
  fake-safe managed-server UI payload. It does not add advanced flags UI and does
  not write Provider Settings.
- A tiny backend transport seam exists, but Linux Unix socket remains the only
  implemented companion transport. Host-gateway TCP and named pipes remain
  deferred.

Live validation harness:

- `test_scripts/validate_lmm_real_llama_server.py`
- Required env: `LMM_REAL_LLAMA_SERVER_BIN`, `LMM_REAL_MODEL_ROOT`, and
  `LMM_REAL_MODEL_ID` or `LMM_REAL_MODEL_PATTERN`/`LMM_REAL_MODEL_FILENAME`.
- Optional env: `LMM_REAL_PORT`, `LMM_REAL_CTX_SIZE`,
  `LMM_REAL_GPU_LAYERS`, `LMM_REAL_THREADS`, `LMM_REAL_READINESS_TIMEOUT`.
- Missing env skips with exit 0.
- When configured, it starts a temporary companion over a Unix socket, scans the
  approved root, starts real `llama-server`, verifies `/v1/models`, checks
  status, stops, verifies port release and redaction, and cleans up.

Explicit non-goals preserved in Phase 2G5:

- No Provider Settings writes.
- No Ask changes.
- No permanent Docker Compose changes.
- No host-gateway TCP, Docker socket, privileged container, or host PID
  namespace.
- No browser storage.
- No automatic restart loop.
- No model download manager.
- No multi-server pool.
- No Windows/macOS process support.
- No Ollama/simple-local-model path in this slice.

Next recommended slice is operator-run live `llama-server` validation using the
new harness, then a design pass for exposing configured real profiles in UI only
if that can preserve the no-free-form-args and no-Provider-Settings-write
boundaries.
