"""Public-safe tests for Slice 176Y writer-generated figure companion."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.llm_client import MissingLLMConfigError  # noqa: E402
from pipeline.writer_generated_figure_companion import (  # noqa: E402
    WRITER_TOKEN,
    build_descriptor_text,
    run_writer_generated_figure_companion,
)

_FAILURES: list[str] = []
_RAW_CANARY = "RAW_SYNTHETIC_PRIVATE_FIGURE_CANARY"


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


def _writer_returning(text: str):
    def _writer(messages):
        assert _RAW_CANARY in messages[-1]["content"]
        return text

    return _writer


def _good_response() -> str:
    return (
        "# Figure companion\n\n"
        f"{WRITER_TOKEN}\n\n"
        "## What this figure shows\n\n"
        "This visual organizes the recovered study relationships into a compact reference. "
        "Read the labels first, then follow the row or branch structure to connect each "
        "condition with the result it supports. It matters for exams because students "
        "must translate a visual cue into the correct interpretation before answering. "
        "A common confusion is treating every visible number as a calculation task, but "
        "this companion is for reading the displayed relationship.\n\n"
        "## How to read it\n\n"
        "1. Identify the starting label.\n2. Follow the nearby labels in order.\n"
        "3. State the exam takeaway in one sentence.\n\n"
        "## Practice seed\n\n"
        "Cover one label and self-test which relationship belongs in that blank-label slot.\n"
    )


def _image_payload(ref: str = "assets/safe_visual.png") -> dict:
    return {
        "source_label": "ensemble",
        "assets": [
            {
                "asset_category": "decision_tree_or_split_diagram",
                "asset_kind": "decision_tree_diagram",
                "display_role": "explanation_support",
                "image_asset_ref": ref,
                "descriptor_text": f"{_RAW_CANARY} descriptor label flow",
            }
        ],
    }


def _structured_payload() -> dict:
    return {
        "source_label": "ensemble",
        "assets": [
            {
                "asset_category": "decision_tree_diagram",
                "display_role": "explanation_support",
                "diagram_nodes": ["Root", "Feature A branch", "Class 1", "Feature B branch", "Class 2"],
                "diagram_edges": [
                    {"from": "Root", "to": "Feature A branch", "label": "condition A"},
                    {"from": "Feature A branch", "to": "Class 1"},
                    {"from": "Root", "to": "Feature B branch", "label": "condition B"},
                    {"from": "Feature B branch", "to": "Class 2"},
                ],
                "descriptor_text": f"{_RAW_CANARY} structured descriptor",
            }
        ],
    }


def _table_like_payload() -> dict:
    return {
        "source_label": "ensemble",
        "assets": [
            {
                "asset_category": "proximity_matrix",
                "display_role": "student_visible_reference",
                "table_json": [[["ID", "A", "B"], ["A", "1.0", "0.5"], ["B", "0.5", "1.0"]]],
            },
            {
                "asset_category": "patient_dataset_table",
                "display_role": "student_visible_reference",
                "table_markdown": ["| patient | feature |\n| --- | --- |\n| A | 1 |"],
            },
            {
                "asset_category": "decision_tree_or_split_diagram",
                "display_role": "explanation_support",
                "table_json": [[["Start", "Check"], ["Root", "Feature"]]],
            },
        ],
    }


def _run(payload: dict, text: str, tmp: str, *, writer=None) -> dict:
    return run_writer_generated_figure_companion(
        visible_payload_override=payload,
        private_companion_dir=str(Path(tmp) / "companion"),
        writer=writer or _writer_returning(text),
    )


def test_completed_image_like_asset_descriptor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_image_payload(), _good_response(), tmp)
        html_path = Path(tmp) / "companion" / "writer_generated_figure_companion_guide.html"
        html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    blob = json.dumps(summary)
    _check("image path completes", summary["status"] == "completed", str(summary))
    _check("visual inserted", summary["visual_inserted"] is True)
    _check("image insertion mode", summary["visual_insertion_mode"] == "image_asset")
    _check("category normalized", summary["selected_asset_category"] == "decision_tree_diagram")
    _check("kind normalized", summary["selected_asset_kind"] == "decision_tree_diagram")
    _check("not table-like", summary["visual_is_table_like"] is False)
    _check("not matrix", summary["visual_is_matrix"] is False)
    _check("not grid", summary["visual_is_grid"] is False)
    _check("explanation beneath", summary["explanation_beneath_asset_present"] is True)
    _check("no raw private path", "/tmp/" not in html and str(Path(tmp)) not in html)
    _check("safe relative ref in html", "assets/safe_visual.png" in html)
    _check("raw descriptor not in summary", _RAW_CANARY not in blob)
    _check("closed summary only", "descriptor label flow" not in blob)


def test_completed_structured_diagram_descriptor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_structured_payload(), _good_response(), tmp)
        html_path = Path(tmp) / "companion" / "writer_generated_figure_companion_guide.html"
        html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    _check("structured path completes", summary["status"] == "completed", str(summary))
    _check("structured mode", summary["visual_insertion_mode"] == "recreated_non_table_diagram")
    _check("recreated visual rendered", "Recreated non-table study diagram" in html and "<table" not in html)
    _check("non-table visual flag", summary["visual_is_table_like"] is False)
    _check("explanation rendered", "What this figure shows" in html)
    _check("reading steps present", summary["study_reading_steps_present"] is True)
    _check("practice seed present", summary["blank_label_practice_seed_present"] is True)


def test_missing_descriptor_blocks_honestly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_writer_generated_figure_companion(
            visible_payload_override={"source_label": "ensemble", "assets": []},
            private_companion_dir=str(Path(tmp) / "companion"),
            writer=_writer_returning(_good_response()),
        )
    _check("missing descriptor blocks", summary["status"] == "blocked")
    _check("missing descriptor blocker", summary["blocked_by"] == "no_existing_non_table_figure_descriptor")
    _check("provider not called", summary["provider_call_made"] is False)
    _check("operator read not required before render", summary["operator_private_read_required"] is False)
    _check("operator read not done before render", summary["operator_private_read_done"] is False)


def test_table_matrix_grid_assets_do_not_count_as_figure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_writer_generated_figure_companion(
            visible_payload_override=_table_like_payload(),
            private_companion_dir=str(Path(tmp) / "companion"),
            writer=_writer_returning(_good_response()),
        )
    _check("table-like payload blocks", summary["status"] == "blocked", str(summary))
    _check("non-table blocker", summary["blocked_by"] == "no_existing_non_table_figure_descriptor")
    _check("no selected category", summary["selected_asset_category"] == "none")
    _check("no selected kind", summary["selected_asset_kind"] == "unknown")
    _check("visual not inserted", summary["visual_inserted"] is False)
    _check("summary written", summary["private_run_closed_summary_written"] is True)
    _check(
        "table companion not counted",
        summary["table_like_visual_companion_status"] == "completed_but_not_counted_for_figure_gate",
    )
    _check("figure companion not produced", summary["figure_diagram_companion_status"] == "not_produced")
    _check("provider not called for table-like", summary["provider_call_made"] is False)
    _check("operator read not required for table-like block", summary["operator_private_read_required"] is False)


def test_provider_unavailable_blocks_honestly() -> None:
    def _missing(_messages):
        raise MissingLLMConfigError("missing")

    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_structured_payload(), _good_response(), tmp, writer=_missing)
    _check("provider unavailable blocks", summary["status"] == "blocked")
    _check("provider unavailable blocker", summary["blocked_by"] == "provider_unavailable")
    _check("provider call false", summary["provider_call_made"] is False)


def test_placeholder_explanation_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_structured_payload(), f"# Figure\n\n{WRITER_TOKEN}\n\nTODO", tmp)
    _check("placeholder blocks", summary["status"] == "blocked")
    _check("placeholder blocker", summary["blocked_by"] == "placeholder_content_detected")
    _check("no guide written", summary["private_rendered_guide_written"] is False)


def test_uncertainty_self_talk_blocks() -> None:
    text = (
        f"{WRITER_TOKEN}\n\n## What this figure shows\n\n"
        "I think the source is unclear, so maybe this diagram shows something, but I am "
        "not sure how students should read it for the exam."
    )
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_structured_payload(), text, tmp)
    _check("uncertainty blocks", summary["status"] == "blocked")
    _check("uncertainty blocker", summary["blocked_by"] == "placeholder_content_detected")


def test_unsafe_asset_path_refused() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_image_payload("/private/source/page.png"), _good_response(), tmp)
    _check("unsafe ref blocks", summary["status"] == "blocked")
    _check("unsafe ref blocker", summary["blocked_by"] == "unsafe_asset_reference")


def test_raw_image_data_refused() -> None:
    payload = _image_payload()
    payload["assets"][0]["image_data"] = "data:image/png;base64,AAAA"
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(payload, _good_response(), tmp)
    _check("raw data blocks", summary["status"] == "blocked")
    _check("raw data blocker", summary["blocked_by"] == "raw_image_data_refused")


def test_no_postprocessor_injection_of_explanation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_structured_payload(), f"# Figure\n\n{WRITER_TOKEN}\n", tmp)
        guide = Path(tmp) / "companion" / "writer_generated_figure_companion_guide.md"
    _check("no explanation blocks", summary["status"] == "blocked")
    _check("postprocessor did not write guide", guide.is_file() is False)
    _check("postprocessor flag false", summary["postprocessor_explanation_injected"] is False)


def test_closed_summary_no_leak_contract() -> None:
    descriptor = build_descriptor_text(_structured_payload()["assets"][0])
    with tempfile.TemporaryDirectory() as tmp:
        summary = _run(_structured_payload(), _good_response(), tmp)
    blob = json.dumps(summary)
    _check("descriptor has canary privately", _RAW_CANARY in descriptor)
    _check("summary excludes canary", _RAW_CANARY not in blob)
    _check("summary excludes token", WRITER_TOKEN not in blob)
    _check("summary excludes data image", "data:image" not in blob)
    _check("summary excludes base64 marker", "base64" not in blob.lower())


def main() -> int:
    tests = [
        test_completed_image_like_asset_descriptor,
        test_completed_structured_diagram_descriptor,
        test_missing_descriptor_blocks_honestly,
        test_table_matrix_grid_assets_do_not_count_as_figure,
        test_provider_unavailable_blocks_honestly,
        test_placeholder_explanation_blocks,
        test_uncertainty_self_talk_blocks,
        test_unsafe_asset_path_refused,
        test_raw_image_data_refused,
        test_no_postprocessor_injection_of_explanation,
        test_closed_summary_no_leak_contract,
    ]
    for test in tests:
        print(f"\n{test.__name__}")
        test()
    if _FAILURES:
        print("\nFAILURES:")
        for failure in _FAILURES:
            print(f" - {failure}")
        return 1
    print("\nAll writer-generated figure companion tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
