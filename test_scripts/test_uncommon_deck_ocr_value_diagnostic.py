"""Public-safe tests for Slice 176Q uncommon-deck OCR value diagnostic."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.uncommon_deck_ocr_value_diagnostic import (  # noqa: E402
    build_closed_uncommon_deck_ocr_value_summary,
    main as diagnostic_main,
    run_uncommon_deck_ocr_value_diagnostic,
)

_FAILURES: list[str] = []


def _check(name: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _FAILURES.append(name)


@contextmanager
def _env(name: str, value: str):
    old = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old


def _touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _source_path(root: Path, name: str) -> Path:
    return root / (name + ("." + "pdf"))


def test_closed_summary_shape_and_safety() -> None:
    summary = build_closed_uncommon_deck_ocr_value_summary(
        status="completed",
        uncommon_candidate_available=True,
        candidate_type="uncommon_course_deck",
        candidate_readiness="needs_ocr_artifact",
        private_source_available=True,
        private_source_gitignored=True,
        private_baseline_guide_available=True,
        private_baseline_guide_gitignored=True,
        next_test_readiness="ready_for_uncommon_deck_ocr_extraction",
        recommended_next_step="run_uncommon_deck_ocr_extraction",
    )
    _check("artifact name", summary["artifact_name"] == "uncommon_deck_ocr_value_diagnostic")
    _check("provider not called", summary["provider_call_made"] is False)
    _check("generation not rerun", summary["generation_rerun"] is False)
    _check("ocr not rerun", summary["ocr_rerun"] is False)
    _check("raw source false", summary["raw_source_committed"] is False)
    _check("raw guide false", summary["raw_guide_text_committed"] is False)
    _check("prompts false", summary["prompts_committed"] is False)
    _check("responses false", summary["responses_committed"] is False)
    _check("payloads false", summary["provider_payloads_committed"] is False)


def test_needs_ocr_artifact_route() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _touch(_source_path(root, "course_source"))
        _touch(root / "reference_notes.md")
        _touch(root / "GuideForge_course.md")
        summary = run_uncommon_deck_ocr_value_diagnostic(inventory_roots=[tmp])
    _check("completed", summary["status"] == "completed")
    _check("uncommon available", summary["uncommon_candidate_available"] is True)
    _check("candidate type", summary["candidate_type"] == "uncommon_course_deck")
    _check("needs ocr", summary["candidate_readiness"] == "needs_ocr_artifact")
    _check("source available", summary["private_source_available"] is True)
    _check("ocr unavailable", summary["private_ocr_artifact_available"] is False)
    _check("next ocr", summary["recommended_next_step"] == "run_uncommon_deck_ocr_extraction")


def test_ready_existing_artifacts_route() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _touch(_source_path(root, "course_source"))
        _touch(root / "reference_notes.md")
        _touch(root / "real_ocr_context_generated_guide.md")
        manifest = root / "extracted_content_manifest.json"
        manifest.write_text(
            json.dumps({"entries": [{"slide_category": "course_specific_table"}]}),
            encoding="utf-8",
        )
        summary = run_uncommon_deck_ocr_value_diagnostic(inventory_roots=[tmp])
    _check("ready", summary["candidate_readiness"] == "ready_existing_artifacts")
    _check("marker available", summary["marker_candidate_status"] == "available")
    _check("marker private", summary["marker_source"] == "private_artifact_categories")
    _check(
        "next coverage",
        summary["recommended_next_step"] == "run_uncommon_deck_coverage_eval_existing_artifacts",
    )


def test_statquest_like_only_is_unsuitable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _touch(_source_path(root, "statquest_ensemble_source"))
        _touch(root / "ensemble_latest.md")
        summary = run_uncommon_deck_ocr_value_diagnostic(inventory_roots=[tmp])
    _check("degraded", summary["status"] == "degraded")
    _check("not uncommon", summary["uncommon_candidate_available"] is False)
    _check("statquest like", summary["candidate_type"] == "statquest_like")
    _check("unsuitable", summary["candidate_readiness"] == "unsuitable")
    _check("pivot", summary["recommended_next_step"] == "pivot_to_rendered_visible_asset_insertion")


def test_needs_baseline_route() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _touch(_source_path(root, "course_source"))
        manifest = root / "extracted_content_manifest.json"
        manifest.write_text(
            json.dumps({"entries": [{"slide_category": "course_specific_table"}]}),
            encoding="utf-8",
        )
        summary = run_uncommon_deck_ocr_value_diagnostic(inventory_roots=[tmp])
    _check("needs baseline", summary["candidate_readiness"] == "needs_baseline_guide")
    _check(
        "next baseline",
        summary["recommended_next_step"] == "run_uncommon_deck_baseline_generation",
    )


def test_runner_prints_closed_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = StringIO()
        with _env("PRIVATE_INVENTORY_ROOTS", tmp), redirect_stdout(out):
            rc = diagnostic_main()
        text = out.getvalue()
    _check("runner exits blocked without inventory", rc == 2)
    _check("runner prints artifact", '"artifact_name": "uncommon_deck_ocr_value_diagnostic"' in text)
    _check("runner no generation", '"generation_rerun": false' in text)


def main() -> int:
    print("test_uncommon_deck_ocr_value_diagnostic:")
    test_closed_summary_shape_and_safety()
    test_needs_ocr_artifact_route()
    test_ready_existing_artifacts_route()
    test_statquest_like_only_is_unsuitable()
    test_needs_baseline_route()
    test_runner_prints_closed_summary()
    if _FAILURES:
        print(f"test_uncommon_deck_ocr_value_diagnostic: FAILED ({len(_FAILURES)})")
        return 1
    print("test_uncommon_deck_ocr_value_diagnostic: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
