"""Public-safe tests for Slice 176S uncommon-deck coverage eval."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.deck_specific_coverage_eval import (  # noqa: E402
    build_closed_uncommon_deck_coverage_summary,
    run_uncommon_deck_coverage_eval,
    uncommon_deck_coverage_main,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


@contextmanager
def _env(values: dict[str, str]):
    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, prior in old.items():
            if prior is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior


def _write_inputs(
    tmp: str,
    *,
    baseline_text: str,
    generated_text: str,
    categories: list[str] | None = None,
    has_record: bool = True,
) -> tuple[str, str, str]:
    baseline = os.path.join(tmp, "candidate_baseline.md")
    generated = os.path.join(tmp, "GuideForge_candidate.md")
    artifact = os.path.join(tmp, "uncommon_deck_local_ocr_artifact.json")
    with open(baseline, "w", encoding="utf-8") as fh:
        fh.write(baseline_text)
    with open(generated, "w", encoding="utf-8") as fh:
        fh.write(generated_text)
    entries = [{"closed_categories": categories or []}] if has_record else []
    with open(artifact, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "artifact_name": "uncommon_deck_local_ocr_extraction",
                "source_label": "candidate_1",
                "closed_categories": categories or [],
                "entries": entries,
            },
            fh,
        )
    return baseline, generated, artifact


def test_closed_summary_shape_and_safety() -> None:
    summary = build_closed_uncommon_deck_coverage_summary(
        status="completed",
        private_baseline_guide_available=True,
        private_baseline_guide_gitignored=True,
        private_generated_guide_available=True,
        private_generated_guide_gitignored=True,
        private_ocr_artifact_available=True,
        private_ocr_artifact_gitignored=True,
        marker_source="closed_static_ids",
        marker_candidate_status="partial",
        markers=[
            {
                "marker_id": "uncommon_text_layer_content",
                "marker_source": "closed_static_ids",
                "baseline_status": "absent",
                "generated_status": "present",
                "delta": "improved",
            }
        ],
    )
    _check("artifact name", summary["artifact_name"] == "uncommon_deck_coverage_eval")
    _check("candidate label", summary["source_label"] == "candidate_1")
    _check("provider false", summary["provider_call_made"] is False)
    _check("generation false", summary["generation_rerun"] is False)
    _check("ocr false", summary["ocr_rerun"] is False)
    _check("raw baseline false", summary["raw_baseline_guide_committed"] is False)
    _check("raw generated false", summary["raw_generated_guide_committed"] is False)
    _check("raw ocr false", summary["raw_ocr_committed"] is False)
    _check("prompts false", summary["prompts_committed"] is False)
    _check("responses false", summary["responses_committed"] is False)
    _check("payloads false", summary["provider_payloads_committed"] is False)
    _check("no scorer mutation", summary["should_modify_contract_scorer"] == "no")


def test_baseline_low_generated_high_improved() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        baseline, generated, artifact = _write_inputs(
            tmp,
            baseline_text="general overview",
            generated_text=(
                "definition and concept section. example case and worked scenario. "
                "question exercise and practice assessment."
            ),
            categories=["concept_or_definition", "example_or_case", "assessment_or_question"],
        )
        summary = run_uncommon_deck_coverage_eval(
            baseline_guide_path=baseline,
            generated_guide_path=generated,
            uncommon_ocr_artifact_path=artifact,
        )
    _check("completed", summary["status"] == "completed")
    _check("generated high", summary["generated_deck_specific_coverage"] == "high")
    _check("improved", summary["deck_specific_coverage_delta"] == "improved")
    _check("provider yes", summary["should_run_provider_generation"] == "yes")
    _check("next real generation", summary["recommended_next_step"] == "run_real_ocr_context_generation_for_candidate_1")


def test_both_high_unchanged_pivots() -> None:
    text = (
        "definition concept principle. example case scenario. question quiz exercise. "
        "table dataset row column."
    )
    with tempfile.TemporaryDirectory() as tmp:
        baseline, generated, artifact = _write_inputs(
            tmp,
            baseline_text=text,
            generated_text=text,
            categories=["concept_or_definition", "example_or_case", "assessment_or_question", "table_like"],
        )
        summary = run_uncommon_deck_coverage_eval(
            baseline_guide_path=baseline,
            generated_guide_path=generated,
            uncommon_ocr_artifact_path=artifact,
        )
    _check("both high baseline", summary["baseline_deck_specific_coverage"] == "high")
    _check("both high generated", summary["generated_deck_specific_coverage"] == "high")
    _check("unchanged", summary["deck_specific_coverage_delta"] == "unchanged")
    _check("pivot", summary["recommended_next_step"] == "pivot_to_rendered_visible_asset_insertion")


def test_both_low_weak_markers_recommends_better_ocr() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        baseline, generated, artifact = _write_inputs(
            tmp,
            baseline_text="overview",
            generated_text="overview",
            categories=[],
            has_record=True,
        )
        summary = run_uncommon_deck_coverage_eval(
            baseline_guide_path=baseline,
            generated_guide_path=generated,
            uncommon_ocr_artifact_path=artifact,
        )
    _check("degraded", summary["status"] == "degraded")
    _check("closed static", summary["marker_source"] == "closed_static_ids")
    _check("partial marker status", summary["marker_candidate_status"] == "partial")
    _check("low reliability", summary["marker_reliability"] == "low")
    _check("better ocr", summary["should_run_better_ocr"] == "yes")
    _check("next improve extraction", summary["recommended_next_step"] == "improve_candidate_1_ocr_extraction")


def test_generated_regressed_routes_to_fixture_quality() -> None:
    baseline_text = "definition concept principle. example case scenario. question quiz exercise."
    with tempfile.TemporaryDirectory() as tmp:
        baseline, generated, artifact = _write_inputs(
            tmp,
            baseline_text=baseline_text,
            generated_text="brief overview",
            categories=["concept_or_definition", "example_or_case", "assessment_or_question"],
        )
        summary = run_uncommon_deck_coverage_eval(
            baseline_guide_path=baseline,
            generated_guide_path=generated,
            uncommon_ocr_artifact_path=artifact,
        )
    _check("regressed", summary["deck_specific_coverage_delta"] == "regressed")
    _check("no provider", summary["should_run_provider_generation"] == "no")
    _check("collect fixture", summary["recommended_next_step"] == "collect_better_uncommon_fixture")


def test_no_raw_text_in_summary_and_runner_closed() -> None:
    raw_baseline = "PUBLIC_SAFE_BASELINE_CANARY"
    raw_generated = "PUBLIC_SAFE_GENERATED_CANARY"
    with tempfile.TemporaryDirectory() as tmp:
        baseline, generated, artifact = _write_inputs(
            tmp,
            baseline_text=raw_baseline,
            generated_text=raw_generated,
            categories=[],
            has_record=True,
        )
        summary = run_uncommon_deck_coverage_eval(
            baseline_guide_path=baseline,
            generated_guide_path=generated,
            uncommon_ocr_artifact_path=artifact,
        )
        rendered = json.dumps(summary)
        out = StringIO()
        with _env(
            {
                "BASELINE_GUIDE_MD": baseline,
                "GENERATED_GUIDE_MD": generated,
                "UNCOMMON_OCR_ARTIFACT_JSON": artifact,
            }
        ), redirect_stdout(out):
            rc = uncommon_deck_coverage_main()
    _check("raw baseline absent", raw_baseline not in rendered)
    _check("raw generated absent", raw_generated not in rendered)
    _check("runner ok", rc == 0)
    _check("runner artifact", '"artifact_name": "uncommon_deck_coverage_eval"' in out.getvalue())
    _check("runner no provider", '"provider_call_made": false' in out.getvalue())


def main() -> int:
    print("test_uncommon_deck_coverage_eval:")
    test_closed_summary_shape_and_safety()
    test_baseline_low_generated_high_improved()
    test_both_high_unchanged_pivots()
    test_both_low_weak_markers_recommends_better_ocr()
    test_generated_regressed_routes_to_fixture_quality()
    test_no_raw_text_in_summary_and_runner_closed()
    if _FAILURES:
        print(f"test_uncommon_deck_coverage_eval: FAILED ({len(_FAILURES)})")
        return 1
    print("test_uncommon_deck_coverage_eval: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
