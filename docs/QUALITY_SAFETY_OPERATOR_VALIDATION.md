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

## Slice 116

Slice 116 hardens the deterministic leak scanner against the clean-case false positive found by Slice 115. It changes only
the unwired offline leak scanner, synthetic tests, and closed-vocabulary docs. It does not add production wiring,
fact-sheet production, judge logic, prompt tuning, repair, providers, or runtime artifact writers.

## Slice 116 Root Cause

```json
{
  "validation_id": "quality_safety_leak_false_positive_root_cause_v1",
  "status": "completed",
  "root_cause_tokens": [
    "leak_boundary_false_positive",
    "technical_weight_term_false_positive"
  ],
  "fix_tokens": [
    "boundary_safe_fixed_signature_matching",
    "technical_weight_term_clean_case"
  ],
  "raw_text_committed": false,
  "raw_paths_committed": false,
  "runtime_outputs_committed": false
}
```

## Slice 116 Scope Honesty

```json
{
  "validation_id": "quality_safety_scope_honesty_v2",
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

## Slice 116 Validation Records

```json
[
  {
    "validation_case": "legacy_confused_wrong_case",
    "input_kind": "private_local_operator_material",
    "fact_sheet_kind": "hand_built_local",
    "extraction_leg_covered": false,
    "unified_status": "failed",
    "detected": true,
    "shippable": false,
    "safety_floor_green": false,
    "blocking_checks": [
      "layer1:leaked_reasoning",
      "layer1:numeric_correctness",
      "recompute:weighted_gini",
      "leak:quality_safety_leak_scan"
    ],
    "failure_category": "legacy_confused_case_detected",
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
    "unified_status": "failed",
    "detected": true,
    "shippable": false,
    "safety_floor_green": false,
    "blocking_checks": [
      "recompute:weighted_gini"
    ],
    "contradiction_required": false,
    "leak_required": false,
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
    "unified_status": "passed",
    "clean_case_passed": true,
    "shippable": true,
    "safety_floor_green": true,
    "blocking_checks": [],
    "failure_category": "none",
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
- Docker validation is optional for Slice 116 because it changes only an offline Quality Safety helper plus docs/tests; docker
  compose config must not be run.

## Slice 117 Extraction-Leg Note

```json
{
  "validation_id": "quality_safety_extraction_leg_scope_v1",
  "slice": "117",
  "extraction_leg_work_started": true,
  "input_kind": "synthetic_sanitized_extraction_bundle",
  "production_end_to_end_covered": false,
  "real_pdf_parsing": false,
  "clean_md_read": false,
  "directory_scan": false,
  "job_artifact_write": false,
  "production_job_wiring": false,
  "provider_calls": false,
  "judge_calls": false
}
```

## Slice 118 Advisory Job Artifact Note

```json
{
  "validation_id": "quality_safety_advisory_job_artifact_scope_v1",
  "slice": "118",
  "artifact_name": "quality_safety_unified_qa.json",
  "production_job_wiring": true,
  "advisory_only": true,
  "blocks_job_success": false,
  "repairs_or_rewrites": false,
  "prompt_or_provider_request_change": false,
  "provider_calls": false,
  "judge_calls": false,
  "stores_raw_guide_or_source_text": false,
  "stores_paths_or_filenames": false,
  "stores_evidence_quotes": false,
  "stores_runtime_traces": false,
  "missing_extraction_bundle_behavior": "component_missing_or_skipped"
}
```

## Slice 123 Advisory Artifact-Path Validation

Slice 123 is distinct from the Slice 115 / 116 detector-only operator validation.
Slices 115–116 isolated the deterministic detectors (recompute / leak / unified
QA) on private operator material using a **hand-built local fact sheet** — they
did not exercise the production artifact path and did not cover the extraction
leg. Slice 123 instead validates the **actual advisory `quality_safety_unified_qa.json`
job artifact path** after the Slice 122 structural-coverage wiring, and separates
two legs explicitly:

- **structural coverage leg** — wired into the advisory artifact via
  `extraction_coverage_bundle` (present with safe structural metadata; `skipped`
  otherwise);
- **numeric fact-sheet extraction leg** — still NOT covered through the
  production hook, which never produces a concept/fact bundle.

### Slice 123 Scope Honesty

```json
{
  "validation_id": "quality_safety_advisory_artifact_path_scope_v1",
  "slice": "123",
  "artifact_name": "quality_safety_unified_qa_json",
  "artifact_kind": "quality_safety_job_artifact",
  "advisory_non_blocking": true,
  "structural_coverage_leg_covered": true,
  "numeric_fact_sheet_extraction_leg_covered": false,
  "synthetic_track_a_checks": "41_passed",
  "production_hook_exercised_synthetically": true,
  "real_material_runtime_runs": "not_observed",
  "judge_ready": false,
  "repair_ready": false,
  "next_engineering_slice": "numeric_extraction_design"
}
```

### Slice 123 Synthetic Track A Records (artifact-path-exercised)

```json
[
  {
    "validation_case": "clean_real_case",
    "input_kind": "synthetic_safe",
    "artifact_path_exercised": true,
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": true,
    "advisory_non_blocking": true,
    "extraction_coverage_bundle_present": true,
    "extraction_coverage_status": "ok",
    "structural_coverage_leg_covered": true,
    "numeric_fact_sheet_extraction_leg_covered": true,
    "recompute_blocker_present": false,
    "leak_blocker_present": false,
    "unified_status": "passed",
    "shippable": true,
    "safety_floor_green": true,
    "expected_case_behavior_observed": true,
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false
  },
  {
    "validation_case": "single_confident_wrong_numeric_case",
    "input_kind": "synthetic_safe",
    "artifact_path_exercised": true,
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": true,
    "advisory_non_blocking": true,
    "extraction_coverage_bundle_present": true,
    "extraction_coverage_status": "ok",
    "structural_coverage_leg_covered": true,
    "numeric_fact_sheet_extraction_leg_covered": true,
    "recompute_blocker_present": true,
    "leak_blocker_present": false,
    "unified_status": "failed",
    "shippable": false,
    "safety_floor_green": false,
    "expected_case_behavior_observed": true,
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false
  },
  {
    "validation_case": "legacy_confused_wrong_case",
    "input_kind": "synthetic_safe",
    "artifact_path_exercised": true,
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": true,
    "advisory_non_blocking": true,
    "extraction_coverage_bundle_present": true,
    "extraction_coverage_status": "ok",
    "structural_coverage_leg_covered": true,
    "numeric_fact_sheet_extraction_leg_covered": false,
    "recompute_blocker_present": false,
    "leak_blocker_present": false,
    "unified_status": "warning",
    "shippable": true,
    "safety_floor_green": false,
    "expected_case_behavior_observed": true,
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false
  }
]
```

The production-shaped `legacy_confused_wrong_case` (no concept/fact bundle, only
structural coverage) keeps the numeric leg uncovered: recompute stays missing, no
recompute blocker is raised, and `safety_floor_green=false` — the artifact does
not claim numeric correctness it cannot verify. `shippable=true` here only
reflects that no detector *failed*; it is not evidence any number was checked.

### Slice 123 Real Track B Records (private operator material, runtime not_observed)

No real-material generation was executed in this automated session, so
runtime-dependent fields are honestly `not_observed`; structurally guaranteed
invariants are recorded directly.

```json
[
  {
    "validation_case": "legacy_confused_wrong_case",
    "input_kind": "private_local_operator_material",
    "artifact_path_exercised": "not_observed",
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": "not_observed",
    "advisory_non_blocking": true,
    "extraction_coverage_bundle_present": "not_observed",
    "extraction_coverage_status": "not_observed",
    "structural_coverage_leg_covered": true,
    "numeric_fact_sheet_extraction_leg_covered": false,
    "recompute_blocker_present": "not_observed",
    "leak_blocker_present": "not_observed",
    "unified_status": "not_observed",
    "shippable": "not_observed",
    "safety_floor_green": "not_observed",
    "expected_case_behavior_observed": "not_observed",
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false,
    "warnings": ["real_material_generation_not_run_this_session"]
  },
  {
    "validation_case": "single_confident_wrong_numeric_case",
    "input_kind": "private_local_operator_material",
    "artifact_path_exercised": "not_observed",
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": "not_observed",
    "advisory_non_blocking": true,
    "extraction_coverage_bundle_present": "not_observed",
    "extraction_coverage_status": "not_observed",
    "structural_coverage_leg_covered": true,
    "numeric_fact_sheet_extraction_leg_covered": false,
    "recompute_blocker_present": "not_observed",
    "leak_blocker_present": "not_observed",
    "unified_status": "not_observed",
    "shippable": "not_observed",
    "safety_floor_green": "not_observed",
    "expected_case_behavior_observed": "not_observed",
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false,
    "warnings": ["real_material_generation_not_run_this_session"]
  },
  {
    "validation_case": "clean_real_case",
    "input_kind": "private_local_operator_material",
    "artifact_path_exercised": "not_observed",
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": "not_observed",
    "advisory_non_blocking": true,
    "extraction_coverage_bundle_present": "not_observed",
    "extraction_coverage_status": "not_observed",
    "structural_coverage_leg_covered": true,
    "numeric_fact_sheet_extraction_leg_covered": false,
    "recompute_blocker_present": "not_observed",
    "leak_blocker_present": "not_observed",
    "unified_status": "not_observed",
    "shippable": "not_observed",
    "safety_floor_green": "not_observed",
    "expected_case_behavior_observed": "not_observed",
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false,
    "warnings": ["real_material_generation_not_run_this_session"]
  }
]
```

### Slice 123 Outcome

```json
{
  "validation_id": "quality_safety_real_disaster_e2e_v1",
  "status": "ok",
  "artifact_path_validation": "ok",
  "structural_coverage_leg_status": "covered",
  "numeric_fact_sheet_extraction_leg_status": "not_covered",
  "judge_ready": false,
  "repair_ready": false,
  "next_step": "numeric_extraction_design"
}
```

## Slice 124 Numeric Extraction Contract Design (cross-reference)

Slice 124 is design-first and adds **no** operator-runtime validation: it does
not read private material, run generations, or call providers/models/cloud. It
records the safe numeric extraction contract
(`docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`) that a later slice can use
to close the Slice 123 numeric leg, plus a pure synthetic contract harness. The
numeric leg remains `not_covered`; `judge_ready`/`repair_ready` remain `false`.

```json
{
  "validation_id": "quality_safety_numeric_extraction_contract_design_v1",
  "slice": "124",
  "operator_runtime_validation": "not_applicable_design_only",
  "production_wiring": "none",
  "contract_doc_added": true,
  "synthetic_contract_harness_checks": "27_passed",
  "numeric_fact_sheet_extraction_leg_covered": false,
  "judge_ready": false,
  "repair_ready": false,
  "next_engineering_slice": "pure_numeric_extraction_record_mapper_v1"
}
```

## Slice 125 Pure Numeric Extraction Record Mapper v1 (cross-reference)

Slice 125 is a pure / unwired implementation slice and adds **no** operator-runtime
validation: it does not read private material, run generations, scan job folders,
or call providers/models/cloud. It implements the numeric extraction mapper
(`pipeline/quality_safety_numeric_extraction_mapper.py`) and a synthetic harness,
proving the contract round-trips through the existing producer + recompute verifier.
The numeric leg remains `not_covered`; `judge_ready`/`repair_ready` remain `false`
until a real artifact path proves it.

```json
{
  "validation_id": "quality_safety_numeric_extraction_record_mapper_v1",
  "slice": "125",
  "operator_runtime_validation": "not_applicable_pure_unwired",
  "production_wiring": "none",
  "mapper_status": "ready",
  "synthetic_mapper_harness_checks": "232_passed",
  "recompute_round_trip": "ok",
  "clean_real_case_synthetic": "recompute_passed",
  "single_confident_wrong_numeric_case_synthetic": "recompute_failed_blocking",
  "numeric_fact_sheet_extraction_leg_covered": false,
  "judge_ready": false,
  "repair_ready": false,
  "next_engineering_slice": "wire_numeric_extraction_mapper_into_advisory_artifact"
}
```

## Slice 126 Wire Numeric Extraction Mapper into Advisory Artifact (cross-reference)

Slice 126 wires the Slice 125 mapper into the advisory
`quality_safety_unified_qa.json` artifact path and adds **no** operator-runtime
validation of its own: it reads no private material, runs no generations, scans no
job folders arbitrarily, and calls no providers/models/cloud. It only adds a
read-only optional sidecar reader (`quality_safety_numeric_extraction_records.json`,
never created in production) and synthetic harness coverage proving numeric records
flow through the real builder + production hook. Closed-vocabulary outcome only;
the numeric leg is `partial` (synthetic records prove the artifact path, no real
extractor yet); `judge_ready`/`repair_ready` remain `false`.

```json
{
  "validation_id": "quality_safety_numeric_extraction_mapper_artifact_wiring",
  "slice": "126",
  "operator_runtime_validation": "not_applicable_synthetic_wiring",
  "advisory_non_blocking": true,
  "safe_input_sidecar": "quality_safety_numeric_extraction_records.json",
  "sidecar_created_in_production": false,
  "artifact_name_unchanged": "quality_safety_unified_qa.json",
  "numeric_bundle_separate_from_structural_coverage": true,
  "numeric_records_fabricated_from_coverage": false,
  "structural_coverage_leg_status": "covered",
  "clean_synthetic_numeric_through_artifact": "recompute_passed",
  "wrong_synthetic_numeric_through_artifact": "recompute_failed_blocking",
  "single_confident_wrong_numeric_case_through_artifact": "recompute_failed_blocking",
  "missing_numeric_records": "skipped_component_missing",
  "malformed_numeric_records": "failed_degraded_no_leak",
  "numeric_fact_sheet_extraction_leg_status": "partial",
  "artifact_path_ready": true,
  "production_numeric_extractor_exists": false,
  "judge_ready": false,
  "repair_ready": false,
  "next_engineering_slice": "safe_numeric_extractor_or_real_operator_numeric_validation"
}
```

## Slice 127 Numeric Sidecar Real-Path Operator Validation

**Purpose.** Validate the Slice 126 numeric sidecar advisory artifact path against
the three real-disaster archetypes and decide the next engineering step. This is an
operator-/harness-validation slice: it implements no production numeric extractor,
no judge, no repair, and no prompt tuning. Slice 126 already proved synthetic
numeric records flow through the producer + recompute verifier via the actual
builder and the production hook (sidecar read). Slice 127 answers whether the
sidecar path can represent the archetypes, whether a real/private operator pass was
run, and what the numeric leg status is.

**Privacy boundary.** Local operator validation may inspect private runtime
material, hand-build a temporary local sidecar JSON, run a job locally, and inspect
`quality_safety_unified_qa.json` locally. None of that private material — sidecar
JSON, raw artifact JSON, generated guides, PDFs/images/DOCX/ZIPs, source/OCR/table/
caption text, copied formulas, numeric prose snippets, evidence quotes, filenames,
basenames, paths, URLs, screenshots, provider payloads, runtime traces, or eval
outputs — is committed. Committed docs carry only closed-vocabulary outcomes.

**Track A — synthetic sidecar regression (run).** Through the actual builder
(`build_quality_safety_job_artifact_payload`) and the production hook
(`_write_quality_safety_unified_qa` reading the optional sidecar):

```json
{
  "validation_id": "quality_safety_numeric_sidecar_synthetic_regression",
  "slice": "127",
  "track": "A",
  "sidecar_missing": "skipped_numeric_extraction_missing_no_crash",
  "sidecar_malformed": "failed_numeric_extraction_degraded_no_leak",
  "sidecar_empty_list": "skipped",
  "clean_synthetic_sidecar": "recompute_passed_through_artifact",
  "wrong_synthetic_sidecar": "recompute_failed_blocking_through_artifact",
  "advisory_non_blocking": true,
  "structural_coverage_separate": true,
  "numeric_records_fabricated_from_coverage": false,
  "forbidden_canary_leak": false,
  "production_hook_reads_numeric_sidecar": "ok"
}
```

**Track B — operator real-path validation with private material.** Not performed
autonomously this slice; safe production of private sidecar records requires an
operator pass or a safe numeric extractor. Closed-vocabulary per-case records
(synthetic equivalents only via Track A):

```json
[
  {
    "validation_case": "legacy_confused_wrong_case",
    "input_kind": "not_run",
    "sidecar_kind": "synthetic_sidecar",
    "sidecar_committed": false,
    "artifact_path_exercised": "not_observed",
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": "not_observed",
    "numeric_input_artifact_name": "quality_safety_numeric_extraction_records_json",
    "numeric_extraction_status": "not_observed",
    "numeric_extraction_bundle_present": "not_observed",
    "numeric_fact_sheet_extraction_leg_covered": "partial",
    "recompute_status": "not_observed",
    "recompute_blocker_present": "not_observed",
    "leak_blocker_present": "not_observed",
    "unified_status": "not_observed",
    "shippable": "not_observed",
    "safety_floor_green": "not_observed",
    "expected_case_behavior_observed": "not_observed",
    "advisory_non_blocking": "not_observed",
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false,
    "warnings": "private_run_deferred"
  },
  {
    "validation_case": "single_confident_wrong_numeric_case",
    "input_kind": "synthetic_safe",
    "sidecar_kind": "synthetic_sidecar",
    "sidecar_committed": false,
    "artifact_path_exercised": true,
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": true,
    "numeric_input_artifact_name": "quality_safety_numeric_extraction_records_json",
    "numeric_extraction_status": "ok",
    "numeric_extraction_bundle_present": true,
    "numeric_fact_sheet_extraction_leg_covered": "partial",
    "recompute_status": "failed",
    "recompute_blocker_present": true,
    "leak_blocker_present": false,
    "unified_status": "failed",
    "shippable": false,
    "safety_floor_green": false,
    "expected_case_behavior_observed": true,
    "advisory_non_blocking": true,
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false,
    "warnings": "synthetic_equivalent_only"
  },
  {
    "validation_case": "clean_real_case",
    "input_kind": "synthetic_safe",
    "sidecar_kind": "synthetic_sidecar",
    "sidecar_committed": false,
    "artifact_path_exercised": true,
    "artifact_name": "quality_safety_unified_qa_json",
    "job_artifact_produced": true,
    "numeric_input_artifact_name": "quality_safety_numeric_extraction_records_json",
    "numeric_extraction_status": "ok",
    "numeric_extraction_bundle_present": true,
    "numeric_fact_sheet_extraction_leg_covered": "partial",
    "recompute_status": "passed",
    "recompute_blocker_present": false,
    "leak_blocker_present": false,
    "unified_status": "passed",
    "shippable": true,
    "safety_floor_green": true,
    "expected_case_behavior_observed": true,
    "advisory_non_blocking": true,
    "raw_text_committed": false,
    "raw_paths_committed": false,
    "runtime_outputs_committed": false,
    "provider_calls": false,
    "judge_calls": false,
    "repair_calls": false,
    "warnings": "synthetic_equivalent_only"
  }
]
```

**Track C — decision record.**

```json
{
  "numeric_sidecar_real_path_validation": "run",
  "slice": "127",
  "status": "partial",
  "synthetic_sidecar_artifact_path": "ok",
  "private_operator_sidecar_artifact_path": "not_run",
  "numeric_fact_sheet_extraction_leg_status": "partial",
  "artifact_path_ready": "partial",
  "artifact_path_ready_for_synthetic_numeric_records": true,
  "production_numeric_extractor_present": false,
  "judge_ready": false,
  "repair_ready": false,
  "next_step": "safe_numeric_extractor_design",
  "warnings": "private_run_deferred"
}
```

Slice 115 through Slice 125 are committed. Slice 126 is committed as `7ff1887` and
merged to `chrome-renderer-v1`. Slice 127 is committed as `35bdf8b` and merged to
`chrome-renderer-v1`.

## Slice 128 Safe Numeric Extractor Design (cross-reference)

Slice 128 is a design-only slice with **no operator-runtime validation of its own**:
it reads no private material, runs no generations, scans no job folders, and calls
no providers/models/cloud. It only adds the design doc
`docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md` plus live-doc updates,
defining the safe extractor's allowed/forbidden inputs, output contract, supported
v1 methods, and degradation policy. The next implementation slice (Slice 129) will
be the place to add synthetic harness coverage; a real/private operator numeric
validation pass remains a separate operator activity.

```json
{
  "validation_id": "quality_safety_safe_numeric_extractor_design",
  "slice": "128",
  "operator_runtime_validation": "not_applicable_design_only",
  "production_extractor_implemented": false,
  "v1_input_category": "caller_supplied_sanitized_numeric_candidates",
  "forbidden_source_parsing": true,
  "v1_methods": "weighted_gini|total_error|amount_of_say|softmax|cross_entropy|forward_pass",
  "new_methods_added": false,
  "legacy_confused_wrong_case": "partial",
  "single_confident_wrong_numeric_case": "representable",
  "clean_real_case": "representable",
  "numeric_fact_sheet_extraction_leg_status": "partial",
  "judge_ready": false,
  "repair_ready": false,
  "next_step": "pure_safe_numeric_extractor_v1",
  "raw_text_committed": false,
  "raw_paths_committed": false,
  "runtime_outputs_committed": false,
  "provider_calls": false,
  "judge_calls": false,
  "repair_calls": false
}
```

Slice 128 is NOT committed.
