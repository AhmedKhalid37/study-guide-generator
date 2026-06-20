# TABLE_STRUCTURE_PHASE2_LOCAL_CHANDRA_OCR_GATE.md — Slice 176G

> Closed local-Chandra structured-OCR rerun-gate record. Closed tokens / counts /
> bools / labels / structural shapes only: no guide / source / OCR / table text, no
> formulas, no raw values / leaf counts / matrix entries, no private paths /
> filenames / hashes / byte counts / screenshots, no model files / caches, no
> provider payloads / prompts / responses / secrets. The repo is the source of
> truth; verify the harness before relying on this.

---

## 0. What this slice is

The **local-Chandra rerun gate** 176F recommended (`recommended_next_step=
install_local_chandra_and_rerun_gate`). 176F proved the two decks are near-empty-text
full-page raster slides and that **Tesseract** recovers prose but **fails** the dense
structured grids (proximity matrix not recovered; Gini masked recompute `not_run`).
This slice **ran local Chandra OCR 2** on the same representative slide categories and
records closed structured-OCR quality + provenance.

**IS:** a produce-before-scaffold local-Chandra rerun gate on the representative real
slides, run once with real data via a gitignored transient harness; a committed closed
record.
**IS NOT:** the OCR ingestion pipeline, a cloud OCR integration, provider/model
generation, a frontend/API feature, a broad recoverability audit, a source-input
bridge, a Layer-2 judge, or repair. No cloud OCR. No nonlocal/API Chandra. No guide
regeneration. `judge_ready=false`; `repair_ready=false`.

- real gate run: gitignored, transient harness (not committed); only closed labels here.
- raw Chandra output, rendered slide images, source PDFs, GGUF model files, and model
  caches stay outside the repo and uncommitted.

## 1. Chandra availability / mode (real, measured)

- The **`chandra-ocr` pip package** (hf / vllm / cli modes) is **not installed**
  locally (`import chandra` fails; no `chandra` CLI on PATH; `vllm` not installed).
- A **local GGUF route is available and was used**: Chandra OCR 2 quantised to GGUF
  (`Q5_K_M` text + self-generated `mmproj`) served through **`llama.cpp` /
  `llama-server`** (build 9307, qwen3vl mmproj support) on the local **RTX 5070 Ti
  16 GB** — the exact path proven in `docs/CHANDRA_GGUF_SPIKE_REPORT.md` (Slice 41).
  This is **local-only** (no network, no API).
- `chandra_status=ran_local`
- `chandra_mode=gguf_local` (llama.cpp/llama-server GGUF; the enumerated package modes
  hf_local/vllm_local/cli_local were **not** the path used because the package is not
  installed — recorded honestly rather than forced into a package-mode label)
- `cloud_ocr_used=false`
- `model_files_committed=false` · `model_cache_committed=false` ·
  `raw_chandra_output_committed=false`

## 2. Method (local only)

Representative pages were selected per category by a Tesseract keyword + max-numeric
pre-scan (same category set as 176F), rendered locally (PyMuPDF) to transient images,
and OCR'd by local `llama-server` over its OpenAI-compatible image path
(`enable_thinking=false`, `--temp 0`, `--image-min-tokens 1024` for bbox grounding).
Output (layout-labelled HTML with `<table>` / LaTeX math / `data-bbox` / `data-label`)
was parsed **structurally only**. For the Gini slide, integer table cells were
considered as candidate class counts and routed to the **real**
`_recompute_weighted_gini` (`SUPPORTED_METHODS`) **only** if a credible column-aligned
grid (≥2 table rows each contributing ≥2 integer cells) was found; **unit-interval
decimals (printed Gini answers) are excluded from inputs**. No raw OCR text, no
rendered images, no model files/caches, and no source PDFs are committed.

## 3. Closed gate result (real decks, local Chandra)

- `artifact_name=quality_safety_local_chandra_ocr_rerun_gate`
- `status=completed`
- `source_decks_considered_count=2`
- `representative_slides_considered_count=4`
- `chandra_status=ran_local` · `chandra_mode=gguf_local` · `cloud_ocr_used=false`
- `chandra_structured_table_quality=clean` (well-formed HTML tables recovered on all 4)
- `chandra_dense_grid_quality=clean` (the dense 5×5 proximity grid recovered —
  the exact structure Tesseract failed in 176F)
- `chandra_math_quality=partial` (LaTeX math recovered on the softmax slide)
- `chandra_figure_caption_quality=partial` (caption/label blocks present on 2 slides)
- `gini_input_cells_recovered=no`
- `gini_input_cells_engine=chandra_local`
- **`gini_masked_recompute_from_ocr_status=not_run`**
- `warning=answer_or_unrelated_values_not_inputs` (Gini)
- `proximity_matrix_recovered=yes`
- `nn3_numeric_content_recovered=partial`
- **`corrected_blocker=local_ocr_available_needs_pipeline`** (with the Gini caveat in §5)
- **`recommended_next_step=build_local_slide_ocr_ingestion_pipeline`** (with the
  precondition in §5: a masked-recompute Gini proof on a worked-example split slide
  must be obtained for/within the numeric path before any Gini number is trusted)

### Per-representative-slide (closed; structural shapes only)

| slide_category | source_label | chandra_table_recovered | grid_cells_recovered | math_recovered | recompute | raw_output_committed | screenshot_committed | raw_values_committed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ensemble_gini_or_leaf_count | ensemble | clean (per-split summary table) | no (1 count/row + computed Gini answer/row; not a ≥2-class grid) | na | not_run | false | false | false |
| ensemble_patient_dataset_table | ensemble | clean (per-row summary table) | partial (1 count/row) | na | not_run | false | false | false |
| ensemble_proximity_matrix | ensemble | clean | yes (full 5×5 dense numeric matrix) | na | not_run | false | false | false |
| nn3_softmax_or_numeric | nn3 | clean (small table) | no | partial (LaTeX recovered) | not_run | false | false | false |

## 4. Finding (what local Chandra actually showed)

- **Local Chandra GGUF materially beats Tesseract on dense raster slides.** It
  recovered well-formed HTML tables, LaTeX math, layout labels, captions, and per-block
  bounding boxes — and, decisively, the **dense 5×5 proximity matrix** that Tesseract
  could **not** recover in 176F (`proximity_matrix_recovered` no → **yes**). Structured
  local OCR on these decks is therefore **viable**.
- **The Gini masked-recompute proof was NOT obtained, and was correctly not banked.**
  The auto-selected representative Gini page (the max-numeric Gini-keyword slide) is a
  **per-split summary table**: each row carries **one** count and the **computed Gini
  value** (a unit-interval decimal). A weighted-Gini recompute needs the **raw ≥2-class
  contingency counts per node**, which are **not** on this summary slide. The decimals
  are **answers**, excluded by construction. So `gini_input_cells_recovered=no` and
  `gini_masked_recompute_from_ocr_status=not_run` (`warning=answer_or_unrelated_values_
  not_inputs`). This is the GATE-2 distinction held firm: a recovered Gini **answer** is
  not a recovered Gini **input**.
- **nn3 numeric content is partial:** the softmax slide's LaTeX math and probability
  values were recovered, but not as a clean recompute-able logit grid.

## 5. Decision (rule B/C blend — recorded honestly)

Per the slice decision rules, Rule B (Gini masked recompute passes) is **not** met, and
Rule C's "improve_tesseract / compare_alternatives" next-steps would **misroute** —
Chandra already beat Tesseract and recovered dense structure. The honest classification:

- `corrected_blocker=local_ocr_available_needs_pipeline` — local structured OCR is
  **demonstrably available** (proximity matrix + dense tables + math recovered locally,
  no cloud). The blocker is no longer raster-OCR capability.
- **Gini caveat (load-bearing, do not launder):** the **Gini masked-recompute proof is
  outstanding**. It was not obtained because the representative Gini slide presents a
  summary (answers), not raw split counts — a **slide-selection / content** matter, not
  an OCR-capability gap. **No Gini number may be trusted** until a masked recompute
  passes from raw split counts on a worked-example slide.
- `recommended_next_step=build_local_slide_ocr_ingestion_pipeline` — but its **numeric
  path must, as a precondition, obtain the Gini masked-recompute proof** (target the
  worked-example tree-split slides, recover the ≥2-class contingency counts, recompute
  through the real verifier with the answer excluded). Until then, Gini stays
  `unverified`; the §0 safety invariant holds (no confident-but-wrong cleanup).

**No ingestion pipeline was built in this slice.** Three load-bearing fields, clean:
`gini_masked_recompute_from_ocr_status=not_run`,
`corrected_blocker=local_ocr_available_needs_pipeline`,
`recommended_next_step=build_local_slide_ocr_ingestion_pipeline` (Gini-proof-gated).

## 6. Continuity with prior slices

- This **follows** 176F and does **not** contradict it: 176F predicted Tesseract was
  insufficient for the dense grids and recommended the local-Chandra rerun; 176G ran it
  and confirms Chandra recovers the dense proximity grid Tesseract missed.
- It **updates** the project blocker from `extraction_gated_on_raster_ocr` (176F, while
  only Tesseract had run) to `local_ocr_available_needs_pipeline` — local structured OCR
  exists; the work moves to a (numeric-proof-gated) ingestion pipeline, not more OCR
  engines.
- The Gini numeric truth remains **unproven** on these decks until a masked recompute
  passes from OCR-recovered raw split counts — that is the next slice's numeric exit bar,
  not a thing 176G banked.

No cloud OCR; no nonlocal/API Chandra; no provider/model generation; no guide
regeneration; no Layer-2 judge; no repair. `judge_ready=false`; `repair_ready=false`.
raw_chandra_output_committed / model_files_committed / model_cache_committed /
screenshot_committed / raw_values_committed all false.
