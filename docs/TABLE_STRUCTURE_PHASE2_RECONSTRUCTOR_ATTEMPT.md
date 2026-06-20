# TABLE_STRUCTURE_PHASE2_RECONSTRUCTOR_ATTEMPT.md — Slice 176C

> Closed attempt record for the one-table-family row/cell reconstructor. Closed
> tokens / counts / bools only: no guide / source / OCR / table text, no formulas,
> no raw values, no private paths / filenames / hashes / byte counts / screenshots,
> no provider payloads / prompts / responses / secrets. The repo is the source of
> truth; verify the module before relying on this.

---

## 0. What this slice is

Acting on Slice 176B's `next_step=build_one_table_family_row_cell_reconstructor`,
this slice builds a **focused, local-only** row/cell reconstructor for **exactly
one** table family on **one** deck and runs it on the real source. It is **not** a
generic table-reconstruction framework, an audit, a source-input bridge, a
prompt/generation slice, Chandra, or cloud OCR.

- module: `pipeline/quality_safety_one_table_family_row_cell_reconstructor.py`
- test: `test_scripts/test_quality_safety_one_table_family_row_cell_reconstructor.py`

## 1. Selection (closed)

- `selected_source_label=ensemble`
- `selected_target_id=proximity_4_3`
- `selected_target_family=proximity`
- `selection_reason=fewer_join_requirements` (proximity is a single ratio;
  weighted_average needs aligned values+weights → more cross-table joins)
- non-selected: `weighted_weight_impute` · `non_selected_target_reason=more_join_requirements`

Selection used region/structure signal strength only — **no** fixture expected
values, answer strings, guide text, or hand-authored target maps.

## 2. The missing piece (the reconstruction step)

Linear text extraction collapses a table to **one token per line** — the row/cell
grid is destroyed. The genuine reconstruction step is **spatial clustering of
positioned tokens (`{x, y, text}`) into rows (by `y`) and cells (by `x`)**. The
module consumes already-extracted positioned tokens for one region; it runs no OCR,
opens no PDF, and reaches no network (the selected deck is text-extractable, so
`local_ocr_status=skipped`). It reuses `SUPPORTED_METHODS` and the real
`recompute_quality_safety_fact` — no parallel recompute engine.

## 3. Anti-laundering (enforced in code, proven in test)

- A proximity **matrix** (cells are proximity *values*, decimals in (0,1)) is the
  **answer**, not an input → refused (`blocked_by=source_input_mapping`, warning
  `answer_matrix_not_input`).
- A lone result value is refused (`answer_value_not_input`).
- Hand-authored rows, fixture-derived values, answer strings, and generated-guide
  candidate values are never inputs. A created record requires
  `source_input_origin=parsed_from_extraction_output` **and** a masked recompute
  that yields a finite value with the answer hidden from the parser.

## 4. Synthetic proof (test)

Public-safe positioned tokens only. The full chain is exercised end-to-end:
reconstruct → inputs → **masked** recompute through the REAL verifier.

- proximity per-tree `same_terminal_node` indicators → ratio recomputes (answer
  masked) → `status=passed`.
- weighted_average values+weights → mean recomputes (answer masked) → `status=passed`.
- anti-laundering refusals, unavailable-region, empty-grid, malformed-token, and
  unsupported-family degrade paths all return closed blocked records without raising.
- the committed `record` is closed-vocabulary only (no floats / raw values).

## 5. Real-deck attempt (closed result)

Ensemble proximity region, via a **gitignored** local harness (not committed);
only closed labels are reported here.

- `status=blocked`
- `target_region_status=found`
- `crop_or_region_input_status=available`
- `local_ocr_status=skipped`
- `row_cell_extraction_status=parsed_from_extraction_output` (grid reconstructed:
  rows / columns / numeric cells all nonzero)
- `source_input_record_status=not_created`
- `source_input_origin=none`
- `machine_consumable_for_recompute=false`
- `masked_recompute_status=not_run`
- `blocked_by=source_input_mapping`
- warnings include `answer_matrix_not_input`
- `hand_authored_rows=false` · `fixture_derived=false` · `answer_string_derived=false`
  · `guide_candidate_derived=false` · `raw_values_committed=false` · `raw_ocr_committed=false`

**Finding:** the reconstructor works on real data — it rebuilt the grid — but the
source contains the proximity **answer matrix**, not the per-tree **inputs** (leaf
assignments / same-terminal-node counts). No machine-consumable source-input record
can be created without laundering answer values, which the module refuses.

## 6. Decision rule and next step

This corroborates 174A/175A `source_input_missing` and trends toward classifying
`proximity_4_3` as **absent-in-source** (only the answer is present), which is a
different failure type from extraction-gated: it does **not** route to OCR.

- `next_step=target_region_detection_for_numeric_tables` — attempt detection of the
  **input** numeric table; if confirmed absent, record `proximity_4_3` as
  absent-in-source and stop routing it through extraction/OCR.

No Chandra; no cloud OCR; no provider/model generation; no Layer-2 judge; no repair.
`judge_ready=false`; `repair_ready=false`.
