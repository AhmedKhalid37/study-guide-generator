# Claude-style Study Guide Pipeline for CachyOS — v2

This pipeline converts course material into a clean, exam-focused study guide:

`PDF / DOCX / PPTX / TXT / MD -> extracted text -> LLM-generated guide -> Markdown sanitizer -> optional math validation -> PDF`

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
