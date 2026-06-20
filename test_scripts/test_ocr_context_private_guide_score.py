"""Tests for the Slice 176L OCR-context private guide preview + closed score.

All fixtures here are SYNTHETIC manifest-like entries (made-up category tokens, tiny
made-up grids) and synthetic lint reports — never the private 176I artifact, never a
real guide, never real source values. They prove:

  * a student-readable preview markdown is assembled from OCR entries, with recovered
    tables surfaced and a comprehensive-style scaffold;
  * the 176K visible-asset payload is embedded when present;
  * scoring runs through the existing deterministic contract lint (no LLM);
  * the baseline comparison is deterministic, closed, and honestly ``unavailable``
    without a baseline;
  * the committed summary is closed-vocab only (tokens/bools, no raw values), with all
    ``*_committed`` flags + ``numeric_verification_claimed`` + judge/repair False.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.ocr_context_private_guide import (
    build_closed_score_summary,
    build_ocr_context_guide_markdown,
    derive_baseline_comparison,
    score_guide_markdown,
    visible_assets_token,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


def _entry(category: str, *, rows: int, cols: int, caption: int = 1) -> dict:
    grid = "<table>" + "".join(
        "<tr>" + "".join(f"<td>r{r}c{c}</td>" for c in range(cols)) + "</tr>"
        for r in range(rows)
    ) + "</table>"
    return {
        "slide_category": category,
        "raw_layout_html": grid,
        "normalized": {"blocks": ["synthetic"]},
        "signals": {
            "max_table_rows": rows,
            "max_table_cols": cols,
            "has_table": True,
            "figure_or_diagram_count": 0,
            "caption_count": caption,
            "text_block_count": 2,
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


def test_preview_markdown_surfaces_tables() -> None:
    entries = [
        _entry("ensemble_proximity_matrix", rows=5, cols=5),
        _entry("ensemble_patient_dataset_table", rows=9, cols=6),
    ]
    md, stats = build_ocr_context_guide_markdown(entries, source_label="ensemble")
    _check("markdown is non-empty string", isinstance(md, str) and len(md) > 50)
    _check("has reference tables heading", "## Reference Tables" in md)
    _check("has comprehensive scaffold", "## Summary" in md and "## Overview" in md)
    _check("recovered at least 2 tables", stats["table_count"] >= 2)
    _check("section count is 2", stats["section_count"] == 2)
    _check("renders a markdown table row", "| ---" in md)


def test_visible_payload_is_embedded() -> None:
    entries = [_entry("ensemble_patient_dataset_table", rows=3, cols=3)]
    payload = {
        "assets": [
            {
                "asset_category": "patient_dataset_table",
                "table_markdown": ["| a | b |\n| --- | --- |\n| 1 | 2 |"],
            }
        ]
    }
    md, stats = build_ocr_context_guide_markdown(entries, visible_payload=payload)
    _check("visible category recorded", "patient_dataset_table" in stats["visible_asset_categories"])
    _check("visible token partial/yes", visible_assets_token(stats["visible_asset_categories"]) in {"partial", "yes"})
    _check("payload markdown embedded", "| a | b |" in md)


def test_score_runs_through_contract_lint() -> None:
    entries = [_entry("ensemble_proximity_matrix", rows=5, cols=5)]
    md, _ = build_ocr_context_guide_markdown(entries)
    report = score_guide_markdown(md)
    _check("lint report is a dict", isinstance(report, dict))
    _check("lint kind is contract lint", report.get("kind") == "guide_quality_contract_lint")
    _check("lint status not skipped", report.get("status") != "skipped")
    _check("lint summary has table_count", isinstance(report.get("summary", {}).get("table_count"), int))


def test_comparison_improved_when_candidate_richer() -> None:
    cand = {
        "kind": "guide_quality_contract_lint",
        "status": "completed",
        "summary": {
            "table_count": 3,
            "required_section_present_count": 6,
            "exam_alert_count": 1,
            "reasoning_leak_count": 0,
            "warning_count": 0,
        },
    }
    base = {
        "kind": "guide_quality_contract_lint",
        "status": "completed",
        "summary": {
            "table_count": 0,
            "required_section_present_count": 4,
            "exam_alert_count": 0,
            "reasoning_leak_count": 0,
            "warning_count": 2,
        },
    }
    sig = derive_baseline_comparison(cand, base)
    _check("score_status scored", sig["score_status"] == "scored")
    _check("baseline improved", sig["baseline_comparison_status"] == "improved")
    _check("figure_table improved", sig["figure_table_signal"] == "improved")
    _check("coverage improved", sig["coverage_signal"] == "improved")


def test_comparison_unavailable_without_baseline() -> None:
    cand = {
        "kind": "guide_quality_contract_lint",
        "status": "completed",
        "summary": {"table_count": 2, "required_section_present_count": 5, "warning_count": 1},
    }
    sig = derive_baseline_comparison(cand, None)
    _check("score_status scored", sig["score_status"] == "scored")
    _check("baseline unavailable", sig["baseline_comparison_status"] == "unavailable")
    _check("figure_table unavailable", sig["figure_table_signal"] == "unavailable")
    _check("coverage unavailable", sig["coverage_signal"] == "unavailable")


def test_comparison_not_available_without_candidate() -> None:
    sig = derive_baseline_comparison({"status": "skipped"}, None)
    _check("score not_available", sig["score_status"] == "not_available")
    _check("baseline unavailable", sig["baseline_comparison_status"] == "unavailable")


def test_closed_summary_is_safe_and_closed() -> None:
    summary = build_closed_score_summary(
        status="completed",
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=True,
        private_visible_artifact_available=True,
        private_visible_artifact_gitignored=True,
        private_guide_artifact_written=True,
        private_guide_artifact_gitignored=True,
        generation_mode="deterministic_stub_preview",
        visible_assets_used="partial",
        selected_visible_asset_categories=["patient_dataset_table"],
        guide_artifact_status="preview_generated",
        render_status="not_run",
        score_status="scored",
        baseline_comparison_status="improved",
        coverage_signal="improved",
        figure_table_signal="improved",
    )
    _check("artifact_name", summary["artifact_name"] == "ocr_context_private_guide_score")
    _check("status completed", summary["status"] == "completed")
    _check("generation_mode preview", summary["generation_mode"] == "deterministic_stub_preview")
    _check("guide preview_generated", summary["guide_artifact_status"] == "preview_generated")
    _check("numeric not claimed", summary["numeric_verification_claimed"] is False)
    _check("judge frozen", summary["judge_ready"] is False)
    _check("repair frozen", summary["repair_ready"] is False)
    _check("cloud ocr false", summary["cloud_ocr_used"] is False)
    _check("generation behavior unchanged", summary["generation_behavior_changed"] is False)
    _check("frontend/api unchanged", summary["frontend_api_changed"] is False)
    _check("all raw flags False", all(summary[k] is False for k in _CLOSED_RAW_FLAGS))
    _check("improved -> harden next step", summary["recommended_next_step"] == "build_off_by_default_ocr_context_generation_path")

    # Closed-vocab only: no string field carries a digit (no raw values leaked).
    ok = True
    for key, value in summary.items():
        if isinstance(value, (bool, int)):
            continue
        if isinstance(value, str):
            if any(ch.isdigit() for ch in value):
                ok = False
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and any(ch.isdigit() for ch in item):
                    ok = False
        else:
            ok = False
    _check("summary closed vocab only (no values)", ok)


def test_regressed_stub_routes_to_real_generation_path() -> None:
    # A deterministic stub that does not beat a full baseline is a known confound; the
    # honest next step is the real off-by-default OCR-context generation path.
    summary = build_closed_score_summary(
        status="completed",
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=True,
        private_guide_artifact_written=True,
        private_guide_artifact_gitignored=True,
        generation_mode="deterministic_stub_preview",
        visible_assets_used="yes",
        selected_visible_asset_categories=["proximity_matrix", "patient_dataset_table"],
        guide_artifact_status="preview_generated",
        score_status="scored",
        baseline_comparison_status="regressed",
        coverage_signal="regressed",
        figure_table_signal="unchanged",
    )
    _check(
        "regressed stub -> build real generation path",
        summary["recommended_next_step"] == "build_off_by_default_ocr_context_generation_path",
    )


def test_blocked_summary_next_step() -> None:
    summary = build_closed_score_summary(
        status="blocked",
        private_ocr_artifact_available=False,
        private_ocr_artifact_gitignored=False,
        blocked_by="private_artifact_missing",
        recommended_next_step="blocked",
    )
    _check("blocked status", summary["status"] == "blocked")
    _check("blocked_by", summary["blocked_by"] == "private_artifact_missing")
    _check("blocked next step", summary["recommended_next_step"] == "blocked")


def main() -> int:
    print("test_ocr_context_private_guide_score:")
    test_preview_markdown_surfaces_tables()
    test_visible_payload_is_embedded()
    test_score_runs_through_contract_lint()
    test_comparison_improved_when_candidate_richer()
    test_comparison_unavailable_without_baseline()
    test_comparison_not_available_without_candidate()
    test_closed_summary_is_safe_and_closed()
    test_regressed_stub_routes_to_real_generation_path()
    test_blocked_summary_next_step()
    if _FAILURES:
        print(f"test_ocr_context_private_guide_score: FAILED ({len(_FAILURES)})")
        return 1
    print("test_ocr_context_private_guide_score: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
