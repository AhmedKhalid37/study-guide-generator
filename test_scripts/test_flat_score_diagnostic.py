"""Public-safe tests for Slice 176O flat-score diagnostic."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.flat_score_diagnostic import (  # noqa: E402
    build_closed_flat_score_summary,
    inspect_existing_scorer_semantics,
    main as diagnostic_main,
    run_flat_score_diagnostic,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


def test_closed_summary_shape_and_safety() -> None:
    summary = build_closed_flat_score_summary(
        status="completed",
        private_baseline_guide_available=True,
        private_baseline_guide_gitignored=True,
        private_176n_guide_available=True,
        private_176n_guide_gitignored=True,
        private_score_artifacts_available=True,
        private_score_artifacts_gitignored=True,
        guide_content_difference="medium",
        ocr_specific_content_added="yes",
        visible_asset_difference="medium",
        scorer_coverage_semantics="structural_contract",
        scorer_structure_weight="high",
        scorer_deck_specific_weight="low",
        eval_insensitive_likelihood="high",
        model_prior_likelihood="low",
        packaging_weak_likelihood="low",
        flat_score_explanation="eval_insensitive",
        recommended_next_step="add_deck_specific_coverage_eval",
    )
    _check("artifact name", summary["artifact_name"] == "flat_score_diagnostic")
    _check("generation not rerun", summary["generation_rerun"] is False)
    _check("provider not called", summary["provider_call_made"] is False)
    _check("raw flags false", summary["raw_baseline_guide_committed"] is False)
    _check("prompts false", summary["prompts_committed"] is False)
    _check("responses false", summary["responses_committed"] is False)
    _check("provider payloads false", summary["provider_payloads_committed"] is False)


def test_scorer_semantics_are_structural() -> None:
    semantics = inspect_existing_scorer_semantics()
    _check("coverage semantics structural", semantics["scorer_coverage_semantics"] == "structural_contract")
    _check("structure weight high", semantics["scorer_structure_weight"] == "high")
    _check("deck weight low", semantics["scorer_deck_specific_weight"] == "low")


def test_private_diagnostic_eval_insensitive_route() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        baseline = os.path.join(tmp, "baseline.md")
        guide = os.path.join(tmp, "real_ocr_context_generated_guide.md")
        source = os.path.join(tmp, "real_ocr_context_source.md")
        visible = os.path.join(tmp, "visible_table_figure_pilot.json")
        score = os.path.join(tmp, "closed_score_result.json")
        with open(baseline, "w", encoding="utf-8") as fh:
            fh.write("# Guide\n## Big Picture\nGeneral ensemble learning overview.\n")
        with open(guide, "w", encoding="utf-8") as fh:
            fh.write(
                "# Guide\n## Big Picture\nPatient dataset table.\n"
                "Proximity matrix.\nDecision tree split diagram.\n"
            )
        with open(source, "w", encoding="utf-8") as fh:
            fh.write("Patient dataset table.\nProximity matrix.\nDecision tree split diagram.\n")
        with open(visible, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "assets": [
                        {"asset_category": "patient_dataset_table"},
                        {"asset_category": "proximity_matrix"},
                    ]
                },
                fh,
            )
        with open(score, "w", encoding="utf-8") as fh:
            json.dump({"status": "scored"}, fh)
        summary = run_flat_score_diagnostic(
            baseline_guide_path=baseline,
            guide_176n_path=guide,
            private_ocr_dir=tmp,
            private_score_artifact_dir=tmp,
        )
    _check("completed", summary["status"] == "completed")
    _check("score artifacts available", summary["private_score_artifacts_available"] is True)
    _check("guide difference high/medium", summary["guide_content_difference"] in {"high", "medium"})
    _check("ocr content added", summary["ocr_specific_content_added"] == "yes")
    _check("eval insensitive", summary["flat_score_explanation"] == "eval_insensitive")
    _check("deck eval next", summary["recommended_next_step"] == "add_deck_specific_coverage_eval")


def test_private_baseline_can_be_discovered_from_ignored_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        guide = os.path.join(tmp, "real_ocr_context_generated_guide.md")
        source = os.path.join(tmp, "real_ocr_context_source.md")
        baseline = os.path.join(tmp, "baseline_candidate.md")
        with open(guide, "w", encoding="utf-8") as fh:
            fh.write("# Guide\n## Big Picture\nPatient dataset table.\n")
        with open(source, "w", encoding="utf-8") as fh:
            fh.write("Patient dataset table.\n")
        with open(baseline, "w", encoding="utf-8") as fh:
            fh.write("# Guide\n## Big Picture\nGeneral ensemble learning overview.\n")
        summary = run_flat_score_diagnostic(
            baseline_guide_dir=tmp,
            guide_176n_path=guide,
            private_ocr_dir=tmp,
        )
    _check("discovered baseline", summary["private_baseline_guide_available"] is True)
    _check("discovered guide", summary["private_176n_guide_available"] is True)


def test_missing_artifacts_blocks() -> None:
    summary = run_flat_score_diagnostic()
    _check("blocked without artifacts", summary["status"] == "blocked")
    _check("next blocked", summary["recommended_next_step"] == "blocked")


def test_runner_prints_closed_summary() -> None:
    out = StringIO()
    with redirect_stdout(out):
        rc = diagnostic_main()
    text = out.getvalue()
    _check("runner exits blocked without env", rc == 2)
    _check("runner prints artifact name", '"artifact_name": "flat_score_diagnostic"' in text)
    _check("runner no generation", '"generation_rerun": false' in text)


def main() -> int:
    print("test_flat_score_diagnostic:")
    test_closed_summary_shape_and_safety()
    test_scorer_semantics_are_structural()
    test_private_diagnostic_eval_insensitive_route()
    test_private_baseline_can_be_discovered_from_ignored_dir()
    test_missing_artifacts_blocks()
    test_runner_prints_closed_summary()
    if _FAILURES:
        print(f"test_flat_score_diagnostic: FAILED ({len(_FAILURES)})")
        return 1
    print("test_flat_score_diagnostic: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
