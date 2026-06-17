"""Quality Safety extraction-bundle adapter v1 (Slice 121).

Pure, **unwired** adapter that maps already-sanitized structural extraction /
coverage artifacts into a normalized *structural coverage bundle* that the Slice
117 fact-sheet producer can be handed later. It is grounded in the Slice 120
metadata inspection (`docs/QUALITY_SAFETY_E2E_VALIDATION.md`):

* extraction / page / visual / table metadata exists structurally;
* safe structural counts are recoverable (``leaf_count_recoverable=yes``);
* per-fact numeric content observations are **not** recoverable today
  (``numeric_observation_recoverable=no``) — so v1 never fabricates numeric
  observations;
* the raw extraction metadata artifact carries a source *basename*, so the
  already-sanitized source coverage report (keyed by an integer source ordinal,
  not a basename) is the preferred input surface and names are never echoed;
* the page-reference shape is ``mixed`` across artifacts, so page refs are
  normalized to closed tokens and a ``mixed_page_ref_shape`` warning is emitted
  when shapes differ.

Naming note (see ``docs/DECISIONS.md``): the producer already owns the kind
``quality_safety_extraction_bundle`` and a ``normalize_quality_safety_extraction_bundle``
function for a *concept/fact* bundle. To avoid a name/shape collision, this v1
adapter emits the distinct kind ``quality_safety_extraction_coverage_bundle`` and
uses ``..._coverage_bundle...`` function names. When such a bundle is passed to
the producer it degrades safely to an empty/partial fact sheet (it has no
``concepts``), which is the intended compatibility for v1.

Purity contract: imports stdlib only; reads only caller-supplied in-memory dicts;
scans no directories; reads no job folders, source documents, or ``clean.md``;
writes no artifacts; calls no providers/models/cloud; imports no FastAPI /
frontend / render / OCR / job-runtime modules; never raises on malformed input;
never mutates caller input.
"""
from __future__ import annotations

import math
import re
from typing import Any

VERSION = 1
BUNDLE_KIND = "quality_safety_extraction_coverage_bundle"

# --- Closed vocabularies (this module owns exactly what it emits) -------------

BUNDLE_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
RECORD_STATUSES = frozenset({"ok", "warning", "skipped", "missing", "unknown"})
RECORD_TYPES = frozenset({"source", "page", "visual", "table", "material_selection"})
SOURCE_QUALITIES = frozenset({"synthetic", "runtime_structural", "unknown"})

# Deterministic warning order for stable serialization.
WARNING_ORDER = (
    "component_missing",
    "input_not_dict",
    "malformed_input",
    "unsupported_record_shape",
    "source_name_excluded",
    "path_excluded",
    "raw_text_excluded",
    "unsafe_field_excluded",
    "count_coerced",
    "mixed_page_ref_shape",
    "numeric_observations_not_recoverable",
    "max_items_reached",
)
_WARNING_SET = frozenset(WARNING_ORDER)

# Map of upstream status tokens -> our closed record vocabulary. Anything not
# listed degrades to ``unknown`` (never echoed verbatim).
_STATUS_MAP = {
    "ok": "ok",
    "complete": "ok",
    "completed": "ok",
    "passed": "ok",
    "covered": "ok",
    "partial": "partial_record",  # remapped below (records have no "partial")
    "warning": "warning",
    "unreadable": "warning",
    "uncovered": "warning",
    "skipped": "skipped",
    "missing": "missing",
    "unknown": "unknown",
    "failed": "warning",
}

_DEFAULT_MAX_ITEMS = 200

_SAFE_SOURCE_REF_RE = re.compile(r"^(?:source_[0-9]{1,4}|page_range|unknown)$")
_SAFE_PAGE_REF_RE = re.compile(r"^(?:page_[0-9]{1,4}|page_range|unknown)$")
_SAFE_GENERATED_ID_RE = re.compile(r"^qs_extract_[0-9]{4,}$")


# --- Public API ---------------------------------------------------------------


def build_empty_quality_safety_extraction_coverage_bundle(
    reason: str = "component_missing",
) -> dict[str, Any]:
    """Return a safe, empty, skipped coverage bundle.

    ``reason`` is coerced to a closed warning token; anything unrecognized
    becomes ``component_missing``.
    """
    token = reason if reason in _WARNING_SET else "component_missing"
    return _bundle(
        status="skipped",
        source_quality="unknown",
        records=[],
        warnings={token},
    )


def normalize_quality_safety_extraction_coverage_bundle(
    data: Any, *, max_items: int | None = None
) -> dict[str, Any]:
    """Normalize a coverage-bundle-shaped dict; never raise, never mutate input.

    Idempotent: re-normalizing a bundle this module produced returns an equal
    bundle. Unsafe strings, unknown tokens, and non-finite counts are dropped or
    coerced with closed warning tokens.
    """
    try:
        return _normalize_bundle(data, max_items=max_items)
    except Exception:
        return _bundle(
            status="failed",
            source_quality="unknown",
            records=[],
            warnings={"malformed_input"},
        )


def build_quality_safety_extraction_coverage_bundle_from_artifacts(
    *,
    source_coverage_report: Any = None,
    extraction_metadata: Any = None,
    visual_inclusion_plan: Any = None,
    table_candidates_manifest: Any = None,
    table_reconstruction_policy: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Build a structural coverage bundle from already-sanitized artifacts.

    Prefers the sanitized source coverage report (keyed by source ordinal) over
    the raw extraction metadata artifact (which may carry a source basename).
    Reads only structural counts/statuses; never names, paths, text, or numeric
    content observations. Never raises.
    """
    try:
        return _build_from_artifacts(
            source_coverage_report=source_coverage_report,
            extraction_metadata=extraction_metadata,
            visual_inclusion_plan=visual_inclusion_plan,
            table_candidates_manifest=table_candidates_manifest,
            table_reconstruction_policy=table_reconstruction_policy,
            max_items=max_items,
        )
    except Exception:
        return _bundle(
            status="failed",
            source_quality="unknown",
            records=[],
            warnings={"malformed_input"},
        )


# --- Builder core -------------------------------------------------------------


def _build_from_artifacts(
    *,
    source_coverage_report: Any,
    extraction_metadata: Any,
    visual_inclusion_plan: Any,
    table_candidates_manifest: Any,
    table_reconstruction_policy: Any,
    max_items: Any,
) -> dict[str, Any]:
    cap = _cap(max_items)
    warnings: set[str] = set()
    records: list[dict[str, Any]] = []
    counter = _Counter()

    have_any = any(
        isinstance(artifact, dict)
        for artifact in (
            source_coverage_report,
            extraction_metadata,
            visual_inclusion_plan,
            table_candidates_manifest,
            table_reconstruction_policy,
        )
    )
    if not have_any:
        return build_empty_quality_safety_extraction_coverage_bundle("component_missing")

    # Source / page records: prefer the sanitized coverage report.
    if isinstance(source_coverage_report, dict):
        _append_source_records_from_coverage(
            source_coverage_report, records, warnings, counter, cap
        )
    elif isinstance(extraction_metadata, dict):
        warnings.add("source_name_excluded")
        _append_source_records_from_extraction(
            extraction_metadata, records, warnings, counter, cap
        )
    elif extraction_metadata is not None or source_coverage_report is not None:
        warnings.add("malformed_input")

    # Visual record(s).
    if visual_inclusion_plan is not None:
        _append_visual_record(visual_inclusion_plan, records, warnings, counter, cap)

    # Table record(s) (candidates and/or policy).
    if table_candidates_manifest is not None or table_reconstruction_policy is not None:
        _append_table_record(
            table_candidates_manifest,
            table_reconstruction_policy,
            records,
            warnings,
            counter,
            cap,
        )

    if len(records) > cap:
        warnings.add("max_items_reached")
        records = records[:cap]

    return _bundle(
        status=_status_from(records, warnings),
        source_quality="runtime_structural",
        records=records,
        warnings=warnings,
    )


def _append_source_records_from_coverage(
    report: dict[str, Any],
    records: list[dict[str, Any]],
    warnings: set[str],
    counter: "_Counter",
    cap: int,
) -> None:
    sources = report.get("sources")
    if not isinstance(sources, list):
        warnings.add("malformed_input")
        return
    if len(sources) > cap:
        warnings.add("max_items_reached")
    for ordinal, source in enumerate(sources[:cap], start=1):
        if len(records) >= cap:
            warnings.add("max_items_reached")
            return
        if not isinstance(source, dict):
            warnings.add("unsupported_record_shape")
            continue
        page_count = _safe_count(source.get("page_count"), warnings)
        visual_count = _safe_count(source.get("visual_candidate_page_count"), warnings)
        records.append(
            _record(
                counter=counter,
                source_ref=f"source_{ordinal}",
                page_ref=None,
                record_type="source",
                status=_map_status(source.get("status")),
                page_count=page_count,
                selected_page_count=None,
                visual_count=visual_count,
                table_count=None,
                record_warnings=set(),
            )
        )


def _append_source_records_from_extraction(
    metadata: dict[str, Any],
    records: list[dict[str, Any]],
    warnings: set[str],
    counter: "_Counter",
    cap: int,
) -> None:
    """Read structural counts only from the raw, name-bearing extraction artifact.

    Source names/paths/text are never read; only per-source page counts/status and
    optional per-page reference *shape* (to detect ``mixed_page_ref_shape``).
    """
    sources = metadata.get("sources")
    if not isinstance(sources, list):
        warnings.add("malformed_input")
        return
    if len(sources) > cap:
        warnings.add("max_items_reached")
    for ordinal, source in enumerate(sources[:cap], start=1):
        if len(records) >= cap:
            warnings.add("max_items_reached")
            return
        if not isinstance(source, dict):
            warnings.add("unsupported_record_shape")
            continue
        page_count = _safe_count(source.get("page_count"), warnings)
        records.append(
            _record(
                counter=counter,
                source_ref=f"source_{ordinal}",
                page_ref=None,
                record_type="source",
                status=_map_status(source.get("status")),
                page_count=page_count,
                selected_page_count=_safe_optional_count(
                    source.get("selected_page_count"), warnings
                ),
                visual_count=None,
                table_count=None,
                record_warnings=set(),
            )
        )
        _maybe_append_page_records(
            source.get("pages"), ordinal, records, warnings, counter, cap
        )


def _maybe_append_page_records(
    pages: Any,
    ordinal: int,
    records: list[dict[str, Any]],
    warnings: set[str],
    counter: "_Counter",
    cap: int,
) -> None:
    if not isinstance(pages, list):
        return
    shapes: set[str] = set()
    page_refs: list[str] = []
    for page in pages:
        ref, shape = _page_ref_and_shape(page)
        shapes.add(shape)
        page_refs.append(ref)
    if len({s for s in shapes if s != "none"}) > 1:
        warnings.add("mixed_page_ref_shape")
    for ref in page_refs:
        if len(records) >= cap:
            warnings.add("max_items_reached")
            return
        records.append(
            _record(
                counter=counter,
                source_ref=f"source_{ordinal}",
                page_ref=ref,
                record_type="page",
                status="ok",
                page_count=1,
                selected_page_count=None,
                visual_count=None,
                table_count=None,
                record_warnings=set(),
            )
        )


def _append_visual_record(
    plan: Any,
    records: list[dict[str, Any]],
    warnings: set[str],
    counter: "_Counter",
    cap: int,
) -> None:
    if len(records) >= cap:
        warnings.add("max_items_reached")
        return
    if not isinstance(plan, dict):
        warnings.add("malformed_input")
        return
    visual_count = _count_from_first(
        plan,
        ("included_count", "visual_count", "selected_count", "asset_count"),
        ("included", "items", "assets", "selections"),
        warnings,
    )
    records.append(
        _record(
            counter=counter,
            source_ref="unknown",
            page_ref=None,
            record_type="visual",
            status=_map_status(plan.get("status")),
            page_count=None,
            selected_page_count=None,
            visual_count=visual_count,
            table_count=None,
            record_warnings=set(),
        )
    )


def _append_table_record(
    manifest: Any,
    policy: Any,
    records: list[dict[str, Any]],
    warnings: set[str],
    counter: "_Counter",
    cap: int,
) -> None:
    if len(records) >= cap:
        warnings.add("max_items_reached")
        return
    table_count = None
    status = "unknown"
    if isinstance(manifest, dict):
        table_count = _count_from_first(
            manifest,
            ("candidate_count", "table_count"),
            ("candidates", "tables"),
            warnings,
        )
        status = _map_status(manifest.get("status"))
    elif manifest is not None:
        warnings.add("malformed_input")
    if isinstance(policy, dict):
        policy_count = _count_from_first(
            policy,
            ("actionable_count", "table_count", "decision_count"),
            ("actions", "decisions", "tables"),
            warnings,
        )
        if table_count is None:
            table_count = policy_count
        if status == "unknown":
            status = _map_status(policy.get("status"))
    elif policy is not None:
        warnings.add("malformed_input")
    records.append(
        _record(
            counter=counter,
            source_ref="unknown",
            page_ref=None,
            record_type="table",
            status=status,
            page_count=None,
            selected_page_count=None,
            visual_count=None,
            table_count=table_count,
            record_warnings=set(),
        )
    )


# --- Normalization core -------------------------------------------------------


def _normalize_bundle(data: Any, *, max_items: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _bundle(
            status="skipped",
            source_quality="unknown",
            records=[],
            warnings={"input_not_dict"},
        )
    cap = _cap(max_items)
    warnings: set[str] = set()
    for token in data.get("warnings", []) if isinstance(data.get("warnings"), list) else []:
        if token in _WARNING_SET:
            warnings.add(token)

    source_quality = data.get("source_quality")
    if source_quality not in SOURCE_QUALITIES:
        source_quality = "unknown"

    raw_records = data.get("coverage_records")
    if raw_records is None:
        raw_records = []
    if not isinstance(raw_records, list):
        warnings.add("malformed_input")
        raw_records = []
    if len(raw_records) > cap:
        warnings.add("max_items_reached")

    counter = _Counter()
    records: list[dict[str, Any]] = []
    for raw in raw_records[:cap]:
        record = _normalize_record(raw, counter, warnings)
        if record is None:
            warnings.add("unsupported_record_shape")
            continue
        records.append(record)

    # numeric_observations is always empty by policy.
    if not _is_empty_list(data.get("numeric_observations")):
        warnings.add("numeric_observations_not_recoverable")

    status = data.get("status")
    if status not in BUNDLE_STATUSES:
        status = _status_from(records, warnings)
    return _bundle(
        status=status,
        source_quality=source_quality,
        records=records,
        warnings=warnings,
    )


def _normalize_record(
    raw: Any, counter: "_Counter", warnings: set[str]
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    record_type = raw.get("record_type")
    if record_type not in RECORD_TYPES:
        record_type = "source"
        warnings.add("unsupported_record_shape")
    raw_counts = raw.get("counts") if isinstance(raw.get("counts"), dict) else {}
    return _record(
        counter=counter,
        source_ref=_safe_source_ref(raw.get("source_ref"), warnings),
        page_ref=_safe_page_ref(raw.get("page_ref"), warnings),
        record_type=record_type,
        status=raw.get("status") if raw.get("status") in RECORD_STATUSES else "unknown",
        page_count=_safe_optional_count(raw_counts.get("page_count"), warnings),
        selected_page_count=_safe_optional_count(raw_counts.get("selected_page_count"), warnings),
        visual_count=_safe_optional_count(raw_counts.get("visual_count"), warnings),
        table_count=_safe_optional_count(raw_counts.get("table_count"), warnings),
        record_warnings=_safe_record_warnings(raw.get("warnings")),
    )


# --- Assembly + summary -------------------------------------------------------


def _record(
    *,
    counter: "_Counter",
    source_ref: str | None,
    page_ref: str | None,
    record_type: str,
    status: str,
    page_count: int | None,
    selected_page_count: int | None,
    visual_count: int | None,
    table_count: int | None,
    record_warnings: set[str],
) -> dict[str, Any]:
    return {
        "id": counter.next_id(),
        "source_ref": source_ref if source_ref is not None else "unknown",
        "page_ref": page_ref,
        "record_type": record_type if record_type in RECORD_TYPES else "source",
        "status": status if status in RECORD_STATUSES else "unknown",
        "counts": {
            "page_count": page_count,
            "selected_page_count": selected_page_count,
            "visual_count": visual_count,
            "table_count": table_count,
        },
        "warnings": _ordered(record_warnings),
    }


def _bundle(
    *,
    status: str,
    source_quality: str,
    records: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    if records:
        warnings.add("numeric_observations_not_recoverable")
    summary = _summary(records)
    return {
        "version": VERSION,
        "kind": BUNDLE_KIND,
        "status": status if status in BUNDLE_STATUSES else "warning",
        "source_quality": source_quality if source_quality in SOURCE_QUALITIES else "unknown",
        "summary": summary,
        "coverage_records": records,
        "numeric_observations": [],
        "warnings": _ordered(warnings),
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    source_count = 0
    page_count = 0
    selected_page_count: int | None = None
    visual_count = 0
    table_count = 0
    for record in records:
        counts = record.get("counts", {})
        if record.get("record_type") == "source":
            source_count += 1
        page_count += _as_int(counts.get("page_count"))
        selected = counts.get("selected_page_count")
        if isinstance(selected, int) and not isinstance(selected, bool):
            selected_page_count = (selected_page_count or 0) + selected
        visual_count += _as_int(counts.get("visual_count"))
        table_count += _as_int(counts.get("table_count"))
    return {
        "source_count": source_count,
        "page_count": page_count,
        "selected_page_count": selected_page_count,
        "visual_count": visual_count,
        "table_count": table_count,
        "coverage_item_count": len(records),
        "numeric_observation_count": 0,
    }


def _status_from(records: list[dict[str, Any]], warnings: set[str]) -> str:
    if "max_items_reached" in warnings:
        return "partial"
    if not records:
        return "skipped"
    structural = {token for token in warnings if token != "numeric_observations_not_recoverable"}
    if structural:
        return "warning"
    return "ok"


# --- Safe primitives ----------------------------------------------------------


class _Counter:
    def __init__(self) -> None:
        self._n = 0

    def next_id(self) -> str:
        self._n += 1
        return f"qs_extract_{self._n:04d}"


def _map_status(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    mapped = _STATUS_MAP.get(value.strip().lower())
    if mapped == "partial_record":
        # records have no "partial"; partial coverage is a warning at record level
        return "warning"
    return mapped if mapped in RECORD_STATUSES else "unknown"


def _page_ref_and_shape(page: Any) -> tuple[str, str]:
    """Return (closed page_ref token, shape token) for a page entry.

    Never echoes a raw value: numeric pages -> ``page_{n}`` (shape ``numeric``);
    an explicit range marker -> ``page_range`` (shape ``range``); anything else ->
    ``unknown`` (shape ``other``); missing -> (``unknown``, ``none``).
    """
    if isinstance(page, dict):
        number = _positive_int(page.get("page"))
        if number is not None:
            return f"page_{min(number, 9999)}", "numeric"
        ref = page.get("page_ref")
        if isinstance(ref, str) and ref.strip().lower() in {"page_range", "page-range", "range"}:
            return "page_range", "range"
        if ref is not None or page.get("page") is not None:
            return "unknown", "other"
        return "unknown", "none"
    number = _positive_int(page)
    if number is not None:
        return f"page_{min(number, 9999)}", "numeric"
    return "unknown", "none"


def _safe_source_ref(value: Any, warnings: set[str]) -> str:
    if not isinstance(value, str):
        return "unknown"
    candidate = value.strip().lower()
    if _SAFE_SOURCE_REF_RE.fullmatch(candidate):
        return candidate
    if value:
        warnings.add("unsafe_field_excluded")
    return "unknown"


def _safe_page_ref(value: Any, warnings: set[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        warnings.add("unsafe_field_excluded")
        return None
    candidate = value.strip().lower()
    if _SAFE_PAGE_REF_RE.fullmatch(candidate):
        return candidate
    warnings.add("unsafe_field_excluded")
    return None


def _safe_record_warnings(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, list):
        for token in value:
            if token in _WARNING_SET:
                out.add(token)
    return out


def _safe_count(value: Any, warnings: set[str]) -> int:
    """Non-negative int (default 0). Coerces with ``count_coerced`` when needed."""
    number = _finite_number(value)
    if number is None:
        if value is not None:
            warnings.add("count_coerced")
        return 0
    coerced = int(number)
    if coerced < 0:
        warnings.add("count_coerced")
        return 0
    if coerced != number:
        warnings.add("count_coerced")
    return coerced


def _safe_optional_count(value: Any, warnings: set[str]) -> int | None:
    if value is None:
        return None
    number = _finite_number(value)
    if number is None:
        warnings.add("count_coerced")
        return None
    coerced = int(number)
    if coerced < 0:
        warnings.add("count_coerced")
        return 0
    if coerced != number:
        warnings.add("count_coerced")
    return coerced


def _count_from_first(
    data: dict[str, Any],
    int_keys: tuple[str, ...],
    list_keys: tuple[str, ...],
    warnings: set[str],
) -> int | None:
    for key in int_keys:
        if key in data:
            return _safe_count(data.get(key), warnings)
    for key in list_keys:
        value = data.get(key)
        if isinstance(value, list):
            return len(value)
    return None


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return value


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value if value >= 0 else 0


def _is_empty_list(value: Any) -> bool:
    return value is None or (isinstance(value, list) and not value)


def _cap(max_items: Any) -> int:
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        return max(0, min(max_items, _DEFAULT_MAX_ITEMS))
    return _DEFAULT_MAX_ITEMS


def _ordered(values: set[str]) -> list[str]:
    return [token for token in WARNING_ORDER if token in values]
