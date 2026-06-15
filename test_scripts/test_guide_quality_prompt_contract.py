#!/usr/bin/env python3
"""Focused tests for the Claude-quality guide prompt contract (Slice 102).

Run with:

    python test_scripts/test_guide_quality_prompt_contract.py

The module turns safe request signals (depth axis / difficulty / generator preset /
style id / mode, or an explicit comprehensive bool) into a deterministic, leak-free
``prompt_block`` of distilled quality directives. Core rules apply to every guide;
the full structural contract is added only for comprehensive/long guides. It reads
no source text, inspects no PDF/image, OCRs nothing, reconstructs no table, and
calls no provider / model / cloud. Synthetic inputs only. No real spec evidence
quotes, source deck names, or output/reference filenames appear here.
"""
from __future__ import annotations

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
    "image_ref", "asset_ref", "asset_id", "url", "argv", "socket", "bytes",
}
KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/|C:\\\\|\\\\\\\\|[A-Za-z]:\\\\)")
URLLIKE = re.compile(r"https?://")
DATA_OR_BASE64 = re.compile(r"(data:|base64|[A-Za-z0-9+/]{120,}={0,2})")
ARGV_OR_SOCKET = re.compile(r"(\.sock|--[a-z]|mmproj|\.gguf|llama-server)")
# Synthetic canaries that must NEVER appear in the emitted contract / prompt block.
# These stand in for the kinds of real values the off-repo spec contains; the real
# values themselves are never placed in this repo.
FORBIDDEN_CANARIES = [
    "private-source.pdf",
    "reference-guide.pdf",
    "lecture-deck-name",
    "Quarterly Private Plan",
    "raw document paragraph",
    "raw OCR dump",
    "source caption text",
    "table cell text",
    "assets/secret.png",
    "sk_guidequalitycontract1234567890",
]

from pipeline.guide_quality_prompt_contract import (  # noqa: E402
    CONTEXT_KIND,
    CONTEXT_VERSION,
    COMPREHENSIVE_INFERRED,
    CORE_ONLY,
    build_guide_quality_prompt_contract,
    infer_comprehensive,
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


# --- Tests --------------------------------------------------------------------


# Distilled core directives that MUST be present (checked by stable phrases).
CORE_MARKERS = [
    "Resolve all ambiguity silently",
    "Never leak reasoning",
    "Never fabricate math",
    "Finish every worked example",
    "Show all arithmetic",
    "Reuse every value consistently",
    "Define every term before",
    "plain-English translation",
    "intuition block",
    "labelled tables",
    "exam-tutor voice",
    "EXAM ALERT",
]
STRUCTURE_MARKERS = [
    "Big Picture",
    "Formula sheet",
    "Definitions cheat sheet",
    "Common Mistakes",
    "Mock Exam",
    "Cram Sheet",
    "Self-Test Checklist",
    "Consolidation",
]


def test_core_rules_always_present() -> None:
    # Even a minimal / non-comprehensive request always carries the core rules.
    ctx = build_guide_quality_prompt_contract(output_depth="quick")
    check("quick → completed", ctx["status"] == "completed")
    check("quick → kind/version", ctx["kind"] == CONTEXT_KIND and ctx["version"] == CONTEXT_VERSION)
    check("quick → not comprehensive", ctx["summary"]["comprehensive"] is False)
    check("quick → no structure rules", ctx["summary"]["structure_rule_count"] == 0)
    check("quick → core rules counted", ctx["summary"]["core_rule_count"] >= 12)
    block = ctx["prompt_block"]
    for marker in CORE_MARKERS:
        check(f"core block has {marker!r}", marker in block)
    check("quick → warns core_only", CORE_ONLY in ctx["warnings"])
    # The contract must announce that it overrides weaker instructions.
    check("block asserts precedence", "take precedence" in block)


def test_comprehensive_structure_for_exhaustive() -> None:
    ctx = build_guide_quality_prompt_contract(output_depth="exhaustive")
    check("exhaustive → comprehensive", ctx["summary"]["comprehensive"] is True)
    check("exhaustive → structure counted", ctx["summary"]["structure_rule_count"] >= 12)
    block = ctx["prompt_block"]
    for marker in STRUCTURE_MARKERS:
        check(f"structure block has {marker!r}", marker in block)
    # Core rules still present alongside the structure.
    check("structure block keeps core rule", "Never fabricate math" in block)


def test_preset_and_style_infer_comprehensive() -> None:
    for preset in ("claude_exam", "claude_review", "claude_cram"):
        ctx = build_guide_quality_prompt_contract(preset_id=preset)
        check(f"{preset} → comprehensive", ctx["summary"]["comprehensive"] is True)
        check(f"{preset} → inferred warning", COMPREHENSIVE_INFERRED in ctx["warnings"])
    ctx = build_guide_quality_prompt_contract(style_id="master_longform")
    check("master_longform style → comprehensive", ctx["summary"]["comprehensive"] is True)
    # A plain study-guide style at balanced depth stays core-only.
    ctx = build_guide_quality_prompt_contract(output_depth="balanced", style_id="basic_study_guide")
    check("basic balanced → core only", ctx["summary"]["comprehensive"] is False)
    check("basic balanced → no structure", ctx["summary"]["structure_rule_count"] == 0)


def test_explicit_comprehensive_overrides_inference() -> None:
    # Explicit False beats an otherwise-comprehensive preset.
    ctx = build_guide_quality_prompt_contract(preset_id="claude_review", comprehensive=False)
    check("explicit False overrides preset", ctx["summary"]["comprehensive"] is False)
    check("explicit False → no inference warning", COMPREHENSIVE_INFERRED not in ctx["warnings"])
    # Explicit True beats a quick depth.
    ctx = build_guide_quality_prompt_contract(output_depth="quick", comprehensive=True)
    check("explicit True overrides quick", ctx["summary"]["comprehensive"] is True)
    check("explicit True → has structure", ctx["summary"]["structure_rule_count"] >= 12)


def test_quick_opts_out_even_with_preset() -> None:
    # An explicit "quick" depth opts out of the full skeleton even on a longform
    # preset — a user asking for short output should not be forced into 13 sections.
    ctx = build_guide_quality_prompt_contract(output_depth="quick", preset_id="claude_review")
    check("quick beats preset → core only", ctx["summary"]["comprehensive"] is False)


def test_unknown_depth_warns_but_degrades() -> None:
    ctx = build_guide_quality_prompt_contract(output_depth="ludicrous")
    check("unknown depth → still completed", ctx["status"] == "completed")
    check("unknown depth → warns output_depth_unknown", "output_depth_unknown" in ctx["warnings"])


def test_hostile_inputs_degrade_safely() -> None:
    # Non-string scalars / odd types must never raise.
    for bad in (123, [], {}, object()):
        ctx = build_guide_quality_prompt_contract(output_depth=bad, preset_id=bad, style_id=bad)
        check(f"hostile {type(bad).__name__} → dict", isinstance(ctx, dict))
        check(f"hostile {type(bad).__name__} → safe status", ctx["status"] in ("completed", "skipped"))
    check("infer_comprehensive hostile → bool", isinstance(infer_comprehensive(123, [], {}, object()), bool))


def test_determinism() -> None:
    import json

    a = build_guide_quality_prompt_contract(output_depth="exhaustive", preset_id="claude_review")
    b = build_guide_quality_prompt_contract(output_depth="exhaustive", preset_id="claude_review")
    check("deterministic identical serialization", json.dumps(a) == json.dumps(b))


def test_no_leak_over_all_paths() -> None:
    import json

    # A hostile canary fed through every scalar must never survive into the output;
    # the builder only emits fixed text + closed tokens, so canaries are dropped.
    cases = [
        build_guide_quality_prompt_contract(output_depth="exhaustive"),
        build_guide_quality_prompt_contract(output_depth="quick"),
        build_guide_quality_prompt_contract(preset_id="private-source.pdf", style_id="reference-guide.pdf"),
        build_guide_quality_prompt_contract(mode="raw OCR dump", difficulty="table cell text"),
    ]
    for index, ctx in enumerate(cases):
        leak = _scan_for_leak(ctx, f"case{index}")
        check(f"case{index} no leak", leak is None, leak or "")
        # The injected canary scalars must not echo into the serialized output.
        flat = json.dumps(ctx)
        for canary in ("private-source.pdf", "reference-guide.pdf", "raw OCR dump", "table cell text"):
            check(f"case{index} drops canary {canary!r}", canary not in flat)


def main() -> None:
    test_core_rules_always_present()
    test_comprehensive_structure_for_exhaustive()
    test_preset_and_style_infer_comprehensive()
    test_explicit_comprehensive_overrides_inference()
    test_quick_opts_out_even_with_preset()
    test_unknown_depth_warns_but_degrades()
    test_hostile_inputs_degrade_safely()
    test_determinism()
    test_no_leak_over_all_paths()
    print(f"\nGuide quality prompt contract tests: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
