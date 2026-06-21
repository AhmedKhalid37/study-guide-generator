"""Candidate_1 structured/local OCR attempt for Slice 176T.

This module makes a narrow attempt to improve the Slice 176R candidate_1
text-layer extraction using existing local OCR routes. Raw source/OCR text is
written only to a private artifact directory; returned summaries are closed
tokens/count buckets only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.uncommon_deck_local_ocr_extraction import (  # noqa: E402
    _closed_marker_categories,
    _count_bucket,
    _extract_tesseract_pages,
    _extract_text_layer_pages,
    _marker_status,
    _pages_bucket,
    _records_from_pages,
    _resolve_candidate_source,
    _safe_label,
)

ARTIFACT_NAME = "candidate1_structured_ocr_attempt"
SOURCE_LABEL_DEFAULT = "candidate_1"
CANDIDATE_TYPE = "uncommon_course_deck"
PREVIOUS_ENGINE = "text_layer"
PREVIOUS_MARKER_RELIABILITY = "low"

STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
BOOL_BLOCKERS = frozenset(
    {
        "none",
        "private_source_missing",
        "structured_ocr_unavailable",
        "local_ocr_unavailable",
        "unsafe_private_artifact_path",
        "extraction_failed",
        "scope_too_large",
    }
)
ENGINES = frozenset(
    {"chandra_gguf_local", "local_structured_ocr_vlm", "tesseract_cli", "text_layer", "mixed_local", "none"}
)
STRUCTURED_STATUSES = frozenset({"ran", "partial", "unavailable", "failed", "not_run"})
LOCAL_STATUSES = frozenset({"ran", "partial", "unavailable", "failed", "not_run"})
COUNT_BUCKETS = frozenset({"none", "low", "medium", "high", "unknown"})
PAGE_BUCKETS = frozenset({"low", "medium", "high", "unknown"})
MARKER_STATUSES = frozenset({"available", "partial", "unavailable"})
MARKER_SOURCES = frozenset(
    {"private_artifact_categories", "closed_static_ids", "mixed_closed_ids", "unavailable"}
)
RELIABILITY = frozenset({"high", "medium", "low", "unknown"})
IMPROVEMENT = frozenset({"yes", "partial", "no", "unavailable"})
READINESS = frozenset({"ready_for_uncommon_deck_coverage_eval", "needs_better_ocr", "blocked"})
NEXT_STEPS = frozenset(
    {
        "rerun_uncommon_deck_coverage_eval",
        "stop_ocr_coverage_campaign",
        "pivot_to_rendered_visible_asset_insertion",
        "collect_better_uncommon_fixture",
        "blocked",
    }
)
_MAX_DEFAULT_PAGES = 8


def build_closed_candidate1_structured_ocr_attempt_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    private_source_available: bool = False,
    private_source_gitignored: bool = False,
    private_improved_ocr_artifact_written: bool = False,
    private_improved_ocr_artifact_gitignored: bool = False,
    ocr_rerun: bool = False,
    attempted_structured_ocr: bool = False,
    structured_ocr_engine: str = "none",
    structured_ocr_status: str = "not_run",
    fallback_engine: str = "none",
    local_ocr_engine: str = "none",
    local_ocr_status: str = "not_run",
    pages_considered_count_bucket: str = "unknown",
    pages_extracted_count_bucket: str = "unknown",
    extracted_text_block_count_bucket: str = "unknown",
    extracted_table_count_bucket: str = "unknown",
    extracted_figure_or_diagram_count_bucket: str = "unknown",
    marker_candidate_status: str = "unavailable",
    marker_source: str = "unavailable",
    marker_reliability: str = "unknown",
    improvement_over_176r: str = "unavailable",
    next_test_readiness: str = "blocked",
    blocked_by: str = "none",
    recommended_next_step: str = "blocked",
) -> dict[str, Any]:
    """Return the committed-safe closed attempt summary."""
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _safe_label(source_label),
        "candidate_type": CANDIDATE_TYPE,
        "previous_extraction_engine": PREVIOUS_ENGINE,
        "previous_marker_reliability": PREVIOUS_MARKER_RELIABILITY,
        "private_source_available": bool(private_source_available),
        "private_source_gitignored": bool(private_source_gitignored),
        "private_improved_ocr_artifact_written": bool(private_improved_ocr_artifact_written),
        "private_improved_ocr_artifact_gitignored": bool(private_improved_ocr_artifact_gitignored),
        "raw_source_committed": False,
        "raw_ocr_committed": False,
        "raw_table_text_committed": False,
        "raw_caption_text_committed": False,
        "rendered_images_committed": False,
        "source_pdf_committed": False,
        "prompts_committed": False,
        "responses_committed": False,
        "provider_payloads_committed": False,
        "cloud_ocr_used": False,
        "provider_call_made": False,
        "generation_rerun": False,
        "coverage_eval_rerun": False,
        "ocr_rerun": bool(ocr_rerun),
        "attempted_structured_ocr": bool(attempted_structured_ocr),
        "structured_ocr_engine": _coerce(structured_ocr_engine, ENGINES, "none"),
        "structured_ocr_status": _coerce(structured_ocr_status, STRUCTURED_STATUSES, "not_run"),
        "fallback_engine": _coerce(fallback_engine, ENGINES, "none"),
        "local_ocr_engine": _coerce(local_ocr_engine, ENGINES, "none"),
        "local_ocr_status": _coerce(local_ocr_status, LOCAL_STATUSES, "not_run"),
        "pages_considered_count_bucket": _coerce(pages_considered_count_bucket, PAGE_BUCKETS, "unknown"),
        "pages_extracted_count_bucket": _coerce(pages_extracted_count_bucket, COUNT_BUCKETS, "unknown"),
        "extracted_text_block_count_bucket": _coerce(
            extracted_text_block_count_bucket, COUNT_BUCKETS, "unknown"
        ),
        "extracted_table_count_bucket": _coerce(extracted_table_count_bucket, COUNT_BUCKETS, "unknown"),
        "extracted_figure_or_diagram_count_bucket": _coerce(
            extracted_figure_or_diagram_count_bucket, COUNT_BUCKETS, "unknown"
        ),
        "marker_candidate_status": _coerce(marker_candidate_status, MARKER_STATUSES, "unavailable"),
        "marker_source": _coerce(marker_source, MARKER_SOURCES, "unavailable"),
        "marker_reliability": _coerce(marker_reliability, RELIABILITY, "unknown"),
        "improvement_over_176r": _coerce(improvement_over_176r, IMPROVEMENT, "unavailable"),
        "next_test_readiness": _coerce(next_test_readiness, READINESS, "blocked"),
        "blocked_by": _coerce(blocked_by, BOOL_BLOCKERS, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "blocked"),
        "broad_ocr_framework_built": False,
    }


def run_candidate1_structured_ocr_attempt(
    *,
    source_path: str | None = None,
    inventory_roots: list[str] | None = None,
    private_ocr_dir: str | None = None,
    source_label: str = SOURCE_LABEL_DEFAULT,
    max_pages: int = _MAX_DEFAULT_PAGES,
    tesseract_enabled: bool = True,
    structured_records_override: list[dict[str, Any]] | None = None,
    text_pages_override: list[str] | None = None,
) -> dict[str, Any]:
    """Attempt candidate_1 extraction improvement using existing local routes."""
    source = _resolve_candidate_source(source_path, inventory_roots)
    if source is None:
        return build_closed_candidate1_structured_ocr_attempt_summary(
            status="blocked",
            source_label=source_label,
            private_source_available=False,
            blocked_by="private_source_missing",
            recommended_next_step="collect_better_uncommon_fixture",
        )
    source_private = is_private_artifact_dir(source.parent)
    if not source_private:
        return build_closed_candidate1_structured_ocr_attempt_summary(
            status="blocked",
            source_label=source_label,
            private_source_available=True,
            private_source_gitignored=False,
            blocked_by="unsafe_private_artifact_path",
            recommended_next_step="blocked",
        )
    if not private_ocr_dir:
        private_ocr_dir = str(Path(tempfile.gettempdir()) / "candidate1_structured_ocr_attempt")
    if not is_private_artifact_dir(private_ocr_dir):
        return build_closed_candidate1_structured_ocr_attempt_summary(
            status="blocked",
            source_label=source_label,
            private_source_available=True,
            private_source_gitignored=True,
            blocked_by="unsafe_private_artifact_path",
            recommended_next_step="blocked",
        )

    out_dir = Path(private_ocr_dir)
    max_pages = max(1, int(max_pages or _MAX_DEFAULT_PAGES))
    attempted_structured = True

    structured_records, structured_status, structured_engine = _structured_records(
        source=source,
        out_dir=out_dir,
        max_pages=max_pages,
        tesseract_enabled=tesseract_enabled,
        override=structured_records_override,
    )
    fallback_records: list[dict[str, Any]] = []
    fallback_engine = "none"
    if not structured_records:
        text_pages = _extract_text_layer_pages(source, max_pages=max_pages, override=text_pages_override)
        fallback_records = _records_from_pages(text_pages)
        fallback_engine = "text_layer" if fallback_records else "none"

    records = structured_records or fallback_records
    categories = _closed_marker_categories(records)
    marker_status, marker_source = _marker_status(categories, bool(records))
    reliability = _marker_reliability(
        categories=categories,
        marker_source=marker_source,
        structured_status=structured_status,
        used_fallback=bool(fallback_records),
    )
    table_count = sum(int(r.get("table_like_count") or 0) for r in records)
    figure_count = sum(int(r.get("figure_or_diagram_like_count") or 0) for r in records)
    improvement = _improvement_over_176r(
        reliability=reliability,
        structured_status=structured_status,
        used_fallback=bool(fallback_records),
        categories=categories,
        table_count=table_count,
        figure_count=figure_count,
    )
    artifact_written = False
    if structured_records:
        artifact_written = _write_private_attempt_artifact(
            out_dir,
            source_label=source_label,
            records=structured_records,
            categories=categories,
            extraction_engine=structured_engine,
            improvement=improvement,
        )
    status, readiness, blocker, next_step = _route_attempt(
        structured_status=structured_status,
        has_records=bool(records),
        used_fallback=bool(fallback_records),
        improvement=improvement,
        reliability=reliability,
    )
    local_engine = structured_engine if structured_records else fallback_engine
    local_status = _local_status(structured_status, bool(records), bool(fallback_records))
    summary = build_closed_candidate1_structured_ocr_attempt_summary(
        status=status,
        source_label=source_label,
        private_source_available=True,
        private_source_gitignored=True,
        private_improved_ocr_artifact_written=artifact_written and improvement in {"yes", "partial"},
        private_improved_ocr_artifact_gitignored=artifact_written
        and improvement in {"yes", "partial"}
        and is_private_artifact_dir(out_dir),
        ocr_rerun=structured_status in {"ran", "partial", "failed"},
        attempted_structured_ocr=attempted_structured,
        structured_ocr_engine=structured_engine,
        structured_ocr_status=structured_status,
        fallback_engine=fallback_engine,
        local_ocr_engine=local_engine,
        local_ocr_status=local_status,
        pages_considered_count_bucket=_pages_bucket(_page_count(source, max_pages, text_pages_override)),
        pages_extracted_count_bucket=_count_bucket(len(records)),
        extracted_text_block_count_bucket=_count_bucket(len([r for r in records if r.get("text_block_present")])),
        extracted_table_count_bucket=_count_bucket(table_count),
        extracted_figure_or_diagram_count_bucket=_count_bucket(figure_count),
        marker_candidate_status=marker_status,
        marker_source=marker_source,
        marker_reliability=reliability,
        improvement_over_176r=improvement,
        next_test_readiness=readiness,
        blocked_by=blocker,
        recommended_next_step=next_step,
    )
    _write_closed_summary(out_dir, summary)
    return summary


def _structured_records(
    *,
    source: Path,
    out_dir: Path,
    max_pages: int,
    tesseract_enabled: bool,
    override: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], str, str]:
    if override is not None:
        records = [_safe_record(r, i) for i, r in enumerate(override) if isinstance(r, dict)]
        return records, "ran" if records else "failed", "local_structured_ocr_vlm"
    pages, tesseract_status = _extract_tesseract_pages(
        source,
        max_pages=max_pages,
        out_dir=out_dir,
        enabled=tesseract_enabled,
        skip=False,
    )
    if pages:
        return _records_from_pages(pages), "ran", "tesseract_cli"
    if tesseract_status == "failed":
        return [], "failed", "tesseract_cli"
    return [], "unavailable", "none"


def _safe_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    categories = [
        _safe_label(c)
        for c in record.get("closed_categories", [])
        if isinstance(c, str) and _safe_label(c)
    ]
    return {
        "page_index": int(record.get("page_index", index) or index),
        "raw_text": str(record.get("raw_text") or ""),
        "closed_categories": sorted(set(categories)),
        "table_like_count": max(0, int(record.get("table_like_count") or 0)),
        "figure_or_diagram_like_count": max(0, int(record.get("figure_or_diagram_like_count") or 0)),
        "text_block_present": bool(record.get("text_block_present", True)),
    }


def _marker_reliability(
    *, categories: list[str], marker_source: str, structured_status: str, used_fallback: bool
) -> str:
    if used_fallback or structured_status not in {"ran", "partial"}:
        return "low" if categories else "unknown"
    if marker_source == "private_artifact_categories" and len(categories) >= 5:
        return "high"
    if marker_source == "private_artifact_categories" and len(categories) >= 3:
        return "medium"
    if categories:
        return "low"
    return "unknown"


def _improvement_over_176r(
    *,
    reliability: str,
    structured_status: str,
    used_fallback: bool,
    categories: list[str],
    table_count: int,
    figure_count: int,
) -> str:
    if used_fallback:
        return "no"
    if structured_status not in {"ran", "partial"}:
        return "unavailable" if not categories else "no"
    if reliability in {"medium", "high"} and (table_count > 0 or figure_count > 0 or len(categories) >= 4):
        return "yes"
    if reliability in {"medium", "high"}:
        return "partial"
    return "no"


def _route_attempt(
    *,
    structured_status: str,
    has_records: bool,
    used_fallback: bool,
    improvement: str,
    reliability: str,
) -> tuple[str, str, str, str]:
    if improvement in {"yes", "partial"} and reliability in {"medium", "high"}:
        return "completed", "ready_for_uncommon_deck_coverage_eval", "none", "rerun_uncommon_deck_coverage_eval"
    if structured_status == "unavailable" and used_fallback:
        return "degraded", "needs_better_ocr", "structured_ocr_unavailable", "collect_better_uncommon_fixture"
    if structured_status == "failed":
        return "degraded" if has_records else "blocked", "needs_better_ocr", "extraction_failed", "pivot_to_rendered_visible_asset_insertion"
    if has_records:
        return "degraded", "needs_better_ocr", "none", "pivot_to_rendered_visible_asset_insertion"
    return "blocked", "blocked", "local_ocr_unavailable", "blocked"


def _local_status(structured_status: str, has_records: bool, used_fallback: bool) -> str:
    if has_records and structured_status == "failed":
        return "partial"
    if has_records:
        return "ran"
    if structured_status == "failed":
        return "failed"
    if structured_status == "unavailable":
        return "unavailable" if not used_fallback else "partial"
    return "not_run"


def _write_private_attempt_artifact(
    out_dir: Path,
    *,
    source_label: str,
    records: list[dict[str, Any]],
    categories: list[str],
    extraction_engine: str,
    improvement: str,
) -> bool:
    if not is_private_artifact_dir(out_dir) or not records:
        return False
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "artifact_name": ARTIFACT_NAME,
            "source_label": _safe_label(source_label),
            "candidate_type": CANDIDATE_TYPE,
            "extraction_engine": extraction_engine,
            "improvement_over_176r": improvement,
            "closed_categories": categories,
            "entries": records,
        }
        (out_dir / "candidate1_structured_ocr_attempt_artifact.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def _write_closed_summary(out_dir: Path, summary: dict[str, Any]) -> None:
    if not is_private_artifact_dir(out_dir):
        return
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "closed_candidate1_structured_ocr_attempt_summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return


def _page_count(source: Path, max_pages: int, override: list[str] | None) -> int:
    if override is not None:
        return min(len(override), max(1, max_pages))
    if source.suffix.lower() != "." + "pdf":
        return 0
    try:
        import fitz

        with fitz.open(source) as document:
            return min(int(document.page_count), max(1, max_pages))
    except Exception:
        return 0


def _env_roots() -> list[str] | None:
    raw = os.environ.get("PRIVATE_INVENTORY_ROOTS")
    if not raw:
        return None
    roots = [p for p in raw.split(os.pathsep) if p]
    return roots or None


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def main() -> int:
    summary = run_candidate1_structured_ocr_attempt(
        source_path=os.environ.get("CANDIDATE_SOURCE_PATH"),
        inventory_roots=_env_roots(),
        private_ocr_dir=os.environ.get("PRIVATE_OCR_DIR"),
        source_label=os.environ.get("SOURCE_LABEL", SOURCE_LABEL_DEFAULT),
        max_pages=int(os.environ.get("MAX_OCR_PAGES", str(_MAX_DEFAULT_PAGES))),
        tesseract_enabled=os.environ.get("TESSERACT_ENABLED", "1") != "0",
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] in {"completed", "degraded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
