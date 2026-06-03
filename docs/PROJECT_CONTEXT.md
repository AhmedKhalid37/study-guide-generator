# PROJECT_CONTEXT.md — Stable Overview

> Stable, slow-changing context for any new session (Claude, ChatGPT, Codex).
> **Start here:** `NEXT_CHAT_HANDOFF.md` (one-page current-state handoff). For the
> live per-slice log see `CURRENT_TASK.md`; for the "why" behind choices see
> `DECISIONS.md`. The canonical project brief is `../CLAUDE.md`.
>
> **Trunk:** `chrome-renderer-v1` is the integrated trunk. Branch new work from it
> (currently `60c3e78` or later) — never from the old consumed feature branches
> (see `DECISIONS.md` → "Consumed feature branches must not be re-merged").

---

## 1. What the app is

**Study Guide Generator** — turns course material (pasted text, uploaded
Markdown, or attachments) into clean, exam-focused study guides and renders them
to PDF, plus Markdown / HTML / DOCX artifacts. It also generates quizzes /
flashcards with CSV / Anki / Quizlet export.

- **Audience:** personal / small-group use. Single operator, not multi-tenant.
- **Intended UX:** a Claude-style desktop shell. The user picks a *style*
  (built-in, custom, or AI-generated) and/or a *generator preset*, optionally
  drafts an outline, generates, then manages results in a Library (folders) and
  an Exports center (per-job downloads + ZIP bundles). Recent Jobs and a Job
  Details drawer expose metadata, warnings, and downloads. The Home page offers
  customizable shortcuts.

## 2. Stack

- **Backend:** FastAPI — `api/server.py`. Defines all `/api/*` routes, then
  mounts the built frontend as a catch-all at `/`. The mount is registered
  **after** the API routes, so `/api/*` always wins over the SPA fallback.
- **Frontend:** React (Vite + Tailwind), built to `frontend/dist`, which the
  backend serves **same-origin**. One origin for UI + API.
- **Rendering pipeline (`pipeline/`):** Markdown sanitizer → LLM orchestrator →
  extraction/OCR → math validate/render → PDF/HTML/DOCX renderers.
  - **PDF rendering uses headless Chromium driven via Node** (not a Python HTML
    engine). This is load-bearing and tuned — do not rewrite casually.
  - **OCR uses Tesseract** for image-only PDFs.
  - Attachment extraction supports `.txt/.md/.csv/.tsv/.docx/.pptx/.pdf`.
- **Deployment:** Dockerized, same-origin, port **8000** (uvicorn
  `api.server:app` on `0.0.0.0:8000`). `frontend/dist` is built inside the
  image, never copied from host.

## 3. Providers

- **DeepSeek** and **Qwen** — configured via `.env` (real keys, server-side
  only, gitignored). These are the verified-working providers.
- **Local llama.cpp** — supported via env/discovery; typically shows
  `configured: false` until a local server is set up.
- `/api/options` exposes only non-secret derived info (e.g. which providers are
  `configured`). **Raw keys never reach the frontend.**

## 4. Architecture facts a new session MUST know

- **Non-root container.** The image creates `appuser` (uid **10001**); the
  entrypoint drops privileges via **gosu** before exec'ing the server. Do not
  assume root inside the container.
- **clean.md chokepoint.** All writes to a job's `clean.md` go through
  `JobManager.save_clean_md(...)` (`pipeline/job_manager.py`). It auto-snapshots
  for version history. Never write `clean.md` directly — route through it.
- **Permanent delete is fenced to trash.** Soft-delete moves
  `jobs/<id>/` → `jobs/.trash/<id>/` (reversible). Permanent purge can act
  **only** on a job already inside `jobs/.trash/`, guarded by a path assertion
  that hard-fails any id resolving outside the trash dir. Active jobs can never
  be hard-deleted directly.
- **Math validation degrades, never fails.** Math validation failures mark the
  offending spans and the job ends as **`completed_with_warnings`** — they do
  **not** kill the job.
- **Generator presets** inject a full system prompt and **append**
  `MARKDOWN_MATH_SYSTEM` (`pipeline/orchestrator.py`). Presets are distinct from
  styles (see `DECISIONS.md`).
- **Shortcut store** is a whitelist-validated JSON file at
  `library/shortcuts.json`. Import/export only accepts whitelisted fields.
- **Job stage reporting.** Coarse status (`queued/running/done/
  completed_with_warnings/failed/cancelled`) is augmented by finer `stage`/`progress`,
  surfaced via `GET /api/jobs/{id}/progress` and polled by the Builder.
- **Cooperative cancel.** `POST /api/jobs/{id}/cancel` writes a sidecar marker
  (`jobs/<id>/cancel.requested`) that the pipeline checks at safe stage boundaries;
  the job ends in the terminal `cancelled` status. It is **checkpoint-based, not a
  process kill**, so it takes effect at the next safe checkpoint and **preserves**
  partial artifacts + the user's inputs/settings (see `DECISIONS.md`).
- **Large-PDF core (preflight + page selection).** A read-only
  `POST /api/preflight/pdf` inspects an uploaded PDF *before* job creation and
  returns a soft verdict (`ok`/`warn`/`blocked`); the Builder surfaces it as a
  warning card. The user can pick **first N pages** or a **manual page range**,
  which becomes `page_selections` (`{filename: [[start, end], …]}`, **1-based
  inclusive**) on the LLM request, persisted in `job.json`. Extraction then
  restricts matching PDFs to the selected **ORIGINAL** pages (original `## Page N`
  anchors preserved; OCR runs **only** on selected pages). Default (no selection)
  ⇒ all pages, byte-equivalent to before. **Automatic split/chunk processing and
  hybrid embedded-text + OCR dedup are deferred** (see `DECISIONS.md`).

## 5. Working conventions

- **One slice per branch.** Small feature slices, verify-and-commit between each.
- **Surgical edits, not rewrites.** Preserve routes and pipeline behavior unless
  the slice is explicitly about them. The PDF pipeline is load-bearing.
- **Backend changes must be proven with a live run** — not just by reading
  source. Build + compile + docker + smoke (`test_scripts/smoke_release.py`).
- Keep same-origin Docker behavior, `/api/*` precedence, and the Claude-style UI
  as the visual baseline.
- Verification commands (from `../CLAUDE.md` §4):
  ```fish
  npm --prefix frontend run build
  python -m compileall api pipeline
  docker compose config && docker compose build && docker compose up
  curl http://localhost:8000/api/health
  curl http://localhost:8000/api/options
  ```
