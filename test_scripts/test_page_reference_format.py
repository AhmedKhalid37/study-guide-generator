"""Prompt-assembly check for the page-reference-format slice.

The ``slide_page_references`` include-section fragment was tightened (prompt-only)
so generated guides always cite source slides/pages in a single parenthesized
format: ``(page N)``, ``(pages N-M)``, ``(pages N, M, P-Q)``. The fragment must
explicitly forbid the loose forms (``p.``, ``pp.``, ``pN``, bare fragments) and
spaced-dash ranges.

Because the fragment is injected via ``build_include_sections_block`` BEFORE the
final ``MARKDOWN_MATH_SYSTEM`` block, this asserts:
  1. the fragment itself carries the exact required format examples and the bans;
  2. an assembled prompt with ``slide_page_references`` enabled includes them;
  3. assembly ordering is preserved — preset prompt first (preset path), axes
     before include sections, include sections before MARKDOWN_MATH_SYSTEM, and
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

# Exact format examples the guidance must contain.
REQUIRED_PHRASES = [
    "(page N)",
    "(pages N-M)",
    "(pages N, M, P-Q)",
    "Never use p.",
]
# Loose forms the guidance must explicitly ban (so the model is steered away).
BANNED_MENTIONS = ["pp.", "pN", "en dash"]


def _system(messages):
    return next(m["content"] for m in messages if m["role"] == "system")


def run():
    # 1. The fragment itself carries the exact required examples + bans.
    for phrase in REQUIRED_PHRASES:
        check(f"1: fragment contains {phrase!r}", phrase in FRAGMENT)
    for mention in BANNED_MENTIONS:
        check(f"1: fragment forbids {mention!r}", mention in FRAGMENT)

    # 1b. The fragment must NOT recommend the old loose '(p. N)' form.
    check(
        "1: fragment no longer recommends '(p. N)'",
        "such as '(p. N)'" not in FRAGMENT,
    )

    # 2. Assembled prompt (default path) with the toggle on includes the format.
    enabled = {"slide_page_references": True}
    default_sys = _system(
        build_messages(
            "Source with ## Page 20 anchor.",
            title="T",
            prompt_name="basic_study_guide",
            include_sections=enabled,
        )
    )
    check("2: assembled default prompt has (page N)", "(page N)" in default_sys)
    check("2: assembled default prompt has (pages N-M)", "(pages N-M)" in default_sys)
    check("2: assembled default prompt has 'Never use p.'", "Never use p." in default_sys)

    # 3. Ordering: axes before include sections, include sections before the math
    #    block, and MARKDOWN_MATH_SYSTEM stays final (default path).
    axis_block = build_axis_directives_block(
        output_depth="balanced", difficulty="exam_level"
    )
    include_block = build_include_sections_block(enabled)
    ordered_sys = _system(
        build_messages(
            "Source.",
            title="T",
            prompt_name="basic_study_guide",
            include_sections=enabled,
            output_depth="balanced",
            difficulty="exam_level",
        )
    )
    axis_pos = ordered_sys.find(axis_block)
    include_pos = ordered_sys.find(include_block)
    math_pos = ordered_sys.find(MARKDOWN_MATH_SYSTEM)
    check("3: axis block present", axis_pos != -1)
    check("3: include block present", include_pos != -1)
    check("3: axes before include sections", 0 <= axis_pos < include_pos)
    check("3: include sections before math block", include_pos < math_pos)
    check(
        "3: default path ends with MARKDOWN_MATH_SYSTEM",
        ordered_sys.endswith(MARKDOWN_MATH_SYSTEM),
        f"...{ordered_sys[-50:]!r}",
    )

    # 4. Preset path: preset prompt first, math block last, page format present.
    preset_prompt = "You are a tuned generator preset. Markdown only."
    preset_sys = _system(
        build_messages_for_preset(
            "Source.",
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
    check("4: preset path includes (page N)", "(page N)" in preset_sys)
    check(
        "4: preset path ends with MARKDOWN_MATH_SYSTEM",
        preset_sys.endswith(MARKDOWN_MATH_SYSTEM),
        f"...{preset_sys[-50:]!r}",
    )
    # Preset ordering: preset < axes < include < math.
    p_axis = preset_sys.find(axis_block)
    p_include = preset_sys.find(include_block)
    p_math = preset_sys.find(MARKDOWN_MATH_SYSTEM)
    check(
        "4: preset ordering preset<axes<include<math",
        0 == preset_sys.find(preset_prompt) < p_axis < p_include < p_math,
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
