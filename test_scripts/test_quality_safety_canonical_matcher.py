#!/usr/bin/env python3
"""Tests for Slice 112 Quality Safety canonical fixture matcher v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. Hostile strings below
are fake canaries used only to prove they are not echoed.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_canonical_matcher import (  # noqa: E402
    build_quality_safety_canonical_match_report,
    match_quality_safety_canonical_facts,
    normalize_quality_safety_canonical_fixture,
)
from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet  # noqa: E402
from pipeline.quality_safety_recompute_verifier import verify_quality_safety_fact_sheet  # noqa: E402

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_canonical1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_CANONICAL_MARKER",
    "TABLE_TEXT_PRIVATE_CANONICAL_MARKER",
    "CAPTION_PRIVATE_CANONICAL_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_CANONICAL_MARKER",
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
    "sk_canonical",
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
ALLOWED_IMPORTS = {"__future__", "math", "re", "typing", "pipeline.quality_safety_fact_sheet"}
REPORT_STATUSES = {"passed", "warning", "failed", "skipped", "partial"}
CHECK_IDS = {
    "canonical_fixture_match",
    "canonical_fixture_mismatch",
    "canonical_fixture_missing",
    "canonical_fixture_skipped_by_recompute_verified",
    "canonical_fixture_skipped_by_recompute_failed",
    "canonical_fixture_not_applicable",
}
CHECK_STATUSES = {"passed", "warning", "failed", "not_applicable", "unknown"}
REPORT_WARNINGS = {
    "fact_sheet_missing",
    "canonical_fixture_missing",
    "malformed_fact_sheet_degraded",
    "malformed_canonical_fixture_degraded",
    "canonical_lecture_id_mismatch",
    "canonical_fact_missing",
    "canonical_value_mismatch",
    "canonical_not_eligible",
    "skipped_by_recompute_verified",
    "skipped_by_recompute_failed",
    "max_items_reached",
}
FIXTURE_WARNINGS = {
    "malformed_canonical_fixture_degraded",
    "invalid_canonical_fact_dropped",
    "invalid_canonical_value",
    "invalid_canonical_tolerance",
    "invalid_canonical_match_key",
    "invalid_lecture_id",
    "invalid_source_quality",
    "unsafe_string_sanitized",
    "max_items_reached",
}


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


def assert_report_shape(name: str, report: dict[str, Any]) -> None:
    check(f"{name}: kind", report.get("kind") == "quality_safety_canonical_match_report")
    check(f"{name}: version", report.get("version") == 1)
    check(f"{name}: blocking true", report.get("blocking") is True)
    check(f"{name}: status closed", report.get("status") in REPORT_STATUSES, str(report.get("status")))
    summary = report.get("summary", {})
    expected_summary = {
        "fact_count",
        "canonical_fact_count",
        "eligible_fact_count",
        "matched_fact_count",
        "mismatch_count",
        "unmatched_fact_count",
        "skipped_by_recompute_count",
        "warning_count",
        "blocking_failure_count",
    }
    check(f"{name}: summary keys", set(summary) == expected_summary, str(summary))
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


def assert_fixture_shape(name: str, fixture: dict[str, Any]) -> None:
    check(f"{name}: fixture kind", fixture.get("kind") == "quality_safety_canonical_fixture")
    check(f"{name}: fixture version", fixture.get("version") == 1)
    check(
        f"{name}: fixture warnings closed",
        all(w in FIXTURE_WARNINGS for w in fixture.get("warnings", [])),
        str(fixture.get("warnings")),
    )


def numeric_fact(
    *,
    fact_id: str = "synthetic.fact",
    label: str = "synthetic_label",
    value: Any = 0.2,
    provenance: str = "unverified",
    verification_status: str = "unverified",
    computation: Any = None,
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "concept": "Synthetic Concept",
        "label": label,
        "value": value,
        "type": "numeric",
        "provenance": provenance,
        "verification_status": verification_status,
        "confidence": "low",
        "source_ref": "source_page_1",
        "computation": computation,
    }


def typed_fact(*, fact_id: str, label: str, value: Any, fact_type: str) -> dict[str, Any]:
    return {
        "id": fact_id,
        "concept": "Synthetic Concept",
        "label": label,
        "value": value,
        "type": fact_type,
        "provenance": "unverified",
        "verification_status": "unverified",
        "confidence": "low",
        "source_ref": "source_page_1",
        "computation": None,
    }


def sheet_of(*facts: dict[str, Any], lecture_id: str = "synthetic_fixture") -> dict[str, Any]:
    return {
        "lecture_id": lecture_id,
        "source_quality": "synthetic",
        "concepts": [{"concept": "Synthetic Concept", "facts": list(facts)}],
    }


def canonical(
    *,
    lecture_id: str = "synthetic_fixture",
    facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_canonical_fixture",
        "lecture_id": lecture_id,
        "source_quality": "synthetic",
        "facts": facts
        if facts is not None
        else [
            {
                "id": "synthetic.canonical.fact",
                "label": "synthetic_label",
                "value": 0.2,
                "tol": 0.01,
                "type": "numeric",
                "match_key": f"{lecture_id}::synthetic_label",
                "allowed_aliases": [],
                "provenance": "canonical_fixture",
            }
        ],
    }


def first_check(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks", [])
    return checks[0] if checks else {}


def test_empty_and_malformed() -> None:
    missing_sheet = build_quality_safety_canonical_match_report(None, canonical())
    check("missing fact sheet skipped", missing_sheet["status"] == "skipped")
    check("missing fact sheet warning", "fact_sheet_missing" in missing_sheet["warnings"])
    assert_report_shape("missing fact sheet", missing_sheet)

    malformed_sheet = build_quality_safety_canonical_match_report(["not", "a", "dict"], canonical())
    check("malformed fact sheet degraded", "malformed_fact_sheet_degraded" in malformed_sheet["warnings"])
    assert_report_shape("malformed fact sheet", malformed_sheet)

    missing_fixture = build_quality_safety_canonical_match_report(sheet_of(numeric_fact()), None)
    check("missing canonical fixture skipped", missing_fixture["status"] == "skipped")
    check("missing canonical fixture warning", "canonical_fixture_missing" in missing_fixture["warnings"])
    assert_report_shape("missing canonical fixture", missing_fixture)

    malformed_fixture = build_quality_safety_canonical_match_report(sheet_of(numeric_fact()), ["bad"])
    check("malformed canonical fixture degraded", "malformed_canonical_fixture_degraded" in malformed_fixture["warnings"])
    check("malformed canonical fixture no raise", malformed_fixture["kind"] == "quality_safety_canonical_match_report")
    assert_report_shape("malformed canonical fixture", malformed_fixture)

    for bad in (None, 1.5, "bad", [], {"facts": "bad"}):
        report = build_quality_safety_canonical_match_report(bad, bad)
        check(f"never raises for {type(bad).__name__}", report.get("status") in REPORT_STATUSES)


def test_canonical_fixture_normalization() -> None:
    raw = canonical(
        facts=[
            {
                "id": "synthetic.fact.id",
                "label": "synthetic_label",
                "value": 0.2,
                "tol": 0.01,
                "type": "numeric",
                "match_key": "synthetic_fixture::synthetic_label",
                "allowed_aliases": ["synthetic_label_alias"],
                "provenance": "canonical_fixture",
            }
        ]
    )
    normalized = normalize_quality_safety_canonical_fixture(raw)
    check("valid fixture no warnings", normalized["warnings"] == [], str(normalized["warnings"]))
    check("valid fixture fact kept", len(normalized["facts"]) == 1)
    check("valid fixture provenance canonical", normalized["facts"][0]["provenance"] == "canonical_fixture")
    assert_fixture_shape("valid fixture", normalized)
    assert_no_canary("valid fixture", normalized)

    invalid = normalize_quality_safety_canonical_fixture(
        {
            "lecture_id": HOSTILE_CANARIES[0],
            "source_quality": "private_cloud",
            "facts": [
                {"id": "synthetic.bad.value", "label": "synthetic_bad_value", "value": "nan", "tol": 0.01},
                {"id": "synthetic.bad.tol", "label": "synthetic_bad_tol", "value": 1.0, "tol": -1.0},
                {
                    "id": HOSTILE_CANARIES[2],
                    "label": HOSTILE_CANARIES[5],
                    "value": 1.0,
                    "tol": 0.01,
                    "match_key": HOSTILE_CANARIES[3],
                    "allowed_aliases": [HOSTILE_CANARIES[4], "synthetic_safe_alias"],
                },
            ],
        }
    )
    check("invalid fixture lecture fallback", invalid["lecture_id"] == "synthetic_fixture", invalid["lecture_id"])
    check("invalid fixture source unknown", invalid["source_quality"] == "unknown")
    check("invalid values dropped/degraded", len(invalid["facts"]) == 1, str(invalid["facts"]))
    check("invalid fixture warnings closed", all(w in FIXTURE_WARNINGS for w in invalid["warnings"]))
    assert_no_canary("invalid fixture", invalid)

    capped = normalize_quality_safety_canonical_fixture(canonical(facts=[{"label": f"synthetic_{i}", "value": i, "tol": 0.1} for i in range(3)]), max_items=2)
    check("max_items caps facts", len(capped["facts"]) == 2)
    check("max_items warning fixture", "max_items_reached" in capped["warnings"])
    first = normalize_quality_safety_canonical_fixture(raw)
    second = normalize_quality_safety_canonical_fixture(raw)
    check("fixture normalization deterministic", serialized(first) == serialized(second))


def test_exact_fallback_match() -> None:
    result = match_quality_safety_canonical_facts(sheet_of(numeric_fact(value=0.205)), canonical())
    report = result["report"]
    check("within tolerance passes", report["status"] == "passed", str(report["status"]))
    check("within tolerance matched count", report["summary"]["matched_fact_count"] == 1)
    verified_fact = result["fact_sheet"]["concepts"][0]["facts"][0]
    check("fact updated canonical provenance", verified_fact["provenance"] == "canonical_fixture")
    check("fact updated verified", verified_fact["verification_status"] == "verified")
    assert_report_shape("within tolerance", report)

    mismatch = match_quality_safety_canonical_facts(sheet_of(numeric_fact(value=0.5)), canonical())
    mismatch_report = mismatch["report"]
    check("outside tolerance fails", mismatch_report["status"] == "failed")
    check("outside tolerance blocking", mismatch_report["summary"]["blocking_failure_count"] == 1)
    check("outside tolerance warning", "canonical_value_mismatch" in mismatch_report["warnings"])
    assert_report_shape("outside tolerance", mismatch_report)


def test_alias_match() -> None:
    alias_fixture = canonical(
        facts=[
            {
                "id": "synthetic.canonical.alias",
                "label": "synthetic_primary_label",
                "value": 0.2,
                "tol": 0.01,
                "type": "numeric",
                "allowed_aliases": ["synthetic_alias_label", HOSTILE_CANARIES[0]],
            }
        ]
    )
    alias_result = match_quality_safety_canonical_facts(
        sheet_of(numeric_fact(label="synthetic_alias_label", value=0.2)),
        alias_fixture,
    )
    check("listed alias matches", alias_result["report"]["status"] == "passed", str(alias_result["report"]))
    assert_no_canary("alias result", alias_result)

    unlisted = match_quality_safety_canonical_facts(
        sheet_of(numeric_fact(label="synthetic_unlisted_alias", value=0.2)),
        alias_fixture,
    )
    check("unlisted alias does not match", unlisted["report"]["status"] == "warning")
    check("unlisted alias warning", "canonical_fact_missing" in unlisted["report"]["warnings"])

    normalized = normalize_quality_safety_canonical_fixture(alias_fixture)
    aliases = normalized["facts"][0]["allowed_aliases"]
    check("unsafe alias dropped", all("fake_private" not in alias for alias in aliases), str(aliases))


def test_recompute_priority() -> None:
    passed_fact = numeric_fact(
        fact_id="synthetic.passed",
        label="synthetic_label",
        value=0.125,
        provenance="computed",
        verification_status="verified",
        computation={"method": "total_error", "inputs": {"misclassified_weight": 0.125}, "result": 0.125},
    )
    passed_sheet = normalize_quality_safety_fact_sheet(sheet_of(passed_fact))
    recomputed = verify_quality_safety_fact_sheet(passed_sheet)
    cannot_override = match_quality_safety_canonical_facts(
        recomputed["fact_sheet"],
        canonical(facts=[{"id": "synthetic.override", "label": "synthetic_label", "value": 0.9, "tol": 0.01}]),
        recompute_report=recomputed["report"],
    )
    check("recompute verified skips canonical", first_check(cannot_override["report"])["check_id"] == "canonical_fixture_skipped_by_recompute_verified")
    check("canonical cannot override recompute pass", cannot_override["fact_sheet"]["concepts"][0]["facts"][0]["value"] == 0.125)

    failed_fact = dict(passed_fact, id="synthetic.failed", value=0.9)
    failed_recomputed = verify_quality_safety_fact_sheet(normalize_quality_safety_fact_sheet(sheet_of(failed_fact)))
    failed_skipped = match_quality_safety_canonical_facts(
        failed_recomputed["fact_sheet"],
        canonical(facts=[{"id": "synthetic.hide", "label": "synthetic_label", "value": 0.9, "tol": 0.01}]),
        recompute_report=failed_recomputed["report"],
    )
    check("recompute failed skips canonical", first_check(failed_skipped["report"])["check_id"] == "canonical_fixture_skipped_by_recompute_failed")
    check("canonical does not hide recompute failure", failed_skipped["report"]["summary"]["blocking_failure_count"] == 0)

    missing_compute = verify_quality_safety_fact_sheet(normalize_quality_safety_fact_sheet(sheet_of(numeric_fact(value=0.2))))
    fallback = match_quality_safety_canonical_facts(
        missing_compute["fact_sheet"],
        canonical(),
        recompute_report=missing_compute["report"],
    )
    check("computation missing may fallback", fallback["report"]["status"] == "passed", str(fallback["report"]))

    unsupported = verify_quality_safety_fact_sheet(
        normalize_quality_safety_fact_sheet(
            sheet_of(
                numeric_fact(
                    value=0.2,
                    computation={"method": "manual", "inputs": {}, "result": 0.2},
                    provenance="computed",
                    verification_status="verified",
                )
            )
        )
    )
    unsupported_fallback = match_quality_safety_canonical_facts(
        unsupported["fact_sheet"],
        canonical(),
        recompute_report=unsupported["report"],
    )
    check("unsupported method may fallback", unsupported_fallback["report"]["status"] == "passed")


def test_lecture_mismatch() -> None:
    report = build_quality_safety_canonical_match_report(
        sheet_of(numeric_fact(), lecture_id="synthetic_fixture"),
        canonical(lecture_id="synthetic_other_fixture"),
    )
    check("lecture mismatch skipped", report["status"] == "skipped")
    check("lecture mismatch warning closed", report["warnings"] == ["canonical_lecture_id_mismatch"], str(report["warnings"]))
    check("lecture mismatch no checks", report["checks"] == [])
    assert_report_shape("lecture mismatch", report)


def test_type_behavior() -> None:
    mixed_sheet = sheet_of(
        numeric_fact(fact_id="synthetic.numeric", label="synthetic_numeric", value=0.2),
        typed_fact(fact_id="synthetic.string", label="synthetic_string", value="synthetic_value", fact_type="string"),
        typed_fact(fact_id="synthetic.category", label="synthetic_category", value="synthetic_a", fact_type="categorical"),
        typed_fact(fact_id="synthetic.table", label="synthetic_table", value={"synthetic_key": "synthetic_value"}, fact_type="table"),
    )
    mixed_fixture = canonical(
        facts=[
            {"id": "synthetic.numeric", "label": "synthetic_numeric", "value": 0.2, "tol": 0.01, "type": "numeric"},
            {"id": "synthetic.string", "label": "synthetic_string", "value": "synthetic_value", "type": "string"},
            {"id": "synthetic.category", "label": "synthetic_category", "value": "synthetic_a", "type": "categorical"},
        ]
    )
    result = match_quality_safety_canonical_facts(mixed_sheet, mixed_fixture)
    statuses = [entry["status"] for entry in result["report"]["checks"]]
    check("numeric matches numeric", result["report"]["summary"]["matched_fact_count"] == 1, str(result["report"]["summary"]))
    check("string/categorical/table not numeric", statuses.count("not_applicable") == 3, str(statuses))
    check("type behavior not failed", result["report"]["status"] == "warning", str(result["report"]["status"]))
    assert_report_shape("type behavior", result["report"])


def test_report_shape_and_status() -> None:
    unmatched = build_quality_safety_canonical_match_report(
        sheet_of(numeric_fact(label="synthetic_missing", value=0.2)),
        canonical(),
    )
    check("unmatched warning", unmatched["status"] == "warning")
    check("unmatched count", unmatched["summary"]["unmatched_fact_count"] == 1)
    check("unmatched not blocking", unmatched["summary"]["blocking_failure_count"] == 0)
    assert_report_shape("unmatched", unmatched)

    failed = build_quality_safety_canonical_match_report(sheet_of(numeric_fact(value=0.8)), canonical())
    check("failed on mismatch", failed["status"] == "failed")
    check("mismatch count increments", failed["summary"]["mismatch_count"] == 1)
    check("blocking count increments", failed["summary"]["blocking_failure_count"] == 1)

    passed = build_quality_safety_canonical_match_report(sheet_of(numeric_fact(value=0.2)), canonical())
    check("passed when all eligible pass", passed["status"] == "passed")
    check("all summary counts non-negative", all(v >= 0 for v in passed["summary"].values()))


def test_slice110_and_111_integration() -> None:
    raw_sheet = sheet_of(
        numeric_fact(
            fact_id="synthetic.recomputed",
            label="synthetic_recomputed",
            value=0.125,
            provenance="computed",
            verification_status="verified",
            computation={"method": "total_error", "inputs": {"misclassified_weight": 0.125}, "result": 0.125},
        ),
        numeric_fact(fact_id="synthetic.fallback", label="synthetic_fallback", value=0.2),
    )
    normalized = normalize_quality_safety_fact_sheet(raw_sheet)
    recomputed = verify_quality_safety_fact_sheet(normalized)
    canonical_fixture = canonical(
        facts=[
            {"id": "synthetic.recomputed", "label": "synthetic_recomputed", "value": 0.9, "tol": 0.01},
            {"id": "synthetic.fallback", "label": "synthetic_fallback", "value": 0.2, "tol": 0.01},
        ]
    )
    result = match_quality_safety_canonical_facts(
        recomputed["fact_sheet"],
        canonical_fixture,
        recompute_report=recomputed["report"],
    )
    check("integration skipped recompute first", result["report"]["summary"]["skipped_by_recompute_count"] == 1)
    check("integration canonical second matched", result["report"]["summary"]["matched_fact_count"] == 1)
    facts = result["fact_sheet"]["concepts"][0]["facts"]
    check("integration recompute fact still computed", facts[0]["provenance"] == "computed", str(facts[0]))
    check("integration fallback fact canonical", facts[1]["provenance"] == "canonical_fixture", str(facts[1]))


def test_seed_fixture_integration() -> None:
    fixture_dir = REPO / "test_scripts" / "fixtures" / "quality_safety"
    clean = json.loads((fixture_dir / "clean_neural_networks_synthetic.json").read_text(encoding="utf-8"))
    ambiguous = json.loads((fixture_dir / "ambiguous_ensemble_synthetic.json").read_text(encoding="utf-8"))

    def from_seed(seed: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": 1,
            "kind": "quality_safety_canonical_fixture",
            "lecture_id": seed["lecture_id"],
            "source_quality": seed["source_quality"],
            "facts": [
                {
                    "id": f"synthetic.seed.{item['label']}",
                    "label": item["label"],
                    "value": item["value"],
                    "tol": item["tol"],
                    "type": "numeric",
                    "match_key": f"{seed['lecture_id']}::{item['label']}",
                }
                for item in seed["ground_truth_numerics"]
            ],
        }

    clean_label = clean["ground_truth_numerics"][0]["label"]
    clean_value = clean["ground_truth_numerics"][0]["value"]
    clean_result = match_quality_safety_canonical_facts(
        sheet_of(
            numeric_fact(label=clean_label, value=clean_value),
            lecture_id=clean["lecture_id"],
        ),
        from_seed(clean),
    )
    check("clean seed fallback match", clean_result["report"]["status"] == "passed", str(clean_result["report"]))

    ambiguous_label = ambiguous["ground_truth_numerics"][0]["label"]
    ambiguous_result = match_quality_safety_canonical_facts(
        sheet_of(
            numeric_fact(label=ambiguous_label, value=0.999),
            lecture_id=ambiguous["lecture_id"],
        ),
        from_seed(ambiguous),
    )
    check("ambiguous seed mismatch failed", ambiguous_result["report"]["status"] == "failed")
    check("ambiguous seed mismatch blocking", ambiguous_result["report"]["summary"]["blocking_failure_count"] == 1)
    assert_no_canary("seed fixture canonical", {"clean": clean_result, "ambiguous": ambiguous_result})


def test_no_leak_sweep() -> None:
    hostile_sheet = {
        "lecture_id": HOSTILE_CANARIES[0],
        "source_quality": "private_cloud",
        "concepts": [
            {
                "concept": HOSTILE_CANARIES[11],
                "facts": [
                    {
                        "id": HOSTILE_CANARIES[2],
                        "concept": HOSTILE_CANARIES[5],
                        "label": HOSTILE_CANARIES[6],
                        "value": 0.2,
                        "type": "numeric",
                        "provenance": "unverified",
                        "verification_status": "unverified",
                        "confidence": "low",
                        "source_ref": HOSTILE_CANARIES[4],
                        "match_key": HOSTILE_CANARIES[8],
                    }
                ],
            }
        ],
    }
    hostile_fixture = {
        "lecture_id": HOSTILE_CANARIES[1],
        "source_quality": "private_cloud",
        "facts": [
            {
                "id": HOSTILE_CANARIES[3],
                "label": HOSTILE_CANARIES[7],
                "value": 0.2,
                "tol": 0.01,
                "type": "numeric",
                "match_key": HOSTILE_CANARIES[8],
                "allowed_aliases": [HOSTILE_CANARIES[9], HOSTILE_CANARIES[10], HOSTILE_CANARIES[12]],
            }
        ],
    }
    result = match_quality_safety_canonical_facts(hostile_sheet, hostile_fixture)
    assert_no_canary("hostile verified output", result["fact_sheet"])
    assert_no_canary("hostile report", result["report"])
    normalized_fixture = normalize_quality_safety_canonical_fixture(hostile_fixture)
    assert_no_canary("hostile canonical fixture", normalized_fixture)


def test_import_hygiene() -> None:
    source_path = REPO / "pipeline" / "quality_safety_canonical_matcher.py"
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
    test_canonical_fixture_normalization()
    test_exact_fallback_match()
    test_alias_match()
    test_recompute_priority()
    test_lecture_mismatch()
    test_type_behavior()
    test_report_shape_and_status()
    test_slice110_and_111_integration()
    test_seed_fixture_integration()
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_canonical_matcher: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
