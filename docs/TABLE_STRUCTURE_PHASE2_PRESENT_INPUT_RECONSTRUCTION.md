# TABLE_STRUCTURE_PHASE2_PRESENT_INPUT_RECONSTRUCTION.md — Slice 176E

> Closed attempt record for the present-input target reconstructor. Closed tokens /
> counts / bools only: no guide / source / OCR / table text, no formulas, no raw
> values, no private paths / filenames / hashes / byte counts / screenshots, no
> provider payloads / prompts / responses / secrets. The repo is the source of
> truth; verify the module before relying on this.

---

## 0. What this slice is

Acting on revised 176D's `next_step=reconstruct_present_input_target`, this slice is
the **validation test** for **exactly one** of 176D's five `computation_input_present`
candidates: does the selected target's computation-**input** table actually exist in
the source deck in a form the local extractor/reconstructor can find and parse, when
the region is **rediscovered cold from extraction signals** — no hand-located region,
no prior spot-check hint, no fixture value, no answer value supplied to the parser?

- module: `pipeline/quality_safety_present_input_target_reconstructor.py`
- test: `test_scripts/test_quality_safety_present_input_target_reconstructor.py`

**IS:** a focused, local-only one-target row/cell class-count reconstruction attempt.
**IS NOT:** another recoverability audit, a source-input bridge, numeric plumbing, a
prompt/generation slice, a visual-manifest rebuild, a generic table framework,
proximity target-region detection, generation wiring, a Layer-2 judge, or repair.
No Chandra; no cloud OCR; no provider/model generation. `judge_ready=false`;
`repair_ready=false`.

**Critical framing:** 176E does **not** inherit 176D's `computation_input_present_count=5`
as proven source truth. 176D classified from committed closed evidence; 176E re-opens
**one** target against the source to see whether that optimism survives cold
rediscovery.

## 1. Selection (closed)

- `selected_source_label=ensemble`
- `selected_target_id=gini_chest_pain`
- `selected_target_family=weighted_gini`
- `selection_reason=simplest_row_cell_mapping` + `cleaner_extraction_region` — a
  categorical Gini split has the simplest 2-class-count mapping and avoids reusing
  `gini_weight_gt_176`'s prior **hand-located** spot-check region (which the
  anti-laundering rule forbids feeding the parser) and avoids chaining a downstream
  formula (total_error / amount_of_say).
- non-selected: `gini_blocked_arteries`, `gini_weight_gt_176`, `total_error_stump_1`,
  `amount_of_say_half_ln_7` → `deferred_by_scope` (one target per slice);
  `proximity_4_3` → `answer_output_only`; `weighted_weight_impute` → `inconclusive`.

Selection used closed input-presence + mapping-simplicity signals only — **no**
fixture expected values, answer strings, guide text, or hand-authored rows.

## 2. Method (cold rediscovery, local only)

The reconstructor consumes positioned `{x, y, text}` tokens for a region the caller
**rediscovered from extraction anchors** (the target's own identity — `gini` / `chest`
— located on the page by extraction, not by hand-supplied coordinates or a spot-check
hint). It reuses the committed 176C grid clusterer (`_reconstruct_grid`, not a
parallel grid engine) and the real `recompute_quality_safety_fact` / `SUPPORTED_METHODS`
(not a parallel recompute engine). Local PyMuPDF word extraction only — no OCR, no
Chandra, no cloud, no network.

**Credibility guard (the decisive correctness fix).** A first naive mapping that
accepted *any* row with ≥2 integers as a class-count "group" produced a **false
positive** on the real deck (it grabbed 2 coincidental small integers and a masked
recompute returned a finite Gini). That is exactly the GATE-2 confound — answer/finite
presence ≠ inputs present. The mapper now requires an **x-column-aligned integer grid**
(≥2 shared columns, each ≥2 cells; ≥2 multi-column rows) — a magnitude-agnostic,
answer-agnostic test for "is this actually a class-count table," not coincidental
integers on unrelated lines. The Gini **value** (a unit-interval decimal) is the
*answer* and is refused as input.

## 3. Anti-laundering (enforced in code, proven in test)

- A created, machine-consumable record requires `source_input_origin=parsed_from_extraction_output`,
  a credible x-aligned integer class-count grid, **and** a masked recompute that yields
  a finite value with the answer hidden from the parser.
- Unit-interval decimal cells (Gini values) are refused (`answer_matrix_not_input`,
  `blocked_by=source_input_mapping`).
- A **hand-located region or prior spot-check hint is refused outright**
  (`blocked_by=privacy_boundary`); the parser must rediscover the region from
  extraction. `parser_received_hand_located_region=false`,
  `parser_received_spot_check_region_hint=false`.
- Hand-authored rows, fixture-derived values, answer strings, and generated-guide
  candidate values are never inputs.

## 4. Synthetic proof (test)

Public-safe positioned tokens only (invented small integers / decimals). The full
chain is exercised end-to-end: x-aligned class-count grid → weighted-Gini inputs →
**masked** recompute through the REAL verifier (finite Gini in (0,1)). Anti-laundering
(answer decimals refused), the hand-located / spot-check provenance guard, the
no-input-region and unsupported-family degrade paths, totality on malformed input, and
the closed-vocab / no-raw-float contract are all asserted. (76 checks.)

## 5. Real-deck attempt (closed result)

Ensemble source deck, gini_chest_pain region rediscovered cold via a **gitignored,
transient** harness (not committed); only closed labels are reported here.

- `status=blocked`
- `selected_region_origin=discovered_from_extraction`
- `parser_received_hand_located_region=false` · `parser_received_spot_check_region_hint=false`
- `target_region_status=found` (an anchor region was located)
- `row_cell_extraction_status=parsed_from_extraction_output` (a grid was rebuilt)
- `source_input_record_status=not_created`
- `source_input_origin=none`
- `inputs_status=unavailable`
- `machine_consumable_for_recompute=false`
- `masked_recompute_status=not_run`
- `input_presence_claim_basis=inconclusive`
- `input_presence_confirmed_against_source=inconclusive`
- `source_confirmation_status=no_input_region_found`
- `blocked_by=row_cell_reconstruction`
- warnings include `no_input_columns_found`
- `hand_authored_rows=false` · `fixture_derived=false` · `answer_string_derived=false`
  · `guide_candidate_derived=false` · `raw_values_committed=false` · `raw_ocr_committed=false`

**Finding.** When the region is rediscovered cold from extraction, the source does
**not** expose a machine-parseable, column-aligned class-count **input** table for
`gini_chest_pain`. The only integers extraction recovers on the anchor region are
coincidental (no shared columns, no corroborating printed Gini). This is **consistent
with** 174A/175A (`source_input_missing`), 176A (`machine_consumable=0`), and 176C
(answer matrix, `typed_candidate_region_count=0`): this deck presents worked
**answers** and tree **diagrams**, not typed class-count input tables in extractable
text.

## 6. Decision and verdict

Per the 176E verdict rule: the selected input-present target did **not** parse cold
and a masked recompute did **not** pass; no input region was confirmed. Therefore
**176D's `computation_input_present` for `gini_chest_pain` was prior-evidence optimism,
not source-confirmed truth.** Do **not** keep treating the five-count as hard fact.

- `next_step=improve_input_region_evidence` (the inputs, if present at all, are in
  tree-diagram **images** / prose, not extractable text — that is a heavier image-region
  path, not text reconstruction) **or** `choose_different_input_present_target`.
- Slice-level recommendation: try at most one more input-present Gini target with the
  same cold-rediscovery bar. **If it also collapses to inconclusive / answer-only,
  stop the numeric grind on Ensemble and pivot table reconstruction toward
  student-visible table/figure insertion** (the reconstructable proximity answer/output
  matrix remains a presentation asset, never a recompute input).

No Chandra; no cloud OCR; no provider/model generation; no guide regeneration; no
Layer-2 judge; no repair. `judge_ready=false`; `repair_ready=false`.
