# Quality Safety Structured Numeric Candidate Producer Design

## Purpose

Design the first acceptable producer of `quality_safety_structured_numeric_candidates.json`.

Slices 132–134 defined the future artifact, built the pure adapter, and wired the
adapter into the advisory `quality_safety_unified_qa.json` path through an optional
read-only sidecar. No code produces that sidecar. This slice (135) decides which
producer is safest and most realistic to build next, and whether the project may
proceed on sidecar-only / operator-waived numeric coverage. It is a design and
discovery slice only: no producer is implemented and no production code changes.

## Problem Found by Slices 131–134

```
existing_production_safe_source_present: false
structured_adapter_artifact_path_status: ok
safe_numeric_extractor_artifact_path_status: ok
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_structured_candidates
production_numeric_extractor_present: structured_artifact_sidecar_only
judge_ready: false
repair_ready: false
```

Slice 131 discovery: no already-present production artifact carries numeric method
inputs; the only structured artifacts that do (the explicit-records and
safe-candidate sidecars) are themselves manually supplied inputs, not producers.
Slice 134 proved the adapter -> safe extractor -> mapper -> fact-sheet -> recompute
-> advisory artifact path works for synthetic structured candidates: clean
candidates pass recompute, wrong supported-method candidates produce recompute
blockers, and unsupported-method candidates are counted but not falsely blocked.
The single missing piece is a safe producer for the structured sidecar.

## Producer Options

### option: operator_approved_structured_export

```
option: operator_approved_structured_export
status: viable
privacy_risk: low
automation_level: semi_automatic
can_emit_supported_methods: true
can_support_single_confident_wrong_numeric_case: true
can_support_clean_real_case: true
can_support_legacy_confused_wrong_case: partial
needs_method_extension: false
decision: select
reason: only_path_with_no_raw_text_risk_and_no_provider_calls; operator_authors_closed_schema_records; adapter_already_whitelists_operator_approved_source_quality_and_provenance; legacy_confused_partial_until_method_extension
```

### option: already_sanitized_structural_artifact_adapter

```
option: already_sanitized_structural_artifact_adapter
status: rejected
privacy_risk: low
automation_level: automatic
can_emit_supported_methods: false
can_support_single_confident_wrong_numeric_case: false
can_support_clean_real_case: false
can_support_legacy_confused_wrong_case: false
needs_method_extension: unknown
decision: reject
reason: slice131_discovery_found_no_structural_artifact_carries_numeric_method_inputs; structural_coverage_must_never_be_converted_into_candidates_or_numeric_facts
```

### option: model_generated_structured_numeric_export

```
option: model_generated_structured_numeric_export
status: partial
privacy_risk: high
automation_level: semi_automatic
can_emit_supported_methods: partial
can_support_single_confident_wrong_numeric_case: partial
can_support_clean_real_case: partial
can_support_legacy_confused_wrong_case: partial
needs_method_extension: unknown
decision: defer
reason: would_require_provider_or_cloud_calls_and_reading_private_source_or_guide_text; out_of_scope_under_no_provider_rules; revisit_only_with_separately_designed_local_only_slice
```

### option: sidecar_only_operator_waiver

```
option: sidecar_only_operator_waiver
status: partial
privacy_risk: low
automation_level: manual
can_emit_supported_methods: partial
can_support_single_confident_wrong_numeric_case: partial
can_support_clean_real_case: partial
can_support_legacy_confused_wrong_case: partial
needs_method_extension: false
decision: defer
reason: acceptable_short_term_stance_but_unprotocolled; operator_approved_structured_export_formalizes_it_with_a_closed_schema_and_a_real_waiver; no_judge_calibration_until_an_explicit_operator_waiver_is_recorded
```

No real text, examples, formulas, filenames, paths, or private material is
included in any option above. All outcomes are closed tokens.

## Recommended Producer v1

Selected: **`operator_approved_structured_export`**.

Meaning:

- the operator prepares structured numeric candidate records using only the
  approved closed schema (`kind=quality_safety_structured_numeric_candidates`,
  whitelisted candidate fields, supported methods, numeric inputs only);
- committed docs record only closed outcomes — never the operator's real numeric
  values, source text, filenames, paths, formulas, or evidence quotes;
- no raw private material is committed to git;
- no production OCR / table / source / `clean.md` parsing is added;
- this is an explicit operator waiver / manual gate, not automated production
  numeric extraction; the project does not claim complete production numeric
  extraction coverage.

This is preferred over the alternatives because it is the only option with no
raw-text risk, no provider/cloud calls, and a producer the adapter already
supports (`source_quality=operator_approved`, `provenance=operator_approved` are
already whitelisted). `already_sanitized_structural_artifact_adapter` is rejected
by the Slice 131 discovery; `model_generated_structured_numeric_export` is
deferred because it conflicts with the no-provider rules and raw-text boundary;
`sidecar_only_operator_waiver` is the same stance without a protocol, so it is
folded into the selected option as a formalized export protocol.

Alternatives considered and not selected:

- `future_structured_numeric_extractor_design`
- `bounded_recompute_method_extension`
- `stop_for_review`

## Required Guardrails

- closed schema only
- no raw text fields
- no filenames / paths / URLs
- no provider payloads
- no formulas_as_text
- only supported methods (`weighted_gini`, `total_error`, `amount_of_say`,
  `softmax`, `cross_entropy`, `forward_pass`); unsupported methods degrade
  unverified and are never promoted to verifier extensions
- adapter is the bridge; the Slice 129 safe extractor is the pre-record
  sanitizer; the Slice 125 numeric mapper remains the final record sanitizer
- advisory / non-blocking; Quality Safety never becomes a blocking gate here
- no automatic shippable upgrade from candidate presence — recompute evidence,
  not candidate existence, drives any outcome
- structural `extraction_coverage_*` is never converted into structured / safe /
  numeric candidates or numeric facts
- all real / private operator validation is summarized as closed tokens only;
  no real numeric values, source text, or evidence quotes enter git
- no judge, `overall_10`, repair, `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`

## Decision Record

```
recommended_producer_v1: operator_approved_structured_export
production_numeric_extractor_present: structured_artifact_sidecar_only
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_structured_candidates
judge_ready: false
repair_ready: false
next_step: operator_export_protocol
```

Conservative stance:

- No explicit operator waiver has been recorded yet, so `judge_ready=false` and
  `repair_ready=false` remain.
- Because `operator_approved_structured_export` is selected, the next slice
  designs the operator export protocol — not a judge, not repair, not prompt
  tuning, not measured quality lift.
- `production_numeric_extractor_present` stays `structured_artifact_sidecar_only`
  until an operator export protocol exists and an operator waiver is explicitly
  approved; only then does it become `operator_approved_structured_export` and
  `numeric_fact_sheet_extraction_leg_status` move toward
  `covered_for_operator_export`.

## Proposed Next Slice

Slice 136 — Operator Structured Numeric Export Protocol

Purpose:

- define the exact operator workflow for producing
  `quality_safety_structured_numeric_candidates.json`-compatible closed-schema
  records (field-by-field, supported methods, numeric inputs only);
- define the explicit operator-waiver wording and where the closed outcome is
  recorded;
- no production code; no producer wiring;
- no raw private content in git;
- no OCR / table / source / `clean.md` parsing;
- no judge / repair / prompt tuning yet.

If a different decision is later made, the next slice should instead be one of
`pure_operator_export_validator`, `bounded_recompute_method_extension`, or
`stop_for_review`, matched to that decision.

## Slice 136 Protocol Status

Slice 136 wrote the operator export protocol for the selected producer (see
`docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md`). It is
docs/design/protocol-only — no operator export validator is implemented and no
producer is wired.

```
operator_protocol_status: ready
operator_export_validator_needed: true
recommended_producer_v1: operator_approved_structured_export
production_numeric_extractor_present: structured_artifact_sidecar_only
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_structured_candidates
judge_ready: false
repair_ready: false
next_step: pure_operator_export_validator
```

The protocol fixes the operator workflow, the closed schema, the allowed/forbidden
values, how private material stays out of git, and the closed-vocabulary validation
record. A real operator validation record is treated as `not_observed` until the
pure validator (Slice 137) exists.

## Slice 137 Validator Status

Slice 137 implemented the pure/unwired operator export validator
(`pipeline/quality_safety_operator_structured_numeric_export_validator.py`) for the
selected `operator_approved_structured_export` producer v1. It gates the operator
export against the Slice 136 protocol and re-emits a sanitized, forbidden-field-free
`quality_safety_structured_numeric_candidates`-shaped payload for the existing
adapter/extractor/mapper/recompute path. Synthetic fixtures only; no production
wiring; no private sidecar validated.

```
validator_status: ready
validator_wired_into_production: false
unsupported_method_handling: degraded_not_extended
judge_ready: false
repair_ready: false
next_step: operator_structured_numeric_export_validation_harness
```

## Slice 138 Harness + Producer Freeze

Slice 138 added the operator validation harness
(`test_scripts/validate_quality_safety_operator_structured_numeric_export.py`),
run synthetic-only, which closes the producer infrastructure phase. The selected
`operator_approved_structured_export` producer v1 stays the hand-authored path;
**no future automated producer is implemented**. The numeric infrastructure is now
frozen unless a real blocker appears.

```
harness_status: ok
producer_v1: operator_approved_structured_export
future_automated_producer: not_implemented
numeric_infrastructure_frozen: true
operator_numeric_export_waiver: approved_for_safety_floor_finalization_synthetic_only
private_operator_run: not_run
judge_ready: false
repair_ready: false
next_step: deterministic_safety_floor_final_gate
```

## Slice 139 Final Gate Relationship

Slice 139's deterministic safety floor final gate confirmed the structured-candidate
path still works (`numeric_path_status=ok`) and that structural coverage never
fabricates numeric records (`structural_coverage_status=ok`). The producer design is
**unchanged**: producer v1 stays the hand-authored `operator_approved_structured_export`
path, no future automated producer is implemented, and the numeric infrastructure
stays frozen.

```
final_gate_status: ready_for_cleanup_freeze
producer_design_changed: false
future_automated_producer: not_implemented
numeric_infrastructure_frozen: true
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: quality_safety_surface_cleanup_freeze
```
