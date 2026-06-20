# TABLE_STRUCTURE_PHASE2_INPUT_EXISTENCE_CLASSIFICATION.md — revised Slice 176D

> Closed record for the numeric-target input-existence classifier. Closed tokens /
> counts / bools only: no guide / source / OCR / table text, no formulas, no raw
> values, no private paths / filenames / hashes / byte counts / screenshots, no
> provider payloads / prompts / responses / secrets. The repo is the source of
> truth; verify the module before relying on this.

---

## 0. Why this slice exists

176C built the one-table-family row/cell reconstructor and ran it on the real
Ensemble proximity region: it **rebuilt the grid**, but the grid was the proximity
**answer matrix** (decimal cells in (0,1)), not the per-tree computation **inputs**.
Anti-laundering refused the answer matrix as input.

The first (uncommitted) 176D then built a target-region detector and concluded
`improve_target_region_detection` — but it routed to "detect harder" off a
**zero typed-candidate** manifest, **without first proving an input table exists**.
That framing was abandoned. The correct prior question is **input existence**:

> For each relevant hard-deck numeric target, does the **source** contain the
> computation **inputs**, or only the **answer / result**?

This decides which targets are worth reconstructing (inputs present) and which must
be marked **unverifiable-from-source** (answer-only — no OCR / region detection
recovers an input that is not there).

## 1. The 176C laundering contradiction — resolved from disk first

Two pasted reports disagreed. Resolved against commit `1771dd9`:

- The `passed` masked recompute belongs to the **synthetic public-safe test**
  (§4 of `TABLE_STRUCTURE_PHASE2_RECONSTRUCTOR_ATTEMPT.md`) that exercises the chain.
- The **real Ensemble deck** (§5) refused the answer matrix and never ran masked
  recompute. Code path: `_map_proximity` → `blocked_by=source_input_mapping` → the
  function returns a blocked record **before** `_masked_recompute`/the verifier.

Clean 176C disk verdict (closed): `masked_recompute_status=not_run` ·
`source_input_record_status=not_created` · `source_input_origin=none` ·
`machine_consumable_for_recompute=false` · `anti_laundering_answer_matrix_refused=true` ·
`verifier_called_on_answer_matrix=false` · `clean_176c_verdict=commit_stands_honest_blocker`.
**1771dd9 stands; no revert.** The "masked recompute passed" phrase was a
pasted-report artifact, not disk truth.

## 2. What this slice is / is not

- module: `pipeline/quality_safety_numeric_target_input_existence.py`
- test: `test_scripts/test_quality_safety_numeric_target_input_existence.py`

**IS:** a closed classification of whether each relevant hard-deck numeric target has
computation inputs present, only answer/result present, or inconclusive/absent.
**IS NOT:** a recoverability audit, a source-input bridge, numeric plumbing, a
prompt/generation slice, a visual-manifest rebuild, a generic table framework,
target-region detection improvement, generation wiring, a Layer-2 judge, or repair.
No Chandra; no cloud OCR. `judge_ready=false`; `repair_ready=false`.

## 3. Method (closed, no raw source touched)

The classifier is **pure and total**: it consumes closed per-target evidence
descriptors (booleans / closed tokens / small counts that summarize **already
committed** closed findings) and emits a closed classification. It reads no files,
opens no PDF, runs no OCR, and reaches no network. It never consumes fixture values,
answer strings, generated-guide candidates, or hand-authored rows.

The committed Ensemble evidence vector encodes only closed findings, attributed:

- **173C** recoverability report: `computation_input_present_count=5`,
  `computation_input_partial_count=2` (targets_considered=7); high-risk Gini
  masked-recompute spot-check **passed** for `gini_weight_gt_176` only.
- **174A**: `proximity_4_3` & `weighted_weight_impute` method-gated →
  `source_input_missing` after methods added (no source-derived structured records).
- **175A / 176A**: no machine-consumable parsed source-input record exists for any
  target (`machine_consumable=0`).
- **176C**: `proximity_4_3` source region reconstructs to the **answer matrix**, not
  inputs; the closed candidate manifest surfaced **0** typed regions for it.

## 4. Synthetic proof (test)

Public-safe descriptors only. Branch coverage: recovered-inputs → present;
masked-passed → present (no spot-check warning); parsed record → present +
`machine_consumable_now=true`; answer matrix → `answer_output_only`; recovered
beats answer-matrix → present (`mixed`); searched-absent → `absent_or_not_found`;
partial → `inconclusive`; no evidence → `inconclusive` (`no_closed_evidence`).
Decision rule, empty-skip, totality on malformed input, the closed-vocab contract,
and the committed Ensemble tallies are all asserted. (120 checks.)

## 5. Closed Ensemble classification result

- `status=completed` · `source_label=ensemble`
- `targets_considered_count=7`
- `computation_input_present_count=5`
- `answer_output_only_count=1`
- `absent_or_not_found_count=0`
- `inconclusive_count=1`
- `reconstruction_candidate_count=5`
- `source_unverifiable_count=1`
- all per-target `machine_consumable_now=false` (no parsed record committed yet)
- `next_step=reconstruct_present_input_target` (Part 1F rule A)

Per-target (closed):

| target_id | existence_status | evidence_basis | priority | future_action |
|---|---|---|---|---|
| gini_chest_pain | computation_input_present | existing_recompute_sidecar | high | reconstruct_rows_cells |
| gini_blocked_arteries | computation_input_present | existing_recompute_sidecar | high | reconstruct_rows_cells |
| gini_weight_gt_176 | computation_input_present | existing_recompute_sidecar | high | reconstruct_rows_cells |
| total_error_stump_1 | computation_input_present | existing_recompute_sidecar | high | reconstruct_rows_cells |
| amount_of_say_half_ln_7 | computation_input_present | existing_recompute_sidecar | high | reconstruct_rows_cells |
| proximity_4_3 | answer_output_only | mixed | none | mark_unverifiable_from_source |
| weighted_weight_impute | inconclusive | existing_recompute_sidecar | medium | inspect_more_closed_evidence |

`gini_weight_gt_176` is masked-recompute-proven; the other four input-present targets
carry `single_target_spot_check_only`. `proximity_4_3` carries `answer_matrix_not_input`
and `no_typed_candidate_region`.

## 6. Decision and product reframe

**Numeric recompute for Ensemble continues — but pivots target.** Do **not** keep
chasing proximity's input table and do **not** improve its region detection: proximity
is **answer-only / unverifiable-from-source**. The worthwhile reconstruction work is the
**input-present** Gini / total-error / amount-of-say targets →
`reconstruct_present_input_target`.

**Product reframe:** the reconstructable proximity **answer/output** matrix is still
useful for **student-visible table/figure insertion** even though it cannot verify
numerics. A reconstructable answer table is a presentation asset, not a recompute input.

No Chandra; no cloud OCR; no provider/model generation; no Layer-2 judge; no repair.
`used_fixture_values=false` · `used_answer_strings=false` · `used_generated_guide_text=false`
· `used_hand_authored_rows=false` · `raw_text_committed=false` · `raw_values_committed=false`.
