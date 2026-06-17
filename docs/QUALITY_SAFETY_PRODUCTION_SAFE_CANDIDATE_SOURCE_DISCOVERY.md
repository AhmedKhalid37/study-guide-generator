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

## Slice 132 Result

Slice 132 selected the future artifact name:

```yaml
future_artifact: quality_safety_structured_numeric_candidates.json
adapter_implemented: false
producer_implemented: false
production_wiring_changed: false
judge_ready: false
repair_ready: false
next_step: pure_structured_numeric_candidate_artifact_adapter_v1
```

`quality_safety_structured_numeric_candidates.json` is the future producer-owned
artifact. It is distinct from the current read-only compatibility sidecar
`quality_safety_safe_numeric_candidates.json` and the post-candidate records
sidecar `quality_safety_numeric_extraction_records.json`.

Allowed future producers:

- `future_structured_numeric_extractor`
- `operator_approved_structured_export`
- `synthetic_fixture_generator`

Forbidden producers:

- `raw_ocr_parser_direct_to_numeric`
- `raw_table_cell_parser_direct_to_numeric`
- `clean_md_parser`
- `provider_payload_parser`
- `source_document_reader`

Selected next step: Slice 133 - Pure Structured Numeric Candidate Artifact
Adapter v1. It should be pure, unwired, synthetic-tested, and should bridge
`quality_safety_structured_numeric_candidates.json`-like dicts into
`quality_safety_safe_numeric_candidates.json`-compatible payloads without
production wiring.

## Slice 133 Adapter Readiness

Slice 133 added a pure adapter but still did not add a production producer or
production wiring.

```yaml
future_artifact: quality_safety_structured_numeric_candidates.json
adapter_status: ready
adapter_output_kind: quality_safety_safe_numeric_candidates
adapter_output_wrapper_key: candidates
production_safe_source_present: false
producer_implemented: false
production_wiring_changed: false
structured_artifact_read_from_jobs: false
sidecar_written_in_production: false
single_confident_wrong_numeric_case: failed_blocking
clean_real_case: passed
legacy_confused_wrong_case: partial
judge_ready: false
repair_ready: false
next_step: wire_structured_numeric_candidate_adapter_into_advisory_artifact_path
```

The adapter proves that the future artifact shape can bridge into the existing
safe-candidate path. It does not change the Slice 131 discovery conclusion that no
current production source emits structured numeric candidates.

## Slice 134 Structured Candidate Artifact Path Status

Slice 134 adds advisory artifact-path wiring for the future structured sidecar,
but still does not add a production producer.

```yaml
future_artifact: quality_safety_structured_numeric_candidates.json
structured_artifact_read_from_jobs: true
structured_artifact_written_in_production: false
structured_numeric_candidate_adapter_artifact_path_status: ok
safe_numeric_extractor_artifact_path_status: ok
precedence: explicit_records_over_safe_candidates_over_structured_candidates
production_safe_source_present: false
production_numeric_extractor_present: structured_artifact_sidecar_only
structural_coverage_into_structured_candidates: false
single_confident_wrong_numeric_case: failed_blocking
clean_real_case: passed
legacy_confused_wrong_case: partial
judge_ready: false
repair_ready: false
next_step: future_structured_numeric_candidate_producer_design_or_operator_waiver
```

The discovery conclusion remains unchanged: the repo now has an advisory bridge
for a future structured sidecar, not an existing production source that emits it.

## Slice 135 Producer Decision

Slice 135 selected the producer for the future structured sidecar (full matrix in
`docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`).

```yaml
recommended_producer_v1: operator_approved_structured_export
already_sanitized_structural_artifact_adapter: reject
model_generated_structured_numeric_export: defer
sidecar_only_operator_waiver: defer
production_safe_source_present: false
production_numeric_extractor_present: structured_artifact_sidecar_only
judge_ready: false
repair_ready: false
next_step: operator_export_protocol
```

This confirms the Slice 131 inventory conclusion: no already-sanitized structural
artifact carries numeric method inputs, so an operator-authored closed-schema
export — not an automated structural adapter — is the chosen safe producer.
