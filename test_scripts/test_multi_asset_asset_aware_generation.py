"""Public-safe tests for Slice 177G multi-asset asset-aware generation.

All fixtures are synthetic; no private artifacts, no real provider calls, and no
raw study content are touched. The writer is always an injected fake. Existing
176X table, 177D insertion seam, and 177E pipeline hook suites are exercised by
their own scripts at the end (scenarios 15-17).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.multi_asset_asset_aware_generation import (  # noqa: E402
    GUIDE_HTML,
    SUMMARY_JSON,
    _figure_descriptor_from_artifact,
    _table_descriptors_from_payload,
    run_multi_asset_asset_aware_generation,
)

_FAILURES: list[str] = []
_TABLE_CANARY = "RAW_SYNTHETIC_TABLE_CANARY_177G"
_FIGURE_CANARY = "RAW_SYNTHETIC_FIGURE_CANARY_177G"
_TABLE_MD = f"| {_TABLE_CANARY} | B |\n| --- | --- |\n| 1 | 2 |"


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


# ---------------------------------------------------------------------------
# Synthetic fixtures + fake writers
# ---------------------------------------------------------------------------

def _png(tmp: str) -> str:
    path = Path(tmp) / "crop.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 48)
    return str(path)


def _descriptors(
    crop: str,
    *,
    tables: int = 2,
    figure: bool = True,
    bad_first_table: bool = False,
    extra_chart_not_ready: bool = False,
) -> list[dict]:
    ids = ["proximity_matrix", "patient_dataset_table", "second_study_table"]
    out: list[dict] = []
    for i in range(tables):
        md = "just prose, not a table" if (bad_first_table and i == 0) else _TABLE_MD
        out.append(
            {
                "asset_id": ids[i],
                "asset_kind_closed": "reconstructed_table",
                "descriptor_ready_for_text_writer": True,
                "render_role": "insert_as_table",
                "table_markdown": md,
            }
        )
    if figure:
        out.append(
            {
                "asset_id": "decision_tree",
                "asset_kind_closed": "non_table_flow_or_structure_diagram",
                "descriptor_ready_for_text_writer": True,
                "render_role": "insert_as_figure_with_explanation",
                "figure_crop_path": crop,
                "descriptor_text": f"asset_kind: figure_or_diagram\n{_FIGURE_CANARY}",
            }
        )
    if extra_chart_not_ready:
        out.append(
            {
                "asset_id": "line_chart",
                "asset_kind_closed": "chart_or_graph_with_existing_descriptor",
                "descriptor_ready_for_text_writer": False,
                "render_role": "omit_with_reason",
                "omit_reason": "descriptor_not_ready",
            }
        )
    return out


def _ready_order(descs: list[dict]) -> list[tuple[str, str]]:
    return [
        (d["asset_id"], d["asset_kind_closed"])
        for d in descs
        if d.get("descriptor_ready_for_text_writer")
    ]


def _table_block(aid: str, *, explanation: str | None = None, inject: str = "") -> str:
    prose = explanation or (
        "This recovered table teaches students how the variables relate and what each "
        "column means for the exam, so they can read it confidently."
    )
    return (
        "{{asset:" + aid + "}}\n"
        "## What this table shows\n"
        f"{prose} {inject}\n\n"
        "## Simplified study table\n"
        "| Pattern to notice | Meaning | Exam takeaway |\n"
        "| --- | --- | --- |\n"
        "| trend rises | values grow over time | watch the slope |\n"
    )


def _figure_block(aid: str) -> str:
    return (
        "{{asset:" + aid + "}}\n"
        "## What this figure shows\n"
        "This diagram shows how the decision splits flow from the root node down to the "
        "leaf outcomes for each class in a clear top-down structure.\n\n"
        "## How to read it\n"
        "1. Start at the top node.\n"
        "2. Follow each branch to its child.\n\n"
        "## Exam takeaway\n"
        "Remember that each split reduces impurity toward a confident leaf.\n"
    )


def _block(aid: str, kind: str) -> str:
    return _table_block(aid) if kind == "reconstructed_table" else _figure_block(aid)


def _compliant_writer(order: list[tuple[str, str]]):
    def writer(_messages):
        parts = ["# Multi-Asset Study Guide\n"]
        for aid, kind in order:
            parts.append(_block(aid, kind))
        return "\n".join(parts)

    return writer


def _run(descs, tmp, writer, **kw):
    out = Path(tmp) / "out"
    return run_multi_asset_asset_aware_generation(
        descriptor_set_override=descs,
        private_output_dir=str(out),
        writer=writer,
        **kw,
    ), out


# ---------------------------------------------------------------------------
# 1. Completed multi-asset generation path
# ---------------------------------------------------------------------------

def test_completed_multi_asset_path() -> None:
    print("test_completed_multi_asset_path")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        summary, out = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        _check("status completed", summary["status"] == "completed", summary.get("blocked_by"))
        _check("off_by_default", summary["off_by_default"] is True)
        _check("normal default unchanged", summary["normal_generation_default_unchanged"] is True)
        _check("generation_scope", summary["generation_scope"] == "single_private_ensemble_multi_asset_generation")
        _check("wrapper_slice false", summary["wrapper_slice"] is False)
        _check("manifest_consumer false", summary["manifest_consumer"] is False)
        _check("coverage_packet_only false", summary["coverage_packet_only"] is False)
        _check("auto_discovery false", summary["auto_discovery_enabled"] is False)
        _check("all_assets_claimed false", summary["all_assets_claimed"] is False)
        _check("descriptor_ready_count>=3", summary["descriptor_ready_count"] >= 3)
        _check("available>=3", summary["available_asset_descriptor_count"] >= 3)
        _check("multi_asset_requirement_met", summary["multi_asset_requirement_met"] is True)
        _check("provider_call_made", summary["provider_call_made"] is True)
        _check("writer_generation_run", summary["writer_generation_run"] is True)
        _check("generation_behavior_changed", summary["generation_behavior_changed"] is True)
        _check("asset_tokens_available>=3", summary["asset_tokens_available_count"] >= 3)
        _check("asset_tokens_inserted>=3", summary["asset_tokens_inserted_count"] >= 3)
        _check("distinct>=3", summary["distinct_inserted_asset_count"] >= 3)
        _check("inserted_table_count==2", summary["inserted_table_count"] == 2)
        _check("inserted_figure_count==1", summary["inserted_non_table_figure_count"] == 1)
        _check("same_single false", summary["same_single_table_figure_output"] is False)
        _check("not_byte_identical true", summary["not_byte_identical_to_prior_single_asset_output"] is True)
        _check("orphan==0", summary["orphan_asset_token_count"] == 0)
        _check("duplicate==0", summary["duplicate_inserted_asset_count"] == 0)
        _check("considered all", summary["all_available_useful_descriptors_considered"] is True)
        _check("render_status rendered", summary["render_status"] == "rendered")
        _check("rendered_html_written", summary["rendered_html_written"] is True)
        _check("private guide written", summary["private_generated_guide_written"] is True)
        _check("no data image", summary["data_image_used"] is False)
        _check("no base64", summary["base64_used"] is False)
        _check("no raw private path", summary["raw_private_paths_in_rendered_html"] is False)
        _check("no broken image", summary["broken_image_marker_detected"] is False)
        _check("ocr not rerun", summary["ocr_rerun"] is False)
        _check("chandra not used", summary["chandra_used"] is False)
        _check("cloud ocr not used", summary["cloud_ocr_used"] is False)
        _check("numeric not claimed", summary["numeric_verification_claimed"] is False)
        _check("frontend unchanged", summary["frontend_api_changed"] is False)
        _check("judge not ready", summary["judge_ready"] is False)
        _check("repair not ready", summary["repair_ready"] is False)
        _check("next step operator read", summary["recommended_next_step"] == "operator_read_multi_asset_generated_guide")
        _check("html on disk", (out / GUIDE_HTML).is_file())
        _check("summary on disk", (out / SUMMARY_JSON).is_file())


# ---------------------------------------------------------------------------
# 2. Blocks if fewer than three ready descriptors
# ---------------------------------------------------------------------------

def test_blocks_insufficient_ready_descriptors() -> None:
    print("test_blocks_insufficient_ready_descriptors")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=1, figure=True)  # 2 ready
        summary, _ = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        _check("status blocked", summary["status"] == "blocked")
        _check("blocked_by insufficient", summary["blocked_by"] == "insufficient_existing_multi_asset_descriptor_set")
        _check("descriptor_ready_count<3", summary["descriptor_ready_count"] < 3)
        _check("no provider call", summary["provider_call_made"] is False)


# ---------------------------------------------------------------------------
# 3. Blocks if output is only the prior single table + single figure pair
# ---------------------------------------------------------------------------

def test_blocks_same_single_table_figure_repeat() -> None:
    print("test_blocks_same_single_table_figure_repeat")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)

        def writer(_m):
            # Insert only the first table + the figure; omit the second table.
            return "# G\n" + _table_block("proximity_matrix") + "\n" + _figure_block("decision_tree")

        summary, _ = _run(descs, tmp, writer)
        _check("status blocked", summary["status"] == "blocked")
        _check("blocked_by same_single", summary["blocked_by"] == "same_single_table_figure_repeat")
        _check("same_single true", summary["same_single_table_figure_output"] is True)
        _check("distinct==2", summary["distinct_inserted_asset_count"] == 2)


# ---------------------------------------------------------------------------
# 4. A completed state requires the generation pass to have run
# ---------------------------------------------------------------------------

def test_blocks_when_generation_not_run() -> None:
    print("test_blocks_when_generation_not_run")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)

        def raising_writer(_m):
            raise RuntimeError("provider exploded")

        summary, _ = _run(descs, tmp, raising_writer)
        _check("status not completed", summary["status"] != "completed")
        _check("blocked_by generation unavailable", summary["blocked_by"] == "writer_generation_unavailable")
        _check("writer_generation_run false", summary["writer_generation_run"] is False)
        _check("completed implies generation (invariant)", not (summary["status"] == "completed" and not summary["writer_generation_run"]))


# ---------------------------------------------------------------------------
# 5. Blocks if orphan asset tokens remain
# ---------------------------------------------------------------------------

def test_blocks_orphan_asset_token() -> None:
    print("test_blocks_orphan_asset_token")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        order = _ready_order(descs)

        def writer(_m):
            body = "# G\n" + "".join(_block(a, k) for a, k in order)
            return body + "\n{{asset:ghost_unknown}}\n## What this figure shows\nstray token here that cannot resolve to anything\n"

        summary, _ = _run(descs, tmp, writer)
        _check("status blocked", summary["status"] == "blocked")
        _check("blocked_by orphan", summary["blocked_by"] == "orphan_asset_token_remaining")
        _check("orphan count>0", summary["orphan_asset_token_count"] > 0)


# ---------------------------------------------------------------------------
# 6. Blocks if the same asset is inserted twice
# ---------------------------------------------------------------------------

def test_blocks_duplicate_asset_insertion() -> None:
    print("test_blocks_duplicate_asset_insertion")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        order = _ready_order(descs)

        def writer(_m):
            # Insert the first table token a second time.
            return "# G\n" + "".join(_block(a, k) for a, k in order) + "\n" + _table_block("proximity_matrix")

        summary, _ = _run(descs, tmp, writer)
        _check("status blocked", summary["status"] == "blocked")
        _check("blocked_by duplicate", summary["blocked_by"] == "duplicate_asset_insertion")
        _check("duplicate count>0", summary["duplicate_inserted_asset_count"] > 0)


# ---------------------------------------------------------------------------
# 7. Blocks if a table descriptor would be inserted as an image
# ---------------------------------------------------------------------------

def test_blocks_table_inserted_as_image() -> None:
    print("test_blocks_table_inserted_as_image")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True, bad_first_table=True)
        summary, _ = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        _check("status blocked", summary["status"] == "blocked")
        _check("blocked_by table_inserted_as_image", summary["blocked_by"] == "table_inserted_as_image")
        _check("tables_inserted_as_images true", summary["tables_inserted_as_images"] is True)


# ---------------------------------------------------------------------------
# 8. Requires real table rendering for table descriptors
# ---------------------------------------------------------------------------

def test_tables_rendered_as_real_tables() -> None:
    print("test_tables_rendered_as_real_tables")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        summary, out = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        html = (out / GUIDE_HTML).read_text(encoding="utf-8")
        _check("tables_rendered_as_real_tables", summary["tables_rendered_as_real_tables"] is True)
        _check("faithful reconstruction present", summary["faithful_table_reconstruction_present"] is True)
        _check("tables_inserted_as_images false", summary["tables_inserted_as_images"] is False)
        _check("html has <table>", "<table" in html)
        _check("html has no leftover token", "{{asset:" not in html)


# ---------------------------------------------------------------------------
# 9. Requires explanation beneath each inserted asset
# ---------------------------------------------------------------------------

def test_requires_explanation_beneath_each_asset() -> None:
    print("test_requires_explanation_beneath_each_asset")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        # Positive: completed run has all explanations.
        summary, _ = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        _check("table explanations present", summary["table_explanations_present"] is True)
        _check("figure explanations present", summary["figure_explanations_present"] is True)
        _check("figure reading steps present", summary["figure_reading_steps_present"] is True)
        _check("figure exam takeaway present", summary["figure_exam_takeaways_present"] is True)

        # Negative: a placeholder explanation beneath one asset blocks.
        def writer(_m):
            blocks = ["# G\n"]
            blocks.append("{{asset:proximity_matrix}}\n## What this table shows\nTODO\n")
            blocks.append(_table_block("patient_dataset_table"))
            blocks.append(_figure_block("decision_tree"))
            return "\n".join(blocks)

        summary2, _ = _run(descs, tmp, writer)
        _check("placeholder blocks", summary2["status"] == "blocked")
        _check("blocked_by missing explanation", summary2["blocked_by"] == "missing_explanation_beneath_asset")


# ---------------------------------------------------------------------------
# 10. Refuses table-like / matrix / grid visuals as figures
# ---------------------------------------------------------------------------

def test_refuses_table_like_visual_as_figure() -> None:
    print("test_refuses_table_like_visual_as_figure")
    # A table-like non-table descriptor must not become a ready figure.
    table_like_descriptor = {
        "selected_asset_category": "decision_tree_diagram",
        "selected_asset_kind": "figure_or_diagram",
        "source_label": "ensemble",
        "visual_is_table_like": True,
        "private_visual_crop_path": "",
    }
    fig = _figure_descriptor_from_artifact(table_like_descriptor, "ensemble")
    _check("table-like figure not ready", fig is not None and fig.descriptor_ready_for_text_writer is False)
    _check("table-like figure omitted", fig is not None and fig.render_role == "omit_with_reason")

    # A proximity_matrix in the payload is classified as a reconstructed table.
    payload = {"source_label": "ensemble", "assets": [{"asset_category": "proximity_matrix", "table_markdown": [_TABLE_MD]}]}
    tables = _table_descriptors_from_payload(payload, "ensemble")
    _check("matrix classified as table", len(tables) == 1 and tables[0].asset_kind_closed == "reconstructed_table")
    _check("matrix render role table", len(tables) == 1 and tables[0].render_role == "insert_as_table")

    # The completed summary asserts the construction-time refusal flag.
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        summary, _ = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        _check("refusal flag true", summary["table_like_visuals_refused_as_figures"] is True)


# ---------------------------------------------------------------------------
# 11. Blocks / refuses data:image / base64
# ---------------------------------------------------------------------------

def test_refuses_data_uri_or_base64() -> None:
    print("test_refuses_data_uri_or_base64")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        order = _ready_order(descs)

        def writer(_m):
            body = "# G\n" + "".join(_block(a, k) for a, k in order)
            return body + "\n![x](data:image/png;base64,AAAABBBBCCCC)\n"

        summary, _ = _run(descs, tmp, writer)
        _check("status blocked", summary["status"] == "blocked")
        _check("blocked_by data uri", summary["blocked_by"] == "data_uri_or_base64_refused")


# ---------------------------------------------------------------------------
# 12. Blocks raw private path in rendered output
# ---------------------------------------------------------------------------

def test_blocks_raw_private_path_in_render() -> None:
    print("test_blocks_raw_private_path_in_render")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        order = _ready_order(descs)

        def writer(_m):
            parts = ["# G\n"]
            parts.append(_table_block("proximity_matrix", inject="See /tmp/leaked_private_path for details."))
            for aid, kind in order[1:]:
                parts.append(_block(aid, kind))
            return "\n".join(parts)

        summary, _ = _run(descs, tmp, writer)
        _check("status blocked", summary["status"] == "blocked")
        _check("blocked_by raw private path", summary["blocked_by"] == "raw_private_path_in_render")
        _check("raw private path flag", summary["raw_private_paths_in_rendered_html"] is True)


# ---------------------------------------------------------------------------
# 13. Records diagram_caption_descriptor_gap honestly
# ---------------------------------------------------------------------------

def test_records_diagram_caption_descriptor_gap() -> None:
    print("test_records_diagram_caption_descriptor_gap")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True, extra_chart_not_ready=True)
        summary, _ = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        _check("status completed", summary["status"] == "completed", summary.get("blocked_by"))
        _check("missing-for-generation count==1", summary["descriptor_missing_for_generation_count"] == 1)
        _check("diagram_caption_descriptor_gap true", summary["diagram_caption_descriptor_gap"] is True)
        _check("chart not inserted", summary["inserted_chart_or_graph_count"] == 0)


# ---------------------------------------------------------------------------
# 14. Closed summary no-leak contract
# ---------------------------------------------------------------------------

def test_closed_summary_no_leak_contract() -> None:
    print("test_closed_summary_no_leak_contract")
    with tempfile.TemporaryDirectory() as tmp:
        descs = _descriptors(_png(tmp), tables=2, figure=True)
        summary, _ = _run(descs, tmp, _compliant_writer(_ready_order(descs)))
        blob = json.dumps(summary)
        _check("no table canary", _TABLE_CANARY not in blob)
        _check("no figure canary", _FIGURE_CANARY not in blob)
        _check("no data uri", "data:image" not in blob and ";base64," not in blob.lower())
        lowered = blob.lower()
        _check("no slash in string values", all(
            "/" not in v and "\\" not in v for v in summary.values() if isinstance(v, str)
        ))
        _check("no image suffix in string values", all(
            ".png" not in v and ".jpg" not in v for v in summary.values() if isinstance(v, str)
        ))
        _check("no private markers", "local_operator_baselines" not in blob and "private_ocr" not in blob and "/tmp/" not in blob)


# ---------------------------------------------------------------------------
# 15-17. Existing sibling suites still pass (no regression)
# ---------------------------------------------------------------------------

def _run_sibling(script: str) -> None:
    path = Path(__file__).resolve().parent / script
    if not path.is_file():
        _check(f"{script} present", False, "sibling test script missing")
        return
    proc = subprocess.run([sys.executable, str(path)], capture_output=True, text=True)
    _check(f"{script} passes", proc.returncode == 0, proc.stdout[-400:] + proc.stderr[-400:])


def test_sibling_suites_still_pass() -> None:
    print("test_sibling_suites_still_pass")
    _run_sibling("test_writer_generated_table_companion.py")  # 176X table companion (15)
    _run_sibling("test_asset_companion_pipeline_hook.py")     # 177E pipeline hook (16)
    _run_sibling("test_asset_companion_insertion.py")         # 177D insertion seam (17)


def main() -> int:
    test_completed_multi_asset_path()
    test_blocks_insufficient_ready_descriptors()
    test_blocks_same_single_table_figure_repeat()
    test_blocks_when_generation_not_run()
    test_blocks_orphan_asset_token()
    test_blocks_duplicate_asset_insertion()
    test_blocks_table_inserted_as_image()
    test_tables_rendered_as_real_tables()
    test_requires_explanation_beneath_each_asset()
    test_refuses_table_like_visual_as_figure()
    test_refuses_data_uri_or_base64()
    test_blocks_raw_private_path_in_render()
    test_records_diagram_caption_descriptor_gap()
    test_closed_summary_no_leak_contract()
    test_sibling_suites_still_pass()
    if _FAILURES:
        print(f"\nFAILED: {len(_FAILURES)} check(s): {_FAILURES}")
        return 1
    print("\nAll multi-asset asset-aware generation tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
