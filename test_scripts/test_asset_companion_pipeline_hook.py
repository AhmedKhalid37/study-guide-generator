"""Public-safe tests for Slice 177E default-off asset-companion pipeline hook."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.asset_companion_pipeline_hook import (  # noqa: E402
    PIPELINE_HOOK_HTML,
    PIPELINE_HOOK_SUMMARY_JSON,
    AssetCompanionPipelineHookConfig,
    apply_asset_companion_pipeline_hook,
    default_asset_companion_pipeline_hook_config,
    run_asset_companion_pipeline_hook,
)
from test_scripts.test_asset_companion_insertion import (  # noqa: E402
    _RAW_COMBINED_CANARY,
    _RAW_GUIDE_CANARY,
    _combined_md,
    _full_guide_md,
    _make_combined_companion,
    _make_full_guide,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        if detail:
            print(f"    {detail}")
        _FAILURES.append(name)


def _run(base: Path, full_guide: str | None, combined_dir: str | None, *, enabled: bool = True) -> dict:
    return run_asset_companion_pipeline_hook(
        full_guide_path=full_guide,
        combined_companion_dir=combined_dir,
        private_output_dir=str(base / "pipeline_hook_177e"),
        enabled=enabled,
        private_runner_enabled=enabled,
    )


def test_disabled_hook_returns_unchanged_markdown() -> None:
    print("test_disabled_hook_returns_unchanged_markdown")
    guide = _full_guide_md()
    combined = _combined_md()
    output, called = apply_asset_companion_pipeline_hook(guide, combined)
    _check("disabled output byte identical", output == guide)
    _check("disabled path did not call seam", called is False)
    _check("disabled output has no companion section", "Recovered visual" not in output)


def test_default_config_keeps_hook_disabled() -> None:
    print("test_default_config_keeps_hook_disabled")
    cfg = default_asset_companion_pipeline_hook_config()
    guide = _full_guide_md()
    output, called = apply_asset_companion_pipeline_hook(
        guide, _combined_md(), config=cfg
    )
    _check("default config enabled false", cfg.enabled is False)
    _check("default config private false", cfg.private_runner_enabled is False)
    _check("default config unchanged", output == guide)
    _check("default config did not call seam", called is False)


def test_private_enabled_hook_calls_177d_seam() -> None:
    print("test_private_enabled_hook_calls_177d_seam")
    guide = _full_guide_md()
    output, called = apply_asset_companion_pipeline_hook(
        guide,
        _combined_md(),
        config=AssetCompanionPipelineHookConfig(enabled=True, private_runner_enabled=True),
    )
    _check("enabled path called insertion seam", called is True)
    _check("enabled path changed guide", output != guide)
    _check("enabled path inserted companion section", "Recovered visual" in output)
    _check("enabled path kept normal guide", "Bagging" in output and "Boosting" in output)


def test_completed_enabled_path_with_synthetic_inputs() -> None:
    print("test_completed_enabled_path_with_synthetic_inputs")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base))
        html_path = base / "pipeline_hook_177e" / PIPELINE_HOOK_HTML
        html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    _check("status completed", summary["status"] == "completed", str(summary))
    _check("artifact name", summary["artifact_name"] == "asset_companion_pipeline_hook")
    _check("slice 177E", summary["slice"] == "177E")
    _check("off by default", summary["off_by_default"] is True)
    _check("normal default unchanged", summary["normal_generation_default_unchanged"] is True)
    _check("default hook disabled", summary["default_hook_enabled"] is False)
    _check("private hook enabled", summary["private_hook_enabled"] is True)
    _check("private runner enabled", summary["private_runner_enabled"] is True)
    _check("normal generation did not invoke hook", summary["hook_invoked_from_normal_generation"] is False)
    _check("private runner invoked hook", summary["hook_invoked_from_private_runner"] is True)
    _check("disabled path byte identical", summary["disabled_path_byte_identical"] is True)
    _check("enabled path called seam", summary["enabled_path_called_insertion_seam"] is True)
    _check("seam source 177d", summary["insertion_seam_source"] == "asset_companion_insertion_177d")
    _check("full guide available", summary["input_full_guide_available"] is True)
    _check("full guide gitignored", summary["input_full_guide_gitignored"] is True)
    _check("combined available", summary["combined_companion_available"] is True)
    _check("combined gitignored", summary["combined_companion_gitignored"] is True)
    _check("section inserted", summary["asset_companion_section_inserted"] is True)
    _check("relative refs preserved", summary["relative_asset_refs_preserved"] is True)
    _check("private render written", summary["private_hook_render_written"] is True)
    _check("private render gitignored", summary["private_hook_render_gitignored"] is True)
    _check("rendered html", summary["render_status"] == "rendered" and summary["render_format"] == "html")
    _check("normal guide content present", summary["normal_guide_content_present"] is True)
    _check("table inserted", summary["table_companion_inserted"] is True)
    _check("faithful table present", summary["faithful_table_present"] is True)
    _check("table explanation present", summary["table_explanation_present"] is True)
    _check("simplified table present", summary["role_aware_simplified_table_present"] is True)
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
    _check("figure explanation", summary["figure_explanation_present"] is True)
    _check("figure reading steps", summary["figure_reading_steps_present"] is True)
    _check("figure exam takeaway", summary["figure_exam_takeaway_present"] is True)
    _check("no raw private paths", summary["raw_private_paths_in_rendered_html"] is False)
    _check("no broken image", summary["broken_image_marker_detected"] is False)
    _check("no data image", summary["data_image_used"] is False)
    _check("no base64", summary["base64_image_used"] is False)
    _check("no provider", summary["provider_call_made"] is False)
    _check("no generation rerun", summary["generation_rerun"] is False)
    _check("no behavior change", summary["generation_behavior_changed"] is False)
    _check("no frontend api", summary["frontend_api_changed"] is False)
    _check("no judge", summary["judge_ready"] is False)
    _check("no repair", summary["repair_ready"] is False)
    _check("blocked none", summary["blocked_by"] == "none")
    _check("next step operator read", summary["recommended_next_step"] == "operator_read_private_pipeline_hook_output")
    _check("html includes normal guide", "Bagging" in html and "Boosting" in html)
    _check("html includes table block", "What this table shows" in html and "Simplified study table" in html)
    _check("html includes figure block", "What this figure shows" in html and "Exam takeaway" in html)
    _check("html uses relative image", "<img" in html and "assets/" in html)
    _check("html no data uri", "data:image" not in html)
    _check("html no base64", "base64" not in html.lower())


def test_blocks_if_companion_missing() -> None:
    print("test_blocks_if_companion_missing")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), str(base / "missing_combined"))
    _check("blocked status", summary["status"] == "blocked")
    _check("missing companion blocker", summary["blocked_by"] == "combined_companion_not_found")


def test_blocks_if_companion_lacks_table_block() -> None:
    print("test_blocks_if_companion_lacks_table_block")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        combined = _make_combined_companion(
            base,
            summary_overrides={"role_aware_simplified_table_present": False},
            include_table=False,
        )
        summary = _run(base, _make_full_guide(base), combined)
    _check("blocked status", summary["status"] == "blocked")
    _check("missing table blocker", summary["blocked_by"] == "combined_companion_missing_table")


def test_blocks_if_companion_lacks_figure_block() -> None:
    print("test_blocks_if_companion_lacks_figure_block")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base, include_figure=False))
    _check("blocked status", summary["status"] == "blocked")
    _check("missing figure blocker", summary["blocked_by"] == "combined_companion_missing_figure")


def test_blocks_if_simplified_table_is_row_reduced_copy() -> None:
    print("test_blocks_if_simplified_table_is_row_reduced_copy")
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
    _check("row reduced blocker", summary["blocked_by"] == "combined_companion_table_row_reduced")


def test_blocks_if_figure_is_table_like_or_invalid() -> None:
    print("test_blocks_if_figure_is_table_like_or_invalid")
    for label, overrides in (
        ("table_like", {"figure_visual_is_table_like": True}),
        ("matrix", {"figure_visual_is_matrix": True}),
        ("grid", {"figure_visual_is_grid": True}),
        ("text_only", {"figure_visual_is_text_only": True}),
        ("sliver", {"figure_visual_is_partial_sliver": True}),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            summary = _run(
                base,
                _make_full_guide(base),
                _make_combined_companion(base, summary_overrides=overrides),
            )
        _check(f"blocked status {label}", summary["status"] == "blocked")
        _check(f"figure invalid blocker {label}", summary["blocked_by"] == "combined_companion_figure_table_like")


def test_blocks_if_rendered_output_contains_raw_private_path() -> None:
    print("test_blocks_if_rendered_output_contains_raw_private_path")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        full_guide = _make_full_guide(
            base,
            extra="Internal reference: local_operator_baselines should never render.\n\n",
        )
        summary = _run(base, full_guide, _make_combined_companion(base))
    _check("blocked status", summary["status"] == "blocked")
    _check("raw private path blocker", summary["blocked_by"] == "raw_private_path_in_render")


def test_refuses_data_image_or_base64() -> None:
    print("test_refuses_data_image_or_base64")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        combined = _make_combined_companion(
            base,
            extra_md="![inline](data:image/png;base64,AAAABBBBCCCC)\n\n",
        )
        summary = _run(base, _make_full_guide(base), combined)
    _check("blocked status", summary["status"] == "blocked")
    _check("data uri blocker", summary["blocked_by"] == "data_uri_or_base64_refused")


def test_preserves_safe_relative_asset_refs() -> None:
    print("test_preserves_safe_relative_asset_refs")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base))
        asset = base / "pipeline_hook_177e" / "assets" / "ensemble_structure_diagram.png"
        asset_copied = asset.is_file()
    _check("relative refs flag", summary["relative_asset_refs_preserved"] is True)
    _check("relative asset copied", asset_copied)


def test_closed_summary_no_leak_contract() -> None:
    print("test_closed_summary_no_leak_contract")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        summary = _run(base, _make_full_guide(base), _make_combined_companion(base))
        blob = json.dumps(summary)
        values_blob = " ".join(str(v) for v in summary.values()).lower()
        summary_path = base / "pipeline_hook_177e" / PIPELINE_HOOK_SUMMARY_JSON
        disk_blob = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    _check("summary excludes guide canary", _RAW_GUIDE_CANARY not in blob)
    _check("summary excludes combined canary", _RAW_COMBINED_CANARY not in blob)
    _check("summary excludes data uri", "data:image" not in values_blob)
    _check("summary excludes base64 payload", ";base64," not in values_blob and "base64" not in values_blob)
    _check("summary values have no paths", not any("/" in str(v) for v in summary.values()))
    _check("summary values have no tmp", "/tmp/" not in values_blob)
    _check("disk summary excludes canaries", _RAW_GUIDE_CANARY not in disk_blob and _RAW_COMBINED_CANARY not in disk_blob)
    _check("disk summary written", bool(disk_blob))


def main() -> int:
    test_disabled_hook_returns_unchanged_markdown()
    test_default_config_keeps_hook_disabled()
    test_private_enabled_hook_calls_177d_seam()
    test_completed_enabled_path_with_synthetic_inputs()
    test_blocks_if_companion_missing()
    test_blocks_if_companion_lacks_table_block()
    test_blocks_if_companion_lacks_figure_block()
    test_blocks_if_simplified_table_is_row_reduced_copy()
    test_blocks_if_figure_is_table_like_or_invalid()
    test_blocks_if_rendered_output_contains_raw_private_path()
    test_refuses_data_image_or_base64()
    test_preserves_safe_relative_asset_refs()
    test_closed_summary_no_leak_contract()
    if _FAILURES:
        print(f"\nFAILED: {len(_FAILURES)} check(s): {_FAILURES}")
        return 1
    print("\nAll asset companion pipeline hook tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
