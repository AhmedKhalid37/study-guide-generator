#!/usr/bin/env python3
"""Tests for Slice 117 Quality Safety fact-sheet producer v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts.
"""
from __future__ import annotations

import ast
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_canonical_matcher import build_quality_safety_canonical_match_report  # noqa: E402
from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet  # noqa: E402
from pipeline.quality_safety_fact_sheet_producer import (  # noqa: E402
    build_quality_safety_fact_sheet_from_extraction,
    extract_quality_safety_computation_records,
    extract_quality_safety_numeric_observations,
    normalize_quality_safety_extraction_bundle,
    run_quality_safety_fact_sheet_producer,
)
from pipeline.quality_safety_recompute_verifier import verify_quality_safety_fact_sheet  # noqa: E402
from pipeline.quality_safety_unified_qa import run_quality_safety_unified_floor  # noqa: E402

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_producer1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_PRODUCER_MARKER",
    "TABLE_TEXT_PRIVATE_PRODUCER_MARKER",
    "CAPTION_PRIVATE_PRODUCER_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_PRODUCER_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MARKER",
    "source text private marker",
    "E=mc^2_private_formula_marker",
)
FORBIDDEN_MARKERS = (
    "/home/fake_private",
    "C:\\fake_private",
    "https://",
    "Authorization",
    "Bearer",
    "sk_producer",
    "data:image",
    "base64",
    "OCR_PRIVATE",
    "TABLE_TEXT_PRIVATE",
    "CAPTION_PRIVATE",
    "PROVIDER_PAYLOAD_PRIVATE",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MARKER",
    "source text private marker",
    "private_formula_marker",
)
PRODUCER_WARNINGS = {
    "malformed_extraction_bundle_degraded",
    "invalid_lecture_id",
    "invalid_source_quality",
    "invalid_concept_dropped",
    "invalid_source_ref",
    "invalid_computation_record_dropped",
    "invalid_numeric_observation_dropped",
    "invalid_computation_method",
    "invalid_computation_inputs",
    "invalid_numeric_value",
    "unsafe_string_sanitized",
    "max_items_reached",
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
    "chandra",
    "mistral",
    "gemini",
    "socket",
    "subprocess",
)
ALLOWED_IMPORTS = {"__future__", "math", "re", "typing", "pipeline.quality_safety_fact_sheet"}


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        suffix = f" - {detail}" if detail else ""
        print(f"[FAIL] {name}{suffix}")


def serialized(node: Any) -> str:
    return json.dumps(node, sort_keys=True)


def assert_no_canary(name: str, node: Any) -> None:
    blob = serialized(node)
    found = [marker for marker in FORBIDDEN_MARKERS if marker in blob]
    found += [canary for canary in HOSTILE_CANARIES if canary in blob]
    check(f"{name}: no hostile canary", not found, str(found))


def assert_closed_warnings(name: str, result: dict[str, Any]) -> None:
    warnings = result.get("warnings", [])
    check(f"{name}: producer warnings closed", all(item in PRODUCER_WARNINGS for item in warnings), str(warnings))


def assert_summary_shape(name: str, result: dict[str, Any]) -> None:
    summary = result.get("summary", {})
    expected = {
        "concept_count",
        "computation_record_count",
        "numeric_observation_count",
        "produced_fact_count",
        "dropped_item_count",
        "warning_count",
    }
    check(f"{name}: summary keys", set(summary) == expected, str(summary))
    check(
        f"{name}: summary non-negative ints",
        all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in summary.values()),
        str(summary),
    )


def weighted_bundle(*, claimed: float = 0.2, lecture_id: str = "synthetic_fixture") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_extraction_bundle",
        "lecture_id": lecture_id,
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": "Synthetic Concept",
                "source_ref": "source_page_1",
                "computation_records": [
                    {
                        "id": "synthetic.weighted_gini.fact",
                        "label": "synthetic_stump_choice_score",
                        "type": "numeric",
                        "method": "weighted_gini",
                        "inputs": {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]},
                        "claimed_value": claimed,
                        "tolerance": 0.01,
                    }
                ],
                "numeric_observations": [
                    {
                        "id": "synthetic.observed.fact",
                        "label": "synthetic_weighted_error",
                        "value": 0.125,
                        "tolerance": 0.005,
                        "source_ref": "source_page_1",
                    }
                ],
            }
        ],
        "warnings": [],
    }


def weighted_computation_only_bundle(*, claimed: float = 0.2) -> dict[str, Any]:
    bundle = weighted_bundle(claimed=claimed)
    bundle["concepts"][0]["numeric_observations"] = []
    return bundle


def method_bundle() -> dict[str, Any]:
    methods = [
        ("synthetic.total_error", "synthetic_total_error", "total_error", {"misclassified_weight": 0.125}, 0.125),
        ("synthetic.amount_of_say", "synthetic_amount_of_say", "amount_of_say", {"total_error": 0.125}, 0.972955),
        ("synthetic.softmax", "synthetic_softmax", "softmax", {"values": [1.0, 2.0, 3.0], "index": 2}, 0.665241),
        ("synthetic.cross_entropy", "synthetic_cross_entropy", "cross_entropy", {"probability": 0.5}, 0.693147),
        (
            "synthetic.forward_pass",
            "synthetic_forward_pass",
            "forward_pass",
            {"inputs": {"x1": 2.0}, "weights": {"x1": 0.5}, "bias": 0.25, "activation": "linear"},
            1.25,
        ),
    ]
    return {
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": "Synthetic Concept",
                "source_ref": "source_page_1",
                "computation_records": [
                    {
                        "id": fact_id,
                        "label": label,
                        "method": method,
                        "inputs": inputs,
                        "claimed_value": value,
                    }
                    for fact_id, label, method, inputs, value in methods
                ],
            }
        ],
    }


def fixture_spec(*, value: float) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_fixture",
        "lecture_id": "synthetic_fixture",
        "title": "Synthetic Fixture",
        "source_quality": "synthetic",
        "expected_topics": ["Synthetic Concept"],
        "ground_truth_numerics": [{"label": "synthetic_stump_choice_score", "value": value, "tol": 0.01}],
        "min_mock_questions": 1,
        "tier_targets": {"premium": 0.9, "local": 0.8},
    }


def candidate_markdown(*, value: float) -> str:
    return "\n".join(
        [
            "# Synthetic Fixture",
            "Synthetic Concept",
            f"synthetic_stump_choice_score: {value}",
            "## Worked Answer",
            "Solution: substitute the synthetic counts and finish with the numeric target.",
            "## Mock Question 1: Which synthetic concept is checked?",
            "Answer: Synthetic Concept.",
        ]
    )


def test_empty_and_malformed_behavior() -> None:
    for item in (None, 7, 1.5, [], object()):
        result = run_quality_safety_fact_sheet_producer(item)
        check(f"never raises {type(item).__name__}", result["kind"] == "quality_safety_fact_sheet_producer_result")
        check(f"missing/malformed skipped {type(item).__name__}", result["status"] in {"skipped", "failed"})
        assert_closed_warnings(f"missing/malformed {type(item).__name__}", result)
        assert_summary_shape(f"missing/malformed {type(item).__name__}", result)
    malformed = normalize_quality_safety_extraction_bundle({"concepts": "not-a-list"})
    check("malformed extraction bundle degraded", "malformed_extraction_bundle_degraded" in malformed["warnings"])


def test_bundle_normalization() -> None:
    normalized = normalize_quality_safety_extraction_bundle(weighted_bundle())
    check("valid bundle kind", normalized["kind"] == "quality_safety_extraction_bundle")
    check("valid bundle warnings clean", normalized["warnings"] == [], str(normalized["warnings"]))
    check("valid bundle concept preserved", normalized["concepts"][0]["concept"] == "Synthetic Concept")
    check("valid bundle deterministic", serialized(normalized) == serialized(normalize_quality_safety_extraction_bundle(weighted_bundle())))

    hostile = weighted_bundle()
    hostile["lecture_id"] = HOSTILE_CANARIES[0]
    hostile["source_quality"] = "private_source_quality"
    hostile["concepts"][0]["source_ref"] = HOSTILE_CANARIES[1]
    hostile["concepts"][0]["concept"] = HOSTILE_CANARIES[2]
    degraded = normalize_quality_safety_extraction_bundle(hostile)
    check("invalid lecture_id warning", "invalid_lecture_id" in degraded["warnings"], str(degraded["warnings"]))
    check("invalid source_quality warning", "invalid_source_quality" in degraded["warnings"], str(degraded["warnings"]))
    check("hostile concept dropped", degraded["concepts"] == [], serialized(degraded))
    assert_no_canary("hostile normalization", degraded)


def test_computation_records() -> None:
    result = run_quality_safety_fact_sheet_producer(weighted_bundle())
    sheet = result["fact_sheet"]
    fact = sheet["concepts"][0]["facts"][0]
    check("weighted_gini fact produced", fact["id"] == "synthetic.weighted_gini.fact")
    check("weighted_gini method preserved", fact["computation"]["method"] == "weighted_gini")
    check("weighted_gini inputs preserved", fact["computation"]["inputs"]["groups"][1]["no"] == 4)
    check("weighted_gini tolerance preserved", fact["computation"]["tolerance"] == 0.01)
    check("computed fact starts unverified", fact["verification_status"] == "unverified")
    check("computed fact has claimed value", fact["value"] == 0.2 and fact["computation"]["result"] == 0.2)

    methods = run_quality_safety_fact_sheet_producer(method_bundle())
    produced_methods = [fact["computation"]["method"] for fact in methods["fact_sheet"]["concepts"][0]["facts"]]
    for method in ("total_error", "amount_of_say", "softmax", "cross_entropy", "forward_pass"):
        check(f"{method} preserved", method in produced_methods, str(produced_methods))

    unknown = weighted_bundle()
    unknown["concepts"][0]["computation_records"][0]["method"] = "new_magic"
    unknown_result = run_quality_safety_fact_sheet_producer(unknown)
    unknown_fact = unknown_result["fact_sheet"]["concepts"][0]["facts"][0]
    check("unknown method warning", "invalid_computation_method" in unknown_result["warnings"], str(unknown_result["warnings"]))
    check("unknown method becomes unknown", unknown_fact["computation"]["method"] == "unknown")

    invalid = weighted_bundle()
    invalid["concepts"][0]["computation_records"][0]["inputs"] = {"groups": [HOSTILE_CANARIES[3]]}
    invalid_result = run_quality_safety_fact_sheet_producer(invalid)
    check("invalid inputs warning", "invalid_computation_inputs" in invalid_result["warnings"], str(invalid_result["warnings"]))
    check("invalid computation dropped", invalid_result["summary"]["produced_fact_count"] == 1, serialized(invalid_result))
    assert_no_canary("invalid computation", invalid_result)


def test_numeric_observations() -> None:
    result = run_quality_safety_fact_sheet_producer(weighted_bundle())
    fact = result["fact_sheet"]["concepts"][0]["facts"][1]
    check("numeric observation fact produced", fact["id"] == "synthetic.observed.fact")
    check("numeric observation unverified", fact["verification_status"] == "unverified")
    check("numeric observation no computation", fact["computation"] is None)
    check("numeric value does not verify", result["fact_sheet"]["summary"]["verified_fact_count"] == 0)

    invalid = weighted_bundle()
    invalid["concepts"][0]["numeric_observations"][0]["value"] = math.inf
    invalid_result = run_quality_safety_fact_sheet_producer(invalid)
    check("non-finite observation warning", "invalid_numeric_value" in invalid_result["warnings"])
    check("non-finite observation dropped", invalid_result["summary"]["numeric_observation_count"] == 0)


def test_fact_sheet_integration() -> None:
    result = run_quality_safety_fact_sheet_producer(weighted_bundle())
    normalized = normalize_quality_safety_fact_sheet(result["fact_sheet"])
    check("produced fact_sheet validates", normalized["kind"] == "quality_safety_fact_sheet")
    assert_summary_shape("producer", result)
    check("deterministic producer serialization", serialized(result) == serialized(run_quality_safety_fact_sheet_producer(weighted_bundle())))
    built = build_quality_safety_fact_sheet_from_extraction(weighted_bundle())
    check("build helper returns fact sheet", built["kind"] == "quality_safety_fact_sheet")
    check("extract computation helper", len(extract_quality_safety_computation_records(weighted_bundle())) == 1)
    check("extract observation helper", len(extract_quality_safety_numeric_observations(weighted_bundle())) == 1)


def test_recompute_integration() -> None:
    clean = run_quality_safety_fact_sheet_producer(weighted_computation_only_bundle(claimed=0.2))["fact_sheet"]
    clean_verified = verify_quality_safety_fact_sheet(clean)
    clean_report = clean_verified["report"]
    check("produced weighted_gini verifies", clean_report["status"] == "passed", serialized(clean_report))
    check("verified via weighted_gini", clean_report["checks"][0]["check_id"] == "weighted_gini")

    wrong = run_quality_safety_fact_sheet_producer(weighted_computation_only_bundle(claimed=0.5))["fact_sheet"]
    wrong_verified = verify_quality_safety_fact_sheet(wrong)
    wrong_report = wrong_verified["report"]
    check("produced weighted_gini fails", wrong_report["status"] == "failed", serialized(wrong_report))
    check("wrong weighted_gini blocks", wrong_report["blocking_failures"][0]["check_id"] == "weighted_gini")


def test_canonical_fallback_unused() -> None:
    sheet = run_quality_safety_fact_sheet_producer(weighted_computation_only_bundle(claimed=0.2))["fact_sheet"]
    verified = verify_quality_safety_fact_sheet(sheet)
    canonical = {
        "version": 1,
        "kind": "quality_safety_canonical_fixture",
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "facts": [{"id": "canon_1", "label": "synthetic_stump_choice_score", "value": 0.99, "tol": 0.01, "type": "numeric"}],
    }
    canonical_report = build_quality_safety_canonical_match_report(
        verified["fact_sheet"],
        canonical,
        recompute_report=verified["report"],
    )
    check("canonical skipped when recompute verified", canonical_report["summary"]["skipped_by_recompute_count"] >= 1)
    check("producer no canonical provenance", "canonical_fixture" not in serialized(sheet))

    wrong = run_quality_safety_fact_sheet_producer(weighted_computation_only_bundle(claimed=0.5))["fact_sheet"]
    wrong_verified = verify_quality_safety_fact_sheet(wrong)
    wrong_canonical = build_quality_safety_canonical_match_report(
        wrong_verified["fact_sheet"],
        canonical,
        recompute_report=wrong_verified["report"],
    )
    check("canonical skipped when recompute failed", wrong_canonical["summary"]["skipped_by_recompute_count"] >= 1)


def test_unified_qa_integration() -> None:
    clean_sheet = run_quality_safety_fact_sheet_producer(weighted_computation_only_bundle(claimed=0.2))["fact_sheet"]
    clean = run_quality_safety_unified_floor(
        candidate_markdown=candidate_markdown(value=0.2),
        fixture_spec=fixture_spec(value=0.2),
        fact_sheet=clean_sheet,
    )
    check("clean unified passed", clean["status"] == "passed", serialized(clean))
    check("clean shippable", clean["shippable"] is True)
    check("clean safety floor green", clean["safety_floor_green"] is True)

    wrong_sheet = run_quality_safety_fact_sheet_producer(weighted_computation_only_bundle(claimed=0.5))["fact_sheet"]
    wrong = run_quality_safety_unified_floor(
        candidate_markdown=candidate_markdown(value=0.5),
        fixture_spec=fixture_spec(value=0.5),
        fact_sheet=wrong_sheet,
    )
    check("wrong unified failed", wrong["status"] == "failed", serialized(wrong))
    check("wrong not shippable", wrong["shippable"] is False)
    check("wrong safety floor red", wrong["safety_floor_green"] is False)
    check("wrong recompute blocker", any(item["component"] == "recompute" and item["check_id"] == "weighted_gini" for item in wrong["blocking_failures"]))
    check("wrong no leak blocker required", wrong["summary"]["leak_blocking_failure_count"] == 0, serialized(wrong))
    check("wrong no layer1 numeric contradiction required", wrong["summary"]["layer1_blocking_failure_count"] == 0, serialized(wrong))


def test_bounds_max_items() -> None:
    bundle = {
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": f"Synthetic Concept {index}",
                "source_ref": "source_page_1",
                "computation_records": [
                    {
                        "id": f"synthetic.fact.{index}",
                        "label": f"synthetic_label_{index}",
                        "method": "total_error",
                        "inputs": {"misclassified_weight": 0.1},
                        "claimed_value": 0.1,
                    }
                    for index in range(5)
                ],
                "numeric_observations": [
                    {"id": f"synthetic.obs.{index}", "label": f"synthetic_obs_{index}", "value": 0.1}
                    for index in range(5)
                ],
            }
            for index in range(5)
        ],
    }
    result = run_quality_safety_fact_sheet_producer(bundle, max_items=2)
    check("max_items status partial", result["status"] == "partial", serialized(result))
    check("max_items warning", "max_items_reached" in result["warnings"], str(result["warnings"]))
    check("concepts capped", result["summary"]["concept_count"] <= 2, str(result["summary"]))
    for concept in result["fact_sheet"]["concepts"]:
        check("facts capped per concept", len(concept["facts"]) <= 2, serialized(concept))


def test_no_leak_sweep() -> None:
    bundle = weighted_bundle()
    bundle["lecture_id"] = HOSTILE_CANARIES[0]
    bundle["concepts"][0]["concept"] = HOSTILE_CANARIES[1]
    bundle["concepts"][0]["source_ref"] = HOSTILE_CANARIES[2]
    bundle["concepts"][0]["computation_records"][0]["label"] = HOSTILE_CANARIES[3]
    bundle["concepts"][0]["computation_records"][0]["inputs"]["payload"] = HOSTILE_CANARIES[4]
    bundle["concepts"][0]["computation_records"].append(
        {
            "id": HOSTILE_CANARIES[5],
            "label": HOSTILE_CANARIES[6],
            "method": "total_error",
            "inputs": {HOSTILE_CANARIES[7]: 1},
            "claimed_value": 1,
        }
    )
    bundle["concepts"][0]["numeric_observations"][0]["label"] = HOSTILE_CANARIES[8]
    bundle["metadata"] = {"uploaded_spec": HOSTILE_CANARIES[9], "evidence": HOSTILE_CANARIES[10]}
    result = run_quality_safety_fact_sheet_producer(bundle)
    assert_no_canary("producer no-leak sweep", result)
    assert_no_canary("producer fact_sheet no-leak sweep", result["fact_sheet"])


def test_import_hygiene() -> None:
    source = (REPO / "pipeline" / "quality_safety_fact_sheet_producer.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    for item in imports:
        for forbidden in FORBIDDEN_IMPORT_PARTS:
            check(f"import {item!r} avoids {forbidden!r}", forbidden not in item.lower())
    check("imports allowed-only", set(imports) <= ALLOWED_IMPORTS, str(imports))


def run() -> int:
    test_empty_and_malformed_behavior()
    test_bundle_normalization()
    test_computation_records()
    test_numeric_observations()
    test_fact_sheet_integration()
    test_recompute_integration()
    test_canonical_fallback_unused()
    test_unified_qa_integration()
    test_bounds_max_items()
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_fact_sheet_producer: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
