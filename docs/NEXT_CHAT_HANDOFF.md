# NEXT_CHAT_HANDOFF.md — Start here

> One-page handoff so a fresh chat (Claude / ChatGPT / Codex) can continue safely
> from the repo alone. The repo is the source of truth. For the full per-slice log
> see `CURRENT_TASK.md`; for the "why" behind choices see `DECISIONS.md`; for the
> stable overview see `PROJECT_CONTEXT.md`; canonical brief is `../CLAUDE.md`.

## Current position
- **Branch (trunk / PR target):** `chrome-renderer-v1`
- **Latest commit:** `4458c9a` — "Wire shortcut repair UI to preview/apply
  (Slice 3B)". The **Shortcut Inspector / Repair Loop** landed as five commits on
  top of the provider-settings group + its follow-up fixes (`70544de` validation
  report, `6a1499c` Test-Connection empty-content fix, `e524c79`
  stored-`default_provider` precedence, `2ea4380` validation-doc pointer):
  `a0f96d1` (design doc), `482c377` (Slice 1 backend inspector), `1f9034f`
  (Slice 2 read-only inspector UI), `e148cc4` (Slice 3A repair preview/apply
  endpoints), `4458c9a` (Slice 3B repair UI wiring). The **in-app provider
  settings feature group** (`978516e`→`61fb423`) and the large-PDF core
  (`60c3e78`) remain on trunk below it; older `61fb423` / `60c3e78` / `901d44b` /
  `65b9b8f` mentions below are historical.
- **Remote:** `origin/chrome-renderer-v1` == `4458c9a` (pushed; local == origin)

## What just landed
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
**Branch from `chrome-renderer-v1` @ `61fb423` (or later) — never from an old stacked
branch.** One small slice per branch; verify (build + compile + docker + smoke) and
commit before moving on. Surgical edits, not rewrites. The PDF/Chromium pipeline is
load-bearing — do not rewrite casually.

## Next recommended slice
**Pick ONE safe option:**
- **Local Model Manager — LMM Slice 2: detection-only backend status endpoint
  (recommended).** The **design is DONE** (LMM Slice 1, docs-only —
  `docs/LOCAL_MODEL_MANAGER_DESIGN.md`): a staged, **detection-first** plan. The
  next implementation slice is the **detection-only** backend: read-only
  `GET /api/local-model/status` + `POST /api/local-model/check` returning safe
  fields only (base-URL host, reachable, latency, model count/list, default model,
  classified `local_offline` error, start instructions). **No process control, no
  raw key, no full URL.** Reuse `_effective_base_url`/`_discover_openai_models`/the
  redaction helpers; provider config WRITES stay on
  `PATCH /api/provider-settings/local`. **Direct Docker→host process spawn is
  REJECTED** — host process control is deferred to an optional host companion
  (Phase 2, design-only). See design §4 + §11 + §13.
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
- **Local Model Manager — Phase 2 host companion launcher (DESIGN-FIRST, later).**
  Process control crosses the container boundary and is deferred to an optional
  host companion (direct Docker→host spawn rejected). Design + sign-off first.

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
- **Local Model Manager** — **design DONE** (LMM Slice 1, docs-only —
  `docs/LOCAL_MODEL_MANAGER_DESIGN.md`): staged detection-first plan (Phase 1
  detection-only; Phase 2 optional host companion; direct Docker→host spawn
  **rejected**). **Next implementation slice = LMM Slice 2: detection-only backend
  status endpoint** (`GET /api/local-model/status` + `POST /api/local-model/check`,
  safe fields only, no process control). Remains a **separate** feature from the
  now-complete in-app provider settings; provider config writes stay on
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
