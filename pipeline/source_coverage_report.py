"""Pure source-coverage report builder.

The report is derived from already-sanitized ``extraction_metadata.json`` and,
optionally, ``visual_assets_manifest.json`` shaped dictionaries. It performs no
file I/O, imports no extractor/provider modules, and emits counts/status tokens
only. Raw source names, paths, text, captions, provider payloads, and exception
messages are never copied into the output.
"""
from __future__ import annotations

from typing import Any

REPORT_VERSION = 1
REPORT_KIND = "source_coverage_report"

_WARNING_ORDER = [
    "metadata_missing",
    "metadata_skipped",
    "metadata_malformed",
    "source_malformed",
    "page_malformed",
    "page_count_mismatch",
    "visual_manifest_malformed",
    "visual_page_out_of_range",
    "unknown_method",
]
_WARNING_SET = set(_WARNING_ORDER)
_SOURCE_STATUSES = {"complete", "partial", "skipped", "unreadable", "unknown"}
_SOURCE_TYPES = {"pdf", "non_pdf", "unknown"}
_PAGE_METHODS = {"embedded_text", "ocr", "none", "unknown"}


def build_source_coverage_report(
    extraction_metadata: dict | None,
    *,
    visual_manifest: dict | None = None,
) -> dict:
    """Build a deterministic, no-leak source coverage report.

    The function is intentionally total: malformed or unavailable input produces
    a skipped/partial report with closed-vocabulary warning tokens instead of
    raising or echoing raw errors.
    """
    try:
        return _build_report(extraction_metadata, visual_manifest)
    except Exception:
        return _empty_report("skipped", ["metadata_malformed"])


def _build_report(extraction_metadata: Any, visual_manifest: Any) -> dict:
    warnings: list[str] = []

    if extraction_metadata is None:
        return _empty_report("skipped", ["metadata_missing"])
    if not isinstance(extraction_metadata, dict):
        return _empty_report("skipped", ["metadata_malformed"])
    if extraction_metadata.get("kind") != "extraction_metadata":
        return _empty_report("skipped", ["metadata_malformed"])

    metadata_status = extraction_metadata.get("status")
    if metadata_status == "skipped":
        return _empty_report("skipped", ["metadata_skipped"])
    if metadata_status != "completed":
        warnings.append("metadata_malformed")

    raw_sources = extraction_metadata.get("sources")
    if not isinstance(raw_sources, list):
        return _empty_report("skipped", _merge_warnings(warnings, ["metadata_malformed"]))

    sources: list[dict[str, Any]] = []
    page_counts: dict[int, int] = {}
    for source_index, source in enumerate(raw_sources, start=1):
        source_report = _source_report(source, source_index)
        sources.append(source_report)
        page_counts[source_index] = source_report["page_count"]
        warnings.extend(source_report["warnings"])

    visual_summary_count, visual_by_source, visual_warnings = _visual_coverage(
        visual_manifest,
        source_count=len(sources),
        page_counts=page_counts,
    )
    warnings.extend(visual_warnings)
    for source in sources:
        source["visual_candidate_page_count"] = len(visual_by_source.get(source["source_index"], set()))

    summary = _summary_from_sources(sources)
    summary["visual_candidate_pages"] = visual_summary_count

    status = _top_level_status(sources, warnings)
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": status,
        "summary": summary,
        "sources": sources,
        "warnings": _merge_warnings(warnings),
    }


def _source_report(source: Any, source_index: int) -> dict[str, Any]:
    if not isinstance(source, dict):
        return _blank_source(
            source_index,
            source_type="unknown",
            status="unknown",
            warnings=["source_malformed"],
        )

    warnings: list[str] = []
    source_type = _source_type(source)
    if source.get("status") == "skipped":
        return _blank_source(
            source_index,
            source_type=source_type,
            status="skipped",
            warnings=["metadata_skipped"],
        )

    pages = source.get("pages")
    if not isinstance(pages, list):
        return _blank_source(
            source_index,
            source_type=source_type,
            status="skipped",
            warnings=["source_malformed"],
        )

    declared_page_count = _safe_nonnegative_int(source.get("page_count"))
    page_records: dict[int, dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            warnings.append("page_malformed")
            continue
        page_number = _positive_int(page.get("page"))
        if page_number is None:
            warnings.append("page_malformed")
            continue
        page_records.setdefault(page_number, page)

    if not page_records:
        return _blank_source(
            source_index,
            source_type=source_type,
            status="skipped",
            page_count=declared_page_count,
            warnings=_merge_warnings(warnings, ["page_malformed"] if pages else []),
        )

    inferred_page_count = max(page_records)
    page_count = declared_page_count or inferred_page_count
    if declared_page_count and (
        len(page_records) != declared_page_count or inferred_page_count > declared_page_count
    ):
        warnings.append("page_count_mismatch")

    embedded_text_pages = 0
    ocr_pages = 0
    empty_or_unreadable_pages = 0
    anchor_pages = 0
    covered_pages = 0

    for page in page_records.values():
        method = _safe_method(page.get("method"))
        if method == "unknown":
            warnings.append("unknown_method")
        text_chars = _safe_nonnegative_int(page.get("text_chars"))
        word_count = _safe_nonnegative_int(page.get("word_count"))
        has_anchor = bool(page.get("has_page_anchor"))

        if method == "embedded_text":
            embedded_text_pages += 1
        elif method == "ocr":
            ocr_pages += 1
        if method == "none" or (text_chars == 0 and word_count == 0 and not has_anchor):
            empty_or_unreadable_pages += 1
        if has_anchor:
            anchor_pages += 1
        if _page_is_covered(method, text_chars, word_count, has_anchor):
            covered_pages += 1

    status = _coverage_status(page_count, covered_pages, warnings)
    return {
        "source_index": source_index,
        "source_type": source_type,
        "status": status,
        "page_count": page_count,
        "covered_page_count": covered_pages,
        "embedded_text_page_count": embedded_text_pages,
        "ocr_page_count": ocr_pages,
        "empty_or_unreadable_page_count": empty_or_unreadable_pages,
        "anchor_page_count": anchor_pages,
        "visual_candidate_page_count": 0,
        "warnings": _merge_warnings(warnings),
    }


def _visual_coverage(
    visual_manifest: Any,
    *,
    source_count: int,
    page_counts: dict[int, int],
) -> tuple[int, dict[int, set[int]], list[str]]:
    if visual_manifest is None:
        return 0, {}, []
    if not isinstance(visual_manifest, dict):
        return 0, {}, ["visual_manifest_malformed"]

    assets = visual_manifest.get("assets")
    if not isinstance(assets, list):
        return 0, {}, ["visual_manifest_malformed"]

    warnings: list[str] = []
    global_pages: set[int] = set()
    by_source: dict[int, set[int]] = {}
    max_page_count = max(page_counts.values(), default=0)

    for asset in assets:
        if not isinstance(asset, dict):
            warnings.append("visual_manifest_malformed")
            continue
        page_number = _positive_int(asset.get("source_page"))
        if page_number is None:
            warnings.append("visual_page_out_of_range")
            continue

        source_index = _positive_int(asset.get("source_index"))
        if source_index is not None:
            source_pages = page_counts.get(source_index)
            if source_pages is None or page_number > source_pages:
                warnings.append("visual_page_out_of_range")
                continue
            by_source.setdefault(source_index, set()).add(page_number)
            continue

        if source_count == 1:
            source_pages = page_counts.get(1, 0)
            if source_pages and page_number > source_pages:
                warnings.append("visual_page_out_of_range")
                continue
            by_source.setdefault(1, set()).add(page_number)
        else:
            if max_page_count and page_number > max_page_count:
                warnings.append("visual_page_out_of_range")
                continue
            global_pages.add(page_number)

    attributed_page_count = sum(len(pages) for pages in by_source.values())
    return len(global_pages) + attributed_page_count, by_source, _merge_warnings(warnings)


def _summary_from_sources(sources: list[dict[str, Any]]) -> dict[str, int]:
    summary = _empty_summary()
    summary["source_count"] = len(sources)
    for source in sources:
        summary["pdf_source_count"] += 1 if source["source_type"] == "pdf" else 0
        summary["total_pages"] += source["page_count"]
        summary["covered_pages"] += source["covered_page_count"]
        summary["embedded_text_pages"] += source["embedded_text_page_count"]
        summary["ocr_pages"] += source["ocr_page_count"]
        summary["empty_or_unreadable_pages"] += source["empty_or_unreadable_page_count"]
        summary["anchor_pages"] += source["anchor_page_count"]
        status = source["status"]
        if status == "complete":
            summary["complete_source_count"] += 1
        elif status == "partial":
            summary["partial_source_count"] += 1
        elif status == "skipped":
            summary["skipped_source_count"] += 1
        elif status == "unreadable":
            summary["unreadable_source_count"] += 1
    return summary


def _top_level_status(sources: list[dict[str, Any]], warnings: list[str]) -> str:
    if not sources:
        return "skipped"
    if any(source["status"] != "complete" for source in sources):
        return "partial"
    if any(warning in {"metadata_malformed", "source_malformed", "page_malformed"} for warning in warnings):
        return "partial"
    return "completed"


def _coverage_status(page_count: int, covered_pages: int, warnings: list[str]) -> str:
    if page_count <= 0:
        return "skipped"
    if covered_pages >= page_count and "page_count_mismatch" not in warnings:
        return "complete"
    if covered_pages > 0:
        return "partial"
    return "unreadable"


def _page_is_covered(method: str, text_chars: int, word_count: int, has_anchor: bool) -> bool:
    if has_anchor:
        return True
    if method in {"embedded_text", "ocr"} and (text_chars > 0 or word_count > 0):
        return True
    return False


def _blank_source(
    source_index: int,
    *,
    source_type: str,
    status: str,
    page_count: int = 0,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_index": source_index,
        "source_type": source_type if source_type in _SOURCE_TYPES else "unknown",
        "status": status if status in _SOURCE_STATUSES else "unknown",
        "page_count": page_count,
        "covered_page_count": 0,
        "embedded_text_page_count": 0,
        "ocr_page_count": 0,
        "empty_or_unreadable_page_count": 0,
        "anchor_page_count": 0,
        "visual_candidate_page_count": 0,
        "warnings": _merge_warnings(warnings or []),
    }


def _empty_report(status: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "version": REPORT_VERSION,
        "kind": REPORT_KIND,
        "status": status,
        "summary": _empty_summary(),
        "sources": [],
        "warnings": _merge_warnings(warnings),
    }


def _empty_summary() -> dict[str, int]:
    return {
        "source_count": 0,
        "pdf_source_count": 0,
        "total_pages": 0,
        "covered_pages": 0,
        "embedded_text_pages": 0,
        "ocr_pages": 0,
        "empty_or_unreadable_pages": 0,
        "anchor_pages": 0,
        "visual_candidate_pages": 0,
        "complete_source_count": 0,
        "partial_source_count": 0,
        "skipped_source_count": 0,
        "unreadable_source_count": 0,
    }


def _source_type(source: dict[str, Any]) -> str:
    source_type = source.get("source_type")
    if source_type in _SOURCE_TYPES:
        return source_type
    content_type = source.get("content_type")
    if content_type == "application/pdf":
        return "pdf"
    if isinstance(content_type, str) and content_type:
        return "non_pdf"
    return "unknown"


def _safe_method(method: Any) -> str:
    if isinstance(method, str) and method in _PAGE_METHODS:
        return method
    return "unknown"


def _safe_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    return value if value > 0 else None


def _merge_warnings(*groups: list[str]) -> list[str]:
    present = {warning for group in groups for warning in group if warning in _WARNING_SET}
    return [warning for warning in _WARNING_ORDER if warning in present]
