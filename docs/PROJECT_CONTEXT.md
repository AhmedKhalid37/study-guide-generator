# PROJECT_CONTEXT.md — Stable Overview

> Stable, slow-changing context for any new session (Claude, ChatGPT, Codex).
> **Start here:** `NEXT_CHAT_HANDOFF.md` (one-page current-state handoff). For the
> live per-slice log see `CURRENT_TASK.md`; for the "why" behind choices see
> `DECISIONS.md`. The canonical project brief is `../CLAUDE.md`.
>
> **Trunk:** `chrome-renderer-v1` is the integrated trunk. Branch new work from it
> (currently `61fb423` or later) — never from the old consumed feature branches
> (see `DECISIONS.md` → "Consumed feature branches must not be re-merged").

---

## 1. What the app is

**Study Guide Generator** — turns course material (pasted text, uploaded
Markdown, or attachments) into clean, exam-focused study guides and renders them
to PDF, plus Markdown / HTML / DOCX artifacts. It also generates quizzes /
flashcards with CSV / Anki / Quizlet export.

- **Audience:** personal / small-group use. Single operator, not multi-tenant.
- **Intended UX:** a Claude-style desktop shell. The user picks a *style*
  (built-in, custom, or AI-generated) and/or a *generator preset*, optionally
  drafts an outline, generates, then manages results in a Library (folders) and
  an Exports center (per-job downloads + ZIP bundles). Recent Jobs and a Job
  Details drawer expose metadata, warnings, and downloads. The Home page offers
  customizable shortcuts.

## 2. Stack

- **Backend:** FastAPI — `api/server.py`. Defines all `/api/*` routes, then
  mounts the built frontend as a catch-all at `/`. The mount is registered
  **after** the API routes, so `/api/*` always wins over the SPA fallback.
- **Frontend:** React (Vite + Tailwind), built to `frontend/dist`, which the
  backend serves **same-origin**. One origin for UI + API.
- **Rendering pipeline (`pipeline/`):** Markdown sanitizer → LLM orchestrator →
  extraction/OCR → math validate/render → PDF/HTML/DOCX renderers.
  - **PDF rendering uses headless Chromium driven via Node** (not a Python HTML
    engine). This is load-bearing and tuned — do not rewrite casually.
  - **OCR uses Tesseract** for image-only PDFs.
  - Attachment extraction supports `.txt/.md/.csv/.tsv/.docx/.pptx/.pdf`.
- **Deployment:** Dockerized, same-origin, port **8000** (uvicorn
  `api.server:app` on `0.0.0.0:8000`). `frontend/dist` is built inside the
  image, never copied from host.

## 3. Providers

- **DeepSeek** and **Qwen** — verified-working providers. **Local llama.cpp** —
  supported via env/discovery; typically shows `configured: false` until a local
  server is set up.
- **Configurable in-app (provider settings, DONE through Slice 5
  `978516e`→`61fb423`).** Keys, base URLs, default models, custom models, and
  sampling/runtime defaults (`timeout_seconds`/`retry_count`/`thinking_default`)
  can be set from the **Providers** page instead of hand-editing `.env`. Backed by
  a two-file server-side store: `config/provider_settings.json` (NON-secret,
  `0644`) and `config/secrets.json` (raw API keys ONLY, `0600`), both gitignored +
  dockerignored. The Providers page also has a per-card **Refresh models** button
  (read-only `POST /api/provider-settings/{provider}/fetch-models`): fetched ids
  are **review-only** and staged into the draft `custom_models` via Add / Add all
  new; an **explicit Save** is required to persist them (after which `/api/options`
  exposes the saved custom models). Fetching never auto-saves and never
  auto-switches the provider/default model.
- **Resolution precedence:** **per-job request > provider-settings store default >
  `.env` > built-in default**. With no store files present every lookup falls
  through to the prior `.env` path, byte-identical to before the store existed.
  Generator presets **never hard-pin** provider/model (`model_hint` stays
  advisory); a preset's **explicit** sampling/thinking value can override the
  stored runtime default.
- **Security.** `/api/options` and `/api/provider-settings` expose only non-secret
  derived info — `configured`, `key_source` (store/env/none), a last-4 `key_hint`,
  `base_url_host`. The public DTO has **no key field by construction**; the API key
  is write-only over the API (set/cleared, never read back). **Raw keys never reach
  the frontend.**
- **Local Model Manager — DETECTION-ONLY + MANUAL COMMAND HELPER, PHASE 1 COMPLETE
  (Slices 2 + 3 + 4).** A *separate* feature from Provider Settings, designed
  in `docs/LOCAL_MODEL_MANAGER_DESIGN.md`. The chosen approach is **staged +
  detection-first**: Phase 1 = **detection-only**. **Slice 2 (backend) is DONE**
  (branch `local-model-status-api`): a read-only **`GET /api/local-model/status`**
  (+ thin `POST /api/local-model/check` alias), backed by `get_local_model_status()`
  in `pipeline/provider_config.py`, reports whether the configured local server is
  reachable and what models it exposes — reusing the existing `local` base-URL
  resolution + `_discover_openai_models` + the redaction helpers. It returns safe
  fields only (host-only URL, reachable, latency, model list/count, default/selected
  model, normalized `local_offline` error, `actions`, `notes`); **`ok` means the
  status request succeeded, not that the server is up**. It **spawns nothing, writes
  nothing, browses no files, and never exposes a raw key or full URL.** **Slice 3
  (frontend) is DONE** (branch `local-model-status-ui`): a read-only **Local Models
  status panel** mounted inside the Providers (Models) page
  (`LocalModelsPanel.jsx` + pure `localModelStatus.js` helpers + the
  `getLocalModelStatus`/`checkLocalModelStatus` API client calls). It shows the live
  status pill (reachable/offline/not-configured/error), host-only base URL,
  in-Docker flag, latency, model count + bounded chips, default/selected model, a
  first-class offline/troubleshooting state (incl. the `--host 0.0.0.0` note), a
  **Refresh status** button, an "Edit local provider settings" link to the Local
  provider card (the single config writer). **Slice 4 (command helper) is DONE**
  (branch `local-model-command-helper`): a read-only
  **`GET /api/local-model/command-profile`** (`get_local_model_command_profiles()`)
  serves static, whitelisted `llama-server` start commands (a default GPU profile +
  a CPU-only profile) with a `/path/to/model.gguf` **placeholder**,
  `--host 0.0.0.0 --port 8080`, and safety warnings; the panel renders a first-class
  **Copy command** block (pure `localModelCommand.js` + a `CommandHelper`) the
  operator runs **manually** — prominent when offline, collapsed when reachable.
  **Command-helper copy support is implemented as MANUAL ONLY: the app never
  executes, spawns, starts, or stops anything; no GGUF scan; no raw key/URL.** With
  Slice 4, **Phase 1 (detection + manual command helper) is feature-complete and
  VALIDATED** (Slice 5 validation pass, `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`
  — all static/Docker/smoke/live-API/no-execution/secret-scan checks pass, no code
  changed). Still ahead: **Ask Your Guide local-only chat** (recommended; consumes LMM
  status, no process control), then an optional **host companion launcher** (Phase 2,
  design-only, sign-off-gated). **Direct Docker→host
  process spawn is rejected** — a non-root (uid 10001), `no-new-privileges` container
  cannot safely manage host processes. Provider config edits stay on Provider
  Settings (no second writer). See `DECISIONS.md`.
- **Local Model Manager Phase 2 direction — HOST COMPANION + APPROVED GGUF LIBRARY
  + START/STOP BRIDGE IN PROGRESS.** Phase 2A is documented in
  `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`; Phase 2B adds the scanning-only host
  companion prototype under `tools/local_model_companion/`; Phase 2C adds the
  read-only Docker backend bridge; Phase 2D adds the frontend model-library picker
  in the existing Local Models panel; Phase 2E persists a selected discovered GGUF
  model as app-side metadata only. Phase 2F is docs-only and defines the future
  safe start/stop/restart contract. Phase 2G1 adds companion-private process
  lifecycle internals with a fake/safe test executable only. Phase 2G2 exposes
  those internals through companion-local Unix-socket HTTP endpoints only. Phase
  2G3 adds the Docker FastAPI backend bridge routes for companion server
  status/start/stop/restart, still with no frontend UI. Future in-app model
  start/stop must go
  through React UI -> Docker FastAPI backend -> Unix-socket-first,
  token-authenticated host companion. For the current Linux Docker deployment,
  companion control assumes a Unix domain socket mounted into the backend
  container; `127.0.0.1`-only companion control is not assumed reachable from
  Docker unless host networking/native packaging is used, and host-gateway TCP
  requires explicit operator sign-off. The Docker backend must not directly browse
  the host filesystem or directly start/stop host processes. Phase 2B scans only
  explicit user-approved roots from an explicit local JSON config; no default home
  scan, no whole-PC scan, no implicit `~/models`, no arbitrary path search from
  Docker. The scanner canonicalizes roots/candidates, accepts `.gguf` files only,
  resolves symlinks and rejects targets outside approved roots, skips symlinked
  directories, bounds files/models/time/warnings, and returns safe model metadata
  with stable opaque ids and root-relative paths only. It implements `GET /health`,
  `GET /models`, and `POST /models/scan` over a token-authenticated Unix socket.
  Phase 2C exposes backend endpoints `GET /api/local-model/companion/status`,
  `GET /api/local-model/library`, and `POST /api/local-model/library/scan`, using
  server-side `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and optional
  `LMM_COMPANION_TIMEOUT_SECONDS`. The bridge whitelists model fields, bounds and
  redacts warnings, rejects absolute returned paths, and never exposes the raw
  companion token/socket path. Phase 2C socket-mount validation adds a manual live
  harness, `test_scripts/validate_lmm_companion_socket_mount.py`, that creates a
  temporary `/tmp` fake approved model root/config/socket, starts the host
  companion, generates a temporary Compose override that mounts only the temp
  runtime directory into service `app`, and verifies the Docker backend can call
  `/api/local-model/companion/status`, `/api/local-model/library`, and
  `/api/local-model/library/scan` through the mounted Unix socket. The override is
  not committed and the production `docker-compose.yml` remains unchanged. The
  live harness passed 17/17: status configured/reachable with `scan`, pre-scan
  library safe/empty, fake GGUF fixtures returned, non-GGUF excluded, redaction
  checks passed, process-control probes unavailable, and the app restored healthy
  with committed Compose only. Phase 2D adds frontend API helpers for companion
  status/library/scan and a read-only **Model Library** section that shows
  unconfigured/offline/auth/reachable/no-roots/no-models/warning states, displays
  only safe GGUF metadata, and initially allowed visual-only model selection in
  React state.
  Phase 2E adds `GET/POST/DELETE /api/local-model/library/selection`, persisted in
  `config/local_model_library_selection.json` via atomic writes, and stores only
  whitelisted safe fields (`id`, `display_name`, `filename`, root-relative
  `relative_path`, `root_id`, `size_bytes`, `modified_at`, `family_hint`,
  `quant_hint`, `server_compatible`, `selected_at`). The Local Models panel now
  shows the saved chosen library model, stale saved selections, a clear-selection
  flow, and a non-runnable future-launch preview that carries model id/filename/
  root-relative path/root id plus a `gpu_default` profile placeholder. The
  command-profile response also carries this selected-model metadata/preview.
  Phase 2F adds the durable design contract for companion endpoints
  `GET /server/status`, `POST /server/start`, `POST /server/stop`, and
  `POST /server/restart`; backend bridge routes
  `GET /api/local-model/server/status`, `POST /api/local-model/server/start`,
  `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`; and future UI controls. Start must
  accept only selected `model_id`, whitelisted `profile_id`, and typed bounded
  params (`port`, `ctx_size`, `gpu_layers`, `threads`, optional `batch_size`),
  never a shell command, free-form args, arbitrary executable path, or raw model
  path. Stop may terminate only the tracked companion-started process after
  identity checks; stale/reused/foreign PIDs are not killed. Restart is stop then
  start with either a fresh validated payload or `reuse_last: true` only when last
  launch metadata still validates. Process state is companion-private,
  permission-restricted, redacted in APIs, and checked for PID reuse on Linux via
  `/proc` where available. Logs are bounded/redacted; port conflicts fail safely;
  companion status is operational state and does not write Provider Settings.
  Phase 2G1 adds `tools/local_model_companion/profiles.py` and
  `process_manager.py` for internal-only fake-executable process control:
  profile validation uses typed bounded params; model ids resolve against
  approved-root scan records; argv arrays are built without shell execution;
  state is written atomically to a companion-owned runtime dir; and Linux `/proc`
  identity checks prevent killing stale/reused/foreign PIDs. Tests create a
  temporary executable Python script and fake `.gguf` files only. Phase 2G2 adds
  companion HTTP `GET /server/status`, `POST /server/start`,
  `POST /server/stop`, and `POST /server/restart` on the companion Unix-socket
  API using the existing token auth. These endpoints accept only typed safe JSON
  (`model_id`, whitelisted `profile_id`, bounded params, `grace_seconds`, or
  validated `reuse_last`), delegate to the process manager, reject unknown
  top-level request fields, and return safe DTOs without token, socket path,
  absolute model path, executable path, raw argv, Authorization, or full URL
  leaks. The companion config may include `process_runtime_dir` and
  `profiles.fake_test.executable`; there is no default real executable. Phase 2G3
  adds FastAPI routes `GET /api/local-model/server/status`,
  `POST /api/local-model/server/start`, `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`. The backend uses the existing
  stdlib Unix-socket bridge with server-side bearer auth, forwards only typed
  safe payload fields (`model_id`, `profile_id`, `port`, `ctx_size`,
  `gpu_layers`, `threads`, `grace_seconds`, or `reuse_last`), rejects unknown
  fields before socket forwarding, and returns only whitelisted/redacted server
  status DTO fields. Phase 2G4 adds frontend/client UI controls only: the Local
  Models panel has a **Managed Server** section that calls those backend bridge
  routes, fetches status on load, starts/restarts from the saved selected library
  model id plus fixed typed `fake_test` defaults (`port`, `ctx_size`,
  `gpu_layers`, `threads`), stops only the companion-managed server with bounded
  `grace_seconds`, keeps selected-model preview and manual command helper
  fallback visible, and clearly states manual servers are not stopped and
  Provider Settings are not changed. Phase 2G5 adds explicit-config real Linux
  `llama-server` profiles (`llama_cpp_gpu_default` /
  `llama_server_gpu_default`) with no default executable, canonical executable
  validation, approved-root model-id resolution only, centralized argv arrays,
  `starting` vs `running` semantics, readiness polling against
  `http://127.0.0.1:<port>/v1/models`, stable `error`/`crashed` states, bounded
  log tails with safe OOM/load/readiness categories, no restart loop, and Linux
  process-group stop after PID identity verification. The backend bridge
  whitelists the new states/categories and has a tiny Unix-socket transport seam;
  Unix socket remains the only implemented transport. Added
  `test_scripts/validate_lmm_real_llama_server.py`, which skips without explicit
  real env and otherwise starts a temporary companion, scans an approved root,
  launches real `llama-server`, verifies `/v1/models`, stops, checks port release
  and redaction, and cleans up. There is still no permanent Docker Compose mount,
  Provider Settings write, Ask change, dependency addition, local provider
  base-URL/model behavior change, direct companion frontend call, shell/free-form
  args UI, browser storage, token/socket exposure in UI, direct Docker host
  process control, direct host filesystem scan, automatic restart loop, model
  download manager, multi-server pool, Windows/macOS process control, or absolute
  host path/raw argv rendering. Next recommended slice is operator-run live
  `llama-server` validation using the harness, then optional real-profile UI
  design if requested.
- **Ask Your Guide — IN PROGRESS (Slice 1 design DONE; Slice 2 backend context
  inventory DONE; Slice 3 backend context preparation / chunking DONE; inserted
  workspace shell DONE; backend local chat API DONE; frontend chat UI wiring DONE;
  chat polish + emitted-citation validation DONE; session management UI/API DONE;
  chat math/source visual polish DONE; empty local-model response guard DONE).** A
  dedicated **`AskGuideWorkspace`** (first-class page/tab alongside
  Builder/Library/Styles/Providers) where the user selects a generated guide/job and
  chats with it using a **local model only**. Designed in
  `docs/ASK_YOUR_GUIDE_DESIGN.md`. **Local-only in v1** — resolves the **`local`
  provider only**, **status-gated** on LMM Phase 1 (offline → first-class offline
  state + the LMM command helper; **no DeepSeek/Qwen/cloud fallback**, a hosted
  "ask any provider" mode is a future explicit opt-in). It **reads** LMM status and
  job artifacts read-only; it **does not** start/stop `llama-server`, create
  generation jobs, or modify `clean.md`/`extracted.txt`/the manifest. A **context
  manager is mandatory** (chunk `clean.md`/`extracted.txt` with `## Page N`/heading
  citation anchors → a dependency-free lexical index cached per `(job_id,
  content_hash)` → **budgeted retrieval** reserving answer/system-rules/recent chat →
  a rolling chat summary; **never** dump the whole guide + all attachments + all
  history into every turn). A hard **accuracy/citation contract** (answer from the
  material first, cite page/section, say so when not covered, never invent
  facts/formulas/pages/dates). Extra uploads are **session-scoped** (never merged into
  the job, reuse `extract.py`); chat history is clearable and **never** auto-exported;
  **no secrets stored.** Build plan is 10 slices. **Slice 2 shipped** the two
  **read-only** context-inventory endpoints — `GET /api/ask/jobs` (lists only
  guides with a generated `clean.md`) + `GET /api/ask/jobs/{id}/context` (per-job
  guide/source/attachment summary + a `readiness` object), backed by the thin
  read-only reader `pipeline/ask_inventory.py` and the existing manifest/attachment
  redaction (no chat, chunking, model call, or UI; original artifacts untouched).
  **Slice 3 shipped** `POST /api/ask/jobs/{id}/prepare` + the stdlib-only
  `pipeline/ask_context.py`: deterministic, citation-labelled chunking of
  `clean.md`/`extracted.txt` on heading / `## Page N` boundaries + a dependency-free
  lexical index (term frequencies + `doc_freq`), cached at
  `jobs/<id>/ask/cache/context_index.json` keyed by a content hash over guide+source
  bytes (idempotent `hit`/`built`/`rebuilt`, atomic writes, fenced to the job dir).
  The whitelisted response returns counts + a citation summary only (no body, key,
  URL, or host path); no model call, sessions, or new dependency. An intentionally
  inserted frontend/product slice then shipped the visible **Ask Guide** workspace
  shell: top-level nav, guide picker, disabled chat/readiness panel, context sources
  rail, prepare-context button, and LMM offline/reachable status with the manual
  command helper. The backend local chat API then shipped session creation/load plus
  `POST /api/ask/sessions/{id}/message`: status-gate on LMM/local availability,
  synchronously prepare/reuse the Slice 3 cache, retrieve a bounded lexical chunk set,
  assemble citation-labelled context + hard answer rules + a small recent-history
  window, and call only the existing `local` OpenAI-compatible provider. Sessions live
  under `jobs/<job_id>/ask/sessions/<session_id>/`; history is JSONL; responses expose
  safe citation metadata only (no prompts or chunk text). **No cloud fallback, no
  DeepSeek/Qwen fallback, no extra uploads, no streaming, no rolling summary, no
  generation jobs, and no artifact mutation.** Frontend chat UI wiring then enabled
  the visible Ask workspace composer against those endpoints: sessions are created
  lazily on first send, loaded before messaging, and rendered as bounded history with
  plain-text answers, backend-returned citation chips, safe retrieved chunk metadata,
  and the existing LMM offline command helper. The UI stores only safe session
  metadata/history in React state and does not persist messages to browser storage.
  The chat polish/citation slice then added backend validation for model-emitted
  bracket citations against retrieved labels (`citations_allowed`, `citations_used`,
  `citations_unsupported`, `citation_validation`), strips unsupported Ask-looking
  citations, preserves normal bracketed prose, formats assistant markdown-ish text
  safely without `dangerouslySetInnerHTML`, fixes guide metadata/session-id display,
  and collapses retrieved chunk metadata by default. The session-management slice
  then added safe session listing, switching, new chat, clear-history, and delete
  controls/endpoints; clear keeps the session/context cache, delete removes only the
  fenced session directory, and lazy session creation on first send remains intact.
  The math/source visual-polish slice then improved the existing frontend-only answer
  renderer without adding markdown/KaTeX/MathJax dependencies: inert parsing handles
  `$$...$$`, `\[...\]`, `\(...\)`, and escaped-dollar inline math; display math
  renders as readable monospace blocks preserving line breaks; inline math renders as
  small monospace chips. Trusted backend-used citations appear in a clearer **Sources
  used** section, unsupported citations remain warning-only, retrieved chunk metadata
  stays collapsed with label/type/page/score/token rows, and chunk text is still
  never rendered. Local-only Ask behavior and session management are unchanged; no
  backend retrieval, prompt assembly, model-call, citation-validation, session,
  clear/delete, or lazy session creation logic changed. A follow-up bugfix discovered
  during manual Ask UI validation guards empty local-model responses:
  `pipeline/ask_sessions.py` catches the narrow
  `RuntimeError("LLM returned an empty response.")` case from
  `generate_chat_completion` and returns a structured `provider_error` with
  `error.category: provider_empty_response` and a retryable user-safe message instead
  of a raw FastAPI 500; the failed turn does not append a successful user/assistant
  history pair. A later local-thinking-model compatibility guard updated Ask prompt
  assembly to request visible assistant content instead of final answers only in
  hidden reasoning/reasoning_content. Manual full-prompt validation then showed the
  system-only guard was insufficient for the Gemma llama-server setup, so Ask now
  also inserts a model-only `/no_think` control in the assembled local-LLM user
  prompt immediately before the final `User question:` block. That marker is never
  persisted as user text, exposed in session load/list summaries, or rendered by the
  frontend, and it does not weaken grounding/citation rules. These Ask follow-ups
  did not change retrieval, fallback behavior, citation validation, session
  management, provider settings, streaming, uploads, rolling summary, multimodal, or
  process control. **NEXT = Ask extra session uploads
  only as a separate explicit slice, or narrow manual Ask polish if another concrete
  issue surfaces.** Still deferred: extra uploads unless explicitly chosen,
  streaming, hosted/cloud Ask, rolling summary, multimodal, and process control.
  See `DECISIONS.md`.

## 4. Architecture facts a new session MUST know

- **Non-root container.** The image creates `appuser` (uid **10001**); the
  entrypoint drops privileges via **gosu** before exec'ing the server. Do not
  assume root inside the container.
- **clean.md chokepoint.** All writes to a job's `clean.md` go through
  `JobManager.save_clean_md(...)` (`pipeline/job_manager.py`). It auto-snapshots
  for version history. Never write `clean.md` directly — route through it.
- **Permanent delete is fenced to trash.** Soft-delete moves
  `jobs/<id>/` → `jobs/.trash/<id>/` (reversible). Permanent purge can act
  **only** on a job already inside `jobs/.trash/`, guarded by a path assertion
  that hard-fails any id resolving outside the trash dir. Active jobs can never
  be hard-deleted directly.
- **Math validation degrades, never fails.** Math validation failures mark the
  offending spans and the job ends as **`completed_with_warnings`** — they do
  **not** kill the job.
- **Generator presets** inject a full system prompt and **append**
  `MARKDOWN_MATH_SYSTEM` (`pipeline/orchestrator.py`). Presets are distinct from
  styles (see `DECISIONS.md`). Presets tune **sampling** only — they **never
  hard-pin** the provider/model; `model_hint` is a soft advisory. A preset's
  explicit sampling/thinking value can override the stored runtime default.
- **Provider settings store** (`pipeline/provider_settings_store.py`). A two-file,
  whitelist-parsed, atomic JSON store under a gitignored `config/`:
  `provider_settings.json` (non-secret, `0644`) and `secrets.json` (raw API keys
  ONLY, `0600`). Keys are write-only over the API and redacted out of every
  response by construction. The resolver in `pipeline/provider_config.py` chains
  **settings store → `.env` → built-in default** (with per-job request still
  winning); no store files ⇒ byte-identical to the prior env path. Endpoints:
  `GET /api/provider-settings`, `PATCH /api/provider-settings/{provider}`,
  `…/clear-key`, `…/test`, `…/fetch-models` (read-only model discovery, no
  auto-persist). The stored `timeout_seconds`/`retry_count`/`thinking_default` are
  applied at the live model-call boundary (`build_provider_config` →
  `generate_chat_completion`). See `DECISIONS.md`.
- **Shortcut store** is a whitelist-validated JSON file at
  `library/shortcuts.json`. Import/export only accepts whitelisted fields.
- **Shortcut Inspector / Repair Loop.** Shortcuts whose saved references
  (provider / model / style / preset / section / axis) rot against live config can
  be inspected and repaired. Each shortcut view carries an **additive `validity`**
  object — a 3-tier status (`valid`/`degraded`/`broken`), the **full** findings
  list, and a saved-`model` check — computed at read time alongside the unchanged
  legacy `valid`/`reason`. `GET /api/shortcuts/{id}/inspect` adds redacted repair
  candidates; `POST …/repair/preview` (read-only) and `…/repair/apply` (the only
  write) drive a Home/Customize badge + Inspector drawer repair UI. **Safety
  model:** **no migration-on-read** (inspect/preview never rewrite
  `shortcuts.json`); **legacy `valid`/`reason` are preserved** byte-for-byte (so a
  degraded-only shortcut can read `valid:true` + `status:degraded`); **preview is
  read-only**; **apply is the only write** and is an explicit whitelisted patch
  (no arbitrary merge-patch); **clone mode mints a new id** and leaves the original
  untouched; no provider/model auto-switch and no raw key ever read or returned.
  **Activation gating:** the legacy `valid` boolean is still the hard guard. A
  **valid** shortcut launches immediately. A **degraded** shortcut (`valid:true` +
  `status:degraded`) **asks before launch** — a confirm dialog offers Continue
  anyway (unchanged launch, no mutation), Repair instead (opens the Inspector), or
  Cancel. A **broken** shortcut (`valid:false`) **stays blocked** and offers
  Inspect / Repair instead of launching. The Edit modal's **Generator Preset**
  dropdown is sourced from `/api/options.generator_presets` (the canonical
  generator-preset registry, same as the Builder Style tab) — **not** the Outline
  quick-template registry (`/api/presets`), which is a separate thing.
- **Shortcuts may optionally include saved prompt/source text.** A builder_setup
  shortcut can carry the typed source prompt under a whitelisted `saved_prompt`
  field, but **only when the user explicitly opts in** (a "Save prompt/source text
  with this shortcut" checkbox, default off). It captures **typed source text
  only** (never uploaded files/attachments/page selections), is capped at
  `MAX_SAVED_PROMPT_CHARS` (100 000), and is **user content, not a secret** — it is
  intentionally present in shortcut read/export when opted in (the inspector shows
  an info-only "Includes saved prompt" marker carrying the *length only*). Applying
  such a shortcut prefills the Builder source text. See `DECISIONS.md`.
- **Job stage reporting.** Coarse status (`queued/running/done/
  completed_with_warnings/failed/cancelled`) is augmented by finer `stage`/`progress`,
  surfaced via `GET /api/jobs/{id}/progress` and polled by the Builder.
- **Cooperative cancel.** `POST /api/jobs/{id}/cancel` writes a sidecar marker
  (`jobs/<id>/cancel.requested`) that the pipeline checks at safe stage boundaries;
  the job ends in the terminal `cancelled` status. It is **checkpoint-based, not a
  process kill**, so it takes effect at the next safe checkpoint and **preserves**
  partial artifacts + the user's inputs/settings (see `DECISIONS.md`).
- **Large-PDF core (preflight + page selection).** A read-only
  `POST /api/preflight/pdf` inspects an uploaded PDF *before* job creation and
  returns a soft verdict (`ok`/`warn`/`blocked`); the Builder surfaces it as a
  warning card. The user can pick **first N pages** or a **manual page range**,
  which becomes `page_selections` (`{filename: [[start, end], …]}`, **1-based
  inclusive**) on the LLM request, persisted in `job.json`. Extraction then
  restricts matching PDFs to the selected **ORIGINAL** pages (original `## Page N`
  anchors preserved; OCR runs **only** on selected pages). Default (no selection)
  ⇒ all pages, byte-equivalent to before. **Automatic split/chunk processing and
  hybrid embedded-text + OCR dedup are deferred** (see `DECISIONS.md`).

## 5. Working conventions

- **One slice per branch.** Small feature slices, verify-and-commit between each.
- **Surgical edits, not rewrites.** Preserve routes and pipeline behavior unless
  the slice is explicitly about them. The PDF pipeline is load-bearing.
- **Backend changes must be proven with a live run** — not just by reading
  source. Build + compile + docker + smoke (`test_scripts/smoke_release.py`).
- Keep same-origin Docker behavior, `/api/*` precedence, and the Claude-style UI
  as the visual baseline.
- Verification commands (from `../CLAUDE.md` §4):
  ```fish
  npm --prefix frontend run build
  python -m compileall api pipeline
  docker compose config && docker compose build && docker compose up
  curl http://localhost:8000/api/health
  curl http://localhost:8000/api/options
  ```
