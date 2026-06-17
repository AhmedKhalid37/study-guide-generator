#!/usr/bin/env python3
"""Tests for Slice 121 Quality Safety extraction-bundle adapter v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. Hostile values below
are synthetic canaries used purely to prove they are excluded from output.

Run:  python test_scripts/test_quality_safety_extraction_bundle_adapter.py
"""
from __future__ import annotations

import ast
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_extraction_bundle_adapter import (  # noqa: E402
    BUNDLE_KIND,
    BUNDLE_STATUSES,
    RECORD_STATUSES,
    RECORD_TYPES,
    WARNING_ORDER,
    build_empty_quality_safety_extraction_coverage_bundle,
    build_quality_safety_extraction_coverage_bundle_from_artifacts,
    normalize_quality_safety_extraction_coverage_bundle,
)
from pipeline.quality_safety_fact_sheet_producer import (  # noqa: E402
    run_quality_safety_fact_sheet_producer,
)

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_adapter1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_ADAPTER_MARKER",
    "TABLE_TEXT_PRIVATE_ADAPTER_MARKER",
    "CAPTION_PRIVATE_ADAPTER_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_ADAPTER_MARKER",
    "UPLOADED_QUALITY_SPEC_PRIVATE_FILENAME",
    "EVIDENCE_QUOTE_PRIVATE_MARKER",
    "source text private marker",
    "E=mc^2_private_formula_marker",
    "Quarterly Private Deck Title",
)
FORBIDDEN_MARKERS = (
    "/home/fake_private",
    "C:\\fake_private",
    "https://",
    "Authorization",
    "Bearer",
    "sk_adapter",
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
    "Quarterly Private",
    "source-deck",
    "uploaded-source",
)
WARNING_VOCAB = set(WARNING_ORDER)
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
    "run_llm_job",
    "chandra",
    "mistral",
    "gemini",
    "socket",
    "subprocess",
    "os",
    "pathlib",
    "json",
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


def assert_summary_shape(name: str, bundle: dict[str, Any]) -> None:
    summary = bundle.get("summary", {})
    expected = {
        "source_count",
        "page_count",
        "selected_page_count",
        "visual_count",
        "table_count",
        "coverage_item_count",
        "numeric_observation_count",
    }
    check(f"{name}: summary keys", set(summary) == expected, str(summary))
    non_null_counts = [
        v
        for k, v in summary.items()
        if k != "selected_page_count" and v is not None
    ]
    check(
        f"{name}: counts non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in non_null_counts),
        str(summary),
    )
    sel = summary.get("selected_page_count")
    check(
        f"{name}: selected_page_count int|null",
        sel is None or (isinstance(sel, int) and not isinstance(sel, bool) and sel >= 0),
        str(sel),
    )
    check(f"{name}: numeric_observation_count is 0", summary.get("numeric_observation_count") == 0)


def assert_bundle_shape(name: str, bundle: dict[str, Any]) -> None:
    check(f"{name}: kind", bundle.get("kind") == BUNDLE_KIND)
    check(f"{name}: version 1", bundle.get("version") == 1)
    check(f"{name}: status closed", bundle.get("status") in BUNDLE_STATUSES, str(bundle.get("status")))
    check(
        f"{name}: source_quality closed",
        bundle.get("source_quality") in {"synthetic", "runtime_structural", "unknown"},
    )
    check(f"{name}: numeric_observations empty", bundle.get("numeric_observations") == [])
    check(
        f"{name}: warnings closed",
        all(w in WARNING_VOCAB for w in bundle.get("warnings", [])),
        str(bundle.get("warnings")),
    )
    assert_summary_shape(name, bundle)
    for record in bundle.get("coverage_records", []):
        check(f"{name}: record_type closed", record.get("record_type") in RECORD_TYPES, str(record))
        check(f"{name}: record status closed", record.get("status") in RECORD_STATUSES, str(record))
        check(
            f"{name}: record id safe",
            isinstance(record.get("id"), str) and record["id"].startswith("qs_extract_"),
            str(record.get("id")),
        )
        check(
            f"{name}: record source_ref safe",
            record.get("source_ref") in {"unknown", "page_range"}
            or (isinstance(record.get("source_ref"), str) and record["source_ref"].startswith("source_")),
            str(record.get("source_ref")),
        )
        page_ref = record.get("page_ref")
        check(
            f"{name}: record page_ref safe",
            page_ref is None
            or page_ref in {"unknown", "page_range"}
            or (isinstance(page_ref, str) and page_ref.startswith("page_")),
            str(page_ref),
        )
        counts = record.get("counts", {})
        check(
            f"{name}: record counts keys",
            set(counts) == {"page_count", "selected_page_count", "visual_count", "table_count"},
            str(counts),
        )
        for value in counts.values():
            check(
                f"{name}: count int|null non-negative",
                value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0),
                str(value),
            )
        check(
            f"{name}: record warnings closed",
            all(w in WARNING_VOCAB for w in record.get("warnings", [])),
            str(record.get("warnings")),
        )


# --- Synthetic fixtures -------------------------------------------------------


def coverage_report() -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "source_coverage_report",
        "status": "partial",
        "summary": {"source_count": 2, "total_pages": 5},
        "sources": [
            {
                "source_index": 1,
                "source_type": "pdf",
                "status": "complete",
                "page_count": 3,
                "covered_page_count": 3,
                "visual_candidate_page_count": 2,
            },
            {
                "source_index": 2,
                "source_type": "pdf",
                "status": "partial",
                "page_count": 2,
                "covered_page_count": 1,
                "visual_candidate_page_count": 0,
            },
        ],
        "warnings": [],
    }


def visual_plan() -> dict[str, Any]:
    return {"version": 1, "kind": "visual_inclusion_plan", "status": "completed", "included_count": 4}


def table_manifest() -> dict[str, Any]:
    return {"version": 1, "kind": "table_candidates_manifest", "status": "completed", "candidates": [1, 2, 3]}


def table_policy() -> dict[str, Any]:
    return {"version": 1, "kind": "table_reconstruction_policy", "status": "completed", "actionable_count": 1}


# --- Tests --------------------------------------------------------------------


def test_empty_and_malformed() -> None:
    empty = build_empty_quality_safety_extraction_coverage_bundle()
    assert_bundle_shape("empty", empty)
    check("empty status skipped", empty["status"] == "skipped")
    check("empty component_missing", "component_missing" in empty["warnings"])
    check("empty has no records", empty["coverage_records"] == [])

    # All-None artifacts → component_missing skipped.
    none_built = build_quality_safety_extraction_coverage_bundle_from_artifacts()
    check("all-none skipped", none_built["status"] == "skipped")
    check("all-none component_missing", "component_missing" in none_built["warnings"])

    for item in (None, 7, 1.5, [], "x", object()):
        built = build_quality_safety_extraction_coverage_bundle_from_artifacts(source_coverage_report=item)
        check(f"build never raises {type(item).__name__}", built["kind"] == BUNDLE_KIND)
        check(f"build malformed degrades {type(item).__name__}", built["status"] in {"skipped", "warning", "failed"})
        normd = normalize_quality_safety_extraction_coverage_bundle(item)
        check(f"normalize never raises {type(item).__name__}", normd["kind"] == BUNDLE_KIND)
        assert_bundle_shape(f"normalize {type(item).__name__}", normd)

    not_dict = normalize_quality_safety_extraction_coverage_bundle(42)
    check("normalize non-dict input_not_dict", "input_not_dict" in not_dict["warnings"])


def test_coverage_report_structural_counts() -> None:
    bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        source_coverage_report=coverage_report(),
        visual_inclusion_plan=visual_plan(),
        table_candidates_manifest=table_manifest(),
        table_reconstruction_policy=table_policy(),
    )
    assert_bundle_shape("coverage", bundle)
    check("coverage source_quality runtime_structural", bundle["source_quality"] == "runtime_structural")
    check("coverage source_count 2", bundle["summary"]["source_count"] == 2)
    check("coverage page_count 5", bundle["summary"]["page_count"] == 5)
    # visual: 2 (source1 candidate pages) + 4 (plan) = 6
    check("coverage visual_count 6", bundle["summary"]["visual_count"] == 6)
    check("coverage table_count 3", bundle["summary"]["table_count"] == 3)
    check("coverage item count", bundle["summary"]["coverage_item_count"] == len(bundle["coverage_records"]))
    types = [r["record_type"] for r in bundle["coverage_records"]]
    check("coverage has source records", types.count("source") == 2)
    check("coverage has visual record", "visual" in types)
    check("coverage has table record", "table" in types)
    refs = [r["source_ref"] for r in bundle["coverage_records"] if r["record_type"] == "source"]
    check("coverage source refs synthetic", refs == ["source_1", "source_2"], str(refs))
    ids = [r["id"] for r in bundle["coverage_records"]]
    check("coverage ids unique sequential", ids == [f"qs_extract_{i:04d}" for i in range(1, len(ids) + 1)], str(ids))


def test_numeric_observations_never_recovered() -> None:
    bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        source_coverage_report=coverage_report()
    )
    check("numeric_observations empty list", bundle["numeric_observations"] == [])
    check("numeric_observation_count 0", bundle["summary"]["numeric_observation_count"] == 0)
    check(
        "numeric not recoverable warning when records present",
        "numeric_observations_not_recoverable" in bundle["warnings"],
    )
    # Even if a hostile caller injects numeric_observations into a bundle, they are dropped.
    injected = normalize_quality_safety_extraction_coverage_bundle(
        {
            "kind": BUNDLE_KIND,
            "coverage_records": [],
            "numeric_observations": [{"value": 0.123456, "label": HOSTILE_CANARIES[12]}],
        }
    )
    check("injected numeric observations dropped", injected["numeric_observations"] == [])
    check("injected numeric obs count 0", injected["summary"]["numeric_observation_count"] == 0)
    check(
        "injected numeric obs warning",
        "numeric_observations_not_recoverable" in injected["warnings"],
    )
    assert_no_canary("injected numeric observations", injected)


def test_raw_names_and_text_excluded() -> None:
    # Hostile fields placed where the adapter must never read names/text.
    hostile = coverage_report()
    hostile["sources"][0]["source_name"] = HOSTILE_CANARIES[0]
    hostile["sources"][0]["title"] = HOSTILE_CANARIES[13]
    hostile["sources"][0]["path"] = HOSTILE_CANARIES[1]
    hostile["sources"][0]["url"] = HOSTILE_CANARIES[2]
    hostile["sources"][0]["ocr_text"] = HOSTILE_CANARIES[5]
    hostile["sources"][1]["caption"] = HOSTILE_CANARIES[7]
    hostile["sources"][1]["table_text"] = HOSTILE_CANARIES[6]
    hostile["provider_payload"] = HOSTILE_CANARIES[8]
    bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(source_coverage_report=hostile)
    assert_no_canary("hostile coverage report", bundle)
    assert_bundle_shape("hostile coverage", bundle)
    # Structural counts still recovered.
    check("hostile still counts pages", bundle["summary"]["page_count"] == 5)

    # Hostile pre-built bundle through normalize: bad refs/ids/types are sanitized.
    hostile_bundle = {
        "kind": BUNDLE_KIND,
        "status": "definitely_not_a_status",
        "source_quality": HOSTILE_CANARIES[11],
        "coverage_records": [
            {
                "id": HOSTILE_CANARIES[0],
                "source_ref": HOSTILE_CANARIES[0],
                "page_ref": HOSTILE_CANARIES[1],
                "record_type": "totally_made_up",
                "status": "leak_status",
                "counts": {
                    "page_count": HOSTILE_CANARIES[2],
                    "selected_page_count": -5,
                    "visual_count": math.inf,
                    "table_count": 2,
                },
                "warnings": [HOSTILE_CANARIES[3], "unsafe_field_excluded"],
            }
        ],
        "warnings": [HOSTILE_CANARIES[4]],
    }
    normd = normalize_quality_safety_extraction_coverage_bundle(hostile_bundle)
    assert_no_canary("hostile pre-built bundle", normd)
    assert_bundle_shape("hostile normalize", normd)
    rec = normd["coverage_records"][0]
    check("hostile id regenerated", rec["id"].startswith("qs_extract_"))
    check("hostile source_ref unknown", rec["source_ref"] == "unknown")
    check("hostile page_ref dropped", rec["page_ref"] is None)
    check("hostile record_type defaulted", rec["record_type"] in RECORD_TYPES)
    check("hostile status unknown", rec["status"] == "unknown")
    check("hostile table_count kept", rec["counts"]["table_count"] == 2)
    check("hostile source_quality coerced", normd["source_quality"] == "unknown")


def test_mixed_page_ref_shape() -> None:
    # Extraction metadata path with per-page refs in differing shapes.
    metadata = {
        "kind": "extraction_metadata",
        "status": "completed",
        "sources": [
            {
                "status": "completed",
                "page_count": 3,
                "selected_page_count": 2,
                "source": HOSTILE_CANARIES[0],  # name must never be echoed
                "pages": [
                    {"page": 1},
                    {"page": 2},
                    {"page_ref": "page_range"},
                ],
            }
        ],
    }
    bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(extraction_metadata=metadata)
    assert_bundle_shape("mixed page ref", bundle)
    assert_no_canary("mixed page ref", bundle)
    check("mixed page ref warning emitted", "mixed_page_ref_shape" in bundle["warnings"])
    check("extraction name excluded warning", "source_name_excluded" in bundle["warnings"])
    page_refs = sorted(
        r["page_ref"] for r in bundle["coverage_records"] if r["record_type"] == "page"
    )
    check("page refs are closed tokens", page_refs == ["page_1", "page_2", "page_range"], str(page_refs))
    check("selected_page_count recovered", bundle["summary"]["selected_page_count"] == 2)


def test_visual_and_table_count_extraction() -> None:
    only_visual = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        visual_inclusion_plan={"status": "completed", "assets": [0, 0, 0, 0, 0]}
    )
    visual_rec = [r for r in only_visual["coverage_records"] if r["record_type"] == "visual"][0]
    check("visual count from list", visual_rec["counts"]["visual_count"] == 5)

    only_table = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        table_candidates_manifest={"status": "completed", "candidate_count": 7}
    )
    table_rec = [r for r in only_table["coverage_records"] if r["record_type"] == "table"][0]
    check("table count from int key", table_rec["counts"]["table_count"] == 7)

    policy_only = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        table_reconstruction_policy={"status": "skipped", "actionable_count": 0}
    )
    policy_rec = [r for r in policy_only["coverage_records"] if r["record_type"] == "table"][0]
    check("table count from policy", policy_rec["counts"]["table_count"] == 0)
    check("table policy status mapped", policy_rec["status"] == "skipped")


def test_max_items_caps_records() -> None:
    sources = [
        {"source_index": i, "source_type": "pdf", "status": "complete", "page_count": 1, "covered_page_count": 1, "visual_candidate_page_count": 0}
        for i in range(1, 11)
    ]
    report = {"kind": "source_coverage_report", "status": "completed", "summary": {}, "sources": sources, "warnings": []}
    capped = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        source_coverage_report=report, max_items=3
    )
    check("max_items status partial", capped["status"] == "partial", serialized(capped["status"]))
    check("max_items warning", "max_items_reached" in capped["warnings"])
    check("records capped to 3", len(capped["coverage_records"]) == 3, str(len(capped["coverage_records"])))
    # deterministic capping
    again = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        source_coverage_report=report, max_items=3
    )
    check("max_items deterministic", serialized(capped) == serialized(again))


def test_no_mutation() -> None:
    report = coverage_report()
    snapshot = copy.deepcopy(report)
    build_quality_safety_extraction_coverage_bundle_from_artifacts(source_coverage_report=report)
    check("caller coverage report not mutated", report == snapshot)

    bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(source_coverage_report=coverage_report())
    bundle_snapshot = copy.deepcopy(bundle)
    normalize_quality_safety_extraction_coverage_bundle(bundle)
    check("caller bundle not mutated by normalize", bundle == bundle_snapshot)


def test_deterministic_and_idempotent() -> None:
    a = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        source_coverage_report=coverage_report(),
        visual_inclusion_plan=visual_plan(),
        table_candidates_manifest=table_manifest(),
    )
    b = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        source_coverage_report=coverage_report(),
        visual_inclusion_plan=visual_plan(),
        table_candidates_manifest=table_manifest(),
    )
    check("deterministic build", serialized(a) == serialized(b))
    check("idempotent normalize", serialized(normalize_quality_safety_extraction_coverage_bundle(a)) == serialized(a))


def test_no_leak_deep_walk() -> None:
    metadata = {
        "kind": "extraction_metadata",
        "status": "completed",
        "sources": [
            {
                "status": "completed",
                "page_count": 2,
                "source": HOSTILE_CANARIES[0],
                "title": HOSTILE_CANARIES[13],
                "ocr_text": HOSTILE_CANARIES[5],
                "pages": [{"page": 1, "caption": HOSTILE_CANARIES[7]}, {"page": 2}],
            }
        ],
        "provider_payload": HOSTILE_CANARIES[8],
    }
    bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        extraction_metadata=metadata,
        source_coverage_report={"sources": [{"status": "complete", "page_count": 2, "evidence": HOSTILE_CANARIES[10]}]},
        visual_inclusion_plan={"status": "completed", "included_count": 2, "caption": HOSTILE_CANARIES[7]},
        table_candidates_manifest={"status": "completed", "candidate_count": 1, "table_text": HOSTILE_CANARIES[6]},
    )
    assert_no_canary("deep walk build", bundle)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            for marker in FORBIDDEN_MARKERS:
                check(f"no-leak walk excludes {marker[:18]!r}", marker not in node, node[:40])

    walk(bundle)


def test_producer_compatibility() -> None:
    bundle = build_quality_safety_extraction_coverage_bundle_from_artifacts(
        source_coverage_report=coverage_report(),
        visual_inclusion_plan=visual_plan(),
        table_candidates_manifest=table_manifest(),
    )
    # The producer must safely consume our coverage bundle. v1 yields no concepts,
    # so the producer degrades to an empty/partial/skipped fact sheet — never a
    # crash and never a leak.
    result = run_quality_safety_fact_sheet_producer(bundle)
    check("producer returns result kind", result["kind"] == "quality_safety_fact_sheet_producer_result")
    check("producer status closed", result["status"] in {"completed", "warning", "failed", "skipped", "partial"})
    check("producer produced no facts from coverage", result["summary"]["produced_fact_count"] == 0)
    check("producer fact sheet present", result["fact_sheet"]["kind"] == "quality_safety_fact_sheet")
    assert_no_canary("producer from coverage bundle", result)

    # Empty bundle also consumed safely.
    empty_result = run_quality_safety_fact_sheet_producer(
        build_empty_quality_safety_extraction_coverage_bundle()
    )
    check(
        "producer consumes empty bundle",
        empty_result["status"] in {"completed", "skipped", "warning"}
        and empty_result["summary"]["produced_fact_count"] == 0,
    )
    assert_no_canary("producer from empty bundle", empty_result)


def test_import_hygiene() -> None:
    source = (REPO / "pipeline" / "quality_safety_extraction_bundle_adapter.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    for item in imports:
        for forbidden in FORBIDDEN_IMPORT_PARTS:
            check(f"import {item!r} avoids {forbidden!r}", forbidden not in item.lower().split("."))
    check("imports allowed-only", set(imports) <= ALLOWED_IMPORTS, str(imports))


def run() -> int:
    test_empty_and_malformed()
    test_coverage_report_structural_counts()
    test_numeric_observations_never_recovered()
    test_raw_names_and_text_excluded()
    test_mixed_page_ref_shape()
    test_visual_and_table_count_extraction()
    test_max_items_caps_records()
    test_no_mutation()
    test_deterministic_and_idempotent()
    test_no_leak_deep_walk()
    test_producer_compatibility()
    test_import_hygiene()
    print(f"\nquality_safety_extraction_bundle_adapter: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
