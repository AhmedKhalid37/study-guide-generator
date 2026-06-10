"""Unit tests for pipeline/guide_lint.py (Slice 19 pure advisory core).

Plain-Python assertion style (matches the rest of test_scripts/). Run with:

    python test_scripts/test_guide_lint.py

Covers clean guides, empty headings (incl. nested), broken tables, unbalanced
math delimiters, fenced-code safety, expected-section presence/normalization,
the KaTeX bridge (pass / error / skipped / no-crash), input immutability, and the
JSON-serializable report shape. KaTeX-dependent assertions accept either a real
render finding or a skipped-info finding so they pass with or without Node/KaTeX.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.guide_lint import GuideLintReport, lint_guide_markdown

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "guide_lint")

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


def _load(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as handle:
        return handle.read()


def _lint(text: str, **kwargs):
    """Lint without the KaTeX subprocess unless a test explicitly enables it."""
    kwargs.setdefault("run_katex", False)
    return lint_guide_markdown(text, **kwargs)


def _rules(text: str, **kwargs) -> list[str]:
    return [f.rule for f in _lint(text, **kwargs).findings]


def _by_rule(report, rule: str) -> list:
    return [f for f in report.findings if f.rule == rule]


# ── Clean guide ───────────────────────────────────────────────────────────────

def test_clean_guide() -> None:
    report = _lint(_load("clean_guide.md"), source_name="clean_guide.md")
    check("clean/no-findings", report.summary["total"] == 0, str(report.summary))
    check("clean/no-error", report.summary["error"] == 0, str(report.summary))
    check("clean/no-warning", report.summary["warning"] == 0, str(report.summary))
    check("clean/source-name", report.source_name == "clean_guide.md")


def test_clean_guide_with_katex() -> None:
    # With KaTeX enabled a clean guide must still produce no error/warning; the
    # only allowed finding is an info-level skip when Node/KaTeX is unavailable.
    report = lint_guide_markdown(_load("clean_guide.md"), run_katex=True)
    check("clean-katex/no-error", report.summary["error"] == 0, str(report.summary))
    check("clean-katex/no-warning", report.summary["warning"] == 0, str(report.summary))
    only_info = all(f.severity == "info" for f in report.findings)
    check("clean-katex/only-info-if-any", only_info, str(report.summary))


# ── Empty headings ─────────────────────────────────────────────────────────────

def test_empty_headings_fixture() -> None:
    report = _lint(_load("empty_headings.md"))
    empties = _by_rule(report, "empty_heading")
    check("empty/two-flagged", len(empties) == 2, str([f.line for f in empties]))
    check("empty/all-warning", all(f.severity == "warning" for f in empties))
    excerpts = " ".join(f.excerpt for f in empties)
    check("empty/same-level-flagged", "Empty Same Level" in excerpts, excerpts)
    check("empty/trailing-flagged", "Trailing Empty" in excerpts, excerpts)
    check("empty/parent-not-flagged", "Parent Group" not in excerpts, excerpts)
    check("empty/child-not-flagged", "Child With Content" not in excerpts, excerpts)


def test_empty_heading_followed_by_heading() -> None:
    check("empty/immediate", "empty_heading" in _rules("## A\n## B\n\nbody\n"))


def test_empty_heading_whitespace_only() -> None:
    check("empty/whitespace", "empty_heading" in _rules("# Title\n\n   \n\t\n"))


def test_nested_parent_not_empty() -> None:
    # A parent heading whose body lives under a child heading is NOT empty.
    md = "## Parent\n### Child\n\nReal body content.\n"
    check("empty/nested-parent-ok", "empty_heading" not in _rules(md), str(_rules(md)))


def test_heading_with_body_not_empty() -> None:
    for label, md in {
        "paragraph": "## H\n\nA paragraph.\n",
        "list": "## H\n\n- item\n",
        "table": "## H\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n",
        "code": "## H\n\n```\ncode\n```\n",
    }.items():
        check(f"non-empty/{label}", "empty_heading" not in _rules(md), md)


# ── Broken tables ──────────────────────────────────────────────────────────────

def test_broken_tables_fixture() -> None:
    report = _lint(_load("broken_tables.md"))
    rules = [f.rule for f in report.findings]
    check("table/header-sep-mismatch", "header_separator_mismatch" in rules, str(rules))
    check("table/body-mismatch", "body_row_mismatch" in rules, str(rules))
    check("table/orphan-separator", "separator_without_header" in rules, str(rules))
    check("table/malformed-separator", "malformed_separator" in rules, str(rules))
    check("table/no-error-severity", report.summary["error"] == 0, str(report.summary))


def test_valid_table_not_flagged() -> None:
    md = "| Name | Score |\n| --- | --- |\n| Ann | 90 |\n| Bob | 85 |\n"
    table_rules = {
        "header_separator_mismatch",
        "body_row_mismatch",
        "separator_without_header",
        "malformed_separator",
    }
    check("table/valid-clean", not (set(_rules(md)) & table_rules), str(_rules(md)))


def test_header_separator_mismatch() -> None:
    md = "| A | B | C |\n| --- | --- |\n"
    check("table/mismatch", "header_separator_mismatch" in _rules(md), str(_rules(md)))


def test_body_row_mismatch() -> None:
    md = "| A | B |\n| --- | --- |\n| 1 |\n"
    check("table/body", "body_row_mismatch" in _rules(md), str(_rules(md)))


# ── Math delimiters ────────────────────────────────────────────────────────────

def test_balanced_inline_math() -> None:
    check("math/balanced-inline", "unbalanced_math" not in _rules("Text $x = 1$ here.\n"))


def test_balanced_display_math() -> None:
    check("math/balanced-display", "unbalanced_math" not in _rules("$$x = 1$$\n"))


def test_unbalanced_single_dollar() -> None:
    report = _lint("This costs $5 and nothing closes it.\n")
    findings = _by_rule(report, "unbalanced_math")
    check("math/unbalanced-dollar", len(findings) == 1, str(report.summary))
    check("math/dollar-warning", findings and findings[0].severity == "warning")


def test_unbalanced_double_dollar() -> None:
    report = _lint("$$ a = b + c\n\nmore text\n")
    findings = _by_rule(report, "unbalanced_math")
    check("math/unbalanced-display", len(findings) >= 1, str(report.summary))
    check("math/display-error", any(f.severity == "error" for f in findings))


def test_unbalanced_paren_latex() -> None:
    report = _lint("Consider \\( y = mx + b with no close.\n")
    findings = _by_rule(report, "unbalanced_math")
    check("math/unbalanced-paren", len(findings) >= 1, str(report.summary))
    check("math/paren-error", any(f.severity == "error" for f in findings))


def test_unbalanced_bracket_latex() -> None:
    report = _lint("Display \\[ y = mx + b with no close.\n")
    findings = _by_rule(report, "unbalanced_math")
    check("math/unbalanced-bracket", len(findings) >= 1, str(report.summary))
    check("math/bracket-error", any(f.severity == "error" for f in findings))


def test_math_delimiters_fixture() -> None:
    report = _lint(_load("math_delimiters.md"))
    findings = _by_rule(report, "unbalanced_math")
    check("math/fixture-one-unbalanced", len(findings) == 1, str(report.summary))
    check("math/fixture-error", findings and findings[0].severity == "error")


# ── Fenced-code safety ─────────────────────────────────────────────────────────

def test_code_safety_fixture() -> None:
    report = _lint(_load("code_safety.md"))
    check("code/no-findings", report.summary["total"] == 0, str(report.to_dict()))


def test_broken_table_in_code_ignored() -> None:
    md = "# H\n\nText.\n\n```\n| A | B | C |\n| --- |\n```\n"
    rules = set(_rules(md))
    table_rules = {"header_separator_mismatch", "malformed_separator", "body_row_mismatch"}
    check("code/table-ignored", not (rules & table_rules), str(rules))


def test_unbalanced_math_in_code_ignored() -> None:
    md = "# H\n\nText.\n\n```\n$$ unbalanced\n\\( unbalanced\n```\n"
    check("code/math-ignored", "unbalanced_math" not in _rules(md), str(_rules(md)))


def test_heading_in_code_not_counted() -> None:
    md = "```\n## Not A Heading\n```\n"
    # No real heading exists, so an in-code heading must not trigger empty_heading.
    check("code/heading-ignored", "empty_heading" not in _rules(md), str(_rules(md)))


# ── Expected / required sections ───────────────────────────────────────────────

def test_expected_all_present() -> None:
    md = _load("clean_guide.md")
    report = _lint(md, expected_sections=["Concepts", "Comparison", "Formulas"])
    check("sections/all-present", _by_rule(report, "missing_section") == [], str(report.summary))


def test_expected_missing_one() -> None:
    md = _load("clean_guide.md")
    report = _lint(md, expected_sections=["Concepts", "Glossary"])
    missing = _by_rule(report, "missing_section")
    check("sections/missing-one", len(missing) == 1, str([f.excerpt for f in missing]))
    check("sections/missing-warning", missing and missing[0].severity == "warning")
    check("sections/missing-name", missing and "Glossary" in missing[0].excerpt)


def test_expected_normalization() -> None:
    md = _load("clean_guide.md")
    report = _lint(md, expected_sections=["concepts!", "  COMPARISON  ", "Formulas."])
    check("sections/normalized", _by_rule(report, "missing_section") == [], str(report.summary))


def test_expected_none_no_findings() -> None:
    md = _load("clean_guide.md")
    report = _lint(md, expected_sections=None)
    check("sections/none-arg", _by_rule(report, "missing_section") == [])


# ── KaTeX bridge ───────────────────────────────────────────────────────────────

def test_katex_valid_no_render_error() -> None:
    report = lint_guide_markdown("# H\n\nText.\n\n$x = 1$\n", run_katex=True)
    check("katex/valid-no-error", _by_rule(report, "katex_render") == [], str(report.to_dict()))
    katex_findings = _by_rule(report, "katex_render") + _by_rule(report, "katex_skipped")
    check("katex/valid-at-most-skip", len(katex_findings) <= 1, str(report.summary))


def test_katex_invalid_finding_or_skip() -> None:
    report = lint_guide_markdown("# H\n\nText.\n\n$\\frac{1}$\n", run_katex=True)
    rules = {f.rule for f in report.findings}
    check(
        "katex/invalid-flag-or-skip",
        ("katex_render" in rules) or ("katex_skipped" in rules),
        str(report.to_dict()),
    )


def test_katex_disabled_no_katex_findings() -> None:
    report = lint_guide_markdown("# H\n\nText.\n\n$\\frac{1}$\n", run_katex=False)
    rules = {f.rule for f in report.findings}
    check("katex/disabled", not ({"katex_render", "katex_skipped"} & rules), str(rules))


def test_katex_no_crash() -> None:
    try:
        lint_guide_markdown("# H\n\n$\\frac{1}$ and $$x$$ stuff\n", run_katex=True)
        ok = True
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"  raised: {exc}")
    check("katex/no-crash", ok)


# ── Safety / robustness ─────────────────────────────────────────────────────────

def test_input_not_mutated() -> None:
    md = _load("broken_tables.md")
    original = str(md)
    _lint(md, expected_sections=["Concepts"])
    check("safety/no-mutation", md == original)


def test_non_string_input() -> None:
    try:
        report = lint_guide_markdown(None, run_katex=False)  # type: ignore[arg-type]
        ok = report.summary["total"] == 0
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"  raised: {exc}")
    check("safety/non-string", ok)


def test_empty_input() -> None:
    report = lint_guide_markdown("", run_katex=False)
    check("safety/empty", report.summary["total"] == 0)


def test_report_serializable() -> None:
    report = _lint(_load("broken_tables.md"))
    as_dict = report.to_dict()
    check("json/version", as_dict.get("version") == 1)
    check("json/has-summary", set(as_dict["summary"]) == {"total", "error", "warning", "info"})
    parsed = json.loads(report.to_json())
    check("json/roundtrip", parsed == as_dict)
    if parsed["findings"]:
        finding = parsed["findings"][0]
        expected_keys = {"id", "rule", "severity", "line", "message", "excerpt"}
        check("json/finding-keys", set(finding) == expected_keys, str(finding.keys()))
        check("json/id-format", finding["id"].startswith("lint_"))


def test_report_is_dataclass() -> None:
    report = _lint("# H\n\nbody\n")
    check("type/report", isinstance(report, GuideLintReport))


if __name__ == "__main__":
    test_clean_guide()
    test_clean_guide_with_katex()
    test_empty_headings_fixture()
    test_empty_heading_followed_by_heading()
    test_empty_heading_whitespace_only()
    test_nested_parent_not_empty()
    test_heading_with_body_not_empty()
    test_broken_tables_fixture()
    test_valid_table_not_flagged()
    test_header_separator_mismatch()
    test_body_row_mismatch()
    test_balanced_inline_math()
    test_balanced_display_math()
    test_unbalanced_single_dollar()
    test_unbalanced_double_dollar()
    test_unbalanced_paren_latex()
    test_unbalanced_bracket_latex()
    test_math_delimiters_fixture()
    test_code_safety_fixture()
    test_broken_table_in_code_ignored()
    test_unbalanced_math_in_code_ignored()
    test_heading_in_code_not_counted()
    test_expected_all_present()
    test_expected_missing_one()
    test_expected_normalization()
    test_expected_none_no_findings()
    test_katex_valid_no_render_error()
    test_katex_invalid_finding_or_skip()
    test_katex_disabled_no_katex_findings()
    test_katex_no_crash()
    test_input_not_mutated()
    test_non_string_input()
    test_empty_input()
    test_report_serializable()
    test_report_is_dataclass()

    total = PASS + FAIL
    print(f"\n{'=' * 54}")
    print(f"Guide lint tests: {PASS}/{total} PASS  {FAIL} FAIL")
    sys.exit(0 if FAIL == 0 else 1)
