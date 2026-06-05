# NEXT_CHAT_HANDOFF.md — Start here

> One-page handoff so a fresh chat (Claude / ChatGPT / Codex) can continue safely
> from the repo alone. The repo is the source of truth. For the full per-slice log
> see `CURRENT_TASK.md`; for the "why" behind choices see `DECISIONS.md`; for the
> stable overview see `PROJECT_CONTEXT.md`; canonical brief is `../CLAUDE.md`.

## Current position
- **Branch (trunk / PR target):** `chrome-renderer-v1`
- **Latest commit on trunk:** `e399f09` — "Add local-model command-helper (copy start
  command) (LMM Slice 4)", on top of the Slice 3 status panel (`7429f24`), the Slice 2
  status endpoint (`e27c674`), the Slice 1 design (`94003bc`), the **Shortcut Inspector
  / Repair Loop** (`a0f96d1`→`4458c9a`) + the Edit-preset follow-up (`adc2a7e`). The
  **in-app provider settings feature group** (`978516e`→`61fb423`) and the large-PDF
  core (`60c3e78`) remain on trunk below.
- **Active work branch:** `docs-validate-local-model-manager-phase1` — **LMM Slice 5**
  (Phase-1 validation / docs reconciliation, **docs-only**) ran here and **PASSED**;
  see "What just landed" + `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`.
- **Remote:** `origin/chrome-renderer-v1` == `e399f09` (the validation branch is local,
  docs-only, not yet pushed/merged).

## What just landed
- **Local Model Manager — Phase 1 COMPLETE + VALIDATED** (Slices 1→4 +
  Slice 5 validation). Detection-only status (`GET /api/local-model/status` +
  `POST /api/local-model/check`), the read-only **Local Models** panel, and the
  manual **command helper** (`GET /api/local-model/command-profile`) are all on trunk
  (`94003bc`→`e399f09`). The **Slice 5 validation pass** (branch
  `docs-validate-local-model-manager-phase1`, docs-only, no code changed) confirmed
  every Phase-1 guarantee: static suites green, Docker container healthy, smoke 28/28,
  live `/status`+`/command-profile` 200 (offline → safe `local_offline`, placeholder
  command, host-only URL), **no-process-execution proof** (only comments assert
  absence; the command helper returns strings/argv via `shlex.quote`), and a **clean
  secret scan** (the lone JS hit was a 4-char `LOCAL_LLM_API_KEY=none` placeholder
  coinciding with `display:"none"`, not a real key). No bugs found. See
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md` + `CURRENT_TASK.md` #49.
- **Local Model Manager — Slice 4: command-helper profiles / Copy start command**
  (branch `local-model-command-helper`). Read-only
  `GET /api/local-model/command-profile` → `get_local_model_command_profiles()` in
  `pipeline/provider_config.py`: static, whitelisted `llama-server` start commands
  (`llama_server_default` GPU + `llama_server_cpu`) with a `/path/to/model.gguf`
  **placeholder**, `--host 0.0.0.0 --port 8080`, and safety warnings. Command built
  from a fixed flag whitelist + `argv` (rendered via `shlex.quote`); the only
  substitution is the model placeholder. Frontend: `getLocalModelCommandProfile()`
  client helper + pure `frontend/src/localModelCommand.js` + a `CommandHelper` block
  in `LocalModelsPanel.jsx` (profile chips, selectable code block, **Copy command**
  with clipboard + manual fallback, prominent when offline / collapsed when
  reachable). The deferred `copy_start_command` "Planned" chip is suppressed; the
  Slice 2 status DTO is unchanged. **Command helper only — the app NEVER executes
  it: no subprocess/spawn, no start/stop, no host companion, no GGUF scan, no
  arbitrary shell, no raw key, host-only URL.** Tests:
  `test_scripts/test_local_model_command_profile.py` 13/13;
  `frontend/scripts/verify-local-model-command.mjs` (`npm run
  test:local-model-command`); Slice 2/3 + provider suites unchanged; `npm run build`
  OK. See `CURRENT_TASK.md` #48 + `LOCAL_MODEL_MANAGER_DESIGN.md` §11 (Slice 4 note).
- **Local Model Manager — Slice 3: Local Models status panel (FRONTEND)** (branch
  `local-model-status-ui`, frontend + API client + docs/tests only). A read-only
  **Local Models** panel mounted inside the Providers (Models) page, consuming the
  Slice 2 endpoints. New API client helpers `getLocalModelStatus()` (`GET
  /api/local-model/status`) + `checkLocalModelStatus()` (`POST /api/local-model/check`);
  pure `frontend/src/localModelStatus.js` helpers (mirrors `shortcutStatus.js`) that
  normalize the DTO into `reachable | offline | not_configured | error | unknown`
  (tolerating missing fields / an old backend) with badge, model-chip
  (`limit=12` + overflow), latency/error/notes, action enabled/disabled, and a
  `hasEnabledProcessControl` invariant guard; `LocalModelsPanel.jsx` rendering a
  status pill, host-only base URL + in-Docker flag, a metrics strip, bounded model
  chips, a first-class offline/troubleshooting state (incl. the `--host 0.0.0.0`
  note), a **Refresh status** button (calls `/check`, never saves/starts), an "Edit
  local provider settings" link that scrolls to `#provider-card-local` (single
  writer), and the **disabled** "Copy start command — Planned" chip. **No process
  control, no inline base-URL editing, no raw key/URL.** Tests:
  `frontend/scripts/verify-local-model-status.mjs` 47/47 (`npm run
  test:local-model-status`); `npm run build` OK; backend suites unchanged
  (`test_local_model_status.py` 17/17, fetch-models 16/16, settings-store 26/26);
  smoke 28/28; live offline proof + clean secret scan. See `CURRENT_TASK.md` #47 +
  `LOCAL_MODEL_MANAGER_DESIGN.md` §11 (Slice 3 note).
- **Local Model Manager — Slice 2: detection-only backend status endpoint**
  (branch `local-model-status-api`, backend-only, on trunk as `e27c674`). Read-only
  `GET /api/local-model/status` + a thin `POST /api/local-model/check` alias, backed
  by `get_local_model_status()` in `pipeline/provider_config.py`. Returns a safe DTO
  (`{ok, provider, configured, base_url_host, base_url_configured, in_docker,
  reachable, models, model_count, default_model, selected_model, latency_ms, error,
  actions, notes}`). **`ok` ≠ reachable.** Connection failures normalize to a single
  `local_offline`. **No process spawn, no writes, no file browsing, no raw key,
  host-only URL.** See `CURRENT_TASK.md` #46 + `LOCAL_MODEL_MANAGER_DESIGN.md` §11.
- **Shortcut Inspector — degraded-activation confirm + "Repair instead"**
  (branch `shortcut-inspector-degraded-activation`, frontend-only). Home card
  launches now route through a pure `activationDecision` (`shortcutStatus.js` →
  `launch`/`confirm`/`blocked`): a **valid** shortcut launches immediately; a
  **degraded-yet-launchable** one (`validity.status === "degraded"` while legacy
  `valid === true`) raises a confirm dialog — **Continue anyway** (unchanged
  launch path, no mutation) / **Repair instead** (opens the existing Inspector
  drawer, no preview/apply until the user acts) / **Cancel**; a **broken** one
  (`valid === false`) stays blocked and shows a "This shortcut is broken."
  Inspect/Repair dialog instead of silently routing. Legacy `valid` is still the
  hard guard. New node harness `verify-shortcut-activation.mjs` (wired into
  `test:shortcuts`). No backend change. See `CURRENT_TASK.md` #43 +
  `SHORTCUT_INSPECTOR_REPAIR_DESIGN.md` §5.5 + `DECISIONS.md`.
- **Shortcut Inspector / Repair Loop — COMPLETE through Slice 3B**
  (`a0f96d1`→`4458c9a`, DONE #39→#42): a read-only inspector with an additive
  `validity` object (3-tier `valid`/`degraded`/`broken` status, the **full**
  findings list, and the previously-missing saved-`model` check) + `GET
  /api/shortcuts/{id}/inspect`, with the legacy `valid`/`reason` preserved
  byte-for-byte; 3-tier Home/Customize badges + a read-only Inspector drawer;
  repair endpoints `POST /api/shortcuts/{id}/repair/preview` (read-only) +
  `…/repair/apply` (the only write — explicit whitelisted patch, in-place or
  clone); and the repair UI (Keep/Replace/Remove controls, in-place vs clone,
  **Preview required before Apply**, editing the draft re-disables Apply,
  explicit confirm). No migration-on-read; preview never mutates `shortcuts.json`;
  clone mints a new id and leaves the original untouched; **card activation is
  unchanged** (still gated on legacy `valid`). Validated docs-only in
  `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`. See `CURRENT_TASK.md` #39→#42 +
  `DECISIONS.md` (shortcut inspector/repair entries).
- **In-app provider settings feature group — COMPLETE through Slice 5**
  (`978516e`→`61fb423`): a two-file server-side store
  (`config/provider_settings.json` non-secret `0644` + `config/secrets.json`
  raw-keys-only `0600`), safe endpoints (`GET /api/provider-settings`,
  `PATCH /api/provider-settings/{provider}`, `…/clear-key`, `…/test`,
  `…/fetch-models`), a frontend Providers page (routed from the Models sidebar
  item) with a per-card **Refresh models** button, and **runtime** wiring so the
  stored `timeout_seconds`/`retry_count`/`thinking_default` reach the live model
  call. The read-only `POST …/{provider}/fetch-models` endpoint (`6da944a`) lists
  provider models without auto-persisting; the Refresh Models UI (`61fb423`) shows
  fetched ids **review-only**, stages new ids into the draft `custom_models` via
  **Add** / **Add all new**, and requires an **explicit Save** to persist (after
  which `/api/options` includes the saved custom models — Builder dropdowns keep
  reading `/api/options`). Fetching never auto-saves and never auto-switches the
  provider/default model. **Security:** raw keys stay **server-side only**;
  `/api/options`, `/api/provider-settings`, and the fetch-models response are
  **redacted** (no key field by construction — only `configured`/`key_source`/
  last-4 `key_hint`/`base_url_host`); the API key is write-only. **Precedence:**
  provider/model = **per-job request > provider-settings default > `.env` >
  built-in**; generator presets **never hard-pin** provider/model (`model_hint`
  advisory), and an **explicit** preset sampling/thinking value overrides the
  stored runtime default. No store files ⇒ byte-identical to the prior env path.
  See `CURRENT_TASK.md` #32→#36 + `DECISIONS.md` (provider-settings entries).
- **Large-PDF core workflow — COMPLETE end-to-end** (`841d3f9`→`60c3e78`): a
  read-only `POST /api/preflight/pdf` verdict (`ok`/`warn`/`blocked`), a Builder
  preflight warning card, `page_selections` (`{filename: [[start,end],…]}`,
  1-based inclusive) plumbed through the request + persisted in the manifest, the
  extractor restricting matching PDFs to the selected ORIGINAL pages (anchors
  preserved, OCR only on selected pages), and a live first-N / manual page-range
  UI. **Usable end-to-end:** preflight warns → user picks first N or a range →
  the request carries `page_selections` → extraction uses the original page
  anchors. **Automatic split/chunk processing and hybrid embedded-text + OCR
  dedup remain deferred.** See `CURRENT_TASK.md` #27→#31.
- **Cooperative server-side cancel** (`901d44b`): a `jobs/<id>/cancel.requested` marker
  checked at safe stage boundaries, a new `cancelled` terminal status,
  `POST /api/jobs/{id}/cancel`, and a Builder Cancel button. **Checkpoint-based,
  cooperative only** — it does **not** kill processes/threads; a cancel during an
  uninterruptible LLM call or Chromium render takes effect at the **next safe
  checkpoint**, not instantly. Partial artifacts and the user's uploads / Builder
  inputs / settings are **preserved** (nothing deleted; re-generate from the Builder).
  Retry-from-cancelled is deferred. See `CURRENT_TASK.md` #22.
- **B4 "Export selected"** (`65b9b8f`): the Library bulk bar gained an "Export selected"
  action reusing the existing `POST /api/exports/bundle` ZIP endpoint (no new primitive,
  no backend change). See `CURRENT_TASK.md` #21.
- **Rerender preserves `generator_preset`** (`2716995`): `retry_failed_job` now reads the
  preset from the manifest and rebuilds through it (tuned sampling params + system prompt
  reapplied), instead of dropping to the default path. A since-removed preset id degrades
  gracefully; the user's saved provider/model still wins. Backend-only.
- **Group C fully integrated** onto `chrome-renderer-v1` (squash `6f888b2`): generator
  presets + cards, output-section toggles (`include_sections`), depth/difficulty axes,
  shortcut options bridge, Builder options UI, `qwen3.7-plus`, Home/nav cleanup.
- **OCR + PDF fixes** on the trunk: re-applied `_preprocess_ocr_image` (`5bde798`), MCQ
  answer + page-reference prompt fixes (`75ec24f`), and **page-level mixed scanned/text
  PDF OCR fallback** (`72dab90` / `773209a`).
- **Docker compose hardening** (`1d51b36`): `mem_limit: 2g`, `pids_limit: 256`,
  `cpus: 2.0`, `security_opt: no-new-privileges:true` (additive, `docker compose config`
  validated). Salvaged from local-only `863f5b7`; its non-root/gosu hardening was already
  in at `6f888b2`.

## ⚠️ Old branches — do NOT re-merge
The whole Group C feature stack (`style-output-toggles`, `style-axes`,
`shortcut-options-bridge`, `builder-options-ui`, `preset-*`, `qwen37-plus-model`,
`home-nav-cleanup`, `library-*`, plus `integ-group-c` and `salvage-compose-limits`) is
**consumed/archival**. Its content already lives in the trunk. **Do not merge or rebase
any of them again** — it would reintroduce superseded code and resurrect resolved
conflicts. They are kept (not deleted) only as reference. See `DECISIONS.md`.

Local-only `61c134c` and `863f5b7` stay **parked on the `hardening` branch** — useful
pieces already salvaged; the rest is deferred (below).

## RULE for new work
**Branch from `chrome-renderer-v1` @ `e399f09` (or later) — never from an old stacked
branch.** One small slice per branch; verify (build + compile + docker + smoke) and
commit before moving on. Surgical edits, not rewrites. The PDF/Chromium pipeline is
load-bearing — do not rewrite casually.

## Next recommended slice
**Pick ONE safe option:**
- **Ask Your Guide — local-only chat (recommended).** Now that LMM Phase 1 is
  complete + validated, the natural next feature is a local-only chat over a generated
  guide that **consumes** the LMM detection status (first-class offline empty state, no
  hosted fallback in local-only mode) and the existing `local` provider. **It reads
  status; it does not start/stop `llama-server`** (no process control). Design-first;
  see `LOCAL_MODEL_MANAGER_DESIGN.md` §10 + §11 ("Later — Ask Your Guide").
- **Local Model Manager — Phase 2 host companion launcher (DESIGN-FIRST, optional).**
  Only if app-managed **start/stop** of a host `llama-server` is desired. Process
  control crosses the container boundary and is deferred to an optional host companion
  (direct Docker→host spawn rejected). Design + sign-off first (LMM Slice 5).
- **Focused manual validation / polish of the Shortcut Inspector UI.** The
  inspect→repair loop + degraded-activation confirm are complete and validated at
  the API + harness level; the remaining gap is a human click-through of the live
  Home/Customize 3-tier badges, the Inspector drawer, the Preview→Apply / clone
  flow (incl. the stale-preview re-disable), and the new degraded/broken
  activation dialogs. Validation / polish only — no code unless a concrete UI bug
  surfaces.
- **Math/PDF font-size rationalization (cause C, CSS-only).** Optional remaining
  fidelity slice; CSS-only investigation before any change.
- **Large-PDF preflight size-limit polish — optional, later.** Raising the upload
  ceiling + preflight size thresholds is a possible later slice; **not part of any
  current slice** and not started.

(The previously-recommended **in-app provider settings** (COMPLETE through
**Slice 5** — fetch-models endpoint + Refresh Models UI), the **shortcut inspector
/ repair loop** (now COMPLETE through **Slice 3B**, `a0f96d1`→`4458c9a`),
**Math/PDF fidelity investigation**, and **Large-PDF preflight design** are **all
DONE** — provider settings shipped as #32→#36 (`978516e`→`61fb423`), the shortcut
inspector shipped as #39→#42, the preflight design shipped as Slices 1–5
(`841d3f9`→`60c3e78`), and the math/PDF fidelity Slices 1–3 shipped (#23–#25). The
provider-settings real-world validation pass also ran
(`docs/VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md`, two now-fixed findings). The
rerender `generator_preset` fix, B4 "Export selected", and server-side cancel are
also DONE and on trunk — see "What just landed". The only remaining math/PDF slice
is the optional **font-size rationalization** (cause C, CSS-only).)

## Open / deferred items
- **rerender drops `generator_preset`** — DONE (`2716995`, on trunk). Rerender now
  reproduces the preset.
- **B4 "Export selected"** — DONE (`65b9b8f`, on trunk). Reuses the existing bundle endpoint.
- **Real server-side cancel button** — DONE (`901d44b`, on trunk; cooperative,
  checkpoint-based, marker file, `cancelled` status; does not kill processes; preserves
  uploads/inputs/settings). Retry-from-cancelled still deferred (re-generate from the
  Builder instead).
- **Large-PDF core (preflight + page-range selection)** — DONE end-to-end
  (`841d3f9`→`60c3e78`, #27→#31): preflight verdict endpoint, Builder warning card,
  `page_selections` plumbing + manifest persistence, extraction honoring selected
  ORIGINAL pages (OCR only on selected pages), and the first-N / manual page-range UI.
- **Math / PDF fidelity Slices 1–3** — DONE (#23–#25). Remaining optional slice:
  **font-size rationalization** (cause C, CSS-only).
- **Large-PDF — still deferred:** automatic split/chunk processing; hybrid
  embedded-text + OCR dedup; raising the upload ceiling (`MAX_UPLOAD_MB`); persisting
  the preflight report in `job.json`; carrying page selections into drafts/shortcuts.
  None started — do not begin without an explicit slice + design.
- **In-app provider settings feature group** — DONE through Slice 5
  (`978516e`→`61fb423`, #32→#36): two-file store (non-secret
  `provider_settings.json` + `0600` `secrets.json`), redacted endpoints, Providers
  UI, runtime `timeout_seconds`/`retry_count`/`thinking_default` applied, read-only
  `fetch-models` endpoint, and the Refresh Models UI (review-only fetch → stage into
  draft `custom_models` → explicit Save). Keys stay server-side only; presets never
  hard-pin provider/model. **Still deferred:** encrypted-at-rest / OS keyring; `.env`
  import; optional Builder "Provider default" thinking UI polish.
- **Local Model Manager** — **Phase 1 COMPLETE + VALIDATED** (Slices 1→4 on trunk
  `94003bc`→`e399f09`; Slice 5 validation docs-only,
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`). Slice 2 =
  the detection-only backend status endpoint (`GET /api/local-model/status` + `POST
  /api/local-model/check`, `get_local_model_status()`) shipping safe fields only.
  Slice 3 = the read-only **Local Models status panel** in the Providers (Models)
  page (`LocalModelsPanel.jsx` + pure `localModelStatus.js` + the
  `getLocalModelStatus`/`checkLocalModelStatus` client helpers): status pill,
  host-only base URL, latency, model count + chips, first-class offline
  troubleshooting, **Refresh status**, and an "Edit local provider settings" link to
  the Local card — **no** process control, inline editing, or raw key/URL. Slice 4 =
  the **command helper** (`GET /api/local-model/command-profile` +
  `localModelCommand.js` + a `CommandHelper` block): a copyable, static, whitelisted
  `llama-server` start command (placeholder model path, `--host 0.0.0.0`) the
  operator runs **manually** — the app never executes it. **Phase 1 is feature-complete
  and validated** (Slice 5, DONE #49). **Next major choice = Ask Your Guide local-only
  chat (recommended)** or the sign-off-gated host-companion DESIGN (Phase 2). Remains a
  **separate** feature from the in-app provider settings; provider config writes stay on
  `PATCH /api/provider-settings/local`.
- **Library archive / tag model** — DESIGN-FIRST (bulk archive needs an archive state +
  `DECISIONS.md` entry; bulk tag needs a tag model; neither started).
- **GHCR publish workflow / prebuilt image** — deferred distribution decision (parked on `hardening`).
- **Pinned dependency lockfile** — deferred; regenerate from this tree, don't lift from `hardening`.
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
- **Shortcut inspector / repair loop** — DONE through Slice 3B
  (`a0f96d1`→`4458c9a`, #39→#42): additive `validity` (3-tier status, full
  findings, saved-model check; legacy `valid`/`reason` preserved), `GET
  …/inspect`, 3-tier badges + read-only Inspector drawer, repair preview
  (read-only) / apply (the only write; in-place + clone) + repair UI
  (Preview-before-Apply, stale-preview re-disable, explicit confirm). Validated
  docs-only (`docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`). The
  **degraded-activation confirm / "Repair instead" Home path (§5.5) is now DONE**
  (branch `shortcut-inspector-degraded-activation`, #43 — see "What just landed").
  **Still deferred:** "Repair all" batch, a Home "N need attention" banner, model
  auto-suggest/fuzzy match, imported preview-row repair before import, tool/view
  repair (repair is scoped to `builder_setup`).
- **Branch retirement** — deferred housekeeping (do not delete branches).
- **Group D** — not started; do not begin without an explicit slice request.

## Verification commands
```fish
npm --prefix frontend run build          # builds frontend/dist (served by backend)
python -m compileall api pipeline        # compile-check backend + pipeline
docker compose config                    # validate compose (expands .env in plaintext — do not share output)
docker compose build
docker compose up
curl http://localhost:8000/api/health    # {"ok":true}
curl http://localhost:8000/api/options   # themes / styles / providers / models / generator_presets (redacted)
curl http://localhost:8000/api/provider-settings  # provider settings, redacted (no raw keys; only configured/key_source/key_hint/base_url_host)
python test_scripts/smoke_release.py     # end-to-end release smoke (~28 checks; outline-ordering check is known-flaky)
```
