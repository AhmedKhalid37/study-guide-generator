#!/usr/bin/env python3
"""Tests for Slice 111 Quality Safety recompute verifier v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. All fixture ids,
labels, values, and canaries are synthetic.
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

from pipeline.quality_safety_fact_sheet import (  # noqa: E402
    normalize_quality_safety_fact_sheet,
)
from pipeline.quality_safety_recompute_verifier import (  # noqa: E402
    build_quality_safety_recompute_report,
    recompute_quality_safety_fact,
    verify_quality_safety_fact_sheet,
    build_golden_target_recompute_proof,
    summarize_golden_target_recompute_proof,
    golden_label_recompute_plan,
    GOLDEN_RECOMPUTE_STATUSES,
    GOLDEN_VALUE_KINDS,
    GOLDEN_CONFIDENCE_LEVELS,
    GOLDEN_CANDIDATE_STATUSES,
    GOLDEN_PROOF_WARNING_ORDER,
    build_generation_ready_numeric_records,
    VERIFIED_VALUE_INSTRUCTION_TOKEN,
    GENERATION_READY_KIND,
)

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/private/source-deck.pdf",
    "C:\\private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_recompute1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_RECOMPUTE_MARKER",
    "TABLE_TEXT_PRIVATE_RECOMPUTE_MARKER",
    "CAPTION_PRIVATE_RECOMPUTE_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_RECOMPUTE_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MARKER",
    "source text private marker",
    "E=mc^2_private_formula_marker",
)
FORBIDDEN_IMPORT_PARTS = (
    "fastapi",
    "frontend",
    "provider",
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
ALLOWED_IMPORTS = {"__future__", "math", "typing", "pipeline.quality_safety_fact_sheet"}
REPORT_WARNINGS = {
    "fact_sheet_missing",
    "malformed_fact_sheet_degraded",
    "non_numeric_fact_not_applicable",
    "computation_missing",
    "unsupported_computation_method",
    "malformed_computation_inputs",
    "invalid_numeric_value",
    "invalid_tolerance",
    "recomputed_mismatch",
    "max_items_reached",
}
CHECK_IDS = {
    "weighted_gini",
    "total_error",
    "amount_of_say",
    "softmax",
    "cross_entropy",
    "forward_pass",
    "numeric_fact_not_recomputable",
    "non_numeric_fact_not_applicable",
}
CHECK_STATUSES = {"passed", "warning", "failed", "not_applicable", "unknown"}
REPORT_STATUSES = {"passed", "warning", "failed", "skipped", "partial"}


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
    markers = [
        "/home/private",
        "C:\\private",
        "https://",
        "Authorization",
        "Bearer",
        "sk_recompute",
        "data:image",
        "base64",
        "OCR_PRIVATE",
        "TABLE_TEXT_PRIVATE",
        "CAPTION_PRIVATE",
        "PROVIDER_PAYLOAD_PRIVATE",
        "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
        "EVIDENCE_QUOTE_PRIVATE_MARKER",
        "private_formula_marker",
        "source text private marker",
    ]
    found = [marker for marker in markers if marker in blob]
    found += [canary for canary in HOSTILE_CANARIES if canary in blob]
    check(f"{name}: no hostile canary", not found, str(found))


def assert_report_shape(name: str, report: dict[str, Any]) -> None:
    check(f"{name}: kind", report.get("kind") == "quality_safety_recompute_report")
    check(f"{name}: version", report.get("version") == 1)
    check(f"{name}: blocking true", report.get("blocking") is True)
    check(f"{name}: status closed", report.get("status") in REPORT_STATUSES, str(report.get("status")))
    summary = report.get("summary", {})
    check(
        f"{name}: summary non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()),
        str(summary),
    )
    for entry in report.get("checks", []):
        check(f"{name}: check id closed", entry.get("check_id") in CHECK_IDS, str(entry.get("check_id")))
        check(f"{name}: check status closed", entry.get("status") in CHECK_STATUSES, str(entry.get("status")))
        check(
            f"{name}: check warnings closed",
            all(w in REPORT_WARNINGS for w in entry.get("warnings", [])),
            str(entry.get("warnings")),
        )
    check(
        f"{name}: report warnings closed",
        all(w in REPORT_WARNINGS for w in report.get("warnings", [])),
        str(report.get("warnings")),
    )


def numeric_fact(
    *,
    fact_id: str = "synthetic.fact",
    label: str = "synthetic_label",
    value: Any,
    method: str,
    inputs: dict[str, Any],
    provenance: str = "computed",
    verification_status: str = "verified",
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "concept": "Synthetic Concept",
        "label": label,
        "value": value,
        "type": "numeric",
        "provenance": provenance,
        "verification_status": verification_status,
        "confidence": "high",
        "source_ref": "source_page_1",
        "computation": {"method": method, "inputs": inputs, "result": value},
    }


def sheet_of(*facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": [{"concept": "Synthetic Concept", "facts": list(facts)}],
    }


def single_check(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks", [])
    return checks[0] if checks else {}


# ── 1. Empty / malformed behavior ───────────────────────────────────────────


def test_empty_and_malformed() -> None:
    missing = build_quality_safety_recompute_report(None)
    check("missing -> skipped", missing["status"] == "skipped")
    check("missing -> fact_sheet_missing", "fact_sheet_missing" in missing["warnings"])
    assert_report_shape("missing", missing)

    malformed = build_quality_safety_recompute_report(["not", "a", "dict"])
    check("malformed degrades", "malformed_fact_sheet_degraded" in malformed["warnings"], str(malformed["warnings"]))
    check("malformed never raises", malformed["kind"] == "quality_safety_recompute_report")
    assert_report_shape("malformed", malformed)

    empty_sheet = normalize_quality_safety_fact_sheet({"lecture_id": "synthetic_fixture", "concepts": []})
    empty_report = build_quality_safety_recompute_report(empty_sheet)
    check("empty sheet skipped", empty_report["status"] == "skipped")

    junk = recompute_quality_safety_fact("not-a-dict")
    check("garbage fact never raises", junk["status"] in CHECK_STATUSES)
    check("garbage fact not_applicable status", junk["verification_status"] == "not_applicable")


# ── 2. weighted_gini ────────────────────────────────────────────────────────


def test_weighted_gini() -> None:
    inputs = {"leafA": {"yes": 3, "no": 0}, "leafB": {"yes": 1, "no": 4}}
    ok = recompute_quality_safety_fact(numeric_fact(value=0.20, method="weighted_gini", inputs=inputs))
    check("weighted_gini recomputes ~0.20", abs((ok["recomputed_value"] or 0) - 0.20) < 1e-9, str(ok))
    check("weighted_gini passes", ok["status"] == "passed" and ok["verification_status"] == "verified")

    groups_shape = {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]}
    ok2 = recompute_quality_safety_fact(numeric_fact(value=0.20, method="weighted_gini", inputs=groups_shape))
    check("weighted_gini groups shape passes", ok2["status"] == "passed", str(ok2))

    mismatch = recompute_quality_safety_fact(numeric_fact(value=0.90, method="weighted_gini", inputs=inputs))
    check("weighted_gini mismatch fails", mismatch["status"] == "failed")
    check("weighted_gini mismatch blocks", mismatch["blocking"] is True)
    check("weighted_gini mismatch warns", "recomputed_mismatch" in mismatch["warnings"])

    malformed = recompute_quality_safety_fact(
        numeric_fact(value=0.20, method="weighted_gini", inputs={"leafA": {"yes": -1, "no": 0}})
    )
    check("weighted_gini malformed -> warning", malformed["status"] == "warning")
    check("weighted_gini malformed unverified", malformed["verification_status"] == "unverified")
    check("weighted_gini malformed not blocking", malformed["blocking"] is False)

    zero_total = recompute_quality_safety_fact(
        numeric_fact(value=0.20, method="weighted_gini", inputs={"leafA": {"yes": 0, "no": 0}})
    )
    check("weighted_gini zero-total degrades", zero_total["status"] == "warning" and zero_total["recomputed_value"] is None)


# ── 3. total_error ──────────────────────────────────────────────────────────


def test_total_error() -> None:
    direct = recompute_quality_safety_fact(
        numeric_fact(value=0.125, method="total_error", inputs={"misclassified_weight": 0.125})
    )
    check("total_error direct passes", direct["status"] == "passed", str(direct))

    listed = recompute_quality_safety_fact(
        numeric_fact(value=0.125, method="total_error", inputs={"misclassified_weights": [0.05, 0.075]})
    )
    check("total_error list passes", listed["status"] == "passed", str(listed))

    mismatch = recompute_quality_safety_fact(
        numeric_fact(value=0.40, method="total_error", inputs={"misclassified_weight": 0.125})
    )
    check("total_error mismatch fails blocking", mismatch["status"] == "failed" and mismatch["blocking"] is True)


# ── 4. amount_of_say ────────────────────────────────────────────────────────


def test_amount_of_say() -> None:
    ok = recompute_quality_safety_fact(
        numeric_fact(value=0.97, method="amount_of_say", inputs={"total_error": 0.125})
    )
    check("amount_of_say recomputes ~0.97", abs((ok["recomputed_value"] or 0) - 0.9730) < 0.001, str(ok))
    check("amount_of_say passes", ok["status"] == "passed")

    bad0 = recompute_quality_safety_fact(
        numeric_fact(value=0.97, method="amount_of_say", inputs={"total_error": 0.0})
    )
    check("amount_of_say error=0 degrades", bad0["status"] == "warning" and bad0["recomputed_value"] is None)
    bad1 = recompute_quality_safety_fact(
        numeric_fact(value=0.97, method="amount_of_say", inputs={"total_error": 1.0})
    )
    check("amount_of_say error=1 degrades", bad1["status"] == "warning")

    mismatch = recompute_quality_safety_fact(
        numeric_fact(value=5.0, method="amount_of_say", inputs={"total_error": 0.125})
    )
    check("amount_of_say mismatch fails blocking", mismatch["status"] == "failed" and mismatch["blocking"] is True)


# ── 5. softmax ──────────────────────────────────────────────────────────────


def test_softmax() -> None:
    values = [1.43, -0.4, 0.23]
    expected = math.exp(1.43 - 1.43) / sum(math.exp(v - 1.43) for v in values)
    ok = recompute_quality_safety_fact(
        numeric_fact(value=round(expected, 4), method="softmax", inputs={"values": values, "index": 0})
    )
    check("softmax recomputes stable value", abs((ok["recomputed_value"] or 0) - expected) < 1e-5, str(ok))
    check("softmax passes", ok["status"] == "passed")

    bad_index = recompute_quality_safety_fact(
        numeric_fact(value=0.5, method="softmax", inputs={"values": values, "index": 9})
    )
    check("softmax invalid index degrades", bad_index["status"] == "warning" and bad_index["recomputed_value"] is None)

    mismatch = recompute_quality_safety_fact(
        numeric_fact(value=0.05, method="softmax", inputs={"values": values, "index": 0})
    )
    check("softmax mismatch fails blocking", mismatch["status"] == "failed" and mismatch["blocking"] is True)


# ── 6. cross_entropy ────────────────────────────────────────────────────────


def test_cross_entropy() -> None:
    ok = recompute_quality_safety_fact(
        numeric_fact(value=0.56, method="cross_entropy", inputs={"probability": 0.57})
    )
    check("cross_entropy recomputes ~0.56", abs((ok["recomputed_value"] or 0) - 0.5621) < 0.001, str(ok))
    check("cross_entropy passes", ok["status"] == "passed")

    zero = recompute_quality_safety_fact(
        numeric_fact(value=0.56, method="cross_entropy", inputs={"probability": 0.0})
    )
    check("cross_entropy p=0 degrades", zero["status"] == "warning" and zero["recomputed_value"] is None)
    negative = recompute_quality_safety_fact(
        numeric_fact(value=0.56, method="cross_entropy", inputs={"probability": -0.5})
    )
    check("cross_entropy p<0 degrades", negative["status"] == "warning")

    mismatch = recompute_quality_safety_fact(
        numeric_fact(value=2.0, method="cross_entropy", inputs={"probability": 0.57})
    )
    check("cross_entropy mismatch fails blocking", mismatch["status"] == "failed" and mismatch["blocking"] is True)


# ── 7. forward_pass ─────────────────────────────────────────────────────────


def test_forward_pass() -> None:
    inputs = {"inputs": {"x1": 0.5, "x2": 0.37}, "weights": {"x1": 0.8, "x2": 0.2}, "bias": 0.1, "activation": "linear"}
    expected = 0.5 * 0.8 + 0.37 * 0.2 + 0.1
    ok = recompute_quality_safety_fact(numeric_fact(value=round(expected, 4), method="forward_pass", inputs=inputs))
    check("forward_pass linear recomputes", abs((ok["recomputed_value"] or 0) - expected) < 1e-9, str(ok))
    check("forward_pass passes", ok["status"] == "passed")

    relu_inputs = dict(inputs, weights={"x1": -1.0, "x2": -1.0}, bias=-1.0, activation="relu")
    relu = recompute_quality_safety_fact(numeric_fact(value=0.0, method="forward_pass", inputs=relu_inputs))
    check("forward_pass relu clamps to 0", relu["status"] == "passed" and relu["recomputed_value"] == 0.0, str(relu))

    sig_inputs = dict(inputs, activation="sigmoid")
    sig_expected = 1.0 / (1.0 + math.exp(-expected))
    sig = recompute_quality_safety_fact(numeric_fact(value=round(sig_expected, 4), method="forward_pass", inputs=sig_inputs))
    check("forward_pass sigmoid recomputes", abs((sig["recomputed_value"] or 0) - sig_expected) < 1e-5, str(sig))

    missing = recompute_quality_safety_fact(
        numeric_fact(
            value=0.5,
            method="forward_pass",
            inputs={"inputs": {"x1": 0.5}, "weights": {"x1": 0.8, "x2": 0.2}, "bias": 0.1},
        )
    )
    check("forward_pass missing input degrades", missing["status"] == "warning" and missing["recomputed_value"] is None)

    mismatch = recompute_quality_safety_fact(numeric_fact(value=99.0, method="forward_pass", inputs=inputs))
    check("forward_pass mismatch fails blocking", mismatch["status"] == "failed" and mismatch["blocking"] is True)


# ── 8. Fact provenance / status ─────────────────────────────────────────────


def test_provenance_status() -> None:
    inputs = {"misclassified_weight": 0.125}
    computed_ok = recompute_quality_safety_fact(
        numeric_fact(value=0.125, method="total_error", inputs=inputs, provenance="computed")
    )
    check("computed+match -> verified", computed_ok["verification_status"] == "verified" and computed_ok["provenance"] == "computed")

    computed_bad = recompute_quality_safety_fact(
        numeric_fact(value=0.40, method="total_error", inputs=inputs, provenance="computed")
    )
    check("computed+mismatch -> failed", computed_bad["verification_status"] == "failed")

    unverified_upgrade = recompute_quality_safety_fact(
        numeric_fact(value=0.125, method="total_error", inputs=inputs, provenance="unverified", verification_status="unverified")
    )
    check("unverified+valid -> upgraded computed", unverified_upgrade["provenance"] == "computed")
    check("unverified+valid -> verified", unverified_upgrade["verification_status"] == "verified")

    canonical = recompute_quality_safety_fact(
        {
            "id": "synthetic.canonical",
            "concept": "Synthetic Concept",
            "label": "synthetic_label",
            "value": 0.2,
            "type": "numeric",
            "provenance": "canonical_fixture",
            "verification_status": "verified",
            "confidence": "high",
            "source_ref": "source_page_1",
            "computation": None,
        }
    )
    check("canonical not recomputed this slice", canonical["status"] == "not_applicable")
    check("canonical stays canonical", canonical["provenance"] == "canonical_fixture")

    non_numeric = recompute_quality_safety_fact(
        {
            "id": "synthetic.string",
            "concept": "Synthetic Concept",
            "label": "synthetic_label",
            "value": "synthetic categorical",
            "type": "string",
            "provenance": "extracted_high",
            "verification_status": "unverified",
            "confidence": "low",
        }
    )
    check("non-numeric -> not_applicable", non_numeric["status"] == "not_applicable")
    check("non-numeric not failed", non_numeric["verification_status"] != "failed")


# ── 9. Integration with Slice 110 schema ────────────────────────────────────


def test_slice110_integration() -> None:
    raw = sheet_of(
        numeric_fact(
            fact_id="synthetic.gini",
            value=0.20,
            method="weighted_gini",
            inputs={"leafA": {"yes": 3, "no": 0}, "leafB": {"yes": 1, "no": 4}},
        ),
        numeric_fact(
            fact_id="synthetic.error",
            value=0.40,
            method="total_error",
            inputs={"misclassified_weight": 0.125},
        ),
    )
    raw_snapshot = serialized(raw)
    normalized = normalize_quality_safety_fact_sheet(raw)
    result = verify_quality_safety_fact_sheet(normalized)
    report = result["report"]
    check("integration status failed", report["status"] == "failed", str(report["status"]))
    check("integration one blocking", report["summary"]["blocking_failure_count"] == 1)
    check("integration verified one", report["summary"]["verified_fact_count"] == 1)
    check("no caller mutation", serialized(raw) == raw_snapshot)
    first = verify_quality_safety_fact_sheet(normalized)
    second = verify_quality_safety_fact_sheet(normalized)
    check("deterministic verify", serialized(first) == serialized(second))
    verified_facts = result["fact_sheet"]["concepts"][0]["facts"]
    statuses = {fact["id"]: fact["verification_status"] for fact in verified_facts}
    check("verified sheet reflects pass", statuses.get("synthetic.gini") == "verified", str(statuses))
    check("verified sheet reflects fail", statuses.get("synthetic.error") == "failed", str(statuses))
    assert_report_shape("integration", report)


# ── 10. Integration with Slice 109 synthetic fixtures ───────────────────────


def test_seed_fixture_integration() -> None:
    fixture_dir = REPO / "test_scripts" / "fixtures" / "quality_safety"
    clean = json.loads((fixture_dir / "clean_neural_networks_synthetic.json").read_text(encoding="utf-8"))
    ambiguous = json.loads((fixture_dir / "ambiguous_ensemble_synthetic.json").read_text(encoding="utf-8"))

    clean_targets = {item["label"]: item["value"] for item in clean["ground_truth_numerics"]}
    ambiguous_targets = {item["label"]: item["value"] for item in ambiguous["ground_truth_numerics"]}

    clean_sheet = sheet_of(
        numeric_fact(
            fact_id="clean.cross_entropy",
            label="synthetic_cross_entropy",
            value=clean_targets["synthetic_cross_entropy"],
            method="cross_entropy",
            inputs={"probability": 0.57},
        )
    )
    clean_report = build_quality_safety_recompute_report(normalize_quality_safety_fact_sheet(clean_sheet))
    check("clean fixture verified", clean_report["summary"]["verified_fact_count"] >= 1, str(clean_report["summary"]))
    check("clean fixture not failed", clean_report["status"] != "failed")

    ambiguous_sheet = sheet_of(
        numeric_fact(
            fact_id="ambiguous.gini",
            label="synthetic_stump_choice_score",
            value=ambiguous_targets["synthetic_stump_choice_score"],
            method="weighted_gini",
            inputs={"leafA": {"yes": 3, "no": 0}, "leafB": {"yes": 1, "no": 4}},
        ),
        numeric_fact(
            fact_id="ambiguous.error",
            label="synthetic_weighted_error",
            value=ambiguous_targets["synthetic_weighted_error"],
            method="total_error",
            inputs={"misclassified_weight": 0.125},
        ),
    )
    ambiguous_report = build_quality_safety_recompute_report(normalize_quality_safety_fact_sheet(ambiguous_sheet))
    check("ambiguous fixture verified", ambiguous_report["summary"]["verified_fact_count"] == 2, str(ambiguous_report["summary"]))
    check("ambiguous fixture passed", ambiguous_report["status"] == "passed", str(ambiguous_report["status"]))
    assert_no_canary("seed fixture integration", {"clean": clean_report, "ambiguous": ambiguous_report})


# ── 11. Report shape / status transitions ───────────────────────────────────


def test_report_status_transitions() -> None:
    passing = build_quality_safety_recompute_report(
        normalize_quality_safety_fact_sheet(
            sheet_of(numeric_fact(value=0.125, method="total_error", inputs={"misclassified_weight": 0.125}))
        )
    )
    check("all-pass -> passed", passing["status"] == "passed")
    check("all-pass no blocking", passing["summary"]["blocking_failure_count"] == 0)

    warning = build_quality_safety_recompute_report(
        normalize_quality_safety_fact_sheet(
            sheet_of(
                {
                    "id": "synthetic.unsupported",
                    "concept": "Synthetic Concept",
                    "label": "synthetic_label",
                    "value": 1.0,
                    "type": "numeric",
                    "provenance": "computed",
                    "verification_status": "verified",
                    "confidence": "high",
                    "computation": {"method": "manual", "inputs": {}, "result": 1.0},
                }
            )
        )
    )
    check("unsupported-only -> warning", warning["status"] == "warning", str(warning["status"]))
    check("unsupported warns token", "unsupported_computation_method" in warning["warnings"])

    failing = build_quality_safety_recompute_report(
        normalize_quality_safety_fact_sheet(
            sheet_of(numeric_fact(value=0.90, method="total_error", inputs={"misclassified_weight": 0.125}))
        )
    )
    check("mismatch -> failed", failing["status"] == "failed")
    check("mismatch blocking increments", failing["summary"]["blocking_failure_count"] == 1)

    many = sheet_of(*[numeric_fact(value=0.125, method="total_error", inputs={"misclassified_weight": 0.125}) for _ in range(5)])
    capped = build_quality_safety_recompute_report(normalize_quality_safety_fact_sheet(many), max_items=2)
    check("max_items -> partial", capped["status"] == "partial")
    check("max_items warning", "max_items_reached" in capped["warnings"])
    check("max_items processed two", capped["summary"]["fact_count"] == 2)


# ── 12. No-leak sweep ───────────────────────────────────────────────────────


def test_no_leak_sweep() -> None:
    hostile_sheet = {
        "lecture_id": HOSTILE_CANARIES[0],
        "source_quality": "private_cloud",
        "concepts": [
            {
                "concept": HOSTILE_CANARIES[1],
                "facts": [
                    {
                        "id": HOSTILE_CANARIES[2],
                        "concept": HOSTILE_CANARIES[5],
                        "label": HOSTILE_CANARIES[6],
                        "value": 0.125,
                        "type": "numeric",
                        "provenance": "computed",
                        "verification_status": "verified",
                        "confidence": "high",
                        "source_ref": HOSTILE_CANARIES[4],
                        "computation": {
                            "method": "total_error",
                            "inputs": {HOSTILE_CANARIES[9]: HOSTILE_CANARIES[10], "misclassified_weight": 0.125},
                            "result": 0.125,
                        },
                    },
                    {
                        "id": HOSTILE_CANARIES[7],
                        "concept": "Synthetic Concept",
                        "label": "synthetic_label",
                        "value": HOSTILE_CANARIES[11],
                        "type": "string",
                        "provenance": "extracted_high",
                        "verification_status": "unverified",
                        "confidence": "low",
                    },
                ],
            }
        ],
    }
    result = verify_quality_safety_fact_sheet(normalize_quality_safety_fact_sheet(hostile_sheet))
    assert_no_canary("no-leak verified sheet", result["fact_sheet"])
    assert_no_canary("no-leak report", result["report"])
    # Direct recompute with hostile id/inputs must also stay clean.
    direct = recompute_quality_safety_fact(
        {
            "id": HOSTILE_CANARIES[0],
            "type": "numeric",
            "value": 0.125,
            "provenance": "computed",
            "verification_status": "verified",
            "computation": {"method": "total_error", "inputs": {"misclassified_weight": 0.125}, "result": 0.125},
        }
    )
    check("hostile id sanitized", direct["fact_id"] == "fact_unknown", str(direct["fact_id"]))
    assert_no_canary("no-leak direct", direct)


# ── 13b. Slice 173A golden-target recompute proof ───────────────────────────

_GOLDEN_RECORD_KEYS = {
    "source_label",
    "target_id",
    "expected_label",
    "recompute_status",
    "committed_value_available",
    "recomputed_matches_committed_fixture",
    "wrong_printed_value_detected_when_candidate_supplied",
    "independently_verified_for_generation",
    "verified_value_kind",
    "confidence",
    "blocking_issue",
    "guide_candidate_status",
    "writer_should_receive_committed_value",
    "warnings",
}


def _golden_spec(lecture_id: str, numerics: list[dict[str, Any]]) -> dict[str, Any]:
    # Synthetic, public-safe golden-like spec (math-identity labels only).
    return {
        "kind": "quality_safety_golden_pair",
        "lecture_id": lecture_id,
        "ground_truth_numerics": numerics,
    }


def _record_by_id(proof: dict[str, Any], target_id: str) -> dict[str, Any]:
    for record in proof.get("records", []):
        if record.get("target_id") == target_id:
            return record
    return {}


def test_golden_label_recompute_plan() -> None:
    # Formula-encoding labels parse to a closed recompute plan (no answer table).
    ce = golden_label_recompute_plan("cross_entropy_neg_ln_0.5")
    check("ce plan method", ce and ce["method"] == "cross_entropy", str(ce))
    check("ce plan input", ce and abs(ce["inputs"]["probability"] - 0.5) < 1e-12, str(ce))
    aos = golden_label_recompute_plan("amount_of_say_half_ln_3")
    # half_ln_3 -> (1-e)/e = 3 -> e = 0.25
    check("aos plan method", aos and aos["method"] == "amount_of_say", str(aos))
    check("aos plan input derived", aos and abs(aos["inputs"]["total_error"] - 0.25) < 1e-12, str(aos))
    # No answer-table / known_numbers path: an ordinary concept label yields NO plan.
    check("no plan for concept label", golden_label_recompute_plan("gini_chest_pain") is None)
    check("no plan for arbitrary", golden_label_recompute_plan("totally_unrelated") is None)
    check("no plan for non-string", golden_label_recompute_plan(123) is None)
    check("no plan for malformed suffix", golden_label_recompute_plan("cross_entropy_neg_ln_abc") is None)


def test_golden_recompute_proof_derives_committed() -> None:
    # Committed expected values that are correct -> independently recomputed & matched.
    spec = _golden_spec(
        "nn_synth",
        [
            {"label": "cross_entropy_neg_ln_0.5", "value": 0.69, "tol": 0.01},
            {"label": "amount_of_say_half_ln_3", "value": 0.55, "tol": 0.01},
        ],
    )
    proof = build_golden_target_recompute_proof(spec)
    ce = _record_by_id(proof, "cross_entropy_neg_ln_0.5")
    aos = _record_by_id(proof, "amount_of_say_half_ln_3")
    check("ce formula_verified", ce.get("recompute_status") == "formula_verified", str(ce))
    check("ce matches committed", ce.get("recomputed_matches_committed_fixture") is True, str(ce))
    check("ce high confidence", ce.get("confidence") == "high", str(ce))
    check("ce committed available", ce.get("committed_value_available") is True)
    # Independently verified -> generation-ready -> writer may receive it.
    check("ce independently verified", ce.get("independently_verified_for_generation") is True, str(ce))
    check("ce writer should receive", ce.get("writer_should_receive_committed_value") is True, str(ce))
    check("aos formula_verified", aos.get("recompute_status") == "formula_verified", str(aos))
    check("aos matches committed", aos.get("recomputed_matches_committed_fixture") is True, str(aos))
    check("aos independently verified", aos.get("independently_verified_for_generation") is True, str(aos))
    check("aos writer should receive", aos.get("writer_should_receive_committed_value") is True, str(aos))
    summary = proof["summary"]
    check("summary 2 formula_verified", summary["formula_verified_count"] == 2, str(summary))
    check("summary 2 committed match", summary["committed_fixture_match_count"] == 2, str(summary))
    check("summary 2 recomputed", summary["recomputed_count"] == 2, str(summary))
    check("summary 2 independently verified", summary["independently_verified_for_generation_count"] == 2, str(summary))
    check("summary 2 writer should receive", summary["writer_should_receive_committed_value_count"] == 2, str(summary))
    assert_no_canary("golden derive proof", proof)


def test_golden_recompute_no_known_numbers_detects_disagreement() -> None:
    # The committed value is deliberately WRONG. A recompute-first engine derives
    # the value from the label's formula and DISAGREES -- proving there is no
    # answer-table that would trivially "match" whatever value is supplied.
    spec = _golden_spec(
        "nn_synth",
        [{"label": "cross_entropy_neg_ln_0.5", "value": 0.10, "tol": 0.01}],
    )
    proof = build_golden_target_recompute_proof(spec)
    rec = _record_by_id(proof, "cross_entropy_neg_ln_0.5")
    check("disagreement recomputed", rec.get("recompute_status") == "recomputed", str(rec))
    check("disagreement not matched", rec.get("recomputed_matches_committed_fixture") is False, str(rec))
    check("disagreement low confidence", rec.get("confidence") == "low", str(rec))
    check(
        "disagreement blocking_issue",
        rec.get("blocking_issue") == "recompute_disagrees_with_committed_fixture",
        str(rec),
    )


def test_golden_recompute_proof_wrong_candidate_detected() -> None:
    # No-laundering: a wrong printed value is a DIAGNOSTIC. The writer may receive
    # the committed value ONLY for the independently verified target -- never for a
    # source_required / unsupported target that merely has a committed fixture value.
    spec = _golden_spec(
        "ens_synth",
        [
            {"label": "amount_of_say_half_ln_3", "value": 0.55, "tol": 0.01},  # formula_verified
            {"label": "gini_synth_node", "value": 0.20, "tol": 0.01},  # source_required
            {"label": "proximity_synth", "value": 0.80, "tol": 0.01},  # unsupported
        ],
    )
    # Closed matcher classifications (read-only): wrong / wrong / missing.
    candidate = {
        "amount_of_say_half_ln_3": "found_but_wrong_value",
        "gini_synth_node": "found_but_wrong_value",
        "proximity_synth": "genuinely_missing",
    }
    proof = build_golden_target_recompute_proof(
        spec, candidate_classification_by_target=candidate
    )
    verified_wrong = _record_by_id(proof, "amount_of_say_half_ln_3")
    src_required_wrong = _record_by_id(proof, "gini_synth_node")
    unsupported_missing = _record_by_id(proof, "proximity_synth")

    # Independently verified target whose printed value is wrong -> writer-ready.
    check("verified -> wrong detected", verified_wrong.get("wrong_printed_value_detected_when_candidate_supplied") is True, str(verified_wrong))
    check("verified -> independently verified", verified_wrong.get("independently_verified_for_generation") is True, str(verified_wrong))
    check("verified -> writer receives committed", verified_wrong.get("writer_should_receive_committed_value") is True, str(verified_wrong))

    # source_required target with a wrong printed value: detected, but NOT writer-ready.
    check("source_required -> wrong detected", src_required_wrong.get("wrong_printed_value_detected_when_candidate_supplied") is True, str(src_required_wrong))
    check("source_required -> committed available", src_required_wrong.get("committed_value_available") is True, str(src_required_wrong))
    check("source_required -> NOT independently verified", src_required_wrong.get("independently_verified_for_generation") is False, str(src_required_wrong))
    check("source_required -> writer NOT ready (no laundering)", src_required_wrong.get("writer_should_receive_committed_value") is False, str(src_required_wrong))

    # unsupported target, genuinely missing: not a wrong-value, not writer-ready.
    check("unsupported -> missing status", unsupported_missing.get("guide_candidate_status") == "missing", str(unsupported_missing))
    check("unsupported -> not a wrong printed value", unsupported_missing.get("wrong_printed_value_detected_when_candidate_supplied") is False, str(unsupported_missing))
    check("unsupported -> writer NOT ready", unsupported_missing.get("writer_should_receive_committed_value") is False, str(unsupported_missing))

    summary = proof["summary"]
    check("summary 2 wrong printed", summary["wrong_printed_value_detected_count"] == 2, str(summary))
    check("summary 1 independently verified", summary["independently_verified_for_generation_count"] == 1, str(summary))
    check("summary 1 writer should receive", summary["writer_should_receive_committed_value_count"] == 1, str(summary))
    # gini (wrong, not verified) + proximity (missing, not verified) are unresolved;
    # the verified amount_of_say target is resolved despite the wrong printed value.
    check("summary 2 unresolved for generation", summary["unresolved_for_generation_count"] == 2, str(summary))


def test_golden_recompute_proof_source_required_and_unsupported() -> None:
    spec = _golden_spec(
        "ens_synth",
        [
            {"label": "gini_synth_node", "value": 0.20, "tol": 0.01},  # supported family, no inputs
            {"label": "softmax_synth", "value": 0.69, "tol": 0.01},  # supported family, no inputs
            {"label": "proximity_synth", "value": 0.80, "tol": 0.01},  # no supported method
        ],
    )
    proof = build_golden_target_recompute_proof(spec)
    gini = _record_by_id(proof, "gini_synth_node")
    softmax = _record_by_id(proof, "softmax_synth")
    prox = _record_by_id(proof, "proximity_synth")
    check("gini source_required", gini.get("recompute_status") == "source_required", str(gini))
    check("softmax source_required", softmax.get("recompute_status") == "source_required", str(softmax))
    check("proximity unsupported", prox.get("recompute_status") == "unsupported", str(prox))
    # Honest degradation: NO value invented, NO confidence promotion, and even
    # though a committed fixture value exists, it is NEVER writer-ready here.
    for rec in (gini, softmax, prox):
        check(f"{rec.get('target_id')} no match", rec.get("recomputed_matches_committed_fixture") is None, str(rec))
        check(f"{rec.get('target_id')} kind unavailable", rec.get("verified_value_kind") == "unavailable", str(rec))
        check(f"{rec.get('target_id')} confidence none", rec.get("confidence") == "none", str(rec))
        check(f"{rec.get('target_id')} committed available", rec.get("committed_value_available") is True, str(rec))
        check(f"{rec.get('target_id')} NOT independently verified", rec.get("independently_verified_for_generation") is False, str(rec))
        check(f"{rec.get('target_id')} writer NOT ready (no laundering)", rec.get("writer_should_receive_committed_value") is False, str(rec))
    summary = proof["summary"]
    check("summary source_required 2", summary["source_required_count"] == 2, str(summary))
    check("summary unsupported 1", summary["unsupported_count"] == 1, str(summary))
    check("summary 0 formula_verified", summary["formula_verified_count"] == 0, str(summary))
    check("summary 0 independently verified", summary["independently_verified_for_generation_count"] == 0, str(summary))
    check("summary 0 writer should receive", summary["writer_should_receive_committed_value_count"] == 0, str(summary))


def test_golden_recompute_no_laundering_gate() -> None:
    # The writer-readiness gate is satisfied ONLY by independent recompute/formula
    # verification with high/medium confidence -- never by the mere presence of a
    # committed expected fixture value. This is the no-laundering requirement.
    spec = _golden_spec(
        "nn_synth",
        [
            {"label": "cross_entropy_neg_ln_0.5", "value": 0.69, "tol": 0.01},  # formula_verified
            {"label": "gini_synth_node", "value": 0.20, "tol": 0.01},  # source_required, fixture-only
            {"label": "proximity_synth", "value": 0.80, "tol": 0.01},  # unsupported, fixture-only
        ],
    )
    proof = build_golden_target_recompute_proof(spec)
    for rec in proof["records"]:
        verified = rec.get("recompute_status") in {"recomputed", "formula_verified"}
        matched = rec.get("recomputed_matches_committed_fixture") is True
        conf_ok = rec.get("confidence") in {"high", "medium"}
        expected_ready = verified and matched and conf_ok
        # writer-readiness exactly tracks independent verification.
        check(
            f"{rec.get('target_id')} writer gate == independent verification",
            rec.get("writer_should_receive_committed_value") == expected_ready
            and rec.get("independently_verified_for_generation") == expected_ready,
            str(rec),
        )
        # A committed fixture value alone is never sufficient.
        if not expected_ready:
            check(
                f"{rec.get('target_id')} fixture-only is NOT writer-ready",
                rec.get("writer_should_receive_committed_value") is False
                and rec.get("committed_value_available") is True,
                str(rec),
            )
    verified_rec = _record_by_id(proof, "cross_entropy_neg_ln_0.5")
    check("formula_verified is writer-ready", verified_rec.get("writer_should_receive_committed_value") is True, str(verified_rec))


def test_golden_recompute_proof_degrades_and_no_mutation() -> None:
    # Malformed inputs degrade to a closed envelope; never raise.
    none_proof = build_golden_target_recompute_proof(None)
    check("none -> closed kind", none_proof.get("kind") == "quality_safety_golden_recompute_proof")
    check("none -> spec_missing warning", "golden_spec_missing" in none_proof.get("warnings", []), str(none_proof))
    check("none -> empty records", none_proof.get("records") == [])
    nonsense = build_golden_target_recompute_proof({"lecture_id": "x", "ground_truth_numerics": "nope"})
    check("nonsense -> no_numeric_targets", "no_numeric_targets" in nonsense.get("warnings", []), str(nonsense))
    bad_candidate = build_golden_target_recompute_proof(
        _golden_spec("x", [{"label": "cross_entropy_neg_ln_0.5", "value": 0.69, "tol": 0.01}]),
        candidate_classification_by_target=["not", "a", "dict"],
    )
    check("bad candidate ignored", "candidate_classification_ignored" in bad_candidate.get("warnings", []), str(bad_candidate))
    # Input spec must never be mutated by the proof builder.
    spec = _golden_spec("x", [{"label": "cross_entropy_neg_ln_0.5", "value": 0.69, "tol": 0.01}])
    before = json.dumps(spec, sort_keys=True)
    build_golden_target_recompute_proof(spec)
    check("spec not mutated", json.dumps(spec, sort_keys=True) == before)


def test_golden_recompute_proof_closed_schema() -> None:
    spec = _golden_spec(
        "ens_synth",
        [
            {"label": "cross_entropy_neg_ln_0.5", "value": 0.69, "tol": 0.01},
            {"label": "gini_synth_node", "value": 0.20, "tol": 0.01},
            {"label": "proximity_synth", "value": 0.80, "tol": 0.01},
        ],
    )
    candidate = {"cross_entropy_neg_ln_0.5": "found_but_wrong_value"}
    proof = build_golden_target_recompute_proof(spec, candidate_classification_by_target=candidate)
    # JSON serializable.
    json.dumps(proof)
    for rec in proof["records"]:
        check("record keys closed", set(rec.keys()) == _GOLDEN_RECORD_KEYS, str(set(rec.keys())))
        check("status closed", rec["recompute_status"] in GOLDEN_RECOMPUTE_STATUSES, str(rec["recompute_status"]))
        check("value_kind closed", rec["verified_value_kind"] in GOLDEN_VALUE_KINDS, str(rec["verified_value_kind"]))
        check("confidence closed", rec["confidence"] in GOLDEN_CONFIDENCE_LEVELS, str(rec["confidence"]))
        check("candidate status closed", rec["guide_candidate_status"] in GOLDEN_CANDIDATE_STATUSES, str(rec["guide_candidate_status"]))
        check("record warnings closed", all(w in GOLDEN_PROOF_WARNING_ORDER for w in rec["warnings"]), str(rec["warnings"]))
        check(
            "tri-state fields",
            rec["recomputed_matches_committed_fixture"] in (True, False, None)
            and rec["wrong_printed_value_detected_when_candidate_supplied"] in (True, False, None)
            and rec["writer_should_receive_committed_value"] in (True, False, None),
            str(rec),
        )
    check("proof warnings closed", all(w in GOLDEN_PROOF_WARNING_ORDER for w in proof["warnings"]), str(proof["warnings"]))
    summary = summarize_golden_target_recompute_proof(proof["records"])
    check(
        "summary non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for k, v in summary.items() if k != "kind"),
        str(summary),
    )
    assert_no_canary("golden closed schema", proof)


# ── 13c. Slice 173B generation-ready numeric records ────────────────────────


def test_generation_ready_includes_only_verified() -> None:
    # Two correct formula-encoding targets -> both independently verified -> both
    # emitted as generation-ready records carrying their (proven) committed value.
    spec = _golden_spec(
        "nn_synth",
        [
            {"label": "cross_entropy_neg_ln_0.5", "value": 0.69, "tol": 0.01},
            {"label": "amount_of_say_half_ln_3", "value": 0.55, "tol": 0.01},
        ],
    )
    out = build_generation_ready_numeric_records(spec)
    check("gen-ready kind", out.get("kind") == GENERATION_READY_KIND, str(out.get("kind")))
    recs = out.get("records")
    check("gen-ready 2 records", isinstance(recs, list) and len(recs) == 2, str(recs))
    for rec in recs:
        check("gen-ready instruction token", rec.get("instruction_token") == VERIFIED_VALUE_INSTRUCTION_TOKEN, str(rec))
        check("gen-ready has rendered value", isinstance(rec.get("verified_value_rendered"), str) and rec["verified_value_rendered"], str(rec))
        check("gen-ready confidence ok", rec.get("confidence") in ("high", "medium"), str(rec))
    s = out["summary"]
    check("gen-ready seen 2", s["records_seen"] == 2, str(s))
    check("gen-ready included 2", s["records_included_for_generation"] == 2, str(s))
    check("gen-ready no wrong included", s["wrong_candidate_values_included"] == 0, str(s))
    check("gen-ready no fixture-only included", s["fixture_only_values_included"] == 0, str(s))
    assert_no_canary("gen-ready verified", out)


def test_generation_ready_excludes_source_required_and_unsupported() -> None:
    # A non-formula concept label with a supported family -> source_required;
    # a label with no supported method -> unsupported. Neither is emitted, and the
    # committed value is never read into the output.
    spec = _golden_spec(
        "mix_synth",
        [
            {"label": "cross_entropy_neg_ln_0.5", "value": 0.69, "tol": 0.01},
            {"label": "gini_node_synth", "value": 0.42, "tol": 0.01},
            {"label": "totally_unrelated_synth", "value": 0.99, "tol": 0.01},
        ],
    )
    out = build_generation_ready_numeric_records(spec)
    recs = out.get("records")
    check("excl: only 1 verified emitted", isinstance(recs, list) and len(recs) == 1, str(recs))
    check("excl: emitted is the verified one", recs and recs[0]["target_id"] == "cross_entropy_neg_ln_0.5", str(recs))
    s = out["summary"]
    check("excl: source_required counted", s["records_excluded_source_required"] == 1, str(s))
    check("excl: unsupported counted", s["records_excluded_unsupported"] == 1, str(s))
    check("excl: umbrella excludes 2", s["records_excluded_not_independently_verified"] == 2, str(s))
    # No excluded committed value (0.42 / 0.99) may appear anywhere in the output.
    blob = serialized(out)
    check("excl: source_required value absent", "0.42" not in blob, blob)
    check("excl: unsupported value absent", "0.99" not in blob, blob)


def test_generation_ready_excludes_wrong_committed_disagreement() -> None:
    # A deliberately WRONG committed value -> recompute disagrees -> NOT verified ->
    # excluded, and the wrong value never enters generation context.
    spec = _golden_spec(
        "wrong_synth",
        [{"label": "cross_entropy_neg_ln_0.5", "value": 0.10, "tol": 0.01}],
    )
    out = build_generation_ready_numeric_records(spec)
    check("wrong: no records emitted", out.get("records") == [], str(out.get("records")))
    s = out["summary"]
    check("wrong: included 0", s["records_included_for_generation"] == 0, str(s))
    check("wrong: umbrella excludes 1", s["records_excluded_not_independently_verified"] == 1, str(s))
    check("wrong: invariant wrong=0", s["wrong_candidate_values_included"] == 0, str(s))
    blob = serialized(out)
    check("wrong: wrong value absent", "0.1" not in blob, blob)


def test_generation_ready_degrades_safely() -> None:
    for bad in (None, 123, "x", [], {}, {"ground_truth_numerics": "nope"}):
        out = build_generation_ready_numeric_records(bad)
        check(f"degrade kind {type(bad).__name__}", out.get("kind") == GENERATION_READY_KIND, str(out))
        check(f"degrade empty records {type(bad).__name__}", out.get("records") == [], str(out))
        check(f"degrade invariant wrong=0 {type(bad).__name__}", out["summary"]["wrong_candidate_values_included"] == 0, str(out))
        assert_no_canary(f"degrade {type(bad).__name__}", out)


# ── 13. Import hygiene ──────────────────────────────────────────────────────


def test_import_hygiene() -> None:
    source_path = REPO / "pipeline" / "quality_safety_recompute_verifier.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    bad = [name for name in imports for part in FORBIDDEN_IMPORT_PARTS if part in name.lower()]
    check("no forbidden imports", bad == [], str(bad))
    check("imports allowed-only", set(imports).issubset(ALLOWED_IMPORTS), str(sorted(set(imports))))


def run() -> int:
    test_empty_and_malformed()
    test_weighted_gini()
    test_total_error()
    test_amount_of_say()
    test_softmax()
    test_cross_entropy()
    test_forward_pass()
    test_provenance_status()
    test_slice110_integration()
    test_seed_fixture_integration()
    test_report_status_transitions()
    test_golden_label_recompute_plan()
    test_golden_recompute_proof_derives_committed()
    test_golden_recompute_no_known_numbers_detects_disagreement()
    test_golden_recompute_proof_wrong_candidate_detected()
    test_golden_recompute_proof_source_required_and_unsupported()
    test_golden_recompute_no_laundering_gate()
    test_golden_recompute_proof_degrades_and_no_mutation()
    test_golden_recompute_proof_closed_schema()
    test_generation_ready_includes_only_verified()
    test_generation_ready_excludes_source_required_and_unsupported()
    test_generation_ready_excludes_wrong_committed_disagreement()
    test_generation_ready_degrades_safely()
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_recompute_verifier: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
