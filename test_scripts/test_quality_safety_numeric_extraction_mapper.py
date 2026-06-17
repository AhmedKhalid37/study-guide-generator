#!/usr/bin/env python3
"""Tests for Slice 125 Quality Safety numeric extraction record mapper v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. Hostile canaries
below are synthetic markers used to prove forbidden content is stripped and never
echoed.

The mapper is pure/unwired: it maps caller-supplied sanitized numeric extraction
records into the existing producer extraction-bundle shape, which the Slice 117
fact-sheet producer and Slice 111 recompute verifier already accept. These tests
prove the round-trip recomputes correct claims, blocks wrong ones, never falsely
verifies bare observations, strips forbidden fields, degrades safely, and stays
import-pure.

Run:  python test_scripts/test_quality_safety_numeric_extraction_mapper.py
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
from pipeline.quality_safety_numeric_extraction_mapper import (  # noqa: E402
    ALLOWED_RECORD_FIELDS,
    FORBIDDEN_RECORD_FIELDS,
    build_empty_quality_safety_numeric_extraction_bundle,
    build_quality_safety_numeric_extraction_bundle,
    map_numeric_extraction_bundle_to_fact_sheet_input,
    normalize_quality_safety_numeric_extraction_record,
)
from pipeline.quality_safety_recompute_verifier import (  # noqa: E402
    SUPPORTED_METHODS,
    build_quality_safety_recompute_report,
)

PASS = 0
FAIL = 0

MODULE_PATH = REPO / "pipeline" / "quality_safety_numeric_extraction_mapper.py"

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_mapper1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_MAPPER_MARKER",
    "TABLE_TEXT_PRIVATE_MAPPER_MARKER",
    "CAPTION_PRIVATE_MAPPER_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_MAPPER_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MAPPER_MARKER",
    "source text private marker",
    "E=mc^2_private_formula_marker",
    "ZZSYNTH_MAPPER_PRIVATE_MARKER_ONLY",
)
FORBIDDEN_MARKERS = (
    "/home/fake_private",
    "C:\\fake_private",
    "https://",
    "Authorization",
    "Bearer",
    "sk_mapper",
    "data:image",
    "base64",
    "OCR_PRIVATE",
    "TABLE_TEXT_PRIVATE",
    "CAPTION_PRIVATE",
    "PROVIDER_PAYLOAD_PRIVATE",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MAPPER_MARKER",
    "source text private marker",
    "private_formula_marker",
    "ZZSYNTH_MAPPER_PRIVATE_MARKER_ONLY",
)

# Mirrors the module's closed record-warning vocabulary.
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
BUNDLE_WARNINGS = frozenset(
    {
        "component_missing",
        "empty_numeric_extraction",
        "malformed_numeric_extraction_input",
        "invalid_numeric_record_dropped",
        "max_items_reached",
    }
)
BUNDLE_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
SOURCE_QUALITIES = frozenset({"synthetic", "runtime_structural", "unknown"})

ALLOWED_IMPORTS = {
    "__future__",
    "math",
    "re",
    "typing",
    "pipeline.quality_safety_recompute_verifier",
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


def computation_record(
    *,
    rec_id: str = "qs_num_seed",
    concept_id: str = "qs_concept_1",
    label: str = "synthetic_score",
    method: str,
    inputs: dict[str, Any],
    value: float,
    tolerance: float = 0.02,
) -> dict[str, Any]:
    return {
        "id": rec_id,
        "concept_id": concept_id,
        "label": label,
        "fact_type": "numeric",
        "value": value,
        "unit": "ratio",
        "provenance": "computed",
        "confidence": "medium",
        "source_ref": "source_page_1",
        "page_ref": "page_1",
        "computation": {"method": method, "inputs": inputs},
        "tolerance": tolerance,
    }


def recompute_report_for(records: list[dict[str, Any]], *, lecture_id: str = "synthetic_fixture") -> dict[str, Any]:
    bundle = build_quality_safety_numeric_extraction_bundle(records)
    fact_sheet_input = map_numeric_extraction_bundle_to_fact_sheet_input(bundle, lecture_id=lecture_id)
    produced = run_quality_safety_fact_sheet_producer(fact_sheet_input)
    return build_quality_safety_recompute_report(produced.get("fact_sheet"))


def assert_bundle_shape(name: str, bundle: dict[str, Any]) -> None:
    check(f"{name}: kind", bundle.get("kind") == "quality_safety_numeric_extraction_bundle")
    check(f"{name}: version 1", bundle.get("version") == 1)
    check(f"{name}: status closed", bundle.get("status") in BUNDLE_STATUSES, str(bundle.get("status")))
    check(f"{name}: source_quality closed", bundle.get("source_quality") in SOURCE_QUALITIES, str(bundle.get("source_quality")))
    summary = bundle.get("summary", {})
    expected_keys = {
        "record_count",
        "numeric_fact_count",
        "computation_record_count",
        "bare_numeric_observation_count",
        "supported_method_count",
        "unsupported_method_count",
    }
    check(f"{name}: summary keys", set(summary) == expected_keys, str(set(summary)))
    check(
        f"{name}: summary non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()),
        str(summary),
    )
    check(f"{name}: bundle warnings closed", all(w in BUNDLE_WARNINGS for w in bundle.get("warnings", [])), str(bundle.get("warnings")))
    for record in bundle.get("numeric_records", []):
        check(
            f"{name}: record fields whitelisted",
            set(record).issubset(
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
            ),
            str(set(record)),
        )
        check(
            f"{name}: record warnings closed",
            all(w in RECORD_WARNINGS for w in record.get("warnings", [])),
            str(record.get("warnings")),
        )
    check(f"{name}: JSON-serializable", isinstance(serialized(bundle), str))


def main() -> int:
    # --- 1. Empty / missing / malformed top-level input degrades safely -------
    empty = build_quality_safety_numeric_extraction_bundle([])
    assert_bundle_shape("empty list", empty)
    check("empty list: skipped", empty.get("status") == "skipped", str(empty.get("status")))
    check("empty list: empty warning", "empty_numeric_extraction" in empty.get("warnings", []))

    none_bundle = build_quality_safety_numeric_extraction_bundle(None)
    assert_bundle_shape("none input", none_bundle)
    check("none input: skipped + component_missing", none_bundle.get("status") == "skipped" and "component_missing" in none_bundle.get("warnings", []))

    malformed = build_quality_safety_numeric_extraction_bundle("not a list")
    assert_bundle_shape("malformed input", malformed)
    check("malformed input: failed", malformed.get("status") == "failed", str(malformed.get("status")))
    check("malformed input: malformed warning", "malformed_numeric_extraction_input" in malformed.get("warnings", []))

    explicit_empty = build_empty_quality_safety_numeric_extraction_bundle()
    assert_bundle_shape("explicit empty", explicit_empty)
    check("explicit empty: skipped + component_missing", explicit_empty.get("status") == "skipped" and "component_missing" in explicit_empty.get("warnings", []))
    check("explicit empty: bad reason coerced", build_empty_quality_safety_numeric_extraction_bundle("evil").get("warnings") == ["component_missing"])

    check("normalize non-dict -> None", normalize_quality_safety_numeric_extraction_record("nope") is None)
    check("normalize None -> None", normalize_quality_safety_numeric_extraction_record(None) is None)

    # --- 2. One valid weighted_gini record recomputes (verified) --------------
    clean = computation_record(
        rec_id="qs_num_clean",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=SUPPORTED_METHOD_FIXTURES["weighted_gini"][1],
    )
    clean_bundle = build_quality_safety_numeric_extraction_bundle([clean])
    assert_bundle_shape("clean weighted_gini", clean_bundle)
    check("clean: status ok", clean_bundle.get("status") == "ok", str(clean_bundle.get("status")))
    check("clean: one computation record", clean_bundle["summary"]["computation_record_count"] == 1)
    clean_report = recompute_report_for([clean])
    passed = [c for c in clean_report.get("checks", []) if c.get("check_id") == "weighted_gini" and c.get("status") == "passed"]
    check("clean: weighted_gini verified", bool(passed), serialized(clean_report.get("checks")))
    check("clean: no blocking failure", not clean_report.get("blocking_failures"))
    check("clean: report passed", clean_report.get("status") == "passed", str(clean_report.get("status")))

    # --- 3. clean_real_case synthetic equivalent passes recompute -------------
    clean_real_records = [
        computation_record(
            rec_id="qs_num_real_a",
            concept_id="qs_concept_real",
            label="synthetic_clean_gini",
            method="weighted_gini",
            inputs={"groups": [{"a": 4, "b": 0}, {"a": 0, "b": 4}]},
            value=0.0,
        ),
        computation_record(
            rec_id="qs_num_real_b",
            concept_id="qs_concept_real",
            label="synthetic_clean_total_error",
            method="total_error",
            inputs={"misclassified_weight": 0.0},
            value=0.0,
        ),
    ]
    clean_real_report = recompute_report_for(clean_real_records)
    check("clean_real_case: report passed", clean_real_report.get("status") == "passed", str(clean_real_report.get("status")))
    check("clean_real_case: no blocking", not clean_real_report.get("blocking_failures"))
    check("clean_real_case: two verified", clean_real_report["summary"]["verified_fact_count"] == 2, serialized(clean_real_report["summary"]))
    assert_no_canary("clean_real_case report", clean_real_report)

    # --- 4. A wrong weighted_gini claim fails (blocking) ----------------------
    wrong = computation_record(
        rec_id="qs_num_wrong",
        method="weighted_gini",
        inputs=SUPPORTED_METHOD_FIXTURES["weighted_gini"][0],
        value=0.9,  # deliberately wrong vs recomputed 0.2
    )
    wrong_report = recompute_report_for([wrong])
    check(
        "wrong: recompute blocking failure raised",
        any(item.get("check_id") == "weighted_gini" for item in wrong_report.get("blocking_failures") or []),
        serialized(wrong_report.get("blocking_failures")),
    )
    check("wrong: report failed", wrong_report.get("status") == "failed", str(wrong_report.get("status")))

    # --- 5. single_confident_wrong_numeric_case synthetic equivalent ----------
    confident_wrong = {
        "id": "qs_num_confident_wrong",
        "concept_id": "qs_concept_confident",
        "label": "synthetic_confident_wrong",
        "fact_type": "numeric",
        "value": 0.95,  # confidently claimed, but wrong
        "unit": "ratio",
        "provenance": "computed",
        "confidence": "high",
        "source_ref": "source_page_3",
        "computation": {"method": "cross_entropy", "inputs": {"probability": 0.5}},  # true value ~0.6931
        "tolerance": 0.01,
    }
    cw_report = recompute_report_for([confident_wrong])
    check("confident_wrong: report failed", cw_report.get("status") == "failed", str(cw_report.get("status")))
    check("confident_wrong: blocking failure raised", bool(cw_report.get("blocking_failures")))
    # No leak and no contradiction: a failed check must not also be reported verified.
    check(
        "confident_wrong: not verified",
        cw_report["summary"]["verified_fact_count"] == 0 and cw_report["summary"]["failed_fact_count"] == 1,
        serialized(cw_report["summary"]),
    )
    assert_no_canary("confident_wrong report", cw_report)

    # --- 6. All supported method tokens accepted when structurally valid ------
    all_method_records = [
        computation_record(
            rec_id=f"qs_num_{method}",
            concept_id="qs_concept_methods",
            label=f"synthetic_{method}",
            method=method,
            inputs=inputs,
            value=value,
        )
        for method, (inputs, value) in SUPPORTED_METHOD_FIXTURES.items()
    ]
    all_bundle = build_quality_safety_numeric_extraction_bundle(all_method_records)
    assert_bundle_shape("all supported methods", all_bundle)
    check(
        "all methods: every supported method maps to a computation record",
        all_bundle["summary"]["computation_record_count"] == len(SUPPORTED_METHODS),
        serialized(all_bundle["summary"]),
    )
    check("all methods: bundle status ok", all_bundle.get("status") == "ok", str(all_bundle.get("status")))
    all_report = recompute_report_for(all_method_records)
    check(
        "all methods: all verified together",
        all_report.get("status") == "passed" and all_report["summary"]["verified_fact_count"] == len(SUPPORTED_METHODS),
        serialized(all_report["summary"]),
    )
    check("all methods: no blocking", not all_report.get("blocking_failures"))

    # --- 7. Bare numeric observation: never falsely recompute-verified --------
    bare = {
        "id": "qs_num_bare",
        "concept_id": "qs_concept_bare",
        "label": "synthetic_count",
        "fact_type": "numeric",
        "value": 42,
        "confidence": "high",
        "provenance": "extracted_high",
        "source_ref": "source_page_2",
    }
    bare_bundle = build_quality_safety_numeric_extraction_bundle([bare])
    assert_bundle_shape("bare observation", bare_bundle)
    check("bare: no computation block", bare_bundle["numeric_records"][0].get("computation") is None)
    check("bare: counted as bare observation", bare_bundle["summary"]["bare_numeric_observation_count"] == 1)
    bare_report = recompute_report_for([bare])
    check("bare: not recomputable", bare_report["summary"]["recomputable_fact_count"] == 0, serialized(bare_report["summary"]))
    check("bare: not verified", bare_report["summary"]["verified_fact_count"] == 0)
    check("bare: not blocking", not bare_report.get("blocking_failures"))

    # --- 8. Unsupported method degrades safely (demoted, never verified) ------
    unsupported = computation_record(
        rec_id="qs_num_unsupported",
        method="weighted_gini",
        inputs={"groups": [{"yes": 1}]},
        value=0.0,
    )
    unsupported["computation"] = {"method": "made_up_method", "inputs": {"x": 1}}
    unsupported_bundle = build_quality_safety_numeric_extraction_bundle([unsupported])
    assert_bundle_shape("unsupported method", unsupported_bundle)
    record = unsupported_bundle["numeric_records"][0]
    check("unsupported: computation demoted to null", record.get("computation") is None)
    check("unsupported: warning present", "unsupported_method" in record.get("warnings", []))
    check("unsupported: counted", unsupported_bundle["summary"]["unsupported_method_count"] == 1)
    unsupported_report = recompute_report_for([unsupported])
    check("unsupported: not verified", unsupported_report["summary"]["verified_fact_count"] == 0)
    check("unsupported: not blocking", not unsupported_report.get("blocking_failures"))

    # --- 9. Malformed computation inputs degrade safely (demoted) -------------
    malformed_inputs = computation_record(
        rec_id="qs_num_malformed",
        method="total_error",
        inputs={"misclassified_weight": "E=mc^2_private_formula_marker"},
        value=0.3,
    )
    malformed_bundle = build_quality_safety_numeric_extraction_bundle([malformed_inputs])
    assert_bundle_shape("malformed inputs", malformed_bundle)
    mrecord = malformed_bundle["numeric_records"][0]
    check("malformed inputs: computation demoted", mrecord.get("computation") is None)
    check("malformed inputs: warning present", "malformed_computation" in mrecord.get("warnings", []))
    assert_no_canary("malformed inputs bundle", malformed_bundle)
    malformed_report = recompute_report_for([malformed_inputs])
    check("malformed inputs: not verified", malformed_report["summary"]["verified_fact_count"] == 0)
    check("malformed inputs: not blocking", not malformed_report.get("blocking_failures"))

    # --- 10. Numeric strings / NaN / Infinity rejected ------------------------
    bad_values = [
        {"concept_id": "c", "label": "l", "fact_type": "numeric", "value": "5"},
        {"concept_id": "c", "label": "l", "fact_type": "numeric", "value": float("nan")},
        {"concept_id": "c", "label": "l", "fact_type": "numeric", "value": float("inf")},
        {"concept_id": "c", "label": "l", "fact_type": "numeric", "value": True},
    ]
    bad_bundle = build_quality_safety_numeric_extraction_bundle(bad_values)
    assert_bundle_shape("bad numeric values", bad_bundle)
    for rec in bad_bundle["numeric_records"]:
        check("bad value: rejected to null", rec.get("value") is None, str(rec.get("value")))
        check("bad value: invalid_numeric_value warning", "invalid_numeric_value" in rec.get("warnings", []))

    # --- 11. Invalid tolerance rejected / capped ------------------------------
    over_cap = computation_record(
        rec_id="qs_num_tol",
        method="total_error",
        inputs={"misclassified_weight": 0.3},
        value=0.3,
        tolerance=5.0,  # above (0, 1] cap
    )
    tol_bundle = build_quality_safety_numeric_extraction_bundle([over_cap])
    trecord = tol_bundle["numeric_records"][0]
    check("tolerance over cap: null", trecord.get("tolerance") is None, str(trecord.get("tolerance")))
    check("tolerance over cap: invalid_tolerance warning", "invalid_tolerance" in trecord.get("warnings", []))
    negative_tol = build_quality_safety_numeric_extraction_bundle(
        [computation_record(method="total_error", inputs={"misclassified_weight": 0.3}, value=0.3, tolerance=-1.0)]
    )["numeric_records"][0]
    check("tolerance negative: null + warning", negative_tol.get("tolerance") is None and "invalid_tolerance" in negative_tol.get("warnings", []))
    good_tol = build_quality_safety_numeric_extraction_bundle(
        [computation_record(method="total_error", inputs={"misclassified_weight": 0.3}, value=0.3, tolerance=0.5)]
    )["numeric_records"][0]
    check("tolerance valid: preserved", good_tol.get("tolerance") == 0.5)

    # --- 12. Forbidden fields stripped; no canary leaks anywhere --------------
    tainted = computation_record(
        rec_id="qs_num_tainted",
        method="cross_entropy",
        inputs={"probability": 0.5},
        value=0.6931471805599453,
    )
    for field in FORBIDDEN_RECORD_FIELDS:
        tainted[field] = "ZZSYNTH_MAPPER_PRIVATE_MARKER_ONLY"
    tainted["paths"] = "/home/fake_private/source-deck.pdf"
    tainted["evidence_quotes"] = "EVIDENCE_QUOTE_PRIVATE_MAPPER_MARKER"
    tainted_bundle = build_quality_safety_numeric_extraction_bundle([tainted])
    assert_bundle_shape("tainted record", tainted_bundle)
    trec = tainted_bundle["numeric_records"][0]
    check(
        "forbidden: no forbidden field on record",
        all(field not in trec for field in FORBIDDEN_RECORD_FIELDS),
        str([f for f in FORBIDDEN_RECORD_FIELDS if f in trec]),
    )
    check("forbidden: stripped warning present", "forbidden_field_stripped" in trec.get("warnings", []))
    assert_no_canary("tainted bundle", tainted_bundle)
    tainted_input = map_numeric_extraction_bundle_to_fact_sheet_input(tainted_bundle)
    tainted_produced = run_quality_safety_fact_sheet_producer(tainted_input)
    assert_no_canary("tainted fact-sheet input", tainted_input)
    assert_no_canary("tainted produced sheet", tainted_produced)
    assert_no_canary("tainted recompute report", recompute_report_for([tainted]))
    # The tainted record's clean computation still recomputes correctly.
    check("forbidden: clean computation still verifies", recompute_report_for([tainted]).get("status") == "passed")

    # --- 13. IDs and source/page refs sanitized -------------------------------
    sanitize = {
        "id": "/home/fake_private/source-deck.pdf",
        "concept_id": "Authorization: Bearer sk_mapper1234567890",
        "label": "OCR_PRIVATE_MAPPER_MARKER",
        "fact_type": "numeric",
        "value": 1.0,
        "unit": "https://private.invalid/source",
        "source_ref": "/home/fake_private/x",
        "page_ref": "C:\\fake_private\\y",
    }
    sanitize_bundle = build_quality_safety_numeric_extraction_bundle([sanitize])
    assert_bundle_shape("sanitized record", sanitize_bundle)
    srec = sanitize_bundle["numeric_records"][0]
    check("sanitize: id replaced with synthetic", srec.get("id") == "qs_num_0001", str(srec.get("id")))
    check("sanitize: concept_id nulled", srec.get("concept_id") is None)
    check("sanitize: label replaced", srec.get("label") == "qs_num_label_0001", str(srec.get("label")))
    check("sanitize: unit nulled", srec.get("unit") is None)
    check("sanitize: source_ref nulled", srec.get("source_ref") is None)
    check("sanitize: page_ref nulled", srec.get("page_ref") is None)
    assert_no_canary("sanitized bundle", sanitize_bundle)

    # --- 14. Deterministic serialization --------------------------------------
    det_records = [
        computation_record(rec_id=f"qs_num_det_{i}", method=method, inputs=inputs, value=value)
        for i, (method, (inputs, value)) in enumerate(SUPPORTED_METHOD_FIXTURES.items())
    ]
    first = build_quality_safety_numeric_extraction_bundle(det_records)
    second = build_quality_safety_numeric_extraction_bundle(copy.deepcopy(det_records))
    check("deterministic: identical output", serialized(first) == serialized(second))
    check(
        "deterministic: mapping stable",
        serialized(map_numeric_extraction_bundle_to_fact_sheet_input(first))
        == serialized(map_numeric_extraction_bundle_to_fact_sheet_input(second)),
    )

    # --- 15. max_items caps records deterministically -------------------------
    many = [computation_record(rec_id=f"qs_num_m_{i}", method="total_error", inputs={"misclassified_weight": 0.1}, value=0.1) for i in range(5)]
    capped = build_quality_safety_numeric_extraction_bundle(many, max_items=2)
    assert_bundle_shape("max_items capped", capped)
    check("max_items: record_count capped", capped["summary"]["record_count"] == 2, serialized(capped["summary"]))
    check("max_items: status partial", capped.get("status") == "partial", str(capped.get("status")))
    check("max_items: warning present", "max_items_reached" in capped.get("warnings", []))

    # --- 16. Non-dict records dropped without crashing ------------------------
    mixed = [computation_record(method="total_error", inputs={"misclassified_weight": 0.1}, value=0.1), "not a dict", 123, None]
    mixed_bundle = build_quality_safety_numeric_extraction_bundle(mixed)
    assert_bundle_shape("mixed records", mixed_bundle)
    check("mixed: one valid record kept", mixed_bundle["summary"]["record_count"] == 1)
    check("mixed: dropped warning", "invalid_numeric_record_dropped" in mixed_bundle.get("warnings", []))
    check("mixed: status warning", mixed_bundle.get("status") == "warning", str(mixed_bundle.get("status")))

    # --- 17. Caller input is never mutated ------------------------------------
    mutation_records = [
        computation_record(rec_id=f"qs_num_mut_{i}", method=method, inputs=inputs, value=value)
        for i, (method, (inputs, value)) in enumerate(SUPPORTED_METHOD_FIXTURES.items())
    ]
    mutation_records.append({"raw_text": "ZZSYNTH_MAPPER_PRIVATE_MARKER_ONLY", "fact_type": "numeric", "value": 1.0})
    snapshot = copy.deepcopy(mutation_records)
    _ = build_quality_safety_numeric_extraction_bundle(mutation_records)
    _ = map_numeric_extraction_bundle_to_fact_sheet_input(build_quality_safety_numeric_extraction_bundle(mutation_records))
    _ = run_quality_safety_fact_sheet_producer(
        map_numeric_extraction_bundle_to_fact_sheet_input(build_quality_safety_numeric_extraction_bundle(mutation_records))
    )
    check("no mutation: caller records unchanged", mutation_records == snapshot)

    # --- 18. Import hygiene / purity guard ------------------------------------
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
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
    check("purity: only allowed imports", imported_modules.issubset(ALLOWED_IMPORTS), str(imported_modules - ALLOWED_IMPORTS))
    forbidden_hits = [
        part
        for part in FORBIDDEN_IMPORT_PARTS
        for module in imported_modules
        if part in module.split(".")
    ]
    check("purity: no forbidden runtime imports", not forbidden_hits, str(forbidden_hits))
    check("purity: no FastAPI/frontend/render/OCR/job/provider imports", not forbidden_hits)
    check("purity: allow-list mirrors module", ALLOWED_RECORD_FIELDS and FORBIDDEN_RECORD_FIELDS)

    print(f"\ntest_quality_safety_numeric_extraction_mapper: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
