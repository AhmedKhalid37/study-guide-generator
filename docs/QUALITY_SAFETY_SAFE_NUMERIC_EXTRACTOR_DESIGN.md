# Quality Safety Safe Numeric Extractor Design

> Slice 128 — design only. The repo/code is the source of truth; this doc records
> a *schema-level* design plus closed-vocabulary outcomes, never runtime values,
> never private/source/guide/OCR/table/caption text, and never copied formulas or
> numeric prose. No production extractor code is added in this slice.

## Purpose

Define a **safe extractor** that can eventually produce
`quality_safety_numeric_extraction_records.json`-compatible records for the
existing advisory artifact path (wired in Slice 126), **without** ever consuming or
emitting private/raw material. The extractor must feed the same Slice 124/125
contract that the numeric extraction mapper already normalizes and that the
recompute verifier already checks — so a wrong numeric claim raises an advisory
recompute blocker and a clean one verifies.

This slice answers *what the extractor is allowed to consume and emit* and *what
the next implementation slice must build*. It does not implement extraction, OCR,
table parsing, source-text parsing, `clean.md` parsing, a judge, repair, or prompt
tuning.

## Problem Found by Slice 127

```
synthetic_sidecar_artifact_path: ok
private_operator_sidecar_artifact_path: not_run
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic
production_numeric_extractor_present: false
judge_ready: false
repair_ready: false
next_step: safe_numeric_extractor_design
```

The transport + verification path is proven for sidecar-supplied records, but no
component **produces** records from real material. This slice designs that
producer's safe boundary.

## Extractor Boundary

### Allowed input categories

- `caller_supplied_sanitized_numeric_candidates` — already-sanitized, structured
  numeric candidates handed in by a caller (the v1 path: the extractor is pure and
  consumes only in-memory structured candidates, never raw documents).
- `synthetic_numeric_fixtures` — synthetic, closed-vocabulary fixtures for tests.
- `future_safe_structured_numeric_artifact` — a *future*, separately-designed safe
  structured numeric artifact (already sanitized at its own boundary). Not built or
  consumed in v1; named here only to mark the eventual production input.

### Forbidden input categories

- `source_documents`
- `pdf_images`
- `docx_files`
- `clean_md_as_numeric_source`
- `ocr_text`
- `page_text`
- `table_cells`
- `captions`
- `guide_text`
- `provider_payloads`
- `raw_runtime_artifacts`
- `raw_artifact_json`
- `filenames`
- `basenames`
- `paths`
- `urls`

The extractor never opens files, never scans job folders, never reads `clean.md`
as a numeric source, never parses OCR/table/source text, and never calls a
provider/model/cloud. A numeric fact is `value` + structured numeric
`computation.inputs` — never a copied formula string or a prose snippet.

## Output Contract

Output records must be compatible with the optional read-only sidecar
`quality_safety_numeric_extraction_records.json` and the Slice 124/125 contract
(verified against `pipeline/quality_safety_numeric_extraction_mapper.py`
`ALLOWED_RECORD_FIELDS`). Each record uses **sanitized tokens only**:

- `id` — safe id token (`^[a-z0-9][a-z0-9._-]{0,79}$`).
- `concept_id` — safe id token or omitted.
- `label` — safe label token (no raw prose).
- `fact_type` — exactly `numeric`.
- `value` — finite number (the claimed value).
- `unit` — safe unit token or omitted.
- `provenance` — one of `extracted_high | computed | unverified`.
- `confidence` — one of `high | medium | low | unsupported`.
- `source_ref` — safe structural ref token (`source_page_N | page_N | slide_N |
  source_ref_N`), never a filename/path/quote.
- `page_ref` — same safe structural ref vocabulary or omitted.
- `computation` — `{ method, inputs }` where `method` is a supported v1 method and
  `inputs` are numeric-only structured values (recursively sanitized; the only
  permitted string input values are the forward-pass activation tokens `linear |
  relu | sigmoid`). Demoted to a bare numeric observation when the method is
  unsupported or the inputs are malformed.
- `tolerance` — number in `(0, 1]` or omitted.
- `warnings` — closed mapper warning tokens only.

The mapper already strips the closed forbidden-field list (`raw_text`,
`source_text`, `guide_text`, `ocr_text`, `table_cells`, `captions`,
`formulas_as_text`, `evidence_quotes`, `filenames`, `basenames`, `paths`, `urls`,
`provider_payloads`, `runtime_traces`, `raw_exceptions`) and flags
`forbidden_field_stripped`. The extractor must emit records that already exclude
these fields by construction and must defer to the mapper as the final sanitizer.

## Supported v1 Methods

Exactly the existing recompute-verifier methods (verified in
`pipeline/quality_safety_recompute_verifier.py` `SUPPORTED_METHODS`):

- `weighted_gini`
- `total_error`
- `amount_of_say`
- `softmax`
- `cross_entropy`
- `forward_pass`

No method is added in this slice. A record whose `computation.method` is outside
this set is demoted to a bare numeric observation (`unsupported_method`), never
falsely recompute-verified.

## Degradation Policy

Closed-token behavior the extractor must guarantee (mirrors the mapper so the leg
never crashes, never blocks the job, and never leaks):

- `no_input` → emit no records; the numeric leg stays `skipped`
  (`component_missing` / `empty_numeric_extraction`). Not an error.
- `malformed_input` → degrade to a closed `failed` outcome
  (`malformed_numeric_extraction_input`); never raise.
- `unsupported_method` → demote that record to a bare numeric observation
  (`unsupported_method`); keep other records.
- `unsafe_field_excluded` → strip and flag (`forbidden_field_stripped` /
  `unsafe_string_sanitized`); raw content never survives.
- `invalid_numeric_value` → drop the value, flag `invalid_numeric_value`; record
  may survive as a non-numeric-fact or be dropped.
- `invalid_computation` → demote to bare observation (`malformed_computation`).
- `missing_required_field` → fill a safe default where the contract allows
  (e.g. generated `id`/`label`) or drop the record
  (`invalid_numeric_record_dropped`).
- `max_items_reached` → cap at the shared `max_items` bound and flag
  `max_items_reached` (`partial`).

## Real-Disaster Archetype Targeting

Closed-vocabulary matrix only (no private content). "Representable" means the
archetype's numeric failure/clean state can be expressed as contract records that
flow through the mapper → producer → recompute verifier → advisory artifact.

```
legacy_confused_wrong_case:
  extractor_representable: partial
  needed_input_category: caller_supplied_sanitized_numeric_candidates
  unsupported_method_blocker: false
  unsafe_source_blocker: false
  next_requirement: mapper_input_generation

single_confident_wrong_numeric_case:
  extractor_representable: true
  needed_input_category: caller_supplied_sanitized_numeric_candidates
  unsupported_method_blocker: false
  unsafe_source_blocker: false
  next_requirement: mapper_input_generation

clean_real_case:
  extractor_representable: true
  needed_input_category: caller_supplied_sanitized_numeric_candidates
  unsupported_method_blocker: false
  unsafe_source_blocker: false
  next_requirement: mapper_input_generation
```

Note: `legacy_confused_wrong_case` is `partial` because some legacy/confused claims
may rest on a computation method outside the supported v1 set; those would need a
separately-designed bounded recompute-method extension before the wrong value can
be recompute-blocked (otherwise they degrade to an unverified bare observation,
not a blocker). The single-confident-wrong and clean cases are representable today
through the supported methods (proven by the Slice 126/127 synthetic path).

## Proposed Slice 129

**Slice 129 — Pure Safe Numeric Extractor v1**

Purpose:
- pure/unwired extractor from `caller_supplied_sanitized_numeric_candidates` into
  `quality_safety_numeric_extraction_records.json`-compatible records;
- synthetic tests only;
- no OCR/table/source parsing;
- no `clean.md` reads;
- no job-folder scanning;
- no production wiring;
- no provider/model/cloud;
- no judge;
- no repair.

If implementation discovers a blocker (e.g. an archetype that needs a method
outside the supported v1 set), recommend the exact bounded blocker slice instead
(for `legacy_confused_wrong_case`: a bounded `recompute_method_extension` design
slice), rather than widening v1 scope.

## Safety Boundary

- Committed docs contain only closed-vocabulary design + outcomes.
- No real source/guide/OCR/table/caption text, copied formulas, numeric prose
  snippets, evidence quotes, filenames, basenames, paths, URLs, raw artifact JSON,
  runtime outputs, screenshots, provider payloads, or real/private sidecar JSON.
- No `quality_judge.py`, `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`.
- No `overall_10` or judge score. No provider/model/cloud call. No generation,
  prompt, request-schema, API, UI, render, export, OCR, table, visual, or Ask Guide
  change. Quality Safety stays advisory/non-blocking.
- `production_numeric_extractor_present: false`; `judge_ready: false`;
  `repair_ready: false`. Production numeric extraction coverage is **not** claimed
  complete.
```
safe_numeric_extractor_design: defined
production_extractor_implemented: false
v1_input_category: caller_supplied_sanitized_numeric_candidates
v1_methods: weighted_gini|total_error|amount_of_say|softmax|cross_entropy|forward_pass
new_methods_added: false
judge_ready: false
repair_ready: false
next_step: pure_safe_numeric_extractor_v1
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 129 Implementation Status — Pure Safe Numeric Extractor v1

Slice 129 implemented the pure/unwired extractor in
`pipeline/quality_safety_safe_numeric_extractor.py` exactly to this design boundary.
Public API: `normalize_safe_numeric_candidate`,
`extract_quality_safety_numeric_records_from_candidates`,
`build_empty_safe_numeric_extraction_records`,
`map_safe_numeric_candidates_to_sidecar_payload`. The extractor consumes only
`caller_supplied_sanitized_numeric_candidates`, resolves the flat `method`/`inputs`
alias into a `computation` block, injects synthetic `qs_safe_num_NNNN` ids when
missing, strips/flags forbidden fields, and **defers all field sanitization to the
Slice 125 mapper** (the single final sanitizer). It imports only stdlib + the
Slice 125 mapper; reads no files, scans no folders, writes no artifacts, calls no
provider/model/cloud; never raises; never mutates caller input.

Compatibility proven by synthetic tests
(`test_scripts/test_quality_safety_safe_numeric_extractor.py`, 207 checks): the
payload flows through `_coerce_numeric_records` → mapper → fact-sheet producer →
recompute verifier, and straight into the real Slice 126 artifact path
(`build_quality_safety_job_artifact_payload(numeric_extraction_records=payload)`).

```
extractor_status: ready
input_category: caller_supplied_sanitized_numeric_candidates
final_sanitizer: slice125_mapper
production_extractor_wired: false
sidecar_payload_compatible: true
single_confident_wrong_numeric_case: recompute_blocked
clean_real_case: recompute_passed
legacy_confused_wrong_case: partial
new_methods_added: false
judge_ready: false
repair_ready: false
next_step: wire_safe_numeric_extractor_into_advisory_artifact_path
no_leak_sweep: clean
docker_compose_config_run: false
```
