#!/usr/bin/env python3
"""Tests for Slice 110 Quality Safety fact-sheet schema v1.

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

from pipeline.quality_safety_fact_sheet import (  # noqa: E402
    build_empty_quality_safety_fact_sheet,
    normalize_quality_safety_fact_record,
    normalize_quality_safety_fact_sheet,
    validate_quality_safety_fact_sheet,
)

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/private/source-deck.pdf",
    "C:\\private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_qualityfactsheet1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_FACT_SHEET_MARKER",
    "TABLE_TEXT_PRIVATE_FACT_SHEET_MARKER",
    "CAPTION_PRIVATE_FACT_SHEET_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_FACT_SHEET_MARKER",
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
FACT_WARNINGS = {
    "malformed_fact_degraded",
    "invalid_fact_id",
    "invalid_fact_type",
    "invalid_provenance",
    "invalid_verification_status",
    "invalid_confidence",
    "invalid_numeric_value",
    "invalid_source_ref",
    "invalid_computation",
    "invalid_computation_method",
    "unsafe_string_sanitized",
    "max_items_reached",
}
SHEET_WARNINGS = {
    "malformed_fact_sheet_degraded",
    "invalid_lecture_id",
    "invalid_source_quality",
    "invalid_concept_dropped",
    "invalid_teaching_note_dropped",
    "invalid_worked_example_dropped",
    "max_items_reached",
    "unsafe_string_sanitized",
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
    found = [canary for canary in HOSTILE_CANARIES if canary in blob]
    extra = [
        marker
        for marker in (
            "/home/private",
            "C:\\private",
            "https://",
            "Authorization",
            "Bearer",
            "sk_qualityfactsheet",
            "data:image",
            "base64",
            "OCR_PRIVATE",
            "TABLE_TEXT_PRIVATE",
            "CAPTION_PRIVATE",
            "PROVIDER_PAYLOAD_PRIVATE",
            "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
            "EVIDENCE_QUOTE_PRIVATE_MARKER",
            "private_formula_marker",
        )
        if marker in blob
    ]
    check(f"{name}: no hostile canary", not found and not extra, str(found or extra))


def assert_closed_warnings(name: str, sheet: dict[str, Any]) -> None:
    warnings = sheet.get("warnings", [])
    fact_warnings: list[str] = []
    for concept in sheet.get("concepts", []):
        for fact in concept.get("facts", []):
            fact_warnings.extend(fact.get("warnings", []))
    check(f"{name}: sheet warnings closed", all(item in SHEET_WARNINGS for item in warnings), str(warnings))
    check(f"{name}: fact warnings closed", all(item in FACT_WARNINGS for item in fact_warnings), str(fact_warnings))


def valid_numeric_sheet() -> dict[str, Any]:
    return {
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": "Synthetic Concept",
                "facts": [
                    {
                        "id": "synthetic.fact.id",
                        "concept": "Synthetic Concept",
                        "label": "synthetic_label",
                        "value": 0.20,
                        "type": "numeric",
                        "provenance": "computed",
                        "verification_status": "verified",
                        "confidence": "high",
                        "source_ref": "source_page_1",
                        "computation": {
                            "method": "weighted_gini",
                            "inputs": {"synthetic_count_a": 3, "synthetic_count_b": 5},
                            "result": 0.20,
                        },
                    }
                ],
                "teaching_notes": ["Synthetic note"],
                "worked_examples": [
                    {"id": "synthetic_example_1", "trace_key": "trace_key_1", "answer": "Synthetic answer"}
                ],
            }
        ],
    }


def test_empty_default_behavior() -> None:
    empty = build_empty_quality_safety_fact_sheet()
    check("empty kind", empty["kind"] == "quality_safety_fact_sheet")
    check("empty completed", empty["status"] == "completed")
    check("empty zero counts", empty["summary"]["fact_count"] == 0 and empty["summary"]["concept_count"] == 0)
    missing = normalize_quality_safety_fact_sheet(None)
    check("missing input never raises", missing["status"] == "skipped")
    malformed = normalize_quality_safety_fact_sheet(["not", "a", "dict"])
    check("malformed input degrades safely", "malformed_fact_sheet_degraded" in malformed["warnings"])
    alias = validate_quality_safety_fact_sheet({})
    check("validate alias returns sheet", alias["kind"] == "quality_safety_fact_sheet")
    assert_closed_warnings("empty/default", malformed)


def test_valid_numeric_computed_fact() -> None:
    sheet = normalize_quality_safety_fact_sheet(valid_numeric_sheet())
    fact = sheet["concepts"][0]["facts"][0]
    check("numeric computed completed", sheet["status"] == "completed", str(sheet))
    check("numeric fact verified", fact["type"] == "numeric" and fact["verification_status"] == "verified")
    check("computed provenance preserved", fact["provenance"] == "computed")
    check("confidence high preserved", fact["confidence"] == "high")
    check("weighted_gini method preserved", fact["computation"]["method"] == "weighted_gini")
    check("computation inputs preserved", fact["computation"]["inputs"] == {"synthetic_count_a": 3, "synthetic_count_b": 5})
    check("computation result preserved", fact["computation"]["result"] == 0.2)
    check("summary numeric verified counts", sheet["summary"]["numeric_fact_count"] == 1 and sheet["summary"]["verified_fact_count"] == 1)
    assert_no_canary("valid numeric", sheet)


def test_valid_unverified_fact() -> None:
    data = valid_numeric_sheet()
    fact = data["concepts"][0]["facts"][0]
    fact["id"] = "synthetic.unverified.fact"
    fact["provenance"] = "unverified"
    fact["verification_status"] = "unverified"
    fact["confidence"] = "medium"
    fact["value"] = 0.75
    sheet = normalize_quality_safety_fact_sheet(data)
    normalized = sheet["concepts"][0]["facts"][0]
    check("unverified provenance preserved", normalized["provenance"] == "unverified")
    check("unverified status preserved", normalized["verification_status"] == "unverified")
    check("numeric value does not verify", sheet["summary"]["verified_fact_count"] == 0)
    check("unverified count increments", sheet["summary"]["unverified_fact_count"] == 1)


def test_valid_canonical_fact() -> None:
    data = valid_numeric_sheet()
    fact = data["concepts"][0]["facts"][0]
    fact["id"] = "synthetic.canonical.fact"
    fact["provenance"] = "canonical_fixture"
    fact["computation"] = {"method": "manual", "inputs": {}, "result": 0.2}
    sheet = normalize_quality_safety_fact_sheet(data)
    normalized = sheet["concepts"][0]["facts"][0]
    check("canonical provenance preserved", normalized["provenance"] == "canonical_fixture")
    check("canonical distinct from computed", normalized["provenance"] != "computed")
    check("canonical verified preserved", normalized["verification_status"] == "verified")
    check("no matcher fields", "match" not in serialized(sheet).lower())


def test_failed_fact() -> None:
    data = valid_numeric_sheet()
    fact = data["concepts"][0]["facts"][0]
    fact["id"] = "synthetic.failed.fact"
    fact["verification_status"] = "failed"
    fact["confidence"] = "low"
    sheet = normalize_quality_safety_fact_sheet(data)
    normalized = sheet["concepts"][0]["facts"][0]
    check("failed status preserved", normalized["verification_status"] == "failed")
    check("failed count increments", sheet["summary"]["failed_fact_count"] == 1)
    check("no repair fields", "repair" not in serialized(sheet).lower() and "blocking" not in serialized(sheet).lower())


def test_enum_hardening() -> None:
    record = normalize_quality_safety_fact_record(
        {
            "id": "Synthetic Unknown Fact",
            "concept": "Synthetic Concept",
            "label": "synthetic_label",
            "value": math.inf,
            "type": "mystery",
            "provenance": "model_guess",
            "verification_status": "certain",
            "confidence": "absolute",
            "source_ref": "page_1",
            "computation": {"method": "new_magic", "inputs": {"safe_input": 1}, "result": 1},
        }
    )
    check("unknown type fallback", record["type"] == "string")
    check("unknown provenance fallback", record["provenance"] == "unverified")
    check("unknown status fallback", record["verification_status"] == "unverified")
    check("unknown confidence fallback", record["confidence"] == "low")
    check("unknown method fallback", record["computation"]["method"] == "unknown")
    check("enum warnings closed", set(record["warnings"]).issubset(FACT_WARNINGS), str(record["warnings"]))


def test_id_source_ref_hardening() -> None:
    hostile_refs = [
        "/home/private/source-deck.pdf",
        "../private/source",
        "https://private.invalid/source",
        "/tmp/app.sock",
        "private-source.pdf",
        "data:image/png;base64," + ("A" * 100),
        "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo" * 4,
    ]
    facts = [
        {
            "id": ref,
            "concept": "Synthetic Concept",
            "label": "synthetic_label",
            "value": 1.0,
            "type": "numeric",
            "provenance": "computed",
            "verification_status": "verified",
            "confidence": "high",
            "source_ref": ref,
        }
        for ref in hostile_refs
    ]
    sheet = normalize_quality_safety_fact_sheet(
        {"lecture_id": "synthetic_fixture", "source_quality": "synthetic", "concepts": [{"concept": "Synthetic", "facts": facts}]}
    )
    normalized = sheet["concepts"][0]["facts"]
    check("hostile ids fallback deterministic", [fact["id"] for fact in normalized] == [f"fact_{idx:04d}" for idx in range(1, len(hostile_refs) + 1)])
    check("hostile source refs removed", all(fact["source_ref"] is None for fact in normalized))
    assert_no_canary("id/source_ref hardening", sheet)
    assert_closed_warnings("id/source_ref hardening", sheet)


def test_string_hygiene() -> None:
    data = {
        "lecture_id": "/home/private/source-deck.pdf",
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": "OCR_PRIVATE_FACT_SHEET_MARKER",
                "facts": [
                    {
                        "id": "safe.fact",
                        "concept": "TABLE_TEXT_PRIVATE_FACT_SHEET_MARKER",
                        "label": "CAPTION_PRIVATE_FACT_SHEET_MARKER",
                        "value": "source text private marker",
                        "type": "string",
                        "provenance": "unverified",
                        "verification_status": "unverified",
                        "confidence": "low",
                    },
                    {
                        "id": "safe.table",
                        "concept": "Synthetic",
                        "label": "synthetic_table",
                        "value": [{"cell": "E=mc^2_private_formula_marker"}],
                        "type": "table",
                        "provenance": "extracted_high",
                        "verification_status": "unverified",
                        "confidence": "low",
                    },
                ],
                "teaching_notes": ["https://private.invalid/source", "Synthetic safe note"],
                "worked_examples": [
                    {"id": "/home/private/example", "trace_key": "trace_key_1", "answer": "PROVIDER_PAYLOAD_PRIVATE_FACT_SHEET_MARKER"},
                    {"id": "synthetic_example", "trace_key": "trace_key_2", "answer": "Synthetic safe answer"},
                ],
            }
        ],
    }
    sheet = normalize_quality_safety_fact_sheet(data)
    concept = sheet["concepts"][0]
    check("hostile concept placeholder", concept["concept"] == "Synthetic Concept")
    check("unsafe note dropped", concept["teaching_notes"] == ["Synthetic safe note"])
    check("unsafe example dropped", len(concept["worked_examples"]) == 1)
    assert_no_canary("string hygiene", sheet)
    assert_closed_warnings("string hygiene", sheet)


def test_bounds_max_items() -> None:
    data = {
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": f"Synthetic Concept {concept_idx}",
                "facts": [
                    {
                        "concept": f"Synthetic Concept {concept_idx}",
                        "label": f"synthetic_label_{fact_idx}",
                        "value": fact_idx,
                        "type": "numeric",
                        "provenance": "computed",
                        "verification_status": "verified",
                        "confidence": "high",
                    }
                    for fact_idx in range(4)
                ],
                "teaching_notes": [f"Synthetic note {idx}" for idx in range(4)],
                "worked_examples": [
                    {"answer": f"Synthetic answer {idx}", "trace_key": f"trace_{idx}"} for idx in range(4)
                ],
            }
            for concept_idx in range(4)
        ],
    }
    sheet = normalize_quality_safety_fact_sheet(data, max_items=2)
    check("max_items partial", sheet["status"] == "partial")
    check("concepts capped", len(sheet["concepts"]) == 2)
    check("facts capped", all(len(concept["facts"]) == 2 for concept in sheet["concepts"]))
    check("notes capped", all(len(concept["teaching_notes"]) == 2 for concept in sheet["concepts"]))
    check("examples capped", all(len(concept["worked_examples"]) == 2 for concept in sheet["concepts"]))
    check("max warning", "max_items_reached" in sheet["warnings"])
    check("deterministic fallback ids", sheet["concepts"][0]["facts"][0]["id"] == "fact_0001")


def test_deterministic_serialization() -> None:
    data = valid_numeric_sheet()
    first = normalize_quality_safety_fact_sheet(data)
    second = normalize_quality_safety_fact_sheet(data)
    check("deterministic serialization", serialized(first) == serialized(second))


def test_seed_fixture_integration() -> None:
    fixture_dir = REPO / "test_scripts" / "fixtures" / "quality_safety"
    clean = json.loads((fixture_dir / "clean_neural_networks_synthetic.json").read_text(encoding="utf-8"))
    ambiguous = json.loads((fixture_dir / "ambiguous_ensemble_synthetic.json").read_text(encoding="utf-8"))
    concepts = []
    for fixture in (clean, ambiguous):
        concepts.append(
            {
                "concept": fixture["title"],
                "facts": [
                    {
                        "id": f"{fixture['lecture_id']}.{target['label']}",
                        "concept": fixture["title"],
                        "label": target["label"],
                        "value": target["value"],
                        "type": "numeric",
                        "provenance": "canonical_fixture",
                        "verification_status": "verified",
                        "confidence": "high",
                        "source_ref": "source_page_1",
                        "computation": {"method": "manual", "inputs": {"synthetic_target_count": 1}, "result": target["value"]},
                    }
                    for target in fixture["ground_truth_numerics"]
                ],
            }
        )
    sheet = normalize_quality_safety_fact_sheet(
        {"lecture_id": "synthetic_fixture", "source_quality": "synthetic", "concepts": concepts}
    )
    check("seed fixture facts normalize", sheet["summary"]["fact_count"] == 5)
    check("seed fixture verified normalize", sheet["summary"]["verified_fact_count"] == 5)
    assert_no_canary("seed fixture integration", sheet)


def test_no_leak_sweep() -> None:
    data = {
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
                        "value": HOSTILE_CANARIES[11],
                        "type": "string",
                        "provenance": "provider_payload",
                        "verification_status": "certain",
                        "confidence": "secret",
                        "source_ref": HOSTILE_CANARIES[4],
                        "computation": {
                            "method": HOSTILE_CANARIES[8],
                            "inputs": {HOSTILE_CANARIES[9]: HOSTILE_CANARIES[10]},
                            "result": math.inf,
                        },
                    }
                ],
                "teaching_notes": list(HOSTILE_CANARIES),
                "worked_examples": [{"id": HOSTILE_CANARIES[0], "trace_key": HOSTILE_CANARIES[2], "answer": HOSTILE_CANARIES[3]}],
            }
        ],
    }
    sheet = normalize_quality_safety_fact_sheet(data)
    assert_no_canary("no-leak sweep", sheet)
    assert_closed_warnings("no-leak sweep", sheet)


def test_import_hygiene() -> None:
    source_path = REPO / "pipeline" / "quality_safety_fact_sheet.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    bad = [name for name in imports for part in FORBIDDEN_IMPORT_PARTS if part in name.lower()]
    check("import hygiene no forbidden imports", bad == [], str(bad))
    check("stdlib imports only", sorted(imports) == ["__future__", "math", "re", "typing"], str(imports))


def run() -> int:
    test_empty_default_behavior()
    test_valid_numeric_computed_fact()
    test_valid_unverified_fact()
    test_valid_canonical_fact()
    test_failed_fact()
    test_enum_hardening()
    test_id_source_ref_hardening()
    test_string_hygiene()
    test_bounds_max_items()
    test_deterministic_serialization()
    test_seed_fixture_integration()
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_fact_sheet: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
