#!/usr/bin/env python3
"""Tests for Slice 129 Quality Safety safe numeric extractor v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. Hostile canaries
below are synthetic markers used to prove forbidden content is stripped and never
echoed.

The extractor is pure/unwired: it converts caller-supplied *sanitized numeric
candidates* into ``quality_safety_numeric_extraction_records``-compatible records,
deferring final field sanitization to the Slice 125 mapper. These tests prove the
payload is sidecar-compatible (flows through the Slice 126 artifact path and the
mapper -> producer -> recompute verifier chain), that a wrong synthetic claim is
recompute-blocked and a clean one verifies, that forbidden fields are stripped and
never echoed, that input is never mutated, and that the module stays import-pure.

Run:  python test_scripts/test_quality_safety_safe_numeric_extractor.py
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
    _coerce_numeric_records,
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
    build_empty_safe_numeric_extraction_records,
    extract_quality_safety_numeric_records_from_candidates,
    map_safe_numeric_candidates_to_sidecar_payload,
    normalize_safe_numeric_candidate,
)

PASS = 0
FAIL = 0

MODULE_PATH = REPO / "pipeline" / "quality_safety_safe_numeric_extractor.py"

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_extractor1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_EXTRACTOR_MARKER",
    "TABLE_TEXT_PRIVATE_EXTRACTOR_MARKER",
    "CAPTION_PRIVATE_EXTRACTOR_MARKER",
    "PAGE_TEXT_PRIVATE_EXTRACTOR_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_EXTRACTOR_MARKER",
    "RAW_ARTIFACT_JSON_PRIVATE_EXTRACTOR_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_EXTRACTOR_MARKER",
    "source text private marker",
    "E=mc^2_private_formula_marker",
    "ZZSYNTH_EXTRACTOR_PRIVATE_MARKER_ONLY",
)
FORBIDDEN_MARKERS = (
    "/home/fake_private",
    "C:\\fake_private",
    "https://",
    "Authorization",
    "Bearer",
    "sk_extractor",
    "data:image",
    "base64",
    "OCR_PRIVATE",
    "TABLE_TEXT_PRIVATE",
    "CAPTION_PRIVATE",
    "PAGE_TEXT_PRIVATE",
    "PROVIDER_PAYLOAD_PRIVATE",
    "RAW_ARTIFACT_JSON_PRIVATE",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_EXTRACTOR_MARKER",
    "source text private marker",
    "private_formula_marker",
    "ZZSYNTH_EXTRACTOR_PRIVATE_MARKER_ONLY",
)

# Closed extractor vocabulary, mirrored for assertions.
PAYLOAD_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
SOURCE_QUALITIES = frozenset({"synthetic", "sanitized_candidates", "unknown"})
PAYLOAD_WARNINGS = frozenset(
    {
        "component_missing",
        "empty_numeric_extraction",
        "malformed_numeric_extraction_input",
        "invalid_numeric_record_dropped",
        "max_items_reached",
    }
)
RECORD_WARNINGS = frozenset(
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
RECORD_FIELDS = frozenset(
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
        "candidate_count",
        "record_count",
        "supported_method_count",
        "unsupported_method_count",
        "dropped_candidate_count",
    }
)

ALLOWED_IMPORTS = {
    "__future__",
    "typing",
    "pipeline.quality_safety_numeric_extraction_mapper",
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
    "os",
    "pathlib",
    "json",
)

# Supported-method fixtures: structured numeric inputs + their correct values.
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


def computation_candidate(
    *,
    cand_id: str | None = None,
    concept_id: str = "qs_concept_1",
    label: str = "synthetic_score",
    method: str,
    inputs: dict[str, Any],
    value: float,
    tolerance: float = 0.02,
    flat_alias: bool = False,
) -> dict[str, Any]:
    """Build a synthetic sanitized numeric candidate.

    ``flat_alias`` emits the flat ``method``/``inputs`` alias instead of a nested
    ``computation`` block, exercising the extractor's alias resolution.
    """
    candidate: dict[str, Any] = {
        "concept_id": concept_id,
        "label": label,
        "fact_type": "numeric",
        "value": value,
        "unit": "ratio",
        "provenance": "computed",
        "confidence": "medium",
        "source_ref": "source_page_1",
        "page_ref": "page_1",
        "tolerance": tolerance,
    }
    if cand_id is not None:
        candidate["id"] = cand_id
    if flat_alias:
        candidate["method"] = method
        candidate["inputs"] = inputs
    else:
        candidate["computation"] = {"method": method, "inputs": inputs}
    return candidate


def assert_payload_shape(name: str, payload: dict[str, Any]) -> None:
    check(f"{name}: kind", payload.get("kind") == "quality_safety_numeric_extraction_records")
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
    for record in payload.get("records", []):
        check(f"{name}: record fields whitelisted", set(record).issubset(RECORD_FIELDS), str(set(record)))
        check(f"{name}: record fact_type numeric", record.get("fact_type") == "numeric")
        check(
            f"{name}: record warnings closed",
            all(w in RECORD_WARNINGS for w in record.get("warnings", [])),
            str(record.get("warnings")),
        )
    check(f"{name}: JSON-serializable", isinstance(serialized(payload), str))


def recompute_report_for_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Drive the payload through the Slice 126 coercion + mapper + producer + verifier."""
    records = _coerce_numeric_records(payload)
    bundle = build_quality_safety_numeric_extraction_bundle(records)
    fact_sheet_input = map_numeric_extraction_bundle_to_fact_sheet_input(bundle)
    produced = run_quality_safety_fact_sheet_producer(fact_sheet_input)
    return build_quality_safety_recompute_report(produced.get("fact_sheet"))


def main() -> int:
    # --- 1. Empty / missing / malformed top-level input degrades safely -------
    none_payload = extract_quality_safety_numeric_records_from_candidates(None)
    assert_payload_shape("none input", none_payload)
    check(
        "none input: skipped + component_missing",
        none_payload.get("status") == "skipped" and "component_missing" in none_payload.get("warnings", []),
        serialized(none_payload),
    )

    empty_payload = extract_quality_safety_numeric_records_from_candidates([])
    assert_payload_shape("empty list", empty_payload)
    check(
        "empty list: skipped + empty_numeric_extraction",
        empty_payload.get("status") == "skipped" and "empty_numeric_extraction" in empty_payload.get("warnings", []),
        serialized(empty_payload),
    )

    malformed_payload = extract_quality_safety_numeric_records_from_candidates("not a list")
    assert_payload_shape("malformed input", malformed_payload)
    check(
        "malformed input: failed + malformed warning",
        malformed_payload.get("status") == "failed"
        and "malformed_numeric_extraction_input" in malformed_payload.get("warnings", []),
        serialized(malformed_payload),
    )

    explicit_empty = build_empty_safe_numeric_extraction_records()
    assert_payload_shape("explicit empty", explicit_empty)
    check(
        "explicit empty: skipped + component_missing",
        explicit_empty.get("status") == "skipped" and explicit_empty.get("warnings") == ["component_missing"],
        serialized(explicit_empty),
    )
    check(
        "explicit empty: bad reason coerced",
        build_empty_safe_numeric_extraction_records("evil").get("warnings") == ["component_missing"],
    )
    check(
        "explicit empty: malformed reason -> failed",
        build_empty_safe_numeric_extraction_records("malformed_numeric_extraction_input").get("status") == "failed",
    )

    check("normalize non-dict -> None", normalize_safe_numeric_candidate("nope") is None)
    check("normalize None -> None", normalize_safe_numeric_candidate(None) is None)
    check("normalize list -> None", normalize_safe_numeric_candidate([1, 2, 3]) is None)

    # --- 2. Valid weighted_gini candidate emits a sidecar-compatible record ----
    clean = computation_candidate(
        cand_id="qs_num_clean",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
    )
    clean_payload = extract_quality_safety_numeric_records_from_candidates([clean])
    assert_payload_shape("clean weighted_gini", clean_payload)
    check("clean: status ok", clean_payload.get("status") == "ok", str(clean_payload.get("status")))
    check("clean: candidate_count 1", clean_payload["summary"]["candidate_count"] == 1)
    check("clean: record_count 1", clean_payload["summary"]["record_count"] == 1)
    check("clean: supported_method_count 1", clean_payload["summary"]["supported_method_count"] == 1)
    check("clean: dropped 0", clean_payload["summary"]["dropped_candidate_count"] == 0)
    clean_report = recompute_report_for_payload(clean_payload)
    clean_passed = [
        c
        for c in clean_report.get("checks", [])
        if c.get("check_id") == "weighted_gini" and c.get("status") == "passed"
    ]
    check("clean: weighted_gini verified", bool(clean_passed), serialized(clean_report.get("checks")))
    check("clean: no blocking failure", not clean_report.get("blocking_failures"))
    check("clean: report passed", clean_report.get("status") == "passed", str(clean_report.get("status")))

    # Synthetic id is generated when the candidate has none.
    no_id = computation_candidate(
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
    )
    no_id_payload = extract_quality_safety_numeric_records_from_candidates([no_id])
    check(
        "no id: synthetic qs_safe_num id",
        no_id_payload["records"][0]["id"] == "qs_safe_num_0001",
        no_id_payload["records"][0]["id"],
    )

    # --- 3. All supported methods accepted with structured inputs (flat alias) -
    all_method_candidates = [
        computation_candidate(
            cand_id=f"qs_num_{method}",
            concept_id=f"qs_concept_{method}",
            label=f"synthetic_{method}",
            method=method,
            inputs=inputs,
            value=value,
            tolerance=0.05,
            flat_alias=True,
        )
        for method, (inputs, value) in SUPPORTED_METHOD_FIXTURES.items()
    ]
    all_payload = extract_quality_safety_numeric_records_from_candidates(all_method_candidates)
    assert_payload_shape("all supported methods", all_payload)
    check(
        "all methods: every candidate kept as supported record",
        all_payload["summary"]["supported_method_count"] == len(SUPPORTED_METHOD_FIXTURES),
        serialized(all_payload["summary"]),
    )
    check("all methods: no unsupported", all_payload["summary"]["unsupported_method_count"] == 0)
    all_report = recompute_report_for_payload(all_payload)
    check("all methods: report passed", all_report.get("status") == "passed", str(all_report.get("status")))
    check("all methods: no blocking", not all_report.get("blocking_failures"))
    assert_no_canary("all methods report", all_report)

    # --- 4. clean_real_case synthetic equivalent passes recompute -------------
    clean_real_candidates = [
        computation_candidate(
            cand_id="qs_num_real_a",
            concept_id="qs_concept_real",
            label="synthetic_clean_gini",
            method="weighted_gini",
            inputs={"groups": [{"a": 4, "b": 0}, {"a": 0, "b": 4}]},
            value=0.0,
        ),
        computation_candidate(
            cand_id="qs_num_real_b",
            concept_id="qs_concept_real",
            label="synthetic_clean_total_error",
            method="total_error",
            inputs={"misclassified_weight": 0.0},
            value=0.0,
            flat_alias=True,
        ),
    ]
    clean_real_payload = extract_quality_safety_numeric_records_from_candidates(clean_real_candidates)
    clean_real_report = recompute_report_for_payload(clean_real_payload)
    check(
        "clean_real_case: report passed",
        clean_real_report.get("status") == "passed",
        str(clean_real_report.get("status")),
    )
    check("clean_real_case: no blocking", not clean_real_report.get("blocking_failures"))
    check(
        "clean_real_case: two verified",
        clean_real_report["summary"]["verified_fact_count"] == 2,
        serialized(clean_real_report["summary"]),
    )
    assert_no_canary("clean_real_case report", clean_real_payload)

    # --- 5. single_confident_wrong_numeric_case fails recompute (blocking) ----
    confident_wrong = computation_candidate(
        cand_id="qs_num_confident_wrong",
        concept_id="qs_concept_wrong",
        label="synthetic_confident_wrong",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=0.9,  # deliberately wrong vs recomputed 0.2
        flat_alias=True,
    )
    wrong_payload = extract_quality_safety_numeric_records_from_candidates([confident_wrong])
    assert_payload_shape("confident wrong", wrong_payload)
    wrong_report = recompute_report_for_payload(wrong_payload)
    check(
        "confident_wrong: recompute blocking failure raised",
        bool(wrong_report.get("blocking_failures")),
        serialized(wrong_report.get("blocking_failures")),
    )
    check(
        "confident_wrong: report failed",
        wrong_report.get("status") == "failed",
        str(wrong_report.get("status")),
    )
    assert_no_canary("confident_wrong report", wrong_report)

    # Through the real Slice 126 artifact path: wrong claim reddens advisory flags.
    wrong_artifact = build_quality_safety_job_artifact_payload(numeric_extraction_records=wrong_payload)
    check(
        "confident_wrong artifact: not shippable",
        wrong_artifact.get("shippable") is False,
        str(wrong_artifact.get("shippable")),
    )
    check(
        "confident_wrong artifact: safety floor not green",
        wrong_artifact.get("safety_floor_green") is False,
        str(wrong_artifact.get("safety_floor_green")),
    )
    check(
        "confident_wrong artifact: numeric status warning/degraded present",
        wrong_artifact.get("numeric_extraction_status") in {"ok", "warning"},
        str(wrong_artifact.get("numeric_extraction_status")),
    )
    assert_no_canary("confident_wrong artifact", wrong_artifact)

    # Clean payload through the same artifact path: numeric leg does not block.
    clean_artifact = build_quality_safety_job_artifact_payload(numeric_extraction_records=clean_payload)
    clean_blockers = [
        b
        for b in clean_artifact.get("blocking_failures", [])
        if isinstance(b, dict) and b.get("check_id") in {"weighted_gini", "recomputed_mismatch"}
    ]
    check("clean artifact: no numeric recompute blocker", not clean_blockers, serialized(clean_artifact.get("blocking_failures")))
    check(
        "clean artifact: numeric status ok",
        clean_artifact.get("numeric_extraction_status") == "ok",
        str(clean_artifact.get("numeric_extraction_status")),
    )

    # --- 6. legacy_confused_wrong_case: unsupported method degrades to partial -
    legacy_unsupported = computation_candidate(
        cand_id="qs_num_legacy_unsupported",
        concept_id="qs_concept_legacy",
        label="synthetic_legacy_confused",
        method="entropy",  # NOT in SUPPORTED_METHODS
        inputs={"probability": 0.5},
        value=0.9,  # wrong, but cannot be recompute-blocked without the method
    )
    legacy_payload = extract_quality_safety_numeric_records_from_candidates([legacy_unsupported])
    assert_payload_shape("legacy unsupported", legacy_payload)
    legacy_record = legacy_payload["records"][0]
    check("legacy unsupported: computation demoted to None", legacy_record.get("computation") is None)
    check(
        "legacy unsupported: unsupported_method warning",
        "unsupported_method" in legacy_record.get("warnings", []),
        str(legacy_record.get("warnings")),
    )
    check(
        "legacy unsupported: counted unsupported",
        legacy_payload["summary"]["unsupported_method_count"] == 1,
        serialized(legacy_payload["summary"]),
    )
    legacy_report = recompute_report_for_payload(legacy_payload)
    check(
        "legacy unsupported: NOT recompute-blocked (partial)",
        not legacy_report.get("blocking_failures"),
        serialized(legacy_report.get("blocking_failures")),
    )

    # The same archetype expressed with a SUPPORTED method IS recompute-blocked.
    legacy_supported = computation_candidate(
        cand_id="qs_num_legacy_supported",
        concept_id="qs_concept_legacy",
        label="synthetic_legacy_supported",
        method="cross_entropy",
        inputs={"probability": 0.5},  # correct -ln(0.5) = 0.6931...
        value=0.9,  # deliberately wrong
    )
    legacy_supported_payload = extract_quality_safety_numeric_records_from_candidates([legacy_supported])
    legacy_supported_report = recompute_report_for_payload(legacy_supported_payload)
    check(
        "legacy supported-method variant: recompute-blocked",
        bool(legacy_supported_report.get("blocking_failures")),
        serialized(legacy_supported_report.get("blocking_failures")),
    )

    # --- 7. Unsupported / invalid value / tolerance / computation degrade -----
    invalid_value = computation_candidate(
        cand_id="qs_num_badval",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value="not_a_number",  # type: ignore[arg-type]
    )
    invalid_value_payload = extract_quality_safety_numeric_records_from_candidates([invalid_value])
    badval_record = invalid_value_payload["records"][0]
    check("invalid value: value None", badval_record.get("value") is None)
    check(
        "invalid value: invalid_numeric_value warning",
        "invalid_numeric_value" in badval_record.get("warnings", []),
        str(badval_record.get("warnings")),
    )

    bad_tol = computation_candidate(
        cand_id="qs_num_badtol",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=0.2,
        tolerance=99.0,  # out of (0, 1]
    )
    bad_tol_payload = extract_quality_safety_numeric_records_from_candidates([bad_tol])
    badtol_record = bad_tol_payload["records"][0]
    check("invalid tolerance: tolerance None", badtol_record.get("tolerance") is None)
    check(
        "invalid tolerance: invalid_tolerance warning",
        "invalid_tolerance" in badtol_record.get("warnings", []),
        str(badtol_record.get("warnings")),
    )

    malformed_comp = {
        "id": "qs_num_badcomp",
        "label": "synthetic_badcomp",
        "fact_type": "numeric",
        "value": 0.2,
        "computation": {"method": "weighted_gini", "inputs": "junk_not_a_dict"},
    }
    malformed_comp_payload = extract_quality_safety_numeric_records_from_candidates([malformed_comp])
    badcomp_record = malformed_comp_payload["records"][0]
    check("malformed computation: demoted to None", badcomp_record.get("computation") is None)
    check(
        "malformed computation: malformed_computation warning",
        "malformed_computation" in badcomp_record.get("warnings", []),
        str(badcomp_record.get("warnings")),
    )

    # --- 8. Forbidden fields stripped and never echoed ------------------------
    tainted = {
        "id": "qs_num_tainted",
        "concept_id": "qs_concept_tainted",
        "label": "synthetic_tainted",
        "fact_type": "numeric",
        "value": SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
        "computation": {"method": "weighted_gini", "inputs": SUPPORTED_METHOD_FIXTURES["weighted_gini"][0]},
        "tolerance": 0.02,
        # Forbidden fields carrying hostile canaries:
        "raw_text": "source text private marker",
        "source_text": "source text private marker",
        "guide_text": "ZZSYNTH_EXTRACTOR_PRIVATE_MARKER_ONLY",
        "ocr_text": "OCR_PRIVATE_EXTRACTOR_MARKER",
        "page_text": "PAGE_TEXT_PRIVATE_EXTRACTOR_MARKER",
        "table_cells": ["TABLE_TEXT_PRIVATE_EXTRACTOR_MARKER"],
        "captions": "CAPTION_PRIVATE_EXTRACTOR_MARKER",
        "formulas_as_text": "E=mc^2_private_formula_marker",
        "evidence_quotes": "EVIDENCE_QUOTE_PRIVATE_EXTRACTOR_MARKER",
        "filenames": "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
        "basenames": "source-deck.pdf",
        "paths": "/home/fake_private/source-deck.pdf",
        "urls": "https://private.invalid/source",
        "provider_payloads": "PROVIDER_PAYLOAD_PRIVATE_EXTRACTOR_MARKER",
        "runtime_traces": "Authorization: Bearer sk_extractor1234567890",
        "raw_exceptions": "C:\\fake_private\\uploaded-source.docx",
        "raw_artifact_json": "RAW_ARTIFACT_JSON_PRIVATE_EXTRACTOR_MARKER",
    }
    tainted_payload = extract_quality_safety_numeric_records_from_candidates([tainted])
    assert_payload_shape("tainted", tainted_payload)
    tainted_record = tainted_payload["records"][0]
    check("tainted: only contract fields survive", set(tainted_record).issubset(RECORD_FIELDS), str(set(tainted_record)))
    check(
        "tainted: forbidden_field_stripped flagged",
        "forbidden_field_stripped" in tainted_record.get("warnings", []),
        str(tainted_record.get("warnings")),
    )
    assert_no_canary("tainted payload", tainted_payload)
    assert_no_canary("tainted normalize_safe_numeric_candidate", normalize_safe_numeric_candidate(tainted))
    assert_no_canary("tainted sidecar payload", map_safe_numeric_candidates_to_sidecar_payload([tainted]))
    # The tainted clean computation still recomputes correctly, with no canary leak.
    tainted_report = recompute_report_for_payload(tainted_payload)
    check("tainted: clean computation still verifies", tainted_report.get("status") == "passed", str(tainted_report.get("status")))
    assert_no_canary("tainted recompute report", tainted_report)
    tainted_artifact = build_quality_safety_job_artifact_payload(numeric_extraction_records=tainted_payload)
    assert_no_canary("tainted artifact payload", tainted_artifact)

    # --- 9. Deterministic serialization ---------------------------------------
    det_a = extract_quality_safety_numeric_records_from_candidates(all_method_candidates)
    det_b = extract_quality_safety_numeric_records_from_candidates(all_method_candidates)
    check("deterministic: identical serialization", serialized(det_a) == serialized(det_b))

    # --- 10. max_items caps candidates deterministically ----------------------
    many = [
        computation_candidate(
            cand_id=f"qs_num_cap_{i}",
            method="weighted_gini",
            inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
            value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
        )
        for i in range(5)
    ]
    capped = extract_quality_safety_numeric_records_from_candidates(many, max_items=2)
    assert_payload_shape("capped", capped)
    check("capped: record_count == 2", capped["summary"]["record_count"] == 2, serialized(capped["summary"]))
    check("capped: candidate_count == 5", capped["summary"]["candidate_count"] == 5)
    check("capped: dropped == 3", capped["summary"]["dropped_candidate_count"] == 3)
    check("capped: status partial", capped.get("status") == "partial", str(capped.get("status")))
    check("capped: max_items_reached warning", "max_items_reached" in capped.get("warnings", []))
    check(
        "capped: deterministic cap (first 2 ids)",
        [r["id"] for r in capped["records"]] == ["qs_num_cap_0", "qs_num_cap_1"],
        serialized([r["id"] for r in capped["records"]]),
    )

    # --- 11. Mixed list with a non-dict candidate drops safely ----------------
    mixed = [clean, "not a dict", {"id": "qs_num_bare", "fact_type": "numeric", "value": 0.5}]
    mixed_payload = extract_quality_safety_numeric_records_from_candidates(mixed)
    assert_payload_shape("mixed", mixed_payload)
    check("mixed: candidate_count 3", mixed_payload["summary"]["candidate_count"] == 3)
    check("mixed: record_count 2", mixed_payload["summary"]["record_count"] == 2)
    check("mixed: dropped 1", mixed_payload["summary"]["dropped_candidate_count"] == 1)
    check(
        "mixed: invalid_numeric_record_dropped warning",
        "invalid_numeric_record_dropped" in mixed_payload.get("warnings", []),
        str(mixed_payload.get("warnings")),
    )
    check("mixed: status warning", mixed_payload.get("status") == "warning", str(mixed_payload.get("status")))

    # --- 12. Caller input is not mutated --------------------------------------
    mutation_input = [
        copy.deepcopy(tainted),
        copy.deepcopy(confident_wrong),
        copy.deepcopy(no_id),
    ]
    snapshot = copy.deepcopy(mutation_input)
    extract_quality_safety_numeric_records_from_candidates(mutation_input)
    normalize_safe_numeric_candidate(mutation_input[0])
    map_safe_numeric_candidates_to_sidecar_payload(mutation_input)
    check("no mutation: caller input unchanged", mutation_input == snapshot)

    # --- 13. Sidecar wrapper compatibility (dict payload + bare list) ---------
    bare_list_records = clean_payload["records"]
    check(
        "sidecar: dict payload coerces to records list",
        _coerce_numeric_records(clean_payload) == bare_list_records,
    )
    check(
        "sidecar: bare records list coerces to itself",
        _coerce_numeric_records(bare_list_records) == bare_list_records,
    )
    check(
        "sidecar: map_ wrapper equals extract payload",
        serialized(map_safe_numeric_candidates_to_sidecar_payload([clean]))
        == serialized(extract_quality_safety_numeric_records_from_candidates([clean])),
    )

    # --- 14. Import hygiene / purity guard ------------------------------------
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

    # --- 15. Whole-run canary sweep -------------------------------------------
    assert_no_canary("final clean payload", clean_payload)
    assert_no_canary("final all payload", all_payload)
    assert_no_canary("final capped payload", capped)

    print(f"\ntest_quality_safety_safe_numeric_extractor: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
