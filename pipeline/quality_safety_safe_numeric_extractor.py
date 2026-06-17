"""Quality Safety safe numeric extractor v1 (Slice 129).

Pure, deterministic, **unwired** safe numeric extractor. It converts
*caller-supplied sanitized numeric candidates* into records compatible with the
optional read-only sidecar ``quality_safety_numeric_extraction_records.json`` and
the Slice 124/125 contract — without ever reading documents, parsing text,
scanning job folders, writing artifacts, or touching the production job path.

Design boundary (``docs/QUALITY_SAFETY_SAFE_NUMERIC_EXTRACTOR_DESIGN.md``):
  * **Allowed input:** ``caller_supplied_sanitized_numeric_candidates`` only —
    already-sanitized, in-memory structured numeric candidate dicts handed in by a
    caller (and synthetic fixtures of the same shape).
  * **Forbidden input:** source documents, PDFs/images, DOCX, ``clean.md`` as a
    numeric source, OCR/page text, table cells, captions, guide text, provider
    payloads, raw runtime/artifact JSON, filenames, basenames, paths, URLs. The
    extractor never opens files, never scans directories, never reads ``clean.md``,
    never parses OCR/table/source text, and never calls a provider/model/cloud.
  * **Output:** the Slice 124/125 record shape (sanitized tokens only), wrapped in
    a ``quality_safety_numeric_extraction_records`` payload. The Slice 125 mapper
    (``normalize_quality_safety_numeric_extraction_record``) remains the **final
    sanitizer**: every record this module emits is produced by that mapper, so raw
    text, formulas, paths, URLs, filenames, provider payloads, OCR/table/caption
    text, and evidence quotes can never be echoed.

The module is intentionally offline and total:
  * stdlib + the Slice 125 mapper only (a pure quality-safety module);
  * no FastAPI / frontend / provider / model / cloud / OCR / table / render / job
    runtime / filesystem imports;
  * reads only caller-supplied in-memory dicts/lists;
  * never raises on malformed input and never mutates the caller's input;
  * every public function returns a JSON-serializable dict with closed-vocabulary
    tokens only.

A numeric fact is ``value`` + structured numeric ``computation.inputs`` — never a
copied formula string or prose snippet. Structural coverage is *not* numeric
evidence and is never converted into a numeric fact here.

This is **not** production wiring: no module imports this extractor, no artifact
is written, and the production job artifact path is unchanged.
"""
from __future__ import annotations

from typing import Any

from pipeline.quality_safety_numeric_extraction_mapper import (
    ALLOWED_RECORD_FIELDS,
    FORBIDDEN_RECORD_FIELDS,
    RECORD_WARNING_ORDER,
    normalize_quality_safety_numeric_extraction_record,
)

VERSION = 1
KIND = "quality_safety_numeric_extraction_records"

# Closed source-quality vocabulary for the extractor payload. ``synthetic`` and
# ``sanitized_candidates`` are the real caller paths; ``unknown`` is the safe
# fallback for malformed top-level input.
SOURCE_QUALITIES = frozenset({"synthetic", "sanitized_candidates", "unknown"})
PAYLOAD_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})

# The extractor's forbidden-field set is the mapper's closed list widened by two
# tokens the extractor refuses to even *carry* toward the mapper. None of these
# are ever copied into a record; their presence on a candidate is flagged.
EXTRACTOR_FORBIDDEN_FIELDS = frozenset(FORBIDDEN_RECORD_FIELDS | {"page_text", "raw_artifact_json"})

# Candidate field aliases the extractor understands beyond the contract shape:
# a candidate may carry a flat ``method`` / ``inputs`` pair instead of a nested
# ``computation`` block. Everything else outside the contract is ignored.
_COMPUTATION_ALIAS_KEYS = frozenset({"method", "inputs"})

_DEFAULT_MAX_ITEMS = 200

PAYLOAD_WARNING_ORDER = (
    "component_missing",
    "empty_numeric_extraction",
    "malformed_numeric_extraction_input",
    "invalid_numeric_record_dropped",
    "max_items_reached",
)
_EMPTY_REASONS = frozenset(
    {"component_missing", "empty_numeric_extraction", "malformed_numeric_extraction_input"}
)


# ── Public API ──────────────────────────────────────────────────────────────


def build_empty_safe_numeric_extraction_records(reason: str = "component_missing") -> dict[str, Any]:
    """Return an empty, no-record safe numeric extraction payload.

    Used when no caller candidates are supplied (the common reality today).
    ``reason`` is constrained to a closed token set.
    """
    token = reason if isinstance(reason, str) and reason in _EMPTY_REASONS else "component_missing"
    status = "failed" if token == "malformed_numeric_extraction_input" else "skipped"
    quality = "unknown" if token == "malformed_numeric_extraction_input" else "sanitized_candidates"
    return _payload(
        status=status,
        source_quality=quality,
        records=[],
        candidate_count=0,
        warnings={token},
    )


def normalize_safe_numeric_candidate(candidate: Any, *, index: int = 0) -> dict[str, Any] | None:
    """Normalize one caller-supplied sanitized numeric candidate into a record.

    Resolves the flat ``method``/``inputs`` alias into a ``computation`` block,
    injects a stable synthetic ``id`` (``qs_safe_num_NNNN``) when the candidate has
    none, strips/flags forbidden fields, then defers all field sanitization to the
    Slice 125 mapper as the final sanitizer. Returns a closed-vocabulary record, or
    ``None`` when the input cannot form a record (non-mapping). Never raises; never
    mutates the caller's input.
    """
    try:
        return _normalize_candidate(candidate, index=index)
    except Exception:
        return None


def extract_quality_safety_numeric_records_from_candidates(
    candidates: Any,
    *,
    max_items: int | None = None,
    source_quality: str = "sanitized_candidates",
) -> dict[str, Any]:
    """Convert a list of caller-supplied sanitized numeric candidates into a payload.

    Returns a ``quality_safety_numeric_extraction_records`` payload whose
    ``records`` are sidecar-compatible (consumable by the Slice 126 artifact path
    and the Slice 125 mapper). Never raises. Malformed top-level input degrades to
    a closed status/warning. The caller's input is never mutated.
    """
    try:
        return _extract(candidates, max_items=max_items, source_quality=source_quality)
    except Exception:
        return _payload(
            status="failed",
            source_quality="unknown",
            records=[],
            candidate_count=0,
            warnings={"malformed_numeric_extraction_input"},
        )


def map_safe_numeric_candidates_to_sidecar_payload(
    candidates: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Return the sidecar-writable payload for caller-supplied candidates.

    The returned dict carries the records under the closed ``records`` key, which
    the Slice 126 artifact reader's ``_coerce_numeric_records`` accepts directly
    (alongside a bare records list). This module never writes the sidecar; it only
    produces the payload shape a future safe writer could persist.
    """
    return extract_quality_safety_numeric_records_from_candidates(candidates, max_items=max_items)


# ── Candidate normalization ──────────────────────────────────────────────────


def _normalize_candidate(candidate: Any, *, index: int) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None

    ordinal = index + 1 if isinstance(index, int) and not isinstance(index, bool) and index >= 0 else 1
    forbidden_present = any(key in candidate for key in EXTRACTOR_FORBIDDEN_FIELDS)

    # Build a contract-shaped candidate carrying only recognized fields. Forbidden
    # fields are never copied toward the mapper; the alias pair is folded into
    # ``computation``; a synthetic id is injected when the candidate has none.
    work: dict[str, Any] = {}
    for key in ALLOWED_RECORD_FIELDS:
        if key in ("computation", "id", "warnings"):
            continue
        if key in candidate:
            work[key] = candidate[key]

    work["id"] = _candidate_id(candidate.get("id"), ordinal)

    computation = _resolve_computation(candidate)
    if computation is not None:
        work["computation"] = computation

    record = normalize_quality_safety_numeric_extraction_record(work, index=index)
    if record is None:
        return None

    # Surface the broader forbidden-field signal even for tokens the mapper does
    # not itself enumerate; the mapper has already guaranteed no forbidden content
    # is in the record body, so this only adds the closed warning token.
    if forbidden_present and "forbidden_field_stripped" not in record.get("warnings", []):
        merged = set(record.get("warnings", [])) | {"forbidden_field_stripped"}
        record["warnings"] = [token for token in RECORD_WARNING_ORDER if token in merged]
    return record


def _candidate_id(value: Any, ordinal: int) -> str:
    """Return the candidate's id when usable, else a stable synthetic safe id.

    A synthetic ``qs_safe_num_NNNN`` id is generated only when the candidate has no
    usable string id (missing / empty / non-string). A present string id is passed
    through to the mapper, which sanitizes it (and falls back on its own if unsafe).
    """
    if isinstance(value, str) and value.strip():
        return value
    return f"qs_safe_num_{ordinal:04d}"


def _resolve_computation(candidate: dict[str, Any]) -> Any:
    """Fold the flat ``method``/``inputs`` alias into a ``computation`` block.

    Precedence: an explicit ``computation`` field wins (passed through unchanged so
    the mapper validates it). Otherwise a flat ``method`` string promotes to
    ``{"method": ..., "inputs": ...}``. Returns ``None`` when the candidate carries
    no computation signal at all (a bare numeric observation).
    """
    if "computation" in candidate:
        return candidate["computation"]
    method = candidate.get("method")
    if isinstance(method, str) and any(key in candidate for key in _COMPUTATION_ALIAS_KEYS):
        return {"method": method, "inputs": candidate.get("inputs")}
    return None


# ── Payload assembly ──────────────────────────────────────────────────────────


def _extract(candidates: Any, *, max_items: Any, source_quality: Any) -> dict[str, Any]:
    quality = (
        source_quality
        if isinstance(source_quality, str) and source_quality in SOURCE_QUALITIES
        else "sanitized_candidates"
    )

    if candidates is None:
        return build_empty_safe_numeric_extraction_records("component_missing")
    if not isinstance(candidates, list):
        return _payload(
            status="failed",
            source_quality="unknown",
            records=[],
            candidate_count=0,
            warnings={"malformed_numeric_extraction_input"},
        )
    if not candidates:
        return _payload(
            status="skipped",
            source_quality=quality,
            records=[],
            candidate_count=0,
            warnings={"empty_numeric_extraction"},
        )

    cap = _cap(max_items)
    candidate_count = len(candidates)
    truncated = candidate_count > cap

    records: list[dict[str, Any]] = []
    dropped = False
    for index, candidate in enumerate(candidates[:cap]):
        record = normalize_safe_numeric_candidate(candidate, index=index)
        if record is None:
            dropped = True
            continue
        records.append(record)

    warnings: set[str] = set()
    if truncated:
        warnings.add("max_items_reached")
    if dropped:
        warnings.add("invalid_numeric_record_dropped")

    status = _status(records=records, truncated=truncated, warnings=warnings)
    return _payload(
        status=status,
        source_quality=quality,
        records=records,
        candidate_count=candidate_count,
        warnings=warnings,
    )


def _status(*, records: list[dict[str, Any]], truncated: bool, warnings: set[str]) -> str:
    if truncated:
        return "partial"
    if not records:
        return "warning" if "invalid_numeric_record_dropped" in warnings else "skipped"
    record_warning = any(record.get("warnings") for record in records)
    if record_warning or "invalid_numeric_record_dropped" in warnings:
        return "warning"
    return "ok"


def _payload(
    *,
    status: str,
    source_quality: str,
    records: list[dict[str, Any]],
    candidate_count: int,
    warnings: set[str],
) -> dict[str, Any]:
    record_count = len(records)
    supported_method_count = sum(1 for record in records if record.get("computation"))
    unsupported_method_count = sum(
        1 for record in records if "unsupported_method" in record.get("warnings", [])
    )
    safe_candidate_count = max(0, candidate_count)
    dropped_candidate_count = max(0, safe_candidate_count - record_count)
    return {
        "version": VERSION,
        "kind": KIND,
        "status": status if status in PAYLOAD_STATUSES else "warning",
        "source_quality": source_quality if source_quality in SOURCE_QUALITIES else "unknown",
        "summary": {
            "candidate_count": safe_candidate_count,
            "record_count": max(0, record_count),
            "supported_method_count": max(0, supported_method_count),
            "unsupported_method_count": max(0, unsupported_method_count),
            "dropped_candidate_count": dropped_candidate_count,
        },
        "records": records,
        "warnings": [token for token in PAYLOAD_WARNING_ORDER if token in warnings],
    }


def _cap(max_items: Any) -> int:
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        return max(0, min(max_items, _DEFAULT_MAX_ITEMS))
    return _DEFAULT_MAX_ITEMS
