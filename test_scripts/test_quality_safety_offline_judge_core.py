#!/usr/bin/env python3
"""Tests for Slice 143 offline judge core v1 (synthetic / caller-supplied only).

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, model
prompts/responses, paths, URLs, images, PDFs, DOCX files, ZIPs, or runtime
artifacts. Hostile canaries are synthetic markers used only to prove forbidden
content is stripped. No judge runs; no provider/model/cloud/local-LLM is called;
no files are read or written.

Run:  python test_scripts/test_quality_safety_offline_judge_core.py
"""
from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_offline_judge_core import (  # noqa: E402
    SYNTHETIC_CASE_IDS,
    build_empty_offline_judge_core_result,
    build_offline_judge_report_from_observations,
    build_synthetic_offline_judge_observations,
    normalize_offline_judge_observations,
    run_synthetic_offline_judge_case,
)
from pipeline.quality_safety_offline_judge_schema import (  # noqa: E402
    ALLOWED_AXES,
    AXIS_STATUSES,
    AXIS_WARNING_TOKENS,
    BLOCKER_TOKENS,
    CALIBRATION_STATUSES,
    CONFIDENCE_VALUES,
    COUNT_KEYS,
    DETERMINISTIC_FLOOR_STATUSES,
    FORBIDDEN_FIELDS,
    INPUT_SCOPES,
    JUDGE_MODEL_KINDS,
    KIND,
    PRIVACY_STATUSES,
    REPORT_STATUSES,
    SCORE_BANDS,
    VERSION,
    WARNING_TOKENS,
    serialize_offline_judge_report,
    validate_offline_judge_report,
)

PASS = 0
FAIL = 0

MODULE_PATH = REPO / "pipeline" / "quality_safety_offline_judge_core.py"

FORBIDDEN_MARKERS = (
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

# The core may import the Slice 142 schema module and stdlib typing only.
ALLOWED_IMPORTS = {
    "__future__",
    "typing",
    "pipeline.quality_safety_offline_judge_schema",
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
    "json",
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


def assert_no_canary(name: str, report: dict[str, Any]) -> None:
    blob = serialize_offline_judge_report(report)
    found = [marker for marker in FORBIDDEN_MARKERS if marker in blob]
    check(f"{name}: no hostile canary", not found, str(found))


def assert_report_shape(name: str, report: dict[str, Any]) -> None:
    result = validate_offline_judge_report(report)
    check(f"{name}: schema valid", result["valid"], str(result["violations"]))
    check(f"{name}: version", report.get("version") == VERSION)
    check(f"{name}: kind", report.get("kind") == KIND)
    check(f"{name}: advisory true", report.get("advisory") is True)
    check(f"{name}: status closed", report.get("status") in REPORT_STATUSES, str(report.get("status")))
    check(f"{name}: judge_model_kind closed", report.get("judge_model_kind") in JUDGE_MODEL_KINDS)
    check(f"{name}: input_scope closed", report.get("input_scope") in INPUT_SCOPES)
    check(f"{name}: judge_ready false", report.get("judge_ready") is False)
    check(f"{name}: repair_ready false", report.get("repair_ready") is False)
    check(f"{name}: calibration closed", report.get("calibration_status") in CALIBRATION_STATUSES)
    check(f"{name}: not operator_validated", report.get("calibration_status") != "operator_validated")
    check(f"{name}: privacy closed", report.get("privacy_status") in PRIVACY_STATUSES)
    check(f"{name}: floor closed", report.get("deterministic_floor_status") in DETERMINISTIC_FLOOR_STATUSES)
    check(f"{name}: blockers closed", all(b in BLOCKER_TOKENS for b in report.get("blockers", [])))
    check(f"{name}: warnings closed", all(w in WARNING_TOKENS for w in report.get("warnings", [])))
    check(f"{name}: no forbidden field", not any(f in report for f in FORBIDDEN_FIELDS))
    expected_summary = {
        "axis_count", "pass_count", "warning_count", "fail_count",
        "not_observed_count", "blocker_count",
    }
    summary = report.get("summary")
    check(f"{name}: summary keys", isinstance(summary, dict) and set(summary) == expected_summary)
    for axis in report.get("axis_results", []):
        check(f"{name}: axis name", axis.get("axis") in ALLOWED_AXES, str(axis.get("axis")))
        check(f"{name}: axis status", axis.get("status") in AXIS_STATUSES)
        check(f"{name}: axis confidence", axis.get("confidence") in CONFIDENCE_VALUES)
        check(f"{name}: axis score_band", axis.get("score_band") in SCORE_BANDS)
        check(
            f"{name}: axis counts ok",
            isinstance(axis.get("counts"), dict)
            and all(
                k in COUNT_KEYS and isinstance(v, int) and not isinstance(v, bool) and v >= 0
                for k, v in axis["counts"].items()
            ),
            str(axis.get("counts")),
        )
        check(
            f"{name}: axis warnings closed",
            all(w in AXIS_WARNING_TOKENS for w in axis.get("warnings", [])),
            str(axis.get("warnings")),
        )
        check(f"{name}: axis no forbidden field", not any(f in axis for f in FORBIDDEN_FIELDS))
    assert_no_canary(name, report)


def main() -> int:
    # --- 1. Empty / malformed observations degrade safely ---------------------
    empty = build_empty_offline_judge_core_result()
    assert_report_shape("empty", empty)
    check("empty: skipped", empty.get("status") == "skipped")

    for bad in (None, 123, "string", [], {"axis_observations": "not_a_list"}):
        report = build_offline_judge_report_from_observations(bad)
        assert_report_shape(f"malformed {bad!r}", report)
        check(f"malformed {bad!r}: judge_ready false", report.get("judge_ready") is False)

    no_axes = build_offline_judge_report_from_observations(
        {"judge_model_kind": "synthetic", "input_scope": "synthetic", "axis_observations": []}
    )
    assert_report_shape("no axes", no_axes)
    check("no axes: skipped", no_axes.get("status") == "skipped")

    # --- 2. Valid clean synthetic observations produce a normalized report ----
    clean_obs = build_synthetic_offline_judge_observations("clean_synthetic_judge_case")
    before = copy.deepcopy(clean_obs)
    clean = build_offline_judge_report_from_observations(clean_obs)
    check("clean: input not mutated", clean_obs == before)
    assert_report_shape("clean", clean)
    check("clean: status ok", clean.get("status") == "ok", str(clean.get("status")))
    check("clean: no blockers", clean.get("blockers") == [])
    check("clean: calibration synthetic_only", clean.get("calibration_status") == "synthetic_only")
    check("clean: privacy ok", clean.get("privacy_status") == "ok")

    # --- 3. All eight axes handled --------------------------------------------
    all_axes_obs = {
        "judge_model_kind": "synthetic",
        "input_scope": "synthetic",
        "axis_observations": [
            {"axis": axis, "signals": {"pass_count": 1}, "confidence": "high"}
            for axis in ALLOWED_AXES
        ],
    }
    all_axes = build_offline_judge_report_from_observations(all_axes_obs)
    assert_report_shape("all axes", all_axes)
    check("all axes: count == 8", all_axes["summary"]["axis_count"] == len(ALLOWED_AXES))
    check("all axes: all pass", all_axes["summary"]["pass_count"] == len(ALLOWED_AXES))
    seen = {a["axis"] for a in all_axes["axis_results"]}
    check("all axes: all distinct present", seen == set(ALLOWED_AXES))

    # --- 4. Unknown axes dropped/warned; duplicates collapsed -----------------
    unknown_obs = {
        "axis_observations": [
            {"axis": "correctness", "signals": {"pass_count": 1}},
            {"axis": "made_up_axis", "signals": {"pass_count": 1}},
            {"axis": 999, "signals": {"pass_count": 1}},
            {"axis": "correctness", "signals": {"fail_count": 1}},
        ]
    }
    unknown = build_offline_judge_report_from_observations(unknown_obs)
    assert_report_shape("unknown axes", unknown)
    check("unknown axes: only known kept", unknown["summary"]["axis_count"] == 1)
    check(
        "unknown axes: duplicate collapsed to first (pass)",
        unknown["axis_results"][0]["status"] == "pass",
    )

    # Observation-level normalization also drops unknown axes.
    norm_obs = normalize_offline_judge_observations(unknown_obs)
    check("normalize_observations: one axis", len(norm_obs["axis_observations"]) == 1)
    check(
        "normalize_observations: axis is correctness",
        norm_obs["axis_observations"][0]["axis"] == "correctness",
    )

    # --- 5. Deterministic axis rules ------------------------------------------
    rules_obs = {
        "axis_observations": [
            {"axis": "correctness", "signals": {"fail_count": 1, "pass_count": 5}, "confidence": "high"},
            {"axis": "completeness", "signals": {"warning_count": 1}, "confidence": "low"},
            {"axis": "exam_readiness", "signals": {"warning_count": 1}, "confidence": "high"},
            {"axis": "math_numeric_safety", "signals": {"pass_count": 2}, "confidence": "high"},
            {"axis": "citation_traceability", "signals": {"pass_count": 2}, "confidence": "medium"},
            {"axis": "source_grounding", "signals": {}, "confidence": "unknown"},
        ]
    }
    rules = build_offline_judge_report_from_observations(rules_obs)
    assert_report_shape("axis rules", rules)
    by_axis = {a["axis"]: a for a in rules["axis_results"]}
    # fail dominates even with passes present.
    check("rule: fail -> fail/failed",
          by_axis["correctness"]["status"] == "fail" and by_axis["correctness"]["score_band"] == "failed")
    # warning + low confidence -> weak band.
    check("rule: warning+low -> warning/weak",
          by_axis["completeness"]["status"] == "warning" and by_axis["completeness"]["score_band"] == "weak")
    # warning + high confidence -> acceptable band.
    check("rule: warning+high -> warning/acceptable",
          by_axis["exam_readiness"]["status"] == "warning" and by_axis["exam_readiness"]["score_band"] == "acceptable")
    # pass + high -> strong.
    check("rule: pass+high -> pass/strong",
          by_axis["math_numeric_safety"]["status"] == "pass" and by_axis["math_numeric_safety"]["score_band"] == "strong")
    # pass + medium -> acceptable.
    check("rule: pass+medium -> pass/acceptable",
          by_axis["citation_traceability"]["status"] == "pass" and by_axis["citation_traceability"]["score_band"] == "acceptable")
    # no signals -> not_observed/unknown.
    check("rule: none -> not_observed/unknown",
          by_axis["source_grounding"]["status"] == "not_observed" and by_axis["source_grounding"]["score_band"] == "unknown")
    check("rule: not_observed warning surfaced",
          "not_observed_axis" in by_axis["source_grounding"]["warnings"])
    check("rule: low confidence warning surfaced",
          "low_confidence" in by_axis["completeness"]["warnings"])

    # --- 6. Summary counts correct --------------------------------------------
    check("summary: axis_count", rules["summary"]["axis_count"] == 6)
    check("summary: fail_count", rules["summary"]["fail_count"] == 1)
    check("summary: warning_count", rules["summary"]["warning_count"] == 2)
    check("summary: pass_count", rules["summary"]["pass_count"] == 2)
    check("summary: not_observed_count", rules["summary"]["not_observed_count"] == 1)
    check("summary: blocker_count matches", rules["summary"]["blocker_count"] == len(rules["blockers"]))

    # --- 7. Blockers / warnings are closed tokens only ------------------------
    token_obs = {
        "axis_observations": [{"axis": "correctness", "signals": {"pass_count": 1}}],
        "warnings": ["weak_band", "FREE_TEXT_NOT_A_TOKEN_CORE"],
        "blockers": ["leak_detected", "NOT_A_BLOCKER_TOKEN_CORE"],
    }
    tokened = build_offline_judge_report_from_observations(token_obs)
    assert_report_shape("token filtering", tokened)
    check("tokens: only closed blockers", all(b in BLOCKER_TOKENS for b in tokened["blockers"]))
    check("tokens: only closed warnings", all(w in WARNING_TOKENS for w in tokened["warnings"]))
    check("tokens: leak_detected kept", "leak_detected" in tokened["blockers"])
    check("tokens: free-text blocker dropped", "NOT_A_BLOCKER_TOKEN_CORE" not in serialize_offline_judge_report(tokened))

    # --- 8. Forbidden fields stripped (observation and axis level) ------------
    forbidden_obs: dict[str, Any] = {
        "axis_observations": [
            {
                "axis": "leakage_privacy_safety",
                "signals": {"fail_count": 1},
                **{f: "AXIS_FORBIDDEN_SYNTHETIC_CORE_MARKER" for f in FORBIDDEN_FIELDS},
            }
        ],
    }
    for field in FORBIDDEN_FIELDS:
        forbidden_obs[field] = f"FORBIDDEN_{field}_SYNTHETIC_CORE_MARKER"
    stripped = build_offline_judge_report_from_observations(forbidden_obs)
    assert_report_shape("forbidden stripped", stripped)
    check("forbidden: no forbidden top-level field", not any(f in stripped for f in FORBIDDEN_FIELDS))
    check(
        "forbidden: no forbidden axis field",
        not any(f in stripped["axis_results"][0] for f in FORBIDDEN_FIELDS),
    )
    blob = serialize_offline_judge_report(stripped)
    check("forbidden: no marker survives", "SYNTHETIC_CORE_MARKER" not in blob, blob[:200])
    check(
        "forbidden: forbidden_field_stripped warning",
        "forbidden_field_stripped" in stripped.get("warnings", [])
        or "forbidden_field_stripped" in stripped["axis_results"][0].get("warnings", []),
    )

    # --- 9. Synthetic cases via run_synthetic_offline_judge_case --------------
    check("case ids exposed", set(SYNTHETIC_CASE_IDS) == {
        "clean_synthetic_judge_case",
        "weak_synthetic_judge_case",
        "failed_synthetic_judge_case",
        "leak_canary_synthetic_judge_case",
        "deterministic_floor_red_synthetic_judge_case",
    })

    for case_id in SYNTHETIC_CASE_IDS:
        obs = build_synthetic_offline_judge_observations(case_id)
        before = copy.deepcopy(obs)
        report = run_synthetic_offline_judge_case(case_id)
        check(f"{case_id}: input not mutated", build_synthetic_offline_judge_observations(case_id) == before)
        assert_report_shape(case_id, report)
        check(f"{case_id}: judge_ready false", report.get("judge_ready") is False)
        check(f"{case_id}: repair_ready false", report.get("repair_ready") is False)
        # Deterministic serialization across repeated runs.
        again = run_synthetic_offline_judge_case(case_id)
        check(
            f"{case_id}: deterministic serialization",
            serialize_offline_judge_report(report) == serialize_offline_judge_report(again),
        )

    weak = run_synthetic_offline_judge_case("weak_synthetic_judge_case")
    check("weak: status warning", weak.get("status") == "warning", str(weak.get("status")))
    check("weak: no blockers", weak.get("blockers") == [])
    check(
        "weak: weak/acceptable bands present",
        any(a["score_band"] in {"weak", "acceptable"} for a in weak["axis_results"]),
    )

    failed = run_synthetic_offline_judge_case("failed_synthetic_judge_case")
    check("failed: status failed/partial", failed.get("status") in {"failed", "partial"})
    check("failed: axis_failed blocker", "axis_failed" in failed.get("blockers", []))
    check("failed: blockers present", bool(failed.get("blockers")))

    leak = run_synthetic_offline_judge_case("leak_canary_synthetic_judge_case")
    assert_no_canary("leak", leak)
    check("leak: privacy not ok", leak.get("privacy_status") in {"warning", "failed"})
    check("leak: judge_ready false", leak.get("judge_ready") is False)
    check("leak: status not ok", leak.get("status") != "ok")

    floor_red = run_synthetic_offline_judge_case("deterministic_floor_red_synthetic_judge_case")
    check("floor red: floor blocked", floor_red.get("deterministic_floor_status") == "blocked")
    check("floor red: deterministic_floor_red blocker",
          "deterministic_floor_red" in floor_red.get("blockers", []))
    check("floor red: status not ok", floor_red.get("status") != "ok")
    check("floor red: judge_ready false", floor_red.get("judge_ready") is False)

    # --- 10. Floor-red payload cannot be overridden by clean observations -----
    override = build_offline_judge_report_from_observations(
        {"axis_observations": [{"axis": "correctness", "signals": {"pass_count": 9}, "confidence": "high"}]},
        deterministic_floor_payload={"safety_floor_green": False},
    )
    assert_report_shape("floor override", override)
    check("override: floor blocked wins", override.get("deterministic_floor_status") == "blocked")
    check("override: deterministic_floor_red blocker",
          "deterministic_floor_red" in override.get("blockers", []))
    check("override: status not ok despite all-pass axes", override.get("status") != "ok")
    check("override: judge_ready false", override.get("judge_ready") is False)

    # --- 11. operator_validated cannot be claimed ----------------------------
    op = build_offline_judge_report_from_observations(
        {"axis_observations": [{"axis": "correctness", "signals": {"pass_count": 1}}],
         "calibration_status": "operator_validated"}
    )
    check("operator_validated: downgraded", op.get("calibration_status") != "operator_validated")

    # --- 12. Import hygiene / purity guard ------------------------------------
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
        not any(tok in lowered for tok in ("open(", "requests.", "httpx.", "subprocess.", "socket.", ".read_text(", ".write_text(")),
    )

    print(f"\ntest_quality_safety_offline_judge_core: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
