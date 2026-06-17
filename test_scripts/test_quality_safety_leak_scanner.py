#!/usr/bin/env python3
"""Tests for Slice 113 Quality Safety verifier-coupled leak scanner v1.

Synthetic-only. These tests do not use real source decks, references, generated
guides, OCR/table/caption text, uploaded quality specs, provider payloads, paths,
URLs, images, PDFs, DOCX files, ZIPs, or runtime artifacts. Hostile strings below
are fake canaries used only to prove they are not echoed.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.quality_safety_canonical_matcher import match_quality_safety_canonical_facts  # noqa: E402
from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet  # noqa: E402
from pipeline.quality_safety_leak_scanner import (  # noqa: E402
    build_quality_safety_leak_report,
    extract_quality_safety_verification_context,
    scan_quality_safety_leaks,
)
from pipeline.quality_safety_recompute_verifier import verify_quality_safety_fact_sheet  # noqa: E402

PASS = 0
FAIL = 0

HOSTILE_CANARIES = (
    "/home/fake_private/source-deck.pdf",
    "C:\\fake_private\\uploaded-source.docx",
    "https://private.invalid/source",
    "Authorization: Bearer sk_leakscanner1234567890",
    "data:image/png;base64," + ("A" * 120),
    "OCR_PRIVATE_LEAK_MARKER",
    "TABLE_TEXT_PRIVATE_LEAK_MARKER",
    "CAPTION_PRIVATE_LEAK_MARKER",
    "PROVIDER_PAYLOAD_PRIVATE_LEAK_MARKER",
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
    "sk_leakscanner",
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
)
FORBIDDEN_IMPORT_PARTS = (
    "fastapi",
    "frontend",
    "provider",
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
ALLOWED_IMPORTS = {"__future__", "re", "typing", "pipeline.quality_safety_fact_sheet"}
REPORT_STATUSES = {"passed", "warning", "failed", "skipped", "partial"}
LEAK_KINDS = {
    "reasoning_leak",
    "uncertainty_leak",
    "unresolved_answer",
    "placeholder_leak",
    "numeric_uncertainty",
    "structural_uncertainty",
}
SEVERITIES = {"blocking", "warning", "info"}
VERIFICATION_STATUSES = {
    "verified_recompute",
    "failed_recompute",
    "verified_canonical",
    "failed_canonical",
    "unverified",
    "not_applicable",
    "unknown",
}
WARNING_TOKENS = {
    "candidate_markdown_missing",
    "malformed_candidate_degraded",
    "malformed_fact_sheet_degraded",
    "malformed_recompute_report_degraded",
    "malformed_canonical_report_degraded",
    "verification_context_missing",
    "unsafe_fact_token_dropped",
    "max_items_reached",
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


def assert_no_raw_phrases(name: str, report: dict[str, Any], phrases: tuple[str, ...]) -> None:
    blob = serialized(report)
    found = [phrase for phrase in phrases if phrase in blob]
    check(f"{name}: no raw phrases", not found, str(found))


def assert_report_shape(name: str, report: dict[str, Any]) -> None:
    check(f"{name}: kind", report.get("kind") == "quality_safety_leak_report")
    check(f"{name}: version", report.get("version") == 1)
    check(f"{name}: status closed", report.get("status") in REPORT_STATUSES, str(report.get("status")))
    summary = report.get("summary", {})
    expected = {
        "line_count",
        "leak_count",
        "blocking_leak_count",
        "warning_leak_count",
        "info_leak_count",
        "verified_recompute_leak_count",
        "failed_recompute_leak_count",
        "verified_canonical_leak_count",
        "failed_canonical_leak_count",
        "unverified_leak_count",
        "unknown_context_leak_count",
        "warning_count",
    }
    check(f"{name}: summary keys", set(summary) == expected, str(summary))
    check(
        f"{name}: summary non-negative ints",
        all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()),
        str(summary),
    )
    check(
        f"{name}: warnings closed",
        all(token in WARNING_TOKENS for token in report.get("warnings", [])),
        str(report.get("warnings")),
    )
    for leak in report.get("leaks", []):
        check(f"{name}: leak kind closed", leak.get("leak_kind") in LEAK_KINDS, str(leak))
        check(f"{name}: severity closed", leak.get("severity") in SEVERITIES, str(leak))
        check(f"{name}: verification status closed", leak.get("verification_status") in VERIFICATION_STATUSES, str(leak))
        check(f"{name}: no line text field", "line_text" not in leak and "matched_text" not in leak, str(leak))
    for failure in report.get("blocking_failures", []):
        check(f"{name}: blocking check id closed", failure.get("check_id") == "quality_safety_leak_scan", str(failure))
        check(f"{name}: blocking severity", failure.get("severity") == "blocking", str(failure))


def numeric_fact(
    *,
    fact_id: str,
    label: str,
    value: Any = 0.2,
    computation: Any = None,
    provenance: str = "unverified",
    verification_status: str = "unverified",
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "concept": "Synthetic Concept",
        "label": label,
        "value": value,
        "type": "numeric",
        "provenance": provenance,
        "verification_status": verification_status,
        "confidence": "low",
        "source_ref": "source_page_1",
        "computation": computation,
    }


def sheet_of(*facts: dict[str, Any], lecture_id: str = "synthetic_fixture") -> dict[str, Any]:
    return {
        "lecture_id": lecture_id,
        "source_quality": "synthetic",
        "concepts": [{"concept": "Synthetic Concept", "facts": list(facts)}],
    }


def canonical_for(*, lecture_id: str = "synthetic_fixture", label: str, value: float = 0.2) -> dict[str, Any]:
    return {
        "version": 1,
        "kind": "quality_safety_canonical_fixture",
        "lecture_id": lecture_id,
        "source_quality": "synthetic",
        "facts": [{"id": f"synthetic.canonical.{label}", "label": label, "value": value, "tol": 0.01, "type": "numeric"}],
    }


def leak_statuses(report: dict[str, Any]) -> list[str]:
    return [leak.get("verification_status") for leak in report.get("leaks", [])]


def test_empty_and_malformed() -> None:
    missing = build_quality_safety_leak_report(None)
    check("missing candidate skipped", missing["status"] == "skipped")
    check("missing candidate warning", "candidate_markdown_missing" in missing["warnings"])
    assert_report_shape("missing candidate", missing)

    malformed = build_quality_safety_leak_report({"bad": "candidate"})
    check("non-string candidate skipped", malformed["status"] == "skipped")
    check("non-string candidate warning", "malformed_candidate_degraded" in malformed["warnings"])
    assert_report_shape("malformed candidate", malformed)

    degraded = build_quality_safety_leak_report(
        "Clean committed sentence.",
        fact_sheet=["bad"],
        recompute_report=["bad"],
        canonical_report=["bad"],
    )
    check("malformed reports degrade", degraded["status"] in {"passed", "warning"})
    check("malformed fact sheet warning", "malformed_fact_sheet_degraded" in degraded["warnings"])
    check("malformed recompute warning", "malformed_recompute_report_degraded" in degraded["warnings"])
    check("malformed canonical warning", "malformed_canonical_report_degraded" in degraded["warnings"])
    assert_report_shape("malformed reports", degraded)

    for bad in (None, 1, 1.5, [], {}, object()):
        report = build_quality_safety_leak_report(bad)
        check(f"never raises for {type(bad).__name__}", report.get("status") in REPORT_STATUSES)


def test_leak_signatures() -> None:
    candidate = """
Wait, compare synthetic_fact carefully.
Actually, the next step is unclear and we'll trust the value.
I think presumably maybe this is not sure.
Synthetic total: = ?
Synthetic approximation: ≈ ?
TODO finish this.
TBD later.
FIXME later.
[insert synthetic step]
[unknown synthetic value]
Final answer:
"""
    report = build_quality_safety_leak_report(candidate)
    kinds = {leak["leak_kind"] for leak in report["leaks"]}
    rules = {leak["rule_id"] for leak in report["leaks"]}
    check("reasoning leak detected", "reasoning_leak" in kinds)
    check("uncertainty leak detected", "uncertainty_leak" in kinds)
    check("numeric uncertainty detected", "numeric_uncertainty" in kinds)
    check("todo placeholder detected", "todo_marker" in rules)
    check("bracket placeholder detected", "placeholder_bracket" in rules)
    check("empty final answer detected", "empty_answer_marker" in rules)
    check("blocking leaks fail", report["status"] == "failed")
    assert_report_shape("leak signatures", report)
    assert_no_raw_phrases("leak signatures", report, ("Actually,", "we'll trust", "I think", "presumably maybe", "[insert synthetic step]"))


def test_false_positive_resistance() -> None:
    candidate = """
## Question 1?
Committed prompt text follows.
## Practice Question?
Committed prompt text follows.
## Mock Question?
Committed prompt text follows.
## Self-test?
Committed prompt text follows.
## Quiz?
Committed prompt text follows.
## Check yourself?
Committed prompt text follows.
## Why?
The committed explanation defines the next step.
## Assumption
Synthetic variable is held constant.
Source: page 12?
"""
    report = build_quality_safety_leak_report(candidate)
    check("safe headings pass", report["status"] == "passed", serialized(report))
    check("no structural question leaks", not report["leaks"], serialized(report))
    assert_report_shape("false positive headings", report)

    unsafe_assumption = build_quality_safety_leak_report("## Assumption\nWe assume synthetic_label is correct.")
    check("assumption with uncertainty language flags", unsafe_assumption["status"] in {"warning", "failed"})
    check("unsafe assumption rule", any(leak["rule_id"] == "unsafe_assumption" for leak in unsafe_assumption["leaks"]))


def test_verifier_coupling() -> None:
    verified_fact = numeric_fact(
        fact_id="synthetic.verified",
        label="synthetic_verified",
        value=0.125,
        computation={"method": "total_error", "inputs": {"misclassified_weight": 0.125}, "result": 0.125},
        provenance="computed",
        verification_status="verified",
    )
    failed_fact = dict(verified_fact, id="synthetic.failed", label="synthetic_failed", value=0.9)
    recomputed = verify_quality_safety_fact_sheet(normalize_quality_safety_fact_sheet(sheet_of(verified_fact, failed_fact)))
    candidate = "synthetic.verified maybe.\nsynthetic.failed maybe."
    report = build_quality_safety_leak_report(candidate, fact_sheet=recomputed["fact_sheet"], recompute_report=recomputed["report"])
    check("recompute verified attached", "verified_recompute" in leak_statuses(report), leak_statuses(report))
    check("recompute failed attached", "failed_recompute" in leak_statuses(report), leak_statuses(report))
    check("recompute contexts block uncertainty", report["summary"]["blocking_leak_count"] == 2, serialized(report))

    canonical_match_sheet = sheet_of(numeric_fact(fact_id="synthetic.canon.pass", label="synthetic_canon_pass", value=0.2))
    canonical_match = match_quality_safety_canonical_facts(
        canonical_match_sheet,
        canonical_for(label="synthetic_canon_pass", value=0.2),
    )
    canonical_pass_report = build_quality_safety_leak_report(
        "synthetic_canon_pass maybe.",
        fact_sheet=canonical_match["fact_sheet"],
        canonical_report=canonical_match["report"],
    )
    check("canonical verified fallback attached", "verified_canonical" in leak_statuses(canonical_pass_report), leak_statuses(canonical_pass_report))

    canonical_fail_sheet = sheet_of(numeric_fact(fact_id="synthetic.canon.fail", label="synthetic_canon_fail", value=0.9))
    canonical_fail = match_quality_safety_canonical_facts(
        canonical_fail_sheet,
        canonical_for(label="synthetic_canon_fail", value=0.2),
    )
    canonical_fail_report = build_quality_safety_leak_report(
        "synthetic_canon_fail maybe.",
        fact_sheet=canonical_fail_sheet,
        canonical_report=canonical_fail["report"],
    )
    check("canonical mismatch fallback attached", "failed_canonical" in leak_statuses(canonical_fail_report), leak_statuses(canonical_fail_report))

    unknown = build_quality_safety_leak_report(
        "synthetic_unknown maybe.",
        fact_sheet=sheet_of(numeric_fact(fact_id="synthetic.unknown", label="synthetic_unknown")),
    )
    check("missing reports unknown", "unknown" in leak_statuses(unknown), leak_statuses(unknown))

    priority_canonical = match_quality_safety_canonical_facts(
        sheet_of(numeric_fact(fact_id="synthetic.priority", label="synthetic_priority", value=0.2)),
        canonical_for(label="synthetic_priority", value=0.2),
    )
    priority_recompute = verify_quality_safety_fact_sheet(
        normalize_quality_safety_fact_sheet(
            sheet_of(
                numeric_fact(
                    fact_id="synthetic.priority",
                    label="synthetic_priority",
                    value=0.125,
                    computation={"method": "total_error", "inputs": {"misclassified_weight": 0.125}, "result": 0.125},
                    provenance="computed",
                    verification_status="verified",
                )
            )
        )
    )
    priority = build_quality_safety_leak_report(
        "synthetic.priority maybe.",
        fact_sheet=priority_recompute["fact_sheet"],
        recompute_report=priority_recompute["report"],
        canonical_report=priority_canonical["report"],
    )
    check("recompute priority over canonical", leak_statuses(priority) == ["verified_recompute"], leak_statuses(priority))


def test_conservative_attachment() -> None:
    sheet = sheet_of(
        numeric_fact(fact_id="synthetic.safe.id", label="synthetic_safe_label", value=0.2),
        numeric_fact(fact_id="synthetic.other.id", label=HOSTILE_CANARIES[5], value=0.2),
    )
    by_id = build_quality_safety_leak_report("synthetic.safe.id maybe.", fact_sheet=sheet, canonical_report={"checks": []})
    check("safe fact id attaches", by_id["leaks"][0]["fact_ids"] == ["synthetic.safe.id"], serialized(by_id))

    by_label = build_quality_safety_leak_report("synthetic_safe_label maybe.", fact_sheet=sheet, canonical_report={"checks": []})
    check("safe label attaches", by_label["leaks"][0]["fact_ids"] == ["synthetic.safe.id"], serialized(by_label))

    no_token = build_quality_safety_leak_report("unrelated maybe.", fact_sheet=sheet, canonical_report={"checks": []})
    check("no token remains unknown", no_token["leaks"][0]["fact_ids"] == [], serialized(no_token))
    check("no token status unknown", no_token["leaks"][0]["verification_status"] == "unknown")

    unsafe = build_quality_safety_leak_report(f"{HOSTILE_CANARIES[5]} maybe.", fact_sheet=sheet, canonical_report={"checks": []})
    check("unsafe label not attached", unsafe["leaks"][0]["fact_ids"] == [], serialized(unsafe))
    check("unsafe token warning", "unsafe_fact_token_dropped" in unsafe["warnings"])
    assert_no_canary("unsafe attachment", unsafe)


def test_report_shape_and_status() -> None:
    clean = build_quality_safety_leak_report("Committed synthetic explanation.")
    check("clean passed", clean["status"] == "passed")
    check("clean no blocking", clean["blocking"] is False)
    assert_report_shape("clean report", clean)

    warning = build_quality_safety_leak_report("Maybe this sentence is advisory only.")
    check("warning-only status", warning["status"] == "warning", serialized(warning))
    check("warning count increments", warning["summary"]["warning_leak_count"] == 1)

    failed = build_quality_safety_leak_report("Wait before committing the answer.")
    check("blocking status failed", failed["status"] == "failed")
    check("blocking count increments", failed["summary"]["blocking_leak_count"] == 1)
    check("blocking failures populated", len(failed["blocking_failures"]) == 1)

    capped = build_quality_safety_leak_report("Maybe one.\nMaybe two.\nMaybe three.", max_items=2)
    check("max_items caps leaks", len(capped["leaks"]) == 2, serialized(capped))
    check("max_items warning", "max_items_reached" in capped["warnings"])
    check("max_items partial when warning-only", capped["status"] == "partial", serialized(capped))
    assert_report_shape("capped report", capped)


def test_slice110_111_112_integration() -> None:
    raw_sheet = sheet_of(
        numeric_fact(
            fact_id="synthetic.recomputed",
            label="synthetic_recomputed",
            value=0.125,
            computation={"method": "total_error", "inputs": {"misclassified_weight": 0.125}, "result": 0.125},
            provenance="computed",
            verification_status="verified",
        ),
        numeric_fact(fact_id="synthetic.fallback", label="synthetic_fallback", value=0.2),
    )
    normalized = normalize_quality_safety_fact_sheet(raw_sheet)
    recomputed = verify_quality_safety_fact_sheet(normalized)
    canonical = match_quality_safety_canonical_facts(
        recomputed["fact_sheet"],
        {
            "version": 1,
            "kind": "quality_safety_canonical_fixture",
            "lecture_id": "synthetic_fixture",
            "source_quality": "synthetic",
            "facts": [
                {"id": "synthetic.recomputed", "label": "synthetic_recomputed", "value": 0.9, "tol": 0.01},
                {"id": "synthetic.fallback", "label": "synthetic_fallback", "value": 0.2, "tol": 0.01},
            ],
        },
        recompute_report=recomputed["report"],
    )
    report = build_quality_safety_leak_report(
        "synthetic_recomputed maybe.\nsynthetic_fallback maybe.",
        fact_sheet=canonical["fact_sheet"],
        recompute_report=recomputed["report"],
        canonical_report=canonical["report"],
    )
    check("integration recompute-first verified", report["leaks"][0]["verification_status"] == "verified_recompute", serialized(report))
    check("integration canonical fallback second", report["leaks"][1]["verification_status"] == "verified_canonical", serialized(report))

    context = extract_quality_safety_verification_context(
        canonical["fact_sheet"],
        recompute_report=recomputed["report"],
        canonical_report=canonical["report"],
    )
    check("context kind", context["kind"] == "quality_safety_verification_context")
    check("context statuses closed", all(item["verification_status"] in VERIFICATION_STATUSES for item in context["facts"]))
    assert_no_canary("integration context", context)


def test_seed_fixture_integration() -> None:
    fixture_dir = REPO / "test_scripts" / "fixtures" / "quality_safety"
    clean_seed = json.loads((fixture_dir / "clean_neural_networks_synthetic.json").read_text(encoding="utf-8"))
    label = clean_seed["ground_truth_numerics"][0]["label"]
    value = clean_seed["ground_truth_numerics"][0]["value"]
    clean_candidate = f"{label} is recorded as a committed synthetic value."
    leaked_candidate = f"{label} maybe = ?"
    sheet = sheet_of(numeric_fact(fact_id=f"synthetic.seed.{label}", label=label, value=value), lecture_id=clean_seed["lecture_id"])
    clean_report = build_quality_safety_leak_report(clean_candidate, fact_sheet=sheet)
    leaked_report = build_quality_safety_leak_report(leaked_candidate, fact_sheet=sheet)
    check("clean synthetic seed candidate passes", clean_report["status"] == "passed", serialized(clean_report))
    check("leaked synthetic seed candidate fails", leaked_report["status"] == "failed", serialized(leaked_report))
    assert_no_canary("seed clean", clean_report)
    assert_no_canary("seed leaked", leaked_report)


def test_no_leak_sweep() -> None:
    hostile_candidate = "\n".join(HOSTILE_CANARIES + ("wait", "synthetic_hostile maybe"))
    hostile_sheet = sheet_of(
        numeric_fact(fact_id=HOSTILE_CANARIES[2], label=HOSTILE_CANARIES[5], value=0.2),
        numeric_fact(fact_id="synthetic.safe.hostile", label="synthetic_hostile", value=0.2),
    )
    hostile_recompute = {
        "checks": [
            {"fact_id": HOSTILE_CANARIES[3], "check_id": "total_error", "status": "failed"},
            {"fact_id": "synthetic.safe.hostile", "check_id": "total_error", "status": "warning"},
        ]
    }
    hostile_canonical = {
        "checks": [
            {"fact_id": HOSTILE_CANARIES[4], "check_id": "canonical_fixture_mismatch", "status": "failed"},
            {"fact_id": "synthetic.safe.hostile", "check_id": "canonical_fixture_match", "status": "passed"},
        ]
    }
    report = build_quality_safety_leak_report(
        hostile_candidate,
        fact_sheet=hostile_sheet,
        recompute_report=hostile_recompute,
        canonical_report=hostile_canonical,
    )
    assert_no_canary("hostile leak report", report)
    assert_no_raw_phrases("hostile leak report", report, ("synthetic_hostile maybe", "wait\n"))


def test_import_hygiene() -> None:
    source_path = REPO / "pipeline" / "quality_safety_leak_scanner.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    bad = [name for name in imports for part in FORBIDDEN_IMPORT_PARTS if part in name.lower()]
    check("no forbidden imports", bad == [], str(bad))
    check("imports allowed-only", set(imports).issubset(ALLOWED_IMPORTS), str(sorted(set(imports))))


def run() -> int:
    test_empty_and_malformed()
    test_leak_signatures()
    test_false_positive_resistance()
    test_verifier_coupling()
    test_conservative_attachment()
    test_report_shape_and_status()
    test_slice110_111_112_integration()
    test_seed_fixture_integration()
    test_no_leak_sweep()
    test_import_hygiene()
    print(f"\nquality_safety_leak_scanner: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
