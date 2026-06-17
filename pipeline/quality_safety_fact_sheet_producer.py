"""Quality Safety fact-sheet producer v1 (Slice 117).

Pure, deterministic mapper from sanitized extraction-like structured bundles to
the Slice 110 fact-sheet schema. This module is intentionally unwired: it reads
only caller-supplied in-memory dicts, writes nothing, scans no directories, reads
no source documents or clean.md, and calls no providers/models/cloud services.
"""
from __future__ import annotations

import math
import re
from typing import Any

from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet

VERSION = 1
BUNDLE_KIND = "quality_safety_extraction_bundle"
RESULT_KIND = "quality_safety_fact_sheet_producer_result"

SOURCE_QUALITIES = frozenset(
    {"clean", "ambiguous_animation_frames", "scanned", "mixed", "synthetic", "unknown"}
)
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
SAFE_VERIFICATION_STATUSES = frozenset({"verified", "unverified", "failed"})
SAFE_CONFIDENCE = frozenset({"high", "medium", "low", "unsupported"})

WARNING_ORDER = (
    "malformed_extraction_bundle_degraded",
    "invalid_lecture_id",
    "invalid_source_quality",
    "invalid_concept_dropped",
    "invalid_source_ref",
    "invalid_computation_record_dropped",
    "invalid_numeric_observation_dropped",
    "invalid_computation_method",
    "invalid_computation_inputs",
    "invalid_numeric_value",
    "unsafe_string_sanitized",
    "max_items_reached",
)

METHOD_TOLERANCES = {
    "weighted_gini": 0.01,
    "total_error": 0.005,
    "amount_of_say": 0.02,
    "softmax": 0.01,
    "cross_entropy": 0.01,
    "forward_pass": 0.01,
    "manual": 1e-6,
    "unknown": 1e-6,
}

_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
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

_DEFAULT_MAX_ITEMS = 200


def normalize_quality_safety_extraction_bundle(data: Any, *, max_items: int | None = None) -> dict[str, Any]:
    """Normalize a sanitized extraction bundle; never raise on malformed input."""
    try:
        return _normalize_bundle(data, max_items=max_items)
    except Exception:
        return _bundle(
            lecture_id="synthetic_fixture",
            source_quality="unknown",
            concepts=[],
            warnings={"malformed_extraction_bundle_degraded"},
        )


def extract_quality_safety_computation_records(
    extraction_bundle: Any, *, max_items: int | None = None
) -> list[dict[str, Any]]:
    """Return normalized computation records with concept context."""
    bundle = normalize_quality_safety_extraction_bundle(extraction_bundle, max_items=max_items)
    records: list[dict[str, Any]] = []
    cap = _cap(max_items)
    for concept in bundle.get("concepts", []):
        if not isinstance(concept, dict):
            continue
        for record in concept.get("computation_records", []):
            if len(records) >= cap:
                return records
            item = dict(record)
            item["concept"] = concept.get("concept", "Synthetic Concept")
            item["source_ref"] = record.get("source_ref") or concept.get("source_ref")
            records.append(item)
    return records


def extract_quality_safety_numeric_observations(
    extraction_bundle: Any, *, max_items: int | None = None
) -> list[dict[str, Any]]:
    """Return normalized numeric observations with concept context."""
    bundle = normalize_quality_safety_extraction_bundle(extraction_bundle, max_items=max_items)
    observations: list[dict[str, Any]] = []
    cap = _cap(max_items)
    for concept in bundle.get("concepts", []):
        if not isinstance(concept, dict):
            continue
        for observation in concept.get("numeric_observations", []):
            if len(observations) >= cap:
                return observations
            item = dict(observation)
            item["concept"] = concept.get("concept", "Synthetic Concept")
            item["source_ref"] = observation.get("source_ref") or concept.get("source_ref")
            observations.append(item)
    return observations


def build_quality_safety_fact_sheet_from_extraction(
    extraction_bundle: Any,
    *,
    fixture_spec: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Build a normalized Slice 110 fact sheet from a sanitized extraction bundle."""
    del fixture_spec
    result = run_quality_safety_fact_sheet_producer(extraction_bundle, max_items=max_items)
    fact_sheet = result.get("fact_sheet")
    if isinstance(fact_sheet, dict):
        return fact_sheet
    return normalize_quality_safety_fact_sheet(None, max_items=max_items)


def run_quality_safety_fact_sheet_producer(
    extraction_bundle: Any,
    *,
    fixture_spec: Any = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Run the pure extraction-bundle to fact-sheet producer; never raise."""
    try:
        del fixture_spec
        return _produce(extraction_bundle, max_items=max_items)
    except Exception:
        fact_sheet = normalize_quality_safety_fact_sheet(None, max_items=max_items)
        return _result(
            status="failed",
            fact_sheet=fact_sheet,
            concept_count=0,
            computation_record_count=0,
            numeric_observation_count=0,
            produced_fact_count=0,
            dropped_item_count=0,
            warnings={"malformed_extraction_bundle_degraded"},
        )


def _produce(extraction_bundle: Any, *, max_items: Any) -> dict[str, Any]:
    normalized = normalize_quality_safety_extraction_bundle(extraction_bundle, max_items=max_items)
    warnings = set(normalized.get("warnings", []))
    concepts_out: list[dict[str, Any]] = []
    produced_fact_count = 0
    computation_record_count = 0
    numeric_observation_count = 0
    dropped_item_count = 0
    cap = _cap(max_items)

    for concept_index, concept in enumerate(normalized.get("concepts", []), start=1):
        if not isinstance(concept, dict):
            dropped_item_count += 1
            warnings.add("invalid_concept_dropped")
            continue
        facts: list[dict[str, Any]] = []
        concept_name = concept.get("concept", "Synthetic Concept")
        concept_ref = concept.get("source_ref")

        for record_index, record in enumerate(concept.get("computation_records", []), start=1):
            if len(facts) >= cap:
                warnings.add("max_items_reached")
                break
            computation_record_count += 1
            fact = _fact_from_computation_record(
                record,
                concept=concept_name,
                source_ref=concept_ref,
                concept_index=concept_index,
                record_index=record_index,
                warnings=warnings,
            )
            if fact is None:
                dropped_item_count += 1
                continue
            facts.append(fact)
            produced_fact_count += 1

        for observation_index, observation in enumerate(concept.get("numeric_observations", []), start=1):
            if len(facts) >= cap:
                warnings.add("max_items_reached")
                break
            numeric_observation_count += 1
            fact = _fact_from_numeric_observation(
                observation,
                concept=concept_name,
                source_ref=concept_ref,
                concept_index=concept_index,
                observation_index=observation_index,
                source_quality=normalized.get("source_quality", "unknown"),
                warnings=warnings,
            )
            if fact is None:
                dropped_item_count += 1
                continue
            facts.append(fact)
            produced_fact_count += 1

        concepts_out.append({"concept": concept_name, "facts": facts})

    fact_sheet = normalize_quality_safety_fact_sheet(
        {
            "lecture_id": normalized.get("lecture_id"),
            "source_quality": normalized.get("source_quality"),
            "concepts": concepts_out,
        },
        max_items=max_items,
    )
    warnings.update(token for token in fact_sheet.get("warnings", []) if token == "max_items_reached")
    status = _producer_status(
        input_was_mapping=isinstance(extraction_bundle, dict),
        warnings=warnings,
        produced_fact_count=produced_fact_count,
    )
    return _result(
        status=status,
        fact_sheet=fact_sheet,
        concept_count=len(normalized.get("concepts", [])),
        computation_record_count=computation_record_count,
        numeric_observation_count=numeric_observation_count,
        produced_fact_count=produced_fact_count,
        dropped_item_count=dropped_item_count,
        warnings=warnings,
    )


def _normalize_bundle(data: Any, *, max_items: Any) -> dict[str, Any]:
    warnings: set[str] = set()
    if not isinstance(data, dict):
        warnings.add("malformed_extraction_bundle_degraded")
        return _bundle(
            lecture_id="synthetic_fixture",
            source_quality="unknown",
            concepts=[],
            warnings=warnings,
        )

    lecture_id = _safe_id(data.get("lecture_id"), "synthetic_fixture", warnings, "invalid_lecture_id")
    source_quality = _safe_source_quality(data.get("source_quality"), warnings)
    cap = _cap(max_items)
    raw_concepts = data.get("concepts")
    if raw_concepts is None:
        raw_concepts = []
    if not isinstance(raw_concepts, list):
        warnings.add("malformed_extraction_bundle_degraded")
        raw_concepts = []
    if len(raw_concepts) > cap:
        warnings.add("max_items_reached")

    concepts: list[dict[str, Any]] = []
    for concept_index, raw_concept in enumerate(raw_concepts[:cap], start=1):
        concept = _normalize_concept(raw_concept, concept_index=concept_index, cap=cap, warnings=warnings)
        if concept is None:
            warnings.add("invalid_concept_dropped")
            continue
        concepts.append(concept)
    return _bundle(lecture_id=lecture_id, source_quality=source_quality, concepts=concepts, warnings=warnings)


def _normalize_concept(data: Any, *, concept_index: int, cap: int, warnings: set[str]) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    concept, concept_safe = _safe_text(data.get("concept"), "Synthetic Concept")
    if not concept_safe:
        warnings.add("unsafe_string_sanitized")
        if data.get("concept") is not None:
            return None
    source_ref = _safe_source_ref(data.get("source_ref"), warnings)

    raw_records = data.get("computation_records") or []
    if not isinstance(raw_records, list):
        warnings.add("invalid_computation_record_dropped")
        raw_records = []
    if len(raw_records) > cap:
        warnings.add("max_items_reached")
    records = []
    for index, raw_record in enumerate(raw_records[:cap], start=1):
        record = _normalize_computation_record(raw_record, concept_index=concept_index, record_index=index, warnings=warnings)
        if record is None:
            warnings.add("invalid_computation_record_dropped")
            continue
        records.append(record)

    raw_observations = data.get("numeric_observations") or []
    if not isinstance(raw_observations, list):
        warnings.add("invalid_numeric_observation_dropped")
        raw_observations = []
    if len(raw_observations) > cap:
        warnings.add("max_items_reached")
    observations = []
    for index, raw_observation in enumerate(raw_observations[:cap], start=1):
        observation = _normalize_numeric_observation(
            raw_observation,
            concept_index=concept_index,
            observation_index=index,
            warnings=warnings,
        )
        if observation is None:
            warnings.add("invalid_numeric_observation_dropped")
            continue
        observations.append(observation)

    return {
        "concept": concept,
        "source_ref": source_ref,
        "computation_records": records,
        "numeric_observations": observations,
    }


def _normalize_computation_record(
    data: Any, *, concept_index: int, record_index: int, warnings: set[str]
) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    method = _safe_method(data.get("method"), warnings)
    inputs, inputs_safe = _safe_mapping(data.get("inputs"), max_items=_DEFAULT_MAX_ITEMS)
    if not inputs_safe or not inputs:
        warnings.add("invalid_computation_inputs")
        return None
    claimed_value = _finite_number(data.get("claimed_value"))
    if claimed_value is None:
        claimed_value = _finite_number(data.get("value"))
    if claimed_value is None and data.get("claimed_value") is not None:
        warnings.add("invalid_numeric_value")
    tolerance = _safe_tolerance(data.get("tolerance"), method)
    record_id = _safe_id(
        data.get("id"),
        f"synthetic.computation.{concept_index:04d}.{record_index:04d}",
        warnings,
        "invalid_computation_record_dropped",
    )
    label = _safe_label(data.get("label"), f"synthetic_computation_{concept_index:04d}_{record_index:04d}", warnings)
    source_ref = _safe_source_ref(data.get("source_ref"), warnings)
    confidence = _safe_confidence(data.get("confidence"), default="medium")
    status = _safe_status(data.get("verification_status"))
    return {
        "id": record_id,
        "label": label,
        "type": "numeric",
        "method": method,
        "inputs": inputs,
        "claimed_value": claimed_value,
        "tolerance": tolerance,
        "source_ref": source_ref,
        "confidence": confidence,
        "verification_status": status,
    }


def _normalize_numeric_observation(
    data: Any, *, concept_index: int, observation_index: int, warnings: set[str]
) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    value = _finite_number(data.get("value"))
    if value is None:
        warnings.add("invalid_numeric_value")
        return None
    observation_id = _safe_id(
        data.get("id"),
        f"synthetic.observation.{concept_index:04d}.{observation_index:04d}",
        warnings,
        "invalid_numeric_observation_dropped",
    )
    label = _safe_label(data.get("label"), f"synthetic_observation_{concept_index:04d}_{observation_index:04d}", warnings)
    source_ref = _safe_source_ref(data.get("source_ref"), warnings)
    confidence = _safe_confidence(data.get("confidence"), default="medium")
    tolerance = _safe_tolerance(data.get("tolerance"), "manual")
    return {
        "id": observation_id,
        "label": label,
        "value": value,
        "tolerance": tolerance,
        "source_ref": source_ref,
        "confidence": confidence,
    }


def _fact_from_computation_record(
    record: Any,
    *,
    concept: str,
    source_ref: str | None,
    concept_index: int,
    record_index: int,
    warnings: set[str],
) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        warnings.add("invalid_computation_record_dropped")
        return None
    method = record.get("method") if record.get("method") in COMPUTATION_METHODS else "unknown"
    value = _finite_number(record.get("claimed_value"))
    return {
        "id": record.get("id") or f"synthetic.computation.{concept_index:04d}.{record_index:04d}",
        "concept": concept,
        "label": record.get("label") or f"synthetic_computation_{concept_index:04d}_{record_index:04d}",
        "value": value,
        "type": "numeric",
        "provenance": "computed" if method in COMPUTATION_METHODS - {"manual", "unknown"} else "unverified",
        "verification_status": record.get("verification_status") if record.get("verification_status") == "verified" else "unverified",
        "confidence": record.get("confidence") if record.get("confidence") in SAFE_CONFIDENCE else "medium",
        "source_ref": record.get("source_ref") or source_ref,
        "computation": {
            "method": method,
            "inputs": record.get("inputs") if isinstance(record.get("inputs"), dict) else {},
            "result": value,
            "tolerance": record.get("tolerance") or METHOD_TOLERANCES.get(method, 1e-6),
        },
    }


def _fact_from_numeric_observation(
    observation: Any,
    *,
    concept: str,
    source_ref: str | None,
    concept_index: int,
    observation_index: int,
    source_quality: str,
    warnings: set[str],
) -> dict[str, Any] | None:
    if not isinstance(observation, dict):
        warnings.add("invalid_numeric_observation_dropped")
        return None
    value = _finite_number(observation.get("value"))
    if value is None:
        warnings.add("invalid_numeric_value")
        warnings.add("invalid_numeric_observation_dropped")
        return None
    provenance = "extracted_high" if source_quality in {"clean", "synthetic"} and observation.get("confidence") == "high" else "unverified"
    return {
        "id": observation.get("id") or f"synthetic.observation.{concept_index:04d}.{observation_index:04d}",
        "concept": concept,
        "label": observation.get("label") or f"synthetic_observation_{concept_index:04d}_{observation_index:04d}",
        "value": value,
        "type": "numeric",
        "provenance": provenance,
        "verification_status": "unverified",
        "confidence": observation.get("confidence") if observation.get("confidence") in SAFE_CONFIDENCE else "medium",
        "source_ref": observation.get("source_ref") or source_ref,
        "computation": None,
    }


def _bundle(
    *,
    lecture_id: str,
    source_quality: str,
    concepts: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": BUNDLE_KIND,
        "lecture_id": lecture_id,
        "source_quality": source_quality,
        "concepts": concepts,
        "warnings": _ordered(warnings),
    }


def _result(
    *,
    status: str,
    fact_sheet: dict[str, Any],
    concept_count: int,
    computation_record_count: int,
    numeric_observation_count: int,
    produced_fact_count: int,
    dropped_item_count: int,
    warnings: set[str],
) -> dict[str, Any]:
    ordered = _ordered(warnings)
    return {
        "version": VERSION,
        "kind": RESULT_KIND,
        "status": status if status in {"completed", "warning", "failed", "skipped", "partial"} else "warning",
        "fact_sheet": fact_sheet,
        "summary": {
            "concept_count": max(0, int(concept_count)),
            "computation_record_count": max(0, int(computation_record_count)),
            "numeric_observation_count": max(0, int(numeric_observation_count)),
            "produced_fact_count": max(0, int(produced_fact_count)),
            "dropped_item_count": max(0, int(dropped_item_count)),
            "warning_count": len(ordered),
        },
        "warnings": ordered,
    }


def _producer_status(*, input_was_mapping: bool, warnings: set[str], produced_fact_count: int) -> str:
    if not input_was_mapping:
        return "skipped"
    if "max_items_reached" in warnings:
        return "partial"
    if produced_fact_count == 0 and "malformed_extraction_bundle_degraded" in warnings:
        return "skipped"
    if warnings:
        return "warning"
    return "completed"


def _safe_id(value: Any, default: str, warnings: set[str], warning_token: str) -> str:
    if not isinstance(value, str):
        if value is not None:
            warnings.add(warning_token)
        return default
    stripped = value.strip().lower()
    if _unsafe_string(stripped):
        warnings.add(warning_token)
        warnings.add("unsafe_string_sanitized")
        return default
    normalized = re.sub(r"\s+", "_", stripped)
    normalized = re.sub(r"[^a-z0-9._-]+", "_", normalized).strip("._-")
    normalized = re.sub(r"[._-]{2,}", "_", normalized)[:80]
    if not _SAFE_ID_RE.fullmatch(normalized):
        warnings.add(warning_token)
        return default
    return normalized


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


def _safe_text(value: Any, default: str) -> tuple[str, bool]:
    if not isinstance(value, str):
        return default, value is None
    text = " ".join(value.strip().split())
    if not text or _unsafe_string(text):
        return default, False
    return text[:120].rstrip(), True


def _safe_label(value: Any, default: str, warnings: set[str]) -> str:
    if not isinstance(value, str):
        return default
    if _unsafe_string(value):
        warnings.add("unsafe_string_sanitized")
        return default
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value.strip()).strip("_.:-")
    if not cleaned or not _SAFE_LABEL_RE.fullmatch(cleaned[:80]):
        warnings.add("unsafe_string_sanitized")
        return default
    return cleaned[:80]


def _safe_source_ref(value: Any, warnings: set[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        warnings.add("invalid_source_ref")
        return None
    candidate = value.strip().lower()
    if _unsafe_string(candidate) or not _SAFE_SOURCE_REF_RE.fullmatch(candidate):
        warnings.add("invalid_source_ref")
        if isinstance(value, str) and _unsafe_string(value):
            warnings.add("unsafe_string_sanitized")
        return None
    return candidate


def _safe_method(value: Any, warnings: set[str]) -> str:
    if not isinstance(value, str):
        warnings.add("invalid_computation_method")
        return "unknown"
    method = value.strip().lower()
    if method not in COMPUTATION_METHODS:
        warnings.add("invalid_computation_method")
        return "unknown"
    return method


def _safe_confidence(value: Any, *, default: str) -> str:
    if not isinstance(value, str):
        return default
    candidate = value.strip().lower()
    return candidate if candidate in SAFE_CONFIDENCE else default


def _safe_status(value: Any) -> str:
    if not isinstance(value, str):
        return "unverified"
    candidate = value.strip().lower()
    return candidate if candidate in SAFE_VERIFICATION_STATUSES else "unverified"


def _safe_tolerance(value: Any, method: str) -> float:
    number = _finite_number(value)
    if number is not None and 0.0 < float(number) <= 1.0:
        return float(number)
    return float(METHOD_TOLERANCES.get(method, 1e-6))


def _safe_mapping(value: Any, *, max_items: int) -> tuple[dict[str, Any], bool]:
    if not isinstance(value, dict):
        return {}, False
    out: dict[str, Any] = {}
    safe = True
    for index, (key, item) in enumerate(value.items()):
        if index >= max_items:
            safe = False
            break
        key_text = key.strip().lower() if isinstance(key, str) else ""
        key_text = re.sub(r"[^a-z0-9._-]+", "_", key_text).strip("._-")
        if not key_text or _unsafe_string(key_text) or not _SAFE_KEY_RE.fullmatch(key_text):
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
        text, safe = _safe_text(value, "sanitized_value")
        return text, safe
    if isinstance(value, list):
        out = []
        safe = True
        for index, item in enumerate(value):
            if index >= max_items:
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
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                safe = False
                break
            key_text = key.strip().lower() if isinstance(key, str) else ""
            key_text = re.sub(r"[^a-z0-9._-]+", "_", key_text).strip("._-")
            if not key_text or _unsafe_string(key_text) or not _SAFE_KEY_RE.fullmatch(key_text):
                safe = False
                continue
            safe_item, item_safe = _safe_json_value(item, depth=depth + 1, max_items=max_items)
            if not item_safe:
                safe = False
            out[key_text] = safe_item
        return out, safe
    return None, False


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


def _ordered(values: set[str]) -> list[str]:
    return [token for token in WARNING_ORDER if token in values]
