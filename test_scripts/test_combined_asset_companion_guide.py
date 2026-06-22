"""Public-safe tests for Slice 177B combined asset companion guide.

All fixtures are synthetic; no private artifacts, provider calls, or raw study
content are touched. Existing 176X table and 177A figure tests are validated by
their own scripts in the slice validation run.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.combined_asset_companion_guide import (  # noqa: E402
    COMBINED_GUIDE_HTML,
    COMBINED_SUMMARY_JSON,
    FIGURE_GUIDE_MD,
    FIGURE_SUMMARY_JSON,
    TABLE_GUIDE_MD,
    TABLE_SUMMARY_JSON,
    run_combined_asset_companion_guide,
)

_FAILURES: list[str] = []
_RAW_TABLE_CANARY = "RAW_SYNTHETIC_TABLE_COMPANION_CANARY"
_RAW_FIGURE_CANARY = "RAW_SYNTHETIC_FIGURE_COMPANION_CANARY"


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


# ---------------------------------------------------------------------------
# Synthetic accepted-companion fixtures
# ---------------------------------------------------------------------------

def _table_summary(*, row_reduced: bool = False) -> dict:
    return {
        "artifact_name": "writer_generated_table_companion",
        "slice": "176X",
        "status": "completed",
        "source_label": "ensemble",
        "faithful_table_present": True,
        "explanation_beneath_asset_present": True,
        "simplified_table_present": True,
        "simplified_table_non_placeholder": True,
        "simplified_table_is_study_oriented": not row_reduced,
        "simplified_table_is_row_reduced_copy": row_reduced,
    }


def _table_md(*, extra: str = "") -> str:
    return (
        f"<!-- {_RAW_TABLE_CANARY} -->\n\n"
        "| Age | Outcome |\n| --- | --- |\n| 34 | Positive |\n| 51 | Negative |\n\n"
        "## What this table shows\n\n"
        "This table records each patient's age alongside the recorded study outcome so "
        "students can connect a numeric predictor with its result. Read each row as one "
        "case and look for the trend across ages. The exam takeaway is that age tends to "
        "track with the outcome category in this dataset.\n\n"
        f"{extra}"
        "## Simplified study table\n\n"
        "| Pattern / thing to notice | Meaning | Exam takeaway |\n"
        "| --- | --- | --- |\n"
        "| Higher age | risk of the outcome rises | watch older cases |\n"
    )


def _make_table_companion(base: Path, *, row_reduced: bool = False, extra_md: str = "") -> str:
    d = base / "writer_generated_table_companion"
    d.mkdir(parents=True, exist_ok=True)
    (d / TABLE_GUIDE_MD).write_text(_table_md(extra=extra_md), encoding="utf-8")
    (d / TABLE_SUMMARY_JSON).write_text(json.dumps(_table_summary(row_reduced=row_reduced)), encoding="utf-8")
    return str(d)


def _figure_summary(**overrides) -> dict:
    summary = {
        "artifact_name": "writer_generated_figure_companion",
        "slice": "177A",
        "status": "completed",
        "source_label": "ensemble",
        "visual_type_closed": "flow_or_structure_diagram",
        "visual_inserted": True,
        "visual_is_non_table_figure": True,
        "visual_is_table_like": False,
        "visual_is_matrix": False,
        "visual_is_grid": False,
        "visual_is_text_only": False,
        "visual_is_partial_sliver": False,
        "explanation_beneath_asset_present": True,
        "study_reading_steps_present": True,
        "exam_takeaway_present": True,
    }
    summary.update(overrides)
    return summary


def _figure_md(*, image_ref: str = "assets/ensemble_structure_diagram.png", extra: str = "") -> str:
    return (
        "# Ensemble Learning Structure Diagram\n\n"
        f"<!-- {_RAW_FIGURE_CANARY} -->\n\n"
        f"![Recovered study visual]({image_ref})\n\n"
        "## What this figure shows\n\n"
        "This diagram traces how one training set fans out into several learners whose "
        "outputs feed a single combiner that produces the final model. Read it left to "
        "right and connect each learner to the shared combiner. It matters for exams "
        "because students must explain why diverse learners reduce error.\n\n"
        f"{extra}"
        "## How to read it\n\n"
        "1. Start at the training data block.\n2. Follow each arrow to a learner.\n"
        "3. Trace the learner outputs into the combiner and final model.\n\n"
        "## Exam takeaway\n\n"
        "Remember the combiner aggregates multiple learners into one stronger final model.\n\n"
        "## Practice seed\n\n"
        "Cover the combiner label and self-test which stage merges the learner outputs.\n"
    )


def _make_figure_companion(
    base: Path,
    *,
    summary_overrides: dict | None = None,
    image_ref: str = "assets/ensemble_structure_diagram.png",
    extra_md: str = "",
    write_asset: bool = True,
) -> str:
    d = base / "writer_generated_figure_companion_177a"
    (d / "assets").mkdir(parents=True, exist_ok=True)
    (d / FIGURE_GUIDE_MD).write_text(_figure_md(image_ref=image_ref, extra=extra_md), encoding="utf-8")
    (d / FIGURE_SUMMARY_JSON).write_text(
        json.dumps(_figure_summary(**(summary_overrides or {}))), encoding="utf-8"
    )
    if write_asset and image_ref.startswith("assets/"):
        (d / image_ref).write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC-NON-TABLE-FIGURE-PIXELS")
    return str(d)


def _run(base: Path, table_dir: str | None, figure_dir: str | None) -> dict:
    return run_combined_asset_companion_guide(
        table_companion_dir=table_dir,
        figure_companion_dir=figure_dir,
        private_combined_dir=str(base / "combined_177b"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_completed_combined_path() -> None:
    print("test_completed_combined_path")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_table_companion(base), _make_figure_companion(base))
        html_path = base / "combined_177b" / COMBINED_GUIDE_HTML
        html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    _check("status completed", summary["status"] == "completed", str(summary))
    _check("slice 177B", summary["slice"] == "177B")
    _check("artifact name", summary["artifact_name"] == "combined_asset_companion_guide")
    _check("source label ensemble", summary["source_label"] == "ensemble")
    _check("render html", summary["combined_render_format"] == "html")
    _check("render status rendered", summary["combined_render_status"] == "rendered")
    _check("guide written", summary["private_combined_guide_written"] is True)
    _check("guide gitignored", summary["private_combined_guide_gitignored"] is True)
    _check("table source label", summary["table_companion_source"] == "private_176x_writer_table_companion")
    _check("table present", summary["table_companion_present"] is True)
    _check("faithful table present", summary["faithful_table_present"] is True)
    _check("table explanation present", summary["table_explanation_present"] is True)
    _check("role aware simplified present", summary["role_aware_simplified_table_present"] is True)
    _check("not row reduced", summary["simplified_table_is_row_reduced_copy"] is False)
    _check("study oriented", summary["simplified_table_is_study_oriented"] is True)
    _check("table visibility pending", summary["table_visibility_status"] == "operator_pending")
    _check("figure source label", summary["figure_companion_source"] == "private_177a_writer_figure_companion")
    _check("figure present", summary["figure_companion_present"] is True)
    _check("figure visual present", summary["figure_visual_present"] is True)
    _check("figure visual type", summary["figure_visual_type_closed"] == "flow_or_structure_diagram")
    _check("figure non-table", summary["figure_visual_is_non_table_figure"] is True)
    _check("figure not text only", summary["figure_visual_is_text_only"] is False)
    _check("figure not sliver", summary["figure_visual_is_partial_sliver"] is False)
    _check("figure not table-like", summary["figure_visual_is_table_like"] is False)
    _check("figure not matrix", summary["figure_visual_is_matrix"] is False)
    _check("figure not grid", summary["figure_visual_is_grid"] is False)
    _check("figure explanation present", summary["figure_explanation_present"] is True)
    _check("figure reading steps present", summary["figure_reading_steps_present"] is True)
    _check("figure exam takeaway present", summary["figure_exam_takeaway_present"] is True)
    _check("figure visibility pending", summary["figure_visibility_status"] == "operator_pending")
    _check("no raw private paths", summary["raw_private_paths_in_rendered_html"] is False)
    _check("data image false", summary["data_image_used"] is False)
    _check("base64 false", summary["base64_image_used"] is False)
    _check("provider call false", summary["provider_call_made"] is False)
    _check("generation rerun false", summary["generation_rerun"] is False)
    _check("generation behavior unchanged", summary["generation_behavior_changed"] is False)
    _check("numeric verification not claimed", summary["numeric_verification_claimed"] is False)
    _check("frontend unchanged", summary["frontend_api_changed"] is False)
    _check("judge not ready", summary["judge_ready"] is False)
    _check("repair not ready", summary["repair_ready"] is False)
    _check("operator read required", summary["operator_private_read_required"] is True)
    _check("operator read not done", summary["operator_private_read_done"] is False)
    _check("blocked none", summary["blocked_by"] == "none")
    _check("next step operator read", summary["recommended_next_step"] == "operator_read_private_combined_asset_companion_guide")
    # Rendered HTML proves both blocks coexist.
    _check("html two tables", html.count("<table") >= 2)
    _check("html has image", "<img" in html and "assets/" in html)
    _check("html table explanation", "What this table shows" in html)
    _check("html simplified table", "Simplified study table" in html)
    _check("html figure explanation", "What this figure shows" in html)
    _check("html figure takeaway", "Exam takeaway" in html)
    _check("html no data uri", "data:image" not in html)
    _check("html no base64", "base64" not in html.lower())
    _check("html no tmp path", "/tmp/" not in html and str(Path(tmp)) not in html)
    _check("html no private marker", ".private_ocr" not in html and "local_operator_baselines" not in html)


def test_blocks_missing_table() -> None:
    print("test_blocks_missing_table")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, str(base / "nope_table"), _make_figure_companion(base))
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by table not found", summary["blocked_by"] == "table_companion_not_found")
    _check("next step rebuild table", summary["recommended_next_step"] == "rebuild_table_companion")
    _check("table not present", summary["table_companion_present"] is False)


def test_blocks_missing_figure() -> None:
    print("test_blocks_missing_figure")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_table_companion(base), str(base / "nope_figure"))
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by figure not found", summary["blocked_by"] == "figure_companion_not_found")
    _check("next step rebuild figure", summary["recommended_next_step"] == "rebuild_figure_companion")
    _check("table present", summary["table_companion_present"] is True)
    _check("figure not present", summary["figure_companion_present"] is False)


def test_blocks_row_reduced_table() -> None:
    print("test_blocks_row_reduced_table")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(
            base,
            _make_table_companion(base, row_reduced=True),
            _make_figure_companion(base),
        )
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by row reduced", summary["blocked_by"] == "table_companion_row_reduced")
    _check("next step rebuild table", summary["recommended_next_step"] == "rebuild_table_companion")


def test_blocks_table_like_figure() -> None:
    print("test_blocks_table_like_figure")
    for label, overrides in (
        ("table_like", {"visual_is_table_like": True}),
        ("matrix", {"visual_is_matrix": True}),
        ("grid", {"visual_is_grid": True}),
        ("text_only", {"visual_is_text_only": True}),
        ("sliver", {"visual_is_partial_sliver": True}),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            summary = _run(
                base,
                _make_table_companion(base),
                _make_figure_companion(base, summary_overrides=overrides),
            )
        _check(f"blocked status ({label})", summary["status"] == "blocked")
        _check(f"blocked_by figure table-like ({label})", summary["blocked_by"] == "figure_companion_table_like")


def test_blocks_raw_private_path_in_render() -> None:
    print("test_blocks_raw_private_path_in_render")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        leak = "Reference dump at local_operator_baselines internal store.\n\n"
        summary = _run(
            base,
            _make_table_companion(base),
            _make_figure_companion(base, extra_md=leak),
        )
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by raw private path", summary["blocked_by"] == "raw_private_path_in_render")


def test_refuses_data_uri_image() -> None:
    print("test_refuses_data_uri_image")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        data_uri = "![inline](data:image/png;base64,AAAABBBBCCCC)\n\n"
        summary = _run(
            base,
            _make_table_companion(base),
            _make_figure_companion(base, extra_md=data_uri),
        )
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by data uri", summary["blocked_by"] == "data_uri_or_base64_refused")


def test_refuses_missing_figure_asset() -> None:
    print("test_refuses_missing_figure_asset")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        fig_dir = _make_figure_companion(base, write_asset=False)
        summary = _run(base, _make_table_companion(base), fig_dir)
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by asset unavailable", summary["blocked_by"] == "figure_asset_unavailable")


def test_closed_summary_no_leak_contract() -> None:
    print("test_closed_summary_no_leak_contract")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_table_companion(base), _make_figure_companion(base))
        blob = json.dumps(summary)
        # Keys are controlled closed vocabulary (e.g. base64_image_used); only values
        # could ever carry leaked content, so scope content scans to values.
        values_blob = " ".join(str(v) for v in summary.values()).lower()
        summary_path = base / "combined_177b" / COMBINED_SUMMARY_JSON
        disk_blob = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    _check("summary excludes table canary", _RAW_TABLE_CANARY not in blob)
    _check("summary excludes figure canary", _RAW_FIGURE_CANARY not in blob)
    _check("summary excludes data uri", "data:image" not in values_blob)
    _check("summary excludes base64 payload", ";base64," not in values_blob and "base64" not in values_blob)
    _check("summary has no path-like values", not any("/" in str(v) for v in summary.values()))
    _check("summary has no tmp path", "/tmp/" not in values_blob)
    _check("disk summary excludes canary", _RAW_TABLE_CANARY not in disk_blob and _RAW_FIGURE_CANARY not in disk_blob)
    _check("disk summary written", bool(disk_blob))


def main() -> int:
    test_completed_combined_path()
    test_blocks_missing_table()
    test_blocks_missing_figure()
    test_blocks_row_reduced_table()
    test_blocks_table_like_figure()
    test_blocks_raw_private_path_in_render()
    test_refuses_data_uri_image()
    test_refuses_missing_figure_asset()
    test_closed_summary_no_leak_contract()
    if _FAILURES:
        print(f"\nFAILED: {len(_FAILURES)} check(s): {_FAILURES}")
        return 1
    print("\nAll combined asset companion guide tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
