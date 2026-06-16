#!/usr/bin/env python3
"""Tests for the Slice 108 quality-safety eval harness skeleton.

Synthetic fixture ids and synthetic canaries only. No source decks, reference
files, uploaded specs, private guide snippets, OCR/table/caption text, provider
payloads, PDFs, images, DOCX, ZIPs, generated guide outputs, or runtime eval
outputs are used.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_eval_harness import (  # noqa: E402
    build_quality_safety_regression_record,
    load_quality_safety_fixture_spec,
    run_quality_safety_eval,
    run_quality_safety_layer1_checks,
)

PASS = 0
FAIL = 0

HOSTILE_PATH = "/home/private/synthetic-source.pdf"
HOSTILE_URL = "https://private.invalid/quality-source"
HOSTILE_AUTH = "Authorization: Bearer sk_qualitysafetycanary1234567890"
HOSTILE_DATA = "data:image/png;base64," + ("A" * 140)
HOSTILE_OCR = "OCR_TABLE_CAPTION_PRIVATE_MARKER"
HOSTILE_PROVIDER = "PROVIDER_PAYLOAD_PRIVATE_MARKER"
HOSTILE_CANARIES = [
    HOSTILE_PATH,
    HOSTILE_URL,
    HOSTILE_AUTH,
    HOSTILE_DATA,
    HOSTILE_OCR,
    HOSTILE_PROVIDER,
]
LEAK_PATTERNS = [
    re.compile(r"/home/private"),
    re.compile(r"https?://"),
    re.compile(r"Authorization", re.IGNORECASE),
    re.compile(r"Bearer", re.IGNORECASE),
    re.compile(r"sk_qualitysafetycanary"),
    re.compile(r"data:image"),
    re.compile(r"base64", re.IGNORECASE),
    re.compile(r"OCR_TABLE_CAPTION_PRIVATE_MARKER"),
    re.compile(r"PROVIDER_PAYLOAD_PRIVATE_MARKER"),
]


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)


def base_fixture(**overrides: Any) -> dict[str, Any]:
    fixture = {
        "version": 1,
        "kind": "quality_safety_fixture",
        "lecture_id": "synthetic_eval_fixture",
        "title": "Synthetic Eval Fixture",
        "source_quality": "synthetic",
        "expected_topics": [
            "synthetic activation flow",
            "synthetic gradient descent",
        ],
        "ground_truth_numerics": [
            {"label": "synthetic alpha", "value": 0.20, "tol": 0.01},
        ],
        "min_mock_questions": 2,
        "tier_targets": {"premium": 9.5, "local": 9.0},
    }
    fixture.update(overrides)
    return fixture


def good_candidate() -> str:
    return "\n".join(
        [
            "# Synthetic Guide",
            "The synthetic activation flow connects the first step to the second step.",
            "The synthetic gradient descent topic is covered with a stable update.",
            "synthetic alpha: 0.205",
            "## Worked Answer",
            "Solution: substitute the synthetic value and finish with 0.205.",
            "## Mock Question 1: What is the synthetic alpha value?",
            "Answer: 0.205",
            "## Practice Question 2: Which topic describes the update?",
            "Answer: synthetic gradient descent.",
        ]
    )


def find_in_serialized(node: Any, needle: str) -> bool:
    return needle in json.dumps(node, sort_keys=True)


def no_canary(name: str, node: Any) -> None:
    blob = json.dumps(node, sort_keys=True)
    found = ""
    for canary in HOSTILE_CANARIES:
        if canary in blob:
            found = canary
            break
    if not found:
        for pattern in LEAK_PATTERNS:
            if pattern.search(blob):
                found = pattern.pattern
                break
    check(f"{name}: no hostile canary", not found, found)


def report_check(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    for item in report.get("checks", []):
        if item.get("id") == check_id:
            return item
    raise AssertionError(check_id)


def test_fixture_loader() -> None:
    fixture = load_quality_safety_fixture_spec(base_fixture())
    check("fixture valid kind", fixture["kind"] == "quality_safety_fixture")
    check("fixture valid topics", fixture["expected_topics"] == ["synthetic activation flow", "synthetic gradient descent"])
    check("fixture valid numeric count", len(fixture["ground_truth_numerics"]) == 1)
    check("fixture valid min questions", fixture["min_mock_questions"] == 2)
    check("fixture valid tier target", fixture["tier_targets"]["premium"] == 9.5)
    check("fixture valid no warnings", fixture["warnings"] == [], str(fixture["warnings"]))

    malformed = load_quality_safety_fixture_spec(["not", "a", "mapping"])
    check("fixture malformed degrades", malformed["lecture_id"] == "synthetic_eval_fixture")
    check("fixture malformed warning", malformed["warnings"] == ["malformed_fixture_degraded"], str(malformed["warnings"]))

    hostile = load_quality_safety_fixture_spec(
        base_fixture(
            expected_topics=["synthetic ok topic", HOSTILE_PATH, 99],
            ground_truth_numerics=[
                {"label": HOSTILE_URL, "value": 1.0, "tol": 0.1},
                {"label": "synthetic beta", "value": "wrong", "tol": 0.1},
                {"label": "synthetic gamma", "value": 1.0, "tol": 0.1},
            ],
            min_mock_questions="two",
            tier_targets={"premium": "bad"},
        )
    )
    check("fixture invalid topic dropped", hostile["expected_topics"] == ["synthetic ok topic"], str(hostile["expected_topics"]))
    check("fixture invalid numeric dropped", hostile["ground_truth_numerics"] == [{"label": "synthetic gamma", "value": 1.0, "tol": 0.1}], str(hostile["ground_truth_numerics"]))
    check("fixture invalid min defaulted", hostile["min_mock_questions"] == 0)
    check("fixture invalid tier dropped", hostile["tier_targets"] == {}, str(hostile["tier_targets"]))
    check("fixture warnings closed", set(hostile["warnings"]).issubset({
        "invalid_expected_topic_dropped",
        "invalid_numeric_target_dropped",
        "invalid_min_mock_questions_defaulted",
        "invalid_tier_target_defaulted",
    }), str(hostile["warnings"]))
    no_canary("fixture hostile loader", hostile)

    first = json.dumps(hostile, sort_keys=True)
    second = json.dumps(load_quality_safety_fixture_spec(base_fixture(
        expected_topics=["synthetic ok topic", HOSTILE_PATH, 99],
        ground_truth_numerics=[
            {"label": HOSTILE_URL, "value": 1.0, "tol": 0.1},
            {"label": "synthetic beta", "value": "wrong", "tol": 0.1},
            {"label": "synthetic gamma", "value": 1.0, "tol": 0.1},
        ],
        min_mock_questions="two",
        tier_targets={"premium": "bad"},
    )), sort_keys=True)
    check("fixture deterministic repeated output", first == second)


def test_leaked_reasoning() -> None:
    report = run_quality_safety_layer1_checks(
        "Wait. Actually this is unclear, so we'll trust the value.",
        base_fixture(expected_topics=[], ground_truth_numerics=[], min_mock_questions=0),
    )
    leak = report_check(report, "leaked_reasoning")
    check("leak fails blocking", leak["status"] == "failed" and "leaked_reasoning" in report["blocking_failures"], str(leak))
    check("leak counts only", leak["signal_count"] >= 4 and "matches" not in leak and "line" not in leak, str(leak))
    check("leak output omits matched text", not any(find_in_serialized(report, term) for term in ["Wait", "Actually", "unclear", "we'll trust"]))

    questions = run_quality_safety_layer1_checks(
        "## Mock Question 1: What is synthetic alpha?\nAnswer: 0.20\n## Q2: Why practice?",
        base_fixture(expected_topics=[], ground_truth_numerics=[], min_mock_questions=2),
    )
    leak2 = report_check(questions, "leaked_reasoning")
    check("mock question marks ignored", leak2["structural_uncertainty_count"] == 0, str(leak2))


def test_numeric_correctness() -> None:
    fixture = base_fixture(expected_topics=[], min_mock_questions=0)
    good = run_quality_safety_layer1_checks("synthetic alpha: 0.205", fixture)
    numeric = report_check(good, "numeric_correctness")
    check("numeric within tolerance passes", numeric["status"] == "passed" and numeric["pass_count"] == 1, str(numeric))

    wrong = run_quality_safety_layer1_checks("synthetic alpha: 0.50 and 0.60", fixture)
    numeric_wrong = report_check(wrong, "numeric_correctness")
    check("numeric wrong fails blocking", numeric_wrong["status"] == "failed" and "numeric_correctness" in wrong["blocking_failures"], str(numeric_wrong))
    check("numeric wrong values only", numeric_wrong["targets"][0]["found_values"] == [0.5, 0.6], str(numeric_wrong))
    check("numeric wrong no snippets", not find_in_serialized(numeric_wrong, "and 0.60"))

    absent = run_quality_safety_layer1_checks("no associated label here", fixture)
    numeric_absent = report_check(absent, "numeric_correctness")
    check("numeric absent unknown warning", numeric_absent["status"] == "unknown" and "numeric_target_missing" in absent["warnings"], str(numeric_absent))
    check("numeric no recomputation fields", "formula" not in json.dumps(numeric_absent, sort_keys=True).lower())


def test_worked_answer_completeness() -> None:
    bad = run_quality_safety_layer1_checks(
        "## Worked Answer\nSolution: synthetic alpha = ?",
        base_fixture(expected_topics=[], ground_truth_numerics=[], min_mock_questions=0),
    )
    worked_bad = report_check(bad, "worked_answer_completeness")
    check("worked unresolved fails blocking", worked_bad["status"] == "failed" and "worked_answer_completeness" in bad["blocking_failures"], str(worked_bad))

    good = run_quality_safety_layer1_checks(
        "## Worked Answer\nSolution: synthetic alpha = 0.20. Answer complete.",
        base_fixture(expected_topics=[], ground_truth_numerics=[], min_mock_questions=0),
    )
    worked_good = report_check(good, "worked_answer_completeness")
    check("worked complete passes", worked_good["status"] == "passed", str(worked_good))


def test_coverage() -> None:
    fixture = base_fixture(ground_truth_numerics=[], min_mock_questions=0)
    report = run_quality_safety_layer1_checks(
        "The Synthetic Activation-Flow is explained. Synthetic gradient descent is present.",
        fixture,
    )
    coverage = report_check(report, "coverage")
    check("coverage normalized observed", coverage["status"] == "passed" and coverage["observed_count"] == 2, str(coverage))

    missing = run_quality_safety_layer1_checks("Synthetic activation flow only.", fixture)
    coverage_missing = report_check(missing, "coverage")
    check("coverage missing warns", coverage_missing["status"] == "warning" and "coverage_below_target" in missing["warnings"], str(coverage_missing))
    check("coverage output safe fixture topic only", coverage_missing["missing_topics"] == ["synthetic gradient descent"], str(coverage_missing))
    check("coverage no candidate guide text", not find_in_serialized(coverage_missing, "activation flow only"))


def test_mock_question_count() -> None:
    fixture = base_fixture(expected_topics=[], ground_truth_numerics=[], min_mock_questions=2)
    enough = run_quality_safety_layer1_checks(
        "## Mock Question 1: What?\n## Q2: Why?",
        fixture,
    )
    mock_enough = report_check(enough, "mock_question_count")
    check("mock count meets minimum", mock_enough["status"] == "passed" and mock_enough["mock_question_count"] == 2, str(mock_enough))

    low = run_quality_safety_layer1_checks("## Practice Question 1: What?", fixture)
    mock_low = report_check(low, "mock_question_count")
    check("mock count below advisory warning", mock_low["status"] == "warning" and "mock_question_count_below_minimum" in low["warnings"], str(mock_low))


def test_regression_record() -> None:
    bad_report = run_quality_safety_layer1_checks(
        "Wait. synthetic alpha: 0.50",
        base_fixture(expected_topics=[], min_mock_questions=0),
    )
    record = build_quality_safety_regression_record(
        run_id="synthetic_run",
        git_sha="abc123",
        model="unknown",
        preset="synthetic",
        lecture_id="synthetic_eval_fixture",
        tier="premium",
        layer1_report=bad_report,
    )
    check("record shippable false on blocking", record["shippable"] is False and record["overall_10"] is None)
    check("record copies safe layer1", record["layer1"]["kind"] == "quality_safety_eval_layer1")

    previous_good = build_quality_safety_regression_record(
        run_id="previous",
        layer1_report=run_quality_safety_layer1_checks(good_candidate(), base_fixture()),
        overall_10=9.4,
    )
    current_bad = build_quality_safety_regression_record(
        run_id="current",
        layer1_report=bad_report,
        overall_10=9.2,
        previous_record=previous_good,
    )
    check("record previous shippable to current false regresses", current_bad["regressed"] is True)

    score_drop = build_quality_safety_regression_record(
        run_id="score_drop",
        layer1_report=run_quality_safety_layer1_checks(good_candidate(), base_fixture()),
        overall_10=8.9,
        previous_record=previous_good,
    )
    check("record score drop regresses", score_drop["regressed"] is True and score_drop["delta_vs_prev"] == {"overall_10_delta": -0.5}, str(score_drop["delta_vs_prev"]))

    null_score = build_quality_safety_regression_record(
        run_id="null_score",
        layer1_report=run_quality_safety_layer1_checks(good_candidate(), base_fixture()),
        overall_10=None,
        previous_record=previous_good,
    )
    check("record null score no fake delta", null_score["overall_10"] is None and null_score["delta_vs_prev"] is None)

    first = json.dumps(current_bad, sort_keys=True)
    second = json.dumps(build_quality_safety_regression_record(
        run_id="current",
        layer1_report=bad_report,
        overall_10=9.2,
        previous_record=previous_good,
    ), sort_keys=True)
    check("record deterministic serialization", first == second)


def test_no_leak_sweep() -> None:
    candidate = "\n".join(
        [
            HOSTILE_PATH,
            HOSTILE_URL,
            HOSTILE_AUTH,
            HOSTILE_DATA,
            HOSTILE_OCR,
            HOSTILE_PROVIDER,
            "Wait, synthetic alpha: 0.50",
            "## Worked Answer",
            "Solution: answer missing",
        ]
    )
    report = run_quality_safety_layer1_checks(candidate, base_fixture())
    record = build_quality_safety_regression_record(
        run_id="synthetic_run",
        git_sha=HOSTILE_PATH,
        model=HOSTILE_URL,
        preset=HOSTILE_AUTH,
        lecture_id=HOSTILE_DATA,
        tier="premium",
        layer1_report=report,
    )
    no_canary("layer1 hostile candidate", report)
    no_canary("record hostile metadata", record)


def test_run_quality_safety_eval_wrapper() -> None:
    result = run_quality_safety_eval(
        good_candidate(),
        base_fixture(),
        run_metadata={"run_id": "synthetic_wrapper", "tier": "premium"},
    )
    check("wrapper returns layer1 and record", set(result) == {"layer1", "record"}, str(result.keys()))
    check("wrapper record run id", result["record"]["run_id"] == "synthetic_wrapper")


def test_import_hygiene() -> None:
    source_path = REPO / "pipeline" / "quality_safety_eval_harness.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                calls.append(func.attr)
            elif isinstance(func, ast.Name):
                calls.append(func.id)
    forbidden_import_prefixes = (
        "api",
        "frontend",
        "requests",
        "urllib",
        "httpx",
        "openai",
        "anthropic",
        "google",
        "boto",
        "pipeline.provider",
        "pipeline.llm",
        "pipeline.ocr",
        "pipeline.pdf_renderer",
        "pipeline.docx_renderer",
        "pipeline.html_renderer",
        "pipeline.run_llm_job",
    )
    bad_imports = [name for name in imports if name.startswith(forbidden_import_prefixes)]
    check("import hygiene no forbidden imports", bad_imports == [], str(bad_imports))
    forbidden_calls = {"urlopen", "post", "socket", "create_connection"}
    bad_calls = sorted(set(calls) & forbidden_calls)
    check("import hygiene no network calls", bad_calls == [], str(bad_calls))


def run() -> int:
    test_fixture_loader()
    test_leaked_reasoning()
    test_numeric_correctness()
    test_worked_answer_completeness()
    test_coverage()
    test_mock_question_count()
    test_regression_record()
    test_no_leak_sweep()
    test_run_quality_safety_eval_wrapper()
    test_import_hygiene()
    print(f"\nquality_safety_eval_harness: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
