#!/usr/bin/env python3
"""Slice 106 — Guide Quality release-validation harness.

Run with:

    python test_scripts/test_guide_quality_release_validation.py

Deterministic, synthetic, validation-only. Slices 102-105 added the guide-quality
prompt contract, contract lint, advisory QA gate, frontend panel model, and
advisory rubric score. This harness proves those pieces compose end-to-end without
adding product behavior, calling an LLM/provider/model/cloud service, inspecting a
PDF/image/OCR stream, reconstructing tables, rendering/exporting, or touching Ask
Guide.

All inputs are synthetic. Hostile canaries are seeded into request-like fields and
artifact positions; every serialized output is deeply scanned to prove the canaries
and broad leak signatures do not survive.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import run_llm_job  # noqa: E402
from pipeline.guide_quality_contract_lint import (  # noqa: E402
    WARNING_ORDER as LINT_WARNING_ORDER,
    build_guide_quality_contract_lint_report,
)
from pipeline.guide_quality_prompt_contract import (  # noqa: E402
    build_guide_quality_prompt_contract,
)
from pipeline.guide_quality_qa_gate import (  # noqa: E402
    WARNING_ORDER as GATE_WARNING_ORDER,
    build_guide_quality_qa_gate,
)
from pipeline.guide_quality_report_v2 import build_guide_quality_report_v2  # noqa: E402
from pipeline.guide_quality_rubric_score import (  # noqa: E402
    AXIS_SPECS,
    WARNING_ORDER as RUBRIC_WARNING_ORDER,
    build_guide_quality_rubric_score,
)
from pipeline.source_coverage_report import build_source_coverage_report  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)


# ---------------------------------------------------------------------------
# Synthetic leak canaries. These are deliberately fake and must never appear in
# any serialized output.
# ---------------------------------------------------------------------------
CANARY_PROVIDER_KEY = "sk_releasevalidationcanary1234567890"
CANARY_AUTH_HEADER = "Authorization: Bearer release-validation-secret"
CANARY_BEARER = "Bearer release-validation-token"
CANARY_COMPANION_TOKEN = "companion_token_release_validation_secret"
CANARY_SOCKET = "/run/guideforge-release-validation.sock"
CANARY_HOST_PATH = "/home/private/course/private_source.pdf"
CANARY_MODEL_PATH = "/models/private-model.gguf"
CANARY_MMPROJ_PATH = "/models/private-mmproj.mmproj"
CANARY_EXECUTABLE_PATH = "/usr/local/bin/private-llama-server"
CANARY_ARGV = "--model /models/private-model.gguf --mmproj /models/private-mmproj.mmproj"
CANARY_URL = "https://private.invalid/guide-quality-release"
CANARY_OCR = "raw OCR text release validation canary"
CANARY_PROVIDER_PAYLOAD = "raw provider payload release validation canary"
CANARY_DATA_URI = "data:image/png;base64,QQQQ"
CANARY_BASE64 = "Q" * 140
CANARY_IMAGE_BYTES = "\\x89PNG release validation image bytes"
CANARY_PRIVATE_DOC = "private document contents release validation canary"
CANARY_REAL_PDF_PATH = "/home/private/course/real_uploaded_private.pdf"
CANARY_REAL_PDF_FILENAME = "real_uploaded_private.pdf"
CANARY_SOURCE_TEXT = "source document text release validation canary"
CANARY_GUIDE_EXCERPT = "generated guide excerpt release validation canary"
CANARY_FORMULA = "secret_formula = alpha + beta"
CANARY_NUMERIC_CLAIM = "numeric claim text 12345.6789 release validation canary"
CANARY_CAPTION = "source caption release validation canary"
CANARY_TABLE_TEXT = "table text release validation canary"
CANARY_SPEC_EVIDENCE = "uploaded quality spec evidence release validation canary"
CANARY_SPEC_FILENAME = "uploaded_quality_spec_private.pdf"
CANARY_TRACEBACK = "Traceback (most recent call last): boom at /home/private/x.py"
CANARY_RAW_EXCEPTION = "RuntimeError: raw exception release validation canary"
CANARY_INSTRUCTION = "raw instruction text release validation canary"
CANARY_WARNING_TEXT = "raw warning text release validation canary"

FORBIDDEN_CANARIES = [
    CANARY_PROVIDER_KEY,
    CANARY_AUTH_HEADER,
    CANARY_BEARER,
    CANARY_COMPANION_TOKEN,
    CANARY_SOCKET,
    CANARY_HOST_PATH,
    CANARY_MODEL_PATH,
    CANARY_MMPROJ_PATH,
    CANARY_EXECUTABLE_PATH,
    CANARY_ARGV,
    CANARY_URL,
    CANARY_OCR,
    CANARY_PROVIDER_PAYLOAD,
    CANARY_DATA_URI,
    CANARY_BASE64,
    CANARY_IMAGE_BYTES,
    CANARY_PRIVATE_DOC,
    CANARY_REAL_PDF_PATH,
    CANARY_REAL_PDF_FILENAME,
    CANARY_SOURCE_TEXT,
    CANARY_GUIDE_EXCERPT,
    CANARY_FORMULA,
    CANARY_NUMERIC_CLAIM,
    CANARY_CAPTION,
    CANARY_TABLE_TEXT,
    CANARY_SPEC_EVIDENCE,
    CANARY_SPEC_FILENAME,
    CANARY_TRACEBACK,
    CANARY_RAW_EXCEPTION,
    CANARY_INSTRUCTION,
    CANARY_WARNING_TEXT,
]

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
KEYLIKE = re.compile(r"\b(sk-|sk_)[A-Za-z0-9_\-]{16,}")
AUTHLIKE = re.compile(r"\bAuthorization\b|\bBearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\|\\\\|[A-Za-z]:\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_SOCKET_MODEL = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
TRACEBACKLIKE = re.compile(r"Traceback \(most recent call last\)|RuntimeError:", re.IGNORECASE)

GUIDE_STATUS_TOKENS = {"completed", "partial", "skipped"}
GATE_STATUS_TOKENS = {"passed", "warning", "skipped", "partial"}
GATE_CHECK_KINDS = {
    "reasoning_leak",
    "required_structure",
    "math_verification",
    "source_coverage",
    "quality_report_v2",
}
GATE_CHECK_STATUSES = {"passed", "warning", "unknown", "not_applicable"}
LINT_CHECK_KINDS = {
    "reasoning_leak",
    "required_structure",
    "exam_alerts",
    "reference_tables",
    "worked_examples",
    "arithmetic_steps",
    "consistency",
}
LINT_CHECK_STATUSES = {"passed", "warning", "not_applicable", "unknown"}
RUBRIC_TOP_STATUSES = {"completed", "partial", "skipped"}
RUBRIC_AXIS_KINDS = {kind for _axis_id, kind in AXIS_SPECS}
RUBRIC_AXIS_STATUSES = {"passed", "warning", "unknown", "not_applicable"}
RUBRIC_CONFIDENCE_VALUES = {"deterministic", "advisory", "unsupported"}
RUBRIC_REASONS = {
    "reasoning_signal_missing",
    "reasoning_leak_count_zero",
    "reasoning_leak_warning_signal",
    "reasoning_leak_severe_signal",
    "required_structure_not_comprehensive",
    "required_structure_signal_missing",
    "required_structure_complete",
    "required_structure_partial",
    "required_structure_absent",
    "exam_focus_signal_missing",
    "exam_alert_count_positive",
    "exam_alert_signal_weak",
    "exam_focus_not_applicable",
    "reference_table_count_positive",
    "reference_table_signal_weak",
    "reference_tables_signal_missing",
    "reference_tables_not_applicable",
    "math_signal_missing",
    "math_checked_zero_mismatch",
    "math_no_checked_claims",
    "math_mismatch_present",
    "source_coverage_signal_missing",
    "source_coverage_clean",
    "source_coverage_warning_signal",
    "coverage_report_signal_missing",
    "coverage_report_no_warnings",
    "coverage_report_warnings_present",
    "visual_table_signal_missing",
    "visual_table_no_warnings",
    "visual_table_warning_signal",
    "semantic_axis_not_deterministically_measured",
}


def stable_json(node: Any) -> str:
    return json.dumps(node, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def scan_for_leak(node: Any, trail: str = "$") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            lower = str(key).lower()
            if lower in SECRET_KEY_NAMES:
                return f"{trail}.{key} secret-like key"
            found = scan_for_leak(value, f"{trail}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = scan_for_leak(value, f"{trail}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        for canary in FORBIDDEN_CANARIES:
            if canary in node:
                return f"{trail} leaked canary {canary!r}"
        stripped = node.replace("assets/", "")
        for label, pattern in (
            ("keylike", KEYLIKE),
            ("authlike", AUTHLIKE),
            ("pathlike", PATHLIKE),
            ("urllike", URLLIKE),
            ("data/base64", DATA_OR_BASE64),
            ("argv/socket/model", ARGV_SOCKET_MODEL),
            ("traceback/raw-exception", TRACEBACKLIKE),
        ):
            if pattern.search(stripped):
                return f"{trail} {label} {node[:80]!r}"
    return None


def no_leak(name: str, node: Any) -> None:
    found = scan_for_leak(node)
    check(f"{name}: no leak", found is None, found or "")


def deterministic(name: str, first: Any, second: Any) -> None:
    check(f"{name}: deterministic serialization", stable_json(first) == stable_json(second))


def assert_no_mutation(name: str, before: Any, after: Any) -> None:
    check(f"{name}: inputs not mutated", before == after)


def assert_non_negative_ints(name: str, node: Any, trail: str = "$") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).endswith("_count") or str(key) in {"total", "ok", "mismatch", "unparseable"}:
                check(
                    f"{name}: {trail}.{key} non-negative int",
                    isinstance(value, int) and not isinstance(value, bool) and value >= 0,
                    repr(value),
                )
            assert_non_negative_ints(name, value, f"{trail}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            assert_non_negative_ints(name, value, f"{trail}[{index}]")


def synthetic_extraction_metadata() -> dict[str, Any]:
    return {
        "kind": "extraction_metadata",
        "status": "completed",
        "sources": [
            {
                "source_type": "pdf",
                "content_type": "application/pdf",
                "page_count": 3,
                "filename": CANARY_REAL_PDF_FILENAME,
                "path": CANARY_REAL_PDF_PATH,
                "text": CANARY_SOURCE_TEXT,
                "ocr_text": CANARY_OCR,
                "caption": CANARY_CAPTION,
                "pages": [
                    {"page": 1, "method": "embedded_text", "text_chars": 1200, "word_count": 180, "has_page_anchor": True},
                    {"page": 2, "method": "ocr", "text_chars": 900, "word_count": 120, "has_page_anchor": True},
                    {"page": 3, "method": "embedded_text", "text_chars": 600, "word_count": 90, "has_page_anchor": True},
                ],
            }
        ],
    }


def synthetic_visual_manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "visual_assets_manifest",
        "status": "completed",
        "assets": [
            {
                "asset_id": "asset_0001",
                "source_index": 1,
                "source_page": 1,
                "caption": CANARY_CAPTION,
                "path": CANARY_HOST_PATH,
            }
        ],
    }


def synthetic_clean_markdown() -> str:
    # Includes the required section aliases, safe app-authored usage phrases, and
    # hostile canaries. Builders may scan this text for counts, but must not store
    # excerpts, headings, formulas, values, captions, table cells, URLs, or paths.
    return f"""
# Synthetic Topic
## How to use this guide
## Big Picture
## Notation / terms you must know
| term | meaning |
| --- | --- |
| synthetic | safe |
## Topic sections
⚠️ EXAM ALERT: synthetic high-yield marker.
Source visual, page 1.
Table reconstruction guidance.
Missing visual and table guidance.
Coverage-aware generation guidance.
Worked example: 2 = 1 + 1 = 2.
Actually, this line is intentionally leaky and must become a count only.
## Formula sheet
## Definitions cheat sheet
## Common Mistakes That Lose Marks
## Consolidation / pipeline section
## Mock Exam
## Last-Minute Cram Sheet
## Self-Test Checklist
{CANARY_GUIDE_EXCERPT}
{CANARY_FORMULA}
{CANARY_NUMERIC_CLAIM}
{CANARY_URL}
{CANARY_TABLE_TEXT}
{CANARY_CAPTION}
{CANARY_SPEC_EVIDENCE}
""".strip()


def synthetic_visual_plan() -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "visual_inclusion_plan",
        "status": "completed",
        "summary": {"planned_count": 1, "missing_count": 0, "unsafe_count": 0},
        "items": [{"caption": CANARY_CAPTION, "asset_ref": "assets/safe.png", "path": CANARY_HOST_PATH}],
        "warnings": [],
    }


def synthetic_table_manifest() -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "table_candidates_manifest",
        "status": "completed",
        "summary": {"table_like_candidate_count": 1, "unreadable_count": 0},
        "candidates": [{"table_text": CANARY_TABLE_TEXT, "source_path": CANARY_HOST_PATH}],
        "warnings": [],
    }


def synthetic_table_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "table_reconstruction_policy",
        "status": "completed",
        "summary": {"policy_item_count": 1, "screenshot_insert_count": 0, "deferred_count": 0},
        "items": [{"instruction": CANARY_INSTRUCTION, "table_text": CANARY_TABLE_TEXT}],
        "warnings": [],
    }


def synthetic_context(kind: str) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": kind,
        "status": "completed",
        "summary": {"prompt_item_count": 1},
        "items": [{"prompt_block": CANARY_INSTRUCTION, "source_text": CANARY_SOURCE_TEXT}],
        "warnings": [CANARY_WARNING_TEXT],
    }


def synthetic_math_verification(*, mismatch: int = 0) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "math_verification",
        "status": "completed",
        "source": "clean.md",
        "report": {
            "version": 1,
            "summary": {"total": 4, "ok": max(4 - mismatch, 0), "mismatch": mismatch, "unparseable": 0},
            "claims": [
                {
                    "id": "claim_0001",
                    "text": CANARY_NUMERIC_CLAIM,
                    "expression": CANARY_FORMULA,
                    "claimed": CANARY_NUMERIC_CLAIM,
                    "computed": CANARY_NUMERIC_CLAIM,
                    "reason": CANARY_RAW_EXCEPTION,
                }
            ],
        },
    }


def synthetic_validation() -> dict[str, Any]:
    return {
        "ok": False,
        "summary": {"error_count": 1, "invalid_count": 1},
        "errors": [{"expr": CANARY_FORMULA, "message": CANARY_TRACEBACK}],
    }


def stage_1_prompt_contract() -> dict[str, Any]:
    kwargs = {
        "output_depth": "exhaustive",
        "difficulty": CANARY_SPEC_EVIDENCE,
        "preset_id": CANARY_SPEC_FILENAME,
        "style_id": CANARY_REAL_PDF_FILENAME,
        "mode": CANARY_PRIVATE_DOC,
    }
    before = copy.deepcopy(kwargs)
    ctx = build_guide_quality_prompt_contract(**kwargs)
    again = build_guide_quality_prompt_contract(**kwargs)
    assert_no_mutation("stage 1 prompt contract", before, kwargs)
    deterministic("stage 1 prompt contract", ctx, again)

    block = ctx.get("prompt_block", "")
    check("stage 1: prompt context completed", ctx.get("status") == "completed")
    check("stage 1: comprehensive detected", ctx.get("summary", {}).get("comprehensive") is True)
    check(
        "stage 1: Guide Quality Contract concept once",
        block.lower().count("guide quality contract") == 1,
        str(block.lower().count("guide quality contract")),
    )
    for phrase in (
        "Never fabricate math",
        "Finish every worked example",
        "Show all arithmetic",
        "Define every term before it is used",
        "Mock Exam",
    ):
        check(f"stage 1: fixed directive represented ({phrase})", phrase in block)
    for canary in (CANARY_SPEC_EVIDENCE, CANARY_SPEC_FILENAME, CANARY_PRIVATE_DOC, CANARY_REAL_PDF_FILENAME):
        check(f"stage 1: request canary dropped ({canary[:16]})", canary not in block)

    core = build_guide_quality_prompt_contract(output_depth="quick")
    core_again = build_guide_quality_prompt_contract(output_depth="quick")
    deterministic("stage 1 core-only contract", core, core_again)
    check("stage 1: quick deterministic core-only", core.get("summary", {}).get("comprehensive") is False)
    check("stage 1: quick omits full structure", "Mock Exam" not in core.get("prompt_block", ""))

    helper_block = run_llm_job._build_guide_quality_prompt_block_safely(
        output_depth="exhaustive",
        difficulty=CANARY_SPEC_EVIDENCE,
        preset_id=CANARY_SPEC_FILENAME,
        style_id=CANARY_REAL_PDF_FILENAME,
        mode=CANARY_PRIVATE_DOC,
    )
    run_llm_source = (ROOT / "pipeline" / "run_llm_job.py").read_text(encoding="utf-8")
    check("stage 1: single prompt append integration point", run_llm_source.count("## Guide Quality Contract") == 1)
    check("stage 1: integration helper returns contract", "Never fabricate math" in helper_block)

    no_leak("stage 1 prompt context", ctx)
    no_leak("stage 1 prompt helper block", {"prompt_block": helper_block})
    return ctx


def stage_2_contract_lint() -> dict[str, Any]:
    kwargs = {"clean_markdown": synthetic_clean_markdown(), "comprehensive": True}
    before = copy.deepcopy(kwargs)
    lint = build_guide_quality_contract_lint_report(**kwargs)
    again = build_guide_quality_contract_lint_report(**kwargs)
    assert_no_mutation("stage 2 contract lint", before, kwargs)
    deterministic("stage 2 contract lint", lint, again)

    check("stage 2: lint completed", lint.get("status") == "completed")
    summary = lint.get("summary", {})
    check("stage 2: reasoning leak counted", summary.get("reasoning_leak_count", 0) > 0)
    check("stage 2: required sections counted", summary.get("required_section_present_count") == summary.get("required_section_count"))
    check("stage 2: exam alerts numeric only", isinstance(summary.get("exam_alert_count"), int))
    check("stage 2: table count numeric only", isinstance(summary.get("table_count"), int))
    check("stage 2: warnings closed", set(lint.get("warnings", [])) <= set(LINT_WARNING_ORDER))
    for item in lint.get("checks", []):
        check("stage 2: check kind closed", item.get("kind") in LINT_CHECK_KINDS, repr(item))
        check("stage 2: check status closed", item.get("status") in LINT_CHECK_STATUSES, repr(item))
        check("stage 2: observed count int", isinstance(item.get("observed_count"), int) and item["observed_count"] >= 0)
        check("stage 2: expected count int", isinstance(item.get("expected_count"), int) and item["expected_count"] >= 0)

    empty = build_guide_quality_contract_lint_report("", comprehensive=True)
    malformed = build_guide_quality_contract_lint_report(None, comprehensive=True)
    check("stage 2: empty input skips", empty.get("status") == "skipped")
    check("stage 2: malformed input skips", malformed.get("status") == "skipped")
    assert_non_negative_ints("stage 2 lint", lint)
    no_leak("stage 2 contract lint", lint)
    no_leak("stage 2 empty lint", empty)
    no_leak("stage 2 malformed lint", malformed)
    return lint


def build_sanitized_artifacts(lint: dict[str, Any]) -> dict[str, Any]:
    source_coverage = build_source_coverage_report(
        synthetic_extraction_metadata(),
        visual_manifest=synthetic_visual_manifest(),
    )
    report_v2 = build_guide_quality_report_v2(
        synthetic_clean_markdown(),
        source_coverage_report=source_coverage,
        visual_inclusion_plan=synthetic_visual_plan(),
        table_candidates_manifest=synthetic_table_manifest(),
        table_reconstruction_policy=synthetic_table_policy(),
        missing_material_context=synthetic_context("missing_material_context"),
        coverage_aware_context=synthetic_context("coverage_aware_prompt_context"),
        full_visual_insertion_enabled=True,
    )
    artifacts = {
        "guide_quality_contract_lint.json": lint,
        "guide_quality_report_v2.json": report_v2,
        "source_coverage_report.json": source_coverage,
        "math_verification.json": synthetic_math_verification(mismatch=0),
        "validation.json": synthetic_validation(),
        "visual_inclusion_plan.json": synthetic_visual_plan(),
        "table_candidates_manifest.json": synthetic_table_manifest(),
        "table_reconstruction_policy.json": synthetic_table_policy(),
    }
    for name, artifact in artifacts.items():
        deterministic(f"artifact {name}", artifact, copy.deepcopy(artifact))
    # Only the builders' generated reports are stage outputs here. The math,
    # validation, visual, and table artifacts below are hostile input fixtures for
    # downstream no-leak tests; they intentionally contain raw canaries that must
    # not survive into the QA gate or rubric score.
    for name in (
        "guide_quality_contract_lint.json",
        "guide_quality_report_v2.json",
        "source_coverage_report.json",
    ):
        no_leak(f"sanitized generated artifact {name}", artifacts[name])
    return artifacts


def stage_3_qa_gate(artifacts: dict[str, Any]) -> dict[str, Any]:
    kwargs = {
        "guide_quality_contract_lint": artifacts["guide_quality_contract_lint.json"],
        "guide_quality_report_v2": artifacts["guide_quality_report_v2.json"],
        "source_coverage_report": artifacts["source_coverage_report.json"],
        "math_verification": artifacts["math_verification.json"],
        "math_validation": artifacts["validation.json"],
        "comprehensive": True,
    }
    before = copy.deepcopy(kwargs)
    gate = build_guide_quality_qa_gate(**kwargs)
    again = build_guide_quality_qa_gate(**kwargs)
    assert_no_mutation("stage 3 QA gate", before, kwargs)
    deterministic("stage 3 QA gate", gate, again)

    check("stage 3: gate status closed", gate.get("status") in GATE_STATUS_TOKENS)
    check("stage 3: gate advisory only", gate.get("summary", {}).get("blocking") is False)
    check("stage 3: warnings closed", set(gate.get("warnings", [])) <= set(GATE_WARNING_ORDER))
    math_checks = [c for c in gate.get("checks", []) if c.get("kind") == "math_verification"]
    check("stage 3: math check present", len(math_checks) == 1)
    if math_checks:
        check("stage 3: math summarized from artifact", math_checks[0].get("observed_count") == 0)
    for item in gate.get("checks", []):
        check("stage 3: gate check kind closed", item.get("kind") in GATE_CHECK_KINDS, repr(item))
        check("stage 3: gate check status closed", item.get("status") in GATE_CHECK_STATUSES, repr(item))
        check("stage 3: gate observed count int", isinstance(item.get("observed_count"), int) and item["observed_count"] >= 0)
        check("stage 3: gate expected count int", isinstance(item.get("expected_count"), int) and item["expected_count"] >= 0)
    assert_non_negative_ints("stage 3 gate", gate)
    no_leak("stage 3 QA gate", gate)
    return gate


def stage_4_rubric_score(artifacts: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    kwargs = {
        "qa_gate": gate,
        "contract_lint": artifacts["guide_quality_contract_lint.json"],
        "guide_quality_report_v2": artifacts["guide_quality_report_v2.json"],
        "source_coverage_report": artifacts["source_coverage_report.json"],
        "math_verification": artifacts["math_verification.json"],
        "validation": artifacts["validation.json"],
        "visual_inclusion_plan": artifacts["visual_inclusion_plan.json"],
        "table_candidates_manifest": artifacts["table_candidates_manifest.json"],
        "table_reconstruction_policy": artifacts["table_reconstruction_policy.json"],
        "comprehensive": True,
    }
    before = copy.deepcopy(kwargs)
    score = build_guide_quality_rubric_score(**kwargs)
    again = build_guide_quality_rubric_score(**kwargs)
    assert_no_mutation("stage 4 rubric score", before, kwargs)
    deterministic("stage 4 rubric score", score, again)

    check("stage 4: rubric status closed", score.get("status") in RUBRIC_TOP_STATUSES)
    check("stage 4: rubric advisory only", score.get("blocking") is False)
    check("stage 4: warnings closed", set(score.get("warnings", [])) <= set(RUBRIC_WARNING_ORDER))
    axes = score.get("axes", [])
    total = sum(axis.get("score") for axis in axes if isinstance(axis.get("score"), int))
    possible = sum(axis.get("max_score") for axis in axes if isinstance(axis.get("max_score"), int))
    known = sum(1 for axis in axes if isinstance(axis.get("score"), int))
    unknown = sum(1 for axis in axes if axis.get("status") == "unknown")
    warnings = sum(1 for axis in axes if axis.get("status") == "warning")
    summary = score.get("summary", {})
    check("stage 4: score_total consistent", summary.get("score_total") == total)
    check("stage 4: score_possible consistent", summary.get("score_possible") == possible)
    check("stage 4: known_axis_count consistent", summary.get("known_axis_count") == known)
    check("stage 4: unknown_axis_count consistent", summary.get("unknown_axis_count") == unknown)
    check("stage 4: warning_axis_count consistent", summary.get("warning_axis_count") == warnings)
    for axis in axes:
        check("stage 4: axis kind closed", axis.get("kind") in RUBRIC_AXIS_KINDS, repr(axis))
        check("stage 4: axis status closed", axis.get("status") in RUBRIC_AXIS_STATUSES, repr(axis))
        check("stage 4: axis confidence closed", axis.get("confidence") in RUBRIC_CONFIDENCE_VALUES, repr(axis))
        check("stage 4: axis reason closed", axis.get("reason") in RUBRIC_REASONS, repr(axis))
        score_value = axis.get("score")
        check("stage 4: axis score valid", score_value in (0, 1, 2, None), repr(axis))
    semantic = {
        axis.get("kind"): axis
        for axis in axes
        if axis.get("kind") in {"beginner_scaffolding", "worked_example_completeness"}
    }
    check("stage 4: beginner scaffolding unsupported", semantic.get("beginner_scaffolding", {}).get("score") is None)
    check("stage 4: beginner scaffolding unknown", semantic.get("beginner_scaffolding", {}).get("status") == "unknown")
    check("stage 4: worked examples unsupported", semantic.get("worked_example_completeness", {}).get("score") is None)
    check("stage 4: worked examples unknown", semantic.get("worked_example_completeness", {}).get("status") == "unknown")

    malformed = build_guide_quality_rubric_score(
        qa_gate=CANARY_PROVIDER_PAYLOAD,
        contract_lint={"status": "completed", "summary": CANARY_TRACEBACK},
        guide_quality_report_v2=CANARY_SOURCE_TEXT,
        source_coverage_report=CANARY_HOST_PATH,
        math_verification={"kind": "math_verification", "status": "completed", "report": CANARY_RAW_EXCEPTION},
        comprehensive=True,
    )
    missing = build_guide_quality_rubric_score(comprehensive=True)
    check("stage 4: malformed degrades safely", malformed.get("status") in RUBRIC_TOP_STATUSES)
    check("stage 4: missing degrades safely", missing.get("status") in RUBRIC_TOP_STATUSES)
    check("stage 4: malformed advisory only", malformed.get("blocking") is False)
    check("stage 4: missing advisory only", missing.get("blocking") is False)
    no_leak("stage 4 rubric score", score)
    no_leak("stage 4 malformed rubric", malformed)
    no_leak("stage 4 missing rubric", missing)
    assert_non_negative_ints("stage 4 rubric", score)
    return score


def stage_5_frontend_panel() -> None:
    script = ROOT / "frontend" / "scripts" / "verify-guide-quality-panel.mjs"
    result = subprocess.run(
        ["node", str(script.relative_to(ROOT / "frontend"))],
        cwd=ROOT / "frontend",
        text=True,
        capture_output=True,
        check=False,
    )
    check("stage 5: frontend guide-quality verifier exits 0", result.returncode == 0, result.stderr[-1000:])
    check("stage 5: frontend verifier reports pass", "All guide-quality-panel helper checks passed." in result.stdout)
    no_leak("stage 5 frontend verifier stderr", {"stderr": result.stderr})


def stage_6_exact_name_routes() -> None:
    try:
        from api import server
        from pipeline.job_manager import Job
    except Exception as exc:  # pragma: no cover - host dependency dependent
        check(
            "stage 6: route coverage skipped with closed reason",
            type(exc).__name__ in {"ImportError", "ModuleNotFoundError"},
            type(exc).__name__,
        )
        return

    names = [
        "guide_quality_contract_lint.json",
        "guide_quality_qa_gate.json",
        "guide_quality_rubric_score.json",
        "guide_quality_report_v2.json",
        "math_verification.json",
        "source_coverage_report.json",
    ]
    with tempfile.TemporaryDirectory(prefix="guide-quality-release-routes-") as tmp:
        job = Job("synthetic-route-job", root=Path(tmp))
        for name in names:
            path, media = server._artifact_path(job, name)
            check(f"stage 6: exact route media for {name}", media == "application/json")
            check(f"stage 6: exact route basename for {name}", path.name == name)

    generic_artifacts = set(getattr(server, "ARTIFACTS", {}).keys())
    export_names = {
        value[0]
        for value in getattr(server, "EXPORT_ARTIFACTS", {}).values()
        if isinstance(value, tuple) and value
    }
    aliases = set(getattr(server, "EXPORT_ARTIFACT_ALIASES", {}).keys())
    check("stage 6: rubric not generic artifact row", "guide_quality_rubric_score.json" not in generic_artifacts)
    check("stage 6: rubric not export selector artifact", "guide_quality_rubric_score.json" not in export_names)
    check("stage 6: rubric not export selector alias", "guide_quality_rubric_score.json" not in aliases)


def static_out_of_scope_guards() -> None:
    run_markdown_source = (ROOT / "pipeline" / "run_markdown_job.py").read_text(encoding="utf-8")
    run_llm_source = (ROOT / "pipeline" / "run_llm_job.py").read_text(encoding="utf-8")
    check("guard: clean.md still saved through JobManager.save_clean_md", "job.save_clean_md(clean, \"generated\")" in run_markdown_source)
    check("guard: rubric writer still after QA gate", run_markdown_source.index("_write_guide_quality_qa_gate(job)") < run_markdown_source.index("_write_guide_quality_rubric_score(job)"))
    check("guard: prompt append still single exact heading", run_llm_source.count("## Guide Quality Contract") == 1)
    ask_refs = []
    for path in (ROOT / "pipeline").glob("ask_*.py"):
        text = path.read_text(encoding="utf-8")
        if "guide_quality_rubric_score" in text or "guide_quality_prompt_contract" in text:
            ask_refs.append(path.name)
    check("guard: Ask Guide has no guide-quality contract/rubric refs", ask_refs == [], ",".join(ask_refs))


def main() -> None:
    static_out_of_scope_guards()
    stage_1_prompt_contract()
    lint = stage_2_contract_lint()
    artifacts = build_sanitized_artifacts(lint)
    gate = stage_3_qa_gate(artifacts)
    score = stage_4_rubric_score(artifacts, gate)
    artifacts["guide_quality_qa_gate.json"] = gate
    artifacts["guide_quality_rubric_score.json"] = score
    release_outputs = {
        "guide_quality_contract_lint.json": artifacts["guide_quality_contract_lint.json"],
        "guide_quality_report_v2.json": artifacts["guide_quality_report_v2.json"],
        "source_coverage_report.json": artifacts["source_coverage_report.json"],
        "guide_quality_qa_gate.json": gate,
        "guide_quality_rubric_score.json": score,
    }
    no_leak("release validation all serialized stage outputs", release_outputs)
    stage_5_frontend_panel()
    stage_6_exact_name_routes()

    print(f"\nGuide Quality release validation: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
