"""Closed uncommon-deck local OCR extraction artifact for Slice 176R.

Runs local-only extraction for the Slice 176Q uncommon candidate and writes raw
OCR/text only to a private artifact directory. The returned summary is closed:
no source text, OCR text, table text, captions, paths, filenames, hashes, byte
counts, prompts, responses, or provider payloads.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.slide_raster_ocr_ingestion import is_private_artifact_dir  # noqa: E402
from pipeline.slide_redundancy_detector import (  # noqa: E402
    FrameRedundancyConfig,
    run_slide_redundancy_detection,
)

ARTIFACT_NAME = "uncommon_deck_local_ocr_extraction"
SOURCE_LABEL_DEFAULT = "candidate_1"
CANDIDATE_TYPE = "uncommon_course_deck"

STATUSES = frozenset({"completed", "degraded", "blocked", "skipped"})
LOCAL_OCR_ENGINES = frozenset(
    {"chandra_gguf_local", "local_structured_ocr_vlm", "tesseract_cli", "text_layer", "mixed_local", "none"}
)
LOCAL_OCR_STATUSES = frozenset({"ran", "partial", "unavailable", "failed", "not_run"})
REDUNDANCY = frozenset({"low", "medium", "high", "unknown", "not_checked"})
FRAME_DEDUP_MODES = frozenset({"auto"})
RESOLVED_FRAME_DEDUP = frozenset({"on", "off", "not_checked"})
COUNT_BUCKETS = frozenset({"none", "low", "medium", "high", "unknown"})
PAGES_CONSIDERED_BUCKETS = frozenset({"low", "medium", "high", "unknown"})
MARKER_STATUSES = frozenset({"available", "partial", "unavailable"})
MARKER_SOURCES = frozenset(
    {"private_artifact_categories", "closed_static_ids", "mixed_closed_ids", "unavailable"}
)
NEXT_TEST_READINESS = frozenset(
    {"ready_for_uncommon_deck_coverage_eval", "needs_better_ocr", "needs_baseline_guide", "blocked"}
)
BLOCKERS = frozenset(
    {
        "none",
        "private_source_missing",
        "local_ocr_unavailable",
        "unsafe_private_artifact_path",
        "extraction_failed",
        "scope_too_large",
    }
)
NEXT_STEPS = frozenset(
    {
        "run_uncommon_deck_coverage_eval_existing_artifacts",
        "improve_uncommon_deck_ocr_extraction",
        "collect_uncommon_deck_fixture",
        "pivot_to_rendered_visible_asset_insertion",
        "blocked",
    }
)

_SOURCE_SUFFIXES = frozenset({"." + "pdf", "." + "ppt", "." + "pptx"})
_COMMON_TOKENS = frozenset({"statquest", "ensemble"})
_MAX_DEFAULT_PAGES = 24


def build_closed_uncommon_deck_local_ocr_summary(
    *,
    status: str,
    source_label: str = SOURCE_LABEL_DEFAULT,
    private_source_available: bool = False,
    private_source_gitignored: bool = False,
    private_ocr_artifact_written: bool = False,
    private_ocr_artifact_gitignored: bool = False,
    ocr_rerun: bool = False,
    local_ocr_engine: str = "none",
    local_ocr_status: str = "not_run",
    slide_redundancy: str = "not_checked",
    resolved_frame_dedup: str = "not_checked",
    pages_considered_count_bucket: str = "unknown",
    pages_extracted_count_bucket: str = "unknown",
    extracted_text_block_count_bucket: str = "unknown",
    extracted_table_count_bucket: str = "unknown",
    extracted_figure_or_diagram_count_bucket: str = "unknown",
    marker_candidate_status: str = "unavailable",
    marker_source: str = "unavailable",
    next_test_readiness: str = "blocked",
    blocked_by: str = "none",
    recommended_next_step: str = "blocked",
) -> dict[str, Any]:
    """Return committed-safe closed OCR extraction summary."""
    return {
        "artifact_name": ARTIFACT_NAME,
        "status": _coerce(status, STATUSES, "blocked"),
        "source_label": _safe_label(source_label),
        "candidate_type": CANDIDATE_TYPE,
        "private_source_available": bool(private_source_available),
        "private_source_gitignored": bool(private_source_gitignored),
        "private_ocr_artifact_written": bool(private_ocr_artifact_written),
        "private_ocr_artifact_gitignored": bool(private_ocr_artifact_gitignored),
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
        "ocr_rerun": bool(ocr_rerun),
        "local_ocr_engine": _coerce(local_ocr_engine, LOCAL_OCR_ENGINES, "none"),
        "local_ocr_status": _coerce(local_ocr_status, LOCAL_OCR_STATUSES, "not_run"),
        "slide_redundancy": _coerce(slide_redundancy, REDUNDANCY, "not_checked"),
        "frame_dedup_mode": "auto",
        "resolved_frame_dedup": _coerce(resolved_frame_dedup, RESOLVED_FRAME_DEDUP, "not_checked"),
        "expensive_frame_selection_built": False,
        "pages_considered_count_bucket": _coerce(
            pages_considered_count_bucket, PAGES_CONSIDERED_BUCKETS, "unknown"
        ),
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
        "next_test_readiness": _coerce(next_test_readiness, NEXT_TEST_READINESS, "blocked"),
        "blocked_by": _coerce(blocked_by, BLOCKERS, "none"),
        "recommended_next_step": _coerce(recommended_next_step, NEXT_STEPS, "blocked"),
    }


def run_uncommon_deck_local_ocr_extraction(
    *,
    source_path: str | None = None,
    inventory_roots: list[str] | None = None,
    private_ocr_dir: str | None = None,
    source_label: str = SOURCE_LABEL_DEFAULT,
    max_pages: int = _MAX_DEFAULT_PAGES,
    text_pages_override: list[str] | None = None,
    page_hashes_override: list[int] | None = None,
    tesseract_enabled: bool = True,
) -> dict[str, Any]:
    """Run local-only OCR/text extraction and write private raw artifact."""
    source = _resolve_candidate_source(source_path, inventory_roots)
    if source is None:
        return build_closed_uncommon_deck_local_ocr_summary(
            status="blocked",
            source_label=source_label,
            private_source_available=False,
            blocked_by="private_source_missing",
            recommended_next_step="collect_uncommon_deck_fixture",
        )

    source_private = is_private_artifact_dir(source.parent)
    if not source_private:
        return build_closed_uncommon_deck_local_ocr_summary(
            status="blocked",
            source_label=source_label,
            private_source_available=True,
            private_source_gitignored=False,
            blocked_by="unsafe_private_artifact_path",
            recommended_next_step="blocked",
        )

    if not private_ocr_dir or not is_private_artifact_dir(private_ocr_dir):
        return build_closed_uncommon_deck_local_ocr_summary(
            status="blocked",
            source_label=source_label,
            private_source_available=True,
            private_source_gitignored=True,
            blocked_by="unsafe_private_artifact_path",
            recommended_next_step="blocked",
        )

    pages = _extract_text_layer_pages(source, max_pages=max_pages, override=text_pages_override)
    ocr_pages, tesseract_status = _extract_tesseract_pages(
        source,
        max_pages=max_pages,
        out_dir=Path(private_ocr_dir),
        enabled=tesseract_enabled,
        skip=bool(pages),
    )
    extracted_pages = pages or ocr_pages
    engine = _engine_from_results(text_pages=pages, ocr_pages=ocr_pages, tesseract_status=tesseract_status)
    local_status = _local_status_from_results(extracted_pages, tesseract_status)

    redundancy, dedup = _closed_redundancy(source, source_label, page_hashes_override)
    records = _records_from_pages(extracted_pages)
    categories = _closed_marker_categories(records)
    marker_status, marker_source = _marker_status(categories, bool(records))
    artifact_written = _write_private_artifact(
        Path(private_ocr_dir),
        source_label=source_label,
        records=records,
        categories=categories,
        extraction_engine=engine,
    )

    if not extracted_pages:
        status = "blocked" if tesseract_status in {"not_available", "skipped"} else "degraded"
        blocked_by = "local_ocr_unavailable" if tesseract_status in {"not_available", "skipped"} else "extraction_failed"
        next_readiness = "blocked" if blocked_by == "local_ocr_unavailable" else "needs_better_ocr"
        next_step = "blocked" if blocked_by == "local_ocr_unavailable" else "improve_uncommon_deck_ocr_extraction"
    elif marker_status in {"available", "partial"} and artifact_written:
        status = "completed" if marker_status == "available" else "degraded"
        blocked_by = "none"
        next_readiness = "ready_for_uncommon_deck_coverage_eval"
        next_step = "run_uncommon_deck_coverage_eval_existing_artifacts"
    else:
        status = "degraded"
        blocked_by = "extraction_failed"
        next_readiness = "needs_better_ocr"
        next_step = "improve_uncommon_deck_ocr_extraction"

    summary = build_closed_uncommon_deck_local_ocr_summary(
        status=status,
        source_label=source_label,
        private_source_available=True,
        private_source_gitignored=True,
        private_ocr_artifact_written=artifact_written,
        private_ocr_artifact_gitignored=artifact_written and is_private_artifact_dir(private_ocr_dir),
        ocr_rerun=bool(extracted_pages or tesseract_status not in {"skipped", "not_available"}),
        local_ocr_engine=engine,
        local_ocr_status=local_status,
        slide_redundancy=redundancy,
        resolved_frame_dedup=dedup,
        pages_considered_count_bucket=_pages_bucket(_page_count(source, max_pages, text_pages_override)),
        pages_extracted_count_bucket=_count_bucket(len(extracted_pages)),
        extracted_text_block_count_bucket=_count_bucket(len([p for p in extracted_pages if p.strip()])),
        extracted_table_count_bucket=_count_bucket(sum(r["table_like_count"] for r in records)),
        extracted_figure_or_diagram_count_bucket=_count_bucket(
            sum(r["figure_or_diagram_like_count"] for r in records)
        ),
        marker_candidate_status=marker_status,
        marker_source=marker_source,
        next_test_readiness=next_readiness,
        blocked_by=blocked_by,
        recommended_next_step=next_step,
    )
    _write_closed_summary(Path(private_ocr_dir), summary)
    return summary


def _resolve_candidate_source(path: str | None, roots: list[str] | None) -> Path | None:
    if path:
        candidate = Path(path)
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in _SOURCE_SUFFIXES:
            return candidate
        return None
    matches: list[Path] = []
    selected_roots = [os.getcwd()] if roots is None else roots
    for root in selected_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        if root_path.is_file():
            if _is_uncommon_private_source(root_path):
                matches.append(root_path)
            continue
        for walk_root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv", "__pycache__"}]
            if not is_private_artifact_dir(walk_root):
                continue
            for name in files:
                p = Path(walk_root) / name
                if _is_uncommon_private_source(p):
                    matches.append(p)
    return sorted(matches, key=lambda p: len(str(p)))[0] if matches else None


def _is_uncommon_private_source(path: Path) -> bool:
    if path.suffix.lower() not in _SOURCE_SUFFIXES or not is_private_artifact_dir(path.parent):
        return False
    return not (_COMMON_TOKENS & _path_tokens(path))


def _extract_text_layer_pages(source: Path, *, max_pages: int, override: list[str] | None) -> list[str]:
    if override is not None:
        return [str(t) for t in override[: max(1, max_pages)] if str(t).strip()]
    if source.suffix.lower() != "." + "pdf":
        return []
    try:
        import fitz
    except Exception:
        return []
    pages: list[str] = []
    try:
        with fitz.open(source) as document:
            for index in range(min(int(document.page_count), max(1, max_pages))):
                text = document[index].get_text("text") or ""
                if text.strip():
                    pages.append(text)
    except Exception:
        return []
    return pages


def _extract_tesseract_pages(
    source: Path,
    *,
    max_pages: int,
    out_dir: Path,
    enabled: bool,
    skip: bool,
) -> tuple[list[str], str]:
    if skip:
        return [], "skipped"
    if not enabled:
        return [], "skipped"
    if source.suffix.lower() != "." + "pdf":
        return [], "not_available"
    if not shutil.which("tesseract"):
        return [], "not_available"
    try:
        import fitz
    except Exception:
        return [], "not_available"

    rendered = out_dir / "rendered_pages"
    if not is_private_artifact_dir(rendered):
        return [], "failed"
    rendered.mkdir(parents=True, exist_ok=True)
    pages: list[str] = []
    try:
        with fitz.open(source) as document:
            limit = min(int(document.page_count), max(1, max_pages))
            for index in range(limit):
                pixmap = document[index].get_pixmap(matrix=fitz.Matrix(2, 2))
                image = rendered / f"page_{index:04d}.png"
                pixmap.save(str(image))
                proc = subprocess.run(
                    ["tesseract", str(image), "stdout", "--psm", "6"],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                if proc.stdout.strip():
                    pages.append(proc.stdout)
    except Exception:
        return pages, "failed" if not pages else "ran"
    return pages, "ran" if pages else "failed"


def _closed_redundancy(source: Path, source_label: str, hashes: list[int] | None) -> tuple[str, str]:
    try:
        config = FrameRedundancyConfig(
            source_label=source_label,
            pdf_path=None if hashes is not None else str(source),
            page_hashes=hashes,
            frame_dedup_mode="auto",
        )
        result = run_slide_redundancy_detection(config)
        detection = result.get("detection", {})
        resolution = result.get("resolution", {})
        redundancy = detection.get("slide_redundancy", "unknown")
        dedup = resolution.get("resolved_frame_dedup", "off")
        return (
            redundancy if redundancy in REDUNDANCY else "unknown",
            dedup if dedup in {"on", "off"} else "off",
        )
    except Exception:
        return "unknown", "not_checked"


def _records_from_pages(pages: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, text in enumerate(pages):
        clean = str(text or "")
        if not clean.strip():
            continue
        categories = sorted(_categories_for_text(clean))
        records.append(
            {
                "page_index": index,
                "raw_text": clean,
                "closed_categories": categories,
                "table_like_count": _table_like_count(clean),
                "figure_or_diagram_like_count": _figure_like_count(clean),
                "text_block_present": True,
            }
        )
    return records


def _categories_for_text(text: str) -> set[str]:
    low = text.lower()
    categories: set[str] = set()
    if any(token in low for token in ("table", "matrix", "dataset", "row", "column")):
        categories.add("table_like")
    if any(token in low for token in ("figure", "diagram", "chart", "graph", "plot")):
        categories.add("figure_or_diagram_like")
    if any(token in low for token in ("example", "case", "scenario", "worked")):
        categories.add("example_or_case")
    if any(token in low for token in ("definition", "concept", "theorem", "principle")):
        categories.add("concept_or_definition")
    if any(token in low for token in ("question", "quiz", "exercise", "assessment")):
        categories.add("assessment_or_question")
    if re.search(r"\b\d+(?:\.\d+)?\b", low):
        categories.add("numeric_content")
    return categories


def _closed_marker_categories(records: list[dict[str, Any]]) -> list[str]:
    out: set[str] = set()
    for record in records:
        for category in record.get("closed_categories", []):
            out.add(_safe_label(category))
    return sorted(out)


def _marker_status(categories: list[str], has_records: bool) -> tuple[str, str]:
    if len(categories) >= 3:
        return "available", "private_artifact_categories"
    if categories or has_records:
        return "partial", "private_artifact_categories" if categories else "closed_static_ids"
    return "unavailable", "unavailable"


def _write_private_artifact(
    out_dir: Path,
    *,
    source_label: str,
    records: list[dict[str, Any]],
    categories: list[str],
    extraction_engine: str,
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
            "closed_categories": categories,
            "entries": records,
        }
        (out_dir / "uncommon_deck_local_ocr_artifact.json").write_text(
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
        (out_dir / "closed_uncommon_deck_local_ocr_summary.json").write_text(
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


def _engine_from_results(*, text_pages: list[str], ocr_pages: list[str], tesseract_status: str) -> str:
    if text_pages and ocr_pages:
        return "mixed_local"
    if text_pages:
        return "text_layer"
    if ocr_pages or tesseract_status in {"ran", "failed"}:
        return "tesseract_cli"
    return "none"


def _local_status_from_results(pages: list[str], tesseract_status: str) -> str:
    if pages and tesseract_status in {"failed", "not_available"}:
        return "partial"
    if pages:
        return "ran"
    if tesseract_status == "failed":
        return "failed"
    if tesseract_status in {"not_available", "skipped"}:
        return "unavailable"
    return "not_run"


def _table_like_count(text: str) -> int:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    table_lines = [line for line in lines if "|" in line or "\t" in line or len(re.findall(r"\s{2,}", line)) >= 2]
    return len(table_lines)


def _figure_like_count(text: str) -> int:
    return len(re.findall(r"\b(figure|diagram|chart|graph|plot)\b", str(text or "").lower()))


def _count_bucket(value: int) -> str:
    if value <= 0:
        return "none"
    if value <= 2:
        return "low"
    if value <= 8:
        return "medium"
    return "high"


def _pages_bucket(value: int) -> str:
    if value <= 0:
        return "unknown"
    if value <= 5:
        return "low"
    if value <= 20:
        return "medium"
    return "high"


def _path_tokens(path: Path) -> set[str]:
    text = " ".join(part.lower() for part in path.parts[-6:])
    return {t for t in re.split(r"[^a-z0-9]+", text) if t}


def _safe_label(value: Any) -> str:
    text = str(value or "unknown")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return (cleaned or "unknown")[:40]


def _coerce(value: Any, allowed: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _env_roots() -> list[str] | None:
    raw = os.environ.get("PRIVATE_INVENTORY_ROOTS")
    if not raw:
        return None
    roots = [p for p in raw.split(os.pathsep) if p]
    return roots or None


def main() -> int:
    summary = run_uncommon_deck_local_ocr_extraction(
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
