# CURRENT_TASK.md — Live handoff

> Update this every slice. For stable overview see `PROJECT_CONTEXT.md`; for the
> "why" behind choices see `DECISIONS.md`.

---

## Where we are

- **Branch:** `library-bulk-backend`
- **Last commit:** `51fc7b9` — Add backend library bulk actions
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

## NEXT (in order)

3. **Library bulk actions — FRONTEND (deferred follow-ups).** The backend (above)
   is done; the UI is still to build:
   - Library multi-select UI + "select all jobs"
   - bulk action toolbar
   - undo toast UI (restore-after-delete)
   - bulk folder-picker UI
   - bulk **archive** — only after an archive state is designed (not started)
   - bulk **tag** — only if/after a tag model exists (not started)
   - bulk **export** — separate follow-up, only if supported by existing
     artifact/export behavior (not started)
4. **Output modules + preset naming/icons.** Output module options plus
   naming/iconography for presets.
5. **Local Model Manager — DESIGN-FIRST.** Backend spawns/kills a host
   `llama-server`. This **crosses the container boundary** (non-root uid 10001
   container managing a host process) — design and get sign-off before coding.
6. **In-app provider settings — DESIGN-FIRST.** Frontend writes provider config
   to **server-side secrets**. Keys must stay server-side only; the frontend
   must never receive raw keys. Design the secret-write path before coding.

## OPEN ITEMS

- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
  Current caps are env-configurable with static defaults.
- **Real cancel button** — deferred backend slice. The Builder shows progress
  but there is no true server-side cancel yet.
