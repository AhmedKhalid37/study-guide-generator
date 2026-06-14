"""Pure page/slide inclusion-exclusion model.

Slice 78 (Full Material Coverage foundation): a deterministic, stdlib-only model
for representing user-controlled page/slide inclusion and exclusion per
attachment. It is intentionally unwired — no request schema, job manifest,
extraction, visual manifest, render/export, UI, prompt, or provider depends on it
yet. Future slices may persist this with job requests, expose Builder controls,
and apply it to extraction/content planning and visual/table manifests.

The model emits 1-based page numbers, counts, mode tokens, and closed-vocabulary
warning tokens only. It performs no file I/O, imports no extractor/provider/render
modules, and never raises on malformed input — it degrades to a safe normalized
output with warnings. Raw source names, paths, document text, OCR text, captions,
table text, image refs, provider payloads, and exception messages are never
copied into the output.
"""
from __future__ import annotations

from typing import Any

SELECTION_VERSION = 1

MODE_ALL = "all"
MODE_INCLUDE = "include"
MODE_EXCLUDE = "exclude"
MODES = {MODE_ALL, MODE_INCLUDE, MODE_EXCLUDE}

_WARNING_ORDER = [
    "selection_missing",
    "selection_malformed",
    "mode_unknown",
    "page_invalid",
    "page_out_of_range",
    "page_count_invalid",
    "include_empty",
    "exclude_overlaps_include",
]
_WARNING_SET = set(_WARNING_ORDER)


def normalize_page_selection(
    selection: dict | None,
    *,
    page_count: int | None = None,
) -> dict:
    """Return a safe normalized page-selection dict.

    Shape::

        {
            "version": 1,
            "mode": "all" | "include" | "exclude",
            "include_pages": [1, 2, 3],
            "exclude_pages": [4, 5],
            "warnings": [],
        }

    The function is total: missing/malformed input degrades to ``mode: all`` with
    closed-vocabulary warning tokens instead of raising. Pages are positive 1-based
    integers, deduplicated and sorted. When ``page_count`` is a valid positive int,
    pages outside ``1..page_count`` are dropped with a warning.
    """
    try:
        return _normalize(selection, page_count)
    except Exception:
        # Defensive: the body above is already total, but never let an advisory
        # model raise into a caller.
        return _normalized(MODE_ALL, [], [], ["selection_malformed"])


def apply_page_selection(page_numbers: list[int], selection: dict | None) -> dict:
    """Apply a (normalized or raw) selection to a concrete list of page numbers.

    Shape::

        {
            "included_pages": [1, 2],
            "excluded_pages": [3],
            "effective_mode": "all" | "include" | "exclude",
            "warnings": [],
        }

    ``page_numbers`` is the universe of pages actually present; it may be unsorted
    and may contain invalid values, which are dropped with a warning. Page numbers
    are never inferred when none are provided. Deterministic and degrade-never-fail.
    """
    try:
        return _apply(page_numbers, selection)
    except Exception:
        return {
            "included_pages": [],
            "excluded_pages": [],
            "effective_mode": MODE_ALL,
            "warnings": ["selection_malformed"],
        }


def summarize_page_selection(
    selection: dict | None,
    *,
    page_count: int | None = None,
) -> dict:
    """Return counts-only summary of a page selection.

    Shape::

        {
            "version": 1,
            "mode": "all" | "include" | "exclude",
            "included_page_count": 0,
            "excluded_page_count": 0,
            "explicit_include_count": 0,
            "explicit_exclude_count": 0,
            "warnings": [],
        }

    When ``page_count`` is a valid positive int the included/excluded counts are
    derived from the concrete universe ``1..page_count``. Without a known universe,
    the counts reflect only what is knowable from the explicit lists.
    """
    try:
        return _summarize(selection, page_count)
    except Exception:
        return {
            "version": SELECTION_VERSION,
            "mode": MODE_ALL,
            "included_page_count": 0,
            "excluded_page_count": 0,
            "explicit_include_count": 0,
            "explicit_exclude_count": 0,
            "warnings": ["selection_malformed"],
        }


def _normalize(selection: Any, page_count: Any) -> dict:
    warnings: list[str] = []
    effective_count = _effective_page_count(page_count, warnings)

    if selection is None:
        return _normalized(MODE_ALL, [], [], _merge_warnings(warnings, ["selection_missing"]))
    if not isinstance(selection, dict):
        return _normalized(MODE_ALL, [], [], _merge_warnings(warnings, ["selection_malformed"]))

    mode = _safe_mode(selection.get("mode"), warnings)

    include_pages = _clean_pages(selection.get("include_pages"), effective_count, warnings)
    exclude_pages = _clean_pages(selection.get("exclude_pages"), effective_count, warnings)

    if set(include_pages) & set(exclude_pages):
        warnings.append("exclude_overlaps_include")

    if mode == MODE_INCLUDE and not include_pages:
        warnings.append("include_empty")

    return _normalized(mode, include_pages, exclude_pages, _merge_warnings(warnings))


def _apply(page_numbers: Any, selection: Any) -> dict:
    warnings: list[str] = []
    universe = _clean_pages(page_numbers, None, warnings)
    universe_set = set(universe)

    normalized = normalize_page_selection(selection)
    warnings.extend(normalized["warnings"])

    mode = normalized["mode"]
    include_set = set(normalized["include_pages"])
    exclude_set = set(normalized["exclude_pages"])

    if mode == MODE_INCLUDE:
        candidate = universe_set & include_set
    else:
        # all and exclude both start from the full universe
        candidate = set(universe_set)

    included = candidate - exclude_set
    excluded = universe_set - included

    return {
        "included_pages": sorted(included),
        "excluded_pages": sorted(excluded),
        "effective_mode": mode,
        "warnings": _merge_warnings(warnings),
    }


def _summarize(selection: Any, page_count: Any) -> dict:
    normalized = normalize_page_selection(selection, page_count=page_count)
    mode = normalized["mode"]
    include_pages = normalized["include_pages"]
    exclude_pages = normalized["exclude_pages"]
    warnings = list(normalized["warnings"])

    effective_count = _effective_page_count(page_count, [])
    if effective_count is not None:
        applied = apply_page_selection(list(range(1, effective_count + 1)), normalized)
        included_count = len(applied["included_pages"])
        excluded_count = len(applied["excluded_pages"])
    elif mode == MODE_INCLUDE:
        # Bounded by the explicit include list when no universe is known.
        included_count = len(set(include_pages) - set(exclude_pages))
        excluded_count = len(set(exclude_pages))
    else:
        # all/exclude included count is unknowable without a universe.
        included_count = 0
        excluded_count = len(set(exclude_pages))

    return {
        "version": SELECTION_VERSION,
        "mode": mode,
        "included_page_count": included_count,
        "excluded_page_count": excluded_count,
        "explicit_include_count": len(include_pages),
        "explicit_exclude_count": len(exclude_pages),
        "warnings": _merge_warnings(warnings),
    }


def _normalized(
    mode: str,
    include_pages: list[int],
    exclude_pages: list[int],
    warnings: list[str],
) -> dict:
    return {
        "version": SELECTION_VERSION,
        "mode": mode if mode in MODES else MODE_ALL,
        "include_pages": sorted(set(include_pages)),
        "exclude_pages": sorted(set(exclude_pages)),
        "warnings": _merge_warnings(warnings),
    }


def _safe_mode(mode: Any, warnings: list[str]) -> str:
    if mode is None:
        # Unspecified mode is a valid default (all); not a malformed input.
        return MODE_ALL
    if mode in MODES:
        return mode
    warnings.append("mode_unknown")
    return MODE_ALL


def _clean_pages(value: Any, effective_count: int | None, warnings: list[str]) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.append("selection_malformed")
        return []

    pages: set[int] = set()
    for item in value:
        page = _positive_int(item)
        if page is None:
            warnings.append("page_invalid")
            continue
        if effective_count is not None and page > effective_count:
            warnings.append("page_out_of_range")
            continue
        pages.add(page)
    return sorted(pages)


def _effective_page_count(page_count: Any, warnings: list[str]) -> int | None:
    if page_count is None:
        return None
    count = _positive_int(page_count)
    if count is None:
        warnings.append("page_count_invalid")
        return None
    return count


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int):
        return None
    return value if value > 0 else None


def _merge_warnings(*groups: list[str]) -> list[str]:
    present = {warning for group in groups for warning in group if warning in _WARNING_SET}
    return [warning for warning in _WARNING_ORDER if warning in present]
