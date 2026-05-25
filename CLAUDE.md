# CLAUDE.md — Study Guide Generator (current)

This file describes the **real, current** project so future Claude Code sessions
have accurate context. It supersedes all earlier drafts.

> **Note for anyone who remembers the old brief:** earlier versions of this file
> described a *Streamlit* app living at `~/sgp/studyguide_app` with a
> `purpose × style` prompt tree and hand-written stub modules. **That design is
> obsolete and no longer reflects reality.** The app is now a React + FastAPI +
> Docker application in this directory. Treat the actual repo as authoritative;
> ignore the old Streamlit/`~/sgp` assumptions entirely.

---

## 1. Project summary

**Study Guide Generator** — turns course material into clean, exam-focused study
guides and renders them to PDF (plus Markdown/HTML artifacts).

- **Frontend:** React (Vite + Tailwind), Claude-style desktop UI.
- **Backend:** FastAPI (`api/server.py`).
- **Pipeline:** a Python study-guide pipeline under `pipeline/` (markdown
  processing, LLM generation, extraction/OCR, math validation, PDF rendering,
  provider config).
- **Deployment:** Dockerized, **same-origin**. The FastAPI backend serves the
  built frontend from `frontend/dist`, so UI and API share one origin.
- **Main port:** `8000` (uvicorn `api.server:app` on `0.0.0.0:8000`).

---

## 2. Current architecture

```text
main-app/
├── api/
│   └── server.py        # FastAPI: /api/* routes + static frontend serving
├── frontend/
│   ├── src/             # React app
│   │   └── components/
│   │       ├── DesktopDashboard.jsx   # Claude-style desktop shell / pages
│   │       ├── BuilderWorkspace.jsx   # builder workflow (input → generate → result)
│   │       └── RecentJobsPanel.jsx    # Recent Jobs list + Job Details drawer
│   └── dist/            # built frontend (served by backend; gitignored)
├── pipeline/            # markdown, LLM, extraction/OCR, math validation/rendering, provider config
├── prompts/             # built-in prompt styles (flat .md files + system/user prompts)
├── user_prompts/        # (NOT YET PRESENT) future home for custom/generated styles
├── jobs/                # generated job artifacts (gitignored)
├── output/              # convenience copies of final outputs (gitignored)
├── themes/              # PDF CSS themes (e.g. claude_clean.css)
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── DOCKER.md            # Docker usage notes
```

**Backend route serving (important):** `api/server.py` defines all explicit
`/api/*` routes first, then mounts the built frontend as a catch-all at `/`
(`app.mount("/", StaticFiles(directory=frontend/dist, html=True))`). Because the
mount is registered **after** the API routes, **`/api/*` always wins** over the
static SPA fallback. Keep it that way.

Key API routes (current): `GET /api/health`, `GET /api/options`,
`GET /api/jobs`, `POST /api/jobs/paste`, `POST /api/jobs/upload-markdown`,
`POST /api/jobs/llm`, `GET /api/jobs/{job_id}`,
`GET /api/jobs/{job_id}/artifacts/{artifact_name}`.

---

## 3. Confirmed working baseline

All of the following are verified working as of the current commit:

- Docker build and run work; container reports **healthy**.
- `GET /api/health` works (`{"ok":true}`).
- `GET /api/options` works (returns themes, input modes, styles, providers, models).
- **Paste text → guide** works.
- **Markdown upload → guide** works.
- **LLM generation** works.
- **Provider registry** works for **DeepSeek** and **Qwen** (both configured via env).
- **Local llama.cpp** provider is supported via env/discovery but may be
  **unconfigured** (shows `configured:false` when no local server is set up).
- **Attachments / OCR** work for LLM generation.
- **Attachment extraction metadata/warnings** are visible in the UI
  (Recent Jobs + Builder result panel).
- **Job Details drawer** works (from Recent Jobs / Library / Exports / Builder).
- **PDF / Markdown / HTML artifacts** generate and download correctly.

---

## 4. Important commands

```fish
# Frontend production build (outputs to frontend/dist, which the backend serves)
npm --prefix frontend run build

# Compile-check the Python backend + pipeline
python -m compileall api pipeline

# Validate / build / run the Docker stack
docker compose config
docker compose build
docker compose up

# Smoke-check the running app
curl http://localhost:8000/api/health
curl http://localhost:8000/api/options
```

Run build + compile + docker checks after changes (see §6).

---

## 5. Environment / security notes

- `.env` contains **real local API keys** and **must never be committed**
  (it is gitignored, along with `.env.save`).
- `docker compose config` **expands env values in plaintext** — never paste its
  raw output publicly or into shared logs.
- **API keys must stay server-side only.** The FastAPI backend holds them.
- The **frontend must never receive raw keys** — expose only derived,
  non-secret info (e.g. which providers are `configured`) through `/api/options`.
- `.env`, `.env.save`, `jobs/`, `output/`, `node_modules/`, and `frontend/dist/`
  must **not** be baked into the Docker image (`.dockerignore` enforces this;
  `frontend/dist` is built inside the image, not copied from host).

---

## 6. Development rules

- **Do not** edit application code when the task is docs-only.
- Preserve backend routes and pipeline behavior unless you are explicitly working
  on that slice.
- **Do not rewrite the PDF pipeline casually** — it is load-bearing and tuned.
- Keep the **same-origin Docker behavior** (backend serves `frontend/dist`).
- Keep **`/api/*` routes winning** over the static frontend catch-all.
- Keep the **Claude-style UI** as the visual baseline.
- Prefer **small feature slices**, with verification after each.
- After changes, run the build/compile/docker smoke checks from §4.

---

## 7. Current next planned feature

**Custom and Generated Styles** — let users define their own study-guide styles
(and generate new ones) alongside the built-in ones.

Planned shape:
- `user_prompts/` directory for user-defined styles.
- `user_prompts/styles.json` registry/metadata for those styles.
- New API routes: `GET / POST / PUT / DELETE /api/styles`.
- `POST /api/styles/generate` to generate a new style.
- Builder can select **both built-in and custom** styles.

None of this exists yet — it is the next slice to implement, not current state.
