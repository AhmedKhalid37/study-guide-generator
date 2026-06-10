# Project Full Inspection Report — GuideForge / Study Guide Generator

> **Purpose.** A detailed, evidence-based snapshot of the repository as it stands,
> produced by reading both the docs **and** the implementation and reconciling the
> two. Intended as input for an independent session (Claude / ChatGPT / Codex) to
> build a next-steps roadmap. **This is a docs/report-only artifact** — no
> application code was changed in producing it.
>
> **Source-of-truth rule.** The running code is authoritative. Where docs and code
> disagree, the discrepancy is called out and the code is trusted. Uncertain items
> are explicitly marked `UNCERTAIN`.
>
> **Generated:** 2026-06-10. **Branch:** `chrome-renderer-v1`. **HEAD:**
> `eaa1263` ("Slice 16: Post-reskin release audit + checkpoint").
> **Working tree:** clean (per `git status --short`).
>
> **Relationship to existing docs.** This complements `docs/PROJECT_DEEP_CONTEXT_REPORT.md`
> (dated 2026-06-08, pre-Slice-12). That report remains accurate for architecture
> and the feature stacks up to Slice 11; this report adds the Slices 12–16 reskin/UX
> phase, refreshes the route inventory against current `api/server.py`, and reframes
> everything toward roadmap selection.

---

## 1. Executive Summary

**What the app is.** GuideForge / Study Guide Generator is a Dockerized,
**same-origin React (Vite + Tailwind) + FastAPI** application for a single operator
or small group. It turns pasted text, uploaded Markdown, or uploaded attachments
(PDF/DOCX/PPTX/TXT/CSV, with Tesseract OCR for image-only PDF pages) into clean,
exam-focused **study guides** rendered to **PDF** (headless Chromium), **HTML**,
**DOCX**, and **Markdown**. It also generates **quizzes/flashcards** (CSV / Anki /
Quizlet export) and provides a **local-model-only "Ask Your Guide"** grounded chat.

Seven workspaces (nav ids in `DesktopDashboard.jsx`): **Home** · **Builder** ·
**Library** · **Ask Guide** · **Styles** · **Models** (Provider Settings + Local
Models) · **Exports**, plus a **Help** workspace (`HelpWorkspace.jsx`, not in the
seven-nav summary but present).

**Current maturity level.** **Mature feature-complete v1 for its stated scope.**
Multiple substantial, well-documented, and (mostly) validated feature stacks are
integrated on the trunk. The most recent phase (Slices 1–16) was a full **GuideForge
visual reskin + UX redesign** to a semantic CSS system, now declared complete. The
backend route surface is large (≈80 routes) and the security model is carefully
constructed. Release smoke (`smoke_release.py`) reports **28 passed / 0 failed / 0
skipped**.

**Current strongest features.**
- **Provider Settings** — in-app provider/key/model/runtime config with a physically
  separated secret store and write-only keys (complete, validated).
- **Generation pipeline** — deterministic prompt assembly, two input transports,
  staged jobs with cooperative cancel, version snapshots, section regeneration,
  retry, re-render.
- **Rendering** — tuned headless-Chromium PDF + KaTeX HTML + lazy DOCX.
- **Library / Trash / Exports** — folders, batch move, trash-before-purge safety,
  multi-job ZIP bundles.
- **Shortcut Inspector / Repair Loop** — 3-tier validity, whitelist-patch repair.
- **Local Model Manager (Phase 1 + Phase 2, paused)** — careful Docker→host
  companion boundary, validated on a real `llama-server`.
- **Ask Your Guide** — local-only grounded chat with enforced citation contract.
- **Reskin** — a 773-class semantic `.sg-*` CSS design system across all workspaces.

**Current weakest / riskiest areas.**
- **No verification/measurement layer.** "Math validation" is **KaTeX render/parse
  validation only** (does LaTeX compile), **not mathematical correctness**. There is
  no eval harness, no factuality check, no structure/outline lint beyond compliance
  reporting. This is the single biggest product gap and is the documented next phase.
- **Ask retrieval is a dependency-free lexical (TF/IDF-ish) index**, no embeddings /
  vector store / reranker. Fine as a v1 but a clear upgrade target.
- **Very large frontend components.** `BuilderWorkspace.jsx` (3,429 LOC),
  `RecentJobsPanel.jsx` (2,005), `HomeShortcuts.jsx` (1,671), `LibraryWorkspace.jsx`
  (1,579), `LocalModelsPanel.jsx` (1,646), and a **200 KB / 3,228-line
  `design-system.css`**. Maintainability/onboarding risk.
- **Dead code / dead branches** left in place by the reskin checkpoint (documented:
  non-embedded `RecentJobsPanel`/`PreviewPanel` branch, `Tile`, `MetaRow`, mockup
  components, `PasteGenerationPanel`, `data/mockups.js`).
- **Stale tests.** `npm run test` (`verify-assets.mjs`) targets the old mockup tree
  and is a known non-blocker but still wired as the default `test` script.
- **`CLAUDE.md` route list is stale** vs. the real surface (the deep report already
  flags this).
- **Provider breadth is narrow** — DeepSeek + Qwen verified; no Gemini/OpenAI/Mistral
  first-class entries; no OCR provider beyond Tesseract.

**Recommended next phase.** A **correctness / measurement layer**, beginning with a
**deterministic math verification core** and an **eval harness Phase 1**, then
surfacing verification results into validation artifacts / JobDetails. This is the
direction the project's own handoff docs point to and it addresses the biggest gap
(quality is currently unmeasured). See §14 for candidate slices and priorities.

---

## 2. Architecture Map

### 2.1 Backend structure (`api/` + `pipeline/`)

- **`api/server.py` (~3,800 LOC)** — the single FastAPI app. Owns all `/api/*` route
  definitions and request DTOs (Pydantic, e.g. `LLMJobRequest`, `QuizRequest`),
  delegating real work to `pipeline/`. The SPA static mount is registered **last** so
  `/api/*` always wins.
- **`pipeline/` (~10,700 LOC across 31 modules)** — all backend logic. Largest:
  `shortcut_store.py` (1,561), `provider_config.py` (1,143),
  `local_model_companion_client.py` (932), `ask_sessions.py` (762),
  `markdown_sanitizer.py` (751). Key roles:
  - Provider/model resolution + redaction + discovery: `provider_config.py`,
    `llm_client.py` (single model-call boundary), `provider_settings_store.py`.
  - Prompt assembly: `orchestrator.py` (canonical section/axis key sets).
  - Job execution: `run_llm_job.py`, `run_markdown_job.py`, `job_stages.py`,
    `job_manager.py` (the `save_clean_md` chokepoint + versions + cancel + trash).
  - Ingestion: `extract.py` (per-page text/OCR + `preflight_pdf`), `input_handler.py`.
  - Rendering: `pdf_renderer.py`, `html_renderer.py`, `docx_renderer.py`.
  - Math/markdown: `math_validator.py`, `markdown_sanitizer.py`, `markdown_sections.py`.
  - Styles/presets: `style_store.py`, `generator_presets.py`, `presets.py`,
    `prompt_loader.py`.
  - Library/shortcuts: `library_store.py`, `shortcut_store.py`.
  - Ask: `ask_inventory.py`, `ask_context.py`, `ask_sessions.py`.
  - LMM bridge: `local_model_companion_client.py`, `local_model_library_selection.py`.
  - Errors: `errors.py` (`classify_exception`, `VALID_CATEGORIES`).
  - **Note (discrepancy):** the deep report lists `pipeline/section_scorer.py`; it
    does **not** exist in the current tree (`pipeline/` has no `section_scorer.py`).
    Section parsing lives in `markdown_sections.py`. `UNCERTAIN` whether it was
    removed or never added — treat the deep-report reference as stale.

### 2.2 Frontend structure (`frontend/src/`)

- Entry: `main.jsx` → `App.jsx` → `GlowBackground` + `DesktopDashboard`.
- **`components/` (~16,500 LOC across 32 files)** — workspaces + primitives. Largest
  are the workspace files (see §1 weakest areas).
- **Pure helper modules (`src/*.js`, React-free, node-testable):** `api/client.js`
  (823 LOC, all fetch helpers), `askGuide.js`, `localModel{Status,Command,Library,
  Server}.js`, `shortcut{Status,Repair}.js`, `styleCompare.js`, and `*Meta.js`
  display-metadata files (`styleMeta`, `folderMeta`, `presetMeta`, `sectionMeta`,
  `shortcutMeta`).
- **`design-system.css` (200 KB, 3,228 lines, 773 `.sg-*` selectors)** — the
  GuideForge semantic stylesheet. Tailwind is configured but **its utilities are
  inert in the live UI** — real styling comes from `.sg-*` classes and element
  cascades. This is a deliberate, documented decision (DECISIONS, Slice 5b).
- **`scripts/*.mjs`** — pure-node verify harnesses (no test runner).

### 2.3 Pipeline structure (generation flow)

Three input transports → job pipeline → artifacts. Detailed in §5.

### 2.4 Runtime / data directories (all gitignored)

`jobs/` (job artifacts + `jobs/.trash/`), `user_prompts/` (custom/AI styles +
`styles.json`), `library/` (`folders.json`, `job_folders.json`, `shortcuts.json`),
`config/` (`provider_settings.json`, `secrets.json`, `local_model_library_selection.json`),
`output/` (convenience copies). `.env` / `.env.save` hold real keys and are
gitignored + dockerignored. **Confirmed in `.gitignore`:** `jobs/`, `user_prompts/`,
`library/`, `config/`, `.env`, `.env.save`. The working tree currently holds ~150
job directories under `jobs/` (runtime data, not tracked).

### 2.5 Docker / same-origin serving model

- Single container, port **8000**, `uvicorn api.server:app`. Multi-stage build:
  `node:20-slim` builds the frontend → `python:3.12-slim` runtime with **chromium**,
  **nodejs/npm**, **tesseract-ocr(+eng)**, **gosu**. `frontend/dist` is built inside
  the image, never copied from host.
- Non-root: `appuser` uid **10001**; entrypoint chowns mounts then drops privileges;
  `no-new-privileges:true`.
- `frontend/dist` mounted as SPA catch-all at `/` **after** all API routes.
- Committed `docker-compose.yml` has **no companion socket mount and no LMM env** —
  LMM validation uses temporary, non-committed overrides.

### 2.6 Important invariants (must hold)

- `/api/*` routes registered before the SPA mount (precedence).
- All `clean.md` writes go through `JobManager.save_clean_md` (auto-snapshots).
- Trash-before-purge: permanent delete acts only inside `jobs/.trash/`.
- `/api/jobs/llm` has **two non-shared parsing paths** (JSON body vs multipart);
  any new `LLMJobRequest` field must be wired into both.
- Cancel is a sidecar marker file, never a `job.json` field, never a process kill.
- Math validation **degrades, never fails** a job.
- Secrets never reach any API response, log, artifact, export, or served JS.
- LMM boundary: backend never touches host FS/processes directly; frontend never
  talks to the companion directly; approved roots come from companion config only.
- Frontend never owns the section/axis/preset key set (backend is canonical).

---

## 3. Route / API Inventory

Verified from `api/server.py` (decorator scan). ~80 routes. Grouped by feature.
Read/write noted; security constraints summarized.

### 3.1 Health / options
- `GET /api/health` — liveness. Read.
- `GET /api/options` — UI bootstrap: providers (redacted), styles, generator presets,
  section/axis vocab, etc. Read. **Security:** no raw keys (redacted DTO only).

### 3.2 Jobs / generation
- `POST /api/jobs/paste` — pasted text → markdown job. Write.
- `POST /api/jobs/upload-markdown` — `.md`/`.markdown` upload → markdown job. Write.
- `POST /api/jobs/llm` — LLM generation. Write. **Two parsing paths** (JSON +
  multipart-with-attachments). Body ≈ `LLMJobRequest` (style/preset, `include_sections`,
  `output_depth`, `difficulty`, provider/model, outline, attachments, `page_selections`).
- `GET /api/jobs` — list jobs (server params exist; UI fetches all). Read.
- `GET /api/jobs/{id}` — manifest. Read.
- `GET /api/jobs/{id}/progress` — coarse status + stage/progress (Builder polls). Read.
- `POST /api/jobs/{id}/cancel` — writes sidecar cancel marker. Write (cooperative).
- `GET /api/jobs/{id}/error` — classified error detail. Read.
- `POST /api/jobs/{id}/retry` — gated to `failed`. Write.
- `POST /api/jobs/{id}/rerender` — regenerate PDF/HTML (keeps DOCX in sync). Write.
- `POST /api/jobs/{id}/favorite` — toggle favorite. Write.
- `GET /api/jobs/{id}/artifacts/{name}` — serve a job artifact. Read. **Security:**
  name is validated; chat/session data not served as a generic artifact.

### 3.3 Versions / sections / regeneration
- `GET /api/jobs/{id}/versions`, `GET …/versions/{v}/clean_md`,
  `POST …/revert/{v}` — version history + revert (rides `save_clean_md`). Read/Write.
- `GET /api/jobs/{id}/clean_md`, `PUT …/clean_md` — manual markdown edit (chokepoint).
- `GET /api/jobs/{id}/sections` — parsed section list. Read.
- `GET /api/jobs/{id}/outline_compliance` — outline-vs-output compliance. Read.
- `POST /api/jobs/{id}/sections/{idx}/regenerate` — regenerate one section. Write.

### 3.4 Quizzes / flashcards
- `POST /api/jobs/{id}/quiz` — generate quiz from `clean.md`; validates
  `question_types`, `count` (∈ `VALID_QUIZ_COUNTS`), `difficulty`. Write.
- `GET /api/jobs/{id}/quizzes`, `GET …/{n}`, `GET …/{n}/export` — list / fetch /
  export (CSV / Anki / Quizlet). Read.

### 3.5 Attachments / preflight
- `POST /api/preflight/pdf` — read-only bounded page-sample inspection before job
  creation; returns `verdict` (`ok`/`warn`/`blocked`) + `warnings[]` +
  `allowed_actions[]`. **Fails open** (only encrypted/corrupt → `blocked`).

### 3.6 Library / folders / favorites / trash
- `GET /api/library` — jobs + folder assignment. Read.
- `GET /api/library/folders`, `POST …`, `PUT …/{id}`, `DELETE …/{id}` — folder CRUD.
- `POST /api/library/jobs/move`, `POST …/{id}/move` — batch + single move. Write.
- `POST /api/jobs/bulk/{delete,restore,move,purge}` — bulk ops. Write. **Security:**
  bulk purge loops the guarded single-item purge (no new raw-delete path).
- `GET /api/jobs/trash`, `POST /api/jobs/{id}/trash`, `POST …/restore`,
  `DELETE /api/jobs/trash`, `DELETE /api/jobs/trash/{id}` — trash lifecycle.
  **Security:** purge path-asserts inside `jobs/.trash/`.
- Favorites: `POST /api/jobs/{id}/favorite` (see §3.2).

### 3.7 Exports / bundles
- `GET /api/exports` — exportable artifacts + filters. Read.
- `POST /api/exports/bundle` — multi-job ZIP with in-zip `manifest.json`. Write
  (produces download). **Security:** chat history never included.

### 3.8 Styles
- `GET /api/styles`, `GET …/{id}`, `POST /api/styles`, `PUT …/{id}`,
  `DELETE …/{id}` — style CRUD. Read/Write.
- `POST /api/styles/generate` — AI style generation (LLM). Write.

### 3.9 Outline presets / generation
- `GET /api/presets` — outline quick-templates (section bundles). Read.
- `POST /api/presets/{id}/apply` — apply a quick-template. Write (returns outline).
- `POST /api/outline/generate` — AI outline draft. Write.

### 3.10 Shortcuts / inspect / repair
- `GET /api/shortcuts`, `…/export`, `POST /api/shortcuts`, `POST …/reorder`,
  `POST …/defaults/reset`, `POST …/import/preview`, `POST …/import`,
  `GET/PUT/DELETE /api/shortcuts/{id}`, `GET …/{id}/export`. CRUD + import/export.
- `GET /api/shortcuts/{id}/inspect` — redacted repair candidates (no write). Read.
- `POST …/{id}/repair/preview` — read-only repair preview. Read.
- `POST …/{id}/repair/apply` — **the only write path** for repair (explicit
  whitelisted patch; unknown key → 400; no provider/model auto-switch).

### 3.11 Provider settings
- `GET /api/provider-settings` — redacted provider config. Read.
- `PATCH /api/provider-settings`, `PATCH …/{provider}` — update. Write.
  **Security:** keys write-only; blank `api_key` is a no-op, never a clear.
- `POST …/{provider}/clear-key` — explicit key clear. Write.
- `POST …/{provider}/test` — connection test (empty-content choice = success). Write.
- `POST …/{provider}/fetch-models` — read-only model discovery (does not persist).

### 3.12 Local Model Manager
- `GET /api/local-model/status`, `POST /api/local-model/check` — local server status.
- `GET /api/local-model/command-profile` — static whitelisted start-command helper.
- `GET /api/local-model/companion/status` — companion reachability (via bridge).
- `GET /api/local-model/library`, `POST …/library/scan` — approved-root GGUF scan.
- `GET/POST/DELETE /api/local-model/library/selection` — app-side selected model.
- `GET /api/local-model/server/status`, `GET …/server/profiles`,
  `POST …/server/{start,stop,restart}` — companion-managed `llama-server` lifecycle.
  **Security:** DTOs whitelist fields; never expose token, socket path, absolute host
  path, executable path, raw argv, Authorization header, or full URLs.

### 3.13 Ask Guide
- `GET /api/ask/jobs` — guides eligible for Ask. Read.
- `GET /api/ask/jobs/{id}/context` — context readiness/inventory. Read.
- `POST /api/ask/jobs/{id}/prepare` — build/reuse context index cache. Write
  (idempotent `hit`/`built`/`rebuilt`).
- `POST /api/ask/jobs/{id}/sessions`, `GET …/sessions` — create/list sessions.
- `GET /api/ask/sessions/{sid}` — session detail. Read.
- `POST /api/ask/sessions/{sid}/message` — chat turn; **local-only**, status-gated
  (offline → structured `local_offline`, no model call). Write.
- `DELETE /api/ask/sessions/{sid}/history`, `DELETE /api/ask/sessions/{sid}` —
  clear history / delete session. Write. **Security:** no secrets in session files;
  never auto-exported.

### 3.14 Static
- `app.mount("/", StaticFiles(directory=frontend/dist, html=True))` — SPA fallback,
  registered last.

> **Discrepancy:** `CLAUDE.md`'s "Key API routes" shortlist is far smaller than the
> real surface (quizzes, sections/regen, versions/revert, outline compliance, bulk,
> trash, full LMM + Ask). `api/server.py` is authoritative. The deep report already
> notes this.

---

## 4. Frontend Workspace Inventory

### 4.1 Home (`HomeShortcuts.jsx`, 1,671 LOC; `RecentJobsPanel.jsx` embedded)
- **Implemented:** hero + Quick Launch shortcut carousel, Favorite Guides, Recent
  Guides, shortcut tiles with 3-tier validity badges. Activation gated through pure
  `activationDecision()` (valid → launch; degraded → confirm; broken → blocked with
  Inspect/Repair).
- **Data:** `/api/shortcuts` (+ inspect/repair), `/api/jobs` / `/api/library`.
- **Reskin:** done (Slices 4, 11, 12). **Limitations:** the non-embedded
  `RecentJobsPanel`/`PreviewPanel` branch is dead; `Tile` (ClaudeIcons) is dead.

### 4.2 Builder (`BuilderWorkspace.jsx`, 3,429 LOC; `OutlineEditor.jsx`)
- **Implemented:** input modes (paste / upload-markdown / LLM), style +
  generator-preset selection (advisory model-hint compatibility warnings),
  output-section toggles + depth/difficulty axes, attachments with large-PDF preflight
  + page selection, editable Outline tab, Generate, progress polling, result panel
  with downloads + warnings, save-to-folder on generate.
- **Data:** `/api/options`, `/api/jobs/llm|paste|upload-markdown`, `/api/preflight/pdf`,
  `/api/jobs/{id}/progress`, `/api/outline/generate`, `/api/presets`.
- **Reskin:** done (Slices 5a/5b). **Limitations:** "Save draft" button and the
  sidebar storage meter are **decorative/inert** (deferred wiring); the visible "mode"
  control was retired (styles define guide type; backend defaults `mode=study_guide`);
  `MetaRow` helper is dead. Largest file in the repo — split candidate.

### 4.3 Library (`LibraryWorkspace.jsx`, 1,579 LOC)
- **Implemented:** folders, client-side search/filter/sort, single + batch move, trash
  view (soft-delete + restore + guarded purge).
- **Data:** `/api/library`, `/api/library/folders`, `/api/jobs/bulk/*`, `/api/jobs/trash`.
- **Reskin:** done (Slice 6, 12). **Limitations:** client-side only — pagination
  deferred; server params exist but UI fetches all jobs once.

### 4.4 Ask Guide (`AskGuideWorkspace.jsx`, 1,382 LOC)
- **Implemented:** three-region layout (guide picker / chat+readiness / context+
  local-model rail). Local-only; offline → first-class offline state + LMM command
  helper. Inert answer renderer (no `dangerouslySetInnerHTML`, no markdown/KaTeX dep);
  collapsed retrieved-chunk metadata (chunk text never rendered). Session
  list/switch/new/clear-history/delete.
- **Data:** `/api/ask/*`, `/api/local-model/status`.
- **Reskin:** redesigned in Slice 13 (UX redesign). **Limitations:** lexical retrieval
  only; no streaming; no extra session uploads; local-only by design.

### 4.5 Styles (`StylesWorkspace.jsx`, 975 LOC)
- **Implemented:** built-in / custom / AI-generated styles; **Compare styles** feature
  (Slice 14): select 2–4 styles, deterministic display-only prompt stats
  (`styleCompare.js`: char/word/heading counts, math/quiz/concise heuristics).
- **Data:** `/api/styles*`, `/api/styles/generate`.
- **Reskin:** done (Slices 8, 12). **Limitations:** compare stats are heuristic/
  display-only (regex keyword detection), not semantic.

### 4.6 Models (`ProviderSettingsWorkspace.jsx` 697 LOC + `LocalModelsPanel.jsx` 1,646 LOC)
- **Implemented:** provider cards (key/base-URL/default-model/custom-models/runtime
  defaults, Test, Refresh models); Local Models panel (status, manual command helper,
  model library scan, managed-server controls with typed schema-driven params).
- **Data:** `/api/provider-settings*`, `/api/local-model/*`.
- **Reskin:** done (Slice 9). **Limitations:** LMM Phase 2 paused; managed server needs
  a configured host companion (not in committed compose); GPU defaults follow-up open.

### 4.7 Exports (`ExportsWorkspace.jsx`, 628 LOC)
- **Implemented:** per-job artifact downloads, filters, multi-job ZIP bundles.
- **Data:** `/api/exports`, `/api/exports/bundle`.
- **Reskin:** done (Slice 10). **Limitations:** chat never exported (by design).

### 4.8 Help (`HelpWorkspace.jsx`, 169 LOC)
- **Implemented:** in-app help/reference workspace. **UNCERTAIN** whether it appears in
  the primary nav or is reached contextually — not in the deep report's seven-nav list.
  Present and wired in `DesktopDashboard.jsx` import set.

### 4.9 Shared drawers / modals / components
- **Job Details drawer** (`RecentJobsPanel.jsx`, 2,005 LOC) — reachable from Recent
  Jobs / Library / Exports / Builder via `useImperativeHandle({ openJob })`. Tabs:
  Details, Quiz, Outline-compliance, Sections, Edit-Markdown, Version-History;
  FailedJobPanel, AttachmentDetails, Validation/Render-log tiles, DiffView,
  QuizQuestionCard.
- **Shortcut Inspector** (`ShortcutInspector.jsx`, 652 LOC) — findings + repair UI.
- **Primitives** (semantic, post-reskin): `Button`, `IconButton`, `StatusPill`,
  `ProviderPill`, `Panel`, `StatCard`, `ItemCard`, `Chip`, `Field`, `Icon`,
  `ClaudeIcons`, `TopBar`, `BrandMark`.
- **Dead/legacy presentational:** `DesktopMockup`, `PhoneMockup`, `GlowBackground`,
  `FallbackImage`, `ImplementationNote`, `MobileScreenPicker`, `PasteGenerationPanel`,
  `data/mockups.js` (documented as dead in Slice 16 audit).

---

## 5. Pipeline / Generation Inventory

### 5.1 Input extraction / OCR (`extract.py`, 412 LOC)
- Supports `.txt/.md/.csv/.tsv/.docx/.pptx/.pdf`. PDF extraction decides **text vs OCR
  per page**: embedded text is "meaningful" (OCR skipped) when stripped text ≥ 40 chars
  **OR** ≥ 5 word-like tokens; otherwise that page is OCR'd via Tesseract. Each page is
  embedded-text **XOR** OCR (never both). Mode reporting: `pdf_text` / `pdf_ocr` /
  `pdf_mixed` (informational metadata only, never branched on).
- `preflight_pdf` — bounded evenly-spaced page sample; advisory; fails open.
- `page_selections` — flat `{filename: [[start,end],…]}`, 1-based inclusive, normalized
  + bounded; restricts extraction to original pages, preserves `## Page N` anchors.

### 5.2 Prompt assembly (`orchestrator.py`, 340 LOC)
- Deterministic order: preset system prompt (preset path only) → axis directives
  (`output_depth` then `difficulty`) → `include_sections` fragments → **`MARKDOWN_MATH_SYSTEM`
  (always last)**. With no preset/axes/sections, the system message is **byte-identical**
  to the historical baseline (test-verified). Unknown section keys dropped; unknown axis
  values rejected at the API boundary (400). Canonical key sets
  (`INCLUDE_SECTION_FRAGMENTS` + aliases, `OUTPUT_DEPTH_FRAGMENTS`, `DIFFICULTY_FRAGMENTS`)
  live here, not the frontend.

### 5.3 Style / generator-preset handling
- **Three non-conflatable registries:** styles (`style_store.py` + `prompts/*.md`,
  define guide type, own voice/tone), generator presets (`generator_presets.py`,
  `/api/options.generator_presets`: full system prompt + sampling, `model_hint` soft
  advisory only), outline quick-templates (`presets.py`, `/api/presets`: section
  bundles). 10 `.md` prompt files in `prompts/` (7 named built-in styles +
  system/user/prompts templates).

### 5.4 LLM provider routing
- Single call boundary `llm_client.generate_chat_completion()` (OpenAI-compatible).
  Resolution precedence: per-job request > provider-settings store default > `.env` >
  built-in default. Runtime (`timeout_seconds`/`retry_count`/`thinking_default`)
  resolved in `build_provider_config`. Retry transient-only (429/5xx/conn/timeout).

### 5.5 Math validation (`math_validator.py`, 133 LOC + `scripts/validate_math.js`)
- **KaTeX-based parse/render validation only.** Runs Node `scripts/validate_math.js`
  (requires `katex`), counts display blocks + inline formulas, parses errors, and
  **degrades, never fails** (missing node / missing validator → `ok=True` skip; a
  failed equation marks spans and ends the job `completed_with_warnings`). **Crucially,
  it validates that LaTeX *compiles*, NOT that the mathematics is *correct*.** This is
  the gap the proposed "deterministic math verification core" fills. Output persisted to
  `validation.json` (`to_json_dict`).

### 5.6 Rendering
- **PDF** (`pdf_renderer.py`, 119 LOC) — headless Chromium via Node; themed by
  `themes/claude_clean.css` (only theme). **Load-bearing/tuned — do not rewrite casually.**
- **HTML** (`html_renderer.py`, 289 LOC) — Node + KaTeX.
- **DOCX** (`docx_renderer.py`, 415 LOC) — **lazy from `clean.md`**; math = literal
  LaTeX text, images = `[image: alt]`, deep lists collapse, raw HTML as text.
- **Markdown** — `clean.md` is the canonical source.

### 5.7 Job artifact lifecycle
- Per job dir `jobs/<id>/`: `job.json` manifest, `final.pdf`, `final.docx` (lazy),
  `final.html`, `clean.md`, `validation.json`, `render.log`, extracted source, version
  snapshots, Ask cache/sessions. Status: `queued/running/done/completed_with_warnings/
  failed/cancelled` + finer stage/progress.

### 5.8 Versioning / retry / cancel / rerender
- `save_clean_md` chokepoint auto-snapshots. Versions list/revert + manual clean_md
  edit. Cooperative cancel = sidecar marker checked at stage boundaries (never kills a
  process; never interrupts mid-Chromium-render). Retry gated to `failed`. Rerender
  regenerates PDF/HTML and keeps DOCX in sync.

### 5.9 Known fragile areas
- The two non-shared `/api/jobs/llm` parsing paths (JSON + multipart) — a field added to
  one only is silently dropped on the other (has bitten the project).
- The PDF/Chromium pipeline and math sanitizer/validator are tuned and load-bearing.
- `clean.md` must only be written through `save_clean_md`.

---

## 6. Provider and Model System

- **Supported providers:** `deepseek`, `qwen`, `local` (canonical ids) + alias map.
  DeepSeek + Qwen verified-working; `local` supported via env/discovery, usually
  `configured:false` until a local server runs. **No first-class Gemini/OpenAI/Mistral.**
- **Storage model:** two-file server-side store under gitignored `config/` —
  `provider_settings.json` (non-secret, `0644`) and `secrets.json` (raw keys only,
  `0600`). The split makes the security boundary physical.
- **Key redaction / write-only:** keys set/cleared, never read back; blank `api_key` in
  PATCH is a no-op. Public DTO has **no key field by construction** — only `configured`,
  `key_source`, last-4 `key_hint` (only if len > 4), `base_url_host` (userinfo stripped).
- **Model fetch/test:** `fetch-models` is read-only discovery (stages into draft
  `custom_models`, requires explicit Save). `test` accepts empty-content choices as
  success (thinking models), no-choices = failure.
- **Local model status:** `get_local_model_status()` reports reachability + exposed
  models, host-only URL, `local_offline` category. `ok` = request succeeded, **not**
  server up.
- **LMM companion boundary:** backend ↔ host companion over token-authed Unix socket
  (`local_model_companion_client.py`). Frontend never talks to companion. Backend never
  touches host FS/processes directly.
- **Managed server:** companion-owned `llama-server` lifecycle; argv centralized (no
  shell, no free-form flags); executable path only from companion config; model path
  only from an approved scanned id; `start_new_session=True`; readiness via
  `/v1/models`; no auto-restart loop; foreign/reused PIDs never killed.
- **Complete vs paused:** Phase 1 (detection + manual command helper) complete +
  validated. Phase 2 (companion → scan → bridge → UI → managed lifecycle) **complete /
  PAUSED after Phase 2G11**. Real CPU-safe E2E **passed**; high-GPU-offload
  (`gpu_layers=999`) **failed safely** (CUDA OOM / `model_may_be_too_large`) on a 26B
  model / 16 GB VRAM and is **not** a default.
- **Security invariants (must not break):** no token / socket path / absolute host
  model or executable path / raw argv / Authorization header / full unsafe URL in any
  LMM response, log, or DTO; root-relative model paths only; Provider Settings is the
  single config writer (LMM/Ask add no second writer).

---

## 7. Ask Guide System

- **Context prep (`ask_context.py`, 390 LOC):** chunks `clean.md` (guide) + optional
  `extracted.txt` (source) deterministically on heading / `## Page N` boundaries
  (~650-token target, ~800 ceiling via chars/4, no overlap), preserving each chunk's
  **citation label** (nearest heading / `Page N`).
- **Indexing:** dependency-free **lexical index** (per-chunk term frequencies +
  `doc_freq`) — **no embeddings, no vector DB, no reranker.**
- **Retrieval currently used:** bounded top-K (~8 chunks, ~3k-token pool) lexical
  retrieval per turn.
- **Cache:** `jobs/<id>/ask/cache/context_index.json`, keyed by content hash over
  guide+source bytes; idempotent (`hit`/`built`/`rebuilt`); atomic; fenced to job dir.
- **Chat/session storage (`ask_sessions.py`, 762 LOC):** sessions under
  `jobs/<id>/ask/sessions/<sid>/` (`session.json` atomic + `history.jsonl` append-only).
  No secrets stored; never auto-exported; no browser storage of chat.
- **Citation contract enforced:** backend validates model bracket citations against
  retrieved labels (`citations_allowed/used/unsupported`, `citation_validation`),
  strips unsupported Ask-looking citations, preserves normal bracketed prose.
- **Local-only constraints:** uses `local` provider only; offline → structured
  `local_offline`, no model call; never starts/stops `llama-server`; never writes job
  artifacts. Empty-response guard returns structured `provider_empty_response`; a
  model-only `/no_think` marker (never persisted/rendered) handles thinking-model
  empty-content behavior.
- **UI state after Slice 13:** dedicated three-region workspace; inert subset renderer
  for answers; collapsed chunk metadata; first-class offline state.
- **Current limitations:** lexical-only retrieval; no streaming; no extra session
  uploads; no rolling summary; no multimodal; local-only.
- **Recommended retrieval upgrades:** vector store (e.g. LanceDB) + embeddings; hybrid
  lexical+vector with a reranker. (See §14.)

---

## 8. Styles / Prompt System

- **Built-in styles:** flat `.md` in `prompts/` — `baby_steps`, `basic_study_guide`,
  `claude_study_guide`, `exam_cram`, `final_solution`, `master_longform`, `mcq_training`
  (+ `study_guide_prompts.md`, `study_guide_system.md`, `study_guide_user.md`
  templates). 10 files total.
- **Custom / AI-generated styles:** persisted in `user_prompts/` (`styles.json`), via
  `/api/styles*` + `/api/styles/generate`. Styles own voice/tone.
- **Compare styles (Slice 14):** select 2–4 styles, view deterministic display-only
  stats from `styleCompare.js` (char/word/heading counts; math/quiz/concise regex
  heuristics). No LLM, no semantic analysis.
- **Generator presets vs style prompts:** presets tune sampling + carry a full system
  prompt, `model_hint` advisory only; styles define the guide type. Never conflate (a
  past shortcut Edit-modal regression proves it matters).
- **Where prompt content lives:** built-ins in `prompts/*.md`; custom/AI in
  `user_prompts/`; assembly directives in `orchestrator.py`.
- **Risks/limitations:** the `styles/` top-level dir is **empty** (don't confuse with
  the styles system); compare stats are heuristic; AI generation quality is unmeasured
  (ties into the eval-harness gap).

---

## 9. Library / Exports / Job Management

- **Library data model:** `library/folders.json` + `job_folders.json` (folder
  membership). Folders CRUD; single + batch move; save-to-folder on generate.
- **Folder / favorite / trash behavior:** favorites toggled per job; trash soft-deletes
  `jobs/<id>/` → `jobs/.trash/<id>/` (reversible); purge acts only inside `jobs/.trash/`
  behind a path assertion; bulk purge loops the guarded single-item purge.
- **Exports / ZIP bundles:** per-job downloads + filters; multi-job ZIP with in-zip
  `manifest.json`; chat history never included.
- **JobDetails capabilities:** metadata, attachment extraction warnings, outline
  summary, downloads, quiz tab, sections, outline compliance, markdown editing, version
  history + revert, failed-job panel, validation/render-log tiles.
- **Artifact links / security:** served via `GET /api/jobs/{id}/artifacts/{name}` with
  name validation; no secrets in `job.json`.
- **Known limitations:** no server-side pagination (UI loads all); no drag-and-drop.

---

## 10. Tests and Validation

### 10.1 End-to-end / smoke (`test_scripts/`)
- `smoke_release.py` — **release check (28 checks; 28/0/0 green)**: paste/upload/LLM/
  attachment/outline/ZIP/folder/style-CRUD/rerender flows + **no-key-leak assertion**.
- `smoke_docx_exports`, `smoke_exports_center`, `smoke_library_bulk`,
  `smoke_library_power_tools`, `smoke_outline_backend`, `smoke_outline_full`,
  `smoke_quiz`, `smoke_save_to_folder`.

### 10.2 Backend-focused
- Ask: `test_ask_context_inventory`, `test_ask_context_prepare`, `test_ask_local_chat`.
- Provider: `test_provider_settings_store`, `test_provider_runtime_settings`,
  `test_provider_fetch_models`, `test_default_provider_precedence`.
- Shortcuts: `test_shortcut_store`, `test_shortcut_inspector`, `test_shortcut_repair`.
- Large-PDF/extraction/math: `test_pdf_preflight`, `test_page_selections`,
  `test_pdf_page_selection_extract`, `test_mixed_pdf_ocr`, `test_math_regressions`,
  `test_long_formula_guidance`, `test_page_reference_format`, `test_markdown_sections`.
- Jobs: `test_cancel_job`, `test_retry_generator_preset`.

### 10.3 Local-model harnesses
- `test_local_model_status`, `test_local_model_command_profile`,
  `test_local_model_companion_scan`, `test_local_model_companion_bridge`,
  `test_local_model_companion_process_{manager,api,bridge}`,
  `test_local_model_companion_real_profile`, `test_local_model_library_selection`,
  `test_lmm_phase2_final_regression`, `test_lmm_real_profile_e2e_harness`.
- Live/manual (require explicit env, skip otherwise):
  `validate_lmm_companion_socket_mount`, `validate_lmm_real_llama_server`,
  `validate_lmm_real_profile_e2e`.

### 10.4 Frontend node harnesses (`frontend/scripts/`)
- `verify-ask-guide`, `verify-local-model-{status,command,library}`,
  `verify-shortcut-{status,form,repair,activation}`, `verify-style-compare` (Slice 14).
- **`verify-assets.mjs`** is the default `npm run test` — **STALE**: it targets the old
  `App.jsx` mockup tree, is a known non-blocker, but is still wired as `test`.

### 10.5 What each test proves / gaps
- **Proves:** API/data-layer correctness of flows, redaction (no key leakage), pure
  helper logic, LMM boundary/redaction, KaTeX *parse* validity.
- **Not covered:** mathematical/factual **correctness** of generated content; output
  *quality* (no eval harness / golden set / scoring); browser-driven UI behavior
  (operator-owned visual review); retrieval quality of Ask; OCR accuracy.
- **Recommended next tests:** eval harness with golden inputs + scored outputs;
  deterministic math-verification unit tests; structure/outline/KaTeX lint tests;
  Ask retrieval relevance tests.

---

## 11. Current Done / Features-Complete List

- Same-origin Dockerized React+FastAPI app, non-root, port 8000.
- Three input transports (paste / upload-markdown / LLM) + attachments with per-page
  text/OCR fallback and large-PDF preflight + page selection.
- Deterministic prompt assembly (sections + depth/difficulty axes + math system block).
- Multi-provider LLM routing (DeepSeek + Qwen verified) with resolution precedence.
- **Provider Settings** (in-app config, two-file store, write-only keys, fetch-models,
  test-connection) — complete + validated.
- Artifact rendering: PDF (Chromium), HTML (KaTeX), DOCX (lazy), Markdown.
- KaTeX parse/render math validation (degrade-not-fail) → `validation.json`.
- Job lifecycle: staged progress, cooperative cancel, retry (failed-gated), rerender,
  version snapshots + revert, manual clean_md edit.
- **Section regeneration** + outline compliance reporting.
- **Quizzes / flashcards** (CSV / Anki / Quizlet export).
- **Library**: folders, batch move, search/filter/sort, **trash-before-purge** safety.
- **Exports**: per-job downloads + multi-job ZIP bundles.
- **Home shortcuts** + **Shortcut Inspector / Repair Loop** (3-tier validity,
  whitelist-patch repair, activation gating) — complete.
- **Ask Your Guide** (local-only grounded chat, lexical retrieval, citation contract,
  sessions) — complete enough.
- **Local Model Manager** Phase 1 (complete+validated) and Phase 2 (complete/paused,
  real CPU-safe E2E passed).
- **GuideForge reskin + UX phase** (Slices 1–16): semantic `.sg-*` CSS system across
  all workspaces, Ask redesign, Home/Library polish, Compare styles, JobDetails reskin,
  release audit — complete.
- Deep project context report + extensive design/validation docs.

---

## 12. Current Not-Done / Deferred List (grouped)

**Correctness / verification**
- Deterministic **math correctness** verification (current validation is parse-only).
- **Eval harness** (golden inputs, scored outputs, regression detection) — none exists.
- Structure / outline / KaTeX **lint** as a deterministic gate (compliance is reported,
  not enforced/repaired).
- Outline **ordering enforcement/repair** post-generation (currently compliance-only).

**Ingestion / OCR**
- Automatic large-PDF split/chunk processing.
- Hybrid embedded-text + OCR dedup / optimization.
- Raising `MAX_UPLOAD_MB`; persisting the preflight report in `job.json`.
- Carrying page selections into drafts/shortcuts.
- Alternative OCR provider (e.g. Mistral OCR) + hybrid OCR metadata.

**Retrieval / Ask**
- Vector store + embeddings (e.g. LanceDB); hybrid retrieval + reranker.
- Extra session uploads; streaming; rolling chat summary; hosted/cloud Ask (kept local).

**Visuals / diagrams**
- Source visual extraction (figures/diagrams from source docs).
- VLM visual understanding (multimodal); second PDF theme / theme-picker.

**Study system**
- FSRS / spaced-repetition scheduling; active-recall / cloze generation;
  Anki `.apkg` export (current Anki export is CSV-shaped, not packaged `.apkg`).

**Providers / local models**
- First-class Gemini / OpenAI / Mistral providers.
- LMM approve-root flow (host-companion design); app-suggested settings/recommendations;
  practical GPU-offload defaults; Ollama / simple-local path; model downloads.

**Packaging / deployment**
- GHCR publish workflow + prebuilt `image:` line; pinned `requirements.txt` lockfile;
  Windows/macOS packaging/support.

**UI polish / dead files / tech debt**
- "Save draft" button + storage meter wiring (currently inert).
- Server-side pagination shared by Library/Exports; drag-and-drop reordering.
- Dead-code sweep (see §13); split oversized components; default `test` script fix.

---

## 13. Technical Debt and Risks

**Dead / unrendered files (documented in Slice 16 audit, left in place):**
- Non-embedded `RecentJobsPanel` return branch + `PreviewPanel` helper (unreachable).
- `Tile` (`ClaudeIcons.jsx`), `MetaRow` (`BuilderWorkspace.jsx`).
- Mockup components: `DesktopMockup`, `PhoneMockup`, `BrandMark`, `GlowBackground`,
  `FallbackImage`, `ImplementationNote`, `MobileScreenPicker`, `PasteGenerationPanel`,
  `data/mockups.js`.

**Stale tests:** `frontend/scripts/verify-assets.mjs` (the default `npm run test`)
targets the old mockup tree — known non-blocker, still wired as `test`.

**Large files needing split:** `BuilderWorkspace.jsx` (3,429), `RecentJobsPanel.jsx`
(2,005), `HomeShortcuts.jsx` (1,671), `LocalModelsPanel.jsx` (1,646),
`LibraryWorkspace.jsx` (1,579); backend `api/server.py` (~3,800),
`pipeline/shortcut_store.py` (1,561), `pipeline/provider_config.py` (1,143);
**`design-system.css` (200 KB / 3,228 lines / 773 classes)**.

**Duplicated CSS / classes:** the reskin layered semantic classes incrementally; some
overlap and inert Tailwind tokens were stripped only in live paths (dead branches still
carry old-palette tokens). Audit reports the live path is clean (0 undefined `.sg-*`).

**Data model limitations:** JSON-file stores (no DB) — fine at single-operator scale,
but library/jobs scans are O(n) and load-all (no pagination); concurrency relies on
atomic writes, not transactions.

**Performance risks:** Chromium PDF render is the heaviest step (uninterruptible mid-
render); lexical Ask retrieval re-reads the cache JSON per turn; load-all library/jobs
in the UI will degrade with many jobs (~150 already on disk).

**Security risks (currently well-managed — keep guarded):** the §6 LMM exposure surface;
secrets must stay out of all API/log/artifact/export/JS surfaces; the two-path
`/api/jobs/llm` parsing rule; trash purge path guard. Slice 16 security scan was clean.

**DX / maintenance risks:** `CLAUDE.md` route list is stale; `PROJECT_DEEP_CONTEXT_REPORT.md`
references a non-existent `section_scorer.py`; the doc set is very large
(`CURRENT_TASK.md` ~243 KB) and could drift; Codex-prompt handoff convention adds
process overhead.

---

## 14. Recommended Roadmap Candidates

> Candidates only — **not** a final roadmap. Priority is a suggestion for the planning
> session. "Risk" = implementation risk to the load-bearing app.

| # | Title | Purpose | Scope | Risk | User value | Dependencies | Priority | Verification needed |
|---|-------|---------|-------|------|-----------|--------------|----------|---------------------|
| 1 | **Deterministic math verification core** | Check *mathematical correctness* (not just KaTeX parse) of generated equations/steps | New pure module (sympy-style symbolic eval + numeric spot-check), no pipeline rewrite | Low–Med (additive, degrade-not-fail) | High (core trust gap) | None | **P0** | Unit tests on known-correct/incorrect fixtures; no job-fail regressions |
| 2 | **Math verification → validation artifacts / JobDetails** | Surface #1 results in `validation.json` + JobDetails tab | Wire core into job run + JobDetails read-only UI | Med (touches job run + drawer) | High | #1 | **P0** | Smoke: artifact present; UI renders; no secret/behavior change |
| 3 | **Deterministic structure / KaTeX / outline lint** | Gate output on heading structure, KaTeX validity, outline coverage | Pure linter + report (advisory first) | Low | Med–High | orchestrator section keys | **P1** | Lint unit tests; degrade-not-fail |
| 4 | **Eval harness Phase 1** | Golden inputs + scored outputs + regression detection | New `test_scripts/eval/` harness, fixtures, scoring | Med | High (enables all quality work) | #1/#3 helpful | **P0/P1** | Reproducible scores on a fixed set |
| 5 | **Source citation / page anchoring** | Tie guide claims back to source pages | Carry `## Page N` anchors into output + Ask | Med | High | extract page anchors | P1 | Page refs correct on mixed PDFs |
| 6 | **Hybrid OCR metadata** | Record per-page OCR vs text + confidence | Extend `extract.py` metadata (no behavior change) | Low | Med | extract | P2 | Metadata in `job.json`; no extraction change |
| 7 | **Mistral OCR provider** | Higher-accuracy OCR than Tesseract | New optional OCR backend behind a provider switch | Med (cost/secret) | Med–High | provider/secret model | P2 | Redaction; opt-in; fallback to Tesseract |
| 8 | **Ask retrieval upgrade (LanceDB)** | Replace lexical index with vector store | New embedding + LanceDB index; keep local-only | Med–High (new dep, local-only constraint) | High | embedding model (local?) | P1 | Retrieval relevance tests; local-only preserved |
| 9 | **Hybrid retrieval + reranker** | Combine lexical+vector + rerank | Builds on #8 | High | Med–High | #8 | P2 | A/B relevance vs lexical |
| 10 | **Source visual extraction** | Pull figures/diagrams from source docs into guides | Extract+embed images; render path changes | High (render pipeline) | High | extract/render | P2/P3 | PDF fidelity; no regression |
| 11 | **VLM visual understanding** | Multimodal understanding of slides/figures | New multimodal provider path | High (cost, new boundary) | High | provider model | P3 | Opt-in; redaction; cost guard |
| 12 | **FSRS spaced repetition** | Schedule review of quiz/flashcard items | New scheduler + per-item state store | Med | High (study value) | quiz system | P1/P2 | Scheduler unit tests |
| 13 | **Active recall / cloze** | Generate cloze/active-recall items | Extend quiz generation | Med | High | quiz system | P2 | Quiz smoke; export round-trip |
| 14 | **Anki `.apkg` export** | True packaged Anki deck (not just CSV) | New packager (sqlite/zip) | Med | Med–High | quiz export | P2 | `.apkg` imports cleanly in Anki |
| 15 | **Gemini provider** | First-class Gemini support | New provider entry + resolution + redaction | Low–Med | Med | provider system | P2 | Redaction; test-connection; fetch-models |
| 16 | **LMM packaging / approve-root** | Resume paused LMM with approve-root flow or packaging | Separately designed host-companion flow | High (boundary-sensitive) | Med (operator-only) | LMM Phase 2 | P3 | Boundary invariants hold; redaction |

**Synthesis:** the highest-leverage cluster is **#1 → #2 → #4 (+#3)** — a correctness/
measurement layer that turns "unmeasured quality" into something gated and visible.
Retrieval (#8) and study-system (#12–14) are the next-best value tiers once quality is
measurable. Visual/VLM (#10–11) and LMM packaging (#16) are higher-risk, later.

---

## 15. Questions for Roadmap Planning

Answer these before locking the next ~10 slices:

1. **Local-only vs cloud default stance.** Is the product intended to lean local-first
   (privacy, no API cost) or cloud-first (quality, less setup)? This changes whether
   #7/#8/#11 need local models or can assume cloud.
2. **Does Ask remain local-only?** The current invariant forbids cloud Ask. A retrieval
   upgrade (#8) and any VLM Ask depends on this answer.
3. **OCR provider budget / cost assumptions.** Is paid OCR (Mistral, #7) acceptable, or
   must OCR stay free/offline (Tesseract)? Cost ceiling per document?
4. **Math correctness vs OCR first?** Both are quality plays. Which pain is worse today —
   wrong math in guides, or poor extraction from scanned slides?
5. **Packaging target.** Stay Linux/Docker single-operator, or invest in GHCR publish /
   Windows-macOS packaging / LMM approve-root? This decides whether #16 and the deferred
   Docker items get priority.
6. **Prioritized user persona.** Solo exam-cram student vs. small study group vs.
   power-user with a local GPU rig? This reweights study-system (#12–14) vs LMM (#16) vs
   retrieval (#8).
7. **Acceptable scope of dead-code / tech-debt cleanup** before/after feature work — is a
   dedicated cleanup slice (dead files, oversized components, default `test` fix, doc
   reconciliation) wanted up front, or folded into feature slices?
8. **Eval harness depth.** Phase 1 lightweight golden-set scoring, or a fuller
   LLM-judge + regression-tracking system? Determines #4 sizing.

---

## Appendix A — Discrepancies Found (code is authoritative)

- **`CLAUDE.md`** route shortlist understates the real ~80-route surface. Trust
  `api/server.py`.
- **`PROJECT_DEEP_CONTEXT_REPORT.md`** lists `pipeline/section_scorer.py`; it does not
  exist in the current tree. Section parsing is in `markdown_sections.py`.
- The deep report (dated 2026-06-08) predates **Slices 12–16** (Compare styles, Ask
  redesign, RecentJobs/JobDetails reskin, release audit). Those are real and integrated.
- **`HelpWorkspace.jsx`** exists but is absent from the deep report's "seven nav
  workspaces" list. `UNCERTAIN` whether it is primary-nav or contextual.
- "Anki export" for quizzes is **CSV-shaped**, not a packaged `.apkg` — true `.apkg` is a
  separate roadmap candidate (#14).

## Appendix B — Uncertainties (marked `UNCERTAIN`)

- Help workspace nav placement (above).
- Exact field-level shape of some POST bodies (quiz, exports/bundle, repair/apply) — the
  route signatures and validation were inspected but full DTOs were not exhaustively
  transcribed; treat shapes here as "rough, verify in `api/server.py` before relying").
- Whether any job-data on disk (~150 dirs) includes Ask caches that should be excluded
  from a future packaging image — likely yes (gitignored), not verified file-by-file.
