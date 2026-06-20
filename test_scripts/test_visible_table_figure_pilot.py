"""Tests for the Slice 176K visible table/figure pilot (pure, public-safe synthetic).

All fixtures here are SYNTHETIC manifest-like entries (made-up category tokens, shape
counts, and tiny made-up grids) — never the private 176I artifact, never real source
values. They prove the pilot's display-only / no-laundering / privacy guards:

  * up to 3 high-value student-visible assets are selected in priority order, capped;
  * tables/captions are surfaced as display assets, figures honestly partial/unavailable;
  * no asset is ever marked numeric_verification and numeric_recompute_claimed stays
    False;
  * every committed record field is a closed token / count / bool — no raw values;
  * a missing / unsafe / empty private artifact is an honest hard blocker;
  * the private payload builder reconstructs table markdown/JSON but those live only in
    the private channel, never in the committed summary.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.visible_table_figure_pilot import (
    MAX_ASSETS_ALLOWED,
    build_closed_pilot_summary,
    build_private_asset_payload,
    descriptor_from_entry,
    extract_layout_tables_from_html,
    select_candidate_descriptors,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


# Synthetic manifest entry factory (closed signals; tiny made-up grid).
def _entry(category: str, *, rows: int, cols: int, figure: int = 0, caption: int = 1) -> dict:
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
            "figure_or_diagram_count": figure,
            "caption_count": caption,
            "text_block_count": 2,
        },
    }


_CLOSED_RAW_FLAGS = (
    "raw_ocr_committed",
    "raw_table_text_committed",
    "raw_caption_text_committed",
    "rendered_images_committed",
    "source_pdf_committed",
    "model_files_committed",
    "model_cache_committed",
)


def test_selects_priority_assets_capped_and_display_only() -> None:
    entries = [
        _entry("ensemble_proximity_matrix", rows=5, cols=5),
        _entry("ensemble_patient_dataset_table", rows=9, cols=6),
        _entry("ensemble_decision_tree_or_split_diagram", rows=5, cols=5),
        _entry("ensemble_gini_or_leaf_count", rows=9, cols=5),  # not a priority category
        _entry("ensemble_weighted_frequency_or_total_error", rows=9, cols=6),
    ]
    selected, warnings = select_candidate_descriptors(entries)
    summary = build_closed_pilot_summary(
        status="completed",
        selected=selected,
        private_artifact_available=True,
        private_artifact_gitignored=True,
        private_visible_artifact_written=True,
        private_visible_artifact_gitignored=True,
        warnings=warnings,
    )
    _check("selects exactly 3 (max)", summary["selected_assets_count"] == MAX_ASSETS_ALLOWED)
    _check("max_assets_allowed is 3", summary["max_assets_allowed"] == 3)
    cats = summary["selected_asset_categories"]
    _check("priority categories selected", set(cats) == {
        "proximity_matrix", "patient_dataset_table", "decision_tree_or_split_diagram"
    })
    _check("answer-summary category NOT selected", "gini_or_leaf_count_answer_summary" not in cats)
    _check("no asset is numeric_verification", all(
        a["display_role"] != "numeric_verification" for a in summary["assets"]
    ))
    _check("numeric_recompute_claimed False", summary["numeric_recompute_claimed"] is False)
    _check("numeric_verification_role display_only", summary["numeric_verification_role"] == "display_only")
    _check("table asset status ready", summary["table_asset_status"] == "ready")
    _check("caption status ready", summary["caption_or_context_status"] == "ready")
    _check("guide readiness off-by-default private", summary["guide_insertion_readiness"] == "ready_for_off_by_default_private_pilot")
    _check("next wire into private guide preview", summary["recommended_next_step"] == "wire_visible_assets_into_private_guide_preview")
    _check("status completed", summary["status"] == "completed")
    _check("all raw flags False", all(summary[k] is False for k in _CLOSED_RAW_FLAGS))
    _check("per-asset raw flags False", all(
        a["raw_content_committed"] is False
        and a["image_bytes_committed"] is False
        and a["private_path_committed"] is False
        for a in summary["assets"]
    ))


def test_cap_respected_when_more_than_three_priority() -> None:
    # Even if max requested is large, the ceiling is MAX_ASSETS_ALLOWED.
    entries = [
        _entry("ensemble_proximity_matrix", rows=5, cols=5),
        _entry("ensemble_patient_dataset_table", rows=9, cols=6),
        _entry("ensemble_decision_tree_or_split_diagram", rows=5, cols=5),
    ]
    selected, _ = select_candidate_descriptors(entries, max_assets=99)
    _check("ceiling enforced at 3", len(selected) == 3)


def test_diagram_is_partial_and_explanation_support() -> None:
    entries = [_entry("ensemble_decision_tree_or_split_diagram", rows=5, cols=5)]
    selected, warnings = select_candidate_descriptors(entries)
    a = selected[0]
    _check("diagram kind", a["asset_kind"] == "diagram")
    _check("diagram status partial", a["asset_status"] == "partial")
    _check("diagram role explanation_support", a["display_role"] == "explanation_support")
    _check("diagram-recovered-as-table warning", "diagram_recovered_as_table" in warnings)


def test_missing_artifact_blocks() -> None:
    summary = build_closed_pilot_summary(
        status="blocked",
        selected=[],
        private_artifact_available=False,
        private_artifact_gitignored=False,
        blocked_by="private_artifact_missing",
        warnings=["private_artifact_missing"],
    )
    _check("missing -> blocked", summary["status"] == "blocked")
    _check("missing -> blocked_by", summary["blocked_by"] == "private_artifact_missing")
    _check("missing -> 0 assets", summary["selected_assets_count"] == 0)
    _check("missing -> readiness blocked", summary["guide_insertion_readiness"] == "blocked")
    _check("missing -> next blocked", summary["recommended_next_step"] == "blocked")


def test_unsafe_path_blocks() -> None:
    summary = build_closed_pilot_summary(
        status="blocked",
        selected=[],
        private_artifact_available=False,
        private_artifact_gitignored=False,
        blocked_by="unsafe_private_artifact_path",
        warnings=["unsafe_private_artifact_path"],
    )
    _check("unsafe -> blocked", summary["status"] == "blocked")
    _check("unsafe -> blocked_by", summary["blocked_by"] == "unsafe_private_artifact_path")


def test_no_visible_assets_blocks() -> None:
    # Only non-priority categories present -> nothing selected.
    entries = [_entry("ensemble_gini_or_leaf_count", rows=9, cols=5)]
    selected, _ = select_candidate_descriptors(entries)
    _check("no priority asset selected", selected == [])
    summary = build_closed_pilot_summary(
        status="blocked",
        selected=selected,
        private_artifact_available=True,
        private_artifact_gitignored=True,
        blocked_by="no_visible_assets",
        warnings=["no_visible_assets"],
    )
    _check("no assets -> blocked", summary["status"] == "blocked")
    _check("no assets -> blocked_by", summary["blocked_by"] == "no_visible_assets")


def test_descriptor_ignores_unknown_category() -> None:
    _check("unknown category -> None", descriptor_from_entry({"slide_category": "ensemble_intro"}) is None)
    _check("non-dict -> None", descriptor_from_entry("nope") is None)


def test_private_payload_has_raw_but_summary_does_not() -> None:
    entry = _entry("ensemble_patient_dataset_table", rows=3, cols=3)
    payload = build_private_asset_payload(entry, "patient_dataset_table")
    _check("payload has markdown", isinstance(payload["table_markdown"], list) and payload["table_markdown"])
    _check("payload has json grid", isinstance(payload["table_json"], list) and payload["table_json"])
    _check("payload display_role student_visible_reference", payload["display_role"] == "student_visible_reference")
    _check("payload numeric_verification_role display_only", payload["numeric_verification_role"] == "display_only")
    # The committed summary must carry NO raw content keys.
    summary = build_closed_pilot_summary(
        status="completed",
        selected=select_candidate_descriptors([entry])[0],
        private_artifact_available=True,
        private_artifact_gitignored=True,
        private_visible_artifact_written=True,
        private_visible_artifact_gitignored=True,
    )
    forbidden = {"table_markdown", "table_json", "raw_layout_html", "normalized_context", "placement_hint"}
    _check("summary has no raw keys", not (set(summary) & forbidden))
    for a in summary["assets"]:
        _check("asset record has no raw keys", not (set(a) & forbidden))


def test_html_extraction_strips_tags() -> None:
    html = "<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>"
    grids = extract_layout_tables_from_html(html)
    _check("one table", len(grids) == 1)
    _check("stripped header", grids[0][0] == ["a", "b"])


def test_record_is_closed_vocab_only() -> None:
    entries = [
        _entry("ensemble_proximity_matrix", rows=5, cols=5),
        _entry("ensemble_patient_dataset_table", rows=9, cols=6),
    ]
    selected, warnings = select_candidate_descriptors(entries)
    summary = build_closed_pilot_summary(
        status="completed",
        selected=selected,
        private_artifact_available=True,
        private_artifact_gitignored=True,
        private_visible_artifact_written=True,
        private_visible_artifact_gitignored=True,
        warnings=warnings,
    )
    ok = True
    for key, value in summary.items():
        if key in {"selected_assets_count", "max_assets_allowed"}:
            continue  # legitimate counts
        if isinstance(value, (bool, int)):
            continue
        if isinstance(value, str):
            if any(ch.isdigit() for ch in value):
                ok = False
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and any(ch.isdigit() for ch in item):
                    ok = False
                elif isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str) and any(ch.isdigit() for ch in v):
                            ok = False
        elif not isinstance(value, dict):
            ok = False
    _check("summary -> closed vocab only (no values)", ok)


def main() -> int:
    print("test_visible_table_figure_pilot:")
    test_selects_priority_assets_capped_and_display_only()
    test_cap_respected_when_more_than_three_priority()
    test_diagram_is_partial_and_explanation_support()
    test_missing_artifact_blocks()
    test_unsafe_path_blocks()
    test_no_visible_assets_blocks()
    test_descriptor_ignores_unknown_category()
    test_private_payload_has_raw_but_summary_does_not()
    test_html_extraction_strips_tags()
    test_record_is_closed_vocab_only()
    if _FAILURES:
        print(f"test_visible_table_figure_pilot: FAILED ({len(_FAILURES)})")
        return 1
    print("test_visible_table_figure_pilot: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
