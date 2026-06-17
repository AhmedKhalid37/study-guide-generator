#!/usr/bin/env python3
"""Slice 145 — Quality Safety Judge Calibration Gate harness (closed records).

Validates **closed-vocabulary calibration records** against the Slice 144 judge
calibration gate / golden protocol
(`docs/QUALITY_SAFETY_JUDGE_CALIBRATION_GATE_PROTOCOL.md`).

This harness validates **calibration records**, not raw/private materials. It is
**not** judge execution and **not** a private operator calibration run by itself:

- It never reads guide/source/reference documents.
- It never reads raw judge reports.
- It never calls providers/models/cloud/local LLMs.
- It never writes output files.
- It never prints local paths.
- It never prints raw record values beyond a closed-vocabulary summary.

Default (synthetic) mode self-tests the protocol's golden-case expectations by
running the pure Slice 143 offline judge core
(`pipeline/quality_safety_offline_judge_core.py`) over **synthetic** observations
only. The synthetic cases are closed records, not private material. The core is
deterministic, reads no files, and calls no models. ``judge_ready`` /
``repair_ready`` always remain ``False`` and the deterministic safety floor
remains the source of truth (a floor-red case can never be overridden).

Optional local closed-record mode (operator-driven, never committed unless the
operator explicitly says so) reads exactly one closed-vocabulary calibration
record JSON file and validates it against the protocol. It reads only that file,
prints no path, prints no raw strings outside closed tokens, writes nothing, and
degrades read/parse failures to closed tokens.

Run (synthetic self-test):
    python test_scripts/validate_quality_safety_judge_calibration_gate.py

Run (local closed-record validation; not committed data):
    python test_scripts/validate_quality_safety_judge_calibration_gate.py \\
        --input /local/private/path/closed_calibration_record.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_offline_judge_core import (  # noqa: E402
    run_synthetic_offline_judge_case,
)
from pipeline.quality_safety_offline_judge_schema import (  # noqa: E402
    BLOCKER_TOKENS,
    WARNING_TOKENS,
    serialize_offline_judge_report,
    validate_offline_judge_report,
)

VALIDATION_ID = "quality_safety_judge_calibration_gate"

# --------------------------------------------------------------------------- #
# Closed vocabularies for the calibration record (Slice 144 protocol)
# --------------------------------------------------------------------------- #
INPUT_KINDS = frozenset({"synthetic_only", "private_operator_closed_record", "not_run"})
JUDGE_CALLS_VALUES = frozenset({"false", "synthetic_only", "local_offline"})
FLOOR_STATUSES = frozenset({"ready_for_cleanup_freeze", "partial", "blocked", "unknown"})
OBS_STATUSES = frozenset({"ok", "warning", "failed", "not_observed"})
CALIBRATION_STATUSES = frozenset(
    {"not_started", "synthetic_only", "operator_validated", "failed", "blocked"}
)
CALIBRATION_WARNING_TOKENS = frozenset(
    {
        "malformed_calibration_record",
        "missing_required_field",
        "invalid_field_value_dropped",
        "operator_validated_not_allowed_yet",
        "judge_ready_forced_false",
        "repair_ready_forced_false",
        "raw_private_material_flag_set",
        "runtime_outputs_flag_set",
        "provider_calls_flag_set",
        "llm_calls_flag_set",
        "repair_calls_flag_set",
        "read_failed",
        "parse_failed",
    }
)

# Closed-vocabulary golden case set (Slice 144). The synthetic core case is used
# only to *self-test* protocol behavior; the expectation tokens are golden-case
# labels, not committed report fields.
GOLDEN_CASES = (
    "clean_real_case",
    "single_confident_wrong_numeric_case",
    "legacy_confused_wrong_case",
    "leak_canary_case",
    "deterministic_floor_red_case",
)

# Synthetic canary fragments that must never survive into any serialized report.
CANARY_FRAGMENTS = (
    "SYNTHETIC_CORE_MARKER",
    "PRIVATE_MARKER",
    "/home/",
    "https://",
    ".pdf",
    ".docx",
    ".zip",
    "E=mc",
    "Bearer",
    "Authorization",
)

# Mapping from golden case -> (synthetic core case id, protocol self-test check).
# Each check receives the normalized core report and returns (passed, status_tok).
_GOLDEN_SELF_TEST = {
    "clean_real_case": "clean_synthetic_judge_case",
    "single_confident_wrong_numeric_case": "failed_synthetic_judge_case",
    "legacy_confused_wrong_case": "weak_synthetic_judge_case",
    "leak_canary_case": "leak_canary_synthetic_judge_case",
    "deterministic_floor_red_case": "deterministic_floor_red_synthetic_judge_case",
}


# --------------------------------------------------------------------------- #
# Synthetic self-test mode
# --------------------------------------------------------------------------- #
def _golden_case_passes(golden_case: str, report: dict[str, Any]) -> bool:
    status = report.get("status")
    blockers = report.get("blockers") or []
    floor = report.get("deterministic_floor_status")

    if golden_case == "clean_real_case":
        return status in {"ok", "warning"} and not blockers
    if golden_case == "single_confident_wrong_numeric_case":
        # Must be detected as blocking/failing (recompute-or-correctness family).
        return status in {"failed", "partial"} and "axis_failed" in blockers
    if golden_case == "legacy_confused_wrong_case":
        # A confused/wrong legacy guide must not pass cleanly.
        return status in {"warning", "partial", "failed"}
    if golden_case == "leak_canary_case":
        # The leak canary must be detected as failing on leakage/privacy.
        return status == "failed" and (
            "leak_detected" in blockers or "privacy_failed" in blockers
        )
    if golden_case == "deterministic_floor_red_case":
        # The floor-red case can never be overridden by the judge.
        return (
            floor == "blocked"
            and "deterministic_floor_red" in blockers
            and status != "ok"
        )
    return False


def _run_synthetic_self_test() -> dict[str, Any]:
    passed = 0
    failed = 0
    schema_ok = True
    leak_ok = True
    floor_ok = True
    core_ok = True

    for golden_case in GOLDEN_CASES:
        core_case = _GOLDEN_SELF_TEST[golden_case]
        report = run_synthetic_offline_judge_case(core_case)

        # Schema compatibility for every self-test report.
        if not validate_offline_judge_report(report)["valid"]:
            schema_ok = False
        if report.get("judge_ready") is not False or report.get("repair_ready") is not False:
            core_ok = False
        if any(b not in BLOCKER_TOKENS for b in report.get("blockers", [])):
            core_ok = False
        if any(w not in WARNING_TOKENS for w in report.get("warnings", [])):
            core_ok = False

        # No forbidden canary may survive serialization.
        if any(frag in serialize_offline_judge_report(report) for frag in CANARY_FRAGMENTS):
            leak_ok = False

        if _golden_case_passes(golden_case, report):
            passed += 1
        else:
            failed += 1

    # The floor-red payload must override clean all-pass observations.
    floor_report = run_synthetic_offline_judge_case(
        "deterministic_floor_red_synthetic_judge_case"
    )
    if (
        floor_report.get("deterministic_floor_status") != "blocked"
        or "deterministic_floor_red" not in floor_report.get("blockers", [])
        or floor_report.get("status") == "ok"
    ):
        floor_ok = False

    record = _make_record(
        input_kind="synthetic_only",
        golden_case_count=len(GOLDEN_CASES),
        passed_case_count=passed,
        failed_case_count=failed,
        operator_review_count=0,
        judge_calls="synthetic_only",
        deterministic_floor_status="ready_for_cleanup_freeze",
        offline_judge_core_status="ok" if core_ok else "failed",
        schema_compatibility_status="ok" if schema_ok else "failed",
        leak_safety_status="ok" if leak_ok else "failed",
        calibration_status="synthetic_only",
        warnings=[],
    )

    all_cases_pass = failed == 0 and passed == len(GOLDEN_CASES)
    protocol_ok = all_cases_pass and schema_ok and leak_ok and floor_ok and core_ok

    summary = dict(record)
    summary.update(
        {
            "private_operator_run": "not_run",
            "protocol_status": "ok" if protocol_ok else "failed",
            "no_raw_private_material": True,
            "next_step": "advisory_judge_artifact_design_or_stop_for_private_calibration",
        }
    )

    # Hard synthetic expectations — the gate must hold.
    ok = (
        protocol_ok
        and record["calibration_status"] == "synthetic_only"
        and record["judge_ready"] is False
        and record["repair_ready"] is False
        and record["raw_private_material_committed"] is False
        and record["runtime_outputs_committed"] is False
        and record["provider_calls"] is False
        and record["llm_calls"] is False
    )
    return {"summary": summary, "ok": ok}


# --------------------------------------------------------------------------- #
# Local closed-record validation mode
# --------------------------------------------------------------------------- #
def _enum(value: Any, allowed: frozenset[str]) -> str | None:
    if isinstance(value, str) and value in allowed:
        return value
    return None


def _non_neg_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _validate_closed_record(raw: Any) -> dict[str, Any]:
    """Validate a caller-supplied closed-vocabulary calibration record.

    Returns a closed-vocabulary summary only. Never raises; never echoes raw
    strings beyond closed tokens; never reveals provided free text.
    """
    warnings: set[str] = set()

    if not isinstance(raw, dict):
        return _local_summary(input_kind="not_run", warnings=["malformed_calibration_record"])

    input_kind = _enum(raw.get("input_kind"), INPUT_KINDS) or "not_run"
    if _enum(raw.get("input_kind"), INPUT_KINDS) is None:
        warnings.add("invalid_field_value_dropped")

    golden_case_count = _non_neg_int(raw.get("golden_case_count"))
    passed_case_count = _non_neg_int(raw.get("passed_case_count"))
    failed_case_count = _non_neg_int(raw.get("failed_case_count"))
    operator_review_count = _non_neg_int(raw.get("operator_review_count"))
    for got in (golden_case_count, passed_case_count, failed_case_count, operator_review_count):
        if got is None:
            warnings.add("invalid_field_value_dropped")

    # Safety boolean flags must be false. A true flag is a leak-shaped record.
    raw_priv = bool(raw.get("raw_private_material_committed"))
    runtime_out = bool(raw.get("runtime_outputs_committed"))
    provider_calls = bool(raw.get("provider_calls"))
    llm_calls = bool(raw.get("llm_calls"))
    repair_calls = bool(raw.get("repair_calls"))
    if raw_priv:
        warnings.add("raw_private_material_flag_set")
    if runtime_out:
        warnings.add("runtime_outputs_flag_set")
    if provider_calls:
        warnings.add("provider_calls_flag_set")
    if llm_calls:
        warnings.add("llm_calls_flag_set")
    if repair_calls:
        warnings.add("repair_calls_flag_set")

    judge_calls_raw = raw.get("judge_calls")
    if judge_calls_raw is False:
        judge_calls = "false"
    else:
        judge_calls = _enum(judge_calls_raw, JUDGE_CALLS_VALUES) or "false"
        if judge_calls_raw is not False and _enum(judge_calls_raw, JUDGE_CALLS_VALUES) is None:
            warnings.add("invalid_field_value_dropped")

    deterministic_floor_status = _enum(raw.get("deterministic_floor_status"), FLOOR_STATUSES) or "unknown"
    offline_judge_core_status = _enum(raw.get("offline_judge_core_status"), OBS_STATUSES) or "not_observed"
    schema_compatibility_status = _enum(raw.get("schema_compatibility_status"), OBS_STATUSES) or "not_observed"
    leak_safety_status = _enum(raw.get("leak_safety_status"), OBS_STATUSES) or "not_observed"

    calibration_status = _enum(raw.get("calibration_status"), CALIBRATION_STATUSES) or "not_started"
    if _enum(raw.get("calibration_status"), CALIBRATION_STATUSES) is None:
        warnings.add("invalid_field_value_dropped")

    # operator_validated may not be claimed unless the conservative protocol gate
    # passes; this harness never authorizes the flip, so downgrade it here.
    operator_validated_claimed = calibration_status == "operator_validated"
    if operator_validated_claimed:
        warnings.add("operator_validated_not_allowed_yet")
        calibration_status = "synthetic_only"

    # judge_ready / repair_ready are forced false by this harness.
    if bool(raw.get("judge_ready")):
        warnings.add("judge_ready_forced_false")
    if bool(raw.get("repair_ready")):
        warnings.add("repair_ready_forced_false")

    # Carry only closed warning tokens supplied in the record.
    supplied = raw.get("warnings")
    if isinstance(supplied, list):
        for tok in supplied[:64]:
            if isinstance(tok, str) and tok in CALIBRATION_WARNING_TOKENS:
                warnings.add(tok)

    summary = _make_record(
        input_kind=input_kind,
        golden_case_count=golden_case_count or 0,
        passed_case_count=passed_case_count or 0,
        failed_case_count=failed_case_count or 0,
        operator_review_count=operator_review_count or 0,
        judge_calls=judge_calls,
        deterministic_floor_status=deterministic_floor_status,
        offline_judge_core_status=offline_judge_core_status,
        schema_compatibility_status=schema_compatibility_status,
        leak_safety_status=leak_safety_status,
        calibration_status=calibration_status,
        warnings=sorted(warnings),
        provider_calls=provider_calls,
        llm_calls=llm_calls,
        raw_private_material_committed=raw_priv,
        runtime_outputs_committed=runtime_out,
        repair_calls=repair_calls,
    )

    # A safe local record: no leak-shaped flags set, schema/leak not failed,
    # no disallowed readiness flip. judge_ready/repair_ready stay false.
    ok = (
        not raw_priv
        and not runtime_out
        and not provider_calls
        and not llm_calls
        and not repair_calls
        and schema_compatibility_status != "failed"
        and leak_safety_status != "failed"
        and offline_judge_core_status != "failed"
    )
    return {"summary": summary, "ok": ok}


def _run_local_mode(input_path: str) -> dict[str, Any]:
    path = Path(input_path)
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return _wrap(_local_summary(input_kind="not_run", warnings=["read_failed"]), ok=False)
    try:
        raw = json.loads(text)
    except Exception:
        return _wrap(_local_summary(input_kind="not_run", warnings=["parse_failed"]), ok=False)
    return _validate_closed_record(raw)


# --------------------------------------------------------------------------- #
# Record builders (closed vocabulary only)
# --------------------------------------------------------------------------- #
def _make_record(
    *,
    input_kind: str,
    golden_case_count: int,
    passed_case_count: int,
    failed_case_count: int,
    operator_review_count: int,
    judge_calls: str,
    deterministic_floor_status: str,
    offline_judge_core_status: str,
    schema_compatibility_status: str,
    leak_safety_status: str,
    calibration_status: str,
    warnings: list[str],
    provider_calls: bool = False,
    llm_calls: bool = False,
    raw_private_material_committed: bool = False,
    runtime_outputs_committed: bool = False,
    repair_calls: bool = False,
) -> dict[str, Any]:
    return {
        "validation_id": VALIDATION_ID,
        "input_kind": input_kind,
        "golden_case_count": golden_case_count,
        "passed_case_count": passed_case_count,
        "failed_case_count": failed_case_count,
        "operator_review_count": operator_review_count,
        "raw_private_material_committed": bool(raw_private_material_committed),
        "runtime_outputs_committed": bool(runtime_outputs_committed),
        "provider_calls": bool(provider_calls),
        "llm_calls": bool(llm_calls),
        "judge_calls": judge_calls,
        "repair_calls": bool(repair_calls),
        "deterministic_floor_status": deterministic_floor_status,
        "offline_judge_core_status": offline_judge_core_status,
        "schema_compatibility_status": schema_compatibility_status,
        "leak_safety_status": leak_safety_status,
        "calibration_status": calibration_status,
        "judge_ready": False,
        "repair_ready": False,
        "warnings": warnings,
    }


def _local_summary(*, input_kind: str, warnings: list[str]) -> dict[str, Any]:
    return _make_record(
        input_kind=input_kind,
        golden_case_count=0,
        passed_case_count=0,
        failed_case_count=0,
        operator_review_count=0,
        judge_calls="false",
        deterministic_floor_status="unknown",
        offline_judge_core_status="not_observed",
        schema_compatibility_status="not_observed",
        leak_safety_status="not_observed",
        calibration_status="not_started",
        warnings=sorted(set(warnings) & CALIBRATION_WARNING_TOKENS),
    )


def _wrap(summary: dict[str, Any], *, ok: bool) -> dict[str, Any]:
    return {"summary": summary, "ok": ok}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate closed-vocabulary judge calibration records (closed records only)."
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "Optional local closed-record JSON path (operator-driven, not committed "
            "data). The path is never printed."
        ),
    )
    args = parser.parse_args(argv)

    if args.input:
        result = _run_local_mode(args.input)
    else:
        result = _run_synthetic_self_test()

    # Closed-vocabulary summary only; never a local path, never raw record values.
    print(json.dumps(result["summary"], sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
