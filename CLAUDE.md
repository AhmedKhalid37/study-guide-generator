# CLAUDE.md — Study Guide Generator working instructions

> Short, current entrypoint for future Claude / Claude Code / Codex sessions.
> This file is intentionally **not** a full project report — it points at the
> deep context and live docs, and records the rules that must not be relearned.
> The **repo (code) is the source of truth**; if any doc disagrees with the
> implementation, trust the code and verify before acting.

---

## Start Here

1. **Read `docs/PROJECT_DEEP_CONTEXT_REPORT.md` first.** It is the single-file
   long-term memory (architecture, backend/frontend maps, full route inventory,
   pipeline, security model, feature groups, deferred work) reconciled against
   the implementation. Absorb it before changing anything.
2. Then skim the live docs (next section) for current state and the "why".
3. For anything load-bearing (PDF render, extraction/OCR, job manager, provider
   resolution, LMM boundary), **open the actual file** before editing — the docs
   summarize, they do not substitute.

> **Note for anyone who remembers an old brief:** ignore the obsolete
> *Streamlit / `~/sgp/studyguide_app`* design entirely, and ignore any older
> copy of this file that only described paste/upload/LLM + library/exports — the
> app has since grown Provider Settings, large-PDF handling, the Shortcut
> Inspector/Repair loop, Ask Your Guide, quizzes/flashcards, section
> regeneration, version history, trash, and the Local Model Manager.

---

## Source Of Truth Order

1. **The repo / running code** — authoritative.
2. **`docs/PROJECT_DEEP_CONTEXT_REPORT.md`** — deep navigational context.
3. **Live docs (keep current as you work):**
   - `docs/CURRENT_TASK.md` — live per-slice log (most recent work at the top).
   - `docs/NEXT_CHAT_HANDOFF.md` — one-page "start here" / current position.
   - `docs/PROJECT_CONTEXT.md` — stable, slow-changing overview.
   - `docs/DECISIONS.md` — append-only rationale for non-obvious choices.
4. **This file (`CLAUDE.md`)** — durable rules + entrypoint only.

---

## Current Project State

**Study Guide Generator** — a Dockerized, **same-origin React (Vite + Tailwind) +
FastAPI** app for a single operator / small group. It turns pasted text, uploaded
Markdown, or uploaded attachments into exam-focused study guides rendered to
**PDF** (headless Chromium) plus **Markdown / HTML / DOCX**, and also generates
**quizzes / flashcards** (CSV / Anki / Quizlet export).

Seven workspaces (nav ids in `DesktopDashboard.jsx`):
**Home** (shortcuts) · **Builder** · **Library** · **Ask Guide** · **Styles** ·
**Models** (Provider Settings + Local Models) · **Exports**.

Completed / validated feature groups (verify in code before relying on details):

- **Provider Settings** — in-app provider/key/model/runtime config — **complete**.
- **Large-PDF preflight + page-selection core** — **complete** (auto-split deferred).
- **Shortcut Inspector / Repair Loop** — **complete**.
- **Ask Your Guide** (local-model-only v1) — **complete enough**; must stay local-only.
- **Local Model Manager (LMM) Phase 1** (detection + manual command helper) — **complete + validated**.
- **Local Model Manager Phase 2** (host companion → approved-GGUF scan → Unix-socket
  backend bridge → model-library UI → companion-managed `llama-server` lifecycle) —
  **safe milestone complete / PAUSED after Phase 2G11 final hardening.**
- **Deep project context report** (`docs/PROJECT_DEEP_CONTEXT_REPORT.md`) — exists.

Recommended next: keep LMM Phase 2 paused; resume only with a separately designed
approve-root flow or a packaging slice. See `docs/CURRENT_TASK.md` for the live pick.

---

## Branch And Git Rules

- **Main branch / trunk / PR target: `chrome-renderer-v1`.** Branch all new work
  from it.
- **Do not revive old consumed/feature branches** — Group C and the
  LMM/Ask/Provider/Shortcut stacks were already squashed/integrated onto the
  trunk. Re-merging/rebasing/cherry-picking them reintroduces superseded code and
  resurrects resolved conflicts. They are kept (operator preference) as archival
  reference only. See `DECISIONS.md` → "Consumed feature branches must not be
  re-merged".
- **Do not force-push.**
- **Use Codex-formatted implementation prompts** when handing off implementation
  work, **unless the user explicitly switches back to Claude Code.**
- **Review reports before recommending a merge** — read the actual diff/validation,
  don't recommend merging on summary alone.
- **Do not repeatedly ask for `git status`** unless there is a concrete safety
  reason (e.g. about to do something destructive or history-altering).
- One slice per branch; verify-and-commit between each; surgical edits, not rewrites.

---

## Development / Slice Rules

- **Docs-only tasks: do not edit application code.** Don't touch backend/frontend
  files when the task is documentation.
- Preserve backend routes and pipeline behavior unless the slice is explicitly
  about that area.
- **Do not rewrite the PDF / Chromium render pipeline casually** — it is
  load-bearing and tuned. Same for the math sanitizer/validator and the
  page-level extraction/OCR fallback.
- Keep the **same-origin Docker behavior** (backend serves `frontend/dist`) and
  keep **`/api/*` routes winning** over the static SPA catch-all (routes are
  registered before the `/` mount — keep that order).
- Keep the **Claude-style UI** as the visual baseline.
- **`/api/jobs/llm` has two request-construction paths that do NOT share parsing**
  (JSON body vs multipart-with-attachments). Any field added to `LLMJobRequest`
  must be wired into the multipart `_parse_llm_request` branch too and verified in
  **both** paths.
- **All writes to a job's `clean.md` go through `JobManager.save_clean_md(...)`** —
  never write it directly (it auto-snapshots version history).
- Prefer small slices with verification after each; commit at stable milestones.

---

## Security Invariants

These must hold. Treat any violation as a blocker.

- **Raw secrets must NEVER appear** in: public APIs (`/api/options`,
  `/api/provider-settings`, `/api/local-model/*`, `/api/ask/*`), logs, job
  artifacts (`job.json`), exports, served JS / frontend state, docs with real
  values, session/history/cache files, or command output pasted to chat. This
  covers both **provider API keys** and the **LMM companion token**. Keys are
  server-side only and write-only over the API; the public DTO has **no key field
  by construction** (only derived non-secret info: `configured`, `key_source`,
  last-4 `key_hint`, `base_url_host`).
- **Do not paste full `docker compose config` output** anywhere — it expands env
  secrets in plaintext. For a syntax check, redirect to a temp file only
  (`docker compose config >/tmp/compose-check.txt`) and don't share its contents.
- **`.env` / `.env.save`** hold real keys — gitignored + dockerignored, never
  committed, never baked into the image.
- **LMM boundary (must hold):**
  - The React frontend **never** talks directly to the host companion (only via
    the backend bridge).
  - The Docker backend **must not** directly browse the host filesystem or
    directly start/stop host processes — that is the host companion's job.
  - **No** Docker socket, privileged container, host PID namespace, whole-PC
    scan, arbitrary shell, free-form argv, or browser-provided host path. Approved
    model roots come from companion config only (no browser folder picker).
  - LMM DTOs whitelist fields and never expose the token, socket path, absolute
    host model/executable path, raw argv, `Authorization` header, or full URLs.

---

## Architecture Snapshot

```text
main-app/
├── api/server.py        # FastAPI: ALL /api/* routes, then SPA static mount at "/"
├── frontend/            # React (Vite + Tailwind) → built to frontend/dist (served by backend)
│   ├── src/components/   # workspaces + panels
│   ├── src/*.js          # pure, React-free helper modules (node-testable)
│   └── scripts/*.mjs     # pure-node verify harnesses (no test runner)
├── pipeline/            # backend logic: extraction/OCR, LLM, render, stores, ask, lmm bridge
├── tools/local_model_companion/  # host-side companion (NOT in the Docker image)
├── prompts/             # built-in style .md prompts + system/user templates
├── user_prompts/        # custom/generated styles + styles.json (gitignored runtime)
├── library/             # folders.json, job_folders.json, shortcuts.json (gitignored runtime)
├── config/              # provider_settings.json, secrets.json, selection json (gitignored)
├── jobs/                # job artifacts + jobs/.trash/ (gitignored)
├── themes/              # PDF CSS themes (only claude_clean.css today)
├── test_scripts/        # smoke_* + test_* + live validation harnesses
└── docs/                # design docs, validation records, deep report, examples/
```

- **Same-origin, single container, port 8000.** `frontend/dist` is built **inside**
  the image (multi-stage), never copied from host.
- **Non-root container:** `appuser` (uid 10001), `no-new-privileges`. Do not assume
  root inside the container.
- Runtime deps baked in: **chromium** (PDF), **nodejs/npm** (KaTeX/HTML), **tesseract-ocr**
  (OCR), **gosu** (privilege drop).
- The committed `docker-compose.yml` has **no companion socket mount and no LMM env**
  — all LMM validation uses temporary, non-committed Compose overrides.

> The real route surface is much larger than the old "Key API routes" list — see
> the deep report §5 and `api/server.py` for the authoritative inventory (jobs +
> versions/revert + section regen + outline compliance, quizzes, bulk + trash,
> preflight, styles, library, shortcuts + inspect/repair, provider-settings,
> local-model/*, ask/*, exports).

---

## Current Feature Map

- **Builder** — paste / upload-markdown / LLM input; style + generator-preset
  selection; output-section toggles + depth/difficulty axes; attachments with
  large-PDF preflight + page selection; editable Outline tab; progress polling;
  result panel with warnings. (The visible "mode" control was retired — styles
  define guide type; backend still defaults `mode` to `study_guide`. "Save draft"
  and the sidebar storage meter are decorative/inert — deferred wiring.)
- **Two distinct registries — never conflate:** generator presets
  (`/api/options.generator_presets`: system prompt + sampling) vs outline
  quick-templates (`/api/presets`: outline section bundles).
- **Sections/axes:** `include_sections`, `output_depth`, `difficulty` — canonical
  key set lives in `pipeline/orchestrator.py`; frontend `*Meta.js` files hold
  labels/grouping only.
- **Library** — folders, search/filter/sort, single + batch move, trash
  (soft-delete + restore + guarded purge; purge only acts inside `jobs/.trash/`).
- **Exports** — per-job downloads, filters, multi-job ZIP bundles (chat history
  never included).
- **Jobs/artifacts** — `final.pdf`, `final.docx` (lazy from `clean.md`),
  `final.html`, `clean.md`, `validation.json`, `render.log`; version snapshots;
  cooperative checkpoint-based cancel (sidecar marker, never a process kill);
  retry gated to `failed`.
- **Providers** — DeepSeek + Qwen verified-working; `local` supported via
  env/discovery (usually `configured:false` until a local server is set up).
  Resolution precedence: per-job request > provider-settings store default >
  `.env` > built-in default.
- **Ask Your Guide** — local-model-only chat over a generated guide with mandatory
  budgeted retrieval + citation contract; reads artifacts read-only; no process
  control; stores no secrets; never auto-exported.
- **Local Model Manager** — see Current Project State; host companion owns host
  filesystem/process access, backend bridges over a token-authed Unix socket.

---

## Deferred Work

Do not begin any of these without an explicit, separately-designed slice:

- **LMM approve-root flow** (must be designed as a host-companion flow).
- **App-suggested local model settings / recommendations.**
- **Ollama / simple-local-model path.**
- **Windows / macOS packaging / support.**
- **Model downloads** (no download manager).
- **Hosted / cloud Ask mode** (Ask stays local-only).
- **Ask extra session uploads.**
- **Large-PDF preflight size-limit polish / hybrid embedded-text + OCR
  optimization** (and automatic split/chunk processing).
- **Broader guide optimization / visual extraction enhancements.**

(Other smaller deferrals — second PDF theme, server-side pagination, GHCR publish,
pinned `requirements.txt` lockfile, outline presets-as-saved, drag-and-drop — are
recorded in the deep report and `DECISIONS.md`.)

---

## Validation Guidance

After backend/frontend changes, prove it with a live run, not just by reading
source:

```fish
npm --prefix frontend run build              # builds to frontend/dist
python -m compileall api pipeline            # (+ tools when companion code changes)
docker compose config && docker compose build && docker compose up
curl http://localhost:8000/api/health
curl http://localhost:8000/api/options
python test_scripts/smoke_release.py         # end-to-end release check
git diff --check
```

Pure helper modules have node harnesses under `frontend/scripts/*.mjs`
(`npm --prefix frontend run test:*`); backend slices have focused
`test_scripts/test_*.py`. Many pure checks skip endpoint sections when FastAPI is
unavailable in host Python — run those in Docker for full coverage.

---

## Common Mistakes To Avoid

- Trusting the old "Key API routes" shortlist — the surface is much larger; check
  `api/server.py`.
- Adding an `LLMJobRequest` field on the JSON path only and forgetting the
  multipart branch (silently dropped whenever a generation has an attachment).
- Writing `clean.md` directly instead of through `JobManager.save_clean_md`.
- Conflating generator presets (`/api/options.generator_presets`) with outline
  quick-templates (`/api/presets`).
- Widening the section/axis vocabulary in frontend `*Meta.js` without first adding
  the fragment in `pipeline/orchestrator.py` (dead toggle that produces nothing).
- Re-merging an old consumed branch, or branching from one instead of `chrome-renderer-v1`.
- Pasting raw `docker compose config` output, or assuming any key/token can appear
  in an API, log, artifact, export, or the frontend.
- Assuming root inside the container, or that the Docker backend may touch the host
  filesystem / host processes directly.
- Reviving deferred work (LMM approve-root, model downloads, hosted Ask, etc.)
  without an explicit slice.
