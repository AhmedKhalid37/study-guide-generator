"""Pure validator for operator-approved structured numeric exports (Slice 137).

Implements the Slice 136 Operator Structured Numeric Export Protocol gate: it
validates a caller-supplied ``quality_safety_structured_numeric_candidates``-like
dict (authored by an operator, or a synthetic fixture) *before* it is allowed to
feed the existing structured adapter → safe extractor → numeric mapper →
fact-sheet → recompute path.

This module is **pure and unwired**:

- imports only stdlib and the Slice 133 adapter (a sibling Quality Safety module);
- reads only caller-supplied dicts/lists — no files, job folders, ``clean.md``,
  source documents, OCR / page / table / caption text;
- writes no artifacts, calls no providers / models / cloud, and imports no
  FastAPI / frontend / render / OCR / job-runtime modules;
- never raises on malformed input and never mutates the caller's input.

It does not wire anything into production, does not validate real/private
sidecars, adds no judge, no repair, no blocking gate, and makes no claim that
production numeric extraction coverage is complete. The Slice 133 adapter remains
the per-candidate sanitizer and the Slice 125 numeric mapper remains the final
record sanitizer; this validator only gates protocol conformance and re-emits an
adapter-ready, forbidden-field-free structured payload of the accepted candidates.
"""
from __future__ import annotations

from typing import Any

from pipeline.quality_safety_structured_numeric_candidate_adapter import (
    FORBIDDEN_CANDIDATE_FIELDS,
    INPUT_KIND,
    SUPPORTED_METHODS,
    adapt_structured_numeric_candidates_to_safe_candidates,
)

VERSION = 1
INPUT_KIND_NAME = INPUT_KIND  # "quality_safety_structured_numeric_candidates"
OUTPUT_KIND = "quality_safety_operator_structured_numeric_export_validation"
STRUCTURED_PAYLOAD_KIND = INPUT_KIND

VALIDATION_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})

# Operator exports must declare an operator-authored or synthetic source. Anything
# else degrades to ``unknown`` (with a warning); the re-emitted structured payload
# then defaults to the safe non-operator label ``synthetic``.
ACCEPTED_SOURCE_QUALITIES = frozenset({"operator_approved", "synthetic"})

# Operator exports may only claim ``operator_approved`` or ``computed`` provenance
# per the Slice 136 protocol; any other (or missing) provenance is rejected.
ACCEPTED_PROVENANCE = frozenset({"operator_approved", "computed"})

VALIDATION_WARNING_ORDER = (
    "component_missing",
    "malformed_input",
    "invalid_kind",
    "invalid_source_quality",
    "candidates_missing",
    "no_candidates",
    "unsafe_field_excluded",
    "invalid_candidate_rejected",
    "invalid_numeric_value",
    "invalid_provenance",
    "invalid_computation",
    "unsupported_method",
    "max_items_reached",
)
VALIDATION_WARNINGS = frozenset(VALIDATION_WARNING_ORDER)

EMPTY_REASONS = frozenset(
    {"component_missing", "malformed_input", "invalid_kind", "candidates_missing", "no_candidates"}
)

_DEFAULT_MAX_ITEMS = 200


def build_empty_operator_structured_numeric_export_validation(
    reason: str = "component_missing",
) -> dict[str, Any]:
    """Return an empty, no-candidate operator export validation result.

    Used when no payload is supplied or the payload cannot form a validation
    (wrong kind, missing/empty candidates). ``reason`` is constrained to a closed
    token set; an unknown reason degrades to ``component_missing``.
    """
    token = reason if isinstance(reason, str) and reason in EMPTY_REASONS else "component_missing"
    status = "failed" if token in {"malformed_input", "invalid_kind"} else "skipped"
    return _result(
        status=status,
        source_quality="unknown",
        accepted=[],
        input_candidate_count=0,
        accepted_count=0,
        rejected_count=0,
        supported_method_count=0,
        unsupported_method_count=0,
        forbidden_field_count=0,
        warnings={token},
    )


def validate_operator_structured_numeric_export(
    payload: Any,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    """Validate an operator-approved structured numeric export.

    Returns a closed-vocabulary validation result carrying summary counts plus a
    sanitized, forbidden-field-free ``structured_numeric_payload`` of the accepted
    candidates (shaped as a ``quality_safety_structured_numeric_candidates`` dict)
    that the existing adapter/extractor/mapper/recompute path can consume directly.

    Never raises; never mutates the caller's input.
    """
    try:
        return _validate(payload, max_items=max_items)
    except Exception:
        return build_empty_operator_structured_numeric_export_validation("malformed_input")


def operator_export_validation_to_structured_numeric_payload(
    validation_result: Any,
) -> dict[str, Any]:
    """Extract the adapter-ready ``structured_numeric_payload`` from a result.

    Returns an empty structured payload when the result is missing or malformed, so
    callers can chain into the adapter unconditionally. Never raises.
    """
    if isinstance(validation_result, dict):
        payload = validation_result.get("structured_numeric_payload")
        if isinstance(payload, dict):
            return payload
    return _empty_structured_payload("synthetic")


# ── Validation driver ─────────────────────────────────────────────────────────


def _validate(payload: Any, *, max_items: Any) -> dict[str, Any]:
    if payload is None:
        return build_empty_operator_structured_numeric_export_validation("component_missing")
    if not isinstance(payload, dict):
        return build_empty_operator_structured_numeric_export_validation("malformed_input")
    if payload.get("kind") != INPUT_KIND_NAME:
        return build_empty_operator_structured_numeric_export_validation("invalid_kind")

    warnings: set[str] = set()
    source_quality = _validated_source_quality(payload.get("source_quality"), warnings)

    raw_candidates = payload.get("candidates")
    if raw_candidates is None:
        return _result(
            status="skipped",
            source_quality=source_quality,
            accepted=[],
            input_candidate_count=0,
            accepted_count=0,
            rejected_count=0,
            supported_method_count=0,
            unsupported_method_count=0,
            forbidden_field_count=0,
            warnings=warnings | {"candidates_missing"},
        )
    if not isinstance(raw_candidates, list):
        return _result(
            status="skipped",
            source_quality=source_quality,
            accepted=[],
            input_candidate_count=0,
            accepted_count=0,
            rejected_count=0,
            supported_method_count=0,
            unsupported_method_count=0,
            forbidden_field_count=0,
            warnings=warnings | {"malformed_input"},
        )
    if not raw_candidates:
        return _result(
            status="skipped",
            source_quality=source_quality,
            accepted=[],
            input_candidate_count=0,
            accepted_count=0,
            rejected_count=0,
            supported_method_count=0,
            unsupported_method_count=0,
            forbidden_field_count=0,
            warnings=warnings | {"no_candidates"},
        )

    cap = _cap(max_items)
    truncated = len(raw_candidates) > cap

    accepted: list[dict[str, Any]] = []
    supported_method_count = 0
    unsupported_method_count = 0
    rejected_count = 0
    forbidden_field_count = 0

    for index, raw in enumerate(raw_candidates[:cap]):
        outcome = _classify_candidate(raw, index=index, source_quality=source_quality)
        forbidden_field_count += outcome["forbidden_field_count"]
        for token in outcome["warnings"]:
            warnings.add(token)
        if outcome["accepted"]:
            accepted.append(outcome["candidate"])
            if outcome["supported"]:
                supported_method_count += 1
            else:
                unsupported_method_count += 1
        else:
            rejected_count += 1

    if truncated:
        warnings.add("max_items_reached")

    accepted_count = len(accepted)
    status = _status(
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        truncated=truncated,
        warnings=warnings,
    )
    return _result(
        status=status,
        source_quality=source_quality,
        accepted=accepted,
        input_candidate_count=len(raw_candidates),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        supported_method_count=supported_method_count,
        unsupported_method_count=unsupported_method_count,
        forbidden_field_count=forbidden_field_count,
        warnings=warnings,
    )


def _classify_candidate(raw: Any, *, index: int, source_quality: str) -> dict[str, Any]:
    """Classify one raw candidate; return acceptance + a sanitized body if kept.

    The sanitized body is produced exclusively by the Slice 133 adapter, so the
    re-emitted candidate carries only whitelisted, sanitized fields and can never
    leak a forbidden field value. Acceptance applies the stricter Slice 136 gate
    (numeric fact_type, finite value, operator/computed provenance, a recomputable
    or at-least-structured computation) on top of that sanitization.
    """
    out_warnings: set[str] = set()
    forbidden_field_count = 0

    if not isinstance(raw, dict):
        return _reject({"invalid_candidate_rejected"}, forbidden_field_count=0)

    forbidden_field_count = sum(1 for key in FORBIDDEN_CANDIDATE_FIELDS if key in raw)
    if forbidden_field_count:
        out_warnings.add("unsafe_field_excluded")

    if raw.get("fact_type") != "numeric":
        return _reject(out_warnings | {"invalid_candidate_rejected"}, forbidden_field_count=forbidden_field_count)

    if not _is_finite_number(raw.get("value")):
        return _reject(out_warnings | {"invalid_numeric_value"}, forbidden_field_count=forbidden_field_count)

    provenance = raw.get("provenance")
    if not (isinstance(provenance, str) and provenance.strip().lower() in ACCEPTED_PROVENANCE):
        return _reject(out_warnings | {"invalid_provenance"}, forbidden_field_count=forbidden_field_count)

    computation = raw.get("computation")
    if not isinstance(computation, dict) or not isinstance(computation.get("method"), str):
        return _reject(out_warnings | {"invalid_computation"}, forbidden_field_count=forbidden_field_count)

    # Sanitize the candidate body through the Slice 133 adapter (single-item run).
    # The adapter strips forbidden fields, sanitizes strings, and resolves the
    # computation; a sanitized computation of ``None`` means the inputs/method were
    # not numeric-safe, which the gate treats as an invalid computation.
    sanitized = _adapt_single(raw, source_quality=source_quality)
    if sanitized is None:
        return _reject(out_warnings | {"invalid_computation"}, forbidden_field_count=forbidden_field_count)

    sani_comp = sanitized.get("computation")
    if not isinstance(sani_comp, dict) or not isinstance(sani_comp.get("method"), str):
        return _reject(out_warnings | {"invalid_computation"}, forbidden_field_count=forbidden_field_count)

    method = sani_comp.get("method")
    supported = method in SUPPORTED_METHODS
    if not supported:
        # Degrade: keep the structurally valid candidate so downstream recompute
        # honestly reports it as unverified/partial, but it is never promoted to a
        # recomputable (supported) method.
        out_warnings.add("unsupported_method")

    return {
        "accepted": True,
        "supported": supported,
        "candidate": sanitized,
        "warnings": out_warnings,
        "forbidden_field_count": forbidden_field_count,
    }


def _reject(warnings: set[str], *, forbidden_field_count: int) -> dict[str, Any]:
    return {
        "accepted": False,
        "supported": False,
        "candidate": None,
        "warnings": set(warnings),
        "forbidden_field_count": forbidden_field_count,
    }


def _adapt_single(raw: dict[str, Any], *, source_quality: str) -> dict[str, Any] | None:
    """Sanitize a single candidate via the Slice 133 adapter; return body or None."""
    quality = source_quality if source_quality in ACCEPTED_SOURCE_QUALITIES else "synthetic"
    adapted = adapt_structured_numeric_candidates_to_safe_candidates(
        {"version": VERSION, "kind": INPUT_KIND_NAME, "source_quality": quality, "candidates": [raw]}
    )
    candidates = adapted.get("candidates") if isinstance(adapted, dict) else None
    if isinstance(candidates, list) and len(candidates) == 1 and isinstance(candidates[0], dict):
        return candidates[0]
    return None


# ── Result assembly ─────────────────────────────────────────────────────────


def _validated_source_quality(value: Any, warnings: set[str]) -> str:
    if isinstance(value, str) and value.strip().lower() in ACCEPTED_SOURCE_QUALITIES:
        return value.strip().lower()
    warnings.add("invalid_source_quality")
    return "unknown"


def _status(
    *,
    accepted_count: int,
    rejected_count: int,
    truncated: bool,
    warnings: set[str],
) -> str:
    if accepted_count == 0:
        return "failed" if rejected_count > 0 else "skipped"
    if rejected_count > 0 or truncated:
        return "partial"
    if warnings:
        return "warning"
    return "ok"


def _result(
    *,
    status: str,
    source_quality: str,
    accepted: list[dict[str, Any]],
    input_candidate_count: int,
    accepted_count: int,
    rejected_count: int,
    supported_method_count: int,
    unsupported_method_count: int,
    forbidden_field_count: int,
    warnings: set[str],
) -> dict[str, Any]:
    safe_input = max(0, input_candidate_count)
    payload_quality = source_quality if source_quality in ACCEPTED_SOURCE_QUALITIES else "synthetic"
    return {
        "version": VERSION,
        "kind": OUTPUT_KIND,
        "status": status if status in VALIDATION_STATUSES else "warning",
        "source_quality": source_quality if source_quality in (ACCEPTED_SOURCE_QUALITIES | {"unknown"}) else "unknown",
        "summary": {
            "input_candidate_count": safe_input,
            "accepted_candidate_count": max(0, accepted_count),
            "rejected_candidate_count": max(0, rejected_count),
            "supported_method_count": max(0, supported_method_count),
            "unsupported_method_count": max(0, unsupported_method_count),
            "forbidden_field_count": max(0, forbidden_field_count),
        },
        "structured_numeric_payload": {
            "version": VERSION,
            "kind": STRUCTURED_PAYLOAD_KIND,
            "source_quality": payload_quality,
            "candidates": accepted,
        },
        "warnings": _ordered(warnings, VALIDATION_WARNING_ORDER),
    }


def _empty_structured_payload(source_quality: str) -> dict[str, Any]:
    quality = source_quality if source_quality in ACCEPTED_SOURCE_QUALITIES else "synthetic"
    return {
        "version": VERSION,
        "kind": STRUCTURED_PAYLOAD_KIND,
        "source_quality": quality,
        "candidates": [],
    }


def _ordered(warnings: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in warnings]


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value == value and value not in (float("inf"), float("-inf"))
    return False


def _cap(max_items: Any) -> int:
    if isinstance(max_items, int) and not isinstance(max_items, bool):
        return max(0, min(max_items, _DEFAULT_MAX_ITEMS))
    return _DEFAULT_MAX_ITEMS
