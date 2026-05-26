# Study Guide Generator

Turn course material into clean, exam-focused **study guides** and export them as
**PDF, DOCX, HTML, or Markdown**. It runs as a single self-contained app:

- **Frontend:** React (Vite + Tailwind), Claude-style desktop UI.
- **Backend:** FastAPI (`api/server.py`) — holds your API keys, runs the pipeline.
- **Pipeline:** Markdown sanitizer, LLM generation, file extraction + OCR, KaTeX
  math validation, and a headless-Chromium PDF renderer.
- **Deployment:** Dockerized and **same-origin** — the backend serves the built
  UI, so the whole app is one container on **port 8000** with no CORS setup.

> Looking for the old Streamlit/pandoc/xelatex `v2` pipeline? It's gone. The
> current app is the React + FastAPI + Docker one described here. A backup of the
> old scripts lives in `legacy_scripts/`.

---

## Quick start (Docker)

You only need **Docker** (Docker Desktop, or Docker Engine + the Compose plugin).
No Python/Node/Chromium/Tesseract on your machine.

```bash
cp .env.example .env      # then put YOUR OWN API keys in .env
docker compose up --build
```

Open **http://localhost:8000**. A friend on your LAN can reach it at
`http://<your-ip>:8000`. Stop with `docker compose down`; rebuild after code
changes with `docker compose up --build`.

See **[DOCKER.md](DOCKER.md)** for more detail.

### `.env` setup

`.env` holds each user's own provider keys. It is **gitignored and kept out of the
image** — never commit it. Start from `.env.example`:

- **DeepSeek:** `DEEPSEEK_BASE_URL`, `DEEPSEEK_API_KEY` (default base
  `https://api.deepseek.com/v1`).
- **Qwen (Alibaba DashScope):** `DASHSCOPE_API_KEY` (or `QWEN_API_KEY`),
  `DASHSCOPE_BASE_URL`, `QWEN_MODEL`.

The Models page shows which providers are **configured** — keys themselves never
leave the backend.

### Local models (llama.cpp), optional

Local models run on the **host** (they need your GPU), not in the container. Run
an OpenAI-compatible server, e.g.:

```bash
llama-server -m ./models/your-model.gguf --port 8080
```

Then uncomment the local block in `.env` (compose already maps
`host.docker.internal`):

```
LOCAL_LLM_BASE_URL=http://host.docker.internal:8080/v1
LOCAL_LLM_API_KEY=local
LOCAL_LLM_MODEL=your-model-name
```

The Models page discovers local models from `GET /v1/models` when the server is
up; if it's offline the app reports the discovery error and keeps running.

---

## Major features

- **Three ways to make a guide:** generate with **AI** (default), **paste** text,
  or **upload Markdown**. AI generation supports source **attachments** (with OCR).
- **Styles:** built-in presets plus your own **custom** and **AI-generated**
  styles (Styles page).
- **Outline tab:** shape the guide's sections (templates, add/reorder/instructions,
  or AI-drafted) before generating — the AI follows it in order.
- **Library:** folders, search, filters, sort, single + **batch move**, and
  **save-to-folder** at generation time.
- **Exports Center:** filter by artifact, download per job, or bundle multiple
  guides into a **ZIP** (with an in-zip `manifest.json`).
- **Re-render:** regenerate PDF/HTML/DOCX from an existing guide without re-running
  the LLM.

## Supported uploads

- **Upload Markdown** input: `.md`, `.markdown`.
- **AI attachments** (source material): `.txt`, `.md`, `.markdown`, `.csv`,
  `.tsv`, `.docx`, `.pptx`, `.pdf`. Image-only PDFs go through **OCR** (Tesseract).

## Artifact outputs

Every generated guide produces: **`final.pdf`**, **`final.docx`**,
**`final.html`**, **`clean.md`**, plus `validation.json` and `render.log`.

## Where data persists

All host-mounted (survive restarts; all gitignored):

- `jobs/` — generated guides + their artifacts
- `user_prompts/` — your custom / AI-generated styles (`styles.json`)
- `library/` — folder definitions + job→folder assignments
- `output/` — convenience copies of final outputs

---

## Troubleshooting

- **Port 8000 already in use:** stop the other process, or change the host port in
  `docker-compose.yml` (e.g. `"8080:8000"`) and open that port instead.
- **Missing `.env`:** copy it first (`cp .env.example .env`) and add real keys, or
  providers show as *not configured* and AI generation is disabled.
- **Local model offline:** the Models page shows a discovery error; hosted
  providers (DeepSeek/Qwen) still work. Start your `llama-server` to enable it.
- **OCR quality:** extracted text from scanned PDFs is only as good as the scan —
  low-resolution or skewed pages produce weak text. Prefer text-based PDFs.
- **`docker compose config` prints secrets:** it expands `.env` values in
  plaintext. Don't paste its output into shared logs or issues.

---

## Develop without Docker (optional)

```bash
pip install -r requirements.txt        # Python deps
npm install                            # root: KaTeX for math validation/render
npm --prefix frontend run build        # build the UI the backend serves
python -m uvicorn api.server:app --reload   # http://127.0.0.1:8000
```

Chromium and Tesseract must be installed locally for PDF rendering and OCR.

### Verification commands

```bash
npm --prefix frontend run build        # build the React UI
python -m compileall api pipeline      # compile-check backend + pipeline
docker compose config                  # validate compose (expands secrets!)
docker compose build                   # build the image
python test_scripts/smoke_release.py   # end-to-end smoke against a running app
```

See **[docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md)** for the full feature
inventory and known limitations.
