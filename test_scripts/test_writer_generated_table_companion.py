"""Public-safe tests for Slice 176X writer-generated table companion.

These tests never call a provider — a synthetic ``writer`` callable is injected. They
use only public-safe synthetic descriptors and synthetic writer outputs, and assert
that the closed summary never carries raw table/explanation/simplified/prompt/response
text or any private path.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.writer_generated_table_companion as wgtc  # noqa: E402
from pipeline.llm_client import MissingLLMConfigError  # noqa: E402
from pipeline.writer_generated_table_companion import (  # noqa: E402
    WRITER_TOKEN,
    detect_simplified_table_shape,
    detect_table_role,
    is_placeholder_text,
    parse_writer_output,
    run_writer_generated_table_companion,
)

_FAILURES: list[str] = []

_RAW_TABLE_CANARY = "RAW_SYNTHETIC_TABLE_CELL_CANARY"
_RAW_EXPL_CANARY = "RAW_SYNTHETIC_EXPLANATION_CANARY_PROSE"
_RAW_SIMPL_CANARY = "RAW_SYNTHETIC_SIMPLIFIED_CELL_CANARY"
_RAW_PROMPT_CANARY = "RAW_SYNTHETIC_PROMPT_CANARY"


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


def _faithful_table() -> str:
    return (
        f"| age | outcome | extra |\n| --- | --- | --- |\n"
        f"| {_RAW_TABLE_CANARY} | yes | q |\n| 41 | no | r |"
    )


def _payload(table: str | None = None, *, category: str = "patient_dataset_table") -> dict:
    return {
        "source_label": "ensemble",
        "assets": [
            {
                "asset_category": category,
                "table_markdown": [table or _faithful_table()],
                "display_role": "student_visible_reference",
            }
        ],
    }


def _good_response() -> str:
    return (
        "Use this dataset section to study patient-level records.\n\n"
        f"{WRITER_TOKEN}\n\n"
        "## What this table shows\n\n"
        "This table lists each patient alongside the recorded study outcome, teaching "
        "learners how patient-level variables map to a clinical result and how to read a "
        f"dataset row by row. {_RAW_EXPL_CANARY}\n\n"
        "## Simplified study table\n\n"
        "| Pattern / thing to notice | Meaning | Exam takeaway |\n| --- | --- | --- |\n"
        f"| Age and outcome are read together | Age helps describe the patient while outcome records the result. {_RAW_SIMPL_CANARY} | Link variables to the result before comparing patients. |\n"
        "| Extra field is supporting context | Extra notes can add context, but the outcome is the main result column. | Focus on the result column when answering dataset questions. |\n"
    )


def _writer_returning(text: str):
    def _writer(messages):
        # Prove the descriptor reached the writer without leaking it into the summary.
        assert isinstance(messages, list) and messages
        return text
    return _writer


def _run(
    text: str,
    tmp: str,
    render_html: bool = True,
    *,
    payload: dict | None = None,
) -> dict:
    return run_writer_generated_table_companion(
        visible_payload_override=payload or _payload(),
        private_companion_dir=str(Path(tmp) / "companion"),
        writer=_writer_returning(text),
        render_html=render_html,
    )


def test_one_token_completes_and_renders() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_good_response(), tmp)
        html_path = Path(tmp) / "companion" / "writer_generated_table_companion_guide.html"
        html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    _check("status completed", summary["status"] == "completed", str(summary))
    _check("provider call made", summary["provider_call_made"] is True)
    _check("generation rerun", summary["generation_rerun"] is True)
    _check("generation behavior changed", summary["generation_behavior_changed"] is True)
    _check("slice 176X", summary["slice"] == "176X")
    _check("writer token count one", summary["writer_token_count"] == "1")
    _check("token inserted by writer", summary["writer_token_inserted_by_writer"] is True)
    _check("postprocessor did not inject", summary["postprocessor_token_injected"] is False)
    _check("faithful present", summary["faithful_table_present"] is True)
    _check("explanation writer-generated", summary["explanation_source"] == "writer_generated_from_descriptor")
    _check("explanation non placeholder", summary["explanation_non_placeholder"] is True)
    _check("simplified writer-generated", summary["simplified_table_source"] == "writer_generated_from_descriptor")
    _check("simplified non placeholder", summary["simplified_table_non_placeholder"] is True)
    _check("simplified policy role-aware", summary["simplified_table_policy"] == "role_aware_study_simplification")
    _check("table role dataset", summary["detected_or_requested_table_role"] == "dataset_numeric")
    _check("dataset shape", summary["simplified_table_shape"] == "dataset_patterns_takeaways")
    _check("not row-reduced copy", summary["simplified_table_is_row_reduced_copy"] is False)
    _check("study oriented", summary["simplified_table_is_study_oriented"] is True)
    _check("preserves key meaning", summary["simplified_table_preserves_key_meaning"] is True)
    _check("render html rendered", summary["render_format"] == "html" and summary["render_status"] == "rendered")
    _check("private guide written", summary["private_rendered_guide_written"] is True)
    _check("private guide gitignored", summary["private_rendered_guide_gitignored"] is True)
    _check("operator read required", summary["operator_private_read_required"] is True)
    _check("operator read not done", summary["operator_private_read_done"] is False)
    _check("visibility operator_pending", summary["faithful_table_visibility_status"] == "operator_pending")
    # Faithful table resolved as a real HTML table, never an image, token gone.
    _check("html has >=2 tables", html.count("<table") >= 2, f"tables={html.count('<table')}")
    _check("html has no image", "<img" not in html and "data:image" not in html)
    _check("token resolved away in html", WRITER_TOKEN not in html)


def test_missing_token_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run("## What this table shows\n\nNo token here at all in this prose body.", tmp)
    _check("missing token blocks", summary["status"] == "blocked")
    _check("missing token blocker", summary["blocked_by"] == "writer_token_missing")
    _check("missing token present false", summary["writer_token_present"] is False)
    _check("missing token inserted false", summary["writer_token_inserted_by_writer"] is False)
    _check("missing token not rendered", summary["private_rendered_guide_written"] is False)


def test_duplicate_token_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        text = f"{WRITER_TOKEN}\n\nsome prose\n\n{WRITER_TOKEN}\n"
        summary = _run(text, tmp)
    _check("duplicate token blocks", summary["status"] == "blocked")
    _check("duplicate token blocker", summary["blocked_by"] == "writer_token_duplicate")
    _check("duplicate token count many", summary["writer_token_count"] == "many")


def test_postprocessor_never_injects_token() -> None:
    # When the writer omits the token, nothing downstream may add it.
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run("Plain study prose with no placeholder marker whatsoever here.", tmp)
        guide = Path(tmp) / "companion" / "writer_generated_table_companion_guide.md"
        wrote_guide = guide.is_file()
    _check("no token -> not rendered", wrote_guide is False)
    _check("postprocessor_token_injected always false", summary["postprocessor_token_injected"] is False)
    _check("no token -> token absent in summary blob", WRITER_TOKEN not in json.dumps(summary))


def test_placeholder_explanation_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        text = (
            f"{WRITER_TOKEN}\n\n## What this table shows\n\nTODO\n\n"
            "## Simplified study table\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
        )
        summary = _run(text, tmp)
    _check("placeholder explanation blocks", summary["status"] == "blocked", str(summary))
    _check("placeholder explanation blocker", summary["blocked_by"] == "placeholder_content_detected")
    _check("placeholder explanation non_placeholder false", summary["explanation_non_placeholder"] is False)


def test_simplified_identical_to_faithful_blocks() -> None:
    # A writer "simplified" table that merely copies the faithful table is not a real
    # writer-generated simplified version, so the slice cannot complete on it.
    with tempfile.TemporaryDirectory() as tmp:
        text = (
            f"{WRITER_TOKEN}\n\n## What this table shows\n\n"
            "This table records each patient and the recorded outcome so a learner can "
            "study how the variables relate across the cohort in detail.\n\n"
            "## Simplified study table\n\n" + _faithful_table() + "\n"
        )
        summary = _run(text, tmp)
    _check("copy simplified does not complete", summary["status"] != "completed", str(summary))
    _check("copy simplified non_placeholder false", summary["simplified_table_non_placeholder"] is False)
    _check("copy simplified row-copy true", summary["simplified_table_is_row_reduced_copy"] is True)


def test_placeholder_simplified_table_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        text = (
            f"{WRITER_TOKEN}\n\n## What this table shows\n\n"
            "This table records patient variables and outcomes so learners can connect "
            "dataset fields to the result column during study.\n\n"
            "## Simplified study table\n\n"
            "| Pattern / thing to notice | Meaning | Exam takeaway |\n| --- | --- | --- |\n"
            "| TODO | TODO | TODO |\n"
        )
        summary = _run(text, tmp)
    _check("placeholder simplified blocks", summary["status"] == "blocked", str(summary))
    _check("placeholder simplified blocker", summary["blocked_by"] == "placeholder_content_detected")
    _check("placeholder simplified non_placeholder false", summary["simplified_table_non_placeholder"] is False)


def test_dataset_numeric_table_contract_blocks_column_trimmed_copy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        text = (
            f"{WRITER_TOKEN}\n\n## What this table shows\n\n"
            "This table records patient-level variables alongside an outcome so learners "
            "can practice reading rows and linking variables to results.\n\n"
            "## Simplified study table\n\n"
            "| age | outcome |\n| --- | --- |\n"
            f"| {_RAW_TABLE_CANARY} | yes |\n| 41 | no |\n"
        )
        summary = _run(text, tmp)
    _check("column-trimmed copy blocks", summary["status"] == "blocked", str(summary))
    _check("column-trimmed copy detected", summary["simplified_table_is_row_reduced_copy"] is True)
    _check("column-trimmed shape unknown", summary["simplified_table_shape"] == "unknown")


def test_terminology_definition_table_contract() -> None:
    faithful = (
        "| Term | Definition | Example |\n| --- | --- | --- |\n"
        "| Sensitivity | Finds true positives | Screening |\n"
        "| Specificity | Finds true negatives | Confirmation |\n"
    )
    response = (
        f"{WRITER_TOKEN}\n\n## What this table shows\n\n"
        "This table defines diagnostic terms and shows why each term matters when students "
        "interpret test performance questions.\n\n"
        "## Simplified study table\n\n"
        "| Term or concept | Simple meaning | What to remember / exam clue |\n| --- | --- | --- |\n"
        "| Sensitivity | Catches people who truly have the condition. | Use it to remember true positives and screening. |\n"
        "| Specificity | Rules out people who truly do not have the condition. | Use it to remember true negatives and confirmation. |\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(response, tmp, payload=_payload(faithful, category="proximity_matrix"))
        html_path = Path(tmp) / "companion" / "writer_generated_table_companion_guide.html"
        html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    _check("terminology role detected", detect_table_role(faithful) == "terminology_definition")
    _check("terminology completes", summary["status"] == "completed", str(summary))
    _check("terminology summary role", summary["detected_or_requested_table_role"] == "terminology_definition")
    _check("terminology simplified shape", summary["simplified_table_shape"] == "terminology_study_cues")
    _check("terminology not smaller duplicate", summary["simplified_table_is_row_reduced_copy"] is False)
    _check("terminology faithful rendered", "Sensitivity" in html and "Specificity" in html)


def test_comparison_table_contract() -> None:
    faithful = (
        "| Difference | Option A | Option B |\n| --- | --- | --- |\n"
        "| Timing | Before exposure | After exposure |\n"
        "| Main use | Prevention | Treatment |\n"
    )
    response = (
        f"{WRITER_TOKEN}\n\n## What this table shows\n\n"
        "This table compares two options so learners can separate when each one is used "
        "and avoid mixing up timing questions.\n\n"
        "## Simplified study table\n\n"
        "| Item | Main difference | When it matters / common mistake |\n| --- | --- | --- |\n"
        "| Option A | Used before exposure. | Choose it for prevention, not treatment. |\n"
        "| Option B | Used after exposure. | Choose it for treatment timing questions. |\n"
    )
    parsed = parse_writer_output(response, faithful_markdown=faithful, table_role="comparison")
    _check("comparison shape helper", detect_simplified_table_shape(parsed["simplified_markdown"]) == "comparison_differences_usage")
    _check("comparison parse real", parsed["simplified_real"] is True, str(parsed))
    _check("comparison study oriented", parsed["simplified_table_is_study_oriented"] is True)


def test_completion_requires_writer_source() -> None:
    # This slice's completion is writer-sourced ONLY: no operator/deterministic source.
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_good_response(), tmp)
    blob = json.dumps(summary)
    _check("explanation source is writer-generated", summary["explanation_source"] == "writer_generated_from_descriptor")
    _check("no deterministic source label leaked", "deterministic_private_transform" not in blob)
    _check("no operator-file source label leaked", "private_operator_file" not in blob)
    _check("module has no operator-explanation env", "PRIVATE_TABLE_EXPLANATION_MD" not in _module_source())


def test_provider_unavailable_blocks_honestly() -> None:
    def _missing(messages):
        raise MissingLLMConfigError("Missing DEEPSEEK_API_KEY.")

    def _api_error(messages):
        raise RuntimeError("upstream 500 from provider")

    with tempfile.TemporaryDirectory() as tmp:
        miss = run_writer_generated_table_companion(
            visible_payload_override=_payload(),
            private_companion_dir=str(Path(tmp) / "c1"),
            writer=_missing,
        )
        err = run_writer_generated_table_companion(
            visible_payload_override=_payload(),
            private_companion_dir=str(Path(tmp) / "c2"),
            writer=_api_error,
        )
    _check("config-missing blocks", miss["status"] == "blocked")
    _check("config-missing blocker", miss["blocked_by"] == "provider_unavailable")
    _check("config-missing no provider call", miss["provider_call_made"] is False)
    _check("api-error blocks", err["status"] == "blocked")
    _check("api-error blocker", err["blocked_by"] == "writer_generation_unavailable")
    _check("api-error no provider call", err["provider_call_made"] is False)


def test_missing_artifact_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_writer_generated_table_companion(
            visible_payload_override={"source_label": "ensemble", "assets": []},
            private_companion_dir=str(Path(tmp) / "c"),
            writer=_writer_returning(_good_response()),
        )
    _check("no artifact blocks", summary["status"] == "blocked")
    _check("no artifact blocker", summary["blocked_by"] == "private_artifact_missing")


def test_unsafe_private_path_refused() -> None:
    summary = run_writer_generated_table_companion(
        visible_payload_override=_payload(),
        private_companion_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "not_private"),
        writer=_writer_returning(_good_response()),
    )
    _check("unsafe path blocks", summary["status"] == "blocked")
    _check("unsafe path blocker", summary["blocked_by"] == "unsafe_private_artifact_path")


def test_closed_summary_no_leak() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_good_response(), tmp)
        blob = json.dumps(summary)
        for canary in (_RAW_TABLE_CANARY, _RAW_EXPL_CANARY, _RAW_SIMPL_CANARY, _RAW_PROMPT_CANARY):
            _check(f"canary absent: {canary}", canary not in blob)
        # No private path / tempdir leaks, no token, no raw markdown pipes-as-table.
        _check("no tempdir path leaked", tmp not in blob)
        _check("no token leaked", WRITER_TOKEN not in blob)
        _check("no markdown table row leaked", "| age | outcome |" not in blob)
        # Every string value is a closed label/path-free token.
        bad = [
            (k, v) for k, v in summary.items()
            if isinstance(v, str) and ("/" in v or "\\" in v or v.endswith(".md") or v.endswith(".json"))
        ]
        _check("no path-like string values", not bad, str(bad))


def test_parse_helper_contract() -> None:
    parsed = parse_writer_output(_good_response(), faithful_markdown=_faithful_table())
    _check("parse one token", parsed["token_count"] == 1)
    _check("parse explanation real", parsed["explanation_real"] is True)
    _check("parse simplified real", parsed["simplified_real"] is True)
    _check("placeholder detector", is_placeholder_text("TODO"))
    _check("short text placeholder", is_placeholder_text("n/a"))
    _check("real prose not placeholder", not is_placeholder_text(
        "This dataset shows patient age and outcome for study comparison across the cohort."))


def _module_source() -> str:
    return Path(wgtc.__file__).read_text(encoding="utf-8")


def main() -> None:
    test_one_token_completes_and_renders()
    test_missing_token_blocks()
    test_duplicate_token_blocks()
    test_postprocessor_never_injects_token()
    test_placeholder_explanation_blocks()
    test_simplified_identical_to_faithful_blocks()
    test_placeholder_simplified_table_blocks()
    test_dataset_numeric_table_contract_blocks_column_trimmed_copy()
    test_terminology_definition_table_contract()
    test_comparison_table_contract()
    test_completion_requires_writer_source()
    test_provider_unavailable_blocks_honestly()
    test_missing_artifact_blocks()
    test_unsafe_private_path_refused()
    test_closed_summary_no_leak()
    test_parse_helper_contract()
    if _FAILURES:
        print("\nFAILURES: " + ", ".join(_FAILURES))
        raise SystemExit(1)
    print("\nAll writer-generated table companion tests passed.")


if __name__ == "__main__":
    main()
