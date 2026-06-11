# CHANDRA_OCR_VERIFICATION.md — Local document-extraction prerequisite gate (Slice 39)

> **Docs-only verification.** This document evaluates **Chandra (Datalab)** as a
> *potential future* **high-quality local** OCR / document-extraction / visual-asset
> provider (`chandra_local`) for GuideForge. It implements nothing. **No** code,
> dependency, model download, provider setting, key, prompt, routing, extraction,
> render, or manifest-schema change is part of this slice, and **Chandra was not
> installed, cloned, built, or run.** Treat this as the prerequisite gate that must
> pass *before* a hands-on spike or any `chandra_local` implementation slice is
> designed — the Chandra equivalent of `MISTRAL_OCR_VERIFICATION.md` (Slice 35).
>
> **Status of facts:** gathered from official / primary Datalab sources (GitHub
> repo, Hugging Face model cards, the modified-OpenRAIL model license) in **June
> 2026** (see §10). Chandra is **actively iterated** — the current generation is
> **Chandra 2 (released 3/2026)**, distinct from the original 9B Chandra 1. Capability,
> parameter count, VRAM, throughput, and **license** all move — **re-confirm against
> live official sources at spike/implementation time.** The repo remains the source
> of truth for *our* side; the project's official docs/license govern *its*.
>
> **No secrets policy:** this document records source URLs and product facts only.
> It contains **no** keys, tokens, `Authorization` headers, companion tokens, socket
> paths, absolute host/model/executable paths, raw argv, unsafe full URLs, uploaded
> document paths, or document contents — and any future implementation must keep all
> of those off the public surface (see §3, §5, §6).

---

## 0. What "Chandra" is (and which artifact is which)

There are **two distinct Hugging Face model cards**, and conflating them produces
wrong feasibility conclusions:

| Artifact | What it is | Params | Weights license tag |
| --- | --- | --- | --- |
| `datalab-to/chandra` | **Chandra 1** (original, Oct 2025), repo version `0.1.0` | **9B** (BF16) | `openrail` |
| `datalab-to/chandra-ocr-2` | **Chandra 2** (current, **3/2026**) — the one we care about | **official count to RE-VERIFY** (earlier secondary write-ups said ~4B; a **community GGUF card reports 5B params / `qwen35` architecture**) | modified OpenRAIL-M |

- The pip package is **`chandra-ocr`**; the GitHub repo is **`datalab-to/chandra`**
  (same org as **Surya** / **Marker** / the **Datalab** hosted API).
- Throughout this doc, **"Chandra"/`chandra_local` means Chandra 2** unless a row
  explicitly refers to Chandra 1.
- **Parameter count — do not treat as settled.** Do **not** state "4B params" as an
  official fact: the v2 card/README does **not** pin a count, an earlier secondary
  write-up reported ~4B, and a **community `chandra-ocr-2-GGUF` conversion reports 5B
  params with a `qwen35` architecture**. The **official parameter count must be
  re-verified** against the Datalab card at spike time; community GGUF metadata is
  evidence, not the primary distribution.
- The decisive shift is still that Chandra 2 is **much smaller than Chandra 1's 9B**,
  and — newer than the original write-up — that a **quantized GGUF route now exists**
  that makes a 16 GB GPU look feasible (see §4).

---

## 1. Product / project status

- **Current generation:** **Chandra 2**, model id **`datalab-to/chandra-ocr-2`**,
  released **March 2026**. Chandra 1 (`datalab-to/chandra`, 9B, Oct 2025) is the
  prior generation and is **heavier** (see §4 — its own HF discussion says 16 GB is
  insufficient for it). Use **Chandra 2** as the reference.
- **Stability / lifecycle:** open-weights, **released** (not labelled experimental),
  with an installable pip package and active GitHub repo/releases/issues. It is a
  **moving** project — treat model id, param count, VRAM, throughput, and license as
  **subject to change** and re-verify before coding.
- **Maintainer:** **Datalab** (`datalab-to`), the team behind **Surya** (OCR / layout
  / reading-order / table recognition) and **Marker** (PDF→Markdown), and a hosted
  document-AI **API**. This matters for the license (§6): the weights are gated
  against **competing with Datalab's own API**.
- **Relevant names to pin:** package `chandra-ocr`; repo `datalab-to/chandra`; model
  `datalab-to/chandra-ocr-2`; **official serving** via **vLLM** (recommended) or
  **HuggingFace transformers** (`chandra-ocr[hf]`) — treat this official HF/Transformers/
  vLLM path as the **likely accuracy / reference baseline**, not merely the
  "completeness" option. **Community GGUF conversions** also exist —
  `noctrex/Chandra-OCR-GGUF` and **`prithivMLmods/chandra-ocr-2-GGUF`**, whose card
  reports **5B params / `qwen35`** and a quant ladder (Q4_K_M ≈ 3.07 GB … BF16/F16 ≈
  9.7 GB) plus **separate `mmproj` multimodal-projector files (≈ 367–676 MB)**. These are
  **third-party community GGUF conversions, NOT the primary official `datalab-to`
  distribution** — central to the feasibility picture (§4) but to be **re-verified before
  the spike**, since a community quant may **lag or diverge** from the official model.

---

## 2. Capabilities (what the official model card / README state)

**Officially stated** (Chandra 2 README / model card):

| Aspect | Finding (official) |
| --- | --- |
| **Inputs** | **PDFs and images.** |
| **Output formats** | **Markdown, HTML, or JSON "with detailed layout information."** |
| **Handwriting** | "Excellent handwriting support." |
| **Forms** | "Reconstructs forms accurately, including checkboxes" (and radio buttons per release notes). |
| **Tables / math / layout** | "Strong performance with tables, math, and complex layouts"; **multi-column** handled. |
| **Figures / images / diagrams** | "Extracts images and diagrams, and adds **captions** and **structured data**." |
| **Multilingual** | **90+ languages**; ~77.8% on an internal 43-language benchmark. |
| **Quality** | **olmOCR benchmark 85.9 ± 0.8** overall (ArXiv 90.2 / Math 89.3 / Tables 89.9) — reported state-of-the-art for its size. |

**Reported by the project / strongly implied by "JSON with detailed layout
information," but NOT itemized verbatim on the current model card/README — confirm
against the actual JSON schema in the hands-on spike:**

- **Per-block bounding boxes** and **typed layout blocks** (figure / diagram / image
  / table / caption / equation / chart / code / form …). The roadmap §6 asserts
  "bounding boxes on every block" and a typed-block taxonomy; the official README
  advertises **"json with detailed layout information"** and **"structured data,"**
  which is consistent with bboxes + typed blocks but does **not** enumerate them.
- **Flowcharts → Mermaid**, **chart/graph data extraction**, **math → LaTeX**, and
  **merged-cell tables.** These appear in secondary write-ups and the project's
  feature framing; the README states tables/math/diagram support generally but does
  **not** spell out Mermaid output, structured chart data, or `colspan`/`rowspan`.

> **Honest gap vs. our roadmap.** `docs/VISION_ROADMAP.md` §6 lists the rich
> Mermaid/chart-data/LaTeX/typed-block/bbox set as if confirmed. The **official**
> surface confirms structured **MD/HTML/JSON-with-layout**, image+diagram extraction
> **with captions and structured data**, tables, math, forms, handwriting, and
> multi-column — but the **exact** JSON field names, the typed-block vocabulary, the
> presence of per-block bboxes, and Mermaid/chart-data output must be **verified from
> the real JSON output** during the spike (§8/§9). The capability story is **very
> promising and directionally as the roadmap describes**, but the precise schema is
> the thing that makes or breaks the `visual_assets_manifest.json` mapping (§3), so it
> must not be assumed.

---

## 3. Fit with GuideForge architecture

The good news, as with Mistral: **Slices 32–38 already built the seams**, and
Chandra's JSON-with-layout output is a *better* structural fit for the visual pillar
than anything local today.

**How Chandra output maps into `visual_assets_manifest.json` (Slice 38 boundary):**
the manifest was deliberately designed (Slice 36 §5 / Slice 38) for the **rich**
provider case while only `fitz_local` populates it today. A future `chandra_local`
path would, **per page/block** that Chandra reports as a visual:

- set `source_provider: "chandra_local"` (already a **reserved-but-not-emitted**
  token in `pipeline/visual_assets_manifest.py`);
- promote `asset_type` from the current single `page_visual_signal` to the
  **reserved-for-later** real types (`extracted_figure` / `table_region` /
  `cropped_region` / `decorative` …) keyed off Chandra's typed blocks;
- populate the today-null fields the schema already carries: real **`bbox`** (from
  Chandra's per-block coordinates), **`caption`** (Chandra emits captions),
  **`scores`** and **`recommended_action`** (set later by V3 candidate scoring, not
  by Chandra directly), `dedupe_group` (V2).

Because the manifest record shape (`asset_id`, `source_page`, `asset_type`, `bbox`,
`caption`, `source_provider`, `recommended_action`, `dedupe_group`, `scores`,
`signals`, `warnings`) was **shaped for this case from day one**, adding Chandra is a
**populate-existing-fields + widen-closed-vocab** change, **not** a schema rebuild —
exactly the payoff Slice 38 was designed to bank.

**What kind of provider is Chandra? — all three at once.** It is simultaneously an
**OCR provider** (image/scan → text), a **document-extraction provider** (layout,
tables, forms, reading order → MD/HTML), and a **visual-asset-extraction provider**
(typed figure/diagram/chart blocks with bboxes + captions). That breadth is why it
does **not** cleanly fit *only* the Slice 32 `OcrProvider` contract.

**Which boundary should it sit behind?**

- The **Slice 32 OCR provider boundary** (`pipeline/ocr_provider.py`: stable
  `provider_id`, availability probe `(ready, reason)`, per-page `ocr_page →
  OcrResult`, safe **category-token-only** warnings) is the right home for Chandra's
  **text/OCR** output and is the cleanest first integration — Chandra can be "a better
  local OCR engine than Tesseract" behind the existing contract, with its visual
  output ignored at first.
- But Chandra's **typed-block / bbox / caption** output exceeds what `OcrResult`
  carries. The honest conclusion: **Chandra should be modeled as a new future
  *document/visual-extraction* provider boundary that *feeds the
  `visual_assets_manifest.json` (Slice 38)*,** while *also* being usable as a richer
  local OCR engine behind the Slice 32 contract. Practically: **start behind Slice 32
  for text (drop-in Tesseract upgrade), then add a manifest-feeding extraction path**
  — not one monolithic provider.
- **Mode wiring (Slice 37):** `chandra_local` is the engine that makes the
  **`local_private`** mode genuinely high-quality. It needs **no `allow_cloud_ocr`,
  no consent prompt, no cost estimate** — nothing leaves the box — so it slots under
  the existing local-first default without touching the cloud opt-in machinery.

**Coexistence with the other engines:**

- `tesseract_local` — **stays the always-available floor / fallback.** Chandra
  unavailable (no GPU / not installed / load failure / timeout) ⇒ degrade to
  Tesseract, never fail a generation (§5).
- `fitz_local` — **stays the cheap, dependency-free signal source** that populates
  the manifest today and on CPU-only / non-GPU machines. Chandra is the **rich
  upgrade** where a capable GPU exists; fitz is the universal baseline.
- `mistral_ocr` — the **cloud** rich path (Slice 35, per-page priced, opt-in). Chandra
  is its **local, privacy-clean, zero-API-cost counterpart** for GPU users. Both map
  into the same manifest; they are alternative populators of the same boundary, chosen
  by **mode** (Local/Private vs Smart Cloud Assist).

**Must remain off the public surface (DTOs/UI/logs/artifacts/exports), mirroring the
LMM whitelisting + provider-settings posture:** absolute host model/weights paths,
executable paths, the vLLM/transformers server URL/port/socket, raw argv, any
companion token, raw model/runtime error strings, and uploaded-document paths. The
public surface gets only **derived, non-secret** info (e.g. `configured` /
`available` / `provider_id` / safe category tokens) — the same rule already enforced
for `OcrResult`, the manifest's closed vocab, and the LMM DTOs.

---

## 4. Hardware feasibility on the target GPU (RTX 5070 Ti 16 GB)

**New GGUF evidence changes this answer.** The earlier verdict was
"uncertain-but-promising / unconfirmed at 16 GB." With a community **`chandra-ocr-2-GGUF`**
quant ladder now in hand, the honest answer is **"GGUF-quantized Chandra 2 appears
likely feasible on 16 GB VRAM — VRAM is probably no longer the primary blocker; the
real risks have moved to multimodal `llama.cpp` support, `mmproj` loading, OCR quality,
throughput, and long-document behavior."**

| Fact | Source | Implication for 16 GB |
| --- | --- | --- |
| Chandra **1 = 9B**; maintainer states **18 GB+** needed **unquantized**; Kaggle 16 GB GPUs reported **insufficient** (users saw ~36 GB demand) | Chandra 1 HF discussion #3 | **Chandra 1 does NOT fit 16 GB.** Do not target v1. |
| Chandra **2** — **official param count to re-verify** (secondary write-up said ~4B; community GGUF card reports **5B / `qwen35`**) — "smaller and more accurate than Chandra 1 across every category" | GitHub README summary / secondary / community GGUF card | Substantially smaller than v1 ⇒ 16 GB becomes **plausible** even before quantization, but the official card **states no VRAM number** and the **count itself is unsettled** (§0). |
| **Community `chandra-ocr-2-GGUF` quant ladder** (third-party): **Q4_K_M ≈ 3.07 GB · Q5_K_M ≈ 3.51 GB · Q6_K ≈ 3.99 GB · Q8_0 ≈ 5.16 GB · BF16/F16 ≈ 9.7 GB**, plus **separate `mmproj` files ≈ 367–676 MB** by precision | Community `chandra-ocr-2-GGUF` model card | **The decisive new fact.** Even the largest weights (BF16 ≈ 9.7 GB) + `mmproj` (≤ ~0.7 GB) leave headroom under 16 GB for KV cache + image tensors; **Q4/Q5/Q8 fit comfortably.** GGUF-quantized v2 **appears likely feasible on 16 GB** — community GGUF, not official. |
| One secondary test: **~18.9 GB** used on an **RTX 5090 (32 GB)** processing a large multi-hundred-page PDF | secondary write-up / discussion | That figure is for an **unquantized / high-concurrency** run; it **does not bound a quantized single-stream GGUF** run. Still a reminder that batch/concurrency/KV cache/image resolution drive memory. |
| Maintainer mitigations: use **vLLM** or **flash-attention** to reduce memory; suggested lighter models (Docling/Paddle) for GPU-constrained setups | Chandra 1 HF discussion #3 | Memory is **tunable** (precision, attention impl, concurrency, max image size). With GGUF on the table, the open question is **whether `llama.cpp`/`llama-server` supports this model's multimodal path + `mmproj`**, not whether the weights fit. |

**Throughput (official):** **1.44 pages/sec** on a **single NVIDIA H100 80 GB** with
vLLM at **96 concurrent sequences**; **~2 pages/sec** "real-world" estimate. The
H100 is far above an RTX 5070 Ti, and that number is at **high concurrency** the
16 GB card cannot match, so **expect materially lower pages/sec on the 5070 Ti** —
plausibly **a fraction of 1 page/sec** at low concurrency. For a 500–2,000-page
course pack that implies **tens of minutes to over an hour** of GPU time per large
deck — usable for a single-operator batch job, **not** interactive.

**Verdict for RTX 5070 Ti 16 GB:** **GGUF-quantized Chandra OCR 2 appears likely
feasible on the RTX 5070 Ti 16 GB. VRAM is likely not the main blocker. The main
blockers are multimodal `llama.cpp` support, `mmproj` loading, OCR quality, throughput,
long-document behavior, and integration stability.** Chandra 2 is the only viable target
(v1's 9B is out). The community `prithivMLmods/chandra-ocr-2-GGUF` ladder puts every
quant (Q4_K_M ≈ 3.07 GB through Q8_0 ≈ 5.16 GB, even BF16 ≈ 9.7 GB) plus its `mmproj`
(≤ ~0.7 GB) **under 16 GB with room for KV cache + image tensors**, so **Q4/Q5/Q8
especially look comfortable.** Spelled out, the remaining blockers have **moved off
VRAM** and onto:
(a) whether **multimodal `llama.cpp` / `llama-server`** actually supports this `qwen35`
multimodal model and loads its **`mmproj`**; (b) **OCR/output quality** of the quantized
weights vs the official vLLM/HF distribution; (c) **throughput**; (d) **long-document
operational behavior** (OOM/leak/timeout on 500–2,000-page decks); and (e) **integration
stability** of the GGUF/`llama-server` path under the existing LMM machinery. **Throughput caveat stands:** the
official **1.44 pages/s is an H100-at-96-concurrency** figure, so a single consumer GPU
at low concurrency will do **materially less** — a **500–2,000-page deck may still be
slow** (tens of minutes to over an hour of GPU time), usable for a single-operator batch
job but not interactive. All of this **must** be settled by the hands-on spike (§8)
before committing to build Local mode around it.

---

## 5. Operational complexity

- **Two install/serve paths — pick by spike result, not assumption:**
  - **Official / reference path:** `pip install chandra-ocr` (**vLLM** backend,
    recommended) or `chandra-ocr[hf]` (**HuggingFace transformers**), driven via
    Chandra's **CLI / server**. This is the **blessed, highest-fidelity** distribution —
    **treat it as the likely accuracy / reference baseline** against which any quantized
    output is judged — but it needs a heavy **CUDA torch / vLLM GPU runtime**,
    **heavyweight** relative to the rest of GuideForge, and likely **its own GPU
    service** (see below).
  - **Practical first-spike path:** the **community `prithivMLmods/chandra-ocr-2-GGUF`**
    quant through the **existing `llama.cpp` / `llama-server` / Local Model Manager**
    pattern GuideForge already uses for local LLMs. **If multimodal `llama-server`
    support works** (model + `mmproj` load, image input → markdown), this path could
    **avoid building a new heavy vLLM service** and instead **reuse the LMM
    `llama-server` lifecycle** — a much lighter integration. **Do not assume it works
    until tested:** GGUF conversion/quantization can degrade OCR quality even if it
    loads, and the community quant may lag/diverge from the official model.
  - **Decision rule:** prefer the **GGUF/`llama-server` path for the first hands-on
    checkpoint** because it reuses existing machinery; fall back to the official vLLM/HF
    service if multimodal `llama.cpp` support proves inadequate — and **always validate
    GGUF quality against the official/reference output, not just quant-vs-quant.**
- **Docker / GPU implications:** the committed app is a **non-root, no-GPU,
  same-origin** FastAPI+SPA container. Chandra needs **GPU access** (NVIDIA Container
  Toolkit / `--gpus`), a large CUDA image, and several GB of **model weights**. Baking
  it into the main image is **out of the question** — it would bloat the image, break
  the non-root/no-GPU posture, and couple the web tier to a GPU. Chandra must run as a
  **separate GPU service/process**, exactly like the local LLM lifecycle is kept out
  of the backend.
- **Best architectural fit = the existing Local Model Manager host-companion
  pattern** (`tools/local_model_companion/`): the **host** owns GPU/process/filesystem
  access and exposes a **token-authed Unix-socket bridge**; the Docker backend
  **bridges** over it and **never** starts host processes or browses the host
  filesystem directly. How heavy this is **depends on which path the spike validates:**
  - **GGUF / `llama-server` path (lighter, preferred to try first):** if multimodal
    `llama-server` can load Chandra GGUF + `mmproj`, this is **a near-reuse of the
    existing LMM `llama-server` lifecycle** — potentially **no brand-new companion
    capability**, just feeding a different (multimodal) model through the path already
    built and hardened in Phase 2.
  - **Official vLLM/HF path (heavier):** the torch/vLLM service is **heavier than the
    llama.cpp/`llama-server` case** the companion was built for (larger runtime,
    GPU scheduling), so it likely needs **its own companion capability / service
    manager** (a "Chandra service" lifecycle), not a trivial reuse.
  - Either way, the **LMM is PAUSED after Phase 2G11** and the **approve-root /
    packaging** work is explicitly **deferred**, so any new Chandra service capability
    is **downstream of, not part of, this verification** — but the GGUF path is
    attractive precisely because it may need **little or none** of that new work.
- **Failure / degrade strategy (non-negotiable, matches every advisory slice):**
  - Chandra **unavailable** (no GPU / not installed / companion down / weights
    missing) ⇒ availability probe returns `(False, reason)` ⇒ **fall back to
    Tesseract/fitz**, never fail generation.
  - Chandra **timeout / OOM / crash** ⇒ degrade to local fallback for the affected
    page(s); **never** kill or block the job.
  - **Oversized documents** ⇒ reuse the **Slice 33 shared page budget** + large-PDF
    preflight + page-range/queue; a 2,000-page deck must be chunked/budgeted, never
    fed whole into a 16 GB GPU.
  - All errors map to **safe category tokens** (`chandra_unavailable`,
    `chandra_timeout`, `chandra_oom`, `fell_back_local` …) — never raw runtime
    strings/paths.

---

## 6. License / commercial constraints (non-legal guidance)

Verified from the GitHub `MODEL_LICENSE` and the model cards (June 2026). **This is
engineering due-diligence, not legal advice — a real commercial product must get
license review from Datalab and/or counsel.**

- **Code:** **Apache 2.0** (permissive; no commercial restriction).
- **Model weights:** **"AI PUBS OPEN RAIL-M LICENSE (MODIFIED)"** — *not* a plain
  open license. Key terms verbatim-in-substance:
  - **Free for research and personal use.**
  - **Commercial use is gated by a size threshold:** you may **not** commercially
    deploy if you (or your employer / affiliated entity) had **> $2,000,000 gross
    revenue in the prior year** *or* raised **> $2,000,000 in total equity/debt
    funding** — unless your use is limited to research/personal purposes.
  - **Competitive-use prohibition:** you may not use it "for any purpose if You (your
    employer, or the entity you are affiliated with) **provides … any product or
    service that competes** with any product or service offered by … Licensor or any
    of its affiliates." Datalab **sells a document-AI OCR API** — so a product that is
    itself an OCR/document-extraction service competing with Datalab is **barred**,
    independent of the revenue threshold.
  - **Commercial / broader licenses** are available from Datalab (`https://www.datalab.to/`).
- **GuideForge personal / single-operator use:** **appears acceptable** — it is
  personal use, well under the $2M thresholds, and a *study-guide generator* is **not**
  an OCR/document-AI service competing with Datalab's API. **(Confirm at use time;
  this is not legal advice.)**
- **Multi-user / "help all students" / any monetized product:** **requires a license
  review before shipping.** Two independent hazards: (a) crossing the **$2M
  revenue/funding** threshold flips commercial use off; and (b) the **competitive-use**
  clause is the sharper risk — a hosted "upload your PDF, get OCR'd study material"
  product could plausibly be read as competing with Datalab's OCR API even *below* $2M.
  **Do not build a public/commercial GuideForge on `chandra_local` weights without
  Datalab's commercial license or explicit written clarification.**

> **Privacy/license interaction:** Chandra is **local**, so privacy is *better* than
> cloud (no third-party upload) — but the **license** is *stricter* than a typical
> permissive model. The two trade in opposite directions: Chandra removes the cloud
> privacy/consent problem entirely while adding a weights-license commercial gate.

---

## 7. Cost / privacy implications

- **No API cost.** Self-hosted ⇒ **zero per-page/API charge** — the opposite of
  Mistral's per-page billing. No `allow_cloud_ocr`, no dollar estimate, no consent
  surface needed.
- **No third-party upload in Local/Private mode.** Nothing leaves the box ⇒ Chandra is
  the **privacy-clean high-quality path** (Slice 36 §7: "Local/Private needs no
  disclaimer"). This is its single biggest strategic advantage over Mistral.
- **The real costs are operational, not financial:** **GPU time / electricity**, the
  heavyweight CUDA/vLLM runtime, model-weight storage, a separate GPU service to
  manage, and **throughput** (§4) on long decks. "Free" in dollars ≠ "free" in
  complexity.
- **Datalab also offers a hosted API.** **Do not design around it** in this slice —
  the whole point of `chandra_local` is *local*. If a cloud Chandra path is ever
  wanted, verify it **separately** (it would re-introduce the Mistral-style cost +
  privacy + consent considerations and the competitive-use license question head-on).

---

## 8. Suggested future hands-on spike (NOT this slice)

A throwaway, **uncommitted** spike — only after this gate passes — to settle the §4/§9
unknowns against the **Slice 38 manifest as the output target**. Now that GGUF evidence
makes VRAM look like a non-blocker, the **GGUF / `llama-server` path is the first thing
to try**, not vLLM.

Inputs: **one small synthetic PDF** + **one real course-deck sample** (incl. a
scanned / video-frame page and a table/figure/math page), plus **2–3 gold/reference
pages** with **manually known expected text/layout** so quality is judged against a
known-good baseline — **not** only quant-vs-quant.

**Run the spike checkpoints in this order — each gates the next:**

1. **Confirm the GGUF repo** (`prithivMLmods/chandra-ocr-2-GGUF`) actually has the model
   quant **and a matching `mmproj`** file.
2. **Confirm the current local `llama.cpp` / `llama-server` build supports this `qwen35`
   multimodal path** at all.
3. **Load** Chandra GGUF **+ `mmproj`**.
4. **Send a small image / page** through the **OpenAI-compatible image-message path**.
5. **Verify it returns real OCR / Markdown / HTML / JSON-like output** — not generic
   chat or hallucination.
6. **Run the 2–3 gold/reference pages** and compare output against the **manually known
   expected text/layout** (quality vs a known-good baseline, ideally also vs the
   official vLLM/HF reference output).
7. **Compare `Q4_K_M`, `Q5_K_M`, `Q8_0`** for **quality and speed**.
8. **Measure VRAM / host RAM, pages/minute, and timeout/crash behavior.**
9. **Check whether output maps cleanly into `visual_assets_manifest.json`** (the §3
   mapping) — per-block **bboxes**, **typed-block vocabulary**, **captions**, **Mermaid**,
   **chart data**, **merged-cell** tables. (GGUF output may differ from the official
   JSON-with-layout schema — confirm what the quantized path actually emits.)
10. **Confirm the fallback plan:** Chandra unavailable **or bad output** → Tesseract/fitz
    path; **never fail generation.**

- **Determinism check:** run the same page twice — is output stable enough for
  GuideForge's byte-stable expectations, or does it need normalization?
- **Do not commit** any model weights, `mmproj` files, large generated outputs, or the
  spike scaffold.

> **Measurement should be staged — don't conflate the two visual milestones:**
> - **After Slice 40 (local asset extraction):** test **asset existence, bbox validity,
>   deterministic ids, safe relative refs, caps, and duplicate/tiny-asset explosion
>   prevention.** Slice 40 only writes the **manifest / assets** — visual assets do
>   **not** reach the generated guide yet.
> - **After the asset-aware prompt/render slices:** test **orphan `{{figure}}` tokens,
>   unknown asset ids, duplicate figure inclusion, and visual coverage** in the rendered
>   guide.
>
> **Sequencing:** run the **Chandra hands-on spike shortly *after* Slice 40 — not in
> parallel with Slice 40's validation** — so a GPU/`llama-server` workload does not add
> noise to Slice 40's fresh extraction smoke test.

---

## 9. Risks and unknowns (confirm before any implementation)

1. **Actual VRAM for Chandra 2 at 16 GB** — **likely no longer the primary blocker**:
   the community GGUF ladder (Q4_K_M ≈ 3.07 GB … BF16 ≈ 9.7 GB) + `mmproj` (≤ ~0.7 GB)
   fits 16 GB with headroom. Still **measure (§8)** per quant, since concurrency / KV
   cache / image resolution can push it up; the old "exceeds 16 GB" data point was an
   unquantized/high-concurrency run.
2. **Multimodal `llama.cpp` / `llama-server` support + `mmproj` loading** — **the new
   top risk.** Does the current `llama-server` actually support this model's vision
   path and load its `mmproj`? If not, the lightweight GGUF route collapses back to the
   heavy official vLLM/HF service. **First spike checkpoint (§8).**
3. **OCR / output quality of the quantized GGUF weights** vs the official vLLM/HF
   distribution — quantization can degrade OCR fidelity; compare Q4/Q5/Q8 (§8).
4. **Actual throughput on RTX 5070 Ti** — official 1.44 pages/s is on an H100 at 96
   concurrency; expect far less. Is a 500–2,000-page deck tolerable?
5. **Exact JSON schema** — field names, typed-block taxonomy, presence of per-block
   bboxes, Mermaid/chart-data/LaTeX/merged-cell output. The §3 manifest mapping
   depends on this and it is **not pinned** from the README; the **GGUF path may emit a
   different format** than the official JSON-with-layout, so confirm both.
6. **Quality on real university slides / video-frame PDFs** — benchmark scores are on
   academic corpora; lecture decks differ.
7. **Robustness / memory behavior on 500–2,000-page decks** — long-run OOM/leak risk;
   throughput may still make large decks slow even though VRAM fits.
8. **Output determinism / stability** for a byte-stable pipeline.
9. **Safe chunking / page-range / budget** integration with Slice 33's shared budget
   and large-PDF preflight.
10. **Official parameter count is unsettled** — secondary write-up said ~4B, the
    community GGUF card reports **5B / `qwen35`**; the Datalab card pins no number.
    Re-verify before relying on any param/VRAM math (§0).
11. **License risk for any public/commercial product** — $2M thresholds **and** the
    competitive-use clause (§6). Needs Datalab review before monetizing.
12. **Quantization legitimacy** — the `chandra-ocr-2-GGUF` quant is community/
    third-party; official support, OCR-quality impact, and license coverage of
    quantized weights are unconfirmed. The license (modified OpenRAIL-M) most likely
    still governs the quantized weights — confirm at use time.
10. **Companion lifecycle weight** — Chandra is heavier than the GGUF `llama-server`
    case; it likely needs its own host-companion service capability (downstream of the
    paused LMM + deferred approve-root/packaging work).

---

## 10. Sources consulted (official / primary first)

Official Datalab / Chandra:
- Chandra GitHub repo (README, capabilities, install, throughput) — https://github.com/datalab-to/chandra
- Chandra releases — https://github.com/datalab-to/chandra/releases
- Chandra 2 model card — https://huggingface.co/datalab-to/chandra-ocr-2
- Chandra 1 model card (9B, prior gen) — https://huggingface.co/datalab-to/chandra
- VRAM / GPU-memory discussion (maintainer: 18 GB+ unquantized; 16 GB insufficient for v1) — https://huggingface.co/datalab-to/chandra/discussions/3
- Model weights license (`MODEL_LICENSE`, modified OpenRAIL-M, $2M thresholds, competitive-use clause) — https://github.com/datalab-to/chandra/blob/master/MODEL_LICENSE
- Datalab (org / commercial licensing / hosted API) — https://www.datalab.to/
- Related Datalab projects (corroboration): Surya — https://github.com/datalab-to/surya

Secondary / community (corroboration only — **not** authoritative for params, VRAM,
license, or schema):
- Community GGUF quant (third-party) — https://huggingface.co/noctrex/Chandra-OCR-GGUF
- Community **`prithivMLmods/chandra-ocr-2-GGUF`** conversion (third-party; reports
  **5B / `qwen35`**, the Q4_K_M ≈ 3.07 GB … BF16 ≈ 9.7 GB quant ladder, and separate
  `mmproj` ≈ 367–676 MB files) — https://huggingface.co/prithivMLmods/chandra-ocr-2-GGUF
  — **community GGUF evidence, not the official `datalab-to` distribution**; a community
  quant may lag/diverge from the official model, so **re-verify the repo contents, param
  count + license coverage before the spike**
- Towards AI write-up (param-count / base-model claims, treat as indicative) —
  https://pub.towardsai.net/chandra-ocr-2-the-open-source-model-that-reads-what-others-cant-6a218faa0efd
- DeepWiki install notes — https://deepwiki.com/datalab-to/chandra/2.1-installation

> Where official and secondary sources disagree (notably the **Chandra 2 parameter
> count** — secondary write-up ~4B vs community GGUF card **5B / `qwen35`**, with **no
> number pinned on the official card** — and the **VRAM at 16 GB**), **trust the
> official Datalab sources and re-verify live**, and treat the community GGUF facts
> (quant sizes, `mmproj`, architecture) as **strong but third-party evidence** to
> confirm in the hands-on spike (§8), not as the official distribution.

---

## 11. Recommendation

**`Proceed to hands-on GGUF spike after manifest schema` — with an explicit license
caveat for any multi-user / commercial use. This is still NOT approval to implement
Chandra as a provider.**

Rationale: Chandra **2** is a **released, well-maintained, open-weights, high-quality
local** document model whose **JSON-with-layout output is a strong structural fit** for
the `visual_assets_manifest.json` boundary that **Slice 38 already shipped** — so there
are **no architectural blockers**, and it is the **privacy-clean, zero-API-cost** way
to make Local/Private mode genuinely strong. **New GGUF evidence sharpens the picture:**
a community **`chandra-ocr-2-GGUF`** quant ladder (Q4_K_M ≈ 3.07 GB … BF16 ≈ 9.7 GB) +
`mmproj` (≤ ~0.7 GB) makes **16 GB VRAM look likely sufficient**, so the spike's job has
shifted from "does it even fit?" to "does the lightweight GGUF/`llama-server` path
work?" What remains **unconfirmed and gating** is no longer dominated by VRAM:

1. **Lightweight-path viability on the RTX 5070 Ti 16 GB** — VRAM is **probably no
   longer the blocker**; the open questions are **multimodal `llama.cpp`/`llama-server`
   support + `mmproj` loading**, **OCR quality of the quantized weights** (Q4/Q5/Q8),
   **throughput** (a 500–2,000-page deck may still be slow), and **long-document
   behavior**. This needs the **hands-on GGUF spike (§8)** — whose **first checkpoint**
   is simply: *can current `llama-server` load Chandra GGUF + `mmproj` and do image /
   PDF-page → markdown OCR?*
2. **License** is **fine for the personal / single-operator tool** but is a **real gate
   for any multi-user / monetized "help all students" product** — both the **$2M
   thresholds** and, more sharply, the **competitive-use clause** against Datalab's own
   OCR API. **Do not build a public/commercial product on Chandra weights without
   Datalab's commercial license / written clarification.** (The modified OpenRAIL-M
   weights license most likely still governs the community-quantized GGUF.)

This is therefore a **conditional go to *spike*, not a green light to *implement***. Do
not install, run, depend on, or wire Chandra into generation until the GGUF spike
settles the `llama-server`/`mmproj`/quality/throughput questions and maps a real sample
into the Slice 38 manifest, and (for anything beyond personal use) the license is cleared.

---

## 12. Proposed next slice

The slice order (`docs/VISION_ROADMAP.md` §9) does **not** require Chandra next — the
visual pillar can advance locally without it. Recommended sequencing:

- **Continue the local visual stack first:** **Slice 40 — local figure
  extraction / cropping into the manifest** (fitz rasterize regions + real bboxes —
  the first real extractor-output change, gated), then **V2 dedup** (Slice 41) and
  **V3 candidate scoring** (Slice 42). These deliver "don't reopen the slides" value on
  **any** machine (no GPU, no license question) and give the Chandra spike a concrete
  manifest target.
- **Shortly *after* Slice 40 (NOT in parallel with Slice 40's validation):** the
  **Chandra 2 hands-on GGUF feasibility spike (§8)** on the RTX 5070 Ti — throwaway,
  uncommitted, **trying the community `prithivMLmods/chandra-ocr-2-GGUF` via
  `llama-server` first** (first checkpoint: does `llama-server` load the GGUF + `mmproj`
  and OCR a page image?), measuring per-quant VRAM / throughput / output quality against
  a known-good reference and mapping a sample into the Slice 38 manifest; official
  vLLM/HF only as fallback. **Deliberately sequenced after Slice 40's fresh extraction
  smoke test** so a GPU/`llama-server` workload doesn't add noise to that validation.
  Its result **gates** whether `chandra_local` becomes a real provider and whether it
  can **reuse the existing LMM `llama-server` path** instead of a new GPU service.
- **Only if the spike passes:** a future **`chandra_local` provider design slice**
  (Slice 32 OCR contract for text + a manifest-feeding extraction path; host-companion
  service lifecycle design; server-side-only paths/URLs; degrade-to-Tesseract
  contract) — **disabled/unwired**, mirroring how Mistral is sequenced (Slice 43).

**Do not** install, download, run, or depend on Chandra, and do not build Local mode
around it, until the spike + (for non-personal use) the license review are done.
