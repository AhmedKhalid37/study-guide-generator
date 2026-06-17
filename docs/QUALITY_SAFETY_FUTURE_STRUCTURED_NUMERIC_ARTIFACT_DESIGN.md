# Quality Safety Future Structured Numeric Artifact Design

## Purpose

Design a future structured numeric artifact that can safely provide production
candidate inputs for the existing safe numeric extractor and advisory artifact
path.

## Problem Found by Slice 131

```yaml
existing_production_safe_source_present: false
numeric_capable_paths: sidecar_only
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_candidates
production_numeric_extractor_present: sidecar_candidate_only
judge_ready: false
repair_ready: false
next_step: future_structured_numeric_artifact_design
```

## Proposed Artifact

Proposed artifact name:

```yaml
artifact_name: quality_safety_structured_numeric_candidates.json
```

`quality_safety_structured_numeric_candidates.json` is the future producer-owned
structured candidate artifact. It is intended to be emitted by a bounded future
producer or operator-approved export, then adapted into the existing safe numeric
candidate shape.

This artifact is different from:

- `quality_safety_safe_numeric_candidates.json`: current internal read-only
  sidecar consumed by the Slice 130 artifact path.
- `quality_safety_numeric_extraction_records.json`: explicit post-candidate
  records sidecar consumed by the numeric extraction path.

The future artifact is producer-owned and source-provenance-aware. The current
safe-candidate sidecar is an internal compatibility input. The records sidecar is
already after candidate normalization and therefore is not the right place to
record future producer status, warnings, or source-quality boundary decisions.

## Producer Boundary

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

## Artifact Boundary

Allowed top-level fields:

- `version`
- `kind`
- `status`
- `source_quality`
- `candidates`
- `summary`
- `warnings`

Allowed candidate fields:

- `id`
- `concept_id`
- `label`
- `fact_type=numeric`
- `value`
- `unit`
- `provenance`
- `confidence`
- `source_ref`
- `page_ref`
- `computation.method`
- `computation.inputs`
- `tolerance`
- `warnings`

Forbidden candidate fields:

- `raw_text`
- `source_text`
- `guide_text`
- `ocr_text`
- `page_text`
- `table_cells`
- `captions`
- `formulas_as_text`
- `evidence_quotes`
- `filenames`
- `basenames`
- `paths`
- `urls`
- `provider_payloads`
- `runtime_traces`
- `raw_exceptions`
- `raw_artifact_json`

## Supported v1 Methods

Supported v1 methods are unchanged:

- `weighted_gini`
- `total_error`
- `amount_of_say`
- `softmax`
- `cross_entropy`
- `forward_pass`

No method is added in this slice.

## Flow

Intended future flow:

```text
future producer
-> quality_safety_structured_numeric_candidates.json
-> pure adapter/bridge
-> quality_safety_safe_numeric_candidates.json-compatible payload
-> safe numeric extractor
-> quality_safety_numeric_extraction_records shape
-> numeric mapper
-> fact-sheet producer
-> recompute verifier
-> advisory quality_safety_unified_qa.json
```

Slice 132 does not implement this flow. The existing Slice 130 path remains
sidecar-only until a bridge and a producer are built. Structural coverage,
visual-selection plans, table policy/count artifacts, and the advisory QA output
remain non-candidate sources.

## Degradation Policy

Closed degradation tokens:

- `component_missing`
- `malformed_input`
- `unsupported_method`
- `unsafe_field_excluded`
- `invalid_numeric_value`
- `invalid_computation`
- `missing_required_field`
- `max_items_reached`
- `producer_not_available`

## Real-Disaster Target Matrix

```yaml
single_confident_wrong_numeric_case:
  future_artifact_representable: true
  supported_method_required: true
  expected_recompute_outcome: failed_blocking
  missing_piece: future_producer

clean_real_case:
  future_artifact_representable: true
  supported_method_required: true
  expected_recompute_outcome: passed
  missing_piece: future_producer

legacy_confused_wrong_case:
  future_artifact_representable: partial
  supported_method_required: true
  expected_recompute_outcome: partial
  missing_piece: method_extension
```

## Proposed Next Slice

Slice 133 - Pure Structured Numeric Candidate Artifact Adapter v1

Purpose:

- pure/unwired adapter from
  `quality_safety_structured_numeric_candidates.json`-like dicts into
  `quality_safety_safe_numeric_candidates.json`-compatible candidate payloads;
- synthetic tests only;
- no production wiring;
- no OCR/table/source parsing;
- no provider/model/cloud;
- no judge;
- no repair.

## Slice 133 Implementation Status

Slice 133 implemented the pure adapter/bridge only:

```yaml
adapter_module: pipeline/quality_safety_structured_numeric_candidate_adapter.py
adapter_status: ready
adapter_implemented: true
producer_implemented: false
production_wiring_changed: false
output_kind: quality_safety_safe_numeric_candidates
output_wrapper_key: candidates
final_sanitizer: slice129_extractor_then_slice125_mapper
supported_methods:
  - weighted_gini
  - total_error
  - amount_of_say
  - softmax
  - cross_entropy
  - forward_pass
unsupported_methods: degrade_unverified
single_confident_wrong_numeric_case: failed_blocking
clean_real_case: passed
legacy_confused_wrong_case: partial
advisory_artifact_path_compatibility: tested_synthetic_wrapper_only
judge_ready: false
repair_ready: false
next_step: wire_structured_numeric_candidate_adapter_into_advisory_artifact_path
```

The adapter accepts only `kind=quality_safety_structured_numeric_candidates`,
strips unknown top-level fields and forbidden candidate fields, and emits a
safe-candidate-compatible payload. It does not read the future artifact from disk
and does not write `quality_safety_safe_numeric_candidates.json`.

## Slice 134 Advisory Artifact Wiring Status

Slice 134 wires the adapter into the advisory artifact path through the optional
read-only sidecar `quality_safety_structured_numeric_candidates.json`.

```yaml
structured_numeric_candidate_adapter_artifact_path_status: ok
structured_numeric_candidates_input_artifact: quality_safety_structured_numeric_candidates.json
artifact_path_ready: true_for_synthetic_structured_candidates
precedence: explicit_records_over_safe_candidates_over_structured_candidates
summary_only_artifact_fields: true
full_adapter_payload_top_level: false
producer_implemented: false
production_numeric_extractor_present: structured_artifact_sidecar_only
structured_artifact_written_in_production: false
ocr_table_source_parsing_added: false
clean_md_numeric_read_added: false
single_confident_wrong_numeric_case: failed_blocking
clean_real_case: passed
legacy_confused_wrong_case: partial
no_leak_boundary: adapter_then_safe_extractor_then_mapper
judge_ready: false
repair_ready: false
next_step: future_structured_numeric_candidate_producer_design_or_operator_waiver
```

This makes the future artifact path testable with synthetic structured candidates,
but it does not implement a producer and does not claim complete production
numeric extraction coverage.

## Slice 135 Producer Design Outcome

Slice 135 chose the first acceptable producer for this artifact. See
`docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md` for the full
options matrix. Design/discovery only — no producer implemented.

```yaml
recommended_producer_v1: operator_approved_structured_export
rejected: already_sanitized_structural_artifact_adapter
deferred: [model_generated_structured_numeric_export, sidecar_only_operator_waiver]
producer_implemented: false
production_numeric_extractor_present: structured_artifact_sidecar_only
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_structured_candidates
judge_ready: false
repair_ready: false
next_step: operator_export_protocol
```

The selected producer is operator-authored and closed-schema; it commits no raw
private material and adds no OCR/table/source/`clean.md` parsing or provider calls.
The adapter already whitelists `source_quality=operator_approved` and
`provenance=operator_approved`, so no artifact-schema change is needed.

## Slice 136 Operator Export Protocol Relationship

Slice 136 wrote the operator workflow that produces this artifact (see
`docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md`). The artifact
shape here is unchanged; the protocol only constrains how an operator authors it by
hand. The `quality_safety_structured_numeric_candidates.json` sidecar remains a
job-local, read-only input that production never creates, and is never committed.

```yaml
operator_protocol_status: ready
operator_export_validator_needed: true
artifact_schema_changed: false
sidecar_committed: false
judge_ready: false
repair_ready: false
next_step: pure_operator_export_validator
```

## Slice 137 Validator Relationship

Slice 137 added a pure validator
(`pipeline/quality_safety_operator_structured_numeric_export_validator.py`) that
sits *in front of* this artifact's adapter: it gates an operator-authored export
against the Slice 136 protocol and re-emits a sanitized
`quality_safety_structured_numeric_candidates`-shaped payload. The artifact schema
is unchanged; the sidecar remains a job-local, read-only input production never
creates and never commits. The validator is not wired into production.

```yaml
validator_status: ready
artifact_schema_changed: false
sidecar_committed: false
validator_wired_into_production: false
judge_ready: false
repair_ready: false
next_step: operator_structured_numeric_export_validation_harness
```

## Slice 138 Harness Relationship

Slice 138 added the operator validation harness
(`test_scripts/validate_quality_safety_operator_structured_numeric_export.py`),
run synthetic-only. The artifact schema is **unchanged**; the sidecar remains a
job-local, read-only input production never creates and never commits. The numeric
infrastructure is now frozen — no further schema/bridge layers before the judge
path.

```yaml
harness_status: ok
artifact_schema_changed: false
sidecar_committed: false
numeric_infrastructure_frozen: true
operator_numeric_export_waiver: approved_for_safety_floor_finalization_synthetic_only
private_operator_run: not_run
judge_ready: false
repair_ready: false
next_step: deterministic_safety_floor_final_gate
```
