# Quality Safety Operator Structured Numeric Export Protocol

## Purpose

Define how an operator can safely create an operator-approved structured numeric
export compatible with `quality_safety_structured_numeric_candidates.json`.

Slice 135 selected `operator_approved_structured_export` as producer v1 (see
`docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md`). This slice
(136) writes the exact manual operator workflow, the schema the operator must
follow, the allowed/forbidden values, how private source material is handled
without committing it, the closed-vocabulary validation record that may be
committed, and the next slice that implements a pure validator for this export. It
is a docs/design/protocol slice only: no operator export validator is implemented,
no production code is wired, no producer runs.

## Boundary

This protocol is:

- `manual_or_operator_approved`
- `advisory_only`
- `closed_schema_only`
- `not_automated_extraction`
- `not_prompt_tuning`
- `not_judge`
- `not_repair`
- `not_blocking`

The operator authors records by hand. The adapter
(`pipeline/quality_safety_structured_numeric_candidate_adapter.py`) is the bridge,
the Slice 129 safe extractor is the pre-record sanitizer, and the Slice 125
numeric mapper remains the final record sanitizer. None of those parse OCR / table
/ source text or read `clean.md` as a numeric source.

## Inputs Allowed Locally

The operator may inspect private source/guide/material **locally** to identify
numeric claims, but must **never commit** any of:

- source text
- guide text
- OCR text
- page text
- table cells
- captions
- formulas_as_text
- evidence quotes
- filenames
- basenames
- paths
- URLs
- screenshots
- raw runtime artifacts
- raw artifact JSON
- provider payloads
- sidecar JSON from private cases

Only closed-vocabulary outcomes and synthetic fixtures/canaries may enter git.

## Output Artifact

The local output artifact name is:

```
quality_safety_structured_numeric_candidates.json
```

It is a **job-local, read-only** input sidecar. Production code never creates it;
the advisory path (`pipeline/quality_safety_job_artifact.py`,
`read_quality_safety_structured_numeric_candidates`) only consumes it if it already
exists under the job dir. It must follow the Slice 132/133 schema exactly as
enforced by the adapter.

Allowed top-level fields:

- `version`
- `kind`
- `status`
- `source_quality`
- `candidates`
- `summary`
- `warnings`

Allowed candidate fields (whitelist; anything else is stripped):

- `id`
- `concept_id`
- `label`
- `fact_type` (= `numeric`)
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

Required values:

- `kind=quality_safety_structured_numeric_candidates`
- `source_quality=operator_approved`
- `provenance=operator_approved` or `provenance=computed`
- `fact_type=numeric`

Supported methods (the only verifiable `computation.method` values; anything else
degrades `unsupported_method` and is never promoted to a verifier extension):

- `weighted_gini`
- `total_error`
- `amount_of_say`
- `softmax`
- `cross_entropy`
- `forward_pass`

`computation.inputs` must be numeric inputs only (finite numbers, lists, and
nested maps with safe keys; the only allowed input strings are `linear`, `relu`,
`sigmoid`). `source_ref` / `page_ref` must match the safe reference shape
(`source_page_<n>`, `page_<n>`, `slide_<n>`, `source_ref_<n>`) and carry no
filename, path, or caption.

Forbidden candidate fields (must never appear in the export):

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

## Operator Workflow

Closed step list:

1. `inspect_private_material_locally`
2. `identify_numeric_claims_with_supported_methods`
3. `encode_structured_candidate_records`
4. `run_local_validation_harness`
5. `inspect_quality_safety_unified_qa_json_locally`
6. `commit_closed_vocabulary_validation_record_only`
7. `do_not_commit_sidecar_or_runtime_outputs`

Notes (closed-vocabulary intent only, no real values):

- Step 1 stays local; nothing from the private material is copied into git.
- Step 2 only keeps numeric claims whose method is one of the supported methods;
  unsupported claims are left for a future bounded method extension, not forced.
- Step 3 uses only whitelisted candidate fields and numeric inputs.
- Step 4 runs the existing synthetic harnesses; it does not add new production code.
- Step 5 inspects the advisory `quality_safety_unified_qa.json` locally; the exact
  artifact name is unchanged and remains advisory / non-blocking.
- Steps 6–7 commit only the closed-vocabulary validation record; the sidecar and
  any runtime/eval/trace output stay out of git.

## Validation Record Template

Closed-vocabulary template that may be committed later (tokens only — never real
numeric values, source text, filenames, paths, or evidence quotes):

```
validation_id: operator_structured_numeric_export_validation
input_kind: private_local_operator_material | synthetic_safe | not_run
operator_export_created: true | false | not_observed
operator_export_committed: false
artifact_name: quality_safety_structured_numeric_candidates_json
artifact_path_exercised: true | false | not_observed
structured_adapter_status: ok | warning | skipped | partial | failed | not_observed
safe_numeric_extractor_status: ok | warning | skipped | partial | failed | not_observed
numeric_extraction_status: ok | warning | skipped | partial | failed | not_observed
recompute_status: passed | failed | skipped | partial | unknown | not_observed
recompute_blocker_present: true | false | not_observed
shippable: true | false | not_observed
safety_floor_green: true | false | not_observed
raw_text_committed: false
raw_paths_committed: false
runtime_outputs_committed: false
provider_calls: false
judge_calls: false
repair_calls: false
warnings: closed tokens only
```

`operator_export_committed` is fixed `false`: the sidecar itself is never
committed. A real run can only be trusted once the pure validator (Slice 137)
exists, so until then any real-run record is treated as `not_observed`.

## Real-Disaster Case Expectations

Closed-vocabulary only (no real text, numbers, filenames, or quotes):

```
single_confident_wrong_numeric_case:
  operator_export_representable: true
  expected_recompute: failed_blocking
  supported_method_required: true
  status: ready_for_operator_validation

clean_real_case:
  operator_export_representable: true
  expected_recompute: passed
  supported_method_required: true
  status: ready_for_operator_validation

legacy_confused_wrong_case:
  operator_export_representable: partial
  expected_recompute: partial
  supported_method_required: false|unknown
  status: needs_method_extension_or_operator_note
```

These mirror the synthetic outcomes already proven by Slice 134's advisory wiring:
a confident-wrong supported-method candidate produces a recompute blocker, a clean
supported-method candidate passes recompute, and an unsupported-method (legacy
confused) candidate is counted but not falsely blocked.

## Decision

Closed vocabulary:

```
operator_protocol_status: ready
operator_export_validator_needed: true
production_numeric_extractor_present: structured_artifact_sidecar_only
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_structured_candidates
judge_ready: false
repair_ready: false
next_step: pure_operator_export_validator
```

The protocol is `ready` as a written workflow, but `operator_export_validator_needed=true`:
no real operator validation record should be trusted until a pure validator exists.
`judge_ready` and `repair_ready` stay `false`; the protocol does not add a judge,
repair, blocking gate, prompt tuning, or measured quality lift, and does not claim
complete production numeric extraction coverage.

## Proposed Next Slice

Slice 137 — Pure Operator Structured Numeric Export Validator v1

Purpose:

- implement a pure/unwired validator for operator-approved
  `quality_safety_structured_numeric_candidates`-like dicts;
- synthetic tests only;
- no production wiring;
- no private sidecar commit;
- no OCR / table / source parsing;
- no judge / repair.

## Slice 137 Validator Status

Slice 137 implemented the pure/unwired validator promised by this protocol:
`pipeline/quality_safety_operator_structured_numeric_export_validator.py`. It gates
an operator-authored (or synthetic) `quality_safety_structured_numeric_candidates`-
like dict against this protocol and re-emits a sanitized, forbidden-field-free
`structured_numeric_payload` that flows through the existing adapter → safe
extractor → numeric mapper → fact-sheet → recompute path and the Slice 134 advisory
artifact path. It validated synthetic fixtures only; it validated no real/private
sidecar and is not wired into production.

```
validator_status: ready
validator_module: pipeline/quality_safety_operator_structured_numeric_export_validator.py
validator_wired_into_production: false
private_sidecar_validated: false
forbidden_fields_detected_counted_stripped: true
unsupported_method_handling: degraded_not_extended
downstream_chain_compatible: true
advisory_artifact_path_compatible: true
single_confident_wrong_numeric_case: validated_ok_then_recompute_blocker
clean_real_case: validated_ok_then_recompute_passed
legacy_confused_wrong_case: validated_warning_partial_unverified
quality_safety_blocking: false
judge_ready: false
repair_ready: false
next_step: operator_structured_numeric_export_validation_harness
```

## Slice 138 Validation Harness + Local/Private Handling

Slice 138 added the operator validation harness
`test_scripts/validate_quality_safety_operator_structured_numeric_export.py`. It
runs the Slice 137 validator end-to-end through the full chain (validator →
adapter → safe extractor → numeric mapper/fact-sheet/recompute → advisory artifact
builder) and prints a **closed-vocabulary summary only**.

- **Default synthetic mode** runs five synthetic cases and exits non-zero if any
  expectation fails: `clean_operator_export_case` (recompute passed),
  `wrong_operator_export_case` (recompute failed_blocking),
  `unsupported_operator_export_case` (partial/unverified, no false blocker),
  `malformed_operator_export_case` (failed/warning, no leak),
  `forbidden_field_operator_export_case` (forbidden fields stripped, no canary
  leak).
- **Optional local/private mode** (`--input <path>`) validates exactly one local
  JSON file the operator authored. It reads only that file, **never prints the
  path, raw values, or raw records**, prints a closed-vocabulary status only, and
  **writes nothing**. A read/parse failure degrades to a closed `input_read_failed`
  token with no path or exception text. The local path and any private JSON / raw
  value must never be committed — only the closed-vocabulary summary is safe.

```
harness_status: ok
harness_module: test_scripts/validate_quality_safety_operator_structured_numeric_export.py
synthetic_mode: implemented
local_private_mode: implemented
local_private_mode_run: not_run
operator_export_committed: false
private_sidecar_validated: false
writes_output_files: false
operator_numeric_export_waiver: approved_for_safety_floor_finalization_synthetic_only
numeric_infrastructure_frozen: true
judge_ready: false
repair_ready: false
next_step: deterministic_safety_floor_final_gate
```

## Slice 139 Final Gate Relationship

Slice 139's deterministic safety floor final gate exercised the operator-validator
output path as one of its numeric prerequisites (`numeric_path_status=ok`) and
confirmed the operator export harness passes (`operator_export_harness_status=ok`).
The protocol is **unchanged**; the numeric infrastructure stays frozen.

```
final_gate_status: ready_for_cleanup_freeze
protocol_changed: false
operator_export_harness_status: ok
numeric_infrastructure_frozen: true
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: quality_safety_surface_cleanup_freeze
```
