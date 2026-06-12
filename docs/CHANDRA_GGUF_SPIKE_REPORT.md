# CHANDRA_GGUF_SPIKE_REPORT.md — Slice 41 (hands-on)

> **Spike / report slice.** This is a *hands-on* feasibility spike that actually
> downloaded, converted, and ran **Chandra OCR 2** as GGUF through the
> `llama.cpp` / `llama-server` path on local hardware. It is **not** an app
> integration. No app code, routing, extraction, prompt, render, UI, provider, or
> `visual_assets_manifest.json` schema was changed. No model files, weights,
> `mmproj`, screenshots, OCR dumps, or bulky logs are committed to the repo — all
> artifacts live in a throwaway workspace **outside** the repository.
>
> Follows Slice 39 (`docs/CHANDRA_OCR_VERIFICATION.md`), which gated Chandra as
> "promising but not implementation-approved", and Slice 40 (local `fitz` figure
> extraction into the manifest), which gave this spike a real manifest target.

---

## 0. Summary verdict

**PROCEED TO PROVIDER DESIGN** — gated behind the existing Local Model Manager /
`llama-server` path, plus a small build/packaging step and an output-normalisation
slice. This is a **strong pass**.

Chandra OCR 2, quantised to GGUF, **loads and runs OCR through the exact path the
Local Model Manager already drives (`llama-server` + `--mmproj`)**, on the local
**RTX 5070 Ti 16 GB**, and produced **near-perfect, richly-structured output**
(layout-labelled HTML with **bounding boxes**, HTML tables, LaTeX math, and
diagram regions) on hand-checked pages — even at **Q4_K_M**. VRAM is **not** the
blocker (≈ 5.4–7.3 GB used). The real friction is operational, not capability:

- The only **public** Chandra GGUF (`hyojk2001/...`) is a **text-only**
  `gguf-my-repo` conversion with **no `mmproj`** → cannot do image OCR as-is.
  The vision projector had to be **generated locally** from the official weights.
- Generating the `mmproj` requires a **recent `llama.cpp`** (the `qwen3_5`→`qwen3vl`
  mmproj exporter) and a one-time **~10.6 GB** download of the official model.
- Output format is **prompt/template-sensitive** (bbox-rich vs plain HTML).
- Long-deck throughput is **batch-acceptable, not interactive**.

None of these are dealbreakers for a single-operator local-OCR provider, but they
shape the next slice (see §6).

---

## 1. Environment

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 5070 Ti, **16 GB** (16303 MiB), driver 610.43.02 |
| OS | Linux x86_64 |
| `llama.cpp` build | **9307** (commit `549b9d8…`), CUDA, GNU 16.1.1 |
| Binaries used | `llama-server`, `llama-mtmd-cli`, `llama-quantize`, convert tooling at the matching commit |
| Model (official) | `datalab-to/chandra-ocr-2` — arch **`Qwen3_5ForConditionalGeneration`** (`model_type: qwen3_5`), image-text-to-text OCR, license `openrail`, **n_ctx_train = 262144 (256K)**, ~10.59 GB bf16 weights |
| Community GGUF | `hyojk2001/chandra-ocr-2-Q4_K_M-GGUF` — **text decoder only, NO mmproj** (made with `gguf-my-repo`) |

> **Provenance note:** the community GGUF is an automated third-party conversion,
> **not** an official Datalab distribution, and ships **only the text decoder**.
> All OCR results below use a **self-generated `mmproj` + self-generated text
> quants** produced from the **official** `datalab-to/chandra-ocr-2` weights with
> the `llama.cpp` convert tooling at build 9307's commit.

### `llama.cpp` architecture support (checkpoint 2)
`libllama` (build 9307) ships loaders for `qwen35`, `qwen35moe` (text) **and**
`qwen3vl`, `qwen3vlmoe` (vision). The convert tooling's `MMPROJ_MODEL_MAP` routes
`Qwen3_5ForConditionalGeneration → qwen3vl`, so this build **can export a Chandra
`mmproj`**. Older builds without this mapping would fail — **version-sensitive**.

---

## 2. Artifacts produced (in throwaway workspace, NOT in repo)

| File | Size | Notes |
|---|---|---|
| `mmproj-chandra-f16.gguf` | ~676 MB | 298 vision tensors (`v.blk.*`, `mm.0/mm.2`, `patch_embd`, `position_embd`) via qwen3vl path |
| `chandra-text-q4_k_m.gguf` | 3.0 GB | quantised from local f16 |
| `chandra-text-q5_k_m.gguf` | 3.4 GB | quantised from local f16 |
| `chandra-text-q8_0.gguf` | 5.0 GB | direct convert `--outtype q8_0` |
| `chandra-text-f16.gguf` | 9.3 GB | quantise source (intermediate) |

Both conversions (`--mmproj` and text) **succeeded cleanly** with build 9307's
tooling (checkpoint 3).

---

## 3. Results

### 3.1 Load (checkpoint 3) — **success**
- `llama-mtmd-cli` and `llama-server` both load **text GGUF + `--mmproj`** with
  full GPU offload (`-ngl 99`), `-c 8192`.
- `llama-server` reports `loaded multimodal model` and serves `/health → ok`.
- mmproj worst-case memory ≈ 892 MiB.

### 3.2 Image input (checkpoint 4) — **success, both paths**
- `llama-mtmd-cli --image <png>` → OCR works.
- **`llama-server` OpenAI-compatible** `POST /v1/chat/completions` with
  `image_url: data:image/png;base64,…` → **works** (this is the path the LMM /
  Ask-style clients would use). Real OCR, **not** generic hallucinated chat.

### 3.3 Gold / reference quality (checkpoint 5) — **near-perfect**
Three synthetic, **non-private**, hand-checkable pages (reference written by hand
before comparison). All three transcribed essentially exactly:

| Page | Result vs hand reference |
|---|---|
| **p1 — text + equation** | Title → `Section-Header h1`; all 5 lines verbatim; chemistry equation rendered as **LaTeX** (`6 \text{ CO}_2 + … \rightarrow …`). Each block carried a `data-bbox` + `data-label`. |
| **p2 — table + math** | Full **HTML `<table>`** reconstructed exactly (Quantity/Symbol/SI Unit · Velocity v m/s · Acceleration a m/s² · Force F N); 4 equations as `<math display="block">` `Equation-Block`s; all with bbox. |
| **p3 — diagram/slide** | Title h1; a **`data-label="Diagram"`** region (with bbox) carrying an alt-text caption, a Mermaid-style `graph LR` of the arrow flow, and a correct bulleted description of the arrows. |

The native output format is **layout-labelled HTML with `data-bbox="x y x2 y2"`
and `data-label` classes** (`Section-Header`, `Text`, `Table`, `Equation-Block`,
`Diagram`, …) — i.e. text **and** structure **and** coordinates in one pass.

### 3.4 Quant comparison (checkpoint 6)
Same p2 page, full GPU offload, `--temp 0`:

| Quant | Output quality | Wall (cold, incl. load) | Peak VRAM |
|---|---|---|---|
| **Q4_K_M** | Near-identical, accurate (bbox ±1px) | ~3.9 s | **~5.4 GB** |
| **Q5_K_M** | Identical/accurate | ~3.8 s | ~5.8 GB |
| **Q8_0** | Identical/accurate | ~4.7 s | ~7.2 GB |

Quality held **even at Q4_K_M** on these pages — they do **not** disagree with each
other only by coincidence; each was checked against the hand reference. VRAM is
comfortable on 16 GB for all quants; Q4/Q5 leave large headroom for context.

### 3.5 Throughput (checkpoint 8) — **batch-acceptable**
- Warm `llama-server`: **~121 generated tok/s** (440 tok in 3.6 s); cold
  `mtmd-cli` ~50 tok/s incl. model load.
- Per page ≈ image-encode + a few hundred output tokens ≈ **~3–7 s/page warm**
  → roughly **~8–20 pages/min** depending on output length.
- Extrapolated (NOT run): a 500-page deck ≈ 25–60 min; 2000 pages ≈ 1.5–4 h.
  **Acceptable for offline/batch, not interactive.** Long decks were **not** run.
- Note: a load warning recommends `--image-min-tokens 1024` for reliable **bbox
  grounding**; raising image tokens improves grounding but **lowers** throughput and
  raises VRAM — a tunable trade-off, not yet swept here.

### 3.6 VRAM/RAM observations
- Idle baseline ~0.75 GB; resident server (Q8, 8K ctx, mmproj) ~7.3 GB; returns to
  baseline cleanly on stop (no leak). **VRAM is not the blocker** (consistent with
  Slice 39's prediction).

---

## 4. Fit with GuideForge

- **Existing path, no new service.** Runs on the **same `llama-server` binary the
  Local Model Manager already supervises**. The only additions vs a text-only
  local model are (a) loading a **`mmproj`** and (b) sending an **image message**.
  **No new companion/service is required**; the LMM boundary (companion owns host
  fs/process, backend bridges over the token-authed socket) is unaffected.
- **Output → `clean.md` source text.** The HTML/markdown + LaTeX math is directly
  usable as extracted source text (after a normalisation pass to the app's
  markdown/math conventions and the math sanitizer).
- **Output → `visual_assets_manifest.json`.** This is the strong fit: Chandra
  **natively emits `data-bbox` + `data-label`** regions — `Table`, `Equation-Block`,
  `Diagram`, figure/`Picture` regions, captions. These map onto the manifest's
  asset candidates (bbox, type, caption, structured table/equation payloads),
  complementing Slice 40's local `fitz` `extracted_figure` crops. **No schema
  change was made this slice** (forbidden); mapping design belongs to a later slice.
- **Companion/build wrinkle.** Because no public Chandra GGUF ships a `mmproj`, the
  app would need to **generate/ship the `mmproj`** (one-time, from official weights,
  with a compatible `llama.cpp`). This is a **packaging/build slice**, not a runtime
  service change.

---

## 5. Risks

1. **No turnkey GGUF.** Public Chandra GGUF is **text-only, no mmproj**; the
   working setup depends on a **self-generated mmproj** from the 10.6 GB official
   model. The app cannot just "point at an HF GGUF".
2. **Community-conversion accuracy.** Sidestepped here by converting from official
   weights; if a third-party GGUF were ever used, accuracy/provenance is unverified.
3. **Architecture/version sensitivity.** Requires a `llama.cpp` build with
   `qwen35` text + `qwen3vl` mmproj support (build 9307 ✓). Older builds fail to
   export/load. **Pin the build** in any provider design.
4. **Prompt/format sensitivity.** Default `mtmd-cli` produced rich bbox+labels;
   the server with a terse prompt produced plainer HTML. Reliable bbox/label output
   needs a **designed prompt/template** (and likely `--image-min-tokens 1024`).
5. **Throughput on long decks.** ~8–20 pages/min is fine for batch but would need
   the already-**deferred** async/batch large-PDF handling for big decks; never
   block interactive generation on it.
6. **License/commercial caveat.** `openrail` on the official weights and a
   third-party quantised base — fine for single-operator/local use; **review terms
   before any hosted/commercial use** (consistent with Slice 39's note).

---

## 6. Recommendation

**If it passes (it did) → next slice = a *design* slice for a `chandra_local` OCR
provider behind the LMM**, scoped as:

1. **mmproj/build slice** — a host-companion-side (not Docker-backend) procedure to
   produce/stage the `mmproj` + a chosen text quant (default **Q5_K_M** for the
   quality/VRAM balance; Q4_K_M as the low-VRAM option), with a **pinned llama.cpp
   build** requirement. No weights in the repo or image.
2. **Output-normalisation slice** — pure mapper from Chandra's layout-HTML
   (`data-bbox` + `data-label` + tables/math/diagrams) into (a) `clean.md` source
   text via the existing save/sanitize chokepoints and (b) **`visual_assets_manifest.json`
   asset candidates** — *reusing Slice 38/40's schema, not changing it*.
3. **Prompt/format slice** — lock a prompt/template that reliably yields the
   bbox+label form, with `--image-min-tokens` tuned for grounding.

**Fallback contract (must hold, unchanged):**
- **Chandra unavailable** (no mmproj / wrong build / no GPU) → fall back to the
  existing **Tesseract / `fitz`** local path.
- **Chandra bad output or timeout** → **degrade, never fail generation** (drop to
  embedded-text + `fitz` figures; the guide still builds).

Keep Chandra **off by default** and **local-only**, matching the Ask/LMM posture.

---

## 7. Reproducibility (sanitised — run outside the repo)

High-level steps (host paths/tokens intentionally omitted):

1. `hf download datalab-to/chandra-ocr-2` (≈10.6 GB; `HF_HUB_DISABLE_XET=1` was
   more reliable unauthenticated).
2. Convert with `llama.cpp` build-9307 tooling:
   `convert_hf_to_gguf.py <model_dir> --mmproj` → `mmproj-*.gguf`;
   `… --outtype q8_0` (and `--outtype f16` + `llama-quantize … Q4_K_M/Q5_K_M`).
3. CLI: `llama-mtmd-cli -m <text.gguf> --mmproj <mmproj.gguf> --image <png> -p "Convert this document page to markdown." -ngl 99 --temp 0`.
4. Server: `llama-server -m <text.gguf> --mmproj <mmproj.gguf> -ngl 99 -c 8192`
   then `POST /v1/chat/completions` with an `image_url` data-URI.

---

## 8. Scope / forbidden (honoured)

No app integration, provider, routing, extraction, prompt, render, UI, export, or
`visual_assets_manifest.json` schema change. No model files, weights, mmproj,
screenshots, OCR dumps, or bulky logs committed. No secrets, tokens, absolute host
paths, raw argv with sensitive paths, or private documents in this report. Test
inputs were **synthetic, non-private** pages.
