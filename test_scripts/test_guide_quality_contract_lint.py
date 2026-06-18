#!/usr/bin/env python3
"""Focused tests for the deterministic guide-quality contract lint (Slice 102).

Run with:

    python test_scripts/test_guide_quality_contract_lint.py

The module scans a generated guide's Markdown for SAFE COUNTS ONLY (reasoning-leak
signatures, required-section presence by heading alias, exam-alert and table counts,
and shallow deferred worked-example / arithmetic / consistency signals). It is
flag-only: it never rejects, regenerates, or fails a job. Critically it stores no
excerpt — never the matched phrase, heading text, table content, formula, example,
or any number from the guide. Synthetic Markdown only; no provider/model/cloud call.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

SECRET_KEY_NAMES = {"api_key", "apikey", "secret", "token", "authorization", "password"}
FORBIDDEN_KEY_NAMES = {
    "filename", "path", "title", "text", "ocr_text", "caption", "table_text",
    "image_ref", "asset_ref", "asset_id", "url", "argv", "socket", "bytes", "excerpt",
}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")

# Hostile canaries embedded in the scanned Markdown. None may appear in the report.
CANARY_FILENAME = "private-source.pdf"
CANARY_TITLE = "Quarterly Private Plan"
CANARY_TABLE = "secret table cell 42x"
CANARY_FORMULA = "E=mc^2_private"
CANARY_KEY = "sk_guidequalitylintcanary1234567890"
FORBIDDEN_CANARIES = [CANARY_FILENAME, CANARY_TITLE, CANARY_TABLE, CANARY_FORMULA, CANARY_KEY]

from pipeline.guide_quality_contract_lint import (  # noqa: E402
    REPORT_KIND,
    REPORT_VERSION,
    build_guide_quality_contract_lint_report,
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


# A clean, comprehensive synthetic guide that satisfies every structural check.
CLEAN_COMPREHENSIVE = """# Topic Study Guide

## How to use this guide
Read top to bottom.

## Big Picture
The three questions this answers.

## Notation and key terms
| symbol | meaning |
| --- | --- |
| x | input |

## Core Topic
A definition, then a worked example carried to the end.

⚠️ EXAM ALERT: this is commonly tested.

## Summary comparison
| method | pro | con |
| --- | --- | --- |
| a | fast | rough |

## Formula sheet
| formula | meaning | page |
| --- | --- | --- |
| s = vt | distance | p1 |

## Definitions cheat sheet
| term | meaning |
| --- | --- |
| x | input |

## Common Mistakes That Lose Marks
Watch the signs.

## Consolidation pipeline
End-to-end flow plus a decision table.

## Mock Exam
Q1 with a full worked solution.

## Last-Minute Cram Sheet
Dense recap.

## Self-Test Checklist
Can I explain x?
"""


def test_empty_and_missing_degrade() -> None:
    for label, value in (("None", None), ("empty", ""), ("whitespace", "   "), ("non-str", 123)):
        rep = build_guide_quality_contract_lint_report(value, comprehensive=True)
        check(f"{label} → skipped", rep["status"] == "skipped")
        check(f"{label} → kind/version", rep["kind"] == REPORT_KIND and rep["version"] == REPORT_VERSION)
        check(f"{label} → empty checks", rep["checks"] == [])


def test_clean_comprehensive_passes() -> None:
    rep = build_guide_quality_contract_lint_report(CLEAN_COMPREHENSIVE, comprehensive=True)
    check("clean → completed", rep["status"] == "completed")
    s = rep["summary"]
    check("clean → zero reasoning leaks", s["reasoning_leak_count"] == 0)
    check("clean → all sections present", s["required_section_present_count"] == s["required_section_count"] and s["required_section_count"] >= 8)
    check("clean → exam alert counted once", s["exam_alert_count"] == 1)
    check("clean → tables counted", s["table_count"] >= 4)
    check("clean → no warnings", rep["warnings"] == [])
    # The reasoning-leak check must be a passed status.
    leak_check = next(c for c in rep["checks"] if c["kind"] == "reasoning_leak")
    check("clean → reasoning_leak passed", leak_check["status"] == "passed")


def test_reasoning_leak_flagged_without_storing_phrase() -> None:
    leaky = (
        "## Intro\n"
        "Actually, it seems the layout is confusing. I think presumably this is unclear. "
        "I'm not sure, but the slide is ambiguous.\n"
    )
    rep = build_guide_quality_contract_lint_report(leaky, comprehensive=False)
    s = rep["summary"]
    check("leaky → leaks counted", s["reasoning_leak_count"] >= 5)
    check("leaky → warns reasoning_leak_present", "reasoning_leak_present" in rep["warnings"])
    leak_check = next(c for c in rep["checks"] if c["kind"] == "reasoning_leak")
    check("leaky → reasoning_leak warning", leak_check["status"] == "warning")
    # The matched phrases must NOT be stored anywhere in the report.
    flat = json.dumps(rep)
    for phrase in ("Actually", "it seems", "confusing", "presumably", "the slide is", "I'm not sure"):
        check(f"leaky → does not store {phrase!r}", phrase not in flat)


def test_intensifier_false_positives_not_counted() -> None:
    # Slice 152: ordinary factual prose that uses "actually" / "presumably" as a
    # mid-sentence intensifier must NOT count as a reasoning leak. These are the
    # detector_boundary_false_positive cases that kept the measured baseline red.
    factual = (
        "## Softmax\n"
        "The model actually outputs probabilities after softmax. "
        "This value is presumably rounded in the worked example. "
        "This step is actually just matrix multiplication, and the bias is "
        "presumably small here.\n"
    )
    rep = build_guide_quality_contract_lint_report(factual, comprehensive=False)
    s = rep["summary"]
    check("factual intensifiers → zero leaks", s["reasoning_leak_count"] == 0, f"count={s['reasoning_leak_count']}")
    leak_check = next(c for c in rep["checks"] if c["kind"] == "reasoning_leak")
    check("factual intensifiers → reasoning_leak passed", leak_check["status"] == "passed")
    check("factual intensifiers → no leak warning", "reasoning_leak_present" not in rep["warnings"])


def test_phrase_boundary_not_substring() -> None:
    # Boundary matching must not fire inside a longer token: "unclearly" must not
    # match "is unclear" when there is no standalone phrase.
    prose = "## Notes\nThe boundary is unclearly drawn but the rule is precise.\n"
    rep = build_guide_quality_contract_lint_report(prose, comprehensive=False)
    check("substring inside word → zero leaks", rep["summary"]["reasoning_leak_count"] == 0)


def test_true_reasoning_leaks_still_counted() -> None:
    # Slice 152 must NOT weaken detection of genuine internal-reasoning / prompt-meta
    # / planning / process-narration leaks. Each synthetic leak line covers one
    # category; all must still increment the count. Synthetic strings only.
    cases = {
        "internal_reasoning": "It seems the answer follows, and i think the rest is unclear.",
        "user_intent": "The user wants a deeper proof, and what the user wants is more rigour.",
        "prompt_meta": "The prompt asks for ten sections, and the prompt is asking for tables.",
        "planning": "Here's my plan: i'm going to include three examples next.",
        "deciding_inclusion": "I should include the derivation; deciding what to include is hard.",
        "process_narration": "Let me think about this. Let me reconsider my reasoning before continuing.",
        "intensifier_marker": "Actually, that is wrong. Presumably this needs revisiting.",
    }
    for label, line in cases.items():
        rep = build_guide_quality_contract_lint_report(f"## H\n{line}\n", comprehensive=False)
        s = rep["summary"]
        check(f"true leak ({label}) counted", s["reasoning_leak_count"] >= 1, f"count={s['reasoning_leak_count']}")
        leak_check = next(c for c in rep["checks"] if c["kind"] == "reasoning_leak")
        check(f"true leak ({label}) warns", leak_check["status"] == "warning")
        check(f"true leak ({label}) warning token", "reasoning_leak_present" in rep["warnings"])
        # Never store the matched phrase.
        flat = json.dumps(rep)
        for fragment in ("user wants", "prompt asks", "my plan", "let me", "actually", "presumably"):
            check(f"true leak ({label}) drops {fragment!r}", fragment not in flat.lower())


def test_comprehensive_missing_sections_warns() -> None:
    thin = "# Guide\n\n## Core Topic\nSome prose only, no required sections.\n"
    rep = build_guide_quality_contract_lint_report(thin, comprehensive=True)
    s = rep["summary"]
    check("thin → sections missing", s["required_section_present_count"] < s["required_section_count"])
    check("thin → warns required_sections_missing", "required_sections_missing" in rep["warnings"])
    check("thin → warns exam_alerts_absent", "exam_alerts_absent" in rep["warnings"])
    check("thin → warns reference_tables_absent", "reference_tables_absent" in rep["warnings"])
    struct = next(c for c in rep["checks"] if c["kind"] == "required_structure")
    check("thin → required_structure warning", struct["status"] == "warning")


def test_alias_sections_accepted() -> None:
    # Headings phrased with safe aliases should still satisfy the structure check.
    aliased = (
        "# Guide\n"
        "## How to use this guide\n"
        "## The Big Picture\n"
        "## Glossary\n"
        "## Formulas at a glance\n"
        "## Definitions reference\n"
        "## Marks you lose\n"
        "## Putting it together\n"
        "## Practice questions\n"
        "## Quick recap\n"
        "## Checklist\n"
        "⚠️ EXAM ALERT here\n"
        "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    )
    rep = build_guide_quality_contract_lint_report(aliased, comprehensive=True)
    s = rep["summary"]
    check("aliases → all sections present", s["required_section_present_count"] == s["required_section_count"])
    check("aliases → no missing-section warning", "required_sections_missing" not in rep["warnings"])


def test_non_comprehensive_structure_not_applicable() -> None:
    rep = build_guide_quality_contract_lint_report("# Short\nSome notes.\n", comprehensive=False)
    struct = next(c for c in rep["checks"] if c["kind"] == "required_structure")
    check("non-comp → structure not_applicable", struct["status"] == "not_applicable")
    check("non-comp → required_section_count 0", rep["summary"]["required_section_count"] == 0)
    check("non-comp → no missing-section warning", "required_sections_missing" not in rep["warnings"])


def test_deferred_checks_present() -> None:
    rep = build_guide_quality_contract_lint_report(CLEAN_COMPREHENSIVE, comprehensive=True)
    kinds = {c["kind"]: c["status"] for c in rep["checks"]}
    check("worked_examples present (unknown)", kinds.get("worked_examples") == "unknown")
    check("arithmetic_steps present (unknown)", kinds.get("arithmetic_steps") == "unknown")
    check("consistency present (not_applicable)", kinds.get("consistency") == "not_applicable")


def test_max_items_truncates_to_partial() -> None:
    rep = build_guide_quality_contract_lint_report(CLEAN_COMPREHENSIVE, comprehensive=True, max_items=2)
    check("max_items → partial", rep["status"] == "partial")
    check("max_items → at most 2 checks", len(rep["checks"]) <= 2)
    check("max_items → warns max_items_applied", "max_items_applied" in rep["warnings"])


def test_check_ids_and_shape() -> None:
    rep = build_guide_quality_contract_lint_report(CLEAN_COMPREHENSIVE, comprehensive=True)
    ids = [c["check_id"] for c in rep["checks"]]
    check("check ids sequential", ids == [f"guide_quality_contract_check_{i:04d}" for i in range(1, len(ids) + 1)])
    for c in rep["checks"]:
        check(f"{c['check_id']} has int observed", isinstance(c["observed_count"], int))
        check(f"{c['check_id']} has int expected", isinstance(c["expected_count"], int))
        check(f"{c['check_id']} status closed", c["status"] in {"passed", "warning", "not_applicable", "unknown"})


def test_determinism() -> None:
    a = build_guide_quality_contract_lint_report(CLEAN_COMPREHENSIVE, comprehensive=True)
    b = build_guide_quality_contract_lint_report(CLEAN_COMPREHENSIVE, comprehensive=True)
    check("deterministic identical serialization", json.dumps(a) == json.dumps(b))


def test_no_leak_with_hostile_markdown() -> None:
    hostile = (
        f"# {CANARY_TITLE}\n"
        f"Source file {CANARY_FILENAME} key {CANARY_KEY}.\n"
        "Actually, it seems unclear.\n"
        f"| {CANARY_TABLE} | {CANARY_FORMULA} |\n| --- | --- |\n| 1 | 2 |\n"
        "⚠️ EXAM ALERT data:image/png;base64,QQQ\n"
        "## Mock Exam\nQ1?\n"
    )
    for comp in (True, False):
        rep = build_guide_quality_contract_lint_report(hostile, comprehensive=comp)
        leak = _scan_for_leak(rep, f"comp={comp}")
        check(f"comp={comp} no leak in report", leak is None, leak or "")
        flat = json.dumps(rep)
        for canary in FORBIDDEN_CANARIES:
            check(f"comp={comp} drops canary {canary!r}", canary not in flat)
        check(f"comp={comp} drops base64 marker", "base64" not in flat and "data:image" not in flat)
        # Even though leaks/tables were counted, only counts survive.
        check(f"comp={comp} still counts leaks", rep["summary"]["reasoning_leak_count"] >= 1)


def main() -> None:
    test_empty_and_missing_degrade()
    test_clean_comprehensive_passes()
    test_reasoning_leak_flagged_without_storing_phrase()
    test_intensifier_false_positives_not_counted()
    test_phrase_boundary_not_substring()
    test_true_reasoning_leaks_still_counted()
    test_comprehensive_missing_sections_warns()
    test_alias_sections_accepted()
    test_non_comprehensive_structure_not_applicable()
    test_deferred_checks_present()
    test_max_items_truncates_to_partial()
    test_check_ids_and_shape()
    test_determinism()
    test_no_leak_with_hostile_markdown()
    print(f"\nGuide quality contract lint tests: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
