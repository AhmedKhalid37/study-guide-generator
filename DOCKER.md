# Running with Docker

This bundles everything the app shells out to — Chromium (PDF), Node + KaTeX
(math), and Tesseract (OCR) — into one image. The backend also serves the built
React UI, so the whole app runs on **one port** with no separate frontend server.

## What your friends need

Just **Docker** (Docker Desktop on Windows/Mac, or Docker Engine + the Compose
plugin on Linux). Nothing else — no Python, Node, Chromium, or Tesseract on their
machine.

## First run

```bash
cp .env.example .env      # then put YOUR OWN API keys in .env
docker compose up --build
```

Open **http://localhost:8000**. That's it.

- `.env` holds each user's own DeepSeek/Qwen keys. It is gitignored and excluded
  from the image — **never** commit it or ship it with your keys inside.
- Persistent host data (mounted as volumes, so it survives
  `docker compose down` / restarts):
  - `./jobs/` — generated guides + their artifacts (PDF/DOCX/HTML/MD/logs)
  - `./user_prompts/` — your custom and AI-generated styles (`styles.json`)
  - `./library/` — folder definitions + job→folder assignments
  - `./output/` — convenience copies of final outputs
- Rebuild after code changes with `docker compose up --build`. Stop with
  `docker compose down`.

## Using local models (llama.cpp)

Local models run on the **host**, not in the container (they need your GPU). Run
llama.cpp on your machine:

```bash
llama-server -m ./models/your-model.gguf --port 8080
```

Then uncomment the local-model block in `.env` — the compose file already maps
`host.docker.internal` so the container can reach the host:

```
LOCAL_LLM_BASE_URL=http://host.docker.internal:8080/v1
LOCAL_LLM_API_KEY=local
LOCAL_LLM_MODEL=your-model-name
```

The Models page discovers local models from the OpenAI-compatible
`GET /v1/models` endpoint when the local server is running. If the server is
offline, the app reports the discovery error but keeps running.

## Notes / limits

- **OCR** is included (Tesseract + English). For other languages, add the
  matching `tesseract-ocr-<lang>` package in the `Dockerfile` apt line.
- **Image size** is ~1–1.3 GB — expected, because Chromium + Node + Tesseract are
  all in there. That's the cost of the app being self-contained.
- **LAN access:** because the UI is served same-origin, a friend on your network
  can also hit `http://<your-ip>:8000` and it just works.
- This image runs the **FastAPI + React** app. The legacy Streamlit UI (`app.py`)
  is still installed; run it ad hoc with
  `docker compose exec app streamlit run app.py` if you ever need it.
