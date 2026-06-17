#!/usr/bin/env python3
"""Tests for Slice 142 offline judge schema fixtures + synthetic harness.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, model
prompts/responses, paths, URLs, images, PDFs, DOCX files, ZIPs, or runtime
artifacts. Hostile canaries are synthetic markers used only to prove forbidden
content is stripped. No judge runs; no provider/model/cloud/local-LLM is called;
no files are read or written.

Run:  python test_scripts/test_quality_safety_offline_judge_schema.py
"""
from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

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
    SYNTHETIC_FIXTURE_IDS,
    VERSION,
    WARNING_TOKENS,
    build_empty_offline_judge_report,
    build_synthetic_offline_judge_fixture,
    normalize_offline_judge_report,
    serialize_offline_judge_report,
    validate_offline_judge_report,
)

PASS = 0
FAIL = 0

MODULE_PATH = REPO / "pipeline" / "quality_safety_offline_judge_schema.py"

HOSTILE_CANARIES = (
    "ZZSYNTH_JUDGE_PRIVATE_MARKER_ONLY",
    "RAW_TEXT_SYNTHETIC_JUDGE_MARKER",
    "SOURCE_TEXT_SYNTHETIC_JUDGE_MARKER",
    "OCR_TEXT_SYNTHETIC_JUDGE_MARKER",
    "TABLE_CELL_SYNTHETIC_JUDGE_MARKER",
    "CAPTION_SYNTHETIC_JUDGE_MARKER",
    "EVIDENCE_QUOTE_SYNTHETIC_JUDGE_MARKER",
    "FREE_TEXT_RATIONALE_SYNTHETIC_JUDGE_MARKER",
    "PRIVATE_RATIONALE_SYNTHETIC_JUDGE_MARKER",
    "CHAIN_OF_THOUGHT_SYNTHETIC_JUDGE_MARKER",
    "PROVIDER_PAYLOAD_SYNTHETIC_JUDGE_MARKER",
    "MODEL_PROMPT_SYNTHETIC_JUDGE_MARKER",
    "MODEL_RESPONSE_SYNTHETIC_JUDGE_MARKER",
    "QUALITY_JUDGE_DUMP_SYNTHETIC_JUDGE_MARKER",
    "NN3_JSON_SYNTHETIC_JUDGE_MARKER",
    "JUDGE_RESPONSE_NN3_SYNTHETIC_JUDGE_MARKER",
    "QUALITY_JSONL_SYNTHETIC_JUDGE_MARKER",
    "UPLOADED_SYNTHETIC_JUDGE_FILENAME",
    "/home/fake_private/synthetic-source.pdf",
    "https://private.invalid/synthetic-judge",
    "E=mc^2_synthetic_judge_marker",
    "synthetic-source.pdf",
    "FREE_TEXT_NOT_A_TOKEN",
    "NOT_A_BLOCKER_TOKEN",
)
FORBIDDEN_MARKERS = (
    "SYNTHETIC_JUDGE_MARKER",
    "/home/",
    "https://",
    ".pdf",
    ".docx",
    ".zip",
    "E=mc",
    "Bearer",
    "Authorization",
)

ALLOWED_IMPORTS = {"__future__", "json", "re", "typing"}
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


def assert_no_canary(name: str, node: Any) -> None:
    blob = serialize_offline_judge_report(node)
    found = [marker for marker in FORBIDDEN_MARKERS if marker in blob]
    found += [canary for canary in HOSTILE_CANARIES if canary in blob]
    check(f"{name}: no hostile canary", not found, str(found))


def assert_report_shape(name: str, report: dict[str, Any]) -> None:
    result = validate_offline_judge_report(report)
    check(f"{name}: valid", result["valid"], str(result["violations"]))
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
    check(
        f"{name}: floor closed",
        report.get("deterministic_floor_status") in DETERMINISTIC_FLOOR_STATUSES,
    )
    check(f"{name}: blockers closed", all(b in BLOCKER_TOKENS for b in report.get("blockers", [])))
    check(f"{name}: warnings closed", all(w in WARNING_TOKENS for w in report.get("warnings", [])))
    check(f"{name}: no forbidden field", not any(f in report for f in FORBIDDEN_FIELDS))
    for axis in report.get("axis_results", []):
        check(f"{name}: axis name", axis.get("axis") in ALLOWED_AXES, str(axis.get("axis")))
        check(f"{name}: axis status", axis.get("status") in AXIS_STATUSES, str(axis.get("status")))
        check(f"{name}: axis confidence", axis.get("confidence") in CONFIDENCE_VALUES)
        check(f"{name}: axis score_band", axis.get("score_band") in SCORE_BANDS)
        check(
            f"{name}: axis counts non-negative ints",
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
    # --- 1. Empty / malformed / wrong-kind payloads degrade safely ------------
    empty = build_empty_offline_judge_report()
    assert_report_shape("empty", empty)
    check("empty: skipped", empty.get("status") == "skipped")
    check("empty: component_missing", empty.get("warnings") == ["component_missing"])

    none_report = normalize_offline_judge_report(None)
    assert_report_shape("none", none_report)
    check("none: skipped", none_report.get("status") == "skipped")
    check("none: component_missing", "component_missing" in none_report.get("warnings", []))

    nondict = normalize_offline_judge_report(123)
    assert_report_shape("non-dict", nondict)
    check("non-dict: malformed warning", "malformed_report_input" in nondict.get("warnings", []))

    wrong_kind = normalize_offline_judge_report({"kind": "not_the_judge", "advisory": True})
    assert_report_shape("wrong kind", wrong_kind)
    check("wrong kind: failed", wrong_kind.get("status") == "failed")
    check("wrong kind: wrong_kind warning", "wrong_kind" in wrong_kind.get("warnings", []))

    # --- 2. advisory normalized to true ---------------------------------------
    not_advisory = normalize_offline_judge_report({"kind": KIND, "advisory": False})
    assert_report_shape("not advisory", not_advisory)
    check("not advisory: advisory normalized", not_advisory.get("advisory") is True)
    check("not advisory: warning", "advisory_normalized" in not_advisory.get("warnings", []))

    missing_advisory = normalize_offline_judge_report({"kind": KIND})
    check("missing advisory: advisory normalized", missing_advisory.get("advisory") is True)
    check("missing advisory: warning", "advisory_normalized" in missing_advisory.get("warnings", []))

    # --- 3. judge_ready / repair_ready always false ---------------------------
    forced = normalize_offline_judge_report(
        {"kind": KIND, "advisory": True, "judge_ready": True, "repair_ready": True}
    )
    assert_report_shape("forced ready", forced)
    check("forced: judge_ready false", forced.get("judge_ready") is False)
    check("forced: repair_ready false", forced.get("repair_ready") is False)

    # --- 4. Allowed axes accepted; unknown dropped; duplicates deduplicated ----
    allowed = normalize_offline_judge_report(
        {
            "kind": KIND,
            "advisory": True,
            "axis_results": [{"axis": axis, "status": "pass"} for axis in ALLOWED_AXES],
        }
    )
    assert_report_shape("allowed axes", allowed)
    check("allowed axes: count", allowed["summary"]["axis_count"] == len(ALLOWED_AXES))
    check("allowed axes: pass_count", allowed["summary"]["pass_count"] == len(ALLOWED_AXES))

    unknown_axis = normalize_offline_judge_report(
        {
            "kind": KIND,
            "advisory": True,
            "axis_results": [
                {"axis": "correctness", "status": "pass"},
                {"axis": "made_up_axis", "status": "pass"},
                {"axis": 123, "status": "pass"},
            ],
        }
    )
    assert_report_shape("unknown axis", unknown_axis)
    check("unknown axis: only known kept", unknown_axis["summary"]["axis_count"] == 1)
    check("unknown axis: dropped warning", "unknown_axis_dropped" in unknown_axis.get("warnings", []))

    duplicate_axis = normalize_offline_judge_report(
        {
            "kind": KIND,
            "advisory": True,
            "axis_results": [
                {"axis": "correctness", "status": "pass"},
                {"axis": "correctness", "status": "fail"},
            ],
        }
    )
    assert_report_shape("duplicate axis", duplicate_axis)
    check("duplicate axis: deduplicated", duplicate_axis["summary"]["axis_count"] == 1)
    check(
        "duplicate axis: keeps first (pass)",
        duplicate_axis["axis_results"][0]["status"] == "pass",
    )
    check(
        "duplicate axis: warning",
        "duplicate_axis_deduplicated" in duplicate_axis.get("warnings", []),
    )
    # Deterministic: same input -> same output regardless of run.
    duplicate_axis_again = normalize_offline_judge_report(
        {
            "kind": KIND,
            "advisory": True,
            "axis_results": [
                {"axis": "correctness", "status": "pass"},
                {"axis": "correctness", "status": "fail"},
            ],
        }
    )
    check(
        "duplicate axis: deterministic",
        serialize_offline_judge_report(duplicate_axis)
        == serialize_offline_judge_report(duplicate_axis_again),
    )

    # --- 5. Unknown axis status/confidence/score_band normalized safely -------
    bad_enums = normalize_offline_judge_report(
        {
            "kind": KIND,
            "advisory": True,
            "axis_results": [
                {
                    "axis": "completeness",
                    "status": "totally_made_up",
                    "confidence": "ultra",
                    "score_band": "godlike",
                }
            ],
        }
    )
    assert_report_shape("bad enums", bad_enums)
    axis = bad_enums["axis_results"][0]
    check("bad enums: status not_observed", axis["status"] == "not_observed")
    check("bad enums: confidence unknown", axis["confidence"] == "unknown")
    check("bad enums: score_band unknown", axis["score_band"] == "unknown")
    check(
        "bad enums: status warning",
        "invalid_axis_status_normalized" in bad_enums.get("warnings", []),
    )
    check(
        "bad enums: confidence warning",
        "invalid_confidence_normalized" in bad_enums.get("warnings", []),
    )
    check(
        "bad enums: score_band warning",
        "invalid_score_band_normalized" in bad_enums.get("warnings", []),
    )

    # --- 6. Counts non-negative ints only -------------------------------------
    bad_counts = normalize_offline_judge_report(
        {
            "kind": KIND,
            "advisory": True,
            "axis_results": [
                {
                    "axis": "exam_readiness",
                    "status": "pass",
                    "counts": {
                        "observation_count": 3,
                        "fail_count": -1,
                        "warning_count": True,
                        "checked_count": 2.5,
                        "not_a_count_key": 9,
                    },
                }
            ],
        }
    )
    assert_report_shape("bad counts", bad_counts)
    counts = bad_counts["axis_results"][0]["counts"]
    check("bad counts: only valid kept", counts == {"observation_count": 3}, str(counts))
    check("bad counts: warning", "invalid_count_dropped" in bad_counts.get("warnings", []))

    # --- 7. Blockers / warnings closed-token only -----------------------------
    bad_tokens = normalize_offline_judge_report(
        {
            "kind": KIND,
            "advisory": True,
            "warnings": ["weak_band", "FREE_TEXT_RATIONALE_SYNTHETIC_JUDGE_MARKER"],
            "blockers": ["leak_detected", "NOT_A_BLOCKER_TOKEN"],
        }
    )
    assert_report_shape("bad tokens", bad_tokens)
    check("bad tokens: free-text warning dropped", "weak_band" in bad_tokens.get("warnings", []))
    check(
        "bad tokens: invalid warning dropped flag",
        "invalid_warning_token_dropped" in bad_tokens.get("warnings", []),
    )
    check("bad tokens: leak_detected kept", "leak_detected" in bad_tokens.get("blockers", []))
    check(
        "bad tokens: invalid blocker dropped flag",
        "invalid_blocker_token_dropped" in bad_tokens.get("warnings", []),
    )
    check(
        "bad tokens: only closed blockers",
        all(b in BLOCKER_TOKENS for b in bad_tokens.get("blockers", [])),
    )

    # --- 8. operator_validated rejected in this slice -------------------------
    op_validated = normalize_offline_judge_report(
        {"kind": KIND, "advisory": True, "calibration_status": "operator_validated"}
    )
    assert_report_shape("operator_validated input", op_validated)
    check(
        "operator_validated: downgraded",
        op_validated.get("calibration_status") != "operator_validated",
    )
    check(
        "operator_validated: warning",
        "operator_validated_not_allowed_yet" in op_validated.get("warnings", []),
    )

    bad_cal = normalize_offline_judge_report(
        {"kind": KIND, "advisory": True, "calibration_status": "made_up"}
    )
    check("bad calibration: not_started", bad_cal.get("calibration_status") == "not_started")
    check(
        "bad calibration: warning",
        "calibration_status_normalized" in bad_cal.get("warnings", []),
    )

    # --- 9. Forbidden fields stripped (top-level and axis-level) --------------
    forbidden_payload: dict[str, Any] = {"kind": KIND, "advisory": True}
    for field in FORBIDDEN_FIELDS:
        forbidden_payload[field] = f"FORBIDDEN_{field}_SYNTHETIC_JUDGE_MARKER"
    forbidden_payload["axis_results"] = [
        {
            "axis": "leakage_privacy_safety",
            "status": "fail",
            **{f: "AXIS_FORBIDDEN_SYNTHETIC_JUDGE_MARKER" for f in FORBIDDEN_FIELDS},
        }
    ]
    stripped = normalize_offline_judge_report(forbidden_payload)
    assert_report_shape("forbidden stripped", stripped)
    check(
        "forbidden stripped: no forbidden top-level field",
        not any(f in stripped for f in FORBIDDEN_FIELDS),
    )
    check(
        "forbidden stripped: no forbidden axis field",
        not any(f in stripped["axis_results"][0] for f in FORBIDDEN_FIELDS),
    )
    check(
        "forbidden stripped: warning",
        "forbidden_field_stripped" in stripped.get("warnings", []),
    )
    blob = serialize_offline_judge_report(stripped)
    check(
        "forbidden stripped: no forbidden marker survives",
        "SYNTHETIC_JUDGE_MARKER" not in blob,
        blob[:200],
    )

    # --- 10. Synthetic fixtures validate + expected behavior ------------------
    check("fixture ids exposed", set(SYNTHETIC_FIXTURE_IDS) == {
        "clean_synthetic_judge_case",
        "weak_synthetic_judge_case",
        "failed_synthetic_judge_case",
        "leak_canary_synthetic_judge_case",
        "deterministic_floor_red_synthetic_judge_case",
    })

    for case_id in SYNTHETIC_FIXTURE_IDS:
        fixture = build_synthetic_offline_judge_fixture(case_id)
        floor_payload = (
            {"safety_floor_green": False}
            if case_id == "deterministic_floor_red_synthetic_judge_case"
            else None
        )
        before = copy.deepcopy(fixture)
        report = normalize_offline_judge_report(fixture, deterministic_floor_payload=floor_payload)
        check(f"{case_id}: input not mutated", fixture == before)
        assert_report_shape(case_id, report)
        check(f"{case_id}: judge_ready false", report.get("judge_ready") is False)
        check(f"{case_id}: repair_ready false", report.get("repair_ready") is False)
        check(
            f"{case_id}: calibration not operator_validated",
            report.get("calibration_status") != "operator_validated",
        )
        # Deterministic serialization across repeated normalization.
        report_again = normalize_offline_judge_report(
            build_synthetic_offline_judge_fixture(case_id), deterministic_floor_payload=floor_payload
        )
        check(
            f"{case_id}: deterministic serialization",
            serialize_offline_judge_report(report) == serialize_offline_judge_report(report_again),
        )

    clean = normalize_offline_judge_report(
        build_synthetic_offline_judge_fixture("clean_synthetic_judge_case")
    )
    check("clean: status ok", clean.get("status") == "ok", str(clean.get("status")))
    check("clean: no blockers", clean.get("blockers") == [])
    check("clean: calibration synthetic_only", clean.get("calibration_status") == "synthetic_only")
    check("clean: privacy ok", clean.get("privacy_status") == "ok")

    weak = normalize_offline_judge_report(
        build_synthetic_offline_judge_fixture("weak_synthetic_judge_case")
    )
    check("weak: status warning", weak.get("status") == "warning", str(weak.get("status")))
    check("weak: no blockers", weak.get("blockers") == [])

    failed = normalize_offline_judge_report(
        build_synthetic_offline_judge_fixture("failed_synthetic_judge_case")
    )
    check("failed: status failed", failed.get("status") == "failed")
    check("failed: axis_failed blocker", "axis_failed" in failed.get("blockers", []))
    check("failed: fail_count > 0", failed["summary"]["fail_count"] > 0)

    leak = normalize_offline_judge_report(
        build_synthetic_offline_judge_fixture("leak_canary_synthetic_judge_case")
    )
    assert_no_canary("leak fixture", leak)
    check("leak: privacy not ok", leak.get("privacy_status") in {"warning", "failed"})
    check("leak: forbidden field warning", "forbidden_field_stripped" in leak.get("warnings", []))
    check("leak: judge_ready false", leak.get("judge_ready") is False)

    floor_red = normalize_offline_judge_report(
        build_synthetic_offline_judge_fixture("deterministic_floor_red_synthetic_judge_case"),
        deterministic_floor_payload={"safety_floor_green": False},
    )
    check("floor red: status failed", floor_red.get("status") == "failed")
    check("floor red: floor blocked", floor_red.get("deterministic_floor_status") == "blocked")
    check(
        "floor red: deterministic_floor_red blocker",
        "deterministic_floor_red" in floor_red.get("blockers", []),
    )
    check("floor red: judge_ready false", floor_red.get("judge_ready") is False)
    check("floor red: not ok", floor_red.get("status") != "ok")

    # Floor payload overrides any softer self-reported floor status.
    floor_override = normalize_offline_judge_report(
        {"kind": KIND, "advisory": True, "deterministic_floor_status": "ready_for_cleanup_freeze"},
        deterministic_floor_payload={"safety_floor_green": False},
    )
    check("floor override: blocked wins", floor_override.get("deterministic_floor_status") == "blocked")
    check(
        "floor override: blocker present",
        "deterministic_floor_red" in floor_override.get("blockers", []),
    )

    # --- 11. Deterministic serialization is stable / sorted -------------------
    check(
        "serialize: sorted keys deterministic",
        serialize_offline_judge_report({"b": 1, "a": 2})
        == serialize_offline_judge_report({"a": 2, "b": 1}),
    )

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
    bad_parts = [part for part in FORBIDDEN_IMPORT_PARTS if f"import {part}" in lowered or f"from {part}" in lowered]
    check("purity: no forbidden runtime imports", not bad_parts, str(bad_parts))
    check(
        "purity: no filesystem/provider call tokens",
        not any(
            tok in lowered for tok in ("open(", "requests.", "httpx.", "subprocess.", "socket.")
        ),
    )

    print(f"\ntest_quality_safety_offline_judge_schema: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
