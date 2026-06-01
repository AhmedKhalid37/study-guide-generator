# CURRENT_TASK.md — Live handoff

> Update this every slice. For stable overview see `PROJECT_CONTEXT.md`; for the
> "why" behind choices see `DECISIONS.md`.

---

## Where we are

- **Branch:** `style-axes`
- **Last commit:** `24442bd` — Add generation depth and difficulty axes
- **Main branch (PR target):** `chrome-renderer-v1`

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

- **Shortcut modules/options persistence bridge** — the old shortcut `modules`
  keys (`shortcut_store.KNOWN_MODULE_KEYS` + `frontend/shortcutMeta.js`) are still
  **inert**: they round-trip through the Builder and `library/shortcuts.json` but
  do **not** reach generation. They must later be bridged to `include_sections`,
  and saved shortcuts should carry both `include_sections` and the C2 axes
  (`output_depth`/`difficulty`) into the generation request. Not done in C2 (the
  slice forbade touching shortcut whitelist/persistence).
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
