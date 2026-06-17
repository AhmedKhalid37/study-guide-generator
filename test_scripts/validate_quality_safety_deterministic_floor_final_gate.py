#!/usr/bin/env python3
"""Slice 139 — Quality Safety Deterministic Safety Floor Final Gate (synthetic).

This is the final deterministic gate for the non-judge Quality Safety surface. It
aggregates the deterministic components already built (Slices 118–138) and decides,
on synthetic fixtures only, whether the deterministic safety floor is ready to be
frozen so the project can move to cleanup/freeze and then offline judge-contract
design.

THIS IS NOT A JUDGE SLICE. It adds no judge scoring, no repair, no prompt tuning,
no new numeric schema/bridge layer, and no production wiring. It imports and drives
the existing pure components and the two existing Quality Safety harnesses, and
prints a **closed-vocabulary summary only** (no raw values, no source/guide/OCR/
table/caption text, no paths, no raw records, no exception text).

Prerequisites checked (closed-vocabulary statuses):
  1. artifact_contract_status        — advisory ``quality_safety_unified_qa.json`` shape unchanged
  2. leak_safety_status              — forbidden synthetic canary stripped, no raw fields survive
  3. recompute_status                — clean passes, wrong recompute-blocks
  4. numeric_path_status             — explicit > safe > structured precedence + operator validator path
  5. structural_coverage_status      — coverage stays separate, never fabricates numeric records
  6. operator_export_harness_status  — Slice 138 synthetic harness passes; waiver synthetic-only
  7. real_disaster_synthetic_status  — core disaster cases reproduce (failed_blocking / passed / partial)
  8. ui_display_status               — already covered by the existing guide-quality panel verify
  9. readiness decision              — closed-vocabulary final gate

Hard guarantees: stdlib + existing Quality Safety modules/harnesses only; no
provider / model / cloud / judge / repair calls; no FastAPI / frontend / render /
OCR imports; no source-document parsing; no ``clean.md`` reads as a numeric source;
no job-folder scanning; no input files read; writes no output files; no production
wiring. Exits non-zero if any deterministic prerequisite fails.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_job_artifact import (  # noqa: E402
    ARTIFACT_NAME,
    KIND,
    build_quality_safety_job_artifact_payload,
)
from test_scripts.validate_quality_safety_operator_structured_numeric_export import (  # noqa: E402
    SYNTHETIC_CANARY,
    _forbidden_field_candidate,
    _operator_candidate,
    _operator_export,
    run_export_validation as run_operator_export,
    run_synthetic as run_operator_export_synthetic,
)
from test_scripts.validate_quality_safety_real_disaster_e2e import (  # noqa: E402
    candidate_markdown,
    fixture_spec,
    numeric_records,
    structured_candidates,
    synthetic_coverage_artifacts,
    weighted_bundle,
)

VALIDATION_ID = "quality_safety_deterministic_floor_final_gate"
ARTIFACT_NAME_EXACT = "quality_safety_unified_qa.json"

PASS = 0
FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        FAIL += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[FAIL] {label}{suffix}")


def _section_ok(before_fail: int) -> str:
    """Closed token: ``ok`` if no new failures occurred since ``before_fail``."""
    return "ok" if FAIL == before_fail else "blocked"


def _recompute_blocker(payload: dict[str, Any]) -> bool:
    return any(
        item.get("component") == "recompute" for item in payload.get("blocking_failures") or []
    )


def _recompute_state(payload: dict[str, Any]) -> Any:
    return payload.get("component_statuses", {}).get("recompute")


# --- 1. artifact contract ------------------------------------------------------


def check_artifact_contract() -> str:
    before = FAIL
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=numeric_records(value=0.2),
    )
    check("artifact: kind unchanged", payload.get("kind") == KIND == "quality_safety_job_artifact")
    check("artifact: exact artifact_name unchanged", payload.get("artifact_name") == ARTIFACT_NAME == ARTIFACT_NAME_EXACT)
    check("artifact: advisory true", payload.get("advisory") is True)
    check(
        "artifact: unified_qa payload shape present",
        isinstance(payload.get("quality_safety_unified_qa"), dict),
    )
    return _section_ok(before)


# --- 2. leak safety ------------------------------------------------------------


def check_leak_safety() -> str:
    before = FAIL
    # Path A: operator export carrying forbidden fields + a synthetic canary.
    op_summary = run_operator_export(
        _operator_export(candidates=[_forbidden_field_candidate()]),
        input_kind="synthetic_safe",
    )
    check("leak: operator summary canary-free", SYNTHETIC_CANARY not in json.dumps(op_summary))
    check("leak: operator forbidden flagged", "unsafe_field_excluded" in (op_summary.get("warnings") or []))

    # Path B: same forbidden payload routed through the full advisory artifact builder
    # via the operator validator's sanitized re-emission.
    from pipeline.quality_safety_operator_structured_numeric_export_validator import (
        operator_export_validation_to_structured_numeric_payload,
        validate_operator_structured_numeric_export,
    )

    validation = validate_operator_structured_numeric_export(
        _operator_export(candidates=[_forbidden_field_candidate()])
    )
    structured_payload = operator_export_validation_to_structured_numeric_payload(validation)
    artifact = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        structured_numeric_candidates=structured_payload,
    )
    check("leak: final artifact canary-free", SYNTHETIC_CANARY not in json.dumps(artifact))
    return _section_ok(before)


# --- 3. recompute --------------------------------------------------------------


def check_recompute() -> str:
    before = FAIL
    clean = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=numeric_records(value=0.2),
    )
    check("recompute: clean passes", _recompute_state(clean) == "passed", json.dumps(_recompute_state(clean)))
    check("recompute: clean shippable", clean.get("shippable") is True)
    check("recompute: clean no blocker", not _recompute_blocker(clean))

    wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        numeric_extraction_records=numeric_records(value=0.9),  # recomputes to 0.2
    )
    check("recompute: wrong fails", _recompute_state(wrong) == "failed", json.dumps(_recompute_state(wrong)))
    check("recompute: wrong blocks", _recompute_blocker(wrong))
    check("recompute: wrong not shippable", wrong.get("shippable") is False)
    return _section_ok(before)


# --- 4. numeric paths + precedence ---------------------------------------------


def check_numeric_paths() -> str:
    before = FAIL

    explicit = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=numeric_records(value=0.2),
    )
    check("numeric: explicit records path passes", _recompute_state(explicit) == "passed")

    safe = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        safe_numeric_candidates=numeric_records(value=0.2),
    )
    check("numeric: safe candidates path passes", _recompute_state(safe) == "passed", json.dumps(_recompute_state(safe)))
    check("numeric: safe extractor status closed", safe.get("safe_numeric_extractor_status") in {"passed", "warning", "ok"})

    structured = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        structured_numeric_candidates=structured_candidates(value=0.2),
    )
    check("numeric: structured candidates path passes", _recompute_state(structured) == "passed", json.dumps(_recompute_state(structured)))

    operator = run_operator_export(
        _operator_export(candidates=[_operator_candidate(value=0.2)]),
        input_kind="synthetic_safe",
    )
    check("numeric: operator validator output path passes", operator.get("recompute_status") == "passed", operator.get("recompute_status"))

    # Precedence: explicit > safe > structured. A correct explicit record must win
    # over a wrong safe candidate and a wrong structured candidate.
    explicit_wins = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=numeric_records(value=0.2),  # correct, wins
        safe_numeric_candidates=numeric_records(value=0.9),  # wrong, superseded
        structured_numeric_candidates=structured_candidates(value=0.9),  # wrong, superseded
    )
    check("precedence: explicit wins -> passes", _recompute_state(explicit_wins) == "passed", json.dumps(_recompute_state(explicit_wins)))
    check("precedence: explicit wins -> no blocker", not _recompute_blocker(explicit_wins))
    check(
        "precedence: safe superseded by explicit",
        explicit_wins.get("safe_numeric_extractor_status") == "skipped",
        str(explicit_wins.get("safe_numeric_extractor_status")),
    )

    # A correct safe candidate must win over a wrong structured candidate.
    safe_wins = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        safe_numeric_candidates=numeric_records(value=0.2),  # correct, wins
        structured_numeric_candidates=structured_candidates(value=0.9),  # wrong, superseded
    )
    check("precedence: safe wins over structured -> passes", _recompute_state(safe_wins) == "passed", json.dumps(_recompute_state(safe_wins)))
    check("precedence: safe wins -> no blocker", not _recompute_blocker(safe_wins))
    return _section_ok(before)


# --- 5. structural coverage stays separate -------------------------------------


def check_structural_coverage() -> str:
    before = FAIL
    coverage = synthetic_coverage_artifacts()
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.5),
        **coverage,
    )
    warnings = payload.get("warnings") or []
    check(
        "coverage: structural coverage present",
        payload.get("extraction_coverage_status") in {"ok", "warning", "partial"},
        str(payload.get("extraction_coverage_status")),
    )
    check(
        "coverage: numeric leg stays missing (not fabricated)",
        _recompute_state(payload) in {"unknown", "skipped"},
        json.dumps(_recompute_state(payload)),
    )
    check("coverage: recompute component honestly missing", "recompute_component_missing" in warnings)
    check(
        "coverage: no numeric observations fabricated from coverage",
        payload.get("extraction_coverage_bundle", {}).get("numeric_observations") == [],
    )
    check(
        "coverage: coverage numeric observation count 0",
        payload.get("extraction_coverage_summary", {}).get("numeric_observation_count") == 0,
    )
    check("coverage: no false recompute blocker from coverage", not _recompute_blocker(payload))
    return _section_ok(before)


# --- 6. operator export harness (Slice 138) ------------------------------------


def check_operator_export_harness() -> str:
    before = FAIL
    # Run the Slice 138 synthetic harness in isolation; suppress its stdout and use
    # only its exit code (0 == all synthetic expectations passed).
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = run_operator_export_synthetic()
    check("operator harness: synthetic suite passes", rc == 0, f"rc={rc}")
    check("operator harness: no canary in captured output", SYNTHETIC_CANARY not in buffer.getvalue())
    return _section_ok(before)


# --- 7. real-disaster synthetic core cases -------------------------------------


def check_real_disaster_synthetic() -> tuple[str, dict[str, str]]:
    before = FAIL
    coverage = synthetic_coverage_artifacts()

    clean = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        extraction_bundle=weighted_bundle(claimed=0.2),
        fixture_spec=fixture_spec(value=0.2),
        **coverage,
    )
    clean_case = "passed" if (clean.get("status") == "passed" and clean.get("shippable") is True) else "unexpected"
    check("disaster: clean_real_case passed", clean_case == "passed", json.dumps(clean.get("status")))

    wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.5),
        extraction_bundle=weighted_bundle(claimed=0.5),
        fixture_spec=fixture_spec(value=0.5),
        **coverage,
    )
    wrong_blocked = (
        wrong.get("status") == "failed"
        and wrong.get("shippable") is False
        and _recompute_blocker(wrong)
    )
    wrong_case = "failed_blocking" if wrong_blocked else "unexpected"
    check("disaster: single_confident_wrong_numeric_case failed_blocking", wrong_case == "failed_blocking", json.dumps(wrong.get("status")))

    legacy = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.5),
        **coverage,
    )
    legacy_warnings = legacy.get("warnings") or []
    legacy_partial = (
        legacy.get("extraction_coverage_status") in {"ok", "warning", "partial"}
        and "recompute_component_missing" in legacy_warnings
        and not _recompute_blocker(legacy)
    )
    legacy_case = "partial" if legacy_partial else "unexpected"
    check("disaster: legacy_confused_wrong_case partial", legacy_case == "partial", json.dumps(_recompute_state(legacy)))

    cases = {
        "clean_real_case": clean_case,
        "single_confident_wrong_numeric_case": wrong_case,
        "legacy_confused_wrong_case": legacy_case,
    }
    return _section_ok(before), cases


# --- main gate -----------------------------------------------------------------


def main() -> int:
    print("Quality Safety deterministic safety floor final gate — synthetic\n")

    artifact_contract_status = check_artifact_contract()
    leak_safety_status = check_leak_safety()
    recompute_status = check_recompute()
    numeric_path_status = check_numeric_paths()
    structural_coverage_status = check_structural_coverage()
    operator_export_harness_status = check_operator_export_harness()
    real_disaster_synthetic_status, disaster_cases = check_real_disaster_synthetic()

    # UI/panel display is already covered by the existing pure node verify harness
    # (frontend/scripts/verify-guide-quality-panel.mjs). This slice adds no frontend
    # change and does not re-run node here; the status is documented, not measured.
    ui_display_status = "already_covered_by_existing_verify"

    prerequisites = {
        "artifact_contract_status": artifact_contract_status,
        "leak_safety_status": leak_safety_status,
        "recompute_status": recompute_status,
        "numeric_path_status": numeric_path_status,
        "structural_coverage_status": structural_coverage_status,
        "operator_export_harness_status": operator_export_harness_status,
        "real_disaster_synthetic_status": real_disaster_synthetic_status,
    }
    all_ready = FAIL == 0 and all(v == "ok" for v in prerequisites.values())

    deterministic_safety_floor_status = "ready_for_cleanup_freeze" if all_ready else "blocked"
    judge_contract_ready = all_ready  # may be true only if the deterministic floor is ready
    next_step = "quality_safety_surface_cleanup_freeze" if all_ready else "stop_for_review"

    summary = {
        "validation_id": VALIDATION_ID,
        "deterministic_safety_floor_status": deterministic_safety_floor_status,
        "artifact_contract_status": artifact_contract_status,
        "leak_safety_status": leak_safety_status,
        "recompute_status": recompute_status,
        "numeric_path_status": numeric_path_status,
        "structural_coverage_status": structural_coverage_status,
        "operator_export_harness_status": operator_export_harness_status,
        "real_disaster_synthetic_status": real_disaster_synthetic_status,
        "real_disaster_cases": disaster_cases,
        "ui_display_status": ui_display_status,
        "operator_numeric_export_waiver": "approved_for_safety_floor_finalization_synthetic_only",
        "numeric_infrastructure_frozen": True,
        "judge_contract_ready": bool(judge_contract_ready),
        "judge_ready": False,
        "repair_ready": False,
        "next_step": next_step,
    }

    print("\nClosed-vocabulary deterministic safety floor final gate record:")
    print("  " + json.dumps(summary, sort_keys=True))

    print(f"\nvalidate_quality_safety_deterministic_floor_final_gate: {PASS} passed, {FAIL} failed")
    return 0 if all_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
