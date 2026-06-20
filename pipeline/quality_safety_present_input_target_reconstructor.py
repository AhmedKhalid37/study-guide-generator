"""Quality Safety **present-input target reconstructor** (Slice 176E).

Revised Slice 176D classified five Ensemble numeric targets as
``computation_input_present`` *on the strength of prior committed closed evidence*
(173C recoverability + a single Gini masked spot-check), but proved that **no parsed
machine-consumable source-input record exists yet** (``machine_consumable_now=false``
for all). This slice is the **validation test** for exactly **one** of those
input-present targets:

    Does the selected target's computation-**input** table actually exist in the
    source deck in a form the local extractor/reconstructor can find and parse —
    when the region is **rediscovered cold from extraction signals**, with no
    hand-located region, no prior spot-check hint, no fixture value, and no answer
    value supplied to the parser?

If yes (integer class-count rows parse cold and a masked recompute yields a finite
value), 176D's optimistic classification earns one real validation point. If the
region only confirms an answer/result table (the Gini *values*, decimals in (0,1)),
or no input region is found, then 176D's ``computation_input_present`` for that
target was prior-evidence optimism — **not** source-confirmed truth — and this slice
records that honestly instead of laundering it.

This module is **not**: another recoverability audit, a source-input bridge, numeric
plumbing, a prompt/generation slice, a visual-manifest rebuild, a generic table
framework, proximity target-region detection, generation wiring, a Layer-2 judge, or
repair. No Chandra; no cloud OCR; no provider/model generation. ``judge_ready=false``;
``repair_ready=false``.

No-laundering / provenance rules (non-negotiable):
  * A source-input record is **created + machine-consumable** ONLY when its integer
    class-count groups are parsed from the reconstructed grid (origin
    ``parsed_from_extraction_output``) and recompute the weighted-Gini quantity with
    the answer masked from the parser.
  * The Gini **value** (a decimal in (0,1)) is the **answer**, never an input. A grid
    whose only numerics are unit-interval decimals is refused
    (``blocked_by=source_input_mapping``, ``answer_matrix_not_input``).
  * Hand-located regions, prior spot-check region hints, fixture values, extracted
    answer strings, and generated-guide candidate values are **never** inputs; if the
    parser is handed a hand-located/spot-check region it refuses to create a record.

Purity & safety: stdlib only, plus the committed grid clusterer reused from the
176C reconstructor (``_reconstruct_grid`` — not a parallel grid engine) and the pure
``SUPPORTED_METHODS`` / ``recompute_quality_safety_fact`` from the recompute verifier
(reuse, not a parallel recompute engine). No FastAPI / frontend / provider / model /
cloud / OCR / fitz / render / job-runtime imports. The committed ``record`` carries
only closed tokens, ints, and bools — no guide / source / OCR / table text, snippets,
copied formulas, raw input values, paths, filenames, hashes, or byte counts. Real
parsed values, when present, live only in the separate ``recompute_input`` channel the
caller may feed to the verifier and must never commit.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.quality_safety_one_table_family_row_cell_reconstructor import (
    _reconstruct_grid,
)
from pipeline.quality_safety_recompute_verifier import (
    SUPPORTED_METHODS,
    recompute_quality_safety_fact,
)

VERSION = 1
KIND = "quality_safety_present_input_target_reconstruction_attempt"
ARTIFACT_NAME = "quality_safety_present_input_target_reconstruction_attempt"

SOURCE_LABEL_DEFAULT = "ensemble"

# The five input-present candidates from revised 176D (proximity_4_3 is answer-only
# and weighted_weight_impute is inconclusive — both excluded by scope).
PRESENT_INPUT_CANDIDATES = frozenset(
    {
        "gini_chest_pain",
        "gini_blocked_arteries",
        "gini_weight_gt_176",
        "total_error_stump_1",
        "amount_of_say_half_ln_7",
    }
)

# Only the weighted_gini family is implemented this slice (one target, simplest
# class-count mapping; total_error / amount_of_say chain a downstream formula first).
SUPPORTED_FAMILIES = frozenset({"weighted_gini"})

# ── Closed vocabularies (this module owns what it emits) ─────────────────────
STATUSES = frozenset({"parsed", "blocked", "skipped"})
TARGET_FAMILIES = frozenset(
    {"weighted_gini", "total_error", "amount_of_say", "unknown"}
)
INPUT_EXISTENCE_STATUSES = frozenset(
    {
        "computation_input_present",
        "answer_output_only",
        "absent_or_not_found",
        "inconclusive",
    }
)
TARGET_REGION_STATUSES = frozenset({"found", "not_found", "ambiguous"})
CROP_REGION_INPUT_STATUSES = frozenset({"available", "unavailable", "unsafe"})
LOCAL_OCR_STATUSES = frozenset({"ran", "unavailable", "empty", "skipped"})
ROW_CELL_STATUSES = frozenset(
    {
        "parsed_from_extraction_output",
        "ocr_prose_only",
        "ambiguous_grid",
        "no_rows_detected",
        "no_cells_detected",
        "target_region_missing",
        "blocked",
    }
)
SOURCE_INPUT_RECORD_STATUSES = frozenset({"created", "not_created"})
SOURCE_INPUT_ORIGINS = frozenset({"parsed_from_extraction_output", "none"})
INPUTS_STATUSES = frozenset({"complete", "incomplete", "unavailable"})
MASKED_RECOMPUTE_STATUSES = frozenset(
    {"passed", "failed", "not_run", "not_supported_without_new_plumbing"}
)

# Patched 176E provenance / source-confirmation vocabularies.
INPUT_PRESENCE_CLAIM_BASES = frozenset(
    {"prior_closed_evidence", "source_confirmed_this_slice", "inconclusive"}
)
INPUT_PRESENCE_CONFIRMED = frozenset({"true", "false", "inconclusive"})
SOURCE_CONFIRMATION_STATUSES = frozenset(
    {
        "computation_input_rows_confirmed",
        "answer_output_only_confirmed",
        "no_input_region_found",
        "ocr_or_region_inconclusive",
        "not_checked",
    }
)
SELECTED_REGION_ORIGINS = frozenset(
    {
        "discovered_from_extraction",
        "discovered_from_closed_candidate_metadata",
        "hand_located_spot_check",
        "unknown",
        "none",
    }
)

# Selection vocabularies (Part 1B).
SELECTION_REASONS = frozenset(
    {
        "strongest_input_presence_evidence",
        "simplest_row_cell_mapping",
        "prior_masked_spot_check_evidence",
        "cleaner_extraction_region",
        "fallback_tie_breaker",
    }
)
NON_SELECTED_REASONS = frozenset(
    {
        "deferred_by_scope",
        "weaker_input_presence_evidence",
        "harder_mapping",
        "inconclusive",
        "answer_output_only",
    }
)

BLOCKED_BY_TOKENS = frozenset(
    {
        "none",
        "target_region_detection",
        "crop_unavailable",
        "ocr_unavailable",
        "ocr_empty",
        "row_cell_reconstruction",
        "ambiguous_grid",
        "source_input_mapping",
        "privacy_boundary",
        "unsupported_method",
        "scope_too_large",
    }
)
NEXT_STEPS = frozenset(
    {
        "wire_parsed_rows_into_recompute",
        "refine_present_input_target_reconstructor",
        "choose_different_input_present_target",
        "improve_input_region_evidence",
        "pivot_table_reconstruction_to_student_visible_tables",
    }
)
WARNING_ORDER = (
    "region_input_unavailable",
    "no_rows_detected",
    "no_cells_detected",
    "ambiguous_grid",
    "answer_matrix_not_input",
    "no_input_columns_found",
    "unsupported_target_family",
    "hand_located_region_refused",
    "spot_check_hint_refused",
    "inputs_incomplete",
    "masked_recompute_failed",
    "malformed_tokens_degraded",
)

_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_INT_RE = re.compile(r"^\d+$")


# ── Public API ───────────────────────────────────────────────────────────────


def reconstruct_present_input_target(
    *,
    source_label: str = SOURCE_LABEL_DEFAULT,
    target_id: str,
    target_family: str = "weighted_gini",
    input_existence_status_from_176d: str = "computation_input_present",
    positioned_tokens: Any = None,
    selected_region_origin: str = "discovered_from_extraction",
    parser_received_hand_located_region: bool = False,
    parser_received_spot_check_region_hint: bool = False,
    local_ocr_status: str = "skipped",
    row_y_tolerance: float = 3.0,
) -> dict[str, Any]:
    """Attempt to reconstruct ONE input-present target's class-count rows cold.

    ``positioned_tokens`` is a closed list of ``{"x","y","text"}`` for a region the
    caller **rediscovered from extraction/candidate signals** (never a hand-located
    or spot-check region). The function reconstructs the grid, maps integer
    class-count rows to weighted-Gini inputs (refusing the unit-interval Gini answer
    cells), and runs an advisory **masked** recompute (answer never supplied).

    Returns ``{"version","kind","record","recompute_input"}`` where ``record`` is
    closed (no values) and ``recompute_input`` — present only when a real
    machine-consumable record was created — carries the ``{method, inputs, ...}`` the
    caller may feed to the verifier and must never commit. Pure, total, offline;
    never raises.
    """
    try:
        return _attempt(
            source_label,
            target_id,
            target_family,
            input_existence_status_from_176d,
            positioned_tokens,
            selected_region_origin,
            parser_received_hand_located_region,
            parser_received_spot_check_region_hint,
            local_ocr_status,
            row_y_tolerance,
        )
    except Exception:
        return _envelope(
            _blocked_record(
                source_label,
                target_id,
                "weighted_gini",
                input_existence_status_from_176d,
                selected_region_origin="unknown",
                row_cell_status="blocked",
                blocked_by="row_cell_reconstruction",
                source_confirmation_status="ocr_or_region_inconclusive",
                input_presence_confirmed="inconclusive",
                warnings=["malformed_tokens_degraded"],
                next_step="refine_present_input_target_reconstructor",
            ),
            None,
        )


# ── Driver ───────────────────────────────────────────────────────────────────


def _attempt(
    source_label: Any,
    target_id: Any,
    target_family: Any,
    existence_status: Any,
    positioned_tokens: Any,
    selected_region_origin: Any,
    hand_located: Any,
    spot_check_hint: Any,
    local_ocr_status: Any,
    row_y_tolerance: Any,
) -> dict[str, Any]:
    source_label = (
        source_label if isinstance(source_label, str) and source_label else SOURCE_LABEL_DEFAULT
    )
    target_id = target_id if isinstance(target_id, str) and target_id else "unknown_target"
    family = target_family if target_family in TARGET_FAMILIES else "unknown"
    existence_status = (
        existence_status if existence_status in INPUT_EXISTENCE_STATUSES else "inconclusive"
    )
    region_origin = (
        selected_region_origin
        if selected_region_origin in SELECTED_REGION_ORIGINS
        else "unknown"
    )
    ocr_status = local_ocr_status if local_ocr_status in LOCAL_OCR_STATUSES else "skipped"

    # Provenance guard — a hand-located region or a prior spot-check hint can NEVER
    # produce a valid created record (this is exactly the laundering 176E forbids).
    if bool(hand_located) or bool(spot_check_hint):
        warns = []
        if bool(hand_located):
            warns.append("hand_located_region_refused")
        if bool(spot_check_hint):
            warns.append("spot_check_hint_refused")
        return _envelope(
            _blocked_record(
                source_label, target_id, family, existence_status,
                selected_region_origin="hand_located_spot_check",
                hand_located=bool(hand_located),
                spot_check_hint=bool(spot_check_hint),
                row_cell_status="blocked",
                blocked_by="privacy_boundary",
                source_confirmation_status="not_checked",
                input_presence_confirmed="inconclusive",
                input_presence_claim_basis="inconclusive",
                warnings=warns,
                next_step="improve_input_region_evidence",
                local_ocr_status=ocr_status,
            ),
            None,
        )

    if family not in SUPPORTED_FAMILIES:
        return _envelope(
            _blocked_record(
                source_label, target_id, family, existence_status,
                selected_region_origin=region_origin,
                row_cell_status="blocked",
                blocked_by="unsupported_method",
                source_confirmation_status="not_checked",
                input_presence_confirmed="inconclusive",
                warnings=["unsupported_target_family"],
                next_step="refine_present_input_target_reconstructor",
                local_ocr_status=ocr_status,
            ),
            None,
        )

    # Region/crop input availability (rediscovered region tokens, never hand-located).
    if not isinstance(positioned_tokens, list) or not positioned_tokens:
        return _envelope(
            _blocked_record(
                source_label, target_id, family, existence_status,
                selected_region_origin=region_origin,
                target_region_status="not_found",
                crop_region_input_status="unavailable",
                row_cell_status="target_region_missing",
                blocked_by="target_region_detection",
                source_confirmation_status="no_input_region_found",
                input_presence_confirmed="inconclusive",
                warnings=["region_input_unavailable"],
                next_step="improve_input_region_evidence",
                local_ocr_status=ocr_status,
            ),
            None,
        )

    grid = _reconstruct_grid(positioned_tokens, row_y_tolerance)
    rows_count = len(grid)
    cols_count = max((len(r) for r in grid), default=0)
    numeric_cells = sum(1 for r in grid for c in r if _NUM_RE.match(c))

    if rows_count == 0:
        return _envelope(
            _blocked_record(
                source_label, target_id, family, existence_status,
                selected_region_origin=region_origin,
                target_region_status="not_found",
                crop_region_input_status="available",
                row_cell_status="no_rows_detected",
                blocked_by="row_cell_reconstruction",
                source_confirmation_status="ocr_or_region_inconclusive",
                input_presence_confirmed="inconclusive",
                warnings=["no_rows_detected"],
                next_step="improve_input_region_evidence",
                local_ocr_status=ocr_status,
            ),
            None,
        )

    method, inputs, warn, blocked_by, confirmation = _map_weighted_gini(
        positioned_tokens, grid, row_y_tolerance
    )

    if method is None or inputs is None:
        # Distinguish answer-only (Gini values found, no inputs) from no-input-region.
        if confirmation == "answer_output_only_confirmed":
            confirmed = "false"
            claim_basis = "prior_closed_evidence"
            next_step = "choose_different_input_present_target"
        else:
            confirmed = "inconclusive"
            claim_basis = "inconclusive"
            next_step = "improve_input_region_evidence"
        return _envelope(
            _blocked_record(
                source_label, target_id, family, existence_status,
                selected_region_origin=region_origin,
                target_region_status="found",
                crop_region_input_status="available",
                row_cell_status="parsed_from_extraction_output",
                blocked_by=blocked_by,
                source_confirmation_status=confirmation,
                input_presence_confirmed=confirmed,
                input_presence_claim_basis=claim_basis,
                warnings=warn,
                next_step=next_step,
                rows_count=rows_count, cols_count=cols_count, numeric_cells=numeric_cells,
                local_ocr_status=ocr_status,
            ),
            None,
        )

    # Genuine integer class-count inputs parsed — masked recompute (answer hidden).
    masked_status = _masked_recompute(method, inputs)
    if masked_status != "passed":
        return _envelope(
            _blocked_record(
                source_label, target_id, family, existence_status,
                selected_region_origin=region_origin,
                target_region_status="found",
                crop_region_input_status="available",
                row_cell_status="parsed_from_extraction_output",
                blocked_by="row_cell_reconstruction",
                source_confirmation_status="ocr_or_region_inconclusive",
                input_presence_confirmed="inconclusive",
                warnings=list(warn) + ["masked_recompute_failed"],
                next_step="refine_present_input_target_reconstructor",
                rows_count=rows_count, cols_count=cols_count, numeric_cells=numeric_cells,
                masked_recompute_status=masked_status,
                local_ocr_status=ocr_status,
            ),
            None,
        )

    record = _record(
        source_label=source_label,
        target_id=target_id,
        target_family=family,
        existence_status=existence_status,
        status="parsed",
        selected_region_origin=region_origin,
        target_region_status="found",
        crop_region_input_status="available",
        local_ocr_status=ocr_status,
        row_cell_extraction_status="parsed_from_extraction_output",
        structured_rows_count=rows_count,
        structured_columns_count=cols_count,
        numeric_cells_count=numeric_cells,
        source_input_record_status="created",
        source_input_origin="parsed_from_extraction_output",
        machine_consumable_for_recompute=True,
        masked_recompute_status="passed",
        input_presence_claim_basis="source_confirmed_this_slice",
        input_presence_confirmed="true",
        source_confirmation_status="computation_input_rows_confirmed",
        blocked_by="none",
        warnings=list(warn),
        next_step="wire_parsed_rows_into_recompute",
        inputs_status="complete",
    )
    recompute_input = {
        "method": method,
        "inputs": inputs,
        "value_kind": "numeric",
        "confidence": "medium",
        "origin": "parsed_from_extraction_output",
        "target_id": target_id,
        "source_label": source_label,
        "target_family": family,
    }
    return _envelope(record, recompute_input)


# ── weighted_gini mapper (return method, inputs, warnings, blocked_by, confirm) ─


def _map_weighted_gini(positioned_tokens: Any, grid: list[list[str]], ytol: Any):
    """Map a reconstructed region to weighted_gini inputs, refusing the Gini answer.

    Legitimate inputs are an **x-column-aligned integer grid**: >= 2 child-node rows,
    each contributing integers to >= 2 *shared* columns (a real class-count table).
    The column-alignment requirement is the credibility guard that distinguishes a
    genuine class-count table from **coincidental** integers scattered across
    unrelated lines — magnitude-agnostic and answer-agnostic (no thresholds tuned to
    any expected value). Inputs shape: ``{"groups": [{"c0": n, ...}, ...]}``.

    The weighted-Gini **value** is a decimal in (0,1) — the *answer*, never an input;
    a region whose only numerics are unit-interval decimals is refused as answer-only.
    """
    warnings: list[str] = []
    groups = _aligned_integer_groups(positioned_tokens, ytol)
    if groups:
        return "weighted_gini", {"groups": groups}, warnings, "none", "computation_input_rows_confirmed"

    # Anti-laundering: unit-interval decimals are Gini *values* (answers), not inputs.
    decimals_in_unit = sum(
        1
        for row in grid
        for c in row
        if _NUM_RE.match(c) and not _INT_RE.match(c) and 0.0 < _to_float(c) < 1.0
    )
    if decimals_in_unit >= 1:
        warnings.append("answer_matrix_not_input")
        return None, None, warnings, "source_input_mapping", "answer_output_only_confirmed"

    warnings.append("no_input_columns_found")
    return None, None, warnings, "row_cell_reconstruction", "no_input_region_found"


def _aligned_integer_groups(positioned_tokens: Any, ytol: Any, xtol: float = 6.0):
    """Return class-count groups ONLY when integers form a real x-aligned grid.

    A credible class-count table requires >= 2 shared x-columns (each populated by
    >= 2 integer cells) and >= 2 rows that each place an integer in >= 2 of those
    shared columns. Coincidental integer pairs on unrelated lines do not share
    columns and are rejected. Pure / total; returns ``[]`` when not credible.
    """
    if not isinstance(positioned_tokens, list):
        return []
    try:
        ytolerance = float(ytol)
    except (TypeError, ValueError):
        ytolerance = 3.0
    if ytolerance <= 0:
        ytolerance = 3.0

    cells: list[tuple[float, float, int]] = []
    for tok in positioned_tokens:
        if not isinstance(tok, dict):
            continue
        x = _coerce_float(tok.get("x"))
        y = _coerce_float(tok.get("y"))
        text = tok.get("text")
        if x is None or y is None or not isinstance(text, str):
            continue
        t = text.strip()
        if _INT_RE.match(t):
            cells.append((x, y, int(t)))
    if len(cells) < 4:
        return []

    # Cluster integer cells into shared x-columns.
    columns: list[dict[str, Any]] = []  # {"x": center, "cells": [(y, val)]}
    for x, y, val in sorted(cells, key=lambda c: c[0]):
        placed = False
        for col in columns:
            if abs(col["x"] - x) <= xtol:
                col["cells"].append((y, val))
                col["x"] = (col["x"] * (len(col["cells"]) - 1) + x) / len(col["cells"])
                placed = True
                break
        if not placed:
            columns.append({"x": x, "cells": [(y, val)]})
    shared_columns = [c for c in columns if len(c["cells"]) >= 2]
    if len(shared_columns) < 2:
        return []

    # Build rows (by y) restricted to shared columns; keep rows touching >= 2 columns.
    shared_columns.sort(key=lambda c: c["x"])
    rows: list[dict[str, Any]] = []
    for col_idx, col in enumerate(shared_columns):
        for y, val in col["cells"]:
            placed = False
            for row in rows:
                if abs(row["y"] - y) <= ytolerance:
                    row["cells"][col_idx] = val
                    placed = True
                    break
            if not placed:
                rows.append({"y": y, "cells": {col_idx: val}})

    groups: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: r["y"]):
        ordered = [row["cells"][i] for i in sorted(row["cells"])]
        if len(ordered) >= 2 and any(n > 0 for n in ordered) and all(n >= 0 for n in ordered):
            groups.append({f"c{i}": n for i, n in enumerate(ordered)})
    return groups if len(groups) >= 2 else []


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


# ── Masked recompute (reuse the real verifier, answer hidden) ────────────────


def _masked_recompute(method: str, inputs: dict[str, Any]) -> str:
    if method not in SUPPORTED_METHODS:
        return "not_run"
    fact = {
        "id": "masked_weighted_gini",
        "type": "numeric",
        "value": None,
        "provenance": "unverified",
        "computation": {"method": method, "inputs": inputs},
    }
    result = recompute_quality_safety_fact(fact)
    recomputed = result.get("recomputed_value") if isinstance(result, dict) else None
    return "passed" if isinstance(recomputed, (int, float)) else "failed"


# ── Record assembly (closed vocabulary only) ─────────────────────────────────


def _record(
    *,
    source_label: str,
    target_id: str,
    target_family: str,
    existence_status: str,
    status: str,
    selected_region_origin: str,
    target_region_status: str,
    crop_region_input_status: str,
    local_ocr_status: str,
    row_cell_extraction_status: str,
    structured_rows_count: int,
    structured_columns_count: int,
    numeric_cells_count: int,
    source_input_record_status: str,
    source_input_origin: str,
    machine_consumable_for_recompute: bool,
    masked_recompute_status: str,
    input_presence_claim_basis: str,
    input_presence_confirmed: str,
    source_confirmation_status: str,
    blocked_by: str,
    warnings: list[str],
    next_step: str,
    inputs_status: str,
    hand_located: bool = False,
    spot_check_hint: bool = False,
) -> dict[str, Any]:
    return {
        "artifact_name": ARTIFACT_NAME,
        "source_label": source_label,
        "selected_source_label": source_label,
        "selected_target_id": target_id,
        "selected_target_family": target_family if target_family in TARGET_FAMILIES else "unknown",
        "input_existence_status_from_176d": _tok(
            existence_status, INPUT_EXISTENCE_STATUSES, "inconclusive"
        ),
        "status": status if status in STATUSES else "blocked",
        "selected_region_origin": _tok(selected_region_origin, SELECTED_REGION_ORIGINS, "unknown"),
        "parser_received_hand_located_region": bool(hand_located),
        "parser_received_spot_check_region_hint": bool(spot_check_hint),
        "target_region_status": _tok(target_region_status, TARGET_REGION_STATUSES, "not_found"),
        "crop_or_region_input_status": _tok(
            crop_region_input_status, CROP_REGION_INPUT_STATUSES, "unavailable"
        ),
        "local_ocr_status": _tok(local_ocr_status, LOCAL_OCR_STATUSES, "skipped"),
        "row_cell_extraction_status": _tok(row_cell_extraction_status, ROW_CELL_STATUSES, "blocked"),
        "structured_rows_count": int(structured_rows_count),
        "structured_columns_count": int(structured_columns_count),
        "numeric_cells_count": int(numeric_cells_count),
        "source_input_record_status": _tok(
            source_input_record_status, SOURCE_INPUT_RECORD_STATUSES, "not_created"
        ),
        "source_input_origin": _tok(source_input_origin, SOURCE_INPUT_ORIGINS, "none"),
        "inputs_status": _tok(inputs_status, INPUTS_STATUSES, "unavailable"),
        "machine_consumable_for_recompute": bool(machine_consumable_for_recompute),
        "masked_recompute_status": _tok(masked_recompute_status, MASKED_RECOMPUTE_STATUSES, "not_run"),
        "input_presence_claim_basis": _tok(
            input_presence_claim_basis, INPUT_PRESENCE_CLAIM_BASES, "inconclusive"
        ),
        "input_presence_confirmed_against_source": _tok(
            input_presence_confirmed, INPUT_PRESENCE_CONFIRMED, "inconclusive"
        ),
        "source_confirmation_status": _tok(
            source_confirmation_status, SOURCE_CONFIRMATION_STATUSES, "not_checked"
        ),
        "hand_authored_rows": False,
        "fixture_derived": False,
        "answer_string_derived": False,
        "guide_candidate_derived": False,
        "raw_values_committed": False,
        "raw_ocr_committed": False,
        "blocked_by": _tok(blocked_by, BLOCKED_BY_TOKENS, "row_cell_reconstruction"),
        "next_step": _tok(next_step, NEXT_STEPS, "refine_present_input_target_reconstructor"),
        "warnings": _ordered_warnings(warnings),
    }


def _blocked_record(
    source_label: str,
    target_id: str,
    target_family: str,
    existence_status: str,
    *,
    selected_region_origin: str,
    row_cell_status: str,
    blocked_by: str,
    source_confirmation_status: str,
    input_presence_confirmed: str,
    warnings: list[str],
    next_step: str,
    input_presence_claim_basis: str = "prior_closed_evidence",
    target_region_status: str = "not_found",
    crop_region_input_status: str = "unavailable",
    local_ocr_status: str = "skipped",
    rows_count: int = 0,
    cols_count: int = 0,
    numeric_cells: int = 0,
    masked_recompute_status: str = "not_run",
    hand_located: bool = False,
    spot_check_hint: bool = False,
) -> dict[str, Any]:
    return _record(
        source_label=source_label,
        target_id=target_id,
        target_family=target_family,
        existence_status=existence_status,
        status="blocked",
        selected_region_origin=selected_region_origin,
        target_region_status=target_region_status,
        crop_region_input_status=crop_region_input_status,
        local_ocr_status=local_ocr_status,
        row_cell_extraction_status=row_cell_status,
        structured_rows_count=rows_count,
        structured_columns_count=cols_count,
        numeric_cells_count=numeric_cells,
        source_input_record_status="not_created",
        source_input_origin="none",
        machine_consumable_for_recompute=False,
        masked_recompute_status=masked_recompute_status,
        input_presence_claim_basis=input_presence_claim_basis,
        input_presence_confirmed=input_presence_confirmed,
        source_confirmation_status=source_confirmation_status,
        blocked_by=blocked_by,
        warnings=warnings,
        next_step=next_step,
        inputs_status="unavailable",
        hand_located=hand_located,
        spot_check_hint=spot_check_hint,
    )


def _envelope(record: dict[str, Any], recompute_input: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": KIND,
        "record": record,
        "recompute_input": recompute_input,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _to_float(text: str) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _tok(value: Any, allowed: Any, default: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return default


def _ordered_warnings(warnings: Any) -> list[str]:
    seen = set(warnings) if isinstance(warnings, (set, list, tuple)) else set()
    return [token for token in WARNING_ORDER if token in seen]
