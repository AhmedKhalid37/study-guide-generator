#!/usr/bin/env python3
"""Slice 147 — Advisory offline judge artifact adapter synthetic harness.

Runs every synthetic adapter case through the pure, unwired artifact schema
adapter (`pipeline/quality_safety_offline_judge_artifact_adapter.py`), proving a
normalized offline judge report adapts into a *write-ready shape* synthetic
artifact payload using synthetic data only.

This is **not** production artifact writing and **not** judge execution: no guide
is scored, no provider/model/cloud/local LLM is called, no files are read or
written, nothing is wired into jobs/UI, and no private calibration is run.
``artifact_write_ready`` / ``ui_display_ready`` / ``judge_ready`` /
``repair_ready`` always remain ``False``; the deterministic safety floor remains
the source of truth (a floor-red case can never become ok / write-ready /
display-ready). The harness prints a **closed-vocabulary summary only** and
writes no files.

Run:  python test_scripts/validate_quality_safety_offline_judge_artifact_adapter_synthetic.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_offline_judge_artifact_adapter import (  # noqa: E402
    ADAPTER_WARNING_TOKENS,
    ARTIFACT_KIND,
    ARTIFACT_NAME,
    SYNTHETIC_ARTIFACT_CASE_IDS,
    build_synthetic_offline_judge_artifact_case,
    run_synthetic_offline_judge_artifact_case,
    serialize_offline_judge_artifact_payload,
    validate_offline_judge_artifact_payload,
)
from pipeline.quality_safety_offline_judge_schema import BLOCKER_TOKENS  # noqa: E402

VALIDATION_ID = "quality_safety_offline_judge_artifact_adapter_synthetic"

# Synthetic canary fragments that must never survive into a serialized result.
CANARY_FRAGMENTS = (
    "SYNTHETIC_ADAPTER_MARKER",
    "PRIVATE_MARKER_ONLY",
    "MALFORMED_SYNTHETIC_ADAPTER_MARKER",
    "/home/",
    "/mnt/",
    "http://",
    "https://",
    ".pdf",
    ".docx",
    ".zip",
    "E=mc",
    "Bearer",
    "Authorization",
)

# Expected closed-vocabulary outcomes per synthetic adapter case.
EXPECTED = {
    "clean_synthetic_judge_case": {"shape_ready": True, "status_not_ok": False, "floor_red": False},
    "weak_synthetic_judge_case": {"shape_ready": True, "status_not_ok": True, "floor_red": False},
    "failed_synthetic_judge_case": {"shape_ready": True, "status_not_ok": True, "floor_red": False},
    "leak_canary_synthetic_judge_case": {"shape_ready": True, "status_not_ok": True, "floor_red": False},
    "deterministic_floor_red_synthetic_judge_case": {"shape_ready": True, "status_not_ok": True, "floor_red": True},
    "malformed_report_case": {"shape_ready": False, "status_not_ok": True, "floor_red": False},
}


def main() -> int:
    adapter_ok = True
    shape_ok = True
    leak_ok = True
    floor_ok = True

    if set(SYNTHETIC_ARTIFACT_CASE_IDS) != set(EXPECTED):
        adapter_ok = False

    any_shape_ready = False

    for case_id in SYNTHETIC_ARTIFACT_CASE_IDS:
        result = run_synthetic_offline_judge_artifact_case(case_id)
        spec: dict[str, Any] = EXPECTED.get(case_id, {})

        # Artifact identity is fixed.
        if result.get("artifact_name") != ARTIFACT_NAME:
            adapter_ok = False
        if result.get("artifact_kind") != ARTIFACT_KIND:
            adapter_ok = False
        if not isinstance(result.get("artifact_payload"), dict):
            adapter_ok = False
        elif result["artifact_payload"].get("kind") != ARTIFACT_KIND:
            adapter_ok = False

        # Readiness is always conservative in Slice 147.
        if (
            result.get("artifact_write_ready") is not False
            or result.get("ui_display_ready") is not False
            or result.get("judge_ready") is not False
            or result.get("repair_ready") is not False
        ):
            adapter_ok = False
        if result.get("private_operator_judge_calibration_run") != "not_run":
            adapter_ok = False
        if result.get("calibration_status") == "operator_validated":
            adapter_ok = False

        # Closed tokens only.
        if any(w not in ADAPTER_WARNING_TOKENS for w in result.get("warnings", [])):
            adapter_ok = False
        if any(b not in BLOCKER_TOKENS for b in result.get("blockers", [])):
            adapter_ok = False

        # Shape readiness expectation.
        if bool(result.get("artifact_shape_ready")) != spec.get("shape_ready"):
            shape_ok = False
        if result.get("artifact_shape_ready"):
            any_shape_ready = True
            if not validate_offline_judge_artifact_payload(result)["valid"]:
                shape_ok = False

        # Status expectation.
        if spec.get("status_not_ok") and result.get("status") == "ok":
            adapter_ok = False

        # Deterministic serialization.
        again = run_synthetic_offline_judge_artifact_case(case_id)
        if serialize_offline_judge_artifact_payload(result) != serialize_offline_judge_artifact_payload(again):
            adapter_ok = False

        # Caller input not mutated.
        before = build_synthetic_offline_judge_artifact_case(case_id)
        run_synthetic_offline_judge_artifact_case(case_id)
        if build_synthetic_offline_judge_artifact_case(case_id) != before:
            adapter_ok = False

        # No forbidden canary survives.
        blob = serialize_offline_judge_artifact_payload(result)
        if any(fragment in blob for fragment in CANARY_FRAGMENTS):
            leak_ok = False

        # Deterministic floor relationship.
        if spec.get("floor_red"):
            payload = result.get("artifact_payload", {})
            if payload.get("deterministic_floor_status") != "blocked":
                floor_ok = False
            if "deterministic_floor_red" not in result.get("blockers", []):
                floor_ok = False
            if result.get("status") == "ok" or result.get("artifact_write_ready") is not False:
                floor_ok = False

    summary = {
        "validation_id": VALIDATION_ID,
        "advisory_judge_artifact_adapter_status": "ok" if adapter_ok else "failed",
        "artifact_shape_status": "ok" if shape_ok else "failed",
        "artifact_write_status": "not_ready",
        "ui_display_status": "not_ready",
        "leak_safety_status": "ok" if leak_ok else "failed",
        "deterministic_floor_relationship_status": "ok" if floor_ok else "failed",
        "calibration_status": "synthetic_only",
        "private_operator_judge_calibration_run": "not_run",
        "artifact_shape_ready": bool(any_shape_ready and shape_ok),
        "artifact_write_ready": False,
        "ui_display_ready": False,
        "judge_ready": False,
        "repair_ready": False,
        "next_step": "advisory_offline_judge_artifact_writer_design_or_stop_for_private_calibration",
    }
    print(json.dumps(summary, sort_keys=True))

    ok = adapter_ok and shape_ok and leak_ok and floor_ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
