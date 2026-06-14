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


# ── Slice 81: apply a material selection to a concrete extraction page universe ──
#
# Closed-vocabulary extraction-application warnings, kept SEPARATE from the
# selection-model warnings above. These describe how a material selection mapped
# onto an attachment's extractable page universe; they carry no page lists,
# filenames, or paths.
APPLY_WARNING_NO_MATCHING_PAGES = "material_selection_no_matching_pages"
APPLY_WARNING_UNIVERSE_UNKNOWN = "material_selection_universe_unknown"
APPLY_WARNING_FILTERED_BY_EXISTING = "material_selection_filtered_by_existing_page_selection"
_APPLY_WARNING_ORDER = [
    APPLY_WARNING_FILTERED_BY_EXISTING,
    APPLY_WARNING_NO_MATCHING_PAGES,
    APPLY_WARNING_UNIVERSE_UNKNOWN,
]
_APPLY_WARNING_SET = set(_APPLY_WARNING_ORDER)


def apply_material_selection_to_page_universe(
    material_selection: dict | None,
    *,
    existing_allowed_pages: list[int] | None = None,
    natural_pages: list[int] | None = None,
) -> dict:
    """Compute the effective extraction page set for one attachment (Slice 81).

    ``existing_allowed_pages`` is the maximum page universe (e.g. the load-bearing
    ``page_selections`` page-range set); when present a material selection can only
    further filter it, never expand it. ``natural_pages`` is the attachment's full
    page universe when known. Either may be ``None``.

    Returns::

        {
            "included_pages": [sorted 1-based ints],   # explicit set to extract
            "excluded_pages": [sorted 1-based ints],   # removed from the universe
            "warnings": [closed apply-tokens],
            "resolved": bool,   # True => included_pages is an explicit set to pass
        }

    ``resolved`` is ``False`` only when the selection cannot be represented as an
    explicit page set (an ``exclude``/``all`` selection with no known universe);
    the caller should then leave extraction unchanged and surface
    ``material_selection_universe_unknown``. Never raises. ``include`` selections
    are always resolvable because the include list IS an explicit page set.
    """
    norm = normalize_page_selection(material_selection)
    mode = norm["mode"]
    include = {p for p in (_positive_int(x) for x in norm["include_pages"]) if p is not None}
    exclude = {p for p in (_positive_int(x) for x in norm["exclude_pages"]) if p is not None}

    universe: set[int] | None = None
    if existing_allowed_pages is not None:
        universe = {p for p in (_positive_int(x) for x in existing_allowed_pages) if p is not None}
    elif natural_pages is not None:
        universe = {p for p in (_positive_int(x) for x in natural_pages) if p is not None}

    warnings: list[str] = []

    if mode == MODE_INCLUDE:
        result = set(include)
        if universe is not None:
            result &= universe
        result -= exclude
        excluded = sorted((universe - result) if universe is not None else (include - result))
        resolved = True
    else:  # all / exclude — needs a known universe to enumerate
        if universe is None:
            return {
                "included_pages": [],
                "excluded_pages": [],
                "warnings": [APPLY_WARNING_UNIVERSE_UNKNOWN],
                "resolved": False,
            }
        result = universe - exclude
        excluded = sorted(universe - result)
        resolved = True

    if existing_allowed_pages is not None:
        warnings.append(APPLY_WARNING_FILTERED_BY_EXISTING)
    if not result:
        warnings.append(APPLY_WARNING_NO_MATCHING_PAGES)

    return {
        "included_pages": sorted(result),
        "excluded_pages": excluded,
        "warnings": [w for w in _APPLY_WARNING_ORDER if w in set(warnings)],
        "resolved": resolved,
    }


# ── Slice 82: apply a material selection to visual/table manifest records ──
#
# Closed-vocabulary visual/table manifest filter tokens, kept SEPARATE from the
# selection-model and extraction-apply tokens above. They report HOW a material
# selection mapped onto a manifest record's source page; they carry no page
# lists, filenames, paths, captions, image refs, or text.
VISUAL_FILTER_DROPPED = "material_selection_visual_filtered"
VISUAL_FILTER_PAGE_UNKNOWN = "material_selection_visual_page_unknown"
VISUAL_FILTER_NO_MATCHING_PAGES = "material_selection_visual_no_matching_pages"
VISUAL_FILTER_TABLE_NOT_PRESENT = "material_selection_table_manifest_not_present"
VISUAL_FILTER_TOKENS = [
    VISUAL_FILTER_DROPPED,
    VISUAL_FILTER_PAGE_UNKNOWN,
    VISUAL_FILTER_NO_MATCHING_PAGES,
    VISUAL_FILTER_TABLE_NOT_PRESENT,
]
_VISUAL_FILTER_SET = set(VISUAL_FILTER_TOKENS)


def page_is_in_material_selection(source_page: Any, allowed_pages: Any) -> dict:
    """Decide whether a visual/table manifest record survives a material filter (Slice 82).

    ``allowed_pages`` is the EFFECTIVE post-material allowed page set for the
    record's source — a collection of positive 1-based ints — or ``None`` when no
    material selection is active for that source (keep everything; existing
    behaviour). It is the *same* effective set Slice 81 computed for extraction
    (``apply_material_selection_to_page_universe`` ∩ the load-bearing
    ``page_selections`` universe), so a material selection can never keep a visual
    record on a page that ``page_selections`` already excluded, nor expand beyond it.

    Returns ``{"kept": bool, "status": <closed token or None>}``:

    * ``allowed_pages`` is ``None`` ⇒ ``kept=True, status=None`` (no active filter).
    * ``source_page`` missing/invalid (≤ 0) under an active filter ⇒ ``kept=False,
      status=material_selection_visual_page_unknown`` — a record whose page cannot
      be verified is dropped conservatively so a user-excluded page can never
      surface a visual.
    * ``source_page`` in ``allowed_pages`` ⇒ ``kept=True, status=None``.
    * ``source_page`` not in ``allowed_pages`` ⇒ ``kept=False,
      status=material_selection_visual_filtered``.

    Pure, stdlib-only, total — never raises.
    """
    if allowed_pages is None:
        return {"kept": True, "status": None}
    allowed = {p for p in (_positive_int(x) for x in allowed_pages) if p is not None}
    page = _positive_int(source_page)
    if page is None:
        return {"kept": False, "status": VISUAL_FILTER_PAGE_UNKNOWN}
    if page in allowed:
        return {"kept": True, "status": None}
    return {"kept": False, "status": VISUAL_FILTER_DROPPED}
