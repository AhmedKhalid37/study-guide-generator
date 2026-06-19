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
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_eval_harness import (  # noqa: E402
    PHASE0_EXIT_BLOCKER_ORDER,
    PHASE0_EXIT_SATISFIED_ORDER,
    PHASE0_EXIT_CHECK_KIND,
    PHASE0_OPERATOR_EXIT_SATISFIED_ORDER,
    PHASE0_OPERATOR_FORBIDDEN_OUTPUTS,
    PHASE0_OPERATOR_INGEST_BLOCKER_ORDER,
    PHASE0_OPERATOR_REFERENCE_JUDGE_SUMMARY_KIND,
    PHASE0_OPERATOR_REQUIRED_CLOSED_OUTPUTS,
    PHASE0_OPERATOR_REQUIRED_LOCAL_RUNS,
    PHASE0_OPERATOR_RESULT_KINDS,
    PHASE0_OPERATOR_RUN_PACKET_KIND,
    PHASE0_REGRESSION_RECORD_KIND,
    PHASE0_RUN_KIND,
    GoldenPairSpecError,
    append_phase0_regression_record_jsonl,
    build_phase0_exit_check,
    build_phase0_exit_check_from_operator_results,
    build_phase0_fact_sheet_summary,
    build_phase0_operator_run_packet,
    build_phase0_regression_record,
    build_phase0_report_skeleton,
    build_quality_safety_regression_record,
    compare_phase0_regression,
    compute_phase0_overall_10,
    get_phase0_operator_run_packet,
    ingest_phase0_operator_closed_result,
    load_golden_pair_spec,
    load_golden_pair_specs,
    load_quality_safety_fixture_spec,
    run_phase0_eval_harness,
    run_quality_safety_eval,
    run_quality_safety_layer1_checks,
    score_phase0_layer1,
)
from pipeline.quality_safety_reference_judge import (  # noqa: E402
    AXES as REFERENCE_JUDGE_AXES,
    EVIDENCE_QUOTE_MAX_WORDS,
    build_phase0_reference_judge_prompt,
    phase0_reference_judge_regression_summary,
    sanitize_phase0_reference_judge_output,
)

GOLDEN_PAIR_DIR = REPO / "test_scripts" / "fixtures" / "quality_safety" / "golden_pairs"
FORBIDDEN_FIXTURE_KEYS = (
    "source_text",
    "guide_text",
    "ocr_text",
    "captions",
    "caption",
    "raw_json",
    "path",
    "filename",
    "sha256",
    "bytes",
)


def read_golden_pair(lecture_id: str) -> dict[str, Any]:
    return json.loads((GOLDEN_PAIR_DIR / f"{lecture_id}.json").read_text(encoding="utf-8"))

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


def test_seed_fixture_file_consumption() -> None:
    fixture_path = REPO / "test_scripts" / "fixtures" / "quality_safety" / "clean_neural_networks_synthetic.json"
    fixture = load_quality_safety_fixture_spec(json.loads(fixture_path.read_text(encoding="utf-8")))
    candidate = "\n".join(
        [
            "activation function forward pass softmax output cross entropy loss training pipeline",
            "synthetic_forward_output: 0.86",
            "synthetic_cross_entropy: 0.56",
            "## Worked Answer",
            "Solution: use the synthetic values and finish.",
            "## Mock Question 1: What is first?",
            "Answer: activation function.",
            "## Mock Question 2: What follows?",
            "Answer: forward pass.",
            "## Practice Question 3: What loss is used?",
            "Answer: cross entropy loss.",
        ]
    )
    report = run_quality_safety_layer1_checks(candidate, fixture)
    check("seed fixture file loads without warnings", fixture["warnings"] == [], str(fixture["warnings"]))
    check("seed fixture file candidate passes", report["shippable"] is True and report["status"] == "passed", str(report))


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

    contradiction = run_quality_safety_layer1_checks(
        "synthetic alpha: 0.205 then synthetic alpha: 0.60",
        fixture,
    )
    numeric_contradiction = report_check(contradiction, "numeric_correctness")
    target = numeric_contradiction["targets"][0]
    check("numeric contradiction fails despite correct value", numeric_contradiction["status"] == "failed" and "numeric_correctness" in contradiction["blocking_failures"], str(numeric_contradiction))
    check("numeric contradiction warning closed", "numeric_contradiction_signal" in contradiction["warnings"], str(contradiction["warnings"]))
    check("numeric contradiction values only", target["found_values"] == [0.205, 0.6] and target["distinct_value_count"] == 2, str(target))
    check("numeric contradiction no snippets", not any(find_in_serialized(numeric_contradiction, term) for term in ["then synthetic", "synthetic alpha: 0.205", "synthetic alpha: 0.60"]))
    check("numeric contradiction no line fields", "line" not in json.dumps(numeric_contradiction, sort_keys=True).lower())

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


def test_golden_pair_set_is_exactly_nn3_and_ensemble() -> None:
    nn3_raw = read_golden_pair("nn3")
    ensemble_raw = read_golden_pair("ensemble")
    specs = load_golden_pair_specs([nn3_raw, ensemble_raw])
    check(
        "golden pair set is exactly nn3 and ensemble",
        set(specs) == {"nn3", "ensemble"},
        str(sorted(specs)),
    )
    check(
        "golden pair kind closed",
        all(spec["kind"] == "quality_safety_golden_pair" for spec in specs.values()),
    )

    # Incomplete and over-complete sets are rejected.
    raised_incomplete = False
    try:
        load_golden_pair_specs([nn3_raw])
    except GoldenPairSpecError:
        raised_incomplete = True
    check("golden pair incomplete set rejected", raised_incomplete)

    raised_duplicate = False
    try:
        load_golden_pair_specs([nn3_raw, ensemble_raw, ensemble_raw])
    except GoldenPairSpecError:
        raised_duplicate = True
    check("golden pair duplicate/extra rejected", raised_duplicate)

    no_canary("golden pair specs", specs)


def test_golden_pair_nn3_topics_and_numerics() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    check("nn3 lecture id", spec["lecture_id"] == "nn3")
    check("nn3 source quality clean", spec["source_quality"] == "clean")
    required_topics = {
        "ReLU",
        "ReLU derivative",
        "network architecture",
        "forward pass",
        "ArgMax",
        "SoftMax",
        "SoftMax derivative",
        "Cross-Entropy",
        "CE vs SSR",
        "training/inference pipeline",
    }
    check(
        "nn3 required topics present",
        required_topics.issubset(set(spec["expected_topics"])),
        str(sorted(required_topics - set(spec["expected_topics"]))),
    )
    numerics = {item["label"]: (item["value"], item["tol"]) for item in spec["ground_truth_numerics"]}
    expected_numerics = {
        "htop_pw0.5_sw0.37": (0.572, 0.01),
        "rset_pw0.5_sw0.37": (0.09, 0.01),
        "rver_pw0.5_sw0.37": (0.86, 0.01),
        "softmax_1.43": (0.69, 0.01),
        "cross_entropy_neg_ln_0.57": (0.56, 0.01),
    }
    check(
        "nn3 required numerics present with values/tolerances",
        all(numerics.get(label) == vt for label, vt in expected_numerics.items()),
        str(numerics),
    )
    check("nn3 min mock questions", spec["min_mock_questions"] == 8)


def test_golden_pair_ensemble_topics_and_numerics() -> None:
    spec = load_golden_pair_spec(read_golden_pair("ensemble"))
    check("ensemble lecture id", spec["lecture_id"] == "ensemble")
    check(
        "ensemble source quality ambiguous frames",
        spec["source_quality"] == "ambiguous_animation_frames",
    )
    numerics = {item["label"]: (item["value"], item["tol"]) for item in spec["ground_truth_numerics"]}
    check(
        "ensemble gini weight_gt_176 = 0.20",
        numerics.get("gini_weight_gt_176") == (0.20, 0.01),
        str(numerics.get("gini_weight_gt_176")),
    )
    for label, value in (
        ("gini_chest_pain", 0.47),
        ("gini_blocked_arteries", 0.50),
        ("total_error_stump_1", 0.125),
        ("amount_of_say_half_ln_7", 0.97),
        ("proximity_4_3", 0.80),
        ("weighted_weight_impute", 198.5),
    ):
        check(
            f"ensemble numeric {label}",
            numerics.get(label, (None,))[0] == value,
            str(numerics.get(label)),
        )
    check("ensemble min mock questions", spec["min_mock_questions"] == 8)


def test_golden_pair_tier_targets() -> None:
    for lecture_id in ("nn3", "ensemble"):
        spec = load_golden_pair_spec(read_golden_pair(lecture_id))
        check(
            f"{lecture_id} tier targets premium 9.5 local 9.0",
            spec["tier_targets"] == {"premium": 9.5, "local": 9.0},
            str(spec["tier_targets"]),
        )


def test_golden_pair_no_raw_material_fields() -> None:
    for lecture_id in ("nn3", "ensemble"):
        raw = read_golden_pair(lecture_id)
        forbidden_present = [key for key in FORBIDDEN_FIXTURE_KEYS if key in raw]
        check(
            f"{lecture_id} fixture has no raw material keys",
            forbidden_present == [],
            str(forbidden_present),
        )
        no_canary(f"{lecture_id} golden fixture", raw)

    # The loader rejects any unknown key, so raw material cannot ride along.
    raised = False
    try:
        load_golden_pair_spec({**read_golden_pair("nn3"), "source_text": "anything"})
    except GoldenPairSpecError:
        raised = True
    check("golden loader rejects raw material key", raised)


def test_golden_pair_rejects_synthetic_fixtures() -> None:
    # The old synthetic Quality Safety fixtures must NOT pass as real golden pairs.
    for name in ("clean_neural_networks_synthetic", "ambiguous_ensemble_synthetic"):
        path = REPO / "test_scripts" / "fixtures" / "quality_safety" / f"{name}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        rejected = False
        try:
            load_golden_pair_spec(raw)
        except GoldenPairSpecError:
            rejected = True
        check(f"synthetic fixture {name} rejected as golden pair", rejected)

    rejected_set = False
    try:
        load_golden_pair_specs(
            [
                json.loads((REPO / "test_scripts" / "fixtures" / "quality_safety" / "clean_neural_networks_synthetic.json").read_text(encoding="utf-8")),
                json.loads((REPO / "test_scripts" / "fixtures" / "quality_safety" / "ambiguous_ensemble_synthetic.json").read_text(encoding="utf-8")),
            ]
        )
    except GoldenPairSpecError:
        rejected_set = True
    check("synthetic fixtures not treated as golden pair set", rejected_set)


def test_phase0_report_skeleton_judge_frozen() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))

    # Shape-only skeleton with no Layer-1 run yet.
    skeleton = build_phase0_report_skeleton(spec)
    for field in (
        "lecture_id",
        "source_quality",
        "tier_targets",
        "layer1_status",
        "layer1_summary",
        "overall_10",
        "shippable",
        "blocking_checks",
        "judge_ready",
        "repair_ready",
        "reference_anchored_judge_status",
        "regression_record_status",
    ):
        check(f"phase0 skeleton has field {field}", field in skeleton)
    check("phase0 judge_ready false", skeleton["judge_ready"] is False)
    check("phase0 repair_ready false", skeleton["repair_ready"] is False)
    check(
        "phase0 reference judge separate and not run",
        skeleton["reference_anchored_judge_status"] == "not_run",
    )
    check("phase0 regression record shape only", skeleton["regression_record_status"] == "shape_only")
    check(
        "phase0 overall_10 and shippable separate fields",
        skeleton["overall_10"] is None and skeleton["shippable"] is False,
    )

    # Even with a Layer-1 report attached, judge readiness stays frozen and
    # overall_10 (Layer-2 score) stays separate from Layer-1 shippability.
    layer1 = run_quality_safety_layer1_checks(good_candidate(), base_fixture())
    populated = build_phase0_report_skeleton(
        spec,
        layer1,
        reference_anchored_judge_status="ok",
        regression_record_status="not_persisted",
    )
    check("phase0 populated judge_ready still false", populated["judge_ready"] is False)
    check("phase0 populated repair_ready still false", populated["repair_ready"] is False)
    check(
        "phase0 populated overall_10 separate from shippable",
        populated["overall_10"] is None
        and isinstance(populated["shippable"], bool)
        and populated["layer1_status"] is not None,
    )
    check(
        "phase0 reference judge status closed-but-separate",
        populated["reference_anchored_judge_status"] == "ok"
        and populated["judge_ready"] is False,
    )
    no_canary("phase0 skeleton", populated)

    raised = False
    try:
        build_phase0_report_skeleton({"kind": "quality_safety_fixture"})
    except GoldenPairSpecError:
        raised = True
    check("phase0 skeleton requires validated golden pair", raised)


def golden_candidate(
    spec: dict[str, Any],
    *,
    topics: list[str] | None = None,
    numerics: list[dict[str, Any]] | None = None,
    mock_count: int | None = None,
    extra_lines: list[str] | None = None,
) -> str:
    """Build a synthetic candidate guide string for one golden-pair spec.

    Uses only the closed authored expectation labels/values; no private guide,
    source, or reference material. Mock questions use the ``Q<n>.`` convention
    the harness recognizes, and contain no ``?`` so the leak detector is not
    triggered outside genuine reasoning leaks injected by a test.
    """
    use_topics = spec["expected_topics"] if topics is None else topics
    use_numerics = spec["ground_truth_numerics"] if numerics is None else numerics
    count = spec["min_mock_questions"] if mock_count is None else mock_count
    lines = ["# Synthetic Golden Candidate"]
    lines.append("Covered topics: " + "; ".join(use_topics) + ".")
    for item in use_numerics:
        # Write the authored label verbatim followed by ``= <value>``; no
        # synthetic ``_out`` suffix is appended. The numeric check strips the
        # matched label span (including any label-internal parameters such as
        # ``pw=0.5`` or ``-ln 0.57``) before reading the candidate value, so the
        # answer on the right-hand side is the only number extracted.
        lines.append(f"{item['label']} = {item['value']}")
    lines.append("## Worked Answer")
    lines.append("Solution: substitute the values and the computation completes.")
    lines.append("## Practice Questions")
    for index in range(count):
        lines.append(f"Q{index + 1}. Restate the computed value for item {index + 1}.")
    if extra_lines:
        lines.extend(extra_lines)
    return "\n".join(lines)


def phase0_check(record: dict[str, Any], check_id: str) -> dict[str, Any]:
    for item in record.get("checks", []):
        if item.get("id") == check_id:
            return item
    raise AssertionError(check_id)


REQUIRED_PHASE0_FIELDS = (
    "lecture_id",
    "source_quality",
    "layer1_status",
    "shippable",
    "overall_10",
    "blocking_checks",
    "checks",
    "judge_ready",
    "repair_ready",
    "reference_anchored_judge_status",
    "regression_record_status",
)


def synthetic_fact_sheet(*facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_fact_sheet",
        "lecture_id": "nn3",
        "source_quality": "clean",
        "concepts": [
            {
                "concept": "Synthetic Numeric Concept",
                "facts": list(facts),
                "teaching_notes": [],
                "worked_examples": [],
            }
        ],
    }


def total_error_fact(
    *,
    fact_id: str = "synthetic_numeric_fact",
    label: str = "synthetic_verified_value",
    value: float = 0.20,
    supplied_status: str = "verified",
    provenance: str = "computed",
    confidence: str = "high",
    computed_value: float = 0.20,
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "concept": "Synthetic Numeric Concept",
        "label": label,
        "value": value,
        "type": "numeric",
        "provenance": provenance,
        "verification_status": supplied_status,
        "confidence": confidence,
        "source_ref": "source_page_1",
        "computation": {
            "method": "total_error",
            "inputs": {"misclassified_weight": computed_value},
            "tolerance": 0.01,
        },
    }


def canonical_fact(
    *,
    fact_id: str = "synthetic_canonical_fact",
    label: str = "synthetic_canonical_value",
    value: float = 0.30,
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "concept": "Synthetic Numeric Concept",
        "label": label,
        "value": value,
        "type": "numeric",
        "provenance": "canonical_fixture",
        "verification_status": "verified",
        "confidence": "high",
        "source_ref": "source_page_2",
    }


def unverified_fact() -> dict[str, Any]:
    return {
        "id": "synthetic_unverified_fact",
        "concept": "Synthetic Numeric Concept",
        "label": "synthetic_unverified_value",
        "value": 0.77,
        "type": "numeric",
        "provenance": "unverified",
        "verification_status": "unverified",
        "confidence": "low",
        "source_ref": "source_page_3",
    }


def test_phase0_scorer_clean_candidate_passes() -> None:
    for lecture_id in ("nn3", "ensemble"):
        spec = load_golden_pair_spec(read_golden_pair(lecture_id))
        record = score_phase0_layer1(golden_candidate(spec), spec)
        check(
            f"{lecture_id} clean candidate has all required fields",
            all(field in record for field in REQUIRED_PHASE0_FIELDS),
            str([f for f in REQUIRED_PHASE0_FIELDS if f not in record]),
        )
        check(
            f"{lecture_id} clean candidate shippable and passes",
            record["shippable"] is True
            and record["layer1_status"] == "passed"
            and record["blocking_checks"] == [],
            str(record["blocking_checks"]) + " " + str(record["layer1_status"]),
        )
        check(
            f"{lecture_id} clean numeric passes",
            phase0_check(record, "numeric_correctness")["status"] == "passed"
            and phase0_check(record, "numeric_correctness")["missing_count"] == 0
            and phase0_check(record, "numeric_correctness")["mismatch_count"] == 0,
            str(phase0_check(record, "numeric_correctness")),
        )
        check(
            f"{lecture_id} clean coverage passes at/above threshold",
            phase0_check(record, "coverage")["status"] == "passed"
            and phase0_check(record, "coverage")["threshold"] == 0.90,
            str(phase0_check(record, "coverage")),
        )
        check(
            f"{lecture_id} clean leak and worked pass",
            phase0_check(record, "leaked_reasoning")["status"] == "passed"
            and phase0_check(record, "worked_answer_completeness")["status"] == "passed",
            str(record["checks"]),
        )
        check(
            f"{lecture_id} judge frozen",
            record["judge_ready"] is False and record["repair_ready"] is False,
        )
        check(
            f"{lecture_id} reference judge separate and not run",
            record["reference_anchored_judge_status"] == "not_run",
        )
        check(
            f"{lecture_id} overall_10 separate from shippable",
            record["overall_10"] is None and isinstance(record["shippable"], bool),
        )
        no_canary(f"{lecture_id} phase0 clean record", record)


def test_phase0_fact_sheet_not_supplied_preserves_layer1_behavior() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    legacy = score_phase0_layer1(golden_candidate(spec), spec)
    explicit_none = score_phase0_layer1(golden_candidate(spec), spec, fact_sheet=None)
    summary = explicit_none["fact_sheet_summary"]
    check(
        "phase0 no fact sheet reports not supplied",
        summary["fact_sheet_status"] == "not_supplied"
        and summary["recompute_verifier_status"] == "not_run"
        and summary["verified_numeric_count"] == 0
        and summary["failed_numeric_count"] == 0
        and summary["unverified_numeric_count"] == 0,
        str(summary),
    )
    check(
        "phase0 no fact sheet keeps numeric behavior",
        phase0_check(legacy, "numeric_correctness") == phase0_check(explicit_none, "numeric_correctness")
        and legacy["shippable"] == explicit_none["shippable"],
        str(explicit_none),
    )


def test_phase0_fact_sheet_verified_and_canonical_summary_passes() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    sheet = synthetic_fact_sheet(total_error_fact(), canonical_fact())
    summary = build_phase0_fact_sheet_summary(sheet, spec)
    record = score_phase0_layer1(
        "\n".join(
            [
                golden_candidate(spec),
                "synthetic_verified_value = 0.20",
                "synthetic_canonical_value = 0.30",
            ]
        ),
        spec,
        fact_sheet=sheet,
    )
    numeric = phase0_check(record, "numeric_correctness")
    check(
        "phase0 valid fact sheet summary passed",
        summary["fact_sheet_status"] == "ok"
        and summary["recompute_verifier_status"] == "passed"
        and summary["verified_numeric_count"] == 1
        and summary["canonical_numeric_count"] == 1
        and summary["committed_numeric_count"] == 2,
        str(summary),
    )
    check(
        "phase0 verified/canonical numerics still require candidate text and pass",
        numeric["status"] == "passed"
        and numeric["expected_count"] >= len(spec["ground_truth_numerics"]) + 2
        and record["shippable"] is True,
        str(numeric),
    )
    no_canary("phase0 verified fact sheet record", record)


def test_phase0_recompute_failed_numeric_blocks_even_if_printed() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    sheet = synthetic_fact_sheet(
        total_error_fact(
            fact_id="synthetic_failed_fact",
            label="synthetic_failed_value",
            value=0.50,
            computed_value=0.20,
        )
    )
    record = score_phase0_layer1(
        "\n".join([golden_candidate(spec), "synthetic_failed_value = 0.50"]),
        spec,
        fact_sheet=sheet,
    )
    numeric = phase0_check(record, "numeric_correctness")
    summary = record["fact_sheet_summary"]
    check(
        "phase0 recompute failed numeric fails summary",
        summary["fact_sheet_status"] == "ok"
        and summary["recompute_verifier_status"] == "failed"
        and summary["failed_numeric_count"] == 1,
        str(summary),
    )
    check(
        "phase0 recompute failed numeric blocks despite printed value",
        numeric["status"] == "failed"
        and numeric["recompute_failed_count"] == 1
        and "numeric_correctness" in record["blocking_checks"]
        and record["shippable"] is False,
        str(numeric),
    )


def test_phase0_unverified_fact_never_creates_confidence() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    sheet = synthetic_fact_sheet(unverified_fact())
    record = score_phase0_layer1(
        "\n".join([golden_candidate(spec), "synthetic_unverified_value = 0.77"]),
        spec,
        fact_sheet=sheet,
    )
    summary = record["fact_sheet_summary"]
    numeric = phase0_check(record, "numeric_correctness")
    check(
        "phase0 unverified numeric is warning only and not committed",
        summary["fact_sheet_status"] == "partial"
        and summary["recompute_verifier_status"] == "partial"
        and summary["unverified_numeric_count"] == 1
        and summary["committed_numeric_count"] == 0
        and "fact_sheet_unverified_numeric" in summary["warnings"],
        str(summary),
    )
    check(
        "phase0 unverified numeric does not pass numeric correctness by itself",
        numeric["status"] == "passed"
        and numeric["verified_numeric_count"] == 0
        and numeric["unverified_numeric_count"] == 1
        and numeric["expected_count"] == len(spec["ground_truth_numerics"]),
        str(numeric),
    )


def test_phase0_verified_fact_still_requires_candidate_value() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    sheet = synthetic_fact_sheet(total_error_fact())
    record = score_phase0_layer1(golden_candidate(spec), spec, fact_sheet=sheet)
    numeric = phase0_check(record, "numeric_correctness")
    check(
        "phase0 verified fact missing from candidate blocks",
        numeric["status"] == "failed"
        and numeric["missing_count"] >= 1
        and "numeric_correctness" in record["blocking_checks"]
        and "committed_numeric_missing" in record["warnings"],
        str(numeric),
    )


def test_phase0_fact_sheet_summary_is_counts_only() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    hostile_sheet = synthetic_fact_sheet(
        {
            **total_error_fact(label=HOSTILE_PATH, value=0.20, computed_value=0.20),
            "raw_text": HOSTILE_OCR,
            "payload": HOSTILE_PROVIDER,
        }
    )
    summary = build_phase0_fact_sheet_summary(hostile_sheet, spec)
    blob = json.dumps(summary, sort_keys=True)
    present_keys = collect_record_keys(summary)
    leaked_keys = [key for key in FORBIDDEN_RECORD_KEYS if key in present_keys]
    check(
        "phase0 fact sheet summary contains counts/statuses only",
        set(summary) == {
            "kind",
            "fact_sheet_status",
            "recompute_verifier_status",
            "fact_sheet_numeric_count",
            "verified_numeric_count",
            "failed_numeric_count",
            "unverified_numeric_count",
            "canonical_numeric_count",
            "committed_numeric_count",
            "warnings",
        }
        and leaked_keys == [],
        str(summary),
    )
    check(
        "phase0 fact sheet summary omits raw labels and hostile material",
        "synthetic_verified_value" not in blob
        and "Synthetic Numeric Concept" not in blob
        and HOSTILE_PATH not in blob
        and HOSTILE_OCR not in blob
        and HOSTILE_PROVIDER not in blob,
        blob,
    )
    no_canary("phase0 fact sheet summary", summary)


def test_phase0_regression_record_includes_safe_fact_sheet_summary() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    sheet = synthetic_fact_sheet(total_error_fact())
    layer1 = score_phase0_layer1(
        "\n".join([golden_candidate(spec), "synthetic_verified_value = 0.20"]),
        spec,
        fact_sheet=sheet,
    )
    regression = build_phase0_regression_record(layer1, run_id="r", model_tier="premium")
    check(
        "phase0 regression record safely includes fact sheet summary",
        regression["fact_sheet_summary"]["fact_sheet_status"] == "ok"
        and regression["fact_sheet_summary"]["recompute_verifier_status"] == "passed"
        and regression["fact_sheet_summary"]["verified_numeric_count"] == 1,
        str(regression["fact_sheet_summary"]),
    )
    present_keys = collect_record_keys(regression)
    leaked_keys = [key for key in FORBIDDEN_RECORD_KEYS if key in present_keys]
    check("phase0 fact sheet regression record has no forbidden keys", leaked_keys == [], str(leaked_keys))
    no_canary("phase0 fact sheet regression record", regression)


def test_phase0_scorer_leaked_reasoning_blocks() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    candidate = golden_candidate(
        spec, extra_lines=["Wait, actually this step is unclear, so we'll trust it."]
    )
    record = score_phase0_layer1(candidate, spec)
    leak = phase0_check(record, "leaked_reasoning")
    check(
        "phase0 leak fails and blocks shipping",
        leak["status"] == "failed"
        and "leaked_reasoning" in record["blocking_checks"]
        and record["shippable"] is False,
        str(record["blocking_checks"]),
    )
    check(
        "phase0 leak record counts only",
        "matches" not in leak and "line" not in json.dumps(leak).lower(),
        str(leak),
    )
    check(
        "phase0 leak omits matched text",
        not any(find_in_serialized(record, term) for term in ["Wait", "actually", "unclear", "we'll trust"]),
    )


def test_phase0_scorer_missing_numeric_blocks() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    reduced = spec["ground_truth_numerics"][:-1]
    record = score_phase0_layer1(golden_candidate(spec, numerics=reduced), spec)
    numeric = phase0_check(record, "numeric_correctness")
    check(
        "phase0 missing numeric fails and blocks",
        numeric["status"] == "failed"
        and numeric["missing_count"] >= 1
        and "numeric_correctness" in record["blocking_checks"]
        and record["shippable"] is False,
        str(numeric),
    )


def test_phase0_scorer_ensemble_gini_weight_numeric() -> None:
    spec = load_golden_pair_spec(read_golden_pair("ensemble"))
    gini = next(
        item for item in spec["ground_truth_numerics"] if item["label"] == "gini_weight_gt_176"
    )
    check("ensemble gini weight_gt_176 expectation is 0.20", gini["value"] == 0.20)

    without_gini = [
        item for item in spec["ground_truth_numerics"] if item["label"] != "gini_weight_gt_176"
    ]
    missing_record = score_phase0_layer1(
        golden_candidate(spec, numerics=without_gini), spec
    )
    missing_numeric = phase0_check(missing_record, "numeric_correctness")
    check(
        "ensemble missing gini weight_gt_176 fails numeric",
        missing_numeric["status"] == "failed"
        and missing_numeric["missing_count"] >= 1
        and missing_record["shippable"] is False,
        str(missing_numeric),
    )

    full_record = score_phase0_layer1(golden_candidate(spec), spec)
    full_numeric = phase0_check(full_record, "numeric_correctness")
    check(
        "ensemble all numerics including gini weight_gt_176 pass",
        full_numeric["status"] == "passed"
        and full_numeric["missing_count"] == 0
        and full_numeric["mismatch_count"] == 0
        and full_record["shippable"] is True,
        str(full_numeric),
    )


# Realistic authored numeric labels that embed numeric parameters (weights,
# softmax inputs, a ``-ln`` argument). These exercise the fix that strips the
# matched label span before reading the candidate answer, so label-internal
# decimals like 0.5, 0.37 or 0.57 are never read as candidate answers or as
# contradictions. No underscore-joined synthetic suffix is used to dodge the
# detector -- the labels are the natural exam forms.
NATURAL_NN3_NUMERICS = [
    {"label": "htop(pw=0.5,sw=0.37)", "value": 0.572, "tol": 0.01},
    {"label": "Rset(pw=0.5,sw=0.37)", "value": 0.09, "tol": 0.01},
    {"label": "Rver(pw=0.5,sw=0.37)", "value": 0.86, "tol": 0.01},
    {"label": "SoftMax(1.43)", "value": 0.69, "tol": 0.01},
    {"label": "CE(-ln 0.57)", "value": 0.56, "tol": 0.01},
]


def natural_nn3_spec() -> dict[str, Any]:
    """A valid nn3 golden-pair spec whose numeric labels are natural exam forms.

    Reuses the committed nn3 topics/mock/tier expectations but swaps in the
    realistic parameter-bearing numeric labels. The strict golden-pair loader
    still validates it, and the golden-pair set stays exactly {nn3, ensemble};
    only the in-memory numeric labels differ for this regression test.
    """
    return load_golden_pair_spec(
        {**read_golden_pair("nn3"), "ground_truth_numerics": NATURAL_NN3_NUMERICS}
    )


def test_phase0_numeric_ignores_label_internal_parameters() -> None:
    spec = natural_nn3_spec()
    # Candidate writes each natural label verbatim followed by ``= <answer>``;
    # e.g. ``htop(pw=0.5,sw=0.37) = 0.572`` and ``CE(-ln 0.57) = 0.56``.
    record = score_phase0_layer1(golden_candidate(spec), spec)
    numeric = phase0_check(record, "numeric_correctness")
    check(
        "natural decimal-bearing labels pass numeric_correctness",
        numeric["status"] == "passed"
        and numeric["missing_count"] == 0
        and numeric["mismatch_count"] == 0
        and numeric["matched_count"] == len(NATURAL_NN3_NUMERICS),
        str(numeric),
    )
    check(
        "natural decimal-bearing labels do not block shipping",
        record["shippable"] is True
        and "numeric_correctness" not in record["blocking_checks"],
        str(record["blocking_checks"]),
    )
    # Label-internal parameters (0.5, 0.37, 0.57, 1.43) and the spurious trailing
    # 37 must not surface as found values or contradictions: record is counts-only.
    blob = json.dumps(record, sort_keys=True)
    check(
        "natural numeric record is counts only (no found values / raw labels)",
        "found_values" not in blob
        and "distinct_value_count" not in blob
        and "pw=0.5" not in blob
        and "sw=0.37" not in blob
        and "-ln 0.57" not in blob,
        blob[:80],
    )
    no_canary("phase0 natural numeric record", record)
    check(
        "natural numeric judge stays frozen and overall_10 separate",
        record["judge_ready"] is False
        and record["repair_ready"] is False
        and record["overall_10"] is None
        and isinstance(record["shippable"], bool),
        str(record["judge_ready"]),
    )


def test_phase0_numeric_natural_wrong_answer_still_fails() -> None:
    spec = natural_nn3_spec()
    # Flip a single answer to a clearly wrong value while keeping the realistic
    # parameter-bearing label: ``htop(pw=0.5,sw=0.37) = 0.999``.
    wrong = [
        {**item, "value": 0.999} if item["label"] == "htop(pw=0.5,sw=0.37)" else item
        for item in NATURAL_NN3_NUMERICS
    ]
    record = score_phase0_layer1(golden_candidate(spec, numerics=wrong), spec)
    numeric = phase0_check(record, "numeric_correctness")
    check(
        "natural wrong answer fails numeric_correctness and blocks",
        numeric["status"] == "failed"
        and numeric["mismatch_count"] >= 1
        and "numeric_correctness" in record["blocking_checks"]
        and record["shippable"] is False,
        str(numeric),
    )


def test_phase0_numeric_ensemble_natural_contradiction_and_mismatch() -> None:
    spec = load_golden_pair_spec(read_golden_pair("ensemble"))

    # Authored expectation: Gini weight_gt_176 = 0.20. The clean candidate
    # passes (covered by the clean-candidate test); here confirm a wrong single
    # value still fails, using the natural spaced form ``Gini weight_gt_176``.
    for wrong_value in (0.42, 0.19):
        mutated = [
            {**item, "value": wrong_value}
            if item["label"] == "gini_weight_gt_176"
            else item
            for item in spec["ground_truth_numerics"]
        ]
        record = score_phase0_layer1(golden_candidate(spec, numerics=mutated), spec)
        numeric = phase0_check(record, "numeric_correctness")
        check(
            f"ensemble gini wrong value {wrong_value} fails numeric_correctness",
            numeric["status"] == "failed"
            and numeric["mismatch_count"] >= 1
            and "numeric_correctness" in record["blocking_checks"]
            and record["shippable"] is False,
            str(numeric),
        )

    # Two contradictory answers for the same authored label still fail as a
    # contradiction (the clean candidate already states 0.20; add 0.42 and 0.19).
    contradiction = score_phase0_layer1(
        golden_candidate(
            spec,
            extra_lines=[
                "Gini weight_gt_176 = 0.42",
                "Gini weight_gt_176 = 0.19",
            ],
        ),
        spec,
    )
    numeric = phase0_check(contradiction, "numeric_correctness")
    check(
        "ensemble gini contradictory answers fail and block",
        numeric["status"] == "failed"
        and numeric["mismatch_count"] >= 1
        and "numeric_correctness" in contradiction["blocking_checks"]
        and contradiction["shippable"] is False,
        str(numeric),
    )
    check(
        "ensemble contradiction record stays counts only and judge frozen",
        "found_values" not in json.dumps(contradiction, sort_keys=True)
        and contradiction["judge_ready"] is False
        and contradiction["repair_ready"] is False,
        str(numeric),
    )
    no_canary("phase0 ensemble contradiction record", contradiction)


def test_phase0_scorer_coverage_below_threshold_blocks() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    # Drop two of ten topics -> 0.8 coverage, below the 0.90 threshold.
    reduced_topics = spec["expected_topics"][:-2]
    record = score_phase0_layer1(golden_candidate(spec, topics=reduced_topics), spec)
    coverage = phase0_check(record, "coverage")
    check(
        "phase0 coverage below threshold fails and blocks",
        coverage["status"] == "failed"
        and coverage["blocking"] is True
        and coverage["coverage_ratio"] is not None
        and coverage["coverage_ratio"] < 0.90
        and "coverage" in record["blocking_checks"]
        and record["shippable"] is False,
        str(coverage),
    )


def test_phase0_scorer_mock_below_min_is_advisory() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    record = score_phase0_layer1(golden_candidate(spec, mock_count=3), spec)
    mock = phase0_check(record, "mock_question_count")
    check(
        "phase0 mock below minimum is advisory warning",
        mock["status"] == "warning" and mock["blocking"] is False,
        str(mock),
    )
    check(
        "phase0 mock below minimum alone does not block shipping",
        record["shippable"] is True and record["blocking_checks"] == [],
        str(record["blocking_checks"]),
    )


def test_phase0_scorer_worked_answer_unresolved_blocks() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    candidate = golden_candidate(
        spec,
        extra_lines=["## Worked Answer", "Solution: answer missing for this step."],
    )
    record = score_phase0_layer1(candidate, spec)
    worked = phase0_check(record, "worked_answer_completeness")
    check(
        "phase0 worked answer unresolved fails and blocks",
        worked["status"] == "failed"
        and "worked_answer_completeness" in record["blocking_checks"]
        and record["shippable"] is False,
        str(worked),
    )


def test_phase0_scorer_no_raw_material_leak() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    hostile_candidate = "\n".join(
        [
            golden_candidate(spec),
            HOSTILE_PATH,
            HOSTILE_URL,
            HOSTILE_AUTH,
            HOSTILE_DATA,
            HOSTILE_OCR,
            HOSTILE_PROVIDER,
        ]
    )
    record = score_phase0_layer1(hostile_candidate, spec)
    no_canary("phase0 hostile candidate record", record)
    blob = json.dumps(record, sort_keys=True).lower()
    check(
        "phase0 record exposes no raw candidate text or paths",
        not any(token in blob for token in ("relu = ", "covered topics", "/home/", ".pdf", "sha256", "bytes")),
        blob[:80],
    )
    check(
        "phase0 record numeric is counts only (no found values)",
        "found_values" not in blob and "distinct_value_count" not in blob,
    )
    # Deterministic, repeatable serialization.
    first = json.dumps(score_phase0_layer1(golden_candidate(spec), spec), sort_keys=True)
    second = json.dumps(score_phase0_layer1(golden_candidate(spec), spec), sort_keys=True)
    check("phase0 scorer deterministic serialization", first == second)


def test_phase0_scorer_rejects_synthetic_and_judge_frozen() -> None:
    # Synthetic Slice 108 fixtures are not valid Phase 0 golden pairs.
    synthetic = base_fixture()
    rejected = False
    try:
        score_phase0_layer1(good_candidate(), synthetic)
    except GoldenPairSpecError:
        rejected = True
    check("phase0 scorer rejects synthetic fixture as golden pair", rejected)

    # Even with a reference-anchored status passed in, production judge stays
    # frozen and overall_10 stays unscored/separate.
    spec = load_golden_pair_spec(read_golden_pair("ensemble"))
    record = score_phase0_layer1(
        golden_candidate(spec),
        spec,
        reference_anchored_judge_status="ok",
        regression_record_status="not_persisted",
    )
    check(
        "phase0 scorer judge stays frozen despite reference status",
        record["judge_ready"] is False
        and record["repair_ready"] is False
        and record["reference_anchored_judge_status"] == "ok"
        and record["regression_record_status"] == "not_persisted"
        and record["overall_10"] is None,
        str(record["reference_anchored_judge_status"]),
    )


FORBIDDEN_RECORD_KEYS = (
    "candidate_text",
    "candidate",
    "snippet",
    "snippets",
    "source_text",
    "guide_text",
    "ocr_text",
    "table_text",
    "caption",
    "captions",
    "filename",
    "path",
    "sha256",
    "hash",
    "bytes",
    "byte_count",
    "prompt",
    "response",
    "payload",
    "raw_json",
    "evidence",
    "quote",
)


def collect_record_keys(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                found.add(key.lower())
            found |= collect_record_keys(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            found |= collect_record_keys(item)
    return found


def test_phase0_overall_clean_candidate_high_and_shippable() -> None:
    for lecture_id in ("nn3", "ensemble"):
        spec = load_golden_pair_spec(read_golden_pair(lecture_id))
        record = score_phase0_layer1(golden_candidate(spec), spec)
        envelope = compute_phase0_overall_10(record)
        check(
            f"{lecture_id} overall clean is 10.0 and shippable",
            envelope["overall_10"] == 10.0 and envelope["shippable"] is True,
            str(envelope),
        )
        check(
            f"{lecture_id} overall_10 and shippable are separate fields",
            "overall_10" in envelope
            and "shippable" in envelope
            and isinstance(envelope["overall_10"], float)
            and isinstance(envelope["shippable"], bool),
            str(envelope),
        )
        check(
            f"{lecture_id} overall is layer1 deterministic-only, no layer2 judge",
            envelope["overall_score_kind"] == "layer1_deterministic_only"
            and envelope["layer2_judge_included"] is False,
            str(envelope),
        )
        check(
            f"{lecture_id} overall keeps production judge frozen",
            envelope["judge_ready"] is False and envelope["repair_ready"] is False,
        )
        no_canary(f"{lecture_id} phase0 overall envelope", envelope)


def test_phase0_overall_leaked_reasoning_lowers_and_blocks() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    clean = compute_phase0_overall_10(score_phase0_layer1(golden_candidate(spec), spec))
    leaked = compute_phase0_overall_10(
        score_phase0_layer1(
            golden_candidate(spec, extra_lines=["Wait, actually this is unclear, so we'll trust it."]),
            spec,
        )
    )
    check(
        "phase0 overall leaked reasoning not shippable and lower",
        leaked["shippable"] is False and leaked["overall_10"] < clean["overall_10"],
        str(leaked),
    )
    check(
        "phase0 overall leaked reasoning stays in range",
        0.0 <= leaked["overall_10"] <= 10.0,
        str(leaked["overall_10"]),
    )


def test_phase0_overall_missing_numeric_lowers_and_blocks() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    clean = compute_phase0_overall_10(score_phase0_layer1(golden_candidate(spec), spec))
    reduced = spec["ground_truth_numerics"][:-1]
    missing = compute_phase0_overall_10(
        score_phase0_layer1(golden_candidate(spec, numerics=reduced), spec)
    )
    check(
        "phase0 overall missing numeric not shippable and lower",
        missing["shippable"] is False and missing["overall_10"] < clean["overall_10"],
        str(missing),
    )


def test_phase0_overall_low_mock_is_advisory_only() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    clean = compute_phase0_overall_10(score_phase0_layer1(golden_candidate(spec), spec))
    low = compute_phase0_overall_10(
        score_phase0_layer1(golden_candidate(spec, mock_count=2), spec)
    )
    check(
        "phase0 overall low mock stays shippable",
        low["shippable"] is True,
        str(low),
    )
    check(
        "phase0 overall low mock may reduce but not below shippable contract",
        low["overall_10"] <= clean["overall_10"] and low["overall_10"] >= 9.0,
        str(low["overall_10"]),
    )


def test_phase0_overall_judge_frozen_unoverrideable() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    # Even if a caller hands a tampered layer1 record claiming judge readiness,
    # the deterministic overall envelope must report the frozen booleans.
    record = score_phase0_layer1(golden_candidate(spec), spec)
    tampered = dict(record)
    tampered["judge_ready"] = True
    tampered["repair_ready"] = True
    envelope = compute_phase0_overall_10(tampered)
    check(
        "phase0 overall judge frozen despite tampered input",
        envelope["judge_ready"] is False and envelope["repair_ready"] is False,
        str(envelope),
    )


def test_phase0_regression_record_closed_and_safe() -> None:
    for lecture_id in ("nn3", "ensemble"):
        spec = load_golden_pair_spec(read_golden_pair(lecture_id))
        record = score_phase0_layer1(golden_candidate(spec), spec)
        regression = build_phase0_regression_record(
            record,
            run_id="synthetic_run",
            model_tier="premium",
            candidate_id="cand-001",
        )
        check(
            f"{lecture_id} regression record kind",
            regression["kind"] == "phase0_eval_regression_record",
            str(regression["kind"]),
        )
        check(
            f"{lecture_id} regression record preserves lecture/source/tier label",
            regression["lecture_id"] == lecture_id
            and regression["source_quality"] == spec["source_quality"]
            and regression["model_tier"] == "premium",
            str(regression),
        )
        check(
            f"{lecture_id} regression record overall separate from shippable",
            isinstance(regression["overall_10"], float)
            and isinstance(regression["shippable"], bool)
            and regression["overall_score_kind"] == "layer1_deterministic_only"
            and regression["layer2_judge_included"] is False,
            str(regression),
        )
        check(
            f"{lecture_id} regression record judge frozen",
            regression["judge_ready"] is False and regression["repair_ready"] is False,
        )
        check(
            f"{lecture_id} regression record default status record_only",
            regression["regression_status"] == "record_only"
            and regression["previous_overall_10"] is None
            and regression["delta_overall_10"] is None,
            str(regression),
        )
        present_keys = collect_record_keys(regression)
        leaked_keys = [key for key in FORBIDDEN_RECORD_KEYS if key in present_keys]
        check(
            f"{lecture_id} regression record has no forbidden field keys",
            leaked_keys == [],
            str(leaked_keys),
        )
        # Serializable to JSON deterministically.
        first = json.dumps(regression, sort_keys=True)
        second = json.dumps(
            build_phase0_regression_record(
                record,
                run_id="synthetic_run",
                model_tier="premium",
                candidate_id="cand-001",
            ),
            sort_keys=True,
        )
        check(f"{lecture_id} regression record deterministic JSON", first == second)
        no_canary(f"{lecture_id} phase0 regression record", regression)


def test_phase0_regression_record_sanitizes_hostile_labels() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    record = score_phase0_layer1(golden_candidate(spec), spec)
    regression = build_phase0_regression_record(
        record,
        run_id=HOSTILE_PATH,
        model_tier="enterprise",
        candidate_id=HOSTILE_URL,
    )
    check(
        "phase0 regression hostile run_id sanitized",
        regression["run_id"] == "synthetic_run",
        str(regression["run_id"]),
    )
    check(
        "phase0 regression unknown tier defaults",
        regression["model_tier"] == "unknown",
        str(regression["model_tier"]),
    )
    check(
        "phase0 regression hostile candidate_id dropped",
        regression["candidate_id"] is None,
        str(regression["candidate_id"]),
    )
    no_canary("phase0 regression hostile labels", regression)


def test_phase0_regression_jsonl_writer_appends_one_line() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    record = score_phase0_layer1(golden_candidate(spec), spec)
    regression = build_phase0_regression_record(
        record, run_id="synthetic_run", model_tier="local"
    )
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "phase0_regression.jsonl"
        append_phase0_regression_record_jsonl(target, regression)
        append_phase0_regression_record_jsonl(target, regression)
        text = target.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if line]
        check(
            "phase0 jsonl writer appends exactly one line per call",
            len(lines) == 2,
            str(len(lines)),
        )
        check(
            "phase0 jsonl writer writes compact parseable lines",
            all(
                json.loads(line)["kind"] == "phase0_eval_regression_record"
                for line in lines
            ),
            text,
        )
        # Writer must reject a record carrying a forbidden field.
        unsafe = dict(regression)
        unsafe["candidate_text"] = "anything"
        rejected = False
        try:
            append_phase0_regression_record_jsonl(target, unsafe)
        except ValueError:
            rejected = True
        check("phase0 jsonl writer rejects forbidden field", rejected)
        # Wrong kind is also rejected.
        rejected_kind = False
        try:
            append_phase0_regression_record_jsonl(target, {"kind": "other"})
        except ValueError:
            rejected_kind = True
        check("phase0 jsonl writer rejects wrong kind", rejected_kind)


def test_phase0_regression_compare_flags_drop() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    clean = score_phase0_layer1(golden_candidate(spec), spec)
    previous = build_phase0_regression_record(clean, run_id="prev", model_tier="premium")
    # Same blocking-pass profile but a synthetically lower overall_10 (> 0.3 drop).
    current = dict(previous)
    current["overall_10"] = round(previous["overall_10"] - 0.4, 4)
    verdict = compare_phase0_regression(current, previous)
    check(
        "phase0 compare flags >0.3 drop as regressed",
        verdict["regression_status"] == "regressed"
        and verdict["overall_delta"] == -0.4,
        str(verdict),
    )
    # A small drop within tolerance stays green.
    small = dict(previous)
    small["overall_10"] = round(previous["overall_10"] - 0.2, 4)
    green = compare_phase0_regression(small, previous)
    check(
        "phase0 compare small drop stays green",
        green["regression_status"] == "green",
        str(green),
    )


def test_phase0_regression_compare_flags_blocking_check() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    clean = score_phase0_layer1(golden_candidate(spec), spec)
    previous = build_phase0_regression_record(clean, run_id="prev", model_tier="premium")
    leaked = score_phase0_layer1(
        golden_candidate(spec, extra_lines=["Wait, actually unclear, so we'll trust it."]),
        spec,
    )
    current = build_phase0_regression_record(leaked, run_id="cur", model_tier="premium")
    verdict = compare_phase0_regression(current, previous)
    check(
        "phase0 compare flags newly failing blocking check",
        verdict["regression_status"] == "regressed"
        and verdict["blocking_regression_count"] >= 1,
        str(verdict),
    )


def test_phase0_regression_compare_not_comparable() -> None:
    nn3 = load_golden_pair_spec(read_golden_pair("nn3"))
    ensemble = load_golden_pair_spec(read_golden_pair("ensemble"))
    nn3_record = build_phase0_regression_record(
        score_phase0_layer1(golden_candidate(nn3), nn3),
        run_id="a",
        model_tier="premium",
    )
    ensemble_record = build_phase0_regression_record(
        score_phase0_layer1(golden_candidate(ensemble), ensemble),
        run_id="b",
        model_tier="premium",
    )
    cross = compare_phase0_regression(nn3_record, ensemble_record)
    check(
        "phase0 compare different lectures not comparable",
        cross["regression_status"] == "not_comparable"
        and "lecture_mismatch" in cross["warnings"],
        str(cross),
    )
    tier_mismatch = build_phase0_regression_record(
        score_phase0_layer1(golden_candidate(nn3), nn3),
        run_id="c",
        model_tier="local",
    )
    tier = compare_phase0_regression(nn3_record, tier_mismatch)
    check(
        "phase0 compare different tiers not comparable",
        tier["regression_status"] == "not_comparable"
        and "model_tier_mismatch" in tier["warnings"],
        str(tier),
    )


def test_phase0_regression_records_only_nn3_and_ensemble() -> None:
    # The real golden pair stays exactly {nn3, ensemble}; a record for any other
    # lecture id degrades to the closed "unknown" token rather than carrying it.
    nn3 = load_golden_pair_spec(read_golden_pair("nn3"))
    record = score_phase0_layer1(golden_candidate(nn3), nn3)
    tampered = dict(record)
    tampered["lecture_id"] = "some_other_lecture"
    regression = build_phase0_regression_record(
        tampered, run_id="x", model_tier="premium"
    )
    check(
        "phase0 regression rejects non-golden lecture id",
        regression["lecture_id"] == "unknown",
        str(regression["lecture_id"]),
    )
    for lecture_id in ("nn3", "ensemble"):
        spec = load_golden_pair_spec(read_golden_pair(lecture_id))
        kept = build_phase0_regression_record(
            score_phase0_layer1(golden_candidate(spec), spec),
            run_id="y",
            model_tier="premium",
        )
        check(
            f"{lecture_id} regression keeps real golden lecture id",
            kept["lecture_id"] == lecture_id,
            str(kept["lecture_id"]),
        )


def synthetic_reference_judge_raw(
    *,
    reference_score: int = 5,
    candidate_score: int = 4,
    evidence: bool = True,
    long_quote: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a tiny synthetic Layer-2 judge output (no real guide material)."""
    raw: dict[str, Any] = {
        "candidate_scores": {axis: candidate_score for axis in REFERENCE_JUDGE_AXES},
        "reference_scores": {axis: reference_score for axis in REFERENCE_JUDGE_AXES},
    }
    if evidence:
        if long_quote:
            quote = " ".join(["padding"] * (EVIDENCE_QUOTE_MAX_WORDS + 5))
        else:
            quote = "clear synthetic explanation with a worked step"
        raw["evidence"] = {axis: quote for axis in REFERENCE_JUDGE_AXES}
    if extra:
        raw.update(extra)
    return raw


def test_reference_judge_axes_are_exactly_seven() -> None:
    check(
        "reference judge axes are exactly the required seven",
        REFERENCE_JUDGE_AXES
        == (
            "conceptual_depth",
            "beginner_friendliness",
            "explanation_quality",
            "comparison_quality",
            "memory_support",
            "mock_question_quality",
            "density_anti_bloat",
        ),
        str(REFERENCE_JUDGE_AXES),
    )
    check("reference judge has seven axes", len(REFERENCE_JUDGE_AXES) == 7)


def test_reference_judge_prompt_builder_contract() -> None:
    prompt = build_phase0_reference_judge_prompt(
        "synthetic reference guide text",
        "synthetic candidate guide text",
        read_golden_pair("nn3"),
    )
    check(
        "reference judge prompt kind and lecture id",
        prompt["kind"] == "quality_safety_phase0_reference_judge_prompt"
        and prompt["lecture_id"] == "nn3",
        str({k: prompt[k] for k in ("kind", "lecture_id")}),
    )
    check(
        "reference judge prompt exposes 0-5 axis range and 15-word quote limit",
        prompt["axis_score_min"] == 0
        and prompt["axis_score_max"] == 5
        and prompt["evidence_quote_max_words"] == 15
        and prompt["reference_calibration_min"] == 4,
        str(prompt),
    )
    blob = json.dumps(prompt).lower()
    check(
        "reference judge prompt frames candidate vs reference benchmark",
        "candidate" in blob and "reference" in blob and "benchmark" in blob,
    )
    check(
        "reference judge prompt requires calibration and strict json",
        "calibrat" in blob and "strict json" in blob,
    )
    check(
        "reference judge prompt requires short evidence quote with 15-word limit",
        "evidence quote" in blob and "15 words" in blob,
    )
    check(
        "reference judge prompt is frozen (judge/repair not ready)",
        prompt["judge_ready"] is False and prompt["repair_ready"] is False,
    )


def test_reference_judge_prompt_builder_is_pure_no_io() -> None:
    source = (REPO / "pipeline" / "quality_safety_reference_judge.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
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
        "pipeline.run_llm_job",
    )
    bad_imports = [name for name in imports if name.startswith(forbidden_import_prefixes)]
    check("reference judge module no forbidden imports", bad_imports == [], str(bad_imports))
    forbidden_calls = {
        "urlopen",
        "post",
        "socket",
        "create_connection",
        "open",
        "write_text",
        "write_bytes",
    }
    bad_calls = sorted(set(calls) & forbidden_calls)
    check(
        "reference judge module makes no network/model/file-write calls",
        bad_calls == [],
        str(bad_calls),
    )


def test_reference_judge_sanitizer_accepts_valid_output() -> None:
    sanitized = sanitize_phase0_reference_judge_output(
        synthetic_reference_judge_raw(), read_golden_pair("nn3")
    )
    check(
        "reference judge sanitizer returns ok calibrated result",
        sanitized["status"] == "ok"
        and sanitized["calibration_status"] == "ok"
        and sanitized["layer2_judge_included"] is True,
        str(sanitized),
    )
    check(
        "reference judge sanitizer retains closed candidate axis scores",
        set(sanitized["candidate_axis_scores"]) == set(REFERENCE_JUDGE_AXES)
        and all(0 <= v <= 5 for v in sanitized["candidate_axis_scores"].values()),
        str(sanitized.get("candidate_axis_scores")),
    )
    check(
        "reference judge sanitizer keeps frozen booleans",
        sanitized["judge_ready"] is False and sanitized["repair_ready"] is False,
    )


def test_reference_judge_sanitizer_rejects_unknown_axis() -> None:
    raw = synthetic_reference_judge_raw()
    raw["candidate_scores"]["totally_unknown_axis"] = 3
    sanitized = sanitize_phase0_reference_judge_output(raw, read_golden_pair("nn3"))
    check(
        "reference judge sanitizer rejects unknown axis as invalid_output",
        sanitized["status"] == "invalid_output"
        and sanitized["layer2_judge_included"] is False
        and "candidate_axis_scores" not in sanitized,
        str(sanitized),
    )


def test_reference_judge_sanitizer_rejects_out_of_range_score() -> None:
    raw = synthetic_reference_judge_raw(candidate_score=6)
    sanitized = sanitize_phase0_reference_judge_output(raw, read_golden_pair("nn3"))
    check(
        "reference judge sanitizer rejects score outside 0..5",
        sanitized["status"] == "invalid_output"
        and sanitized["layer2_judge_included"] is False,
        str(sanitized),
    )
    raw_low = synthetic_reference_judge_raw(candidate_score=-1)
    sanitized_low = sanitize_phase0_reference_judge_output(raw_low, read_golden_pair("nn3"))
    check(
        "reference judge sanitizer rejects negative score",
        sanitized_low["status"] == "invalid_output",
        str(sanitized_low),
    )


def test_reference_judge_sanitizer_drops_long_evidence_quote() -> None:
    raw = synthetic_reference_judge_raw(long_quote=True)
    sanitized = sanitize_phase0_reference_judge_output(raw, read_golden_pair("nn3"))
    check(
        "reference judge sanitizer stays ok but drops over-long quotes",
        sanitized["status"] == "ok"
        and sanitized["evidence_quote_dropped_count"] >= 1
        and "evidence" not in sanitized,
        str(sanitized),
    )
    short = sanitize_phase0_reference_judge_output(
        synthetic_reference_judge_raw(), read_golden_pair("nn3")
    )
    check(
        "reference judge sanitizer keeps short (<=15 word) synthetic quotes",
        isinstance(short.get("evidence"), dict)
        and all(
            len(q.split()) <= EVIDENCE_QUOTE_MAX_WORDS
            for q in short["evidence"].values()
        ),
        str(short.get("evidence")),
    )


def test_reference_judge_sanitizer_marks_miscalibrated() -> None:
    raw = synthetic_reference_judge_raw(reference_score=3)
    sanitized = sanitize_phase0_reference_judge_output(raw, read_golden_pair("nn3"))
    check(
        "reference judge sanitizer marks miscalibrated when reference axis < 4",
        sanitized["status"] == "miscalibrated"
        and sanitized["calibration_status"] == "miscalibrated",
        str(sanitized),
    )
    check(
        "miscalibrated result does not include layer2 and discards candidate scores",
        sanitized["layer2_judge_included"] is False
        and "candidate_axis_scores" not in sanitized,
        str(sanitized),
    )
    check(
        "miscalibrated result keeps frozen booleans",
        sanitized["judge_ready"] is False and sanitized["repair_ready"] is False,
    )


def test_reference_judge_sanitizer_strips_hostile_fields() -> None:
    # ``evidence=False`` keeps the focus on hostile EXTRA fields: the dev-time
    # sanitized result is allowed to retain its own short (<=15 word) evidence
    # quotes, but it must never copy raw model output, prompts, source text,
    # paths, urls, or data URIs that ride along in the raw judge output.
    raw = synthetic_reference_judge_raw(
        evidence=False,
        extra={
            "model_response": HOSTILE_PROVIDER,
            "raw_prompt": HOSTILE_AUTH,
            "source_text": HOSTILE_OCR,
            "path": HOSTILE_PATH,
            "url": HOSTILE_URL,
            "image": HOSTILE_DATA,
        },
    )
    sanitized = sanitize_phase0_reference_judge_output(raw, read_golden_pair("nn3"))
    present_keys = collect_record_keys(sanitized)
    leaked_keys = [key for key in FORBIDDEN_RECORD_KEYS if key in present_keys]
    check(
        "reference judge sanitizer drops forbidden field keys",
        leaked_keys == [],
        str(leaked_keys),
    )
    hostile_keys = [
        key
        for key in ("model_response", "raw_prompt", "source_text", "path", "url", "image")
        if key in present_keys
    ]
    check(
        "reference judge sanitizer drops hostile extra fields",
        hostile_keys == [],
        str(hostile_keys),
    )
    no_canary("reference judge sanitized output", sanitized)


def test_reference_judge_regression_summary_is_record_safe() -> None:
    sanitized = sanitize_phase0_reference_judge_output(
        synthetic_reference_judge_raw(), read_golden_pair("nn3")
    )
    summary = phase0_reference_judge_regression_summary(sanitized)
    present_keys = collect_record_keys(summary)
    leaked_keys = [key for key in FORBIDDEN_RECORD_KEYS if key in present_keys]
    check(
        "reference judge regression summary drops evidence/quote keys",
        leaked_keys == [] and "evidence" not in present_keys,
        str(leaked_keys),
    )
    check(
        "reference judge regression summary stays closed and included",
        summary["status"] == "ok"
        and summary["calibration_status"] == "ok"
        and summary["layer2_judge_included"] is True,
        str(summary),
    )
    no_canary("reference judge regression summary", summary)


def test_reference_judge_layer2_integration_into_regression_record() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    layer1 = score_phase0_layer1(golden_candidate(spec), spec)
    overall_baseline = build_phase0_regression_record(
        layer1, run_id="r", model_tier="premium"
    )["overall_10"]

    ok_summary = phase0_reference_judge_regression_summary(
        sanitize_phase0_reference_judge_output(
            synthetic_reference_judge_raw(), read_golden_pair("nn3")
        )
    )
    included = build_phase0_regression_record(
        layer1,
        run_id="r",
        model_tier="premium",
        reference_judge_summary=ok_summary,
    )
    check(
        "ok layer2 summary sets layer2_judge_included true",
        included["layer2_judge_included"] is True
        and included["reference_anchored_judge"]["status"] == "ok",
        str(included["reference_anchored_judge"]),
    )
    check(
        "layer2 summary never blends into layer1 overall_10",
        included["overall_10"] == overall_baseline
        and included["overall_score_kind"] == "layer1_deterministic_only",
        str(included["overall_10"]),
    )
    check(
        "layer2 integration keeps production judge frozen",
        included["judge_ready"] is False and included["repair_ready"] is False,
    )
    present_keys = collect_record_keys(included)
    leaked_keys = [key for key in FORBIDDEN_RECORD_KEYS if key in present_keys]
    check("layer2 regression record has no forbidden keys", leaked_keys == [], str(leaked_keys))
    no_canary("layer2 regression record", included)

    miscal_summary = phase0_reference_judge_regression_summary(
        sanitize_phase0_reference_judge_output(
            synthetic_reference_judge_raw(reference_score=3), read_golden_pair("nn3")
        )
    )
    miscalibrated = build_phase0_regression_record(
        layer1,
        run_id="r",
        model_tier="premium",
        reference_judge_summary=miscal_summary,
    )
    check(
        "miscalibrated layer2 summary keeps layer2_judge_included false",
        miscalibrated["layer2_judge_included"] is False
        and miscalibrated["reference_anchored_judge"]["status"] == "miscalibrated",
        str(miscalibrated["reference_anchored_judge"]),
    )


def test_reference_judge_default_record_is_not_run() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    layer1 = score_phase0_layer1(golden_candidate(spec), spec)
    record = build_phase0_regression_record(layer1, run_id="r", model_tier="premium")
    check(
        "default regression record layer2 not included and reference not run",
        record["layer2_judge_included"] is False
        and record["reference_anchored_judge_status"] == "not_run"
        and record["reference_anchored_judge"]["status"] == "not_run",
        str(record["reference_anchored_judge"]),
    )
    check(
        "default regression record overall stays layer1 deterministic only",
        record["overall_score_kind"] == "layer1_deterministic_only",
        str(record["overall_score_kind"]),
    )
    # The default record (with the new closed sub-summary) is still JSONL-safe.
    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "phase0_regression.jsonl"
        append_phase0_regression_record_jsonl(target, record)
        lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line]
        check("default record with layer2 summary still appends one line", len(lines) == 1)


def test_reference_judge_prompt_stays_within_nn3_ensemble() -> None:
    for lecture_id in ("nn3", "ensemble"):
        prompt = build_phase0_reference_judge_prompt(
            "ref", "cand", read_golden_pair(lecture_id)
        )
        check(
            f"reference judge prompt lecture id {lecture_id}",
            prompt["lecture_id"] == lecture_id,
        )
    rejected = False
    try:
        build_phase0_reference_judge_prompt(
            "ref", "cand", {**read_golden_pair("nn3"), "lecture_id": "other_lecture"}
        )
    except GoldenPairSpecError:
        rejected = True
    check("reference judge prompt rejects non-golden lecture id", rejected)


def phase0_golden_specs() -> list[dict[str, Any]]:
    return [read_golden_pair("nn3"), read_golden_pair("ensemble")]


def phase0_clean_candidates() -> dict[str, str]:
    return {
        lecture_id: golden_candidate(load_golden_pair_spec(read_golden_pair(lecture_id)))
        for lecture_id in ("nn3", "ensemble")
    }


def test_phase0_runner_requires_exactly_nn3_and_ensemble() -> None:
    candidates = phase0_clean_candidates()
    rejected_short = False
    try:
        run_phase0_eval_harness(candidates, [read_golden_pair("nn3")])
    except GoldenPairSpecError:
        rejected_short = True
    check("phase0 runner rejects golden set missing ensemble", rejected_short)

    rejected_extra = False
    try:
        run_phase0_eval_harness(
            candidates,
            [read_golden_pair("nn3"), read_golden_pair("ensemble"), read_golden_pair("nn3")],
        )
    except GoldenPairSpecError:
        rejected_extra = True
    check("phase0 runner rejects duplicate golden spec", rejected_extra)

    run = run_phase0_eval_harness(candidates, phase0_golden_specs())
    check("phase0 runner kind", run["kind"] == "phase0_eval_harness_run")
    check(
        "phase0 runner golden pair ids exactly nn3 and ensemble",
        run["golden_pair_ids"] == ["nn3", "ensemble"],
    )
    check("phase0 runner lecture count is two", run["lecture_count"] == 2)


def test_phase0_runner_clean_candidates_all_shippable() -> None:
    run = run_phase0_eval_harness(phase0_clean_candidates(), phase0_golden_specs())
    check("phase0 runner clean all_shippable", run["all_shippable"] is True)
    check("phase0 runner clean shippable_count", run["shippable_count"] == 2)
    check("phase0 runner clean non_shippable_count", run["non_shippable_count"] == 0)
    check("phase0 runner clean min_overall_10", run["min_overall_10"] == 10.0)
    check("phase0 runner clean average_overall_10", run["average_overall_10"] == 10.0)
    check("phase0 runner clean no warnings", run["warnings"] == [], str(run["warnings"]))
    check(
        "phase0 runner overall_score_kind layer1 deterministic only",
        run["overall_score_kind"] == "layer1_deterministic_only",
    )
    check(
        "phase0 runner record count matches lectures",
        len(run["records"]) == 2
        and all(r["kind"] == "phase0_eval_regression_record" for r in run["records"]),
    )


def test_phase0_runner_bad_ensemble_candidate_not_all_shippable() -> None:
    spec = load_golden_pair_spec(read_golden_pair("ensemble"))
    wrong = [{**item, "value": item["value"] + 5.0} for item in spec["ground_truth_numerics"]]
    candidates = {
        "nn3": golden_candidate(load_golden_pair_spec(read_golden_pair("nn3"))),
        "ensemble": golden_candidate(spec, numerics=wrong),
    }
    run = run_phase0_eval_harness(candidates, phase0_golden_specs())
    check("phase0 runner bad ensemble not all_shippable", run["all_shippable"] is False)
    check("phase0 runner bad ensemble non_shippable_count", run["non_shippable_count"] == 1)
    check("phase0 runner bad ensemble shippable_count", run["shippable_count"] == 1)
    check(
        "phase0 runner bad ensemble min below average",
        run["min_overall_10"] is not None
        and run["average_overall_10"] is not None
        and run["min_overall_10"] <= run["average_overall_10"],
    )


def test_phase0_runner_deterministic_aggregate() -> None:
    candidates = phase0_clean_candidates()
    specs = phase0_golden_specs()
    first = json.dumps(run_phase0_eval_harness(candidates, specs), sort_keys=True)
    second = json.dumps(run_phase0_eval_harness(candidates, specs), sort_keys=True)
    check("phase0 runner aggregate deterministic", first == second)


def test_phase0_runner_missing_candidate_is_closed_failure() -> None:
    run = run_phase0_eval_harness(
        {"nn3": golden_candidate(load_golden_pair_spec(read_golden_pair("nn3")))},
        phase0_golden_specs(),
    )
    check("phase0 runner missing candidate warns", "candidate_missing" in run["warnings"])
    check("phase0 runner missing candidate not all_shippable", run["all_shippable"] is False)
    check("phase0 runner missing candidate still two records", len(run["records"]) == 2)
    no_canary("phase0 runner missing candidate", run)


def test_phase0_runner_judge_frozen_and_layer2_excluded_by_default() -> None:
    run = run_phase0_eval_harness(phase0_clean_candidates(), phase0_golden_specs())
    check("phase0 runner production offline judge frozen", run["production_offline_judge_frozen"] is True)
    check("phase0 runner judge_ready false", run["judge_ready"] is False)
    check("phase0 runner repair_ready false", run["repair_ready"] is False)
    check("phase0 runner layer2 excluded by default", run["layer2_judge_included"] is False)
    for record in run["records"]:
        check(
            "phase0 runner record judge frozen",
            record["judge_ready"] is False and record["repair_ready"] is False,
        )


def test_phase0_runner_accepts_caller_supplied_fact_sheet() -> None:
    sheet = synthetic_fact_sheet(total_error_fact())
    run = run_phase0_eval_harness(
        phase0_clean_candidates(),
        phase0_golden_specs(),
        fact_sheet_by_lecture_id={"nn3": sheet},
    )
    nn3_record = next(r for r in run["records"] if r["lecture_id"] == "nn3")
    summary = nn3_record["fact_sheet_summary"]
    check(
        "phase0 runner fact sheet summary kind",
        summary["kind"] == "quality_safety_phase0_fact_sheet_summary",
    )
    check(
        "phase0 runner fact sheet summary counts only",
        set(summary).issubset(
            {
                "kind",
                "fact_sheet_status",
                "recompute_verifier_status",
                "fact_sheet_numeric_count",
                "verified_numeric_count",
                "failed_numeric_count",
                "unverified_numeric_count",
                "canonical_numeric_count",
                "committed_numeric_count",
                "warnings",
            }
        ),
    )
    ensemble_record = next(r for r in run["records"] if r["lecture_id"] == "ensemble")
    check(
        "phase0 runner unsupplied lecture reports not_supplied",
        ensemble_record["fact_sheet_summary"]["fact_sheet_status"] == "not_supplied",
    )


def test_phase0_runner_layer2_only_with_explicit_ok_summary() -> None:
    ok_summary = {
        "status": "ok",
        "calibration_status": "ok",
        "candidate_axis_scores": {axis: 5 for axis in REFERENCE_JUDGE_AXES},
        "reference_axis_scores": {axis: 5 for axis in REFERENCE_JUDGE_AXES},
    }
    run = run_phase0_eval_harness(
        phase0_clean_candidates(),
        phase0_golden_specs(),
        reference_judge_summary_by_lecture_id={"nn3": ok_summary},
    )
    check("phase0 runner layer2 included with ok summary", run["layer2_judge_included"] is True)
    check(
        "phase0 runner overall stays layer1 deterministic with layer2 summary",
        run["overall_score_kind"] == "layer1_deterministic_only"
        and run["min_overall_10"] == 10.0,
    )
    bad = run_phase0_eval_harness(
        phase0_clean_candidates(),
        phase0_golden_specs(),
        reference_judge_summary_by_lecture_id={"nn3": "not-a-dict"},
    )
    check(
        "phase0 runner ignores non-dict reference summary",
        bad["layer2_judge_included"] is False
        and "reference_summary_input_ignored" in bad["warnings"],
    )


def test_phase0_runner_record_has_no_raw_material() -> None:
    spec = load_golden_pair_spec(read_golden_pair("nn3"))
    hostile_topics = spec["expected_topics"] + HOSTILE_CANARIES
    candidates = {
        "nn3": golden_candidate(spec, topics=hostile_topics, extra_lines=HOSTILE_CANARIES),
        "ensemble": golden_candidate(load_golden_pair_spec(read_golden_pair("ensemble"))),
    }
    run = run_phase0_eval_harness(candidates, phase0_golden_specs())
    no_canary("phase0 runner aggregate", run)
    for record in run["records"]:
        no_canary("phase0 runner record", record)


def test_phase0_exit_check_blocked_before_real_runs() -> None:
    run = run_phase0_eval_harness(phase0_clean_candidates(), phase0_golden_specs())
    exit_check = build_phase0_exit_check(run)
    check("phase0 exit-check kind", exit_check["kind"] == "phase0_exit_check")
    check(
        "phase0 exit-check phase token",
        exit_check["phase"] == "phase0_eval_harness_fact_sheet_skeleton",
    )
    check(
        "phase0 exit-check clean run is not_ready (structural blockers hold)",
        exit_check["phase0_exit_status"] == "not_ready",
        exit_check["phase0_exit_status"],
    )
    check(
        "phase0 exit-check never ready in this slice",
        exit_check["phase0_exit_status"] != "ready",
    )
    check(
        "phase0 exit-check golden pair ids",
        exit_check["golden_pair_ids"] == ["nn3", "ensemble"],
    )
    check(
        "phase0 exit-check judge frozen",
        exit_check["production_offline_judge_frozen"] is True
        and exit_check["judge_ready"] is False
        and exit_check["repair_ready"] is False,
    )


def test_phase0_exit_check_blockers_are_closed_tokens() -> None:
    allowed_blockers = {
        "phase0_required_run_missing",
        "phase0_run_not_all_shippable",
        "real_old_ensemble_run_not_recorded",
        "reference_judge_execution_not_run",
        "reference_judge_calibration_not_recorded",
        "fact_sheet_production_wiring_not_present",
        "regression_history_not_established",
    }
    run = run_phase0_eval_harness(phase0_clean_candidates(), phase0_golden_specs())
    exit_check = build_phase0_exit_check(run)
    check(
        "phase0 exit-check blockers closed tokens only",
        set(exit_check["blockers"]).issubset(allowed_blockers),
        str(exit_check["blockers"]),
    )
    check(
        "phase0 exit-check structural blockers present",
        {
            "real_old_ensemble_run_not_recorded",
            "reference_judge_execution_not_run",
            "reference_judge_calibration_not_recorded",
            "fact_sheet_production_wiring_not_present",
            "regression_history_not_established",
        }.issubset(set(exit_check["blockers"])),
    )
    check(
        "phase0 exit-check next_step closed token",
        exit_check["next_step"]
        in ("phase0_address_non_shippable_run", "phase0_record_real_runs_and_judge_calibration"),
    )


def test_phase0_exit_check_satisfied_includes_built_components() -> None:
    run = run_phase0_eval_harness(phase0_clean_candidates(), phase0_golden_specs())
    exit_check = build_phase0_exit_check(run)
    expected_satisfied = {
        "golden_pair_specs_present",
        "layer1_deterministic_scorer_present",
        "overall_10_separate_from_shippable",
        "regression_record_shape_present",
        "reference_judge_contract_present",
        "factsheet_recompute_integration_present",
        "production_offline_judge_frozen",
    }
    check(
        "phase0 exit-check satisfied lists built components",
        set(exit_check["satisfied"]) == expected_satisfied,
        str(exit_check["satisfied"]),
    )


def test_phase0_exit_check_vocabularies_are_closed_and_well_formed() -> None:
    # The module-level closed vocabularies must match the canonical spelling
    # exactly so a garbled/pasted token (e.g. slit_recorded, referencded, rshed)
    # can never become a live blocker/satisfied token.
    canonical_blockers = (
        "phase0_required_run_missing",
        "phase0_run_not_all_shippable",
        "real_old_ensemble_run_not_recorded",
        "reference_judge_execution_not_run",
        "reference_judge_calibration_not_recorded",
        "fact_sheet_production_wiring_not_present",
        "regression_history_not_established",
    )
    canonical_satisfied = (
        "golden_pair_specs_present",
        "layer1_deterministic_scorer_present",
        "overall_10_separate_from_shippable",
        "regression_record_shape_present",
        "reference_judge_contract_present",
        "factsheet_recompute_integration_present",
        "production_offline_judge_frozen",
    )
    check(
        "phase0 exit-check blocker vocabulary pinned",
        PHASE0_EXIT_BLOCKER_ORDER == canonical_blockers,
        str(PHASE0_EXIT_BLOCKER_ORDER),
    )
    check(
        "phase0 exit-check satisfied vocabulary pinned",
        PHASE0_EXIT_SATISFIED_ORDER == canonical_satisfied,
        str(PHASE0_EXIT_SATISFIED_ORDER),
    )
    # No malformed/garbled tokens anywhere in the closed vocabularies.
    malformed = {"slit_recorded", "referencded", "rshed", "slit"}
    vocab = set(PHASE0_EXIT_BLOCKER_ORDER) | set(PHASE0_EXIT_SATISFIED_ORDER)
    check(
        "phase0 exit-check vocab has no malformed tokens",
        not (vocab & malformed),
        str(vocab & malformed),
    )
    token_re = re.compile(r"^[a-z0-9_]+$")
    check(
        "phase0 exit-check vocab tokens are clean snake_case",
        all(token_re.match(token) for token in vocab),
        str(sorted(t for t in vocab if not token_re.match(t))),
    )
    # Every token emitted by the runner+exit-check must be a member of the
    # declared closed vocabulary -- no free-form or garbled tokens can appear.
    for candidates in (phase0_clean_candidates(), None):
        run = (
            run_phase0_eval_harness(candidates, phase0_golden_specs())
            if candidates is not None
            else None
        )
        exit_check = build_phase0_exit_check(run)
        check(
            "phase0 exit-check emitted blockers are closed-vocab members",
            set(exit_check["blockers"]).issubset(set(PHASE0_EXIT_BLOCKER_ORDER)),
            str(exit_check["blockers"]),
        )
        check(
            "phase0 exit-check emitted satisfied are closed-vocab members",
            set(exit_check["satisfied"]).issubset(set(PHASE0_EXIT_SATISFIED_ORDER)),
            str(exit_check["satisfied"]),
        )
        check(
            "phase0 exit-check emitted tokens have no malformed members",
            not ((set(exit_check["blockers"]) | set(exit_check["satisfied"])) & malformed),
        )


def test_phase0_exit_check_flags_non_shippable_run() -> None:
    spec = load_golden_pair_spec(read_golden_pair("ensemble"))
    wrong = [{**item, "value": item["value"] + 5.0} for item in spec["ground_truth_numerics"]]
    candidates = {
        "nn3": golden_candidate(load_golden_pair_spec(read_golden_pair("nn3"))),
        "ensemble": golden_candidate(spec, numerics=wrong),
    }
    run = run_phase0_eval_harness(candidates, phase0_golden_specs())
    exit_check = build_phase0_exit_check(run)
    check(
        "phase0 exit-check blocked on non-shippable run",
        exit_check["phase0_exit_status"] == "blocked"
        and "phase0_run_not_all_shippable" in exit_check["blockers"],
    )

    missing = build_phase0_exit_check(None)
    check(
        "phase0 exit-check flags missing run",
        "phase0_required_run_missing" in missing["blockers"]
        and missing["phase0_exit_status"] != "ready",
    )


def test_phase0_runner_and_exit_check_no_leak_sweep() -> None:
    run = run_phase0_eval_harness(phase0_clean_candidates(), phase0_golden_specs())
    exit_check = build_phase0_exit_check(run)
    no_canary("phase0 runner sweep", run)
    no_canary("phase0 exit-check sweep", exit_check)


# --- Slice 166: local-operator run packet + closed result ingest ------------


def synthetic_operator_run_summary(
    *,
    run_label: str,
    all_shippable: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A tiny synthetic closed operator run summary (no real material)."""
    summary: dict[str, Any] = {
        "kind": PHASE0_RUN_KIND,
        "run_label": run_label,
        "all_shippable": all_shippable,
        "shippable_count": 2 if all_shippable else 1,
        "non_shippable_count": 0 if all_shippable else 1,
        "overall_score_kind": "layer1_deterministic_only",
    }
    if extra:
        summary.update(extra)
    return summary


def synthetic_operator_reference_summary() -> dict[str, Any]:
    return {
        "kind": PHASE0_OPERATOR_REFERENCE_JUDGE_SUMMARY_KIND,
        "reference_judge_status": "ok",
        "calibrated": True,
        "calibration_status": "ok",
    }


def synthetic_operator_full_results() -> list[dict[str, Any]]:
    return [
        synthetic_operator_run_summary(run_label="nn3_current_candidate"),
        synthetic_operator_run_summary(run_label="ensemble_current_candidate"),
        synthetic_operator_run_summary(
            run_label="ensemble_old_failure_candidate", all_shippable=False
        ),
        synthetic_operator_run_summary(run_label="reference_judge_calibration_run"),
        synthetic_operator_reference_summary(),
        {"kind": PHASE0_REGRESSION_RECORD_KIND, "lecture_id": "nn3"},
    ]


def test_phase0_operator_run_packet_is_closed_and_exact() -> None:
    packet = build_phase0_operator_run_packet()
    check(
        "operator run packet kind",
        packet["kind"] == "phase0_operator_run_packet"
        and packet["kind"] == PHASE0_OPERATOR_RUN_PACKET_KIND,
        str(packet["kind"]),
    )
    check(
        "operator run packet golden pair is exactly nn3 and ensemble",
        packet["golden_pair_ids"] == ["nn3", "ensemble"],
        str(packet["golden_pair_ids"]),
    )
    check(
        "operator run packet required local runs",
        packet["required_local_runs"] == list(PHASE0_OPERATOR_REQUIRED_LOCAL_RUNS)
        and "ensemble_old_failure_candidate" in packet["required_local_runs"]
        and "reference_judge_calibration_run" in packet["required_local_runs"],
        str(packet["required_local_runs"]),
    )
    check(
        "operator run packet required closed outputs",
        packet["required_closed_outputs"] == list(PHASE0_OPERATOR_REQUIRED_CLOSED_OUTPUTS),
        str(packet["required_closed_outputs"]),
    )
    check(
        "operator run packet forbidden outputs listed",
        set(("source_text", "guide_text", "reference_text", "raw_prompt", "raw_response",
             "provider_payload", "filepath", "filename", "hash", "byte_count", "screenshot"))
        .issubset(set(packet["forbidden_outputs"]))
        and set(packet["forbidden_outputs"]) == set(PHASE0_OPERATOR_FORBIDDEN_OUTPUTS),
        str(packet["forbidden_outputs"]),
    )
    check(
        "operator run packet judge frozen + closed-summary only",
        packet["production_offline_judge_frozen"] is True
        and packet["judge_ready"] is False
        and packet["repair_ready"] is False
        and packet["layer2_execution_mode"] == "operator_local_only_not_in_production"
        and packet["persistence_policy"] == "closed_summary_only",
        str(packet),
    )
    check(
        "operator run packet numeric strategy is recompute-first not known_numbers",
        packet["numeric_strategy"] == "recompute_first_not_manual_known_numbers",
        str(packet["numeric_strategy"]),
    )
    # The packet alias returns an equal, fresh object.
    alias = get_phase0_operator_run_packet()
    check("operator run packet alias equal and fresh", alias == packet and alias is not packet)


def test_phase0_operator_run_packet_has_no_private_material() -> None:
    packet = build_phase0_operator_run_packet()
    no_canary("operator run packet", packet)
    blob = json.dumps(packet, sort_keys=True)
    # No private paths, file extensions, shell-ish path templates, hashes, byte
    # counts, or source/reference document names.
    for pattern in (
        re.compile(r"/home/|/mnt/|/tmp/"),
        re.compile(r"\.pdf|\.docx|\.zip|\.png|\.jpg", re.IGNORECASE),
        re.compile(r"[a-f0-9]{32,}"),
        re.compile(r"[0-9]{7,}\s*bytes"),
        re.compile(r"https?://"),
    ):
        check(
            f"operator run packet has no private material ({pattern.pattern})",
            not pattern.search(blob),
            pattern.pattern,
        )


def test_phase0_operator_ingest_accepts_valid_closed_summaries() -> None:
    run_ingest = ingest_phase0_operator_closed_result(
        synthetic_operator_run_summary(run_label="nn3_current_candidate")
    )
    check(
        "ingest accepts valid run summary",
        run_ingest["ingest_status"] == "ok"
        and run_ingest["accepted_kind"] == PHASE0_RUN_KIND,
        str(run_ingest),
    )
    exit_ingest = ingest_phase0_operator_closed_result(
        {"kind": PHASE0_EXIT_CHECK_KIND, "phase0_exit_status": "not_ready", "blocker_count": 5}
    )
    check(
        "ingest accepts valid exit-check summary",
        exit_ingest["ingest_status"] == "ok"
        and exit_ingest["accepted_kind"] == PHASE0_EXIT_CHECK_KIND,
        str(exit_ingest),
    )
    ref_ingest = ingest_phase0_operator_closed_result(synthetic_operator_reference_summary())
    check(
        "ingest accepts valid reference judge summary",
        ref_ingest["ingest_status"] == "ok"
        and ref_ingest["accepted_kind"] == PHASE0_OPERATOR_REFERENCE_JUDGE_SUMMARY_KIND,
        str(ref_ingest),
    )
    reg_ingest = ingest_phase0_operator_closed_result(
        {"kind": PHASE0_REGRESSION_RECORD_KIND, "lecture_id": "ensemble", "overall_10": 9.7}
    )
    check(
        "ingest accepts valid regression record summary",
        reg_ingest["ingest_status"] == "ok"
        and reg_ingest["accepted_kind"] == PHASE0_REGRESSION_RECORD_KIND,
        str(reg_ingest),
    )
    # Sanitized result is closed and always carries frozen booleans.
    for ingest in (run_ingest, exit_ingest, ref_ingest, reg_ingest):
        sanitized = ingest["sanitized_result"]
        check(
            "ingest sanitized result keeps judge frozen",
            sanitized["judge_ready"] is False
            and sanitized["repair_ready"] is False
            and sanitized["production_offline_judge_frozen"] is True,
            str(sanitized),
        )
        check(
            "ingest record keeps judge frozen",
            ingest["judge_ready"] is False and ingest["repair_ready"] is False,
        )


def test_phase0_operator_ingest_rejects_forbidden_keys() -> None:
    forbidden_payloads = {
        "source_text": {"kind": PHASE0_RUN_KIND, "source_text": "x"},
        "guide_text": {"kind": PHASE0_RUN_KIND, "guide_text": "x"},
        "reference_text": {"kind": PHASE0_RUN_KIND, "reference_text": "x"},
        "raw_prompt": {"kind": PHASE0_RUN_KIND, "raw_prompt": "x"},
        "raw_response": {"kind": PHASE0_RUN_KIND, "raw_response": "x"},
        "provider_payload": {"kind": PHASE0_RUN_KIND, "provider_payload": "x"},
        "path": {"kind": PHASE0_RUN_KIND, "path": "x"},
        "filename": {"kind": PHASE0_RUN_KIND, "filename": "x"},
        "hash": {"kind": PHASE0_RUN_KIND, "hash": "x"},
        "byte_count": {"kind": PHASE0_RUN_KIND, "byte_count": 5},
        "screenshot": {"kind": PHASE0_RUN_KIND, "screenshot": "x"},
        # Nested forbidden key must also be caught.
        "nested_guide_text": {"kind": PHASE0_RUN_KIND, "inner": {"guide_text": "x"}},
    }
    for name, payload in forbidden_payloads.items():
        ingest = ingest_phase0_operator_closed_result(payload)
        check(
            f"ingest rejects forbidden key ({name})",
            ingest["ingest_status"] == "blocked"
            and "forbidden_key_present" in ingest["blockers"]
            and ingest["sanitized_result"] is None,
            str(ingest),
        )
        no_canary(f"ingest forbidden {name}", ingest)


def test_phase0_operator_ingest_rejects_private_strings() -> None:
    cases = {
        "/home/private/source.txt": "private_path_like_value",
        "/mnt/data/reference": "private_path_like_value",
        "data:image/png;base64,AAAA": "data_uri_or_encoded_value",
        "this is base64 encoded": "data_uri_or_encoded_value",
        "Authorization: Bearer xyz": "secret_like_value",
        "api_key=zzz": "secret_like_value",
        "the secret value here": "secret_like_value",
    }
    for value, expected_token in cases.items():
        ingest = ingest_phase0_operator_closed_result(
            {"kind": PHASE0_EXIT_CHECK_KIND, "note": value}
        )
        check(
            f"ingest rejects private-looking string ({expected_token})",
            ingest["ingest_status"] == "blocked"
            and expected_token in ingest["blockers"]
            and ingest["sanitized_result"] is None,
            str(ingest),
        )
        no_canary(f"ingest private string {expected_token}", ingest)
    # A long evidence quote is rejected even without paths/secrets.
    long_quote = "the model explained the gradient step in great careful pedagogical detail here"
    quote_ingest = ingest_phase0_operator_closed_result(
        {"kind": PHASE0_REGRESSION_RECORD_KIND, "note": long_quote}
    )
    check(
        "ingest rejects long evidence quote",
        quote_ingest["ingest_status"] == "blocked"
        and "long_evidence_quote_value" in quote_ingest["blockers"],
        str(quote_ingest),
    )


def test_phase0_operator_ingest_never_allows_judge_or_repair_ready() -> None:
    for flag in ("judge_ready", "repair_ready"):
        ingest = ingest_phase0_operator_closed_result(
            {"kind": PHASE0_RUN_KIND, flag: True}
        )
        check(
            f"ingest blocks {flag}=true",
            ingest["ingest_status"] == "blocked"
            and f"{flag}_must_stay_false" in ingest["blockers"]
            and ingest["judge_ready"] is False
            and ingest["repair_ready"] is False,
            str(ingest),
        )
    # Even on an otherwise-clean ok result, the sanitized projection forces both
    # frozen booleans to False (they can never be carried through as True).
    ok = ingest_phase0_operator_closed_result(
        synthetic_operator_run_summary(run_label="nn3_current_candidate")
    )
    check(
        "ingest sanitized never carries judge/repair ready true",
        ok["sanitized_result"]["judge_ready"] is False
        and ok["sanitized_result"]["repair_ready"] is False,
        str(ok["sanitized_result"]),
    )


def test_phase0_operator_ingest_invalid_shapes() -> None:
    not_mapping = ingest_phase0_operator_closed_result(["not", "a", "mapping"])
    check(
        "ingest marks non-mapping invalid",
        not_mapping["ingest_status"] == "invalid"
        and "result_not_mapping" in not_mapping["blockers"],
        str(not_mapping),
    )
    unknown = ingest_phase0_operator_closed_result({"kind": "phase0_unknown_kind"})
    check(
        "ingest marks unknown kind invalid",
        unknown["ingest_status"] == "invalid"
        and "unknown_result_kind" in unknown["blockers"]
        and unknown["accepted_kind"] is None,
        str(unknown),
    )
    check(
        "ingest result kinds are exactly the four operator closed outputs",
        PHASE0_OPERATOR_RESULT_KINDS == set(PHASE0_OPERATOR_REQUIRED_CLOSED_OUTPUTS),
        str(PHASE0_OPERATOR_RESULT_KINDS),
    )
    check(
        "ingest blocker tokens are closed snake_case",
        all(re.match(r"^[a-z0-9_]+$", t) for t in PHASE0_OPERATOR_INGEST_BLOCKER_ORDER),
        str(PHASE0_OPERATOR_INGEST_BLOCKER_ORDER),
    )


def test_phase0_operator_exit_check_not_ready_when_summaries_missing() -> None:
    empty = build_phase0_exit_check_from_operator_results([])
    check(
        "operator exit-check empty is not_ready",
        empty["phase0_exit_status"] == "not_ready",
        str(empty["phase0_exit_status"]),
    )
    check(
        "operator exit-check empty lists missing-summary blockers",
        {
            "real_old_ensemble_run_not_recorded",
            "reference_judge_execution_not_run",
            "reference_judge_calibration_not_recorded",
            "fact_sheet_production_wiring_not_present",
            "regression_history_not_established",
        }.issubset(set(empty["blockers"])),
        str(empty["blockers"]),
    )
    # Blockers are a closed subset of the shared exit-check blocker vocabulary.
    check(
        "operator exit-check blockers closed tokens only",
        set(empty["blockers"]).issubset(set(PHASE0_EXIT_BLOCKER_ORDER)),
        str(empty["blockers"]),
    )
    check(
        "operator exit-check judge frozen",
        empty["production_offline_judge_frozen"] is True
        and empty["judge_ready"] is False
        and empty["repair_ready"] is False,
    )


def test_phase0_operator_exit_check_never_ready_even_when_full() -> None:
    # Even with all required closed summaries present and valid, readiness can
    # never be faked: the fact-sheet production-wiring blocker is structural.
    exit_check = build_phase0_exit_check_from_operator_results(synthetic_operator_full_results())
    check(
        "operator exit-check full set is not ready",
        exit_check["phase0_exit_status"] != "ready",
        str(exit_check["phase0_exit_status"]),
    )
    check(
        "operator exit-check full set still blocks on fact-sheet wiring",
        exit_check["blockers"] == ["fact_sheet_production_wiring_not_present"],
        str(exit_check["blockers"]),
    )
    check(
        "operator exit-check satisfied lists recorded runs",
        {
            "operator_results_validated_closed",
            "operator_nn3_current_run_recorded",
            "operator_ensemble_current_run_recorded",
            "operator_ensemble_old_failure_run_recorded",
            "operator_reference_judge_execution_recorded",
            "operator_reference_judge_calibration_recorded",
            "operator_regression_history_recorded",
            "production_offline_judge_frozen",
        }.issubset(set(exit_check["satisfied"])),
        str(exit_check["satisfied"]),
    )
    check(
        "operator exit-check satisfied closed vocab only",
        set(exit_check["satisfied"]).issubset(set(PHASE0_OPERATOR_EXIT_SATISFIED_ORDER)),
        str(exit_check["satisfied"]),
    )
    check("operator exit-check validated count", exit_check["validated_result_count"] == 6)


def test_phase0_operator_exit_check_blocks_on_failing_current_candidate() -> None:
    results = [
        synthetic_operator_run_summary(run_label="nn3_current_candidate"),
        synthetic_operator_run_summary(
            run_label="ensemble_current_candidate", all_shippable=False
        ),
    ]
    exit_check = build_phase0_exit_check_from_operator_results(results)
    check(
        "operator exit-check blocked on failing current candidate",
        exit_check["phase0_exit_status"] == "blocked"
        and "phase0_run_not_all_shippable" in exit_check["blockers"],
        str(exit_check),
    )


def test_phase0_operator_exit_check_drops_invalid_results() -> None:
    # Invalid/blocked results never count toward readiness.
    mixed = [
        {"kind": "phase0_unknown_kind"},
        {"kind": PHASE0_RUN_KIND, "guide_text": "leak"},
        synthetic_operator_run_summary(run_label="nn3_current_candidate"),
    ]
    exit_check = build_phase0_exit_check_from_operator_results(mixed)
    check(
        "operator exit-check counts only validated ok results",
        exit_check["validated_result_count"] == 1,
        str(exit_check["validated_result_count"]),
    )
    check(
        "operator exit-check still not_ready with one valid result",
        exit_check["phase0_exit_status"] == "not_ready",
        str(exit_check["phase0_exit_status"]),
    )


def test_phase0_operator_layer_no_leak_and_not_known_numbers() -> None:
    # Reference-anchored dev-time judge stays separate from this ingest layer and
    # is never executed here: feeding a reference summary only records a closed,
    # frozen status; it computes no axis blend and flips no judge gate.
    packet = build_phase0_operator_run_packet()
    no_canary("operator packet sweep", packet)
    hostile = {
        "kind": PHASE0_RUN_KIND,
        "run_label": "nn3_current_candidate",
        "note": HOSTILE_PATH,
        "guide_text": HOSTILE_OCR,
        "payload": HOSTILE_PROVIDER,
    }
    ingest = ingest_phase0_operator_closed_result(hostile)
    check(
        "operator ingest blocks hostile candidate",
        ingest["ingest_status"] == "blocked",
        str(ingest["ingest_status"]),
    )
    no_canary("operator ingest hostile sweep", ingest)
    exit_check = build_phase0_exit_check_from_operator_results([hostile])
    no_canary("operator exit-check hostile sweep", exit_check)
    # Recompute-first numeric strategy, not manual operator known_numbers: the
    # packet declares the strategy and the ingest carries no per-numeric "known"
    # answer fields (it accepts only closed counts/statuses).
    check(
        "operator layer keeps numeric strategy recompute-first",
        packet["numeric_strategy"] == "recompute_first_not_manual_known_numbers",
        str(packet["numeric_strategy"]),
    )
    ok = ingest_phase0_operator_closed_result(
        synthetic_operator_run_summary(run_label="nn3_current_candidate")
    )
    check(
        "operator ingest carries no manual known_numbers field",
        "known_numbers" not in json.dumps(ok["sanitized_result"], sort_keys=True),
        str(ok["sanitized_result"]),
    )


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
    test_seed_fixture_file_consumption()
    test_leaked_reasoning()
    test_numeric_correctness()
    test_worked_answer_completeness()
    test_coverage()
    test_mock_question_count()
    test_regression_record()
    test_no_leak_sweep()
    test_run_quality_safety_eval_wrapper()
    test_golden_pair_set_is_exactly_nn3_and_ensemble()
    test_golden_pair_nn3_topics_and_numerics()
    test_golden_pair_ensemble_topics_and_numerics()
    test_golden_pair_tier_targets()
    test_golden_pair_no_raw_material_fields()
    test_golden_pair_rejects_synthetic_fixtures()
    test_phase0_report_skeleton_judge_frozen()
    test_phase0_scorer_clean_candidate_passes()
    test_phase0_fact_sheet_not_supplied_preserves_layer1_behavior()
    test_phase0_fact_sheet_verified_and_canonical_summary_passes()
    test_phase0_recompute_failed_numeric_blocks_even_if_printed()
    test_phase0_unverified_fact_never_creates_confidence()
    test_phase0_verified_fact_still_requires_candidate_value()
    test_phase0_fact_sheet_summary_is_counts_only()
    test_phase0_regression_record_includes_safe_fact_sheet_summary()
    test_phase0_scorer_leaked_reasoning_blocks()
    test_phase0_scorer_missing_numeric_blocks()
    test_phase0_scorer_ensemble_gini_weight_numeric()
    test_phase0_numeric_ignores_label_internal_parameters()
    test_phase0_numeric_natural_wrong_answer_still_fails()
    test_phase0_numeric_ensemble_natural_contradiction_and_mismatch()
    test_phase0_scorer_coverage_below_threshold_blocks()
    test_phase0_scorer_mock_below_min_is_advisory()
    test_phase0_scorer_worked_answer_unresolved_blocks()
    test_phase0_scorer_no_raw_material_leak()
    test_phase0_scorer_rejects_synthetic_and_judge_frozen()
    test_phase0_overall_clean_candidate_high_and_shippable()
    test_phase0_overall_leaked_reasoning_lowers_and_blocks()
    test_phase0_overall_missing_numeric_lowers_and_blocks()
    test_phase0_overall_low_mock_is_advisory_only()
    test_phase0_overall_judge_frozen_unoverrideable()
    test_phase0_regression_record_closed_and_safe()
    test_phase0_regression_record_sanitizes_hostile_labels()
    test_phase0_regression_jsonl_writer_appends_one_line()
    test_phase0_regression_compare_flags_drop()
    test_phase0_regression_compare_flags_blocking_check()
    test_phase0_regression_compare_not_comparable()
    test_phase0_regression_records_only_nn3_and_ensemble()
    test_reference_judge_axes_are_exactly_seven()
    test_reference_judge_prompt_builder_contract()
    test_reference_judge_prompt_builder_is_pure_no_io()
    test_reference_judge_sanitizer_accepts_valid_output()
    test_reference_judge_sanitizer_rejects_unknown_axis()
    test_reference_judge_sanitizer_rejects_out_of_range_score()
    test_reference_judge_sanitizer_drops_long_evidence_quote()
    test_reference_judge_sanitizer_marks_miscalibrated()
    test_reference_judge_sanitizer_strips_hostile_fields()
    test_reference_judge_regression_summary_is_record_safe()
    test_reference_judge_layer2_integration_into_regression_record()
    test_reference_judge_default_record_is_not_run()
    test_reference_judge_prompt_stays_within_nn3_ensemble()
    test_phase0_runner_requires_exactly_nn3_and_ensemble()
    test_phase0_runner_clean_candidates_all_shippable()
    test_phase0_runner_bad_ensemble_candidate_not_all_shippable()
    test_phase0_runner_deterministic_aggregate()
    test_phase0_runner_missing_candidate_is_closed_failure()
    test_phase0_runner_judge_frozen_and_layer2_excluded_by_default()
    test_phase0_runner_accepts_caller_supplied_fact_sheet()
    test_phase0_runner_layer2_only_with_explicit_ok_summary()
    test_phase0_runner_record_has_no_raw_material()
    test_phase0_exit_check_blocked_before_real_runs()
    test_phase0_exit_check_blockers_are_closed_tokens()
    test_phase0_exit_check_satisfied_includes_built_components()
    test_phase0_exit_check_vocabularies_are_closed_and_well_formed()
    test_phase0_exit_check_flags_non_shippable_run()
    test_phase0_runner_and_exit_check_no_leak_sweep()
    test_phase0_operator_run_packet_is_closed_and_exact()
    test_phase0_operator_run_packet_has_no_private_material()
    test_phase0_operator_ingest_accepts_valid_closed_summaries()
    test_phase0_operator_ingest_rejects_forbidden_keys()
    test_phase0_operator_ingest_rejects_private_strings()
    test_phase0_operator_ingest_never_allows_judge_or_repair_ready()
    test_phase0_operator_ingest_invalid_shapes()
    test_phase0_operator_exit_check_not_ready_when_summaries_missing()
    test_phase0_operator_exit_check_never_ready_even_when_full()
    test_phase0_operator_exit_check_blocks_on_failing_current_candidate()
    test_phase0_operator_exit_check_drops_invalid_results()
    test_phase0_operator_layer_no_leak_and_not_known_numbers()
    test_import_hygiene()
    print(f"\nquality_safety_eval_harness: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
