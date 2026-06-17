# Quality Safety Numeric Extraction Contract

> Slice 124 — design-first, bounded. No production wiring. Closed-vocabulary
> only. See `CLAUDE.md` for the durable rules and `QUALITY_SAFETY_E2E_VALIDATION.md`
> / `QUALITY_SAFETY_OPERATOR_VALIDATION.md` for the validation records.

## Purpose

Define the **safe structured numeric extraction contract** needed to feed the
existing pure fact-sheet producer (`pipeline/quality_safety_fact_sheet_producer.py`)
and recompute verifier (`pipeline/quality_safety_recompute_verifier.py`) so that
the numeric fact-sheet extraction leg can be covered end-to-end in a later slice.

This document is the **schema/policy contract only**. It does *not* implement OCR
parsing, table parsing, source/document reading, `clean.md` reading, providers,
models, cloud, a judge, or repair. It introduces no production wiring.

## Problem Found by Slice 123

Slice 123 validated the *actual* advisory `quality_safety_unified_qa.json`
artifact path and recorded — closed tokens only:

```
structural_coverage_leg_status: covered
numeric_fact_sheet_extraction_leg_status: not_covered
judge_ready: false
repair_ready: false
next_step: numeric_extraction_design
```

The production hook supplies only `candidate_markdown` plus structural-coverage
sibling artifacts and **never produces a concept/fact bundle**, so the recompute
component stays `component_missing` no matter how rich the structural coverage is.
Structural coverage carries page/visual/table **counts only** — it is *not*
numeric recompute evidence and is never converted into one. This contract defines
the missing producer-input shape without inventing facts or capturing private
content.

## Existing Building Blocks

Closed design references only (verified against code, trust code over docs):

- `quality_safety_fact_sheet` — Slice 110 fact-record / fact-sheet schema and
  normalizer. Numeric facts carry `value`, `type`, `provenance`,
  `verification_status`, `confidence`, `source_ref`, and an optional
  `computation` block (`method`, `inputs`, `result`, `tolerance`).
- `quality_safety_fact_sheet_producer` — Slice 117 pure mapper from a sanitized
  `quality_safety_extraction_bundle` to a normalized fact sheet. Reads
  `concepts[].computation_records[]` and `concepts[].numeric_observations[]`.
- `quality_safety_recompute_verifier` — Slice 111 pure recompute/verify pass over
  a fact sheet; the **primary truth path**.
- `quality_safety_job_artifact` — advisory job-artifact payload builder.
- `quality_safety_extraction_coverage_bundle` — Slice 121/122 **structural**
  coverage adapter (counts only; `numeric_observation_count` is always `0`).

No raw examples from real material appear anywhere in this contract.

## Contract Boundary

The contract describes one **numeric extraction record** — a sanitized
candidate that a future caller would hand to the producer. It maps onto the
producer's `computation_records[]` entry (for recomputable facts) or
`numeric_observations[]` entry (for bare observed numbers).

Allowed fields for a numeric extraction record:

- `id` — synthetic/stable safe id (matches `^[a-z0-9][a-z0-9._-]{0,79}$`).
- `concept_id` — synthetic/stable safe id grouping records under a concept.
- `label` — safe closed/synthetic label (`^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$`).
- `fact_type` — `numeric` only for this contract.
- `value` — finite float/int (the claimed numeric value).
- `unit` — optional closed/synthetic token (no free text).
- `provenance` — `extracted_high` | `computed` | `unverified`.
- `confidence` — `high` | `medium` | `low` | `unsupported`.
- `source_ref` — sanitized token only (`^(?:source_page|page|slide|source_ref)_[0-9]{1,4}$`).
- `page_ref` — sanitized token only (same closed shape as `source_ref`).
- `computation.method` — closed method token (see Supported First Methods).
- `computation.inputs` — method-specific **numeric** arrays/maps only.
- `tolerance` — finite non-negative float within cap `(0.0, 1.0]`.
- `warnings` — closed tokens only.

Forbidden fields (must never appear in a committed record or a produced artifact):

- `raw_text`
- `source_text`
- `guide_text`
- `ocr_text`
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

Rationale: the existing producer/recompute modules already sanitize ids, labels,
source refs, and computation keys to closed shapes and drop unsafe strings; this
contract makes the **upstream** caller responsible for never emitting raw content
in the first place, so the numeric leg can be exercised without ever capturing
private text. A numeric fact is `value` + `computation.inputs` (structured
numbers) — never a copied formula string or prose snippet.

## Supported First Methods

Use only methods already supported by the recompute verifier
(`SUPPORTED_METHODS`). Each is given an **allowed synthetic input shape at a
schema level only** — no private formulas or copied real examples. Numbers below
are illustrative synthetic placeholders.

```
weighted_gini:
  inputs:
    groups:
      - <class_label_token>: finite count >= 0   # per-group class counts
      - <class_label_token>: finite count >= 0
  # equivalently each group may carry {class_counts: {<token>: count, ...}}

total_error:
  inputs:
    misclassified_weight: finite number >= 0      # single-value form
  # OR
  inputs:
    misclassified_weights: [finite number >= 0, ...]

amount_of_say:
  inputs:
    total_error: finite number in (0, 1)

softmax:
  inputs:
    values: [finite number, ...]                  # logits
    index: integer in [0, len(values))

cross_entropy:
  inputs:
    probability: finite number in (0, 1]

forward_pass:
  inputs:
    inputs:  {<node_token>: finite number, ...}
    weights: {<node_token>: finite number, ...}   # same key set as inputs
    bias: finite number (optional, default 0)
    activation: linear | relu | sigmoid (optional, default linear)
```

A bare observed number with no recomputable method maps to a
`numeric_observation` (no `computation` block); the verifier records it as
`numeric_fact_not_recomputable` and never blocks on it. Methods outside the
supported set must downgrade to a warning, never a fabricated pass.

## Real-Disaster Representability Matrix

Closed-vocabulary matrix only (derived from the existing producer + verifier
capabilities, not from any private material).

```
legacy_confused_wrong_case:
  structural_coverage_representable: true
  numeric_fact_representable: true
  recompute_blocker_possible: true
  leak_blocker_possible: true
  artifact_path_ready: false
  missing_piece: numeric_extraction

single_confident_wrong_numeric_case:
  structural_coverage_representable: true
  numeric_fact_representable: true
  recompute_blocker_possible: true
  leak_blocker_possible: true
  artifact_path_ready: false
  missing_piece: numeric_extraction

clean_real_case:
  structural_coverage_representable: true
  numeric_fact_representable: true
  recompute_blocker_possible: true
  leak_blocker_possible: true
  artifact_path_ready: false
  missing_piece: numeric_extraction
```

Reading: the fact-sheet schema and recompute verifier can already *represent*
each numeric disaster case (Slice 123 Track A proved the verifier fails the
wrong-numeric case when fed a synthetic bundle). The single shared `missing_piece`
is `numeric_extraction`: nothing yet **produces** a sanitized numeric extraction
record from real material and hands it to the producer through the artifact path.
`artifact_path_ready: false` everywhere reflects that the production hook does not
yet build a concept/fact bundle. No case is blocked by a missing
`method_contract` or a missing `source_signal` at the schema level — the methods
above cover the represented disasters.

## Proposed Next Implementation Slice

### Slice 125 — Pure Numeric Extraction Record Mapper v1

Purpose:

- A pure / unwired mapper from caller-supplied **sanitized numeric extraction
  records** (this contract's shape) into the existing
  `quality_safety_extraction_bundle` / `quality_safety_fact_sheet` shapes that the
  Slice 117 producer and Slice 111 verifier already accept.
- Synthetic tests only; no production wiring.
- No OCR parsing, no table parsing, no source/`clean.md` reading.
- No provider/model/cloud calls.
- No judge, no `overall_10`, no repair, no blocking gate.

Acceptance shape:

- Maps `concept_id`-grouped numeric extraction records into the producer's
  `concepts[].computation_records[]` (recomputable) and
  `concepts[].numeric_observations[]` (bare) lists.
- Rejects/drops any record carrying a forbidden field to a closed warning token;
  never echoes raw content; never raises.
- Round-trips through `run_quality_safety_fact_sheet_producer` and
  `build_quality_safety_recompute_report` with only numeric structured inputs.

> Do **not** lock Slice 125 if this contract finds a blocker. The matrix above
> finds no schema-level blocker (every represented disaster maps onto an existing
> method), so Slice 125 as a pure record mapper is the recommended next step. If a
> later real-material spike surfaces a method the verifier cannot recompute, the
> correct next slice instead becomes a **bounded recompute-method extension**
> (one method, pure, tested) before any mapper wiring — recommend that explicitly
> rather than widening Slice 125.

## Slice 125 Implementation Status — Pure Numeric Extraction Record Mapper v1

Slice 125 implements the **pure / unwired** mapper proposed above
(`pipeline/quality_safety_numeric_extraction_mapper.py`). No production wiring was
added; the no-leak boundary above is preserved.

Public functions:

- `normalize_quality_safety_numeric_extraction_record(record, *, index=0)` — one
  caller record → one closed numeric record (or `None` for non-mappings).
- `build_quality_safety_numeric_extraction_bundle(records, *, max_items=None,
  source_quality="synthetic")` → normalized `quality_safety_numeric_extraction_bundle`.
- `build_empty_quality_safety_numeric_extraction_bundle(reason="component_missing")`
  → empty/skipped bundle for the common "no numeric component" case.
- `map_numeric_extraction_bundle_to_fact_sheet_input(bundle, *, lecture_id=None)`
  → existing `quality_safety_extraction_bundle` shape for the Slice 117 producer.

Mapper behavior (all proven by
`test_scripts/test_quality_safety_numeric_extraction_mapper.py`, 232 checks):

- Allow-listed fields only; the closed forbidden-field list is stripped and flagged
  `forbidden_field_stripped`; no synthetic canary leaks into any produced structure.
- Supported `computation` survives with **numeric-only** `inputs` (string values
  stripped except the closed forward-pass activation tokens). Unsupported methods
  and malformed/empty inputs **demote** to a bare numeric fact (`computation: null`)
  with `unsupported_method` / `malformed_computation` — never a fabricated pass.
- Round-trips through `run_quality_safety_fact_sheet_producer` and
  `build_quality_safety_recompute_report` for all six supported methods.
- `clean_real_case` synthetic equivalent → recompute `passed`;
  `single_confident_wrong_numeric_case` synthetic equivalent → recompute `failed`
  with a blocking failure and no contradiction/leak; bare numeric observations are
  never falsely recompute-verified.
- Invalid numeric values (NaN/Infinity/strings/bools) → `null` +
  `invalid_numeric_value`; out-of-cap / non-positive tolerance → `null` +
  `invalid_tolerance` (cap `(0.0, 1.0]`); deterministic serialization; `max_items`
  caps records; caller input is never mutated; import-pure (stdlib + the verifier's
  `SUPPORTED_METHODS` only).

```
quality_safety_numeric_extraction_record_mapper_v1: implemented
mapper_status: ready
production_wiring: none
supported_methods: weighted_gini total_error amount_of_say softmax cross_entropy forward_pass
recompute_round_trip: ok
clean_real_case_synthetic: recompute_passed
single_confident_wrong_numeric_case_synthetic: recompute_failed_blocking
bare_observation_false_verify: prevented
numeric_fact_sheet_extraction_leg_status: not_covered
judge_ready: false
repair_ready: false
next_step: wire_numeric_extraction_mapper_into_advisory_artifact
no_leak_sweep: clean
docker_compose_config_run: false
```

The numeric leg remains `not_covered`: the mapper is correct on synthetic inputs
but is **not** wired into the production artifact path. Coverage is only claimable
once a real artifact path produces sanitized numeric records from real material
(Slice 126).

## Slice 126 Wiring Status — Numeric Extraction Mapper into the Advisory Artifact

Slice 126 wires the Slice 125 mapper into the **actual** advisory
`quality_safety_unified_qa.json` job-artifact path
(`pipeline/quality_safety_job_artifact.py` +
`pipeline/run_markdown_job.py:_write_quality_safety_unified_qa`). It stays
advisory/non-blocking and adds **no** production numeric extractor.

- **Safe input sidecar (read-only):** exact name
  `quality_safety_numeric_extraction_records.json`, a job-local *input* candidate
  for a future safe numeric extractor. Read only if it already exists; **never
  created or written in production**; not added to any generic artifact/export
  list or UI row. Accepts a records list or a dict wrapper
  (`records`/`numeric_records`/`numeric_extraction_records`).
- **Artifact additions (separate from structural `extraction_coverage_*`):**
  `numeric_extraction_status` (`ok|warning|skipped|partial|failed`),
  `numeric_extraction_summary` (counts only), `numeric_extraction_warnings`
  (closed mapper tokens), and the full sanitized `numeric_extraction_bundle`.
- **Path readiness:** the artifact path is **ready for synthetic numeric records**
  — clean records recompute-`passed`, wrong records raise a recompute blocker
  (`shippable=false`, `safety_floor_green=false`) through the real builder and the
  production hook. No real production numeric extractor exists yet, so the leg is
  **partial**, not covered.
- **No-leak boundary (unchanged):** numeric records are sanitized by the Slice 125
  mapper before anything is built; no source/OCR/table/caption text, copied
  formulas, numeric prose, filenames, basenames, paths, URLs, provider payloads,
  raw exceptions, or evidence quotes appear in the artifact. Structural coverage
  counts are never converted into numeric facts.

```
quality_safety_numeric_extraction_mapper_artifact_wiring: implemented
advisory_non_blocking: true
safe_input_sidecar: quality_safety_numeric_extraction_records.json
sidecar_created_in_production: false
artifact_name_unchanged: quality_safety_unified_qa.json
numeric_bundle_separate_from_structural_coverage: true
numeric_records_fabricated_from_coverage: false
clean_synthetic_numeric_through_artifact: recompute_passed
wrong_synthetic_numeric_through_artifact: recompute_failed_blocking
single_confident_wrong_numeric_case_through_artifact: recompute_failed_blocking
missing_numeric_records: skipped_component_missing
malformed_numeric_records: failed_degraded_no_leak
artifact_path_ready_for_synthetic_numeric_records: true
production_numeric_extractor_exists: false
numeric_fact_sheet_extraction_leg_status: partial
judge_ready: false
repair_ready: false
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 127 Validation Status — Numeric Sidecar Real-Path Operator Validation

Slice 127 validated the contract path through the sidecar (operator-/harness-only;
no production extractor, judge, or repair). The synthetic sidecar path is confirmed
through the actual builder and the production hook; the real/private operator pass
is deferred. The contract itself is unchanged.

```
contract_path_validated_through_sidecar: yes_synthetic
contract_path_validated_through_private_operator_material: not_run
clean_synthetic_record_recompute: passed
wrong_synthetic_record_recompute: failed_blocking
missing_sidecar_behavior: skipped_component_missing
malformed_sidecar_behavior: failed_degraded_no_leak
production_extractor_status: absent
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready_for_synthetic_numeric_records: true
judge_ready: false
repair_ready: false
next_contract_need: none_yet
next_step: safe_numeric_extractor_design
no_leak_sweep: clean
docker_compose_config_run: false
```

The contract supports the current archetypes via the supported first methods; no
new contract field or method is required before a safe numeric extractor slice.
A bounded recompute-method extension is needed only if a real case surfaces an
unsupported computation method.

## Slice 128 Design Outcome — Safe Numeric Extractor

Slice 128 designed the safe production numeric extractor that will eventually emit
records compatible with this contract (full design in
`docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`). The contract itself is
unchanged: the extractor must emit the existing record shape and defer to the
Slice 125 mapper as the final sanitizer. Design only; no production extractor code.

```
safe_numeric_extractor_design: defined
production_extractor_implemented: false
v1_input_category: caller_supplied_sanitized_numeric_candidates
forbidden_input_categories: source_documents|pdf_images|docx_files|clean_md_as_numeric_source|ocr_text|page_text|table_cells|captions|guide_text|provider_payloads|raw_runtime_artifacts|raw_artifact_json|filenames|basenames|paths|urls
output_record_shape: slice124_125_contract_unchanged
v1_methods: weighted_gini|total_error|amount_of_say|softmax|cross_entropy|forward_pass
new_methods_added: false
legacy_confused_wrong_case: partial
single_confident_wrong_numeric_case: representable
clean_real_case: representable
numeric_fact_sheet_extraction_leg_status: partial
judge_ready: false
repair_ready: false
next_step: pure_safe_numeric_extractor_v1
next_contract_need: none_unless_unsupported_method_surfaces
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 129 Mapper/Extractor Compatibility Status

Slice 129 implemented the pure safe extractor
(`pipeline/quality_safety_safe_numeric_extractor.py`). The contract is unchanged:
the extractor emits the existing record shape and **defers to the Slice 125 mapper
as the final sanitizer** (every emitted record is produced by
`normalize_quality_safety_numeric_extraction_record`). The extractor's
`quality_safety_numeric_extraction_records` payload carries records under the closed
`records` key, which the Slice 126 artifact reader's `_coerce_numeric_records`
accepts directly. No production wiring; no contract field or method added.

```
extractor_implemented: true
extractor_wired: false
final_sanitizer: slice125_mapper
record_shape: slice124_125_contract_unchanged
sidecar_records_key: records
v1_methods: weighted_gini|total_error|amount_of_say|softmax|cross_entropy|forward_pass
new_methods_added: false
contract_changed: false
judge_ready: false
repair_ready: false
no_leak_sweep: clean
docker_compose_config_run: false
```

## Non-Goals (Slice 124)

- Not the judge tranche; no judge, no `overall_10`, no `quality_judge.py`,
  `nn3.json`, `judge_response_nn3.json`, or `quality.jsonl`.
- Not repair; not prompt tuning; not a measured quality lift; not general
  hardening.
- No production wiring, no new routes, no frontend change, no generic artifact
  selector row, no blocking gate.
- No OCR/table/source/`clean.md` reading; no provider/model/cloud calls.
- Does not claim the numeric extraction leg is covered — it remains `not_covered`
  until a real artifact path proves it with safe structured concept/fact data.
