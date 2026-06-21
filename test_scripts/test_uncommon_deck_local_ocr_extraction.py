"""Public-safe tests for Slice 176R uncommon-deck local OCR extraction."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.uncommon_deck_local_ocr_extraction import (  # noqa: E402
    build_closed_uncommon_deck_local_ocr_summary,
    main as extraction_main,
    run_uncommon_deck_local_ocr_extraction,
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
    summary = build_closed_uncommon_deck_local_ocr_summary(
        status="completed",
        private_source_available=True,
        private_source_gitignored=True,
        private_ocr_artifact_written=True,
        private_ocr_artifact_gitignored=True,
        ocr_rerun=True,
        local_ocr_engine="text_layer",
        local_ocr_status="ran",
        marker_candidate_status="partial",
        marker_source="private_artifact_categories",
        next_test_readiness="ready_for_uncommon_deck_coverage_eval",
        recommended_next_step="run_uncommon_deck_coverage_eval_existing_artifacts",
    )
    _check("artifact name", summary["artifact_name"] == "uncommon_deck_local_ocr_extraction")
    _check("candidate label", summary["source_label"] == "candidate_1")
    _check("provider not called", summary["provider_call_made"] is False)
    _check("cloud false", summary["cloud_ocr_used"] is False)
    _check("generation false", summary["generation_rerun"] is False)
    _check("raw ocr false", summary["raw_ocr_committed"] is False)
    _check("raw table false", summary["raw_table_text_committed"] is False)
    _check("prompts false", summary["prompts_committed"] is False)
    _check("responses false", summary["responses_committed"] is False)
    _check("payloads false", summary["provider_payloads_committed"] is False)
    _check("no expensive selection", summary["expensive_frame_selection_built"] is False)


def test_source_missing_blocks() -> None:
    with tempfile.TemporaryDirectory() as out:
        summary = run_uncommon_deck_local_ocr_extraction(private_ocr_dir=out, inventory_roots=[])
    _check("blocked", summary["status"] == "blocked")
    _check("missing blocker", summary["blocked_by"] == "private_source_missing")
    _check("collect fixture", summary["recommended_next_step"] == "collect_uncommon_deck_fixture")


def test_unsafe_private_path_refused() -> None:
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as unsafe_root, tempfile.TemporaryDirectory() as out:
        source = Path(unsafe_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=["table matrix dataset 123"],
        )
    _check("unsafe blocked", summary["status"] == "blocked")
    _check("unsafe blocker", summary["blocked_by"] == "unsafe_private_artifact_path")
    _check("source not gitignored", summary["private_source_gitignored"] is False)


def test_gitignored_private_artifact_accepted_and_text_layer_degraded() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=["table matrix dataset 123", "definition concept diagram example"],
            page_hashes_override=[1, 2, 3, 4],
        )
        artifact = Path(out) / "uncommon_deck_local_ocr_artifact.json"
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    _check("artifact written", summary["private_ocr_artifact_written"] is True)
    _check("artifact private", summary["private_ocr_artifact_gitignored"] is True)
    _check("text engine", summary["local_ocr_engine"] == "text_layer")
    _check("status completed or degraded", summary["status"] in {"completed", "degraded"})
    _check("marker ready", summary["marker_candidate_status"] in {"available", "partial"})
    _check("coverage next", summary["next_test_readiness"] == "ready_for_uncommon_deck_coverage_eval")
    _check("private payload has raw only private", "entries" in payload)


def test_local_ocr_unavailable_sets_unavailable() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=[],
            tesseract_enabled=False,
        )
    _check("blocked or degraded", summary["status"] in {"blocked", "degraded"})
    _check("ocr unavailable", summary["local_ocr_status"] == "unavailable")
    _check("local blocker", summary["blocked_by"] == "local_ocr_unavailable")


def test_closed_summary_contains_no_raw_text() -> None:
    raw = "table matrix dataset synthetic public marker 123"
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=[raw],
            page_hashes_override=[1, 1, 8],
        )
    rendered = json.dumps(summary)
    _check("raw absent", raw not in rendered)
    _check("source path absent", private_root not in rendered)
    _check("output path absent", out not in rendered)


def test_marker_candidate_status_behaviors() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        available = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=["table matrix 123 diagram example definition"],
            page_hashes_override=[1, 1, 1, 1],
        )
        partial = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=["plain lecture content"],
            page_hashes_override=[1, 2, 3],
        )
        unavailable = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=[],
            tesseract_enabled=False,
        )
    _check("available markers", available["marker_candidate_status"] == "available")
    _check("partial markers", partial["marker_candidate_status"] == "partial")
    _check("unavailable markers", unavailable["marker_candidate_status"] == "unavailable")


def test_redundancy_integration_and_frame_dedup_auto() -> None:
    with tempfile.TemporaryDirectory() as private_root, tempfile.TemporaryDirectory() as out:
        source = Path(private_root) / "candidate.pdf"
        _touch_pdf(source)
        summary = run_uncommon_deck_local_ocr_extraction(
            source_path=str(source),
            private_ocr_dir=out,
            text_pages_override=["table matrix 123 diagram example definition"],
            page_hashes_override=[7, 7, 7, 7, 7, 7],
        )
    _check("redundancy closed", summary["slide_redundancy"] in {"low", "medium", "high", "unknown"})
    _check("dedup auto", summary["frame_dedup_mode"] == "auto")
    _check("dedup resolved", summary["resolved_frame_dedup"] in {"on", "off"})
    _check("expensive not built", summary["expensive_frame_selection_built"] is False)


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
            rc = extraction_main()
        text = out_stream.getvalue()
    _check("runner exits blocked without text", rc == 2)
    _check("runner artifact name", '"artifact_name": "uncommon_deck_local_ocr_extraction"' in text)
    _check("runner no provider", '"provider_call_made": false' in text)
    _check("runner no cloud", '"cloud_ocr_used": false' in text)


def main() -> int:
    print("test_uncommon_deck_local_ocr_extraction:")
    test_closed_summary_shape_and_safety()
    test_source_missing_blocks()
    test_unsafe_private_path_refused()
    test_gitignored_private_artifact_accepted_and_text_layer_degraded()
    test_local_ocr_unavailable_sets_unavailable()
    test_closed_summary_contains_no_raw_text()
    test_marker_candidate_status_behaviors()
    test_redundancy_integration_and_frame_dedup_auto()
    test_runner_prints_closed_summary()
    if _FAILURES:
        print(f"test_uncommon_deck_local_ocr_extraction: FAILED ({len(_FAILURES)})")
        return 1
    print("test_uncommon_deck_local_ocr_extraction: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
