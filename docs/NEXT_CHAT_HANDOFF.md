# NEXT_CHAT_HANDOFF.md — Start here

> One-page handoff so a fresh chat (Claude / ChatGPT / Codex) can continue safely
> from the repo alone. The repo is the source of truth. For the full per-slice log
> see `CURRENT_TASK.md`; for the "why" behind choices see `DECISIONS.md`; for the
> stable overview see `PROJECT_CONTEXT.md`; canonical brief is `../CLAUDE.md`.

## Current position
- **Branch (trunk / PR target):** `chrome-renderer-v1`
- **Latest commit:** `60c3e78` — "Enable PDF page selection UI". The **large-PDF
  core workflow** landed as five slices on top of cooperative cancel (`901d44b`):
  `841d3f9` (preflight endpoint), `9eefe25` (Builder preflight warnings),
  `d00380b` (page-selection plumbing), `db4de9d` (extraction honors selected
  pages), `60c3e78` (page-selection UI). Older `901d44b` / `1d51b36` / `65b9b8f`
  mentions below are historical.
- **Remote:** `origin/chrome-renderer-v1` == `60c3e78` (pushed; local == origin)

## What just landed
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
**Branch from `chrome-renderer-v1` @ `60c3e78` (or later) — never from an old stacked
branch.** One small slice per branch; verify (build + compile + docker + smoke) and
commit before moving on. Surgical edits, not rewrites. The PDF/Chromium pipeline is
load-bearing — do not rewrite casually.

## Next recommended slice
**Pick ONE safe option:**
- **Real-world validation pass over several large PDFs.** The large-PDF core is now
  complete end-to-end; run it on a handful of real big/scanned decks and confirm
  preflight verdicts, first-N + manual range selection, original `## Page N` anchors,
  OCR only on selected pages, and the rendered PDF. Validation/manual click-through
  only — no code unless a concrete bug surfaces.
- **In-app provider settings (DESIGN-FIRST).** Design the server-side secret-write
  path (keys never reach the frontend) before any code.
- **Shortcut inspector / repair loop (DESIGN/POLISH).** Surface the store's
  `valid`/`reason` "references unavailable …" state and a repair UX for broken
  provider/preset/style references. Design first.

(The previously-recommended **Math/PDF fidelity investigation** and **Large-PDF
preflight design** are **both DONE** — the preflight design shipped as Slices 1–5
(`841d3f9`→`60c3e78`) and the math/PDF fidelity Slices 1–3 shipped (#23–#25). The
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
- **Local Model Manager** — DESIGN-FIRST (crosses the container boundary; get sign-off).
- **In-app provider settings** — DESIGN-FIRST (server-side secret write path; keys never reach frontend).
- **Library archive / tag model** — DESIGN-FIRST (bulk archive needs an archive state +
  `DECISIONS.md` entry; bulk tag needs a tag model; neither started).
- **GHCR publish workflow / prebuilt image** — deferred distribution decision (parked on `hardening`).
- **Pinned dependency lockfile** — deferred; regenerate from this tree, don't lift from `hardening`.
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
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
