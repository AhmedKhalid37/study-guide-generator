"""Public-safe tests for Slice 176U rendered reconstructed-table proof."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.rendered_visible_asset_insertion_proof import (  # noqa: E402
    VISIBILITY_STATUSES,
    build_closed_rendered_visible_asset_insertion_summary,
    insert_visible_asset_into_markdown,
    is_safe_relative_asset_ref,
    run_rendered_visible_asset_insertion_proof,
    select_visible_asset_payload,
)

_FAILURES: list[str] = []
_RAW_CANARY = "RAW_SYNTHETIC_TABLE_CELL_CANARY"


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


def _payload() -> dict:
    return {
        "source_label": "ensemble",
        "assets": [
            {
                "asset_category": "proximity_matrix",
                "table_markdown": ["| p | q |\n| --- | --- |\n| x | y |"],
                "display_role": "student_visible_reference",
            },
            {
                "asset_category": "patient_dataset_table",
                "table_markdown": [f"| a | b |\n| --- | --- |\n| {_RAW_CANARY} | z |"],
                "display_role": "student_visible_reference",
            },
        ],
    }


def test_safe_relative_asset_ref_gate() -> None:
    _check("safe asset ref accepted", is_safe_relative_asset_ref("assets/s00_page_0001_figure_01.png"))
    bad = [
        "/tmp/x.png",
        "assets/../x.png",
        "assets\\x.png",
        "http://example.test/x.png",
        "data:image/png;base64,AAAA",
        "assets/sub/x.png",
        "assets/x.jpg",
    ]
    _check("unsafe refs rejected", all(not is_safe_relative_asset_ref(ref) for ref in bad), str(bad))


def test_select_prefers_patient_dataset_table() -> None:
    selected = select_visible_asset_payload(_payload())
    _check("patient table selected first", selected is not None and selected["asset_category"] == "patient_dataset_table")


def test_private_markdown_asset_insertion_summary_is_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proof"
        summary = run_rendered_visible_asset_insertion_proof(
            visible_payload_override=_payload(),
            private_render_dir=str(out),
            render_html=False,
        )
    blob = json.dumps(summary, sort_keys=True)
    _check("markdown-only is not rendered proof", summary["private_rendered_guide_written"] is False)
    _check("insertion mode private table", summary["insertion_mode"] == "private_markdown_table")
    _check("render unavailable degrades honestly", summary["status"] == "degraded")
    _check("markdown-only rejected as completed", summary["render_status"] == "not_run")
    _check("renderer unavailable blocker", summary["blocked_by"] == "renderer_unavailable")
    _check("raw table canary absent from summary", _RAW_CANARY not in blob, blob)


def test_display_only_and_disabled_runtime_flags() -> None:
    summary = build_closed_rendered_visible_asset_insertion_summary(
        status="completed",
        selected_asset_category="patient_dataset_table",
        selected_asset_kind="table",
        insertion_mode="private_markdown_table",
        render_format="html",
        render_status="rendered",
        asset_visibility_status="visible",
        export_visibility_status="visible",
        private_rendered_guide_written=True,
        private_rendered_guide_gitignored=True,
        phase4_next_requirement="add_explanation_beneath_asset",
        recommended_next_step="inspect_private_rendered_reconstructed_table_guide",
    )
    _check("artifact name strict", summary["artifact_name"] == "rendered_reconstructed_table_proof")
    _check("display-only role preserved", summary["selected_asset_role"] == "display_only")
    _check("table not inserted as image", summary["table_inserted_as_image"] is False)
    _check("numeric verification false", summary["numeric_verification_claimed"] is False)
    _check("provider call false", summary["provider_call_made"] is False)
    _check("generation rerun false", summary["generation_rerun"] is False)
    _check("ocr rerun false", summary["ocr_rerun"] is False)
    _check("coverage rerun false", summary["coverage_eval_rerun"] is False)
    _check("cloud OCR false", summary["cloud_ocr_used"] is False)


def test_render_html_visibility_closed_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proof"
        summary = run_rendered_visible_asset_insertion_proof(
            visible_payload_override=_payload(),
            private_render_dir=str(out),
            render_html=True,
        )
    _check("completed status requires rendered table", summary["status"] == "completed", str(summary))
    _check("render status rendered", summary["render_status"] == "rendered")
    _check("render format html", summary["render_format"] == "html")
    _check("table category selected", summary["selected_asset_category"] in {"patient_dataset_table", "proximity_matrix"})
    _check("selected kind table", summary["selected_asset_kind"] == "table")
    _check("insertion mode table only", summary["insertion_mode"] in {"private_markdown_table", "private_reconstructed_table"})
    _check("private rendered guide written", summary["private_rendered_guide_written"] is True)
    _check("asset visibility status closed", summary["asset_visibility_status"] in VISIBILITY_STATUSES)
    _check("export visibility status closed", summary["export_visibility_status"] in VISIBILITY_STATUSES)
    _check("asset visibility visible", summary["asset_visibility_status"] == "visible")
    _check("phase4 next explains", summary["phase4_next_requirement"] == "add_explanation_beneath_asset")


def test_table_image_ref_rejected_for_completion() -> None:
    md, mode = insert_visible_asset_into_markdown(
        "# Guide",
        {"asset_category": "patient_dataset_table", "asset_ref": "assets/s00_page_0002_figure_01.png"},
    )
    _check("table image ref not inserted", md is None)
    _check("table image ref not counted", mode == "not_run")
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_rendered_visible_asset_insertion_proof(
            visible_payload_override={
                "source_label": "ensemble",
                "assets": [
                    {
                        "asset_category": "patient_dataset_table",
                        "asset_ref": "assets/s00_page_0002_figure_01.png",
                    }
                ],
            },
            private_render_dir=str(Path(tmp) / "proof"),
            render_html=True,
        )
    _check("table image-only cannot complete", summary["status"] == "blocked", str(summary))
    _check("table image-only blocker", summary["blocked_by"] == "private_visible_table_missing")


def test_completed_status_requires_table_and_visibility() -> None:
    weak = build_closed_rendered_visible_asset_insertion_summary(
        status="completed",
        selected_asset_category="none",
        selected_asset_kind="unknown",
        insertion_mode="not_run",
        render_format="html",
        render_status="rendered",
        asset_visibility_status="visible",
        private_rendered_guide_written=True,
        private_rendered_guide_gitignored=True,
    )
    _check("completed downgraded without table", weak["status"] != "completed")
    no_visibility = build_closed_rendered_visible_asset_insertion_summary(
        status="completed",
        selected_asset_category="patient_dataset_table",
        selected_asset_kind="table",
        insertion_mode="private_markdown_table",
        render_format="html",
        render_status="rendered",
        asset_visibility_status="not_checked",
        private_rendered_guide_written=True,
        private_rendered_guide_gitignored=True,
        blocked_by="asset_visibility_failed",
    )
    _check("completed downgraded without visibility", no_visibility["status"] != "completed")
    markdown_only = build_closed_rendered_visible_asset_insertion_summary(
        status="completed",
        selected_asset_category="patient_dataset_table",
        selected_asset_kind="table",
        insertion_mode="private_markdown_table",
        render_format="not_run",
        render_status="not_run",
        asset_visibility_status="not_checked",
        private_rendered_guide_written=False,
        private_rendered_guide_gitignored=True,
        blocked_by="renderer_unavailable",
    )
    _check("completed downgraded without html/pdf render", markdown_only["status"] != "completed")


def test_reconstructed_table_mode_completes_when_rendered() -> None:
    payload = {
        "source_label": "ensemble",
        "assets": [
            {
                "asset_category": "proximity_matrix",
                "reconstructed_table_markdown": "| m | n |\n| --- | --- |\n| u | v |",
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        summary = run_rendered_visible_asset_insertion_proof(
            visible_payload_override=payload,
            private_render_dir=str(Path(tmp) / "proof"),
            render_html=True,
        )
    _check("reconstructed table can complete", summary["status"] == "completed", str(summary))
    _check("reconstructed table mode", summary["insertion_mode"] == "private_reconstructed_table")


def test_missing_visible_artifact_blocks() -> None:
    summary = run_rendered_visible_asset_insertion_proof(
        visible_artifact_path=str(Path(tempfile.gettempdir()) / "missing_visible_artifact.json"),
        private_render_dir=str(Path(tempfile.gettempdir()) / "proof"),
    )
    _check("missing artifact blocks", summary["status"] == "blocked")
    _check("missing blocker", summary["blocked_by"] == "private_visible_table_missing")


def test_phase4_requirements_present() -> None:
    summary = build_closed_rendered_visible_asset_insertion_summary(
        status="completed",
        selected_asset_category="patient_dataset_table",
        selected_asset_kind="table",
        insertion_mode="private_markdown_table",
        render_format="html",
        render_status="rendered",
        asset_visibility_status="visible",
        export_visibility_status="visible",
        private_rendered_guide_written=True,
        private_rendered_guide_gitignored=True,
        phase4_next_requirement="add_faithful_table_plus_simplified_version",
        recommended_next_step="add_faithful_table_plus_simplified_version",
    )
    _check("phase4 faithful+simplified allowed", summary["phase4_next_requirement"] == "add_faithful_table_plus_simplified_version")
    _check("phase4 next step faithful+simplified allowed", summary["recommended_next_step"] == "add_faithful_table_plus_simplified_version")


def main() -> None:
    test_safe_relative_asset_ref_gate()
    test_select_prefers_patient_dataset_table()
    test_private_markdown_asset_insertion_summary_is_closed()
    test_display_only_and_disabled_runtime_flags()
    test_render_html_visibility_closed_status()
    test_table_image_ref_rejected_for_completion()
    test_completed_status_requires_table_and_visibility()
    test_reconstructed_table_mode_completes_when_rendered()
    test_missing_visible_artifact_blocks()
    test_phase4_requirements_present()
    if _FAILURES:
        print("\nFAILURES: " + ", ".join(_FAILURES))
        raise SystemExit(1)
    print("\nAll rendered reconstructed-table proof tests passed.")


if __name__ == "__main__":
    main()
