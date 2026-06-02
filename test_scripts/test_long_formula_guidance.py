"""Prompt-assembly check for the long-formula guidance slice (math-formula-guidance).

Slice 3 (prompt-guidance only) adds a concise rule to ``MARKDOWN_MATH_SYSTEM``
telling the model to avoid very long single-line display equations and instead
break long derivations across multiple lines inside ``\\begin{aligned}``.

Because the guidance lives in ``MARKDOWN_MATH_SYSTEM`` — the math/table contract
that both the default and the generator-preset paths append LAST — this asserts:
  1. the new guidance is present in the DEFAULT path's system message;
  2. the new guidance is present in the PRESET path's system message;
  3. ``MARKDOWN_MATH_SYSTEM`` is still the FINAL appended block in both paths
     (preset system prompt, when present, stays first);
  4. the guidance still rides along when a formula-heavy guide enables the
     ``formula_sheet`` / ``worked_examples`` / ``solved_mock_exam`` sections.

    python test_scripts/test_long_formula_guidance.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.orchestrator import (  # noqa: E402
    MARKDOWN_MATH_SYSTEM,
    build_messages,
    build_messages_for_preset,
)

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# A distinctive phrase from the new guidance (also asserts the existing aligned
# rule is intact, so the slice did not weaken the surrounding math contract).
GUIDANCE_NEEDLE = "Avoid very long single-line display equations"
PROSE_NEEDLE = "never wrap an explanatory sentence"
ALIGNED_NEEDLE = "\\begin{aligned}"


def _system(messages):
    return next(m["content"] for m in messages if m["role"] == "system")


def run():
    # 0. The guidance lives in MARKDOWN_MATH_SYSTEM (single source of truth).
    check(
        "0: MARKDOWN_MATH_SYSTEM carries the long-formula guidance",
        GUIDANCE_NEEDLE in MARKDOWN_MATH_SYSTEM
        and PROSE_NEEDLE in MARKDOWN_MATH_SYSTEM
        and ALIGNED_NEEDLE in MARKDOWN_MATH_SYSTEM,
    )

    # 1. Default path includes the new guidance.
    default_sys = _system(
        build_messages("Some source.", title="T", prompt_name="basic_study_guide")
    )
    check("1: default path includes the new guidance", GUIDANCE_NEEDLE in default_sys)
    check(
        "1: default path ends with MARKDOWN_MATH_SYSTEM",
        default_sys.endswith(MARKDOWN_MATH_SYSTEM),
        f"...{default_sys[-60:]!r}",
    )

    # 2. Preset path includes the new guidance, with the preset prompt first.
    preset_prompt = "You are a tuned generator preset. Markdown only."
    preset_sys = _system(
        build_messages_for_preset("Some source.", system_prompt=preset_prompt)
    )
    check("2: preset path includes the new guidance", GUIDANCE_NEEDLE in preset_sys)
    check(
        "2: preset system prompt comes first",
        preset_sys.startswith(preset_prompt),
        f"{preset_sys[:60]!r}...",
    )
    check(
        "2: preset path ends with MARKDOWN_MATH_SYSTEM (final appended block)",
        preset_sys.endswith(MARKDOWN_MATH_SYSTEM),
        f"...{preset_sys[-60:]!r}",
    )

    # 3. Formula-heavy guide (sections + axes set): guidance still present AND
    #    MARKDOWN_MATH_SYSTEM still last, after the section/axis fragments.
    heavy_sections = {
        "formula_sheet": True,
        "worked_examples": True,
        "solved_mock_exam": True,
        "mcqs_with_answers": True,
    }
    heavy_sys = _system(
        build_messages(
            "Some source.",
            title="T",
            prompt_name="basic_study_guide",
            include_sections=heavy_sections,
            output_depth="exhaustive",
            difficulty="exam_level",
        )
    )
    check(
        "3: formula-heavy default path includes the new guidance",
        GUIDANCE_NEEDLE in heavy_sys,
    )
    check(
        "3: formula-heavy default path still ends with MARKDOWN_MATH_SYSTEM",
        heavy_sys.endswith(MARKDOWN_MATH_SYSTEM),
        f"...{heavy_sys[-60:]!r}",
    )

    heavy_preset_sys = _system(
        build_messages_for_preset(
            "Some source.",
            system_prompt=preset_prompt,
            include_sections=heavy_sections,
            output_depth="exhaustive",
            difficulty="exam_level",
        )
    )
    check(
        "3: formula-heavy preset path includes the new guidance",
        GUIDANCE_NEEDLE in heavy_preset_sys,
    )
    check(
        "3: formula-heavy preset path keeps preset first + math block last",
        heavy_preset_sys.startswith(preset_prompt)
        and heavy_preset_sys.endswith(MARKDOWN_MATH_SYSTEM),
    )

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
