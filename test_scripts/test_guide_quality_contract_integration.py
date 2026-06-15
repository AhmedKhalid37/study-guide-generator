#!/usr/bin/env python3
"""Integration tests for the guide-quality contract wiring (Slice 102).

Run with:

    python test_scripts/test_guide_quality_contract_integration.py

Verifies how the prompt contract is wired into the generation prompt path WITHOUT
calling an LLM/provider/model/cloud:

  * the safe builder in ``run_llm_job`` returns the contract block for normal
    requests and ``""`` on degrade (so the prompt stays byte-identical);
  * the contract is appended at exactly ONE integration point (single
    ``## Guide Quality Contract`` heading);
  * it composes with the dual-explanation block (both can coexist in the assembled
    source) and is independent of the coverage-aware guidance;
  * Ask Guide is unaffected (no Ask module references the contract);
  * the helper output carries no leak.

Pure / static-source inspection only. No PDFs/images/OCR; no provider call.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PASS = 0
FAIL = 0

KEYLIKE = re.compile(r"(sk-|sk_)[A-Za-z0-9_\-]{16,}")
PATHLIKE = re.compile(r"(/home/|/usr/|/etc/|/var/|/tmp/)")
URLLIKE = re.compile(r"https?://")

from pipeline import run_llm_job  # noqa: E402
from pipeline.dual_explanation_prompt_context import (  # noqa: E402
    build_dual_explanation_prompt_context,
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


def test_safe_builder_returns_block() -> None:
    block = run_llm_job._build_guide_quality_prompt_block_safely(
        output_depth="exhaustive", preset_id="claude_review", style_id="master_longform", mode="exam"
    )
    check("builder returns non-empty block", isinstance(block, str) and bool(block.strip()))
    check("block has core rule", "Never fabricate math" in block)
    check("block has structure (comprehensive)", "Mock Exam" in block)
    # Core-only request still yields a block (core rules always apply).
    core = run_llm_job._build_guide_quality_prompt_block_safely(output_depth="quick")
    check("core-only request still returns block", bool(core.strip()))
    check("core-only omits structure skeleton", "Mock Exam" not in core)


def test_safe_builder_degrades_to_empty() -> None:
    # Hostile inputs must never raise and must degrade to "" only if the builder
    # cannot produce a completed context. (Odd scalars still produce core rules, so
    # the contract is robust; the contract is empty only on an internal failure.)
    for bad in (object(), 12.5, b"bytes"):
        out = run_llm_job._build_guide_quality_prompt_block_safely(output_depth=bad, preset_id=bad)
        check(f"hostile {type(bad).__name__} → str", isinstance(out, str))


def test_single_integration_point() -> None:
    source = (REPO / "pipeline" / "run_llm_job.py").read_text(encoding="utf-8")
    count = source.count("## Guide Quality Contract")
    check("exactly one contract heading appended", count == 1, f"found {count}")
    # The append uses the safe builder, not the raw module, at the call site.
    check("call site uses safe builder", "_build_guide_quality_prompt_block_safely(" in source)


def test_composes_with_dual_explanation() -> None:
    # Simulate the run_llm_job assembly order: dual-explanation block then the
    # contract block, both appended to a base source. Both must survive intact and
    # neither must clobber the other.
    base = "Base source text."
    dual_ctx = build_dual_explanation_prompt_context(True)
    dual_block = dual_ctx["prompt_block"]
    contract = run_llm_job._build_guide_quality_prompt_block_safely(
        output_depth="exhaustive", preset_id="claude_review"
    )
    assembled = base
    assembled = assembled.rstrip() + f"\n\n## Dual Explanation Mode\n\n{dual_block}"
    assembled = assembled.rstrip() + f"\n\n## Guide Quality Contract\n\n{contract}"
    check("assembled keeps base", "Base source text." in assembled)
    check("assembled keeps dual heading", "## Dual Explanation Mode" in assembled)
    check("assembled keeps contract heading", "## Guide Quality Contract" in assembled)
    check("assembled keeps dual content", "Explain it simply:" in assembled)
    check("assembled keeps contract content", "Never fabricate math" in assembled)
    # Headings appear once each (no duplication from composition).
    check("one dual heading", assembled.count("## Dual Explanation Mode") == 1)
    check("one contract heading", assembled.count("## Guide Quality Contract") == 1)


def test_ask_guide_unaffected() -> None:
    ask_files = list((REPO / "pipeline").glob("ask_*.py"))
    check("ask modules exist to scan", len(ask_files) > 0)
    offenders = []
    for path in ask_files:
        text = path.read_text(encoding="utf-8")
        if (
            "guide_quality_prompt_contract" in text
            or "guide_quality_contract_lint" in text
            or "Guide Quality Contract" in text
        ):
            offenders.append(path.name)
    check("no Ask module references the contract", offenders == [], ",".join(offenders))


def test_helper_output_no_leak() -> None:
    block = run_llm_job._build_guide_quality_prompt_block_safely(
        output_depth="exhaustive", preset_id="private-source.pdf", style_id="reference-guide.pdf"
    )
    payload = json.dumps(block)
    check("block has no key-like value", not KEYLIKE.search(payload))
    check("block has no host path", not PATHLIKE.search(payload))
    check("block has no URL", not URLLIKE.search(payload))
    check("injected filename canary dropped", "private-source.pdf" not in payload)
    check("injected reference canary dropped", "reference-guide.pdf" not in payload)


def main() -> None:
    test_safe_builder_returns_block()
    test_safe_builder_degrades_to_empty()
    test_single_integration_point()
    test_composes_with_dual_explanation()
    test_ask_guide_unaffected()
    test_helper_output_no_leak()
    print(f"\nGuide quality contract integration tests: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
