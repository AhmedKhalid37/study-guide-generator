# CLAUDE.md — Study Guide Generator & Markdown→PDF App (v1)

This file is the authoritative brief for building the v1 skeleton of this app.
Read it fully before writing any code. Follow it literally. Where it says
**STUB** or **DO NOT IMPLEMENT**, create the file with a passthrough/placeholder
and a `# TODO(human)` marker — do not write real logic. Those pieces are written
by hand and dropped in later; if you implement them, they will be deleted.

---

## 0. What this app is

A local desktop app (Streamlit UI) that turns course material into a clean,
exam-focused study-guide **PDF** that visually matches a specific reference
look (serif body, pill-styled inline code, KaTeX math). It supports four inputs:

- **A** — generate from files/text via a hosted LLM (DeepSeek)
- **B** — generate from files/text via a local LLM (Ollama / llama.cpp)
- **C** — paste existing AI output (ChatGPT/Claude/etc.) → clean → PDF
- **D** — upload an existing `.md` → clean → PDF

A, B, C, D collapse into **two code paths**:
1. *Generate path* (A, B): need an LLM to produce Markdown.
2. *Have-markdown path* (C, D): Markdown already exists; skip the LLM.

Everything downstream of "we have Markdown" is identical for all four.

---

## 1. LOCKED decisions — do not change, do not "improve"

These were decided deliberately. Do not substitute alternatives.

- **Render stack is Path 1:** `Markdown → HTML+KaTeX → headless Chromium → PDF`.
- **NO Pandoc. NO XeLaTeX. NO LaTeX.** The old `render_pdf.sh` is dead. Do not
  call it, port it, or reintroduce a LaTeX dependency.
- **HTML→PDF engine is Playwright** (Python) driving bundled Chromium via
  `page.pdf()`. Not `wkhtmltopdf`, not `weasyprint`, not a raw
  `chromium --print-to-pdf` shell call.
- **Math engine is KaTeX**, rendered server-side in the Node MD→HTML step. The
  same KaTeX is the validation gate. There is no second math engine.
- **UI is Streamlit.** Do not switch to FastAPI/Flask/React.
- **One LLM client** for all providers. DeepSeek and local servers are both
  OpenAI-compatible — they differ only by `base_url` / `api_key` / `model`.
  Do not write per-provider client classes.
- **Prompt templates: `purpose × style` only** for v1. Do NOT build
  `subjects/` or `profiles/` composition. Those folders may exist empty.
- **Shell snippets in any docs/READMEs you write must be fish shell**, not bash.
- **Styling is external CSS.** No visual styling may be hardcoded in Python or
  in the renderer. All look-and-feel lives in `pdf_templates/*.css` (which are
  STUBS — see §3).

---

## 2. DIVISION OF LABOUR — read this twice

You (the agent) build the **plumbing**. Four pieces are written by hand and
must be left as runnable passthrough stubs.

### You BUILD (full implementation):
`config.py`, `job_manager.py`, `input_handler.py`, `text_extractor.py`,
`orchestrator.py`, `llm_client.py`, `math_validator.py`, `pdf_renderer.py`,
`render/md_to_html.js`, `app.py`, the folder scaffold, `requirements.txt`,
`package.json`, and a short fish-shell `README.md`.

### You STUB (create file, passthrough body, `# TODO(human)`, NO logic):
- `pipeline/markdown_sanitizer.py` → `def sanitize(text: str) -> str: return text`
- `pipeline/auto_repair.py` → returns input unchanged (signature in §4)
- `pdf_templates/*.css` → create the files but leave them near-empty
  (a `/* TODO(human): theme */` comment + a single `body{}` rule is fine).
  **Do not write a theme.** Generic CSS here will be deleted.
- `prompts/**/*.md` → create placeholder files with a `<!-- TODO(human) -->`
  line only. **Do not write prompt content.**

### You PORT from the existing repo `~/sgp/studyguide_pipeline`:
- `scripts/validate_math.js` → copy to `render/validate_math.js`, then **extend
  it** to accept a `--json` flag that prints a single JSON object to stdout:
  `{"ok": bool, "displayBlocks": int, "inlineFormulas": int, "errors":[{"expr","displayMode","error"}]}`.
  Keep the existing human-readable mode as default. Keep its KaTeX logic intact.
- `scripts/build_guide.py` → harvest **only** `extract_text`, `clean_text`,
  `chunk_text` (and the chunk-merge idea) into the new modules. Discard the rest;
  it is the old monolith.
- `scripts/sanitize_markdown_math.py` → **DO NOT PORT.** Replaced by the human
  stub above.
- `scripts/render_pdf.sh` → **DEAD.** Do not use.

---

## 3. Folder structure (create exactly this)

Target location: `~/sgp/studyguide_app/` (new tree; the old pipeline stays put).

```text
studyguide_app/
├── app.py
├── config.py
├── requirements.txt
├── package.json
├── README.md
├── CLAUDE.md                  # this file
├── pipeline/
│   ├── __init__.py
│   ├── input_handler.py
│   ├── text_extractor.py
│   ├── orchestrator.py
│   ├── llm_client.py
│   ├── markdown_sanitizer.py  # STUB
│   ├── math_validator.py
│   ├── auto_repair.py         # STUB
│   ├── pdf_renderer.py
│   └── job_manager.py
├── render/
│   ├── md_to_html.js          # markdown-it + KaTeX → standalone HTML
│   └── validate_math.js       # ported + --json flag
├── prompts/
│   ├── _system.md             # STUB placeholder
│   ├── exam/
│   │   ├── baby_steps.md       # STUB
│   │   ├── cram_guide.md       # STUB
│   │   └── final_solution.md   # STUB
│   ├── presentation/
│   ├── report/
│   ├── project/
│   └── general/
├── pdf_templates/
│   ├── default.css            # STUB
│   └── clean_exam.css         # STUB
├── assets/
│   └── fonts/                 # human drops the body serif here later
├── jobs/                      # runtime output, gitignored
└── output/                    # convenience copies of final PDFs
```

---

## 4. Module contracts

Implement these signatures so the hand-written pieces drop in without edits.
Python 3.11+, full type hints, `pathlib`, no global mutable state.

### `config.py`
A single immutable settings object built from env + defaults.
- Paths: `BASE_DIR`, `JOBS_DIR`, `OUTPUT_DIR`, `PROMPTS_DIR`,
  `PDF_TEMPLATES_DIR`, `ASSETS_DIR`, `RENDER_DIR`.
- Providers (resolved from env, with these defaults):
  - `deepseek`: `base_url="https://api.deepseek.com"`, key from `DEEPSEEK_API_KEY`, `model="deepseek-chat"`.
  - `local`: `base_url=os.getenv("LLM_BASE_URL","http://127.0.0.1:8080/v1")`, key `os.getenv("LLM_API_KEY","local")`, `model=os.getenv("LLM_MODEL","local-model")`.
- Defaults: `DEFAULT_PURPOSE="exam"`, `DEFAULT_STYLE="cram_guide"`,
  `DEFAULT_CSS="default.css"`, `PAGE_FORMAT="A4"`, `CHUNK_CHARS=18000`.

### `job_manager.py`
Owns the on-disk job folder and manifest. **All artifact paths come from here**
— no other module hardcodes filenames.
- `job_id` format: `YYYYMMDD-HHMMSS-<4hexchars>`.
- `class Job` with at least:
  - `Job.create(meta: dict) -> Job` — makes `jobs/<id>/` and `jobs/<id>/input/`
    and `jobs/<id>/logs/`, writes initial `job.json`.
  - properties returning paths: `dir`, `input_dir`, `logs_dir`,
    `raw_md`, `clean_md`, `extracted_txt`, `final_html`, `final_pdf`,
    `validation_json`, `manifest`.
  - `save_text(path: Path, text: str)`, `save_upload(file) -> Path`.
  - `update(**fields)` — merge into manifest and re-write `job.json`.
  - `set_status(status: str, error: str | None = None)`.
- Fixed artifact filenames inside `jobs/<id>/`:
  `job.json`, `input/…`, `extracted.txt`, `raw.md`, `clean.md`,
  `final.html`, `final.pdf`, `validation.json`, `logs/render.log`,
  `logs/repair.log`.
- `job.json` fields: `id, created_at, path_mode ("generate"|"have_markdown"),
  input_type, purpose, style, provider, model, output_type, status, error,
  timings{}`.

### `input_handler.py`
Normalises the three input kinds into "we have a starting artifact + we know
whether extraction is needed".
- `accept_uploads(job: Job, files) -> list[Path]` — save originals to `input/`.
- `accept_paste(job: Job, text: str) -> Path` — save as `input/pasted.md`.
- `needs_extraction(path: Path) -> bool` — True for pdf/docx/pptx/txt; False for md.

### `text_extractor.py` (port from `build_guide.py`)
- `extract_text(path: Path) -> str` — handles `.md/.markdown/.txt/.pdf/.docx/.pptx`
  (PyMuPDF, python-docx, python-pptx). Raise `ValueError` on unsupported types.
- `clean_text(text: str) -> str`.
- `chunk_text(text: str, max_chars: int) -> list[str]`.

### `orchestrator.py`
Turns user choices + source text into messages, calls the LLM, returns raw md.
- `load_template(purpose: str, style: str) -> str` — reads
  `prompts/<purpose>/<style>.md`. Raise a clear error if missing.
- `build_messages(template: str, source: str, *, title: str, mode: str,
  chunk_note: str = "") -> list[dict]` — system from `prompts/_system.md`;
  user from the template with `{title}`, `{source}`, `{mode}` substituted.
  **Templates are stubs; just load and substitute whatever is in them.**
- `generate_guide(job: Job, source: str, *, purpose, style, provider, title) -> str`
  — single-shot if `len(source) <= CHUNK_CHARS`; otherwise chunk → generate per
  chunk → merge (port the merge idea from `build_guide.py`, keep it simple).
  Writes the result to `job.raw_md`.

### `llm_client.py`
One OpenAI-compatible client for every provider.
- `get_client(provider: str) -> openai.OpenAI` — builds from `config` provider entry.
- `complete(provider: str, messages: list[dict], *, temperature: float = 0.2) -> str`.
- No streaming needed for v1. No provider-specific subclasses.

### `markdown_sanitizer.py` — **STUB**
```python
def sanitize(text: str) -> str:
    # TODO(human): real two-phase math/markdown sanitizer is provided by hand.
    return text
```

### `math_validator.py`
Thin wrapper over `render/validate_math.js --json`.
- `@dataclass` `MathError(expr: str, display_mode: bool, message: str)`.
- `@dataclass` `ValidationResult(ok: bool, errors: list[MathError],
  display_blocks: int, inline_formulas: int)`.
- `validate(md_path: Path) -> ValidationResult` — run node, parse the JSON,
  write the raw JSON to `job.validation_json` (caller passes the path or you
  return it and the caller saves). If `node` is missing, return `ok=True` with a
  logged warning (do not hard-fail the pipeline on a missing validator).

### `auto_repair.py` — **STUB**
```python
def repair(text: str, errors: list, *, allow_llm: bool, llm_call=None) -> str:
    # TODO(human): regex-first → revalidate → bounded LLM fallback.
    return text
```
Define the signature exactly as above so the real version slots in. No logic.

### `pdf_renderer.py`
Mechanics only. **No visual styling in this file.**
- `render(clean_md: Path, css_path: Path, *, out_html: Path, out_pdf: Path,
  page_format: str = "A4") -> None`.
- Step 1: `node render/md_to_html.js <clean_md> <css_path> <out_html>` →
  writes a **standalone** HTML file: KaTeX-rendered math, `<style>` containing
  the embedded contents of `katex.min.css` **and** the template CSS, GFM tables
  enabled. (Embed CSS inline so Chromium needs no external file resolution.)
- Step 2: Playwright → launch chromium → `page.goto("file://"+out_html)` →
  wait for `networkidle` and `document.fonts.ready` → `page.pdf(path=out_pdf,
  format=page_format, print_background=True, margin=...)`.
  `print_background=True` is mandatory (the inline-code pills are CSS
  backgrounds and vanish without it).
- Log both steps to `job.logs_dir/render.log`.

### `render/md_to_html.js`
- Use `markdown-it` with tables enabled + a dollar-delimiter KaTeX plugin
  (suggested: `markdown-it-texmath` paired with `katex`; confirm it renders
  both `$…$` inline and `$$…$$` display). Read `katex.min.css` from
  `node_modules/katex/dist/`.
- Args: `<input.md> <template.css> <output.html>`.
- Emit one self-contained HTML document; embed both CSS sources in a single
  `<style>` block; wrap body content in `<main class="guide">…</main>`.

### `app.py` (Streamlit)
- Wizard driven by `st.session_state` (Streamlit re-runs top-to-bottom every
  interaction — persist all choices/results in session_state or they vanish).
- Steps: pick path (have-markdown vs generate) → input (upload / paste / md
  file) → options (purpose, style, provider, output type: md|pdf|both) → Run.
- On Run: create a `Job`, drive the pipeline (see §5), show progress, then offer
  downloads of `clean.md` and/or `final.pdf` and a link to the job folder.
- For the **skeleton**, fully wire **Path D** (upload `.md`). Wire C/A/B as the
  pipeline functions become available; gate A/B behind "provider configured".

---

## 5. Pipeline order (the single function every path funnels into)

```
create Job
  → (generate path) extract_text → orchestrator.generate_guide → raw.md
  → (have-md path)  save input as raw.md
  → sanitize(raw.md) → clean.md
  → validate(clean.md) → validation.json
  → if not ok and repair allowed: auto_repair → re-sanitize → re-validate (bounded)
  → pdf_renderer.render(clean.md, css) → final.html + final.pdf
  → copy final.pdf to output/, set_status("done")
```
Every stage updates the manifest status and writes its artifact before the next
stage runs, so a crash leaves a debuggable job folder.

---

## 6. Build phases (do them in this order)

1. **Skeleton MVP — Path D end to end with stubs.** Upload `.md` → passthrough
   sanitize → validate → render → PDF + job artifacts. Stubs are passthrough so
   this runs and produces a real (if unstyled) PDF on first launch.
2. **Path C** — paste textarea → save as `raw.md` → identical downstream.
3. **Path A (DeepSeek)** — wire `llm_client` + `orchestrator`; provider=deepseek.
4. **Path B (local)** — same code, provider=local (base_url swap). Trivial.
5. Leave the repair LLM-fallback wiring as a no-op call into the stub; the human
   fills `auto_repair.py` later.

Do not start phase N+1 until phase N runs clean.

---

## 7. Dependencies

**Node** (`package.json`): `markdown-it`, `katex`, a KaTeX markdown-it plugin
(`markdown-it-texmath` suggested). Node + npm assumed present on the system.

**Python** (`requirements.txt`):
```
openai>=1.30.0
pymupdf>=1.24.0
python-docx>=1.1.0
python-pptx>=0.6.23
rich>=13.7.0
streamlit>=1.36.0
playwright>=1.44.0
```
After install, Chromium is fetched once with `playwright install chromium`
(document this in the README, fish-shell). **Do not add** pandas, numpy,
langchain, or any LaTeX/Pandoc tooling.

---

## 8. Conventions

- Python 3.11+, type hints everywhere, `pathlib.Path` over string paths.
- Config via env + `config.py`; never hardcode secrets or URLs in modules.
- Logging: write per-stage logs into the job's `logs/`; use `rich` for any
  console output. Keep functions pure where practical (I/O at the edges).
- Fail loudly with clear messages; never swallow an exception silently — write
  it to the manifest `error` field and the relevant log.
- Any shell command you put in README/comments is **fish**.
- Keep the diff reviewable: small modules, no clever metaprogramming.

---

## 9. Skeleton acceptance check

The skeleton is "done" when:
- `streamlit run app.py` launches without error.
- Uploading a `.md` produces a `final.pdf` and a complete `jobs/<id>/` folder
  containing `job.json`, `raw.md`, `clean.md`, `final.html`, `final.pdf`,
  `validation.json`, and `logs/render.log`.
- The four STUB files exist, are passthrough, and carry `# TODO(human)` /
  `<!-- TODO(human) -->` markers.
- No Pandoc/XeLaTeX/LaTeX reference exists anywhere in the tree.
- `render/validate_math.js --json` prints valid JSON.

Stop after the skeleton + Path C and report. The human supplies the four
hand-written pieces (sanitizer, auto-repair, theme CSS, prompt templates)
before A/B are exercised for real.
