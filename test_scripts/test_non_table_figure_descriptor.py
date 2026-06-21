"""Public-safe tests for Slice 176Z non-table figure descriptor production."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.non_table_figure_descriptor import (  # noqa: E402
    build_closed_summary,
    run_non_table_figure_descriptor,
    select_non_table_candidate,
)

_FAILURES: list[str] = []
_RAW_CANARY = "RAW_SYNTHETIC_PRIVATE_CONTEXT_CANARY"


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


def _touch_private_asset(tmp: str) -> str:
    path = Path(tmp) / "asset.png"
    path.write_text("synthetic", encoding="utf-8")
    return str(path)


def _diagram_candidate(asset_path: str) -> dict:
    return {
        "candidate_source": "synthetic_fixture",
        "candidate_scan_mode": "synthetic_fixture",
        "asset_category": "decision_tree_diagram",
        "asset_kind": "decision_tree_diagram",
        "visual_type": "decision_tree_diagram",
        "diagram_nodes": ["root", "branch", "leaf"],
        "diagram_edges": [{"from": "root", "to": "branch"}, {"from": "branch", "to": "leaf"}],
        "_private_visual_crop_path": asset_path,
        "_private_context_text": _RAW_CANARY,
    }


def _chart_candidate(asset_path: str) -> dict:
    return {
        "candidate_source": "synthetic_fixture",
        "candidate_scan_mode": "synthetic_fixture",
        "asset_category": "chart",
        "asset_kind": "chart",
        "visual_type": "chart",
        "chart_series": [{"label": "series", "points": [1, 2, 3]}],
        "_private_visual_crop_path": asset_path,
        "_private_context_text": _RAW_CANARY,
    }


def test_accepts_synthetic_non_table_diagram_descriptor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        selected = select_non_table_candidate([_diagram_candidate(_touch_private_asset(tmp))])
    _check("diagram selected", selected is not None)
    _check("diagram category", selected and selected["asset_category"] == "decision_tree_diagram")


def test_accepts_synthetic_chart_descriptor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        selected = select_non_table_candidate([_chart_candidate(_touch_private_asset(tmp))])
    _check("chart selected", selected is not None)
    _check("chart category", selected and selected["asset_category"] == "chart")


def test_rejects_text_only_private_crop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        candidate = _diagram_candidate(_touch_private_asset(tmp))
        candidate.pop("diagram_nodes", None)
        candidate.pop("diagram_edges", None)
        candidate["visual_is_text_only"] = True
        selected = select_non_table_candidate([candidate])
    _check("text-only crop rejected", selected is None)


def test_rejects_wrong_source_label() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        candidate = _diagram_candidate(_touch_private_asset(tmp))
        candidate["visual_source_matches_label"] = False
        selected = select_non_table_candidate([candidate])
    _check("wrong source rejected", selected is None)


def test_rejects_partial_visual_sliver() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        candidate = _diagram_candidate(_touch_private_asset(tmp))
        candidate["visual_is_partial_sliver"] = True
        selected = select_non_table_candidate([candidate])
    _check("partial sliver rejected", selected is None)


def test_rejects_table() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        candidate = _diagram_candidate(_touch_private_asset(tmp))
        candidate["asset_category"] = "table"
        candidate["table_markdown"] = ["| a | b |"]
        selected = select_non_table_candidate([candidate])
    _check("table rejected", selected is None)


def test_rejects_matrix_or_proximity_matrix() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        candidate = _diagram_candidate(_touch_private_asset(tmp))
        candidate["asset_category"] = "proximity_matrix"
        selected = select_non_table_candidate([candidate])
    _check("matrix rejected", selected is None)


def test_rejects_grid_table_like_visual() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        candidate = _diagram_candidate(_touch_private_asset(tmp))
        candidate["asset_category"] = "structured_grid"
        candidate["max_table_rows"] = 3
        candidate["max_table_cols"] = 3
        selected = select_non_table_candidate([candidate])
    _check("grid rejected", selected is None)


def test_rejects_unsafe_private_path_in_committed_summary() -> None:
    summary = build_closed_summary(
        status="completed",
        candidate_source="/tmp/private",
        candidate_scan_mode="synthetic_fixture",
        selected_asset_category="chart",
        selected_asset_kind="chart",
        descriptor_written=True,
        descriptor_gitignored=True,
        private_visual_asset_available=True,
        private_visual_asset_gitignored=True,
        visual_is_non_table_figure=True,
        visual_type_closed="chart",
    )
    blob = json.dumps(summary)
    _check("unsafe path summary rejected", "/tmp/private" not in blob and summary["candidate_source"] == "none")


def test_blocks_when_no_eligible_non_table_visual_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_non_table_figure_descriptor(private_descriptor_dir=tmp, inventory_roots=[])
    _check("blocked", summary["status"] == "blocked")
    _check("no descriptor", summary["descriptor_written"] is False)
    _check("operator blocker", summary["blocked_by"] == "no_acceptable_non_table_figure_crop_after_operator_review")
    _check("next improves selector", summary["recommended_next_step"] == "improve_non_table_visual_crop_selection")


def test_writes_private_descriptor_only_under_ignored_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = {
            "source_label": "ensemble",
            "assets": [_diagram_candidate(_touch_private_asset(tmp))],
        }
        visible = Path(tmp) / "visible_table_figure_pilot.json"
        visible.write_text(json.dumps(payload), encoding="utf-8")
        out_dir = Path(tmp) / "descriptor"
        summary = run_non_table_figure_descriptor(
            private_descriptor_dir=str(out_dir),
            private_visible_artifact=str(visible),
            inventory_roots=[],
        )
        descriptor = out_dir / "non_table_figure_descriptor.json"
        closed = out_dir / "closed_non_table_figure_descriptor_summary.json"
        descriptor_written = descriptor.is_file()
        closed_written = closed.is_file()
        summary_copy = dict(summary)
    _check("completed", summary_copy["status"] == "completed", str(summary_copy))
    _check("descriptor written privately", descriptor_written)
    _check("closed summary written privately", closed_written)
    _check("descriptor gitignored", summary_copy["descriptor_gitignored"] is True)
    _check("visual available", summary_copy["private_visual_asset_available"] is True)
    _check("operator rejection reason recorded", summary_copy["operator_rejected_previous_crop_reason"] == "text_only_or_wrong_source")
    _check("target visual type recorded", summary_copy["operator_target_visual_type"] == "ensemble_structure_diagram")
    _check("source match recorded", summary_copy["visual_source_matches_label"] is True)
    _check("text-only false recorded", summary_copy["visual_is_text_only"] is False)


def test_closed_summary_contains_no_raw_private_content() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = {"source_label": "ensemble", "assets": [_chart_candidate(_touch_private_asset(tmp))]}
        visible = Path(tmp) / "visible_table_figure_pilot.json"
        visible.write_text(json.dumps(payload), encoding="utf-8")
        summary = run_non_table_figure_descriptor(
            private_descriptor_dir=str(Path(tmp) / "descriptor"),
            private_visible_artifact=str(visible),
            inventory_roots=[],
        )
    blob = json.dumps(summary)
    _check("summary excludes raw canary", _RAW_CANARY not in blob)
    _check("summary excludes temp path", tmp not in blob)
    _check("summary excludes data uri", "data:image" not in blob)
    _check("summary excludes base64", "base64" not in blob.lower())
    _check("summary excludes provider payload", "provider_payload" not in blob)


def main() -> int:
    print("test_non_table_figure_descriptor:")
    test_accepts_synthetic_non_table_diagram_descriptor()
    test_accepts_synthetic_chart_descriptor()
    test_rejects_text_only_private_crop()
    test_rejects_wrong_source_label()
    test_rejects_partial_visual_sliver()
    test_rejects_table()
    test_rejects_matrix_or_proximity_matrix()
    test_rejects_grid_table_like_visual()
    test_rejects_unsafe_private_path_in_committed_summary()
    test_blocks_when_no_eligible_non_table_visual_exists()
    test_writes_private_descriptor_only_under_ignored_output()
    test_closed_summary_contains_no_raw_private_content()
    if _FAILURES:
        print(f"test_non_table_figure_descriptor: FAILED ({len(_FAILURES)})")
        return 1
    print("test_non_table_figure_descriptor: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
