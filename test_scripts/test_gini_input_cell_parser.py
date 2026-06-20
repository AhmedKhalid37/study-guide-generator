"""Tests for the Slice 176J Gini input-cell parser (pure, public-safe synthetic).

All fixtures here are SYNTHETIC OCR-like structures (made-up class-count grids and
answer-summary shapes) — never the private 176I artifact, never real source values.
They prove the parser's no-laundering guards: genuine column-aligned class-count rows
parse + masked-recompute; a Gini answer column is refused as answer-output-only;
scattered integers are rejected as false positives; an available expected answer
blocks record creation; a missing artifact is an honest hard blocker.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.gini_input_cell_parser import (
    extract_layout_tables_from_html,
    parse_gini_input_cells,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


# Closed-vocab keys that must never carry a raw value.
_CLOSED_RAW_FLAGS = ("raw_ocr_committed", "raw_table_text_committed", "raw_values_committed")


def test_raw_class_count_grid_parses_and_masked_recomputes() -> None:
    # Synthetic per-node class-count grid: label + two class-count columns x 3 nodes.
    tables = [
        [
            ["node", "class_a", "class_b"],
            ["left", "30", "10"],
            ["mid", "5", "25"],
            ["right", "12", "8"],
        ]
    ]
    out = parse_gini_input_cells(
        selected_target_id="gini_chest_pain", layout_tables=tables
    )
    rec = out["record"]
    _check("raw grid -> status parsed", rec["status"] == "parsed")
    _check("raw grid -> candidate raw_class_count_inputs", rec["candidate_kind"] == "raw_class_count_inputs")
    _check("raw grid -> column alignment passed", rec["column_alignment_status"] == "passed")
    _check("raw grid -> source record created", rec["source_input_record_status"] == "created")
    _check("raw grid -> machine consumable", rec["machine_consumable_for_recompute"] is True)
    _check("raw grid -> masked recompute passed", rec["masked_recompute_status"] == "passed")
    _check("raw grid -> origin ocr_from_rendered_slide", rec["source_input_origin"] == "ocr_from_rendered_slide")
    _check("raw grid -> next wire into recompute", rec["recommended_next_step"] == "wire_ocr_inputs_into_recompute")
    _check("raw grid -> recompute_input present", isinstance(out["recompute_input"], dict))
    _check("raw grid -> no raw flags true", all(rec[k] is False for k in _CLOSED_RAW_FLAGS))


def test_answer_summary_table_refused_as_answer_output_only() -> None:
    # Synthetic per-split ANSWER summary: one count column + one Gini-value column.
    tables = [
        [
            ["feature", "split", "count", "side", "gini"],
            ["chest_pain", "yes", "40", "left", "0.42"],
            ["chest_pain", "no", "30", "left", "0.37"],
            ["chol", "yes", "25", "right", "0.18"],
            ["chol", "no", "15", "right", "0.49"],
        ]
    ]
    out = parse_gini_input_cells(
        selected_target_id="gini_chest_pain", layout_tables=tables
    )
    rec = out["record"]
    _check("answer table -> status blocked", rec["status"] == "blocked")
    _check("answer table -> candidate computed_gini_answer", rec["candidate_kind"] == "computed_gini_answer")
    _check("answer table -> rejected false positive", rec["input_cell_candidate_status"] == "rejected_false_positive")
    _check("answer table -> false_positive_rejected true", rec["false_positive_rejected"] is True)
    _check("answer table -> answer agnostic guard passed", rec["answer_agnostic_guard_status"] == "passed")
    _check("answer table -> blocked_by answer_output_only", rec["blocked_by"] == "answer_output_only")
    _check("answer table -> no source record", rec["source_input_record_status"] == "not_created")
    _check("answer table -> masked recompute not_run", rec["masked_recompute_status"] == "not_run")
    _check("answer table -> next pivot_to_visible_table_pilot", rec["recommended_next_step"] == "pivot_to_visible_table_pilot")
    _check("answer table -> recompute_input None", out["recompute_input"] is None)


def test_unrelated_integers_rejected_false_positive() -> None:
    # Scattered single integers on unrelated lines (no >= 2 shared integer columns).
    tables = [
        [
            ["slide", "page"],
            ["intro", "1"],
            ["agenda", "2"],
            ["summary", "9"],
        ]
    ]
    out = parse_gini_input_cells(
        selected_target_id="gini_chest_pain", layout_tables=tables
    )
    rec = out["record"]
    _check("unrelated ints -> blocked", rec["status"] == "blocked")
    _check("unrelated ints -> candidate unrelated_integers", rec["candidate_kind"] == "unrelated_integers")
    _check("unrelated ints -> rejected false positive", rec["input_cell_candidate_status"] == "rejected_false_positive")
    _check("unrelated ints -> column alignment failed", rec["column_alignment_status"] == "failed")
    _check("unrelated ints -> blocked_by false_positive_guard", rec["blocked_by"] == "false_positive_guard")
    _check("unrelated ints -> no source record", rec["source_input_record_status"] == "not_created")


def test_expected_answer_available_blocks_record() -> None:
    # Even a genuine grid must NOT create a record if the answer is available.
    tables = [
        [
            ["node", "a", "b"],
            ["l", "30", "10"],
            ["r", "5", "25"],
        ]
    ]
    out = parse_gini_input_cells(
        selected_target_id="gini_chest_pain",
        layout_tables=tables,
        expected_answer_available=True,
    )
    rec = out["record"]
    _check("answer-available -> blocked", rec["status"] == "blocked")
    _check("answer-available -> guard failed", rec["answer_agnostic_guard_status"] == "failed")
    _check("answer-available -> no record", rec["source_input_record_status"] == "not_created")
    _check("answer-available -> recompute_input None", out["recompute_input"] is None)


def test_missing_artifact_is_hard_blocker() -> None:
    out = parse_gini_input_cells(
        selected_target_id="gini_chest_pain",
        layout_tables=None,
        private_artifact_available=False,
        private_artifact_gitignored=False,
    )
    rec = out["record"]
    _check("missing -> blocked", rec["status"] == "blocked")
    _check("missing -> warning private_artifact_missing", rec["warning"] == "private_artifact_missing")
    _check("missing -> blocked_by private_artifact_missing", rec["blocked_by"] == "private_artifact_missing")
    _check("missing -> origin none", rec["input_cell_candidate_origin"] == "none")


def test_unsupported_family_is_skipped() -> None:
    out = parse_gini_input_cells(
        selected_target_id="proximity_4_3",
        target_family="proximity",
        layout_tables=[[["a", "b"], ["1", "2"]]],
    )
    rec = out["record"]
    _check("unsupported -> skipped", rec["status"] == "skipped")
    _check("unsupported -> family unknown", rec["selected_target_family"] == "unknown")
    _check("unsupported -> blocked_by unsupported_method", rec["blocked_by"] == "unsupported_method")
    _check("unsupported -> masked not_supported", rec["masked_recompute_status"] == "not_supported")


def test_html_extraction_strips_tags() -> None:
    html = (
        "<table><tr><th>node</th><th>a</th><th>b</th></tr>"
        "<tr><td>l</td><td>30</td><td>10</td></tr>"
        "<tr><td>r</td><td>5</td><td>25</td></tr></table>"
    )
    grids = extract_layout_tables_from_html(html)
    _check("html -> one table", len(grids) == 1)
    _check("html -> three rows", len(grids[0]) == 3)
    _check("html -> stripped cells", grids[0][1] == ["l", "30", "10"])
    out = parse_gini_input_cells(selected_target_id="gini_chest_pain", layout_tables=grids)
    _check("html grid -> parses", out["record"]["status"] == "parsed")


def test_record_is_closed_vocab_only() -> None:
    # No record field may carry a non-token / value-like payload.
    out = parse_gini_input_cells(
        selected_target_id="gini_chest_pain",
        layout_tables=[[["node", "a", "b"], ["l", "30", "10"], ["r", "5", "25"]]],
    )
    rec = out["record"]
    ok = True
    for key, value in rec.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, str):
            # closed tokens are short kebab/snake identifiers, never digits-bearing values
            if any(ch.isdigit() for ch in value):
                ok = False
        elif not isinstance(value, (str, bool)):
            ok = False
    _check("record -> closed vocab only (no values)", ok)


def main() -> int:
    print("test_gini_input_cell_parser:")
    test_raw_class_count_grid_parses_and_masked_recomputes()
    test_answer_summary_table_refused_as_answer_output_only()
    test_unrelated_integers_rejected_false_positive()
    test_expected_answer_available_blocks_record()
    test_missing_artifact_is_hard_blocker()
    test_unsupported_family_is_skipped()
    test_html_extraction_strips_tags()
    test_record_is_closed_vocab_only()
    if _FAILURES:
        print(f"test_gini_input_cell_parser: FAILED ({len(_FAILURES)})")
        return 1
    print("test_gini_input_cell_parser: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
