#!/usr/bin/env python3
"""Tests for the Slice 147 advisory offline judge artifact schema adapter.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, model
prompts/responses, paths, URLs, images, PDFs, DOCX files, ZIPs, or runtime
artifacts. Hostile canaries are synthetic markers used only to prove forbidden
content is stripped. No judge runs; no provider/model/cloud/local-LLM is called;
no files are read or written; nothing is wired into production.

The adapter is pure/unwired: it adapts a normalized offline judge report into a
write-ready synthetic artifact payload shape only. ``artifact_write_ready`` /
``ui_display_ready`` / ``judge_ready`` / ``repair_ready`` always remain ``False``;
the deterministic safety floor remains the source of truth.

Run:  python test_scripts/test_quality_safety_offline_judge_artifact_adapter.py
"""
from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_offline_judge_artifact_adapter import (  # noqa: E402
    ADAPTER_RESULT_KIND,
    ADAPTER_STATUSES,
    ADAPTER_WARNING_TOKENS,
    ARTIFACT_KIND,
    ARTIFACT_NAME,
    SYNTHETIC_ARTIFACT_CASE_IDS,
    adapt_offline_judge_report_to_artifact_payload,
    build_empty_offline_judge_artifact_adapter_result,
    build_synthetic_offline_judge_artifact_case,
    run_synthetic_offline_judge_artifact_case,
    serialize_offline_judge_artifact_payload,
    validate_offline_judge_artifact_payload,
)
from pipeline.quality_safety_offline_judge_core import (  # noqa: E402
    run_synthetic_offline_judge_case,
)
from pipeline.quality_safety_offline_judge_schema import (  # noqa: E402
    BLOCKER_TOKENS,
    FORBIDDEN_FIELDS,
    KIND,
)

PASS = 0
FAIL = 0

MODULE_PATH = REPO / "pipeline" / "quality_safety_offline_judge_artifact_adapter.py"

FORBIDDEN_MARKERS = (
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

# The adapter may import only the Slice 142 schema, the Slice 143 core, and
# stdlib typing / json. No FastAPI / frontend / render / OCR / provider / model /
# job-runtime imports are allowed.
ALLOWED_IMPORTS = {
    "__future__",
    "typing",
    "json",
    "pipeline.quality_safety_offline_judge_schema",
    "pipeline.quality_safety_offline_judge_core",
}
FORBIDDEN_IMPORT_PARTS = (
    "fastapi",
    "frontend",
    "provider",
    "model_client",
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "render",
    "ocr",
    "fitz",
    "pytesseract",
    "job_manager",
    "run_markdown_job",
    "quality_safety_job_artifact",
    "quality_judge",
    "chandra",
    "mistral",
    "gemini",
    "socket",
    "subprocess",
    "os",
    "pathlib",
)


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[FAIL] {name}{suffix}")


def assert_no_canary(name: str, result: dict[str, Any]) -> None:
    blob = serialize_offline_judge_artifact_payload(result)
    found = [marker for marker in FORBIDDEN_MARKERS if marker in blob]
    check(f"{name}: no hostile canary", not found, str(found))


def assert_result_shape(name: str, result: dict[str, Any]) -> None:
    check(f"{name}: is dict", isinstance(result, dict))
    check(f"{name}: kind", result.get("kind") == ADAPTER_RESULT_KIND)
    check(f"{name}: status closed", result.get("status") in ADAPTER_STATUSES, str(result.get("status")))
    check(f"{name}: artifact_name", result.get("artifact_name") == ARTIFACT_NAME, str(result.get("artifact_name")))
    check(f"{name}: artifact_kind", result.get("artifact_kind") == ARTIFACT_KIND, str(result.get("artifact_kind")))
    payload = result.get("artifact_payload")
    check(f"{name}: payload is dict", isinstance(payload, dict))
    check(f"{name}: payload kind", isinstance(payload, dict) and payload.get("kind") == "quality_safety_offline_judge_report")
    # Readiness must always be conservative in Slice 147.
    check(f"{name}: artifact_write_ready false", result.get("artifact_write_ready") is False)
    check(f"{name}: ui_display_ready false", result.get("ui_display_ready") is False)
    check(f"{name}: judge_ready false", result.get("judge_ready") is False)
    check(f"{name}: repair_ready false", result.get("repair_ready") is False)
    check(f"{name}: shape_ready is bool", isinstance(result.get("artifact_shape_ready"), bool))
    check(f"{name}: private run not_run", result.get("private_operator_judge_calibration_run") == "not_run")
    check(f"{name}: calibration not operator_validated", result.get("calibration_status") != "operator_validated")
    # Summary closed/non-negative.
    summary = result.get("summary")
    check(
        f"{name}: summary keys",
        isinstance(summary, dict)
        and set(summary) == {"axis_count", "blocker_count", "warning_count", "forbidden_field_count"},
        str(summary),
    )
    if isinstance(summary, dict):
        check(
            f"{name}: summary non-negative ints",
            all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()),
            str(summary),
        )
    # Closed tokens only.
    check(
        f"{name}: warnings closed",
        isinstance(result.get("warnings"), list) and all(w in ADAPTER_WARNING_TOKENS for w in result["warnings"]),
        str(result.get("warnings")),
    )
    check(
        f"{name}: blockers closed",
        isinstance(result.get("blockers"), list) and all(b in BLOCKER_TOKENS for b in result["blockers"]),
        str(result.get("blockers")),
    )
    # No forbidden field survives at the top level of result or payload.
    check(f"{name}: no forbidden result field", not any(f in result for f in FORBIDDEN_FIELDS))
    if isinstance(payload, dict):
        check(f"{name}: no forbidden payload field", not any(f in payload for f in FORBIDDEN_FIELDS))
        for axis in payload.get("axis_results", []):
            check(f"{name}: no forbidden axis field", not any(f in axis for f in FORBIDDEN_FIELDS))
    assert_no_canary(name, result)


def main() -> int:
    # --- 1. Empty / malformed input degrades safely ---------------------------
    empty = build_empty_offline_judge_artifact_adapter_result()
    assert_result_shape("empty", empty)
    check("empty: status skipped", empty.get("status") == "skipped")
    check("empty: shape_ready false", empty.get("artifact_shape_ready") is False)

    for bad in (None, 123, "string", [], ()):
        result = adapt_offline_judge_report_to_artifact_payload(bad)
        assert_result_shape(f"malformed {bad!r}", result)
        check(f"malformed {bad!r}: shape_ready false", result.get("artifact_shape_ready") is False)
        check(f"malformed {bad!r}: status skipped/failed", result.get("status") in {"skipped", "failed"})

    # --- 2. Normalized report (built directly) is accepted --------------------
    direct = run_synthetic_offline_judge_case("clean_synthetic_judge_case")
    direct_result = adapt_offline_judge_report_to_artifact_payload(direct)
    assert_result_shape("direct normalized", direct_result)
    check("direct: shape_ready true", direct_result.get("artifact_shape_ready") is True)
    check("direct: status ok", direct_result.get("status") == "ok")

    # --- 3. Slice 143 synthetic core report is accepted -----------------------
    core_report = run_synthetic_offline_judge_case("weak_synthetic_judge_case")
    core_result = adapt_offline_judge_report_to_artifact_payload(core_report)
    assert_result_shape("core weak", core_result)
    check("core weak: shape_ready true", core_result.get("artifact_shape_ready") is True)
    check("core weak: warning status allowed", core_result.get("status") in {"warning", "ok"})

    # --- 4. Identity invariants -----------------------------------------------
    check("artifact_name constant", ARTIFACT_NAME == "quality_safety_offline_judge_report.json")
    check("artifact_kind constant", ARTIFACT_KIND == "quality_safety_offline_judge_report")
    check("artifact_kind matches schema KIND", ARTIFACT_KIND == KIND)

    # --- 5. validate_offline_judge_artifact_payload ---------------------------
    v_result = validate_offline_judge_artifact_payload(direct_result)
    check("validate: result payload valid", v_result["valid"], str(v_result["violations"]))
    v_payload = validate_offline_judge_artifact_payload(direct_result["artifact_payload"])
    check("validate: bare payload valid", v_payload["valid"], str(v_payload["violations"]))
    v_bad = validate_offline_judge_artifact_payload({"kind": "wrong", "version": 1})
    check("validate: wrong kind invalid", not v_bad["valid"])

    # --- 6. Every synthetic adapter case --------------------------------------
    case_ids = list(SYNTHETIC_ARTIFACT_CASE_IDS)
    check(
        "case ids exposed",
        set(case_ids)
        == {
            "clean_synthetic_judge_case",
            "weak_synthetic_judge_case",
            "failed_synthetic_judge_case",
            "leak_canary_synthetic_judge_case",
            "deterministic_floor_red_synthetic_judge_case",
            "malformed_report_case",
        },
    )

    for case_id in case_ids:
        report = build_synthetic_offline_judge_artifact_case(case_id)
        before = copy.deepcopy(report)
        result = run_synthetic_offline_judge_artifact_case(case_id)
        # Caller input not mutated by adaptation.
        check(f"{case_id}: input not mutated", build_synthetic_offline_judge_artifact_case(case_id) == before)
        assert_result_shape(case_id, result)
        # Readiness always conservative.
        check(f"{case_id}: write_ready false", result.get("artifact_write_ready") is False)
        check(f"{case_id}: ui_display_ready false", result.get("ui_display_ready") is False)
        check(f"{case_id}: judge_ready false", result.get("judge_ready") is False)
        check(f"{case_id}: repair_ready false", result.get("repair_ready") is False)
        # Deterministic serialization across repeated runs.
        again = run_synthetic_offline_judge_artifact_case(case_id)
        check(
            f"{case_id}: deterministic serialization",
            serialize_offline_judge_artifact_payload(result)
            == serialize_offline_judge_artifact_payload(again),
        )

    # --- 7. Per-case expected outcomes ----------------------------------------
    clean = run_synthetic_offline_judge_artifact_case("clean_synthetic_judge_case")
    check("clean: shape_ready true", clean.get("artifact_shape_ready") is True)
    check("clean: status ok", clean.get("status") == "ok")
    check("clean: no blockers", clean.get("blockers") == [])

    weak = run_synthetic_offline_judge_artifact_case("weak_synthetic_judge_case")
    check("weak: shape_ready true", weak.get("artifact_shape_ready") is True)
    check("weak: warning status allowed", weak.get("status") in {"warning", "ok"})

    failed = run_synthetic_offline_judge_artifact_case("failed_synthetic_judge_case")
    check("failed: shape_ready true/partial-ok", failed.get("artifact_shape_ready") in {True, False})
    check("failed: status not ok", failed.get("status") != "ok")
    check("failed: write_ready false", failed.get("artifact_write_ready") is False)

    leak = run_synthetic_offline_judge_artifact_case("leak_canary_synthetic_judge_case")
    assert_no_canary("leak", leak)
    check("leak: forbidden_field_count > 0", leak["summary"]["forbidden_field_count"] > 0, str(leak["summary"]))
    check("leak: forbidden_field_stripped warning", "forbidden_field_stripped" in leak.get("warnings", []))
    check("leak: write_ready false", leak.get("artifact_write_ready") is False)
    check("leak: status not ok", leak.get("status") != "ok")

    floor = run_synthetic_offline_judge_artifact_case("deterministic_floor_red_synthetic_judge_case")
    check("floor: deterministic_floor_red blocker", "deterministic_floor_red" in floor.get("blockers", []))
    check("floor: status not ok", floor.get("status") != "ok")
    check("floor: not write-ready", floor.get("artifact_write_ready") is False)
    check("floor: not display-ready", floor.get("ui_display_ready") is False)
    check("floor: payload floor blocked", floor["artifact_payload"].get("deterministic_floor_status") == "blocked")

    malformed = run_synthetic_offline_judge_artifact_case("malformed_report_case")
    check("malformed: shape_ready false", malformed.get("artifact_shape_ready") is False)
    check("malformed: status skipped/failed", malformed.get("status") in {"skipped", "failed"})
    check("malformed: write_ready false", malformed.get("artifact_write_ready") is False)

    # --- 8. Calibration interaction -------------------------------------------
    synth_calib = adapt_offline_judge_report_to_artifact_payload(
        direct,
        calibration_record={
            "calibration_status": "synthetic_only",
            "private_operator_judge_calibration_run": "not_run",
        },
    )
    assert_result_shape("calib synthetic_only", synth_calib)
    check("calib: synthetic_only does not write-enable", synth_calib.get("artifact_write_ready") is False)
    check("calib: synthetic_only does not display-enable", synth_calib.get("ui_display_ready") is False)
    check("calib: private run still not_run", synth_calib.get("private_operator_judge_calibration_run") == "not_run")
    check(
        "calib: shape_ready can be true under synthetic_only",
        synth_calib.get("artifact_shape_ready") is True,
    )

    # operator_validated in a calibration record is never honored / never enables.
    op_calib = adapt_offline_judge_report_to_artifact_payload(
        direct, calibration_record={"calibration_status": "operator_validated"}
    )
    assert_result_shape("calib operator_validated", op_calib)
    check("calib op: warned", "operator_validated_not_allowed_yet" in op_calib.get("warnings", []))
    check("calib op: not operator_validated", op_calib.get("calibration_status") != "operator_validated")
    check("calib op: not write-ready", op_calib.get("artifact_write_ready") is False)
    check("calib op: not display-ready", op_calib.get("ui_display_ready") is False)

    # operator_validated requested on the report itself is also stripped/warned.
    op_report = dict(direct)
    op_report["calibration_status"] = "operator_validated"
    op_report_result = adapt_offline_judge_report_to_artifact_payload(op_report)
    check("report op: not operator_validated", op_report_result.get("calibration_status") != "operator_validated")
    check("report op: warned", "operator_validated_not_allowed_yet" in op_report_result.get("warnings", []))

    # A private-shaped / non-closed calibration record is stripped + warned, never
    # enabling readiness.
    private_calib = adapt_offline_judge_report_to_artifact_payload(
        direct,
        calibration_record={
            "operator_notes": "PRIVATE_NOTE_SYNTHETIC_ADAPTER_MARKER",
            "source_text": "SOURCE_TEXT_SYNTHETIC_ADAPTER_MARKER",
        },
    )
    assert_result_shape("calib private", private_calib)
    check("calib private: stripped warning", "calibration_record_stripped" in private_calib.get("warnings", []))
    check("calib private: not write-ready", private_calib.get("artifact_write_ready") is False)
    check("calib private: not display-ready", private_calib.get("ui_display_ready") is False)

    # --- 9. Deterministic floor red cannot become ok / write / display --------
    floor_payload_red = adapt_offline_judge_report_to_artifact_payload(
        run_synthetic_offline_judge_case("clean_synthetic_judge_case"),
        deterministic_floor_payload={"safety_floor_green": False},
    )
    assert_result_shape("floor override clean", floor_payload_red)
    check("floor override: floor blocked wins", floor_payload_red["artifact_payload"].get("deterministic_floor_status") == "blocked")
    check("floor override: deterministic_floor_red blocker", "deterministic_floor_red" in floor_payload_red.get("blockers", []))
    check("floor override: status not ok", floor_payload_red.get("status") != "ok")
    check("floor override: not write-ready", floor_payload_red.get("artifact_write_ready") is False)
    check("floor override: not display-ready", floor_payload_red.get("ui_display_ready") is False)

    # --- 10. Forbidden fields stripped / counted ------------------------------
    forbidden_report: dict[str, Any] = dict(run_synthetic_offline_judge_case("clean_synthetic_judge_case"))
    for field in FORBIDDEN_FIELDS:
        forbidden_report[field] = f"FORBIDDEN_{field}_SYNTHETIC_ADAPTER_MARKER"
    forbidden_result = adapt_offline_judge_report_to_artifact_payload(forbidden_report)
    assert_result_shape("forbidden stripped", forbidden_result)
    check("forbidden: count > 0", forbidden_result["summary"]["forbidden_field_count"] > 0)
    check("forbidden: stripped warning", "forbidden_field_stripped" in forbidden_result.get("warnings", []))
    check(
        "forbidden: no marker survives",
        "SYNTHETIC_ADAPTER_MARKER" not in serialize_offline_judge_artifact_payload(forbidden_result),
    )

    # --- 11. Import hygiene / purity guard ------------------------------------
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    check("purity: imports whitelisted", imported.issubset(ALLOWED_IMPORTS), str(imported - ALLOWED_IMPORTS))
    lowered = source.lower()
    bad_parts = [p for p in FORBIDDEN_IMPORT_PARTS if f"import {p}" in lowered or f"from {p}" in lowered]
    check("purity: no forbidden runtime imports", not bad_parts, str(bad_parts))
    check(
        "purity: no filesystem/provider/network call tokens",
        not any(
            tok in lowered
            for tok in ("open(", "requests.", "httpx.", "subprocess.", "socket.", ".read_text(", ".write_text(", "urllib")
        ),
    )

    print(f"\ntest_quality_safety_offline_judge_artifact_adapter: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
