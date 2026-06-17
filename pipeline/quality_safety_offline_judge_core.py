"""Pure offline judge core v1 (Slice 143) — synthetic / caller-supplied only.

This module converts **caller-supplied closed observations** (synthetic, in this
slice) into the Slice 142 offline judge report shape
(`pipeline/quality_safety_offline_judge_schema.py`) using **deterministic rules
only**. It is *not* an LLM judge and *not* production wiring:

- It does not read real guide/source/reference text.
- It does not call providers/models/cloud/local LLMs.
- It does not read or write files.
- It does not score real guides or inspect job artifacts.

Every report it returns is passed through the Slice 142 schema normalizer before
return, so it is sanitized by construction: forbidden content cannot survive,
``advisory`` is forced ``True``, and ``judge_ready`` / ``repair_ready`` always
normalize to ``False``. The deterministic safety floor stays the source of truth:
a ``deterministic_floor_payload`` indicating ``blocked`` yields a
``deterministic_floor_red`` blocker and a non-``ok`` status that this core can
never override. The core cannot mark anything shippable or operator-validated.
"""
from __future__ import annotations

from typing import Any

from pipeline.quality_safety_offline_judge_schema import (
    ALLOWED_AXES,
    ALLOWED_AXIS_SET,
    AXIS_WARNING_TOKENS,
    BLOCKER_TOKENS,
    CALIBRATION_STATUSES,
    CONFIDENCE_VALUES,
    FORBIDDEN_FIELDS,
    INPUT_SCOPES,
    JUDGE_MODEL_KINDS,
    KIND,
    PRIVACY_STATUSES,
    WARNING_TOKENS,
    build_empty_offline_judge_report,
    normalize_offline_judge_report,
)

# Closed signal-count keys accepted on an axis observation's ``signals`` block.
SIGNAL_KEYS = (
    "pass_count",
    "warning_count",
    "fail_count",
    "not_observed_count",
)
SIGNAL_KEY_SET = frozenset(SIGNAL_KEYS)

# Content warnings the core may derive deterministically and surface at axis and
# report level (all members of the Slice 142 closed vocabularies).
_DERIVED_CONTENT_WARNINGS = frozenset(
    {"low_confidence", "weak_band", "not_observed_axis", "leak_canary_observed", "privacy_concern"}
)

_MAX_AXIS_OBSERVATIONS = 64
_MAX_TOKENS = 64
_MAX_DEPTH = 6


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_empty_offline_judge_core_result(reason: str = "component_missing") -> dict[str, Any]:
    """Return a safe, skipped, advisory-only empty report (delegates to schema)."""
    return build_empty_offline_judge_report(reason)


def normalize_offline_judge_observations(observations: Any) -> dict[str, Any]:
    """Sanitize arbitrary observations into a closed-vocabulary observation dict.

    Never raises and never mutates its caller input. Unknown axes are dropped,
    forbidden fields are detected (and never copied), and all enums/tokens are
    constrained to the Slice 142 closed vocabularies.
    """
    try:
        return _normalize_observations(observations)
    except Exception:
        return _empty_observations("malformed_observations")


def build_offline_judge_report_from_observations(
    observations: Any,
    *,
    deterministic_floor_payload: Any = None,
) -> dict[str, Any]:
    """Convert closed observations into a normalized Slice 142 judge report.

    Deterministic and pure. The result is always passed through the Slice 142
    schema normalizer, so ``judge_ready`` / ``repair_ready`` are forced ``False``
    and the report is sanitized by construction. A floor-red
    ``deterministic_floor_payload`` can never be overridden by the observations.
    """
    try:
        norm = _normalize_observations(observations)
    except Exception:
        return build_empty_offline_judge_report("malformed_observations")

    if not norm["axis_observations"] and not norm["derived_warnings"]:
        # Nothing observable — degrade to a safe skipped report, but still honor
        # a floor-red payload via the schema normalizer below.
        payload = _schema_payload(norm, axis_results=[])
        return normalize_offline_judge_report(
            payload, deterministic_floor_payload=deterministic_floor_payload
        )

    axis_results = [_axis_result_from_observation(obs) for obs in norm["axis_observations"]]
    payload = _schema_payload(norm, axis_results=axis_results)
    return normalize_offline_judge_report(
        payload, deterministic_floor_payload=deterministic_floor_payload
    )


def build_synthetic_offline_judge_observations(case_id: Any) -> dict[str, Any]:
    """Return synthetic *observation* input for a named case (synthetic only)."""
    builder = _SYNTHETIC_CASES.get(case_id if isinstance(case_id, str) else "")
    if builder is None:
        return _empty_observations("component_missing")
    return builder()


def run_synthetic_offline_judge_case(case_id: Any) -> dict[str, Any]:
    """Build synthetic observations for ``case_id`` and run the core over them."""
    observations = build_synthetic_offline_judge_observations(case_id)
    floor_payload = _synthetic_floor_payload(case_id)
    return build_offline_judge_report_from_observations(
        observations, deterministic_floor_payload=floor_payload
    )


SYNTHETIC_CASE_IDS = (
    "clean_synthetic_judge_case",
    "weak_synthetic_judge_case",
    "failed_synthetic_judge_case",
    "leak_canary_synthetic_judge_case",
    "deterministic_floor_red_synthetic_judge_case",
)


# --------------------------------------------------------------------------- #
# Observation normalization
# --------------------------------------------------------------------------- #
def _empty_observations(*derived: str) -> dict[str, Any]:
    return {
        "judge_model_kind": "synthetic",
        "input_scope": "synthetic",
        "calibration_status": "synthetic_only",
        "privacy_status": "unknown",
        "axis_observations": [],
        "blockers": [],
        "warnings": [],
        "derived_warnings": sorted({d for d in derived if d in WARNING_TOKENS}),
    }


def _normalize_observations(observations: Any) -> dict[str, Any]:
    if not isinstance(observations, dict):
        return _empty_observations("malformed_observations")

    derived: set[str] = set()
    if _contains_forbidden_field(observations) or _contains_unsafe_string(observations, depth=0):
        derived.add("forbidden_field_stripped")

    judge_model_kind = _enum(observations.get("judge_model_kind"), JUDGE_MODEL_KINDS, "synthetic")
    input_scope = _enum(observations.get("input_scope"), INPUT_SCOPES, "synthetic")
    calibration_status = _calibration(observations.get("calibration_status"))
    privacy_status = _enum(observations.get("privacy_status"), PRIVACY_STATUSES, "unknown")

    axis_observations = _normalize_axis_observations(observations.get("axis_observations"), derived)

    return {
        "judge_model_kind": judge_model_kind,
        "input_scope": input_scope,
        "calibration_status": calibration_status,
        "privacy_status": privacy_status,
        "axis_observations": axis_observations,
        "blockers": sorted(_filter_tokens(observations.get("blockers"), BLOCKER_TOKENS)),
        "warnings": sorted(_filter_tokens(observations.get("warnings"), WARNING_TOKENS)),
        "derived_warnings": sorted(derived & WARNING_TOKENS),
    }


def _normalize_axis_observations(raw: Any, derived: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in raw[:_MAX_AXIS_OBSERVATIONS]:
        if not isinstance(entry, dict):
            continue
        axis = entry.get("axis")
        if not isinstance(axis, str) or axis.strip().lower() not in ALLOWED_AXIS_SET:
            continue
        axis = axis.strip().lower()
        if axis in seen:
            continue
        seen.add(axis)
        if _contains_forbidden_field(entry) or _contains_unsafe_string(entry, depth=0):
            derived.add("forbidden_field_stripped")
        out.append(_normalize_axis_observation(axis, entry))
    return out


def _normalize_axis_observation(axis: str, entry: dict[str, Any]) -> dict[str, Any]:
    signals = entry.get("signals")
    counts = {key: 0 for key in SIGNAL_KEYS}
    if isinstance(signals, dict):
        for key, value in signals.items():
            if (
                isinstance(key, str)
                and key in SIGNAL_KEY_SET
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            ):
                counts[key] = value
    confidence = _enum(entry.get("confidence"), CONFIDENCE_VALUES, "unknown")
    forbidden_axis = _contains_forbidden_field(entry) or _contains_unsafe_string(entry, depth=0)
    carried = _filter_tokens(entry.get("warnings"), AXIS_WARNING_TOKENS)
    if forbidden_axis:
        carried.add("forbidden_field_stripped")
    return {
        "axis": axis,
        "signals": counts,
        "confidence": confidence,
        "warnings": carried,
    }


# --------------------------------------------------------------------------- #
# Deterministic axis -> axis_result rules
# --------------------------------------------------------------------------- #
def _axis_result_from_observation(obs: dict[str, Any]) -> dict[str, Any]:
    signals = obs["signals"]
    confidence = obs["confidence"]
    pass_count = signals["pass_count"]
    warning_count = signals["warning_count"]
    fail_count = signals["fail_count"]
    not_observed_count = signals["not_observed_count"]

    warnings: set[str] = set(obs["warnings"])

    if fail_count > 0:
        status = "fail"
        score_band = "failed"
    elif warning_count > 0:
        status = "warning"
        score_band = "weak" if confidence in {"low", "unknown"} else "acceptable"
        warnings.add("weak_band")
    elif pass_count > 0:
        status = "pass"
        score_band = "strong" if confidence == "high" else "acceptable"
    else:
        status = "not_observed"
        score_band = "unknown"
        warnings.add("not_observed_axis")

    if confidence == "low":
        warnings.add("low_confidence")

    counts = {
        "observation_count": pass_count + warning_count + fail_count + not_observed_count,
        "pass_count": pass_count,
        "warning_count": warning_count,
        "fail_count": fail_count,
        "not_observed_count": not_observed_count,
    }
    # Drop zero-valued derived counts except observation_count to keep output tight.
    counts = {k: v for k, v in counts.items() if k == "observation_count" or v > 0}

    return {
        "axis": obs["axis"],
        "status": status,
        "confidence": confidence,
        "score_band": score_band,
        "counts": counts,
        "warnings": sorted(warnings & AXIS_WARNING_TOKENS),
    }


def _schema_payload(norm: dict[str, Any], *, axis_results: list[dict[str, Any]]) -> dict[str, Any]:
    # Aggregate derived content warnings up to the report level so report status
    # reflects them; the schema normalizer is the final authority.
    report_warnings: set[str] = set(norm["warnings"]) | set(norm["derived_warnings"])
    for axis in axis_results:
        report_warnings |= {w for w in axis["warnings"] if w in _DERIVED_CONTENT_WARNINGS}
    report_warnings &= WARNING_TOKENS

    return {
        "version": 1,
        "kind": KIND,
        "advisory": True,
        "judge_model_kind": norm["judge_model_kind"],
        "input_scope": norm["input_scope"],
        "axis_results": axis_results,
        "blockers": norm["blockers"],
        "warnings": sorted(report_warnings),
        "calibration_status": norm["calibration_status"],
        "privacy_status": norm["privacy_status"],
        # The core never asserts a softer floor than the floor payload; leave it
        # unknown unless the floor payload (authoritative) overrides it.
        "deterministic_floor_status": "unknown",
    }


# --------------------------------------------------------------------------- #
# Small pure helpers
# --------------------------------------------------------------------------- #
def _enum(value: Any, allowed: frozenset[str], default: str) -> str:
    if isinstance(value, str) and value.strip().lower() in allowed:
        return value.strip().lower()
    return default


def _calibration(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in CALIBRATION_STATUSES:
        token = value.strip().lower()
        # operator_validated cannot be claimed in this slice; the schema will also
        # downgrade it, but the core never emits it.
        return "synthetic_only" if token == "operator_validated" else token
    return "synthetic_only"


def _filter_tokens(raw: Any, allowed: frozenset[str]) -> set[str]:
    out: set[str] = set()
    if not isinstance(raw, list):
        return out
    for token in raw[:_MAX_TOKENS]:
        if isinstance(token, str) and token in allowed:
            out.add(token)
    return out


def _contains_forbidden_field(obj: Any, depth: int = 0) -> bool:
    if depth > _MAX_DEPTH:
        return False
    if isinstance(obj, dict):
        if any(key in FORBIDDEN_FIELDS for key in obj):
            return True
        return any(_contains_forbidden_field(v, depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_forbidden_field(item, depth + 1) for item in obj)
    return False


def _contains_unsafe_string(obj: Any, *, depth: int) -> bool:
    if depth > _MAX_DEPTH:
        return False
    if isinstance(obj, str):
        lowered = obj.lower()
        markers = ("/home/", "/mnt/", "http://", "https://", ".pdf", ".docx", ".zip",
                   "bearer", "authorization", "api_key", "api-key", "secret", "data:", "base64")
        return any(m in lowered for m in markers)
    if isinstance(obj, dict):
        return any(_contains_unsafe_string(v, depth=depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_unsafe_string(item, depth=depth + 1) for item in obj)
    return False


# --------------------------------------------------------------------------- #
# Synthetic observation cases (synthetic data + synthetic canaries only)
# --------------------------------------------------------------------------- #
def _axis_obs(
    axis: str,
    *,
    pass_count: int = 0,
    warning_count: int = 0,
    fail_count: int = 0,
    not_observed_count: int = 0,
    confidence: str = "high",
    warnings: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    obs: dict[str, Any] = {
        "axis": axis,
        "signals": {
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "not_observed_count": not_observed_count,
        },
        "confidence": confidence,
        "warnings": list(warnings or []),
    }
    if extra:
        obs.update(extra)
    return obs


def _base_observations(**overrides: Any) -> dict[str, Any]:
    obs: dict[str, Any] = {
        "case_id": "synthetic",
        "judge_model_kind": "synthetic",
        "input_scope": "synthetic",
        "axis_observations": [],
        "blockers": [],
        "warnings": [],
        "calibration_status": "synthetic_only",
        "privacy_status": "ok",
    }
    obs.update(overrides)
    return obs


def _clean_case() -> dict[str, Any]:
    return _base_observations(
        case_id="clean_synthetic_judge_case",
        axis_observations=[
            _axis_obs(axis, pass_count=3, confidence="high") for axis in ALLOWED_AXES
        ],
        privacy_status="ok",
    )


def _weak_case() -> dict[str, Any]:
    return _base_observations(
        case_id="weak_synthetic_judge_case",
        axis_observations=[
            _axis_obs("correctness", warning_count=1, confidence="medium"),
            _axis_obs("completeness", warning_count=1, confidence="low",
                      warnings=["low_confidence"]),
            _axis_obs("source_grounding", not_observed_count=1, confidence="unknown"),
            _axis_obs("structure_and_study_value", pass_count=2, confidence="medium"),
            _axis_obs("math_numeric_safety", pass_count=2, confidence="high"),
            _axis_obs("leakage_privacy_safety", pass_count=1, confidence="high"),
            _axis_obs("citation_traceability", warning_count=1, confidence="low"),
            _axis_obs("exam_readiness", pass_count=1, confidence="medium"),
        ],
        privacy_status="ok",
    )


def _failed_case() -> dict[str, Any]:
    return _base_observations(
        case_id="failed_synthetic_judge_case",
        axis_observations=[
            _axis_obs("correctness", fail_count=2, pass_count=1, confidence="high"),
            _axis_obs("completeness", warning_count=1, confidence="medium"),
            _axis_obs("math_numeric_safety", fail_count=1, confidence="high"),
        ],
        privacy_status="ok",
    )


def _leak_case() -> dict[str, Any]:
    # Synthetic canaries under forbidden field keys to prove they are stripped.
    canary_extra = {
        "guide_text": "ZZSYNTH_CORE_PRIVATE_MARKER_ONLY",
        "evidence_quotes": "EVIDENCE_QUOTE_SYNTHETIC_CORE_MARKER",
        "free_text_rationales": "FREE_TEXT_RATIONALE_SYNTHETIC_CORE_MARKER",
        "paths": "/home/fake_private/synthetic-core-source.pdf",
    }
    leak_axis = _axis_obs(
        "leakage_privacy_safety",
        fail_count=2,
        confidence="high",
        warnings=["leak_canary_observed", "privacy_concern"],
        extra=canary_extra,
    )
    obs = _base_observations(
        case_id="leak_canary_synthetic_judge_case",
        axis_observations=[
            _axis_obs("correctness", pass_count=2, confidence="high"),
            leak_axis,
        ],
        warnings=["leak_canary_observed", "privacy_concern"],
        privacy_status="failed",
    )
    # Top-level forbidden canary fields that must never survive into output.
    obs.update(
        {
            "raw_text": "RAW_TEXT_SYNTHETIC_CORE_MARKER",
            "source_text": "SOURCE_TEXT_SYNTHETIC_CORE_MARKER",
            "ocr_text": "OCR_TEXT_SYNTHETIC_CORE_MARKER",
            "table_cells": ["TABLE_CELL_SYNTHETIC_CORE_MARKER"],
            "captions": "CAPTION_SYNTHETIC_CORE_MARKER",
            "formulas_as_text": "E=mc^2_synthetic_core_marker",
            "filenames": "UPLOADED_SYNTHETIC_CORE_FILENAME",
            "basenames": "synthetic-core-source.pdf",
            "urls": "https://private.invalid/synthetic-core",
            "provider_payloads": "PROVIDER_PAYLOAD_SYNTHETIC_CORE_MARKER",
            "model_prompts": "MODEL_PROMPT_SYNTHETIC_CORE_MARKER",
            "model_responses": "MODEL_RESPONSE_SYNTHETIC_CORE_MARKER",
            "private_rationales": "PRIVATE_RATIONALE_SYNTHETIC_CORE_MARKER",
            "chain_of_thought": "CHAIN_OF_THOUGHT_SYNTHETIC_CORE_MARKER",
            "quality_judge_dump": "QUALITY_JUDGE_DUMP_SYNTHETIC_CORE_MARKER",
            "nn3_json": "NN3_JSON_SYNTHETIC_CORE_MARKER",
            "judge_response_nn3_json": "JUDGE_RESPONSE_NN3_SYNTHETIC_CORE_MARKER",
            "quality_jsonl": "QUALITY_JSONL_SYNTHETIC_CORE_MARKER",
            # Free-text / unknown tokens that must be dropped.
            "warnings": ["leak_canary_observed", "FREE_TEXT_NOT_A_TOKEN_CORE"],
            "blockers": ["leak_detected", "NOT_A_BLOCKER_TOKEN_CORE"],
        }
    )
    return obs


def _floor_red_case() -> dict[str, Any]:
    return _base_observations(
        case_id="deterministic_floor_red_synthetic_judge_case",
        axis_observations=[
            _axis_obs("correctness", pass_count=2, confidence="high"),
            _axis_obs("math_numeric_safety", warning_count=1, confidence="medium"),
        ],
        privacy_status="ok",
    )


_SYNTHETIC_CASES = {
    "clean_synthetic_judge_case": _clean_case,
    "weak_synthetic_judge_case": _weak_case,
    "failed_synthetic_judge_case": _failed_case,
    "leak_canary_synthetic_judge_case": _leak_case,
    "deterministic_floor_red_synthetic_judge_case": _floor_red_case,
}


def _synthetic_floor_payload(case_id: Any) -> dict[str, Any] | None:
    if case_id == "deterministic_floor_red_synthetic_judge_case":
        return {"safety_floor_green": False}
    return None
