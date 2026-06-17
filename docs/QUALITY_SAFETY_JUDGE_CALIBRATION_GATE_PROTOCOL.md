# Quality Safety Judge Calibration Gate Protocol

> Design / protocol-only (Slice 144). Closed-vocabulary only. This protocol does
> **not** run private calibration, does **not** implement judge execution, and
> adds **no** provider/model/cloud/local-LLM calls, **no** repair, **no** prompt
> tuning, and **no** production wiring. The repo/code is the source of truth; if
> any doc disagrees with the implementation, trust the code and verify.

## Purpose

Define the closed-vocabulary **calibration gate** that must pass before any
offline judge report can be trusted as an **advisory** quality signal.

The Slice 143 offline judge core
(`pipeline/quality_safety_offline_judge_core.py`) is pure, deterministic, and
synthetic-only. Its output is **not** trusted for real quality decisions yet.
This protocol defines the golden-case set, the closed-vocabulary calibration
record shape, and the conservative pass/fail rules that a **later** slice would
have to satisfy before `judge_ready` could ever be considered.

This protocol does not run private calibration and does not implement judge
execution.

## Current Preconditions

Closed vocabulary (reconciled against the deterministic floor final gate,
offline judge contract, schema, and core):

```
deterministic_safety_floor_status: ready_for_cleanup_freeze
numeric_infrastructure_frozen: true
quality_safety_surface_frozen: true
quality_safety_blocking: false
offline_judge_contract_status: ready
offline_judge_schema_status: ok
offline_judge_core_status: ok
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
```

## Boundary

The calibration gate is:

- `protocol_only`
- `advisory_only`
- `non_blocking`
- `no_repair`
- `no_prompt_tuning`
- `no_provider_calls`
- `no_llm_calls`
- `no_judge_calls`
- `no_runtime_outputs_committed`
- `no_private_material_committed`
- `no_numeric_infrastructure_unfreeze`

The gate observes; it never edits guides, never writes job artifacts, never
exposes anything in the UI, and never makes Quality Safety blocking.

## Golden Case Set

The required future golden cases, in closed vocabulary only. Each case is
described by closed expectations; **no** real text, guide snippets, source
snippets, formulas, filenames, paths, screenshots, examples, or raw judge
outputs are included or permitted here.

### 1. clean_real_case

```
expected_deterministic_floor: pass
expected_judge_status: ok|warning
expected_blockers: none
expected_axis_pattern: mostly_pass
required_operator_review: true
```

### 2. single_confident_wrong_numeric_case

```
expected_deterministic_floor: failed_blocking
expected_judge_status: failed|partial
expected_blockers: recompute_or_correctness
expected_axis_pattern: correctness_fail
required_operator_review: true
```

### 3. legacy_confused_wrong_case

```
expected_deterministic_floor: partial
expected_judge_status: warning|partial|failed
expected_blockers: not_required
expected_axis_pattern: source_grounding_or_correctness_warning
required_operator_review: true
```

### 4. leak_canary_case

```
expected_deterministic_floor: failed_blocking|warning
expected_judge_status: failed
expected_blockers: leakage_privacy
expected_axis_pattern: leakage_fail
required_operator_review: true
```

### 5. deterministic_floor_red_case

```
expected_deterministic_floor: blocked|failed_blocking
expected_judge_status: failed|partial
expected_blockers: deterministic_floor_red
expected_axis_pattern: not_allowed_to_override_floor
required_operator_review: false
```

> The closed expectation tokens above (`recompute_or_correctness`,
> `leakage_privacy`, `correctness_fail`, etc.) are golden-case **expectation
> labels**, not committed report fields. The actual report `blockers` /
> `axis_results` remain those of the Slice 142 schema closed vocabularies; the
> calibration record records only counts and closed statuses (next section).

## Calibration Record Shape

The future **committed** calibration record. Closed-vocabulary only — never raw
private material, never runtime judge outputs, never free-text rationales.

```
validation_id: quality_safety_judge_calibration_gate
input_kind: synthetic_only | private_operator_closed_record | not_run
golden_case_count: <non-negative int>
passed_case_count: <non-negative int>
failed_case_count: <non-negative int>
operator_review_count: <non-negative int>
raw_private_material_committed: false
runtime_outputs_committed: false
provider_calls: false
llm_calls: false
judge_calls: false | synthetic_only | local_offline
repair_calls: false
deterministic_floor_status: ready_for_cleanup_freeze | partial | blocked | unknown
offline_judge_core_status: ok | warning | failed | not_observed
schema_compatibility_status: ok | warning | failed | not_observed
leak_safety_status: ok | warning | failed | not_observed
calibration_status: not_started | synthetic_only | operator_validated | failed | blocked
judge_ready: false | true
repair_ready: false
warnings: [ closed tokens only ]
```

For **Slice 144**:

- `calibration_status` must remain `synthetic_only` or `not_started`.
- `judge_ready` must remain `false`.
- `repair_ready` must remain `false`.
- No calibration record is actually produced in this slice (protocol-only).

## Pass/Fail Rules

Conservative rules. Calibration is *not* allowed to flip readiness on its own;
each step below is a **necessary** condition, and the final flip is a separate
explicit decision in a later slice.

Calibration may become `operator_validated` **only in a later slice** if **all**
of the following hold:

- all required golden cases have closed-vocabulary operator records;
- the deterministic floor remains passing where expected;
- the `single_confident_wrong_numeric_case` is detected as blocking/failing;
- the `leak_canary_case` is detected as failing;
- the `deterministic_floor_red_case` cannot be overridden by the judge;
- no raw private material is committed;
- no provider/cloud/private runtime payload is committed;
- no free-text private rationales are committed;
- `schema_compatibility_status=ok`;
- `offline_judge_core_status=ok`;
- the operator review count covers all required private cases.

The judge may become **ready** (`judge_ready=true`) **only in a later gate** if:

- `calibration_status=operator_validated`;
- the pass/fail rules above all pass;
- the deterministic floor remains the source of truth;
- a later **explicit** decision sets `judge_ready=true`.

`repair_ready` remains `false` regardless of calibration. Repair is out of scope
for this entire protocol.

## Relationship to Offline Judge Core

- Slice 143 core is **synthetic-only and deterministic** (no LLM, no provider,
  no file I/O).
- Core output is **not trusted** for real quality decisions yet.
- The core **cannot** be used on private material until this calibration
  protocol is actually exercised in a later slice.
- Future private/operator calibration must commit **only closed records**.
- **No** raw judge report from private material may be committed.

## Relationship to Deterministic Safety Floor

- The deterministic floor remains a **hard gate / source of truth**.
- The judge **cannot** override recompute blockers.
- The judge **cannot** override leak/privacy blockers.
- The judge **cannot** mark anything shippable if the deterministic floor is red.
- The judge **cannot** fabricate facts from structural coverage metadata.
- The judge remains **advisory** even after calibration unless a later explicit
  policy decision changes it.

This protocol does **not** unfreeze the numeric infrastructure or the
deterministic surface, and adds **no** numeric schema/bridge layer.

## Proposed Next Slice

**Slice 145 — Private Operator Judge Calibration Pass.** Kept precise:

- the private/local operator run is **optional and local**;
- committed output must be **closed vocabulary only**;
- **no** raw private guide/source/reference text;
- **no** model/provider/cloud calls unless explicitly approved;
- **no** `judge_ready=true` unless the gate criteria are actually met and
  explicitly recorded.

**Alternative (if avoiding any private run):** *Slice 145 — Synthetic
Calibration Gate Harness* — a synthetic-only harness that exercises this
protocol's golden-case expectations against the Slice 143 core, committing only
a closed-vocabulary record.

Recommended `next_step` for now: `private_operator_judge_calibration_pass`
(choose the conservative path based on readiness; the synthetic harness is the
safe fallback if no private run is desired).

## Decision Record

```
judge_calibration_gate_protocol_status: ready
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: private_operator_judge_calibration_pass
docker_compose_config_run: false
```

Conservative posture: the **protocol** can be `ready`; **judge readiness must
remain false** and **repair readiness must remain false** until a later explicit
gate (and operator validation) approves them.

## Slice 145 — Calibration Gate Harness / Private Pass Status

Slice 145 implemented the closed-record **calibration gate harness**
(`test_scripts/validate_quality_safety_judge_calibration_gate.py`) that exercises
this protocol. The harness validates **closed-vocabulary calibration records**,
not raw/private materials:

- Default **synthetic self-test** runs the five golden cases (`clean_real_case`,
  `single_confident_wrong_numeric_case`, `legacy_confused_wrong_case`,
  `leak_canary_case`, `deterministic_floor_red_case`) by exercising the pure
  Slice 143 offline judge core over **synthetic** observations only. The synthetic
  cases are closed records, not private material.
- Optional **local closed-record mode** (`--input <path>`) reads exactly one
  closed calibration-record JSON, never prints the path or raw values, never
  writes files, and degrades read/parse failures to closed tokens.
- The harness never reads guide/source/reference documents, never reads raw judge
  reports, never invokes the judge core on private material, never calls
  providers/models/cloud/local LLMs, and prints a closed-vocabulary summary only.

The synthetic self-test confirms the protocol's conservative behavior: the
wrong-numeric case is detected as blocking, the leak canary is detected as
failing, the floor-red case cannot be overridden, no canary survives
serialization, and `judge_ready` / `repair_ready` stay `false`.

```
private_operator_judge_calibration_run: not_run
calibration_gate_harness_status: ok
golden_case_count: 5
passed_case_count: 5
failed_case_count: 0
input_kind: synthetic_only
protocol_status: ok
no_raw_private_material: true
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: advisory_judge_artifact_design_or_stop_for_private_calibration
docker_compose_config_run: false
```

No private/operator closed-record run was performed in Slice 145; local
closed-record mode is implemented but not run as committed data. Calibration stays
`synthetic_only` and the judge stays advisory and non-blocking.

## Slice 146 — Advisory Offline Judge Artifact Design relationship

Slice 146 (docs/design-only) adds
`docs/QUALITY_SAFETY_ADVISORY_OFFLINE_JUDGE_ARTIFACT_DESIGN.md`, which designs how a
*future* advisory offline judge report artifact may be stored and surfaced **after**
this calibration gate passes. The design does not implement artifact writing, does
not wire anything into production, and does not relax this protocol: the calibration
gate / golden protocol remains the precondition for any judge trust, the
deterministic floor stays the source of truth, and the future judge stays advisory
and non-blocking. The artifact's display is gated on a later calibration policy
decision; `judge_ready` and `repair_ready` stay false.

```
advisory_judge_artifact_design_status: ready
artifact_write_ready: false
ui_display_ready: false
judge_calibration_gate_protocol_status: ready
calibration_status: synthetic_only
private_operator_judge_calibration_run: not_run
judge_ready: false
repair_ready: false
next_step: advisory_offline_judge_artifact_schema_adapter_or_stop_for_private_calibration
docker_compose_config_run: false
```
