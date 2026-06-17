# Quality Safety — Deterministic Safety Floor Final Gate (Slice 139)

> Closed-vocabulary record for the final deterministic gate on the non-judge
> Quality Safety surface. Synthetic-only. No raw artifacts, no private material,
> no judge, no repair, no production wiring. The repo/code is the source of truth;
> this doc summarizes the gate harness
> `test_scripts/validate_quality_safety_deterministic_floor_final_gate.py`.

---

## Purpose

Slice 139 is the **final deterministic gate** for the Quality Safety Unit. It
aggregates the deterministic components built across Slices 118–138 and decides —
on synthetic fixtures only — whether the deterministic safety floor is ready to be
**frozen** so the project can move to cleanup/freeze and then offline judge-contract
design.

This is **not** a judge slice. It adds **no** judge scoring, **no** repair, **no**
prompt tuning, **no** new numeric schema/bridge layer, and **no** production wiring.
It imports and drives the existing pure components and the two existing Quality
Safety harnesses, and prints a **closed-vocabulary summary only**.

The gate harness:
- has **no private/local input mode** (synthetic-only),
- reads **no** input files and writes **no** output files,
- makes **no** provider / model / cloud / judge / repair calls,
- imports **no** FastAPI / frontend / render / OCR code,
- parses **no** source documents, reads **no** `clean.md` as a numeric source,
  scans **no** job folders,
- exits **non-zero** if any deterministic prerequisite fails.

---

## Prerequisites checked

Each prerequisite resolves to a closed token (`ok` | `blocked`). The gate is
`ready_for_cleanup_freeze` only when **all** are `ok` and no check failed.

1. **artifact_contract_status** — the advisory artifact payload shape is unchanged
   through the synthetic builder path: `kind=quality_safety_job_artifact`,
   `advisory=true`, exact artifact name `quality_safety_unified_qa.json`, and the
   embedded `quality_safety_unified_qa` payload is present.
2. **leak_safety_status** — a synthetic forbidden canary smuggled into forbidden
   candidate fields is stripped/blocked through the operator validator and the
   advisory artifact builder; **no** raw forbidden field and **no** canary survives
   into any final payload or summary.
3. **recompute_status** — a clean synthetic numeric case passes recompute (shippable);
   a wrong synthetic numeric case raises a recompute **blocker** and goes
   not-shippable.
4. **numeric_path_status** — the explicit-records path, the safe-candidates path,
   the structured-candidates path, and the operator-validator output path all work;
   the deterministic precedence **explicit records > safe candidates > structured
   candidates** holds (a correct higher-precedence input wins over wrong lower
   ones).
5. **structural_coverage_status** — structural extraction coverage stays **separate**
   from the numeric leg: with coverage present but no numeric inputs, the numeric
   recompute leg stays honestly missing, no numeric observation is fabricated from
   coverage counts, and no false recompute blocker appears.
6. **operator_export_harness_status** — the Slice 138 synthetic operator export
   harness passes in isolation (exit 0, no canary leak); the operator numeric export
   waiver is recorded as **synthetic-only**.
7. **real_disaster_synthetic_status** — the core real-disaster synthetic cases
   reproduce:
   - `single_confident_wrong_numeric_case = failed_blocking`
   - `clean_real_case = passed`
   - `legacy_confused_wrong_case = partial`
8. **ui_display_status** — the advisory UI/panel display is **already covered by the
   existing** pure node verify harness
   (`frontend/scripts/verify-guide-quality-panel.mjs`); Slice 139 adds **no**
   frontend change and does not re-run node — the status is documented, not
   measured (`already_covered_by_existing_verify`).

---

## Final gate outcome (synthetic, closed-vocabulary)

```
validation_id: quality_safety_deterministic_floor_final_gate
deterministic_safety_floor_status: ready_for_cleanup_freeze
artifact_contract_status: ok
leak_safety_status: ok
recompute_status: ok
numeric_path_status: ok
structural_coverage_status: ok
operator_export_harness_status: ok
real_disaster_synthetic_status: ok
real_disaster_cases:
  clean_real_case: passed
  single_confident_wrong_numeric_case: failed_blocking
  legacy_confused_wrong_case: partial
ui_display_status: already_covered_by_existing_verify
operator_numeric_export_waiver: approved_for_safety_floor_finalization_synthetic_only
numeric_infrastructure_frozen: true
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: quality_safety_surface_cleanup_freeze
```

Harness result: **34 passed, 0 failed.** Companion suites all green: operator
export harness (35), operator export validator (422), structured candidate adapter
(177), safe numeric extractor (207), job artifact (753), recompute verifier (99),
real-disaster e2e (100), unified QA (73). `compileall` clean; `git diff --check`
clean. No Docker required (test/docs only); no `docker compose config` run.

---

## What is frozen

- **The numeric infrastructure is frozen.** No further numeric schema/bridge layers
  will be added before the judge path unless a real blocker appears. The layered
  numeric chain (extraction records → safe candidates → structured candidates →
  operator export protocol → pure operator export validator → operator export
  validation harness) plus the adapter, safe extractor, mapper, fact-sheet producer,
  and recompute verifier are considered complete-enough and stable.
- **The deterministic safety floor is frozen** at `ready_for_cleanup_freeze`: the
  advisory artifact contract, leak-scan/no-leak rules, recompute verifier,
  fact-sheet/numeric extraction path, structural extraction coverage, safe numeric
  extractor, structured numeric candidate adapter, operator structured export
  validator, the operator export validation harness/synthetic-only waiver, and the
  real-disaster synthetic E2E are all aggregated and passing.

## What is not frozen

- The **offline judge contract** (not yet designed). `judge_contract_ready=true`
  records only that the deterministic floor is ready enough to begin **designing**
  that contract — it does **not** mean a judge exists.
- The **Quality Safety surface cleanup/freeze** slice (Slice 140) — the next step.

---

## Remaining limitations

- **Synthetic-only.** Every prerequisite is proven on synthetic fixtures. No
  private/local operator run was performed or committed
  (`operator_numeric_export_waiver=approved_for_safety_floor_finalization_synthetic_only`).
- **Advisory, never blocking.** Nothing in the Quality Safety surface blocks
  generation, export, or any user-facing path. The recompute "blocker" only makes
  the advisory artifact's `shippable` / `safety_floor_green` go red.
- **No production numeric extraction.** No production code reads source/OCR/table
  text or writes numeric/safe/structured sidecars. Numeric verification only runs
  when a caller already supplies sanitized records/candidates. **Production numeric
  extraction coverage is NOT complete** and is not claimed to be.
- **No judge, no repair.** This gate measures only the deterministic floor.

---

## Explicit status

- **`judge_ready=false`** — no judge contract/core exists yet; the judge baseline
  stays blocked.
- **`repair_ready=false`** — no repair is implemented or planned in this slice.
- **Next step is cleanup/freeze before the judge contract:**
  `next_step=quality_safety_surface_cleanup_freeze` (Slice 140 — Quality Safety
  Surface Cleanup / Freeze). The offline judge contract is designed only **after**
  cleanup/freeze.

## Slice 140 Surface Freeze

Slice 140 froze the deterministic (non-judge) Quality Safety surface (docs /
test-surface cleanup only; no production code change) and consolidated the freeze
list into a single summary, `docs/QUALITY_SAFETY_SURFACE_FREEZE.md`. This doc is
**unchanged** in substance and is now one of the frozen pointers; the numeric
infrastructure stays frozen.

```
quality_safety_surface_frozen: true
numeric_infrastructure_frozen: true
this_doc_changed: false
freeze_summary: docs/QUALITY_SAFETY_SURFACE_FREEZE.md
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: offline_judge_contract_design
```

## Slice 141 Relationship to the Future Offline Judge

Slice 141 designed the offline judge contract
(`docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`, design only). This final gate
**remains the source of truth** for hard deterministic blockers. The future offline
judge is advisory and subordinate: it **cannot** override the recompute or leak
blockers measured here, **cannot** mark a guide shippable if this floor is red, and
**cannot** fabricate facts from structural coverage. It may only add advisory
quality findings, and only after a separate calibration gate approves it.

```
deterministic_floor_is_source_of_truth: true
judge_can_override_deterministic_blockers: false
offline_judge_contract_status: ready
judge_contract_ready: true
judge_ready: false
repair_ready: false
next_step: offline_judge_schema_fixtures_and_synthetic_harness
```
