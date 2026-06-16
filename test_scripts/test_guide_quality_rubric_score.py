#!/usr/bin/env python3
"""Focused tests for guide_quality_rubric_score.json (Slice 105).

Synthetic sanitized dicts only. No source documents, real filenames, OCR text,
PDF/image bytes, provider calls, or cloud calls are used.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
FORBIDDEN_KEY_NAMES = {
    "filename",
    "path",
    "title",
    "text",
    "ocr_text",
    "caption",
    "table_text",
    "image_ref",
    "asset_ref",
    "asset_id",
    "url",
    "argv",
    "socket",
    "bytes",
    "excerpt",
    "formula",
    "claims",
    "claim",
    "report_error",
}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")

CANARY_FILENAME = "private_uploaded_source.pdf"
CANARY_PATH = "/home/private/course/private_uploaded_source.pdf"
CANARY_TEXT = "raw uploaded source text must not appear"
CANARY_OCR = "ocr dump private words"
CANARY_CAPTION = "private source caption"
CANARY_TABLE = "private table row value"
CANARY_FORMULA = "secret_numeric_claim = 19.75"
CANARY_URL = "https://private.invalid/raw"
CANARY_DATA_URI = "data:image/png;base64," + ("A" * 140)
CANARY_PAYLOAD = "provider payload private content"
CANARY_KEY = "sk_rubricscorecanary1234567890"
CANARY_TRACEBACK = "Traceback (most recent call last): boom at /home/private/x.py"
FORBIDDEN_CANARIES = [
    CANARY_FILENAME,
    CANARY_PATH,
    CANARY_TEXT,
    CANARY_OCR,
    CANARY_CAPTION,
    CANARY_TABLE,
    CANARY_FORMULA,
    CANARY_URL,
    CANARY_DATA_URI,
    CANARY_PAYLOAD,
    CANARY_KEY,
    CANARY_TRACEBACK,
]

from pipeline.guide_quality_rubric_score import (  # noqa: E402
    KIND,
    VERSION,
    build_guide_quality_rubric_score,
)


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


def axis(score: dict, kind: str) -> dict:
    for item in score["axes"]:
        if item["kind"] == kind:
            return item
    raise AssertionError(kind)


def _scan_for_leak(node: Any, trail: str = "score") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            lower = str(key).lower()
            if lower in SECRET_KEY_NAMES:
                return f"{trail}.{key} secret-like key"
            if lower in FORBIDDEN_KEY_NAMES:
                return f"{trail}.{key} forbidden key"
            found = _scan_for_leak(value, f"{trail}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_leak(value, f"{trail}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        for canary in FORBIDDEN_CANARIES:
            if canary in node:
                return f"{trail} canary {canary!r}"
        for label, pattern in (
            ("keylike", KEYLIKE),
            ("pathlike", PATHLIKE),
            ("urllike", URLLIKE),
            ("data/base64", DATA_OR_BASE64),
            ("argv/socket", ARGV_OR_SOCKET),
        ):
            if pattern.search(node):
                return f"{trail} {label} {node[:48]!r}"
    return None


def _no_leak(name: str, score: dict) -> None:
    found = _scan_for_leak(score)
    check(f"{name}: no leak", found is None, found or "")


def contract_lint(
    *,
    comprehensive: bool = True,
    leaks: int = 0,
    present: int = 10,
    required: int = 10,
    exam_alerts: int = 2,
    tables: int = 2,
    status: str = "completed",
) -> dict:
    return {
        "version": 1,
        "kind": "guide_quality_contract_lint",
        "status": status,
        "summary": {
            "comprehensive": comprehensive,
            "reasoning_leak_count": leaks,
            "required_section_count": required,
            "required_section_present_count": present,
            "exam_alert_count": exam_alerts,
            "table_count": tables,
            "warning_count": 0,
        },
        "checks": [],
        "warnings": [],
    }


def qa_gate(*, reasoning: str = "passed", source: str = "passed") -> dict:
    return {
        "version": 1,
        "kind": "guide_quality_qa_gate",
        "status": "passed",
        "summary": {"comprehensive": True, "blocking": False},
        "checks": [
            {
                "kind": "reasoning_leak",
                "status": reasoning,
                "observed_count": 0 if reasoning == "passed" else 1,
                "expected_count": 0,
            },
            {
                "kind": "source_coverage",
                "status": source,
                "observed_count": 0,
                "expected_count": 0,
            },
        ],
        "warnings": [],
    }


def quality_report_v2(*, warning_count: int = 0, warnings: list[str] | None = None) -> dict:
    return {
        "version": 2,
        "kind": "guide_quality_report",
        "status": "completed",
        "summary": {"warning_count": warning_count},
        "checks": [],
        "warnings": list(warnings or []),
    }


def coverage_report(
    *,
    status: str = "completed",
    unreadable_pages: int = 0,
    unreadable_sources: int = 0,
    gaps: int = 0,
) -> dict:
    return {
        "version": 1,
        "kind": "source_coverage_report",
        "status": status,
        "summary": {
            "covered_pages": 8,
            "empty_or_unreadable_pages": unreadable_pages,
            "unreadable_source_count": unreadable_sources,
            "source_gap_count": gaps,
        },
        "sources": [],
        "warnings": [],
    }


def math_verification(*, total: int = 3, mismatch: int = 0, status: str = "completed") -> dict:
    return {
        "version": 1,
        "kind": "math_verification",
        "status": status,
        "report": {
            "version": 1,
            "summary": {"total": total, "ok": max(total - mismatch, 0), "mismatch": mismatch},
            "claims": [
                {
                    "id": "claim_0001",
                    "text": CANARY_TEXT,
                    "expression": CANARY_FORMULA,
                    "reason": CANARY_TRACEBACK,
                }
            ],
        },
    }


def visual_plan(*, planned: int = 1, missing: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "visual_inclusion_plan",
        "status": "completed",
        "summary": {"planned_count": planned, "missing_count": missing},
        "items": [{"caption": CANARY_CAPTION, "asset_ref": CANARY_FILENAME}],
    }


def table_manifest(*, candidates: int = 1, unreadable: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "table_candidates_manifest",
        "status": "completed",
        "summary": {"table_like_candidate_count": candidates, "unreadable_count": unreadable},
        "candidates": [{"table_text": CANARY_TABLE, "source_path": CANARY_PATH}],
    }


def table_policy(*, items: int = 1, deferred: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "table_reconstruction_policy",
        "status": "completed",
        "summary": {"policy_item_count": items, "deferred_count": deferred},
        "items": [{"filename": CANARY_FILENAME, "raw_url": CANARY_URL}],
    }


def green_score(**overrides: Any) -> dict:
    kwargs = {
        "qa_gate": qa_gate(),
        "contract_lint": contract_lint(),
        "guide_quality_report_v2": quality_report_v2(),
        "source_coverage_report": coverage_report(),
        "math_verification": math_verification(),
        "visual_inclusion_plan": visual_plan(),
        "table_candidates_manifest": table_manifest(),
        "table_reconstruction_policy": table_policy(),
        "comprehensive": True,
    }
    kwargs.update(overrides)
    return build_guide_quality_rubric_score(**kwargs)


def test_missing_inputs() -> None:
    score = build_guide_quality_rubric_score()
    check("missing kind", score["kind"] == KIND)
    check("missing version", score["version"] == VERSION)
    check("missing skipped", score["status"] == "skipped", score["status"])
    check("missing blocking false", score["blocking"] is False)
    check("missing ten axes", score["summary"]["rubric_axis_count"] == 10)
    check("missing no known axes", score["summary"]["known_axis_count"] == 0)
    check("missing unknown axes", score["summary"]["unknown_axis_count"] == 10)
    _no_leak("missing", score)


def test_all_green() -> None:
    score = green_score()
    check("green completed", score["status"] == "completed")
    check("green blocking false", score["blocking"] is False)
    check("green known axes", score["summary"]["known_axis_count"] == 8)
    check("green score total", score["summary"]["score_total"] == 16)
    check("green score possible", score["summary"]["score_possible"] == 16)
    check("semantic unsupported", axis(score, "beginner_scaffolding")["confidence"] == "unsupported")
    _no_leak("green", score)


def test_reasoning_warning() -> None:
    score = green_score(contract_lint=contract_lint(leaks=2), qa_gate=qa_gate(reasoning="warning"))
    item = axis(score, "reasoning_hygiene")
    check("reasoning warning status", item["status"] == "warning")
    check("reasoning warning score drops", item["score"] == 0)
    check("reasoning warning closed reason", item["reason"] == "reasoning_leak_severe_signal")
    _no_leak("reasoning warning", score)


def test_required_structure_modes() -> None:
    complete = green_score(contract_lint=contract_lint(present=10, required=10))
    partial = green_score(contract_lint=contract_lint(present=6, required=10))
    short = green_score(contract_lint=contract_lint(comprehensive=False), comprehensive=False)
    check("required complete pass", axis(complete, "required_structure")["score"] == 2)
    check("required partial warning", axis(partial, "required_structure")["score"] == 1)
    check("required short n/a", axis(short, "required_structure")["status"] == "not_applicable")


def test_exam_and_table_scoring() -> None:
    score = green_score(contract_lint=contract_lint(exam_alerts=0, tables=0))
    check("exam alert weak", axis(score, "exam_focus")["score"] == 1)
    check("tables weak from table artifacts", axis(score, "reference_tables")["score"] == 1)
    no_table_signal = green_score(
        contract_lint=contract_lint(exam_alerts=2, tables=0),
        table_candidates_manifest=table_manifest(candidates=0),
        table_reconstruction_policy=table_policy(items=0),
    )
    check("tables weak without signal", axis(no_table_signal, "reference_tables")["score"] == 1)


def test_math_modes() -> None:
    clean = green_score(math_verification=math_verification(total=4, mismatch=0))
    mismatch = green_score(math_verification=math_verification(total=4, mismatch=1))
    none_checked = green_score(math_verification=math_verification(total=0, mismatch=0))
    missing = green_score(math_verification=None)
    bad = green_score(math_verification={"status": "completed", "report": {"summary": "bad"}})
    check("math clean", axis(clean, "math_verification")["score"] == 2)
    check("math mismatch", axis(mismatch, "math_verification")["score"] == 0)
    check("math none checked advisory one", axis(none_checked, "math_verification")["score"] == 1)
    check("math missing unknown", axis(missing, "math_verification")["score"] is None)
    check("math malformed safe", axis(bad, "math_verification")["status"] == "unknown")
    _no_leak("math modes", bad)


def test_source_coverage_modes() -> None:
    clean = green_score(source_coverage_report=coverage_report())
    warn = green_score(source_coverage_report=coverage_report(status="partial", unreadable_pages=2, gaps=1))
    fallback = green_score(source_coverage_report=None, qa_gate=qa_gate(source="warning"))
    check("source clean", axis(clean, "source_coverage")["score"] == 2)
    check("source warning", axis(warn, "source_coverage")["score"] == 1)
    check("source fallback", axis(fallback, "source_coverage")["score"] == 1)


def test_report_and_visual_table_modes() -> None:
    report_warn = green_score(guide_quality_report_v2=quality_report_v2(warning_count=3))
    visual_warn = green_score(
        guide_quality_report_v2=quality_report_v2(warnings=["visual_signal_missing"]),
        visual_inclusion_plan=visual_plan(missing=1),
        table_candidates_manifest=table_manifest(unreadable=1),
        table_reconstruction_policy=table_policy(deferred=1),
    )
    visual_missing = green_score(
        visual_inclusion_plan=None,
        table_candidates_manifest=None,
        table_reconstruction_policy=None,
    )
    check("report warning affects alignment", axis(report_warn, "coverage_signal_alignment")["score"] == 1)
    check("visual warnings advisory", axis(visual_warn, "visual_table_honesty")["score"] == 1)
    check("visual missing unknown", axis(visual_missing, "visual_table_honesty")["status"] == "unknown")
    _no_leak("visual warning", visual_warn)


def test_semantic_unknown() -> None:
    score = green_score()
    for kind in ("beginner_scaffolding", "worked_example_completeness"):
        item = axis(score, kind)
        check(f"{kind} unknown", item["status"] == "unknown")
        check(f"{kind} score null", item["score"] is None)
        check(f"{kind} unsupported", item["confidence"] == "unsupported")


def test_malformed_and_max_items() -> None:
    malformed = green_score(contract_lint=["not", "a", "dict"], qa_gate="bad")
    limited = green_score(max_items=3)
    check("malformed closed warning", "malformed_input_degraded" in malformed["warnings"])
    check("malformed no throw axes", malformed["summary"]["rubric_axis_count"] == 10)
    check("max items partial", limited["status"] == "partial")
    check("max items count", limited["summary"]["rubric_axis_count"] == 3)
    check("max items warning", "max_items_reached" in limited["warnings"])
    _no_leak("malformed", malformed)


def test_hostile_canaries() -> None:
    hostile_contract = contract_lint(leaks=1, present=4, required=10, exam_alerts=0, tables=0)
    hostile_contract.update(
        {
            "filename": CANARY_FILENAME,
            "path": CANARY_PATH,
            "title": CANARY_TEXT,
            "warnings": [CANARY_KEY],
            "checks": [{"instruction": CANARY_TEXT, "formula": CANARY_FORMULA}],
        }
    )
    score = green_score(
        qa_gate={
            "status": "passed",
            "summary": {"comprehensive": True, "url": CANARY_URL},
            "checks": [{"kind": "reasoning_leak", "status": "warning", "observed_count": 1}],
            "warnings": [CANARY_TRACEBACK],
        },
        contract_lint=hostile_contract,
        guide_quality_report_v2={
            "status": "completed",
            "summary": {"warning_count": 2, "raw": CANARY_PAYLOAD},
            "warnings": ["table_signal_missing", CANARY_DATA_URI],
        },
        source_coverage_report={
            "status": "partial",
            "summary": {
                "empty_or_unreadable_pages": 1,
                "unreadable_source_count": 1,
                "path": CANARY_PATH,
                "ocr_text": CANARY_OCR,
            },
        },
        math_verification=math_verification(total=2, mismatch=1),
        visual_inclusion_plan=visual_plan(missing=1),
        table_candidates_manifest=table_manifest(unreadable=1),
        table_reconstruction_policy=table_policy(deferred=1),
    )
    serialized = json.dumps(score, sort_keys=True)
    check("hostile no forbidden canary", not any(canary in serialized for canary in FORBIDDEN_CANARIES))
    _no_leak("hostile", score)


def test_deterministic() -> None:
    first = green_score()
    second = green_score()
    check("deterministic repeated calls", first == second)


def test_stdlib_only() -> None:
    import pipeline.guide_quality_rubric_score as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    check("no pipeline import", "from pipeline" not in src and "import pipeline" not in src)
    for forbidden in ("fastapi", "requests", "httpx", "openai", "PIL", "fitz", "pytesseract", "chandra"):
        check(f"no import of {forbidden}", forbidden not in src)


def test_exact_name_route_if_available() -> None:
    try:
        from api import server
        from pipeline.job_manager import Job
    except Exception as exc:
        check(f"[SKIP] server import unavailable ({type(exc).__name__})", True)
        return

    with tempfile.TemporaryDirectory() as tmp:
        job = Job(Path(tmp) / "job-x")
        job.dir.mkdir(parents=True, exist_ok=True)
        check("Job exposes rubric property", job.guide_quality_rubric_score_json.name == "guide_quality_rubric_score.json")
        path, media = server._artifact_path(job, "guide_quality_rubric_score.json")
        check("exact-name path resolves", path == job.guide_quality_rubric_score_json)
        check("exact-name media json", media == "application/json")

    server_src = (REPO / "api" / "server.py").read_text(encoding="utf-8")
    check("not in ARTIFACTS dict", '"guide_quality_rubric_score.json": (' not in server_src)


def main() -> int:
    test_missing_inputs()
    test_all_green()
    test_reasoning_warning()
    test_required_structure_modes()
    test_exam_and_table_scoring()
    test_math_modes()
    test_source_coverage_modes()
    test_report_and_visual_table_modes()
    test_semantic_unknown()
    test_malformed_and_max_items()
    test_hostile_canaries()
    test_deterministic()
    test_stdlib_only()
    test_exact_name_route_if_available()

    print(f"\nGuide quality rubric score tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
