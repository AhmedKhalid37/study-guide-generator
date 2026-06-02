"""Unit tests for pipeline/markdown_sections.py.

Covers the four mandatory edge cases plus splice correctness and
the outline compliance checker.

    python test_scripts/test_markdown_sections.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.markdown_sections import (
    check_outline_compliance,
    normalize_heading,
    parse_sections,
    splice_section,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        msg = f"[FAIL] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


# ── 1. Preamble before first heading ────────────────────────────────────────

def test_preamble() -> None:
    md = "Preamble text.\n\n# H1\nContent under H1.\n"
    sections = parse_sections(md)
    preamble = sections[0]
    h1_sections = [s for s in sections if s.heading_level > 0]

    check("preamble/exists", len(sections) >= 2)
    check("preamble/index_0", preamble.index == 0)
    check("preamble/heading_level_0", preamble.heading_level == 0)
    check("preamble/heading_text_empty", preamble.heading_text == "")
    check("preamble/contains_text", "Preamble text." in preamble.raw_markdown)
    check("preamble/start_line_0", preamble.start_line == 0)
    check("preamble/end_line_eq_h1_start", preamble.end_line == h1_sections[0].start_line)
    check("preamble/h1_exists", h1_sections and h1_sections[0].heading_text == "H1")


# ── 2. No preamble ───────────────────────────────────────────────────────────

def test_no_preamble() -> None:
    md = "# H1\nContent.\n"
    sections = parse_sections(md)
    check("no_preamble/single_section", len(sections) == 1)
    check("no_preamble/level_1", sections[0].heading_level == 1)
    check("no_preamble/index_0", sections[0].index == 0)


# ── 3. Repeated heading titles ───────────────────────────────────────────────

def test_repeated_headings() -> None:
    md = "## Summary\nFirst summary.\n\n## Summary\nSecond summary.\n"
    sections = parse_sections(md)
    check("repeated/two_sections", len(sections) == 2, f"got {len(sections)}")
    check("repeated/both_named_summary", all(s.heading_text == "Summary" for s in sections))
    check("repeated/different_start_lines", sections[0].start_line != sections[1].start_line)
    check("repeated/first_has_first", "First summary." in sections[0].raw_markdown)
    check("repeated/second_has_second", "Second summary." in sections[1].raw_markdown)
    check("repeated/indices_differ", sections[0].index != sections[1].index)
    # No overlap: first section ends where second begins
    check("repeated/no_overlap", sections[0].end_line == sections[1].start_line)


# ── 4. ## inside fenced code block must be ignored ───────────────────────────

def test_code_block_heading_ignored() -> None:
    md = (
        "# Real Heading\n\n"
        "```python\n"
        "## Not a heading — just a comment\n"
        "x = 1\n"
        "```\n\n"
        "More content.\n"
    )
    sections = parse_sections(md)
    heading_sections = [s for s in sections if s.heading_level > 0]
    check("code_block/one_heading", len(heading_sections) == 1, f"got {len(heading_sections)}")
    check("code_block/correct_title", heading_sections[0].heading_text == "Real Heading")
    check("code_block/raw_includes_fence", "```python" in heading_sections[0].raw_markdown)
    check("code_block/raw_includes_comment", "## Not a heading" in heading_sections[0].raw_markdown)


# ── 5. Nested sub-headings ───────────────────────────────────────────────────

def test_nested_subheadings() -> None:
    md = "# H1\n\n## H2a\n\n### H3\n\n## H2b\n"
    sections = parse_sections(md)
    by_text = {s.heading_text: s for s in sections if s.heading_level > 0}

    h1 = by_text["H1"]
    h2a = by_text["H2a"]
    h3 = by_text["H3"]
    h2b = by_text["H2b"]

    # H1 spans everything
    check("nested/h1_contains_h2a", "H2a" in h1.raw_markdown)
    check("nested/h1_contains_h3", "H3" in h1.raw_markdown)
    check("nested/h1_contains_h2b", "H2b" in h1.raw_markdown)

    # H2a spans until H2b, so contains H3 but not H2b
    check("nested/h2a_contains_h3", "H3" in h2a.raw_markdown)
    check("nested/h2a_excludes_h2b", "H2b" not in h2a.raw_markdown)

    # H3 ends at H2b
    check("nested/h3_excludes_h2b", "H2b" not in h3.raw_markdown)
    check("nested/h3_level_3", h3.heading_level == 3)

    # H2b is its own section at level 2
    check("nested/h2b_level_2", h2b.heading_level == 2)
    check("nested/h2b_end_at_eof", h2b.end_line == len(md.splitlines(keepends=True)))


# ── 6. Splice — basic ────────────────────────────────────────────────────────

def test_splice_basic() -> None:
    md = "# Intro\n\nIntro content.\n\n# Conclusion\n\nConclusion content.\n"
    sections = parse_sections(md)
    conclusion = next(s for s in sections if s.heading_text == "Conclusion")
    new_content = "# Conclusion\n\nNew conclusion text.\n"
    result = splice_section(md, conclusion, new_content)
    check("splice_basic/new_text_present", "New conclusion text." in result)
    check("splice_basic/old_text_gone", "Conclusion content." not in result)
    check("splice_basic/intro_preserved", "Intro content." in result)


# ── 7. Splice with duplicate heading — the correctness test ──────────────────

def test_splice_duplicate_heading() -> None:
    md = (
        "# Guide\n\n"
        "## Summary\nFirst part.\n\n"
        "## Details\nDetails content.\n\n"
        "## Summary\nSecond part.\n"
    )
    sections = parse_sections(md)
    heading_sections = [s for s in sections if s.heading_level > 0]
    summaries = [s for s in heading_sections if s.heading_text == "Summary"]
    check("dup/two_summaries", len(summaries) == 2, f"got {len(summaries)}")

    second_summary = summaries[1]
    new_content = "## Summary\nReplaced second summary.\n"
    result = splice_section(md, second_summary, new_content)

    check("dup/new_content_present", "Replaced second summary." in result)
    check("dup/first_part_preserved", "First part." in result)
    check("dup/details_preserved", "Details content." in result)
    check("dup/old_second_gone", "Second part." not in result)

    # Confirm the SECOND occurrence was replaced (not the first)
    first_pos = result.find("## Summary")
    second_pos = result.find("## Summary", first_pos + 1)
    replaced_pos = result.find("Replaced second summary.")
    check("dup/correct_occurrence_replaced", second_pos != -1 and second_pos < replaced_pos)


# ── 8. Outline compliance checker ────────────────────────────────────────────

def test_outline_compliance() -> None:
    md = "# Guide\n\n## Introduction\n\n## Core Concepts\n\n## Practice Problems\n"
    sections = parse_sections(md)
    outline = ["Introduction", "Key Concepts", "Applications"]
    result = check_outline_compliance(outline, sections)

    check("compliance/3_results", len(result) == 3)
    check("compliance/introduction_found", result[0]["status"] == "found")
    check("compliance/key_concepts_renamed", result[1]["status"] == "renamed",
          f"got {result[1]['status']!r}, matched={result[1]['matched_heading']!r}")
    check("compliance/applications_missing", result[2]["status"] == "missing")
    check("compliance/renamed_matched_heading", result[1]["matched_heading"] == "Core Concepts")
    check("compliance/missing_heading_none", result[2]["matched_heading"] is None)


def test_compliance_no_outline_match() -> None:
    """All sections present in doc → all found."""
    md = "## Alpha\n## Beta\n## Gamma\n"
    sections = parse_sections(md)
    result = check_outline_compliance(["Alpha", "Beta", "Gamma"], sections)
    check("compliance_all_found/alpha", result[0]["status"] == "found")
    check("compliance_all_found/beta", result[1]["status"] == "found")
    check("compliance_all_found/gamma", result[2]["status"] == "found")


def test_compliance_all_missing() -> None:
    md = "## Alpha\n## Beta\n"
    sections = parse_sections(md)
    result = check_outline_compliance(["One", "Two", "Three"], sections)
    statuses = {r["status"] for r in result}
    check("compliance_all_missing/no_found", "found" not in statuses)


# ── 9. normalize_heading ─────────────────────────────────────────────────────

def test_normalize_heading() -> None:
    check("norm/lowercase", normalize_heading("Hello World") == "hello world")
    check("norm/strip_bold", normalize_heading("**Bold** text") == "bold text")
    check("norm/strip_italic", normalize_heading("*italic* text") == "italic text")
    check("norm/strip_code", normalize_heading("`code` here") == "code here")
    check("norm/collapse_spaces", normalize_heading("  multiple   spaces  ") == "multiple spaces")
    check("norm/mixed", normalize_heading("**Key** Concepts and `formulas`") == "key concepts and formulas")


# ── 10. Edge cases ────────────────────────────────────────────────────────────

def test_empty_document() -> None:
    sections = parse_sections("")
    check("empty/is_list", isinstance(sections, list))
    check("empty/at_most_one", len(sections) <= 1)


def test_only_preamble() -> None:
    md = "Just some text with no headings.\n"
    sections = parse_sections(md)
    check("only_preamble/one_section", len(sections) == 1)
    check("only_preamble/level_0", sections[0].heading_level == 0)
    check("only_preamble/has_text", "Just some text" in sections[0].raw_markdown)


def test_deeply_nested() -> None:
    md = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6\n"
    sections = parse_sections(md)
    heading_sections = [s for s in sections if s.heading_level > 0]
    check("deep/6_sections", len(heading_sections) == 6, f"got {len(heading_sections)}")
    levels = [s.heading_level for s in heading_sections]
    check("deep/levels_1_to_6", levels == [1, 2, 3, 4, 5, 6])
    # H1 must span everything
    h1 = heading_sections[0]
    check("deep/h1_spans_all", "H6" in h1.raw_markdown)


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_preamble()
    test_no_preamble()
    test_repeated_headings()
    test_code_block_heading_ignored()
    test_nested_subheadings()
    test_splice_basic()
    test_splice_duplicate_heading()
    test_outline_compliance()
    test_compliance_no_outline_match()
    test_compliance_all_missing()
    test_normalize_heading()
    test_empty_document()
    test_only_preamble()
    test_deeply_nested()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"Parser edge-case tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
