#!/usr/bin/env python3
"""Slice 137 — Pure Operator Structured Numeric Export Validator v1 (synthetic).

Proves the pure/unwired validator
``pipeline.quality_safety_operator_structured_numeric_export_validator`` gates an
operator-approved ``quality_safety_structured_numeric_candidates``-like dict per
the Slice 136 protocol, strips/counts forbidden fields without leaking them, and
that its re-emitted ``structured_numeric_payload`` flows through the existing
downstream chain:

    operator validator
      → structured numeric candidate adapter
      → safe numeric extractor
      → numeric mapper
      → fact-sheet producer
      → recompute verifier

and, separately, through the Slice 134 advisory artifact path
(``build_quality_safety_job_artifact_payload(structured_numeric_candidates=...)``).

Synthetic-only. No real source decks, references, generated guides, OCR/table/
caption text, uploaded specs, provider payloads, paths, URLs, PDFs, DOCX/ZIPs, or
runtime artifacts are read or written. No providers, models, cloud, judge, or
repair are invoked. No production wiring. No private sidecar is validated.

Run:  python test_scripts/test_quality_safety_operator_structured_numeric_export_validator.py
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
)
from pipeline.quality_safety_operator_structured_numeric_export_validator import (  # noqa: E402
    OUTPUT_KIND,
    STRUCTURED_PAYLOAD_KIND,
    VALIDATION_STATUSES,
    VALIDATION_WARNINGS,
    build_empty_operator_structured_numeric_export_validation,
    operator_export_validation_to_structured_numeric_payload,
    validate_operator_structured_numeric_export,
)

PASS = 0
FAIL = 0

MODULE_PATH = REPO / "pipeline" / "quality_safety_operator_structured_numeric_export_validator.py"

SUMMARY_KEYS = frozenset(
    {
        "input_candidate_count",
        "accepted_candidate_count",
        "rejected_candidate_count",
        "supported_method_count",
        "unsupported_method_count",
        "forbidden_field_count",
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

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_operator1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_OPERATOR_MARKER",
    "TABLE_TEXT_PRIVATE_OPERATOR_MARKER",
    "CAPTION_PRIVATE_OPERATOR_MARKER",
    "PAGE_TEXT_PRIVATE_OPERATOR_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_OPERATOR_MARKER",
    "RAW_ARTIFACT_JSON_PRIVATE_OPERATOR_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_OPERATOR_MARKER",
    "source text private operator marker",
    "E=mc^2_private_operator_formula_marker",
    "ZZSYNTH_OPERATOR_PRIVATE_MARKER_ONLY",
)
FORBIDDEN_MARKERS = (
    "/home/fake_private",
    "C:\\fake_private",
    "https://",
    "Authorization",
    "Bearer",
    "sk_operator",
    "data:image",
    "base64",
    "OCR_PRIVATE",
    "TABLE_TEXT_PRIVATE",
    "CAPTION_PRIVATE",
    "PAGE_TEXT_PRIVATE",
    "PROVIDER_PAYLOAD_PRIVATE",
    "RAW_ARTIFACT_JSON_PRIVATE",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_OPERATOR_MARKER",
    "source text private operator marker",
    "private_operator_formula_marker",
    "ZZSYNTH_OPERATOR_PRIVATE_MARKER_ONLY",
)

FORBIDDEN_CANDIDATE_FIELD_PAYLOAD: dict[str, Any] = {
    "raw_text": "source text private operator marker",
    "source_text": "source text private operator marker",
    "guide_text": "ZZSYNTH_OPERATOR_PRIVATE_MARKER_ONLY",
    "ocr_text": "OCR_PRIVATE_OPERATOR_MARKER",
    "page_text": "PAGE_TEXT_PRIVATE_OPERATOR_MARKER",
    "table_cells": ["TABLE_TEXT_PRIVATE_OPERATOR_MARKER"],
    "captions": "CAPTION_PRIVATE_OPERATOR_MARKER",
    "formulas_as_text": "E=mc^2_private_operator_formula_marker",
    "evidence_quotes": "EVIDENCE_QUOTE_PRIVATE_OPERATOR_MARKER",
    "filenames": "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "basenames": "source-deck.pdf",
    "paths": "/home/fake_private/source-deck.pdf",
    "urls": "https://private.invalid/source",
    "provider_payloads": "PROVIDER_PAYLOAD_PRIVATE_OPERATOR_MARKER",
    "runtime_traces": "Authorization: Bearer sk_operator1234567890",
    "raw_exceptions": "C:\\fake_private\\uploaded-source.docx",
    "raw_artifact_json": "RAW_ARTIFACT_JSON_PRIVATE_OPERATOR_MARKER",
}

ALLOWED_IMPORT_ROOTS = {"__future__", "typing"}
ALLOWED_PIPELINE_IMPORTS = {
    "pipeline.quality_safety_structured_numeric_candidate_adapter",
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
    "quality_safety_job_artifact",
    "chandra",
    "mistral",
    "gemini",
    "socket",
    "subprocess",
    "pathlib",
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


def operator_export(candidates: list[Any], *, source_quality: str = "operator_approved") -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_structured_numeric_candidates",
        "status": "ok",
        "source_quality": source_quality,
        "candidates": candidates,
        "summary": {"candidate_count": len(candidates)},
        "warnings": [],
    }


def operator_candidate(
    *,
    cand_id: str = "qs_op_clean",
    concept_id: str = "qs_op_concept",
    label: str = "synthetic_score",
    method: str,
    inputs: dict[str, Any],
    value: float,
    tolerance: float = 0.02,
    provenance: str = "operator_approved",
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


def assert_result_shape(name: str, result: dict[str, Any]) -> None:
    check(f"{name}: kind", result.get("kind") == OUTPUT_KIND, str(result.get("kind")))
    check(f"{name}: version 1", result.get("version") == 1)
    check(f"{name}: status closed", result.get("status") in VALIDATION_STATUSES, str(result.get("status")))
    check(
        f"{name}: source_quality closed",
        result.get("source_quality") in {"operator_approved", "synthetic", "unknown"},
        str(result.get("source_quality")),
    )
    summary = result.get("summary", {})
    check(f"{name}: summary keys", set(summary) == SUMMARY_KEYS, str(set(summary)))
    for key in SUMMARY_KEYS:
        val = summary.get(key)
        check(f"{name}: {key} non-negative int", isinstance(val, int) and not isinstance(val, bool) and val >= 0, str(val))
    payload = result.get("structured_numeric_payload", {})
    check(f"{name}: payload kind", payload.get("kind") == STRUCTURED_PAYLOAD_KIND, str(payload.get("kind")))
    check(
        f"{name}: payload source_quality",
        payload.get("source_quality") in {"operator_approved", "synthetic"},
        str(payload.get("source_quality")),
    )
    check(f"{name}: payload candidates list", isinstance(payload.get("candidates"), list))
    check(
        f"{name}: warnings closed",
        all(w in VALIDATION_WARNINGS for w in result.get("warnings", [])),
        str(result.get("warnings")),
    )
    check(f"{name}: JSON-serializable", isinstance(serialized(result), str))


def downstream_chain(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run validator output through adapter → extractor → mapper → producer → recompute."""
    payload = operator_export_validation_to_structured_numeric_payload(result)
    adapter_payload = adapt_structured_numeric_candidates_to_safe_candidates(payload)
    extraction = extract_quality_safety_numeric_records_from_candidates(adapter_payload.get("candidates"))
    bundle = build_quality_safety_numeric_extraction_bundle(extraction.get("records"))
    fact_input = map_numeric_extraction_bundle_to_fact_sheet_input(bundle)
    produced = run_quality_safety_fact_sheet_producer(fact_input)
    report = build_quality_safety_recompute_report(produced.get("fact_sheet"))
    return adapter_payload, extraction, bundle, produced, report


def main() -> int:
    # --- 1. Missing / malformed / wrong-kind / empty payloads degrade safely ---
    empty = build_empty_operator_structured_numeric_export_validation()
    assert_result_shape("empty explicit", empty)
    check("empty explicit: skipped", empty.get("status") == "skipped")
    check("empty explicit: component_missing", empty.get("warnings") == ["component_missing"], serialized(empty))

    none_result = validate_operator_structured_numeric_export(None)
    assert_result_shape("none", none_result)
    check("none: skipped", none_result.get("status") == "skipped")
    check("none: component_missing", "component_missing" in none_result.get("warnings", []))

    malformed = validate_operator_structured_numeric_export("not a dict")
    assert_result_shape("malformed", malformed)
    check("malformed: failed", malformed.get("status") == "failed", serialized(malformed))
    check("malformed: malformed_input", "malformed_input" in malformed.get("warnings", []))

    wrong_kind = validate_operator_structured_numeric_export({"kind": "wrong", "candidates": []})
    assert_result_shape("wrong kind", wrong_kind)
    check("wrong kind: failed", wrong_kind.get("status") == "failed")
    check("wrong kind: invalid_kind", "invalid_kind" in wrong_kind.get("warnings", []))

    missing_candidates = validate_operator_structured_numeric_export(
        {"version": 1, "kind": "quality_safety_structured_numeric_candidates", "source_quality": "operator_approved"}
    )
    assert_result_shape("missing candidates", missing_candidates)
    check("missing candidates: skipped", missing_candidates.get("status") == "skipped")
    check("missing candidates: candidates_missing", "candidates_missing" in missing_candidates.get("warnings", []))

    empty_candidates = validate_operator_structured_numeric_export(operator_export([]))
    assert_result_shape("empty candidates", empty_candidates)
    check("empty candidates: skipped", empty_candidates.get("status") == "skipped")
    check("empty candidates: no_candidates", "no_candidates" in empty_candidates.get("warnings", []))

    non_list = validate_operator_structured_numeric_export(
        {"version": 1, "kind": "quality_safety_structured_numeric_candidates", "candidates": {"a": 1}}
    )
    assert_result_shape("non-list candidates", non_list)
    check("non-list candidates: skipped", non_list.get("status") == "skipped")
    check("non-list candidates: malformed_input", "malformed_input" in non_list.get("warnings", []))

    # --- 2. Valid operator-approved weighted_gini validates -------------------
    clean = operator_candidate(
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
    )
    clean_result = validate_operator_structured_numeric_export(operator_export([clean]))
    assert_result_shape("clean operator", clean_result)
    check("clean operator: status ok", clean_result.get("status") == "ok", str(clean_result.get("status")))
    check("clean operator: source operator_approved", clean_result.get("source_quality") == "operator_approved")
    check("clean operator: input 1", clean_result["summary"]["input_candidate_count"] == 1)
    check("clean operator: accepted 1", clean_result["summary"]["accepted_candidate_count"] == 1)
    check("clean operator: rejected 0", clean_result["summary"]["rejected_candidate_count"] == 0)
    check("clean operator: supported 1", clean_result["summary"]["supported_method_count"] == 1)
    check("clean operator: no warnings", clean_result.get("warnings") == [], serialized(clean_result.get("warnings")))
    check("clean operator: payload source operator_approved", clean_result["structured_numeric_payload"]["source_quality"] == "operator_approved")

    # --- 3. Valid synthetic export validates ----------------------------------
    synth_result = validate_operator_structured_numeric_export(operator_export([clean], source_quality="synthetic"))
    assert_result_shape("synthetic operator", synth_result)
    check("synthetic: status ok", synth_result.get("status") == "ok")
    check("synthetic: source synthetic", synth_result.get("source_quality") == "synthetic")
    check("synthetic: payload source synthetic", synth_result["structured_numeric_payload"]["source_quality"] == "synthetic")

    # Invalid source_quality degrades to unknown (with warning) but still validates.
    bad_source = validate_operator_structured_numeric_export(operator_export([clean], source_quality="structured_numeric_artifact"))
    assert_result_shape("bad source", bad_source)
    check("bad source: source unknown", bad_source.get("source_quality") == "unknown")
    check("bad source: invalid_source_quality warning", "invalid_source_quality" in bad_source.get("warnings", []))
    check("bad source: payload falls back to synthetic", bad_source["structured_numeric_payload"]["source_quality"] == "synthetic")

    # --- 4. All supported methods accepted with synthetic structured inputs ----
    all_candidates = [
        operator_candidate(
            cand_id=f"qs_op_{method}",
            concept_id=f"qs_op_concept_{method}",
            label=f"synthetic_{method}",
            method=method,
            inputs=inputs,
            value=value,
            tolerance=0.05,
            provenance="computed",
        )
        for method, (inputs, value) in SUPPORTED_METHOD_FIXTURES.items()
    ]
    all_result = validate_operator_structured_numeric_export(operator_export(all_candidates))
    assert_result_shape("all supported", all_result)
    check("all supported: status ok", all_result.get("status") == "ok", serialized(all_result.get("warnings")))
    check(
        "all supported: supported count",
        all_result["summary"]["supported_method_count"] == len(SUPPORTED_METHOD_FIXTURES),
        serialized(all_result["summary"]),
    )
    check("all supported: accepted count", all_result["summary"]["accepted_candidate_count"] == len(SUPPORTED_METHOD_FIXTURES))
    _, all_extraction, _, _, all_report = downstream_chain(all_result)
    check("all supported downstream: extractor ok", all_extraction.get("status") == "ok", str(all_extraction.get("status")))
    check("all supported downstream: recompute passed", all_report.get("status") == "passed", str(all_report.get("status")))
    check("all supported downstream: no blocking", not all_report.get("blocking_failures"))

    # --- 5. Unsupported method degrades (kept, flagged, not recomputable) ------
    unsupported = operator_candidate(
        cand_id="qs_op_legacy_unsupported",
        concept_id="qs_op_legacy",
        label="synthetic_legacy_confused",
        method="entropy",
        inputs={"probability": 0.5},
        value=0.9,
        provenance="computed",
    )
    unsupported_result = validate_operator_structured_numeric_export(operator_export([unsupported]))
    assert_result_shape("unsupported", unsupported_result)
    check("unsupported: warning status", unsupported_result.get("status") == "warning", str(unsupported_result.get("status")))
    check("unsupported: token", "unsupported_method" in unsupported_result.get("warnings", []))
    check("unsupported: counted unsupported", unsupported_result["summary"]["unsupported_method_count"] == 1)
    check("unsupported: supported 0", unsupported_result["summary"]["supported_method_count"] == 0)
    check("unsupported: accepted 1 (degraded, kept)", unsupported_result["summary"]["accepted_candidate_count"] == 1)
    _, _, _, _, unsupported_report = downstream_chain(unsupported_result)
    check("unsupported downstream: no blocking", not unsupported_report.get("blocking_failures"))
    check("unsupported downstream: report not failed", unsupported_report.get("status") != "failed", str(unsupported_report.get("status")))

    # --- 6. Invalid numeric value rejected ------------------------------------
    bad_value = operator_candidate(method="weighted_gini", inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0], value=0.2)
    bad_value["value"] = "not_numeric"
    bad_value_result = validate_operator_structured_numeric_export(operator_export([bad_value]))
    assert_result_shape("bad value", bad_value_result)
    check("bad value: failed (all rejected)", bad_value_result.get("status") == "failed")
    check("bad value: invalid_numeric_value", "invalid_numeric_value" in bad_value_result.get("warnings", []))
    check("bad value: accepted 0", bad_value_result["summary"]["accepted_candidate_count"] == 0)
    check("bad value: rejected 1", bad_value_result["summary"]["rejected_candidate_count"] == 1)
    check("bad value: empty payload", bad_value_result["structured_numeric_payload"]["candidates"] == [])

    # --- 7. Invalid computation rejected --------------------------------------
    no_method = operator_candidate(method="weighted_gini", inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0], value=0.2)
    no_method["computation"] = {"inputs": {"groups": []}}  # method missing
    no_method_result = validate_operator_structured_numeric_export(operator_export([no_method]))
    assert_result_shape("no method", no_method_result)
    check("no method: failed", no_method_result.get("status") == "failed")
    check("no method: invalid_computation", "invalid_computation" in no_method_result.get("warnings", []))

    bad_inputs = operator_candidate(method="weighted_gini", inputs={"groups": "EVIDENCE_QUOTE_PRIVATE_OPERATOR_MARKER"}, value=0.2)
    bad_inputs_result = validate_operator_structured_numeric_export(operator_export([bad_inputs]))
    assert_result_shape("bad inputs", bad_inputs_result)
    check("bad inputs: rejected/degraded", bad_inputs_result["summary"]["accepted_candidate_count"] == 0)
    check("bad inputs: invalid_computation", "invalid_computation" in bad_inputs_result.get("warnings", []))
    assert_no_canary("bad inputs result", bad_inputs_result)

    # --- 8. Invalid provenance rejected ---------------------------------------
    bad_prov = operator_candidate(
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=0.2,
        provenance="extracted_high",
    )
    bad_prov_result = validate_operator_structured_numeric_export(operator_export([bad_prov]))
    assert_result_shape("bad provenance", bad_prov_result)
    check("bad provenance: failed", bad_prov_result.get("status") == "failed")
    check("bad provenance: invalid_provenance", "invalid_provenance" in bad_prov_result.get("warnings", []))

    missing_prov = operator_candidate(method="weighted_gini", inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0], value=0.2)
    del missing_prov["provenance"]
    missing_prov_result = validate_operator_structured_numeric_export(operator_export([missing_prov]))
    check("missing provenance: invalid_provenance", "invalid_provenance" in missing_prov_result.get("warnings", []))
    check("missing provenance: rejected", missing_prov_result["summary"]["accepted_candidate_count"] == 0)

    # Non-numeric fact_type rejected.
    non_numeric = operator_candidate(method="weighted_gini", inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0], value=0.2)
    non_numeric["fact_type"] = "text"
    non_numeric_result = validate_operator_structured_numeric_export(operator_export([non_numeric]))
    check("non-numeric: invalid_candidate_rejected", "invalid_candidate_rejected" in non_numeric_result.get("warnings", []))
    check("non-numeric: rejected", non_numeric_result["summary"]["accepted_candidate_count"] == 0)

    # --- 9. Forbidden fields detected, counted, stripped, never emitted -------
    tainted = operator_candidate(
        cand_id="qs_op_tainted",
        concept_id="qs_op_tainted_concept",
        label="synthetic_tainted",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
    )
    tainted.update(copy.deepcopy(FORBIDDEN_CANDIDATE_FIELD_PAYLOAD))
    tainted_result = validate_operator_structured_numeric_export(operator_export([tainted]))
    assert_result_shape("tainted", tainted_result)
    check("tainted: still accepted", tainted_result["summary"]["accepted_candidate_count"] == 1)
    check("tainted: warning status", tainted_result.get("status") == "warning")
    check("tainted: unsafe_field_excluded", "unsafe_field_excluded" in tainted_result.get("warnings", []))
    check(
        "tainted: forbidden_field_count matches",
        tainted_result["summary"]["forbidden_field_count"] == len(FORBIDDEN_CANDIDATE_FIELD_PAYLOAD),
        str(tainted_result["summary"]["forbidden_field_count"]),
    )
    assert_no_canary("tainted validator result", tainted_result)
    payload = operator_export_validation_to_structured_numeric_payload(tainted_result)
    assert_no_canary("tainted structured payload", payload)
    t_adapter, t_extraction, t_bundle, t_produced, t_report = downstream_chain(tainted_result)
    assert_no_canary("tainted adapter output", t_adapter)
    assert_no_canary("tainted extractor output", t_extraction)
    assert_no_canary("tainted mapper output", t_bundle)
    assert_no_canary("tainted fact sheet", t_produced)
    assert_no_canary("tainted recompute report", t_report)
    tainted_artifact = build_quality_safety_job_artifact_payload(structured_numeric_candidates=payload)
    assert_no_canary("tainted artifact payload", tainted_artifact)

    # --- 10. Real-disaster synthetic equivalents (downstream) -----------------
    # single_confident_wrong_numeric_case: supported method, wrong claimed value.
    confident_wrong = operator_candidate(
        cand_id="qs_op_confident_wrong",
        concept_id="qs_op_wrong",
        label="synthetic_confident_wrong",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=0.9,
    )
    wrong_result = validate_operator_structured_numeric_export(operator_export([confident_wrong]))
    check("single_confident_wrong: validates ok", wrong_result.get("status") == "ok", str(wrong_result.get("status")))
    _, _, _, _, wrong_report = downstream_chain(wrong_result)
    check("single_confident_wrong: recompute blocking", bool(wrong_report.get("blocking_failures")), serialized(wrong_report))
    check("single_confident_wrong: report failed", wrong_report.get("status") == "failed", str(wrong_report.get("status")))
    wrong_payload = operator_export_validation_to_structured_numeric_payload(wrong_result)
    wrong_artifact = build_quality_safety_job_artifact_payload(structured_numeric_candidates=wrong_payload)
    check("single_confident_wrong artifact: not shippable", wrong_artifact.get("shippable") is False)
    check("single_confident_wrong artifact: safety floor red", wrong_artifact.get("safety_floor_green") is False)
    check(
        "single_confident_wrong artifact: adapter ok",
        wrong_artifact.get("structured_numeric_candidate_adapter_status") in {"ok", "warning"},
        str(wrong_artifact.get("structured_numeric_candidate_adapter_status")),
    )

    # clean_real_case: supported methods, correct claimed values.
    clean_real = [
        operator_candidate(
            cand_id="qs_op_clean_a",
            concept_id="qs_op_clean_real",
            label="synthetic_clean_gini",
            method="weighted_gini",
            inputs={"groups": [{"a": 4, "b": 0}, {"a": 0, "b": 4}]},
            value=0.0,
        ),
        operator_candidate(
            cand_id="qs_op_clean_b",
            concept_id="qs_op_clean_real",
            label="synthetic_clean_total_error",
            method="total_error",
            inputs={"misclassified_weight": 0.0},
            value=0.0,
        ),
    ]
    clean_real_result = validate_operator_structured_numeric_export(operator_export(clean_real))
    check("clean_real_case: validates ok", clean_real_result.get("status") == "ok")
    check("clean_real_case: accepted 2", clean_real_result["summary"]["accepted_candidate_count"] == 2)
    _, _, _, _, clean_real_report = downstream_chain(clean_real_result)
    check("clean_real_case: recompute passed", clean_real_report.get("status") == "passed", str(clean_real_report.get("status")))
    check("clean_real_case: no blocking", not clean_real_report.get("blocking_failures"))
    clean_real_artifact = build_quality_safety_job_artifact_payload(
        structured_numeric_candidates=operator_export_validation_to_structured_numeric_payload(clean_real_result)
    )
    check("clean_real_case artifact: shippable", clean_real_artifact.get("shippable") is True)

    # legacy_confused_wrong_case: unsupported method stays partial; supported variant blocks.
    legacy_result = validate_operator_structured_numeric_export(operator_export([unsupported]))
    _, _, _, _, legacy_report = downstream_chain(legacy_result)
    check("legacy_confused_wrong_case: partial/unverified (no blocking)", not legacy_report.get("blocking_failures"))
    check("legacy_confused_wrong_case: validator warning", legacy_result.get("status") == "warning")

    legacy_supported = operator_candidate(
        cand_id="qs_op_legacy_supported",
        concept_id="qs_op_legacy",
        label="synthetic_legacy_supported",
        method="cross_entropy",
        inputs={"probability": 0.5},
        value=0.9,  # cross_entropy(0.5) ≈ 0.693, so 0.9 is wrong → blocks
        provenance="computed",
    )
    legacy_mixed_result = validate_operator_structured_numeric_export(operator_export([unsupported, legacy_supported]))
    assert_result_shape("legacy mixed", legacy_mixed_result)
    check("legacy mixed: accepted 2", legacy_mixed_result["summary"]["accepted_candidate_count"] == 2)
    check("legacy mixed: supported 1", legacy_mixed_result["summary"]["supported_method_count"] == 1)
    check("legacy mixed: unsupported 1", legacy_mixed_result["summary"]["unsupported_method_count"] == 1)
    _, _, _, _, legacy_mixed_report = downstream_chain(legacy_mixed_result)
    check(
        "legacy_confused_wrong_case: supported variant blocks",
        bool(legacy_mixed_report.get("blocking_failures")),
        serialized(legacy_mixed_report.get("blocking_failures")),
    )

    # --- 11. Mixed accepted + rejected → partial ------------------------------
    mixed = validate_operator_structured_numeric_export(operator_export([clean, bad_prov]))
    assert_result_shape("mixed", mixed)
    check("mixed: partial", mixed.get("status") == "partial", str(mixed.get("status")))
    check("mixed: accepted 1", mixed["summary"]["accepted_candidate_count"] == 1)
    check("mixed: rejected 1", mixed["summary"]["rejected_candidate_count"] == 1)

    # --- 12. Determinism, max_items cap, no mutation --------------------------
    det_a = validate_operator_structured_numeric_export(operator_export(all_candidates))
    det_b = validate_operator_structured_numeric_export(operator_export(all_candidates))
    check("deterministic serialization", serialized(det_a) == serialized(det_b))

    capped = validate_operator_structured_numeric_export(operator_export(all_candidates), max_items=2)
    assert_result_shape("capped", capped)
    check("capped: input count full", capped["summary"]["input_candidate_count"] == len(all_candidates))
    check("capped: accepted capped to 2", capped["summary"]["accepted_candidate_count"] == 2)
    check("capped: partial", capped.get("status") == "partial")
    check("capped: max_items_reached", "max_items_reached" in capped.get("warnings", []))
    capped_again = validate_operator_structured_numeric_export(operator_export(all_candidates), max_items=2)
    check("capped: deterministic", serialized(capped) == serialized(capped_again))

    mutation_input = operator_export([copy.deepcopy(tainted), copy.deepcopy(clean)])
    before = copy.deepcopy(mutation_input)
    validate_operator_structured_numeric_export(mutation_input)
    check("no caller mutation", mutation_input == before)

    # --- 13. Accessor degrades safely -----------------------------------------
    fallback_payload = operator_export_validation_to_structured_numeric_payload("not a dict")
    check("accessor: fallback kind", fallback_payload.get("kind") == STRUCTURED_PAYLOAD_KIND)
    check("accessor: fallback empty", fallback_payload.get("candidates") == [])

    # --- 14. Import hygiene / purity guard ------------------------------------
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported_modules.add(module)
            imported_roots.add(module.split(".")[0])
    allowed_roots = ALLOWED_IMPORT_ROOTS | {"pipeline"}
    check(
        "import hygiene: roots allowed",
        imported_roots.issubset(allowed_roots),
        str(imported_roots - allowed_roots),
    )
    pipeline_imports = {m for m in imported_modules if m.startswith("pipeline")}
    check(
        "import hygiene: only allowed pipeline modules",
        pipeline_imports.issubset(ALLOWED_PIPELINE_IMPORTS),
        str(pipeline_imports - ALLOWED_PIPELINE_IMPORTS),
    )
    source_text = MODULE_PATH.read_text(encoding="utf-8")
    import_lines = [ln for ln in source_text.splitlines() if ln.strip().startswith(("import ", "from "))]
    joined = "\n".join(import_lines).lower()
    forbidden_hits = [part for part in FORBIDDEN_IMPORT_PARTS if part in joined]
    check("purity guard: no forbidden import parts", not forbidden_hits, str(forbidden_hits))

    # --- 15. No forbidden canary across all produced outputs ------------------
    blob = serialized(
        [
            empty, none_result, malformed, wrong_kind, missing_candidates, empty_candidates,
            non_list, clean_result, synth_result, bad_source, all_result, unsupported_result,
            bad_value_result, no_method_result, bad_inputs_result, bad_prov_result,
            missing_prov_result, non_numeric_result, tainted_result, wrong_result,
            clean_real_result, legacy_result, legacy_mixed_result, mixed, capped,
        ]
    )
    check("no synthetic canary across results", "ZZSYNTH_OPERATOR_PRIVATE_MARKER_ONLY" not in blob)

    print(f"\ntest_quality_safety_operator_structured_numeric_export_validator: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
