"""Quality Safety numeric extraction record mapper v1 (Slice 125).

Pure, deterministic, **unwired** mapper from caller-supplied *sanitized numeric
extraction records* (the Slice 124 contract shape, see
``docs/QUALITY_SAFETY_NUMERIC_EXTRACTION_CONTRACT.md``) into:

  1. a normalized ``quality_safety_numeric_extraction_bundle`` (closed-vocabulary,
     numeric-only), and
  2. an existing ``quality_safety_extraction_bundle`` shape that the Slice 117
     fact-sheet producer (and therefore the Slice 111 recompute verifier) already
     accept.

This closes the schema/mapper gap that Slice 123 found and Slice 124 designed,
while staying pure/unwired: it is **not** wired into production jobs in this
slice.

The module is intentionally offline and total:
  * stdlib only, plus the closed ``SUPPORTED_METHODS`` set from the recompute
    verifier (a pure quality-safety module);
  * no FastAPI / frontend / provider / model / cloud / OCR / table / render / job
    runtime imports;
  * reads only caller-supplied in-memory dicts/lists — scans no directories,
    reads no source documents, no ``clean.md``, writes no artifacts, and calls no
    providers/models/cloud;
  * never raises on malformed input and never mutates the caller's input;
  * every public function returns a JSON-serializable dict with closed-vocabulary
    tokens only; raw text, formulas, paths, URLs, filenames, basenames, provider
    payloads, OCR/table/caption text, evidence quotes, and raw exception text are
    never echoed.

A numeric fact is ``value`` + structured numeric ``computation.inputs`` — never a
copied formula string or prose snippet. Structural coverage is *not* numeric
evidence and is never converted into a numeric fact here.
"""
from __future__ import annotations

import math
import re
from typing import Any

from pipeline.quality_safety_recompute_verifier import SUPPORTED_METHODS

VERSION = 1
BUNDLE_KIND = "quality_safety_numeric_extraction_bundle"

# Closed source-quality vocabulary for the numeric bundle.
SOURCE_QUALITIES = frozenset({"synthetic", "runtime_structural", "unknown"})

# The only fields a caller-supplied record may carry through. Everything else
# (notably the forbidden raw-content fields) is dropped before anything is built.
ALLOWED_RECORD_FIELDS = frozenset(
    {
        "id",
        "concept_id",
        "label",
        "fact_type",
        "value",
        "unit",
        "provenance",
        "confidence",
        "source_ref",
        "page_ref",
        "computation",
        "tolerance",
        "warnings",
    }
)

# Closed forbidden-field list (kept in sync with the Slice 124 contract). Any of
# these on a caller record is stripped and flagged; raw content never survives.
FORBIDDEN_RECORD_FIELDS = frozenset(
    {
        "raw_text",
        "source_text",
        "guide_text",
        "ocr_text",
        "table_cells",
        "captions",
        "formulas_as_text",
        "evidence_quotes",
        "filenames",
        "basenames",
        "paths",
        "urls",
        "provider_payloads",
        "runtime_traces",
        "raw_exceptions",
    }
)

PROVENANCE_VALUES = frozenset({"extracted_high", "computed", "unverified"})
CONFIDENCE_VALUES = frozenset({"high", "medium", "low", "unsupported"})

# The only string *values* permitted inside computation.inputs: the closed
# forward-pass activation tokens. Every other string value is stripped.
_ALLOWED_INPUT_STRING_VALUES = frozenset({"linear", "relu", "sigmoid"})

# Tolerance cap convention shared with the recompute verifier / producer.
_MAX_TOLERANCE = 1.0

_DEFAULT_MAX_ITEMS = 200
_MAX_INPUT_DEPTH = 4

RECORD_WARNING_ORDER = (
    "forbidden_field_stripped",
    "invalid_id",
    "invalid_concept_id",
    "invalid_label",
    "invalid_unit",
    "invalid_provenance",
    "invalid_confidence",
    "invalid_source_ref",
    "invalid_page_ref",
    "invalid_numeric_value",
    "invalid_tolerance",
    "unsupported_method",
    "malformed_computation",
    "unsafe_string_sanitized",
)
_RECORD_WARNINGS = frozenset(RECORD_WARNING_ORDER)

BUNDLE_WARNING_ORDER = (
    "component_missing",
    "empty_numeric_extraction",
    "malformed_numeric_extraction_input",
    "invalid_numeric_record_dropped",
    "max_items_reached",
)
_EMPTY_REASONS = frozenset(
    {"component_missing", "empty_numeric_extraction", "malformed_numeric_extraction_input"}
)

_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_SAFE_UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_%./-]{0,31}$")
_SAFE_SOURCE_REF_RE = re.compile(r"^(?:source_page|page|slide|source_ref)_[0-9]{1,4}$")
_SAFE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_UNSAFE_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|/var/|\\\\|[A-Za-z]:\\|\.\./|/\.\.|"
    r"authorization|bearer|api[_-]?key|token|secret|data:|base64|provider payload|"
    r"ocr|caption|table text|uploaded[_ -]?quality|quality[_ -]?spec|evidence quote|"
    r"source text|raw text|guide snippet|source snippet|private|\.pdf|\.docx|\.zip|"
    r"\.png|\.jpg|\.jpeg|\.webp|\.socket|\.sock)",
    re.IGNORECASE,
)
_BASE64ISH_RE = re.compile(r"^[A-Za-z0-9+/]{80,}={0,2}$")


# ── Public API ──────────────────────────────────────────────────────────────


def build_empty_quality_safety_numeric_extraction_bundle(
    reason: str = "component_missing",
) -> dict[str, Any]:
    """Return an empty, no-record numeric extraction bundle.

    Used when no numeric extraction component supplied records (the common
    production reality today). ``reason`` is constrained to a closed token set.
    """
    token = reason if isinstance(reason, str) and reason in _EMPTY_REASONS else "component_missing"
    status = "failed" if token == "malformed_numeric_extraction_input" else "skipped"
    return _bundle(
        status=status,
        source_quality="unknown",
        numeric_records=[],
        warnings={token},
    )


def normalize_quality_safety_numeric_extraction_record(
    record: Any, *, index: int = 0
) -> dict[str, Any] | None:
    """Normalize one caller-supplied numeric extraction record.

    Returns a closed-vocabulary, numeric-only record dict, or ``None`` when the
    input cannot form a record (non-mapping). Never raises; never mutates input.
    Forbidden fields are stripped and flagged; raw content is never echoed.
    """
    try:
        return _normalize_record(record, index=index)
    except Exception:
        return None


def build_quality_safety_numeric_extraction_bundle(
    records: Any,
    *,
    max_items: int | None = None,
    source_quality: str = "synthetic",
) -> dict[str, Any]:
    """Normalize a list of caller-supplied numeric extraction records into a bundle.

    Never raises. Malformed top-level input degrades to a closed status/warning.
    The caller's input is never mutated.
    """
    try:
        return _build_bundle(records, max_items=max_items, source_quality=source_quality)
    except Exception:
        return _bundle(
            status="failed",
            source_quality="unknown",
            numeric_records=[],
            warnings={"malformed_numeric_extraction_input"},
        )


def map_numeric_extraction_bundle_to_fact_sheet_input(
    bundle: Any, *, lecture_id: str | None = None
) -> dict[str, Any]:
    """Map a normalized numeric extraction bundle to a producer extraction bundle.

    Produces the existing ``quality_safety_extraction_bundle`` shape consumed by
    ``run_quality_safety_fact_sheet_producer`` (and hence the recompute verifier).
    Records carrying a supported ``computation`` become ``computation_records``;
    bare numeric facts become ``numeric_observations``. Never raises; never
    mutates input.
    """
    try:
        return _map_to_fact_sheet_input(bundle, lecture_id=lecture_id)
    except Exception:
        return {
            "version": VERSION,
            "kind": "quality_safety_extraction_bundle",
            "lecture_id": "synthetic_fixture",
            "source_quality": "unknown",
            "concepts": [],
        }


# ── Record normalization ────────────────────────────────────────────────────


def _normalize_record(record: Any, *, index: int) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    warnings: set[str] = set()

    # Hard contract boundary: never copy any forbidden field; flag if present.
    if any(key in record for key in FORBIDDEN_RECORD_FIELDS):
        warnings.add("forbidden_field_stripped")
    safe = {key: value for key, value in record.items() if key in ALLOWED_RECORD_FIELDS}

    ordinal = index + 1 if isinstance(index, int) and not isinstance(index, bool) and index >= 0 else 1

    record_id = _safe_id(safe.get("id"), f"qs_num_{ordinal:04d}", warnings, "invalid_id")
    concept_id = _safe_optional_id(safe.get("concept_id"), warnings, "invalid_concept_id")
    label = _safe_label(safe.get("label"), f"qs_num_label_{ordinal:04d}", warnings)
    unit = _safe_unit(safe.get("unit"), warnings)
    provenance = _safe_enum(safe.get("provenance"), PROVENANCE_VALUES, "unverified", warnings, "invalid_provenance")
    confidence = _safe_enum(safe.get("confidence"), CONFIDENCE_VALUES, "medium", warnings, "invalid_confidence")
    source_ref = _safe_source_ref(safe.get("source_ref"), warnings, "invalid_source_ref")
    page_ref = _safe_source_ref(safe.get("page_ref"), warnings, "invalid_page_ref")

    value = _finite_number(safe.get("value"))
    if value is None and safe.get("value") is not None:
        warnings.add("invalid_numeric_value")

    tolerance = _safe_tolerance(safe.get("tolerance"), warnings)
    computation = _safe_computation(safe.get("computation"), warnings)

    return {
        "id": record_id,
        "concept_id": concept_id,
        "label": label,
        "fact_type": "numeric",
        "value": value,
        "unit": unit,
        "provenance": provenance,
        "confidence": confidence,
        "source_ref": source_ref,
        "page_ref": page_ref,
        "computation": computation,
        "tolerance": tolerance,
        "warnings": _ordered(warnings, RECORD_WARNING_ORDER),
    }


def _safe_computation(value: Any, warnings: set[str]) -> dict[str, Any] | None:
    """Return a closed ``{method, inputs}`` block, or ``None`` (demoted to bare).

    Only a supported method with fully-clean numeric inputs survives. Unsupported
    methods and malformed/empty inputs are demoted to ``None`` (a bare numeric
    fact) so they remain *unverified* — never falsely recompute-verified.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        warnings.add("malformed_computation")
        return None
    method = value.get("method")
    if not isinstance(method, str) or method.strip().lower() not in SUPPORTED_METHODS:
        warnings.add("unsupported_method")
        return None
    method = method.strip().lower()
    inputs, ok = _sanitize_numeric_inputs(value.get("inputs"), depth=0)
    if not ok or not isinstance(inputs, dict) or not inputs:
        warnings.add("malformed_computation")
        return None
    return {"method": method, "inputs": inputs}


def _sanitize_numeric_inputs(value: Any, *, depth: int) -> tuple[Any, bool]:
    """Recursively keep numeric-only structured inputs; strip everything else.

    Returns ``(clean_value, ok)``. ``ok`` is ``False`` if anything had to be
    stripped (a string value, an unsafe key, an over-deep node), so the caller can
    demote the whole computation rather than recompute partially-stripped inputs.
    """
    if depth > _MAX_INPUT_DEPTH:
        return None, False
    # Booleans must never be treated as numbers.
    if isinstance(value, bool):
        return None, False
    number = _finite_number(value)
    if number is not None:
        return number, True
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _ALLOWED_INPUT_STRING_VALUES:
            return token, True
        return None, False
    if isinstance(value, list):
        out: list[Any] = []
        ok = True
        for item in value:
            clean, child_ok = _sanitize_numeric_inputs(item, depth=depth + 1)
            if not child_ok:
                ok = False
                continue
            out.append(clean)
        return out, ok
    if isinstance(value, dict):
        out_map: dict[str, Any] = {}
        ok = True
        for key, item in value.items():
            key_text = key.strip().lower() if isinstance(key, str) else ""
            key_text = re.sub(r"[^a-z0-9._-]+", "_", key_text).strip("._-")
            if not key_text or _unsafe_string(key_text) or not _SAFE_KEY_RE.fullmatch(key_text):
                ok = False
                continue
            clean, child_ok = _sanitize_numeric_inputs(item, depth=depth + 1)
            if not child_ok:
                ok = False
                continue
            out_map[key_text] = clean
        return out_map, ok
    return None, False


# ── Bundle assembly ─────────────────────────────────────────────────────────


def _build_bundle(records: Any, *, max_items: Any, source_quality: Any) -> dict[str, Any]:
    quality = source_quality if isinstance(source_quality, str) and source_quality in SOURCE_QUALITIES else "unknown"

    if records is None:
        return build_empty_quality_safety_numeric_extraction_bundle("component_missing")
    if not isinstance(records, list):
        return _bundle(
            status="failed",
            source_quality="unknown",
            numeric_records=[],
            warnings={"malformed_numeric_extraction_input"},
        )
    if not records:
        return _bundle(
            status="skipped",
            source_quality=quality,
            numeric_records=[],
            warnings={"empty_numeric_extraction"},
        )

    cap = _cap(max_items)
    warnings: set[str] = set()
    truncated = len(records) > cap
    if truncated:
        warnings.add("max_items_reached")

    numeric_records: list[dict[str, Any]] = []
    dropped = False
    for index, raw in enumerate(records[:cap]):
        normalized = normalize_quality_safety_numeric_extraction_record(raw, index=index)
        if normalized is None:
            dropped = True
            continue
        numeric_records.append(normalized)
    if dropped:
        warnings.add("invalid_numeric_record_dropped")

    status = _bundle_status(numeric_records=numeric_records, truncated=truncated, warnings=warnings)
    return _bundle(
        status=status,
        source_quality=quality,
        numeric_records=numeric_records,
        warnings=warnings,
    )


def _bundle_status(*, numeric_records: list[dict[str, Any]], truncated: bool, warnings: set[str]) -> str:
    if truncated:
        return "partial"
    if not numeric_records:
        # Non-empty input whose records all dropped -> warning, not skipped.
        return "warning" if "invalid_numeric_record_dropped" in warnings else "skipped"
    record_warning = any(record.get("warnings") for record in numeric_records)
    if record_warning or "invalid_numeric_record_dropped" in warnings:
        return "warning"
    return "ok"


def _bundle(
    *,
    status: str,
    source_quality: str,
    numeric_records: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    computation_record_count = sum(1 for record in numeric_records if record.get("computation"))
    bare_numeric_observation_count = len(numeric_records) - computation_record_count
    unsupported_method_count = sum(
        1 for record in numeric_records if "unsupported_method" in record.get("warnings", [])
    )
    numeric_fact_count = sum(1 for record in numeric_records if record.get("value") is not None)
    return {
        "version": VERSION,
        "kind": BUNDLE_KIND,
        "status": status if status in {"ok", "warning", "skipped", "partial", "failed"} else "warning",
        "source_quality": source_quality if source_quality in SOURCE_QUALITIES else "unknown",
        "summary": {
            "record_count": max(0, len(numeric_records)),
            "numeric_fact_count": max(0, numeric_fact_count),
            "computation_record_count": max(0, computation_record_count),
            "bare_numeric_observation_count": max(0, bare_numeric_observation_count),
            "supported_method_count": max(0, computation_record_count),
            "unsupported_method_count": max(0, unsupported_method_count),
        },
        "numeric_records": numeric_records,
        "warnings": _ordered(warnings, BUNDLE_WARNING_ORDER),
    }


# ── Mapping to the existing producer extraction-bundle shape ─────────────────


def _map_to_fact_sheet_input(bundle: Any, *, lecture_id: Any) -> dict[str, Any]:
    quality = "unknown"
    records: list[dict[str, Any]] = []
    if isinstance(bundle, dict):
        candidate = bundle.get("source_quality")
        if isinstance(candidate, str) and candidate in SOURCE_QUALITIES:
            quality = candidate
        raw_records = bundle.get("numeric_records")
        if isinstance(raw_records, list):
            records = [record for record in raw_records if isinstance(record, dict)]

    safe_lecture = _safe_id(lecture_id, "synthetic_fixture", set(), "invalid_id")
    # The producer's source-quality vocabulary differs (no "runtime_structural");
    # map our token onto the closest accepted producer value to avoid a spurious
    # producer warning, preserving the synthetic/clean provenance path.
    producer_quality = "synthetic" if quality == "synthetic" else "unknown"

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    order: list[str] = []
    for record in records:
        if record.get("fact_type") != "numeric":
            continue
        concept_id = record.get("concept_id") or "qs_num_concept_default"
        if concept_id not in grouped:
            grouped[concept_id] = {"computation_records": [], "numeric_observations": []}
            order.append(concept_id)
        bucket = grouped[concept_id]
        computation = record.get("computation")
        if isinstance(computation, dict) and computation.get("method") in SUPPORTED_METHODS:
            bucket["computation_records"].append(
                {
                    "id": record.get("id"),
                    "label": record.get("label"),
                    "type": "numeric",
                    "method": computation.get("method"),
                    "inputs": computation.get("inputs"),
                    "claimed_value": record.get("value"),
                    "tolerance": record.get("tolerance"),
                    "source_ref": record.get("source_ref"),
                    "confidence": record.get("confidence"),
                    "verification_status": "unverified",
                }
            )
        else:
            bucket["numeric_observations"].append(
                {
                    "id": record.get("id"),
                    "label": record.get("label"),
                    "value": record.get("value"),
                    "tolerance": record.get("tolerance"),
                    "source_ref": record.get("source_ref"),
                    "confidence": record.get("confidence"),
                }
            )

    concepts = [
        {
            "concept": concept_id,
            "source_ref": _concept_source_ref(grouped[concept_id]),
            "computation_records": grouped[concept_id]["computation_records"],
            "numeric_observations": grouped[concept_id]["numeric_observations"],
        }
        for concept_id in order
    ]
    return {
        "version": VERSION,
        "kind": "quality_safety_extraction_bundle",
        "lecture_id": safe_lecture,
        "source_quality": producer_quality,
        "concepts": concepts,
    }


def _concept_source_ref(bucket: dict[str, list[dict[str, Any]]]) -> str | None:
    for item in bucket["computation_records"] + bucket["numeric_observations"]:
        ref = item.get("source_ref")
        if isinstance(ref, str) and ref:
            return ref
    return None


# ── Safe-field helpers ──────────────────────────────────────────────────────


def _safe_id(value: Any, default: str, warnings: set[str], warning_token: str) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add(warning_token)
        return default
    stripped = value.strip().lower()
    if not stripped or _unsafe_string(stripped):
        warnings.add(warning_token)
        if stripped and _unsafe_string(stripped):
            warnings.add("unsafe_string_sanitized")
        return default
    normalized = re.sub(r"\s+", "_", stripped)
    normalized = re.sub(r"[^a-z0-9._-]+", "_", normalized).strip("._-")
    normalized = re.sub(r"[._-]{2,}", "_", normalized)[:80]
    if not _SAFE_ID_RE.fullmatch(normalized):
        warnings.add(warning_token)
        return default
    return normalized


def _safe_optional_id(value: Any, warnings: set[str], warning_token: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        warnings.add(warning_token)
        return None
    stripped = value.strip().lower()
    if not stripped or _unsafe_string(stripped):
        warnings.add(warning_token)
        if stripped and _unsafe_string(stripped):
            warnings.add("unsafe_string_sanitized")
        return None
    normalized = re.sub(r"\s+", "_", stripped)
    normalized = re.sub(r"[^a-z0-9._-]+", "_", normalized).strip("._-")
    normalized = re.sub(r"[._-]{2,}", "_", normalized)[:80]
    if not _SAFE_ID_RE.fullmatch(normalized):
        warnings.add(warning_token)
        return None
    return normalized


def _safe_label(value: Any, default: str, warnings: set[str]) -> str:
    if not isinstance(value, str):
        return default
    if _unsafe_string(value):
        warnings.add("invalid_label")
        warnings.add("unsafe_string_sanitized")
        return default
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value.strip()).strip("_.:-")
    if not cleaned or not _SAFE_LABEL_RE.fullmatch(cleaned[:80]):
        warnings.add("invalid_label")
        return default
    return cleaned[:80]


def _safe_unit(value: Any, warnings: set[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        warnings.add("invalid_unit")
        return None
    candidate = value.strip()
    if not candidate or _unsafe_string(candidate) or not _SAFE_UNIT_RE.fullmatch(candidate):
        warnings.add("invalid_unit")
        if isinstance(value, str) and _unsafe_string(value):
            warnings.add("unsafe_string_sanitized")
        return None
    return candidate


def _safe_source_ref(value: Any, warnings: set[str], warning_token: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        warnings.add(warning_token)
        return None
    candidate = value.strip().lower()
    if _unsafe_string(candidate) or not _SAFE_SOURCE_REF_RE.fullmatch(candidate):
        warnings.add(warning_token)
        if _unsafe_string(candidate):
            warnings.add("unsafe_string_sanitized")
        return None
    return candidate


def _safe_enum(value: Any, allowed: frozenset[str], default: str, warnings: set[str], warning_token: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        warnings.add(warning_token)
        return default
    candidate = value.strip().lower()
    if candidate not in allowed:
        warnings.add(warning_token)
        return default
    return candidate


def _safe_tolerance(value: Any, warnings: set[str]) -> float | None:
    if value is None:
        return None
    number = _finite_number(value)
    if number is None or not (0.0 < float(number) <= _MAX_TOLERANCE):
        warnings.add("invalid_tolerance")
        return None
    return float(number)


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if isinstance(value, int):
        return int(value)
    return float(value)


def _unsafe_string(value: str) -> bool:
    if not isinstance(value, str):
        return True
    if not value.strip():
        return True
    if "\x00" in value or "\n" in value or "\r" in value or "\t" in value:
        return True
    if _UNSAFE_RE.search(value):
        return True
    if _BASE64ISH_RE.fullmatch(value.strip()):
        return True
    return False


def _cap(max_items: Any) -> int:
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        return max(0, min(max_items, _DEFAULT_MAX_ITEMS))
    return _DEFAULT_MAX_ITEMS


def _ordered(values: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in values]
