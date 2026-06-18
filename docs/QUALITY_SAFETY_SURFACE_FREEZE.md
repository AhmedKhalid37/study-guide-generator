# Quality Safety — Surface Freeze (Slice 140)

> Single consolidated freeze summary for the deterministic (non-judge) Quality
> Safety surface. Closed-vocabulary only. No raw artifacts, no private material, no
> judge, no repair, no production wiring, no prompt tuning. The repo/code is the
> source of truth; this doc lists what is frozen and points at the design/validation
> docs that hold the detail.

---

## Purpose

The deterministic Quality Safety surface grew across many slices (Slices 118–139)
into several scattered design and validation docs. Slice 139's deterministic safety
floor final gate decided the surface is `ready_for_cleanup_freeze`. Slice 140
**freezes** it and gives one place to reason about it before Slice 141 begins
**Offline Judge Contract Design**.

This is a **docs / test-surface cleanup slice only**. It adds **no** new Quality
Safety feature, **no** new numeric schema/bridge layer, **no** judge scoring, **no**
repair, and **no** prompt tuning. No production code changed
(`quality_safety_job_artifact.py`, `run_markdown_job.py`, `api/server.py` unchanged).

The whole Quality Safety surface remains **advisory, never blocking**: nothing here
blocks generation, export, or any user-facing path. A recompute "blocker" only makes
the advisory artifact's `shippable` / `safety_floor_green` go red.

---

## Frozen artifact names

The advisory artifact and the (caller-supplied, job-local, read-only) numeric input
sidecars are frozen at these exact names:

- `quality_safety_unified_qa.json` — the advisory job artifact (`kind=quality_safety_job_artifact`, `advisory=true`)
- `quality_safety_numeric_extraction_records.json` — explicit sanitized numeric records input
- `quality_safety_safe_numeric_candidates.json` — safe numeric candidates input
- `quality_safety_structured_numeric_candidates.json` — structured numeric candidates input

Production code never **creates or commits** the numeric input sidecars; numeric
verification only runs when a caller already supplies sanitized records/candidates.

---

## Frozen field families

The closed field families produced/consumed by the surface are frozen:

- `extraction_coverage_*` — structural extraction coverage (kept separate from the numeric leg)
- `numeric_extraction_*` — explicit numeric extraction records path
- `safe_numeric_extractor_*` — safe numeric candidates path
- `structured_numeric_candidate_adapter_*` — structured numeric candidates adapter path
- `operator_structured_numeric_export_validation` — operator export protocol/validator path
- `deterministic_floor_final_gate` — Slice 139 aggregate gate

Deterministic numeric precedence is frozen as **explicit records > safe candidates >
structured candidates** (a correct higher-precedence input wins over wrong
lower-precedence ones).

---

## Frozen validation harnesses

These nine harnesses define the frozen, reproducible synthetic validation surface:

- `validate_quality_safety_deterministic_floor_final_gate.py`
- `validate_quality_safety_operator_structured_numeric_export.py`
- `validate_quality_safety_real_disaster_e2e.py`
- `test_quality_safety_operator_structured_numeric_export_validator.py`
- `test_quality_safety_structured_numeric_candidate_adapter.py`
- `test_quality_safety_safe_numeric_extractor.py`
- `test_quality_safety_job_artifact.py`
- `test_quality_safety_recompute_verifier.py`
- `test_quality_safety_unified_qa.py`

All are synthetic/deterministic, read no private input, write no output files, and
print closed-vocabulary results only.

---

## Frozen non-goals

The following stay out of scope and are not added by freezing the surface:

- no judge scoring yet
- no repair
- no prompt tuning
- no production numeric extractor claim
- no private sidecar commit
- no raw text / formulas / evidence / paths / provider payloads in committed records
- no blocking gate
- no new numeric schema/bridge layers unless a real blocker appears

---

## Known limitations

- The operator waiver is **synthetic-only**
  (`operator_numeric_export_waiver=approved_for_safety_floor_finalization_synthetic_only`);
  no private/local operator run was performed or committed.
- `production_numeric_extractor_present` remains the sidecar / structured-sidecar /
  operator-approved path only. **Production numeric extraction coverage is NOT
  complete** and is not claimed to be — no production code reads source/OCR/table
  text or writes numeric/safe/structured sidecars.
- `judge_ready=false` — no judge contract/core exists yet.
- `repair_ready=false` — no repair is implemented or planned in this slice.
- `judge_contract_ready=true` means **only** that the offline judge **contract** may
  now be **designed** — it does not mean a judge exists.

---

## Next allowed phase

- `offline_judge_contract_design` (Slice 141) — **design only**, not implementation.
  Judge scoring, repair, prompt tuning, and any new numeric infrastructure remain out
  of scope until separately and explicitly designed.

---

## Pointers (detail lives in these docs)

- `docs/QUALITY_SAFETY_DETERMINISTIC_FLOOR_FINAL_GATE.md` — Slice 139 aggregate gate
- `docs/QUALITY_SAFETY_E2E_VALIDATION.md` — end-to-end synthetic validation records
- `docs/QUALITY_SAFETY_OPERATOR_VALIDATION.md` — operator/waiver status
- `docs/QUALITY_SAFETY_OPERATOR_STRUCTURED_NUMERIC_EXPORT_PROTOCOL.md` — operator export protocol
- `docs/QUALITY_SAFETY_STRUCTURED_NUMERIC_CANDIDATE_PRODUCER_DESIGN.md` — structured candidate producer design
- `docs/QUALITY_SAFETY_FUTURE_STRUCTURED_NUMERIC_ARTIFACT_DESIGN.md` — future structured artifact design
- `docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md` — numeric extraction record contract
- `docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md` — safe numeric extractor design

---

## Explicit status

```
deterministic_safety_floor_status: ready_for_cleanup_freeze
numeric_infrastructure_frozen: true
quality_safety_surface_frozen: true
quality_safety_blocking: false
operator_numeric_export_waiver: approved_for_safety_floor_finalization_synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: offline_judge_contract_design
```

---

## Slice 141 — Offline judge contract design has begun (surfaces stay frozen)

Slice 141 began **Offline Judge Contract Design** (design only) in
`docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`. Designing the judge contract does
**not** unfreeze the numeric infrastructure or the deterministic surface: no judge
core, no judge calls, no provider/model/cloud/local-LLM calls, no repair, no prompt
tuning, no new numeric schema/bridge layer were added. The frozen artifact names,
field families, and validation harnesses above are unchanged.

The future offline judge — once built and calibrated — is advisory and layered on
top of this frozen surface; it can never override a deterministic recompute/leak
blocker, never mark a guide shippable if the floor is red, and never fabricate facts
from structural coverage. The proposed (not produced) future artifact is
`quality_safety_offline_judge_report.json`.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
offline_judge_contract_status: ready
future_judge_artifact_name: quality_safety_offline_judge_report_json
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: offline_judge_schema_fixtures_and_synthetic_harness
```

---

## Slice 142 — Schema fixtures do not unfreeze the deterministic / numeric surfaces

Slice 142 added a **pure** offline judge schema module
(`pipeline/quality_safety_offline_judge_schema.py`), synthetic fixtures, and a
synthetic harness. This proves the future judge report shape using **synthetic data
only**; it does **not** unfreeze the numeric infrastructure or the deterministic
surface. No judge core, no judge calls, no provider/model/cloud/local-LLM calls, no
repair, no prompt tuning, and no new numeric schema/bridge layer were added. The
frozen artifact names, field families, and validation harnesses above are unchanged,
and nothing in production imports the new schema module.

The future offline judge — once built and calibrated — stays advisory and layered on
top of this frozen surface; it can never override a deterministic recompute/leak
blocker, never mark a guide shippable if the floor is red, and never fabricate facts
from structural coverage. The proposed (not produced) future artifact remains
`quality_safety_offline_judge_report.json`.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
offline_judge_schema_status: ok
future_judge_artifact_name: quality_safety_offline_judge_report_json
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: offline_judge_core_v1_synthetic_only
```

---

## Slice 143 — Synthetic offline judge core does not unfreeze any surface

Slice 143 added a **pure** offline judge core
(`pipeline/quality_safety_offline_judge_core.py`) that converts caller-supplied
**synthetic closed observations** into the Slice 142 report shape using
deterministic rules only. This does **not** unfreeze the numeric infrastructure or
the deterministic surface, and adds **no** numeric schema/bridge layer. No judge
calls, no provider/model/cloud/local-LLM calls, no repair, and no prompt tuning
were added; nothing in production imports the core. The frozen artifact names,
field families, and validation harnesses above are unchanged.

The core stays advisory and layered on top of this frozen surface: it can never
override a deterministic recompute/leak/floor blocker, never mark a guide
shippable if the floor is red, and never fabricate facts from structural coverage.
The proposed (not produced) future artifact remains
`quality_safety_offline_judge_report.json`.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
offline_judge_core_status: ok
future_judge_artifact_name: quality_safety_offline_judge_report_json
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: judge_calibration_gate_golden_protocol
```

---

## Slice 144 — Calibration gate protocol does not unfreeze any surface

Slice 144 added the **judge calibration gate / golden protocol**
(`docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`), a docs/protocol-only
slice. Defining the calibration gate does **not** unfreeze the deterministic
surface or the numeric infrastructure, and adds **no** numeric schema/bridge
layer. No production code changed; no judge ran; no provider/model/cloud/local-LLM
call was added. The frozen artifact names, field families, and validation
harnesses above remain unchanged, and the deterministic safety floor stays the
source of truth. The future judge stays advisory and non-blocking; even after
calibration it cannot override deterministic blockers unless a later explicit
policy decision changes it.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
judge_calibration_gate_protocol_status: ready
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: private_operator_judge_calibration_pass
```

---

## Slice 145 — Calibration gate harness does not unfreeze any surface

Slice 145 added the closed-record calibration gate harness
(`test_scripts/validate_quality_safety_judge_calibration_gate.py`), a test/docs-only
slice. Exercising the calibration gate over synthetic golden cases does **not**
unfreeze the deterministic surface or the numeric infrastructure, and adds **no**
numeric schema/bridge layer. No production code changed; no judge ran on private
material; no provider/model/cloud/local-LLM call was added; no private calibration
was run (`private_operator_judge_calibration_run=not_run`). The frozen artifact
names, field families, and validation harnesses above remain unchanged, and the
deterministic safety floor stays the source of truth. The future judge stays
advisory and non-blocking.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
judge_calibration_gate_protocol_status: ready
private_operator_judge_calibration_run: not_run
calibration_gate_harness_status: ok
calibration_status: synthetic_only
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: advisory_judge_artifact_design_or_stop_for_private_calibration
```

---

## Slice 146 — Advisory artifact design does not unfreeze any surface

Slice 146 (docs/design-only) adds
`docs/QUALITY_SAFETY_ADVISORY_OFFLINE_JUDGE_ARTIFACT_DESIGN.md`. Designing the future
advisory offline judge report artifact does **not** unfreeze the deterministic
surface or the numeric infrastructure, adds **no** numeric schema/bridge layer, adds
**no** new artifact name, schema kind, or field, and relaxes **no** forbidden-field
family. No production code changed; no artifact was written; no judge ran; no
provider/model/cloud/local-LLM call was added. The frozen artifact names, field
families, and validation harnesses above remain unchanged, and the deterministic
safety floor stays the source of truth. The future judge stays advisory and
non-blocking.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
advisory_judge_artifact_design_status: ready
artifact_write_ready: false
ui_display_ready: false
calibration_status: synthetic_only
private_operator_judge_calibration_run: not_run
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: advisory_offline_judge_artifact_schema_adapter_or_stop_for_private_calibration
```

---

## Slice 147 — Advisory artifact schema adapter does not unfreeze any surface

Slice 147 adds a pure, unwired artifact schema adapter
(`pipeline/quality_safety_offline_judge_artifact_adapter.py`) plus synthetic tests.
The adapter reuses the Slice 142 normalizer verbatim and does **not** unfreeze the
deterministic surface or the numeric infrastructure, adds **no** numeric schema/bridge
layer, adds **no** new artifact name, schema kind, or field, and relaxes **no**
forbidden-field family. It writes no artifact, wires nothing into production, and
calls no provider/model/cloud/local LLM. The frozen artifact names, field families,
and validation harnesses remain unchanged, and the deterministic safety floor stays
the source of truth. The future judge stays advisory and non-blocking.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
advisory_judge_artifact_adapter_status: ok
artifact_shape_ready: true
artifact_write_ready: false
ui_display_ready: false
calibration_status: synthetic_only
private_operator_judge_calibration_run: not_run
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: advisory_offline_judge_artifact_writer_design_or_stop_for_private_calibration
```
