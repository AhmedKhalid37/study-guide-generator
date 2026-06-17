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
