# Quality Safety E2E Validation

> Slice 120 — Advisory Artifact E2E + Extraction Metadata Inspection.
> Closed-vocabulary record only. The repo/code is the source of truth; this doc
> records *outcomes as tokens/counts/booleans*, never runtime values.

## Purpose

Validate advisory job-artifact visibility (production → exact-name fetch →
read-only UI display) and inspect the existing extraction/page metadata reality
before building the extraction-bundle adapter. The adapter design must be based
on observed repo/runtime reality, not a guessed schema.

## Scope

- advisory artifact E2E only;
- extraction/page metadata inspection only;
- no adapter implementation;
- no production behavior change (one synthetic-safe validation harness only);
- no judge;
- no prompt tuning;
- no repair;
- no blocking gate.

## Privacy Boundary

Committed records here must NOT contain any of:

- real file names;
- absolute or relative paths;
- source text;
- guide text;
- snippets;
- OCR / table / caption text;
- formulas copied from private/generated material;
- evidence quotes;
- raw artifact JSON;
- runtime output JSON;
- provider payloads;
- screenshots;
- generated files (PDF / DOCX / ZIP / images);
- URLs, data URIs, base64, tokens/keys/secrets.

Real / local operator validation may inspect runtime outputs locally, but only
closed-vocabulary outcomes are committed.

## Closed-Vocabulary Report Template

Reuse the two blocks below for future re-validation. Fill each field with a
token from its allowed set only; never paste a runtime value.

```
quality_safety_e2e_validation: run
status: ok | warning | failed | not_run
sample_type: synthetic_safe | non_private_operator_sample | not_applicable
job_completed: true | false | not_observed
artifact_name: quality_safety_unified_qa_json
artifact_produced: true | false | not_observed
exact_name_fetch: ok | failed | not_run
ui_display: ok | failed | not_run
missing_extraction_state: component_missing_skipped | failed | not_observed
artifact_advisory_non_blocking: true | false | not_observed
job_status_changed_by_quality_safety: false | true | not_observed
raw_artifact_json_committed: false
raw_runtime_output_committed: false
private_material_committed: false
provider_calls: false | not_observed
judge_calls: false
repair_calls: false
no_leak_sweep: clean | failed | not_run
warnings: []
```

```
quality_safety_extraction_metadata_inspection: run
status: ok | warning | failed | not_run
inspection_source: code_and_synthetic_runtime | code_only | runtime_only | not_run
extraction_artifact_present: true | false | unknown
page_metadata_present: true | false | unknown
candidate_fields_observed:
  - <closed structural tokens only>
visual_metadata_present: true | false | unknown
table_metadata_present: true | false | unknown
page_ref_shape: none | page_number | source_ref | page_range | mixed | unknown
leaf_count_recoverable: yes | no | unknown
numeric_observation_recoverable: yes | no | unknown
unsafe_fields_excluded:
  - <closed tokens>
extraction_leg_design_status: ready | partial | blocked
warnings: []
```

## Advisory Artifact E2E Record (Slice 120)

Method: synthetic-safe, deterministic, no Docker / provider / model. The advisory
writer was exercised with the production-equivalent call shape (candidate
markdown only, no extraction bundle — matching `pipeline/run_markdown_job.py`),
the exact-name artifact was written and read back, the read-only frontend
normalizer accepted the production-shaped payload, and a synthetic canary
smuggled through `job_metadata` was confirmed dropped. Validated by
`test_scripts/validate_quality_safety_e2e_artifact.py` (22/22) plus the existing
`frontend/scripts/verify-guide-quality-panel.mjs`.

```
quality_safety_e2e_validation: run
status: ok
sample_type: synthetic_safe
job_completed: not_observed
artifact_name: quality_safety_unified_qa_json
artifact_produced: true
exact_name_fetch: ok
ui_display: ok
missing_extraction_state: component_missing_skipped
artifact_advisory_non_blocking: true
job_status_changed_by_quality_safety: false
raw_artifact_json_committed: false
raw_runtime_output_committed: false
private_material_committed: false
provider_calls: false
judge_calls: false
repair_calls: false
no_leak_sweep: clean
warnings: []
```

Notes (closed tokens only):

- `exact_name_fetch=ok` is established two ways: (1) the API exposes the artifact
  through the existing exact-name per-file route (no generic artifact row added),
  and (2) the harness writes and reads it back by its exact filename.
- `ui_display=ok`: the read-only normalizer maps the production payload to
  `state=available` with closed statuses/components/warning tokens only.
- `missing_extraction_state=component_missing_skipped`: with no extraction bundle
  supplied (today's production path), the recompute and canonical components
  degrade to `unknown`/`skipped` and the closed `*_component_missing` warnings are
  recorded; no facts are invented and no exception is raised.
- `job_completed=not_observed`: validation was at the artifact/function + API-route
  level, not a full server job lifecycle.

## Extraction Metadata Inspection Record (Slice 120)

Method: code inspection of the existing extraction/page metadata writers and the
already-sanitized derived artifacts, plus the synthetic-runtime artifact build.
Inspected writers/derived artifacts (by capability, not by value): the per-job
extraction metadata writer, the page classifier/OCR-routing metadata, the source
coverage report, the visual assets manifest, and the table candidate/policy
artifacts.

```
quality_safety_extraction_metadata_inspection: run
status: ok
inspection_source: code_and_synthetic_runtime
extraction_artifact_present: true
page_metadata_present: true
candidate_fields_observed:
  - attachment_count
  - page_count
  - selected_page_count
  - extraction_mode
  - extraction_status
  - source_ref
  - page_ref
  - page_index
  - visual_count
  - table_count
  - artifact_presence
  - material_selection_status
  - source_coverage_counts
  - visual_plan_counts
  - table_policy_counts
visual_metadata_present: true
table_metadata_present: true
page_ref_shape: mixed
leaf_count_recoverable: yes
numeric_observation_recoverable: no
unsafe_fields_excluded:
  - raw_text
  - paths
  - filenames
  - urls
  - ocr_text
  - table_cells
  - captions
  - formulas
  - evidence_quotes
  - provider_payloads
  - runtime_traces
extraction_leg_design_status: partial
warnings: []
```

Notes (closed tokens only):

- `page_ref_shape=mixed`: per-page records carry a page number/index, derived
  reports key by a source reference, and a page-anchor boolean exists — the
  reference shape is not uniform across artifacts.
- `leaf_count_recoverable=yes`: structural counts (page counts, per-category page
  counts, visual asset counts, table counts) are recoverable as closed integers.
- `numeric_observation_recoverable=no`: current metadata stores *structural counts
  only*. It does not store per-fact numeric content observations, so the numeric
  recompute leg (the kind the recompute verifier checks) cannot be fed from
  today's extraction metadata.
- `unsafe_fields_excluded` is load-bearing: the raw extraction metadata artifact
  carries a source basename field, so any adapter must read only sanitized
  structural counts/tokens and must never carry the basename, paths, or any text.
- `extraction_leg_design_status=partial`: a structural-count adapter leg is
  feasible now; a numeric-observation/recompute leg is not recoverable from
  current metadata.

## Adapter Design Notes From Observed Reality

Design-level conclusions only (no schema committed, no implementation):

```
adapter_input_candidates:
  - source_coverage_counts        # prefer the already-sanitized coverage report
  - page_count
  - extraction_mode
  - visual_plan_counts
  - table_policy_counts
  - material_selection_status
adapter_output_target: quality_safety_extraction_bundle
first_supported_fact_kinds:
  - structural_count
  - coverage_presence
first_supported_methods:
  - count_presence
  - structural_coverage
missing_data_behavior: component_missing_skipped
unsafe_fields_policy: exclude
production_wiring_status: deferred_to_slice_122
adapter_design_status: partial
```

- Prefer the already-sanitized source coverage report as the primary input: it is
  keyed by a source reference (not a basename) and exposes per-category page
  counts. Treat the raw extraction metadata artifact as a secondary, name-bearing
  source from which only sanitized structural counts/tokens may be read.
- The first adapter version should emit structural-count / coverage-presence facts
  only. Numeric-recompute facts are out of reach until a future slice records
  numeric content observations; do not invent them.
- Missing or malformed metadata must degrade to the closed `component_missing` /
  `skipped` state already used by the advisory artifact — never an error and never
  a fabricated fact.

## Adapter Implementation Outcome (Slice 121)

The pure/unwired adapter `pipeline/quality_safety_extraction_bundle_adapter.py`
was implemented from the Slice 120 findings above. Closed-vocabulary outcome only:

```
quality_safety_extraction_adapter_v1: implemented
purity: pure_unwired
output_kind: quality_safety_extraction_coverage_bundle
preferred_input: source_coverage_report
secondary_input: extraction_metadata_structural_counts_only
visual_input: visual_inclusion_plan_counts
table_input: table_candidates_manifest_and_policy_counts
first_supported_fact_kinds: structural_count, coverage_presence
numeric_observations: empty
numeric_observation_count: 0
numeric_observations_fabricated: false
source_basename_echoed: false
raw_text_echoed: false
path_or_url_echoed: false
page_ref_handling: closed_tokens_with_mixed_page_ref_shape_warning
malformed_input_behavior: degrades_to_skipped_or_warning_never_raises
caller_input_mutated: false
deterministic_serialization: true
producer_compatibility: safe_degradation_empty_or_partial_fact_sheet
adapter_design_status: ready_for_structural_leg
production_wiring_status: deferred_to_slice_122
no_leak_sweep: clean
provider_calls: false
judge_calls: false
repair_calls: false
warnings: []
```

Notes (closed tokens only):

- `adapter_design_status=ready_for_structural_leg`: the structural-count /
  coverage-presence leg that Slice 120 marked feasible is now implemented and
  tested; the numeric-observation/recompute leg remains out of reach
  (`numeric_observation_recoverable=no`) and is intentionally not fabricated.
- `producer_compatibility=safe_degradation_empty_or_partial_fact_sheet`: the
  coverage bundle carries no `concepts`, so the Slice 117 producer yields an
  empty/partial fact sheet without raising or leaking — proven by test.
- `output_kind` is distinct from the producer's concept/fact
  `quality_safety_extraction_bundle` to avoid a name/shape collision (see
  `DECISIONS.md`).

## Adapter Wiring Outcome (Slice 122)

The Slice 121 coverage adapter is now wired into the advisory
`quality_safety_unified_qa.json` job artifact path. Closed-vocabulary outcome only:

```
extraction_coverage_wiring: implemented
wiring_mode: advisory_non_blocking
artifact_name: quality_safety_unified_qa_json
artifact_kind: quality_safety_job_artifact
added_fields: extraction_coverage_status, extraction_coverage_summary, extraction_coverage_bundle
coverage_bundle_kind: quality_safety_extraction_coverage_bundle
coverage_status_vocabulary: ok|warning|skipped|partial|failed
no_metadata_behavior: extraction_coverage_status_skipped
no_metadata_warning: extraction_coverage_missing
degraded_warning: extraction_coverage_degraded
metadata_source: already_produced_safe_sibling_json_artifacts_read_only
fed_into_concept_fact_producer: false
fed_into_recompute_verifier: false
numeric_observations: empty
numeric_observation_count: 0
numeric_observations_fabricated: false
fact_sheet_component_state: component_missing_when_no_concept_bundle
recompute_component_state: component_missing_when_no_concept_bundle
canonical_component_state: component_missing_when_no_fixture
shippable_upgraded_by_coverage: false
safety_floor_green_upgraded_by_coverage: false
job_status_changed_by_quality_safety: false
provider_calls: false
judge_calls: false
repair_calls: false
frontend_changed: false
routes_changed: false
hostile_field_exclusion: paths|urls|basenames|filenames|ocr_text|table_cells|captions|formulas|snippets|provider_payloads|authorization|data_uri|base64|raw_exceptions
deterministic_serialization: true
caller_input_mutated: false
job_artifact_tests: 276_passed
e2e_artifact_harness: 36_passed
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 123 — Real-Disaster E2E with Advisory Coverage Leg

**Scope.** Validate the *actual* advisory `quality_safety_unified_qa.json` job
artifact path against the real-disaster case archetypes after the Slice 122
coverage wiring, and record — honestly, in closed vocabulary — which legs are
covered. This is an operator-/harness-validation slice: it adds no production
code change (one synthetic-safe harness plus docs only).

**Privacy boundary.** Real operator validation may inspect private local material
at runtime, but committed records carry closed tokens only. No real PDFs, images,
DOCX/PDF/ZIPs, generated guides, runtime artifacts, eval/trace outputs, raw
artifact JSON, raw extracted metadata, provider payloads, source/reference/spec
filenames, paths, OCR/table/caption text, guide snippets, copied formulas,
numeric prose, or evidence quotes are committed.

**Two-leg distinction (the core honesty point).**
- *Structural coverage leg* — now wired into the advisory artifact via
  `extraction_coverage_bundle` (Slice 122). Present with safe synthetic structural
  metadata; `skipped` when absent.
- *Numeric fact-sheet extraction leg* — still NOT covered through the production
  hook. `_write_quality_safety_unified_qa` supplies only `candidate_markdown` plus
  the structural-coverage sibling artifacts; it never produces a concept/fact
  bundle, so recompute stays `component_missing` / `skipped` no matter how rich
  the structural coverage is. Structural coverage is not numeric recompute
  evidence and is never converted into one.

### Track A — Synthetic-safe artifact-path validation

`test_scripts/validate_quality_safety_real_disaster_e2e.py` (41 checks, all
passed) drives the real builder and the real production hook with synthetic-safe
inputs across the three archetypes. Closed-vocabulary records (display only):

```
clean_real_case:                  artifact_path_exercised=true input_kind=synthetic_safe job_artifact_produced=true advisory_non_blocking=true extraction_coverage_bundle_present=true extraction_coverage_status=ok structural_coverage_leg_covered=true numeric_fact_sheet_extraction_leg_covered=true recompute_blocker_present=false unified_status=passed shippable=true safety_floor_green=true
single_confident_wrong_numeric_case: artifact_path_exercised=true input_kind=synthetic_safe job_artifact_produced=true advisory_non_blocking=true extraction_coverage_bundle_present=true extraction_coverage_status=ok structural_coverage_leg_covered=true numeric_fact_sheet_extraction_leg_covered=true recompute_blocker_present=true unified_status=failed shippable=false safety_floor_green=false
legacy_confused_wrong_case:       artifact_path_exercised=true input_kind=synthetic_safe job_artifact_produced=true advisory_non_blocking=true extraction_coverage_bundle_present=true extraction_coverage_status=ok structural_coverage_leg_covered=true numeric_fact_sheet_extraction_leg_covered=false recompute_blocker_present=false unified_status=warning shippable=true safety_floor_green=false
```

Note the `legacy_confused_wrong_case` is the production-shaped archetype: no
concept/fact bundle is supplied (mirroring the real hook), so the numeric leg is
honestly uncovered (`recompute_component_state=unknown`, no recompute blocker)
even though structural coverage is present. Cases 1–2 show the numeric leg works
*when* a synthetic concept/fact bundle is fed — proving the verifier, not the
production extraction path. Structural coverage never invented a numeric
observation (`numeric_observation_count=0` everywhere) and never upgraded
`shippable` / `safety_floor_green`.

### Track B — Real-disaster operator validation record (closed tokens)

No real-material generation was executed in this automated session (no provider/
model/cloud calls are permitted here), so the real-material runs are honestly
recorded as `not_observed` for runtime-dependent fields. The structurally
code-guaranteed invariants are recorded directly. See
`QUALITY_SAFETY_OPERATOR_VALIDATION.md` → Slice 123 for the per-case records.

### Closed outcome

```
quality_safety_real_disaster_e2e_validation: run
status: ok
artifact_path_validation: ok
synthetic_track_a: 41_passed
real_track_b_runtime: not_observed
structural_coverage_leg_status: covered
numeric_fact_sheet_extraction_leg_status: not_covered
structural_coverage_upgrades_shippable: false
numeric_observations_fabricated: false
advisory_non_blocking: true
provider_calls: false
judge_calls: false
repair_calls: false
judge_ready: false
repair_ready: false
next_step: numeric_extraction_design
no_leak_sweep: clean
docker_compose_config_run: false
warnings: []
```

**Next-step recommendation.** Do not proceed to a judge baseline or repair: the
numeric fact-sheet extraction leg is not covered through the production artifact
path (no concept/fact bundle is produced). The next engineering slice should be
**numeric extraction design** — a safe concept/fact extraction-to-fact-sheet
mapper that feeds the existing recompute verifier — before any judge/repair work.

## Slice 124 — Numeric Extraction Contract Design (cross-reference)

Slice 124 acts on the Slice 123 finding above. It is **design-first, no
production wiring**: it defines the safe structured numeric extraction contract
(`docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md`) that a later slice can use
to feed the existing fact-sheet producer and recompute verifier, and adds a pure
synthetic contract harness (`test_scripts/test_quality_safety_numeric_extraction_contract.py`,
27 passed). The numeric leg remains `not_covered` and `judge_ready`/`repair_ready`
remain `false` — the contract does not claim coverage.

```
quality_safety_numeric_extraction_contract_design: run
status: ok
production_wiring: none
contract_doc_added: true
synthetic_contract_harness: 27_passed
supported_methods: weighted_gini total_error amount_of_say softmax cross_entropy forward_pass
representability_missing_piece: numeric_extraction
numeric_fact_sheet_extraction_leg_status: not_covered
judge_ready: false
repair_ready: false
next_step: pure_numeric_extraction_record_mapper_v1
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 125 — Pure Numeric Extraction Record Mapper v1 (cross-reference)

Slice 125 implements the pure / unwired mapper proposed by the Slice 124 contract
(`pipeline/quality_safety_numeric_extraction_mapper.py`) plus a synthetic harness
(`test_scripts/test_quality_safety_numeric_extraction_mapper.py`, 232 passed). The
mapper translates sanitized numeric extraction records into the existing producer
extraction-bundle shape and round-trips through the producer + recompute verifier.
**No production wiring** was added; the numeric leg remains `not_covered` and
`judge_ready`/`repair_ready` remain `false`.

```
quality_safety_numeric_extraction_record_mapper_v1: run
status: ok
mapper_status: ready
production_wiring: none
synthetic_mapper_harness: 232_passed
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

## Slice 126 — Wire Numeric Extraction Mapper into Advisory Artifact

Slice 126 wires the Slice 125 mapper into the **actual** advisory
`quality_safety_unified_qa.json` job-artifact path (builder
`pipeline/quality_safety_job_artifact.py` and the production hook
`pipeline/run_markdown_job.py:_write_quality_safety_unified_qa`). The real-disaster
E2E harness (`test_scripts/validate_quality_safety_real_disaster_e2e.py`, 60 passed)
and the job-artifact harness (`test_scripts/test_quality_safety_job_artifact.py`,
428 passed) prove synthetic numeric records flow through the producer + recompute
verifier via the actual builder and the production hook (sidecar read). Advisory /
non-blocking; no production numeric extractor was added.

```
quality_safety_numeric_extraction_mapper_artifact_wiring: run
status: ok
advisory_non_blocking: true
safe_input_sidecar: quality_safety_numeric_extraction_records.json
sidecar_created_in_production: false
artifact_name_unchanged: quality_safety_unified_qa.json
numeric_bundle_separate_from_structural_coverage: true
numeric_records_fabricated_from_coverage: false
structural_coverage_leg_status: covered
clean_synthetic_numeric_through_artifact: recompute_passed
wrong_synthetic_numeric_through_artifact: recompute_failed_blocking
single_confident_wrong_numeric_case_through_artifact: recompute_failed_blocking
missing_numeric_records: skipped_component_missing
malformed_numeric_records: failed_degraded_no_leak
production_hook_reads_numeric_sidecar: ok
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true
production_numeric_extractor_exists: false
judge_ready: false
repair_ready: false
next_step: safe_numeric_extractor_or_real_operator_numeric_validation
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 127 — Numeric Sidecar Real-Path Operator Validation

**Scope.** Operator-/harness-validation of the Slice 126 numeric sidecar advisory
artifact path against the real-disaster archetypes. No production extractor, no
judge, no repair, no prompt tuning. The synthetic sidecar path is re-confirmed
through the actual builder and the production hook; the real/private operator pass
is deferred. Closed-vocabulary summary:

```
numeric_sidecar_real_path_validation: run
slice: 127
status: partial
synthetic_sidecar_artifact_path: ok
sidecar_missing_behavior: skipped_numeric_extraction_missing_no_crash
sidecar_malformed_behavior: failed_numeric_extraction_degraded_no_leak
clean_synthetic_recompute_through_artifact: passed
wrong_synthetic_recompute_through_artifact: failed_blocking
production_hook_reads_numeric_sidecar: ok
advisory_non_blocking: true
structural_coverage_separate: true
numeric_records_fabricated_from_coverage: false
private_operator_sidecar_artifact_path: not_run
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready_for_synthetic_numeric_records: true
production_numeric_extractor_exists: false
judge_ready: false
repair_ready: false
next_step: safe_numeric_extractor_design
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 128 — Safe Numeric Extractor Design (cross-reference)

Slice 128 is a design-only slice (full design in
`docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md`). It adds no production
extractor, runs no new E2E path, and changes no artifact behavior; the synthetic
sidecar artifact path from Slice 126/127 is unchanged. Closed-vocabulary outcome:

```
safe_numeric_extractor_design: defined
production_extractor_implemented: false
v1_input_category: caller_supplied_sanitized_numeric_candidates
v1_methods: weighted_gini|total_error|amount_of_say|softmax|cross_entropy|forward_pass
new_methods_added: false
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_changed: false
judge_ready: false
repair_ready: false
next_step: pure_safe_numeric_extractor_v1
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 129 — Pure Safe Numeric Extractor v1 (cross-reference)

Slice 129 implemented the pure/unwired extractor
(`pipeline/quality_safety_safe_numeric_extractor.py`). It is **not** production
wiring: no module imports it, no artifact is written, and the production job
artifact path is unchanged. Synthetic tests prove the extractor payload flows
through `_coerce_numeric_records` → mapper → producer → recompute verifier, and
straight into the real Slice 126 artifact path. Closed-vocabulary outcome:

```
extractor_implemented: true
extractor_wired: false
final_sanitizer: slice125_mapper
sidecar_payload_compatible: true
single_confident_wrong_numeric_case: recompute_blocked
clean_real_case: recompute_passed
legacy_confused_wrong_case: partial
v1_methods: weighted_gini|total_error|amount_of_say|softmax|cross_entropy|forward_pass
new_methods_added: false
artifact_path_changed: false
judge_ready: false
repair_ready: false
next_step: wire_safe_numeric_extractor_into_advisory_artifact_path
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 130 — Safe Numeric Extractor Wired into Advisory Artifact Path

Slice 130 wired the Slice 129 extractor into the advisory artifact path. An
optional, read-only, internal candidate sidecar
`quality_safety_safe_numeric_candidates.json` feeds the extractor; its records run
through the existing Slice 126 numeric mapper + producer + recompute verifier. The
real-disaster e2e harness exercises this through both
`build_quality_safety_job_artifact_payload(safe_numeric_candidates=...)` and the
production hook `_write_quality_safety_unified_qa`. Observed closed-vocabulary
outcome (synthetic):

```
safe_numeric_extractor_wired_into_artifact: true
safe_numeric_candidates_input_artifact: quality_safety_safe_numeric_candidates.json
candidate_sidecar_written_in_production: false
precedence: explicit_numeric_records_over_safe_candidates
safe_numeric_extractor_artifact_path_status: ok
clean_safe_candidate_recompute: passed
wrong_safe_candidate_recompute: failed_blocking
unsupported_method_candidate: counted_not_blocked
structural_coverage_into_candidates: false
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_candidates
production_numeric_extractor_present: sidecar_candidate_only
judge_ready: false
repair_ready: false
next_step: production_safe_candidate_source_or_operator_waiver
no_leak_sweep: clean
docker_compose_config_run: false
```

## Slice 131 — Production Safe Candidate Source Discovery

Slice 131 is docs-only discovery. It inspected existing code/docs and did not run
operator runtime validation. Closed-vocabulary outcome:

```
production_safe_candidate_source_discovery: run
status: partial
inspection_source: code_only
existing_production_safe_source_present: false
sidecar_only_source_present: true
source_coverage_report_can_feed_candidates: false
extraction_metadata_can_feed_candidates: false
visual_inclusion_plan_can_feed_candidates: false
table_candidates_manifest_can_feed_candidates: false
table_reconstruction_policy_can_feed_candidates: false
single_confident_wrong_numeric_case_support: sidecar_or_future_artifact
clean_real_case_support: sidecar_or_future_artifact
legacy_confused_wrong_case_support: partial
operator_waiver_recorded: false
numeric_fact_sheet_extraction_leg_status: partial
judge_ready: false
repair_ready: false
next_step: future_structured_numeric_artifact_design
docker_compose_config_run: false
```

## Slice 132 — Future Structured Numeric Artifact Design

Slice 132 is docs-only design. It does not run operator runtime validation and
does not change the e2e artifact path.

```
future_structured_numeric_artifact_design: defined
future_artifact: quality_safety_structured_numeric_candidates.json
adapter_implemented: false
producer_implemented: false
production_wiring_changed: false
single_confident_wrong_numeric_case_representable: true
single_confident_wrong_numeric_case_expected_recompute: failed_blocking
clean_real_case_representable: true
clean_real_case_expected_recompute: passed
legacy_confused_wrong_case_representable: partial
legacy_confused_wrong_case_expected_recompute: partial
numeric_fact_sheet_extraction_leg_status: partial
judge_ready: false
repair_ready: false
next_step: pure_structured_numeric_candidate_artifact_adapter_v1
docker_compose_config_run: false
```

## Slice 133 — Pure Structured Numeric Candidate Adapter v1

Slice 133 is pure/unwired adapter work. It does not run operator runtime
validation and does not wire the adapter into production.

```
structured_numeric_candidate_adapter: ready
adapter_module: pipeline/quality_safety_structured_numeric_candidate_adapter.py
input_kind: quality_safety_structured_numeric_candidates
output_kind: quality_safety_safe_numeric_candidates
output_wrapper_key: candidates
production_wiring_changed: false
producer_implemented: false
extractor_mapper_recompute_chain: passed
advisory_artifact_path_compatibility: passed_synthetic_wrapper_only
single_confident_wrong_numeric_case: failed_blocking
clean_real_case: passed
legacy_confused_wrong_case: partial
unsupported_methods: degrade_unverified
numeric_fact_sheet_extraction_leg_status: partial
judge_ready: false
repair_ready: false
next_step: wire_structured_numeric_candidate_adapter_into_advisory_artifact_path
docker_compose_config_run: false
```

## Slice 134 — Structured Numeric Adapter Advisory Artifact Wiring

Slice 134 wires the adapter into the advisory artifact path for synthetic/read-only
structured sidecars. It does not implement the future producer.

```
structured_numeric_candidate_adapter_artifact_path_status: ok
structured_numeric_candidates_input_artifact: quality_safety_structured_numeric_candidates.json
safe_numeric_extractor_artifact_path_status: ok
numeric_fact_sheet_extraction_leg_status: partial
artifact_path_ready: true_for_synthetic_structured_candidates
production_numeric_extractor_present: structured_artifact_sidecar_only
precedence: explicit_records_over_safe_candidates_over_structured_candidates
clean_structured_candidate_recompute: passed
wrong_structured_candidate_recompute: failed_blocking
legacy_confused_wrong_case: partial
structured_adapter_status_without_sidecar: skipped
structural_coverage_into_structured_candidates: false
producer_implemented: false
judge_ready: false
repair_ready: false
next_step: future_structured_numeric_candidate_producer_design_or_operator_waiver
docker_compose_config_run: false
```

## Non-Goals

- The Slice 122 coverage wiring is advisory transparency only; the numeric /
  recompute extraction leg remains NOT covered (structural counts are not numeric
  recompute evidence).
- Do not treat structural coverage as numeric facts, feed it to the concept/fact
  producer, or let it upgrade `shippable` / `safety_floor_green`.
- Do not change API routes, frontend display, generation prompts, request
  schemas, provider/model/cloud behavior, render/export/OCR/table/visual behavior,
  or Ask Guide.
- Do not add a generic artifact selector/listing row.
- Do not make Quality Safety blocking.
- Do not add judge scoring, `overall_10`, `quality_judge.py`, `nn3.json`,
  `judge_response_nn3.json`, or `quality.jsonl`.
- Do not implement repair.
