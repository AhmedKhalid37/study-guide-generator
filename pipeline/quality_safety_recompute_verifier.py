"""Quality Safety recompute verifier v1 (Slice 111).

Pure, deterministic numeric *recompute* verifier for the Quality Safety Unit. It
consumes the Slice 110 fact-record / fact-sheet schema
(:mod:`pipeline.quality_safety_fact_sheet`) and verifies numeric facts by
recomputing their value from structured computation inputs.

This is the **primary truth path** for the Quality Safety Unit: when a numeric
fact carries a supported computation method and inputs, the value is recomputed
and compared within tolerance. Canonical-fixture *matching* is intentionally out
of scope here (it is the narrow fallback added in Slice 112).

The module is intentionally unwired and offline:
  * stdlib only, plus :mod:`pipeline.quality_safety_fact_sheet`;
  * no FastAPI / frontend / provider / model / cloud / OCR / render / job runtime
    imports;
  * reads no source documents, no ``clean.md``, writes no artifacts, calls no
    providers/models;
  * never raises on malformed input; every public function returns a
    JSON-serializable dict with closed-vocabulary tokens only;
  * never echoes raw paths, URLs, provider payloads, snippets, OCR/table/caption
    text, or raw exception text — only numeric values, counts, and closed tokens.
"""
from __future__ import annotations

import math
from typing import Any

from pipeline.quality_safety_fact_sheet import normalize_quality_safety_fact_sheet

VERSION = 1
KIND = "quality_safety_recompute_report"

SUPPORTED_METHODS = frozenset(
    {"weighted_gini", "total_error", "amount_of_say", "softmax", "cross_entropy", "forward_pass"}
)

# Method-specific absolute tolerances (documented + tested).
METHOD_TOLERANCES: dict[str, float] = {
    "weighted_gini": 0.01,
    "total_error": 0.005,
    "amount_of_say": 0.02,
    "softmax": 0.01,
    "cross_entropy": 0.01,
    "forward_pass": 0.01,
}
DEFAULT_TOLERANCE = 1e-6
MAX_TOLERANCE = 1.0

CHECK_IDS = frozenset(
    {
        "weighted_gini",
        "total_error",
        "amount_of_say",
        "softmax",
        "cross_entropy",
        "forward_pass",
        "numeric_fact_not_recomputable",
        "non_numeric_fact_not_applicable",
    }
)
CHECK_STATUSES = frozenset({"passed", "warning", "failed", "not_applicable", "unknown"})
REPORT_STATUSES = frozenset({"passed", "warning", "failed", "skipped", "partial"})

WARNING_ORDER = (
    "fact_sheet_missing",
    "malformed_fact_sheet_degraded",
    "non_numeric_fact_not_applicable",
    "computation_missing",
    "unsupported_computation_method",
    "malformed_computation_inputs",
    "invalid_numeric_value",
    "invalid_tolerance",
    "recomputed_mismatch",
    "max_items_reached",
)

_DEFAULT_MAX_FACTS = 1000
_REPORT_ROUND = 6


# ── Public API ──────────────────────────────────────────────────────────────


def recompute_quality_safety_fact(fact_record: Any, *, tolerance: Any = None) -> dict[str, Any]:
    """Recompute and verify one fact record; never raise on malformed input.

    Returns a JSON-serializable result dict with the public check fields plus the
    derived ``verification_status`` / ``provenance`` for a verified sheet update.
    """
    try:
        return _recompute_fact(fact_record, tolerance=tolerance)
    except Exception:
        return _result(
            fact_id="fact_unknown",
            check_id="numeric_fact_not_recomputable",
            status="unknown",
            supplied_value=None,
            recomputed_value=None,
            tolerance=None,
            verification_status="not_applicable",
            provenance="unverified",
            blocking=False,
            warnings=["malformed_computation_inputs"],
        )


def build_quality_safety_recompute_report(fact_sheet: Any, *, max_items: int | None = None) -> dict[str, Any]:
    """Build the recompute report for a fact sheet; never raise on malformed input."""
    report, _ = _verify(fact_sheet, max_items=max_items)
    return report


def verify_quality_safety_fact_sheet(fact_sheet: Any, *, max_items: int | None = None) -> dict[str, Any]:
    """Verify a fact sheet; return the verified normalized sheet plus the report.

    The caller's input is never mutated: normalization produces fresh structures
    and only those are updated with recompute-derived status/provenance.
    """
    report, verified_sheet = _verify(fact_sheet, max_items=max_items)
    return {"fact_sheet": verified_sheet, "report": report}


# ── Verification driver ─────────────────────────────────────────────────────


def _verify(fact_sheet: Any, *, max_items: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    report_warnings: set[str] = set()
    checks: list[dict[str, Any]] = []
    blocking_failures: list[dict[str, Any]] = []

    if fact_sheet is None:
        report_warnings.add("fact_sheet_missing")
        return (
            _build_report("skipped", checks, blocking_failures, report_warnings),
            normalize_quality_safety_fact_sheet(None),
        )

    normalized = normalize_quality_safety_fact_sheet(fact_sheet)
    if "malformed_fact_sheet_degraded" in normalized.get("warnings", []):
        report_warnings.add("malformed_fact_sheet_degraded")

    cap = _resolve_max_items(max_items)
    processed = 0
    truncated = False
    concepts = normalized.get("concepts", [])
    for concept in concepts:
        if truncated:
            break
        facts = concept.get("facts", []) if isinstance(concept, dict) else []
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if processed >= cap:
                truncated = True
                break
            result = _recompute_fact(fact, tolerance=None)
            checks.append(_public_check(result))
            for token in result["warnings"]:
                report_warnings.add(token)
            if result["blocking"]:
                blocking_failures.append(_blocking_entry(result))
            # Update only the normalized (non-caller) sheet, and only with
            # Slice 110 verification statuses.
            if isinstance(fact, dict) and result["verification_status"] in {"verified", "unverified", "failed"}:
                fact["verification_status"] = result["verification_status"]
                fact["provenance"] = result["provenance"]
            processed += 1

    if truncated:
        report_warnings.add("max_items_reached")

    status = _report_status(checks, blocking_failures, report_warnings)
    report = _build_report(status, checks, blocking_failures, report_warnings)
    return report, normalized


def _recompute_fact(fact_record: Any, *, tolerance: Any) -> dict[str, Any]:
    if not isinstance(fact_record, dict):
        return _result(
            fact_id="fact_unknown",
            check_id="numeric_fact_not_recomputable",
            status="unknown",
            supplied_value=None,
            recomputed_value=None,
            tolerance=None,
            verification_status="not_applicable",
            provenance="unverified",
            blocking=False,
            warnings=["malformed_computation_inputs"],
        )

    fact_id = _safe_fact_id(fact_record.get("id"))
    fact_type = fact_record.get("type")
    provenance = fact_record.get("provenance") if isinstance(fact_record.get("provenance"), str) else "unverified"
    original_status = fact_record.get("verification_status")

    # Non-numeric facts are never failed — they are simply not applicable here.
    if fact_type != "numeric":
        return _result(
            fact_id=fact_id,
            check_id="non_numeric_fact_not_applicable",
            status="not_applicable",
            supplied_value=None,
            recomputed_value=None,
            tolerance=None,
            verification_status="not_applicable",
            provenance=provenance,
            blocking=False,
            warnings=["non_numeric_fact_not_applicable"],
        )

    supplied = _finite_number(fact_record.get("value"))
    computation = fact_record.get("computation")
    method = computation.get("method") if isinstance(computation, dict) else None

    has_supported_computation = isinstance(computation, dict) and method in SUPPORTED_METHODS

    # Canonical-fixture facts are matched in Slice 112, not recomputed here —
    # unless a supported computation is also explicitly present.
    if provenance == "canonical_fixture" and not has_supported_computation:
        return _result(
            fact_id=fact_id,
            check_id="numeric_fact_not_recomputable",
            status="not_applicable",
            supplied_value=supplied,
            recomputed_value=None,
            tolerance=None,
            verification_status="not_applicable",
            provenance=provenance,
            blocking=False,
            warnings=[],
        )

    # No computation at all -> cannot recompute; downgrade to unverified.
    if not isinstance(computation, dict):
        return _result(
            fact_id=fact_id,
            check_id="numeric_fact_not_recomputable",
            status="warning",
            supplied_value=supplied,
            recomputed_value=None,
            tolerance=None,
            verification_status="unverified",
            provenance=_downgrade_provenance(provenance),
            blocking=False,
            warnings=["computation_missing"],
        )

    # Unsupported method -> not blocking in v1.
    if method not in SUPPORTED_METHODS:
        return _result(
            fact_id=fact_id,
            check_id="numeric_fact_not_recomputable",
            status="warning",
            supplied_value=supplied,
            recomputed_value=None,
            tolerance=None,
            verification_status="unverified",
            provenance=_downgrade_provenance(provenance),
            blocking=False,
            warnings=["unsupported_computation_method"],
        )

    tol, tol_invalid = _resolve_tolerance(tolerance, computation, fact_record, method)
    recomputed = _RECOMPUTE_METHODS[method](computation.get("inputs"))

    # Inputs missing / malformed / unsafe for the claimed method.
    if recomputed is None:
        return _result(
            fact_id=fact_id,
            check_id=method,
            status="warning",
            supplied_value=supplied,
            recomputed_value=None,
            tolerance=tol,
            verification_status="unverified",
            provenance=_downgrade_provenance(provenance),
            blocking=False,
            warnings=_with_tol(["malformed_computation_inputs"], tol_invalid),
        )

    report_recomputed = round(recomputed, _REPORT_ROUND)

    # Supplied value is non-finite/malformed but recompute succeeded.
    if supplied is None:
        claimed = provenance == "computed" or original_status == "verified"
        if claimed:
            return _result(
                fact_id=fact_id,
                check_id=method,
                status="failed",
                supplied_value=None,
                recomputed_value=report_recomputed,
                tolerance=tol,
                verification_status="failed",
                provenance=provenance,
                blocking=True,
                warnings=_with_tol(["invalid_numeric_value"], tol_invalid),
            )
        return _result(
            fact_id=fact_id,
            check_id=method,
            status="warning",
            supplied_value=None,
            recomputed_value=report_recomputed,
            tolerance=tol,
            verification_status="unverified",
            provenance=_downgrade_provenance(provenance),
            blocking=False,
            warnings=_with_tol(["invalid_numeric_value"], tol_invalid),
        )

    # Compare using the raw recomputed float; report the rounded value.
    if abs(recomputed - supplied) <= tol:
        return _result(
            fact_id=fact_id,
            check_id=method,
            status="passed",
            supplied_value=supplied,
            recomputed_value=report_recomputed,
            tolerance=tol,
            verification_status="verified",
            provenance=_upgrade_provenance(provenance),
            blocking=False,
            warnings=_with_tol([], tol_invalid),
        )

    return _result(
        fact_id=fact_id,
        check_id=method,
        status="failed",
        supplied_value=supplied,
        recomputed_value=report_recomputed,
        tolerance=tol,
        verification_status="failed",
        provenance=provenance,
        blocking=True,
        warnings=_with_tol(["recomputed_mismatch"], tol_invalid),
    )


# ── Recompute methods (pure, total, return float or None) ───────────────────


def _recompute_weighted_gini(inputs: Any) -> float | None:
    if not isinstance(inputs, dict):
        return None
    raw_groups = inputs.get("groups")
    if isinstance(raw_groups, list):
        groups = raw_groups
    else:
        groups = [value for value in inputs.values() if isinstance(value, dict)]
    if not groups:
        return None
    totals: list[float] = []
    ginis: list[float] = []
    for group in groups:
        counts = _group_counts(group)
        if counts is None:
            return None
        total = math.fsum(counts)
        if total <= 0:
            return None
        gini = 1.0 - math.fsum((count / total) ** 2 for count in counts)
        totals.append(total)
        ginis.append(gini)
    grand_total = math.fsum(totals)
    if grand_total <= 0:
        return None
    return math.fsum((total / grand_total) * gini for total, gini in zip(totals, ginis))


def _group_counts(group: Any) -> list[float] | None:
    if not isinstance(group, dict):
        return None
    source = group.get("class_counts") if isinstance(group.get("class_counts"), dict) else group
    counts: list[float] = []
    for value in source.values():
        number = _finite_number(value)
        if number is None or number < 0:
            return None
        counts.append(float(number))
    return counts if counts else None


def _recompute_total_error(inputs: Any) -> float | None:
    if not isinstance(inputs, dict):
        return None
    if "misclassified_weight" in inputs:
        weight = _finite_number(inputs.get("misclassified_weight"))
        if weight is None or weight < 0:
            return None
        return float(weight)
    weights = inputs.get("misclassified_weights")
    if isinstance(weights, list) and weights:
        total = 0.0
        for value in weights:
            number = _finite_number(value)
            if number is None or number < 0:
                return None
            total += float(number)
        return total
    return None


def _recompute_amount_of_say(inputs: Any) -> float | None:
    if not isinstance(inputs, dict):
        return None
    error = _finite_number(inputs.get("total_error"))
    if error is None or not (0.0 < error < 1.0):
        return None
    return 0.5 * math.log((1.0 - error) / error)


def _recompute_softmax(inputs: Any) -> float | None:
    if not isinstance(inputs, dict):
        return None
    raw_values = inputs.get("values")
    if not isinstance(raw_values, list) or not raw_values:
        return None
    values: list[float] = []
    for value in raw_values:
        number = _finite_number(value)
        if number is None:
            return None
        values.append(float(number))
    index = inputs.get("index")
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    if not (0 <= index < len(values)):
        return None
    shift = max(values)
    exps = [math.exp(value - shift) for value in values]
    denom = math.fsum(exps)
    if denom <= 0:
        return None
    return exps[index] / denom


def _recompute_cross_entropy(inputs: Any) -> float | None:
    if not isinstance(inputs, dict):
        return None
    probability = _finite_number(inputs.get("probability"))
    if probability is None or not (0.0 < probability <= 1.0):
        return None
    return -math.log(probability)


def _recompute_forward_pass(inputs: Any) -> float | None:
    if not isinstance(inputs, dict):
        return None
    node_inputs = inputs.get("inputs")
    weights = inputs.get("weights")
    if not isinstance(node_inputs, dict) or not isinstance(weights, dict) or not weights:
        return None
    if set(node_inputs.keys()) != set(weights.keys()):
        return None
    bias_raw = inputs.get("bias", 0)
    bias = _finite_number(bias_raw)
    if bias is None:
        return None
    total = float(bias)
    for key, weight_raw in weights.items():
        weight = _finite_number(weight_raw)
        value = _finite_number(node_inputs.get(key))
        if weight is None or value is None:
            return None
        total += float(value) * float(weight)
    activation = inputs.get("activation", "linear")
    if not isinstance(activation, str):
        return None
    activation = activation.strip().lower()
    if activation == "linear":
        return total
    if activation == "relu":
        return max(0.0, total)
    if activation == "sigmoid":
        return 1.0 / (1.0 + math.exp(-total))
    return None


_RECOMPUTE_METHODS = {
    "weighted_gini": _recompute_weighted_gini,
    "total_error": _recompute_total_error,
    "amount_of_say": _recompute_amount_of_say,
    "softmax": _recompute_softmax,
    "cross_entropy": _recompute_cross_entropy,
    "forward_pass": _recompute_forward_pass,
}


# ── Helpers ─────────────────────────────────────────────────────────────────


def _resolve_tolerance(explicit: Any, computation: Any, fact_record: Any, method: str) -> tuple[float, bool]:
    method_default = METHOD_TOLERANCES.get(method, DEFAULT_TOLERANCE)
    candidates: list[Any] = [explicit]
    if isinstance(computation, dict):
        candidates.append(computation.get("tolerance"))
    if isinstance(fact_record, dict):
        candidates.append(fact_record.get("tolerance"))
    invalid = False
    for candidate in candidates:
        if candidate is None:
            continue
        number = _finite_number(candidate)
        if number is None or not (0.0 < number <= MAX_TOLERANCE):
            invalid = True
            continue
        return float(number), invalid
    return method_default, invalid


def _upgrade_provenance(provenance: str) -> str:
    if provenance == "unverified":
        return "computed"
    return provenance


def _downgrade_provenance(provenance: str) -> str:
    if provenance in {"extracted_high", "unverified"}:
        return provenance
    return "unverified"


def _with_tol(tokens: list[str], tol_invalid: bool) -> list[str]:
    if tol_invalid:
        return tokens + ["invalid_tolerance"]
    return tokens


def _result(
    *,
    fact_id: str,
    check_id: str,
    status: str,
    supplied_value: Any,
    recomputed_value: Any,
    tolerance: Any,
    verification_status: str,
    provenance: str,
    blocking: bool,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "check_id": check_id if check_id in CHECK_IDS else "numeric_fact_not_recomputable",
        "status": status if status in CHECK_STATUSES else "unknown",
        "supplied_value": supplied_value if isinstance(supplied_value, (int, float)) and not isinstance(supplied_value, bool) else None,
        "recomputed_value": recomputed_value if isinstance(recomputed_value, (int, float)) and not isinstance(recomputed_value, bool) else None,
        "tolerance": tolerance if isinstance(tolerance, (int, float)) and not isinstance(tolerance, bool) else None,
        "verification_status": verification_status,
        "provenance": provenance if isinstance(provenance, str) else "unverified",
        "blocking": bool(blocking),
        "warnings": _ordered_warnings(warnings),
    }


def _public_check(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "fact_id": result["fact_id"],
        "check_id": result["check_id"],
        "status": result["status"],
        "supplied_value": result["supplied_value"],
        "recomputed_value": result["recomputed_value"],
        "tolerance": result["tolerance"],
        "warnings": list(result["warnings"]),
    }


def _blocking_entry(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "fact_id": result["fact_id"],
        "check_id": result["check_id"],
        "status": "failed",
        "supplied_value": result["supplied_value"],
        "recomputed_value": result["recomputed_value"],
        "tolerance": result["tolerance"],
    }


def _build_report(
    status: str,
    checks: list[dict[str, Any]],
    blocking_failures: list[dict[str, Any]],
    warnings: set[str],
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": KIND,
        "status": status if status in REPORT_STATUSES else "warning",
        "blocking": True,
        "summary": _summary(checks, blocking_failures),
        "checks": checks,
        "blocking_failures": blocking_failures,
        "warnings": _ordered_warnings(warnings),
    }


def _summary(checks: list[dict[str, Any]], blocking_failures: list[dict[str, Any]]) -> dict[str, int]:
    fact_count = len(checks)
    numeric_fact_count = 0
    recomputable_fact_count = 0
    verified_fact_count = 0
    failed_fact_count = 0
    unverified_fact_count = 0
    not_applicable_count = 0
    warning_count = 0
    for check in checks:
        check_id = check.get("check_id")
        status = check.get("status")
        if check_id != "non_numeric_fact_not_applicable":
            numeric_fact_count += 1
        if check.get("recomputed_value") is not None:
            recomputable_fact_count += 1
        if status == "passed":
            verified_fact_count += 1
        elif status == "failed":
            failed_fact_count += 1
        elif status == "not_applicable":
            not_applicable_count += 1
        elif status == "warning":
            warning_count += 1
            unverified_fact_count += 1
        else:  # unknown
            unverified_fact_count += 1
    return {
        "fact_count": max(0, fact_count),
        "numeric_fact_count": max(0, numeric_fact_count),
        "recomputable_fact_count": max(0, recomputable_fact_count),
        "verified_fact_count": max(0, verified_fact_count),
        "failed_fact_count": max(0, failed_fact_count),
        "unverified_fact_count": max(0, unverified_fact_count),
        "not_applicable_count": max(0, not_applicable_count),
        "warning_count": max(0, warning_count),
        "blocking_failure_count": max(0, len(blocking_failures)),
    }


def _report_status(
    checks: list[dict[str, Any]],
    blocking_failures: list[dict[str, Any]],
    warnings: set[str],
) -> str:
    if not checks and "fact_sheet_missing" in warnings:
        return "skipped"
    if blocking_failures:
        return "failed"
    if "max_items_reached" in warnings:
        return "partial"
    if not checks:
        return "skipped"
    has_warning = any(check.get("status") in {"warning", "unknown"} for check in checks)
    has_verified = any(check.get("status") == "passed" for check in checks)
    if has_warning:
        return "warning"
    if has_verified:
        return "passed"
    return "passed"


def _resolve_max_items(max_items: Any) -> int:
    if isinstance(max_items, bool):
        return _DEFAULT_MAX_FACTS
    if isinstance(max_items, int):
        return max(0, max_items)
    return _DEFAULT_MAX_FACTS


def _safe_fact_id(value: Any) -> str:
    if not isinstance(value, str):
        return "fact_unknown"
    candidate = value.strip()
    if not candidate or len(candidate) > 80:
        return "fact_unknown"
    for char in candidate:
        if not (char.isalnum() or char in "._-"):
            return "fact_unknown"
    return candidate


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return value


def _ordered_warnings(warnings: Any) -> list[str]:
    seen = set(warnings) if isinstance(warnings, (set, list, tuple)) else set()
    return [token for token in WARNING_ORDER if token in seen]
