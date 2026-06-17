# Quality Safety Operator Validation

## Slice 115

Slice 115 is an offline operator validation slice for the deterministic Quality Safety safety floor. It is docs-only and
does not add production code, tests, runtime artifact writers, CLI scripts, real fixtures, generated outputs, JSONL logs, or
judge logic.

The validation checks whether the completed Slices 108-114 deterministic floor catches real operator failures when supplied
with private local operator material and a hand-built local fact sheet. The committed record is closed-vocabulary only.

Slice 115 isolates the deterministic safety detectors on real private operator material using a hand-built local fact sheet.
It validates recompute/leak/unified-QA behavior, not the extraction-to-fact-sheet leg. The extraction leg remains
unvalidated and is the purpose of the next engineering slice. A green detector result in Slice 115 does not mean the
production app catches the failure end-to-end yet.

## Contract Inspection

```json
{
  "validation_id": "quality_safety_contract_inspection_v1",
  "status": "completed",
  "weighted_gini_leaf_count_inputs_supported": true,
  "weighted_gini_group_count_inputs_supported": true,
  "fact_sheet_computation_field_safe_for_weighted_gini": true,
  "recompute_report_shape": "numeric_supplied_recomputed_tolerance_only",
  "unified_qa_aggregates_recompute_and_leak_blockers": true,
  "unified_qa_raw_snippets_stored": false,
  "leak_scanner_context_attachment": "safe_fact_ids_or_labels_only",
  "contract_blocker": false
}
```

## Scope Honesty

```json
{
  "validation_id": "quality_safety_scope_honesty_v1",
  "extraction_leg_covered": false,
  "detectors_covered": [
    "recompute",
    "leak",
    "unified_qa"
  ],
  "fact_sheet_kind": "hand_built_local",
  "production_end_to_end_covered": false,
  "next_engineering_slice": "extraction_to_fact_sheet_producer"
}
```

## Validation Records

```json
[
  {
    "validation_case": "legacy_confused_wrong_case",
    "input_kind": "private_local_operator_material",
    "fact_sheet_kind": "hand_built_local",
    "extraction_leg_covered": false,
    "weighted_gini_contract_supported": true,
    "unified_status": "failed",
    "shippable": false,
    "safety_floor_green": false,
    "expected_legacy_failure_detected": true,
    "blocking_checks": [
      "layer1:leaked_reasoning",
      "layer1:numeric_correctness",
      "recompute:weighted_gini",
      "leak:quality_safety_leak_scan"
    ],
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false
  },
  {
    "validation_case": "single_confident_wrong_numeric_case",
    "input_kind": "private_local_operator_material",
    "fact_sheet_kind": "hand_built_local",
    "extraction_leg_covered": false,
    "weighted_gini_contract_supported": true,
    "single_wrong_value_only": true,
    "contradiction_required": false,
    "leak_required": false,
    "unified_status": "failed",
    "shippable": false,
    "safety_floor_green": false,
    "blocking_checks": [
      "recompute:weighted_gini"
    ],
    "expected_legacy_failure_detected": true,
    "failure_category": "confident_wrong_value_detected",
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false
  },
  {
    "validation_case": "clean_real_case",
    "input_kind": "private_local_operator_material",
    "fact_sheet_kind": "hand_built_local",
    "extraction_leg_covered": false,
    "weighted_gini_contract_supported": "not_applicable_or_true",
    "unified_status": "failed",
    "shippable": false,
    "safety_floor_green": false,
    "blocking_checks": [
      "layer1:leaked_reasoning",
      "leak:quality_safety_leak_scan"
    ],
    "clean_case_passed": false,
    "failure_category": "clean_case_false_positive",
    "component_miss_tokens": [
      "false_positive_leak"
    ],
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false
  }
]
```

## Safety Boundary

- Committed docs contain only closed-vocabulary validation outcomes.
- No real PDFs, images, DOCX/PDF/ZIPs, runtime artifacts, generated guides, eval outputs, or runtime JSON outputs are added.
- No real source/reference filenames, uploaded quality-spec filenames, evidence quotes, snippets, OCR/table/caption text,
  paths, URLs, image bytes, formulas copied from private/generated material, or provider payloads are added.
- No `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl` is added.
- No `overall_10` or judge score is computed.
- No provider/model/cloud call is made.
- No generation, prompt, request schema, API, UI, render, export, OCR, table, visual, or Ask Guide behavior is changed.
- Docker validation is optional for this docs/operator-validation slice; docker compose config must not be run.

Slice 115 is NOT committed.
