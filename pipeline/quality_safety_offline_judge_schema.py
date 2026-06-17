"""Pure schema + synthetic fixtures for the future offline judge report (Slice 142).

This module proves the **future** offline judge report contract
(`docs/QUALITY_SAFETY_OFFLINE_JUDGE_CONTRACT.md`) can be normalized, sanitized,
serialized, and validated using **synthetic data only**. It is *not* judge
execution: it does not score guides, read files, scan jobs, parse source/OCR/table
text, call providers/models/cloud/local LLMs, or wire anything into production.

The proposed (not produced) future artifact name remains
``quality_safety_offline_judge_report.json`` and the schema ``kind`` is
``quality_safety_offline_judge_report``. The future judge stays advisory,
non-blocking initially, and subordinate to the deterministic safety floor:
``judge_ready`` always normalizes to ``False`` in this slice and ``repair_ready``
always normalizes to ``False``.

The normalizer rebuilds output strictly from a closed vocabulary of whitelisted
fields, so no raw guide/source/reference text, free-text rationale, filename,
path, URL, provider payload, model prompt/response, or other forbidden content can
survive into a committed report by construction.
"""
from __future__ import annotations

import json
import re
from typing import Any

VERSION = 1
KIND = "quality_safety_offline_judge_report"

REPORT_STATUSES = frozenset({"ok", "warning", "skipped", "partial", "failed"})
JUDGE_MODEL_KINDS = frozenset({"synthetic", "local_offline", "operator_assisted", "unknown"})
INPUT_SCOPES = frozenset({"synthetic", "private_runtime", "unknown"})

ALLOWED_AXES = (
    "correctness",
    "completeness",
    "source_grounding",
    "structure_and_study_value",
    "math_numeric_safety",
    "leakage_privacy_safety",
    "citation_traceability",
    "exam_readiness",
)
ALLOWED_AXIS_SET = frozenset(ALLOWED_AXES)

AXIS_STATUSES = frozenset({"pass", "warning", "fail", "not_observed", "not_applicable"})
CONFIDENCE_VALUES = frozenset({"high", "medium", "low", "unknown"})
SCORE_BANDS = frozenset({"strong", "acceptable", "weak", "failed", "unknown"})

CALIBRATION_STATUSES = frozenset(
    {"not_started", "synthetic_only", "operator_validated", "failed", "blocked"}
)
PRIVACY_STATUSES = frozenset({"ok", "warning", "failed", "unknown"})
DETERMINISTIC_FLOOR_STATUSES = frozenset(
    {"ready_for_cleanup_freeze", "partial", "blocked", "unknown"}
)

# Closed count-key vocabulary for per-axis ``counts`` (non-negative ints only).
COUNT_KEYS = frozenset(
    {
        "observation_count",
        "finding_count",
        "pass_count",
        "warning_count",
        "fail_count",
        "not_observed_count",
        "checked_count",
        "flagged_count",
    }
)

# Fields that must never appear in a committed judge report. The normalizer never
# copies arbitrary input fields, so these cannot survive; their presence in input
# only raises a closed-vocabulary warning.
FORBIDDEN_FIELDS = frozenset(
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
        "screenshots",
        "raw_runtime_artifacts",
        "raw_artifact_json",
        "provider_payloads",
        "model_prompts",
        "model_responses",
        "private_rationales",
        "free_text_rationales",
        "chain_of_thought",
        "quality_judge_dump",
        "nn3_json",
        "judge_response_nn3_json",
        "quality_jsonl",
    }
)

# Closed blocker vocabulary. Blockers are derived deterministically; only these
# tokens may appear in a report's ``blockers`` list.
BLOCKER_ORDER = (
    "deterministic_floor_red",
    "leak_detected",
    "privacy_failed",
    "calibration_failed",
    "axis_failed",
)
BLOCKER_TOKENS = frozenset(BLOCKER_ORDER)

# Closed warning vocabulary: normalization warnings plus closed content findings.
WARNING_ORDER = (
    # normalization warnings
    "component_missing",
    "malformed_report_input",
    "wrong_kind",
    "advisory_normalized",
    "judge_ready_forced_false",
    "repair_ready_forced_false",
    "forbidden_field_stripped",
    "unsafe_string_stripped",
    "unknown_axis_dropped",
    "duplicate_axis_deduplicated",
    "invalid_axis_status_normalized",
    "invalid_confidence_normalized",
    "invalid_score_band_normalized",
    "invalid_count_dropped",
    "invalid_warning_token_dropped",
    "invalid_blocker_token_dropped",
    "calibration_status_normalized",
    "operator_validated_not_allowed_yet",
    "privacy_status_normalized",
    "deterministic_floor_status_normalized",
    "judge_model_kind_normalized",
    "input_scope_normalized",
    "status_normalized",
    # closed content findings (may be carried from input)
    "low_confidence",
    "weak_band",
    "not_observed_axis",
    "leak_canary_observed",
    "privacy_concern",
)
WARNING_TOKENS = frozenset(WARNING_ORDER)

# Per-axis warnings are constrained to the closed content-finding subset.
AXIS_WARNING_ORDER = (
    "forbidden_field_stripped",
    "unsafe_string_stripped",
    "invalid_count_dropped",
    "invalid_warning_token_dropped",
    "low_confidence",
    "weak_band",
    "not_observed_axis",
    "leak_canary_observed",
    "privacy_concern",
)
AXIS_WARNING_TOKENS = frozenset(AXIS_WARNING_ORDER)

_MAX_AXES = 64
_MAX_TOKENS = 64
_MAX_DEPTH = 6
_SAFE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
_UNSAFE_RE = re.compile(
    r"(https?://|/home/|/mnt/|/tmp/|/var/|\\\\|[A-Za-z]:\\|\.\./|/\.\.|"
    r"authorization|bearer|api[_-]?key|token|secret|data:|base64|provider payload|"
    r"ocr|caption|table text|evidence quote|source text|raw text|guide snippet|"
    r"chain[_ -]?of[_ -]?thought|rationale|private|\.pdf|\.docx|\.zip|\.png|\.jpg|"
    r"\.jpeg|\.webp)",
    re.IGNORECASE,
)
_BASE64ISH_RE = re.compile(r"^[A-Za-z0-9+/]{80,}={0,2}$")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_empty_offline_judge_report(reason: str = "component_missing") -> dict[str, Any]:
    """Return a safe, skipped, advisory-only empty report with a closed warning."""
    token = reason if isinstance(reason, str) and reason in WARNING_TOKENS else "component_missing"
    return _report(
        status="skipped",
        judge_model_kind="unknown",
        input_scope="unknown",
        axis_results=[],
        blockers=set(),
        warnings={token},
        calibration_status="not_started",
        privacy_status="unknown",
        deterministic_floor_status="unknown",
    )


def normalize_offline_judge_report(
    payload: Any,
    *,
    deterministic_floor_payload: Any = None,
) -> dict[str, Any]:
    """Normalize an arbitrary payload into the closed/sanitized report shape.

    Never raises, never mutates its caller input. ``judge_ready`` and
    ``repair_ready`` always normalize to ``False`` in this slice.
    """
    try:
        return _normalize(payload, deterministic_floor_payload=deterministic_floor_payload)
    except Exception:
        return build_empty_offline_judge_report("malformed_report_input")


def validate_offline_judge_report(payload: Any) -> dict[str, Any]:
    """Validate a normalized report against the closed contract.

    Returns ``{"valid": bool, "violations": [closed tokens]}`` only — never raw
    content. ``operator_validated`` is rejected in this slice.
    """
    violations: set[str] = set()
    if not isinstance(payload, dict):
        return {"valid": False, "violations": ["not_a_dict"]}
    if payload.get("version") != VERSION:
        violations.add("bad_version")
    if payload.get("kind") != KIND:
        violations.add("bad_kind")
    if payload.get("advisory") is not True:
        violations.add("advisory_not_true")
    if payload.get("status") not in REPORT_STATUSES:
        violations.add("bad_status")
    if payload.get("judge_model_kind") not in JUDGE_MODEL_KINDS:
        violations.add("bad_judge_model_kind")
    if payload.get("input_scope") not in INPUT_SCOPES:
        violations.add("bad_input_scope")
    if payload.get("calibration_status") not in CALIBRATION_STATUSES:
        violations.add("bad_calibration_status")
    if payload.get("calibration_status") == "operator_validated":
        violations.add("operator_validated_not_allowed_yet")
    if payload.get("privacy_status") not in PRIVACY_STATUSES:
        violations.add("bad_privacy_status")
    if payload.get("deterministic_floor_status") not in DETERMINISTIC_FLOOR_STATUSES:
        violations.add("bad_deterministic_floor_status")
    if payload.get("judge_ready") is not False:
        violations.add("judge_ready_not_false")
    if payload.get("repair_ready") is not False:
        violations.add("repair_ready_not_false")

    if any(field in payload for field in FORBIDDEN_FIELDS):
        violations.add("forbidden_field_present")

    blockers = payload.get("blockers")
    if not isinstance(blockers, list) or any(b not in BLOCKER_TOKENS for b in blockers):
        violations.add("bad_blockers")
    warnings = payload.get("warnings")
    if not isinstance(warnings, list) or any(w not in WARNING_TOKENS for w in warnings):
        violations.add("bad_warnings")

    summary = payload.get("summary")
    expected_summary = {
        "axis_count",
        "pass_count",
        "warning_count",
        "fail_count",
        "not_observed_count",
        "blocker_count",
    }
    if not isinstance(summary, dict) or set(summary) != expected_summary:
        violations.add("bad_summary")
    elif not all(
        isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in summary.values()
    ):
        violations.add("bad_summary_counts")

    axis_results = payload.get("axis_results")
    if not isinstance(axis_results, list):
        violations.add("bad_axis_results")
    else:
        seen: set[str] = set()
        for axis in axis_results:
            if not isinstance(axis, dict):
                violations.add("bad_axis_entry")
                continue
            if set(axis) != {"axis", "status", "confidence", "score_band", "counts", "warnings"}:
                violations.add("bad_axis_fields")
            if axis.get("axis") not in ALLOWED_AXIS_SET:
                violations.add("bad_axis_name")
            elif axis.get("axis") in seen:
                violations.add("duplicate_axis")
            else:
                seen.add(axis.get("axis"))
            if axis.get("status") not in AXIS_STATUSES:
                violations.add("bad_axis_status")
            if axis.get("confidence") not in CONFIDENCE_VALUES:
                violations.add("bad_axis_confidence")
            if axis.get("score_band") not in SCORE_BANDS:
                violations.add("bad_axis_score_band")
            counts = axis.get("counts")
            if not isinstance(counts, dict) or not all(
                k in COUNT_KEYS
                and isinstance(v, int)
                and not isinstance(v, bool)
                and v >= 0
                for k, v in counts.items()
            ):
                violations.add("bad_axis_counts")
            axis_warnings = axis.get("warnings")
            if not isinstance(axis_warnings, list) or any(
                w not in AXIS_WARNING_TOKENS for w in axis_warnings
            ):
                violations.add("bad_axis_warnings")

    return {"valid": not violations, "violations": sorted(violations)}


def serialize_offline_judge_report(payload: Any) -> str:
    """Deterministically serialize a normalized report to a JSON string."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_synthetic_offline_judge_fixture(case_id: Any) -> dict[str, Any]:
    """Return a synthetic *input* payload for a named case (synthetic data only).

    The returned payload is pre-normalization input intended to be fed through
    :func:`normalize_offline_judge_report`. Leak cases carry synthetic canaries to
    prove they are stripped; no real/private material is used.
    """
    builder = _SYNTHETIC_FIXTURES.get(case_id if isinstance(case_id, str) else "")
    if builder is None:
        return build_empty_offline_judge_report("component_missing")
    return builder()


SYNTHETIC_FIXTURE_IDS = (
    "clean_synthetic_judge_case",
    "weak_synthetic_judge_case",
    "failed_synthetic_judge_case",
    "leak_canary_synthetic_judge_case",
    "deterministic_floor_red_synthetic_judge_case",
)


# --------------------------------------------------------------------------- #
# Normalization internals
# --------------------------------------------------------------------------- #
def _normalize(payload: Any, *, deterministic_floor_payload: Any) -> dict[str, Any]:
    if payload is None:
        return build_empty_offline_judge_report("component_missing")
    if not isinstance(payload, dict):
        return build_empty_offline_judge_report("malformed_report_input")
    if payload.get("kind") != KIND:
        report = build_empty_offline_judge_report("wrong_kind")
        report["status"] = "failed"
        return report

    warnings: set[str] = set()

    if _contains_forbidden_field(payload):
        warnings.add("forbidden_field_stripped")
    if _contains_unsafe_string(payload, depth=0):
        warnings.add("unsafe_string_stripped")

    if payload.get("advisory") is not True:
        warnings.add("advisory_normalized")

    judge_model_kind = _enum(
        payload.get("judge_model_kind"), JUDGE_MODEL_KINDS, "unknown", warnings,
        "judge_model_kind_normalized",
    )
    input_scope = _enum(
        payload.get("input_scope"), INPUT_SCOPES, "unknown", warnings, "input_scope_normalized"
    )

    axis_results = _normalize_axes(payload.get("axis_results"), warnings)

    # Carry deterministic floor status from the floor payload when provided.
    deterministic_floor_status = _deterministic_floor_status(
        payload.get("deterministic_floor_status"),
        deterministic_floor_payload,
        warnings,
    )

    privacy_status = _enum(
        payload.get("privacy_status"), PRIVACY_STATUSES, "unknown", warnings,
        "privacy_status_normalized",
    )

    calibration_status = _calibration_status(payload.get("calibration_status"), warnings)

    # Incoming closed tokens, filtered. Free-text or unknown tokens are dropped.
    warnings |= _filter_tokens(
        payload.get("warnings"), WARNING_TOKENS, warnings, "invalid_warning_token_dropped"
    )
    blockers = _filter_tokens(
        payload.get("blockers"), BLOCKER_TOKENS, warnings, "invalid_blocker_token_dropped"
    )

    # Derived blockers — deterministic, never weaker than the floor/privacy state.
    if deterministic_floor_status == "blocked":
        blockers.add("deterministic_floor_red")
    if privacy_status == "failed":
        blockers.add("privacy_failed")
    if any(axis["status"] == "fail" for axis in axis_results):
        blockers.add("axis_failed")
    if calibration_status == "failed":
        blockers.add("calibration_failed")

    status = _report_status(axis_results=axis_results, blockers=blockers, warnings=warnings)

    return _report(
        status=status,
        judge_model_kind=judge_model_kind,
        input_scope=input_scope,
        axis_results=axis_results,
        blockers=blockers,
        warnings=warnings,
        calibration_status=calibration_status,
        privacy_status=privacy_status,
        deterministic_floor_status=deterministic_floor_status,
    )


def _normalize_axes(raw: Any, warnings: set[str]) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        warnings.add("malformed_report_input")
        return []
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in raw[:_MAX_AXES]:
        if not isinstance(entry, dict):
            warnings.add("unknown_axis_dropped")
            continue
        axis = entry.get("axis")
        if not isinstance(axis, str) or axis.strip().lower() not in ALLOWED_AXIS_SET:
            warnings.add("unknown_axis_dropped")
            continue
        axis = axis.strip().lower()
        if axis in seen:
            warnings.add("duplicate_axis_deduplicated")
            continue
        seen.add(axis)
        out.append(_normalize_axis(axis, entry, warnings))
    return out


def _normalize_axis(axis: str, entry: dict[str, Any], warnings: set[str]) -> dict[str, Any]:
    if _contains_forbidden_field(entry):
        warnings.add("forbidden_field_stripped")
    if _contains_unsafe_string(entry, depth=0):
        warnings.add("unsafe_string_stripped")

    status = entry.get("status")
    if not (isinstance(status, str) and status.strip().lower() in AXIS_STATUSES):
        if status is not None:
            warnings.add("invalid_axis_status_normalized")
        status = "not_observed"
    else:
        status = status.strip().lower()

    confidence = _enum(
        entry.get("confidence"), CONFIDENCE_VALUES, "unknown", warnings,
        "invalid_confidence_normalized",
    )
    score_band = _enum(
        entry.get("score_band"), SCORE_BANDS, "unknown", warnings,
        "invalid_score_band_normalized",
    )
    counts = _normalize_counts(entry.get("counts"), warnings)
    axis_warnings = _filter_tokens(
        entry.get("warnings"), AXIS_WARNING_TOKENS, warnings, "invalid_warning_token_dropped"
    )

    return {
        "axis": axis,
        "status": status,
        "confidence": confidence,
        "score_band": score_band,
        "counts": counts,
        "warnings": _ordered(axis_warnings, AXIS_WARNING_ORDER),
    }


def _normalize_counts(raw: Any, warnings: set[str]) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        if (
            isinstance(key, str)
            and key in COUNT_KEYS
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
        ):
            out[key] = value
        else:
            warnings.add("invalid_count_dropped")
    return {key: out[key] for key in sorted(out)}


def _enum(
    value: Any,
    allowed: frozenset[str],
    default: str,
    warnings: set[str],
    warning_token: str,
) -> str:
    if value is None:
        return default
    if isinstance(value, str) and value.strip().lower() in allowed:
        return value.strip().lower()
    warnings.add(warning_token)
    return default


def _calibration_status(value: Any, warnings: set[str]) -> str:
    if value is None:
        return "not_started"
    if not isinstance(value, str) or value.strip().lower() not in CALIBRATION_STATUSES:
        warnings.add("calibration_status_normalized")
        return "not_started"
    token = value.strip().lower()
    # operator_validated cannot be claimed in this slice; downgrade to synthetic_only.
    if token == "operator_validated":
        warnings.add("operator_validated_not_allowed_yet")
        return "synthetic_only"
    return token


def _deterministic_floor_status(
    payload_value: Any,
    floor_payload: Any,
    warnings: set[str],
) -> str:
    if isinstance(floor_payload, dict):
        derived = _floor_status_from_payload(floor_payload)
        if derived is not None:
            return derived
    if payload_value is None:
        return "unknown"
    if isinstance(payload_value, str) and payload_value.strip().lower() in DETERMINISTIC_FLOOR_STATUSES:
        return payload_value.strip().lower()
    warnings.add("deterministic_floor_status_normalized")
    return "unknown"


def _floor_status_from_payload(floor_payload: dict[str, Any]) -> str | None:
    for key in ("deterministic_floor_status", "deterministic_safety_floor_status"):
        value = floor_payload.get(key)
        if isinstance(value, str) and value.strip().lower() in DETERMINISTIC_FLOOR_STATUSES:
            return value.strip().lower()
    # Map a synthetic floor red/green signal to the closed vocabulary.
    green = floor_payload.get("safety_floor_green")
    if green is False:
        return "blocked"
    if green is True:
        return "ready_for_cleanup_freeze"
    return None


def _filter_tokens(
    raw: Any,
    allowed: frozenset[str],
    warnings: set[str],
    drop_warning: str,
) -> set[str]:
    out: set[str] = set()
    if raw is None:
        return out
    if not isinstance(raw, list):
        warnings.add(drop_warning)
        return out
    for token in raw[:_MAX_TOKENS]:
        if isinstance(token, str) and token in allowed:
            out.add(token)
        else:
            warnings.add(drop_warning)
    return out


def _report_status(
    *,
    axis_results: list[dict[str, Any]],
    blockers: set[str],
    warnings: set[str],
) -> str:
    if blockers:
        return "failed"
    if any(axis["status"] == "fail" for axis in axis_results):
        return "failed"
    if not axis_results:
        return "skipped"
    content = {"low_confidence", "weak_band", "not_observed_axis", "leak_canary_observed", "privacy_concern"}
    if (
        warnings & content
        or any(axis["status"] in {"warning", "not_observed"} for axis in axis_results)
        or any(axis["warnings"] for axis in axis_results)
    ):
        return "warning"
    return "ok"


def _report(
    *,
    status: str,
    judge_model_kind: str,
    input_scope: str,
    axis_results: list[dict[str, Any]],
    blockers: set[str],
    warnings: set[str],
    calibration_status: str,
    privacy_status: str,
    deterministic_floor_status: str,
) -> dict[str, Any]:
    blocker_list = _ordered(blockers, BLOCKER_ORDER)
    pass_count = sum(1 for a in axis_results if a["status"] == "pass")
    warning_count = sum(1 for a in axis_results if a["status"] == "warning")
    fail_count = sum(1 for a in axis_results if a["status"] == "fail")
    not_observed_count = sum(1 for a in axis_results if a["status"] == "not_observed")
    return {
        "version": VERSION,
        "kind": KIND,
        "advisory": True,
        "status": status if status in REPORT_STATUSES else "warning",
        "judge_model_kind": judge_model_kind if judge_model_kind in JUDGE_MODEL_KINDS else "unknown",
        "input_scope": input_scope if input_scope in INPUT_SCOPES else "unknown",
        "summary": {
            "axis_count": len(axis_results),
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "not_observed_count": not_observed_count,
            "blocker_count": len(blocker_list),
        },
        "axis_results": axis_results,
        "blockers": blocker_list,
        "warnings": _ordered(warnings, WARNING_ORDER),
        "calibration_status": calibration_status if calibration_status in CALIBRATION_STATUSES else "not_started",
        "privacy_status": privacy_status if privacy_status in PRIVACY_STATUSES else "unknown",
        "deterministic_floor_status": deterministic_floor_status
        if deterministic_floor_status in DETERMINISTIC_FLOOR_STATUSES
        else "unknown",
        "judge_ready": False,
        "repair_ready": False,
    }


def _ordered(tokens: set[str], order: tuple[str, ...]) -> list[str]:
    return [token for token in order if token in tokens]


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
        return bool(_UNSAFE_RE.search(obj) or _BASE64ISH_RE.fullmatch(obj.strip()))
    if isinstance(obj, dict):
        return any(_contains_unsafe_string(v, depth=depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_unsafe_string(item, depth=depth + 1) for item in obj)
    return False


# --------------------------------------------------------------------------- #
# Synthetic fixtures (synthetic data + synthetic canaries only)
# --------------------------------------------------------------------------- #
def _axis(
    axis: str,
    status: str,
    *,
    confidence: str = "high",
    score_band: str = "strong",
    counts: dict[str, int] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "axis": axis,
        "status": status,
        "confidence": confidence,
        "score_band": score_band,
        "counts": dict(counts or {"observation_count": 0}),
        "warnings": list(warnings or []),
    }


def _base_input(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": VERSION,
        "kind": KIND,
        "advisory": True,
        "judge_model_kind": "synthetic",
        "input_scope": "synthetic",
        "axis_results": [],
        "blockers": [],
        "warnings": [],
        "calibration_status": "synthetic_only",
        "privacy_status": "ok",
        "deterministic_floor_status": "ready_for_cleanup_freeze",
        # Even if a fixture tried to assert these, the normalizer forces them false.
        "judge_ready": False,
        "repair_ready": False,
    }
    payload.update(overrides)
    return payload


def _clean_fixture() -> dict[str, Any]:
    return _base_input(
        axis_results=[
            _axis(axis, "pass", counts={"observation_count": 3, "checked_count": 3})
            for axis in ALLOWED_AXES
        ],
        calibration_status="synthetic_only",
        privacy_status="ok",
        deterministic_floor_status="ready_for_cleanup_freeze",
    )


def _weak_fixture() -> dict[str, Any]:
    axes = [
        _axis("correctness", "warning", confidence="medium", score_band="acceptable",
              counts={"observation_count": 2, "flagged_count": 1}, warnings=["weak_band"]),
        _axis("completeness", "warning", confidence="low", score_band="weak",
              counts={"observation_count": 2, "warning_count": 1},
              warnings=["low_confidence", "weak_band"]),
        _axis("source_grounding", "not_observed", confidence="unknown", score_band="unknown",
              counts={"not_observed_count": 1}, warnings=["not_observed_axis"]),
        _axis("structure_and_study_value", "pass", confidence="medium", score_band="acceptable"),
        _axis("math_numeric_safety", "pass"),
        _axis("leakage_privacy_safety", "pass"),
        _axis("citation_traceability", "warning", confidence="low", score_band="weak",
              warnings=["weak_band"]),
        _axis("exam_readiness", "pass", confidence="medium", score_band="acceptable"),
    ]
    return _base_input(
        axis_results=axes,
        warnings=["low_confidence", "weak_band"],
        calibration_status="synthetic_only",
    )


def _failed_fixture() -> dict[str, Any]:
    axes = [
        _axis("correctness", "fail", confidence="high", score_band="failed",
              counts={"observation_count": 4, "fail_count": 2}),
        _axis("completeness", "warning", confidence="medium", score_band="weak",
              warnings=["weak_band"]),
        _axis("math_numeric_safety", "fail", confidence="high", score_band="failed",
              counts={"flagged_count": 1}),
    ]
    return _base_input(
        axis_results=axes,
        blockers=["axis_failed"],
        warnings=["weak_band"],
        calibration_status="synthetic_only",
    )


def _leak_canary_fixture() -> dict[str, Any]:
    # Synthetic canaries placed under forbidden field keys to prove stripping.
    canary_axis = _axis(
        "leakage_privacy_safety", "fail", confidence="high", score_band="failed",
        counts={"flagged_count": 2}, warnings=["leak_canary_observed", "privacy_concern"],
    )
    canary_axis.update(
        {
            "guide_text": "ZZSYNTH_JUDGE_PRIVATE_MARKER_ONLY",
            "evidence_quotes": "EVIDENCE_QUOTE_SYNTHETIC_JUDGE_MARKER",
            "free_text_rationales": "FREE_TEXT_RATIONALE_SYNTHETIC_JUDGE_MARKER",
            "paths": "/home/fake_private/synthetic-source.pdf",
        }
    )
    payload = _base_input(
        axis_results=[
            _axis("correctness", "pass"),
            canary_axis,
        ],
        warnings=["leak_canary_observed", "privacy_concern"],
        privacy_status="failed",
        calibration_status="synthetic_only",
    )
    payload.update(
        {
            "raw_text": "RAW_TEXT_SYNTHETIC_JUDGE_MARKER",
            "source_text": "SOURCE_TEXT_SYNTHETIC_JUDGE_MARKER",
            "ocr_text": "OCR_TEXT_SYNTHETIC_JUDGE_MARKER",
            "table_cells": ["TABLE_CELL_SYNTHETIC_JUDGE_MARKER"],
            "captions": "CAPTION_SYNTHETIC_JUDGE_MARKER",
            "formulas_as_text": "E=mc^2_synthetic_judge_marker",
            "filenames": "UPLOADED_SYNTHETIC_JUDGE_FILENAME",
            "basenames": "synthetic-source.pdf",
            "urls": "https://private.invalid/synthetic-judge",
            "provider_payloads": "PROVIDER_PAYLOAD_SYNTHETIC_JUDGE_MARKER",
            "model_prompts": "MODEL_PROMPT_SYNTHETIC_JUDGE_MARKER",
            "model_responses": "MODEL_RESPONSE_SYNTHETIC_JUDGE_MARKER",
            "private_rationales": "PRIVATE_RATIONALE_SYNTHETIC_JUDGE_MARKER",
            "chain_of_thought": "CHAIN_OF_THOUGHT_SYNTHETIC_JUDGE_MARKER",
            "quality_judge_dump": "QUALITY_JUDGE_DUMP_SYNTHETIC_JUDGE_MARKER",
            "nn3_json": "NN3_JSON_SYNTHETIC_JUDGE_MARKER",
            "judge_response_nn3_json": "JUDGE_RESPONSE_NN3_SYNTHETIC_JUDGE_MARKER",
            "quality_jsonl": "QUALITY_JSONL_SYNTHETIC_JUDGE_MARKER",
            # Free-text / unknown closed tokens that must be dropped.
            "warnings": ["leak_canary_observed", "FREE_TEXT_NOT_A_TOKEN"],
            "blockers": ["leak_detected", "NOT_A_BLOCKER_TOKEN"],
        }
    )
    return payload


def _floor_red_fixture() -> dict[str, Any]:
    return _base_input(
        axis_results=[
            _axis("correctness", "pass"),
            _axis("math_numeric_safety", "warning", confidence="medium", score_band="acceptable"),
        ],
        blockers=["deterministic_floor_red"],
        deterministic_floor_status="blocked",
        calibration_status="blocked",
    )


_SYNTHETIC_FIXTURES = {
    "clean_synthetic_judge_case": _clean_fixture,
    "weak_synthetic_judge_case": _weak_fixture,
    "failed_synthetic_judge_case": _failed_fixture,
    "leak_canary_synthetic_judge_case": _leak_canary_fixture,
    "deterministic_floor_red_synthetic_judge_case": _floor_red_fixture,
}
