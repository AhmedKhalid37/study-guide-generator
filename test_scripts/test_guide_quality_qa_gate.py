#!/usr/bin/env python3
"""Focused tests for the deterministic guide-quality QA gate v1 (Slice 103).

Run with:

    python test_scripts/test_guide_quality_qa_gate.py

The gate combines the already-sanitized contract lint, guide quality report v2,
source coverage report, and the existing numeric math verification into one advisory
pass/warning/skipped summary. It is FLAG-ONLY (``blocking`` is always ``False``); it
never rejects, regenerates, blocks render/export, or fails a job, and it reruns no
math verification. Critically it copies no string out of its inputs — only known
integer counts and closed tokens — so no excerpt, phrase, heading, formula, value,
table content, caption, OCR text, filename, path, or raw verifier error is ever
persisted, even when hostile canaries are injected. Synthetic dicts only; no
provider/model/cloud call.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
FORBIDDEN_KEY_NAMES = {
    "filename", "path", "title", "text", "ocr_text", "caption", "table_text",
    "image_ref", "asset_ref", "asset_id", "url", "argv", "socket", "bytes",
    "excerpt", "formula", "claims", "claim", "report_error",
}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")

# Hostile canaries embedded in the INPUT artifacts. None may appear in the gate.
CANARY_FILENAME = "private-source.pdf"
CANARY_TITLE = "Quarterly Private Plan"
CANARY_FORMULA = "E=mc^2_private"
CANARY_VALUE = "42.0000001_secret"
CANARY_ERROR = "Traceback (most recent call last): boom at /home/secret/x.py"
CANARY_KEY = "sk_guidequalityqagatecanary1234567890"
FORBIDDEN_CANARIES = [
    CANARY_FILENAME, CANARY_TITLE, CANARY_FORMULA, CANARY_VALUE, CANARY_ERROR, CANARY_KEY,
]

from pipeline.guide_quality_qa_gate import (  # noqa: E402
    GATE_KIND,
    GATE_VERSION,
    MATH_VERIFICATION_ARTIFACT_MISSING,
    MAX_ITEMS_APPLIED,
    build_guide_quality_qa_gate,
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


def _scan_for_leak(node: Any, path: str = "") -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            lower = str(key).lower()
            if lower in SECRET_KEY_NAMES:
                return f"{path}.{key} (secret-like field name)"
            if lower in FORBIDDEN_KEY_NAMES:
                return f"{path}.{key} (forbidden field)"
            found = _scan_for_leak(value, f"{path}.{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found = _scan_for_leak(value, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(node, str):
        for canary in FORBIDDEN_CANARIES:
            if canary in node:
                return f"{path} (canary: {canary!r})"
        for label, pattern in (
            ("keylike", KEYLIKE),
            ("pathlike", PATHLIKE),
            ("urllike", URLLIKE),
            ("data/base64", DATA_OR_BASE64),
            ("argv/socket", ARGV_OR_SOCKET),
        ):
            if pattern.search(node):
                return f"{path} ({label}: {node[:40]!r})"
    return None


def _no_leak(name: str, gate: dict) -> None:
    found = _scan_for_leak(gate)
    check(f"{name}: no leak", found is None, f"leak at {found}")


# =============================================================================
# Synthetic input artifacts (mirroring the real sanitized shapes)
# =============================================================================


def clean_contract_lint(*, comprehensive: bool = True, leaks: int = 0, present: int = 10, total: int = 10) -> dict:
    return {
        "version": 1,
        "kind": "guide_quality_contract_lint",
        "status": "completed",
        "summary": {
            "comprehensive": comprehensive,
            "reasoning_leak_count": leaks,
            "required_section_count": total,
            "required_section_present_count": present,
            "exam_alert_count": 3,
            "table_count": 4,
            "warning_count": 0,
        },
        "checks": [],
        "warnings": [],
    }


def clean_quality_report_v2(*, warnings: int = 0) -> dict:
    return {
        "version": 2,
        "kind": "guide_quality_report",
        "status": "completed",
        "summary": {"warning_count": warnings},
        "checks": [],
        "warnings": [],
    }


def coverage_report(*, status: str = "completed", unreadable_pages: int = 0, unreadable_sources: int = 0) -> dict:
    return {
        "version": 1,
        "kind": "source_coverage_report",
        "status": status,
        "summary": {
            "source_count": 1,
            "total_pages": 10,
            "covered_pages": 10 - unreadable_pages,
            "empty_or_unreadable_pages": unreadable_pages,
            "unreadable_source_count": unreadable_sources,
        },
        "sources": [],
        "warnings": [],
    }


def math_verification(*, total: int = 5, ok: int = 5, mismatch: int = 0, unparseable: int = 0, status: str = "completed") -> dict:
    # Inner report carries canary-laden claims to prove the gate copies no string.
    return {
        "version": 1,
        "kind": "math_verification",
        "status": status,
        "source": "clean.md",
        "report": {
            "version": 1,
            "source_name": "clean.md",
            "summary": {"total": total, "ok": ok, "mismatch": mismatch, "unparseable": unparseable},
            "claims": [
                {"id": "claim_0001", "status": "mismatch", "expression": CANARY_FORMULA, "reason": CANARY_VALUE}
            ],
        },
    }


def hostile_inputs() -> dict:
    """Inputs riddled with canaries in every string-bearing position."""
    return {
        "guide_quality_contract_lint": {
            "kind": "guide_quality_contract_lint",
            "status": "completed",
            "title": CANARY_TITLE,
            "filename": CANARY_FILENAME,
            "summary": {
                "comprehensive": True,
                "reasoning_leak_count": 2,
                "required_section_count": 10,
                "required_section_present_count": 6,
                "warning_count": 3,
                "note": CANARY_ERROR,
            },
            "checks": [{"instruction": CANARY_FORMULA, "excerpt": CANARY_VALUE}],
            "warnings": [CANARY_KEY],
        },
        "guide_quality_report_v2": {
            "kind": "guide_quality_report",
            "status": "completed",
            "summary": {"warning_count": 4, "raw": CANARY_FORMULA},
        },
        "source_coverage_report": {
            "kind": "source_coverage_report",
            "status": "partial",
            "summary": {"empty_or_unreadable_pages": 3, "path": CANARY_FILENAME},
        },
        "math_verification": math_verification(total=4, ok=2, mismatch=2),
        "comprehensive": True,
    }


# =============================================================================
# Tests
# =============================================================================


def test_constants() -> None:
    check("GATE_VERSION is 1", GATE_VERSION == 1)
    check("GATE_KIND token", GATE_KIND == "guide_quality_qa_gate")


def test_all_missing_is_safe() -> None:
    gate = build_guide_quality_qa_gate()
    check("all-missing kind", gate["kind"] == GATE_KIND)
    check("all-missing status skipped/partial", gate["status"] in {"skipped", "partial"})
    check("all-missing blocking False", gate["summary"]["blocking"] is False)
    check("all-missing no passed checks", gate["summary"]["passed_count"] == 0)
    check("all-missing no warning checks", gate["summary"]["warning_count"] == 0)
    check("all-missing math-missing warning", MATH_VERIFICATION_ARTIFACT_MISSING in gate["warnings"])
    _no_leak("all-missing", gate)


def test_clean_inputs_pass() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        guide_quality_report_v2=clean_quality_report_v2(),
        source_coverage_report=coverage_report(),
        math_verification=math_verification(),
        comprehensive=True,
    )
    check("clean → passed", gate["status"] == "passed", gate["status"])
    check("clean blocking False", gate["summary"]["blocking"] is False)
    check("clean warning_count 0", gate["summary"]["warning_count"] == 0)
    check("clean has checks", gate["summary"]["check_count"] == 5)
    _no_leak("clean", gate)


def test_clean_lint_and_report_only_pass() -> None:
    # Math + coverage absent, but contract lint + quality report clean → still passed.
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        guide_quality_report_v2=clean_quality_report_v2(),
        comprehensive=True,
    )
    check("lint+report only → passed", gate["status"] == "passed", gate["status"])
    check("lint+report blocking False", gate["summary"]["blocking"] is False)
    _no_leak("lint+report only", gate)


def test_reasoning_leak_warns() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(leaks=3),
        guide_quality_report_v2=clean_quality_report_v2(),
        math_verification=math_verification(),
        comprehensive=True,
    )
    check("reasoning leak → warning", gate["status"] == "warning")
    leak_check = next(c for c in gate["checks"] if c["kind"] == "reasoning_leak")
    check("leak check warning", leak_check["status"] == "warning")
    check("leak check observed=3", leak_check["observed_count"] == 3)
    check("reasoning_leak_present warning", "reasoning_leak_present" in gate["warnings"])
    check("blocking still False", gate["summary"]["blocking"] is False)
    _no_leak("reasoning leak", gate)


def test_missing_required_sections_warns() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(present=6, total=10),
        comprehensive=True,
    )
    check("missing sections → warning", gate["status"] == "warning")
    struct = next(c for c in gate["checks"] if c["kind"] == "required_structure")
    check("structure warning", struct["status"] == "warning")
    check("structure observed/expected", struct["observed_count"] == 6 and struct["expected_count"] == 10)
    check("required_sections_missing warning", "required_sections_missing" in gate["warnings"])
    _no_leak("missing sections", gate)


def test_required_structure_not_applicable_when_short() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(comprehensive=False, present=0, total=0),
        comprehensive=False,
    )
    struct = next(c for c in gate["checks"] if c["kind"] == "required_structure")
    check("structure n/a for short guide", struct["status"] == "not_applicable")
    check("short guide summary comprehensive False", gate["summary"]["comprehensive"] is False)
    _no_leak("short guide structure", gate)


def test_math_clean_passes() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        math_verification=math_verification(total=5, ok=5, mismatch=0),
        comprehensive=True,
    )
    math_check = next(c for c in gate["checks"] if c["kind"] == "math_verification")
    check("math clean → passed", math_check["status"] == "passed")
    check("math observed mismatch 0", math_check["observed_count"] == 0)
    _no_leak("math clean", gate)


def test_math_mismatch_warns() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        math_verification=math_verification(total=5, ok=3, mismatch=2),
        comprehensive=True,
    )
    check("math mismatch → gate warning", gate["status"] == "warning")
    math_check = next(c for c in gate["checks"] if c["kind"] == "math_verification")
    check("math check warning", math_check["status"] == "warning")
    check("math observed mismatch 2", math_check["observed_count"] == 2)
    check("math mismatch warning token", "math_verification_mismatch_present" in gate["warnings"])
    _no_leak("math mismatch", gate)


def test_math_no_claims_not_applicable() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        math_verification=math_verification(total=0, ok=0, mismatch=0),
        comprehensive=True,
    )
    math_check = next(c for c in gate["checks"] if c["kind"] == "math_verification")
    check("math no claims → not_applicable", math_check["status"] == "not_applicable")
    _no_leak("math no claims", gate)


def test_math_skipped_artifact_unknown() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        math_verification={"kind": "math_verification", "status": "skipped", "reason": "verifier_error"},
        comprehensive=True,
    )
    math_check = next(c for c in gate["checks"] if c["kind"] == "math_verification")
    check("math skipped → unknown", math_check["status"] == "unknown")
    check("math missing warning present", MATH_VERIFICATION_ARTIFACT_MISSING in gate["warnings"])
    _no_leak("math skipped", gate)


def test_math_missing_artifact_unknown() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        comprehensive=True,
    )
    math_check = next(c for c in gate["checks"] if c["kind"] == "math_verification")
    check("math missing → unknown/not_applicable", math_check["status"] in {"unknown", "not_applicable"})
    check("math missing warning token", MATH_VERIFICATION_ARTIFACT_MISSING in gate["warnings"])
    _no_leak("math missing", gate)


def test_math_validation_fallback_warns() -> None:
    # No numeric verification, but KaTeX validation explicitly failed → warning.
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        math_validation={"ok": False, "summary": {"error_count": 2}},
        comprehensive=True,
    )
    math_check = next(c for c in gate["checks"] if c["kind"] == "math_verification")
    check("math fallback warning", math_check["status"] == "warning")
    check("math fallback still flags missing-artifact", MATH_VERIFICATION_ARTIFACT_MISSING in gate["warnings"])
    _no_leak("math fallback", gate)


def test_source_coverage_unreadable_warns() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        source_coverage_report=coverage_report(status="partial", unreadable_pages=3),
        comprehensive=True,
    )
    check("coverage unreadable → warning", gate["status"] == "warning")
    cov = next(c for c in gate["checks"] if c["kind"] == "source_coverage")
    check("coverage check warning", cov["status"] == "warning")
    check("coverage observed pages 3", cov["observed_count"] == 3)
    check("source_coverage_incomplete warning", "source_coverage_incomplete" in gate["warnings"])
    _no_leak("coverage unreadable", gate)


def test_source_coverage_complete_passes() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        source_coverage_report=coverage_report(status="completed", unreadable_pages=0),
        comprehensive=True,
    )
    cov = next(c for c in gate["checks"] if c["kind"] == "source_coverage")
    check("coverage complete → passed", cov["status"] == "passed")
    _no_leak("coverage complete", gate)


def test_quality_report_v2_warning_count_warns() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        guide_quality_report_v2=clean_quality_report_v2(warnings=2),
        comprehensive=True,
    )
    check("v2 warnings → gate warning", gate["status"] == "warning")
    v2 = next(c for c in gate["checks"] if c["kind"] == "quality_report_v2")
    check("v2 check warning", v2["status"] == "warning")
    check("v2 observed 2", v2["observed_count"] == 2)
    check("quality_report_warnings_present token", "quality_report_warnings_present" in gate["warnings"])
    _no_leak("v2 warnings", gate)


def test_blocking_always_false() -> None:
    scenarios = [
        build_guide_quality_qa_gate(),
        build_guide_quality_qa_gate(guide_quality_contract_lint=clean_contract_lint(), math_verification=math_verification(mismatch=5, ok=0, total=5), comprehensive=True),
        build_guide_quality_qa_gate(**hostile_inputs()),
    ]
    for index, gate in enumerate(scenarios):
        check(f"blocking False [{index}]", gate["summary"]["blocking"] is False)


def test_hostile_canaries_stripped() -> None:
    gate = build_guide_quality_qa_gate(**hostile_inputs())
    _no_leak("hostile inputs", gate)
    flat = json.dumps(gate)
    for canary in FORBIDDEN_CANARIES:
        check(f"hostile drops {canary[:18]!r}", canary not in flat)
    # The gate still produces real signal from the hostile (but structured) inputs.
    check("hostile → warning", gate["status"] == "warning")
    check("hostile blocking False", gate["summary"]["blocking"] is False)


def test_malformed_inputs_degrade() -> None:
    for bad in (object(), 12.5, b"bytes", [1, 2, 3], "string", None):
        gate = build_guide_quality_qa_gate(
            guide_quality_contract_lint=bad,
            guide_quality_report_v2=bad,
            source_coverage_report=bad,
            math_verification=bad,
            math_validation=bad,
            comprehensive=True,
        )
        check(f"malformed {type(bad).__name__} → dict", isinstance(gate, dict))
        check(f"malformed {type(bad).__name__} status valid", gate["status"] in {"passed", "warning", "skipped", "partial"})
        check(f"malformed {type(bad).__name__} blocking False", gate["summary"]["blocking"] is False)
        _no_leak(f"malformed {type(bad).__name__}", gate)


def test_determinism() -> None:
    args = hostile_inputs()
    first = json.dumps(build_guide_quality_qa_gate(**args), sort_keys=True)
    second = json.dumps(build_guide_quality_qa_gate(**args), sort_keys=True)
    check("deterministic repeated calls", first == second)


def test_max_items_cap() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        guide_quality_report_v2=clean_quality_report_v2(),
        source_coverage_report=coverage_report(),
        math_verification=math_verification(),
        comprehensive=True,
        max_items=2,
    )
    check("max_items truncates checks", gate["summary"]["check_count"] == 2)
    check("max_items applied warning", MAX_ITEMS_APPLIED in gate["warnings"])
    check("max_items status partial/warning", gate["status"] in {"partial", "warning"})
    # max_items=0 → no checks → skipped, still safe.
    zero = build_guide_quality_qa_gate(guide_quality_contract_lint=clean_contract_lint(), max_items=0)
    check("max_items=0 no checks", zero["summary"]["check_count"] == 0)
    check("max_items=0 skipped", zero["status"] == "skipped")
    _no_leak("max_items", gate)


def test_check_id_and_kind_shape() -> None:
    gate = build_guide_quality_qa_gate(
        guide_quality_contract_lint=clean_contract_lint(),
        guide_quality_report_v2=clean_quality_report_v2(),
        source_coverage_report=coverage_report(),
        math_verification=math_verification(),
        comprehensive=True,
    )
    valid_kinds = {"reasoning_leak", "required_structure", "math_verification", "source_coverage", "quality_report_v2"}
    valid_status = {"passed", "warning", "unknown", "not_applicable"}
    for index, c in enumerate(gate["checks"], start=1):
        check(f"check_id {index} positional", c["check_id"] == f"guide_quality_gate_check_{index:04d}")
        check(f"check {index} kind closed", c["kind"] in valid_kinds)
        check(f"check {index} status closed", c["status"] in valid_status)
        check(f"check {index} observed int", isinstance(c["observed_count"], int))
        check(f"check {index} expected int", isinstance(c["expected_count"], int))
        check(f"check {index} warnings list", isinstance(c["warnings"], list))


def test_module_is_stdlib_only() -> None:
    # Inspect actual import statements only — descriptive prose in the safety
    # docstring legitimately mentions render/OCR/socket/frontend as things the
    # module does NOT do, so a raw substring scan would false-positive.
    source = (REPO / "pipeline" / "guide_quality_qa_gate.py").read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    banned = [
        "pipeline", "fastapi", "requests", "httpx", "openai", "anthropic",
        "render", "ocr", "tesseract", "chromium", "subprocess", "socket",
        "torch", "llama", "frontend", "provider", "model",
    ]
    for line in import_lines:
        for token in banned:
            check(f"import '{line}' avoids '{token}'", token not in line.lower())
    # Only stdlib imports expected (typing / __future__).
    check("only stdlib imports", set(import_lines) <= {"from __future__ import annotations", "from typing import Any"}, str(import_lines))


def test_writer_uses_save_text() -> None:
    source = (REPO / "pipeline" / "run_markdown_job.py").read_text(encoding="utf-8")
    check("writer present", "_write_guide_quality_qa_gate" in source)
    check("writer uses job.save_text", "job.save_text(artifact_path" in source)
    # Build/write happens after the contract lint + math verification.
    gate_pos = source.index("_write_guide_quality_qa_gate(job)")
    lint_pos = source.index("_write_guide_quality_contract_lint(job)")
    math_pos = source.index("_write_math_verification(job)")
    check("gate written after contract lint", gate_pos > lint_pos)
    check("gate written after math verification", gate_pos > math_pos)


def test_not_in_generic_lists() -> None:
    server = (REPO / "api" / "server.py").read_text(encoding="utf-8")
    # Exact-name route exists.
    check("exact-name route present", 'artifact_name == "guide_quality_qa_gate.json"' in server)
    # Not registered in the generic ARTIFACTS dict (which maps by quoted filename:tuple).
    check("not in ARTIFACTS dict", '"guide_quality_qa_gate.json": (' not in server)


def test_exact_name_path_if_server_available() -> None:
    try:
        from pipeline.job_manager import Job  # noqa: F401
    except Exception as exc:
        check("[SKIP] Job import unavailable", True, f"{type(exc).__name__}")
        return
    try:
        from api import server  # noqa: F401
    except Exception as exc:
        check("[SKIP] server import unavailable", True, f"{type(exc).__name__}")
        return
    import tempfile
    from pipeline.job_manager import Job

    with tempfile.TemporaryDirectory() as tmp:
        job = Job(Path(tmp) / "job-x")
        job.dir.mkdir(parents=True, exist_ok=True)
        check("Job exposes qa-gate property", job.guide_quality_qa_gate_json.name == "guide_quality_qa_gate.json")
        path, media = server._artifact_path(job, "guide_quality_qa_gate.json")
        check("exact-name path resolves", path == job.guide_quality_qa_gate_json)
        check("exact-name media json", media == "application/json")


def main() -> int:
    test_constants()
    test_all_missing_is_safe()
    test_clean_inputs_pass()
    test_clean_lint_and_report_only_pass()
    test_reasoning_leak_warns()
    test_missing_required_sections_warns()
    test_required_structure_not_applicable_when_short()
    test_math_clean_passes()
    test_math_mismatch_warns()
    test_math_no_claims_not_applicable()
    test_math_skipped_artifact_unknown()
    test_math_missing_artifact_unknown()
    test_math_validation_fallback_warns()
    test_source_coverage_unreadable_warns()
    test_source_coverage_complete_passes()
    test_quality_report_v2_warning_count_warns()
    test_blocking_always_false()
    test_hostile_canaries_stripped()
    test_malformed_inputs_degrade()
    test_determinism()
    test_max_items_cap()
    test_check_id_and_kind_shape()
    test_module_is_stdlib_only()
    test_writer_uses_save_text()
    test_not_in_generic_lists()
    test_exact_name_path_if_server_available()
    print(f"\nGuide quality QA gate tests: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
