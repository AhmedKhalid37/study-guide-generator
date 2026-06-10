#!/usr/bin/env python3
"""Focused tests for Slice 23B source page-citation prompt assembly.

These checks are prompt-assembly tests, not LLM-output tests. They prove the
conditional source page-citation directive appears only when source text carries
``## Page N`` anchors, and that preset/non-preset paths preserve the final
``MARKDOWN_MATH_SYSTEM`` invariant.

    python test_scripts/test_source_page_citations.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.orchestrator import (  # noqa: E402
    MARKDOWN_MATH_SYSTEM,
    SOURCE_PAGE_CITATION_DIRECTIVE,
    build_messages,
    build_messages_for_preset,
    build_source_page_citation_block,
    source_has_page_anchors,
)

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def _system(messages: list[dict]) -> str:
    return next(message["content"] for message in messages if message["role"] == "system")


def _user(messages: list[dict]) -> str:
    return next(message["content"] for message in messages if message["role"] == "user")


def test_anchor_detection_and_directive_block() -> None:
    with_anchors = "Intro\n\n## Page 3\nImportant definition."
    no_anchors = "Intro\n\n### Page 3\nNot an extraction anchor."
    check("detects Page anchor", source_has_page_anchors(with_anchors))
    check("does not detect non-anchor heading", not source_has_page_anchors(no_anchors))
    check(
        "directive returned when anchors exist",
        build_source_page_citation_block(with_anchors) == SOURCE_PAGE_CITATION_DIRECTIVE,
    )
    check("directive absent without anchors", build_source_page_citation_block(no_anchors) == "")


def test_template_prompt_includes_directive_for_anchors() -> None:
    source = "## Page 1\nAlpha fact.\n\n## Page 2\nBeta formula."
    messages = build_messages(source, title="Citation Prompt", prompt_name="basic_study_guide")
    system = _system(messages)
    user = _user(messages)
    check("template: citation directive present", SOURCE_PAGE_CITATION_DIRECTIVE in system)
    check("template: user still contains Page 1", "## Page 1" in user)
    check("template: user still contains Page 2", "## Page 2" in user)
    check("template: compact p citation guidance present", "(p. 3)" in system)
    check("template: compact pp citation guidance present", "(pp. 3-5)" in system)
    check("template: no-invent instruction present", "Do not invent page citations" in system)
    check(
        "template: directive before math system",
        0 <= system.find(SOURCE_PAGE_CITATION_DIRECTIVE) < system.find(MARKDOWN_MATH_SYSTEM),
    )
    check("template: math system remains last", system.endswith(MARKDOWN_MATH_SYSTEM))


def test_template_prompt_no_anchor_baseline_unchanged() -> None:
    messages = build_messages("Alpha fact without anchors.", title="No Anchors")
    system = _system(messages)
    check("template no-anchor: directive absent", SOURCE_PAGE_CITATION_DIRECTIVE not in system)
    check("template no-anchor: system is math baseline", system == MARKDOWN_MATH_SYSTEM)


def test_preset_prompt_matches_template_behavior() -> None:
    preset_prompt = "Preset system prompt."
    with_anchors = "## Page 7\nSource fact."
    no_anchors = "Source fact without anchors."
    with_messages = build_messages_for_preset(with_anchors, system_prompt=preset_prompt)
    no_messages = build_messages_for_preset(no_anchors, system_prompt=preset_prompt)
    with_system = _system(with_messages)
    no_system = _system(no_messages)
    check("preset with anchors: preset prompt first", with_system.startswith(preset_prompt))
    check("preset with anchors: citation directive present", SOURCE_PAGE_CITATION_DIRECTIVE in with_system)
    check(
        "preset with anchors: order preset<directive<math",
        0 == with_system.find(preset_prompt)
        < with_system.find(SOURCE_PAGE_CITATION_DIRECTIVE)
        < with_system.find(MARKDOWN_MATH_SYSTEM),
    )
    check("preset with anchors: math system remains last", with_system.endswith(MARKDOWN_MATH_SYSTEM))
    check(
        "preset no-anchor: baseline unchanged",
        no_system == f"{preset_prompt}\n\n{MARKDOWN_MATH_SYSTEM}",
    )


def run() -> bool:
    test_anchor_detection_and_directive_block()
    test_template_prompt_includes_directive_for_anchors()
    test_template_prompt_no_anchor_baseline_unchanged()
    test_preset_prompt_matches_template_behavior()

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
