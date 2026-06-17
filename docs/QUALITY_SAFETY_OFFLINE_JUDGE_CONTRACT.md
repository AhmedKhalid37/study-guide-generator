# Quality Safety Offline Judge Contract

> Design-only contract for a future offline judge. Closed-vocabulary only. No raw
> artifacts, no private material, no judge implementation, no provider/model/cloud
> calls, no repair, no prompt tuning, no production wiring. The repo/code is the
> source of truth; this doc designs a contract, it does not produce an artifact.

---

## Purpose

Define the contract for a future offline judge that evaluates generated guide
quality **after** the deterministic safety floor has passed.

This contract does not implement the judge. Slice 141 designs the contract only.
No judge core, no judge calls, no provider/model/cloud/local-LLM calls, no
`quality_judge.py`, no runtime judge outputs (`nn3.json`,
`judge_response_nn3.json`, `quality.jsonl`) are added.

The offline judge — once it exists and is calibrated — would be **advisory only**
and layered strictly on top of the frozen deterministic surface
(`docs/QUALITY_SAFETY_SURFACE_FREEZE.md`). It can never relax a deterministic
blocker.

---

## Preconditions

Closed vocabulary:

```
deterministic_safety_floor_status: ready_for_cleanup_freeze
numeric_infrastructure_frozen: true
judge_contract_ready: true
judge_ready: false
repair_ready: false
offline_judge_contract_status: design_only
```

The deterministic (non-judge) Quality Safety surface is frozen (Slice 140). The
judge contract may now be designed, but no judge exists and none is implemented in
this slice.

---

## Boundary

The offline judge is:

- `offline_only`
- `advisory_only`
- `non_blocking_initially`
- `no_repair`
- `no_prompt_tuning`
- `no_provider_calls_in_contract_slice`
- `no_runtime_outputs_committed`
- `no_private_material_committed`

The judge never edits `clean.md`, never calls a provider/model/cloud endpoint
inside this contract slice, never repairs or rewrites guide text, never tunes
prompts, and never becomes a blocking gate by virtue of this contract.

---

## Allowed Runtime Inputs Later

These are **future runtime-only** input categories for when the judge is built and
calibrated. No example drawn from real/private material is committed here; only the
category names and closed-vocabulary shapes are designed.

Allowed future runtime inputs may include:

- generated guide markdown or `clean.md` at runtime (read-only, never committed)
- the deterministic `quality_safety_unified_qa.json` advisory payload at runtime
- sanitized source coverage summaries (counts/coverage only)
- sanitized extraction coverage summaries (`extraction_coverage_*`, counts only)
- sanitized operator validation summaries (closed-vocabulary status only)
- optional private/local reference material at runtime only, **never committed**
- synthetic fixtures for tests (synthetic ids and synthetic canaries only)

Important:

- The contract may allow the **future** judge to inspect private/local material at
  **runtime**, but every **committed** output must be closed-vocabulary and
  sanitized.
- No committed format may contain raw guide/source/reference text. Runtime input
  text stays at runtime; only sanitized, closed-vocabulary, count-only summaries
  may ever be committed.

---

## Forbidden Committed Content

The following must never appear in any committed judge-related record:

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
- raw artifact JSON from private jobs
- provider payloads
- model prompts or responses from private jobs
- judge free-text rationales from private jobs
- chain-of-thought
- `quality_judge.py` output dumps
- `nn3.json`
- `judge_response_nn3.json`
- `quality.jsonl`

---

## Proposed Future Judge Artifact

A future artifact name is **proposed**, not produced in Slice 141.

Recommended name:

```
quality_safety_offline_judge_report.json
```

- The exact name is **proposed**, not produced in Slice 141 (nothing writes it).
- `advisory=true`.
- non-blocking initially.
- not exposed as a final user-facing score until calibrated.
- not used for repair (`repair_ready=false`).
- when it later exists, it is a job-local, sanitized, closed-vocabulary artifact —
  it never carries raw guide/source/reference text or any forbidden content above.

---

## Output Shape

A closed/sanitized output shape with **no raw rationale**. Suggested top-level
fields:

```
version
kind=quality_safety_offline_judge_report
advisory=true
status            : ok | warning | skipped | partial | failed
judge_model_kind  : synthetic | local_offline | operator_assisted | unknown
input_scope       : synthetic | private_runtime | unknown
summary
axis_results
blockers
warnings
calibration_status
privacy_status
deterministic_floor_status
```

`summary`, `blockers`, and `warnings` are closed-vocabulary/count-only — token
lists and counts, never raw snippets.

Suggested axes:

- `correctness`
- `completeness`
- `source_grounding`
- `structure_and_study_value`
- `math_numeric_safety`
- `leakage_privacy_safety`
- `citation_traceability`
- `exam_readiness`

For each axis (closed-vocabulary, count-only — no raw snippets):

```
status      : pass | warning | fail | not_observed | not_applicable
confidence  : high | medium | low | unknown
score_band  : strong | acceptable | weak | failed | unknown
counts      : closed-vocabulary counts only (e.g. observation/finding counts)
```

**Default: no free-text rationales.** Free-text rationales are not part of the
committed contract. If a future test ever needs them, they are constrained to
**synthetic-only** fixtures and are **never** committed from private/runtime runs.
The safer default — and the one this contract adopts — is no free-text rationales
in any committed record.

---

## Calibration Requirements

The judge cannot be trusted until calibrated. The minimum calibration gate must
require:

- synthetic sanity cases pass
- `clean_real_case` closed-vocabulary operator result
- `single_confident_wrong_numeric_case` closed-vocabulary operator result
- `legacy_confused_wrong_case` closed-vocabulary operator result
- leak canary rejection (synthetic canary stripped, no raw fields survive)
- the deterministic safety floor must remain passing throughout
- no raw/private material in any committed calibration record

Closed vocabulary:

```
calibration_status: not_started | synthetic_only | operator_validated | failed | blocked

judge_ready: false  (stays false until calibration_status=operator_validated AND a
                     later, separate gate explicitly approves it)

repair_ready: false
```

`judge_ready` cannot be flipped true by this contract, by reaching
`synthetic_only`, or by reaching `operator_validated` alone — a later, separately
designed gate must approve it.

---

## Relationship to Deterministic Safety Floor

- The deterministic safety floor remains the **source of truth** for hard
  deterministic blockers (recompute blockers, leak blockers).
- The judge **cannot override** recompute blockers.
- The judge **cannot override** leak blockers.
- The judge **cannot** mark a guide shippable if the deterministic safety floor is
  red (`shippable` / `safety_floor_green` stay owned by the deterministic surface).
- The judge can only add **advisory** quality findings, and only **after**
  calibration.
- The judge **cannot fabricate facts** from structural coverage metadata; structural
  coverage stays separate from the numeric leg and never produces numeric
  observations.

The frozen deterministic surface (`docs/QUALITY_SAFETY_SURFACE_FREEZE.md`) is **not
unfrozen** by this contract. No numeric schema/bridge layer is added.

---

## Future Implementation Slices

Proposed next judge-path slices (conservative; each separately designed/approved):

- **Slice 142 — Offline Judge Schema Fixtures and Synthetic Harness** — schema +
  synthetic fixtures + a pure schema/text harness; no judge core, no provider calls.
- **Slice 143 — Offline Judge Core v1, Synthetic Only** — judge core wired to
  synthetic fixtures only; no private input, no provider/cloud calls.
- **Slice 144 — Judge Calibration Gate / Golden Protocol** — closed-vocabulary
  golden calibration protocol; deterministic floor must stay green.
- **Slice 145 — Private Operator Judge Calibration Pass** — operator runs
  calibration on private/local material at runtime; only closed-vocabulary results
  committed.
- **Slice 146 — Advisory Offline Judge Artifact v1** — produce the advisory
  `quality_safety_offline_judge_report.json` (non-blocking), only if calibration
  passed.

If the project needs one more cleanup/consolidation slice before implementation
begins, insert it before Slice 142 — a small surface-consolidation pass is cheap
and keeps the judge path easy to reason about.

---

## Decision Record

Closed vocabulary:

```
offline_judge_contract_status: ready
future_judge_artifact_name: quality_safety_offline_judge_report_json
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: offline_judge_schema_fixtures_and_synthetic_harness
```

Conservative stance:

- Contract ready **can** be true.
- Judge ready **must** remain false.
- Repair ready **must** remain false.

---

## Slice 142 — Schema fixtures + synthetic harness status (implemented, synthetic-only)

Slice 142 implemented this contract as a **pure schema module** plus **synthetic
fixtures** and a **synthetic harness** — not judge execution. No judge core, no
judge calls, no provider/model/cloud/local-LLM calls, no `quality_judge.py`, no
`nn3.json`, no `judge_response_nn3.json`, no `quality.jsonl`, no repair, no prompt
tuning, no production wiring, no UI, and no blocking gate were added.

- **Module:** `pipeline/quality_safety_offline_judge_schema.py` (pure; stdlib-only;
  no file I/O; no provider/model/cloud/local-LLM calls). Public functions:
  `build_empty_offline_judge_report`, `normalize_offline_judge_report`,
  `validate_offline_judge_report`, `build_synthetic_offline_judge_fixture`,
  `serialize_offline_judge_report`.
- **Output `kind`:** `quality_safety_offline_judge_report`. **Proposed future
  artifact name (not produced):** `quality_safety_offline_judge_report.json`.
- **Sanitized by construction:** output is rebuilt from a closed whitelist; the
  forbidden committed content listed above cannot survive. `advisory` is forced
  `true`; `judge_ready` and `repair_ready` are forced `false`;
  `calibration_status=operator_validated` is downgraded to `synthetic_only`.
- **Synthetic fixtures:** `clean_synthetic_judge_case`, `weak_synthetic_judge_case`,
  `failed_synthetic_judge_case`, `leak_canary_synthetic_judge_case`,
  `deterministic_floor_red_synthetic_judge_case`.
- **Synthetic harness:** `test_scripts/validate_quality_safety_offline_judge_synthetic_harness.py`
  (runs fixtures, normalizes/validates, checks deterministic serialization,
  no-canary survival, forced false readiness, floor-red can never become
  shippable/ready; prints closed-vocabulary summary only; writes no files).
- **Deterministic floor remains source of truth:** a synthetic
  `deterministic_floor_status=blocked` case yields a `deterministic_floor_red`
  blocker and a non-`ok` status; a floor-red payload overrides a softer
  self-reported floor status.

```
offline_judge_schema_status: ok
synthetic_fixture_status: ok
leak_safety_status: ok
deterministic_floor_relationship_status: ok
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: offline_judge_core_v1_synthetic_only
docker_compose_config_run: false
```

---

## Slice 143 — Offline judge core v1 status (implemented, synthetic-only)

Slice 143 implemented a **pure offline judge core**
(`pipeline/quality_safety_offline_judge_core.py`) that converts caller-supplied
**closed observations** (synthetic, in this slice) into this contract's report
shape using **deterministic rules only** — not an LLM judge, not production
wiring, and never inspecting real guide/source/reference text. No judge calls, no
provider/model/cloud/local-LLM calls, no `quality_judge.py`, no `nn3.json`, no
`judge_response_nn3.json`, no `quality.jsonl`, no repair, no prompt tuning, no UI,
and no blocking gate were added.

- **Public functions:** `build_offline_judge_report_from_observations`,
  `normalize_offline_judge_observations`,
  `build_synthetic_offline_judge_observations`, `run_synthetic_offline_judge_case`,
  `build_empty_offline_judge_core_result`. Imports only the Slice 142 schema
  module + stdlib `typing`; no file I/O; no provider/model/cloud/local-LLM calls.
- **Deterministic axis rules:** `fail_count>0 → fail/failed`; else `warning_count>0
  → warning` (weak band when confidence low/unknown, else acceptable); else
  `pass_count>0 → pass` (strong when confidence high, else acceptable); else
  `not_observed/unknown`. Every report is passed through the Slice 142 normalizer,
  so `advisory=true`, `judge_ready=false`, `repair_ready=false`, and forbidden
  content is stripped by construction.
- **Floor remains source of truth:** a floor-red `deterministic_floor_payload`
  yields a `deterministic_floor_red` blocker and a non-`ok` status even when all
  axes pass; `privacy_status=failed` yields `privacy_failed`; a failing axis yields
  `axis_failed`. The core cannot mark anything shippable or operator-validated.
- **Synthetic cases:** `clean_synthetic_judge_case`, `weak_synthetic_judge_case`,
  `failed_synthetic_judge_case`, `leak_canary_synthetic_judge_case`,
  `deterministic_floor_red_synthetic_judge_case`.
- **Harness:** `test_scripts/validate_quality_safety_offline_judge_core_synthetic.py`
  (closed-vocabulary summary; writes no files; exits nonzero on failure).

```
offline_judge_core_status: ok
synthetic_case_status: ok
schema_compatibility_status: ok
leak_safety_status: ok
deterministic_floor_relationship_status: ok
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: judge_calibration_gate_golden_protocol
docker_compose_config_run: false
```
