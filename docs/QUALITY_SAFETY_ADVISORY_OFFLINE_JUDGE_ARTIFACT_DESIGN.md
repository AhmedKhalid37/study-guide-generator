# Quality Safety Advisory Offline Judge Artifact Design

> Slice 146 — **design-only.** This document designs how a *future* advisory
> offline judge report artifact may be stored and surfaced after calibration,
> without making it blocking or trusted prematurely. It implements nothing: no
> artifact writing, no production wiring, no UI, no judge execution, no
> provider/model/cloud/local-LLM call, no repair, no prompt tuning. The
> deterministic safety floor remains the source of truth, and the future judge
> stays advisory and non-blocking. Closed vocabulary only; no real/private
> material, filenames, paths, or snippets appear here.

## Purpose

Design how a future advisory offline judge report artifact may be stored and
surfaced after calibration, without making it blocking or trusted prematurely.

This design does not implement artifact writing.

It builds on the closed-vocabulary surface already proven by:

- the offline judge contract (`docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`);
- the Slice 142 schema (`pipeline/quality_safety_offline_judge_schema.py`);
- the Slice 143 offline judge core (`pipeline/quality_safety_offline_judge_core.py`);
- the Slice 144 calibration gate / golden protocol
  (`docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`);
- the Slice 145 calibration gate harness
  (`test_scripts/validate_quality_safety_judge_calibration_gate.py`).

## Preconditions

Use closed vocabulary:

```
deterministic_safety_floor_status: ready_for_cleanup_freeze
numeric_infrastructure_frozen: true
offline_judge_contract_status: ready
offline_judge_schema_status: ok
offline_judge_core_status: ok
judge_calibration_gate_protocol_status: ready
calibration_status: synthetic_only
private_operator_judge_calibration_run: not_run
judge_contract_ready: true
judge_ready: false
repair_ready: false
```

## Proposed Artifact

Exact proposed artifact name:

```
quality_safety_offline_judge_report.json
```

Kind:

```
quality_safety_offline_judge_report
```

(Matches the Slice 142 schema `KIND` and the contract; this design proposes no new
artifact name and no new schema `kind`.)

Artifact boundary:

- `advisory=true`
- `non_blocking`
- `not_user_score`
- `not_repair_input`
- `not_shippability_source`
- `not_deterministic_floor_override`
- `hidden_or_internal_until_calibrated`

## Integration Boundary

Future allowed integration:

- optional job-local artifact after the offline judge core/report is produced;
- read-only UI display only after calibration policy allows;
- docs/operator validation may record closed outcomes only.

Forbidden integration:

- no blocking gate;
- no shippable override;
- no recompute override;
- no leak override;
- no repair trigger;
- no prompt tuning trigger;
- no raw rationale display from private jobs;
- no raw model prompt/response storage;
- no provider payload storage;
- no generic artifact export of private judge raw outputs.

## Storage Rules

Allowed committed/runtime-safe fields:

- fields from the Slice 142 schema only;
- closed axis statuses;
- confidence tokens;
- score_band tokens;
- count-only summaries;
- closed blockers;
- closed warnings;
- `calibration_status`;
- `privacy_status`;
- `deterministic_floor_status`.

Forbidden stored fields:

- source text;
- guide text;
- OCR/page/table/caption text;
- `formulas_as_text`;
- evidence quotes;
- filenames;
- basenames;
- paths;
- URLs;
- screenshots;
- raw runtime artifacts;
- raw artifact JSON from private jobs;
- provider payloads;
- model prompts;
- model responses;
- private rationales;
- free-text rationales;
- `chain_of_thought`;
- `quality_judge.py` dumps;
- `nn3.json`;
- `judge_response_nn3.json`;
- `quality.jsonl`.

(These forbidden field families already match the Slice 142 schema
`FORBIDDEN_FIELDS` set, which the normalizer never copies; this design adds no new
field and relaxes none.)

## Display Policy

Future UI display is allowed only after a later slice decides:

- `calibration_status` is sufficient;
- `privacy_status` is ok;
- the deterministic floor relationship is enforced;
- no raw/private rationale fields exist.

Until then:

- no UI display;
- no user-facing score;
- no grade-like overall score;
- no repair suggestions.

## Readiness

Use closed vocabulary:

```
advisory_judge_artifact_design_status=ready
artifact_write_ready=false
ui_display_ready=false
judge_ready=false
repair_ready=false
next_step=advisory_offline_judge_artifact_schema_adapter_or_stop_for_private_calibration
```

Conservative posture:

- Artifact design ready can be true (`advisory_judge_artifact_design_status=ready`).
- Artifact write ready must remain false (`artifact_write_ready=false`).
- UI display ready must remain false (`ui_display_ready=false`).
- Judge ready must remain false (`judge_ready=false`).
- Repair ready must remain false (`repair_ready=false`).

## Proposed Next Slice

Choose the next step conservatively.

**Option A — recommended if continuing without private data:**
Slice 147 — Advisory Offline Judge Artifact Schema Adapter, Synthetic Only.
Purpose:

- pure/unwired adapter that accepts normalized offline judge reports and verifies
  write-ready shape synthetically;
- no production writing;
- no UI;
- no private input;
- no `judge_ready=true`.

**Option B — Stop for Private Operator Calibration.**
Purpose:

- perform closed-record private calibration before continuing toward artifact
  wiring.

Recommended if continuing without private data: **Slice 147 — Advisory Offline
Judge Artifact Schema Adapter, Synthetic Only.**
