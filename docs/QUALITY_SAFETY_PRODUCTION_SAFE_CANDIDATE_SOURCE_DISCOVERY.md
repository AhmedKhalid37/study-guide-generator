# Quality Safety Production Safe Candidate Source Discovery

## Purpose

Determine whether existing already-sanitized structured artifacts can feed safe
numeric candidates, or whether an operator waiver / future extractor design is
required.

## Problem Found by Slice 130

```
safe_numeric_extractor_artifact_path_status: ok
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_candidates
production_numeric_extractor_present: sidecar_candidate_only
judge_ready: false
repair_ready: false
next_step: production_safe_candidate_source_or_operator_waiver
```

## Candidate Source Inventory

```yaml
- source_name: explicit_numeric_records_sidecar
  present_in_code: true
  already_sanitized: true
  contains_numeric_method_inputs: true
  contains_raw_text_risk: false
  can_feed_safe_numeric_candidates: false
  supported_cases:
    - single_confident_wrong_numeric_case
    - clean_real_case
  missing_piece: none
  decision: reject

- source_name: safe_numeric_candidates_sidecar
  present_in_code: true
  already_sanitized: true
  contains_numeric_method_inputs: true
  contains_raw_text_risk: false
  can_feed_safe_numeric_candidates: true
  supported_cases:
    - single_confident_wrong_numeric_case
    - clean_real_case
  missing_piece: source_signal
  decision: defer

- source_name: source_coverage_report
  present_in_code: true
  already_sanitized: true
  contains_numeric_method_inputs: false
  contains_raw_text_risk: false
  can_feed_safe_numeric_candidates: false
  supported_cases: []
  missing_piece: method_inputs
  decision: reject

- source_name: extraction_metadata
  present_in_code: true
  already_sanitized: false
  contains_numeric_method_inputs: false
  contains_raw_text_risk: true
  can_feed_safe_numeric_candidates: false
  supported_cases: []
  missing_piece: method_inputs
  decision: reject

- source_name: visual_inclusion_plan
  present_in_code: true
  already_sanitized: true
  contains_numeric_method_inputs: false
  contains_raw_text_risk: false
  can_feed_safe_numeric_candidates: false
  supported_cases: []
  missing_piece: method_inputs
  decision: reject

- source_name: table_candidates_manifest
  present_in_code: true
  already_sanitized: true
  contains_numeric_method_inputs: false
  contains_raw_text_risk: false
  can_feed_safe_numeric_candidates: false
  supported_cases: []
  missing_piece: numeric_values
  decision: defer

- source_name: table_reconstruction_policy
  present_in_code: true
  already_sanitized: true
  contains_numeric_method_inputs: false
  contains_raw_text_risk: false
  can_feed_safe_numeric_candidates: false
  supported_cases: []
  missing_piece: numeric_values
  decision: defer

- source_name: quality_safety_unified_qa
  present_in_code: true
  already_sanitized: true
  contains_numeric_method_inputs: false
  contains_raw_text_risk: false
  can_feed_safe_numeric_candidates: false
  supported_cases: []
  missing_piece: method_inputs
  decision: reject

- source_name: future_structured_numeric_artifact
  present_in_code: false
  already_sanitized: unknown
  contains_numeric_method_inputs: unknown
  contains_raw_text_risk: unknown
  can_feed_safe_numeric_candidates: unknown
  supported_cases:
    - single_confident_wrong_numeric_case
    - clean_real_case
    - legacy_confused_wrong_case
  missing_piece: unknown
  decision: inspect_later

- source_name: operator_manual_sidecar
  present_in_code: false
  already_sanitized: unknown
  contains_numeric_method_inputs: unknown
  contains_raw_text_risk: unknown
  can_feed_safe_numeric_candidates: unknown
  supported_cases:
    - single_confident_wrong_numeric_case
    - clean_real_case
  missing_piece: operator_waiver
  decision: inspect_later
```

## Decision

```
next_step: future_structured_numeric_artifact_design
existing_production_safe_source_present: false
sidecar_only_source_present: true
operator_waiver_recorded: false
judge_ready: false
repair_ready: false
```

Existing already-produced structured artifacts do not safely contain the required
numeric candidate shape: a finite numeric value plus structured
`computation.method` and numeric `computation.inputs`. `source_coverage_report`
and `extraction_metadata` are structural coverage surfaces; they cannot be
converted into numeric candidates. `visual_inclusion_plan` is a visual-selection
surface. `table_candidates_manifest` and `table_reconstruction_policy` carry
table structure/count/policy tokens, including count signals and preservation
intent, but not cell values or recomputable method inputs. `quality_safety_unified_qa`
is an output artifact and must not become a recursive candidate source.

`single_confident_wrong_numeric_case` and `clean_real_case` are representable only
through the existing explicit sidecar / safe-candidate sidecar path or a future
structured numeric artifact. `legacy_confused_wrong_case` remains partial unless
the future source emits a supported method; unsupported real methods require a
bounded recompute-method extension.

## Proposed Next Slice

Slice 132 - Future Structured Numeric Artifact Design

Purpose: define a future structured artifact that an extractor or operator can
populate with safe method-input records. No production extraction, no OCR/table
parsing, no judge.
