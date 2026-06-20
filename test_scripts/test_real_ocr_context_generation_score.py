"""Tests for Slice 176N real OCR-context generation closed summary.

Fixtures are synthetic and public-safe. The tests do not call a provider; they prove
the source-material packaging, closed vocabularies, honest no-stub routing, and the
env-driven runner's blocked path when no generation client is available.
"""
from __future__ import annotations

import os
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.real_ocr_context_generation import (
    build_closed_generation_summary,
    build_ocr_context_source_text,
    generation_mode_for_provider,
    main as real_generation_main,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


def _entry(category: str, *, page: int = 1, rows: int = 3, cols: int = 3) -> dict:
    grid = "<table>" + "".join(
        "<tr>" + "".join(f"<td>r{r}c{c}</td>" for c in range(cols)) + "</tr>"
        for r in range(rows)
    ) + "</table>"
    return {
        "page": page,
        "slide_category": category,
        "raw_layout_html": grid,
        "signals": {
            "has_table": True,
            "max_table_rows": rows,
            "max_table_cols": cols,
            "caption_count": 1,
            "text_block_count": 1,
        },
    }


_CLOSED_RAW_FLAGS = (
    "raw_ocr_committed",
    "raw_guide_text_committed",
    "raw_table_text_committed",
    "raw_caption_text_committed",
    "rendered_guide_committed",
    "source_pdf_committed",
    "prompts_committed",
    "responses_committed",
    "provider_payloads_committed",
)


def test_source_text_packages_real_context_not_guide_stub() -> None:
    entries = [
        _entry("ensemble_proximity_matrix", page=2, rows=4, cols=4),
        _entry("ensemble_patient_dataset_table", page=3, rows=5, cols=3),
    ]
    payload = {
        "assets": [
            {
                "asset_category": "patient_dataset_table",
                "table_markdown": ["| a | b |\n| --- | --- |\n| x | y |"],
            }
        ]
    }
    source, stats = build_ocr_context_source_text(
        entries, source_label="Ensemble", visible_payload=payload
    )
    _check("source text is non-empty", isinstance(source, str) and len(source) > 80)
    _check("uses page anchors", "## Page 2" in source and "## Page 3" in source)
    _check("surfaces markdown tables", "| ---" in source)
    _check("records section count", stats["section_count"] == 2)
    _check("records visible category", stats["visible_asset_categories"] == ["patient_dataset_table"])


def test_generation_mode_mapping_is_closed() -> None:
    _check("local mode", generation_mode_for_provider("local") == "existing_local_provider")
    _check("configured mode", generation_mode_for_provider("deepseek") == "existing_configured_provider")
    _check("unknown unavailable", generation_mode_for_provider("other") == "generation_unavailable")


def test_closed_summary_is_safe_and_no_stub_mode() -> None:
    summary = build_closed_generation_summary(
        status="completed",
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=True,
        private_visible_artifact_available=True,
        private_visible_artifact_gitignored=True,
        private_generated_guide_written=True,
        private_generated_guide_gitignored=True,
        generation_mode="existing_configured_provider",
        visible_assets_used="yes",
        selected_visible_asset_categories=["proximity_matrix", "patient_dataset_table"],
        guide_artifact_status="generated",
        render_status="not_run",
        score_status="scored",
        baseline_comparison_status="improved",
        coverage_signal="improved",
        figure_table_signal="improved",
    )
    _check("artifact name", summary["artifact_name"] == "real_ocr_context_generation_score")
    _check("real generation mode", summary["generation_mode"] == "existing_configured_provider")
    _check("generated status", summary["guide_artifact_status"] == "generated")
    _check("stub confound false", summary["stub_vs_full_confounded"] is False)
    _check("numeric not claimed", summary["numeric_verification_claimed"] is False)
    _check("judge frozen", summary["judge_ready"] is False)
    _check("repair frozen", summary["repair_ready"] is False)
    _check("normal behavior unchanged", summary["generation_behavior_changed"] is False)
    _check("frontend/api unchanged", summary["frontend_api_changed"] is False)
    _check("all raw flags false", all(summary[k] is False for k in _CLOSED_RAW_FLAGS))
    _check(
        "improved routes to harden path",
        summary["recommended_next_step"] == "harden_off_by_default_ocr_context_generation_path",
    )


def test_deterministic_stub_mode_is_rejected_by_closed_summary() -> None:
    summary = build_closed_generation_summary(
        status="completed",
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=True,
        generation_mode="deterministic_stub_preview",
    )
    _check("stub mode coerces to not_run", summary["generation_mode"] == "not_run")


def test_main_blocks_without_existing_generation_client() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        manifest = os.path.join(tmp, "extracted_content_manifest.json")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write('{"entries":[{"slide_category":"ensemble_proximity_matrix","raw_layout_html":"<table><tr><td>x</td></tr></table>","signals":{"has_table":true}}]}')
        env = {
            "PRIVATE_OCR_DIR": tmp,
            "SOURCE_LABEL": "ensemble",
            "INCLUDE_VISIBLE_ASSETS": "0",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch(
                "pipeline.real_ocr_context_generation._resolve_generation_config",
                return_value=(None, "none", "provider_unavailable"),
            ):
                out = StringIO()
                with redirect_stdout(out):
                    rc = real_generation_main()
        text = out.getvalue()
    _check("main exits blocked", rc == 2)
    _check("blocked summary printed", '"status": "blocked"' in text)
    _check("guide not generated", '"guide_artifact_status": "blocked"' in text)
    _check("generation unavailable", '"generation_mode": "generation_unavailable"' in text)


def main() -> int:
    print("test_real_ocr_context_generation_score:")
    test_source_text_packages_real_context_not_guide_stub()
    test_generation_mode_mapping_is_closed()
    test_closed_summary_is_safe_and_no_stub_mode()
    test_deterministic_stub_mode_is_rejected_by_closed_summary()
    test_main_blocks_without_existing_generation_client()
    if _FAILURES:
        print(f"test_real_ocr_context_generation_score: FAILED ({len(_FAILURES)})")
        return 1
    print("test_real_ocr_context_generation_score: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
