"""Public-safe tests for Slice 176P deck-specific coverage eval."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.deck_specific_coverage_eval import (  # noqa: E402
    build_closed_deck_specific_coverage_summary,
    main as coverage_main,
    run_deck_specific_coverage_eval,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


def test_closed_summary_shape_and_safety() -> None:
    summary = build_closed_deck_specific_coverage_summary(
        status="completed",
        private_baseline_guide_available=True,
        private_baseline_guide_gitignored=True,
        private_176n_guide_available=True,
        private_176n_guide_gitignored=True,
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=True,
        private_visible_artifact_available=True,
        private_visible_artifact_gitignored=True,
        marker_source="private_artifact_categories",
        markers=[
            {
                "marker_id": "patient_dataset_table",
                "marker_source": "private_artifact_categories",
                "baseline_status": "absent",
                "ocr_context_status": "present",
                "delta": "improved",
            }
        ],
    )
    _check("artifact name", summary["artifact_name"] == "deck_specific_coverage_eval")
    _check("generation not rerun", summary["generation_rerun"] is False)
    _check("provider not called", summary["provider_call_made"] is False)
    _check("raw guide flags false", summary["raw_baseline_guide_committed"] is False)
    _check("prompts false", summary["prompts_committed"] is False)
    _check("responses false", summary["responses_committed"] is False)
    _check("provider payloads false", summary["provider_payloads_committed"] is False)
    _check("diagnostic role", summary["coverage_eval_role"] == "diagnostic")
    _check("no scorer mutation", summary["should_modify_contract_scorer"] == "no")


def test_status_deltas() -> None:
    summary = build_closed_deck_specific_coverage_summary(
        status="completed",
        marker_source="closed_static_ids",
        markers=[
            {
                "marker_id": "patient_dataset_table",
                "marker_source": "closed_static_ids",
                "baseline_status": "absent",
                "ocr_context_status": "present",
                "delta": "improved",
            },
            {
                "marker_id": "proximity_matrix",
                "marker_source": "closed_static_ids",
                "baseline_status": "present",
                "ocr_context_status": "present",
                "delta": "unchanged",
            },
            {
                "marker_id": "decision_tree_or_split_diagram",
                "marker_source": "closed_static_ids",
                "baseline_status": "present",
                "ocr_context_status": "absent",
                "delta": "regressed",
            },
            {
                "marker_id": "weighted_frequency_or_total_error",
                "marker_source": "closed_static_ids",
                "baseline_status": "absent",
                "ocr_context_status": "partial",
                "delta": "improved",
            },
        ],
    )
    deltas = {m["marker_id"]: m["delta"] for m in summary["markers"]}
    _check("absent to present improved", deltas["patient_dataset_table"] == "improved")
    _check("both present unchanged", deltas["proximity_matrix"] == "unchanged")
    _check("present to absent regressed", deltas["decision_tree_or_split_diagram"] == "regressed")
    _check("partial handled", deltas["weighted_frequency_or_total_error"] == "improved")


def test_private_eval_improved() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        baseline = os.path.join(tmp, "baseline.md")
        guide = os.path.join(tmp, "real_ocr_context_generated_guide.md")
        manifest = os.path.join(tmp, "extracted_content_manifest.json")
        visible = os.path.join(tmp, "visible_table_figure_pilot.json")
        with open(baseline, "w", encoding="utf-8") as fh:
            fh.write("# Guide\nGeneral ensemble overview.\n")
        with open(guide, "w", encoding="utf-8") as fh:
            fh.write(
                "# Guide\nPatient dataset table.\n"
                "Proximity matrix and terminal node explanation.\n"
                "Decision tree split diagram with leaf node practice.\n"
            )
        with open(manifest, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "entries": [
                        {"slide_category": "ensemble_patient_dataset_table"},
                        {"slide_category": "ensemble_proximity_matrix"},
                        {"slide_category": "ensemble_decision_tree_or_split_diagram"},
                    ]
                },
                fh,
            )
        with open(visible, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "assets": [
                        {"asset_category": "patient_dataset_table"},
                        {"asset_category": "decision_tree_or_split_diagram"},
                    ]
                },
                fh,
            )
        summary = run_deck_specific_coverage_eval(
            baseline_guide_path=baseline,
            guide_176n_path=guide,
            private_ocr_dir=tmp,
            visible_artifact_path=visible,
        )
    _check("completed", summary["status"] == "completed")
    _check("marker source private", summary["marker_source"] == "private_artifact_categories")
    _check("deck coverage improved", summary["deck_specific_coverage_delta"] == "improved")
    _check("next advisory", summary["recommended_next_step"] == "integrate_deck_specific_coverage_as_advisory_eval")
    _check("closed marker ids only", all("marker_id" in m and "baseline_status" in m for m in summary["markers"]))


def test_nonprivate_paths_are_refused() -> None:
    summary = run_deck_specific_coverage_eval(
        baseline_guide_path=__file__,
        guide_176n_path=__file__,
        private_ocr_dir=os.path.dirname(__file__),
    )
    _check("blocked for nonprivate paths", summary["status"] == "blocked")
    _check("baseline unavailable", summary["private_baseline_guide_available"] is False)
    _check("guide unavailable", summary["private_176n_guide_available"] is False)
    _check("next blocked", summary["recommended_next_step"] == "blocked")


def test_runner_prints_closed_summary() -> None:
    out = StringIO()
    with redirect_stdout(out):
        rc = coverage_main()
    text = out.getvalue()
    _check("runner exits blocked without env", rc == 2)
    _check("runner prints artifact name", '"artifact_name": "deck_specific_coverage_eval"' in text)
    _check("runner no generation", '"generation_rerun": false' in text)


def main() -> int:
    print("test_deck_specific_coverage_eval:")
    test_closed_summary_shape_and_safety()
    test_status_deltas()
    test_private_eval_improved()
    test_nonprivate_paths_are_refused()
    test_runner_prints_closed_summary()
    if _FAILURES:
        print(f"test_deck_specific_coverage_eval: FAILED ({len(_FAILURES)})")
        return 1
    print("test_deck_specific_coverage_eval: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
