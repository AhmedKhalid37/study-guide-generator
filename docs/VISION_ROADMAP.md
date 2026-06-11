# VISION_ROADMAP.md — Self-contained study guides (capability stack + phased plan)

> **Status: planning / design input.** This is a roadmap proposal, not a slice. It
> sits beside `docs/ROADMAP_INPUT_SUMMARY.md` and `docs/HYBRID_OCR_DESIGN.md` and is
> meant to be turned into small, verifiable slices in the project's established
> style: advisory-first, degrade-not-fail, local/private by default, server-side
> keys only, byte-identical output when a feature is unused, `clean.md` writes only
> via `JobManager.save_clean_md`, exact-name artifacts before generic lists.
>
> The **repo is the source of truth.** Every "today" claim below is grounded in
> `pipeline/extract.py`, `pipeline/orchestrator.py`, `pipeline/run_llm_job.py`, the
> renderers (`pdf_renderer.py` / `html_renderer.py` / `docx_renderer.py`), and OCR
> slices 29–35. Re-verify before implementing.
>
> **External-fact freshness.** Provider facts (Chandra, Mistral) were checked June
> 2026 against official sources and are summarized in §6. Re-verify capability,
> pricing, VRAM, and **license** at the start of any implementation slice — these
> move.

---

## 1. North star

A **self-contained exam-prep guide**: a student opens the generated guide on exam
night and needs nothing else — not the messy lecture PDF, not the professor's slide
frames. Four pillars (plus a fifth, adjacent one):

1. **Capture** — reliably pull *everything that matters* out of messy / scanned /
   figure-heavy decks, not just the clean text pages.
2. **Explain** — simplify and teach clearly and correctly (the app's strongest
   pillar today).
3. **Show** — embed the *necessary* tables, figures, graphs, diagrams, and images
   inline, so the student never reopens the source.
4. **Trust** — make "complete and correct" measurable, not hoped.
5. **Retain** (adjacent) — practice, active recall, spaced repetition, so students
   ace the course, not just read a good guide.

## 2. Honest current gap analysis

- **Explain — strong.** Deterministic prompt assembly (`include_sections`,
  `output_depth`/`difficulty` axes, generator presets, `## Page N` citations), math
  verification, guide lint. Mature.
- **Capture — text-only.** `_extract_pdf` produces embedded text or Tesseract OCR
  text with `## Page N` anchors. Cloud OCR is designed and gated (29–35) but unwired.
  Advisory metadata (visual signals 30, classification 31, routing 33/34) exists but
  changes no behavior.
- **Show — nonexistent.** No figure is ever extracted into a guide. DOCX images are
  `[image: alt]` placeholders; the markdown sanitizer and Chromium theme have no
  figure path. (Roadmap #10 visual extraction, #11 VLM — both unbuilt.)
- **Trust — partial.** Math verifier, guide lint, eval harness, Ask retrieval tests
  exist. Source-*coverage* and visual-coverage do not.
- **Cost / privacy — a primitive, not a product.** A page-count budget and an
  off-by-default `allow_cloud_ocr` flag exist. No dollar estimate, no explicit modes,
  no dedup, no consent surface.

## 3. The tension — and how Chandra changes it

"Help **all** students" + "never reopen the slides" pushes toward cloud OCR / VLM
(best capture of scans and the only way to judge figures by *seeing* them). "Student
material" pushes toward local privacy. These don't reconcile into one default — they
reconcile into **explicit modes** (§4).

**Chandra partly dissolves the tension for GPU users.** A high-quality *local*
document model (§6) means layout-aware figure/table/diagram extraction with **zero
bytes leaving the box and no consent prompt needed**. That turns Local/Private from a
weak fallback into a genuine first-class mode for anyone with a capable GPU — the
single most important strategic shift since the first draft of this roadmap.

## 4. Mode strategy

- **Local / Private** — embedded text + Tesseract fallback today; **future
  `chandra_local`** for high-quality layout-aware extraction. No cloud, no consent
  prompt, no API cost. Strongest for digitally-authored PDFs; with Chandra, also
  strong on scans (GPU permitting).
- **Smart Cloud Assist** — `mistral_ocr` on *selected* weak / scanned / visual-heavy
  pages only. Budgeted, opt-in, per-session consent. The recommended default *paid*
  mode. Cents to ~$1–$2 per course pack when selective.
- **Maximum Fidelity** — broader cloud extraction + optional future VLM visual
  reasoning. Explicit warning, dollar + page caps. "Use for important documents."

## 5. The provider-agnostic manifest (the load-bearing design decision)

The biggest architectural call: **the visual asset manifest is a normalization
boundary, not a fitz dump.** fitz, Chandra, and Mistral all emit overlapping
information at different fidelity:

| source          | gives you                                                        | fidelity |
|-----------------|------------------------------------------------------------------|----------|
| `fitz` (local)  | image xref rects, drawing-object counts, page dims               | crude    |
| `chandra_local` | typed layout blocks (figure/diagram/table/caption/…) + bboxes + captions, Mermaid for flowcharts, chart data, LaTeX, merged-cell tables | rich, local |
| `mistral_ocr`   | per-page Markdown, reconstructed md/HTML tables, figure images, dimensions | rich, cloud |

So `visual_assets_manifest.json` must be designed for the **rich** case from day one,
even while only fitz populates it. One normalized asset record:

```json
{
  "asset_id": "page_0142_fig_01",
  "source_page": 142,
  "asset_type": "diagram",
  "bbox": [120, 220, 880, 640],
  "caption": "Backpropagation flow through an MLP.",
  "source_provider": "fitz_local",
  "recommended_action": "include_as_figure",
  "dedupe_group": null,
  "scores": {}
}
```

`source_provider` ∈ `{fitz_local, chandra_local, mistral_ocr, vlm_*}`. Cheap fitz
signals, Chandra's typed blocks, and Mistral's images all map into the same shape, so
no schema rebuild is needed when a richer provider lands. Closed-vocabulary fields,
no paths/keys/raw provider payloads — same leak-safety posture as
`extraction_metadata.json`.

## 6. Provider roles (verified June 2026 — re-verify at impl time)

- **`tesseract_local`** — current basic local OCR. Text only, no layout. Always
  available, the floor.
- **`chandra_local`** — **near-roadmap, not vague-future.** `datalab-to/chandra`,
  Chandra OCR 2 is a **4B-parameter** model (down from 9B in v1), reported
  state-of-the-art on the olmOCR benchmark (~85.9%), released 3/2026. Converts
  images/PDFs to structured HTML/Markdown/JSON with **bounding boxes on every block**
  and **typed blocks** (figure / diagram / image / table / caption / equation /
  chart / code…); flowcharts → Mermaid; chart data extracted; math → LaTeX;
  merged-cell tables preserved. Runs locally via HuggingFace transformers or a vLLM
  server. **Feasibility on the target GPU (RTX 5070 Ti 16 GB):** 4B fits comfortably
  in 16 GB; the real risks are **throughput** (VLM-class OCR over 500–2,000 pages on
  one consumer GPU is minutes-to-tens-of-minutes) and **infra** (a torch/vLLM GPU
  service beside the Dockerized FastAPI app — the Local Model Manager host-companion
  pattern is precedent, but Chandra is heavier than llama.cpp). **License (decision-
  relevant):** code is Apache 2.0; **model weights are a modified OpenRAIL-M license
  — free for research, personal use, and startups under $2M funding/revenue, and may
  not be used competitively with Datalab's own API**; commercial self-hosting needs a
  license. → **Fine for the personal/single-operator tool; a multi-user "help all
  students" product would likely need Datalab's commercial license. Decide with eyes
  open before building Local mode around it.**
- **`mistral_ocr`** — **near-roadmap cloud provider, not shelved.** Per-page priced
  (~$2/1,000 OCR-3, half via batch), returns per-page Markdown + reconstructed
  tables (md/HTML) + figure images + dimensions. A direct enabler of the table and
  figure pillars, not "just text OCR." Disabled until the mode + budget framework and
  opt-in settings exist (Slice 35 conditional-go: confirm live pricing + privacy).
- **`gemini` / other VLM** — optional future cloud *visual-reasoning* provider for
  ambiguous figure-necessity judgement only. Last, opt-in, budgeted, verified-first.
  Not near-term.

## 7. Privacy / cost stance

Privacy is a **disclosure / consent layer, not a hard blocker** — most university
slides aren't highly sensitive, but users may upload private notes, marked work,
classmates' names, or paid course PDFs, so the app must never silently upload.

- Cloud processing is always **explicit and opt-in**, never the default.
- A **once-per-session** disclaimer for cloud modes: "Cloud extraction may send
  selected pages, images, tables, or figures to a third-party provider and may incur
  API costs. Continue only if you're okay processing this material with that
  provider."
- **Local / Private (Tesseract or Chandra) needs no disclaimer** — nothing leaves the
  box. This is the privacy-clean high-quality path.
- Cloud is **budgeted and capped** (dollar + page), with a pre-run estimate, sized
  for 500–2,000-page course packs.

## 8. Dependency-ordered visual stack

```
V1 manifest (advisory) ─► V2 dedup/filter ─► V3 candidate scoring (text-replacement test)
                                                       │
                                                       ▼
                                             V4 asset-aware prompt
                                                       │
                                                       ▼
                                             V5 render embed  ──► V7 visual + coverage eval
                                                       ▲
                                   V6 VLM (optional, upgrades V3)
```

- **V1 — visual asset manifest (advisory).** Provider-agnostic schema (§5), first
  populated from existing Slice 30 signals only. No render/guide change. Everything
  below needs this.
- **V2 — dedup + decorative filtering (advisory).** Perceptual-hash `dedupe_group`s;
  flag logos/titles/tiny/duplicate. The 2,000-video-frame cost lever — collapse the
  deck *before* spending cloud/VLM.
- **V3 — candidate scoring = the text-replacement test (advisory).** Per asset:
  `include_as_figure | convert_to_table | summarize_as_text | omit`, from cheap
  signals (drawing density → diagram; OCR/Chandra table block → inline table, no
  image; "see figure" references; formula proximity; uniqueness; size). Tables are a
  near-free win.
- **V4 — asset-aware prompt assembly.** Give the guide-writer an asset *inventory*
  (id, page, caption, recommended action) so it can place `{{figure:asset_id}}`
  tokens and explain them. Inert until V5; byte-identical when no assets. Add a token
  lint (well-formed, no unknown ids).
- **V5 — visual render path (HIGH RISK, late).** Resolve tokens → embedded images in
  `clean.md`/PDF/HTML/DOCX; sanitizer whitelist + theme caption styling + replace the
  DOCX placeholder. Touches the tuned Chromium PDF path — flag-gated, golden-render
  regression-tested.
- **V6 — VLM understanding (optional ceiling).** Opt-in, budgeted, verified-first;
  upgrades V3's heuristic necessity calls for ambiguous candidates. Non-blocking.
- **V7 — visual + coverage eval (advisory).** High-value figures included? orphaned
  tokens? duplicate figures? all selected source pages represented? Makes
  "self-contained" measurable.

**Critical separation:** OCR page **classification** answers *"how was this page
extracted and how reliable is it?"* (`embedded_text / ocr_fallback / likely_scanned /
blank_or_low_text / mixed / error`). Visual **candidate scoring** answers *"does this
asset belong in the guide?"* These never merge. Page/asset **dedup** is an upstream
cost lever; guide **inclusion** is downstream and requires the manifest first.

**Local-extraction limitation:** local fitz extraction is useful for digitally
authored PDFs (image rects, drawing clusters). For scanned / video-frame decks the
whole page is often one image, and fitz can't segment a figure inside it — that's
where `chandra_local`, `mistral_ocr`, or a VLM is needed.

## 9. Proposed slice order

```
Slice 35  Commit Mistral OCR prerequisite verification (docs).            [done/committing]
Slice 36  Commit this visual/cost roadmap (docs only).
Slice 37  Provider-agnostic OCR/extraction mode + cost/budget skeleton, disabled by default.
Slice 38  visual_assets_manifest.json schema (provider-agnostic), populated from existing
          Slice 30 signals only — advisory, no new extraction.
Slice 39  Chandra local feasibility — DOCS verification only (capability, license, VRAM,
          throughput, integration shape, from official sources; NO install, NO API call).
          Mirrors Slice 35 for Mistral.
Slice 40  Actual local figure extraction / cropping into the manifest (fitz: rasterize
          regions + bboxes). First real extractor-output change — gated.
Slice 41  Dedup + decorative filtering (V2).
Slice 42  Candidate scoring / text-replacement test (V3).
Slice 43  Mistral provider skeleton — disabled and unwired (Slice 32 boundary; server-side
          key-storage design; no network to generation).

Parallel / later (not blocking the above):
  • Chandra HANDS-ON feasibility spike — run on the RTX 5070 Ti, time a real 500-page
    deck, judge output quality. Do AFTER Slice 38 so "useful output" has a schema target;
    can run alongside 40–42. Gates whether chandra_local becomes a real provider.
  • V4 asset-aware prompt assembly.
  • V5 visual render path — golden-render tested, flag-gated.
  • V6 optional VLM provider verification/skeleton.
  • Source-coverage + JobDetails surfacing (Trust pillar); V7 visual eval.
  • Retain pillar: FSRS spaced repetition, active-recall/cloze, true Anki .apkg.
```

## 10. Decision forks to resolve

1. **Cloud OCR (Mistral): yes/no + cost ceiling.** Gates Smart Cloud Assist / Max
   Fidelity. (Slice 35 = conditional-go on pricing + privacy.)
2. **Chandra local: pursue?** Gated by the Slice 39 docs verification + the hands-on
   spike, and by the **license vs multi-user ambition** question.
3. **VLM: ever?** Determines whether V6 is on the map. The pipeline reaches a good
   result without it.
4. **Privacy floor.** Local/Private is a first-class supported mode (honestly weaker
   without a GPU + Chandra); cloud is always explicit/opt-in.
5. **Render-risk appetite.** V5 touches the tuned PDF path — confirm appetite for a
   gated, golden-tested change before building it.

## 11. Quick wins worth pulling early

- **Tables are nearly free.** Chandra and Mistral both reconstruct tables as
  embeddable markdown/HTML — most tables become inline guide tables with no image and
  no render-path risk, delivering a big chunk of "don't reopen the slides" before V5.
- **Dedup pays for itself immediately** on video-frame decks — cost lever (cloud) and
  quality lever (fewer duplicate figures) at once.
- **Cost estimate at preflight** is small and removes the scariest unknown before a
  cloud run.
- **Chandra-local, if feasible, is the privacy-clean high-quality path** — no
  disclaimer, no API cost, strong on scans. Verifying it early (Slice 39) is cheap and
  could reshape how much of the visual pipeline runs locally.

## 12. Principles preserved throughout

Advisory artifact before behavior change; degrade-not-fail (no OCR / figure / VLM
step ever fails or blocks a generation); local/private default with explicit opt-in
cloud; server-side-only keys with key-less DTOs; closed-vocabulary leak-safe
metadata; exact-name artifacts before generic lists; `clean.md` writes only via
`JobManager.save_clean_md`; byte-identical output when a feature is unused; small
verifiable slices, verify-and-commit between. The visual stack is ambitious but
sequenced so all but one slice (V5) stay inside these guarantees.
