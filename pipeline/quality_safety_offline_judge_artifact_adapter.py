"""Pure advisory offline judge artifact schema adapter (Slice 147) — synthetic only.

This module adapts a **normalized offline judge report** (the Slice 142 schema /
Slice 143 core shape) into a *write-ready* synthetic artifact payload for the
proposed future advisory artifact ``quality_safety_offline_judge_report.json``
(kind ``quality_safety_offline_judge_report``), as designed in
``docs/QUALITY_SAFETY_ADVISORY_OFFLINE_JUDGE_ARTIFACT_DESIGN.md``.

It is **pure and unwired**. It is *not* production artifact writing and *not*
judge execution:

- It does not write the artifact or any file.
- It does not know job paths and does not inspect the filesystem.
- It does not read ``clean.md`` or any source/guide/reference text.
- It does not call providers/models/cloud/local LLMs.
- It does not wire judge reports into job artifacts or expose them in the UI.

The adapter only verifies/normalizes the *shape*. Conservative readiness is
enforced by construction: ``artifact_write_ready``, ``ui_display_ready``,
``judge_ready`` and ``repair_ready`` are **always** ``False`` in this slice.
``artifact_shape_ready`` may be ``True`` only for a valid, genuine normalized
report. The artifact_payload is rebuilt strictly through the Slice 142 schema
normalizer, so forbidden content (source/guide/OCR/table/caption text, evidence
quotes, filenames, paths, URLs, provider payloads, model prompts/responses,
private rationales, chain-of-thought, ``nn3.json`` / ``judge_response_nn3.json``
/ ``quality.jsonl`` dumps, etc.) cannot survive into the payload by construction.
The deterministic safety floor remains the source of truth: a floor-red input can
never be marked ``ok``, write-ready, or display-ready, and the adapter can never
mark anything shippable or override the floor/recompute/leak decisions.
"""
from __future__ import annotations

import json
from typing import Any

from pipeline.quality_safety_offline_judge_core import run_synthetic_offline_judge_case
from pipeline.quality_safety_offline_judge_schema import (
    BLOCKER_ORDER,
    BLOCKER_TOKENS,
    CALIBRATION_STATUSES,
    DETERMINISTIC_FLOOR_STATUSES,
    FORBIDDEN_FIELDS,
    KIND,
    PRIVACY_STATUSES,
    build_empty_offline_judge_report,
    normalize_offline_judge_report,
    validate_offline_judge_report,
)

ADAPTER_RESULT_VERSION = 1
ADAPTER_RESULT_KIND = "quality_safety_offline_judge_artifact_adapter_result"

# Proposed future artifact identity (matches the Slice 142 schema / design doc).
ARTIFACT_NAME = "quality_safety_offline_judge_report.json"
ARTIFACT_KIND = KIND  # "quality_safety_offline_judge_report"

ADAPTER_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})

# Closed adapter-level warning vocabulary. Only these tokens may appear in an
# adapter result's ``warnings`` list; everything else is dropped by construction.
ADAPTER_WARNING_ORDER = (
    "component_missing",
    "malformed_report_input",
    "wrong_kind",
    "schema_invalid",
    "forbidden_field_stripped",
    "calibration_record_stripped",
    "operator_validated_not_allowed_yet",
)
ADAPTER_WARNING_TOKENS = frozenset(ADAPTER_WARNING_ORDER)

# A calibration_record, if supplied, must be closed-vocabulary only: a small
# whitelist of keys, each mapping to a closed enum value. Anything else is
# stripped (the record never enables write/display readiness in this slice).
ALLOWED_CALIBRATION_RECORD_KEYS = frozenset(
    {
        "calibration_status",
        "privacy_status",
        "deterministic_floor_status",
        "private_operator_judge_calibration_run",
    }
)
ALLOWED_PRIVATE_RUN_VALUES = frozenset({"not_run", "pending", "blocked"})

SYNTHETIC_ARTIFACT_CASE_IDS = (
    "clean_synthetic_judge_case",
    "weak_synthetic_judge_case",
    "failed_synthetic_judge_case",
    "leak_canary_synthetic_judge_case",
    "deterministic_floor_red_synthetic_judge_case",
    "malformed_report_case",
)

_MAX_DEPTH = 6
_UNSAFE_MARKERS = (
    "/home/",
    "/mnt/",
    "/tmp/",
    "/var/",
    "http://",
    "https://",
    ".pdf",
    ".docx",
    ".zip",
    ".png",
    ".jpg",
    "bearer",
    "authorization",
    "api_key",
    "api-key",
    "secret",
    "data:",
    "base64",
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_empty_offline_judge_artifact_adapter_result(
    reason: str = "component_missing",
) -> dict[str, Any]:
    """Return a safe, skipped, never-ready adapter result with a closed warning."""
    token = reason if isinstance(reason, str) and reason in ADAPTER_WARNING_TOKENS else "component_missing"
    payload_reason = token if token in {"component_missing", "malformed_report_input"} else "component_missing"
    payload = build_empty_offline_judge_report(payload_reason)
    return _result(
        status="skipped",
        payload=payload,
        warnings={token},
        forbidden_field_count=0,
        shape_ready=False,
    )


def adapt_offline_judge_report_to_artifact_payload(
    report: Any,
    *,
    calibration_record: Any = None,
    deterministic_floor_payload: Any = None,
) -> dict[str, Any]:
    """Adapt a normalized offline judge report into a write-ready artifact payload.

    Pure and deterministic; never raises, never mutates its caller input. Returns
    the closed adapter-result shape with the sanitized Slice 142 report under
    ``artifact_payload``. ``artifact_write_ready`` / ``ui_display_ready`` /
    ``judge_ready`` / ``repair_ready`` are always ``False``.
    """
    try:
        return _adapt(
            report,
            calibration_record=calibration_record,
            deterministic_floor_payload=deterministic_floor_payload,
        )
    except Exception:
        return build_empty_offline_judge_artifact_adapter_result("malformed_report_input")


def validate_offline_judge_artifact_payload(payload: Any) -> dict[str, Any]:
    """Validate the artifact payload (a Slice 142 report) against the contract.

    Accepts either an adapter result (validates its ``artifact_payload``) or a
    bare report. Returns ``{"valid": bool, "violations": [closed tokens]}`` only.
    """
    if isinstance(payload, dict) and payload.get("kind") == ADAPTER_RESULT_KIND:
        report = payload.get("artifact_payload")
    else:
        report = payload
    result = validate_offline_judge_report(report)
    violations = list(result.get("violations", []))
    if not (isinstance(report, dict) and report.get("kind") == ARTIFACT_KIND):
        if "bad_kind" not in violations:
            violations.append("bad_artifact_kind")
    return {"valid": result.get("valid", False) and not violations, "violations": sorted(set(violations))}


def serialize_offline_judge_artifact_payload(payload: Any) -> str:
    """Deterministically serialize an adapter result / artifact payload to JSON."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_synthetic_offline_judge_artifact_case(case_id: Any) -> Any:
    """Return a synthetic *input report* for a named adapter case (synthetic only).

    The returned value is pre-adaptation input intended to be fed through
    :func:`adapt_offline_judge_report_to_artifact_payload`. The leak case carries
    synthetic canaries under forbidden field keys to prove stripping; the
    malformed case carries a wrong ``kind``. No real/private material is used.
    """
    builder = _SYNTHETIC_CASES.get(case_id if isinstance(case_id, str) else "")
    if builder is None:
        return None
    return builder()


def run_synthetic_offline_judge_artifact_case(case_id: Any) -> dict[str, Any]:
    """Build the synthetic input report for ``case_id`` and run the adapter."""
    report = build_synthetic_offline_judge_artifact_case(case_id)
    floor_payload = (
        {"safety_floor_green": False}
        if case_id == "deterministic_floor_red_synthetic_judge_case"
        else None
    )
    calibration_record = {
        "calibration_status": "synthetic_only",
        "private_operator_judge_calibration_run": "not_run",
    }
    return adapt_offline_judge_report_to_artifact_payload(
        report,
        calibration_record=calibration_record,
        deterministic_floor_payload=floor_payload,
    )


# --------------------------------------------------------------------------- #
# Adaptation internals
# --------------------------------------------------------------------------- #
def _adapt(
    report: Any,
    *,
    calibration_record: Any,
    deterministic_floor_payload: Any,
) -> dict[str, Any]:
    if report is None:
        return build_empty_offline_judge_artifact_adapter_result("component_missing")
    if not isinstance(report, dict):
        return build_empty_offline_judge_artifact_adapter_result("malformed_report_input")

    warnings: set[str] = set()

    forbidden_field_count = _count_forbidden_fields(report)
    if forbidden_field_count or _contains_unsafe_string(report, depth=0):
        warnings.add("forbidden_field_stripped")

    if calibration_record is not None and not _calibration_record_is_closed(calibration_record):
        warnings.add("calibration_record_stripped")
    if _asks_operator_validated(report) or _asks_operator_validated(calibration_record):
        warnings.add("operator_validated_not_allowed_yet")

    wrong_kind = report.get("kind") != KIND
    if wrong_kind:
        warnings.add("wrong_kind")

    # Rebuild the payload strictly through the Slice 142 normalizer. This strips
    # all forbidden content and forces judge_ready / repair_ready to False.
    payload = normalize_offline_judge_report(
        report, deterministic_floor_payload=deterministic_floor_payload
    )

    valid = bool(validate_offline_judge_report(payload).get("valid"))
    if not valid:
        warnings.add("schema_invalid")

    floor_red = "deterministic_floor_red" in payload.get("blockers", [])

    # Shape-ready only for a valid, genuine (right-kind) normalized report. The
    # wrong-kind placeholder is itself schema-valid, so it is gated out here.
    shape_ready = valid and not wrong_kind

    status = _adapter_status(
        wrong_kind=wrong_kind, valid=valid, payload=payload, floor_red=floor_red
    )

    return _result(
        status=status,
        payload=payload,
        warnings=warnings,
        forbidden_field_count=forbidden_field_count,
        shape_ready=shape_ready,
    )


def _adapter_status(
    *,
    wrong_kind: bool,
    valid: bool,
    payload: dict[str, Any],
    floor_red: bool,
) -> str:
    if wrong_kind or not valid:
        return "failed"
    if floor_red:
        # Floor red can never be ok / write-ready / display-ready.
        return "failed"
    payload_status = payload.get("status")
    if payload_status in ADAPTER_STATUSES:
        if payload_status == "skipped":
            return "partial"
        return payload_status
    return "partial"


def _result(
    *,
    status: str,
    payload: Any,
    warnings: set[str],
    forbidden_field_count: int,
    shape_ready: bool,
) -> dict[str, Any]:
    safe_payload = payload if isinstance(payload, dict) else build_empty_offline_judge_report(
        "malformed_report_input"
    )
    summary = safe_payload.get("summary", {})
    axis_count = summary.get("axis_count", 0) if isinstance(summary, dict) else 0
    blocker_count = summary.get("blocker_count", 0) if isinstance(summary, dict) else 0
    payload_warning_count = len(safe_payload.get("warnings", []))
    blockers = _ordered(set(safe_payload.get("blockers", [])) & BLOCKER_TOKENS, BLOCKER_ORDER)
    calibration_status = safe_payload.get("calibration_status", "not_started")
    if calibration_status not in CALIBRATION_STATUSES or calibration_status == "operator_validated":
        calibration_status = "not_started"

    return {
        "version": ADAPTER_RESULT_VERSION,
        "kind": ADAPTER_RESULT_KIND,
        "status": status if status in ADAPTER_STATUSES else "failed",
        "artifact_name": ARTIFACT_NAME,
        "artifact_kind": ARTIFACT_KIND,
        "artifact_payload": safe_payload,
        "summary": {
            "axis_count": _nn(axis_count),
            "blocker_count": _nn(blocker_count),
            "warning_count": _nn(payload_warning_count),
            "forbidden_field_count": _nn(forbidden_field_count),
        },
        "blockers": blockers,
        "calibration_status": calibration_status,
        "private_operator_judge_calibration_run": "not_run",
        "artifact_shape_ready": bool(shape_ready),
        "artifact_write_ready": False,
        "ui_display_ready": False,
        "judge_ready": False,
        "repair_ready": False,
        "warnings": _ordered(warnings & ADAPTER_WARNING_TOKENS, ADAPTER_WARNING_ORDER),
    }


# --------------------------------------------------------------------------- #
# Small pure helpers
# --------------------------------------------------------------------------- #
def _nn(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _ordered(tokens: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in tokens]


def _asks_operator_validated(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    value = obj.get("calibration_status")
    return isinstance(value, str) and value.strip().lower() == "operator_validated"


def _calibration_record_is_closed(record: Any) -> bool:
    if record is None:
        return True
    if not isinstance(record, dict):
        return False
    if _count_forbidden_fields(record) or _contains_unsafe_string(record, depth=0):
        return False
    for key, value in record.items():
        if key not in ALLOWED_CALIBRATION_RECORD_KEYS or not isinstance(value, str):
            return False
        token = value.strip().lower()
        if key == "calibration_status" and token not in CALIBRATION_STATUSES:
            return False
        if key == "privacy_status" and token not in PRIVACY_STATUSES:
            return False
        if key == "deterministic_floor_status" and token not in DETERMINISTIC_FLOOR_STATUSES:
            return False
        if key == "private_operator_judge_calibration_run" and token not in ALLOWED_PRIVATE_RUN_VALUES:
            return False
    return True


def _count_forbidden_fields(obj: Any, depth: int = 0) -> int:
    if depth > _MAX_DEPTH:
        return 0
    total = 0
    if isinstance(obj, dict):
        total += sum(1 for key in obj if key in FORBIDDEN_FIELDS)
        for value in obj.values():
            total += _count_forbidden_fields(value, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            total += _count_forbidden_fields(item, depth + 1)
    return total


def _contains_unsafe_string(obj: Any, *, depth: int) -> bool:
    if depth > _MAX_DEPTH:
        return False
    if isinstance(obj, str):
        lowered = obj.lower()
        return any(marker in lowered for marker in _UNSAFE_MARKERS)
    if isinstance(obj, dict):
        return any(_contains_unsafe_string(v, depth=depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_unsafe_string(item, depth=depth + 1) for item in obj)
    return False


# --------------------------------------------------------------------------- #
# Synthetic adapter cases (synthetic data + synthetic canaries only)
# --------------------------------------------------------------------------- #
def _clean_case() -> dict[str, Any]:
    return run_synthetic_offline_judge_case("clean_synthetic_judge_case")


def _weak_case() -> dict[str, Any]:
    return run_synthetic_offline_judge_case("weak_synthetic_judge_case")


def _failed_case() -> dict[str, Any]:
    return run_synthetic_offline_judge_case("failed_synthetic_judge_case")


def _floor_red_case() -> dict[str, Any]:
    return run_synthetic_offline_judge_case("deterministic_floor_red_synthetic_judge_case")


def _leak_case() -> dict[str, Any]:
    # Start from a sanitized core leak report, then inject synthetic canaries under
    # forbidden field keys (top-level and axis-level) to prove the adapter strips
    # them. The injected dict is a fresh copy; the core's output is not mutated.
    base = run_synthetic_offline_judge_case("leak_canary_synthetic_judge_case")
    injected: dict[str, Any] = dict(base)
    injected.update(
        {
            "raw_text": "RAW_TEXT_SYNTHETIC_ADAPTER_MARKER",
            "source_text": "SOURCE_TEXT_SYNTHETIC_ADAPTER_MARKER",
            "guide_text": "ZZSYNTH_ADAPTER_PRIVATE_MARKER_ONLY",
            "ocr_text": "OCR_TEXT_SYNTHETIC_ADAPTER_MARKER",
            "page_text": "PAGE_TEXT_SYNTHETIC_ADAPTER_MARKER",
            "table_cells": ["TABLE_CELL_SYNTHETIC_ADAPTER_MARKER"],
            "captions": "CAPTION_SYNTHETIC_ADAPTER_MARKER",
            "formulas_as_text": "E=mc^2_synthetic_adapter_marker",
            "evidence_quotes": "EVIDENCE_QUOTE_SYNTHETIC_ADAPTER_MARKER",
            "filenames": "UPLOADED_SYNTHETIC_ADAPTER_FILENAME",
            "basenames": "synthetic-adapter-source.pdf",
            "paths": "/home/fake_private/synthetic-adapter-source.pdf",
            "urls": "https://private.invalid/synthetic-adapter",
            "screenshots": "SCREENSHOT_SYNTHETIC_ADAPTER_MARKER",
            "raw_runtime_artifacts": "RAW_RUNTIME_SYNTHETIC_ADAPTER_MARKER",
            "raw_artifact_json": "RAW_ARTIFACT_JSON_SYNTHETIC_ADAPTER_MARKER",
            "provider_payloads": "PROVIDER_PAYLOAD_SYNTHETIC_ADAPTER_MARKER",
            "model_prompts": "MODEL_PROMPT_SYNTHETIC_ADAPTER_MARKER",
            "model_responses": "MODEL_RESPONSE_SYNTHETIC_ADAPTER_MARKER",
            "private_rationales": "PRIVATE_RATIONALE_SYNTHETIC_ADAPTER_MARKER",
            "free_text_rationales": "FREE_TEXT_RATIONALE_SYNTHETIC_ADAPTER_MARKER",
            "chain_of_thought": "CHAIN_OF_THOUGHT_SYNTHETIC_ADAPTER_MARKER",
            "quality_judge_dump": "QUALITY_JUDGE_DUMP_SYNTHETIC_ADAPTER_MARKER",
            "nn3_json": "NN3_JSON_SYNTHETIC_ADAPTER_MARKER",
            "judge_response_nn3_json": "JUDGE_RESPONSE_NN3_SYNTHETIC_ADAPTER_MARKER",
            "quality_jsonl": "QUALITY_JSONL_SYNTHETIC_ADAPTER_MARKER",
        }
    )
    axes = [dict(axis) for axis in injected.get("axis_results", [])]
    if axes:
        axes[0] = dict(axes[0])
        axes[0]["guide_text"] = "AXIS_GUIDE_TEXT_SYNTHETIC_ADAPTER_MARKER"
        axes[0]["evidence_quotes"] = "AXIS_EVIDENCE_SYNTHETIC_ADAPTER_MARKER"
        injected["axis_results"] = axes
    return injected


def _malformed_case() -> dict[str, Any]:
    # Wrong-kind input: the normalizer rejects it and the adapter degrades to a
    # failed, not-shape-ready result. The stray marker must not survive output.
    return {
        "version": 1,
        "kind": "not_a_judge_report",
        "advisory": True,
        "garbage_field": "MALFORMED_SYNTHETIC_ADAPTER_MARKER",
    }


_SYNTHETIC_CASES = {
    "clean_synthetic_judge_case": _clean_case,
    "weak_synthetic_judge_case": _weak_case,
    "failed_synthetic_judge_case": _failed_case,
    "leak_canary_synthetic_judge_case": _leak_case,
    "deterministic_floor_red_synthetic_judge_case": _floor_red_case,
    "malformed_report_case": _malformed_case,
}
