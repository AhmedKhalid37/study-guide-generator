# TABLE_STRUCTURE_PHASE2_SEAM_MAP.md — Phase 2 row/cell reconstruction seam

> Slice 176B closed inventory + seam map. **No new extraction code.** This is a
> read-only inventory of the existing visual/table pilot stack plus an NN3-separate
> recoverability check, used to define the exact boundary where region detection
> ends and row/cell reconstruction must begin. Closed tokens / counts / bools only:
> no guide / source / OCR / table text, no formulas, no private paths, filenames,
> hashes, byte counts, screenshots, provider payloads, prompts/responses, or
> secrets. The repo is the source of truth; verify modules before relying on this.

---

## 0. Why this slice exists

Slice 175A proved the existing extraction outputs are **not machine-consumable
structured numeric input**, and Slice 176A confirmed (by actually trying) that the
two source-input-missing Ensemble targets (`proximity_4_3`,
`weighted_weight_impute`) stay `blocked` / `table_structure_missing`. Before
building any extractor, this slice (a) checks whether NN3 is easier than Ensemble
and may not need table reconstruction at all, and (b) inventories what the existing
visual/table pilot stack already produces, where it stops, and the input/output
contract for the missing row/cell reconstructor.

**This slice adds no extraction code, no row/cell extractor, and no framework
code.** It is not another recoverability audit, source-input bridge,
numeric-context plumbing, prompt/generation slice, or visual-manifest rebuild. No
Chandra; no cloud OCR.

---

## 1. NN3 separate recoverability check (Part 1B)

NN3 is `partial_text`, so it is worth asking whether its numeric inputs can be
parsed by the existing **non-table** numeric chain without any table
reconstruction. Inspected existing producers only; wrote no new NN3 parser.

The existing numeric chain is:
`quality_safety_safe_numeric_extractor` → `quality_safety_numeric_extraction_mapper`
→ `quality_safety_fact_sheet_producer` → `quality_safety_recompute_verifier`. Every
module in that chain is **pure and unwired** and consumes only
**caller-supplied sanitized numeric candidates / in-memory dicts** — none of them
reads source documents, `clean.md`, OCR/page/table text, or parses numeric values
out of extraction output. The `quality_safety_extraction_bundle_adapter` (grounded
in the Slice 120 metadata inspection) records the decisive fact: structural counts
are recoverable (`leaf_count_recoverable=yes`) but **per-fact numeric content
observations are not** (`numeric_observation_recoverable=no`), and v1 never
fabricates them.

Closed report:

- `source_label=nn3`
- `source_quality=partial_text`
- `targets_considered=5`
- `existing_structured_source_input_producer_exists=true` (the unwired numeric chain exists)
- `producer_ran=true` (inspected; runs on caller-supplied candidates)
- `producer_output_has_target_records=false`
- `parsed_from_existing_extraction_count=0`
- `machine_consumable_count=0`
- `source_input_records_created_count=0`
- `answer_string_only_count=0`
- `hand_located_count=0`
- `fixture_derived_count=0`
- `guide_candidate_derived_count=0`
- `remaining_source_required_count=5`
- `nn3_free_numeric_path_status=unstructured_text_only`

**Hard-rule outcome:** no existing producer creates structured input records for
NN3 from extraction, so this slice **does not** hand-author or build a new NN3
parser. NN3's `partial_text` yields prose/structural signals, not parsed numeric
facts; it is not a free win and is recorded honestly as blocked.

---

## 2. Existing visual/table pilot inventory (Part 1C)

Closed reuse map for the existing stack:

- `existing_visual_manifest_exists=true` (`visual_assets_manifest.py`, the sanitizer/security boundary)
- `existing_visual_asset_extractor_exists=true` (`visual_asset_extractor.py`, Slice 40)
- `existing_table_candidate_manifest_exists=true` (`table_candidate_manifest.py`, Slice 92)
- `existing_reconstructable_table_detection_exists=true` (candidate-level region detection only)
- `existing_table_reconstruction_policy_exists=true` (`table_reconstruction_policy.py`, Slice 85)
- `existing_row_cell_reconstruction_exists=false`
- `existing_crop_generation_exists=true` (`visual_asset_extractor` crops embedded regions to PNG, gated off by default)
- `existing_region_detection_reusable=true`
- `existing_table_candidate_decision_tokens_reusable=true`
- `existing_stack_outputs_cell_values=false`
- `existing_stack_outputs_rows_cells=false`
- `existing_stack_outputs_counts_only=true` (table candidate manifest emits counts + decision tokens, never cell values)
- `existing_stack_outputs_region_crops=true` (extractor crops, advisory-only, gated)
- `slice60_stash_relevant=false`
- `slice60_stash_relevance=selection_trace`
- `reuse_boundary=region_detection_plus_crops`
- `missing_piece=row_cell_reconstruction`

What each piece does and where it stops:

- `visual_asset_extractor.py` — local-only (`fitz_local`) PyMuPDF crop of embedded
  image regions into `extracted_figure` PNG assets with a bbox + safe relative ref.
  Produces **region crops, not numeric cells**. Gated off by default
  (`GUIDEFORGE_LOCAL_FIGURE_EXTRACTION`); advisory-only; no OCR, no network.
- `visual_assets_manifest.py` — re-sanitizes asset records into the manifest (the
  security boundary). Closed fields only.
- `table_candidate_manifest.py` — derives sanitized table candidates from the
  visual manifest. Emits **counts + decision tokens** (region/structure signals),
  **never cell values**; reconstructs nothing, reads no PDF/image, no OCR, no crop.
- `table_reconstruction_policy.py` — **decision-only** layer
  (`reconstruct_with_original` / `simplify_only` / `defer` / `skip_unreadable` /
  `skip_unsafe`). Pure and unwired; does **not** reconstruct rows/cells, read PDFs,
  OCR, or read values. `screenshot_insert_count` is always 0.

**Conclusion:** the stack detects table **regions** and can crop them, and has a
decision policy for what to do with them, but **nothing reconstructs rows/cells**
or maps a region/crop to structured numeric `inputs`. That mapping is the gap.

---

## 3. Slice 60 stash read-only relevance (Part 1A)

Inspected name-only / stat only — **not** applied, popped, dropped, or restored.
The stash touches docs plus a job-runtime wiring file and a
visual-**markdown-insertion** module. By category it is a visual-pilot
**selection/insertion trace** (which visuals get placed into the rendered guide),
i.e. downstream student-visible rendering — **not** numeric row/cell extraction.

- `slice60_stash_relevant=false` (for the row/cell reconstructor seam)
- `slice60_stash_relevance=selection_trace`

It is potentially relevant **later** to Phase 2 step 4 (student-visible table
insertion / simplified table explanations), not to the reconstruction extractor.
The stash stays parked and untouched.

---

## 4. Reuse boundary and missing piece

- `reuse_boundary=region_detection_plus_crops` — region detection + decision tokens
  (`table_candidate_manifest`) and region crops (`visual_asset_extractor`) are
  reusable as the reconstructor's **input** surface.
- `missing_piece=row_cell_reconstruction` — there is no code that turns a detected
  region / crop into structured rows/cells and then into a machine-consumable
  `source_inputs_by_target` record.

---

## 5. Row/cell reconstructor seam contract (Part 1D — definition only, not built)

### reconstructor_input_contract

- `source_label` — closed source label (e.g. `ensemble`)
- `target_id` — one focused target id
- `target_family` — recompute family (`proximity` | `weighted_average`)
- `region_token_or_crop_token` — closed candidate/crop handle (no path/filename/bytes)
- `region_source` — closed token (`existing_table_stack` | `existing_visual_manifest` | `local_ocr` | `fitz_signal`)
- `local_private_ocr_source` — local-only, existing-Tesseract path; never Chandra, never cloud
- `table_candidate_token` — `table_candidate_manifest` candidate handle (closed id only)
- `safe_page_or_region_reference` — closed/ordinal page-or-region reference (no private page text)

### reconstructor_output_contract

- `source_label`
- `target_id`
- `target_family`
- `row_cell_extraction_status` — `structured_rows` | `partial_structure` | `ocr_prose_only` | `not_found` | `not_run`
- `source_input_record_status` — `created` | `partial` | `not_created`
- `source_input_origin` — must be `parsed_from_extraction_output` to count (hand-authored / fixture-derived / answer-string-derived rejected)
- `machine_consumable_for_recompute` — bool; true only when origin is `parsed_from_extraction_output` **and** structure is `structured_rows` **and** it carries a supported method + structured `inputs` dict matching the family
- `blocked_by` — closed token (`table_structure_missing` | `target_region_missing` | `ocr_prose_only` | `ambiguous_rows` | `unsupported_target_family` | `source_artifact_unavailable` | `none`)
- `warnings` — ordered closed tokens

The created record must be shaped so it drops straight into the existing recompute
input the verifier already accepts:
`source_inputs_by_target = {target_id: {"method": <supported>, "inputs": {...},
"value_kind": "numeric", "confidence": "high"|"medium"}}` — exactly what
`_source_recompute_plan_lookup` consumes. No new recompute engine; reuse
`SUPPORTED_METHODS`.

### privacy_contract

- `no_raw_ocr_text=true`
- `no_table_text=true`
- `no_raw_values_in_committed_artifacts=true`
- `no_private_paths_or_filenames=true`
- `no_hashes_or_byte_counts=true`

### success_bar

- `one_table_family_one_deck_end_to_end`
- `parsed_from_extraction_output`
- `recompute_proof_from_parsed_inputs`
- `no_hand_authored_rows`
- `no_fixture_truth`
- `no_answer_string_inputs`

---

## 6. Decision rule (Part 1F)

Evaluating the rule against this inventory:

- (A) NN3 existing producer makes machine-consumable records? **No** (`nn3_free_numeric_path_status=unstructured_text_only`).
- (B) Existing table stack already has rows/cells? **No** (`existing_stack_outputs_rows_cells=false`).
- (C) Existing stack provides region detection/crops but not rows/cells? **Yes** (`reuse_boundary=region_detection_plus_crops`, `missing_piece=row_cell_reconstruction`).
- (D) Target regions unidentifiable? **No** (region detection + crops exist).
- (E) No reusable stack? **No** (a reusable region/crop stack exists).

**`next_step=build_one_table_family_row_cell_reconstructor`** (Slice 176C) — a
focused, local-only row/cell reconstructor for **one** Ensemble table family on
**one** deck, consuming the reuse boundary above and emitting the
reconstructor_output_contract record so the existing verifier can recompute the
target from parsed (not hand-located) inputs. Not another audit, not another
source-input bridge, not a context hook; not Chandra; not cloud OCR; not a generic
table-reconstruction framework.
