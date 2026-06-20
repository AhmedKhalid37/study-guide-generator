# CURRENT_TASK.md — Live handoff

> Update this every slice. For stable overview see `PROJECT_CONTEXT.md`; for the
> "why" behind choices see `DECISIONS.md`.

---

## Phase 2 product path — **Slice 176K: visible table/figure pilot from the private 176I OCR artifact; first product-facing consumer; private pilot artifact produced; NOT committed.**

- **phase=Phase 2 (first product-facing consumer of the 176I private OCR artifact)** · **slice=176K** ·
  **module=`pipeline/visible_table_figure_pilot.py`** · **test=`test_scripts/test_visible_table_figure_pilot.py`** ·
  **branch=`slice176k-visible-table-figure-pilot-private-ocr`** · **judge_ready=false** · **repair_ready=false**.
- **Why this slice.** 176J settled the Gini numeric path for this artifact as **answer_output_only / not
  machine-consumable** and routed to `pivot_to_visible_table_pilot`. 176K is that pivot: the **product path**,
  the first downstream consumer that turns recovered OCR content into **student-visible display assets** (not
  numerics). It exists because 176I produced real extracted content.
- **What it is / is NOT.** A minimal selector that picks a **very small** set (max 3) of high-value
  student-visible assets and packages reconstructed table markdown / structured table JSON / caption-context /
  a placement hint into a **private, gitignored** pilot artifact, emitting a committed-safe closed summary. NOT
  a numeric parser, numeric-recompute wiring, broad table engine, guide-generation wiring, frontend/API, full
  ingestion rollout, Layer-2 judge, repair, cloud OCR, or provider/model generation.
- **Real result (ran on the private artifact).** Selected the 3 priority categories cleanly recovered by 176I:
  `selected_assets_count=3` (max 3) · `selected_asset_categories=[proximity_matrix, patient_dataset_table,
  decision_tree_or_split_diagram]` · `selected_asset_kinds=mixed` · `private_artifact_available=true` ·
  `private_artifact_gitignored=true` · `private_visible_artifact_written=true` ·
  `private_visible_artifact_gitignored=true` · `table_asset_status=ready` · `figure_asset_status=partial`
  (the decision-tree slide was recovered as a table grid, not a true figure image) ·
  `caption_or_context_status=ready` · `guide_insertion_readiness=ready_for_off_by_default_private_pilot` ·
  `numeric_verification_role=display_only` · `numeric_recompute_claimed=false` · `blocked_by=none` ·
  `recommended_next_step=wire_visible_assets_into_private_guide_preview`.
- **Anti-laundering (display-only).** These are **display / study assets**, not numeric verification. No asset
  is `numeric_verification`; the numeric-bearing tables are `display_only`; nothing is fed into recompute and
  no numeric correctness is claimed. Raw reconstructed tables, captions, rendered crops, source PDFs, model
  files/caches, and private paths live **only** in the private artifact directory — never committed.
- **Validation.** `compileall api pipeline test_scripts` OK; `test_visible_table_figure_pilot` OK;
  `test_gini_input_cell_parser` OK; `test_slide_raster_ocr_ingestion` OK; `git diff --check` clean. No Docker.
  No frontend/API/generation code touched. The private artifacts and `local_operator_baselines/` stay ignored.
  **NOT committed.**
- **176K is the last preparation slice.** No further readiness/seam/adapter/policy-only/numeric-parser slice
  may follow. Per the byte-identical invariant, the **next** slice (176L) must change what a student can
  actually read: a private regenerated guide / guide preview built from the extracted 176I OCR content (and,
  if safe in scope, the selected 176K visible assets), compared against the existing baseline with a **scored
  comparison if existing eval tooling supports it** — no new judge, no repair, no cloud OCR, no frontend/API
  wiring.

---

## Phase 2 numeric consumer — **Slice 176J: Gini input-cell parser over the private 176I OCR artifact; numeric path stays blocked (slide is an answer summary); committed `91c32ab` / merged to trunk.**

- **phase=Phase 2 (first numeric consumer of the 176I private OCR artifact)** · **slice=176J** ·
  **module=`pipeline/gini_input_cell_parser.py`** · **test=`test_scripts/test_gini_input_cell_parser.py`** ·
  **branch=`slice176j-gini-input-cell-parser-private-artifact`** · **judge_ready=false** · **repair_ready=false**.
- **Why this slice.** 176I extracted real slide content and set
  `numeric_recompute_readiness=needs_input_cell_parser`. 176J is the **first numeric consumer**: it tries to
  parse **raw Gini class-count input cells** for one target out of the private OCR artifact and run a **masked**
  recompute (printed answer never supplied) — only if credible raw inputs are found.
- **What it is / is NOT.** A minimal, answer-agnostic parser for one weighted-Gini target. NOT an OCR engine,
  broad table engine, guide-generation wiring, frontend/API, Layer-2 judge, repair, cloud OCR, or
  provider/model generation. No raw OCR/table text, raw values, or private paths committed.
- **Real result (honest, anti-laundering).** Ran the parser on the private 176I artifact's gini slide. That
  slide is a **per-split answer summary** — each row carries a single count and a single Gini **value** (a
  unit-interval decimal), **not** a raw class-count grid (which needs ≥2 paired class-count integer columns per
  node). The parser correctly **refused the Gini answer column** and created **no** source-input record:
  `status=blocked` · `selected_target_id=gini_chest_pain` · `selected_target_family=weighted_gini` ·
  `private_artifact_available=true` · `private_artifact_gitignored=true` ·
  `input_cell_candidate_status=rejected_false_positive` · `input_cell_candidate_origin=private_ocr_artifact` ·
  `candidate_kind=computed_gini_answer` · `class_label_coherence=not_applicable` ·
  `column_alignment_status=failed` · `answer_agnostic_guard_status=passed` ·
  `source_input_record_status=not_created` · `source_input_origin=none` ·
  `machine_consumable_for_recompute=false` · `masked_recompute_status=not_run` · `false_positive_rejected=true` ·
  `warning=answer_or_unrelated_values_not_inputs` · `blocked_by=answer_output_only` ·
  `recommended_next_step=pivot_to_visible_table_pilot`.
- **Numeric truth NOT claimed.** Gini stays `unverified`: no raw class-count inputs were parsed, no masked
  recompute ran. This is **consistent** with the 176G/176H note that the representative Gini slide is an answer
  summary, not the raw class-count grid. Artifact quality was sufficient (table cleanly recovered); the inputs
  simply are not on this slide — so the next step is **not** more OCR plumbing. The private guide-context and
  visible-table pilots remain valid downstream regardless.
- **Validation.** `compileall api pipeline test_scripts` OK; `test_gini_input_cell_parser` OK;
  `test_slide_raster_ocr_ingestion` OK; `recompute_verifier` 311/0; `git diff --check` clean. No Docker. No
  frontend/API/generation code touched. The private artifact and `local_operator_baselines/` stay ignored.
  **NOT committed.**

---

## Phase 2 slide-raster OCR ingestion — **Slice 176I-real: ran local structured OCR on real content slides; private extracted-content artifact produced; committed `937f843` / merged to trunk.**

- **phase=Phase 2 slide-raster OCR ingestion** · **slice=176I-real (real content extraction run)** ·
  **runner=`test_scripts/run_local_structured_ocr_content_extraction.py`** ·
  **doc=`docs/LOCAL_STRUCTURED_OCR_CONTENT_EXTRACTION.md`** ·
  **branch=`slice176i-run-local-structured-ocr-content-extraction`** · **judge_ready=false** · **repair_ready=false**.
- **Why this slice.** 176G proved local structured OCR recovers dense grids; 176H built only the seam. This is
  the **first real content-extraction run** of that proven producer on **content-bearing** slides (not
  title/intro/text-layer pages) — produce-before-scaffold, no new adapter framework.
- **What ran (real, local).** Chandra OCR 2 **GGUF** via local `llama-server` (OpenAI-compatible
  `/v1/chat/completions`, local-only, no cloud/API), driven by the **committed** `chandra_local_provider`
  payload builder + `chandra_normalizer`. Content slides selected by a Tesseract keyword + numeric-density
  pre-scan; rendered locally (PyMuPDF). Raw layout-HTML + manifest written **only** to a private gitignored dir.
- **GATE-2 confound caught + fixed (not banked blind).** The first pass under-recovered (4/5 slides empty),
  which **contradicted 176G**. Diagnosis: server-side **thinking** was on → the transcription went to the
  hidden reasoning channel and content came back empty. 176G ran thinking-off; re-running with
  `enable_thinking=false` recovered well-formed tables — **consistent with 176G**. Corrected run is the banked one.
- **Closed extraction summary (corrected run).** `status=completed` · `source_label=ensemble` ·
  `selected_slide_categories_count=5` (4 distinct pages) · `pages_rendered_count=5` ·
  `structured_ocr_status=ran_local` · `structured_ocr_engine=chandra_gguf_local` · `cloud_ocr_used=false` ·
  `private_artifact_written=true` · `private_artifact_gitignored=true` · `content_extraction_status=extracted` ·
  `extracted_text_block_count_bucket=high` · `extracted_table_count_bucket=medium` ·
  `extracted_figure_or_diagram_count_bucket=low` · `dense_grid_recovery_status=recovered` ·
  `patient_dataset_table_status=recovered` · `proximity_matrix_status=recovered` ·
  `gini_or_leaf_count_status=partial` · `guide_content_readiness=ready_for_private_prompt_context_pilot` ·
  `visible_table_readiness=ready_for_visible_table_pilot` · `numeric_recompute_readiness=needs_input_cell_parser` ·
  `gini_masked_recompute_from_ocr_status=not_attempted` ·
  `recommended_next_step=run_gini_input_cell_parser_on_private_artifact`.
- **Anti-laundering.** "recovered" = structure extracted, **not** numeric verification. Gini stays
  `unverified`: no masked recompute was run from raw input cells. Numeric truth is a **later** consumer.
- **Validation.** `compileall api pipeline test_scripts` OK; `test_slide_raster_ocr_ingestion` OK; 176F gate OK;
  `recompute_verifier` 311/0; `git diff --check` clean. No Docker. No frontend/API/generation code touched. No
  raw OCR/table text, rendered images, source PDFs, model files/caches, or private paths committed;
  `local_operator_baselines/` (incl. the private extracted-content artifact) stays ignored. **NOT committed.**

---

## Phase 2 slide-raster OCR ingestion — **Slice 176H local slide-OCR ingestion artifact seam; off-by-default; committed `29420cc` / merged to trunk.**

- **phase=Phase 2 slide-raster OCR ingestion** · **slice=176H (ingestion artifact seam)** ·
  **module=`pipeline/slide_raster_ocr_ingestion.py`** · **test=`test_scripts/test_slide_raster_ocr_ingestion.py`** ·
  **branch=`slice176h-local-slide-ocr-ingestion-seam`** · **judge_ready=false** · **repair_ready=false**.
- **Why this slice.** 176G's recorded next step was `build_local_slide_ocr_ingestion_pipeline`. This is its
  **first minimal, off-by-default increment** — only the artifact **seam**, not guide-generation wiring,
  not frontend/API integration, not numeric-recompute wiring, not a Layer-2 judge, not repair, not cloud OCR.
- **What it IS.** Pure/testable helpers + an inert-by-default runner: `classify_pdf_text_layer`,
  `detect_full_page_image_blocks`, `is_private_artifact_dir`, `render_selected_pages_to_temp_images`,
  `run_tesseract_if_available`, `run_local_structured_ocr_if_configured`, `write_private_ocr_artifact`,
  `build_closed_slide_ocr_summary`, `run_slide_raster_ocr_ingestion`. Raw OCR / rendered images go **only**
  to a private gitignored/temp directory; if none is available the seam **degrades to a closed `blocked`
  status rather than writing into the repo**. Every persisted field is a closed token/count/bool.
- **Closed safety posture (hardwired).** `cloud_ocr_used=false`; `raw_ocr_committed=false`,
  `raw_table_text_committed=false`, `rendered_images_committed=false`, `model_files_committed=false`,
  `model_cache_committed=false`. Structured-OCR engine labels stay closed and a GGUF/VLM route is **not**
  relabelled hf/cli (`structured_ocr_engine=chandra_gguf_local` ≠ `chandra_hf_local`/`chandra_cli_local`).
  **`numeric_recompute_readiness` can never be `ready_for_masked_recompute` from this seam** — a later
  masked-recompute consumer owns that (it is forced down to `needs_input_cell_parser`).
- **Optional local smoke (real deck, 2-page subset, rendered to `/tmp` only, auto-deleted; closed labels
  only).** `status=completed` · `pages_rendered_count=2` · `tesseract_status=available` (binary present,
  python bindings absent in host → bulk text `not_run`) · `structured_ocr_status=not_available` ·
  `cloud_ocr_used=false` · `private_artifact_written=true` · `rendered_images_committed=false` ·
  `numeric_recompute_readiness=needs_input_cell_parser`. The smoke sampled the **first two pages**
  (title/intro → `text_layer`/`usable`), which does **not** contradict the 176F/176G `near_empty` finding
  on the **category-selected dense grid slides** — a different page class.
- **Validation.** `compileall` OK; `test_slide_raster_ocr_ingestion` OK; 176F gate OK; recompute_verifier
  311/0; `git diff --check` clean. No Docker. No frontend/API/generation code touched. No model
  files/caches/raw OCR/rendered images/source PDFs/private paths committed; `local_operator_baselines/`
  stays ignored. **NOT committed.**

---

## Phase 2 slide-raster OCR ingestion — **Slice 176G local-Chandra structured-OCR rerun gate; ran local Chandra on real slides; committed `0bc9230` / merged to trunk.**

- **phase=Phase 2 slide-raster OCR ingestion** · **slice=176G (local-Chandra rerun gate)** ·
  **doc=`docs/TABLE_STRUCTURE_PHASE2_LOCAL_CHANDRA_OCR_GATE.md`** ·
  **branch=`slice176g-local-chandra-ocr-rerun-gate`** · **judge_ready=false** · **repair_ready=false**.
- **Why this slice.** 176F recommended `install_local_chandra_and_rerun_gate`: Tesseract read prose
  but failed the dense Gini/proximity grids. This slice ran the local **Chandra OCR 2 GGUF** route
  (`llama.cpp`/`llama-server`, `Q5_K_M`+self-generated `mmproj`, RTX 5070 Ti, the Slice-41 path) on the
  same representative slide categories. The `chandra-ocr` pip package (hf/vllm/cli) is **not installed**;
  the GGUF route is local-only (no cloud, no API).
- **Produce-before-scaffold.** Rendered representative pages (PyMuPDF) → local `llama-server` image path
  (`enable_thinking=false`, `--image-min-tokens 1024`, `--temp 0`); parsed layout-HTML **structurally
  only**; masked Gini recompute routed through the **real** `_recompute_weighted_gini`, gated on a
  credible column-aligned class-count grid, with the printed Gini decimal **excluded** as an answer.
- **Real gate result (closed):** `chandra_status=ran_local` · `chandra_mode=gguf_local` ·
  `cloud_ocr_used=false` · `model_files_committed=false` · `raw_chandra_output_committed=false` ·
  `chandra_structured_table_quality=clean` · `chandra_dense_grid_quality=clean` (the dense **5×5
  proximity matrix Tesseract failed in 176F was recovered**) · `chandra_math_quality=partial` (LaTeX on
  the softmax slide) · `proximity_matrix_recovered=yes` · `nn3_numeric_content_recovered=partial`.
- **Gini (load-bearing, not banked).** The auto-selected representative Gini slide is a **per-split
  summary** (one count + the computed Gini *answer* per row), **not** the raw ≥2-class contingency grid.
  `gini_input_cells_recovered=no` · `gini_input_cells_engine=chandra_local` ·
  **`gini_masked_recompute_from_ocr_status=not_run`** · `warning=answer_or_unrelated_values_not_inputs`.
  A recovered Gini **answer** is not a recovered Gini **input** (GATE-2 held).
- **Decision.** **`corrected_blocker=local_ocr_available_needs_pipeline`** (local structured OCR is
  demonstrably available — Rule B/C blend; Rule C's improve-Tesseract/compare-alternatives would
  misroute). **`recommended_next_step=build_local_slide_ocr_ingestion_pipeline`**, **Gini-proof-gated**:
  its numeric path must first obtain a masked-recompute Gini proof from raw split counts on a
  worked-example slide; until then Gini stays `unverified`. **No ingestion pipeline built.** No cloud
  OCR; no provider/model generation; no guide regeneration; no Layer-2 judge; no repair. Raw Chandra
  output / rendered images / source PDFs / GGUF model files / caches stay in `/tmp`+`~`, uncommitted;
  `local_operator_baselines/` stays ignored. **NOT committed.**

---

## Phase 2 slide-raster OCR verification gate — **Slice 176F correction + Tesseract-first OCR gate; run on real decks; NOT committed.**

- **phase=Phase 2 slide-raster OCR ingestion (reframed)** · **slice=176F (correction + verification gate)** ·
  **test=`test_scripts/test_quality_safety_slide_raster_ocr_gate.py`** ·
  **doc=`docs/TABLE_STRUCTURE_PHASE2_SLIDE_RASTER_OCR_GATE.md`** ·
  **branch=`slice176f-slide-raster-ocr-verification-gate`** · **judge_ready=false** · **repair_ready=false**.
- **Pre-state correction.** Revised **Slice 176E is committed/merged/pushed as `92e389d`** (the earlier
  "NOT committed" handoff text was stale). 176F starts from trunk `chrome-renderer-v1` at `92e389d`.
- **Why this slice.** Direct source inspection overturned the prior "absent / unverifiable-from-source"
  inference. Both decks were re-measured: **near-empty text layers, full-page raster slide images.**
  The blocker is **`extraction_gated_on_raster_ocr`**, not absent. NN3 is **not** clean partial_text.
- **Produce-before-scaffold.** Ran **Tesseract 5.x** (local, PyMuPDF render + preprocessing +
  anchor-cropping) on the **real** decks; masked Gini recompute routed through the **real**
  `_recompute_weighted_gini`, gated by the **176E column-alignment credibility guard**.
- **Real gate result (closed):** `tesseract_status=ran` · `chandra_status=not_available` ·
  `cloud_ocr_used=false` · `tesseract_bulk_text_quality=clean` (gini/chest/patient/softmax/
  cross-entropy keyword layer recovered at clean confidence despite near-empty text layers) ·
  `tesseract_dense_grid_quality=failed` · `tesseract_preprocessed_gini_quality=failed` ·
  `gini_input_cells_recovered=no` · `gini_input_cells_engine=none` ·
  **`gini_masked_recompute_from_ocr_status=not_run`** · `proximity_matrix_recovered=no` ·
  `nn3_numeric_content_recovered=partial`.
- **GATE-2 catch (again).** A naive "finite Gini from a couple of OCR integers" appeared and was
  **rejected** by the credibility guard as the same coincidental false positive — **not banked**.
- **Decision (rule C).** **`corrected_blocker=extraction_gated_on_raster_ocr`** ·
  **`recommended_next_step=install_local_chandra_and_rerun_gate`** (secondary
  `improve_tesseract_preprocessing`). Inputs are present as slide pixels; Tesseract reads prose but
  not the dense numeric grids; Chandra (local) is the designed structured-table OCR — rerun this gate
  before building any ingestion pipeline. **No ingestion pipeline built.** No Chandra ran (unavailable
  locally); no cloud OCR; no provider/model generation; no guide regeneration; no Layer-2 judge; no
  repair. `local_operator_baselines/` + transient render/OCR stay uncommitted/ignored; no raw
  OCR/source/table text, images, or private paths committed. **NOT committed.**

---

## Phase 2 present-input reconstruction — **Slice 176E one-target cold reconstruction attempt; committed/merged as `92e389d`.**

- **phase=Phase 2 present-input reconstruction** · **slice=176E (one input-present target)** ·
  **module=`pipeline/quality_safety_present_input_target_reconstructor.py`** ·
  **test=`test_scripts/test_quality_safety_present_input_target_reconstructor.py`** ·
  **doc=`docs/TABLE_STRUCTURE_PHASE2_PRESENT_INPUT_RECONSTRUCTION.md`** ·
  **branch=`slice176e-reconstruct-present-input-target`** · **judge_ready=false** · **repair_ready=false**.
- **Framing.** 176E does **not** inherit 176D's `computation_input_present_count=5` as proven source
  truth. It is the **validation test** for one selected target: does its computation-**input** table
  actually exist in the source in a form the local extractor can find+parse when the region is
  **rediscovered cold from extraction** (no hand-located region, no spot-check hint, no fixture/answer
  values supplied to the parser)?
- **Selected target:** `gini_chest_pain` · family `weighted_gini` ·
  `selection_reason=simplest_row_cell_mapping`+`cleaner_extraction_region` (categorical 2-class split;
  avoids reusing `gini_weight_gt_176`'s hand-located spot-check region and avoids chaining a downstream
  formula). Non-selected: other 4 input-present → `deferred_by_scope`; `proximity_4_3` → answer_output_only;
  `weighted_weight_impute` → inconclusive.
- **GATE-2 catch (the key event).** A first naive mapper accepted *any* row with ≥2 integers as a Gini
  group and reported `status=parsed`/`created`/`masked_recompute=passed` on the real deck — a **false
  positive**: it grabbed 2 coincidental small integers and the masked recompute returned a finite Gini.
  Verified the measurement (the 2 integer-pair rows were coincidental; no corroborating printed Gini),
  refused to bank it, and added a **column-alignment credibility guard** (≥2 shared x-columns each ≥2
  cells; ≥2 multi-column rows) — magnitude/answer-agnostic, not tuned to any expected value.
- **Real-deck result (closed; gitignored transient harness, local PyMuPDF only):**
  `status=blocked` · `selected_region_origin=discovered_from_extraction` ·
  `parser_received_hand_located_region=false` · `parser_received_spot_check_region_hint=false` ·
  `target_region_status=found` · `row_cell_extraction_status=parsed_from_extraction_output` ·
  `source_input_record_status=not_created` · `source_input_origin=none` · `inputs_status=unavailable` ·
  `machine_consumable_for_recompute=false` · `masked_recompute_status=not_run` ·
  `input_presence_claim_basis=inconclusive` · `input_presence_confirmed_against_source=inconclusive` ·
  `source_confirmation_status=no_input_region_found` · `blocked_by=row_cell_reconstruction` ·
  warning `no_input_columns_found`.
- **Finding/verdict.** Cold rediscovery does **not** expose a machine-parseable, column-aligned
  class-count **input** table for `gini_chest_pain`; the only integers extraction recovers are
  coincidental. **Consistent with** 174A/175A `source_input_missing`, 176A `machine_consumable=0`, 176C
  answer-matrix + `typed_candidate_region_count=0`: the deck presents worked **answers** and tree
  **diagrams**, not typed class-count input tables in extractable text. Therefore **176D's
  `computation_input_present` for this target was prior-evidence optimism, not source-confirmed truth —
  do not keep treating the five-count as hard fact.**
- **next_step=`improve_input_region_evidence`** (inputs, if present, live in tree-diagram **images**/prose
  — a heavier image-region path, not text reconstruction) **or** `choose_different_input_present_target`.
  Slice-level: try at most one more input-present Gini target at the same cold bar; **if it also collapses,
  stop the Ensemble numeric grind and pivot to student-visible table/figure insertion** (the proximity
  answer matrix remains a presentation asset, never a recompute input).
- **Validation:** `compileall api pipeline test_scripts` OK; new test 76/76; 176D input-existence 120/120;
  176C reconstructor + recompute-verifier (311) still pass; `git diff --check` clean. No Docker; no
  `docker compose config`. No Chandra; no cloud OCR; no provider/model generation; no guide regeneration;
  no Layer-2 judge; no repair.
- **NOT committed** (per supervisor stop condition). `docs/SUPERVISOR_PROTOCOL.md` remains untracked;
  `local_operator_baselines/` + the transient real-deck harness stay uncommitted/ignored.

---

## Phase 2 input-existence — **Revised Slice 176D numeric-target input-existence classification; built + run on committed evidence; committed `e3a0102`.**

- **phase=Phase 2 input-existence classification** · **slice=revised 176D** ·
  **module=`pipeline/quality_safety_numeric_target_input_existence.py`** ·
  **test=`test_scripts/test_quality_safety_numeric_target_input_existence.py`** ·
  **branch=`slice176d-target-input-existence-classification`** · **judge_ready=false** · **repair_ready=false**.
- **176C laundering contradiction — resolved from disk before any work.** The pasted
  "masked recompute passed for both families through the verifier" was a **pasted-report
  artifact**, not disk truth. On disk (commit `1771dd9`): the `passed` masked recompute is
  the **synthetic public-safe test** (§4 of the 176C attempt doc) that exercises the chain;
  the **real Ensemble deck** (§5) refused the proximity **answer matrix** and never ran masked
  recompute. Control flow confirmed: `_map_proximity` returns `blocked_by=source_input_mapping`
  and the function returns a **blocked record before** the `_masked_recompute`/verifier call.
  Clean 176C disk verdict: `masked_recompute_status=not_run` · `source_input_record_status=not_created` ·
  `source_input_origin=none` · `machine_consumable_for_recompute=false` ·
  `anti_laundering_answer_matrix_refused=true` · `verifier_called_on_answer_matrix=false` ·
  **`clean_176c_verdict=commit_stands_honest_blocker`**. **1771dd9 stands; no revert.**
- **Reframe.** The honest next question was **not** "detect better" (the abandoned 176D
  region-detector wrongly routed to `improve_target_region_detection` off a zero-candidate
  manifest). The correct question: for each hard-deck numeric target, does the **source** carry
  computation **inputs**, or only the **answer/result**? The abandoned 176D region-detector
  files were discarded (Path 2); a clean branch + classifier replaces them.
- **Classifier (pure, total, closed-vocab, no I/O).** Consumes closed per-target evidence
  descriptors (booleans/tokens/small counts summarizing **already-committed** closed findings) and
  emits a closed per-target + aggregate classification. Reads no files, no PDF, no OCR, no network.
  Never consumes fixture values, answer strings, generated-guide candidates, or hand-authored rows.
- **Committed Ensemble evidence vector (closed):** assembled strictly from prior committed slices —
  173C recoverability (`computation_input_present_count=5`, `partial=2`) + Gini masked-recompute
  spot-check (passed for `gini_weight_gt_176` only); 174A method-gated→`source_input_missing`;
  175A/176A `machine_consumable=0` (no parsed record); 176C proximity→answer matrix + 0 typed
  candidate regions. No raw values/formulas/answer strings baked in.
- **Closed Ensemble classification result:** status=`completed` · source_label=`ensemble` ·
  targets_considered_count=7 · computation_input_present_count=5 · answer_output_only_count=1 ·
  absent_or_not_found_count=0 · inconclusive_count=1 · reconstruction_candidate_count=5 ·
  source_unverifiable_count=1 · **next_step=`reconstruct_present_input_target`** (Part 1F rule A).
  All 7 `machine_consumable_now=false` (no parsed source-input record committed yet).
- **Per-target (closed):**
  - `gini_chest_pain`, `gini_blocked_arteries`, `gini_weight_gt_176`, `total_error_stump_1`,
    `amount_of_say_half_ln_7` → `computation_input_present` · evidence=`existing_recompute_sidecar` ·
    priority=`high` · future=`reconstruct_rows_cells`. (`gini_weight_gt_176` is masked-recompute-proven;
    the other four carry `single_target_spot_check_only`.)
  - `proximity_4_3` → `answer_output_only` · evidence=`mixed` (reconstructed answer matrix + 0 typed
    candidate regions) · priority=`none` · future=`mark_unverifiable_from_source`.
  - `weighted_weight_impute` → `inconclusive` · evidence=`existing_recompute_sidecar` (partial) ·
    priority=`medium` · future=`inspect_more_closed_evidence`.
- **Decision (numeric recompute for Ensemble continues — but pivots target).** Do **not** keep chasing
  proximity's input table and do **not** `improve_target_region_detection` for it: proximity is answer-only
  / unverifiable-from-source. The worthwhile reconstruction work is the **input-present** Gini/total-error/
  amount-of-say targets → `reconstruct_present_input_target`. **Product reframe:** the reconstructable
  proximity **answer/output** matrix remains useful for **student-visible table/figure insertion** even
  though it cannot verify numerics.
- **Validation:** `compileall api pipeline test_scripts` OK; input-existence test 120/120; 176C
  reconstructor + recompute-verifier tests still pass; `git diff --check` clean. No Docker; no
  `docker compose config`. No Chandra; no cloud OCR; no provider/model generation; no Layer-2 judge; no repair.
- **NOT committed** (per supervisor stop condition). `docs/SUPERVISOR_PROTOCOL.md` remains untracked.

---

## Phase 2 row/cell reconstruction — **Slice 176C one-table-family reconstructor; built + run on real deck; NOT committed.**

- **phase=Phase 2 row/cell reconstruction** · **slice=176C (one table family, one deck)** ·
  **module=`pipeline/quality_safety_one_table_family_row_cell_reconstructor.py`** ·
  **test=`test_scripts/test_quality_safety_one_table_family_row_cell_reconstructor.py`** ·
  **chandra_used=false** · **cloud_ocr_used=false** · **judge_ready=false** · **repair_ready=false**.
- **Selection (closed):** selected_source_label=ensemble · selected_target_id=proximity_4_3 ·
  selected_target_family=proximity · selection_reason=`fewer_join_requirements` (proximity is a single
  ratio; weighted_average needs aligned values+weights → more joins). non_selected target
  weighted_weight_impute · non_selected_target_reason=`more_join_requirements`.
- **Missing piece found:** linear text extraction collapses tables to one token per line (grid
  destroyed); the genuine reconstruction step is **spatial clustering of positioned tokens
  (`{x,y,text}`) into rows/cells**. The reconstructor consumes already-extracted positioned tokens
  (text-extractable deck → `local_ocr_status=skipped`, no OCR/PDF/network in the module).
- **Synthetic proof (test):** reconstruct → inputs → **masked** recompute through the REAL verifier:
  proximity per-tree `same_terminal_node` indicators recompute the ratio and weighted_average
  values+weights recompute the mean, both with the answer hidden from the parser. Anti-laundering proven:
  a proximity *matrix* (decimal answer cells) and a lone result value are refused as inputs.
- **Real-deck attempt (Ensemble proximity region, gitignored harness, closed labels only):**
  status=`blocked` · target_region_status=`found` · crop_or_region_input_status=`available` ·
  row_cell_extraction_status=`parsed_from_extraction_output` (grid reconstructed: rows/cols/numeric
  cells all nonzero) · source_input_record_status=`not_created` · source_input_origin=`none` ·
  machine_consumable_for_recompute=`false` · masked_recompute_status=`not_run` ·
  blocked_by=`source_input_mapping` · warnings include `answer_matrix_not_input`.
  **Finding:** the source contains the proximity **answer matrix** (decimal values), not the per-tree
  **inputs** (leaf assignments / same-terminal-node counts). The reconstructor correctly refused to
  launder matrix answers into inputs. hand_authored_rows / fixture_derived / answer_string_derived /
  guide_candidate_derived / raw_values_committed / raw_ocr_committed all `false`.
- **next_step=`target_region_detection_for_numeric_tables`** — the reconstructor works; the gap is now
  an **input** numeric table that appears **absent** for proximity_4_3 (answer-only source). This
  corroborates 174A/175A `source_input_missing` and trends toward classifying proximity_4_3 as
  **absent-in-source** (not extraction-gated → not an OCR problem). No Chandra; no cloud OCR; no
  provider/model generation; no Layer-2 judge; no repair.

---

## Phase 2 table-pilot seam map — **Slice 176B NN3 check + seam map; docs-only; committed `0a9794b`.**

- **phase=Phase 2 table-pilot seam map** · **slice=176B (inventory + seam, no extraction code)** ·
  **doc=`docs/TABLE_STRUCTURE_PHASE2_SEAM_MAP.md`** · **chandra_used=false** · **cloud_ocr_used=false** ·
  **judge_ready=false** · **repair_ready=false**.
- **NN3 separate recoverability check:** source_label=nn3 · source_quality=partial_text ·
  targets_considered=5 · existing_structured_source_input_producer_exists=true (unwired numeric chain) ·
  producer_ran=true · producer_output_has_target_records=false · parsed_from_existing_extraction_count=0 ·
  machine_consumable_count=0 · source_input_records_created_count=0 · remaining_source_required_count=5 ·
  **nn3_free_numeric_path_status=`unstructured_text_only`**. The numeric chain
  (safe_numeric_extractor→numeric_extraction_mapper→fact_sheet_producer→recompute_verifier) is pure/unwired
  and consumes caller-supplied sanitized candidates; the extraction-bundle adapter records
  `numeric_observation_recoverable=no`. No new NN3 parser built or hand-authored.
- **Existing visual/table pilot inventory:** existing_visual_manifest_exists=true ·
  existing_visual_asset_extractor_exists=true · existing_table_candidate_manifest_exists=true ·
  existing_table_reconstruction_policy_exists=true · existing_row_cell_reconstruction_exists=false ·
  existing_crop_generation_exists=true · existing_region_detection_reusable=true ·
  existing_stack_outputs_rows_cells=false · existing_stack_outputs_counts_only=true ·
  existing_stack_outputs_region_crops=true · **reuse_boundary=`region_detection_plus_crops`** ·
  **missing_piece=`row_cell_reconstruction`**.
- **Slice 60 stash (read-only name-only/stat; not applied/popped/dropped):** slice60_stash_relevant=false ·
  slice60_stash_relevance=`selection_trace` (visual markdown insertion / downstream rendering, not numeric
  row/cell extraction; potentially relevant later to student-visible table insertion only).
- **Reconstructor seam contract:** input=region/crop/table-candidate handles + local private OCR + safe
  page/region ref; output=`row_cell_extraction_status` + `source_input_record_status` +
  origin must be `parsed_from_extraction_output` to count, shaped to drop into the verifier's
  `source_inputs_by_target` ({method, inputs, value_kind, confidence}); privacy_contract all true;
  success_bar=one_table_family_one_deck_end_to_end + recompute_proof_from_parsed_inputs.
- **Decision-rule next_step=`build_one_table_family_row_cell_reconstructor`** (Slice 176C, option C):
  region detection/crops exist but rows/cells do not. Not another audit, not another source-input bridge,
  not Chandra, not cloud OCR, not a generic framework.

---

## Phase 2 OCR/table-structure extraction — **Slice 176A focused table-structure attempt; committed `b9c6ee9`.**

- **phase=Phase 2 OCR/table-structure extraction** ·
  **reason=175A_proved_existing_outputs_not_machine_consumable** ·
  **previous_recompute_ready_count=2** · **source_input_missing_count=10** ·
  **focused_targets=`proximity_4_3`,`weighted_weight_impute`** ·
  **next_artifact=quality_safety_focused_table_structure_attempt.json** ·
  **local_private_only=true** · **chandra_used=false** · **cloud_ocr_used=false** ·
  **hand_authored_target_inputs=false** · **fixture_values_used_as_source_inputs=false** ·
  **guide_candidate_values_used_as_source_inputs=false** · **existing_table_stack_checked=true** ·
  **judge_ready=false** · **repair_ready=false**.
- **Existing-stack inspection (reuse-before-rebuild):** `table_candidate_manifest.py`
  derives candidates from the sanitized `visual_assets_manifest` and emits **counts +
  decision tokens only** (rows/columns/numeric_cell_count), never cell values;
  `table_reconstruction_policy.py` is **decision-only** and explicitly does NOT reconstruct
  rows/cells, OCR, or read values; `visual_asset_extractor.py` produces **image crops**, not
  numeric cells; the recompute `source_inputs_by_target` path consumes a fact sheet's
  structured `computation.inputs`, which nothing parses from extraction for these targets.
  Conclusion: existing stack detects table **regions** but reconstructs **no rows/cells** →
  `reuse_path=existing_visual_manifest` (regions reusable) · `blocker=table_structure_missing`.
- **Focused attempt result (real current state, no synthetic inputs):**
  status=`blocked` · targets_considered=2 · structured_rows_count=0 ·
  source_input_records_created_count=0 · machine_consumable_count=0 ·
  hand_authored_target_map_count=0 · fixture_derived_count=0 · answer_string_derived_count=0.
  Both targets → table_structure_status=`not_found`, source_input_record_status=`not_created`,
  source_input_origin=`none`, machine_consumable_for_recompute=false,
  blocked_by=`table_structure_missing`.
- **Optional recompute proof:** did NOT run (no source-input record was created with
  `parsed_from_extraction_output`).
- **Artifact / harness:** added pure `pipeline/quality_safety_focused_table_structure_attempt.py`
  (closed-vocabulary, two-target only, reuses `SUPPORTED_METHODS`; rejects hand-authored /
  fixture-derived / answer-string origins; `ocr_prose_only` never machine-consumable) + focused
  tests. No generated `.json` artifact committed (runtime/private only).
- **Decision-rule next_step=`OCR_table_structure_extractor`** — table regions are detectable but
  no current code reconstructs numeric cell rows; cell-value recovery needs an OCR/table-structure
  extractor targeting those regions. local-only, no Chandra, no cloud OCR. scope=minimal.

---

## Phase 2 source-derived numeric verification — **Slice 174A source-input bridge proof run; NOT committed.**

- **phase=Phase 2 source-derived numeric verification** ·
  **input_basis=masked_gini_recompute_passed_and_2_method_gated_targets_remaining** ·
  **numeric_context_plumbing_stopped=true** · **student_visible_output_invariant=true** ·
  **real_artifact=closed_recompute_proof_for_method_gated_ensemble_targets** ·
  **generation_reproducibility_gap=true** ·
  **next_step=source_input_provenance_recovery** · **judge_ready=false** ·
  **repair_ready=false**.
- **Slice 174A closed recompute proof:** recompute_methods_added_count=2 ·
  source_input_bridge_added=true · bridge_scope=minimal ·
  method_gated_target_ids=`proximity_4_3`,`weighted_weight_impute` · targets_considered=12 ·
  previous_independently_verified_count=2 · newly_independently_verified_count=0 ·
  total_independently_verified_count=2 · remaining_method_gated_count=0 · extraction_gated_count=0 ·
  unresolved_for_generation_count=10 · writer_ready_count=2 ·
  fixture_only_values_used_as_truth=false · extracted_answer_text_used_as_truth=false ·
  guide_candidate_values_used_as_truth=false · next_step=source_input_provenance_recovery.
- **Pair proof detail:** NN3 targets_considered=5 · total_independently_verified_count=1 ·
  remaining_blockers `source_required=4`. Ensemble targets_considered=7 · method_gated_before=2 ·
  method_gated_after=0 · newly_independently_verified_count=0 · total_independently_verified_count=1 ·
  remaining_blockers `source_required=4`,`source_input_missing=2`.
- **Negative-proof conclusion:** Slice 174A is a negative proof, not verification progress:
  newly_independently_verified_count=0 and total_independently_verified_count=2. The two targets moved from
  method-gated to source_input_missing; for both `proximity_4_3` and `weighted_weight_impute`,
  source_input_record_exists=false and source_input_record_shape_valid=false. Do not claim 10/12
  recompute-ready.
- **Slice 174A implementation result:** first added exactly the missing method computations (`proximity`,
  `weighted_average`) and an initial closed `source_inputs_by_target` proof input path, but the first proof stayed
  blocked with newly_independently_verified_count=0 and method_gated_after=2. The branch was not committed. The
  slice then continued under the produce-before-scaffold gate and added only a minimal exact Ensemble bridge from
  already-structured source fact-sheet inputs to the existing `source_inputs_by_target` proof input. The real local
  artifacts still provide no source-derived structured records for `proximity_4_3` or `weighted_weight_impute`
  (`source_input_projection_count=0`), so both targets remain honestly blocked as `source_input_missing` and not
  writer-ready. The proof did not use fixture expected values, extracted answer text, or guide candidate values as
  truth.
- **Decision-rule next_step:** `source_input_provenance_recovery`. This is not another bridge attempt. The next
  artifact must classify target inputs as `parsed_from_extraction_output`, `hand_authored_target_map`, or
  `not_machine_consumable`. If inputs are not machine-consumable from existing extraction, route to
  `OCR_table_structure_extraction`. Do not build a recompute-method registry; do not continue numeric-context
  plumbing; do not regenerate guides; do not run Layer-2 judge.
- **next_step=closed_decision_from_real_recompute_proof:** `source_input_provenance_recovery`.

---

## Phase 2 source extraction / reproducible measurement — **Slice 173C audit committed.**

- **phase=Phase 2 source extraction / reproducible measurement** ·
  **numeric_context_plumbing_stopped=true** · **student_visible_output_invariant=true** ·
  **real_artifact=corrected_extraction_provenance_audit_plus_masked_gini_recompute** ·
  **generation_reproducibility_gap=true** ·
  **next_step=add_missing_recompute_methods** · **judge_ready=false** ·
  **repair_ready=false**.
- **Produce-before-scaffold gate:** the required artifact is a real closed extraction run on the NN3 and
  Ensemble source decks using existing extraction/OCR/table paths, followed by a closed classification of the
  remaining numeric failures. The artifact did not exist before this run. Existing producer code does exist:
  `pipeline.extract.extract_file`. Therefore the correct action was to run it, not build more numeric-context
  plumbing or an audit scaffold.
- **Slice 173C status:** abandoned without commit. It exposed two real findings: verified numeric context can
  affect only 2 of 12 targets, and faithful Builder reruns need a complete persisted generation profile. No
  dry-run/operator scaffold from 173C was kept. The old operator branch was abandoned and not committed.
- **SUPERVISOR_PROTOCOL Gate 2 fired:** the first extraction framing was too clean for the prior evidence. The
  corrected framing is `ensemble=image_heavy`, not `clean_text`; `OCR_path_used=existing_local_tesseract`, not
  `none`; `nn3=partial_text`. The measurement rule is `question_2_5=is_the_artifact_measuring_what_we_think`:
  surprisingly clean results require provenance and semantics verification before routing.
- **Closed extraction provenance/semantics verification:** source_decks_available=true · extraction_ran=true ·
  source_identity_matches_expected_deck=true · extraction_was_run_against_raw_source=true ·
  raw_source_pdf_checked_for_both_decks=true ·
  extraction_output_is_prior_processed_text=false · recoverability_semantics=inputs_not_answer_strings ·
  existing_producer_used=`pipeline.extract.extract_file` · OCR_path_used=existing_local_tesseract ·
  table_structure_path_used=none · targets_considered=12 · extraction_gated_count=0 ·
  method_gated_count=2 · absent_or_not_found_count=0 · already_recoverable_count=10 ·
  partial_recovery_count=2.
- **High-risk Ensemble Gini masked recompute spot-check:** source_label=ensemble ·
  target_id=`gini_weight_gt_176` · raw_source_checked=true · extraction_input_kind=raw_source_pdf ·
  OCR_method_used=existing_local_tesseract · computation_inputs_visible_in_raw_source=true ·
  computation_inputs_recovered_by_extraction=true · answer_value_string_present=true ·
  answer_value_string_masked_before_recompute=true · gini_recomputed_from_recovered_inputs=true ·
  recomputed_value_matches_fixture_within_tol=true · recompute_used_only_inputs_not_answer_string=true ·
  recoverable_by_inputs_not_answer=true · spot_check_status=passed. Fixture expected value was withheld from
  the recompute call and used only for the final tolerance comparison.
- **NN3 closed extraction:** source_available=true · extraction_ran=true · extraction_quality=partial_text ·
  targets_considered=5 · input_evidence_checked_count=5 · answer_value_only_match_count=0 ·
  label_only_match_count=0 · computation_input_present_count=5 · computation_input_partial_count=0 ·
  computation_input_absent_count=0 · already_recoverable_count=5 · extraction_gated_count=0 ·
  method_gated_count=0 · absent_or_not_found_count=0 · recoverability_report_valid=true.
- **Ensemble closed extraction:** source_available=true · extraction_ran=true · extraction_quality=image_heavy ·
  targets_considered=7 · input_evidence_checked_count=7 · answer_value_only_match_count=0 ·
  label_only_match_count=0 · computation_input_present_count=5 · computation_input_partial_count=2 ·
  computation_input_absent_count=0 · already_recoverable_count=5 · extraction_gated_count=0 ·
  method_gated_count=2 · absent_or_not_found_count=0 · recoverability_report_valid=true.
- **Reproducibility gap:** generation_settings_persisted_to_job_artifact=false for the local closed artifact set;
  reproducible_builder_profile_available=false; missing_generation_settings_count=3;
  missing_generation_settings_categories=`length`, `source_labels_input_mode`, `exported_job_manifest`;
  impact=`manual_regeneration_not_reproducible`,`provenance_fragile`,`operator_equivalence_blocked`;
  recommended_next_slice_if_prioritized=`persist_generation_settings_to_job_artifact`.
- **Decision:** existing extraction already recovers the needed supported-method input families, while the remaining
  Ensemble targets are method-gated rather than extraction-gated. Per the masked recompute proof, route next to
  `add_missing_recompute_methods`. Do not route to OCR from this run, do not create 173D, do not continue verified
  numeric-context plumbing, do not regenerate guides, and do not run Layer-2 judge. Slice 174A pass condition is
  honest movement, not a forced 12/12 green result; if 174A reports a surprisingly clean 12/12, Gate 2 must fire
  again before banking it.
- **Slice 174A prepared, not started here:** branch `slice174a-add-missing-recompute-methods`; real artifact is a
  closed recompute proof run showing the two previously method-gated Ensemble targets are now recomputed or still
  honestly blocked, and whether total independently verified targets increased. Implement exactly the missing
  recompute methods and run the proof in the same slice; do not build a registry/framework/dry-run, do not touch
  prompt-generation context, and do not use fixture expected values, extracted answer text, or guide candidate
  values as truth.

---

## Slice 173A — **Recompute verifier catches wrong printed values**, on `slice173a-recompute-verifier-catches-wrong-values`. **COMMITTED `1905af7`; merged to `chrome-renderer-v1`.**

- **Recompute-first proof slice, not generation wiring and not score-laundering.** After Slice 172
  reduced trusted leak signals, the dominant measured blocker is **numeric correctness — specifically
  `found_but_wrong_value`**: the guides confidently print wrong committed numbers. This slice proves
  the recompute engine can **independently derive the committed fixture values** and **diagnose the
  wrong printed values**, without loosening matchers, inventing values, or changing generation.
- **phase=Phase 0 numeric product quality** · **slice173a_focus=recompute_verifier_catches_wrong_printed_values** ·
  **input_basis=post_slice172_found_but_wrong_value_dominant** · **generation_wiring=false** ·
  **next_required_product_slice=173b_verified_numeric_generation_context** · **leak_prompt_changes=false** ·
  **numeric_matcher_changes=false** · **fixture_expected_value_changes=false** · **repair_changes=false** ·
  **judge_ready=false** · **repair_ready=false**.
- **Post-Slice-172 closed rerun (Part 0; scorer `d517601`, candidates `nn3_v6.md`/`ensemble_v6.md`,
  no regeneration):** NN3 numeric buckets `found_and_matched=0` / `found_but_wrong_value=2` /
  `genuinely_missing=3`; Ensemble `found_and_matched=1` / `found_but_wrong_value=6`. Numeric is the
  lead blocker; mock shortfall is advisory (non-blocking); leak reduced to a small genuine+signature
  residue; **coverage now blocking** (NN3 ratio 0.60, Ensemble 0.6154 < 0.90) — tracked as a side
  effect, not the lead; Layer-2 judge deferred.
- **Change (`pipeline/quality_safety_recompute_verifier.py`, additive only — existing v1 API untouched):**
  new closed *golden-target recompute proof* layer: `golden_label_recompute_plan` (parses a closed
  `{method, inputs}` plan **from the committed golden label only** — `cross_entropy_neg_ln_X` → `-ln(X)`;
  `amount_of_say_half_ln_N` → `0.5·ln(N)` via `total_error = 1/(N+1)`), `build_golden_target_recompute_proof`
  (recomputes via the existing production methods, verifies against the committed fixture value within
  the **existing** tolerance, and — given a read-only closed numeric-matcher classification — reports a
  `wrong_value_detected` **diagnostic**), and `summarize_golden_target_recompute_proof`. Closed enums only:
  `recompute_status ∈ {recomputed, formula_verified, source_required, unsupported, verifier_error}`,
  `verified_value_kind`, `confidence`, `guide_candidate_status`. Honest degradation: targets without
  a label-derivable plan → `source_required` (supported family, no committed inputs) or `unsupported`
  (no supported method); no value invented, no confidence promotion.
- **No-laundering correction (the load-bearing fix this slice exists for):** wrong-value detection is
  **proof that a printed value is wrong**, never proof that the writer should receive the committed value.
  The record distinguishes **four** closed facts: `wrong_printed_value_detected_when_candidate_supplied`
  (diagnostic), `committed_value_available` (the fixture has an expected value), `independently_verified_for_generation`
  (recompute proof), and `writer_should_receive_committed_value` (policy). `writer_should_receive_committed_value`
  is `true` **only** when `recompute_status ∈ {recomputed, formula_verified}` **and**
  `recomputed_matches_committed_fixture=true` **and** `confidence ∈ {high, medium}`. For
  `source_required` / `unsupported` / `verifier_error` — or any target whose only available value is the
  committed expected fixture — it is `false`. A committed fixture value scores/validates recompute; it is
  **never** treated as generation-ready numeric context unless independently recomputed/formula-verified.
- **Recompute-first invariant proven (not known_numbers):** the disagreement test deliberately sets a
  wrong committed value and the engine **disagrees** (`recompute_disagrees_with_committed_fixture`)
  rather than trivially matching — there is no answer table. No fixture expected value/tolerance edited;
  numeric matcher consumed read-only and not loosened; no prompt/generation/frontend/API change;
  offline judge/repair stay frozen.
- **Tests (`test_scripts/test_quality_safety_recompute_verifier.py`, synthetic public-safe only):**
  plan parsing + no-answer-table; committed values independently derived, matched & writer-ready; disagreement
  detection; **no-laundering gate** (`recomputed`/`formula_verified` + match + high/medium → writer-ready;
  `source_required`/`unsupported` with a committed fixture value → **not** writer-ready even when the
  printed value is wrong); wrong-value detected while writer stays not-ready; source_required vs unsupported
  honest degradation with no invention; malformed-input closed degrade + input-spec non-mutation; closed
  schema/enums + no-leak sweep. **Suite 203 pass (was 178).**
- **Real closed local run (committed golden specs × post-Slice-172 candidates `nn3_v6.md`/`ensemble_v6.md`,
  no regeneration):**
  - **Pair:** recompute_proof_ran=true · total_targets=12 · recomputed=2 · formula_verified=2 ·
    source_required=8 · unsupported=2 · verifier_error=0 · committed_fixture_match=2 ·
    wrong_printed_value_detected=8 · independently_verified_for_generation=2 ·
    writer_should_receive_committed_value=**2** · unresolved_for_generation=**9**.
  - **NN3:** target_count=5 · recomputed=1 · formula_verified=1 · source_required=4 · unsupported=0 ·
    verifier_error=0 · committed_fixture_match=1 (`cross_entropy_neg_ln_0.57`, matches committed) ·
    wrong_printed_value_detected=2 · independently_verified_for_generation=1 ·
    writer_should_receive_committed_value=1 · unresolved_for_generation=4 · warnings `recompute_plan_unavailable`.
    The single recompute-verified target is currently printed **wrong** → it (and only it) is writer-ready.
  - **Ensemble:** target_count=7 · recomputed=1 · formula_verified=1 · source_required=4 · unsupported=2 ·
    verifier_error=0 · committed_fixture_match=1 (`amount_of_say_half_ln_7`, matches committed) ·
    wrong_printed_value_detected=6 · independently_verified_for_generation=1 ·
    writer_should_receive_committed_value=1 · unresolved_for_generation=5 · warnings
    `recompute_plan_unavailable`,`unsupported_method`. The single recompute-verified target is printed
    **wrong** → it (and only it) is writer-ready.
  - `wrong_printed_value_detected` (NN3 2, Ensemble 6 = 8) equals the matcher's `found_but_wrong_value`,
    cross-validating both engines. But only the **2** independently formula-verified values are writer-ready;
    the other **9** wrong/missing targets stay `unresolved_for_generation` — no laundering.
- **173B readiness:** Slice 173A proves wrong printed values are **detectable** and makes the **2**
  independently formula-verified values generation-ready; it does **not** make all committed fixture
  values writer-ready (`unresolved_for_generation_count=9`). For the `source_required`/`unsupported`
  targets, **173B must either** derive computation inputs from source/fact-sheet extraction **or** leave
  those values unavailable to generation and force the writer to a closed fallback. **173B must not inject
  committed expected fixture values directly into generation.**
- **Validation (no Docker):** `python -m compileall api pipeline test_scripts`;
  `test_quality_safety_recompute_verifier` (203), `test_quality_safety_eval_harness` (577),
  `test_quality_safety_unified_qa` (73), `test_guide_quality_prompt_contract` (383),
  `test_guide_quality_contract_lint` (150); `git diff --check` clean.
- **Changed files:** `pipeline/quality_safety_recompute_verifier.py`,
  `test_scripts/test_quality_safety_recompute_verifier.py`, `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`. **NOT COMMITTED.** No guide regenerated; no
  generation wiring touched.

---

## Slice 172 — **Product genuine-leak prompt discipline**, on `slice172-product-genuine-leak-discipline`. **NOT COMMITTED.**

- **Product prompt slice, not a detector slice.** Slice 171 made the Phase 0 leak count trustworthy by separating
  legitimate study-question scaffolding from genuine deliberation. The solved-mock regenerated guides still failed
  `leaked_reasoning` on a small set of **trusted genuine** signals (NN3 `signal_count=2`: signature 1 + genuine
  structural 1; Ensemble `signal_count=6`: signature 4 + genuine structural 2). So prompt refinement is now justified
  by trusted product defects, not by the previously-inflated solved-mock false positives.
- **phase=Phase 0 product quality** · **slice172_focus=genuine_leak_prompt_refinement** ·
  **input_basis=slice171_trusted_leak_classification** · **false_positive_scaffolding_separated=true** ·
  **prompt_changes_target_genuine_signals_only=true** · **numeric_matcher_changes=false** · **detector_changes=false** ·
  **next_step=commit_then_manual_regenerate_and_rerun_phase0**
- **Change (`pipeline/guide_quality_prompt_contract.py`, core rules only — applies to every guide at every depth):**
  - **New rule — student-facing vs model-facing questions.** Explicitly *separates* the two: the guide **may** pose
    questions when they are student-facing learning structure (solved mock exam, practice questions, self-test
    checklist, active-recall prompts, exam-alert callouts, section headings framed as concept questions — all allowed
    and encouraged). What is prohibited is the **model posing its own unresolved question in explanatory prose**: an
    explanatory sentence/paragraph must state the settled answer and must not convert unresolved deliberation into a
    rhetorical question. Closes with "Question marks and concept-framed headings are never banned on their own; only
    unresolved model-facing uncertainty is." → **no global question-mark ban, no rhetorical-heading ban.**
  - **Strengthened numeric final-answer rule** (existing "Preserve every numeric example and target"): now requires
    **one committed final value** (kept the back-compat phrase "final committed value"), allows two-or-more candidate
    values **only when the contrast is explicitly pedagogical and unambiguous** (e.g. a deliberately-shown wrong answer
    beside the correct one), and states "never leave competing values unresolved as the final answer". Closed fallbacks
    "Not specified in the provided material." / "Not verified from provided material." retained.
  - **Preserved Slice 168 improvements:** the broad flat denylist stays removed; ordinary teaching phrases stay allowed
    ("You need to normalize the weights.", "This will likely appear on the exam.", "This probably matters because…");
    no `known_numbers` infrastructure; no hardcoded private values; concrete prohibited forms (`"Wait"`, `"Actually"`
    self-correction, `"unclear"`, `"we'll trust"`, `"the table is confusing"`, `"= ?"`, `"≈ ?"`) still prohibited.
- **No change to:** `pipeline/quality_safety_eval_harness.py`, the numeric matcher / numeric fixtures, the wired
  `quality_safety_leak_scanner`, generation runtime wiring, frontend/API, or production judge/repair readiness
  (`judge_ready=false`, `repair_ready=false` stay frozen). No detector/eval change; no repair added.
- **Tests (`test_scripts/test_guide_quality_prompt_contract.py`):** new
  `test_student_vs_model_facing_question_discipline` (synthetic public-safe only) asserts the contract separates
  student-facing from model-facing questions; permits solved-mock/practice/self-test/active-recall/exam-alert/concept
  headings; prohibits the model posing its own unresolved question in prose; keeps the concrete self-correction /
  source-confusion / numeric-uncertainty forms prohibited; requires one committed final value or the closed
  unverifiable fallback; does **not** flat-ban ordinary words (`maybe`, `probably`, `likely`, `we need to`,
  `this might be`, `the material doesn't say`, `I will`, `I should`); contains **no** global question-mark ban; and
  carries no hardcoded private numeric literal (4+ digit scan). Suite: **383 pass** (was 253).
- **Validation (no Docker):** `python -m compileall api pipeline test_scripts`; `test_guide_quality_prompt_contract`
  (383), `test_guide_quality_contract_lint` (150), `test_quality_safety_eval_harness` (577),
  `test_quality_safety_recompute_verifier` (99), `test_quality_safety_unified_qa` (73); `git diff --check` clean.
- **Changed files:** `pipeline/guide_quality_prompt_contract.py`, `test_scripts/test_guide_quality_prompt_contract.py`,
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`. **NOT COMMITTED.** No guide regenerated in
  this slice; next step is manual regenerate + rerun Phase 0 against the now-trustworthy genuine leak signal.

---

## Slice 171 — **Phase 0 leak structural-signal classification**, on `slice171-phase0-leak-structural-classification`. **Committed `023b55d`; on trunk `chrome-renderer-v1`.**

- **Measurement-trust slice, not prompt tuning.** Slices 168–170 trusted the leak signal as blocking, but a closed
  audit of the solved-mock regenerated guides showed the blocking structural `32` in **both** NN3 and Ensemble was
  mostly legitimate study-guide question scaffolding, not genuine model deliberation (NN3 genuine 1/32, Ensemble
  2/32). The overbroad source was the Phase 0 eval-harness `_check_leaked_reasoning` (every line containing `?`
  minus narrow mock headings counted as structural uncertainty), **not** the wired `quality_safety_leak_scanner`.
- **phase=Phase 0 measurement trust** · **slice171_focus=leak_structural_signal_classification**
- **source_of_problem=phase0_eval_harness_question_line_heuristic** · **solved_mock_false_positive_risk=true** ·
  **do_not_weaken_true_positive_leak_detection=true** · **generation_prompt_changes=false** · **numeric_changes=false** ·
  **next_step=rerun_solved_mock_guides_after_leak_classification (done — see below)**
- **Change (`pipeline/quality_safety_eval_harness.py`):** each question-like line is now classified into one **closed**
  category — `genuine_deliberation_or_uncertainty`, `mock_or_practice_question`, `self_test_or_checklist_question`,
  `exam_alert_or_instructional_question`, `worked_solution_prompt_question`, `source_citation_or_page_ref_pattern`,
  `rhetorical_or_concept_heading_question`, `other_false_positive`, `unknown_needs_operator_review`. The check blocks
  **only** on `genuine_deliberation_or_uncertainty` and `unknown_needs_operator_review` (plus the unchanged
  whole-text `_LEAK_PATTERNS` signature scan); the other categories are reported as non-blocking counts.
  - Genuine detection (priority-first) = unresolved numeric `= ?`/`≈ ?`/`≃ ?`, any signature word on the line, or a
    strong line-level uncertainty phrase (`not sure`, `could be either`, `which value is right`, `conflicting`, …).
    An ambiguous soft hint (`maybe`/`perhaps`/…) with no strong signal and no scaffold shape → `unknown` (still blocks).
  - New output fields: `genuine_structural_uncertainty_count`, `non_leak_question_scaffold_count`,
    `structural_question_like_count`, `structural_signal_categories` (closed counts), `warnings` (closed tokens).
    Backward-compat: `structural_uncertainty_count` now = blocking structural count (genuine + unknown), so the
    existing "mock questions ignored → 0" behavior holds; `signal_count`/`signature_count` semantics preserved.
  - Removed the now-dead narrow `_MOCK_LINE_RE`/`_is_mock_question_line`; the classifier reuses the Slice 169
    count-only mock matcher for the `mock_or_practice_question` category (never decides blocking on its own).
  - **No prompt/generation change, no numeric matcher change, no tolerance change, no aggregator hiding/warning
    suppression, recompute-first authoritative, judge frozen (`judge_ready=false`, `repair_ready=false`), no repair.**
- **Tests:** `test_leaked_reasoning_structural_classification` (synthetic public-safe text only) — signature
  self-correction blocks; unresolved numeric blocks as genuine with `signature_count=0`; competing values block;
  mock/self-test/checklist/worked/exam-alert/rhetorical/source-ref scaffolding are non-blocking and separated;
  mixed (one genuine + 3 practice) blocks on the genuine leak while reporting the 3 separately; soft hint →
  `unknown` still blocks; plain study question → non-blocking `other_false_positive`; closed-shape + no-raw-text guards.
- **Real local closed rerun (current solved-mock regenerated guides, recomputed OLD numbers match prior run exactly):**
  - **NN3:** OLD `signal_count=33` / `structural_uncertainty_count=32` → NEW `signal_count=2`, `signature_count=1`,
    `genuine_structural_uncertainty_count=1`, `non_leak_question_scaffold_count=31`
    (categories: mock 6, source_ref 1, other_false_positive 24, all others 0). **Leak still blocking** (genuine + signature).
    `detector_false_positive_reduced=true`.
  - **Ensemble:** OLD `signal_count=36` / `structural_uncertainty_count=32` → NEW `signal_count=6`, `signature_count=4`,
    `genuine_structural_uncertainty_count=2`, `non_leak_question_scaffold_count=30`
    (categories: mock 8, other_false_positive 22, all others 0). **Leak still blocking** (genuine + signature).
    `detector_false_positive_reduced=true`.
  - Both guides' genuine counts (1, 2) match the prior closed audit exactly; no `unknown_needs_operator_review` hits.
- **Decision rule outcome:** leak remains blocking due to **genuine** signals in both guides → per the slice rule the
  next slice **can** be product-prompt refinement against the (now trustworthy) genuine leak signal. Numeric remains the
  other open blocker; leak false-positive inflation is no longer masking it.
- **Validation (no Docker):** `python -m compileall api pipeline test_scripts`; `test_quality_safety_eval_harness`
  (577 pass), `test_quality_safety_recompute_verifier` (99), `test_quality_safety_unified_qa` (73),
  `test_guide_quality_prompt_contract` (253), `test_guide_quality_contract_lint` (150); `git diff --check` clean.
- **Changed files:** `pipeline/quality_safety_eval_harness.py`, `test_scripts/test_quality_safety_eval_harness.py`,
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`. **NOT COMMITTED.**

---

## Slice 170 — **Phase 0 numeric label-attribution matcher**, on `slice170-phase0-numeric-label-attribution`. **NOT COMMITTED.**

- **Produce-before-scaffold gate:** real Layer-1 measurement already exists; this slice does **not** regenerate any
  guide. After Slice 169 the mock counter is trusted, but numeric correctness was **not**: all expected values are
  literally present while all targets classified `label_not_found` — the blocker was **attribution**, not absence.
- **phase=Phase 0 measurement trust** · **slice170_focus=numeric_label_attribution**
- **regeneration_blocked_until_numeric_attribution_trusted=true** · **numeric_values_present_but_unanchored=true** ·
  **do_not_widen_tolerances=true** · **do_not_edit_expected_values=true** ·
  **next_step=rerun_current_guides_after_numeric_attribution_then_decide_regeneration**
- **Matcher (`pipeline/quality_safety_eval_harness.py`):**
  - Numeric targets now carry optional **safe alias / concept-anchor metadata** (`aliases`, capped, validated by
    `_safe_golden_label`, deduped). The matcher anchors on the authored label **OR** any approved alias
    (`_numeric_anchor_terms`, `_label_value_scan_multi`), so a value is attributed via the phrasing the guide
    actually prints — not only the fixture's internal label code.
  - Added a **committed worked-final-answer** reading (`_committed_answer_numbers`): the number after the last
    result separator (`= / ≈ / ≃ / →`) is credited when internally consistent and within the **existing** tolerance,
    so a correct final answer is not failed as a contradiction by its own working steps. Two different committed
    answers still contradict; a wrong committed answer is still wrong.
  - **Proximity tightened:** value-on-next-line only fires when the anchor stands alone as a header (stripping it
    leaves no other word tokens), so a mid-sentence "Covered topics:" mention never proximity-grabs an unrelated
    next-line number.
  - Closed per-target diagnostic extended (`classify_numeric_target`): adds `alias_found`, `alias_matched`
    (enum/fixture-token only), `proximity_mode` (`same_line`/`next_line`/`none`), `competing_value_count`.
  - **No tolerance widened, no expected value edited, wrong/competing values still fail, stray values still not
    credited, recompute-first stays authoritative, leak detection untouched, judge frozen
    (`judge_ready=false`, `repair_ready=false`), no repair, no generation/prompt change, no regeneration.**
- **Fixtures (`golden_pairs/nn3.json`, `ensemble.json`): alias metadata ONLY** — every expected value and tolerance
  is unchanged (guarded by `test_golden_pair_alias_metadata_guard`). Aliases are generic public ML terms already
  implied by the existing label codes (e.g. `chest pain`, `amount of say`, `weight > 176`, `cross-entropy`,
  `raw versicolor`); no private guide/source snippets.
- **Real local closed diagnostic (rerun on current unchanged local guides; truthful/mixed, NOT a green pass):**
  - **NN3 (5 targets):** `found_and_matched` 0 · `format/context_missed` 0 · `found_but_wrong_value` 5
    (all `competing_unresolved_values`) · `genuinely_missing` 0. Every target now `alias_found=1`, `value_found=1`
    (concept present + value present) — the previous `label_not_found` was a matcher artifact. Gate
    pass=0/fail=5/missing=0, `failed`, blocking.
  - **Ensemble (7 targets):** `found_and_matched` 1 (`gini_chest_pain`=0.47, `worked_final_answer`) ·
    `format/context_missed` 0 · `found_but_wrong_value` 5 (competing) · `genuinely_missing` 1
    (`gini_weight_gt_176`, `label_present_value_absent`). Gate pass=1/fail=5/missing=1, `failed`, blocking.
  - **Interpretation:** trusted matches = 1 (ensemble chest-pain). No target is a **confirmed** wrong value — the
    competing buckets hold the correct value co-located with worked-step numbers on number-dense lines, so the
    bounded matcher safely refuses to credit them. The remaining blocker is **attribution against co-located worked
    numbers**, not numeric absence. **`numeric_correctness` is now a truthful detector but not green → regeneration
    stays blocked.**
- **Tests:** added `test_numeric_label_attribution_aliases`, `test_numeric_alias_gate_credit_and_no_launder`,
  `test_golden_pair_alias_metadata_guard` (synthetic public-safe text only). `test_quality_safety_eval_harness.py`
  554 passed / 0 failed; recompute_verifier 99/0; unified_qa 73/0; prompt_contract 253/0; contract_lint 150/0;
  `git diff --check` clean. **Docker not run; `docker compose config` not run.**
- **Safety:** Slice 60 trace stash parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted; no
  private guide/source/OCR/table/caption text, paths, filenames, hashes, byte counts, screenshots, provider
  payloads, prompts/responses, or secrets committed. **Slice 170 is NOT committed.**

---

## Slice 169 — **Phase 0 numeric-matcher + mock-counter measurement-trust sanity**, on `slice169-phase0-matcher-mock-sanity`. **NOT COMMITTED.**

- **Produce-before-scaffold gate:** the real Phase 0 current-pair run already exists; this slice does **not** regenerate
  any guide. It fixes **measurement trust** (the scorer must tell the truth) before any regeneration or prompt tuning.
- **Why:** the run reported `numeric_correctness` matched 0/n and Ensemble `mock_question_count=0`, but the current
  generated guides actually contain worked numeric examples and a full Mock Exam — so those zeros are **matcher /
  counter artifacts**, not proof of product absence, and may not drive a product change until proven.
- **phase=Phase 0 measurement trust**
- **slice169_focus=numeric_matcher_and_mock_counter_sanity**
- **regeneration_blocked_until_matcher_sanity=true** · **numeric_0n_untrusted_until_classified=true** ·
  **mock_0_untrusted_until_counter_sanity=true** · **found_but_wrong_value_routes_to_product_fix=true**
- **Numeric matcher (`pipeline/quality_safety_eval_harness.py`):**
  - Added a shared **label-anchored value scan** (`_label_value_scan`) used by the gate and the diagnostic: same-line
    numbers, same-line **format equivalents** (a `97%` reads as both `97` and `0.97`), and a bounded **PDF line-break
    proximity** fallback (the single next non-empty line, only when the label's own line carries no number). Every
    value is **anchored to an actual label occurrence**, so a stray number elsewhere is never blindly matched.
  - Contradiction is still judged on the **literally written** numbers; the within-tolerance test additionally accepts
    format equivalents. **Expected golden values were not edited; fixture tolerances were not widened.** Wrong values
    and competing/unresolved values still **fail** the gate (blocking), exactly as before.
- **Closed per-target classification** (`classify_numeric_targets` / `classify_numeric_target` /
  `summarize_numeric_classification`): each golden target → exactly one of `found_and_matched`,
  `found_but_format_or_context_missed`, `found_but_wrong_value`, `genuinely_missing`, with closed fields
  (`expected_value`, `matched_value`, `within_tolerance`, `label_found`, `value_found`, `reason_code`,
  `recompute_verifier_status`, `lecture_id`, `target_id`). `found_and_matched` = pre-Slice-169 strict matcher;
  `found_but_format_or_context_missed` = correct within the **existing** tolerance but only recovered by Slice 169's
  format/proximity work (so a clean run can be audited). **`found_but_wrong_value` is sacred** — a present-but-wrong
  or competing value stays a real defect routed to later generation/verifier work, never laundered into a match.
- **Mock counter:** added a **count-only** matcher (`_is_mock_question_count_line`) that recognizes structurally
  present `Mock/Practice Question`, `Question N`, and `Q4.` forms after stripping Markdown heading/list/emphasis
  decoration. Kept **independent** of `_is_mock_question_line` (the reasoning-leak `?` exemption) so **leak detection
  is unchanged**. It credits a present question only — never a bare `Mock Exam`/`Solution`/`Answer key` heading or a
  stray `?`.
- **Not changed / not weakened:** no eval gate loosened, no warning/failure hidden, no aggregator patched, no
  leak-detector weakened, no generation prompt changed, no guide regenerated, no `local_operator_baselines/` committed.
  Numeric strategy stays **recompute-first** (tolerance/contradiction adjudicates wrongness; classifier passes a
  `recompute_verifier_status` through, it does not replace the verifier). Production offline judge stays **frozen**
  (`judge_ready=false`, `repair_ready=false`); no API/frontend/job wiring touched. **Docker not run; no
  `docker compose config` run.** Slice 60 trace stash parked and untouched.
- **Tests:** added `test_numeric_classification_diagnostic`, `test_numeric_matcher_format_equivalence_gate`,
  `test_mock_question_counter_sanity` in `test_scripts/test_quality_safety_eval_harness.py` (synthetic public text
  only) covering exact/rounded/approx/percent/line-break matches, present-but-wrong, absent, label-without-value,
  value-without-label-proximity, competing values, and the Mock-Exam `Question N`/`Solution` counting.
- **Closed diagnostic — rerun on current unchanged local guides (NOT a green pass; truthful/mixed).** Ran the
  Slice-169 matcher/counter against the current unchanged local NN3 + Ensemble guide text (gitignored; no
  regeneration). Closed counts only, stable target ids only, no guide snippets. Expected values + tolerances were
  **not** edited; fixtures unchanged.
  - **NN3 (5 targets):** with the committed opaque stable-id labels **and** with natural exam-form anchor labels →
    `found_and_matched=0`, `found_but_format_or_context_missed=0`, `found_but_wrong_value=0`, `genuinely_missing=5`
    (all `label_not_found`). Numeric gate: matched 0, missing 5, mismatch 0, status `unknown`, **blocking false**.
    **Honesty note:** all five values are literally present in the guide (auxiliary value-presence scan = true for all
    5); the misses are **matcher-anchoring limits** — the guide states them in LaTeX/prose (`a_{\text{top}}`,
    `\max(0,0.572)`, `-\ln(0.57)`), so the label-anchored scan cannot attribute them. NN3 numerics are therefore
    **still untrusted in both directions** (neither confirmed present nor proven absent). The format-equivalence /
    proximity additions did **not** rescue NN3.
  - **Ensemble (7 targets), natural anchors:** `found_and_matched=1` (`proximity_4_3` → 0.80, strict same-line),
    `found_but_format_or_context_missed=0`, `found_but_wrong_value=6`, `genuinely_missing=0`. Numeric gate: matched 1,
    missing 0, mismatch 6, status `failed`, **blocking true**. `found_but_wrong_value` stayed failing/blocking; **no
    wrong value was reclassified as matched**. **Honesty note:** of the six `found_but_wrong_value`, only
    `gini_weight_gt_176` (golden 0.20) is a **confirmed genuine** product confusion (the guide vacillates 0.42 vs
    0.19, never a clean 0.20); the other five are `competing_unresolved_values` driven by **generic-anchor + messy
    PDF-extraction** multi-occurrence, so they are flagged-not-credited rather than five proven defects. The matcher
    correctly refused to launder any of them into a match.
  - **Mock counter (count-only `_is_mock_question_count_line`):** NN3 `mock_question_count=12` (min 8 → passed),
    Ensemble `mock_question_count=10` (min 8 → passed). The fix **does** detect the current guides' Mock-Exam
    structure (`Question N` / `Q4.` forms); no credit for bare `Mock Exam`/`Solution` headings or stray `?` — counts
    equal the actual question totals (NN3 Q1–Q12; Ensemble Question 1–10). This is the one signal cleanly rescued.
  - **Verdict:** truthful **mixed** result, not a suspicious clean pass. Mock-count zero was a real counter artifact
    (now fixed). Numeric zero is **partly** a matcher artifact (Ensemble proximity now matches; NN3 values present
    but unanchorable) but is **not** a clean rescue — numeric measurement trust is **not** established; the gate stays
    honest (Ensemble blocks on real+generic-driven wrongness, NN3 stays non-blocking `unknown`). No eval gate was
    weakened; `judge_ready=false`/`repair_ready=false` unchanged.
- **next_step=numeric_label_anchoring_robustness_or_targeted_regeneration_then_rerun** (numeric matcher still cannot
  trust real LaTeX/PDF guide text; mock counter trusted). **Slice 169 still NOT committed.**

---

## Slice 168 — **Narrow product generation fix for the trusted Phase 0 blocker (visible deliberation)**, on `slice168-product-generation-phase0-blocker-fix`. **COMMITTED `1d66f07`, fast-forward merged to trunk `chrome-renderer-v1`, pushed.**

- **Produce-before-scaffold gate applied:** a real Phase 0 Layer-1 run was produced locally on real gitignored
  GuideForge outputs, so the measured artifact exists. Eval-harness scaffolding stays **paused**; work shifted to
  generation output quality directly.
- **Supervisor review narrowed this slice.** The measurement revealed one **trusted** product defect — **visible
  deliberation / structural uncertainty** (leaked reasoning) in the final guide text — but its other signals are
  **not yet trusted as product absence**:
  - `numeric_correctness=0/n` is at least partly a **matcher artifact** (the generated guides do contain numeric
    worked examples); it is **not** proof all numerics are absent.
  - Ensemble `mock_question_count=0` is a **counting/extraction artifact** — the generated Ensemble guide actually
    contains a full Mock Exam with worked solutions; it is **not** proof mock questions are absent.
  - These two require **scorer/matcher sanity work** before they can drive any product change.
- **phase=Phase 1 narrow product-quality fix (trusted blocker only) after real Phase 0 Layer-1 baseline**
- **real_phase0_layer1_baseline_exists=true** · **trusted_blocker=leaked_reasoning (visible deliberation)**
- **eval_scaffolding_paused=true**
- **product_fix_focus=prompt_contract_final_answer_discipline** — the fix lives in the always-applied guide-quality
  **prompt contract** (`pipeline/guide_quality_prompt_contract.py`), whose `prompt_block` is appended to every
  generation prompt. No scorer/gate/validator/detector/matcher/counter change.
- **What changed (generation directives only):**
  - **Anti-leak (narrowed):** replaced the broad bare-substring ban on normal instructional words/phrases
    (`maybe`, `probably`, `likely`, `we need to`, `this might be`, `the material doesn't say`, `I will`,
    `I should`) with a **resolve-then-emit final-answer rule**: the guide must not expose first-person reasoning,
    self-correction, unresolved source confusion, or numeric uncertainty. It prohibits concrete deliberation forms
    (`"I think"`, `"I'm not sure"`, `"Wait"`, `"Actually"`-as-self-correction, `"unclear"`, `"we'll trust"`,
    `"let's infer"`, `"the slide/table is confusing"`, `"if this is wrong"`, an unresolved `= ?` / `≈ ?`, and
    multiple unresolved competing candidate values), **explicitly allows** ordinary teaching language (`You need
    to…`, `This will likely appear on the exam`, `This probably matters because…`), and offers the closed
    fallback "Not specified in the provided material." instead of speculation.
  - **Numeric (retained, reframed):** the numeric-preservation core rule is kept as **general final-answer
    discipline** — carry worked numeric examples to a committed final value, do not print unresolved/competing
    candidate values, and mark unverifiable numbers "Not verified from provided material." It does **not** claim
    the 0/n measurement proves numerics are absent, and hardcodes no private NN3/Ensemble values. No
    `known_numbers` infrastructure was added.
  - **Coverage:** the Slice-168 coverage-checklist core rule was **removed** — coverage trust is not established
    and it is outside the trusted blocker.
  - **Mock questions (reframed):** the comprehensive Mock-Exam structure rule is kept only as a **general
    high-detail/exam-guide expectation** (meaningful practice questions with worked solutions and answer keys); it
    is **no longer documented as a measured Ensemble absence**.
- **Tests:** `test_phase0_blocker_directives` rewritten to assert the resolve-then-emit / no-visible-deliberation
  rule, the prohibited self-correction/source-confusion/numeric-uncertainty forms, the closed fallback, the
  retained numeric discipline, and that normal teaching language is **not** flat-banned;
  `test_mock_question_minimum_for_exam_guides` reframed as general exam-guide behaviour. All generic — no private
  source/guide text.
- **Not weakened:** no eval gate, scorer, aggregator, leak detector, numeric matcher, or mock-question counter was
  changed or loosened; no warnings/failures hidden.
- **Not added:** no validator, packet, CLI skeleton, exit-check, ingest, schema, bridge, repair, production judge
  execution, or `known_numbers` runtime. Numeric strategy stays recompute-first.
- **Frozen:** production offline judge stays frozen (`judge_ready=false`, `repair_ready=false`).
- **No production job/API/frontend wiring changed.** **Docker not run; no `docker compose config` run.**
  Slice 60 trace stash parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted; no private
  material/raw artifacts/snippets/hashes/byte counts committed.
- **next_step=measurement_sanity_numeric_and_mock_matcher_or_regenerate_then_rerun**

---

## Slice 167 — **Phase 0 closed-summary validator CLI**, on `slice167-phase0-closed-summary-validator`. **NOT COMMITTED.**

- **Part 0 completed:** Slice 166 was committed as `e21e741` ("Slice 166: Add Phase 0 operator closed result packet"),
  fast-forward merged to trunk `chrome-renderer-v1` (`caf8171..e21e741`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean before branching Slice 167; **no docker compose config was run**; **Docker
  was not run**; the Slice 60 trace stash remains parked and untouched; `local_operator_baselines/` stayed
  ignored/uncommitted; no private material was committed. The operator run packet + closed-result ingest are committed;
  the closed-result ingest rejects raw/private material; no real operator run was executed; no production job/API/frontend
  wiring changed; the production offline judge remains frozen (`judge_ready=false`, `repair_ready=false`).
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=167**
- **phase0_closed_summary_validator_present=true** — new `test_scripts/validate_phase0_closed_summary.py` is a safe,
  offline, local tooling bridge that lets an operator validate already-sanitized Phase 0 *closed summary* JSON files
  later, without reading raw/private source materials. It exposes `validate_closed_summaries(paths)` and a `main(argv)`
  CLI. It accepts only JSON files explicitly passed on the command line, parses JSON, runs each parsed object through
  `ingest_phase0_operator_closed_result(...)`, and combines the accepted (`ok`) results with
  `build_phase0_exit_check_from_operator_results(...)`. It prints **only** a closed validation summary
  (`kind=phase0_closed_summary_validation`, `ok`, `input_count`, `accepted_count`, `invalid_count`, `accepted_kinds`,
  closed `blockers`, closed `warnings`, `phase0_exit_status`, `golden_pair_ids=["nn3","ensemble"]`, frozen judge
  booleans). It exits nonzero if any input is invalid.
- **validator_input_mode=explicit_json_files_only** — positional `nargs="+"` JSON paths; no default input path.
- **validator_default_scan=false** — no recursive search, no directory scanning, no `glob`/`rglob`/`walk`/`iterdir`/
  `listdir`/`scandir`; rejects directories (`input_is_a_directory`) and non-JSON / unparseable files
  (`input_not_a_json_file`, `input_not_valid_json`, `input_not_a_readable_file`). It never reads `jobs/`,
  operator baseline directories, source/reference PDFs, generated guides, generated guide markdown, OCR/table/caption
  text, screenshots, or raw artifacts by default. Forbidden raw/private material in an explicitly-passed file is
  rejected closed (`input_rejected_forbidden_material`) and never echoed; structurally wrong input is rejected closed
  (`input_rejected_invalid_shape`). The validator surfaces its own closed validator-level vocabulary and never re-emits
  the ingest layer's internal blocker tokens or any input content (defense in depth).
- **phase0_real_operator_run_executed=false** — no real private run was executed; tests use synthetic closed summary
  JSON in `tmp_path` only. No provider/model/cloud/local-LLM/judge call; no file discovery/reader of private materials.
- **production_job_api_frontend_wiring_changed=false** — a `test_scripts/` CLI + tests + docs only; no API route, no
  SPA-mount ordering change, no production job behavior change. **No `pipeline/` code changed** (the existing
  `ingest_phase0_operator_closed_result` / `build_phase0_exit_check_from_operator_results` helpers were sufficient).
- **overall_score_kind=layer1_deterministic_only**, **layer2_judge_included=false** by default.
- **golden_pair_ids=nn3,ensemble**
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false**. The dev-time reference-anchored
  eval judge remains separate (in `pipeline/quality_safety_reference_judge.py`) and is neither imported nor executed by
  the validator.
- **numeric_strategy=recompute_first_not_manual_known_numbers** — the validator carries no per-numeric "known" answer
  infrastructure; numeric truth stays recompute-first via the golden specs.
- **Changed files (5):** `test_scripts/validate_phase0_closed_summary.py` (new),
  `test_scripts/test_quality_safety_eval_harness.py`, `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`,
  `docs/DECISIONS.md`.
- **Validation (host):** `compileall api pipeline test_scripts` OK; `test_quality_safety_eval_harness.py` **498/0** (was
  405/0); `test_quality_safety_recompute_verifier.py` **99/0**; `test_quality_safety_unified_qa.py` **73/0**;
  `test_guide_quality_baseline.py` **207/0**; `validate_guide_quality_baseline_harness.py` `failure_count=0`;
  `validate_phase0_closed_summary.py --help` rc=0; `git diff --check` clean; no-leak grep over the diff returned no
  private hits. Phase 0 exit-check status from synthetic validator tests stays `not_ready` (structural blocker holds).
- **next_step=phase0_real_operator_run_local_only_or_phase0_exit_gap_closure**. **Slice 167 is NOT committed.**

---

## Slice 166 — **Phase 0 local-operator run packet + closed result ingest**, on `slice166-phase0-operator-run-packet`. **COMMITTED as `e21e741`; merged/pushed to trunk.**

- **Part 0 completed:** Slice 165 was committed as `caf8171` ("Slice 165: Add Phase 0 eval runner exit check"),
  fast-forward merged to trunk `chrome-renderer-v1` (`bce7e33..caf8171`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean before branching Slice 166; **no docker compose config was run**; **Docker
  was not run**; the Slice 60 trace stash remains parked and untouched; `local_operator_baselines/` stayed
  ignored/uncommitted; no private material was committed. The runner + exit-check are committed; the exit-check closed
  vocabularies are clean and `phase0_exit_status` stays `not_ready`/`blocked` (never falsely `ready`); the production
  offline judge remains frozen (`judge_ready=false`, `repair_ready=false`).
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=166**
- **phase0_operator_run_packet_present=true** — `build_phase0_operator_run_packet()` (alias
  `get_phase0_operator_run_packet()`) in `pipeline/quality_safety_eval_harness.py` returns a closed, safe instruction
  contract: `kind=phase0_operator_run_packet`, `phase=phase0_eval_harness_fact_sheet_skeleton`,
  `golden_pair_ids=["nn3","ensemble"]`, `required_local_runs` (nn3 current, ensemble current, ensemble old-failure,
  reference-judge calibration), `required_closed_outputs` (the four ingest kinds), `forbidden_outputs` (source/guide/
  reference/ocr/table text, captions, raw prompt/response, provider payload, filepath, filename, hash, byte count,
  screenshot), `layer2_execution_mode=operator_local_only_not_in_production`, `persistence_policy=closed_summary_only`,
  `numeric_strategy=recompute_first_not_manual_known_numbers`, and frozen judge booleans. It names no private path,
  filename, source/reference document, or shell command.
- **phase0_operator_closed_result_ingest_present=true** — `ingest_phase0_operator_closed_result(result)` accepts only
  closed summaries of a recognized kind (`phase0_eval_harness_run`, `phase0_exit_check`, `phase0_reference_judge_summary`,
  `phase0_eval_regression_record`) and returns `ingest_status=ok|invalid|blocked` with closed `blockers`/`warnings`,
  `accepted_kind`, `golden_pair_ids`, and a closed `sanitized_result` (ok only). It marks `invalid` for bad shape/unknown
  kind and `blocked` for any forbidden key (anywhere in the tree), private-path-like / data-URI-or-encoded / secret-like /
  other private-material-like / long-evidence-quote string value, or an attempt to set `judge_ready`/`repair_ready` true.
  The sanitizer keeps only bounded numerics, booleans, and short closed snake/dotted tokens, and always forces
  `judge_ready=false`, `repair_ready=false`, `production_offline_judge_frozen=true`.
- **phase0_exit_check_from_operator_results_present=true** — `build_phase0_exit_check_from_operator_results(results)`
  ingests each result, uses only the `ok` ones, and reports honestly. It can never fake `ready`: the structural
  `fact_sheet_production_wiring_not_present` blocker cannot be cleared by a closed summary, so even a full, valid synthetic
  result set returns `not_ready`. Missing summaries surface `real_old_ensemble_run_not_recorded`,
  `reference_judge_execution_not_run`, `reference_judge_calibration_not_recorded`, and `regression_history_not_established`;
  a genuinely non-shippable **current** candidate adds `phase0_run_not_all_shippable` and flips to `blocked` (the
  old-failure run is *expected* non-shippable and does not). Blockers reuse the shared closed exit-check vocabulary;
  `satisfied` uses a pinned operator-specific closed vocabulary.
- **phase0_real_operator_run_executed=false** — no real private run was executed; tests use synthetic closed summaries
  only. No provider/model/cloud/local-LLM/judge call, no file discovery/reader, no reading of `jobs/`,
  `local_operator_baselines/`, PDFs, guides, `clean.md`, OCR/table/caption text, screenshots, or raw artifacts.
- **production_job_api_frontend_wiring_changed=false** — pure schema/contract + ingest functions and tests only; no API
  route, no SPA-mount ordering change, no production job behavior change; no CLI validation script added.
- **overall_score_kind=layer1_deterministic_only**, **layer2_judge_included=false** by default.
- **golden_pair_ids=nn3,ensemble**
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false**. The dev-time reference-anchored
  eval judge remains separate (in `pipeline/quality_safety_reference_judge.py`) and is not executed by this layer.
- **numeric_strategy=recompute_first_not_manual_known_numbers** — the ingest carries no per-numeric "known" answer field;
  numeric truth stays recompute-first via the golden specs.
- **Changed files (5):** `pipeline/quality_safety_eval_harness.py`, `test_scripts/test_quality_safety_eval_harness.py`,
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation (host):** `compileall api pipeline test_scripts` OK; `test_quality_safety_eval_harness.py` **405/0** (was
  315/0); `test_quality_safety_recompute_verifier.py` **99/0**; `test_quality_safety_unified_qa.py` **73/0**;
  `test_guide_quality_baseline.py` **207/0**; `validate_guide_quality_baseline_harness.py` `failure_count=0`;
  `git diff --check` clean; no-leak grep over the diff returned no private hits.
- **next_step=phase0_real_operator_run_execution_local_only_or_phase0_exit_gap_closure.** **Slice 166 is NOT committed.**


## Slice 165 — **Phase 0 eval runner + exit-check skeleton**, on `slice165-phase0-eval-runner-exit-check`. **COMMITTED as `caf8171`; merged to trunk (`bce7e33..caf8171`) and pushed.**

- **Part 0 completed:** Slice 164 was committed as `bce7e33` ("Slice 164: Integrate Phase 0 factsheet recompute path"),
  fast-forward merged to trunk `chrome-renderer-v1`, and pushed with a normal `git push` (no force-push). `origin/chrome-renderer-v1`,
  local trunk, and the Slice 165 branch all sit at `bce7e33`. Final trunk status was clean before branching Slice 165;
  **no docker compose config was run**; **Docker was not run**; the Slice 60 trace stash remains parked and untouched;
  `local_operator_baselines/` stayed ignored/uncommitted; no private material was committed. (The starting working tree
  for this chat was already on `slice165-phase0-eval-runner-exit-check`, clean, with Slice 164 on trunk — Part 0 had been
  completed in the prior session; this was re-verified, not re-done.)
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=165**
- **phase0_eval_runner_present=true** — `run_phase0_eval_harness(candidate_text_by_lecture_id, golden_pair_specs, *, fact_sheet_by_lecture_id=None, reference_judge_summary_by_lecture_id=None, run_id="synthetic", model_tier="premium")`
  in `pipeline/quality_safety_eval_harness.py`. Pure, deterministic, in-memory. It validates the golden pair set as exactly
  `{nn3, ensemble}` via `load_golden_pair_specs` (raises `GoldenPairSpecError` otherwise), scores each lecture with
  `score_phase0_layer1` (optionally folding a caller-supplied in-memory fact sheet), and builds a closed
  `build_phase0_regression_record` per lecture. A missing/non-string candidate degrades to an empty candidate (which fails
  the deterministic Layer-1 gates and is non-shippable) and records a closed `candidate_missing`/`candidate_invalid`
  warning instead of crashing. Returns a closed aggregate: `kind=phase0_eval_harness_run`, `run_id`, `model_tier`,
  `golden_pair_ids=["nn3","ensemble"]`, `lecture_count`, `shippable_count`, `non_shippable_count`, `min_overall_10`,
  `average_overall_10`, `all_shippable`, `overall_score_kind=layer1_deterministic_only`, `layer2_judge_included`,
  `production_offline_judge_frozen=true`, `judge_ready=false`, `repair_ready=false`, `records=[...]`, closed `warnings`.
- **phase0_exit_check_present=true** — `build_phase0_exit_check(run_record)` returns a closed exit-check record
  (`kind=phase0_exit_check`, `phase=phase0_eval_harness_fact_sheet_skeleton`) with closed `blockers`/`satisfied` tokens
  only. It cannot invent readiness: structural blockers (`real_old_ensemble_run_not_recorded`,
  `reference_judge_execution_not_run`, `reference_judge_calibration_not_recorded`, `fact_sheet_production_wiring_not_present`,
  `regression_history_not_established`) always hold this slice, so the status is never `ready`. A missing run record adds
  `phase0_required_run_missing`; a non-shippable run adds `phase0_run_not_all_shippable` and flips the status to `blocked`.
  `satisfied` lists the built components (golden-pair specs, Layer-1 scorer, overall_10-separate-from-shippable, regression
  record shape, reference-judge contract, factsheet recompute integration, frozen judge).
- **phase0_exit_status=not_ready** (clean synthetic run; `blocked` when a run is non-shippable).
- **layer2_judge_included=false** by default; `true` only when an explicit, already-sanitized, fully-calibrated
  reference-judge summary is supplied per lecture, and even then `overall_10` stays Layer-1 deterministic-only.
- **golden_pair_ids=nn3,ensemble**
- **overall_score_kind=layer1_deterministic_only**
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false**
- **numeric_strategy=recompute_first_not_manual_known_numbers** — not manual operator `known_numbers` infrastructure; the
  closed golden expectations + optional caller-supplied recompute summary drive numeric truth. No repair, no judge
  execution, no producer/discovery/file reader, no provider/model/cloud/local-LLM call, no production job/API/frontend
  wiring, and no reading of `jobs/`, `local_operator_baselines/`, PDFs, guides, `clean.md`, OCR/table/caption text,
  screenshots, or raw artifacts was added. No CLI validation script was added (pure functions + tests only).
- **Changed files (5):** `pipeline/quality_safety_eval_harness.py`, `test_scripts/test_quality_safety_eval_harness.py`,
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation (host):** `compileall api pipeline test_scripts` OK; `test_quality_safety_eval_harness.py` **305/0** (was
  254/0); `test_quality_safety_recompute_verifier.py` **99/0**; `test_quality_safety_unified_qa.py` **73/0**;
  `test_guide_quality_baseline.py` **207/0**; `validate_guide_quality_baseline_harness.py` `failure_count=0`;
  `git diff --check` clean; no-leak grep over the diff returned no private hits.
- **next_step=phase0_real_operator_run_plan_or_phase0_exit_gap_closure.** **Slice 165 committed as `caf8171`; merged and pushed.**


## Slice 164 — **Phase 0 fact-sheet schema + recompute verifier integration**, on `slice164-phase0-factsheet-recompute-integration`. **COMMITTED as `bce7e33`; merged to trunk and pushed.**

- **Part 0 completed:** Slice 163 was committed as `c4d9607` ("Slice 163: Add Phase 0 reference judge contract"),
  fast-forward merged to trunk `chrome-renderer-v1` (`06496d0..c4d9607`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean before branching Slice 164; **no docker compose config was run**; **Docker
  was not run**; the Slice 60 trace stash remains parked and untouched; `local_operator_baselines/` stayed
  ignored/uncommitted; no private material was committed. The Phase 0 reference-anchored judge contract is now
  committed; judge execution was **not** implemented; no provider/model/cloud/local-LLM calls were added;
  `layer2_judge_included=false` by default; `overall_10` remains Layer-1 deterministic-only; the production offline
  judge remains frozen (`judge_ready=false`, `repair_ready=false`).
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=164**
- **phase0_fact_sheet_schema_integration_present=true** — `build_phase0_fact_sheet_summary(fact_sheet, golden_spec)` in
  `pipeline/quality_safety_eval_harness.py` summarizes caller-supplied in-memory fact sheets using the existing Slice 110
  fact-sheet schema. The summary is closed counts/statuses only: `fact_sheet_status`,
  `recompute_verifier_status`, numeric counts, and closed warnings. It never returns fact labels, raw text, source/guide/
  OCR/table/caption text, snippets, paths, filenames, hashes, byte counts, provider payloads, prompts/responses, or raw
  artifact JSON.
- **phase0_recompute_verifier_integration_present=true** — `score_phase0_layer1(..., fact_sheet=None)` optionally runs
  the existing recompute verifier over a caller-supplied fact sheet and folds the safe summary into the Phase 0 eval
  path. With no fact sheet, the Layer-1 numeric behavior is preserved and the record reports
  `fact_sheet_status=not_supplied` / `recompute_verifier_status=not_run`. If recompute reports a failed numeric,
  `numeric_correctness` fails and `shippable=false` even when the candidate prints the supplied value. Verified/canonical
  numeric facts add committed numeric targets that the candidate must still contain; unverified/low-confidence values are
  counted/warned and never used to pass numeric correctness.
- **fact_sheet_input_mode=caller_supplied_in_memory_only** — no producer, discovery, file reader, job wiring, API route,
  frontend, OCR/table/source parsing, clean.md parsing, raw artifact reader, or production behavior was added.
- **production_fact_sheet_wiring_changed=false**
- **overall_score_kind=layer1_deterministic_only**
- **layer2_judge_included=false**
- **golden_pair_ids=nn3,ensemble**
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false**
- **numeric_strategy=recompute_first_not_manual_known_numbers** — this is not manual operator `known_numbers`
  infrastructure and it preserves the factsheet-spec invariant: unverified numeric facts never become confident values;
  no repair/production wiring was added.
- **Validation (host, so far):** `test_quality_safety_eval_harness.py` **254/0** (was 238/0). Full Slice 164 validation
  still pending.
- **next_step=phase0_eval_harness_runner_or_exit_check.** **Slice 164 is NOT committed.**


## Slice 163 — **Phase 0 dev-time reference-anchored judge contract skeleton**, on `slice163-phase0-reference-anchored-judge-contract`. **COMMITTED as `c4d9607`; merged to trunk (`06496d0..c4d9607`) and pushed.**

- **Part 0 completed:** Slice 162 was committed as `06496d0` ("Slice 162: Add Phase 0 overall score regression record"),
  fast-forward merged to trunk `chrome-renderer-v1` (`e76173f..06496d0`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean; **no docker compose config was run**; **Docker was not run**; the Slice 60
  trace stash remains parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted; no private material
  was committed. The Phase 0 `overall_10` envelope + regression record are now committed; `overall_10` is Layer-1
  deterministic-only and stays separate from `shippable`; the production offline judge remains frozen
  (`judge_ready=false`, `repair_ready=false`).
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=163**
- **phase0_reference_anchored_judge_contract_present=true** — a **dev-time, reference-anchored Layer-2 eval judge
  contract skeleton** (roadmap §A3). New pure/unwired helper module `pipeline/quality_safety_reference_judge.py` plus
  closed contract constants in `pipeline/quality_safety_eval_harness.py`. This is **separate** from the frozen
  production offline judge and is **not** a production shippability gate.
- **closed axes (exactly seven)** — `conceptual_depth`, `beginner_friendliness`, `explanation_quality`,
  `comparison_quality`, `memory_support`, `mock_question_quality`, `density_anti_bloat`. Per-axis score is an
  **integer 0..5**. Result statuses: `not_run`/`ok`/`miscalibrated`/`invalid_output`/`blocked`/`skipped`; calibration
  statuses: `not_run`/`ok`/`miscalibrated`.
- **prompt-construction boundary** — `build_phase0_reference_judge_prompt(reference_text, candidate_text, golden_spec)`
  validates the golden-pair spec (lecture id stays within `{nn3, ensemble}`) and returns an **in-memory messages object
  for a caller to send later**. It calls **no** provider/model and writes **no** file. The instruction states the
  reference is the 9–10 benchmark, the candidate is scored relative to it, axes are scored 0–5, calibration requires the
  reference to score ≥ 4 on every axis, strict JSON only, and a short per-axis evidence quote of at most
  **`evidence_quote_max_words=15`** words. Reference/candidate text is embedded in-memory only (caller-supplied);
  committed tests/docs use **tiny synthetic strings only**.
- **output sanitizer/validator** — `sanitize_phase0_reference_judge_output(raw, golden_spec)` reads only the closed
  known fields (`candidate_scores`, `reference_scores`, optional short `evidence`), validates the seven closed axes and
  integer 0..5 scores, enforces the ≤15-word evidence-quote limit (over-long/secret-ish quotes dropped + counted),
  drops every unknown/forbidden field, classifies invalid shapes as `invalid_output`, and marks `miscalibrated`
  (discarding candidate scores) when any reference axis is below 4. It never sets `judge_ready`/`repair_ready` true,
  never triggers repair, and never copies provider payloads, prompts, raw model output, paths, filenames, hashes, byte
  counts, or long quotes. `phase0_reference_judge_regression_summary(sanitized)` produces a **record-safe** closed
  summary that **drops evidence quotes entirely**.
- **integration (not executed)** — `build_phase0_regression_record(...)` gains an optional `reference_judge_summary`
  that is defensively re-validated (`_safe_reference_judge_summary`): evidence/forbidden fields dropped, statuses
  closed, `layer2_judge_included` set **true only** when the summary is fully calibrated and `ok`. **Default stays
  `reference_anchored_judge_status=not_run` and `layer2_judge_included=false`.** A Layer-2 summary **never** blends into
  `overall_10` — `overall_10` stays Layer-1 deterministic-only (verified).
- **layer2_judge_included=false** by default; **overall_score_kind=layer1_deterministic_only** unchanged;
  **golden_pair_ids=nn3,ensemble** unchanged.
- **phase0_reference_anchored_judge_execution=false** — no provider/model/cloud/local-LLM call was added; no judge was
  executed; no JSONL regression run was performed; the old frozen offline-judge core was **not** called or extended.
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false**,
  **numeric_strategy=recompute_first_not_manual_known_numbers** (this is **not** manual operator known_numbers
  infrastructure). No frontend/API/production-job changes; no repair; reasoning-leak detection reused and **not
  weakened**.
- **Validation (host):** `compileall api pipeline test_scripts` clean;
  `test_quality_safety_eval_harness.py` **238/0** (was 199/0); `test_quality_safety_recompute_verifier.py` 99/0;
  `test_quality_safety_unified_qa.py` 73/0; `test_guide_quality_baseline.py` 207/0;
  `validate_guide_quality_baseline_harness.py` ok; `git diff --check` clean. **Docker not run.**
- **next_step=phase0_fact_sheet_schema_eval_integration_or_reference_judge_runner_design.** **Slice 163 is committed,
  merged to trunk, and pushed.**


## Slice 162 — **Phase 0 overall score + regression record shape/persistence**, on `slice162-phase0-overall-score-regression-record`. **COMMITTED as `06496d0`; merged to trunk (`e76173f..06496d0`) and pushed.**

- **Part 0 completed:** Slice 161 was committed as `e76173f` ("Slice 161: Add Phase 0 Layer-1 deterministic scorer"),
  fast-forward merged to trunk `chrome-renderer-v1` (`4e652bd..e76173f`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean; **no docker compose config was run**; **Docker was not run**; the Slice 60
  trace stash remains parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted; no private material
  was committed. The Phase 0 Layer-1 deterministic scorer is now committed; numeric label-internal parameters stay
  ignored while genuine wrong answers still fail; the production offline judge remains frozen
  (`judge_ready=false`, `repair_ready=false`).
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=162**
- **phase0_overall_10_present=true** — `compute_phase0_overall_10(layer1_record)` in
  `pipeline/quality_safety_eval_harness.py`. Pure/deterministic. Takes a `score_phase0_layer1` record and returns a
  closed envelope with a **separate** `overall_10` and `shippable`. `overall_10` starts at `10.0` and subtracts bounded
  closed penalties (leaked_reasoning/numeric/worked_answer large; coverage scaled by shortfall; mock-question small),
  clamped to `[0.0, 10.0]` and rounded to one decimal.
- **overall_score_kind=layer1_deterministic_only** — the envelope always reports
  `overall_score_kind=layer1_deterministic_only` and **layer2_judge_included=false**; this `overall_10` is **not** the
  final premium/local 9.5/9.0 product-quality score (that belongs to the later, separate dev-time reference-anchored
  Layer-2 judge). `shippable` mirrors **only** the Layer-1 blocking gates; the advisory mock-question shortfall reduces
  `overall_10` but never sets `shippable=false` on its own. `judge_ready`/`repair_ready` are always `false` here and
  **unoverrideable** (verified against a tampered input record).
- **phase0_regression_record_shape_present=true** — `build_phase0_regression_record(layer1_record, *, run_id,
  model_tier, candidate_id=None, previous_overall_10=None)` returns a closed `phase0_eval_regression_record`: version,
  kind, `lecture_id` (closed to `nn3`/`ensemble`/`unknown`), `source_quality`, sanitized `run_id`/`model_tier`
  (`premium`/`local`/`unknown`)/optional safe `candidate_id`, `overall_10`, `overall_score_kind`,
  `layer2_judge_included=false`, `shippable`, `blocking_checks`, `layer1_status`, per-check `check_statuses`,
  `judge_ready=false`/`repair_ready=false`, `reference_anchored_judge_status`, `regression_status`,
  optional `previous_overall_10`/`delta_overall_10`, closed `warnings`. **No** candidate/source/guide/OCR/table/caption
  text, snippet, path, filename, hash, byte count, or provider payload — verified by a forbidden-key sweep and the
  hostile-canary sweep.
- **phase0_regression_jsonl_writer_present=true** — `append_phase0_regression_record_jsonl(path, record)` appends one
  compact JSON line; append-only; **caller-supplied parent dir only** (no default into `jobs/` or
  `local_operator_baselines/`); reads no private file. It **rejects** any record that is not a
  `phase0_eval_regression_record` or that carries a forbidden field or secret-ish token. Tested in a temp dir only
  (exactly one line per call; forbidden field + wrong kind rejected).
- **regression comparison** — `compare_phase0_regression(current_record, previous_record)` returns a closed verdict
  (`regression_status=green|regressed|not_comparable`, `overall_delta`, `blocking_regression_count`, closed
  `warnings`). Per the roadmap: **regress** if `overall_10` drops by more than `0.3` vs a previous green run on the same
  lecture/model, or if any previously passing blocking check now fails. Lecture/model-tier mismatch or a missing
  `overall_10` ⇒ `not_comparable`.
- **golden_pair_ids=nn3,ensemble** — unchanged real Phase 0 pair; a record for any other lecture id degrades its
  `lecture_id` to the closed `unknown` token rather than carrying it (verified).
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false**,
  **dev_time_reference_anchored_eval_status=not_built_yet** (the dev-time reference-anchored Layer-2 judge stays
  separate and is **not executed** in this slice), **numeric_strategy=recompute_first_not_manual_known_numbers**.
  No frontend/API/production-job changes; no repair; reasoning-leak detection reused and **not weakened**.
- **Validation (host):** `compileall api pipeline test_scripts` clean;
  `test_quality_safety_eval_harness.py` **199/0** (was 151/0); `test_quality_safety_recompute_verifier.py` 99/0;
  `test_quality_safety_unified_qa.py` 73/0; `test_guide_quality_baseline.py` 207/0;
  `validate_guide_quality_baseline_harness.py` ok; `git diff --check` clean. **Docker not run.**
- **next_step=phase0_reference_anchored_judge_skeleton_or_fact_sheet_schema_integration.** **Slice 162 is NOT committed.**

---

## Slice 161 — **Phase 0 Layer-1 deterministic scorer on the real golden pair**, on `slice161-phase0-layer1-deterministic-scorer`. **COMMITTED `e76173f`.**

- **Part 0 completed:** Slice 160 was committed as `4e652bd` ("Slice 160: Add Phase 0 golden pair eval skeleton"),
  fast-forward merged to trunk `chrome-renderer-v1` (`da795a8..4e652bd`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean; **no docker compose config was run**; **Docker was not run**; the Slice 60
  trace stash remains parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted; no private material
  was committed. The Phase 0 golden-pair specs (`nn3`, `ensemble`) are now committed.
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=161**
- **phase0_layer1_deterministic_scorer_present=true** — `score_phase0_layer1(candidate_text, golden_spec, *, ...)` in
  `pipeline/quality_safety_eval_harness.py`. Pure, in-memory, deterministic. It validates the golden-pair spec, runs the
  five closed Layer-1 detectors over the **caller-supplied candidate string** and the closed authored expectation spec,
  and returns a closed, JSON-serializable, **counts-only** record. It reads **no file**, no source/reference document,
  no `clean.md`, no OCR/caption/table text, no provider payload, no model, and no judge.
- **golden_pair_ids=nn3,ensemble** — unchanged real Phase 0 pair; the scorer rejects the synthetic Slice 108 fixtures as
  golden pairs (verified by test).
- **layer1_checks=leaked_reasoning,numeric_correctness,coverage,mock_q_count,worked_answer_completeness** — implemented
  via the existing closed detectors (reasoning-leak detection reused, **not weakened**):
  - `leaked_reasoning` — reused `_check_leaked_reasoning`; counts only (signature + structural), **blocking**, no
    matched text.
  - `numeric_correctness` — golden pairs require **every** authored numeric, so any **missing or contradicted** numeric
    is a **blocking** fail. Reshaped to counts only: `expected_count`, `matched_count`, `missing_count`,
    `mismatch_count` (the detailed per-target list / any extracted candidate values are **dropped** from the record).
    **Patch:** before extracting candidate numbers the check now **strips the matched authored-label span**
    (`_strip_label_spans`), so label-internal parameters (e.g. `pw=0.5`, `sw=0.37`, `-ln 0.57`, `1.43`, the `176` in
    `gini_weight_gt_176`) are **not** read as candidate answers or contradictions; only the right-hand-side answer after
    `=`/`:`/`≈` is read. When the label tokens are not a contiguous run the line is left unchanged, so general
    contradiction detection is **not weakened** (e.g. `Gini weight_gt_176 = 0.42` vs `= 0.19` still fails).
  - `coverage` — lowercase/punctuation-stripped/whitespace-collapsed topic matching; `coverage_ratio` vs
    `threshold=0.90`; **blocking only when below threshold**. Reshaped to counts only (`expected_topic_count`,
    `matched_topic_count`, `coverage_ratio`, `threshold`); the authored `missing_topics` list is **dropped**.
  - `mock_question_count` — advisory only (`status=warning` when below `min_required`), **non-blocking**; does not
    alone make `shippable=false`.
  - `worked_answer_completeness` — reused detector; unresolved final-answer markers are a **blocking** fail; counts
    only.
- **Record shape:** `lecture_id`, `source_quality`, `tier_targets`, `layer1_status`, `layer1_summary`, **separate
  `overall_10` and `shippable`**, `blocking_checks`, `checks`, `judge_ready=false`, `repair_ready=false`,
  `reference_anchored_judge_status` (`not_run` default), `regression_record_status` (`shape_only` default), `warnings`.
  - **`overall_10` is intentionally left unscored (`None`)** with `overall_10_basis="layer1_deterministic_not_scored"`
    — a real 0–10 quality score is owned by the later, **separate** dev-time reference-anchored eval judge, not this
    deterministic path; it must not pretend to include a Layer-2 judge score.
  - **`shippable` reflects only the deterministic Layer-1 blocking gates** (it is `false` iff any blocking check fails);
    advisory checks never block on their own.
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false** — hard-coded with no override
  path in the scorer (verified by test even when a `reference_anchored_judge_status` is supplied).
- **dev_time_reference_anchored_eval_status=not_built_yet** (status field present and separate; judge not built/executed).
- **numeric_strategy=recompute_first_not_manual_known_numbers** — the golden `ground_truth_numerics` remain closed
  authored **expectation** specs scored against caller text; **not** a general operator-typed known_numbers runtime path.
- **Boundaries honored:** no Layer-2 judge execution; no provider/model/cloud/local-LLM call; no filesystem reading of
  private guides; no JSONL persistence (shape-only); no repair; reasoning-leak detection unweakened; no aggregator/eval
  patched to hide warnings/failures; frontend and API routes untouched.
- **Validation (green):** `compileall api pipeline test_scripts` (exit 0); `test_quality_safety_eval_harness.py`
  **151/0** (was 105/0; +3 regression tests for natural decimal-bearing labels and the natural ensemble
  contradiction/mismatch); `test_quality_safety_recompute_verifier.py` **99/0**; `test_quality_safety_unified_qa.py`
  **73/0**; `test_guide_quality_baseline.py` **207/0**; `validate_guide_quality_baseline_harness.py` ok;
  `git diff --check` clean. **Docker not run; no docker compose config run.**
- **label_internal_parameter_patch=applied** — `_strip_label_spans` removes matched-label spans before numeric
  extraction so realistic labels (`htop(pw=0.5,sw=0.37)`, `SoftMax(1.43)`, `CE(-ln 0.57)`, `gini_weight_gt_176`) no
  longer create false contradictions; tests use the natural label forms (no underscore `_out` dodge). Committed
  golden-pair specs (`nn3`, `ensemble`) unchanged; golden-pair set still exactly `{nn3, ensemble}`.
- **next_step=phase0_overall_score_regression_record_shape_or_reference_judge_skeleton**.

---

## Slice 160 — **Phase 0 real golden-pair eval harness skeleton (`nn3` + `ensemble`)**, on `slice160-phase0-real-golden-pair-eval-skeleton`. **COMMITTED `4e652bd`; merged to trunk; pushed.**

- **Part 0 completed:** Slice 159 was committed as `da795a8` ("Slice 159: Adopt master roadmap Phase 0 grounding"),
  fast-forward merged to trunk `chrome-renderer-v1` (`3a44c91..da795a8`), and pushed with a normal `git push` (no
  force-push). `docs/GUIDEFORGE_MASTER_ROADMAP.md` is now committed and authoritative. Final trunk status was clean;
  **no docker compose config was run**; **Docker was not run**; the Slice 60 trace stash remains parked and untouched;
  `local_operator_baselines/` stayed ignored/uncommitted; no private material was committed.
- **phase=Phase 0 — Eval harness + fact-sheet skeleton** (active; phase order unchanged).
- **slice=160**
- **phase0_real_golden_pair_fixtures_present=true** — `test_scripts/fixtures/quality_safety/golden_pairs/nn3.json`
  and `test_scripts/fixtures/quality_safety/golden_pairs/ensemble.json`.
- **golden_pair_ids=nn3,ensemble** — the loader requires the set to be **exactly** `{nn3, ensemble}` (incomplete,
  duplicate, extra, or unknown lecture ids are rejected). The old synthetic Quality Safety fixtures do **not** pass as
  golden pairs (distinct `kind` + lecture id) — verified by test.
- **What this slice added (code):**
  - `pipeline/quality_safety_eval_harness.py` — a **separate strict** golden-pair layer beside the synthetic Slice 108
    layer: `GoldenPairSpecError`, `load_golden_pair_spec(...)` (closed-shape validator that *raises* instead of
    degrading; rejects unknown keys so no raw source/guide/OCR/caption material can ride along; preserves authored
    case + math/slash punctuation in labels), `load_golden_pair_specs(...)` (enforces exactly `{nn3, ensemble}`), and
    `build_phase0_report_skeleton(...)`.
  - The Phase 0 report skeleton holds the scoreboard *shape* for later slices: `lecture_id`, `source_quality`,
    `tier_targets`, `layer1_status`, `layer1_summary`, **separate `overall_10` and `shippable`**, `blocking_checks`,
    `judge_ready`, `repair_ready`, `reference_anchored_judge_status` (`not_run|missing|miscalibrated|ok`),
    `regression_record_status` (`shape_only|not_persisted`). **`judge_ready`/`repair_ready` are hard-coded `False`
    with no override** — the production offline judge stays frozen by construction.
- **Boundaries honored:** no Layer-2 judge execution; **no provider/model call**; no JSONL regression persistence
  (shape-only); no repair; recompute-first numeric strategy preserved (these `ground_truth_numerics` are closed
  authored *expectation* specs for the scoreboard, **not** a general operator-typed known_numbers runtime path); the
  dev-time reference-anchored eval judge stays **separate** from the frozen production offline judge and is **not yet
  executed** (`reference_anchored_judge_status=not_run`).
- **production_offline_judge_frozen=true**, **judge_ready=false**, **repair_ready=false**.
- **dev_time_reference_anchored_eval_status=skeleton_only** (status field present; judge not built/executed).
- **numeric_strategy=recompute_first_not_manual_known_numbers**.
- **Validation (green):** `compileall api pipeline test_scripts` (exit 0); `test_quality_safety_eval_harness.py`
  **105/0** (was 52/0); `test_quality_safety_recompute_verifier.py` **99/0**; `test_quality_safety_unified_qa.py`
  **73/0**; `test_guide_quality_baseline.py` **207/0**; `validate_guide_quality_baseline_harness.py` ok;
  `git diff --check` clean. **Docker not run; no docker compose config run.**
- **next_step=phase0_layer1_deterministic_scorer_real_pair**.

---

## Slice 159 — **Master Roadmap adoption + Phase 0 eval-harness grounding**, on `slice159-master-roadmap-phase0-eval-grounding`. **NOT COMMITTED (docs-only grounding).**

- **Part 0 completed:** Slice 158 was committed as `3a44c91` ("Slice 158: Triage remaining QA gate warning"),
  fast-forward merged to trunk `chrome-renderer-v1` (`5ab92f0..3a44c91`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean; **no docker compose config was run**; the Slice 60 trace stash remains
  parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted; no private material was committed.
- **phase=Phase 0 — Eval harness + fact-sheet skeleton**
- **roadmap_authority=docs/GUIDEFORGE_MASTER_ROADMAP.md** (added this slice — copied in verbatim; it did **not**
  previously exist in the repo). `roadmap_adopted=true`.
- **previous_next_step_superseded=multi_guide_read_then_product_fix**
- **current_next_step=phase0_eval_harness_real_golden_pair_skeleton**
- **Closed findings (inspection of existing Phase 0-related code; code is source of truth):**
  - `existing_eval_harness_present=true` — `pipeline/quality_safety_eval_harness.py` (Slice 108): pure synthetic-only
    Layer-1 scorer (leaked_reasoning / numeric_correctness / worked_answer_completeness / coverage / mock_question_count)
    + fixture loader + a regression-record *shape*. Synthetic-only; persists no JSONL; no Layer-2; no real golden pair.
  - `existing_fact_sheet_schema_present=true` — `pipeline/quality_safety_fact_sheet.py` (Slice 110): fact-record +
    fact-sheet schema (§B1/§B2) with provenance + verification-status vocab. Recompute-first foundation.
  - `existing_recompute_verifier_present=true` — `pipeline/quality_safety_recompute_verifier.py` (Slice 111):
    recompute-first **primary numeric truth path** (§B3); recomputes structured facts within tolerance.
  - `existing_reference_anchored_judge_present=false` — only the **frozen production offline judge** exists
    (`quality_safety_offline_judge_{core,schema,artifact_adapter}.py`, Slices 142–143) which forces
    `judge_ready`/`repair_ready` to False. The Phase 0 **dev-time** reference-anchored eval judge (candidate vs Claude
    reference, local, operator key, closed scores + <15-word quotes) is **not yet a separate built module** — must be
    built, kept distinct from the frozen production judge.
  - `existing_regression_record_present=shape_only` — `REGRESSION_KIND` + a "future JSONL record" builder exist, but
    no append-only JSONL persistence is wired.
  - `existing_real_golden_pair_fixtures_present=false` — only synthetic fixtures
    (`test_scripts/fixtures/quality_safety/*_synthetic.json`); no real `nn3` / `ensemble` golden pair with
    `expected_topics` + `ground_truth_numerics` (incl. `Gini weight_gt_176 = 0.20`) + `min_mock_questions` + `tier_targets`.
  - `production_offline_judge_frozen=true`, `judge_ready=false`, `repair_ready=false`.
  - `numeric_strategy=recompute_first_not_manual_known_numbers`.
- **Component classification (existing modules vs Phase 0):**
  - `reusable_for_phase0`: `quality_safety_fact_sheet.py` (schema §B1/§B2), `quality_safety_recompute_verifier.py`
    (recompute-first truth path §B3), `quality_safety_canonical_matcher.py` (narrow canonical fallback §B4,
    recompute-preserving), `quality_safety_leak_scanner.py` (leak blocking check §B6 — **do not weaken**).
  - `reusable_after_refactor`: `quality_safety_eval_harness.py` (Layer-1 + fixture loader + regression-record shape —
    needs real golden pair, JSONL persistence, `overall_10`/`shippable` separation, Layer-2 judge),
    `quality_safety_unified_qa.py` (deterministic aggregation of Slices 108–113 — repoint at the real golden-pair path),
    `test_scripts/fixtures/quality_safety/*_synthetic.json` (keep as unit tests, **not** the real golden pair).
  - `archived_frozen_do_not_extend` (synthetic drift ≈ Slices 117–147 + production offline judge):
    `quality_safety_offline_judge_{core,schema,artifact_adapter}.py`, `quality_safety_fact_sheet_producer.py`,
    `quality_safety_operator_structured_numeric_export_validator.py`, `quality_safety_structured_numeric_candidate_adapter.py`,
    `quality_safety_safe_numeric_extractor.py`, `quality_safety_numeric_extraction_mapper.py`,
    `quality_safety_extraction_bundle_adapter.py`.
  - `unrelated_current_baseline` (live wired measurement layer, Slices 149–157 — keep, not the golden-pair harness):
    `guide_quality_{baseline,qa_gate,report_v2,rubric_score,contract_lint,prompt_contract}.py`,
    `quality_safety_job_artifact.py`.
  - `missing` (build next): real `nn3` + `ensemble` golden-pair fixtures with `ground_truth_numerics`; dev-time
    Layer-2 reference-anchored eval judge (separate from the frozen production judge); `overall_10`+`shippable`
    separated reporting wired to the real decks; append-only regression-record JSONL persistence.
- **next_slice=phase0_real_golden_pair_eval_harness_skeleton**
- **No code changed.** Docs-only grounding (one authoritative roadmap doc + short live-doc updates). **Docker NOT run;
  no docker compose config was run.** `local_operator_baselines/` stayed ignored/uncommitted; no guide text/snippets/
  raw artifacts/paths/fingerprints committed; Slice 60 stash untouched. **Slice 159 remains UNCOMMITTED.**

---

## Slice 158 — **Lean QA-gate warning triage**, on `slice158-qa-gate-warning-triage`. **Committed `3a44c91`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 157 was committed as `5ab92f0` ("Slice 157: Add current app state inspection report"),
  fast-forward merged to trunk `chrome-renderer-v1` (`8f27091..5ab92f0`), and pushed with a normal `git push` (no
  force-push). Final trunk status was clean; **no docker compose config was run**; the Slice 60 trace stash remains
  parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted; no private material was committed.
- **Goal:** explain why the current best measured run (`app_run_6_reasoning_fix_iteration_2`) still reads
  `guide_quality_qa_gate_status=warning` / `baseline_status=warning`. Lean triage — no new measurement infrastructure,
  no `known_numbers`, no style audit, no figure/table work, no judge/repair, no private guide snippets.
- **Closed triage result (`current_best_run=app_run_6`):**
  - `guide_quality_qa_gate_status=warning`, `baseline_status=warning`, `numeric_math_status=not_available`.
  - The QA gate's `warning_count=2` (of 5 checks; 3 passed): the `math_verification` check is `warning` and the
    `quality_report_v2` check is `warning`. All of `reasoning_leak`, `required_structure`, `source_coverage` pass.
  - **`math_verification` warning** = the production math_verifier ran on the real guide and reported `mismatch>0`
    (closed token `math_verification_mismatch_present`). The stored gate reads the verifier's nested `report.summary`
    correctly. Whether those mismatches are true math errors vs verifier false positives is **unconfirmed** — it would
    require reading the private guide's flagged expressions.
  - **`quality_report_v2` warning** = closed tokens `source_page_signal_missing`, `missing_material_signal_missing`,
    `coverage_signal_missing` (no page-citation / coverage / missing-material signals detected) — an observability /
    citation product gap, not a gate bug.
  - **`baseline_status=warning` is driven solely by the QA gate** (`gate.status=warning → warning`). Every other
    metric is `pass`/`not_available`; the baseline → gate mapping is **correct** (not a mapping or threshold bug).
  - **Separate latent finding (NOT the warning driver, left unfixed):** the baseline's `_extract_artifact_scalars`
    reads top-level `data.get("summary")` for every artifact, but `math_verification.json` nests its summary under
    `report.summary` (the QA gate's own `_math_summary` reads it correctly). So the baseline's `numeric_math`
    derivation never sees `total`/`mismatch`, yielding `numeric_math_status=not_available`. **Deliberately not
    patched here** — surfacing the unconfirmed mismatches as `FAIL` would expand numeric measurement against the
    numeric-freeze directive; the production math signal is already visible via the QA gate, so nothing is hidden.
- **Closed triage tokens:**
  - `qa_gate_warning_triage=run`
  - `current_best_run=app_run_6`
  - `guide_quality_qa_gate_status=warning`
  - `numeric_math_status=not_available`
  - `warning_root_category=mixed` (production math_verifier `mismatch>0` needing private-guide confirmation +
    `quality_report_v2` coverage/citation signal-missing; the gate/baseline mapping itself is correct)
  - `baseline_mapping_changed=false`
  - `qa_gate_changed=false`
  - `math_verifier_changed=false`
  - `next_step=phase0_eval_harness_fact_sheet_skeleton`
- **Strategic correction (supersedes the prior multi-guide/product-fix pick):** `docs/GUIDEFORGE_MASTER_ROADMAP.md`
  is now the authoritative phase order. The earlier `next_step=multi_guide_read_then_product_fix` is **superseded** —
  the next step is **Phase 0: eval harness + fact-sheet skeleton**, not multi-guide/product-fix work. Records:
  - `master_roadmap_adopted=true`
  - `authoritative_phase_order=GUIDEFORGE_MASTER_ROADMAP.md`
  - `do_not_reorder_phases=true`
  - `production_offline_judge_frozen=true`
  - `dev_time_reference_anchored_eval_allowed=true`
  - `numeric_strategy=recompute_first_not_manual_known_numbers`
- **No code changed.** Docs-only triage (true/mixed product gap → do not fix product behavior here).
- **Validation (all green on unchanged tree):** baseline (207), baseline harness, prompt contract (143), contract
  lint (150), QA gate (177), `compileall api pipeline test_scripts`, `git diff --check`. Closed `app_run_6` harness
  rerun confirms the statuses above (closed summary only). **Docker NOT run; no docker compose config was run.**
- **`local_operator_baselines/` stayed ignored/uncommitted; no guide text/snippets/aliases/raw artifacts/paths/
  fingerprints committed; Slice 60 stash untouched. Slice 158 remains UNCOMMITTED.**

---

## Slice 157 — **Current App State Inspection Report**, on `slice157-current-app-state-inspection-report`. **Committed `5ab92f0`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 156 was committed as `8f27091` ("Slice 156: Observe reference completeness and figure
  handling via closed local guide-text scanner"), fast-forward merged to trunk `chrome-renderer-v1`
  (`35c6b71..8f27091`), and pushed with a normal `git push` (no force-push). Final trunk status before branching Slice
  157 was clean; **no docker compose config was run**; the Slice 60 trace stash remains parked and untouched;
  `local_operator_baselines/` stayed ignored/uncommitted; no guide text/snippets/matched aliases/raw artifacts/private
  paths/private fingerprints were committed.
- **What this slice is:** a full current-state inspection / analysis / documentation report of the GuideForge app,
  based on the live trunk after Slice 156. **Inspection only** — no product features, no runtime/API/frontend/
  backend/pipeline logic change, no test change, no private `local_operator_baselines/` content inspected beyond
  confirming the folder stays ignored.
- **Created:** `docs/GUIDEFORGE_CURRENT_STATE_INSPECTION.md` (12 sections: Executive Summary, Architecture Overview,
  User-Facing Feature Inventory, Backend API Inventory, Pipeline Module Inventory, Artifact Inventory, Quality Safety
  + Measured Baseline History, Slice History Summary, Test/Validation Inventory, Gap/Risk Register, Recommended Next
  10 Slices, New Chat Handoff). Closed labels only — no guide text, snippets, matched aliases, source text, raw
  artifacts, hashes, byte counts, paths, screenshots, PDFs/DOCX/ZIPs, provider payloads, or secrets.
- **Validation:** read-only repo inspection (`git log`, route/module/test enumeration) + fast suites — baseline (207),
  prompt contract (143), contract lint (150), QA gate (177), `compileall api pipeline test_scripts` clean; `app_run_6`
  local harness both modes (closed counts only). **Docker was NOT run; no docker compose config was run.**
- **Closed `app_run_6` status recorded (committed docs only):** `reasoning_leak_status=pass`,
  `source_coverage_status=pass`, `reference_relative_completeness_status=pass`, `figure_handling_status=pass`,
  `baseline_status=warning`; remaining gap `numeric_math_status=not_available` + QA-gate warning.
- **Committed `5ab92f0`, fast-forward merged to `chrome-renderer-v1` (`8f27091..5ab92f0`), pushed (no force-push).**
  Followed by Slice 158 (QA-gate warning triage) — see entry above.

---

## Slice 156 — **Closed Local Guide Coverage Baseline**, on `slice156-closed-local-guide-coverage-baseline`. **Committed `8f27091`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 155 was committed as `35c6b71` ("Slice 155: Observe source coverage baseline
  status"), fast-forward merged to trunk `chrome-renderer-v1` (`1dae76f..35c6b71`), and pushed with a normal
  `git push` (no force-push). Final trunk status before branching Slice 156 was clean; **no docker compose config
  was run**; the Slice 60 trace stash remains parked and untouched; `local_operator_baselines/` stayed
  ignored/uncommitted.
- **Goal:** make `reference_relative_completeness_status` and `figure_handling_status` measurable (off
  `needs_future_metric`) using a **closed local-only guide-text scanner** that emits closed counts/statuses only,
  reading a local gitignored generated-guide text file — never committing the guide text or snippets.
- **Implementation (closed-count scanner, no new evaluator stack):**
  - `pipeline/guide_quality_baseline.py`: added `collect_guide_quality_baseline_guide_text_metrics(guide_text,
    golden_spec)` (deterministic lowercase + punctuation-strip + whitespace-collapse + alias matching) returning
    **closed counts/statuses only** — never text, snippets, matched aliases, paths, or filenames. Added optional
    `guide_text_metrics=` to `build_guide_quality_baseline_record(...)`; when supplied it observes the two metrics
    from the closed counts (source `guide_text_scan`) and embeds a closed `guide_text_coverage` counts block.
    Without it, legacy `needs_future_metric` derivation is unchanged. Closed figure "explained-missing" markers
    (e.g. "cannot be reproduced", "diagram explained") count an expected figure as handled. No OCR / PDF parse /
    image inspection / LLM call.
  - Golden spec extended with closed alias checks only: `reference_completeness_checks`, `figure_handling_checks`,
    `section_coverage_checks` (short concept labels + general educational aliases; path-like aliases stripped by
    normalization).
  - `test_scripts/validate_guide_quality_baseline_harness.py`: added optional `--guide-text` local mode (reads the
    file, computes closed coverage, surfaces closed counts; path/text/alias never printed; path-leak guard extended
    to the guide-text path). Omitting `--guide-text` preserves prior behavior.
- **Closed flags:**
  - `closed_local_guide_coverage_baseline=run`
  - `local_guide_text_available=true`
  - `local_guide_text_committed=false`
  - `raw_guide_text_committed=false`
  - `snippet_committed=false`
  - `source_pdf_parsed=false`
  - `ocr_used=false`
  - `lmm_or_judge_used=false`
  - `reference_relative_completeness_status_before=needs_future_metric`
  - `reference_relative_completeness_status_after=pass`
  - `figure_handling_status_before=needs_future_metric`
  - `figure_handling_status_after=pass`
  - `source_coverage_status=pass`
  - `reasoning_leak_status=pass`
  - `baseline_status=warning`
  - `next_step=style_preset_audit_gate`
- **Measured `app_run_6_reasoning_fix_iteration_2` (with `--guide-text`, closed counts only):**
  `reference_relative_completeness_status=pass` (`matched_reference_check_count=4`, `missing_reference_check_count=0`),
  `figure_handling_status=pass` (`matched_figure_check_count=1`, `missing_figure_check_count=0`), section coverage
  `matched_section_check_count=2` of `section_check_count=3`, `baseline_status=warning` (still driven by the QA-gate
  warning + numeric `not_available`, **not** by the new metrics — no failure hidden). Without `--guide-text` both
  metrics correctly stay `needs_future_metric` (`local_guide_text_available=false`). No matched-alias text, snippet,
  or path recorded.
- **Local guide text:** copied the local job's `clean.md` into the gitignored path
  `local_operator_baselines/nn_iris/app_guide_text/app_run_6_reasoning_fix_iteration_2.clean.local.md` (confirmed
  ignored); read only at runtime to compute closed counts. **Not committed; contents never pasted.**
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`,
  `M docs/GUIDE_QUALITY_BASELINE_HARNESS.md`, `M pipeline/guide_quality_baseline.py`,
  `M test_scripts/test_guide_quality_baseline.py`, `M test_scripts/validate_guide_quality_baseline_harness.py`,
  `M test_scripts/fixtures/guide_quality_baseline/nn_iris_local_golden_spec.json`.
- **Validation (all green):** baseline tests (207, was 131; +15 Slice 156 synthetic cases + 1 stdlib-allow update),
  baseline harness synthetic self-test (`ok`), prompt contract (143), contract lint (150), QA gate (177),
  `compileall api pipeline test_scripts` clean; `app_run_6` local harness both modes (without `--guide-text` →
  metrics `needs_future_metric`; with `--guide-text` → `reference`/`figure` both `pass`); `git diff --check` clean;
  no-leak sweep clean. **Docker was NOT run; no docker compose config was run.**
- **Next gate:** `style_preset_audit_gate` — reasoning-leak, source coverage, reference completeness, and figure
  handling now all read green for `app_run_6`. **Slice 156 remains UNCOMMITTED.**

---

## Slice 155 — **Source Coverage / Completeness Baseline Gap**, on `slice155-source-coverage-completeness-baseline-gap`. **Committed `35c6b71`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 154 was committed as `1dae76f` ("Slice 154: Harden prompt contract for line-initial
  discourse leaks"), fast-forward merged to trunk `chrome-renderer-v1` (`af606d4..1dae76f`), and pushed with a normal
  `git push` (no force-push). Final trunk status before branching Slice 155 was clean; **no docker compose config was run**;
  the Slice 60 trace stash remains parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted. (Three
  Slice 154 doc lines that described the source attachment with fingerprint-level provenance were softened to the closed
  label `source_match_verified=true` before committing, so no source hash / byte count / source fingerprint was committed.)
- **Goal:** close the next measured baseline gap after the reasoning leak passed — `source_coverage_status=not_observed` on
  `app_run_6_reasoning_fix_iteration_2`, despite `source_coverage_report.json` being an existing, wired artifact.
- **Outcome A — existing artifact mapping fixed (the next gap is genuinely closed).** Inspection found a closed-token
  mismatch in the baseline aggregator: the source coverage producer's **top-level** report status token is `completed`
  (`pipeline/source_coverage_report.py::_top_level_status`), while the per-source token is `complete`. The baseline
  aggregator's `_derive_source_coverage` (`pipeline/guide_quality_baseline.py`) only mapped `{"complete", "ok"}` → pass,
  so a fully-covered source's `completed` top status silently fell through to `not_observed`. The QA gate already handled
  `completed` correctly (only `{partial, unreadable}` count as incomplete there), and the baseline aggregator's own
  synthetic test used a `complete` fixture the real producer never emits — so the gap was hidden, not a true absence of data.
- **Fix (narrow, closed-token only):** added `"completed"` to the pass set in `_derive_source_coverage`; added the real
  producer top-level token `("completed", "pass")` as a regression case in `test_source_coverage_status_derivation`. No
  detector, prompt-contract, QA-gate, producer, API, UI, renderer, export, OCR, table, visual, judge, or repair change.
- **Closed flags:**
  - `source_coverage_gap_investigation=run`
  - `status=ok`
  - `app_run_6_baseline_reference=closed_summary_only`
  - `reasoning_leak_status=pass`
  - `baseline_status=warning`
  - `source_coverage_status_before=not_observed`
  - `source_coverage_status_after=pass`
  - `source_coverage_artifact_present=true`
  - `source_coverage_closed_fields_available=true`
  - `source_coverage_mapping_changed=true`
  - `reference_relative_completeness_status=needs_future_metric`
  - `figure_handling_status=needs_future_metric`
  - `next_step=reference_completeness_or_figure_gap`
- **Reference completeness / figure handling stay deferred (verified, not assumed):** `_derive_reference_relative_completeness`
  and `_derive_figure_handling` already explain that existing wired artifacts expose no concept/section labels or figure ids
  that can be matched against the golden spec without parsing guide text or images. Source coverage exposes only a closed
  `visual_candidate_pages` counter, not figure-id-level handling. Gap reasons: `existing_artifacts_do_not_expose_safe_reference_labels`,
  `source_coverage_report_lacks_visual_closed_counts`. Both remain `needs_future_metric` — no faking.
- **Local artifact inspection:** `app_run_6` (and `app_run_5`) `source_coverage_report.json` were inspected **key/status/count-only**
  (top-level keys, `status=completed`, per-source `status=complete`, summary key names, int-ness of counts) — no raw JSON, source
  filenames, paths, page text, snippets, OCR text, captions, or extracted source material were printed or committed.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`,
  `M pipeline/guide_quality_baseline.py`, `M test_scripts/test_guide_quality_baseline.py`.
- **Validation (all green):** baseline tests (131, was 130), baseline harness synthetic self-test (`ok`), reasoning-leak protection
  — prompt contract (143), contract lint (150), QA gate (177), `compileall api pipeline test_scripts` clean; `app_run_6` local
  harness rerun (`source_coverage_status` `not_observed`→`pass`, `reasoning_leak_status=pass`, `baseline_status=warning`);
  `app_run_5` local harness rerun (`source_coverage_status=pass` now, but `reasoning_leak_status=fail` still → `baseline_status=failed`
  — the fix did not hide any failure); `git diff --check` clean; no-leak sweep clean. **Docker was NOT run; no docker compose config
  was run.**
- **Next gate:** `reference_completeness_or_figure_gap` — both need a new closed-field artifact before they can move off
  `needs_future_metric`; style/preset audit (`style_preset_audit_gate`) remains available now that reasoning-leak and source
  coverage both read green. **Slice 155 remains UNCOMMITTED.**

---

## Slice 154 — **Reasoning Leak Fix Iteration 2 (prompt-contract line-initial discourse-marker hardening)**, on `slice154-reasoning-leak-fix-iteration-2`. **Committed `1dae76f`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 153 was committed as `af606d4` ("Slice 153: Verify app-pipeline baseline provenance"),
  fast-forward merged to trunk `chrome-renderer-v1` (`a1dfdd4..af606d4`), and pushed with a normal `git push` (no force-push).
  Final trunk status before branching Slice 154 was clean; **no docker compose config was run**; the Slice 60 trace stash remains
  parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted.
- **What this slice is:** the narrowest second prompt/output-contract fix for the single residual leak category that
  `app_run_5_app_pipeline_verified` surfaced (`reasoning_leak_status=fail`, `baseline_status=failed`). The remaining hit is a
  **line-initial discourse/intensifier marker** (`target_category=line_initial_discourse_intensifier`) — a sentence/paragraph
  opening with `Actually,` / `Presumably,` that the Slice 152 hardened detector intentionally counts as a true positive. The
  detector is behaving as designed, so the fix is at the prompt-contract layer, not the detector.
- **Fix type:** `prompt_contract_line_initial_discourse_marker_hardening`. Added one concise core rule to the shared
  `_CORE_RULES` chokepoint in `pipeline/guide_quality_prompt_contract.py` (the same always-applied contract Slice 151 hardened,
  appended once as the `## Guide Quality Contract` block in `pipeline/run_llm_job.py`). The new rule requires **direct
  instructional prose** and forbids beginning a sentence or paragraph with a conversational correction / reasoning discourse
  marker such as `Actually,` / `Presumably,`, instructing the model to state the corrected fact plainly instead. It does not ask
  the model to reveal hidden reasoning and does not reduce comprehensiveness.
- **Closed flags:**
  - `target_category=line_initial_discourse_intensifier`
  - `detector_changed=false`
  - `baseline_mapping_changed=false`
  - `generation_prompt_changed=true`
  - `provider_calls=false` (no operator regeneration during this slice)
  - `judge_calls=false`
  - `repair_calls=false`
- **Measured verification gate — RUN (Case A / PASS):** the app runtime was rebuilt + restarted onto this Slice 154 working tree
  (the prompt contract is COPY'd into the image, so a rebuild was required for the running app to serve the new contract), confirmed
  live (`/api/health` ok), and one fresh NN/Iris app guide was generated through the normal app pipeline with settings matching
  `app_run_5` (DeepSeek `deepseek-v4-pro`, generator preset `claude_review`, the same custom style, same section toggles,
  `strict_math` + `dual_explanation_mode` on, the same source as `app_run_5` (`source_match_verified=true`)).
  No special one-off anti-leak user prompt was added; the fix was exercised only through the app's shared Guide Quality Contract.
  The 6 exact-name artifacts were copied into `local_operator_baselines/nn_iris/app_job_artifacts/app_run_6_reasoning_fix_iteration_2/`
  (ignored/uncommitted) and the baseline harness was run on that run label.
  - `reasoning_leak_fix_iteration_2_local_regeneration_run=closed_summary_only`
  - `app_run_6_reasoning_fix_iteration_2`:
    - `reasoning_leak_status: pass`
    - `numeric_math_status: not_available`
    - `guide_quality_qa_gate_status: warning`
    - `source_coverage_status: not_observed`
    - `structure_contract_status: pass`
    - `reference_relative_completeness_status: needs_future_metric`
    - `figure_handling_status: needs_future_metric`
    - `artifact_existence_status: pass`
    - `baseline_status: warning`
  - **Provenance of the pass (genuine, not a harness quirk):** the app's stored contract-lint artifact reports
    `reasoning_leak_count=0` for `app_run_6` vs `reasoning_leak_count=1` for `app_run_5` — the single residual line-initial
    discourse/intensifier marker that failed `app_run_5` is gone, and `structure_contract_status` improved `warning`→`pass`. The
    detector was unchanged between the two runs, so the drop to zero is attributable to the Slice 154 prompt-contract hardening.
  - `fix_verification_status=pass`
  - `next_step=source_coverage_gap_or_style_preset_audit_gate`
- **Slice 154 is now commit-ready** (the measured gate passed). Remaining residual statuses (`qa_gate=warning`,
  `source_coverage=not_observed`, numeric/figure/reference `needs_future_metric`) are pre-existing baseline limitations unrelated to
  the reasoning-leak fix and are deferred to the next gate (`source_coverage_gap_or_style_preset_audit_gate`).
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`,
  `M pipeline/guide_quality_prompt_contract.py`, `M test_scripts/test_guide_quality_prompt_contract.py`. Detector, baseline
  aggregator, API, frontend, providers, renderer, exports, OCR, tables, visuals, Ask Guide, repair, and judge are unchanged.
- **Validation (all green):** prompt contract (143, was 110), contract integration (24), contract lint (150), QA gate (177),
  baseline tests (130), baseline harness synthetic self-test (`ok`), `compileall api pipeline
  test_scripts` clean; `app_run_5_app_pipeline_verified` local harness rerun (record preserved: `reasoning_leak_status=fail`,
  `baseline_status=failed`); `app_run_6_reasoning_fix_iteration_2` local harness run (`reasoning_leak_status=pass`,
  `baseline_status=warning`); `git diff --check` clean; no-leak sweep clean. **Docker WAS used this gate** — the image was rebuilt
  and the container restarted so the running app served the Slice 154 prompt contract; **no docker compose config was run.**
- **Style/preset audit stays deferred** until the reasoning-leak baseline passes — it now has (`app_run_6` green on reasoning
  leak), so the next gate is `source_coverage_gap_or_style_preset_audit_gate`. **Slice 154 remains UNCOMMITTED (per this gate).**

---

## Slice 153 — **App-Pipeline Baseline Provenance Gate**, on `slice153-app-pipeline-baseline-provenance-gate`. **Committed `af606d4`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 152 was committed as `a1dfdd4` ("Slice 152: Harden reasoning leak detector boundaries"),
  fast-forward merged to trunk `chrome-renderer-v1` (`d5d528a..a1dfdd4`), and pushed with a normal `git push` (no force-push).
  Final trunk status before branching Slice 153 was clean; **no docker compose config was run**; the Slice 60 trace stash remains
  parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted.
- **What this slice is:** an operator **provenance gate**, not a feature. It verifies the full app pipeline after Slice 151
  prompt-contract hardening and Slice 152 detector hardening by generating one fresh local NN/Iris app guide on the **restarted**
  runtime and recording closed aggregate baseline metrics for `app_run_5_app_pipeline_verified`. No code change. No prompt/detector/
  baseline-logic change. No style/preset audit.
- **Operator action performed:** the running app was restarted/recreated on this working tree (trunk = Slice 151 + 152), confirmed
  live (`/api/health` ok), and one fresh app guide was generated from the same local NN/Iris source with settings close to
  `app_run_3`/`app_run_4`. The 6 exact-name artifacts were copied into the ignored
  `local_operator_baselines/nn_iris/app_job_artifacts/app_run_5_app_pipeline_verified/`. No generated guide or raw artifact was
  committed.
- **Provenance VERIFIED (the key result):** `runtime_refreshed_after_slice152=true`. The app's stored contract-lint artifact reports
  `reasoning_leak_count=1`, and recomputing the **hardened working-tree detector** over the **same** fresh guide also yields `1`
  (pre-fix `app_run_4` was `2`). Matching counts prove the running app served the Slice 152 hardened detector — app-pipeline
  provenance is genuine, not a deterministic recompute.
- **Honest measured outcome — a genuine residual leak, NOT a false positive:** the single hit is a **context-gated intensifier**
  (high-precision phrase tier = 0; intensifier tier = 1), classified in closed vocabulary as a **line-initial `actually` discourse
  marker** (`branch=LINE_START`, not a markdown heading/list marker, not mid-sentence). Per Slice 152's deliberate design a
  sentence/line-initial `Actually,`/`Presumably,` is an **intended true positive** (self-correction tone in settled prose), so this
  is a real reasoning-leak that the Slice 151 prompt contract did not suppress — **not** a detector boundary false positive.
  Hardening the detector to drop line-initial intensifiers would weaken true-positive detection (forbidden), so the fix belongs in
  the prompt contract.
- **`app_run_5_app_pipeline_verified` closed baseline (summary only):**
  - `reasoning_leak_status: fail` (1 genuine line-initial intensifier discourse marker)
  - `numeric_math_status: not_available`
  - `guide_quality_qa_gate_status: warning`
  - `source_coverage_status: not_observed`
  - `structure_contract_status: warning`
  - `reference_relative_completeness_status: needs_future_metric`
  - `figure_handling_status: needs_future_metric`
  - `artifact_existence_status: pass`
  - `baseline_status: failed`
- **Gate record:**
  - `app_pipeline_baseline_provenance_gate: run`
  - `status: warning` (provenance verification **succeeded**; the gate's hoped-for `reasoning_leak_status=pass` was **not** met
    because a genuine residual leak remains — recorded honestly, not hidden)
  - `runtime_refreshed_after_slice152: true`
  - `local_operator_material_committed: false`
  - `raw_artifact_json_committed: false`
  - `generated_guide_committed: false`
  - `provider_calls: true` (one fresh app generation through the normal pipeline)
  - `judge_calls: false`
  - `repair_calls: false`
  - `next_step: reasoning_leak_fix_iteration_2`
- **Decision rule applied:** `reasoning_leak_status=fail` → closed triage → category is a genuine line-initial intensifier
  discourse marker (a true positive, not a detector limitation) → `next_step=reasoning_leak_fix_iteration_2` (tighten the prompt
  contract / final-output hygiene to suppress sentence-initial self-correction discourse markers). Detector hardening iteration is
  **not** indicated — the detector is behaving as designed. Style/preset audit stays deferred until the reasoning-leak baseline is
  green or explicitly waived.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`. No code changes.
- **Validation (all green):** contract lint (150), QA gate (177), baseline tests (130), baseline harness synthetic self-test
  (`ok`), prompt contract (110), `compileall api pipeline test_scripts` clean; `app_run_5_app_pipeline_verified` local harness run
  (`baseline_harness_status=ok`, statuses above); `git diff --check` clean; no-leak sweep clean. Docker used only to restart the
  local app; **no docker compose config run.**
- **Slice 153 is commit-ready (docs only) but remains UNCOMMITTED per the gate.** First action next chat: commit Slice 153 docs on
  its branch, then proceed to `reasoning_leak_fix_iteration_2`.

---

## Slice 152 — **Contract-Lint False-Positive Hardening (detector boundary)**, on `slice152-contract-lint-false-positive-hardening`. **Committed `a1dfdd4`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 151 was committed as `d5d528a` ("Slice 151: Harden guide prompt contract against reasoning
  leaks"), fast-forward merged to trunk `chrome-renderer-v1` (`d6f9f87..d5d528a`), and pushed with a normal `git push` (no
  force-push). Final trunk status before branching Slice 152 was clean; **no docker compose config was run**; the Slice 60 trace
  stash remains parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted.
- **What this slice is:** harden the guide-quality **contract-lint** reasoning-leak detector boundary so
  `detector_boundary_false_positive` hits (mid-sentence factual intensifiers) no longer keep the measured baseline red, while
  **preserving** detection of genuine internal-reasoning / prompt-meta / planning / process-narration leaks. It does **not** start
  a style/preset audit, judge work, or repair, and it does **not** map `leak_count > 0 → pass` or patch the baseline aggregator.
- **Fix type: `contract_lint_detector_boundary_hardening`** in `pipeline/guide_quality_contract_lint.py`. The old detector
  summed raw `lowered.count(sig)` over a flat signature list that included `"actually,"` / `"actually "` / `"presumably"`, so any
  mid-sentence factual intensifier (`"the model actually outputs ..."`, `"this value is presumably rounded ..."`) over-flagged
  as a leak — the exact `detector_boundary_false_positive` Slices 150–151 isolated. The detector now uses two tiers:
  - **High-precision phrases** (word-boundary matched, not raw substrings): the existing internal-reasoning/uncertainty phrases
    plus added prompt/user-intent, planning/drafting, and "deciding what to include" phrases. Word boundaries stop a phrase
    firing inside a longer token (e.g. `"is unclear"` no longer matches inside `"unclearly"`).
  - **Context-gated intensifiers** (`"actually"` / `"presumably"`): counted **only** when sentence-initial (start of text,
    after sentence-ending punctuation, or at a line/list/heading start), i.e. used as a self-correction discourse marker — never
    as mid-sentence factual prose.
- **Output shape unchanged.** `reasoning_leak_count` / `reasoning_leak_status` / `warning_count` / warning tokens are all
  identical in shape; only the counting logic changed. So **no baseline / aggregator change was needed.**
  - `false_positive_target=detector_boundary_false_positive`
  - `true_leak_detection_preserved=true` (synthetic-verified; see below)
  - `prompt_contract_changed=false` · `baseline_mapping_changed=false`
  - `provider_calls=false` · `judge_calls=false` · `repair_calls=false`. No model call, no provider/render/export/OCR/table/
    visual change, no request-schema/Builder/Ask/API/UI change, no new gate, no blocking behaviour, no
    `quality_judge.py`/`nn3.json`/`judge_response_nn3.json`/`quality.jsonl`, no `judge_ready`/`repair_ready` flip.
- **Detection NOT weakened.** The reasoning-leak category and the baseline `count > 0 → fail` mapping are intact; only the
  boundary between factual prose and a genuine leak moved.
- **Synthetic detector verification:**
  - `synthetic_false_positive_cases=pass` — factual intensifier prose (`"actually"`/`"presumably"` mid-sentence) now counts
    **0** leaks and the reasoning-leak check `passed`; a substring-inside-a-word case (`"unclearly"`) also counts 0.
  - `synthetic_true_positive_cases=pass` — synthetic canaries for internal reasoning, user-intent analysis, prompt-meta,
    planning/drafting, deciding-what-to-include, process narration, and a sentence-initial intensifier marker all still count
    `>= 1` and warn `reasoning_leak_present`; the no-store invariant still holds (no matched phrase appears in the report).
- **Local measured verification (honest) — Option B recompute, now CLOSED:**
  - `detector_hardening_local_recompute_run=closed_summary_only`
  - **Provenance note:** the operator regenerated one fresh app guide from the same local NN/Iris source on this branch, but
    the running app was still serving the **pre-fix** detector module (not restarted after the Slice 152 edit), so the fresh job's
    stored contract-lint artifact baked in a pre-fix `reasoning_leak_count=2` — both hits the bare substring `"actually "` used
    **mid-sentence** (the exact `detector_boundary_false_positive`). The hardened working-tree detector run over the **same** fresh
    guide counts **0**. Per operator decision (Option B), the hardened detector was re-run **deterministically** over the fresh
    guide to produce the hardened contract-lint artifact for `app_run_4_detector_hardened`; all other measured artifacts
    (`math_verification`, `qa_gate`, `report_v2`, `source_coverage`, `rubric_score`) were copied as generated (Slice 152 does not
    touch them). No baseline aggregator was patched and no leak failure was hidden — the recompute is the legitimate hardened
    detector, not a mapping change.
  - **`app_run_4_detector_hardened` closed baseline (summary only):**
    - `reasoning_leak_status: pass`
    - `numeric_math_status: not_available`
    - `guide_quality_qa_gate_status: warning`
    - `source_coverage_status: not_observed`
    - `structure_contract_status: warning`
    - `reference_relative_completeness_status: needs_future_metric`
    - `figure_handling_status: needs_future_metric`
    - `artifact_existence_status: pass`
    - `baseline_status: warning` (remaining warnings — qa_gate, 9/10 structure, future-metric placeholders — are pre-existing
      measured-baseline observations outside Slice 152's scope; the reasoning-leak gate is green).
  - `detector_hardening_verification_status=pass`
  - The stale `app_run_1`/`app_run_2`/`app_run_3_reasoning_fix` artifacts still report `reasoning_leak_status=fail` when rerun
    (expected — old pre-fix counts; historical record preserved).
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`,
  `M pipeline/guide_quality_contract_lint.py`, `M test_scripts/test_guide_quality_contract_lint.py`.
- **Validation (all green):** contract lint (150 passed, was 83), QA gate (177), baseline tests (130), baseline harness
  synthetic self-test (`ok`), prompt contract (110 — Slice 151 still holds), contract integration (24), release validation
  (234); the three reproducible local runs (`app_run_1`/`app_run_2`/`app_run_3_reasoning_fix`: `reasoning_leak_status=fail`
  unchanged, stale-count record preserved); `compileall api pipeline test_scripts` clean; `git diff --check` clean; no-leak
  sweep clean. Docker not required (no production/API/UI change); **no docker compose config run.**
- **`next_step=style_preset_audit_gate_or_source_coverage_gap`** — synthetic false-positive/true-positive cases pass **and** the
  fresh local `app_run_4_detector_hardened` measured run reports `reasoning_leak_status=pass`, so detector hardening is verified on
  a real fresh app guide. **Slice 152 is commit-ready** (docs updated, validation green) but per the gate **remains uncommitted**
  in this turn. The next gate is `style_preset_audit` (or `source_coverage_gap`); both stay deferred until explicitly started.

---

## Slice 151 — **First Measured Reasoning Leak Fix (prompt-contract hardening)**, on `slice151-first-measured-reasoning-leak-fix`. **Committed `d5d528a`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 150 was committed as `d6f9f87` ("Slice 150: Triage measured reasoning leak baseline failure"),
  fast-forward merged to trunk `chrome-renderer-v1` (`7e298b6..d6f9f87`), and pushed with a normal `git push` (no force-push).
  Final trunk status before branching Slice 151 was clean; **no docker compose config was run**; the Slice 60 trace stash
  remains parked and untouched; `local_operator_baselines/` stayed ignored/uncommitted.
- **What this slice is:** the **first narrow measured reasoning-leak fix** for the true leak confirmed in Slice 150
  (`app_run_2`, `leak_category=internal_reasoning_phrase`). It does **not** start a style/preset audit, judge work, repair, or a
  general quality rewrite.
- **Fix type: `prompt_contract_hardening`.** The shared chokepoint is `pipeline/guide_quality_prompt_contract.py`
  `_CORE_RULES` (built by `build_guide_quality_prompt_contract`, appended **last** in `pipeline/run_llm_job.py` as the
  `## Guide Quality Contract` block). Core rules are always included for **every** generation (paste or attachment, any
  style/preset including custom styles, comprehensive or not), so they cannot be omitted or overridden by a style. The existing
  rule #2 banned only hedge/uncertainty words; this slice adds one concise **final-output hygiene** core rule that bans the
  broader `internal_reasoning_phrase` category: internal reasoning, hidden analysis, prompt/instruction analysis, commentary on
  what the prompt or user is asking for, planning/drafting notes, process narration, and meta-commentary — requiring the final
  guide to contain only student-facing study content. The clause does **not** ask the model to reveal or summarise hidden
  reasoning.
- **Scope discipline:**
  - `true_leak_target=app_run_2_internal_reasoning_phrase`
  - `app_run_1_false_positive_hardening=deferred` (the `detector_boundary_false_positive` / intensifier over-flagging stays a
    Slice 152 candidate — not combined here; contract-lint detection was not touched).
  - `generation_prompt_changed=true` (the always-applied core contract gained one rule).
  - `provider_calls=false` · `judge_calls=false` · `repair_calls=false`. No model call, no provider/render/export/OCR/table/
    visual change, no request-schema change, no Builder/Ask-Guide/API/UI change, no new gate, no blocking behaviour, no
    `quality_judge.py`/`nn3.json`/`judge_response_nn3.json`/`quality.jsonl`, no `judge_ready`/`repair_ready` flip.
- **Detection NOT weakened.** Reasoning-leak detection and the baseline `count > 0 → fail` mapping are unchanged; the measured
  `app_run_1`/`app_run_2` baselines still report `reasoning_leak_status=fail` (the true leak is **not** suppressed).
- **Fix verification (honest) — MEASURED, closed-summary only:**
  - `reasoning_leak_fix_local_regeneration_run=closed_summary_only`
  - The operator regenerated one app guide from the same local NN/Iris source on this branch; exact-name artifacts were copied
    into the ignored `local_operator_baselines/nn_iris/app_job_artifacts/app_run_3_reasoning_fix/` and the Slice 149 local
    baseline harness was rerun. Closed aggregate statuses:
    ```
    app_run_3_reasoning_fix:
      reasoning_leak_status: fail
      numeric_math_status: not_available
      guide_quality_qa_gate_status: warning
      source_coverage_status: not_observed
      structure_contract_status: warning
      reference_relative_completeness_status: needs_future_metric
      figure_handling_status: needs_future_metric
      artifact_existence_status: pass
    ```
  - **Closed-record triage of the new run (only closed category tokens emitted; no guide text / phrase / count printed to docs):**
    the genuine `internal_reasoning_phrase` category that produced the `app_run_2` true leak is **absent** in `app_run_3`
    (`true_internal_reasoning_phrase_hits=0`, boundary-aware). The remaining `reasoning_leak_count>0` is composed **only** of
    `detector_boundary_false_positive` hits — mid-sentence factual intensifiers (`"actually"`/`"presumably"`) the crude
    substring detector over-flags, the exact secondary finding Slice 150 surfaced on `app_run_1`. The prompt-contract hardening
    therefore **did eliminate the measured true leak**, but the baseline cannot turn green because the detector's known
    intensifier false-positive still fires.
  - `fix_verification_status=blocked_by_contract_lint_false_positive`
  - `next_step=contract_lint_false_positive_hardening`
  - **The true leak does NOT persist** (true-reasoning-phrase hits = 0); equally, the fix is **not** claimed to flip the baseline
    green — that is gated on the detector-hardening slice. Slice 151 remains **NOT committed** pending the operator's decision on
    sequencing (commit the verified prompt fix now, or fold in detector hardening first).
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`,
  `M pipeline/guide_quality_prompt_contract.py`, `M test_scripts/test_guide_quality_prompt_contract.py`.
- **Validation (all green):** prompt contract (110 passed), contract integration (24), contract lint (83), QA gate (177),
  release validation (234), baseline tests (130), baseline harness synthetic self-test (`ok`); the two reproducible local runs
  (`app_run_1`/`app_run_2`: `reasoning_leak_status=fail` unchanged, baseline record preserved) plus the new
  `app_run_3_reasoning_fix` run (`baseline_harness_status=ok`, `reasoning_leak_status=fail` driven by intensifier
  false-positives only); `compileall api pipeline test_scripts` clean; `git diff --check` clean; no-leak sweep clean. Docker not
  required (no production/API/UI change); **no docker compose config run.**
- **`next_step=contract_lint_false_positive_hardening`** — the measured regeneration (`app_run_3_reasoning_fix`) verified the
  prompt-contract hardening removed the `app_run_2` true leak, but the baseline is still red on `reasoning_leak_status` because
  the contract-lint detector over-flags factual intensifiers. The detector-hardening slice (give the reasoning-leak signatures
  word boundaries / context, and reconsider the `any count > 0 → hard fail` escalation) must land before the baseline can turn
  green. Style/preset audit stays deferred.

---

## Slice 150 — **Reasoning Leak Baseline Failure Triage (closed-record only)**, on `slice150-reasoning-leak-baseline-failure-triage`. **Committed `d6f9f87`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 149 was committed as `7e298b6` ("Slice 149: Add measured guide quality baseline harness"),
  fast-forward merged to trunk `chrome-renderer-v1` (`74ddf76..7e298b6`), and pushed with a normal `git push` (no force-push).
  The measured baseline failure (`baseline_status=failed`, `reasoning_leak_status=fail` on both app runs) was committed as an
  honest measured baseline record, **not** hidden. Final trunk status before branching Slice 150 was clean; **no docker compose
  config was run**; the Slice 60 trace stash remains parked and untouched.
- **What this slice is:** a narrow **closed-vocabulary triage** of the first measured baseline failure
  (`reasoning_leak_status=fail` on `app_run_1` and `app_run_2`). It decides whether the failure is a true reasoning leak in the
  generated guide, a contract-lint false positive, a baseline interpretation bug, or under-determined. No prompt tuning, no
  repair, no generation change, no judge/provider/model/cloud/local-LLM call, no new blocking gate, no rebuilt checks.
- **Baseline mapping verified correct (no code change).** The baseline collector whitelists `reasoning_leak_count` from
  `guide_quality_contract_lint.json`'s summary and `_derive_reasoning_leak` maps `count > 0 → fail` (headline first-class
  metric). The local artifacts carry a **real positive** `reasoning_leak_count` on both runs (no matched text stored), so the
  baseline correctly reports `fail` — this is **not** a baseline interpretation bug. No baseline / contract-lint / generation
  code was touched.
- **Local operator triage ran (closed record only).** Inspected only the local **gitignored** app job artifacts and app guide
  files under `local_operator_baselines/`; classification was computed programmatically and emits **closed category tokens
  only**. No guide/source/OCR/table/caption text, no leaking phrase, no count, no filename, no path, no raw artifact JSON, no
  snippet was printed into docs or committed.

  ```
  reasoning_leak_baseline_failure_triage: run
  status: ok
  input_scope: local_gitignored_operator_artifacts
  local_operator_material_committed: false
  raw_guide_text_committed: false
  raw_artifact_json_committed: false
  provider_calls: false
  judge_calls: false
  repair_calls: false
  baseline_mapping_changed: false
  runs:
    app_run_1:
      baseline_reasoning_leak_status: fail
      triage_status: contract_lint_false_positive
      leak_category: detector_boundary_false_positive
      fix_recommendation: contract_lint_hardening
    app_run_2:
      baseline_reasoning_leak_status: fail
      triage_status: true_reasoning_leak_visible
      leak_category: internal_reasoning_phrase
      fix_recommendation: prompt_contract_fix
  overall_decision: true_leak_confirmed
  next_step: first_measured_reasoning_leak_fix
  ```

- **Mixed result, honestly recorded.** `app_run_2` contains a **genuine** internal-reasoning phrase (matched with both-sided
  word boundaries; PDF-extracted reproduced count validated within ±2 of the artifact's `reasoning_leak_count`) → a real leak.
  `app_run_1` fired only on factual-intensifier signatures (`"actually "`, `"presumably"`) that the substring detector treats as
  hedges → a **detector false positive**. Headline decision is `true_leak_confirmed` because reasoning-leak is the first-class
  regression guard and at least one generated guide genuinely leaked internal reasoning. **Secondary finding:** the contract-lint
  reasoning-leak detector over-flags common factual intensifiers, and the baseline's `any count > 0 → hard fail` escalation will
  mislabel clean guides — both warrant a future `contract_lint_false_positive_hardening` slice.
- **Operator-authorization boundary held.** A prompt-contract fix is **proven warranted but NOT applied** — generation prompts are
  unchanged pending an explicit operator decision in a later slice. This slice records the recommendation only.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`. No code changed.
- **Validation (all green):** `test_guide_quality_baseline.py` (130 passed), `validate_guide_quality_baseline_harness.py`
  synthetic self-test (`baseline_harness_status=ok`, exit 0) plus the two reproducible local runs (`app_run_1`/`app_run_2`:
  `baseline_harness_status=ok`, exit 0, `reasoning_leak_status=fail` unchanged), `compileall api pipeline test_scripts` clean;
  `git diff --check` clean; no-leak sweep clean. Docker not required (no production/API/UI change); **no docker compose config
  run.**
- **Next recommended slice:** **Slice 151 — First Measured Reasoning Leak Fix** (operator-authorized prompt-contract fix for the
  `app_run_2` internal-reasoning leak; keep only if the measured `reasoning_leak_status` improves), with a parallel candidate
  `contract_lint_false_positive_hardening` for the intensifier over-flagging surfaced by `app_run_1`. Style/preset audit stays
  deferred until the first measured failure is handled.

---

## Slice 149 — **Measured Guide Quality Baseline Harness (reuse existing wired artifacts)**, on `slice149-measured-guide-quality-baseline-harness`. **Committed `7e298b6`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 148 was committed as `74ddf76` ("Slice 148: Freeze judge path and redirect to measured
  baseline"), fast-forward merged to trunk `chrome-renderer-v1` (`effc9d9..74ddf76`), and pushed with a normal `git push` (no
  force-push). The ambiguous `next_step` token `measured_guide_quality_baseline_real_public_fixture_harness` was corrected to
  `measured_guide_quality_baseline_existing_artifacts_harness` before committing. Final trunk status before branching Slice 149
  was clean; **no docker compose config was run**; the Slice 60 trace stash remains parked and untouched.
- **What this slice is:** a pure, deterministic, stdlib-only **baseline aggregator / diff harness** that scores a *real, locally
  generated* guide by **reusing existing wired artifacts** — it is **not** a new evaluator stack. It reads the existing
  exact-name artifact JSON from a caller-provided local job directory, extracts **closed scalar statuses/counts only**, compares
  them against a committed **closed golden spec**, and emits a closed aggregate baseline record (plus an optional trend diff). It
  reruns no checks, reads no PDFs/guides/`clean.md`/source/OCR/table/caption text, writes nothing to the repo, and calls no
  provider/model/cloud/local LLM. Advisory and non-blocking.
- **Reuse, do not rebuild (enforced):** math verification, guide-quality contract lint, the QA gate, source coverage, report v2,
  and the rubric are **not** reimplemented. New logic is limited to the thin aggregator/diff plus two deferred new metrics.
- **Existing wired artifacts reused (exact names):** `math_verification.json`, `guide_quality_contract_lint.json`,
  `guide_quality_qa_gate.json`, `guide_quality_report_v2.json`, `source_coverage_report.json`, and
  `guide_quality_rubric_score.json` (advisory/supporting only). **Required core:** contract lint + QA gate + math verification.
- **Metric families (all present):** `reasoning_leak_status` (**headline, first-class** — from contract lint primary, QA gate
  fallback; fail when leak count > 0), `numeric_math_status` (from `math_verification.json`; spec-relative numeric scoring
  deferred to `needs_future_metric` while golden `known_numbers` is empty), `guide_quality_qa_gate_status`,
  `source_coverage_status`, `structure_contract_status` (contract lint sections / report v2), `reference_relative_completeness_status`
  (`needs_future_metric` — artifacts expose no safe concept/section labels to match without parsing guide text),
  `figure_handling_status` (`needs_future_metric` — no safe figure-id-level signal), `artifact_existence_status`.
- **`reasoning_leak_status` is the headline metric** and a first-class regression guard (reasoning-leak was an original real
  failure mode); it is never buried under generic guide quality.
- **Privacy / fixture policy (held):** source/reference PDFs and generated guide outputs stay **local and gitignored**; the only
  committed artifact is the **golden spec** (closed facts/labels/expectations — not copied source text) plus, when run, **closed
  aggregate metrics**. No private paths/filenames/raw artifact JSON/source/guide/OCR/table/caption text is committed. The
  collector never returns or prints the artifact directory path.
- **Local operator baseline now run (closed summary only).** The harness gained a safe **local mode**
  (`validate_guide_quality_baseline_harness.py --golden-spec … --artifact-dir … --run-label …`) that reads only the exact-name
  wired artifact JSONs from a caller-provided **local gitignored** job dir and prints a **closed aggregate summary only** — never
  the dir path, never raw artifact JSON, never source/guide/OCR/table/caption text, snippets, formulas, filenames, or paths. It
  exits nonzero only on a harness error (unreadable golden spec / missing `--artifact-dir`), never because a metric is honestly
  `not_available` / `needs_future_metric` / `fail`. Synthetic self-test behavior is preserved when no `--artifact-dir` is passed.
  - `local_operator_baseline_run = closed_summary_only`
  - `baseline_status = failed` (worst-of across both runs; advisory/non-blocking — **not** a gate)
  - `baseline_run_count = 2` · `baseline_run_labels: app_run_1, app_run_2`
  - Source/reference material, generated guides, and the copied app job artifacts stay **local and gitignored** (under
    `local_operator_baselines/`, ignored via `.git/info/exclude`) — **none committed**.
  - **app_run_1 (closed metric statuses):** `reasoning_leak_status: fail` · `numeric_math_status: not_available` ·
    `guide_quality_qa_gate_status: warning` · `source_coverage_status: warning` · `structure_contract_status: pass` ·
    `reference_relative_completeness_status: needs_future_metric` · `figure_handling_status: needs_future_metric` ·
    `artifact_existence_status: pass`.
  - **app_run_2 (closed metric statuses):** `reasoning_leak_status: fail` · `numeric_math_status: not_available` ·
    `guide_quality_qa_gate_status: warning` · `source_coverage_status: not_observed` · `structure_contract_status: pass` ·
    `reference_relative_completeness_status: needs_future_metric` · `figure_handling_status: needs_future_metric` ·
    `artifact_existence_status: pass`.
  - **Honest gaps (not "covered"):** `reference_relative_completeness_status` and `figure_handling_status` both degrade to
    `needs_future_metric` on the real runs — `metric_family_present=true`, `metric_value_measured=false`,
    `gap_reason=existing_artifacts_do_not_expose_safe_labels_or_visual_counts`. `numeric_math_status=not_available` because the
    real `math_verification.json` summary exposes no closed `total` counter to drive the metric.
  - **known_numbers policy:** golden `known_numbers=[]` (no operator-confirmed closed numbers); `spec_relative_numeric_status =
    needs_operator_known_numbers`. The `numeric_spec_relative_scoring_needs_future_metric` warning is recorded on both runs.
  - `next_step = run_local_operator_baseline_or_style_audit_after_local_run` (the local baseline has now run, so Slice 150 is
    unblocked per `local_operator_baseline_run = closed_summary_only`).
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`,
  `?? pipeline/guide_quality_baseline.py`, `?? test_scripts/test_guide_quality_baseline.py`,
  `?? test_scripts/validate_guide_quality_baseline_harness.py`,
  `?? test_scripts/fixtures/guide_quality_baseline/nn_iris_local_golden_spec.json`,
  `?? docs/GUIDE_QUALITY_BASELINE_HARNESS.md`. **Slice 149 remains NOT committed.** No `local_operator_baselines/` file is
  tracked or committed.
- **Validation (all green):** `test_guide_quality_baseline.py` (130 passed / 0 failed — now includes local-mode tests on
  synthetic temp dirs only), `validate_guide_quality_baseline_harness.py` synthetic self-test (`baseline_harness_status=ok`,
  exit 0) plus two real local-mode runs (`app_run_1`, `app_run_2`: `baseline_harness_status=ok`, exit 0, closed summary only),
  `compileall api pipeline test_scripts` clean; existing producers unchanged and green (math verifier 74, contract lint 83, QA
  gate 177, report v2 100, rubric 63); quality-safety adapter/calibration/floor harnesses re-run green; `git diff --check` clean;
  no-leak sweep clean. Docker not required (no production/API/UI behavior changed); **no docker compose config run.**
- **Out of scope / unchanged:** no LLM judge, no `quality_judge.py`/`nn3.json`/`judge_response_nn3.json`/`quality.jsonl`, no
  prompt tuning, no repair, no rebuilding wired checks, no `api/server.py`/routes/frontend/Builder/Ask-Guide change, no
  generation/provider/render/export/OCR/table/visual change, no `judge_ready`/`repair_ready`/`artifact_write_ready`/
  `ui_display_ready` flip.
- **Next recommended slice:** **Slice 150 — Style/Preset Output Audit using the baseline** (run the baseline locally across
  style/generator presets and compare closed aggregate metrics; still advisory, still no committed private content).

---

## Slice 148 — **Judge Path Freeze / Calibration Decision Checkpoint (lean, docs-only)**, on `slice148-quality-safety-judge-path-freeze-checkpoint`. **Committed `74ddf76`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 147 was committed as `effc9d9`, fast-forward merged to trunk `chrome-renderer-v1`
  (`1f01231..effc9d9`), and pushed with a normal `git push` (no force-push). Final trunk status before branching Slice 148 was
  clean; **no docker compose config was run**; the Slice 60 trace stash remains parked and untouched.
- **Why this slice exists (stop/redirect, not more judge infrastructure):** the offline judge scaffold is now complete at
  **synthetic-only** (contract design, schema fixtures, synthetic core, calibration gate protocol + synthetic harness, advisory
  artifact design, pure/unwired artifact adapter). Continuing to writer / UI / job integration **before real calibration** would
  manufacture false confidence. This slice freezes the judge path and corrects the next-phase policy back to **real measured
  guide quality** on public/redistributable golden material — *not* another synthetic abstraction.
- **Scope (lean, docs-only):** edits exactly three live docs — `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`,
  `docs/DECISIONS.md`. **No** new checkpoint doc; **no** production code; **no** tests; **no** new pipeline module; **no** fixture
  / PDF / spec file; **no** API / frontend / generation-prompt / request-schema / render / export / OCR / table / visual / Ask
  Guide change; **no** artifact writer; **no** UI display; **no** judge execution; **no** provider/model/cloud/local-LLM call;
  **no** private calibration; **no** repair; **no** prompt tuning. No `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`,
  or `quality.jsonl` added.
- **Closed decision block:**
  - `judge_path_freeze_checkpoint: run`
  - `status: ok`
  - `decision_status: pause_judge_path`
  - `default_path: measured_guide_quality_baseline`
  - `calibration_status: synthetic_only`
  - `private_operator_judge_calibration_run: not_run`
  - `artifact_shape_ready: true`
  - `artifact_write_ready: false`
  - `ui_display_ready: false`
  - `judge_ready: false`
  - `repair_ready: false`
  - `next_step: measured_guide_quality_baseline_existing_artifacts_harness`
  - `warnings: [judge_path_paused_until_private_calibration, synthetic_only_baseline_not_accepted_for_product_quality]`
- **Privacy policy correction recorded (privacy ≠ synthetic-only):** private student/source material, private generated guides,
  private source/OCR/table/caption text, private paths/filenames, raw judge outputs, provider payloads, prompts/responses, and
  private runtime artifacts **remain forbidden in git**. Public/redistributable benchmark fixtures are a *different* category:
  golden source/reference PDFs and generated guide outputs still stay **local and gitignored by default** (do **not** commit
  source/reference PDFs for Slice 149); the committed repo artifact is the **golden spec** (closed facts/labels/expectations, not
  copied source text) plus **closed aggregate scores / trend snapshots**. If public/redistributable status of any fixture is not
  verified, **stop and report** rather than committing it.
- **Corrected Slice 149 mandate — Measured Guide Quality Baseline Harness (real local fixture + committed golden spec):**
  build a baseline aggregator/diff harness that scores a *real, locally generated* guide by **reusing existing wired artifacts**
  rather than rebuilding a parallel Quality Safety stack. It reads, from a real local golden job (operator keeps the fixture
  local/gitignored and confirms it is safe to use locally — e.g. NN/Iris material), the existing exact-name artifacts where
  present: `math_verification.json`, `guide_quality_contract_lint.json`, `guide_quality_qa_gate.json`,
  `guide_quality_report_v2.json`, `source_coverage_report.json`, and `guide_quality_rubric_score.json` (advisory/supporting
  only). It compares their closed summaries against a committed golden spec (`required_concepts`, `key_facts`, `known_numbers`,
  `must_not_claim`, `expected_figures_or_diagrams` as closed labels/counts, `expected_sections`/reference-relative subsection
  labels) and commits **closed aggregate metrics only**. Metric families: `reasoning_leak_status` (headline; from
  `guide_quality_contract_lint.json` / `guide_quality_qa_gate.json` — first-class because reasoning-leak was an original real
  failure mode), `numeric_math_status` (from `math_verification.json` + golden `known_numbers`), `source_coverage_status` (from
  `source_coverage_report.json`), `structure_contract_status` (from contract lint + report v2), `guide_quality_gate_status`
  (from QA gate), `reference_relative_completeness_status` (new thin metric vs golden spec), `figure_handling_status` (new thin
  metric vs closed expected figure/diagram labels/counts), `artifact_existence_status`. **Out of scope for 149:** LLM judge,
  `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, `quality.jsonl`, prompt tuning, repair, rebuilding math
  verification / contract lint / QA gate / source coverage, any new provider/model/cloud call beyond the normal generation the
  operator explicitly runs, and any synthetic-only baseline as the main deliverable. Missing data → record a closed
  `not_available` / `needs_future_metric` status; do not invent a new subsystem.
- **Provisional plan (hard plan 148–152 only):** 148 (this freeze/policy correction) · 149 (measured baseline aggregator over
  existing wired artifacts, real local fixture + committed golden spec) · 150 (style/preset output audit using the baseline) ·
  151 (first measured guide-quality improvement, one narrow change only, kept only if metrics improve) · 152 (source coverage /
  missing-material clarity). **Slice 153+ deliberately left unplanned** until 149–151 prove the measurement loop works.
- **Validation (docs-only):** `compileall api pipeline test_scripts` clean; offline judge artifact adapter synthetic harness,
  judge calibration gate harness, and deterministic floor final gate re-run green; `git diff --check` clean; no-leak sweep clean.
  Docker not required (docs-only; no API/UI/runtime path changed); **no docker compose config run.**
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/NEXT_CHAT_HANDOFF.md`, `M docs/DECISIONS.md`. **Slice 148 remains NOT
  committed.**
- **Next recommended slice:** **Slice 149 — Measured Guide Quality Baseline Harness (real local fixture + committed golden
  spec).** The judge path stays frozen/paused (`judge_ready=false`; `repair_ready=false`; `artifact_write_ready=false`;
  `ui_display_ready=false`; `calibration_status=synthetic_only`; `private_operator_judge_calibration_run=not_run`); resume judge
  work only after an explicit operator decision and a real private closed-record calibration pass. The deterministic Quality
  Safety floor stays the source of truth.

---

## Slice 147 — **Advisory Offline Judge Artifact Schema Adapter, Synthetic Only**, on `slice147-quality-safety-advisory-offline-judge-artifact-adapter`. **Committed `effc9d9`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 146 was committed as `1f01231`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `8ad39c7..1f01231`). Final trunk status before branching Slice 147 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope (pure/unwired adapter + synthetic tests):** add a pure, deterministic, **unwired** adapter that accepts a normalized
  offline judge report (Slice 142 schema / Slice 143 core shape) and returns a **write-ready synthetic artifact payload shape**
  for the proposed advisory artifact. This is **not** production artifact writing and **not** judge execution: **no** artifact
  file written, **no** wiring of judge reports into job artifacts, **no** UI display, **no** judge execution, **no** LLM judge,
  **no** provider/model/cloud/local-LLM call, **no** filesystem/`clean.md`/source/guide/reference read, **no** private
  calibration, **no** repair, **no** prompt tuning, **no** blocking gate, **no** numeric infrastructure unfreeze, **no**
  route/frontend/request-schema/render/export/OCR/table/visual/Ask Guide change. No `api/server.py`,
  `quality_safety_job_artifact.py`, or `run_markdown_job.py` change; no `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl` added.
- **New module (`pipeline/quality_safety_offline_judge_artifact_adapter.py`):** pure adapter over the Slice 142 normalizer.
  Public surface: `build_empty_offline_judge_artifact_adapter_result`,
  `adapt_offline_judge_report_to_artifact_payload`, `validate_offline_judge_artifact_payload`,
  `build_synthetic_offline_judge_artifact_case`, `run_synthetic_offline_judge_artifact_case`,
  `serialize_offline_judge_artifact_payload`. The result carries `kind=quality_safety_offline_judge_artifact_adapter_result`,
  `artifact_name=quality_safety_offline_judge_report.json`, `artifact_kind=quality_safety_offline_judge_report`, the sanitized
  normalized report under `artifact_payload`, a count-only `summary`
  (`axis_count`/`blocker_count`/`warning_count`/`forbidden_field_count`), closed `blockers`/`warnings`, and closed readiness
  flags. The payload is rebuilt strictly through the Slice 142 normalizer, so forbidden content cannot survive by construction;
  imports are restricted to the schema + core + stdlib `json`/`typing`.
- **Readiness (closed vocabulary):** `advisory_judge_artifact_adapter_status=ok`; `artifact_shape_ready=true` (for valid,
  genuine normalized reports); `artifact_write_ready=false`; `ui_display_ready=false`; `judge_ready=false`; `repair_ready=false`;
  `calibration_status=synthetic_only`; `private_operator_judge_calibration_run=not_run`.
- **Synthetic cases covered:** `clean_synthetic_judge_case` (shape_ready, status ok), `weak_synthetic_judge_case` (shape_ready,
  warning), `failed_synthetic_judge_case` (shape_ready, status not ok, `axis_failed` blocker), `leak_canary_synthetic_judge_case`
  (forbidden canaries stripped, `forbidden_field_count>0`, `forbidden_field_stripped` warning, status not ok),
  `deterministic_floor_red_synthetic_judge_case` (`deterministic_floor_red` blocker, status not ok, never write/display-ready),
  `malformed_report_case` (wrong kind → shape_ready false, status failed). Calibration interactions: `synthetic_only` does not
  enable write/display; `operator_validated` (in report or record) is never honored and is warned; private-shaped/non-closed
  calibration records are stripped + warned. Deterministic floor red can never become ok/write-ready/display-ready.
- **Validation (all green):** adapter test (582 passed / 0 failed), adapter synthetic harness (ok, exit 0), calibration gate
  harness (synthetic ok, exit 0), core test (769), core synthetic harness (ok), schema test (667), Slice 142 harness (ok), floor
  final gate (34), operator export harness (35), operator export validator (422), candidate adapter (177), safe extractor (207),
  job artifact (753), recompute verifier (99), real-disaster e2e (100), unified QA (73); `compileall api pipeline test_scripts`
  clean; `git diff --check` clean. Docker not run (pure synthetic/test-only); no docker compose config run.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_ADVISORY_OFFLINE_JUDGE_ARTIFACT_DESIGN.md`, `M docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_SURFACE_FREEZE.md`,
  `?? pipeline/quality_safety_offline_judge_artifact_adapter.py`,
  `?? test_scripts/test_quality_safety_offline_judge_artifact_adapter.py`,
  `?? test_scripts/validate_quality_safety_offline_judge_artifact_adapter_synthetic.py`. **Slice 147 remains NOT committed.**
- **Next recommended slice:** **advisory offline judge artifact writer design** (a separately-designed slice that decides where a
  job-local artifact may be written, still advisory/non-blocking and still gated on calibration before any UI display), *or*
  **stop for a private operator calibration pass** before any artifact wiring. Judge baseline stays blocked (`judge_ready=false`;
  `repair_ready=false`); the deterministic floor stays the source of truth.

---

## Slice 146 — **Advisory Offline Judge Artifact Design**, on `slice146-quality-safety-advisory-offline-judge-artifact-design`. **Committed `1f01231`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 145 was committed as `8ad39c7`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `91e6c7d..8ad39c7`). Final trunk status before branching Slice 146 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope (docs/design-only):** design how a *future* advisory offline judge report artifact may be stored and surfaced after
  calibration, without making it blocking or trusted prematurely. **No** production artifact writing, **no** wiring of judge
  reports into job artifacts, **no** UI display, **no** judge execution, **no** LLM judge, **no** provider/model/cloud/local-LLM
  calls, **no** `quality_judge.py`, **no** `nn3.json`, **no** `judge_response_nn3.json`, **no** `quality.jsonl`, **no** runtime
  judge outputs, **no** repair, **no** prompt tuning, **no** blocking gate, **no** numeric infrastructure unfreeze, **no**
  route/frontend/request-schema/render/export/OCR/table/visual/Ask Guide change. No production code changed in this slice.
- **New doc (`docs/QUALITY_SAFETY_ADVISORY_OFFLINE_JUDGE_ARTIFACT_DESIGN.md`):** purpose, closed-vocabulary preconditions,
  proposed artifact, artifact boundary, integration boundary (allowed/forbidden), storage rules (allowed/forbidden fields),
  display policy, conservative readiness, and the proposed next slice.
- **Proposed artifact name:** `quality_safety_offline_judge_report.json` (kind `quality_safety_offline_judge_report`; matches the
  Slice 142 schema — no new artifact name, no new schema kind, no new field, no field relaxed).
- **Artifact boundary:** `advisory=true`, `non_blocking`, `not_user_score`, `not_repair_input`, `not_shippability_source`,
  `not_deterministic_floor_override`, `hidden_or_internal_until_calibrated`.
- **Integration boundary:** *allowed (future):* optional job-local artifact after the offline judge core/report is produced;
  read-only UI display only after calibration policy allows; docs/operator validation may record closed outcomes only.
  *Forbidden:* no blocking gate, no shippable override, no recompute override, no leak override, no repair trigger, no prompt
  tuning trigger, no raw rationale display from private jobs, no raw model prompt/response storage, no provider payload storage,
  no generic artifact export of private judge raw outputs.
- **Storage rules:** *allowed* — Slice 142 schema fields only, closed axis statuses, confidence/score_band tokens, count-only
  summaries, closed blockers/warnings, `calibration_status`, `privacy_status`, `deterministic_floor_status`. *Forbidden* — source/
  guide/OCR/page/table/caption text, `formulas_as_text`, evidence quotes, filenames, basenames, paths, URLs, screenshots, raw
  runtime artifacts, raw artifact JSON from private jobs, provider payloads, model prompts/responses, private/free-text
  rationales, `chain_of_thought`, `quality_judge.py` dumps, `nn3.json`, `judge_response_nn3.json`, `quality.jsonl`.
- **Display policy:** future UI display allowed only after a later slice decides `calibration_status` is sufficient,
  `privacy_status` is ok, the deterministic floor relationship is enforced, and no raw/private rationale fields exist. Until then:
  no UI display, no user-facing score, no grade-like overall score, no repair suggestions.
- **Readiness (closed vocabulary):** `advisory_judge_artifact_design_status=ready`; `artifact_write_ready=false`;
  `ui_display_ready=false`; `judge_ready=false`; `repair_ready=false`;
  `next_step=advisory_offline_judge_artifact_schema_adapter_or_stop_for_private_calibration`.
- **Validation (all green):** calibration gate harness (synthetic ok, exit 0), core test (769), core synthetic harness (ok),
  schema test (667), Slice 142 harness (ok), floor final gate (34), operator export harness (35), operator export validator
  (422), candidate adapter (177), safe extractor (207), job artifact (753), recompute verifier (99), real-disaster e2e (100),
  unified QA (73); `compileall api pipeline test_scripts` clean; `git diff --check` clean. Docker not run (docs/design-only); no
  docker compose config run.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`, `M docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_SURFACE_FREEZE.md`, `?? docs/QUALITY_SAFETY_ADVISORY_OFFLINE_JUDGE_ARTIFACT_DESIGN.md`.
  **Slice 146 remains NOT committed.**
- **Next recommended slice:** **Slice 147 — Advisory Offline Judge Artifact Schema Adapter, Synthetic Only** (pure/unwired
  adapter that accepts normalized offline judge reports and verifies write-ready shape synthetically; no production writing, no
  UI, no private input, no `judge_ready=true`), *or* **stop for a private operator calibration pass** before any artifact wiring.
  Judge baseline stays blocked (`judge_ready=false`; `repair_ready=false`).

---

## Slice 145 — **Private Operator Judge Calibration Pass**, on `slice145-quality-safety-private-operator-judge-calibration-pass`. **Committed `8ad39c7`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 144 was committed as `91e6c7d`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `0dedf99..91e6c7d`). Final trunk status before branching Slice 145 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope (test/docs-only):** exercise the Slice 144 calibration gate / golden protocol via a closed-record **calibration gate
  harness**, and record the private/operator calibration pass status using **closed-vocabulary committed records only**. **No**
  private material committed, **no** judge execution on private material, **no** LLM judge, **no** provider/model/cloud/local-LLM
  calls, **no** `quality_judge.py`, **no** `nn3.json`, **no** `judge_response_nn3.json`, **no** `quality.jsonl`, **no** runtime
  judge outputs, **no** repair, **no** prompt tuning, **no** blocking gate, **no** production wiring, **no** UI, **no**
  route/frontend/request-schema/render/export/OCR/table/visual/Ask Guide change, **no** numeric infrastructure unfreeze. No
  production code changed in this slice.
- **New harness (`test_scripts/validate_quality_safety_judge_calibration_gate.py`):** validates closed-vocabulary calibration
  records against the Slice 144 protocol. Default **synthetic self-test** runs the five golden cases (`clean_real_case`,
  `single_confident_wrong_numeric_case`, `legacy_confused_wrong_case`, `leak_canary_case`, `deterministic_floor_red_case`) by
  exercising the pure Slice 143 offline judge core over **synthetic** observations only (closed records, not private material).
  Optional **local closed-record mode** (`--input <path>`) reads exactly one closed calibration-record JSON, never prints the
  path or raw values, never writes files, and degrades read/parse failures to closed tokens. The harness never reads
  guide/source/reference documents, never reads raw judge reports, never calls providers/models/cloud/local LLMs, and prints a
  closed-vocabulary summary only.
- **Synthetic calibration harness result:** `golden_case_count=5`, `passed_case_count=5`, `failed_case_count=0`,
  `input_kind=synthetic_only`, `protocol_status=ok`, `offline_judge_core_status=ok`, `schema_compatibility_status=ok`,
  `leak_safety_status=ok`, `deterministic_floor_status=ready_for_cleanup_freeze`, `private_operator_run=not_run`,
  `no_raw_private_material=true`, `calibration_status=synthetic_only`, `judge_ready=false`, `repair_ready=false`,
  `next_step=advisory_judge_artifact_design_or_stop_for_private_calibration`.
- **Private/operator pass decision:** `private_operator_judge_calibration_run=not_run`. No private/local operator closed-record
  run was performed in this slice. Local closed-record mode is **implemented** but **not run as committed data**; no operator
  records were supplied. The synthetic self-test is the committed evidence.
- **Calibration decision:** `calibration_status=synthetic_only`; `judge_ready=false`; `repair_ready=false`;
  `next_step=advisory_judge_artifact_design_or_stop_for_private_calibration`. `calibration_status` stays `synthetic_only` because
  no operator supplied closed records for the required golden cases; `judge_ready` stays false (no later explicit readiness gate
  authorized it); `repair_ready` stays false (out of scope).
- **Validation (all green):** calibration gate harness (synthetic ok, exit 0; local-mode valid/leak-shaped/read-fail/parse-fail
  exercised), core test (769), core synthetic harness (ok), schema test (667), Slice 142 harness (core compatibility ok), gate
  (34), operator export harness (35), operator export validator (422), adapter (177), safe extractor (207), job artifact (753),
  recompute verifier (99), real-disaster e2e (100), unified QA (73); `compileall` clean; `git diff --check` clean. Docker not run
  (test/docs-only); no docker compose config run.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`, `M docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_SURFACE_FREEZE.md`, `?? test_scripts/validate_quality_safety_judge_calibration_gate.py`.
  **Slice 145 remains NOT committed.**
- **Next recommended slice:** **Slice 146 — Advisory Offline Judge Artifact Design** (closed-vocabulary advisory artifact /
  sidecar design, still non-blocking, still no private input and no provider/model/cloud/local-LLM calls), *or* stop here for a
  separately-arranged **private operator calibration pass** if/when the operator supplies closed records. Judge baseline stays
  blocked (`judge_ready=false`; `repair_ready=false`).

---

## Slice 144 — **Judge Calibration Gate / Golden Protocol**, on `slice144-quality-safety-judge-calibration-gate-protocol`. **Committed `91e6c7d`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 143 was committed as `0dedf99`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `800b187..0dedf99`). Final trunk status before branching Slice 144 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope (docs/protocol-only):** define the closed-vocabulary **calibration gate / golden protocol** that must pass before any
  offline judge report can be trusted as an advisory quality signal. **No** private calibration, **no** judge execution, **no**
  LLM judge, **no** provider/model/cloud/local-LLM calls, **no** `quality_judge.py`, **no** `nn3.json`, **no**
  `judge_response_nn3.json`, **no** `quality.jsonl`, **no** runtime judge outputs, **no** repair, **no** prompt tuning, **no**
  blocking gate, **no** production wiring, **no** UI, **no** route/frontend/request-schema/render/export/OCR/table/visual/Ask
  Guide change, **no** numeric infrastructure unfreeze. No production code changed in this slice.
- **New doc (`docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`):** purpose, current preconditions (closed vocabulary),
  boundary (`protocol_only`/`advisory_only`/`non_blocking`/`no_repair`/`no_prompt_tuning`/`no_provider_calls`/`no_llm_calls`/
  `no_judge_calls`/`no_runtime_outputs_committed`/`no_private_material_committed`), the **golden case set** (five closed cases:
  `clean_real_case`, `single_confident_wrong_numeric_case`, `legacy_confused_wrong_case`, `leak_canary_case`,
  `deterministic_floor_red_case`), the closed-vocabulary **calibration record shape** (`validation_id`, `input_kind`, counts,
  `*_committed=false` flags, `*_calls=false`, statuses, `judge_ready=false`, `repair_ready=false`, closed `warnings`), the
  conservative **pass/fail rules**, the **offline-judge-core** and **deterministic-floor** relationships, and the proposed next
  slice.
- **Golden case summary:** `clean_real_case` (floor pass, judge ok|warning, no blockers); `single_confident_wrong_numeric_case`
  (floor failed_blocking, judge failed|partial, recompute/correctness blocker); `legacy_confused_wrong_case` (floor partial,
  judge warning|partial|failed); `leak_canary_case` (floor failed_blocking|warning, judge failed, leakage/privacy);
  `deterministic_floor_red_case` (floor blocked, judge cannot override). No real text/snippets/filenames/paths committed.
- **Pass/fail rules:** calibration may become `operator_validated` only in a later slice when all required golden cases have
  closed operator records, the floor passes where expected, the wrong-numeric case is detected as blocking, the leak canary is
  detected as failing, the floor-red case cannot be overridden, no raw private/runtime/free-text material is committed, schema
  compatibility is `ok`, and core status is `ok`. The judge may become ready only in a later gate after
  `calibration_status=operator_validated` and an explicit decision; repair stays false regardless.
- **Deterministic-floor relationship:** the floor remains the hard gate / source of truth; the judge cannot override
  recompute/leak/privacy blockers, cannot mark anything shippable while the floor is red, cannot fabricate facts from structural
  coverage, and remains advisory even after calibration unless a later explicit policy changes it. No surface unfreeze.
- **Decision record:** `judge_calibration_gate_protocol_status=ready`; `calibration_status=synthetic_only`;
  `judge_contract_ready=true`; `judge_ready=false`; `repair_ready=false`; `next_step=private_operator_judge_calibration_pass`.
- **Validation (all green):** core test (769), core synthetic harness (ok), schema test (667), Slice 142 harness (core
  compatibility ok), gate (34), operator export harness (35), operator export validator (422), adapter (177), safe extractor
  (207), job artifact (753), recompute verifier (99), real-disaster e2e (100), unified QA (73); `compileall` clean;
  `git diff --check` clean. Docker not run (docs/protocol-only); no docker compose config run.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`, `M docs/QUALITY_SAFETY_SURFACE_FREEZE.md`,
  `M docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `?? docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`.
  **Slice 144 remains NOT committed.**
- **Next recommended slice:** **Slice 145 — Private Operator Judge Calibration Pass** (conservative; the *Synthetic Calibration
  Gate Harness* is the safe fallback if no private run is desired). Judge baseline stays blocked (`judge_ready=false`;
  `repair_ready=false`).

---

## Slice 143 — **Offline Judge Core v1, Synthetic Only**, on `slice143-quality-safety-offline-judge-core-synthetic-v1`. **Committed `0dedf99`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 142 was committed as `800b187`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `b193d43..800b187`). Final trunk status before branching Slice 143 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope:** a pure, unwired **offline judge core v1** that converts caller-supplied **synthetic closed observations** into the
  Slice 142 offline judge report shape using **deterministic rules only**. It is **not** an LLM judge, **not** production wiring,
  and does **not** inspect real guide/source/reference text. **No judge calls, no provider/model/cloud/local-LLM calls, no
  `quality_judge.py`, no `nn3.json`, no `judge_response_nn3.json`, no `quality.jsonl`, no repair, no prompt tuning, no blocking
  gate, no UI, no route/frontend/request-schema/render/export/OCR/table/visual/Ask Guide change, no numeric infrastructure
  unfreeze.** `quality_safety_job_artifact.py`, `run_markdown_job.py`, `api/server.py` unchanged.
- **New pure module (`pipeline/quality_safety_offline_judge_core.py`):** `build_offline_judge_report_from_observations`,
  `normalize_offline_judge_observations`, `build_synthetic_offline_judge_observations`, `run_synthetic_offline_judge_case`,
  `build_empty_offline_judge_core_result`. Imports **only** the Slice 142 schema module + stdlib `typing`; reads/writes no files;
  calls no provider/model/cloud/local LLM. Every report is passed through the Slice 142 schema normalizer before return, so it is
  sanitized by construction and `judge_ready` / `repair_ready` always normalize to `False`.
- **Deterministic axis rules (closed observations → axis_results):** `fail_count>0 → fail/failed`; else `warning_count>0 →
  warning` (`weak` band when confidence is low/unknown, else `acceptable`); else `pass_count>0 → pass` (`strong` when confidence
  high, else `acceptable`); else `not_observed/unknown`. Summary carries `axis_count`, `pass_count`, `warning_count`,
  `fail_count`, `not_observed_count`, `blocker_count`. The core **cannot** override deterministic recompute/leak/floor blockers:
  a floor-red `deterministic_floor_payload` yields a `deterministic_floor_red` blocker and a non-`ok` status even when all axes
  pass; a `privacy_status=failed` yields `privacy_failed`; a failing axis yields `axis_failed`.
- **Synthetic cases (synthetic ids + synthetic canaries only):** `clean_synthetic_judge_case` (status `ok`, no blockers),
  `weak_synthetic_judge_case` (status `warning`, weak/acceptable bands), `failed_synthetic_judge_case` (status `failed`,
  `axis_failed`), `leak_canary_synthetic_judge_case` (forbidden canaries stripped, `privacy_status=failed`, status `failed`),
  `deterministic_floor_red_synthetic_judge_case` (`deterministic_floor_status=blocked`, `deterministic_floor_red`, status
  `failed`). All normalize with `judge_ready=false` / `repair_ready=false`.
- **`offline_judge_core_status=ok`** (synthetic harness). `calibration_status=synthetic_only`; `judge_ready=false`;
  `repair_ready=false`.
- **Tests/harnesses added:** `test_scripts/test_quality_safety_offline_judge_core.py` (769 checks: empty/malformed degrade,
  clean report, all eight axes, unknown axes dropped, deterministic axis rules, summary counts, closed blocker/warning tokens,
  forbidden-field stripping, no-canary survival, floor-red cannot be overridden, `operator_validated` downgraded, deterministic
  serialization, caller input not mutated, import/purity guard) and
  `test_scripts/validate_quality_safety_offline_judge_core_synthetic.py` (closed-vocabulary summary; writes no files; exits
  nonzero on failure). The Slice 142 harness gained an opportunistic `offline_judge_core_compatibility_status` (no production
  dependency).
- **Synthetic core harness result:** `offline_judge_core_status=ok`, `synthetic_case_status=ok`, `schema_compatibility_status=ok`,
  `leak_safety_status=ok`, `deterministic_floor_relationship_status=ok`, `calibration_status=synthetic_only`,
  `judge_ready=false`, `repair_ready=false`, `next_step=judge_calibration_gate_golden_protocol`.
- **Future judge artifact name (proposed only):** `quality_safety_offline_judge_report.json` (nothing produces it here).
- **Validation (all green):** core test (769), core synthetic harness (ok), schema test (667), Slice 142 harness
  (core compatibility `ok`), gate (34), operator export harness (35), operator export validator (422), adapter (177), safe
  extractor (207), job artifact (753), recompute verifier (99), real-disaster e2e (100), unified QA (73); `compileall` clean;
  `git diff --check` clean. Docker not run (pure synthetic/test only); no docker compose config run.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`, `M docs/QUALITY_SAFETY_SURFACE_FREEZE.md`,
  `M docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `M test_scripts/validate_quality_safety_offline_judge_synthetic_harness.py`,
  `?? pipeline/quality_safety_offline_judge_core.py`, `?? test_scripts/test_quality_safety_offline_judge_core.py`,
  `?? test_scripts/validate_quality_safety_offline_judge_core_synthetic.py`. **Slice 143 remains NOT committed.**
- **Decision record:** `offline_judge_core_status=ok`; `calibration_status=synthetic_only`; `judge_contract_ready=true`;
  `judge_ready=false`; `repair_ready=false`; `next_step=judge_calibration_gate_golden_protocol`.
- **Next recommended slice:** **Slice 144 — Judge Calibration Gate / Golden Protocol.** Judge baseline stays blocked
  (`judge_ready=false`; `repair_ready=false`); the calibration gate defines the golden-case protocol that must pass before
  `judge_ready` could ever be considered — still no private input and no provider/model/cloud/local-LLM calls.

---

## Slice 142 — **Offline Judge Schema Fixtures and Synthetic Harness**, on `slice142-quality-safety-offline-judge-schema-fixtures`. **Committed `800b187`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 141 was committed as `b193d43`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `62b7b82..b193d43`). Final trunk status before branching Slice 142 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope:** pure schema + synthetic fixtures + a synthetic harness. This slice proves the **future** offline judge report shape
  can be **normalized / sanitized / serialized / validated** using **synthetic data only**. It is **not** judge execution. **No
  judge core, no judge calls, no provider/model/cloud/local-LLM calls, no `quality_judge.py`, no `nn3.json`, no
  `judge_response_nn3.json`, no `quality.jsonl`, no repair, no prompt tuning, no blocking gate, no production wiring, no UI, no
  route/frontend/request-schema/render/export/OCR/table/visual/Ask Guide change, no numeric infrastructure unfreeze.**
  `quality_safety_job_artifact.py`, `run_markdown_job.py`, `api/server.py` unchanged.
- **New pure module (`pipeline/quality_safety_offline_judge_schema.py`):** `build_empty_offline_judge_report`,
  `normalize_offline_judge_report`, `validate_offline_judge_report`, `build_synthetic_offline_judge_fixture`,
  `serialize_offline_judge_report`. Stdlib-only (`json`, `re`, `typing`); reads/writes no files; calls no
  provider/model/cloud/local LLM. The normalizer rebuilds output strictly from a closed whitelist, so no raw guide/source/
  reference text, free-text rationale, filename, path, URL, provider payload, model prompt/response, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl` content can survive into output by construction.
- **Output report shape (closed/sanitized):** `version`, `kind=quality_safety_offline_judge_report`, `advisory=true`,
  `status` (`ok|warning|skipped|partial|failed`), `judge_model_kind`, `input_scope`, `summary` (count-only),
  `axis_results` (eight allowed axes; per-axis closed `status`/`confidence`/`score_band`/`counts`/`warnings`), `blockers`
  (closed tokens), `warnings` (closed tokens), `calibration_status`, `privacy_status`, `deterministic_floor_status`,
  `judge_ready=false`, `repair_ready=false`. No free-text rationales.
- **Synthetic fixtures (synthetic ids + synthetic canaries only):** `clean_synthetic_judge_case` (mostly pass,
  `synthetic_only`), `weak_synthetic_judge_case` (warnings/weak bands), `failed_synthetic_judge_case` (fail axis + blocker),
  `leak_canary_synthetic_judge_case` (canaries stripped, privacy not ok), `deterministic_floor_red_synthetic_judge_case`
  (`deterministic_floor_status=blocked`, blocker present). All normalize with `judge_ready=false`/`repair_ready=false`.
- **Synthetic harness (`test_scripts/validate_quality_safety_offline_judge_synthetic_harness.py`):** runs all fixtures,
  normalizes/validates, checks deterministic serialization, no-canary survival, `judge_ready`/`repair_ready` always false, and
  that a floor-red case can never become shippable/ready; prints a closed-vocabulary summary only; writes no files; exits
  nonzero on failure. Result: `offline_judge_schema_status=ok`, `synthetic_fixture_status=ok`, `leak_safety_status=ok`,
  `deterministic_floor_relationship_status=ok`, `calibration_status=synthetic_only`, `judge_ready=false`, `repair_ready=false`.
- **Future judge artifact name (proposed only):** `quality_safety_offline_judge_report.json` (nothing produces it here).
- **Validation (all green):** schema test (667), synthetic harness (ok), gate (34), operator export harness (35), operator
  export validator (422), adapter (177), safe extractor (207), job artifact (753), recompute verifier (99), real-disaster e2e
  (100), unified QA (73); `compileall` clean; `git diff --check` clean. Docker not run (pure schema/test only); no docker
  compose config run.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`, `M docs/QUALITY_SAFETY_SURFACE_FREEZE.md`,
  `M docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `?? pipeline/quality_safety_offline_judge_schema.py`,
  `?? test_scripts/test_quality_safety_offline_judge_schema.py`,
  `?? test_scripts/validate_quality_safety_offline_judge_synthetic_harness.py`. **Slice 142 remains NOT committed.**
- **Decision record:** `offline_judge_schema_status=ok`; `calibration_status=synthetic_only`; `judge_contract_ready=true`;
  `judge_ready=false`; `repair_ready=false`; `next_step=offline_judge_core_v1_synthetic_only`.
- **Next recommended slice:** **Slice 143 — Offline Judge Core v1, Synthetic Only.** Judge baseline stays blocked
  (`judge_ready=false`; `repair_ready=false`); the judge core would be wired to synthetic fixtures only — no private input, no
  provider/model/cloud/local-LLM calls.

---

## Slice 141 — **Offline Judge Contract Design**, on `slice141-quality-safety-offline-judge-contract-design`. **Committed `b193d43`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 140 was committed as `62b7b82`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `c421465..62b7b82`). Final trunk status before branching Slice 141 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope:** docs / design only; **no production code change.** Now that the deterministic (non-judge) Quality Safety surface is
  frozen (Slice 140), this slice **designs the offline judge contract** — it does **not** implement a judge. **No judge core, no
  judge calls, no provider/model/cloud/local-LLM calls, no `quality_judge.py`, no `nn3.json`, no `judge_response_nn3.json`, no
  `quality.jsonl`, no repair, no prompt tuning, no blocking gate, no route/frontend/request-schema/render/export/OCR/table/visual/
  Ask Guide change, no numeric infrastructure unfreeze.** `quality_safety_job_artifact.py`, `run_markdown_job.py`,
  `api/server.py` unchanged.
- **New doc (`docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`)** defines, closed-vocabulary only: preconditions; boundary
  (`offline_only`, `advisory_only`, `non_blocking_initially`, `no_repair`, `no_prompt_tuning`, `no_provider_calls_in_contract_slice`,
  `no_runtime_outputs_committed`, `no_private_material_committed`); allowed future runtime-only inputs (sanitized/closed-vocabulary
  committed outputs only); forbidden committed content; the **proposed** future artifact name
  `quality_safety_offline_judge_report.json` (proposed, not produced); the closed/sanitized output shape (no free-text rationale)
  with eight axes (`correctness`, `completeness`, `source_grounding`, `structure_and_study_value`, `math_numeric_safety`,
  `leakage_privacy_safety`, `citation_traceability`, `exam_readiness`); calibration requirements; the relationship to the
  deterministic floor (judge cannot override recompute/leak blockers or fabricate facts from coverage); the next five judge-path
  slices; and the decision record.
- **Future judge artifact name (proposed only):** `quality_safety_offline_judge_report.json` (`advisory=true`, non-blocking
  initially, not a final user score until calibrated, not used for repair).
- **Decision record:** `offline_judge_contract_status=ready`; `numeric_infrastructure_frozen=true`;
  `quality_safety_surface_frozen=true`; `judge_contract_ready=true`; `judge_ready=false`; `repair_ready=false`;
  `next_step=offline_judge_schema_fixtures_and_synthetic_harness`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_SURFACE_FREEZE.md`, `M docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `?? docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`. **Slice 141 remains NOT committed.**
- **Next recommended slice:** **Slice 142 — Offline Judge Schema Fixtures and Synthetic Harness.** `judge_ready=false`;
  `repair_ready=false`; the judge contract is designed only — implementation begins, synthetic-only, in a later separately
  designed slice.

---

## Slice 140 — **Quality Safety Surface Cleanup / Freeze**, on `slice140-quality-safety-surface-cleanup-freeze`. **Committed `62b7b82`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 139 was committed as `c421465`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `cd7ac45..c421465`). Final trunk status before branching Slice 140 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope:** docs / test-surface cleanup only; **no production code change.** This slice freezes the deterministic (non-judge)
  Quality Safety surface so it is easy to reason about before Slice 141 begins **Offline Judge Contract Design**. It adds a single
  consolidated freeze summary `docs/QUALITY_SAFETY_SURFACE_FREEZE.md` and aligns the stale handoff/current-task pointers. **No new
  Quality Safety feature, no new numeric schema/bridge layer, no judge scoring, no repair, no prompt tuning, no production wiring,
  no route/frontend change, no provider/model/cloud, no OCR/table/source/`clean.md` parsing, no real/private sidecar.**
  `quality_safety_job_artifact.py`, `run_markdown_job.py`, `api/server.py` unchanged.
- **Freeze summary (`docs/QUALITY_SAFETY_SURFACE_FREEZE.md`)** records, closed-vocabulary only: frozen artifact names
  (`quality_safety_unified_qa.json`, `quality_safety_numeric_extraction_records.json`,
  `quality_safety_safe_numeric_candidates.json`, `quality_safety_structured_numeric_candidates.json`); frozen field families
  (`extraction_coverage_*`, `numeric_extraction_*`, `safe_numeric_extractor_*`, `structured_numeric_candidate_adapter_*`,
  `operator_structured_numeric_export_validation`, `deterministic_floor_final_gate`); the nine frozen validation harnesses; the
  frozen non-goals; the known limitations; and the next allowed phase (`offline_judge_contract_design`).
- **Stale-doc cleanup:** the live `CURRENT_TASK.md` / `NEXT_CHAT_HANDOFF.md` "current position" pointers now reflect Slice 139 as
  trunk commit `c421465` and Slice 140 as the live uncommitted slice; archived historical slice records are left as-is.
- **Known limitations (unchanged, re-stated):** operator waiver is **synthetic-only**;
  `production_numeric_extractor_present` remains the sidecar / structured-sidecar / operator-approved path only;
  `judge_ready=false`; `repair_ready=false`; `judge_contract_ready=true` means only that contract **design** may begin.
- **Companion validation (all green):** gate (34), operator export harness (35), operator export validator (422), structured
  candidate adapter (177), safe numeric extractor (207), job artifact (753), recompute verifier (99), real-disaster e2e (100),
  unified QA (73); `compileall` clean; `git diff --check` clean. Docker not run (docs/test-surface only); no docker compose config run.
- **Decision record:** `deterministic_safety_floor_status=ready_for_cleanup_freeze`; `numeric_infrastructure_frozen=true`;
  `quality_safety_surface_frozen=true`; `judge_contract_ready=true`; `judge_ready=false`; `repair_ready=false`;
  `next_step=offline_judge_contract_design`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `M docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`,
  `M docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`, `?? docs/QUALITY_SAFETY_SURFACE_FREEZE.md`.
  **Slice 140 remains NOT committed.**
- **Next recommended slice:** **Slice 141 — Offline Judge Contract Design.** `judge_ready=false`; `repair_ready=false`; the offline
  judge **contract** is designed (not implemented) now that the deterministic floor is frozen.

---

## Slice 139 — **Deterministic Safety Floor Final Gate**, on `slice139-quality-safety-deterministic-floor-final-gate`. **Committed `c421465`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 138 was committed as `cd7ac45`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `763fb4a..cd7ac45`). Final trunk status before branching Slice 139 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope:** test-harness + docs only; **no production code change.** New harness
  `test_scripts/validate_quality_safety_deterministic_floor_final_gate.py` and new design doc
  `docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md`. The gate aggregates the deterministic components built in Slices
  118–138 (advisory `quality_safety_unified_qa.json` artifact, leak/no-leak rules, recompute verifier, fact-sheet/numeric
  extraction path, structural extraction coverage, safe numeric extractor, structured numeric candidate adapter, operator
  structured export validator, operator export harness/synthetic-only waiver, real-disaster synthetic E2E) and decides
  readiness. **No new numeric schema/bridge layer, no production wiring, no route/frontend change, no judge, no repair, no
  blocking gate, no provider/model/cloud, no OCR/table/source/`clean.md` parsing, no real/private sidecar, no private input
  mode.** `quality_safety_job_artifact.py`, `run_markdown_job.py`, `api/server.py` unchanged.
- **Gate harness behavior:** synthetic-only; no private input mode; reads no input files; writes no output files; prints a
  closed-vocabulary summary only; exits non-zero if any deterministic prerequisite fails. It imports/drives the existing pure
  components and the two existing Quality Safety harnesses.
- **Final gate result (`34 passed, 0 failed`):**
  - `deterministic_safety_floor_status=ready_for_cleanup_freeze`
  - `artifact_contract_status=ok`, `leak_safety_status=ok`, `recompute_status=ok`, `numeric_path_status=ok`,
    `structural_coverage_status=ok`, `operator_export_harness_status=ok`, `real_disaster_synthetic_status=ok`,
    `ui_display_status=already_covered_by_existing_verify`
  - real-disaster cases: `clean_real_case=passed`, `single_confident_wrong_numeric_case=failed_blocking`,
    `legacy_confused_wrong_case=partial`
  - `operator_numeric_export_waiver=approved_for_safety_floor_finalization_synthetic_only`; `numeric_infrastructure_frozen=true`
  - `judge_contract_ready=true` (deterministic floor is ready; this only unblocks *designing* the judge contract — no judge
    exists), `judge_ready=false`, `repair_ready=false`
- **Companion validation (all green):** gate (34), operator export harness (35), operator export validator (422), structured
  candidate adapter (177), safe numeric extractor (207), job artifact (753), recompute verifier (99), real-disaster e2e (100),
  unified QA (73); `compileall` clean; `git diff --check` clean. Docker not run (test/docs only); no docker compose config run.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md`,
  `M docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `?? docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md`,
  `?? test_scripts/validate_quality_safety_deterministic_floor_final_gate.py`. **Slice 139 remains NOT committed.**
- **Next recommended slice:** **Slice 140 — Quality Safety Surface Cleanup / Freeze.** `judge_ready=false`; `repair_ready=false`;
  the offline judge contract is designed only after cleanup/freeze.

---

## Slice 138 — **Operator Structured Numeric Export Validation Harness / Waiver Decision**, on `slice138-quality-safety-operator-structured-numeric-export-validation-harness`. **Committed `cd7ac45`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 137 was committed as `763fb4a`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push; `eb13ada..763fb4a`). Final trunk status before branching Slice 138 was clean; no docker
  compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope:** test-harness + docs only; **no production code change.** New harness
  `test_scripts/validate_quality_safety_operator_structured_numeric_export.py` lets the operator run the Slice 137 validator
  end-to-end and record a closed-vocabulary result. **No new numeric schema/bridge layer, no production wiring, no route, no
  frontend, no judge, no repair, no blocking gate, no provider/model/cloud, no OCR/table/source/`clean.md` parsing, no real/private
  sidecar committed.** `quality_safety_job_artifact.py`, `run_markdown_job.py`, `api/server.py` unchanged.
- **Harness behavior:**
  - **Default synthetic mode** (`python test_scripts/validate_quality_safety_operator_structured_numeric_export.py`) runs five
    synthetic cases through the full chain (operator validator → structured adapter → safe extractor → numeric
    mapper/fact-sheet/recompute → advisory artifact builder) and **exits non-zero if any expectation fails**.
  - **Optional local/private mode** (`--input <path>`) reads only that one JSON file, **never prints the path, raw values, or raw
    records**, prints a closed-vocabulary status only, and **writes nothing**; a read/parse failure degrades to a closed
    `input_read_failed` token. Local path / private JSON / raw values must never be committed.
  - Closed summary fields are closed tokens only (`validation_id`, `input_kind`, `operator_export_created`,
    `operator_export_committed=false`, `artifact_name`, `artifact_path_exercised`, the five component statuses,
    `recompute_status`, `recompute_blocker_present`, `shippable`, `safety_floor_green`, `*_committed=false`, `provider/judge/
    repair_calls=false`, closed `warnings`).
- **Synthetic results:** `35 passed, 0 failed` — `clean_operator_export_case` recompute **passed** (shippable);
  `wrong_operator_export_case` recompute **failed → blocker** (not shippable); `unsupported_operator_export_case`
  partial/unverified (no false blocker, `unverified_unsupported_method`); `malformed_operator_export_case` validator **failed**, no
  leak; `forbidden_field_operator_export_case` forbidden fields **stripped**, no canary leak. The validator (422), adapter (177),
  safe extractor (207), job artifact (753), recompute verifier (99), real-disaster e2e (100) all still pass; `compileall` clean;
  `git diff --check` clean. Docker not run (test/docs only); no docker compose config run.
- **Waiver decision:** `operator_numeric_export_waiver=approved_for_safety_floor_finalization_synthetic_only`. Only the synthetic
  harness was run; **no private/local operator run was performed or committed.** `private_operator_run=not_run`.
- **Numeric infrastructure is now FROZEN** — no more numeric schema/bridge layers before the judge path unless a real blocker
  appears.
- **Decision record:** `harness_status=ok`; `numeric_infrastructure_frozen=true`;
  `operator_numeric_export_waiver=approved_for_safety_floor_finalization_synthetic_only`; `private_operator_run=not_run`;
  `judge_ready=false`; `repair_ready=false`; `next_step=deterministic_safety_floor_final_gate`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`,
  `?? test_scripts/validate_quality_safety_operator_structured_numeric_export.py`. **Slice 138 remains NOT committed.**
- **Next recommended slice:** **Slice 139 — Deterministic Safety Floor Final Gate.** `judge_ready=false`; `repair_ready=false`.

---

## Slice 137 — **Pure Operator Structured Numeric Export Validator v1**, on `slice137-quality-safety-operator-structured-numeric-export-validator-v1`. **Committed `763fb4a`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 136 was committed as `eb13ada`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Final trunk status before branching Slice 137 was clean; no docker compose config was run;
  the Slice 60 trace stash remains parked and untouched.
- **Scope:** pure/unwired implementation. New module
  `pipeline/quality_safety_operator_structured_numeric_export_validator.py` validates an operator-authored (or synthetic)
  `quality_safety_structured_numeric_candidates`-like dict against the Slice 136 protocol *before* it may feed the existing
  adapter → safe extractor → numeric mapper → fact-sheet → recompute path. **No production wiring, no route, no frontend change,
  no real/private sidecar validated, no judge, no repair, no blocking gate, no OCR/table/source/`clean.md` parsing, no
  provider/model/cloud.** `quality_safety_job_artifact.py` was **not** changed (no compatibility bug found).
- **Public API:** `validate_operator_structured_numeric_export(payload, *, max_items=None)`,
  `build_empty_operator_structured_numeric_export_validation(reason="component_missing")`,
  `operator_export_validation_to_structured_numeric_payload(validation_result)`.
- **Output shape:** `kind=quality_safety_operator_structured_numeric_export_validation`; closed `status`
  (`ok|warning|skipped|partial|failed`); `source_quality` (`operator_approved|synthetic|unknown`); `summary`
  (`input_candidate_count`, `accepted_candidate_count`, `rejected_candidate_count`, `supported_method_count`,
  `unsupported_method_count`, `forbidden_field_count`); a sanitized, forbidden-field-free `structured_numeric_payload`
  (`kind=quality_safety_structured_numeric_candidates`, `source_quality=operator_approved|synthetic`, `candidates`); closed
  `warnings`.
- **Gate rules:** require `kind=quality_safety_structured_numeric_candidates`; `source_quality` operator_approved/synthetic else
  degrade to `unknown`; `fact_type=numeric`, finite `value`, `provenance` ∈ {operator_approved, computed}, and a dict
  `computation` with a string method for acceptance; supported methods `weighted_gini`/`total_error`/`amount_of_say`/`softmax`/
  `cross_entropy`/`forward_pass`. Unsupported methods are **degraded** (kept + flagged `unsupported_method`, never promoted to a
  recomputable/supported count). Forbidden fields are detected, counted, stripped, and never emitted (the Slice 133 adapter is
  reused per-candidate so no forbidden value can leak). Never raises; never mutates caller input; deterministic; `max_items` caps.
- **Downstream compatibility (proved with synthetic fixtures):** validator → structured candidate adapter → safe numeric
  extractor → numeric mapper → fact-sheet producer → recompute verifier all chain cleanly; and the re-emitted
  `structured_numeric_payload` feeds the Slice 134 advisory artifact path
  (`build_quality_safety_job_artifact_payload(structured_numeric_candidates=...)`) — clean cases stay shippable, confident-wrong
  cases raise a recompute blocker and go not-shippable.
- **Real-disaster synthetic equivalents:** `single_confident_wrong_numeric_case` validates `ok` then produces a recompute
  **blocker** downstream (not shippable); `clean_real_case` validates `ok` and **passes** recompute (shippable);
  `legacy_confused_wrong_case` (unsupported method) validates `warning` and stays **partial/unverified** (no false blocker), while
  the supported-method variant blocks correctly.
- **Validation:** new test `test_scripts/test_quality_safety_operator_structured_numeric_export_validator.py` (422 passed, 0
  failed); adapter (177), safe extractor (207), job artifact (753), recompute verifier (99), real-disaster e2e (100) all pass;
  `python -m compileall api pipeline test_scripts` clean; `git diff --check` clean. Docker not run (pure/unwired); no docker
  compose config run.
- **Decision record:** `validator_status=ready`; `operator_export_must_be_validated_before_private_runs=true`;
  `validator_wired_into_production=false`; `quality_safety_blocking=false`; `unsupported_methods=degraded_not_extended`;
  `judge_ready=false`; `repair_ready=false`; `next_step=operator_structured_numeric_export_validation_harness`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md`,
  `M docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`,
  `?? pipeline/quality_safety_operator_structured_numeric_export_validator.py`,
  `?? test_scripts/test_quality_safety_operator_structured_numeric_export_validator.py`. **Slice 137 is committed as `763fb4a` and
  merged to `chrome-renderer-v1`.**
- **Next recommended slice:** **Slice 138 — Operator Structured Numeric Export Validation Harness** (still pure/unwired; no
  production wiring; no judge/repair) unless a blocker is found.

---

## Slice 136 — **Operator Structured Numeric Export Protocol**, on `slice136-quality-safety-operator-structured-numeric-export-protocol`. **Committed `eb13ada`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 135 was committed as `c96e5f4`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Final trunk status before branching Slice 136 was clean; no docker compose config was run;
  the Slice 60 trace stash remains parked and untouched.
- **Scope:** docs/design/protocol-only. New doc `docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md` defines the
  exact operator workflow that produces a `quality_safety_structured_numeric_candidates.json`-compatible closed-schema export.
  **No operator export validator was implemented, no producer was wired, no production code changed, no OCR/table/source/`clean.md`
  parsing, no provider/model/cloud, no judge, no repair, no blocking gate.**
- **Operator protocol (closed step list):** `inspect_private_material_locally` → `identify_numeric_claims_with_supported_methods`
  → `encode_structured_candidate_records` → `run_local_validation_harness` → `inspect_quality_safety_unified_qa_json_locally` →
  `commit_closed_vocabulary_validation_record_only` → `do_not_commit_sidecar_or_runtime_outputs`.
- **Schema:** Slice 132/133 closed schema; required `kind=quality_safety_structured_numeric_candidates`,
  `source_quality=operator_approved`, `provenance=operator_approved|computed`, `fact_type=numeric`; supported methods
  `weighted_gini`, `total_error`, `amount_of_say`, `softmax`, `cross_entropy`, `forward_pass`; numeric inputs only. Forbidden
  candidate fields (raw_text / source_text / guide_text / ocr_text / page_text / table_cells / captions / formulas_as_text /
  evidence_quotes / filenames / basenames / paths / urls / provider_payloads / runtime_traces / raw_exceptions / raw_artifact_json)
  must never appear.
- **Privacy handling:** operator may inspect private material **locally only**; never commit source/guide/OCR/page/table/caption
  text, formulas, evidence quotes, filenames, basenames, paths, URLs, screenshots, runtime artifacts, raw artifact JSON, provider
  payloads, or the sidecar JSON itself. Only closed-vocabulary records and synthetic fixtures/canaries enter git.
- **Validation record:** closed-vocabulary template committed (tokens only). `operator_export_committed` is fixed `false`; a real
  run is `not_observed` until the pure validator (Slice 137) exists.
- **Decision record:** `operator_protocol_status=ready`; `operator_export_validator_needed=true`;
  `production_numeric_extractor_present=structured_artifact_sidecar_only`; `numeric_fact_sheet_extraction_leg_status=partial`;
  `artifact_path_ready=true_for_synthetic_structured_candidates`; `judge_ready=false`; `repair_ready=false`;
  `next_step=pure_operator_export_validator`.
- **Next recommended slice:** **Slice 137 — Pure Operator Structured Numeric Export Validator v1** (pure/unwired validator for
  operator-approved structured-candidate-like dicts; synthetic tests only; no production wiring; no private sidecar commit; no
  OCR/table/source parsing; no judge/repair).
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`,
  `?? docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md`. **Slice 136 is committed as `eb13ada` and merged to
  `chrome-renderer-v1`.**

---

## Slice 135 — **Future Structured Numeric Candidate Producer Design**, on `slice135-quality-safety-structured-numeric-candidate-producer-design`. **Committed `c96e5f4`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 134 was committed as `244361a`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Final trunk status before branching Slice 135 was clean; no docker compose config was run;
  the Slice 60 trace stash remains parked and untouched.
- **Scope:** docs/design-only. New doc `docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md` designs the first
  acceptable producer of `quality_safety_structured_numeric_candidates.json`. **No producer was implemented, no producer wiring
  was added, no production code changed, no OCR/table/source/`clean.md` parsing, no provider/model/cloud, no judge, no repair.**
- **Producer options evaluated (closed vocabulary):** `operator_approved_structured_export` (**select**),
  `already_sanitized_structural_artifact_adapter` (reject — Slice 131 found no structural artifact carries numeric method
  inputs), `model_generated_structured_numeric_export` (defer — would require provider/cloud and raw-text reads), and
  `sidecar_only_operator_waiver` (defer — unprotocolled stance folded into the selected option).
- **Recommended producer v1:** `operator_approved_structured_export` — operator authors closed-schema records only; no raw
  private material in git; explicit manual waiver/gate, not automated production extraction. The adapter already whitelists
  `source_quality=operator_approved` and `provenance=operator_approved`.
- **Decision record:** `recommended_producer_v1=operator_approved_structured_export`;
  `production_numeric_extractor_present=structured_artifact_sidecar_only`; `numeric_fact_sheet_extraction_leg_status=partial`;
  `artifact_path_ready=true_for_synthetic_structured_candidates`; `judge_ready=false`; `repair_ready=false`;
  `next_step=operator_export_protocol`.
- **Next recommended slice:** **Slice 136 — Operator Structured Numeric Export Protocol** (docs/design; defines exact operator
  workflow + explicit waiver wording; no production code; no judge/repair/prompt tuning). Judge baseline stays blocked
  (`judge_ready=false`) until an explicit operator waiver is approved.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`,
  `M docs/QUALITY_SAFETY_PRODUCTION_SAFE_CANDIDATE_SOURCE_DISCOVERY.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `?? docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`. **Slice 135 is committed as `c96e5f4` and merged to
  `chrome-renderer-v1`.**

---

## Slice 134 — **Wire Structured Numeric Candidate Adapter into Advisory Artifact Path**, on `slice134-wire-structured-numeric-candidate-adapter-advisory-artifact`. **Committed `244361a`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 133 was committed as `990179c`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Final trunk status before branching Slice 134 was clean; no docker compose config was run;
  the Slice 60 trace stash remains parked and untouched.
- **Scope:** advisory/non-blocking wiring only. `quality_safety_job_artifact.py` and `run_markdown_job.py` now optionally read
  the exact job-local sidecar `quality_safety_structured_numeric_candidates.json`, pass it through the Slice 133 adapter, and feed
  the adapted payload into the existing Slice 129 safe-candidate path. **No future producer was implemented, no structured
  sidecar is written, no OCR/table/source parsing was added, no `clean.md` numeric read was added, and no production numeric
  extraction coverage is claimed complete.**
- **Precedence:** deterministic and non-merged: `quality_safety_numeric_extraction_records.json` >
  `quality_safety_safe_numeric_candidates.json` > `quality_safety_structured_numeric_candidates.json`.
- **Artifact shape:** `quality_safety_unified_qa.json` keeps the same exact artifact name and now adds
  `structured_numeric_candidate_adapter_status`, `structured_numeric_candidate_adapter_summary`, and
  `structured_numeric_candidate_adapter_warnings`. These are summary/status/warnings only; adapted candidates flow internally
  into `safe_numeric_extractor_*` / `numeric_extraction_*`.
- **Observed synthetic outcomes:** structured clean candidate -> adapter `ok`, safe extractor `ok`, recompute `passed`;
  structured wrong candidate -> recompute blocker / `failed` / `shippable=false` / `safety_floor_green=false`;
  unsupported structured method -> partial/warning, counted, and not falsely recompute-blocked.
- **Closed-vocabulary outcome:** `structured_numeric_candidate_adapter_artifact_path_status=ok`;
  `safe_numeric_extractor_artifact_path_status=ok`; `numeric_fact_sheet_extraction_leg_status=partial`;
  `artifact_path_ready=true_for_synthetic_structured_candidates`;
  `production_numeric_extractor_present=structured_artifact_sidecar_only`; `judge_ready=false`; `repair_ready=false`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`,
  `M docs/QUALITY_SAFETY_PRODUCTION_SAFE_CANDIDATE_SOURCE_DISCOVERY.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`,
  `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `M pipeline/quality_safety_job_artifact.py`,
  `M pipeline/run_markdown_job.py`, `M test_scripts/test_quality_safety_job_artifact.py`,
  `M test_scripts/validate_quality_safety_real_disaster_e2e.py`.
- **Next recommended slice:** **Slice 135 — Future Structured Numeric Candidate Producer Design or Operator Waiver**, unless
  review finds a blocker. Do not claim production numeric extraction coverage complete until a real producer exists and is
  validated.
- **Out of scope / unchanged:** no `api/server.py` change, no routes, no frontend/UI change, no generic artifact listing, no
  generation/prompt/provider/request-schema/render/export/OCR/table/visual/Ask Guide change, no judge/`overall_10`/repair/
  blocking gate, no `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. **Slice 134 is committed as
  `244361a` and merged to `chrome-renderer-v1`.**

---

## Slice 133 — **Pure Structured Numeric Candidate Artifact Adapter v1**, on `slice133-quality-safety-structured-numeric-candidate-adapter-v1`. **Committed `990179c`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 132 was committed as `9d48656`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Final trunk status before branching Slice 133 was clean; no docker compose config was run;
  the Slice 60 trace stash remains parked and untouched.
- **Scope:** pure/unwired adapter only. Added
  `pipeline/quality_safety_structured_numeric_candidate_adapter.py`, which converts caller-supplied
  `quality_safety_structured_numeric_candidates` dictionaries into
  `quality_safety_safe_numeric_candidates`-compatible payloads under the existing closed `candidates` wrapper. **No production
  wiring, no sidecar reads/writes, no job-folder scan, no source/OCR/table/caption parsing, no `clean.md` numeric read, no
  provider/model/cloud, no API/frontend/runtime import, no judge, no repair, no blocking.**
- **Output shape:** `version=1`, `kind=quality_safety_safe_numeric_candidates`, closed `status`, closed `source_quality`,
  `summary.input_candidate_count`, `summary.output_candidate_count`, `summary.supported_method_count`,
  `summary.unsupported_method_count`, `summary.dropped_candidate_count`, sanitized `candidates`, and closed top-level
  `warnings`.
- **Supported methods:** unchanged v1 set: `weighted_gini`, `total_error`, `amount_of_say`, `softmax`, `cross_entropy`,
  `forward_pass`. Unsupported safe method tokens are preserved only far enough for the Slice 129 extractor / Slice 125 mapper to
  degrade them as unsupported/unverified; no verifier method is added.
- **Compatibility result:** synthetic structured artifact -> adapter -> safe numeric extractor -> numeric mapper -> fact-sheet
  producer -> recompute verifier works. Clean supported candidates pass recompute; wrong supported candidates raise recompute
  blockers; unsupported methods remain partial/unverified without false recompute verification.
- **Advisory artifact-path compatibility:** `build_quality_safety_job_artifact_payload(safe_numeric_candidates=adapter_payload)`
  accepts the adapter's `{"candidates": [...]}` wrapper. Clean synthetic payload produces `safe_numeric_extractor_status=ok`,
  `numeric_extraction_status=ok`, and `component_statuses.recompute=passed`; wrong synthetic payload produces a recompute blocker.
  This is compatibility-only and adds no production wiring.
- **Real-disaster synthetic equivalents:** `single_confident_wrong_numeric_case` -> `failed_blocking`; `clean_real_case` ->
  `passed`; `legacy_confused_wrong_case` -> `partial` for unsupported method, with a supported-method variant blocking correctly.
- **Closed-vocabulary outcome:** `adapter_status=ready`; `adapter_implemented=true`; `producer_implemented=false`;
  `production_wiring_changed=false`; `numeric_fact_sheet_extraction_leg_status=partial`; `judge_ready=false`;
  `repair_ready=false`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`,
  `M docs/QUALITY_SAFETY_PRODUCTION_SAFE_CANDIDATE_SOURCE_DISCOVERY.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`,
  `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `?? pipeline/quality_safety_structured_numeric_candidate_adapter.py`,
  `?? test_scripts/test_quality_safety_structured_numeric_candidate_adapter.py`.
- **Next recommended slice:** **Slice 134 — Wire Structured Numeric Candidate Adapter into Advisory Artifact Path**, unless a
  later review finds a blocker. This should be a separate bounded wiring slice; Slice 133 remains unwired.
- **Out of scope / unchanged:** no `quality_safety_job_artifact.py` change, no `run_markdown_job.py` change, no `api/server.py`
  change, no routes, no frontend change, no production sidecar reader/writer, no generation/prompt/provider/request-schema/render/
  export/OCR/table/visual/Ask Guide change, no judge/`overall_10`/repair/blocking gate, no `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`. **Slice 133 is committed as `990179c` and merged to `chrome-renderer-v1`.**

---

## Slice 132 — **Future Structured Numeric Artifact Design**, on `slice132-quality-safety-future-structured-numeric-artifact-design`. **Committed `9d48656`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 131 was committed as `9db63b1`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Final trunk status before branching was clean; no docker compose config was run; the Slice
  60 trace stash remains parked and untouched.
- **Scope:** design only. Define the future producer-owned structured numeric candidate artifact that can become the first
  production safe candidate source. **No production extraction, no adapter implementation, no OCR/table/source parsing, no
  `clean.md` numeric read, no sidecar writes, no provider/model/cloud, no judge, no repair, no prompt tuning, no blocking.**
- **New doc:** `docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`.
- **Proposed artifact:** `quality_safety_structured_numeric_candidates.json`.
- **Sidecar distinction:** `quality_safety_structured_numeric_candidates.json` is the future producer-owned source artifact;
  `quality_safety_safe_numeric_candidates.json` remains the current internal read-only compatibility sidecar consumed by the
  Slice 130 path; `quality_safety_numeric_extraction_records.json` remains the explicit post-candidate records sidecar.
- **Producer boundary:** allowed future producers are `future_structured_numeric_extractor`,
  `operator_approved_structured_export`, and `synthetic_fixture_generator`. Forbidden producers are
  `raw_ocr_parser_direct_to_numeric`, `raw_table_cell_parser_direct_to_numeric`, `clean_md_parser`,
  `provider_payload_parser`, and `source_document_reader`.
- **Output contract:** allowed top-level fields are `version`, `kind`, `status`, `source_quality`, `candidates`, `summary`, and
  `warnings`. Allowed candidate fields match the Slice 129/125 numeric candidate shape: ids/labels, `fact_type=numeric`,
  `value`, `unit`, safe refs, confidence/provenance, structured `computation.method` + `computation.inputs`, `tolerance`, and
  closed warnings. Forbidden fields include raw/source/guide/OCR/page/table/caption text, formula strings, evidence quotes,
  filenames/basenames/paths/URLs, provider payloads, runtime traces, raw exceptions, and raw artifact JSON.
- **Flow decision:** future producer -> `quality_safety_structured_numeric_candidates.json` -> pure adapter/bridge ->
  `quality_safety_safe_numeric_candidates.json`-compatible payload -> Slice 129 safe extractor -> Slice 130 advisory path.
  Slice 132 does not implement this flow; existing production path remains sidecar-only.
- **Real-disaster target matrix:** `single_confident_wrong_numeric_case` is `future_artifact_representable=true`,
  `expected_recompute_outcome=failed_blocking`, `missing_piece=future_producer`; `clean_real_case` is
  `future_artifact_representable=true`, `expected_recompute_outcome=passed`, `missing_piece=future_producer`;
  `legacy_confused_wrong_case` is `future_artifact_representable=partial`, `expected_recompute_outcome=partial`,
  `missing_piece=method_extension`.
- **Closed-vocabulary outcome:** `structured_numeric_artifact_design=defined`; `artifact_name=quality_safety_structured_numeric_candidates.json`;
  `adapter_implemented=false`; `producer_implemented=false`; `production_wiring_changed=false`; `judge_ready=false`;
  `repair_ready=false`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_PRODUCTION_SAFE_CANDIDATE_SOURCE_DISCOVERY.md`,
  `?? docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md`.
- **Next recommended slice:** **Slice 133 — Pure Structured Numeric Candidate Artifact Adapter v1**. Purpose: pure/unwired
  adapter from `quality_safety_structured_numeric_candidates.json`-like dicts into
  `quality_safety_safe_numeric_candidates.json`-compatible payloads; synthetic tests only; no production wiring, parser, judge,
  or repair.
- **Out of scope / unchanged:** no production code, no `quality_safety_job_artifact.py` change, no `run_markdown_job.py` change,
  no `api/server.py` change, no routes, no frontend change, no generation/prompt/provider/request-schema/render/export/OCR/
  table/visual/Ask Guide change, no judge/`overall_10`/repair/blocking gate, no `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`. **Slice 132 is committed as `9d48656` and merged to `chrome-renderer-v1`.**

---

## Slice 131 — **Production Safe Candidate Source Discovery**, on `slice131-quality-safety-production-safe-candidate-source-discovery`. **Committed `9db63b1`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 130 was committed as `cd3a23b`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Final trunk status before branching was clean; no docker compose config was run; the Slice
  60 trace stash remains parked and untouched.
- **Scope:** discovery/design only. Inspect existing code/docs for already-sanitized structured artifacts that could feed
  `quality_safety_safe_numeric_candidates.json`-compatible records. **No production source adapter, no OCR/table/source parsing,
  no `clean.md` numeric read, no job-folder scan, no sidecar writes, no provider/model/cloud, no judge, no repair, no blocking.**
- **New doc:** `docs/QUALITY_SAFETY_PRODUCTION_SAFE_CANDIDATE_SOURCE_DISCOVERY.md` records a closed-vocabulary inventory of
  `explicit_numeric_records_sidecar`, `safe_numeric_candidates_sidecar`, `source_coverage_report`, `extraction_metadata`,
  `visual_inclusion_plan`, `table_candidates_manifest`, `table_reconstruction_policy`, `quality_safety_unified_qa`,
  `future_structured_numeric_artifact`, and `operator_manual_sidecar`.
- **Discovery result:** no existing already-produced structured artifact safely contains the required numeric candidate shape
  (`value` plus structured `computation.method` and numeric `computation.inputs`). Structural coverage artifacts contain counts
  and shape only; table artifacts contain table structure/count/policy tokens but no safe cell values or recomputable method
  inputs; `quality_safety_unified_qa.json` is an output artifact and not a candidate source.
- **Existing safe source decision:** the two sidecar paths can represent synthetic/manual candidates, but they are not production
  sources. `single_confident_wrong_numeric_case` and `clean_real_case` remain representable through sidecars or a future
  structured numeric artifact; `legacy_confused_wrong_case` remains `partial` unless a supported method is emitted, otherwise a
  bounded recompute-method extension is required.
- **Closed-vocabulary outcome:** `existing_production_safe_source_present=false`; `sidecar_only_source_present=true`;
  `operator_waiver_recorded=false`; `next_step=future_structured_numeric_artifact_design`; `judge_ready=false`;
  `repair_ready=false`.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `?? docs/QUALITY_SAFETY_PRODUCTION_SAFE_CANDIDATE_SOURCE_DISCOVERY.md`.
- **Next recommended slice:** **Slice 132 — Future Structured Numeric Artifact Design**. Purpose: define a future structured
  artifact that an extractor or operator can populate with safe method-input records. No production extraction, no OCR/table
  parsing, no judge.
- **Out of scope / unchanged:** no production code, no `quality_safety_job_artifact.py` change, no `run_markdown_job.py` change,
  no `api/server.py` change, no routes, no frontend change, no generation/prompt/provider/request-schema/render/export/OCR/
  table/visual/Ask Guide change, no judge/`overall_10`/repair/blocking gate, no `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`. **Slice 131 is committed as `9db63b1` and merged to `chrome-renderer-v1`.**

---

## Slice 130 — **Wire Safe Numeric Extractor into Advisory Artifact Path**, on `slice130-wire-safe-numeric-extractor-advisory-artifact`. **Committed `cd3a23b`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 129 was committed as `0bff68c`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). No docker compose config was run; the Slice 60 trace stash remains parked and untouched.
- **Scope:** wire the Slice 129 safe numeric extractor into the advisory `quality_safety_unified_qa.json` artifact path. Remains
  **advisory / non-blocking**. An optional, job-local, read-only candidate sidecar feeds the safe extractor, whose records run
  through the existing Slice 126 numeric sidecar/mapper/recompute path. **No production OCR/table/source parsing, no `clean.md`
  numeric read, no job-folder scan, no sidecar writes in production, no provider/model/cloud, no judge, no repair, no blocking.**
- **Candidate input artifact (read-only, optional, internal, non-user-facing):** `quality_safety_safe_numeric_candidates.json` —
  a list of sanitized candidate dicts, or a dict wrapper under a closed `candidates` key. Never created/written by production code,
  never added to generic artifact/export/UI lists. The Slice 125 mapper remains the final sanitizer (strips source/OCR/table/
  caption text, raw formulas, filenames, basenames, paths, URLs, provider payloads, raw runtime/artifact JSON).
- **Precedence (deterministic):** explicit `quality_safety_numeric_extraction_records.json` records **win**; the safe candidate
  sidecar feeds the numeric leg **only** when no explicit records are present. When both exist, safe candidates are summarized
  only (`safe_numeric_extractor_status=skipped`, warning `superseded_by_explicit_records`) and never merged.
- **`pipeline/quality_safety_job_artifact.py`:** added `safe_numeric_candidates` param to
  `build_quality_safety_job_artifact_payload` / `write_quality_safety_job_artifact`; a read-only reader
  `read_quality_safety_safe_numeric_candidates`; runs the Slice 129 extractor; surfaces three **new top-level fields** —
  `safe_numeric_extractor_status` (ok|warning|skipped|partial|failed), `safe_numeric_extractor_summary` (counts only),
  `safe_numeric_extractor_warnings` (closed tokens only). Existing `numeric_extraction_*` fields remain the canonical recompute
  evidence; full extractor payload is NOT inlined (summary/status/warnings only; sanitized records flow internally into
  `numeric_extraction_bundle`). Artifact name/kind/`advisory=true` unchanged.
- **`pipeline/run_markdown_job.py`:** `_write_quality_safety_unified_qa` now also reads the optional candidate sidecar from the
  same job-local location (read-only) and passes it through; degraded fallback payload carries the three new fields too.
- **Validation (synthetic):** safe candidate payload flows through the real artifact path
  (`build_quality_safety_job_artifact_payload(safe_numeric_candidates=...)`) and the production hook
  (`_write_quality_safety_unified_qa`): clean candidate → recompute **passed**, `shippable=true`; wrong candidate → recompute
  **blocking failure**, `shippable=false`, `safety_floor_green=false`; unsupported-method candidate → counted unsupported, **not**
  recompute-blocked; structural coverage is **not** converted into candidates/records; forbidden candidate fields stripped, no
  canary leak; precedence proven (explicit correct records win over a wrong candidate).
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `M pipeline/quality_safety_job_artifact.py`, `M pipeline/run_markdown_job.py`,
  `M test_scripts/test_quality_safety_job_artifact.py`, `M test_scripts/validate_quality_safety_real_disaster_e2e.py`.
- **Validation runs:** safe extractor 207; numeric mapper 232; job artifact **595**; recompute verifier 99; unified qa 73;
  real-disaster e2e **80**; `compileall api pipeline test_scripts` OK; `git diff --check` clean; no-leak sweep clean. No docker
  compose config was run; Docker not required (no container surface changed).
- **Closed-vocabulary outcome:** `safe_numeric_extractor_artifact_path_status=ok`;
  `numeric_fact_sheet_extraction_leg_status=partial`; `artifact_path_ready=true_for_synthetic_candidates`;
  `production_numeric_extractor_present=sidecar_candidate_only`; `judge_ready=false`; `repair_ready=false`. Production numeric
  extraction coverage is **not** claimed complete (no production source emits candidates yet).
- **Next recommended slice:** a production safe-candidate *source* (a separately-designed bounded slice that derives sanitized
  candidates from already-sanitized structured artifacts), or an explicit operator waiver accepting sidecar-only coverage. Only
  after a proven production candidate source (or waiver) revisit `judge_ready`.
- **Out of scope / unchanged:** no `api/server.py` change, no routes, no frontend change, no generic artifact selector row, no
  generation/prompt/provider/request-schema/render/export/OCR/table/visual/Ask Guide change, no judge/`overall_10`/repair/blocking
  gate, no `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. **Slice 130 is committed as `cd3a23b`
  and merged to `chrome-renderer-v1`.**

---

## Slice 129 — **Pure Safe Numeric Extractor v1**, on `slice129-quality-safety-safe-numeric-extractor-v1`. **Committed `0bff68c`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 128 was committed as `8534784`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Slice 128 designed the safe numeric extractor (design only; allowed input
  `caller_supplied_sanitized_numeric_candidates`; v1 methods unchanged; `production_numeric_extractor_present=false`,
  `judge_ready=false`, `repair_ready=false`). No docker compose config was run; the Slice 60 trace stash remains parked.
- **Scope:** implement a **pure, unwired** safe numeric extractor that converts caller-supplied sanitized numeric candidates
  into `quality_safety_numeric_extraction_records.json`-compatible records. **Not production wiring** — no module imports it, no
  artifact is written, and the production job artifact path is unchanged. No OCR/table/source parsing, no `clean.md` reads, no
  job-folder scan, no provider/model/cloud, no judge, no repair, no prompt tuning.
- **New module `pipeline/quality_safety_safe_numeric_extractor.py`** (stdlib + Slice 125 mapper only):
  - `normalize_safe_numeric_candidate(candidate, *, index=0)` — resolves the flat `method`/`inputs` alias into a `computation`
    block, injects a stable synthetic `qs_safe_num_NNNN` id when the candidate has none, strips/flags forbidden fields, then
    **defers all field sanitization to the Slice 125 mapper** (`normalize_quality_safety_numeric_extraction_record`) as the
    final sanitizer. Returns a closed-vocabulary record or `None`; never raises; never mutates input.
  - `extract_quality_safety_numeric_records_from_candidates(candidates, *, max_items=None, source_quality="sanitized_candidates")`
    — returns a `quality_safety_numeric_extraction_records` payload (`version`, `kind`, `status`, `source_quality`, `summary`
    {`candidate_count`, `record_count`, `supported_method_count`, `unsupported_method_count`, `dropped_candidate_count`},
    `records`, `warnings`).
  - `build_empty_safe_numeric_extraction_records(reason="component_missing")` — empty/closed payload.
  - `map_safe_numeric_candidates_to_sidecar_payload(candidates, *, max_items=None)` — the sidecar-writable payload (records under
    the closed `records` key, accepted directly by the Slice 126 artifact reader's `_coerce_numeric_records`).
- **Supported v1 methods (unchanged):** `weighted_gini`, `total_error`, `amount_of_say`, `softmax`, `cross_entropy`,
  `forward_pass`. No new methods. Unsupported methods demote to a bare numeric observation (`unsupported_method`), never
  falsely recompute-verified.
- **Compatibility proven (synthetic):** payload flows through `_coerce_numeric_records` → Slice 125 mapper → fact-sheet
  producer → recompute verifier, **and** straight into the real Slice 126 artifact path
  (`build_quality_safety_job_artifact_payload(numeric_extraction_records=payload)`):
  - `single_confident_wrong_numeric_case` synthetic → recompute **blocking failure**; through the artifact path `shippable=false`,
    `safety_floor_green=false`.
  - `clean_real_case` synthetic → recompute **passed**; artifact numeric status `ok`, no numeric recompute blocker.
  - `legacy_confused_wrong_case` synthetic → **partial**: an unsupported-method claim demotes to a bare observation and is
    **not** recompute-blocked (the wrong value escapes); the same archetype expressed with a supported method **is** blocked.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `?? pipeline/quality_safety_safe_numeric_extractor.py`, `?? test_scripts/test_quality_safety_safe_numeric_extractor.py`.
- **Validation:** new extractor test **207 passed**; numeric mapper 232; job artifact 428; recompute verifier 99; real-disaster
  e2e 60; `compileall api pipeline test_scripts` OK; `git diff --check` clean; no-leak sweep clean. No docker compose config was
  run; Docker not required (pure/unwired slice).
- **Extractor status:** `ready` for `caller_supplied_sanitized_numeric_candidates` (clean + single-confident-wrong archetypes);
  `partial` for `legacy_confused_wrong_case` (would need a separately-designed bounded `recompute_method_extension` only if a real
  claim rests on an unsupported method). No production wiring → `judge_ready=false`, `repair_ready=false`; production numeric
  extraction coverage is **not** claimed complete.
- **Next recommended slice:** **Slice 130 — Wire Safe Numeric Extractor into Advisory Artifact Path** (unless a blocker surfaces).
- **Out of scope / unchanged:** no production wiring, no change to `quality_safety_job_artifact.py`/`run_markdown_job.py`/
  `api/server.py`, no routes, no frontend change, no generic artifact selector row, no generation/prompt/provider/
  request-schema/render/export/visual/Ask Guide change, no judge/`overall_10`/repair/blocking gate, no `quality_judge.py`,
  `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. **Slice 129 is committed as `0bff68c` and merged to
  `chrome-renderer-v1`.**

---

## Slice 128 — **Safe Numeric Extractor Design**, on `slice128-quality-safety-safe-numeric-extractor-design`. **Committed `8534784`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 127 was committed as `35bdf8b`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Slice 127 validated the numeric sidecar advisory artifact path (synthetic path `ok`;
  private operator path `not_run`; leg `partial`; `judge_ready=false`, `repair_ready=false`). No docker compose config was run;
  the Slice 60 trace stash remains parked and untouched.
- **Scope:** **design only** — define the safe production numeric extractor that can eventually produce
  `quality_safety_numeric_extraction_records.json`-compatible records, without consuming/emitting private/raw material. No
  production extractor code, no OCR/table/source parsing, no `clean.md` reads, no job-folder scan, no judge, no repair, no
  prompt tuning. **Docs-only** (new design doc + live-doc updates); no optional test added — the existing mapper tests already
  cover the schema/forbidden-field stripping as an executable spec.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `?? docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`.
- **Design summary (new doc `docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`):**
  - **Allowed inputs:** `caller_supplied_sanitized_numeric_candidates` (v1 path), `synthetic_numeric_fixtures`,
    `future_safe_structured_numeric_artifact` (named, not built in v1).
  - **Forbidden inputs:** source documents, pdf images, docx files, `clean.md` as numeric source, OCR/page text, table cells,
    captions, guide text, provider payloads, raw runtime artifacts, raw artifact JSON, filenames, basenames, paths, URLs.
  - **Output contract:** Slice 124/125 record shape (`id`, `concept_id`, `label`, `fact_type=numeric`, `value`, `unit`,
    `provenance`, `confidence`, `source_ref`, `page_ref`, `computation.{method,inputs}`, `tolerance`, `warnings`) —
    sanitized tokens only; mapper remains the final sanitizer.
  - **Supported v1 methods (verified against `SUPPORTED_METHODS`):** `weighted_gini`, `total_error`, `amount_of_say`,
    `softmax`, `cross_entropy`, `forward_pass`. No new methods.
  - **Degradation:** closed-token behavior for no_input/malformed/unsupported_method/unsafe_field/invalid_value/
    invalid_computation/missing_field/max_items — never crash, never block the job, never leak.
- **Archetype targeting (closed vocabulary):** `single_confident_wrong_numeric_case` and `clean_real_case` →
  `extractor_representable=true` via supported methods; `legacy_confused_wrong_case` → `partial` (may need a bounded
  recompute-method extension if its claim rests on an unsupported method). All three need
  `next_requirement=mapper_input_generation`; no `unsafe_source_blocker`.
- **Next recommended slice:** **Slice 129 — Pure Safe Numeric Extractor v1** (pure/unwired, synthetic tests only, no parsing,
  no wiring, no provider/judge/repair). If a real case needs an unsupported method, recommend a bounded
  `recompute_method_extension` design slice instead of widening v1.
- **No-leak boundary:** docs carry only closed-vocabulary design + outcomes; no source/guide/OCR/table/caption text, copied
  formulas, numeric prose, evidence quotes, filenames, basenames, paths, URLs, raw artifact JSON, runtime outputs, provider
  payloads, or real/private sidecar JSON. `production_numeric_extractor_present=false`; production coverage **not** claimed
  complete. `judge_ready=false`, `repair_ready=false`.
- **Validation:** `compileall api pipeline test_scripts` OK; numeric mapper 232 passed; job artifact 428 passed; real-disaster
  e2e 60 passed; `git diff --check` clean; no-leak sweep clean. No docker compose config was run; Docker not required
  (docs-only design slice).
- **Out of scope / unchanged:** no production extractor, no OCR/table/source parsing, no `clean.md` numeric read, no job-folder
  scan, no change to `quality_safety_job_artifact.py`/`run_markdown_job.py`/`api/server.py`, no routes, no frontend change, no
  generic artifact selector row, no generation/prompt/provider/request-schema/render/export/visual/Ask Guide change, no
  judge/`overall_10`/repair/blocking gate, no `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`.
  **Slice 128 is committed as `8534784` and merged to `chrome-renderer-v1`.**

---

## Slice 127 — **Numeric Sidecar Real-Path Operator Validation**, on `slice127-quality-safety-numeric-sidecar-real-path-validation`. **Committed `35bdf8b`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 126 was committed as `7ff1887`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed with
  a normal `git push` (no force-push). Slice 126 wired the Slice 125 numeric extraction mapper into the advisory
  `quality_safety_unified_qa.json` artifact path. No docker compose config was run; the Slice 60 trace stash remains parked
  and untouched.
- **Scope:** operator-/harness-validation only. Validate the Slice 126 numeric sidecar advisory artifact path against the
  real-disaster archetypes and decide the next step. No production extraction, no judge, no repair, no prompt tuning. Docs-only
  (no application-code change); the existing synthetic real-disaster harness already records the required closed-token
  outcomes, so no new harness script was added.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`.
- **Track A — synthetic sidecar regression (run, ok):** through the actual builder + production hook — sidecar missing →
  `skipped`/`numeric_extraction_missing` (no crash); malformed → `failed`/`numeric_extraction_degraded` (no leak); clean
  synthetic record → `recompute=passed` through the artifact; wrong synthetic record → recompute blocker, `shippable=false`,
  `safety_floor_green=false`; artifact stays advisory/non-blocking; structural coverage stays separate; no canary leaks.
- **Track B — operator real-path validation with private material:** `input_kind=not_run` this slice (not performed
  autonomously; safe production of private sidecar records requires an operator pass or a safe numeric extractor). All three
  archetypes (`legacy_confused_wrong_case`, `single_confident_wrong_numeric_case`, `clean_real_case`) validated only via the
  synthetic equivalents in Track A; `sidecar_committed=false`, `raw_text_committed=false`, `provider_calls=false`,
  `judge_calls=false`, `repair_calls=false`.
- **Decision record:** `numeric_sidecar_real_path_validation=run`; `status=partial`;
  `synthetic_sidecar_artifact_path=ok`; `private_operator_sidecar_artifact_path=not_run`;
  `numeric_fact_sheet_extraction_leg_status=partial`; `artifact_path_ready=true_for_synthetic` (partial overall);
  `production_numeric_extractor_present=false`; `judge_ready=false`; `repair_ready=false`;
  `next_step=safe_numeric_extractor_design`.
- **Validation:** numeric mapper 232 passed; job artifact 428 passed; real-disaster e2e 60 passed; recompute verifier 99;
  unified QA 73; `compileall api pipeline test_scripts` OK; `git diff --check` clean; no-leak sweep clean. No docker compose
  config was run.
- **Out of scope / unchanged:** no production numeric extractor; no OCR/table/source parsing; no `clean.md` numeric read; no
  job-folder scan; no routes; no frontend change; no generic artifact selector row; no generation/prompt/provider/
  request-schema/render/export/visual/Ask Guide change; no judge/`overall_10`/repair/blocking gate; no `quality_judge.py`,
  `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. **Slice 127 is committed as `35bdf8b` and merged to `chrome-renderer-v1`.**

---

## Slice 126 — **Wire Numeric Extraction Mapper into Advisory Artifact**, on `slice126-wire-quality-safety-numeric-mapper-advisory-artifact`. **Committed `7ff1887`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 125 was committed as `13a7ef6`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 125 added the pure/unwired numeric extraction mapper
  (`pipeline/quality_safety_numeric_extraction_mapper.py`). No docker compose config was run; the Slice 60 trace stash remains
  parked and untouched.
- **Scope:** wire the Slice 125 mapper into the existing advisory `quality_safety_unified_qa.json` job artifact path so a safe
  numeric extraction records sidecar (when present) feeds the producer + recompute verifier. Advisory/non-blocking; no
  production numeric extractor is created.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `M pipeline/quality_safety_job_artifact.py`,
  `M pipeline/run_markdown_job.py`, `M test_scripts/test_quality_safety_job_artifact.py`,
  `M test_scripts/validate_quality_safety_real_disaster_e2e.py`.
- **Safe input artifact:** exact name `quality_safety_numeric_extraction_records.json` — an optional, **read-only** job-local
  *input* sidecar candidate for a future safe numeric extractor. It is **never created or written in production** by this
  slice; it is read only if it already exists, and is not added to any generic artifact/export list or UI row. Accepts a bare
  records list or a dict wrapper (`records` / `numeric_records` / `numeric_extraction_records`).
- **Artifact shape (new fields, kept SEPARATE from `extraction_coverage_*`):** `numeric_extraction_status`
  (`ok|warning|skipped|partial|failed`), `numeric_extraction_summary` (counts only: record/numeric_fact/computation_record/
  supported_method/unsupported_method), `numeric_extraction_warnings` (closed mapper tokens), and the full sanitized
  `numeric_extraction_bundle` (Slice 125 mapper output — already closed-vocabulary, capped, numeric-only). Exact artifact name
  `quality_safety_unified_qa.json`, kind `quality_safety_job_artifact`, `advisory=true`, `source=job_runtime` all unchanged.
- **Behavior:** when numeric records are present and no explicit `extraction_bundle` was supplied, the mapped numeric bundle
  feeds the concept/fact producer → recompute verifier → unified QA, so a **wrong** numeric claim raises a recompute blocker
  (`shippable=false`, `safety_floor_green=false`) and a **clean** one verifies (`recompute=passed`). Missing records degrade to
  `numeric_extraction_status=skipped` + `numeric_extraction_missing`; malformed records degrade to `failed` +
  `numeric_extraction_degraded` — no crash, no job failure, no false shippable upgrade, no raw-value leak.
- **Coverage stays separate:** the structural `extraction_coverage_bundle` still never feeds the producer and is never turned
  into numeric facts; numeric records are never fabricated from structural coverage counts (proven by tests).
- **Recompute-through-artifact (proven):** `clean_real_case` synthetic → `recompute=passed`, shippable;
  `single_confident_wrong_numeric_case` synthetic → recompute blocker, `shippable=false`; wrong `weighted_gini` →
  `shippable=false`, `safety_floor_green=false`; all through the **actual** `build_quality_safety_job_artifact_payload` and the
  production hook `_write_quality_safety_unified_qa` (sidecar read).
- **No production numeric extractor exists yet.** `numeric_fact_sheet_extraction_leg_status=partial` (synthetic records prove
  the artifact path; real material still needs a safe extractor). `artifact_path_ready=true` for synthetic numeric records.
  `judge_ready=false`, `repair_ready=false`.
- **Validation:** numeric mapper 232 passed; job artifact 428 passed; real-disaster e2e 60 passed; fact-sheet producer 182;
  recompute verifier 99; unified QA 73; e2e artifact 36; `compileall api pipeline test_scripts` OK; `git diff --check` clean;
  no-leak sweep clean. No docker compose config was run.
- **Out of scope / unchanged:** no OCR/table/source parsing, no `clean.md` numeric read, no job-folder scan, no `api/server.py`
  change, no routes, no frontend change, no generic artifact selector row, no generation/prompt/provider/request-schema/render/
  export/visual/Ask Guide change, no judge/`overall_10`/repair/blocking gate, no `quality_judge.py`/`nn3.json`/
  `judge_response_nn3.json`/`quality.jsonl`. **Slice 126 is committed as `7ff1887` and merged to `chrome-renderer-v1`.**

---

## Slice 125 — **Pure Numeric Extraction Record Mapper v1**, on `slice125-quality-safety-numeric-extraction-record-mapper-v1`. **Committed `13a7ef6`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 124 was committed as `242d580`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 124 defined the safe structured numeric extraction contract
  (`docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`) and recorded `judge_ready=false`, `repair_ready=false`,
  `next_step=pure_numeric_extraction_record_mapper_v1`. No docker compose config was run, and the Slice 60 trace stash remains
  parked and untouched.
- **Scope:** implement a **pure / unwired** mapper from caller-supplied sanitized numeric extraction records (the Slice 124
  contract shape) into the existing producer `quality_safety_extraction_bundle` shape, so the Slice 117 fact-sheet producer
  and Slice 111 recompute verifier can validate structured numeric facts. Closes the schema/mapper gap from Slice 123/124 but
  adds **no production wiring** — the mapper is not wired into jobs in this slice.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`, `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`,
  `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`, `?? pipeline/quality_safety_numeric_extraction_mapper.py`,
  `?? test_scripts/test_quality_safety_numeric_extraction_mapper.py`.
- **Mapper (`pipeline/quality_safety_numeric_extraction_mapper.py`):** pure, stdlib + the verifier's `SUPPORTED_METHODS` only.
  Public functions: `normalize_quality_safety_numeric_extraction_record`, `build_quality_safety_numeric_extraction_bundle`,
  `build_empty_quality_safety_numeric_extraction_bundle`, `map_numeric_extraction_bundle_to_fact_sheet_input`. Emits a closed
  `quality_safety_numeric_extraction_bundle` (`status` ∈ ok|warning|skipped|partial|failed; `summary` counts; numeric-only
  records with `computation.{method,inputs}` or null) and maps it onto the producer's `computation_records[]` /
  `numeric_observations[]`. Allow-listed fields only; the closed forbidden-field list is stripped and flagged; structured
  numeric `computation.inputs` only (string values stripped except the closed forward-pass activation tokens); tolerance
  capped to `(0.0, 1.0]`; never raises, never mutates caller input.
- **Supported methods:** exactly the verifier's `SUPPORTED_METHODS` — `weighted_gini`, `total_error`, `amount_of_say`,
  `softmax`, `cross_entropy`, `forward_pass`. No new recompute methods were invented; unsupported methods **degrade** (demoted
  to a bare numeric fact with `unsupported_method`), never extend the verifier.
- **Recompute compatibility (proven by tests):** mapper bundle → producer → recompute verifier works for all six supported
  methods; `clean_real_case` synthetic equivalent recompute-verified (`passed`); `single_confident_wrong_numeric_case`
  synthetic equivalent recompute-`failed` with a blocking failure and no contradiction/leak; bare numeric observations are
  never falsely recompute-verified; unsupported/malformed-inputs records degrade without crashing.
- **No production wiring:** no `quality_safety_job_artifact.py` / `run_markdown_job.py` / `api/server.py` change, no routes, no
  frontend change, no generic artifact selector row, no OCR/table/source/`clean.md` reads, no provider/model/cloud calls.
- **judge_ready=false, repair_ready=false** — unchanged; the numeric leg stays `not_covered` until a real **artifact path**
  proves it with safe structured concept/fact data. This slice does **not** claim numeric coverage.
- **Validation:** mapper harness 232 passed; numeric extraction contract 27 passed; fact-sheet producer 182 passed; fact sheet
  61 passed; recompute verifier 99 passed; real-disaster harness 41 passed; `compileall api pipeline test_scripts` OK;
  `git diff --check` clean; no-leak sweep clean. No docker compose config was run; Docker not required (pure module + synthetic
  tests).
- **Next recommended slice:** **Slice 126 — Wire Numeric Extraction Mapper into Advisory Artifact** (advisory, non-blocking)
  unless a real-material spike first surfaces an unsupported method (then a bounded recompute-method extension comes first).
- **Out of scope / unchanged:** no judge scoring, `overall_10`, repair loop, or blocking gate; no `quality_judge.py`,
  `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`; no generation/prompt/provider/request-schema/render/export/OCR/
  table/visual/Ask Guide change. **Committed `13a7ef6`, merged + pushed to `chrome-renderer-v1`.**

---

## Slice 124 — **Quality Safety Numeric Extraction Contract Design**, on `slice124-quality-safety-numeric-extraction-contract-design`. **Committed `242d580`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 123 was committed as `624a70e`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 123 validated the advisory `quality_safety_unified_qa.json` artifact path
  and recorded, in closed vocabulary, `structural_coverage_leg_status=covered`,
  `numeric_fact_sheet_extraction_leg_status=not_covered`, `judge_ready=false`, `repair_ready=false`,
  `next_step=numeric_extraction_design`. No docker compose config was run, and the Slice 60 trace stash remains parked and
  untouched.
- **Scope:** design-first, bounded. Define the safe structured **numeric extraction contract** needed to feed the existing
  pure fact-sheet producer (`quality_safety_fact_sheet_producer`) and recompute verifier
  (`quality_safety_recompute_verifier`) so the numeric leg can be closed in a later slice — closing the Slice 123 gap. No
  production wiring; docs plus one pure synthetic contract harness.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `?? docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`, `?? test_scripts/test_quality_safety_numeric_extraction_contract.py`.
  No production code changed.
- **Contract (new doc `docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`):** one *numeric extraction record* shape mapping
  onto the producer's `computation_records[]` (recomputable) / `numeric_observations[]` (bare) lists. Allowed fields only
  (`id`, `concept_id`, `label`, `fact_type=numeric`, `value`, `unit`, `provenance`, `confidence`, `source_ref`, `page_ref`,
  `computation.method`, `computation.inputs`, `tolerance`, `warnings`); a closed **forbidden-field** list (`raw_text`,
  `source_text`, `guide_text`, `ocr_text`, `table_cells`, `captions`, `formulas_as_text`, `evidence_quotes`, `filenames`,
  `basenames`, `paths`, `urls`, `provider_payloads`, `runtime_traces`, `raw_exceptions`). Supported-first methods are exactly
  the verifier's `SUPPORTED_METHODS` (`weighted_gini`, `total_error`, `amount_of_say`, `softmax`, `cross_entropy`,
  `forward_pass`), each with a schema-level synthetic input shape (no private formulas/examples).
- **Representability matrix outcome:** all three archetypes (`legacy_confused_wrong_case`,
  `single_confident_wrong_numeric_case`, `clean_real_case`) are `numeric_fact_representable=true`,
  `recompute_blocker_possible=true`, `leak_blocker_possible=true`, `artifact_path_ready=false`, sharing one
  `missing_piece=numeric_extraction`. No schema-level method/source blocker found.
- **Next recommended slice:** **Slice 125 — Pure Numeric Extraction Record Mapper v1** (pure/unwired contract→bundle mapper,
  synthetic tests only; no OCR/table parsing, no source/`clean.md` reads, no providers/judge/repair). The contract found no
  blocker, so Slice 125 is recommended; if a later real-material spike surfaces an unsupported method, recommend a bounded
  recompute-method extension first instead.
- **judge_ready=false, repair_ready=false** — unchanged; the numeric leg stays `not_covered` until a real artifact path proves
  it with safe structured concept/fact data. This slice does **not** claim numeric coverage.
- **No-leak boundary:** closed-vocabulary docs only; the contract doc and synthetic harness use synthetic ids/labels/methods
  and illustrative synthetic numbers (with a synthetic canary smuggled into a forbidden field to prove it is stripped). No
  real source/guide/OCR/table/caption text, copied formulas, numeric prose, evidence quotes, filenames, basenames, paths,
  URLs, raw artifact JSON, runtime outputs, screenshots, or provider payloads.
- **Validation:** numeric extraction contract harness 27 passed; fact sheet 61 passed; recompute verifier 99 passed;
  real-disaster harness 41 passed; `compileall api pipeline test_scripts` OK; `git diff --check` clean; no-leak sweep clean. No
  docker compose config was run; Docker not required (docs + pure synthetic test only).
- **Out of scope / unchanged:** no production mapper wired, no OCR/table parsing, no source/`clean.md` read, no routes, no
  frontend change, no generic artifact selector row, no generation/prompt/provider/request-schema/render/export/OCR/table/
  visual/Ask Guide change, no judge scoring, `overall_10`, repair loop, or blocking gate; no `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`. **Committed `242d580`, merged + pushed to `chrome-renderer-v1`.**

---

## Slice 123 — **Real-Disaster E2E with Advisory Coverage Leg**, on `slice123-quality-safety-real-disaster-e2e-coverage-leg`. **Committed `624a70e`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 122 was committed as `979bb4e`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 122 wired the Slice 121 structural-coverage adapter into the advisory
  `quality_safety_unified_qa.json` artifact; no docker compose config was run, and the Slice 60 trace stash remains parked and
  untouched.
- **Scope:** operator-/harness-validation slice. Validate the *actual* advisory job-artifact path against the real-disaster
  case archetypes after Slice 122 coverage wiring, and record — in closed vocabulary only — which legs are now covered. No
  production code change: one synthetic-safe harness plus docs only.
- **Files changed:** `M docs/CURRENT_TASK.md`, `M docs/DECISIONS.md`, `M docs/NEXT_CHAT_HANDOFF.md`,
  `M docs/QUALITY_SAFETY_E2E_VALIDATION.md`, `M docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md`,
  `?? test_scripts/validate_quality_safety_real_disaster_e2e.py`. No `quality_safety_job_artifact.py` /
  `run_markdown_job.py` / `api/server.py` / frontend change was needed (the artifact path was not broken).
- **Track A (synthetic-safe, artifact-path-exercised):** new harness
  `test_scripts/validate_quality_safety_real_disaster_e2e.py` (41 checks, all passed) drives the real builder and the real
  production hook `_write_quality_safety_unified_qa` with synthetic-safe inputs across three archetypes:
  - `clean_real_case` → `unified_status=passed`, `shippable=true`, `safety_floor_green=true`, coverage present.
  - `single_confident_wrong_numeric_case` → `unified_status=failed`, `shippable=false`, recompute blocker present (proves the
    verifier works *when* a concept/fact bundle is fed).
  - `legacy_confused_wrong_case` (production-shaped: structural coverage present, **no** concept/fact bundle) → recompute
    stays `unknown`/missing, no recompute blocker, `safety_floor_green=false`, `shippable=true` only because nothing failed.
    This is the honest gap.
- **Track B (real private operator material):** no real-material generation was run in this automated session (provider/model/
  cloud calls are not permitted here), so runtime fields are recorded honestly as `not_observed`; the structurally guaranteed
  invariants (`advisory_non_blocking=true`, `structural_coverage_leg_covered=true`,
  `numeric_fact_sheet_extraction_leg_covered=false`) are recorded directly. Records live in
  `docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md` → Slice 123.
- **Coverage-leg status:** **structural coverage leg = covered** (wired into the artifact; present with safe metadata,
  `skipped` otherwise). **Numeric fact-sheet extraction leg = NOT covered** through the production hook — that hook supplies
  only `candidate_markdown` + structural-coverage siblings and never produces a concept/fact bundle, so recompute stays
  `component_missing`. Structural coverage never invented numerics (`numeric_observation_count=0`) and never upgraded
  `shippable` / `safety_floor_green`.
- **judge_ready=false, repair_ready=false.** Next slice should be **numeric extraction design** (a safe concept/fact
  extraction-to-fact-sheet mapper feeding the existing recompute verifier) — *not* a judge baseline or repair, because the
  numeric leg is still uncovered end-to-end.
- **Validation:** real-disaster harness 41 passed; E2E artifact harness 36 passed; job artifact 276 passed; adapter 705
  passed; unified QA 73 passed; `compileall api pipeline test_scripts` OK; `git diff --check` clean; no-leak sweep clean. No
  docker compose config was run; Docker not required (docs + synthetic harness only).
- **Out of scope / unchanged:** no numeric extraction implemented, no extraction-to-fact-sheet mapper, no
  `quality_safety_job_artifact.py` / `run_markdown_job.py` / `api/server.py` change, no routes, no frontend change, no generic
  artifact selector row, no generation/prompt/provider/request-schema/render/export/OCR/table/visual/Ask Guide change, no
  judge scoring, `overall_10`, repair loop, or blocking gate; no `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or
  `quality.jsonl`. **Committed `624a70e`, merged + pushed to `chrome-renderer-v1`.**

---

## Slice 122 — **Wire Coverage Adapter into Advisory Artifact**, on `slice122-wire-quality-safety-coverage-adapter-advisory-artifact`. **Committed `979bb4e`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 121 was committed as `b382eed`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 121 added the pure/unwired `quality_safety_extraction_coverage_bundle`
  adapter; no production behavior changed, no docker compose config was run, and the Slice 60 trace stash remains parked and
  untouched.
- **Scope:** wire the Slice 121 structural-coverage adapter into the existing advisory `quality_safety_unified_qa.json` job
  artifact path. Still **advisory / non-blocking only**. The artifact now carries safe structural coverage metadata when the
  job already produced the safe sibling JSON artifacts, and degrades to a closed `skipped` coverage leg with the
  `extraction_coverage_missing` warning when none exist. The deterministic QA behavior, `shippable`, and `safety_floor_green`
  are unchanged.
- **Wiring (`pipeline/quality_safety_job_artifact.py`):** `build_quality_safety_job_artifact_payload` /
  `write_quality_safety_job_artifact` gained optional `source_coverage_report`, `extraction_metadata`,
  `visual_inclusion_plan`, `table_candidates_manifest`, `table_reconstruction_policy` args (all default `None`). They feed
  **only** `build_quality_safety_extraction_coverage_bundle_from_artifacts` (Slice 121). When all are absent the bundle is the
  empty `skipped` bundle and `extraction_coverage_missing` is recorded; on degraded/failed adapter output
  `extraction_coverage_degraded` is recorded. The coverage bundle **never** feeds the concept/fact fact-sheet producer and is
  never numeric recompute evidence.
- **Production reader (`pipeline/run_markdown_job.py`):** `_write_quality_safety_unified_qa` now reads the already-produced,
  already-sanitized sibling JSON artifacts read-only via a new `_read_job_json_artifact(job, attr)` helper
  (`source_coverage_report.json`, `extraction_metadata.json`, `visual_inclusion_plan.json`,
  `table_candidates_manifest.json`, `table_reconstruction_policy.json`) and passes the dicts into the builder. Read-only,
  never raises; the hardcoded write-failure fallback dict gained matching closed `extraction_coverage_*` fields for shape
  stability.
- **Safe fields added to `quality_safety_unified_qa.json`:** `extraction_coverage_status`
  (`ok|warning|skipped|partial|failed`), `extraction_coverage_summary` (closed counts only: `source_count`, `page_count`,
  `selected_page_count|null`, `visual_count`, `table_count`, `coverage_item_count`, `numeric_observation_count=0`), and
  `extraction_coverage_bundle` (the Slice 121 `quality_safety_extraction_coverage_bundle`). All existing fields (`status`,
  `shippable`, `safety_floor_green`, `component_statuses`, `deterministic_axes_0_5`, `summary`, `blocking_failures`,
  `warnings`, `quality_safety_unified_qa`) are unchanged. `kind` stays `quality_safety_job_artifact`; `artifact_name` stays
  `quality_safety_unified_qa.json`; `advisory=true` and `source=job_runtime` unchanged.
- **Numeric / recompute leg remains NOT covered** — structural coverage is not numeric recompute evidence.
  `numeric_observations=[]` and `numeric_observation_count=0` always; the fact-sheet / recompute / canonical components stay
  honestly `component_missing` / `skipped` when no concept/fact extraction bundle exists. Structural coverage never upgrades
  `shippable` / `safety_floor_green` (proven by test).
- **Frontend unchanged:** the Slice 119 normalizer is allowlist-based and ignores the new top-level fields; its verify
  harness still passes. No route, no UI, no generic artifact selector changed.
- **Validation:** job artifact 276 (was 216); adapter 705; producer 182; unified QA 73; fact sheet 61; recompute verifier 99;
  E2E artifact harness 36 (was 22); `compileall api pipeline test_scripts` OK; `git diff --check` clean; frontend
  guide-quality-panel verify OK. No docker compose config was run.
- **Out of scope / unchanged:** no new routes, no `api/server.py` change, no frontend change, no generic artifact selector
  row, no generation/prompt/provider/request-schema/render/export/OCR/table/visual/Ask Guide behavior change, no judge
  scoring, `overall_10`, repair loop, or blocking gate; no `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or
  `quality.jsonl`. **Committed `979bb4e`, merged + pushed to `chrome-renderer-v1`.**

---

## Slice 121 — **Pure Extraction-Bundle Adapter v1**, on `slice121-quality-safety-extraction-bundle-adapter-v1`. **Committed `b382eed`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 120 was committed as `06deb50`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 120 validated the advisory Quality Safety visible path (production build →
  exact-name fetch → read-only UI display) on a synthetic-safe sample and inspected the existing extraction/page metadata; no
  production behavior changed, no docker compose config was run, and the Slice 60 trace stash remains parked and untouched.
- **Scope:** Slice 121 adds a **pure, unwired** adapter (`pipeline/quality_safety_extraction_bundle_adapter.py`) that maps
  already-sanitized structural extraction/coverage artifacts into a normalized **structural coverage bundle** the Slice 117
  fact-sheet producer can be handed later. Built directly from Slice 120 findings. The adapter reads only caller-supplied
  in-memory dicts, scans no directories, reads no job folders / source documents / `clean.md`, writes no artifacts, calls no
  providers/models/cloud, imports stdlib only, never raises on malformed input, and never mutates caller input.
- **Output shape (closed tokens / counts only):** `version=1`, `kind=quality_safety_extraction_coverage_bundle`,
  `status ∈ {ok,warning,skipped,partial,failed}`, `source_quality ∈ {synthetic,runtime_structural,unknown}`, a `summary`
  (`source_count`, `page_count`, `selected_page_count|null`, `visual_count`, `table_count`, `coverage_item_count`,
  `numeric_observation_count=0`), `coverage_records[]` (synthetic `qs_extract_NNNN` ids, sanitized `source_ref`/`page_ref`
  tokens, closed `record_type`/`status`, count-only `counts`, closed `warnings`), `numeric_observations=[]` always, and a
  closed top-level `warnings` list.
- **Preferred input:** the already-sanitized **source coverage report** (keyed by an integer source ordinal, not a basename)
  is preferred over the raw, name-bearing extraction metadata artifact; visual-inclusion-plan / table-candidate-manifest /
  table-reconstruction-policy counts are read structurally. **Source basenames, filenames, paths, URLs, titles, OCR/table/
  caption text, formulas, evidence quotes, provider payloads, and traces are never read or echoed.**
- **Numeric observations intentionally not recovered in v1:** Slice 120 found `numeric_observation_recoverable=no`, so the
  adapter never fabricates numeric observations — `numeric_observations=[]` and `numeric_observation_count=0` always, with the
  closed `numeric_observations_not_recoverable` warning when coverage records exist.
- **Distinct kind decision:** the Slice 117 producer already owns `kind=quality_safety_extraction_bundle` (a *concept/fact*
  bundle) and a `normalize_quality_safety_extraction_bundle` function; to avoid a name/shape collision this v1 adapter emits
  the distinct `quality_safety_extraction_coverage_bundle` kind and `..._coverage_bundle...` function names. Passing the
  coverage bundle to the producer degrades safely to an empty/partial fact sheet (no `concepts`) — proven by test.
- **Validation:** `test_scripts/test_quality_safety_extraction_bundle_adapter.py` (705/705) plus regression of the producer
  (182), job artifact (216), fact sheet (61), recompute verifier (99), and unified QA (73). `python -m compileall api
  pipeline test_scripts` OK; `git diff --check` clean. No Docker required (pure/unwired); no docker compose config was run.
- **Production wiring deferred to Slice 122.** No-leak boundary: closed vocabulary, counts only, synthetic ids — no raw text,
  names, basenames, paths, URLs, OCR/table/caption text, formulas, snippets, evidence quotes, provider payloads, or traces.
- **Out of scope / unchanged:** no production job wiring, no `quality_safety_job_artifact.py` / `run_markdown_job.py` /
  `api/server.py` change, no new routes, no frontend change, no generic artifact selector row, no generation/prompt/provider/
  request-schema/render/export/OCR/table/visual/Ask Guide behavior change, no judge scoring, `overall_10`, repair loop, or
  blocking gate; no `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. **Committed `b382eed`,
  merged + pushed to `chrome-renderer-v1`.**

---

## Slice 120 — **Quality Safety Advisory Artifact E2E + Extraction Metadata Inspection**, on `slice120-quality-safety-e2e-and-extraction-metadata-inspection`. **Committed `06deb50`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 119 was committed as `91a1134`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 119 surfaced `quality_safety_unified_qa.json` in the existing Guide Quality
  advisory UI as a read-only, non-blocking section behind a strict display allowlist; no backend artifact generation, API,
  generation/prompt/provider/request-schema/render/export/OCR/table/visual/Ask Guide behavior changed, no docker compose
  config was run, and the Slice 60 trace stash remains parked and untouched.
- **Scope:** Slice 120 is docs/operator-validation first. It validates the full advisory Quality Safety visible path
  (production build → exact-name fetch → read-only UI display) on a synthetic-safe sample, and inspects the existing
  extraction/page metadata to discover what safe structured metadata exists today before designing the extraction-bundle
  adapter. One synthetic-safe validation harness was added; no production behavior changed.
- **Advisory artifact E2E (closed tokens):** `status=ok`, `sample_type=synthetic_safe`, `artifact_produced=true`,
  `artifact_name=quality_safety_unified_qa_json`, `exact_name_fetch=ok`, `ui_display=ok`,
  `missing_extraction_state=component_missing_skipped`, `artifact_advisory_non_blocking=true`,
  `job_status_changed_by_quality_safety=false`, `provider_calls=false`, `judge_calls=false`, `repair_calls=false`,
  `no_leak_sweep=clean`, `private_material_committed=false`, `raw_runtime_output_committed=false`.
- **Extraction metadata inspection (closed tokens):** `status=ok`, `inspection_source=code_and_synthetic_runtime`,
  `extraction_artifact_present=true`, `page_metadata_present=true`, `visual_metadata_present=true`,
  `table_metadata_present=true`, `page_ref_shape=mixed`, `leaf_count_recoverable=yes`,
  `numeric_observation_recoverable=no`, `extraction_leg_design_status=partial`. Candidate fields are closed structural
  tokens only (page/coverage/visual/table counts, extraction mode/status, source/page refs); raw text, filenames, paths,
  URLs, OCR/table/caption text, formulas, evidence quotes, provider payloads, and traces are excluded.
- **Adapter design status:** **partial** — a structural-count / coverage-presence adapter leg is feasible now (prefer the
  already-sanitized source coverage report, which is keyed by a source ref, not a basename); a numeric-observation/recompute
  leg is not recoverable from today's metadata. Production wiring is deferred to Slice 122; the pure adapter is the next
  slice (Slice 121).
- **No-leak boundary:** committed records use closed vocabulary only. Full detail in `docs/QUALITY_SAFETY_E2E_VALIDATION.md`.
- **Out of scope / unchanged:** no adapter implementation, no production wiring, no API route change, no frontend display
  change, no generic artifact selector row, no generation/prompt/provider/request-schema/render/export/OCR/table/visual/Ask
  Guide behavior change, no judge scoring, `overall_10`, repair loop, or blocking gate; no `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`. **Committed `06deb50`, merged + pushed to `chrome-renderer-v1`.**

---

## Slice 119 — **Quality Safety Advisory UI Display v1**, on `slice119-quality-safety-advisory-ui-display-v1`. **Committed `91a1134`, merged + pushed to `chrome-renderer-v1`.**

- **Scope:** Slice 119 surfaces `quality_safety_unified_qa.json` in the existing Guide Quality advisory UI. The section is
  read-only and advisory, degrades calmly when the artifact is missing, and uses a strict frontend display allowlist.
- **Display boundary:** the UI shows only closed tokens, booleans/unknowns, non-negative counts, component statuses,
  deterministic 0-5 axes, capped blocking rows, and capped warning tokens. It does not display raw guide/source text,
  snippets, formulas, OCR/table/caption text, paths, filenames, URLs, evidence quotes, provider payloads, runtime traces, or
  raw nested child report fields outside the allowlist.
- **Out of scope / unchanged:** no backend artifact generation change, no API behavior change, no generation/prompt/provider
  request/request-schema/job-success/render/export/OCR/table/visual/Ask Guide behavior change, no judge scoring,
  `overall_10`, repair loop, blocking gate, `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`.

---

## Slice 118 — **Quality Safety Advisory Job Artifact v1**, on `slice118-quality-safety-advisory-job-artifact-v1`. **Committed `c9644aa`, merged + pushed to `chrome-renderer-v1`.**

- **Scope:** Slice 118 adds advisory production job artifact generation for the exact artifact name
  `quality_safety_unified_qa.json`. The helper builds a safe payload from existing deterministic Quality Safety modules and
  the job pipeline writes it after `clean.md` exists and before rendering. It is reached by exact filename only, not generic
  artifact rows or export selectors.
- **Advisory contract:** the artifact never blocks job success, never changes job status, never rewrites or repairs guide
  content, never changes prompts or provider requests, never changes request schemas, never calls providers/models/cloud, and
  never changes render/export/OCR/table/visual/Ask Guide behavior. It does not add judge scoring, `overall_10`,
  `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`.
- **Payload shape:** `version=1`, `kind=quality_safety_job_artifact`, `artifact_name=quality_safety_unified_qa.json`,
  `advisory=true`, `source=job_runtime`, top-level `status`, `shippable`, `safety_floor_green`, `component_statuses`,
  `deterministic_axes_0_5`, safe count-only `summary`, closed-token `blocking_failures`, closed-token `warnings`, and nested
  `quality_safety_unified_qa`.
- **Missing extraction behavior:** production does not invent fact sheets. It uses `clean.md`/candidate markdown only as input
  to the leak scanner and does not store it. Structured extraction bundles are used only if a safe bundle exists. When no
  extraction bundle exists, the artifact records closed `component_missing` / skipped state for fact-sheet, recompute, and
  canonical components while still running safe leak scanning against `clean.md` when available.
- **Safety boundary:** the artifact stores only closed tokens/counts and safe deterministic report structures. It does not
  store raw guide/source text, snippets, formulas, paths, filenames, URLs, OCR/table/caption text, evidence quotes, provider
  payloads, runtime traces, real PDFs/images/DOCX/PDF/ZIPs, generated guide artifacts, eval JSON outputs, or private
  material. Tests use synthetic bundles/canaries only. No frontend/UI change was added.

---

## Slice 117 — **Quality Safety Fact-Sheet Producer v1**, on `slice117-quality-safety-fact-sheet-producer-v1`. **Committed `e389697`, merged + pushed to `chrome-renderer-v1`.**

- **Scope:** Slice 117 added `pipeline/quality_safety_fact_sheet_producer.py`, a pure/unwired stdlib helper that maps
  sanitized structured extraction bundles into the Slice 110 `quality_safety_fact_sheet` schema. It is not a PDF parser, does
  not read source documents or `clean.md`, does not scan directories, does not write job artifacts or runtime JSON, and is not
  wired into production jobs.
- **Synthetic integration proof:** `test_scripts/test_quality_safety_fact_sheet_producer.py` proves extraction bundle →
  producer fact sheet → recompute verifier → unified QA. A synthetic single-confident-wrong `weighted_gini` fact is blocked by
  recompute without leak or contradiction, and a synthetic clean computation-only extraction bundle passes unified QA with
  `shippable=true` and `safety_floor_green=true`.

---

## Slice 116 — **Quality Safety Leak Scanner Clean-Case False-Positive Hardening**, on `slice116-quality-safety-leak-false-positive-hardening`. **Committed `0bef077`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 115 was committed as `92a4fb2`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 115 was docs/operator-validation only. It recorded the red deterministic
  safety-floor validation honestly: `clean_real_case=false_positive_leak`,
  `failure_category=clean_case_false_positive`, and `extraction_leg_covered=false`. It added no code, tests, runtime
  outputs, real fixtures, generated guides, provider/model/cloud call, judge, `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`; no docker compose config was run; the parked Slice 60 trace stash remains
  untouched.
- **Scope:** Slice 116 is a targeted leak-scanner hardening slice. It changes only the unwired offline leak scanner,
  synthetic leak-scanner tests, and closed-vocabulary docs. It fixes the clean-case false-positive blocker found by Slice 115
  before fact-sheet production, production job wiring, judge scoring, prompt tuning, or repair work.
- **Root cause tokens:** `leak_boundary_false_positive`; `technical_weight_term_false_positive`. Fixed leak signatures now
  use boundary-safe matching for word/phrase signals instead of substring-prone matching around technical terms. The
  structural guards also keep practice/mock/self-test/quiz/check-yourself headings, pedagogical `Why?` headings, formal
  `Assumption` headings, source/page references, and formal `Probable Cause` labels out of leak results unless actual
  uncertainty wording is present.
- **Tests:** `test_scripts/test_quality_safety_leak_scanner.py` adds synthetic boundary tests proving `weight`, `weights`,
  `weighted`, `weighted_gini`, `weighted error`, `await`, `awaiting`, `straightforward`, `actual`, `factual`, and clean
  weighted technical prose produce zero leaks, while the major fixed leak signatures and structural uncertainty markers still
  trigger. Recompute priority over canonical remains covered.
- **Closed-vocabulary operator revalidation:** `legacy_confused_wrong_case` remains detected with
  `detected=true`, `shippable=false`, `safety_floor_green=false`, and blockers including `leak`, `numeric`, and
  `recompute`. `single_confident_wrong_numeric_case` remains detected with
  `blocking_checks=[recompute:weighted_gini]`, `contradiction_required=false`, and `leak_required=false`.
  `clean_real_case` now passes with `clean_case_passed=true`, `unified_status=passed`, `shippable=true`,
  `safety_floor_green=true`, and `blocking_checks=[]`. `extraction_leg_covered=false` remains recorded because fact-sheet
  production is still not built.
- **Out of scope / unchanged:** no fact-sheet producer, production runtime wiring, app route, UI/export selector, generic
  artifact entry, reference-anchored LLM judge, `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, `quality.jsonl`,
  `overall_10`, prompt tuning, repair/rewrite/regeneration, live generation, provider/model/cloud call, Docker config,
  generation/prompt/request/API/UI/render/export/OCR/table/visual/Ask Guide behavior change, or Chandra gate change.
- **Safety boundary:** docs and tests use synthetic fixtures/canaries or closed-vocabulary outcomes only. No real PDFs,
  images, DOCX/PDF/ZIPs, runtime artifacts, generated guides, eval outputs, real source/reference filenames, uploaded
  quality-spec filenames, evidence quotes, snippets, OCR/table/caption text, paths, URLs, image bytes, formulas copied from
  private/generated material, provider payloads, or runtime output JSON were added. Slice 116 was committed as `0bef077`,
  merged, and pushed before Slice 117.

---

## Slice 115 — **Quality Safety Real-Disaster Operator Validation**, on `slice115-quality-safety-real-disaster-operator-validation`. **Committed `92a4fb2`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 114 was committed as `f3693dc`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 114 added only the unwired deterministic unified-QA report layer and
  synthetic tests. It computed `shippable` / `safety_floor_green`, emitted deterministic axes
  (`accuracy`, `coverage`, `solved_problem`, `clarity`), did not compute `overall_10`, did not add judge scoring, did not
  tune prompts, did not repair/rewrite/regenerate, changed no API/frontend/generation/prompt/request/render/export/OCR/
  table/visual/Ask Guide behavior, added no provider/model/cloud call, committed no real fixtures/runtime outputs/generated
  guides/binary artifacts, and did not add Claude's `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or
  `quality.jsonl`. No docker compose config was run. The parked Slice 60 trace stash remains untouched.
- **Scope:** Slice 115 is a docs-only/offline operator validation slice. It validates the completed deterministic safety
  detectors from Slices 108-114 using private local operator material and a hand-built local fact sheet. It validates
  recompute/leak/unified-QA behavior only; `extraction_leg_covered=false`. It does not validate extraction-to-fact-sheet
  production behavior, and a green detector result would not mean the production app catches the failure end-to-end yet. It
  adds no production code, no tests, no CLI scripts, no runtime artifact writers, no JSONL logs, no generated outputs, no
  judge, no repair loop, and no fact-sheet producer.
- **Contract inspection:** `weighted_gini` is supported by the fact-sheet/recompute contract. The fact-sheet `computation`
  field can encode safe structured `{method, inputs}` data for leaf/group counts. The recompute report exposes only safe
  fact ids, closed check/status/warning tokens, and numeric supplied/recomputed/tolerance values. Unified QA aggregates
  Layer-1, recompute, canonical, and leak blocking failures without raw snippets. The leak scanner can attach verification
  context through safe fact ids or labels only.
- **Closed-vocabulary operator results:** `legacy_confused_wrong_case` failed as expected with
  `blocking_checks=[layer1:leaked_reasoning, layer1:numeric_correctness, recompute:weighted_gini, leak:quality_safety_leak_scan]`
  and `expected_legacy_failure_detected=true`. `single_confident_wrong_numeric_case` failed as expected with
  `blocking_checks=[recompute:weighted_gini]`, `single_wrong_value_only=true`, `contradiction_required=false`,
  `leak_required=false`, and `failure_category=confident_wrong_value_detected`. `clean_real_case` did **not** pass:
  `unified_status=failed`, `shippable=false`, `safety_floor_green=false`,
  `blocking_checks=[layer1:leaked_reasoning, leak:quality_safety_leak_scan]`, `clean_case_passed=false`,
  `failure_category=clean_case_false_positive`, `component_miss_tokens=[false_positive_leak]`. All records use
  `input_kind=private_local_operator_material`, `fact_sheet_kind=hand_built_local`, `extraction_leg_covered=false`,
  `raw_text_committed=false`, `raw_paths_committed=false`, `runtime_outputs_committed=false`, `provider_calls=false`, and
  `judge_calls=false`.
- **Out of scope / unchanged:** no reference-anchored LLM judge, `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, `quality.jsonl`, `overall_10`, prompt tuning, repair/rewrite/regeneration, fact-sheet producer,
  production runtime wiring, app route, UI/export selector, generic artifact entry, What the Lecturer Skipped, Active Recall,
  Memory Hooks, Practical Example Generator, Solve Path Generator, question-bank coverage, generation/prompt/request/API/UI/
  render/export/OCR/table/visual/Ask Guide behavior change, provider/model/cloud call, live generation, or Docker config.
- **Safety boundary:** the runtime validation read private local material, but committed docs use closed-vocabulary outcomes
  only. No real PDFs/images/DOCX/ZIPs, runtime artifacts, generated guides, eval outputs, real source/reference filenames,
  uploaded quality-spec filenames, evidence quotes, snippets, OCR/table/caption text, paths, URLs, image bytes, formulas
  copied from private/generated material, provider payloads, or runtime output JSON were added. Slice 115 was committed as
  `92a4fb2`, merged, and pushed before Slice 116.

---

## Slice 114 — **Quality Safety Unified QA Artifact v1**, on `slice114-quality-safety-unified-qa-artifact-v1`. **Committed `f3693dc`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 113 was committed as `4b002c6`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 113 added only the unwired verifier-coupled leak scanner and synthetic
  tests. It remained leak-scanner-only/unwired, did not repair/rewrite/regenerate/tune prompts, changed no API/frontend/
  generation/prompt/request/render/export/OCR/table/visual/Ask Guide behavior, added no provider/model/cloud call, committed
  no real fixtures/runtime outputs/generated guides/binary artifacts, and did not add Claude's `quality_judge.py`,
  `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. No docker compose config was run. The parked Slice 60 trace
  stash remains untouched.
- **Scope:** Slice 114 adds the unified deterministic Quality Safety QA report layer. It aggregates Layer-1 eval,
  recompute verifier, canonical fallback, and verifier-coupled leak scanner outputs into one pure report that determines
  `shippable` / `safety_floor_green` for the deterministic safety floor.
- **New pure module:** `pipeline/quality_safety_unified_qa.py` exposes `build_quality_safety_unified_qa_report(...)`,
  `aggregate_quality_safety_reports(...)`, `build_quality_safety_deterministic_axes(...)`, and the optional offline
  `run_quality_safety_unified_floor(...)`. It is stdlib plus Quality Safety modules only, reads no source documents or
  `clean.md`, writes no artifacts, calls no providers/models/cloud services, imports no FastAPI/frontend/OCR/render/job
  runtime code, never raises on malformed input, and returns deterministic JSON-serializable dicts with closed vocabularies.
- **Aggregation behavior:** normalized blocking failures keep only component, closed check id, status, severity, safe fact
  ids, closed verification status, and closed warning tokens. Ordering is deterministic: Layer-1, recompute, canonical,
  leak. Recompute failures remain primary; canonical fallback can verify only when recompute did not verify/fail; leak
  failures preserve safe recompute/canonical context.
- **Safety floor behavior:** `shippable` is true only for passed/warning reports with zero blocking failures.
  `safety_floor_green` additionally requires no missing/malformed component warnings, a passed/skipped leak component, no
  numeric blocking failures, no failed recompute/canonical mismatch, and no Layer-1 blocking failures. This is the
  deterministic floor only.
- **Deterministic axes:** the report emits `deterministic_axes_0_5` for later judge injection: `accuracy`, `coverage`,
  `solved_problem`, and `clarity`. It does not compute `overall_10`, judge scores, or any 9.5/9.0 quality score.
- **Tests:** `test_scripts/test_quality_safety_unified_qa.py` uses synthetic data and hostile synthetic canaries only. It
  covers empty/malformed behavior, all-green floor, Layer-1/recompute/canonical/leak blocking, warning-only reports,
  deterministic axes, Slices 108-113 integration, recompute-first/canonical-second/leak-context behavior, Slice 109 seed
  fixture gates, no-leak sweeps, and import hygiene (73 checks pass). Both Slice 109 synthetic seed fixtures pass the green
  safety-floor test with all-green synthetic candidates; the ambiguous synthetic leaked/mismatched candidate fails as
  expected.
- **Out of scope / unchanged:** no reference-anchored LLM judge, `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`,
  `quality.jsonl`, `overall_10`, prompt tuning, repair/rewrite/regeneration, production runtime wiring, app route, UI/export
  selector, generic artifact entry, What the Lecturer Skipped, Active Recall, Memory Hooks, Practical Example Generator,
  Solve Path Generator, question-bank coverage, generation/prompt/request/API/UI/render/export/OCR/table/visual/Ask Guide
  behavior change, provider/model/cloud call, or Docker config. Docker validation is optional/not required because this is
  offline/unified-QA-only.
- **Safety boundary:** only synthetic fixtures/content were used. No real PDFs/images/DOCX/ZIPs, runtime artifacts,
  generated guides, eval outputs, real source/reference filenames, uploaded quality-spec filenames, evidence quotes,
  snippets, OCR/table/caption text, paths, URLs, image bytes, formulas copied from private/generated material, or provider
  payloads were added. Slice 114 was committed as `f3693dc`, merged, and pushed before Slice 115.

---

## Slice 113 — **Quality Safety Verifier-Coupled Leak Scanner v1**, on `slice113-quality-safety-verifier-coupled-leak-scanner-v1`. **Committed `4b002c6`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 112 was committed as `1606896`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 112 added only the unwired canonical matcher and synthetic tests. It was
  matcher-only/unwired, preserved recompute priority, never overrode recompute-verified facts, never hid recompute-failed
  facts, changed no API/frontend/generation/prompt/request/render/export/OCR/table/visual/Ask Guide behavior, added no
  provider/model/cloud call, committed no real fixtures/runtime outputs/generated guides/binary artifacts, and did not add
  Claude's `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`. No docker compose config was run.
  The parked Slice 60 trace stash remains untouched.
- **Scope:** Slice 113 adds the unwired Quality Safety **verifier-coupled leak scanner**. It scans caller-supplied candidate
  Markdown only, detects deterministic leak/uncertainty signals, and records safe verification-status context beside leak
  hits for future repair safety. It does not repair, rewrite, regenerate, tune prompts, decide the unified QA artifact, or
  claim shippable status. Slice 114 will aggregate the unified QA artifact later.
- **New pure module:** `pipeline/quality_safety_leak_scanner.py` is stdlib-only plus the Slice 110 fact-sheet normalizer.
  It exposes `scan_quality_safety_leaks(...)`, `build_quality_safety_leak_report(...)`, and
  `extract_quality_safety_verification_context(...)`. It reads no source documents or `clean.md`, writes no artifacts, calls
  no providers/models/cloud services, imports no FastAPI/frontend/OCR/render/job runtime code, never raises on malformed
  input, and returns deterministic JSON-serializable dicts with closed-vocabulary tokens only.
- **Leak detection:** fixed case-insensitive signatures cover reasoning/uncertainty phrases, trust/inference language,
  TODO/TBD/FIXME markers, `[insert ...]` / `[fill ...]` / `[unknown ...]` placeholders, `= ?` / `≈ ?`, formula-like
  question marks, and empty `answer:` / `final answer:` / `solution:` blocks. False-positive resistance keeps normal
  mock/practice/self-test/quiz/check-yourself question headings, committed pedagogical `Why?` headings, formal
  `Assumption` headings, and source/page refs from being flagged as structural uncertainty.
- **Verifier coupling:** safe fact ids/labels from the normalized fact sheet can attach nearby leaks to fact ids. Recompute
  report statuses have priority: recompute verified ⇒ `verified_recompute`; recompute failed ⇒ `failed_recompute`.
  Canonical verified/mismatch applies only when recompute did not verify/fail that fact. Missing reports stay `unknown`.
  The scanner never fuzzy-matches long concept text, uses no embeddings/LLM, and never stores raw line text, snippets,
  formulas copied from private/generated material, OCR/table/caption text, paths, URLs, provider payloads, or evidence
  quotes.
- **Report / blocking behavior:** reports use `kind:"quality_safety_leak_report"`, version 1, closed statuses
  (`passed/warning/failed/skipped/partial`), closed leak kinds/severities/verification statuses/warnings, summary counts,
  `blocking`, `leaks`, and closed-token `blocking_failures`. Any blocking leak fails; warning-only leaks warn; clean
  candidates pass; missing/malformed candidate markdown skips/degrades safely.
- **Tests:** `test_scripts/test_quality_safety_leak_scanner.py` uses synthetic data and synthetic hostile canaries only. It
  covers empty/malformed input, all major leak families, false-positive resistance, conservative fact attachment, recompute
  and canonical verifier coupling, recompute-first priority, report shape/status/capping, Slice 110/111/112 integration,
  Slice 109 synthetic seed fixture integration, no-leak sweeps, and import hygiene (181 checks pass).
- **Out of scope / unchanged:** no production artifact writer, app route, UI/export selector, generic artifact entry, LLM
  judge, `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, `quality.jsonl`, unified QA artifact, repair loop, What
  the Lecturer Skipped, Active Recall, Memory Hooks, Practical Example Generator, Solve Path Generator, question-bank
  coverage, generation/prompt/request/API/UI/render/export/OCR/table/visual/Ask Guide behavior change, provider/model/cloud
  call, or Docker config. Docker validation is optional/not required because this is offline/leak-scanner-only.
- **Safety boundary:** only synthetic fixtures/content were used. No real PDFs/images/DOCX/ZIPs, runtime artifacts,
  generated guides, eval outputs, real source/reference filenames, uploaded quality-spec filenames, evidence quotes,
  snippets, OCR/table/caption text, paths, URLs, image bytes, formulas copied from private/generated material, or provider
  payloads were added. Slice 113 was committed as `4b002c6`, merged, and pushed before Slice 114.

---

## Slice 112 — **Quality Safety Canonical Fixture Matcher v1**, on `slice112-quality-safety-canonical-matcher-v1`. **Committed `1606896`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 111 was committed as `9d2050b`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 111 added only the unwired Quality Safety recompute verifier and synthetic
  tests. It changed no API route, frontend, generation prompt, request schema, Builder UI, Ask Guide, render/export/OCR/
  table/visual behavior, runtime artifact writer, provider/model/cloud integration, or Docker config. `pipeline/math_verifier.py`
  was not modified. The parked Slice 60 trace stash remains untouched.
- **Scope:** Slice 112 adds the unwired Quality Safety **canonical fixture matcher** as step 2 of the runtime hierarchy only:
  recompute from structured computation inputs remains the primary truth path; canonical fixture matching is fallback-only;
  otherwise facts remain unverified. The matcher is not wired into production artifacts, routes, jobs, prompts, exports, UI,
  renderers, OCR, table/visual handling, Ask Guide, leak gates, or repair loops.
- **New pure module:** `pipeline/quality_safety_canonical_matcher.py` is stdlib-only plus the Slice 110 fact-sheet normalizer.
  It exposes `normalize_quality_safety_canonical_fixture(...)`, `match_quality_safety_canonical_facts(...)`, and
  `build_quality_safety_canonical_match_report(...)`. It reads only caller-supplied dicts, writes no artifacts, reads no
  source documents or `clean.md`, calls no providers/models/cloud services, never raises, never mutates caller input, and
  returns deterministic JSON-serializable dicts with closed-vocabulary tokens only.
- **Canonical fixture schema:** normalized fixtures use `kind:"quality_safety_canonical_fixture"`, version 1, safe
  `lecture_id`, closed `source_quality`, bounded canonical facts, safe ids/labels/match keys/aliases, finite numeric
  values/tolerances, `provenance:"canonical_fixture"`, and closed warnings. Fixture data is synthetic only; no real golden
  corpus, source/reference filenames, uploaded quality-spec filenames, evidence quotes, snippets, formulas copied from
  private/generated material, OCR/table/caption text, paths, URLs, image bytes, or provider payloads are added.
- **Fallback-only behavior:** the matcher normalizes the Slice 110 fact sheet and canonical fixture, reads the optional
  Slice 111 recompute report by safe fact id, and canonical-matches only numeric facts that are not already recompute-verified
  or recompute-failed. Recompute-verified facts are skipped and cannot be overridden. Recompute-failed facts are skipped and
  cannot be hidden. Missing/unsupported/malformed recompute results may use exact canonical fallback when lecture id matches,
  type matches, id/label/match key/explicit safe alias matches, and the supplied numeric value is within tolerance. No fuzzy
  matching, embeddings, raw guide-text inference, provider calls, or LLM judge is added.
- **Report / blocking behavior:** reports use `kind:"quality_safety_canonical_match_report"`, version 1, closed statuses
  (`passed/warning/failed/skipped/partial`), closed check ids/statuses/warnings, summary counts, `blocking:true`, and
  `blocking_failures`. Canonical mismatch for an eligible fallback fact is blocking; missing canonical entries and lecture
  mismatches are warnings/skips, not blocking; recompute pass/fail skips do not add new blocking failures. Checks store only
  safe ids/labels/match keys, numeric supplied/canonical/tolerance values, and closed warnings.
- **Tests:** `test_scripts/test_quality_safety_canonical_matcher.py` uses synthetic data and synthetic hostile canaries only.
  It covers empty/malformed behavior, fixture normalization, exact fallback pass/fail, explicit alias matching, recompute
  priority, lecture mismatch, type behavior, report shape/status/blocking counts, Slice 110 + 111 integration, Slice 109
  synthetic seed fixture integration, no-leak sweep, and import hygiene (159 checks pass).
- **Out of scope / unchanged:** no production artifact writer, app route, UI/export selector, generic artifact list entry,
  LLM judge, quality_judge.py, nn3.json, judge_response_nn3.json, quality.jsonl, What the Lecturer Skipped, Active Recall,
  Memory Hooks, Practical Example Generator, Solve Path Generator, question-bank coverage, production leak gate, repair loop,
  generation/prompt/request/API/UI/render/export/OCR/table/visual/Ask Guide behavior change, provider/model/cloud call, or
  `pipeline/math_verifier.py` change. Docker validation is optional/not required because this is offline/matcher-only.
- **Safety boundary:** only synthetic fixtures/content were used. No real PDFs/images/DOCX/ZIPs, runtime artifacts,
  generated guides, eval outputs, real source/reference filenames, uploaded quality-spec filenames, evidence quotes,
  snippets, OCR/table/caption text, paths, URLs, image bytes, formulas copied from private/generated material, or provider
  payloads were added. Slice 112 was committed as `1606896`, merged, and pushed before Slice 113.

---

## Slice 111 — **Quality Safety Recompute Verifier v1**, on `slice111-quality-safety-recompute-verifier-v1`. **Committed `9d2050b`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 110 was committed as `ff7c971`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 110 added only the unwired Quality Safety fact-record/fact-sheet schema and
  its synthetic tests. It changed no API route, frontend, generation prompt, request schema, Builder UI, Ask Guide,
  render/export/OCR/table/visual behavior, runtime artifact writer, provider/model/cloud integration, or Docker config. The
  parked Slice 60 trace stash remains untouched.
- **Scope:** Slice 111 adds the unwired Quality Safety **recompute verifier** — the primary numeric truth path. It consumes
  the Slice 110 fact-sheet/fact-record schema and verifies numeric facts by recomputing their value from structured
  computation inputs. Canonical fixture matching stays fallback-only and is deferred to Slice 112; this slice implements
  recompute (step 1 of the runtime hierarchy) only.
- **Existing `math_verifier.py` inspected, kept separate.** `pipeline/math_verifier.py` (Slice 18/21) is text/guide-oriented:
  it AST-walks generated Markdown/plain text for inline numeric *claims* (e.g. `2 + 3 = 5`) and produces
  `math_verification.json`-style output. It is **not** structured-fact-oriented. The Quality Safety verifier instead consumes
  structured `{method, inputs}` records, so per the slice rules it is a **separate module** with no reuse and no change to
  `math_verifier.py` or its existing behavior. The new verifier is **not** routed through production math verification.
- **New pure module:** `pipeline/quality_safety_recompute_verifier.py` is stdlib-only (plus the Slice 110
  `quality_safety_fact_sheet` import) and exposes `recompute_quality_safety_fact(...)`,
  `verify_quality_safety_fact_sheet(...)`, and `build_quality_safety_recompute_report(...)`. It reads only caller-supplied
  dicts, writes no artifacts, reads no source documents or `clean.md`, calls no providers/models/cloud services, never
  raises, and returns deterministic JSON-serializable dicts with closed-vocabulary tokens only.
- **Supported recompute methods (v1):** `weighted_gini`, `total_error`, `amount_of_say`, `softmax` (numerically stable),
  `cross_entropy`, and `forward_pass` (linear, plus tested `relu`/`sigmoid`). Method tolerances: weighted_gini 0.01,
  total_error 0.005, amount_of_say 0.02, softmax 0.01, cross_entropy 0.01, forward_pass 0.01 (fallback default 1e-6,
  cap 1.0). Tolerance precedence: explicit arg > computation/fact metadata (if safe) > method default.
- **Fact-sheet integration behavior:** only numeric facts with a supported computation method are recomputed. Match within
  tolerance ⇒ `verified` (an `unverified` fact may upgrade to `computed`); mismatch ⇒ `failed` + blocking failure;
  missing/unsupported/malformed computation ⇒ `unverified` warning (not blocking); non-numeric facts ⇒ `not_applicable`
  (never failed); `canonical_fixture` facts without computation are **not** recomputed here (Slice 112). Caller input is never
  mutated and Slice 110 fact `verification_status` values stay in `{verified, unverified, failed}`.
- **Report schema / blocking:** `kind:"quality_safety_recompute_report"`, version 1, `blocking:true`, closed statuses
  (`passed/warning/failed/skipped/partial`), summary counts, closed check ids/statuses, `blocking_failures`, and closed
  warning tokens. Only recomputed mismatch (or an invalid supplied value on a claimed verified/computed fact) is a blocking
  failure; unsupported method and malformed inputs are non-blocking warnings. Checks store only safe fact id, check id,
  status, numeric supplied/recomputed/tolerance values, and closed warnings — never snippets, formula strings, raw inputs,
  paths, URLs, provider payloads, OCR/table/caption text, or raw exception text.
- **Tests:** `test_scripts/test_quality_safety_recompute_verifier.py` uses synthetic data and synthetic hostile canaries
  only. It covers empty/malformed behavior, each supported method (pass/mismatch/degrade), provenance/status transitions,
  Slice 110 schema integration (no mutation, deterministic), Slice 109 synthetic fixture recompute, report shape/status
  transitions, a no-leak sweep, and import hygiene (99 checks pass).
- **Out of scope / unchanged:** no canonical fixture matcher, no production leak gate, no repair loop, no runtime artifact
  writer, no app route, no UI/export selector, no LLM judge, no What the Lecturer Skipped / Active Recall / other picked
  study-intelligence features, no generation/prompt/request/API/UI/render/export/OCR/table/visual/Ask Guide behavior change,
  and no provider/model/cloud calls. Docker validation is optional/not required because this is offline/verifier-only.
- **Safety boundary:** only synthetic fixtures/content were used. No real PDFs/images/DOCX/ZIPs, runtime artifacts, generated
  guides, eval outputs, source/reference filenames, uploaded quality-spec filenames, evidence quotes, snippets,
  OCR/table/caption text, paths, URLs, image bytes, formulas copied from private/generated material, or provider payloads
  were added. Slice 111 was committed as `9d2050b`, merged, and pushed before Slice 112.

---

## Slice 110 — **Quality Safety Fact-Sheet Schema v1**, on `slice110-quality-safety-factsheet-schema-v1`. **Committed `ff7c971`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 109 was committed as `2bbd644`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 109 added sanitized synthetic seed fixture specs and the forward-fixed
  numeric contradiction hardening after pushed Slice 108. It changed no API route, frontend, generation prompt, request
  schema, Builder UI, Ask Guide, render/export/OCR/table/visual behavior, runtime artifact writer, provider/model/cloud
  integration, or Docker config. The parked Slice 60 trace stash remains untouched.
- **Scope:** Slice 110 adds the unwired Quality Safety fact-record/fact-sheet schema only. The schema is the contract later
  recompute verification, canonical fallback, leak scanner coupling, and unified QA artifacts will read.
- **New pure module:** `pipeline/quality_safety_fact_sheet.py` is stdlib-only and exposes
  `normalize_quality_safety_fact_record(...)`, `normalize_quality_safety_fact_sheet(...)`,
  `validate_quality_safety_fact_sheet(...)`, and `build_empty_quality_safety_fact_sheet(...)`. It reads only caller-supplied
  dicts, writes no artifacts, reads no source documents or `clean.md`, calls no providers/models/cloud services, and returns
  deterministic JSON-serializable dicts only.
- **Fact records:** normalize to closed fact types (`numeric`, `categorical`, `string`, `table`), provenance
  (`extracted_high`, `computed`, `canonical_fixture`, `unverified`), verification status (`verified`, `unverified`,
  `failed`), confidence (`high`, `medium`, `low`, `unsupported`), safe ids/source refs, bounded values, optional safe
  computation metadata, and closed warnings only. Unknown enums and malformed values downgrade safely; numeric facts with
  invalid/non-finite values become `null` and unverified.
- **Fact sheets:** normalize to `kind:"quality_safety_fact_sheet"`, version 1, closed status/source-quality values, safe
  lecture id, bounded concepts/facts/teaching notes/worked examples, non-negative summary counts, and closed warnings only.
  `max_items` caps concepts, facts, notes, and examples and marks the sheet `partial` with `max_items_reached`.
- **Tests:** `test_scripts/test_quality_safety_fact_sheet.py` uses only synthetic data and synthetic hostile canaries. It
  covers empty/malformed behavior, computed/unverified/canonical/failed facts, enum downgrades, id/source-ref hardening,
  string/table/note/example hygiene, bounds, deterministic serialization, synthetic seed-fixture integration, no-leak sweep,
  and import hygiene.
- **Out of scope / unchanged:** no recompute verifier, no canonical fixture matcher, no production leak gate, no repair loop,
  no runtime fact-sheet artifact writer, no app route, no UI/export selector, no LLM judge scoring, no What the Lecturer
  Skipped mode, no Active Recall or other picked study-intelligence features, no generation/prompt/request/API/UI/render/
  export/OCR/table/visual/Ask Guide behavior change, and no provider/model/cloud calls. Docker validation is optional/not
  required because this is offline/schema-only and changes no production runtime behavior.
- **Safety boundary:** only synthetic fixtures/content were used. No real PDFs/images/DOCX/ZIPs, runtime artifacts,
  generated guides, eval outputs, source/reference filenames, uploaded quality-spec filenames, evidence quotes, snippets,
  OCR/table/caption text, paths, URLs, image bytes, formulas copied from private/generated material, or provider payloads
  were added. Slice 110 was committed as `ff7c971`, merged, and pushed before Slice 111.

---

## Slice 109 — **Quality Safety Seed Fixtures v1**, on `slice109-quality-safety-seed-fixtures-v1`. **Committed `2bbd644`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 108 was committed as `133e8e0`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 108 added only the offline deterministic eval harness skeleton and its
  synthetic tests. It changed no API route, frontend, generation prompt, request schema, Builder UI, Ask Guide,
  render/export/OCR/table/visual behavior, runtime artifact writer, provider/model/cloud integration, or Docker config. The
  parked Slice 60 trace stash remains untouched.
- **Scope:** Slice 109 adds sanitized synthetic seed fixture specs for the Quality Safety eval harness. This is **not** the
  real golden corpus. Future operator-approved non-private golden data still needs an explicit safe fixture policy.
- **Seed fixtures:** `test_scripts/fixtures/quality_safety/clean_neural_networks_synthetic.json` and
  `test_scripts/fixtures/quality_safety/ambiguous_ensemble_synthetic.json` exercise two Layer-1 deterministic roles only:
  one clean math/NN-like source and one ambiguous ensemble/tree-like source. They contain synthetic ids/topics/numeric
  targets/minimum question counts/tier targets only.
- **Harness hardening:** after review, the numeric check now treats two or more distinct values printed for the same fixture
  label as a blocking `numeric_correctness` failure, even when one value matches the expected target. Reports still contain
  only closed statuses/warnings, numeric values/counts, and sanitized fixture labels; they do not store candidate snippets.
- **Tests:** `test_scripts/test_quality_safety_seed_fixtures.py` validates fixture existence, JSON-only/no-binary contents,
  forbidden field absence, loader compatibility, synthetic pass/fail candidates, deterministic serialization, no-leak sweeps,
  and import hygiene. `test_scripts/test_quality_safety_eval_harness.py` adds a small seed-fixture consumption check and
  numeric contradiction coverage.
- **Safety boundary:** no source deck PDFs, reference guides, generated guides, runtime eval outputs, evidence quotes, private
  filenames, real source/reference/uploaded quality-spec filenames, real source text, OCR text, table text, captions, paths,
  URLs, image data, provider payloads, or formulas copied from private/generated material were added. The fixtures are for
  Layer-1 deterministic harness testing only.
- **Out of scope / unchanged:** no LLM judge scoring, no fact-sheet schema, no canonical fixture matcher, no recompute
  verifier, no production leak gate, no repair loop, no What the Lecturer Skipped mode, no Active Recall or other picked
  study-intelligence features, no frontend UI, no API routes, no generic artifact list entries, no export selectors, no
  generation/prompt/request/API/UI/render/export/OCR/table/visual/Ask Guide behavior change, and no provider/model/cloud
  calls. Docker validation is optional/not required for this offline test-fixture slice unless production runtime changes are
  made. Chandra remains blocked by its own live-validation gate. Slice 109 was committed, merged, and pushed before
  Slice 110.

---

## Slice 108 — **Quality Safety Eval Harness Skeleton**, on `slice108-quality-safety-eval-harness-skeleton`. **Committed `133e8e0`, merged + pushed to `chrome-renderer-v1`.**

- **Part 0 completed:** Slice 107 was committed as `03cacc7`, fast-forward merged to trunk `chrome-renderer-v1`, and pushed
  with a normal `git push` (no force-push). Slice 107 changed docs plus frontend Guide Quality panel/display/verifier files
  only; no backend production-code files changed. It changed no generation, prompt, provider/model/cloud, render/export,
  OCR/table/visual, request schema, API, or Ask Guide behavior. The parked Slice 60 trace stash remains untouched.
- **Phase:** this starts the new **Quality Safety Unit** phase. The external eval/fact-sheet plan called this a revised Slice
  106, but this repo already has Slices 106 and 107, so the work is tracked here as Slice 108.
- **Goal:** add a deterministic, offline, synthetic eval harness skeleton that measures candidate guide Markdown without
  changing generation. The harness loads small synthetic fixture specs, runs Layer-1 deterministic checks, and builds an
  in-memory regression record shape suitable for future JSONL output.
- **New module:** `pipeline/quality_safety_eval_harness.py` is pure stdlib-only and exposes
  `load_quality_safety_fixture_spec(data)`, `run_quality_safety_layer1_checks(candidate_markdown, fixture_spec, *,
  max_items=None)`, `build_quality_safety_regression_record(...)`, and `run_quality_safety_eval(...)`. It persists no runtime
  eval outputs by default and does not write files.
- **Synthetic fixture behavior:** the loader tolerates malformed input, normalizes counts defensively, degrades unknown
  `source_quality` to a closed token, drops invalid expected topics/numeric targets/tier targets with closed warnings, and
  never copies arbitrary raw source strings into warnings. Fixture identifiers are sanitized synthetic ids only.
- **Layer-1 checks:** deterministic checks cover leaked reasoning signals, numeric correctness against fixture values,
  shallow worked-answer completeness, expected-topic coverage, and mock/practice question count. Reports contain only closed
  check ids/statuses/warnings, counts, numeric floats, and safe synthetic fixture labels/topics; no candidate snippets are
  stored. Leaked reasoning, numeric mismatch, and unresolved worked-answer signals are blocking failures; coverage below 90%
  and too few mock questions are advisory warnings in this skeleton.
- **Regression record:** `build_quality_safety_regression_record(...)` returns a deterministic
  `quality_safety_regression_record` dict with metadata defaults, `overall_10:null` unless supplied, shippability separate
  from score, safe Layer-1 data, warnings/blocking failures, optional deltas, and regression detection for shippable
  true→false, newly failed blocking checks, or an `overall_10` drop greater than 0.3.
- **Tests:** `test_scripts/test_quality_safety_eval_harness.py` uses only synthetic fixtures and synthetic hostile canaries.
  It covers loader degradation/determinism/no-leak behavior, all five Layer-1 checks, regression record semantics, wrapper
  output, no-leak sweep, and import hygiene. No real deck/reference filenames, uploaded quality-spec filenames, private
  content, snippets, paths, OCR text, table text, captions, formulas, provider payloads, generated guides, runtime artifacts,
  or eval outputs are added.
- **Out of scope / unchanged:** no What the Lecturer Skipped mode, no Active Recall, no Memory Hooks, no Practical Example
  Generator, no Solve Path Generator, no question-bank coverage, no fact-sheet schema, no canonical fixtures, no recompute
  verifier, no production leak gate, no repair loop, no Layer-2 LLM judge, no real golden fixtures, no frontend UI, no API
  routes, no generic artifact list entries, no export selectors, no provider/model/cloud calls, no generation prompts, no
  request schemas, no Builder UI, no Ask Guide, no OCR/PDF/image/table/render/export behavior, and no direct `clean.md`
  writes. Chandra remains blocked by its own live-validation gate. Slice 108 was committed, merged, and pushed before
  Slice 109.

---

## Slice 107 — **Guide Quality closeout panel rubric + operator checklist**, on `slice107-guide-quality-closeout`. **Committed `03cacc7`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 106 was committed `d34b39e`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`** in Part 0. Push was a
  normal `git push` (no force-push). Slice 106 had no production-code changes: docs plus the synthetic release-validation
  harness only. The guide-quality release validation remains synthetic/validation-only, and the parked Slice 60 stash remains
  untouched.
- **Goal:** close the guide-quality correction phase before returning to picked study-intelligence features by surfacing the
  existing `guide_quality_rubric_score.json` artifact in the JobDetails Guide Quality panel and adding a safe operator
  validation checklist/report format.
- **Frontend:** `frontend/src/guideQualityDisplay.js` now exports `GUIDE_QUALITY_RUBRIC_SCORE_ARTIFACT` and
  `summarizeGuideQualityRubricScore(rubric)`. The summarizer tolerates missing/malformed input, never throws, copies no raw
  artifact strings, and emits only non-negative summary counts plus closed axis `kind`/`status`/`confidence`/`score`
  values. Unknown axis kinds are dropped; hostile statuses/confidence values degrade to closed fallbacks. Unsupported
  semantic axes remain `unknown` / `score:null` / `unsupported`.
- **Panel behavior:** `GuideQualityPanel.jsx` fetches `guide_quality_rubric_score.json` independently alongside
  `guide_quality_qa_gate.json`, `guide_quality_contract_lint.json`, `guide_quality_report_v2.json`, `math_verification.json`,
  and `source_coverage_report.json`. Missing/404/non-JSON/network failures degrade to calm Not available states. A new
  Rubric score section shows artifact status, `blocking:false`/advisory semantics, score totals, axis counts, and closed
  axis rows only. The panel Artifacts section includes the fixed exact-name label **Guide Quality Rubric Score**.
- **Operator checklist:** `docs/GUIDE_QUALITY_OPERATOR_VALIDATION.md` defines a docs-only, closed-vocabulary manual-review
  report format that explicitly forbids guide/source snippets, formulas, filenames, paths, OCR/table/caption text, images,
  provider material, uploaded quality-spec evidence quotes, and uploaded quality-spec filenames. Current recorded status is
  `guide_quality_operator_validation: not_run` with `reason: non_private_operator_sample_not_supplied`; no completed operator
  validation was fabricated.
- **Validation performed:** frontend `node scripts/verify-guide-quality-panel.mjs`,
  `node scripts/verify-material-coverage-final-panel.mjs`, `node scripts/verify-dual-explanation-mode-ui.mjs`,
  `npm run build`, and `npm test` passed. Backend `python test_scripts/test_guide_quality_release_validation.py`
  (234/0), `test_guide_quality_rubric_score.py` (63/0), `test_guide_quality_qa_gate.py` (177/0),
  `test_guide_quality_contract_lint.py` (83/0), `test_guide_quality_report_v2.py` (100/0),
  `test_source_coverage_report.py` (59/0), `python -m compileall api pipeline`, and `git diff --check` passed. Docker
  validation passed: `docker compose build`, `docker compose up -d --force-recreate`, health `{"ok":true}`,
  `smoke_release.py` 29/0/0, and `docker compose ps` healthy. Optional exact-name fetch of
  `guide_quality_rubric_score.json` on a smoke-generated synthetic job returned HTTP 200 / `application/json`,
  `kind:"guide_quality_rubric_score"`, `blocking:false`, and no leak-pattern hits.
- **Out of scope / unchanged:** no generation behavior; no prompt behavior; no LLM/provider/model/cloud calls; no backend
  artifact-generation behavior; no existing artifact schema changes; no render/export behavior; no Ask Guide behavior; no
  extraction/OCR/PDF/image handling; no table reconstruction; no figure insertion/material selection/visual filtering.
  Chandra remains blocked by its own live-validation gate. Slice 107 was committed, merged, and pushed before Slice 108.

---

## Slice 106 — **Guide Quality release validation**, on `slice106-guide-quality-release-validation`. **Committed `d34b39e`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 105 was committed `10041b7`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`** (Guide Quality
  Rubric Score v1). Slice 106 branched from fresh trunk after that push.
- **Goal:** add a deterministic, synthetic, validation-only release checkpoint proving the guide-quality correction phase
  coheres end to end. It validates the Slice 102 prompt contract and contract lint, Slice 103 QA gate, Slice 104 frontend
  panel model, Slice 105 rubric score, exact-name artifact route coverage where host dependencies allow, composition order,
  advisory-only/blocking semantics, unsupported semantic axes, determinism, input non-mutation, and a broad no-leak sweep.
- **New harness — `test_scripts/test_guide_quality_release_validation.py`**. It exercises real helpers directly:
  `build_guide_quality_prompt_contract`, `run_llm_job._build_guide_quality_prompt_block_safely`,
  `build_guide_quality_contract_lint_report`, `build_source_coverage_report`, `build_guide_quality_report_v2`,
  `build_guide_quality_qa_gate`, `build_guide_quality_rubric_score`, and the existing Node
  `frontend/scripts/verify-guide-quality-panel.mjs`. It uses synthetic canaries only; no real PDFs/images/DOCX/ZIPs,
  runtime artifacts, generated guides, eval JSONs, traces, private filenames, private source text, or quality-spec evidence
  are persisted.
- **Validation performed before commit:** `python test_scripts/test_guide_quality_release_validation.py` passed (234/0;
  exact-name route coverage skipped with a closed host-dependency reason in that environment). Existing backend regression,
  frontend verifier scripts, `npm run build`, `npm test`, `compileall`, `git diff --check`, and Docker smoke passed. Slice 106
  remained validation-only and added no production behavior.

---

## Slice 105 — **Guide Quality Rubric Score v1**, on `slice105-guide-quality-rubric-score-v1`. **Committed `10041b7`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 104 was committed `d5acd12`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`** (JobDetails Guide
  Quality panel v1). Slice 105 branches from fresh trunk after that push.
- **Goal:** add a deterministic, sanitized, advisory scorecard artifact named `guide_quality_rubric_score.json`. It converts
  existing guide-quality signals into closed rubric axes without pretending to semantically grade what deterministic artifacts
  cannot prove. It is advisory only: `blocking:false`, never rejects/regenerates, never changes job status, never blocks
  render/export, and never changes prompts/generation/Ask Guide/UI.
- **New module — `pipeline/guide_quality_rubric_score.py`** (pure, stdlib-only). `build_guide_quality_rubric_score(...)`
  consumes only already-sanitized sibling artifacts where present: `guide_quality_qa_gate.json`,
  `guide_quality_contract_lint.json`, `guide_quality_report_v2.json`, `source_coverage_report.json`,
  `math_verification.json`, `validation.json`, `visual_inclusion_plan.json`, `table_candidates_manifest.json`, and
  `table_reconstruction_policy.json`. It does **not** read `clean.md`, source documents, PDFs/images/OCR, captions, table
  text, or provider payloads. It copies no strings from input artifacts except closed tokens used for decisions, and emits
  only closed axis ids/statuses/reasons/confidence values, counts, booleans, `null`, and closed warnings.
- **Rubric axes:** `reasoning_hygiene`, `required_structure`, `exam_focus`, `reference_tables`, `math_verification`,
  `source_coverage`, `coverage_signal_alignment`, `visual_table_honesty`, `beginner_scaffolding`, and
  `worked_example_completeness`. Deterministic axes score 0/1/2 from safe counts/statuses only. Unsupported semantic axes
  stay `unknown` with `score:null`, `confidence:"unsupported"`, and
  `reason:"semantic_axis_not_deterministically_measured"` instead of fake scoring.
- **Artifact wiring:** `Job.guide_quality_rubric_score_json`, `_write_guide_quality_rubric_score(job)` in
  `pipeline/run_markdown_job.py` immediately after the Slice 103 QA gate writer, and exact-name `_artifact_path` support in
  `api/server.py` returning `application/json`. It is deliberately **not** added to generic `ARTIFACTS`, generic UI rows,
  export selectors, or the Slice 104 Guide Quality panel.
- **Validation:** `test_guide_quality_rubric_score.py` (63) passes; existing `test_guide_quality_qa_gate.py` (177),
  `test_guide_quality_contract_lint.py` (83), `test_guide_quality_report_v2.py` (100), `test_source_coverage_report.py` (59),
  and `test_full_material_coverage_release_validation.py` (86) pass; `compileall api pipeline` and `git diff --check` clean.
  Frontend regression passed (`verify-guide-quality-panel.mjs`, `verify-material-coverage-final-panel.mjs`,
  `npm run build`, `npm test`). Docker validation passed (`docker compose build`, `docker compose up -d --force-recreate`,
  health, `smoke_release.py` 29/0/0, `docker compose ps` healthy). Live synthetic paste-job check confirmed
  `guide_quality_rubric_score.json` is produced, exact-name fetchable with HTTP 200 / `application/json`, `blocking:false`,
  and no synthetic snippet/formula/path/filename/data-URI/base64 leak.
- **Out of scope / unchanged:** no prompt/generation change; no LLM/provider/model/cloud call; no Chandra/Mistral/Gemini; no
  OCR/PDF/image inspection; no table reconstruction; no render/export change; no frontend UI change; no Ask Guide change; no
  auto-reject/regenerate; no direct `clean.md` read or write. Chandra remains blocked by its own live-validation gate.
  The artifact remains advisory-only (`blocking:false`) and no generation/prompt/render/export/Ask Guide behavior changed.

---

## Slice 104 — **JobDetails Guide Quality panel v1**, on `slice104-jobdetails-guide-quality-panel`. **Committed `d5acd12`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 103 was committed `71f5f8c`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`** (flag-only Guide
  Quality QA Gate). Slice 104 branches from that fresh trunk.
- **Goal:** surface the existing guide-quality signals in JobDetails as a safe, **read-only / advisory** panel. It is a
  frontend *visibility* slice — **not** a replacement for evaluation. It only displays the deterministic/advisory signals that
  already exist (Slices 102/103 + the older coverage/math measurements). It changes **no** generation behavior.
- **New helper module — `frontend/src/guideQualityDisplay.js`** (pure, React-free). `summarizeGuideQualityQaGate(...)`,
  `summarizeGuideQualityContractLint(...)`, `summarizeMathVerificationArtifact(...)` (counts only — never claim text /
  formulas / values), and the composite `summarizeGuideQualityPanelModel({ qaGate, contractLint, guideQualityReportV2,
  mathVerification, sourceCoverageReport })`. It **reuses** the already-shipped `summarizeSourceCoverage` /
  `summarizeGuideQualityReportV2` + exact-name constants from `materialCoverageDisplay.js` (single source of truth). Like the
  backend gate it copies **no string** out of any artifact — only known **non-negative integer counts** and **closed status /
  kind tokens** validated against in-module allow-lists — so no excerpt / phrase / heading / formula / value / table / caption
  / OCR / filename / path / source title / image-asset ref / URL / token / raw error can reach the display model, even from a
  hostile canary. Deterministic; never throws.
- **New component — `frontend/src/components/GuideQualityPanel.jsx`**, wired into `RecentJobsPanel.jsx` JobDetails drawer as a
  new **Guide Quality** tab (after Material Coverage). It fetches the five exact-name artifacts on **independent** lifecycles
  (`guide_quality_qa_gate.json`, `guide_quality_contract_lint.json`, `guide_quality_report_v2.json`, `math_verification.json`,
  `source_coverage_report.json`); a 404 → "Not available", any other error / non-JSON → calm "Unavailable" (no raw error text
  or URLs). Older jobs without the artifacts still render. Six sections: Overall QA Gate (status + counts + advisory copy +
  `blocking:false`), Prompt Contract Lint, Math Verification (counts only), Coverage & Completeness, Quality Checks
  (closed-kind chips from the gate), and Artifacts (fixed exact-name links; missing → "Not available").
- **Validated:** new `verify-guide-quality-panel.mjs` passes (all-missing/valid/malformed/hostile-canary/determinism); existing
  `verify-material-coverage-final-panel.mjs`, `verify-dual-explanation-mode-ui.mjs`, `verify-material-page-selections-ui.mjs`
  re-run green; FE build + `npm test` green; backend `test_guide_quality_qa_gate.py` (177), `test_guide_quality_contract_lint.py`
  (83), `test_guide_quality_report_v2.py` (100), `test_source_coverage_report.py` (59), `test_full_material_coverage_release_validation.py`
  (86) all green; `compileall` clean; Docker `smoke_release.py` **29/0/0** (smoke does not deep-exercise the new panel — relied
  on the focused FE verify script + backend artifact tests).
- **Out of scope / unchanged:** no generation/prompt change; no LLM/provider/model/cloud call; no Chandra/Mistral/Gemini; no
  OCR/PDF/image inspection; no table reconstruction; no render/export change; no figure-insertion / material-selection /
  visual-filter change; no Ask Guide change; no auto-reject/regenerate; no direct `clean.md` write. Chandra remains blocked by
  its own live-validation gate.

---

## Slice 103 — **Guide Quality QA Gate v1**, on `slice103-guide-quality-qa-gate-v1`. **Committed `71f5f8c`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 102 was committed `815a0dc`, fast-forward merged, and pushed to trunk `chrome-renderer-v1`** (guide-quality prompt
  contract + flag-only contract lint). Slice 103 branches from that fresh trunk.
- **Goal:** add a higher-level *advisory* QA gate that combines the already-sanitized quality signals into one closed
  pass/warning/skipped summary. It addresses the off-repo quality spec's post-generation QA/coverage-gate direction while
  staying **flag-only / advisory** in v1 — it does **not** reject, regenerate, block render/export, or fail jobs. `blocking`
  is always `False`.
- **New module — `pipeline/guide_quality_qa_gate.py`** (pure, stdlib-only). `build_guide_quality_qa_gate(...)` consumes only
  already-sanitized input dicts — the guide-quality **contract lint** (Slice 102), the **guide quality report v2** (Slice 96),
  the **source coverage report** (Slice 77), and the existing numeric **math verification** (Slice 21; `math_verification.json`)
  — plus an optional KaTeX `math_validation` fallback. It emits five closed-kind checks: `reasoning_leak`,
  `required_structure` (comprehensive only; `not_applicable` otherwise), `math_verification`, `source_coverage`, and
  `quality_report_v2`. Gate `status` rolls up to `passed` / `warning` / `skipped` (all signals unknown) / `partial`
  (defensive `max_items` cap). It **copies no string** out of its inputs — only known **integer counts** and **closed
  tokens**; every instruction string is a fixed in-module constant, so no excerpt/phrase/heading/formula/value/table/
  caption/OCR/filename/path/raw-error can pass through even from a hostile canary.
- **Math handling — summarized, not rerun.** The existing math verifier already runs and writes `math_verification.json`
  earlier in the pipeline; the gate only reads its `report.summary` (`total`/`mismatch`): a non-zero `mismatch` → `warning`,
  zero claims → `not_applicable`, clean → `passed`. A missing/skipped math artifact → `unknown` with the closed warning
  `math_verification_artifact_missing` (the KaTeX `validation.json` is consulted only as a presence-only fallback). No
  formulas/numbers/raw verifier errors are ever stored. Deeper pipeline-ordering integration was **not** needed — math
  verification is written before the gate, so math status is available, not forced to `unknown`.
- **Artifact wiring:** `Job.guide_quality_qa_gate_json`, a `_write_guide_quality_qa_gate(job)` writer in `run_markdown_job.py`
  (after the contract lint + math verification; reads the manifest to infer `comprehensive` and the four sibling artifacts via
  the existing `_read_json_artifact`), and an exact-name `_artifact_path` route → `application/json`. Reached only by exact
  filename — deliberately **not** in the generic ARTIFACTS list / generic UI rows / export selectors. No UI added.
- **Validation:** new `test_guide_quality_qa_gate.py` (177) passes; Slice 102 prompt/lint/integration + report-v2 + coverage
  tests re-run green; FE verify scripts + build + `npm test` green (no FE change); `compileall` clean; Docker
  `smoke_release.py` 29/0/0; **live paste-job check** confirmed `guide_quality_qa_gate.json` is written, exact-name fetchable
  (HTTP 200, `application/json`), `status:passed`, `blocking:false`, counts-only, no leaks.
- **Out of scope / unchanged:** no LLM/provider/model/cloud call; no provider/model change; no new product features (no
  active recall / mnemonics / question banks / solve paths); no prompt change (Slice 102 left intact); no Chandra/Mistral/
  Gemini; no OCR/PDF/image inspection; no table reconstruction; no render/export change; no figure-insertion / material-
  selection / visual-filter change; no Ask Guide change; no auto-reject/regenerate; no direct `clean.md` write. Chandra
  remains blocked by its own live-validation gate. **Slice 103 is NOT committed.**

---

## Slice 102 — **Claude-quality guide prompt contract v1**, on `slice102-guide-quality-prompt-contract`. **Committed `815a0dc`, merged + pushed to `chrome-renderer-v1`.**

- **New phase:** before returning to the picked study features (active recall etc.), this slice starts a guide-*quality*
  correction phase. Its product requirements come from an off-repo quality-fix spec; only the **distilled rules** are
  implemented here — no real spec evidence quotes, source deck names, or output/reference filenames are copied into the
  repo.
- **Slice 101 was committed `89f8532`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1`** (~100 MB
  attachment support; it also folded in two unrelated provider-icon SVG refreshes per operator instruction). Slice 102
  branches from that fresh trunk.
- **Central prompt contract — `pipeline/guide_quality_prompt_contract.py`** (pure, stdlib-only). `build_guide_quality_prompt_contract(...)`
  turns safe request signals (depth axis / difficulty / generator preset / style id / mode, or an explicit `comprehensive`
  bool) into a deterministic, leak-free `prompt_block`. **Core rules always** (resolve ambiguity silently; no leaked
  reasoning/uncertainty; no fabricated math; finish examples; show all arithmetic; numeric consistency; define terms;
  per-formula plain-English; intuition blocks; reference data in labelled tables; confident exam-tutor voice; ⚠️ EXAM
  ALERT). The **full 13-section structural contract** is added only for comprehensive/long guides. `infer_comprehensive(...)`:
  `quick` depth opts out, `exhaustive` opts in, else any longform/exam generator preset (`claude_exam/review/cram`) or
  longform style (`master_longform`, `exam_cram`) opts in; explicit bool overrides.
- **Integration — `pipeline/run_llm_job.py`:** a single new `_build_guide_quality_prompt_block_safely(...)` appends the block
  under one `## Guide Quality Contract` heading, composing **after** the dual-explanation block so its precedence note is the
  last thing the model reads. Applies to every guide generation (paste + attachments); on any failure it returns `""` so the
  prompt stays byte-identical. **Ask Guide is untouched.**
- **Styles/presets unchanged.** The contract is kept **centralized** (one appended block) rather than duplicating long text
  across `prompts/study_guide_prompts.md` / styles; the block states it **takes precedence over weaker/conflicting**
  instructions, so it overrides without editing the load-bearing preset bodies.
- **Flag-only lint — `pipeline/guide_quality_contract_lint.py`** (pure, stdlib-only). `build_guide_quality_contract_lint_report(clean_markdown, comprehensive=..., max_items=...)`
  scans the generated `clean.md` for **safe COUNTS ONLY**: reasoning-leak signatures, required-section presence (by heading
  alias), exam-alert and table counts, and shallow **deferred** worked-example / arithmetic / consistency signals (deep math
  verification stays with the existing math verifier; deep numeric-consistency is deferred and never stores a value). It
  stores **no excerpt** — never the matched phrase, heading text, table content, formula, example, or any number. Checks use
  closed `check_id`/`kind`/`status`. It is **flag-only**: it never rejects/regenerates and never fails the job.
- **Artifact wiring:** `Job.guide_quality_contract_lint_json`, a `_write_guide_quality_contract_lint(job)` writer in
  `run_markdown_job.py` (after the v2 report; reads the manifest to infer `comprehensive`), and an exact-name
  `_artifact_path` route → `application/json`. Reached only by exact filename — deliberately **not** added to the generic
  ARTIFACTS list, generic UI rows, or export selectors. No UI added.
- **Validation:** new tests `test_guide_quality_prompt_contract.py` (76), `test_guide_quality_contract_lint.py` (83),
  `test_guide_quality_contract_integration.py` (24) all pass; existing prompt/coverage tests re-run green; frontend
  build + `npm test` green (no FE change); `compileall` clean; Docker `smoke_release.py` 29/0/0; live check confirmed the
  `## Guide Quality Contract` block is appended to a generated job's prompt and the `guide_quality_contract_lint.json`
  artifact is written and served (HTTP 200, no leaks).
- **Out of scope / unchanged:** no active recall or other picked features; no extra LLM/provider/model/cloud call; no
  provider/model selection change; no Chandra/Mistral/Gemini; no OCR/PDF/image inspection; no table reconstruction; no
  render/export change; no figure-insertion / material-selection / visual-manifest-filter change; no Ask Guide change; no
  direct `clean.md` write. Chandra remains blocked by its own live-validation gate. **Slice 102 is NOT committed.**

---

## Slice 101 — **EMERGENCY: ~100 MB guide attachment support**, on `slice101-large-attachment-100mb-support`. **Committed `89f8532`, merged + pushed to `chrome-renderer-v1`.**

- **Reprioritized:** Slice 101 active recall was **paused**. The immediate need is letting the app accept and generate a
  guide from an attachment around **100 MB**. This slice raises the upload ceiling only — it adds no study features, no
  LLM/provider/model/cloud call, and changes no generation/OCR/render/export/material-selection semantics.
- **Slice 100 was committed `fbff55d`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1`** (Full Material
  Coverage release validation). Slice 101 branches from that fresh trunk.
- **Backend (`api/server.py`):** the per-attachment ceiling is now a single env-tunable constant. New helper
  `_resolve_max_attachment_mb()` reads `GUIDEFORGE_MAX_ATTACHMENT_MB` (default **150 MB**, a safe margin above the 100 MB
  target). Any missing / non-integer / out-of-range value **degrades to the default** (never raises); the accepted band is
  floored at 100 MB (so the 100 MB goal always fits) and capped at 1024 MB (so a hostile value can't disable the guard).
  `MAX_LLM_ATTACHMENT_BYTES` is derived from it, so both request paths (preflight + multipart attachments) share one
  ceiling. **Before: 15 MB. After: 150 MB default.**
- **Streaming already safe:** the upload guard already reads in 1 MiB chunks and rejects *before* buffering the whole file,
  so no whole-file-in-memory read was introduced. Oversize now returns **HTTP 413** (was 400) with a **generic,
  filename-free** detail (no-leak: never echoes the upload filename/path/content/raw exception). Allowed file types and
  extraction behaviour are unchanged.
- **Frontend:** new pure helper `frontend/src/uploadLimits.js` (`classifyAttachmentSize` + constants + calm copy), mirroring
  the 150 MB backend default with a 100 MB "large file" threshold. The Builder previously did **no** client-side size check
  (relied on the server); it now pre-flights by `file.size` only (never name/contents), drops over-ceiling files with the
  generic copy *"Files larger than 150 MB can't be uploaded."*, and shows *"Large files may take longer to process."* No
  page-selection / material-selection payload changed.
- **Tests:** new `test_scripts/test_large_attachment_limits.py` (env-resolution matrix; 100 MB stream accepted via a stub
  UploadFile — no committed fixture; oversize → 413 generic) and `frontend/scripts/verify-large-attachment-upload-limit.mjs`
  (100 MB accepted/flagged large; >150 MB rejected with calm copy; content-free verdict; determinism; no material-selection
  regression). `test_pdf_preflight.py` oversize assertion updated 400→413.
- **Validation:** frontend build + full `npm test` green; `compileall` clean; new backend test 24/24 in Docker; preflight
  test 25/25; `smoke_release.py` 29/0/0; **live ~100 MB sparse-file upload returned HTTP 200 (not 413), `max_upload_mb` 150**
  — temp file deleted, never committed.
- **Limitations still present:** this raises *app-level* caps only. If a reverse proxy / web server is ever placed in front,
  its body-size cap must be aligned separately. Very large guides may still hit provider context limits or longer
  extraction/generation time — out of scope for this emergency slice. Chandra remains blocked by its own live-validation
  gate. **Slice 101 is NOT committed.**

---

## Slice 100 — **Full Material Coverage E2E release validation**, on `slice100-full-material-coverage-release-validation`. **Committed `fbff55d`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 99 was committed `e8d6f86`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1`** (it added the
  optional dual explanation mode). Slice 100 branches from that fresh trunk.
- **Goal:** a deterministic, synthetic, validation-only **release checkpoint** proving the whole Full Material Coverage
  phase (Slices 82–99) coheres end to end — *without adding any product behaviour*. It is a signal/coherence validation
  (safe counts, statuses, refs line up and stay leak-free), **not** a semantic grader and **not** a live-LLM run.
- **New backend harness `test_scripts/test_full_material_coverage_release_validation.py`** (86 checks). It assembles one
  synthetic scenario (two attachments addressed only by safe positional ids; material page exclusions active; source
  coverage with covered + unreadable pages; 4 useful non-table figures with tiny temp PNG assets; 5 table-like records →
  reconstruct / simplify / skip_unreadable / defer / unsafe-skipped; static app headings + safe page signals + safe figure
  refs in the guide Markdown) and walks the **real already-merged pure helpers** in release order:
  material page selections → source coverage report → visual inclusion plan → **full** non-table figure insertion (into
  synthetic clean Markdown, behind the Slice 90 env switch) → render/export asset ride-along (`find_all_exportable_visual_assets`,
  uncapped, safe `assets/<slug>.png` only) → table candidate manifest → table reconstruction policy → table reconstruction
  prompt context → missing visual/table guidance → coverage-aware generation guidance → guide quality report v2 → Ask Guide
  coverage grounding → dual explanation mode (off byte-equivalent + on two-layer guidance). A deep no-leak walk over every
  serialized stage asserts none of the seeded canaries survive; a determinism check asserts identical serialization on
  repeat.
- **Frontend release validation = reuse of the existing per-dimension verify scripts** (`verify-material-page-selections-ui`,
  `verify-material-coverage-display`, `verify-material-coverage-warnings`, `verify-material-coverage-final-panel`,
  `verify-dual-explanation-mode-ui`). No new frontend script was added (it would only duplicate these) and **no UI changed**.
- **Out of scope / unchanged:** no new product feature; no LLM/provider/model/cloud call; no extraction/OCR change; no
  PDF/image inspection; no table reconstruction; no UI; no render/export behaviour change; no figure-insertion semantics
  change; no material page-selection change; no visual-manifest-filter change. No direct `clean.md` write. Chandra remains
  blocked by its own live-validation gate. **Slice 100 is NOT committed.**

---

## Slice 99 — **Explain like I'm 10 / Exam answer mode v1**, on `slice99-dual-explanation-mode`. **Committed `e8d6f86`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 98 was committed `9f9d838`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1`** (it added Ask
  Guide coverage grounding). Slice 99 branches from that fresh trunk.
- **Goal:** an optional study-quality generation mode that asks the guide generator to explain difficult / exam-important
  concepts **two ways** — a beginner-friendly "Explain it simply" block plus a formal "Exam answer" block — so a student
  can understand the concept and then learn the version to write in the exam. **Default off.** Missing/false ⇒ generation
  prompt is byte-identical to before.
- **New pure module `pipeline/dual_explanation_prompt_context.py`** — stdlib-only, imports nothing from `pipeline` and no
  provider/model/OCR/renderer/FastAPI/frontend. `build_dual_explanation_prompt_context(enabled, *, max_items=None)` returns
  `{version, kind:"dual_explanation_prompt_context", status (completed/skipped), summary{enabled, prompt_item_count},
  prompt_block, warnings}`. Only a real `True` enables; `None`/`False` ⇒ normal off; any other type ⇒ off + closed
  `enabled_not_bool` warning. `max_items` is a defensive ceiling only. The `prompt_block` is a fixed, deterministic,
  source-grounded instruction (two companion blocks; concise; no invented facts/examples/labels/table values/diagram
  details/citations; say what's missing instead of guessing). Never raises; reads no source text.
- **Prompt integration = `run_llm_job.py`** via `_build_dual_explanation_prompt_block_safely(enabled)`, appended to the
  generation source under the `## Dual Explanation Mode` heading **after** the Slice 93/94/95 attachment guidance blocks.
  Applies to every generation (paste or attachment). Disabled ⇒ empty block ⇒ prompt byte-equivalent. Composes safely with
  the Slice 95 coverage-aware guidance.
- **Request field `dual_explanation_mode: bool` (default False)** wired into BOTH `/api/jobs/llm` paths: the JSON
  `LLMJobRequest` model (pydantic-coerced) and the multipart `_parse_llm_request` branch (`_form_bool`), and threaded into
  the `run_llm_job(...)` call. Persisted in the job manifest as `dual_explanation_mode` (mirrors the visual-pilot
  `visual_markdown_image_pilot` precedent — persisted, not surfaced in the public job-details DTO).
- **Frontend:** new pure helper `frontend/src/dualExplanationOptIn.js` (`DUAL_EXPLANATION_PAYLOAD_KEY`/`_LABEL`/`_HELPER`,
  `dualExplanationPayloadFields`) + a Builder toggle ("Explain difficult concepts two ways" with helper copy) in the
  `source === "llm"` options area. Default off; the field is sent only when true (omitted otherwise, matching the
  visual-pilot convention), so a default request stays byte-equivalent. Does not touch `page_selections` /
  `material_page_selections`.
- **Tests:** `test_dual_explanation_prompt_context.py` (91, pure: disabled/enabled/malformed/max_items/determinism/no-leak/
  import-hygiene + run_llm_job integration helper), `test_dual_explanation_request.py` (JSON+multipart parse, manifest
  persistence, prompt-block presence/absence, hostile-value no-leak; skips without FastAPI),
  `frontend/scripts/verify-dual-explanation-mode-ui.mjs` (payload helper + static BuilderWorkspace wiring).
- **Out of scope / unchanged:** no extra LLM/provider/model/cloud call; no provider/model selection change; no PDF/image/
  OCR inspection; no table reconstruction; no render/export change; no figure-insertion / material-selection / visual-filter
  change; no Ask Guide change. Chandra remains blocked by its own live-validation gate.

---

## Slice 98 — **Ask Guide coverage grounding upgrade**, on `slice98-ask-guide-coverage-grounding`. **Committed `9f9d838`, merged + pushed to `chrome-renderer-v1`.**

- **Slice 97 was committed `e6e91df`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1`** (it finalized the
  JobDetails Material Coverage panel). Slice 98 branches from that fresh trunk.
- **Goal:** make **Ask Your Guide** aware of the same safe coverage signals that Slices 82–97 gave the guide + JobDetails.
  When a user asks Ask Guide a coverage/meta question ("were any pages excluded?", "did the guide include all figures?",
  "were tables reconstructed?", "why is a diagram missing?", "can I trust the coverage?"), the local answer model now has a
  short, sanitized **coverage grounding** block in its context, derived from the already-sanitized exact-name artifacts +
  the job's safe page-selection fields. **Counts/statuses only.** Course content still comes from the guide/source chunks.
- **New pure module `pipeline/ask_coverage_grounding.py`** — stdlib-only, imports nothing from `pipeline` and no
  provider/model/OCR/renderer/FastAPI/frontend. `build_ask_coverage_grounding(*, job, source_coverage_report,
  visual_inclusion_plan, table_candidates_manifest, table_reconstruction_policy, guide_quality_report_v2, max_items)`
  returns `{version, kind:"ask_coverage_grounding", status (completed/partial/skipped), summary, grounding_text, items,
  warnings}`. It reads every input **for decisions only** (never echoes a raw field), emits only closed tokens / ints /
  `None` / bools / fixed instruction strings + `ask_grounding_NNNN` item ids, degrades to a safe `skipped` on any
  malformed/missing input, and never raises. `summary` carries `has_material_page_selections`, `source_count`,
  `unreadable_page_count`, `planned_visual_count`, `observed_safe_figure_ref_count`, `table_candidate_count`,
  `table_policy_item_count`, `missing_material_signal_count`, `quality_warning_count`, `grounding_item_count`.
- **Closed signal item kinds:** `material_selection`, `source_coverage`, `visual_coverage`, `table_policy`,
  `missing_material`, `guide_quality`. The `grounding_text` always opens with a meta-context disclaimer ("not course
  content"; use only for coverage/figure/table/completeness questions; not a citable source) and closes with "these are
  deterministic signal checks, not semantic proof" + "do not invent figure/table details; if unavailable, say so."
- **Integration point = Ask Guide model-facing context preamble (not an indexed/citable chunk).** In
  `pipeline/ask_sessions.py`: `build_coverage_grounding_for_job(job)` reads the job manifest's `material_page_selection` /
  `material_page_selections` + the five exact-name artifacts (via a total/degrade-safe `_read_artifact_json`) and calls the
  pure builder; `answer_message` calls it and threads `coverage_grounding_text` into `assemble_prompt`, which injects it
  into the **system** message after the existing `ANSWER_RULES` + citation-label list, framed by a new
  `COVERAGE_GROUNDING_RULES` constant that states it is internal meta-context, not citable, not course content. The
  grounding is **not** added to the lexical/context index and carries no chunk text or citation label, so the citation
  contract is unchanged. An absent/skipped grounding yields an empty string → the prompt is byte-identical to before.
- **Preserved:** the direct-answer guard (`Answer directly in normal assistant content.`), the empty-response guard
  (`provider_empty_response`), `/no_think` (`LOCAL_THINKING_MODEL_CONTROL`, model-facing in the user message only), and all
  citation rules/validation. No provider/model/cloud call, no figure-insertion / material-selection / visual-filter /
  render / export change, no table reconstruction, no PDF/image/OCR inspection, no direct `clean.md` write. Chandra remains
  blocked by its own live-validation gate.
- **Tests:** new `test_scripts/test_ask_coverage_grounding.py` (synthetic dicts only) — missing/empty → skipped; malformed
  → safe degrade with closed warnings; per-signal summaries (selection active/inactive, source coverage, visual planned +
  observed safe figure refs, table candidate/policy, missing-material, guide-quality warnings); count coercion; `max_items`
  ceiling → partial; deterministic ids/serialization; a deep-walk no-leak sweep (no filename/path/title/text/OCR/caption/
  table-text/image-ref/asset-ref/base64/data-URI/URL/token/argv/socket/model-path/raw-exception); hostile status not
  echoed; stdlib-only purity guard; and a guarded `ask_sessions` integration section (grounding injected into system, not a
  citation label, `/no_think` + direct-answer + citation contract preserved, empty grounding → no block). Reran the
  existing ask suite + the coverage-artifact regressions. **Slice 98 is NOT committed.**

---

## Slice 97 — **JobDetails Material Coverage final panel**, on `slice97-jobdetails-material-coverage-final-panel`. **COMMITTED `e6e91df` → trunk `chrome-renderer-v1`.**

- **Upgrades the existing JobDetails "Material Coverage" tab into the final read-only coverage dashboard for the current
  material-coverage phase.** Slice 96 was committed `2fc6d95`, fast-forward merged, and pushed to trunk on
  `chrome-renderer-v1` (it added `guide_quality_report_v2.json`). Slice 97 is a **frontend display slice only**: it reads
  safe **exact-name** artifacts and shows counts/statuses/checks. It changes no backend generation behavior.
- **It does NOT** change backend extraction/OCR, inspect PDFs/images, reconstruct tables, add table text extraction,
  change prompts, change render/export, change figure insertion semantics, change material page-selection logic, change
  visual-manifest filtering, add provider/model/cloud code, or call Chandra/Mistral/Gemini. Chandra remains blocked by its
  own live-validation gate. No backend route was added (the exact-name route already exists via `_artifact_path`).
- **Artifacts fetched (exact-name, independent fetch lifecycle each):** `source_coverage_report.json`,
  `visual_inclusion_plan.json`, `table_candidates_manifest.json`, `table_reconstruction_policy.json`,
  `guide_quality_report_v2.json`. A 404 = "Not available"; any non-404/network/non-JSON = calm "Unavailable"; raw error
  text / raw URL is never surfaced; older jobs with missing artifacts still render the panel.
- **Panel sections (counts/statuses only):** (1) Material selections — active/inactive + attachments-with-exclusions +
  global selection; (2) Source coverage — sources / total / covered / embedded-text / OCR / unreadable; (3) Figures and
  diagrams — planned non-table count + observed safe figure-ref count (from `guide_quality_report_v2`) + visual check
  status, with honest "full insertion may be off for older/default jobs" copy; (4) Tables — table-candidate count + policy
  item count + reconstruct/simplify/defer/unreadable/unsafe counts + screenshot-insert shown as "Not used" (always 0),
  with "tables are not inserted as screenshots" copy; (5) Missing material — missing-material check status + item count;
  (6) Guide quality v2 — report status + per-check (source_pages/visuals/tables/missing_material/coverage) statuses +
  warning count + "deterministic signal checking, not semantic grading" copy; (7) Artifacts — fixed exact-name links only
  (calm "Not available" when missing). Slice 89 "what this means" notes retained.
- **Helper changes (`frontend/src/materialCoverageDisplay.js`):** new `summarizeTableCandidatesManifest(manifest)`,
  `summarizeTableReconstructionPolicy(policy)`, `summarizeGuideQualityReportV2(report)`, and composite
  `buildMaterialCoverageFinalModel({ job, sourceCoverageReport, visualInclusionPlan, tableCandidatesManifest,
  tableReconstructionPolicy, guideQualityReportV2 })`. The Slice 88 `buildMaterialCoverageDisplayModel` is preserved and
  still used (the final builder extends it). Every helper tolerates missing/malformed input, never throws, emits closed
  status/check tokens + non-negative integer counts only, surfaces no raw artifact warnings/source detail/filenames/paths/
  table text/captions/OCR text/image-asset refs/raw URLs/raw errors, and is deterministic. The report's `instruction`
  strings and `check_id`s are never surfaced (counts/statuses only).
- **`MaterialCoveragePanel.jsx`** fetches the three new exact-name artifacts independently (existing source/visual fetches
  unchanged), builds the final model, and renders the 7 sections. **`RecentJobsPanel.jsx` was NOT changed** — the tab was
  already wired with `jobId`/`job`. Minor layout-only CSS added in `design-system.css` (`.sg-artifact-links`,
  `.sg-artifact-link-row`, `.sg-coverage-checks`).
- **Tests:** new `frontend/scripts/verify-material-coverage-final-panel.mjs` (wired into `npm test` + a `test:` script) —
  covers all-missing → calm unavailable, valid manifest/policy/report summaries, screenshot-insert = 0/"not used", check
  statuses without image refs, malformed degrade, hostile canaries stripped (deep-walk), fixed exact-name links, legacy
  Slice 88/89 behavior, determinism. Reran `verify-material-page-selections-ui`, `verify-material-coverage-display`,
  `verify-material-coverage-warnings`. **Slice 97 is NOT committed.**

---

## Slice 96 — **Guide quality report v2**, on `slice96-guide-quality-report-v2`. **COMMITTED `2fc6d95`, merged + pushed to `chrome-renderer-v1`.**

- **Adds a deterministic, sanitized `guide_quality_report_v2.json` that measures whether the generated guide appears to
  reflect the Slices 82–95 coverage signals.** Slice 95 was committed `c8d3c02`, fast-forward merged, and pushed to trunk
  on `chrome-renderer-v1` (coverage-aware generation prompt context). Slice 96 is the matching measurement: after a guide
  is generated it scans `clean.md` for **safe counts only** and compares them against the already-sanitized coverage
  artifacts.
- **It does NOT** call an LLM, change prompts, change extraction/OCR, inspect PDFs/images, read image bytes, reconstruct
  tables, extract table text, add UI, change render/export, change figure insertion semantics, change material
  page-selection logic, change visual-manifest filtering, or add/call any provider/model/cloud (no Chandra/Mistral/Gemini).
  Chandra remains blocked by its own live-validation gate.
- **This is a signal/count report, NOT a semantic evaluator** — it does not claim to prove correctness. Where an expected
  signal is not observed it emits a closed warning rather than a failure.
- **New pure module:** `pipeline/guide_quality_report_v2.py` —
  `build_guide_quality_report_v2(clean_markdown, *, source_coverage_report=None, visual_inclusion_plan=None,
  table_candidates_manifest=None, table_reconstruction_policy=None, missing_material_context=None,
  coverage_aware_context=None, full_visual_insertion_enabled=False, max_items=None)` → sanitized report dict
  (`version`=2/`kind`/`status`/`summary`/`checks`/`warnings`). It scans `clean.md` for: safe page-grounded signals
  (`page N`, counted + unique), safe Markdown image refs of the fixed `assets/<slug>.png` shape (URLs / data URIs /
  absolute paths / traversal / backslash / nested paths / schemes all rejected), and a closed set of static app-authored
  guidance phrases (`Source visual, page`, `Table Reconstruction Guidance`, `Missing Visual and Table Guidance`,
  `Coverage-Aware Generation Guidance`). It emits one closed *check* per dimension in fixed order — `source_pages`,
  `visuals`, `tables`, `missing_material`, `coverage` — each with a safe `check_id` (`guide_quality_check_NNNN`), closed
  `kind`, closed `status` (`passed`/`warning`/`not_applicable`/`unknown`), `observed_count`, `expected_count`, fixed-shape
  `instruction`, and closed per-check `warnings`. **No `clean.md` excerpt is ever persisted** — the markdown is read for
  counts only. Missing/empty `clean.md` → safe `skipped`; `max_items`/ceiling → `partial`; malformed artifacts degrade with
  closed warnings. stdlib-only (no `pipeline`/provider/model/OCR/renderer/FastAPI import).
- **Integration point:** `pipeline/run_markdown_job.py::run_raw_markdown_pipeline`, right after `_write_guide_lint(job)`
  (so after `save_clean_md`). `_write_guide_quality_report_v2(job)` reads `clean.md` + the already-written sanitized sibling
  artifacts (`source_coverage_report.json`, `visual_inclusion_plan.json`, `table_candidates_manifest.json`,
  `table_reconstruction_policy.json`), rebuilds the Slice 94 missing-material + Slice 95 coverage-aware contexts from those
  same artifacts via the existing pure builders, and writes the report through `job.save_text(...)`. Same advisory contract
  as math-verification / guide-lint: never changes status, never blocks the render, never fails the job; a missing/unreadable
  `clean.md` or any error degrades to a small safe `skipped` artifact (no traceback).
- **Artifact:** `jobs/<id>/guide_quality_report_v2.json`. New `Job.guide_quality_report_v2_json` property + exact-name
  `_artifact_path` entry returning `application/json`. **Exact-name download only** — deliberately NOT added to the generic
  `ARTIFACTS` list, generic UI rows, or export selectors (UI surfacing deferred).
- **Tests:** `test_scripts/test_guide_quality_report_v2.py` (synthetic clean-Markdown + synthetic artifact dicts only) —
  100/100 pass; the exact-name server check skips in host Python (FastAPI unavailable) and is covered in Docker.

---

## Slice 95 — **Coverage-aware generation prompt v1**, on `slice95-coverage-aware-generation-prompt`. **COMMITTED `c8d3c02`, merged + pushed to `chrome-renderer-v1`.**

- **Adds a single sanitized coverage-aware generation guidance block that tells the guide generator how to use the
  selected material completely and honestly.** Slice 94 was committed `3264b92`, fast-forward merged, and pushed to trunk
  on `chrome-renderer-v1` (missing visual/table explainer core). Slices 82–94 established the layered coverage signals
  (included/excluded pages, source coverage, planned visuals, table candidate/policy, table prompt context, missing-material
  context). Slice 95 is the summarising capstone on top.
- **It does NOT** change extraction/OCR, inspect PDFs/images, read image bytes, reconstruct tables, extract table text,
  add UI, change render/export, change figure insertion semantics, change material page-selection logic, change
  visual-manifest filtering, or add/call any provider/model/cloud (no Chandra/Mistral/Gemini). Chandra remains blocked by
  its own live-validation gate.
- **Product rule.** The block instructs the LLM to focus only on included material, never rely on excluded pages/slides,
  treat source-coverage gaps as constraints (mentioned generically and page-based), connect explanations to inserted
  figures, reconstruct/simplify tables only when source text supports it, and add honest missing-material notes instead of
  inventing diagram labels, captions, table rows/cells, or numeric values. It SUMMARISES which closed coverage signals are
  active — it never repeats the per-item Slice 93/94 detail.
- **New pure module:** `pipeline/coverage_aware_prompt_context.py` —
  `build_coverage_aware_prompt_context(*, job_request=None, source_coverage_report=None, visual_inclusion_plan=None,
  table_candidates_manifest=None, table_reconstruction_policy=None, table_prompt_context=None, missing_material_context=None,
  full_visual_insertion_enabled=False, max_items=None)` → sanitized context dict
  (`version`/`kind`/`status`/`summary`/`prompt_block`/`items`/`warnings`). It reads each input for **decisions only** (counts
  + a page-selection-active bool) and emits one closed *signal item* per active coverage signal, in fixed order:
  `included_page` (page exclusions active), `source_gap` (unreadable pages > 0), `visual_plan` (planned visuals > 0),
  `table_policy` (table candidates/policy items > 0), `missing_material` (missing-material items > 0). Items carry a safe
  generated `item_id` (`coverage_context_NNNN`), `source_page` `None` (signals are aggregate, not page-anchored), closed
  `kind`, and a fixed-shape `instruction`. Defensive ceiling / `max_items` → `partial`; all-inactive/empty/missing/malformed
  → safe `skipped` + empty block. stdlib-only.
- **Integration point:** `pipeline/run_llm_job.py::_attach_sources`. After the Slice 93 table block and Slice 94
  missing-material block, `_build_coverage_aware_prompt_block_safely(...)` builds the context from the page-selection
  envelope (`{material_page_selection, material_page_selections}`) + the captured source coverage report + the visual
  inclusion plan + the two table artifacts + the Slice 94 missing-material context, and returns its `prompt_block` only when
  the context is `completed`/`partial` **and** `prompt_item_count > 0`; appended under a `## Coverage-Aware Generation
  Guidance` heading. The source-coverage writer helper now returns its report dict so counts are reused (no artifact
  re-read). Absent/skipped/empty ⇒ prompt byte-identical. No new artifact is persisted (in-memory prompt context only).
  Degrade-never-fail.
- **Tests:** `test_scripts/test_coverage_aware_prompt_context.py` (synthetic dicts only) — missing/malformed/all-inactive →
  skipped+empty; page-selection active/inactive (global + per-attachment `attachments`); source coverage / visual / table /
  missing-material counts summarized; signal ordering + deterministic `coverage_context_NNNN` ids; defensive `max_items`;
  hostile-canary strip + full no-leak scan; closed-kind tokens; page None-or-positive-int; stdlib-only import hygiene; and
  the run_llm_job helper (none/inactive → empty, actionable → guidance, no raw Slice 93/94 block duplication, no leak).
- **Validation:** `compileall` clean; the Slice 95 test plus the rerun Slice 90–94 + source-coverage suites all pass;
  Docker build + `/api/health` + `smoke_release.py` green. `git diff --check` clean. **Slice 95 is NOT committed.**

---

## Slice 94 — **Missing diagram/table explainer core**, on `slice94-missing-visual-table-explainer-core`. **Committed `3264b92`, fast-forward merged + pushed to `chrome-renderer-v1`.**

- **Adds an honest "what was missing" explainer so detected visual/table material that cannot be inserted or
  reconstructed is acknowledged without inventing its contents.** Slice 93 was committed `774a2e4`, fast-forward merged,
  and pushed to trunk on `chrome-renderer-v1` (table reconstruction prompt-context integration). Slices 90–91 made full
  non-table figure insertion safe; Slices 92–93 added the sanitized table artifacts + safe table prompt context. Slice 94
  consumes the Slice 84 visual inclusion plan + the two Slice 92 table artifacts to plan safe, generic missing-material
  guidance.
- **It does NOT** inspect PDFs/images, OCR, read image bytes, extract table text, reconstruct tables, generate
  image-derived diagram explanations, call any provider/model/cloud, change render/export, change figure insertion
  semantics, change visual-manifest filtering, change material page-selection, or add UI. Tables are never screenshots.
- **No-hallucination product rule.** When useful visual or table-like material is detected but unavailable, the guidance
  tells the model to add a short, honest note naming the *kind* of item and the *page*, and never to invent labels, rows,
  values, or diagram details. For unreadable/deferred tables it asks for a "table-like material was detected on page N but
  its contents were not readable" note; for un-inserted figures/diagrams it points the student at the source page.
- **New pure module:** `pipeline/missing_material_explainer.py` —
  `build_missing_material_explainer_context(visual_inclusion_plan, table_candidates_manifest,
  table_reconstruction_policy, *, full_visual_insertion_enabled=False, max_items=None)` → sanitized context dict
  (`version`/`kind`/`status`/`summary`/`items`/`prompt_block`/`warnings`). Behavior: table policy `defer` →
  `table_deferred` item, `skip_unreadable` → `table_unreadable` item, `skip_unsafe` → counted only (never surfaced),
  `reconstruct_with_original`/`simplify_only` → not missing (handled by Slice 93). Planned non-table visuals →
  `visual_not_inserted` items **only when full visual insertion is disabled**; when enabled, planned visuals are never
  marked missing (no insertion-failure signal exists, so failure is never invented — a closed warning is recorded). Items
  carry a safe generated `item_id` (`missing_material_NNNN`), positive-int `source_page`, closed `material_kind`
  (`diagram`/`figure`/`graph`/`chart`/`table`/`table_like`/`unknown`), closed `reason`, and a fixed-shape `instruction`.
  Invalid-page items dropped; defensive ceiling / `max_items` → `partial`; all-missing/empty → safe `skipped` + empty
  block. stdlib-only.
- **Integration point:** `pipeline/run_llm_job.py::_attach_sources`. After the Slice 93 table prompt context,
  `_build_missing_material_prompt_block_safely(...)` builds the explainer (reading the full-insertion mode switch via the
  existing `is_full_visual_insertion_enabled()` env helper) and returns its `prompt_block` only when the context is
  `completed`/`partial` **and** `prompt_item_count > 0`; appended under a `## Missing Visual and Table Guidance` heading.
  Absent/skipped/empty ⇒ prompt byte-identical. The inclusion-plan writer helper now returns the plan dict so the builder
  reuses it (no artifact re-read). No new artifact is persisted (in-memory prompt context only). Degrade-never-fail.
- **Files changed:** `pipeline/missing_material_explainer.py` (new), `pipeline/run_llm_job.py` (imports + one local +
  builder helper + plan-writer returns plan + safe append), `test_scripts/test_missing_material_explainer.py` (new), plus
  the three docs. **No table reconstruction, no OCR/PDF/image inspection, no image-derived diagram explanation, no
  provider/model/cloud, no render/export, no figure insertion semantics, no material selection / visual filtering, no UI,
  and no direct `clean.md` write changed.**
- **Validation (host):** `test_missing_material_explainer` 121/0, `test_table_reconstruction_prompt_context` 108/0,
  `test_table_candidate_manifest` 105/0, `test_table_reconstruction_policy_artifact` 39/0,
  `test_table_reconstruction_policy` 145/0, `test_full_visual_insertion_v2` 81/0,
  `test_full_visual_render_export_validation` 22/0 (DOCX+bundle skip on host), `test_material_coverage_e2e_validation`
  79/0. `compileall` clean; `git diff --check` clean. **Docker:** build + health + `smoke_release.py`. No-leak sweep
  clean. **NOT committed.**
- **Next:** later slices can surface missing-material notes in the UI or persist an artifact if a need appears; image-only
  understanding stays deferred. Chandra remains blocked by its own live-validation gate.

---

## Slice 93 — **Table reconstruction prompt-context integration v1**, on `slice93-table-reconstruction-prompt-context`. **Committed `774a2e4`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

- **Uses the Slice 92 sanitized table artifacts to add safe, honest table reconstruction guidance to the guide
  generation prompt.** Slice 92 was committed `ea3f321`, fast-forward merged, and pushed to trunk on
  `chrome-renderer-v1` (table candidate manifest + reconstruction policy artifacts). Slice 93 turns those two
  already-sanitized artifacts (`table_candidates_manifest.json` + `table_reconstruction_policy.json`) into a short,
  deterministic, leak-free **prompt context** appended to the normal generation source — telling the LLM how to handle
  table-like material safely.
- **It does NOT** reconstruct tables from images, inspect PDFs/images, OCR, read image bytes, extract table text, call
  any provider/model/cloud, change material page-selection or visual filtering, change render/export, change figure
  insertion semantics, or add UI. Tables are still never treated as screenshots.
- **No-hallucination product rule.** The appended guidance is honest and closed: reconstruct/simplify a table **only**
  when its contents are present in the provided source text; preserve `headers`/`column_labels`/`row_labels`/
  `exam_terms`/`numeric_values`/`units` when available; never invent rows/columns/labels/values for image-only or
  unreadable tables; for `defer`/`skip_unreadable` tables emit an honest "table-like material was detected on page N but
  its contents were not readable" note. `skip_unsafe` items are excluded entirely (never surfaced).
- **New pure module:** `pipeline/table_reconstruction_prompt_context.py` — `build_table_reconstruction_prompt_context(
  table_candidates_manifest, table_reconstruction_policy, *, max_items=None)` returns a sanitized context dict
  (`version`, `kind`, `status`, `summary`, `prompt_block`, `items`, `warnings`). Each actionable policy item becomes a
  prompt item with a closed `action`, positive-int `source_page` (or `None`), closed `preserve` tokens, a safe generated
  `candidate_id` (`table_candidate_NNNN`, recovered from the manifest or synthesized), and a fixed-shape `instruction`.
  Missing/`None`/malformed/skipped artifacts → safe `skipped` context with an empty `prompt_block`; a defensive ceiling /
  `max_items` marks `partial`. stdlib-only; imports nothing from providers/models/OCR/renderers/FastAPI/frontend.
- **Integration point:** `pipeline/run_llm_job.py::_attach_sources`. After the Slice 92 candidate manifest + policy are
  written, `_build_table_prompt_block_safely(...)` builds the context and returns its `prompt_block` only when the
  context is `completed`/`partial` **and** `prompt_item_count > 0`; the block is appended to the attached source under a
  `## Table Reconstruction Guidance` heading. Absent/skipped/empty context ⇒ the prompt is byte-identical to before. The
  policy writer helper now returns the policy dict so the builder reuses it (no artifact re-read). Degrade-never-fail —
  prompt-context failure never gates generation.
- **Files changed:** `pipeline/table_reconstruction_prompt_context.py` (new), `pipeline/run_llm_job.py` (import + one
  variable + builder helper + safe append), `test_scripts/test_table_reconstruction_prompt_context.py` (new), plus the
  three docs. **No table reconstruction, no OCR/PDF/image inspection, no provider/model/cloud, no render/export, no
  figure insertion semantics, no material selection / visual filtering, no UI, and no direct `clean.md` write changed.**
- **Validation (host):** `test_table_reconstruction_prompt_context` 108/0, `test_table_candidate_manifest` 105/0,
  `test_table_reconstruction_policy_artifact` 39/0, `test_table_reconstruction_policy` 145/0,
  `test_material_coverage_e2e_validation` 79/0, `test_source_coverage_report` 59/0, `test_full_visual_insertion_v2` 81/0,
  `test_full_visual_render_export_validation` 22/0 (DOCX+bundle skip on host). `compileall` clean; `git diff --check`
  clean. **Docker:** build + health + `smoke_release.py`. No-leak sweep clean.
- **Next:** Slice 94 — missing diagram/table explainer core, consuming the visual inclusion plan + table artifacts.
  Chandra remains blocked by its own live-validation gate.

---

## Slice 92 — **Table candidate manifest + reconstruction-policy artifacts**, on `slice92-table-candidate-manifest-policy-artifacts`. **Committed `ea3f321`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

- **Builds the missing sanitized table-candidate bridge so table reconstruction prompt integration (Slice 93/94) can
  start safely.** Slice 91 was committed `ff7bc70`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1`
  (full figure render/export validated). Slice 85 added a pure table *policy core*, but it had only ever consumed
  **synthetic** candidates because there is still no real table manifest. Slice 92 derives sanitized table candidates
  from the already-safe `visual_assets_manifest.json` (Slice 82 page-filtered) and persists two exact-name artifacts.
- **It does NOT** reconstruct tables, call an LLM, change prompts, insert tables into Markdown/PDF/DOCX, add UI, OCR,
  inspect PDFs/images, or call any provider/model/cloud. It also treats a table as a **decision record, never a
  screenshot** — `screenshot_insert_count` is always `0`.
- **New artifacts (exact-name download only).**
  - `table_candidates_manifest.json` (`pipeline/table_candidate_manifest.py`, new) — recognizes table-like manifest
    records by closed tokens (`table`, `table_like`, `grid_table`, `dense_table`, `table_region`, `tabular`,
    `table_image`), skips non-table records (counted), skips unsafe/malformed/page-less records (counted), and emits
    sanitized candidates: a safe generated `candidate_id` (`table_candidate_0001`…), `source_index`, positive-int
    `source_page`, closed `table_kind`, closed `confidence` token, and a count-only `signals` block (bool
    `has_text_layer` + non-negative int `rows`/`columns`/`cell_text_count`/`numeric_cell_count`/`header_cell_count`).
    Missing/malformed/skipped input → safe `skipped` manifest; a defensive ceiling marks `partial`.
  - `table_reconstruction_policy.json` (`pipeline/table_reconstruction_policy_artifact.py`, new) — feeds the sanitized
    candidates into the **unchanged Slice 85** `build_table_reconstruction_policy(...)` and persists the result. A
    genuinely skipped candidate manifest → `skipped` policy; otherwise the policy decides each candidate
    (`reconstruct_with_original` / `simplify_only` / `defer` / `skip_unreadable` / `skip_unsafe`) and never a screenshot.
- **Bridge.** `table_policy_candidates(manifest)` flattens each manifest candidate into the shape the Slice 85 policy
  reads (closed `kind` token + flat count signals + `has_text_layer` + `confidence`); only closed tokens/ints/bools/None
  cross the bridge — no field of the source record is ever echoed.
- **Files changed:** `pipeline/table_candidate_manifest.py` (new), `pipeline/table_reconstruction_policy_artifact.py`
  (new), `pipeline/job_manager.py` (two exact-name `Job` path properties), `pipeline/run_llm_job.py` (two degrade-never-
  fail writer calls wired after the visual manifest is written), `api/server.py` (two exact-name `_artifact_path`
  branches — NOT added to `ARTIFACTS`, generic UI rows, or export selectors), `test_scripts/test_table_candidate_manifest.py`
  (new), `test_scripts/test_table_reconstruction_policy_artifact.py` (new), plus the three docs. **No table reconstruction,
  no prompt/provider/model/cloud, no render/export code, no figure insertion semantics, no material selection / visual
  filtering, no UI, and no direct `clean.md` write changed. The Slice 85 policy core is unchanged (its 145-test suite
  still passes byte-identical).**
- **Validation (host):** `test_table_candidate_manifest` 105/0, `test_table_reconstruction_policy_artifact` 39/0,
  `test_table_reconstruction_policy` 145/0, `test_visual_assets_manifest` 65/0, `test_material_coverage_e2e_validation`
  79/0, `test_source_coverage_report` 59/0, `test_source_coverage_artifact` 45/0, `test_full_visual_insertion_v2` 81/0,
  `test_full_visual_render_export_validation` 22/0 (DOCX+bundle skip on host). `compileall` clean; `git diff --check`
  clean. **Docker:** build + health + `smoke_release.py` 29/0; both new focused tests 105/0 and 39/0 in-image; exact-name
  download of both artifacts returns **HTTP 200 + `application/json`**. **NOT committed.**
- **Next:** Slice 93/94 — table reconstruction prompt integration/validation, consuming these sanitized artifacts.
  Chandra remains blocked by its own live-validation gate.

---

## Slice 91 — **Full figure insertion export/render validation**, on `slice91-full-figure-render-export-validation`. **Committed `ff7bc70`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

- **Validates and hardens the render/export asset path for the Slice 90 full insertion mode.** Slice 90 was committed
  `096148f`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1`; it can now place *many* safe
  `assets/<slug>.png` figure refs into a guide's `clean.md`, but broad PDF/DOCX/HTML/export fidelity was explicitly
  deferred. Slice 91 proves a guide with many inserted figures rides through Markdown → HTML → PDF → DOCX → export-ZIP
  safely, and fixes the one load-bearing cap.
- **The one load-bearing cap-2 was the export bundle ride-along** (`/api/exports/bundle` in `api/server.py`, fed by
  `find_exportable_visual_pilot_assets`, itself capped at `_HARD_MAX_IMAGES` (2), plus a redundant `>= 2` break in the
  server loop). With full insertion enabled this would have silently dropped every referenced figure past the first two.
  **The HTML/PDF/DOCX renderers were already uncapped** — they render/embed every referenced `assets/<slug>.png` from the
  job dir (HTML emits one `<img>` per ref; Chromium PDF consumes that HTML; DOCX embeds each present figure and leaves a
  safe `[image missing: assets/<slug>.png]` marker for an absent one) — so no renderer change was needed; this slice
  proves that with focused synthetic checks.
- **Fix (smallest safe change).** Added `find_all_exportable_visual_assets(job, *, limit=_FULL_INSERTION_HARD_CEILING)` —
  the uncapped (only ceiling-bounded) twin of the legacy helper. Discovery is driven purely by what `clean.md` actually
  references, so it is correct for **both** the legacy capped pilot (a guide referencing ≤2 still yields ≤2) and full
  insertion (many), and still only rides along safe job-local `assets/<slug>.png` refs whose real file resolves *inside*
  the job dir (realpath containment; symlink escape, absolute, `..`, URL, `data:`/base64, non-PNG, nested all rejected).
  The legacy `find_exportable_visual_pilot_assets` now simply delegates with `limit=_HARD_MAX_IMAGES`, so legacy behavior
  is byte-identical. The export bundle loop switched to the uncapped helper and the redundant `>= 2` break is replaced by
  the same defensive `_FULL_INSERTION_HARD_CEILING` (200) guard. Bundle manifest keeps both the backward-compatible first-
  ref field (`visual_pilot_asset`) and the full list (`visual_pilot_assets`); ride-along figures still never count toward
  the requested-artifact gate (`files_included`).
- **Files changed:** `pipeline/visual_markdown_insertion.py` (new `find_all_exportable_visual_assets`; legacy helper
  delegates), `api/server.py` (bundle ride-along uses the uncapped helper; cap-2 removed), and
  `test_scripts/test_full_visual_render_export_validation.py` (new), plus the three docs. **No figure selection/planning
  semantics, material page-selection, visual-manifest filtering, prompt/provider/model/cloud, UI, table policy, or direct
  `clean.md` write changed.**
- **New test** `test_scripts/test_full_visual_render_export_validation.py` (synthetic temp dirs + a few fake-PNG bytes;
  a tiny *valid* 1×1 PNG is generated at runtime for the DOCX embed check — nothing committed). Part A (pure, always runs):
  discovers all 5 referenced figures (not 2), legacy helper still stops at 2, dedupe + deterministic order, missing
  skipped, all-unsafe rejected, defensive ceiling holds, `limit` honoured. Part B (HTML): all 5 refs survive, one `<img>`
  each, no leak. Part C (DOCX, skips when python-docx absent on host): embeds all 5 present, safe marker for the missing
  one, no path leak. Part D (bundle, skips when FastAPI absent on host): all 5 ride along (not 2), missing skipped, unsafe
  never bundled, manifest records safe relative refs only and leaks no bytes/path/url/base64.
- **Validation:** host `test_full_visual_render_export_validation.py` 22/0 (DOCX+bundle skipped), full **41/0 in Docker**;
  legacy export asset 9/0 host / 28/0 Docker; full insertion v2 81/0; inclusion planner 179/0, plan artifact 64/0, manifest
  65/0, coverage E2E 79/0, caption polish 132/0, multifigure 63/0, quality gate 50/0; `compileall api pipeline test_scripts`
  clean; `git diff --check` clean; Docker build + health + `smoke_release.py` 29/0. Chandra remains blocked by its own
  live-validation gate. **Slice 91 is NOT committed.**

---

## Slice 90 — **Full non-table figure insertion v2**, on `slice90-full-non-table-figure-insertion-v2`. **COMMITTED `096148f` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Moves from coverage/control into actual guide-generation behavior.** Slices 82–89 built and exposed the Full Material
  Coverage foundation (planner core, plan artifact, table-policy core, coverage E2E, Builder exclusion UI, JobDetails
  display, controls/warnings). Slice 89 was committed `b879590`, fast-forward merged, and pushed to trunk on
  `chrome-renderer-v1`. Slice 90 turns *planned* non-table visuals into *inserted* guide content: when visuals are enabled
  it inserts **all useful planned non-table figures from included pages** (subject to the deterministic Slice 83 safety
  filtering) instead of the legacy top-1/top-2 visual-pilot cap. It is **not** "insert every crop": table-like,
  decorative/logo/header/background, tiny, blank, unsafe, and unmappable records are still skipped. No table reconstruction;
  no prompt/provider/model/cloud change; no UI; no render/export code change.
- **Gate (unchanged two-key AND, plus a mode switch).** Insertion still requires BOTH the env master switch
  (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT`) AND the per-job opt-in (`visual_markdown_image_pilot`). On top of that,
  the new server-side **mode switch** `GUIDEFORGE_ENABLE_FULL_VISUAL_INSERTION` (off by default) selects the plan-driven
  full path; with it off the legacy capped pilot runs **byte-identical**. The mode switch can never enable insertion on its
  own. Default deployment output is unchanged.
- **Safe candidate mapping (Slice 84 deferral resolved).** The planner now emits a safe generated `candidate_id`
  (`pipeline/visual_inclusion_planner.candidate_id_for_manifest_position` → `"visual_candidate_NNNN"`, a fixed-shape
  positional ordinal, never a slug/path/filename/ref). Insertion walks the manifest once to build `{candidate_id: record}`
  by the same positional formula, then resolves each plan item back to its sanitized manifest record without any path/slug.
  The plan public schema gains exactly this one safe field; everything else is the Slice 83 closed-token schema.
- **Insertion path** (`pipeline/visual_markdown_insertion.py`): new `is_full_visual_insertion_enabled()`,
  `select_full_visual_markdown_candidates(job, *, manifest, plan)` (ordered, de-duplicated by candidate_id + asset slug,
  each record re-validated by the **unchanged** hard gates: `fitz_local` `extracted_figure` only, safe `assets/<slug>.png`
  ref, real file inside the job dir, never Chandra/Mistral/page-signal), and `_apply_full_visual_insertion(job, text)`.
  Reuses the existing `insert_visual_markdown_references` placement (source-page anchor when present, else one trailing
  `## Visual References` section). **Captions forced to the generic page-derived convention** (`None` →
  `![Extracted figure from source page N]` + `*Source visual, page N.*`) so a future manifest `caption`/OCR fragment can
  never ride into the guide. Degrade-never-fail: unmappable/missing/all-skipped degrades to a closed skip reason and the
  original guide; a job never fails because of insertion.
- **Files changed:** `pipeline/visual_inclusion_planner.py` (+`candidate_id`), `pipeline/visual_markdown_insertion.py`
  (full-insertion path), `test_scripts/test_full_visual_insertion_v2.py` (new), `test_scripts/test_visual_inclusion_planner.py`
  + `test_scripts/test_visual_inclusion_plan_artifact.py` (schema now allows the safe `candidate_id`), and the three docs.
  `visual_inclusion_plan_artifact.py` is unchanged (it inherits the planner schema). `run_llm_job.py` / `run_markdown_job.py`
  unchanged — the insertion wiring point (`apply_visual_markdown_pilot` just before `save_clean_md`) already covers both the
  LLM and raw-markdown paths.
- **Validation:** `test_full_visual_insertion_v2.py` 81/0 (5-figure insert-all, table/decorative/tiny/blank/unsafe skipped,
  excluded-page absence, deterministic order, safe mapping, unmappable/all-unmappable degrade, dedupe, safe captions,
  sanitized public plan, mode-off legacy, import hygiene). Reran inclusion planner 179/0, plan artifact 64/0, manifest 65/0,
  manifest-planning 47/0, coverage E2E 79/0, pilot trace 56/0, caption polish 132/0, multifigure 63/0, quality gate 50/0,
  export asset 9/0, table policy 145/0, legacy insertion 53/0. `compileall api pipeline test_scripts` clean. Docker build +
  health + `smoke_release.py` 29/0 (default output unchanged). Chandra remains blocked by its own live-validation gate.
  **Slice 90 was committed `096148f`, fast-forward merged, and pushed to `chrome-renderer-v1`. Slice 91 (above) validates
  PDF/DOCX/HTML/export with many figures.**

---

## Slice 89 — **Full Material Coverage controls and warnings**, on `slice89-material-coverage-controls-warnings`. **COMMITTED `b879590` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Final user-facing warning/control polish before Slice 90 full non-table figure insertion v2.** Slice 88 was
  committed `769d1f5`, fast-forward merged, and pushed to trunk on `chrome-renderer-v1` (it added the read-only JobDetails
  "Material Coverage" display). Slices 87–88 let users *set* per-attachment page/slide exclusions and *see* coverage
  counts after a job. Slice 89 adds the honest **controls + warnings** layer so the user clearly understands which
  attachments have active exclusions, how many pages/slides are excluded, that exclusions apply to guide content **and**
  visual/table planning, that the separate `page_selections` is preserved, and — critically — that full figure insertion
  and table reconstruction are **not enabled yet** (no overpromising).
- **Frontend UX/control slice only.** No backend change: extraction logic, material page-selection application,
  visual-manifest filtering, visual inclusion planning, table policy, render/export/prompt/provider behavior, and
  visual-pilot ranking/classification/cap/default/two-key-gate/caption are all untouched. **No new backend field; the
  Slice 87 submit payload shape is unchanged.** No table reconstruction; no all-visual insertion/rendering.
- **New pure helper** `frontend/src/materialCoverageWarnings.js` (React-free, node-testable):
  - `buildBuilderMaterialCoverageSummary({ exclusionInputs }) → { active, attachmentsWithExclusions, totalExcludedPages,
    hasInvalidTokens }` — consumes the **positional** ordered array of raw exclusion-input strings (the same array the
    submit path maps from `attachments`); emits **counts + a boolean invalid flag only**. Never carries filenames, paths,
    page numbers, or the raw invalid tokens the user typed. Reuses `parsePageListInput` for parsing.
  - `buildJobMaterialCoverageNotes(displayModel) → [{ token, tone, text }]` — derives a fixed, deterministic, **closed
    vocabulary** of honest note strings from the Slice 88 display model: selections applied, useful visuals planned
    (insertion is a later step), table reconstruction not enabled yet, and a calm "artifacts may be unavailable for older
    jobs" note. Never echoes raw artifact warning text; tolerates missing/malformed models.
- **Builder controls/warnings** (`frontend/src/components/BuilderWorkspace.jsx`): a compact `MaterialCoverageControls`
  block rendered once below the attachment list whenever ≥1 paginated attachment is present. Shows the active/inactive
  state, the local summary (`"N attachments have exclusions. M pages/slides will be skipped."`), a generic invalid-token
  hint (`"Some entries were ignored. Use numbers or ranges like 2, 4-6, 10."` — never the raw token), the scope note
  (`"Exclusions apply to guide source text and visual/table coverage planning."`), the honest limitation copy (`"Full
  figure insertion and table reconstruction are not enabled yet; this job will still record coverage signals for them."`),
  and a **"Clear exclusions"** button that resets the parent's raw-input state. The block consumes the positional summary
  only — it never persists filenames/paths as keys and never changes the submit payload shape.
- **JobDetails warnings** (`frontend/src/components/MaterialCoveragePanel.jsx`): a new "What this means" section renders
  the closed-vocab notes from `buildJobMaterialCoverageNotes`, computed only once both artifact fetches settle (so no
  premature "unavailable" flash). 404/missing artifacts stay calm; no scary error language; no raw artifact warnings.
- **CSS** `frontend/src/design-system.css`: `.sg-coverage-controls*` (Builder block) and `.sg-coverage-note*` (JobDetails
  notes) — calm, count/status-only surfaces, no per-source detail.
- **Validation:** new node harness `frontend/scripts/verify-material-coverage-warnings.mjs` (added to `npm run test` +
  `test:material-coverage-warnings`) covers inactive/active summaries, attachment + total page counts, invalid-token
  generic flag (no raw value), cleared = empty deterministic state, positional/no-filename-leak, notes for active
  selections / available plan / deferred table reconstruction / missing artifacts, malformed-model tolerance, hostile
  canary no-leak, and determinism. `npm run build` + full frontend suite pass; existing
  `verify-material-page-selections-ui.mjs` / `verify-material-coverage-display.mjs` still pass. Python regressions green
  on host. Docker build + health + `smoke_release.py` 29/0. **Slice 89 is NOT committed.**

---

## Slice 88 — **JobDetails material coverage display**, on `slice88-jobdetails-material-coverage-display`. **COMMITTED `769d1f5` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **First read-only surface for the Full Material Coverage signals.** Slice 87 was committed `844e394`, fast-forward
  merged, and pushed to trunk on `chrome-renderer-v1` (it added the Builder UI for per-attachment page/slide exclusions).
  Slices 76–86 built + validated the backend that produces those signals; Slice 87 let users *set* exclusions. Slice 88
  adds a **read-only** "Material Coverage" tab in Job Details so a user can *see*, after a job finishes, safe coverage
  information: whether material page selections were present, page coverage counts (covered / embedded-text / OCR /
  unreadable) from `source_coverage_report.json`, how many useful non-table visuals were planned and how many table-like /
  unsafe candidates were skipped from `visual_inclusion_plan.json`, plus a static deferred table-policy note.
- **UI display only.** No backend change at all. Extraction/OCR routing, material page-selection application,
  visual-manifest filtering, visual inclusion planning, table policy, render/export/prompt/provider behavior, and
  visual-pilot ranking/classification/cap/default/two-key-gate/caption are all untouched. No table reconstruction; no
  all-visual insertion/rendering. It consumes only already-safe job-response fields and **exact-name** artifact fetches.
- **New pure helper** `frontend/src/materialCoverageDisplay.js` (React-free, node-testable):
  - `summarizeMaterialSelections(job)` — counts attachments carrying an explicit include/exclude page set (positional
    `attachment_<index>` keys only) + the global selection; reports `active`/`inactive`. Never reads a key/filename/page.
  - `summarizeSourceCoverage(report)` — closed-vocab status + non-negative page counts from the report `summary`.
  - `summarizeVisualInclusionPlan(plan)` — closed-vocab status + planned / table-like-skipped / unsafe-skipped counts.
  - `buildMaterialCoverageDisplayModel({ job, sourceCoverageReport, visualInclusionPlan })` — composite safe model; null
    reports degrade to a neutral `unavailable` section (never an error); table policy note is a static deferred string.
  - All summarizers tolerate missing/malformed input, never throw, emit only counts/booleans/closed status tokens, and
    pass status through an allowlist so no free-form text rides out.
- **New panel** `frontend/src/components/MaterialCoveragePanel.jsx`: fetches `source_coverage_report.json` and
  `visual_inclusion_plan.json` by **exact name** via the existing `getJobArtifact` / `artifactUrl` helpers (404 ⇒ calm
  "not available", never an error), reads `material_page_selection(s)` from the already-safe job response, and renders
  count tiles + status tags. Exact-name artifact links use the existing safe URL only. Wired into `RecentJobsPanel.jsx`
  as a new "Material Coverage" drawer tab (icon `Gauge`); new neutral `.sg-tag-slate` tag added to `design-system.css`.
- **No backend / client.js change.** The artifact route already serves both exact names (`api/server.py` `_artifact_path`)
  and `getJobArtifact` already does exact-name JSON fetch — so no new route and no client helper were needed.
- **Validation:** new node harness `frontend/scripts/verify-material-coverage-display.mjs` (added to `npm run test` +
  `test:material-coverage-display`) covers missing/malformed degradation, count summaries, safe-key-only active counting,
  hostile canary no-leak over the display model, and determinism. `npm run build` + full frontend suite pass. Python
  regressions green on host (material coverage E2E 79/0, source coverage report 59/0, source coverage artifact 45/0,
  inclusion planner 178/0, plan artifact 62/0, table policy 145/0). Docker build + health + `smoke_release.py` 29/0.
  Committed `769d1f5`, fast-forward merged, and pushed to `chrome-renderer-v1`.

---

## Slice 87 — **Builder UI for per-attachment page/slide exclusions**, on `slice87-builder-page-slide-exclusions-ui`. **COMMITTED `844e394` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **First UI slice on top of the Full Material Coverage backend.** Slice 86 was committed `3db8572`, fast-forward merged,
  and pushed to trunk on `chrome-renderer-v1` (it added the deterministic synthetic Material Coverage **E2E validation
  harness** that proved the whole backend chain end-to-end). Slices 78–86 proved the backend can persist + apply
  per-attachment material page selections. Slice 87 adds the **first Builder control** so a user can actually set
  per-attachment page/slide **exclusions** and submit them through the already-merged `material_page_selections` field.
- **UI-wiring only.** No backend change: extraction logic, visual-manifest filtering, visual inclusion planning, table
  policy, render/export/prompt/provider behavior, and visual-pilot cap/ranking/classification/caption are all untouched.
  The backend remains the source of truth for normalization/application.
- **New pure helper** `frontend/src/materialPageSelections.js`:
  - `parsePageListInput(input) → { pages, warnings }` — parses positive 1-based integers and simple ranges (`2, 4-6, 10`);
    dedupes + sorts; drops invalid tokens with **closed-vocabulary** local warning tokens (`page_token_invalid`,
    `page_range_invalid`, `page_range_reversed`, `page_number_invalid`) and never echoes the raw token.
  - `buildMaterialPageSelections(orderedInputs) → envelope` — maps per-attachment raw inputs **by upload order** into the
    safe envelope `{ version:1, attachments:{ attachment_<index>: { version:1, mode:"exclude", include_pages:[],
    exclude_pages:[…], warnings:[] } }, warnings:[] }`. Attachments with no exclusions are omitted; index follows upload
    order even when earlier attachments have none. Keys are **always** `attachment_<index>`, never filenames/paths.
  - `hasActiveMaterialSelections(envelope)` — the gate the Builder uses to decide whether to send the field at all.
- **Builder wiring** (`frontend/src/components/BuilderWorkspace.jsx`): new `materialExclusions` state keyed by the stable
  `attachmentKey(file)` signature (raw typed text per attachment); a small `MaterialExclusionField` rendered under each
  paginated attachment (`.pdf` / `.pptx`) with copy *"Exclude pages/slides — e.g. 2, 4-6, 10 — These pages will be skipped
  from guide content and visual/table planning."* plus a live "Excluding pages …" confirmation and generic hint text for
  invalid input (never the raw value). At submit, `attachments.map(f => materialExclusions[attachmentKey(f)] ?? "")` is
  converted to the envelope and threaded through `buildBuilderPayload → buildLlmPayload`, which adds
  `material_page_selections` **only** when at least one exclusion is active. Removing an attachment drops its entry.
- **Request path** (`frontend/src/api/client.js`): `material_page_selections` added to the multipart object-stringify
  whitelist (alongside `outline` / `include_sections` / `page_selections`) so the envelope is JSON-stringified into the
  attachment `FormData`. The JSON-only (no-attachment) path serializes it with the rest of the payload; with no active
  exclusion the field is simply absent.
- **`page_selections` untouched.** The older extraction page-range field (keyed by filename, load-bearing) is preserved
  exactly — separate state, separate field, separate UI (the preflight card).
- **Validation:** new node harness `frontend/scripts/verify-material-page-selections-ui.mjs` (added to `npm run test` and
  `test:material-page-selections-ui`) covers parse/dedupe/ranges, closed warnings, positional keys, omitted attachments,
  the active gate, determinism, and filename/path/URL/data-URI/base64 canary no-leak over the serialized payload.
  `npm run build` passes; the full frontend suite passes. Python suite green on host (material coverage E2E 79/0, model
  183/0, extraction 31/0, manifest planning 47/0, inclusion planner 178/0, plan artifact 62/0, table policy 145/0);
  FastAPI-gated tests run in Docker: `test_page_selection_request_persistence.py` 182/0, `test_page_selections.py` 24/0.
  Docker build + health + `smoke_release.py` 29/0. **Slice 87 is NOT committed.**

---

## Slice 86 — **Material Coverage E2E validation harness**, on `slice86-material-coverage-e2e-validation`. **COMMITTED `3db8572` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (validation side).** Slice 85 was committed `8a1b780`, fast-forward merged,
  and pushed to trunk on `chrome-renderer-v1` (it added the pure, stdlib-only table reconstruction/simplification **policy
  core** `pipeline/table_reconstruction_policy.py`). Slices 76–85 built the backend foundation for Full Material Coverage
  (source coverage report core/artifact; global + per-attachment material page-selection persistence; selection applied to
  text extraction and to visual-manifest planning; full non-table visual inclusion planner + artifact; table policy core).
  Slice 86 adds a **deterministic synthetic E2E validation harness** that proves these pieces work together as one chain —
  **before** any Builder UI is built on top of them.
- **Validation-only.** No UI, no new job artifact persisted, no table reconstruction, no LLM/prompt integration, no extra
  visuals inserted, no visual-pilot cap change, no render/export change, no provider/model call. The harness is pure and
  unwired: it composes already-merged pure helpers over synthetic dictionaries and asserts the result.
- **New test** `test_scripts/test_material_coverage_e2e_validation.py` validates the chain:
  `material page selection → text extraction page filtering → visual manifest page filtering → visual inclusion plan →
  table reconstruction policy → source/visual/material coverage summary`, using
  `apply_material_selection_to_page_universe` / `page_is_in_material_selection`,
  `build_visual_assets_manifest(..., page_filters=...)`, `build_visual_inclusion_plan`,
  `build_table_reconstruction_policy`, and `build_source_coverage_report`.
- **Synthetic scenario:** two attachments (`attachment_0`, `attachment_1`) with existing `page_selections` universes
  `{1,2,3,4}` and `{5,6,7,8}`; a global material selection (`exclude 2,4,6,8`); a per-attachment override on
  `attachment_0` (`include 1,9`). Effective extraction sets resolve to `attachment_0 → {1}` (override beats global; page 9
  dropped as outside the universe) and `attachment_1 → {5,7}` (global fallback). Visual sources carry signals on every
  page so the filter is exercised; enriched records add a useful figure + a table-like + a decorative + a tiny visual;
  four table-candidate dicts feed the policy.
- **Proven by assertions (79 pass / 0 fail on host):** per-attachment selection overrides the global fallback; existing
  `page_selections` caps the maximum universe and material cannot expand beyond it (page 9 dropped, out-of-universe
  include → empty + closed `material_selection_no_matching_pages`); excluded pages are absent from the extracted-content
  page plan; visual records on excluded pages are filtered out (only pages `{1,5,7}` survive, 5 filtered); the full
  inclusion plan includes **all** eligible useful non-table visuals (4, not top 1–2); decorative/tiny/table-like visuals
  are **not** planned as normal visuals; table-like records are counted by the **table policy** (all 4 handled, routed to
  `reconstruct_with_original`/`simplify_only`), never screenshot-inserted — `screenshot_insert_count` stays `0`; source
  coverage counts are deterministic and sanitized; an in-memory `material_coverage_validation` summary shape is emitted;
  a hostile-canary no-leak sweep over every stage output passes; repeated calls serialize identically.
- **In-memory summary only.** The harness emits a `material_coverage_validation` summary dict (checks + counts) for
  assertion; **no new job artifact is persisted** in this slice.
- **Scope boundaries.** Validation-only: `api/server.py`, `pipeline/run_llm_job.py`, `pipeline/job_manager.py`, the
  visual-inclusion planner/artifact, `visual_markdown_insertion.py`, renderers, exporters, prompts, providers, frontend,
  and visual-pilot ranking/classification/cap/caption files are all untouched. No API route change, no job-execution
  wiring, no extraction/OCR routing change, no render/export/prompt/provider behavior change, no visual-pilot
  ranking/classification/cap/default/two-key-gate/caption change, no table reconstruction implemented, no new artifact
  persisted, no Chandra/Mistral/Gemini/model/provider/cloud call, no direct `clean.md` write, no table manifest invented.
  Chandra remains blocked by its own live-validation gate. Docker rebuild **not required** (pure/unwired validation).
  **Slice 86 is NOT committed.**

---

## Slice 85 — **Table reconstruction/simplification policy core**, on `slice85-table-reconstruction-policy-core`. **COMMITTED `8a1b780` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (table decision side).** Slice 84 was committed `7cc9d6f`, fast-forward
  merged, and pushed to trunk on `chrome-renderer-v1` (it persisted the Slice 83 non-table plan as the exact-name artifact
  `visual_inclusion_plan.json`). The non-table planner deliberately **skips table-like material** — tables must not be
  treated as ordinary screenshot visuals. Slice 85 adds the next, still-pure step: a deterministic **policy core** that
  decides what should later happen to a table-like candidate. **No actual table reconstruction happens yet.**
- **Policy-core only.** No table content is reconstructed, no LLM/prompt is touched, no table is inserted into
  Markdown/PDF/DOCX, **no table artifact writer is added**, no UI, no OCR, no PDF/image inspection, no provider/model call.
  There is **no table manifest today and this slice invents none** — the module evaluates synthetic / sanitized
  *table-candidate-shaped* dicts only and returns a sanitized policy dict.
- **New pure module** `pipeline/table_reconstruction_policy.py` (stdlib-only, unwired):
  - `classify_table_candidate(candidate)` → sanitized per-candidate item dict;
  - `build_table_reconstruction_policy(candidates, *, max_items=None)` → sanitized policy dict
    (`version, kind, status, summary, items, warnings`).
- **Product rule encoded:** a table should generally **not** be inserted as a screenshot. Future modes (not implemented
  here) are **`reconstruct_with_original`** (original table text + a simpler/clearer version) and **`simplify_only`** (the
  simpler/clearer version only), plus **`defer`**, **`skip_unreadable`**, **`skip_unsafe`**. `screenshot_insert_count` is
  **always 0** — screenshot insertion is never the default table behavior.
- **Deterministic classification rules:** table-likeness is recognized from closed tokens
  (`table, table_like, grid_table, dense_table, table_region, table_image, tabular`) across
  `candidate_kind/visual_kind/visual_type/table_signal/kind/type/asset_type`; non-table records are **never** treated as
  table screenshots (warned `not_table_like`, no item). For a table-like record: unsafe → `skip_unsafe`; missing/invalid
  `source_page` → `defer` (closed warning); insufficient structure → `skip_unreadable`; low confidence → `defer`;
  otherwise text-layer present → `reconstruct_with_original`, text-layer absent/unknown (with structure) → `simplify_only`.
- **Preserve list (closed/deterministic):** `headers, column_labels, row_labels, exam_terms, numeric_values, units` —
  `exam_terms` always kept; header/numeric signals add the rest in fixed order. Skip/defer items carry an empty preserve.
- **Default = handle ALL candidates** (not top-1/2). `max_items` is a defensive ceiling only, default `None`; when passed
  it truncates in input order, sets `status: partial`, and records `max_items_applied`.
- **No-leak / safety:** emits only closed tokens, ints, `None`, fixed strings — verified by hostile-canary fields
  (path/title/caption/ocr/table-text/image-ref/asset-id/url/token/argv/socket/model-path/base64/data-uri) the policy reads
  for decisions and never echoes. Total/pure: never raises; malformed input → safe skipped policy.
- **Tests:** new `test_scripts/test_table_reconstruction_policy.py` — **145 passed, 0 failed** on host. Covers
  missing/malformed → skipped, non-table-not-a-screenshot, reconstruct-with-text+structure, simplify-without-text,
  dense/generic table recognition, missing/invalid `source_page` defer, insufficient-structure skip, unsafe skip, low-conf
  defer, screenshot_insert==0, closed/deterministic preserve, default-handles-all (7 of 7), `max_items` ceiling +
  reindex, determinism, schema whitelist, hostile-canary no-leak, and stdlib-only/unwired import hygiene. Slice 83 planner
  (178/0), Slice 84 artifact (62/0), visual-assets-manifest (65/0), page-selection-manifest-planning (47/0) all still
  green.
- **Scope boundaries.** Pure policy core only: `api/server.py`, `pipeline/run_llm_job.py`,
  `pipeline/visual_inclusion_planner.py`, `pipeline/visual_inclusion_plan_artifact.py`,
  `pipeline/visual_markdown_insertion.py`, renderers, exporters, prompts, providers, frontend all untouched. No API route
  change, no job-execution wiring, no extraction/OCR routing change, no render/export/prompt/provider behavior change, no
  visual-pilot ranking/classification/cap/default/two-key-gate/caption change, no Chandra/Mistral/Gemini/model/provider/
  cloud call, no direct `clean.md` write, no table manifest invented. Chandra remains blocked by its own live-validation
  gate. **Slice 85 is NOT committed.**

---

## Slice 84 — **Persist visual inclusion plan artifact**, on `slice84-visual-inclusion-plan-artifact`. **COMMITTED `7cc9d6f` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (persistence side).** Slice 83 was committed `72e1f87`, fast-forward merged,
  and pushed to trunk on `chrome-renderer-v1` (it added the pure, stdlib-only **full non-table visual inclusion planner
  core** — `build_visual_inclusion_plan(...)`). Slice 84 wires that planner output into backend job artifacts as the safe
  exact-name artifact `visual_inclusion_plan.json`, derived **only** from the already-sanitized
  `visual_assets_manifest.json`. No Markdown insertion / render / export / UI / provider wiring yet.
- **New writer** `pipeline/visual_inclusion_plan_artifact.py`: `write_visual_inclusion_plan(job, visual_manifest=None)`.
  Builds the Slice 83 plan, serializes deterministic JSON (`indent=2, sort_keys=True`) through `job.save_text(...)`, and
  is **degrade-never-fail** — any disk-write failure prints a safe message (`type(exc).__name__` only, no raw exception)
  and returns the in-memory plan; generation continues.
- **New `Job.visual_inclusion_plan_json`** (`<job>/visual_inclusion_plan.json`), modeled on the other advisory siblings:
  exact-name download only, never in `ARTIFACTS` / generic UI rows / export selectors / `VISUAL_ADVISORY_EXPORT_ARTIFACTS`,
  never gates job status.
- **Exact-name download** added to `api/server.py` `_artifact_path` (`application/json`), mirroring
  `source_coverage_report.json`. **Deliberately NOT** added to `ARTIFACTS`, `_artifact_urls`, `_artifact_details`,
  `EXPORT_ARTIFACTS`, `EXPORT_ARTIFACT_ALIASES`, or the export ride-along tuple. No generic JobDetails/export surfacing.
- **Integration point:** `run_llm_job._attach_sources`, immediately after the visual-assets manifest is written and read
  back (`visual_manifest_obj`), alongside the existing manifest-derived scoring/replacement-plan writers, via the wrapped
  `_write_visual_inclusion_plan_safely(...)`. Written exactly when the manifest is written; non-PDF / no-extraction jobs
  omit it (no call). A missing/skipped/malformed manifest yields a safe **skipped** plan via the pure planner.
- **Default = plan ALL eligible non-table visuals** (not top-1/2): the artifact inherits the Slice 83 contract verbatim.
  **Table-like records are skipped and counted** (`table_like_skipped_count`); decorative/logo/header/footer/background/
  watermark/tiny/blank/low-information/unsafe/unknown records are skipped per Slice 83 signals.
- **Candidate mapping deferred.** Slice 84 keeps the Slice 83 plan schema **as-is** (smallest safe option). Items expose
  only safe closed tokens / ints / `None` (`plan_index, source_index, source_page, visual_kind, inclusion_role, reason,
  warnings`). No `candidate_id` was added; if a future insertion slice needs one it must be a **generated internal id**
  (e.g. `visual_candidate_0001`) — never a filename/path/raw image-ref/caption/OCR/source text.
- **No-leak.** The artifact emits only closed tokens, ints, `None`, fixed strings — verified by hostile-canary record
  fields (filename/title/path/text/ocr/caption/table/image-ref/asset-ref/url/argv/socket/model-path/base64/key) that the
  planner reads for decisions and never echoes.
- **Tests:** new `test_scripts/test_visual_inclusion_plan_artifact.py` — **62 passed, 0 failed** on host (the
  `api.server` exact-name section SKIPs on host where FastAPI is absent; covered in Docker). Covers writes-from-manifest,
  default-plans-all (5 of 5, not top-2), table-skip+count, decorative/tiny/blank/unsafe skip, missing/skipped/malformed
  manifest → safe skipped plan, write-failure degrade-never-fail, determinism, exact-name route + no generic/export
  exposure, `_attach_sources` wiring + writer-failure-does-not-fail-generation, schema whitelist, hostile-canary no-leak,
  no `clean.md` write. Slice 83 planner tests still **178/0**.
- **Scope boundaries.** Persistence only: no Markdown insertion (`visual_markdown_insertion.py` untouched), no table
  reconstruction (Slice 85), no PDF/DOCX render change, no export-bundle change, no prompts/providers, no frontend/UI, no
  extraction/OCR routing change, no visual-pilot ranking/classification/cap/default/two-key-gate/caption change, no
  Chandra/Mistral/Gemini/model/provider/cloud call, no direct `clean.md` write. Chandra remains blocked by its own
  live-validation gate. **Slice 84 is NOT committed.**

---

## Slice 83 — **Full non-table visual inclusion planner core**, on `slice83-full-visual-inclusion-planner-core`. **COMMITTED `72e1f87` + MERGED (ff) + PUSHED to `chrome-renderer-v1`.**

- **Full Material Coverage foundation slice (planner side).** Slice 82 was committed `fd3fb97`, fast-forward merged, and
  pushed to trunk on `chrome-renderer-v1` (it applied material page selections to **visual-assets manifest planning**, so
  visual candidates from material-excluded PDF pages never enter `visual_assets_manifest.json`). Slice 83 adds the next,
  still-pure step: a planner that decides **which non-table visuals from the already-page-filtered manifest** should be
  planned for future guide inclusion. This is the deliberate move **away from "top 1–2 visuals forever."**
- **Product goal (not "insert every crop").** Include **all useful non-table figures/diagrams/graphs/charts/instructional
  visuals from included pages, after deterministic safety filtering** — explicitly NOT every crop, logo, decorative
  header, background, tiny/blank/low-information crop, or table-as-screenshot.
- **New pure module** `pipeline/visual_inclusion_planner.py`, stdlib-only, unwired. Public API:
  `build_visual_inclusion_plan(visual_manifest: dict | None, *, max_items: int | None = None) -> dict`.
- **Plan shape:** `{version, kind:"visual_inclusion_plan", status: completed|partial|skipped, summary{...}, items[], warnings[]}`.
  Each item: `{plan_index, source_index (int|None), source_page, visual_kind (diagram|figure|graph|chart|image|unknown),
  inclusion_role (primary_visual|supporting_visual), reason:"non_table_visual_from_included_page", warnings[]}`.
  `summary` carries `source_count, candidate_count, planned_count, non_table_planned_count, table_like_skipped_count,
  unsafe_or_incomplete_skipped_count, page_count_with_planned_visuals`.
- **Default = plan ALL eligible non-table visuals.** No hard cap at 1 or 2. `max_items` is an optional **defensive
  ceiling only** (default `None`); when passed as a non-negative int and it truncates the plan, `status` becomes
  `partial` and `max_items_applied` is recorded. Any other `max_items` value is ignored.
- **Eligibility (deterministic).** A record is planned iff: it has a strictly-positive **int** `source_page`; it is not
  table-like; it is not decorative/logo/header/footer/background/watermark; it is not marked unsafe; it is not a
  low-information page (`signals.classification == "blank_or_low_text"`); it is not a tiny crop (`crop_*_px < 24`); and it
  carries a recognized non-table type. Today's manifest types `page_visual_signal` (→ supporting, kind derived from
  `has_drawings`/`has_images`) and `extracted_figure` (→ primary, kind `figure`) are non-table; explicit future kind
  tokens (diagram/figure/graph/chart/image/plot/illustration) are honored, with `plot→graph`, `illustration→figure`.
- **Table-like skip.** Records typed `table`/`table_like`/`grid_table`/`dense_table`/`table_region`/`tabular`/`table_image`
  are **skipped** and counted in `table_like_skipped_count`. Table belongs to the later table reconstruction/simplification
  policy slice — **never** screenshot insertion here. Table wins over any co-present figure token (conservative).
- **Unknown visual type rule (documented).** A record with no recognized type token at all is **skipped** with
  `visual_type_unknown` (the safer choice; today's real manifests only ever emit `page_visual_signal`/`extracted_figure`,
  so this only affects future/hostile records and never reduces real coverage).
- **Ordering.** Deterministic by `source_index` (when present), then `source_page`, then original manifest position — a
  stable sort that reproduces the manifest's existing source-then-page order. Exact-duplicate records (same internal
  `asset_id`) are collapsed; that id is used for dedupe **only** and is never emitted.
- **Closed warning/status tokens:** `manifest_missing`, `manifest_malformed`, `manifest_skipped`, `record_malformed`,
  `source_page_missing`, `source_page_invalid`, `visual_type_table_skipped`, `visual_type_unknown`,
  `visual_record_unsafe`, `visual_record_decorative`, `visual_record_low_information`, `visual_record_tiny`,
  `max_items_applied`. No raw exception strings.
- **No-leak.** The plan emits only closed tokens, ints, `None`, and fixed strings. No filename/path, document/OCR/caption/
  table text, image ref, asset ref/asset id, image bytes, base64/data URI, provider payload, token, URL, argv, socket
  path, model path, or raw exception can survive — input fields are read for decisions only and never echoed. Verified by
  hostile-canary tests.
- **Tests:** new `test_scripts/test_visual_inclusion_planner.py` — **178 passed, 0 failed** on host. Covers missing/
  malformed/skipped/empty manifests, non-table planning, table/decorative/low-info/tiny/unsafe skips, unknown-type rule,
  missing/invalid `source_page`, manifest-order preservation, default-plans-all (7 of 7, not top-2), `max_items` ceiling,
  dedupe, determinism, schema whitelist, hostile-canary no-leak, and stdlib-only import hygiene.
- **Scope boundaries.** Planner-core only and **unwired**: not imported by generation, Markdown insertion, renderers,
  exporters, prompts, `api/server.py`, or the frontend. No artifact persisted yet (that is Slice 84). No table
  reconstruction (Slice 85). No visual-pilot ranking/classification/cap/default/two-key-gate/caption change. No
  extraction/OCR routing change. No render/export/prompt/provider change. No Chandra/Mistral/Gemini/model/provider/cloud
  call. No direct `clean.md` write. Chandra remains blocked by its own live-validation gate. **Slice 83 is NOT committed.**
- **Roadmap framing (Slices 83–86 = Full Material Coverage backend foundation):** **Slice 83** full non-table visual
  inclusion planner core (this) · **Slice 84** persist `visual_inclusion_plan.json` (safe exact-name artifact; may carry
  stable safe candidate IDs + source page numbers, never raw image refs/filenames/text) · **Slice 85** table
  reconstruction/simplification policy core · **Slice 86** material-coverage E2E validation. **No UI** until the backend
  chain proves page selections apply consistently to content extraction, visual candidates, table candidates/policy, and
  coverage reporting.

### Prior position (Slice 82 — committed & merged)

## Slice 82 — **Apply material page selections to visual/table manifests**, on `slice82-apply-material-page-selection-to-visuals`. **COMMITTED `fd3fb97` + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**

- **Full Material Coverage foundation slice (visual side).** Slice 81 was committed `7ca109d`, fast-forward merged, and
  pushed to trunk on `chrome-renderer-v1` (it applied material selections to attachment **text extraction / content
  planning**). Slice 82 applies the **same** effective page selection to **visual-assets manifest planning**, so visual
  candidates from material-excluded PDF pages never enter the manifest.
- **What it does.** In `_attach_sources` (`pipeline/run_llm_job.py`), the slice now keeps a per-metadata-source list
  `visual_page_filters` in lockstep with `extraction_metadata_sources`. Each entry is the **effective post-material
  allowed page set** (the *same* set Slice 81 computed for extraction) when a material selection was **applied** for that
  attachment, or `None` (no active filter ⇒ existing visual-manifest behaviour). It is passed as the new
  `page_filters=` kwarg to `write_visual_assets_manifest`.
- **Manifest-level filter.** `build_visual_assets_manifest(sources, extracted_assets, *, page_filters=None)` drops a
  page-level `page_visual_signal` candidate whose `source_page` is not in its source's allowed set, BEFORE it becomes a
  manifest record. `page_filters=None` / absent ⇒ output byte-identical to before Slice 82.
- **Missing/invalid `source_page`.** Under an active filter, a candidate whose `source_page` cannot be verified (≤ 0)
  is **dropped conservatively** (`material_selection_visual_page_unknown`) so a user-excluded page can never surface a
  visual. With no active filter the candidate is kept (unchanged). On the live path page candidates always carry a valid
  physical page number, so this only affects hostile/synthetic input.
- **Interaction with the load-bearing `page_selections`.** The effective allowed set is Slice 81's
  intersection(`page_selections` universe, material selection), so a material selection can never keep a visual record on
  a page `page_selections` already excluded, nor expand visuals beyond it. `exclude`/`all` with no known universe defers
  (no filter; existing behaviour) exactly as extraction does.
- **Precedence per attachment:** per-attachment `material_page_selections.attachments.attachment_<i>` → global
  `material_page_selection` → default-all — identical to Slice 81 (the filter reuses the same resolution).
- **New pure helper** `page_is_in_material_selection(source_page, allowed_pages)` in `pipeline/page_selection_model.py`
  returns `{kept, status}` (closed token or `None`); stdlib-only, never raises.
- **Warning/status tokens (closed):** `material_selection_visual_filtered`, `material_selection_visual_page_unknown`,
  `material_selection_visual_no_matching_pages` (a source whose every candidate was filtered out → still a `completed`
  manifest, never a failure), plus `material_selection_table_manifest_not_present` reserved for the future table layer.
  A new `summary.pages_filtered_by_material_selection` int records how many candidates were dropped. No page lists,
  filenames, paths, captions, image refs, or text appear in any warning.
- **Table manifests.** There is **no separate table manifest / table-extraction artifact today** — the only visual
  artifact is `visual_assets_manifest.json`. Table-manifest page filtering is therefore **deferred** to a future table
  extraction/reconstruction layer (the reserved token documents it honestly); Slice 82 invents no table artifact.
- **Extracted figures (gated, off by default)** already receive the material-filtered `pages` at extraction time
  (Slice 40 path), so they are restricted upstream; the explicit manifest filter targets the live `page_visual_signal`
  path. Documented in DECISIONS.
- **What changed:** `pipeline/page_selection_model.py` (new pure helper + closed tokens), `pipeline/visual_assets_manifest.py`
  (`page_filters` kwarg + per-source filter + summary count + closed warnings), `pipeline/run_llm_job.py` (build
  `visual_page_filters`, pass to the manifest writer), and new
  `test_scripts/test_page_selection_visual_manifest_planning.py`. `api/server.py` unchanged (Slice 80 wired the request
  fields).
- **Scope boundaries.** No Builder UI. No all-figures planner. No table reconstruction. No visual-pilot
  selection/ranking/classification/cap/default/two-key-gate/caption change (the pilot may simply see fewer candidates
  when a selection excludes pages — the cap is unchanged). No extraction/OCR routing change beyond the intended visual
  manifest page filtering. No render/export/prompt/provider behavior change. No Chandra/Mistral/Gemini/model/provider/cloud
  call. No direct `clean.md` write (still via `JobManager.save_clean_md`). Chandra remains blocked by its own
  live-validation gate. **Slice 82 committed `fd3fb97`, fast-forward merged to `chrome-renderer-v1`, and pushed.**
  Validated: host suite green; Docker `test_page_selection_request_persistence.py` 182/0 and `test_page_selections.py`
  24/24; Docker rebuild + `/api/health` + `smoke_release.py` 29/0/0.

### Prior position (Slice 81 — committed & merged)

- **Apply material page selections to extraction/content planning**, on
  `slice81-apply-material-page-selection-to-extraction`. **COMMITTED `7ca109d` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED.**
- Slice 81 is the first slice that **applied** the persisted material selection — to attachment **text extraction /
  content planning only**.
- **What it does.** In `_attach_sources` (`pipeline/run_llm_job.py`), for each PDF attachment it resolves the active
  material selection and filters which pages `extract_file(path, pages=...)` reads, so only selected pages reach the
  model-facing source text. Nothing else changes.
- **Precedence per attachment:** per-attachment `material_page_selections.attachments.attachment_<i>` (by request
  attachment order, 0-based) → global `material_page_selection` → default-all. A per-attachment entry wins outright when
  present (even default-all, which then suppresses the global fallback).
- **Interaction with the load-bearing `page_selections`.** The existing filename-keyed `page_selections` page-range
  field still defines the **maximum** page universe. A material selection can only **further filter** that universe; it
  never expands extraction beyond it (`include` intersects the universe; `exclude`/`all` subtract from it). When there is
  no `page_selections` universe and the selection is `exclude`/`all` (which need a known universe to enumerate),
  filtering is **deferred** (extraction unchanged) with a closed warning — pages are never guessed. `include` selections
  are always applied because the include list is itself an explicit page set.
- **New pure helper** `apply_material_selection_to_page_universe(material_selection, *, existing_allowed_pages=None,
  natural_pages=None)` in `pipeline/page_selection_model.py` returns `{included_pages, excluded_pages, warnings,
  resolved}` — deterministic, never raises, page-ints only.
- **Resolution helpers** `_resolve_material_selection` / `_is_active_material_selection` in `run_llm_job.py` pick the
  active selection and treat a default-all selection as a no-op (extraction byte-identical when absent/default-all).
- **Per-attachment summary.** When a material selection is active for an attachment, a safe
  `entry["material_selection"] = {"status": "applied"|"deferred"|"not_applicable", "warnings": [closed tokens]}` is
  recorded in the attachment manifest entry (counts/tokens only — no page lists, filenames, or paths). Absent/default-all
  ⇒ no field added.
- **Non-PDF attachments** are ignored safely (`material_selection_non_pdf_ignored`); current non-PDF extraction is
  unchanged.
- **Warning tokens (closed vocabulary):** `material_selection_applied`, `material_selection_no_matching_pages`,
  `material_selection_non_pdf_ignored`, `material_selection_universe_unknown`,
  `material_selection_filtered_by_existing_page_selection` (plus `material_selection_invalid_attachment_key` reserved at
  the Slice 80 normalization layer).
- **What changed:** `pipeline/page_selection_model.py` (new pure helper), `pipeline/run_llm_job.py` (apply in
  `_attach_sources`; new resolution helpers; threaded the two material params from `run_llm_job`), and new
  `test_scripts/test_page_selection_extraction_planning.py`. `api/server.py` unchanged (Slice 80 already wired the
  request fields).
- **Scope boundaries.** No Builder UI. No application to visual/table manifests, no all-figures planner, no table
  reconstruction. No visual-pilot selection/ranking/classification/cap/default/two-key-gate/caption change. No
  render/export/prompt/provider behavior change (generated guide text differs only as a consequence of less source text
  when a selection is explicitly active). No Chandra/Mistral/Gemini/model/provider/cloud call. No direct `clean.md`
  write (still via `JobManager.save_clean_md`). Existing `page_selections` page-range extraction unchanged (regression:
  `test_page_selections.py` 24/24). Chandra remains blocked by its own live-validation gate.

### Prior position (Slice 80 — committed & merged)

- **Per-attachment material page-selection persistence**, on `slice80-per-attachment-material-page-selections`.
  **COMMITTED `55eb243` + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- Slice 80 added the future-facing per-attachment `material_page_selections`
  persistence shape so the next Builder UI slice has a correct backend model to save into. It is
  still applied to nothing.
- **Persisted field:** new top-level `material_page_selections` on `LLMJobRequest`, persisted as a deterministic
  **envelope**: `{"version": 1, "attachments": {"attachment_0": <Slice 78 normalized model>, ...}, "warnings": []}`.
  Keys are SAFE internal attachment indices only (`attachment_<index>`, in request attachment order) — **never**
  filenames/paths/titles. Each value is normalized through `normalize_page_selection`. An envelope (not a flat map) was
  chosen so the "ignored unsafe key" closed warning has a home without ever copying the offending key into output.
- **Why an envelope vs. a flat map.** A flat `{key: model}` map has nowhere safe to record `attachment_key_invalid`
  without echoing the (potentially filename) key it rejected. The envelope carries a top-level closed-vocabulary
  `warnings` list (`selections_malformed`, `attachment_key_invalid`) while keeping per-attachment models intact. The
  normalizer accepts BOTH a flat client map and the persisted envelope on input, so retry round-trips.
- **Precedence (documented, not yet applied):** `material_page_selections` is the preferred per-attachment intent;
  the Slice 79 top-level `material_page_selection` remains the global fallback/default. Both are persisted (after
  normalization) when supplied. Neither is merged into extracted page ranges yet.
- **What changed:** `api/server.py` (new `LLMJobRequest.material_page_selections` field; `_MATERIAL_ATTACHMENT_KEY_RE`;
  `_normalize_material_page_selections` + `_material_selections_envelope` + `_safe_material_page_selections` helpers;
  wired into the JSON handler, the multipart `_parse_llm_request` branch, the retry path, and both
  `job_response`/ask-context echoes) and `pipeline/run_llm_job.py` (new `material_page_selections` param persisted in
  the `Job.create` manifest). Extended `test_scripts/test_page_selection_request_persistence.py` with per-attachment
  helper + endpoint coverage.
- **Both request paths wired + tested** (JSON body and multipart-with-attachments), per the permanent rule.
- **Absent ⇒ byte-identical output.** Absent/None ⇒ empty envelope `{version:1, attachments:{}, warnings:[]}`; job
  artifacts unchanged. Malformed top-level ⇒ empty envelope + `selections_malformed`. Unsafe/filename/path/title keys ⇒
  dropped + `attachment_key_invalid` (key never persisted). Bad entry value / unknown mode / invalid pages ⇒ degrade via
  the pure model's own per-entry warnings. Multipart bad-JSON ⇒ empty envelope. Never raises a 400.
- **Existing behaviour preserved.** The load-bearing, filename-keyed `page_selections` PDF page-range field and Slice 79
  `material_page_selection` are unchanged — verified by `test_page_selections.py` (24/24) and the existing Slice 79
  cases (still passing).
- **Safety.** Persisted/echoed envelope carries only `version`, safe `attachment_<index>` keys, normalized models
  (mode + sorted/deduped positive 1-based ints + closed warnings), and closed top-level warnings. No filenames, paths,
  document text, OCR text, captions, table text, image refs/bytes, base64/data URI, provider payloads, tokens, raw argv,
  sockets, model/mmproj/executable paths, URLs, or raw exception messages — verified with hostile-canary tests over the
  manifest and the response.
- **Scope boundaries.** No frontend/UI. The model is applied to NOTHING — no extraction/OCR routing, content/guide
  generation, visual manifest, render, export, or prompt change. No visual-pilot selection/ranking/classification/cap/
  default/two-key-gate/caption change. No Chandra/Mistral/Gemini/model/provider/cloud call. No direct `clean.md` write
  (all `clean.md` writes still via `JobManager.save_clean_md`). Page-exclusion application, all-figures planner, and
  table reconstruction remain documented future direction only. Chandra remains blocked by its own live-validation
  gate.

### Prior position (Slice 79 — committed & merged)

- **Persist page/slide selection with job requests**, on `slice79-page-selection-request-persistence`. **COMMITTED
  `d4d2513` + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- Slice 79 persisted the top-level `material_page_selection`
  normalized model with job requests/manifests so later slices can apply it to extraction/content planning, visual/table
  manifests, and Builder UI. It is still NOT applied to anything yet.
- **Persisted field:** new top-level `material_page_selection` on `LLMJobRequest` — the Slice 78 normalized shape
  `{version, mode, include_pages, exclude_pages, warnings}`. This is a **new, future-facing** field, deliberately
  SEPARATE from the existing load-bearing, filename-keyed `page_selections` PDF page-range field (which still drives
  extraction and is unchanged). A single top-level model was chosen for the smallest safe change; per-attachment mapping
  (`material_page_selections`) is documented as the next step.
- **What changed:** `api/server.py` (new `LLMJobRequest.material_page_selection` field; `_normalize_material_page_selection`
  + `_safe_material_page_selection` helpers; wired into the JSON handler, the multipart `_parse_llm_request` branch, the
  retry path, and both `job_response`/ask-context echoes; imports `normalize_page_selection`) and `pipeline/run_llm_job.py`
  (new `material_page_selection` param persisted in the `Job.create({...})` manifest). New test
  `test_scripts/test_page_selection_request_persistence.py`.
- **Both request-construction paths wired + tested.** Per the permanent rule, the field is parsed on BOTH the JSON body
  path and the multipart-with-attachments path (`_parse_llm_request`), and both are exercised in the test.
- **Absent field ⇒ byte-identical output.** Absent/None normalizes to a clean default `mode: "all"` with no warnings;
  job artifacts are unchanged (only an extra safe manifest key is stored). Existing `page_selections` behaviour
  (normalization, 400 on bad shapes, manifest persistence, retry round-trip) is preserved — covered by the unchanged
  `test_scripts/test_page_selections.py` (24/24).
- **Degrade-never-fail.** Unlike `_normalize_page_selections` (which 400s), `material_page_selection` never raises a 400
  on malformed *content*: unknown mode → `all` + `mode_unknown`; bad page lists → dropped + `selection_malformed`/
  `page_invalid`. Multipart bad-JSON falls back to the default.
- **Safety.** The persisted/echoed model carries only `version`, `mode ∈ {all, include, exclude}`, sorted/deduped
  positive 1-based page integers, and closed-vocabulary warnings. No filenames, paths, document text, OCR text,
  captions, table text, image refs/bytes, base64/data URI, provider payloads, tokens, raw argv, sockets,
  model/mmproj/executable paths, URLs, or raw exception messages — verified with hostile-canary tests over the manifest
  and the response.
- **Scope boundaries.** No frontend/UI. The model is NOT applied to extraction/OCR routing, content/guide generation,
  visual manifest, render, export, or prompts. No visual-pilot selection/ranking/classification/cap/default/
  two-key-gate/caption change. No Chandra/Mistral/Gemini/model/provider/cloud call. No direct `clean.md` write
  (all `clean.md` writes still go through `JobManager.save_clean_md`). Page exclusion application, all-figures planner,
  and table reconstruction remain documented future direction only. Chandra remains blocked by its own
  live-validation gate.

### Prior position (Slice 78 — committed & merged)

- **Page/slide inclusion-exclusion pure model**, on `slice78-page-slide-selection-model`. **COMMITTED `ee04f55` +
  MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- Slice 78 added the pure, deterministic model for representing user-controlled page/slide inclusion and exclusion per
  attachment.
- **What changed:** new stdlib-only module `pipeline/page_selection_model.py` plus synthetic tests
  `test_scripts/test_page_selection_model.py`. No production wiring.
- **Public API:** `normalize_page_selection(selection, *, page_count=None)`,
  `apply_page_selection(page_numbers, selection)`, and `summarize_page_selection(selection, *, page_count=None)`.
- **Normalized schema:** `{version, mode, include_pages, exclude_pages, warnings}` with `mode ∈ {all, include,
  exclude}`. Pages are positive 1-based integers, deduplicated and sorted. Invalid pages are dropped with warnings;
  with a valid `page_count` out-of-range pages are dropped. `mode: all` includes all pages except exclusions; `mode:
  include` includes only listed pages (then subtracts exclusions); `mode: exclude` includes all except exclusions.
  Unknown mode degrades to `all` with a warning; an empty include list in `include` mode yields an empty included set
  with a warning.
- **Apply behavior:** `apply_page_selection(page_numbers, selection)` returns `{included_pages, excluded_pages,
  effective_mode, warnings}`. The page-number universe is normalized (positive/unique/sorted); invalid values are
  dropped with a warning; pages are never inferred when none are provided.
- **Summary behavior:** `summarize_page_selection(...)` returns counts only — `{version, mode, included_page_count,
  excluded_page_count, explicit_include_count, explicit_exclude_count, warnings}`.
- **Warning tokens (closed vocabulary):** `selection_missing`, `selection_malformed`, `mode_unknown`, `page_invalid`,
  `page_out_of_range`, `page_count_invalid`, `include_empty`, `exclude_overlaps_include`.
- **Safety:** stdlib-only, deterministic, and degrade-never-fail. It never raises and never copies filenames, paths,
  source titles, document text, OCR text, source captions, table text, image refs, image bytes, base64/data URI,
  provider payloads, tokens, raw argv, sockets, model/mmproj/executable paths, URLs, or raw exception messages.
- **Scope boundaries (pure core only):** no API route, no request/job-manifest wiring, no job execution wiring, no
  extraction/OCR routing change, no visual manifest behavior change, no render/export change, no frontend/UI, no prompt
  change, no provider/model/cloud call, no Chandra/Mistral/Gemini integration, and no `clean.md` write. No visual-pilot
  selection/ranking/classification/cap/default/two-key-gate/caption behavior change.
- **Future slices may** persist this model with job requests (now done — Slice 79), expose Builder UI controls, apply
  it to extraction/content planning, apply it to visual/table manifests, and later plan all useful non-table figures
  plus table reconstruction/simplification. Chandra remains blocked by its own live-validation gate.

### Prior position (Slice 77 — committed & merged)

- **Source coverage report artifact writer**, on `slice77-source-coverage-report-artifact`. **COMMITTED `3ebfe54` +
  MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**
- **Foundation for revised Full Material Coverage direction.** Slice 76 was committed, fast-forward merged, and pushed
  to trunk as `91e3845`. Slice 77 persists its pure report as the exact-name job artifact
  `source_coverage_report.json`, the first foundation artifact for future page/slide include-exclude controls,
  all useful non-table figure/diagram/graph inclusion from included pages, table reconstruction/simplification, and
  coverage-aware guide generation.
- **What changed:** new writer `pipeline/source_coverage_artifact.py`, new `Job.source_coverage_report_json`, exact-name
  download mapping in `api/server.py`, and `_attach_sources` wiring in `pipeline/run_llm_job.py` after extraction
  metadata and the optional visual manifest are available. The writer consumes
  `build_source_coverage_report(extraction_metadata, *, visual_manifest=None)`.
- **Artifact behavior:** writes deterministic JSON at `<job>/source_coverage_report.json`. Completed PDF extraction
  metadata produces a completed/partial Slice 76 report; skipped/unavailable metadata produces the same safe skipped
  report schema. Visual manifest input is counts-only from sanitized `source_page` values and malformed visual input
  emits closed warnings without failing generation.
- **Safety:** the artifact is sanitized, closed-vocabulary, deterministic, and degrade-never-fail. It does not copy
  filenames, paths, source titles, source text, OCR text, source captions, table text, image refs, image bytes,
  base64/data URI, provider payloads, tokens, raw argv, sockets, model/mmproj/executable paths, URLs, or raw exception
  messages.
- **Scope boundaries:** no frontend/UI; no generic JobDetails row; no generic artifact list exposure; export ZIP
  inclusion deferred; no `clean.md` write; no extraction/OCR routing change; no render/export/prompt/provider/model/
  cloud behavior change; no Chandra/Mistral/Gemini call; no visual-pilot selection/ranking/classification/cap/default/
  two-key-gate/caption behavior change. Page exclusion, all-figures mode, and table reconstruction are documented
  future direction only, not implemented in Slice 77. Chandra remains blocked by its own live-validation gate.
- **Validation:** focused tests `test_scripts/test_source_coverage_report.py` and
  `test_scripts/test_source_coverage_artifact.py` passed, alongside `test_extraction_metadata.py` and
  `test_visual_assets_manifest.py`; Docker build + health + `smoke_release.py` all green before commit.

### Prior position (Slice 76 — committed & merged)
- **Slice 76 (source coverage report pure core) — COMMITTED `91e3845` + MERGED to `chrome-renderer-v1`
  (fast-forward) + PUSHED** on branch `slice76-source-coverage-report-core`. It added stdlib-only
  `pipeline/source_coverage_report.py` with public API
  `build_source_coverage_report(extraction_metadata, *, visual_manifest=None)` plus
  `test_scripts/test_source_coverage_report.py`.
- The core reads no files and imports no extraction/render/provider modules. It emits only `version: 1`,
  `kind: "source_coverage_report"`, status, summary counts, per-source counts/status, and closed warning tokens. It
  never copies filenames, paths, titles, document/OCR/table text, source captions, image refs, image bytes,
  base64/data URI, URLs, provider payloads, tokens, raw argv, socket paths, model/mmproj/executable paths, or raw
  exception messages.
- Slice 76 changed no API route, no job artifact writer, no `clean.md`, no frontend/UI, no export, no extraction/OCR
  routing, no render/prompt/provider/model/cloud behavior, and no visual-pilot behavior.

### Likely next slices after Slice 82 (documentation only)
- Slice 83 — Builder UI for per-attachment page/slide exclusions (save/load `material_page_selections`)
- Slice 84 — Full non-table figure inclusion planner
- Slice 85 — Table reconstruction/simplification policy core (introduces a real table manifest; then apply the
  Slice 82 page filter to it via `material_selection_table_manifest_not_present` → real filtering)
- Slice 86 — Table reconstruction prompt integration or E2E material coverage validation

---

## Slice 75 — **Diverse visual-pilot exit validation**, on `slice75-visual-pilot-diverse-exit-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward) + PUSHED.**

- **Validation / exit-decision slice only.** Slice 75 is intentionally **not** more caption polish, not more
  table/diagram heuristic work, and not a UI slice. It checks whether enough **diverse, manually categorized,
  non-private** operator samples are available to decide whether the default-off visual markdown pilot should remain
  opt-in, become more discoverable, or pause pending a controlled understanding layer such as Chandra. Chandra remains
  blocked by its own live-validation gate.
- **Outcome:** `diverse_visual_pilot_exit_validation: not_run`; `reason:
  non_private_diverse_samples_not_available`. An operator-local sample count was present, but no safe manual mapping
  from samples to the requested closed categories was available in this session, and the slice rules forbid guessing
  categories from local PDFs. No harness run was performed and no trace/render/export artifacts were produced.
- **Target category records (all skipped):** `math_heavy_deck`, `mostly_text_only_pdf`,
  `low_quality_or_scan_like_pdf`, `mixed_diagrams_tables_deck`, and `no_good_figures_deck` each recorded
  `status: skipped`, `skip_reason: sample_not_available`, `trace_artifact_present: not_applicable`,
  `trace_no_leak_sweep: not_applicable`, `effective_max_images: not_applicable`, `inserted_visual_count: 0`,
  all candidate/type/selected counts `0`, `selected_visual_type: none_inserted`,
  `irreplaceable_visual_selected: not_applicable`, `selected_figures_quality: none_inserted`,
  `caption_status: not_applicable`, `graceful_omission: not_applicable`, all render/export booleans
  `not_applicable`, `warnings: [sample_unavailable]`, `failure_category: sample_unavailable`,
  `no_leak_sweep: clean`.
- **Aggregate exit record:** `validated_category_count: 0`, `available_category_count: 0`, `pilot_inserted_count: 0`,
  `graceful_omission_count: 0`, `bad_selection_count: 0`, `caption_safe_count: 0`,
  `pdf_image_visible_count: 0`, `docx_render_ok_count: 0`, `export_png_included_count: 0`,
  `no_leak_sweep: clean`, `exit_recommendation: insufficient_evidence`, `exit_reason:
  diverse_validation_insufficient_sample_count`.
- **Scope / safety:** docs-only (`VISUAL_PILOT_OPERATOR_VALIDATION.md`, this file, `NEXT_CHAT_HANDOFF.md`,
  `DECISIONS.md`). No production pipeline/API/frontend code changed; no harness was added; no selection,
  classification, ranking, cap, caption, export, renderer, OCR-routing, prompt, provider/model/cloud, or UI behavior
  changed. No Chandra/model/provider/cloud call. No committed binary/image/PDF/DOCX/ZIP/runtime output, eval JSON, or
  `visual_markdown_selection_trace.json`. No sample path, filename, document text, OCR text, source caption/table text,
  image bytes, base64, data URI, full URL, provider payload, token, raw argv, model/mmproj/executable path, or raw
  exception recorded.
- **Decision:** keep the visual markdown pilot default-off / opt-in for now due insufficient diverse evidence. The
  morphology loop remains paused; the caption micro-loop is not starting. Next useful step is an operator-provided
  closed-category mapping for multiple known non-private samples, then rerun this exit-validation slice without
  changing visual behavior. **Slice 75 commit `00c3f79`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

---

## Slice 74 — **Visual caption / source-page polish (final in-lab visual-pilot polish)**, on `slice74-visual-pilot-caption-page-polish`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Small user-visible polish slice — NOT a new heuristic loop.** Slice 73 proved (on the real, non-private operator
  sample) that the pilot now selects irreplaceable diagrams/figures (`selected_visual_type: diagrams_or_figures_present`,
  `irreplaceable_visual_selected: true`). Per the operator's adjustment, Slice 74 is the **final in-lab caption/page
  polish** for the current visual pilot: it adds a safe, generic italic caption line **below** each inserted visual and
  then the morphology/classification loop stays **paused/frozen**. No selection, ranking, classification, cap, default,
  two-key gate, export, renderer, provider/model/cloud, OCR-routing, prompt, or UI behavior changed. **No separate
  caption-validation follow-up slice will be created.**
- **What changed (one file).** `pipeline/visual_markdown_insertion.py` gains a tiny `_visual_caption_line(source_page)`
  helper (returns exactly `*Source visual, page N.*` when a positive integer page is known, else the page-free
  `*Source visual.*`) and a `build_visual_markdown_block(candidate)` wrapper that appends that caption one blank line
  **below** the unchanged `build_visual_markdown_image(...)` ref. Both insertion entry points
  (`insert_visual_markdown_reference` / `insert_visual_markdown_references`) now emit the block. The caption is a fixed
  closed string + bounded integer page only — it can carry **no** source filename, path, title, raw manifest caption,
  OCR/document/extracted-table text, base64/data URI, provider payload, token, or URL regardless of input. Caption
  construction **degrades-never-fails**: any error falls back to the image ref alone (pre-Slice-74 output).
- **Invariants proven unchanged.** Image asset refs are byte-identical (the `![alt](assets/<slug>.png)` line is
  untouched; the caption is an additional italic line); selected candidate **order**, **count**, and **ranking
  outcomes** match the unmodified selector; default-off output stays byte-identical; the caption never appears unless
  **both** the master flag and per-job opt-in are on; cap stays hard-capped at **2**, default stays **1**; no UI count
  selector; export ref-scan still finds only the safe `assets/<slug>.png` refs; the Slice 68 selection trace is
  unchanged and never carries the caption text.
- **Status flags for the next session:**
  - `visual_pilot_morphology_loop_status: paused_after_real_success`
  - `visual_pilot_polish_scope: final_in_lab_caption_page_polish`
  - `next_recommended_slice: diverse_visual_pilot_exit_validation`
- **Next slice is NOT more visual polish/heuristics.** It should be a **diverse validation / exit-decision** slice across
  multiple document types (one math-heavy deck, one mostly text-only PDF, one low-quality/scan-like PDF if available, one
  deck with diagrams/tables mixed, and one deck with no good figures to verify graceful omission), to decide whether
  visual markdown stays opt-in, becomes more discoverable, or pauses pending a controlled understanding layer (e.g.
  Chandra, which remains blocked by its own live-validation gate).
- **Tests.** New `test_scripts/test_visual_pilot_caption_page_polish.py` (24-scenario coverage: caption presence,
  page label, generic fallback, no filename/path/OCR/table/base64/data-URI/token leak, cap 1 + cap 2, order, refs/count/
  ranking unchanged, default-off byte-identical, both gates off → no caption, tables-when-best + diagram-beats-table
  ranking unchanged, sanitized trace, export ride-along, PDF/DOCX render, degrade-never-fail) — **133 PASS / 0 FAIL /
  0 SKIP in the container** (host shows 1 SKIP: python-docx absent). The full visual-pilot + insertion/render/export/
  options/anki suites and the offline eval pass on host; the production image was rebuilt + recreated, `/api/health`
  `{"ok":true}`, `smoke_release.py` 29/0/0, and the visual-pilot suite (incl. the new test) re-run **inside the
  container** (Pillow + python-docx present, no skips) all green. `git diff --check` clean.
- **Optional real operator caption validation:** `caption_operator_validation: not_run`; `reason:
  non_private_operator_sample_not_available`. The non-private operator sample is not available in this session, so no
  real cap-2 caption rerun was performed and **no sanitized caption-operator result was recorded** (none invented). When
  the sample is next available, it can be inspected inside Slice 74 (no follow-up slice); record only the sanitized
  `caption_operator_validation` closed-vocab fields.
- **Safety / no-leak:** only a fixed caption string + bounded page integer is emitted into the guide; tests build every
  PNG at runtime in a temp dir — nothing binary/image/PDF/DOCX/ZIP/runtime committed; runtime eval result JSONs stay
  gitignored. No real PDF path/filename, document/OCR/table/source-caption text, image bytes, base64, data URI, full URL,
  raw argv, token, or model/mmproj/executable path recorded. **Slice 74 commit `9e92e5a`, fast-forward merged + pushed
  to trunk `chrome-renderer-v1`.**

---

## Slice 73 — **Dense-wrapped-table real operator validation**, on `slice73-visual-pilot-dense-wrapped-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Reruns the existing operator harness against the real, **non-private** operator
  sample now that **Slice 72's dense / wrapped-cell two-column table detection fix** is on trunk, then reads Slice 68's
  sanitized selection trace + manually inspects the rendered PDF/HTML/DOCX to record — closed vocabulary only —
  whether the pilot now selects at least one irreplaceable diagram/figure instead of only reconstructable tables.
  **No production pipeline/API/frontend code changed; no heuristic tuned; no ranking/cap/default/gate/render/export/
  extraction-OCR routing change; no model/provider/cloud call.** Docs-only — **no harness correction was needed.**
- **Outcome this session (the long-standing `tables_only` result finally flipped): `dense_wrapped_table_operator_validation:
  run` — `status: ok`, `trace_artifact_present: true`, `trace_no_leak_sweep: clean`, `effective_max_images: 2`,
  `inserted_visual_count: 2`, `safe_candidate_count: 11`, `unsafe_candidate_count: 0`, `selected_count: 2`,
  `type_counts {diagram_or_figure: 9, reconstructable_table: 2, unknown: 0, decorative_or_low_information: 0}`,
  `selected_visual_type: diagrams_or_figures_present`, `irreplaceable_visual_selected: true`, `selected_figures_quality:
  all_useful_or_acceptable`, `selection_explanation: diagrams_selected_after_dense_table_fix`,
  `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true`,
  `warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`, `no_leak_sweep: clean`.**
- **What unblocked it.** The trace's `type_counts` still reads `diagram_or_figure: 9` / `reconstructable_table: 2`,
  but the two reconstructable two-column definition tables that Slice 71 *selected* are now **deprioritized** behind
  the diagram tier (`rejection_reason_counts.deprioritized_reconstructable_table: 2`), so diagram-first ranking now
  reaches the genuine schematic figures. Both selected candidates are `classified_diagram_or_figure` with
  `selection_reason: selected_by_diagram_first_ranking`; manual ground-truth confirms both are legible,
  content-bearing, non-decorative graphics from distinct source pages that render visibly in PDF/DOCX and ride along
  in the export ZIP.
- **Decision gate / next work (recorded, not started):** `decision_gate: irreplaceable_diagram_selected_on_real_sample`;
  `next_recommended_slice: visual_placement_or_citation_polish_may_now_be_considered` — because an irreplaceable
  diagram/figure is finally selected on the real sample, future visual work **may** now consider placement/citation
  polish as a separately-designed slice (a *may*, not a mandate; classification precision can be revisited if other
  samples regress).
- **Hard boundaries honored:** no cap above 2 (default still **1**, cap still hard-capped at **2**), no UI count
  selector, no Chandra/Mistral/Gemini/cloud OCR, no model/provider/`llama-server` call, no image generation, no
  OCR-routing/renderer/prompt/export change, no new API route. Chandra remains blocked by its own live-validation gate.
- **Safety / no-leak:** only sanitized closed-vocab + bounded-numeric fields recorded; **no** real PDF path/filename,
  document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, provider payload, or raw exception. The runtime
  `visual_markdown_selection_trace.json` was **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 73 commit `76e837b`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

---

## Slice 72 — **Dense ruled / wrapped-cell two-column table detection**, on `slice72-visual-pilot-dense-wrapped-table-detection`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production classification slice (precision only).** Slice 71's real-sample validation showed Slice 70 measurably
  improved table-vs-diagram classification (the trace's type buckets split: `diagram_or_figure: 9`,
  `reconstructable_table: 2`, where Slice 69 read 11 / 0) but the two *selected* visuals were **still** reconstructable
  two-column definition tables. Root cause: those tables are **densely ruled with wrapped multi-line cells**, so each
  column's antialiased wrapped lines merge into too FEW separated horizontal text bands for Slice 70's `two_col_split`
  per-column band guard (≥ 3 bands) to fire — they fall through to `diagram_or_figure` and lead the diagram tier.
- **What changed:** one more bounded, deterministic, **pixel-only** signal — `dense_wrapped_two_col` — added to the
  existing `extracted_figure` crop analyzer (`pipeline/visual_markdown_insertion.py`). It does **not** rely on band
  count; it pairs the two-column structure with two guards a diagram cannot fake: a **persistent clean vertical gutter**
  (`_gutter_consistency` — a diagram's connectors/diagonals break it) and per-column **text richness**
  (`_column_text_richness` — avg ink-runs per inked row: several words per row, not a continuous shape outline). It
  fires only when there are exactly two substantial dense columns, a real persistent gutter, and both columns are
  text-rich. Wired as a fourth path inside `_looks_like_reconstructable_table`, so the public classification token and
  the Slice 68 trace schema are unchanged.
- **Effect (verified by tests):** dense / wrapped-cell / ruled / lightly-ruled two-column definition tables now
  classify as `reconstructable_table` (incl. the *merged-band* case where Slice 70's `two_col_split` cannot fire);
  labeled diagrams, flowcharts, and irregular diagrams stay `diagram_or_figure` (text presence alone never flips a
  diagram); a diagram/figure still beats a reconstructable table at cap 1 and ranks first at cap 2; tables are still
  selected when best/only. Default remains **1**; hard cap remains **2**; two-key gate, render, export ride-along,
  extraction/OCR routing, prompts, and `/api/options` all unchanged. No Chandra/Mistral/Gemini/model/provider/cloud
  call; no UI/frontend change. Chandra remains blocked by its own live-validation gate.
- **Validation:** `python -m compileall api pipeline test_scripts` clean; the new
  `test_visual_pilot_dense_wrapped_table_detection.py` (81 PASS / 0 FAIL, cap-1 and cap-2) plus the full visual-pilot
  suite, `validate_visual_pilot_operator_sample.py --self-test`, the insertion/render/export/options/anki tests, and the
  offline eval all pass on host; the production image was rebuilt + recreated, `/api/health` `{"ok":true}`,
  `smoke_release.py` 29/0/0, and the visual-pilot suite was re-run **inside the container** (Pillow present — no skips:
  multifigure 78, quality_gate 54) all green. `git diff --check` clean.
- **Optional real operator revalidation: NOT run in the Slice 72 session** — the non-private operator sample was not
  available then, so no real cap-2 rerun was performed and no sanitized operator result was recorded (none invented).
  **Slice 73 has since run that revalidation and recorded the flipped `diagrams_or_figures_present` result above.**
- **Safety / no-leak:** only bounded numeric pixel summaries and closed-vocab tokens are produced; the classifier never
  OCRs, never calls a model/provider/network, never base64/serializes/logs image bytes, records no path or source text,
  and adds **no** new artifact (the Slice 68 trace is the only one). Tests build every PNG at runtime in a temp dir —
  nothing binary/image/PDF/DOCX/ZIP/runtime committed; runtime eval result JSONs stay gitignored. **Slice 72 is
  COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

---

## Slice 71 — **Table-vs-diagram precision operator validation**, on `slice71-visual-pilot-table-diagram-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Reruns the existing operator harness against the real, **non-private** operator
  sample now that **Slice 70's table-vs-diagram classifier precision fix** is on trunk, then reads Slice 68's
  sanitized selection trace + manually inspects the rendered PDF/HTML/DOCX to record — closed vocabulary only —
  whether the pilot now selects an irreplaceable diagram/figure instead of only reconstructable tables. **No
  production pipeline/API/frontend code changed; no heuristic tuned; no ranking/cap/default/gate/render/export/
  extraction-OCR routing change; no model/provider/cloud call.** Docs-only — **no harness correction was needed.**
- **Outcome this session (honest): `table_diagram_precision_operator_validation: run` — `status: ok`,
  `trace_artifact_present: true`, `trace_no_leak_sweep: clean`, `effective_max_images: 2`, `inserted_visual_count: 2`,
  `safe_candidate_count: 11`, `unsafe_candidate_count: 0`, `selected_count: 2`,
  `type_counts {diagram_or_figure: 9, reconstructable_table: 2, unknown: 0, decorative_or_low_information: 0}`,
  `selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`, `selected_figures_quality:
  all_useful_or_acceptable`, `selection_explanation: tables_still_misclassified_as_diagram_or_figure`,
  `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true`,
  `warnings: [multiple_figures_present_one_inserted]`, `failure_category: none`, `no_leak_sweep: clean`.**
- **Slice 70 measurably improved classification but did not yet generalize.** The trace's `type_counts` is **no longer
  collapsed** — `diagram_or_figure: 9` **and** `reconstructable_table: 2` (Slice 69 read 11 / 0), and the 2 typed
  tables were correctly **deprioritized** (`deprioritized_reconstructable_table: 2`). **But manual inspection
  ground-truths that both *selected* visuals are still reconstructable two-column definition tables** — they are
  densely ruled with wrapped multi-line cells, so the Slice 70 two-column-split guard (several *separated* row bands
  per column) does not fire and they still type as `diagram_or_figure`, leading the diagram tier in priority order.
  **Genuine irreplaceable diagrams/figures were present and correctly extracted among the safe candidates but were
  NOT selected** — so this is still **classification precision**, not extraction and not pure ranking.
- **Next work (recorded, not started):** `continue_table_vs_diagram_classification_precision` — keep improving the
  deterministic local classifier for densely-ruled / wrapped-text two-column tables (or design a controlled
  understanding layer in a separate slice). **Do not** proceed to UI polish or cap expansion until an irreplaceable
  diagram/figure is selected in real validation, or there is a deliberate product decision to accept tables.
- **Hard boundaries honored:** no cap above 2, no UI count selector, no Chandra/Mistral/Gemini/cloud OCR, no
  model/provider/`llama-server` call, no image generation, no OCR-routing/renderer/prompt/export change, no new API
  route. Chandra remains blocked by its own live-validation gate.
- **Safety / no-leak:** only sanitized closed-vocab + bounded-numeric fields recorded; **no** real PDF path/filename,
  document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, provider payload, or raw exception. The runtime
  `visual_markdown_selection_trace.json` was **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 71 is NOT committed.**

---

## Slice 70 — **Table-vs-diagram visual-classification precision**, on `slice70-visual-pilot-table-diagram-precision`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production classification slice (precision only).** Slice 69's real-sample selection trace localized the
  remaining failure to *classification*, not extraction/ranking/cap/export/rendering/UI: **all 11 safe candidates were
  classified `diagram_or_figure`** while the two *selected* visuals were, by manual inspection, clean two-column
  definition/glossary **tables** (`selection_explanation: tables_misclassified_as_diagram_or_figure`). Slice 70
  improves the deterministic, bounded, pixel-only visual-type classifier so **two-column / glossary / definition
  tables classify as `reconstructable_table`** instead of `diagram_or_figure`, giving Slice 64's diagram-first
  ranking a real signal — while genuine diagrams/figures (including labeled ones) stay `diagram_or_figure`.
- **Root mechanism fixed.** A glossary/definition table has **variable-height rows** (multi-line definitions wrap),
  so its horizontal text bands are *not* evenly spaced; Slice 66's text-grid path requires a *regular* row rhythm and
  missed it, and with no drawn rules the lightly-ruled path missed it too — so it fell through to
  `diagram_or_figure`. Slice 70 adds one bounded pixel-only feature, **`two_col_split`**, that fires only when the
  crop has **exactly two substantial text columns separated by a real gutter** (whitespace or a thin drawn divider)
  **AND each column independently contains several separated horizontal text bands**. The per-column row-band
  requirement is the guard that keeps a labeled **diagram** a diagram — text presence alone never flips a diagram;
  row-spacing regularity is intentionally **not** required, which is what now catches variable-height glossary rows.
- **Behavior:** two-column/glossary/definition tables → `reconstructable_table`; lightly-ruled two-column, text-band
  central-gutter, and strong-grid tables remain `reconstructable_table`; irregular labeled diagrams, flowcharts, and
  diagrams whose labels make text-like dark bands remain `diagram_or_figure`. **Diagrams beat reconstructable tables**
  (cap 1 picks the diagram; cap 2 with one of each selects both, diagram first; cap 2 with two diagrams + a table
  selects the two diagrams). **Tables are still allowed when best/only.** The existing Slice 68 selection trace
  reflects the improved classification automatically (`type_counts` no longer collapse) — **no artifact schema
  change**.
- **Hard boundaries honored:** cap still hard-capped at **2**, default still **1**, `fitz_local` + `extracted_figure`
  only, safe `assets/<slug>.png` only, file-inside-job-dir gate, Chandra/Mistral/`page_visual_signal` still rejected,
  degrade-never-fail (no Pillow / unreadable / too-small ⇒ `unknown`, prior behavior). **No** frontend/UI change, **no**
  `/api/options` change, **no** export/cap/OCR-routing/renderer/prompt/extraction change, **no** model/provider/cloud/
  `llama-server` call, **no** new API route, **no** committed binary/image/PDF/DOCX/ZIP/runtime fixture (every PNG is
  runtime-built in a temp dir). Chandra remains blocked by its own live-validation gate.
- **Tests:** new `test_scripts/test_visual_pilot_table_diagram_precision.py` (24-point coverage, **70/70** pass host;
  **70/70** with `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`). Full visual-pilot suite + operator self-test +
  insertion/render/export/anki/options + `eval --offline --all` (no regression, 0.8306→0.8306) green host-side; the
  rebuilt+recreated container is `/api/health` `{"ok":true}` and the in-container visual suite is green
  (precision 70/0, selection-trace 56/0, light-table 66/0, type-ranking 64/0, multifigure 78/0, quality-gate 54/0,
  operator self-test PASS). `git diff --check` clean. **Slice 70 is NOT committed.**
- **Release smoke (`smoke_release.py`):** `release_smoke_status: transient_failure_then_green_on_rerun` ·
  `release_smoke_failure_category: outline_ordering_check` · `slice70_visual_tests: green` ·
  `slice70_docker_health: green` · `slice70_not_cause: confirmed`. A first run reported **28/29** with a single
  `outline_ordering_check` miss (`pos=[-1,-1,-1]`); an unchanged rerun on the same Slice 70 branch/container passed
  **29/0/0** with that same check green — i.e. a flaky LLM section-ordering check, **not** caused by Slice 70 (which
  only adds a deterministic pixel-only visual-type feature and cannot affect generated outline text). No raw
  generated guide content recorded.
- **Safety / no-leak:** classifier reads only bounded non-sensitive pixel summaries; never OCRs, never base64/
  serializes/logs image bytes, never records a path or source text, adds no artifact. No real PDF path/filename,
  document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or
  provider payload anywhere.

---

## Slice 69 — **Real operator selection-trace audit**, on `slice69-visual-pilot-selection-trace-operator-audit`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Reruns the existing operator harness against the real, **non-private**
  operator sample with **Slice 68's sanitized selection trace** (`visual_markdown_selection_trace.json`) enabled,
  then reads that trace to explain *why* the real sample still selects tables instead of irreplaceable diagrams —
  without leaking source material. **No production pipeline/API/frontend code changed; no new visual behavior; no
  ranking/cap/default/gate/render/export/extraction-OCR routing change; no model/provider/cloud call.** Docs-only —
  **no harness correction was needed.**
- **Outcome this session: `selection_trace_operator_audit: run` — `status: ok`, `trace_artifact_present: true`,
  `trace_no_leak_sweep: clean`, `effective_max_images: 2`, `inserted_visual_count: 2`, `safe_candidate_count: 11`,
  `unsafe_candidate_count: 0`, `selected_count: 2`.** The non-private sample was available, so the cap-2 harness
  **was** run inside the rebuilt Slice 68 container; the trace + rendered PDF/HTML/DOCX were copied to a host folder
  and inspected by hand. Trace was checked for leaks **before** any field was transcribed (clean).
- **Root cause finally localized — it is classification, not extraction or pure ranking.** The trace's `type_counts`
  shows **all 11 safe candidates classified `diagram_or_figure`** (`reconstructable_table: 0`, `unknown: 0`,
  `decorative_or_low_information: 0`). Manual inspection ground-truths the discrepancy: the two **selected** visuals
  are clean two-column definition/glossary **tables** (`selected_visual_type: tables_only`,
  `irreplaceable_visual_selected: false`, `selected_figures_quality: all_useful_or_acceptable`), and at least one
  **genuinely irreplaceable schematic diagram was present among the safe candidates but was NOT selected**. Because
  the pixel classifier over-accepts reconstructable tables as `diagram_or_figure`, every candidate carries the same
  `visual_type_score: 3`, diagram-first ranking has nothing to discriminate on, and pure quality score picks the
  clean tables (`quality_score: 1.2`) ahead of the real diagram. `selection_explanation:
  tables_misclassified_as_diagram_or_figure`.
- **Next work (recorded, not started):** `improve_visual_type_classification_table_vs_diagram_precision` — the
  deterministic local pixel classifier must separate reconstructable tables from genuine diagrams so diagram-first
  ranking gets a real signal. **Not** extraction (diagrams present) and **not** a blind ranking/threshold change
  (ranking is signal-starved, not wrong). The trace is **sufficient** to localize this; its per-candidate
  rejection-reason coverage is sparse (only `rejected_secondary_below_quality_floor: 1` for nine unselected
  candidates) — a possible future *trace* refinement, not a reason to guess heuristics.
- **Hard boundaries honored:** no cap above 2, no UI count selector, no Chandra/Mistral/Gemini/cloud OCR, no
  model/provider/llama-server call, no image generation, no OCR-routing/renderer/prompt/export change, no new API
  route. **Do not proceed to UI polish or cap expansion** until an irreplaceable diagram/figure is selected in real
  validation, or there is a deliberate product decision to accept tables.
- **Safety / no-leak:** only sanitized closed-vocab + bounded-numeric fields recorded; **no** real PDF path/filename,
  document text, OCR text, source caption/table text, image bytes, base64, data URI, full URL, raw argv, token,
  model/mmproj/executable path, provider payload, or raw exception. The runtime
  `visual_markdown_selection_trace.json` was **inspected but not committed**; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 69 is NOT committed.**

---

## Slice 68 — **Sanitized visual-pilot selection trace / candidate audit**, on `slice68-visual-pilot-sanitized-selection-trace`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production diagnostic slice (visibility only).** Slice 67 proved the real post-Slice-66 cap-2 run still
  selected **two useful-but-reconstructable tables only** (`selected_visual_type: tables_only`,
  `irreplaceable_visual_selected: false`); the next problem is **visibility, not more blind heuristic tuning**.
  Slice 68 adds a bounded, sanitized **candidate-audit artifact** so future real operator runs can explain *why*
  diagrams were not selected — which candidates existed, their classified visual type, and why the chosen tables
  outranked them. **Diagnostic only — ranking/cap/default/two-key-gate/UI/render/export/extraction-OCR routing all
  unchanged; no model/provider/cloud call added.**
- **What changed (one production file):** `pipeline/visual_markdown_insertion.py`. Added
  `build_visual_markdown_selection_trace(...)` + `_emit_selection_trace(...)` (and small pure helpers), and wired
  `_emit_selection_trace` into `apply_visual_markdown_pilot` at the three both-gates-pass exits (inserted,
  insert-failed, no-candidate). Selection logic, the `_pick_candidates`/`_best_typed` ranking core, the cap reader,
  and the two-key gate are **byte-for-byte unchanged** — the trace is built by an independent, read-only pass that
  never influences the decision.
- **Exact artifact:** `visual_markdown_selection_trace.json`, written to the job dir **only** when the global
  master env switch is ON **and** the job opted in **and** candidate selection was attempted (including the
  no-candidate / low-quality skip — that is exactly the case worth auditing). **Never** written when the master
  switch is off, the job did not opt in, or the pilot code is not reached. Build/write is wrapped degrade-never-fail
  — a trace problem can never fail generation and leaves no partial file.
- **Sanitized + bounded.** Top level is whitelisted: `schema_version`, `status`, `reason`, `effective_max_images`,
  `inserted_visual_count`, `selected_candidates`, `candidate_summary`, `warnings`. Per-selected-candidate carries
  only safe fields (`asset_id`, safe `assets/<slug>.png` `asset_ref`, `source_page`, `source_provider`,
  `visual_type`, `visual_type_score`, `classification`, `quality_score`, `quality_reasons`, `placement`, `rank`,
  `selected`, `selection_reason`); `candidate_summary` is counts only (`total_manifest_assets`,
  `safe_candidate_count`, `unsafe_candidate_count`, `selected_count`, `type_counts`, `rejection_reason_counts`). All
  reasons are **closed-vocabulary tokens** (`selected_by_diagram_first_ranking` · `selected_by_quality_ranking` ·
  `selected_by_priority_order` · `rejected_low_quality` · `rejected_unsafe_ref` · `rejected_wrong_provider` ·
  `rejected_wrong_asset_type` · `rejected_duplicate_asset_ref` · `rejected_duplicate_asset_id` ·
  `rejected_secondary_below_quality_floor` · `deprioritized_reconstructable_table` · `classified_*`). **No** absolute
  path, source filename, document/OCR/caption/extracted-table text, image bytes, base64, data URI, provider payload,
  raw exception, URL, token, raw argv, or model/mmproj/executable path is ever included. Chandra/Mistral/
  page_visual_signal candidates are **counted/rejected** but never written raw.
- **New focused test:** `test_scripts/test_visual_pilot_selection_trace_sanitized.py` (20-point coverage:
  written/not-written gating, default cap 1 / env cap 2, selected+inserted counts, tables-only vs diagram-selected
  via safe tokens, safe/unsafe counts, unsafe-ref counted-not-raw, foreign-provider rejection, full no-leak sweep,
  trace-failure-never-fails-generation, default-off byte-identical, two-key gate unchanged, cap constants unchanged,
  export excludes the trace, pilot does not write `clean.md`). **56/56 pass host and in-container.**
- **Validation:** `compileall api pipeline test_scripts` OK; the full visual-pilot suite + operator self-test +
  insertion/render/export/anki/options + `eval --offline --all` all green host-side; rebuilt + recreated the
  container, `/api/health` `{"ok":true}`, `smoke_release.py` **29/29**, and the visual-pilot suite re-run
  in-container (selection-trace 56/0, light-table 66/0, type-ranking 64/0, multifigure 78/0, quality-gate 54/0,
  operator self-test PASS). `git diff --check` clean. The container test copies were removed after the run.
- **Decision recorded:** instrument before tuning. The next visual slice can read this trace on a real run to decide
  whether the diagrams are being **classified** wrong (type detection) or **ranked/capped** wrong (selection), rather
  than guessing. **Do not** change ranking/cap/default in this slice; **do not** expand beyond hard cap 2, add a UI
  count selector, or add Chandra/Mistral/Gemini/model/provider/cloud integration. Chandra remains blocked by its own
  live-validation gate.
- **Safety / no-leak:** no real PDF path/filename, document text, OCR text, image bytes, base64, data URI, full URL,
  raw argv, token, model/mmproj/executable path, or provider payload recorded; nothing binary/image/PDF/DOCX/ZIP/
  runtime committed. **Slice 68 is NOT committed.**

---

## Slice 67 — **Improved-light-table real operator validation**, on `slice67-visual-pilot-light-table-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Validation/docs slice only.** Records whether Slice 66's strengthened lightly-ruled / text-heavy table
  detection lets the **real** non-private operator sample finally select a hard-to-reconstruct diagram/figure
  instead of tables only. **No production pipeline/API/frontend code changed; no new visual behavior added.**
  **Docs-only — no harness correction was needed.**
- **Outcome this session: `light_table_operator_visual_quality_review: run` — `status: ok`,
  `inserted_visual_count: 2`, `selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`,
  `selected_figures_quality: all_useful_or_acceptable`.** The non-private operator sample was available again, so
  the cap-2 operator harness **was** run inside the rebuilt Slice 66 container
  (`GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`, `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`,
  `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`); the rendered PDF/HTML/DOCX were copied to a host folder and inspected
  by hand. All render/export checks passed (`pdf_render_ok` / `pdf_image_visible` / `docx_render_ok` /
  `export_zip_ok` / `export_png_included: true`), `warnings: [multiple_figures_present_one_inserted]`,
  `failure_category: none`, `no_leak_sweep: clean`. Full record + interpretation in
  `VISUAL_PILOT_OPERATOR_VALIDATION.md`.
- **Honest outcome — improved light-table detection did *not* change the real selection.** The two inserted
  visuals are still **useful/acceptable but reconstructable tables**; the genuinely irreplaceable visual content
  present elsewhere in the sample was **not** selected. Slice 66 improved the synthetic / light-table detection
  tests, but the real cap-2 run still lands on **two useful tables only** — readable and useful, yet
  reconstructable from extracted text. **No irreplaceable diagram/figure was selected, so visual-type selection is
  still not solved for the real sample.** `decision_gate: light_table_detection_did_not_change_real_outcome` ·
  `next_recommended_slice: add_sanitized_selection_trace_before_more_heuristics`.
- **Decision:** **do not proceed to UI polish or cap expansion.** Before further heuristic tuning, add a
  **sanitized selection trace / candidate audit** so future runs can explain (in closed-vocab / bounded-numeric form
  only) *why* diagrams were not selected — which candidates existed, their classified visual type, and why the
  chosen tables outranked them. **Do not expand beyond cap 2. Do not add a UI count selector. Do not add
  Chandra/Mistral/Gemini/model/provider/cloud integration.** Chandra remains blocked by its own live-validation
  gate.
- **Validation:** docs-only; `git diff --check` clean. The harness was **not** touched (no `compileall` /
  `--self-test` needed beyond Slice 66's already-green run). No production behavior, no frontend/UI, no
  extraction/OCR-routing/prompt/render/export change, no Chandra/model/provider/cloud call.
- **Safety / no-leak:** only the sanitized closed-vocabulary fields recorded — no real PDF path/filename, document
  text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or provider
  payload; nothing binary/image/PDF/DOCX/ZIP/runtime committed. **Slice 67 is NOT committed.**

---

## Slice 66 — **Lightly-ruled / text-heavy table detection**, on `slice66-visual-pilot-light-table-detection`. **COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).**

- **Production-behavior slice (visual-type detection only).** Slice 65's real operator validation proved the
  Slice 64 diagram-first ranking **did not change the real sample outcome** — the two selected visuals stayed
  **useful tables only** (`selected_visual_type: tables_only`, `irreplaceable_visual_selected: false`). **Root
  cause:** the Slice 64 classifier only recognized a **strong full horizontal+vertical rule grid** as a table, so
  the sample's **lightly-ruled / text-heavy** tables stayed `unknown` and every candidate sat in one visual-type
  tier — ranking had no signal to act on. Slice 66 improves the **deterministic, local, pixel-only** visual-type
  detection so a lightly-ruled / reconstructable table is classified as `reconstructable_table` rather than
  `unknown`, giving diagram-first ranking a real signal. **This is detection work *before* any UI/placement polish,
  exactly as Slice 65 recommended.**
- **What changed (one file):** `pipeline/visual_markdown_insertion.py`. Extended the bounded grayscale feature
  summary (`_summarize_gray_pixels`) with a **softer-ink** (`_LT_INK`) horizontal **text-band rhythm** and a
  vertical **column-gutter** structure, and added a conservative `_looks_like_reconstructable_table(...)` rule
  (plus pure helpers `_profile_runs`, `_runs_regular`, `_count_col_blocks`) wired into
  `_classify_visual_type_from_features` **after** the existing strong-grid table rule and **before** the diagram
  rule. Two dual-signal table paths: (a) **text-grid** — a regular repeated text-band rhythm *and* a multi-column
  gutter structure; (b) **lightly-ruled** — multiple full horizontal rules *without* a strong vertical-rule grid,
  backed by either the row rhythm or the column structure. A genuine diagram (irregular row spacing, no clean
  full-height column gutters, no repeated horizontal rules) satisfies neither and stays `diagram_or_figure`.
- **Behavior outcome:** lightly-ruled and text-band (weak/no vertical rule) tables now classify as
  `reconstructable_table`; the diagram still classifies as `diagram_or_figure`; a diagram **beats** a lightly-ruled
  table at cap 1, and at cap 2 a diagram is selected **before** a table. **Tables remain allowed when they are the
  best/only useful visual.** Same hard limits as Slice 64: pixel-only over the already-safe job-dir-contained crop,
  **no OCR / model / provider / network / cloud / `llama-server` / image-gen**, no bytes/base64/data-URI/path/text
  retained, **no new artifact**; Pillow-absent / unreadable / too-small ⇒ `unknown` ⇒ **byte-identical fallback**
  to the prior Slice 60/62 quality-only selection.
- **Invariants unchanged:** global master flag + per-job opt-in two-key gate, **default cap 1**, **hard cap 2**
  (server-side only), `fitz_local` / `extracted_figure`-only, unsafe-ref / Chandra / Mistral / `page_visual_signal`
  still rejected, decorative/low-information rejection still dominates, default-off output **byte-identical**,
  export ride-along unchanged. **No frontend/UI, no `/api/options`/route change, no cap change, no extraction/
  OCR-routing/prompt/render/export behavior change.** Chandra remains blocked by its own live-validation gate.
- **Tests:** new `test_scripts/test_visual_pilot_light_table_detection.py` (runtime-generated tiny PNG fixtures in
  temp dirs — never committed) covering strong-grid / lightly-ruled / text-band tables → `reconstructable_table`,
  diagram → `diagram_or_figure`, diagram-beats-light-table at cap 1, cap-2 diagram-first / two-diagrams /
  only-tables, decorative rejection, unknown-preserves-prior, analysis-failure degrade, unsafe-ref / blocked-provider
  exclusion, determinism, two-key gate, default-off byte-identical, default-1 / hard-cap-2, export ride-along, and a
  full no-leak sweep. Existing visual-type ranking / multifigure / quality-gate / insertion / render / export /
  options / e2e / anki tests and the operator-sample `--self-test` all still pass unchanged.
- **Validation:** `python -m compileall api pipeline test_scripts` clean; full visual + anki + offline eval suite
  green on host; **Docker** `build` + `up` + `/api/health` + `smoke_release.py` (29/0) green; the visual tests also
  re-run **inside the production container** (Pillow 12 present) with **no skips** (light-table 66/0, ranking 64/0,
  multifigure 78/0, quality-gate 54/0, operator `--self-test` PASS); copied-in test scripts removed from the
  container afterward; `git diff --check` clean.
- **Optional real operator revalidation:** **not run in this slice** — the non-private operator sample is not
  available in this session. The desired outcome (`selected_visual_type: diagrams_or_figures_present` /
  `irreplaceable_visual_selected: true`) is **not assumed**; whether the strengthened detection actually flips the
  real sample must be confirmed by re-running the cap-2 operator harness when the sample is available, and recorded
  only if true after manual inspection.
- **Safety / no-leak:** only closed-vocab tokens and bounded numeric features in info dicts / tests — no real PDF
  path/filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, or
  model/mmproj/executable path in any doc/test/artifact/log; **nothing binary/image/PDF/DOCX/ZIP/runtime committed**.
  **Slice 66 is NOT committed.**

---

## Slice 65 — **Diagram-first real operator validation record**, on `slice65-visual-pilot-diagram-first-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Validation/docs slice.** Records a real, sanitized operator validation of the **Slice 64 diagram-first
  ranking** behavior against the same already-supplied non-private operator sample. Slice 64 proved diagram-first
  ranking **synthetically and in Docker** but explicitly left the **real** operator revalidation *not run*; Slice
  65 closes that one gap. **No production pipeline/API/frontend code changed; no new visual behavior added.**
  **Docs-only — no harness correction was needed.**
- **What was done:** used the rebuilt Slice 64 container, ran the existing operator harness
  (`validate_visual_pilot_operator_sample.py`) with `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`,
  `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`, `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2` against the non-private sample
  (copied in/out via the running compose container; sample removed from the container afterward), copied the
  rendered PDF/HTML/DOCX to a host folder, and inspected the inserted visuals by hand.
- **Recorded (sanitized, closed vocab):** `diagram_first_operator_visual_quality_review: run` · `status: ok` ·
  `pilot_inserted: true` · **`inserted_visual_count: 2`** · **`selected_visual_type: tables_only`** ·
  **`irreplaceable_visual_selected: false`** · **`selected_figures_quality: all_useful_or_acceptable`** ·
  `pdf_render_ok/pdf_image_visible/docx_render_ok/export_zip_ok/export_png_included: true` ·
  `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`.
- **Honest outcome — diagram-first did *not* change the real selection.** The two inserted visuals are still
  **reconstructable tables**, and the genuinely irreplaceable visual content present elsewhere in the sample was
  **not** selected. **Root cause (sanitized):** the Slice 64 ranking only re-orders when its deterministic pixel
  classifier can tell a `reconstructable_table` from a `diagram_or_figure`; the table-grid heuristic fires only on
  a strong regular horizontal **and** vertical rule grid, and it did **not** recognize these **lightly-ruled**
  tables as tables — so every safe candidate landed in the same visual-type tier and selection fell back
  **byte-for-byte** to the prior Slice 60/62 quality-and-order pick. The classifier behaved exactly as designed
  (no regression); it simply had no clear table-vs-diagram signal to act on here. `decision_gate:
  diagram_first_ranking_did_not_change_real_outcome` · `next_recommended_slice:
  improve_visual_type_detection_before_ui_polish`.
- **Decision:** because `selected_visual_type: tables_only`, the next visual slice should **continue visual-type
  ranking / detection work before any UI or placement polish** — specifically strengthen table-vs-diagram
  detection (recognize borderless/lightly-ruled tables and/or detect genuine diagrams more strongly) so the
  ranking has a real signal. **Do not expand beyond cap 2, no UI count selector, no Chandra/Mistral/Gemini/
  model/provider/cloud integration.** Default remains exactly 1; hard cap remains 2.
- **Out of scope (unchanged):** no frontend/UI, no `/api/options`/route change, no cap change, no
  extraction/OCR-routing/prompt/render/export behavior change, no model/provider/cloud/`llama-server`/image-gen
  call. Chandra remains blocked by its own live-validation gate.
- **Safety / no-leak:** only sanitized closed-vocab fields recorded — no real PDF path/filename, document text,
  OCR text, image bytes, base64, data URI, full URL, raw argv, token, or model/mmproj/executable path in any
  doc/test/artifact/log; the host review folder lives outside the repo and **nothing binary/image/PDF/DOCX/ZIP/
  runtime was committed**. **Slice 65 is NOT committed.**

---

## Slice 64 — **Prefer diagrams over reconstructable tables (visual-type ranking)**, on `slice64-visual-pilot-diagram-first-ranking`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Production-behavior slice (ranking only).** Slice 63 proved the cap-2 plumbing on a real sample but
  selected **tables only**; tables are useful yet often **reconstructable** from extracted text into clean
  generated tables. Slice 64 adds a conservative, deterministic **visual-type ranking** so a hard-to-reconstruct
  **diagram/figure** is preferred over a reconstructable **table** when both are available — while a good table
  is still selected when it is the **best/only** useful visual. **Scope is ranking, not expansion.**
- **What changed (one file):** `pipeline/visual_markdown_insertion.py`. Added a pixel-only visual-type
  classifier (`classify_visual_markdown_candidate_type_for_pilot`), a priority scorer
  (`score_visual_type_priority_for_pilot`), and wired a **type-first / quality-second** selection tier into the
  existing single- and multi-figure pickers (`_pick_candidate`, `_pick_candidates` → `_select_multi`, via a new
  `_best_typed` helper). All Slice 60 quality gating and Slice 62 cap/secondary-floor/page-diversity rules are
  unchanged underneath.
- **Closed visual-type vocabulary:** `diagram_or_figure` · `reconstructable_table` ·
  `decorative_or_low_information` · `unknown`. **Preferred order:** `diagram_or_figure > reconstructable_table >
  unknown > decorative_or_low_information`.
- **How classification works (safe, deterministic):** only the **already-safe, already-job-dir-contained**
  `assets/<slug>.png` crop is opened (re-validated for ref + realpath containment first), read read-only with
  **Pillow**, converted to grayscale, bounded-downscaled, and summarized into a few **bounded non-sensitive**
  features (size, aspect, near-white blank ratio, full horizontal/vertical rule counts, rough edge density).
  Tables = strong regular horizontal+vertical grid; diagrams = substantial non-grid graphic content;
  decorative = near-empty / extreme banner with low edges. **It never OCRs, calls a model/provider/network,
  base64/serializes/logs image bytes, records a path or source text, or adds an artifact.**
- **Degrade-never-fail / backward-compatible:** if Pillow is unavailable, the crop is unreadable/corrupt, or it
  is too small to analyze, the type is **`unknown`** — which makes the type priority uniform, so selection
  **falls back byte-for-byte** to the prior Slice 60/62 quality-only behavior. Default-off output stays
  byte-identical; the two-key gate is unchanged; **default cap remains exactly 1**; **hard cap remains 2**;
  `fitz_local`/`extracted_figure`-only and all unsafe-ref / Chandra / Mistral / `page_visual_signal` rejections
  are unchanged.
- **Ranking behavior (proven in tests):** diagram beats table at cap 1; two diagrams beat a table at cap 2; one
  diagram + one table at cap 2 selects **both with the diagram first**; only-tables still selects a table;
  pixel-decorative is **not** preferred just to avoid a table; a lone metadata-accepted candidate is still
  inserted (no over-rejection).
- **Tests:** new `test_scripts/test_visual_pilot_visual_type_ranking.py` (runtime-built tiny PNG fixtures in
  temp dirs — diagram/table/decorative drawn with Pillow, solid/corrupt via stdlib; pixel cases skip cleanly
  without Pillow). Host: ranking **64/0/0**; existing multifigure / quality_gate / e2e / insertion / render /
  export_asset / options / anki / operator `--self-test` / offline eval all green; `git diff --check` clean.
  **In-container (full deps):** ranking **64/0/0**, multifigure **78/0/0**, quality_gate **54/0/0**, operator
  `--self-test` PASS (Pillow 12.2.0 present). **Docker:** `docker compose build` + `up --force-recreate` ok,
  `/api/health` `{"ok":true}`, `smoke_release.py` **29/0/0**.
- **Optional real operator revalidation:** **not run** this slice (no non-private operator sample available in
  this environment). The desired-but-not-assumed outcome is `selected_visual_type: diagrams_or_figures_present`
  / `irreplaceable_visual_selected: true`; the actual result must be recorded only if/when the harness is rerun.
- **Out of scope (unchanged):** no frontend/UI, no UI count selector, no `/api/options` change, no cap change,
  no new API route, no extraction/OCR-routing/prompt/render/export behavior change, no Chandra/Mistral/Gemini/
  model/provider/cloud/`llama-server` call, no image generation. Chandra remains blocked by its own
  live-validation gate.
- **Safety / no-leak:** classifier returns only closed-vocab tokens + bounded numerics in internal info dicts;
  no real PDF path/filename, document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token,
  or model/mmproj/executable path in any doc/test/artifact/log. No committed binary/image/PDF/DOCX/ZIP/runtime
  fixture. **Slice 64 is COMMITTED + MERGED to `chrome-renderer-v1` (fast-forward).** The optional real operator
  revalidation that this entry left *not run* was subsequently performed and recorded in **Slice 65** above.

---

## Slice 63 — **Cap-2 real operator validation record**, on `slice63-visual-pilot-cap2-operator-validation`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Validation/docs slice.** Records a real, sanitized operator validation of the **Slice 62 cap-2 path**
  against the same already-supplied non-private operator sample. Slice 62 validated the capped multi-figure
  pilot **synthetically and in Docker** but did not run the optional **real** cap-2 revalidation; Slice 63
  closes that one gap. **No production pipeline/API/frontend code changed; no new visual behavior added.**
- **What was done:** rebuilt/used the Slice 62 container, ran the existing operator harness
  (`validate_visual_pilot_operator_sample.py`) with `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT=1`,
  `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION=1`, `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES=2`, copied the rendered
  PDF/HTML/DOCX to a host folder, and inspected the inserted figures by hand.
- **One tiny safe harness correction (the only code touched):** the harness export check previously hard-coded
  **exactly one** bundled PNG (`len(png_entries) == 1`), which falsely reported `export_png_included: false`
  when the cap-2 path legitimately bundled **two** referenced PNGs. It now requires the bundled-PNG count to
  equal the sanitized `inserted_visual_count` and stay within `1..2`, each still a safe relative
  `assets/<slug>.png` ref. No production code/schema/vocabulary changed; `--self-test` (default cap, one
  figure) stays green with `export_png_included: true`.
- **Recorded result (sanitized, closed vocab):** `cap2_operator_visual_quality_review: run` · `status: ok` ·
  `pilot_inserted: true` · **`inserted_visual_count: 2`** · **`selected_figures_quality:
  all_useful_or_acceptable`** · `pdf_render_ok: true` · `pdf_image_visible: true` · `docx_render_ok: true` ·
  `export_zip_ok: true` · `export_png_included: true` · `warnings: [multiple_figures_present_one_inserted]` ·
  `failure_category: none` · `no_leak_sweep: clean`. The two inserted figures were genuine content-bearing
  material from **distinct source pages**, not decorative chrome; both rendered visibly and rode along in the
  export bundle.
- **Operator-review nuance (sanitized, closed vocab):** `selected_visual_type: tables_only` ·
  `irreplaceable_visual_selected: false` · `decision_gate:
  cap2_plumbing_passed_but_visual_type_priority_incomplete` · `next_recommended_slice:
  prefer_diagrams_over_reconstructable_tables`. Both selected visuals were **important tables**, not
  diagrams/figures that are hard to reconstruct.
- **Interpretation / decision gate:** Slice 63 **proves the cap-2 pipeline works on a real, non-private sample**
  (selection → capped multi-insertion → render → export). Slice 62 made cap 2 *available*, default stays 1; this
  record confirms the cap-2 **real** output is useful (`all_useful_or_acceptable`). **But** both inserted visuals
  were useful/acceptable **tables**, and tables are often reconstructable from extracted text into clean
  generated tables — so the irreplaceable-visual goal is only partially met. The visual/OCR feature exists
  especially to preserve visuals an LLM **cannot** recreate from text (diagrams, flowcharts, screenshots,
  labeled figures, network maps). **Therefore the next visual slice should NOT be placement/UI polish yet;** it
  should **improve visual-type ranking** — prefer diagrams/figures over reconstructable tables when both are
  available, while still allowing tables when they are the best/only useful visual. **Do not expand beyond cap
  2; do not add Chandra/Mistral/Gemini/model/provider/cloud integration.** A `mixed_quality` verdict would have
  meant improve ranking/placement first; `decorative_or_bad_present`/`unclear` would have meant keep doing
  selection-quality work. Chandra remains blocked by its own live-validation gate.
- **Files:** `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md` (cap-2 record + interpretation), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`; tiny correction in
  `test_scripts/validate_visual_pilot_operator_sample.py`. No frontend/UI, extraction/OCR-routing, prompt,
  render, export, or route change. No Chandra/model/provider/cloud call.
- **Safety / no-leak:** only sanitized closed-vocab fields + safe relative refs; no real PDF path/filename,
  document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable
  path, or raw exception in any doc/test/artifact/log. No committed binary/image/PDF/DOCX/ZIP/runtime output.
  **Slice 63 is NOT committed.**

---

## Slice 62 — **Capped multi-figure visual pilot**, on `slice62-visual-pilot-capped-multifigure`. **COMMITTED + MERGED to `chrome-renderer-v1`.**

- **Cautiously extends the off-by-default visual markdown image pilot from "at most one figure" to "up to a
  small server-configured cap" (hard upper bound `2`).** Default behavior is **unchanged: exactly one figure**.
  Slices 59/60/61 cleared the single-figure plumbing + Slice 60 quality gate on a real non-private sample;
  Slice 62 is the first step beyond one figure, and it stays small on purpose.
- **Why:** the Slice 61 post-fix operator verdict was `selected_figure_quality: useful_diagram_or_table` — in the
  `useful_diagram_or_table` / `acceptable_but_not_best` band, the decision gate for "cautious multi-figure may be
  considered next." This slice takes exactly that step: up to **2** figures, never more, never user-selectable N.
- **Gate (unchanged) + new cap:** the existing **two-key gate** (global master env `…ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT`
  AND per-job opt-in `visual_markdown_image_pilot`) is untouched. A new **server-side env integer**
  `GUIDEFORGE_VISUAL_MARKDOWN_MAX_IMAGES` sets the cap: default `1`, min `1`, **hard max `2`**;
  absent/empty/non-integer/`0`/negative/`>2`/huge all **degrade to `1`** (never clamp upward). The cap matters
  only when both gates are on AND local figure extraction produced safe candidates.
- **Selection (reuses the Slice 60 quality gate):** candidates stay `fitz_local` + `extracted_figure` + safe
  `assets/<slug>.png` (file present inside the job dir, realpath-contained) only — never Chandra/Mistral/
  page-visual-signal/unsafe refs. The first/strongest pick is **byte-for-byte the existing single-best
  decision**. Additional figures (up to the cap) must each clear a **secondary quality floor** (`score ≥ 1.15`,
  i.e. genuinely content-bearing, not merely neutral/penalized), must not duplicate an already-selected
  `asset_id` or `asset_ref`, and **prefer a distinct source page** (same-page second figure only when no
  better alternative qualifies). Strongest stays first. Only-decorative ⇒ insert none with a closed reason; a
  low-quality second ⇒ insert one. The cap is never filled with junk.
- **Insertion:** with exactly one figure the output is **byte-identical** to the pre-Slice-62 pilot (singular
  `## Visual Reference` heading / same anchored placement). With more than one, each figure with a deterministic
  `<!-- visual-anchor: source_page_NNNN -->` marker is placed at its anchor; the rest are appended together
  under a single trailing **`## Visual References`** (plural) section. Captions stay generic page-only —
  `Extracted figure from source page N` — never source captions, OCR text, document text, or image content.
- **Export:** the bundle now rides along **all and only** the referenced pilot PNGs, **capped at 2**, each a
  safe job-local `assets/<slug>.png` resolved inside the job dir (realpath-contained, regular file). Never the
  whole `assets/` dir, never an unreferenced/cropped extra. PNG ride-alongs **still do not** count toward
  `files_included` / `total_included`, so a pilot-PNG-only job with no requested artifact **still 404s**. Bundle
  index keeps `visual_pilot_asset` (first ref or `null`, backward-compatible) and adds `visual_pilot_assets`
  (the capped safe list). No absolute paths or image bytes recorded.
- **Out of scope (unchanged):** no Chandra/Mistral/Gemini/model/provider/cloud call, no llama-server/image
  generation, no OCR-routing/extraction/prompt/renderer change, no new API route, no arbitrary N-figure support,
  no UI count selector. Chandra remains blocked by its own live-validation gate.
- **Frontend / `/api/options`:** **untouched** — no UI count selector; payload behavior unchanged
  (`enable_visual_references` still sent only when checked).
- **Files (code):** `pipeline/visual_markdown_insertion.py` (cap reader + capped multi-select helpers + multi
  insertion + plural export helper), `api/server.py` (export bundle rides all referenced PNGs up to cap; index
  keeps `visual_pilot_asset` + adds `visual_pilot_assets`). **Tests:** new
  `test_scripts/test_visual_pilot_multifigure.py` (env cap, selection, safety gates, insertion, no-mutation,
  render-skippable, export-skippable, no-leak sweep — **63 passed / 0 failed / 3 host-skipped**);
  `validate_visual_pilot_operator_sample.py` gained a safe `inserted_visual_count` integer field and now accepts
  1..2 safe refs (self-test green).
- **Validation (host):** `compileall` clean; `test_visual_pilot_multifigure` 63/0/3; `test_visual_pilot_quality_gate`
  50/0/1; `test_visual_markdown_insertion` 53/0; `test_visual_markdown_render` 6/0/1; `test_visual_pilot_export_asset`
  9/0; `test_visual_pilot_options` 16/0; `test_anki_export` 46/0; operator `--self-test` PASS; `e2e_validation`
  16/0/3; offline eval no regression (delta 0.0); `git diff --check` clean. Docker rebuild + `/api/health` +
  `smoke_release.py` + container-side multifigure/quality-gate/operator self-test run separately.
- **Safety / no-leak:** only sanitized closed-vocab fields and safe relative refs; no real PDF path/filename,
  document text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable
  path, or raw exception in any doc/test/artifact/log. No committed binary/image/PDF/DOCX/ZIP/runtime fixture
  (test PNGs are tiny runtime-built byte literals under temp dirs).
- **Slice 62 is NOT committed.** Parked Slice 60 trace stash remains untouched.

---

## Slice 61 — **Post-fix visual-quality operator review record**, on `slice61-visual-pilot-postfix-quality-review`. **NOT COMMITTED.**

- **Docs / validation-record only.** No production code, frontend/UI, export, extraction/OCR-routing, prompt,
  render, or route change; no multi-figure, no Chandra/model/provider/cloud call; no committed binary/image/
  PDF/DOCX/ZIP/runtime output. Slice 60 is committed and merged to trunk (`chrome-renderer-v1`) ahead of this.
- **Why:** Slice 60 fixed the quality gate and the PDF image-visibility check, and reran the real, non-private
  operator validation with `status: ok` · `pilot_inserted: true` · `pdf_render_ok: true` · `pdf_image_visible:
  true` · `docx_render_ok: true` · `export_zip_ok: true` · `export_png_included: true` ·
  `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`. The
  one thing Slice 60 deliberately left open was the **human** quality classification of the now-selected figure.
  This slice records that post-fix verdict as the decision gate for the next visual step.
- **What was done:** reran the existing operator harness (`validate_visual_pilot_operator_sample.py`) inside the
  freshly rebuilt Slice 60 container against the already-supplied non-private sample, copied the rendered
  PDF/HTML/DOCX to a host output folder, and had the operator classify the selected figure using only the closed
  vocabulary `useful_diagram_or_table` · `acceptable_but_not_best` · `decorative_or_low_information` ·
  `wrong_or_bad_crop` · `unclear`.
- **Recorded post-fix review (sanitized, closed vocab):**
  `postfix_operator_visual_quality_review: run` · `status: ok` · `pilot_inserted: true` ·
  **`selected_figure_quality: useful_diagram_or_table`** · `pdf_render_ok: true` · `pdf_image_visible: true` ·
  `docx_render_ok: true` · `export_zip_ok: true` · `export_png_included: true` ·
  `warnings: [multiple_figures_present_one_inserted]` · `failure_category: none` · `no_leak_sweep: clean`.
  The **pre-fix** Slice 60 review (`selected_figure_quality: decorative_or_low_information` ·
  `extraction_candidate_quality: mostly_usable` · `crop_quality: mostly_good_some_label_loss` ·
  `pdf_image_visible: false` · `docx_image_visible: true` ·
  `failure_category: selection_quality_insufficient` · `no_leak_sweep: clean`) is preserved for comparison.
- **Decision-gate outcome:** `useful_diagram_or_table` falls in the
  `useful_diagram_or_table` / `acceptable_but_not_best` band → **cautious multi-figure or improved placement may
  be considered next**, as a separately-designed slice and still one figure at a time until that slice is
  scoped. Chandra remains blocked by its own live-validation gate.
- **Files:** `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md` (new Slice 61 section), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md` — **docs only**.
- **Safety / no-leak:** only sanitized closed-vocabulary fields recorded; no real PDF path/filename, document
  text, OCR text, image bytes, base64, data URI, full URL, raw argv, token, model/mmproj/executable path, or
  raw exception. Harness temp files were copied into the container `/tmp`, run, then removed; nothing committed.
- **Slice 61 is NOT committed.**

---

## Slice 60 — **Visual-pilot quality gate + PDF image-visibility validation**, on `slice60-visual-pilot-quality-gate`. **COMMITTED & merged to trunk.**

- **Why this replaced the earlier trace direction:** an earlier Slice 60 attempt added a *selection trace
  artifact*. Manual operator review showed that was the wrong fix — the real problems were **selection quality**
  and **PDF image visibility**, not missing trace metadata. The trace work was **parked (stashed, not committed)**
  and this quality-gate slice took its place.
- **What manual review found (sanitized):** the real, non-private sample produced **multiple** extracted
  figures and **most table/figure crops were usable** (some label loss). But the pilot selected a **low-value
  chapter-title / title-page crop**, and the PDF check was too weak — it reported `pdf_render_ok: true` while
  manual inspection showed a **broken/missing image marker** instead of a visible embedded image.
  - Recorded **pre-fix** human-review result (closed vocab):
    `operator_visual_quality_review: run` · `selected_figure_quality: decorative_or_low_information` ·
    `extraction_candidate_quality: mostly_usable` · `crop_quality: mostly_good_some_label_loss` ·
    `pdf_image_visible: false` · `docx_image_visible: true` ·
    `failure_category: selection_quality_insufficient` · `no_leak_sweep: clean`.
  - Recorded **post-fix** sanitized result (in-container `--self-test`, and the same code path a real run
    uses): `status: ok` · `pilot_inserted: true` · `pdf_render_ok: true` · **`pdf_image_visible: true`** ·
    `docx_render_ok: true` · `export_zip_ok: true` · `export_png_included: true` · `warnings: []` ·
    `failure_category: none` · `no_leak_sweep: clean`. The earlier `pdf_image_visible: false` was the harness
    layout artifact described below, now resolved; the quality gate independently fixes the decorative-selection
    half.
- **Quality gate (`pipeline/visual_markdown_insertion.py`):** the hard safety gates are **unchanged**
  (`fitz_local` only · `extracted_figure` only · safe `assets/<slug>.png` · real file inside the job dir · one
  figure maximum · degrade-never-fail · never Chandra/Mistral/`page_visual_signal`). On top of those, the safe
  candidates are now **ranked** by a conservative, deterministic gate using **only already-available manifest
  metadata** — `source_page`, `bbox`, and the `signals` page/crop dimensions. It **never** inspects private
  text, OCR text, captions, source contents, or image bytes, and **never** calls a model.
  - New helpers: `score_visual_markdown_candidate_for_pilot(asset)` →
    `{score, decorative, reasons}`; `rank_visual_markdown_candidates(assets)` → best index or `None`;
    `is_decorative_visual_candidate(asset)`. Closed-vocab quality reasons only (`quality_title_page`,
    `quality_full_page_crop`, `quality_content_sized`, `quality_small_area`, `quality_banner_shape`,
    `quality_narrow_shape`, `quality_header_region`, `quality_footer_region`, `quality_tiny_crop`,
    `quality_metadata_sparse`).
  - Behavior: prefer content-sized figures; **drop** confident decorative chrome (title-page full crop,
    header/footer banner strips, tiny logos/icons); penalize banner/narrow/small/full-page shapes for ranking;
    **preserve replacement-plan / manifest priority order on ties and near-ties** (a rival only displaces it
    when clearly better, by a margin). When all safe candidates are decorative → **omit** with new closed reason
    `visual_candidate_low_quality` (no insertion, byte-identical guide). When metadata is **sparse** it degrades
    to a neutral, non-decorative score so a good figure is **never over-rejected** (the synthetic-fixture shape).
    Still **one figure maximum**; default-off / opt-in gates unchanged; no frontend/UI/export/extraction/OCR/
    prompt change, no new route.
- **PDF image-visibility validation (harness `test_scripts/validate_visual_pilot_operator_sample.py`):** new
  summary field **`pdf_image_visible`** distinguishes “a PDF rendered” (`pdf_render_ok`) from “the inserted
  figure is actually an **embedded, figure-sized image object**” (`pdf_image_visible`). Implemented with PyMuPDF
  (`page.get_images(full=True)`); a broken/missing ref renders only a tiny **~14×16 broken-image placeholder
  icon**, so the check counts only images ≥ 32 px on both sides (the placeholder does not register). Skips
  calmly (`null` + closed warning `pdf_image_check_skipped_no_fitz`) when PyMuPDF is unavailable on host; Docker
  covers it with 0 skips. Summary is now **eleven** closed-vocab fields; still no path/filename/text/OCR/bytes/
  base64.
- **Root cause of the “broken PDF marker” — a harness layout artifact, NOT a production bug.** `render_pdf`
  writes its intermediate HTML next to the **output PDF** (`pdf.with_suffix(".html")`), and Chromium resolves
  the relative `assets/<slug>.png` ref against **that** directory. Production always renders to **`job.final_pdf`**
  — a sibling of `clean.md` and `assets/` — so the figure embeds correctly. The Slice 59 harness wrote
  `operator_final.pdf` to the temp **base** dir (outside the job dir), so `assets/` resolved to a non-existent
  path and Chromium embedded only the broken-image placeholder — which is what manual review saw. **Fix:** the
  harness now renders the PDF **inside the job dir** (sibling of `assets/`), mirroring production exactly. No
  renderer change was needed (the renderer was already correct for the production layout).
- **Tests:** new `test_scripts/test_visual_pilot_quality_gate.py` (50 host PASS / 1 skip — PDF-visibility skips
  w/o PyMuPDF+Chromium on host): content-beats-decorative for title/banner/tiny/header-footer; single
  content-sized inserts; only-junk omits safely; unsafe refs & Chandra/Mistral/`page_visual_signal` excluded;
  one-figure rule, default-off byte-identical, two-key gate truth-table; no-mutation; full no-leak sweep; PDF
  **embedding** (not just non-empty) positive **and** negative (missing ref → not visible). `e2e` test gained a
  fitz-guarded `render.pdf_image_visible` check; operator `--self-test` updated for the new field.
- **Results (host):** `compileall` clean; new gate test 50/0/1; `validate_*_operator_sample.py --self-test`
  PASS; `test_visual_pilot_e2e_validation.py` 16/0/3; `test_visual_markdown_insertion.py` 53/0 (flag-off) and
  77/0 (flag-on); `test_visual_markdown_render.py` 6/0/1; export-asset 9/0; options 16/0; anki 46/0; eval
  `--offline --all` no regression; `git diff --check` clean. Docker validation: see handoff.
- **Boundaries reaffirmed:** still **one figure maximum**; **no** Chandra/Mistral/Gemini/cloud/model/provider/
  llama-server call; **no** multi-figure support; Chandra remains blocked by its own live-validation gate. The
  real sample PDF path/filename and document contents are **not** recorded anywhere.

---

## Slice 59 — **Visual-pilot manual operator validation harness + runbook**, on `slice59-visual-pilot-operator-validation-harness`. **NOT COMMITTED.**

- **Purpose:** make it safe and repeatable for an operator to validate the **current single-figure visual
  pilot** against a real, **non-private** sample PDF when one is available. Slice 58 proved the stitched path
  with synthetic data; Slice 59 adds an opt-in manual harness that drives the **genuine** pipeline over a real
  PDF. **Validation/harness slice only — adds NO production code and changes NO behavior.**
- **New harness `test_scripts/validate_visual_pilot_operator_sample.py`** — a manual CLI, NOT part of normal
  smoke. Two modes:
  - `--pdf "<non-private-sample.pdf>" [--output-dir <dir>]` — real run. Drives `extract_local_figures`
    (`fitz_local` only) → `write_visual_assets_manifest` → `write_visual_asset_scoring_report` →
    `write_visual_replacement_plan_report` → `apply_visual_markdown_pilot` (both gates on, via `save_clean_md`)
    → HTML/PDF/DOCX render → `export_bundle`. **Refuses to run without `--pdf`** (unless `--self-test`).
  - `--self-test` — synthetic dry run (runtime stdlib PNG + synthetic manifest, no fitz/provider/model/cloud)
    that exercises the **same** insertion/render/export + summary code and asserts the summary schema,
    closed-vocab values, and no-leak behavior. Explicitly **does not** pretend to be real operator validation.
- **Safety/no-leak (both modes):** never prints the PDF path/basename/text, OCR text, image bytes, base64,
  data URIs, tokens, headers, model/mmproj/executable paths, raw argv, or full URLs. Emits only a fixed
  **closed-vocabulary** summary (`status`, `pilot_inserted`, `safe_asset_ref_present`, `html_render_ok`,
  `pdf_render_ok`, `docx_render_ok`, `export_zip_ok`, `export_png_included`, `warnings`, `failure_category`)
  plus closed-vocab step markers; exceptions are sanitized to closed `failure_category` tokens (only an
  exception *type name* is surfaced); a final sweep scans every pipeline-derived string. All working files
  live under a temp/output dir — nothing committed.
- **New `docs/VISUAL_PILOT_OPERATOR_VALIDATION.md`** — runbook: why it exists, opt-in/non-private policy, the
  safe placeholder command template, the closed-vocab field tables, and the recorded status — now
  `manual_operator_pdf_validation: run` / `status: ok` (see below).
- **Real operator validation — RUN, successful (sanitized):** the harness was run on **one real, non-private,
  operator-supplied PDF**. Recorded sanitized result: `status: ok`, `pilot_inserted: true`,
  `safe_asset_ref_present: true`, `html_render_ok: true`, `pdf_render_ok: true`, `docx_render_ok: true`,
  `export_zip_ok: true`, `export_png_included: true`, `warnings: [multiple_figures_present_one_inserted]`,
  `failure_category: none`, `no_leak_sweep: clean`. The `fitz_local` pilot found **one or more** candidates and
  inserted **exactly one**, preserving the one-figure rule; the warning is **expected** and confirms the design
  rule was obeyed. **This clears the current single-figure visual-pilot operator-validation gate.** It does
  **not** clear the Chandra live-validation gate and does **not** approve multi-figure insertion. Only the
  sanitized closed-vocab summary was recorded — no real path, filename, document/OCR text, image bytes, base64,
  data URI, full URL, raw argv, token, or raw exception.
- **Results:** host `--self-test` PASS (HTML/PDF render real; DOCX/export skip calmly w/o python-docx/FastAPI);
  **in container `--self-test` PASS** (all of pilot_inserted / safe_asset_ref / html / pdf / docx / export_zip /
  export_png `true`, 0 warnings, no leak). Real `--pdf` operator run recorded successful (sanitized fields
  above). Refusal + sanitized missing-file paths verified (no path echoed).
  `compileall api pipeline test_scripts` + `git diff --check` clean; `/api/health` ok.
- **Scope / hard boundaries:** **no** production-code change, **no** frontend/UI change, **no** renderer /
  export / extraction / OCR-routing / prompt change, **no** new API route, **no** advisory schema change,
  **no** generic artifact-list change, **no** multi-figure / Chandra / Mistral / Gemini / cloud, **no**
  model/provider/llama-server/network call, **no** new image pipeline, **no** committed PDF/image/DOCX/ZIP
  fixture. **≤1 figure; `fitz_local` only; safe `assets/<slug>.png` only — unchanged.** The real operator
  validation pass is now **recorded**, clearing the single-figure operator gate; **Chandra extraction
  integration remains blocked by Slice 45 `status:not_run`; multi-figure stays deferred** (out of scope until
  separately designed).

---

## Slice 58 — **Visual-pilot stitched E2E validation harness + record**, on `slice58-visual-pilot-e2e-validation`. **COMMITTED `39dc162`, merged to trunk.**

- **Purpose:** prove the already-shipped **single-figure** visual pilot (Slices 52–57) works as **one connected
  chain** before any visual expansion. This is a **validation/harness slice only** — it adds **no** production
  code and changes **no** behavior.
- **Chain stitched (output of each stage feeds the next):** safe job-local `assets/<slug>.png` → existing
  visual manifest / replacement-plan shape → global pilot master flag ON → per-job opt-in ON → standard
  markdown image insertion (**exactly one** figure) → HTML/PDF/DOCX render compatibility → export ZIP
  portability including the single referenced PNG.
- **New harness `test_scripts/test_visual_pilot_e2e_validation.py`** — reuses the existing helpers/patterns
  from `test_visual_markdown_insertion.py`, `test_visual_markdown_render.py`, `test_visual_pilot_export_asset.py`,
  and `test_visual_pilot_options.py`. It builds a real `JobManager.Job`, regenerates `clean.md` via the real
  `apply_visual_markdown_pilot` (opted in through the persisted manifest) and `save_clean_md`, then renders +
  exports it. Verifies all 13 points: one image; safe `assets/<slug>.png` ref; generic page caption (real
  `None`-caption path, not raw OCR); unsafe refs rejected; manifest/plan/source-PNG unmutated; HTML safe
  relative `<img>` + no absolute path; non-empty PDF (SKIP w/o Chromium); non-empty DOCX (SKIP w/o
  python-docx); export carries exactly the one referenced PNG under `assets/`; extra crop / blanket assets dir
  excluded; `files_included` counts requested artifacts only and the PNG alone still `404`s the gate; bundle
  index records only the safe relative `visual_pilot_asset`; and a final no-leak sweep over every serialized
  output.
- **Synthetic data only:** the test PNG is generated at runtime by a tiny stdlib builder (`zlib` + `struct`);
  every PNG/PDF/DOCX/HTML/ZIP is written under a temp dir and removed. **No committed binary/image/PDF/DOCX/ZIP
  fixture, no base64, no data URI.**
- **New `docs/VISUAL_PILOT_E2E_VALIDATION.md`** — records what the harness proves, what it does **not** prove,
  the synthetic-data discipline, and the manual-review status: `manual_operator_pdf_validation: not_run`
  (reason `non_private_operator_sample_not_supplied`).
- **Results:** host `16 passed / 0 failed / 2 skipped` (DOCX + export skip w/o python-docx/FastAPI); **in
  container `29 passed / 0 failed / 0 skipped`** (full chain). Existing `test_visual_markdown_insertion`
  (53/0), `test_visual_markdown_render` (6/0/1), `test_visual_pilot_export_asset` (9/0),
  `test_visual_pilot_options` (16/0), `test_anki_export` (46/0), and offline eval all green;
  `compileall api pipeline test_scripts` + `git diff --check` clean; `/api/health` ok.
- **Scope / hard boundaries:** **no** production-code change, **no** frontend/UI change, **no** renderer /
  export / extraction / OCR-routing / prompt change, **no** new API route, **no** advisory schema change,
  **no** generic artifact-list change, **no** multi-figure / Chandra / Mistral / Gemini / cloud, **no**
  model/provider/llama-server/network call, **no** new image pipeline, **no** committed image fixture. **≤1
  figure; `fitz_local` only; safe `assets/<slug>.png` only — unchanged.** **Chandra extraction integration
  remains blocked by Slice 45 `status:not_run`.**

---

## Slice 57 — **Visual-pilot readiness capability + Builder guard**, on `slice57-visual-pilot-readiness-guard`. **COMMITTED `9c4ccc0`, merged to trunk.**

- **Purpose:** make the Builder's per-job visual opt-in **accurately reflect whether the pilot can realistically
  work for a new job**. The toggle stays **default-off**, but it is now **enabled only when the backend reports
  readiness** — i.e. both server-side switches are on. This is a **readiness/UX guard only**; it does **not**
  enable visual insertion, change the backend dual gate, or auto-enable extraction.
- **Why readiness needs two switches:** insertion needs (1) the global pilot master flag
  `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` AND (2) local figure extraction
  `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION` (which is what produces the `fitz_local` `extracted_figure` the pilot
  inserts for **new** jobs). With master on but extraction off, a fresh job has nothing to insert — so the
  opt-in would be a dead control. Readiness = master **AND** extraction.
- **Backend (`/api/options.capabilities`):** now reports three **non-secret booleans** (no env names, paths,
  tokens, or raw config):
  - `visual_markdown_image_pilot` — global pilot master flag (**preserved**; same meaning as Slice 54/55 —
    backward-compatible).
  - `local_figure_extraction` — local figure-extraction flag.
  - `visual_references_ready` — `true` **only when both** of the above are `true`.
- **Frontend (`visualPilotOptIn.js` + Builder):** two new pure helpers
  `isVisualReferencesReady(capabilities)` (trusts the backend's derived flag, falls back to AND-ing the two
  components for older/partial payloads) and `visualPilotReadinessNote(capabilities)` (fixed safe copy). The
  Builder mirrors readiness into the toggle's enabled/checked state and shows a **calm** note when not ready:
  - master flag off ⇒ *"Visual references are not enabled on this server."*
  - master on but extraction off ⇒ *"Visual references need local figure extraction to be enabled on this server."*
  - both on ⇒ toggle enabled, no note.
- **Request payload unchanged from Slice 55:** `enable_visual_references` is added **only** when the user opts
  in; a default / opted-out / not-ready request stays byte-identical.
- **Scope:** small `/api/options` capability refinement + small Builder guard + focused tests/docs. **No** new
  page, broad visual settings, export-bundle change, generic artifact-row change, advisory schema change,
  renderer/prompt/extraction/OCR-routing change, Chandra/Mistral/Gemini/cloud, model/llama-server/network
  call, image processing, image fixtures, or `clean.md` write. **No more than one figure; `fitz_local` only;
  safe `assets/<slug>.png` only — all unchanged.**
- **Backend gates unchanged (defence-in-depth):** the global master flag **cannot be bypassed**; the per-job
  opt-in still defaults false; readiness in `/api/options` is a **UI affordance only** and is **not** a new
  insertion gate — `apply_visual_markdown_pilot` still independently re-checks both switches and remains
  degrade-never-fail even if capabilities are stale/absent. Local figure extraction is **never** auto-enabled
  by the toggle and extraction is **never** run because of it.
- **Safety/no-leak:** capabilities expose only safe booleans; the readiness notes are fixed copy. No env
  names, paths, tokens, headers, socket/model/mmproj/executable paths, raw argv, image bytes, data URIs,
  base64, OCR text, or provider payloads in the API response, the UI, logs, docs, or tests.
- **Unchanged:** guide output; prompts; PDF/HTML/DOCX rendering; extraction/OCR routing; visual advisory JSON
  ride-alongs (Slice 51); the Slice 56 PNG export ride-along; Anki `.apkg` (Slice 53); CSV/TSV quiz exports;
  the default-off Slice 54/55 pilot gate. **Chandra extraction integration remains blocked by Slice 45
  `status:not_run`.**
- **Tests:**
  - New `test_scripts/test_visual_pilot_options.py` — Part A (pure, host): readiness truth table over all four
    env combinations (master off+figure off / on+off / off+on / on+on ⇒ ready only when both on), all plain
    booleans. Part B (FastAPI/Docker): `server.options()` capability subtree has the three keys with correct
    booleans, backward-compatible `visual_markdown_image_pilot`, a fixed safe key set, and no
    secret/path/env-name/url in the payload; default env ⇒ not ready. **16/0 on host** (Part B auto-skips).
  - Updated `frontend/scripts/verify-visual-pilot-opt-in.mjs` — readiness truth table, calm master-off and
    extraction-off messages, ready⇒enabled, payload field only when checked, and no path/token/env-name/
    url/data-uri leak in the notes.
  - Existing batteries still green: `test_visual_markdown_insertion`, `test_visual_markdown_render`,
    `test_visual_pilot_export_asset`, `test_anki_export`, visual planner/scoring/artifact/manifest/advisory,
    `test_local_figure_extraction`, OCR/Chandra suites, eval, frontend build + all verifies.
- **Status:** **NOT committed** (per instruction). Host validation green; Docker rebuild/recreate +
  `/api/health` + `smoke_release.py` + `/api/options` readiness spot-check run before any commit.

---

## Slice 56 — **Export the referenced visual-pilot PNG** with bundles, on `slice56-visual-pilot-export-asset`.

- **Purpose:** make exported Markdown/HTML **portable**. When a guide's `clean.md` contains the Slice 54
  pilot's safe image reference `![caption](assets/<slug>.png)`, the export bundle now includes **that single
  referenced job-local PNG** so the markdown image resolves outside the app too. Nothing else about export
  changes.
- **Scope:** **backend export-bundle logic only** (`api/server.py` `export_bundle`) plus two small read-only
  detection helpers in `pipeline/visual_markdown_insertion.py` and a focused test. **No frontend/UI, no new
  API route, no new generic artifact row, no schema change, no renderer/prompt/extraction/OCR-routing
  change, no Chandra, no model/llama-server/network call, no image processing, no `clean.md` write.**
- **Detection (read-only):**
  - `extract_visual_pilot_asset_refs(markdown_text)` — pure/string-only. Scans for `![...](assets/<slug>.png)`
    and keeps only refs that pass the existing Slice 54 `validate_visual_asset_ref` (fixed
    `assets/<slug>.png` shape; rejects absolute, `..`, backslash, URL, `data:`/base64, non-PNG, nested
    subdir, `-`/non-`[A-Za-z0-9_]` slugs). Order-preserving + de-duped; never raises.
  - `find_exportable_visual_pilot_asset(job)` — reads the job's `clean.md` read-only (new `_read_text`
    helper; never opens image bytes), returns the **first** referenced ref **only if** the file really
    exists **inside** the job dir (existing `_asset_file_ok` realpath containment ⇒ symlink escapes
    rejected). Returns **at most one** ref (pilot's one-figure rule); `None` on no clean.md / no safe ref /
    missing / unsafe file. Never raises.
- **Bundle wiring:** in `export_bundle`, after the Slice 51 advisory ride-alongs, the detected PNG is added
  as ZIP entry `<base_dir>/assets/<slug>.png` (preserves the existing per-job relative layout, so the
  bundled `clean.md`/`final.html` resolve it). Defence-in-depth re-check (`is_relative_to` + `is_file`)
  before writing. Any problem is caught and **skipped calmly** — export still succeeds.
- **Boundary decisions:**
  - **Not** counted toward `files_included` / `total_included` — like the advisory ride-alongs it can
    **never by itself** satisfy the "at least one requested artifact" gate (a pilot-PNG-only job with no
    requested artifact still 404s).
  - Includes **only** the one *referenced* PNG — **never** the whole `assets/` dir, **never** unreferenced
    or extra cropped images.
  - The bundle index records only the **safe relative ref** (`visual_pilot_asset: "assets/<slug>.png"` or
    `null`) — no absolute/local filesystem path, no image bytes.
- **Safety/no-leak:** no image bytes, absolute paths, `..`, backslashes, URLs, data URIs, base64, tokens,
  headers, socket/executable/model/mmproj paths, raw argv, OCR text, or provider payloads in logs, the ZIP
  metadata, the manifest, docs, or tests. Source PNG and `clean.md` are left **byte-identical** (no mutation).
- **Unchanged:** guide output; prompts; PDF/HTML/DOCX rendering; extraction/OCR routing; visual advisory
  JSON ride-alongs (Slice 51); Anki `.apkg` export (Slice 53); CSV/TSV quiz exports; the default-off visual
  pilot gate (Slices 54/55). **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**
- **Tests:** `test_scripts/test_visual_pilot_export_asset.py`.
  - **Part A (pure, host-runnable):** ref extraction order/de-dup; rejects every unsafe/non-pilot ref;
    `find_…` returns the first referenced+present ref, and `None` for missing-file / no-clean.md /
    unreferenced / **symlink-escape**. **9/0** on host.
  - **Part B (bundle, runs in Docker / when FastAPI importable):** referenced PNG rides along exactly once
    under `<base_dir>/assets/`; unreferenced extra PNG **not** bundled; entry is relative+safe; carries real
    bytes but the manifest does **not** echo image bytes/paths; records safe relative ref; `files_included`
    counts requested artifacts only; missing referenced file skipped calmly (export still succeeds, ref
    `null`); no-safe-ref job bundles no PNG; unsafe refs all rejected; pilot-PNG-only job still 404s; source
    PNG + `clean.md` byte-identical after export.
- **Status:** **NOT committed** (per instruction). Host validation green (Part A + full backend battery +
  eval + frontend build/test/verify); Docker rebuild + `/api/health` + `smoke_release.py` + Part B bundle
  section run before any commit.

---

## Slice 55 — **Per-job opt-in** for the visual markdown image pilot, on `slice55-visual-pilot-job-opt-in`.

- **Purpose:** make the proven Slice 54 pilot **user-controllable per job** while keeping it **default-off
  and safe**. The pilot now requires **two gates AND-ed together**: the global env master switch **and** an
  explicit per-job opt-in. A job opt-in can **never** bypass the master switch.
- **Gating truth table** (both required; only the last row may insert — still subject to all Slice 54
  candidate/path safety gates):
  - global **false** + job **false** ⇒ no insertion (`visual_pilot_disabled`)
  - global **false** + job **true**  ⇒ no insertion (`visual_pilot_disabled`) — opt-in cannot bypass env
  - global **true**  + job **false** ⇒ no insertion (`visual_pilot_job_opt_out`)
  - global **true**  + job **true**  ⇒ insertion *may* run (≤1 `fitz_local` `extracted_figure`, safe path)
- **Global master flag:** `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` (env; truthy ∈ {1,true,yes,on}),
  **still required, default false**. Unchanged from Slice 54.
- **Per-job option:** persisted job manifest key **`visual_markdown_image_pilot`** (bool, **default false**).
  An old job created before this option ⇒ key absent ⇒ treated as **false**. Coerced to a strict bool;
  any non-bool/malformed value ⇒ **false** (never accidentally on).
- **Request field:** **`enable_visual_references`** (bool, default false) on `LLMJobRequest`, wired into
  **both** the JSON and the multipart `_parse_llm_request` branches (multipart via `_form_bool(...,False)`).
  `create_llm_job` passes it to `run_llm_job(enable_visual_references=…)`, which stores it as the
  `visual_markdown_image_pilot` manifest option. **Only the LLM path** carries this (only LLM+PDF jobs ever
  produce a `fitz_local` `extracted_figure`); paste/upload paths are untouched (no dead toggle).
- **Pilot integration point:** `pipeline/visual_markdown_insertion.py` gained
  `is_job_visual_pilot_opt_in(job)` (reads the manifest key, total/never-raises) and
  `apply_visual_markdown_pilot` now checks the env switch **first**, then the per-job opt-in, before any
  candidate read. Env-off short-circuits without ever reading the job option. New closed-vocab reason
  `visual_pilot_job_opt_out`. **No change to the single `save_clean_md` chokepoint**; the helper is still
  wired at the same spot in `run_raw_markdown_pipeline`.
- **Capability flag (non-secret):** `/api/options` now returns
  `capabilities.visual_markdown_image_pilot` = the global master-switch state, so the Builder can render
  its opt-in **enabled** (master on) vs **disabled-with-note** (master off). Exposes only the experimental
  on/off bit — never a key/token/path/URL.
- **Frontend (Builder only, no redesign):** a single experimental toggle **"Add one visual reference
  (experimental)"** in the LLM settings block, **default unchecked**, **disabled with a short note when the
  server capability is off**. It adds the single `enable_visual_references: true` to the request **only when
  on** (default/opted-out request stays byte-equivalent). New pure helper `frontend/src/visualPilotOptIn.js`
  (`visualPilotPayloadFields`, `isVisualPilotEffectivelyOn`, `isVisualPilotToggleEnabled`) keeps the
  payload/toggle logic React-free + node-testable. **No new page, no broad visual settings, no export/
  artifact rows, no Job Details panel change.**
- **Slice 54 visual behaviour is unchanged:** ≤1 `fitz_local` `extracted_figure`; safe `assets/<slug>.png`
  only; existing markdown/render path; no renderer rewrite; no Chandra/Mistral/Gemini/cloud; degrade-never-
  fail. The opt-in only adds a *second* gate in front of the same Slice 54 path.
- **Tests:**
  - `test_scripts/test_visual_markdown_insertion.py` — added a **flag-independent truth-table** (sets/clears
    the env var itself) covering all four (global, job) combos incl. **(off,on) proving opt-in can't bypass
    env**, plus opt-in coercion unit checks (missing/None/false/`"banana"`/int ⇒ false; `true`/`"true"`/
    manifest-read ⇒ true; broken `read_manifest` degrades to false). **flag-off 53/0, flag-on 77/0.**
  - `test_scripts/test_visual_markdown_render.py` — added a **negative-gate** case (master switch on + job
    opted out ⇒ original markdown, renders with **no `<img>`**). **6/0, 1 skip** (docx host dep) both modes.
  - `frontend/scripts/verify-visual-pilot-opt-in.mjs` (added to `npm test`) — payload field present **only**
    when opted in; never serialises `false`; toggle forced off+disabled when capability off; exact safe
    field name `enable_visual_references` + label; full no-leak scan.
- **Scope guards:** default still **off**; master env flag still required (not optional); ≤1 figure; no
  Chandra/Mistral/Gemini/cloud images; no image generation; no broad visual settings; no export-bundle/
  artifact-list/advisory-schema change; no prompt/OCR-routing/extraction/broad-render rewrite; no model/
  llama-server/network call; no `clean.md` write outside `save_clean_md`.
  **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**
- **Status:** **NOT committed** (per instruction). Host validation green (backend battery + eval + frontend
  build/test/verify); Docker rebuild + `/api/health` + `smoke_release.py` + flag-on focused validation run
  before any commit.

---

## Slice 54 — Minimal **V4/V5 visual markdown image pilot**, off by default, on `slice54-visual-markdown-image-pilot`.

- **Purpose:** finally prove the *smallest possible* end-to-end visual path. When an explicit,
  off-by-default flag is set, insert **at most one** existing `fitz_local` `extracted_figure` (already
  cropped to the job's `assets/<slug>.png` by Slice 40) into the generated guide as a **standard
  Markdown image** — `![safe caption](assets/<slug>.png)` — flowing through the **existing**
  `JobManager.save_clean_md` chokepoint and the **existing** PDF/HTML/DOCX renderers. **No renderer was
  rewritten. No Chandra. No new image generation. No new artifact. No frontend toggle.**
- **Key finding (the thing this pilot set out to prove):** the existing render path *already* resolves a
  job-local relative `assets/<slug>.png` reference. PDF/HTML render from a `file://` URI rooted at the
  job dir (`final.html` sits beside `assets/`), so a relative `<img src="assets/…">` resolves locally;
  the DOCX renderer's `_resolve_image_path` already resolves relative refs against the job dir and
  degrades to an `[image missing: …]` marker rather than failing. **So no renderer change was needed.**
- **Feature flag:** `GUIDEFORGE_ENABLE_VISUAL_MARKDOWN_IMAGE_PILOT` (env; truthy ∈ {1,true,yes,on}),
  **default false** — mirrors the existing `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION` pattern. With the flag
  unset the pilot is a **no-op**: it returns the sanitized clean Markdown **unchanged (byte-identical)**
  without reading any artifact, so default guide output is exactly as before this slice.
- **New module:** `pipeline/visual_markdown_insertion.py` (stdlib-only: `json`, `os`, `re`, `sys`,
  `typing`; imports nothing from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server;
  reads only the job's already-persisted, already-sanitized `visual_assets_manifest.json` /
  `visual_replacement_plan.json` and the on-disk `assets/` PNG). Public API:
  - `is_visual_markdown_pilot_enabled() -> bool`
  - `apply_visual_markdown_pilot(job, clean_md) -> (str, info)` — the degrade-never-fail entry point.
  - `select_visual_markdown_candidate(job, *, manifest=None, replacement_plan=None) -> dict | None`
  - `validate_visual_asset_ref(asset_ref) -> str | None`
  - `build_visual_markdown_image(candidate) -> str`
  - `insert_visual_markdown_reference(clean_md, candidate) -> (str, info)`
- **Integration point (single, surgical):** `pipeline/run_markdown_job.py::run_raw_markdown_pipeline`,
  immediately **before** the existing `job.save_clean_md(...)` call — `clean = sanitize(raw)` →
  `clean, _ = apply_visual_markdown_pilot(job, clean)` → `save_clean_md(clean, "generated")`. **No new
  clean.md writer; the single chokepoint is preserved** (the figure is snapshotted into version history
  like any other clean.md write).
- **Candidate rules (narrow on purpose):** `fitz_local` only; `extracted_figure` only; **one maximum**.
  Preferred = a `visual_replacement_plan.json` item with `candidate_action:"candidate_include_as_figure"`
  whose `asset_id` resolves to a safe `extracted_figure` in `visual_assets_manifest.json`. Fallback
  (flag-on, all safety gates still applied) = the first safe `fitz_local` `extracted_figure` in the
  manifest. **Never** Chandra (`chandra_local` / a `chandra_blocked` marker), **never** `mistral_ocr`,
  **never** `page_visual_signal`. If no safe candidate exists, the figure is omitted and the job
  continues normally.
- **Safe asset-path gate:** the ref must be exactly `^assets/[A-Za-z0-9_]+\.png$` **and** the file must
  really exist *inside* the job directory (realpath-containment check rejects symlink escapes). Rejected:
  absolute paths, `..`, backslashes, URL-like refs, `data:`/base64, subdirs, non-PNG. The rendered
  Markdown never contains a host path; the renderer never receives an arbitrary host path from model
  output.
- **Caption:** a generic, plain-text, length-limited (≤80), safe-charset, Markdown-escaped string
  derived from the **source page only** (`Extracted figure from source page N`). Manifest captions are
  `None` in practice, so the generic path is always used. **No** raw caption / OCR text / provider
  payload / path / URL / token / image byte / data URI is ever emitted.
- **Placement (dumb v1):** if the guide carries a deterministic `<!-- visual-anchor: source_page_NNNN -->`
  marker for the figure's page, the image is placed at that anchor; otherwise a single trailing
  `## Visual Reference` section is appended. Never mid-prose, never semantic, never derived from raw
  source text.
- **Degrade-never-fail:** any failure (no candidate / unsafe ref / missing file / malformed artifact /
  insertion error) yields the **original** Markdown and a **closed-vocab** reason (`visual_pilot_disabled`,
  `visual_candidate_unavailable`, `visual_candidate_unsafe`, `visual_asset_missing`,
  `visual_asset_path_invalid`, `visual_markdown_insert_failed`, `visual_format_unsupported`,
  `visual_render_degraded`). The job never fails because of the pilot; reasons are stderr-only (no
  job.json field, no artifact-list change). Raw paths / exceptions are never logged.
- **PDF/HTML/DOCX validated separately:** PDF + HTML use the existing Markdown→render path (relative
  `assets/…` resolves from the job `file://` root); DOCX embeds the relative image via the existing
  `_resolve_image_path` or degrades to its existing `[image missing: …]` marker — never fails the export.
  No DOCX/Chromium rewrite.
- **New tests:** `test_scripts/test_visual_markdown_insertion.py` (**flag-off 26/0**, **flag-on 50/0**:
  flag-off byte-identical even with artifacts present; one-image-max; ref shape; reject absolute/`..`/
  backslash/url/data-uri/non-png/subdir; reject Chandra / chandra_blocked / page_visual_signal; missing
  file degrades; plan→manifest fallback; caption sanitization + length limit; anchor vs Visual-Reference
  placement; no mutation of manifest/plan on disk or in-memory; full no-leak scan) and
  `test_scripts/test_visual_markdown_render.py` (HTML `<img src="assets/…">` with **no host path**; PDF
  renders non-empty via Chromium; DOCX embeds/degrades without raising — each SKIPs cleanly when its host
  dep is absent). All existing visual/anki/ocr/eval/export tests still pass; frontend build/test/verify
  unchanged (no frontend change this slice).
- **Scope guards:** flag **off by default**; ≤1 figure; no Chandra/Mistral/Gemini/cloud images; no
  frontend toggle; no export-bundle change; no generic artifact-list change; no prompt change; no OCR
  routing change; no extraction behavior change (only reads already-produced advisory artifacts when the
  flag is on); no model/llama-server/network call; no `clean.md` write outside `save_clean_md`.
  **Chandra extraction integration remains blocked by Slice 45 `status:not_run`.**
- **Status:** **committed `cdebbaa` and fast-forward merged to `chrome-renderer-v1` (pushed).** Slice 55
  builds on it.

---

## Slice 53 — True Anki **`.apkg`** export (backend core + export route + tiny UI button) on `slice53-anki-apkg-export`.

- **Purpose:** add a **real, importable Anki `.apkg` package** export for the *already generated*
  quiz / flashcard items in `jobs/<id>/quizzes/<n>.json`, so the operator can study generated material
  in Anki. This is **direct user-visible study value**. It deliberately does **not** touch the visual
  advisory pipeline, visual rendering, Chandra, OCR routing, extraction, or guide-generation prompts.
- **New module:** `pipeline/anki_export.py` — **stdlib-only** (`sqlite3`, `zipfile`, `json`, `hashlib`,
  `html`, `io`, `os`, `re`, `tempfile`). An `.apkg` is a ZIP holding a SQLite `collection.anki2`
  (Anki **schema 11** — the long-stable, universally importable format) plus an empty `media` map.
  **No `genanki`/third-party dependency was added** (requirements.txt unchanged); no network, no
  model/provider call, no image/media, no LaTeX. Public API:
  - `build_apkg(items, *, job_id, quiz_n, title=None) -> bytes`
  - `normalize_cards(items) -> (list[(front_html, back_html)], skipped_counts)`
  - `deck_id_for(job_id, quiz_n) -> int`, `deck_name_for(title) -> str`,
    `apkg_filename(job_id, quiz_n) -> str`
- **Card model:** single shared **"GuideForge Basic"** 2-field model (`Front` / `Back`). Question →
  Front (MCQ also lists its options so the card is self-testable); answer → Back (MCQ resolves the
  answer letter to its full option text — mirrors the existing `_render_quiz_export` front/back rules).
  All field text is **HTML-escaped** (newlines → `<br>`) so user study text can't be mis-parsed as markup.
- **Deterministic deck/model IDs (no churn, no leaks):** model id is a **fixed app-level constant**
  (`MODEL_ID = 1010101010`) reused across every export; deck id is a stable SHA-256 of
  `"deck"+job_id+quiz_n` folded into a safe Anki id range (per-job deck under the `GuideForge::<title>`
  subdeck). Note **GUIDs are index-based** (derived from internal ids, **never** card text), so
  re-exporting the same quiz **updates** rather than duplicates on re-import. Creation/mod timestamps
  are **fixed constants** (never wall-clock) → re-export is byte-stable. The required Anki `csum` is the
  format's internal one-way duplicate checksum of the first field (not an externally meaningful id).
- **Route:** **no new route** — extended the existing `GET /api/jobs/{job_id}/quizzes/{quiz_n}/export`
  by adding `apkg` to `VALID_EXPORT_FORMATS` (now `{csv, anki_tsv, quizlet, apkg}`). For `apkg` the
  route returns `application/octet-stream`, `Content-Disposition: attachment; filename="quiz-<job>-<n>.apkg"`
  (existing naming convention; filename is path-sanitized). **CSV / anki_tsv / quizlet exports are
  unchanged.**
- **Degrade-safe input:** malformed / empty cards are skipped (closed-vocab counts:
  `skipped_empty`, `skipped_malformed`); **zero surviving cards → a valid empty-deck `.apkg`** (no
  exception), matching the existing route's "empty export, not an error" behaviour.
- **No-leak:** the package embeds only the user's own Front/Back study text + a sanitized deck name.
  It never embeds provider keys, headers, tokens, socket paths, local/host paths, executable paths,
  model/`mmproj` paths, raw argv, raw OCR dumps, raw provider/model payloads, image bytes, data URIs,
  base64, artifact URLs, or internal job-directory metadata. `job_id` only seeds derived numeric
  ids/guids/filename — it is never written into the package.
- **Frontend:** one-line addition to the existing quiz export-button row in `RecentJobsPanel.jsx`
  (`{ format: "apkg", label: "Anki .apkg" }`) using the existing `quizExportUrl(...)` helper. No new
  page, no redesign, no visual-advisory UI touched.
- **New test:** `test_scripts/test_anki_export.py` (**46/0** on host; route section runs in Docker) —
  valid non-empty ZIP w/ `collection.anki2`+`media`, schema-11 tables, correct note/card counts,
  field-separator + MCQ option/answer content, **byte-identical re-export**, stable GUIDs, per-job
  distinct decks, malformed/empty skip counts, empty-deck package, full no-leak scan (keys/paths/urls/
  data-uris/sockets/job-id), stdlib-only import assertion, and route-level checks (apkg status/
  content-type/disposition + **CSV/anki_tsv still work** + bad-format 400).
- **Scope guards (unchanged by this slice):** no FSRS / in-app spaced repetition; no images/audio/media
  in decks; no guide-generation prompt changes; no PDF/HTML/DOCX render changes; no visual insertion
  wired into guides; no OCR routing changes; **Chandra extraction integration remains blocked by
  Slice 45 `status:not_run`**; visual render insertion remains a separate decision.
- **Status:** **NOT committed** (per instruction). Validation pending Docker rebuild + `/api/health` +
  `smoke_release.py`.

---

## Slice 52 — Visual **insertion planner core** (pure, unwired; roadmap V3+) on `slice52-visual-insertion-planner-core`.

- **Purpose:** add a pure, deterministic **insertion planner core** — the next V3+ step after the
  replacement planner (`docs/VISION_ROADMAP.md` §8). It consumes an already-sanitized
  `visual_replacement_plan.json`-shaped replacement plan (and, optionally, a **safe-only** source-page
  anchor inventory) and returns a **separate advisory insertion-position plan** — a per-asset
  `insertion_mode` / `placement` / `anchor_status` with closed-vocab `reasons`. It does **not** mutate
  the replacement plan or anchors, persist an artifact, embed visuals, change extraction/guides/
  rendering, or wire into production. **Not** a Chandra integration slice, **not** a visual-embedding
  slice.
- **New module:** `pipeline/visual_insertion_planner.py` (stdlib-only: `re`, `typing`; imports nothing
  from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/job-manager/extraction/
  run-job/`visual_*` cores; no `json`/`os`/`pathlib`/`socket`/`subprocess`). Public API (small, pure,
  total):
  - `plan_visual_insertion_item(item, *, anchors_by_page=None) -> dict`
  - `plan_visual_insertions(items, *, anchors_by_page=None) -> list[dict]`
  - `build_visual_insertion_plan(replacement_plan, *, source_page_anchors=None) -> dict`
- **Insertion plan report shape:** `{version:1, kind:"visual_insertion_plan", status:"completed",
  source:"visual_replacement_plan.json", insertions:[…], summary:{insertion_count,
  figure_reference_count, table_reference_count, text_summary_reference_count, review_only_count,
  unknown_count, anchor_matched_count, anchor_missing_count}, warnings:[…]}`. Each insertion:
  `{asset_id, source_page, source_provider, asset_type, candidate_action, insertion_mode, placement,
  anchor_id, anchor_status, reasons:[…], warnings:[…]}`.
- **Closed vocab only:** `insertion_mode` ∈ {figure_reference, table_reference, text_summary_reference,
  review_only, unknown}; `placement` ∈ {source_page_reference, review_appendix, unknown};
  `anchor_status` ∈ {matched, missing, not_required, unknown}; `candidate_action` ∈
  {candidate_include_as_figure, candidate_convert_to_table, candidate_summarize_as_text, review_only,
  unknown}; `source_provider` ∈ {fitz_local, chandra_local, mistral_ocr, unknown}; `asset_type` ∈
  {page_visual_signal, extracted_figure, table, table_region, equation_block, diagram, figure,
  image_region, cropped_region, unknown_region, unknown}; closed `reasons`
  (candidate_include_as_figure/convert_to_table/summarize_as_text, review_only, anchor_matched,
  anchor_missing, source_page_reference, review_appendix, chandra_blocked, low_information_signal,
  unknown_candidate_action, input_sanitized); closed `warnings` (replacement_plan_malformed,
  replacement_item_malformed, asset_id_missing/invalid, source_page_invalid, source_provider_unrecognized,
  asset_type_unrecognized, candidate_action_unrecognized, anchor_id_invalid, anchor_lookup_missing,
  input_unrecognized).
- **Planning rules (advisory, conservative):** `candidate_include_as_figure` → `figure_reference`;
  `candidate_convert_to_table` → `table_reference`; `candidate_summarize_as_text` →
  `text_summary_reference`; `review_only` → `review_only` (placement `review_appendix`, anchor
  `not_required`); `unknown`/malformed → `unknown`. **Anchors are presence-only and safe-only:** for a
  reference mode, a matching source-page anchor yields `anchor_status:"matched"` + placement
  `source_page_reference` + a sanitized `anchor_id`; any miss (no inventory, uncovered page, or
  dropped/invalid anchor id) degrades to `anchor_status:"missing"` + placement `unknown` +
  `anchor_lookup_missing` — the item stays advisory and must not be placed without an anchor.
- **Chandra still blocked:** any `chandra_local` item (or one carrying a `chandra_blocked` marker on its
  input reasons) is **never** mapped to a direct `figure_reference`/`table_reference`/
  `text_summary_reference` mode — it degrades to `review_only` + `review_appendix` and always carries
  the closed reason `chandra_blocked`, because Chandra *extraction* integration remains gated by Slice
  45 `status:not_run` (`operator_input_not_supplied`). This core reads only the planned-item *shape*; it
  integrates nothing.
- **Pure / unwired / no production change:** not imported by `run_llm_job.py` or anything else; **no
  artifact written** (no `visual_insertion_plan.json` this slice); no API route; no frontend/UI; no
  export-bundle/generic artifact-list exposure; `visual_assets_manifest.json` /
  `visual_asset_scoring.json` / `visual_replacement_plan.json` schemas unchanged and **never mutated**;
  no extraction/OCR-routing/prompt/render/guide-output change; no `clean.md` write; no model/
  llama-server/cloud/network call; no image files/bytes. Captions/source text/provider payloads/paths/
  tokens/data-URIs/base64/argv are never read into output; an anchor inventory contributes only a
  sanitized slug-safe `anchor_id` (no raw anchor field echoed).
- **New test:** `test_scripts/test_visual_insertion_planner.py` (**243/0**) — include_as_figure/
  convert_to_table/summarize_as_text with a matching anchor → the matching reference mode; review_only
  needs no anchor; missing anchor degrades with `anchor_lookup_missing`/`anchor_missing`; malformed
  replacement plan → safe completed report with `replacement_plan_malformed`; malformed item → safe
  `unknown` fallback; invalid asset id → deterministic slug-safe fallback; invalid source page → `None`
  + `source_page_invalid`; invalid anchor id dropped (never emitted); chandra_local/chandra_blocked →
  `chandra_blocked` + never a direct insertion; no mutation of plan/anchors; smuggled
  captions/source-text/provider-payloads/paths/tokens/base64/data-URIs/image-bytes never leak; summary
  counts; determinism; no forbidden imports.
- **Validation:** `compileall api pipeline test_scripts` OK; insertion-planner **243/0**;
  replacement-planner **186/0**; replacement-plan-artifact **68/0**; scoring-core **146/0**;
  scoring-artifact **58/0**; advisory-export-bundle skips its endpoint section on host Python (FastAPI
  absent — covered live in Slice 51); manifest **65/0**; figure-extraction **50/0** (+2 skipped);
  chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness **96/0**;
  ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**; offline
  eval scored 3 guides (no regression); frontend build + test green; verify-job-details-visual-advisory
  green; `git diff --check` clean. `smoke_release.py` / Docker **not required** (pure/unwired — no
  server/extraction/render/artifact/export/UI behavior touched). **Status:** NOT committed (per
  instruction) on `slice52-visual-insertion-planner-core`.

---

## Slice 50 — **Job Details "Visual advisory" diagnostics panel** (read-only UI) on `slice50-jobdetails-visual-advisory-panel`.

- **Purpose:** add a read-only Job Details drawer tab that surfaces the advisory **visual artifact
  chain** — `visual_assets_manifest.json` (Slice 40) → `visual_asset_scoring.json` (Slice 47) →
  `visual_replacement_plan.json` (Slice 49) — using **exact-name artifact fetches only**. It shows
  **safe COUNTS and closed-vocab status only**. It is a pure inspection slice: it does **not** change
  guide generation, prompts, extraction behavior, OCR routing, rendering, exports, or any artifact
  schema, it makes **no** production include/omit decision, and it does **not** embed visuals. **Not**
  a Chandra integration slice.
- **No backend changes.** Reuses the existing exact-name artifact routes
  (`/api/jobs/{id}/artifacts/<name>`) via the existing `getJobArtifact` / `artifactUrl` client helpers.
  The three advisory artifacts remain **out of** `ARTIFACTS` / `EXPORT_ARTIFACTS` / `_artifact_urls` /
  `_artifact_details` — they are **not** added to any generic artifact list, export bundle, or existing
  artifact UI row; they are reached only by exact filename through this read-only panel.
- **New frontend files:**
  - `frontend/src/visualAdvisoryArtifacts.js` — pure, React-free, node-testable helpers. Exposes the
    exact artifact-name constants, `isArtifactMissing(error)` (404 ⇒ "not generated for this job"),
    `safeToken(value)` (strict `^[a-z0-9_]+$`, ≤48 chars, else `unavailable`), and
    `summarizeVisualManifest` / `summarizeVisualScoring` / `summarizeVisualReplacementPlan`. Each
    returns a **count-only** view model (`state`/`tone`/`label` + non-negative integer counts); it
    never mutates input, never throws, and never passes through captions, OCR/source text, provider
    payloads, image refs/bytes, data URIs, base64, paths, URLs, or tokens — even closed-vocab reasons
    go through `safeToken` first.
  - `frontend/src/components/VisualAdvisoryPanel.jsx` — read-only drawer panel. Independently fetches
    the three exact-name artifacts (one missing/malformed artifact never blocks the others), treats
    **404 as a calm "Not available"** (no scary error), shows compact tiles (manifest:
    candidates / pages-with-signals / extracted-figures; scoring: scored + high/medium/low/unknown
    priority counts; plan: item count + candidate-action counts), summarizes
    `chandra_blocked` presence as an **advisory/blocked** notice with no raw detail, and renders
    exact-name "Open … JSON" links (`artifactUrl(jobId, name)` — the only permitted URL). No raw JSON
    is shown inline.
- **Wiring:** `frontend/src/components/RecentJobsPanel.jsx` (the Job Details drawer) gains a
  `Visual Advisory` tab (`Images` icon) rendering `<VisualAdvisoryPanel jobId={…} />`. Small additive
  `.sg-artifact-link` style in `frontend/src/design-system.css`.
- **New test:** `frontend/scripts/verify-job-details-visual-advisory.mjs` (added to `npm run test` and
  as `npm run verify-job-details-visual-advisory`) — exact artifact names; 404⇒missing; `safeToken`
  allowlist (rejects paths/free-text/over-long/non-string); manifest/scoring/plan completed counts;
  priority + candidate-action counts; `chandra_blocked` present via item reason AND top-level warning,
  absent otherwise; skipped/malformed degrade safely with closed-vocab reasons; and a serialized
  no-leak sweep over every produced view model (no caption/OCR/path/URL/data-URI/base64/token).
- **Confirmations:** guide output, prompts, rendering, extraction, OCR routing, and artifact schemas
  are **unchanged**; the manifest / scoring / plan artifacts are **not mutated** (read-only fetch);
  candidate actions remain **advisory only**; no generic artifact-list / export-bundle / existing-row
  exposure was added; no model / llama-server / cloud / network call beyond normal app API artifact
  fetches; no image file read, no image bytes, no `clean.md` write. Chandra *extraction* integration
  remains **blocked** by Slice 45 `status:not_run` (`operator_input_not_supplied`).
- **Validation:** `compileall api pipeline test_scripts` OK; planner **186/0**; plan-artifact **68/0**;
  scoring-core **146/0**; scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0**
  (+2 skipped); chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness
  **96/0**; ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**;
  extraction-metadata **9/9**; offline eval scored 3 guides (no regression); frontend build green;
  `npm run test` green (incl. new visual-advisory harness); `git diff --check` clean. Full Docker
  rebuild/recreate + `/api/health` + `smoke_release.py` run (UI/artifact-inspection slice).
  **Status:** committed (`1ed94c9`) and fast-forward merged to `chrome-renderer-v1` (pushed).

---

## Slice 51 — Include **visual advisory JSON artifacts** in **export bundles** when present on `slice51-visual-advisory-export-bundle`.

- **Purpose:** make multi-job export bundles more complete and portable by bundling the three advisory
  visual **JSON diagnostics** — `visual_assets_manifest.json` (Slice 40), `visual_asset_scoring.json`
  (Slice 47), `visual_replacement_plan.json` (Slice 49) — **alongside** the requested exports **only
  when they exist** for a job. This is an export-bundle **inclusion** slice only.
- **What it includes:** **JSON diagnostics only.** It does **not** include cropped image files or image
  bytes; the per-job `assets/*.png` crops are never bundled. It makes **no** production include/omit
  decision and embeds **no** visuals.
- **Backend code path:** `api/server.py` → `export_bundle` (`POST /api/exports/bundle`). A new narrow
  constant `VISUAL_ADVISORY_EXPORT_ARTIFACTS = ("visual_assets_manifest.json",
  "visual_asset_scoring.json", "visual_replacement_plan.json")` drives a small ride-along loop after
  the existing selector loop: for each name present (`_artifact_path(...).exists()`), the file is added
  to the job's bundle folder. The advisory files are **not** user selectors and are **deliberately kept
  out of** `EXPORT_ARTIFACTS` / `EXPORT_ARTIFACT_ALIASES` / `ARTIFACTS`, so no export-UI artifact type
  and no generic artifact UI row is added, and `artifact_types` is unchanged.
- **Gate / partial / absent behavior:** ride-along advisory files do **not** count toward
  `total_included`, so they never by themselves satisfy the "at least one requested artifact" gate — a
  bundle whose requested artifacts are all absent still returns the same `404`. If only some advisory
  files exist, only those are bundled; if none exist, bundle behavior is exactly as before. An absent
  advisory file is skipped calmly, never an error, and never fails the whole export.
- **Bundle index (`manifest.json`):** each job entry gains a `visual_advisory_included` list of the
  **filenames** bundled (presence/safe-metadata only). No raw artifact JSON content is inlined into the
  index, logs, or terminal output.
- **Comment hygiene:** the now-inaccurate "never in export bundles" notes in
  `api/server.py:_artifact_path` and `pipeline/job_manager.py` (scoring/plan properties) were corrected
  to "bundled as a ride-along JSON diagnostic when present, without adding a generic UI row." The
  `assets_dir` (PNG) comment is unchanged — image bytes are still never exported.
- **No-leak:** advisory files are read **read-only** and never mutated; no image bytes / data URIs /
  base64 / paths / URLs / headers / tokens / socket paths / executable paths / model/mmproj paths / raw
  argv / private document text / raw OCR / raw provider payloads enter logs, docs, tests, or the safe
  bundle metadata.
- **New test:** `test_scripts/test_visual_advisory_export_bundle.py` — drives `export_bundle` against
  temp-dir Jobs (monkeypatched `_get_job`): all-three-present inclusion; partial set; none-present =
  unchanged; **no `.png` / `assets/` entries**; index `visual_advisory_included` carries filenames only
  with no raw body / leak; advisory-only job still `404`s for an absent requested artifact; export
  leaves all three artifacts **byte-identical**; the three names stay out of `ARTIFACTS` /
  `EXPORT_ARTIFACTS` / aliases / `_artifact_urls` / `_artifact_details` while exact-name routes still
  resolve. Skips automatically when FastAPI is unavailable in host Python (full coverage in Docker).
- **Confirmations:** generated guide output, prompts, rendering, extraction behavior, OCR routing, and
  artifact schemas are **unchanged**; visual artifacts are **not mutated** by export; candidate actions
  remain **advisory only**; **no** generic artifact UI rows / export-UI exposure added; no frontend
  change; no API route change (existing `/api/exports/bundle` only); no `clean.md` write; no model /
  llama-server / cloud / network call. Chandra *extraction* integration remains **blocked** by Slice 45
  `status:not_run` (`operator_input_not_supplied`).
- **Validation:** `compileall api pipeline test_scripts` OK; new export-bundle test (host: SKIP — no
  FastAPI; Docker: full); planner **186/0**; plan-artifact **68/0**; scoring-core **146/0**;
  scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0** (+2 skipped);
  chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness **96/0**;
  ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**;
  extraction-metadata **9/9**; offline eval scored 3 guides (no regression); frontend build green;
  `npm run test` green; advisory mjs green; `git diff --check` clean. Full Docker rebuild/recreate +
  `/api/health` + `smoke_release.py` (export-behavior slice).
  **Status:** NOT committed (awaiting operator review).

---

## Slice 49 — Persist `visual_replacement_plan.json` as an **advisory exact-name artifact** on `slice49-visual-replacement-plan-artifact`.

- **Purpose:** wire the Slice 48 replacement-planner core into the job artifact flow as the sibling
  artifact `visual_replacement_plan.json`, **derived from** the already-written
  `visual_asset_scoring.json` report (with the manifest passed only for a **presence-only** asset-id
  cross-check). Pure artifact writing/serving — it does **not** change guide output, prompts,
  extraction, OCR routing, visual embedding, include/omit decisions, UI, or export bundles, and is
  **not** a Chandra integration slice. This is a second-level advisory artifact: manifest (V1 source)
  → scoring (Slice 47 advisory) → replacement plan (Slice 49 advisory, derived from scoring).
- **Artifact:** exact name `visual_replacement_plan.json`, written as a sibling of the scoring report.
  Reachable **only by exact name** at `/api/jobs/{id}/artifacts/visual_replacement_plan.json`; absent
  → graceful 404 ("Artifact not found."), like the other exact-name advisory siblings.
- **Wiring (production):**
  - `pipeline/job_manager.py` — new `Job.visual_replacement_plan_json` property
    (`<job>/visual_replacement_plan.json`).
  - `api/server.py` — dedicated `_artifact_path` branch mapping the exact name → that path
    (`application/json`). Deliberately **NOT** added to `ARTIFACTS` / `EXPORT_ARTIFACTS` /
    `_artifact_urls` / `_artifact_details` → no generic artifact-list, export-bundle, or UI row.
  - `pipeline/visual_replacement_planner.py` — new degrade-not-fail writers
    `write_visual_replacement_plan_report(job, scoring_report, *, manifest=None)` and
    `write_skipped_visual_replacement_plan_report(job, *, reason=…, safe_message=…)`. Added stdlib
    imports `json` + `sys`; the writers take a duck-typed `job` and call only its `save_text` /
    `visual_replacement_plan_json` (no `job_manager` import). The pure planning core is unchanged.
  - `pipeline/run_llm_job.py` — after `write_visual_asset_scoring_report(...)`, calls
    `write_visual_replacement_plan_report(job, scoring_report, manifest=visual_manifest_obj)` reusing
    the already-read manifest object and the returned scoring report (no re-read).
- **Writer behavior:** when the scoring report is a `completed` report with a list of `scores`, builds
  the plan via `build_visual_replacement_plan(scoring_report, manifest=…)` and writes it
  (`json.dumps(..., indent=2, sort_keys=True)`). When scoring is skipped/unavailable, writes a safe
  **skipped** plan (`status:"skipped"`, closed `reason` + short `safe_message`, `items:[]`) for
  consistency with the Slice 47 posture. Any write failure degrades to a `write_failed` skipped plan.
  Never raises into job generation, never gates/fails the job, never touches job status / validation /
  `clean.md`. Closed skip reasons: `visual_scoring_unavailable`, `visual_manifest_unavailable`,
  `visual_replacement_planning_unavailable`, `write_failed`.
- **Report shape preserved (Slice 48):** `{version:1, kind:"visual_replacement_plan",
  status:"completed"|"skipped", source:"visual_asset_scoring.json", items, summary, warnings}`.
  Candidate actions remain **advisory only** (`candidate_include_as_figure` / `candidate_convert_to_table`
  / `candidate_summarize_as_text` / `review_only` / `unknown`) — no production include/omit/render/
  prompt decision is made, no visual is embedded.
- **No mutation / no leak:** `visual_assets_manifest.json` and `visual_asset_scoring.json` are read
  only and **never mutated** (manifest contributes presence only — no field echoed). The plan never
  carries `image_ref`/`caption`/`source_text`, image bytes, data URIs, base64, paths, URLs, headers,
  tokens, socket/model/mmproj/executable paths, raw argv, raw provider/OCR payloads, or private
  document text; reasons/warnings are closed vocabulary.
- **Chandra still blocked:** any `chandra_local` item is planned **only as advisory** and carries
  `chandra_blocked`; Chandra *extraction* integration remains gated by Slice 45 `status:not_run`
  (`operator_input_not_supplied`).
- **New test:** `test_scripts/test_visual_replacement_plan_artifact.py` (**68/0**, api.server section
  auto-skipped in host Python) — completed write shape + summary counts; one item per score; advisory
  actions only; chandra item blocked+advisory; no caption/image_ref/source/path/url/base64 leak; no
  `image_ref`/`caption` field on items; scoring report + manifest not mutated (in-memory + on-disk
  bytes); manifest→scoring→plan integration with `has_manifest_match`; skipped on unavailable scoring
  (none/empty/skipped/scores-not-list/non-dict); skipped on write failure (no raw exception, no file
  left); explicit skipped writer defaults + out-of-vocab reason coercion; malformed scoring plans
  safely; exact-name route maps + not in ARTIFACTS/EXPORT_ARTIFACTS/_artifact_urls/_artifact_details.
  Existing planner test updated (**186/0**) — import hygiene now allows `json`/`sys`.
- **Validation:** `compileall api pipeline test_scripts` OK; planner **186/0**; plan-artifact **68/0**;
  scoring-core **146/0**; scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0**
  (+2 skipped); chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness
  **96/0**; ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**;
  extraction-metadata **9/9**; offline eval scored 3 guides (no regression); frontend build + test
  green; `git diff --check` clean. Full Docker rebuild/recreate + `/api/health` + `smoke_release.py`
  required (touches `api/server.py` + `job_manager.py` + `run_llm_job.py`). **Status:** NOT committed
  (awaiting operator review).

---

## Slice 48 — Visual **replacement planner core** (pure, unwired; roadmap V3) on `slice48-visual-replacement-planner-core`.

- **Purpose:** add a pure, deterministic **replacement planner core** — the next V3
  step after candidate scoring (`docs/VISION_ROADMAP.md` §8). It consumes an
  already-sanitized `visual_asset_scoring.json`-shaped scoring report (and, optionally, a
  `visual_assets_manifest.json`-shaped manifest for a **presence-only** cross-check) and returns a
  **separate advisory replacement plan** — a per-asset `candidate_action` / `placement` / `priority`
  with closed-vocab `reasons`. It does **not** mutate the scoring report or manifest, persist an
  artifact, embed visuals, change extraction/guides/rendering, or wire into production. **Not** a
  Chandra integration slice.
- **New module:** `pipeline/visual_replacement_planner.py` (stdlib-only: `re`, `typing`; imports
  nothing from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/job-manager/
  extraction/run-job/`visual_asset_scoring`/`visual_assets_manifest`). Public API (small, pure, total):
  - `plan_visual_replacement_candidate(score, *, asset=None) -> dict`
  - `plan_visual_replacement_candidates(scores, *, assets_by_id=None) -> list[dict]`
  - `build_visual_replacement_plan(scoring_report, *, manifest=None) -> dict`
- **Plan report shape:** `{version:1, kind:"visual_replacement_plan", status:"completed",
  source:"visual_asset_scoring.json", items:[…], summary:{item_count,
  candidate_include_as_figure_count, candidate_convert_to_table_count,
  candidate_summarize_as_text_count, review_only_count, unknown_count}, warnings:[…]}`. Each item:
  `{asset_id, source_page, source_provider, asset_type, priority, candidate_action, placement,
  reasons:[…], warnings:[…]}`.
- **Closed vocab only:** `candidate_action` ∈ {candidate_include_as_figure, candidate_convert_to_table,
  candidate_summarize_as_text, review_only, unknown}; `placement` ∈ {source_page_reference, unknown};
  `priority` ∈ {high, medium, low, unknown}; `source_provider` ∈ {fitz_local, chandra_local,
  mistral_ocr, unknown}; `asset_type` ∈ {page_visual_signal, extracted_figure, table, table_region,
  equation_block, diagram, figure, image_region, cropped_region, unknown_region, unknown}; closed
  `reasons` (score_high/medium/low, asset_type_diagram/figure/table/equation/page_signal,
  has_manifest_match, missing_manifest_match, review_required, chandra_blocked, low_information_signal,
  unknown_asset_type, input_sanitized); closed `warnings` (scoring_report_malformed,
  score_item_malformed, asset_lookup_missing, asset_id_missing/invalid, asset_type_unrecognized,
  source_provider_unrecognized, priority_unrecognized, candidate_action_unresolved, input_unrecognized).
- **Planning rules (advisory, conservative):** high/medium visual figure types (diagram, figure,
  image_region, cropped_region, extracted_figure) → `candidate_include_as_figure`; high/medium
  table/table_region → `candidate_convert_to_table`; high/medium equation_block (or a *legitimately*
  unknown visual block) → `candidate_summarize_as_text`; low priority / bare page signal →
  `review_only`; malformed/unknown-priority → `unknown`. A recognized-but-unmapped or
  coerced-unrecognized type at actionable priority falls back to `review_only` +
  `candidate_action_unresolved` (never guesses an embedding). `placement` is `source_page_reference`
  only for an actionable candidate with a known source page, else `unknown`.
- **Chandra still blocked:** any `chandra_local` item is planned **only as advisory** and always
  carries the closed reason `chandra_blocked`, because Chandra *extraction* integration remains gated
  by Slice 45 `status:not_run` (`operator_input_not_supplied`). This core reads only the asset
  *shape*; it integrates nothing.
- **Pure / unwired / no production change:** not imported by `run_llm_job.py` or anything else; no
  artifact written (no `visual_replacement_plan.json` this slice); no API route; no frontend/UI; no
  export-bundle/generic artifact-list exposure; `visual_assets_manifest.json` /
  `visual_asset_scoring.json` schemas unchanged and **never mutated**; no extraction/OCR-routing/
  prompt/render/guide-output change; no `clean.md` write; no model/llama-server/cloud/network call; no
  image files/bytes. Captions/source text/provider payloads are never read into output; a manifest
  cross-check contributes **presence only** (no manifest field echoed).
- **New test:** `test_scripts/test_visual_replacement_planner.py` (**186/0**) — include_as_figure for
  all high-priority visual types; medium/high table→convert; high/medium equation (and legit-unknown
  block)→summarize; low/page-signal→review_only; malformed score item→safe `unknown` fallback;
  malformed scoring report→safe completed report with `scoring_report_malformed`; manifest
  presence-match without field leak; missing match→`missing_manifest_match`+`asset_lookup_missing`;
  chandra_local→`chandra_blocked` + still advisory; no mutation of report/manifest; smuggled
  secrets/paths/base64/data-URIs/argv never leak; invalid asset ids→deterministic slug-safe fallback;
  summary counts; determinism; no forbidden imports.
- **Validation:** `compileall api pipeline test_scripts` OK; planner **186/0**; scoring-core **146/0**;
  scoring-artifact **58/0**; manifest **65/0**; figure-extraction **50/0** (+2 skipped);
  chandra-normalizer **68/0**; chandra-local-provider **68/0**; chandra-live-harness **96/0**;
  ocr-modes **121/121**; ocr-routing-policy **120/120**; ocr-routing-integration **56/56**; offline
  eval scored 3 guides (no regression); frontend build + test green; `git diff --check` clean.
  `smoke_release.py` / Docker **not required** (pure/unwired — no server/extraction/render/artifact
  behavior touched). **Status:** committed (`967748a`) and fast-forward-merged to
  `chrome-renderer-v1`; pushed.

---

## Slice 47 — Persist `visual_asset_scoring.json` as an **advisory exact-name artifact** on `slice47-visual-asset-scoring-artifact`.

- **Purpose:** persist the Slice 46 scoring report as the sibling artifact
  `visual_asset_scoring.json`, **derived from** the already-written `visual_assets_manifest.json`.
  Pure artifact writing/serving — it does **not** change guide output, prompts, extraction, OCR
  routing, visual embedding, include/omit decisions, UI, or export bundles, and is **not** a Chandra
  integration slice.
- **Artifact:** exact name `visual_asset_scoring.json`, written as a sibling of the manifest.
  Reachable **only by exact name** at `/api/jobs/{id}/artifacts/visual_asset_scoring.json`; absent →
  graceful 404 ("Artifact not found."), like the other exact-name advisory siblings.
- **Wiring (production):**
  - `pipeline/job_manager.py` — new `Job.visual_asset_scoring_json` property (`<job>/visual_asset_scoring.json`).
  - `api/server.py` — dedicated `_artifact_path` branch mapping the exact name → that path
    (`application/json`). **Deliberately NOT** added to `ARTIFACTS`, `EXPORT_ARTIFACTS`,
    `_artifact_urls`, `_artifact_details`, export bundles, or any UI row.
  - `pipeline/run_llm_job.py` — in `_attach_sources`, immediately after
    `write_visual_assets_manifest(...)`, calls
    `write_visual_asset_scoring_report(job, _read_visual_manifest_for_scoring(job))`. The helper
    reads the just-written manifest back off disk and returns `None` on any read/parse error
    (total, never raises, never mutates). Written **exactly when** the manifest is written; non-PDF /
    no-extraction jobs omit **both** artifacts (no call).
  - `pipeline/visual_asset_scoring.py` — thin degrade-not-fail writer
    `write_visual_asset_scoring_report(job, manifest)` (+ `write_skipped_visual_asset_scoring_report`,
    `_is_scorable_manifest`, `_skipped_report`); stable JSON (`indent=2, sort_keys=True`). Closed
    skip reasons only: `visual_manifest_unavailable`, `visual_scoring_unavailable`, `write_failed`.
    `safe_message` is a fixed constant; stderr (if reached) carries an **exception class name only**.
    The Slice 46 `score_visual_assets_manifest(...)` report shape is unchanged.
- **Degrade-not-fail / no mutation:** the writer never raises into job generation, never gates/fails
  the job, never touches job status / validation / `clean.md`, and **never mutates**
  `visual_assets_manifest.json`. A non-scorable/unavailable manifest → `skipped`
  (`visual_manifest_unavailable`); a write error → `skipped` (`write_failed`).
- **`recommended_action` stays `unknown`** for every score (no include/omit decision); no model /
  `llama-server` / Chandra / Mistral / Gemini / network / image-file access; no `clean.md` write.
- **Chandra still blocked:** Chandra **extraction** integration remains gated by Slice 45
  `status:not_run` (`operator_input_not_supplied`); this slice only persists a report derived from
  whatever manifest the existing `fitz_local` path produced — it integrates nothing.
- **New test:** `test_scripts/test_visual_asset_scoring_artifact.py` (**58/0**; api.server endpoint
  section auto-skips when FastAPI is absent in host Python — covered in Docker) — completed write +
  shape/summary counts; `recommended_action` all `unknown`; no caption/image_ref/path/url/base64
  leak in artifact bytes; manifest file+dict unmutated; manifest→read-back→score integration;
  skipped on unavailable/malformed manifest (5 cases); write-failure degrades to `write_failed`
  (via a `save_text`-raising `Job` subclass; no raw exception text in the report); explicit-skipped
  defaults + out-of-vocab reason coerced; exact-name route resolves & not in
  `ARTIFACTS`/`EXPORT_ARTIFACTS`/`_artifact_urls`/`_artifact_details`. Also updated
  `test_scripts/test_visual_asset_scoring.py` to allow stdlib `json`/`sys` (now **146/0**).
- **Validation:** `compileall api pipeline test_scripts` OK; scoring-core **146/0**; scoring-artifact
  **58/0**; manifest **65/0**; figure-extraction **50/0** (+2 skipped); chandra-normalizer **68/0**;
  chandra-local-provider **68/0**; chandra-live-harness **96/0**; ocr-modes **121/121**;
  ocr-routing-policy **120/120**; ocr-routing-integration **56/56**; extraction-metadata **9/9**;
  offline eval scored 3 guides (no regression); frontend build + test green; fresh Docker
  build + `/api/health` ok + `smoke_release.py`; `git diff --check` clean. **Status:** NOT committed
  (awaiting operator review).

---

## Slice 46 — Visual asset **scoring core** (pure, unwired; roadmap V3) on `slice46-visual-asset-scoring-core`.

- **Purpose:** add a pure, deterministic **scoring core** for visual asset candidates — the V3
  "candidate scoring" step from `docs/VISION_ROADMAP.md` §8, sitting between the advisory manifest
  (V1) and any future guide-inclusion decision (V4+). It scores existing
  `visual_assets_manifest.json`-shaped assets and returns a **separate advisory scoring report**;
  it does **not** mutate the manifest, change guides/rendering, embed visuals, or wire into
  production. **Not** a Chandra integration slice.
- **New module:** `pipeline/visual_asset_scoring.py` (stdlib-only: `re`, `typing`; imports nothing
  from `fitz`/Tesseract/llama.cpp/Chandra/Mistral/Gemini/LMM/renderers/server/job-manager/
  extraction). Public API (small, pure, total):
  - `score_visual_asset_candidate(asset, *, page_context=None) -> dict`
  - `score_visual_asset_candidates(assets, *, page_context_by_page=None) -> list[dict]`
  - `score_visual_assets_manifest(manifest, *, page_context_by_page=None) -> dict`
- **Report shape:** `{version:1, kind:"visual_asset_scoring", status:"completed",
  source:"visual_assets_manifest.json", scores:[…], summary:{asset_count, high/medium/low/
  unknown_priority_count}, warnings:[…]}`. Each score:
  `{asset_id, source_page, source_provider, asset_type, recommended_action:"unknown", priority,
  include_score, reasons:[…], warnings:[…]}`.
- **Closed vocab only:** `priority` ∈ {high, medium, low, unknown}; `recommended_action` stays
  **`unknown` for every score** this slice; `source_provider` ∈ {fitz_local, chandra_local,
  mistral_ocr, unknown}; `asset_type` ∈ {page_visual_signal, extracted_figure, table, table_region,
  equation_block, diagram, figure, image_region, cropped_region, unknown_region, unknown};
  closed `reasons` tokens (asset_type_table/diagram/equation/extracted_figure, has_bbox,
  has_caption, large_region, page_has_images, page_has_drawings, provider_*, low_information_signal,
  unknown_asset_type, input_sanitized); closed `warnings` tokens (asset_id_missing/invalid,
  source_page_invalid, asset_type_unrecognized, source_provider_unrecognized, bbox_invalid,
  signals_invalid, manifest_malformed, input_unrecognized).
- **Behavior:** pure/deterministic/total — never raises, never mutates input, no clock/random/
  network/file/image access. Invalid/missing asset ids → deterministic slug-safe fallback
  (`asset_0001`); source page coerced to a positive int or `None`; bbox parsed only as 4 finite
  ordered numbers; **captions used only as a boolean `has_caption` signal and never emitted**;
  unknown/malformed assets score `unknown`/`low` with closed warnings. Heuristics keep
  tables/diagrams/equations/extracted-figures above a bare `page_visual_signal`; strong page
  signals lift a page signal at most low→medium (conservative).
- **Unwired / no production change:** not imported by `pipeline/run_llm_job.py` or anything else;
  no artifact written; `pipeline/visual_assets_manifest.py` unchanged (no schema change); no
  extraction/OCR-routing change; no Chandra provider/harness change; no model/llama-server/cloud
  calls; no API route; no frontend/UI; no Provider Settings/LMM change; no prompt/render/export
  change; no `clean.md` write; no image files/bytes.
- **Chandra still blocked:** Chandra **extraction** integration remains gated by Slice 45
  `status:not_run` (`operator_input_not_supplied`) until a live harness pass is recorded. This
  slice only *reads the asset shape* the Slice 42 normalizer would emit; it integrates nothing.
- **New test:** `test_scripts/test_visual_asset_scoring.py` (**146/0**) — minimal page_visual_signal;
  extracted_figure with bbox+large-region; Chandra diagram/table/equation_block shapes; deterministic
  priority ordering; action-always-unknown; bbox invalid → `bbox_invalid`; id missing/unsafe →
  safe fallback; malformed/non-dict manifest+assets safe; no input mutation; no raw caption emitted;
  smuggled path/URL/token/header/base64/data-URI/argv/socket/gguf/mmproj strings never appear;
  source_page coercion; no forbidden imports.
- **Validation:** `compileall api pipeline test_scripts` OK; scoring **146/0**; manifest **65/0**;
  figure-extraction **50/0** (+2 skipped); chandra-normalizer **68/0**; chandra-local-provider
  **68/0**; chandra-live-harness **96/0**; ocr-modes **121/121**; ocr-routing-policy **120/120**;
  ocr-routing-integration **56/56**; offline eval scored 3 guides (no regression); frontend
  build OK + frontend test green; `git diff --check` clean. `smoke_release.py` **not required** —
  no production-wired/server/extraction/render/artifact behavior is touched (pure unwired module).
- **Status: NOT committed** (awaiting operator review).

---

## Slice 45 — Chandra live-harness validation report + operator runbook (DOCS-ONLY) — committed `591d664`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.

- **Purpose:** a **docs-only gate/report** slice that records (a) **how to safely run** the
  Slice 44 Chandra live validation harness and (b) a **sanitized** live validation result if an
  operator has a local Chandra-capable `llama-server` available. **Not** an integration slice —
  no code/test/app behavior changes.
- **New doc:** `docs/CHANDRA_LIVE_HARNESS_VALIDATION.md` (§1 purpose · §2 operator-owned
  preconditions · §3 placeholder-only run command template · §4 safe-output policy · §5
  recordable summary fields + this slice's result · §6 gate decision · §7 future-slice notes).
  - **Run template uses placeholders only** (`--endpoint "<local-openai-compatible-endpoint>"`,
    `--image "<non-private-test-image>"`) — no real path/endpoint/port/token/socket/model/mmproj/
    executable recorded.
  - **Safe-output policy:** record only closed-vocabulary summary fields (`reachable`,
    `request_ok`, `parse_status`, `normalized_kind`, `normalized_status`, `source_text_char_count`,
    `asset_count`, closed-vocab `parse_warnings`/`normalize_warnings`, `failure_category`,
    `elapsed_ms` if safe). Never raw OCR text, raw provider response, image path/basename/bytes,
    base64/data URI, full URL/query, headers/tokens, or model/mmproj/exec/socket paths.
- **Recorded validation result this slice:** `status: not_run`, reason `operator_input_not_supplied`.
  No live Chandra `llama-server` endpoint and no non-private test image were supplied during this
  docs-only slice, so **no live HTTP request was made** and **no result was fabricated**. The
  Slice 44 harness remains proven only by its fake-transport suite (`test_chandra_live_harness`
  **96/0**).
- **Gate decision:** current state is `not_run` ⇒ the **disabled extraction-side adapter slice
  stays blocked** until a live run passes. A pass ⇒ proceed to a still-**disabled**, off-by-default
  extraction-side adapter (Tesseract/`fitz` fallback, degrade-not-fail); a fail/`not_run` ⇒ fix the
  harness/provider boundary or rerun first.
- **Scope (docs-only):** no code, no tests, no app integration, no extraction wiring, no
  `ocr_routing`/`extraction_metadata.json`/`visual_assets_manifest.json` change, no API route, no
  frontend/UI, no Provider Settings, no Local Model Manager, no render/export/artifact change, no
  `clean.md` write, no `llama-server` management, no subprocess/Docker, no model/mmproj/quant file,
  no raw OCR/provider output committed.
- **Validation:** `git diff --check` clean; `git diff --name-only` docs-only (new
  `docs/CHANDRA_LIVE_HARNESS_VALIDATION.md` + `CURRENT_TASK.md` + `NEXT_CHAT_HANDOFF.md` +
  `DECISIONS.md`). No build/smoke required — no code touched.
- **Status: committed `591d664`, fast-forward merged + pushed to trunk `chrome-renderer-v1`.**

---

## Slice 44 — Chandra local provider **live validation harness** (manual / opt-in only) — committed `8468c16`, merged + pushed to trunk `chrome-renderer-v1`.

- **Purpose:** add a **manual, opt-in** live validation harness so an operator can prove —
  *outside production app flow* — that a local Chandra-capable `llama-server` **they started
  themselves** can accept one page image and return output that flows cleanly through the
  Slice 43 boundary: operator's local server response →
  `parse_chandra_chat_response(...)` → `normalize_chandra_chat_response(...)` →
  Slice 42 normalizer output → **safe closed-vocabulary summary only**. Harness slice only.
- **Manual / opt-in:** a real HTTP request happens **only** when the operator runs the CLI with
  their own `--endpoint` and `--image`. **Not** part of release smoke. Importing the module
  triggers **no** network / file read / model call / subprocess / Docker / server check.
- **What it does NOT do (unchanged production behavior):** does **not** wire Chandra into
  `pipeline/extract.py`, OCR routing, `ocr_routing`, `extraction_metadata.json`, or the
  `visual_assets_manifest.json` schema; writes no `clean.md`; adds **no** API route, frontend/UI,
  Provider Settings, or Local Model Manager change; touches no renderers/exports/artifacts or
  study-guide prompt assembly; starts/stops/manages **no** `llama-server`; uses **no** subprocess,
  shell, or Docker call; downloads **no** model; commits **no** model/mmproj/quant file, raw OCR
  dump, screenshot, or image fixture (tests use tiny synthetic bytes in a temp file).
- **Script:** new **`test_scripts/validate_chandra_local_provider_live.py`** — stdlib transport
  (`urllib`) used **only** when the operator runs it; tests inject a fake transport. Shape:
  - `run_validation(endpoint, image_path, *, transport=None, timeout_seconds=60.0, prompt=None) -> dict`
    — **total/leak-safe**: builds the request via the Slice 43
    `build_chandra_image_message_payload(...)`, sends it (injected/real transport), parses +
    normalizes, and returns a closed-vocabulary summary. Every failure path resolves to a closed
    `failure_category`; nothing raises to the caller.
  - `redact_endpoint_for_display(endpoint) -> str` — keeps only scheme+host, masks the port
    (`<port>`), drops path/query and any `user:token@` userinfo; non-http(s)/unparseable →
    `"local_endpoint_supplied"`.
  - `safe_summary_from_normalized(normalized, parse_warnings=None) -> dict` — projects the Slice 42
    output to counts + filtered closed-vocab warnings (source text reported only as a **char
    count**, never echoed).
  - `http_transport(url, payload, timeout) -> response` — stdlib `urllib` POST, **no auth header**;
    maps connection/HTTP/decoding errors to `connection_failed` / `request_failed` /
    `response_malformed` carrying **only** the category.
  - `print_safe_summary(summary, *, verbose=False)` — prints a **whitelisted** key set as JSON.
- **Safe summary fields (closed vocabulary):** `reachable`, `request_ok`, `image_supplied`,
  `endpoint_display` (redacted), `parse_status` (`none`/`ok`/`empty`/`malformed`), `normalized_kind`,
  `normalized_status`, `source_text_char_count`, `asset_count`, `parse_warnings`,
  `normalize_warnings`, `failure_category` (`connection_failed` / `request_failed` /
  `response_malformed` / `provider_empty_content` / `normalization_failed` / `image_read_failed` /
  `invalid_endpoint`), and `elapsed_ms` (verbose only). **Never** prints/returns raw OCR text, the
  raw provider payload, the image path, image bytes, a base64/data URI, a full URL, query strings,
  headers, `Authorization`/`Bearer` fragments, raw argv, or model/mmproj/executable/socket paths.
- **Tests:** new **`test_scripts/test_chandra_live_harness.py`** — **96/0**, fake transport only,
  no live server: success parse+normalize; safe-summary counts/tokens only + no raw OCR text;
  malformed-shape and `response_malformed`/`connection_failed`/`request_failed` categories
  (no traceback/secret echo); endpoint redaction of query/token/userinfo/Bearer/path-token →
  `http://<host>:<port>/...`; image path/basename not echoed; base64 data URI in the *request* but
  never in the summary/print; raw malicious payload (URL/path/auth/key/socket/argv/gguf/`<script>`)
  never leaked; request built via the Slice 43 payload builder; `provider_empty_content` and
  `image_read_failed` categories; real `http_transport` never invoked; no forbidden imports.
- **Validation (all green):** `npm --prefix frontend run build` + `run test`;
  `python -m compileall api pipeline test_scripts`; `test_chandra_local_provider` 68/0;
  `test_chandra_live_harness` 96/0; `test_chandra_normalizer` 68/0; `test_visual_assets_manifest`
  65/0; `test_local_figure_extraction` 50/0/2; `test_ocr_provider` 18/18; `test_ocr_routing_policy`
  120/120; `test_ocr_routing_integration` 56/56; `test_ocr_modes` 121/121; `test_extraction_metadata`
  9/9; `test_pdf_visual_signals` 44/44; `test_pdf_page_classification` 56/56; `test_math_verifier`
  74/74; `test_guide_lint` 74/74; `test_eval_harness` 64/64; `test_page_anchor_reachability` 21/21;
  `test_source_page_citations` 19/19; `test_ask_retrieval_relevance` 12/0; `test_ask_lexical_hygiene`
  34/0; `test_guide_lint_artifact` 26/26; `eval/run_eval.py --offline --all` (3 guides, no
  regression); `git diff --check` clean. `smoke_release.py` **not** required — no
  server/extraction/render/artifact/UI behavior is touched (manual-harness-only).
- **Files:** new `test_scripts/validate_chandra_local_provider_live.py`, new
  `test_scripts/test_chandra_live_harness.py`, docs (`CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`,
  `DECISIONS.md`). **Status: committed `8468c16`, fast-forward merged + pushed to trunk
  `chrome-renderer-v1`.**
- **Next (deferred, separate slice):** only after this harness proves stable on real hardware,
  decide whether to add a **disabled** extraction-side adapter (still off-by-default, with
  Tesseract/`fitz` fallback and degrade-not-fail) — no extraction wiring before then.

---

## Slice 43 — Chandra local provider/client skeleton (committed `2bc14ef`, merged to trunk; DISABLED / UNWIRED).

- **Purpose:** add a small, **disabled/unwired** Chandra local provider/client skeleton
  that names the third boundary in the Chandra chain and makes it testable —
  **without running any model**:
  page image bytes → **OpenAI-compatible `llama-server` request shape** →
  (a future integration runs the model) → raw Chandra output string →
  **Slice 42 normalizer** → safe normalized output. **Foundation slice only**, not a
  provider integration: nothing in a production path constructs or calls it.
- **What it does NOT do:** does not run Chandra / `llama-server`; opens no socket; makes
  no real model/server/network call (tests use injected fake responses only); does not
  download or open any model / mmproj / quant file; does not wire into
  `pipeline/extract.py` or OCR routing; does not change `ocr_routing`,
  `extraction_metadata.json`, or the `visual_assets_manifest.json` schema; writes no
  `clean.md`; embeds no visuals; adds no API route, frontend toggle, Provider Settings,
  or Local Model Manager change; does not touch prompts/render/exports or any generated
  guide. `ChandraLocalProvider.enabled is False` by construction.
- **Module:** new **`pipeline/chandra_local_provider.py`** — stdlib-only (`base64`,
  `typing`) + the Slice 42 normalizer; **no new dependency**, **no import** of
  `fitz`/Tesseract/llama.cpp/`openai`/Mistral/Gemini/Chandra-runtime/LMM/`socket`/
  `subprocess`/HTTP client. Public API:
  - `build_chandra_image_message_payload(image_bytes, *, mime_type="image/png", prompt=None) -> dict`
    — OpenAI-compatible multimodal chat payload (`messages=[{role:"user", content:[text, image_url]}]`,
    conservative `temperature=0.0` + `max_tokens`); image → base64 data URI **only here**;
    no model id / base URL / host path / argv embedded. Non-bytes input raises `TypeError`
    (developer-misuse guard) without echoing the value; unknown/hostile `mime_type` collapses to PNG.
  - `parse_chandra_chat_response(response) -> {"content": str, "warnings": [...]}` — accepts the
    `{"choices":[{"message":{"content":...}}]}` dict shape and SDK-object equivalents; **total**
    (never raises), degrades to closed-vocab warnings (`empty_response`/`no_choices`/`no_message`/
    `no_content`/`malformed_response`), and **never echoes the raw provider payload**.
  - `normalize_chandra_chat_response(response, *, source_page=1) -> dict` — bridges parse →
    `normalize_chandra_output(...)`; returns the Slice 42 `kind:"chandra_normalized_output"`
    envelope (all leak-scrubbing delegated to the normalizer); empty/malformed → valid
    `completed` output with `empty_output`.
  - `class ChandraLocalProvider` (`provider_id="chandra_local"`, `enabled=False`,
    `is_enabled() -> False`) — thin handle delegating to the module functions.
- **Default OCR/layout prompt:** `CHANDRA_OCR_LAYOUT_PROMPT` constant requests layout HTML with
  `data-label` + `data-bbox`, HTML tables, LaTeX math, and captioned diagrams/figures. It is a
  fixed template constant, **not** wired into guide generation.
- **Tests:** new **`test_scripts/test_chandra_local_provider.py`** — **68/0** (payload shape +
  no model/path/argv leak; prompt requests `data-label`/`data-bbox`/tables/LaTeX/captions; image
  data URI only in the request, not in parsed/normalized output; mime whitelist; non-bytes
  rejected w/o echo; parse normal/object/degrade/no-echo; normalizer bridge incl. empty + malicious
  scrub; provider disabled/unwired; no-forbidden-imports). Injected fake responses only — no real
  Chandra dump, model file, or local path.
- **Validation (all green):** `python -m compileall api pipeline test_scripts`;
  `test_chandra_normalizer` 68/0; `test_chandra_local_provider` 68/0; `test_visual_assets_manifest`
  65/0 (manifest unchanged); `test_local_figure_extraction` 50/0/2-skip; `test_ocr_provider` 18/18;
  `test_ocr_routing_policy` 120/120; `test_ocr_routing_integration` 56/56; `eval/run_eval.py
  --offline --all` (3 guides, no regression, delta 0.0); frontend `build` + `test` green;
  `git diff --check` clean. `smoke_release.py` not required — no server/extraction/render/artifact
  behavior is touched (no production wiring).
- **Files:** new `pipeline/chandra_local_provider.py`, new `test_scripts/test_chandra_local_provider.py`,
  this log, `NEXT_CHAT_HANDOFF.md`, `DECISIONS.md`. **No app integration, no manifest schema change,
  no extraction/OCR/prompt/render/UI/export change.** **Do not commit until the operator says so.**
- **Next (design, not built):** a `chandra_local` integration slice that flips `enabled` behind an
  explicit, **off-by-default** local OCR route on the LMM `llama-server` path — running the model,
  handing its raw string to this bridge, with **Tesseract/`fitz` fallback and degrade-not-fail**
  behavior; then candidate scoring/`recommended_action` and asset-aware prompt/render embed.

---

## Slice 42 — Chandra output normalizer core (committed `6e7f55f`, merged + pushed to trunk `chrome-renderer-v1`).

- **Purpose:** add a **pure, deterministic Chandra output normalizer** that turns a
  *raw Chandra layout string* (the `data-bbox` + `data-label` HTML-ish output Slice 41
  confirmed) into two GuideForge-shaped products — a safe **`source_text`** fragment
  and **`visual_assets_manifest.json`-shaped asset candidates** — **without running
  Chandra, `llama-server`, or any model.** Normalization-core slice, **not** provider
  integration. Off the wire entirely; nothing is wired into extraction.
- **What it does NOT do:** does not call Chandra / `llama-server`; does not download or
  open any model / mmproj / quant file; does not wire Chandra into extraction or OCR
  routing; does not write `clean.md` or any image bytes; does not score candidates
  (`recommended_action` stays `"unknown"`, `asset_ref` stays `null`); does not change
  the `visual_assets_manifest.json` schema, prompts, render, exports, UI, or any
  generated guide.
- **Module:** new **`pipeline/chandra_normalizer.py`** — pure stdlib (`re`,
  `html.parser.HTMLParser`, `typing`), **no new dependency**, **no import** of
  `fitz`/Tesseract/llama.cpp/Mistral/Gemini/Chandra-runtime/LMM. Public API:
  - `normalize_chandra_output(raw_output, *, source_page=1) -> dict` (total; never raises)
  - `extract_chandra_blocks(raw_output) -> list[dict]`
  - `chandra_blocks_to_source_text(blocks) -> str`
  - `chandra_blocks_to_manifest_assets(blocks, *, source_page) -> list[dict]`
- **Output shape:** `{version:1, kind:"chandra_normalized_output", status:"completed",
  source_provider:"chandra_local", source_text, assets[], warnings[]}`. Each asset
  mirrors the Slice 38/40 manifest asset (`asset_id` `page_<NNNN>_chandra_<II>`,
  `source_page`, `asset_type`, `bbox`, `caption`, `source_provider:"chandra_local"`,
  `recommended_action:"unknown"`, `dedupe_group:null`, `scores:{}`, **`asset_ref:null`**,
  `signals.chandra_label`, `warnings[]`).
- **Asset mapping (closed vocab):** `Table→table`, `Equation/Formula/Math→equation_block`,
  `Diagram/Chart/Graph→diagram`, `Figure→figure`, `Image/Picture→image_region`,
  unrecognized label → `unknown_region` (+ `label_unrecognized`). **Text/caption blocks
  are NOT emitted as visual assets** (they feed `source_text` only).
- **`source_text` behavior:** deterministic; headers → Markdown `#`/`##`, tables → simple
  Markdown grid, equations → preserved LaTeX/text, visual-region captions → plain line;
  no raw HTML/script/style, image bytes/base64, paths, URLs, or secrets.
- **Bbox behavior:** parses 4 finite, well-ordered floats from `data-bbox` → `[x0,y0,x1,y1]`;
  missing → `null` + `bbox_missing` (visual regions), unparseable/ill-ordered → `null` +
  `bbox_invalid`. Raw bbox strings are never echoed.
- **Safety / no-leak:** every captured/raw string is scrubbed field-by-field — strips
  URLs, abs/UNC/Windows paths, `.sock`, `Authorization`/`Bearer`, `sk-`/`pk-`-style keys,
  `--flag` argv, `data:…;base64`/long base64 runs, `<script>`/`<style>`, residual tags,
  control chars. Output is JSON-safe and uses closed-vocab warnings only.
- **Tests:** new **`test_scripts/test_chandra_normalizer.py`** — **68/0** (envelope +
  determinism, table/equation/diagram+caption, invalid/missing bbox, unrecognized label,
  plain-text/markdown fallback, never-raises on malformed + non-string, smuggled-secret
  no-leak sweep, multi-region ids/ordering, helper functions, no-forbidden-imports).
  Tiny **handcrafted synthetic** fixtures only — no real Chandra dump / private doc /
  screenshot / local path.
- **Validation (all green):** `python -m compileall api pipeline test_scripts`;
  `git diff --check`; the full focused battery incl. `test_visual_assets_manifest`
  (manifest unchanged) and `test_local_figure_extraction`; `test_chandra_normalizer`
  68/0; `eval/run_eval.py --offline --all` (3 guides, no regression); frontend `build` +
  `test` green; `smoke_release.py` **29/0/0**.
- **Files:** new `pipeline/chandra_normalizer.py`, new `test_scripts/test_chandra_normalizer.py`,
  this log, `NEXT_CHAT_HANDOFF.md`, `DECISIONS.md`. **No app integration, no manifest
  schema change, no extraction/OCR/prompt/render/UI/export change.** **Do not commit until
  the operator says so.**
- **Next (design, not built):** a `chandra_local` provider/integration slice that actually
  runs the model on the LMM `llama-server` path and feeds this normalizer; candidate
  scoring/`recommended_action`; asset-aware prompt/render embed.

---

## Slice 41 — Chandra GGUF hands-on spike (committed `218de18`, merged + pushed to trunk `chrome-renderer-v1`; docs-only).

- **Purpose:** the **hands-on** follow-up to Slice 39's docs-only Chandra gate —
  actually download, convert, and **run Chandra OCR 2 as GGUF through the existing
  `llama.cpp`/`llama-server` path** to decide whether it can produce useful
  OCR/document-extraction for GuideForge. **Spike/report only — no app integration.**
  Full write-up: **`docs/CHANDRA_GGUF_SPIKE_REPORT.md`**.
- **Verdict: PROCEED TO PROVIDER DESIGN** (strong pass), gated behind the LMM /
  `llama-server` path + a small mmproj build step + an output-normalisation slice.
- **What ran (on RTX 5070 Ti 16 GB, `llama.cpp` build 9307 / `549b9d8`, CUDA):**
  - Confirmed arch support: `libllama` has `qwen35`(text)+`qwen3vl`(vision) loaders;
    convert tooling's `MMPROJ_MODEL_MAP` routes `Qwen3_5ForConditionalGeneration →
    qwen3vl`, so this build **can export a Chandra mmproj**.
  - **Key blocker found + solved:** the only public GGUF
    (`hyojk2001/chandra-ocr-2-Q4_K_M-GGUF`) is **text-only, NO mmproj** (gguf-my-repo)
    → can't OCR as-is. Generated **mmproj-chandra-f16.gguf (~676 MB)** + text quants
    **Q4_K_M/Q5_K_M/Q8_0** from the **official** `datalab-to/chandra-ocr-2` (~10.6 GB)
    with build-9307 convert tooling.
  - **Load:** success on both `llama-mtmd-cli` and `llama-server` (`-ngl 99`,
    `--mmproj`, `-c 8192`).
  - **Image input:** works via CLI **and** the **OpenAI-compatible**
    `llama-server /v1/chat/completions` `image_url` data-URI path (the LMM-style path).
  - **Quality (3 synthetic, non-private, hand-checked pages):** near-perfect.
    Native output is **layout-HTML with `data-bbox` + `data-label`**
    (Section-Header/Text/**Table**/**Equation-Block**/**Diagram**), **HTML tables**,
    **LaTeX math**, diagram regions w/ captions. Held **even at Q4_K_M**.
  - **VRAM (not the blocker):** Q4 ~5.4 GB · Q5 ~5.8 GB · Q8 ~7.2 GB (8K ctx);
    resident server ~7.3 GB, frees cleanly on stop. Model trains at **256K ctx**.
  - **Throughput:** ~121 gen tok/s warm server → ~**8–20 pages/min** (batch-OK, not
    interactive). Long decks **not** run.
- **Fit:** runs on the **same `llama-server` the LMM already supervises** — **no new
  service**; only adds an mmproj + image message. Output maps to **`clean.md`** source
  text and (strongly) to **`visual_assets_manifest.json`** asset candidates (bbox /
  type / caption / table / equation), complementing Slice 40's `fitz` crops. **No
  manifest schema change made** (forbidden this slice).
- **Files (docs-only):** new `docs/CHANDRA_GGUF_SPIKE_REPORT.md`; this log;
  `docs/NEXT_CHAT_HANDOFF.md`. **No app/build/smoke** (no app code touched). Model
  files / weights / mmproj / quants live in a **throwaway workspace outside the repo**
  — none committed.
- **Recommended next slices (design, not yet built):** (1) host-companion **mmproj/
  quant build** step w/ a **pinned llama.cpp build**; (2) pure **output→clean.md +
  manifest normaliser** (reusing the Slice 38/40 schema); (3) **prompt/template**
  lock for reliable bbox+label output (`--image-min-tokens 1024` for grounding).
  **Fallback contract preserved:** Chandra unavailable → Tesseract/`fitz`; Chandra
  bad/timeout → degrade, never fail generation. Keep off-by-default + local-only.
- **Validation (docs/spike slice):** `git status --short`, `git diff --check`,
  `git diff --name-only` — changes are **docs-only**; repo clean of model artifacts.

---

## Slice 40 — Local figure extraction / cropping into the visual manifest (uncommitted on `slice40-local-figure-extraction-into-manifest`).

- **Purpose:** the **first real extractor-output change** in the visual stack (roadmap
  V1→V2 bridge). Where Slice 38 only emitted page-level `page_visual_signal` candidates
  (`bbox: null`), Slice 40 actually **crops embedded image regions out of the PDF** with
  PyMuPDF (`fitz`) and adds real **`extracted_figure`** assets — real `bbox`, a **safe
  relative `image_ref`** (`assets/<slug>.png`), and a saved PNG under the job's new
  `assets/` dir. **`fitz_local` only** — no Chandra/Mistral/Gemini/VLM, no network, no OCR.
- **Gated / off by default:** `GUIDEFORGE_LOCAL_FIGURE_EXTRACTION` (truthy = on). When
  unset/false the extractor is never invoked and the manifest is **byte-identical to
  Slice 38**. Verified flag-on (1 figure cropped, PNG written, in-page bbox) and flag-off
  (no work) live in the container.
- **No guide/prompt/render/export/UI change:** assets do **not** reach the generated
  guide this slice — Slice 40 only writes the **manifest + asset PNGs**. (Asset-aware
  prompt/render is a later V4/V5 slice; orphan-`{{figure}}`/coverage tests belong there.)
- **Files:**
  - `pipeline/visual_asset_extractor.py` (new) — `fitz` crop module:
    `local_figure_extraction_enabled()` + `extract_local_figures(pdf, assets_dir,
    source_index, pages, remaining_budget)`. Degrade-not-fail (missing fitz / corrupt PDF
    / bad image ⇒ fewer/zero assets, never a job failure). **Explosion prevention:** skips
    tiny/decorative regions (`MIN_SIDE_POINTS=24pt`, `MIN_AREA_FRACTION=0.004`), collapses
    duplicate placements of the same region, caps `MAX_FIGURES_PER_PAGE=12` /
    `MAX_FIGURES_PER_JOB=200`; crops at `CROP_DPI=150`. Deterministic ids/filenames
    (`s{src:02d}_page_{NNNN}_figure_{MM}`).
  - `pipeline/visual_assets_manifest.py` — `build_/write_visual_assets_manifest(... ,
    extracted_assets=None)`; the manifest **re-sanitises every extracted record
    field-by-field** (asset-id slug, `extracted_figure` type, finite/ordered `bbox`,
    strict `^assets/[A-Za-z0-9_]+\.png$` `image_ref`, whitelisted numeric `signals`) so the
    **manifest — not the fitz extractor — stays the security boundary** and cannot be
    poisoned. Summary gains `extracted_figure_count`. **Stays fitz-free / pure.**
  - `pipeline/job_manager.py` — new `Job.assets_dir` (`<job>/assets`), advisory, not in
    exports / `ARTIFACTS` / DTOs.
  - `pipeline/run_llm_job.py` — tracks saved PDF path + page set in lockstep with
    extraction-metadata sources; `_extract_local_figures(job, pdf_inputs)` runs the gated
    extractor and passes results to the manifest writer (off-by-default → no-op).
  - `test_scripts/test_local_figure_extraction.py` (new) — 59 checks: pure
    re-sanitisation (bbox validity, id slugging, safe relative refs, leak prevention,
    backward-compat) + real-fitz crops (file existence, in-page bbox, tiny/duplicate
    collapse, per-page cap, determinism).
- **Validation (green):** `python -m compileall api pipeline` OK; `git diff --check` clean;
  `test_local_figure_extraction.py` **50/0 host (2 fitz cases skip) → 59/0/0 in Docker**;
  `test_visual_assets_manifest.py` **65/0** (backward-compatible); fresh
  `docker compose build` + `up --force-recreate`; `/api/health` `{"ok":true}`;
  `smoke_release.py` **29/0/0** on live :8000 (default flag-off ⇒ guide output unchanged).
- **Next:** Slice 41 — dedup + decorative filtering (V2, perceptual-hash `dedupe_group`),
  then Slice 42 candidate scoring (V3). Chandra GGUF spike runs shortly after (not in
  parallel with this slice's validation).

---

## Slice 39 — Chandra local feasibility verification (COMMITTED `7b97146`, merged to `chrome-renderer-v1`).

- **Purpose:** the **Chandra equivalent of Slice 35's Mistral gate** — a docs-only
  feasibility verification of **Chandra (Datalab)** as a future **high-quality local**
  OCR / document-extraction / visual-asset provider (`chandra_local`) for the
  Local/Private mode. **No** install, run, clone, build, weight download, dependency,
  provider code, API route, setting, key, prompt, routing, extraction, render, or
  `visual_assets_manifest.json` schema change. Chandra was **not** installed or run;
  facts come from official Datalab sources (GitHub repo, HF model cards, `MODEL_LICENSE`)
  checked **June 2026**.
- **Deliverable:** new **`docs/CHANDRA_OCR_VERIFICATION.md`** (§0–§12): which artifact
  is which (Chandra 1 `datalab-to/chandra` 9B vs **Chandra 2 `datalab-to/chandra-ocr-2`
  ~4B, the target**), product status/maintainer, capabilities (official vs
  reported-but-unverified), GuideForge integration shape (maps into the **Slice 38**
  manifest; modeled as OCR + document + visual-asset provider; sits behind the Slice 32
  contract for text + a future manifest-feeding extraction path; powers the Slice 37
  `local_private` mode; coexists with `tesseract_local`/`fitz_local`/`mistral_ocr`),
  **hardware feasibility on RTX 5070 Ti 16 GB**, operational complexity (heavy CUDA/vLLM
  GPU service; best fit = LMM host-companion pattern but heavier than the GGUF case),
  **license** (Apache-2.0 code + **modified OpenRAIL-M weights**), cost/privacy,
  hands-on spike plan, risks/unknowns, sources, recommendation, next slice.
- **Key verified facts:** Chandra **2** (released **3/2026**), `datalab-to/chandra-ocr-2`,
  pip `chandra-ocr`, vLLM (recommended) or HF transformers; **olmOCR 85.9**; outputs
  **MD/HTML/JSON with detailed layout info**, image+diagram extraction **with captions
  + structured data**, tables/math/forms/handwriting/multi-column, 90+ languages.
  **Throughput: 1.44 pages/s on H100 80 GB @96 concurrency (~2 pages/s real-world est.)**
  — expect **much less** on a 16 GB consumer GPU.
- **PATCHED with GGUF evidence (the feasibility-changing update):** a community
  **`prithivMLmods/chandra-ocr-2-GGUF`** conversion exists, reporting **5B params /
  `qwen35`** and a quant ladder (**Q4_K_M ≈ 3.07 GB · Q5_K_M ≈ 3.51 GB · Q6_K ≈ 3.99 GB ·
  Q8_0 ≈ 5.16 GB · BF16/F16 ≈ 9.7 GB**) + separate **`mmproj` ≈ 367–676 MB** — **community
  GGUF evidence, not the official `datalab-to` distribution** (a community quant may
  lag/diverge; re-verify before the spike). Consequences recorded in the doc:
  - **Param count is no longer stated as "4B official":** secondary ~4B vs GGUF-card 5B/
    `qwen35`, none pinned on the official card → **re-verify at spike time.**
  - **Hardware verdict revised** from `uncertain-but-promising` to **GGUF-quantized
    Chandra OCR 2 likely feasible on the RTX 5070 Ti 16 GB (esp. Q4/Q5/Q8); VRAM is
    likely not the main blocker.** Real blockers are now **multimodal `llama.cpp`
    support, `mmproj` loading, OCR quality, throughput, long-document behavior, and
    integration stability.** Throughput caveat kept: a 500–2,000-page deck may still be
    slow on one consumer GPU.
  - **Integration reframed into two paths:** **official** = vLLM / HF Transformers via
    Chandra CLI/server; **practical first spike** = GGUF through the **existing
    `llama.cpp`/`llama-server`/Local Model Manager** pattern — which **could avoid a
    brand-new companion/service** if multimodal `llama-server` works. **First hands-on
    checkpoint:** *can current `llama-server` load Chandra GGUF + `mmproj` and do
    image/PDF-page → markdown OCR?*
- **License conclusion unchanged:** code Apache-2.0; weights "AI PUBS OPEN RAIL-M
  (MODIFIED)" — free for research/personal/startups < $2M revenue OR funding, no competing
  with Datalab's OCR API ⇒ **fine for personal/single-operator; multi-user/commercial
  needs Datalab license review** (non-legal guidance).
- **Honest correction to roadmap §6:** the rich Mermaid / chart-data / LaTeX / per-block
  bbox / typed-block claims are **reported / implied by "JSON with layout info" but NOT
  itemized on the official card/README** — flagged for confirmation against the real
  output in the hands-on spike (the GGUF path may emit a different format).
- **Recommendation (revised):** **`Proceed to hands-on GGUF spike after manifest schema`**
  (manifest schema already shipped in Slice 38) — **with an explicit license caveat for
  multi-user / commercial use. Still NOT approval to implement Chandra as a provider.**
  The spike tests: model load · `mmproj` availability/loading · image input through
  `llama-server` · output-format quality · **Q4_K_M / Q5_K_M / Q8_0 comparison** ·
  pages/minute · VRAM/RAM · fallback behavior · mapping output into
  `visual_assets_manifest.json`.
- **Proposed next:** continue the **local** visual stack first (Slice 40 fitz figure
  extraction/cropping into the manifest → V2 dedup → V3 candidate scoring — no GPU / no
  license question), then run the **Chandra 2 GGUF spike shortly *after* Slice 40 (NOT in
  parallel with Slice 40 validation** — GPU/`llama-server` noise would disturb the fresh
  extraction smoke), GGUF/`llama-server` first against a known-good reference, to gate
  whether `chandra_local` becomes a real provider and whether it can reuse the existing
  LMM `llama-server` path; only then a disabled/unwired `chandra_local` provider-design
  slice. **Visual measurement is staged:** Slice 40 only writes manifest/assets (test
  asset existence/bbox/ids/refs/caps/dup-explosion); `{{figure}}` orphan/coverage tests
  come **after** the asset-aware prompt/render slices.
- **Files (docs only):** `docs/CHANDRA_OCR_VERIFICATION.md` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `git status --short`, `git diff --check` clean, `git diff --name-only`
  docs-only (no build/smoke required — no code touched). **Do not commit Slice 39 yet**
  unless directed.

---

## Slice 38 — Visual assets manifest schema from existing signals (COMMITTED `8a788c7`, merged to `chrome-renderer-v1`).

- **Purpose:** add the first **provider-agnostic** `visual_assets_manifest.json`
  advisory artifact — the **normalization boundary** Slice 36 called for — populated
  **only** from existing page-level visual/page signals already collected for
  `extraction_metadata.json` (Slice 30/31/34). This is a **schema/advisory-artifact**
  slice, **not** an image-extraction slice.
- **Deliverable:** new `pipeline/visual_assets_manifest.py` — a stdlib-only module
  (`json` + `typing`, **no** `fitz`/Tesseract/Mistral/Gemini/Chandra/`ocr_provider`
  imports) with:
  - **Pure builder** `build_visual_assets_manifest(sources) -> dict` — takes the
    same already-sanitized extraction-metadata source records persisted in
    `extraction_metadata.json` and returns the manifest dict. Pure & total: never
    raises, never opens a PDF, never crops, never calls a provider; degrades to an
    empty-but-valid manifest on any bad input.
  - **Wrapped writers** `write_visual_assets_manifest(job, sources)` (advisory,
    never raises, degrades to a `skipped` artifact on write failure) and
    `write_skipped_visual_assets_manifest(job, ...)`.
- **Manifest top-level shape:** `{version:1, kind:"visual_assets_manifest",
  status:"completed", source:"extraction_metadata.json", assets:[...],
  summary:{asset_count, pages_with_visual_signals, source_providers:[...]},
  warnings:[]}`.
- **Asset record (page-level visual *candidate*):** `{asset_id:"page_NNNN_visual_01",
  source_page, asset_type:"page_visual_signal", bbox:null, caption:null,
  source_provider:"fitz_local", recommended_action:"unknown", dedupe_group:null,
  scores:{}, signals:{image_object_count, drawing_object_count, has_images,
  has_drawings, page_width, page_height, classification, ocr_route_action},
  warnings:[]}`. One candidate is emitted **per page** that carries a positive image
  OR drawing signal; a page with **both** yields exactly **one** candidate (its
  `signals` records both).
- **Because nothing is cropped, each asset is a page-level visual *candidate***
  ("this page has a visual signal worth a closer look later"), **not** a real
  extracted figure. `bbox` is always `null` this slice.
- **Closed vocabulary, leak-free:** `source_provider` only ever `fitz_local`
  (future-reserved `chandra_local`/`mistral_ocr`/`vlm_*` documented but **not**
  emitted); `asset_type` only `page_visual_signal`; `recommended_action` only
  `unknown` (no scoring yet); `classification`/`ocr_route_action` coerced to closed
  Slice 31/34 vocab; dimensions/counts coerced numerically. Every field is a fixed
  token / int / float / `None` / empty dict / deterministic `asset_id` — inputs are
  coerced field-by-field and **never echoed**, so no raw path, host path, image byte,
  raw PDF object, provider payload, OCR error, key/token/header, URL, socket, or argv
  can survive even from a smuggled record.
- **Persistence convention (smallest approach):** the manifest is **derived from
  `extraction_metadata.json`** and is written **exactly when those PDF sources
  exist** — wired in `run_llm_job.py` immediately after
  `write_extraction_metadata(...)`. Non-PDF jobs / unavailable metadata **omit** the
  artifact entirely (matching how non-applicable artifacts are handled). A page set
  with zero visual signals still writes a valid `completed` manifest with an empty
  `assets` list.
- **Access:** exact-name download via the existing
  `/api/jobs/{id}/artifacts/visual_assets_manifest.json` route (one `_artifact_path`
  entry + a `Job.visual_assets_manifest_json` property). **Not** added to the generic
  `ARTIFACTS` list, `_artifact_urls`/`_artifact_details`, export bundles, or any
  frontend tab — same posture as `math_verification.json` / `guide_lint.json` /
  `extraction_metadata.json`.
- **No API route added/changed** beyond the exact-name `_artifact_path` mapping (no
  new endpoint). **No** extraction/text/OCR/routing/prompt/render change; guide text
  and `clean.md` are byte-identical when this feature is unused (it only writes one
  sibling JSON).
- **Out of scope (later slices):** local figure extraction/cropping, dedup,
  decorative filtering, candidate scoring/text replacement, Chandra verification,
  Mistral skeleton, Gemini/VLM, any external API, UI, export-bundle wiring.
- **Files:** `pipeline/visual_assets_manifest.py` (new),
  `test_scripts/test_visual_assets_manifest.py` (new, 65 checks — pure builder +
  integration), `pipeline/job_manager.py` (+`visual_assets_manifest_json` property),
  `api/server.py` (+exact-name `_artifact_path` entry), `pipeline/run_llm_job.py`
  (+wrapped writer call), docs.
- **Validation (all green):** `test_visual_assets_manifest` 65/65, `compileall`,
  fresh Docker rebuild + `--force-recreate`, `/api/health` 200, `smoke_release.py`
  **29 passed / 0 failed / 0 skipped** on live :8000, exact-name route confirmed wired
  (`visual_assets_manifest.json` → graceful 404 on a non-PDF job, `clean.md` → 200),
  `git diff --check` clean. **Committed `8a788c7`, fast-forward merged to
  `chrome-renderer-v1`, pushed.**

---

## Slice 37 — OCR/extraction mode + cost/budget skeleton (COMMITTED `9fbbb1d`, merged to `chrome-renderer-v1`).

- **Purpose:** add a **pure, provider-agnostic** mode + cost/budget *framework*
  that later visual-manifest and cloud/Chandra provider slices can plug into —
  **without** changing any behavior. Framework/skeleton only; **no provider is
  implemented, no cloud call is made, cloud OCR stays disabled by default.**
- **Deliverable:** new `pipeline/ocr_modes.py` — a stdlib-only module
  (`dataclasses` + `typing`, **no** `fitz`/Tesseract/`ocr_provider`/cloud SDK
  imports) defining:
  - **Modes** (Slice 36 vocab): `local_private` (default) · `smart_cloud_assist`
    · `maximum_fidelity`.
  - **Provider roles:** `local_ocr_provider` · `cloud_document_provider` ·
    `cloud_vision_provider`. **Provider ids:** `tesseract_local` (impl today) ·
    `chandra_local` · `mistral_ocr` (future; naming them wires nothing).
  - **DTOs:** `OcrModeSettings` (mode, `cloud_opt_in`, `local_ocr_available`,
    `page_cap`, `dollar_cap`, `selected_page_count`) · `OcrBudget` ·
    `OcrProviderPricing` · `OcrCostEstimate` (mode, provider id/role, billing
    unit, billed pages, `estimated_cost_usd`, `currency:"USD"`, `is_estimate`,
    `status`, `price_source`, closed-vocab `warnings`).
  - **Functions:** `default_ocr_mode_settings()` · `resolve_ocr_mode_config()` ·
    `ocr_budget()` · `provider_pricing()` · `estimate_ocr_cost()` ·
    `safe_ocr_mode_settings_dict()` · `safe_ocr_cost_estimate_dict()` ·
    `ocr_provider_pricing_snapshot()`.
- **Mapping to Slice 33 routing:** `resolve_ocr_mode_config(settings)` returns the
  exact `pipeline.ocr_routing.default_config()` shape (`allow_cloud_ocr`,
  `local_ocr_available`, `max_ocr_pages`, `page_budget_remaining`) plus an
  advisory `mode` echo the routing core ignores. **Default mode `local_private`
  ⇒ `allow_cloud_ocr=False`.** `allow_cloud_ocr` is `True` **only** when the mode
  is cloud-capable **AND** `cloud_opt_in is True` (a real bool — truthy strings
  are rejected). A mode name alone never enables cloud; even when allowed, the
  Slice 33 policy only returns an *advisory* `cloud_ocr_candidate` — no cloud OCR
  is wired into extraction.
- **Cost skeleton:** static, documented price snapshot only (no network).
  `mistral_ocr` = **per page, ~$2/1,000 (standard) / ~$1/1,000 (batch),
  `is_estimate:true`, `price_source:"docs/MISTRAL_OCR_VERIFICATION.md"` (June 2026
  estimate, re-verify before any billing UI)**. Local providers are free/exact.
  Unknown providers ⇒ safe `status:"unavailable"/"unknown"`. 500 pages on
  `smart_cloud_assist` ⇒ advisory `$1.00`, `is_estimate:true`, page/dollar caps
  applied as advisory warnings.
- **Leak-safety:** every output field is a closed-vocab token / int / float /
  `None` / `"USD"` / the repo-relative `price_source`; hostile keys (api_key,
  base_url, authorization, host/socket path, argv) are dropped, never echoed.
- **No API route added or changed; no frontend.** Not wired into extraction,
  routing, prompts, `/api/jobs/llm` fields, Ask/retrieval, render, artifacts,
  exports, or `extraction_metadata.json`/manifest schemas.
- **Files changed:** `pipeline/ocr_modes.py` (new),
  `test_scripts/test_ocr_modes.py` (new, 121 checks), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** frontend build + `npm run test` green · `compileall api
  pipeline test_scripts` clean · full backend OCR/eval/lint/ask suite green ·
  `test_ocr_modes.py` 121/121 · eval `--offline --all` no regression ·
  `git diff --check` clean · `smoke_release.py` green (live :8000).
- **Proposed next:** `visual_assets_manifest.json` normalization-boundary skeleton
  (still no provider/extraction change), per `docs/VISION_ROADMAP.md`.

---

## Slice 36 — Revised visual / cost / provider-strategy roadmap (COMMITTED + MERGED to `chrome-renderer-v1`, commit `976aebc`).

- **Purpose:** capture the operator's revised long-range vision as a **planning
  doc**, before any visual-asset or cloud-OCR code. **Implements nothing** — no
  code, dependency, provider setting, key, prompt, routing, extraction, schema,
  or render change; no external OCR/vision API (Mistral / Gemini / Chandra) was
  called.
- **Deliverable:** new `docs/VISION_ROADMAP.md` covering: planning-status caveats
  (repo is source of truth; re-verify every provider fact at impl time); the
  **Capture → Explain → Show → Trust → Retain** north star; current gap analysis
  (Explain strong, Capture text-only, Show unbuilt, Trust partial, cost/privacy
  primitive); the **three-mode** strategy (Local/Private default · Smart Cloud
  Assist · Maximum Fidelity); the **provider-agnostic `visual_assets_manifest.json`
  normalization boundary** (sources `fitz_local` / `chandra_local` / `mistral_ocr`
  / future `vlm_*`; closed-vocab asset records: `asset_id`, `source_page`,
  `asset_type`, `bbox`, `caption`, `source_provider`, `recommended_action`,
  `dedupe_group`, `scores`; no raw paths/keys/URLs/payloads); provider roles;
  **Chandra framing** (near-roadmap high-quality *local* mode, license caveat,
  **not** production-approved until docs slice + RTX 5070 Ti hands-on spike);
  privacy-as-disclosure/consent (not a hard blocker); the **dependency-ordered
  visual stack V1–V7** (render-embed late/high-risk); the **OCR-classification vs
  visual-candidate-scoring** separation; a **proposed** Slice 37–43 order; and the
  carried slice principles.
- **Key reframing:** this **resequences (does not cancel)** the old
  `HYBRID_OCR_DESIGN.md` §9 "Slice 36 = Mistral provider" item — the Mistral
  provider skeleton is now **proposed Slice 43** (disabled/unwired), so the
  provider-agnostic mode/budget + visual-manifest layer can land first.
- **Mistral kept on the near map** as a visual/table enabler (likely first cloud
  document-extraction provider), **not shelved**; **Chandra captured** as the
  near-roadmap high-quality *local* option that could make Local/Private mode
  high quality for GPU users (still gated).
- **Proposed next:** **Slice 37 — provider-agnostic OCR/extraction mode +
  cost/budget skeleton** (framework only; no provider wired, no cloud call).
- **Files changed (docs only):** `docs/VISION_ROADMAP.md` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`,
  `docs/ROADMAP_INPUT_SUMMARY.md`, `docs/DECISIONS.md`.
- **Validation:** `git diff --name-only` shows docs only · `git diff --check`
  clean · no build/smoke needed (no code touched).
- **Note on numbering:** Slices 37–43 in `docs/VISION_ROADMAP.md` are **proposed
  future work, not completed** — do not treat them as existing.

---

## Slice 35 — Mistral OCR prerequisite verification (COMMITTED + MERGED to `chrome-renderer-v1`, commit `45a54d2`).

- **Purpose:** prerequisite **gate** before *any* cloud-OCR code. Verify whether
  **Mistral OCR / Document AI** is safe and suitable as a future cloud OCR provider,
  from official Mistral sources. **Implements nothing** — no code, dependency,
  provider setting, key, prompt, routing, extraction, or schema change. No Mistral
  API was called with any document.
- **Deliverable:** new `docs/MISTRAL_OCR_VERIFICATION.md` covering product status,
  request/response format, pricing, rate limits, privacy/data-handling, fit with the
  Slice 32 boundary + Slice 33/34 routing, implementation risks, unknowns, sources,
  and a recommendation.
- **Key facts verified (June 2026, re-confirm at impl time):** GA & versioned —
  original Mistral OCR plus **Mistral OCR 3** (`mistral-ocr-2512`, GA 2025-12-17);
  `mistral-ocr-latest` alias. Endpoint `POST https://api.mistral.ai/v1/ocr`
  (SDK `client.ocr.process`). Inputs: PDF/PPTX/DOCX or image via public URL, base64,
  or uploaded file id; **≤ 50 MB, ≤ 1,000 pages**; Batch API (async, −50%). Output:
  **per-page Markdown** + tables (md/HTML) + images + dimensions + optional
  confidence scores. Pricing **per page** (~$1/1,000 original, ~$2/1,000 OCR 3;
  half via batch). Rate limits per API key (RPS/TPM/monthly, tiered). Privacy: API
  data **not used for training**; default **30-day** abuse-retention unless **ZDR**
  (Scale plan, stateless calls only); self-host option for sensitive orgs.
- **Architecture fit:** **no blockers** — Slice 32 `OcrProvider`/`OcrResult` boundary,
  Slice 33 `cloud_ocr_candidate`/`allow_cloud_ocr`/shared budget, and Slice 34
  advisory `ocr_route_*` recorder already provide the exact seams. A future
  `MistralCloudOcrProvider` plugs into the Slice 32 contract; routing flips the
  Slice 33 candidate into a real dispatch only under explicit opt-in, page-budgeted,
  with mandatory local-Tesseract fallback. Key/`Authorization`/raw provider
  errors/URLs/doc paths stay **server-side only** (provider-settings DTO posture).
- **Recommendation:** **Proceed only after the operator confirms pricing and
  privacy**, then implement strictly behind an explicit, off-by-default opt-in. The
  gating concerns are **policy** (confirm live per-page price; accept third-party
  processing of student notes with default 30-day retention, mitigable via opt-in +
  ZDR + no public URLs), **not** technical. **Not** a green light to route real
  documents through Mistral yet.
- **Proposed next:** **Slice 36 — Mistral OCR provider skeleton / OCR provider-settings
  + key-storage design, disabled by default** (no network to generation).
- **Files changed (docs only):** `docs/MISTRAL_OCR_VERIFICATION.md` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `git diff --name-only` shows docs only · `git diff --check` clean ·
  no build/smoke needed (no code touched).
- **Note on prior position:** trunk HEAD is now **Slice 34 committed**
  (`25e3fd3`), not the uncommitted state the older handoff text below describes.

---

## Slice 34 — wire local OCR routing into extraction (IMPLEMENTED — uncommitted on `slice34-wire-local-ocr-routing`).

- **Purpose:** first **live** integration of the Slice 33 routing policy into the
  PDF extraction path — **local-only and behaviour-compatible**. Extraction now
  records a safe, advisory per-page **routing decision**; it does **not** add
  Mistral/cloud OCR, provider settings, UI, prompt changes, or any
  generation-gating. This is Slice 34 in `docs/HYBRID_OCR_DESIGN.md` §9.
- **Recorder, not a router (key design):** the policy is consulted *after* a page's
  method/text/visual signals are known and is recorded as metadata; it **never
  decides whether OCR actually runs.** The unchanged per-page text-vs-OCR logic in
  `_extract_pdf` still does that, so **extracted text and `## Page N` anchors are
  byte-identical** to before and OCR-availability behaviour is preserved. (A blank
  page that extraction historically *attempts* to OCR still does so even though the
  advisory route says `skip_ocr` — advisory route metadata, not yet a
  behaviour-changing router.)
- **Where it's wired:** `pipeline/extract.py` imports
  `ocr_routing.decide_ocr_route` and `extraction_metadata.classify_pdf_page_record`.
  New `_pdf_route_decision(record, *, ocr_ready)` maps a page's already-collected
  signals → advisory `classification` (shared classifier = single source of truth)
  → policy decision, with `local_ocr_available = ocr_ready` (the document-level
  Tesseract availability the extractor already probed) and `allow_cloud_ocr=False`.
  `_pdf_page_metadata(..., ocr_ready=...)` attaches the route to every PDF page.
- **New per-page fields (additive):** `ocr_route_action`, `ocr_route_provider`,
  `ocr_route_reason`, `ocr_route_confidence`, `ocr_route_warnings` — all
  closed-vocabulary / JSON-safe. **Local-only:** `ocr_route_provider` is only ever
  `"tesseract_local"` or `null` (never a cloud id).
- **Sanitiser carries, not recomputes:** `extraction_metadata._safe_page` whitelists
  each route token against the vocabularies imported from `ocr_routing` (new
  `_safe_route_*` helpers) — the same carry-and-coerce posture it already applies to
  `method`/`warnings`. A smuggled `ocr_route_*` value coerces to a fixed safe token;
  no path, secret, image blob, URL, or free-text error can survive. Route fields are
  emitted **only when the extractor supplied them**, so legacy / hand-built / non-PDF
  records stay byte-identical.
- **`extraction_metadata.json` stays `version: 2`** — additive page fields under the
  established "bump once on the first new field (Slice 30), not on every additive
  field" rule (see `DECISIONS.md`). No other artifact schema touched.
- **Degrade-not-fail:** `_pdf_route_decision` wraps the whole adapter; any unexpected
  error records a fixed safe route (`action:"unknown"`,
  `reason:"routing_unavailable"`, `warnings:["routing_input_unrecognized"]`) and
  never propagates. Routing can never fail a generation.
- **Scope guard — NO change to:** Mistral/cloud OCR, provider settings, prompts,
  `/api/jobs/llm` request fields, frontend/UI, Ask/retrieval, LanceDB/embeddings,
  the generic `ARTIFACTS`/export-bundle lists, the PDF/Chromium render pipeline,
  generation gating, or the `validation.json` / `math_verification.json` /
  `guide_lint.json` schemas. The OCR engine still goes through the Slice 32 local
  provider boundary unchanged.
- **Files changed:** `pipeline/extract.py`, `pipeline/extraction_metadata.py`,
  `test_scripts/test_ocr_routing_integration.py` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ ·
  `test_ocr_routing_integration` 56/56 (fitz e2e skipped on host) ·
  `test_ocr_routing_policy` 120/120 · `test_extraction_metadata` 9/9 ·
  `test_pdf_page_classification` 56/56 · `test_pdf_visual_signals` 44/44 ·
  `test_ocr_provider` 18/18 · `test_math_verifier` 74/74 · `test_guide_lint` 74/74 ·
  `test_eval_harness` 64/64 · `test_page_anchor_reachability` 21/21 ·
  `test_source_page_citations` 19/19 · `test_ask_retrieval_relevance` 12/12 ·
  `test_ask_lexical_hygiene` 34/34 · `test_guide_lint_artifact` 26/26 ·
  `run_eval.py --offline --all` scored 3 (no regression) · `git diff --check` clean.
  `smoke_release.py` requires the live Dockerized app on :8000 (not running in this
  host shell) — run it in Docker for full e2e coverage, along with the fitz path.
- **Next:** Slice 35 — Mistral OCR prerequisite verification (docs-only; gate for the
  gated cloud provider in Slice 36). Routing stays local-only/advisory until then.

---

## Slice 33 — hybrid OCR routing policy core (COMMITTED + MERGED to `chrome-renderer-v1`, commit `5296976`).

- **Purpose:** add a **pure, deterministic OCR routing-policy core** that decides
  what *should* happen for a page (use embedded text / local OCR / skip / cloud
  candidate) from the existing advisory page classification, **without wiring it
  into extraction**. This is the "pure core, then integrate" step in
  `docs/HYBRID_OCR_DESIGN.md` §9 (Slice 33); §5/§6 describe the policy. Extraction
  behaviour, OCR calls, prompts, metadata artifacts, and generation are unchanged.
- **New module `pipeline/ocr_routing.py`:**
  - `decide_ocr_route(page_metadata, config=None) -> decision` — single page.
  - `decide_ocr_routes(pages, config=None) -> [decision, ...]` — list with a
    shared OCR-page budget applied in input order.
  - `default_config()` — local-first, cloud-off defaults.
  - Reads **only** `page_metadata["classification"]`; never trusts or echoes any
    other input field, so smuggled paths/secrets/image blobs cannot leak.
  - **Pure / deterministic / dependency-free:** no I/O, clock, or randomness; no
    import of `fitz`, Tesseract, `pipeline.ocr_provider`, cloud providers, or
    provider settings. The classification vocabulary is mirrored locally.
- **Decision shape (JSON-safe, closed vocab only):**
  `{action, provider, reason, confidence, warnings}`.
  - `action` ∈ `{use_embedded_text, use_local_ocr, skip_ocr, cloud_ocr_candidate,
    unknown}`.
  - `provider` is `null` or the literal `"tesseract_local"` (no key/URL/path,
    `null` for cloud candidates — no cloud provider exists).
  - `reason` / `warnings` are fixed tokens (`REASONS` / `WARNINGS`); `confidence`
    ∈ `{high, medium, low}`.
- **Policy mapping (from classification):**
  - `embedded_text` → `use_embedded_text` (`embedded_text_sufficient`, high).
  - `mixed` → `use_embedded_text` (`mixed_has_meaningful_text`, medium) — trust
    the text layer, don't OCR a page that already has meaningful text.
  - `ocr_fallback` → `use_embedded_text` (`ocr_already_applied`, high) — OCR
    already ran and produced this page's captured text; re-OCRing would duplicate
    work and change nothing (documented choice).
  - `likely_scanned` → `use_local_ocr` (`scanned_needs_ocr`, provider
    `tesseract_local`), subject to availability + budget.
  - `blank_or_low_text` → `skip_ocr` (`blank_low_text_no_visual`, high).
  - `unknown`/unrecognised → `unknown` (`unknown_classification`, low) —
    conservative, never cloud, never spends budget.
  - `error` → `skip_ocr` (`classification_error`, low).
- **Local / cloud / budget behaviour:**
  - **Local-first, cloud-off by default.** `cloud_ocr_candidate` is returned
    **only** when `allow_cloud_ocr` is an explicit `True` AND local OCR is
    unavailable; provider stays `null` (advisory future option, nothing wired).
    With local available, cloud is never volunteered even when allowed.
  - Local unavailable + cloud off → `skip_ocr` with `local_ocr_unavailable` +
    `cloud_ocr_disabled` warnings (job still runs on whatever text exists).
  - **Budget:** `page_budget_remaining` (or `max_ocr_pages`) caps OCR-bound
    pages; only OCR actions consume budget; once exhausted, OCR-bound pages
    downgrade to `skip_ocr` (`ocr_budget_exhausted`). Deterministic by input order.
  - Config sanitiser rejects truthy non-booleans (a smuggled string can't flip
    cloud on) and coerces bad counts to `None`.
- **Failure is impossible:** any malformed/hostile input → fixed safe decision
  (`action:"unknown"`, `reason:"routing_unavailable"`,
  `warnings:["routing_input_unrecognized"]`); `decide_ocr_routes` on a non-list →
  `[]`, and a bad page mid-batch degrades without aborting the batch.
- **NOT wired into extraction.** Nothing in `pipeline/extract.py`, `api/`, or the
  frontend imports `ocr_routing`; `grep` confirms only the module + its test
  reference it. No extraction text change, no OCR call, no metadata-artifact change.
- **Scope guard — NO change to:** `pipeline/extract.py`, Mistral/cloud OCR,
  provider settings, prompts, `/api/jobs/llm` request fields, frontend/UI,
  Ask/retrieval, LanceDB/embeddings, the generic `ARTIFACTS`/export-bundle lists,
  the PDF/Chromium render pipeline, generation gating, or the `validation.json` /
  `math_verification.json` / `guide_lint.json` / `extraction_metadata.json` schemas.
- **Files changed:** `pipeline/ocr_routing.py` (new),
  `test_scripts/test_ocr_routing_policy.py` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ ·
  `test_ocr_routing_policy` 120/120 · `test_math_verifier` 74/74 · `test_guide_lint`
  74/74 · `test_eval_harness` 64/64 · `test_page_anchor_reachability` 21/21 ·
  `test_source_page_citations` 19/19 · `test_extraction_metadata` 9/9 ·
  `test_pdf_visual_signals` 44/44 · `test_pdf_page_classification` 56/56 ·
  `test_ocr_provider` 18/18 (tesseract-gated e2e skipped on host) ·
  `test_ask_retrieval_relevance` 12/12 · `test_ask_lexical_hygiene` 34/34 ·
  `test_guide_lint_artifact` 26/26 · `run_eval.py --offline --all` scored 3 (no
  regression) · `git diff --check` clean · `smoke_release.py` ✓.
- **Next:** Slice 34 — wire the router into the local Tesseract extraction path
  and record `ocr_recommended` / `ocr_attempted` / `skipped_reason` in metadata
  (the first slice that *changes* what extraction records; still local-only).

---

## Slice 32 — OCR provider boundary refactor (COMMITTED + MERGED to `chrome-renderer-v1`, commit `c42837c`).

- **Purpose:** isolate OCR behind a clean **backend-only provider boundary**
  before any routing change or cloud OCR provider, with **local behaviour kept
  byte-identical**. Slice 30 added visual signals, Slice 31 added advisory page
  classification; this is Slice 32 in the `docs/HYBRID_OCR_DESIGN.md` §9 sequence
  (it is the "pure refactor" slice — no behaviour change).
- **New module `pipeline/ocr_provider.py`:**
  - `OcrRequest(page, page_number)` — a single `fitz` page handle + 1-based page
    number; the provider rasterises the page itself (no whole-document, no paths,
    no job/user ids cross the boundary).
  - `OcrResult(text, provider_id, confidence=None, warnings=[], error_category=None)`
    — normalised, JSON-safe; whitelisted fields only (no image bytes, raw page
    data, paths, URLs, keys, or raw error strings). `confidence` stays `None`
    (the local `image_to_string` path doesn't return it cheaply).
  - `OcrProvider` — base contract: `provider_id`, `is_available() -> (ready,
    reason)`, `ocr_page(request) -> OcrResult`.
  - `TesseractLocalOcrProvider` (`provider_id = "tesseract_local"`) — the default
    and only provider; a **behaviour-identical** wrapper around the old in-line
    `_ocr_available` / `_ocr_page` / `_preprocess_ocr_image`. `_preprocess_ocr_image`
    moved here.
  - `get_default_ocr_provider()` — returns a stable module-level singleton.
- **`pipeline/extract.py` rewiring (minimal):** `_extract_pdf` now does
  `ocr_provider = get_default_ocr_provider()`, `ocr_ready, reason =
  ocr_provider.is_available()`, and `ocr_provider.ocr_page(OcrRequest(page=page,
  page_number=index)).text` (still guarded by `if ocr_ready`). `_ocr_available()`
  remains as a thin backward-compatible shim delegating to the provider (kept for
  `preflight_pdf` + existing tests that import it). `_ocr_page` /
  `_preprocess_ocr_image` removed from `extract.py` (no external callers); unused
  `import shutil` dropped.
- **Behaviour preserved (degrade-not-fail unchanged):** same pages OCR'd, same
  extracted text, same `mode`/`method` derivation, same per-page warnings
  (`ocr_unavailable` / `ocr_empty_fallback_embedded_text` / `no_text_extracted`),
  same once-per-document availability message strings. The old in-line OCR path did
  **not** catch raster/recognise exceptions, so — to stay byte-identical — the local
  provider does **not** either; `error_category` is reserved for future providers.
- **`extraction_metadata.json`: UNCHANGED.** No `ocr_provider` field added, **no
  version bump** (stays `version: 2`). Adding the provider id now would alter the
  artifact bytes for OCR'd pages; it is deferred to the routing slice (34). The
  existing `test_extraction_metadata.py` exact-value asserts pass unchanged = the
  byte-identical proof.
- **Scope guard — NO change to:** Mistral/cloud OCR, OCR routing, page
  classification, prompts, provider settings, `/api/jobs/llm` request fields,
  frontend/UI, Ask/retrieval, LanceDB/embeddings, the generic `ARTIFACTS`/
  export-bundle lists, the PDF/Chromium render pipeline, generation gating, or the
  `validation.json` / `math_verification.json` / `guide_lint.json` schemas.
- **Files changed:** `pipeline/ocr_provider.py` (new), `pipeline/extract.py`
  (rewire), `test_scripts/test_ocr_provider.py` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ · `test_ocr_provider`
  37/37 (incl. fitz integration paths: provider success, text-page-skips-OCR,
  unavailable-degrade, empty-OCR-drop, no-leak) · `test_math_verifier` 74/74 ·
  `test_guide_lint` 74/74 · `test_eval_harness` 64/64 ·
  `test_page_anchor_reachability` 21/21 · `test_source_page_citations` 19/19 ·
  `test_extraction_metadata` 9/9 host (46/46 with fitz) · `test_pdf_visual_signals`
  44/44 · `test_pdf_page_classification` 56/56 · `test_ask_retrieval_relevance`
  12/12 · `test_ask_lexical_hygiene` 34/34 · `test_guide_lint_artifact` 26/26 ·
  `eval/run_eval.py --offline --all` ✓ · `git diff --check` clean ·
  `smoke_release.py` (live :8000) ✓. **Not committed** (per slice rule).

---

## Slice 31 — advisory PDF page classification metadata (IMPLEMENTED — uncommitted on `slice31-pdf-page-classification-metadata`).

- **Purpose:** the next step after Slice 30. Use the existing text/word/method
  signals (Slice 24A) plus the visual/object signals (Slice 30) to emit an
  **advisory page classification** in `extraction_metadata.json`. This slice
  **only adds derived metadata** — it does **not** call OCR, reroute pages,
  change extracted text, or touch prompts/generation.
- **Fields added (per PDF page, advisory-only):**
  - `classification` — one of `embedded_text | ocr_fallback | likely_scanned |
    blank_or_low_text | mixed | unknown | error` (closed vocabulary; `unknown`
    fallback, like `_safe_method`).
  - `classification_reasons` — list of fixed, whitelisted reason tokens
    (e.g. `method_ocr`, `meaningful_embedded_text`, `images_present`,
    `no_visual_objects`, `visual_signals_unavailable`,
    `classification_unavailable`). No free text, paths, or values.
  - `ocr_recommended` — bool routing **hint** only; `True` only for
    `likely_scanned`. Nothing reads it yet.
- **Where computed:** `pipeline/extraction_metadata.py::_classify_pdf_page(record)`
  (pure helper) called from `_safe_page` **after** the record is fully sanitized.
  It reads only the already-sanitized numeric/method/visual fields — never any
  upstream-supplied `classification` key — so a smuggled value is overwritten by
  construction. `_safe_classification` / `_safe_reasons` whitelist the persisted
  output.
- **Heuristics (conservative, deterministic):** `method == "ocr"` →
  `ocr_fallback`. `embedded_text` with meaningful text (≥40 chars OR ≥5 word
  tokens, mirroring `_is_meaningful_page_text`) → `embedded_text`, or `mixed` when
  image objects are present. Low/zero-text pages (`none`, or sparse `embedded_text`
  fallback) → `likely_scanned` when image/drawing objects are present,
  `blank_or_low_text` when visuals were positively measured-absent, else `unknown`
  (visual signal missing → cannot distinguish scan from blank). Explicit per-page
  error warning (`page_extraction_error` / `ocr_error` / `extraction_error`, none
  emitted today) → `error`.
- **Versioning:** `extraction_metadata.json` stays **`version: 2`**. The new fields
  are purely additive/optional, consistent with the Slice 29 rule (bump once when
  the first new field ships — done in Slice 30; later additive fields keep v2). No
  version churn.
- **Degrade-not-fail:** `_classify_pdf_page` never raises; any unexpected input
  degrades to `classification: "unknown"` + `["classification_unavailable"]`.
  Persisted classification is **always** in the closed vocabulary.
- **Scope guard — NO change to:** extraction text output, OCR behaviour/routing,
  Mistral/cloud OCR, provider settings, prompts, `/api/jobs/llm` request fields,
  frontend/UI, Ask/retrieval, LanceDB/embeddings, the generic `ARTIFACTS`/
  export-bundle lists, the PDF/Chromium render pipeline, generation gating, or the
  `validation.json` / `math_verification.json` / `guide_lint.json` schemas.
- **Files changed:** `pipeline/extraction_metadata.py`,
  `test_scripts/test_pdf_page_classification.py` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ · backend suites
  (`test_math_verifier` 74/74, `test_guide_lint` 74/74, `test_eval_harness` 64/64,
  `test_page_anchor_reachability` 21/21, `test_source_page_citations` 19/19,
  `test_extraction_metadata` 9/9, `test_pdf_visual_signals` 44/44,
  `test_ask_retrieval_relevance` 12/0, `test_ask_lexical_hygiene` 34/0,
  `test_guide_lint_artifact` 26/26, `test_pdf_page_classification` 56/56) ✓ ·
  `eval/run_eval.py --offline --all` ✓ (delta 0.0) · `git diff --check` ✓ ·
  `smoke_release.py` ✓. Host Python lacks PyMuPDF so the PDF-attachment section of
  `test_extraction_metadata.py` SKIPs (documented); classification is fully covered
  by the plain-dict tests in `test_pdf_page_classification.py` and runs end-to-end
  in Docker.
- **Not committed** (per task instruction).

---

## Slice 30 — PDF page visual-signal metadata (COMMITTED + MERGED to `chrome-renderer-v1`, commit `752bf03`).

- **Purpose:** the first implementation step after the Slice 29 design. Enrich the
  per-page PDF `extraction_metadata.json` records with cheap, additive
  visual/object signals so a **future** slice can classify scanned/image-heavy
  pages and route OCR. This slice **only collects data** — it does **not** classify
  pages, decide OCR routing, call any OCR, or change extracted text.
- **Fields added (per PDF page, advisory-only, numeric/boolean):**
  - `image_object_count` — `len(page.get_images(full=False))`; `None` if unmeasured.
  - `drawing_object_count` — `len(page.get_drawings())`; `None` if unmeasured.
  - `has_images` / `has_drawings` — booleans derived from the counts; `None` if
    unmeasured.
  - `page_width` / `page_height` — from `page.rect` (points, 2-dp); `None` if
    unmeasured.
  - `visual_warnings` — only present when a signal failed; carries safe category
    strings (`visual_image_signal_unavailable`, `visual_drawing_signal_unavailable`,
    `visual_dimension_signal_unavailable`) — never exception text or paths.
- **Where collected:** `pipeline/extract.py::_pdf_visual_signals(page)`, called once
  per processed page inside `_extract_pdf`'s loop (after the page-selection skip,
  before/around the existing text/OCR decision). Merged into the page record by
  `_pdf_page_metadata(..., visual=...)`. Carried through the artifact sanitiser
  `pipeline/extraction_metadata.py::_safe_page` (whitelisted + coerced).
- **Versioning:** `extraction_metadata.json` bumped `version: 1 → 2` (both the
  `completed` and `skipped` payloads) per the Slice 29 rule "bump to v2 when the
  first new field ships". All v1 keys remain present and unchanged; new fields are
  optional/additive; missing new keys mean "not measured", never an error.
- **Degrade-not-fail:** `_pdf_visual_signals` never raises — each of the three
  signal groups is independently guarded; on failure the field is `None` and a safe
  category is appended to `visual_warnings`. Extraction text, mode/method, job
  status, and all other artifacts are untouched. No image bytes, object data,
  paths, or text ever enter the metadata.
- **Scope guard — NO change to:** extraction text output, OCR behaviour/routing,
  page classification (deferred to Slice 31), Mistral/cloud OCR, provider settings,
  prompts, `/api/jobs/llm` request fields, frontend/UI, Ask/retrieval,
  LanceDB/embeddings, the generic `ARTIFACTS`/export-bundle lists, the
  PDF/Chromium render pipeline, or generation gating. No `validation.json` /
  `math_verification.json` / `guide_lint.json` schema change.
- **Files changed:** `pipeline/extract.py`, `pipeline/extraction_metadata.py`,
  `test_scripts/test_extraction_metadata.py` (version 1→2 + visual-field
  assertions), `test_scripts/test_pdf_visual_signals.py` (new),
  `docs/CURRENT_TASK.md`, `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend run
  test` ✓ · `python -m compileall api pipeline test_scripts` ✓ · backend suites
  (`test_math_verifier` 74/74, `test_guide_lint` 74/74, `test_eval_harness` 64/64,
  `test_page_anchor_reachability` 21/21, `test_source_page_citations` 19/19,
  `test_extraction_metadata` 9/9, `test_ask_retrieval_relevance` 12/0,
  `test_ask_lexical_hygiene` 34/0, `test_guide_lint_artifact` 26/26,
  `test_pdf_visual_signals` 44/44) ✓ · `eval/run_eval.py --offline --all` ✓ ·
  `git diff --check` ✓ · `smoke_release.py` 29/0 ✓. Host Python lacks PyMuPDF, so
  the PDF-attachment + route sections of `test_extraction_metadata.py` SKIP
  (documented behaviour); the visual-signal logic is fully covered by the
  fake-page tests in `test_pdf_visual_signals.py` and runs end-to-end in Docker.

---

## Slice 29 — Hybrid OCR & scan-aware extraction architecture (DESIGN-ONLY — committed `d0b91f1`, merged to `chrome-renderer-v1`).

- **Purpose:** decide the architecture for hybrid OCR, scan-aware extraction, and
  a future OCR-provider boundary (with Mistral OCR as a candidate cloud provider)
  **before** writing any OCR code. Docs only — no application code, no schema, no
  dependency, no extraction/OCR behaviour change.
- **Deliverable:** new `docs/HYBRID_OCR_DESIGN.md` covering: (1) the current
  extraction flow grounded in `pipeline/extract.py` /
  `pipeline/extraction_metadata.py` / `pipeline/run_llm_job.py` /
  `api/server.py`; (2) a page-classification model (`embedded_text`,
  `ocr_fallback`, `likely_scanned`, `blank_or_low_text`, `mixed`, `error`) and the
  signals that determine each; (3) a backward-compatible `extraction_metadata.json`
  evolution (additive/optional fields, `version: 1` stays readable, bump to
  `version: 2` only when a new field ships); (4) a backend-only OCR provider
  boundary (`tesseract_local` default, future `mistral`, future local model);
  (5) a cost- & privacy-aware hybrid routing policy (embedded → local → cloud,
  cloud opt-in/off by default); (6) large-PDF interaction reusing existing
  preflight + page-range + size guards; (7) Mistral OCR **prerequisites to verify**
  (endpoint/format, file types, page limits, pricing, output shape, rate limits,
  privacy/retention, errors) — **not implemented**; (8) OCR security/privacy
  constraints extending CLAUDE.md invariants; (9) a proposed 7-slice sequence
  (Slices 30–36).
- **Grounding facts captured (verified in code, not assumed):**
  - PDFs read via PyMuPDF (`fitz`) in `_extract_pdf`; `## Page N` anchors use the
    **original physical** page index; per-page text/OCR decision is already
    page-level (`_is_meaningful_page_text` ≥ 40 chars or ≥ 5 word tokens →
    embedded; else per-page Tesseract OCR; else drop).
  - `extraction_metadata.json` (Slice 24A, `version: 1`) is written in
    `_attach_sources` after extraction, before the LLM call; per-page `method` ∈
    `{embedded_text, ocr, none}` and `_safe_method` whitelists
    `{embedded_text, ocr, none, unknown}`. Downloadable by exact name only; not in
    generic artifact lists; PDF attachments only.
  - Preflight (`preflight_pdf` → `POST /api/preflight/pdf` →
    `_build_pdf_preflight_report`) is OCR-free, produces `scanned_flag`
    (`text`/`mixed`/`image_heavy`/`unknown`), `verdict`, `recommended_mode`,
    `allowed_actions`; image-object presence is **not** inspected today (the key
    new signal the design adds in Slice 30).
- **Key decisions:** classification is **additive/advisory** next to legacy
  `method` (never required, unknown-safe); OCR keys follow the existing
  server-side-only, write-only, key-less-DTO provider pattern; cloud OCR is
  **opt-in and off by default** (local-first, mirroring Ask staying local-only);
  OCR is **degrade-not-fail** and never changes job status (same posture as
  `extraction_metadata.json` / `math_verification.json` / `guide_lint.json`);
  auto-split stays deferred.
- **Scope guard — NO change to:** any backend/frontend/pipeline file, tests,
  fixtures, dependencies, extraction/OCR heuristics, artifact schema, prompts,
  provider settings, `/api/jobs/llm` request fields, Ask/retrieval, or the
  PDF/Chromium render pipeline. No Mistral dependency or API call. Updated only
  `docs/HYBRID_OCR_DESIGN.md` (new), `docs/CURRENT_TASK.md`,
  `docs/NEXT_CHAT_HANDOFF.md`, `docs/DECISIONS.md`.
- **Validation (docs-only):** `git diff --check` ✓ · `git diff --name-only` shows
  docs only ✓. No build/smoke required (no code touched).

---

## Slice 28 — JobDetails guide-lint UI tab (DONE — committed on trunk as `f3bb0ad`).

- **Purpose:** surface the per-job `guide_lint.json` artifact (Slice 27) in the
  JobDetails drawer as a read-only, advisory panel, closing the
  visibility-parity gap with the math-verification UI (Slice 22). Frontend/UI
  only — **no** backend, pipeline, or artifact-schema change.
- **Pattern:** mirrors the Slice 22 math-verification UI architecture exactly:
  - `frontend/src/guideLintArtifact.js` — pure, React-free normalizer
    (`summarizeGuideLintArtifact`, `safeLintExcerpt`, `GUIDE_LINT_ARTIFACT`).
  - `frontend/src/components/GuideLintPanel.jsx` — drawer panel component.
  - `frontend/scripts/verify-guide-lint.mjs` — plain-node helper harness, wired
    into the `test` chain + a `test:guide-lint` script in `frontend/package.json`.
- **UI placement:** new **"Guide Lint"** tab in the JobDetails drawer tab bar
  (`RecentJobsPanel.jsx`), placed immediately after **Verification**, icon
  `FileCheck2`. Available for any job (not gated on `canEdit`), mirroring the
  Verification tab; the panel itself renders a calm "not available" state for
  jobs without the artifact.
- **Lazy fetch:** `GuideLintPanel` fetches `guide_lint.json` via the existing
  `getJobArtifact(jobId, "guide_lint.json")` client helper in a `useEffect`. The
  panel is only mounted when `drawerTab === "guide-lint"`, so the request fires
  only when the tab is opened (and re-fires if `jobId` changes).
- **States handled:** loading · completed (status chip by worst severity, source
  `clean.md`, summary tiles total/errors/warnings/info, top findings sorted
  error→warning→info with severity tag, rule, message, line) · skipped (safe
  message) · missing 404 ("No guide-lint artifact is available for this job") ·
  malformed / wrong kind ("could not be read") · fetch/network error (safe
  generic message). Copy stays explicitly advisory ("checks structure,
  formatting, and math-render risk — not whether the content is correct").
- **Compact view:** findings capped at `GUIDE_LINT_DISPLAY_LIMIT` (8) with a
  "N additional findings hidden" note; excerpts whitespace-collapsed/truncated;
  no `dangerouslySetInnerHTML`; no raw URLs/paths/secrets surfaced.
- **CSS:** reuses the existing compact `sg-mathv-claim` row layout; added two
  severity-tint rules (`.sg-mathv-claim.error`, `.sg-mathv-claim.warning`) in
  `design-system.css` alongside the math `.mismatch`/`.unparseable` tints.
- **Scope guard — NO change to:** backend, pipeline, artifact schema, generic
  artifact lists, Exports bundles, prompts, provider/model behavior,
  `/api/jobs/llm` request fields, OCR/extraction, Ask/retrieval,
  LanceDB/embeddings, or the PDF/Chromium render pipeline. No rerun/recompute
  button; no job mutation.
- **Validation:** `npm --prefix frontend run build` ✓ · `npm --prefix frontend
  run test` (incl. new `verify-guide-lint.mjs`, 22 checks) ✓ · `python -m
  compileall api pipeline test_scripts` ✓ · math_verifier / guide_lint /
  eval_harness / page_anchor_reachability / source_page_citations /
  extraction_metadata / ask_retrieval_relevance / ask_lexical_hygiene /
  guide_lint_artifact test scripts ✓ · `run_eval.py --offline --all` ✓ ·
  `git diff --check` ✓. `smoke_release.py` requires a live server at
  `localhost:8000` (end-to-end Docker check) and was not run in the host-only
  environment — frontend-only changes, backend unchanged.

---

## Slice 27 — Persist guide_lint.json advisory artifact (DONE — committed on trunk as `0d73f24`).

- **Purpose:** close the correctness-visibility asymmetry where math verification
  is persisted as a per-job artifact (Slice 21) but the deterministic guide-lint
  core (Slice 19) was still only a test/CLI tool. This slice persists a per-job
  `guide_lint.json` advisory artifact; **no UI** (JobDetails surfacing is a later
  slice, mirroring Slice 22).
- **Pattern:** mirrors the Slice 21 `math_verification.json` contract exactly —
  advisory-only, **never** fails a job, **never** changes job status, **never**
  blocks the render, downloadable by exact artifact name, and **not** added to
  generic artifact lists / Exports / Library / JobDetails this slice.
- **Where lint runs:** `pipeline/run_markdown_job.py::run_raw_markdown_pipeline`,
  in the new helper `_write_guide_lint(job)`, called immediately after
  `_write_math_verification(job)` — i.e. after the sanitized `clean.md` is saved
  and `validation.json` is written, before the Chromium render. Both job entry
  paths (`run_llm_job` and the paste/markdown paths) flow through this shared
  pipeline, so the artifact is produced for every successfully-sanitized job.
- **Artifact shape (completed):**
  ```json
  {"version": 1, "kind": "guide_lint", "status": "completed",
   "source": "clean.md", "report": { …GuideLintReport.to_dict()… }}
  ```
  **Degraded (lint crash):**
  ```json
  {"version": 1, "kind": "guide_lint", "status": "skipped",
   "reason": "lint_error", "safe_message": "Guide lint could not be completed."}
  ```
- **expected_sections / available_source_pages — NOT passed (documented):**
  - `expected_sections`: the job manifest only stores canonical section-toggle
    keys (e.g. `key_concepts`), not the heading text the LLM actually emits, so
    feeding them to the heading matcher would yield unreliable / noisy
    `missing_section` findings. Wiring real expected headings is deferred.
  - `available_source_pages`: source page anchors are not reliably available at
    this point without invasive source-text plumbing (and are absent for paste /
    Markdown-upload jobs), so the optional page-citation check stays disabled to
    keep the slice non-invasive. Lint still runs all other rules + the existing
    Node/KaTeX render bridge (which itself degrades to an info finding when
    unavailable — it never crashes the helper).
- **Degrade-not-fail:** any exception from the lint core (or the read) is caught;
  a small `skipped` artifact is written instead, and **only the exception type
  name** is logged to stderr (`Guide lint skipped (X); job continues.`) — never
  the message/args, traceback, paths, or guide content. Writing the degraded
  artifact is itself wrapped so it can never raise.
- **Plumbing:** new `Job.guide_lint_json` property (`pipeline/job_manager.py`,
  `<job>/guide_lint.json`, sibling of `math_verification.json`); exact-name
  special-case in `api/server.py::_artifact_path` returning
  `(job.guide_lint_json, "application/json")` — kept OUT of `ARTIFACTS`, so it
  never appears in `_artifact_urls` / `_artifact_details` (no generic list row)
  and is reached only by the fixed filename `guide_lint.json` (no traversal).
- **Tests:** new `test_scripts/test_guide_lint_artifact.py` (26 host checks, +1
  route check that runs only in Docker where FastAPI is importable): completed
  shape, structural-findings recorded without failing the job, zero-findings
  total 0, lint-crash → safe `skipped` (no traceback / no exc message),
  secret-name + key-like value scan on both completed and skipped artifacts,
  `validation.json` + `math_verification.json` left byte-identical, guide_lint
  report shape/version, and (Docker-only) the download route resolving the exact
  name while staying out of `ARTIFACTS` / urls / details and still 404-ing a
  traversal name.
- **Untouched (verified):** no frontend/UI/JobDetails change; no generic artifact
  list / Exports ZIP inclusion; no `validation.json` / `math_verification.json` /
  `extraction_metadata.json` schema change; no prompt / provider / model change;
  no `/api/jobs/llm` request-field change; no OCR/extraction change; no
  Ask/retrieval/LanceDB/embeddings change; no PDF/Chromium render change; no
  generation gating/failing on lint.

---

## Slice 25B — Ask lexical retrieval hygiene (DONE — committed `ae44a85`, trunk HEAD).

- **Purpose:** improve the existing deterministic local-only lexical (tf-idf) Ask
  retrieval with cheap, explainable changes, then prove the effect against the
  Slice 25A baseline. No embeddings / LanceDB / vector search / reranker /
  cross-encoder / new ML dependency — lexical hygiene only.
- **Root cause (from 25A):** the index and query both tokenised with a bare
  `[a-z0-9]{2,}` lowercaser and **no stopword/plural hygiene**. Common function
  words ("the", "it", "on") flooded scoring (idf≈1 but high tf), so unrelated
  sections out-scored the right one on a paraphrased query.
- **Change — new shared module `pipeline/ask_lexical.py`:**
  - `lexical_terms(text)` → normalised term-frequency dict, used by **both** the
    index build and the query scorer so they can never drift apart.
  - `STOPWORDS` — small built-in English function-word set (articles, pronouns,
    auxiliaries, prepositions, conjunctions, common question/determiner words).
    Deliberately excludes domain vocabulary; tokens like `l2`, `f1`, `sigmoid`,
    `dropout` survive intact.
  - `normalize_token` — conservative **regular `+s` plural** folding only
    (single trailing `-s`, guarded against doubled `ss` and short tokens), so
    `example`/`examples` and `weight`/`weights` fold to the same stem. No `-es`
    rule (would break singular/plural symmetry) and **no verb-tense stemming**
    (`-ing`/`-ed`) — that risks mangling tokens like `string`/`based` for little
    gain.
- **Wiring:** `ask_context._term_freqs` and `ask_sessions._terms` now both
  delegate to `lexical_terms` (the old per-module `_TERM_RE` and the now-unused
  `Counter` import in `ask_sessions` were removed). Segmentation is unchanged;
  only stopword filtering + plural folding are new.
- **Index/cache compatibility:** the index *shape* is unchanged (still
  `terms` + `doc_freq`), but their *contents* are now normalised. `INDEX_VERSION`
  bumped `1 → 2` so any existing v1 cache is treated as stale by `_cache_valid`
  and **rebuilt automatically** on the next `prepare_context` — no user action,
  no manual cache deletion, and no chance of mixing old un-normalised index terms
  with new query terms. See `DECISIONS.md` → "Ask index version bump on lexical-
  hygiene change".
- **Baseline before → after (k=5, `test_ask_retrieval_relevance.py`):**
  - Blocking cases **unchanged**: `hit_rate@5 = 1.0`, `mrr = 0.9`, `missing = []`
    (4 keyword guide queries rank #1; the source-page query ranks #2).
  - Paraphrase **known-weakness** case ("model memorizes training data…"):
    **rank 5 → rank 1** on this fixture. Stopword removal killed the function-word
    noise so the residual content-word overlap (`model`, `new`) ranks the
    Overfitting section first.
- **Honest remaining weakness:** this is still *lexical overlap*, not semantics.
  The paraphrase improved only because it shares a couple of content words with
  the target; a paraphrase with **zero** shared content words would still miss.
  The case is therefore kept `known_weakness: true` (non-blocking) and embedding/
  semantic retrieval remains future work. The harness `retrieval`/`version`
  labels and the fixture `note` were updated to record this.
- **Tests:** new `test_scripts/test_ask_lexical_hygiene.py` (34 checks) locks in
  stopword filtering, plural folding, technical-token survival, the
  index==query tokeniser invariant, a clean `doc_freq`/chunk-terms (no stopword
  leak), the four blocking keyword cases staying #1, and the paraphrase reaching
  #1. Existing Ask tests (`test_ask_context_prepare` 28, `test_ask_context_inventory`
  11, `test_ask_local_chat` 45) still pass.
- **Scope guardrails (verified):** no UI/frontend change; no provider/model/
  local-server/LLM call; no LanceDB/embeddings/vector/reranker/cross-encoder/new
  ML dependency; no `/api/ask/*` or other route/field change; no Ask
  chat/session API behaviour change beyond retrieval ranking; no prompt change;
  no OCR/extraction change; no citation-directive change; no artifact-schema
  (`validation.json` / `math_verification.json` / `extraction_metadata.json`)
  change; no PDF/Chromium render-pipeline change. No secrets/tokens/paths
  exposed (fixture is synthetic ML study text; redaction helpers untouched).

---

## Slice 25A — Ask retrieval relevance harness + lexical baseline (DONE — uncommitted).

- **Purpose:** establish an offline, deterministic baseline of the *current*
  local-only lexical (tf-idf) Ask retrieval **before** any LanceDB / embeddings /
  reranking / context-compression work. Measurement only — no retrieval change.
- **Retrieval boundary used (real code, no server/model/provider/Docker):**
  - `pipeline/ask_context.py::prepare_context(...)` builds the deterministic
    chunk + lexical index from a job's `clean.md` (guide) + `extracted.txt`
    (source); `load_index(...)` reads it back.
  - `pipeline/ask_sessions.py::_score_chunks(...)` / `retrieve_chunks(...)` are
    the exact functions Ask uses at chat time to rank + budget-select chunks.
  - The harness writes the fixture into a **temp** job dir (`Job(id, root=tmp)`),
    never touching real `jobs/`, `library/`, or `config/`.
- **Harness:** `test_scripts/test_ask_retrieval_relevance.py` (offline, no keys,
  no LLM call). Fixtures under `test_scripts/fixtures/ask_retrieval/`:
  `guide.md` (4 topic sections), `source.txt` (4 `## Page N` source slides),
  `queries.json` (6 query→expected-target cases, one flagged `known_weakness`).
- **Metrics (JSON-serializable, deterministic):** per-case `rank`, `hit_at_k`,
  `reciprocal_rank`, and the budgeted public-retrieval result; aggregate
  `hit_rate_at_k`, `mrr`, and a `missing` list over blocking cases. Known-weakness
  cases are reported but **non-blocking**. Run with `--json` for the full report.
- **Baseline result (k=5):** `hit_rate@5 = 1.0`, `mrr = 0.9`, `missing = []` over
  the 5 blocking cases (4 keyword guide queries rank #1; the source-page query
  ranks #2). The paraphrase **known-weakness** case ("model memorizes training
  data…", with no shared keywords) is the honest weakness: the correct section
  drops to **rank 5** (reciprocal rank 0.2), behind three unrelated sections,
  because lexical scoring has no stopword removal or semantic match. Recorded
  as-is (not forced), motivating future embedding/semantic retrieval.
- **Scope guardrails (verified):** Ask runtime/chat/session/prompt behavior
  unchanged; no provider/model/local-server call; no LanceDB/embeddings/vector
  DB/reranking/new ML dependency; no frontend/UI; no `/api/ask/*` or
  `/api/jobs/llm` route/field change; no OCR/extraction, citation-directive, or
  artifact-schema (`validation.json` / `math_verification.json` /
  `extraction_metadata.json`) change; no PDF/Chromium render-pipeline change. No
  secrets/tokens/paths exposed (fixture is synthetic ML study text).

---

## Slice 24A — Persist per-page extraction metadata artifact (DONE — uncommitted).

- **Purpose:** persist lightweight per-page extraction metadata for uploaded PDF
  attachments as a per-job artifact, creating measurement/audit groundwork for
  later hybrid OCR work without changing extraction behavior.
- **Artifact:** `extraction_metadata.json` is written as a sibling job artifact
  only when PDF attachment metadata is available, with shape
  `{version: 1, kind: "extraction_metadata", status: "completed", sources: [...]}`.
  Each PDF source records `filename`, `content_type`, `page_count`, source
  `warnings`, and page records with `page`, `method`, `text_chars`,
  `word_count`, `has_page_anchor`, and `warnings`.
- **Skipped shape:** if metadata collection/writing cannot be completed safely,
  the helper writes `{version: 1, kind: "extraction_metadata", status: "skipped",
  reason: "metadata_unavailable", safe_message: ...}` on a best-effort basis.
  Failures never fail job creation, never change job status, and logs include
  only the exception type.
- **Collection point:** `pipeline/extract.py::_extract_pdf(...)` now records page
  metadata while it makes the existing embedded-text vs OCR decision. The text
  blocks, `## Page N` anchors, mode calculation, warnings, OCR availability
  checks, and page-selection behavior are otherwise unchanged.
- **Pipeline/API integration:** `pipeline/run_llm_job.py::_attach_sources(...)`
  writes PDF metadata after attachment extraction and before the LLM call.
  `pipeline/job_manager.py` adds `Job.extraction_metadata_json`.
  `api/server.py::_artifact_path(...)` exact-special-cases
  `extraction_metadata.json`, so it is downloadable at
  `GET /api/jobs/{id}/artifacts/extraction_metadata.json`.
- **Not listed:** `extraction_metadata.json` is intentionally not added to
  `ARTIFACTS`, export bundle selectors, `_artifact_urls(...)`, or
  `_artifact_details(...)`, so generic UI artifact lists / JobDetails remain
  unchanged in this slice.
- **Attachment coverage:** PDFs only. Non-PDF attachments are omitted from this
  artifact.
- **Tests:** added `test_scripts/test_extraction_metadata.py` for completed and
  skipped artifact shape, no secret-like leakage, no generic artifact-list
  exposure, and PDF attachment integration when PyMuPDF is available.
- **Scope guardrails:** no frontend/UI, prompt, provider, OCR heuristic,
  page-selection, `/api/jobs/llm` request-field, `validation.json`,
  `math_verification.json`, Ask/retrieval, VLM, or PDF/Chromium render-pipeline
  changes.

---

## Slice 23B — Source page-citation directive + checks (DONE — uncommitted).

- **Purpose:** add model-facing guidance that uses the Slice 23A proof: when
  source text contains extraction-style `## Page N` anchors, generated guides
  should cite source pages compactly and deterministically measurable offline.
- **Prompt change:** `pipeline/orchestrator.py` now defines
  `SOURCE_PAGE_CITATION_DIRECTIVE` and conditionally inserts it when
  `source_text` contains `## Page N` anchors. Exact directive:
  "When the source text contains '## Page N' anchors, cite the source page for
  factual claims, examples, formulas, and definitions where possible. Use compact
  citations like (p. 3) or (pp. 3-5), and cite only pages that appear as source
  anchors. Do not invent page citations."
- **Insertion point / invariants:** both `build_messages(...)` and
  `build_messages_for_preset(...)` insert the conditional citation block after
  axis/include-section guidance and before `MARKDOWN_MATH_SYSTEM`; preset system
  prompts still come first; `MARKDOWN_MATH_SYSTEM` remains the final block in
  both paths. With no page anchors and no other options, the default system
  prompt remains `MARKDOWN_MATH_SYSTEM`; the preset no-anchor baseline remains
  `{preset_prompt}\n\n{MARKDOWN_MATH_SYSTEM}`.
- **Format alignment:** the existing optional `slide_page_references` fragment was
  aligned from the older `(page N)` policy to compact `(p. N)` / `(pp. N-M)` so it
  does not conflict with the new source-driven directive.
- **Advisory checker:** `pipeline/guide_lint.py` now has optional
  `available_source_pages` support plus `extract_source_page_anchors(...)`. When
  offline tooling supplies pages, it detects conservative citations such as
  `p. 3`, `pp. 3-5`, `page 3`, and warns with `page_citation_range` if cited
  pages are unavailable or no anchors were supplied. It is advisory only and is
  not wired into live jobs, artifacts, UI, `validation.json`, or
  `math_verification.json`.
- **Eval wiring:** `test_scripts/eval/score_guide.py` accepts optional golden-spec
  `source_page_anchors` and passes them into the linter. The sample golden spec
  and fixtures now include `## Page 1` / `## Page 2` source anchors and valid
  compact citations so offline mode measures citation plausibility.
- **Tests added/updated:** new `test_scripts/test_source_page_citations.py`
  covers conditional directive insertion, no-anchor baselines, preset/non-preset
  consistency, and math-block-last ordering. Updated
  `test_scripts/test_page_anchor_reachability.py`,
  `test_scripts/test_page_reference_format.py`,
  `test_scripts/test_guide_lint.py`, and `test_scripts/test_eval_harness.py`.
- **Scope guardrails:** no frontend/UI, JobDetails, backend route, provider,
  provider setting, `/api/jobs/llm` request-field, OCR/extraction,
  retrieval/LanceDB/Ask, `validation.json`, `math_verification.json`,
  guide-lint job artifact, or render/PDF pipeline changes.

---

## Slice 23A — Verify source page-anchor reachability (DONE — uncommitted).

- **Purpose:** measurement/proof slice before citation behavior changes. Prove
  whether extraction-style source anchors such as `## Page N` survive the
  ingestion/input/prompt path and reach model-facing prompt assembly.
- **Inspected path:** `pipeline/extract.py` emits PDF anchors as `## Page N`;
  `pipeline/run_llm_job.py::_attach_sources(...)` copies/extracts attachments,
  appends extracted text under `## Attached Sources`, and passes the augmented
  source into `generate_study_guide(...)`; `pipeline/orchestrator.py` assembles
  model messages with `build_messages(...)` (template path) or
  `build_messages_for_preset(...)` (preset path); `pipeline/prompt_loader.py`
  injects `{source}` into the user template. The exact model-facing boundary is
  the `messages` list passed to `generate_chat_completion(messages, config)`.
- **Result:** PASS. `## Page 1`, `## Page 2`, etc. currently reach the
  model-facing `user` message. Template prompts preserve anchors inside the
  rendered source block; preset prompts use `source_text` as the user message
  verbatim; attachment-augmented source preserves anchors after `_attach_sources`.
- **Focused proof added:** `test_scripts/test_page_anchor_reachability.py` plus
  fixture `test_scripts/fixtures/page_anchor_reachability/extracted_pages.txt`.
  The test covers simple two-anchor source text, anchors surrounded by normal
  lecture text, attachment augmentation into prompt assembly, preset prompt
  assembly, and explicitly verifies no default citation directive/output citation
  assumption is introduced.
- **Behavior changes:** none. Tests/docs only. No citation directive change, no
  generated-guide instruction change, no citation lint/eval rule, no frontend/UI,
  provider, OCR, extraction, retrieval, `validation.json`, `math_verification.json`,
  or `/api/jobs/llm` request-field change.
- **Slice 23B implication:** citation/page-reference prompt, lint, and eval work
  can proceed from the premise that extraction-produced `## Page N` anchors are
  already available to the model input. Slice 23B still needs to add citation
  behavior explicitly; Slice 23A does not assume rendered output citations.

---

## Slice 22 — JobDetails math verification artifact UI (DONE — uncommitted).

- **Purpose:** add the first read-only JobDetails surface for the Slice 21
  per-job `math_verification.json` artifact without adding it to the generic
  artifact grid/list.
- **Scope guardrails:** frontend read-only UI only. No backend job behavior, no
  pipeline behavior, no prompt/provider changes, no `/api/jobs/llm` request-field
  changes, no `validation.json` schema change, no guide-lint integration, no
  artifact writes, no rerun button, and no raw HTML/`dangerouslySetInnerHTML`.
- **UI placement:** `JobDetailsDrawer` now has a `Verification` tab. Opening that
  tab mounts `MathVerificationPanel`, which fetches
  `GET /api/jobs/{id}/artifacts/math_verification.json` on demand. The existing
  `Artifacts` section remains unchanged and still does not list
  `math_verification.json`.
- **Frontend files:** `frontend/src/api/client.js` adds a bounded JSON artifact
  reader; `frontend/src/mathVerification.js` contains pure artifact
  classification/bounding helpers; `frontend/src/components/MathVerificationPanel.jsx`
  renders the read-only panel; `RecentJobsPanel.jsx` adds the tab mount;
  `design-system.css` adds compact semantic claim-row styles; `frontend/package.json`
  chains the new helper harness.
- **States handled:** completed artifacts show `report.summary` total / ok /
  mismatch / unparseable and a bounded, compact claim list prioritizing mismatch
  and unparseable claims; skipped artifacts show the safe skipped message; 404
  older jobs show "not available"; unexpected shapes and invalid JSON show
  malformed-artifact messaging; network/fetch failures show fetch-error
  messaging.
- **Validation:** `npm --prefix frontend run build` green; `npm --prefix frontend
  run test` green (now includes the math verification helper harness);
  `node frontend/scripts/verify-math-verification.mjs` green; `python -m
  compileall api pipeline test_scripts` green; `python
  test_scripts/test_math_verifier.py` → 74/74; `python
  test_scripts/test_guide_lint.py` → 64/64; `python
  test_scripts/test_eval_harness.py` → 59/59; `python
  test_scripts/eval/run_eval.py --offline --all` → 3 guides scored; `git diff
  --check` clean; `python test_scripts/smoke_release.py` → 29 passed / 0 failed
  / 0 skipped.

---

## Slice 20 — Eval harness Phase 1: deterministic scoring framework + golden specs (DONE — reviewed + committed).

- **Purpose:** third **correctness / measurement** slice. Build the first
  **deterministic evaluation harness** for guide quality — the *measurement spine*
  that lets us score guide outputs using the pure correctness modules from Slice 18
  (math verifier) and Slice 19 (guide lint) **before** we optimize prompts, OCR,
  retrieval, or styles. This slice **measures**, it does not improve generation.
- **Scope guardrails honored:** **no** generation-prompt change, **no** provider
  behavior change, **no** `/api/jobs/llm` request-field change, **no** Builder/
  JobDetails UI change, **no** job-artifact integration of math/lint, **no** writes
  to live `jobs/`/`library/`/`config/` (offline never touches the API; the optional
  live mode only POSTs to the existing no-provider `/api/jobs/paste`). **No**
  LLM-judge, **no** embeddings/LanceDB, **no** OCR/retrieval/citation changes. **No
  new dependency** — JSON specs (stdlib), reusing Slice 18/19 modules.
- **New area — `test_scripts/eval/`:**
  - `score_guide.py` — pure, importable scoring core. `build_result(spec,
    guide_text, *, guide_path, mode, artifacts, run_katex) -> dict` plus the
    per-metric scorers `score_concepts`, `score_must_not_claim`, `score_math`
    (reuses `pipeline.math_verifier.verify_math_claims`), `score_lint` (reuses
    `pipeline.guide_lint.lint_guide_markdown`, KaTeX **off** by default for fast
    offline runs), `score_artifacts`, and `compute_overall`. Spec validation via
    `validate_spec` / `SpecError`.
  - `run_eval.py` — CLI: `--offline` (required; no keys/Docker/LLM), `--all`
    (every golden spec × its `offline_guides`), `--live` (optional; submits the
    spec's `source_path` to `/api/jobs/paste`, fetches `clean.md`, scores it +
    probes artifact presence; times out cleanly, records only the API **host**,
    never the full URL). Writes a JSON result + appends `summary.csv`; **scans
    every result for credential-looking field names/values and blocks the write
    on a suspected secret**.
  - `golden/sample.json` + `golden/README.md`; `fixtures/` (`sample_source.md`,
    `sample_good_guide.md`, `sample_bad_math_guide.md`,
    `sample_bad_structure_guide.md`) + `fixtures/README.md`; `results/README.md`
    (generated `*.json`/`*.csv` git-ignored). Top-level `README.md`.
- **Spec format — JSON (not YAML):** stdlib-only, so offline scoring needs no
  extra dependency and runs identically on host and in the non-root Docker image
  (same dependency-free stance as Slice 18 declining SymPy). A `.yaml`/`.yml`
  loader is used only if PyYAML is importable; committed specs stay `.json`.
  Fields: `id` (required), `title`, `source_kind`, `source_path` (required for
  `--live`), `expected_sections`, `required_concepts`, `must_not_claim`,
  `known_numbers` (advisory/reserved this slice), `offline_guides`.
- **Scoring metrics (all `[0,1]`, higher better):** `concepts` = found/total by
  normalized substring match; `must_not_claim` = (total−violations)/total; `math`
  = `(ok + 0.75·unparseable)/total` (mismatches earn **no** credit, unparseable
  earns partial — never fails on unparseable, never on zero claims); `lint` =
  `clamp(1 − (0.20·errors + 0.05·warnings))` (info ignored); `artifacts` =
  present/expected (live only; `null`/not-applicable offline); `overall` =
  weighted mean (`.30/.25/.20/.15/.10`) **renormalized** over non-null components.
- **Regression comparison:** keyed on `(spec_id, mode, guide)` — a result is
  compared to the most recent prior result for *that same guide* (never a
  different guide that shares the spec), reporting previous/current overall, the
  delta, and per-metric deltas. **Non-blocking** this slice. Result filenames are
  guide-keyed (`<spec>__<mode>__<guide>__<run_id>.json`) with a collision counter.
- **Result shape:** `{version, run_id, mode, spec_id, spec_title, guide_path,
  scores{overall,concepts,math,lint,must_not_claim,artifacts}, details{
  missing_concepts, must_not_claim_violations, math_summary, lint_summary,
  lint_top_findings, artifacts}, regression?}`.
- **Tests / fixtures:** `test_scripts/test_eval_harness.py` (plain-Python
  assertion style) — **59/59 PASS**. Covers valid/invalid spec loading, concept
  matching + normalization, must-not-claim detection, math + lint integration on
  fixtures, scoring clean / bad-math / bad-structure guides + ordering, artifact
  scoring, overall renormalization, the JSON result shape, previous-run comparison
  (incl. different-guide isolation), the `--all` CLI, and the no-secret guarantee
  (clean result clean; planted `sk-…` value blocks the write; `api_key` field name
  caught).
- **Validation:** `npm --prefix frontend run build`; `npm --prefix frontend run
  test`; `python -m compileall api pipeline test_scripts`; `python
  test_scripts/test_math_verifier.py` → 74/74; `python test_scripts/test_guide_lint.py`
  → 64/64; `python test_scripts/test_eval_harness.py` → 59/59; `python
  test_scripts/eval/run_eval.py --offline --all` → 3 guides scored; `git diff
  --check` clean — **all green.** `python test_scripts/smoke_release.py` → 26
  passed / 2 failed / 0 skipped; the 2 failures (LLM attachment + outline flows)
  are **environmental, not a regression** — the host hit its thread/process limit
  so Chromium could not fork to render PDFs (`pthread_create: Resource temporarily
  unavailable (11)`; confirmed by a direct paste probe returning "PDF rendering
  failed: Chromium failed to render the PDF"). Slice 20 adds **zero**
  server/pipeline/frontend code, so it cannot affect `/api/jobs/llm` or PDF
  rendering. The optional live eval mode hit the same host PDF fork limit and
  failed cleanly through its graceful error path — exactly as designed.
- **Status:** **DONE — reviewed + committed.** Approval condition was one final
  smoke retry after freeing host resources; the environmental Chromium fork limit
  was traced to the app container's cgroup `PidsLimit=256` being saturated by
  ~179 zombie/`<defunct>` Chromium children (uid 10001) from earlier failed
  renders. Resolved by restarting the container (no runtime `jobs/`/`library/`/
  `config/` data deleted); smoke retried after the restart. Slice 20 adds **zero**
  server/pipeline/frontend code, so it cannot affect `/api/jobs/llm` or PDF
  rendering regardless of the smoke outcome.
  Next (separate, designed phase): eval Phase 2 may add an LLM-judge layer and/or
  a curated golden dataset, or we begin surfacing the verifier + linter as a
  job-stage advisory report — none of which start without their own slice.

---

## Slice 19 — Deterministic guide-lint core: pure advisory module + fixtures (DONE — reviewed + committed).

- **Purpose:** second **correctness / measurement** slice. Add a deterministic,
  **advisory-only** linter that scans generated guide Markdown for *structural and
  rendering-risk* issues, producing a JSON-serializable findings report. **Pure
  core only** — it never mutates input, never fails generation, and is wired into
  nothing.
- **Scope guardrails honored:** **no** frontend change, **no** API change, **no**
  job-pipeline integration, **no** artifact writing, **no** prompt change, **no**
  render/OCR/math-sanitizer rewrite. `pipeline/math_validator.py` (KaTeX render
  validation) is **reused, not modified**; `pipeline/math_verifier.py` (Slice 18)
  is **untouched**. No new dependency.
- **New file — `pipeline/guide_lint.py`:**
  - Public API: `lint_guide_markdown(markdown, *, source_name=None,
    expected_sections=None, run_katex=True) -> GuideLintReport`. Dataclasses
    `LintFinding` / `GuideLintReport` with `to_dict()` / `to_json()`; report shape
    = `{version, source_name, summary{total,error,warning,info}, findings[...]}`,
    each finding `{id, rule, severity, line, message, excerpt}`.
  - **Rules implemented:**
    1. `empty_heading` (warning) — heading with no body before the next heading;
       whitespace-only counts as empty; a parent heading whose body lives under a
       deeper child heading is **not** flagged; a heading is not flagged when it
       has a paragraph/list/table/math block/image/code block under it.
    2. broken-table family (warning, conservative — never `error`):
       `separator_without_header`, `header_separator_mismatch` (header vs separator
       column count), `malformed_separator` (header followed by an invalid
       separator-candidate row), `body_row_mismatch` (body row column count).
    3. `unbalanced_math` — unbalanced `$$…$$`/`\(…\)`/`\[…\]` (**error**) and
       unbalanced single `$` (**warning**, since it is ambiguous with unescaped
       currency). Escaped `\$` is ignored.
    4. `katex_render` (error) / `katex_skipped` (info) — **reuses** the existing
       Node/KaTeX bridge (`scripts/validate_math.js` via
       `pipeline.math_validator.validate`) by writing the Markdown to a transient
       temp file (never a job artifact) and reading the result. If Node/KaTeX is
       unavailable or the subprocess raises, it degrades to a single `katex_skipped`
       info finding — it never crashes linting and never changes math-validation
       behavior. Verified live: node + katex present → invalid `$\frac{1}$` yields
       a real `katex_render` error; valid math yields nothing.
    5. `missing_section` (warning) — when `expected_sections` is provided, each
       entry is matched against headings by normalized text (lowercase, punctuation
       → space, collapsed spaces) with equality or substring fallback (len ≥ 3).
       Order is **not** enforced this slice.
  - **Markdown safety:** fenced code blocks (``` / ~~~, marker-tracked) are excluded
    from heading/table/math checks; inline code spans are excluded from math checks;
    input is never mutated; no `dangerouslySetInnerHTML`, no HTML rendering.
  - **Bounds:** text ≤ 200k chars, ≤ 2000 findings, KaTeX subprocess timeout 30s,
    excerpts ≤ 160 chars.
  - **Optional CLI:** `python -m pipeline.guide_lint <file>` prints the JSON report
    (stdout only — no file writes).
- **Intentionally unsupported / deferred:** setext (underline) headings (ATX only),
  GFM cell-alignment correctness, escaped-pipe cell counting, table content/semantic
  checks, link/image-target validation, spelling/readability, and any
  job/`validation.json`/UI integration. All deferred to later designed slices.
- **Tests / fixtures:** `test_scripts/test_guide_lint.py` (plain-Python assertion
  style, run `python test_scripts/test_guide_lint.py`) — **64/64 PASS**. Covers a
  clean guide (0 findings), empty headings (same-level/whitespace/nested/parent +
  each body type), broken tables (each rule + valid table not flagged), math
  delimiters (balanced inline/display + unbalanced `$`/`$$`/`\(`/`\[`), fenced-code
  safety (broken table / unbalanced math / heading-like text inside a fence all
  ignored), expected sections (all-present / missing-one / normalization / `None`),
  KaTeX (valid passes, invalid → render finding or skip, disabled, no-crash), input
  immutability, non-string/empty input, and the JSON report shape. Five fixtures
  under `test_scripts/fixtures/guide_lint/` (`clean_guide.md`, `empty_headings.md`,
  `broken_tables.md`, `math_delimiters.md`, `code_safety.md`).
- **Validation (all green):** `npm --prefix frontend run build`; `npm --prefix
  frontend run test` (full maintained chain); `python -m compileall api pipeline`;
  `python test_scripts/test_math_verifier.py` → 74/74; `python
  test_scripts/test_guide_lint.py` → 64/64; `git diff --check` clean; `python
  test_scripts/smoke_release.py` → **28 passed / 0 failed / 0 skipped** (live app
  unchanged — guide-lint is not imported by the server).
- **Status:** **DONE — reviewed + committed** on `chrome-renderer-v1`. **Pure
  advisory guide-lint core only:** no job integration, no artifact, no API, no
  `validation.json`, no prompt, no frontend/UI. Next (separate, designed slice):
  the **eval-harness Phase 1** (deterministic scoring framework over the Slice 18
  verifier + Slice 19 linter), then decide whether/how to surface the verifier +
  linter (job-stage advisory report / `validation.json` / JobDetails) — generation
  must never fail on either.

---

## Slice 18 — Deterministic math verification core: pure module + fixtures (DONE — reviewed + committed).

- **Purpose:** first **correctness / measurement** slice after the reskin/hygiene
  phase. Add a deterministic, safe verifier that inspects generated guide
  Markdown/text and checks **simple numeric math claims** (`2 + 3 = 5`, `sqrt(16)
  = 4`, `exp(1.43) / (1 + exp(1.43)) ≈ 0.806`, …), producing a structured report
  with per-claim verdicts `ok` / `mismatch` / `unparseable`. **Pure core only.**
- **Scope guardrails honored:** **no** job-pipeline integration, **no** artifact
  writing, **no** `validation.json` change, **no** API routes, **no** frontend/UI/
  JobDetails change, **no** prompt change, **no** render/OCR/math-sanitizer rewrite.
  `pipeline/math_validator.py` (KaTeX render validation) is **untouched** — this is
  a deliberately separate concept (numeric correctness, not render syntax).
- **New file — `pipeline/math_verifier.py`:**
  - Public API: `verify_math_claims(text, *, source_name=None, tolerance_abs=1e-6,
    tolerance_rel=1e-3) -> MathVerificationReport`. Dataclasses `ClaimResult` /
    `MathVerificationReport` with `to_dict()` / `to_json()`; report shape =
    `{version, source_name, summary{total,ok,mismatch,unparseable}, claims[...]}`.
  - **Extraction (Tier A, line-based):** `expr <rel> number` where `rel` ∈
    `=`, `≈`, `~=`, `→`, `->` (normalized to exact `=` / approx `≈`); chained
    `a = b ≈ c` handled as adjacent pairs. Skips fenced code blocks (``` / ~~~)
    and inline code spans; unwraps `$…$`, `$$…$$`, `\(…\)`, `\[…\]`. A prose
    lead-in is trimmed to the trailing expression **only** when bounded by a
    non-word char, so `x + 2 = 5` stays `unparseable` (never a false `2`).
  - **Normalizer (deliberately limited):** unicode minus `−`→`-`; `×`,`·`,
    `\times`,`\cdot`→`*`; `÷`→`/`; `^`→`**`; `√(…)`/`\sqrt{…}`; `\frac{a}{b}`;
    `\left`/`\right` removal; thousands commas; `π`→`pi`; `e`/`exp`; constants
    `pi`/`e`/`tau`.
  - **Evaluation safety:** stdlib `ast` parse + explicit whitelist walk —
    **no `eval`/`exec`**, no attribute access, no names beyond whitelisted
    constants, no imports/FS/network/process. Allowed funcs: `sqrt, exp, log,
    ln, log10, log2, sin, cos, tan, abs`. Bounds: text ≤ 200k chars, line ≤ 2k,
    expr ≤ 200 chars / ≤ 100 tokens / ≤ 120 AST nodes, `**` exponent ≤ 100 /
    base ≤ 1e6, ≤ 5000 claims. Every verifier exception → `unparseable` (never
    `mismatch`); attribute/dunder/string payloads are rejected unexecuted.
  - **Tolerance:** `ok` if abs diff ≤ `1e-6` OR rel diff ≤ `1e-3`; approximate
    (`≈`) claims additionally allow one unit-in-last-place of the claimed literal
    (chained-rounding slack) — e.g. `0.8057 ≈ 0.806` and the logistic example are
    `ok`, while real near-misses (`1/3 ≈ 0.350`, `2 + 3 ≈ 5.4`) stay `mismatch`.
  - **Optional CLI:** `python -m pipeline.math_verifier <file>` prints the JSON
    report (stdout only — no file writes).
- **Dependency decision:** **none added.** SymPy *is* installed in the host env
  (1.14.0) but is **not** listed in `requirements.txt` and is **not used** — a
  stdlib `ast`+`math` evaluator is safer (explicit whitelist, no parser surprises,
  no hang risk) and keeps the backend dependency set unchanged.
- **Tests / fixtures:** `test_scripts/test_math_verifier.py` (plain-Python
  assertion style, run `python test_scripts/test_math_verifier.py`) — **74/74
  PASS**. Covers good claims, mismatches, unparseable (units/variables/symbolic/
  prose), Markdown safety (fenced + inline code, `$…$`/`\[…\]` wrappers),
  normalization, tolerance/rounding, chained claims, line numbers, safety guards
  (long expr rejected, unknown function rejected, malicious `__import__`/attribute/
  `open` payloads not executed → `unparseable`, pow-blowup + div-by-zero guarded),
  report JSON round-trip, and four fixtures under
  `test_scripts/fixtures/math_verifier/` (`good_claims.md`, `mismatch_claims.md`,
  `unparseable_claims.md`, `code_block.md`).
- **Validation (all green):** `npm --prefix frontend run build`; `npm --prefix
  frontend run test` (full maintained chain); `python -m compileall api pipeline`;
  `python test_scripts/test_math_verifier.py` → 74/74; `git diff --check` clean;
  `python test_scripts/smoke_release.py` → **28 passed / 0 failed / 0 skipped**
  (live app unchanged — verifier is not imported by the server).
- **Pure-core scope (reconfirmed at commit):** Slice 18 is **math-correctness core
  only** — **no** job-pipeline integration, **no** artifact writing, **no**
  `validation.json` field, **no** API route, **no** prompt change, and **no**
  frontend/UI/JobDetails surfacing. The verifier is not imported by `api/server.py`
  or any pipeline stage.
- **Status:** **DONE** — reviewed, approved, and committed.
  Next (separate, designed slice): decide whether/how to integrate the verifier
  (job-stage report / `validation.json` / JobDetails) — generation must never fail
  on it.

---

## Slice 17 — Hygiene checkpoint: dead-file sweep + test-chain repair (DONE — reviewed + committed).

- **Purpose:** hygiene checkpoint after committed Slice 16 (`eaa1263`) and Slice 15
  (`033e7d1`). **Not a feature slice** — no backend/API/pipeline/endpoint/payload
  changes, no render/OCR/math/prompt changes, no LMM/provider changes, no new deps.
  Carry out the dead-code sweep Slice 16 deferred and fix the stale `npm test` chain.
- **Working tree (what this slice changes):**
  - **Deleted (proven-unreachable dead files, via `git rm`):** mockup/legacy
    presentational set — `BrandMark.jsx`, `Chip.jsx`, `ClaudeIcons.jsx`,
    `DesktopMockup.jsx`, `FallbackImage.jsx`, `Field.jsx`, `GlowBackground.jsx`,
    `ImplementationNote.jsx`, `MobileScreenPicker.jsx`, `PasteGenerationPanel.jsx`,
    `PhoneMockup.jsx`, `StatCard.jsx`, `TopBar.jsx`, `data/mockups.js`; the five
    `public/mockups/*.png` assets; and the obsolete `scripts/verify-assets.mjs`
    harness. Zero live imports/usages confirmed before removal.
  - **`frontend/package.json`:** `npm test` was `node scripts/verify-assets.mjs`
    (stale mockup harness). Now chains the maintained harnesses:
    `verify-shortcut-{status,repair,activation,form}` +
    `verify-local-model-{status,command,library}` + `verify-ask-guide` +
    `verify-style-compare`. The old stale-test caveat is now obsolete.
  - **`frontend/src/App.jsx`:** comment updated to drop the stale `GlowBackground`
    mention (component deleted).
  - **`docs/PROJECT_DEEP_CONTEXT_REPORT.md`:** §6 component map + verify-harness
    list updated to remove `GlowBackground`/mockup/`verify-assets` references and
    record the Slice 17 deletions.
- **Validation (all green):** `npm run build`; full `npm test` chain (all 9
  harnesses pass) + the four explicitly-run `test:local-model-{status,command,
  library}` / `test:style-compare`; `python -m compileall api pipeline`;
  `git diff --check` clean. Container already healthy and serving the
  post-deletion build (deleted `/mockups/mobile-home.png` → **404**, SPA root →
  **200**); `smoke_release.py` **28 passed / 0 failed / 0 skipped** (incl. no-key-
  leakage on `/api/options`, `/api/styles`, JobDetails + full paste/upload/LLM/
  attachment/outline/ZIP/folder/style-CRUD/rerender flows).
- **Audit D (semantic CSS / inert utilities):**
  - **Undefined live `sg-*`: 0** — 743 `sg-*` tokens used in JSX, all defined among
    the 773 `.sg-*` selectors. (The dead `Tile`/`sg-tile-*` source from Slice 16's
    note is gone with `ClaudeIcons.jsx`.)
  - **Old-palette/inert Tailwind in live reachable files: only 2 occurrences**, both
    in `RecentJobsPanel.jsx` lines 348/362 (`text-slate-300`/`text-slate-400`) inside
    `PreviewPanel`, which renders **only** in the non-embedded `RecentJobsPanel`
    branch. The sole render site (`HomeShortcuts`) always passes `embedded`; the
    other importers (`Builder`/`Exports`/`Library`) pull only the named exports
    (`JobDetailsDrawer`/`StylePill`/`FolderPill`). So this branch is **unreachable
    dead code** — **intentionally left** (a hygiene slice avoids churning a
    known-dead branch; logged for a future structural pass), not a live leftover.
  - **Dead-file leftovers:** none — no live references to any deleted component.
- **Security quick-scan (no secrets printed):** `/api/options` & `/api/styles` —
  no raw keys (smoke also asserts this); `/api/provider-settings` — only safe DTO
  fields (`configured`, `key_source`, `key_hint` last-4, `base_url_host`), no raw
  key/full URL; `/api/local-model/status` — whitelisted fields only, no token/
  socket/Authorization/absolute host path/executable path/raw argv (the lone
  `.gguf` token is a bare model basename, the documented non-secret identifier).
- **Live walkthrough (functional, API-backed; visual review is operator-owned):**
  all 7 workspaces + Help + JobDetails reachable — Home (`/api/shortcuts`,`/api/jobs`
  200), Builder (`/api/options`,`/api/presets` 200; generation PASS), Library
  (`/api/library`,`/api/library/folders` 200; move/batch PASS), Ask Guide
  (`/api/ask/jobs` 200), Styles (`/api/styles` 200; style CRUD PASS), Models
  (`/api/provider-settings`,`/api/local-model/status` 200), Exports (`/api/exports`
  200; ZIP PASS), Help (static workspace wired in nav + Ask `onOpenHelp`),
  JobDetails (metadata + no-key-leakage PASS).
- **Status:** **DONE** — reviewed, approved, and committed.

---

## Slice 16 — Post-reskin release audit + checkpoint (implemented + verified, awaiting review).

- **Purpose:** release-audit/checkpoint after the GuideForge reskin + UX phase
  (Slices 1–15). **No features, no redesign, no roadmap work.** Verify the app is
  clean, document the reskin phase complete, and make only surgical low-risk
  fixes the audit turns up.
- **Audit A (baseline):** Slice 15 committed (`033e7d1`), working tree started
  clean.
- **Audit B (build/test):** `npm run build` green; `test:local-model-status`,
  `test:local-model-command`, `test:local-model-library`, `test:style-compare`
  all pass; `python -m compileall api pipeline` green; `git diff --check` clean.
- **Audit C (served app):** `docker compose build` + `up -d` green; `/api/health`
  `{"ok":true}`; `/api/options` 200 with only non-secret keys. `smoke_release.py`
  **28 passed / 0 failed / 0 skipped** (incl. the "no key leakage in job details"
  assertion + full paste/upload/LLM/attachment/outline/ZIP/folder/style-CRUD/
  rerender flows). Served container bundle confirmed **fresh** (the `sm:grid-cols-2`
  token removed in this slice is absent from the served JS), not stale host/dev
  output.
- **Audit D (semantic CSS / inert utilities):**
  - Defined `.sg-*` selectors: 773; `sg-*` tokens used: 745. **Undefined in the
    live render path: 0.** The only two unmatched tokens (`sg-tile-`,
    `sg-tile-glow`) come from the dynamic `Tile` export in `ClaudeIcons.jsx`,
    which is **dead** (zero imports/usages) — not in any live path.
  - **Live inert/old-palette leftovers found:** a handful in the JobDetails
    drawer body of `RecentJobsPanel.jsx` (stray `text-sm font-bold text-white`
    headers, `text-slate-*`/`mt-*`/`grid sm:grid-cols-2` on `h3/dt/dd/p/dl/section/
    span`). These were **inert no-ops, not raw UI** — the `.sg-drawer-body`
    base element cascade (Slice 5b/15) already styles `section/h3/dl/dt/dd/p` —
    but they were stripped anyway so the live path carries no leftover palette.
  - **Dead-file/dead-branch leftovers (left in place, reported):** the
    non-embedded `RecentJobsPanel` return branch + its `PreviewPanel` helper
    (lines ~311–393, `bg-navy-900`/`shadow-navy`/`backdrop-blur`/`ember-500`)
    are **unreachable** — the sole caller (`HomeShortcuts`) always passes
    `embedded`. Also dead: `Tile` (ClaudeIcons), `MetaRow` (BuilderWorkspace),
    and the mockup components (`DesktopMockup`, `PhoneMockup`, `BrandMark`,
    `GlowBackground`, `FallbackImage`, `ImplementationNote`, `MobileScreenPicker`,
    `PasteGenerationPanel`, `data/mockups.js`, etc.). Not churned (checkpoint
    slice avoids structural rewrites); recorded for a future dead-code sweep.
  - **Other live workspaces** (Ask/Builder/Home/Library/LocalModels/Styles/Help/
    DesktopDashboard): **zero genuine old-palette tokens.** Remaining matches are
    layout utilities (`flex`/`grid`/`gap-1`) on elements that also carry inline
    styles or `sg-*` classes, or render acceptably inline — cosmetically
    negligible, not raw. Deferred (not worth churn).
- **Audit E (functional):** end-to-end flows validated at the API/data layer via
  `smoke_release.py` (generation start→done, JobDetails metadata, library
  folder/move, Exports ZIP, Styles create/use/delete, rerender, outline order).
  Browser-driven visual walkthrough + screenshots are **operator-owned** (per
  standing instruction); not produced here.
- **Audit F (security):** `/api/options`, `/api/styles`, `/api/provider-settings`,
  `/api/local-model/status` carry **no raw keys/tokens/secrets**; provider DTO
  exposes only `configured`/`key_source`/last-4 `key_hint`/`base_url_host`;
  local-model DTO exposes no token/socket/abs-path/executable/argv/Authorization;
  served JS bundle contains no `.env` secret (and not even the last-4 hint).
- **Fixes made (1 file, frontend-only):** `frontend/src/components/RecentJobsPanel.jsx`
  — stripped inert Tailwind/old-palette className tokens off live drawer-body
  `h3/dt/dd/p/dl/section/span` elements (now styled solely by the existing
  `.sg-drawer-body` semantic cascade); the failed-job title span and `MetaTerm`
  values use small inline `var(--*)` styles matching the in-file pattern. **No
  CSS file change needed** (the semantic rules already existed). No behaviour,
  handlers, endpoints, payloads, tab ids, artifact links, drawer-open contract,
  or data surface changed.
- **Docs:** this entry + `NEXT_CHAT_HANDOFF.md` (reskin/UX phase complete through
  Slice 16; next phase = correctness/measurement, starting with deterministic
  math verification).
- **Status: implemented + verified, awaiting review before commit.**

---

## Slice 15 — RecentJobsPanel + JobDetails body reskin (DONE / committed).

- **Slice 15 closes the last Slice 11 reskin debt:** the JobDetails drawer
  **body/tab content** still rendered with inert Tailwind utilities (badges
  concatenating, tiles/cards with no surface, code/log blocks unstyled, notices
  uncoloured, oversized 24px lucide icons). **Frontend visual/CSS/markup only** —
  no backend/API/pipeline changes; every handler, endpoint, payload, tab id,
  artifact link, retry/rerender/section-regen/revert flow, and the
  `useImperativeHandle({ openJob })` drawer-opening contract are untouched.
- **Files changed (2, frontend-only):**
  `frontend/src/components/RecentJobsPanel.jsx` (markup/className swaps across the
  drawer body: Details, Quiz, Outline-compliance, Sections, Edit-Markdown,
  Version-History tabs + FailedJobPanel, AttachmentDetails, Validation/Render-log
  tiles, DiffView, QuizQuestionCard) and `frontend/src/design-system.css`
  (additive **"RecentJobs + JobDetails body — Slice 15"** block).
- **Scope A (Recent list):** the Home Recent/Favorite cards already used the
  semantic `Panel`/`ItemCard`/`ProviderPill` system (Slice 11/12) — left as-is.
  The dead non-embedded `PreviewPanel` branch was not churned.
- **Scope B/C (drawer body):** new semantic classes layered on the existing
  Slice 5b `.sg-drawer-body` element cascade — `.sg-tag(+tones)`,
  `.sg-tile/.sg-tile-value`, `.sg-pre`, `.sg-notice(+tones)`, `.sg-danger-card`,
  `.sg-card-row(+good/warn/bad)`, `.sg-stack`, `.sg-grid-2/3`, `.sg-head-row`,
  `.sg-chip-row`, `.sg-btn-row`, `.sg-btn-accent`, `.sg-opt-btn`, `.sg-idx`,
  `.sg-diff-*`, `.sg-q-opt`, `.sg-att-item`, plus a generic
  `.sg-drawer-body svg{16px}` default (Tailwind `h-x/w-x` are inert) and
  `.sg-drawer-body .sg-spin` so loaders actually spin. Reuses `.pill`,
  `.recent-state`, `.sg-form-sub`, `.sg-modal-action`, `.sg-tab-stack`,
  `.sg-art-*`, `.sg-row*` where they already fit.
- **Safety:** pure class/markup change — no new data surfaced; no secrets, keys,
  host paths, tokens, socket paths, raw argv, or hidden prompts exposed; no
  `dangerouslySetInnerHTML`/raw HTML; no new deps; no Tailwind utilities revived
  (no `.grid`/`.flex`-by-name rules). Larger Slice 5b density baseline kept.
- **Verification:** `npm run build` green; `python -m compileall api pipeline`
  green; `git diff --check` clean; `git diff` is **frontend-only (2 files)**;
  `docker compose up -d --build` green (healthy) and the **container-built served
  bundle** confirmed to contain the new CSS + JSX classes; `smoke_release.py`
  **28 passed / 0 failed / 0 skipped** (incl. no-key-leak assertions; provider LLM
  flows exercise untouched backend). Screenshots delegated to the operator; no
  automated screenshots.
- **Status: implemented + verified, awaiting review before commit.**

---

## Slice 14 — Styles "Compare styles" feature DONE.

- **Slice 14 adds a real Compare Styles feature to the Styles workspace.** This is
  the long-missing capability the "compare built-in prompts side by side" shortcut
  always described but nothing implemented. **Frontend-only** — no backend, API,
  pipeline, style CRUD, generation, or Builder-payload changes.
- **Data source:** the existing **`GET /api/styles/{id}`** detail endpoint already
  returns the full prompt `content` (it backs clone/edit) for both built-in and
  custom styles. The list `GET /api/styles` deliberately omits `content`, so the
  compare panel fetches each selected style's body **lazily on demand** and caches
  it. Verified live: detail returns `content` with **no** filename/path/secret/key
  leakage (built-in *and* custom).
- **Files changed:** `frontend/src/components/StylesWorkspace.jsx` (compare state +
  `ComparePanel`/`CompareColumn`/`Stat`/`FlagChip`, card selection wiring),
  `frontend/src/design-system.css` (additive "Compare styles — Slice 14" block),
  `frontend/package.json` (`test:style-compare` script). **New:**
  `frontend/src/styleCompare.js` (pure helpers: `toggleCompareSelection`,
  `stylePromptStats`, MIN/MAX) and `frontend/scripts/verify-style-compare.mjs`
  (node harness, 20 checks).
- **UX:** header **Compare styles** toggle (turns into **Exit compare**); in
  compare mode the cards become checkbox-selectable (selection is visually
  separate from **Use** — Use/Build/Edit/Delete still work via stopPropagation);
  2–4 styles allowed (locked out + dimmed at 4). The top **Compare panel** shows a
  `<2`-selected empty state ("Select at least two styles to compare."), Clear, and
  Exit; otherwise renders side-by-side columns (2 = balanced; 3–4 = horizontally
  scrollable grid, no body overflow). Each column shows name, built-in/custom
  badge, description, type, based-on, tags, deterministic stats (words/chars/
  headings) + math/quiz/concise flags, a scrollable monospace prompt block, and
  Use/Build (+Edit/Delete for custom). No LLM/semantic analysis; no
  `dangerouslySetInnerHTML`; compare state is local-only (never persisted).
- **Verification:** `npm run build` green; `npm run test:style-compare` 20/20;
  `python -m compileall api pipeline` green; `git diff --check` clean; docker
  `build`+`up` green (served bundle/CSS contain the compare markup + grid);
  `/api/styles/{id}` leak-scanned (built-in + custom) — none; `smoke_release.py`
  **28/28**. (`npm run test`/verify-assets is a pre-existing stale failure on
  unrelated `App.jsx` mockup checks — fails identically on clean HEAD.)
- **Visual inspection delegated to user; no automated screenshots required.**
- **Status: implemented + verified + visually reviewed — committed.**

---

## Slice 13 — Ask Guide workspace redesign DONE.

- **Slice 13 (Ask Guide workspace UX/layout redesign) is DONE.** Frontend
  UX/layout-only — no backend/API/pipeline changes; Ask endpoints, payloads,
  session ids, cache semantics, prepare-context behavior, citation parsing, and
  message response handling are untouched.
- **Files changed:** `frontend/src/components/AskGuideWorkspace.jsx`,
  `frontend/src/components/DesktopDashboard.jsx`,
  `frontend/src/components/HelpWorkspace.jsx` (new),
  `frontend/src/design-system.css` (additive "Ask Guide redesign — Slice 13" +
  Help block).
- **Redesign:** chat-first layout; a compact selected-guide / local-model /
  session **status bar** (model + green/red connection dot, selected guide,
  prepared status, chat count, with **Refresh chats** + **New chat** actions); a
  **collapsible guide selector** (collapses once a guide is selected, expands to a
  client-side title search + list); **collapsible right-rail details** (Chats,
  Context sources, Preparation, Local model, and conditional Latest answer
  context — the last three collapsed by default); and a new frontend-only **Help
  workspace** hosting the manual local-model / llama-server setup instructions
  (reuses `CommandHelper`), wired to the previously-dead Help nav row. Ask's
  Local-model card now links to Help instead of embedding the command block.
- **Preserved:** local-only Ask behavior (no cloud fallback / provider switching),
  session/cache semantics, prepare-context behavior, citation safety, retrieved
  metadata safety (metadata only — never chunk bodies), local-model gating,
  handlers, API calls, and payloads. `/no_think` is never surfaced; no secrets,
  host paths, argv, tokens, socket paths, or URLs are exposed; no new
  dependencies; no Tailwind utilities revived; larger Slice 5b density baseline
  kept.
- **Verification:** build green; local-model status/command/library harnesses
  green; `compileall` green; `git diff --check` clean; `docker compose build && up`
  green (container serves the new bundle — new Ask/Help markup + CSS confirmed in
  the served JS/CSS); `smoke_release.py` **28/28** (clean run — outline-order
  assertion passed).
- **Visual inspection delegated to user; no automated screenshots required.**

---

## Slice 12 — Home & Library UX polish DONE.

- **Slice 12 (Home + Library UX polish) is DONE.** Frontend visual/UX only — no
  backend routes, payloads, job/shortcut ids, or pipeline behavior changed.
- **Files changed:** `frontend/src/components/DesktopDashboard.jsx`,
  `frontend/src/components/HomeShortcuts.jsx`,
  `frontend/src/components/LibraryWorkspace.jsx`,
  `frontend/src/components/RecentJobsPanel.jsx`,
  `frontend/src/design-system.css`.
- **Original review blockers and the fixes applied:**
  - **Stale/capped favorites →** Home "Favorite Guides" now loads real favorites
    from the full `/api/library` (newest sort) instead of the capped recent-20
    `jobs` prop Home was previously handed; the obsolete `jobs` fetch/prop wiring
    in `DesktopDashboard` was removed. Favorites refresh on `jobsRefreshKey` so a
    favorite toggled elsewhere shows on return to Home.
  - **Quick Launch cards →** simplified to icon / title / type (+ status pill only
    when degraded/broken); dropped the pastel fills and the inline description.
    Cards now use the shared dark `glass` treatment and the **silver hover sheen
    no longer clips**.
  - **Provider badges →** every real badge uses the white circular treatment
    (`variant: "light"`) so all marks read as centred glyphs on matching white
    circles (no odd dark circle).
  - **Provider tooltip copy →** each real badge carries curated, non-sensitive
    hover copy (model name + strength + how GuideForge uses it); cluster stays
    `aria-hidden`.
  - **Ghost/empty badge removed →** the cluster now renders only real providers.
  - **Library favorites filter + Home deep-links →** added a **Favorites** filter
    chip and a **Title Z–A** sort to Library (search / filter / sort / folder /
    trash / selection / bulk behavior all preserved); Home "View all" links on the
    Favorite and Recent panels deep-link into Library via the existing
    `libraryView` nonce channel (`favorites` presets the new filter + reveals the
    filter bar; `recent` opens newest). Both panels are capped at 5 items on Home.
  - **Library folder rail →** ends naturally under the folder controls when short
    and grows only as needed.
- **Security preserved:** no keys/tokens/paths/secrets in the DOM; badge copy is
  static curated text, nothing dynamic or sensitive.
- **Live verification:** local browser pass confirmed (Quick Launch hover no
  longer clips, white provider circles, working favorites, Home→Library
  deep-links, favorites filter), no horizontal overflow at 1920/1440.
- **Verification:** build green; `compileall` green; `git diff --check` clean;
  `smoke_release.py` 28/28 (checked with the known unrelated LLM
  `outline use → followed in order` ordering flake only — clean on re-run).

---

## Slice 11 — Final QA / polish sweep (HomeShortcuts + ShortcutInspector) DONE.

- **Slice 11 (GuideForge UI reskin — final QA pass) is DONE.** Visual/CSS/markup
  only. No app logic, handlers, state, ids, endpoints, payloads, or render
  pipeline changed.
- **Audit-driven scope (Option 2):** fixed the two live raw surfaces that the
  Slices 1–10 reskin left behind — **HomeShortcuts** leftovers and a full reskin
  of the **ShortcutInspector** Inspect/Repair drawer. The large
  **RecentJobsPanel / JobDetails body** reskin was **deliberately deferred** to
  its own dedicated slice (it is ~2.1k lines and needs screenshot/live
  verification; the JobDetails drawer *shell* already has its baseline
  `sg-drawer-*` reskin).
- **Files changed:** `frontend/src/components/HomeShortcuts.jsx`,
  `frontend/src/components/ShortcutInspector.jsx`, and
  `frontend/src/design-system.css` (additive "Reskin QA — Slice 11" block).
- **HomeShortcuts fixes:** shortcut-row meta chips (type / status / saved-prompt)
  → real `.sg-tag*`; emoji tile sizing; **Degraded / Broken activation dialogs**
  now use a real centered overlay (`.sg-modal-scrim` + `.sg-dialog`) instead of
  inert `fixed inset-0` Tailwind that rendered them inline; Import-shortcuts
  panel (intro, mono textarea, preview/primary buttons, error box, preview item
  cards, rename field, footer) reskinned; `Field` + `SavedPromptControl`
  helpers; native `<option>` backgrounds via one scoped CSS rule (removed inert
  per-option Tailwind).
- **ShortcutInspector fixes:** full reskin of the right-side drawer reusing the
  `.sg-drawer-root/scrim/sheet` shell (z-index lifted so it sits above the
  Customize modal); status pills, finding cards, repair field controls,
  mode/section option rows, preview + diff, confirm step, and footer
  Preview/Apply/Close actions all use dedicated `.sg-insp-*` / `.sg-act`
  semantic classes. Repair/confirm/destructive semantics, disabled states, and
  the preview-before-apply gate are unchanged.
- **Class audit:** undefined `sg-*` classes in the live render tree = **0**
  (before and after; the only 3 unmatched — `sg-tile*` — live solely in the dead,
  never-imported `ClaudeIcons.jsx`). Inert-Tailwind/old-palette leftovers in
  live-rendered code reduced to RecentJobsPanel only (deferred); `MetaRow` in
  BuilderWorkspace is dead/unused and left as-is.
- **Security preserved:** the inspector still renders only redacted backend
  candidates; no keys/tokens/paths in the DOM.
- **Live verification:** container rebuilt (`docker compose build && up`) and
  confirmed serving the new dist; all five target surfaces visually verified at
  100% zoom (Home cards / Customize modal + Import panel / Inspector drawer above
  the modal / Degraded+Broken activation overlays), no horizontal overflow at
  1920/1440/1024.
- **Verification:** build green; local-model status/command/library harnesses
  green; `compileall` green; `git diff --check` clean; class audit clean;
  `smoke_release.py` **28/28** (an earlier run flaked only on the LLM
  `outline use → followed in order` ordering assertion; clean on re-run).

---

## Slice 10 — Exports workspace reskin DONE.

- **Slice 10 (GuideForge UI reskin — Exports workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/ExportsWorkspace.jsx` and
  `frontend/src/design-system.css`.
- **Preserved:** export list behavior, artifact download URLs, inline/download
  variants, ZIP bundle payload/manifest behavior, selection/filter/sort state,
  rerender action, `JobDetails` wiring, handlers, and API calls.
- **Verification:** build green, `compileall` green, `git diff --check` clean,
  live browser pass, artifact endpoints checked, ZIP bundle checked,
  `smoke_release.py` 28/28.

---

## Slice 9 — Models workspace reskin DONE.

- **Slice 9 (GuideForge UI reskin — Models workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/ProviderSettingsWorkspace.jsx`,
  `frontend/src/components/LocalModelsPanel.jsx`, and
  `frontend/src/design-system.css`.
- **Preserved:** provider settings behavior, write-only API key behavior,
  fetched-models review-only flow, Local Models status, command helper, model
  library, managed-server safety behavior, handlers, state, endpoint paths, and
  API payloads.
- **Security preserved:** no raw keys, full URLs, companion tokens, socket paths,
  absolute host paths, executable paths, or raw argv exposed.
- **Verification:** build green, local-model status/command/library harnesses
  green, `compileall` green, `git diff --check` clean, live browser pass,
  `smoke_release.py` 28/28.

---

## Slice 8 — Styles workspace reskin DONE.

- **Slice 8 (GuideForge UI reskin — Styles workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/StylesWorkspace.jsx` and
  `frontend/src/design-system.css`.
- **Preserved:** style CRUD, built-in/custom/generated style behavior, AI style
  generation behavior, form validation, handlers, state, and API calls.
- **Verification:** build green, `compileall` green, `git diff --check` clean,
  live browser pass, `smoke_release.py` 28/28.

---

## Slice 7 — Ask Guide workspace reskin DONE.

- **Slice 7 (GuideForge UI reskin — Ask Guide workspace) is DONE.**
  Visual/layout-only.
- **Files changed:** `frontend/src/components/AskGuideWorkspace.jsx` and
  `frontend/src/design-system.css` (additive "Ask Guide — Slice 7" block).
- **Preserved:** local-only Ask behavior, sessions, prepare-context behavior,
  citations, retrieved metadata safety (metadata-only, no chunk body),
  local-model status gating, handlers, and API calls/payloads.
- **Verification:** build green, `compileall` green, `git diff --check` clean,
  live browser pass, `smoke_release.py` 28/28.

---

## NEXT — LMM Phase 2G11 final hardening/regression DONE; Phase 2 paused.

- **Local Model Manager Phase 2G11 is DONE** on branch
  `lmm-phase2g11-final-hardening`.
- **Current safe LMM Phase 2 milestone is complete/paused.** The implemented
  Linux path remains: host companion, approved-root GGUF scanning,
  Unix-socket-only backend bridge, model-library UI, selected-model handoff,
  companion-managed server controls, real `llama-server` lifecycle hardening,
  safe real-profile metadata/typed controls, `.ini` preset import, configured
  real-profile E2E harness, runtime setup UX, and runtime-service/operator docs.
- **Final offline regression harness added:**
  `test_scripts/test_lmm_phase2_final_regression.py` validates runtime-service
  example files/placeholders, JSON/INI parsing through the companion preset
  loader, Compose/systemd template boundaries, backend/profile DTO redaction,
  CPU-safe/manual helper defaults, risky-only `gpu_layers=999` scope, no LMM
  Provider Settings writes, no Ask coupling, no direct frontend companion calls,
  no permanent production Compose companion mount/env, companion-config-only
  approved roots, no browser folder picker, and safe selected-model fields.
- **Validation facts preserved:** CPU-safe real validation passed with
  `/usr/bin/llama-server`, `LMM_REAL_MODEL_ROOT=/mnt/ai/llm-models`,
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, `port=18080`, `ctx_size=4096`,
  `gpu_layers=0`, and `threads=8`. Full offload `gpu_layers=999` failed safely
  with CUDA OOM / `model_may_be_too_large` on the 26B model and is not a default.
- **Scope preserved:** tests/docs only; no production backend behavior change,
  no frontend UI change, no Ask change, no Provider Settings write, no permanent
  Docker Compose change, no installer/autostart behavior, no committed token,
  no token/socket/absolute host model path/executable path/raw argv exposure, no
  browser folder picker, no approve-root implementation, no model download
  manager, and no app-suggested settings.
- **Deferred after pause:** approve-root flow design and implementation,
  app-suggested settings/recommendations, Ollama/simple-local-model path,
  Windows/macOS packaging/support, and model downloads.
- **Recommended next slice:** pause LMM Phase 2 and move to another planned area;
  resume LMM only with a separately designed approve-root flow or packaging
  slice.

## Previous — LMM Phase 2G10 runtime-service/operator packaging docs DONE.

- **Local Model Manager Phase 2G10 is DONE** on branch
  `lmm-phase2g10-runtime-service-docs`.
- **Runtime service guide added:**
  `docs/LOCAL_MODEL_MANAGER_RUNTIME_SERVICE.md` documents Linux-first operator
  startup for the host companion, safe paths, token handling, manual companion
  health checks, temporary Docker override shape, systemd user-service template,
  E2E validation, troubleshooting, and the security checklist.
- **Safe templates added under `docs/examples/`:**
  `lmm-companion.config.example.json`,
  `lmm-companion.profiles.example.ini`,
  `lmm-companion.user.service.example`, and
  `docker-compose.lmm-companion.override.example.yml`.
- **Operational boundary preserved:** the socket directory is the only Docker
  mount shown; the token is a placeholder and server-side only; model roots are
  read by the host companion, not the Docker backend; and the examples avoid
  whole-home mounts, Docker socket, privileged mode, host PID namespace, host
  networking, and host-gateway TCP.
- **Validation basis documented:** Phase 2G8 CPU-safe E2E passed with
  `/usr/bin/llama-server`, `/mnt/ai/llm-models`,
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, `port=18080`,
  `ctx_size=4096`, `gpu_layers=0`, and `threads=8`; full offload
  `gpu_layers=999` remains an advanced risky example only because it failed
  safely with CUDA OOM on the 26B model.
- **Scope preserved:** docs/templates only; no production backend behavior
  change, no frontend UI change, no Ask change, no Provider Settings write, no
  permanent Docker Compose change, no actual installer, no app-installed system
  service, no committed token, no model download manager, and no app-suggested
  settings.

## Previous — LMM Phase 2G9 approved-folder setup UX polish DONE.

- **Local Model Manager Phase 2G9 is DONE** on branch
  `lmm-phase2g9-runtime-setup-polish`.
- **Manual command helper presets changed:** the default profile is now
  CPU-safe (`-c 4096 -ngl 0 --threads 8`), with GPU balanced
  (`-c 4096 -ngl 20 --threads 8`) and low-memory
  (`-c 2048 -ngl 0 --threads 8`) presets. Full offload `-ngl 999` remains only
  as an advanced profile explicitly labeled risky / may OOM, and is not the
  default.
- **Setup UX clarified:** Local Models now explains that approved GGUF folders
  come from the host companion config, the browser app cannot safely browse the
  whole PC or pick host folders directly, operators must configure
  `approved_roots`, restart the companion, then scan, and manual server mode
  still works without the companion. A compact example/edit-me JSON config block
  uses placeholders only.
- **Stale selection copy clarified:** when the companion is unconfigured and a
  saved selected model exists, the UI says it is a saved selection from a
  previous validation/session and is not confirmed by a live scan. When the
  companion is configured but the model is absent from the current library, the
  UI says it is saved but not in the current scan and may need rescanning.
- **Safe root/status display:** companion/backend library payloads may now
  include path-free root summaries (`id`, `recursive`, `model_count`) and the UI
  displays them when available. Absolute root paths, socket paths, tokens, and
  raw argv are not exposed.
- **Managed Server setup copy clarified:** controls remain disabled when the
  companion/profile is unavailable, explain they only control the
  companion-managed process, do not stop manual servers, and do not change
  Provider Settings. No-profile copy points to companion config/preset files.
- **Validation basis:** Phase 2G5/2G8 CPU-safe validation passed with
  `gpu_layers=0`, `ctx_size=4096`, `threads=8`; full GPU/offload
  `gpu_layers=999` failed safely as CUDA OOM / `model_may_be_too_large` and is
  not a default.
- **Scope preserved:** no true browser folder picker, no companion config write
  endpoint, no frontend-provided host path accepted by backend/companion, no
  Provider Settings writes, no Ask changes, no permanent Docker Compose changes,
  no model download manager, no app-suggested settings, no browser storage, no
  token/socket/raw absolute path/raw argv exposure, no free-form flags UI, and
  no whole-PC scan.
- **Recommended next slice:** packaging/runtime-service docs and a guided
  operator startup flow for running the host companion reliably. A future
  approve-root flow still needs a separate host-companion design.

## Previous — LMM Phase 2G7 operator setup docs + safe preset import DONE.

## Previous — LMM Phase 2G5 real Linux llama-server validation/hardening DONE.

## Previous — LMM Phase 2G4 Local Models managed-server UI DONE.

## Previous — LMM Phase 2G3 backend process bridge DONE.

- **Local Model Manager Phase 2G3 — FastAPI backend bridge for companion server
  status/start/stop/restart is DONE** on branch
  `lmm-phase2g3-backend-process-bridge`.
- **Backend routes added only:** `GET /api/local-model/server/status`,
  `POST /api/local-model/server/start`, `POST /api/local-model/server/stop`, and
  `POST /api/local-model/server/restart`. They delegate to the companion's
  existing Unix-socket `/server/*` endpoints using server-side
  `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and optional
  `LMM_COMPANION_TIMEOUT_SECONDS`.

## Previous — LMM Phase 2G2 companion HTTP process API DONE.

- **Local Model Manager Phase 2G2 — companion Unix-socket HTTP process-control
  endpoints is DONE** on branch `lmm-phase2g2-companion-process-api`.
- **Endpoints added on the host companion only:** `GET /server/status`,
  `POST /server/start`, `POST /server/stop`, and `POST /server/restart`. They use
  the existing companion token auth and Unix-socket `BaseHTTPRequestHandler`
  server.

## Previous — LMM Phase 2G1 companion process-control internals DONE.

- **Local Model Manager Phase 2G1 — companion process-control internals with
  fake/safe test executable only is DONE** on branch
  `lmm-phase2g1-companion-process-internals`.
- **Code added:** `tools/local_model_companion/profiles.py` defines typed,
  bounded launch profiles and the explicit `fake_test` profile constructor.
  `tools/local_model_companion/process_manager.py` defines
  `ManagedServerProcessManager`, `start_managed_server`,
  `stop_managed_server`, and `get_managed_server_status`.
- **Recommended next slice was:** Phase 2G2 companion HTTP server endpoints for
  process status/start/stop/restart, still no backend bridge or UI.

## Previous — LMM Phase 2F start/stop design review DONE.

- **Local Model Manager Phase 2F — start/stop design review is DONE** on branch
  `lmm-phase2f-start-stop-design`. This was a docs-only safety review for future
  Phase 2G companion-managed `llama-server` process control.
- **Design scope:** `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md` defines the
  future contract for companion `GET /server/status`, `POST /server/start`,
  `POST /server/stop`, and `POST /server/restart`; backend bridge routes
  `GET/POST /api/local-model/server/*`; and Local Models UI start/stop/restart
  behavior. Phase 2F added no code/routes/UI/Docker changes.
- **Boundary reaffirmed:** Docker FastAPI never directly starts, stops, restarts,
  signals, or inspects host processes; only the host companion may spawn
  `llama-server`; the companion may stop only a process it started and still
  tracks; no Docker socket, privileged container, host PID namespace, or direct
  Docker-to-host spawn.

## Previous — LMM Phase 2E selected library model handoff DONE.

- **Local Model Manager Phase 2E — selected library model handoff is DONE** on
  branch `lmm-phase2e-selected-model-handoff`. Added safe backend persistence for
  a chosen companion-library GGUF model without process control.
- **Backend endpoints added:** `GET /api/local-model/library/selection` returns
  `{ selected, future_launch_preview }`; `POST /api/local-model/library/selection`
  persists a selected model by `model_id` plus optional safe snapshot, preferring
  validation against the cached companion library when available; `DELETE
  /api/local-model/library/selection` clears only the app-side selection.
- **Safety scope preserved:** no Provider Settings write, no Ask change, no local
  provider base URL/model behavior change, no Docker change, no host-gateway TCP,
  no Docker socket, no privileged container, no host PID namespace, no
  `llama-server` process launch, no subprocess/shell execution, no start/stop/
  restart route or UI control, no browser localStorage/sessionStorage, no
  raw companion token/socket/Authorization/full URL exposure, and no absolute host
  model path exposure.

## Previous — LMM Phase 2D UI model-library picker DONE.

- **Local Model Manager Phase 2D — Local Models UI model-library picker is DONE**
  on branch `lmm-phase2d-model-library-ui`. Frontend/client/tests/docs only.
  Added a compact **Model Library** section to the existing Local Models panel.
  It fetches companion status from `GET /api/local-model/companion/status` and
  cached library data from `GET /api/local-model/library`, and adds **Scan
  approved folder(s)** wired to `POST /api/local-model/library/scan`.
- **Selection was frontend-only in Phase 2D:** clicking a discovered model only
  updated React component state for visual selection inside the panel. Phase 2E
  supersedes this with backend selection metadata while still avoiding Provider
  Settings writes and process control.

## Previous — LMM Phase 2C socket-mount validation harness ADDED.

- **Local Model Manager Phase 2C socket-mount validation — PASSED** on
  branch `lmm-phase2c-socket-mount-validation`. Added
  `test_scripts/validate_lmm_companion_socket_mount.py`, a manual live validation
  harness that proves the deployed Docker backend can reach a host companion
  through a mounted Unix domain socket and call the Phase 2C backend endpoints
  successfully.
- **Validation-only behavior:** the harness creates a temporary `/tmp`
  validation workspace, fake approved model root, fake `.gguf` files plus one
  non-GGUF file, explicit companion config, host companion process, and temporary
  Compose override. The override mounts only the temporary runtime directory into
  the app container and sets server-side `LMM_COMPANION_SOCKET`,
  `LMM_COMPANION_TOKEN`, and `LMM_COMPANION_TIMEOUT_SECONDS`. It is removed during
  cleanup and is not committed. The committed `docker-compose.yml` is unchanged.
- **Runtime checks covered by the harness:** wait for companion `GET /health` over
  the host Unix socket, bring the app service up with the temporary override, wait
  for `GET /api/health` on `http://127.0.0.1:8000`, then call
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`,
  `POST /api/local-model/library/scan`, and `GET /api/local-model/library`. It
  asserts configured/reachable status, `scan` capability, safe empty pre-scan
  library, fake GGUF model discovery, non-GGUF exclusion, root-relative
  `relative_path`, and no backend response leak of the token, raw socket path, or
  temporary absolute host model path.
- **Safety scope preserved:** no frontend UI, no production Docker Compose change,
  no Provider Settings write, no Ask change, no local provider base-URL behavior
  change, no host-gateway TCP, no Docker socket, no privileged container, no host
  PID namespace, no `llama-server` launch, no start/stop/restart backend API, and
  no process-control/subprocess/shell addition outside the validation script's own
  orchestration. The harness explicitly checks that
  `POST /api/local-model/server/start`, `/stop`, and `/restart` are unavailable.
- **Validation command:** `python test_scripts/validate_lmm_companion_socket_mount.py`.
  This is manual/live only and should not be added to normal smoke release unless
  explicitly requested. It will fail clearly if Docker is unavailable, Compose
  cannot use service `app`, port `8000` cannot become healthy, or the socket mount
  cannot be reached from the container.
- **Validation result:** live Docker/socket validation passed 17/17. Endpoint
  summary: companion status was configured/reachable with `scan`; pre-scan library
  returned safe empty models; scan returned the two fake GGUF fixtures
  (`gemma-validation-Q4_K_M.gguf`, `nested/qwen-validation-Q8_0.GGUF`) and excluded
  `notes.txt`; post-scan cached library returned both models; process-control
  probes for `/server/start`, `/server/stop`, and `/server/restart` returned
  unavailable (`405 Method Not Allowed`). Redaction proof passed: backend responses
  contained no companion token, no raw host/container socket path, and no temporary
  absolute host model/runtime path. The app service was restored with the committed
  Compose file only and was healthy afterward.
- **Recommended next slice:** Phase 2D Local Models UI model-library picker using
  the existing read-only endpoints, still with no start/stop/process control.

## Previous — LMM Phase 2C backend companion bridge DONE.

- **Local Model Manager Phase 2C — read-only backend bridge to the host companion
  model library is DONE** on branch `lmm-phase2c-backend-companion-bridge`.
  Backend-only: added `pipeline/local_model_companion_client.py`, wired
  `api/server.py`, and added `test_scripts/test_local_model_companion_bridge.py`.
  New endpoints under the existing LMM namespace:
  `GET /api/local-model/companion/status`, `GET /api/local-model/library`, and
  `POST /api/local-model/library/scan`. They use server-side env only:
  `LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`, and optional
  `LMM_COMPANION_TIMEOUT_SECONDS`.
- **Phase 2C bridge behavior:** the backend uses a tiny stdlib Unix-socket HTTP
  client (`socket.AF_UNIX`) with `Authorization: Bearer <token>`, bounded timeout,
  and JSON response parsing. Missing socket/token means unconfigured. Missing,
  refused, timed-out, auth-failed, malformed, or unexpected companion responses
  return safe HTTP-200-style DTOs with normalized categories:
  `companion_config`, `companion_offline`, `companion_auth`,
  `companion_timeout`, or `companion_error`. The frontend never receives the raw
  token, raw socket path, Authorization header, traceback, or low-level socket
  detail.
- **Phase 2C library safety:** the bridge whitelists model fields only (`id`,
  `display_name`, `filename`, `relative_path`, `root_id`, `size_bytes`,
  `modified_at`, `family_hint`, `quant_hint`, `server_compatible`), drops
  unexpected companion fields, rejects absolute `relative_path` values, redacts
  absolute paths/URLs/auth-like text/tokens from strings and bounded warnings, and
  never scans host files directly from Docker. `GET /api/local-model/library`
  reads the companion's cached model list only; `POST /api/local-model/library/scan`
  delegates the explicit scan to the companion.
- **Phase 2C hard non-goals preserved:** no frontend UI, no Docker Compose change,
  no Provider Settings writes, no Ask changes, no local provider base-URL behavior
  change, no direct Docker host filesystem scan, no host-gateway TCP
  implementation, no start/stop/restart routes, no process control, no model
  launch, no shell execution, no subprocess usage in the bridge, and no new
  dependency.
- **Validation:** `python test_scripts/test_local_model_companion_bridge.py` passed
  14/14 checks (FastAPI route introspection skipped because FastAPI is not
  installed in host Python), covering unconfigured env, successful fake Unix-socket
  responses and Authorization header, model whitelisting/counting, auth failure,
  missing/refused socket, timeout, malformed/unexpected JSON, redaction, absolute
  path rejection, warning bounds, and no process-control route/source surface.
  Also passed: `python test_scripts/test_local_model_companion_scan.py` 21/21
  (with the known AF_UNIX bind runtime skip in this sandbox),
  `python test_scripts/test_local_model_status.py` 17/17,
  `python test_scripts/test_local_model_command_profile.py` 13/13,
  `python -m compileall api pipeline tools`, `npm --prefix frontend run
  test:local-model-status`, `npm --prefix frontend run test:local-model-command`,
  `npm --prefix frontend run build` (existing Vite large-chunk warning only),
  `git diff --check`, and `docker compose config >/tmp/compose-check.txt` exit 0.
- **Recommended next slice:** Phase 2D Local Models UI model-library picker using
  these read-only endpoints, still with no start/stop/process control. If runtime
  deployment confidence is preferred first, do a narrow Docker/socket-mount
  validation slice before UI; no Compose mount was added in Phase 2C.

## Previous — LMM Phase 2B approved-folder scanning companion DONE.

- **Local Model Manager Phase 2B — host companion approved-folder GGUF scanning
  prototype is DONE** on branch `lmm-phase2b-companion-scan`. Added isolated,
  stdlib-only companion code under `tools/local_model_companion/`:
  `config.py`, `model_library.py`, and `companion.py`. It loads an explicit JSON
  config, scans only configured user-approved roots for `.gguf` files, returns safe
  metadata with stable opaque ids derived from `root_id + normalized relative_path`,
  and keeps absolute host paths out of model records. Config path is explicit via
  `--config` or `LMM_COMPANION_CONFIG`; there is no default home scan, no implicit
  `~/models`, and no silent root creation. Missing config returns a safe
  `no_approved_roots` warning and no models.
- **Phase 2B Unix socket status:** implemented a minimal Unix-domain-socket HTTP
  companion API in `tools/local_model_companion/companion.py`: `GET /health`,
  `GET /models` (cached only), and `POST /models/scan` (explicit scan). Every
  endpoint requires `Authorization: Bearer <token>`; token comes from
  `LMM_COMPANION_TOKEN` or the explicit local companion config and is never
  returned. The current execution sandbox denies AF_UNIX bind with
  `PermissionError: [Errno 1] Operation not permitted`, so the focused test verifies
  the socket server implementation shape and reports the runtime bind as skipped by
  sandbox.
- **Implemented scan safety:** approved-root canonicalization, candidate
  canonicalization, `.gguf` case-insensitive match, symlink resolution with
  inside-root enforcement, symlink escapes rejected, symlinked directories skipped
  to avoid loops, optional recursion, max files inspected, max models returned,
  elapsed-time guard, bounded warnings, missing-root/broken-symlink/path errors as
  warnings, root-relative paths only in records, best-effort family/quant hints, and
  no absolute host paths in model records.
- **Hard non-goals preserved:** no backend bridge endpoints, no frontend UI, no
  Docker Compose changes, no Provider Settings changes, no Ask changes, no new
  frontend dependency, no model execution, no whole-PC scan, no default home scan,
  no arbitrary path search from Docker, no arbitrary shell commands, no
  `llama-server` start/stop/restart, no process control, no subprocess usage in the
  companion package.
- **Focused validation:** `python test_scripts/test_local_model_companion_scan.py`
  passed 21/21 checks, including no-config/no-roots, missing root warning, simple
  GGUF metadata, non-GGUF ignore, recursive scan, symlink inside accepted, symlink
  escape rejected, traversal guard, broken symlink warning, max models, bounded
  warnings, config shape, socket implementation shape, source inspection for no
  process control/shell/subprocess, stable ids, hints, and no absolute host paths in
  model records. Continue to run `python -m compileall api pipeline tools` and
  `git diff --check` before closing the slice if not already run.
- **Recommended next slice:** Phase 2C should add a read-only Docker backend bridge
  that talks to the mounted Unix socket for companion health/status and model
  library/scan, with server-side token/socket config only and no frontend token or
  socket exposure. Keep start/stop/restart deferred.

## Previous — LMM Phase 2A host companion design DONE.

- **Local Model Manager Phase 2A — host companion + approved GGUF model library
  DESIGN is DONE** — branch `lmm-phase2-host-companion-design`, docs-only. New
  design doc: `docs/LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`. It keeps Phase 1 as
  complete/validated and defines the future Phase 2 boundary: React UI →
  Docker FastAPI backend → Unix-socket-first, token-authenticated host companion →
  approved model directory scan → host `llama-server` process lifecycle. The
  Docker backend must not directly browse the host filesystem or start/stop host
  processes; direct Docker-to-host spawn remains permanently rejected. Model
  scanning is limited to explicit user-approved roots, never whole-PC or default
  home-directory scanning. The companion owns host filesystem/process access and
  exposes only a narrow local API with whitelisted command profiles, typed safe
  parameters, bounded/redacted logs, and stop behavior limited to processes it
  started and tracks.
- **Phase 2A transport correction:** for the current Linux Docker deployment,
  Phase 2B should assume a Unix domain socket mounted into the backend container.
  A companion bound only to host `127.0.0.1` is not assumed reachable from Docker;
  loopback-only TCP is valid only for host-network/native packaging, and
  host-gateway TCP requires explicit operator sign-off, firewall restriction to
  Docker bridge subnets, and token auth. `llama-server` may still bind
  `--host 0.0.0.0` for the model `/v1` API so Docker can reach it; that is
  separate from the companion control API, which must never be public.
- **Phase 2A non-goals were preserved:** no code, no companion implementation, no
  backend endpoints, no frontend UI, no Docker changes, no process spawn, no
  model scanning implementation, no provider settings behavior change, no Ask
  behavior change, no uploads, and no new dependency.
- **Recommended next LMM slice only if the operator chooses to proceed:** Phase
  2B companion prototype for approved-folder GGUF scanning only, using the chosen
  transport contract, with no start/stop yet. Do not implement start/stop before
  the companion design and security boundary are accepted.

## Previous — Ask local direct-answer guard DONE; NEXT = explicit extra-uploads slice or broader manual Ask polish. (LMM Phase 1 COMPLETE + VALIDATED below.)

- **Ask Your Guide — local direct-answer guard is DONE** — branch
  `ask-local-direct-answer-guard`. Manual local llama-server testing with
  `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` showed thinking-style responses could spend
  the whole budget in `reasoning_content` and return empty visible assistant content.
  The first system-rule-only guard failed in the full Ask prompt; direct tests showed
  `/no_think` in the model-facing user message produces visible content.
  `pipeline/ask_sessions.py` now keeps the concise visible-answer system rules and
  adds a standalone `/no_think` local thinking-model control immediately before the
  final `User question:` block sent to `generate_chat_completion`. The marker is
  model-only: it is not stored in `history.jsonl`, returned by session load/list
  responses, included in session summaries, or rendered by the frontend.
  Citation/grounding rules are preserved. Validated: `python
  test_scripts/test_ask_local_chat.py` passed 45/45 pure checks with endpoint skip
  because FastAPI is unavailable in this environment; `python
  test_scripts/test_ask_context_inventory.py` passed 11/11 with the same endpoint
  skip; `python test_scripts/test_ask_context_prepare.py` passed 28/28 with the same
  endpoint skip; `python -m compileall api pipeline` passed; `npm --prefix frontend
  run test:ask-guide` passed; `npm --prefix frontend run build` passed with the
  existing Vite large-chunk warning; `python test_scripts/smoke_release.py` passed
  28/28; `docker compose config >/tmp/compose-check.txt` exited 0. Local-only
  behavior is unchanged: no hosted fallback, provider-settings writes, local model
  process control, uploads, streaming, retrieval changes, citation-validation
  changes, or reasoning_content exposure.
- **Ask Your Guide — empty local-model response guard is DONE** — branch
  `ask-empty-response-guard`, see DONE #59 below. During manual Ask UI validation
  after the math/source polish slice, a browser Ask message returned
  `POST /api/ask/sessions/{session_id}/message` → 500 because
  `generate_chat_completion` raised `RuntimeError("LLM returned an empty response.")`
  and Ask did not catch it. `pipeline/ask_sessions.py` now catches that narrow empty
  local-model RuntimeError and returns a safe structured `provider_error` response
  with `error.category: provider_empty_response` plus a retryable user-safe message.
  The failed turn does not append a successful user/assistant message to history.
  Local-only behavior is unchanged, and no retrieval, prompt assembly, model fallback,
  citation validation, session management, clear/delete, provider settings,
  streaming, uploads, rolling summary, multimodal, or process-control behavior
  changed. Focused coverage was added in `test_scripts/test_ask_local_chat.py`;
  validations are listed in DONE #59. The original empty local-model behavior was
  not reproducible after the Docker app was rebuilt/restarted and healthy, but the
  simulated regression is now covered.
- **Ask Your Guide — chat math/source visual polish is DONE** — branch
  `ask-chat-math-source-polish`, see DONE #58 below. Frontend-only Ask chat
  readability polish in `frontend/src/askGuide.js`,
  `frontend/src/components/AskGuideWorkspace.jsx`, and
  `frontend/scripts/verify-ask-guide.mjs`. Added inert math-aware answer parsing for
  `$$...$$`, `\[...\]`, `\(...\)`, and escaped-dollar inline math; display math
  renders as readable monospace blocks preserving line breaks; inline math renders as
  small monospace chips. No `dangerouslySetInnerHTML`, no markdown dependency, no
  KaTeX/MathJax, and no new dependency. Trusted backend-used citations now appear in
  a clearer **Sources used** section; unsupported citations remain warning-only and
  are not trusted chips. Retrieved chunk metadata stays collapsed and shows cleaner
  label/type/page/score/token rows; chunk text is still never rendered. Local-only
  Ask behavior and session management are unchanged.
- **NEXT — conservative choices only.** Do not start extra uploads automatically.
  Recommended next is either (1) broader/manual Ask UI polish only if another
  concrete issue surfaces, or (2) Ask Your Guide extra session uploads as a separate
  explicit slice if the operator chooses to continue Ask features. Keep streaming,
  hosted/cloud Ask, rolling summary, multimodal, and process control deferred.
- **Ask Your Guide — session management UI/API is DONE** — branch
  `ask-session-management`, see DONE #57 below. Added safe session listing,
  switching, new chat, clear-history, and delete-session behavior. Backend routes:
  `GET /api/ask/jobs/{job_id}/sessions`,
  `DELETE /api/ask/sessions/{session_id}/history`, and
  `DELETE /api/ask/sessions/{session_id}`. Clear keeps the session id and prepared
  context cache; delete removes only the fenced session directory. The Ask workspace
  now has a compact Chat sessions rail panel plus active-session clear/delete
  controls, preserves lazy session creation on first send, and keeps explicit prepare
  + local-only chat behavior unchanged. No extra uploads, no export, no streaming,
  no cloud/DeepSeek/Qwen fallback, no process control, no provider settings writes,
  and no new dependencies.
- **Ask Your Guide — chat polish + emitted-citation validation is DONE** — branch
  `ask-chat-polish-citations`, see DONE #56 below. The local-only Ask message
  endpoint now validates bracket-style model citations against the turn's retrieved
  citation labels, strips unsupported Ask-looking citations from the returned/stored
  answer, and returns `citations_allowed`, `citations_used`,
  `citations_unsupported`, plus `citation_validation{ok, unsupported_count}`.
  Normal bracketed prose that does not look like an Ask citation is left alone. The
  prompt now asks for fewer, clearer citations at paragraph ends or a short sources
  line without weakening grounding. The Ask UI renders safe answer blocks for
  headings/bold/lists without `dangerouslySetInnerHTML`, fixes the
  `Guide only · [object Object]` metadata bug, hides full technical session ids,
  shows trusted citation chips from backend-used citations, warns on unsupported
  citations, and keeps retrieved chunk metadata collapsed by default. No chunk text,
  raw prompts, keys, full URLs, provider settings writes, cloud fallback, streaming,
  extra uploads, process control, or new dependencies.
- **Ask Your Guide — frontend chat UI wiring is DONE** — branch
  `ask-chat-ui`, see DONE #55 below. The existing Ask workspace now creates chat
  sessions lazily on first send, loads the session with `GET /api/ask/sessions/{id}`,
  posts non-streaming messages to the backend local chat endpoint, renders bounded
  history, answer text, backend-returned citation chips, safe retrieved citation
  metadata, and safe local-model info. Chat stays gated on selected guide + ready
  context + explicit prepare + reachable local model + no in-flight send. Local
  offline/unconfigured keeps the composer disabled and shows the existing command
  helper. No localStorage/sessionStorage persistence, no raw HTML rendering, no
  chunk/source/guide text rendering, no process control, no provider writes, no extra
  uploads, no exports, no streaming, and no cloud fallback.
- **Ask Your Guide — backend local chat API is DONE** — branch
  `ask-local-chat-api`, see DONE #54 below. Backend-only session creation/load +
  non-streaming local-only message endpoint now exist:
  `POST /api/ask/jobs/{id}/sessions`, `GET /api/ask/sessions/{session_id}`, and
  `POST /api/ask/sessions/{session_id}/message`. The message path status-gates on
  LMM/local provider availability, prepares or reuses the Slice 3 lexical index,
  retrieves a bounded top-K chunk set, assembles citation-labelled prompt context +
  recent history, and calls only the existing `local` OpenAI-compatible provider.
  Offline/unconfigured local returns a structured safe response with **no model call**.
  Sessions live under `jobs/<job_id>/ask/sessions/<session_id>/`; original artifacts
  are untouched. **No frontend/UI changes, no extra uploads, no cloud fallback, no
  DeepSeek/Qwen fallback, no streaming, no rolling summary, no generation jobs, no
  new dependency.**
- **Ask Your Guide — Slice 3 is DONE (backend context preparation / chunking)** —
  branch `ask-context-prepare`, see DONE #52 below. New stdlib-only helper
  `pipeline/ask_context.py` chunks `clean.md` (guide) + optional `extracted.txt`
  (source) deterministically on heading / `## Page N` boundaries (~650-token target,
  ~800 ceiling, `chars/4`, no overlap), preserving each chunk's **citation label**
  (nearest guide heading / `Page N`) and building a dependency-free lexical index
  (per-chunk term frequencies + `doc_freq`). `POST /api/ask/jobs/{id}/prepare` builds
  or reuses a cache at `jobs/<id>/ask/cache/context_index.json`, keyed by a content
  hash over guide+source bytes: **idempotent** (`hit` rewrites nothing; content change
  → `rebuilt`; corrupt/stale → safe rebuild), **atomic** writes, **fenced** to the job
  dir. Unknown job → 404; guide-less existing job → 200 `ready:false`. Response is an
  explicit whitelist (counts + bounded citation summary + job-relative cache path) —
  **no guide/source body, chunk text, key, URL, or host path.** **No chat, no retrieval
  endpoint, no model/local-model call, no sessions, no extra uploads, no UI, no new
  dependency; original artifacts untouched (no `save_clean_md`, no manifest write).**
- **Ask Your Guide — Slice 2 is DONE (backend context inventory endpoint)** —
  branch `ask-context-inventory`, see DONE #51 below. Two **read-only** endpoints over
  generated-guide artifacts: `GET /api/ask/jobs` lists **only Ask-eligible jobs** (those
  with a generated `clean.md`; guide-less / failed / incomplete jobs are filtered out)
  with curated, redacted picker fields (id/title/status/created+updated/style/preset/
  provider/model/favorite/attachment_summary/guide+source availability); `GET
  /api/ask/jobs/{id}/context` returns a per-job **readiness + source inventory**
  (guide `clean_md` present + char + heading counts; source `extracted.txt` present +
  char + `## Page N` anchor count; redacted attachment names/modes/extracted_chars/
  warnings; page selections; a `readiness{status,ready,reasons}` object). Thin read-only
  reader `pipeline/ask_inventory.py` (counts only — never a guide/source **body**);
  routes reuse the existing `_safe_manifest`/`_safe_attachment_metadata`/
  `_attachment_summary`/`_safe_page_selections` redaction and emit an explicit field
  whitelist, so **no raw key / full base URL / filesystem path / artifact body** can ride
  along. **No chat, no chunking, no retrieval/indexing, no model call, no session storage,
  no UI; original job artifacts untouched (no `save_clean_md`, no manifest write).**
- **Ask Your Guide — Slice 1 design is DONE (docs-only)** — branch
  `ask-your-guide-design`, on `docs/ASK_YOUR_GUIDE_DESIGN.md`, see DONE #50 below.
  A dedicated **`AskGuideWorkspace`** (first-class page/tab) where the user selects a
  generated guide/job and chats with it using a **local model only** (status-gated on
  LMM Phase 1; no DeepSeek/Qwen/cloud fallback). Mandatory **context manager +
  budgeted retrieval** (chunk `clean.md`/`extracted.txt` with `## Page N`/heading
  citation anchors, dependency-free lexical index cached per `(job_id, content_hash)`,
  reserve answer/system-rules/recent-chat, rolling chat summary). Hard
  **accuracy/citation contract** (answer from material first, cite page/section, say
  so when not covered, never invent). Conservative session-scoped storage (never
  auto-exported, no secrets). 8 proposed endpoints, all local-only + read-only over
  job artifacts. **No code changed.**
- **LMM Phase 1 is COMPLETE and VALIDATED.** Slices 1→4 (design → detection-only
  status endpoint → status panel → command helper) are on trunk (`94003bc`,
  `e27c674`, `7429f24`, `e399f09`), and the **Slice 5 validation + docs-reconciliation
  pass PASSED** — see DONE #49 below and
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`. All static, Docker, smoke,
  live-API, no-process-execution, and secret-leak checks pass; **no code changed.**
- **LMM Slice 4 is DONE (command-helper profiles / Copy start command)** — branch
  `local-model-command-helper`, on trunk `e399f09`, see DONE #48 below. Read-only
  `GET /api/local-model/command-profile` (`get_local_model_command_profiles()`)
  serves static, whitelisted `llama-server` start commands (default GPU + CPU-only
  profiles) with a `/path/to/model.gguf` **placeholder**, `--host 0.0.0.0 --port
  8080`, and safety warnings. The Local Models panel renders a first-class **Copy
  command** block (profile chips, selectable code block, clipboard + manual
  fallback), prominent when offline and collapsed when reachable. **Command helper
  only — the app never executes it; no spawn/start/stop, no GGUF scan, no host
  companion.** Pure `localModelCommand.js` helpers; backend + frontend harnesses
  green; no provider-write or status-DTO behavior change.
- **NEXT — Ask Your Guide local-only chat (recommended), OR host-companion DESIGN
  (optional, sign-off-gated).** Phase 1 is feature-complete + validated, so the next
  major choices are: (1) **Ask Your Guide** local-only chat — consumes LMM status,
  no process control — recommended; (2) **host companion DESIGN** (LMM Slice 5,
  Option B) only if the user wants app-managed start/stop later; (3) Math/PDF
  font-size rationalization; (4) Large-PDF preflight size-limit polish. **Still
  deferred (do not begin without an explicit slice):** no host process control, no
  start/stop, no GGUF browsing, no host companion implementation, no Ask Your Guide
  chat yet. See `LOCAL_MODEL_MANAGER_DESIGN.md` §11.
- **LMM Slice 3 is DONE (Local Models status panel, FRONTEND)** — branch
  `local-model-status-ui`, see DONE #47 below. Consumes the Slice 2 endpoints
  (`getLocalModelStatus`/`checkLocalModelStatus` API helpers) and renders a
  read-only **Local Models** panel inside the Providers page: live status pill
  (reachable green / offline amber / not-configured grey / error red), host-only
  base URL, in-Docker flag, latency, model count + bounded model chips,
  default/selected model, redacted offline message + first-class troubleshooting
  (with the `--host 0.0.0.0` gotcha), backend `notes`, a **Refresh status** button
  (calls `/check`, never saves/starts anything), an "Edit local provider settings"
  link that scrolls to the Local provider card (single writer), and the disabled
  **Copy start command — Planned** affordance. Pure `localModelStatus.js` helpers
  unit-tested by `verify-local-model-status.mjs` (47/47). **No process control, no
  inline base-URL editing, no raw key/URL.**
- **LMM Slice 2 is DONE (detection-only backend status endpoint)** — branch
  `local-model-status-api`, DONE #46. Read-only `GET /api/local-model/status`
  (+ thin `POST /api/local-model/check` alias), `get_local_model_status()`.
- **LMM Slice 1 design is DONE** (DONE #45) — `docs/LOCAL_MODEL_MANAGER_DESIGN.md`:
  detection-first, Option D (Docker→host spawn) REJECTED, Option C not the default.
- **LMM Slice 4 is DONE** (DONE #48) — the §9 command-profile helper +
  enabled **Copy command** button (a display template the app never executes;
  `--host 0.0.0.0` guidance kept).
- **LMM Slice 5 (Phase-1 validation / docs reconciliation) is DONE** (DONE #49) —
  validation **PASSED**, `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`, docs-only,
  no code changed. Phase 1 is complete. NEXT is **Ask Your Guide local-only chat**
  (recommended) or the sign-off-gated host-companion DESIGN (see the header above +
  design §11).
- **The Shortcut Inspector / Repair loop is COMPLETE** (Slices 1+2+3A+3B + the
  degraded-activation confirm polish, DONE #39→#43). See the block just below and
  DONE #43 for the latest slice. **A follow-up shortcut slice (DONE #44) then
  fixed the Edit-modal generator-preset source bug and added opt-in
  `saved_prompt`** — see DONE #44.

---

## Shortcut Inspector / Repair Loop (Slices 1+2+3A+3B + degraded-activation DONE)

- **Design doc:** `docs/SHORTCUT_INSPECTOR_REPAIR_DESIGN.md`. Safe UX + backend
  contract for inspecting and repairing shortcuts whose saved references
  (provider/model/style/preset/section/axis/tool/view) have gone invalid.
- **Slice 1 (backend inspector, read-only) is DONE** (DONE #39, branch
  `shortcut-inspector-backend`). Added a findings engine in
  `pipeline/shortcut_store.py` (`_collect_findings` / `_validity`) + the additive
  `validity` object on every `_public` view (list/get/import-preview) + the
  read-only `GET /api/shortcuts/{id}/inspect` route. Legacy `valid`/`reason` are
  **unchanged**. Fixes all three gaps: 3-tier status (binary→`valid`/`degraded`/
  `broken`), **full** findings list (not first-failure), and the previously-missing
  **saved-model** check. No writes, no frontend, no store refactor.
- **Slice 2 (frontend badges + read-only Inspector UI) is DONE** (DONE #40, branch
  `shortcut-inspector-ui`). `inspectShortcut` API helper + pure
  `frontend/src/shortcutStatus.js` status/badge/finding helpers (3-tier, with a
  fallback for old payloads lacking `validity`) + 3-tier badges on Home cards
  (valid quiet; degraded amber "Needs attention"; broken red "Broken") and
  Customize rows + a read-only `ShortcutInspector` drawer (findings + redacted
  repair-candidate summary + "read-only; repair comes next"). **No mutation, no
  preview/apply, no provider/model auto-switch, no raw keys.** Card activation is
  **unchanged** (still gated on legacy `valid`; broken never auto-routed). Backend
  untouched. node harness `verify-shortcut-status.mjs` 25/25; live Chromium UI
  proof; secret scan clean.
- **Slice 3A (backend repair preview + apply endpoints, BACKEND ONLY) is DONE**
  (DONE #41, branch `shortcut-inspector-repair-backend`). Added a shared,
  read-only repair normalizer (`_prepare_repair`) + `preview_repair` (pure) +
  `apply_repair` (the only write) to `pipeline/shortcut_store.py`, plus the two
  routes `POST /api/shortcuts/{id}/repair/preview` and `…/repair/apply`. Repair
  is an **explicit whitelisted patch** (`mode` + `changes{provider, model, style,
  generator_preset, output_depth, difficulty, include_sections{remove,set},
  remove_fields}` + `clone_name`) — **no arbitrary merge-patch**. Apply reuses the
  existing `update_shortcut` (in place) / `create_shortcut` (clone) CRUD, so the
  whitelist + atomic write hold automatically. **No auto-repair, no
  migration-on-read, no silent overwrite, no provider/model auto-switch, no raw
  keys.** `test_scripts/test_shortcut_repair.py` 29/29; existing
  `test_shortcut_store.py` 39/39 + `test_shortcut_inspector.py` 19/19 unchanged.
- **Slice 3B (frontend repair UI wiring) is DONE** (DONE #42, branch
  `shortcut-inspector-repair-ui`). The read-only drawer is now a safe repair
  surface: `previewShortcutRepair`/`applyShortcutRepair` API helpers + pure
  `frontend/src/shortcutRepair.js` draft/payload/staleness helpers + an enabled
  repair panel (provider/model/style/preset/depth/difficulty Keep/Replace/Remove,
  unknown-section removal, in-place/clone mode, live Preview diff, confirm-gated
  Apply). **Apply requires a fresh preview** (editing the draft marks it stale);
  no repair-on-open, no auto-switch, no raw keys. `verify-shortcut-repair.mjs`
  green; backend tests unchanged; live in-container repair flow + secret scan
  clean. Card activation behaviour is **unchanged**.
- **Degraded-activation confirm + "Repair instead" is DONE** (DONE #43, branch
  `shortcut-inspector-degraded-activation`). Home activation is now gated through a
  pure `activationDecision` (`frontend/src/shortcutStatus.js`): a **valid** shortcut
  launches immediately (no prompt); a **degraded-yet-launchable** shortcut
  (`validity.status === "degraded"` while legacy `valid === true`) raises a
  confirm dialog (**Continue anyway** / **Repair instead** → existing Inspector
  drawer / **Cancel**) before launching; a **broken** shortcut (`valid === false`)
  stays blocked and now shows a "This shortcut is broken" dialog offering
  **Inspect / Repair** instead of silently routing. **Legacy `valid` is still the
  hard guard**; Continue anyway calls the unchanged launch path with **no
  mutation**; Repair instead only opens the Inspector (no preview/apply until the
  user acts). New node harness `verify-shortcut-activation.mjs` (wired into
  `test:shortcuts`). Backend untouched; secret scan clean.
- **Remaining deferred polish (not started — pick one as an explicit slice):**
  (a) manual browser click-through of the live Preview→Apply UX + drawer/dialog
  layout polish; (b) the design §"Optional later polish" — "Repair all" batch, a
  Home "N shortcuts need attention" banner, model auto-suggest (preselect-only).
  See design doc §5/§7 and the `DECISIONS.md` repair entries.

---

## Where we are

- **Branch:** `chrome-renderer-v1` (the live integrated trunk; PR target)
- **Trunk tip:** `e399f09` — "Add local-model command-helper (copy start command)
  (LMM Slice 4)". The **Local Model Manager Phase 1** landed as four commits on top
  of the Shortcut Inspector group + the Edit-preset follow-up (`adc2a7e`): `94003bc`
  (Slice 1 design), `e27c674` (Slice 2 detection-only status endpoint), `7429f24`
  (Slice 3 Local Models status panel), and `e399f09` (Slice 4 command helper). Phase
  1 is now **validated** (Slice 5, DONE #49,
  `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`). Below the LMM group sit the
  **Shortcut Inspector / Repair Loop** (`a0f96d1`→`4458c9a`), the **in-app provider
  settings feature group** (`978516e`→`61fb423`), and the large-PDF core
  (`60c3e78`). Older `4458c9a` / `61fb423` / `60c3e78` / `901d44b` / `65b9b8f`
  references further down are historical — trunk is now `e399f09`.
- **`origin/chrome-renderer-v1`:** `e399f09` (local == origin; pushed)
- **Provider settings feature group is COMPLETE through Slice 5** (design →
  backend store/endpoints → Providers UI → runtime wiring → fetch-models endpoint
  → Refresh Models UI). See DONE #32 (backend store), #33 (Providers UI), #34
  (runtime), #35 (fetch-models endpoint), #36 (Refresh Models UI), and the design
  doc `docs/PROVIDER_SETTINGS_DESIGN.md`. Highlights:
  - **Security:** raw API keys stay **server-side only**. `/api/options` and
    `/api/provider-settings` are **redacted** (no key field by construction —
    only `configured`/`key_source`/last-4 `key_hint`/`base_url_host`).
    `config/provider_settings.json` is **non-secret** (`0644`);
    `config/secrets.json` holds **raw keys only** (`0600`, gitignored +
    dockerignored). The frontend never receives a raw key.
  - **Precedence:** provider/model resolves **per-job request > provider-settings
    default > `.env` > built-in default**. Generator presets **never hard-pin**
    provider/model — `model_hint` stays **advisory** — but a preset's **explicit**
    sampling/thinking value **can override** the stored runtime defaults.
  - **Runtime applied:** the stored `timeout_seconds`, `retry_count`, and
    `thinking_default` now reach the live model call (resolved once in
    `build_provider_config`, applied in `generate_chat_completion`). No store
    files ⇒ byte-identical to trunk (no timeout, 0 retries, thinking `True`).
  - **fetch-models endpoint: DONE** (DONE #35, branch
    `provider-settings-fetch-models`) — read-only `POST
    /api/provider-settings/{provider}/fetch-models`, no auto-persist.
  - **Refresh Models UI: DONE** (DONE #36, branch
    `provider-settings-fetch-models-ui`) — each Providers card has a **Refresh
    models** button calling the read-only endpoint. Fetched ids are
    **review-only**; a per-model **Add** / **Add all new** stages them into the
    draft `custom_models`, and an **explicit Save** is required to persist (after
    which `/api/options` includes the saved custom models — Builder dropdowns keep
    reading `/api/options`). Fetching never auto-saves and never auto-switches the
    provider/default model.
  - **Deferred:** encrypted-at-rest / OS keyring, `.env` import, the **Local Model
    Manager** (separate design-first feature), and the optional Builder "Provider
    default" thinking UI polish.
- **Large-PDF core is COMPLETE end-to-end** (preflight design → endpoint →
  Builder warning UI → page-selection plumbing → extraction honors selected
  pages → first-N/manual page-range UI). See DONE #27→#31. Automatic
  split/chunk processing and hybrid embedded-text + OCR dedup remain **deferred**.
- **Group C is COMPLETE and INTEGRATED** (C1 → C5, incl. C4a–d) onto `chrome-renderer-v1`.
- **For new sessions:** branch from `chrome-renderer-v1` @ `e399f09` (or later). Do **not**
  re-merge any of the old stacked feature branches — they are consumed/archival (see
  `DECISIONS.md` → "Consumed feature branches must not be re-merged"). The short one-page
  start-here is `docs/NEXT_CHAT_HANDOFF.md`.

## INTEGRATION — DONE: Group C is now on `chrome-renderer-v1` (pushed)

Group C was integrated onto the real target and `chrome-renderer-v1` was moved to the
integrated tip and pushed. The work originally landed on the throwaway `integ-group-c`
branch (off `origin/chrome-renderer-v1` @ `38cc822`); `chrome-renderer-v1` now points at
`1d51b36`. Sequence on the trunk:

- `6f888b2` — **Squash of the Group C stack** onto `38cc822`. Clean fast-forward, **zero
  conflicts** (the earlier "5 conflicts" were artifacts of two local-only commits on local
  `chrome-renderer-v1`: `863f5b7` Docker-hardening and `61c134c`, neither pushed nor in the stack).
- `5bde798` — **Re-applied `_preprocess_ocr_image`** (the one non-duplicate piece salvaged from
  local-only `61c134c`); its event-loop and provider-error changes were already superseded by the stack.
- `75ec24f` — **Prompt fixes** for two manual-test findings: MCQ answer explanations were wrapped in
  `$...$` (KaTeX stripped the spaces → `Biasshiftsthebaseline`); `slide_page_references` was too weak.
  Strengthened `mcqs_with_answers` (prose, never `$...$`) and `slide_page_references` (carry `## Page N`
  anchors through as compact `(p. N)` refs). Prompt-only; verified on a synthetic multi-page source.
- `72dab90` + `773209a` — **Mixed scanned/text PDF OCR fallback fixed** (+ its docs). Real issue:
  `_extract_pdf` decided text-vs-OCR for the WHOLE document, so one page of embedded text (a title
  slide) suppressed OCR for the rest — the 118-page `04_Neural_Networks...Backpropagation` extracted
  only ~97 chars / `## Page 1`. New behavior: **page-level** fallback — each page uses meaningful
  embedded text (≥40 chars OR ≥5 word-like tokens) else is OCR'd individually (reusing
  `_preprocess_ocr_image`); `## Page N` anchors preserved; mode now `pdf_text` / `pdf_ocr` /
  `pdf_mixed`. Verified on the real artifact: **~97 → 18,799 chars, 1 → 118 `## Page` headings, mode
  `pdf_mixed`**. Regression test `test_scripts/test_mixed_pdf_ocr.py` (synthetic page-1-text +
  pages-2/3-image PDF; skips cleanly without PyMuPDF/tesseract, full pass in Docker). Release smoke
  28/28 (the known outline-ordering check flaked once, passed on rerun).
- `1d51b36` — **Compose resource limits + `no-new-privileges` hardening** salvaged from local-only
  `863f5b7` (`mem_limit: 2g`, `pids_limit: 256`, `cpus: 2.0`, `security_opt: no-new-privileges:true`).
  Additive to `docker-compose.yml` only; `docker compose config` validated. `863f5b7`'s non-root/gosu
  hardening was already integrated at `6f888b2`; its **GHCR publish workflow / prebuilt image** and
  **pinned dependency lockfile** remain **deferred** decisions (see `DECISIONS.md`).

### Local-only commits `61c134c` and `863f5b7` — parked on `hardening`
Both were investigated. Useful pieces were salvaged onto the trunk (OCR preprocessing from
`61c134c` → `5bde798`; compose resource limits from `863f5b7` → `1d51b36`). The remaining
pieces (GHCR publish/prebuilt image, pinned deps) are deferred. The commits themselves stay
parked on the `hardening` branch — not merged, not deleted.

- **NOT automated — needs manual click-through:** generate a guide from a real scanned PDF through the
  Builder and confirm page references appear and MCQ answer spacing is correct in the rendered PDF.
- **Deferred:** large-PDF upload UX / preflight / page-range selection.

## DONE (in order)

1. **Generator presets** — Claude-Exam / Review / Cram: full system prompts +
   tuned sampling params (`a97d763`).
2. **Slice 3 — env-configurable attachment caps** (200k/600k default) +
   preset-aware truncation warning (`6f4d28c`).
3. **Slice 4 — math degrade** — math validation failures degrade to marked spans
   instead of killing the job; math prompt hardened (`9ba7e52`).
4. **Slice 5 — cleanup/hardening** — removed `legacy_scripts` + stray root files;
   redact host paths in error responses (`f3a8d84`).
5. **Slice 1A** — job stage reporting in pipeline + `/api/jobs/{id}/progress`
   endpoint (`d3d75fd`).
6. **Slice 1B** — persistent Builder action bar, live progress button,
   dirty-state warning, tooltips (`ec34d59`); progress poll tuned to 300ms
   (`f6424c9`).
7. **Slice 2A** — backend shortcut store with whitelist-validated import/export,
   defaults, 11 endpoints (`72fa2cd`).
8. **Slice 2B** — Home shortcuts UI, customize modal, import/export,
   save-as-shortcut (`afab4f2`).
9. **Slice 3/B1 — Library bulk actions (BACKEND ONLY)** — `51fc7b9`. Three
   partial-success endpoints under `/api/jobs/bulk/*` (`delete`/`restore`/
   `move`) that **reuse the existing single-item internals**: bulk delete →
   `trash_job` (soft-delete to `jobs/.trash/`, guarded by
   `_guarded_trash_target` — never hard-deletes), bulk restore → `restore_job`,
   bulk move → `library_store.move_job` (existing `folder_id` model). Routes
   registered **before** the parametric `/api/jobs/{job_id}/restore` so the
   literal `bulk` segment is never read as a job id. Verified in Docker (uid
   10001/appuser) via `test_scripts/smoke_library_bulk.py` (16/16) +
   curl/`ls .trash` evidence. **Frontend multi-select UI is NOT in this slice.**
10. **Slice B2 — Library multi-select bulk actions UI (FRONTEND)** — `5916861`.
    Library multi-select with per-job checkboxes + **select-all-visible**, a
    selection-aware bulk toolbar (Move to folder / Move to Unfiled / **Delete** /
    Clear), **bulk delete** routed through the soft-trash with an **Undo toast**
    (bulk restore of exactly the trashed ids), and **bulk move-to-folder**. All
    three use the canonical `/api/jobs/bulk/*` family; the legacy
    `/api/library/jobs/move` caller was migrated to `/api/jobs/bulk/move`
    (`folder_id`, not `folder`). Partial-success aware (`partitionResults`):
    succeeded ids cleared, `error` ids kept selected, ok/fail counts toasted;
    whole-request 404 (unknown folder) keeps selection + list untouched.
    Selection clears on folder/search/filter change. Verified in Docker via a
    real headless-Chromium (Playwright) click-through + captured bulk network
    calls; release smoke 28/28 (flaky outline check passed 3/3 in preflight).
11. **Slice B3 — finish Library folder + trash actions (FRONTEND + 1 backend
    route)** — `f1201a0`. **Folder multi-select** in the rail (per-folder
    checkboxes on non-system folders) + a folder action bar (count / Delete /
    Clear). **Bulk folder delete** offers BOTH behaviors via a dedicated
    two-path modal: **(A) Delete folders only** → guides fall back to Unfiled
    (loops the existing `DELETE /api/library/folders/{id}`), and **(B) Delete
    folders + move guides to Trash** → guides soft-deleted via the existing
    `/api/jobs/bulk/delete` (trash, NOT hard-delete) before the folders are
    removed. Partial-success aware: failed folders stay selected, successful
    ones disappear, ok/fail (+ trashed count) toasted. **Trash view** gained
    **multi-select** (per-card checkboxes + select-all), **Restore selected**
    (`/api/jobs/bulk/restore`), and **Permanently delete selected** behind a
    strong "cannot be undone" confirm. New backend route **`POST
    /api/jobs/bulk/purge`** loops the existing guarded `purge_trashed_job`
    (operates strictly inside `jobs/.trash/`; no new `rmtree` path) and refuses
    any id not currently trashed. Verified in Docker (smoke 28/28) + curl:
    bulk/purge returns ok for a trashed id and `error: not in trash` for
    bogus / `../escape` / active ids (active job untouched on disk); Option A
    leaves the guide active+Unfiled; Option B lands the guide in Trash and gone
    from active; bulk/restore returns a purged job to active.

12. **Slice C1 — expanded output-section toggles (BACKEND + prompt assembly)** —
    `fe898c4` (branch `style-output-toggles`). Added a real `include_sections`
    dict-of-bool field to `LLMJobRequest`, threaded
    `LLMJobRequest → run_llm_job → generate_study_guide → orchestrator`. Investigation
    first confirmed the pre-existing "module" keys (`mcqs`/`glossary`/… in
    `shortcut_store.KNOWN_MODULE_KEYS` + `frontend/shortcutMeta.js`) were
    **shortcut-only UI state** that **never reached prompt assembly**, so a new
    backend mechanism was required (per the STEP-1 stop rule, confirmed with the
    operator before building). Single source of truth is `INCLUDE_SECTION_FRAGMENTS`
    in `pipeline/orchestrator.py` (21 canonical keys: the 18 target toggles + 3 kept
    legacy keys); legacy keys normalise via `INCLUDE_SECTION_ALIASES`
    (`mcqs→mcqs_with_answers`, `formulas→formula_sheet`, `diagrams→diagrams_figures`).
    **New toggles default off** — an unset/empty/unknown-only map produces a
    **byte-identical** system message (verified: default `== MARKDOWN_MATH_SYSTEM`;
    preset path `== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`). Enabled fragments are
    injected **before** `MARKDOWN_MATH_SYSTEM`, which **remains the final block** in
    both default and preset paths; order is deterministic (insertion order). Unknown
    keys ignored (whitelist convention). `include_sections` is persisted in the job
    manifest so **rerender** reproduces the same sections. Verified in Docker (uid
    10001/appuser): in-container orchestrator proof of fragment presence/ordering for
    7 toggles, a real DeepSeek generation whose guide followed the requested sections
    (Glossary / MCQs+Answer Key / Worked examples / Formula sheet; slide refs
    correctly omitted as the source had none), manifest persistence confirmed; release
    smoke **28/28** (flaky outline-ordering check passed). **Builder UI exposure
    deferred to C3; depth/difficulty/voice deferred to C2; shortcut
    whitelist/persistence extension deferred.** Also documented the prior bulk-purge
    decision in `DECISIONS.md`.

13. **Slice C2 — generation depth + difficulty axes (BACKEND + prompt assembly)** —
    `24442bd` (branch `style-axes`). Added two **optional scalar-enum** global
    generation-directive axes to `LLMJobRequest`: `output_depth`
    (`quick`/`balanced`/`exhaustive`) and `difficulty`
    (`beginner`/`normal`/`exam_level`/`advanced`), threaded
    `LLMJobRequest → run_llm_job → generate_study_guide → orchestrator` (mirroring C1)
    and **persisted in the job manifest** so rerender/retry reproduces them. Source of
    truth: `OUTPUT_DEPTH_FRAGMENTS` / `DIFFICULTY_FRAGMENTS` in
    `pipeline/orchestrator.py`; assembled via `build_axis_directives_block`.
    - **Axes default unset.** With both unset the system message is **byte-identical**
      to before (verified: default `== MARKDOWN_MATH_SYSTEM`; preset path
      `== "{system}\n\n{MARKDOWN_MATH_SYSTEM}"`). Unknown/None axes add no fragment.
    - **Assembly order:** preset system prompt (preset path) → **axes** →
      **include_sections** → `MARKDOWN_MATH_SYSTEM`. Axes inject **before**
      include_sections; `MARKDOWN_MATH_SYSTEM` **remains the final block** in both paths.
    - **`voice` was DROPPED** — STEP-1 found it duplicates the Styles system
      (`baby_steps`/`exam_cram` styles + "blunt voice"/"formal" prompt directives);
      confirmed with the operator. **Voice/tone remains owned by Styles.** `difficulty`
      does **not** duplicate `mode` (mode is vestigial free-text with no difficulty
      semantics).
    - **Validation:** unknown axis values rejected at the API boundary (`HTTP 400`),
      orchestrator ignores unknowns defensively.
    - **Verified in Docker** (uid 10001/appuser, container healthy): in-container
      orchestrator proof of byte-identical no-axes paths + ordering (depth<difficulty<
      sections<MATH); a real DeepSeek generation with `output_depth=quick` +
      `difficulty=exam_level` + `include_sections={glossary, mcqs_with_answers}` whose
      guide showed a definitions table + MCQs/Answer Key (concise, exam-pitched);
      manifest persisted both axes + sections; invalid `output_depth`/`difficulty`
      returned 400. Release smoke **28/28** (flaky outline-ordering check passed).
    - **Builder UI exposure deferred (C3); shortcut persistence bridge deferred.**

14. **Slice — shortcut options persistence bridge (BACKEND ONLY)** — `cc75292`
    (branch `shortcut-options-bridge`). Extended the `builder_setup` shortcut
    payload whitelist (`pipeline/shortcut_store.py:_normalize_payload`) with the
    real C1/C2 generation fields: `include_sections` (canonical dict-of-bool),
    `output_depth`, and `difficulty`. **Closes the "legacy shortcut modules are
    inert" gap at the backend shortcut boundary** — shortcuts can now carry the
    fields that actually reach prompt assembly.
    - **Reuses C1 normalization** — `include_sections` is validated through
      `orchestrator.normalize_include_sections` + `INCLUDE_SECTION_ALIASES`
      (no second alias table); unknown keys dropped, only canonical enabled keys
      stored.
    - **Axes validated, not coerced** — invalid `output_depth`/`difficulty` are
      **rejected** via `ShortcutStoreError` (→ HTTP 400 on create/update; import
      pushes the offending shortcut into the batch `errors` list), never silently
      persisted. Unset → `None`.
    - **Legacy `modules` translate-on-read** — `_bridge_payload` derives
      `include_sections` from legacy `modules` in the **returned/exported**
      representation only (`_public` + `_exportable`); explicit `include_sections`
      wins, legacy modules only fill missing sections. **`shortcuts.json` is never
      rewritten on read** — old shortcuts stay old on disk until the user
      explicitly creates/updates/imports.
    - **Verified in Docker** (uid 10001/appuser, healthy): Test A create/read
      canonical round-trip; Test B export→import-preview→import (fields survive,
      id regenerated on conflict, no silent overwrite); Test C invalid axes → 400
      / import `errors`, unknown section key dropped; Test D legacy modules-only
      injected in-container translated to canonical sections on GET **and** export
      with **identical sha256 before/after** (disk still has no `include_sections`);
      Test E old field-less shortcut loads cleanly, nothing forced. Unit test
      `test_scripts/test_shortcut_store.py` **39/39**; release smoke **28/28**
      (flaky outline check passed).
    - **Builder UI wiring (load fields into Builder state + send to
      `/api/jobs/llm`) is the NEXT slice — NOT done here.**

15. **Slice C3 — expose output sections + axes in the Builder (FRONTEND + 1
    backend form-parser fix)** — `7af9cbd` (branch `builder-options-ui`).
    Surfaces the C1 `include_sections` + C2 `output_depth`/`difficulty` fields in
    the Builder and round-trips them through save/load shortcuts and the local
    draft.
    - **New `frontend/src/sectionMeta.js`** holds the display metadata only:
      21 section toggles in 4 cosmetic groups (Practice/Reference/Exam help/
      Source-aware) + the axis option tables + `normalizeSectionState`/
      `hasEnabledSections`. **The backend owns the key set** — every key mirrors
      `INCLUDE_SECTION_FRAGMENTS`/`OUTPUT_DEPTH_FRAGMENTS`/`DIFFICULTY_FRAGMENTS`
      in `pipeline/orchestrator.py` (verified 1:1, no invented keys). The frontend
      never widens the vocabulary.
    - **Builder UI:** replaced the old free-text `includes` chips with grouped
      `SectionControls` toggles + a new `AxisControls` (two segmented rows, "Auto"
      = unset). Action bar gained Sections + Axes summary chips. Legacy
      `includesToModules`/`modulesToIncludes`/`includeOptions` removed.
    - **Default stays clean:** `buildLlmPayload` omits `include_sections` when no
      section is enabled and omits each axis when unset, so a fresh Builder
      generate request carries none of these fields (and never a `voice` field —
      voice stays owned by Styles). Sections no longer appended as free text in
      `augmentSourceText`.
    - **Save/load shortcut wiring:** `builderStateToPayload` now emits the
      canonical `include_sections` + axes (not the inert legacy `modules`);
      `applyBuilderPrefill` reads them back and re-normalizes sections via
      `normalizeSectionState` (drops keys the Builder no longer exposes).
    - **Local draft parity:** `buildDraft`/`handleRestoreDraft` now persist +
      rehydrate the canonical fields (restore re-normalizes), replacing the old
      `includes` they used to carry. Dirty-state `settingsSignature` already
      covers all three, so changing a section/axis after a generation marks the
      preview stale.
    - **Backend form-parser fix:** the multipart branch of `_parse_llm_request`
      (`api/server.py`) now reads `include_sections` (JSON string → dict) +
      `output_depth`/`difficulty`. **Without this the options were silently
      dropped whenever a generation had attachments** (the no-attachments JSON
      path already worked). See `DECISIONS.md`.
    - **Verified in Docker** (uid 10001/appuser, healthy): frontend build OK; an
      esbuild-bundled harness drove the real `buildLlmPayload`/
      `builderStateToPayload`/`normalizeSectionState` (default omits all 4 incl.
      `voice`; selected sends canonical sections+axes; save→load→generate
      round-trips; unknown keys dropped on load; empty shortcut → `{}`/null).
      Live end-to-end: JSON-path job persisted sections+axes to `job.json`;
      **multipart-path job WITH an attachment persisted `{flashcards,
      formula_sheet}` + `exhaustive`/`advanced`** (proves the fix); default job →
      `{}`/null/null; invalid `output_depth` → HTTP 400. Release smoke **28/28**.
    - **NOT automated — needs manual click-through:** visual layout/spacing of the
      new grouped toggles + segmented axes, and tooltip hover behaviour
      (`InfoTip`/`FieldLabel tip`). DOM presence + wiring are proven; pixel
      layout is not.

16. **Slice C4a — generator preset display metadata + `model_hint` exposure
    (BACKEND ONLY)** — `3820c0c` (branch `preset-metadata`). Added three
    **display-only** descriptive fields to the canonical generator-preset registry
    (`_PRESET_DEFS` in `pipeline/generator_presets.py`) ahead of the preset-card UI:
    `purpose` (short purpose label), `recommended_use` (one-line "best with …"
    guidance), and `model` (clean model-name string for an icon/model chip, distinct
    from the longer prose `model_hint`). All exposed through the **existing**
    `_public()` → `list_generator_presets()` → `/api/options.generator_presets` path —
    **no new endpoint, no schema migration**. `name`/`description`/`provider`/
    `model_hint` already existed and were already exposed; this slice only **added the
    three missing fields**.
    - **`model_hint` exposed as a SOFT advisory only.** Unchanged semantics: the preset
      path only **soft-warns** on a provider mismatch (`generator_preset_warning`) and
      never blocks; the user can still pick any provider+model. C4a adds **no**
      enforcement and **no** hard pin.
    - **Display-only proof (source + grep):** `purpose`/`recommended_use`/`model` appear
      **only** in the registry defs and `_public`, nowhere in `orchestrator.py`/
      `run_llm_job.py`/the `/api/jobs/llm` handler. Generation still reads only `block`
      (→ system prompt), the sampling params, and `provider`/`model_hint`/`name` (warning
      text). `_public` reads the new fields via `.get()` so a preset omitting one
      serializes it as `None` instead of raising. Existing preset ids unchanged.
    - **Verified in Docker** (uid 10001/appuser, healthy): `python -m compileall`,
      `docker compose config/build/up`; `/api/options` shows all three presets carrying
      `purpose`/`description`/`recommended_use`/`model`/`model_hint`/`provider`; a
      full-payload secret scan (`sk-`/`api_key`/`secret`/…) found **no** leak. A live
      `claude_review` generation on DeepSeek completed `done` (no mismatch warning — it
      ran on its tuned provider) and the job manifest recorded `generator_preset:
      claude_review` unchanged, with **none** of the new display fields in the manifest.
      Release smoke **27/28 then 28/28** — the only failure was the **known flaky
      outline-ordering check**, which passed on rerun (pre-existing, depends on LLM
      output order, unrelated to this backend metadata change).
    - **Frontend preset cards / icons / compatibility warning deferred to C4b.** Do not
      hardcode card data in the frontend — it must consume this backend metadata.
    - Also added the permanent `DECISIONS.md` rule: any future `/api/jobs/llm` request
      field must be wired into **both** the JSON and multipart paths and verified in both.

17. **Slice C4b — generator preset cards + soft compatibility warning
    (FRONTEND ONLY)** — `b3d7785` (branch `preset-cards-ui`). Renders the C4a
    generator-preset metadata as preset **cards** in the Builder Style tab and adds
    a soft, advisory model-compatibility warning. **Consumes backend data only** —
    no preset copy is hardcoded; the cards read `name`/`purpose`/`description`/
    `recommended_use`/`model`/`model_hint`/`provider`/`params`/`available` from
    `/api/options.generator_presets` (the **generator** preset list from
    `generator_presets.py`, NOT the purpose/outline `presets.py`).
    - **New `frontend/src/presetMeta.js`** (display/compat helpers only): provider
      id → local SVG icon map (`providerIconFor`), text-badge fallback
      (`providerLabelFor`), and the soft `presetCompat(preset, selectedModel)`
      matcher. Three local SVGs committed under
      `frontend/src/assets/providers/{deepseek,qwen,local}.svg` (Vite resolves them
      to emitted asset URLs — 54–82 KB, above the 4 KB inline limit, so they are
      **separate files**, not JS-inlined). Logos render on a small **white chip**
      because Qwen/Local marks are near-black and would vanish on the dark UI; a
      missing/broken icon falls back to the text badge (`onError` + badge sibling),
      never blocking card render.
    - **Cards** (`GeneratorPresetCard` + rewritten `GeneratorPresetControls`):
      provider icon/badge, `model` chip, preset name, purpose label, description,
      recommended-use ("Best for: …"), selected ring + check. `available:false`
      greys/disables the card per the existing convention. The "None (use style)"
      option is kept. **Selection semantics unchanged** — a card still sets the same
      `generatorPreset` id the old chip selector did; the generate payload is
      untouched.
    - **Soft compatibility warning** replaces the old provider-mismatch note with a
      `model_hint`-vs-selected-model advisory: shown only when a preset is selected
      **and** it has a `model_hint` **and** the selected model is a confident
      non-match. Matching (`presetCompat`) normalises both sides to alphanumeric-only
      tokens and accepts equality/containment against **both** the prose `model_hint`
      **and** the cleaner `model` chip string (so "Gemma 4" rescues the local
      `gemma-4-…gguf` id where the longer prose hint would false-positive). Prefers
      **no** warning when unsure (no hint / unknown model → no warning). Warning copy:
      "This preset is tuned for {model_hint}. It may still work with {selectedModel},
      but {model_hint} is recommended." Plus an InfoTip restating it is advisory.
    - **Advisory-only — never blocks.** The Generate button stays `disabled={running}`
      only (never gated on compat); `buildLlmPayload` sends the user's `model` +
      `generator_preset` independently of the warning. **Proven end-to-end:** a live
      `claude_review` (hint "DeepSeek V4 Pro") generation with the **non-hint**
      `deepseek-chat` model completed `done`; the job manifest recorded
      `generator_preset: claude_review` + `model: deepseek-chat` (the user's choice).
    - **Tooltip priority adjusted** (`sectionMeta.js`): removed tips from the obvious
      controls (MCQs ×2, Flashcards, Glossary) and added/kept them on the less
      obvious ones (TL;DR summary, cram sheet, exam alerts, common mistakes,
      diagrams/figures, solved mock exam, self-test checklist, definitions cheat
      sheet, summary tables, instructor notes) plus the existing
      formula-sheet/worked-examples/citations/slide-refs tips and the new
      model-compatibility tip. Uses the existing `InfoTip` system — no new tooltip
      mechanism.
    - **Verified in Docker** (uid 10001/appuser, healthy): frontend build OK (SVGs
      emitted as separate assets); an esbuild harness drove the real `presetCompat`
      through **10/10** match/mismatch/absent cases (incl. the local-gemma rescue and
      the unsure→no-warning cases) + icon URL/badge fallback; served bundle contains
      the card/warning strings and references all three SVGs (served `200
      image/svg+xml`); `/api/options` unchanged; release smoke **28/28** (flaky
      outline check passed). **C3 controls confirmed intact** in the served bundle
      (axes Exhaustive/Exam-level, sections Cram sheet/Worked examples, Save draft,
      action bar/shortcut/progress markers).
    - **NOT automated — needs manual click-through:** card visual layout/spacing,
      provider-icon visual quality, warning placement/legibility, tooltip hover
      behaviour, overall UX feel.

18. **Slice C4c — add Qwen `qwen3.7-plus` to the model registry (REGISTRY ONLY)** —
    `390060c` (branch `qwen37-plus-model`). Added the model id `qwen3.7-plus` to
    `QWEN_MODELS` in `pipeline/provider_config.py` — the **single source of truth**
    for the Qwen model list surfaced through `/api/options` (`models.Qwen` +
    `provider_details[qwen].available_models`) and enforced by
    `validate_provider_model` (a model must be in `QWEN_MODELS` to be accepted).
    - **Ordering:** inserted at index 1, immediately after `qwen3.7-max`, next to the
      other 3.7-family model. **Default unchanged** — the Qwen default is
      `os.getenv("QWEN_MODEL") or os.getenv("LLM_MODEL") or QWEN_MODELS[0]`, and
      `qwen3.7-max` is still `QWEN_MODELS[0]`, so `default_model` stays `qwen3.7-max`.
      `qwen3.7-max` was not replaced; all six existing Qwen ids remain.
    - **Scope:** registry list only — no Builder UI, preset cards, prompt assembly,
      shortcut store, provider-settings architecture, Local Model Manager, or
      generation-pipeline behaviour changed (beyond now accepting this model id). The
      Builder's static `fallbackProviderDetails` Qwen list (a pre-`/api/options`
      placeholder) was intentionally left untouched — the real, authoritative list
      comes from `/api/options` and now includes `qwen3.7-plus`.
    - **Verified in Docker** (uid 10001/appuser, healthy): `compileall` OK; `compose
      config/build/up` OK; `/api/options` shows `qwen3.7-plus` in `models.Qwen` and
      `provider_details[qwen].available_models` (position 2), `default_model` still
      `qwen3.7-max`, all existing Qwen models present; full-payload secret scan clean.
      **Live generation verified:** a real `provider=qwen` + `model=qwen3.7-plus`
      generation completed `done` (manifest recorded `model: qwen3.7-plus`, 2716-byte
      `clean.md` with genuine study-guide content) — not just options exposure.

19. **Slice C5 — Home/nav cleanup + non-destructive stack merge preview
    (FRONTEND ONLY + preview)** — `7f78542` (branch `home-nav-cleanup`).
    Closes Group C by cleaning the Home page. **Cleanup, not a redesign.**
    - **Duplicate lower "Customize" button removed.** The Home "Pinned shortcuts"
      section head carried a second `Customize` button (`HomeShortcuts.jsx`)
      identical in behaviour to the page-head entry. Removed it; the section head
      now shows just its `<h2>`.
    - **Single primary entry kept:** the page-head **"Customize Shortcuts"**
      button. It calls `setCustomizeOpen(true)` → opens `CustomizeShortcutsModal`
      (the shortcut customization modal). **It does NOT route to Styles** — proven
      in the served bundle (exactly one "Customize Shortcuts" string; the modal is
      the shortcut editor, no Styles navigation on that handler).
    - **Smart Tools:** **already absent from Home** — no Smart Tools UI exists
      anywhere in the frontend (only orphaned `.sg-smart-*` CSS + an unrelated
      `Smartphone` icon import in the unused, never-rendered `TopBar.jsx`). Nothing
      to remove; it was not the sole entry point to anything. Orphaned CSS left
      untouched (cleanup-only, no behaviour change).
    - **Compare Styles:** **already lives in Styles, no move needed.** It is not a
      hardcoded Home button — it exists only as a `compare_styles` *shortcut tool
      type* (`shortcutMeta.js`) that routes to Styles via `TOOL_ROUTES`
      (`DesktopDashboard.jsx`). The Styles workspace **is** the compare surface
      ("Compare built-in prompt presets side by side…", `StylesWorkspace.jsx`,
      verified present in the served bundle).
    - **Home focus preserved:** pinned shortcuts + Recent Guides (`RecentJobsPanel`).
      No "continue last setup / continue last guide" feature exists on Home — there
      was nothing of that kind to preserve.
    - **Scope held:** diff is a single 3-line deletion in `HomeShortcuts.jsx`. No
      backend, Builder, Library, prompt assembly, shortcut store, provider model
      registry, Local Model Manager, provider settings, cancel, or rerender-preset
      code touched.
    - **Verified in Docker** (healthy): frontend build OK; `compose config/build/up`
      OK; `/api/health` ok; `/api/options` still lists **`qwen3.7-plus`** (C4c
      intact) + all three generator presets. Served bundle confirms **C3/C4b not
      regressed** — axes (Exhaustive/Exam-level), section toggles (Cram sheet/Worked
      examples), Save draft, preset cards ("Best for"), and the soft compat warning
      ("tuned for") all present. Release smoke **28/28** (flaky outline-ordering
      check passed).
    - **NOT automated — needs manual click-through:** Home layout/spacing after the
      button removal, the single Customize button opening the modal, Compare Styles
      functioning from the Styles tab, and overall visual polish.
    - **Stack merge preview (non-destructive, `git merge-tree --write-tree`
      chrome-renderer-v1 HEAD):** the stacked chain is **NOT cleanly mergeable** into
      `chrome-renderer-v1` yet — **5 pre-existing conflicts**: `Dockerfile`,
      `api/server.py`, `pipeline/extract.py`, `pipeline/llm_client.py`,
      `requirements.txt`. These are **stack-vs-target divergence, not introduced by
      C5** (C5 only touches `HomeShortcuts.jsx`, which is not in the conflict set).
      No merge was performed, no branch history rewritten, `chrome-renderer-v1`
      untouched. **Recommendation:** the conflicts need a deliberate review/resolve
      pass before merging the stack into `chrome-renderer-v1` — likely the Chrome
      renderer branch and the feature stack both edited the backend/runtime files.
      Group-C feature work itself is sound; this is an integration step, not a C5 bug.

20. **Slice C4d — generator preset card simplification + compatibility polish
    (FRONTEND ONLY)** — `0015e50` (branch `preset-card-polish`). A UI polish/
    correction pass on the C4b preset cards — not a redesign. Still consumes the
    C4a `/api/options.generator_presets` metadata (no hardcoded copy); **no backend,
    registry, prompt-assembly, or shortcut-store change**.
    - **Cards simplified:** removed the dense `description` paragraph and the entire
      **"Best for:" (`recommended_use`) block**. Each card now shows: a large
      provider icon + **bold model-name headline**, the **preset name** directly
      under it, and `purpose` as the single one-line subtitle. Shorter, scan-first.
    - **Identity made prominent:** `ProviderBadge` gained a `size="lg"` variant
      (icon chip `h-12 w-12`, was `h-6 w-6`) paired with the bold model name, so the
      "Gemma 4 → Claude-Exam / DeepSeek V4 Pro → Claude-Review / Qwen 3.7 Max/Plus →
      Claude-Cram" pairing is glanceable. Text-badge fallback kept + enlarged to
      match; missing/broken icon still never blocks the card (`onError`).
    - **`presetModelLabel(preset)`** (new, `presetMeta.js`): returns the backend
      `model` verbatim, except the Qwen 3.7 preset renders **"Qwen 3.7 Max / Plus"**
      (one preset covers both models).
    - **Qwen 3.7 Max/Plus compatibility:** added an explicit, conservative
      compatibility family `["qwen37max","qwen37plus"]` (normalised tokens) in
      `presetCompat`. When the preset's `model`/`model_hint` and the selected model
      are both in the family, the advisory warning is **suppressed**. **Not broadened**
      to other Qwen models (e.g. `qwen3.6-plus` still warns against the 3.7 preset).
      See `DECISIONS.md`.
    - **Advisory stays advisory:** the warning is display-only; Generate is still
      `disabled={running}` only, no auto-switch, the generate payload still sends the
      user's selected model + preset independently. Selection / save-as-shortcut /
      load-shortcut / C3 sections / C2 depth-difficulty / action bar / model badge /
      progress button / dirty-state all unchanged (card render is the only edit).
    - **Verified in Docker** (healthy): frontend build OK; `compose config/build/up`
      OK; `/api/health` ok; `/api/options` unchanged. An esbuild harness drove the
      **real** `presetCompat`/`presetModelLabel` through **9/9** cases — Qwen Max →
      no warn, Qwen Plus → no warn (the fix), `qwen3.6-plus` → warn (conservative),
      Qwen+DeepSeek → warn, DeepSeek/Gemma matches → no warn, empty selection → no
      warn; labels: qwen→"Qwen 3.7 Max / Plus", deepseek→"DeepSeek V4 Pro",
      gemma→"Gemma 4". Served bundle: **"Best for" gone (0 occurrences)**, "Qwen 3.7
      Max / Plus" present, compat "tuned for" warning present, C3/C4b markers
      (Exhaustive/Exam-level/Cram sheet/Worked examples/Save draft/Generator preset)
      intact. Release smoke **28/28** (flaky outline check passed).
    - **NOT automated — needs operator judgment:** whether the new icon size feels
      right, whether the cards are visually balanced, whether the reduced text feels
      appropriate, and whether the one-line `purpose` subtitles read well.

21. **Slice B4 — "Export selected" in the Library bulk bar (FRONTEND ONLY)** —
    `65b9b8f` (branch `library-export-selected`, now on trunk). The Library multi-select bulk toolbar
    (`BulkBar`) gained an **"Export selected"** action between *Move to Unfiled*
    and *Delete*. It reuses the existing `downloadExportBundle` client helper →
    `POST /api/exports/bundle` (the **same** endpoint/contract the Exports center
    uses); **no new export primitive and no backend change**. It sends the
    currently selected **active** Library job ids with `artifacts: ["pdf"]` (the
    `BundleRequest` default); the backend silently skips any selected guide
    lacking a PDF and only 404s if NONE are available. The helper streams the ZIP
    straight into a browser download (same pattern as Exports), so the result is
    surfaced the existing way. New `exporting` state disables the button while a
    bundle is building and when nothing is selected; the button shows a spinner +
    "Exporting…". Success/failure are reported through the existing **toast**
    convention (success names the downloaded filename); **selection is preserved
    on both success and failure** (never cleared on a failed export). Existing
    Move / Move-to-Unfiled / Delete (and Trash Restore/Purge) behavior is
    untouched. Trash exports were **not** added (out of scope). Verified in
    Docker: frontend build OK; `python -m compileall api pipeline` OK; `compose
    config/build/up` OK; `/api/health` ok; `/api/options` unchanged; release smoke
    **28/28**. Focused call-path check (no frontend test runner exists in-repo):
    posting the exact button payload (`{job_ids: <2 active ids>, artifacts:
    ["pdf"]}`) returns a `200 application/zip` with `Content-Disposition:
    attachment`, both guides' `final.pdf`, and `manifest.json`.

22. **Slice — cooperative server-side cancel (BACKEND + FRONTEND)** — `901d44b`
    (branch `server-side-cancel`, now on trunk). Adds a true server-side cancel for in-flight
    generations, completing the progress/cancel/retry triad (progress + retry
    already existed). **Design-first**, cooperative-only — **no process killing,
    no PDF/Chromium-pipeline rewrite.**
    - **Cancel state is a sidecar marker file** `jobs/<id>/cancel.requested`
      (`Job.request_cancel`/`cancel_requested`/`clear_cancel_request`/
      `raise_if_cancelled` in `pipeline/job_manager.py`), deliberately **not** a
      `job.json` field: the running job thread continuously read-modify-writes
      the manifest via `set_stage`/`update`, so a concurrent manifest write from
      the cancel request could be lost. The marker is write-once by the canceller,
      existence-checked by the pipeline → no shared-mutable-file race. Mirrors the
      existing trash-marker pattern.
    - **New terminal status `cancelled`** (distinct from `failed`; `error: null`).
      A new `JobCancelled` signal is raised at safe stage boundaries and caught at
      every pipeline entry point (`run_llm_job`, `run_pasted_text_job`,
      `run_markdown_job`) → set `cancelled`, clear the marker, return the job
      (never classified as a failure).
    - **Checkpoints (`raise_if_cancelled`) only at existing stage boundaries:**
      before extraction, **before the LLM call** (best early exit), **after the LLM
      returns / before render** (skip Chromium), and at the top of
      `run_raw_markdown_pipeline` + before `render_pdf`. **Never** mid-LLM-call,
      mid-Chromium-render, or mid-`save_clean_md`. Honest limitation: cancel = "stop
      at the next safe checkpoint," not instant abort; a cancel during the
      uninterruptible LLM/render wait takes effect when that call returns.
    - **Endpoint `POST /api/jobs/{job_id}/cancel`** (`api/server.py`): writes the
      marker for a running job (`cancelled: true`); **already-terminal jobs are a
      safe no-op** (`cancelled: false`, status echoed, **no marker, artifacts
      untouched**); unknown id → 404. It does **not** set status itself (the running
      thread owns the manifest).
    - **Partial artifacts preserved** — nothing is deleted on cancel; input/source
      stays. **Retry-from-cancelled is intentionally NOT wired** (`retry_failed_job`
      stays gated to `failed`); the Builder keeps its inputs/selections on cancel so
      the user simply re-generates. Documented, deferred.
    - **Frontend** (`BuilderWorkspace.jsx` + `api/client.js`): `cancelJob` client
      helper; the action bar shows a **Cancel** button only while running, enabled
      once the existing job-discovery poller learns the in-flight id (the create-job
      POST is blocking); `cancelled` added to `TERMINAL_STATUSES` so polling stops;
      a cancelled result shows a "Generation cancelled" state and **does not** clear
      the draft/inputs or present a guide.
    - **Verified:** host — `compileall` OK, frontend build OK, focused test
      `test_scripts/test_cancel_job.py` 14/14 (pipeline level). Docker (healthy,
      uid 10001) — same test **22/22** incl. the endpoint via TestClient
      (running→marker+true / done→no-op+no-marker / unknown→404); live curl proof on
      a real `done` paste job (no-op, no marker) + unknown→404; release smoke
      **28/28** (LLM/attachment/outline flows ran). **NOT automated — needs manual
      click-through:** clicking Cancel mid-generation in the live Builder and seeing
      the cancelled state + preserved inputs.

23. **Math/PDF fidelity Slice 1 — page-break guard for display math (CSS-ONLY)** —
    branch `math-display-breaks`. Added `break-inside: avoid;` +
    `page-break-inside: avoid;` to `.guide .katex-display` in **both** the base
    rule and the `@media print` block of `themes/claude_clean.css`, putting display
    math in the same break-protected family as `table`/`pre`/`blockquote`/`img`.
    **Strictly CSS-only** — no `pdf_renderer.py`, Chromium flags, KaTeX bridge /
    HTML renderer, sanitizer, prompts, `@page` geometry, or dependency change.
    Diff is 5 added lines in one file.
    - **New fixture `test_scripts/math_layout_fixture.md`** (inline + long-inline,
      short/long display, aligned block, arrows, display-in-list, display-in-table,
      and ~1 page of filler before a boundary equation). No external API calls.
    - **Honest verification (real Chromium PDF render, old vs. new CSS):** KaTeX
      display math in this pipeline **already renders atomically and never splits
      mid-equation** — a fitting block (incl. a 14-row `aligned`) jumps **whole** to
      the next page in both old and new CSS, at every filler offset tested. KaTeX's
      vlist/positioned-span output exposes no in-equation break points, and
      `.katex-display` already carries `overflow` (scroll container = monolithic).
      The only observed "split" is an equation **taller than the page** (45-row
      probe) — a *forced overflow* `break-inside` cannot prevent. So Slice 1 is
      **defensive/consistency hardening**, not a fix for a reproduced visible split;
      it becomes load-bearing if a later slice removes the overflow clipping.
    - **NOT fixed (deferred, not claimed):** long-equation overflow/clipping
      (cause B, Slice 2), math font-size rationalization (cause C, Slice 3), and
      prompt guidance for multi-line form (cause D, Slice 4). See
      `MATH_PDF_FIDELITY_INVESTIGATION.md` §10.
    - **Verified:** `npm --prefix frontend run build` OK; `python -m compileall api
      pipeline` OK; `docker compose config` OK; `docker compose build` OK; container
      recreated on the new image and **healthy** (`/api/health` `{"ok":true}`, new
      CSS confirmed baked in — 2× `page-break-inside`); `/api/options` OK, no secret
      leak; release smoke **28/28**; plus the before/after PDF render comparison
      above (HTML render shows 22 `.katex-display` blocks, the rule present in base
      + print, no raw LaTeX leaked into `<code>`).

24. **Math/PDF fidelity Slice 2 — long display math overflow/clipping (CSS-ONLY)** —
    branch `math-display-overflow`. Changed the **print** rule for
    `.guide .katex-display` from `overflow: hidden` to `overflow: visible` in
    `themes/claude_clean.css` (the only functional change; `0.9em` print font-size
    left untouched — font rationalization is Slice 3). **Strictly CSS-only** — no
    `pdf_renderer.py`, Chromium flags, KaTeX bridge / HTML renderer, sanitizer,
    prompts, `@page` geometry, or dependency change. Diff is one rule + an
    explanatory comment.
    - **Root cause (confirmed by real PDF renders):** a PDF page can't scroll, so
      the screen's `overflow-x: auto` becoming `overflow: hidden` in print **silently
      discarded** any display-equation content past the ~176 mm content box. KaTeX
      never auto-wraps display math (`white-space: nowrap`), so long single-line
      equations exceeded the box and lost their right tail. With `overflow: visible`
      a too-wide equation is **left-anchored** (readable start always kept) and
      extends into the empty side margin (`@page` has margins only — no
      header/footer/page-number to collide with). Only equations wider than the
      **whole A4 page** still clip, now at the physical edge, not the content box.
    - **Before/after (real markdown→HTML→PDF Chromium path, end-marker probes):**
      `overflow: hidden` clipped the right end-marker at **every** equation length
      tested; `overflow: visible` **keeps** moderate lengths (recovered into the
      margin) and only page-width-exceeding equations still clip. Real
      `test_scripts/math_layout_fixture.md` renders cleanly — long single-line
      equation no longer truncated within the content box; aligned block, arrows,
      display-in-list, and the **sanitized** table case verified **identical**
      before/after (no table/list regression).
    - **Improvement, not a full fix (not overclaimed):** arbitrarily long single-line
      equations cannot be made to fully fit CSS-only (KaTeX won't reflow; aggressive
      font shrink doesn't fit them and re-introduces cramping). Genuine semantic
      multi-line wrapping is **prompt-side (cause D / Slice 4)**; font-size
      rationalization is **cause C / Slice 3**. Both remain deferred. See
      `MATH_PDF_FIDELITY_INVESTIGATION.md` §11.
    - **Verified:** `npm --prefix frontend run build` OK; `python -m compileall api
      pipeline` OK; `docker compose config` OK; `docker compose build` OK; container
      recreated on the new image and **healthy** (`/api/health` `{"ok":true}`, new
      CSS confirmed baked in — print `.katex-display` now `overflow: visible`);
      `/api/options` OK; release smoke **28/28**; plus the before/after PDF render
      comparison above.

25. **Math/PDF fidelity Slice 3 — long-formula prompt guidance (PROMPT-ONLY)** —
    branch `math-formula-guidance`, commit `Guide long formulas into aligned math`.
    This is the **cause D / "Slice 4"** prompt-side work in
    `MATH_PDF_FIDELITY_INVESTIGATION.md` §7 (the doc numbers prompt guidance as
    Slice 4; this task tracked it as Slice 3 — same work). Extended
    `MARKDOWN_MATH_SYSTEM` in `pipeline/orchestrator.py` (the math/table contract
    appended **last** in both the default and generator-preset system messages)
    with a concise rule: avoid very long single-line display equations (they
    overflow PDF page width); break long equations/derivations across multiple
    lines inside `\begin{aligned} ... \end{aligned}`, one step per line, each line
    reasonably short; write prose explanations outside math delimiters — never
    wrap an explanatory sentence in `$...$`/`$$...$$`.
    - **Prompt-only.** No `pdf_renderer.py`, Chromium flags, KaTeX bridge / HTML
      renderer, sanitizer, CSS, `@page` geometry, or dependency change. The new
      text generalizes the existing "prose is not math" rule already in the
      `mcqs_with_answers` section fragment — it does not duplicate or contradict
      it, and does not weaken the existing aligned/table/matrix rules.
    - **Ordering preserved:** a preset's own system prompt stays first;
      `MARKDOWN_MATH_SYSTEM` stays the **final** appended block in both paths.
    - **Improvement, not a fix (not overclaimed):** this shapes model *output* so
      fewer equations are wide enough to hit the §11 clipping limit; it cannot
      reflow an over-wide equation the model still emits. That residual stays the
      deferred CSS/renderer limit. Font-size rationalization (**cause C**) remains
      untouched/deferred.
    - **Verified:** `python -m compileall api pipeline` OK; new
      `test_scripts/test_long_formula_guidance.py` **10/10** (default + preset +
      formula-heavy paths all carry the guidance, math block still last);
      `test_math_regressions.py` OK; `npm --prefix frontend run build` OK;
      `docker compose config`/`build` OK; container **healthy**
      (`/api/health` `{"ok":true}`, `/api/options` OK); release smoke **28/28**.

26. **Page-reference format standardization (PROMPT-ONLY)** — branch
    `page-reference-format`, commit `Standardize page reference prompts`. Manual
    PDF validation showed slide/page citations were inconsistent (`p.20`,
    `p. 20`, `pp. 20-21`, `p.96 − 100`, bare fragments, spaced-dash ranges).
    Tightened the **`slide_page_references`** include-section fragment in
    `pipeline/orchestrator.py` so the model always cites pages in one
    parenthesized format: `(page N)` for a single page, `(pages N-M)` for a
    continuous range, `(pages N, M, P-Q)` for multiple pages/ranges; a normal
    hyphen `-` for ranges (never an en dash or spaced dash). The old loose
    `(p. N)` recommendation was removed and `p.`, `pp.`, `pN`, and bare
    out-of-paren fragments are now explicitly banned.
    - **Prompt-only.** No renderer, sanitizer, CSS, dependency, or pipeline
      change. The fragment is injected via `build_include_sections_block`
      **before** `MARKDOWN_MATH_SYSTEM`; math guidance is untouched and stays the
      final appended block, so there is no conflict.
    - **Verified:** new `test_scripts/test_page_reference_format.py` **21/21**
      (fragment carries the exact format examples + bans; assembled default and
      preset prompts include them; ordering preset<axes<include<math preserved;
      math contract intact alongside page refs); `test_long_formula_guidance.py`
      **10/10** regression; `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build` OK;
      container **healthy** (`/api/health` `{"ok":true}`, `/api/options` OK);
      release smoke pass.

27. **Large-PDF preflight Slice 1 — backend endpoint only** — branch
    `large-pdf-preflight-api`, commit `Add PDF preflight endpoint`. Implements the
    first slice of `docs/LARGE_PDF_PREFLIGHT_DESIGN.md` §10: a **read-only**
    `POST /api/preflight/pdf` that inspects ONE uploaded PDF *before* job creation
    and returns a lightweight verdict — **no UI, no job, no extractor change, no
    OCR, no limit change.**
    - **New helper `pipeline.extract.preflight_pdf`** — opens with `fitz`, reads
      `page_count`, probes a bounded, evenly spaced page sample
      (`_preflight_sample_indices`, default 20) with `get_text("text")` gated by the
      **existing** `_is_meaningful_page_text`, and reuses the **existing**
      `_ocr_available()`. **`_extract_pdf` is untouched** (no behavior change).
      Returns `PdfPreflightResult`; raises new `PdfEncryptedError` (encrypted) /
      existing `ExtractionError` (corrupt).
    - **Endpoint** (`api/server.py`, registered before the static mount): multipart,
      single `file`, **PDF-only** (non-PDF → `400`). Streams to a temp file reusing
      the **existing** `MAX_LLM_ATTACHMENT_BYTES` (15 MB) guard (over-limit → `400`,
      ceiling unchanged); temp file removed in `finally`; inspection runs in a
      threadpool. `_build_pdf_preflight_report` assembles `verdict` (`ok`/`warn`/
      `blocked`) + `warnings[]` + `allowed_actions[]` + echoed `limits{}`.
      **Encrypted/corrupt → `blocked` (with `ok: true`); any other failure (incl.
      PyMuPDF missing on host) → degrades to `ok`** so preflight never blocks a
      processable PDF. `allowed_actions` ∈ {`continue`, `process_first_n`,
      `choose_page_range`, `remove_file`}; **`split_automatically` never emitted**
      (deferred). No secrets/host temp paths in the response.
    - **Env knobs** (`os.getenv`, read once at import; the §4 names):
      `PREFLIGHT_SAMPLE_PAGES`/`PREFLIGHT_WARN_PAGES`/`PREFLIGHT_WARN_SIZE_MB`/
      `PREFLIGHT_OCR_PAGE_LIMIT`/`PREFLIGHT_DEFAULT_FIRST_N`/
      `PREFLIGHT_IMAGE_HEAVY_RATIO`/`PREFLIGHT_TEXT_RATIO`. `MAX_UPLOAD_MB` reported,
      not changed.
    - **Verified in Docker** (healthy): `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build`/`up` OK;
      `/api/health` `{"ok":true}`; `/api/options` unchanged. New
      `test_scripts/test_pdf_preflight.py` **24/24** (helper + endpoint via
      TestClient: text/image-heavy/mixed/encrypted/corrupt/non-PDF-400/oversize-400/
      warn-by-pages; skips cleanly without PyMuPDF). Release smoke **28/28**. Live
      curl: text PDF → `ok`/`full`/`[continue]`; image-heavy → `warn`/`image_heavy`/
      `first_n` + first-N/range/remove actions; non-PDF → `400`; corrupt `.pdf` →
      `blocked`/`[remove_file]`.
    - **Deferred (unchanged):** frontend banner/actions (Slice 2), page-range flow
      into `_extract_pdf` (Slice 3), automatic split/chunk + hybrid OCR dedup
      (Slice 4+). See the design doc's Slice-1 implementation note.

28. **Large-PDF preflight Slice 2 — Builder warning UI** — branch
    `large-pdf-preflight-ui`, commit `Show PDF preflight warnings in Builder`.
    Wires the Slice-1 endpoint into the Builder so a large/scanned/problem PDF is
    surfaced **before** generation. **Frontend + API-client only — no backend,
    extractor, OCR, job, or limit change.**
    - **API client** (`frontend/src/api/client.js`): new `preflightPdf(file)` —
      multipart `POST /api/preflight/pdf`. A non-PDF/oversize/network failure
      rejects via `requestJson`; callers treat any failure as a **soft warning**
      and never block generation.
    - **`AttachmentsPicker`** (`BuilderWorkspace.jsx`): on adding a `.pdf`, calls
      preflight per file and stores `{status, report?}` in a new parent state map
      `attachmentPreflights`, keyed by a stable `attachmentKey` (name+size+
      lastModified). Lives **beside the selected files only** — never persisted to
      a job. Removing a file prunes its entry; "Continue anyway" marks it
      acknowledged.
    - **`PreflightCard`**: quiet for ordinary PDFs (verdict `ok`, no warnings);
      `checking` → spinner; `error` → soft "Could not inspect this PDF; it will be
      processed normally." For `warn` (amber) / `blocked` (red) it shows file size,
      page count, scanned flag, OCR-page estimate, the backend `warnings[]`, and a
      recommended action. Actions: **Continue anyway** (warn only) + **Remove
      file**; **Process first N pages** / **Choose page range** render **disabled
      with a "coming later" note** (Slice 3 builds the real flow).
    - **Generate gate**: `validateInputs` blocks generation when any attached PDF's
      verdict is `blocked` (corrupt/encrypted → must remove/replace). `warn`/`ok`
      never block. A preflight failure never blocks. Builder state/selections are
      preserved on warn/fail.
    - **Verified in Docker** (healthy): `npm --prefix frontend run build` OK;
      `python -m compileall api pipeline` OK; `docker compose config`/`build`/`up`
      OK; `/api/health` `{"ok":true}`; `/api/options` unchanged. Backend contract
      the UI consumes re-confirmed `test_scripts/test_pdf_preflight.py` **24/24**;
      release smoke **28/28**. Live curl: non-PDF → `400`; text PDF →
      `ok`/`text`/`[continue]`. No JS test runner exists in the repo (only an
      asset-verify script); adding vitest/jsdom would be out-of-scope dependency
      work, so the contract is covered by the existing backend test.
    - **Deferred (unchanged):** page-range flow into `_extract_pdf` (Slice 3),
      automatic split/chunk + hybrid OCR dedup (Slice 4+). The "first N" / "page
      range" buttons are intentionally inert affordances until Slice 3.

29. **Large-PDF Slice 3 — page-selection request plumbing** — branch
    `large-pdf-page-selection-plumbing`, commit `Plumb PDF page selections through
    jobs`. Makes PDF page selections **representable, validated, and persisted**
    without changing extraction. **Plumbing only — `_extract_pdf` untouched, no
    page filtering, no active page-range UI.**
    - **Field/shape:** new optional `page_selections` on the LLM request —
      `{filename: [[start, end], ...]}`, **1-based inclusive** (e.g.
      `{"deck.pdf": [[1, 20], [35, 42]]}`). Absent/null/empty ⇒ `{}` ⇒ all pages ⇒
      current behaviour. Chose the flat list-of-ranges form (task brief) over the
      design §5.1 `{mode, first_n, ranges}` object — "first N" is just `[[1, N]]`.
    - **Validation** (`_normalize_page_selections`, raises **400** on bad shapes):
      positive-int `[start, end]` pairs with `start <= end` (`bool` rejected);
      ranges sorted + overlapping/adjacent merged to a canonical spec; bounded by
      `MAX_PAGE_SELECTION_FILES`=20 / `MAX_PAGE_RANGES_PER_FILE`=50. Does **not**
      need the real page count (no clamp yet).
    - **Both paths wired** (DECISIONS.md rule): JSON body via `LLMJobRequest`
      (loose `dict[str, Any]`, normalized at handler) **and** multipart via a JSON
      string in `_parse_llm_request`, mirroring `include_sections`/`outline`.
    - **Persistence:** stored in `job.json` by `run_llm_job` (`page_selections`
      key, default `{}`), echoed by `job_response` (`_safe_page_selections`), and
      **preserved across retry** (re-normalized + re-stored); rerender never
      touches it. **Not** forwarded to `_attach_sources`/extraction.
    - **Frontend:** `buildLlmPayload` adds `page_selections` only when the Builder
      carries a selection; reserved internal `pageSelections` state (default `{}`,
      no control sets it) keeps default requests byte-equivalent; `client.js` sends
      it as a JSON string on the multipart path. No page-range UI yet.
    - **Verified:** `compileall api pipeline` OK; `npm … build` OK; `docker compose
      config`/`build`/`up` OK; `/api/health` `{"ok":true}`; `/api/options`
      unchanged. New `test_scripts/test_page_selections.py` **24/24** (offline:
      LLM + renderer stubbed) — normalizer validation/merge, JSON + multipart
      persistence, default-omits, invalid→400, retry-preserves. Release smoke
      **28/28** (flaky outline-ordering check green on re-run).
    - **Deferred (unchanged):** `pages=` filter into `_extract_pdf` + the picker
      that populates `pageSelections` + enabling the Slice-2 actions (next slice);
      automatic split/chunk + hybrid OCR dedup (Slice 4+).

30. **Large-PDF Slice 4 — PDF extraction honors selected pages** — branch
    `large-pdf-page-selection-extraction`, commit `Filter PDF extraction by
    selected pages`. Makes the persisted Slice-3 `page_selections` finally **change
    what is extracted**: matching PDF attachments are restricted to the selected
    ORIGINAL pages. **Backend/extraction only — no page-range UI, no split/chunk,
    no hybrid OCR dedup, no limit change; `_extract_pdf` extended surgically (not
    rewritten); non-PDF extraction untouched; default (no selection) byte-for-byte
    unchanged.**
    - **`extract_file(path, pages=None)` / `_extract_pdf(path, pages=None)`**
      (`pipeline/extract.py`): `pages` = optional iterable of **1-based ORIGINAL**
      page numbers, **PDF-only** (ignored for every other type). The filter is one
      `if selected is not None and index not in selected: continue` at the top of
      the existing per-page loop, **before** any `get_text`/OCR — so **OCR only ever
      runs on selected pages**. Per-page text-XOR-OCR fallback unchanged.
    - **Original anchors preserved:** the loop still enumerates from 1 and emits
      `## Page {index}` with the *original* number, so selecting pages 20-21 yields
      `## Page 20`/`## Page 21`, **never** renumbered `## Page 1`/`## Page 2`.
    - **Validated against real `document.page_count`:** requested pages are
      intersected with `[1, page_count]`; out-of-range pages are **dropped (not
      clamped)** with a warning naming them; if **no** selected page is in range →
      empty `ExtractionResult("", "pdf_text", [warning])` (no crash), and the caller
      reports "no text could be extracted" exactly as today.
    - **Mode over the subset:** `pdf_text`/`pdf_ocr`/`pdf_mixed` computed from the
      selected pages (text-only subset → `pdf_text`, image-only subset → `pdf_ocr`,
      etc.).
    - **Threading** (`pipeline/run_llm_job.py`): `run_llm_job` → `_attach_sources`
      passes `page_selections`; for **PDF attachments only** it looks the selection
      up by the attachment's **original filename** (`AttachmentSource.filename` =
      the `original_filename` in attachment metadata = the Slice-3/frontend key),
      flattens the normalized `[[start,end],...]` ranges (`_expand_page_ranges`),
      and calls `extract_file(path, pages=...)`. Exact `dict.get` match — no
      fuzzy/index guessing; a selection for an unmatched filename is unused; same
      original filename on two attachments both legitimately get that selection.
    - **Verified in Docker** (healthy): `python -m compileall api pipeline` OK;
      `npm --prefix frontend run build` OK; `docker compose config`/`build`/`up` OK
      (no secret output pasted); `/api/health` `{"ok":true}`; `/api/options`
      unchanged. New `test_scripts/test_pdf_page_selection_extract.py` **39/39**
      (text pages 2-3 → original anchors, no page 1; no-selection == select-all;
      out-of-range safe warning; OCR-gated scanned-subset OCR-only; mixed-subset
      mode correctness; `_attach_sources` filename-keyed threading). Existing
      `test_mixed_pdf_ocr.py` and `test_page_selections.py` both still pass
      (24/24). Release smoke **28/28** (flaky outline check green on re-run). Live
      Docker generation with `page_selections={"sel.pdf": [[2, 3]]}` → the job's
      `input/source.txt` carries only `## Page 2`/`## Page 3` (not `## Page 1`) and
      the manifest persists the selection.
    - **Deferred (unchanged):** the active page-range **UI** picker that populates
      `pageSelections` + enabling the Slice-2 actions (Slice 5); automatic
      split/chunk + hybrid embedded-text + OCR dedup (still §9 deferred).

31. **Large-PDF Slice 5 — page-selection UI is live** — branch
    `large-pdf-page-selection-ui`, commit `Enable PDF page selection UI`. Turns the
    Slice-2 inert "Process first N pages" / "Choose page range" affordances into
    **working** Builder controls that populate `pageSelections`, which the Slice-3
    plumbing already sends and the Slice-4 extractor already honors. **Frontend/UI
    only — no backend, `_extract_pdf`, page-selection validation, upload-limit, or
    dependency change.**
    - **`PreflightCard` actions enabled** (`BuilderWorkspace.jsx`, `warn` PDFs;
      `blocked` still Remove-only). **Process first N** → `{ "<file.name>": [[1, N]] }`
      with `N = limits.default_first_n` (20) **capped by `page_count`** when known.
      **Choose page range** → inline editor parsing `1-20` / `1-20, 35-42` via new
      `parsePageRanges` to `[[1,20],[35,42]]` (**1-based inclusive**, validated:
      positive ints, `start <= end`, sorted; bad token → inline error, no apply;
      exceeding a known `page_count` applies with a soft note — backend/extractor
      drop the extras safely).
    - **Active-selection bar:** a calm green **"Using pages 1-20"** (`formatPageRanges`)
      replaces the amber warning once a selection is set, with **Edit range** +
      **Use all pages** (clears → all pages). The **"coming later"** note/disabled
      buttons are removed.
    - **Per-file, keyed by `file.name`** — the exact backend match key
      (`original_filename`); multiple PDFs each carry their own selection.
      **Removing a file clears its selection** unless a duplicate-named sibling
      remains.
    - **Default unchanged / opt-in:** no selection ⇒ `pageSelections` `{}` ⇒
      `buildLlmPayload` omits `page_selections` ⇒ "all pages" ⇒ byte-equivalent
      request. **Not** persisted to drafts/shortcuts (the attachments it refers to
      aren't either, so it would be orphaned); preflight report still not persisted
      to `job.json`.
    - **Verified** (Docker healthy): `npm … build` OK; `compileall api pipeline` OK;
      `compose config`/`build`/`up` OK (no secret output); `/api/health` `{"ok":true}`,
      `/api/options` unchanged. `buildLlmPayload` payload harness **5/5** (default &
      empty omit; first-N, multi-range, multi-PDF included verbatim); parse-rule
      check **12/12**; served bundle carries the new strings and **no** "coming
      later". `test_page_selections.py` **24/24**, `test_pdf_page_selection_extract.py`
      **39/39**, release smoke **28/28** (transient provider/host hiccups on
      overlapping runs cleared on a clean run after a container restart). Live Docker
      generation with `page_selections={"multi.pdf": [[2, 3]]}` → manifest persists
      the selection and `input/source.txt` carries only `## Page 2`/`## Page 3` (not
      pages 1/4).
    - **NOT automated — needs manual browser click-through:** the warn card's First-N
      button, the inline range editor (valid + invalid input), the "Using pages …"
      bar + Use-all-pages reset, per-file selection with two PDFs, and clearing on
      file removal. DOM strings + payload/extraction wiring are proven; pixel
      layout/hover is not.
    - **Deferred (unchanged):** automatic split/chunk processing + hybrid
      embedded-text + OCR dedup (§9).

32. **Provider Settings Slice 1 — backend store + safe endpoints (BACKEND ONLY)** —
    branch `provider-settings-backend`, commit `Add backend provider settings store`.
    Server-side foundation for in-app provider settings per
    `docs/PROVIDER_SETTINGS_DESIGN.md` §18. **No frontend UI, no Local Model
    Manager, no provider auto-switching, no generator-preset hard-pinning.**
    - **New store** `pipeline/provider_settings_store.py` mirroring the existing
      JSON stores (atomic temp-file + `os.replace`, whitelist parsing, defensive
      load). Two files under a gitignored `config/`: `provider_settings.json`
      (NON-SECRET, `0644`) and `secrets.json` (raw API keys ONLY, `0600`). Raw keys
      live **only** in `secrets.json` — never in the public file, a response DTO, a
      log line, a job manifest, or an export.
    - **Resolver layer** in `pipeline/provider_config.py`: a single
      settings-store → `.env` → built-in-default chain (`_effective_api_key` /
      `_effective_base_url` / `_effective_default_model` + custom-model merge) used
      by both the registry entries and `build_provider_config`. **No store files ⇒
      byte-identical to the old env path** (the migration guarantee). Per-job
      request provider/model still wins; the store only supplies defaults; sampling
      precedence is preset pin → store → env/default (§4b).
    - **Endpoints** (registered before the static mount): `GET /api/provider-settings`,
      `PATCH /api/provider-settings/{provider}` (partial; `api_key` write-only —
      blank = unchanged), `POST /api/provider-settings/{provider}/clear-key`, and
      `POST /api/provider-settings/{provider}/test` (tiny `max_tokens:1` probe, 10s
      timeout, no retries, **no job/artifacts**, classified+redacted errors). All go
      through one redacting serializer (`_settings_to_public_dict`) that has **no key
      field by construction** — it exposes only `configured`, a `key_source`
      (`store`/`env`/`none`), a last-4 `key_hint` (only when len > 4), `base_url_host`
      (host only, userinfo stripped), models, sampling, and `last_test`.
    - **`/api/options` unchanged in shape**; it now derives values from the resolver
      (store → env), so a saved key flips `configured` without any Builder change.
    - **Docker:** `config/` added to `.gitignore` + `.dockerignore`; `./config`
      volume added to compose; `docker-entrypoint.sh` chowns `/app/config` to
      `appuser` so the non-root process can write the store.
    - **Verified** (Docker healthy, uid 10001/appuser): `test_provider_settings_store.py`
      **26/26** (no-store byte-identical; PATCH non-secret → settings.json, key →
      secrets.json `0600` only; blank=no-op; clear-key flips `configured`; bounds
      400s; preset sampling override never repins provider/model). `npm … build` OK;
      `compileall api pipeline` OK; `compose config`/`build`/`up` OK (no secret
      output); `/api/health` `{"ok":true}`; release smoke **28/28**. **Secret-leak
      scan**: the three real configured keys appear in **none** of `/api/options`,
      `/api/provider-settings`, or live PATCH/test responses; live PATCH→GET→test→
      clear-key proven end-to-end against DeepSeek (test probe returns a redacted
      `provider_auth` for a bad key, no raw key in the body).
    - **Deferred (not started — need an explicit slice):** the frontend Providers
      settings page (§11); wiring store `timeout_seconds`/`retry_count`/
      `thinking_default` into the live client (stored + displayed only this slice);
      `fetch-models`; encrypted-at-rest secrets / OS keyring; `.env` import.

33. **Provider Settings Slice 2 — frontend settings UI (FRONTEND + API CLIENT ONLY)** —
    branch `provider-settings-ui`, commit `Add provider settings UI`. The §11
    Providers page consuming the Slice 1 endpoints. **No backend resolver/security
    change, no Local Model Manager, no provider auto-switching, no preset
    hard-pinning, no dependency/lockfile change.**
    - **API client** (`frontend/src/api/client.js`): added `getProviderSettings`,
      `updateProviderSettings(provider, patch)`, `setDefaultProvider(provider)`,
      `clearProviderKey(provider)`, `testProviderSettings(provider, payload?)`. The
      patch is partial; `api_key` is included **only when non-empty** (blank = keep
      current). Nothing reads a raw key back.
    - **New workspace** `frontend/src/components/ProviderSettingsWorkspace.jsx`,
      routed from the existing **Models** sidebar item (the old read-only
      `ModelsPage`/`ProviderCard`/`normalizeModelProviders` in `DesktopDashboard.jsx`
      were removed — that page only read `/api/options`; the new page is the editor).
      One card per provider showing safe fields only (configured pill, `key_source`,
      last-4 `key_hint`, `base_url_host`, default model, custom models, temperature/
      top_p/max_tokens/timeout/retries, qwen thinking, `last_test`).
    - **API key field is write-only**: a password input, never prefilled, empty =
      unchanged, sent only on Save, cleared after Save. **Remove key** button calls
      `clear-key` behind a `window.confirm` (disabled unless `key_source==="store"`).
      **Test connection** shows loading/OK/failure with the server's already-redacted
      message + category + latency only — never a raw key or request body. Base URL is
      a blank-keeps-current override (only the host is ever exposed by the backend).
    - **Resilience:** the Builder still reads `/api/options` independently, so a failed
      `GET /api/provider-settings` only shows a recoverable error + Retry on the
      settings page; generation is unaffected.
    - **Verified:** `npm … build` OK; `compileall api pipeline` OK; `compose config`
      PASS (no secret output); `compose build`/`up` OK; `/api/health` `{"ok":true}`;
      `/api/options` OK; release smoke **27/28** (the one fail is the non-deterministic
      "outline followed in order" LLM-output assertion, unrelated — no backend/pipeline
      code changed). **Secret-leak proof:** PATCHed a sentinel key
      `sk-FAKE-LEAKCHECK-…` on `local` → it appears in **none** of `/api/provider-settings`,
      `/api/options`, the PATCH/test responses, the served `frontend/dist` JS, or the
      non-secret `config/provider_settings.json`; it lived **only** in `secrets.json`
      (`0600`, uid 10001/appuser) and host `cat config/secrets.json` is **Permission
      denied** (expected, supports the model). `clear-key` reverted `local` to
      `key_source:"env"` and removed the sentinel from `secrets.json`.
    - **Deferred (unchanged from Slice 1):** wiring store `timeout_seconds`/
      `retry_count`/`thinking_default` into the live client (now DONE — see #34);
      `fetch-models`; encrypted-at-rest secrets / OS keyring; `.env` import.

34. **Provider Settings Slice 3 — runtime defaults wired into live generation
    (BACKEND ONLY)** — branch `provider-settings-runtime`, commit `Apply provider
    runtime settings` (commit `40df617`). The stored `timeout_seconds`,
    `retry_count`, and `thinking_default` now reach the live model call. **No
    Local Model Manager, no provider auto-switching, no generator-preset
    hard-pinning, no new env knob.**
    - **Mechanism:** `LLMConfig` gained `timeout`/`retry_count` fields, resolved
      in `build_provider_config` (store → default) and consumed in
      `generate_chat_completion`, so **every** path that builds a config via
      `build_provider_config` (study-guide, style, outline, section-regen, quiz)
      picks them up. Timeout: an explicit caller `timeout=` (the test probe's
      short fail-fast value) wins over `config.timeout`; the probe also forces
      `retries=0`.
    - **Retry is transient-only:** bounded `[0,10]`, retries only transient
      API/transport failures (429, 5xx, connection/timeout type-names); **never**
      4xx (auth/model/bad-request), missing config, unsupported provider, or
      cancel. Retry is internal to the single model call (no duplicate
      jobs/artifacts).
    - **Thinking precedence (qwen-only):** explicit request/preset value wins,
      else store `thinking_default` fills, else `True`. `LLMJobRequest.qwen_thinking`
      / the multipart default became `None` so an "unset" field lets the store
      fill, while the Builder still sends an explicit bool ⇒ unchanged UI. This is
      the rule "a preset's explicit sampling/thinking can override the stored
      runtime default; provider/model is never hard-pinned."
    - **Migration guarantee:** no store files ⇒ byte-identical to trunk (timeout
      `None`, 0 retries, thinking `True`).
    - **Verified:** `test_scripts/test_provider_runtime_settings.py` (22 checks) +
      existing `test_provider_settings_store.py` (26) + `smoke_release.py`
      (28/0/0). See `DECISIONS.md` → "Provider runtime settings: timeout/retry at
      the call boundary, transient-only retry".
    - **Deferred (unchanged):** `fetch-models` endpoint; encrypted-at-rest secrets
      / OS keyring; `.env` import; the **Local Model Manager** (separate
      design-first feature); optional Builder "Provider default" thinking UI polish.

35. **Provider Settings Slice 4 — backend fetch-models endpoint (BACKEND ONLY)** —
    branch `provider-settings-fetch-models`, commit `Add provider fetch-models
    endpoint`. Adds the long-deferred read-only model-discovery endpoint. **No
    frontend UI, no Local Model Manager, no provider auto-switching, no
    generator-preset hard-pinning, no dependency/lockfile change.**
    - **Endpoint:** `POST /api/provider-settings/{provider}/fetch-models`,
      registered **before** the static mount, run in a threadpool. Unknown provider
      → **HTTP 400** (existing `_resolve_known_provider`). Returns the stable schema
      `{provider, ok, models, source, base_url_host, error}` — `error` is `null` on
      success or `{category, message}` (redacted) on failure. `base_url_host` is
      host-only (never the full URL).
    - **Fetch (`provider_config.fetch_provider_models`):** resolves the **effective**
      base URL + key (store → `.env` → built-in default) and **reuses the existing
      `_discover_openai_models` `/models` discovery** (the same path `local` already
      used) for **all** providers — DeepSeek/Qwen hit `…/v1/models`, local hits
      `{base_url}/models` (keeping the `host.docker.internal`-only-in-Docker guard).
      A short fail-fast `PROVIDER_FETCH_MODELS_TIMEOUT` (10s) is used; the list comes
      back sorted + de-duplicated. It does **not** call `build_provider_config`, so a
      model-less provider can still list.
    - **READ-ONLY / no auto-persist:** no job, no artifacts; writes neither
      `provider_settings.json` nor `secrets.json`; does **not** add fetched ids to
      `custom_models` (returns them only — saving belongs to the future frontend
      "Refresh models" slice). Provider/model precedence + preset `model_hint`
      advisory behavior unchanged.
    - **Redaction:** the raw key never appears in the response; errors are mapped to
      a coarse category (`provider_auth`/`provider_ratelimit`/`provider_model`/
      `provider_network`/`local_offline`/`provider_error`) and stripped of the key +
      full URL. Unconfigured / no base URL → a **safe non-OK** result (not a 400,
      never the missing-key specifics).
    - **Verified:** new `test_scripts/test_provider_fetch_models.py` **16/16**
      (sorted/deduped success; local uses `/models`; unconfigured safe error;
      401 + network failures classified + redacted, no key leak; sentinel key absent
      from fetch / `/api/provider-settings` / `/api/options`; no file writes / no
      `custom_models`; precedence + preset advisory intact). `compileall` OK; frontend
      build OK; `docker compose config`/`build`/`up` OK, container healthy. Live
      Docker: unknown → 400; local → safe `provider_network` timeout; DeepSeek
      (env-configured) → `ok:true` with the real provider list; a fake key PATCHed on
      `local` appeared in **none** of the fetch / `/api/provider-settings` /
      `/api/options` responses or the container logs (cleared afterward).
      `test_provider_settings_store.py` 26/26, `test_provider_runtime_settings.py`
      22/22, release smoke **28/28**. See `DECISIONS.md` → "Provider fetch-models is
      read-only and does not auto-persist".
    - **Deferred (unchanged):** the frontend "Refresh models" button +
      save-to-`custom_models`; encrypted-at-rest secrets / OS keyring; `.env` import;
      the **Local Model Manager**.

36. **Provider Settings Slice 5 — frontend Refresh Models UI (FRONTEND + API CLIENT
    ONLY)** — branch `provider-settings-fetch-models-ui`, commit `Add provider model
    refresh UI`. Wires the DONE #35 read-only endpoint into the Providers page.
    **No backend resolver/security/store change, no Local Model Manager, no provider
    auto-switching, no generator-preset hard-pinning, no dependency/lockfile change.**
    - **API client (`frontend/src/api/client.js`):** new `fetchProviderModels(provider)`
      → `POST /api/provider-settings/{provider}/fetch-models` (no body). Returns the
      redacted `{provider, ok, models, source, base_url_host, error}` verbatim; never
      reads a raw key.
    - **UI (`ProviderSettingsWorkspace.jsx`):** each provider card gains a **Refresh
      models** button with a loading state. Success renders the fetched ids in a panel
      (`{n} fetched · {m} new`); failure shows only the backend's redacted
      `{category, message}`; an empty list shows a calm "No models returned" state.
      Fetched ids are **review-only** — each *new* id (not already in registry ∪ draft
      custom models) gets a per-model **Add** button, plus **Add all new**; ids already
      present render a non-actionable "in list"/"added" tag (dedupe).
    - **No auto-persist / no auto-switch:** adding only stages an id into the draft
      `custom_models`; nothing is saved until the existing **Save**
      (`PATCH /api/provider-settings/{provider}`) runs. A successful fetch never saves,
      never changes the default model/provider, and editing/refresh/clear invalidates a
      shown fetch list. Builder dropdowns keep reading `/api/options`, which includes
      the saved custom models after Save.
    - **Verified:** frontend build OK; `compileall api pipeline` OK; `docker compose
      config` exit 0 / no stderr (no secret expansion printed); `docker compose
      build`/`up` OK, container healthy; `/api/health` ok, `/api/options` shape intact.
      `test_provider_fetch_models.py` **16/16**, `test_provider_settings_store.py`
      **26/26**, release smoke **28/28** (no outline flake). Live Docker: DeepSeek
      (env-configured) fetch → `ok:true` real list; unconfigured local → safe
      `provider_network`/`provider_config`; a sentinel key PATCHed on `local` appeared
      in **none** of the fetch / `/api/provider-settings` / `/api/options` responses or
      the served JS bundle (cleared afterward); add-a-custom-model → Save → it appears
      in `/api/options` (then restored).
    - **Deferred (unchanged):** encrypted-at-rest secrets / OS keyring; `.env` import;
      the **Local Model Manager**.

37. **Fix — Provider "Test connection" false-negative on empty content (BACKEND
    ONLY)** — branch `fix-provider-test-empty-content`. Resolves validation
    **Finding #1**: `POST /api/provider-settings/{provider}/test` reported
    `ok:false` for reasoning/thinking models (Qwen with thinking, DeepSeek V4 Pro)
    because the `max_tokens=1` probe gets a valid choice with **empty visible
    content**, and `generate_chat_completion` raised "LLM returned an empty
    response."
    - **Fix (narrow):** added an `allow_empty_content: bool = False` kwarg to
      `generate_chat_completion` (`pipeline/llm_client.py`). When `True`, a choice
      with empty/null content returns `""` instead of raising; a response with **no
      choices** still raises on both paths. `test_provider`
      (`pipeline/provider_config.py`) now passes `allow_empty_content=True` —
      nothing else on the probe changed (still `max_tokens=1`, `retries=0`,
      `PROVIDER_TEST_TIMEOUT`).
    - **Scope guard:** normal study-guide generation is **unchanged** — default
      `allow_empty_content=False` keeps it strict so empty/bad model output is
      never silently accepted. No change to provider/model precedence, fetch-models,
      or the frontend.
    - **Verified:** `compileall api pipeline` OK; `test_provider_runtime_settings.py`
      **28/28** (added section 9: probe accepts empty/null content & reports
      `ok:true`; normal generation still rejects empty; a probe 401 still
      `ok:false`; probe result JSON carries no raw key), `test_provider_settings_store.py`
      **26/26**, `test_provider_fetch_models.py` **16/16**, release smoke **28/28**.
      See `DECISIONS.md` → "Provider Test Connection accepts empty content".

38. **Fix — stored `default_provider` precedence was inert (BACKEND ONLY)** —
    branch `fix-default-provider-precedence`. Resolves validation **Finding #2**:
    with no per-request provider, `api/server.py:_pick_generate_provider(None)`
    always picked the **first configured** provider (DeepSeek) and ignored the
    stored provider-settings `default_provider` (e.g. Qwen).
    - **Fix (narrow):** new pure helper
      `provider_config.stored_default_provider_entry(registry)` resolves the stored
      `default_provider` against the registry and returns its public entry **only**
      when it is set, known, and **configured** (else `None`). `_pick_generate_provider`
      consults it in the no-request-provider branch, **before** the first-configured
      fallback. Precedence ladder is now **explicit per-request provider > stored
      `default_provider` > first-configured fallback**.
    - **Scope guard:** an explicit per-request provider still wins (the
      `if provider:` branch is untouched); an unset / unknown / unconfigured stored
      default falls straight through to the historical first-configured behavior.
      The stored `default_model` path is unchanged (request model still wins, else
      the selected provider's effective default_model). Generator presets stay
      advisory — sampling only, never repinning provider/model. No raw key is read
      or exposed by the new path; `/api/options` Builder pre-select left out of scope.
    - **Verified:** `compileall api pipeline` OK; new
      `test_scripts/test_default_provider_precedence.py` **14/14** (stored default
      picked over first-configured; request provider wins; unconfigured/unknown/unset
      default → first-configured fallback; stored default_model used when request
      model absent; request model wins; preset stays advisory; leak-scan clean),
      `test_provider_settings_store.py` **26/26**, `test_provider_runtime_settings.py`
      **28/28**, `test_provider_fetch_models.py` **16/16**. See `DECISIONS.md` →
      "Stored default_provider is a default only".

39. **Shortcut Inspector Slice 1 — backend inspector (BACKEND ONLY, read-only)** —
    branch `shortcut-inspector-backend`. Adds a richer, additive read-only
    validity layer for shortcuts that fixes the three known gaps without changing
    any existing behavior.
    - **Engine (`pipeline/shortcut_store.py`):** `_collect_findings(record)` →
      the **full** list of findings (provider/model/style/preset/section/axis/
      tool/view/legacy/payload-shape), `_status_from_findings` → 3-tier status
      (`error`⇒`broken`, `warning`⇒`degraded`, else `valid`), and `_validity` →
      `{status, findings[], repairable}`. Each finding is
      `{code, severity, field, message, current_value, repairable, candidates?}`
      with stable codes (`provider_missing`, `provider_unconfigured`,
      `model_unavailable`, `style_missing`, `generator_preset_missing`,
      `section_unknown`, `output_depth_invalid`, `difficulty_invalid`,
      `tool_route_missing`, `legacy_field_ignored`, `payload_shape_invalid`,
      `inspection_error`). Candidates come from live **redacted** registries only
      (provider ids/labels/`configured`, provider `available_models`, style ids,
      preset ids, canonical section keys, axis enums) — never a raw key.
    - **Additive field:** `validity` is attached in `_public`, so it rides on
      `GET /api/shortcuts`, `GET /api/shortcuts/{id}`, and import-preview. Legacy
      `valid`/`reason` (from the untouched `_evaluate_validity`) stay byte-compatible.
    - **New route:** `GET /api/shortcuts/{id}/inspect` (read-only) returns
      `{id,name,type,valid,reason,validity,repair_candidates}`; unknown id → 404.
    - **Deliberate divergence (documented):** the new model/section/axis checks
      raise `validity.status` to `degraded` but **do not** flip the legacy
      `valid:true` those shortcuts have today, so the existing activation guard is
      unchanged (see `DECISIONS.md` → "Shortcut inspector Slice 1: legacy `valid`
      stays true for new degraded findings"). Invalid axes are treated as
      **degraded** (ignored/defaulted at load), not broken.
    - **Verified:** `compileall api pipeline` OK; new
      `test_scripts/test_shortcut_inspector.py` **19/19** (valid/degraded/broken
      tiers, model-unavailable degraded with legacy `valid` still true, missing
      style/preset, unknown section, invalid axes, tool/view broken, multiple
      simultaneous findings, `…/inspect` 404, read-only sha256 unchanged, sentinel
      no-key-leak); existing `test_shortcut_store.py` **39/39**,
      `test_provider_settings_store.py` **26/26**. Live in Docker (healthy):
      `…/inspect` on a valid shortcut → `valid`/empty findings; on an injected
      broken+degraded shortcut → `broken` + `[provider_missing, style_missing,
      section_unknown]` with `shortcuts.json` sha256 unchanged; unknown id → 404;
      `smoke_release.py` **28/28**; secret scan clean across
      inspect/list/options/provider-settings + container logs. **No frontend, no
      repair preview/apply, no store refactor in this slice.**

40. **Shortcut Inspector Slice 2 — frontend badges + read-only Inspector drawer
    (FRONTEND + API client + node harness + docs)** — branch
    `shortcut-inspector-ui`. Surfaces Slice 1's `validity` data in the UI.
    **Read-only: no mutation, no preview/apply, no provider/model auto-switch, no
    raw keys; backend behaviour unchanged** (the Slice 1 response shape was
    already correct).
    - **API client (`frontend/src/api/client.js`):** `inspectShortcut(id)` →
      `GET /api/shortcuts/{id}/inspect` via the shared `requestJson` helper (404 /
      network errors surface the server `detail` like the other helpers; the
      already-redacted response never carries a raw key).
    - **Status helpers (`frontend/src/shortcutStatus.js`, pure / no React):**
      `shortcutStatus` prefers `validity.status` and **falls back** for old
      payloads with no `validity` (`valid:false`⇒broken, else valid);
      `statusBadge` (valid→"Valid", degraded→"Needs attention", broken→"Broken"),
      `countFindingsBySeverity`, `issueCount`, `shortcutFindings`. Tolerates
      missing validity, unknown status, non-array findings, null shortcut.
    - **Home cards (`HomeShortcuts.jsx`):** valid stays quiet (no badge); degraded
      → amber "Needs attention" chip, broken → red "Broken" chip; the chip + a
      small Info button open the Inspector (`stopPropagation`, so card activation
      is not triggered). **Activation unchanged** — still gated on the legacy
      `valid` boolean and routed by `DesktopDashboard.handleActivateShortcut`
      exactly as before; broken shortcuts are never auto-routed to Builder/Tools.
    - **Customize rows:** per-row tiered status chip + issue count + an **Inspect**
      icon-button. Create/edit/import/export/reorder/pin/delete untouched; import-
      preview rows left as-is (no saved id to inspect).
    - **Inspector drawer (`ShortcutInspector.jsx`, new):** right-side read-only
      panel; calls `inspectShortcut(id)` on open (seeds header from the list view
      while loading); loading / 404 / network-error states; renders name, type,
      status pill, legacy `valid/reason` (when blocked), every finding
      (code/field/severity/message/current_value/repairable + candidate count), and
      a redacted candidates **summary** (configured-vs-total providers, models per
      provider, style/preset/section/axis counts). States plainly *"Repair actions
      are not available yet. This inspector is read-only."*; the only repair
      control is a **disabled** "Repair (coming next)" button — no Save/Apply.
    - **Verified:** node harness `frontend/scripts/verify-shortcut-status.mjs`
      **25/25** (status normalization, old-payload fallback, finding counts, badge
      labels), wired into `npm --prefix frontend test`. `npm … build` OK;
      `compileall api pipeline` OK; backend `test_shortcut_inspector.py` **19/19** +
      `test_shortcut_store.py` **39/39** unchanged. Docker (healthy): `/api/health`
      ok, `/api/options` ok, live `…/inspect` shape/404 confirmed; real Chromium
      drove the degraded badge → Inspector (findings + candidates + read-only note
      + disabled repair, **no Apply/Save**), the Customize-row Inspect button, and a
      valid shortcut's "No problems found". `smoke_release.py` **28/28**; full
      secret scan (served bundle + inspect/list/options/provider-settings + logs)
      **clean**. **NOT automated — operator judgment:** badge/drawer visual
      polish, spacing, colour legibility.

41. **Shortcut Inspector Slice 3A — backend repair preview + apply endpoints
    (BACKEND ONLY)** — branch `shortcut-inspector-repair-backend`. Adds the safe
    mutation surface the read-only Inspector (Slices 1+2) was built against. **No
    frontend repair UI in this slice — that is Slice 3B.**
    - **Store logic (`pipeline/shortcut_store.py`):** one shared, read-only
      normalizer `_prepare_repair(id, body)` feeds both `preview_repair` (pure —
      returns original + proposed summaries, a field-level `diff`, and the
      resulting `validity`, writing nothing) and `apply_repair` (the **only**
      write). Apply reuses the existing CRUD: `update_shortcut` for `in_place`,
      `create_shortcut` for `clone` — so the whitelist + atomic write + id
      generation all come for free; **no new raw write to `shortcuts.json`**.
    - **Explicit whitelisted patch (NOT arbitrary merge-patch):** body is
      `{mode: in_place|clone, changes{…}, clone_name?}`. `changes` whitelist:
      `provider`, `model`, `style`, `generator_preset`, `output_depth`,
      `difficulty`, `include_sections{remove:[…], set:{k:bool}}`, and
      `remove_fields:[…]` (removable = `model`/`style`/`generator_preset`/
      `output_depth`/`difficulty` — **provider is not removable**). Any unknown
      top-level or change key is **rejected (HTTP 400)** — a mutation boundary, not
      silently ignored. The proposed payload runs through the same
      `_normalize_payload`, so preview == apply and unknown fields never persist.
    - **Validation against LIVE config:** replacement provider must resolve **and**
      be configured; a replacement model is validated against the **repaired**
      provider (provider-in-same-repair wins, else the existing provider; a
      model-only repair with no provider context → 400); style/preset checked for
      existence; axes validated by the store enum; `include_sections.set` keys must
      be canonical/alias keys. All invalid → 400, nothing written.
    - **Routes (`api/server.py`):** `POST /api/shortcuts/{id}/repair/preview` +
      `POST /api/shortcuts/{id}/repair/apply`, registered with the other
      `/api/shortcuts/*` routes (before the static catch-all). Unknown id → 404;
      bad request → 400, both via the existing `_shortcut_error` mapper. Repair
      currently supports `builder_setup` shortcuts only; others → safe 400.
    - **Safety guarantees:** read-only preview (sha256 unchanged), no auto-repair,
      no migration-on-read, no silent overwrite, no provider/model auto-switch
      (preset `model_hint` stays advisory — a model only changes when the caller
      explicitly asks), clone never overwrites (new id; original untouched), and
      **no raw key** read or returned.
    - **Tests:** `test_scripts/test_shortcut_repair.py` **29/29** (preview
      read-only; in-place provider/model repair; clone new-id + original-unchanged;
      unknown-field / invalid provider/style/preset/model/axis/section → error;
      model-provider context; model-only-no-provider → error; remove optional
      field; unknown-section removal; validity recompute; no migration-on-read;
      no key leak). `test_shortcut_store.py` **39/39** + `test_shortcut_inspector.py`
      **19/19** + `test_provider_settings_store.py` **26/26** unchanged.

42. **Shortcut Inspector Slice 3B — frontend repair UI wiring (FRONTEND + API
    client + harness + docs)** — branch `shortcut-inspector-repair-ui`. Wires the
    read-only Slice 2 Inspector drawer to the Slice 3A repair endpoints. **No
    backend change** (the 3A contract was correct as-is).
    - **API client (`frontend/src/api/client.js`):** `previewShortcutRepair`
      (READ-ONLY) + `applyShortcutRepair` (the only write), shared `requestJson`
      conventions, sending the 3A whitelisted patch `{mode, changes, clone_name?}`.
    - **Pure helpers (`frontend/src/shortcutRepair.js`):** `emptyRepairDraft`,
      `buildRepairPayload` (drops empty `replace` values so a half-finished choice
      never mutates), `draftSignature` (preview-staleness), `draftHasChanges`,
      `modelCandidatesForProvider`, `effectiveProvider`, `defaultCloneName`,
      `repairFieldKey`. The frontend never widens the backend field/op vocabulary.
    - **Inspector (`ShortcutInspector.jsx`):** the disabled "Repair (coming next)"
      footer becomes an enabled repair panel **only** for a repairable
      `builder_setup` with a supported action — else "No repair needed." / "No
      supported repair action for these findings." (no Apply). Per repairable
      finding: provider/model/style/preset/depth/difficulty Keep / Replace /
      Remove selects (model filtered by the selected/repaired provider; **provider
      not removable**) + per-key Remove toggles for unknown `include_sections`
      keys. Mode selector (in-place / clone) + clone-name input (default `"{name}
      (repaired copy)"`). **Preview** shows the proposed mode, field diff, resulting
      status, warnings, and "original unchanged until apply". **Apply** is disabled
      until a **fresh** preview exists for the current draft (editing the draft
      marks the preview stale → Apply re-disabled) and requires an explicit confirm
      whose copy differs in-place vs clone. On success: refresh the parent list
      (`onRepaired` → `reload`/`refresh`) + re-inspect in place.
    - **Safety held:** no repair call on open; draft starts empty; no apply without
      a fresh preview + explicit confirm; no provider/model auto-switch; tolerant
      of missing candidates / unknown codes / old payloads. **Activation behaviour
      unchanged** (still gated on legacy `valid`; broken never auto-routed; degraded
      still launchable).
    - **Verified:** `python -m compileall api pipeline` OK; backend
      `test_shortcut_repair.py` **29/29** + `test_shortcut_inspector.py` **19/19** +
      `test_shortcut_store.py` **39/39** (unchanged); `verify-shortcut-repair.mjs`
      (new) + `verify-shortcut-status.mjs` green (`npm --prefix frontend run
      test:shortcuts`); frontend build OK; Docker healthy. Live repair flow proven
      via the API in-container (broken → inspect broken/repairable → preview leaves
      the list byte-identical → apply in-place keeps id + flips to valid → clone
      makes a new id and leaves the original broken → invalid provider → 400).
      Release smoke **28/28**. Secret scan (served bundle + inspect/preview/apply/
      list/options/provider-settings + container logs) clean — 0 API-key leaks.
    - **NOT automated — needs manual click-through:** the drawer's visual layout,
      the live Preview→Apply UX in a browser, and the degraded-activation
      confirm/"Repair instead" Home path (deferred — see below).

43. **Shortcut Inspector — degraded-activation confirm + "Repair instead"
    (FRONTEND ONLY + harness + docs)** — branch
    `shortcut-inspector-degraded-activation`. Closes the design §5.5 gap that
    Slice 2/3B deliberately deferred: a **degraded** shortcut used to launch
    silently because legacy `valid === true`. **No backend change, no new repair
    logic, no bulk/auto repair.**
    - **Pure gating (`frontend/src/shortcutStatus.js`):** new `activationDecision`
      → `"launch" | "confirm" | "blocked"`. Legacy `valid === false` is still the
      hard guard (always `blocked`); `validity.status === "broken"` blocks; a
      degraded-yet-launchable shortcut (`status === "degraded"`, `valid !== false`)
      returns `confirm`; everything else (valid / old payload with no `validity`)
      returns `launch`. Pure + node-testable; the component duplicates no status
      logic.
    - **Home wiring (`HomeShortcuts.jsx`):** every card launch routes through a
      `requestActivate` gate. **Valid → launches immediately** via the unchanged
      `onActivateShortcut` path (no prompt). **Degraded → a confirm dialog**
      (shortcut name, "Needs attention · N issues found", top finding messages
      capped at 3, "some saved settings may be ignored or replaced by defaults")
      with **Continue anyway** (calls the original launch path, **no mutation**) /
      **Repair instead** (opens the existing `ShortcutInspector` drawer focused on
      that shortcut — **no preview/apply** until the user acts) / **Cancel** (no
      launch). **Broken → a "This shortcut is broken." dialog** offering **Inspect /
      Repair** (opens the Inspector) or Cancel — it no longer silently routed
      anywhere, and never routes to Builder/Tools.
    - **Safety held:** Continue anyway never repairs/modifies; Repair instead only
      opens the Inspector (reusing the single existing drawer, not a second
      system); no preview/apply call happens until the user uses the existing
      repair UI. Existing Home/Customize 3-tier badges + the repair preview/apply
      flow are unchanged.
    - **Verified:** `python -m compileall api pipeline` OK; backend
      `test_shortcut_store.py` **39/39** + `test_shortcut_inspector.py` **19/19** +
      `test_shortcut_repair.py` **29/29** (unchanged); new node harness
      `verify-shortcut-activation.mjs` (10/10, wired into `npm --prefix frontend
      run test:shortcuts` alongside the status + repair harnesses) covers
      valid→launch, degraded→confirm, broken→blocked, the legacy-guard-wins cases,
      and the missing-`validity` fallback; frontend build OK; `docker compose
      config/build/up` OK; `/api/health` ok; `/api/options` unchanged; release
      smoke **28/28**. Secret scan (served bundle + shortcut list/inspect + repair
      preview/apply + `/api/options` + `/api/provider-settings` + container logs)
      clean — the only env-value matches are **non-secret** model ids / base URLs,
      **0 API-key leaks**.
    - **NOT automated — needs manual click-through:** clicking a degraded card and
      seeing the confirm before launch, Continue anyway launching, Repair instead
      opening the Inspector repair UI, Cancel doing nothing, and the broken dialog.

44. **Shortcut Edit modal generator-preset fix + opt-in "Save prompt with
    shortcut" (FRONTEND + backend whitelist + tests + docs)** — branch
    `shortcut-prompt-save-and-preset-fix`.
    - **Part A — bugfix (root cause):** the Shortcut Edit modal's **Generator
      Preset** dropdown was sourced from `getPresets()` → `/api/presets`, which is
      the **Outline quick-template** registry (`pipeline/presets.py`: Exam Cram /
      Academic Report / Presentation / Chapter Summary / Final Revision) — a
      *different* registry from the real **generator presets**
      (`pipeline/generator_presets.py`: `claude_exam` / `claude_review` /
      `claude_cram`, exposed at `/api/options.generator_presets` and used by the
      Builder Style tab). The modal therefore saved outline-template ids into
      `payload.generator_preset`, which the Inspector then flagged
      `generator_preset_missing`. **Fix:** the modal now loads
      `options.generator_presets` (canonical source, same as Builder) and renders
      via a new pure `generatorPresetOptions(presets, current)` helper in
      `shortcutMeta.js` — leads with **None** (empty id → clears), shows the real
      presets, and appends any **legacy/invalid stored id** (incl. a mis-saved
      outline id) as a trailing **"… — unavailable"** option so old shortcuts load
      without crashing and **without being rewritten on read** (only changes if the
      user picks another option and saves). Builder Style preset cards and Builder
      Outline quick-templates are **unchanged** (the Outline flow still uses
      `getPresets()`).
    - **Part B — opt-in saved prompt/source text:** a builder_setup shortcut may
      now optionally carry the typed **source prompt/text** under a whitelisted
      `saved_prompt` field. **Opt-in only, default OFF.** The Builder "Save as
      shortcut" button opens a small dialog (name + checkbox *"Save prompt/source
      text with this shortcut"*, with a live char count); the Home Customize edit
      modal shows/edits/removes an existing saved prompt and badges rows + import
      preview with **"Saved prompt"**. Only **typed source text** is saved — never
      uploaded files / attachments / page selections / file paths. Size limit
      **100 000 chars** (`MAX_SAVED_PROMPT_CHARS`, mirrored in front+back); oversized
      is **rejected** (HTTP 400 on create/update, skipped on import), not truncated
      silently. Backend (`pipeline/shortcut_store.py`): `_clean_saved_prompt` +
      whitelist add (key **omitted** when empty so config-only shortcuts never grow
      it), an **info-only** inspector finding `saved_prompt_included` (carries the
      **length, never the text**; does **not** affect validity), and export/import/
      repair round-trip (bridge copies the key, repair re-runs the same whitelist).
      **Builder prefill is implemented:** applying a shortcut with `saved_prompt`
      prefills the Builder source text.
    - **Verified:** `python -m compileall api pipeline` OK; `test_shortcut_store.py`
      **53/53** (extended: omit-when-absent, persist, export/import + preview
      round-trip, oversized-reject, at-limit-accept, remove-on-update, info-marker
      length-not-text), `test_shortcut_inspector.py` **19/19**,
      `test_shortcut_repair.py` **29/29**; new node harness
      `verify-shortcut-form.mjs` (wired into `test:shortcuts`) covers the preset
      source/canonical-id/legacy-safe cases + saved-prompt opt-in/clamp/strip;
      frontend build OK; `docker compose config/build/up` OK; `/api/health` ok;
      `/api/options.generator_presets` = `['claude_exam','claude_review','claude_cram']`
      (no outline ids); release smoke **28/28**; live API round-trip of a shortcut
      with `saved_prompt` (valid:true, info marker, export carries it, inspect does
      **not** echo the text). Secret scan (served bundle + `/api/options` +
      `/api/provider-settings` + shortcut list/inspect + container logs) clean —
      **0 API-key leaks**; saved prompt is **user content**, opt-in, never silent.
    - **NOT automated — needs manual click-through:** the Builder save dialog
      checkbox (off by default; export with/without prompt), the edit-modal
      "Saved prompt" badge + remove, and the dropdown showing only real presets.

45. **Local Model Manager — DESIGN (LMM Slice 1, DOCS-ONLY)** — branch
    `local-model-manager-design`. A design-first slice for a *Local Model Manager*
    (LMM) that helps the operator run and use a local OpenAI-compatible model server
    (llama.cpp / `llama-server`) from inside the app. **No code written** — design
    doc + doc reconciliation only.
    - **New `docs/LOCAL_MODEL_MANAGER_DESIGN.md`** covering: (§1) the **current
      `local` provider behavior** read from live code — base-URL resolution chain
      (`_effective_base_url("local")` = store → `LOCAL_LLM_BASE_URL`/`LLM_BASE_URL`,
      **no built-in fallback** so an unset base URL ⇒ not-configured), how
      `/api/options` discovers local models (`_discover_openai_models` GET
      `{base}/models`, 1.5 s), how `fetch-models` reuses the same discovery (10 s,
      read-only, no persist), the offline behavior (discovery returns `([], str(exc))`;
      the `host.docker.internal`-outside-Docker guard), and the **`local_offline`**
      error category (generation path via `classify_exception`; fetch-models via
      `_classify_fetch_error`). (§2) **Architecture options A–D**: A detection-only,
      B host companion launcher, C in-container llama-server, D direct Docker→host
      spawn. (§3) **Recommended staged approach** — Phase 1 detection-only, Phase 2
      optional host companion, Phase 3 optional packaged desktop. (§4) **Phase 1
      backend API** — read-only `GET /api/local-model/status` + `POST
      /api/local-model/check` with a safe DTO (base-URL host, reachable, latency,
      model count/list, default model, classified error, start instructions). (§5)
      **Phase 1 frontend** — a Local Models view (status card, host display + link to
      Providers, Refresh, discovered models, "how to start llama-server" copy
      command, offline/troubleshooting states, Start/Stop omitted or disabled
      "Planned"). (§6) model-file management deferred (no GGUF browsing in Phase 1).
      (§7) security model. (§8) process lifecycle for Phase 2/3. (§9) a llama.cpp
      **command-profile schema** (not a hardcoded command). (§10) future Ask Your
      Guide local-only chat dependency. (§11) the LMM Slice 1→6+ plan. (§12) risks.
      (§13) recommendation.
    - **Recommendation: detection-first.** Phase 1 (Option A) reuses the existing
      local provider + fetch-models and crosses **no** container boundary;
      **Option D (direct Docker→host process spawn) is REJECTED** (a non-root,
      `no-new-privileges` container cannot safely/reliably manage host processes —
      it would need the Docker socket / `--privileged` / host PID namespace, which
      destroys the security model); process control, if ever wanted, goes through a
      host companion (Option B). Option C (in-container llama-server) is not the
      default (GPU passthrough / image size / mounts). **No second writer for
      provider config** — config edits stay on `PATCH /api/provider-settings/local`.
    - **Scope held:** no backend process spawning, no frontend UI, no provider-
      settings change, no generation-pipeline change, no Docker-config change, no
      llama.cpp integration code touched (read-only investigation), no dependencies,
      no raw key / full URL anywhere. Diff is **docs-only**.
    - **Doc reconciliation:** `CURRENT_TASK.md` (this entry + the NEXT block →
      LMM Slice 2), `NEXT_CHAT_HANDOFF.md` (LMM is design-only; next slice is
      detection-only backend status), `PROJECT_CONTEXT.md` (LMM is planned/design-
      first, not implemented), `DECISIONS.md` (detection-first + Option D rejection).
    - **Verified:** docs-only diff (`git diff --name-only` lists only the five docs);
      `python -m compileall api pipeline` OK (code opened read-only for the §1
      investigation; **none changed**). No Docker run required (no code touched).

46. **Local Model Manager — Slice 2: detection-only backend status endpoint
    (BACKEND ONLY)** — branch `local-model-status-api`. A safe, **read-only** status
    API for the configured `local` OpenAI-compatible server. Per design §4 + §11.
    - **New route `GET /api/local-model/status`** (+ a thin `POST
      /api/local-model/check` alias for the frontend "Refresh" verb — same probe,
      no new behavior). Both registered in `api/server.py` **before** the static SPA
      mount and run through `run_in_threadpool` like the existing test/fetch routes.
    - **New `get_local_model_status()` in `pipeline/provider_config.py`** — resolves
      the effective local base URL via the existing `_effective_base_url("local")`
      chain (store → `LOCAL_LLM_BASE_URL`/`LLM_BASE_URL`, no built-in default),
      probes `{base}/models` with a fail-fast 10 s timeout reusing
      **`_discover_openai_models`** (the same single discovery path as fetch-models),
      and returns the §4.2 DTO: `{ok, provider, configured, base_url_host,
      base_url_configured, in_docker, reachable, models, model_count, default_model,
      selected_model, latency_ms, error, actions, notes}`. Models are merged with
      stored `custom_models` exactly like `_local_entry`; `selected_model` resolves
      `default → first discovered`.
    - **`ok` ≠ reachable.** `ok:true` means the **status request** succeeded; the
      live server state is in `reachable`/`error`. Offline, no-base-URL, and
      malformed-URL are all **normal status results** (HTTP 200), never a crash.
    - **Error normalization:** a new `_classify_local_status_error` collapses **all**
      connection failures (refused / timed out / DNS / the out-of-Docker
      `host.docker.internal` guard) to a single **`local_offline`** (design §1.6),
      while genuine auth/model errors keep `provider_auth`/`provider_model`. No-base-
      URL uses `provider_config` (matching fetch-models). Messages pass through the
      existing `_safe_fetch_message` (raw key redacted, full URL collapsed to host,
      length-capped).
    - **Safety held:** no process spawn / start / stop / PID; no file or GGUF
      browsing; no command execution; **no writes** (provider settings, secrets,
      jobs, artifacts all untouched — provider config writes stay on
      `PATCH /api/provider-settings/local`); **no raw key** (no key field by
      construction); **host-only URL** via `_base_url_host` (drops userinfo/port/
      path/query). `actions` advertises `open_provider_settings` (enabled) and
      `copy_start_command` (**disabled**, "planned for a later slice" — no enabled
      control that does nothing); `notes` surfaces the `--host 0.0.0.0` gotcha only
      when the host is `host.docker.internal`. No new dependencies; no Docker-config,
      renderer, prompt, or pipeline changes.
    - **Tests:** new `test_scripts/test_local_model_status.py` (**17/17**) — reachable
      (sorted/de-duped models + count + latency), offline → `local_offline` + null
      latency, unconfigured (no base URL), malformed URL (redacted, no crash),
      host-only (no full URL/userinfo/query), sentinel key never in the response,
      no-write (settings/secrets unchanged, id not auto-persisted), and the action
      descriptors. Existing `test_provider_fetch_models.py` (16/16),
      `test_provider_settings_store.py` (26/26), `test_provider_runtime_settings.py`
      (28/28) all still pass.
    - **Verified:** `compileall` OK; `npm run build` OK; `docker compose config`
      exit 0; image built; container **healthy**. Live with **no** local server:
      `GET /api/local-model/status` and `POST /api/local-model/check` return HTTP 200
      with `reachable:false`, `error.category:"local_offline"`, `latency_ms:null`,
      and the `--host 0.0.0.0` note. `/api/options` 200; release smoke **28/28**.
      Secret scan clean — no configured key, `sk-` token, full URL, or userinfo in
      `/status`, `/options`, or `/provider-settings`; container logs carry 0 key
      tokens. **No live local server required for the automated tests** (urllib
      `urlopen` is monkeypatched; `/.dockerenv` faked).

47. **Local Model Manager — Slice 3: Local Models status panel (FRONTEND)** —
    branch `local-model-status-ui`. The §5 read-only operational view over the
    Slice 2 endpoints. Frontend + API client + docs/tests only; **no backend,
    Docker, pipeline, renderer, prompt, or provider-write changes.**
    - **API client helpers** (`frontend/src/api/client.js`): `getLocalModelStatus()`
      (`GET /api/local-model/status`, page-open read) and `checkLocalModelStatus()`
      (`POST /api/local-model/check`, the "Refresh" verb). Both go through the
      existing `requestJson`; neither sends a body, writes, or mutates settings.
    - **Pure status helpers** (`frontend/src/localModelStatus.js`, mirrors
      `shortcutStatus.js`): `localServerState` normalizes the DTO into
      `reachable | offline | not_configured | error | unknown` (reachable wins;
      `base_url_configured:false` or `provider_config` → not_configured;
      `local_offline` → offline; other classified error → error; not-reachable with
      no info → calm offline; missing/garbage status → unknown). Plus `stateBadge`
      (label + CSS-agnostic `tone`), `statusModels`/`statusModelCount`,
      `modelChips(limit=12)` (bounded list + overflow count), `statusLatencyMs`,
      `statusErrorMessage`, `statusNotes`, `statusActions` (enabled **only** when
      explicitly `true`), `findAction`, and `hasEnabledProcessControl` (the
      invariant guard). **Tolerates missing fields and an old backend.**
    - **Panel** (`frontend/src/components/LocalModelsPanel.jsx`): a rounded card
      with a live status pill, host-only base URL + in-Docker flag, a 4-up metrics
      strip (latency / models / default / selected), bounded model chips
      (selected highlighted, `+N more` overflow), a redacted offline/error message,
      a **first-class** offline/not-configured troubleshooting block (start the
      server, confirm `…/v1/models`, the `--host 0.0.0.0` Docker-host note, then
      Refresh), backend `notes`, a **Refresh status** button (loading state, calls
      `/check`, never saves/starts), an "Edit local provider settings" link, and the
      disabled **Copy start command — Planned** chip from the backend `actions`. If
      the status **request** itself fails (e.g. an old backend with no endpoint) it
      shows a calm "status unavailable" state instead of crashing.
    - **Providers integration** (`ProviderSettingsWorkspace.jsx`): the panel mounts
      under the provider cards; the edit link scrolls the `#provider-card-local`
      card into view with a brief `sg-card-flash` highlight (cosmetic CSS only).
      Providers stays the **single writer** — the panel never edits the base URL or
      model inline. No second nav item; lives on the existing **Models** page.
    - **Safety:** read-only; no start/stop/restart/process control anywhere
      (`hasEnabledProcessControl` is asserted false); no raw key or full URL (only
      the backend's host-only `base_url_host`); no stack traces; status never stored
      in shortcuts/jobs; selected provider/model never auto-changed. No new deps.
    - **Tests:** new `frontend/scripts/verify-local-model-status.mjs` (**47/47**,
      wired as `npm run test:local-model-status`) — state normalization (incl.
      missing-fields fallbacks), badge label/tone, model count + 12-chip display
      limit/overflow, latency/error/notes accessors, action enabled/disabled
      mapping, and the no-enabled-process-control invariant. Backend suites
      unchanged: `test_local_model_status.py` (17/17),
      `test_provider_fetch_models.py` (16/16), `test_provider_settings_store.py`
      (26/26).
    - **Verified:** `compileall` OK; `npm run build` OK (1601 modules); harness
      47/47; `docker compose config` exit 0; image built; container **healthy**.
      Live with **no** local server: `GET /api/local-model/status` returns HTTP 200
      `reachable:false`, `error.category:"local_offline"`, `latency_ms:null`,
      host-only `host.docker.internal`, and the `--host 0.0.0.0` note (panel renders
      the calm offline state). `/api/options` 200; release smoke **28/28**. Secret
      scan **clean** — no `.env` key value in the served JS bundle, `/status`,
      `/options`, or `/provider-settings`; container logs carry 0 key tokens.

48. **Local Model Manager — Slice 4: command-helper profiles / Copy start command**
    — branch `local-model-command-helper`. The §9 command-profile helper: a safe,
    copyable `llama-server` start command the operator runs **manually** outside the
    app. **Command helper only — the app never executes it; no process spawn,
    start/stop, host companion, GGUF scan, or arbitrary shell.** No Docker, pipeline,
    renderer, prompt, large-PDF, or Shortcut Inspector changes; no provider-write
    behavior change; no new deps.
    - **Backend** (`pipeline/provider_config.py` + `api/server.py`): read-only
      `GET /api/local-model/command-profile` → `get_local_model_command_profiles()`.
      Response: `{ok, provider, in_docker, base_url_host, profile, profiles[],
      notes[]}`; each profile `{id, label, description, command, argv[],
      placeholders{model_path}, warnings[]}`. Two static profiles:
      `llama_server_default` (GPU offload, `--n-gpu-layers 999`, `-c 8192`) and
      `llama_server_cpu` (CPU only, `-c 4096`), both `--host 0.0.0.0 --port 8080`.
      `argv` is built from a **fixed flag whitelist** with literal values; the only
      substitution token is `{model_path}` → the placeholder `/path/to/model.gguf`
      (no host filesystem read, no request input). The display `command` is rendered
      from `argv` via `shlex.quote`. **No subprocess/spawn anywhere; no raw key;
      host-only URL.** `--threads`/`--flash-attn` intentionally omitted from defaults.
    - **Frontend**: `getLocalModelCommandProfile()` client helper + pure
      `frontend/src/localModelCommand.js` (`normalizeProfile`, `commandProfiles`,
      `defaultProfile`, `profileById`, `commandAvailable`, `copyButtonLabel`,
      `commandNotes`) + a `CommandHelper` block in `LocalModelsPanel.jsx`: profile
      chips (when >1), a selectable command code block, a **Copy command** button
      (`navigator.clipboard` + manual "select & copy" fallback on failure), the
      static warnings, and "run on your host… then Refresh status." **Prominent**
      (expanded) when offline/not-configured, **secondary** (collapsed `<details>`)
      when reachable. The deferred `copy_start_command` "Planned" chip is suppressed
      (the real helper supersedes it); the Slice 2 status DTO is unchanged. **No
      Start/Stop button; nothing executes.**
    - **Tests:** new `test_scripts/test_local_model_command_profile.py` (**13/13**) —
      shape, placeholder path, host/port, warnings, no-key + no-URL leak with a stored
      key, no-write, no-spawn (source inspection + `subprocess.Popen` monkeypatch
      trip), status unchanged. New `frontend/scripts/verify-local-model-command.mjs`
      (wired as `npm run test:local-model-command`) — normalization/selection, copy
      gating, deterministic command, warnings/notes, label states, no execute/start
      export. Slice 2/3 suites unchanged: `test_local_model_status.py` (17/17),
      `verify-local-model-status.mjs` (47/47), `test_provider_fetch_models.py`
      (16/16), `test_provider_settings_store.py` (26/26).
    - **Verified:** `compileall` OK; `npm run build` OK; harnesses green; Docker
      build + container **healthy**; `GET /api/local-model/command-profile` 200 with
      the placeholder command; `/api/local-model/status` + `/api/options` 200;
      release smoke green. Secret scan **clean** — no key in the endpoint, served JS,
      `/options`, `/provider-settings`, or container logs.

49. **Local Model Manager — Slice 5: Phase-1 validation / docs reconciliation
    (DOCS-ONLY)** — branch `docs-validate-local-model-manager-phase1` (cut from
    `chrome-renderer-v1` @ `e399f09`). A verification + docs pass over the whole LMM
    Phase 1 (Slices 1→4). **No feature work, no refactor, no process spawn, no
    start/stop, no host companion, no GGUF browsing, no Docker config change, no
    provider-settings write-behavior change. No code changed.**
    - **Deliverable:** new `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md` +
      reconciled `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`, `PROJECT_CONTEXT.md`,
      `LOCAL_MODEL_MANAGER_DESIGN.md`. No `DECISIONS.md` change — validation surfaced
      no non-obvious rule not already recorded.
    - **Static checks PASS:** `compileall` OK; `test_local_model_status.py` 17/17;
      `test_local_model_command_profile.py` 13/13; `test_provider_fetch_models.py`
      16/16; `test_provider_settings_store.py` 26/26; `npm run build` OK;
      `npm run test:local-model-status` + `npm run test:local-model-command` green.
    - **Docker/smoke PASS:** `compose config`/`build`/`up` OK (container **healthy**);
      `/api/health` `{"ok":true}`; `/api/local-model/status`, `/command-profile`, and
      `/api/options` all 200; release smoke **28/28**.
    - **Live API PASS (no local server running):** `/status` → 200, `ok:true`,
      `reachable:false`, `error.category:"local_offline"` (redacted message), no raw
      key, host-only URL, `copy_start_command` disabled. `/command-profile` → 200 with
      both whitelisted profiles, the `/path/to/model.gguf` placeholder, `--host
      0.0.0.0 --port 8080`, no real host paths, no secrets, no execution.
    - **No-process-execution PROOF:** the only `subprocess`/`spawn`/`os.system`
      matches in the LMM code are **comments asserting absence**; the one real
      `subprocess` reference is the pre-existing PDF/render pipeline, untouched. The
      command helper returns strings/argv only (`shlex.quote` is display-quoting).
    - **Secret-leak scan CLEAN:** real `.env` keys (never printed) + a generic `sk-`
      pattern found **0** hits in `/local-model/status`, `/command-profile`,
      `/options`, `/provider-settings`, container logs, and changed docs. The lone JS
      match was an investigated **false positive** — `LOCAL_LLM_API_KEY` is a 4-char
      placeholder (`none`) coinciding with minified React's `display:"none"`; the real
      DeepSeek/Qwen keys appear nowhere.
    - **UI (source + harness + smoke) PASS:** the panel mounts in Providers/Models;
      offline state is safe/readable; Refresh works; Edit-settings scrolls/highlights
      `#provider-card-local`; the command helper appears and is clearly manual; Copy
      has a manual fallback; **no Start/Stop/Restart**, **no file/GGUF picker**;
      existing provider settings unaffected. (Full pixel-level browser click-through
      not run — proven structurally; optional human polish pass deferred.)
    - **Outcome:** **Phase 1 COMPLETE + validated; no bugs found; no code changed.**
      Recommended next: **Ask Your Guide local-only chat**, or host-companion DESIGN
      (sign-off-gated). Safe to merge (docs-only).

50. **Ask Your Guide — Slice 1: design (DOCS-ONLY)** — branch `ask-your-guide-design`
    (cut from `chrome-renderer-v1` @ `95132fe`). A design-first definition of a
    dedicated **Ask Your Guide** workspace where the user selects a generated
    guide/job and chats with it using a **local** model. **No backend endpoint, no
    frontend UI, no pipeline/extraction change, no provider-settings change, no LMM
    change, no new dependency. No code changed.**
    - **Deliverable:** new `docs/ASK_YOUR_GUIDE_DESIGN.md` + reconciled
      `CURRENT_TASK.md`, `NEXT_CHAT_HANDOFF.md`, `PROJECT_CONTEXT.md`, and three
      `DECISIONS.md` entries.
    - **Dedicated workspace, not a Library button.** `AskGuideWorkspace` is a
      first-class page/tab alongside Builder/Library/Styles/Providers — guide+session
      picker (left), chat (center), sources/context/citations panel (right/drawer).
      Library/Job Details may *later* deep-link "Open in Ask Your Guide"; the
      workspace is primary.
    - **Local-only in v1.** Resolves the **`local` provider only**, **status-gated**
      on LMM Phase 1 (`GET /api/local-model/status`); offline → first-class offline
      state + the LMM command helper, chat disabled. **No DeepSeek/Qwen/cloud
      fallback**; a hosted "ask any provider" mode is a future **explicit** opt-in.
      Model-agnostic (any OpenAI-compatible local server); long-context / thinking /
      multimodal used only when the server advertises them (multimodal deferred).
    - **Context manager is mandatory** (no "send the whole guide + all attachments +
      all history every turn"): chunk `clean.md`/`extracted.txt` with `## Page N` /
      heading **citation anchors**, a **dependency-free lexical** index cached per
      `(job_id, content_hash)`, **budgeted retrieval** (reserve answer + system rules
      + recent chat, fill the remainder), a **rolling chat summary** + recent-turn
      window + pinned facts, visible prep progress, and graceful "too large for this
      model" failure.
    - **Accuracy/citation contract:** answer from guide/source/uploads first; cite
      page/section; say so when not in the material; never invent
      facts/formulas/pages/dates; distinguish "from your guide" vs general knowledge;
      explain conflicts; ask when ambiguous; show + check calculations; mark
      high-vs-uncertain exam advice. A later slice **validates** emitted citations
      against in-context labels.
    - **Storage (conservative):** per-guide sessions under
      `jobs/<id>/ask/sessions/<sid>/` (metadata + history + uploads + cache);
      extra uploads **session-scoped** (never merged into the original job); chat
      history clearable/deletable; **never** auto-exported; **no secrets stored**.
    - **Endpoints proposed (sliceable, all local-only + redacted):** `GET
      /api/ask/jobs`, `GET /api/ask/jobs/{id}/context`, `POST …/prepare`, `POST
      …/sessions`, `GET /api/ask/sessions/{sid}`, `POST …/message`, `POST
      …/attachments`, `DELETE …/sessions/{sid}` + `…/history`. Every route reads job
      artifacts **read-only** (never `save_clean_md`, never creates a generation
      job), reuses `extract.py` for extra uploads, and leaks no key/full URL.
    - **10-slice build plan** (design → context inventory → chunking → local chat →
      workspace shell → chat UI → extra uploads → long-chat memory → accuracy/polish →
      optional multimodal), each with scope/files/tests/acceptance/non-goals.
    - **Outcome:** design complete; **NEXT = Ask Slice 2 (backend context inventory
      endpoint)**. Safe to merge (docs-only).

51. **Ask Your Guide — Slice 2: backend context inventory endpoint (BACKEND ONLY)**
    — branch `ask-context-inventory` (cut from `chrome-renderer-v1`, trunk incl.
    `95132fe` + `af0ec0e`). Two **read-only** inventory/context-summary endpoints for
    generated guides — **no chat, no chunking, no retrieval/indexing, no model call,
    no local-model call, no cloud fallback, no session storage, no extra uploads, no
    frontend, no mutation of any original job artifact.**
    - **New thin reader `pipeline/ask_inventory.py`** — read-only artifact reader:
      `has_generated_guide(job)` (eligibility = `clean.md` exists),
      `guide_inventory(job)` (`clean_md_present` + char count + ATX heading count),
      `source_inventory(job)` (`extracted_txt_present` + char count + `## Page N`
      anchor count). Returns **counts/booleans only — never a guide/source body**;
      never writes, never calls `save_clean_md`, no secret surface.
    - **`GET /api/ask/jobs`** lists **only Ask-eligible jobs** (those with a generated
      `clean.md`); guide-less / failed / incomplete jobs (no `clean.md`) are **filtered
      out**, not returned as ineligible. Reuses the existing `JOBS_DIR.glob("*/job.json")`
      manifest listing + the same newest-first / favorites-float ordering as `/api/jobs`.
      Each row is a curated, redacted picker summary: `id`, `title`, `status`,
      `created_at`, `updated_at`, `style` (`prompt_name`), `generator_preset`,
      `provider`, `model`, `favorite`, `attachment_summary`, `guide_available`,
      `source_available`.
    - **`GET /api/ask/jobs/{id}/context`** returns a per-job readiness + source
      inventory: `guide{clean_md_present,char_count,heading_count}`,
      `source{extracted_txt_present,char_count,page_anchor_count}`, redacted
      `attachments[]` (filename/extension/mode/status/extracted_chars/truncated/
      warnings), `attachment_summary`, `page_selections`, and a
      `readiness{status:"ready"|"not_ready", ready:bool, reasons:[]}` object. An
      **unknown job → 404** (via the existing `_get_job` guard); an existing but
      guide-less job → `200` `not_ready` (not a 404).
    - **Redacted by construction.** Both routes build on the existing
      `_safe_manifest` / `_safe_attachment_metadata` / `_attachment_summary` /
      `_safe_page_selections` helpers and emit an **explicit field whitelist** —
      nothing from the manifest is passed through verbatim — so **no raw API key,
      `api_key`/`Authorization` field, `sk-` value, full base URL (scheme/host), or
      filesystem path** can ride along, and **no guide/source body** is ever returned.
      Registered well before the SPA mount (and the parametric `/api/jobs/{job_id}`
      catch-all — different prefix), so `/api/*` keeps winning.
    - **Verified** (`python -m compileall api pipeline` OK; `docker compose config`
      exit 0; image rebuilt + container healthy): focused
      `test_scripts/test_ask_context_inventory.py` **50/50 in Docker** (pure reader +
      both endpoints: eligible appears / guide-less absent / counts + page-anchor +
      attachment fields + page selections / unknown→404 / redaction scan / read-only
      sha256 of `clean.md`+`extracted.txt`+`job.json` unchanged). **Live** seeded-job
      proof: `/api/ask/jobs` + `/context` return the curated fields; a raw-response
      secret scan over both endpoints found **no** `sk-`/`api_key`/`Authorization`/
      `https://`/`/home/secret`/`base_url` leak even though the seeded manifest +
      attachment carried a planted `sk-live-…` key, a full base URL, and a host path.
      Release smoke unchanged. **No frontend file touched** (build not needed).

52. **Ask Your Guide — Slice 3: backend context preparation / chunking (BACKEND
    ONLY)** — branch `ask-context-prepare` (cut from `chrome-renderer-v1`, trunk
    incl. `af0ec0e` + `2634f63`). Turns a job's generated `clean.md` + optional
    `extracted.txt` into a deterministic, citation-labelled chunk index plus a
    dependency-free lexical index, cached per `(job_id, content_hash)`. **No chat,
    no retrieval/query endpoint, no model call, no local-model call, no cloud/key
    read, no sessions, no extra uploads, no frontend, no new dependency, no mutation
    of any original job artifact.**
    - **New helper `pipeline/ask_context.py`** (stdlib only). `prepare_context(job)`
      reads `clean.md` (required) + `extracted.txt` (optional), computes a content
      hash over their bytes, and builds OR reuses the cache. Chunking is
      **deterministic**: split on markdown heading boundaries (guide) / `## Page N`
      anchors (source), then pack paragraphs up to ~650-token (`chars/4`) targets
      with an ~800-token hard ceiling; a single oversized paragraph hard-splits.
      **No overlap in v1** (paragraph/heading boundaries only) — recorded in
      `DECISIONS.md`. Each chunk carries `id`, `source_type` (`guide`|`source`),
      `label` (**nearest heading** for guide / **`Page N`** for source), `page`,
      `char_count`, `approx_tokens`, lexical `terms` (freq map), and `text` (cache
      only). Index also stores `doc_freq` for later BM25-style scoring.
    - **`POST /api/ask/jobs/{id}/prepare`** (registered before the SPA mount). Unknown
      job → **404** (`_get_job` guard). Guide-less existing job → **200 `ready:false`**
      with a reason (mirrors the Slice 2 context endpoint, not a 404). Eligible job →
      builds/reuses the cache and returns an **explicit whitelist**: `job_id`, `ready`,
      `cache_status` (`built`/`hit`/`rebuilt`), `content_hash`, guide/source/total
      chunk counts, a `citation_summary` (bounded heading + page-number samples), and
      a **job-relative** `cache_relpath`. **Idempotent**: an unchanged guide+source is
      a `hit` that rewrites nothing; a content change (`clean.md` OR `extracted.txt`)
      rebuilds; a corrupt/stale cache rebuilds safely instead of crashing.
    - **Cache layout:** `jobs/<job_id>/ask/cache/context_index.json` — fenced inside
      the job dir (`_ensure_fenced`), written atomically (temp file + `os.replace`),
      safe to delete/rebuild. The cache file holds chunk text + terms (Slice 4 needs
      them) but **only** the whitelisted top-level keys — it never touches the manifest,
      so no secret/key/URL/host-path/unrelated field can enter it. The prepare response
      never returns guide/source body, chunk `text`, keys, URLs, or host paths.
    - **Verified** (`python -m compileall api pipeline` OK; `docker compose config`
      exit 0; container healthy): focused `test_scripts/test_ask_context_prepare.py`
      **58/58 in Docker** (pure chunker + endpoint: build→hit→rebuild on guide/source
      change, heading + `## Page N` label preservation, corrupt-cache recovery, 404,
      guide-less, cache-key whitelist, response + cache secret scans, and sha256
      immutability of `clean.md`/`extracted.txt`/`job.json`). **Slice 2 regression**
      `test_ask_context_inventory.py` **50/50** unchanged. **Live** proof on a real
      eligible job: `prepare` built 20 guide chunks, second call returned `hit`, raw
      response + on-disk cache secret-scanned clean (no `sk-`/`api_key`/`Authorization`/
      `https://`/host path/chunk `text`). **No frontend/shared file touched** (build not
      required).

53. **Ask Your Guide — inserted Slice 4: first-class workspace shell (FRONTEND
    ONLY)** — branch `ask-workspace-shell` (cut from `chrome-renderer-v1` at
    `a29a405`). Inserts the visible product shell before backend chat/session
    complexity: a top-level `Ask Guide` workspace in the sidebar with left guide
    picker, center disabled chat/readiness panel, and right context/local-model rail.
    **No backend route changed. No chat endpoint, no `/api/ask/sessions`, no model call,
    no local-model call, no cloud fallback, no extra uploads, no chat history
    persistence, no artifact mutation, no dependency.**
    - **Frontend API helpers** in `frontend/src/api/client.js`: `getAskJobs`,
      `getAskJobContext`, `prepareAskJobContext`, consuming the existing
      summary-only endpoints from Ask Slices 2/3. Existing LMM helpers continue to
      consume `GET /api/local-model/status` and `GET /api/local-model/command-profile`.
    - **New `frontend/src/components/AskGuideWorkspace.jsx`**: fetches eligible
      generated guides from `GET /api/ask/jobs`, selects a guide and loads
      `GET /api/ask/jobs/{id}/context`, shows guide/source readiness counts
      (guide chars/headings, source chars/page anchors), attachment filenames/modes/
      warnings, page selections, provider/model/preset/style metadata, and reasons
      for not-ready jobs. The center panel has a disabled composer and explicit
      "chat lands next" copy. `Prepare context` calls
      `POST /api/ask/jobs/{id}/prepare` and shows cache status (`built`/`hit`/
      `rebuilt`), total/guide/source chunk counts, and bounded citation samples.
    - **Local model status**: the rail reads LMM status and reuses the existing
      `localModelStatus.js`/`localModelCommand.js` helpers plus the exported
      `CommandHelper` renderer from `LocalModelsPanel.jsx`. Offline/unconfigured
      states show the manual command helper; reachable states show safe model count,
      default/selected model, latency, and bounded model chips. There are **no**
      start/stop/process-control buttons.
    - **Security/redaction proof in the UI layer**: new pure
      `frontend/src/askGuide.js` helper renders only summary fields and defensively
      basenames attachment/page-selection filenames. It never renders guide/source
      bodies, chunk text, full URLs, raw keys, or host filesystem paths; browser state
      holds only endpoint summaries. Build output is generated by Vite and no new
      served secret surface is introduced.
    - **Verified**: `npm run test:ask-guide` (all helper checks pass, including
      POSIX/Windows path stripping), `npm run test:local-model-command` pass,
      `npm run test:local-model-status` pass, `npm run build` pass. Backend files were
      not touched, so `compileall` was not required for this slice. Ask backend
      regression tests are still expected before merge handoff (inventory + prepare).

54. **Ask Your Guide — backend local chat API (BACKEND ONLY)** — branch
    `ask-local-chat-api`. Adds minimal Ask chat session storage and local-only chat
    generation:
    - **Endpoints:** `POST /api/ask/jobs/{job_id}/sessions` creates
      `jobs/<job_id>/ask/sessions/<session_id>/session.json` + `history.jsonl` for
      jobs with generated `clean.md` (unknown job → 404; guide-less job →
      safe `not_ready` 409); `GET /api/ask/sessions/{session_id}` returns safe
      metadata + bounded history; `POST /api/ask/sessions/{session_id}/message`
      validates input, status-gates on LMM/local availability, retrieves, calls the
      local provider, persists JSONL history, and updates session metadata.
    - **Retrieval/prompting:** reuses/refreshes the Slice 3 prepared cache
      synchronously via `ask_context.prepare_context()` (writes only the Ask cache,
      never original artifacts), then dependency-free lexical scores over cached
      chunk term frequencies + `doc_freq`. Query = current question plus a tiny recent
      user-history window. Retrieval is bounded to top 8 chunks and an approximate
      3k-token pool (`chars/4`) with room reserved for system rules, recent chat, and
      answer. Responses return answer text, allowed citation labels, safe chunk
      metadata only (no chunk text), session id, and safe local model status.
    - **Local-only proof:** message calls `get_local_model_status()` first; offline /
      unconfigured / unreachable returns structured `local_offline` without building
      provider config or calling the model. The generation call uses
      `build_provider_config("local", selected_model, max_tokens=...)` and
      `generate_chat_completion`; focused tests assert no DeepSeek/Qwen/cloud fallback
      path is used.
    - **Security/storage:** session ids are opaque `ask_<uuidhex>` values and session
      lookup is fenced under each parent job. `session.json` is atomic; history appends
      JSONL. Raw prompts are never stored or returned. Obvious `sk-*` keys,
      Authorization bearer headers, and full `http(s)://` URLs are masked before Ask
      cache/session persistence and responses. `session.json`/`history.jsonl` are not
      exported by existing export endpoints.
    - **Artifact immutability:** tests sha256 `clean.md`, `extracted.txt`, and
      `job.json` before/after session creation and message calls; all unchanged. The
      slice never calls `JobManager.save_clean_md`, never creates generation jobs, and
      never rewrites guide/source/manifest artifacts.
    - **Verified:** `test_scripts/test_ask_local_chat.py` **40/40** in the Docker
      image with the repo mounted; Ask inventory regression
      `test_ask_context_inventory.py` **50/50**; Ask prepare regression
      `test_ask_context_prepare.py` **58/58**; `python -m compileall api pipeline`
      pass; `docker compose config >/tmp/compose-check.txt` exit 0; release smoke
      **28/28** against the live container. Docker image rebuilt + app container
      healthy. **Frontend build not required by the slice** because no frontend/shared
      files were touched (the Docker rebuild reused the existing frontend build layer).

55. **Ask Your Guide — frontend chat UI wiring (FRONTEND)** — branch `ask-chat-ui`.
    Wires the visible Ask workspace to the already-landed local-only chat API:
    - **Endpoints consumed:** `GET /api/ask/jobs`, `GET /api/ask/jobs/{job_id}/context`,
      `POST /api/ask/jobs/{job_id}/prepare`, `POST /api/ask/jobs/{job_id}/sessions`,
      `GET /api/ask/sessions/{session_id}`, `POST /api/ask/sessions/{session_id}/message`,
      `GET /api/local-model/status`, `POST /api/local-model/check`, and
      `GET /api/local-model/command-profile`.
    - **UX:** guide selection and context inventory remain visible; Prepare Context is
      explicit and still works; chat sessions are created lazily on first send, then
      loaded before messaging. The composer enables only when a guide is selected,
      context is ready, prepare has succeeded, the local model is reachable, and no
      send is in flight. Message success appends the user turn + assistant answer and
      renders only backend-returned citation labels and safe retrieved chunk metadata.
      Failures keep the draft available for retry; `local_offline` shows the existing
      LMM command helper and keeps the composer disabled.
    - **Security:** no `dangerouslySetInnerHTML`; answers render as plain text with
      preserved whitespace. Frontend normalizers defensively redact obvious `sk-*`
      keys, Authorization bearer headers, full `http(s)://` URLs, and POSIX/Windows
      host paths before storing/rendering. The UI stores only safe `session_id`,
      session metadata, bounded message history, citation labels, retrieved chunk
      metadata (id/source/page/tokens/score), and safe local model fields. It never
      renders guide/source bodies, chunk text, raw prompts/system prompts, raw keys,
      full URLs, or filesystem paths, and it does not persist chat to browser storage.
    - **Non-goals preserved:** no backend chat behavior change, no extra uploads, no
      chat export, no backend citation-validation slice, no long-chat rolling-summary
      UI, no streaming, no cloud fallback, no hosted provider selector, no DeepSeek/Qwen
      fallback, no local model process control, no provider settings writes, and no new
      dependencies.
    - **Verified:** `npm run test:ask-guide` pass (45/45 helper checks),
      `npm run build` pass (existing Vite chunk-size warning only),
      `npm run test:local-model-command` pass, `npm run test:local-model-status` pass,
      `test_scripts/test_ask_context_inventory.py` **50/50** in Docker with the repo
      mounted, `test_scripts/test_ask_context_prepare.py` **58/58** in Docker,
      `test_scripts/test_ask_local_chat.py` **40/40** in Docker, and
      release smoke **28/28**. `docker compose config >/tmp/compose-check.txt` exit 0.
      Backend/shared Python was not touched, so `python -m compileall api pipeline` was
      not required.

56. **Ask Your Guide — chat polish + emitted-citation validation** — branch
    `ask-chat-polish-citations`.
    Tight backend + frontend polish over the already-working local Ask chat flow:
    - **Backend citation validation:** `POST /api/ask/sessions/{session_id}/message`
      now post-validates bracket-style citations emitted by the local model against
      the exact allowed citation labels retrieved for that turn. Ask-looking
      unsupported citations (for example `[Guide Fake Topic]`) are stripped from the
      answer and reported; normal bracketed prose that does not look like an Ask
      citation is preserved. Responses include `citations_allowed`,
      `citations_used`, `citations_unsupported`, and
      `citation_validation: {ok, unsupported_count}`. Trusted `citations` now mirror
      used/validated citations, not unsupported labels.
    - **Prompt cleanup:** the answer rules still require grounding and exact allowed
      labels, but now prefer citations at paragraph ends or a short sources line
      instead of noisy citations after nearly every sentence.
    - **Frontend polish:** guide cards format attachment summaries as safe human text
      instead of `Guide only · [object Object]`; the workspace shows a friendly
      session-active label with only a short suffix instead of the full technical
      `ask_...` id; assistant answers render through a tiny inert subset renderer for
      headings, bold, numbered/bulleted lists, line breaks, and fenced blocks (no
      `dangerouslySetInnerHTML`, no markdown dependency); escaped math dollars are
      cleaned for readability.
    - **Sources/citations UX:** citation chips come from backend machine-readable
      used citations; unsupported citations show a subtle warning and are not rendered
      as trusted chips. Retrieved chunk metadata remains available but is collapsed
      behind `Sources used` / `Show retrieved chunks` disclosures by default. Chunk
      text is still never rendered.
    - **Security/non-goals:** no raw prompts/messages are logged by the new code, raw
      prompts are not returned, full chunk text is not returned to the UI, and the
      existing redaction of obvious `sk-*` keys, Authorization bearer headers, full
      URLs, and host paths remains in place. Local-only enforcement is unchanged. No
      extra uploads, no streaming, no cloud fallback, no hosted provider selector, no
      DeepSeek/Qwen fallback, no rolling summary, no multimodal, no local model
      process control, no provider settings writes, and no new dependencies.
    - **Verified:** `npm run test:ask-guide` pass (58/58 helper checks),
      `npm run build` pass (existing Vite chunk-size warning only),
      `npm run test:local-model-command` pass, `npm run test:local-model-status`
      pass, `python test_scripts/test_ask_local_chat.py` pass for pure checks
      (14/14; endpoint portion skipped on the host because FastAPI is not installed),
      `python test_scripts/test_ask_context_inventory.py` pass for pure checks
      (11/11; endpoint portion skipped for missing host FastAPI),
      `python test_scripts/test_ask_context_prepare.py` pass for pure checks (28/28;
      endpoint portion skipped for missing host FastAPI), and
      `python -m compileall api pipeline` pass. `docker compose config
      >/tmp/compose-check.txt` exit 0. A running Docker image was healthy, but it did
      not include `test_scripts/`, so in-container endpoint reruns were unavailable
      without copying files into the container.

57. **Ask Your Guide — session management UI/API** — branch
    `ask-session-management`.
    Adds safe controls for managing persisted Ask sessions without changing local chat
    generation:
    - **Backend endpoints:** `GET /api/ask/jobs/{job_id}/sessions` lists safe
      summaries for one eligible guide (session id, job id, title, created/updated,
      cheap message count, and a redacted bounded last-message snippet). Unknown job
      returns 404; an eligible job with no sessions returns an empty list. `DELETE
      /api/ask/sessions/{session_id}/history` clears `history.jsonl`, keeps
      `session.json` and the same session id, updates metadata, and does not touch
      the context cache. `DELETE /api/ask/sessions/{session_id}` deletes only that
      fenced session directory and returns `{deleted:true, session_id}`.
    - **Existing behavior preserved:** `POST /api/ask/jobs/{id}/sessions`, `GET
      /api/ask/sessions/{id}`, and `POST /api/ask/sessions/{id}/message` keep their
      prior contracts. Local-only status gating, retrieval, prompt assembly, citation
      validation, and model-call behavior are unchanged.
    - **Frontend UX:** the Ask workspace now lists sessions for the selected guide in
      a compact right-rail panel, can switch to any listed session, starts a new chat
      without re-preparing context, keeps lazy session creation for first send when
      no session is active, and adds confirm-gated **Clear chat** / **Delete** controls
      for the active session. Clear keeps the guide, prepared context, selected
      session, and draft flow intact; delete removes the session from the list and
      loads the next newest session when available, otherwise returns to no active
      chat for that guide.
    - **Security/non-goals:** summaries and UI helpers render only bounded redacted
      metadata/snippets. No raw prompts, full answers in list summaries, chunk text,
      guide/source bodies, keys, Authorization headers, full URLs, or filesystem paths
      are returned/rendered by the new surfaces. No browser storage is used. No extra
      uploads, chat export, streaming, cloud fallback, hosted selector, DeepSeek/Qwen
      fallback, long-chat rolling summary, multimodal, local model process control,
      provider settings writes, or new dependencies.
    - **Verified:** `npm run test:ask-guide` pass (67/67 helper checks),
      `npm run build` pass (existing Vite chunk-size warning only), `python
      test_scripts/test_ask_local_chat.py` pass for pure checks (27/27; endpoint
      portion skipped on the host because FastAPI is not installed), `python
      test_scripts/test_ask_context_inventory.py` pass for pure checks (11/11;
      endpoint portion skipped for missing host FastAPI), `python
      test_scripts/test_ask_context_prepare.py` pass for pure checks (28/28; endpoint
      portion skipped for missing host FastAPI), `python -m compileall api pipeline`
      pass, `npm run test:local-model-command` pass, `npm run test:local-model-status`
      pass, release smoke **28/28**, and `docker compose config
      >/tmp/compose-check.txt` exit 0. The running Docker image was healthy but did
      not include `test_scripts/`, so in-container endpoint-script reruns were not
      available without copying test files into the container.

58. **Ask Your Guide — chat math/source visual polish** — branch
    `ask-chat-math-source-polish`.
    Frontend-only readability polish for the existing local Ask chat UI:
    - **Code files changed:** `frontend/src/askGuide.js`,
      `frontend/src/components/AskGuideWorkspace.jsx`, and
      `frontend/scripts/verify-ask-guide.mjs`.
    - **Math answer rendering:** added inert math-aware answer parsing for
      `$$...$$`, `\[...\]`, `\(...\)`, and escaped-dollar inline math. Display math
      renders as readable monospace blocks preserving line breaks; inline math renders
      as small monospace chips. No `dangerouslySetInnerHTML`, no markdown dependency,
      no KaTeX/MathJax, and no new dependency.
    - **Source/citation affordances:** trusted backend-used citations now appear in a
      clearer **Sources used** section. Unsupported citations remain warning-only and
      are not trusted chips. Retrieved chunk metadata remains collapsed by default
      and shows cleaner label/type/page/score/token rows. Chunk text is still never
      rendered.
    - **Behavior preserved:** local-only Ask behavior is unchanged. Session
      management behavior is unchanged. No backend retrieval, prompt assembly,
      model-call, citation-validation, session, clear/delete, or lazy session
      creation logic changed. No extra uploads, streaming, hosted/cloud Ask mode,
      DeepSeek/Qwen fallback, rolling summary, multimodal, local model process
      control, provider settings writes, browser storage, or new dependencies.
    - **Verified:** root `npm run test:ask-guide` failed because the root package has
      no such script. `frontend` `npm run test:ask-guide` passed. `frontend`
      `npm run build` passed with the existing Vite chunk-size warning. `frontend`
      `npm run test:local-model-command` passed. `frontend`
      `npm run test:local-model-status` passed. `python -m compileall api pipeline`
      passed. `python test_scripts/test_ask_local_chat.py` passed pure checks;
      endpoint section skipped because FastAPI is unavailable on the host. `python
      test_scripts/test_ask_context_inventory.py` passed pure checks; endpoint
      section skipped because FastAPI is unavailable on the host. `python
      test_scripts/test_ask_context_prepare.py` passed pure checks; endpoint section
      skipped because FastAPI is unavailable on the host. `python
      test_scripts/smoke_release.py` passed **28/28**. `docker compose config
      >/tmp/compose-check.txt` exit code 0.
    - **Manual validation follow-up:** browser validation after this slice found the
      empty local-model response guard bug recorded in DONE #59.

59. **Bugfix — Ask empty local-model response guard** — branch
    `ask-empty-response-guard`.
    Discovered during manual Ask UI validation after the math/source polish slice.
    - **Bug:** a browser Ask message returned
      `POST /api/ask/sessions/{session_id}/message` → 500. The traceback showed
      `generate_chat_completion` raised
      `RuntimeError("LLM returned an empty response.")`; Ask did not catch that
      exception, so FastAPI returned raw 500 text.
    - **Fix:** `pipeline/ask_sessions.py` now catches the narrow empty local-model
      RuntimeError response case and returns a safe structured `provider_error`
      response with `error.category: provider_empty_response` and a retryable,
      user-safe message.
    - **History behavior:** the failed turn does not append a successful
      user/assistant message to history.
    - **Behavior preserved:** local-only behavior is unchanged. No retrieval, prompt
      assembly, model fallback, citation validation, session management, clear/delete,
      provider settings, streaming, uploads, rolling summary, multimodal, or
      process-control behavior changed.
    - **Tests/validation:** `test_scripts/test_ask_local_chat.py` updated with
      focused coverage. `python test_scripts/test_ask_local_chat.py` passed 38/38;
      endpoint section skipped because plain Python lacks FastAPI. `python
      test_scripts/test_ask_context_inventory.py` passed 11/11; endpoint skipped for
      missing FastAPI. `python test_scripts/test_ask_context_prepare.py` passed
      28/28; endpoint skipped for missing FastAPI. `.venv/bin/python -m compileall
      api pipeline` passed. `npm --prefix frontend run test:ask-guide` passed.
      `npm --prefix frontend run build` passed. `docker compose config
      >/tmp/compose-check.txt` exit code 0. `.venv/bin/python
      test_scripts/smoke_release.py` ran 27/28 with one existing-looking non-Ask
      outline-ordering failure.
    - **Manual validation:** Docker app rebuilt/restarted and healthy. The original
      empty local-model behavior was not reproducible, but the simulated regression
      is now covered.

60. **Compatibility fix — Ask local thinking-model `/no_think` control** — branch
    `ask-local-direct-answer-guard`.
    Follow-up to manual browser validation of DONE #59.
    - **Bug:** the previous direct-answer system rules were not strong enough for the
      full Ask prompt with the Gemma llama-server setup. The local model generated
      through the whole Ask response budget in hidden `reasoning_content` and
      returned no visible assistant content, producing `provider_empty_response`.
    - **Fix:** `pipeline/ask_sessions.py` keeps the direct visible-answer system
      rules and adds a standalone `/no_think` local thinking-model control only to
      the assembled model-facing user message, immediately before the final `User
      question:` block sent to `generate_chat_completion`.
    - **Model-only boundary:** `/no_think` is not appended to the saved raw user turn,
      not stored in `history.jsonl`, not returned by session load/list responses, not
      included in session summaries, and not rendered by the frontend. Citation and
      grounding rules are preserved.
    - **Tests/validation:** `python test_scripts/test_ask_local_chat.py` passed
      45/45 pure checks with endpoint skip because FastAPI is unavailable in this
      environment. `python test_scripts/test_ask_context_inventory.py` passed 11/11
      with endpoint skip. `python test_scripts/test_ask_context_prepare.py` passed
      28/28 with endpoint skip. `python -m compileall api pipeline` passed.
      `npm --prefix frontend run test:ask-guide` passed. `npm --prefix frontend run
      build` passed with the existing Vite large-chunk warning. `python
      test_scripts/smoke_release.py` passed 28/28. `docker compose config
      >/tmp/compose-check.txt` exit code 0.
    - **Manual/live validation:** Docker app rebuilt/restarted and healthy. Local
      model status from the container was reachable for
      `gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`. A live Ask session
      `ask_7cec13974cbf48ccb7de71889c9a71e9` against job
      `20260605-181809-c768` returned `status: answered` with visible assistant
      content instead of `provider_empty_response`. Session load/list responses and
      persisted `history.jsonl` did not contain `/no_think`; container-side grep of
      that session/cache found no `/no_think`, `reasoning_content`, or
      `provider_empty_response`. Headless Chromium verified the rebuilt browser shell
      is served; a full browser click/send replay was not automated in this repo.

61. **Local Model Manager Phase 2G7 — operator setup docs + safe profile preset
    import** — branch `lmm-phase2g7-profile-presets-docs`. Added
    `docs/LOCAL_MODEL_MANAGER_OPERATOR_SETUP.md`, a Linux-first operator guide
    covering how to find `llama-server` (`command -v llama-server`,
    `readlink -f /proc/<pid>/exe`), approved model roots, companion JSON config,
    process runtime dir, token handling, safe CPU / low-memory GPU / balanced GPU
    profile examples, Unix socket Docker mount concept, backend env vars
    (`LMM_COMPANION_SOCKET`, `LMM_COMPANION_TOKEN`,
    `LMM_COMPANION_TIMEOUT_SECONDS`), the real validation harness
    (`test_scripts/validate_lmm_real_llama_server.py`), troubleshooting, and
    Linux-first platform scope.
    - **Implemented optional `.ini` preset import** in
      `tools/local_model_companion/config.py` using Python stdlib
      `configparser` with interpolation disabled. Preset paths come only from
      explicit companion JSON (`profile_preset_files`), never from the frontend.
      Imported presets require `llama_server_executable` in companion JSON; the
      preset file cannot set executable/model paths or commands. Imported
      sections become normal `llama_server` profiles through the same whitelist
      schema used by JSON profiles.
    - **Rejected rather than ignored:** unknown preset keys, duplicate ids,
      `DEFAULT` values, invalid int/bool/enum/range values, env expansion,
      shell/path-like text, and command/args/shell/model_path/executable/
      free-form flag keys. CPU safe and GPU balanced defaults avoid
      `gpu_layers=999`.
    - **Docs reconciled:** `PROJECT_CONTEXT.md`, `NEXT_CHAT_HANDOFF.md`,
      `LOCAL_MODEL_MANAGER_PHASE2_DESIGN.md`, and `DECISIONS.md` now record that
      CPU validation passed, full offload `gpu_layers=999` failed safely as
      `model_may_be_too_large` / CUDA OOM, profile presets/defaults are
      whitelist-based, app-suggested settings remain deferred, and `.ini` import
      is implemented.
    - **Scope preserved:** no app-suggested settings, AI-generated
      recommendations, Provider Settings writes, Ask changes, permanent Docker
      Compose changes, frontend UI changes, free-form flags, raw shell command
      execution, model download manager, host-gateway TCP, Docker socket,
      privileged container, host PID namespace, Windows/macOS implementation, or
      token/socket/absolute path/raw argv exposure.

## NEXT (in order)

> **Provider settings feature group is DONE through Slice 5** (DONE #32→#36):
> design (`978516e`) → backend store + safe endpoints (`1ba2b28`) → frontend
> Providers UI (`3024a33`) → runtime settings applied to live generation
> (`40df617`) → backend fetch-models endpoint (`6da944a`) → frontend Refresh
> Models UI (`61fb423`). Raw keys stay **server-side only**; `/api/options` and
> `/api/provider-settings` are **redacted**; `config/provider_settings.json` is
> non-secret (`0644`), `config/secrets.json` is secret-only (`0600`). Precedence:
> **per-job request > provider-settings default > `.env` > built-in**; generator
> presets **never hard-pin** provider/model (`model_hint` advisory), and an
> **explicit** preset sampling/thinking value overrides the stored runtime default.
> The **fetch-models endpoint** (DONE #35) is read-only and never auto-persists;
> the **Refresh Models UI** (DONE #36) fetches review-only model ids, stages new
> ids into draft `custom_models` via Add / Add all new, and requires an **explicit
> Save** to persist (after which `/api/options` exposes the saved custom models).
> Still deferred from provider settings: **encrypted-at-rest / OS keyring, `.env`
> import, the Local Model Manager (separate design-first feature), and the optional
> Builder "Provider default" thinking UI polish.**
>
> **Large-PDF core (DONE #27→#31) and Group C (C1→C5) also remain done.** The
> earlier "in-app provider settings — design-first" recommendation is now
> **completed and removed**. The only remaining math/PDF slice is **font-size
> rationalization** (cause C, CSS-only) — optional, not the headline.
>
> **Shortcut Inspector / Repair Loop is COMPLETE through Slice 3B** (DONE #39→#42,
> `a0f96d1`→`4458c9a`): backend read-only inspector + `validity`, read-only
> Inspector UI, repair preview/apply endpoints, and the repair UI. The earlier
> "shortcut inspector / repair loop — design/polish" recommendation is **done and
> removed** from this list. The provider-settings real-world validation pass also
> ran (see `docs/VALIDATION_PROVIDER_SETTINGS_LARGE_PDF.md`) and surfaced two
> already-fixed findings, so it is no longer a recommended next step either. The
> Shortcut Inspector itself was validated in
> `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md` (docs-only; no code changed).

> **LMM Phase 1 is DONE through validation** (Slices 1→4 + Slice 5 validation,
> #45→#49; `94003bc`→`e399f09`, validated in
> `docs/VALIDATION_LOCAL_MODEL_MANAGER_PHASE1.md`). The earlier "Phase-1 validation /
> docs reconciliation" recommendation is **done and removed** from this list.

1. **Ask Your Guide — extra session uploads (optional, explicit separate slice).**
   Do not start automatically. If the operator chooses to continue Ask features,
   design/implement session-scoped extra uploads separately, keeping them out of job
   artifacts and preserving local-only Ask behavior.
2. **Broader manual Ask UI validation / polish, only if a concrete issue surfaces.**
   The empty local-model response regression found during manual validation is now
   guarded and covered. Keep any follow-up narrow and bug-driven.
3. **Local Model Manager — next real-setup slice, explicit only.**
   Phase 2G7 completed operator docs and safe `.ini` preset import. App-suggested
   settings remain deferred until more real validation exists. Any future LMM
   work should stay explicit and narrow, for example additional live validation,
   packaging/runtime-service docs, or a separately approved recommendations
   design. Preserve the host companion boundary: no direct Docker→host spawn, no
   Provider Settings writes, no Ask changes, no permanent Docker Compose changes,
   no Docker socket/privileged/host-PID path.
4. **Math/PDF font-size rationalization (cause C) — optional CSS-only
   investigation.** The remaining math/PDF fidelity slice; investigate the
   CSS-only font sizing before any change.
5. **Large-PDF preflight size-limit polish — optional, later.** Raising/uniting
   the upload ceiling + preflight size thresholds is a possible later slice. It is
   **explicitly not part of this slice** and not started.
6. **Focused manual validation / polish of the Shortcut Inspector UI.** The
   inspect→repair loop is complete and validated at the API + served-bundle level
   (`docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`); the remaining gap is a human
   click-through of the live Home/Customize 3-tier badges, the Inspector drawer
   layout, and the Preview→Apply / clone flow (incl. the stale-preview re-disable).
   Validation / polish only — no feature work unless a concrete UI bug surfaces.

(**Also still on the books, design-first:** Library archive / tag model — bulk
**archive** needs a new archive state designed + a `DECISIONS.md` entry first;
bulk **tag** needs a tag model designed first. Neither is started. Bulk **export**
is already DONE (B4). Do not begin either without an explicit slice + design
sign-off.)

## OPEN ITEMS

- **Shortcut options → Builder wiring — DONE (`7af9cbd`, Slice C3).** The Builder
  now exposes `include_sections` + the C2 axes, loads them from a selected
  shortcut into Builder state, and sends them to `/api/jobs/llm` (both the JSON
  and multipart/attachment transports). The backend bridge (`cc75292`) feeds the
  load path; legacy `modules` still translate to canonical `include_sections` on
  read/export. No longer open.
- **Generator preset cards + compatibility warning (C4b) — DONE (`b3d7785`).** The
  Builder Style tab now renders generator presets as cards (provider SVG icon / text
  badge, model chip, purpose, description, recommended use, selected state) consuming
  the C4a `/api/options.generator_presets` metadata, plus a soft, advisory
  `model_hint`-vs-selected-model compatibility warning that never blocks Generate.
  See `presetMeta.js` + `DECISIONS.md`. The shortcut **inspector/repair** loop
  (the store's `valid`/`reason` "references unavailable …" surfacing) is now
  **DONE** (DONE #39→#42). **Still open:** richer **shortcut** cards on Home.
- **Home duplicate "Customize" button — DONE (`7f78542`, Slice C5).** The lower
  duplicate "Customize" button in the Pinned-shortcuts section head was removed;
  the single page-head "Customize Shortcuts" entry is kept and opens the shortcut
  customization modal (not Styles). Smart Tools confirmed already absent from Home;
  Compare Styles confirmed already living in Styles. No longer open.
- **Shortcut inspector / repair loop — DONE** (DONE #39→#42, `a0f96d1`→`4458c9a`,
  on trunk). Read-only inspector + additive `validity` (3-tier status, full
  findings list, saved-model check), 3-tier Home/Customize badges + read-only
  Inspector drawer, repair preview/apply endpoints (preview read-only, apply the
  only write, in-place + clone), and the repair UI (Preview-before-Apply,
  stale-preview re-disables Apply, explicit confirm). Validated docs-only in
  `docs/VALIDATION_SHORTCUT_INSPECTOR_REPAIR.md`. **Still deferred:** the
  degraded-activation confirm / "Repair instead" Home path (§5.5), "Repair all"
  batch, a Home "N need attention" banner, model auto-suggest/fuzzy match,
  imported preview-row repair before import, and tool/view repair (repair is
  scoped to `builder_setup` only). **Update:** the degraded-activation confirm /
  "Repair instead" Home path (§5.5) is now **DONE (#43)** — degraded shortcuts ask
  before launch, broken stay blocked with an Inspect/Repair dialog, valid launch
  unchanged.
- **Rerender drops `generator_preset` — FIXED** (`2716995`, branch
  `fix-rerender-generator-preset`, now on trunk).
  `retry_failed_job` (`api/server.py`, `path_mode == "generate"`) now reads
  `generator_preset` from the manifest and rebuilds through it: the preset is resolved,
  its tuned sampling params are applied to the provider config (mirroring the
  `/api/jobs/llm` preset path), and the id is passed to `generate_study_guide`. An
  absent/null preset keeps the default path; a since-removed preset id degrades
  gracefully to the default path instead of failing the retry. The user's saved
  provider/model still wins (`model_hint` stays advisory). Backend-only; no new request
  field. Regression test `test_scripts/test_retry_generator_preset.py` (7/7 in Docker:
  threading + sampling overrides, default path, stale-id degrade, and a real on-disk job
  whose manifest still records the preset after retry).
- **Provider-aware truncation caps** — deferred (Option B in `DECISIONS.md`).
  Current caps are env-configurable with static defaults.
- **Real cancel button — DONE** (`901d44b`, branch `server-side-cancel`, now on
  trunk; DONE #22). Cooperative server-side cancel via a `jobs/<id>/cancel.requested`
  marker checked at safe stage boundaries; new `cancelled` terminal status;
  `POST /api/jobs/{id}/cancel`; Builder Cancel button. **Cooperative + checkpoint-based:**
  it does **not** kill processes or threads — it sets a marker that the pipeline checks
  at safe stage boundaries, so a cancel requested during an uninterruptible LLM call or
  Chromium render only takes effect at the **next safe checkpoint** (it is "stop at the
  next checkpoint," not an instant abort). **Partial artifacts and the user's uploads /
  Builder inputs / settings are preserved** — nothing is deleted on cancel; the Builder
  keeps its inputs so the user simply re-generates. No pipeline rewrite. **Still
  deferred:** retry-from-cancelled (kept gated to `failed`; re-generate from the Builder
  instead).
- **Docker GHCR publish workflow / prebuilt image** — deferred. `863f5b7` carried a
  `.github/workflows/publish.yml` (push image to GHCR on `v*` tags) and an
  `image: ghcr.io/...` line in compose. Needs a deliberate distribution decision before
  adopting (the app is local-only/single-operator today). Parked on `hardening`.
- **Pinned dependency lockfile** — deferred. `863f5b7` fully froze `requirements.txt`
  (transitive pins + new packages). Reproducibility is good, but a freeze should be
  regenerated from *this* tree, not lifted from the divergent `hardening` branch. Its
  own deliberate slice if/when wanted.
- **Branch retirement** — deferred housekeeping. The consumed feature/integration
  branches (and the short-lived `salvage-compose-limits`, `integ-group-c`) are kept,
  not deleted, per the operator's "do not delete branches" rule.
- **Group D** — not started. Do not begin without an explicit slice request.
