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
    "artifact_write_failed",
    "component_degraded",
    "unsafe_metadata_dropped",
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
    "pipeline.quality_safety_fact_sheet_producer",
    "pipeline.quality_safety_leak_scanner",
    "pipeline.quality_safety_recompute_verifier",
    "pipeline.quality_safety_unified_qa",
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
    test_import_hygiene()
    print(f"\nquality_safety_job_artifact: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
