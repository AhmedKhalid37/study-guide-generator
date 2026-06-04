# LOCAL_MODEL_MANAGER_DESIGN.md — Manage local OpenAI-compatible model servers

> **Status: DESIGN-FIRST (LMM Slice 1). No code written.** This document is the
> design for a *Local Model Manager* (LMM) — a feature that helps the operator run
> and use a local OpenAI-compatible model server (llama.cpp / `llama-server`) from
> inside the Study Guide Generator. It is a **separate feature** from in-app
> Provider Settings (which is COMPLETE through Slice 5). For the live per-slice log
> see `CURRENT_TASK.md`; for the "why" behind choices see `DECISIONS.md`; for the
> stable overview see `PROJECT_CONTEXT.md`; the canonical brief is `../CLAUDE.md`.
>
> **Hard constraint that shapes the whole design:** the backend runs **inside a
> non-root Docker container** as `appuser` (uid **10001**), behind
> `no-new-privileges:true`. A local `llama-server` the operator wants to manage
> runs on the **host**, reached today at `http://host.docker.internal:8080/v1`.
> A container process **cannot reliably or safely** start/stop a host process —
> that crosses the container↔host boundary. The recommendation below is therefore
> **detection-first**, with process control deferred to an explicit, optional
> host-side companion.

---

## 1. Current local-provider behavior (investigated, as built today)

All findings below are from reading the live code (no code changed).

### 1.1 How `local` is configured
- `local` is a first-class provider in the registry alongside `deepseek` and
  `qwen` (`pipeline/provider_config.py`). Aliases (`PROVIDER_ALIASES`) map
  `local` / `Local` / `Local llama.cpp` / `Local OpenAI-compatible` / `llama.cpp`
  → the canonical id `local`. Its `kind` is `"local"` (cloud providers are
  `"cloud"`); display name is **"Local llama.cpp"**.
- It is configured through the **same** settings-store → env → built-in chain as
  every provider. The effective resolvers are:
  - **base URL** — `_effective_base_url("local")` = store `base_url` →
    `LOCAL_LLM_BASE_URL` → `LLM_BASE_URL` → **(no built-in default)**.
  - **api key** — `_effective_api_key("local")` = store secret →
    `LOCAL_LLM_API_KEY` → `LLM_API_KEY` → the literal **`"local"`** (a
    placeholder, *not* a real secret; see §7).
  - **default model** — `_effective_default_model("local")` = store
    `default_model` → `LOCAL_LLM_MODEL` → `LLM_MODEL` → **(none)**.
- The built-in constant `LOCAL_LLM_BASE_URL = "http://host.docker.internal:8080/v1"`
  exists but is **not** wired into `_env_base_url("local")` as a fallback — so a
  local provider with **no** configured base URL resolves to `None` and is
  treated as **not configured**. (Contrast: deepseek/qwen have built-in base-URL
  defaults.) `docker-compose.yml` adds `extra_hosts: host.docker.internal:host-gateway`
  so the container *can* reach a host server once a base URL is set.

### 1.2 How the base URL is resolved
- Single chain `_effective_base_url("local")` (above), used identically by the
  registry entry, `build_provider_config`, the provider-settings public view, and
  fetch-models. There is no second code path.

### 1.3 How `/api/options` discovers local models
- `GET /api/options` calls `get_provider_registry()` (default `discover_local=True`).
- `_local_entry(discover=True)` resolves the base URL and, **if a base URL is set**,
  calls `_discover_openai_models(base_url, api_key=…)` which does a **GET
  `{base_url}/models`** with a **1.5 s** timeout. Returned ids are sorted/deduped,
  merged with any store `custom_models`, and the first becomes the default model if
  none is configured.
- `configured` is `True` **only when** a base URL **and** a default model both
  resolve. If a base URL is set but no model is found/configured, `configured` is
  `False` and `discovery_error` is set (e.g. `"LOCAL_LLM_MODEL is required when
  using a local provider."`).

### 1.4 How fetch-models handles local
- `POST /api/provider-settings/local/fetch-models` → `fetch_provider_models("local")`
  → the **same** `_discover_openai_models` against the resolved base URL with a
  **10 s** fail-fast timeout (`PROVIDER_FETCH_MODELS_TIMEOUT`). It is **read-only**
  (no job, no artifacts) and **does not persist** the discovered ids — staging into
  `custom_models` + an explicit Save is a separate UI step. The response schema is
  `{provider, ok, models, source, base_url_host, error}` where `error` is `null` or
  `{category, message}`. The raw key never appears; the base URL is collapsed to
  host-only in any error string.

### 1.5 What happens when local is offline
- **`/api/options`:** discovery fails inside `_discover_openai_models`; the
  `except (OSError, URLError, JSONDecodeError)` returns `([], str(exc))`. The local
  entry comes back `configured:false`, `available_models:[]` (unless a default
  model is configured), and `discovery_error` carries the (host-collapsed) reason.
  The page still loads — discovery never raises.
- **A special guard:** if the base URL host is `host.docker.internal` **and**
  `/.dockerenv` does **not** exist (i.e. running **outside** Docker, e.g. local
  dev), discovery short-circuits with
  *"host.docker.internal is only reachable from Docker; start the app in Docker or
  use localhost for local development."*
- **fetch-models:** returns `ok:false` with a classified `error` (see §1.6).
- **A real generation against an offline local server:** the OpenAI client raises a
  connection error; `pipeline/errors.classify_exception` maps
  `APIConnectionError` / `ConnectionRefusedError` → category **`local_offline`** with
  the message *"Local model server at {base_url} is offline — start llama-server or
  choose a hosted provider."*

### 1.6 Error category / message used for local offline
- The canonical category set (`pipeline/errors.py:VALID_CATEGORIES`) includes
  **`local_offline`**. Two surfaces produce it:
  - **Generation path:** `classify_exception(...)` → `("local_offline", "Local
    model server … is offline — start llama-server or choose a hosted provider.")`.
  - **fetch-models path:** `_classify_fetch_error(...)` returns `"local_offline"`
    when the discovery error mentions `host.docker.internal`; other connection
    failures classify as `provider_network` there. (Note the slight asymmetry: the
    generation path uses `local_offline` for any connection refusal, while
    fetch-models reserves `local_offline` for the docker-host hint and otherwise
    says `provider_network`. The LMM status endpoint, §4, should normalize to a
    **single** `local_offline` category for connection failures.)

**Takeaway:** everything the detection-only LMM needs already exists server-side —
base-URL resolution, `/models` discovery, redaction, and a `local_offline`
category. The LMM Phase 1 is largely a **presentation + status-shaping** layer over
existing primitives, not new infrastructure.

---

## 2. Architecture options

### Option A — Detection-only manager (recommended first slice)
- The app **never** starts/stops processes. It:
  - resolves + displays the configured base URL (host-only),
  - probes reachability and fetches `/v1/models`,
  - shows status/latency/model list/errors,
  - shows a **copy-able "how to start `llama-server`" command** the operator runs
    **themselves on the host**.
- **Pros:** zero container-boundary crossing; no root/host privileges; no new
  dependencies; no GPU packaging; reuses the existing local provider +
  fetch-models; immediate UX value (clear "is it up?", "what models?", "how do I
  start it?"). Fully inside the current security model.
- **Cons:** the operator still launches the server by hand. (Acceptable — it is a
  single-operator tool.)

### Option B — Host-side companion launcher (optional, later)
- A **separate, tiny host program** (script or daemon) runs **outside** Docker,
  under the operator's own account, and exposes a **localhost-only**, **token-
  authenticated** control API. The app's backend calls the companion to
  start/stop/restart `llama-server` with **whitelisted** flags.
- **Pros:** real process control without giving the container host privileges; the
  privilege boundary stays where the OS already trusts it (the host user);
  GPU/driver access is the host's, not the container's.
- **Cons:** more moving parts (install/run/version the companion); a new
  localhost control surface that **must** be authenticated and command-whitelisted;
  cross-platform packaging (Linux/macOS/Windows). Design only in this doc; build
  only after explicit sign-off.

### Option C — In-container `llama-server`
- Bundle and run `llama-server` **inside** the app container.
- **Pros:** the backend can manage a process in its **own** namespace (no boundary
  crossing for control).
- **Cons (heavy):** **GPU passthrough** into Docker is platform-specific and often
  unavailable (NVIDIA Container Toolkit / ROCm / none on macOS); **model files**
  must be mounted (large bind mounts, path/permission management under uid 10001);
  **image size** balloons (CUDA/ROCm runtimes are gigabytes); CPU-only inference in
  a memory-limited container (`mem_limit: 2g`, `pids_limit: 256`) is too slow to be
  useful for real models; conflicts with the current lean, same-origin image. **Not
  recommended** as the default; could be an *opt-in* "CPU-only experiment" image
  variant far later, documented but not built.

### Option D — Direct backend process spawn (host) — **REJECTED**
- The backend (inside Docker, uid 10001, `no-new-privileges`) tries to spawn a
  **host** `llama-server`.
- **Why this fails / is unsafe:**
  - A container process cannot launch a process in the **host** PID namespace
    without escape mechanisms (mounting the Docker socket, `--privileged`,
    host PID namespace) — each of which **destroys the security model** (a
    container with the Docker socket is effectively root on the host).
  - `no-new-privileges:true` and the non-root user explicitly forbid privilege
    escalation; spawning host processes is the opposite of the hardening already
    shipped (`1d51b36`).
  - Even if it "worked" via a socket mount, building a host command line from
    user-supplied model paths/flags inside a privileged context is a **shell-
    injection + arbitrary-execution** catastrophe.
  - PID tracking, GPU access, and binary/model paths all refer to the **host**
    filesystem the container cannot see — so it is also **unreliable**, not just
    unsafe.
- **Verdict:** rejected. If process control is ever wanted, it goes through Option
  B (host companion), never Option D. This rejection is recorded in `DECISIONS.md`.

---

## 3. Recommended architecture — staged

**Phase 1 — Detection-only Local Model Manager (Option A).** Build first.
**Phase 2 — Optional host companion launcher (Option B), design then build.**
**Phase 3 — Optional packaged desktop/native flow** (an Electron/native wrapper
that runs the backend *and* the model server under one local user, sidestepping the
container boundary entirely) — far later, design only.

### Why Phase 1 first
- **No container-boundary process control** — nothing the container can't already
  do. It only makes HTTP calls it already makes.
- **No root/host privileges** — stays under uid 10001 + `no-new-privileges`.
- **No dependency / GPU packaging** — no CUDA/ROCm/llama-server in the image.
- **Reuses existing, proven primitives** — `_effective_base_url`,
  `_discover_openai_models`, the redaction helpers, and the `local_offline`
  category. Low risk, small surface.
- **Immediate UX benefit** — the operator gets a single place that answers "is my
  local server up?", "what models does it expose?", "what's the latency?", and
  "what command starts it?" — which today is scattered across the Providers page
  and env files.
- It also **de-risks** Phase 2: the status/contract/UX shaped here is exactly what
  a companion would feed, so Phase 2 becomes "add a control plane behind the same
  status view," not a redesign.

---

## 4. Backend API design for Phase 1 (detection-only)

**Decision: add a thin, read-only `local-model` namespace** rather than overloading
the provider-settings endpoints. Provider Settings *could* technically answer most
of this (its public view already exposes `base_url_host`, `available_models`,
`discovery_error`, `last_test`), but a dedicated namespace (a) keeps the LMM mental
model distinct from "edit my provider keys," (b) lets the status response be shaped
for *this* UI (reachability + latency + start instructions) without bending the
provider-settings DTO, and (c) gives Phase 2 a natural home. Config **writes**
(base URL, default model) still go through the **existing**
`PATCH /api/provider-settings/local` — the LMM does **not** introduce a second
writer for provider config.

### 4.1 Endpoints (all read-only in Phase 1)
```
GET  /api/local-model/status
  → current resolved status WITHOUT a live network probe where possible
    (fast; uses the last known/registry view). Safe to call on page open.

POST /api/local-model/check
  → actively probe the configured base URL: a reachability + latency measurement
    (and a /models fetch). Fail-fast timeout (~10 s). This is the "Refresh" action.

POST /api/local-model/fetch-models   (OPTIONAL — may simply reuse the existing
  POST /api/provider-settings/local/fetch-models, which already does exactly this)
```
> **Recommendation:** implement `status` + `check`; for model listing **reuse** the
> existing provider-settings `fetch-models` rather than duplicate discovery. If a
> dedicated `/api/local-model/fetch-models` is added, it must be a thin delegate to
> `fetch_provider_models("local")` — never a second discovery implementation.

### 4.2 Status response — safe fields only
```jsonc
{
  "base_url_host": "host.docker.internal",   // HOST ONLY — never scheme+port+userinfo? see note
  "base_url_present": true,                   // is a base URL configured at all
  "in_docker": true,                          // /.dockerenv present (affects host.docker.internal advice)
  "reachable": false,                          // did the probe connect?
  "latency_ms": null,                          // round-trip ms, or null if not probed/unreachable
  "models": [],                                // discovered model ids (may be empty)
  "model_count": 0,
  "default_model": null,                       // resolved default (store→env), may be null
  "selected_model": null,                      // same as default in Phase 1 (no per-LMM selection yet)
  "configured": false,                         // base URL AND a usable model both resolve
  "error": { "category": "local_offline",      // normalized category (see §1.6)
             "message": "Local model server is offline — start llama-server (see command below)." },
  "instructions": {                            // shown when offline / unconfigured
    "summary": "Start a local llama.cpp server, then click Refresh.",
    "command_profile_id": "llama_server_default"   // points at a §9 command profile; UI renders it
  }
}
```
**Field rules (mandatory):**
- **No raw API key**, ever. The local key is the placeholder `"local"` or a
  user-set value — neither is returned.
- **No full base URL.** Expose `base_url_host` (host only) — never the scheme +
  port + path, and **never** userinfo. *(Open question for build time: the port can
  be useful for "is 8080 the right port?" troubleshooting and is not itself a
  secret. If we expose it, expose `base_url_host` + `base_url_port` as **separate
  scalar fields** derived via `urlparse`, never a reconstructed URL string, and
  still drop any userinfo. Decide in LMM Slice 2; default to host-only if unsure.)*
- **Error** uses the existing category vocabulary (`local_offline`,
  `provider_network`, `provider_auth`, `provider_model`, …) and a redacted,
  length-capped message — reuse `_safe_fetch_message` / `_redact_secret`.
- `status` should be cheap and non-probing (so the page opens fast); `check` does
  the network round-trip. Both go through `run_in_threadpool` like the existing
  test/fetch endpoints.

### 4.3 What is explicitly NOT in Phase 1
- **No** start/stop/restart endpoints. **No** process spawn. **No** PID. **No** log
  tailing of a process the container doesn't own. **No** file browsing. **No** GGUF
  path input. Those are Phase 2+ (and §8/§9 design them ahead of time).

---

## 5. Frontend UI design for Phase 1

A **Local Models** view (a sub-panel of the Providers page, or a sibling nav item),
designed to integrate with — not duplicate — the existing Providers page.

### 5.1 Layout (one screen)
```
┌─ Local Models ───────────────────────────────────────────────┐
│  ● Status: Offline            [ Refresh ]                      │
│  Base URL host: host.docker.internal   (port 8080)            │
│      └ Configure base URL → opens Providers ▸ Local            │
│  Latency: —    Models discovered: 0                            │
│                                                               │
│  ⚠ No local server reachable.                                 │
│     1. Make sure llama-server is running on your host.        │
│     2. Confirm the base URL/port match.                       │
│                                                               │
│  ▸ How to start llama-server            [ Copy command ]      │
│    llama-server -m <model.gguf> --host 0.0.0.0 --port 8080 …  │
│                                                               │
│  Discovered models:  (none — start the server and Refresh)    │
│                                                               │
│  Requirements: a GGUF model file + a llama.cpp build on the   │
│  host. The app talks to it over http://…:8080/v1.             │
│                                                               │
│  [ Start server ]  [ Stop server ]   (disabled — "Planned")   │
└───────────────────────────────────────────────────────────────┘
```
### 5.2 Components / behavior
- **Server status card** — colored dot (green reachable / amber configured-but-
  unreachable / grey not-configured), latency, model count. Driven by
  `GET /api/local-model/status`; **Refresh** calls `POST /api/local-model/check`.
- **Base URL display + edit link** — shows `base_url_host` (and port if §4.2 keeps
  it). It **does not edit** the base URL inline; a **"Configure base URL"** link
  navigates to **Providers ▸ Local**, which is the single writer. (Avoids two edit
  surfaces for one value.)
- **Refresh models** — lists discovered ids (reusing the existing local
  fetch-models). Review-only — selecting a default model still happens on the
  Providers page in Phase 1.
- **"How to start llama-server" helper** — renders a command from a §9 **command
  profile** with a **Copy command** button. The command is a **template the
  operator runs on their host**; the app never executes it.
- **Model requirements warning** — short note that a GGUF + llama.cpp build are
  needed on the host, and that quality/speed depend on the chosen model + hardware
  (manage expectations; see §12).
- **Offline state** — first-class: clear "not reachable," the troubleshooting
  steps, and the start command. Never a console error or a blank panel.
- **Port / base URL troubleshooting** — inline hint: "App is in Docker → it reaches
  the host at `host.docker.internal`; make sure llama-server binds `--host 0.0.0.0`
  (not `127.0.0.1`) so the container can reach it." (This is a real, common gotcha.)
- **Start/Stop buttons** — **either omitted** or rendered **disabled with a
  "Planned" tag** so the roadmap is visible without implying it works. No enabled
  control that does nothing.

### 5.3 Integration with Providers (no user confusion)
- Providers page = **credentials + base URL + default model + sampling/runtime**
  for *all* providers (cloud + local).
- Local Models page = **operational view of the local server only** (is it up,
  what models, how to start it). It **links back** to Providers for any config edit.
- A one-line cross-reference on each page points at the other, so the boundary is
  explicit. (See §12 "user confusion" risk.)

---

## 6. Model file (GGUF) management

- **Phase 1: do NOT browse local GGUF files.** The backend is in Docker; it cannot
  see host paths, and silently scanning a filesystem is both useless (wrong
  namespace) and a security smell. Phase 1 only references the model **by id** as
  returned from `/v1/models` (the running server already knows its loaded model).
- **The start-command helper** uses a **placeholder** (`-m <path-to-model.gguf>`);
  the operator fills in their own host path. The app never reads or validates that
  path in Phase 1.
- **Later (Phase 2, host companion):** the companion may scan a **single,
  user-approved model directory** (configured explicitly, e.g.
  `~/models`) and list `*.gguf` files there. **Never** scan arbitrary or
  app-supplied paths; never traverse outside the approved root (see §7/§8 path
  validation). Directory approval is an explicit operator action, not a default.
- **Never** scan arbitrary filesystem paths silently, in any phase.

---

## 7. Security model

Phase 1 inherits the existing, already-shipped guarantees and adds nothing risky:
- **No host process control in Phase 1.** Detection only.
- **No arbitrary shell commands.** The start command is a **display template**;
  the app never runs it.
- **No arbitrary file browsing.** No GGUF/path input reaches a filesystem call.
- **No raw key exposure.** The local "key" is the placeholder `"local"` (or a
  user-set value); it is never returned. All messages pass through
  `_redact_secret`. The status DTO has **no key field by construction** (mirrors
  the provider-settings redaction rule).
- **Base URLs with credentials are redacted to host (+ optional port) only** in the
  UI and in every error string — reuse `_base_url_host` (`urlparse().hostname`,
  which already drops userinfo/path/query). Never echo a reconstructed full URL.
- **Logs must be sanitized** — any status/probe message that could embed a URL or
  key is redacted + length-capped before it leaves the backend (reuse
  `_safe_fetch_message`). The frontend never receives raw transport errors.

**If a future host companion (Phase 2) exists, it MUST:**
- **bind only to localhost** (`127.0.0.1`), never `0.0.0.0`;
- **require a token or same-user access** — a shared secret the app holds (stored
  server-side, never sent to the frontend) **or** an OS-level same-user check;
- **only allow whitelisted commands + flags** — a fixed `llama-server` profile
  (§9), values validated/typed, **no free-form command string** ever accepted;
- **only access user-approved model directories** — a configured root, path-
  canonicalized, traversal-rejected (§8);
- **never expose arbitrary shell execution** — no `shell=True`, no string
  concatenation into a shell; spawn with an **argv array** only;
- treat its own control API as an **untrusted-input boundary** (whitelist parse,
  exactly like shortcut import).

---

## 8. Process lifecycle design (Phase 2/3 only — design ahead, not built)

For the host companion (Option B). None of this exists in Phase 1.
- **start / stop / restart semantics** — `start` spawns `llama-server` with a
  validated argv from a profile; `stop` signals the tracked PID (SIGTERM, then
  SIGKILL after a grace timeout); `restart` = stop-then-start with the same profile.
- **PID tracking** — companion records the spawned PID + the profile it launched
  with in a small state file under its own (host) state dir.
- **stale PID detection** — on startup/status, verify the PID is alive **and** is
  actually a `llama-server` (check the process command), not a recycled PID;
  treat a dead/foreign PID as "not running" and clear it.
- **log tailing** — capture the child's stdout/stderr to a host log file the
  companion owns; expose a **bounded, sanitized** tail (last N lines, redacted) —
  never the whole file, never unbounded streaming.
- **port conflict handling** — before start, check the port is free; if occupied,
  fail with a clear "port N in use" instead of spawning a doomed process. Detect
  "address already in use" on the child and surface it.
- **crash detection** — if the child exits unexpectedly, mark status `crashed`,
  surface the (sanitized) tail, and do **not** auto-restart loop (avoid restart
  storms); require an explicit restart.
- **command construction from a whitelist** — argv built **only** from a typed
  profile (§9); each value validated (enum/int/bounded); unknown keys dropped.
- **`llama-server` binary path validation** — the binary path is a companion-side
  config (operator-set), canonicalized + existence/execute-bit checked; not
  supplied by the app/frontend per request.
- **GGUF model path validation** — must resolve **inside** the approved model
  root after canonicalization (`realpath` + prefix check); reject symlinks
  escaping the root; reject `..` traversal.
- **GPU flag validation** — `--n-gpu-layers` is a bounded integer; flags come from
  the whitelist only; no raw GPU/driver strings passed through.
- **cancellation / timeout** — start has a readiness timeout (poll `/v1/models`
  until healthy or timeout → kill + report); stop has a grace timeout before
  SIGKILL.
- **multi-server vs single-server** — **start with single-server** (one managed
  `llama-server` at a time) — simpler PID/port/state model, matches the single-
  operator audience. Multi-server (a pool keyed by port) is a later possibility,
  not the first companion build.
- **Windows / Linux differences** — signals (`SIGTERM` vs `taskkill`), path
  separators, binary extension (`.exe`), and shell quoting differ; the companion
  abstracts a tiny per-OS process layer. argv-array spawning (no shell) sidesteps
  most quoting issues.
- **Docker vs native desktop** — in the Docker deployment the companion is a
  **separate host process** the app calls over localhost; in a future packaged
  desktop app (Phase 3) the same logic could live in the native wrapper running as
  the operator, removing the boundary. The control contract should be identical so
  the frontend doesn't care which backs it.

---

## 9. llama.cpp command profile (for the helper + future companion)

Do **not** hardcode one final command. Define a **profile schema**; the UI renders
a command from it, and a future companion validates an argv from it.

```jsonc
// command profile (display + future-launch). Values are typed + bounded.
{
  "id": "llama_server_default",
  "binary": "llama-server",          // operator-set on the host; placeholder in UI
  "args": {
    "model":        { "flag": "-m",              "type": "path",   "placeholder": "<model.gguf>" },
    "host":         { "flag": "--host",          "type": "string", "default": "0.0.0.0" },  // 0.0.0.0 so Docker can reach it
    "port":         { "flag": "--port",          "type": "int",    "default": 8080, "min": 1, "max": 65535 },
    "ctx_size":     { "flag": "--ctx-size",      "type": "int",    "default": 4096, "min": 256 },
    "n_gpu_layers": { "flag": "--n-gpu-layers",  "type": "int",    "default": 0,    "min": 0 },
    "threads":      { "flag": "--threads",       "type": "int",    "optional": true },
    "batch_size":   { "flag": "--batch-size",    "type": "int",    "optional": true },
    "ubatch_size":  { "flag": "--ubatch-size",   "type": "int",    "optional": true },
    "flash_attn":   { "flag": "--flash-attn",    "type": "bool",   "optional": true },  // presence-only flag
    "parallel":     { "flag": "--parallel",      "type": "int",    "optional": true },  // concurrent slots
    "chat_template":{ "flag": "--chat-template", "type": "string", "optional": true }   // only if model needs it
  },
  "endpoint": "/v1"   // llama-server exposes an OpenAI-compatible API under /v1
}
```
- The rendered helper command (Phase 1) substitutes placeholders and shows, e.g.:
  `llama-server -m <model.gguf> --host 0.0.0.0 --port 8080 --ctx-size 4096
  --n-gpu-layers 0`.
- **`--host 0.0.0.0`** is called out specifically because binding `127.0.0.1`
  makes the server unreachable from the Docker container (the #1 local-setup
  gotcha; see §5.2).
- The OpenAI-compatible endpoint is `{base_url}` ending in `/v1`; the app's existing
  `local` provider already targets `…/v1` and discovers models at `…/v1/models`.
- Multiple profiles can coexist later (e.g. `cpu_only`, `gpu_full_offload`); the
  schema is the contract, the specific values are not.

---

## 10. Relationship to "Ask Your Guide" chat (future, not implemented here)

- A future **Ask Your Guide** chat feature could run **local-only** to avoid API
  cost — it would depend on **local model availability** surfaced by the LMM status.
- If the local server is offline, chat shows a **first-class empty state** ("Local
  model offline — start it from Local Models") rather than erroring or silently
  failing — reusing the LMM status + the `local_offline` category.
- For a cost-control "local-only" mode, there is **no hosted fallback** — the user
  explicitly chose local; falling back to a paid provider would betray that intent.
  (A separate "use any provider" chat mode could fall back, but that is a different
  toggle.)
- **This design slice does not implement chat.** It only notes that LMM status is
  the dependency chat would read, so the status contract (§4.2) should stay stable
  and reusable.

---

## 11. Implementation slices

Each slice: **scope / files likely touched / tests / acceptance / non-goals.**

### LMM Slice 1 — docs / design only (THIS TASK)
- **Scope:** this design doc + doc reconciliation. No code.
- **Files:** `docs/LOCAL_MODEL_MANAGER_DESIGN.md` (new); `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md` (updated).
- **Tests:** docs-only diff; optional `python -m compileall api pipeline` (no code
  changed).
- **Acceptance:** design covers current behavior, options A–D, the staged
  recommendation, the Phase 1 API + UI, security, and the slice plan; `DECISIONS.md`
  records detection-first + the Option D rejection.
- **Non-goals:** any code, any endpoint, any UI.

### LMM Slice 2 — detection-only backend status endpoint (BACKEND ONLY)
- **Scope:** add read-only `GET /api/local-model/status` + `POST
  /api/local-model/check`. Reuse `_effective_base_url("local")`,
  `_discover_openai_models`, the redaction helpers, and the `local_offline`
  category. Normalize connection failures to a single `local_offline` category
  (§1.6). Add a `local_model` view function in `pipeline/provider_config.py` (or a
  thin new module) that returns the §4.2 DTO. **No** process control, **no** new
  writer for provider config.
- **Files likely touched:** `api/server.py` (2 routes), `pipeline/provider_config.py`
  (status builder reusing existing resolvers), possibly `pipeline/errors.py` (only
  if a shared normalizer helps — prefer not to widen the category set).
- **Tests:** a focused `test_scripts/test_local_model_status.py` — configured+
  reachable (mock/local stub), configured+offline → `local_offline`, no-base-URL →
  `base_url_present:false`/`configured:false`, out-of-docker `host.docker.internal`
  guard, and a **secret scan** of the response (no key, no full URL, no userinfo).
  Run in Docker (uid 10001); release smoke unchanged.
- **Acceptance:** both endpoints return the §4.2 shape with safe fields only; status
  is cheap/non-probing, check probes with a fail-fast timeout; no raw key / full URL
  ever appears; existing `/api/options` + provider-settings untouched.
- **Non-goals:** any UI; any start/stop; any persistence; any GGUF/path handling.

> **Slice 2 implementation note (DONE — branch `local-model-status-api`).** Built
> `GET /api/local-model/status` + a thin `POST /api/local-model/check` alias in
> `api/server.py` (registered before the SPA mount, via `run_in_threadpool`) backed
> by `get_local_model_status()` in `pipeline/provider_config.py`.
> - **One probing implementation, not the status/check split sketched in §4.1.** In
>   practice the operator opens the Local Models panel *specifically* to see live
>   state, so `status` **does** probe (fail-fast 10 s, reusing `_discover_openai_models`)
>   and `check` is a same-behavior alias for an explicit "Refresh" verb. This keeps a
>   single code path and a stable contract; if a truly cheap non-probing open is
>   wanted later it can read the registry view without changing the DTO.
> - **`ok` is decoupled from `reachable`** as §4.2 requires: `ok:true` means the
>   request succeeded; offline / no-base-URL / malformed-URL all return HTTP 200 with
>   `reachable:false` and a classified `error`, never a crash.
> - **DTO shipped** (superset of §4.2): `{ok, provider, configured, base_url_host,
>   base_url_configured, in_docker, reachable, models, model_count, default_model,
>   selected_model, latency_ms, error, actions, notes}`. `base_url_host` is **host
>   only** (no port — §4.2's optional `base_url_port` was **not** added; host-only is
>   the default the doc says to pick when unsure). `actions` carries
>   `open_provider_settings` (enabled) + `copy_start_command` (**disabled**, deferred
>   to Slice 4); `notes` surfaces the `--host 0.0.0.0` gotcha only when the host is
>   `host.docker.internal`.
> - **Error normalization (§1.6) realized** via `_classify_local_status_error`: every
>   connection failure (refused / timeout / DNS / out-of-Docker `host.docker.internal`
>   guard) → a single `local_offline`; auth/model errors keep their category; no base
>   URL → `provider_config`. Messages reuse `_safe_fetch_message` (key-redacted,
>   URL-collapsed, length-capped).
> - **Tests:** `test_scripts/test_local_model_status.py` (17/17), existing provider
>   fetch-models / settings-store / runtime-settings suites unchanged; release smoke
>   28/28; live offline proof + clean secret scan. **No** process control, file
>   browsing, writes, or new deps.

### LMM Slice 3 — Local Models status panel (FRONTEND)
- **Scope:** the §5 Local Models view consuming Slice 2 + the existing local
  fetch-models. Status card, base-URL host display + link to Providers, Refresh,
  discovered models, offline/troubleshooting states. Start/Stop omitted or
  disabled-"Planned".
- **Files likely touched:** a new `frontend/src/components/LocalModelsWorkspace.jsx`
  (or a Providers sub-panel), `frontend/src/api/client.js` (status/check helpers),
  nav wiring in `DesktopDashboard.jsx`.
- **Tests:** a node/esbuild harness for any pure status→badge mapping (mirroring
  `shortcutStatus.js` testing); live Chromium click-through (offline + reachable);
  served-bundle secret scan.
- **Acceptance:** offline shows a first-class state + start command + troubleshooting;
  reachable shows latency + model list; "Configure base URL" routes to Providers;
  no enabled control that does nothing; no raw key/URL in the bundle or network tab.
- **Non-goals:** any process control; inline base-URL editing (links to Providers).

> **Slice 3 implementation note (DONE — branch `local-model-status-ui`).** Built
> the read-only Local Models panel as a **sub-panel of the existing Providers
> (Models) page**, not a separate nav item — the §5.3 "operational view that links
> back to the single config writer" without a second top-level destination.
> - **API client:** `getLocalModelStatus()` (`GET /status`, page-open) +
>   `checkLocalModelStatus()` (`POST /check`, the "Refresh" verb) in
>   `frontend/src/api/client.js`, both via the existing `requestJson` — no body, no
>   write, no settings mutation.
> - **Pure helpers** in `frontend/src/localModelStatus.js` (mirrors
>   `shortcutStatus.js`): `localServerState` → `reachable | offline |
>   not_configured | error | unknown` (reachable wins; `base_url_configured:false`
>   or a `provider_config` category → not_configured; `local_offline` → offline;
>   any other classified error → error; not-reachable-with-no-info → a **calm
>   offline** default; missing/garbage status → unknown so an **old backend** with
>   no endpoint degrades gracefully). Plus `stateBadge` (label + CSS-agnostic
>   `tone`), `modelChips(limit=12)` (bounded list + overflow), latency/error/notes
>   accessors, `statusActions` (enabled **only** when explicitly `true`), and
>   `hasEnabledProcessControl` — the asserted invariant that no start/stop control
>   is ever enabled. All tolerate missing fields.
> - **Panel** (`LocalModelsPanel.jsx`): status pill, host-only base URL + in-Docker
>   flag, a 4-up metrics strip, selected-highlighted model chips with `+N more`
>   overflow, the redacted offline/error message, a first-class
>   offline/not-configured troubleshooting block (start server → confirm
>   `…/v1/models` → the `--host 0.0.0.0` Docker-host note → Refresh), backend
>   `notes`, the **Refresh status** button, an **Edit local provider settings** link
>   that scrolls the `#provider-card-local` card into view with a brief
>   `sg-card-flash` highlight (cosmetic CSS only), and the **disabled** "Copy start
>   command — Planned" chip from the backend `actions`. A failed status *request*
>   shows a calm "status unavailable" state, never a crash.
> - **Single writer preserved:** the panel never edits the base URL/model inline;
>   all config edits route to the Providers ▸ Local card.
> - **Tests:** `frontend/scripts/verify-local-model-status.mjs` (**47/47**, wired as
>   `npm run test:local-model-status`); `npm run build` OK; release smoke 28/28;
>   live offline proof + clean secret scan (no key in the served bundle, `/status`,
>   `/options`, `/provider-settings`, or container logs). **No** process control,
>   inline editing, raw key/URL, or new deps. The **Copy start command** stays
>   disabled — enabling it (with the §9 profile) is **Slice 4**.

### LMM Slice 4 — command-helper profiles / copy start command
- **Scope:** the §9 command-profile rendering + **Copy command** button (likely
  folded into Slice 3, or a thin follow-up). A small profile registry (backend or
  a static frontend table mirroring the schema) drives the displayed command.
- **Files likely touched:** `frontend/src/` (a `localModelProfiles.js` display
  table) and/or a backend profile constant if the profile should be server-owned.
- **Tests:** harness over the command-rendering function (placeholder substitution,
  bounded ints); copy-to-clipboard click-through.
- **Acceptance:** the rendered command is correct + copyable; `--host 0.0.0.0`
  guidance present; the app never executes it.
- **Non-goals:** any execution; any host file/path resolution.

### LMM Slice 5 — host companion launcher DESIGN (Option B)
- **Scope:** a dedicated design doc (`docs/LOCAL_MODEL_COMPANION_DESIGN.md`) for the
  host companion: localhost+token control API, whitelisted profile launch, PID/log/
  lifecycle (§8), approved model dir scan (§6), per-OS process layer. **Design only.**
- **Files:** new design doc + `DECISIONS.md` entry. No code.
- **Acceptance:** a buildable companion contract + threat model, explicitly sign-off-
  gated.
- **Non-goals:** any companion code.

### LMM Slice 6+ — host companion implementation (only if approved)
- **Scope:** build the companion + the backend client to it, behind a feature flag.
  Strictly per the Slice 5 design + §7/§8 security. Single-server first.
- **Non-goals:** multi-server pool; Windows packaging (later); auto-restart loops.

### Later — Ask Your Guide local-only chat integration
- Reads LMM status; first-class offline empty state; no hosted fallback in
  local-only mode. Separate feature; not started.

---

## 12. Risk analysis

| Risk | Mitigation |
| --- | --- |
| **Container can't reliably manage host processes** | Phase 1 never tries; process control is deferred to a host companion (Option B), never direct spawn (Option D rejected). |
| **GPU / CUDA / ROCm complexity** | Phase 1 needs no GPU packaging; the server runs on the host with the host's drivers. In-container GPU (Option C) is explicitly not the default. |
| **Shell injection** | No shell execution in Phase 1. The companion (later) uses argv arrays + a typed flag whitelist, never a free-form command string or `shell=True`. |
| **Path traversal / arbitrary file access** | No path input in Phase 1 (model referenced by id). The companion (later) canonicalizes + prefix-checks paths against a single approved model root. |
| **Exposing logs / secrets** | No key field by construction; URLs collapsed to host(+port) via `urlparse`; all messages redacted + length-capped (reuse `_redact_secret`/`_safe_fetch_message`); log tails (later) bounded + sanitized. |
| **Port conflicts** | Phase 1 surfaces "unreachable" + a port-troubleshooting hint. The companion (later) checks the port before start and reports "in use." |
| **Zombie / stale processes** | Companion (later) tracks PID + verifies it is a live `llama-server`; treats dead/foreign PIDs as not-running; no auto-restart storms. |
| **User confusion: Provider Settings vs Local Manager** | Single writer for config (Providers); LMM is operational/read-only and **links** to Providers; one-line cross-references on both pages; distinct nav labels. |
| **Overpromising local model quality/performance** | A requirements/expectations note in the UI (model + hardware dependent); no claims of parity with hosted models; CPU-only-in-Docker explicitly discouraged. |
| **`host.docker.internal` unreachable in some environments** | The existing out-of-Docker guard already explains it; UI calls out `--host 0.0.0.0` binding and the docker-host gateway. |

---

## 13. Recommendation

- **Build Phase 1 (detection-only, Option A) first** — it is safe, small, reuses
  existing primitives, and delivers immediate value with **zero** boundary-crossing.
- **Reject Option D** (direct Docker→host spawn) permanently; if process control is
  ever wanted, do it via a **host companion** (Option B) designed in LMM Slice 5,
  built only on explicit sign-off.
- **Do not build in-container `llama-server`** (Option C) as the default path.
- **Next implementation slice after this design: LMM Slice 2** — the detection-only
  backend status endpoint.

These choices are recorded in `DECISIONS.md`.
