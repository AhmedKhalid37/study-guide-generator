#!/usr/bin/env python3
"""Tests for Slice 133 structured numeric candidate adapter v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. Hostile canaries are
synthetic markers used only to prove forbidden content is stripped.

Run:  python test_scripts/test_quality_safety_structured_numeric_candidate_adapter.py
"""
from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_fact_sheet_producer import (  # noqa: E402
    run_quality_safety_fact_sheet_producer,
)
from pipeline.quality_safety_job_artifact import (  # noqa: E402
    build_quality_safety_job_artifact_payload,
)
from pipeline.quality_safety_numeric_extraction_mapper import (  # noqa: E402
    build_quality_safety_numeric_extraction_bundle,
    map_numeric_extraction_bundle_to_fact_sheet_input,
)
from pipeline.quality_safety_recompute_verifier import (  # noqa: E402
    build_quality_safety_recompute_report,
)
from pipeline.quality_safety_safe_numeric_extractor import (  # noqa: E402
    extract_quality_safety_numeric_records_from_candidates,
)
from pipeline.quality_safety_structured_numeric_candidate_adapter import (  # noqa: E402
    adapt_structured_numeric_candidates_to_safe_candidates,
    build_empty_structured_numeric_candidate_adapter_result,
    normalize_structured_numeric_candidate_artifact,
)

PASS = 0
FAIL = 0

MODULE_PATH = REPO / "pipeline" / "quality_safety_structured_numeric_candidate_adapter.py"

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_structured1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_STRUCTURED_MARKER",
    "TABLE_TEXT_PRIVATE_STRUCTURED_MARKER",
    "CAPTION_PRIVATE_STRUCTURED_MARKER",
    "PAGE_TEXT_PRIVATE_STRUCTURED_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_STRUCTURED_MARKER",
    "RAW_ARTIFACT_JSON_PRIVATE_STRUCTURED_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_STRUCTURED_MARKER",
    "source text private marker",
    "E=mc^2_private_formula_marker",
    "ZZSYNTH_STRUCTURED_PRIVATE_MARKER_ONLY",
)
FORBIDDEN_MARKERS = (
    "/home/fake_private",
    "C:\\fake_private",
    "https://",
    "Authorization",
    "Bearer",
    "sk_structured",
    "data:image",
    "base64",
    "OCR_PRIVATE",
    "TABLE_TEXT_PRIVATE",
    "CAPTION_PRIVATE",
    "PAGE_TEXT_PRIVATE",
    "PROVIDER_PAYLOAD_PRIVATE",
    "RAW_ARTIFACT_JSON_PRIVATE",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_STRUCTURED_MARKER",
    "source text private marker",
    "private_formula_marker",
    "ZZSYNTH_STRUCTURED_PRIVATE_MARKER_ONLY",
)

PAYLOAD_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
SOURCE_QUALITIES = frozenset({"synthetic", "structured_numeric_artifact", "operator_approved", "unknown"})
PAYLOAD_WARNINGS = frozenset(
    {
        "component_missing",
        "empty_structured_numeric_artifact",
        "malformed_structured_numeric_artifact_input",
        "unsupported_artifact_kind",
        "missing_candidates",
        "invalid_candidate_dropped",
        "max_items_reached",
    }
)
CANDIDATE_WARNINGS = frozenset(
    {
        "forbidden_field_stripped",
        "invalid_id",
        "invalid_concept_id",
        "invalid_label",
        "invalid_unit",
        "invalid_provenance",
        "invalid_confidence",
        "invalid_source_ref",
        "invalid_page_ref",
        "invalid_numeric_value",
        "invalid_tolerance",
        "unsupported_method",
        "malformed_computation",
        "unsafe_string_sanitized",
    }
)
CANDIDATE_FIELDS = frozenset(
    {
        "id",
        "concept_id",
        "label",
        "fact_type",
        "value",
        "unit",
        "provenance",
        "confidence",
        "source_ref",
        "page_ref",
        "computation",
        "tolerance",
        "warnings",
    }
)
SUMMARY_KEYS = frozenset(
    {
        "input_candidate_count",
        "output_candidate_count",
        "supported_method_count",
        "unsupported_method_count",
        "dropped_candidate_count",
    }
)

SUPPORTED_METHOD_FIXTURES: dict[str, tuple[dict[str, Any], float]] = {
    "weighted_gini": ({"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]}, 0.2),
    "total_error": ({"misclassified_weight": 0.3}, 0.3),
    "amount_of_say": ({"total_error": 0.25}, 0.5493061443340549),
    "softmax": ({"values": [1.0, 2.0, 3.0], "index": 2}, 0.6652409557748218),
    "cross_entropy": ({"probability": 0.5}, 0.6931471805599453),
    "forward_pass": (
        {"inputs": {"x1": 1.0, "x2": 2.0}, "weights": {"x1": 0.5, "x2": 0.5}, "bias": 0.0, "activation": "linear"},
        1.5,
    ),
}

ALLOWED_IMPORTS = {"__future__", "math", "re", "typing"}
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
    "chandra",
    "mistral",
    "gemini",
    "socket",
    "subprocess",
    "os",
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


def assert_no_canary(name: str, node: Any) -> None:
    blob = serialized(node)
    found = [marker for marker in FORBIDDEN_MARKERS if marker in blob]
    found += [canary for canary in HOSTILE_CANARIES if canary in blob]
    check(f"{name}: no hostile canary", not found, str(found))


def structured_artifact(candidates: list[Any], *, source_quality: str = "structured_numeric_artifact") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_structured_numeric_candidates",
        "status": "ok",
        "source_quality": source_quality,
        "candidates": candidates,
        "summary": {"candidate_count": len(candidates)},
        "warnings": [],
        "unknown_top_level": "ZZSYNTH_STRUCTURED_PRIVATE_MARKER_ONLY",
    }


def structured_candidate(
    *,
    cand_id: str = "qs_struct_clean",
    concept_id: str = "qs_struct_concept",
    label: str = "synthetic_score",
    method: str,
    inputs: dict[str, Any],
    value: float,
    tolerance: float = 0.02,
    provenance: str = "computed",
    confidence: str = "medium",
) -> dict[str, Any]:
    return {
        "id": cand_id,
        "concept_id": concept_id,
        "label": label,
        "fact_type": "numeric",
        "value": value,
        "unit": "ratio",
        "provenance": provenance,
        "confidence": confidence,
        "source_ref": "source_page_1",
        "page_ref": "page_1",
        "computation": {"method": method, "inputs": inputs},
        "tolerance": tolerance,
        "warnings": [],
    }


def assert_adapter_payload_shape(name: str, payload: dict[str, Any]) -> None:
    check(f"{name}: kind", payload.get("kind") == "quality_safety_safe_numeric_candidates")
    check(f"{name}: version 1", payload.get("version") == 1)
    check(f"{name}: status closed", payload.get("status") in PAYLOAD_STATUSES, str(payload.get("status")))
    check(
        f"{name}: source_quality closed",
        payload.get("source_quality") in SOURCE_QUALITIES,
        str(payload.get("source_quality")),
    )
    summary = payload.get("summary", {})
    check(f"{name}: summary keys", set(summary) == SUMMARY_KEYS, str(set(summary)))
    check(
        f"{name}: summary non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()),
        str(summary),
    )
    check(
        f"{name}: payload warnings closed",
        all(w in PAYLOAD_WARNINGS for w in payload.get("warnings", [])),
        str(payload.get("warnings")),
    )
    for candidate in payload.get("candidates", []):
        check(f"{name}: candidate fields whitelisted", set(candidate).issubset(CANDIDATE_FIELDS), str(set(candidate)))
        check(f"{name}: candidate fact_type numeric", candidate.get("fact_type") == "numeric")
        check(
            f"{name}: candidate warnings closed",
            all(w in CANDIDATE_WARNINGS for w in candidate.get("warnings", [])),
            str(candidate.get("warnings")),
        )
    check(f"{name}: JSON-serializable", isinstance(serialized(payload), str))


def downstream_chain(adapter_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    extraction_payload = extract_quality_safety_numeric_records_from_candidates(adapter_payload.get("candidates"))
    bundle = build_quality_safety_numeric_extraction_bundle(extraction_payload.get("records"))
    fact_input = map_numeric_extraction_bundle_to_fact_sheet_input(bundle)
    produced = run_quality_safety_fact_sheet_producer(fact_input)
    report = build_quality_safety_recompute_report(produced.get("fact_sheet"))
    return extraction_payload, bundle, produced, report


def main() -> int:
    # --- 1. Empty / malformed / wrong-kind payloads degrade safely ------------
    empty = build_empty_structured_numeric_candidate_adapter_result()
    assert_adapter_payload_shape("empty explicit", empty)
    check("empty explicit: skipped", empty.get("status") == "skipped")
    check("empty explicit: component_missing", empty.get("warnings") == ["component_missing"], serialized(empty))

    malformed = adapt_structured_numeric_candidates_to_safe_candidates("not a dict")
    assert_adapter_payload_shape("malformed", malformed)
    check("malformed: skipped", malformed.get("status") == "skipped", serialized(malformed))
    check(
        "malformed: warning",
        "malformed_structured_numeric_artifact_input" in malformed.get("warnings", []),
        serialized(malformed),
    )

    wrong_kind = adapt_structured_numeric_candidates_to_safe_candidates({"kind": "wrong", "candidates": []})
    assert_adapter_payload_shape("wrong kind", wrong_kind)
    check("wrong kind: skipped", wrong_kind.get("status") == "skipped")
    check("wrong kind: unsupported warning", "unsupported_artifact_kind" in wrong_kind.get("warnings", []))

    missing_candidates = adapt_structured_numeric_candidates_to_safe_candidates(
        {"version": 1, "kind": "quality_safety_structured_numeric_candidates"}
    )
    assert_adapter_payload_shape("missing candidates", missing_candidates)
    check("missing candidates: warning", "missing_candidates" in missing_candidates.get("warnings", []))

    # --- 2. Valid weighted_gini adapts to the safe candidates wrapper ---------
    clean_candidate = structured_candidate(
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
    )
    clean_payload = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact([clean_candidate]))
    assert_adapter_payload_shape("clean weighted_gini", clean_payload)
    check("clean: status ok", clean_payload.get("status") == "ok", str(clean_payload.get("status")))
    check("clean: input count 1", clean_payload["summary"]["input_candidate_count"] == 1)
    check("clean: output count 1", clean_payload["summary"]["output_candidate_count"] == 1)
    check("clean: supported count 1", clean_payload["summary"]["supported_method_count"] == 1)
    check("clean: output wrapper candidates key", isinstance(clean_payload.get("candidates"), list))
    extraction_payload, bundle, produced, clean_report = downstream_chain(clean_payload)
    check("clean downstream: extractor ok", extraction_payload.get("status") == "ok", str(extraction_payload.get("status")))
    check("clean downstream: mapper ok", bundle.get("status") == "ok", str(bundle.get("status")))
    check("clean downstream: producer has fact sheet", isinstance(produced.get("fact_sheet"), dict))
    check("clean downstream: recompute passed", clean_report.get("status") == "passed", str(clean_report.get("status")))
    assert_no_canary("clean downstream report", clean_report)

    # --- 3. All supported methods survive with synthetic structured inputs ----
    all_candidates = [
        structured_candidate(
            cand_id=f"qs_struct_{method}",
            concept_id=f"qs_struct_concept_{method}",
            label=f"synthetic_{method}",
            method=method,
            inputs=inputs,
            value=value,
            tolerance=0.05,
        )
        for method, (inputs, value) in SUPPORTED_METHOD_FIXTURES.items()
    ]
    all_payload = normalize_structured_numeric_candidate_artifact(structured_artifact(all_candidates, source_quality="synthetic"))
    assert_adapter_payload_shape("all supported", all_payload)
    check(
        "all supported: count",
        all_payload["summary"]["supported_method_count"] == len(SUPPORTED_METHOD_FIXTURES),
        serialized(all_payload["summary"]),
    )
    _, _, _, all_report = downstream_chain(all_payload)
    check("all supported: recompute passed", all_report.get("status") == "passed", str(all_report.get("status")))
    check("all supported: no blocking", not all_report.get("blocking_failures"))

    # --- 4. Unsupported method stays unverified and does not falsely verify ---
    unsupported = structured_candidate(
        cand_id="qs_struct_legacy_unsupported",
        concept_id="qs_struct_legacy",
        label="synthetic_legacy_confused",
        method="entropy",
        inputs={"probability": 0.5},
        value=0.9,
    )
    unsupported_payload = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact([unsupported]))
    assert_adapter_payload_shape("unsupported", unsupported_payload)
    check("unsupported: counted", unsupported_payload["summary"]["unsupported_method_count"] == 1)
    unsupported_extraction, _, _, unsupported_report = downstream_chain(unsupported_payload)
    unsupported_record = unsupported_extraction["records"][0]
    check("unsupported downstream: computation demoted", unsupported_record.get("computation") is None)
    check("unsupported downstream: warning", "unsupported_method" in unsupported_record.get("warnings", []))
    check("unsupported downstream: no blocking", not unsupported_report.get("blocking_failures"))

    # --- 5. Invalid value / tolerance degrade without crashes -----------------
    invalid_value = structured_candidate(
        cand_id="qs_struct_bad_value",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=0.2,
    )
    invalid_value["value"] = "not_numeric"
    invalid_value_payload = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact([invalid_value]))
    assert_adapter_payload_shape("invalid value", invalid_value_payload)
    check("invalid value: candidate rejected", invalid_value_payload["summary"]["output_candidate_count"] == 0)
    check("invalid value: dropped", invalid_value_payload["summary"]["dropped_candidate_count"] == 1)
    check("invalid value: warning status", invalid_value_payload.get("status") == "warning")

    invalid_tolerance = structured_candidate(
        cand_id="qs_struct_bad_tol",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
        tolerance=99.0,
    )
    invalid_tolerance_payload = adapt_structured_numeric_candidates_to_safe_candidates(
        structured_artifact([invalid_tolerance])
    )
    bad_tol_candidate = invalid_tolerance_payload["candidates"][0]
    check("invalid tolerance: stripped to None", bad_tol_candidate.get("tolerance") is None)
    check("invalid tolerance: warning", "invalid_tolerance" in bad_tol_candidate.get("warnings", []))
    invalid_tol_extraction, _, _, _ = downstream_chain(invalid_tolerance_payload)
    check("invalid tolerance downstream: no invalid tolerance", invalid_tol_extraction["records"][0].get("tolerance") is None)

    # --- 6. Forbidden fields stripped from every downstream stage -------------
    tainted = structured_candidate(
        cand_id="qs_struct_tainted",
        concept_id="qs_struct_tainted_concept",
        label="synthetic_tainted",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
    )
    tainted.update(
        {
            "raw_text": "source text private marker",
            "source_text": "source text private marker",
            "guide_text": "ZZSYNTH_STRUCTURED_PRIVATE_MARKER_ONLY",
            "ocr_text": "OCR_PRIVATE_STRUCTURED_MARKER",
            "page_text": "PAGE_TEXT_PRIVATE_STRUCTURED_MARKER",
            "table_cells": ["TABLE_TEXT_PRIVATE_STRUCTURED_MARKER"],
            "captions": "CAPTION_PRIVATE_STRUCTURED_MARKER",
            "formulas_as_text": "E=mc^2_private_formula_marker",
            "evidence_quotes": "EVIDENCE_QUOTE_PRIVATE_STRUCTURED_MARKER",
            "filenames": "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
            "basenames": "source-deck.pdf",
            "paths": "/home/fake_private/source-deck.pdf",
            "urls": "https://private.invalid/source",
            "provider_payloads": "PROVIDER_PAYLOAD_PRIVATE_STRUCTURED_MARKER",
            "runtime_traces": "Authorization: Bearer sk_structured1234567890",
            "raw_exceptions": "C:\\fake_private\\uploaded-source.docx",
            "raw_artifact_json": "RAW_ARTIFACT_JSON_PRIVATE_STRUCTURED_MARKER",
        }
    )
    tainted_payload = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact([tainted]))
    assert_adapter_payload_shape("tainted", tainted_payload)
    check(
        "tainted: forbidden warning",
        "forbidden_field_stripped" in tainted_payload["candidates"][0].get("warnings", []),
        serialized(tainted_payload["candidates"][0].get("warnings")),
    )
    assert_no_canary("tainted adapter output", tainted_payload)
    tainted_extraction, tainted_bundle, tainted_produced, tainted_report = downstream_chain(tainted_payload)
    assert_no_canary("tainted extractor output", tainted_extraction)
    assert_no_canary("tainted mapper output", tainted_bundle)
    assert_no_canary("tainted fact sheet", tainted_produced)
    assert_no_canary("tainted recompute report", tainted_report)
    tainted_artifact = build_quality_safety_job_artifact_payload(safe_numeric_candidates=tainted_payload)
    assert_no_canary("tainted artifact payload", tainted_artifact)

    # --- 7. Real-disaster synthetic equivalents ------------------------------
    confident_wrong = structured_candidate(
        cand_id="qs_struct_confident_wrong",
        concept_id="qs_struct_wrong",
        label="synthetic_confident_wrong",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=0.9,
    )
    wrong_payload = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact([confident_wrong]))
    _, _, _, wrong_report = downstream_chain(wrong_payload)
    check("single_confident_wrong: blocking", bool(wrong_report.get("blocking_failures")), serialized(wrong_report))
    check("single_confident_wrong: report failed", wrong_report.get("status") == "failed", str(wrong_report.get("status")))
    wrong_artifact = build_quality_safety_job_artifact_payload(safe_numeric_candidates=wrong_payload)
    check("single_confident_wrong artifact: not shippable", wrong_artifact.get("shippable") is False)
    check("single_confident_wrong artifact: safety floor red", wrong_artifact.get("safety_floor_green") is False)

    clean_real = [
        structured_candidate(
            cand_id="qs_struct_clean_a",
            concept_id="qs_struct_clean_real",
            label="synthetic_clean_gini",
            method="weighted_gini",
            inputs={"groups": [{"a": 4, "b": 0}, {"a": 0, "b": 4}]},
            value=0.0,
        ),
        structured_candidate(
            cand_id="qs_struct_clean_b",
            concept_id="qs_struct_clean_real",
            label="synthetic_clean_total_error",
            method="total_error",
            inputs={"misclassified_weight": 0.0},
            value=0.0,
        ),
    ]
    clean_real_payload = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact(clean_real))
    _, _, _, clean_real_report = downstream_chain(clean_real_payload)
    check("clean_real_case: report passed", clean_real_report.get("status") == "passed", str(clean_real_report.get("status")))
    check("clean_real_case: no blocking", not clean_real_report.get("blocking_failures"))

    legacy_supported = structured_candidate(
        cand_id="qs_struct_legacy_supported",
        concept_id="qs_struct_legacy",
        label="synthetic_legacy_supported",
        method="cross_entropy",
        inputs={"probability": 0.5},
        value=0.9,
    )
    legacy_supported_payload = adapt_structured_numeric_candidates_to_safe_candidates(
        structured_artifact([unsupported, legacy_supported])
    )
    _, _, _, legacy_supported_report = downstream_chain(legacy_supported_payload)
    check("legacy_confused_wrong_case: partial unsupported present", unsupported_payload.get("status") == "warning")
    check(
        "legacy_confused_wrong_case: supported variant blocks",
        bool(legacy_supported_report.get("blocking_failures")),
        serialized(legacy_supported_report.get("blocking_failures")),
    )

    # --- 8. Determinism, max_items, and no mutation ---------------------------
    det_a = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact(all_candidates))
    det_b = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact(all_candidates))
    check("deterministic serialization", serialized(det_a) == serialized(det_b))

    many = [
        structured_candidate(
            cand_id=f"qs_struct_cap_{i}",
            method="weighted_gini",
            inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
            value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
        )
        for i in range(5)
    ]
    capped = adapt_structured_numeric_candidates_to_safe_candidates(structured_artifact(many), max_items=2)
    assert_adapter_payload_shape("capped", capped)
    check("capped: output count 2", capped["summary"]["output_candidate_count"] == 2)
    check("capped: input count 5", capped["summary"]["input_candidate_count"] == 5)
    check("capped: dropped 3", capped["summary"]["dropped_candidate_count"] == 3)
    check("capped: status partial", capped.get("status") == "partial")
    check("capped: max_items warning", "max_items_reached" in capped.get("warnings", []))
    check("capped: deterministic first ids", [c["id"] for c in capped["candidates"]] == ["qs_struct_cap_0", "qs_struct_cap_1"])

    mutation_input = structured_artifact([copy.deepcopy(tainted), copy.deepcopy(confident_wrong)])
    mutation_snapshot = copy.deepcopy(mutation_input)
    adapt_structured_numeric_candidates_to_safe_candidates(mutation_input)
    normalize_structured_numeric_candidate_artifact(mutation_input)
    check("no mutation: caller input unchanged", mutation_input == mutation_snapshot)

    # --- 9. Advisory artifact-path compatibility via safe candidates wrapper --
    clean_artifact = build_quality_safety_job_artifact_payload(safe_numeric_candidates=clean_payload)
    check("advisory path: safe extractor ok", clean_artifact.get("safe_numeric_extractor_status") == "ok")
    check("advisory path: numeric ok", clean_artifact.get("numeric_extraction_status") == "ok")
    check(
        "advisory path: recompute passed",
        clean_artifact.get("component_statuses", {}).get("recompute") == "passed",
        serialized(clean_artifact.get("component_statuses")),
    )
    wrong_artifact_again = build_quality_safety_job_artifact_payload(safe_numeric_candidates=wrong_payload)
    check("advisory path wrong: recompute blocker", bool(wrong_artifact_again.get("blocking_failures")))
    check("advisory path wrong: failed", wrong_artifact_again.get("status") == "failed")

    # --- 10. Import hygiene / purity guard -----------------------------------
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    check("purity: imports whitelisted", imported.issubset(ALLOWED_IMPORTS), str(imported - ALLOWED_IMPORTS))
    lowered = MODULE_PATH.read_text(encoding="utf-8").lower()
    bad_parts = [part for part in FORBIDDEN_IMPORT_PARTS if f"import {part}" in lowered or f"from {part}" in lowered]
    check("purity: no forbidden runtime imports", not bad_parts, str(bad_parts))
    check(
        "purity: no filesystem/provider call tokens",
        not any(tok in lowered for tok in ("open(", "requests.", "httpx.", "subprocess.", "socket.")),
    )

    # --- 11. Whole-run canary sweep ------------------------------------------
    assert_no_canary("final clean payload", clean_payload)
    assert_no_canary("final all payload", all_payload)
    assert_no_canary("final capped payload", capped)

    print(f"\ntest_quality_safety_structured_numeric_candidate_adapter: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
