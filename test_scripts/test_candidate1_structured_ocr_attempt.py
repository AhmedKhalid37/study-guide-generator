"""Public-safe tests for Slice 176T candidate_1 structured OCR attempt."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.candidate1_structured_ocr_attempt import (  # noqa: E402
    build_closed_candidate1_structured_ocr_attempt_summary,
    main as attempt_main,
    run_candidate1_structured_ocr_attempt,
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


def _touch_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% public-safe synthetic test fixture\n")


def test_closed_summary_shape_and_safety() -> None:
    summary = build_closed_candidate1_structured_ocr_attempt_summary(
        status="completed",
        private_source_available=True,
        private_source_gitignored=True,
        private_improved_ocr_artifact_written=True,
        private_improved_ocr_artifact_gitignored=True,
        ocr_rerun=True,
        attempted_structured_ocr=True,
        structured_ocr_engine="tesseract_cli",
        structured_ocr_status="ran",
        local_ocr_engine="tesseract_cli",
        local_ocr_status="ran",
        marker_candidate_status="available",
        marker_source="private_artifact_categories",
        marker_reliability="medium",
        improvement_over_176r="partial",
        next_test_readiness="ready_for_uncommon_deck_coverage_eval",
        recommended_next_step="rerun_uncommon_deck_coverage_eval",
    )
    _check("artifact name", summary["artifact_name"] == "candidate1_structured_ocr_attempt")
    _check("candidate label", summary["source_label"] == "candidate_1")
    _check("previous engine", summary["previous_extraction_engine"] == "text_layer")
    _check("previous reliability", summary["previous_marker_reliability"] == "low")
    _check("provider false", summary["provider_call_made"] is False)
    _check("generation false", summary["generation_rerun"] is False)
    _check("coverage false", summary["coverage_eval_rerun"] is False)
    _check("cloud false", summary["cloud_ocr_used"] is False)
    _check("raw source false", summary["raw_source_committed"] is False)
    _check("raw ocr false", summary["raw_ocr_committed"] is False)
    _check("raw table false", summary["raw_table_text_committed"] is False)
    _check("raw caption false", summary["raw_caption_text_committed"] is False)
    _check("prompts false", summary["prompts_committed"] is False)
    _check("responses false", summary["responses_committed"] is False)
    _check("payloads false", summary["provider_payloads_committed"] is False)
    _check("no broad framework", summary["broad_ocr_framework_built"] is False)


def test_structured_unavailable_text_fallback_no_improvement() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_candidate1_structured_ocr_attempt(
            source_path=str(source),
            private_ocr_dir=out,
            tesseract_enabled=False,
            text_pages_override=["plain lecture content"],
        )
    _check("degraded", summary["status"] == "degraded")
    _check("structured unavailable", summary["structured_ocr_status"] == "unavailable")
    _check("fallback text", summary["fallback_engine"] == "text_layer")
    _check("local text", summary["local_ocr_engine"] == "text_layer")
    _check("no improvement", summary["improvement_over_176r"] == "no")
    _check("needs better", summary["next_test_readiness"] == "needs_better_ocr")


def test_structured_richer_categories_improves_reliability() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_candidate1_structured_ocr_attempt(
            source_path=str(source),
            private_ocr_dir=out,
            structured_records_override=[
                {
                    "raw_text": "PUBLIC_SAFE_STRUCTURED_CANARY",
                    "closed_categories": [
                        "text_layer_content",
                        "concept_or_definition",
                        "example_or_case",
                        "table_like",
                    ],
                    "table_like_count": 2,
                    "figure_or_diagram_like_count": 0,
                    "text_block_present": True,
                }
            ],
        )
        artifact = Path(out) / "candidate1_structured_ocr_attempt_artifact.json"
        artifact_exists = artifact.exists()
    _check("completed", summary["status"] == "completed")
    _check("structured ran", summary["structured_ocr_status"] == "ran")
    _check("medium reliability", summary["marker_reliability"] == "medium")
    _check("improved", summary["improvement_over_176r"] == "yes")
    _check("ready eval", summary["next_test_readiness"] == "ready_for_uncommon_deck_coverage_eval")
    _check("next rerun coverage", summary["recommended_next_step"] == "rerun_uncommon_deck_coverage_eval")
    _check("private artifact", artifact_exists)


def test_text_layer_fallback_does_not_count_as_improvement() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_candidate1_structured_ocr_attempt(
            source_path=str(source),
            private_ocr_dir=out,
            tesseract_enabled=False,
            text_pages_override=["table matrix dataset definition example"],
        )
    _check("fallback only", summary["fallback_engine"] == "text_layer")
    _check("low reliability", summary["marker_reliability"] == "low")
    _check("no improvement despite categories", summary["improvement_over_176r"] == "no")
    _check("improved artifact false", summary["private_improved_ocr_artifact_written"] is False)


def test_no_raw_ocr_text_in_committed_summary() -> None:
    raw = "PUBLIC_SAFE_RAW_OCR_CANARY"
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_candidate1_structured_ocr_attempt(
            source_path=str(source),
            private_ocr_dir=out,
            structured_records_override=[
                {
                    "raw_text": raw,
                    "closed_categories": ["concept_or_definition", "example_or_case", "table_like"],
                    "table_like_count": 1,
                    "text_block_present": True,
                }
            ],
        )
    rendered = json.dumps(summary)
    _check("raw absent", raw not in rendered)
    _check("private source path absent", private_root not in rendered)
    _check("private out path absent", out not in rendered)


def test_private_paths_refused_if_not_gitignored() -> None:
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as unsafe_root, tempfile.TemporaryDirectory() as out:
        source = Path(unsafe_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_candidate1_structured_ocr_attempt(
            source_path=str(source),
            private_ocr_dir=out,
            structured_records_override=[
                {"closed_categories": ["concept_or_definition"], "text_block_present": True}
            ],
        )
    _check("blocked", summary["status"] == "blocked")
    _check("unsafe blocker", summary["blocked_by"] == "unsafe_private_artifact_path")
    _check("source not gitignored", summary["private_source_gitignored"] is False)


def test_runner_prints_closed_summary() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        out_stream = StringIO()
        with _env(
            {
                "CANDIDATE_SOURCE_PATH": str(source),
                "PRIVATE_OCR_DIR": out,
                "TESSERACT_ENABLED": "0",
            }
        ), redirect_stdout(out_stream):
            rc = attempt_main()
        text = out_stream.getvalue()
    _check("runner exits blocked without text", rc == 2)
    _check("runner artifact name", '"artifact_name": "candidate1_structured_ocr_attempt"' in text)
    _check("runner no provider", '"provider_call_made": false' in text)
    _check("runner no generation", '"generation_rerun": false' in text)
    _check("runner no coverage", '"coverage_eval_rerun": false' in text)
    _check("runner no cloud", '"cloud_ocr_used": false' in text)


def main() -> int:
    print("test_candidate1_structured_ocr_attempt:")
    test_closed_summary_shape_and_safety()
    test_structured_unavailable_text_fallback_no_improvement()
    test_structured_richer_categories_improves_reliability()
    test_text_layer_fallback_does_not_count_as_improvement()
    test_no_raw_ocr_text_in_committed_summary()
    test_private_paths_refused_if_not_gitignored()
    test_runner_prints_closed_summary()
    if _FAILURES:
        print(f"test_candidate1_structured_ocr_attempt: FAILED ({len(_FAILURES)})")
        return 1
    print("test_candidate1_structured_ocr_attempt: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
