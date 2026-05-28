Prompt:
Perform a full A-to-Z review of this entire application. READ ONLY — make NO code
changes, create NO files except a single report. Produce REVIEW.md in the repo
root with these sections. Be specific: cite file paths and line numbers. Do not
pad with praise. Rank issues by severity (critical / high / medium / low).

1. FUNCTIONALITY
   - Map the full feature set and trace the main flows: upload/paste -> extract ->
     LLM generate -> sanitize -> validate math -> render PDF/HTML/DOCX.
   - Flag any broken, half-wired, or dead features. Note features that exist in
     the backend but aren't exposed in the UI, and vice versa.

2. SECURITY
   - Re-audit path handling (job_id, artifact downloads, trash/restore) for
     traversal. Confirm the is_relative_to guards hold everywhere.
   - Check for any committed secrets, unsafe subprocess calls (shell=True),
     SSRF risk in URL fetching, unsafe deserialization, and the Chromium
     --no-sandbox + non-root posture.
   - Confirm the container still runs as non-root (uid 10001) and the export
     allowlist still excludes .env.

3. EFFICIENCY / PERFORMANCE
   - Identify synchronous/blocking calls on the event loop (the create_llm_job
     fix was applied — confirm no NEW blocking calls were introduced in later
     phases).
   - Flag redundant LLM calls, unbounded loops, full-directory scans on every
     request (e.g. Library listing reading every job.json), and the final
     Docker image size with the biggest contributors.

4. CODE QUALITY
   - Duplication (note: scripts/ vs legacy_scripts/ was a known duplicate —
     confirm status), inconsistent error handling, missing tests on critical
     paths, TODOs left in code.

5. BETA-READINESS VERDICT
   - Top 5 things to fix before wider release, in priority order.

Output ONLY the REVIEW.md file and a short summary in chat. Change nothing else.



Review:
# Study Guide Generator — A-to-Z Code Review

**Scope:** Full read-only review of the app on branch `feature-phase5` (HEAD `698d18e`).
**Method:** Read `api/server.py`, the entire `pipeline/`, the Docker stack, the
frontend API client + preview components, and relevant git history.
**No code was changed.** This file is the only artifact produced.

> **Headline finding up front:** `feature-phase5` was branched from `38cc822`
> *before* the two hardening commits landed and **never merged them back**. The
> commits `863f5b7 "Harden Docker: non-root"` and `61c134c "Fix event-loop
> blocking"` exist only on `chrome-renderer-v1` and `hardening`
> (`git branch --contains` confirms both; `git merge-base --is-ancestor 61c134c
> HEAD` returns false). So on this branch the container **runs as root** and the
> main generation endpoint **blocks the event loop** — both regressions relative
> to the review brief's assumptions.

---

## 1. FUNCTIONALITY

### Feature map (all confirmed wired end-to-end)
The backend API surface (`api/server.py`) and the frontend client
(`frontend/src/api/client.js`) match closely — there are no orphaned backend
routes and no UI calls to missing routes. Verified the following flows:

| Flow | Entry | Pipeline |
|------|-------|----------|
| Paste → guide | `POST /api/jobs/paste` (`server.py:1050`) | `run_pasted_text_job` → `run_raw_markdown_pipeline` (`run_markdown_job.py:61,94`) |
| Markdown upload → guide | `POST /api/jobs/upload-markdown` (`server.py:1072`) | `run_markdown_job` (`run_markdown_job.py:21`) |
| LLM generate (+attachments/OCR) | `POST /api/jobs/llm` (`server.py:1105`) | `_save_llm_attachments` → `run_llm_job` → `extract_file` → `generate_study_guide` → `run_raw_markdown_pipeline` |
| Sanitize → validate → render | inside `run_raw_markdown_pipeline` (`run_markdown_job.py:94`) | `sanitize` → `validate` (node KaTeX) → `render_pdf` (Chromium) |
| DOCX (lazy) | `_ensure_docx` (`server.py:2273`) | `pipeline/docx_renderer.render_docx` |
| Styles CRUD + AI generate | `/api/styles*` | `pipeline/style_store.py` |
| Library folders + move/batch | `/api/library*` | `pipeline/library_store.py` |
| Exports center + ZIP bundle | `/api/exports*` | `export_bundle` (`server.py:732`) |
| Outline gen + presets | `/api/outline/generate`, `/api/presets*` | `presets.py` |
| Versions / edit / revert / section regen / quiz | `/api/jobs/{id}/...` | `markdown_sections.py`, quiz helpers in `server.py` |

The full generation chain (extract → LLM → sanitize → math-validate → render
PDF/HTML, DOCX lazily) is intact and consistent.

### Broken / half-wired / drift
- **Doc drift (low).** `CLAUDE.md §7` lists "outline templates as saved presets"
  and "wiring the cosmetic Save draft button" as *deferred / not started*, but
  both are implemented: `pipeline/presets.py` + `GET /api/presets` +
  `applyPreset` (`client.js:44`), and commit `698d18e "Phase 5A: … draft
  autosave"`. The status section is stale and understates what ships.
- **Obsolete Streamlit app still present (low/medium).** `app.py` (533 lines) is
  the old Streamlit UI that `CLAUDE.md` declares obsolete, yet it is git-tracked
  **and copied into the Docker image** (`Dockerfile:62 COPY app.py ./`). It is
  dead in the React/FastAPI deployment. See also §3 (drags in Streamlit deps).
- **Local llama.cpp provider** correctly reports `configured:false` when unset
  (`provider_config.py:235`) — expected, not a bug.
- No truly dead backend routes were found; the API/UI parity is good.

---

## 2. SECURITY

### Path traversal — guards hold
- `_get_job` (`server.py:2243`) rejects `/`, `\`, `""`, `.`, `..`, then resolves
  and requires `job_dir.is_relative_to(JOBS_DIR)` **and** manifest existence.
  Solid.
- Artifact downloads (`get_artifact` `server.py:1178` → `_artifact_path`
  `server.py:2293`) only map a fixed `ARTIFACTS` dict to `getattr(job, key)` —
  `artifact_name` is never used as a raw path. Safe.
- Version / quiz file access uses int path segments and `_is_job_path`
  (`server.py:1370,1382,1710,1723,2327`). Safe.
- `style_store._safe_custom_path` (`style_store.py:107`) strips directory
  components, requires `.md`, and re-checks `is_relative_to(USER_PROMPTS_DIR)`.
  Folder ids are validated against `ID_PATTERN` and used only as JSON keys
  (`library_store.py:35`). No traversal surface found in stores.
- ZIP bundle entry names are slugified (`_safe_slug` `server.py:851`) and
  uniquified — no zip path escape.

**Verdict:** the `is_relative_to` guards are present and correct everywhere they
matter.

### Secrets / subprocess / SSRF / deserialization
- **No committed secrets.** Only `.env.example` is tracked (`git ls-files`);
  `.env`/`.env.save` are gitignored and excluded by `.dockerignore`.
- **No `shell=True`, `os.system`, `eval`, `exec`, `pickle`, or `yaml.load`**
  anywhere in `pipeline/`, `api/`, `app.py`. All subprocess calls use list-form
  argv (`pdf_renderer.py:44`, `html_renderer.py:216`, `math_validator.py:69`).
- **No user-controlled SSRF in provider config.** `_discover_openai_models`
  (`provider_config.py:268`) fetches only env-configured `base_url`, never user
  input, and blocks `host.docker.internal` outside Docker.

### CRITICAL — container runs as root + Chromium `--no-sandbox`
- `Dockerfile` has **no `USER` directive** (`grep` confirms none); the process
  runs as **uid 0**. The brief's "non-root uid 10001" only exists on
  `chrome-renderer-v1` (`Dockerfile:29 RUN useradd --uid 10001 appuser`), which
  is **not merged here**.
- `pdf_renderer.py:48` launches Chromium with `--no-sandbox`. `--no-sandbox` +
  **root** + rendering **attacker-influenceable HTML** (see next item) is the
  worst-case posture: a Chromium renderer exploit runs as root in the container.

### HIGH — stored XSS via raw HTML in rendered guides
- `html_renderer._markdown_to_html` constructs MarkdownIt with **`"html": True`**
  (`html_renderer.py:56`), so raw `<script>`/`<iframe>` in the source markdown
  (pasted text, uploaded `.md`, LLM output, or extracted attachment text) is
  passed through verbatim into `final.html`.
- `final.html` is served **inline, same-origin** (`get_artifact` with
  `disposition=inline`) and previewed in
  **`RecentJobsPanel.jsx:1463 sandbox="allow-same-origin allow-scripts"`**.
  Setting *both* `allow-same-origin` and `allow-scripts` on a same-origin frame
  **defeats the sandbox** — scripts execute in the app's origin.
  - Inconsistent with `BuilderWorkspace.jsx:1704` which uses
    `sandbox="allow-same-origin"` only (scripts disabled) — the safer choice.
- Combined with **no authentication** (below), a crafted guide can script the
  app origin and call any `/api/*` route (delete folders/styles, read every
  job's content).

### HIGH — SSRF / local-file read through the PDF renderer
- Because of `html: True`, source content can embed `<img src="http://attacker/…">`
  or `<iframe src="file:///etc/passwd">`. Chromium loads the HTML from a
  `file://` origin (`pdf_renderer.py:58`) and will fetch remote resources and
  local files, baking them into the PDF or beaconing out. There is no Content
  Security Policy and no network isolation on the render step.

### HIGH — no authentication / authorization anywhere
- Every `/api/*` route is unauthenticated. The container binds `0.0.0.0:8000`
  (`Dockerfile:72`) and `docker-compose.yml:6` publishes `8000:8000`, so **any
  host on the LAN** can: trigger LLM jobs (burning the owner's API credits),
  read all generated guides, and delete styles/folders. There is no rate limit
  on the expensive LLM endpoints.

### Export allowlist — holds
- `EXPORT_ARTIFACTS` / `ARTIFACTS` (`server.py:55,72`) are fixed allowlists; raw
  source, attachments, and `.env` can never be bundled or downloaded.
  `_safe_manifest` (`server.py:1997`) strips all filesystem-path fields before
  returning manifests. `.dockerignore` excludes `.env`/`.env.save`. Good.

---

## 3. EFFICIENCY / PERFORMANCE

### CRITICAL — event-loop blocking regression in `create_llm_job`
- `create_llm_job` is `async def` (`server.py:1106`) but calls the **fully
  synchronous** `run_llm_job(...)` **directly** at `server.py:1130` — no
  `await`, no `asyncio.to_thread`, and `asyncio` is not even imported.
- `run_llm_job` does a blocking LLM HTTP call (`generate_study_guide`), a Node
  KaTeX subprocess, and a Chromium subprocess — potentially **minutes**. For
  that entire duration the asyncio event loop is blocked, so **every other
  request hangs** (health checks, job listing, a second user's request).
- This is a **regression**: commit `61c134c` wrapped it as
  `await asyncio.to_thread(run_llm_job, …)`, but that commit is on
  `chrome-renderer-v1`/`hardening`, not on `feature-phase5`. Verified HEAD has
  `import asyncio` absent and the bare call present.
- Ironic asymmetry: the *other* LLM endpoints (`retry` `server.py:1229`,
  `regenerate_job_section` `:1454`, `generate_quiz` `:1582`, `generate_outline`
  `:472`, `generate_style` `:319`) are plain `def`, so Starlette runs them in
  the threadpool and they do **not** block the loop. Only the primary path is
  broken.

### MEDIUM — full-directory rescans + repeated file reads on every list request
- `/api/jobs` (`list_jobs` `server.py:568`), `/api/library` (`_all_library_jobs`
  `:944`), and `/api/exports` (`_all_export_jobs` `:804`) each `glob('*/job.json')`
  over the entire `jobs/` tree, parse every manifest, and `stat` ~6 artifacts per
  job (`_artifact_availability` `:2259`) on **every** call (including every
  search keystroke, since filtering is server-side).
- Worse, each job triggers `library_store.folder_id_for(job_id)` (via
  `_all_library_jobs:959`, `_all_export_jobs:821`, `_folder_meta:1984`), and
  `folder_id_for` (`library_store.py:317`) re-reads and re-parses the **entire
  `job_folders.json`** every call → O(N) full reads of the same file per list.
  `list_jobs`/`_all_export_jobs` precompute `folders_by_id` but still pay the
  per-job assignment read.
- **No server-side pagination** on `/api/library` or `/api/exports` (only
  `/api/jobs` honors `limit`). Fine for a personal corpus; will degrade with
  hundreds–thousands of jobs.

### MEDIUM — Docker image bloat from an unused dependency tree
- `requirements.txt` pins `streamlit>=1.36.0`, which drags in pandas, pyarrow,
  altair, etc. Streamlit is only used by the **obsolete** `app.py`; the React +
  FastAPI deployment never imports it. Removing `streamlit` (and dropping
  `app.py` from the image) would cut several hundred MB.
- Largest image contributors overall: `chromium` + its libs, `nodejs npm`,
  `tesseract-ocr` + fonts, and the Python wheels (`pymupdf`, `pillow`, plus the
  needless `streamlit`/pandas/pyarrow). (Image not built during this read-only
  review; this is from the dependency manifest + `Dockerfile`.)

### LOW — other
- No redundant/duplicate LLM calls observed; each endpoint makes one call.
- Loops are bounded: `MAX_OUTLINE_SECTIONS=50`, `MAX_BUNDLE_JOBS=100`,
  attachment caps (`run_llm_job.py:17`), quiz content cap 120 KB
  (`server.py:1641`). Good.
- `export_bundle` builds the whole ZIP in an in-memory `BytesIO`
  (`server.py:740`); bounded by 100 jobs but many large PDFs could spike memory.

---

## 4. CODE QUALITY

- **Duplication — `scripts/` vs `legacy_scripts/` still present (low).**
  `legacy_scripts/` is git-tracked and largely duplicates `scripts/`
  (`build_guide.py` identical; `sanitize_markdown_math.py` differs).
  `.dockerignore` keeps `legacy_scripts/` out of the image, but it remains repo
  clutter. The known duplicate was **not** removed.
- **Stray source artifacts (low).** `ch4_raw.md`, `ch5_raw.md`, `ch6_raw.md` are
  tracked at repo root — leftover input material, not part of the app.
- **Dead code (low/medium).** `app.py` (Streamlit) is obsolete but shipped
  (see §1/§3). `run_markdown_job._run_raw_markdown_pipeline` (`:180`) is an
  unused private alias of the public function.
- **Error handling — mostly consistent, one smell.** Pipeline errors are well
  categorized via `pipeline/errors.classify_exception` and surfaced through
  `_job_error`/`set_status`. However several "keep the artifact in sync" blocks
  swallow all exceptions silently with bare `except Exception: pass`
  (`server.py:768, 1322, 1360, 1398, 1568`) for lazy DOCX regen. Acceptable as
  best-effort, but a failed DOCX refresh leaves a stale `.docx` with no signal.
- **No TODO/FIXME/XXX** left in `pipeline/`, `api/`, or `frontend/src/`. Clean.
- **Tests — manual smoke only, no runner/CI.** `test_scripts/` has useful
  coverage of the riskiest pure logic (`test_math_regressions.py`,
  `test_markdown_sections.py`) plus end-to-end smoke (`smoke_release.py`), but
  there is **no `pytest`/CI config** (`no pytest.ini/pyproject/.github`). The
  security-critical guards (`_get_job` traversal, `_safe_custom_path`, the
  sanitizer's code-fence handling) have no automated regression test, and
  nothing runs the smokes on push.

---

## 5. BETA-READINESS VERDICT

The feature set is broad, coherent, and largely works; the blockers are not
features but **two regressions that never merged from the hardening branch** plus
the consequences of rendering untrusted HTML. Top 5, in priority order:

1. **Restore the non-blocking LLM call.** Wrap the generation in
   `await asyncio.to_thread(run_llm_job, …)` at `server.py:1130` (re-add
   `import asyncio`), or merge `61c134c`. Until then a single generation freezes
   the whole server. *(Critical)*

2. **Run the container as non-root and rein in Chromium.** Add the
   `USER 10001`/`appuser` setup (merge `863f5b7`); `--no-sandbox` as root over
   attacker-influenced HTML is the highest-impact security gap. *(Critical)*

3. **Stop executing untrusted HTML.** Either disable `html: True` in
   `html_renderer.py:56` (or sanitize/strip script/iframe/remote-resource tags),
   and fix the preview iframe to **`sandbox="allow-same-origin"` only**
   (remove `allow-scripts` at `RecentJobsPanel.jsx:1463`). This closes the
   stored-XSS and SSRF/local-file vectors together. *(High)*

4. **Add authentication + a rate limit** before exposing beyond a trusted
   single user — the app binds `0.0.0.0` with no auth and unmetered LLM
   endpoints (credit-burn + data exposure on any shared network). *(High)*

5. **Trim and pin for reproducible, smaller deploys.** Drop `streamlit`/`app.py`
   from `requirements.txt` and the image, pin `fastapi`/`uvicorn`/
   `python-multipart` versions, and remove `legacy_scripts/` + stray
   `ch*_raw.md`. Then cache folder assignments per request to avoid the O(N)
   re-reads in library/exports listing. *(Medium)*

**Bottom line:** safe and pleasant for the single trusted local user it was built
for; **not ready for wider/multi-user or LAN-exposed release** until items 1–4
are addressed. Note that `chrome-renderer-v1` already contains the fixes for #1
and #2 — the immediate action is reconciling `feature-phase5` with that branch.
