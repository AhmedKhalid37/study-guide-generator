# GuideForge Current State Inspection

> Slice 157 — Current App State Inspection Report. Inspection / documentation
> only: no runtime behavior, API, frontend, backend, pipeline logic, or tests
> were changed. Based on the live repo state **after Slice 156 merged to trunk**
> (`chrome-renderer-v1` @ `8f27091`). The repo / running code is the source of
> truth; where a doc disagreed with code, code was verified before recording.
>
> Privacy: this report records **closed labels only**. No guide text, snippets,
> matched aliases, source text, raw artifact JSON, hashes, byte counts, private
> paths, filenames, screenshots, provider payloads, or secrets appear here.

---

## 1. Executive Summary

**What GuideForge is.** GuideForge (a.k.a. Study Guide Generator) is a
Dockerized, same-origin **React (Vite + Tailwind) + FastAPI** app for a single
operator / small group. It turns pasted text, uploaded Markdown, or uploaded
attachments into exam-focused study guides rendered to **PDF** (headless
Chromium) plus **Markdown / HTML / DOCX**, and also generates **quizzes /
flashcards** (CSV / Anki / Quizlet export). It runs as a single non-root
container on port 8000; the backend serves the built `frontend/dist` and all
`/api/*` routes are registered before the SPA static mount.

**Current trunk.** `chrome-renderer-v1`.

**Current phase.** **Measured guide-quality baseline hardening.** The LLM-judge
path is frozen at synthetic-only; the active work is a deterministic, advisory,
closed-vocabulary **baseline aggregator** that scores real locally-generated
guides by reusing existing wired artifacts, plus narrow prompt-contract /
detector / mapping fixes driven by what the baseline measures. No new external
service calls; no judge or repair execution.

**Latest merged slices.** Trunk head is **Slice 156** (`8f27091`, "Observe
reference completeness and figure handling via closed local guide-text
scanner"), preceded by Slice 155 (`35c6b71`, source coverage baseline status),
Slice 154 (`1dae76f`, line-initial discourse-leak prompt hardening), Slice 153
(`af606d4`, app-pipeline baseline provenance), and Slice 152 (`a1dfdd4`,
reasoning-leak detector boundary hardening).

**What is working.** Provider Settings; Builder generation (paste / upload-md /
LLM with attachments + large-PDF preflight + page selection); outline / style /
preset selection; PDF / HTML / MD / DOCX exports + multi-job ZIP bundles;
Library / folders / trash; quizzes / flashcards + Anki/Quizlet export; Ask Your
Guide (local-model-only); Local Model Manager Phase 2 (paused but complete);
math verification, source coverage, guide-quality contract lint, QA gate, report
v2, and rubric artifacts are all production-wired; the measured baseline
aggregator now reads **green** on `app_run_6` for reasoning leak, source
coverage, reference relative completeness, and figure handling.

**What remains unmeasured or risky.** `numeric_math_status=not_available` (no
operator-confirmed known-numbers spec yet); the QA gate still emits a
non-blocking **warning** on `app_run_6`; the LLM-judge path is frozen at
synthetic-only (`judge_ready=false`, `repair_ready=false`,
`calibration_status=synthetic_only`); reference completeness and figure handling
are observed only via closed alias checks and should be refined; full
visual/table handling remains a long-term gap; and the docs surface is large and
at risk of drift.

---

## 2. Architecture Overview

**Backend framework / entry points.** FastAPI in `api/server.py`. It registers
**all** `/api/*` routes first, then mounts the built SPA (`frontend/dist`) at
`/` — this order is load-bearing (API routes must win over the catch-all).
Pipeline logic lives under `pipeline/`. The host-side Local Model companion
(`tools/local_model_companion/`) is **not** in the Docker image.

**Frontend framework / main pages.** React (Vite + Tailwind), entry
`frontend/src/main.jsx` → `App.jsx` → `components/DesktopDashboard.jsx`. Seven
workspaces (nav ids in `DesktopDashboard.jsx`): **Home** (`HomeShortcuts.jsx`,
`RecentJobsPanel.jsx`) · **Builder** (`BuilderWorkspace.jsx`,
`OutlineEditor.jsx`) · **Library** (`LibraryWorkspace.jsx`, `ItemCard.jsx`) ·
**Ask Guide** (`AskGuideWorkspace.jsx`) · **Styles** (`StylesWorkspace.jsx`) ·
**Models** (`ProviderSettingsWorkspace.jsx`, `LocalModelsPanel.jsx`) ·
**Exports** (`ExportsWorkspace.jsx`). Result/quality panels:
`GuideQualityPanel.jsx`, `GuideLintPanel.jsx`, `MathVerificationPanel.jsx`,
`MaterialCoveragePanel.jsx`, `VisualAdvisoryPanel.jsx`,
`ShortcutInspector.jsx`. Pure React-free helpers live in `frontend/src/*.js`
(node-testable); pure verify harnesses in `frontend/scripts/*.mjs`.

**Pipeline modules / responsibilities.** See §5 for the full inventory. The
orchestrator (`pipeline/orchestrator.py`) owns the canonical section/axis key
set; `input_handler.py` + `extract.py` + the OCR stack feed the LLM
(`llm_client.py`) via prompt assembly (`prompt_loader.py`, generator presets,
coverage/dual-explanation/table prompt-context modules); the sanitizer + math
validator clean and check output; the render/export modules emit final files;
the quality modules emit advisory artifacts.

**Job lifecycle.** A request (paste / upload-markdown / LLM) creates a job via
`JobManager`; `run_llm_job.py` / `run_markdown_job.py` drive
extraction → prompt assembly → generation → sanitize → render/export → quality
artifact writes. Progress is polled (`/api/jobs/{id}/progress`). Cancel is
cooperative (a sidecar checkpoint marker — never a process kill). Retry is gated
to `failed` jobs. Section regeneration, version snapshots/revert, and rerender
are supported.

**Artifact storage model.** Per-job artifacts live under `jobs/<id>/`
(gitignored runtime). All writes to `clean.md` go through
`JobManager.save_clean_md(...)` (auto-snapshots version history); never written
directly. Trash is soft-delete under `jobs/.trash/` with guarded purge (purge
only acts inside `.trash/`). See §6 for the artifact table.

**Rendering / export flow.** `pdf_renderer.py` (headless Chromium, load-bearing
and tuned), `html_renderer.py` (KaTeX/HTML via nodejs), `docx_renderer.py`
(lazy DOCX from `clean.md`); themes under `themes/` (`claude_clean.css` today).
Exports: per-job downloads + multi-job ZIP bundles (chat history never
included).

**Provider / model flow.** `provider_config.py` + `provider_settings_store.py`.
Resolution precedence: per-job request > provider-settings store default >
`.env` > built-in default. DeepSeek + Qwen verified-working; `local` supported
via env/discovery. Keys are server-side only, write-only over the API; the
public DTO has no key field by construction.

**Ask Guide flow.** `ask_context.py`, `ask_inventory.py`, `ask_lexical.py`,
`ask_coverage_grounding.py`, `ask_sessions.py`. Local-model-only chat over a
generated guide with mandatory budgeted retrieval + citation contract; reads
artifacts read-only; no process control; stores no secrets; never auto-exported.

**Local Model Manager status.** Phase 1 (detection + manual command helper) and
Phase 2 (host companion → approved-GGUF scan → Unix-socket backend bridge →
model-library UI → companion-managed `llama-server` lifecycle) are **complete /
validated** but **PAUSED** after Phase 2G11 hardening. Modules:
`local_model_companion_client.py`, `local_model_library_selection.py`. The
committed `docker-compose.yml` has no companion socket mount and no LMM env.

---

## 3. User-Facing Feature Inventory

- **Home / shortcuts / recent guides** — `HomeShortcuts.jsx` (configurable
  shortcuts with inspect/repair loop), `RecentJobsPanel.jsx`.
- **Builder generation flow** — paste / upload-markdown / LLM input; style +
  generator-preset selection; output-section toggles + depth/difficulty axes;
  attachments with large-PDF preflight + page selection; progress polling;
  result panel with warnings. ("Save draft" + sidebar storage meter are
  decorative/inert — deferred wiring. The visible "mode" control was retired;
  backend still defaults `mode=study_guide`.)
- **Outline / style / preview behavior** — editable Outline tab
  (`OutlineEditor.jsx`); outline quick-templates (`/api/presets`) are distinct
  from generator presets (`/api/options.generator_presets`).
- **Provider settings** — `ProviderSettingsWorkspace.jsx`: provider/key/model/
  runtime config; test connection; fetch models. Keys write-only.
- **Custom styles and presets** — `StylesWorkspace.jsx`, `styleCompare.js`,
  `style_store.py`; generate/edit/delete custom styles (`/api/styles*`).
- **Library / folders / exports** — `LibraryWorkspace.jsx`: folders,
  search/filter/sort, single + batch move, soft-delete trash + restore + guarded
  purge.
- **PDF / HTML / MD / DOCX exports** — per-job downloads, filters, multi-job ZIP
  bundles (`ExportsWorkspace.jsx`, `/api/exports*`).
- **Anki export** — present: `pipeline/anki_export.py` + quiz export routes
  (`/api/jobs/{id}/quizzes/{n}/export`); CSV / Anki / Quizlet flashcard/quiz
  export.
- **Ask Your Guide** — `AskGuideWorkspace.jsx`; local-model-only chat with
  budgeted retrieval + citation contract.
- **Local model status / manager** — `LocalModelsPanel.jsx`; detection, command
  helper, companion status, library scan, server lifecycle (paused).
- **Visual pilot / figure handling** — present as advisory:
  `VisualAdvisoryPanel.jsx`, `visualAdvisoryArtifacts.js`, and a large
  `pipeline/visual_*` module set (extractor, scoring, manifest, inclusion/
  insertion/replacement planners, markdown insertion). Opt-in.
- **Source coverage / quality panel** — `MaterialCoveragePanel.jsx`,
  `GuideQualityPanel.jsx`, `GuideLintPanel.jsx`, `MathVerificationPanel.jsx`
  surface the advisory quality artifacts.
- **Stage progress / cancel / retry** — progress polling; cooperative cancel
  (sidecar marker); retry gated to `failed`; section regeneration; version
  history + revert; rerender.

---

## 4. Backend API Inventory

Routes inspected in `api/server.py` (declared with `@app.<method>`; all under
`/api/*`, registered before the SPA mount). No payloads/secrets shown.

| Endpoint | Method | Purpose | Major artifact / feature |
|---|---|---|---|
| `/api/health` | GET | Liveness check | — |
| `/api/options` | GET | Capabilities, generator presets, sections/axes | Builder options |
| `/api/provider-settings` | GET / PATCH | Read / update provider config (non-secret DTO) | Providers |
| `/api/provider-settings/{provider}` | PATCH | Per-provider update | Providers |
| `/api/provider-settings/{provider}/clear-key` | POST | Clear stored key (write-only) | Providers |
| `/api/provider-settings/{provider}/test` | POST | Test provider connectivity | Providers |
| `/api/provider-settings/{provider}/fetch-models` | POST | List provider models | Providers |
| `/api/local-model/status` | GET | Local model detection status | LMM |
| `/api/local-model/check` | POST | Re-probe local model | LMM |
| `/api/local-model/command-profile` | GET | Manual command helper | LMM Phase 1 |
| `/api/local-model/companion/status` | GET | Host companion status (bridge) | LMM Phase 2 |
| `/api/local-model/library` | GET | Approved-GGUF library | LMM Phase 2 |
| `/api/local-model/library/scan` | POST | Trigger companion scan | LMM Phase 2 |
| `/api/local-model/server/status` | GET | `llama-server` lifecycle status | LMM Phase 2 |
| `/api/local-model/server/profiles` | GET | Server profiles | LMM Phase 2 |
| `/api/local-model/server/start|stop|restart` | POST | Companion-managed lifecycle | LMM Phase 2 |
| `/api/local-model/library/selection` | GET / POST / DELETE | Selected model | LMM Phase 2 |
| `/api/styles` | GET / POST | List / create styles | Styles |
| `/api/styles/{style_id}` | GET / PUT / DELETE | Read / update / delete style | Styles |
| `/api/styles/generate` | POST | Generate a custom style | Styles |
| `/api/presets` | GET | Outline quick-templates | Outline presets |
| `/api/presets/{preset_id}/apply` | POST | Apply outline preset | Outline |
| `/api/outline/generate` | POST | Generate outline | Outline |
| `/api/jobs` | GET | List jobs | Library |
| `/api/jobs/paste` | POST | Create job from pasted text | Builder |
| `/api/jobs/upload-markdown` | POST | Create job from uploaded markdown | Builder |
| `/api/preflight/pdf` | POST | Large-PDF preflight + page selection | Builder |
| `/api/jobs/llm` | POST | LLM generation (JSON **and** multipart paths) | Builder / generation |
| `/api/jobs/{job_id}` | GET | Job detail | Library |
| `/api/jobs/{job_id}/progress` | GET | Progress polling | Job lifecycle |
| `/api/jobs/{job_id}/cancel` | POST | Cooperative cancel (sidecar) | Job lifecycle |
| `/api/jobs/{job_id}/favorite` | POST | Toggle favorite | Library |
| `/api/jobs/{job_id}/artifacts/{artifact_name}` | GET | Fetch named artifact | Artifacts |
| `/api/jobs/{job_id}/error` | GET | Error detail | Job lifecycle |
| `/api/jobs/{job_id}/retry` | POST | Retry (gated to `failed`) | Job lifecycle |
| `/api/jobs/{job_id}/rerender` | POST | Re-render from `clean.md` | Render |
| `/api/jobs/{job_id}/versions` | GET | Version snapshots | Version history |
| `/api/jobs/{job_id}/clean_md` | GET / PUT | Read / write `clean.md` (via JobManager) | `clean.md` |
| `/api/jobs/{job_id}/versions/{version}/clean_md` | GET | Versioned `clean.md` | Version history |
| `/api/jobs/{job_id}/revert/{version}` | POST | Revert to version | Version history |
| `/api/jobs/{job_id}/sections` | GET | Section listing | Section regen |
| `/api/jobs/{job_id}/outline_compliance` | GET | Outline compliance check | Outline |
| `/api/jobs/{job_id}/sections/{section_index}/regenerate` | POST | Regenerate a section | Section regen |
| `/api/jobs/{job_id}/quiz` | POST | Generate quiz/flashcards | Quizzes |
| `/api/jobs/{job_id}/quizzes` | GET | List quizzes | Quizzes |
| `/api/jobs/{job_id}/quizzes/{quiz_n}` | GET | Quiz detail | Quizzes |
| `/api/jobs/{job_id}/quizzes/{quiz_n}/export` | GET | CSV / Anki / Quizlet export | Anki/Quizlet |
| `/api/jobs/bulk/delete|restore|move|purge` | POST | Bulk library ops | Library / trash |
| `/api/jobs/trash` | GET / DELETE | List / purge trash (inside `.trash/` only) | Trash |
| `/api/jobs/{job_id}/trash` | POST | Soft-delete | Trash |
| `/api/jobs/{job_id}/restore` | POST | Restore from trash | Trash |
| `/api/jobs/trash/{job_id}` | DELETE | Purge single trashed job | Trash |
| `/api/library` | GET | Library view | Library |
| `/api/library/folders` | GET / POST | List / create folders | Folders |
| `/api/library/folders/{folder_id}` | PUT / DELETE | Rename / delete folder | Folders |
| `/api/library/jobs/move` | POST | Batch move | Folders |
| `/api/library/jobs/{job_id}/move` | POST | Single move | Folders |
| `/api/shortcuts` | GET / POST | List / create shortcuts | Home shortcuts |
| `/api/shortcuts/export` | GET | Export shortcuts | Shortcuts |
| `/api/shortcuts/reorder` | POST | Reorder | Shortcuts |
| `/api/shortcuts/defaults/reset` | POST | Reset defaults | Shortcuts |
| `/api/shortcuts/import/preview` / `/api/shortcuts/import` | POST | Import preview / apply | Shortcuts |
| `/api/shortcuts/{shortcut_id}` | GET / PUT / DELETE | CRUD | Shortcuts |
| `/api/shortcuts/{shortcut_id}/export` | GET | Single export | Shortcuts |
| `/api/shortcuts/{shortcut_id}/inspect` | GET | Inspector | Inspect/repair loop |
| `/api/shortcuts/{shortcut_id}/repair/preview|apply` | POST | Repair loop | Inspect/repair loop |
| `/api/exports` | GET | Export listing/filters | Exports |
| `/api/exports/bundle` | POST | Multi-job ZIP bundle | Exports |
| `/api/ask/jobs` | GET | Ask-eligible jobs | Ask Guide |
| `/api/ask/jobs/{job_id}/context` | GET | Ask context inventory | Ask Guide |
| `/api/ask/jobs/{job_id}/prepare` | POST | Prepare/index for Ask | Ask Guide |
| `/api/ask/jobs/{job_id}/sessions` | GET / POST | List / create Ask sessions | Ask Guide |
| `/api/ask/sessions/{session_id}` | GET / DELETE | Read / delete session | Ask Guide |
| `/api/ask/sessions/{session_id}/message` | POST | Ask a question | Ask Guide |
| `/api/ask/sessions/{session_id}/history` | DELETE | Clear history | Ask Guide |

> Note: `/api/jobs/llm` has two request-construction paths (JSON body vs
> multipart-with-attachments) that do **not** share parsing — any field added to
> `LLMJobRequest` must be wired into the multipart `_parse_llm_request` branch
> too.

---

## 5. Pipeline Module Inventory

Exact filenames under `pipeline/`.

- **Extraction / OCR / page selection** — `input_handler.py`, `extract.py`,
  `extraction_metadata.py`, `ocr_modes.py`, `ocr_provider.py`,
  `ocr_routing.py`, `page_selection_model.py`,
  `missing_material_explainer.py`. Chandra-related OCR scaffolding:
  `chandra_local_provider.py`, `chandra_normalizer.py` (Chandra blocked unless
  explicitly cleared).
- **Prompt assembly** — `prompt_loader.py`, `generator_presets.py`,
  `presets.py`, `coverage_aware_prompt_context.py`,
  `dual_explanation_prompt_context.py`, `table_reconstruction_prompt_context.py`,
  `guide_quality_prompt_contract.py` (shared `_CORE_RULES` chokepoint).
- **LLM generation** — `llm_client.py`, `orchestrator.py` (canonical
  section/axis vocabulary), `run_llm_job.py`, `run_markdown_job.py`.
- **Sanitizer / markdown cleanup** — `markdown_sanitizer.py`,
  `markdown_sections.py`.
- **Math verification** — `math_validator.py` (sanitizer/validator), `math_verifier.py`
  (numeric `math_verification.json` producer).
- **Source coverage** — `source_coverage_report.py` (producer;
  `_top_level_status` emits `completed`), `source_coverage_artifact.py` (writer).
- **Guide quality contract lint / QA gate / rubric / report** —
  `guide_quality_contract_lint.py`, `guide_quality_qa_gate.py`,
  `guide_quality_rubric_score.py`, `guide_quality_report_v2.py`, `guide_lint.py`.
- **Baseline harness** — `guide_quality_baseline.py` (Slice 149 aggregator;
  Slice 155 source-coverage token fix; Slice 156 closed guide-text scanner).
- **Render / export** — `pdf_renderer.py`, `html_renderer.py`,
  `docx_renderer.py`.
- **Visual asset handling** — `visual_asset_extractor.py`,
  `visual_asset_scoring.py`, `visual_assets_manifest.py`,
  `visual_inclusion_plan_artifact.py`, `visual_inclusion_planner.py`,
  `visual_insertion_planner.py`, `visual_replacement_planner.py`,
  `visual_markdown_insertion.py`, `table_candidate_manifest.py`,
  `table_reconstruction_policy.py`, `table_reconstruction_policy_artifact.py`.
- **Anki export** — `anki_export.py`.
- **Ask Guide indexing / chat** — `ask_context.py`, `ask_inventory.py`,
  `ask_lexical.py`, `ask_coverage_grounding.py`, `ask_sessions.py`.
- **Job manager / stores** — `job_manager.py` (owns `save_clean_md`),
  `job_stages.py`, `library_store.py`, `style_store.py`, `shortcut_store.py`,
  `provider_settings_store.py`, `provider_config.py`,
  `local_model_companion_client.py`, `local_model_library_selection.py`.
- **Quality Safety (frozen, synthetic-only)** — the `quality_safety_*` module
  family (offline judge schema/core/adapters, fact sheet + producer, leak
  scanner, canonical matcher, recompute verifier, eval harness, numeric
  extraction/extractor/mapper, unified QA, job artifact, operator export
  validator). `quality_safety_unified_qa.py` is the one wired into job artifacts.

---

## 6. Artifact Inventory

Closed metric fields are summarized; raw artifact bodies are **never** safe to
commit. "Wired" = produced in the live job pipeline (`run_markdown_job.py` /
`run_llm_job.py`).

| Artifact | Producer | Consumer / UI | Wired vs synthetic | Advisory vs blocking | Raw safe to commit? | Closed fields (if relevant) |
|---|---|---|---|---|---|---|
| `clean.md` | generation → `JobManager.save_clean_md` | render/export, Ask, version history | wired | n/a (source of truth) | No | — |
| `final.pdf` / `final.html` / `final.docx` | renderers | Exports / downloads | wired | n/a | No | — |
| `math_verification.json` | `math_verifier.py` (`_write_math_verification`) | `MathVerificationPanel`, QA gate, baseline | wired | advisory | No | numeric status; baseline shows `numeric_math_status` |
| `source_coverage_report.json` | `source_coverage_report.py` / `source_coverage_artifact.py` | `MaterialCoveragePanel`, baseline | wired | advisory | No | top status `completed`; per-source `complete`; `visual_candidate_pages` count |
| `guide_quality_contract_lint.json` | `guide_quality_contract_lint.py` | `GuideLintPanel`/`GuideQualityPanel`, baseline | wired | advisory | No | `reasoning_leak_count`, section/structure counts |
| `guide_quality_qa_gate.json` | `guide_quality_qa_gate.py` | `GuideQualityPanel`, baseline | wired | advisory (non-blocking) | No | gate status (currently `warning` on `app_run_6`) |
| `guide_quality_report_v2.json` | `guide_quality_report_v2.py` | `GuideQualityPanel`, baseline | wired | advisory | No | warning counts |
| `guide_quality_rubric_score.json` | `guide_quality_rubric_score.py` | `GuideQualityPanel`, baseline (supporting) | wired | advisory | No | rubric sub-scores |
| `quality_safety_unified_qa.json` | `quality_safety_unified_qa.py` | advisory display | wired | advisory | No | unified QA counts |
| Offline judge report (`quality_safety_offline_judge_report.json`) | judge adapters | none (not written) | **synthetic / design-only** | advisory | No | `judge_ready=false`, `calibration_status=synthetic_only` |
| Visual / figure assets + manifests | `visual_*` modules | `VisualAdvisoryPanel` | wired (opt-in) | advisory | No | candidate counts, selection trace (sanitized) |
| Anki / Quizlet exports | `anki_export.py` / quiz routes | Exports | wired (on request) | n/a | No | — |
| Baseline record | `guide_quality_baseline.py` | local harness (closed summary) | wired (advisory, repo-write-none) | advisory (non-blocking) | Closed summary only | metric families + `guide_text_coverage` counts |

---

## 7. Quality Safety and Measured Baseline History

Recent arc (closed labels from committed docs only):

- **Judge path frozen at synthetic-only** (Slice 148). The offline-judge
  scaffold (contract, schema fixtures, synthetic core, calibration gate
  protocol + synthetic harness, advisory artifact design, pure/unwired adapter)
  is complete only at synthetic level.
- `artifact_write_ready=false`, `ui_display_ready=false`, `judge_ready=false`,
  `repair_ready=false`, `calibration_status=synthetic_only`.
- **Measured baseline pivot** (Slice 149): a pure, deterministic, stdlib-only
  baseline aggregator that **reuses existing wired artifacts** rather than
  building a new evaluator stack; advisory and non-blocking.
- **Existing wired artifact reuse**: contract lint + QA gate + math verification
  (core), plus source coverage, report v2, rubric (supporting).
- **Reasoning leak failure and fixes**: Slice 150 triaged the first measured
  `reasoning_leak_status=fail`; Slice 151 hardened the prompt contract
  (final-output hygiene rule); Slice 154 added the line-initial discourse-marker
  rule.
- **Detector hardening** (Slice 152): two-tier reasoning-leak detector
  (word-boundary high-precision phrases + context-gated sentence-initial
  intensifiers) that removed false positives without weakening true-positive
  detection.
- **App-pipeline provenance gate** (Slice 153): verified the running app served
  the hardened detector/contract by matching stored vs recomputed leak counts.
- **Source coverage mapping fix** (Slice 155): added `completed` to the pass set
  in `_derive_source_coverage` (producer emits `completed`, aggregator only
  mapped `complete`/`ok`).
- **Closed local guide coverage scanner** (Slice 156): optional `--guide-text`
  local mode + closed alias checks make reference completeness and figure
  handling observable from closed counts only.

**Current `app_run_6` closed status (from committed docs only):**

- `reasoning_leak_status=pass`
- `source_coverage_status=pass`
- `reference_relative_completeness_status=pass`
- `figure_handling_status=pass`
- `baseline_status=warning`

**Remaining gap:** `numeric_math_status=not_available`; the QA-gate **warning**
remains (still recorded in committed docs). No failure is hidden — `baseline_status`
stays `warning` and is driven by the QA-gate warning + numeric `not_available`,
not by the newly-observed metrics.

---

## 8. Slice History Summary

Every slice on trunk (`chrome-renderer-v1`), in integration order, with commit
hash + purpose. All are **merged** except Slice 157 (this inspection slice, not
committed). Hashes are the integrated trunk commits; earlier feature work was
delivered on consumed branches (kept as archival reference, never re-merged).
Phases group the work; the headline detail for 147–156 is preserved in §7.

### Phase 0 — Integrated feature tracks (pre-unified numbering)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 1 | `482c377` | Add read-only shortcut inspector | Backend inspect endpoint for shortcuts | merged |
| 2 | `1f9034f` | Add read-only shortcut inspector UI | Surface inspector in Home shortcuts | merged |
| 3A | `e148cc4` | Shortcut repair preview + apply endpoints | Repair-loop backend | merged |
| 3B | `4458c9a` | Wire shortcut repair UI to preview/apply | Repair-loop frontend | merged |
| LMM 2 | `e27c674` | Detection-only Local Model status endpoint | LMM Phase 1 detection | merged |
| LMM 3 | `7429f24` | Local Models status panel | LMM Phase 1 UI | merged |
| LMM 4 | `e399f09` | Local-model command helper (copy start cmd) | Manual launch helper | merged |
| LMM 5 | `95132fe` | Validate LMM Phase 1 + reconcile docs | Phase 1 validation gate | merged |
| Ask 1 | `af0ec0e` | Design Ask Your Guide (local-only chat) | Ask Guide design (docs-only) | merged |

### Phase 1 — Claude-style UI reskin (Slices 2–17)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 2 | `371a6fc` | UI reskin shell — sidebar, topbar, layout grid + icons | App shell baseline | merged |
| 3 | `c8ad600` | UI reskin primitives (Button, StatusPill, Panel, etc.) | Shared component library | merged |
| 3.5 | `e3537f9` | Shell polish — nav labels + collapsible sidebar | Nav usability | merged |
| 3.6 | `456ff57` | Enlarge collapsed-sidebar nav icons | Nav polish | merged |
| 4 | `1d167bf` | UI reskin — Home (hero, Quick Launch, Favorites, Recent) | Home workspace | merged |
| 5a | `19cefcc` | UI reskin — Builder spine (shell, tabs, action bar) | Builder skeleton | merged |
| 5b | `7102d00` | UI reskin — Builder tab internals + density | Builder internals | merged |
| 5b-docs | `06b5fd4` | Record Slice 5b decisions (density baseline) | Decision log | merged |
| 6 | `e3a42df` | UI reskin — Library workspace | Library skin | merged |
| 7 | `14b849b` | UI reskin — Ask Guide workspace | Ask skin | merged |
| 8 | `95c64b3` | UI reskin — Styles workspace | Styles skin | merged |
| 9 | `7ef4bd5` | UI reskin — Models workspace | Models skin | merged |
| 10 | `598e1e6` | UI reskin — Exports workspace | Exports skin | merged |
| 11 | `15825aa` | UI reskin — final QA sweep (HomeShortcuts + Inspector) | Reskin QA | merged |
| 12 | `4274cf6` | Home and Library UX polish | UX polish | merged |
| 13 | `4af53a8` | UX redesign — Ask Guide workspace | Ask UX | merged |
| 14 | `c626404` | Feature — Compare styles | Style comparison tool | merged |
| 15 | `033e7d1` | UI reskin — Recent jobs and JobDetails body | JobDetails skin | merged |
| 16 | `eaa1263` | Post-reskin release audit + checkpoint | Release checkpoint | merged |
| 17 | `ff214fd` | Hygiene checkpoint — dead-code sweep + test cleanup | Cleanup | merged |

### Phase 2 — Deterministic verification & extraction (Slices 18–35)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 18 | `2c47d03` | Deterministic math verification core | Math verifier engine | merged |
| 19 | `9f1becf` | Deterministic guide lint core | Guide lint engine | merged |
| 20 | `2078c8d` | Eval harness Phase 1 — scoring framework | Deterministic scoring | merged |
| 21 | `a492e3b` | Persist math verification job artifact | `math_verification.json` | merged |
| 22 | `b932667` | Add JobDetails math verification UI | `MathVerificationPanel` | merged |
| 23A | `d4cd95b` | Verify source page-anchor reachability | Page-anchor checks | merged |
| 23B | `1aac60b` | Add source page citation directive + checks | Citation contract | merged |
| 23B-t | `b6c68c2` | Include Slice 23B citation coverage updates | Test coverage | merged |
| 24A | `226767c` | Persist PDF extraction metadata artifact | Extraction metadata | merged |
| 25A | `2e97f73` | Add Ask retrieval relevance baseline | Ask retrieval eval | merged |
| 25B | `ae44a85` | Improve Ask lexical retrieval hygiene | Ask lexical quality | merged |
| 26 | `a9263f0` | Reconcile project handoff docs | Docs reconciliation | merged |
| 27 | `0d73f24` | Persist guide lint job artifact | Guide lint artifact | merged |
| 28 | `f3bb0ad` | Add JobDetails guide lint UI | `GuideLintPanel` | merged |
| 29 | `d0b91f1` | Document hybrid OCR architecture | OCR design doc | merged |
| 30 | `752bf03` | Add PDF page visual metadata signals | Visual signals | merged |
| 31 | `ce0332e` | Add advisory PDF page classification metadata | Page classification | merged |
| 32 | `c42837c` | Add OCR provider boundary | OCR provider seam | merged |
| 33 | `5296976` | Add pure OCR routing policy core | OCR routing core | merged |
| 34 | `25e3fd3` | Record local OCR routing decisions in metadata | Routing provenance | merged |
| 35 | `45a54d2` | Verify Mistral OCR prerequisites | Mistral OCR verification | merged |

### Phase 3 — Visual / OCR / Chandra roadmap & visual pilot (Slices 36–75)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 36 | `976aebc` | Add visual and cost roadmap | Roadmap doc | merged |
| 37 | `9fbbb1d` | Add OCR mode and cost budget skeleton | OCR mode/budget | merged |
| 38 | `8a788c7` | Add visual assets manifest schema | Visual manifest schema | merged |
| 39 | `7b97146` | Verify Chandra local OCR feasibility | Chandra spike | merged |
| 40 | `bed7cf8` | Local figure extraction/cropping into manifest | Figure extraction | merged |
| 41 | `218de18` | Report Chandra GGUF hands-on spike | Chandra spike report | merged |
| 42 | `6e7f55f` | Add Chandra output normalizer core | Chandra normalizer | merged |
| 43 | `2bc14ef` | Add disabled Chandra local provider skeleton | Chandra provider (disabled) | merged |
| 44 | `8468c16` | Add Chandra live validation harness | Chandra harness | merged |
| 45 | `591d664` | Document Chandra live harness validation gate | Chandra gate doc | merged |
| 46 | `e8e69ed` | Add visual asset scoring core | Visual scoring | merged |
| 47 | `b1680fa` | Persist visual asset scoring artifact | Scoring artifact | merged |
| 48 | `967748a` | Add visual replacement planner core | Replacement planner | merged |
| 49 | `9338eb9` | Persist visual replacement plan artifact | Replacement artifact | merged |
| 50 | `1ed94c9` | Add Job Details visual advisory panel | `VisualAdvisoryPanel` | merged |
| 51 | `ee9be55` | Include visual advisory artifacts in export bundles | Export wiring | merged |
| 52 | `88c1aa8` | Add visual insertion planner core | Insertion planner | merged |
| 53 | `8c6d537` | Add Anki apkg export | Anki export | merged |
| 54 | `cdebbaa` | Add off-by-default visual markdown image pilot | Visual pilot (opt-out) | merged |
| 55 | `c2c4dd1` | Add per-job opt-in for visual markdown pilot | Pilot opt-in | merged |
| 56 | `2a09261` | Export referenced visual pilot asset | Pilot export | merged |
| 57 | `9c4ccc0` | Add visual pilot readiness guard | Pilot guard | merged |
| 58 | `39dc162` | Add visual pilot stitched E2E validation | Pilot E2E | merged |
| 59 | `a79e99d` | Add visual pilot operator validation harness | Pilot operator gate | merged |
| 60 | `4b5df88` | Add visual pilot quality gate | Pilot quality gate (trace stash parked here) | merged |
| 61 | `6d555a9` | Record post-fix visual pilot quality review | Quality review | merged |
| 62 | `798776e` | Add capped multi-figure visual pilot | Multi-figure cap | merged |
| 63 | `386226c` | Record cap-2 visual pilot operator validation | Validation record | merged |
| 64 | `edd27fd` | Prefer diagrams in visual pilot ranking | Diagram-first ranking | merged |
| 65 | `670309c` | Record diagram-first pilot operator validation | Validation record | merged |
| 66 | `5ffc53b` | Improve light table visual detection | Light-table detection | merged |
| 67 | `098500e` | Record light-table pilot operator validation | Validation record | merged |
| 68 | `9a8f10d` | Add sanitized visual pilot selection trace | Selection trace | merged |
| 69 | `2a33e11` | Record visual pilot selection trace audit | Trace audit | merged |
| 70 | `943480d` | Improve table diagram visual classification | Table/diagram class | merged |
| 71 | `a45bae8` | Record table diagram pilot operator validation | Validation record | merged |
| 72 | `5a23852` | Improve dense wrapped table classification | Dense-table detection | merged |
| 73 | `76e837b` | Record dense wrapped table pilot validation | Validation record | merged |
| 74 | `9e92e5a` | Add safe visual source page captions | Page captions | merged |
| 75 | `00c3f79` | Record visual pilot diverse validation gap | Gap record | merged |

### Phase 4 — Source coverage, page selection & material coverage (Slices 76–95)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 76 | `91e3845` | Add source coverage report core | Coverage engine | merged |
| 77 | `3ebfe54` | Persist source coverage report artifact | `source_coverage_report.json` | merged |
| 78 | `ee04f55` | Add page selection model core | Page-selection model | merged |
| 79 | `d4d2513` | Persist material page selection requests | Selection persistence | merged |
| 80 | `55eb243` | Persist per-attachment material page selections | Per-attachment selection | merged |
| 81 | `7ca109d` | Apply material page selections to extraction | Extraction filtering | merged |
| 82 | `fd3fb97` | Apply material page selections to visual manifests | Visual filtering | merged |
| 83 | `72e1f87` | Add full visual inclusion planner core | Inclusion planner | merged |
| 84 | `7cc9d6f` | Persist visual inclusion plan artifact | Inclusion artifact | merged |
| 85 | `8a1b780` | Add table reconstruction policy core | Table policy | merged |
| 86 | `3db8572` | Add material coverage E2E validation | Coverage E2E | merged |
| 87 | `844e394` | Add Builder page exclusion UI | Page exclusion UI | merged |
| 88 | `769d1f5` | Add JobDetails material coverage display | Coverage panel | merged |
| 89 | `b879590` | Add material coverage controls and warnings | Coverage warnings | merged |
| 90 | `096148f` | Add full non-table figure insertion v2 | Figure insertion v2 | merged |
| 91 | `ff7bc70` | Validate full figure render and export | Figure render E2E | merged |
| 92 | `ea3f321` | Add table candidate and policy artifacts | Table artifacts | merged |
| 93 | `774a2e4` | Add table reconstruction prompt context | Table prompt context | merged |
| 94 | `3264b92` | Add missing visual and table explainer | Missing-material explainer | merged |
| 95 | `c8d3c02` | Add coverage-aware generation prompt context | Coverage-aware prompt | merged |

### Phase 5 — Guide quality contract (Slices 96–107)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 96 | `2fc6d95` | Add guide quality report v2 | `guide_quality_report_v2.json` | merged |
| 97 | `e6e91df` | Finalize JobDetails material coverage panel | Coverage panel final | merged |
| 98 | `9f9d838` | Add Ask Guide coverage grounding | Ask grounding | merged |
| 99 | `e8d6f86` | Add dual explanation mode | Dual-explanation prompt | merged |
| 100 | `fbff55d` | Add full material coverage release validation | Coverage release gate | merged |
| 101 | `89f8532` | Support 100MB guide attachments | Large attachment limit | merged |
| 102 | `815a0dc` | Add guide quality prompt contract | `_CORE_RULES` chokepoint | merged |
| 103 | `71f5f8c` | Add guide quality QA gate | `guide_quality_qa_gate.json` | merged |
| 104 | `d5acd12` | Add JobDetails guide quality panel | `GuideQualityPanel` | merged |
| 105 | `10041b7` | Add guide quality rubric score | `guide_quality_rubric_score.json` | merged |
| 106 | `d34b39e` | Add guide quality release validation | Quality release gate | merged |
| 107 | `03cacc7` | Close guide quality phase | Phase checkpoint | merged |

### Phase 6 — Quality Safety scaffold (Slices 108–140)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 108 | `133e8e0` | Add quality safety eval harness skeleton | Eval harness | merged |
| 109 | `2bbd644` | Add quality safety seed fixtures | Seed fixtures | merged |
| 110 | `ff7c971` | Add quality safety fact-sheet schema | Fact-sheet schema | merged |
| 111 | `9d2050b` | Add quality safety recompute verifier | Recompute verifier | merged |
| 112 | `1606896` | Add quality safety canonical matcher | Canonical matcher | merged |
| 113 | `4b002c6` | Add quality safety leak scanner | Leak scanner | merged |
| 114 | `f3693dc` | Add quality safety unified QA report | `quality_safety_unified_qa.json` | merged |
| 115 | `92a4fb2` | Record quality safety operator validation | Operator validation | merged |
| 116 | `0bef077` | Harden quality safety leak scanner | Leak scanner hardening | merged |
| 117 | `e389697` | Add quality safety fact-sheet producer | Fact-sheet producer | merged |
| 118 | `c9644aa` | Add advisory quality safety job artifact | Advisory artifact | merged |
| 119 | `91a1134` | Display advisory quality safety artifact | Advisory display | merged |
| 120 | `06deb50` | Validate quality safety advisory E2E | Advisory E2E | merged |
| 121 | `b382eed` | Add quality safety extraction coverage adapter | Coverage adapter | merged |
| 122 | `979bb4e` | Wire quality safety coverage into advisory artifact | Coverage wiring | merged |
| 123 | `624a70e` | Validate quality safety real-disaster E2E | Disaster E2E | merged |
| 124 | `242d580` | Define quality safety numeric extraction contract | Numeric contract | merged |
| 125 | `13a7ef6` | Add quality safety numeric extraction mapper | Numeric mapper | merged |
| 126 | `7ff1887` | Wire numeric mapper into advisory artifact | Numeric wiring | merged |
| 127 | `35bdf8b` | Validate numeric sidecar artifact path | Numeric sidecar gate | merged |
| 128 | `8534784` | Design quality safety safe numeric extractor | Extractor design | merged |
| 129 | `0bff68c` | Add quality safety safe numeric extractor | Safe extractor | merged |
| 130 | `cd3a23b` | Wire safe numeric extractor into advisory artifact | Extractor wiring | merged |
| 131 | `9db63b1` | Discover quality safety safe candidate sources | Candidate discovery | merged |
| 132 | `9d48656` | Design future structured numeric artifact | Structured design | merged |
| 133 | `990179c` | Add structured numeric candidate adapter | Candidate adapter | merged |
| 134 | `244361a` | Wire structured numeric adapter into advisory artifact | Adapter wiring | merged |
| 135 | `c96e5f4` | Design structured numeric candidate producer | Producer design | merged |
| 136 | `eb13ada` | Define operator structured numeric export protocol | Export protocol | merged |
| 137 | `763fb4a` | Add operator structured numeric export validator | Export validator | merged |
| 138 | `cd7ac45` | Add operator numeric export validation harness | Export harness | merged |
| 139 | `c421465` | Add deterministic safety floor final gate | Deterministic floor gate | merged |
| 140 | `62b7b82` | Freeze quality safety surface | Surface freeze | merged |

### Phase 7 — Offline judge + freeze (Slices 141–148)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 141 | `b193d43` | Design offline judge contract | Judge contract | merged |
| 142 | `800b187` | Add offline judge schema fixtures | Judge schema/fixtures | merged |
| 143 | `0dedf99` | Add offline judge core synthetic v1 | Synthetic judge core | merged |
| 144 | `91e6c7d` | Define judge calibration gate protocol | Calibration protocol | merged |
| 145 | `8ad39c7` | Add judge calibration gate harness | Calibration harness | merged |
| 146 | `1f01231` | Design advisory offline judge artifact | Judge artifact design | merged |
| 147 | `effc9d9` | Add advisory offline judge artifact adapter (synthetic) | Pure/unwired adapter → write-ready synthetic payload | merged |
| 148 | `74ddf76` | Freeze judge path, redirect to measured baseline | Stop judge infra before real calibration; default measured baseline | merged |

### Phase 8 — Measured baseline hardening (Slices 149–156)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 149 | `7e298b6` | Measured guide quality baseline harness | Deterministic stdlib aggregator reusing wired artifacts + golden spec | merged |
| 150 | `d6f9f87` | Triage measured reasoning leak baseline failure | Closed-vocabulary triage; confirmed true leak vs false positive | merged |
| 151 | `d5d528a` | Harden guide prompt contract against reasoning leaks | Added final-output hygiene core rule | merged |
| 152 | `a1dfdd4` | Harden reasoning leak detector boundaries | Two-tier detector; removed false positives, kept true positives | merged |
| 153 | `af606d4` | Verify app-pipeline baseline provenance | Provenance gate: stored vs recomputed leak counts match | merged |
| 154 | `1dae76f` | Harden prompt contract for line-initial discourse leaks | Forbid sentence-initial `Actually,`/`Presumably,` markers | merged |
| 155 | `35c6b71` | Observe source coverage baseline status | Added `completed` to source-coverage pass set + regression test | merged |
| 156 | `8f27091` | Closed local guide-text coverage scanner | Optional `--guide-text` mode + closed alias checks observe reference completeness + figure handling | merged (trunk head) |

### Phase 9 — Inspection (Slice 157)

| Slice | Hash | Title | Purpose | Status |
|---|---|---|---|---|
| 157 | — | Current App State Inspection Report | This report — full current-state inspection / analysis / documentation; no runtime/API/frontend/backend/pipeline/test change | **NOT committed** |

---

## 9. Test and Validation Inventory

Tests live under `test_scripts/*.py` (pure `test_*` + `smoke_*` + `validate_*`
harnesses; no test runner) and `frontend/scripts/*.mjs` (pure-node verify).

- **Guide quality baseline** — `test_guide_quality_baseline.py`,
  `validate_guide_quality_baseline_harness.py`.
- **Prompt contract** — `test_guide_quality_prompt_contract.py`,
  `test_guide_quality_contract_integration.py`.
- **Contract lint** — `test_guide_quality_contract_lint.py`.
- **QA gate** — `test_guide_quality_qa_gate.py`,
  `test_guide_quality_report_v2.py`, `test_guide_quality_rubric_score.py`,
  `test_guide_quality_release_validation.py`.
- **Math verification** — `test_math_verifier.py`, `test_math_artifact.py`,
  `test_math_regressions.py`, `test_long_formula_guidance.py`.
- **Source coverage** — `test_source_coverage_report.py`,
  `test_source_coverage_artifact.py`, `test_source_page_citations.py`,
  `test_page_reference_format.py`, `test_material_coverage_e2e_validation.py`,
  `test_full_material_coverage_release_validation.py`.
- **Visual pilot** — `test_visual_*` (asset scoring, manifest, inclusion/
  insertion/replacement planners, markdown render, multifigure, table/diagram
  precision, quality gate, selection-trace sanitized, e2e validation),
  `test_table_*`, `test_local_figure_extraction.py`.
- **Ask Guide** — `test_ask_context_inventory.py`, `test_ask_context_prepare.py`,
  `test_ask_coverage_grounding.py`, `test_ask_lexical_hygiene.py`,
  `test_ask_local_chat.py`, `test_ask_retrieval_relevance.py`.
- **Provider / local model** — `test_provider_*`, `test_default_provider_precedence.py`,
  `test_local_model_*`, `test_lmm_*`, `validate_lmm_*`.
- **Quality safety** — `test_quality_safety_*` + `validate_quality_safety_*`
  (synthetic harnesses).
- **OCR / extraction / preflight** — `test_ocr_*`, `test_extraction_metadata.py`,
  `test_pdf_*`, `test_page_selection*`, `test_pdf_preflight.py`,
  `test_large_attachment_limits.py`, `test_mixed_pdf_ocr.py`.
- **Frontend verify scripts** — `frontend/scripts/verify-*.mjs` (ask-guide,
  guide-quality-panel, guide-lint, math-verification, material-coverage*,
  shortcut*, local-model*, style-compare, visual-pilot-opt-in, dual-explanation,
  job-details-visual-advisory).
- **Release / smoke validation** — `smoke_release.py`, `smoke_*` (docx exports,
  exports center, library bulk/power tools, outline, quiz, save-to-folder).

**Safe commands commonly used:**

```fish
python -m compileall api pipeline test_scripts
python test_scripts/test_guide_quality_baseline.py
python test_scripts/validate_guide_quality_baseline_harness.py
python test_scripts/test_guide_quality_prompt_contract.py
python test_scripts/test_guide_quality_contract_lint.py
python test_scripts/test_guide_quality_qa_gate.py
git diff --check
```

(Many endpoint sections skip when FastAPI is unavailable in host Python; run in
Docker for full coverage. Do **not** run `docker compose config`.)

---

## 10. Current Gap / Risk Register

| Gap / risk | Evidence | Impact | Current status | Recommended next slice |
|---|---|---|---|---|
| Numeric math not measured | `numeric_math_status=not_available`; golden `known_numbers=[]` | Numeric correctness unscored | Deferred (`needs_operator_known_numbers`) | Slice A: operator known-numbers spec |
| QA-gate warning persists | `guide_quality_qa_gate_status=warning` on `app_run_6` (committed docs) | Baseline can't reach green | Open (non-blocking) | Slice B: QA-gate warning triage |
| Style/preset audit not run | `next_step=style_preset_audit_gate` (committed docs) | Per-style output quality unmeasured | Pending (now unblocked) | Slice C: style/preset audit gate |
| Figure handling shallow | Observed only via closed alias checks (Slice 156) | Pass may be coarse | Measured but coarse | Slice F: figure-handling refinement |
| Reference completeness shallow | Alias-check observation only | Pass may be coarse | Measured but coarse | Slice G: reference completeness refinement |
| Visual/table handling long-term | Large `visual_*` advisory set, opt-in only | Figures/tables not first-class | Advisory only | Slice H: visual/table roadmap checkpoint |
| Judge path frozen | `judge_ready=false`, `calibration_status=synthetic_only` | No real LLM-judge scoring | Intentionally frozen | (none — keep frozen until real calibration) |
| Docs bloat / drift | 40+ docs under `docs/`; per-slice log growing | Onboarding cost, drift risk | Open | Slice J: docs consolidation checkpoint |
| Synthetic-only tests/artifacts | Quality-safety harnesses synthetic; offline judge unwired | False confidence if treated as measured | Labeled synthetic | (keep labeled; no action) |
| LMM remaining work | Phase 2 paused; approve-root flow deferred | No managed approve-root | Paused by design | Slice I: LMM/provider stability (only if needed) |

---

## 11. Recommended Next 10 Slices

Measured-data-first discipline (close measured gaps before adding features):

1. **Numeric known-numbers spec** — add operator-confirmed closed
   `known_numbers` to the golden spec so `numeric_math_status` can move off
   `not_available` (closed numeric labels only; no source text).
2. **QA-gate warning triage** — closed-vocabulary triage of the persistent
   `guide_quality_qa_gate_status=warning` on `app_run_6`; decide whether it is a
   true content gap, a gate-threshold artifact, or a mapping issue.
3. **Style/preset audit gate** — run the baseline across generator/outline
   presets and compare closed aggregate metrics (advisory, no committed private
   content). This is the currently-flagged `next_step`.
4. **First measured guide-quality improvement** — act on the highest-signal gap
   the audit/QA-gate triage surfaces, with a narrow prompt-contract or pipeline
   fix.
5. **Post-fix regeneration gate** — verify the improvement on a fresh
   app-pipeline regeneration with closed-summary provenance (matching stored vs
   recomputed counts).
6. **Figure handling refinement** — deepen the closed figure-handling check
   beyond a single alias match if the audit shows it is too coarse.
7. **Reference completeness refinement** — refine reference completeness beyond
   alias checks (e.g. weighted required-concept coverage), still closed-vocabulary.
8. **Visual / table roadmap checkpoint** — assess the advisory `visual_*` stack
   and decide a measured, privacy-safe path to first-class figure/table handling.
9. **Local model / provider stability** — only if a real gap appears; LMM
   approve-root stays deferred to a separately-designed host-companion slice.
10. **Release / readiness checkpoint** — run `smoke_release.py` + the quality
    suite, reconcile docs, and record a closed readiness snapshot.

---

## 12. New Chat Handoff

```
Repo path:           main-app/  (Study Guide Generator working dir; canonical brief ../CLAUDE.md)
Trunk:               chrome-renderer-v1
Latest commit:       8f27091  (Slice 156 — closed local guide-text coverage scanner)
Current phase:       Measured guide-quality baseline hardening (judge path frozen synthetic-only)
Active branch:       slice157-current-app-state-inspection-report (inspection report; NOT committed)
Measured baseline (app_run_6, committed closed labels only):
  reasoning_leak_status=pass
  source_coverage_status=pass
  reference_relative_completeness_status=pass
  figure_handling_status=pass
  baseline_status=warning
  numeric_math_status=not_available  (QA-gate warning still present)
Next recommended slice: numeric known-numbers spec, then QA-gate warning triage,
                        then the style/preset audit gate (next_step=style_preset_audit_gate)

Critical hard rules:
  - Trunk is chrome-renderer-v1; branch per slice; no force-push.
  - Do not revive consumed branches; do not disturb the parked Slice 60 stash.
  - Do not run/paste `docker compose config`.
  - Commit closed vocabulary only — no guide text, snippets, matched aliases,
    source text, raw artifacts, hashes, byte counts, paths, screenshots, PDFs,
    DOCX, ZIPs, provider payloads, or secrets. local_operator_baselines/ stays
    ignored.
  - All clean.md writes go through JobManager.save_clean_md.
  - Keep /api/* routes registered before the SPA static mount.
  - Judge path stays frozen: do not set judge_ready/repair_ready=true; do not
    weaken true-positive leak detection or patch the aggregator to hide failures.
  - Chandra blocked unless explicitly cleared; no new external service calls.
  - If code disagrees with docs, trust code and verify before editing.
```

---

*Slice 157 inspection report — documentation only; no runtime/API/frontend/
backend/pipeline/test changes. Based on trunk `chrome-renderer-v1` @ `8f27091`.*
