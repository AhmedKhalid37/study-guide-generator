"""Quality Safety fact-sheet schema v1 (Slice 110).

Pure, deterministic schema/normalization helpers for future quality-safety
verification. This module is intentionally unwired: it reads only caller-supplied
dicts, writes nothing, calls no providers/models, and does not inspect source
documents, clean.md, OCR, renderers, jobs, FastAPI, or frontend code.

The public functions are total and return JSON-serializable dicts. Malformed input
degrades to closed warning tokens only; raw exception text and raw unsafe strings
are never emitted.
"""
from __future__ import annotations

import math
import re
from typing import Any

VERSION = 1
KIND = "quality_safety_fact_sheet"

FACT_TYPES = frozenset({"numeric", "categorical", "string", "table"})
PROVENANCE_VALUES = frozenset({"extracted_high", "computed", "canonical_fixture", "unverified"})
VERIFICATION_STATUSES = frozenset({"verified", "unverified", "failed"})
CONFIDENCE_VALUES = frozenset({"high", "medium", "low", "unsupported"})
COMPUTATION_METHODS = frozenset(
    {
        "weighted_gini",
        "total_error",
        "amount_of_say",
        "softmax",
        "cross_entropy",
        "forward_pass",
        "manual",
        "unknown",
    }
)

SHEET_STATUSES = frozenset({"completed", "partial", "skipped", "warning"})
SOURCE_QUALITIES = frozenset(
    {"clean", "ambiguous_animation_frames", "scanned", "mixed", "synthetic", "unknown"}
)

FACT_WARNING_ORDER = (
    "malformed_fact_degraded",
    "invalid_fact_id",
    "invalid_fact_type",
    "invalid_provenance",
    "invalid_verification_status",
    "invalid_confidence",
    "invalid_numeric_value",
    "invalid_source_ref",
    "invalid_computation",
    "invalid_computation_method",
    "unsafe_string_sanitized",
    "max_items_reached",
)

SHEET_WARNING_ORDER = (
    "malformed_fact_sheet_degraded",
    "invalid_lecture_id",
    "invalid_source_quality",
    "invalid_concept_dropped",
    "invalid_teaching_note_dropped",
    "invalid_worked_example_dropped",
    "max_items_reached",
    "unsafe_string_sanitized",
)

_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_SAFE_SOURCE_REF_RE = re.compile(r"^(?:source_page|page|slide|source_ref)_[0-9]{1,4}$")
_SAFE_COMPUTATION_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_UNSAFE_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|/var/|\\\\|[A-Za-z]:\\|\.\./|/\.\.|"
    r"authorization|bearer|api[_-]?key|token|secret|data:|base64|provider payload|"
    r"ocr|caption|table text|uploaded[_ -]?quality|quality[_ -]?spec|evidence quote|"
    r"source text|raw text|guide snippet|source snippet|private|\.pdf|\.docx|\.zip|"
    r"\.png|\.jpg|\.jpeg|\.webp|\.socket|\.sock)",
    re.IGNORECASE,
)
_BASE64ISH_RE = re.compile(r"^[A-Za-z0-9+/]{80,}={0,2}$")

_DEFAULT_CONCEPT_LIMIT = 80
_DEFAULT_FACT_LIMIT = 200
_DEFAULT_NOTE_LIMIT = 40
_DEFAULT_EXAMPLE_LIMIT = 40
_MAX_STRING_LEN = 120
_MAX_VALUE_STRING_LEN = 200
_MAX_TABLE_ITEMS = 24


def normalize_quality_safety_fact_record(data: Any, *, max_items: int | None = None) -> dict[str, Any]:
    """Normalize one fact record; never raise on malformed input."""
    try:
        return _normalize_fact_record(data, fallback_id="fact_unknown", max_items=max_items)
    except Exception:
        return _fact_record(
            fact_id="fact_unknown",
            concept="Synthetic Concept",
            label="synthetic_label",
            value=None,
            fact_type="string",
            provenance="unverified",
            verification_status="unverified",
            confidence="low",
            source_ref=None,
            computation=None,
            warnings={"malformed_fact_degraded"},
        )


def normalize_quality_safety_fact_sheet(data: Any, *, max_items: int | None = None) -> dict[str, Any]:
    """Normalize a fact sheet; never raise on malformed input."""
    try:
        return _normalize_fact_sheet(data, max_items=max_items)
    except Exception:
        return _sheet(
            status="skipped",
            lecture_id="synthetic_fixture",
            source_quality="unknown",
            concepts=[],
            warnings={"malformed_fact_sheet_degraded"},
        )


def validate_quality_safety_fact_sheet(data: Any, *, max_items: int | None = None) -> dict[str, Any]:
    """Alias for normalization; the normalized dict is the validation result."""
    return normalize_quality_safety_fact_sheet(data, max_items=max_items)


def build_empty_quality_safety_fact_sheet(
    *, lecture_id: Any = None, source_quality: Any = None
) -> dict[str, Any]:
    """Build an empty completed fact sheet with safe metadata."""
    warnings: set[str] = set()
    safe_lecture = _safe_meta_id(lecture_id, "synthetic_fixture", warnings, "invalid_lecture_id")
    safe_quality = _safe_source_quality(source_quality, warnings)
    return _sheet(
        status="completed",
        lecture_id=safe_lecture,
        source_quality=safe_quality,
        concepts=[],
        warnings=warnings,
    )


def _normalize_fact_sheet(data: Any, *, max_items: Any) -> dict[str, Any]:
    warnings: set[str] = set()
    if not isinstance(data, dict):
        warnings.add("malformed_fact_sheet_degraded")
        return _sheet(
            status="skipped",
            lecture_id="synthetic_fixture",
            source_quality="unknown",
            concepts=[],
            warnings=warnings,
        )

    lecture_id = _safe_meta_id(data.get("lecture_id"), "synthetic_fixture", warnings, "invalid_lecture_id")
    source_quality = _safe_source_quality(data.get("source_quality"), warnings)
    concept_cap = _cap(max_items, _DEFAULT_CONCEPT_LIMIT)
    fact_cap = _cap(max_items, _DEFAULT_FACT_LIMIT)
    note_cap = _cap(max_items, _DEFAULT_NOTE_LIMIT)
    example_cap = _cap(max_items, _DEFAULT_EXAMPLE_LIMIT)

    raw_concepts = data.get("concepts")
    if raw_concepts is None:
        raw_concepts = []
    if not isinstance(raw_concepts, list):
        warnings.add("malformed_fact_sheet_degraded")
        raw_concepts = []

    concepts: list[dict[str, Any]] = []
    if len(raw_concepts) > concept_cap:
        warnings.add("max_items_reached")
    for concept_index, raw_concept in enumerate(raw_concepts[:concept_cap], start=1):
        concept = _normalize_concept(
            raw_concept,
            concept_index=concept_index,
            fact_cap=fact_cap,
            note_cap=note_cap,
            example_cap=example_cap,
            sheet_warnings=warnings,
        )
        if concept is None:
            warnings.add("invalid_concept_dropped")
            continue
        concepts.append(concept)

    status = _sheet_status(concepts, warnings)
    return _sheet(
        status=status,
        lecture_id=lecture_id,
        source_quality=source_quality,
        concepts=concepts,
        warnings=warnings,
    )


def _normalize_concept(
    data: Any,
    *,
    concept_index: int,
    fact_cap: int,
    note_cap: int,
    example_cap: int,
    sheet_warnings: set[str],
) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None

    concept_name, concept_safe = _safe_text(data.get("concept"), "Synthetic Concept")
    if not concept_safe:
        sheet_warnings.add("unsafe_string_sanitized")

    facts_raw = data.get("facts")
    if facts_raw is None:
        facts_raw = []
    if not isinstance(facts_raw, list):
        facts_raw = []
        sheet_warnings.add("malformed_fact_sheet_degraded")
    if len(facts_raw) > fact_cap:
        sheet_warnings.add("max_items_reached")

    facts: list[dict[str, Any]] = []
    for fact_index, raw_fact in enumerate(facts_raw[:fact_cap], start=1):
        fallback_id = f"fact_{fact_index:04d}"
        fact = _normalize_fact_record(
            raw_fact,
            fallback_id=fallback_id,
            concept_default=concept_name,
            max_items=fact_cap,
        )
        facts.append(fact)

    notes = _safe_note_list(data.get("teaching_notes"), note_cap, sheet_warnings)
    examples = _safe_examples(data.get("worked_examples"), example_cap, concept_index, sheet_warnings)

    return {
        "concept": concept_name,
        "facts": facts,
        "teaching_notes": notes,
        "worked_examples": examples,
    }


def _normalize_fact_record(
    data: Any,
    *,
    fallback_id: str,
    concept_default: str = "Synthetic Concept",
    max_items: Any = None,
) -> dict[str, Any]:
    warnings: set[str] = set()
    if not isinstance(data, dict):
        warnings.add("malformed_fact_degraded")
        data = {}

    fact_id = _safe_fact_id(data.get("id"), fallback_id, warnings)
    concept, concept_safe = _safe_text(data.get("concept"), concept_default)
    label, label_safe = _safe_label(data.get("label"), "synthetic_label")
    if not concept_safe or not label_safe:
        warnings.add("unsafe_string_sanitized")

    fact_type = _safe_enum(data.get("type"), FACT_TYPES, "string", warnings, "invalid_fact_type")
    provenance = _safe_enum(data.get("provenance"), PROVENANCE_VALUES, "unverified", warnings, "invalid_provenance")
    status = _safe_enum(
        data.get("verification_status"),
        VERIFICATION_STATUSES,
        "unverified",
        warnings,
        "invalid_verification_status",
    )
    confidence = _safe_enum(data.get("confidence"), CONFIDENCE_VALUES, "low", warnings, "invalid_confidence")
    source_ref = _safe_source_ref(data.get("source_ref"), warnings)
    value = _safe_value(data.get("value"), fact_type, warnings)
    if fact_type == "numeric" and value is None:
        status = "unverified"
    computation = _safe_computation(data.get("computation"), fact_type, warnings, max_items=max_items)

    return _fact_record(
        fact_id=fact_id,
        concept=concept,
        label=label,
        value=value,
        fact_type=fact_type,
        provenance=provenance,
        verification_status=status,
        confidence=confidence,
        source_ref=source_ref,
        computation=computation,
        warnings=warnings,
    )


def _fact_record(
    *,
    fact_id: str,
    concept: str,
    label: str,
    value: Any,
    fact_type: str,
    provenance: str,
    verification_status: str,
    confidence: str,
    source_ref: str | None,
    computation: dict[str, Any] | None,
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "concept": concept,
        "label": label,
        "value": value,
        "type": fact_type,
        "provenance": provenance,
        "verification_status": verification_status,
        "confidence": confidence,
        "source_ref": source_ref,
        "computation": computation,
        "warnings": _ordered(warnings, FACT_WARNING_ORDER),
    }


def _sheet(
    *,
    status: str,
    lecture_id: str,
    source_quality: str,
    concepts: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    sheet_warnings = _ordered(warnings, SHEET_WARNING_ORDER)
    summary = _summary(concepts, sheet_warnings)
    return {
        "version": VERSION,
        "kind": KIND,
        "status": status if status in SHEET_STATUSES else "warning",
        "lecture_id": lecture_id,
        "source_quality": source_quality,
        "summary": summary,
        "concepts": concepts,
        "warnings": sheet_warnings,
    }


def _summary(concepts: list[dict[str, Any]], sheet_warnings: list[str]) -> dict[str, int]:
    fact_count = 0
    numeric_fact_count = 0
    verified_fact_count = 0
    unverified_fact_count = 0
    failed_fact_count = 0
    fact_warning_count = 0
    for concept in concepts:
        facts = concept.get("facts") if isinstance(concept, dict) else []
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            fact_count += 1
            if fact.get("type") == "numeric":
                numeric_fact_count += 1
            status = fact.get("verification_status")
            if status == "verified":
                verified_fact_count += 1
            elif status == "failed":
                failed_fact_count += 1
            else:
                unverified_fact_count += 1
            fw = fact.get("warnings")
            if isinstance(fw, list):
                fact_warning_count += len(fw)
    return {
        "concept_count": max(0, len(concepts)),
        "fact_count": max(0, fact_count),
        "numeric_fact_count": max(0, numeric_fact_count),
        "verified_fact_count": max(0, verified_fact_count),
        "unverified_fact_count": max(0, unverified_fact_count),
        "failed_fact_count": max(0, failed_fact_count),
        "warning_count": max(0, len(sheet_warnings) + fact_warning_count),
    }


def _sheet_status(concepts: list[dict[str, Any]], warnings: set[str]) -> str:
    if "max_items_reached" in warnings:
        return "partial"
    if warnings:
        return "warning"
    if not concepts:
        return "completed"
    return "completed"


def _safe_meta_id(value: Any, default: str, warnings: set[str], warning_token: str) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add(warning_token)
        return default
    stripped = value.strip()
    if _unsafe_string(stripped):
        warnings.add(warning_token)
        return default
    normalized = _normalize_id_chars(stripped)
    if not _SAFE_ID_RE.fullmatch(normalized):
        warnings.add(warning_token)
        return default
    return normalized


def _safe_fact_id(value: Any, fallback: str, warnings: set[str]) -> str:
    if not isinstance(value, str):
        warnings.add("invalid_fact_id")
        return fallback
    stripped = value.strip().lower()
    if _unsafe_string(stripped):
        warnings.add("invalid_fact_id")
        return fallback
    normalized = _normalize_id_chars(stripped)
    if not _SAFE_ID_RE.fullmatch(normalized):
        warnings.add("invalid_fact_id")
        return fallback
    return normalized


def _normalize_id_chars(value: str) -> str:
    normalized = re.sub(r"\s+", "_", value.strip().lower())
    normalized = re.sub(r"[^a-z0-9._-]+", "_", normalized)
    normalized = normalized.strip("._-")
    normalized = re.sub(r"[._-]{2,}", "_", normalized)
    return normalized[:80]


def _safe_source_quality(value: Any, warnings: set[str]) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add("invalid_source_quality")
        return "unknown"
    candidate = value.strip().lower()
    if candidate not in SOURCE_QUALITIES:
        warnings.add("invalid_source_quality")
        return "unknown"
    return candidate


def _safe_enum(
    value: Any,
    allowed: frozenset[str],
    default: str,
    warnings: set[str],
    warning_token: str,
) -> str:
    if not isinstance(value, str):
        warnings.add(warning_token)
        return default
    candidate = value.strip().lower()
    if candidate not in allowed:
        warnings.add(warning_token)
        return default
    return candidate


def _safe_text(value: Any, default: str, *, max_len: int = _MAX_STRING_LEN) -> tuple[str, bool]:
    if not isinstance(value, str):
        return default, value is None
    stripped = " ".join(value.strip().split())
    if not stripped or _unsafe_string(stripped):
        return default, False
    if len(stripped) > max_len:
        stripped = stripped[:max_len].rstrip()
    return stripped, True


def _safe_label(value: Any, default: str) -> tuple[str, bool]:
    if not isinstance(value, str):
        return default, value is None
    stripped = value.strip()
    if not stripped or _unsafe_string(stripped):
        return default, False
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", stripped).strip("_.:-")
    if not cleaned:
        return default, False
    return cleaned[:80], True


def _safe_source_ref(value: Any, warnings: set[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        warnings.add("invalid_source_ref")
        return None
    candidate = value.strip().lower()
    if _unsafe_string(candidate) or not _SAFE_SOURCE_REF_RE.fullmatch(candidate):
        warnings.add("invalid_source_ref")
        return None
    return candidate


def _safe_value(value: Any, fact_type: str, warnings: set[str]) -> Any:
    if fact_type == "numeric":
        number = _finite_number(value)
        if number is None:
            warnings.add("invalid_numeric_value")
            return None
        return number
    if fact_type in {"string", "categorical"}:
        text, safe = _safe_text(value, "sanitized_value", max_len=_MAX_VALUE_STRING_LEN)
        if not safe:
            warnings.add("unsafe_string_sanitized")
        return text
    if fact_type == "table":
        sanitized, safe = _safe_json_value(value, depth=0, max_items=_MAX_TABLE_ITEMS)
        if not safe:
            warnings.add("unsafe_string_sanitized")
        return sanitized
    return None


def _safe_computation(
    value: Any,
    fact_type: str,
    warnings: set[str],
    *,
    max_items: Any,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        warnings.add("invalid_computation")
        return None
    method = value.get("method")
    if not isinstance(method, str):
        method = "unknown"
        warnings.add("invalid_computation_method")
    else:
        method = method.strip().lower()
        if method not in COMPUTATION_METHODS:
            method = "unknown"
            warnings.add("invalid_computation_method")

    input_cap = _cap(max_items, _MAX_TABLE_ITEMS)
    inputs, inputs_safe = _safe_mapping(value.get("inputs"), max_items=input_cap)
    result = value.get("result")
    safe_result: float | int | None
    if result is None:
        safe_result = None
    else:
        safe_result = _finite_number(result)
        if safe_result is None:
            warnings.add("invalid_computation")
    if not inputs_safe:
        warnings.add("invalid_computation")
    if fact_type == "numeric" and result is not None and safe_result is None:
        warnings.add("invalid_numeric_value")
    tolerance = value.get("tolerance")
    safe_tolerance: float | int | None
    if tolerance is None:
        safe_tolerance = None
    else:
        safe_tolerance = _finite_number(tolerance)
        if safe_tolerance is None or not (0.0 < float(safe_tolerance) <= 1.0):
            safe_tolerance = None
            warnings.add("invalid_computation")
    return {"method": method, "inputs": inputs, "result": safe_result, "tolerance": safe_tolerance}


def _safe_mapping(value: Any, *, max_items: int) -> tuple[dict[str, Any], bool]:
    if value is None:
        return {}, True
    if not isinstance(value, dict):
        return {}, False
    out: dict[str, Any] = {}
    safe = True
    for idx, (key, item) in enumerate(value.items()):
        if idx >= max_items:
            safe = False
            break
        key_text = str(key).strip().lower() if isinstance(key, str) else ""
        key_text = re.sub(r"[^a-z0-9._-]+", "_", key_text).strip("._-")
        if not key_text or _unsafe_string(key_text) or not _SAFE_COMPUTATION_KEY_RE.fullmatch(key_text):
            safe = False
            continue
        safe_item, item_safe = _safe_json_value(item, depth=0, max_items=max_items)
        if not item_safe:
            safe = False
        out[key_text] = safe_item
    return out, safe


def _safe_json_value(value: Any, *, depth: int, max_items: int) -> tuple[Any, bool]:
    if depth > 3:
        return None, False
    if value is None or isinstance(value, bool):
        return value, True
    number = _finite_number(value)
    if number is not None:
        return number, True
    if isinstance(value, str):
        text, safe = _safe_text(value, "sanitized_value", max_len=_MAX_VALUE_STRING_LEN)
        return text, safe
    if isinstance(value, list):
        out = []
        safe = True
        for idx, item in enumerate(value):
            if idx >= max_items:
                safe = False
                break
            safe_item, item_safe = _safe_json_value(item, depth=depth + 1, max_items=max_items)
            if not item_safe:
                safe = False
            out.append(safe_item)
        return out, safe
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        safe = True
        for idx, (key, item) in enumerate(value.items()):
            if idx >= max_items:
                safe = False
                break
            key_text = str(key).strip().lower() if isinstance(key, str) else ""
            key_text = re.sub(r"[^a-z0-9._-]+", "_", key_text).strip("._-")
            if not key_text or _unsafe_string(key_text) or not _SAFE_COMPUTATION_KEY_RE.fullmatch(key_text):
                safe = False
                continue
            safe_item, item_safe = _safe_json_value(item, depth=depth + 1, max_items=max_items)
            if not item_safe:
                safe = False
            out[key_text] = safe_item
        return out, safe
    return None, False


def _safe_note_list(value: Any, cap: int, warnings: set[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.add("invalid_teaching_note_dropped")
        return []
    if len(value) > cap:
        warnings.add("max_items_reached")
    out: list[str] = []
    for item in value[:cap]:
        text, safe = _safe_text(item, "", max_len=_MAX_VALUE_STRING_LEN)
        if not text or not safe:
            warnings.add("invalid_teaching_note_dropped")
            if not safe:
                warnings.add("unsafe_string_sanitized")
            continue
        out.append(text)
    return out


def _safe_examples(
    value: Any,
    cap: int,
    concept_index: int,
    warnings: set[str],
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.add("invalid_worked_example_dropped")
        return []
    if len(value) > cap:
        warnings.add("max_items_reached")
    out: list[dict[str, Any]] = []
    for index, item in enumerate(value[:cap], start=1):
        if not isinstance(item, dict):
            warnings.add("invalid_worked_example_dropped")
            continue
        example_id = _safe_example_id(
            item.get("id"),
            f"example_{concept_index:04d}_{index:04d}",
        )
        trace_key = _safe_trace_key(item.get("trace_key"))
        answer, answer_safe = _safe_text(item.get("answer"), "sanitized_answer", max_len=_MAX_VALUE_STRING_LEN)
        if not answer_safe:
            warnings.add("invalid_worked_example_dropped")
            warnings.add("unsafe_string_sanitized")
            continue
        out.append({"id": example_id, "trace_key": trace_key, "answer": answer})
    return out


def _safe_example_id(value: Any, fallback: str) -> str:
    if not isinstance(value, str) or _unsafe_string(value):
        return fallback
    normalized = _normalize_id_chars(value)
    return normalized if _SAFE_ID_RE.fullmatch(normalized) else fallback


def _safe_trace_key(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _unsafe_string(value):
        return None
    candidate = value.strip()
    return candidate[:80] if _SAFE_TOKEN_RE.fullmatch(candidate) else None


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


def _cap(max_items: Any, default: int) -> int:
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        return max(0, min(max_items, default))
    return default


def _ordered(values: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in values]
