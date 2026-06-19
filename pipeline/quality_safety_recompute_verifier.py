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


# ── Slice 173A: golden-target recompute proof ────────────────────────────────
#
# Recompute-FIRST proof layer over the committed golden-pair numeric targets. Its
# only job is to prove, with closed records, that:
#   (a) the recompute engine can INDEPENDENTLY derive a committed golden fixture
#       value from committed public-safe metadata (here: the parameters encoded in
#       the committed golden *label* itself, e.g. ``cross_entropy_neg_ln_0.57`` →
#       ``-ln(0.57)`` and ``amount_of_say_half_ln_7`` → ``0.5·ln(7)`` via the
#       algebraic identity ``total_error = 1/(N+1)``), and verify it matches the
#       committed expected value within the EXISTING fixture tolerance; and
#   (b) when a (closed) guide-candidate classification is supplied, the verifier
#       can diagnose a currently-printed WRONG value — a DIAGNOSTIC only.
#
# No-laundering rule (Slice 173A correction): a committed fixture value is
# ``writer_should_receive_committed_value=true`` / generation-ready ONLY when it
# was INDEPENDENTLY recomputed or formula-verified, matched the committed fixture
# within the EXISTING tolerance, and confidence is high/medium. Detecting a wrong
# printed value, or the mere existence of a committed expected value, NEVER makes a
# target writer-ready. ``source_required`` / ``unsupported`` / ``verifier_error``
# targets are never writer-ready here; making them generation-ready is Slice 173B's
# job (source-derived computation inputs or a closed fallback), not fixture-value
# injection. The record distinguishes the four facts explicitly:
# ``wrong_printed_value_detected_when_candidate_supplied`` (diagnostic),
# ``committed_value_available`` (fixture has a value),
# ``independently_verified_for_generation`` (recompute proof), and
# ``writer_should_receive_committed_value`` (policy, derived ONLY from the proof).
#
# It NEVER invents a value, never carries a manual answer/``known_numbers`` table
# (every recomputed value is derived from a closed formula plan parsed only from
# the already-committed label), never edits a fixture expected value/tolerance,
# never loosens the numeric matcher, and never touches generation. Targets whose
# committed metadata does not encode the inputs degrade honestly to
# ``source_required`` (a supported method exists but inputs are not available from
# committed metadata) or ``unsupported`` (no supported recompute method). Output is
# closed tokens / counts only: no guide text, snippets, candidate values, source
# text, paths, filenames, hashes, or byte counts.

GOLDEN_PROOF_KIND = "quality_safety_golden_recompute_proof"
GOLDEN_PROOF_SUMMARY_KIND = "quality_safety_golden_recompute_proof_summary"

GOLDEN_RECOMPUTE_STATUSES = frozenset(
    {"recomputed", "formula_verified", "source_required", "unsupported", "verifier_error"}
)
GOLDEN_VALUE_KINDS = frozenset(
    {"numeric", "percentage", "probability", "expression", "unavailable"}
)
GOLDEN_CONFIDENCE_LEVELS = frozenset({"high", "medium", "low", "none"})

# Closed guide-candidate statuses, derived read-only from the eval-harness numeric
# matcher's closed per-target classification (never from a raw candidate value).
GOLDEN_CANDIDATE_STATUSES = frozenset(
    {
        "wrong_value_detected",
        "matched",
        "format_or_context_missed",
        "missing",
        "not_supplied",
        "unknown",
    }
)
# Closed numeric-matcher classification tokens this layer consumes (read-only).
_MATCHER_WRONG = "found_but_wrong_value"
_MATCHER_MISSING = "genuinely_missing"
_MATCHER_FORMAT = "found_but_format_or_context_missed"
_MATCHER_MATCHED = "found_and_matched"

GOLDEN_PROOF_WARNING_ORDER = (
    "golden_spec_missing",
    "golden_spec_invalid",
    "no_numeric_targets",
    "unexpected_source_label",
    "recompute_plan_unavailable",
    "unsupported_method",
    "recompute_disagrees_with_committed_fixture",
    "candidate_classification_ignored",
    "verifier_error",
)

GOLDEN_PROOF_BLOCKING_ISSUES = frozenset(
    {"recompute_disagrees_with_committed_fixture", "verifier_error"}
)

# Concept families mapped to a SUPPORTED recompute method, used ONLY to tell
# ``source_required`` (a supported method exists but committed metadata lacks the
# inputs) apart from ``unsupported`` (no supported method) when no closed formula
# plan is derivable from the label. This is a closed prefix map over committed
# golden labels; it carries no answer values.
_GOLDEN_METHOD_FAMILIES: tuple[tuple[str, str], ...] = (
    ("cross_entropy", "cross_entropy"),
    ("softmax", "softmax"),
    ("gini", "weighted_gini"),
    ("total_error", "total_error"),
    ("amount_of_say", "amount_of_say"),
    ("htop", "forward_pass"),
    ("rset", "forward_pass"),
    ("rver", "forward_pass"),
    ("rsetosa", "forward_pass"),
)

_GOLDEN_MAX_TARGETS = 64


def golden_label_recompute_plan(label: Any) -> dict[str, Any] | None:
    """Return a closed recompute plan derivable PURELY from the committed label.

    Public-safe and recompute-first: parses only the already-committed golden
    label string into a ``{method, inputs, value_kind}`` plan for the existing
    recompute methods. Returns ``None`` when the label does not encode the inputs.
    Never reads source material; never consults an answer table.
    """
    if not isinstance(label, str):
        return None
    text = label.strip()

    prefix = "cross_entropy_neg_ln_"
    if text.startswith(prefix):
        probability = _parse_label_float(text[len(prefix):])
        if probability is None or not (0.0 < probability <= 1.0):
            return None
        return {
            "method": "cross_entropy",
            "inputs": {"probability": probability},
            "value_kind": "numeric",
        }

    prefix = "amount_of_say_half_ln_"
    if text.startswith(prefix):
        ratio = _parse_label_float(text[len(prefix):])
        if ratio is None or ratio <= 0.0:
            return None
        # half_ln_N ≡ 0.5·ln(N) ≡ 0.5·ln((1-e)/e) with the algebraic identity
        # (1-e)/e = N  ⇒  e = 1/(N+1). This derives the recompute INPUT from the
        # label, then exercises the production amount_of_say method (no answer
        # value is hardcoded).
        total_error = 1.0 / (ratio + 1.0)
        return {
            "method": "amount_of_say",
            "inputs": {"total_error": total_error},
            "value_kind": "numeric",
        }

    return None


def _golden_method_family(label: Any) -> str | None:
    if not isinstance(label, str):
        return None
    text = label.strip().lower()
    for prefix, method in _GOLDEN_METHOD_FAMILIES:
        if text.startswith(prefix):
            return method if method in SUPPORTED_METHODS else None
    return None


def _candidate_status_for(classification: Any) -> str:
    if classification == _MATCHER_WRONG:
        return "wrong_value_detected"
    if classification == _MATCHER_MATCHED:
        return "matched"
    if classification == _MATCHER_FORMAT:
        return "format_or_context_missed"
    if classification == _MATCHER_MISSING:
        return "missing"
    return "unknown"


def build_golden_target_recompute_proof(
    golden_spec: Any,
    *,
    candidate_classification_by_target: Any = None,
) -> dict[str, Any]:
    """Build the closed recompute-proof record set for one golden-pair spec.

    Pure, deterministic, offline. Reads only the committed golden spec
    (``lecture_id`` + ``ground_truth_numerics`` label/value/tolerance) and an
    OPTIONAL closed ``{target_id: matcher_classification}`` map (consumed read-only
    from the eval-harness numeric matcher; never a raw candidate value). For each
    target it derives a closed recompute plan from the committed label, recomputes
    via the existing engine, and verifies the recompute matches the committed
    fixture value within the EXISTING tolerance. Never raises; never echoes guide
    text, candidate values, source text, paths, filenames, hashes, or byte counts.
    """
    try:
        return _build_golden_target_recompute_proof(
            golden_spec, candidate_classification_by_target
        )
    except Exception:
        return {
            "version": VERSION,
            "kind": GOLDEN_PROOF_KIND,
            "source_label": "unknown",
            "records": [],
            "summary": summarize_golden_target_recompute_proof([]),
            "warnings": ["verifier_error"],
        }


def _build_golden_target_recompute_proof(
    golden_spec: Any, candidate_map: Any
) -> dict[str, Any]:
    warnings: set[str] = set()

    if not isinstance(golden_spec, dict):
        warnings.add("golden_spec_missing")
        return _golden_proof_envelope("unknown", [], warnings)

    source_label = golden_spec.get("lecture_id")
    if not isinstance(source_label, str) or not source_label:
        warnings.add("golden_spec_invalid")
        source_label = "unknown"

    targets = golden_spec.get("ground_truth_numerics")
    if not isinstance(targets, list) or not targets:
        warnings.add("no_numeric_targets")
        return _golden_proof_envelope(source_label, [], warnings)

    classification_lookup: dict[str, str] = {}
    if candidate_map is not None:
        if isinstance(candidate_map, dict):
            for key, value in candidate_map.items():
                if isinstance(key, str) and isinstance(value, str):
                    classification_lookup[key] = value
        else:
            warnings.add("candidate_classification_ignored")

    records: list[dict[str, Any]] = []
    for position, item in enumerate(targets[:_GOLDEN_MAX_TARGETS]):
        if not isinstance(item, dict):
            continue
        records.append(
            _golden_target_record(item, position, source_label, classification_lookup, warnings)
        )

    return _golden_proof_envelope(source_label, records, warnings)


def _golden_target_record(
    item: dict[str, Any],
    position: int,
    source_label: str,
    classification_lookup: dict[str, str],
    warnings: set[str],
) -> dict[str, Any]:
    label = item.get("label")
    target_id = label if isinstance(label, str) and label else f"target_{position}"
    expected = _finite_number(item.get("value"))
    committed_available = expected is not None
    tol = _finite_number(item.get("tol"))

    candidate_supplied = target_id in classification_lookup
    candidate_status = (
        _candidate_status_for(classification_lookup.get(target_id))
        if candidate_supplied
        else "not_supplied"
    )

    record_warnings: set[str] = set()
    plan = golden_label_recompute_plan(label)

    recompute_status = "source_required"
    matches_committed: bool | None = None
    value_kind = "unavailable"
    confidence = "none"
    blocking_issue: str | None = None

    if plan is not None and committed_available:
        fact_record = {
            "id": f"golden.{source_label}.{position:04d}",
            "type": "numeric",
            "value": expected,
            "computation": {
                "method": plan["method"],
                "inputs": plan["inputs"],
                **({"tolerance": tol} if tol is not None else {}),
            },
        }
        result = recompute_quality_safety_fact(fact_record)
        status = result.get("status")
        recomputed_value = result.get("recomputed_value")
        if recomputed_value is None:
            # Plan existed but the engine could not derive a value: honest error.
            recompute_status = "verifier_error"
            blocking_issue = "verifier_error"
            record_warnings.add("verifier_error")
        elif status == "passed":
            recompute_status = "formula_verified"
            matches_committed = True
            value_kind = plan.get("value_kind", "numeric")
            confidence = "high"
        else:
            # Recompute ran but disagrees with the committed fixture value.
            recompute_status = "recomputed"
            matches_committed = False
            value_kind = plan.get("value_kind", "numeric")
            confidence = "low"
            blocking_issue = "recompute_disagrees_with_committed_fixture"
            record_warnings.add("recompute_disagrees_with_committed_fixture")
    else:
        family = _golden_method_family(label)
        if family is not None:
            recompute_status = "source_required"
            record_warnings.add("recompute_plan_unavailable")
        else:
            recompute_status = "unsupported"
            record_warnings.add("unsupported_method")

    if not committed_available:
        warnings.add("golden_spec_invalid")

    # Independent-verification gate — the ONLY path to a generation-ready value.
    # A committed fixture value is writer-ready ONLY when the recompute engine
    # INDEPENDENTLY recomputed / formula-verified it, it matched the committed
    # fixture within the EXISTING tolerance, and confidence is high/medium. A value
    # that merely exists in the committed fixture (``source_required`` /
    # ``unsupported`` / ``verifier_error``) is NOT generation-ready and must never
    # be laundered into writer-ready context. No-laundering requirement.
    independently_verified = (
        recompute_status in {"recomputed", "formula_verified"}
        and matches_committed is True
        and confidence in {"high", "medium"}
    )

    # Wrong-printed-value detection is a DIAGNOSTIC only: it proves the currently
    # printed value is wrong, never that the writer should receive the committed
    # value. Null when no candidate classification was supplied.
    if not candidate_supplied:
        wrong_printed_detected: bool | None = None
    else:
        wrong_printed_detected = classification_lookup.get(target_id) == _MATCHER_WRONG

    # Writer-readiness derives ONLY from independent verification — never from the
    # mere existence of a committed fixture value or a detected wrong value.
    writer_should_receive = independently_verified

    warnings.update(record_warnings)

    return {
        "source_label": source_label,
        "target_id": target_id,
        "expected_label": target_id,
        "recompute_status": recompute_status,
        "committed_value_available": bool(committed_available),
        "recomputed_matches_committed_fixture": matches_committed,
        "wrong_printed_value_detected_when_candidate_supplied": wrong_printed_detected,
        "independently_verified_for_generation": bool(independently_verified),
        "verified_value_kind": value_kind if value_kind in GOLDEN_VALUE_KINDS else "unavailable",
        "confidence": confidence if confidence in GOLDEN_CONFIDENCE_LEVELS else "none",
        "blocking_issue": blocking_issue if blocking_issue in GOLDEN_PROOF_BLOCKING_ISSUES else None,
        "guide_candidate_status": candidate_status if candidate_status in GOLDEN_CANDIDATE_STATUSES else "unknown",
        "writer_should_receive_committed_value": writer_should_receive,
        "warnings": _ordered_golden_warnings(record_warnings),
    }


def _golden_proof_envelope(
    source_label: str, records: list[dict[str, Any]], warnings: set[str]
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": GOLDEN_PROOF_KIND,
        "source_label": source_label if isinstance(source_label, str) and source_label else "unknown",
        "records": records,
        "summary": summarize_golden_target_recompute_proof(records),
        "warnings": _ordered_golden_warnings(warnings),
    }


def summarize_golden_target_recompute_proof(records: Any) -> dict[str, Any]:
    """Aggregate closed counts over golden recompute-proof records."""
    rows = records if isinstance(records, list) else []
    summary = {
        "kind": GOLDEN_PROOF_SUMMARY_KIND,
        "target_count": 0,
        "recomputed_count": 0,
        "formula_verified_count": 0,
        "source_required_count": 0,
        "unsupported_count": 0,
        "verifier_error_count": 0,
        "committed_fixture_match_count": 0,
        "wrong_printed_value_detected_count": 0,
        "independently_verified_for_generation_count": 0,
        "writer_should_receive_committed_value_count": 0,
        "unresolved_for_generation_count": 0,
    }
    for record in rows:
        if not isinstance(record, dict):
            continue
        summary["target_count"] += 1
        status = record.get("recompute_status")
        if status == "formula_verified":
            summary["formula_verified_count"] += 1
            summary["recomputed_count"] += 1
        elif status == "recomputed":
            summary["recomputed_count"] += 1
        elif status == "source_required":
            summary["source_required_count"] += 1
        elif status == "unsupported":
            summary["unsupported_count"] += 1
        elif status == "verifier_error":
            summary["verifier_error_count"] += 1
        if record.get("recomputed_matches_committed_fixture") is True:
            summary["committed_fixture_match_count"] += 1
        if record.get("wrong_printed_value_detected_when_candidate_supplied") is True:
            summary["wrong_printed_value_detected_count"] += 1
        independently_verified = record.get("independently_verified_for_generation") is True
        if independently_verified:
            summary["independently_verified_for_generation_count"] += 1
        if record.get("writer_should_receive_committed_value") is True:
            summary["writer_should_receive_committed_value_count"] += 1
        # Unresolved for generation = the guide is not correct AND we have NO
        # independently-verified value to give the writer. A committed fixture value
        # alone does NOT resolve a target (no laundering): source_required /
        # unsupported targets stay unresolved until 173B derives source inputs.
        guide_not_correct = record.get("guide_candidate_status") in {
            "wrong_value_detected",
            "missing",
            "format_or_context_missed",
        }
        if guide_not_correct and not independently_verified:
            summary["unresolved_for_generation_count"] += 1
    return summary


def _parse_label_float(token: Any) -> float | None:
    if not isinstance(token, str):
        return None
    try:
        value = float(token.strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _ordered_golden_warnings(warnings: Any) -> list[str]:
    seen = set(warnings) if isinstance(warnings, (set, list, tuple)) else set()
    return [token for token in GOLDEN_PROOF_WARNING_ORDER if token in seen]


# ── Slice 173B: generation-ready verified numeric records ────────────────────
#
# Export layer that turns the Slice 173A recompute proof into the closed set of
# numeric values that may be handed to the GENERATION writer. It is the single
# no-laundering gate between "the verifier knows a committed value exists" and
# "the writer is allowed to use that value":
#
#   A committed fixture value is emitted as a generation-ready record ONLY when its
#   Slice 173A proof record is ``independently_verified_for_generation=true`` (i.e.
#   ``recompute_status in {recomputed, formula_verified}`` AND
#   ``recomputed_matches_committed_fixture=true`` AND ``confidence in {high,
#   medium}`` AND ``writer_should_receive_committed_value=true``). For every other
#   target the committed value is NEVER read here, so it can never leak into the
#   writer's context: ``source_required`` / ``unsupported`` / ``verifier_error`` and
#   any "recomputed-but-disagrees" target are excluded with closed exclusion counts.
#
# The verified value is the committed golden fixture value (which the recompute
# engine independently reproduced within the EXISTING tolerance) — never a guide
# candidate value, never a fixture-only/unverified value, never an invented value.
# Output is closed: a short student-facing label, a rendered numeric string for
# verified values only, a closed value-kind/confidence token, and the fixed
# ``use_verified_value`` instruction token. No guide text, candidate values, source
# text, snippets, derivations, tolerances, paths, filenames, hashes, or byte counts.

GENERATION_READY_KIND = "quality_safety_generation_ready_numeric_records"
GENERATION_READY_SUMMARY_KIND = "quality_safety_generation_ready_numeric_summary"

# Fixed instruction token the writer consumes for every verified value.
VERIFIED_VALUE_INSTRUCTION_TOKEN = "use_verified_value"

GENERATION_READY_WARNING_ORDER = (
    "golden_spec_missing",
    "verified_value_unrenderable",
    "verifier_error",
)


def build_generation_ready_numeric_records(
    golden_spec: Any,
    *,
    candidate_classification_by_target: Any = None,
) -> dict[str, Any]:
    """Closed generation-ready numeric records for one golden-pair spec.

    Runs the Slice 173A recompute proof, then emits a record carrying the
    committed (recompute-proven) value ONLY for targets that are
    ``independently_verified_for_generation``. Every non-verified target is
    excluded and counted; its committed value is never read. Pure, deterministic,
    offline; never raises; never echoes guide text, candidate values, source text,
    paths, filenames, hashes, or byte counts.
    """
    try:
        return _build_generation_ready_numeric_records(
            golden_spec, candidate_classification_by_target
        )
    except Exception:
        return {
            "version": VERSION,
            "kind": GENERATION_READY_KIND,
            "source_label": "unknown",
            "records": [],
            "summary": _summarize_generation_ready([], records_seen=0, excluded={}),
            "warnings": ["verifier_error"],
        }


def _build_generation_ready_numeric_records(
    golden_spec: Any, candidate_map: Any
) -> dict[str, Any]:
    warnings: set[str] = set()

    proof = build_golden_target_recompute_proof(
        golden_spec, candidate_classification_by_target=candidate_map
    )
    source_label = proof.get("source_label", "unknown")
    proof_records = proof.get("records")
    proof_records = proof_records if isinstance(proof_records, list) else []

    # Closed committed-value lookup keyed by the SAME target_id the proof uses
    # (the golden label). Built once; consulted ONLY for independently-verified
    # targets so a non-verified committed value is never even read.
    value_lookup: dict[str, Any] = {}
    if isinstance(golden_spec, dict):
        targets = golden_spec.get("ground_truth_numerics")
        if isinstance(targets, list):
            for position, item in enumerate(targets[:_GOLDEN_MAX_TARGETS]):
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                key = label if isinstance(label, str) and label else f"target_{position}"
                value_lookup[key] = _finite_number(item.get("value"))
    else:
        warnings.add("golden_spec_missing")

    records: list[dict[str, Any]] = []
    excluded = {
        "source_required": 0,
        "unsupported": 0,
        "verifier_error": 0,
        "recomputed_disagrees": 0,
    }

    for proof_record in proof_records:
        if not isinstance(proof_record, dict):
            continue
        target_id = proof_record.get("target_id")
        if not isinstance(target_id, str):
            continue

        if proof_record.get("independently_verified_for_generation") is True:
            # No-laundering gate passed: read the committed value (which recompute
            # independently reproduced within tolerance) ONLY now.
            rendered = _render_verified_value(value_lookup.get(target_id))
            if rendered is None:
                warnings.add("verified_value_unrenderable")
                # A verified record whose value cannot be rendered is dropped, not
                # laundered through as an unverified value.
                excluded["verifier_error"] += 1
                continue
            kind = proof_record.get("verified_value_kind")
            confidence = proof_record.get("confidence")
            records.append(
                {
                    "source_label": source_label,
                    "target_id": target_id,
                    "expected_label": proof_record.get("expected_label", target_id),
                    "verified_value_rendered": rendered,
                    "verified_value_kind": kind if kind in GOLDEN_VALUE_KINDS else "numeric",
                    "confidence": confidence if confidence in GOLDEN_CONFIDENCE_LEVELS else "high",
                    "instruction_token": VERIFIED_VALUE_INSTRUCTION_TOKEN,
                }
            )
            continue

        # Excluded: bucket by recompute_status for closed exclusion counts. The
        # committed value is NEVER read for these targets.
        status = proof_record.get("recompute_status")
        if status == "source_required":
            excluded["source_required"] += 1
        elif status == "unsupported":
            excluded["unsupported"] += 1
        elif status == "verifier_error":
            excluded["verifier_error"] += 1
        elif status == "recomputed":
            excluded["recomputed_disagrees"] += 1

    return {
        "version": VERSION,
        "kind": GENERATION_READY_KIND,
        "source_label": source_label if isinstance(source_label, str) and source_label else "unknown",
        "records": records,
        "summary": _summarize_generation_ready(
            records, records_seen=len(proof_records), excluded=excluded
        ),
        "warnings": [token for token in GENERATION_READY_WARNING_ORDER if token in warnings],
    }


def _summarize_generation_ready(
    records: list[dict[str, Any]], *, records_seen: int, excluded: dict[str, int]
) -> dict[str, Any]:
    included = len(records)
    src = int(excluded.get("source_required", 0))
    uns = int(excluded.get("unsupported", 0))
    err = int(excluded.get("verifier_error", 0))
    dis = int(excluded.get("recomputed_disagrees", 0))
    return {
        "kind": GENERATION_READY_SUMMARY_KIND,
        "records_seen": int(records_seen),
        "records_included_for_generation": included,
        "records_excluded_source_required": src,
        "records_excluded_unsupported": uns,
        "records_excluded_verifier_error": err,
        # Umbrella exclusion count = everything that was not independently verified
        # (source_required + unsupported + verifier_error + recomputed-but-disagrees).
        "records_excluded_not_independently_verified": src + uns + err + dis,
        # Hard invariants — these can never be non-zero by construction. Surfaced as
        # closed counts so the dry run can assert the no-laundering guarantee.
        "wrong_candidate_values_included": 0,
        "fixture_only_values_included": 0,
    }


def _render_verified_value(value: Any) -> str | None:
    """Render a recompute-verified numeric value as a closed display string."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        text = f"{value:.6g}"
        return text
    return None
