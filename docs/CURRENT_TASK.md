# CURRENT_TASK.md — Live handoff

> Update this every slice. For stable overview see `PROJECT_CONTEXT.md`; for the
> "why" behind choices see `DECISIONS.md`.

---

## Where we are

- **Branch:** `home-nav-cleanup`
- **Last commit:** `7f78542` — Clean up Home shortcuts navigation (C5)
- **Main branch (PR target):** `chrome-renderer-v1`
- **Group C is COMPLETE** (C1 → C5).

## DONE (in order)

1. **Generator presets** — Claude-Exam / Review / Cram: full system prompts +
   tuned sampling params (`a97d763`).
2. **Slice 3 — env-configurable attachment caps** (200k/600k default) +
   preset-aware truncation warning (`6f4d28c`).
3. **Slice 4 — math degrade** — math validation failures degrade to marked spans
   instead of killing the job; math prompt hardened (`9ba7e52`).
4. **Slice 5 — cleanup/hardening** — removed `legacy_scripts` + stray root files;
   redact host paths in error responses (`f3a8d84`).
5. **Slice 1A** — job stage reporting in pipeline + `/api/jobs/{id}/progress`
   endpoint (`d3d75fd`).
6. **Slice 1B** — persistent Builder action bar, live progress button,
   dirty-state warning, tooltips (`ec34d59`); progress poll tuned to 300ms
   (`f6424c9`).
7. **Slice 2A** — backend shortcut store with whitelist-validated import/export,
   defaults, 11 endpoints (`72fa2cd`).
8. **Slice 2B** — Home shortcuts UI, customize modal, import/export,
   save-as-shortcut (`afab4f2`).
9. **Slice 3/B1 — Library bulk actions (BACKEND ONLY)** — `51fc7b9`. Three
   partial-success endpoints under `/api/jobs/bulk/*` (`delete`/`restore`/
   `move`) that **reuse the existing single-item internals**: bulk delete →
   `trash_job` (soft-delete to `jobs/.trash/`, guarded by
   `_guarded_trash_target` — never hard-deletes), bulk restore → `restore_job`,
   bulk move → `library_store.move_job` (existing `folder_id` model). Routes
   registered **before** the parametric `/api/jobs/{job_id}/restore` so the
   literal `bulk` segment is never read as a job id. Verified in Docker (uid
   10001/appuser) via `test_scripts/smoke_library_bulk.py` (16/16) +
   curl/`ls .trash` evidence. **Frontend multi-select UI is NOT in this slice.**
10. **Slice B2 — Library multi-select bulk actions UI (FRONTEND)** — `5916861`.
    Library multi-select with per-job checkboxes + **select-all-visible**, a
    selection-aware bulk toolbar (Move to folder / Move to Unfiled / **Delete** /
    Clear), **bulk delete** routed through the soft-trash with an **Undo toast**
    (bulk restore of exactly the trashed ids), and **bulk move-to-folder**. All
    three use the canonical `/api/jobs/bulk/*` family; the legacy
    `/api/library/jobs/move` caller was migrated to `/api/jobs/bulk/move`
    (`folder_id`, not `folder`). Partial-success aware (`partitionResults`):
    succeeded ids cleared, `error` ids kept selected, ok/fail counts toasted;
    whole-request 404 (unknown folder) keeps selection + list untouched.
    Selection clears on folder/search/filter change. Verified in Docker via a
    real headless-Chromium (Playwright) click-through + captured bulk network
    calls; release smoke 28/28 (flaky outline check passed 3/3 in preflight).
11. **Slice B3 — finish Library folder + trash actions (FRONTEND + 1 backend
    route)** — `f1201a0`. **Folder multi-select** in the rail (per-folder
    checkboxes on non-system folders) + a folder action bar (count / Delete /
    Clear). **Bulk folder delete** offers BOTH behaviors via a dedicated
    two-path modal: **(A) Delete folders only** → guides fall back to Unfiled
    (loops the existing `DELETE /api/library/folders/{id}`), and **(B) Delete
    folders + move guides to Trash** → guides soft-deleted via the existing
    `/api/jobs/bulk/delete` (trash, NOT hard-delete) before the folders are
    removed. Partial-success aware: failed folders stay selected, successful
    ones disappear, ok/fail (+ trashed count) toasted. **Trash view** gained
    **multi-select** (per-card checkboxes + select-all), **Restore selected**
    (`/api/jobs/bulk/restore`), and **Permanently delete selected** behind a
    strong "cannot be undone" confirm. New backend route **`POST
    /api/jobs/bulk/purge`** loops the existing guarded `purge_trashed_job`
    (operates strictly inside `jobs/.trash/`; no new `rmtree` path) and refuses
    any id not currently trashed. Verified in Docker (smoke 28/28) + curl:
    bulk/purge returns ok for a trashed id and `error: not in trash` for
    bogus / `../escape` / active ids (active job untouched on disk); Option A
    leaves the guide active+Unfiled; Option B lands the guide in Trash and gone
    from active; bulk/restore returns a purged job to active.

12. **Slice C1 — expanded output-section toggles (BACKEND + prompt assembly)** —
    `fe898c4` (branch `style-output-toggles`). Added a real `include_sections`
    dict-of-bool field to `LLMJobRequest`, threaded
    `LLMJobRequest → run_llm_job → generate_study_guide → orchestrator`. Investigation
    first confirmed the pre-existing "module" keys (`mcqs`/`glossary`/… in
    `shortcut_store.KNOWN_MODULE_KEYS` + `frontend/shortcutMeta.js`) were
    **shortcut-only UI state** that **never reached prompt assembly**, so a new
    backend mechanism was required (per the STEP-1 stop rule, confirmed with the
    operator before building). Single source of truth is `INCLUDE_SECTION_FRAGMENTS`
    in `pipeline/orchestrator.py` (21 canonical keys: the 18 target toggles + 3 kept
    legacy keys); legacy keys normalise via `INCLUDE_SECTION_ALIASES`
    (`mcqs→mcqs_with_answers`, `formulas→formula_sheet`, `diagrams→diagrams_figures`).
    **New toggles default off** — an unset/empty/unknown-only map produces a
    **byte-identical** system message (verified: default `== MARKDOWN_MATH_SYSTEM`;
    preset path `== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`). Enabled fragments are
    injected **before** `MARKDOWN_MATH_SYSTEM`, which **remains the final block** in
    both default and preset paths; order is deterministic (insertion order). Unknown
    keys ignored (whitelist convention). `include_sections` is persisted in the job
    manifest so **rerender** reproduces the same sections. Verified in Docker (uid
    10001/appuser): in-container orchestrator proof of fragment presence/ordering for
    7 toggles, a real DeepSeek generation whose guide followed the requested sections
    (Glossary / MCQs+Answer Key / Worked examples / Formula sheet; slide refs
    correctly omitted as the source had none), manifest persistence confirmed; release
    smoke **28/28** (flaky outline-ordering check passed). **Builder UI exposure
    deferred to C3; depth/difficulty/voice deferred to C2; shortcut
    whitelist/persistence extension deferred.** Also documented the prior bulk-purge
    decision in `DECISIONS.md`.

13. **Slice C2 — generation depth + difficulty axes (BACKEND + prompt assembly)** —
    `24442bd` (branch `style-axes`). Added two **optional scalar-enum** global
    generation-directive axes to `LLMJobRequest`: `output_depth`
    (`quick`/`balanced`/`exhaustive`) and `difficulty`
    (`beginner`/`normal`/`exam_level`/`advanced`), threaded
    `LLMJobRequest → run_llm_job → generate_study_guide → orchestrator` (mirroring C1)
    and **persisted in the job manifest** so rerender/retry reproduces them. Source of
    truth: `OUTPUT_DEPTH_FRAGMENTS` / `DIFFICULTY_FRAGMENTS` in
    `pipeline/orchestrator.py`; assembled via `build_axis_directives_block`.
    - **Axes default unset.** With both unset the system message is **byte-identical**
      to before (verified: default `== MARKDOWN_MATH_SYSTEM`; preset path
      `== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`). Unknown/None axes add no fragment.
    - **Assembly order:** preset system prompt (preset path) → **axes** →
      **include_sections** → `MARKDOWN_MATH_SYSTEM`. Axes inject **before**
      include_sections; `MARKDOWN_MATH_SYSTEM` **remains the final block** in both paths.
    - **`voice` was DROPPED** — STEP-1 found it duplicates the Styles system
      (`baby_steps`/`exam_cram` styles + "blunt voice"/"formal" prompt directives);
      confirmed with the operator. **Voice/tone remains owned by Styles.** `difficulty`
      does **not** duplicate `mode` (mode is vestigial free-text with no difficulty
      semantics).
    - **Validation:** unknown axis values rejected at the API boundary (`HTTP 400`),
      orchestrator ignores unknowns defensively.
    - **Verified in Docker** (uid 10001/appuser, container healthy): in-container
      orchestrator proof of byte-identical no-axes paths + ordering (depth<difficulty<
      sections<MATH); a real DeepSeek generation with `output_depth=quick` +
      `difficulty=exam_level` + `include_sections={glossary, mcqs_with_answers}` whose
      guide showed a definitions table + MCQs/Answer Key (concise, exam-pitched);
      manifest persisted both axes + sections; invalid `output_depth`/`difficulty`
      returned 400. Release smoke **28/28** (flaky outline-ordering check passed).
    - **Builder UI exposure deferred (C3); shortcut persistence bridge deferred.**

14. **Slice — shortcut options persistence bridge (BACKEND ONLY)** — `cc75292`
    (branch `shortcut-options-bridge`). Extended the `builder_setup` shortcut
    payload whitelist (`pipeline/shortcut_store.py:_normalize_payload`) with the
    real C1/C2 generation fields: `include_sections` (canonical dict-of-bool),
    `output_depth`, and `difficulty`. **Closes the "legacy shortcut modules are
    inert" gap at the backend shortcut boundary** — shortcuts can now carry the
    fields that actually reach prompt assembly.
    - **Reuses C1 normalization** — `include_sections` is validated through
      `orchestrator.normalize_include_sections` + `INCLUDE_SECTION_ALIASES`
      (no second alias table); unknown keys dropped, only canonical enabled keys
      stored.
    - **Axes validated, not coerced** — invalid `output_depth`/`difficulty` are
      **rejected** via `ShortcutStoreError` (→ HTTP 400 on create/update; import
      pushes the offending shortcut into the batch `errors` list), never silently
      persisted. Unset → `None`.
    - **Legacy `modules` translate-on-read** — `_bridge_payload` derives
      `include_sections` from legacy `modules` in the **returned/exported**
      representation only (`_public` + `_exportable`); explicit `include_sections`
      wins, legacy modules only fill missing sections. **`shortcuts.json` is never
      rewritten on read** — old shortcuts stay old on disk until the user
      explicitly creates/updates/imports.
    - **Verified in Docker** (uid 10001/appuser, healthy): Test A create/read
      canonical round-trip; Test B export→import-preview→import (fields survive,
      id regenerated on conflict, no silent overwrite); Test C invalid axes → 400
      / import `errors`, unknown section key dropped; Test D legacy modules-only
      injected in-container translated to canonical sections on GET **and** export
      with **identical sha256 before/after** (disk still has no `include_sections`);
      Test E old field-less shortcut loads cleanly, nothing forced. Unit test
      `test_scripts/test_shortcut_store.py` **39/39**; release smoke **28/28**
      (flaky outline check passed).
    - **Builder UI wiring (load fields into Builder state + send to
      `/api/jobs/llm`) is the NEXT slice — NOT done here.**

15. **Slice C3 — expose output sections + axes in the Builder (FRONTEND + 1
    backend form-parser fix)** — `7af9cbd` (branch `builder-options-ui`).
    Surfaces the C1 `include_sections` + C2 `output_depth`/`difficulty` fields in
    the Builder and round-trips them through save/load shortcuts and the local
    draft.
    - **New `frontend/src/sectionMeta.js`** holds the display metadata only:
      21 section toggles in 4 cosmetic groups (Practice/Reference/Exam help/
      Source-aware) + the axis option tables + `normalizeSectionState`/
      `hasEnabledSections`. **The backend owns the key set** — every key mirrors
      `INCLUDE_SECTION_FRAGMENTS`/`OUTPUT_DEPTH_FRAGMENTS`/`DIFFICULTY_FRAGMENTS`
      in `pipeline/orchestrator.py` (verified 1:1, no invented keys). The frontend
      never widens the vocabulary.
    - **Builder UI:** replaced the old free-text `includes` chips with grouped
      `SectionControls` toggles + a new `AxisControls` (two segmented rows, "Auto"
      = unset). Action bar gained Sections + Axes summary chips. Legacy
      `includesToModules`/`modulesToIncludes`/`includeOptions` removed.
    - **Default stays clean:** `buildLlmPayload` omits `include_sections` when no
      section is enabled and omits each axis when unset, so a fresh Builder
      generate request carries none of these fields (and never a `voice` field —
      voice stays owned by Styles). Sections no longer appended as free text in
      `augmentSourceText`.
    - **Save/load shortcut wiring:** `builderStateToPayload` now emits the
      canonical `include_sections` + axes (not the inert legacy `modules`);
      `applyBuilderPrefill` reads them back and re-normalizes sections via
      `normalizeSectionState` (drops keys the Builder no longer exposes).
    - **Local draft parity:** `buildDraft`/`handleRestoreDraft` now persist +
      rehydrate the canonical fields (restore re-normalizes), replacing the old
      `includes` they used to carry. Dirty-state `settingsSignature` already
      covers all three, so changing a section/axis after a generation marks the
      preview stale.
    - **Backend form-parser fix:** the multipart branch of `_parse_llm_request`
      (`api/server.py`) now reads `include_sections` (JSON string → dict) +
      `output_depth`/`difficulty`. **Without this the options were silently
      dropped whenever a generation had attachments** (the no-attachments JSON
      path already worked). See `DECISIONS.md`.
    - **Verified in Docker** (uid 10001/appuser, healthy): frontend build OK; an
      esbuild-bundled harness drove the real `buildLlmPayload`/
      `builderStateToPayload`/`normalizeSectionState` (default omits all 4 incl.
      `voice`; selected sends canonical sections+axes; save→load→generate
      round-trips; unknown keys dropped on load; empty shortcut → `{}`/null).
      Live end-to-end: JSON-path job persisted sections+axes to `job.json`;
      **multipart-path job WITH an attachment persisted `{flashcards,
      formula_sheet}` + `exhaustive`/`advanced`** (proves the fix); default job →
      `{}`/null/null; invalid `output_depth` → HTTP 400. Release smoke **28/28**.
    - **NOT automated — needs manual click-through:** visual layout/spacing of the
      new grouped toggles + segmented axes, and tooltip hover behaviour
      (`InfoTip`/`FieldLabel tip`). DOM presence + wiring are proven; pixel
      layout is not.

16. **Slice C4a — generator preset display metadata + `model_hint` exposure
    (BACKEND ONLY)** — `3820c0c` (branch `preset-metadata`). Added three
    **display-only** descriptive fields to the canonical generator-preset registry
    (`_PRESET_DEFS` in `pipeline/generator_presets.py`) ahead of the preset-card UI:
    `purpose` (short purpose label), `recommended_use` (one-line "best with …"
    guidance), and `model` (clean model-name string for an icon/model chip, distinct
    from the longer prose `model_hint`). All exposed through the **existing**
    `_public()` → `list_generator_presets()` → `/api/options.generator_presets` path —
    **no new endpoint, no schema migration**. `name`/`description`/`provider`/
    `model_hint` already existed and were already exposed; this slice only **added the
    three missing fields**.
    - **`model_hint` exposed as a SOFT advisory only.** Unchanged semantics: the preset
      path only **soft-warns** on a provider mismatch (`generator_preset_warning`) and
      never blocks; the user can still pick any provider+model. C4a adds **no**
      enforcement and **no** hard pin.
    - **Display-only proof (source + grep):** `purpose`/`recommended_use`/`model` appear
      **only** in the registry defs and `_public`, nowhere in `orchestrator.py`/
      `run_llm_job.py`/the `/api/jobs/llm` handler. Generation still reads only `block`
      (→ system prompt), the sampling params, and `provider`/`model_hint`/`name` (warning
      text). `_public` reads the new fields via `.get()` so a preset omitting one
      serializes it as `None` instead of raising. Existing preset ids unchanged.
    - **Verified in Docker** (uid 10001/appuser, healthy): `python -m compileall`,
      `docker compose config/build/up`; `/api/options` shows all three presets carrying
      `purpose`/`description`/`recommended_use`/`model`/`model_hint`/`provider`; a
      full-payload secret scan (`sk-`/`api_key`/`secret`/…) found **no** leak. A live
      `claude_review` generation on DeepSeek completed `done` (no mismatch warning — it
      ran on its tuned provider) and the job manifest recorded `generator_preset:
      claude_review` unchanged, with **none** of the new display fields in the manifest.
      Release smoke **27/28 then 28/28** — the only failure was the **known flaky
      outline-ordering check**, which passed on rerun (pre-existing, depends on LLM
      output order, unrelated to this backend metadata change).
    - **Frontend preset cards / icons / compatibility warning deferred to C4b.** Do not
      hardcode card data in the frontend — it must consume this backend metadata.
    - Also added the permanent `DECISIONS.md` rule: any future `/api/jobs/llm` request
      field must be wired into **both** the JSON and multipart paths and verified in both.

17. **Slice C4b — generator preset cards + soft compatibility warning
    (FRONTEND ONLY)** — `b3d7785` (branch `preset-cards-ui`). Renders the C4a
    generator-preset metadata as preset **cards** in the Builder Style tab and adds
    a soft, advisory model-compatibility warning. **Consumes backend data only** —
    no preset copy is hardcoded; the cards read `name`/`purpose`/`description`/
    `recommended_use`/`model`/`model_hint`/`provider`/`params`/`available` from
    `/api/options.generator_presets` (the **generator** preset list from
    `generator_presets.py`, NOT the purpose/outline `presets.py`).
    - **New `frontend/src/presetMeta.js`** (display/compat helpers only): provider
      id → local SVG icon map (`providerIconFor`), text-badge fallback
      (`providerLabelFor`), and the soft `presetCompat(preset, selectedModel)`
      matcher. Three local SVGs committed under
      `frontend/src/assets/providers/{deepseek,qwen,local}.svg` (Vite resolves them
      to emitted asset URLs — 54–82 KB, above the 4 KB inline limit, so they are
      **separate files**, not JS-inlined). Logos render on a small **white chip**
      because Qwen/Local marks are near-black and would vanish on the dark UI; a
      missing/broken icon falls back to the text badge (`onError` + badge sibling),
      never blocking card render.
    - **Cards** (`GeneratorPresetCard` + rewritten `GeneratorPresetControls`):
      provider icon/badge, `model` chip, preset name, purpose label, description,
      recommended-use ("Best for: …"), selected ring + check. `available:false`
      greys/disables the card per the existing convention. The "None (use style)"
      option is kept. **Selection semantics unchanged** — a card still sets the same
      `generatorPreset` id the old chip selector did; the generate payload is
      untouched.
    - **Soft compatibility warning** replaces the old provider-mismatch note with a
      `model_hint`-vs-selected-model advisory: shown only when a preset is selected
      **and** it has a `model_hint` **and** the selected model is a confident
      non-match. Matching (`presetCompat`) normalises both sides to alphanumeric-only
      tokens and accepts equality/containment against **both** the prose `model_hint`
      **and** the cleaner `model` chip string (so "Gemma 4" rescues the local
      `gemma-4-…gguf` id where the longer prose hint would false-positive). Prefers
      **no** warning when unsure (no hint / unknown model → no warning). Warning copy:
      "This preset is tuned for {model_hint}. It may still work with {selectedModel},
      but {model_hint} is recommended." Plus an InfoTip restating it is advisory.
    - **Advisory-only — never blocks.** The Generate button stays `disabled={running}`
      only (never gated on compat); `buildLlmPayload` sends the user's `model` +
      `generator_preset` independently of the warning. **Proven end-to-end:** a live
      `claude_review` (hint "DeepSeek V4 Pro") generation with the **non-hint**
      `deepseek-chat` model completed `done`; the job manifest recorded
      `generator_preset: claude_review` + `model: deepseek-chat` (the user's choice).
    - **Tooltip priority adjusted** (`sectionMeta.js`): removed tips from the obvious
      controls (MCQs ×2, Flashcards, Glossary) and added/kept them on the less
      obvious ones (TL;DR summary, cram sheet, exam alerts, common mistakes,
      diagrams/figures, solved mock exam, self-test checklist, definitions cheat
      sheet, summary tables, instructor notes) plus the existing
      formula-sheet/worked-examples/citations/slide-refs tips and the new
      model-compatibility tip. Uses the existing `InfoTip` system — no new tooltip
      mechanism.
    - **Verified in Docker** (uid 10001/appuser, healthy): frontend build OK (SVGs
      emitted as separate assets); an esbuild harness drove the real `presetCompat`
      through **10/10** match/mismatch/absent cases (incl. the local-gemma rescue and
      the unsure→no-warning cases) + icon URL/badge fallback; served bundle contains
      the card/warning strings and references all three SVGs (served `200
      image/svg+xml`); `/api/options` unchanged; release smoke **28/28** (flaky
      outline check passed). **C3 controls confirmed intact** in the served bundle
      (axes Exhaustive/Exam-level, sections Cram sheet/Worked examples, Save draft,
      action bar/shortcut/progress markers).
    - **NOT automated — needs manual click-through:** card visual layout/spacing,
      provider-icon visual quality, warning placement/legibility, tooltip hover
      behaviour, overall UX feel.

18. **Slice C4c — add Qwen `qwen3.7-plus` to the model registry (REGISTRY ONLY)** —
    `390060c` (branch `qwen37-plus-model`). Added the model id `qwen3.7-plus` to
    `QWEN_MODELS` in `pipeline/provider_config.py` — the **single source of truth**
    for the Qwen model list surfaced through `/api/options` (`models.Qwen` +
    `provider_details[qwen].available_models`) and enforced by
    `validate_provider_model` (a model must be in `QWEN_MODELS` to be accepted).
    - **Ordering:** inserted at index 1, immediately after `qwen3.7-max`, next to the
      other 3.7-family model. **Default unchanged** — the Qwen default is
      `os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL") or QWEN_MODELS[0]`, and
      `qwen3.7-max` is still `QWEN_MODELS[0]`, so `default_model` stays `qwen3.7-max`.
      `qwen3.7-max` was not replaced; all six existing Qwen ids remain.
    - **Scope:** registry list only — no Builder UI, preset cards, prompt assembly,
      shortcut store, provider-settings architecture, Local Model Manager, or
      generation-pipeline behaviour changed (beyond now accepting this model id). The
      Builder's static `fallbackProviderDetails` Qwen list (a pre-`/api/options`
      placeholder) was intentionally left untouched — the real, authoritative list
      comes from `/api/options` and now includes `qwen3.7-plus`.
    - **Verified in Docker** (uid 10001/appuser, healthy): `compileall` OK; `compose
      config/build/up` OK; `/api/options` shows `qwen3.7-plus` in `models.Qwen` and
      `provider_details[qwen].available_models` (position 2), `default_model` still
      `qwen3.7-max`, all existing Qwen models present; full-payload secret scan clean.
      **Live generation verified:** a real `provider=qwen` + `model=qwen3.7-plus`
      generation completed `done` (manifest recorded `model: qwen3.7-plus`, 2716-byte
      `clean.md` with genuine study-guide content) — not just options exposure.

19. **Slice C5 — Home/nav cleanup + non-destructive stack merge preview
    (FRONTEND ONLY + preview)** — `7f78542` (branch `home-nav-cleanup`).
    Closes Group C by cleaning the Home page. **Cleanup, not a redesign.**
    - **Duplicate lower "Customize" button removed.** The Home "Pinned shortcuts"
      section head carried a second `Customize` button (`HomeShortcuts.jsx`)
      identical in behaviour to the page-head entry. Removed it; the section head
      now shows just its `<h2>`.
    - **Single primary entry kept:** the page-head **"Customize Shortcuts"**
      button. It calls `setCustomizeOpen(true)` → opens `CustomizeShortcutsModal`
      (the shortcut customization modal). **It does NOT route to Styles** — proven
      in the served bundle (exactly one "Customize Shortcuts" string; the modal is
      the shortcut editor, no Styles navigation on that handler).
    - **Smart Tools:** **already absent from Home** — no Smart Tools UI exists
      anywhere in the frontend (only orphaned `.sg-smart-*` CSS + an unrelated
      `Smartphone` icon import in the unused, never-rendered `TopBar.jsx`). Nothing
      to remove; it was not the sole entry point to anything. Orphaned CSS left
      untouched (cleanup-only, no behaviour change).
    - **Compare Styles:** **already lives in Styles, no move needed.** It is not a
      hardcoded Home button — it exists only as a `compare_styles` *shortcut tool
      type* (`shortcutMeta.js`) that routes to Styles via `TOOL_ROUTES`
      (`DesktopDashboard.jsx`). The Styles workspace **is** the compare surface
      ("Compare built-in prompt presets side by side…", `StylesWorkspace.jsx`,
      verified present in the served bundle).
    - **Home focus preserved:** pinned shortcuts + Recent Guides (`RecentJobsPanel`).
      No "continue last setup / continue last guide" feature exists on Home — there
      was nothing of that kind to preserve.
    - **Scope held:** diff is a single 3-line deletion in `HomeShortcuts.jsx`. No
      backend, Builder, Library, prompt assembly, shortcut store, provider model
      registry, Local Model Manager, provider settings, cancel, or rerender-preset
      code touched.
    - **Verified in Docker** (healthy): frontend build OK; `compose config/build/up`
      OK; `/api/health` ok; `/api/options` still lists **`qwen3.7-plus`** (C4c
      intact) + all three generator presets. Served bundle confirms **C3/C4b not
      regressed** — axes (Exhaustive/Exam-level), section toggles (Cram sheet/Worked
      examples), Save draft, preset cards ("Best for"), and the soft compat warning
      ("tuned for") all present. Release smoke **28/28** (flaky outline-ordering
      check passed).
    - **NOT automated — needs manual click-through:** Home layout/spacing after the
      button removal, the single Customize button opening the modal, Compare Styles
      functioning from the Styles tab, and overall visual polish.
    - **Stack merge preview (non-destructive, `git merge-tree --write-tree`
      chrome-renderer-v1 HEAD):** the stacked chain is **NOT cleanly mergeable** into
      `chrome-renderer-v1` yet — **5 pre-existing conflicts**: `Dockerfile`,
      `api/server.py`, `pipeline/extract.py`, `pipeline/llm_client.py`,
      `requirements.txt`. These are **stack-vs-target divergence, not introduced by
      C5** (C5 only touches `HomeShortcuts.jsx`, which is not in the conflict set).
      No merge was performed, no branch history rewritten, `chrome-renderer-v1`
      untouched. **Recommendation:** the conflicts need a deliberate review/resolve
      pass before merging the stack into `chrome-renderer-v1` — likely the Chrome
      renderer branch and the feature stack both edited the backend/runtime files.
      Group-C feature work itself is sound; this is an integration step, not a C5 bug.

## NEXT (in order)

3. **Library bulk actions — remaining follow-ups (deferred, not this slice).**
   - bulk **archive** — only after an archive state is designed + `DECISIONS.md`
     entry (not started; needs new metadata/state)
   - bulk **tag** — only if/after a tag model exists (not started; needs design)
   - bulk **export** — separate follow-up. NOTE: a working ZIP-bundle export
     already exists (`POST /api/exports/bundle`, used by the Exports center), so
     a small **B4** slice could expose a "Export selected" action in the Library
     bulk bar that reuses it. Kept out of B3 to avoid mixing slices.
4. **Output modules + preset naming/icons.** Output module options plus
   naming/iconography for presets.
5. **Local Model Manager — DESIGN-FIRST.** Backend spawns/kills a host
   `llama-server`. This **crosses the container boundary** (non-root uid 10001
   container managing a host process) — design and get sign-off before coding.
6. **In-app provider settings — DESIGN-FIRST.** Frontend writes provider config
   to **server-side secrets**. Keys must stay server-side only; the frontend
   must never receive raw keys. Design the secret-write path before coding.

## OPEN ITEMS

- **Shortcut options → Builder wiring — DONE (`7af9cbd`, Slice C3).** The Builder
  now exposes `include_sections` + the C2 axes, loads them from a selected
  shortcut into Builder state, and sends them to `/api/jobs/llm` (both the JSON
  and multipart/attachment transports). The backend bridge (`cc75292`) feeds the
  load path; legacy `modules` still translate to canonical `include_sections` on
  read/export. No longer open.
- **Generator preset cards + compatibility warning (C4b) — DONE (`b3d7785`).** The
  Builder Style tab now renders generator presets as cards (provider SVG icon / text
  badge, model chip, purpose, description, recommended use, selected state) consuming
  the C4a `/api/options.generator_presets` metadata, plus a soft, advisory
  `model_hint`-vs-selected-model compatibility warning that never blocks Generate.
  See `presetMeta.js` + `DECISIONS.md`. **Still open:** richer **shortcut** cards on
  Home and the shortcut **inspector/repair** loop (the store's `valid`/`reason`
  "references unavailable …" surfacing) are not built yet.
- **Home duplicate "Customize" button — DONE (`7f78542`, Slice C5).** The lower
  duplicate "Customize" button in the Pinned-shortcuts section head was removed;
  the single page-head "Customize Shortcuts" entry is kept and opens the shortcut
  customization modal (not Styles). Smart Tools confirmed already absent from Home;
  Compare Styles confirmed already living in Styles. No longer open.
- **Shortcut inspector / repair loop** — a later UX for inspecting an invalid
  shortcut and repairing its broken references (provider/preset/style) is not
  started.
- **Rerender drops `generator_preset`** — the retry/rerender path
  (`retry_failed_job` in `api/server.py`) rebuilds from the manifest and now
  reproduces `include_sections` + the C2 axes, but it still does **not** pass
  `generator_preset`, so a preset-generated job re-renders through the **default**
  prompt path (losing the preset system prompt + sampling params). Fix in a
  separate focused slice (do not bundle with C2).
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
  Current caps are env-configurable with static defaults.
- **Real cancel button** — deferred backend slice. The Builder shows progress
  but there is no true server-side cancel yet.
