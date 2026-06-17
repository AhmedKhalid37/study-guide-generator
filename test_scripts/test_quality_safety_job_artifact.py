#!/usr/bin/env python3
"""Tests for Slice 118 Quality Safety advisory job artifact v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_job_artifact import (  # noqa: E402
    ARTIFACT_NAME,
    build_quality_safety_job_artifact_payload,
    write_quality_safety_job_artifact,
)

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_jobartifact1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_JOB_ARTIFACT_MARKER",
    "TABLE_TEXT_PRIVATE_JOB_ARTIFACT_MARKER",
    "CAPTION_PRIVATE_JOB_ARTIFACT_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_JOB_ARTIFACT_MARKER",
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
    "sk_jobartifact",
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
    "CANDIDATE_PRIVATE_TEXT_MARKER",
)
JOB_WARNINGS = {
    "candidate_markdown_missing",
    "extraction_bundle_missing",
    "fact_sheet_component_missing",
    "recompute_component_missing",
    "canonical_component_missing",
    "extraction_coverage_missing",
    "extraction_coverage_degraded",
    "numeric_extraction_missing",
    "numeric_extraction_degraded",
    "artifact_write_failed",
    "component_degraded",
    "unsafe_metadata_dropped",
    "max_items_reached",
}
EXTRACTION_COVERAGE_STATUSES = {"ok", "warning", "skipped", "partial", "failed"}
NUMERIC_EXTRACTION_STATUSES = {"ok", "warning", "skipped", "partial", "failed"}
NUMERIC_BUNDLE_WARNINGS = {
    "component_missing",
    "empty_numeric_extraction",
    "malformed_numeric_extraction_input",
    "invalid_numeric_record_dropped",
    "max_items_reached",
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
    "chandra",
    "mistral",
    "gemini",
    "socket",
    "subprocess",
)
ALLOWED_IMPORTS = {
    "__future__",
    "json",
    "pathlib",
    "typing",
    "pipeline.quality_safety_canonical_matcher",
    "pipeline.quality_safety_extraction_bundle_adapter",
    "pipeline.quality_safety_fact_sheet_producer",
    "pipeline.quality_safety_leak_scanner",
    "pipeline.quality_safety_numeric_extraction_mapper",
    "pipeline.quality_safety_recompute_verifier",
    "pipeline.quality_safety_safe_numeric_extractor",
    "pipeline.quality_safety_structured_numeric_candidate_adapter",
    "pipeline.quality_safety_unified_qa",
}
SAFE_EXTRACTOR_STATUSES = {"ok", "warning", "skipped", "partial", "failed"}
SAFE_EXTRACTOR_WARNINGS = {
    "component_missing",
    "empty_numeric_extraction",
    "malformed_numeric_extraction_input",
    "invalid_numeric_record_dropped",
    "max_items_reached",
    "superseded_by_explicit_records",
}
SAFE_EXTRACTOR_SUMMARY_KEYS = {
    "candidate_count",
    "record_count",
    "supported_method_count",
    "unsupported_method_count",
    "dropped_candidate_count",
}
STRUCTURED_ADAPTER_STATUSES = {"ok", "warning", "skipped", "partial", "failed"}
STRUCTURED_ADAPTER_WARNINGS = {
    "component_missing",
    "structured_numeric_candidates_missing",
    "empty_structured_numeric_artifact",
    "malformed_structured_numeric_artifact_input",
    "unsupported_artifact_kind",
    "missing_candidates",
    "invalid_candidate_dropped",
    "max_items_reached",
    "superseded_by_explicit_records",
    "superseded_by_safe_candidates",
}
STRUCTURED_ADAPTER_SUMMARY_KEYS = {
    "input_candidate_count",
    "output_candidate_count",
    "supported_method_count",
    "unsupported_method_count",
    "dropped_candidate_count",
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


def assert_job_warnings_closed(name: str, payload: dict[str, Any]) -> None:
    warnings = payload.get("warnings", [])
    check(f"{name}: job warnings closed", all(item in JOB_WARNINGS for item in warnings), str(warnings))


def weighted_bundle(*, claimed: float = 0.2) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_extraction_bundle",
        "lecture_id": "synthetic_fixture",
        "source_quality": "synthetic",
        "concepts": [
            {
                "concept": "Synthetic Concept",
                "source_ref": "source_page_1",
                "computation_records": [
                    {
                        "id": "synthetic.weighted_gini.fact",
                        "label": "synthetic_stump_choice_score",
                        "type": "numeric",
                        "method": "weighted_gini",
                        "inputs": {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]},
                        "claimed_value": claimed,
                        "tolerance": 0.01,
                    }
                ],
                "numeric_observations": [],
            }
        ],
    }


def fixture_spec(*, value: float) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_fixture",
        "lecture_id": "synthetic_fixture",
        "title": "Synthetic Fixture",
        "source_quality": "synthetic",
        "expected_topics": ["Synthetic Concept"],
        "ground_truth_numerics": [{"label": "synthetic_stump_choice_score", "value": value, "tol": 0.01}],
        "min_mock_questions": 1,
        "tier_targets": {"premium": 0.9, "local": 0.8},
    }


def candidate_markdown(*, value: float = 0.2, marker: str = "") -> str:
    tail = f"\n{marker}" if marker else ""
    return "\n".join(
        [
            "# Synthetic Fixture",
            "Synthetic Concept",
            f"synthetic_stump_choice_score: {value}",
            "## Worked Answer",
            "Solution: substitute the synthetic counts and finish with the numeric target.",
            "## Mock Question 1: Which synthetic concept is checked?",
            "Answer: Synthetic Concept.",
        ]
    ) + tail


def test_pure_payload_without_extraction() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(marker="CANDIDATE_PRIVATE_TEXT_MARKER")
    )
    check("payload kind", payload["kind"] == "quality_safety_job_artifact")
    check("payload artifact exact", payload["artifact_name"] == ARTIFACT_NAME)
    check("payload advisory", payload["advisory"] is True)
    check("payload status closed", payload["status"] in {"passed", "warning", "failed", "skipped", "partial"})
    check("payload has shippable", isinstance(payload["shippable"], bool))
    check("payload has safety floor", isinstance(payload["safety_floor_green"], bool))
    check("unified nested", payload["quality_safety_unified_qa"]["kind"] == "quality_safety_unified_qa")
    check("missing extraction warning", "extraction_bundle_missing" in payload["warnings"], str(payload["warnings"]))
    check("recompute missing warning", "recompute_component_missing" in payload["warnings"], str(payload["warnings"]))
    check("leak component ran", payload["component_statuses"]["leak"] in {"passed", "warning", "failed"})
    assert_no_canary("without extraction payload", payload)
    assert_job_warnings_closed("without extraction payload", payload)


def test_payload_with_extraction_clean_and_wrong() -> None:
    clean = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        extraction_bundle=weighted_bundle(claimed=0.2),
        fixture_spec=fixture_spec(value=0.2),
    )
    check("clean status passed", clean["status"] == "passed", serialized(clean))
    check("clean shippable", clean["shippable"] is True)
    check("clean safety green", clean["safety_floor_green"] is True)
    check("clean recompute passed", clean["component_statuses"]["recompute"] == "passed")
    assert_no_canary("clean extraction payload", clean)

    wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.5),
        extraction_bundle=weighted_bundle(claimed=0.5),
        fixture_spec=fixture_spec(value=0.5),
    )
    check("wrong status failed", wrong["status"] == "failed", serialized(wrong))
    check("wrong not shippable", wrong["shippable"] is False)
    check("wrong safety red", wrong["safety_floor_green"] is False)
    check(
        "wrong recompute blocker",
        any(item["component"] == "recompute" and item["check_id"] == "weighted_gini" for item in wrong["blocking_failures"]),
        serialized(wrong),
    )
    assert_no_canary("wrong extraction payload", wrong)


def test_missing_and_malformed_components() -> None:
    missing_candidate = build_quality_safety_job_artifact_payload(extraction_bundle=weighted_bundle())
    check("missing candidate warning", "candidate_markdown_missing" in missing_candidate["warnings"])
    check("missing candidate leak unknown", missing_candidate["component_statuses"]["leak"] == "unknown")
    assert_no_canary("missing candidate", missing_candidate)

    missing_extraction = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown())
    check("missing extraction warning", "extraction_bundle_missing" in missing_extraction["warnings"])
    check("missing extraction component missing count", missing_extraction["summary"]["component_missing_count"] >= 2)

    malformed = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        extraction_bundle={"concepts": "not-a-list"},
    )
    check("malformed degrades", "component_degraded" in malformed["warnings"], str(malformed["warnings"]))
    check("malformed status closed", malformed["status"] in {"passed", "warning", "failed", "skipped", "partial"})
    assert_no_canary("malformed extraction", malformed)


def test_artifact_writing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job"
        payload = write_quality_safety_job_artifact(
            job_dir,
            candidate_markdown=candidate_markdown(),
        )
        artifact = job_dir / ARTIFACT_NAME
        check("artifact written exact name", artifact.exists())
        loaded = json.loads(artifact.read_text(encoding="utf-8"))
        check("artifact deterministic sort", artifact.read_text(encoding="utf-8") == json.dumps(loaded, indent=2, sort_keys=True) + "\n")
        check("write return matches file", serialized(payload) == serialized(loaded))
        assert_no_canary("written artifact", loaded)

        blocking_file = Path(tmp) / "not_a_dir"
        blocking_file.write_text("synthetic", encoding="utf-8")
        failed = write_quality_safety_job_artifact(
            blocking_file,
            candidate_markdown=candidate_markdown(),
        )
        check("write failure does not raise", failed["kind"] == "quality_safety_job_artifact")
        check("write failure warning", "artifact_write_failed" in failed["warnings"], str(failed["warnings"]))


class FakeJob:
    def __init__(self, root: Path, *, fail_write: bool = False) -> None:
        self.dir = root
        self.clean_md = root / "clean.md"
        self.quality_safety_unified_qa_json = root / ARTIFACT_NAME
        self.source_coverage_report_json = root / "source_coverage_report.json"
        self.extraction_metadata_json = root / "extraction_metadata.json"
        self.visual_inclusion_plan_json = root / "visual_inclusion_plan.json"
        self.table_candidates_manifest_json = root / "table_candidates_manifest.json"
        self.table_reconstruction_policy_json = root / "table_reconstruction_policy.json"
        self.status = "validating"
        self.fail_write = fail_write

    def save_text(self, path: Path, text: str) -> Path:
        if self.fail_write:
            raise OSError("synthetic write failure")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


def test_production_hook_behavior() -> None:
    from pipeline.run_markdown_job import _write_quality_safety_unified_qa

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = FakeJob(root)
        job.clean_md.write_text(candidate_markdown(), encoding="utf-8")
        before = hashlib.sha256(job.clean_md.read_bytes()).hexdigest()
        _write_quality_safety_unified_qa(job)
        after = hashlib.sha256(job.clean_md.read_bytes()).hexdigest()
        check("production hook writes artifact", job.quality_safety_unified_qa_json.exists())
        check("production hook keeps clean.md unchanged", before == after)
        check("production hook keeps status unchanged", job.status == "validating")

        failing_root = Path(tmp) / "failing_job"
        failing_root.mkdir()
        failing = FakeJob(failing_root, fail_write=True)
        failing.clean_md.write_text(candidate_markdown(), encoding="utf-8")
        _write_quality_safety_unified_qa(failing)
        check("production hook write exception swallowed", failing.status == "validating")


def test_no_leak_sweep() -> None:
    bundle = weighted_bundle()
    bundle["lecture_id"] = HOSTILE_CANARIES[0]
    bundle["concepts"][0]["concept"] = HOSTILE_CANARIES[1]
    bundle["concepts"][0]["source_ref"] = HOSTILE_CANARIES[2]
    bundle["concepts"][0]["computation_records"][0]["label"] = HOSTILE_CANARIES[3]
    bundle["concepts"][0]["computation_records"][0]["inputs"]["payload"] = HOSTILE_CANARIES[4]
    bundle["concepts"][0]["numeric_observations"] = [
        {"id": HOSTILE_CANARIES[5], "label": HOSTILE_CANARIES[6], "value": 1.0}
    ]
    metadata = {
        "path": HOSTILE_CANARIES[0],
        "url": HOSTILE_CANARIES[2],
        "auth": HOSTILE_CANARIES[3],
        "ocr": HOSTILE_CANARIES[5],
        "table": HOSTILE_CANARIES[6],
        "caption": HOSTILE_CANARIES[7],
        "provider": HOSTILE_CANARIES[8],
        "spec": HOSTILE_CANARIES[9],
        "quote": HOSTILE_CANARIES[10],
    }
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(marker="\n".join(HOSTILE_CANARIES)),
        extraction_bundle=bundle,
        job_metadata=metadata,
    )
    check("metadata dropped warning", "unsafe_metadata_dropped" in payload["warnings"], str(payload["warnings"]))
    assert_no_canary("hostile job artifact", payload)


def synthetic_source_coverage_report() -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "source_coverage_report",
        "sources": [
            {"status": "ok", "page_count": 3, "visual_candidate_page_count": 1},
            {"status": "covered", "page_count": 2, "visual_candidate_page_count": 0},
        ],
    }


def hostile_source_coverage_report() -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "source_coverage_report",
        "path": HOSTILE_CANARIES[0],
        "url": HOSTILE_CANARIES[2],
        "auth": HOSTILE_CANARIES[3],
        "data_uri": HOSTILE_CANARIES[4],
        "sources": [
            {
                "status": "ok",
                "page_count": 2,
                "visual_candidate_page_count": 1,
                "basename": HOSTILE_CANARIES[0],
                "filename": HOSTILE_CANARIES[9],
                "ocr_text": HOSTILE_CANARIES[5],
                "table_text": HOSTILE_CANARIES[6],
                "caption": HOSTILE_CANARIES[7],
                "formula": HOSTILE_CANARIES[12],
                "quote": HOSTILE_CANARIES[10],
            }
        ],
    }


def hostile_visual_plan() -> dict[str, Any]:
    return {
        "status": "ok",
        "included_count": 2,
        "caption": HOSTILE_CANARIES[7],
        "asset_path": HOSTILE_CANARIES[0],
    }


def hostile_table_manifest() -> dict[str, Any]:
    return {
        "status": "ok",
        "candidate_count": 1,
        "table_text": HOSTILE_CANARIES[6],
        "provider": HOSTILE_CANARIES[8],
    }


def test_extraction_coverage_skipped_without_metadata() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
    )
    check("coverage status closed", payload["extraction_coverage_status"] in EXTRACTION_COVERAGE_STATUSES)
    check("coverage skipped without metadata", payload["extraction_coverage_status"] == "skipped")
    check("coverage missing warning", "extraction_coverage_missing" in payload["warnings"], str(payload["warnings"]))
    bundle = payload["extraction_coverage_bundle"]
    check("coverage bundle kind", bundle["kind"] == "quality_safety_extraction_coverage_bundle")
    check("coverage no records", bundle["coverage_records"] == [])
    check("coverage numeric obs empty", bundle["numeric_observations"] == [])
    check("coverage summary numeric 0", payload["extraction_coverage_summary"]["numeric_observation_count"] == 0)
    assert_job_warnings_closed("coverage skipped", payload)
    assert_no_canary("coverage skipped", payload)


def test_extraction_coverage_populated() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report=synthetic_source_coverage_report(),
        visual_inclusion_plan={"status": "ok", "included_count": 2},
        table_candidates_manifest={"status": "ok", "candidate_count": 1},
    )
    bundle = payload["extraction_coverage_bundle"]
    check("populated kind", bundle["kind"] == "quality_safety_extraction_coverage_bundle")
    check("populated status closed", payload["extraction_coverage_status"] in EXTRACTION_COVERAGE_STATUSES)
    check("populated has records", len(bundle["coverage_records"]) >= 2, serialized(bundle["summary"]))
    summary = payload["extraction_coverage_summary"]
    check("populated source_count", summary["source_count"] == 2, str(summary))
    check("populated page_count", summary["page_count"] == 5, str(summary))
    check("populated numeric_observation_count 0", summary["numeric_observation_count"] == 0)
    check("populated numeric obs empty", bundle["numeric_observations"] == [])
    # Structural coverage must never become numeric recompute evidence.
    check("populated recompute still missing", "recompute_component_missing" in payload["warnings"], str(payload["warnings"]))
    check("populated fact sheet still missing", "fact_sheet_component_missing" in payload["warnings"], str(payload["warnings"]))
    # Record ids are synthetic qs_extract_NNNN tokens only.
    for record in bundle["coverage_records"]:
        check("populated record id synthetic", record["id"].startswith("qs_extract_"), record["id"])
    assert_job_warnings_closed("coverage populated", payload)
    assert_no_canary("coverage populated", payload)


def test_extraction_coverage_excludes_hostile_fields() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report=hostile_source_coverage_report(),
        extraction_metadata={"sources": [{"page_count": 1, "basename": HOSTILE_CANARIES[0]}]},
        visual_inclusion_plan=hostile_visual_plan(),
        table_candidates_manifest=hostile_table_manifest(),
    )
    assert_no_canary("coverage hostile fields", payload)
    bundle = payload["extraction_coverage_bundle"]
    check("hostile numeric obs empty", bundle["numeric_observations"] == [])
    check("hostile numeric count 0", payload["extraction_coverage_summary"]["numeric_observation_count"] == 0)
    assert_job_warnings_closed("coverage hostile", payload)


def test_extraction_coverage_does_not_upgrade_safety() -> None:
    # A wrong-answer recompute case must stay failed/not-shippable even when rich
    # structural coverage is present.
    wrong = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.5),
        extraction_bundle=weighted_bundle(claimed=0.5),
        fixture_spec=fixture_spec(value=0.5),
        source_coverage_report=synthetic_source_coverage_report(),
        visual_inclusion_plan={"status": "ok", "included_count": 5},
        table_candidates_manifest={"status": "ok", "candidate_count": 5},
    )
    check("coverage does not upgrade status", wrong["status"] == "failed", serialized(wrong["status"]))
    check("coverage does not upgrade shippable", wrong["shippable"] is False)
    check("coverage does not upgrade safety", wrong["safety_floor_green"] is False)


def test_extraction_coverage_no_mutation_and_deterministic() -> None:
    report = synthetic_source_coverage_report()
    snapshot = json.dumps(report, sort_keys=True)
    first = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report=report,
    )
    second = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report=synthetic_source_coverage_report(),
    )
    check("coverage no caller mutation", json.dumps(report, sort_keys=True) == snapshot)
    check("coverage deterministic", serialized(first) == serialized(second))


def test_extraction_coverage_adapter_failure_degrades() -> None:
    # A dict-shaped but malformed coverage report must not raise and must degrade
    # to a closed status with closed job warnings.
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report={"sources": "not-a-list", "garbage": object().__class__.__name__},
    )
    check("adapter failure status closed", payload["extraction_coverage_status"] in EXTRACTION_COVERAGE_STATUSES)
    check("adapter failure kind", payload["extraction_coverage_bundle"]["kind"] == "quality_safety_extraction_coverage_bundle")
    assert_job_warnings_closed("adapter failure", payload)
    assert_no_canary("adapter failure", payload)


def test_production_hook_reads_sibling_artifacts() -> None:
    from pipeline.run_markdown_job import _write_quality_safety_unified_qa

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = FakeJob(root)
        job.clean_md.write_text(candidate_markdown(), encoding="utf-8")
        (root / "source_coverage_report.json").write_text(
            json.dumps(synthetic_source_coverage_report()), encoding="utf-8"
        )
        (root / "visual_inclusion_plan.json").write_text(
            json.dumps({"status": "ok", "included_count": 2}), encoding="utf-8"
        )
        _write_quality_safety_unified_qa(job)
        loaded = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))
        check("hook coverage status closed", loaded["extraction_coverage_status"] in EXTRACTION_COVERAGE_STATUSES)
        check("hook coverage has records", len(loaded["extraction_coverage_bundle"]["coverage_records"]) >= 2)
        check("hook coverage numeric count 0", loaded["extraction_coverage_summary"]["numeric_observation_count"] == 0)
        assert_no_canary("hook coverage", loaded)


# --- Slice 126: numeric extraction mapper wiring -----------------------------

# weighted_gini of these groups recomputes to 0.2 (Slice 125 fixture).
WEIGHTED_GINI_INPUTS = {"groups": [{"yes": 3, "no": 0}, {"yes": 1, "no": 4}]}


def numeric_record(
    *,
    method: str = "weighted_gini",
    inputs: dict[str, Any] | None = None,
    value: float = 0.2,
    rec_id: str = "qs_num_clean",
    concept_id: str = "qs_concept_1",
    label: str = "synthetic_score",
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
        "computation": {"method": method, "inputs": inputs if inputs is not None else dict(WEIGHTED_GINI_INPUTS)},
        "tolerance": tolerance,
    }


def assert_numeric_shape(name: str, payload: dict[str, Any]) -> None:
    check(f"{name}: numeric status closed", payload["numeric_extraction_status"] in NUMERIC_EXTRACTION_STATUSES, str(payload.get("numeric_extraction_status")))
    summary = payload["numeric_extraction_summary"]
    check(
        f"{name}: numeric summary keys",
        set(summary) == {"record_count", "numeric_fact_count", "computation_record_count", "supported_method_count", "unsupported_method_count"},
        str(set(summary)),
    )
    check(f"{name}: numeric warnings closed", all(w in NUMERIC_BUNDLE_WARNINGS for w in payload["numeric_extraction_warnings"]), str(payload["numeric_extraction_warnings"]))
    bundle = payload["numeric_extraction_bundle"]
    check(f"{name}: numeric bundle kind", bundle.get("kind") == "quality_safety_numeric_extraction_bundle", str(bundle.get("kind")))
    check(f"{name}: artifact name unchanged", payload["artifact_name"] == ARTIFACT_NAME)
    assert_job_warnings_closed(name, payload)


def test_numeric_records_missing_degrades() -> None:
    payload = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown())
    assert_numeric_shape("numeric missing", payload)
    check("numeric missing: status skipped", payload["numeric_extraction_status"] == "skipped", str(payload["numeric_extraction_status"]))
    check("numeric missing: warning present", "numeric_extraction_missing" in payload["warnings"], str(payload["warnings"]))
    check("numeric missing: record_count 0", payload["numeric_extraction_summary"]["record_count"] == 0)
    # No numeric records => the concept/fact recompute leg stays honestly missing.
    check("numeric missing: recompute still missing", "recompute_component_missing" in payload["warnings"])
    assert_no_canary("numeric missing", payload)


def test_numeric_records_clean_verified() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=[numeric_record(value=0.2)],
    )
    assert_numeric_shape("numeric clean", payload)
    check("numeric clean: status ok", payload["numeric_extraction_status"] == "ok", str(payload["numeric_extraction_status"]))
    check("numeric clean: one computation record", payload["numeric_extraction_summary"]["computation_record_count"] == 1, str(payload["numeric_extraction_summary"]))
    check("numeric clean: recompute passed", payload["component_statuses"]["recompute"] == "passed", serialized(payload["component_statuses"]))
    check("numeric clean: no recompute blocker", not any(item["component"] == "recompute" for item in payload["blocking_failures"]))
    check("numeric clean: shippable", payload["shippable"] is True, serialized(payload["status"]))
    # The numeric leg fed the producer; the structural extraction bundle was not
    # supplied, so the explicit-bundle "missing" warning must NOT be present.
    check("numeric clean: no extraction_bundle_missing", "extraction_bundle_missing" not in payload["warnings"], str(payload["warnings"]))
    assert_no_canary("numeric clean", payload)


def test_numeric_records_wrong_blocks() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        numeric_extraction_records=[numeric_record(value=0.9)],  # recomputes to 0.2
    )
    assert_numeric_shape("numeric wrong", payload)
    # Well-formed record => bundle status ok; the wrong VALUE is caught by recompute.
    check("numeric wrong: bundle status ok", payload["numeric_extraction_status"] == "ok", str(payload["numeric_extraction_status"]))
    check(
        "numeric wrong: recompute blocker",
        any(item["component"] == "recompute" and item["check_id"] == "weighted_gini" for item in payload["blocking_failures"]),
        serialized(payload["blocking_failures"]),
    )
    check("numeric wrong: status failed", payload["status"] == "failed", str(payload["status"]))
    check("numeric wrong: not shippable", payload["shippable"] is False)
    check("numeric wrong: safety floor red", payload["safety_floor_green"] is False)
    assert_no_canary("numeric wrong", payload)


def test_numeric_records_confident_wrong_case() -> None:
    # single_confident_wrong_numeric_case synthetic equivalent through the builder.
    confident_wrong = {
        "id": "qs_num_confident_wrong",
        "concept_id": "qs_concept_confident",
        "label": "synthetic_confident_wrong",
        "fact_type": "numeric",
        "value": 0.95,  # confidently claimed, but cross_entropy(0.5) ~= 0.6931
        "confidence": "high",
        "provenance": "computed",
        "source_ref": "source_page_3",
        "computation": {"method": "cross_entropy", "inputs": {"probability": 0.5}},
        "tolerance": 0.01,
    }
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.95),
        numeric_extraction_records=[confident_wrong],
    )
    assert_numeric_shape("confident wrong", payload)
    check("confident wrong: status failed", payload["status"] == "failed", str(payload["status"]))
    check("confident wrong: blocker present", any(item["component"] == "recompute" for item in payload["blocking_failures"]))
    check("confident wrong: not shippable", payload["shippable"] is False)
    assert_no_canary("confident wrong", payload)


def test_numeric_records_clean_real_case() -> None:
    # clean_real_case synthetic equivalent: two correct facts, no blocking.
    records = [
        numeric_record(rec_id="qs_num_real_a", concept_id="qs_concept_real", label="clean_gini", method="weighted_gini", inputs={"groups": [{"a": 4, "b": 0}, {"a": 0, "b": 4}]}, value=0.0),
        numeric_record(rec_id="qs_num_real_b", concept_id="qs_concept_real", label="clean_total_error", method="total_error", inputs={"misclassified_weight": 0.0}, value=0.0),
    ]
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.0),
        numeric_extraction_records=records,
    )
    assert_numeric_shape("clean real", payload)
    check("clean real: recompute passed", payload["component_statuses"]["recompute"] == "passed", serialized(payload["component_statuses"]))
    check("clean real: no blocking", not payload["blocking_failures"])
    check("clean real: two computation records", payload["numeric_extraction_summary"]["computation_record_count"] == 2)
    check("clean real: shippable", payload["shippable"] is True)
    assert_no_canary("clean real", payload)


def test_numeric_records_malformed_degrades() -> None:
    for label, value in (
        ("string", "not-a-list"),
        ("dict-no-records", {"version": 1, "kind": "quality_safety_numeric_extraction_records"}),
        ("number", 123),
    ):
        payload = build_quality_safety_job_artifact_payload(
            candidate_markdown=candidate_markdown(),
            numeric_extraction_records=value,
        )
        assert_numeric_shape(f"numeric malformed {label}", payload)
        check(f"numeric malformed {label}: degraded warning", "numeric_extraction_degraded" in payload["warnings"], str(payload["warnings"]))
        check(f"numeric malformed {label}: status failed", payload["numeric_extraction_status"] == "failed", str(payload["numeric_extraction_status"]))
        check(f"numeric malformed {label}: no crash kind", payload["kind"] == "quality_safety_job_artifact")
        assert_no_canary(f"numeric malformed {label}", payload)

    # Empty list => skipped, not failed.
    empty = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown(), numeric_extraction_records=[])
    check("numeric empty: status skipped", empty["numeric_extraction_status"] == "skipped", str(empty["numeric_extraction_status"]))


def test_numeric_records_dict_wrapper() -> None:
    wrapper = {"version": 1, "kind": "quality_safety_numeric_extraction_records", "records": [numeric_record(value=0.2)]}
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=wrapper,
    )
    assert_numeric_shape("numeric wrapper", payload)
    check("numeric wrapper: one record", payload["numeric_extraction_summary"]["record_count"] == 1, str(payload["numeric_extraction_summary"]))
    check("numeric wrapper: recompute passed", payload["component_statuses"]["recompute"] == "passed")


def test_numeric_records_separate_from_coverage() -> None:
    # Structural coverage and numeric extraction are surfaced as SEPARATE bundles;
    # neither contaminates the other.
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=[numeric_record(value=0.2)],
        source_coverage_report=synthetic_source_coverage_report(),
        visual_inclusion_plan={"status": "ok", "included_count": 2},
        table_candidates_manifest={"status": "ok", "candidate_count": 1},
    )
    assert_numeric_shape("separate", payload)
    check("separate: coverage bundle distinct kind", payload["extraction_coverage_bundle"]["kind"] == "quality_safety_extraction_coverage_bundle")
    check("separate: numeric bundle distinct kind", payload["numeric_extraction_bundle"]["kind"] == "quality_safety_numeric_extraction_bundle")
    # Structural coverage never becomes a numeric fact.
    check("separate: coverage numeric obs empty", payload["extraction_coverage_bundle"]["numeric_observations"] == [])
    check("separate: coverage numeric count 0", payload["extraction_coverage_summary"]["numeric_observation_count"] == 0)
    # Numeric records still verified through recompute.
    check("separate: recompute passed", payload["component_statuses"]["recompute"] == "passed")
    check("separate: numeric record present", payload["numeric_extraction_summary"]["record_count"] == 1)


def test_numeric_not_fabricated_from_coverage() -> None:
    # Rich structural coverage but NO numeric records => numeric leg stays skipped;
    # coverage counts are never turned into numeric facts.
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report=synthetic_source_coverage_report(),
        visual_inclusion_plan={"status": "ok", "included_count": 9},
        table_candidates_manifest={"status": "ok", "candidate_count": 9},
    )
    check("not fabricated: numeric skipped", payload["numeric_extraction_status"] == "skipped")
    check("not fabricated: numeric record_count 0", payload["numeric_extraction_summary"]["record_count"] == 0)
    check("not fabricated: numeric fact_count 0", payload["numeric_extraction_summary"]["numeric_fact_count"] == 0)
    check("not fabricated: coverage present", payload["extraction_coverage_status"] in EXTRACTION_COVERAGE_STATUSES)
    check("not fabricated: recompute still missing", "recompute_component_missing" in payload["warnings"])


def test_numeric_records_hostile_stripped() -> None:
    tainted = numeric_record(method="cross_entropy", inputs={"probability": 0.5}, value=0.6931471805599453)
    tainted["raw_text"] = HOSTILE_CANARIES[5]
    tainted["source_text"] = HOSTILE_CANARIES[11]
    tainted["formulas_as_text"] = HOSTILE_CANARIES[12]
    tainted["paths"] = HOSTILE_CANARIES[0]
    tainted["evidence_quotes"] = HOSTILE_CANARIES[10]
    tainted["label"] = HOSTILE_CANARIES[3]
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.6931471805599453),
        numeric_extraction_records=[tainted],
    )
    assert_numeric_shape("hostile numeric", payload)
    assert_no_canary("hostile numeric", payload)
    # The clean computation still recomputes despite the stripped hostile fields.
    check("hostile numeric: recompute passed", payload["component_statuses"]["recompute"] == "passed")


def test_numeric_records_no_mutation() -> None:
    records = [numeric_record(value=0.2), {"raw_text": HOSTILE_CANARIES[5], "fact_type": "numeric", "value": 1.0}]
    snapshot = json.dumps(records, sort_keys=True)
    first = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown(value=0.2), numeric_extraction_records=records)
    check("numeric no mutation: caller unchanged", json.dumps(records, sort_keys=True) == snapshot)
    second = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown(value=0.2), numeric_extraction_records=[numeric_record(value=0.2), {"raw_text": HOSTILE_CANARIES[5], "fact_type": "numeric", "value": 1.0}])
    check("numeric deterministic", serialized(first["numeric_extraction_bundle"]) == serialized(second["numeric_extraction_bundle"]))


def test_numeric_records_sidecar_read() -> None:
    from pipeline.quality_safety_job_artifact import (
        NUMERIC_RECORDS_ARTIFACT_NAME,
        read_quality_safety_numeric_extraction_records,
    )

    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job"
        job_dir.mkdir()
        # No sidecar yet => None => numeric leg skipped.
        check("sidecar absent reads None", read_quality_safety_numeric_extraction_records(job_dir) is None)
        absent = write_quality_safety_job_artifact(job_dir, candidate_markdown=candidate_markdown())
        check("sidecar absent: numeric skipped", absent["numeric_extraction_status"] == "skipped")

        # Drop a synthetic sidecar; the writer must consume it read-only.
        (job_dir / NUMERIC_RECORDS_ARTIFACT_NAME).write_text(
            json.dumps({"records": [numeric_record(value=0.2)]}), encoding="utf-8"
        )
        present = write_quality_safety_job_artifact(job_dir, candidate_markdown=candidate_markdown(value=0.2))
        check("sidecar present: recompute passed", present["component_statuses"]["recompute"] == "passed", serialized(present["component_statuses"]))
        check("sidecar present: one record", present["numeric_extraction_summary"]["record_count"] == 1)
        assert_no_canary("sidecar present", present)


def test_production_hook_reads_numeric_sidecar() -> None:
    from pipeline.quality_safety_job_artifact import NUMERIC_RECORDS_ARTIFACT_NAME
    from pipeline.run_markdown_job import _write_quality_safety_unified_qa

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = FakeJob(root)
        job.clean_md.write_text(candidate_markdown(value=0.9), encoding="utf-8")
        (root / NUMERIC_RECORDS_ARTIFACT_NAME).write_text(
            json.dumps({"records": [numeric_record(value=0.9)]}), encoding="utf-8"  # wrong vs 0.2
        )
        _write_quality_safety_unified_qa(job)
        loaded = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))
        check("hook numeric: bundle present", loaded["numeric_extraction_summary"]["record_count"] == 1, serialized(loaded["numeric_extraction_summary"]))
        check(
            "hook numeric: recompute blocker through production path",
            any(item.get("component") == "recompute" for item in loaded.get("blocking_failures") or []),
            serialized(loaded.get("blocking_failures")),
        )
        check("hook numeric: not shippable", loaded["shippable"] is False)
        check("hook numeric: safety floor red", loaded["safety_floor_green"] is False)
        assert_no_canary("hook numeric", loaded)


def assert_safe_shape(name: str, payload: dict[str, Any]) -> None:
    check(f"{name}: safe status closed", payload["safe_numeric_extractor_status"] in SAFE_EXTRACTOR_STATUSES, str(payload.get("safe_numeric_extractor_status")))
    summary = payload["safe_numeric_extractor_summary"]
    check(f"{name}: safe summary keys", set(summary) == SAFE_EXTRACTOR_SUMMARY_KEYS, str(set(summary)))
    check(
        f"{name}: safe summary non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()),
        str(summary),
    )
    check(f"{name}: safe warnings closed", all(w in SAFE_EXTRACTOR_WARNINGS for w in payload["safe_numeric_extractor_warnings"]), str(payload["safe_numeric_extractor_warnings"]))
    check(f"{name}: artifact name unchanged", payload["artifact_name"] == ARTIFACT_NAME)
    check(f"{name}: advisory", payload["advisory"] is True)
    assert_job_warnings_closed(name, payload)


def safe_candidate(*, method: str = "weighted_gini", value: float = 0.2, rec_id: str = "qs_safe_clean") -> dict[str, Any]:
    """A sanitized numeric candidate (contract shape) for the safe extractor."""
    return numeric_record(method=method, value=value, rec_id=rec_id)


def test_safe_candidates_missing_degrades() -> None:
    # No candidate sidecar and no numeric record sidecar => current skipped behavior.
    payload = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown())
    assert_safe_shape("safe missing", payload)
    check("safe missing: status skipped", payload["safe_numeric_extractor_status"] == "skipped", str(payload["safe_numeric_extractor_status"]))
    check("safe missing: no safe warnings", payload["safe_numeric_extractor_warnings"] == [], str(payload["safe_numeric_extractor_warnings"]))
    check("safe missing: numeric still skipped", payload["numeric_extraction_status"] == "skipped", str(payload["numeric_extraction_status"]))
    check("safe missing: candidate_count 0", payload["safe_numeric_extractor_summary"]["candidate_count"] == 0)
    assert_no_canary("safe missing", payload)


def test_safe_candidates_clean_verified() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        safe_numeric_candidates=[safe_candidate(value=0.2)],
    )
    assert_safe_shape("safe clean", payload)
    assert_numeric_shape("safe clean numeric", payload)
    check("safe clean: extractor ok", payload["safe_numeric_extractor_status"] == "ok", str(payload["safe_numeric_extractor_status"]))
    check("safe clean: candidate_count 1", payload["safe_numeric_extractor_summary"]["candidate_count"] == 1)
    check("safe clean: record_count 1", payload["safe_numeric_extractor_summary"]["record_count"] == 1)
    check("safe clean: numeric status ok", payload["numeric_extraction_status"] == "ok", str(payload["numeric_extraction_status"]))
    check("safe clean: recompute passed", payload["component_statuses"]["recompute"] == "passed", serialized(payload["component_statuses"]))
    check("safe clean: no recompute blocker", not any(item["component"] == "recompute" for item in payload["blocking_failures"]))
    check("safe clean: shippable", payload["shippable"] is True)
    assert_no_canary("safe clean", payload)


def test_safe_candidates_wrong_blocks() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        safe_numeric_candidates=[safe_candidate(value=0.9, rec_id="qs_safe_confident_wrong")],  # recomputes to 0.2
    )
    assert_safe_shape("safe wrong", payload)
    check("safe wrong: extractor ok", payload["safe_numeric_extractor_status"] == "ok", str(payload["safe_numeric_extractor_status"]))
    check(
        "safe wrong: recompute blocker",
        any(item["component"] == "recompute" and item["check_id"] == "weighted_gini" for item in payload["blocking_failures"]),
        serialized(payload["blocking_failures"]),
    )
    check("safe wrong: status failed", payload["status"] == "failed", str(payload["status"]))
    check("safe wrong: not shippable", payload["shippable"] is False)
    check("safe wrong: safety floor red", payload["safety_floor_green"] is False)
    assert_no_canary("safe wrong", payload)


def test_safe_candidates_malformed_degrades() -> None:
    for label, value in (("string", "not a list"), ("dict-no-candidates", {"version": 1})):
        payload = build_quality_safety_job_artifact_payload(
            candidate_markdown=candidate_markdown(),
            safe_numeric_candidates=value,
        )
        assert_safe_shape(f"safe malformed {label}", payload)
        check(f"safe malformed {label}: status failed", payload["safe_numeric_extractor_status"] == "failed", str(payload["safe_numeric_extractor_status"]))
        check(
            f"safe malformed {label}: malformed warning",
            "malformed_numeric_extraction_input" in payload["safe_numeric_extractor_warnings"],
            str(payload["safe_numeric_extractor_warnings"]),
        )
        # Malformed safe candidates never fabricate a numeric record or a job failure.
        check(f"safe malformed {label}: numeric skipped", payload["numeric_extraction_status"] == "skipped", str(payload["numeric_extraction_status"]))
        check(f"safe malformed {label}: kind intact", payload["kind"] == "quality_safety_job_artifact")
        assert_no_canary(f"safe malformed {label}", payload)

    # Empty candidate list => extractor skipped (empty), no crash.
    empty = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown(), safe_numeric_candidates=[])
    assert_safe_shape("safe empty", empty)
    check("safe empty: status skipped", empty["safe_numeric_extractor_status"] == "skipped", str(empty["safe_numeric_extractor_status"]))


def test_safe_candidates_dict_wrapper() -> None:
    wrapper = {"version": 1, "kind": "quality_safety_safe_numeric_candidates", "candidates": [safe_candidate(value=0.2)]}
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        safe_numeric_candidates=wrapper,
    )
    assert_safe_shape("safe wrapper", payload)
    check("safe wrapper: candidate_count 1", payload["safe_numeric_extractor_summary"]["candidate_count"] == 1)
    check("safe wrapper: recompute passed", payload["component_statuses"]["recompute"] == "passed", serialized(payload["component_statuses"]))


def test_safe_candidates_precedence_explicit_wins() -> None:
    # Both explicit records (correct) AND safe candidates (wrong) present: explicit
    # numeric records win deterministically; safe candidates are summarized only.
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=[numeric_record(value=0.2)],  # explicit, correct
        safe_numeric_candidates=[safe_candidate(value=0.9, rec_id="qs_safe_loser")],  # would be wrong
    )
    assert_safe_shape("precedence", payload)
    check("precedence: safe skipped (superseded)", payload["safe_numeric_extractor_status"] == "skipped", str(payload["safe_numeric_extractor_status"]))
    check(
        "precedence: superseded warning",
        "superseded_by_explicit_records" in payload["safe_numeric_extractor_warnings"],
        str(payload["safe_numeric_extractor_warnings"]),
    )
    # The explicit (correct) records drove recompute; the wrong candidate was ignored.
    check("precedence: numeric ok", payload["numeric_extraction_status"] == "ok", str(payload["numeric_extraction_status"]))
    check("precedence: recompute passed", payload["component_statuses"]["recompute"] == "passed", serialized(payload["component_statuses"]))
    check("precedence: no recompute blocker from candidate", not any(item["component"] == "recompute" for item in payload["blocking_failures"]))
    check("precedence: shippable", payload["shippable"] is True)
    # Safe candidate summary still reflects the supplied candidate count.
    check("precedence: candidate_count 1", payload["safe_numeric_extractor_summary"]["candidate_count"] == 1)
    assert_no_canary("precedence", payload)


def test_safe_candidates_unsupported_method() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        safe_numeric_candidates=[safe_candidate(method="entropy", value=0.9, rec_id="qs_safe_unsupported")],
    )
    assert_safe_shape("safe unsupported", payload)
    check("safe unsupported: counted", payload["safe_numeric_extractor_summary"]["unsupported_method_count"] == 1, serialized(payload["safe_numeric_extractor_summary"]))
    # An unsupported-method claim must NOT be recompute-blocked (no method to verify).
    check("safe unsupported: no recompute blocker", not any(item["component"] == "recompute" for item in payload["blocking_failures"]), serialized(payload["blocking_failures"]))
    assert_no_canary("safe unsupported", payload)


def test_safe_candidates_not_fabricated_from_coverage() -> None:
    # Structural coverage present but no safe candidates => safe leg stays skipped;
    # structural coverage is never converted into safe candidates/records.
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report=synthetic_source_coverage_report(),
    )
    assert_safe_shape("safe vs coverage", payload)
    check("safe vs coverage: safe skipped", payload["safe_numeric_extractor_status"] == "skipped")
    check("safe vs coverage: no safe records", payload["safe_numeric_extractor_summary"]["record_count"] == 0)
    check("safe vs coverage: coverage present", payload["extraction_coverage_status"] in EXTRACTION_COVERAGE_STATUSES)
    check("safe vs coverage: numeric not fabricated", payload["numeric_extraction_status"] == "skipped")


def test_safe_candidates_hostile_stripped() -> None:
    tainted = dict(safe_candidate(value=0.2, rec_id="qs_safe_tainted"))
    tainted.update(
        {
            "raw_text": HOSTILE_CANARIES[11],
            "source_text": "source text private marker",
            "ocr_text": HOSTILE_CANARIES[5],
            "table_cells": [HOSTILE_CANARIES[6]],
            "captions": HOSTILE_CANARIES[7],
            "formulas_as_text": HOSTILE_CANARIES[12],
            "evidence_quotes": HOSTILE_CANARIES[10],
            "filenames": HOSTILE_CANARIES[9],
            "basenames": "SYNTHETIC_BASENAME_TOKEN",
            "paths": HOSTILE_CANARIES[0],
            "urls": HOSTILE_CANARIES[2],
            "provider_payloads": HOSTILE_CANARIES[8],
            "runtime_traces": HOSTILE_CANARIES[3],
            "raw_artifact_json": "RAW_ARTIFACT_JSON_PRIVATE_MARKER",
        }
    )
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        safe_numeric_candidates=[tainted],
    )
    assert_safe_shape("safe tainted", payload)
    # The clean computation still recomputes; no canary survives anywhere.
    check("safe tainted: recompute passed", payload["component_statuses"]["recompute"] == "passed", serialized(payload["component_statuses"]))
    assert_no_canary("safe tainted", payload)


def test_safe_candidates_no_mutation_and_deterministic() -> None:
    candidates = [safe_candidate(value=0.2), {"raw_text": HOSTILE_CANARIES[11], "fact_type": "numeric", "value": 1.0}]
    snapshot = serialized(candidates)
    first = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown(value=0.2), safe_numeric_candidates=candidates)
    second = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown(value=0.2), safe_numeric_candidates=[safe_candidate(value=0.2), {"raw_text": HOSTILE_CANARIES[11], "fact_type": "numeric", "value": 1.0}])
    check("safe: caller input not mutated", serialized(candidates) == snapshot)
    check("safe: deterministic serialization", serialized(first) == serialized(second))
    assert_no_canary("safe deterministic", first)


def test_safe_candidates_sidecar_read() -> None:
    from pipeline.quality_safety_job_artifact import (
        SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME,
        read_quality_safety_safe_numeric_candidates,
    )

    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job"
        job_dir.mkdir()
        # No sidecar yet => None => safe leg skipped.
        check("safe sidecar absent reads None", read_quality_safety_safe_numeric_candidates(job_dir) is None)
        absent = write_quality_safety_job_artifact(job_dir, candidate_markdown=candidate_markdown())
        check("safe sidecar absent: safe skipped", absent["safe_numeric_extractor_status"] == "skipped")

        # Drop a synthetic candidate sidecar; the writer must consume it read-only.
        (job_dir / SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME).write_text(
            json.dumps({"candidates": [safe_candidate(value=0.2)]}), encoding="utf-8"
        )
        present = write_quality_safety_job_artifact(job_dir, candidate_markdown=candidate_markdown(value=0.2))
        check("safe sidecar present: extractor ok", present["safe_numeric_extractor_status"] == "ok", str(present["safe_numeric_extractor_status"]))
        check("safe sidecar present: recompute passed", present["component_statuses"]["recompute"] == "passed", serialized(present["component_statuses"]))
        check("safe sidecar present: one record", present["safe_numeric_extractor_summary"]["record_count"] == 1)
        # The writer must NOT create the candidate sidecar — read-only.
        check("safe sidecar not created by writer", (job_dir / SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME).exists())
        assert_no_canary("safe sidecar present", present)


def test_production_hook_reads_safe_candidates_sidecar() -> None:
    from pipeline.quality_safety_job_artifact import SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME
    from pipeline.run_markdown_job import _write_quality_safety_unified_qa

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = FakeJob(root)
        job.clean_md.write_text(candidate_markdown(value=0.9), encoding="utf-8")
        (root / SAFE_NUMERIC_CANDIDATES_ARTIFACT_NAME).write_text(
            json.dumps({"candidates": [safe_candidate(value=0.9, rec_id="qs_safe_hook_wrong")]}), encoding="utf-8"  # wrong vs 0.2
        )
        _write_quality_safety_unified_qa(job)
        loaded = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))
        check("hook safe: extractor ok", loaded["safe_numeric_extractor_status"] == "ok", str(loaded.get("safe_numeric_extractor_status")))
        check("hook safe: record consumed", loaded["safe_numeric_extractor_summary"]["record_count"] == 1, serialized(loaded["safe_numeric_extractor_summary"]))
        check(
            "hook safe: recompute blocker through production path",
            any(item.get("component") == "recompute" for item in loaded.get("blocking_failures") or []),
            serialized(loaded.get("blocking_failures")),
        )
        check("hook safe: not shippable", loaded["shippable"] is False)
        check("hook safe: safety floor red", loaded["safety_floor_green"] is False)
        assert_no_canary("hook safe", loaded)


# --- Slice 134: structured candidate adapter artifact wiring -----------------

def assert_structured_shape(name: str, payload: dict[str, Any]) -> None:
    check(
        f"{name}: structured status closed",
        payload["structured_numeric_candidate_adapter_status"] in STRUCTURED_ADAPTER_STATUSES,
        str(payload.get("structured_numeric_candidate_adapter_status")),
    )
    summary = payload["structured_numeric_candidate_adapter_summary"]
    check(f"{name}: structured summary keys", set(summary) == STRUCTURED_ADAPTER_SUMMARY_KEYS, str(set(summary)))
    check(
        f"{name}: structured summary non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()),
        str(summary),
    )
    check(
        f"{name}: structured warnings closed",
        all(w in STRUCTURED_ADAPTER_WARNINGS for w in payload["structured_numeric_candidate_adapter_warnings"]),
        str(payload["structured_numeric_candidate_adapter_warnings"]),
    )
    check(f"{name}: no top-level adapted candidates", "structured_numeric_candidate_adapter_payload" not in payload)
    check(f"{name}: artifact name unchanged", payload["artifact_name"] == ARTIFACT_NAME)
    assert_job_warnings_closed(name, payload)


def structured_artifact(candidates: list[Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_structured_numeric_candidates",
        "status": "ok",
        "source_quality": "structured_numeric_artifact",
        "summary": {"candidate_count": len(candidates)},
        "candidates": candidates,
        "warnings": [],
    }


def structured_candidate(
    *,
    method: str = "weighted_gini",
    value: float = 0.2,
    rec_id: str = "qs_struct_clean",
) -> dict[str, Any]:
    candidate = numeric_record(method=method, value=value, rec_id=rec_id)
    candidate["page_ref"] = "page_1"
    return candidate


def test_structured_candidates_missing_degrades() -> None:
    payload = build_quality_safety_job_artifact_payload(candidate_markdown=candidate_markdown())
    assert_structured_shape("structured missing", payload)
    check(
        "structured missing: status skipped",
        payload["structured_numeric_candidate_adapter_status"] == "skipped",
        str(payload["structured_numeric_candidate_adapter_status"]),
    )
    check(
        "structured missing: warning",
        payload["structured_numeric_candidate_adapter_warnings"] == ["structured_numeric_candidates_missing"],
        str(payload["structured_numeric_candidate_adapter_warnings"]),
    )
    check("structured missing: safe skipped", payload["safe_numeric_extractor_status"] == "skipped")
    check("structured missing: numeric skipped", payload["numeric_extraction_status"] == "skipped")
    assert_no_canary("structured missing", payload)


def test_structured_candidates_clean_verified() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        structured_numeric_candidates=structured_artifact([structured_candidate(value=0.2)]),
    )
    assert_structured_shape("structured clean", payload)
    assert_safe_shape("structured clean safe", payload)
    assert_numeric_shape("structured clean numeric", payload)
    check("structured clean: adapter ok", payload["structured_numeric_candidate_adapter_status"] == "ok")
    check("structured clean: adapter output count 1", payload["structured_numeric_candidate_adapter_summary"]["output_candidate_count"] == 1)
    check("structured clean: safe extractor ok", payload["safe_numeric_extractor_status"] == "ok")
    check("structured clean: numeric ok", payload["numeric_extraction_status"] == "ok")
    check("structured clean: recompute passed", payload["component_statuses"]["recompute"] == "passed", serialized(payload["component_statuses"]))
    check("structured clean: shippable", payload["shippable"] is True)
    assert_no_canary("structured clean", payload)


def test_structured_candidates_wrong_blocks() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        structured_numeric_candidates=structured_artifact([structured_candidate(value=0.9, rec_id="qs_struct_wrong")]),
    )
    assert_structured_shape("structured wrong", payload)
    check("structured wrong: adapter ok", payload["structured_numeric_candidate_adapter_status"] == "ok")
    check("structured wrong: safe extractor ok", payload["safe_numeric_extractor_status"] == "ok")
    check(
        "structured wrong: recompute blocker",
        any(item["component"] == "recompute" and item["check_id"] == "weighted_gini" for item in payload["blocking_failures"]),
        serialized(payload["blocking_failures"]),
    )
    check("structured wrong: status failed", payload["status"] == "failed", str(payload["status"]))
    check("structured wrong: not shippable", payload["shippable"] is False)
    check("structured wrong: safety floor red", payload["safety_floor_green"] is False)
    assert_no_canary("structured wrong", payload)


def test_structured_candidates_malformed_degrades() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        structured_numeric_candidates={"kind": "wrong", "candidates": []},
    )
    assert_structured_shape("structured malformed", payload)
    check(
        "structured malformed: failed",
        payload["structured_numeric_candidate_adapter_status"] == "failed",
        str(payload["structured_numeric_candidate_adapter_status"]),
    )
    check(
        "structured malformed: warning",
        "unsupported_artifact_kind" in payload["structured_numeric_candidate_adapter_warnings"],
        str(payload["structured_numeric_candidate_adapter_warnings"]),
    )
    check("structured malformed: safe skipped", payload["safe_numeric_extractor_status"] == "skipped")
    check("structured malformed: numeric skipped", payload["numeric_extraction_status"] == "skipped")
    assert_no_canary("structured malformed", payload)


def test_structured_candidates_precedence_explicit_and_safe_win() -> None:
    explicit_wins = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        numeric_extraction_records=[numeric_record(value=0.2)],
        safe_numeric_candidates=[safe_candidate(value=0.9, rec_id="qs_safe_loser")],
        structured_numeric_candidates=structured_artifact([structured_candidate(value=0.9, rec_id="qs_struct_loser")]),
    )
    assert_structured_shape("structured precedence explicit", explicit_wins)
    check("structured precedence explicit: adapter skipped", explicit_wins["structured_numeric_candidate_adapter_status"] == "skipped")
    check(
        "structured precedence explicit: superseded",
        "superseded_by_explicit_records" in explicit_wins["structured_numeric_candidate_adapter_warnings"],
        str(explicit_wins["structured_numeric_candidate_adapter_warnings"]),
    )
    check("structured precedence explicit: safe superseded", "superseded_by_explicit_records" in explicit_wins["safe_numeric_extractor_warnings"])
    check("structured precedence explicit: recompute passed", explicit_wins["component_statuses"]["recompute"] == "passed")
    check("structured precedence explicit: shippable", explicit_wins["shippable"] is True)

    safe_wins = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        safe_numeric_candidates=[safe_candidate(value=0.2, rec_id="qs_safe_winner")],
        structured_numeric_candidates=structured_artifact([structured_candidate(value=0.9, rec_id="qs_struct_loser")]),
    )
    assert_structured_shape("structured precedence safe", safe_wins)
    check("structured precedence safe: adapter skipped", safe_wins["structured_numeric_candidate_adapter_status"] == "skipped")
    check(
        "structured precedence safe: superseded",
        "superseded_by_safe_candidates" in safe_wins["structured_numeric_candidate_adapter_warnings"],
        str(safe_wins["structured_numeric_candidate_adapter_warnings"]),
    )
    check("structured precedence safe: safe extractor ok", safe_wins["safe_numeric_extractor_status"] == "ok")
    check("structured precedence safe: recompute passed", safe_wins["component_statuses"]["recompute"] == "passed")
    check("structured precedence safe: no structured blocker", not safe_wins["blocking_failures"])
    assert_no_canary("structured precedence explicit", explicit_wins)
    assert_no_canary("structured precedence safe", safe_wins)


def test_structured_candidates_unsupported_method() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.9),
        structured_numeric_candidates=structured_artifact(
            [structured_candidate(method="entropy", value=0.9, rec_id="qs_struct_unsupported")]
        ),
    )
    assert_structured_shape("structured unsupported", payload)
    check("structured unsupported: adapter warning", payload["structured_numeric_candidate_adapter_status"] == "warning")
    check("structured unsupported: counted", payload["structured_numeric_candidate_adapter_summary"]["unsupported_method_count"] == 1)
    check("structured unsupported: safe counted", payload["safe_numeric_extractor_summary"]["unsupported_method_count"] == 1)
    check(
        "structured unsupported: no recompute blocker",
        not any(item["component"] == "recompute" for item in payload["blocking_failures"]),
        serialized(payload["blocking_failures"]),
    )
    assert_no_canary("structured unsupported", payload)


def test_structured_candidates_not_fabricated_from_coverage() -> None:
    payload = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(),
        source_coverage_report=synthetic_source_coverage_report(),
        table_candidates_manifest={"status": "ok", "candidate_count": 5},
    )
    assert_structured_shape("structured vs coverage", payload)
    check("structured vs coverage: adapter skipped", payload["structured_numeric_candidate_adapter_status"] == "skipped")
    check("structured vs coverage: no adapter output", payload["structured_numeric_candidate_adapter_summary"]["output_candidate_count"] == 0)
    check("structured vs coverage: safe skipped", payload["safe_numeric_extractor_status"] == "skipped")
    check("structured vs coverage: numeric skipped", payload["numeric_extraction_status"] == "skipped")
    check("structured vs coverage: coverage present", payload["extraction_coverage_status"] in EXTRACTION_COVERAGE_STATUSES)
    check("structured vs coverage: coverage numeric 0", payload["extraction_coverage_summary"]["numeric_observation_count"] == 0)


def test_structured_candidates_hostile_stripped_no_mutation_and_deterministic() -> None:
    tainted = structured_candidate(value=0.2, rec_id="qs_struct_tainted")
    tainted.update(
        {
            "raw_text": HOSTILE_CANARIES[11],
            "source_text": "source text private marker",
            "guide_text": "CANDIDATE_PRIVATE_TEXT_MARKER",
            "ocr_text": HOSTILE_CANARIES[5],
            "page_text": "PAGE_TEXT_PRIVATE_JOB_ARTIFACT_MARKER",
            "table_cells": [HOSTILE_CANARIES[6]],
            "captions": HOSTILE_CANARIES[7],
            "formulas_as_text": HOSTILE_CANARIES[12],
            "evidence_quotes": HOSTILE_CANARIES[10],
            "filenames": HOSTILE_CANARIES[9],
            "basenames": "SYNTHETIC_BASENAME_TOKEN",
            "paths": HOSTILE_CANARIES[0],
            "urls": HOSTILE_CANARIES[2],
            "provider_payloads": HOSTILE_CANARIES[8],
            "runtime_traces": HOSTILE_CANARIES[3],
            "raw_exceptions": HOSTILE_CANARIES[1],
            "raw_artifact_json": "RAW_ARTIFACT_JSON_PRIVATE_MARKER",
        }
    )
    artifact = structured_artifact([tainted])
    snapshot = serialized(artifact)
    first = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        structured_numeric_candidates=artifact,
    )
    second = build_quality_safety_job_artifact_payload(
        candidate_markdown=candidate_markdown(value=0.2),
        structured_numeric_candidates=structured_artifact([dict(tainted)]),
    )
    assert_structured_shape("structured tainted", first)
    check("structured tainted: caller input unchanged", serialized(artifact) == snapshot)
    check("structured tainted: deterministic", serialized(first) == serialized(second))
    check("structured tainted: recompute passed", first["component_statuses"]["recompute"] == "passed", serialized(first["component_statuses"]))
    assert_no_canary("structured tainted", first)


def test_structured_candidates_sidecar_read_and_hook() -> None:
    from pipeline.quality_safety_job_artifact import (
        STRUCTURED_NUMERIC_CANDIDATES_ARTIFACT_NAME,
        read_quality_safety_structured_numeric_candidates,
    )
    from pipeline.run_markdown_job import _write_quality_safety_unified_qa

    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp) / "job"
        job_dir.mkdir()
        check("structured sidecar absent reads None", read_quality_safety_structured_numeric_candidates(job_dir) is None)
        absent = write_quality_safety_job_artifact(job_dir, candidate_markdown=candidate_markdown())
        check("structured sidecar absent: skipped", absent["structured_numeric_candidate_adapter_status"] == "skipped")

        (job_dir / STRUCTURED_NUMERIC_CANDIDATES_ARTIFACT_NAME).write_text(
            json.dumps(structured_artifact([structured_candidate(value=0.2)])),
            encoding="utf-8",
        )
        present = write_quality_safety_job_artifact(job_dir, candidate_markdown=candidate_markdown(value=0.2))
        check("structured sidecar present: adapter ok", present["structured_numeric_candidate_adapter_status"] == "ok")
        check("structured sidecar present: safe ok", present["safe_numeric_extractor_status"] == "ok")
        check("structured sidecar present: recompute passed", present["component_statuses"]["recompute"] == "passed")
        assert_no_canary("structured sidecar present", present)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        job = FakeJob(root)
        job.clean_md.write_text(candidate_markdown(value=0.9), encoding="utf-8")
        (root / STRUCTURED_NUMERIC_CANDIDATES_ARTIFACT_NAME).write_text(
            json.dumps(structured_artifact([structured_candidate(value=0.9, rec_id="qs_struct_hook_wrong")])),
            encoding="utf-8",
        )
        _write_quality_safety_unified_qa(job)
        loaded = json.loads(job.quality_safety_unified_qa_json.read_text(encoding="utf-8"))
        check("hook structured: adapter ok", loaded["structured_numeric_candidate_adapter_status"] == "ok")
        check("hook structured: safe ok", loaded["safe_numeric_extractor_status"] == "ok")
        check("hook structured: recompute blocker", any(item.get("component") == "recompute" for item in loaded.get("blocking_failures") or []))
        check("hook structured: not shippable", loaded["shippable"] is False)
        check("hook structured: safety floor red", loaded["safety_floor_green"] is False)
        assert_no_canary("hook structured", loaded)


def test_import_hygiene() -> None:
    source = (REPO / "pipeline" / "quality_safety_job_artifact.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    for item in imports:
        for forbidden in FORBIDDEN_IMPORT_PARTS:
            check(f"import {item!r} avoids {forbidden!r}", forbidden not in item.lower())
    check("imports allowed-only", set(imports) <= ALLOWED_IMPORTS, str(imports))

    server = (REPO / "api" / "server.py").read_text(encoding="utf-8")
    check("exact-name route present", 'artifact_name == "quality_safety_unified_qa.json"' in server)
    check("not generic artifact row", '"quality_safety_unified_qa.json": ("' not in server)


def run() -> int:
    test_pure_payload_without_extraction()
    test_payload_with_extraction_clean_and_wrong()
    test_missing_and_malformed_components()
    test_artifact_writing()
    test_production_hook_behavior()
    test_no_leak_sweep()
    test_extraction_coverage_skipped_without_metadata()
    test_extraction_coverage_populated()
    test_extraction_coverage_excludes_hostile_fields()
    test_extraction_coverage_does_not_upgrade_safety()
    test_extraction_coverage_no_mutation_and_deterministic()
    test_extraction_coverage_adapter_failure_degrades()
    test_production_hook_reads_sibling_artifacts()
    test_numeric_records_missing_degrades()
    test_numeric_records_clean_verified()
    test_numeric_records_wrong_blocks()
    test_numeric_records_confident_wrong_case()
    test_numeric_records_clean_real_case()
    test_numeric_records_malformed_degrades()
    test_numeric_records_dict_wrapper()
    test_numeric_records_separate_from_coverage()
    test_numeric_not_fabricated_from_coverage()
    test_numeric_records_hostile_stripped()
    test_numeric_records_no_mutation()
    test_numeric_records_sidecar_read()
    test_production_hook_reads_numeric_sidecar()
    test_safe_candidates_missing_degrades()
    test_safe_candidates_clean_verified()
    test_safe_candidates_wrong_blocks()
    test_safe_candidates_malformed_degrades()
    test_safe_candidates_dict_wrapper()
    test_safe_candidates_precedence_explicit_wins()
    test_safe_candidates_unsupported_method()
    test_safe_candidates_not_fabricated_from_coverage()
    test_safe_candidates_hostile_stripped()
    test_safe_candidates_no_mutation_and_deterministic()
    test_safe_candidates_sidecar_read()
    test_production_hook_reads_safe_candidates_sidecar()
    test_structured_candidates_missing_degrades()
    test_structured_candidates_clean_verified()
    test_structured_candidates_wrong_blocks()
    test_structured_candidates_malformed_degrades()
    test_structured_candidates_precedence_explicit_and_safe_win()
    test_structured_candidates_unsupported_method()
    test_structured_candidates_not_fabricated_from_coverage()
    test_structured_candidates_hostile_stripped_no_mutation_and_deterministic()
    test_structured_candidates_sidecar_read_and_hook()
    test_import_hygiene()
    print(f"\nquality_safety_job_artifact: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
