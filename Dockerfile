# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# Study Guide Generator — single-image build.
# The backend shells out to three native binaries (Chromium for PDF, Node+KaTeX
# for math, Tesseract for OCR), so they all live here alongside Python. The
# React frontend is built in stage 1 and served same-origin by FastAPI in
# stage 2, so the whole app runs on ONE port with no CORS.
#
# Local models (llama.cpp/Gemma/Qwen) are NOT in this image — they run on the
# host's GPU. The container reaches a host-run llama-server via
# http://host.docker.internal:8080/v1 (see docker-compose.yml + .env.example).
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: build the React frontend ──────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Empty base URL => the app issues relative requests, so it works behind
# whatever host/port the backend is served on (see src/api/client.js).
ENV VITE_API_BASE_URL=""
RUN npm run build

# ── Stage 2: runtime (Python + native binaries) ────────────────────────────
FROM python:3.12-slim AS runtime

# System dependencies the pipeline shells out to:
#   chromium            -> PDF rendering (pdf_renderer.py)
#   nodejs              -> KaTeX validate + render (validate_math.js, html_renderer.py)
#   tesseract-ocr (+eng)-> OCR for image-only PDFs (extract.py)
#   fonts-*             -> readable PDFs from headless Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        nodejs npm \
        tesseract-ocr tesseract-ocr-eng \
        fonts-liberation fonts-dejavu-core fonts-noto-core \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Python deps first (cached unless requirements.txt changes).
COPY requirements.txt ./
RUN pip install --break-system-packages -r requirements.txt

# KaTeX (node_modules/katex) for the runtime math passes. Root package.json
# declares katex; install only that, no dev tooling.
COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund

# Application code (.dockerignore keeps node_modules/.venv/jobs/.env/etc. out).
COPY pipeline/ ./pipeline/
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY prompts/ ./prompts/
COPY themes/ ./themes/
COPY app.py ./

# Built frontend from stage 1, served same-origin by FastAPI.
COPY --from=frontend /ui/dist ./frontend/dist

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).status==200 else 1)"

# 0.0.0.0 so the port is reachable from outside the container (and over LAN).
CMD ["python", "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
