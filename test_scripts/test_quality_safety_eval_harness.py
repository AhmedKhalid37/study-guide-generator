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
    GoldenPairSpecError,
    append_phase0_regression_record_jsonl,
    build_phase0_regression_record,
    build_phase0_report_skeleton,
    build_quality_safety_regression_record,
    compare_phase0_regression,
    compute_phase0_overall_10,
    load_golden_pair_spec,
    load_golden_pair_specs,
    load_quality_safety_fixture_spec,
    run_quality_safety_eval,
    run_quality_safety_layer1_checks,
    score_phase0_layer1,
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
    test_import_hygiene()
    print(f"\nquality_safety_eval_harness: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
