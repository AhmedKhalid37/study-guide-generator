"""Prompt-assembly check for the optional page-reference include-section fragment.

Slice 23B aligns the ``slide_page_references`` fragment with the default
source-page citation directive: compact ``(p. N)`` / ``(pp. N-M)`` citations
when source anchors exist, with no invented page numbers.

Because the fragment is injected via ``build_include_sections_block`` BEFORE the
final ``MARKDOWN_MATH_SYSTEM`` block, this asserts:
  1. the fragment itself carries compact citation examples and no-invention rule;
  2. an assembled prompt with ``slide_page_references`` enabled includes them;
  3. assembly ordering is preserved — preset prompt first (preset path), axes
     before include sections, citation directive before MARKDOWN_MATH_SYSTEM, and
     MARKDOWN_MATH_SYSTEM stays the final block (both default and preset paths);
  4. there is no conflict with the math guidance (math block still intact + last).

    python test_scripts/test_page_reference_format.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.orchestrator import (  # noqa: E402
    INCLUDE_SECTION_FRAGMENTS,
    MARKDOWN_MATH_SYSTEM,
    SOURCE_PAGE_CITATION_DIRECTIVE,
    build_axis_directives_block,
    build_include_sections_block,
    build_messages,
    build_messages_for_preset,
)

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


FRAGMENT = INCLUDE_SECTION_FRAGMENTS["slide_page_references"]

REQUIRED_PHRASES = [
    "(p. N)",
    "(pp. N-M)",
    "Do not invent page numbers",
]


def _system(messages):
    return next(m["content"] for m in messages if m["role"] == "system")


def run():
    # 1. The fragment itself carries compact examples + no-invention guidance.
    for phrase in REQUIRED_PHRASES:
        check(f"1: fragment contains {phrase!r}", phrase in FRAGMENT)
    check(
        "1: fragment no longer bans compact p./pp. citations",
        "Never use p." not in FRAGMENT and "Never use pp." not in FRAGMENT,
    )

    # 2. Assembled prompt (default path) with the toggle on includes the format.
    enabled = {"slide_page_references": True}
    default_sys = _system(
        build_messages(
            "## Page 20\nSource with anchor.",
            title="T",
            prompt_name="basic_study_guide",
            include_sections=enabled,
        )
    )
    check("2: assembled default prompt has (p. N)", "(p. N)" in default_sys)
    check("2: assembled default prompt has (pp. N-M)", "(pp. N-M)" in default_sys)
    check(
        "2: assembled default prompt has source citation directive",
        SOURCE_PAGE_CITATION_DIRECTIVE in default_sys,
    )

    # 3. Ordering: axes before include sections, source citations before the math
    #    block, and MARKDOWN_MATH_SYSTEM stays final (default path).
    axis_block = build_axis_directives_block(
        output_depth="balanced", difficulty="exam_level"
    )
    include_block = build_include_sections_block(enabled)
    ordered_sys = _system(
        build_messages(
            "## Page 1\nSource.",
            title="T",
            prompt_name="basic_study_guide",
            include_sections=enabled,
            output_depth="balanced",
            difficulty="exam_level",
        )
    )
    axis_pos = ordered_sys.find(axis_block)
    include_pos = ordered_sys.find(include_block)
    citation_pos = ordered_sys.find(SOURCE_PAGE_CITATION_DIRECTIVE)
    math_pos = ordered_sys.find(MARKDOWN_MATH_SYSTEM)
    check("3: axis block present", axis_pos != -1)
    check("3: include block present", include_pos != -1)
    check("3: citation directive present", citation_pos != -1)
    check("3: axes before include sections", 0 <= axis_pos < include_pos)
    check("3: include sections before citation directive", include_pos < citation_pos)
    check("3: citation directive before math block", citation_pos < math_pos)
    check(
        "3: default path ends with MARKDOWN_MATH_SYSTEM",
        ordered_sys.endswith(MARKDOWN_MATH_SYSTEM),
        f"...{ordered_sys[-50:]!r}",
    )

    # 4. Preset path: preset prompt first, math block last, page format present.
    preset_prompt = "You are a tuned generator preset. Markdown only."
    preset_sys = _system(
        build_messages_for_preset(
            "## Page 1\nSource.",
            system_prompt=preset_prompt,
            include_sections=enabled,
            output_depth="balanced",
            difficulty="exam_level",
        )
    )
    check(
        "4: preset system prompt comes first",
        preset_sys.startswith(preset_prompt),
        f"{preset_sys[:50]!r}...",
    )
    check("4: preset path includes (p. N)", "(p. N)" in preset_sys)
    check(
        "4: preset path ends with MARKDOWN_MATH_SYSTEM",
        preset_sys.endswith(MARKDOWN_MATH_SYSTEM),
        f"...{preset_sys[-50:]!r}",
    )
    # Preset ordering: preset < axes < include < citation < math.
    p_axis = preset_sys.find(axis_block)
    p_include = preset_sys.find(include_block)
    p_citation = preset_sys.find(SOURCE_PAGE_CITATION_DIRECTIVE)
    p_math = preset_sys.find(MARKDOWN_MATH_SYSTEM)
    check(
        "4: preset ordering preset<axes<include<citation<math",
        0 == preset_sys.find(preset_prompt) < p_axis < p_include < p_citation < p_math,
    )

    # 5. Math guidance untouched / no conflict: the aligned-math rule still rides
    #    along intact when page references are enabled.
    check(
        "5: math contract intact alongside page refs",
        "\\begin{aligned}" in default_sys
        and "Avoid very long single-line display equations" in default_sys,
    )

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
