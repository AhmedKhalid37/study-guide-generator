"""Quality Safety **focused** table-structure extraction attempt (Slice 176A).

Slice 174A added the ``proximity`` / ``weighted_average`` recompute methods, and
Slices 174A/175A proved the two remaining Ensemble targets

  * ``proximity_4_3``        (method ``proximity``)
  * ``weighted_weight_impute`` (method ``weighted_average``)

stay blocked because no structured numeric *source-input* record exists for them:
the existing sidecar / fact-sheet / recompute chain produces no target records
parsed from extraction output. Slice 175A's audit settled the provenance question
(``producer_output_is_parsed_from_extraction=false``) and pointed the next real
artifact at local table-structure extraction.

This module is that **focused attempt** — deliberately scoped to exactly the two
target ids above, never a broad N-target sweep and never a generic table
reconstruction framework. It evaluates whatever closed signals the EXISTING local
table/visual stack already produces (region candidates / decision policy) plus any
already-parsed source-input candidate records, and emits a single closed
``quality_safety_focused_table_structure_attempt`` record set saying, per target,
whether a machine-consumable structured source-input record could be created or
which named blocker stopped it.

No-laundering / provenance rules (non-negotiable):
  * A source-input record is **created + machine-consumable** ONLY when its origin
    is ``parsed_from_extraction_output``, its table structure is
    ``structured_rows``, and it carries a supported recompute method matching the
    target family with a structured ``inputs`` dict.
  * Hand-authored target maps, fixture-derived values, and extracted answer
    strings are **rejected** — counted, never turned into a created record.
  * ``ocr_prose_only`` is never machine-consumable.

Purity & safety: stdlib only plus the pure ``SUPPORTED_METHODS`` set from the
recompute verifier (reuse, not a parallel engine). No FastAPI / frontend /
provider / model / cloud / OCR / render / job-runtime imports; reads no source
documents and no ``clean.md``; writes no artifacts itself; never raises; emits only
closed tokens, ints, bools, and ``None`` — no guide / source / OCR / table text,
snippets, copied formulas, raw input values, paths, filenames, hashes, or byte
counts can survive into the output.
"""
from __future__ import annotations

from typing import Any

from pipeline.quality_safety_recompute_verifier import SUPPORTED_METHODS

VERSION = 1
KIND = "quality_safety_focused_table_structure_attempt"

# The two — and only two — Ensemble targets this focused attempt addresses, each
# mapped to its supported recompute-method family. Not a registry; a fixed pair.
FOCUSED_TARGETS: tuple[str, ...] = ("proximity_4_3", "weighted_weight_impute")
_TARGET_FAMILY: dict[str, str] = {
    "proximity_4_3": "proximity",
    "weighted_weight_impute": "weighted_average",
}

SOURCE_LABEL = "ensemble"

# ── Closed vocabularies (this module owns what it emits) ─────────────────────
TARGET_FAMILIES = frozenset({"proximity", "weighted_average", "unknown"})

REGION_SOURCES = frozenset(
    {
        "existing_table_stack",
        "existing_visual_manifest",
        "existing_ocr_metadata",
        "local_ocr",
        "fitz_signal",
        "unknown",
    }
)

TABLE_STRUCTURE_STATUSES = frozenset(
    {"structured_rows", "partial_structure", "ocr_prose_only", "not_found", "not_run"}
)

SOURCE_INPUT_RECORD_STATUSES = frozenset({"created", "partial", "not_created"})

SOURCE_INPUT_ORIGINS = frozenset(
    {
        "parsed_from_extraction_output",
        "hand_authored_target_map",
        "fixture_derived",
        "answer_string_derived",
        "none",
        "unknown",
    }
)

# Origins that are NEVER allowed to become a created/machine-consumable record.
_REJECTED_ORIGINS = frozenset(
    {"hand_authored_target_map", "fixture_derived", "answer_string_derived"}
)

BLOCKED_BY_TOKENS = frozenset(
    {
        "none",
        "ocr_prose_only",
        "table_structure_missing",
        "target_region_missing",
        "ambiguous_rows",
        "unsupported_target_family",
        "source_artifact_unavailable",
        "existing_stack_unwired",
        "unknown",
    }
)

WARNING_ORDER = (
    "no_parsed_source_input",
    "ocr_prose_only_not_consumable",
    "hand_authored_target_map_rejected",
    "fixture_derived_rejected",
    "answer_string_derived_rejected",
    "unsupported_target_family",
    "ambiguous_rows",
    "existing_stack_reconstructs_no_rows",
    "source_artifact_unavailable",
    "malformed_candidate_degraded",
)

_STATUS_COMPLETED = "completed"
_STATUS_BLOCKED = "blocked"


# ── Public API ───────────────────────────────────────────────────────────────


def build_focused_table_structure_attempt(
    *,
    region_signals_by_target: Any = None,
    source_input_candidates_by_target: Any = None,
) -> dict[str, Any]:
    """Build the closed focused table-structure attempt record set.

    Both arguments are OPTIONAL closed maps keyed by the two focused target ids:

      * ``region_signals_by_target`` — ``{target_id: {"region_identified": bool,
        "region_source": <REGION_SOURCES token>}}`` describing what the existing
        local table/visual stack could already say about each target's region.
      * ``source_input_candidates_by_target`` — ``{target_id: {"origin": <origin>,
        "table_structure_status": <status>, "method": <recompute method>,
        "inputs": <dict>}}`` describing any already-parsed source-input candidate.

    When called with no arguments (the real current state per Slice 175A) every
    target degrades honestly to ``not_created`` / ``table_structure_missing`` and
    the attempt ``status`` is ``blocked``. Pure, total, offline; never raises.
    """
    try:
        return _build(region_signals_by_target, source_input_candidates_by_target)
    except Exception:
        return _blocked_envelope(["malformed_candidate_degraded"])


def _build(region_map: Any, candidate_map: Any) -> dict[str, Any]:
    region_lookup = _coerce_map(region_map)
    candidate_lookup = _coerce_map(candidate_map)

    records: list[dict[str, Any]] = []
    for target_id in FOCUSED_TARGETS:
        records.append(
            _target_record(
                target_id,
                region_lookup.get(target_id),
                candidate_lookup.get(target_id),
            )
        )

    any_structured = any(
        r["source_input_record_status"] == "created"
        and r["machine_consumable_for_recompute"] is True
        for r in records
    )
    status = _STATUS_COMPLETED if any_structured else _STATUS_BLOCKED
    return _envelope(status, records)


# ── Per-target evaluation ────────────────────────────────────────────────────


def _target_record(
    target_id: str, region_signal: Any, candidate: Any
) -> dict[str, Any]:
    family = _TARGET_FAMILY.get(target_id, "unknown")
    region_identified, region_source = _resolve_region(region_signal)
    warnings: list[str] = []

    table_structure_status = "not_run"
    source_input_record_status = "not_created"
    source_input_origin = "none"
    machine_consumable = False
    blocked_by = "table_structure_missing"

    if not isinstance(candidate, dict):
        # No parsed candidate at all → the existing stack gave us no structured
        # rows for this target (Slice 175A's real current state).
        table_structure_status = "not_found"
        blocked_by = "table_structure_missing"
        warnings.append("no_parsed_source_input")
        warnings.append("existing_stack_reconstructs_no_rows")
        return _record(
            target_id, family, region_identified, region_source,
            table_structure_status, source_input_record_status, source_input_origin,
            machine_consumable, blocked_by, warnings,
        )

    origin = _token(candidate.get("origin"), SOURCE_INPUT_ORIGINS, "unknown")
    table_structure_status = _token(
        candidate.get("table_structure_status"), TABLE_STRUCTURE_STATUSES, "not_found"
    )
    method = candidate.get("method")
    inputs = candidate.get("inputs")
    source_input_origin = origin

    # Rejected origins can never become a created record — count + name them.
    if origin in _REJECTED_ORIGINS:
        warnings.append(f"{origin}_rejected")
        blocked_by = "table_structure_missing" if origin == "fixture_derived" else "table_structure_missing"
        # Keep the honest blocker generic; the origin warning carries the reason.
        return _record(
            target_id, family, region_identified, region_source,
            table_structure_status, "not_created", source_input_origin,
            False, "table_structure_missing", warnings,
        )

    # OCR prose is never machine-consumable, regardless of origin.
    if table_structure_status == "ocr_prose_only":
        warnings.append("ocr_prose_only_not_consumable")
        return _record(
            target_id, family, region_identified, region_source,
            "ocr_prose_only", "not_created", source_input_origin,
            False, "ocr_prose_only", warnings,
        )

    # The only path to a created, machine-consumable record.
    if (
        origin == "parsed_from_extraction_output"
        and table_structure_status == "structured_rows"
        and isinstance(method, str)
        and isinstance(inputs, dict)
        and inputs
    ):
        if method not in SUPPORTED_METHODS or (family != "unknown" and method != family):
            warnings.append("unsupported_target_family")
            return _record(
                target_id, family, region_identified, region_source,
                table_structure_status, "not_created", source_input_origin,
                False, "unsupported_target_family", warnings,
            )
        return _record(
            target_id, family, region_identified, region_source,
            "structured_rows", "created", "parsed_from_extraction_output",
            True, "none", warnings,
        )

    # Parsed but not structured enough (region/partial only) → honest blocker.
    if origin == "parsed_from_extraction_output":
        warnings.append("existing_stack_reconstructs_no_rows")
        bucket = "table_structure_missing"
        if table_structure_status == "partial_structure":
            bucket = "ambiguous_rows"
            warnings.append("ambiguous_rows")
        return _record(
            target_id, family, region_identified, region_source,
            table_structure_status, "not_created", source_input_origin,
            False, bucket, warnings,
        )

    warnings.append("no_parsed_source_input")
    return _record(
        target_id, family, region_identified, region_source,
        table_structure_status, "not_created", source_input_origin,
        False, "table_structure_missing", warnings,
    )


def _resolve_region(region_signal: Any) -> tuple[bool, str]:
    if not isinstance(region_signal, dict):
        return False, "unknown"
    identified = region_signal.get("region_identified") is True
    source = _token(region_signal.get("region_source"), REGION_SOURCES, "unknown")
    return identified, source


# ── Assembly ─────────────────────────────────────────────────────────────────


def _record(
    target_id: str,
    family: str,
    region_identified: bool,
    region_source: str,
    table_structure_status: str,
    source_input_record_status: str,
    source_input_origin: str,
    machine_consumable: bool,
    blocked_by: str,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "source_label": SOURCE_LABEL,
        "target_id": target_id,
        "target_family": family if family in TARGET_FAMILIES else "unknown",
        "region_identified": bool(region_identified),
        "region_source": region_source if region_source in REGION_SOURCES else "unknown",
        "table_structure_status": table_structure_status
        if table_structure_status in TABLE_STRUCTURE_STATUSES
        else "not_found",
        "source_input_record_status": source_input_record_status
        if source_input_record_status in SOURCE_INPUT_RECORD_STATUSES
        else "not_created",
        "source_input_origin": source_input_origin
        if source_input_origin in SOURCE_INPUT_ORIGINS
        else "unknown",
        "machine_consumable_for_recompute": bool(machine_consumable),
        "blocked_by": blocked_by if blocked_by in BLOCKED_BY_TOKENS else "unknown",
        "warnings": _ordered_warnings(warnings),
    }


def _envelope(status: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": KIND,
        "status": status if status in {_STATUS_COMPLETED, _STATUS_BLOCKED} else _STATUS_BLOCKED,
        "source_labels": [SOURCE_LABEL],
        "targets_considered": len(FOCUSED_TARGETS),
        "records": records,
        "summary": _summarize(records),
    }


def _blocked_envelope(extra_warnings: list[str]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for target_id in FOCUSED_TARGETS:
        records.append(
            _record(
                target_id,
                _TARGET_FAMILY.get(target_id, "unknown"),
                False,
                "unknown",
                "not_run",
                "not_created",
                "none",
                False,
                "table_structure_missing",
                list(extra_warnings),
            )
        )
    return _envelope(_STATUS_BLOCKED, records)


def _summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "structured_rows_count": 0,
        "partial_structure_count": 0,
        "ocr_prose_only_count": 0,
        "not_found_count": 0,
        "source_input_records_created_count": 0,
        "machine_consumable_count": 0,
        "not_machine_consumable_count": 0,
        "hand_authored_target_map_count": 0,
        "fixture_derived_count": 0,
        "answer_string_derived_count": 0,
    }
    for record in records:
        if not isinstance(record, dict):
            continue
        status = record.get("table_structure_status")
        if status == "structured_rows":
            summary["structured_rows_count"] += 1
        elif status == "partial_structure":
            summary["partial_structure_count"] += 1
        elif status == "ocr_prose_only":
            summary["ocr_prose_only_count"] += 1
        elif status == "not_found":
            summary["not_found_count"] += 1
        if record.get("source_input_record_status") == "created":
            summary["source_input_records_created_count"] += 1
        if record.get("machine_consumable_for_recompute") is True:
            summary["machine_consumable_count"] += 1
        else:
            summary["not_machine_consumable_count"] += 1
        origin = record.get("source_input_origin")
        if origin == "hand_authored_target_map":
            summary["hand_authored_target_map_count"] += 1
        elif origin == "fixture_derived":
            summary["fixture_derived_count"] += 1
        elif origin == "answer_string_derived":
            summary["answer_string_derived_count"] += 1
    return summary


# ── Helpers ──────────────────────────────────────────────────────────────────


def _coerce_map(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key, entry in value.items():
        if isinstance(key, str) and key in _TARGET_FAMILY:
            out[key] = entry
    return out


def _token(value: Any, allowed: Any, default: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return default


def _ordered_warnings(warnings: Any) -> list[str]:
    seen = set(warnings) if isinstance(warnings, (set, list, tuple)) else set()
    return [token for token in WARNING_ORDER if token in seen]
