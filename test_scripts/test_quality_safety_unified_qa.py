#!/usr/bin/env python3
"""Tests for Slice 114 quality-safety unified QA report."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO / "test_scripts" / "fixtures" / "quality_safety"
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_canonical_matcher import build_quality_safety_canonical_match_report  # noqa: E402
from pipeline.quality_safety_eval_harness import (  # noqa: E402
    load_quality_safety_fixture_spec,
    run_quality_safety_layer1_checks,
)
from pipeline.quality_safety_leak_scanner import build_quality_safety_leak_report  # noqa: E402
from pipeline.quality_safety_recompute_verifier import build_quality_safety_recompute_report  # noqa: E402
from pipeline.quality_safety_unified_qa import (  # noqa: E402
    aggregate_quality_safety_reports,
    build_quality_safety_deterministic_axes,
    build_quality_safety_unified_qa_report,
    run_quality_safety_unified_floor,
)

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/private/unified-source.pdf",
    "https://private.invalid/uploaded-quality-spec",
    "Authorization: Bearer sk_qualitysafetyunified123456",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_UNIFIED_MARKER",
    "TABLE_TEXT_PRIVATE_UNIFIED_MARKER",
    "CAPTION_PRIVATE_UNIFIED_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_UNIFIED_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MARKER",
)
LEAK_PATTERNS = (
    re.compile(r"/home/private"),
    re.compile(r"https?://"),
    re.compile(r"Authorization", re.IGNORECASE),
    re.compile(r"Bearer", re.IGNORECASE),
    re.compile(r"sk_qualitysafetyunified"),
    re.compile(r"data:image", re.IGNORECASE),
    re.compile(r"base64", re.IGNORECASE),
    re.compile(r"OCR_PRIVATE_UNIFIED_MARKER"),
    re.compile(r"TABLE_TEXT_PRIVATE_UNIFIED_MARKER"),
    re.compile(r"CAPTION_PRIVATE_UNIFIED_MARKER"),
    re.compile(r"PROVIDER_PAYLOAD_PRIVATE_UNIFIED_MARKER"),
    re.compile(r"UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME"),
    re.compile(r"EVIDENCE_QUOTE_PRIVATE_MARKER"),
)
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "re",
    "typing",
    "pipeline.quality_safety_eval_harness",
    "pipeline.quality_safety_fact_sheet",
    "pipeline.quality_safety_recompute_verifier",
    "pipeline.quality_safety_canonical_matcher",
    "pipeline.quality_safety_leak_scanner",
}
FORBIDDEN_IMPORT_PARTS = (
    "fastapi",
    "frontend",
    "provider",
    "model_client",
    "openai",
    "anthropic",
    "gemini",
    "mistral",
    "chandra",
    "render",
    "ocr",
    "tesseract",
    "fitz",
    "job_manager",
    "server",
    "api.",
    "requests",
    "httpx",
    "subprocess",
    "socket",
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


def serialized(node: Any) -> str:
    return json.dumps(node, sort_keys=True)


def assert_no_leak(name: str, node: Any) -> None:
    blob = serialized(node)
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


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def fact_sheet_from_fixture(spec: dict[str, Any], *, omit_computation: bool = False, mismatch: bool = False) -> dict[str, Any]:
    facts = []
    for index, target in enumerate(spec.get("ground_truth_numerics", []), start=1):
        value = float(target["value"])
        if mismatch and index == 1:
            value += 0.25
        fact = {
            "id": f"fact_{index:04d}",
            "concept": "Synthetic Concept",
            "label": target["label"],
            "value": value,
            "type": "numeric",
            "provenance": "computed",
            "verification_status": "verified",
            "confidence": "high",
        }
        if not omit_computation:
            fact["computation"] = {
                "method": "total_error",
                "inputs": {"misclassified_weight": float(target["value"])},
                "tolerance": float(target.get("tol", 0.01)),
            }
        facts.append(fact)
    return {
        "version": 1,
        "kind": "quality_safety_fact_sheet",
        "lecture_id": spec.get("lecture_id", "synthetic_fixture"),
        "source_quality": "synthetic",
        "concepts": [{"concept": "Synthetic Concept", "facts": facts}],
    }


def canonical_from_fixture(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_canonical_fixture",
        "lecture_id": spec.get("lecture_id", "synthetic_fixture"),
        "source_quality": "synthetic",
        "facts": [
            {
                "id": f"canon_{index:04d}",
                "label": target["label"],
                "value": float(target["value"]),
                "tol": float(target.get("tol", 0.01)),
                "type": "numeric",
            }
            for index, target in enumerate(spec.get("ground_truth_numerics", []), start=1)
        ],
    }


def candidate_from_fixture(spec: dict[str, Any], *, leaked: bool = False, mismatch: bool = False, low_mock: bool = False) -> str:
    topics = spec.get("expected_topics", [])
    lines = [
        f"# {spec.get('title', 'Synthetic Candidate')}",
        " ".join(str(topic) for topic in topics),
    ]
    for index, target in enumerate(spec.get("ground_truth_numerics", []), start=1):
        value = float(target["value"])
        if mismatch and index == 1:
            value += 0.25
        lines.append(f"{target['label']}: {value}")
    lines.extend(
        [
            "## Worked Answer",
            "Solution: substitute the synthetic values and finish with the listed numeric targets.",
        ]
    )
    count = 1 if low_mock else int(spec.get("min_mock_questions", 0))
    for index in range(1, count + 1):
        prefix = "Mock" if index % 2 else "Practice"
        lines.append(f"## {prefix} Question {index}: Which synthetic topic is checked?")
        lines.append("Answer: the listed synthetic topic.")
    if leaked:
        lines.append("Wait, fact_0001 seems uncertain = ?")
        lines.append("Final answer:")
    return "\n".join(lines)


def assert_report_shape(name: str, report: dict[str, Any]) -> None:
    check(f"{name}: kind", report.get("kind") == "quality_safety_unified_qa")
    check(f"{name}: version", report.get("version") == 1)
    check(f"{name}: status closed", report.get("status") in {"passed", "warning", "failed", "skipped", "partial"})
    check(f"{name}: axes keys", set(report.get("deterministic_axes_0_5", {})) == {"accuracy", "coverage", "solved_problem", "clarity"})
    check(f"{name}: no overall_10", "overall_10" not in serialized(report))
    assert_no_leak(name, report)


def test_empty_and_malformed() -> None:
    empty = build_quality_safety_unified_qa_report()
    check("missing all inputs skipped", empty["status"] == "skipped")
    check("missing all inputs not shippable", empty["shippable"] is False)
    check("missing all inputs warning", "component_missing" in empty["warnings"])
    malformed = aggregate_quality_safety_reports(layer1_report={"kind": "wrong", "warnings": [HOSTILE_CANARIES[0]]})
    check("malformed child degrades", malformed["status"] in {"warning", "skipped"})
    check("malformed child warning closed", "component_malformed" in malformed["warnings"])
    assert_report_shape("malformed child", malformed)
    for value in (None, 1, 1.2, [], object()):
        try:
            report = build_quality_safety_unified_qa_report(candidate_markdown=value, fixture_spec=value, fact_sheet=value)
            ok = isinstance(report, dict)
        except Exception:
            ok = False
        check(f"never raises for {type(value).__name__}", ok)


def test_all_green_and_runner() -> None:
    spec = fixture("clean_neural_networks_synthetic.json")
    report = run_quality_safety_unified_floor(
        candidate_markdown=candidate_from_fixture(spec),
        fixture_spec=spec,
        fact_sheet=fact_sheet_from_fixture(spec),
    )
    check("all-green status passed", report["status"] == "passed")
    check("all-green shippable", report["shippable"] is True)
    check("all-green safety floor", report["safety_floor_green"] is True)
    check("all-green no blockers", report["summary"]["blocking_failure_count"] == 0)
    check("all-green accuracy", report["deterministic_axes_0_5"]["accuracy"] == 5)
    check("all-green coverage", report["deterministic_axes_0_5"]["coverage"] == 5)
    check("all-green solved", report["deterministic_axes_0_5"]["solved_problem"] == 5)
    check("all-green clarity", report["deterministic_axes_0_5"]["clarity"] == 5)
    assert_report_shape("all-green", report)


def test_layer1_blocking() -> None:
    spec = fixture("clean_neural_networks_synthetic.json")
    candidate = candidate_from_fixture(spec, leaked=True)
    layer1 = run_quality_safety_layer1_checks(candidate, load_quality_safety_fixture_spec(spec))
    report = aggregate_quality_safety_reports(
        layer1_report=layer1,
        recompute_report=build_quality_safety_recompute_report(fact_sheet_from_fixture(spec)),
        leak_report=build_quality_safety_leak_report(candidate),
    )
    check("layer1 blocking not shippable", report["shippable"] is False)
    failures = report["blocking_failures"]
    check("layer1 failure component", any(item["component"] == "layer1" for item in failures))
    check("layer1 closed id", any(item["check_id"] in {"leaked_reasoning", "worked_answer_completeness"} for item in failures))
    assert_no_leak("layer1 blocking", report)


def test_recompute_blocking() -> None:
    spec = fixture("clean_neural_networks_synthetic.json")
    report = run_quality_safety_unified_floor(
        candidate_markdown=candidate_from_fixture(spec),
        fixture_spec=spec,
        fact_sheet=fact_sheet_from_fixture(spec, mismatch=True),
        canonical_fixture=canonical_from_fixture(spec),
    )
    check("recompute mismatch fails", report["shippable"] is False)
    check("accuracy zero on recompute mismatch", report["deterministic_axes_0_5"]["accuracy"] == 0)
    check("recompute failure present", any(item["component"] == "recompute" for item in report["blocking_failures"]))
    check("canonical does not override recompute failure", report["summary"]["failed_recompute_count"] > 0)
    assert_no_leak("recompute blocking", report)


def test_canonical_fallback_pass_and_fail() -> None:
    spec = fixture("clean_neural_networks_synthetic.json")
    clean = run_quality_safety_unified_floor(
        candidate_markdown=candidate_from_fixture(spec),
        fixture_spec=spec,
        fact_sheet=fact_sheet_from_fixture(spec, omit_computation=True),
        canonical_fixture=canonical_from_fixture(spec),
    )
    check("canonical fallback pass shippable", clean["shippable"] is True)
    check("canonical verified count", clean["summary"]["verified_canonical_count"] > 0)
    check("canonical accuracy 5", clean["deterministic_axes_0_5"]["accuracy"] == 5)
    bad = run_quality_safety_unified_floor(
        candidate_markdown=candidate_from_fixture(spec),
        fixture_spec=spec,
        fact_sheet=fact_sheet_from_fixture(spec, omit_computation=True, mismatch=True),
        canonical_fixture=canonical_from_fixture(spec),
    )
    check("canonical fallback mismatch not shippable", bad["shippable"] is False)
    check("canonical failure component", any(item["component"] == "canonical" for item in bad["blocking_failures"]))
    assert_no_leak("canonical fallback", bad)


def test_leak_blocking_and_warning_only() -> None:
    spec = fixture("clean_neural_networks_synthetic.json")
    sheet = fact_sheet_from_fixture(spec)
    recompute = build_quality_safety_recompute_report(sheet)
    leak = build_quality_safety_leak_report("fact_0001 seems uncertain = ?", fact_sheet=sheet, recompute_report=recompute)
    report = aggregate_quality_safety_reports(
        layer1_report=run_quality_safety_layer1_checks(candidate_from_fixture(spec), load_quality_safety_fixture_spec(spec)),
        recompute_report=recompute,
        leak_report=leak,
    )
    check("leak blocking not shippable", report["shippable"] is False)
    check("clarity zero", report["deterministic_axes_0_5"]["clarity"] == 0)
    check(
        "leak verification preserved",
        any(item["verification_status"] == "verified_recompute" for item in report["blocking_failures"]),
    )
    warning_layer1 = run_quality_safety_layer1_checks(
        candidate_from_fixture(spec, low_mock=True),
        load_quality_safety_fixture_spec(spec),
    )
    warning_report = aggregate_quality_safety_reports(
        layer1_report=warning_layer1,
        recompute_report=recompute,
        leak_report=build_quality_safety_leak_report(candidate_from_fixture(spec), fact_sheet=sheet, recompute_report=recompute),
    )
    check("warning-only status", warning_report["status"] == "warning")
    check("warning-only shippable", warning_report["shippable"] is True)
    check("mock warning token", "mock_question_warning" in warning_report["warnings"])
    assert_no_leak("leak warning", warning_report)


def test_axes_thresholds() -> None:
    def layer1(expected: int, observed: int) -> dict[str, Any]:
        return {
            "version": 1,
            "kind": "quality_safety_eval_layer1",
            "status": "passed",
            "shippable": True,
            "summary": {
                "blocking_failure_count": 0,
                "expected_topic_count": expected,
                "observed_topic_count": observed,
            },
            "checks": [{"id": "worked_answer_completeness", "status": "passed", "blocking": False}],
            "blocking_failures": [],
            "warnings": [],
        }

    expected_scores = [(20, 19, 5), (20, 17, 4), (20, 14, 3), (20, 10, 2), (20, 9, 0)]
    for expected, observed, score in expected_scores:
        report = aggregate_quality_safety_reports(
            layer1_report=layer1(expected, observed),
            recompute_report={"version": 1, "kind": "quality_safety_recompute_report", "status": "passed", "summary": {"verified_fact_count": 1}, "checks": [], "blocking_failures": [], "warnings": []},
            leak_report={"version": 1, "kind": "quality_safety_leak_report", "status": "passed", "summary": {}, "leaks": [], "blocking_failures": [], "warnings": []},
        )
        check(f"coverage axis {observed}/{expected}", report["deterministic_axes_0_5"]["coverage"] == score)
    missing_numeric = aggregate_quality_safety_reports(layer1_report=layer1(1, 1), leak_report=None, recompute_report=None)
    axes = build_quality_safety_deterministic_axes(missing_numeric)
    check("numeric missing accuracy 2", axes["accuracy"] == 2)
    check("no overall_10 produced", "overall_10" not in serialized(missing_numeric))


def test_integration_recompute_canonical_leak_context() -> None:
    spec = fixture("clean_neural_networks_synthetic.json")
    sheet = fact_sheet_from_fixture(spec, omit_computation=True)
    sheet["concepts"][0]["facts"][0]["computation"] = {
        "method": "total_error",
        "inputs": {"misclassified_weight": float(spec["ground_truth_numerics"][0]["value"])},
    }
    recompute = build_quality_safety_recompute_report(sheet)
    canonical = build_quality_safety_canonical_match_report(sheet, canonical_from_fixture(spec), recompute_report=recompute)
    leak = build_quality_safety_leak_report("fact_0001 seems uncertain = ?\nfact_0002 seems uncertain = ?", fact_sheet=sheet, recompute_report=recompute, canonical_report=canonical)
    report = aggregate_quality_safety_reports(
        layer1_report=run_quality_safety_layer1_checks(candidate_from_fixture(spec), load_quality_safety_fixture_spec(spec)),
        recompute_report=recompute,
        canonical_report=canonical,
        leak_report=leak,
    )
    statuses = {item["verification_status"] for item in report["blocking_failures"] if item["component"] == "leak"}
    check("integration recompute-first context", "verified_recompute" in statuses)
    check("integration canonical-second context", "verified_canonical" in statuses)
    check("integration failure due leaks", report["shippable"] is False)


def test_seed_fixture_gate() -> None:
    for name in ("clean_neural_networks_synthetic.json", "ambiguous_ensemble_synthetic.json"):
        spec = fixture(name)
        report = run_quality_safety_unified_floor(
            candidate_markdown=candidate_from_fixture(spec),
            fixture_spec=spec,
            fact_sheet=fact_sheet_from_fixture(spec),
        )
        check(f"{name} green passes", report["safety_floor_green"] is True)
        assert_no_leak(f"{name} green", report)
    ambiguous = fixture("ambiguous_ensemble_synthetic.json")
    bad = run_quality_safety_unified_floor(
        candidate_markdown=candidate_from_fixture(ambiguous, leaked=True, mismatch=True),
        fixture_spec=ambiguous,
        fact_sheet=fact_sheet_from_fixture(ambiguous, mismatch=True),
    )
    check("ambiguous leaked/mismatched fails", bad["safety_floor_green"] is False and bad["shippable"] is False)
    assert_no_leak("ambiguous bad", bad)


def test_no_leak_sweep() -> None:
    hostile_child = {
        "version": 1,
        "kind": "quality_safety_eval_layer1",
        "status": "failed",
        "shippable": False,
        "summary": {"blocking_failure_count": 1, "expected_topic_count": 1, "observed_topic_count": 0},
        "checks": [{"id": HOSTILE_CANARIES[0], "status": "failed", "blocking": True, "raw": HOSTILE_CANARIES[1]}],
        "blocking_failures": [HOSTILE_CANARIES[0]],
        "warnings": [HOSTILE_CANARIES[2], "expected_topic_missing"],
    }
    report = build_quality_safety_unified_qa_report(
        candidate_markdown="\n".join(HOSTILE_CANARIES),
        fixture_spec={"lecture_id": HOSTILE_CANARIES[0], "expected_topics": HOSTILE_CANARIES},
        fact_sheet={"concepts": [{"concept": HOSTILE_CANARIES[3], "facts": [{"id": HOSTILE_CANARIES[4], "label": HOSTILE_CANARIES[5]}]}]},
        layer1_report=hostile_child,
        recompute_report={"kind": "quality_safety_recompute_report", "status": "failed", "summary": {}, "checks": [{"fact_id": HOSTILE_CANARIES[6], "check_id": HOSTILE_CANARIES[7], "status": "failed"}], "blocking_failures": [], "warnings": [HOSTILE_CANARIES[8]]},
        leak_report={"kind": "quality_safety_leak_report", "status": "failed", "summary": {}, "leaks": [{"severity": "blocking", "fact_ids": [HOSTILE_CANARIES[9]], "verification_status": HOSTILE_CANARIES[0]}], "blocking_failures": [], "warnings": [HOSTILE_CANARIES[1]]},
    )
    assert_no_leak("hostile unified", report)
    check("hostile only closed warnings", all(token in {"component_malformed", "layer1_warning", "coverage_warning", "leak_warning"} for token in report["warnings"]))
    check("hostile check id sanitized", all(item["check_id"] in {"unknown_check", "quality_safety_leak_scan"} for item in report["blocking_failures"]))


def test_import_hygiene() -> None:
    source = (REPO / "pipeline" / "quality_safety_unified_qa.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    bad = [name for name in imports if any(part in name.lower() for part in FORBIDDEN_IMPORT_PARTS)]
    check("no forbidden imports", bad == [], str(bad))
    check("imports allowed-only", set(imports).issubset(ALLOWED_IMPORT_ROOTS), str(sorted(set(imports) - ALLOWED_IMPORT_ROOTS)))


def main() -> int:
    test_empty_and_malformed()
    test_all_green_and_runner()
    test_layer1_blocking()
    test_recompute_blocking()
    test_canonical_fallback_pass_and_fail()
    test_leak_blocking_and_warning_only()
    test_axes_thresholds()
    test_integration_recompute_canonical_leak_context()
    test_seed_fixture_gate()
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_unified_qa: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
