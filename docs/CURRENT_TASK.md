# CURRENT_TASK.md — Live handoff

> Update this every slice. For stable overview see `PROJECT_CONTEXT.md`; for the
> "why" behind choices see `DECISIONS.md`.

---

## Where we are

- **Branch:** `chrome-renderer-v1` (the live integrated trunk; PR target)
- **Trunk tip:** `901d44b` — Add cooperative job cancellation. Since the
  Group-C integration note below was written, several more commits landed on trunk:
  `687c8ca` (docs reconcile), `2716995` (preserve generator preset on rerender),
  `65b9b8f` (B4 "Export selected"), and `901d44b` (cooperative server-side cancel).
  The older `1d51b36` / `65b9b8f` references further down are historical — trunk is
  now `901d44b`.
- **`origin/chrome-renderer-v1`:** `901d44b` (local == origin; pushed)
- **Group C is COMPLETE and INTEGRATED** (C1 → C5, incl. C4a–d) onto `chrome-renderer-v1`.
- **For new sessions:** branch from `chrome-renderer-v1` @ `901d44b` (or later). Do **not**
  re-merge any of the old stacked feature branches — they are consumed/archival (see
  `DECISIONS.md` → "Consumed feature branches must not be re-merged"). The short one-page
  start-here is `docs/NEXT_CHAT_HANDOFF.md`.

## INTEGRATION — DONE: Group C is now on `chrome-renderer-v1` (pushed)

Group C was integrated onto the real target and `chrome-renderer-v1` was moved to the
integrated tip and pushed. The work originally landed on the throwaway `integ-group-c`
branch (off `origin/chrome-renderer-v1` @ `38cc822`); `chrome-renderer-v1` now points at
`1d51b36`. Sequence on the trunk:

- `6f888b2` — **Squash of the Group C stack** onto `38cc822`. Clean fast-forward, **zero
  conflicts** (the earlier "5 conflicts" were artifacts of two local-only commits on local
  `chrome-renderer-v1`: `863f5b7` Docker-hardening and `61c134c`, neither pushed nor in the stack).
- `5bde798` — **Re-applied `_preprocess_ocr_image`** (the one non-duplicate piece salvaged from
  local-only `61c134c`); its event-loop and provider-error changes were already superseded by the stack.
- `75ec24f` — **Prompt fixes** for two manual-test findings: MCQ answer explanations were wrapped in
  `$...$` (KaTeX stripped the spaces → `Biasshiftsthebaseline`); `slide_page_references` was too weak.
  Strengthened `mcqs_with_answers` (prose, never `$...$`) and `slide_page_references` (carry `## Page N`
  anchors through as compact `(p. N)` refs). Prompt-only; verified on a synthetic multi-page source.
- `72dab90` + `773209a` — **Mixed scanned/text PDF OCR fallback fixed** (+ its docs). Real issue:
  `_extract_pdf` decided text-vs-OCR for the WHOLE document, so one page of embedded text (a title
  slide) suppressed OCR for the rest — the 118-page `04_Neural_Networks...Backpropagation` extracted
  only ~97 chars / `## Page 1`. New behavior: **page-level** fallback — each page uses meaningful
  embedded text (≥40 chars OR ≥5 word-like tokens) else is OCR'd individually (reusing
  `_preprocess_ocr_image`); `## Page N` anchors preserved; mode now `pdf_text` / `pdf_ocr` /
  `pdf_mixed`. Verified on the real artifact: **~97 → 18,799 chars, 1 → 118 `## Page` headings, mode
  `pdf_mixed`**. Regression test `test_scripts/test_mixed_pdf_ocr.py` (synthetic page-1-text +
  pages-2/3-image PDF; skips cleanly without PyMuPDF/tesseract, full pass in Docker). Release smoke
  28/28 (the known outline-ordering check flaked once, passed on rerun).
- `1d51b36` — **Compose resource limits + `no-new-privileges` hardening** salvaged from local-only
  `863f5b7` (`mem_limit: 2g`, `pids_limit: 256`, `cpus: 2.0`, `security_opt: no-new-privileges:true`).
  Additive to `docker-compose.yml` only; `docker compose config` validated. `863f5b7`'s non-root/gosu
  hardening was already integrated at `6f888b2`; its **GHCR publish workflow / prebuilt image** and
  **pinned dependency lockfile** remain **deferred** decisions (see `DECISIONS.md`).

### Local-only commits `61c134c` and `863f5b7` — parked on `hardening`
Both were investigated. Useful pieces were salvaged onto the trunk (OCR preprocessing from
`61c134c` → `5bde798`; compose resource limits from `863f5b7` → `1d51b36`). The remaining
pieces (GHCR publish/prebuilt image, pinned deps) are deferred. The commits themselves stay
parked on the `hardening` branch — not merged, not deleted.

- **NOT automated — needs manual click-through:** generate a guide from a real scanned PDF through the
  Builder and confirm page references appear and MCQ answer spacing is correct in the rendered PDF.
- **Deferred:** large-PDF upload UX / preflight / page-range selection.

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

20. **Slice C4d — generator preset card simplification + compatibility polish
    (FRONTEND ONLY)** — `0015e50` (branch `preset-card-polish`). A UI polish/
    correction pass on the C4b preset cards — not a redesign. Still consumes the
    C4a `/api/options.generator_presets` metadata (no hardcoded copy); **no backend,
    registry, prompt-assembly, or shortcut-store change**.
    - **Cards simplified:** removed the dense `description` paragraph and the entire
      **"Best for:" (`recommended_use`) block**. Each card now shows: a large
      provider icon + **bold model-name headline**, the **preset name** directly
      under it, and `purpose` as the single one-line subtitle. Shorter, scan-first.
    - **Identity made prominent:** `ProviderBadge` gained a `size="lg"` variant
      (icon chip `h-12 w-12`, was `h-6 w-6`) paired with the bold model name, so the
      "Gemma 4 → Claude-Exam / DeepSeek V4 Pro → Claude-Review / Qwen 3.7 Max/Plus →
      Claude-Cram" pairing is glanceable. Text-badge fallback kept + enlarged to
      match; missing/broken icon still never blocks the card (`onError`).
    - **`presetModelLabel(preset)`** (new, `presetMeta.js`): returns the backend
      `model` verbatim, except the Qwen 3.7 preset renders **"Qwen 3.7 Max / Plus"**
      (one preset covers both models).
    - **Qwen 3.7 Max/Plus compatibility:** added an explicit, conservative
      compatibility family `["qwen37max","qwen37plus"]` (normalised tokens) in
      `presetCompat`. When the preset's `model`/`model_hint` and the selected model
      are both in the family, the advisory warning is **suppressed**. **Not broadened**
      to other Qwen models (e.g. `qwen3.6-plus` still warns against the 3.7 preset).
      See `DECISIONS.md`.
    - **Advisory stays advisory:** the warning is display-only; Generate is still
      `disabled={running}` only, no auto-switch, the generate payload still sends the
      user's selected model + preset independently. Selection / save-as-shortcut /
      load-shortcut / C3 sections / C2 depth-difficulty / action bar / model badge /
      progress button / dirty-state all unchanged (card render is the only edit).
    - **Verified in Docker** (healthy): frontend build OK; `compose config/build/up`
      OK; `/api/health` ok; `/api/options` unchanged. An esbuild harness drove the
      **real** `presetCompat`/`presetModelLabel` through **9/9** cases — Qwen Max →
      no warn, Qwen Plus → no warn (the fix), `qwen3.6-plus` → warn (conservative),
      Qwen+DeepSeek → warn, DeepSeek/Gemma matches → no warn, empty selection → no
      warn; labels: qwen→"Qwen 3.7 Max / Plus", deepseek→"DeepSeek V4 Pro",
      gemma→"Gemma 4". Served bundle: **"Best for" gone (0 occurrences)**, "Qwen 3.7
      Max / Plus" present, compat "tuned for" warning present, C3/C4b markers
      (Exhaustive/Exam-level/Cram sheet/Worked examples/Save draft/Generator preset)
      intact. Release smoke **28/28** (flaky outline check passed).
    - **NOT automated — needs operator judgment:** whether the new icon size feels
      right, whether the cards are visually balanced, whether the reduced text feels
      appropriate, and whether the one-line `purpose` subtitles read well.

21. **Slice B4 — "Export selected" in the Library bulk bar (FRONTEND ONLY)** —
    `65b9b8f` (branch `library-export-selected`, now on trunk). The Library multi-select bulk toolbar
    (`BulkBar`) gained an **"Export selected"** action between *Move to Unfiled*
    and *Delete*. It reuses the existing `downloadExportBundle` client helper →
    `POST /api/exports/bundle` (the **same** endpoint/contract the Exports center
    uses); **no new export primitive and no backend change**. It sends the
    currently selected **active** Library job ids with `artifacts: ["pdf"]` (the
    `BundleRequest` default); the backend silently skips any selected guide
    lacking a PDF and only 404s if NONE are available. The helper streams the ZIP
    straight into a browser download (same pattern as Exports), so the result is
    surfaced the existing way. New `exporting` state disables the button while a
    bundle is building and when nothing is selected; the button shows a spinner +
    "Exporting…". Success/failure are reported through the existing **toast**
    convention (success names the downloaded filename); **selection is preserved
    on both success and failure** (never cleared on a failed export). Existing
    Move / Move-to-Unfiled / Delete (and Trash Restore/Purge) behavior is
    untouched. Trash exports were **not** added (out of scope). Verified in
    Docker: frontend build OK; `python -m compileall api pipeline` OK; `compose
    config/build/up` OK; `/api/health` ok; `/api/options` unchanged; release smoke
    **28/28**. Focused call-path check (no frontend test runner exists in-repo):
    posting the exact button payload (`{job_ids: <2 active ids>, artifacts:
    ["pdf"]}`) returns a `200 application/zip` with `Content-Disposition:
    attachment`, both guides' `final.pdf`, and `manifest.json`.

22. **Slice — cooperative server-side cancel (BACKEND + FRONTEND)** — `901d44b`
    (branch `server-side-cancel`, now on trunk). Adds a true server-side cancel for in-flight
    generations, completing the progress/cancel/retry triad (progress + retry
    already existed). **Design-first**, cooperative-only — **no process killing,
    no PDF/Chromium-pipeline rewrite.**
    - **Cancel state is a sidecar marker file** `jobs/<id>/cancel.requested`
      (`Job.request_cancel`/`cancel_requested`/`clear_cancel_request`/
      `raise_if_cancelled` in `pipeline/job_manager.py`), deliberately **not** a
      `job.json` field: the running job thread continuously read-modify-writes
      the manifest via `set_stage`/`update`, so a concurrent manifest write from
      the cancel request could be lost. The marker is write-once by the canceller,
      existence-checked by the pipeline → no shared-mutable-file race. Mirrors the
      existing trash-marker pattern.
    - **New terminal status `cancelled`** (distinct from `failed`; `error: null`).
      A new `JobCancelled` signal is raised at safe stage boundaries and caught at
      every pipeline entry point (`run_llm_job`, `run_pasted_text_job`,
      `run_markdown_job`) → set `cancelled`, clear the marker, return the job
      (never classified as a failure).
    - **Checkpoints (`raise_if_cancelled`) only at existing stage boundaries:**
      before extraction, **before the LLM call** (best early exit), **after the LLM
      returns / before render** (skip Chromium), and at the top of
      `run_raw_markdown_pipeline` + before `render_pdf`. **Never** mid-LLM-call,
      mid-Chromium-render, or mid-`save_clean_md`. Honest limitation: cancel = "stop
      at the next safe checkpoint," not instant abort; a cancel during the
      uninterruptible LLM/render wait takes effect when that call returns.
    - **Endpoint `POST /api/jobs/{job_id}/cancel`** (`api/server.py`): writes the
      marker for a running job (`cancelled: true`); **already-terminal jobs are a
      safe no-op** (`cancelled: false`, status echoed, **no marker, artifacts
      untouched**); unknown id → 404. It does **not** set status itself (the running
      thread owns the manifest).
    - **Partial artifacts preserved** — nothing is deleted on cancel; input/source
      stays. **Retry-from-cancelled is intentionally NOT wired** (`retry_failed_job`
      stays gated to `failed`); the Builder keeps its inputs/selections on cancel so
      the user simply re-generates. Documented, deferred.
    - **Frontend** (`BuilderWorkspace.jsx` + `api/client.js`): `cancelJob` client
      helper; the action bar shows a **Cancel** button only while running, enabled
      once the existing job-discovery poller learns the in-flight id (the create-job
      POST is blocking); `cancelled` added to `TERMINAL_STATUSES` so polling stops;
      a cancelled result shows a "Generation cancelled" state and **does not** clear
      the draft/inputs or present a guide.
    - **Verified:** host — `compileall` OK, frontend build OK, focused test
      `test_scripts/test_cancel_job.py` 14/14 (pipeline level). Docker (healthy,
      uid 10001) — same test **22/22** incl. the endpoint via TestClient
      (running→marker+true / done→no-op+no-marker / unknown→404); live curl proof on
      a real `done` paste job (no-op, no marker) + unknown→404; release smoke
      **28/28** (LLM/attachment/outline flows ran). **NOT automated — needs manual
      click-through:** clicking Cancel mid-generation in the live Builder and seeing
      the cancelled state + preserved inputs.

23. **Math/PDF fidelity Slice 1 — page-break guard for display math (CSS-ONLY)** —
    branch `math-display-breaks`. Added `break-inside: avoid;` +
    `page-break-inside: avoid;` to `.guide .katex-display` in **both** the base
    rule and the `@media print` block of `themes/claude_clean.css`, putting display
    math in the same break-protected family as `table`/`pre`/`blockquote`/`img`.
    **Strictly CSS-only** — no `pdf_renderer.py`, Chromium flags, KaTeX bridge /
    HTML renderer, sanitizer, prompts, `@page` geometry, or dependency change.
    Diff is 5 added lines in one file.
    - **New fixture `test_scripts/math_layout_fixture.md`** (inline + long-inline,
      short/long display, aligned block, arrows, display-in-list, display-in-table,
      and ~1 page of filler before a boundary equation). No external API calls.
    - **Honest verification (real Chromium PDF render, old vs. new CSS):** KaTeX
      display math in this pipeline **already renders atomically and never splits
      mid-equation** — a fitting block (incl. a 14-row `aligned`) jumps **whole** to
      the next page in both old and new CSS, at every filler offset tested. KaTeX's
      vlist/positioned-span output exposes no in-equation break points, and
      `.katex-display` already carries `overflow` (scroll container = monolithic).
      The only observed "split" is an equation **taller than the page** (45-row
      probe) — a *forced overflow* `break-inside` cannot prevent. So Slice 1 is
      **defensive/consistency hardening**, not a fix for a reproduced visible split;
      it becomes load-bearing if a later slice removes the overflow clipping.
    - **NOT fixed (deferred, not claimed):** long-equation overflow/clipping
      (cause B, Slice 2), math font-size rationalization (cause C, Slice 3), and
      prompt guidance for multi-line form (cause D, Slice 4). See
      `MATH_PDF_FIDELITY_INVESTIGATION.md` §10.
    - **Verified:** `npm --prefix frontend run build` OK; `python -m compileall api
      pipeline` OK; `docker compose config` OK; `docker compose build` OK; container
      recreated on the new image and **healthy** (`/api/health` `{"ok":true}`, new
      CSS confirmed baked in — 2× `page-break-inside`); `/api/options` OK, no secret
      leak; release smoke **28/28**; plus the before/after PDF render comparison
      above (HTML render shows 22 `.katex-display` blocks, the rule present in base
      + print, no raw LaTeX leaked into `<code>`).

24. **Math/PDF fidelity Slice 2 — long display math overflow/clipping (CSS-ONLY)** —
    branch `math-display-overflow`. Changed the **print** rule for
    `.guide .katex-display` from `overflow: hidden` to `overflow: visible` in
    `themes/claude_clean.css` (the only functional change; `0.9em` print font-size
    left untouched — font rationalization is Slice 3). **Strictly CSS-only** — no
    `pdf_renderer.py`, Chromium flags, KaTeX bridge / HTML renderer, sanitizer,
    prompts, `@page` geometry, or dependency change. Diff is one rule + an
    explanatory comment.
    - **Root cause (confirmed by real PDF renders):** a PDF page can't scroll, so
      the screen's `overflow-x: auto` becoming `overflow: hidden` in print **silently
      discarded** any display-equation content past the ~176 mm content box. KaTeX
      never auto-wraps display math (`white-space: nowrap`), so long single-line
      equations exceeded the box and lost their right tail. With `overflow: visible`
      a too-wide equation is **left-anchored** (readable start always kept) and
      extends into the empty side margin (`@page` has margins only — no
      header/footer/page-number to collide with). Only equations wider than the
      **whole A4 page** still clip, now at the physical edge, not the content box.
    - **Before/after (real markdown→HTML→PDF Chromium path, end-marker probes):**
      `overflow: hidden` clipped the right end-marker at **every** equation length
      tested; `overflow: visible` **keeps** moderate lengths (recovered into the
      margin) and only page-width-exceeding equations still clip. Real
      `test_scripts/math_layout_fixture.md` renders cleanly — long single-line
      equation no longer truncated within the content box; aligned block, arrows,
      display-in-list, and the **sanitized** table case verified **identical**
      before/after (no table/list regression).
    - **Improvement, not a full fix (not overclaimed):** arbitrarily long single-line
      equations cannot be made to fully fit CSS-only (KaTeX won't reflow; aggressive
      font shrink doesn't fit them and re-introduces cramping). Genuine semantic
      multi-line wrapping is **prompt-side (cause D / Slice 4)**; font-size
      rationalization is **cause C / Slice 3**. Both remain deferred. See
      `MATH_PDF_FIDELITY_INVESTIGATION.md` §11.
    - **Verified:** `npm --prefix frontend run build` OK; `python -m compileall api
      pipeline` OK; `docker compose config` OK; `docker compose build` OK; container
      recreated on the new image and **healthy** (`/api/health` `{"ok":true}`, new
      CSS confirmed baked in — print `.katex-display` now `overflow: visible`);
      `/api/options` OK; release smoke **28/28**; plus the before/after PDF render
      comparison above.

25. **Math/PDF fidelity Slice 3 — long-formula prompt guidance (PROMPT-ONLY)** —
    branch `math-formula-guidance`, commit `Guide long formulas into aligned math`.
    This is the **cause D / "Slice 4"** prompt-side work in
    `MATH_PDF_FIDELITY_INVESTIGATION.md` §7 (the doc numbers prompt guidance as
    Slice 4; this task tracked it as Slice 3 — same work). Extended
    `MARKDOWN_MATH_SYSTEM` in `pipeline/orchestrator.py` (the math/table contract
    appended **last** in both the default and generator-preset system messages)
    with a concise rule: avoid very long single-line display equations (they
    overflow PDF page width); break long equations/derivations across multiple
    lines inside `\begin{aligned} ... \end{aligned}`, one step per line, each line
    reasonably short; write prose explanations outside math delimiters — never
    wrap an explanatory sentence in `$...$`/`$$...$$`.
    - **Prompt-only.** No `pdf_renderer.py`, Chromium flags, KaTeX bridge / HTML
      renderer, sanitizer, CSS, `@page` geometry, or dependency change. The new
      text generalizes the existing "prose is not math" rule already in the
      `mcqs_with_answers` section fragment — it does not duplicate or contradict
      it, and does not weaken the existing aligned/table/matrix rules.
    - **Ordering preserved:** a preset's own system prompt stays first;
      `MARKDOWN_MATH_SYSTEM` stays the **final** appended block in both paths.
    - **Improvement, not a fix (not overclaimed):** this shapes model *output* so
      fewer equations are wide enough to hit the §11 clipping limit; it cannot
      reflow an over-wide equation the model still emits. That residual stays the
      deferred CSS/renderer limit. Font-size rationalization (**cause C**) remains
      untouched/deferred.
    - **Verified:** `python -m compileall api pipeline` OK; new
      `test_scripts/test_long_formula_guidance.py` **10/10** (default + preset +
      formula-heavy paths all carry the guidance, math block still last);
      `test_math_regressions.py` OK; `npm --prefix frontend run build` OK;
      `docker compose config`/`build` OK; container **healthy**
      (`/api/health` `{"ok":true}`, `/api/options` OK); release smoke **28/28**.

26. **Page-reference format standardization (PROMPT-ONLY)** — branch
    `page-reference-format`, commit `Standardize page reference prompts`. Manual
    PDF validation showed slide/page citations were inconsistent (`p.20`,
    `p. 20`, `pp. 20-21`, `p.96 − 100`, bare fragments, spaced-dash ranges).
    Tightened the **`slide_page_references`** include-section fragment in
    `pipeline/orchestrator.py` so the model always cites pages in one
    parenthesized format: `(page N)` for a single page, `(pages N-M)` for a
    continuous range, `(pages N, M, P-Q)` for multiple pages/ranges; a normal
    hyphen `-` for ranges (never an en dash or spaced dash). The old loose
    `(p. N)` recommendation was removed and `p.`, `pp.`, `pN`, and bare
    out-of-paren fragments are now explicitly banned.
    - **Prompt-only.** No renderer, sanitizer, CSS, dependency, or pipeline
      change. The fragment is injected via `build_include_sections_block`
      **before** `MARKDOWN_MATH_SYSTEM`; math guidance is untouched and stays the
      final appended block, so there is no conflict.
    - **Verified:** new `test_scripts/test_page_reference_format.py` **21/21**
      (fragment carries the exact format examples + bans; assembled default and
      preset prompts include them; ordering preset<axes<include<math preserved;
      math contract intact alongside page refs); `test_long_formula_guidance.py`
      **10/10** regression; `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build` OK;
      container **healthy** (`/api/health` `{"ok":true}`, `/api/options` OK);
      release smoke pass.

27. **Large-PDF preflight Slice 1 — backend endpoint only** — branch
    `large-pdf-preflight-api`, commit `Add PDF preflight endpoint`. Implements the
    first slice of `docs/LARGE_PDF_PREFLIGHT_DESIGN.md` §10: a **read-only**
    `POST /api/preflight/pdf` that inspects ONE uploaded PDF *before* job creation
    and returns a lightweight verdict — **no UI, no job, no extractor change, no
    OCR, no limit change.**
    - **New helper `pipeline.extract.preflight_pdf`** — opens with `fitz`, reads
      `page_count`, probes a bounded, evenly spaced page sample
      (`_preflight_sample_indices`, default 20) with `get_text("text")` gated by the
      **existing** `_is_meaningful_page_text`, and reuses the **existing**
      `_ocr_available()`. **`_extract_pdf` is untouched** (no behavior change).
      Returns `PdfPreflightResult`; raises new `PdfEncryptedError` (encrypted) /
      existing `ExtractionError` (corrupt).
    - **Endpoint** (`api/server.py`, registered before the static mount): multipart,
      single `file`, **PDF-only** (non-PDF → `400`). Streams to a temp file reusing
      the **existing** `MAX_LLM_ATTACHMENT_BYTES` (15 MB) guard (over-limit → `400`,
      ceiling unchanged); temp file removed in `finally`; inspection runs in a
      threadpool. `_build_pdf_preflight_report` assembles `verdict` (`ok`/`warn`/
      `blocked`) + `warnings[]` + `allowed_actions[]` + echoed `limits{}`.
      **Encrypted/corrupt → `blocked` (with `ok: true`); any other failure (incl.
      PyMuPDF missing on host) → degrades to `ok`** so preflight never blocks a
      processable PDF. `allowed_actions` ∈ {`continue`, `process_first_n`,
      `choose_page_range`, `remove_file`}; **`split_automatically` never emitted**
      (deferred). No secrets/host temp paths in the response.
    - **Env knobs** (`os.getenv`, read once at import; the §4 names):
      `PREFLIGHT_SAMPLE_PAGES`/`PREFLIGHT_WARN_PAGES`/`PREFLIGHT_WARN_SIZE_MB`/
      `PREFLIGHT_OCR_PAGE_LIMIT`/`PREFLIGHT_DEFAULT_FIRST_N`/
      `PREFLIGHT_IMAGE_HEAVY_RATIO`/`PREFLIGHT_TEXT_RATIO`. `MAX_UPLOAD_MB` reported,
      not changed.
    - **Verified in Docker** (healthy): `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build`/`up` OK;
      `/api/health` `{"ok":true}`; `/api/options` unchanged. New
      `test_scripts/test_pdf_preflight.py` **24/24** (helper + endpoint via
      TestClient: text/image-heavy/mixed/encrypted/corrupt/non-PDF-400/oversize-400/
      warn-by-pages; skips cleanly without PyMuPDF). Release smoke **28/28**. Live
      curl: text PDF → `ok`/`full`/`[continue]`; image-heavy → `warn`/`image_heavy`/
      `first_n` + first-N/range/remove actions; non-PDF → `400`; corrupt `.pdf` →
      `blocked`/`[remove_file]`.
    - **Deferred (unchanged):** frontend banner/actions (Slice 2), page-range flow
      into `_extract_pdf` (Slice 3), automatic split/chunk + hybrid OCR dedup
      (Slice 4+). See the design doc's Slice-1 implementation note.

28. **Large-PDF preflight Slice 2 — Builder warning UI** — branch
    `large-pdf-preflight-ui`, commit `Show PDF preflight warnings in Builder`.
    Wires the Slice-1 endpoint into the Builder so a large/scanned/problem PDF is
    surfaced **before** generation. **Frontend + API-client only — no backend,
    extractor, OCR, job, or limit change.**
    - **API client** (`frontend/src/api/client.js`): new `preflightPdf(file)` —
      multipart `POST /api/preflight/pdf`. A non-PDF/oversize/network failure
      rejects via `requestJson`; callers treat any failure as a **soft warning**
      and never block generation.
    - **`AttachmentsPicker`** (`BuilderWorkspace.jsx`): on adding a `.pdf`, calls
      preflight per file and stores `{status, report?}` in a new parent state map
      `attachmentPreflights`, keyed by a stable `attachmentKey` (name+size+
      lastModified). Lives **beside the selected files only** — never persisted to
      a job. Removing a file prunes its entry; "Continue anyway" marks it
      acknowledged.
    - **`PreflightCard`**: quiet for ordinary PDFs (verdict `ok`, no warnings);
      `checking` → spinner; `error` → soft "Could not inspect this PDF; it will be
      processed normally." For `warn` (amber) / `blocked` (red) it shows file size,
      page count, scanned flag, OCR-page estimate, the backend `warnings[]`, and a
      recommended action. Actions: **Continue anyway** (warn only) + **Remove
      file**; **Process first N pages** / **Choose page range** render **disabled
      with a "coming later" note** (Slice 3 builds the real flow).
    - **Generate gate**: `validateInputs` blocks generation when any attached PDF's
      verdict is `blocked` (corrupt/encrypted → must remove/replace). `warn`/`ok`
      never block. A preflight failure never blocks. Builder state/selections are
      preserved on warn/fail.
    - **Verified in Docker** (healthy): `npm --prefix frontend run build` OK;
      `python -m compileall api pipeline` OK; `docker compose config`/`build`/`up`
      OK; `/api/health` `{"ok":true}`; `/api/options` unchanged. Backend contract
      the UI consumes re-confirmed `test_scripts/test_pdf_preflight.py` **24/24**;
      release smoke **28/28**. Live curl: non-PDF → `400`; text PDF →
      `ok`/`text`/`[continue]`. No JS test runner exists in the repo (only an
      asset-verify script); adding vitest/jsdom would be out-of-scope dependency
      work, so the contract is covered by the existing backend test.
    - **Deferred (unchanged):** page-range flow into `_extract_pdf` (Slice 3),
      automatic split/chunk + hybrid OCR dedup (Slice 4+). The "first N" / "page
      range" buttons are intentionally inert affordances until Slice 3.

29. **Large-PDF Slice 3 — page-selection request plumbing** — branch
    `large-pdf-page-selection-plumbing`, commit `Plumb PDF page selections through
    jobs`. Makes PDF page selections **representable, validated, and persisted**
    without changing extraction. **Plumbing only — `_extract_pdf` untouched, no
    page filtering, no active page-range UI.**
    - **Field/shape:** new optional `page_selections` on the LLM request —
      `{filename: [[start, end], ...]}`, **1-based inclusive** (e.g.
      `{"deck.pdf": [[1, 20], [35, 42]]}`). Absent/null/empty ⇒ `{}` ⇒ all pages ⇒
      current behaviour. Chose the flat list-of-ranges form (task brief) over the
      design §5.1 `{mode, first_n, ranges}` object — "first N" is just `[[1, N]]`.
    - **Validation** (`_normalize_page_selections`, raises **400** on bad shapes):
      positive-int `[start, end]` pairs with `start <= end` (`bool` rejected);
      ranges sorted + overlapping/adjacent merged to a canonical spec; bounded by
      `MAX_PAGE_SELECTION_FILES`=20 / `MAX_PAGE_RANGES_PER_FILE`=50. Does **not**
      need the real page count (no clamp yet).
    - **Both paths wired** (DECISIONS.md rule): JSON body via `LLMJobRequest`
      (loose `dict[str, Any]`, normalized at handler) **and** multipart via a JSON
      string in `_parse_llm_request`, mirroring `include_sections`/`outline`.
    - **Persistence:** stored in `job.json` by `run_llm_job` (`page_selections`
      key, default `{}`), echoed by `job_response` (`_safe_page_selections`), and
      **preserved across retry** (re-normalized + re-stored); rerender never
      touches it. **Not** forwarded to `_attach_sources`/extraction.
    - **Frontend:** `buildLlmPayload` adds `page_selections` only when the Builder
      carries a selection; reserved internal `pageSelections` state (default `{}`,
      no control sets it) keeps default requests byte-equivalent; `client.js` sends
      it as a JSON string on the multipart path. No page-range UI yet.
    - **Verified:** `compileall api pipeline` OK; `npm … build` OK; `docker compose
      config`/`build`/`up` OK; `/api/health` `{"ok":true}`; `/api/options`
      unchanged. New `test_scripts/test_page_selections.py` **24/24** (offline:
      LLM + renderer stubbed) — normalizer validation/merge, JSON + multipart
      persistence, default-omits, invalid→400, retry-preserves. Release smoke
      **28/28** (flaky outline-ordering check green on re-run).
    - **Deferred (unchanged):** `pages=` filter into `_extract_pdf` + the picker
      that populates `pageSelections` + enabling the Slice-2 actions (next slice);
      automatic split/chunk + hybrid OCR dedup (Slice 4+).

30. **Large-PDF Slice 4 — PDF extraction honors selected pages** — branch
    `large-pdf-page-selection-extraction`, commit `Filter PDF extraction by
    selected pages`. Makes the persisted Slice-3 `page_selections` finally **change
    what is extracted**: matching PDF attachments are restricted to the selected
    ORIGINAL pages. **Backend/extraction only — no page-range UI, no split/chunk,
    no hybrid OCR dedup, no limit change; `_extract_pdf` extended surgically (not
    rewritten); non-PDF extraction untouched; default (no selection) byte-for-byte
    unchanged.**
    - **`extract_file(path, pages=None)` / `_extract_pdf(path, pages=None)`**
      (`pipeline/extract.py`): `pages` = optional iterable of **1-based ORIGINAL**
      page numbers, **PDF-only** (ignored for every other type). The filter is one
      `if selected is not None and index not in selected: continue` at the top of
      the existing per-page loop, **before** any `get_text`/OCR — so **OCR only ever
      runs on selected pages**. Per-page text-XOR-OCR fallback unchanged.
    - **Original anchors preserved:** the loop still enumerates from 1 and emits
      `## Page {index}` with the *original* number, so selecting pages 20-21 yields
      `## Page 20`/`## Page 21`, **never** renumbered `## Page 1`/`## Page 2`.
    - **Validated against real `document.page_count`:** requested pages are
      intersected with `[1, page_count]`; out-of-range pages are **dropped (not
      clamped)** with a warning naming them; if **no** selected page is in range →
      empty `ExtractionResult("", "pdf_text", [warning])` (no crash), and the caller
      reports "no text could be extracted" exactly as today.
    - **Mode over the subset:** `pdf_text`/`pdf_ocr`/`pdf_mixed` computed from the
      selected pages (text-only subset → `pdf_text`, image-only subset → `pdf_ocr`,
      etc.).
    - **Threading** (`pipeline/run_llm_job.py`): `run_llm_job` → `_attach_sources`
      passes `page_selections`; for **PDF attachments only** it looks the selection
      up by the attachment's **original filename** (`AttachmentSource.filename` =
      the `original_filename` in attachment metadata = the Slice-3/frontend key),
      flattens the normalized `[[start,end],...]` ranges (`_expand_page_ranges`),
      and calls `extract_file(path, pages=...)`. Exact `dict.get` match — no
      fuzzy/index guessing; a selection for an unmatched filename is unused; same
      original filename on two attachments both legitimately get that selection.
    - **Verified in Docker** (healthy): `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build`/`up` OK
      (no secret output pasted); `/api/health` `{"ok":true}`; `/api/options`
      unchanged. New `test_scripts/test_pdf_page_selection_extract.py` **39/39**
      (text pages 2-3 → original anchors, no page 1; no-selection == select-all;
      out-of-range safe warning; OCR-gated scanned-subset OCR-only; mixed-subset
      mode correctness; `_attach_sources` filename-keyed threading). Existing
      `test_mixed_pdf_ocr.py` and `test_page_selections.py` both still pass
      (24/24). Release smoke **28/28** (flaky outline check green on re-run). Live
      Docker generation with `page_selections={"sel.pdf": [[2, 3]]}` → the job's
      `input/source.txt` carries only `## Page 2`/`## Page 3` (not `## Page 1`) and
      the manifest persists the selection.
    - **Deferred (unchanged):** the active page-range **UI** picker that populates
      `pageSelections` + enabling the Slice-2 actions (Slice 5); automatic
      split/chunk + hybrid embedded-text + OCR dedup (still §9 deferred).

31. **Large-PDF Slice 5 — page-selection UI is live** — branch
    `large-pdf-page-selection-ui`, commit `Enable PDF page selection UI`. Turns the
    Slice-2 inert "Process first N pages" / "Choose page range" affordances into
    **working** Builder controls that populate `pageSelections`, which the Slice-3
    plumbing already sends and the Slice-4 extractor already honors. **Frontend/UI
    only — no backend, `_extract_pdf`, page-selection validation, upload-limit, or
    dependency change.**
    - **`PreflightCard` actions enabled** (`BuilderWorkspace.jsx`, `warn` PDFs;
      `blocked` still Remove-only). **Process first N** → `{ "<file.name>": [[1, N]] }`
      with `N = limits.default_first_n` (20) **capped by `page_count`** when known.
      **Choose page range** → inline editor parsing `1-20` / `1-20, 35-42` via new
      `parsePageRanges` to `[[1,20],[35,42]]` (**1-based inclusive**, validated:
      positive ints, `start <= end`, sorted; bad token → inline error, no apply;
      exceeding a known `page_count` applies with a soft note — backend/extractor
      drop the extras safely).
    - **Active-selection bar:** a calm green **"Using pages 1-20"** (`formatPageRanges`)
      replaces the amber warning once a selection is set, with **Edit range** +
      **Use all pages** (clears → all pages). The **"coming later"** note/disabled
      buttons are removed.
    - **Per-file, keyed by `file.name`** — the exact backend match key
      (`original_filename`); multiple PDFs each carry their own selection.
      **Removing a file clears its selection** unless a duplicate-named sibling
      remains.
    - **Default unchanged / opt-in:** no selection ⇒ `pageSelections` `{}` ⇒
      `buildLlmPayload` omits `page_selections` ⇒ "all pages" ⇒ byte-equivalent
      request. **Not** persisted to drafts/shortcuts (the attachments it refers to
      aren't either, so it would be orphaned); preflight report still not persisted
      to `job.json`.
    - **Verified** (Docker healthy): `npm … build` OK; `compileall api pipeline` OK;
      `compose config`/`build`/`up` OK (no secret output); `/api/health` `{"ok":true}`,
      `/api/options` unchanged. `buildLlmPayload` payload harness **5/5** (default &
      empty omit; first-N, multi-range, multi-PDF included verbatim); parse-rule
      check **12/12**; served bundle carries the new strings and **no** "coming
      later". `test_page_selections.py` **24/24**, `test_pdf_page_selection_extract.py`
      **39/39**, release smoke **28/28** (transient provider/host hiccups on
      overlapping runs cleared on a clean run after a container restart). Live Docker
      generation with `page_selections={"multi.pdf": [[2, 3]]}` → manifest persists
      the selection and `input/source.txt` carries only `## Page 2`/`## Page 3` (not
      pages 1/4).
    - **NOT automated — needs manual browser click-through:** the warn card's First-N
      button, the inline range editor (valid + invalid input), the "Using pages …"
      bar + Use-all-pages reset, per-file selection with two PDFs, and clearing on
      file removal. DOM strings + payload/extraction wiring are proven; pixel
      layout/hover is not.
    - **Deferred (unchanged):** automatic split/chunk processing + hybrid
      embedded-text + OCR dedup (§9).

## NEXT (in order)

> Slices 1–3 of the math/PDF fidelity work (`math-display-breaks` DONE #23,
> `math-display-overflow` DONE #24, `math-formula-guidance` DONE #25) added the
> display-math page-break guard, the long-equation overflow improvement, and the
> prompt-side long-formula guidance (cause D). The one remaining math/PDF slice is
> **font-size rationalization** (cause C, CSS-only). The rerender-preset fix
> (`2716995`), B4 "Export selected" (`65b9b8f`), and the cooperative server-side
> cancel (`901d44b`) are **DONE and on trunk**. See DONE #20→#24 and OPEN ITEMS.

1. **Recommended next — pick ONE, design/investigation only (do NOT start
   implementation in a docs slice):**
   - **Math / PDF fidelity investigation.** Diagnose how reliably math (KaTeX
     spans, formula sheets) and page references survive the Chromium PDF render
     across real multi-page sources. The PDF/Chromium pipeline is load-bearing —
     investigate and write findings first; do not rewrite casually.
   - **Large-PDF preflight design (DESIGN-FIRST).** Design the upload
     preflight / page-range selection / OCR-cost UX for big scanned PDFs
     (deliberately left out of the page-level OCR fallback). Design + sign-off
     before any code.
2. **Output modules + preset naming/icons.** Output module options plus
   naming/iconography for presets.
3. **Local Model Manager — DESIGN-FIRST.** Backend spawns/kills a host
   `llama-server`. This **crosses the container boundary** (non-root uid 10001
   container managing a host process) — design and get sign-off before coding.
4. **In-app provider settings — DESIGN-FIRST.** Frontend writes provider config
   to **server-side secrets**. Keys must stay server-side only; the frontend
   must never receive raw keys. Design the secret-write path before coding.
5. **Library archive / tag model — DESIGN-FIRST.** Bulk **archive** needs a new
   archive state designed + a `DECISIONS.md` entry first; bulk **tag** needs a
   tag model designed first. Neither is started. Bulk **export** is already DONE
   (B4). Do not begin either without an explicit slice + design sign-off.

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
- **Rerender drops `generator_preset` — FIXED** (`2716995`, branch
  `fix-rerender-generator-preset`, now on trunk).
  `retry_failed_job` (`api/server.py`, `path_mode == "generate"`) now reads
  `generator_preset` from the manifest and rebuilds through it: the preset is resolved,
  its tuned sampling params are applied to the provider config (mirroring the
  `/api/jobs/llm` preset path), and the id is passed to `generate_study_guide`. An
  absent/null preset keeps the default path; a since-removed preset id degrades
  gracefully to the default path instead of failing the retry. The user's saved
  provider/model still wins (`model_hint` stays advisory). Backend-only; no new request
  field. Regression test `test_scripts/test_retry_generator_preset.py` (7/7 in Docker:
  threading + sampling overrides, default path, stale-id degrade, and a real on-disk job
  whose manifest still records the preset after retry).
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
  Current caps are env-configurable with static defaults.
- **Real cancel button — DONE** (`901d44b`, branch `server-side-cancel`, now on
  trunk; DONE #22). Cooperative server-side cancel via a `jobs/<id>/cancel.requested`
  marker checked at safe stage boundaries; new `cancelled` terminal status;
  `POST /api/jobs/{id}/cancel`; Builder Cancel button. **Cooperative + checkpoint-based:**
  it does **not** kill processes or threads — it sets a marker that the pipeline checks
  at safe stage boundaries, so a cancel requested during an uninterruptible LLM call or
  Chromium render only takes effect at the **next safe checkpoint** (it is "stop at the
  next checkpoint," not an instant abort). **Partial artifacts and the user's uploads /
  Builder inputs / settings are preserved** — nothing is deleted on cancel; the Builder
  keeps its inputs so the user simply re-generates. No pipeline rewrite. **Still
  deferred:** retry-from-cancelled (kept gated to `failed`; re-generate from the Builder
  instead).
- **Docker GHCR publish workflow / prebuilt image** — deferred. `863f5b7` carried a
  `.github/workflows/publish.yml` (push image to GHCR on `v*` tags) and an
  `image: ghcr.io/...` line in compose. Needs a deliberate distribution decision before
  adopting (the app is local-only/single-operator today). Parked on `hardening`.
- **Pinned dependency lockfile** — deferred. `863f5b7` fully froze `requirements.txt`
  (transitive pins + new packages). Reproducibility is good, but a freeze should be
  regenerated from *this* tree, not lifted from the divergent `hardening` branch. Its
  own deliberate slice if/when wanted.
- **Branch retirement** — deferred housekeeping. The consumed feature/integration
  branches (and the short-lived `salvage-compose-limits`, `integ-group-c`) are kept,
  not deleted, per the operator's "do not delete branches" rule.
- **Group D** — not started. Do not begin without an explicit slice request.
