# Claude-style Study Guide Pipeline for CachyOS — v2

This pipeline converts course material into a clean, exam-focused study guide:

`PDF / DOCX / PPTX / TXT / MD -> extracted text -> LLM-generated guide -> Markdown sanitizer -> optional math validation -> PDF`

Note: `legacy_scripts/` contains a backup copy of the old working pipeline
scripts as they existed before the Chrome renderer work.

## Streamlit MVP

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Install Node dependencies for KaTeX validation/rendering:

```bash
npm install
```

Chromium is required for Chrome/HTML PDF rendering. On CachyOS:

```bash
sudo pacman -S --needed chromium
```

Launch the app:

```bash
python -m streamlit run app.py
```

To test upload mode, launch the app and upload `ch4_raw.md`.

To test paste mode, paste this small example:

```md
# Paste Test

The formula is (z=\frac{x-\mu}{\sigma}).
```

Run math sanitizer/renderer regression tests:

```bash
python test_scripts/test_math_regressions.py
```

## CLI LLM Mode

The LLM path is CLI-first and uses one OpenAI-compatible client for hosted APIs
or local servers.

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your actual API key and model. Never commit `.env`; it is
ignored by git so secrets stay local.

For a local OpenAI-compatible server, point `LLM_BASE_URL` and `LLM_MODEL` at
that server instead.

Generate, sanitize, validate, and render from a text/Markdown source file:

```bash
python -m pipeline.run_llm_job \
  --source-file ch6_raw.md \
  --title "Chapter 6 Study Guide" \
  --mode exam
```

The command creates a `jobs/<job_id>/` folder containing `input/source.txt`,
`raw.md`, `clean.md`, `final.html`, `final.pdf`, logs, and `job.json`.

After `.env` is set, launch Streamlit normally:

```bash
python -m streamlit run app.py
```

Streamlit LLM mode supports DeepSeek and Qwen as hosted OpenAI-compatible
providers. Choose the provider, then choose one of its listed model IDs or use
the custom model ID field. Model overrides are per run only. `deepseek-v4-flash`
is the faster/cheaper DeepSeek style option; `deepseek-v4-pro` is the
better-quality style option.

For DeepSeek, set `DEEPSEEK_BASE_URL` and `DEEPSEEK_API_KEY`. The default
DeepSeek base URL is `https://api.deepseek.com/v1`.

For Qwen through Alibaba DashScope, Alibaba's official API key environment
variable is `DASHSCOPE_API_KEY`. The Qwen base URL is
`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`; set
`DASHSCOPE_BASE_URL` only if you need to override it. `QWEN_API_KEY` remains
available as a fallback, and `QWEN_MODEL` can set the environment-default model.
The app includes `qwen3.7-max` and `qwen3.6-plus` as Qwen model options. Qwen
thinking mode sends `extra_body={"enable_thinking": True}` with the
non-streaming chat completion request. Streaming is not implemented yet; the app
uses the final response only. `qwen3.6-plus` is currently added as a
text-generation model option. Actual visual/image understanding would require a
later image-upload/multimodal feature.

LLM mode also includes style presets. The default is `Basic study guide`; you
can switch per run to baby-step explanation, exam cram, MCQ training, final
solution, or Claude-style study guide. Each preset is a Markdown prompt in
`prompts/`.

Alternatively, launch Streamlit with provider environment variables using fish
shell:

```fish
set -x DEEPSEEK_BASE_URL "https://api.deepseek.com/v1"
set -x DEEPSEEK_API_KEY "your_deepseek_key_here"
set -x DEEPSEEK_MODEL_FLASH "deepseek-v4-flash"
set -x DASHSCOPE_BASE_URL "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
set -x DASHSCOPE_API_KEY "your_dashscope_key_here"
set -x QWEN_MODEL "qwen3.7-max"
set -x LLM_TEMPERATURE "0.2"
python -m streamlit run app.py
```

This v2 upgrade adds the most useful ideas from the second Claude run:

- a **math sanitizer** that repairs broken Markdown math
- display math conversion: `[ ... ]` blocks -> `$$ ... $$`
- inline math conversion: `(P(X=2))` -> `$P(X=2)$`
- balanced-parentheses scanning so nested formulas like `(P(X\ge1)=1-P(X=0))` work
- protection for display math blocks so inline scanning does not corrupt them
- currency escaping, e.g. `$70,000` -> `\$70,000`
- percent escaping inside math, e.g. `37.5%` -> `37.5\%`
- table-safe conditional probability bars: `P(A|B)` -> `P(A\mid B)`
- combinatorics prescript fixes: `_5C_2` -> `{}_5C_2`
- optional KaTeX validation to catch math rendering errors before PDF export

It is designed for your CachyOS + NVIDIA GPU setup and works with either:

1. a local OpenAI-compatible server such as `llama-server`, or
2. a hosted OpenAI-compatible API endpoint.

---

## 1. Install system dependencies on CachyOS

```bash
sudo pacman -Syu
sudo pacman -S --needed python python-pip python-virtualenv pandoc texlive-binextra texlive-latexrecommended texlive-fontsrecommended nodejs npm poppler
```

Optional OCR for scanned PDFs:

```bash
sudo pacman -S --needed tesseract tesseract-data-eng
```

---

## 2. Python setup

```bash
cd studyguide_pipeline_cachyos_v2
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Optional KaTeX validation:

```bash
npm install
```

---

## 3. Use with an API model

Set an OpenAI-compatible endpoint:

```bash
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="YOUR_KEY"
export LLM_MODEL="gpt-4.1"
```

Then run:

```bash
python scripts/build_guide.py input.pdf \
  --title "Chapter 5 — Discrete Probability Distributions" \
  --out output/chapter5.md \
  --mode exam \
  --validate-math
```

---

## 4. Use locally with your 5070 Ti

Build llama.cpp with CUDA:

```bash
git clone https://github.com/ggml-org/llama.cpp ~/projects/llama.cpp
cd ~/projects/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

Start a GGUF model:

```bash
bash scripts/run_llama_server.sh ~/models/YOUR_MODEL.gguf
```

In another terminal:

```bash
export LLM_BASE_URL="http://127.0.0.1:8080/v1"
export LLM_API_KEY="local"
export LLM_MODEL="local-model"
```

Generate:

```bash
python scripts/build_guide.py chapter.pdf \
  --title "Chapter 8 — Intrusion Detection" \
  --out output/chapter8.md \
  --mode exam \
  --validate-math
```

Recommended local models for a 16 GB GPU:

- Qwen2.5-14B-Instruct GGUF Q4/Q5
- Mistral-Small / Nemo-style instruct models in Q4/Q5
- 7B/8B instruct models if you want faster generation

For very long chapters, use chunked generation automatically handled by the script.

---

## 5. Sanitize existing Claude/ChatGPT Markdown only

Use this when you already have a study guide but formulas are broken:

```bash
python scripts/sanitize_markdown_math.py raw_guide.md clean_guide.md --validate
```

Example broken input:

```md
[
P(X\ge1)=1-P(X=0)
]

The mean is (\mu=np).
```

Clean output:

```md
$$
P(X\ge1)=1-P(X=0)
$$

The mean is $\mu=np$.
```

---

## 6. Convert Markdown to PDF

```bash
bash scripts/render_pdf.sh output/chapter5.md output/chapter5.pdf
```

The PDF renderer uses:

- `pandoc`
- `xelatex`
- `DejaVu Sans`
- Markdown dollar math

---

## 7. Best prompt style

The included prompt tries to reproduce the guide structure you liked:

- “What this chapter is about”
- simple explanations
- tables for comparisons
- formula section
- exam clues
- common mistakes
- memory hints
- final cheat sheet
- practice questions with answers

You can edit:

```text
prompts/study_guide_system.md
prompts/study_guide_user.md
```

---

## 8. Troubleshooting

### `--flash-attn` error

Newer `llama.cpp` expects:

```bash
-fa auto
```

or:

```bash
--flash-attn auto
```

This package uses `--flash-attn auto`.

### PDF font errors

Install the recommended TeX/font packages:

```bash
sudo pacman -S --needed texlive-binextra texlive-latexrecommended texlive-fontsrecommended ttf-dejavu
```

### Math validation fails

Run:

```bash
python scripts/sanitize_markdown_math.py raw.md clean.md --validate --show-math
```

Then fix the specific formula it reports.

---

## 9. Folder layout

```text
studyguide_pipeline_cachyos_v2/
├── scripts/
│   ├── build_guide.py
│   ├── sanitize_markdown_math.py
│   ├── validate_math.js
│   ├── render_pdf.sh
│   ├── run_llama_server.sh
│   └── setup_cachyos.sh
├── prompts/
│   ├── study_guide_system.md
│   └── study_guide_user.md
├── examples/
│   ├── example_command.txt
│   └── broken_math_example.md
├── requirements.txt
├── package.json
└── README.md
```
