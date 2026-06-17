#!/usr/bin/env python3
"""Slice 142 — Offline Judge Schema Fixtures + Synthetic Harness (synthetic only).

Runs every synthetic offline-judge fixture through the pure schema normalizer and
validator, proving the **future** offline judge report contract
(`docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`) can be normalized, sanitized,
serialized, and validated using synthetic data only.

This is **not** judge execution. No guide is scored, no provider/model/cloud/local
LLM is called, no files are read or written, and nothing is wired into production.
``judge_ready`` and ``repair_ready`` always remain ``False``; the deterministic
safety floor remains the source of truth (a synthetic floor-red case can never
become shippable/ready). The harness prints a **closed-vocabulary summary only**.

Run:  python test_scripts/validate_quality_safety_offline_judge_synthetic_harness.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_offline_judge_schema import (  # noqa: E402
    BLOCKER_TOKENS,
    SYNTHETIC_FIXTURE_IDS,
    WARNING_TOKENS,
    build_synthetic_offline_judge_fixture,
    normalize_offline_judge_report,
    serialize_offline_judge_report,
    validate_offline_judge_report,
)

# Slice 143 core compatibility is checked opportunistically: if the pure core
# module is present, its synthetic reports must validate against this schema. The
# harness does not depend on production and degrades gracefully if absent.
try:
    from pipeline.quality_safety_offline_judge_core import (  # noqa: E402
        SYNTHETIC_CASE_IDS as CORE_CASE_IDS,
        run_synthetic_offline_judge_case,
    )
except Exception:  # pragma: no cover - core module optional for this harness
    CORE_CASE_IDS = ()
    run_synthetic_offline_judge_case = None

VALIDATION_ID = "quality_safety_offline_judge_synthetic_harness"
ARTIFACT_NAME_TOKEN = "quality_safety_offline_judge_report_json"

# Synthetic canary fragments that must never survive into normalized output.
CANARY_FRAGMENTS = (
    "SYNTHETIC_JUDGE_MARKER",
    "PRIVATE_MARKER",
    "/home/",
    "https://",
    ".pdf",
    ".docx",
    ".zip",
    "E=mc",
    "Bearer",
    "Authorization",
    "FREE_TEXT_NOT_A_TOKEN",
    "NOT_A_BLOCKER_TOKEN",
)

# Expected closed-vocabulary outcomes per synthetic fixture.
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


def _floor_payload(case_id: str) -> dict[str, Any] | None:
    if case_id == "deterministic_floor_red_synthetic_judge_case":
        return {"safety_floor_green": False}
    return None


def main() -> int:
    schema_ok = True
    fixture_ok = True
    leak_ok = True
    floor_ok = True

    fixture_ids = list(SYNTHETIC_FIXTURE_IDS)
    if set(fixture_ids) != set(EXPECTED):
        schema_ok = False
        fixture_ok = False

    for case_id in fixture_ids:
        fixture = build_synthetic_offline_judge_fixture(case_id)
        report = normalize_offline_judge_report(
            fixture, deterministic_floor_payload=_floor_payload(case_id)
        )

        # Schema validity + invariants.
        result = validate_offline_judge_report(report)
        if not result["valid"]:
            schema_ok = False
        if report.get("judge_ready") is not False or report.get("repair_ready") is not False:
            schema_ok = False
        if report.get("calibration_status") == "operator_validated":
            schema_ok = False
        if any(b not in BLOCKER_TOKENS for b in report.get("blockers", [])):
            schema_ok = False
        if any(w not in WARNING_TOKENS for w in report.get("warnings", [])):
            schema_ok = False

        # Deterministic serialization.
        report_again = normalize_offline_judge_report(
            build_synthetic_offline_judge_fixture(case_id),
            deterministic_floor_payload=_floor_payload(case_id),
        )
        if serialize_offline_judge_report(report) != serialize_offline_judge_report(report_again):
            schema_ok = False

        # No forbidden canary survives.
        blob = serialize_offline_judge_report(report)
        if any(fragment in blob for fragment in CANARY_FRAGMENTS):
            leak_ok = False

        # Expected closed-vocabulary outcome.
        spec = EXPECTED.get(case_id, {})
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
            if report.get("status") == "ok":
                floor_ok = False
            if report.get("judge_ready") is not False:
                floor_ok = False

    # A floor-red payload must override a softer self-reported floor status.
    override = normalize_offline_judge_report(
        {"kind": "quality_safety_offline_judge_report", "advisory": True,
         "deterministic_floor_status": "ready_for_cleanup_freeze"},
        deterministic_floor_payload={"safety_floor_green": False},
    )
    if override.get("deterministic_floor_status") != "blocked":
        floor_ok = False
    if "deterministic_floor_red" not in override.get("blockers", []):
        floor_ok = False

    # Slice 143 core compatibility (opportunistic; no production dependency).
    core_status = "absent"
    if run_synthetic_offline_judge_case is not None:
        core_ok = bool(CORE_CASE_IDS)
        for case_id in CORE_CASE_IDS:
            report = run_synthetic_offline_judge_case(case_id)
            if not validate_offline_judge_report(report)["valid"]:
                core_ok = False
            if report.get("judge_ready") is not False or report.get("repair_ready") is not False:
                core_ok = False
            blob = serialize_offline_judge_report(report)
            if any(fragment in blob for fragment in CANARY_FRAGMENTS):
                core_ok = False
                leak_ok = False
        core_status = "ok" if core_ok else "failed"

    summary = {
        "validation_id": VALIDATION_ID,
        "future_judge_artifact_name": ARTIFACT_NAME_TOKEN,
        "offline_judge_schema_status": "ok" if schema_ok else "failed",
        "synthetic_fixture_status": "ok" if fixture_ok else "failed",
        "leak_safety_status": "ok" if leak_ok else "failed",
        "deterministic_floor_relationship_status": "ok" if floor_ok else "failed",
        "offline_judge_core_compatibility_status": core_status,
        "calibration_status": "synthetic_only",
        "judge_contract_ready": True,
        "judge_ready": False,
        "repair_ready": False,
        "next_step": "offline_judge_core_v1_synthetic_only",
    }
    print(json.dumps(summary, sort_keys=True))

    ok = schema_ok and fixture_ok and leak_ok and floor_ok and core_status in {"ok", "absent"}
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
