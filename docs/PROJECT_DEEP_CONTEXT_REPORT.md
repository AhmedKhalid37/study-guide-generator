# Study Guide Generator — Deep Project Context Report

> Single-file long-term project memory for future Claude / Claude Code / Codex
> sessions. Built by reading the repo (docs **and** implementation) and reconciling
> the two. Where docs and code disagree, the discrepancy is called out explicitly
> (see §22 and the "Discrepancies" notes inline). The repo is the source of truth;
> this report is a navigational/contextual summary, not a substitute for reading the
> load-bearing files before changing them.
>
> Generated: 2026-06-08. Branch: `chrome-renderer-v1`.

---

## 1. Executive Summary

**Study Guide Generator** is a Dockerized, same-origin **React (Vite + Tailwind) +
FastAPI** application that turns course material (pasted text, uploaded Markdown, or
uploaded attachments) into clean, exam-focused **study guides**, rendered to **PDF**
(via headless Chromium) plus **Markdown / HTML / DOCX** artifacts. It also generates
**quizzes / flashcards** with CSV / Anki / Quizlet export.

It is a **single-operator / small-group** tool (not multi-tenant) with a Claude-style
desktop UI. The user picks a **style** and/or a **generator preset**, optionally drafts
an **outline**, generates, then manages results in a **Library** (folders) and an
**Exports** center. A **Home** page offers customizable, inspectable **shortcuts**. An
**Ask Your Guide** workspace lets the user chat (local-model-only) with a generated
guide, grounded and cited.

The codebase has accreted several substantial, well-documented feature groups, most of
which are **complete and validated**:

- **Provider Settings** (in-app provider/key/model/runtime config) — **complete**.
- **Large-PDF preflight + page selection core** — **complete** (auto-split deferred).
- **Shortcut Inspector / Repair Loop** — **complete**.
- **Ask Your Guide** (local-only v1) — **complete enough**; must stay local-only.
- **Local Model Manager (LMM) Phase 1** (detection + manual command helper) —
  **complete + validated**.
- **Local Model Manager Phase 2** (host companion → approved-GGUF scan → Unix-socket
  backend bridge → model-library UI → companion-managed `llama-server` lifecycle) —
  **safe milestone complete/PAUSED after Phase 2G11 final hardening.**

A reader who absorbs this file plus `CLAUDE.md`, `docs/PROJECT_CONTEXT.md`,
`docs/DECISIONS.md`, and `docs/NEXT_CHAT_HANDOFF.md` should be able to continue work
without the original chat history.

---

## 2. Current Repo / Branch Assumptions

- **Main branch / trunk / PR target: `chrome-renderer-v1`.** Branch all new work from
  it. (`git status` at session start was clean on this branch.)
- **Codex-formatted implementation prompts** are the current convention for handing off
  implementation work, **unless the user explicitly switches back to Claude Code.**
- **No old consumed/feature branches may be revived, merged, rebased, or
  cherry-picked.** Group C and the LMM/Ask/Provider/Shortcut stacks were already
  squashed/integrated onto the trunk; re-merging would reintroduce superseded code and
  resurrect resolved conflicts. Old branches are *kept, not deleted* (operator
  preference), as archival reference only. See `DECISIONS.md` → "Consumed feature
  branches must not be re-merged".
- **Do not force-push.**
- **One slice per branch**, verify-and-commit between each, surgical edits not rewrites.
- Doc-tracking files that must stay current: `docs/CURRENT_TASK.md` (live per-slice
  log, ~3000 lines), `docs/NEXT_CHAT_HANDOFF.md` (one-page start-here),
  `docs/PROJECT_CONTEXT.md` (stable overview), `docs/DECISIONS.md` (append-only
  rationale). `CLAUDE.md` is the canonical brief.
- **Note:** `CLAUDE.md` is somewhat *behind* the current state — it predates the LMM,
  Ask, Provider-Settings, Shortcut, large-PDF, quiz, and section-regen features and
  still describes the older baseline. Treat `PROJECT_CONTEXT.md` / `CURRENT_TASK.md` /
  this report as the more current narrative, and the code as authoritative.

---

## 3. Product Purpose And User Experience

**Problem solved:** an exam-stressed student (or small study group) has raw course
material — lecture slides (PDF, often scanned), notes, pasted text — and wants a clean,
structured, exam-focused study guide quickly, in a polished document they can print or
revise from, optionally with quizzes/flashcards and the ability to *ask the guide
questions* with citations.

**Audience:** personal / small-group; single operator, not multi-tenant. This shapes
many decisions (e.g. trash-before-purge, server-side keys, no auth layer assumed).

**Intended UX:** a Claude-style desktop shell with a left **Workspace** sidebar. The
seven nav workspaces (`frontend/src/components/DesktopDashboard.jsx`, `navItems`):

1. **Home** — customizable shortcut tiles (`HomeShortcuts.jsx`).
2. **Builder** — input → (outline) → generate → result (`BuilderWorkspace.jsx`).
3. **Library** — folders + search/filter/sort + batch move + trash (`LibraryWorkspace.jsx`).
4. **Ask Guide** — chat with a generated guide, local-only (`AskGuideWorkspace.jsx`).
5. **Styles** — built-in / custom / AI-generated styles (`StylesWorkspace.jsx`).
6. **Models** — Provider Settings + Local Models panel (`ProviderSettingsWorkspace.jsx`).
7. **Exports** — artifact center + ZIP bundles (`ExportsWorkspace.jsx`).

(`activeSection` ids are `home/builder/library/ask/styles/models/exports`; note the nav
id for Provider Settings is **`models`**, labeled "Models".)

Core happy path: pick a style/preset → optionally draft an outline → paste/upload/LLM
input → Generate → view result + warnings in Builder → manage in Library/Exports →
optionally Ask the guide questions.

---

## 4. High-Level Architecture

```text
main-app/
├── api/server.py        # FastAPI: ALL /api/* routes, then SPA static mount at "/"
├── frontend/            # React (Vite + Tailwind) → built to frontend/dist (served by backend)
│   ├── src/components/   # workspaces + panels
│   ├── src/*.js          # pure helper modules (status/repair/meta/command), node-testable
│   └── scripts/*.mjs     # pure-node verify harnesses
├── pipeline/            # all backend logic: extraction, LLM, render, stores, ask, lmm bridge
├── tools/local_model_companion/  # host-side companion (NOT in the Docker image)
├── prompts/             # built-in style .md prompts + system/user templates
├── user_prompts/        # custom/generated styles + styles.json (gitignored runtime)
├── library/             # folders.json, job_folders.json, shortcuts.json (gitignored runtime)
├── config/              # provider_settings.json, secrets.json, local_model_library_selection.json (gitignored)
├── jobs/                # generated job artifacts + jobs/.trash/ (gitignored)
├── output/              # convenience copies of final outputs (gitignored)
├── themes/              # PDF CSS themes (only claude_clean.css today)
├── test_scripts/        # smoke_* + test_* harnesses + live LMM validation harnesses
├── docs/                # design docs, validation records, examples/
├── Dockerfile, docker-compose.yml, docker-entrypoint.sh, .dockerignore
```

**Same-origin design (load-bearing):** `api/server.py` registers every `/api/*` route
first, then mounts the built SPA as a catch-all at `/`
(`StaticFiles(directory=frontend/dist, html=True)`). Because the mount is registered
**after** the API routes, **`/api/*` always wins** over the SPA fallback. Keep it that
way. One origin for UI + API; no CORS plumbing.

**Deployment:** Dockerized, port **8000**, uvicorn `api.server:app` on `0.0.0.0:8000`.
`frontend/dist` is **built inside the image** (multi-stage `node:20-slim` → copied into
`python:3.12-slim` runtime), never copied from host.

**Runtime dependencies baked into the image:** **chromium** (PDF render), **nodejs/npm**
(KaTeX validate + HTML render), **tesseract-ocr (+eng)** (OCR for image-only PDFs),
**gosu** (privilege drop). Non-root: image creates `appuser` (uid **10001**); entrypoint
`mkdir`s + `chown`s the runtime dirs then `exec gosu appuser "$@"`. Container also runs
`no-new-privileges:true`. **Do not assume root inside the container.**

---

## 5. Backend Architecture

`api/server.py` (~3800 lines) is the single FastAPI app. It owns route definitions and
request DTOs (Pydantic models such as `LLMJobRequest`), delegating real work to
`pipeline/` modules. Key backend modules:

- `pipeline/provider_config.py` — provider registry (`deepseek`, `qwen`, `local`),
  alias map, base-URL/key/model resolution chains, redaction helpers, `/models`
  discovery (`_discover_openai_models`), `get_local_model_status()`,
  `get_local_model_command_profiles()`, `build_provider_config`.
- `pipeline/llm_client.py` — `LLMConfig` + `generate_chat_completion()` (the single
  model-call boundary; OpenAI-compatible). Timeout/retry/`allow_empty_content` live here.
- `pipeline/provider_settings_store.py` — two-file whitelist JSON store (see §11).
- `pipeline/orchestrator.py` — system-prompt assembly: `MARKDOWN_MATH_SYSTEM`,
  `INCLUDE_SECTION_FRAGMENTS` (+ `INCLUDE_SECTION_ALIASES`), `OUTPUT_DEPTH_FRAGMENTS`,
  `DIFFICULTY_FRAGMENTS`, `normalize_include_sections`. The canonical section/axis key
  set lives **here**, not the frontend.
- `pipeline/run_llm_job.py`, `pipeline/run_markdown_job.py`, `pipeline/job_stages.py` —
  job execution paths (LLM generation vs markdown-only), staged with progress reporting.
- `pipeline/job_manager.py` — `Job` / `JobManager`; the `save_clean_md` chokepoint,
  version snapshots, cancel-marker handling (`request_cancel`/`raise_if_cancelled`),
  trash/purge fencing.
- `pipeline/extract.py` — attachment extraction + page-level OCR + `preflight_pdf`.
- `pipeline/math_validator.py` — KaTeX-based math validation (degrade-not-fail).
- `pipeline/pdf_renderer.py`, `pipeline/html_renderer.py`, `pipeline/docx_renderer.py` —
  artifact renderers. PDF uses headless Chromium via Node.
- `pipeline/markdown_sanitizer.py`, `pipeline/markdown_sections.py`,
  `pipeline/section_scorer.py` — markdown clean-up and section parsing/scoring.
- `pipeline/style_store.py`, `pipeline/generator_presets.py`, `pipeline/presets.py`,
  `pipeline/prompt_loader.py` — style registry, generator presets, outline quick-templates.
- `pipeline/library_store.py`, `pipeline/shortcut_store.py` — library folders + shortcuts.
- `pipeline/ask_inventory.py`, `pipeline/ask_context.py`, `pipeline/ask_sessions.py` —
  Ask Your Guide read inventory, chunking/index, sessions+chat.
- `pipeline/local_model_companion_client.py` — backend → host companion Unix-socket bridge.
- `pipeline/local_model_library_selection.py` — app-side selected-GGUF persistence.
- `pipeline/errors.py` — `classify_exception`, `VALID_CATEGORIES` (incl. `local_offline`).

**Route inventory (verified from `api/server.py`):**

- Core: `GET /api/health`, `GET /api/options`.
- Provider settings: `GET /api/provider-settings`, `PATCH /api/provider-settings`,
  `PATCH /api/provider-settings/{provider}`, `POST …/{provider}/clear-key`,
  `POST …/{provider}/test`, `POST …/{provider}/fetch-models`.
- Local Model Manager: `GET /api/local-model/status`, `POST /api/local-model/check`,
  `GET /api/local-model/command-profile`, `GET /api/local-model/companion/status`,
  `GET /api/local-model/library`, `POST /api/local-model/library/scan`,
  `GET /api/local-model/server/status`, `GET /api/local-model/server/profiles`,
  `POST /api/local-model/server/start|stop|restart`,
  `GET|POST|DELETE /api/local-model/library/selection`.
- Styles: `GET /api/styles`, `GET/PUT/DELETE /api/styles/{id}`, `POST /api/styles`,
  `POST /api/styles/generate`.
- Outline: `GET /api/presets`, `POST /api/presets/{id}/apply`, `POST /api/outline/generate`.
- Jobs: `GET /api/jobs`, `GET /api/jobs/{id}`, `…/progress`, `…/error`, `…/cancel`,
  `…/favorite`, `…/retry`, `…/rerender`, `…/artifacts/{name}`, `…/versions`,
  `…/clean_md` (GET/PUT), `…/versions/{v}/clean_md`, `…/revert/{v}`, `…/sections`,
  `…/outline_compliance`, `…/sections/{idx}/regenerate`.
- Input: `POST /api/jobs/paste`, `POST /api/jobs/upload-markdown`, `POST /api/jobs/llm`,
  `POST /api/preflight/pdf`.
- Bulk + trash: `POST /api/jobs/bulk/{delete,restore,move,purge}`,
  `GET /api/jobs/trash`, `POST /api/jobs/{id}/trash`, `…/restore`,
  `DELETE /api/jobs/trash`, `DELETE /api/jobs/trash/{id}`.
- Quizzes: `POST /api/jobs/{id}/quiz`, `GET /api/jobs/{id}/quizzes`, `…/{n}`, `…/{n}/export`.
- Ask: `GET /api/ask/jobs`, `GET /api/ask/jobs/{id}/context`,
  `POST /api/ask/jobs/{id}/prepare`, `POST /api/ask/jobs/{id}/sessions`,
  `GET /api/ask/jobs/{id}/sessions`, `GET /api/ask/sessions/{sid}`,
  `POST /api/ask/sessions/{sid}/message`, `DELETE /api/ask/sessions/{sid}/history`,
  `DELETE /api/ask/sessions/{sid}`.
- Library: `GET /api/library`, `GET/POST /api/library/folders`,
  `PUT/DELETE /api/library/folders/{id}`, `POST /api/library/jobs/move`,
  `POST /api/library/jobs/{id}/move`.
- Shortcuts: `GET /api/shortcuts`, `…/export`, `POST /api/shortcuts`, `…/reorder`,
  `…/defaults/reset`, `…/import/preview`, `…/import`, `GET/PUT/DELETE /api/shortcuts/{id}`,
  `…/{id}/export`, `…/{id}/inspect`, `…/{id}/repair/preview`, `…/{id}/repair/apply`.
- Exports: `GET /api/exports`, `POST /api/exports/bundle`.

> **Note:** the route surface is much larger than `CLAUDE.md`'s "Key API routes" list —
> quizzes, section regeneration, version history/revert, outline compliance, bulk
> operations, trash, and the full LMM/Ask surfaces are all real and additive. `CLAUDE.md`
> is out of date on this; `api/server.py` is authoritative.

---

## 6. Frontend Architecture

React + Vite + Tailwind. Entry: `frontend/src/main.jsx` → `App.jsx` → `GlowBackground` +
`DesktopDashboard`. `DesktopDashboard.jsx` is the shell: holds `activeSection` state,
the sidebar nav, and conditionally renders each workspace.

**Component map (`frontend/src/components/`):** `DesktopDashboard`, `HomeShortcuts`,
`BuilderWorkspace`, `OutlineEditor`, `RecentJobsPanel`, `PasteGenerationPanel`,
`LibraryWorkspace`, `StylesWorkspace`, `ExportsWorkspace`, `ProviderSettingsWorkspace`,
`LocalModelsPanel`, `AskGuideWorkspace`, `ShortcutInspector`, plus presentational pieces
(`TopBar`, `BrandMark`, `ClaudeIcons`, `GlowBackground`, `FallbackImage`,
`ImplementationNote`, `DesktopMockup`, `PhoneMockup`, `MobileScreenPicker`).

**Pure helper modules (`frontend/src/*.js`)** — deliberately React-free so plain-node
harnesses in `frontend/scripts/*.mjs` can unit-test them without a test runner:
`api/client.js` (all fetch helpers), `askGuide.js`, `localModelStatus.js`,
`localModelCommand.js`, `localModelLibrary.js`, `localModelServer.js`, `shortcutStatus.js`
(incl. `activationDecision`), `shortcutRepair.js`, and `*Meta.js` display-metadata files
(`styleMeta`, `folderMeta`, `presetMeta`, `sectionMeta`, `shortcutMeta`).

**Key frontend principle:** display-metadata files hold **labels/grouping only**; the
canonical key sets (sections, axes, presets) live in the backend. The frontend can never
invent a section/axis the backend won't honour. (`DECISIONS.md` → "Builder section/axis
metadata: the frontend never owns the key set".)

**Verify harnesses (node, no test runner):** `verify-assets`, `verify-ask-guide`,
`verify-local-model-{status,command,library}`,
`verify-shortcut-{status,form,repair,activation}`.

**Rendering safety:** assistant answers and shortcut findings are rendered through tiny
inert subset renderers — **no `dangerouslySetInnerHTML`, no markdown/KaTeX/MathJax
dependency** in the Ask/answer path. Frontend normalizers redact `sk-*` keys, bearer
headers, full URLs, and host paths before storing/rendering. There is **no
localStorage/sessionStorage** persistence of chat/session data.

---

## 7. UI Workspaces And User Flows

- **Home** (`HomeShortcuts`) — shortcut tiles with 3-tier validity badges; activation is
  gated through pure `activationDecision()` (valid → launch; degraded → confirm dialog
  with Continue/Repair/Cancel; broken → blocked dialog offering Inspect/Repair).
- **Builder** (`BuilderWorkspace`) — input modes (paste / upload-markdown / LLM), style +
  generator-preset selection (preset cards with advisory model-hint compatibility
  warnings), output-section toggles + depth/difficulty axes, attachments with large-PDF
  preflight warning + page selection, an editable **Outline** tab (`OutlineEditor`),
  Generate, progress polling, and the result panel (downloads + warnings). Save-to-folder
  during generation. The visible "mode" control was retired (styles define guide type);
  backend still accepts `mode` defaulting to `study_guide`. The "Save draft" button and
  the sidebar storage meter are **decorative/inert** (deferred wiring).
- **Library** (`LibraryWorkspace`) — folders, client-side search/filter/sort, single +
  batch move, trash view (soft-delete + restore + guarded purge).
- **Ask Guide** (`AskGuideWorkspace`) — three-region: guide picker / chat+readiness /
  context+local-model rail. Local-only (see §13).
- **Styles** (`StylesWorkspace`) — built-in, custom, and AI-generated styles.
- **Models** (`ProviderSettingsWorkspace` + `LocalModelsPanel`) — provider cards
  (key/base-URL/default-model/custom-models/runtime defaults, Test, Refresh models) and
  the Local Models panel (status, command helper, model library, managed server).
- **Exports** (`ExportsWorkspace`) — per-job artifact downloads, filters, ZIP bundles.

Cross-cutting: a **Job Details drawer** is reachable from Recent Jobs / Library / Exports
/ Builder, showing metadata, attachment extraction warnings, outline summary, and
downloads.

---

## 8. Generation Pipeline

Three input transports converge on the job pipeline:

- `POST /api/jobs/paste` — pasted text → markdown job.
- `POST /api/jobs/upload-markdown` — `.md`/`.markdown` upload → markdown job.
- `POST /api/jobs/llm` — LLM generation. **Two request-construction paths that DO NOT
  share parsing:** a JSON body (no attachments, parsed for free by the `LLMJobRequest`
  Pydantic model) and a **multipart/form-data** body (with attachments, hand-built
  field-by-field in `_parse_llm_request`). **Permanent rule:** any field added to
  `LLMJobRequest` must be wired into the multipart branch too and verified in *both*
  paths (C3 found `include_sections`/`output_depth`/`difficulty` were silently dropped on
  the multipart side; large-PDF `page_selections` learned the same lesson).

**System-prompt assembly (`pipeline/orchestrator.py`), deterministic order:**
`preset system prompt (preset path only)` → `axis/global directive fragments`
(`output_depth` then `difficulty`) → `include_sections` fragments → **`MARKDOWN_MATH_SYSTEM`
(always the final appended block)**. With no preset, no axes, and no sections, the
assembled system message is **byte-identical** to the historical baseline (verified by
equality in tests). Unknown section keys are dropped; unknown axis values are rejected at
the API boundary (HTTP 400) and defensively ignored by the orchestrator on rerender.

**Generation-affecting request fields:**
- `include_sections` — canonical dict-of-bool (glossary, MCQs, formula sheet, etc.),
  single source of truth `INCLUDE_SECTION_FRAGMENTS`; legacy shortcut "modules" keys
  alias onto canonical keys via `INCLUDE_SECTION_ALIASES`.
- `output_depth` (`quick`/`balanced`/`exhaustive`) and `difficulty`
  (`beginner`/`normal`/`exam_level`/`advanced`) — global directive axes, persisted in the
  manifest so rerender reproduces them. **`voice` was deliberately NOT added** — Styles
  own voice/tone.

**Job lifecycle:**
- Coarse status: `queued/running/done/completed_with_warnings/failed/cancelled`,
  augmented by finer `stage`/`progress` (`GET /api/jobs/{id}/progress`, polled by Builder).
- **Cooperative cancel:** `POST /api/jobs/{id}/cancel` writes a sidecar marker
  (`jobs/<id>/cancel.requested`) checked at safe stage boundaries — **checkpoint-based,
  not a process kill**; nothing is deleted; ends in terminal `cancelled`. Retry-from-
  cancelled is intentionally not wired (re-generate from Builder).
- **Retry** (`…/retry`) is gated to `failed` jobs.
- **clean.md chokepoint:** ALL writes to a job's `clean.md` go through
  `JobManager.save_clean_md(...)`, which auto-snapshots version history. Never write
  `clean.md` directly. Versions/revert and manual clean_md editing ride this.
- **Section regeneration:** `POST /api/jobs/{id}/sections/{idx}/regenerate` re-generates
  one parsed section; outline compliance is reported via `…/outline_compliance`.
- **Quizzes/flashcards:** `POST /api/jobs/{id}/quiz` generates from a guide; listed/
  exported via `…/quizzes` (CSV / Anki / Quizlet).

---

## 9. Rendering / PDF / DOCX / HTML Pipeline

- **PDF** (`pipeline/pdf_renderer.py`) — rendered with **headless Chromium driven via
  Node** (NOT a Python HTML engine). Themed by CSS under `themes/` (only
  `claude_clean.css` exists today; a second theme / theme-picker is deferred).
  **Load-bearing and tuned — do not rewrite casually.**
- **HTML** (`pipeline/html_renderer.py`) — uses Node + KaTeX for math rendering.
- **DOCX** (`pipeline/docx_renderer.py`) — **lazy-generated from `clean.md`** on demand,
  so even old jobs can produce a DOCX. Fidelity is practical, not pixel-perfect: math is
  preserved as literal LaTeX *text* (not rendered equations); images become `[image: alt]`
  placeholders; deeply nested lists collapse to the deepest Word level; raw HTML renders
  as text.
- **Math validation** (`pipeline/math_validator.py`) — KaTeX-based; **degrades, never
  fails.** A failed equation marks the offending spans and ends the job as
  `completed_with_warnings` rather than killing an expensive generation. The math
  sanitizer + KaTeX validation are load-bearing.
- **Re-render:** `POST /api/jobs/{id}/rerender` regenerates PDF/HTML (keeps DOCX in sync).

Per-job artifacts: `final.pdf`, `final.docx` (lazy), `final.html`, `clean.md`,
`validation.json`, `render.log` (plus extracted source text, version snapshots, and any
Ask session data under the job dir).

---

## 10. Attachment Extraction, OCR, And Large-PDF Handling

**Extraction (`pipeline/extract.py`):** supports `.txt/.md/.csv/.tsv/.docx/.pptx/.pdf`.
OCR uses **Tesseract** for image-only PDF pages.

**Page-level (not whole-document) text/OCR fallback (load-bearing fix):** `_extract_pdf`
decides text-vs-OCR **per page**. A page's embedded text is "meaningful" (OCR skipped)
when stripped text is **≥ 40 chars OR has ≥ 5 word-like tokens**; otherwise that page is
OCR'd individually. A page uses embedded text **XOR** OCR (never both, to avoid
duplication). This fixed mixed PDFs where one text title-slide previously suppressed OCR
for the rest of the deck. Mode reporting gained `pdf_mixed` (alongside `pdf_text` /
`pdf_ocr`); mode is informational metadata in `job.json` only, never branched on.

**Large-PDF core (`docs/LARGE_PDF_PREFLIGHT_DESIGN.md`, Slices 1–5, COMPLETE):**
- `POST /api/preflight/pdf` — read-only, inspects a bounded evenly-spaced page sample
  *before* job creation, returns `verdict` (`ok`/`warn`/`blocked`) + `warnings[]` +
  `allowed_actions[]`. **Only encrypted/corrupt PDFs are `blocked`; any other inspection
  failure (incl. PyMuPDF missing) degrades to `ok`** — preflight is advisory, fails open,
  never gates a processable PDF. `split_automatically` is never emitted.
- `page_selections` — a flat `{filename: [[start, end], …]}`, **1-based inclusive**
  ("first N" = `[[1, N]]`). Normalized (sorted/merged ranges), bounded
  (`MAX_PAGE_SELECTION_FILES`=20, `MAX_PAGE_RANGES_PER_FILE`=50), bad shapes → HTTP 400,
  wired into both JSON and multipart request paths, persisted in `job.json`, preserved
  across retry. Absent/empty ⇒ all pages ⇒ byte-equivalent to before.
- Extraction restricts matching PDFs to the selected **ORIGINAL** pages (a single
  `if index not in selected: continue` before any get_text/OCR), keeps original
  `## Page N` anchors (selecting pages 20–21 yields `## Page 20`/`## Page 21`, never
  renumbered), matches by original filename, drops out-of-range pages with a warning.

**Deferred (deliberately):** automatic split/chunk processing; hybrid embedded-text + OCR
dedup; raising `MAX_UPLOAD_MB`; persisting the preflight report in `job.json`; carrying
page selections into drafts/shortcuts. (Truncation caps are env-configurable, defaults
200k/600k — Option A; provider-aware caps are Option B, deferred.)

---

## 11. Provider System And Provider Settings

**Providers:** `deepseek`, `qwen`, `local` (canonical ids), with `PROVIDER_ALIASES`
mapping display variants. DeepSeek + Qwen are verified-working; **local** is supported via
env/discovery and usually shows `configured:false` until a local server is set up.
`local`'s built-in `LOCAL_LLM_BASE_URL = http://host.docker.internal:8080/v1` exists but is
**not** wired as an automatic fallback, so an unconfigured local provider resolves to
`None` (not configured). compose adds `extra_hosts: host.docker.internal:host-gateway`.

**Provider Settings (COMPLETE through Slice 5):** lets the user configure keys, base URLs,
default models, custom models, and runtime defaults (`timeout_seconds`/`retry_count`/
`thinking_default`) **in-app** instead of editing `.env`.

- **Two-file server-side store** (`pipeline/provider_settings_store.py`, under gitignored +
  dockerignored `config/`): `provider_settings.json` (**non-secret**, `0644`) and
  `secrets.json` (**raw API keys ONLY**, `0600`). The split makes the security boundary
  physical: the public serializer reads only the non-secret file + flags and never
  serializes `secrets.json`.
- **Keys are write-only over the API** (set/cleared, never read back). A blank `api_key`
  in a PATCH is a no-op, never a clear.
- **Public DTO has no key field by construction** — exposes only `configured`,
  `key_source` (store/env/none), a last-4 `key_hint` (only when key length > 4), and
  `base_url_host` (host only, userinfo stripped).
- **Resolution precedence: per-job request > provider-settings store default > `.env` >
  built-in default.** With no store files, every lookup falls through to the prior `.env`
  path, byte-identical to before the store existed. A stored `default_provider` ranks below
  an explicit per-request provider but above the historical "first-configured" guess.
- **Runtime applied at the call boundary:** stored `timeout_seconds`/`retry_count`/
  `thinking_default` resolved once in `build_provider_config`, applied in
  `generate_chat_completion`. Retry is **transient-only** (429/5xx/connection/timeout);
  4xx/missing-config/unsupported are not retried. No store ⇒ no timeout, 0 retries,
  thinking `True` ⇒ byte-identical to trunk.
- **Generator presets never hard-pin** provider/model — `model_hint` is a soft advisory.
  A preset's explicit sampling/thinking value *can* override the stored runtime default.
- **fetch-models** (`POST /api/provider-settings/{provider}/fetch-models`): read-only model
  discovery reusing `_discover_openai_models`; does **not** auto-persist or auto-switch.
  The Refresh-Models UI stages fetched ids into the draft `custom_models`; an explicit
  **Save** is required before `/api/options` surfaces them.
- **Test connection** (`…/test`) treats an empty-content choice as success
  (`allow_empty_content=True`, probe-only) so thinking models aren't misclassified as
  broken; a response with no choices is still a failure.

`/api/options` and `/api/provider-settings` expose only redacted, non-secret derived info.
**Raw keys never reach the frontend.**

---

## 12. Local Model Manager

A **separate feature** from Provider Settings (Provider Settings stays the only config
writer — no second writer). Designed in `docs/LOCAL_MODEL_MANAGER_DESIGN.md` (Phase 1) and
`docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md` (Phase 2), with operator/runtime docs in
`docs/LOCAL_MODEL_MANAGER_OPERATOR_SETUP.md` and
`docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md`.

**Hard constraint shaping everything:** the backend runs inside a **non-root (uid 10001),
`no-new-privileges` Docker container**; a host `llama-server` runs on the host. A
container process **cannot safely start/stop host processes** — **direct Docker→host spawn
is permanently REJECTED.** Host filesystem/process access is owned by an optional
**host-side companion**, never by the Docker backend directly.

### 12.1 Phase 1 — COMPLETE + VALIDATED

Detection-only + manual command helper (Slices 1→5, validated in
`docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`):

- `GET /api/local-model/status` (+ thin `POST /api/local-model/check` alias) →
  `get_local_model_status()`: reports whether the configured local server is reachable and
  what models it exposes, reusing existing base-URL resolution + `_discover_openai_models`
  + redaction. Returns host-only URL, reachable, latency, model list/count,
  default/selected model, normalized `local_offline` category, actions, notes. **`ok` means
  the status request succeeded, NOT that the server is up.** Spawns/writes/browses nothing;
  never exposes a raw key or full URL.
- `GET /api/local-model/command-profile` → static, whitelisted `llama-server` start
  commands (default GPU + CPU-only profiles) with a `/path/to/model.gguf` placeholder,
  `--host 0.0.0.0 --port 8080`, and safety warnings. The panel renders a **Copy command**
  block the operator runs **manually** — the app never executes/spawns/starts/stops
  anything; no GGUF scan; no raw key/URL.
- Frontend: `LocalModelsPanel.jsx` + pure `localModelStatus.js`/`localModelCommand.js`.

### 12.2 Phase 2 Architecture

Flow: **React UI → Docker FastAPI backend → Unix-socket-first, token-authenticated host
companion → approved-root GGUF scan → host `llama-server` process lifecycle.** For the
current Linux Docker deployment, companion control assumes a **Unix domain socket mounted
into the backend container**; a `127.0.0.1`-only companion is not assumed reachable from
Docker unless host networking/native packaging is used; **host-gateway TCP requires
explicit operator sign-off** (firewall-restricted to Docker bridge subnets + token auth).
`llama-server` may still bind `--host 0.0.0.0` for its model `/v1` API (so Docker can reach
the model), which is **separate** from the companion control API (which must never be
public).

### 12.3 Companion (`tools/local_model_companion/`, host-side, NOT in the Docker image)

Stdlib-only Python package (~2500 lines): `config.py` (explicit JSON config loading + `.ini`
preset import via `configparser` with interpolation disabled), `model_library.py`
(bounded approved-root `.gguf` scanner), `profiles.py` (typed bounded launch profiles +
`fake_test`), `process_manager.py` (`ManagedServerProcessManager` lifecycle), `companion.py`
(Unix-domain-socket `BaseHTTPRequestHandler` API). Config is explicit via `--config` /
`LMM_COMPANION_CONFIG`; **no default home scan, no implicit `~/models`, no silent root
creation.** Companion endpoints (all behind `Authorization: Bearer <token>`):
`GET /health`, `GET /models`, `POST /models/scan`, `GET /profiles`, `GET /server/status`,
`POST /server/start|stop|restart`.

### 12.4 Model Library (scan + selection)

- Scanner canonicalizes roots/candidates, accepts `.gguf` case-insensitively, resolves
  symlinks and **rejects targets outside approved roots**, skips symlinked directories,
  bounds files/models/time/warnings, returns **root-relative paths only** with stable
  opaque ids (`root_id + normalized relative_path`), and **never** absolute host paths.
- Backend bridge (`pipeline/local_model_companion_client.py`): a tiny stdlib `AF_UNIX`
  HTTP client using server-side `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, optional
  `LMM_COMPANION_TIMEOUT_SECONDS`. Whitelists model fields, rejects absolute returned
  paths, redacts tokens/auth/URLs/abs-paths, normalizes failures to safe categories
  (`companion_config`/`companion_offline`/`companion_auth`/`companion_timeout`/
  `companion_error`). Endpoints: `GET /api/local-model/companion/status`,
  `GET /api/local-model/library`, `POST /api/local-model/library/scan`.
- Selection (`config/local_model_library_selection.json`, atomic writes):
  `GET/POST/DELETE /api/local-model/library/selection` persists only whitelisted safe
  fields (`id`, `display_name`, `filename`, root-relative `relative_path`, `root_id`,
  `size_bytes`, `modified_at`, `family_hint`, `quant_hint`, `server_compatible`,
  `selected_at`). App-side only; no process control.

### 12.5 Managed Server Start/Stop

- Backend bridge routes `GET /api/local-model/server/{status,profiles}`,
  `POST …/server/{start,stop,restart}` forward only `model_id`, whitelisted `profile_id`,
  and typed bounded params (`port`, `ctx_size`, `gpu_layers`, `threads`, plus
  `parallel`/`cache_type_k`/`cache_type_v`/`flash_attention`/`mmap` in the schema);
  stop forwards bounded `grace_seconds`; restart forwards an explicit payload or
  `{reuse_last: true}`. Unknown fields → safe `bad_request` before any socket call.
- Companion side: executable path comes **only** from companion config (canonicalized,
  must be executable; no default real executable). Model path resolves only from an
  approved scanned model id. Argv is centralized
  (`<exe> -m <model> --host <configured-safe-host> --port <port> -c <ctx_size>
  -ngl <gpu_layers> --threads <threads>`); **no shell, no free-form args.** Launch uses
  `start_new_session=True`; lifecycle persists `starting` then promotes to `running` only
  after host-side `GET http://127.0.0.1:<port>/v1/models`; stable `error`/`crashed`
  states; **no auto-restart loop.** Stop targets only a verified tracked process group
  after Linux `/proc` identity checks; **foreign/reused/uncertain PIDs are never killed.**
- The `fake_test` profile is for validation only. The Managed Server UI picks the safest
  runnable profile in memory (`cpu_safe` → first runnable non-test → `fake_test`), renders
  typed schema-driven controls, and keeps the manual command helper as fallback.

### 12.6 Runtime Service Docs

`docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md` + safe templates under `docs/examples/`
(`lmm-companion.config.example.json`, `lmm-companion.profiles.example.ini`,
`lmm-companion.user.service.example`, `docker-compose.lmm-companion.override.example.yml`):
Linux-first operator startup, token handling (placeholder `replace-with-local-token`,
server-side only), manual health checks, **socket-directory-only** Docker mount, systemd
user-service template, E2E validation env, troubleshooting, security checklist. Templates
use placeholders only and avoid whole-home mounts, Docker socket, privileged mode, host
PID namespace, host networking, and host-gateway TCP.

### 12.7 Current Safe Milestone And Deferred LMM Work

**The current safe LMM Phase 2 milestone is COMPLETE / PAUSED after Phase 2G11** (final
offline regression harness `test_scripts/test_lmm_phase2_final_regression.py` + doc
reconciliation). Implemented Linux path: host companion, approved-root scan, Unix-socket
backend bridge, model-library UI, selected-model handoff, companion-managed server
controls, real `llama-server` lifecycle hardening, safe typed controls, `.ini` preset
import, configured real-profile E2E harness, runtime-setup UX, and operator/runtime docs.

**Deferred (do not begin without separate explicit design):** the **approve-root flow**
(must be separately designed as a host-companion flow), app-suggested settings /
recommendations, Ollama / simple-local-model path, Windows/macOS packaging/support, and
model downloads. **Recommended next: keep LMM Phase 2 paused; resume only with a
separately designed approve-root flow or packaging slice.**

---

## 13. Ask Your Guide

Designed in `docs/ASK_YOUR_GUIDE_DESIGN.md`; implemented through chat + session management
+ visual polish + guards. **Local-only v1 is complete enough and MUST remain local-only
unless explicitly redesigned.**

- **A dedicated first-class workspace** (`AskGuideWorkspace.jsx`) where the user selects a
  generated guide/job and chats with it using the **`local` provider only**, status-gated
  on LMM Phase 1. Offline → first-class offline state + the LMM command helper. **No
  DeepSeek/Qwen/cloud fallback** (a hosted mode would be a separate explicit opt-in).
- It **reads** LMM status + job artifacts read-only; it **does not** start/stop
  `llama-server`, create generation jobs, or modify `clean.md`/`extracted.txt`/manifest.
- **Mandatory context manager** (never dump the whole guide + all attachments + all
  history into every turn): `pipeline/ask_context.py` chunks `clean.md` (guide) + optional
  `extracted.txt` (source) deterministically on heading / `## Page N` boundaries (~650-token
  target, ~800 ceiling via `chars/4`, no overlap), preserving each chunk's **citation
  label** (nearest heading / `Page N`), and builds a **dependency-free lexical index**
  (per-chunk term frequencies + `doc_freq`). `POST /api/ask/jobs/{id}/prepare` builds/reuses
  a cache at `jobs/<id>/ask/cache/context_index.json` keyed by a content hash over
  guide+source bytes (idempotent `hit`/`built`/`rebuilt`, atomic writes, fenced to the job
  dir).
- **Chat:** sessions live under `jobs/<job_id>/ask/sessions/<session_id>/` (`session.json`
  atomic + `history.jsonl` append-only). `POST /api/ask/sessions/{sid}/message` status-gates
  on local availability (offline → structured `local_offline`, **no model call**), prepares/
  reuses the cache, retrieves a bounded top-K (~8, ~3k-token pool) lexical chunk set,
  assembles hard answer rules + citation-labelled chunks + a small recent-history window,
  and calls only `build_provider_config("local", …)` + `generate_chat_completion`.
- **Citation contract enforced:** the backend validates model-emitted bracket citations
  against retrieved labels (`citations_allowed`/`citations_used`/`citations_unsupported`/
  `citation_validation`), strips unsupported Ask-looking citations, preserves normal
  bracketed prose.
- **Guards:** empty local-model responses are caught and returned as structured
  `provider_error` (`category: provider_empty_response`), not a raw 500; a local
  thinking-model compatibility guard inserts a **model-only `/no_think`** marker
  immediately before the final `User question:` block — never persisted to history, never
  in session summaries, never rendered by the frontend.
- **Frontend** renders answers through an inert subset renderer (no
  `dangerouslySetInnerHTML`, no markdown/KaTeX/MathJax dep); inert math-aware parsing for
  `$$…$$`/`\[…\]`/`\(…\)`/escaped-dollar inline math renders as monospace blocks/chips;
  retrieved chunk metadata stays collapsed and **chunk text is never rendered**.
- **Session management:** list/switch/new/clear-history/delete. Clear keeps the session id +
  context cache; delete removes only the fenced session directory.
- **No secrets stored**, ever, in session files/caches/logs. Chat is **never** auto-exported.

**Deferred:** extra session uploads (separate explicit slice), streaming, hosted/cloud Ask,
rolling summary, multimodal, and process control.

---

## 14. Home Shortcuts / Shortcut Inspector / Repair Loop

**Shortcut store** (`pipeline/shortcut_store.py`, `library/shortcuts.json`, atomic write
`0644`): a versioned JSON registry of three shortcut types — `builder_setup`, `tool`,
`library_view` — each with a **whitelisted** payload (`_normalize_payload` reads only known
keys; unknown keys like `cmd`/`path`/`args` can never ride in). Import/export are
whitelist-validated.

**Shortcut Inspector / Repair Loop — COMPLETE** (Slices 1+2+3A+3B + degraded-activation +
the Edit-modal preset fix + opt-in `saved_prompt`):

- Each shortcut view carries an **additive `validity`** object: a 3-tier status
  (`valid`/`degraded`/`broken` = worst severity of a full `findings[]` list) + a
  saved-`model` check, computed at read time **alongside the unchanged legacy
  `valid`/`reason`**. A degraded-only shortcut can read `valid:true` + `status:degraded`.
- `GET /api/shortcuts/{id}/inspect` adds redacted repair candidates;
  `POST …/repair/preview` (read-only) and `…/repair/apply` (**the only write**) drive the
  badge + Inspector drawer repair UI.
- **Safety model:** **no migration-on-read** (inspect/preview never rewrite
  `shortcuts.json` — verified byte-identical); legacy `valid`/`reason` preserved
  byte-for-byte; **apply is the only write** and is an **explicit whitelisted patch**
  (`mode` + `changes{provider,model,style,generator_preset,output_depth,difficulty,
  include_sections{remove,set},remove_fields}` + `clone_name`) — **not** an arbitrary
  merge-patch; unknown key → HTTP 400; `provider` is not removable; clone mints a new id and
  leaves the original untouched; **no provider/model auto-switch**; no raw key ever read or
  returned. Apply reuses existing `update_shortcut`/`create_shortcut` CRUD so the
  whitelist + atomic write hold automatically.
- **Apply requires a fresh preview** of the current draft (editing the draft marks the
  preview stale and re-disables Apply); the draft starts empty (all "keep").
- **Activation gating** (`activationDecision` in `shortcutStatus.js`, used by
  `HomeShortcuts`): **legacy `valid` is the hard guard.** Valid → launch immediately;
  degraded (`valid:true`+`status:degraded`) → confirm dialog (Continue anyway / Repair
  instead / Cancel); broken (`valid:false`) → blocked dialog (Inspect / Repair), never
  silently routed.
- **Edit modal Generator Preset dropdown** is sourced from
  `/api/options.generator_presets` (the canonical generator-preset registry, same as the
  Builder Style tab) — **NOT** the Outline quick-template registry `/api/presets` (two
  distinct registries that must never be conflated).
- **Opt-in `saved_prompt`:** a `builder_setup` shortcut may carry typed source text under a
  whitelisted `saved_prompt` field **only when the user explicitly opts in** (default off),
  capped at `MAX_SAVED_PROMPT_CHARS` (100 000), typed source text only (no uploads/page
  selections). It is **user content, not a secret** — intentionally present in
  read/export when opted in; the inspector shows an info-only `saved_prompt_included`
  marker carrying the **length only**.

---

## 15. Builder Styles, Generator Presets, Sections, Axes

Two distinct, non-conflatable registries plus the styles system:

- **Styles** (`pipeline/style_store.py` + `prompts/`): define the guide *type*;
  user-editable and AI-generatable. Built-ins (flat `.md` in `prompts/`):
  `baby_steps`, `basic_study_guide`, `claude_study_guide`, `exam_cram`, `final_solution`,
  `master_longform`, `mcq_training` (+ `study_guide_prompts.md`, `study_guide_system.md`,
  `study_guide_user.md`). Custom/AI styles persist in `user_prompts/` (`/api/styles*`,
  `/api/styles/generate`). **Styles own voice/tone.**
- **Generator presets** (`pipeline/generator_presets.py`, `_PRESET_DEFS`, exposed at
  `/api/options.generator_presets`): `claude_exam`, `claude_review`, `claude_cram`. Each
  carries a **full system prompt + tuned sampling params**. They inject their system prompt
  then **append `MARKDOWN_MATH_SYSTEM`**. Presets tune **sampling only** — they **never
  hard-pin** provider/model (`model_hint` is a soft advisory; the preset card shows an
  advisory, non-blocking compatibility warning only on a confident model mismatch). Display
  fields (`purpose`/`recommended_use`/`model`) are additive and display-only — no
  resolution path reads them.
- **Outline quick-templates** (`pipeline/presets.py`, exposed at `/api/presets`):
  `exam_guide`, `report_guide`, `presentation`, `chapter_summary`, `final_revision` — outline
  *section bundles* for the Builder **Outline** tab. **Different registry from generator
  presets.**
- **Sections + axes:** `include_sections` (canonical dict-of-bool, source of truth
  `INCLUDE_SECTION_FRAGMENTS`), `output_depth`, `difficulty` — see §8. Frontend
  `sectionMeta.js` holds labels/grouping only; the backend owns the key set.
- **Outline** (`OutlineEditor.jsx`, `POST /api/outline/generate`): editable sections +
  templates + AI draft; injected as a "Required Outline" directive and summarized in Job
  Details. Outline ordering relies on model compliance (strong directive, not enforced/
  repaired post-generation).

---

## 16. Library, Jobs, Artifacts, Trash, Exports

- **Library** (`pipeline/library_store.py`, `library/folders.json` + `job_folders.json`):
  folders (create/rename/delete), single + batch move, save-to-folder on generate, and
  client-side search/filter/sort over `GET /api/library` (server params exist and are used
  by smoke tests, but the UI fetches all jobs once — pagination deferred).
- **Jobs** (`pipeline/job_manager.py`): each job is a directory `jobs/<id>/` with
  `job.json` manifest (title, status, attachments[] with filename/mode/extracted_chars/
  warnings, page_selections, generator_preset, include_sections, axes, provider/model,
  favorite). Coarse status + finer stage/progress; cooperative cancel via sidecar marker.
- **Artifacts:** `final.pdf`, `final.docx` (lazy from clean.md), `final.html`, `clean.md`,
  `validation.json`, `render.log`, plus extracted source, version snapshots, and Ask
  session data. Served via `GET /api/jobs/{id}/artifacts/{name}`.
- **Versions:** every `save_clean_md` snapshots; `…/versions`, `…/versions/{v}/clean_md`,
  `…/revert/{v}`, plus manual `GET/PUT …/clean_md` editing (routed through the chokepoint).
- **Trash (load-bearing safety):** soft-delete moves `jobs/<id>/` → `jobs/.trash/<id>/`
  (reversible). **Permanent purge can act ONLY on a job already inside `jobs/.trash/`,
  behind a path assertion that hard-fails any id resolving outside the trash dir.** Active
  jobs can never be hard-deleted directly. Bulk purge (`POST /api/jobs/bulk/purge`) just
  **loops the guarded single-item purge** — no new raw-delete path; bogus/traversal/active
  ids are rejected without touching disk.
- **Exports** (`ExportsWorkspace.jsx`, `GET /api/exports`, `POST /api/exports/bundle`):
  per-job artifact downloads + filters + multi-job **ZIP bundles** with an in-zip
  `manifest.json`. Chat history is never included in any export.
- **Quizzes:** `POST /api/jobs/{id}/quiz` + `…/quizzes` + `…/quizzes/{n}/export`
  (CSV / Anki / Quizlet).

---

## 17. Security And Secret-Handling Invariants

**Core invariant: raw secrets must NEVER appear in any of these surfaces:**
`/api/options`, `/api/provider-settings`, `/api/local-model/*`, `/api/ask/*`, logs,
`job.json`, exports, served JS, docs with real values, frontend state, session/history/
cache files, or command output pasted to chat. Keys are **server-side only**, write-only
over the API, and redacted out of every response **by construction** (the public DTO has no
key field). The frontend never receives a raw key — only derived non-secret info
(`configured`, `key_source`, last-4 `key_hint`, `base_url_host`).

**`.env` handling:** `.env` (and `.env.save`) contain real local API keys, are gitignored +
dockerignored, and **must never be committed**. They are not baked into the Docker image.

**Do not paste full `docker compose config` output anywhere** — it expands env values
(secrets) in plaintext. For a compose syntax check, redirect to a temp file only:
`docker compose config >/tmp/compose-check.txt` (and do not include its contents).

**LMM controls must NOT expose:** raw companion token, socket path, absolute host model
path, raw argv, `Authorization` header, full URLs with secrets, executable path, unbounded
logs, or tracebacks. Backend LMM DTOs whitelist fields, bound + redact log tails, reject
absolute returned paths, and return root-relative model paths only.

**LMM boundary invariants (must hold):**
- Docker backend must **not** directly browse the host filesystem.
- Docker backend must **not** directly start/stop host processes.
- The React frontend must **never** talk directly to the host companion (only via the
  backend bridge).
- Companion config, approved roots, and real process control are **host-side / operator-
  owned**.
- **No Docker socket, no privileged container, no host PID namespace, no whole-PC scan, no
  browser-provided arbitrary host path.** Approved roots come from companion config only —
  there is **no browser folder picker**.

**Other security/safety facts:** shortcut import/export is whitelist-parsed (untrusted-input
boundary); `saved_prompt` is opt-in user content (not a secret) and carries length-only in
inspect; Ask is local-only and stores no secrets; trash-before-purge prevents accidental
destructive loss.

---

## 18. Docker / Deployment / Runtime Assumptions

- **Same-origin, single container, port 8000**, `restart: unless-stopped`.
- **Multi-stage build:** `node:20-slim` builds the frontend → `python:3.12-slim` runtime
  with chromium + nodejs/npm + tesseract-ocr(+eng) + gosu. `frontend/dist` is built in the
  image, never copied from host (enforced by `.dockerignore`).
- **Non-root:** `appuser` (uid 10001); entrypoint creates/chowns runtime dirs then drops
  privileges via `gosu`. `security_opt: no-new-privileges:true`.
- **Resource limits:** `mem_limit: 2g`, `pids_limit: 256`, `cpus: 2.0`, `shm_size: 512m`
  (Chromium headroom).
- **Volumes (persist across restarts):** `./jobs`, `./user_prompts`, `./library`, `./config`.
- **`extra_hosts: host.docker.internal:host-gateway`** lets the container reach a host-run
  `llama-server` once a local base URL is configured.
- The committed `docker-compose.yml` has **no companion socket mount and no LMM env** —
  all LMM validation uses temporary, non-committed Compose overrides.
- **Deferred Docker work:** GHCR publish workflow + prebuilt `image:` line, and a fully
  pinned `requirements.txt` lockfile (must be regenerated from the current tree, not lifted
  from the divergent `hardening` branch).

---

## 19. Tests And Validation Harnesses

`test_scripts/` holds smoke + focused + live-validation harnesses (the running Docker image
does not necessarily include `test_scripts/`; many pure checks skip the endpoint sections
when FastAPI is unavailable in host Python):

- **End-to-end smoke:** `smoke_release.py` (release check, ~28 checks), plus
  `smoke_docx_exports`, `smoke_exports_center`, `smoke_library_bulk`,
  `smoke_library_power_tools`, `smoke_outline_backend`, `smoke_outline_full`, `smoke_quiz`,
  `smoke_save_to_folder`.
- **Ask:** `test_ask_context_inventory`, `test_ask_context_prepare`, `test_ask_local_chat`.
- **Provider/settings:** `test_provider_settings_store`, `test_provider_runtime_settings`,
  `test_provider_fetch_models`, `test_default_provider_precedence`.
- **Shortcuts:** `test_shortcut_store`, `test_shortcut_inspector`, `test_shortcut_repair`.
- **Large-PDF / extraction / math:** `test_pdf_preflight`, `test_page_selections`,
  `test_pdf_page_selection_extract`, `test_mixed_pdf_ocr`, `test_math_regressions`,
  `test_long_formula_guidance`, `test_page_reference_format`, `test_markdown_sections`.
- **Jobs:** `test_cancel_job`, `test_retry_generator_preset`.
- **LMM:** `test_local_model_status`, `test_local_model_command_profile`,
  `test_local_model_companion_scan`, `test_local_model_companion_bridge`,
  `test_local_model_companion_process_{manager,api,bridge}`,
  `test_local_model_companion_real_profile`, `test_local_model_library_selection`,
  `test_lmm_phase2_final_regression`, `test_lmm_real_profile_e2e_harness`.
- **LMM live/manual (require explicit env, skip otherwise):**
  `validate_lmm_companion_socket_mount`, `validate_lmm_real_llama_server`,
  `validate_lmm_real_profile_e2e`.
- **Frontend node harnesses (`frontend/scripts/`):** `verify-assets`, `verify-ask-guide`,
  `verify-local-model-{status,command,library}`,
  `verify-shortcut-{status,form,repair,activation}`.

Standard verification loop (from `CLAUDE.md` §4): `npm --prefix frontend run build` →
`python -m compileall api pipeline` → `docker compose config` / `build` / `up` →
`curl /api/health` + `/api/options` → `smoke_release.py`. **Backend changes must be proven
with a live run, not just by reading source.**

---

## 20. Important Real Validation Facts

Preserve exactly (LMM real-model validation):

```text
/usr/bin/llama-server exists and was used.
LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models.
Model: gemma-4-26B-A4B-it-UD-Q4_K_M.gguf.
CPU-safe validation passed with port=18080, ctx_size=4096, gpu_layers=0, threads=8.
Full GPU/offload gpu_layers=999 failed safely with CUDA OOM and was classified model_may_be_too_large.
gpu_layers=999 must not be treated as a default for large models.
```

- CPU-safe **real lifecycle + real configured-profile E2E** validation **PASSED** (Phase
  2G5 / 2G8): the backend/companion path selected the real profile/model, reached `running`
  readiness via `/v1/models`, stopped cleanly, and released the port. Redaction passed (no
  token / socket path / absolute model root / executable path / Authorization / full URL /
  raw argv; model paths root-relative only).
- **High-GPU-offload validation has NOT passed.** `gpu_layers=999` failed safely before
  readiness (CUDA OOM / `model_may_be_too_large`) on the 26B model on 16GB VRAM. Do **not**
  describe high-GPU-offload as validated, and do **not** use `gpu_layers=999` as a default
  for large models. Practical GPU defaults still need a follow-up.
- Manual command-helper defaults are **CPU-safe first** (`-c 4096 -ngl 0 --threads 8`), with
  GPU balanced (`-c 4096 -ngl 20 --threads 8`) and low-memory (`-c 2048 -ngl 0 --threads 8`)
  presets; full offload `-ngl 999` remains an advanced, explicitly risky / may-OOM option
  only — never the default.
- Ask local-model compatibility: with the Gemma `llama-server` setup,
  `/v1/chat/completions` could return HTTP 200 with empty visible `content` (answer only in
  `reasoning_content`, `finish_reason: length`); the `/no_think` model-only marker restored
  visible content. This is why the empty-response guard and `/no_think` marker exist.
- Provider Settings validation findings: Test-connection empty-content acceptance and the
  stored-`default_provider`-as-default tier both came from validation
  (`docs/VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md`).
- Other validation records: `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`,
  `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`,
  `docs/MATH_PDF_FIDELITY_INVESTIGATION.md`.

---

## 21. Deferred Features / Future Roadmap

**Generation/UI deferred (from `FEATURE_STATUS.md`):** saved/reusable outline templates as
presets; drag-and-drop reordering (outline/library); server-side pagination shared by
Library/Exports; a second PDF theme / theme-picker; wiring the cosmetic "Save draft" button
(and the decorative storage meter); streaming LLM responses; multimodal/image understanding.

**Large-PDF deferred:** automatic split/chunk processing; hybrid embedded-text + OCR dedup;
raising `MAX_UPLOAD_MB`; persisting the preflight report; carrying page selections into
drafts/shortcuts. Provider-aware truncation caps (Option B).

**Ask deferred:** extra session uploads (explicit slice), streaming, hosted/cloud Ask,
rolling chat summary, multimodal, process control.

**LMM deferred (require separate design):** the **approve-root flow** (separately designed
host-companion flow), app-suggested settings/recommendations, Ollama/simple-local-model
path, Windows/macOS packaging/support, model downloads. **LMM Phase 2 is paused.**

**Docker deferred:** GHCR publish + prebuilt image; pinned requirements lockfile.

**Memory pointer:** `MEMORY.md` records a deferred follow-up — PDF page-anchor +
attachment-truncation slices (`generator-presets-followups.md`).

---

## 22. Known Risks And Fragile Areas

- **The PDF/Chromium pipeline is load-bearing and tuned** — do not rewrite casually. Cancel
  deliberately never interrupts mid-Chromium-render (uninterruptible external wait).
- **The math sanitizer + KaTeX validation are load-bearing** — degrade-not-fail behaviour
  must be preserved; don't make a bad equation fail a whole job.
- **`/api/jobs/llm` has two non-shared request-parsing paths (JSON + multipart).** Any new
  `LLMJobRequest` field must be wired into `_parse_llm_request` AND verified in both paths;
  a compile check + no-attachment smoke will NOT catch a multipart-only drop. This has bitten
  the project (C3) and is a permanent rule.
- **`clean.md` chokepoint:** never write `clean.md` directly; route through
  `JobManager.save_clean_md` or version history breaks.
- **Trash/purge path guard:** never add a delete primitive that can act outside
  `jobs/.trash/`; loop the existing guarded purge.
- **No migration-on-read:** inspect/preview (shortcuts) and read paths must not rewrite
  on-disk JSON; the only writes are explicit user actions.
- **Cancel state is a sidecar marker, NOT a `job.json` field** (avoids a lost-update race
  with the worker's manifest writes). Do not move it into the manifest.
- **`CLAUDE.md` is stale** relative to the current feature set (no LMM/Ask/quiz/section-regen/
  version mentions in its route list). Trust the code + `PROJECT_CONTEXT.md` /
  `CURRENT_TASK.md`. (This is the main doc/implementation discrepancy found — see below.)
- **LMM has many redaction surfaces.** Any new LMM response field risks leaking a token /
  socket path / absolute host path / raw argv — every LMM DTO must be re-checked against the
  §17 exposure list.
- The `styles/` top-level directory is empty (the real built-in prompts live in `prompts/`;
  custom/AI styles live in `user_prompts/`). Don't confuse `styles/` (empty) with the styles
  *system*.

---

## 23. Rules For Future AI Agents

1. **Branch from `chrome-renderer-v1`.** Never revive/merge/rebase/cherry-pick old consumed
   branches. **Do not force-push.**
2. **Use Codex-formatted implementation prompts** unless the user switches back to Claude
   Code.
3. **One slice per branch**, surgical edits not rewrites, verify-and-commit between each
   (build + compile + docker + smoke). Prove backend changes with a live run.
4. **Keep load-bearing invariants:** same-origin Docker, `/api/*` precedence over the SPA
   mount, the Claude-style UI baseline, the PDF/Chromium + math pipeline, the `save_clean_md`
   chokepoint, trash-before-purge, math-degrades-not-fails, cancel-as-sidecar-marker,
   no-migration-on-read.
5. **Secrets never leak** to the §17 surfaces. Don't paste full `docker compose config`
   output. Keep keys server-side and write-only.
6. **LMM stays inside its boundary:** no direct Docker→host filesystem/process access, no
   frontend→companion calls, no Docker socket / privileged container / host PID namespace /
   whole-PC scan / browser host-path picker. Approved roots come from companion config only.
   **LMM Phase 2 is paused** — resume only with a separately designed approve-root flow or
   packaging slice. `gpu_layers=999` is not a default.
7. **Ask Your Guide stays local-only** (no DeepSeek/Qwen/cloud fallback) unless explicitly
   redesigned; it never writes job artifacts and never controls processes.
8. **Provider Settings is the single config writer** — don't add a second writer in LMM/Ask.
   `model_hint` is a soft advisory, never a hard pin.
9. **Two-path rule for `/api/jobs/llm`** (JSON + multipart) — wire and verify both.
10. **Frontend never owns the section/axis/preset key set** — add backend fragments first.
11. **Generator presets ≠ outline quick-templates ≠ styles** — three registries; don't
    conflate (the shortcut Edit modal regression proves this matters).
12. **Don't begin deferred work without an explicit slice/sign-off.** When uncertain about
    current state, prefer `PROJECT_CONTEXT.md` / `CURRENT_TASK.md` / the code over the stale
    `CLAUDE.md`.

---

## 24. Quick File Map

| Area | Key files |
| --- | --- |
| FastAPI app / routes | `api/server.py` |
| Provider config / resolution / LMM status | `pipeline/provider_config.py` |
| Model call boundary | `pipeline/llm_client.py` |
| Provider settings store | `pipeline/provider_settings_store.py` |
| Prompt assembly (sections/axes/math) | `pipeline/orchestrator.py` |
| Job execution | `pipeline/run_llm_job.py`, `run_markdown_job.py`, `job_stages.py` |
| Job manager / clean.md / trash / cancel | `pipeline/job_manager.py` |
| Extraction / OCR / preflight | `pipeline/extract.py` |
| Renderers | `pipeline/pdf_renderer.py`, `html_renderer.py`, `docx_renderer.py` |
| Math | `pipeline/math_validator.py`, `markdown_sanitizer.py` |
| Sections | `pipeline/markdown_sections.py`, `section_scorer.py` |
| Styles / presets | `pipeline/style_store.py`, `generator_presets.py`, `presets.py`, `prompt_loader.py` |
| Library / shortcuts | `pipeline/library_store.py`, `shortcut_store.py` |
| Ask Your Guide | `pipeline/ask_inventory.py`, `ask_context.py`, `ask_sessions.py` |
| LMM backend bridge / selection | `pipeline/local_model_companion_client.py`, `local_model_library_selection.py` |
| Host companion (NOT in image) | `tools/local_model_companion/{config,model_library,profiles,process_manager,companion}.py` |
| Frontend shell / workspaces | `frontend/src/components/DesktopDashboard.jsx` + `*Workspace.jsx` + `HomeShortcuts.jsx` + `LocalModelsPanel.jsx` + `ShortcutInspector.jsx` |
| Frontend pure helpers | `frontend/src/{api/client,askGuide,localModel*,shortcut*,*Meta}.js` |
| Built-in style prompts | `prompts/*.md` |
| PDF theme | `themes/claude_clean.css` |
| Docker | `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, `.dockerignore` |
| Canonical docs | `CLAUDE.md`, `docs/PROJECT_CONTEXT.md`, `docs/CURRENT_TASK.md`, `docs/DECISIONS.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/FEATURE_STATUS.md` |
| Design docs | `docs/{ASK_YOUR_GUIDE,PROVIDER_SETTINGS,SHORTCUT_INSPECTOR_REPAIR,LARGE_PDF_PREFLIGHT,LOCAL_MODEL_MANAGER,LOCAL_MODEL_MANAGER_PHASE2}_DESIGN.md` |
| Operator/runtime docs + examples | `docs/LOCAL_MODEL_MANAGER_{OPERATOR_SETUP,RUNTIME_SERVICE}.md`, `docs/examples/` |
| Validation records | `docs/VALIDATION_*.md`, `docs/MATH_PDF_FIDELITY_INVESTIGATION.md` |

---

## 25. Recommended Next Work Options

These are *options*, not started work — each needs an explicit slice and sign-off. Listed
to orient a fresh session, not to authorize action.

1. **Keep LMM Phase 2 paused** (current recommendation). If LMM is resumed, the next slice
   must be a **separately designed approve-root flow** (host-companion) or a **packaging/
   runtime-service** slice — not start/stop changes.
2. **Practical GPU defaults follow-up** for LMM: `gpu_layers=999` OOMs large models on 16GB
   VRAM; a balanced/auto offload recommendation needs design (overlaps with the deferred
   "app-suggested settings", which is itself deferred — do not assume it).
3. **Ask Your Guide extra session uploads** as a separate explicit slice (reuse `extract.py`,
   session-scoped, never merged into the job), or narrow bug-driven Ask polish.
4. **Math/PDF font-size rationalization** (see `docs/MATH_PDF_FIDELITY_INVESTIGATION.md`).
5. **Outline ordering enforcement/repair** post-generation (currently compliance-only).
6. **Doc reconciliation:** refresh `CLAUDE.md` to match the current feature set (its route
   list and "confirmed baseline" predate LMM/Ask/quiz/section-regen/versions). This is a
   docs-only cleanup — see the follow-up note in the final response.
7. Other deferred items (pagination, drag-and-drop, second PDF theme, streaming, Save-draft
   wiring) — each its own slice.
