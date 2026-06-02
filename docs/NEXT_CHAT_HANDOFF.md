# NEXT_CHAT_HANDOFF.md — Start here

> One-page handoff so a fresh chat (Claude / ChatGPT / Codex) can continue safely
> from the repo alone. The repo is the source of truth. For the full per-slice log
> see `CURRENT_TASK.md`; for the "why" behind choices see `DECISIONS.md`; for the
> stable overview see `PROJECT_CONTEXT.md`; canonical brief is `../CLAUDE.md`.

## Current position
- **Branch (trunk / PR target):** `chrome-renderer-v1`
- **Latest commit:** `65b9b8f` — "Add Library export selected action" (B4). After the
  Group-C integration, three more commits landed: `687c8ca` (docs reconcile),
  `2716995` (preserve generator preset on rerender), `65b9b8f` (B4). Older `1d51b36`
  mentions below are historical.
- **Remote:** `origin/chrome-renderer-v1` == `65b9b8f` (pushed; local == origin)
- **In progress (unmerged):** branch `server-side-cancel` — cooperative server-side
  cancel (marker file + `cancelled` status + `POST /api/jobs/{id}/cancel` + Builder
  Cancel button; no process killing, no pipeline rewrite). See `CURRENT_TASK.md` #22.

## What just landed
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
**Branch from `chrome-renderer-v1` @ `1d51b36` (or later) — never from an old stacked
branch.** One small slice per branch; verify (build + compile + docker + smoke) and
commit before moving on. Surgical edits, not rewrites. The PDF/Chromium pipeline is
load-bearing — do not rewrite casually.

## Next recommended slice
**Fix rerender dropping `generator_preset` (backend-only).** `retry_failed_job`
(`api/server.py`) rebuilds a job from its manifest and reproduces `include_sections` +
the C2 axes, but does **not** pass `generator_preset` — so a preset-built job re-renders
through the **default** prompt path, losing the preset system prompt + tuned sampling
params. Well-scoped, isolated to `retry_failed_job`. Verify with Docker smoke + a
manifest check that the preset survives a rerender. Do not bundle with anything else.

(Then, if wanted: **B4 — "Export selected" in the Library bulk bar**, reusing the
existing `POST /api/exports/bundle` ZIP endpoint.)

## Open / deferred items
- **rerender drops `generator_preset`** — the recommended next slice (above).
- **B4 "Export selected"** — small; reuse the existing bundle endpoint.
- **GHCR publish workflow / prebuilt image** — deferred distribution decision (parked on `hardening`).
- **Pinned dependency lockfile** — deferred; regenerate from this tree, don't lift from `hardening`.
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
- **Real server-side cancel button** — DONE (branch `server-side-cancel`; cooperative,
  marker-based, `cancelled` status). Retry-from-cancelled still deferred (re-generate
  from the Builder instead).
- **Local Model Manager** — DESIGN-FIRST (crosses the container boundary; get sign-off).
- **In-app provider settings** — DESIGN-FIRST (server-side secret write path; keys never reach frontend).
- **Shortcut inspector / repair loop** — not started.
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
curl http://localhost:8000/api/options   # themes / styles / providers / models / generator_presets
python test_scripts/smoke_release.py     # end-to-end release smoke (~28 checks; outline-ordering check is known-flaky)
```
