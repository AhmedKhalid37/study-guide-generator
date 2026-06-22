"""Public-safe tests for Slice 177D off-by-default asset-companion insertion seam.

All fixtures are synthetic; no private artifacts, provider calls, or raw study
content are touched. The existing 177C full-preview, 177B combined-guide, 177A
figure-companion and 176X table-companion tests are validated by their own scripts in
the slice run (cases 13/14 in the slice plan).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.asset_companion_insertion import (  # noqa: E402
    INSERTED_GUIDE_HTML,
    INSERTION_SUMMARY_JSON,
    insert_companion_section,
    pick_insertion_point,
    run_asset_companion_insertion,
)
from pipeline.combined_asset_companion_guide import (  # noqa: E402
    COMBINED_GUIDE_MD,
    COMBINED_SUMMARY_JSON,
)

_FAILURES: list[str] = []
_RAW_GUIDE_CANARY = "RAW_SYNTHETIC_FULL_GUIDE_CANARY"
_RAW_COMBINED_CANARY = "RAW_SYNTHETIC_COMBINED_COMPANION_CANARY"


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

def _full_guide_md(*, with_summary: bool = True, extra: str = "") -> str:
    summary = (
        "## Summary\n\n"
        "Diversity among learners reduces variance and improves generalisation.\n"
        if with_summary
        else ""
    )
    return (
        "# Ensemble Learning Study Guide\n\n"
        f"<!-- {_RAW_GUIDE_CANARY} -->\n\n"
        "## Overview\n\n"
        "Ensemble learning combines several weak learners into one stronger model.\n\n"
        f"{extra}"
        "## Bagging\n\n"
        "Bagging trains learners on bootstrap samples and averages their outputs.\n\n"
        "| Method | Idea |\n| --- | --- |\n| Bagging | average bootstrap learners |\n\n"
        "## Boosting\n\n"
        "Boosting fits learners sequentially, each correcting the previous errors.\n\n"
        f"{summary}"
    )


def _combined_summary(**overrides) -> dict:
    summary = {
        "artifact_name": "combined_asset_companion_guide",
        "slice": "177B",
        "status": "completed",
        "source_label": "ensemble",
        "table_companion_present": True,
        "faithful_table_present": True,
        "table_explanation_present": True,
        "role_aware_simplified_table_present": True,
        "simplified_table_is_row_reduced_copy": False,
        "simplified_table_is_study_oriented": True,
        "figure_companion_present": True,
        "figure_visual_present": True,
        "figure_visual_type_closed": "flow_or_structure_diagram",
        "figure_visual_is_non_table_figure": True,
        "figure_visual_is_table_like": False,
        "figure_visual_is_matrix": False,
        "figure_visual_is_grid": False,
        "figure_visual_is_text_only": False,
        "figure_visual_is_partial_sliver": False,
        "figure_explanation_present": True,
        "figure_reading_steps_present": True,
        "figure_exam_takeaway_present": True,
    }
    summary.update(overrides)
    return summary


def _combined_md(
    *,
    image_ref: str = "assets/ensemble_structure_diagram.png",
    include_table: bool = True,
    include_figure: bool = True,
    extra: str = "",
) -> str:
    table_block = (
        "## Reconstructed table companion\n\n"
        "| Age | Outcome |\n| --- | --- |\n| 34 | Positive |\n| 51 | Negative |\n\n"
        "### What this table shows\n\n"
        "Each row pairs a patient age with the recorded outcome so students connect a "
        "numeric predictor to its result.\n\n"
        "### Simplified study table\n\n"
        "| Pattern | Meaning | Exam takeaway |\n| --- | --- | --- |\n"
        "| Higher age | risk rises | watch older cases |\n\n"
    ) if include_table else ""
    figure_block = (
        "## Non-table figure companion\n\n"
        f"![Recovered study visual]({image_ref})\n\n"
        "### What this figure shows\n\n"
        "The diagram traces training data fanning out into several learners feeding one "
        "combiner that produces the final model.\n\n"
        "### How to read it\n\n"
        "1. Start at the training data.\n2. Follow each arrow to a learner.\n"
        "3. Trace the outputs into the combiner.\n\n"
        "### Exam takeaway\n\n"
        "The combiner aggregates diverse learners into one stronger model.\n\n"
    ) if include_figure else ""
    return (
        "# Combined Asset Companion Study Guide\n\n"
        f"<!-- {_RAW_COMBINED_CANARY} -->\n\n"
        "This private study section combines one table companion and one figure companion.\n\n"
        "---\n\n"
        f"{table_block}"
        f"{extra}"
        "---\n\n"
        f"{figure_block}"
    )


def _make_full_guide(base: Path, *, with_summary: bool = True, extra: str = "") -> str:
    d = base / "full_guide"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "ensemble_latest.md"
    p.write_text(_full_guide_md(with_summary=with_summary, extra=extra), encoding="utf-8")
    return str(p)


def _make_combined_companion(
    base: Path,
    *,
    summary_overrides: dict | None = None,
    image_ref: str = "assets/ensemble_structure_diagram.png",
    include_table: bool = True,
    include_figure: bool = True,
    extra_md: str = "",
    write_asset: bool = True,
) -> str:
    d = base / "combined_177b"
    (d / "assets").mkdir(parents=True, exist_ok=True)
    (d / COMBINED_GUIDE_MD).write_text(
        _combined_md(
            image_ref=image_ref,
            include_table=include_table,
            include_figure=include_figure,
            extra=extra_md,
        ),
        encoding="utf-8",
    )
    (d / COMBINED_SUMMARY_JSON).write_text(
        json.dumps(_combined_summary(**(summary_overrides or {}))), encoding="utf-8"
    )
    if write_asset and image_ref.startswith("assets/"):
        (d / image_ref).write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC-NON-TABLE-FIGURE-PIXELS")
    return str(d)


def _run(base: Path, full_guide: str | None, combined_dir: str | None, *, enabled: bool = True) -> dict:
    return run_asset_companion_insertion(
        full_guide_path=full_guide,
        combined_companion_dir=combined_dir,
        private_output_dir=str(base / "insertion_177d"),
        enabled=enabled,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_completed_insertion_path() -> None:
    print("test_completed_insertion_path")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base))
        html_path = base / "insertion_177d" / INSERTED_GUIDE_HTML
        html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    _check("status completed", summary["status"] == "completed", str(summary))
    _check("slice 177D", summary["slice"] == "177D")
    _check("artifact name", summary["artifact_name"] == "asset_companion_insertion_seam")
    _check("source label ensemble", summary["source_label"] == "ensemble")
    _check("off by default", summary["off_by_default"] is True)
    _check("normal generation default unchanged", summary["normal_generation_default_unchanged"] is True)
    _check("private runner enabled", summary["private_runner_enabled"] is True)
    _check("input full guide source", summary["input_full_guide_source"] == "private_ensemble_full_guide")
    _check("input full guide available", summary["input_full_guide_available"] is True)
    _check("input full guide gitignored", summary["input_full_guide_gitignored"] is True)
    _check("combined source", summary["combined_companion_source"] == "private_177b_or_177c_combined_asset_companion")
    _check("combined available", summary["combined_companion_available"] is True)
    _check("combined gitignored", summary["combined_companion_gitignored"] is True)
    _check("insertion mode", summary["insertion_mode"] == "gated_private_companion_section")
    _check("insertion location before summary", summary["insertion_location"] == "before_trailing_summary")
    _check("section inserted", summary["asset_companion_section_inserted"] is True)
    _check("relative refs preserved", summary["relative_asset_refs_preserved"] is True)
    _check("inserted guide written", summary["private_inserted_guide_written"] is True)
    _check("inserted guide gitignored", summary["private_inserted_guide_gitignored"] is True)
    _check("render format html", summary["render_format"] == "html")
    _check("render status rendered", summary["render_status"] == "rendered")
    _check("normal guide content present", summary["normal_guide_content_present"] is True)
    _check("table inserted", summary["table_companion_inserted"] is True)
    _check("faithful table present", summary["faithful_table_present"] is True)
    _check("table explanation present", summary["table_explanation_present"] is True)
    _check("role aware simplified present", summary["role_aware_simplified_table_present"] is True)
    _check("not row reduced", summary["simplified_table_is_row_reduced_copy"] is False)
    _check("study oriented", summary["simplified_table_is_study_oriented"] is True)
    _check("figure inserted", summary["figure_companion_inserted"] is True)
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
    _check("no raw private paths", summary["raw_private_paths_in_rendered_html"] is False)
    _check("no broken image", summary["broken_image_marker_detected"] is False)
    _check("data image false", summary["data_image_used"] is False)
    _check("base64 false", summary["base64_image_used"] is False)
    _check("provider call false", summary["provider_call_made"] is False)
    _check("generation rerun false", summary["generation_rerun"] is False)
    _check("generation behavior unchanged", summary["generation_behavior_changed"] is False)
    _check("cloud ocr false", summary["cloud_ocr_used"] is False)
    _check("numeric verification not claimed", summary["numeric_verification_claimed"] is False)
    _check("frontend unchanged", summary["frontend_api_changed"] is False)
    _check("judge not ready", summary["judge_ready"] is False)
    _check("repair not ready", summary["repair_ready"] is False)
    _check("operator read required", summary["operator_private_read_required"] is True)
    _check("operator read not done", summary["operator_private_read_done"] is False)
    _check("blocked none", summary["blocked_by"] == "none")
    _check("next step operator read", summary["recommended_next_step"] == "operator_read_private_asset_companion_insertion_output")
    # Rendered HTML proves the full guide AND both companion blocks coexist.
    _check("html has companion section", "Recovered visual" in html)
    _check("html has full-guide heading", "Bagging" in html and "Boosting" in html)
    _check("html table explanation", "What this table shows" in html)
    _check("html simplified table", "Simplified study table" in html)
    _check("html figure explanation", "What this figure shows" in html)
    _check("html figure takeaway", "Exam takeaway" in html)
    _check("html has image", "<img" in html and "assets/" in html)
    _check("html no data uri", "data:image" not in html)
    _check("html no base64", "base64" not in html.lower())
    _check("html no tmp path", "/tmp/" not in html and str(Path(tmp)) not in html)
    _check("html no private marker", ".private_ocr" not in html and "local_operator_baselines" not in html)


def test_off_by_default_pure_seam() -> None:
    print("test_off_by_default_pure_seam")
    guide = _full_guide_md()
    combined = _combined_md()
    # Disabled (the normal-generation default): guide returned byte-for-byte unchanged.
    unchanged = insert_companion_section(guide, combined, enabled=False)
    _check("disabled seam returns guide unchanged", unchanged == guide)
    _check("disabled seam has no companion marker", "Recovered visual" not in unchanged)
    # Enabled: companion section is inserted.
    enabled = insert_companion_section(guide, combined, enabled=True)
    _check("enabled seam inserts companion", "Recovered visual" in enabled)
    _check("enabled seam keeps original guide body", "Bagging" in enabled and "Boosting" in enabled)
    _check("enabled seam differs from guide", enabled != guide)


def test_off_by_default_runner_disabled() -> None:
    print("test_off_by_default_runner_disabled")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base), enabled=False)
        html_path = base / "insertion_177d" / INSERTED_GUIDE_HTML
        wrote_guide = html_path.is_file()
    _check("disabled runner status degraded", summary["status"] == "degraded")
    _check("disabled runner private_runner_enabled false", summary["private_runner_enabled"] is False)
    _check("disabled runner section not inserted", summary["asset_companion_section_inserted"] is False)
    _check("disabled runner insertion location not_inserted", summary["insertion_location"] == "not_inserted")
    _check("disabled runner blocked_by seam_disabled", summary["blocked_by"] == "seam_disabled")
    _check("disabled runner next step enable", summary["recommended_next_step"] == "enable_private_runner")
    _check("disabled runner normal default unchanged", summary["normal_generation_default_unchanged"] is True)
    _check("disabled runner wrote no inserted guide", wrote_guide is False)


def test_insertion_location_appended_when_no_summary() -> None:
    print("test_insertion_location_appended_when_no_summary")
    guide_no_summary = _full_guide_md(with_summary=False)
    idx, location = pick_insertion_point(guide_no_summary)
    _check("no-summary location appended_at_end", location == "appended_at_end")
    _check("no-summary index none", idx is None)
    guide_with_summary = _full_guide_md(with_summary=True)
    idx2, location2 = pick_insertion_point(guide_with_summary)
    _check("with-summary location before_trailing_summary", location2 == "before_trailing_summary")
    _check("with-summary index set", isinstance(idx2, int))
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base, with_summary=False), _make_combined_companion(base))
    _check("runner appended_at_end status completed", summary["status"] == "completed", str(summary))
    _check("runner appended_at_end location", summary["insertion_location"] == "appended_at_end")


def test_blocks_missing_full_guide() -> None:
    print("test_blocks_missing_full_guide")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, str(base / "nope_guide.md"), _make_combined_companion(base))
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by full guide not found", summary["blocked_by"] == "full_guide_not_found")
    _check("next step provide full guide", summary["recommended_next_step"] == "provide_full_guide")
    _check("full guide not available", summary["input_full_guide_available"] is False)


def test_blocks_missing_combined() -> None:
    print("test_blocks_missing_combined")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), str(base / "nope_combined"))
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by combined not found", summary["blocked_by"] == "combined_companion_not_found")
    _check("next step rebuild combined", summary["recommended_next_step"] == "rebuild_combined_companion")
    _check("full guide available", summary["input_full_guide_available"] is True)
    _check("combined not available", summary["combined_companion_available"] is False)


def test_blocks_combined_missing_table() -> None:
    print("test_blocks_combined_missing_table")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        combined = _make_combined_companion(
            base,
            summary_overrides={"role_aware_simplified_table_present": False},
            include_table=False,
        )
        summary = _run(base, _make_full_guide(base), combined)
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by missing table", summary["blocked_by"] == "combined_companion_missing_table")


def test_blocks_combined_missing_figure() -> None:
    print("test_blocks_combined_missing_figure")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        combined = _make_combined_companion(base, include_figure=False)
        summary = _run(base, _make_full_guide(base), combined)
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by missing figure", summary["blocked_by"] == "combined_companion_missing_figure")


def test_blocks_table_like_figure() -> None:
    print("test_blocks_table_like_figure")
    for label, overrides in (
        ("table_like", {"figure_visual_is_table_like": True}),
        ("matrix", {"figure_visual_is_matrix": True}),
        ("grid", {"figure_visual_is_grid": True}),
        ("text_only", {"figure_visual_is_text_only": True}),
        ("sliver", {"figure_visual_is_partial_sliver": True}),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            combined = _make_combined_companion(base, summary_overrides=overrides)
            summary = _run(base, _make_full_guide(base), combined)
        _check(f"blocked status ({label})", summary["status"] == "blocked")
        _check(
            f"blocked_by figure table-like ({label})",
            summary["blocked_by"] == "combined_companion_figure_table_like",
        )


def test_blocks_row_reduced_table() -> None:
    print("test_blocks_row_reduced_table")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        combined = _make_combined_companion(
            base,
            summary_overrides={
                "simplified_table_is_row_reduced_copy": True,
                "simplified_table_is_study_oriented": False,
            },
        )
        summary = _run(base, _make_full_guide(base), combined)
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by row reduced", summary["blocked_by"] == "combined_companion_table_row_reduced")


def test_blocks_raw_private_path_in_render() -> None:
    print("test_blocks_raw_private_path_in_render")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        leak = "Reference dump at local_operator_baselines internal store.\n\n"
        full_guide = _make_full_guide(base, extra=leak)
        summary = _run(base, full_guide, _make_combined_companion(base))
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by raw private path", summary["blocked_by"] == "raw_private_path_in_render")


def test_refuses_data_uri_image() -> None:
    print("test_refuses_data_uri_image")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        data_uri = "![inline](data:image/png;base64,AAAABBBBCCCC)\n\n"
        combined = _make_combined_companion(base, extra_md=data_uri)
        summary = _run(base, _make_full_guide(base), combined)
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by data uri", summary["blocked_by"] == "data_uri_or_base64_refused")


def test_refuses_missing_asset() -> None:
    print("test_refuses_missing_asset")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        combined = _make_combined_companion(base, write_asset=False)
        summary = _run(base, _make_full_guide(base), combined)
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by relative assets unavailable", summary["blocked_by"] == "relative_assets_unavailable")


def test_preserves_relative_asset_refs() -> None:
    print("test_preserves_relative_asset_refs")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base))
        asset = base / "insertion_177d" / "assets" / "ensemble_structure_diagram.png"
        asset_copied = asset.is_file()
    _check("relative refs preserved flag", summary["relative_asset_refs_preserved"] is True)
    _check("asset file copied to private dir", asset_copied is True)


def test_closed_summary_no_leak_contract() -> None:
    print("test_closed_summary_no_leak_contract")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base))
        blob = json.dumps(summary)
        values_blob = " ".join(str(v) for v in summary.values()).lower()
        summary_path = base / "insertion_177d" / INSERTION_SUMMARY_JSON
        disk_blob = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    _check("summary excludes guide canary", _RAW_GUIDE_CANARY not in blob)
    _check("summary excludes combined canary", _RAW_COMBINED_CANARY not in blob)
    _check("summary excludes data uri", "data:image" not in values_blob)
    _check("summary excludes base64 payload", ";base64," not in values_blob and "base64" not in values_blob)
    _check("summary has no path-like values", not any("/" in str(v) for v in summary.values()))
    _check("summary has no tmp path", "/tmp/" not in values_blob)
    _check("disk summary excludes canary", _RAW_GUIDE_CANARY not in disk_blob and _RAW_COMBINED_CANARY not in disk_blob)
    _check("disk summary written", bool(disk_blob))


def main() -> int:
    test_completed_insertion_path()
    test_off_by_default_pure_seam()
    test_off_by_default_runner_disabled()
    test_insertion_location_appended_when_no_summary()
    test_blocks_missing_full_guide()
    test_blocks_missing_combined()
    test_blocks_combined_missing_table()
    test_blocks_combined_missing_figure()
    test_blocks_table_like_figure()
    test_blocks_row_reduced_table()
    test_blocks_raw_private_path_in_render()
    test_refuses_data_uri_image()
    test_refuses_missing_asset()
    test_preserves_relative_asset_refs()
    test_closed_summary_no_leak_contract()
    if _FAILURES:
        print(f"\nFAILED: {len(_FAILURES)} check(s): {_FAILURES}")
        return 1
    print("\nAll asset companion insertion seam tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
