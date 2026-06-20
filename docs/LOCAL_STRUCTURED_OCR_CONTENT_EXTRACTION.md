# LOCAL_STRUCTURED_OCR_CONTENT_EXTRACTION.md — Slice 176I-real

> Closed-vocabulary record of the **first real content-extraction run** of the local
> structured OCR producer on content-bearing slides. Closed tokens / counts / buckets /
> bools only: no guide / source / OCR / table / caption text, no formulas, no raw values
> / leaf counts / matrix entries, no private paths / filenames / hashes / byte counts /
> screenshots, no model files / caches, no provider payloads / prompts / responses /
> secrets. The repo (code) is the source of truth; verify
> `test_scripts/run_local_structured_ocr_content_extraction.py` before relying on this.

---

## 0. What this slice is

The **first real content-extraction run** using the local structured OCR producer proven
in Slice 176G — **not** a seam/adapter/readiness slice (176H built the seam). It runs the
proven local **Chandra OCR 2 GGUF** route (`llama.cpp` / `llama-server`,
OpenAI-compatible `/v1/chat/completions`, local-only, no cloud/API) on **content-bearing**
slides of one real deck and writes a **private** extracted-content artifact for downstream
guide/figure/numeric consumers, plus this committed-safe closed summary.

**IS:** run the proven producer on real content slides; produce a private extracted-content
artifact + a closed extraction summary.
**IS NOT:** an adapter/seam/readiness slice, guide-generation wiring, frontend/API
integration, full ingestion rollout, numeric-recompute wiring, a Layer-2 judge, repair,
cloud OCR, provider/model generation, or a broad new framework. No raw OCR dumped into git.
`judge_ready=false`; `repair_ready=false`.

## 1. Producer (real, local) and minimal runner

- Runner: `test_scripts/run_local_structured_ocr_content_extraction.py` — env-driven
  (`DECK_PDF`, `SOURCE_LABEL`, `PRIVATE_OCR_DIR`, `CHANDRA_ENDPOINT`, `TESSERACT_BIN`,
  DPI / cap knobs). Carries **no private paths** in code.
- Selection: a **Tesseract keyword + numeric-density pre-scan** over locally-rendered
  pages (the 176F/176G idea) picks the most numeric-dense matching page per content
  category; title/intro/agenda pages are excluded. Selection is cached privately.
- Extraction: selected pages are rendered locally (PyMuPDF) and OCR'd through the
  **committed** `pipeline/chandra_local_provider.py` payload builder against the running
  local `llama-server`; output runs through `pipeline/chandra_normalizer.py`. Raw
  layout-HTML + a manifest are written **only** to the private gitignored dir.
- `cloud_ocr_used=false` · `structured_ocr_engine=chandra_gguf_local`.

## 2. GATE-2 confound found and corrected (do not skip)

The **first** extraction pass under-recovered (4/5 content slides returned **empty**
content), which **contradicted 176G** (which recovered the dense 5×5 proximity grid). Per
the trust-the-measurement rule, the contradiction was diagnosed before banking:

- With server-side **thinking enabled**, this qwen3vl-based server emitted the entire
  transcription into the hidden **reasoning channel** and returned an **empty** content
  field (`finish_reason=stop`, content length 0, reasoning length high).
- 176G ran with **thinking disabled**. Re-running with `enable_thinking=false` (via
  `chat_template_kwargs`) plus a larger token budget recovered well-formed tables on the
  same slides — **consistent with 176G**.

So the initial "failed" recovery was a **config confound, not an OCR-capability gap**; the
corrected run is the banked result. (The runner now hardwires thinking off.)

## 3. Closed extraction summary (real deck, local structured OCR — corrected run)

- `artifact_name=local_structured_ocr_content_extraction`
- `status=completed`
- `source_label=ensemble`
- `selected_slide_categories_count=5` (over **4 distinct pages** — one page satisfied two
  categories)
- `pages_rendered_count=5`
- `structured_ocr_status=ran_local` · `structured_ocr_engine=chandra_gguf_local` ·
  `cloud_ocr_used=false`
- `private_artifact_written=true` · `private_artifact_gitignored=true`
- `raw_ocr_committed=false` · `raw_table_text_committed=false` ·
  `rendered_images_committed=false` · `source_pdf_committed=false` ·
  `model_files_committed=false` · `model_cache_committed=false`
- `content_extraction_status=extracted`
- `extracted_text_block_count_bucket=high`
- `extracted_table_count_bucket=medium`
- `extracted_figure_or_diagram_count_bucket=low`
- `dense_grid_recovery_status=recovered`
- `patient_dataset_table_status=recovered`
- `gini_or_leaf_count_status=partial` (structure present; **not** a numeric verification)
- `proximity_matrix_status=recovered` (consistent with 176G's 5×5 recovery)
- `guide_content_readiness=ready_for_private_prompt_context_pilot`
- `visible_table_readiness=ready_for_visible_table_pilot`
- `numeric_recompute_readiness=needs_input_cell_parser`
- `gini_masked_recompute_from_ocr_status=not_attempted`
- `recommended_next_step=run_gini_input_cell_parser_on_private_artifact`

### Per-content-slide (closed; structural shapes only)

| slide_category | structured_ocr_status | table_recovered | dense_grid_recovered | figure_recovered | caption_or_context |
| --- | --- | --- | --- | --- | --- |
| ensemble_proximity_matrix | ran_local | yes | yes | no | yes |
| ensemble_patient_dataset_table | ran_local | yes | yes | no | yes |
| ensemble_gini_or_leaf_count | ran_local | yes | yes | yes | yes |
| ensemble_decision_tree_or_split_diagram | ran_local | yes | yes | no | yes |
| ensemble_weighted_frequency_or_total_error | ran_local | yes | yes | no | yes |

(`raw_output_committed` / `screenshot_committed` / `raw_values_committed` all `false`.)

## 4. Anti-laundering posture (numeric truth NOT claimed)

- "recovered" here means **slide structure/content was extracted** into the private
  artifact — it is **not** numeric verification.
- For Gini: a structured grid was recovered, but **no masked recompute was run** from raw
  input cells (the answer was not masked-and-recomputed), so `gini_or_leaf_count_status`
  stays `partial`, `numeric_recompute_readiness=needs_input_cell_parser`, and
  `gini_masked_recompute_from_ocr_status=not_attempted`. **Gini stays `unverified`.**
- A recovered answer/output table is never counted as a recovered numeric **input**.

## 5. Continuity and downstream order

- **Follows** 176G (local structured OCR recovers dense grids) and **does not contradict**
  it once the thinking confound is corrected; **follows** 176F (Tesseract alone failed
  dense/structured extraction) and **uses** the 176H private-artifact posture.
- First downstream consumer: a **private guide-context pilot** or **visible table/figure
  pilot** (Phase 4) over the private artifact.
- Later downstream consumer: **numeric recompute**, which requires a masked input-cell
  parser proof (Gini class-count grid, answer excluded) through the existing verifier
  before any number is trusted.

No cloud OCR; no provider/model generation; no guide-generation wiring; no Layer-2 judge;
no repair. No raw private OCR / table / source / guide text, private paths, filenames,
hashes, byte counts, screenshots, model files, or model caches committed.
`local_operator_baselines/` (incl. the private extracted-content artifact) stays ignored.
`judge_ready=false`; `repair_ready=false`. **NOT committed.**
