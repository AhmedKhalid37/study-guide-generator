# TABLE_STRUCTURE_PHASE2_SLIDE_RASTER_OCR_GATE.md — Slice 176F

> Closed verification-gate record for slide-raster OCR. Closed tokens / counts /
> bools / labels only: no guide / source / OCR / table text, no formulas, no raw
> values, no private paths / filenames / hashes / byte counts / screenshots, no
> provider payloads / prompts / responses / secrets. The repo is the source of
> truth; verify the harness/module before relying on this.

---

## 0. What this slice is

A **correction + verification gate**, not a pipeline build. Direct source inspection
(outside this repo workflow) overturned the prior closed-evidence inference that the
Ensemble numeric inputs are *absent / unverifiable-from-source*. This slice verifies,
**with real local OCR on the real decks**, whether the inputs are recoverable, and
corrects the project record accordingly. It tries **Tesseract first** (with local
preprocessing/cropping) before assuming Chandra is needed.

**IS:** a produce-before-scaffold OCR verification gate run on the real decks, plus a
committed corrected record + a public-safe reproducibility test.
**IS NOT:** another cold text-layer Gini attempt, a recoverability audit, a
source-input bridge, numeric plumbing, a prompt/generation slice, a visual-manifest
rebuild, a generic ingestion pipeline, generation wiring, a Layer-2 judge, or repair.
No cloud OCR. No nonlocal Chandra/API. No provider/model generation. No guide
regeneration. `judge_ready=false`; `repair_ready=false`.

- public-safe test: `test_scripts/test_quality_safety_slide_raster_ocr_gate.py`
- real gate run: gitignored, transient harness (not committed); only closed labels here.

## 1. Corrected source-deck classification (real, measured)

The two decks were re-measured directly from the gitignored operator baseline.

- **Ensemble deck**
  - `text_layer_status=near_empty`
  - `page_count=446`
  - `extractable_text_chars_approx=5045`
  - `effective_content_form=full_page_raster_slide_images`
  - `numeric_input_blocker=extraction_gated_on_raster_ocr`
- **NN3 deck**
  - `text_layer_status=near_empty`
  - `page_count=340`
  - `extractable_text_chars_approx=234`
  - `effective_content_form=full_page_raster_slide_images`
  - `prior_partial_text_classification=metadata_artifact`

Corrected conclusions:

- `do_not_mark_ensemble_numeric_inputs_absent_globally=true`
- `do_not_mark_nn3_as_clean_partial_text=true`
- `phase2_reframed_as=slide_raster_ocr_ingestion`
- `tesseract_role=bulk_text_captions_loose_tables`
- `local_chandra_role=structured_tables_math_figures_verification`
- `cloud_ocr_allowed=false`
- `local_chandra_allowed=true`

## 2. Method (Tesseract-first, local only)

Pages were rendered locally (PyMuPDF) to transient images, OCR'd with **Tesseract
5.x** (`--psm 6` / `--psm 11`, TSV word boxes + per-word confidence as a text-free
quality proxy), with local preprocessing (grayscale, upscale, binarize) and
**anchor-region cropping** attempted for the dense grids. The masked Gini recompute
routes through the **real** `_recompute_weighted_gini` (`SUPPORTED_METHODS`), never a
parallel engine, and is **only** run when the **176E column-alignment credibility
guard** passes on the OCR integer cells (≥2 shared x-columns each ≥2 cells, ≥2
multi-column rows). The printed Gini answer is never supplied as an input. No raw OCR
text, no rendered images, and no source PDFs are committed.

## 3. Closed gate result (real decks)

- `artifact_name=quality_safety_slide_raster_ocr_gate`
- `status=completed`
- `source_decks_considered_count=2`
- `ensemble_text_layer_status=near_empty`
- `nn3_text_layer_status=near_empty`
- `ensemble_effective_content_form=full_page_raster_slide_images`
- `nn3_effective_content_form=full_page_raster_slide_images`
- `tesseract_status=ran`
- `chandra_status=not_available`
- `cloud_ocr_used=false`
- `local_chandra_only=true`
- `representative_slides_considered_count=4` (categories below)
- `tesseract_bulk_text_quality=clean`
- `tesseract_loose_table_quality=partial`
- `tesseract_dense_grid_quality=failed`
- `tesseract_preprocessed_gini_quality=failed`
- `chandra_structured_table_quality=unavailable`
- `chandra_math_quality=unavailable`
- `gini_input_cells_recovered=no`
- `gini_input_cells_engine=none`
- **`gini_masked_recompute_from_ocr_status=not_run`**
- `proximity_matrix_recovered=no`
- `nn3_numeric_content_recovered=partial`
- **`corrected_blocker=extraction_gated_on_raster_ocr`**
- **`recommended_next_step=install_local_chandra_and_rerun_gate`**
  (secondary: `improve_tesseract_preprocessing`)

### Per-representative-slide (closed)

| slide_category | source_label | tess_table | tess_pp_table | chandra_table | grid_cells | math | ocr_committed | screenshot_committed | raw_values_committed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ensemble_gini_or_leaf_count_slide | ensemble | failed | failed | unavailable | no | na | false | false | false |
| ensemble_patient_dataset_table_slide | ensemble | partial | partial | unavailable | partial | na | false | false | false |
| ensemble_proximity_matrix_slide | ensemble | failed | failed | unavailable | no | na | false | false | false |
| nn3_softmax_or_numeric_slide | nn3 | partial | partial | unavailable | no | partial | false | false | false |

## 4. Finding (what OCR actually showed)

- **The decks are image-locked but OCR-readable for prose.** Tesseract recovered
  bulk slide text, captions, and the relevant terminology (the Gini / chest-pain /
  patient / proximity / softmax / cross-entropy keyword layer) at **clean** mean word
  confidence on both decks, despite near-empty PDF text layers. This **confirms** the
  corrected classification: full-page raster slides, not absent content.
- **The dense numeric grids did NOT survive OCR as structured cells.** On every
  tested Gini / proximity / NN3 numeric slide, the 176E credibility guard **failed**
  (never ≥2 shared columns AND ≥2 multi-column rows). Local preprocessing and
  anchor-region cropping did **not** rescue the grid and sometimes erased the
  integers. A single naive "finite Gini from a couple of integers" appeared and was
  **correctly rejected** by the guard as the same coincidental false positive 176E
  was built to catch — so it was **not banked**.
- Therefore `gini_masked_recompute_from_ocr_status=not_run`: no credible class-count
  input grid was recovered to recompute from. (`warning=answer_or_unrelated_values_not_inputs`.)

## 5. Decision (rule C)

Tesseract recovers bulk text / loose tables but **not** the dense / structured Gini
(and proximity / NN3) input cells, and **Chandra is not available locally** in this
environment. Per the slice decision rule:

- `corrected_blocker=extraction_gated_on_raster_ocr` — the inputs **are** present as
  slide pixels; the current OCR path reads prose but not the dense numeric grids.
- `recommended_next_step=install_local_chandra_and_rerun_gate` — Chandra (local
  HuggingFace/vLLM, per `docs/CHANDRA_OCR_VERIFICATION.md`) is the designed
  structured-table/math OCR; rerun this gate on the same slides before building any
  ingestion pipeline. Secondary: `improve_tesseract_preprocessing` (better table
  binarization / deskew / cell segmentation) is a cheaper thing to try first.

**No ingestion pipeline was built in this slice.** The three load-bearing fields,
clean: `gini_masked_recompute_from_ocr_status=not_run`,
`corrected_blocker=extraction_gated_on_raster_ocr`,
`recommended_next_step=install_local_chandra_and_rerun_gate`.

## 6. Continuity with prior slices

- This does **not** contradict 176E. 176E was an honest false-positive guard / hard
  blocker on the **text-layer** path; this slice confirms why (the inputs are in
  raster pixels) and that the same guard correctly rejects the OCR false positive too.
- It **corrects** 176D's optimism and the prior "absent / unverifiable-from-source"
  and "NN3 partial_text" labels: the inputs are **not** absent and NN3 is **not**
  clean partial_text — both decks are extraction-gated on raster-slide OCR.
- Numeric truth on these decks cannot be finished until the dense grids are extracted
  by a structured OCR engine — that routes to Phase 2 OCR (Chandra), not to more
  numeric-context plumbing or another text-layer Gini attempt.

No Chandra ran (not available locally); no cloud OCR; no provider/model generation;
no guide regeneration; no Layer-2 judge; no repair. `judge_ready=false`;
`repair_ready=false`.
