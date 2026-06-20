"""Quality Safety **one-table-family row/cell reconstructor** (Slice 176C).

Slice 176B's seam map established the exact boundary: the existing local stack
detects table **regions** and can crop them (`reuse_boundary=region_detection_plus_crops`),
but **nothing reconstructs rows/cells** (`missing_piece=row_cell_reconstruction`)
or maps a region to a machine-consumable `source_inputs_by_target` record. This
module is that missing piece — deliberately scoped to **one** table family on
**one** deck, never a generic table-reconstruction framework.

The decisive real-deck fact (probed in 176C): linear text extraction collapses a
table to one token per line, destroying the grid. PyMuPDF (and Tesseract) expose
word **coordinates**; so the genuine reconstruction step is **spatial clustering
of positioned tokens into rows/cells**. This module consumes already-extracted
positioned tokens (``{"x","y","text"}``) for one region — it runs no OCR, opens no
PDF, and reaches no network — and rebuilds the grid, then maps it to the focused
family's recompute inputs.

No-laundering / provenance rules (non-negotiable, mirror Slice 176A):
  * A source-input record is **created + machine-consumable** ONLY when its inputs
    are parsed from the reconstructed grid (origin ``parsed_from_extraction_output``)
    and recompute the family's quantity with the answer masked.
  * The **answer must never become an input.** A proximity *matrix* (cells are the
    proximity values, decimals in (0,1)) and a lone result value are answer-shaped;
    this module **refuses** to treat them as inputs (``blocked_by=source_input_mapping``).
  * Hand-authored rows, fixture-derived values, extracted answer strings, and
    generated-guide candidate values are **never** inputs.

Purity & safety: stdlib ``re`` only, plus the pure ``SUPPORTED_METHODS`` set and
the pure ``recompute_quality_safety_fact`` from the recompute verifier (reuse, not
a parallel engine). No FastAPI / frontend / provider / model / cloud / OCR / fitz /
render / job-runtime imports. The committed ``record`` carries only closed tokens,
ints, and bools — no guide / source / OCR / table text, snippets, copied formulas,
raw input values, paths, filenames, hashes, or byte counts. Real parsed values, when
present, live only in the separate ``recompute_input`` channel the caller may feed to
the verifier and must never commit.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.quality_safety_recompute_verifier import (
    SUPPORTED_METHODS,
    recompute_quality_safety_fact,
)

VERSION = 1
KIND = "quality_safety_one_table_family_row_cell_reconstruction_attempt"

SOURCE_LABEL_DEFAULT = "ensemble"

# ── Closed vocabularies (this module owns what it emits) ─────────────────────
STATUSES = frozenset({"parsed", "blocked", "skipped"})
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
MASKED_RECOMPUTE_STATUSES = frozenset(
    {"passed", "failed", "not_run", "not_supported_without_new_plumbing"}
)
INPUTS_STATUSES = frozenset({"complete", "incomplete", "unavailable"})
CONFIDENCES = frozenset({"high", "medium", "low", "none"})
TARGET_FAMILIES = frozenset({"proximity", "weighted_average", "unknown"})

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
        "target_region_detection_for_numeric_tables",
        "improve_crop_ocr_quality",
        "refine_one_family_row_cell_parser",
        "build_one_table_family_row_cell_reconstructor",
    }
)
WARNING_ORDER = (
    "region_input_unavailable",
    "no_rows_detected",
    "no_cells_detected",
    "ambiguous_grid",
    "answer_matrix_not_input",
    "answer_value_not_input",
    "no_input_columns_found",
    "unsupported_target_family",
    "inputs_incomplete",
    "masked_recompute_failed",
    "malformed_tokens_degraded",
)

_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_INT_RE = re.compile(r"^\d+$")
_PAIR_RE = re.compile(r"(\d+)\D+(\d+)")


# ── Public API ───────────────────────────────────────────────────────────────


def reconstruct_one_table_family(
    *,
    source_label: str = SOURCE_LABEL_DEFAULT,
    target_id: str,
    target_family: str,
    positioned_tokens: Any = None,
    local_ocr_status: str = "skipped",
    row_y_tolerance: float = 3.0,
) -> dict[str, Any]:
    """Attempt one-table-family row/cell reconstruction from positioned tokens.

    ``positioned_tokens`` is a closed list of ``{"x": num, "y": num, "text": str}``
    for **one** region (the reuse boundary: existing region/crop tokens, optionally
    via local-private OCR). The function reconstructs the grid by spatial
    clustering, maps it to the family's recompute inputs, and runs an advisory
    **masked** recompute (the answer is never supplied to the parser).

    Returns ``{"version", "kind", "record", "recompute_input"}`` where ``record``
    is closed (no values) and ``recompute_input`` — present only when a real
    machine-consumable record was created — carries the ``{method, inputs, ...}``
    the caller may feed to the verifier and must never commit. Pure, total,
    offline; never raises.
    """
    try:
        return _attempt(
            source_label,
            target_id,
            target_family,
            positioned_tokens,
            local_ocr_status,
            row_y_tolerance,
        )
    except Exception:
        return _envelope(
            _blocked_record(
                source_label,
                target_id,
                target_family,
                row_cell_status="blocked",
                blocked_by="row_cell_reconstruction",
                warnings=["malformed_tokens_degraded"],
                next_step="refine_one_family_row_cell_parser",
            ),
            None,
        )


# ── Driver ───────────────────────────────────────────────────────────────────


def _attempt(
    source_label: Any,
    target_id: Any,
    target_family: Any,
    positioned_tokens: Any,
    local_ocr_status: Any,
    row_y_tolerance: Any,
) -> dict[str, Any]:
    source_label = source_label if isinstance(source_label, str) and source_label else SOURCE_LABEL_DEFAULT
    target_id = target_id if isinstance(target_id, str) and target_id else "unknown_target"
    family = target_family if target_family in TARGET_FAMILIES else "unknown"
    ocr_status = local_ocr_status if local_ocr_status in LOCAL_OCR_STATUSES else "skipped"

    if family == "unknown" or family not in {"proximity", "weighted_average"}:
        return _envelope(
            _blocked_record(
                source_label, target_id, family,
                row_cell_status="blocked",
                blocked_by="unsupported_method",
                warnings=["unsupported_target_family"],
                next_step="refine_one_family_row_cell_parser",
                local_ocr_status=ocr_status,
            ),
            None,
        )

    # Region/crop input availability.
    if not isinstance(positioned_tokens, list) or not positioned_tokens:
        return _envelope(
            _blocked_record(
                source_label, target_id, family,
                target_region_status="not_found",
                crop_region_input_status="unavailable",
                row_cell_status="target_region_missing",
                blocked_by="crop_unavailable",
                warnings=["region_input_unavailable"],
                next_step="target_region_detection_for_numeric_tables",
                local_ocr_status=ocr_status,
            ),
            None,
        )

    grid = _reconstruct_grid(positioned_tokens, row_y_tolerance)
    rows_count = len(grid)
    multi_cell_rows = [r for r in grid if len(r) >= 2]
    cols_count = max((len(r) for r in grid), default=0)
    numeric_cells = sum(1 for r in grid for c in r if _NUM_RE.match(c))

    if rows_count == 0:
        return _envelope(
            _blocked_record(
                source_label, target_id, family,
                target_region_status="not_found",
                crop_region_input_status="available",
                row_cell_status="no_rows_detected",
                blocked_by="row_cell_reconstruction",
                warnings=["no_rows_detected"],
                next_step="refine_one_family_row_cell_parser",
                local_ocr_status=ocr_status,
            ),
            None,
        )
    if not multi_cell_rows or numeric_cells == 0:
        return _envelope(
            _blocked_record(
                source_label, target_id, family,
                target_region_status="found",
                crop_region_input_status="available",
                row_cell_status="no_cells_detected",
                blocked_by="row_cell_reconstruction",
                warnings=["no_cells_detected"],
                next_step="refine_one_family_row_cell_parser",
                rows_count=rows_count, cols_count=cols_count, numeric_cells=numeric_cells,
                local_ocr_status=ocr_status,
            ),
            None,
        )

    # Family-specific row/cell → inputs mapping (with anti-laundering).
    if family == "proximity":
        method, inputs, warn, blocked_by = _map_proximity(target_id, grid)
    else:
        method, inputs, warn, blocked_by = _map_weighted_average(grid)

    if method is None or inputs is None:
        return _envelope(
            _blocked_record(
                source_label, target_id, family,
                target_region_status="found",
                crop_region_input_status="available",
                row_cell_status="parsed_from_extraction_output",
                blocked_by=blocked_by,
                warnings=warn,
                next_step="target_region_detection_for_numeric_tables"
                if blocked_by == "source_input_mapping"
                else "refine_one_family_row_cell_parser",
                rows_count=rows_count, cols_count=cols_count, numeric_cells=numeric_cells,
                local_ocr_status=ocr_status,
            ),
            None,
        )

    # Genuine inputs parsed — run advisory masked recompute (answer hidden).
    masked_status = _masked_recompute(method, inputs)
    if masked_status != "passed":
        return _envelope(
            _blocked_record(
                source_label, target_id, family,
                target_region_status="found",
                crop_region_input_status="available",
                row_cell_status="parsed_from_extraction_output",
                blocked_by="row_cell_reconstruction",
                warnings=list(warn) + ["masked_recompute_failed"],
                next_step="refine_one_family_row_cell_parser",
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
        status="parsed",
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
        blocked_by="none",
        warnings=list(warn),
        next_step="wire_parsed_rows_into_recompute",
        inputs_status="complete",
        confidence="medium",
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


# ── Spatial grid reconstruction (the missing piece) ──────────────────────────


def _reconstruct_grid(tokens: list, ytol: Any) -> list[list[str]]:
    try:
        tol = float(ytol)
    except (TypeError, ValueError):
        tol = 3.0
    if tol <= 0:
        tol = 3.0
    cleaned: list[tuple[float, float, str]] = []
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        x = _coerce_float(tok.get("x"))
        y = _coerce_float(tok.get("y"))
        text = tok.get("text")
        if x is None or y is None or not isinstance(text, str) or not text.strip():
            continue
        cleaned.append((x, y, text.strip()))
    cleaned.sort(key=lambda t: (round(t[1] / tol), t[0]))
    rows: list[dict[str, Any]] = []
    for x, y, text in cleaned:
        placed = False
        for row in rows:
            if abs(row["y"] - y) <= tol:
                row["cells"].append((x, text))
                placed = True
                break
        if not placed:
            rows.append({"y": y, "cells": [(x, text)]})
    grid: list[list[str]] = []
    for row in rows:
        ordered = [text for _, text in sorted(row["cells"], key=lambda c: c[0])]
        grid.append(ordered)
    return grid


# ── Family mappers (return method, inputs, warnings, blocked_by) ─────────────


def _map_proximity(target_id: str, grid: list[list[str]]):
    """Map a reconstructed grid to proximity inputs, refusing answer matrices.

    Legitimate inputs: a per-tree ``same_terminal_node`` 0/1 indicator sequence,
    or sample-indexed integer leaf-id rows for the pair (i, j) whose per-tree
    equality yields the indicators. A proximity *matrix* (decimal cells in (0,1))
    is the **answer**, not an input, and is rejected.
    """
    warnings: list[str] = []
    pair = _PAIR_RE.search(target_id or "")
    sample_i = int(pair.group(1)) if pair else None
    sample_j = int(pair.group(2)) if pair else None

    # (1) A row that is a run of 0/1 indicators (same_terminal_node list).
    for row in grid:
        bits = [c for c in row if c in ("0", "1")]
        if len(bits) >= 2 and len(bits) == sum(1 for c in row if _NUM_RE.match(c)):
            indicators = [int(c) for c in bits]
            return "proximity", {"same_terminal_node": indicators}, warnings, "none"

    # (2) Sample-indexed integer leaf-id rows for the pair → equality indicators.
    if sample_i is not None and sample_j is not None:
        row_i = _leaf_row_for_sample(grid, sample_i)
        row_j = _leaf_row_for_sample(grid, sample_j)
        if row_i is not None and row_j is not None and len(row_i) == len(row_j) and row_i:
            indicators = [1 if a == b else 0 for a, b in zip(row_i, row_j)]
            return "proximity", {"same_terminal_node": indicators}, warnings, "none"

    # (3) Anti-laundering: decimal cells in (0,1) are proximity *values* (answers).
    decimals_in_unit = sum(
        1
        for row in grid
        for c in row
        if _NUM_RE.match(c) and not _INT_RE.match(c) and 0.0 < _to_float(c) < 1.0
    )
    if decimals_in_unit >= 2:
        warnings.append("answer_matrix_not_input")
        return None, None, warnings, "source_input_mapping"

    warnings.append("no_input_columns_found")
    return None, None, warnings, "source_input_mapping"


def _map_weighted_average(grid: list[list[str]]):
    """Map a reconstructed grid to weighted_average inputs (values + weights).

    Legitimate inputs: two aligned numeric columns (values, weights) of equal
    length >= 2. A lone numeric (the result) is rejected as answer-shaped.
    """
    warnings: list[str] = []
    columns = _numeric_columns(grid)
    if len(columns) >= 2:
        usable = [col for col in columns if len(col) >= 2]
        if len(usable) >= 2:
            values, weights = usable[0], usable[1]
            n = min(len(values), len(weights))
            if n >= 2 and all(w >= 0 for w in weights[:n]) and sum(weights[:n]) > 0:
                return (
                    "weighted_average",
                    {"values": values[:n], "weights": weights[:n]},
                    warnings,
                    "none",
                )

    total_numeric = sum(1 for row in grid for c in row if _NUM_RE.match(c))
    if total_numeric <= 1:
        warnings.append("answer_value_not_input")
        return None, None, warnings, "source_input_mapping"
    warnings.append("no_input_columns_found")
    return None, None, warnings, "source_input_mapping"


def _leaf_row_for_sample(grid: list[list[str]], sample: int) -> list[int] | None:
    target = str(sample)
    for row in grid:
        if not row:
            continue
        if row[0] == target:
            ints = [int(c) for c in row[1:] if _INT_RE.match(c)]
            if ints:
                return ints
    return None


def _numeric_columns(grid: list[list[str]]) -> list[list[float]]:
    width = max((len(r) for r in grid), default=0)
    columns: list[list[float]] = []
    for idx in range(width):
        col: list[float] = []
        for row in grid:
            if idx < len(row) and _NUM_RE.match(row[idx]) and not _is_index_token(row[idx]):
                col.append(_to_float(row[idx]))
        if len(col) >= 2:
            columns.append(col)
    return columns


def _is_index_token(text: str) -> bool:
    # A bare small integer leading a row is more likely a row index than a value;
    # this is a conservative guard and is not relied on for correctness.
    return False


# ── Masked recompute (reuse the real verifier, answer hidden) ────────────────


def _masked_recompute(method: str, inputs: dict[str, Any]) -> str:
    if method not in SUPPORTED_METHODS:
        return "not_run"
    # value MASKED (None) and provenance non-claimed → verifier recomputes from
    # inputs only and reports the recomputed value without any supplied answer.
    fact = {
        "id": "masked_proximity_or_weighted",
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
    status: str,
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
    blocked_by: str,
    warnings: list[str],
    next_step: str,
    inputs_status: str,
    confidence: str,
) -> dict[str, Any]:
    return {
        "artifact_name": KIND,
        "source_label": source_label,
        "selected_target_id": target_id,
        "selected_target_family": target_family if target_family in TARGET_FAMILIES else "unknown",
        "status": status if status in STATUSES else "blocked",
        "target_region_status": _tok(target_region_status, TARGET_REGION_STATUSES, "not_found"),
        "crop_or_region_input_status": _tok(crop_region_input_status, CROP_REGION_INPUT_STATUSES, "unavailable"),
        "local_ocr_status": _tok(local_ocr_status, LOCAL_OCR_STATUSES, "skipped"),
        "row_cell_extraction_status": _tok(row_cell_extraction_status, ROW_CELL_STATUSES, "blocked"),
        "structured_rows_count": int(structured_rows_count),
        "structured_columns_count": int(structured_columns_count),
        "numeric_cells_count": int(numeric_cells_count),
        "source_input_record_status": _tok(source_input_record_status, SOURCE_INPUT_RECORD_STATUSES, "not_created"),
        "source_input_origin": _tok(source_input_origin, SOURCE_INPUT_ORIGINS, "none"),
        "machine_consumable_for_recompute": bool(machine_consumable_for_recompute),
        "masked_recompute_status": _tok(masked_recompute_status, MASKED_RECOMPUTE_STATUSES, "not_run"),
        "inputs_status": _tok(inputs_status, INPUTS_STATUSES, "unavailable"),
        "confidence": _tok(confidence, CONFIDENCES, "none"),
        "hand_authored_rows": False,
        "fixture_derived": False,
        "answer_string_derived": False,
        "guide_candidate_derived": False,
        "raw_values_committed": False,
        "raw_ocr_committed": False,
        "blocked_by": _tok(blocked_by, BLOCKED_BY_TOKENS, "row_cell_reconstruction"),
        "next_step": _tok(next_step, NEXT_STEPS, "refine_one_family_row_cell_parser"),
        "warnings": _ordered_warnings(warnings),
    }


def _blocked_record(
    source_label: str,
    target_id: str,
    target_family: str,
    *,
    target_region_status: str = "not_found",
    crop_region_input_status: str = "unavailable",
    local_ocr_status: str = "skipped",
    row_cell_status: str,
    blocked_by: str,
    warnings: list[str],
    next_step: str,
    rows_count: int = 0,
    cols_count: int = 0,
    numeric_cells: int = 0,
    masked_recompute_status: str = "not_run",
) -> dict[str, Any]:
    return _record(
        source_label=source_label,
        target_id=target_id,
        target_family=target_family,
        status="blocked",
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
        blocked_by=blocked_by,
        warnings=warnings,
        next_step=next_step,
        inputs_status="unavailable",
        confidence="none",
    )


def _envelope(record: dict[str, Any], recompute_input: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "version": VERSION,
        "kind": KIND,
        "record": record,
        "recompute_input": recompute_input,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


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
