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
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_recompute_verifier: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
