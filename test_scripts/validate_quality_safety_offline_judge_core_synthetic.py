#!/usr/bin/env python3
"""Slice 143 — Offline Judge Core v1 synthetic harness (synthetic only).

Runs every synthetic offline-judge *core* case through the pure deterministic
core (`pipeline/quality_safety_offline_judge_core.py`), proving caller-supplied
closed observations convert into a normalized, sanitized Slice 142 report using
synthetic data only.

This is **not** judge execution. No guide is scored, no provider/model/cloud/local
LLM is called, no files are read or written, and nothing is wired into production.
``judge_ready`` / ``repair_ready`` always remain ``False``; the deterministic
safety floor remains the source of truth (a synthetic floor-red case can never
become shippable/ready, and the core cannot override deterministic blockers). The
harness prints a **closed-vocabulary summary only**.

Run:  python test_scripts/validate_quality_safety_offline_judge_core_synthetic.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_offline_judge_core import (  # noqa: E402
    SYNTHETIC_CASE_IDS,
    build_offline_judge_report_from_observations,
    run_synthetic_offline_judge_case,
)
from pipeline.quality_safety_offline_judge_schema import (  # noqa: E402
    BLOCKER_TOKENS,
    KIND,
    WARNING_TOKENS,
    serialize_offline_judge_report,
    validate_offline_judge_report,
)

VALIDATION_ID = "quality_safety_offline_judge_core_synthetic"
ARTIFACT_NAME_TOKEN = "quality_safety_offline_judge_report_json"

# Synthetic canary fragments that must never survive into normalized output.
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
    "FREE_TEXT_NOT_A_TOKEN_CORE",
    "NOT_A_BLOCKER_TOKEN_CORE",
)

# Expected closed-vocabulary outcomes per synthetic core case.
EXPECTED = {
    "clean_synthetic_judge_case": {"status": "ok", "blockers_empty": True, "privacy": {"ok"}},
    "weak_synthetic_judge_case": {"status": "warning", "blockers_empty": True, "privacy": {"ok"}},
    "failed_synthetic_judge_case": {
        "status": "failed",
        "blockers_empty": False,
        "privacy": {"ok", "unknown", "warning", "failed"},
    },
    "leak_canary_synthetic_judge_case": {
        "status": "failed",
        "blockers_empty": False,
        "privacy": {"warning", "failed"},
    },
    "deterministic_floor_red_synthetic_judge_case": {
        "status": "failed",
        "blockers_empty": False,
        "privacy": {"ok", "unknown", "warning", "failed"},
    },
}


def main() -> int:
    core_ok = True
    fixture_ok = True
    schema_ok = True
    leak_ok = True
    floor_ok = True

    case_ids = list(SYNTHETIC_CASE_IDS)
    if set(case_ids) != set(EXPECTED):
        core_ok = False
        fixture_ok = False

    for case_id in case_ids:
        report = run_synthetic_offline_judge_case(case_id)

        # Schema compatibility: every core report must validate against Slice 142.
        result = validate_offline_judge_report(report)
        if not result["valid"]:
            schema_ok = False
        if report.get("kind") != KIND:
            schema_ok = False
        if report.get("judge_ready") is not False or report.get("repair_ready") is not False:
            core_ok = False
        if report.get("calibration_status") == "operator_validated":
            core_ok = False
        if any(b not in BLOCKER_TOKENS for b in report.get("blockers", [])):
            core_ok = False
        if any(w not in WARNING_TOKENS for w in report.get("warnings", [])):
            core_ok = False

        # Deterministic serialization.
        again = run_synthetic_offline_judge_case(case_id)
        if serialize_offline_judge_report(report) != serialize_offline_judge_report(again):
            core_ok = False

        # No forbidden canary survives.
        blob = serialize_offline_judge_report(report)
        if any(fragment in blob for fragment in CANARY_FRAGMENTS):
            leak_ok = False

        # Expected closed-vocabulary outcome.
        spec: dict[str, Any] = EXPECTED.get(case_id, {})
        if report.get("status") != spec.get("status"):
            fixture_ok = False
        if spec.get("blockers_empty") and report.get("blockers"):
            fixture_ok = False
        if not spec.get("blockers_empty") and not report.get("blockers"):
            fixture_ok = False
        if report.get("privacy_status") not in spec.get("privacy", set()):
            fixture_ok = False

        # Deterministic floor red can never become shippable/ready.
        if case_id == "deterministic_floor_red_synthetic_judge_case":
            if report.get("deterministic_floor_status") != "blocked":
                floor_ok = False
            if "deterministic_floor_red" not in report.get("blockers", []):
                floor_ok = False
            if report.get("status") == "ok" or report.get("judge_ready") is not False:
                floor_ok = False

    # A floor-red payload must override clean all-pass observations.
    override = build_offline_judge_report_from_observations(
        {"axis_observations": [{"axis": "correctness", "signals": {"pass_count": 9}, "confidence": "high"}]},
        deterministic_floor_payload={"safety_floor_green": False},
    )
    if override.get("deterministic_floor_status") != "blocked":
        floor_ok = False
    if "deterministic_floor_red" not in override.get("blockers", []):
        floor_ok = False
    if override.get("status") == "ok":
        floor_ok = False

    summary = {
        "validation_id": VALIDATION_ID,
        "future_judge_artifact_name": ARTIFACT_NAME_TOKEN,
        "offline_judge_core_status": "ok" if core_ok else "failed",
        "synthetic_case_status": "ok" if fixture_ok else "failed",
        "schema_compatibility_status": "ok" if schema_ok else "failed",
        "leak_safety_status": "ok" if leak_ok else "failed",
        "deterministic_floor_relationship_status": "ok" if floor_ok else "failed",
        "calibration_status": "synthetic_only",
        "judge_contract_ready": True,
        "judge_ready": False,
        "repair_ready": False,
        "next_step": "judge_calibration_gate_golden_protocol",
    }
    print(json.dumps(summary, sort_keys=True))

    ok = core_ok and fixture_ok and schema_ok and leak_ok and floor_ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
