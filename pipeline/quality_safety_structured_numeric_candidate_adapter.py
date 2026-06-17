"""Pure adapter for future structured numeric candidate artifacts (Slice 133).

Converts caller-supplied ``quality_safety_structured_numeric_candidates`` dicts
into ``quality_safety_safe_numeric_candidates``-compatible payloads. This module
does not read files, scan job folders, parse source/OCR/table text, write
artifacts, call providers, or wire anything into production. The Slice 129 safe
numeric extractor remains the final sanitizer for downstream use.
"""
from __future__ import annotations

import math
import re
from typing import Any

VERSION = 1
INPUT_KIND = "quality_safety_structured_numeric_candidates"
OUTPUT_KIND = "quality_safety_safe_numeric_candidates"

PAYLOAD_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
SOURCE_QUALITIES = frozenset({"synthetic", "structured_numeric_artifact", "operator_approved", "unknown"})

SUPPORTED_METHODS = frozenset(
    {"weighted_gini", "total_error", "amount_of_say", "softmax", "cross_entropy", "forward_pass"}
)

ALLOWED_CANDIDATE_FIELDS = frozenset(
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
FORBIDDEN_CANDIDATE_FIELDS = frozenset(
    {
        "raw_text",
        "source_text",
        "guide_text",
        "ocr_text",
        "page_text",
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
        "raw_artifact_json",
    }
)

PROVENANCE_VALUES = frozenset({"extracted_high", "computed", "unverified", "operator_approved"})
CONFIDENCE_VALUES = frozenset({"high", "medium", "low", "unsupported"})
_ALLOWED_INPUT_STRING_VALUES = frozenset({"linear", "relu", "sigmoid"})

PAYLOAD_WARNING_ORDER = (
    "component_missing",
    "empty_structured_numeric_artifact",
    "malformed_structured_numeric_artifact_input",
    "unsupported_artifact_kind",
    "missing_candidates",
    "invalid_candidate_dropped",
    "max_items_reached",
)
PAYLOAD_WARNINGS = frozenset(PAYLOAD_WARNING_ORDER)

CANDIDATE_WARNING_ORDER = (
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
CANDIDATE_WARNINGS = frozenset(CANDIDATE_WARNING_ORDER)

_DEFAULT_MAX_ITEMS = 200
_MAX_INPUT_DEPTH = 4
_MAX_TOLERANCE = 1.0

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


def build_empty_structured_numeric_candidate_adapter_result(
    reason: str = "component_missing",
) -> dict[str, Any]:
    """Return an empty safe-candidate-compatible adapter payload."""
    token = reason if isinstance(reason, str) and reason in PAYLOAD_WARNINGS else "component_missing"
    return _payload(
        status="skipped",
        source_quality="unknown",
        candidates=[],
        input_candidate_count=0,
        supported_method_count=0,
        unsupported_method_count=0,
        warnings={token},
    )


def normalize_structured_numeric_candidate_artifact(
    payload: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Normalize a future structured artifact into the adapter output shape."""
    return adapt_structured_numeric_candidates_to_safe_candidates(payload, max_items=max_items)


def adapt_structured_numeric_candidates_to_safe_candidates(
    payload: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Convert a future structured artifact dict into safe-candidate payloads.

    The returned dict uses the existing closed ``candidates`` wrapper accepted by
    the Slice 130 advisory path. The function never raises and never mutates its
    caller input.
    """
    try:
        return _adapt(payload, max_items=max_items)
    except Exception:
        return build_empty_structured_numeric_candidate_adapter_result(
            "malformed_structured_numeric_artifact_input"
        )


def _adapt(payload: Any, *, max_items: Any) -> dict[str, Any]:
    if payload is None:
        return build_empty_structured_numeric_candidate_adapter_result("component_missing")
    if not isinstance(payload, dict):
        return build_empty_structured_numeric_candidate_adapter_result(
            "malformed_structured_numeric_artifact_input"
        )
    if payload.get("kind") != INPUT_KIND:
        return build_empty_structured_numeric_candidate_adapter_result("unsupported_artifact_kind")

    source_quality = _source_quality(payload.get("source_quality"))
    raw_candidates = payload.get("candidates")
    if raw_candidates is None:
        return _payload(
            status="skipped",
            source_quality=source_quality,
            candidates=[],
            input_candidate_count=0,
            supported_method_count=0,
            unsupported_method_count=0,
            warnings={"missing_candidates"},
        )
    if not isinstance(raw_candidates, list):
        return _payload(
            status="skipped",
            source_quality=source_quality,
            candidates=[],
            input_candidate_count=0,
            supported_method_count=0,
            unsupported_method_count=0,
            warnings={"malformed_structured_numeric_artifact_input"},
        )
    if not raw_candidates:
        return _payload(
            status="skipped",
            source_quality=source_quality,
            candidates=[],
            input_candidate_count=0,
            supported_method_count=0,
            unsupported_method_count=0,
            warnings={"empty_structured_numeric_artifact"},
        )

    cap = _cap(max_items)
    truncated = len(raw_candidates) > cap
    adapted: list[dict[str, Any]] = []
    supported_method_count = 0
    unsupported_method_count = 0
    dropped = False
    for index, candidate in enumerate(raw_candidates[:cap]):
        normalized = _normalize_candidate(candidate, index=index)
        if normalized is None:
            dropped = True
            continue
        computation = normalized.get("computation")
        method = computation.get("method") if isinstance(computation, dict) else None
        if method in SUPPORTED_METHODS:
            supported_method_count += 1
        elif "unsupported_method" in normalized.get("warnings", []):
            unsupported_method_count += 1
        adapted.append(normalized)

    warnings: set[str] = set()
    if truncated:
        warnings.add("max_items_reached")
    if dropped:
        warnings.add("invalid_candidate_dropped")

    status = _status(candidates=adapted, truncated=truncated, warnings=warnings)
    return _payload(
        status=status,
        source_quality=source_quality,
        candidates=adapted,
        input_candidate_count=len(raw_candidates),
        supported_method_count=supported_method_count,
        unsupported_method_count=unsupported_method_count,
        warnings=warnings,
    )


def _normalize_candidate(candidate: Any, *, index: int) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None

    warnings: set[str] = set()
    if any(key in candidate for key in FORBIDDEN_CANDIDATE_FIELDS):
        warnings.add("forbidden_field_stripped")

    if candidate.get("fact_type") != "numeric":
        return None

    value = _finite_number(candidate.get("value"))
    if value is None:
        return None

    ordinal = index + 1 if isinstance(index, int) and not isinstance(index, bool) and index >= 0 else 1
    candidate_id = _safe_id(candidate.get("id"), f"qs_struct_num_{ordinal:04d}", warnings, "invalid_id")
    concept_id = _safe_optional_id(candidate.get("concept_id"), warnings, "invalid_concept_id")
    label = _safe_label(candidate.get("label"), f"qs_struct_label_{ordinal:04d}", warnings)
    unit = _safe_unit(candidate.get("unit"), warnings)
    provenance = _safe_enum(
        candidate.get("provenance"),
        PROVENANCE_VALUES,
        "unverified",
        warnings,
        "invalid_provenance",
    )
    confidence = _safe_enum(
        candidate.get("confidence"),
        CONFIDENCE_VALUES,
        "medium",
        warnings,
        "invalid_confidence",
    )
    source_ref = _safe_source_ref(candidate.get("source_ref"), warnings, "invalid_source_ref")
    page_ref = _safe_source_ref(candidate.get("page_ref"), warnings, "invalid_page_ref")
    tolerance = _safe_tolerance(candidate.get("tolerance"), warnings)
    computation = _safe_computation(candidate.get("computation"), warnings)
    incoming_warnings = _safe_incoming_warnings(candidate.get("warnings"))
    warnings.update(incoming_warnings)

    out: dict[str, Any] = {
        "id": candidate_id,
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
        "warnings": _ordered(warnings, CANDIDATE_WARNING_ORDER),
    }
    return {key: out[key] for key in ALLOWED_CANDIDATE_FIELDS if key in out}


def _safe_computation(value: Any, warnings: set[str]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        warnings.add("malformed_computation")
        return None
    method = value.get("method")
    if not isinstance(method, str):
        warnings.add("unsupported_method")
        return None
    safe_method = _safe_method(method)
    if safe_method is None:
        warnings.add("unsupported_method")
        warnings.add("unsafe_string_sanitized")
        return None
    inputs, ok = _sanitize_numeric_inputs(value.get("inputs"), depth=0)
    if not ok or not isinstance(inputs, dict) or not inputs:
        warnings.add("malformed_computation")
        return None
    if safe_method not in SUPPORTED_METHODS:
        warnings.add("unsupported_method")
    return {"method": safe_method, "inputs": inputs}


def _sanitize_numeric_inputs(value: Any, *, depth: int) -> tuple[Any, bool]:
    if depth > _MAX_INPUT_DEPTH:
        return None, False
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
        if _unsafe_string(candidate):
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


def _safe_enum(
    value: Any,
    allowed: frozenset[str],
    default: str,
    warnings: set[str],
    warning_token: str,
) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        warnings.add(warning_token)
        return default
    candidate = value.strip().lower()
    if candidate in allowed:
        return candidate
    warnings.add(warning_token)
    if _unsafe_string(candidate):
        warnings.add("unsafe_string_sanitized")
    return default


def _safe_method(value: str) -> str | None:
    candidate = value.strip().lower()
    if not candidate or _unsafe_string(candidate):
        return None
    normalized = re.sub(r"[^a-z0-9_]+", "_", candidate).strip("_")
    if not normalized or not re.fullmatch(r"[a-z0-9_]{1,64}", normalized):
        return None
    return normalized


def _safe_tolerance(value: Any, warnings: set[str]) -> float | None:
    if value is None:
        return None
    number = _finite_number(value)
    if number is None or number < 0 or number > _MAX_TOLERANCE:
        warnings.add("invalid_tolerance")
        return None
    return number


def _safe_incoming_warnings(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {token for token in value if isinstance(token, str) and token in CANDIDATE_WARNINGS}


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return None
        if isinstance(value, int):
            return int(value)
        return float(value)
    return None


def _unsafe_string(value: str) -> bool:
    return bool(_UNSAFE_RE.search(value) or _BASE64ISH_RE.fullmatch(value.strip()))


def _source_quality(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in SOURCE_QUALITIES:
        return value.strip().lower()
    return "unknown"


def _status(*, candidates: list[dict[str, Any]], truncated: bool, warnings: set[str]) -> str:
    if truncated:
        return "partial"
    if not candidates:
        return "warning" if "invalid_candidate_dropped" in warnings else "skipped"
    if warnings or any(candidate.get("warnings") for candidate in candidates):
        return "warning"
    return "ok"


def _payload(
    *,
    status: str,
    source_quality: str,
    candidates: list[dict[str, Any]],
    input_candidate_count: int,
    supported_method_count: int,
    unsupported_method_count: int,
    warnings: set[str],
) -> dict[str, Any]:
    output_count = len(candidates)
    safe_input_count = max(0, input_candidate_count)
    dropped_count = max(0, safe_input_count - output_count)
    return {
        "version": VERSION,
        "kind": OUTPUT_KIND,
        "status": status if status in PAYLOAD_STATUSES else "warning",
        "source_quality": source_quality if source_quality in SOURCE_QUALITIES else "unknown",
        "summary": {
            "input_candidate_count": safe_input_count,
            "output_candidate_count": max(0, output_count),
            "supported_method_count": max(0, supported_method_count),
            "unsupported_method_count": max(0, unsupported_method_count),
            "dropped_candidate_count": dropped_count,
        },
        "candidates": candidates,
        "warnings": _ordered(warnings, PAYLOAD_WARNING_ORDER),
    }


def _ordered(warnings: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in warnings]


def _cap(max_items: Any) -> int:
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        return max(0, min(max_items, _DEFAULT_MAX_ITEMS))
    return _DEFAULT_MAX_ITEMS
